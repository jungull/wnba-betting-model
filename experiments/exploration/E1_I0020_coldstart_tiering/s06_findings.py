"""E1_I0020 STEP 8 -- assemble FINDINGS.json from the artifacts written by s01-s05."""
import json
import os

import numpy as np
import pandas as pd

import ct_base as B


def rd(n):
    return pd.read_csv(os.path.join(B.OUT, n))


def js(n):
    with open(os.path.join(B.OUT, n)) as fh:
        return json.load(fh)


s01, s02, s02b = js("_s01.json"), js("_s02.json"), js("_s02b.json")
s03, s04, s05 = js("_s03.json"), js("_s04.json"), js("_s05.json")
R = rd("placeholder_comparison.csv")
DEC = rd("d087_decomposition.csv")
CMP = rd("component_decomposition.csv")
PN = rd("permutation_nulls.csv")
Z = rd("zero_games_case.csv")
CR = rd("handover_curve.csv")
P = rd("pooled_operating_rule.csv")
SS = rd("per_season_stability.csv")


def pick(df, **kw):
    d = df
    for k, v in kw.items():
        d = d[d[k] == v]
    return d.iloc[0].to_dict() if len(d) else None


F = {}
F["screen"] = "E1_I0020_coldstart_tiering"
F["question"] = ("USER, VERBATIM: 'we should categorise players by ones we have sufficient data to "
                 "model and ones that will have to be given a smart filler score maybe rookies get "
                 "a placeholder based on their position on the team and draft position.'")
F["partition"] = {
    "scored_seasons": B.SCREEN_SEASONS,
    "prior_pool_seed_season": 2021,
    "why_2021_is_not_scored": ("D076 established the 2021 champion fold is degenerate "
                               "(n_train_rows=0, model_was_fitted=false).  2021 is used ONLY as a "
                               "source of OBSERVED OUTCOMES to seed the walk-forward prior pool for "
                               "the 2022 fold."),
    "holdout_never_read": [2025, 2026],
    "enforcement": ("screenkit.assert_partition on COLUMN VALUES at every load and before every "
                    "write, plus an explicit max-date assertion, plus the K4 adjudication described "
                    "in kit_defects."),
}
F["authorisation"] = {
    "champion_retrained_or_refitted": False,
    "champion_scored_as_is": True,
    "models_fitted_here": ("shrunk group means (position / draft bucket / depth bucket / two "
                           "crosses) on strictly prior seasons; one 3-parameter OLS of production "
                           "on log(draft pick) and a round-2 indicator; one fixed-form shrinkage "
                           "blend weight lam(n)=n/(n+k).  Nothing else."),
}

# ---------------------------------------------------------------- reproduction
F["step1_reproduction"] = {
    "anchor_A_D076_depth_quintile_table": {
        "reproduced": True,
        "worst_absolute_delta_across_whole_table": max(s01["anchorA_max_abs_deltas"].values()),
        "per_column_max_abs_delta": s01["anchorA_max_abs_deltas"],
        "bottom_quintile_skill_minutes": s01["anchorA_table"][0]["skill_minutes"],
        "bottom_quintile_skill_pts": s01["anchorA_table"][0]["skill_pts"],
        "published_values_for_comparison": {"minutes": -0.151, "points": -0.066},
    },
    "anchor_B_D081_coldstart_splice": {
        "reproduced": True,
        "per_column_max_abs_delta": s01["anchorB_max_abs_deltas"],
        "pooled_points_skill_threshold_0": s01["anchorB_table"][0]["pooled_skill_vs_ref"],
        "pooled_points_skill_threshold_3": s01["anchorB_table"][1]["pooled_skill_vs_ref"],
        "p_blockflip_threshold_3": s01["anchorB_table"][1]["p_vs_champion_blockflip"],
    },
    "fallback_row_claim": {
        "briefing_said": "~1,061 fallback rows scoring -18.6%",
        "measured_n": s01["fallback_rows"]["n"],
        "measured_points_skill": s01["fallback_rows"]["skill_pts"],
        "reproduced": True,
    },
    "verdict": "BOTH ANCHORS REPRODUCE TO MACHINE PRECISION.  The screen proceeded.",
}

