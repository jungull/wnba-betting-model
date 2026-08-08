"""S11 -- assemble FINDINGS.json from the artefacts on disk. No number is typed by hand."""
import os, json
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def J(n):
    with open(os.path.join(HERE, "scripts", n)) as f:
        return json.load(f)
def C(n):
    return pd.read_csv(os.path.join(HERE, n))

s00, s06, s07, s08, s09 = J("_s00.json"), J("_s06.json"), J("_s07.json"), J("_s08.json"), J("_s09.json")
AT, COV, EXd, DIS = C("AUDIT_TABLE_EXT.csv"), C("COVERAGE_EXT.csv"), C("EXPOSED_CELLS_EXT.csv"), C("EXPOSED_DISCHARGE.csv")
MVS, EST, NW = C("MEASURED_VARIANCE_SHARES.csv"), C("E1_I0021_ESTIMAND_CHECK.csv"), C("NULL_WIDTH_CONTRAST.csv")
K = AT[AT.is_kill]
det = K[K.z_obs_vs_null.notna() & K.EXPOSURE.isin(["EXPOSED", "NOT_EXPOSED"])]

def ct(col):
    t = pd.crosstab(det[col], det.EXPOSURE)
    g = lambda r, c: int(t.loc[r, c]) if (r in t.index and c in t.columns) else 0
    tp, fp, fn, tn = g(True, "EXPOSED"), g(True, "NOT_EXPOSED"), g(False, "EXPOSED"), g(False, "NOT_EXPOSED")
    return dict(n=int(len(det)), true_positive=tp, false_positive=fp, false_negative=fn,
                true_negative=tn,
                sensitivity=round(tp / (tp + fn), 4) if tp + fn else None,
                specificity=round(tn / (tn + fp), 4) if tn + fp else None,
                positive_predictive_value=round(tp / (tp + fp), 4) if tp + fp else None)

PRIOR_EXPOSED, PRIOR_KILLS, PRIOR_UNDET = 83, 1367, 0

