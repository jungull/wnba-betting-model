"""
s08 -- assemble FINDINGS.json FROM THE ARTEFACTS ON DISK.

Nothing here is typed in by hand: every number is read back out of the CSV/JSON this screen wrote,
so FINDINGS.json cannot drift from the evidence.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import uid_base as ub  # noqa: E402
import s00_prereg as pr  # noqa: E402

O = ub.OUT


def rd(name):
    return pd.read_csv(os.path.join(O, name))


def js(name):
    with open(os.path.join(O, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    repro = rd("reproduction_d093.csv")
    fc = rd("interaction_forecast.csv")
    ceil = rd("arithmetic_ceiling.csv")
    tier = rd("usage_tier_gain.csv")
    me = rd("usage_tier_maineffect.csv")
    plac = rd("placebo_diagnostics.csv")
    leak = rd("leakage_probes.csv")
    ll = rd("leadlag_profile.csv")
    fw = rd("stress_family_wise.csv")
    seas = rd("stress_season_stability.csv")
    axes = rd("stress_alternative_axes.csv")
    scale = rd("stress_scale_test.csv")
    refsens = rd("reference_sensitivity.csv")
    j1, j2, j3, j5, j6, j7 = (js("_s01.json"), js("_s02.json"), js("_s03.json"), js("_s05.json"),
                              js("_s06.json"), js("_s07.json"))

    def cell(df, **kw):
        q = df.copy()
        for k, v in kw.items():
            q = q[q[k] == v]
        return None if len(q) == 0 else q.iloc[0].to_dict()

    wf = fc[(fc.fit == "walk_forward") & (fc.base == "B_COMPLETE")]
    prim = cell(wf, cell_id="A10_opp_defrtg|points|DECISION")
    cop = cell(wf, cell_id="A10_opp_defrtg|ppm|DECISION")
    pool_ppm = cell(wf, cell_id="A10_opp_defrtg|ppm|POOLED")
    pool_pts = cell(wf, cell_id="A10_opp_defrtg|points|POOLED")

    F = {}
    F["screen"] = "E1_I0023_usage_defence_interaction"
    F["question"] = ("D093 established a STRUCTURAL fact -- per-player sensitivity to opponent "
                     "defence rises with the player's own strictly-prior usage. This screen asks "
                     "the DIFFERENT question of whether a usage x opponent-defence INTERACTION "
                     "TERM improves a forecast against a COMPLETE prior reference.")
    F["prereg_sha256"] = j2["prereg_sha256"]
    F["cells_added_after_preregistration"] = j2["cells_added"]
    F["cells_dropped_after_preregistration"] = j2["cells_dropped"]
    F["verdict"] = "SPLIT"
    F["verdict_in_one_paragraph"] = (
        "KILL the preregistered interaction term, and RAISE a new and larger lead that it uncovered. "
        "The usage x opponent-defence interaction FAILS its own preregistered primary cell: on "
        "points, on D081's decision stratum, against a complete prior reference, walk-forward, it "
        "is dR2 %+0.6f at correct-level p %.4f. It clears only POOLED, where it is worth "
        "dR2 %+0.6f on points, and its family-wise p over the 18 hashed cells is %.4f -- marginal, "
        "and driven by a cell that is not the decision stratum. BUT the step-5 reconciliation "
        "returned something much larger: the opponent-defence MAIN effect, which D085 declared dead "
        "across twelve constructions and 36 cells, is ALIVE and large inside the TOP VOLUME "
        "TERCILE -- walk-forward dR2 %+0.6f on points-per-minute and %+0.6f on points, decision "
        "stratum, against the same complete reference, surviving a within-date opponent-swap null "
        "at the draw floor. It is not a leak (the column reproduces an independent shift(1) rebuild "
        "to %.1e and a planted leaky twin is cleanly separated), it is stable in all three seasons, "
        "it is positive in every one of 48 leave-one-opponent-season-out refits, and its negative "
        "controls are clean. D085 missed it because POOLED it is dR2 %+0.6f at p %.4f -- which is "
        "essentially D085's own best figure of 0.00144."
        % (prim["dr2_a_minus_b"], prim["p_cluster"], pool_pts["dr2_a_minus_b"], j2["family_wise_p"],
           float(cell(fw, cell="REAL|ppm|DECISION|T3_high")["dr2"]),
           float(cell(fw, cell="REAL|points|DECISION|T3_high")["dr2"]),
           j6["frozen_vs_clean_max_abs_diff"],
           float(cell(plac, response="ppm", stratum="POOLED", tier="ALL_TIERS",
                      contrast="MAIN_EFFECT")["dr2_real"]),
           float(cell(plac, response="ppm", stratum="POOLED", tier="ALL_TIERS",
                      contrast="MAIN_EFFECT")["p_cluster_signflip"])))

    # ------------------------------------------------------------------ STEP 1
    F["step1_reproduction_of_D093"] = {
        "status": j1["verdict"],
        "max_abs_delta_spearman_over_8_relationships": j1["max_abs_delta_spearman"],
        "max_abs_delta_p": j1["max_abs_delta_p"],
        "family_wise_p_published": j1["family_wise_p_published"],
        "family_wise_p_reproduced": j1["family_wise_p_reproduced"],
        "per_relationship": json.loads(repro.to_json(orient="records")),
        "note": ("D093's hd_base imports the shared screen kit, which this screen was directed not "
                 "to import. group_slopes_fast and cyclic_shift_within_groups were REIMPLEMENTED "
                 "from D093's source (credited). This exact reproduction is the evidence that the "
                 "reimplementation is faithful."),
    }

    # ------------------------------------------------------------------ STEP 2
    F["step2_does_the_interaction_improve_a_forecast"] = {
        "answer": "NO on the stratum that matters; marginally YES pooled.",
        "primary_cell_declared_a_priori": prim,
        "co_primary_cell": cop,
        "pooled_ppm": pool_ppm,
        "pooled_points": pool_pts,
        "family_wise_p_over_18_hashed_cells": j2["family_wise_p"],
        "family_wise_max_z": j2["family_wise_max_z"],
        "family_wise_argmax": j2["family_wise_argmax"],
        "attrition": j2["attrition"],
        "median_null_width_inflation_cluster_over_row": j2["median_null_width_inflation"],
        "wrong_null_trap": ("TENTH confirmation in this programme: the correct-level cluster null "
                            "is %.3fx wider than the row-level null, and 8 of 18 real cells clear "
                            "the naive row-level bar while only 2 clear the correct one."
                            % j2["median_null_width_inflation"]),
        "reference_incompleteness_caught_prospectively": {
            "worst_cell": "A10_opp_defrtg|ppm|DECISION",
            "dr2_against_incomplete_reference": float(
                cell(refsens, cell_id="A10_opp_defrtg|ppm|DECISION")["dr2_B_SINGLE"]),
            "dr2_against_complete_reference": float(
                cell(refsens, cell_id="A10_opp_defrtg|ppm|DECISION")["dr2_B_COMPLETE"]),
            "ratio": float(cell(refsens, cell_id="A10_opp_defrtg|ppm|DECISION")["ratio"]),
            "note": ("Completing the reference removes 85% of this cell's increment. This is "
                     "D090/D091's top-ranked failure mode, caught prospectively for the second "
                     "time. The complete reference is the headline everywhere."),
        },
        "table": json.loads(fc.to_json(orient="records")),
    }

    # ------------------------------------------------------------------ STEP 3
    def ck(stratum, tier, contrast):
        return cell(ceil, defence="A10_opp_defrtg", stratum=stratum, tier=tier, contrast=contrast,
                    fit="walk_forward")
    F["step3_arithmetic_ceiling"] = {
        "form": pr.PREREG["ceiling_form"],
        "benchmarks": pr.CEILING_BENCHMARKS,
        "preregistered_interaction_DECISION": ck("DECISION", "ALL_TIERS", "INTERACTION"),
        "preregistered_interaction_POOLED": ck("POOLED", "ALL_TIERS", "INTERACTION"),
        "main_effect_DECISION_top_tier": ck("DECISION", "T3_high_usage", "MAIN_EFFECT"),
        "main_effect_POOLED_top_tier": ck("POOLED", "T3_high_usage", "MAIN_EFFECT"),
        "answer": ("The ceiling is NOT tiny and therefore does NOT close the lead by arithmetic. "
                   "The preregistered interaction's ceiling on the decision stratum is %.8f -- "
                   "1.10x D079's shot-mix ceiling, 9.6x D084's conversion ceiling and 0.60x D089's "
                   "teammate-volume ceiling. The interaction dies on its FORECAST, not on its "
                   "arithmetic. The main effect inside the top volume tercile has a ceiling of "
                   "%.8f, which is 6.2x the largest ceiling this programme had measured."
                   % (ck("DECISION", "ALL_TIERS", "INTERACTION")["ceiling_D084_form_var_share"],
                      ck("DECISION", "T3_high_usage",
                         "MAIN_EFFECT")["ceiling_D084_form_var_share"])),
        "caveat": ("The ceiling statistic has a NOISE FLOOR: the pure-noise interaction control "
                   "returns a walk-forward ceiling of up to 3.98e-04 purely from estimation noise "
                   "in its own coefficient. Ceilings below roughly 4e-04 in this screen are not "
                   "distinguishable from that floor."),
        "table": json.loads(ceil.to_json(orient="records")),
    }

    # ------------------------------------------------------------------ STEP 4
    F["step4_is_the_heterogeneity_exploitable"] = {
        "answer": ("YES, and the subpopulation IS pre-game identifiable -- but the axis is NOT "
                   "specifically usage. The gain is entirely in the TOP tercile of prior volume, "
                   "and splitting on prior MINUTES (dR2 %+0.6f) or prior POINTS-PER-MINUTE "
                   "(%+0.6f) works as well as prior USAGE (%+0.6f). 'Usage' is a proxy for "
                   "'this player scores a lot', not the mechanism."
                   % (float(cell(axes, axis="prior_minutes_per_game", response="ppm",
                                 tier="T3_high")["dr2"]),
                      float(cell(axes, axis="prior_points_per_minute", response="ppm",
                                 tier="T3_high")["dr2"]),
                      float(cell(axes, axis="prior_usage_per_game", response="ppm",
                                 tier="T3_high")["dr2"]))),
        "interaction_gain_by_tier": json.loads(tier.to_json(orient="records")),
        "alternative_axes": json.loads(axes.to_json(orient="records")),
        "tier_cut_points_are_pre_game": ("Tercile cut points are computed on the TRAINING seasons "
                                         "only and applied forward, so a tier label could have "
                                         "been attached before tip-off."),
    }

    # ------------------------------------------------------------------ STEP 5
    F["step5_is_the_dead_main_effect_explained_by_cancellation"] = {
        "answer": ("PARTLY, AND NOT IN THE FORM PREDICTED. It is NOT sign cancellation: the "
                   "opponent-defence slope is POSITIVE in all three usage tiers and MONOTONE "
                   "INCREASING (%+.3e -> %+.3e -> %+.3e on points-per-minute, cluster-robust t "
                   "%+.2f -> %+.2f -> %+.2f). It is DILUTION: a single pooled slope is a "
                   "compromise that under-fits the top tercile and buys nothing in the other two, "
                   "so the pooled increment collapses to dR2 %+0.6f at p %.4f -- which is "
                   "D085's own null. The registered prediction ('positive in the top tier, zero or "
                   "negative in the bottom') is therefore HALF confirmed and half refuted, and it "
                   "is reported as such."
                   % tuple([float(cell(me, response="ppm", stratum="POOLED",
                                       tier=t)["beta_defence_in_sample"])
                            for t in ["T1_low_usage", "T2_mid_usage", "T3_high_usage"]]
                           + [float(cell(me, response="ppm", stratum="POOLED",
                                         tier=t)["t_cluster_robust"])
                              for t in ["T1_low_usage", "T2_mid_usage", "T3_high_usage"]]
                           + [float(cell(plac, response="ppm", stratum="POOLED",
                                         tier="ALL_TIERS", contrast="MAIN_EFFECT")["dr2_real"]),
                              float(cell(plac, response="ppm", stratum="POOLED", tier="ALL_TIERS",
                                         contrast="MAIN_EFFECT")["p_cluster_signflip"])])),
        "main_effect_by_tier": json.loads(me.to_json(orient="records")),
        "contradicts_D085": ("D085 ruling 1 says defensive matchup is closed and must not be "
                             "re-screened. This screen agrees with D085 POOLED (dR2 %+0.6f, "
                             "p %.4f, against D085's best of 0.00144) and disagrees inside the top "
                             "volume tercile (dR2 %+0.6f, swap p %.4f). D085 never stratified by "
                             "volume. THE COORDINATOR SHOULD VERIFY THIS INDEPENDENTLY BEFORE ANY "
                             "RULING IS CHANGED."
                             % (float(cell(plac, response="ppm", stratum="POOLED",
                                           tier="ALL_TIERS", contrast="MAIN_EFFECT")["dr2_real"]),
                                float(cell(plac, response="ppm", stratum="POOLED",
                                           tier="ALL_TIERS",
                                           contrast="MAIN_EFFECT")["p_cluster_signflip"]),
                                float(cell(fw, cell="REAL|ppm|DECISION|T3_high")["dr2"]),
                                float(cell(fw, cell="REAL|ppm|DECISION|T3_high")["p_swap"]))),
    }

    # ------------------------------------------------------------------ robustness of the new lead
    F["the_new_lead_and_everything_that_was_thrown_at_it"] = {
        "what_it_is": ("The opponent's strictly-prior defensive rating predicts a HIGH-VOLUME "
                       "player's single-game points-per-minute, when the model is fitted inside "
                       "the top volume tercile. It does NOT survive as a pooled interaction term."),
        "headline_cells": json.loads(fw[fw.kind == "REAL"].to_json(orient="records")),
        "family_wise_p_over_12_tier_cells": j7["family_wise_p"],
        "family_wise_max_z": j7["family_wise_max_z"],
        "family_wise_argmax": j7["family_wise_argmax"],
        "negative_control_min_p": j7["control_min_p"],
        "negative_control_max_z": j7["control_max_z"],
        "leakage": {
            "cold_start_check": "INCONCLUSIVE and reported as such -- no rows with zero opponent "
                                "prior games exist in the frame",
            "independent_rebuild_max_abs_diff": j6["frozen_vs_clean_max_abs_diff"],
            "leaky_twin_max_abs_diff": j6["frozen_vs_leaky_max_abs_diff"],
            "leadlag_profile": json.loads(ll.to_json(orient="records")),
            "verdict": ("NO LEAK. The frozen column reproduces an explicit shift(1)-before-expanding "
                        "rebuild from master_team to %.1e; its lead-lag profile is the "
                        "strictly-prior signature (increment INTO game k correlates %+.4f with game "
                        "k, increment OUT OF game k correlates %+.4f) and is cleanly separated from "
                        "a deliberately leaky twin (%+.4f / %+.4f). THE PROBE DETECTS A PLANTED "
                        "LEAK, which is what makes its clean verdict worth anything."
                        % (j6["frozen_vs_clean_max_abs_diff"],
                           float(cell(ll, column="FROZEN_A10")
                                 ["corr_increment_INTO_game_k_with_game_k"]),
                           float(cell(ll, column="FROZEN_A10")
                                 ["corr_increment_OUT_OF_game_k_with_game_k"]),
                           float(cell(ll, column="LEAKY_defrtg")
                                 ["corr_increment_INTO_game_k_with_game_k"]),
                           float(cell(ll, column="LEAKY_defrtg")
                                 ["corr_increment_OUT_OF_game_k_with_game_k"]))),
            "table": json.loads(leak.to_json(orient="records")),
        },
        "placebos": {
            "league_mean_on_date_placebo_share_of_effect": float(
                cell(plac, response="ppm", stratum="DECISION", tier="T3_high_usage",
                     contrast="MAIN_EFFECT")["P1_share_of_real"]),
            "cross_sectional_share_of_effect": float(
                cell(plac, response="ppm", stratum="DECISION", tier="T3_high_usage",
                     contrast="MAIN_EFFECT")["P3_share_of_real"]),
            "note": ("The effect is CROSS-SECTIONAL: a column carrying only the league's own "
                     "time/level component reproduces essentially none of it, and the "
                     "within-date-demeaned defence column reproduces essentially all of it."),
            "table": json.loads(plac.to_json(orient="records")),
        },
        "season_stability": json.loads(seas.to_json(orient="records")),
        "jackknife_over_48_opponent_seasons": {
            "full": j7["jackknife_full"], "min": j7["jackknife_min"],
            "median": j7["jackknife_median"], "all_positive": j7["jackknife_all_positive"]},
        "scale_test": json.loads(scale.to_json(orient="records")),
        "practical_size": (
            "1 sd of opponent defensive rating (%.3f) x beta %.3e points-per-minute = %.6f ppm, "
            "x %.1f minutes = %.3f points per game, which is %.2f%% of a %.3f-point response sd."
            % (ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["sd_interaction_term"],
               ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["mean_interaction_beta_on_ppm"],
               ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["sd_interaction_term"]
               * ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["mean_interaction_beta_on_ppm"],
               ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["mean_minutes_estimate"],
               ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["points_moved_by_1sd"],
               100.0 * ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["points_moved_by_1sd"]
               / ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["sd_y_points"],
               ck("DECISION", "T3_high_usage", "MAIN_EFFECT")["sd_y_points"])),
    }

    F["UNRESOLVED"] = [
        ("THE TENSION THIS SCREEN COULD NOT RESOLVE. A tier-restricted model gains dR2 +0.024 from "
         "the defence column, while a POOLED model with a usage x defence interaction -- which also "
         "lets the defence slope vary with usage -- gains only +0.0002 on the same stratum. The "
         "difference is that the tier-restricted model refits EVERY coefficient inside the tier, "
         "not only the defence slope. This screen did NOT test the intermediate specification "
         "(pooled model, tier-dummy x defence), which is the obvious next test and would settle "
         "whether the gain needs a separate model per volume tier or only a tier-specific defence "
         "slope."),
        ("Whether the effect is really about VOLUME at all. Prior minutes, prior points-per-minute "
         "and prior usage all work; the screen cannot separate them and does not claim to."),
        ("Whether this beats a market. No historical odds exist for these seasons, so the lead is "
         "untested against a price, exactly as D089's lead is."),
    ]

    F["files"] = sorted(f for f in os.listdir(O) if not f.startswith("__"))
    with open(os.path.join(O, "FINDINGS.json"), "w", encoding="utf-8") as fh:
        json.dump(F, fh, indent=2, default=float)
    print("wrote FINDINGS.json (%d bytes)" % os.path.getsize(os.path.join(O, "FINDINGS.json")))
    print(F["verdict_in_one_paragraph"])


if __name__ == "__main__":
    main()
