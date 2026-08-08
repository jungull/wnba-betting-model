"""E0_I0019 -- s07: assemble FINDINGS.json from the artifacts already on disk.  Computes nothing
new except the leads table, which is a re-read of screen_results_repaired.csv + decile_tables.csv.
"""
import json
import os

import numpy as np
import pandas as pd

import av_base as B

OUT = B.OUT


def rd(name):
    return json.load(open(os.path.join(OUT, name)))


s01 = rd("s01_provenance.json")
s03 = rd("s03_characterisation.json")
s04 = rd("s04_screen.json")
s05 = rd("s05_spreads.json")
s06 = rd("s06_abstention.json")
CJ = rd("candidates.json")
RES = pd.read_csv(os.path.join(OUT, "screen_results_repaired.csv"))
DEC = pd.read_csv(os.path.join(OUT, "survivor_decomposition.csv"))
SPR = pd.read_csv(os.path.join(OUT, "decile_tables.csv"))
head = pd.DataFrame(s03["A_headline"]).set_index("forecast")

rich = RES[(RES["p_familywise"] < 0.05) &
           RES["dependent"].isin(["skill_vs_R3", "llskill_vs_R3"])]
leads = []
for c in sorted(rich["candidate"].unique()):
    sub = rich[rich["candidate"] == c]
    d = DEC[DEC["candidate"] == c]
    g = SPR[SPR["candidate"] == c]
    sgn = RES[(RES["candidate"] == c) & (RES["dependent"] == "signed_err")].iloc[0]
    leads.append(dict(
        candidate=c, family=sub["family"].iloc[0],
        max_abs_t=float(sub["t"].abs().max()),
        p_between=float(sub["p_between"].min()), p_within=float(sub["p_within"].min()),
        within_null_degenerate=bool(sub["within_null_degenerate"].all()),
        p_familywise=float(sub["p_familywise"].min()),
        var_share_between=float(sub["var_share_between"].iloc[0]),
        share_of_skill_gap_explained_by_candidate_itself=(
            float(d["share_of_gap_explained_by_candidate"].iloc[0]) if len(d) else None),
        practical_spread_bss_vs_R3=float(g["bss_vs_R3"].max() - g["bss_vs_R3"].min()),
        bss_vs_R3_worst_decile=float(g["bss_vs_R3"].min()),
        bss_vs_R3_best_decile=float(g["bss_vs_R3"].max()),
        calibration_gap_min=float(g["calib_gap"].min()),
        calibration_gap_max=float(g["calib_gap"].max()),
        calibration_gap_spread=float(g["calib_gap"].max() - g["calib_gap"].min()),
        signed_err_t=float(sgn["t"]), signed_err_p_familywise=float(sgn["p_familywise"])))
LEADS = pd.DataFrame(leads).sort_values("share_of_skill_gap_explained_by_candidate_itself")
LEADS.to_csv(os.path.join(OUT, "leads.csv"), index=False)
print(LEADS.to_string(index=False, float_format=lambda v: "%.4f" % v))