# ---------------------------------------------------------------- taxonomy
F["step2_taxonomy"] = {
    "tier_variables_all_pregame": ["pl_games_prior", "pl_career_games_prior", "pl_minutes_prior",
                                   "pl_prior_season_games", "pl_is_rookie_window",
                                   "pl_teamgames_since_appear", "depth_bucket"],
    "boundary_derivation": ("NOT a round number.  Taken from where the champion's MAE skill against "
                            "the point-in-time running-mean reference CROSSES ZERO on the "
                            "skill-versus-tier curve: negative at 0,1,2 prior same-season "
                            "appearances, positive and stable from 3 upward."),
    "skill_at_exactly_n_prior_appearances_points": {
        str(int(r["n"])): r["skill_at_pts"] for r in s02["crossover_curve"]
        if r["axis"] == "pl_games_prior" and r["n"] <= 6},
    "skill_at_exactly_n_prior_appearances_minutes": {
        str(int(r["n"])): r["skill_at_minutes"] for r in s02["crossover_curve"]
        if r["axis"] == "pl_games_prior" and r["n"] <= 6},
    "chosen_boundary": ("the champion's OWN pts__is_fallback flag.  It is a strict superset of "
                        "'fewer than 3 prior same-season appearances' (999 rows, ALL flagged) plus "
                        "62 returning-from-absence rows, and ZERO rows with <3 priors escape it."),
    "tier_sizes": {
        "n_rows_data_poor": s02b["fallback_vs_count"]["n_fallback"],
        "pct_of_all_rows": 100.0 * s02b["fallback_vs_count"]["n_fallback"] / 13879,
        "n_rows_lt3_priors": s02b["fallback_vs_count"]["n_lt3"],
        "pct_of_decision_relevant_population_lt3": [
            r["pct_decision"] for r in s02["tier_sizes"] if r["boundary_prior_games_lt"] == 3][0],
        "decision_relevant_definition": ("PRE-GAME: point-in-time running-mean minutes expectation "
                                         ">= 15 (ref_minutes >= 15), 10,042 rows / 72.4%.  The "
                                         "outcome-conditioned version agrees (69.4%) and was NOT "
                                         "used to define anything."),
    },
    "THE_CENTRAL_MECHANICAL_FACT": {
        "what": ("On the data-poor tier the champion emits a CONSTANT.  It is the same filler score "
                 "for every player, in all three seasons."),
        "champion_points_on_tier_mean": s05["tier_forecast_spread"]["pts"]["champion_sd"],
        "champion_points_sd": s05["tier_forecast_spread"]["pts"]["champion_sd"],
        "champion_minutes_sd": s05["tier_forecast_spread"]["minutes"]["champion_sd"],
        "truth_points_sd": s05["tier_forecast_spread"]["pts"]["truth_sd"],
        "rule_points_sd": s05["tier_forecast_spread"]["pts"]["rule_sd"],
        "reading": ("champion sd 0.013 points against a truth sd of 7.2.  The user's 'smart filler "
                    "score' is precisely the thing this constant should be replaced by."),
    },
    "SURPRISE_skill_is_not_monotone": {
        "what": ("Skill is ~0 at ZERO prior appearances, -4.9%/-10.1% (pts/min) at ONE, "
                 "-39.1%/-81.8% at TWO, and back to +2.6%/-3.6% at THREE."),
        "mechanism": ("It is the REFERENCE moving, not the model.  At 0 priors the reference has no "
                      "player information either and both sides are constants, so skill is ~0 by "
                      "construction.  At 1-2 priors the reference has become a sharp player-specific "
                      "estimate while the champion is still emitting its constant."),
        "consequence": ("The damage is where the player HAS one or two observations the model is "
                        "not using, NOT where they have none.  The zero-games cell is 71 rows."),
    },
}

