"""Known-answer fixture tests for SCORE_BASELINES (D043 / D036).

Every numeric routine the producer relies on is exercised against a
hand-computed answer; the strict-lag property is verified structurally on
synthetic fixtures (a target game's prediction never reads that game or
any later game). Run:

    python experiments/market_program/SCORE_BASELINES/TESTS.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_score_baselines as sb  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 1. lagged_ewma -- hand-computed recursive EWMA, alpha = 2/11
# ---------------------------------------------------------------------------
a = sb.EFF_ALPHA
check("ewma_alpha_is_2_over_11", abs(a - 2.0 / 11.0) < 1e-15)
# e1=1.0; e2=a*2+(1-a)*1; e3=a*0.5+(1-a)*e2  (hand-derivable chain)
e2 = a * 2.0 + (1 - a) * 1.0
e3 = a * 0.5 + (1 - a) * e2
check("ewma_known_answer_3_values",
      abs(sb.lagged_ewma([1.0, 2.0, 0.5]) - e3) < 1e-12,
      f"got {sb.lagged_ewma([1.0, 2.0, 0.5])}, want {e3}")
check("ewma_empty_is_none", sb.lagged_ewma([]) is None)
check("ewma_single_value_identity", sb.lagged_ewma([7.25]) == 7.25)

# ---------------------------------------------------------------------------
# 2. clustered_mean_ci -- hand-computed 2-cluster fixture
#    x = [1, 3, 5, 7]; clusters = [d1, d1, d2, d2]; mean = 4
#    T_d1 = (1-4)+(3-4) = -4 ; T_d2 = (5-4)+(7-4) = +4
#    var = (2/1) * (16+16) / 16 = 4 ; half = 1.96 * 2
# ---------------------------------------------------------------------------
m, hw, n, g = sb.clustered_mean_ci([1, 3, 5, 7], ["d1", "d1", "d2", "d2"])
check("clustered_ci_mean", m == 4.0)
check("clustered_ci_halfwidth", abs(hw - sb.Z95 * 2.0) < 1e-12, f"got {hw}")
check("clustered_ci_counts", (n, g) == (4, 2))
m1, hw1, n1, g1 = sb.clustered_mean_ci([2.0, 2.0], ["d1", "d1"])
check("clustered_ci_single_cluster_no_ci", hw1 is None and m1 == 2.0)

# ---------------------------------------------------------------------------
# 3. metric_block -- errors [3, -1, 2, -4] on two dates
#    MAE = (3+1+2+4)/4 = 2.5 ; bias = 0 ; MSE = (9+1+4+16)/4 = 7.5
# ---------------------------------------------------------------------------
blk = sb.metric_block([3, -1, 2, -4], ["d1", "d1", "d2", "d2"])
check("metric_block_mae", abs(blk["mae"] - 2.5) < 1e-12)
check("metric_block_bias", abs(blk["bias"] - 0.0) < 1e-12)
check("metric_block_rmse", abs(blk["rmse"] - math.sqrt(7.5)) < 1e-12)
check("metric_block_n", blk["n"] == 4 and blk["n_date_clusters"] == 2)

# ---------------------------------------------------------------------------
# 4. prob_block -- Brier known answer
#    p = [0.8, 0.3], y = [1, 0] -> brier = (0.04 + 0.09)/2 = 0.065
#    log loss = (-ln 0.8 - ln 0.7)/2
# ---------------------------------------------------------------------------
pb = sb.prob_block([0.8, 0.3], [1.0, 0.0], ["d1", "d2"])
check("prob_block_brier", abs(pb["brier"] - 0.065) < 1e-12)
check("prob_block_logloss",
      abs(pb["log_loss"] - (-(math.log(0.8) + math.log(0.7)) / 2)) < 1e-12)
bins = {r["bin"]: r for r in pb["calibration_10bin"]}
check("prob_block_calibration_bins",
      bins["[0.8,0.9)"]["n"] == 1 and bins["[0.3,0.4)"]["n"] == 1)

# ---------------------------------------------------------------------------
# 5. fit_logistic_1d -- saturated two-point known answer
#    margins -1 (1 win / 4) and +1 (3 wins / 4):
#    exact MLE: intercept = 0, slope = ln(3)/1... precisely:
#    b0 - b1 = logit(0.25) = -ln 3 ; b0 + b1 = logit(0.75) = +ln 3
# ---------------------------------------------------------------------------
margins = [-1.0] * 4 + [1.0] * 4
ys = [1, 0, 0, 0] + [1, 1, 1, 0]
beta = sb.fit_logistic_1d(margins, ys)
check("logistic_intercept_zero", abs(beta[0]) < 1e-6, f"got {beta[0]}")
check("logistic_slope_ln3", abs(beta[1] - math.log(3.0)) < 1e-6, f"got {beta[1]}")
p = sb.apply_logistic(np.array([0.0, math.log(3.0)]), [1.0])
check("apply_logistic_known", abs(p[0] - 0.75) < 1e-12)

# ---------------------------------------------------------------------------
# 6. build_eff_ewmas -- strict lag + min-history gate on a synthetic team
# ---------------------------------------------------------------------------
tg_fix = pd.DataFrame({
    "game_id": ["g1", "g2", "g3", "g4", "g5"],
    "team_id": [10] * 5,
    "game_date": pd.to_datetime(
        ["2024-01-01", "2024-01-03", "2024-01-05", "2024-01-07", "2024-01-09"]),
    "ppp_off": [1.0, 2.0, 0.5, 1.5, 1.2],
    "ppp_def": [0.9, 1.1, 1.0, 0.8, 1.0],
})
eff = sb.build_eff_ewmas(tg_fix)
check("eff_first_three_games_cold_start",
      all(eff[(f"g{i}", 10)][0] is None for i in (1, 2, 3)))
off4, def4, nprior4 = eff[("g4", 10)]
check("eff_game4_uses_exactly_3_priors", nprior4 == 3)
check("eff_game4_off_known_answer", abs(off4 - e3) < 1e-12,
      f"got {off4}, want {e3}")  # same chain as fixture 1: [1.0, 2.0, 0.5]
d2 = a * 1.1 + (1 - a) * 0.9
d3 = a * 1.0 + (1 - a) * d2
check("eff_game4_def_known_answer", abs(def4 - d3) < 1e-12)
# STRICT LAG: game 4's value must not move if game 4/5 outcomes change
tg_mut = tg_fix.copy()
tg_mut.loc[3:, "ppp_off"] = 99.0
eff_mut = sb.build_eff_ewmas(tg_mut)
check("eff_strict_lag_target_game_never_read",
      abs(eff_mut[("g4", 10)][0] - off4) < 1e-15)

# ---------------------------------------------------------------------------
# 7. build_composite -- pace x blended efficiency arithmetic
#    pace 80; home off 1.05 / away def 0.95 -> home = 80 * 1.00 = 80
#    away off 1.00 / home def 0.90 -> away = 80 * 0.95 = 76
# ---------------------------------------------------------------------------
games_fix = pd.DataFrame({
    "game_id": ["gA", "gB", "gC"],
    "home_team_id": [1, 1, 1], "away_team_id": [2, 2, 2],
})
pace_fix = pd.DataFrame({
    "game_id": ["gA", "gB", "gC"],
    "projected_team_off_possessions": [80.0, np.nan, 80.0],
    "pace_resolved": [True, False, True],
})
eff_fix = {
    ("gA", 1): (1.05, 0.90, 5), ("gA", 2): (1.00, 0.95, 5),
    ("gB", 1): (1.05, 0.90, 5), ("gB", 2): (1.00, 0.95, 5),
    ("gC", 1): (None, None, 1), ("gC", 2): (1.00, 0.95, 5),
}
comp, excl = sb.build_composite(games_fix, pace_fix, eff_fix)
row = comp.iloc[0]
check("composite_home_score", abs(row["pred_home"] - 80.0) < 1e-12)
check("composite_away_score", abs(row["pred_away"] - 76.0) < 1e-12)
check("composite_total_margin",
      abs(row["pred_total"] - 156.0) < 1e-12 and abs(row["pred_margin"] - 4.0) < 1e-12)
check("composite_pace_exclusion_counted",
      excl["PACE_UNRESOLVED_NO_PRIOR_GAMES"] == 1)
check("composite_eff_exclusion_counted",
      excl["EFF_HISTORY_LT_3_PRIOR_GAMES"] == 1)
check("composite_emits_only_covered_games", len(comp) == 1)

# ---------------------------------------------------------------------------
# 8. build_league_average -- strictly-lagged expanding means
#    date1: totals 150 & 160, margins +5 & -3, home wins 1 & 0
#    date2 prediction: total 155, margin +1, p_home 0.5 ; date1 excluded
# ---------------------------------------------------------------------------
lg_games = pd.DataFrame({
    "game_id": ["g1", "g2", "g3"],
    "game_date": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-02"]),
    "actual_total": [150.0, 160.0, 170.0],
    "actual_margin": [5.0, -3.0, 2.0],
    "y_home_win": [1.0, 0.0, 1.0],
})
lg, lg_excl = sb.build_league_average(lg_games)
check("league_avg_cold_start_counted", lg_excl["NO_PRIOR_LEAGUE_GAMES"] == 2)
check("league_avg_known_answer",
      len(lg) == 1 and abs(lg.iloc[0]["pred_total"] - 155.0) < 1e-12
      and abs(lg.iloc[0]["pred_margin"] - 1.0) < 1e-12
      and abs(lg.iloc[0]["p_home"] - 0.5) < 1e-12)

# ---------------------------------------------------------------------------
# 9. build_team_avg -- season-to-date means, injected master frame
#    Team 1 prior game: scored 90, allowed 80. Team 2 prior: scored 70, allowed 85.
#    Target (1 home vs 2): home = (90 + 85)/2 = 87.5 ; away = (70 + 80)/2 = 75
# ---------------------------------------------------------------------------
mt_fix = pd.DataFrame({
    "game_id": ["p1", "p1b", "t1", "t1b"],
    "team_id": [1, 2, 1, 2],
    "season": [2024] * 4,
    "game_date": pd.to_datetime(["2024-06-01", "2024-06-01", "2024-06-03", "2024-06-03"]),
    "pts": [90.0, 70.0, 88.0, 77.0],
    "opp_pts": [80.0, 85.0, 77.0, 88.0],
})
ta_games = pd.DataFrame({
    "game_id": ["t1", "p1"],
    "home_team_id": [1, 1], "away_team_id": [2, 2],
    "season": [2024, 2024],
    "game_date": pd.to_datetime(["2024-06-03", "2024-06-01"]),
})
ta, ta_excl = sb.build_team_avg(ta_games, mt=mt_fix)
check("team_avg_cold_start_counted",
      ta_excl["NO_SAME_SEASON_PRIOR_GAME_EITHER_TEAM"] == 1)
trow = ta[ta["game_id"] == "t1"].iloc[0]
check("team_avg_home_known_answer", abs(trow["pred_home"] - 87.5) < 1e-12)
check("team_avg_away_known_answer", abs(trow["pred_away"] - 75.0) < 1e-12)

# ---------------------------------------------------------------------------
# 10. walkforward_winprob -- never same-season, never future
# ---------------------------------------------------------------------------
wf_games = pd.DataFrame({
    "game_id": [f"g{i}" for i in range(8)],
    "season": [2021] * 4 + [2022] * 4,
    "y_home_win": [1, 0, 1, 0, 1, 1, 0, 1],
})
wf_df = pd.DataFrame({
    "game_id": [f"g{i}" for i in range(8)],
    "pred_margin": [4, -4, 6, -6, 3, 5, -2, 1],
})
wf_out, wf_fits = sb.walkforward_winprob(wf_df, wf_games)
merged = wf_out.merge(wf_games, on="game_id")
check("walkforward_first_season_has_no_prob",
      merged.loc[merged["season"] == 2021, "p_home"].isna().all())
check("walkforward_later_season_has_prob",
      merged.loc[merged["season"] == 2022, "p_home"].notna().all())
check("walkforward_fit_trained_on_prior_season_only",
      wf_fits[2022]["train_seasons"] == [2021] and wf_fits[2021] is None)

# ---------------------------------------------------------------------------
# 11. Output artifact invariants (runs only if the producer has run)
# ---------------------------------------------------------------------------
out_path = HERE / "score_baselines.json"
if out_path.exists():
    with open(out_path, encoding="utf-8") as f:
        out = json.load(f)
    FROZEN_T1_CAVEAT_SHA = (
        "93a816cc9357af8d0a09da60695eee60e6921b1cbf1fbcb2b7c8b125216e21f7")
    check("output_caveat_sha_matches_bookie_frozen_constant",
          out["market_comparison"]["caveat_sha256"] == FROZEN_T1_CAVEAT_SHA)
    check("output_evidence_class",
          out["evidence_class"] == "COMPOSITE_BASELINE"
          and "NAIVE_BASELINE" in out["evidence_class_semantics"])
    check("output_matched_universe_declared",
          "MATCHED universe only" in out["market_comparison"]["universe"])
    pooled = out["methods"]["composite_pace_x_eff_v1"]["POOLED"]
    check("output_pooled_has_provenance",
          all(k in pooled["provenance"] for k in
              ("model_version", "target", "cutoff", "universe", "date_range",
               "n", "evidence_class", "computed_at")))
    check("output_2021_winprob_excluded",
          out["methods"]["composite_pace_x_eff_v1"]["2021"].get("win_prob") is None)
    pm = out["market_comparison"]["paired_metrics"]
    check("output_paired_metrics_have_ci_and_n",
          all(pm[k] is None or ("paired_delta_ci95" in pm[k] and pm[k]["n_pairs"] > 0)
              for k in pm))
else:
    print("[SKIP] output artifact checks (score_baselines.json not built yet)")

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
    sys.exit(1)
print("ALL TESTS PASSED")
