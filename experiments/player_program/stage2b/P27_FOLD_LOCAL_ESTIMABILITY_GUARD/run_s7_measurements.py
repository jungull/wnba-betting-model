#!/usr/bin/env python3
"""run_s7_measurements.py -- run the S7 guard against the frozen artifacts and emit MEASUREMENTS.json.

Reads only. Writes only inside this node's directory.

    python experiments/player_program/stage2b/P27_FOLD_LOCAL_ESTIMABILITY_GUARD/run_s7_measurements.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parent.parent                       # experiments/player_program
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PROGRAM))

import fold_estimability_guard as G                # noqa: E402
import feature_gate as fg                          # noqa: E402  (frozen, READ ONLY)

PRIOR = PROGRAM / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PROGRAM / "possessions_v2" / "possessions_raw_v2.parquet"
REGULATION_MIN = 40.0                              # EVIDENCE_PACKET_V2.incumbent.constants


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_universe() -> pd.DataFrame:
    """The 2,982-row / 1,491-cluster universe, with the incumbent offset and the tier partition."""
    d = pd.read_parquet(PRIOR)
    r = d[d["pace_resolved"]].copy().reset_index(drop=True)

    # own / opponent trailing pace estimate. Both team-rows of a game are present, so the
    # opponent's estimate is the game total minus the team's own. This is the S5 construction.
    tot = r.groupby("game_id")["team_pace_estimate"].transform("sum")
    r["own_pace_est"] = r["team_pace_estimate"].astype(float)
    r["opp_pace_est"] = (tot - r["team_pace_estimate"]).astype(float)

    # tier partition, one-hot over the three resolved pace_source levels
    for lvl in ["league_prior_all", "team_window_prior_season", "team_window_same_season"]:
        r[f"tier_{lvl}"] = (r["pace_source"] == lvl).astype(float)

    r["offset_projected"] = r["projected_team_off_possessions"].astype(float)
    return r


def realised_target() -> pd.DataFrame:
    """Regulation-equivalent realised offensive possessions, per the frozen incumbent formula.

    EVIDENCE_PACKET_V2.possession_unit_ruling permits realised duration to normalise a COMPLETED
    historical outcome only. This is the historical outcome column; it never enters the design.
    """
    p = pd.read_parquet(POSS, columns=["game_id", "offense_team_id", "period"])
    g = p.groupby("game_id").agg(max_period=("period", "max")).reset_index()
    g["game_minutes"] = REGULATION_MIN + 5.0 * np.maximum(0, g["max_period"] - 4)
    n = (p.groupby(["game_id", "offense_team_id"]).size().rename("n_off_poss").reset_index()
         .rename(columns={"offense_team_id": "team_id"}))
    n = n.merge(g, on="game_id", how="left")
    n["realised_off_poss"] = n["n_off_poss"] * REGULATION_MIN / n["game_minutes"]
    return n[["game_id", "team_id", "realised_off_poss"]]


TIERS_ONEHOT = ["tier_league_prior_all", "tier_team_window_prior_season",
                "tier_team_window_same_season"]
TIERS_REFCODED = ["tier_league_prior_all", "tier_team_window_prior_season"]  # ref = same_season


def main() -> int:
    U = build_universe()
    tgt = realised_target()
    U = U.merge(tgt, on=["game_id", "team_id"], how="left")

    out: dict = {
        "schema": "s7_measurements/1",
        "node": "P27_FOLD_LOCAL_ESTIMABILITY_GUARD",
        "epistemic_status": ("INFRASTRUCTURE + task-specific INVARIANT. Proves an arm/fold is "
                             "estimable before it is fitted. Does not establish that an estimable "
                             "arm is a real effect."),
        "inputs": {
            "team_possession_prior_v1.parquet": {"path": str(PRIOR.relative_to(PROGRAM.parent.parent)),
                                                 "sha256": file_sha256(PRIOR)},
            "possessions_raw_v2.parquet": {"path": str(POSS.relative_to(PROGRAM.parent.parent)),
                                           "sha256": file_sha256(POSS)},
        },
        "frozen_gate_constants_mirrored": {
            "feature_gate.RANK_TOL": fg.RANK_TOL, "guard.RANK_TOL": G.RANK_TOL,
            "feature_gate.COND_MAX": fg.COND_MAX, "guard.COND_MAX": G.COND_MAX,
            "agree": bool(fg.RANK_TOL == G.RANK_TOL and fg.COND_MAX == G.COND_MAX)},
    }

    # ---------------------------------------------------------------- M1 universe
    all_rows = pd.read_parquet(PRIOR)
    out["M1_universe"] = {
        "rows_in_artifact": int(len(all_rows)),
        "pace_resolved_true": int(all_rows["pace_resolved"].sum()),
        "pace_resolved_false": int((~all_rows["pace_resolved"]).sum()),
        "resolved_rows": int(len(U)),
        "resolved_game_clusters": int(U["game_id"].nunique()),
        "team_rows_per_cluster": {str(k): int(v) for k, v in
                                  U.groupby("game_id").size().value_counts().items()},
        "rows_with_realised_target": int(U["realised_off_poss"].notna().sum()),
        "packet_claim": {"team_game_rows": 2982, "game_clusters": 1491},
        "matches_packet": bool(len(U) == 2982 and U["game_id"].nunique() == 1491),
    }

    # ---------------------------------------------------------------- M2 S7 reproduction
    ct = pd.crosstab(U["pace_source"], U["season"])
    out["M2_S7_reproduction"] = {
        "pace_source_by_season": {str(i): {str(c): int(ct.loc[i, c]) for c in ct.columns}
                                  for i in ct.index},
        "packet_figure": json.loads(json.dumps(
            {"league_prior_all": {"2021": 28, "2022": 0, "2023": 0, "2024": 0, "2025": 3,
                                  "2026": 6},
             "team_window_prior_season": {"2021": 0, "2022": 36, "2023": 36, "2024": 36,
                                          "2025": 36, "2026": 39},
             "team_window_same_season": {"2021": 382, "2022": 442, "2023": 484, "2024": 488,
                                         "2025": 581, "2026": 385}})),
        "identically_zero_cells": [{"tier": str(i), "season": int(c)}
                                   for i in ct.index for c in ct.columns
                                   if int(ct.loc[i, c]) == 0],
        "n_seasons": int(ct.shape[1]),
    }
    zero_seasons = sorted({int(c) for i in ct.index for c in ct.columns
                           if int(ct.loc[i, c]) == 0})
    out["M2_S7_reproduction"]["seasons_with_an_identically_zero_tier"] = zero_seasons
    out["M2_S7_reproduction"]["n_folds_with_identically_zero_tier_SEASON_BLOCK"] = len(zero_seasons)
    out["M2_S7_reproduction"]["claim_four_of_six"] = bool(
        len(zero_seasons) == 4 and ct.shape[1] == 6)

    # ---------------------------------------------------------------- M3 S5 reproduction
    dev = (U["own_pace_est"] + U["opp_pace_est"] - 2.0 * U["offset_projected"]).abs()
    out["M3_S5_reproduction"] = {
        "identity": "own_pace_est + opp_pace_est == 2 * projected_team_off_possessions",
        "rows": int(len(U)), "max_abs_deviation": float(dev.max()),
        "corr_own_projected": round(float(np.corrcoef(U["own_pace_est"],
                                                      U["offset_projected"])[0, 1]), 4),
        "corr_own_opp": round(float(np.corrcoef(U["own_pace_est"],
                                                U["opp_pace_est"])[0, 1]), 4),
        "packet_figure": {"rows": 2982, "max_abs_deviation": 0.0,
                          "corr_own_projected": 0.7738, "corr_own_opp": 0.1977},
    }

    # ---------------------------------------------------------------- M4 what the frozen gate says
    # feature_gate.audit is called EXACTLY as a caller would, with every applicable argument
    # supplied per GATE_INVOCATION_CONTRACT section 3.1. It is not modified or subclassed.
    def frozen_gate(names):
        try:
            rec = fg.audit(U, names, offset=U["offset_projected"].to_numpy(float),
                           target=U["realised_off_poss"].to_numpy(float), test_df=U)
            return {"raised": False, "passed": rec["passed"],
                    "findings": rec["findings"], "design_rank": rec["design_rank"]}
        except fg.FeatureGateFailure as e:
            return {"raised": True, "blocking": json.loads(str(e))}

    out["M4_frozen_gate_on_pooled_design"] = {
        "opponent_arm_features_own_and_opp": frozen_gate(["own_pace_est", "opp_pace_est"]),
        "tier_onehot_as_features": frozen_gate(TIERS_ONEHOT),
        "note": ("feature_gate.audit was invoked with offset=, target= and test_df= supplied. "
                 "The design_rank block is computed from `names` alone; the offset column is "
                 "used only for the pairwise deterministic_transform_of_offset correlation."),
    }

    # ------------------------------------- M6 the frozen gate, pooled vs per fold, on tier dummies
    # The most direct possible statement of GATE_INVOCATION_CONTRACT section 1: the SAME frozen
    # gate, the SAME columns, passing pooled and blocking per fold. No wrapper involved.
    def gate_on(rows, names):
        try:
            rec = fg.audit(rows, names, offset=rows["offset_projected"].to_numpy(float),
                           target=rows["realised_off_poss"].to_numpy(float), test_df=rows)
            return {"passed": rec["passed"], "blocking_kinds": [], "n_rows": int(len(rows))}
        except fg.FeatureGateFailure as e:
            b = json.loads(str(e))
            return {"passed": False, "blocking_kinds": sorted({x["kind"] for x in b}),
                    "blocking": b, "n_rows": int(len(rows))}

    per_fold = {f"train_{s}": gate_on(U[U["season"] == s], TIERS_REFCODED)
                for s in sorted(U["season"].unique())}
    pooled = gate_on(U, TIERS_REFCODED)
    out["M6_frozen_gate_pooled_vs_per_fold"] = {
        "columns_audited": TIERS_REFCODED,
        "pooled": pooled,
        "per_fold": per_fold,
        "pooled_passed_but_folds_blocked": sorted(
            [k for k, v in per_fold.items() if not v["passed"]]) if pooled["passed"] else [],
        "reading": ("the frozen gate itself, unmodified, passes these two columns on the pooled "
                    "2,982-row matrix and blocks them on zero_variance in the folds listed. That "
                    "is the ws3 shape reappearing on the authoritative control, and it is why a "
                    "pooled audit is not admissible evidence about the matrices that are fitted."),
    }

    # ---------------------------------------------------------------- scenarios through the guard
    prereg_ok = G.Preregistration(
        registered_at_utc="2026-08-04T00:00:00Z",
        registered_by="P27_FOLD_LOCAL_ESTIMABILITY_GUARD (prospective; no arm has been fitted)",
        rule_spec_sha256="",  # filled below
        results_visible_at_registration=False,
        record_path=("experiments/player_program/stage2b/P27_FOLD_LOCAL_ESTIMABILITY_GUARD/"
                     "ACTIVE_SET_RULE_PREREGISTRATION.json"))
    rule = G.ActiveSetRule(
        rule_id="S7_TIER_SUPPORT_v1",
        min_nonzero_clusters=10,
        min_std=1e-8,
        rationale=("a tier indicator is admitted to a training fold only when at least 10 distinct "
                   "GAME CLUSTERS in that fold carry the tier and the indicator has non-degenerate "
                   "variance. The cluster floor mirrors feature_gate's own refusal to assess rank "
                   "below 10 complete rows, lifted from rows to clusters because both team-rows of "
                   "a game share one projection."))
    prereg_ok = G.Preregistration(**{**prereg_ok.as_record(),
                                     "rule_spec_sha256": rule.spec_sha256})

    common = dict(offset_col="offset_projected", cluster_col="game_id", season_col="season")

    scen = {}

    # S-A: K0_MATCHED exactly as EVIDENCE_PACKET_V2 specifies it -- featureless, incumbent
    #      projection as offset, carrying the tier partition. One-hot over all three levels.
    scen["A_K0_MATCHED_tier_onehot"] = G.guard(
        U, candidate_features=[], nuisance_terms=TIERS_ONEHOT,
        null_features=[], null_nuisance=TIERS_ONEHOT,
        fold_policy="SEASON_BLOCK", arm_id="K0_MATCHED_tier_onehot", **common)

    # S-B: same control, reference-coded (drop team_window_same_season). Isolates the fold
    #      degeneracy from the dummy trap.
    scen["B_K0_MATCHED_tier_refcoded"] = G.guard(
        U, candidate_features=[], nuisance_terms=TIERS_REFCODED,
        null_features=[], null_nuisance=TIERS_REFCODED,
        fold_policy="SEASON_BLOCK", arm_id="K0_MATCHED_tier_refcoded", **common)

    # S-C: the S5 opponent-adjustment challenger against that control.
    scen["C_opponent_arm_vs_K0_refcoded"] = G.guard(
        U, candidate_features=["own_pace_est", "opp_pace_est"], nuisance_terms=TIERS_REFCODED,
        null_features=[], null_nuisance=TIERS_REFCODED,
        fold_policy="SEASON_BLOCK", arm_id="opponent_adjustment_challenger", **common)

    # S-D: scenario B with the conforming preregistered active-set rule.
    scen["D_K0_MATCHED_refcoded_with_valid_rule"] = G.guard(
        U, candidate_features=[], nuisance_terms=TIERS_REFCODED,
        null_features=[], null_nuisance=TIERS_REFCODED,
        rule=rule, prereg=prereg_ok,
        fold_policy="SEASON_BLOCK", arm_id="K0_MATCHED_tier_refcoded_active_set", **common)

    # S-E: the same rule registered AFTER results are visible -- must be refused.
    prereg_bad = G.Preregistration(**{**prereg_ok.as_record(),
                                      "results_visible_at_registration": True})
    scen["E_rule_registered_after_results_is_refused"] = G.guard(
        U, candidate_features=[], nuisance_terms=TIERS_REFCODED,
        null_features=[], null_nuisance=TIERS_REFCODED,
        rule=rule, prereg=prereg_bad,
        fold_policy="SEASON_BLOCK", arm_id="K0_MATCHED_post_hoc_rule", **common)

    # S-F: the alternative fold reading.
    scen["F_expanding_prior_seasons_fold_policy"] = G.guard(
        U, candidate_features=[], nuisance_terms=TIERS_REFCODED,
        null_features=[], null_nuisance=TIERS_REFCODED,
        fold_policy="EXPANDING_PRIOR_SEASONS", arm_id="K0_MATCHED_tier_refcoded_expanding",
        **common)

    # ---------------------------- M7 how much of "include the intercept" the frozen gate already has
    # Naively, "the rank audit must include the intercept" reads as a gap in feature_gate. It is
    # mostly NOT one, and the correction is worth stating: feature_gate CENTRES every column before
    # the SVD, and centring is algebraically equivalent to projecting out an intercept. An exact
    # AFFINE dependency among DECLARED features is therefore already caught. Measured below on the
    # 2022 fold, where only two of the three tiers occur and the two dummies sum to 1.
    f22 = U[U["season"] == 2022]
    out["M7_intercept_coverage_of_the_frozen_gate"] = {
        "case": "fold 2022, columns [tier_team_window_prior_season, tier_team_window_same_season]; "
                "only two tiers occur in 2022 so the two dummies sum to 1 on every row",
        "n_rows": int(len(f22)),
        "sum_of_the_two_dummies_is_one_on": int(
            ((f22["tier_team_window_prior_season"] + f22["tier_team_window_same_season"]) == 1.0
             ).sum()),
        "frozen_gate_design_rank_report": fg.design_rank_report(
            f22, ["tier_team_window_prior_season", "tier_team_window_same_season"]),
        "conclusion": ("the frozen gate reports numerical_rank 1 of 2. Centring already discharges "
                       "the intercept for exact affine dependence AMONG DECLARED FEATURES. The "
                       "residual gap in acceptance criterion 2 is therefore NOT the intercept: it "
                       "is the OFFSET and the NUISANCE terms, which never enter `names` and so "
                       "never enter the SVD at all. Scenario C is the measured instance."),
    }

    out["scenarios"] = scen

    # ---------------------------------------------------------------- headline extraction
    def headline(s):
        r = scen[s]
        return {
            "overall": r["overall"],
            "n_folds": len(r["folds"]),
            "fold_verdicts": {f["fold_id"]: f["verdict"] for f in r["folds"]},
            "final_design_verdict": r["final_design"]["verdict"],
            "final_design_blocking_kinds": sorted({b["kind"]
                                                   for b in r["final_design"]["blocking"]}),
            "terms_absent_or_zero_variance_in_at_least_one_fold":
                r["pooled_vs_fold_reconciliation"][
                    "terms_absent_or_zero_variance_in_at_least_one_fold"],
            "pooled_pass_would_be_misleading":
                r["pooled_vs_fold_reconciliation"]["pooled_pass_would_be_misleading"],
            "pooled_pass_masks_fold_degeneracy":
                r["pooled_vs_fold_reconciliation"]["pooled_pass_masks_fold_degeneracy"],
            "folds_marked_unevaluable": r["folds_marked_unevaluable"],
            "folds_estimable_only_under_active_set_rule":
                r["folds_estimable_only_under_active_set_rule"],
            "condition_numbers_augmented": {
                f["fold_id"]: round(f["rank_augmented_with_offset_and_nuisance"].get(
                    "condition_number", float("nan")), 4)
                for f in r["folds"] + [r["final_design"]]},
            "offset_absorption_relative_residual": {
                f["fold_id"]: f["offset_absorption"].get("relative_residual_norm")
                for f in r["folds"] + [r["final_design"]]},
            "param_counts": {k: {"cand": v["n_params_candidate"], "null": v["n_params_null"],
                                 "delta": v["delta_params"], "reconciled": v["reconciled"]}
                             for k, v in r["parameter_count_reconciliation"].items()},
            "frozen_gate_would_miss_rank_deficiency": {
                f["fold_id"]: f["rank_delta_vs_frozen_gate"]["frozen_gate_would_miss_this"]
                for f in r["folds"] + [r["final_design"]]},
        }

    out["headlines"] = {k: headline(k) for k in scen}

    # per-fold cluster support for the tier terms, the number the row count overstates
    supp = {}
    for f in scen["B_K0_MATCHED_tier_refcoded"]["folds"]:
        supp[f["fold_id"]] = {
            "n_rows": f["n_rows"], "n_clusters": f["n_clusters"],
            **{t: {"n_nonzero_rows": f["column_diagnostics"][t]["n_nonzero_rows"],
                   "n_clusters_with_support": f["column_diagnostics"][t][
                       "n_clusters_with_support"],
                   "std": f["column_diagnostics"][t]["std"],
                   "unique_levels": f["column_diagnostics"][t]["unique_levels"]}
               for t in TIERS_REFCODED}}
    out["M5_per_fold_cluster_support"] = supp

    (HERE / "MEASUREMENTS.json").write_text(json.dumps(out, indent=2, default=str),
                                            encoding="utf-8")
    (HERE / "ACTIVE_SET_RULE_PREREGISTRATION.json").write_text(
        json.dumps({"schema": "s7_active_set_preregistration/1",
                    "rule_spec": rule.spec, "rule_spec_sha256": rule.spec_sha256,
                    "preregistration": prereg_ok.as_record(),
                    "status": ("DECLARED BY THIS NODE AS A REFERENCE INSTANCE. It is NOT registered "
                               "for any arm. An arm that wishes to use it must register it in the "
                               "arm registry before its own execution; this file is the guard's "
                               "conformance example, not a program-level registration.")},
                   indent=2), encoding="utf-8")
    print(json.dumps(out["headlines"], indent=2, default=str)[:6000])
    print("\nwrote", HERE / "MEASUREMENTS.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