# ---------------------------------------------------------------- placeholders
def block(cell, target):
    sl = R[(R["cell"] == cell) & (R["target"] == target)]
    return {r["placeholder"]: {"mae": r["mae"], "r2_of_forecast": r["r2_placeholder"],
                               "dr2_vs_champion": r["dr2_vs_champion"],
                               "p_cluster_vs_champion": r["p_cluster_vs_champion"],
                               "dr2_vs_P1full_complete_running_mean": r["dr2_vs_P1full"],
                               "p_cluster_vs_P1full": r["p_cluster_vs_P1full"],
                               "p_row_level_NAIVE_vs_P1full": r["p_row_NAIVE_vs_P1full"],
                               "null_sd_inflation_vs_P1full": r["inflation_vs_P1full"]}
            for _, r in sl.iterrows()}


F["step3_placeholders"] = {
    "tier_n": 1061, "tier_clusters": 475,
    "clustering_level": "(season, player_id); row-level null reported alongside for contrast only",
    "n_draws": B.N_DRAWS,
    "TWO_BASELINES_AND_WHY": {
        "P1_ref_D076": ("D076's frozen reference.  It is an expanding mean over THE CHAMPION'S "
                        "SCORED ROWS, and the champion scores only 71 of 479 true first appearances, "
                        "so for 404 of 475 player-seasons its first scored row has no prior row of "
                        "its own frame and the 'running mean' is the LEAGUE MEAN wearing that name."),
        "P1full_running_mean": ("the player's own prior same-season appearances taken from "
                                "master_player, COMPLETE.  *** THIS IS THE CRUDE BASELINE THAT HAS "
                                "TO BE BEATEN. ***"),
        "why_this_matters": ("D087.  Scoring against the incomplete reference would have credited "
                             "the placeholders with a large, significant, permutation-surviving "
                             "increment that was nothing but the reference's blind spot."),
        "size_of_the_illusion_points_dr2": {
            "blend_vs_incomplete_reference": pick(R, cell="TIER_DATA_POOR (fallback)", target="pts",
                                                  placeholder="P5d_blend_k2")["dr2_vs_P1refD076"],
            "blend_vs_complete_running_mean": pick(R, cell="TIER_DATA_POOR (fallback)", target="pts",
                                                   placeholder="P5d_blend_k2")["dr2_vs_P1full"],
        },
    },
    "points": block("TIER_DATA_POOR (fallback)", "pts"),
    "minutes": block("TIER_DATA_POOR (fallback)", "minutes"),
    "points_per_minute": block("TIER_DATA_POOR (fallback)", "ppm"),
    "HEADLINE_ANSWER": {
        "does_a_smarter_placeholder_beat_the_crude_running_mean": (
            "YES, BUT ONLY AS A BLEND, AND THE MARGIN IS MODEST ON MINUTES.  A standalone "
            "structural prior LOSES to the crude complete running mean on every target except in "
            "the zero-games cell."),
        "standalone_draft_prior_vs_complete_running_mean_points_dr2":
            pick(R, cell="TIER_DATA_POOR (fallback)", target="pts",
                 placeholder="P3_draft_ols")["dr2_vs_P1full"],
        "standalone_position_prior_vs_complete_running_mean_points_dr2":
            pick(R, cell="TIER_DATA_POOR (fallback)", target="pts",
                 placeholder="P2_position")["dr2_vs_P1full"],
        "pure_structural_P5c_vs_complete_running_mean_points_dr2":
            pick(R, cell="TIER_DATA_POOR (fallback)", target="pts",
                 placeholder="P5c_additive")["dr2_vs_P1full"],
        "pure_structural_P5c_vs_complete_running_mean_points_p":
            pick(R, cell="TIER_DATA_POOR (fallback)", target="pts",
                 placeholder="P5c_additive")["p_cluster_vs_P1full"],
        "winner": "P5d_blend_k2",
    },
    "shrinkage_k_sensitivity_file": "shrinkage_sensitivity.csv",
}

