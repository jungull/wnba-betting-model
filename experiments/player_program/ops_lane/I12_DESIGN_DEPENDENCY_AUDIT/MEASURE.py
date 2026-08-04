#!/usr/bin/env python3
"""MEASURE.py — run design_dependency_audit against the REAL frozen artifacts.

Every number in REPORT.md comes from this script. It writes MEASUREMENTS.json and prints a
summary. It reads only:

    projected_exposure_v1/team_possession_prior_v1.parquet    (frozen incumbent prior)
    possessions_v2/possessions_raw_v2.parquet                  (frozen possession events)
    feature_gate.py / comparison_gate.py / gate_invocation.py  (bytes only, plus import of the first)
    stage2b/P25_OFFSET_DEPENDENCY_GUARD/                       (read-only cross-check)

It reads NOTHING under stage2b/SEALED_RESULTS and contains no path that could.

Usage:  python MEASURE.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# this script imports modules that live OUTSIDE this node's write scope (feature_gate, and P25's
# guard for the cross-check). Bytecode caching would write .pyc files into their directories, so
# it is disabled before any of those imports happen.
sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
PP = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PP))

import feature_gate as fg                                                    # noqa: E402
import design_dependency_audit as A                                          # noqa: E402

PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"

M: dict = {}


def build_panel() -> pd.DataFrame:
    """The frozen incumbent panel: own/opp pace estimates, the incumbent projection as offset,
    and the regulation-equivalent target. Recipe identical to the one P25 used, rebuilt here
    independently so the two node's row counts are a cross-check rather than a shared assumption."""
    prior = pd.read_parquet(PRIOR)
    M["prior_rows_total"] = int(len(prior))
    M["prior_games_total"] = int(prior.game_id.nunique())
    M["prior_rows_unresolved"] = int((~prior.pace_resolved).sum())

    s = prior.groupby("game_id")["team_pace_estimate"].transform("sum")
    prior = prior.assign(own_est=prior.team_pace_estimate, opp_est=s - prior.team_pace_estimate)
    d = prior[prior.pace_resolved].copy()
    d = d[np.isfinite(d.own_est) & np.isfinite(d.opp_est)
          & np.isfinite(d.projected_team_off_possessions)].reset_index(drop=True)

    poss = pd.read_parquet(POSS, columns=["game_id", "offense_team_id", "period"])
    gm = poss.groupby("game_id")["period"].max().rename("max_period").reset_index()
    gm["game_minutes"] = 40 + 5 * np.maximum(0, gm.max_period - 4)
    n = (poss.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
         .rename(columns={"offense_team_id": "team_id"}))
    n = n.merge(gm[["game_id", "game_minutes"]], on="game_id", validate="m:1")
    n["target"] = n.n_off_poss * 40.0 / n.game_minutes
    d = d.merge(n[["game_id", "team_id", "target"]], on=["game_id", "team_id"],
                how="left", validate="1:1")
    d["contrast_own_minus_opp"] = d.own_est - d.opp_est
    for lvl in sorted(d.pace_source.unique()):
        d[f"src_{lvl}"] = (d.pace_source == lvl).astype(float)
    return d


def slim(rec: dict) -> dict:
    """The decision-bearing part of an audit record, for MEASUREMENTS.json."""
    return {
        "label": rec["design"]["label"],
        "blocks": rec["design"]["blocks"],
        "n_rows": rec.get("n_rows"),
        "n_complete_rows": rec.get("n_complete_rows"),
        "passed": rec["passed"],
        "blocking_kinds": sorted({f["kind"] for f in rec["blocking"]}),
        "finding_kinds": rec["finding_kinds"],
        "augmented_rank": {k: rec.get("augmented_rank", {}).get(k) for k in
                           ("n_features", "numerical_rank", "full_rank", "condition_number",
                            "singular_values", "produced_by")},
        "r2_column_on_rest": rec.get("affine_reconstruction", {}).get("r2_column_on_rest"),
        "null_space_relations": rec.get("affine_reconstruction", {}).get("null_space_relations"),
        "offset_reconstruction": rec.get("offset_reconstruction"),
        "candidate_vs_offset": rec.get("candidate_vs_offset"),
        "grants_offset_slope_freedom": rec.get("grants_offset_slope_freedom"),
        "feature_gate_record": rec.get("feature_gate_record"),
        "folds": rec.get("folds"),
        "cluster_fold_check": rec.get("cluster_fold_check"),
        "receipt_sha256": rec["receipt_sha256"],
    }


