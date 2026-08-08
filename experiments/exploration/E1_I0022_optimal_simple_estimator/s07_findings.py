"""E1_I0022 STEP 7 -- assemble FINDINGS.json from the artefacts written by s01-s06."""
import json
import os

import numpy as np
import pandas as pd

import ose_base as B

J = lambda n: json.load(open(os.path.join(B.OUT, n)))
C = lambda n: pd.read_csv(os.path.join(B.OUT, n))

s01, s03, s04, s05, s06 = J("_s01.json"), J("_s03.json"), J("_s04.json"), J("_s05.json"), J("_s06.json")
pre = J("_prereg.json")
cv, inf_, sel, dep = C("champion_vs_best.csv"), C("paired_inference.csv"), \
    C("selection_and_optimism.csv"), C("depth_adaptive_selection.csv")
fbs, hyb, r2, rob = C("fallback_split.csv"), C("hybrid_postocc.csv"), \
    C("r2_walkforward.csv"), C("eval_row_floor_robustness.csv")
surf = C("estimator_surface.csv")
ctrl = C("cyclic_shift_control.csv").rename(columns={"Unnamed: 0": "target"})

pool = cv[cv.slice == "pooled_wf"].set_index("target")
strat = cv[cv.slice == "decision_stratum_wf"].set_index("target")
mod = fbs[fbs.slice == "champion_MODELLED_rows"].set_index("target")
fbr = fbs[fbs.slice == "champion_FALLBACK_rows"].set_index("target")
seli = sel.set_index("target")