# ---------------------------------------------------------------- D087 decomposition
dec2_pts = pick(DEC, cell="TIER_DATA_POOR", target="pts", k=2.0)
dec2_min = pick(DEC, cell="TIER_DATA_POOR", target="minutes", k=2.0)
F["step3b_D087_decomposition"] = {
    "the_confound": ("BLEND_STRUCT mixes two mechanisms: SHRINKING a noisy 1-2 game mean toward a "
                     "constant, and the CONTENT of that constant.  The control BLEND_LEAGUE is "
                     "identical in every respect except that it shrinks toward the plain league "
                     "mean."),
    "points_k2": {
        "gain_of_BLEND_STRUCT_over_complete_running_mean": dec2_pts["dr2_STRUCT_vs_P1full"],
        "p": dec2_pts["p_STRUCT_vs_P1full"],
        "gain_of_SHRINKAGE_ALONE_over_complete_running_mean": dec2_pts["dr2_LEAGUE_vs_P1full"],
        "p_shrinkage_alone": dec2_pts["p_LEAGUE_vs_P1full"],
        "gain_of_STRUCTURE_on_top_of_shrinkage": dec2_pts["dr2_STRUCT_vs_LEAGUE"],
        "p_cluster": dec2_pts["p_cluster_STRUCT_vs_LEAGUE"],
        "p_row_level_NAIVE": dec2_pts["p_row_NAIVE_STRUCT_vs_LEAGUE"],
        "null_sd_inflation": dec2_pts["inflation"],
    },
    "minutes_k2": {
        "gain_of_BLEND_STRUCT_over_complete_running_mean": dec2_min["dr2_STRUCT_vs_P1full"],
        "gain_of_SHRINKAGE_ALONE_over_complete_running_mean": dec2_min["dr2_LEAGUE_vs_P1full"],
        "gain_of_STRUCTURE_on_top_of_shrinkage": dec2_min["dr2_STRUCT_vs_LEAGUE"],
        "p_cluster": dec2_min["p_cluster_STRUCT_vs_LEAGUE"],
    },
    "VERDICT": ("SHRINKAGE ALONE CONTRIBUTES NOTHING AND ON MINUTES IT HURTS.  Shrinking toward the "
                "league mean moves points by %+.4f (p=%.3f) and minutes by %+.4f.  ALL of the gain, "
                "and more, comes from WHAT the blend shrinks toward.  The user's proposal is doing "
                "the work."
                % (dec2_pts["dr2_LEAGUE_vs_P1full"], dec2_pts["p_LEAGUE_vs_P1full"],
                   dec2_min["dr2_LEAGUE_vs_P1full"])),
    "component_ladder_points_tier": [
        {"step": r["step"], "r2_of_forecast": r["r2_of_forecast"],
         "dr2_vs_previous": r.get("dr2_vs_previous_step"),
         "p_cluster_vs_previous": r.get("p_cluster_vs_previous")}
        for _, r in CMP[(CMP["cell"] == "TIER_DATA_POOR") & (CMP["target"] == "pts")].iterrows()],
    "component_reading": ("DEPTH-CHART RANK is the dominant component.  DRAFT SLOT adds a real but "
                          "much smaller increment on top of it.  LISTED POSITION adds NOTHING "
                          "(points dR2 -0.0014, p=0.78) and should be dropped."),
}

