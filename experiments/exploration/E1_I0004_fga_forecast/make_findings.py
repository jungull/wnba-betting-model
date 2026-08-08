"""E1 I0004c -- assemble FINDINGS.json from the three result files. No new statistics."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]


def L(n):
    return json.load(open(os.path.join(HERE, n), encoding="utf-8"))


B, E, A = L("build_results.json"), L("end_to_end_results.json"), L("addendum_results.json")
PW = L("pooled_vs_wf.json")
s3, n3 = E["step3_zone_counts"], E["step3_nulls_walkforward"]
s4, n4 = E["step4_points"], E["step4_nulls_walkforward"]

F = {
    "screen_id": "E1_I0004_fga_forecast",
    "parent": "E1_I0004_shot_selection (decision D074)",
    "status": "E1 EXPLORATION -- NON-CLAIMING. A LEAD, never a RESULT. No registry "
              "entry, no preregistration, no promotion, no leaderboard row.",
    "question": ("The parent's player-game increment (+0.019138861495123338 dR2 on "
                 "Restricted-Area attempt counts) is measured CONDITIONAL ON REALISED "
                 "FGA and is therefore a mix increment, not a forecast increment. Does "
                 "the opponent shot-mix signal survive when TOTAL ATTEMPTS must also be "
                 "forecast from strictly prior-games information?"),
    "verdict": "SPLIT",
    "verdict_detail": {
        "zone_attempt_counts": "KEEP-AS-LEAD",
        "player_points": "KILL",
        "one_line": ("The mix signal survives the attempts forecast almost intact "
                     "(+0.016853 walk-forward vs +0.019139 conditional, 88% retained, "
                     "family-wise p 0.0002 at the opponent-team-season level), but it "
                     "is arithmetically too small to move a points forecast: even a "
                     "PERFECT mix term could only buy dR2 <= 0.00113 on FG points, and "
                     "the realised walk-forward number is +0.000021 at p 0.2150.")},

    "partition": {"seasons_used": B["seasons_used"],
                  "holdout_2025_2026": "never read, joined, filtered against, counted, "
                                       "plotted or described",
                  "date_range_of_analysis_frame": "2021-05-21 .. 2024-10-20"},
    "r2_convention": B["r2_convention"],

    # ------------------------------------------------------------------------ STEP 1
    "step1_reproduction": {
        "target": "E1_I0004_shot_selection/dr2_results.json, Restricted Area, 2021-2024",
        "target_dR2": B["step1_reproduction"]["target_dR2"],
        "target_R2_base": B["step1_reproduction"]["target_m0"],
        "reproduced_from_predecessor_frame_dR2":
            B["step1_reproduction"]["from_predecessor_frame"]["dR2"],
        "reproduced_from_independent_raw_rebuild_dR2":
            B["step1_reproduction"]["from_raw_rebuild"]["dR2"],
        "abs_diff_from_predecessor_frame":
            B["step1_reproduction"]["abs_diff_from_predecessor_frame"],
        "abs_diff_from_independent_raw_rebuild":
            B["step1_reproduction"]["abs_diff_from_raw_rebuild"],
        "n_match": True,
        "frame_column_max_abs_deltas_raw_rebuild_vs_frozen_frame":
            B["step1_reproduction"]["frame_column_max_abs_deltas"],
        "exact": B["step1_reproduction"]["exact"],
        "conditional_dR2_all_five_zones":
            {z: B["step1_conditional_all_zones"][z]["dR2"] for z in ZONES}},

    # ------------------------------------------------------------------------ STEP 2
    "step2_fga_forecasts": {
        "target": "the player's realised total field-goal attempts over the five zones",
        "definitions": {
            "F_LG": "league prior mean FGA per player-game over games played strictly "
                    "before this calendar date, same season. NO player information. "
                    "Floor reference.",
            "F_A": "CRUDE. (sum of the player's FGA over strictly prior games in season "
                   "+ K_A * F_LG) / (prior games + K_A), K_A = 3.",
            "F_A2": "reference. EWMA_0.30 of the player's FGA over strictly prior games "
                    "in season -- identical to the predecessor's role_prior_fga.",
            "F_B_nopace": "BETTER, core. Frozen own_rate_v2_split_alpha driven by REAL "
                          "prior-game MINUTES: EWMA_0.03(FGA per 36 min)[strictly prior] "
                          "* EWMA_0.30(minutes)[strictly prior] / 36.",
            "F_B": "BETTER, headline. F_B_nopace * opponent prior-pace multiplier "
                   "(attempts faced per game in the opponent's strictly prior games this "
                   "season / league prior mean, clipped to [0.85, 1.15])."},
        "accuracy_on_all_player_games_n_prior_ge_3":
            B["step2_fga_forecast_accuracy"]["all_player_games"],
        "accuracy_on_the_headline_analysis_set":
            B["step2_fga_forecast_accuracy"]["analysis_set"],
        "accuracy_by_season_analysis_set":
            B["step2_fga_forecast_accuracy"]["by_season"],
        "realised_fga_moments_analysis_set": B["step2_realised_fga_moments"],
        "minutes_source_coverage_fraction": B["minutes_coverage_fraction"],
        "note": ("On the headline analysis set the crude F_A edges F_B on R2 (0.35699 "
                 "vs 0.35158) purely because that set is defined by a realised-FGA gate "
                 "(FGA >= 5) which truncates the low tail; on the untruncated set of all "
                 "player-games F_B is the better forecast on every metric (R2 0.58422 vs "
                 "0.56201, MAE 2.5670 vs 2.6810). Both are carried everywhere.")},

    # ------------------------------------------------------------------------ STEP 3
    "step3_end_to_end_zone_attempt_counts": {
        "specification": {
            "BASELINE": "z_att ~ 1 + S1 * FGAhat",
            "CANDIDATE": "z_att ~ 1 + S1 * FGAhat + FGAhat * OS",
            "realised_information_on_the_right_hand_side": "NONE",
            "walk_forward": "coefficients refitted at every distinct game date on all "
                            "rows strictly earlier in time; MIN_TRAIN = 1000 rows; "
                            "9290 of 10307 RA rows scored out of sample"},
        "HEADLINE_RA_walkforward_dR2_F_B": s3[RA]["F_B"]["wf_dR2"],
        "HEADLINE_RA_walkforward_dR2_F_A": s3[RA]["F_A"]["wf_dR2"],
        "conditional_comparator_pooled_realised_FGA": E["step3_degradation_RA"][
            "predecessor_pooled_conditional_dR2_realised_FGA"],
        "degradation_decomposition_RA": E["step3_degradation_RA"],
        "fraction_of_the_conditional_increment_retained_F_B": (
            s3[RA]["F_B"]["wf_dR2"]
            / E["step3_degradation_RA"][
                "predecessor_pooled_conditional_dR2_realised_FGA"]),
        "base_R2_collapse_RA": {
            "conditional_on_realised_FGA": s3[RA]["fga"]["wf_R2_base"],
            "with_forecast_F_B": s3[RA]["F_B"]["wf_R2_base"],
            "comment": ("The LEVEL of predictability collapses (0.5110 -> 0.3135) once "
                        "attempts must be forecast. The INCREMENT does not. The mix term "
                        "is close to orthogonal to attempts-forecast error.")},
        "all_zones": s3,
        "MAE_improvement_RA_F_B_rim_attempts_per_game": s3[RA]["F_B"]["wf_dMAE"],
        "natural_units": E["natural_units_RA"],
        "nulls_walkforward_opponent_team_season_level": n3,
        "family_wise_p_five_zone_max_z": E["step3_family_wise_p"],
        "null_inflation_factor_correct_over_naive_RA": {
            "F_A": n3["F_A"][RA]["inflation_sd_cluster_over_row"],
            "F_B": n3["F_B"][RA]["inflation_sd_cluster_over_row"]},
        "defective_no_op_placebo_run_on_purpose": {
            z: {"ref": n3["F_B"][z]["real_cluster"], "null_mean": n3["F_B"][z]["noop_mean"],
                "null_sd": n3["F_B"][z]["noop_sd"],
                "max_abs_dev": n3["F_B"][z]["noop_max_abs_dev"]} for z in ZONES},
        "robustness_sample_gate_made_pregame": E["robustness_pregame_gate"],
        "pooled_vs_walkforward_like_for_like": {
            "why": ("Walk-forward prints HIGHER than pooled in-sample (+0.016853 vs "
                    "+0.016480), which flatters the headline choice and must be "
                    "explained. It is a ROW-SET effect: pooled uses all 10307 rows, "
                    "walk-forward scores only the 9290 after MIN_TRAIN. Held to the "
                    "identical rows the true cost of out-of-sample fitting is NEGATIVE "
                    "in all 15 cells, as it must be."),
            "table": PW}},

    # ------------------------------------------------------------------------ STEP 4
    "step4_player_points": {
        "specification": {
            "BASELINE": "pts ~ 1 + FGAhat * sum_z(S1_z * q_z * v_z)",
            "CANDIDATE": "pts ~ 1 + FGAhat * sum_z(S1_z * q_z * v_z) "
                         "+ FGAhat * sum_z(OS_z * q_z * v_z)",
            "q_z": "the player's STRICTLY PRIOR-games zone conversion rate, shrunk "
                   "(K_Q = 20 attempts) toward the league zone rate over games played "
                   "strictly before this calendar date. NO realised conversion.",
            "v_z": "2 or 3 points per make",
            "sum_z_OS_z": "0 to machine precision (max|.| = 1.11e-16), so the candidate "
                          "term is a PURE MIX SHIFT at constant forecast volume"},
        "results": s4,
        "nulls_walkforward_opponent_team_season_level": n4,
        "HEADLINE_fg_points_walkforward_dR2_F_B": s4["fg_pts"]["F_B"]["wf_dR2"],
        "HEADLINE_fg_points_p_cluster_level": n4["fg_pts"]["F_B"]["p_cluster_one_sided"],
        "secondary_total_box_points_walkforward_dR2_F_B":
            s4["pts_total_box"]["F_B"]["wf_dR2"],
        "secondary_total_box_points_p_cluster_level":
            n4["pts_total_box"]["F_B"]["p_cluster_one_sided"],
        "secondary_total_box_points_p_naive_row_level":
            n4["pts_total_box"]["F_B"]["p_row_one_sided"],
        "why_it_fails": {
            "sd_of_the_mix_term_in_points_F_B": 0.1955,
            "sd_of_the_points_target_fg_pts": s4["fg_pts"]["target_sd"],
            "arithmetic_ceiling_dR2_if_the_mix_term_were_a_perfect_orthogonal_predictor":
                0.001127,
            "comment": ("A rim-ward mix shift DOES raise expected points -- the sign is "
                        "right and the pooled coefficient is +0.5354 -- but 1 sd of the "
                        "opponent mix signal moves the points forecast by only 0.196 "
                        "points against a 5.82-point response sd. The channel is "
                        "arithmetically incapable of mattering, whatever its "
                        "statistical significance. This is a magnitude verdict, not a "
                        "power verdict.")}},

    # ------------------------------------------------------------------------ STEP 5
    "step5_where_it_survives_best": {
        "note": "Reported because step 3 survived. All splits are strictly PRE-GAME "
                "observables. Splits were specified together before running.",
        "walkforward_dR2_by_bin_RA": E["step5_heterogeneity_walkforward_RA"],
        "pocket_nulls_opponent_team_season_level": A["step5_pocket_nulls"],
        "abstention_reading": ("The increment is concentrated where the opponent's rim "
                               "allowance is far from league average: walk-forward dR2 "
                               "+0.047428 in the extreme-|OS| tercile vs +0.000050 in "
                               "the near-average tercile (F_B). MAE improves by 0.062 "
                               "rim attempts/game in the extreme tercile and is slightly "
                               "WORSE in the near-average tercile. An abstention rule on "
                               "|OS| is therefore supported."),
        "mechanical_caveat": ("A higher dR2 in the extreme-|OS| tercile is PARTLY "
                              "MECHANICAL -- the regressor has more variance there. It "
                              "says where the model ACTS, which is what abstention "
                              "needs; it is NOT evidence of a heterogeneous slope."),
        "asymmetry": ("On the SIGNED split the increment is larger against rim-STINGY "
                      "defences (dR2 +0.038389, MAE -0.08534) than against rim-permissive "
                      "ones (dR2 +0.015007, MAE +0.01452 -- i.e. MAE gets WORSE). Not "
                      "preselected as a hypothesis; reported because it was computed."),
        "role_concentration": ("Broad-based, consistent with the parent's finding of no "
                               "high-usage pocket: low +0.012903, mid +0.018926, high "
                               "+0.017429 (F_B)."),
        "minutes_stability_surprise": ("The signal is WEAKER for stable-minutes players "
                                       "(+0.010143) than for mid (+0.022148) or volatile "
                                       "(+0.018578) ones -- the opposite of the obvious "
                                       "guess, and consistent with the parent's warning "
                                       "not to assume where the pocket is.")},

    # ------------------------------------------------------------------- FALSIFICATION
    "falsification_tests": {
        "volume_placebo": {
            "construction": "the identical FGAhat*OS_rim term applied to realised TOTAL "
                            "attempts instead of RIM attempts. If OS_rim were a pace "
                            "proxy rather than a mix signal it would predict total FGA.",
            "results": A["volume_placebo"],
            "reading": ("F_B: rim dR2 +0.016853 vs TOTAL-attempts dR2 -0.000309 (ratio "
                        "-1.8%). The signal is a mix signal, not a disguised pace or "
                        "volume signal.")},
        "degradation_curve": {
            "construction": "FGAhat(lam) = lam*F_B + (1-lam)*F_LG, tracing the end-to-end "
                            "dR2 against the attempts forecast's own R2.",
            "results": A["degradation_curve"],
            "reading": ("The end-to-end dR2 is essentially FLAT in attempts-forecast "
                        "quality: +0.016140 with a forecast carrying NO player "
                        "information at all (own R2 -0.364), +0.017429 at the interior "
                        "optimum, +0.016853 at the headline forecast, +0.018905 with "
                        "perfect realised FGA. This is the direct answer to the screen's "
                        "question: FGA forecast error does NOT swamp the mix effect, "
                        "because the two error sources are close to orthogonal.")},
        "all_forecast_variants": A["all_forecast_variants"],
        "min_train_sensitivity": A["min_train_sensitivity"],
        "defective_no_op_placebo": ("Run on purpose on every cell. Permuting the grouping "
                                    "KEY and recomputing the aggregate from it is a "
                                    "bijective relabel, so every row keeps its own true "
                                    "value. Signature confirmed: sd = 0.000e+00 and "
                                    "max|dev| = 0.000e+00 on all 5 zones x 2 forecasts "
                                    "and on all 4 points cells -- bitwise zero, no LAPACK "
                                    "noise. It tests nothing; it is here so the genuine "
                                    "controls can be seen to be genuine by contrast.")},

    # -------------------------------------------------------------------- PROVENANCE
    "provenance": {
        "manifest_check": {
            "method": "read the sibling <artifact>.manifest.json and inspect the "
                      "asof_granularity COLUMN VALUE; MISSING MANIFEST IS 'UNVERIFIABLE', "
                      "NOT A PASS. Partition checks TEST COLUMN VALUES, never bytes.",
            "manifests_found_under_data": 13,
            "asof_granularity_row": ["data/masters/master_player.parquet",
                                     "data/masters/master_team.parquet"],
            "asof_granularity_artifact_or_season": [
                "data/rapm/rapm_v0.csv", "data/rapm/rapm_walkforward.csv",
                "data/rapm/rapm_walkforward_seasons.csv",
                "data/w1_truth/extraction_resolution.csv",
                "data/w1_truth/player_game_availability.csv",
                "data/w1_truth/roster_asof.csv",
                "data/zone_maps/league_zone_averages.csv",
                "data/zone_maps/player_zone_offense.csv",
                "data/zone_maps/shrinkage_priors.csv",
                "data/zone_maps/team_zone_defense.csv",
                "data/zone_maps/team_zone_offense.csv"],
            "zone_maps": "FORBIDDEN (asof_granularity == 'artifact'). NOT READ. Zones "
                         "derived from the raw per-shot SHOT_ZONE_BASIC label.",
            "sources_read_with_NO_manifest": {
                "data/shotcharts/shots_{2021..2024}_{regular,playoffs}.parquet":
                    "UNVERIFIABLE by manifest. Admitted on structural grounds: the "
                    "season IS the filename and every column is a property of that one "
                    "shot event. No aggregate, no shrunk value, no cross-row derivation.",
                "data/wnba_gamelog_{2021..2024}.parquet":
                    "UNVERIFIABLE by manifest. Admitted on the same structural grounds "
                    "and audited in-script: the three ratio columns were re-derived and "
                    "confirmed to be within-row identities (max|diff| 5.0e-4, the file's "
                    "own rounding); every other column is a raw counting stat of that one "
                    "game. Used for ONE thing -- the player's minutes in strictly prior "
                    "games -- and every headline is also reported with forecasts (F_LG, "
                    "F_A, F_A2) that never touch this source."},
            "column_value_partition_scan_on_gamelogs": "no 2025/2026 hits in any column",
            "structural_violations": 0},
        "constants_preselected": B["constants"],
        "preselected_analysis_choices": E["preselected"],
        "frames_written": ["forecast_frame.parquet (51473 rows, 10307 player-games)",
                           "forecast_frame_pregame_gate.parquet (52461 rows, 10506 "
                           "player-games, gate F_B >= 5)"]},

    "what_could_not_be_established": [
        "No holdout evaluation and no preregistration -- out of E1 scope. 2025/2026 "
        "was never opened.",
        "No market comparison. A +0.29-rim-attempt shift and a 0.023-attempt MAE "
        "improvement have not been compared to any prop line, so exploitability is "
        "still untested. Nothing here says the effect is priced or unpriced.",
        "The points result is a MAGNITUDE finding on THIS construction. A different "
        "points pipeline -- one that also forecast free-throw volume, or that used the "
        "mix signal to move a variance/distribution rather than a mean -- was not built "
        "and could in principle do better. What is established is that the mean-points "
        "channel through zone mix is ~0.2 points wide.",
        "The zone-conversion rates q_z are shrunk prior-games player rates and were not "
        "themselves opponent-adjusted; the parent's separate conversion channel was not "
        "layered in here.",
        "48 opponent-team-season clusters is the resolution limit: p = 0.0002 means 'no "
        "draw in 5000 reached it', not a point estimate.",
        "Free-throw volume, rest, home/away, injuries and lineup were not conditioned "
        "on anywhere."]}

json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print("wrote FINDINGS.json")
print(f"  verdict            : {F['verdict']}")
print(f"  decisive number    : wf dR2 (F_B, no realised FGA) = "
      f"{F['step3_end_to_end_zone_attempt_counts']['HEADLINE_RA_walkforward_dR2_F_B']:+.6f}")
print(f"  conditional parent : {F['step3_end_to_end_zone_attempt_counts']['conditional_comparator_pooled_realised_FGA']:+.6f}")
print(f"  retained           : "
      f"{100 * F['step3_end_to_end_zone_attempt_counts']['fraction_of_the_conditional_increment_retained_F_B']:.1f}%")
print(f"  points (fg_pts)    : {F['step4_player_points']['HEADLINE_fg_points_walkforward_dR2_F_B']:+.6f} "
      f"p={F['step4_player_points']['HEADLINE_fg_points_p_cluster_level']:.4f}")
print(f"  reproduction delta : {F['step1_reproduction']['abs_diff_from_independent_raw_rebuild']:.3e}")
