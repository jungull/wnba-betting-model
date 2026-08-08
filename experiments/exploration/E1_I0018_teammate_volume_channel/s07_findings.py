"""E1_I0018 s07 -- assemble FINDINGS.json from every step's artifacts.  No new statistic here."""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_base import N_DRAWS, OUT, SEED, hdr

J = {}
for s in ["_s01", "_s02", "_s03", "_s04", "_s05", "_s06"]:
    with open(os.path.join(OUT, s + ".json"), encoding="utf-8") as fh:
        J[s] = json.load(fh)

res = pd.read_csv(os.path.join(OUT, "screen_results.csv"))
lad = pd.read_csv(os.path.join(OUT, "tiptime_loss_ladder.csv"))
wf = pd.read_csv(os.path.join(OUT, "walkforward_points.csv"))
cl = pd.read_csv(os.path.join(OUT, "ceiling_reconciliation.csv"))

with open(os.path.join(OUT, "CANDIDATES_PRESELECTED.md"), "rb") as fh:
    CAND_SHA = hashlib.sha256(fh.read()).hexdigest().upper()


def cell(cand, oc, base, stratum, col="dr2"):
    q = res[(res.candidate == cand) & (res.outcome == oc) & (res.base == base)
            & (res.stratum == stratum)]
    return None if not len(q) else float(q[col].iloc[0])


def cellpair(cand, oc, base, stratum):
    return {"dr2": cell(cand, oc, base, stratum),
            "p_correct_level": cell(cand, oc, base, stratum, "p_correct_level"),
            "p_familywise_maxt": cell(cand, oc, base, stratum, "p_familywise_maxt"),
            "p_row_level_NAIVE_CONTRAST_ONLY": cell(cand, oc, base, stratum, "p_row_level_NAIVE"),
            "sign": cell(cand, oc, base, stratum, "sign"),
            "n": cell(cand, oc, base, stratum, "n")}


TT, PO = "T01_c04_tiptime", "P01_c04_prevgame"