F["step3c_permutation_nulls"] = {
    "note": ("Correct grouping level chosen with screenkit.detect_grouping_level; the row-level "
             "null is reported alongside with its width ratio.  Cluster-robust SEs are not used "
             "anywhere as a substitute."),
    "levels_found": s04["grouping_levels"],
    "results": PN.to_dict("records"),
    "reading": ("DRAFT SLOT and DEPTH RANK both carry genuine cross-sectional signal (p=0.002 at "
                "the correct level).  LISTED POSITION does NOT (p=0.200 points, 0.150 minutes) -- "
                "it is the one component of the user's proposal that the data does not support."),
    "an_honest_oddity": ("For depth_bucket the CORRECT (game-team) null is NARROWER than the row "
                         "null (ratio 0.74/0.82), the opposite of the usual direction.  That is "
                         "because reshuffling depth slots inside one roster on one night preserves "
                         "that night's depth marginal exactly, which is a more constrained -- and "
                         "here more conservative -- null than a free row shuffle.  Reported rather "
                         "than smoothed over."),
}

# ---------------------------------------------------------------- zero games
def zblock(pop, target):
    sl = Z[(Z["population"] == pop) & (Z["target"] == target)]
    return {r["placeholder"]: {"mae": r["mae"], "dr2_vs_league_mean": r["dr2_vs_league_mean"],
                               "p_cluster": r["p_cluster"]} for _, r in sl.iterrows()}


F["step4_zero_games_case"] = {
    "why_the_contrast_is_vs_the_league_mean": ("At zero prior appearances a same-season running "
                                               "mean does not exist, so the honest comparator is "
                                               "what a system with no player information can do: "
                                               "the league mean."),
    "SELECTION_CAVEAT": {
        "true_first_appearances_in_master_2022_2024": 479,
        "of_those_scored_by_the_champion": 71,
        "coverage": 71.0 / 479.0,
        "meaning": ("The champion produces no scored forecast for 85% of debuts, so every number "
                    "in this section is conditional on that selection.  It also means the "
                    "production system is ALREADY abstaining on most of this population."),
    },
    "zero_same_season_n71_points": zblock("zero_same_season", "pts"),
    "zero_same_season_n71_minutes": zblock("zero_same_season", "minutes"),
    "zero_career_n22_points": zblock("zero_career", "pts"),
    "zero_career_n22_minutes": zblock("zero_career", "minutes"),
    "zero_same_season_but_has_career_n49_points": zblock("zero_same_season_but_has_career", "pts"),
    "VERDICT": ("THIS IS WHERE THE USER'S PROPOSAL HAS NO COMPETITION AND IT WINS BY A LOT.  On the "
                "22 rows with literally no prior appearance, the draft+depth prior beats the league "
                "mean by dR2 +1.16 on points (p=0.007) and +1.17 on minutes (p=0.003), while the "
                "champion beats it by +0.0008 / -0.029.  The draft prior ALONE gets +1.07 / +0.95.  "
                "But the cell is 22 rows, and 49 of the 71 zero-same-season rows are veterans with "
                "prior-season history for whom the CAREER mean is the better answer."),
}

F["step5_handover_curve"] = {
    "statistic": ("r2_of_forecast(y, champion) - r2_of_forecast(y, P5d_blend_k2) in bins of prior "
                  "same-season appearances.  POSITIVE = champion ahead.  95% CI from a 2000-draw "
                  "CLUSTER BOOTSTRAP over (season, player_id)."),
    "points": CR[CR["target"] == "pts"].to_dict("records"),
    "minutes": CR[CR["target"] == "minutes"].to_dict("records"),
    "CROSSOVER": {
        "minutes": ("6-7 prior appearances -- the first bin whose whole 95% CI is above zero "
                    "(+0.0282, CI [+0.0137, +0.0431]).  4-5 is ambiguous."),
        "points": ("16-24 prior appearances (+0.0136, CI [+0.0038, +0.0244]), and the 25+ bin is "
                   "NOT significant (+0.0062, CI [-0.0035, +0.0165]).  On points the champion "
                   "barely ever pulls clear of the blend."),
        "operating_reading": ("Hand over at 3 prior appearances -- that is where the champion stops "
                              "emitting its constant and its own path switches on.  Between 3 and 5 "
                              "the blend is still slightly ahead on points; from 6 the champion is "
                              "clearly ahead on minutes.  A conservative rule hands over at 3; a "
                              "points-optimal rule hands over at 6."),
    },
}

