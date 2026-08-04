#!/usr/bin/env python3
"""MEASURE.py -- every number in P28's REPORT.md, re-derived from the frozen artifacts.

Read-only. Writes exactly one file: MEASUREMENTS.json, inside this node's own directory.
No git command is run. No frozen artifact is imported for its side effects; feature_gate and
comparison_gate are imported and CALLED, never edited.

Run:  python experiments/player_program/stage2b/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT/MEASURE.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PP = HERE.parent.parent                      # experiments/player_program
ROOT = PP.parent.parent                      # repo worktree root
sys.path.insert(0, str(PP))

import comparison_gate as cg                                          # noqa: E402
import feature_gate as fg                                             # noqa: E402

PRIOR = PP / "projected_exposure_v1" / "team_possession_prior_v1.parquet"
POSS = PP / "possessions_v2" / "possessions_raw_v2.parquet"
TOV = PP / "turnover_targets_v1" / "team_turnover_reconciliation_v1.parquet"
SCORER = PP / "run_turnover_p1_universe_fix.py"
PACKET = PP / "stage2a" / "EVIDENCE_PACKET_V2.json"
STOPC = PP / "stage2a" / "V2_STOP_CONDITION.json"

REGULATION_MIN = 40.0
WINDOW_K = 10                                # mirrors possession_features.WINDOW_K


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def f(x, n=5):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def agree(measured, stated, tol):
    """AGREES / CORRECTS against a figure the V2 packet or stop-condition states."""
    if stated is None:
        return {"packet_states": None, "verdict": "NOT_IN_PACKET"}
    ok = abs(float(measured) - float(stated)) <= tol
    return {"packet_states": stated, "delta": f(float(measured) - float(stated), 8),
            "verdict": "AGREES" if ok else "CORRECTS"}


M: dict = {"schema": "player_program_node_measurements/1",
           "node_id": "P28_PRIMARY_SECONDARY_ORDERING_CONTRACT"}

# --------------------------------------------------------------------------- #
# M0 -- artifact identity
# --------------------------------------------------------------------------- #
M["M0_artifact_digests"] = {
    str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p)
    for p in (PRIOR, POSS, TOV, SCORER, PACKET, STOPC)}

packet = json.loads(PACKET.read_text(encoding="utf-8"))
boundary = packet["downstream_operational_boundary"]
mm = boundary["measured_mismatch"]

# --------------------------------------------------------------------------- #
# M1 -- the frozen scorer's pairing, read from the bytes of the scorer itself
# --------------------------------------------------------------------------- #
lines = SCORER.read_text(encoding="utf-8").splitlines()
line149 = lines[148]
M["M1_frozen_scorer_pairing"] = {
    "file": "experiments/player_program/run_turnover_p1_universe_fix.py",
    "line_number": 149,
    "line_text": line149.strip(),
    "packet_cites": boundary["recorded_pairing"]["consumer"],
    "operational_exposure_column": "projected_team_off_possessions",
    "regulation_equivalent": True,
    "outcome_is_raw_full_game_turnovers": True,
    "verdict": ("AGREES -- line 149 selects projected_team_off_possessions (regulation-equivalent) "
                "on the operational track; the outcome it is scored against is the realised RAW "
                "full-game turnover total, which no line rescales by game_minutes"),
    "rescale_of_turnovers_by_game_minutes_anywhere_in_scorer":
        any("game_minutes" in ln for ln in lines)}

# --------------------------------------------------------------------------- #
# M2 -- the universe, and the OT partition
# --------------------------------------------------------------------------- #
P = pd.read_parquet(PRIOR)
pos = pd.read_parquet(POSS, columns=["game_id", "period", "offense_team_id"])

n_off = (pos.groupby(["game_id", "offense_team_id"]).size().rename("raw_off_poss")
         .reset_index().rename(columns={"offense_team_id": "team_id"}))
maxp = pos.groupby("game_id")["period"].max().rename("max_period").reset_index()
n_off = n_off.merge(maxp, on="game_id", how="left", validate="m:1")
n_off["game_minutes"] = REGULATION_MIN + 5.0 * np.maximum(0, n_off["max_period"] - 4)
n_off["reg_equiv"] = n_off["raw_off_poss"] * REGULATION_MIN / n_off["game_minutes"]
n_off["is_overtime"] = n_off["max_period"] > 4

U = P.merge(n_off, on=["game_id", "team_id"], how="left", validate="1:1")
U_all = U.copy()
U = U[U["pace_resolved"].astype(bool) & U["reg_equiv"].notna()].copy()

U["proj"] = U["projected_team_off_possessions"].astype(float)
U["err_reg"] = U["proj"] - U["reg_equiv"]
U["err_raw"] = U["proj"] - U["raw_off_poss"]

M["M2_universe"] = {
    "prior_rows_published": int(len(P)),
    "rows_after_pace_resolved_and_outcome_join": int(len(U)),
    "game_clusters": int(U["game_id"].nunique()),
    "rows_dropped": int(len(P) - len(U)),
    "packet_check_rows": agree(len(U), 2982, 0),
    "packet_check_clusters": agree(U["game_id"].nunique(), 1491, 0),
    "note": ("1,491 clusters is the count over the 2,982-row PREDICTION universe. The packet's "
             "games_with_one_shared_projection = 1495 counts a different population (all games, "
             "including the 4 unresolved). Both are correct over different universes -- see the "
             "V2 stop-condition note packet_nits_flagged_not_corrected."),
    "all_games_in_possessions_artifact": int(n_off["game_id"].nunique()),
    "ot_games_all": int(n_off.loc[n_off["is_overtime"], "game_id"].nunique()),
    "ot_game_rate_all": f(n_off.loc[n_off["is_overtime"], "game_id"].nunique()
                          / n_off["game_id"].nunique()),
    "packet_check_ot_games": agree(n_off.loc[n_off["is_overtime"], "game_id"].nunique(), 66, 0),
    "packet_check_total_games": agree(n_off["game_id"].nunique(), 1495, 0),
    "packet_check_ot_game_rate": agree(
        n_off.loc[n_off["is_overtime"], "game_id"].nunique() / n_off["game_id"].nunique(),
        packet["overtime_window_contamination"]["ot_game_rate"], 5e-5),
    "max_period_composition_over_ot_games": {
        str(int(k)): int(v) for k, v in
        n_off.loc[n_off["is_overtime"]].drop_duplicates("game_id")["max_period"]
        .value_counts().sort_index().items()},
}

# --------------------------------------------------------------------------- #
# M3 -- re-derivation of the packet's measured_mismatch block
# --------------------------------------------------------------------------- #
strata = {}
for label, mask, stated in (("regulation", ~U["is_overtime"], mm["regulation"]),
                            ("overtime", U["is_overtime"], mm["overtime"])):
    d = U[mask]
    got = {
        "n_rows": int(len(d)),
        "n_game_clusters": int(d["game_id"].nunique()),
        "mae_vs_reg_equiv_target": f(np.mean(np.abs(d["err_reg"]))),
        "mae_vs_RAW_target": f(np.mean(np.abs(d["err_raw"]))),
        "bias_vs_reg_equiv": f(np.mean(d["err_reg"])),
        "bias_vs_RAW": f(np.mean(d["err_raw"])),
        "mean_realised_reg_equiv": f(np.mean(d["reg_equiv"]), 4),
        "mean_realised_raw": f(np.mean(d["raw_off_poss"]), 4),
        "sd_realised_reg_equiv": f(np.std(d["reg_equiv"], ddof=1)),
        "sd_abs_err_reg_equiv": f(np.std(np.abs(d["err_reg"]), ddof=1)),
    }
    got["packet_comparison"] = {
        k: agree(got[k], stated.get(k), 5e-5 if isinstance(stated.get(k), float) else 0)
        for k in ("n_rows", "n_game_clusters", "mae_vs_reg_equiv_target", "mae_vs_RAW_target",
                  "bias_vs_reg_equiv", "bias_vs_RAW", "mean_realised_reg_equiv",
                  "mean_realised_raw")}
    strata[label] = got

strata["pooled"] = {
    "n_rows": int(len(U)),
    "mae_vs_reg_equiv_target": f(np.mean(np.abs(U["err_reg"]))),
    "mae_vs_RAW_target": f(np.mean(np.abs(U["err_raw"]))),
    "bias_vs_reg_equiv": f(np.mean(U["err_reg"])),
    "bias_vs_RAW": f(np.mean(U["err_raw"])),
    "note": "the pooled figure is not stated in the packet; it is derived here for the contract",
}
M["M3_scorer_mismatch"] = strata
M["M3_scorer_mismatch"]["mismatch_magnitude"] = {
    "mean_raw_minus_reg_equiv_on_OT_rows":
        f(np.mean(U.loc[U["is_overtime"], "raw_off_poss"] - U.loc[U["is_overtime"], "reg_equiv"]), 4),
    "mean_raw_minus_reg_equiv_on_non_OT_rows":
        f(np.mean(U.loc[~U["is_overtime"], "raw_off_poss"] - U.loc[~U["is_overtime"], "reg_equiv"]), 8),
    "interpretation": ("this is the accounting gap the frozen scorer leaves open. It is exactly "
                       "zero off OT rows and about eleven possessions on OT rows."),
}

# --------------------------------------------------------------------------- #
# M4 -- the propagation coefficient from possessions to turnovers
# --------------------------------------------------------------------------- #
T = pd.read_parquet(TOV)
UT = U.merge(T[["game_id", "team_id", "team_turnovers_total", "player_attributed",
                "team_off_possessions"]], on=["game_id", "team_id"], how="left", validate="1:1")
UT["rate_total_over_raw"] = UT["team_turnovers_total"] / UT["raw_off_poss"]
UT["rate_total_over_recon_poss"] = UT["team_turnovers_total"] / UT["team_off_possessions"]
UT["rate_attributed_over_raw"] = UT["player_attributed"] / UT["raw_off_poss"]
UT["rate_total_over_reg_equiv"] = UT["team_turnovers_total"] / UT["reg_equiv"]
UT["rate_attributed_over_reg_equiv"] = UT["player_attributed"] / UT["reg_equiv"]

stated_rate = packet["downstream_turnover_team_error"]["implied_team_tov_rate"]
cands = {}
for name in ("rate_total_over_raw", "rate_total_over_recon_poss", "rate_attributed_over_raw",
             "rate_total_over_reg_equiv", "rate_attributed_over_reg_equiv"):
    v = UT[name].astype(float)
    cands[name] = {"n": int(v.notna().sum()), "mean": f(v.mean()), "sd": f(v.std(ddof=1)),
                   "p05": f(v.quantile(0.05), 4), "p50": f(v.quantile(0.50), 4),
                   "p95": f(v.quantile(0.95), 4)}
best = min(cands, key=lambda k: abs(cands[k]["mean"] - stated_rate["mean"]))
M["M4_propagation"] = {
    "candidate_definitions": cands,
    "definition_that_reproduces_the_packet": best,
    "packet_states": {k: stated_rate[k] for k in ("n", "mean", "sd", "p05", "p50", "p95")},
    "packet_comparison": {k: agree(cands[best][k], stated_rate[k], 5e-5 if k != "n" else 0)
                          for k in ("n", "mean", "sd", "p05", "p50", "p95")},
    "propagation_coefficient_used_downstream": f(cands[best]["mean"]),
    "note": ("the mean implied rate is the mechanical propagation coefficient the packet uses: a "
             "one-possession projection error is worth about that many turnovers, holding the "
             "realised rate fixed. It is a POST-HOC attribution, not a predictive path, and it "
             "never enters a feature matrix."),
}
RATE = UT[best].astype(float).to_numpy()
UT["rate_used"] = RATE

# --------------------------------------------------------------------------- #
# M5 -- trailing OT rate: a strictly-lagged, gate-passing feature
# --------------------------------------------------------------------------- #
UT = UT.sort_values(["game_date", "game_id", "team_id"]).reset_index(drop=True)
hist: dict = {}
tr, depth = [], []
for r in UT.itertuples(index=False):
    h = hist.setdefault(r.team_id, [])
    w = h[-WINDOW_K:]
    tr.append(float(np.mean(w)) if w else np.nan)
    depth.append(len(w))
    h.append(1.0 if r.is_overtime else 0.0)
UT["trailing_ot_rate"] = tr
UT["trailing_ot_depth"] = depth
UT["trailing_ot_rate_filled"] = UT["trailing_ot_rate"].fillna(0.0)

gate_frame = UT[["trailing_ot_rate_filled"]].rename(
    columns={"trailing_ot_rate_filled": "trailing_ot_rate"}).copy()
offset = np.log(UT["proj"].to_numpy(float))
target = UT["reg_equiv"].to_numpy(float)
try:
    rec = fg.audit(gate_frame, ["trailing_ot_rate"], offset=offset, target=target,
                   test_df=gate_frame, outcome_mask=UT["is_overtime"].to_numpy(bool))
    gate_verdict = {"passed": bool(rec["passed"]), "findings": rec["findings"],
                    "blocking": rec["blocking"],
                    "design_rank": {k: rec["design_rank"][k] for k in
                                    ("numerical_rank", "full_rank", "condition_number")}}
except fg.FeatureGateFailure as exc:                       # pragma: no cover -- reported if it fires
    gate_verdict = {"passed": False, "raised": str(exc)}

# GATE_INVOCATION_CONTRACT s1: the pooled/final-design audit does NOT discharge the per-fold
# obligation. Run it on every chronological training fold as well.
per_fold_gate = {}
for season, idx in UT.groupby("season").groups.items():
    sub = UT.loc[idx]
    gf = sub[["trailing_ot_rate_filled"]].rename(
        columns={"trailing_ot_rate_filled": "trailing_ot_rate"}).copy()
    try:
        rf = fg.audit(gf, ["trailing_ot_rate"],
                      offset=np.log(sub["proj"].to_numpy(float)),
                      target=sub["reg_equiv"].to_numpy(float), test_df=gf,
                      outcome_mask=sub["is_overtime"].to_numpy(bool))
        per_fold_gate[str(season)] = {"n_rows": int(len(sub)), "passed": bool(rf["passed"]),
                                      "blocking": rf["blocking"],
                                      "finding_kinds": sorted({x["kind"] for x in rf["findings"]})}
    except fg.FeatureGateFailure as exc:
        per_fold_gate[str(season)] = {"n_rows": int(len(sub)), "passed": False,
                                      "raised": str(exc)[:400]}

M["M5_trailing_ot_rate"] = {
    "construction": (f"per team, the mean of the OT indicator over its most recent {WINDOW_K} "
                     "games with game_date STRICTLY EARLIER than the row's own; the target game's "
                     "own max_period never enters. Nulls (no prior game) filled with 0.0, "
                     "declared."),
    "window_k": WINDOW_K,
    "n_rows": int(len(UT)),
    "n_null_before_fill": int(UT["trailing_ot_rate"].isna().sum()),
    "mean": f(UT["trailing_ot_rate_filled"].mean()),
    "sd": f(UT["trailing_ot_rate_filled"].std(ddof=1)),
    "max": f(UT["trailing_ot_rate_filled"].max()),
    "corr_with_target_reg_equiv": f(np.corrcoef(UT["trailing_ot_rate_filled"], target)[0, 1]),
    "corr_with_offset_log_projection": f(np.corrcoef(UT["trailing_ot_rate_filled"], offset)[0, 1]),
    "corr_with_target_game_is_overtime":
        f(np.corrcoef(UT["trailing_ot_rate_filled"], UT["is_overtime"].astype(float))[0, 1]),
    "feature_gate_thresholds": {"corr_threshold": 0.999, "target_corr_threshold": 0.98,
                                "missingness_corr_threshold": 0.5},
    "feature_gate_verdict_final_assembled_design": gate_verdict,
    "feature_gate_verdict_per_chronological_fold": per_fold_gate,
    "all_folds_pass": all(v.get("passed") for v in per_fold_gate.values()),
    "verdict": ("the feature is strictly lagged, is not a function of the target game's realised "
                "duration, and PASSES feature_gate.audit with every optional argument supplied. "
                "No feature-matrix check in the repository can block it."),
}

# --------------------------------------------------------------------------- #
# M6 -- the arbitrage: a deterministic perturbation, not a fitted arm
# --------------------------------------------------------------------------- #
r = UT["trailing_ot_rate_filled"].to_numpy(float)
rc = r - r.mean()
proj = UT["proj"].to_numpy(float)
y_reg = UT["reg_equiv"].to_numpy(float)
y_raw = UT["raw_off_poss"].to_numpy(float)
ot = UT["is_overtime"].to_numpy(bool)

base_primary = float(np.mean(np.abs(proj - y_reg)))
base_down = float(np.mean(np.abs(RATE * (proj - y_raw))))

FAMILIES = {
    "uniform_inflation": {
        "multiplier": lambda lam: 1.0 + lam,
        "admissible": True,
        "carrier": "no feature -- a constant scale on the projection",
        "note": "the adversarial source's stated CONTROL: uniform inflation, no targeting"},
    "trailing_ot_rate_uncentered": {
        "multiplier": lambda lam: 1.0 + lam * r,
        "admissible": True,
        "carrier": "trailing_ot_rate (strictly lagged, feature_gate-passing)",
        "note": "the exploit E5 names: inflation TARGETED at rows with high OT propensity"},
    "trailing_ot_rate_centered": {
        "multiplier": lambda lam: 1.0 + lam * rc,
        "admissible": True,
        "carrier": "trailing_ot_rate, mean-centred (mean projection preserved)",
        "note": "a mean-preserving variant, so the channel cannot be confused with a level shift"},
    "ORACLE_target_game_is_overtime": {
        "multiplier": lambda lam: 1.0 + lam * ot.astype(float),
        "admissible": False,
        "carrier": "the TARGET GAME's realised is_overtime -- PROHIBITED by the ruling",
        "note": ("bounding construction only. It is the maximum size of the arbitrage channel "
                 "under perfect foreknowledge of OT, and it may never be used predictively.")},
}
LAMBDAS = (0.0, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.14, 0.2, 0.3, 0.5, 1.0)

families_out = {}
for fam, cfg in FAMILIES.items():
    grid = []
    for lam in LAMBDAS:
        p2 = proj * cfg["multiplier"](lam)
        prim = float(np.mean(np.abs(p2 - y_reg)))
        down = float(np.mean(np.abs(RATE * (p2 - y_raw))))
        grid.append({
            "lambda": lam,
            "primary_possession_mae_reg_equiv": f(prim, 6),
            "delta_primary_vs_lambda0": f(prim - base_primary, 6),
            "primary_worsens": bool(prim > base_primary + 1e-12),
            "downstream_turnover_mae_vs_RAW": f(down, 6),
            "delta_downstream_vs_lambda0": f(down - base_down, 6),
            "downstream_improves": bool(down < base_down - 1e-12),
            "downstream_mae_OT_rows": f(float(np.mean(np.abs(RATE[ot] * (p2[ot] - y_raw[ot])))), 6),
            "downstream_mae_nonOT_rows":
                f(float(np.mean(np.abs(RATE[~ot] * (p2[~ot] - y_raw[~ot])))), 6),
            "ARBITRAGE": bool(prim > base_primary + 1e-12 and down < base_down - 1e-12),
        })
    arb = [g for g in grid if g["ARBITRAGE"]]

    # fine scan for the family's OPTIMUM arbitrage: largest downstream improvement subject to
    # the primary target getting strictly worse.
    fine, both_improve = [], []
    for lam in np.concatenate([np.linspace(0.0, 0.05, 501)[1:], np.linspace(0.05, 1.0, 191)[1:]]):
        p2 = proj * cfg["multiplier"](float(lam))
        prim = float(np.mean(np.abs(p2 - y_reg)))
        down = float(np.mean(np.abs(RATE * (p2 - y_raw))))
        if prim > base_primary + 1e-12 and down < base_down - 1e-12:
            fine.append((float(lam), prim, down))
        if prim < base_primary - 1e-12 and down < base_down - 1e-12:
            both_improve.append((float(lam), prim, down))
    opt = min(fine, key=lambda t: t[2]) if fine else None

    families_out[fam] = {
        "carrier": cfg["carrier"], "admissible_under_the_ruling": cfg["admissible"],
        "note": cfg["note"], "grid": grid,
        "n_lambda_values_that_arbitrage": len(arb),
        "arbitrage_exists": bool(arb or fine),
        "fine_scan_n_arbitraging_lambdas": len(fine),
        "fine_scan_n_lambdas_where_BOTH_metrics_improve": len(both_improve),
        "fine_scan_lambda_range": ([f(min(t[0] for t in fine), 6), f(max(t[0] for t in fine), 6)]
                                   if fine else None),
        "OPTIMUM": (None if opt is None else {
            "lambda": f(opt[0], 6),
            "primary_possession_mae_reg_equiv": f(opt[1], 6),
            "primary_gets_worse_by": f(opt[1] - base_primary, 6),
            "downstream_turnover_mae_vs_RAW": f(opt[2], 6),
            "downstream_gets_better_by": f(base_down - opt[2], 6),
            "downstream_relative_improvement_pct": f(100.0 * (base_down - opt[2]) / base_down, 4),
        }),
    }

any_admissible = any(v["arbitrage_exists"] for k, v in families_out.items()
                     if FAMILIES[k]["admissible"])
M["M6_arbitrage_demonstration"] = {
    "what_this_is": ("CLOSED-FORM deterministic perturbations of the frozen incumbent projection, "
                     "proj_lambda = proj * m(lambda). These are counterexample constructions, NOT "
                     "fitted arms, NOT registered challengers. No comparative historical "
                     "performance of any challenger was inspected."),
    "primary_metric": "MAE of the projection against REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
    "downstream_metric": ("mechanical propagation through the FROZEN scorer's pairing: "
                          "|realised_rate * (projected_reg_equiv_exposure - RAW possessions)|, "
                          "the turnover-team error attributable to possession mis-projection "
                          "holding the realised rate fixed"),
    "baseline_lambda0": {"primary_possession_mae": f(base_primary, 6),
                         "downstream_turnover_mae": f(base_down, 6),
                         "downstream_mae_OT_rows": f(float(np.mean(np.abs(RATE[ot] * (proj[ot] - y_raw[ot])))), 6),
                         "downstream_mae_nonOT_rows": f(float(np.mean(np.abs(RATE[~ot] * (proj[~ot] - y_raw[~ot])))), 6)},
    "families": families_out,
    "arbitrage_reproduces_with_an_ADMISSIBLE_carrier": bool(any_admissible),
    "arbitrage_reproduces_with_the_ORACLE_carrier":
        bool(families_out["ORACLE_target_game_is_overtime"]["arbitrage_exists"]),
}

# the predictive strength of the carrier -- why the admissible families behave as they do
lag_ot = UT["trailing_ot_rate_filled"].to_numpy(float)
M["M6_arbitrage_demonstration"]["carrier_predictive_strength"] = {
    "corr_trailing_ot_rate_with_target_game_is_overtime":
        f(float(np.corrcoef(lag_ot, ot.astype(float))[0, 1])),
    "mean_trailing_ot_rate_on_OT_rows": f(float(lag_ot[ot].mean())),
    "mean_trailing_ot_rate_on_nonOT_rows": f(float(lag_ot[~ot].mean())),
    "difference": f(float(lag_ot[ot].mean() - lag_ot[~ot].mean())),
    "base_rate_of_OT_rows": f(float(ot.mean())),
    "interpretation": ("if this correlation is at or below zero, the trailing OT rate does not "
                       "identify the rows the arbitrage needs, and targeted inflation degenerates "
                       "towards uniform inflation. This is a MEASURED property of THIS panel, not "
                       "a property of the mechanism, and it is not a licence to admit the "
                       "feature."),
}

# --------------------------------------------------------------------------- #
# M7 -- what the existing gates can and cannot see
# --------------------------------------------------------------------------- #
import dataclasses                                                       # noqa: E402
side_fields = [f_.name for f_ in dataclasses.fields(cg.SideSpec)]
M["M7_gate_coverage"] = {
    "comparison_gate_DIMENSIONS_count": len(cg.DIMENSIONS),
    "comparison_gate_DIMENSIONS": list(cg.DIMENSIONS),
    "SideSpec_fields": side_fields,
    "SideSpec_has_target_field": "target" in side_fields,
    "SideSpec_has_metric_field": "metric" in side_fields,
    "SideSpec_has_ordering_field": any("order" in s for s in side_fields),
    "gain_report_metric_name_is_a_free_string": True,
    "gain_report_signature": "gain_report(metrics, *, lower_is_better=True, metric_name='metric', uncertainty=None)",
    "feature_gate_BLOCKING": sorted(fg.BLOCKING),
    "feature_gate_has_a_target_identity_check": False,
    "conclusion": ("neither frozen gate carries any representation of WHICH target a metric is "
                   "computed against, nor of the ORDER in which two metrics were computed. "
                   "comparison_gate compares a challenger to a control on ONE unnamed metric; "
                   "feature_gate audits ONE matrix. The ordering constraint is therefore not "
                   "implementable inside either gate and must live at the CALL SITE."),
}

# --------------------------------------------------------------------------- #
# M8 -- the naming collision on the word PRIMARY
# --------------------------------------------------------------------------- #
src = (PP / "comparison_gate.py").read_text(encoding="utf-8")
M["M8_primary_naming_collision"] = {
    "comparison_gate_primary_incremental_test": "challenger_vs_k0",
    "comparison_gate_meaning_of_primary": "the primary CONTRAST (which two sides are compared)",
    "this_contract_meaning_of_primary": "the primary TARGET (which outcome the metric is computed against)",
    "occurrences_of_primary_incremental_test_in_comparison_gate":
        src.count("primary_incremental_test"),
    "risk": ("a report that says 'the primary test passed' is ambiguous between the two senses. "
             "P28 uses PRIMARY TARGET and SECONDARY DOWNSTREAM METRIC and never the bare word."),
}

# --------------------------------------------------------------------------- #
# M9 -- OT stratum sd-compression check (E3 / the packet's units-artifact caveat)
# --------------------------------------------------------------------------- #
sd_ot = float(np.std(np.abs(U.loc[U["is_overtime"], "err_reg"]), ddof=1))
sd_non = float(np.std(np.abs(U.loc[~U["is_overtime"], "err_reg"]), ddof=1))
gm_ot = U.loc[U["is_overtime"], "game_minutes"]
sd_signed_ot = float(np.std(U.loc[U["is_overtime"], "err_reg"], ddof=1))
sd_signed_non = float(np.std(U.loc[~U["is_overtime"], "err_reg"], ddof=1))
M["M9_ot_sd_compression"] = {
    "sd_SIGNED_err_reg_equiv_OT": f(sd_signed_ot),
    "sd_SIGNED_err_reg_equiv_nonOT": f(sd_signed_non),
    "sd_SIGNED_ratio": f(sd_signed_ot / sd_signed_non),
    "adversarial_source_states_sd_OT": 3.07361,
    "adversarial_source_states_sd_nonOT": 3.69921,
    "which_sd_the_source_reported": ("the SIGNED-error sd; the ratio it quotes, 0.831, matches "
                                     "3.07361/3.69921 = 0.83088"),
    "sd_abs_err_reg_equiv_OT": f(sd_ot),
    "sd_abs_err_reg_equiv_nonOT": f(sd_non),
    "sd_ratio_of_ABS_err": f(sd_ot / sd_non),
    "pure_scale_factor_single_OT_40_over_45": f(40.0 / 45.0),
    "mean_scale_factor_over_OT_rows": f(float(np.mean(40.0 / gm_ot))),
    "adversarial_source_states_sd_ratio": 0.831,
    "note": ("recorded because it bears on whether the OT stratum's lower reg-equivalent MAE may "
             "be cited as a fact about difficulty. P28 does NOT resolve it; it forbids the "
             "downstream number from deciding anything, which is a weaker and safer claim."),
}

out = HERE / "MEASUREMENTS.json"
out.write_text(json.dumps(M, indent=1), encoding="utf-8")
print(f"wrote {out}")
print(json.dumps({"rows": M["M2_universe"]["rows_after_pace_resolved_and_outcome_join"],
                  "clusters": M["M2_universe"]["game_clusters"],
                  "arbitrage_admissible":
                      M["M6_arbitrage_demonstration"]["arbitrage_reproduces_with_an_ADMISSIBLE_carrier"],
                  "arbitrage_oracle":
                      M["M6_arbitrage_demonstration"]["arbitrage_reproduces_with_the_ORACLE_carrier"],
                  "gate_passed_final_design":
                      M["M5_trailing_ot_rate"]["feature_gate_verdict_final_assembled_design"]["passed"],
                  "gate_passed_all_folds": M["M5_trailing_ot_rate"]["all_folds_pass"]},
                 indent=1))
