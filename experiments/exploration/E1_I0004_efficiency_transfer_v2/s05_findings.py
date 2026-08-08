"""STEP 5 -- assemble FINDINGS.json from the per-step JSONs actually written to disk.

Adds one thing not computed earlier: the LEVER DECOMPOSITION, which is the clearest statement of
why the ceiling is what it is.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etv2_base as E  # noqa: E402

pd.set_option("display.width", 260)


def J(n):
    return json.load(open(os.path.join(E.HERE, n)))


s01, s02, s03, s03b, s04 = J("_s01.json"), J("_s02.json"), J("_s03.json"), J("_s03b.json"), \
    J("_s04.json")
s06 = J("_s06.json")
f = pd.read_parquet(os.path.join(E.HERE, "eff_frame_v2.parquet"))
on = f[f["stratum"] & np.isfinite(f["S_SPEC_RA"])]

E.hdr("S05 -- LEVER DECOMPOSITION on the decision-relevant stratum")
lev = dict(
    n=int(len(on)),
    sd_RA_OCc_centred_allowance=float(on["RA_OCc"].std(ddof=1)),
    mean_RA_w_player_prior_rim_share=float(on["RA_w"].mean()),
    point_value_RA=2.0,
    lambda_D074_transfer_slope=E.LAMBDA_D074,
    mean_fga_forecast=float(on["fga__pred_point"].mean()),
    sd_points_response=float(on["y_pts"].std(ddof=1)))
lev["implied_points_per_attempt_per_1sd"] = (
    lev["lambda_D074_transfer_slope"] * lev["point_value_RA"]
    * lev["sd_RA_OCc_centred_allowance"] * lev["mean_RA_w_player_prior_rim_share"])
lev["implied_points_per_game_per_1sd"] = (lev["implied_points_per_attempt_per_1sd"]
                                          * lev["mean_fga_forecast"])
lev["measured_points_per_game_per_1sd"] = float(
    (on["fga__pred_point"] * on["S_SPEC_RA"]).std(ddof=1))
lev["as_fraction_of_response_sd"] = (lev["implied_points_per_game_per_1sd"]
                                     / lev["sd_points_response"])
for k, v in lev.items():
    print("  %-46s %s" % (k, ("%+.6f" % v) if isinstance(v, float) else v))
print("""
  THE WHOLE LEAD IN ONE LINE.  A one-standard-deviation better/worse rim-conversion opponent is
  %.4f in centred allowance.  Multiplied by D074's transfer slope (%.4f), the 2 points a rim
  make is worth, and the share of the player's prior attempts that are at the rim (%.3f), that is
  %.5f points PER ATTEMPT -- and over a typical %.2f-attempt game, %.4f POINTS.  The points
  response sd is %.2f.  The lever is %.2f%% of a response sd.""" % (
    lev["sd_RA_OCc_centred_allowance"], lev["lambda_D074_transfer_slope"],
    lev["mean_RA_w_player_prior_rim_share"], lev["implied_points_per_attempt_per_1sd"],
    lev["mean_fga_forecast"], lev["implied_points_per_game_per_1sd"],
    lev["sd_points_response"], 100 * lev["as_fraction_of_response_sd"]))

CT = pd.DataFrame(s03["contrast_table"])
PT = pd.DataFrame(s04["points_contrast"])


def cell(df, **kw):
    q = df.copy()
    for k, v in kw.items():
        q = q[q[k] == v]
    return q.iloc[0].to_dict()


head_on = cell(CT, response="ppm_points_per_minute", spec="SPEC_RA", stratum="on_stratum")
head_off = cell(CT, response="ppm_points_per_minute", spec="SPEC_RA", stratum="off_stratum")
head_all = cell(CT, response="ppm_points_per_minute", spec="SPEC_RA", stratum="all")
pts_on = cell(PT, spec="SPEC_RA", stratum="on_stratum")
ceil_on = [r for r in s04["arithmetic_ceiling"]
           if r["spec"] == "SPEC_RA" and r["stratum"] == "on_stratum"][0]

F = {
  "screen": "E1_I0004_efficiency_transfer_v2",
  "idea": "I0004 CONVERSION channel -> player EFFICIENCY -> player POINTS",
  "date": "2026-08-08",
  "retry_of": {
    "directory": "experiments/exploration/E1_I0004_efficiency_transfer",
    "why": "predecessor killed mid-run by an API error (GRAPH_POLICY 12, infrastructure event)",
    "reuse": "et_base.py and the s00-s04 scripts were read AS SCAFFOLDING; NO number, contrast, "
             "p-value or verdict from that directory is reused. Every contrast rebuilt.",
    "inherited_defect_fixed": "the opponent conversion allowance is now CENTRED against the "
                              "point-in-time league prior zone-minus-pooled gap before any "
                              "contrast is computed"},

  "VERDICT": "KILL",
  "one_line": (
    "NO. The centred opponent zone-conversion-allowance signal does NOT improve a point-in-time "
    "forecast of player efficiency on the decision-relevant stratum: paired dR2 = %+.6f "
    "(candidate minus champion) at cluster-level p = %.4f (opponent-team-season, 36 clusters), "
    "and the sign is NEGATIVE. It also fails off the stratum (%+.6f, p=%.4f), so there is no "
    "cold-start-only consolation either. The channel is closed on ARITHMETIC, not on power: one "
    "sd of the centred signal moves the points forecast by only %.4f points against a %.4f-point "
    "response sd, so even a PERFECT ORTHOGONAL predictor is capped at dR2 <= %.6f -- roughly "
    "%.1fx SMALLER than the dR2 <= 0.001127 ceiling on which D079 already killed the SHOT-MIX "
    "channel." % (head_on["dR2_cand_minus_base"], head_on["p_cluster_opp_team_season"],
                  head_off["dR2_cand_minus_base"], head_off["p_cluster_opp_team_season"],
                  ceil_on["points_moved_by_1sd_of_signal"], ceil_on["sd_y_points_this_frame"],
                  ceil_on["CEILING_A_perfect_orthogonal_dR2"],
                  0.001127 / ceil_on["CEILING_A_perfect_orthogonal_dR2"])),

  "step1_reproduction": {
    "a1_D074_conversion_headline_slope_plus_0p373": {
      "target_beta": E.D074_TARGET["beta"],
      "reproduced_beta": s01["a1_d074_statistic"]["reproduced"]["beta"],
      "abs_delta_beta": abs(s01["a1_d074_statistic"]["delta"]["beta"]),
      "abs_delta_n": abs(s01["a1_d074_statistic"]["delta"]["n"]), "exact": True},
    "a2_D074_construction_rebuilt_from_raw_shots": {
      "max_abs_diff_vs_frozen_O2": s01["a2_d074_construction"]["max_abs_diff"],
      "n_matched": s01["a2_d074_construction"]["n_matched"],
      "n_rebuild_nan": s01["a2_d074_construction"]["n_rebuild_nan"], "exact": True},
    "a3_five_zone_family": {
      z: dict(reproduced_beta=v["reproduced"]["beta"], published_beta=v["published"]["beta"],
              max_abs_delta=v["max_abs_delta"], match=v["match"])
      for z, v in s01["a3_five_zone_family"].items()},
    "b_D081_decision_relevant_stratum": {
      "rule": E.STRATUM_RULE,
      "n": s01["b_d081_stratum"]["reproduced"]["n"],
      "points_skill_reproduced": s01["b_d081_stratum"]["reproduced"]["points_skill"],
      "points_skill_target": E.D081_TARGET["points_skill"],
      "abs_delta_points_skill": abs(s01["b_d081_stratum"]["delta"]["points_skill"]),
      "abs_delta_p": abs(s01["b_d081_stratum"]["delta"]["p_two_sided_block_signflip"]),
      "all_seven_quantities_matched_at_0": True,
      "NOTE_on_minutes_skill": (
        "The task brief quoted D081 minutes skill as +7.7%. The frozen decomp_frame value on the "
        "DECISION-RELEVANT STRATUM (>=8 prior appearances AND trailing-5 minutes >=24, n=5107) "
        "is +6.143%, which is what reproduced at 0.000e+00. Tracked back to D081's own NOTES.md: "
        "+7.69% is the minutes skill on the >=20 prior appearances x >=24 minutes cell (n=3087) "
        "of its depth-by-volume grid -- a tighter cell INSIDE the stratum, not the stratum "
        "itself. No discrepancy; different row set, identical conclusion.")},
    "verdict": "BOTH ANCHORS REPRODUCE EXACTLY (0.000e+00 on every checked quantity except the "
               "five-zone family, which matches its 4-dp published table to 4.99e-05)."},

  "step2_the_centring": {
    "what_was_centred": "OC_z, the opponent's strictly-prior zone conversion rate MINUS its own "
                        "strictly-prior POOLED conversion rate (D074's O2 construction).",
    "how": "OCc_z = OC_z - lg_prior_gap_z(season, calendar date), where lg_prior_gap_z is the "
           "LEAGUE's own zone-minus-pooled conversion gap over ALL league games on STRICTLY "
           "EARLIER calendar dates in the same season. Not back-filled (back-filling the first "
           "dates from later ones would read forward). It is a date-indexed scalar shared by "
           "every opponent, so the CROSS-SECTIONAL ORDERING of opponents is untouched and only "
           "the additive LEVEL is removed.",
    "why_it_mattered": "Uncentred, OC_RA has a league-wide mean of +0.1886 against a cross-"
                       "sectional sd of 0.0380 -- a mean 5.0x its own sd. Added to a forecast it "
                       "is overwhelmingly a CONSTANT, i.e. a LEVEL SHIFT, not a matchup signal. "
                       "This is the defect the predecessor died reporting, and the same "
                       "distinction as D080.",
    "per_zone": s02["centring"],
    "measured_damage_of_NOT_centring": {
      "ppm_on_stratum_dR2_uncentred": cell(CT, response="ppm_points_per_minute",
                                           spec="SPEC_RA_UNCENTRED",
                                           stratum="on_stratum")["dR2_cand_minus_base"],
      "ppm_on_stratum_dR2_centred": head_on["dR2_cand_minus_base"],
      "points_on_stratum_dR2_uncentred": cell(PT, spec="SPEC_RA_UNCENTRED",
                                              stratum="on_stratum")["dR2_cand_minus_champ"],
      "comment": "The uncentred form is ~16x more damaging and would have been read as "
                 "'significant' two-sided (p=0.0042 on points) -- significant in the WRONG "
                 "direction, and entirely an artefact of the uncorrected level. Any reader of "
                 "the abandoned directory's FINDINGS.json is reading that artefact."},
    "alternative_centring_robustness": "A within-slate cross-sectional demean (OCc_xs) was also "
                                       "built and gives the same verdict (see contrast table, "
                                       "*_XSCENTRED rows); it is secondary because it depends on "
                                       "who else played that night."},

  "step3_headline_efficiency_contrast": {
    "test": "screenkit.paired_forecast_comparison(y, candidate, champion_baseline, groups) -- "
            "paired loss difference with a WHOLE-CLUSTER SIGN-FLIP null.",
    "primary_spec": "SPEC_RA: D074's frozen slope +0.3731536 applied to the RESTRICTED AREA "
                    "ONLY, which is the cell that actually survived the five-way multiplicity "
                    "(RA beta +0.4037; paint -0.1216 and corner 3 -0.2558 are NEGATIVE).",
    "primary_response": "points per minute (where D081 located the failure).",
    "ON_the_decision_relevant_stratum": head_on,
    "OFF_the_decision_relevant_stratum": head_off,
    "ALL_rows": head_all,
    "points_per_FGA_same_spec": {
      "on_stratum": cell(CT, response="ppf_points_per_FGA", spec="SPEC_RA",
                         stratum="on_stratum"),
      "off_stratum": cell(CT, response="ppf_points_per_FGA", spec="SPEC_RA",
                          stratum="off_stratum")},
    "which_case_are_we_in": "NEITHER. The contrast is negative and non-significant ON the "
                            "stratum (dR2 %+.6f, p %.4f) AND negative off it (dR2 %+.6f, p "
                            "%.4f). This is not the 'helps only cold-start rows, therefore "
                            "redundant with D081's free running-mean splice' case -- it does not "
                            "help anywhere." % (head_on["dR2_cand_minus_base"],
                                                head_on["p_cluster_opp_team_season"],
                                                head_off["dR2_cand_minus_base"],
                                                head_off["p_cluster_opp_team_season"]),
    "full_table": s03["contrast_table"]},

  "step3_inference_hygiene": {
    "grouping_level_measured_not_assumed": s02["grouping_levels"],
    "var_share_between_opponent_team_season": s02["var_share_between_opp_team_season"],
    "cluster_level_used_for_headline": "opponent_team_season (36 clusters) -- the coarsest level "
                                       "the signal's variance actually lives at (68.2% between).",
    "p_at_every_level_primary_cell": {
      k: {kk: head_on[kk] for kk in head_on if kk.startswith(("p_", "nclust_"))}
      for k in ["on_stratum"]},
    "row_level_null_inflation": {
      "on_stratum": head_on["inflation_cluster_over_row"],
      "off_stratum": head_off["inflation_cluster_over_row"],
      "all": head_all["inflation_cluster_over_row"],
      "comment": "The row-level null is 1.53-1.83x too narrow. Several row-level p values here "
                 "look 'significant' (e.g. 0.0056 all-rows) -- for a NEGATIVE dR2. Reading them "
                 "as support would have been backwards twice over."},
    "cluster_robust_SEs": "NOT used as a substitute for a permutation null anywhere.",
    "noop_placebo": {
      "identity_observed_sd": s03b["P1_identity"]["sd"],
      "identity_is_noop": s03b["P1_identity"]["is_noop"],
      "permute_key_and_rebuild_observed_sd": s03b["P2_permute_key_and_rebuild"]["sd"],
      "comment": "The literal identity returns sd = 0.000e+00 exactly, as it must. A first-pass "
                 "'relabel' transform was found to be algebraically the identity and was "
                 "replaced -- see NOTES.md, self-reported defect."},
    "real_permutation_control": s03b["P3_real_opponent_reassignment"]},

  "step4_points_propagation": {
    "construction": "pts_cand = ppm_cand x the champion's OWN minutes forecast, identically "
                    "pts_pred + fga_pred * S (verified to 3.6e-15).",
    "on_stratum": pts_on,
    "off_stratum": cell(PT, spec="SPEC_RA", stratum="off_stratum"),
    "all_rows": cell(PT, spec="SPEC_RA", stratum="all"),
    "full_table": s04["points_contrast"]},

  "step4_ARITHMETIC_CEILING": {
    "form": "D079's exact calculation: dR2 <= (points moved by 1 sd of the signal / response sd)^2",
    "on_stratum": ceil_on,
    "headline": ("One sd of the centred RA conversion signal moves the points forecast by %.4f "
                 "points against a %.4f-point response sd. CEILING dR2 <= %.6f. D079 killed the "
                 "SHOT-MIX channel at dR2 <= 0.001127. THIS CHANNEL'S CEILING IS %.1fx SMALLER "
                 "THAN THE ONE THAT ALREADY KILLED SHOT MIX."
                 % (ceil_on["points_moved_by_1sd_of_signal"], ceil_on["sd_y_points_this_frame"],
                    ceil_on["CEILING_A_perfect_orthogonal_dR2"],
                    0.001127 / ceil_on["CEILING_A_perfect_orthogonal_dR2"])),
    "oracle_upper_bound_DIAGNOSTIC": {
      "value": ceil_on["DIAGNOSTIC_ORACLE_best_scaling_dR2"],
      "warning": "USES THE REALISED RESPONSE. It is the dR2 obtainable if the transfer "
                 "coefficient were rescaled WITH HINDSIGHT on these very rows. It is an UPPER "
                 "BOUND and a DIAGNOSTIC, never a screened result and never a forecast. It is "
                 "reported to show that the failure is NOT a mis-scaled coefficient: even chosen "
                 "with hindsight the signal buys dR2 <= %.6f."
                 % ceil_on["DIAGNOSTIC_ORACLE_best_scaling_dR2"]},
    "direction_DIAGNOSTIC": {
      "corr_residual_vs_forecast_movement_on_stratum": ceil_on["DIAGNOSTIC_corr_resid_vs_move"],
      "comment": "NEGATIVE. D074's slope is positive on the SHOT-ZONE CONVERSION RATE; once "
                 "aggregated to player-game points the residual correlation with the transferred "
                 "adjustment is slightly negative. The mechanism does not survive aggregation."},
    "lever_decomposition": lev,
    "all_specs_and_strata": s04["arithmetic_ceiling"],
    "efficiency_response_ceiling": s04["efficiency_ceiling"]},

  "best_cells_chased_to_ground": {
    "what": "Four of the 54 cells have a POSITIVE centred dR2. All four are on the SECONDARY "
            "response (points per FGA), on the stratum. They are reported and chased, not "
            "dismissed.",
    "table": s06["propagation_of_positive_ppf_cells"],
    "ppf_ceilings": s06["ppf_ceiling"],
    "reading": [
      "Each positive dR2 EXCEEDS its own 'perfect orthogonal predictor' ceiling. That is not a "
      "signal beating a bound -- the ceiling is exact only for a predictor orthogonal to the "
      "baseline's error, and sampling variation can overshoot it. For a term this small, sitting "
      "ABOVE the ceiling is a symptom of NOISE, not of strength.",
      "None is significant at the cluster level (p 0.277-0.399).",
      "The points-per-FGA baseline itself has a NEGATIVE R2 (-0.0126 on the stratum): the "
      "champion's implied points-per-attempt is worse than a constant. A positive dR2 against "
      "such a baseline is a low bar.",
      "DECISIVELY: every one vanishes or reverses when propagated to POINTS. The largest becomes "
      "+0.000019 at cluster p = 0.9658."]},

  "why_this_is_not_D079_repeated": (
    "D079's ceiling was an argument about REALLOCATING attempts at constant volume, and it does "
    "not apply to CONVERSION -- converting better is not reallocating. That reasoning was "
    "correct and is why this screen was worth running. The conversion channel needed and got its "
    "OWN ceiling calculation, and that ceiling turns out to be even smaller. The reason is "
    "different: not that the mechanism is arithmetically constrained, but that the OPPONENT'S "
    "cross-sectional spread in rim-conversion allowance is small (sd 0.0380) and reaches points "
    "only through a %.3f rim share of attempts and a %.3f transfer slope."
    % (lev["mean_RA_w_player_prior_rim_share"], E.LAMBDA_D074)),

  "what_this_does_and_does_not_kill": {
    "KILLED": "The transfer of D074's opponent zone-conversion-allowance signal into the "
              "champion's per-minute / per-attempt EFFICIENCY forecast, and thence into points. "
              "Killed on arithmetic, on the decision-relevant stratum and off it.",
    "NOT_touched": "D074's own finding stands and reproduced exactly at 0.000e+00. The signal is "
                   "real at the shot-zone conversion level; it is simply far too small a lever "
                   "on player-game points to matter. Nothing here says the EFFICIENCY step is "
                   "unfixable -- it says this particular basketball-specific candidate is not "
                   "the fix, and D081's finding that generic pre-game state is dead is unchanged."},

  "constraints": {
    "partition": "2021-2024 only; champion-forecast work 2022-2024. shots_2025_*.parquet and "
                 "shots_2026_regular.parquet were never constructed as a path and never opened. "
                 "Enforced by screenkit.assert_partition on COLUMN VALUES at every stage; no "
                 "byte/regex scan used as a partition check.",
    "no_realised_game_information": "Every candidate input is strictly prior-games-only. Realised "
                                    "fga/minutes/points appear only as responses and in the two "
                                    "LOUDLY LABELLED diagnostics above.",
    "zone_maps": "data/zone_maps/* NOT READ (asof_granularity 'artifact'). Zones derived from the "
                 "raw per-shot SHOT_ZONE_BASIC label.",
    "manifest_check": s01["input_provenance"],
    "manifest_verdict": "EVERY input is UNVERIFIABLE (no sibling manifest). That is NOT a pass "
                        "and travels with this verdict. It does not weaken a KILL.",
    "no_model_fitting": "Nothing trained; the champion was not retrained or modified. LAMBDA is "
                        "D074's frozen +0.3731536. The only regressions run are (a) the D074 "
                        "reproduction, which re-derives a published number, and (b) the ORACLE "
                        "ceiling, which is a bound reported as a bound.",
    "R2_convention": "D069: plain unweighted, SST about the unweighted mean. Forecasts scored "
                     "with screenkit.r2_of_forecast (which does NOT refit), never r2_plain."},

  "cheating_disclosure": {
    "where_I_could_have_cheated": [
      "SPEC CHOICE. Three transfer specs were built (RA-only, all-five-global, all-five-per-zone) "
      "x three centrings (league-centred, uncentred, cross-sectionally demeaned) x two efficiency "
      "responses x three strata = 54 cells. Picking the best would be spec-shopping. SPEC_RA on "
      "points-per-minute was declared PRIMARY in s01's printed output BEFORE any contrast was "
      "computed, on the stated ground that RA is the cell that survived D074's multiplicity. "
      "THE FULL 54-CELL TABLE IS PUBLISHED in efficiency_contrast.csv, and the four positive "
      "centred cells in it are chased to ground in `best_cells_chased_to_ground` below rather "
      "than dismissed.",
      "CLUSTER LEVEL. Four cluster levels were run. The COARSEST/most conservative "
      "(opponent-team-season, 36 clusters) is the headline. Finer levels give SMALLER p -- for a "
      "NEGATIVE dR2 -- so choosing the coarse level is conservative for the KILL and would have "
      "been the cheat if the sign had been positive.",
      "CEILING FRAMING. The ceiling could have been quoted against the 5.82 FG-points sd instead "
      "of this frame's 7.55 total-points sd to make it look larger. Both are in "
      "arithmetic_ceiling.csv; the headline uses this frame's own response sd, which is the "
      "LARGER denominator and therefore the SMALLER, more damning ceiling. Stated explicitly."],
    "preselected_specifications": "YES for the primary cell (declared in s01 before contrasts). "
                                  "NO for the secondary specs, which are exploratory and are "
                                  "labelled as such. Nothing was dropped after being computed.",
    "nothing_was_reused_from_the_abandoned_run": True},

  "artifacts": sorted(os.listdir(E.HERE)),
}

json.dump(F, open(os.path.join(E.HERE, "FINDINGS.json"), "w"), indent=2, default=str)
print("\n  wrote FINDINGS.json  (%d bytes)"
      % os.path.getsize(os.path.join(E.HERE, "FINDINGS.json")))
print("  VERDICT: %s" % F["VERDICT"])
print("  " + F["one_line"])
print("DONE s05")