F["step6_recommended_rule_priced"] = {
    "rule": ("IF pts__is_fallback THEN forecast = lam(n)*own_complete_running_mean + "
             "(1-lam(n))*(league_prior + depth_deviation + draft_deviation), lam(n)=n/(n+2), "
             "n = prior same-season appearances.  ELSE keep the champion untouched."),
    "pooled": P.to_dict("records"),
    "headline_points": {
        "champion_pooled_skill_vs_refD076": pick(P, target="pts",
                                                 variant="champion_untouched")["pooled_skill_vs_refD076"],
        "D081_crude_splice": pick(P, target="pts",
                                  variant="D081_crude_splice_refD076")["pooled_skill_vs_refD076"],
        "crude_splice_with_COMPLETE_running_mean": pick(
            P, target="pts",
            variant="crude_splice_COMPLETE_running_mean")["pooled_skill_vs_refD076"],
        "RECOMMENDED": pick(P, target="pts",
                            variant="RECOMMENDED_blend_splice")["pooled_skill_vs_refD076"],
        "dr2_of_rule_over_champion": pick(P, target="pts",
                                          variant="RECOMMENDED_blend_splice")["dr2_vs_champion"],
        "p": pick(P, target="pts", variant="RECOMMENDED_blend_splice")["p_vs_champion"],
        "dr2_of_rule_over_the_CRUDE_splice": pick(
            P, target="pts", variant="RECOMMENDED_blend_splice")["dr2_vs_crude_complete"],
        "p_over_crude": pick(P, target="pts",
                             variant="RECOMMENDED_blend_splice")["p_vs_crude_complete"],
    },
    "per_season_stability": SS.to_dict("records"),
    "per_season_reading": ("The rule beats the untouched champion in all three seasons on both "
                           "targets, every p = 0.0005.  Against the CRUDE complete-running-mean "
                           "splice it is significant on points in all three seasons but NOT on "
                           "minutes in any single season -- the minutes increment is real pooled "
                           "and small per fold."),
}

F["controls"] = {
    "noop_placebo": s01["noop_placebo"],
    "negative_control_self_comparison": s01["negctrl_self_comparison"],
    "negative_control_pure_noise": s01["negctrl_pure_noise"],
    "negative_control_random_tier": s05["negative_control_random_tier"],
    "random_tier_reading": ("Applying the same blend to a RANDOM 7.6% of rows gains dR2 +0.0028 "
                            "(sd 0.0010, max 0.0065) on points against the real tier's +0.0348.  "
                            "The gain is located in the tier, not in the blend being better "
                            "everywhere."),
}

