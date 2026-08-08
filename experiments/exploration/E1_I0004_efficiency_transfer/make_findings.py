"""Assemble FINDINGS.json from the four step outputs.  No new statistics are computed here."""
import json
import os

import et_base as E

S = {k: json.load(open(os.path.join(E.HERE, "_s%s.json" % k))) for k in ["01", "02", "03", "04"]}
h = S["03"]["headline_ppf_decision_stratum"]
hm = S["03"]["headline_ppm_decision_stratum"]
pts = {(r["stratum"], r["spec"]): r for r in S["03"]["points_contrast"]}
eff = {(r["target"], r["stratum"], r["spec"]): r for r in S["03"]["efficiency_contrast"]}
DEC = "DECISION-RELEVANT (>=8 prior, trail5 min >=24)"
OFF = "OFF-STRATUM (everything else)"
POO = "POOLED"
ceil_dec = S["04"]["ceiling_vs_d079"][0]
orc = {(r["stratum"], r["target"]): r for r in S["04"]["ORACLE_in_sample_upper_bound"]}

F = {
    "screen_id": "E1_I0004_efficiency_transfer",
    "tier": "E1 -- NON-CLAIMING.  Nothing here is a RESULT; it is a LEAD or it is dead.",
    "date": "2026-08-07",
    "question": ("Does the opponent zone-conversion-allowance signal (D074's CONVERSION channel, "
                 "slope +0.373) improve a point-in-time forecast of player EFFICIENCY, and does "
                 "that improvement survive on the stratum where the champion actually fails "
                 "(D081: >=8 prior same-season appearances AND trailing-5 mean minutes >=24)?"),
    "verdict": "KILL",
    "one_line": (
        "NO. On the decision-relevant stratum the conversion-adjusted efficiency forecast is "
        "indistinguishable from the champion's own: points-per-FGA dR2 = +6.00e-04 at "
        "cluster p = 0.3967 (opponent-team-season, 36 clusters; naive row-level p = 0.2280, "
        "inflation 1.37x), and MAE skill against the matched point-in-time prior-mean reference "
        "moves the WRONG way (-2.78e-04). Points-per-minute is -5.48e-04 at p = 0.2535 and points "
        "is -2.84e-04 at p = 0.4763. The channel is also arithmetically incapable of mattering: "
        "1 sd of the signal moves a points forecast by 0.086 points, a ceiling of dR2 <= 2.17e-04 "
        "on D079's own 5.82-point denominator -- 5.2x TIGHTER than the 0.00113 ceiling on which "
        "D079 killed the shot-mix channel. D079's arithmetic argument genuinely does not transfer "
        "to conversion, and the ceiling computed from scratch for conversion is smaller anyway."),

    "reproduction_before_changing_anything": {
        "policy": "Both anchors reproduced BEFORE any construction. Either failing = STOP.",
        "D074_corrected_conversion_headline": {
            "target": S["01"]["a1_d074_statistic"]["target"],
            "reproduced_statistic": {k: S["01"]["a1_d074_statistic"]["reproduced"][k]
                                     for k in ("n", "corr", "diff", "beta")},
            "absolute_delta": S["01"]["a1_d074_statistic"]["delta"],
            "abs_delta_beta": abs(float(S["01"]["a1_d074_statistic"]["delta"]["beta"])),
            "construction_rebuilt_from_raw_shot_files": S["01"]["a2_d074_construction"],
            "five_zone_family": {z: {"reproduced_beta": v["reproduced"]["beta"],
                                     "published_beta": v["published"]["beta"],
                                     "max_abs_delta_vs_4dp_published": v["max_abs_delta"],
                                     "match": v["match"]}
                                 for z, v in S["01"]["a3_five_zone_family"].items()},
            "note": ("The killed E0 headline of +0.0392 is never quoted. The corrected headline is "
                     "beta +0.3731536 / corr +0.0288 / diff +0.0176 on the 30,764-row common set. "
                     "IMPORTANT STRUCTURAL FACT recovered in reproduction: across the five-zone "
                     "family the surviving effect is essentially RESTRICTED AREA ONLY (+0.4037); "
                     "paint (-0.1216) and corner 3 (-0.2558) are negative and mid-range/ATB3 are "
                     "~0. The family-wise p 0.0124 is a max-t statement that the RA cell survives "
                     "five-way multiplicity, NOT that five zones carry the effect.")},
        "D081_decision_relevant_stratum": {
            "rule": S["01"]["b_d081_stratum"]["rule"],
            "reproduced": S["01"]["b_d081_stratum"]["reproduced"],
            "target": S["01"]["b_d081_stratum"]["target"],
            "absolute_delta": S["01"]["b_d081_stratum"]["delta"],
            "max_abs_delta": max(abs(float(v))
                                 for v in S["01"]["b_d081_stratum"]["delta"].values())},
        "both_reproduced_exactly": True},

    "headline_decision_relevant_stratum": {
        "rule": E.STRATUM_RULE,
        "spec": ("SPEC A -- the faithful transfer of the D074 slope that survived multiplicity: "
                 "adj_ppf = 0.3731535713274873 * w_RA * 2.0 * OCc_RA, where w_RA is the share of "
                 "the player's STRICTLY PRIOR same-season FGA taken in the restricted area and "
                 "OCc_RA is the opponent's STRICTLY PRIOR restricted-area conversion allowance "
                 "centred on the strictly-prior league zone gap."),
        "points_per_fga": {
            "n": h["n"], "n_clusters": h["n_clusters"], "cluster_level": "opponent-team-season",
            "r2_of_forecast_baseline": h["r2_baseline"],
            "r2_of_forecast_candidate": h["r2_candidate"],
            "dr2_candidate_minus_baseline": h["dr2_candidate_minus_baseline"],
            "p_two_sided_cluster_signflip": h["p_two_sided_cluster"],
            "p_row_level_NAIVE_anticonservative": h["p_row_level_NAIVE"],
            "null_sd_inflation_cluster_over_row": h["inflation_cluster_over_row"],
            "mae_skill_vs_prior_mean_reference_baseline": h["skill_baseline"],
            "mae_skill_vs_prior_mean_reference_candidate": h["skill_candidate"],
            "delta_mae_skill": h["d_skill"]},
        "points_per_minute": {
            "n": hm["n"], "dr2_candidate_minus_baseline": hm["dr2_candidate_minus_baseline"],
            "p_two_sided_cluster_signflip": hm["p_two_sided_cluster"],
            "delta_mae_skill": hm["d_skill"]},
        "points": {
            "n": pts[(DEC, "A")]["n"],
            "dr2_candidate_minus_baseline": pts[(DEC, "A")]["dr2_candidate_minus_baseline"],
            "p_two_sided_cluster_signflip": pts[(DEC, "A")]["p_two_sided_cluster"],
            "delta_mae_skill": pts[(DEC, "A")]["d_skill"]},
        "squared_loss_and_absolute_loss_disagree_in_sign": (
            "On points-per-FGA the paired SQUARED-loss difference is slightly positive "
            "(+6.00e-04) while the MAE skill difference is slightly negative (-2.78e-04). Both are "
            "~0 and neither is significant; the disagreement is reported rather than resolved, and "
            "no headline is taken from whichever sign is more flattering."),
        "answer": "NO -- the conversion signal does not improve efficiency on the stratum where "
                  "the champion fails."},

    "off_stratum_contrast": {
        "points_per_fga": {k: eff[("ppf", OFF, "A")][k]
                           for k in ("n", "dr2_candidate_minus_baseline", "p_two_sided_cluster",
                                     "d_skill", "p_row_level_NAIVE")},
        "points_per_minute": {k: eff[("ppm", OFF, "A")][k]
                              for k in ("n", "dr2_candidate_minus_baseline",
                                        "p_two_sided_cluster", "d_skill")},
        "points": {k: pts[(OFF, "A")][k] for k in ("n", "dr2_candidate_minus_baseline",
                                                   "p_two_sided_cluster", "d_skill")},
        "which_case_are_we_in": (
            "NEITHER. The signal does not help on the decision-relevant stratum AND it does not "
            "help off it; off-stratum points-per-FGA is -2.50e-04 at p=0.3575 and MAE skill "
            "-1.76e-04. This is not the 'helps only on thin-sample / low-minute players, therefore "
            "redundant with D081's free running-mean splice' case -- there is nothing to be "
            "redundant with. It is simply absent everywhere.")},

    "pooled_contrast": {
        "points_per_fga": {k: eff[("ppf", POO, "A")][k]
                           for k in ("n", "dr2_candidate_minus_baseline", "p_two_sided_cluster",
                                     "d_skill")},
        "points": {k: pts[(POO, "A")][k] for k in ("n", "dr2_candidate_minus_baseline",
                                                   "p_two_sided_cluster", "d_skill")}},

    "all_preregistered_specifications": {
        "why_all_are_reported": ("All four specs were fixed in s02_build.py/s03_contrast.py before "
                                 "any contrast was computed and ALL FOUR are reported, so there "
                                 "was no freedom to pick a winner afterwards."),
        "A_headline_RA_only_frozen_slope_centred": "adj = 0.3731536 * w_RA * 2 * OCc_RA",
        "B_five_zone_one_global_slope": "adj = 0.3731536 * sum_z w_z * PV_z * OCc_z",
        "C_five_zone_per_zone_frozen_betas_OPTIMISTIC": (
            "adj = sum_z beta_z * w_z * PV_z * OCc_z with beta_z the frozen five-zone betas. "
            "Those betas were estimated on the SAME 2021-2024 partition, so this spec is "
            "in-sample in its coefficients and can only flatter the candidate. Reported to bound "
            "the channel from above; never a verdict."),
        "U_uncentred_sensitivity_MIS_CALIBRATED": (
            "adj = 0.3731536 * w_RA * 2 * OC_RA with the raw D074 OC. OC_RA has a league-wide mean "
            "of +0.1835 because restricted-area shots simply convert better than the pooled "
            "average; D074 measured its slope in a regression WITH AN INTERCEPT, which absorbs "
            "that level. As an additive forecast adjustment the uncentred form injects a "
            "systematic +0.0338 points-per-attempt bias and, as expected, LOSES badly "
            "(points-per-minute dR2 -9.09e-03 at p=0.0090). It is reported to show the arithmetic, "
            "not as a candidate."),
        "results_by_spec_decision_stratum": {
            "ppf": {t: {k: eff[("ppf", DEC, t)][k]
                        for k in ("dr2_candidate_minus_baseline", "p_two_sided_cluster",
                                  "d_skill")} for t in "ABCU"},
            "ppm": {t: {k: eff[("ppm", DEC, t)][k]
                        for k in ("dr2_candidate_minus_baseline", "p_two_sided_cluster",
                                  "d_skill")} for t in "ABCU"},
            "pts": {t: {k: pts[(DEC, t)][k]
                        for k in ("dr2_candidate_minus_baseline", "p_two_sided_cluster",
                                  "d_skill")} for t in "ABCU"}},
        "no_spec_clears_anything": True},

    "arithmetic_ceiling_for_this_channel": {
        "convention": ("D079's: dR2 <= (sd of the points adjustment / sd of the points response)^2 "
                       "-- the ceiling if the term were a PERFECT predictor of the residual and "
                       "orthogonal to the champion's own forecast."),
        "why_D079s_number_does_not_transfer": (
            "D079's 0.00113 came from a MIX term, which reallocates attempts at constant volume. "
            "Converting better is not reallocating, so that ceiling genuinely does not bind here "
            "and had to be recomputed from scratch. Recomputed, it is TIGHTER."),
        "decision_relevant_stratum": {
            "one_sd_of_signal_moves_points_by": ceil_dec["one_sd_move_points_A"],
            "sd_total_points_response_this_frame": ceil_dec["sd_total_points"],
            "sd_fg_points_response_this_frame_DIAGNOSTIC": ceil_dec["sd_fg_points_DIAG"],
            "ceiling_dr2_vs_total_points": ceil_dec["ceiling_dR2_vs_total_points_A"],
            "ceiling_dr2_vs_fg_points": ceil_dec["ceiling_dR2_vs_fg_points_A"],
            "ceiling_dr2_vs_D079_5p82_denominator": ceil_dec["ceiling_dR2_vs_D079_denominator_A"],
            "spec_B_ceiling_vs_D079_denominator": ceil_dec["ceiling_dR2_vs_D079_denominator_B"],
            "spec_C_ceiling_vs_D079_denominator": ceil_dec["ceiling_dR2_vs_D079_denominator_C"]},
        "head_to_head_with_D079": {
            "shot_mix_1sd_move_points": 0.196, "shot_mix_ceiling_dr2": 0.001127,
            "conversion_1sd_move_points": ceil_dec["one_sd_move_points_A"],
            "conversion_ceiling_dr2": ceil_dec["ceiling_dR2_vs_D079_denominator_A"],
            "conversion_ceiling_is_tighter_by_factor":
                0.001127 / ceil_dec["ceiling_dR2_vs_D079_denominator_A"]},
        "is_the_ceiling_tiny": True,
        "statement": ("YES, tiny -- and that is a complete answer. Even a PERFECT conversion "
                      "adjustment of this magnitude could buy at most dR2 ~2e-04 on points. The "
                      "lead is closed on arithmetic, independently of any p-value.")},

    "oracle_in_sample_upper_bound_NOT_A_FORECAST": {
        "what_it_is": ("screenkit.delta_r2_plain REFITS, so this is what the term would buy with "
                       "its coefficient chosen knowing the answer on these very rows. It answers "
                       "'is the transfer merely mis-scaled?'. It is an ORACLE and is NOT a result."),
        "decision_stratum_ppf": orc[(DEC, "ppf")],
        "decision_stratum_ppm": orc[(DEC, "ppm")],
        "decision_stratum_pts": orc[(DEC, "pts")],
        "reading": ("On points-per-FGA the oracle coefficient is +1.42, i.e. the D074 DIRECTION "
                    "does reproduce on the champion's own efficiency residual and the frozen scale "
                    "of 1.0 is roughly right -- but even the oracle only buys dR2 +5.71e-04. On "
                    "points-per-minute (-0.26) and on POINTS (-0.46) the oracle coefficient is "
                    "NEGATIVE and the oracle dR2 on points is +2.76e-05. The transfer is not "
                    "mis-scaled; the channel is too small to matter, and once it is weighted by "
                    "attempts and minutes it does not even keep its sign.")},

    "inference": {
        "headline_test": "screenkit.paired_forecast_comparison -- forecast vs forecast on the same "
                         "rows, paired squared-loss difference, null by sign-flipping WHOLE "
                         "clusters.",
        "cluster_level_chosen": "opponent-team-season",
        "how_chosen": ("screenkit.detect_grouping_level was run on OC__Restricted Area and on "
                       "adjA_ppf rather than assuming a level. OC is constant within "
                       "(opponent-team, game); the ADJUSTMENT multiplies it by a player-specific "
                       "prior mix so no coarser level is exactly constant and the kit correctly "
                       "returns recommended_permutation_level = None with status "
                       "NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE (the P2 behaviour). "
                       "The clustering therefore comes from the OUTCOME side, which "
                       "detect_grouping_level explicitly does not inspect: the candidate-minus-"
                       "baseline loss difference is driven by one opponent-team-season allowance "
                       "series shared by every player who faced that team."),
        "var_share_between_adjA": S["03"]["var_share_between_adjA"],
        "alternative_clusterings": S["03"]["alternative_clusterings_headline"],
        "row_level_null_reported_alongside": True,
        "cluster_robust_SEs_used_as_a_substitute": False,
        "note_on_power": ("There are only 36 opponent-team-seasons (12 teams x 3 seasons), so the "
                          "cluster test is low-powered. The conclusion does not hinge on it: the "
                          "null-sd inflation over the row level is only 1.37x and even the "
                          "ANTICONSERVATIVE row-level p is 0.2280. A signal that cannot clear an "
                          "anticonservative null is not being killed by a conservative one."),
        "n_draws": 5000, "seed": E.SEED},

    "noop_placebo": S["03"]["noop_placebo"],

    "controls_and_guards": {
        "manifest_check": S["01"]["input_provenance"],
        "manifest_verdict": ("ALL FOUR inputs are UNVERIFIABLE (no sibling manifest), which is NOT "
                             "a pass and travels with this verdict. The two anchor parquets are "
                             "frozen outputs of committed screens; the raw per-season shot files "
                             "carry the season in the filename and are re-checked here on COLUMN "
                             "VALUES. Nothing here is deployable."),
        "partition_check": "screenkit.assert_partition on VALUES (parsed dates and season-valued "
                           "columns) after every load and every filter. No byte or regex scan is "
                           "used as a partition check anywhere.",
        "seasons_touched": [2021, 2022, 2023, 2024],
        "seasons_2025_2026": "NEVER read, joined, filtered against, counted, plotted or described. "
                             "data/shotcharts/shots_2025_*.parquet and shots_2026_regular.parquet "
                             "exist; their paths are never constructed.",
        "zone_maps": "FORBIDDEN and NOT READ. Zones are derived from the raw per-shot "
                     "SHOT_ZONE_BASIC label.",
        "future_leakage_probe": {
            "retrospective_suspect_vs_prior_only_clean":
                S["02"]["leakage_probe_retro_vs_prior"],
            "reverse_direction": S["02"]["leakage_probe_reverse"],
            "reading": ("The probe FLAGS the known offender (leave-one-GAME-out full-season "
                        "opponent zone rate: corr +0.5551 with the opponent's own strictly-after "
                        "future vs +0.2982 for the prior-only OC, dR2 0.2479 in predicting that "
                        "future) and does NOT flag the prior-only construction this screen uses. "
                        "That is the machinery behaving correctly, not a certificate.")},
        "pressure_lib_pregame_columns_used": ("NONE. No `*_pregame` column from pressure_lib.py is "
                                              "touched anywhere in this screen, so the D080 "
                                              "current-season-league-mean subtlety does not arise. "
                                              "The one shared season-level anchor this screen does "
                                              "use -- the league zone-minus-pooled gap used to "
                                              "centre OC -- is built ONLY from games strictly "
                                              "before the date, so it is legitimate for the level "
                                              "claim as well as the cross-sectional one.")},

    "time_window_table": [
        {"quantity": "OCc_z opponent zone-conversion allowance (centred)",
         "window": "the opponent's own games with game_date STRICTLY EARLIER in the same season "
                   "(cumsum minus own row), minus the league zone-minus-pooled gap over all games "
                   "STRICTLY EARLIER in the same season",
         "reads_the_current_game": "NO",
         "verified": "value-by-value against D074's frozen O2 column at max|diff| = 0.000e+00 "
                     "(s01a2), and the league anchor is not back-filled"},
        {"quantity": "w_z player prior zone mix",
         "window": "the player's own games with game_date STRICTLY EARLIER in the same season "
                   "(cumsum minus own row); gate >=20 strictly-prior FGA",
         "reads_the_current_game": "NO",
         "verified": "sum_z w_z == 1 to 2.2e-16 on every row that has a mix"},
        {"quantity": "base_ppf / base_ppm champion implied efficiency",
         "window": "ratios of the champion's OWN point forecasts on this row",
         "reads_the_current_game": "NO (the champion's own walk-forward guarantee)",
         "verified": "carried unchanged from D081's frozen decomp_frame; nothing refitted"},
        {"quantity": "refA_* / refB_* references",
         "window": "D081's strictly-prior expanding player references, .shift(1) BEFORE "
                   ".expanding(), with a same-season expanding league-mean cold fallback",
         "reads_the_current_game": "NO",
         "verified": "carried unchanged from the frozen decomp_frame"},
        {"quantity": "y_pts / y_fga / y_minutes / y_ppf / y_ppm",
         "window": "the current game", "reads_the_current_game": "YES -- IT IS THE RESPONSE",
         "verified": "never an input to any forecast"},
        {"quantity": "DIAG_fg_points, DIAG_realised_ra_allowed, OC_LOO_RETRO",
         "window": "current game / the opponent's whole season",
         "reads_the_current_game": "YES -- LABELLED DIAGNOSTIC",
         "verified": "excluded from every headline; DIAG_fg_points is used only as a ceiling "
                     "denominator and a free-throw-dilution figure, DIAG_realised_ra_allowed only "
                     "as the leakage probe's outcome, OC_LOO_RETRO only as the probe's known-bad "
                     "suspect"}],

    "coverage": {
        "champion_rows": S["02"]["n_rows_champion_frame"],
        "rows_with_unresolved_opponent": S["02"]["n_rows_opponent_unresolved"],
        "rows_with_a_usable_RA_signal": 11267,
        "rows_where_candidate_equals_champion": 2598,
        "contrast_repeated_on_signal_rows_only": S["03"]["signal_rows_only"],
        "free_throw_dilution_DIAGNOSTIC": {
            "fg_points_share_of_total_points": S["02"]["DIAG_fg_point_share_of_total_points"],
            "note": "17.4% of the points the champion forecasts are free throws, which a "
                    "conversion-allowance signal cannot touch."}},

    "where_i_could_have_cheated": [
        {"decision": "Which transfer specification to call the headline.",
         "risk": "Four are defensible; picking after seeing the answer would be selection.",
         "handled": "All four were fixed in the scripts before any contrast ran and ALL FOUR are "
                    "reported at every stratum and every target. None clears anything, so the "
                    "choice is moot in this case -- but it was removed rather than made."},
        {"decision": "Centring OC on the strictly-prior league zone gap.",
         "risk": "This is a construction change relative to D074's raw O2.",
         "handled": "DISCLOSED. It was added after seeing the MEAN and SD of OC printed in s02a "
                    "and BEFORE any contrast, skill number or p-value existed. It is forced "
                    "arithmetic, not tuning: D074 measured the slope in a regression WITH AN "
                    "INTERCEPT, so the +0.18 league-wide RA-vs-pooled level was absorbed there and "
                    "must be removed here. The uncentred variant is carried through as spec U and "
                    "loses badly, which is the evidence that the centring is necessary rather "
                    "than convenient."},
        {"decision": "The cluster level for the paired null.",
         "risk": "Choosing the level that gives the p one wants.",
         "handled": "Five levels are reported (opponent-team-season, game, player-season, "
                    "player-game, row). The coarsest and most conservative is the headline. Every "
                    "level gives p >= 0.21; the choice cannot change the verdict."},
        {"decision": "The reference for the MAE skill.",
         "risk": "REF-A is easier than REF-B.",
         "handled": "Both reported. The candidate loses to the baseline against both."},
        {"decision": "Reporting the in-sample ORACLE dR2.",
         "risk": "An oracle number can be mistaken for a result and is always flattering.",
         "handled": "Labelled ORACLE in the field name, in the section header and in the note, "
                    "and used only as an UPPER BOUND that strengthens the KILL. It is also small."},
        {"decision": "The squared-loss/absolute-loss sign disagreement on points-per-FGA.",
         "risk": "Quoting whichever of +6.00e-04 and -2.78e-04 suits the story.",
         "handled": "Both are in the headline block with the disagreement stated explicitly."},
        {"decision": "Was any specification preselected and then dropped?",
         "risk": "Silent abandonment of a spec.",
         "handled": "No. Nothing was dropped. Every specification written down was run and is "
                    "reported."}],

    "kit_feedback": {
        "defects_found": "NONE. The kit behaved correctly on every call in this screen.",
        "detail": [
            "detect_grouping_level correctly returned recommended_permutation_level = None with "
            "status NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE for the row-varying "
            "adjustment (the post-P2 behaviour), and correctly found the coarser levels for the "
            "opponent allowance.",
            "paired_forecast_comparison is exactly the right shape for this screen's question and "
            "was used as the headline; its dr2_a_minus_b agreed with r2_of_forecast(y,a) - "
            "r2_of_forecast(y,b), and its p_row_level_NAIVE / inflation fields removed the need "
            "to hand-roll the contrast null.",
            "r2_of_forecast (not r2_plain) was used for every scored forecast, and r2_plain's "
            "REFITTING behaviour was used deliberately and only for the labelled ORACLE bound -- "
            "the P3 distinction was load-bearing here and the docstrings made it unambiguous.",
            "noop_placebo returned sd = 0.000e+00 with n_distinct_draw_values = 1 on the identity "
            "and on the relabel-the-key-and-recompute transform (both correctly flagged vacuous), "
            "and sd = 4.448e-04 on a genuine shuffle (correctly not flagged).",
            "future_leakage_probe flagged the leave-one-game-out full-season opponent rate and did "
            "not flag the prior-only construction, in both directions.",
            "assert_partition passed on every frame and correctly SKIPPED pl_prior_season_games "
            "and tm_season_progress as season-NAMED but not season-VALUED."],
        "one_observation_not_a_defect": (
            "paired_forecast_comparison's docstring is explicit that it does not know whether your "
            "clusters are right, and detect_grouping_level is explicit that it inspects the "
            "FEATURE and not the OUTCOME. For a forecast contrast those two facts leave a real gap "
            "the caller must close by hand: the feature-side detector returns None for any "
            "row-varying candidate, which is correct, but gives no help choosing the outcome-side "
            "cluster the paired test actually needs. Both docstrings say so plainly, so this is a "
            "documented boundary rather than a defect -- but a future kit might offer an "
            "outcome-side companion to detect_grouping_level.")},

    "what_would_change_this_verdict": [
        "Nothing available inside this partition. The arithmetic ceiling (dR2 <= 2.17e-04 on "
        "points) binds before any inference question arises, and it is 5.2x tighter than the "
        "ceiling on which D079 already killed the sibling mix channel.",
        "The channel would need roughly an order of magnitude more leverage per attempt -- e.g. a "
        "conversion-allowance measure with several times the cross-sectional spread of the "
        "opponent's prior RA allowance (sd 0.040 after centring) -- before it could move points "
        "enough to be worth measuring.",
        "D074's conversion lead remains a real, thin SHOT-LEVEL effect. This screen does not "
        "withdraw it. It establishes that it does not transfer to a player-game efficiency "
        "forecast, which is a separate and now-answered question."],

    "files_written": sorted(os.listdir(E.HERE)),
}

json.dump(F, open(os.path.join(E.HERE, "FINDINGS.json"), "w", encoding="utf-8"), indent=2,
          default=str)
print("wrote FINDINGS.json  (verdict=%s)" % F["verdict"])