F = {
  "screen": "E1_I0022_optimal_simple_estimator",
  "question_from_the_user": "so at this point a player's average score to date with a ewma is the "
                            "best predictor of their score and any nuance just muddies the water?",
  "one_line_answer":
      "Almost. An EWMA of the player's own prior games -- properly tuned -- beats the reference this "
      "programme has been scoring against, and beats the CHAMPION outright on the pooled rows for all "
      "four targets. But the champion's pooled loss is entirely the 7.33% of rows on which it emits a "
      "literal constant; on the 92.67% of rows where it actually models, the champion BEATS the best "
      "tuned simple estimator on points (+1.07%, p=0.0002) and FGA (+0.88%, p=0.0012), ties on minutes, "
      "and slightly loses on points-per-minute. The nuance is not muddying the water -- it is being "
      "swamped by a cold-start fallback.",

  "partition": {"seasons_present": [2022, 2023, 2024],
                "policy": "exploration partition 2021-2024; the 2021 fold is degenerate "
                          "(n_train_rows=0) and is absent from the frozen frame",
                "season_calendar_ranges": s01["season_ranges"],
                "no_2025_or_2026_row_was_read_joined_plotted_or_described": True},

  "step1_reproduction": {
      "source": "E0_I0015_points_skill_decomposition/decomp_frame.parquet + component_skill.csv (D081)",
      "verdict": "EXACT -- all nine published numbers reproduced at |delta| = 0.000e+00",
      "max_abs_delta_skill": s01["max_abs_delta_skill"],
      "max_abs_delta_mae": s01["max_abs_delta_mae"],
      "reproduced_with": "this screen's own local metric code (ose_base), NOT by importing psd_base "
                         "and NOT by importing the shared screen kit",
      "table": s01["reproduction"],
      "independent_reference_rebuild": s01["independent_reference_rebuild"],
      "leak_probe_corr_with_players_strictly_future_mean_pts": s01["leak_probe_corr_with_future"]},

  "step2_preregistration": {
      "file": "ESTIMATOR_GRID.md", "grid_sha256": pre["grid_sha256"],
      "spec_sha256": pre["spec_sha256"], "n_cells": pre["n_cells"],
      "added_after_prereg": 0, "dropped_after_prereg": 0,
      "dimensions": {"targets": pre["targets"], "modes": pre["modes"],
                     "memory_settings": len(pre["memories"]), "shrink_settings": len(pre["shrinks"]),
                     "history_minutes_floors": pre["floors"]},
      "hash_written_before_any_skill_number_for_any_cell": True},

  "step2_surface_shape": {
      "winner_per_target_tuned_on_2022_2023": {
          t: json.loads(seli.loc[t, "cellB"]) for t in B.TARGETS},
      "FORM": "EWMA beats SMA beats expanding for ALL FOUR targets. For points the COMPOSITE "
              "(minutes-estimate x points-per-minute-estimate) edges the direct points estimate "
              "(4.10855 vs 4.11323 tuning MAE). Minutes-weighting the history HURTS every level "
              "target (pts 4.10855 -> 4.30762).",
      "MEMORY": {"points": "EWMA half-life 8 games", "minutes": "EWMA half-life 2 games",
                 "fga": "EWMA half-life 5 games", "ppm": "EWMA half-life 40 games (~expanding)",
                 "comment": "the optimal memory differs by a factor of 20 ACROSS TARGETS: minutes is "
                            "a short-memory quantity (role changes fast), points-per-minute is a "
                            "long-memory quantity (true shooting talent), points sits in between. "
                            "A single half-life for all three is the wrong object."},
      "SHRINKAGE": {"points": "k=0.5 toward the player's own PRIOR-SEASON value",
                    "minutes": "NONE (k=0) -- shrinkage strictly hurts minutes",
                    "fga": "k=0.5 toward prior season", "ppm": "k=2 toward prior season",
                    "comment": "shrinkage is weak everywhere and the best target is always the "
                               "player's own prior season, never the league mean; the league mean "
                               "was the worst of the three shrinkage targets for every quantity."},
      "RATIO_OF_PRIOR_SUMS_vs_MEAN_OF_PRIOR_RATIOS": {
          "winner_for_ppm": "mean_of_prior_ratios at EVERY history floor",
          "by_floor": s05["ros_vs_mor_by_floor"],
          "comment": "D093 found the ordering FLIPPED under a minutes floor. It does NOT flip here: "
                     "mean-of-prior-ratios wins at floors 0/5/10/15 and its margin WIDENS with the "
                     "floor (0.00123 -> 0.00236). The difference is that D093's floor filtered the "
                     "rows being SCORED; this grid's floor filters the HISTORY. Both were run."},
      "HISTORY_MINUTES_FLOOR": "floor = 0 wins for every target, monotonically. Every positive floor "
                               "degrades the estimator (points 4.109 -> 4.209 -> 4.379 -> 4.617 at "
                               "floors 0/5/10/15). Discarding low-minute prior games throws away "
                               "more information than it removes noise.",
      "marginal_best_by_dimension_tuning_rows": s04["surface_shape"]},

  "step2_depth_adaptation": {
      "does_the_optimum_vary_with_depth": "YES in the selected cell, NO in walk-forward payoff",
      "walkforward_gain_from_adapting_pct": {
          t: float(100 * (s04["selection"][t]["mae_wf_adaptive"] /
                          s04["selection"][t]["mae_wf_global"] - 1)) for t in B.TARGETS},
      "comment": "Selected cells differ sharply by tier -- e.g. minutes picks EWMA half-life 12 with "
                 "shrinkage at 1-2 priors and half-life 2 unshrunk at 25+; ppm picks a 1-game window "
                 "heavily shrunk at 1-2 priors and a 30-game window at 25+. But the walk-forward "
                 "gain from adapting is -0.06% to -0.21% (a gain) for pts/minutes/fga and +0.07% (a "
                 "LOSS) for ppm. The depth-dependence is real and the payoff from exploiting it is "
                 "within noise. One global setting is very nearly good enough.",
      "per_tier": dep.to_dict("records")},

  "step2_tuning_honesty": {
      "protocol": "split A: hyperparameters selected on season 2022, scored on 2023. "
                  "split B: selected on 2022+2023, scored on 2024. "
                  "WALK-FORWARD EVALUATION ROWS = 2023 union 2024 (n=9,517). "
                  "Selection criterion = lowest MAE on the TUNING rows only.",
      "in_sample_versus_walkforward_gap": sel.to_dict("records"),
      "optimism_gap_pct": {r["target"]: r["optimism_gap_pct"] for _, r in sel.iterrows()},
      "why_it_matters": "The largest optimism gap is +0.80% (points). The champion's pooled deficit "
                        "is -1.93% to -4.41%. The verdict therefore survives even if the estimator's "
                        "hyperparameters had been chosen with full hindsight -- the deficit is "
                        "2.4x to 85x the entire tuning optimism."},

  "step3_THE_DECISIVE_COMPARISON": {
      "definition": "champion_skill = 1 - MAE_champion / MAE_best_tuned_simple_estimator, identical "
                    "walk-forward rows. POSITIVE = the champion is better.",
      "n_walkforward_rows": int(s04["n_wf_eval_rows"]),
      "HEADLINE_ONE_NUMBER_PER_TARGET_POOLED": {
          t: {"champion_skill_vs_best_simple_pct": float(100 * pool.loc[t, "champ_skill_vs_best_simple"]),
              "champion_mae": float(pool.loc[t, "champ_mae"]),
              "best_simple_mae": float(pool.loc[t, "best_simple_mae"]),
              "p_two_sided_blockflip": float(
                  inf_[(inf_.target == t) & (inf_.slice == "pooled_wf")]["p_two_sided_blockflip"].iloc[0]),
              "verdict": "CHAMPION LOSES"} for t in B.TARGETS},
      "on_D081_decision_stratum": {
          t: {"n": int(strat.loc[t, "n"]),
              "champion_skill_vs_best_simple_pct": float(100 * strat.loc[t, "champ_skill_vs_best_simple"]),
              "p_two_sided_blockflip": float(
                  inf_[(inf_.target == t) & (inf_.slice == "decision_stratum_wf")]["p_two_sided_blockflip"].iloc[0])}
          for t in B.TARGETS},
      "by_prior_appearance_tier": cv[cv["slice"].str.startswith("tier_")].to_dict("records"),
      "how_much_of_the_reference_was_the_problem": {
          t: {"best_simple_beats_D081_reference_by_pct":
              float(100 * pool.loc[t, "best_simple_skill_vs_d081_ref"]),
              "champion_vs_D081_reference_pct": float(100 * pool.loc[t, "champ_skill_vs_d081_ref"]),
              "champion_vs_best_simple_pct": float(100 * pool.loc[t, "champ_skill_vs_best_simple"])}
          for t in B.TARGETS},
      "reference_dependence_measured": "Swapping the reference from D081's frozen prior-appearance "
                                       "mean to the best tuned simple estimator moves the champion's "
                                       "MINUTES skill from +3.71% to -4.41% on IDENTICAL rows -- an "
                                       "8.12-point swing from the comparison alone, with the "
                                       "champion's forecasts untouched. FGA moves from +0.00% to "
                                       "-3.13%, points from -0.57% to -1.93%, ppm from +0.99% to "
                                       "-1.33%. This is D090's factor-of-six phenomenon reproduced "
                                       "on four new targets, and it confirms reference dependence as "
                                       "the leading explanation for the programme's nulls (D091, D093).",
      "r2_walkforward_no_refit": r2.to_dict("records")},

  "step4_WHERE_THE_ADVANTAGE_LIVES": {
      "the_single_dominant_split": "the champion's own pre-game `<target>__is_fallback` flag",
      "fallback_rows_wf": s06["fallback_rows_wf"], "fallback_share_wf": s06["fallback_share_wf"],
      "fallback_levels": s06["fallback_levels_wf"],
      "on_fallback_rows_the_champion_emits": "TWO distinct point values across all 698 rows "
                                             "(points sd 0.0156, minutes sd 0.0474, fga sd 0.0177) "
                                             "-- it is a literal constant. This extends D092, which "
                                             "found a constant below 3 appearances: the constant "
                                             "region is exactly the fallback region (all 657 rows "
                                             "with <3 priors, plus 41 rows in the 3-7 tier).",
      "champion_vs_best_simple_on_FALLBACK_rows": {
          t: {"n": int(fbr.loc[t, "n"]), "skill_pct": float(100 * fbr.loc[t, "champ_skill_vs_best_simple"]),
              "p": float(fbr.loc[t, "p_two_sided_blockflip"])} for t in B.TARGETS},
      "champion_vs_best_simple_on_MODELLED_rows": {
          t: {"n": int(mod.loc[t, "n"]), "skill_pct": float(100 * mod.loc[t, "champ_skill_vs_best_simple"]),
              "p": float(mod.loc[t, "p_two_sided_blockflip"])} for t in B.TARGETS},
      "THE_NEAR_CANCELLATION": "Exactly the failure mode D081 warned about. Pooled points is "
                               "-1.93%; that is 610 rows at -38.06% cancelling 8,860 rows at "
                               "+0.92%. The 1-2-prior tier alone contributes +139.5% of the pooled "
                               "excess error for points and +92.4% for minutes.",
      "pooled_decomposition_by_tier": C("pooled_decomposition.csv").to_dict("records"),
      "other_conditional_slices": C("where_the_advantage_lives.csv").to_dict("records"),
      "where_the_champion_WINS": "points on modelled rows (+1.07%, p=0.0002); FGA on modelled rows "
                                 "(+0.88%, p=0.0012); points in every tier with >=3 priors "
                                 "(+0.54% to +1.32%); FGA at 15-24 priors (+1.82%, p=0.0007) and "
                                 "25+ (+0.77%, p=0.047); and it wins MORE on LOW-minute players "
                                 "(points +4.36% in the bottom trailing-5-minutes quartile) than on "
                                 "high-minute ones (-1.08% in the top quartile).",
      "where_the_champion_LOSES": "every fallback row, catastrophically (-35% to -43%); minutes "
                                 "everywhere (it never beats the estimator on any tier by more than "
                                 "+0.03%, all p>0.86); points-per-minute in every tier except a dead "
                                 "heat at 15-24 priors; and on short rest (points -8.64% at 1-2 "
                                 "rest days) and long layoffs (-2.81% at 3+ days).",
      "post_hoc_hybrid_DECLARED_POST_HOC": hyb.to_dict("records")},

  "controls_and_traps": {
      "cyclic_shift_control": {
          "construction": "within-player CYCLIC SHIFT of the champion's forecast series, credited to "
                          "E1_I0021_heterogeneity_diagnostic/hd_base.py cyclic_shift_within_groups (D093)",
          "verified_to_perturb": True,
          "measured": ctrl.to_dict("records"),
          "reproduces_D093s_warning": "the plain within-player SHUFFLE null is 1.34x to 2.14x "
                                      "NARROWER than the honest cyclic-shift null for every target "
                                      "(minutes: sd 0.00677 vs 0.01448). A test built on the shuffle "
                                      "would have been anticonservative here too."},
      "vacuous_control_check": "every control in this screen was checked for a nonzero measured sd "
                               "before being read as evidence; the cyclic shift moves the statistic "
                               "by sd 3.9e-03 to 1.4e-02, not 5.2e-17",
      "paired_inference": "(season, player_id) BLOCK SIGN-FLIP on paired absolute-error differences, "
                          "4,000 draws, never row-level",
      "nothing_was_fitted_on_the_champion": True,
      "evaluation_row_minutes_floor_robustness": rob.to_dict("records"),
      "robustness_verdict": "the champion loses at EVERY evaluation-row minutes floor from 0 to 24 "
                            "for all four targets; the pooled verdict does not depend on garbage time"},

  "self_identified_defects_and_where_i_could_have_cheated": {
      "1_GRAND_fallback_touches_the_whole_frame": {
          "what": "the shrinkage-target fallback chain ends in a whole-frame value",
          "rows_affected": 56, "seasons_affected": [2022],
          "why_it_is_bounded": "it fires only on rows whose season has no strictly-earlier game AND "
                               "no predecessor season in the frame -- i.e. the opening date of 2022. "
                               "2023 and 2024 opening-date rows fall back to the previous season, "
                               "which is calendar-disjoint and therefore strictly prior. Every "
                               "WALK-FORWARD EVALUATION row is in 2023 or 2024, so no evaluation row "
                               "ever reaches it. It can only have contaminated 56 of 4,362 tuning "
                               "rows in split A (1.28%).",
          "asserted_in_code": "s03_sweep.py asserts the GRAND-fallback rows are 2022-only and the "
                              "assertion is live (it FIRED on a first draft that claimed the wrong "
                              "thing, which is how the 135-vs-56 distinction was found)"},
      "2_post_hoc_fallback_split": "the fallback/modelled split in s06 was chosen AFTER seeing the "
                                   "tier table. It is labelled post hoc everywhere. Nothing was "
                                   "re-selected on it and no hyperparameter depends on it, but the "
                                   "hybrid MAE in hybrid_postocc.csv must be read as descriptive.",
      "3_no_hyperparameter_was_chosen_after_seeing_an_evaluation_number":
          "the grid was hashed in s02 before any cell's skill was computed; s03 computed the whole "
          "surface with no selection in it; s04 selected only on tuning-row MAE. The in-sample "
          "selection is computed and published SOLELY as the optimism gap and is never the headline.",
      "4_conditional_slices_in_s05_are_descriptive": "the slice list was written before the numbers "
                                                     "but is not multiplicity-corrected; treat "
                                                     "individual slice p-values as descriptive.",
      "5_ppm_is_scored_as_a_ratio": "points-per-minute MAE is on the ratio scale, so its skill "
                                    "numbers are not commensurable with the level targets'.",
      "6_only_236_players_and_475_player_seasons": "block-level inference has 475 blocks pooled and "
                                                   "as few as ~150 in thin tiers; tier-0 (n=47) "
                                                   "numbers are reported but should not be leaned on."},

  "artefacts": sorted(os.listdir(B.OUT)),
}

json.dump(F, open(os.path.join(B.OUT, "FINDINGS.json"), "w"), indent=2, default=str)
B.hdr("FINDINGS.json WRITTEN")
print(json.dumps(F["step3_THE_DECISIVE_COMPARISON"]["HEADLINE_ONE_NUMBER_PER_TARGET_POOLED"], indent=2))
print(json.dumps(F["step4_WHERE_THE_ADVANTAGE_LIVES"]["champion_vs_best_simple_on_MODELLED_rows"], indent=2))
print(json.dumps(F["step3_THE_DECISIVE_COMPARISON"]["how_much_of_the_reference_was_the_problem"], indent=2))
print("DONE s07")