F["kit_defects"] = {
    "K4_assert_partition_raises_on_clean_data": {
        "severity": "HIGH -- a guard that rejects correct data trains callers to disable it",
        "summary": ("screenkit.assert_partition raises PartitionViolation on a frame whose every "
                    "observation is inside 2021-2024, whenever the frame carries a year-valued "
                    "player attribute such as draft_year (values 2002-2020), because such a year "
                    "legitimately PREDATES the partition."),
        "not_a_repeat_of_K0": ("K0 was a NAME match with no value gate.  K4 SATISFIES the K0 "
                               "invariant: the value gate is asked 'are these years?' and answers "
                               "YES correctly.  The defect is that the partition needs to know "
                               "'is this the OBSERVATION SEASON of the row?', which is a different "
                               "question that every year-valued attribute answers NO to."),
        "direction_is_ignored": ("The guard exists to stop 2025/2026 -- the FUTURE -- entering. "
                                 "draft_year=2008 cannot be a holdout leak.  The current code "
                                 "returns both cases as identically-shaped violation STRINGS, so a "
                                 "caller cannot distinguish them without parsing the guard's own "
                                 "prose, which is the textual check the module forbids."),
        "workaround_is_a_false_pass_door": ("season_cols=['season'] silences the false alarm AND a "
                                            "genuine 2026 leak in any column the caller did not "
                                            "name.  Demonstrated in reproduction 4."),
        "repro": "KIT_DEFECT_K4_REPRO.py (4 reproductions) / run_log_kit_defect_K4.txt",
        "fix_applied_to_kit": False,
        "why_not": ("screenkit.py is outside this screen's write scope and two other agents are "
                    "running against it."),
        "what_this_screen_did_instead": ("ct_base.assert_partition_adjudicated: calls the kit with "
                                         "raise_on_violation=False; any flagged value >= 2025 is "
                                         "FATAL in any column; a flagged column is tolerated only "
                                         "if it is on an explicit one-column allowlist AND every "
                                         "flagged value is strictly earlier than the partition; and "
                                         "the strict unmodified kit check is ALSO run on the frame "
                                         "with the allowlisted column dropped."),
    },
    "K5_nit_permutation_null_refuses_string_categoricals": {
        "severity": "LOW -- correct, safe behaviour with an actionable message; reported as friction",
        "summary": ("permutation_null raises TypeError on a string/categorical feature "
                    "('the kit will not guess an encoding for you').  Group priors over categorical "
                    "labels -- position, draft bucket, depth bucket -- are among the most natural "
                    "things to permute in this program, so most users will hit it."),
        "resolution": ("Not a bug.  The message names the fix and the refusal is the safe failure "
                       "mode.  This screen declared a bijective integer codebook (see "
                       "categorical_codebooks) and mapped back inside stat_fn.  A worked "
                       "categorical example in the kit README would remove the friction."),
        "categorical_codebooks": s04["categorical_codebooks"],
    },
    "kit_functions_used": ["check_manifest", "assert_partition", "r2_of_forecast", "r2_plain",
                           "paired_forecast_comparison", "permutation_null", "detect_grouping_level",
                           "var_share_between", "noop_placebo"],
}

F["manifest_status_honest"] = {
    "master_player.parquet": "USABLE_IF_FILTERED (asof_granularity=row) -- filtered at load",
    "analysis_frame.parquet": "UNVERIFIABLE (no manifest) -- frozen D076 output, value-checked here",
    "decomp_frame.parquet": "UNVERIFIABLE (no manifest) -- frozen D081 output, value-checked here",
    "player_bios.csv": ("UNVERIFIABLE (no manifest).  NEVER TREATED AS A PASS.  Used on an explicit "
                        "structural argument tested on COLUMN VALUES: age advances by exactly +1 "
                        "across 100% of consecutive player-season pairs inside 2021-2024, and "
                        "height/weight vary within player across seasons -- neither is possible "
                        "from a replicated current-state pull.  draft_year/round/number are "
                        "constant within player, as immutable facts must be."),
    "residual_caveat_not_resolved": ("position_raw varies within player in 0.00% of cases, so this "
                                     "screen CANNOT distinguish 'position never changes' from "
                                     "'position is a current-state field replicated backwards'.  "
                                     "This is defused by the result rather than by evidence: the "
                                     "position prior carries no signal (permutation p = 0.20) and "
                                     "is dropped from the recommendation."),
    "forbidden_artifacts_not_opened": ["data/w1_truth/player_game_availability.csv",
                                       "data/w1_truth/roster_asof.csv"],
    "availability_rebuilt_from": "master_player box membership, as D076 did",
}

F["files_written"] = sorted(os.listdir(B.OUT))
B.jdump(F, "FINDINGS.json")
print("FINDINGS.json written with %d top-level keys" % len(F))
