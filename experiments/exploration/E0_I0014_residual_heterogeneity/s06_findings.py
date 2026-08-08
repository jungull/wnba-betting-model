"""Assemble FINDINGS.json from the artefacts produced by s03/s04/s05."""
import json
import os

import numpy as np
import pandas as pd

import rh_base as B

R = pd.read_csv(os.path.join(B.OUT, "screen_results.csv"))
FW = json.load(open(os.path.join(B.OUT, "familywise_summary.json")))
P1 = json.load(open(os.path.join(B.OUT, "step1_provenance.json")))
NP = json.load(open(os.path.join(B.OUT, "noop_placebo.json")))
A = pd.read_csv(os.path.join(B.OUT, "abstention_curves.csv"))
S = pd.read_csv(os.path.join(B.OUT, "abstention_per_season.csv"))
CC = pd.read_csv(os.path.join(B.OUT, "complete_case_robustness.csv"))
SUB = pd.read_csv(os.path.join(B.OUT, "abstention_games_prior_within_nonfallback.csv"))
COMP = pd.read_csv(os.path.join(B.OUT, "abstention_composite_minutes.csv"))

cells = []
for _, r in R.iterrows():
    cells.append({k: (None if (isinstance(v, float) and not np.isfinite(v)) else
                      (v.item() if hasattr(v, "item") else v)) for k, v in r.items()})

Ra = R[R["dependent"].str.endswith("absres")].copy()
Ra["abs_dec_spread"] = Ra["dec_spread"].abs()
alive = Ra[(Ra["p_correct_level"] < 0.05)]
dead = Ra[(Ra["p_correct_level"] >= 0.05)]

rank = (Ra.sort_values("abs_dec_spread", ascending=False)
        [["candidate", "family", "dependent", "correct_null_level", "beta_per_sd", "t_classical",
          "p_correct_level", "p_row_level_NAIVE", "null_inflation_factor",
          "p_familywise_whole_screen", "p_familywise_absres_family",
          "dec_lo_mean", "dec_hi_mean", "dec_spread", "dec_ratio",
          "qrt_lo_mean", "qrt_hi_mean", "qrt_ratio", "delta_r2_plain_unweighted"]]
        .head(40).to_dict(orient="records"))