def main() -> int:
    t0 = time.time()

    # ---------------------------------------------------------------- 1. frozen gate bytes
    M["frozen_gate_status"] = A.frozen_gate_status()
    M["receipt_integrity_sha256"] = hashlib.sha256(
        (PP / "receipt_integrity.py").read_bytes()).hexdigest()
    M["frozen_gate_bytes"] = {n: int((PP / n).stat().st_size) for n in A.FROZEN_GATE_DIGESTS}

    # G00_LIVE_RECONCILIATION recorded expected digests for the same three files; compare.
    g00 = json.loads((PP / "orchestration" / "nodes" / "G00_LIVE_RECONCILIATION"
                      / "RECONCILIATION.json").read_text())
    fh = g00["checks"]["frozen_hashes"]
    M["g00_recorded_vs_live"] = {
        n: {"g00_expected": fh[f"experiments/player_program/{n}"]["expected"],
            "live": M["frozen_gate_status"]["live"][n],
            "agrees": fh[f"experiments/player_program/{n}"]["expected"]
                      == M["frozen_gate_status"]["live"][n]}
        for n in A.FROZEN_GATE_DIGESTS}

    # PROGRAM_STATE pins the same digests; three independent sources must agree on the bytes.
    ps = json.loads((PP / "PROGRAM_STATE.json").read_text())
    sc = ps["shared_contracts"]
    M["program_state_vs_live"] = {
        n: {"program_state": sc[n.replace(".py", "")]["sha256"],
            "live": M["frozen_gate_status"]["live"][n],
            "agrees": sc[n.replace(".py", "")]["sha256"] == M["frozen_gate_status"]["live"][n]}
        for n in A.FROZEN_GATE_DIGESTS}
    M["program_state_vs_live"]["receipt_integrity.py"] = {
        "program_state": sc["receipt_integrity"]["sha256"],
        "live": M["receipt_integrity_sha256"],
        "agrees": sc["receipt_integrity"]["sha256"] == M["receipt_integrity_sha256"]}

    # does the program's own open-gap list name the identifiability gap S5 describes?
    gaps = json.dumps(ps["open_methodological_gaps"]).lower()
    M["program_state_open_gaps"] = {
        "n_entries": len(ps["open_methodological_gaps"]),
        "ids": [g["id"] for g in ps["open_methodological_gaps"]],
        "mentions_offset": "offset" in gaps,
        "mentions_augmented": "augmented" in gaps,
        "mentions_identifiab": "identifiab" in gaps,
        "mentions_rank": "rank" in gaps,
    }

    # ---------------------------------------------------------------- 2. the panel
    d = build_panel()
    M["panel_rows"] = int(len(d))
    M["panel_game_clusters"] = int(d.game_id.nunique())
    M["panel_rows_per_cluster"] = sorted(d.groupby("game_id").size().unique().tolist())
    M["panel_target_nulls"] = int(d.target.isna().sum())
    dev = (d.own_est + d.opp_est) - 2 * d.projected_team_off_possessions
    M["s5_identity_max_abs_deviation"] = float(np.abs(dev).max())
    M["s5_identity_rows_exactly_zero"] = int((dev == 0).sum())
    M["corr_own_projected"] = round(float(np.corrcoef(d.own_est,
                                                      d.projected_team_off_possessions)[0, 1]), 6)
    M["corr_opp_projected"] = round(float(np.corrcoef(d.opp_est,
                                                      d.projected_team_off_possessions)[0, 1]), 6)
    M["corr_own_opp"] = round(float(np.corrcoef(d.own_est, d.opp_est)[0, 1]), 6)
    M["feature_gate_corr_threshold_default"] = 0.999
    M["pace_source_counts"] = {k: int(v) for k, v in d.pace_source.value_counts().items()}
    M["pace_source_by_season"] = (pd.crosstab(d.season, d.pace_source)
                                  .astype(int).to_dict(orient="index"))
    M["pace_level_source_crosstab"] = (pd.crosstab(d.pace_level, d.pace_source)
                                       .astype(int).to_dict(orient="index"))
    M["pace_level_is_deterministic_in_pace_source"] = bool(
        d.groupby("pace_source")["pace_level"].nunique().max() == 1
        and d.groupby("pace_level")["pace_source"].nunique().max() == 1)

    off = d.projected_team_off_possessions.to_numpy(float)
    y = d.target.to_numpy(float)

    # ---------------------------------------------------------------- 3. feature_gate alone
    try:
        fg_rec = fg.audit(d, ["own_est", "opp_est"], offset=off, target=y)
        M["feature_gate_alone_on_own_opp"] = {
            "passed": bool(fg_rec["passed"]),
            "findings": [f["kind"] for f in fg_rec["findings"]],
            "n_features_seen": fg_rec["design_rank"]["n_features"],
            "numerical_rank": fg_rec["design_rank"]["numerical_rank"],
            "condition_number": fg_rec["design_rank"]["condition_number"],
            "arguments_supplied": ["offset", "target"],
        }
    except fg.FeatureGateFailure as exc:
        M["feature_gate_alone_on_own_opp"] = {"passed": False, "blocking": json.loads(str(exc))}

    # ---------------------------------------------------------------- 4. the audited designs
    designs = {}

    designs["A_own_opp_vs_offset"] = A.Design(
        d, x=["own_est", "opp_est"], offset=["projected_team_off_possessions"],
        fold="season", cluster="game_id", label="A: X={own_est,opp_est}, offset=projection")

    designs["B_nuisance_carries_opponent"] = A.Design(
        d, x=["own_est"], offset=["projected_team_off_possessions"], nuisance=["opp_est"],
        fold="season", cluster="game_id",
        label="B: X={own_est}, nuisance={opp_est}, offset=projection")

    designs["C_orthogonal_contrast"] = A.Design(
        d, x=["contrast_own_minus_opp"], offset=["projected_team_off_possessions"],
        fold="season", cluster="game_id",
        label="C: X={own-opp contrast}, offset=projection")

    designs["D_full_tier_dummy_set"] = A.Design(
        d, x=["contrast_own_minus_opp"], offset=["projected_team_off_possessions"],
        nuisance=[f"src_{s}" for s in sorted(d.pace_source.unique())],
        fold="season", cluster="game_id",
        label="D: C plus the COMPLETE pace_source dummy set (no reference level dropped)")

    designs["E_tier_dummies_reference_dropped"] = A.Design(
        d, x=["contrast_own_minus_opp"], offset=["projected_team_off_possessions"],
        nuisance=[f"src_{s}" for s in sorted(d.pace_source.unique())][1:],
        fold="season", cluster="game_id",
        label="E: D with the reference level dropped (the correct parameterisation)")

    designs["F_duplicate_tier_encoding"] = A.Design(
        d, x=["contrast_own_minus_opp"], offset=["projected_team_off_possessions"],
        nuisance=[f"src_{s}" for s in sorted(d.pace_source.unique())][1:] + ["pace_level"],
        fold="season", cluster="game_id",
        label="F: E plus pace_level, the same tier ladder under a second encoding")

    M["audits"] = {}
    for key, des in designs.items():
        rec = A.audit_design(des, target=y)
        M["audits"][key] = slim(rec)

    # column-ORDER sensitivity of the recovered relation, on the real artifact: the CONTENT of the
    # recovered identity must not depend on the order the caller declared the columns in; only its
    # floating-point residual may.
    perms = {
        "x_then_offset": A.Design(d, x=["own_est", "opp_est"],
                                  offset=["projected_team_off_possessions"], label="perm1"),
        "reversed_x": A.Design(d, x=["opp_est", "own_est"],
                               offset=["projected_team_off_possessions"], label="perm2"),
        "opp_in_nuisance": A.Design(d, x=["own_est"], nuisance=["opp_est"],
                                    offset=["projected_team_off_possessions"], label="perm3"),
    }
    M["column_order_invariance"] = {}
    for k, des in perms.items():
        r = A.audit_design(des, target=y, run_feature_gate=False)
        rel = r["affine_reconstruction"]["null_space_relations"]
        M["column_order_invariance"][k] = {
            "n_relations": len(rel),
            "coefficients_normalised": (
                {c: round(v / rel[0]["coefficients"]["projected_team_off_possessions"], 9)
                 for c, v in rel[0]["coefficients"].items()} if rel else None),
            "max_abs_deviation": rel[0]["max_abs_deviation"] if rel else None,
            "augmented_rank": r["augmented_rank"]["numerical_rank"],
            "blocking_kinds": sorted({f["kind"] for f in r["blocking"]}),
        }

    # the condition number of an EXACTLY singular design is rounding noise, and reusable guidance
    # has to say so with a number attached: re-audit design A under row permutations and report the
    # spread of the condition number against the stability of the rank finding.
    conds, ranks, r2s = [], [], []
    for seed in range(8):
        perm = np.random.default_rng(seed).permutation(len(d))
        dp = d.iloc[perm].reset_index(drop=True)
        r = A.audit_design(A.Design(dp, x=["own_est", "opp_est"],
                                    offset=["projected_team_off_possessions"]),
                           run_feature_gate=False)
        conds.append(r["augmented_rank"]["condition_number"])
        ranks.append((r["augmented_rank"]["numerical_rank"], r["augmented_rank"]["n_features"]))
        r2s.append(r["offset_reconstruction"]["projected_team_off_possessions"]["r2_on_design"])
    M["condition_number_stability_under_row_permutation"] = {
        "n_permutations": len(conds),
        "min": min(conds), "max": max(conds),
        "relative_spread": (max(conds) - min(conds)) / min(conds),
        "rank_findings": sorted({f"{a}/{b}" for a, b in ranks}),
        "r2_offset_on_design_values": sorted(set(r2s)),
        "p25_recorded_condition_number": None,
    }

    # fail-closed behaviour of the entry point, on the real design A
    try:
        A.assert_design_identified(designs["A_own_opp_vs_offset"], target=y)
        M["assert_design_identified_on_A"] = {"raised": False}
    except A.DesignDependencyFailure as exc:
        M["assert_design_identified_on_A"] = {
            "raised": True, "n_blocking": len(exc.blocking),
            "kinds": sorted({b["kind"] for b in exc.blocking})}

    # ---------------------------------------------------------------- 5. cross-check vs P25
    sys.path.insert(0, str(PP / "stage2b" / "P25_OFFSET_DEPENDENCY_GUARD"))
    try:
        import offset_dependency_guard as G                                   # noqa: E402
        p25_kinds = None
        try:
            G.audit_augmented_design(d, ["own_est", "opp_est"], off)
            p25_kinds = []
        except G.OffsetDependencyFailure as exc:
            p25_kinds = sorted({b["kind"] for b in exc.blocking})
        M["p25_cross_check"] = {
            "entry_point": "offset_dependency_guard.audit_augmented_design",
            "entry_point_found": p25_kinds is not None,
            "p25_blocking_kinds": p25_kinds,
            "i12_blocking_kinds": M["audits"]["A_own_opp_vs_offset"]["blocking_kinds"],
            "both_block": bool(p25_kinds) and not M["audits"]["A_own_opp_vs_offset"]["passed"],
            "p25_module_sha256": hashlib.sha256(
                (PP / "stage2b" / "P25_OFFSET_DEPENDENCY_GUARD"
                 / "offset_dependency_guard.py").read_bytes()).hexdigest(),
        }
        p25_meas = json.loads((PP / "stage2b" / "P25_OFFSET_DEPENDENCY_GUARD"
                               / "MEASUREMENTS.json").read_text())
        M["condition_number_stability_under_row_permutation"]["p25_recorded_condition_number"] = (
            p25_meas.get("augmented_rank", {}).get("condition_number"))
        M["condition_number_stability_under_row_permutation"]["i12_vs_p25_relative_difference"] = (
            abs(M["audits"]["A_own_opp_vs_offset"]["augmented_rank"]["condition_number"]
                - p25_meas["augmented_rank"]["condition_number"])
            / p25_meas["augmented_rank"]["condition_number"])
        M["p25_agreement_on_shared_numbers"] = {
            "rows": {"p25": p25_meas.get("identity_rows"), "i12": M["panel_rows"],
                     "agrees": p25_meas.get("identity_rows") == M["panel_rows"]},
            "clusters": {"p25": p25_meas.get("identity_game_clusters"),
                         "i12": M["panel_game_clusters"],
                         "agrees": p25_meas.get("identity_game_clusters")
                                   == M["panel_game_clusters"]},
            "max_abs_deviation": {"p25": p25_meas.get("identity_max_abs_deviation"),
                                  "i12": M["s5_identity_max_abs_deviation"],
                                  "agrees": p25_meas.get("identity_max_abs_deviation")
                                            == M["s5_identity_max_abs_deviation"]},
            "corr_own_projected": {"p25": p25_meas.get("corr_own_projected"),
                                   "i12": M["corr_own_projected"],
                                   "agrees": p25_meas.get("corr_own_projected")
                                             == M["corr_own_projected"]},
            # like-for-like: P25's r2_offset_on_own_alone is the offset regressed on own_est ONLY,
            # which in this node's block language is design B's X block.
            "r2_offset_on_own_alone": {
                "p25": p25_meas.get("r2_offset_on_own_alone"),
                "i12": M["audits"]["B_nuisance_carries_opponent"]["offset_reconstruction"]
                       ["projected_team_off_possessions"]["r2_on_x"],
                "agrees": p25_meas.get("r2_offset_on_own_alone")
                          == M["audits"]["B_nuisance_carries_opponent"]["offset_reconstruction"]
                             ["projected_team_off_possessions"]["r2_on_x"]},
            "offset_tie_groups_size_ge_2": {
                "p25": p25_meas.get("offset_tie_groups_size_ge_2"),
                "i12": M["audits"]["A_own_opp_vs_offset"]["candidate_vs_offset"]["own_est"]
                       ["tie_group_probe"]["tie_groups_size_ge_2"],
                "agrees": p25_meas.get("offset_tie_groups_size_ge_2")
                          == M["audits"]["A_own_opp_vs_offset"]["candidate_vs_offset"]["own_est"]
                             ["tie_group_probe"]["tie_groups_size_ge_2"]},
            "offset_tie_groups_where_own_est_constant": {
                "p25": p25_meas.get("offset_tie_groups_where_own_est_constant"),
                "i12": M["audits"]["A_own_opp_vs_offset"]["candidate_vs_offset"]["own_est"]
                       ["tie_group_probe"]["groups_where_column_constant"],
                "agrees": p25_meas.get("offset_tie_groups_where_own_est_constant")
                          == M["audits"]["A_own_opp_vs_offset"]["candidate_vs_offset"]["own_est"]
                             ["tie_group_probe"]["groups_where_column_constant"]},
        }
    except Exception as exc:                                     # pragma: no cover - diagnostic
        M["p25_cross_check"] = {"error": f"{type(exc).__name__}: {exc}"}

    # ---------------------------------------------------------------- 6. gate bytes AFTER the run
    after = A.frozen_gate_digests()
    M["frozen_gates_unchanged_after_run"] = {
        n: {"before": M["frozen_gate_status"]["live"][n], "after": after[n],
            "unchanged": after[n] == M["frozen_gate_status"]["live"][n]
                         and after[n] == A.FROZEN_GATE_DIGESTS[n]}
        for n in after}

    M["runtime_seconds"] = round(time.time() - t0, 3)
    M["module_sha256"] = hashlib.sha256(
        (HERE / "design_dependency_audit.py").read_bytes()).hexdigest()

    (HERE / "MEASUREMENTS.json").write_text(json.dumps(M, indent=1, sort_keys=True, default=str))
    print(json.dumps({k: M[k] for k in
                      ("panel_rows", "panel_game_clusters", "s5_identity_max_abs_deviation",
                       "feature_gate_alone_on_own_opp", "runtime_seconds")},
                     indent=1, default=str))
    for k, v in M["audits"].items():
        print(f"{k:34s} passed={v['passed']!s:5s} rank="
              f"{v['augmented_rank']['numerical_rank']}/{v['augmented_rank']['n_features']} "
              f"cond={v['augmented_rank']['condition_number']:.4g} "
              f"blocking={v['blocking_kinds']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