findings = {
  "screen": "E1_I0018_teammate_volume_channel",
  "status": "E1 EXPLORATION -- EVERY ITEM HERE IS A LEAD, NEVER A RESULT. No bootstrap, no "
            "promotion threshold, no preregistration obligation. Nothing was written to "
            "registry.jsonl, DECISION_LEDGER.jsonl, GRAPH_EVENTS.jsonl or idea_log.jsonl, and "
            "nothing outside this directory was modified.",
  "question": "D085 set aside C04_teammate_usg_present because it was dead on true shooting and "
              "eFG but alive on points-per-minute -- i.e. it was not an EFFICIENCY lead. Since "
              "POINTS = MINUTES x SHOTS-PER-MINUTE x POINTS-PER-SHOT and D081 put the points "
              "error ~3:1 on the per-minute step, a signal on the VOLUME arm of that step is "
              "aimed at exactly where the champion fails. Does it reach points, is it subject to "
              "the same arithmetic ceiling that killed D079 and D084, and is any of it available "
              "before tip-off?",
  "VERDICT": "SPLIT",
  "verdict_detail": {
      "tip_time_variant": "SURVIVES. T01 (reads TODAY's box membership) clears family-wise on "
                          "points-per-minute AND shots-per-minute, on the pooled frame and on the "
                          "decision stratum, under a SINGLE reference and under a COMPLETE "
                          "own-prior reference, and propagates to points with a WALK-FORWARD "
                          "coefficient at paired dR2 +0.0078 (cluster p 0.0005) on the decision "
                          "stratum. Its arithmetic ceiling is 0.003484, which is 3.1x D079's mix "
                          "ceiling and 27x D084's conversion ceiling. IT IS NOT USABLE AS A "
                          "FORECASTING FEATURE: its only non-prior input is a POST-GAME "
                          "observation.",
      "strictly_prior_only_variant": "PARTIALLY SURVIVES. P01 (previous game's box membership, no "
                                     "same-day information at all) clears family-wise on "
                                     "SHOTS-PER-MINUTE under the complete reference on both "
                                     "strata (fw p 0.0116 both), and propagates to points "
                                     "walk-forward at +0.00235 (cluster p 0.0345) on the decision "
                                     "stratum. It FAILS family-wise on POINTS-PER-MINUTE under "
                                     "the complete reference (fw p 0.0815 decision, 0.3727 "
                                     "pooled). Its ceiling is 0.001928, comparable to D079's "
                                     "0.001127. Every other prior-only variant (P02, P03, P06) "
                                     "dies under the complete reference and P02 additionally dies "
                                     "walk-forward.",
      "why_SPLIT_and_not_KEEP_or_KILL": "The channel is real and it is the volume channel, but "
                                        "roughly 60-70% of it lives in same-day roster "
                                        "information that is not knowable when an early line is "
                                        "posted. Rounding this to KEEP would overstate a usable "
                                        "edge; rounding it to KILL would discard the first "
                                        "channel in this program whose arithmetic ceiling is "
                                        "materially larger than D079's."},
  "partition": {"seasons": [2021, 2022, 2023, 2024],
                "check": "screenkit.assert_partition, VALUE-based on parsed dates and "
                         "season-valued columns. No regex or byte scan is used as a partition "
                         "check anywhere in this screen.",
                "max_game_date": "2024 season end (asserted < 2025-01-01 in s01)"},
  "inputs_and_manifests": J["_s01"]["manifests"],
  "forbidden_files_not_opened": [
      "data/w1_truth/player_game_availability.csv (asof_granularity=artifact, "
      "fit_through_season=2026 -> UNUSABLE; filtering does not help)",
      "data/w1_truth/roster_asof.csv (same verdict)"],
  "availability_method": "REBUILT FROM BOX MEMBERSHIP (minutes > 0), the D076 method, exactly as "
                         "D085 did. This is the same substitution D076 made when the same two "
                         "files were forbidden.",
  "r2_convention": "D069 -- plain unweighted OLS R2, SST about the UNWEIGHTED mean. The screening "
                   "statistic is the IN-SAMPLE increment dR2 of adding the candidate to a fixed "
                   "base; it is compared to a permutation null and NEVER to zero. "
                   "screenkit.r2_of_forecast scores given forecasts; screenkit.r2_plain/"
                   "delta_r2_plain refit. Both are used and never confused (the kit's P3 hazard).",
  "no_model_fitting": "The champion was never loaded and never retrained. The only fitting "
                      "anywhere is the screening regression y ~ 1 + base + candidate.",

  "STEP_1_reproduction_of_D085": {
      "target": "E0_I0016_efficiency_predictors, C04_teammate_usg_present",
      "column_level": {"max_abs_diff_C04_vs_frozen_column": 0.0,
                       "max_abs_diff_C08_vs_frozen_column": 0.0,
                       "nan_pattern_mismatches": 0,
                       "row_sets_identical": True,
                       "note": "C04 was rebuilt from master_player.parquet, not copied."},
      "statistic_level": J["_s02"]["abs_delta_dr2"],
      "statistic_level_permutation_p": J["_s02"]["abs_delta_permutation_p"],
      "per_season": J["_s02"]["abs_delta_dr2_per_season"],
      "worst_abs_delta_dr2": J["_s02"]["worst_abs_delta_dr2"],
      "worst_abs_delta_p": J["_s02"]["worst_abs_delta_p"],
      "REPRODUCED": J["_s02"]["REPRODUCED"],
      "note": "The three cells transcribed from D085's FULL-PRECISION screen_results.csv "
              "reproduced at 0.000e+00 (ppm, efg) and 3.253e-19 (ts). The residual ~1e-11 deltas "
              "are entirely the 10-decimal ROUNDING in survivor_forensics.json, which is the only "
              "place the decision-stratum, reliability-control and alternate-entity numbers are "
              "published.",
      "bonus_check_on_the_kit": "D085's N2 was implemented in its own ep_base.py because the kit "
                                "had no scheme for it (the K2 gap). That code was ported into the "
                                "kit at D086. This screen called the KIT version and reproduced "
                                "D085's p_N2 EXACTLY in every cell, which independently confirms "
                                "the port."},

  "STEP_2_channel_decomposition": {
      "identity": "y_ppm = y_spm * y_pps exactly (max abs err 1.776e-15), with "
                  "TSA = fga + 0.44*fta as 'shots'. y_pps == 2*y_ts and refB_pps == 2*refB_ts "
                  "both at 0.000e+00, so the conversion arm of this decomposition IS D085's true "
                  "shooting outcome rescaled, and the pps cell reproduces the ts dR2 to machine "
                  "precision -- a free correctness check on the machinery.",
      "measured_directly_not_inferred": {
          "POOLED_B_SINGLE": {"ppm": cellpair(TT, "ppm", "B_SINGLE", "POOLED"),
                              "spm_VOLUME_ARM": cellpair(TT, "spm", "B_SINGLE", "POOLED"),
                              "pps_CONVERSION_ARM": cellpair(TT, "pps", "B_SINGLE", "POOLED"),
                              "ts": cellpair(TT, "ts", "B_SINGLE", "POOLED"),
                              "efg": cellpair(TT, "efg", "B_SINGLE", "POOLED"),
                              "fgapm_secondary": cellpair(TT, "fgapm", "B_SINGLE", "POOLED"),
                              "ppfga_secondary": cellpair(TT, "ppfga", "B_SINGLE", "POOLED")},
          "DECISION_B_SINGLE": {"ppm": cellpair(TT, "ppm", "B_SINGLE", "DECISION"),
                                "spm_VOLUME_ARM": cellpair(TT, "spm", "B_SINGLE", "DECISION"),
                                "pps_CONVERSION_ARM": cellpair(TT, "pps", "B_SINGLE", "DECISION"),
                                "ts": cellpair(TT, "ts", "B_SINGLE", "DECISION"),
                                "efg": cellpair(TT, "efg", "B_SINGLE", "DECISION"),
                                "fgapm_secondary": cellpair(TT, "fgapm", "B_SINGLE", "DECISION"),
                                "ppfga_secondary": cellpair(TT, "ppfga", "B_SINGLE", "DECISION")}},
      "conclusion": "CONFIRMED AND STRENGTHENED. On the decision stratum the volume arm carries a "
                    "LARGER increment (0.007987) than points-per-minute itself (0.004963) while "
                    "the conversion arm is dead (0.000062, family-wise p 1.0). D085's indirect "
                    "inference was right; the direct measurement makes it sharper."},

  "STEP_2b_D087_reference_incompleteness_trap": {
      "prediction_registered_in_advance": "CANDIDATES_PRESELECTED.md section 5, hashed before any "
                                          "statistic: T01 = T02 - O01 identically (asserted at "
                                          "1.421e-14), T02 is constant within a team-game, so ALL "
                                          "of T01's within-team-game variation is MINUS the "
                                          "player's own strictly-prior usage per game -- a "
                                          "strictly-prior player-level quantity absent from "
                                          "D085's base. The prediction was that completing the "
                                          "reference would collapse the increment.",
      "outcome": "THE PREDICTION WAS HALF RIGHT AND IS REPORTED AS SUCH.",
      "ladder": {
          "ppm_POOLED": {"B_SINGLE": cellpair(TT, "ppm", "B_SINGLE", "POOLED"),
                         "B_COMPLETE": cellpair(TT, "ppm", "B_COMPLETE", "POOLED"),
                         "B_COMPLETE_PLUS_USAGE":
                             cellpair(TT, "ppm", "B_COMPLETE_PLUS_USAGE", "POOLED")},
          "ppm_DECISION": {"B_SINGLE": cellpair(TT, "ppm", "B_SINGLE", "DECISION"),
                           "B_COMPLETE": cellpair(TT, "ppm", "B_COMPLETE", "DECISION"),
                           "B_COMPLETE_PLUS_USAGE":
                               cellpair(TT, "ppm", "B_COMPLETE_PLUS_USAGE", "DECISION")},
          "spm_POOLED": {"B_SINGLE": cellpair(TT, "spm", "B_SINGLE", "POOLED"),
                         "B_COMPLETE": cellpair(TT, "spm", "B_COMPLETE", "POOLED"),
                         "B_COMPLETE_PLUS_USAGE":
                             cellpair(TT, "spm", "B_COMPLETE_PLUS_USAGE", "POOLED")},
          "spm_DECISION": {"B_SINGLE": cellpair(TT, "spm", "B_SINGLE", "DECISION"),
                           "B_COMPLETE": cellpair(TT, "spm", "B_COMPLETE", "DECISION"),
                           "B_COMPLETE_PLUS_USAGE":
                               cellpair(TT, "spm", "B_COMPLETE_PLUS_USAGE", "DECISION")}},
      "components_screened_separately": {
          "T02_teamgame_present_usg_ppm_DECISION_B_COMPLETE":
              cellpair("T02_teamgame_present_usg", "ppm", "B_COMPLETE", "DECISION"),
          "O01_own_usg_pg_ppm_POOLED_B_SINGLE":
              cellpair("O01_own_usg_pg", "ppm", "B_SINGLE", "POOLED"),
          "O01_own_usg_pg_ppm_POOLED_B_COMPLETE":
              cellpair("O01_own_usg_pg", "ppm", "B_COMPLETE", "POOLED"),
          "O01_own_usg_pg_ppm_DECISION_B_COMPLETE":
              cellpair("O01_own_usg_pg", "ppm", "B_COMPLETE", "DECISION")},
      "reading": "On the POOLED frame the trap is real and large: completing the reference cuts "
                 "T01's ppm increment 2.95x (0.003300 -> 0.001117) and O01 on its own is the "
                 "single biggest ppm increment in the whole screen (0.011116) which itself "
                 "collapses 8.2x once the reference is completed (-> 0.001360). D085's base was "
                 "genuinely incomplete. On the DECISION stratum, however, completing the "
                 "reference costs almost nothing (0.004963 -> 0.004235, 1.17x) and the surviving "
                 "signal is carried by T02, the TEAM-GAME component -- which is NOT an own-prior "
                 "quantity and cannot be a reference-incompleteness artifact. So the trap "
                 "explains most of the POOLED effect and almost none of the DECISION effect."},

  "STEP_3_tip_time": {
      "a_what_information_is_needed": {
          "the_only_non_prior_input": "PRESENT(g) = the set of players with MINUTES > 0 in "
                                      "TODAY's box for that team.",
          "why_that_is_worse_than_an_injury_report": "'appeared with minutes > 0' is strictly "
                                                     "stronger than 'was on the active list'. A "
                                                     "dressed, healthy coach's-decision DNP, a "
                                                     "blowout benching, a warm-up injury and an "
                                                     "ejection all remove a player from "
                                                     "PRESENT(g). A PERFECT pre-game injury "
                                                     "report therefore reconstructs at best a "
                                                     "SUPERSET of PRESENT(g), never PRESENT(g).",
          "earliest_moment_knowable": "PRESENT(g) itself is a POST-GAME observation and is never "
                                      "knowable pre-game. The closest pre-game proxies are the "
                                      "official inactive list and announced starting lineups, "
                                      "roughly 30-60 minutes before tip. EARLY LINES ARE POSTED "
                                      "THE PREVIOUS DAY OR THE MORNING OF, i.e. HOURS BEFORE ANY "
                                      "OF IT.",
          "what_this_screen_cannot_establish": "The split between 'absent because unavailable' "
                                               "and 'active but logged zero minutes' cannot be "
                                               "made here, because data/w1_truth/roster_asof.csv "
                                               "is the file that would make it and it is "
                                               "FORBIDDEN. Stated as a limit, not worked around.",
          "roster_churn": J["_s06"]["roster_churn"],
          "absence_persistence_DIAGNOSTIC":
              J["_s06"]["absence_persistence_DIAGNOSTIC_reads_next_game"]},
      "b_strictly_prior_only_variants": {
          "P01_c04_prevgame": {
              "definition": "identical to T01 except PRESENT is the team's PREVIOUS game's box "
                            "membership. Reads NO same-day information.",
              "spm_POOLED_B_COMPLETE": cellpair(PO, "spm", "B_COMPLETE", "POOLED"),
              "spm_DECISION_B_COMPLETE": cellpair(PO, "spm", "B_COMPLETE", "DECISION"),
              "ppm_POOLED_B_COMPLETE": cellpair(PO, "ppm", "B_COMPLETE", "POOLED"),
              "ppm_DECISION_B_COMPLETE": cellpair(PO, "ppm", "B_COMPLETE", "DECISION")},
          "P02_c04_availweighted": {
              "spm_POOLED_B_COMPLETE": cellpair("P02_c04_availweighted", "spm", "B_COMPLETE",
                                                "POOLED"),
              "ppm_DECISION_B_COMPLETE": cellpair("P02_c04_availweighted", "ppm", "B_COMPLETE",
                                                  "DECISION"),
              "note": "clears family-wise under B_SINGLE and dies under B_COMPLETE, and dies "
                      "again walk-forward (cluster p 0.16 / 0.94). Reported as attrition."},
          "P03_c04_avail5": {"ppm_DECISION_B_SINGLE": cellpair("P03_c04_avail5", "ppm", "B_SINGLE",
                                                               "DECISION")},
          "P04_absent_usg_prevgame_ppm_POOLED_B_SINGLE":
              cellpair("P04_absent_usg_prevgame", "ppm", "B_SINGLE", "POOLED"),
          "P05_n_present_prevgame_ppm_POOLED_B_SINGLE":
              cellpair("P05_n_present_prevgame", "ppm", "B_SINGLE", "POOLED"),
          "P06_c04_rotstab_ppm_POOLED_B_COMPLETE":
              cellpair("P06_c04_rotstab", "ppm", "B_COMPLETE", "POOLED")},
      "c_loss_ladder": json.loads(lad.to_json(orient="records")),
      "median_prior_only_retains_pct": J["_s06"]["median_prior_only_retains_pct"],
      "same_day_news_component_is_itself_significant": {
          "N02_news_vs_avail_spm_DECISION_B_COMPLETE":
              cellpair("N02_news_vs_avail", "spm", "B_COMPLETE", "DECISION"),
          "N01_news_vs_prevgame_spm_DECISION_B_COMPLETE":
              cellpair("N01_news_vs_prevgame", "spm", "B_COMPLETE", "DECISION"),
          "reading": "The pure same-day increment clears family-wise on its own, which is the "
                     "cleanest possible statement that the tip-time advantage is not an artifact "
                     "of the prior-only variant being a noisier version of the same thing."}},

  "STEP_4_points_propagation_and_ceiling": {
      "minutes_forecast": J["_s04"]["minutes_forecast"],
      "in_sample_coefficient": json.loads(
          pd.read_csv(os.path.join(OUT, "points_propagation.csv")).to_json(orient="records")),
      "WALK_FORWARD_coefficient_HEADLINE": json.loads(wf.to_json(orient="records")),
      "why_walk_forward_is_the_headline": "An in-sample screening coefficient reads the whole "
                                          "partition. Constraint 3 of this screen's brief requires "
                                          "the time-window audit to cover INFERENCE STEPS, so the "
                                          "coefficient is refitted on seasons < s and applied to "
                                          "season s. 2021 is unscored (no prior season).",
      "arithmetic_ceiling": {
          "form": "D084's: 1 sd of the centred signal moves the points forecast by X points "
                  "against a Y-point response sd, so dR2 <= Var(shift)/Var(response).",
          "TIP_TIME_DECISION_B_COMPLETE": {
              "points_move_per_1sd": 0.4553, "response_sd": 7.4956,
              "ceiling_dr2_D084_exact_form": 0.003689,
              "ceiling_dr2_from_actual_forecast_shift":
                  float(cl[(cl.candidate == TT) & (cl.stratum == "DECISION")
                           & (cl.base == "B_COMPLETE")]["D084_form_ceiling_var_share"].iloc[0])},
          "PRIOR_ONLY_DECISION_B_COMPLETE": {
              "points_move_per_1sd": 0.3400, "response_sd": 7.4956,
              "ceiling_dr2_D084_exact_form": 0.002057,
              "ceiling_dr2_from_actual_forecast_shift":
                  float(cl[(cl.candidate == PO) & (cl.stratum == "DECISION")
                           & (cl.base == "B_COMPLETE")]["D084_form_ceiling_var_share"].iloc[0])},
          "all_cells": json.loads(cl.to_json(orient="records")),
          "volume_route_cross_check": J["_s04"]["volume_route_ceiling"],
          "precedents": {"D079_shot_mix_channel": 0.001127, "D084_conversion_channel": 0.000129},
          "comparison": "The tip-time ceiling on the decision stratum (0.003689, D084's exact "
                        "form) is 3.3x D079's mix ceiling and 28.6x D084's conversion ceiling. "
                        "The STRICTLY-PRIOR-ONLY ceiling (0.002057) is 1.8x D079's and 15.9x "
                        "D084's. In points terms, "
                        "D084's conversion channel moved the forecast 0.0859 points per sd "
                        "against a 7.5505-point response sd; this one moves it 0.4553 points "
                        "per sd against a 7.4956-point response sd -- 5.3x further against an "
                        "almost identical denominator.",
          "the_paradox_and_its_resolution": "The realised paired dR2 on points EXCEEDS the "
                                            "D084-form ceiling in several cells. That is not an "
                                            "arithmetic error: the coefficient is fitted on "
                                            "POINTS-PER-MINUTE and then multiplied by minutes, so "
                                            "the shift is UNDER-scaled for points (implied "
                                            "optimal rescaling 1.3x to 3.0x). The identity "
                                            "realised = (2*c_opt - 1)*var_share holds to "
                                            "8.674e-19 across all 16 cells. The best-rescaling "
                                            "ORACLE ceiling is reported alongside and is a "
                                            "DIAGNOSTIC ONLY -- it uses the realised response.",
          "honest_denominator_caveat": "These increments are measured against a MATCHED "
                                       "POINT-IN-TIME REFERENCE (points R2 0.29 on the decision "
                                       "stratum, 0.49 pooled), NOT against the champion. D076's "
                                       "rule is obeyed: skill against a strictly-prior reference "
                                       "facing the same rows, never raw MAE reduction. The MAE "
                                       "figures are reported beside the skill figures precisely "
                                       "so they cannot be confused; the largest MAE reduction "
                                       "anywhere here is 0.79%."}},

  "STEP_5_mechanism": {
      "sign_predicted_in_advance": "CANDIDATES_PRESELECTED.md section 6, hashed before any "
                                   "statistic: usage redistribution -> NEGATIVE on ppm and spm; "
                                   "shot creation -> POSITIVE.",
      "measured": json.loads(pd.read_csv(os.path.join(OUT, "mechanism_signs.csv"))
                             .to_json(orient="records")),
      "verdict": "USAGE REDISTRIBUTION. T01's coefficient is NEGATIVE on both ppm and spm in "
                 "every stratum and under every base (16 of 16 cells), and the complementary "
                 "quantity T03_absent_usg is POSITIVE on spm in every stratum. The shot-creation "
                 "story predicted the opposite sign and is refuted. The sign was registered "
                 "before the statistic was computed.",
      "practical_magnitude": "On the decision stratum, moving T01 from its 10th to its 90th "
                             "percentile shifts the reference residual by -0.0504 shots per "
                             "minute = -1.52 true-shot attempts per game at 30.2 minutes, and "
                             "-0.0622 points per minute = -1.88 points per game.",
      "symmetry": {
          "table": json.loads(pd.read_csv(os.path.join(OUT, "symmetry_kink_test.csv"))
                              .to_json(orient="records")),
          "reading": "DIRECTIONALLY ASYMMETRIC BUT NOT SIGNIFICANTLY SO. The absence arm's slope "
                     "is larger than the return arm's in 8 of 8 cells (ratio 0.40 to 0.87, median "
                     "0.62), i.e. a player gains more when a teammate goes out than they give "
                     "back when the teammate returns. But the KINK term adds dR2 between 8e-06 "
                     "and 2.4e-04 over the linear deviation and fails BOTH correct-level nulls in "
                     "7 of 8 cells; the single exception (spm, POOLED, team norm, p_N2 0.0067) "
                     "has dR2 2.39e-04 and would not clear the family-wise threshold. The honest "
                     "statement is that the data are consistent with a symmetric, mechanical "
                     "redistribution and this screen cannot distinguish it from a modest "
                     "asymmetry."}},

  "nulls": {
      "N1_within_entity_season": "screenkit.permutation_null(scheme=SCHEME_WITHIN) at "
                                 "(team_id, season), block_col='season'. Entity level survives, "
                                 "game-to-game alignment dies.",
      "N2_entity_label_swap": "screenkit.entity_swap_null at (team_id, season) -- the K2 fix, now "
                              "a kit function. Whole entity-season series reassigned within "
                              "season at proportional positions.",
      "N3_row_level": "screenkit ROW_LEVEL via null_width_comparison. CONTRAST ONLY, NEVER a "
                      "verdict. No cluster-robust SE is reported anywhere as an alternative.",
      "level_chosen_by": "screenkit.detect_grouping_level, which returned "
                         "NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE and "
                         "recommended_permutation_level=None -- the K2 signature. Neither scheme "
                         "alone is valid, so BOTH are run and a cell is credited only if it beats "
                         "both.",
      "headline_rule": "p_correct_level = max(p_N1, p_N2); family-wise p = max over the two nulls "
                       "of the max-t p.",
      "grouping_level_report": J["_s02"]["grouping_level_detection"],
      "draws": N_DRAWS, "seed": SEED,
      "row_null_inflation": {
          "median_sd_N1_over_sd_row": J["_s03"]["attrition"]["median_inflation_N1_over_row"],
          "median_sd_N2_over_sd_row": J["_s03"]["attrition"]["median_inflation_N2_over_row"],
          "note": "Both are close to 1 on this frame, so the row-level null happens not to be "
                  "badly too narrow HERE. That is reported, not relied on: the row-level p still "
                  "carries no verdict anywhere in this screen."}},

  "multiplicity": {
      "family": "ALL %d cells screened in this directory, in ONE family" % len(res),
      "method": "max-t across the family from the correct-level permutation draws, standardised "
                "per cell, computed separately on N1 and N2 with the WORSE reported",
      "draws": N_DRAWS},
  "attrition": J["_s03"]["attrition"],
  "negative_control": {
      "candidate": "G01_noise (deterministic pseudo-random N(0,1), seed 20260808)",
      "cells": json.loads(res[res.candidate == "G01_noise"][
          ["outcome", "base", "stratum", "dr2", "p_correct_level",
           "p_familywise_maxt"]].to_json(orient="records")),
      "clears_familywise": 0,
      "points_propagation_paired_p_cluster": "0.66 to 0.73 in sample, 0.46 to 0.92 walk-forward"},
  "noop_placebo": J["_s03"]["noop_placebo"],
  "observed_sds": J["_s03"]["observed_sds"],
  "leakage_probes": {"references": J["_s01"]["leakage_probes_headline"],
                     "candidates_flagged": 0,
                     "note": "A probe flag is a SCREENING FLAG, NOT A VERDICT (kit K1). The two "
                             "reference probes fired on refB vs refA -- BOTH strictly prior by "
                             "construction -- which is exactly the better-estimator case K1 "
                             "documents. The positive control (a full-season mean) fired far "
                             "harder (corr +0.8465, dR2 0.2731) and is the calibration."},
  "preselection": {"preselected": True, "file": "CANDIDATES_PRESELECTED.md",
                   "sha256": CAND_SHA,
                   "frozen_at": "2026-08-08T06:55:22-04:00, before any statistic was computed",
                   "n_preselected": 16,
                   "n_declared_additions_before_any_statistic": 2,
                   "declared_additions": ["M03_dev_pos_playernorm", "M04_dev_neg_playernorm"],
                   "reason_for_additions": "CANDIDATES_PRESELECTED.md specified the M-family norm "
                                           "as the TEAM's strictly-prior expanding mean of T01. "
                                           "T01 is player-specific, so a team mean of it mixes "
                                           "O01 across players. Both norms were therefore built "
                                           "and BOTH are reported. The hashed specification was "
                                           "implemented exactly as M01/M02; the player-norm "
                                           "variant is M03/M04. Declared at implementation time, "
                                           "before any statistic was computed.",
                   "n_screened": int(res["candidate"].nunique()),
                   "candidates_added_after_seeing_results": 0,
                   "candidates_dropped_after_seeing_results": 0},
  "artifacts": sorted(os.listdir(OUT)),
}

with open(os.path.join(OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(findings, fh, indent=2, default=str)
hdr("WROTE FINDINGS.json")
print("  verdict = %s" % findings["VERDICT"])
print("  cells = %d, candidates screened = %d" % (len(res), res["candidate"].nunique()))
print("  candidate list SHA-256 = %s" % CAND_SHA)