out = {
  "experiment_id": "E0_I0014_residual_heterogeneity",
  "tier": "E0_DISCOVERY",
  "status_of_every_number_here": (
      "LEAD, NOT RESULT. E0 is fast, permissive, time-boxed and explicitly non-claiming. Nothing "
      "in this file may be cited as evidence for anything, promoted, or entered on a leaderboard. "
      "No preregistration, no bootstrap, no promotion threshold was run."),
  "question": (
      "GRAPH_POLICY 13.5 / decision D051: not 'what new feature improves the mean forecast' but "
      "'what observable pre-game state predicts WHEN the existing player model is accurate versus "
      "inaccurate', and can we abstain elsewhere."),

  "partition": {
    "seasons_read": [2021, 2022, 2023, 2024],
    "seasons_screened": [2022, 2023, 2024],
    "why_2021_dropped": ("the 2021 OOF fold is DEGENERATE -- fold_receipt__2021.json reports "
                         "train_seasons=[], n_train_rows=0, model_was_fitted=false, "
                         "cold_start_declared_constant_only=true. Its residuals are residuals of a "
                         "declared constant, not of the model."),
    "holdout_2025_2026": ("NEVER read, joined, plotted, described or summarised. Enforced by a "
                          "VALUE test on the season column and on max(game_date) at every load and "
                          "before every write (rh_base.guard). No regex/byte scan of file contents "
                          "was used as a partition check anywhere."),
    "guard_points": ["rh_base.load_master", "rh_base.load_contract", "s03 analysis frame write",
                     "s04 screen input", "s05 abstention input"]
  },

  "manifest_checks": {
    "data/masters/master_player.parquet": {"asof_granularity": "row", "verdict": "USED"},
    "experiments/prediction_contract_v4/player_game.parquet": {"asof_granularity": "row",
                                                               "verdict": "USED (row_uid bridge + outcomes)"},
    "experiments/cbs_v15_player_oof_v5/attempt_001/predictions__*__{2022,2023,2024}.parquet": {
        "asof_granularity": "artifact",
        "verdict": "USED, and here is why that is legitimate: each per-season artifact carries its "
                   "OWN fit_through_season equal to its own season (2022/2023/2024), so the WHOLE "
                   "artifact is bounded inside the exploration partition. No filtering is being "
                   "relied on to rescue a mixed-bound file; the file itself never saw 2025/2026.",
        "fit_through_season_by_file": {"2022": 2022, "2023": 2023, "2024": 2024}},
    "data/w1_truth/player_game_availability.csv": {
        "asof_granularity": "artifact", "fit_through_season": 2026,
        "verdict": "REFUSED AND NEVER OPENED. This is the file an availability screen reaches for "
                   "first; its manifest was read before any use and it is artifact-granular with a "
                   "2026 bound, so filtering to 2021-2024 does not help."},
    "data/w1_truth/roster_asof.csv": {"asof_granularity": "artifact", "fit_through_season": 2026,
                                      "verdict": "REFUSED AND NEVER OPENED"},
    "data/zone_maps/*": {"verdict": "artifact-granular, NOT TOUCHED"},
    "experiments/minutes_baselines/test_predictions.csv": {
        "verdict": "NOT USED -- it has NO sibling manifest, so its as-of granularity cannot be "
                   "established, and its test seasons are 2024/2025/2026."}
  },

  "step1_point_in_time_provenance": {
    "verdict": "POINT-IN-TIME. A genuine season-chronological walk-forward already existed; no "
               "walk-forward had to be built.",
    "residual_source": "experiments/cbs_v15_player_oof_v5/attempt_001/predictions__<target>__<season>.parquet",
    "arm": "cbs_v15_player_oof_v5, estimator inherited from contract_baseline_suite_v14",
    "targets_available": {"pts": "player_scoring_distribution",
                          "minutes": "e_minutes_given_active",
                          "fga": "attempts_usage",
                          "p_active": "declared constant 0.8 -- not screened"},
    "targets_NOT_available": ["rebounds", "assists"],
    "fold_structure": P1["provenance_by_season"],
    "receipt_evidence": ["fold_boundary receipt ok in every fold",
                         "provenance_history receipt ok in every fold",
                         "own_outcome_never_informed_its_forecast = true in every fold",
                         "forecast_cutoff is a prior-day 18:00 UTC stamp; feature_asof is a "
                         "prior-day 12:00 UTC stamp, per row"],
    "empirical_leak_probes": {
        "probe_1_cold_start_is_a_pooled_constant": (
            "rows flagged is_cold_start carry exactly ONE distinct pred_point per season for every "
            "target -- a pooled prior, carrying no player-specific information"),
        "probe_2_prior_vs_future_tracking": {
            "pts": {"corr_pred_prior_mean": 0.9467, "corr_pred_future_mean": 0.8540},
            "minutes": {"corr_pred_prior_mean": 0.9220, "corr_pred_future_mean": 0.8299},
            "fga": {"corr_pred_prior_mean": 0.9486, "corr_pred_future_mean": 0.8785},
            "reading": "every forecast tracks the player's PRIOR-game mean more tightly than the "
                       "player's remaining-season mean, which is what a point-in-time forecast "
                       "must do and what an in-sample fit would not."}},
    "caveat_declared": ("the v15 artifacts are stamped generation_only=true / scores_computed=false. "
                        "Computing residuals from them for an E0 characterisation is not a scoring "
                        "event and no metric here is registered.")
  },

  "baseline_error_levels_2022_2024_appeared_rows": P1["baselines"],
  "baseline_reading": (
      "the champion player forecast barely beats a point-in-time expanding prior-appearance mean: "
      "skill = -0.22% on points, +0.12% on FGA, +3.55% on minutes. This is the number the "
      "abstention curves have to move, and it is why every curve below reports SKILL as well as MAE."),

  "r2_convention": {
      "declared": "PLAIN UNWEIGHTED OLS R2 = 1 - SSE/SST with SST about the UNWEIGHTED mean (D069)",
      "weighting_used": "none anywhere in this screen",
      "defective_form_avoided": "sst = sum((sqrt(w)*y - mean(sqrt(w)*y))**2) is NOT used",
      "implementation": "rh_base.r2_plain and the delta_r2_plain_unweighted column"},

  "screen_design": {
      "dependent_quantities": ["absolute residual", "squared residual"],
      "targets": ["pts", "minutes", "fga"],
      "n_rows": FW["n_rows"],
      "n_candidates_after_dedupe": FW["n_candidates"],
      "n_cells": FW["n_cells"],
      "dedupe_note": ("is_fallback / fallback_level / is_cold_start / n_prior_games are byte-identical "
                      "across the three targets in the v15 artifact; the duplicate copies were removed "
                      "so they are not triple-counted in the family"),
      "model": "|resid| ~ season fixed effects + z(candidate); FWL slope, classical t reported but "
               "never trusted on its own",
      "missing_data": "within-season median imputation so one shared permutation index serves every "
                      "candidate; complete-case robustness reported for the imputed candidates",
      "permutation_draws": FW["n_draws"], "seed": FW["seed"]},

  "permutation_method": {
      "principle": "permute at the level at which the candidate ACTUALLY VARIES; permute the "
                   "ASSIGNMENT of an already-computed value, never recompute inside a draw",
      "BETWEEN_block_null": "whole (season,player_id) or (season,team_id) blocks of already-computed "
                            "values are reassigned to other blocks inside the same season",
      "WITHIN_block_null": "values are shuffled INSIDE each block, so the block's LEVEL survives and "
                           "only the game-to-game alignment is destroyed",
      "selection_rule": ("var_share_between_blocks > 0.5 -> BETWEEN-block is the candidate's null; "
                         "otherwise WITHIN-block is. Applying the wrong one leaves the effect "
                         "standing and returns p ~ 1 by construction, which is exactly what happens "
                         "in the columns p_between_block_null / p_within_block_null for the "
                         "mismatched cells -- both are reported for every cell so this is visible."),
      "n_correct_null_between": FW["n_correct_null_between"],
      "n_correct_null_within": FW["n_correct_null_within"],
      "n_blocks": {"player_season": 475, "team_season": 36},
      "row_level_naive_null": "reported ALONGSIDE, never used for a verdict",
      "inflation_factor": {
          "definition": "sd of the correct-level max-|t| null divided by sd of the naive row-level null",
          "min": float(R["null_inflation_factor"].min()),
          "p05": float(R["null_inflation_factor"].quantile(0.05)),
          "median": float(R["null_inflation_factor"].median()),
          "p95": float(R["null_inflation_factor"].quantile(0.95)),
          "max": float(R["null_inflation_factor"].max()),
          "frac_cells_above_1": float((R["null_inflation_factor"] > 1).mean()),
          "median_by_level": {
              "BETWEEN-block": float(R[R.correct_null_level == "BETWEEN-block"]
                                     ["null_inflation_factor"].median()),
              "WITHIN-block": float(R[R.correct_null_level == "WITHIN-block"]
                                    ["null_inflation_factor"].median())}},
      "inflation_reading": ("median 1.40, 5th-95th pct 0.95-2.36, range 0.58-2.89, above 1 in 84% "
                            "of cells. For block-level state (between-block null) it runs 1.00-2.89 "
                            "with median 1.99, reproducing the program's known 1.00-3.82x finding. "
                            "For a handful of within-block candidates the correct null is NARROWER "
                            "than the naive one -- the naive null is not uniformly anticonservative, "
                            "it is simply the wrong null in whichever direction."),
      "cluster_robust_se": "NOT used as a substitute -- the program has found it unreliable in both "
                           "directions"},

  "familywise": {
      "family": "%d dependents x %d candidates = %d cells, max-|t| across the SAME permutation draws"
                % (FW["n_dependents"], FW["n_candidates"], FW["n_cells"]),
      "observed_max_abs_t": FW["observed_max_abs_t_whole_screen"],
      "familywise_p_whole_screen": FW["familywise_p_whole_screen_correct_level"],
      "observed_max_abs_t_absres_family": FW["observed_max_abs_t_absres_family"],
      "familywise_p_absres_family": FW["familywise_p_absres_family_correct_level"],
      "null_maxt_correct_level": FW["null_maxt_correct"],
      "null_maxt_row_naive": FW["null_maxt_row_naive"],
      "verdict": ("the screen as a whole survives family-wise correction at the correct level "
                  "(p = 0.000, observed max|t| = 41.6 against a correct-level max-|t| null whose "
                  "own maximum over 1000 draws is 30.3). The heterogeneity is real; the question "
                  "is whether it is USEFUL, which is what step 3 answers.")},

  "noop_placebo": NP["noop_placebo"],
  "noop_placebo_reading": ("run ON PURPOSE as a POSITIVE diagnostic. The defective control permutes "
                           "the block key and then looks the value up by the ORIGINAL key, so the "
                           "shuffled label is never consulted. It reproduced the real t = -15.270403 "
                           "on every one of 200 draws with max deviation exactly 0.000e+00 and sd "
                           "exactly 0.000000 -- the known signature. The live block control on the "
                           "same cell moved to mean t = -11.23 with sd 1.046, which proves the real "
                           "permutation genuinely shuffles."),

  "ranked_candidates_by_practical_spread_on_abs_residual": rank,
  "attrition": {
      "n_absres_cells": int(len(Ra)),
      "n_cells_p_correct_lt_0p05": int(len(alive)),
      "n_cells_p_correct_ge_0p05": int(len(dead)),
      "n_cells_familywise_lt_0p05_absres_family": int((Ra["p_familywise_absres_family"] < 0.05).sum()),
      "candidates_with_any_familywise_survivor": sorted(
          Ra[Ra["p_familywise_absres_family"] < 0.05]["candidate"].unique().tolist()),
      "reading": ("115 of 174 |residual| cells clear p<0.05 at the correct level, which sounds like "
                  "a lot until the family is applied: only 20 cells across 14 candidates clear the "
                  "family-wise max-|t| correction, and ten of those 14 are volume proxies "
                  "(pred_point, pl_*_mean5, pl_start_frac5). THREE survive both the family and the "
                  "volume test: is_fallback / fallback_level on minutes, and pts__pred_width on "
                  "points. Adding pl_games_prior -- which FAILS family-wise (|t|=15.3 against a "
                  "family max of 41.6) but carries by far the largest SKILL gain -- the usable "
                  "leads from a 58-candidate screen number FOUR.")},
  "all_cells": cells,

  "the_volume_confound": (
      "|residual| on a counting stat scales with the player's volume, so ANY rule that abstains on "
      "high-volume player-games cuts pooled MAE while carrying zero information. pts__pred_point is "
      "the proof: abstaining on its worst quartile cuts points MAE by 9.9% and moves SKILL by "
      "+0.00007. Raw MAE reduction is NOT evidence of a conditional edge. Every abstention curve "
      "here reports skill against a point-in-time expanding prior-appearance mean, which absorbs "
      "the confound."),

  "step3_abstention": {
      "reference_forecast": "point-in-time expanding mean of the player's PRIOR same-season "
                            "appearances; cold rows fall back to the league mean over games "
                            "strictly earlier in the same season",
      "skill_definition": "1 - MAE_model / MAE_reference, computed on the RETAINED set",
      "ranking_is_operational": "rows are ranked on the RAW pre-game value with a single pooled "
                                "threshold, not on a within-season rank, so the rule is one a "
                                "production system could actually apply",
      "curves": A.to_dict(orient="records"),
      "per_season_stability_at_75pct_coverage": S.to_dict(orient="records"),
      "operational_thresholds_games_prior": {
          "0.90": 3, "0.80": 6, "0.75": 8, "0.60": 13, "0.50": 17, "0.40": 21, "0.25": 27},
      "games_prior_within_nonfallback_rows_only": SUB.to_dict(orient="records"),
      "composite_fallback_or_thin": COMP.to_dict(orient="records"),
      "nesting_finding": ("is_fallback and pl_games_prior are NESTED, not independent: the fallback "
                          "rate is 29.1% in the bottom games_prior quartile and EXACTLY 0% in the "
                          "other three. The composite rule is therefore identical to games_prior "
                          "alone. But the games_prior gradient SURVIVES inside the non-fallback rows "
                          "(skill 0.0799 -> 0.0966 at 75% coverage -> 0.1069 at 60%), so it is not "
                          "merely a restatement of the fallback flag.")},

  "the_single_most_useful_table": {
      "what": "player-games split into quintiles of pl_games_prior (prior same-season appearances), "
              "with the model's SKILL against the point-in-time prior-mean reference in each",
      "table": pd.read_csv(os.path.join(B.OUT, "depth_quintile_table.csv")).to_dict(orient="records"),
      "reading": ("the pooled minutes skill of +3.6% is an average over a bottom quintile where the "
                  "model is WORSE THAN A NAIVE PRIOR MEAN (skill -15.1%) and four upper quintiles "
                  "where it is worth +3.0%, +10.0%, +11.0%, +10.9%. Points behaves the same way: "
                  "-6.6% in the bottom quintile against +0.4% / +1.6% / +2.3% / +1.6% above it. "
                  "This is GRAPH_POLICY 13.5's claim, in this repo's own numbers: pooled averaging "
                  "was hiding a usable regime behind a harmful one.")},

  "conditioning_check": {
      "question": "do the surviving leads collapse onto one early-season axis?",
      "answer": ("mostly yes, but not entirely. pl_games_prior and tm_game_idx correlate at 0.897, "
                 "and tm_first_meeting / tm_prior_meetings / tm_five_tenure_prior lose almost all "
                 "of their effect once depth and team-game index are held fixed (delta-R2 added "
                 "<= 0.0023 on every target). Three things survive conditioning: "
                 "tm_newfaces_prior (minutes delta-R2 +0.0186), pts__is_fallback (minutes +0.0831) "
                 "and pts__pred_width (points +0.0933)."),
      "file": "run_log_conditioning.txt / lead_correlations.csv / depth_quintile_table.csv"},

  "headline_leads": [
      {"rank": 1, "rule": "abstain on player-games with few PRIOR same-season appearances",
       "candidate": "pl_games_prior (equivalently the artifact's own n_prior_games)",
       "target": "minutes", "correct_null_level": "WITHIN-block", "t": -15.26,
       "p_correct_level": 0.000, "p_familywise_whole_screen": 1.000,
       "practical_spread_abs_residual_minutes": {"worst_decile": 8.454, "best_decile": 4.762,
                                                 "ratio": 0.563},
       "abstention": {"coverage_1.00": {"mae": 5.080, "skill": 0.0355},
                      "coverage_0.75": {"mae": 4.720, "skill": 0.0897, "threshold": ">= 8 prior games"},
                      "coverage_0.60": {"mae": 4.698, "skill": 0.1051},
                      "coverage_0.40": {"mae": 4.685, "skill": 0.1081}},
       "per_season_skill_gain_at_75pct": {"2022": 0.0424, "2023": 0.0515, "2024": 0.0675},
       "reading": "giving up the thinnest-sample quarter of player-games roughly TRIPLES the "
                  "minutes model's skill over a prior-mean reference, from +3.6% to +9.0%, and "
                  "the gain is positive and monotone in every season separately. Note the failure "
                  "of family-wise correction on this specific cell (p_fw = 1.00): its |t| of 15.3 "
                  "is far from the screen's max of 41.6. It is a LEAD on spread, not a "
                  "family-wise-significant cell."},
      {"rank": 2, "rule": "abstain when the model itself fell back off its primary estimator",
       "candidate": "is_fallback / fallback_level", "target": "minutes",
       "correct_null_level": "WITHIN-block", "t": 39.13, "p_correct_level": 0.000,
       "p_familywise_whole_screen": 0.000,
       "practical_spread_abs_residual_minutes": {"worst_decile": 8.657, "best_decile": 4.318,
                                                 "ratio": 2.005},
       "abstention": {"coverage_0.90": {"mae": 4.690, "skill": 0.0784}},
       "per_season_skill_gain_at_75pct": {"2022": 0.0314, "2023": 0.0402, "2024": 0.0403},
       "reading": "the single largest and most family-wise-secure heterogeneity in the screen, and "
                  "it is FREE -- the model already emits the flag. Minutes error doubles on fallback "
                  "rows. But it is nested inside rank 1."},
      {"rank": 3, "rule": "abstain on wide predictive intervals for points",
       "candidate": "pts__pred_width (q95 - q05)", "target": "pts",
       "correct_null_level": "BETWEEN-block", "t": 39.35, "p_correct_level": 0.000,
       "p_familywise_whole_screen": 0.000,
       "practical_spread_abs_residual_pts": {"worst_decile": 5.038, "best_decile": 1.966,
                                             "ratio": 2.562},
       "abstention": {"coverage_1.00": {"mae": 4.191, "skill": -0.0022},
                      "coverage_0.75": {"mae": 3.858, "skill": 0.0128},
                      "coverage_0.50": {"mae": 3.232, "skill": 0.0317},
                      "coverage_0.25": {"mae": 2.517, "skill": 0.0506}},
       "per_season_skill_gain_at_75pct": {"2022": 0.0164, "2023": 0.0106, "2024": 0.0242},
       "reading": "the ONLY pre-game state that turns the points model from negative skill to "
                  "positive skill. Small in absolute terms (+1.3 points of skill at 75% coverage, "
                  "+5.1 at 25%) but positive in all three seasons and monotone in coverage. Note "
                  "that pred_SD does NOT work (skill gain ~0 at every coverage) -- only the "
                  "quantile WIDTH does, which is itself a finding about the v15 uncertainty head."},
      {"rank": 4, "rule": "a debutant played for the team in its last prior game",
       "candidate": "tm_newfaces_prior", "target": "minutes",
       "correct_null_level": "WITHIN-block", "t": 19.27, "p_correct_level": 0.000,
       "p_familywise_absres_family": 1.000,
       "practical_spread_abs_residual_minutes": {"worst_decile": 6.913, "best_decile": 4.478,
                                                 "ratio": 1.544},
       "survives_conditioning_on_depth_and_game_index": True,
       "abstention": {"coverage_0.75": {"mae": 4.753, "skill": 0.0437, "skill_gain": 0.0082}},
       "reading": "the only roster-stability candidate that survives, and the clearest example in "
                  "this screen of a state that predicts ERROR without predicting differential "
                  "SKILL -- the naive reference is almost equally hurt there. Worth a look as a "
                  "VARIANCE feature, not as an abstention rule."}],

  "what_died": {
      "schedule_state": ("rest days, back-to-back, third-in-four, games-in-prior-7-days, opponent "
                         "rest and rest differential: all tiny. Best |t| in the family is well "
                         "under the correct-level noise floor for practical spread; no schedule "
                         "candidate produced a decile ratio outside roughly 0.95-1.10 on any target. "
                         "DATE PROVENANCE: these were computed from AS-PLAYED game dates. There is "
                         "no scheduled-date artifact in this repo (contract_v4.scheduled_tip_time is "
                         "NaT with tip_time_quality='none' for the screened seasons). They are "
                         "as-played fields and are described as such."),
      "opponent_unfamiliarity": "first meeting vs later meetings, and prior-meeting count: nothing.",
      "roster_stability_PARTIAL": (
          "team roster churn between the last two prior games (|t| <= 2.24), starting-five tenure "
          "(|t| <= 8.63, and it points the WRONG way for a stability story) and starting-five "
          "change (|t| <= 3.30) are all null or near-null. tm_newfaces_prior -- the count of "
          "players who DEBUTED for the club in its last prior game -- is the one survivor of the "
          "family and it is NOT an early-season artefact: conditioned on both pl_games_prior and "
          "tm_game_idx it still carries t = +16.35 and delta-R2 +0.0186 on minutes |residual|, "
          "with a worst-vs-best decile of 6.913 vs 4.478 minutes (ratio 1.54). It does NOT, "
          "however, convert into abstention value: its skill gain at 75% coverage is only +0.008 "
          "because the prior-mean reference degrades on those rows almost as much as the model "
          "does. It predicts ERROR without predicting differential SKILL, which is the distinction "
          "that matters for a conditional edge."),
      "role_volatility_as_a_standalone_edge": ("pl_min_sd5 and pl_min_cv5 have large |t| but their "
                                               "abstention curves have NEGATIVE skill gain at every "
                                               "coverage in every season -- they are volume proxies, "
                                               "not error predictors. This is the volume confound "
                                               "caught in the act."),
      "game_context": "home/away is null; team game index / season progress is small and unstable."},

  "complete_case_robustness": CC.to_dict(orient="records"),

  "limitations": [
      "13,879 player-games over three seasons; one arm; no bootstrap; no preregistration.",
      "Only points, minutes and FGA were screenable. The v15 arm emits NO rebound or assist "
      "forecast, so the D051 residual characterisation cannot be completed for those targets "
      "without new generation.",
      "p_active is a declared constant 0.8 and was not screened.",
      "The frame is restricted to rows where the player APPEARED and all three targets are "
      "outcome-scoreable, so nothing here speaks to the did-not-play decision.",
      "Squared-residual dependents are heavy-tailed; their within-block nulls are wide and their "
      "cells should be read only as a sanity companion to the absolute-residual cells.",
      "Within-season median imputation was used for candidates with missing early-season history "
      "(max 10.5% missing); complete-case t-statistics are reported and agree in sign everywhere, "
      "though pl_start_switch5 and pl_dnp_frac5 are noticeably stronger complete-case.",
      "The abstention curves are in-sample to the 2022-2024 exploration partition. They are a "
      "LEAD. Nothing has been validated forward."]
}

with open(os.path.join(B.OUT, "FINDINGS.json"), "w") as fh:
    json.dump(out, fh, indent=2, default=str)
print("wrote FINDINGS.json (%d cells, %d ranked)" % (len(cells), len(rank)))