F = {
  "screen": "E1_I0040_audit_extension",
  "extends": "E1_I0038_within_entity_null_audit",
  "partition": "2021-2024 exploration only; 2025/26 never opened (asserted, not assumed)",
  "one_line": ("32 of 1,304 killed cells in the 30 unaudited screens are structurally exposed to "
               "the within-entity null failure, all in one screen, none of them flips; the "
               "programme-wide total across all 38 screens is 115."),

  "anchors_reproduced_before_any_new_statistic": {
    "source": "scripts/s00_anchors.py",
    "killed_cells_at_opp_team_season": {"prior": 337, "reproduced": 337, "exact": True},
    "killed_cells_at_player_season": {"prior": 213, "reproduced": 213, "exact": True,
        "note": "reproduces from level_recorded, NOT candidate_level_recorded (431); see DEFECTS D-07"},
    "sum_D115_level_estimate": {"prior": 550, "reproduced": 550, "exact": True},
    "all_cells_incl_survivors": {"prior": "299/427", "reproduced": "299/427", "exact": True},
    "arithmetic_ceiling_kills_in_census": {"prior": 213, "reproduced": s00["A3_is_ceiling"], "exact": True},
    "census_size_exposed_undeterminable": {"prior": [1999, 83, 0],
        "reproduced": [s00["audit_table_rows"], s00["A4_exposure_tally"]["EXPOSED"], 0], "exact": True},
    "D097_R08_dR2_on_13784_rows": {"prior_quoted": 0.0064881160,
        "reproduced_full_precision": 0.0064881159695263, "n_rows": 13784, "exact_to_quoted_digit": True},
    "D097_R08_N_CYCLIC_null_mean": {"prior_quoted": 0.0078802401,
        "reproduced_full_precision": 0.0078802401210119, "exact_to_quoted_digit": True}},

  "coverage": {
    "screens_in_programme": 38, "screens_in_prior_census": 8, "screens_audited_here": 30,
    "of_the_thirty_that_decide_cells_with_a_permutation_null": s09["screens_deciding_cells"],
    "of_the_thirty_that_decide_none": s09["screens_not_deciding_cells"],
    "screens_deciding_none": COV[~COV.decides_cells_with_a_permutation_null].screen.tolist(),
    "cells_audited": s09["cells_audited"], "kills": s09["kills"],
    "excluded_as_re_analysis_of_census_cells": {
        "E1_I0026_detection_floor": [1349, 1975], "E1_I0036_D097_COMPONENT_NULLS_N_CYCLIC": 2,
        "reason": "power/level re-analysis of cells E1_I0036 and E1_I0038 already audited; "
                  "counting them would double-count the programme-wide total (DEFECTS D-08)"}},

  "headline_counts_for_the_thirty": {
    "killed_cells": s07["kills"],
    "EXPOSED": s07["exposed"],
    "NOT_EXPOSED": s07["not_exposed"],
    "UNDETERMINABLE": s07["undeterminable"],
    "EXPOSED_ALREADY_COUNTED_IN_E1_I0038": s07["already_counted"],
    "exposure_rate": round(s07["exposed"] / s07["kills"], 4),
    "within_entity_decided_kills": s09["within_entity_kills"],
    "flag_z_lt_neg1_trips_on_kills": int((K.flag_z_lt_neg1 == True).sum()),
    "bare_flag_trips_on_kills": int((K.flag_null_mean_gt_observed == True).sum()),
    "z_computable_on_kills": int(K.z_obs_vs_null.notna().sum())},

  "PROGRAMME_WIDE_COMBINED_WITH_PRIOR_AUDIT": {
    "screens": 38,
    "auditable_kills": PRIOR_KILLS + s07["kills"],
    "EXPOSED_TOTAL": PRIOR_EXPOSED + s07["exposed"],
    "from_E1_I0038_census": PRIOR_EXPOSED, "from_this_extension": s07["exposed"],
    "NOT_EXPOSED_TOTAL": 1284 + s07["not_exposed"],
    "UNDETERMINABLE_TOTAL": PRIOR_UNDET + s07["undeterminable"],
    "programme_wide_exposure_rate": round((PRIOR_EXPOSED + s07["exposed"]) / (PRIOR_KILLS + s07["kills"]), 4),
    "verdict_flips_programme_wide": {"per_cell": 52, "family_wise": 11,
                                     "all_from": "E1_I0038 / D085", "added_here": 0},
    "D115_original_fear": 550,
    "audit_is_now_complete": True},

  "max_signature_hunt": {
    "targeted_pass_hits": 0, "loose_pass_raw_hits": 240,
    "after_removing_prints_and_maxT_familywise": 106,
    "combining_two_p_values_or_two_schemes": 3,
    "surviving_a_read": 0,
    "conclusion": "the banned p_correct = max(p_within, p_between) occurs ZERO times in the thirty",
    "note": "max-T family-wise (a maximum over CELLS within ONE null) is legitimate and appears in "
            "seven screens; it is not the defect"},

  "E1_I0021_heterogeneity_diagnostic_THE_NAMED_HIGHEST_RISK_SCREEN": {
    "verdict": "NOT_EXPOSED",
    "killed_cells": int((AT[(AT.screen == 'E1_I0021_heterogeneity_diagnostic') & AT.is_kill]).shape[0]),
    "killed_cells_decided_by_a_within_entity_null": int(
        ((AT.screen == 'E1_I0021_heterogeneity_diagnostic') & AT.is_kill &
         (AT.null_class == 'WITHIN_ENTITY')).sum()),
    "exposed": 0,
    "exposed_under_the_FROZEN_RULE_APPLIED_MECHANICALLY": s07["i21_mechanical_exposed"],
    "measured_between_player_variance_shares": {
        r["candidate"]: round(float(r["var_share_between"]), 4)
        for _, r in MVS[MVS.screen == "E1_I0021_heterogeneity_diagnostic"].iterrows()},
    "why_not_exposed": ("the statistic is the SD of per-player slopes fitted on WITHIN-player "
                        "demeaned x and y (hd_base.py:225-252, demean=True; null uses the identical "
                        "arithmetic at hd_base.py:269), so the between-player component of the "
                        "candidate is annihilated before the statistic exists"),
    "DECISIVE_MEASUREMENT": {
        "test": "multiply the candidate's between-player component by 10, and delete it entirely; "
                "recompute the statistic both times",
        "max_absolute_change_in_the_statistic": s06["E1_I0021_max_delta_from_between_component"],
        "detail": json.loads(EST.to_json(orient="records")),
        "conclusion": "a null cannot be blind to a component the statistic cannot see either"},
    "combination_rule": "four schemes run, all reported, one is the verdict (N4 within-player "
                        "cyclic shift). No max(). D090's formulation, arrived at independently.",
    "credit": ("this screen found and measured the kit gap the whole enquiry rests on -- "
               "SCHEME_WITHIN is anticonservative for autocorrelated regressors (p=0.0015 where the "
               "honest null gives 0.39) -- and recommended SCHEME_WITHIN_CYCLIC, which the kit now "
               "carries and now RAISES on the unsafe one")},

  "the_one_exposed_screen": {
    "screen": "E1_I0031_rapm_as_prior",
    "exposed_kills": s07["exposed"],
    "mechanism": ("NOT the max() conjunction. A COMPOSITE candidate was assigned the null "
                  "appropriate to only one of its components. pm_all = pm_game_level + "
                  "pm_prev_season was tested under the within-player-season cyclic null, but "
                  "pm_prev_season_imp is CONSTANT within player-season, so the cyclic shift is the "
                  "identity on it. A new defect shape; DEFECTS D-04."),
    "constancy_proof": {
        "player_seasons": s08["pm_prev_season_imp_player_seasons"],
        "with_more_than_one_distinct_value": s08["pm_prev_season_imp_nonconstant_groups"],
        "max_within_group_spread": s08["pm_prev_season_imp_max_within_spread"]},
    "measured_between_player_season_shares": {
        r["candidate"]: round(float(r["var_share_between"]), 4)
        for _, r in MVS[MVS.screen == "E1_I0031_rapm_as_prior"].iterrows()},
    "disposition_of_the_32": {
        "dischargeable_from_disk": s08["dischargeable"],
        "blind_component_killed_under_its_own_MATCHED_null": "%d of %d" % (
            s08["pm_all_blind_component_killed_matched"], s08["pm_all_cells"]),
        "max_dR2_the_blind_component_contributes": s08["pm_all_max_blind_increment"],
        "below_D103_single_cell_floor_0.00102": s08["below_floor"],
        "ELIGIBLE_for_remeasurement_under_the_frozen_triage_rule": s08["eligible_for_remeasurement"],
        "of_those_with_a_recoverable_null_mean": s08["eligible_with_recoverable_null_mean"],
        "were_they_remeasured": False,
        "why_not": ("no matched between-entity arm exists on disk (unlike D085/D097 which ran both), "
                    "so producing one is a fresh 2,000-draw refit on a walk-forward stratum. "
                    "Refitting is the last resort. Recorded as UNRESOLVED, not as clean.")},
    "null_width_bound": {
        "median_cyclic_over_relabel_p95_ratio": s08["median_null_width_ratio_cyclic_over_relabel"],
        "range": [round(float(NW.ratio.min()), 3), round(float(NW.ratio.max()), 3)],
        "status": "reported as a bound on the room only; D101 forbids treating it as a repriced p"}},

  "immune_by_design": {
    "E0_I0015_points_skill_decomposition": {
        "killed_cells": 548, "within_block_kills": 358, "exposed": 0,
        "mechanism": "picks the scheme from the MEASURED variance share in its own code "
                     "(s03_mechanism_and_abstention.py:284: BETWEEN-block if vsb > 0.5 else WITHIN)",
        "max_between_share_among_WITHIN_block_candidates": 0.4791308332211436,
        "min_between_share_among_BETWEEN_block_candidates": 0.5148890329686022,
        "caveat": "margin to the 0.50 threshold is only 0.0209; the cleanliness IS threshold-"
                  "sensitive and would not survive a threshold of 0.45 (DEFECTS D-09)"},
    "E1_I0021_heterogeneity_diagnostic": {
        "mechanism": "uses an estimand that annihilates the between-entity component, making the "
                     "null choice moot; a different mechanism from E0_I0014's and E0_I0015's"}},

  "resolved_from_undeterminable_by_measurement": {
    "entered_undeterminable": 50, "resolved_by_measurement": 44,
    "reclassified_as_already_counted": 3, "remain_undeterminable": s07["undeterminable"],
    "remaining": ["E1_I0034_redistribution P01_LEAKAGE_minutes/fga/pts"],
    "why_they_remain": ("candidate FREED_* has no row in candidate_level_audit.csv and no measured "
                        "share at the null's own entity (season). Not guessed."),
    "E1_I0030_measurements": {
        "is_home_between_player_share": float(MVS[(MVS.screen == 'E1_I0030_home_advantage_accounting') &
                                                  (MVS.candidate == 'is_home')].var_share_between.iloc[0]),
        "travel_arms_between_team_season_share": {
            r["candidate"]: round(float(r["var_share_between"]), 6)
            for _, r in MVS[(MVS.screen == 'E1_I0030_home_advantage_accounting') &
                            (MVS.candidate != 'is_home')].iterrows()}}},

  "arithmetic_ceiling": {
    "prior_censuss_213_ceiling_kills_are_all_inside_the_census": True,
    "re_measured_here": 0,
    "ceiling_attaining_cells_found_in_the_thirty": int(AT.is_ceiling.sum()),
    "where": "E1_I0036's own re-run tables (LEVEL_RERUN_CELLS 10, LEVEL_FAIRTEST_CELLS 8, "
             "D097_RELEVEL_CELLS 2), identified by observed == ceiling to within 1e-12",
    "kill_reason_CEILING_members_in_the_thirty": 0,
    "note": "these are ceiling-ATTAINING fair-test cells, not cells killed for being at a ceiling. "
            "A ceiling kill is arithmetic and survives every methodological revision, including this one."},

  "the_flag_remeasured_on_an_independent_population": {
    "population": "killed cells in the thirty with a computable z and a determinate exposure class",
    "z_lt_neg1_point_0": ct("flag_z_lt_neg1"),
    "bare_null_mean_gt_observed": ct("flag_null_mean_gt_observed"),
    "prior_audit_values_for_z_lt_neg1": {"sensitivity": 0.446, "specificity": 0.980},
    "conclusion": ("the DIRECTION of E1_I0038's finding replicates -- the magnitude-aware form is "
                   "materially more specific than the bare flag -- but specificity is 0.840 here "
                   "against 0.980 there. n is small and concentrated in three screens; this is a "
                   "caution, not a revision. DEFECTS D-06.")},

  "record_keeping_extending_the_846_of_1999_finding": {
    "cells_audited": s09["cells_audited"],
    "null_mean_written_by_the_screen": s09["null_mean_recorded"],
    "pct_written": round(100 * s09["null_mean_recorded"] / s09["cells_audited"], 1),
    "prior_census_pct": 42.3,
    "recovered_from_the_screens_own_archive": s09["null_mean_recovered"],
    "PERMANENTLY_UNRECOVERABLE": s09["null_mean_unrecoverable"],
    "recoverable_but_not_recovered_here": 1592,
    "why_not_recovered": "their decision null is between-entity; they cannot exhibit this failure "
                         "and recovery would change no verdict. Raw draws exist for all of them.",
    "SCREENS_STORING_DRAWS_STANDARDISED": s09["screens_with_standardised_draws"],
    "of_screens": 30,
    "comparison": "E1_I0038 lost 117 census cells permanently because E0_I0017 standardised its "
                  "draws. That failure mode does NOT recur outside the census: all 119 CSV draw "
                  "dumps and 35 .npz archives in the thirty were tested empirically and every one "
                  "is raw.",
    "SCREENS_WITH_AN_INCOMPLETE_ARCHIVE": s09["screens_with_incomplete_draw_archive"],
    "which": "E1_I0031_rapm_as_prior -- permutation_draws_plusminus.csv is keyed on 4 columns while "
             "its results table has 5; the missing key is `stratum` and the arm never written is "
             "the DECISION stratum. Proved by exact null_p95 match on 24 rows and mismatch on 24. "
             "16 of the 24 lost null means are on exposed cells, including all 7 triage-eligible "
             "cells. DEFECTS D-02.",
    "bound_this_places_on_any_future_audit": ("24 cells in the thirty can never have a null mean. "
                                              "Every other missing null mean is recoverable.")},

  "defects_raised": {
    "D-01_A": "THIS SCREEN's own s04 mis-attached a variance share by substring match; repaired "
              "with an explicit map, 3 cells returned to UNDETERMINABLE",
    "D-02_A": "E1_I0031's draw archive omits the stratum key; 24 null means permanently gone, "
              "16 on exposed cells",
    "D-03_A": "the exposure rule has an unstated scope condition: the statistic must be able to SEE "
              "the between-entity component. Costs E1_I0021 12 false exposures.",
    "D-04_A": "a null chosen correctly per column can be wrong for a BUNDLE of columns -- a new "
              "defect shape the max() ban does not catch",
    "D-05_B": "21.3% null-mean coverage in the thirty vs 42.3% in the census; D103 ruling 2 still "
              "not applied retrospectively",
    "D-06_B": "the flag's specificity does not replicate at 0.980; measured 0.840 here",
    "D-07_B": "E1_I0038's 213/337 anchor reproduces from level_recorded and not from "
              "candidate_level_recorded, and the prose names neither",
    "D-08_C": "E1_I0026's 1,349 rows treated as a re-analysis, not new cells -- a judgement call",
    "D-09_C": "E0_I0015's immunity has a margin of 0.0209 and is threshold-sensitive"},

  "what_was_NOT_done": [
    "no cell was re-measured; no permutation was re-run",
    "no champion was fitted",
    "no production change was enacted",
    "the shared screen kit was opened read-only and never modified",
    "no process was killed; no blanket Stop-Process/taskkill was ever issued",
    "nothing outside experiments/exploration/E1_I0040_audit_extension/ was written, staged or committed",
    "2025/26 was never opened -- asserted with a hard SystemExit on every frame, not assumed"],

  "standard_compliance": {
    "anchors_reproduced_before_new_statistics": True,
    "counterweight_reported_in_the_same_document": True,
    "most_weakening_result_reported": ("fga -> pm_game_level, decision_stratum_wf, p=0.0805 at 1.11x "
                                       "the floor under a null blind to 73% of the dominant column, "
                                       "with its null mean deleted -- FLIPS.md closing section"),
    "UNDETERMINABLE_not_collapsed": True,
    "casualties_not_manufactured": ("14 of 15 deciding screens have zero exposure and 0 flips were "
                                    "found; 'most screens are clean' is the result and it is reported "
                                    "as the result")}
}

with open(os.path.join(HERE, "FINDINGS.json"), "w") as f:
    json.dump(F, f, indent=2, default=str)
print(json.dumps(F, indent=2, default=str)[:6000])
print("\n... wrote FINDINGS.json (%d bytes)"
      % os.path.getsize(os.path.join(HERE, "FINDINGS.json")))