F = {
 "screen_id": "E0_I0019_availability_forecast",
 "tier": "E0 DISCOVERY -- fast, permissive, time-boxed, EXPLICITLY NON-CLAIMING. A LEAD, NEVER A RESULT.",
 "question": ("`p_active` -- the arm's predicted probability that a player appears at all -- had "
              "never been characterised. D076 enumerated the arm's targets as points/minutes/FGA "
              "and omitted it. Is it point-in-time? How good is it? Where is it systematically "
              "wrong? Does it add anything to D076's abstention rule?"),
 "partition": {"allowed": [2021, 2022, 2023, 2024], "screened": [2022, 2023, 2024],
               "why_2021_excluded": "fold is DEGENERATE in BOTH arms: n_train_rows=0, "
                                    "model_was_fitted=false, declared-constant only",
               "holdout_never_touched": [2025, 2026]},

 "STEP_1_PROVENANCE": {
   "verdict": s01["J_verdict"],
   "checks": s01["J_checks"],
   "receipts": {
     "walk_forward": "season S fitted only on seasons < S, both arms; train_seasons asserted "
                     "strictly prior for every fold",
     "fold_boundary_receipt_ok": True, "provenance_history_receipt_ok": True,
     "own_outcome_never_informed_its_forecast": True,
     "forecast_scored_against_outcome": False, "evaluation_metric_calculated": False},
   "artifact_granularity_question": {
     "screenkit_check_manifest_status": "UNUSABLE (asof_granularity='artifact') -- CORRECT as a "
                                        "generic verdict, and NOT overridden lightly",
     "what_this_screen_verified_instead": ("every row_uid in each per-season p_active file was "
                                           "joined to the manifest-carrying contract v4 and the "
                                           "resulting season and game_date VALUES were asserted "
                                           "equal to the file's own season. 2022 -> [2022] "
                                           "2022-05-08..2022-09-18; 2023 -> [2023] "
                                           "2023-05-21..2023-10-18; 2024 -> [2024] "
                                           "2024-05-16..2024-10-20. D076's reasoning is therefore "
                                           "VERIFIED rather than inherited."),
     "forecast_cutoff_precedes_the_game_on": "17809/17809 rows, both arms, 0 violations"},
   "leak_probes": {
     "probe1_cold_start_single_pooled_constant_D076s": s01["E_probe1_cold_start"],
     "probe2_tracks_prior_more_than_future_D076s": s01["F_probe2_prior_vs_future"],
     "probe3_within_stratum_AUC_own_design": s01["G_probe3_within_stratum_auc"],
     "probe4_v4_leadlag_profile_peak_own_design": s01["H3_probe4_v4_profile_peak_sign_test"],
     "probe5_fold_identity_hashes": s01["I_probe5_hashes"]},
   "probe4_was_redesigned_THREE_TIMES_see_DEFECTS_md": {
     "v1_absolute_threshold": s01["H_probe4_v1_absolute_threshold_FAILED"],
     "v2_bracketed_contrast_WITHDRAWN": s01["H_probe4_v2_bracketed_contrast_WITHDRAWN"]["_status"],
     "v3_spike_threshold_WITHDRAWN":
        s01["H2_probe4_v3_leadlag_spike_THRESHOLD_WITHDRAWN"]["_status"],
     "v4_final_is_a_SIGN_TEST_with_no_tunable_constant": True,
     "disclosure": "This is the place this screen could most easily have cheated. See DEF-1, "
                   "DEF-1b, DEF-1c. All three failing versions' scripts, logs and numbers are on "
                   "disk unaltered."},
   "forbidden_artifacts_not_opened": s01["B_forbidden"],
   "availability_rebuilt_from": "master_player box membership (minutes > 0), as D076 did; "
                                "agreement with contract v4 `appeared` = 1.000000 on 17,809 rows"},

 "STEP_2_HOW_GOOD_IS_IT": {
   "n_rows": 17809, "seasons": [2022, 2023, 2024], "base_rate_appeared": 0.7793,
   "headline": s03["A_headline"],
   "plain_language": {
     "discrimination": "v15 p_active AUC 0.9016 (v14 0.8958). It ranks who will play very well.",
     "calibration": ("ECE 0.0338 on 20 bins; the reliability term is 0.00182 of a Brier score of "
                     "0.0922, i.e. about 2% of the total error is miscalibration. It is close to "
                     "calibrated OVERALL but has a systematic S-SHAPE, described below."),
     "skill_vs_a_naive_base_rate": "Brier skill +46.4% -- but that is a trivially weak reference.",
     "skill_vs_a_per_player_prior_rate": "+24.5%",
     "skill_vs_a_shrunk_career_prior_rate": "+38.5%",
     "skill_vs_a_RICH_walkforward_lookup_R3": ("+7.1% ONLY. This is the number that matters. R3 "
                                               "is a non-parametric table of the appearance rate "
                                               "by (career prior rate x consecutive absences x "
                                               "depth), estimated on strictly prior seasons. "
                                               "p_active beats it, but by 7%, not by the 39% a "
                                               "weaker reference suggests.")},
   "clustered_paired_tests": s03["C_paired"],
   "calibration_S_shape": s03["E_coarse_calibration"],
   "sharpness": s03["F_sharpness"],
   "decomposition_against_own_components_REFITTED": s03["G_decomposition"]},

 "STEP_3_WHERE_IS_IT_SYSTEMATICALLY_WRONG": {
   "design": {"candidates": len(CJ["candidates"]), "dependents": len(CJ["dependents"]),
              "cells": CJ["n_cells"], "candidate_list_sha256": CJ["candidate_hash"],
              "dependent_list_sha256": CJ["dependent_hash"],
              "added_since_hash": 0, "dropped_since_hash": 0,
              "n_permutation_draws": s04["n_draws"]},
   "nulls": {"correct_level_maxt_null": {"mean": s04["maxt_correct_mean"],
                                         "q95": s04["maxt_correct_q95"],
                                         "max": s04["maxt_correct_max"]},
             "NAIVE_row_maxt_null": {"mean": s04["maxt_row_mean"], "q95": s04["maxt_row_q95"],
                                     "max": s04["maxt_row_max"]},
             "family_wise_bar_correct_vs_naive": [s04["maxt_correct_q95"], s04["maxt_row_q95"]],
             "per_cell_sd_inflation_median": s04["per_cell_inflation_median"],
             "noop_placebo": s04["noop_placebo"]},
   "attrition": s05["attrition"],
   "leads_surviving_family_wise_against_the_RICH_reference": LEADS.to_dict("records"),
   "schedule_family": {"cells": s05["schedule_family"]["cells"],
                       "max_abs_t": s05["schedule_family"]["max_abs_t"],
                       "familywise_survivors": s05["schedule_family"]["familywise_survivors"],
                       "verdict": "DEAD AGAIN. 0 of 30 cells clear family-wise; max |t| 4.43 "
                                  "against a family-wise bar of 8.68. Back-to-backs, 3-in-4, "
                                  "rest days, games in the prior 7 days and home/away all die. "
                                  "This is the SAME dead family in new clothes, on a genuinely "
                                  "different target."},
   "roster_churn_family": {"verdict": "DEAD. 0 of 30 cells clear family-wise, max |t| 8.01."},
   "season_phase_contention_family": {"verdict": "DEAD. 0 of 30 cells clear family-wise, "
                                                 "max |t| 7.25."},
   "negative_controls": {"surviving_family_wise": 0,
                         "note": "neg_ctrl_player_noise reached p_row = 0.0020 on llskill_vs_R3 "
                                 "under the NAIVE row null and p = 0.068 under the correct "
                                 "player-block null -- the control did its job."}},

 "STEP_4_INTERACTION_WITH_THE_ABSTENTION_RULE": {
   "minutes_pooled_reproduction_of_D076": s06["minutes_pooled"],
   "minutes_abstention_curves": s06["minutes_abstention"],
   "p_active_within_D076_depth_quintiles": s06["within_depth_quintiles"],
   "axis_correlation": s06["axis_correlation"],
   "verdict": ("NO. p_active does NOT improve D076's abstention trade-off. Ordering by depth "
               "gives minutes skill +0.0355 -> +0.0902 at 75% coverage -> +0.1048 at 60%; "
               "ordering by any p_active-derived rule tops out at +0.0747 at 75%. COMBINING the "
               "two ranks is WORSE than depth alone (+0.0852 vs +0.0902 at 75%). Inside depth "
               "quintiles, p_active buys +0.046 in the thinnest quintile ONLY -- and skill there "
               "is still NEGATIVE (-0.151 -> -0.105) -- and is zero or negative in the other "
               "four. They are very largely the same rule wearing two names."),
   "availability_side_abstention": s06["availability_abstention"],
   "void_risk_bands": s06["void_risk"]},

 "SELF_IDENTIFIED_DEFECTS": {
   "file": "DEFECTS.md (written incrementally, at the moment of discovery)",
   "DEF_1_1b_1c": "probe 4 was redesigned three times after failing; every version preserved",
   "DEF_2": "v15's declared row universe (prediction_contract_v5) has ZERO manifests, so 3,808 "
            "v15 p_active forecasts on tiers B_s2_weak_fallback / B_transaction_sensitivity are "
            "DROPPED. Those tiers are the marginal-roster rows where availability is hardest, so "
            "this screen's coverage of the hard cases is narrower than the arm's.",
   "DEF_3": "check_manifest returns UNUSABLE on p_active and that verdict is CORRECT; the screen "
            "overrides it only on the value-level evidence in s01C, and logs the override.",
   "DEF_4": "I mislabelled max(p_between, p_within) as 'the p at the correct level'. Caught by an "
            "arithmetic impossibility in my own output. Repaired in s05; family-wise numbers "
            "unchanged, per-cell labelling was wrong."},

 "KIT_FEEDBACK": {
   "kit_version_used": "_screen_kit (D077/D082/D086), 159 assertions",
   "defects_found_in_the_kit": "NONE. Every kit function behaved as documented.",
   "ergonomics_confirmed": [
     "check_manifest's verdict field is `status` -- confirmed, and used.",
     "A misspelled key returns None silently -- CONFIRMED AND IT COST ME A RUN. "
     "`paired_forecast_comparison` returns `dr2_a_minus_b` and `p`; I asked for `dr2` and "
     "`p_value` via .get(default) and got a full table of NaN that LOOKED like a legitimate "
     "degenerate result rather than a typo. The screen now asserts every key it reads is "
     "present. SUGGESTION: a `strict_get` helper, or returning a mapping that raises on unknown "
     "keys, would have turned a silent wrong answer into an immediate error."],
   "positive_notes": [
     "assert_partition's value gates fired correctly and informatively on THREE season-named and "
     "ONE date-named column in this screen's own frame (tm_season_progress, "
     "pl_prior_rate_inseason, pl_prior_season_games, candidate_at_cutoff) -- the K0 repair is "
     "doing real work here, not hypothetically.",
     "detect_grouping_level returned None + NO_COARSER_LEVEL_EXISTS for exactly the 35 "
     "row-varying player-level candidates and named team_game for the 15 team-level ones. The P2 "
     "repair meant I could not accidentally pipe 'row' into a null.",
     "noop_placebo returned sd = 0.0 exactly with n_distinct_draw_values = 1, and correctly "
     "verdicted CONFIRMED NO-OP."]},

 "WHERE_I_COULD_HAVE_CHEATED": [
   "PROBE 4, THREE TIMES (the big one) -- see DEF-1/1b/1c. I redesigned a provenance gate after "
   "watching it fail. Mitigations: every version on disk, each withdrawal names a confound "
   "documented in screenkit K1, the final criterion is a SIGN with no free parameter, it fires "
   "on an injected 10% leak, and four other probes passed on their first pre-registered form.",
   "THE RICH REFERENCE R3's BIN EDGES were chosen by me before seeing any result, but they were "
   "not pre-registered in a hashed artifact the way the candidate list was. A different binning "
   "would move the 7.1% headline skill number. The edges are in s02_build_candidates.py.",
   "PSEUDO_K = 5 for every Beta-shrunk quantity was declared a priori and never tuned, but it was "
   "also never sensitivity-tested. It affects R2 and R3 and therefore the skill headline.",
   "THE SEASON FIXED EFFECT is itself a retrospective statistic. It is applied identically to the "
   "model, to every reference and to every permutation draw, so it cannot manufacture a "
   "differential -- but it IS a full-season quantity inside the inference machinery, which is "
   "exactly the door D085's sixth instance came through, and it is named in the TIME-WINDOW "
   "TABLE for that reason.",
   "I CHOSE the player-season as the clustering unit for paired_forecast_comparison on the "
   "argument that appearance decisions are serially correlated within a player-season. That is a "
   "judgement, not a measurement. A coarser unit (team-season) would widen the null.",
   "3,808 v15 forecasts were dropped for lack of a manifested row universe (DEF-2), and they are "
   "disproportionately the hard rows. Every number here is conditional on that exclusion."],

 "NON_CLAIMS": [
   "This is E0. Nothing here is a result. The leads below are leads.",
   "No model was fitted or retrained. References were CONSTRUCTED; the only regressions are the "
   "screen's own FWL slope t-statistics and the deliberately-generous in-sample augmented "
   "reference used for the decomposition test.",
   "`p_active` was never scored inside the arm (scores_computed=false, "
   "evaluation_metric_calculated=false in every manifest and receipt). This screen is the FIRST "
   "time it has been scored against its outcome, so every number here is new and unreplicated.",
   "Rebound and assist availability are not covered because no such forecast exists in the arm.",
   "2025 and 2026 were never read, joined, plotted or described."],
}
json.dump(F, open(os.path.join(OUT, "FINDINGS.json"), "w"), indent=2, default=str)
print("\nwrote FINDINGS.json")
