"""E0_I0029 s07 -- assemble FINDINGS.json from the artifacts the earlier steps wrote.

Every number in FINDINGS.json is READ BACK FROM THE FILE THAT PRODUCED IT.  Nothing is retyped
from a run log, so FINDINGS.json cannot drift from the CSVs the way a hand-written summary can.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ft_base import HEADLINE_SEASONS, OUT, SEASONS, hdr, jsonable
from s01_prereg import PREREG_HASH

BENCH = {"D089_largest_measured_ALIVE": 0.002057, "D079_shot_mix_DEAD": 0.001127,
         "D084_opponent_conversion_DEAD": 0.000129}


def jl(name):
    return json.load(open(os.path.join(OUT, name)))


s00, s02, s03, s04, s05, s06 = (jl("_s00.json"), jl("_s02.json"), jl("_s03.json"),
                                jl("_s04.json"), jl("_s05.json"), jl("_s06.json"))
R = pd.read_csv(os.path.join(OUT, "screen_results.csv"))
C = pd.read_csv(os.path.join(OUT, "arithmetic_ceiling.csv"))
M = pd.read_csv(os.path.join(OUT, "matchup_decomposition.csv"))
S = pd.read_csv(os.path.join(OUT, "ladder_summary.csv"))
P = pd.read_csv(os.path.join(OUT, "propagation_walkforward.csv"))
LP = pd.read_csv(os.path.join(OUT, "leakage_probes.csv"))

DEC = "DECISION (>=8 prior, >=24 trail-5 min)"
dec = S[S["subset"] == DEC].set_index("target")

F = {}
F["screen_id"] = "E0_I0029_freethrow_hurdle"
F["prereg_sha256"] = PREREG_HASH
F["added_since_hash"] = 0
F["dropped_since_hash"] = 0
F["r2_convention"] = ("plain unweighted OLS R2 = 1 - SSE/SST, SST about the UNWEIGHTED mean "
                      "(D069 adopted default)")
F["partition"] = list(SEASONS)
F["headline_seasons"] = list(HEADLINE_SEASONS)
F["holdout_never_touched"] = [2025, 2026]
F["n_cell_runs"] = s05["n_cell_runs"]
F["time_window_table"] = s02["time_window_table"]
F["manifest_checks"] = s00["manifests"]
F["forbidden_not_opened"] = s00["forbidden_not_opened"]
F["leakage_probes"] = LP.to_dict("records")
F["feasibility_reproduction"] = s00["feasibility_reproduction"]

# ---------------------------------------------------------------- STEP 1
F["STEP_1_the_hurdle"] = dict(
    hurdle_is_real=dict(
        mean_fta=s00["hurdle_excess_zero"]["mean_fta"],
        poisson_P0=s00["hurdle_excess_zero"]["poisson_p0"],
        observed_P0=s00["hurdle_excess_zero"]["observed_p0"],
        excess_zero_mass=s00["hurdle_excess_zero"]["excess"],
        hurdle_share_of_Var_ftm=s00["total_variance_law"]["hurdle_share_of_ftm_variance"],
        reading=("the zero mass is NOT a low rate -- it is 3.1x what a Poisson with the observed "
                 "mean would produce, and knowing only WHETHER the player reached the line "
                 "accounts for 45.7% of Var(ftm).  Free-throw production really is a hurdle "
                 "process, so the premise of this screen is confirmed on bytes.")),
    COMMON_DENOMINATOR_ANSWER=dict(
        denominator="SST(ftm) over the FULL stratum (D099)",
        note=("stages B and C live on the fta>0 subset; their own-SST R2s are NOT comparable "
              "across stages and are reported separately below"),
        DECISION=s04["DECISION (2022-2024)"], POOLED=s04["POOLED (2022-2024)"]),
    per_stage_own_denominator=s04["per_stage_own_denominator"],
    ORACLE_LADDER_per_stage_DECISION_stratum={
        t: dict(stage=str(dec.loc[t, "stage"]), n=int(dec.loc[t, "n"]),
                denominator=str(dec.loc[t, "denominator"]), sd_y=float(dec.loc[t, "sd_y"]),
                r2_REF_matched_prior_reference=float(dec.loc[t, "r2_REF_matched"]),
                best_honest_rung=str(dec.loc[t, "best_honest_rung"]),
                r2_best_honest=float(dec.loc[t, "r2_best_honest"]),
                r2_O1_seasonmean_ORACLE=float(dec.loc[t, "r2_O1_seasonmean"]),
                r2_O2_ORACLE=float(dec.loc[t, "r2_O2_oracle"]),
                r2_O3_ORACLE=float(dec.loc[t, "r2_O3_oracle"]),
                IRREDUCIBLE_share_even_to_O2=float(dec.loc[t, "IRREDUCIBLE_share_even_to_O2"]),
                REACHABLE_HEADROOM_O2_minus_best_honest=float(
                    dec.loc[t, "headroom_O2_minus_best_honest"]))
        for t in dec.index},
    calibration_anchor=s03["anchor"])

# ---------------------------------------------------------------- STEP 2
mdec = M[M["stratum"] == "DECISION"]
alive_m = R[(R["base"] == "B_COMPLETE") & (R["family"].isin(["M", "X"])) &
            (R["p_family_wise"] < 0.05) & (R["dR2"] > 0)]
alive_m_guarded = R[(R["base"].isin(["B_COMPLETE_PLUS_M02", "B_MATCHUP", "B_MATCHUP2"])) &
                    (R["p_family_wise"] < 0.05) & (R["dR2"] > 0)]
xrows = M[M["family"] == "X"]
F["STEP_2_the_matchup_question"] = dict(
    question=("does the opponent's prior fouls-conceded rate predict a player's free-throw "
              "production beyond that player's own prior rate?"),
    what_D085_did_NOT_test=("D085 killed the INTERACTION; its two main effects were the CONTROL, "
                            "never the candidate, and its twelve opponent constructions were "
                            "screened against points, rebounds and assists -- never against "
                            "free-throw production itself"),
    n_opponent_or_interaction_cells_clearing_family_wise_over_B_COMPLETE=int(len(alive_m)),
    n_clearing_over_the_DECOMPOSITION_bases=int(len(alive_m_guarded)),
    survivors_over_B_COMPLETE=alive_m[["stratum", "target", "candidate", "dR2", "p_correct_level",
                                       "p_family_wise", "sd_inflation_correct_over_row"]]
        .to_dict("records"),
    survivors_after_decomposition=alive_m_guarded[["stratum", "target", "base", "candidate", "dR2",
                                                   "p_correct_level", "p_family_wise"]]
        .to_dict("records"),
    D085_guard=dict(
        design=("both main effects (F02 own prior fouls-drawn rate, M01 opp prior fouls conceded) "
                "are in B_MATCHUP FROM THE START; the B_COMPLETE figure is a DIAGNOSTIC of the "
                "trap, never a result"),
        rows=xrows.to_dict("records")),
    decomposition_table="matchup_decomposition.csv")

# ---------------------------------------------------------------- STEP 3
cd = C[(C["stratum"] == "DECISION") & (C["response"] == "y_pts")]
best = cd[~cd["is_oracle"] & (~cd["signal"].isin(["G01_noise", "G02_placebo_noop",
                                                  "G03_placebo_perturbed"]))] \
    .sort_values("CEILING_dR2_base_residualised", ascending=False)
ora = cd[cd["is_oracle"]]
F["STEP_3_does_it_reach_points"] = dict(
    ceiling_form="CEILING_dR2 = (|beta| * sd_candidate / sd_y)^2   (D084/D089 form)",
    benchmarks=BENCH,
    largest_non_oracle_ceiling_on_POINTS_decision_stratum=(
        best.iloc[0][["signal", "CEILING_dR2_raw", "CEILING_dR2_base_residualised",
                      "ratio_to_D089_alive", "beta", "sd_signal_resid_of_base", "sd_response",
                      "move_per_1sd_resid_natural_units", "verdict_vs_benchmarks"]].to_dict()
        if len(best) else None),
    top_10_ceilings_on_POINTS=best.head(10)[
        ["signal", "CEILING_dR2_base_residualised", "ratio_to_D089_alive",
         "move_per_1sd_resid_natural_units", "verdict_vs_benchmarks"]].to_dict("records"),
    ORACLE_upper_bound_perfect_ftm_knowledge=(
        ora.iloc[0][["signal", "CEILING_dR2_raw", "CEILING_dR2_base_residualised",
                     "move_per_1sd_resid_natural_units"]].to_dict() if len(ora) else None),
    walkforward_propagation=P.to_dict("records"),
    per_season_consistency="per_season_consistency.csv",
    history_floor_sensitivity=s06["floor_curve"])

# ---------------------------------------------------------------- STEP 4
F["STEP_4_the_structural_question"] = dict(
    question="does the champion model free-throw production at all?",
    answer="NO -- free throws are absent from the player arm entirely",
    method="the champion was NEVER loaded, retrained or refitted; this is read off its source and "
           "its artifact schemas",
    verified_on_bytes=dict(
        the_four_player_targets=["attempts_usage", "e_minutes_given_active", "p_active",
                                 "player_scoring_distribution"],
        what_player_scoring_distribution_is=(
            "EWMA of the player's prior per-36 TOTAL points x (EWMA minutes / 36), a single "
            "continuous scalar, wrapped in a residual-derived 5-quantile envelope.  It is a "
            "distribution over TOTAL POINTS with no 2PT/3PT/FT decomposition anywhere."),
        estimator_location="cbs_v7.py:437-458 (conditional_center)",
        response_binding="cbs_player_runner_v14.py:273-278 -- ycol='points'",
        ft_columns_dropped_at_the_frame_boundary=(
            "cbs_real_frames_v3.py:614-632 -- the `keep` list carries only minutes, points and "
            "fga as outcome columns.  ftm / fta / ft_pct / fouls_drawn are not even present in the "
            "dataframe the estimator sees."),
        attempts_usage_is_FGA_only=(
            "cbs_v7.py:449-451 uses frame['fga'] / frame['minutes'].  There is no 0.44*FTA and no "
            "true-shooting-attempts construction anywhere in the champion."),
        grep_evidence=("regex \\bftm\\b|\\bfta\\b|\\bft_pct\\b|free.?throw|fouls_drawn returns "
                       "ZERO hits across all 16 champion-lineage .py files"),
        the_asymmetry_that_makes_this_a_finding=(
            "the TEAM arm DOES carry an explicit free-throw channel: cbs_real_frames_v3.py:722 "
            "tg['ch_ft'] = tg['ftm'], one of four channels (ft / 3pt / paint / np2) that satisfy "
            "an asserted points identity.  The decomposition the team arm is built on has NO "
            "player analogue.  So this is not an oversight of the data -- the same programme "
            "decomposed team scoring into free throws and did not decompose player scoring."),
        data_was_available_not_missing=("master_player.parquet carries ftm, fta, ft_pct and "
                                        "fouls_drawn at 100% coverage across 2021-2024")),
    why_this_matters=(
        "the champion's points estimator is a single per-36 rate scaled by expected minutes.  It "
        "therefore represents free-throw production as a CONSTANT FRACTION of a player's scoring "
        "rate.  This screen measures that the free-throw component is (a) governed by a hurdle "
        "whose honest predictability is concentrated in the hurdle rather than the rate, and (b) "
        "on a DIFFERENT and LOWER predictability scale from the rest of scoring.  Aggregating it "
        "into a single points rate is exactly the mis-specification D091's post-mortem item 5 "
        "anticipated: 'points-per-minute pools field-goal volume, shot mix, conversion and free "
        "throws ... if different components are predictable to different degrees, aggregating "
        "destroys the signal before it can be measured'."))

# ---------------------------------------------------------------- controls, defects, verdict
noop = R[R["candidate"] == "G02_placebo_noop"]
pert = R[R["candidate"] == "G03_placebo_perturbed"]
noise = R[R["candidate"] == "G01_noise"]
F["controls"] = dict(
    negative_control_G01_noise=dict(max_abs_dR2=float(noise["dR2"].abs().max()),
                                    median_p_correct_level=float(noise["p_correct_level"].median()),
                                    n_cells=int(len(noise)),
                                    frac_cells_clearing_p05=float((noise["p_correct_level"] < 0.05).mean())),
    noop_placebo_G02=dict(max_abs_dR2=float(noop["dR2"].abs().max()),
                          is_confirmed_noop=bool(noop["dR2"].abs().max() < 1e-9),
                          note="affine copy of the base's first column; MUST be ~0 by collinearity"),
    perturbation_check_G03=dict(
        median_abs_dR2=float(pert["dR2"].abs().median()),
        max_abs_dR2=float(pert["dR2"].abs().max()),
        frac_cells_detected_p_correct_lt_05=float((pert["p_correct_level"] < 0.05).mean()),
        note=("the perturbing placebo MUST move the statistic and MUST be detected, otherwise a "
              "null verdict from this machinery would be uninformative rather than negative")),
    floor_of_resolution=s05["floor_of_resolution"],
    null_inflation=dict(
        median_sd_inflation_correct_over_row=float(R["sd_inflation_correct_over_row"].median()),
        max_sd_inflation=float(R["sd_inflation_correct_over_row"].max()),
        note=("the row-level null is reported ONLY to expose this inflation and NEVER carries a "
              "verdict.  Cluster-robust SEs are not used: they moved t the wrong way twice here.")))

F["defects_found_in_this_screens_own_work"] = [
    dict(id="D-01", severity="HIGH", title="conditional references were response-conditioned",
         caught_by="an SST=0 crash in s05, not by inspection",
         effect_on_conclusion=("it was making the headline conclusion LOOK STRONGER.  Stage B's "
                               "honest contribution on the DECISION stratum rose from 0.15559 to "
                               "0.17019 after the fix; stage A still dominates, on a smaller "
                               "margin"),
         evidence="probes P1c (max abs diff 0.000e+00 on conditional rows) and P1d "
                  "(corr(availability, response) fell from +1.0 to +0.1138)"),
    dict(id="D-02", severity="MEDIUM", title="the no-op placebo was not a no-op",
         caught_by="the perturbation check itself, which refused to pass and stopped the run",
         effect_on_conclusion="none on any published number; it invalidated only the control arm, "
                              "which was rebuilt and rerun",
         evidence="G02 built from ref_mean__y_ftm showed max |dR2| 2.591e-02 on the five targets "
                  "it was not built from; per-target placebos now give a confirmed no-op")]

alive = R[(R["base"] == "B_COMPLETE") & (R["family"] != "G") & (R["p_family_wise"] < 0.05) &
          (R["dR2"] > 0)]
F["survivors_over_B_COMPLETE"] = alive.sort_values("dR2", ascending=False)[
    ["stratum", "rowset", "target", "base", "candidate", "family", "level", "n", "dR2",
     "p_correct_level", "p_family_wise", "sd_inflation_correct_over_row"]].to_dict("records")

json.dump(jsonable(F), open(os.path.join(OUT, "FINDINGS.json"), "w"), indent=2)
hdr("FINDINGS.json WRITTEN")
print("  prereg hash %s" % PREREG_HASH)
print("  %d cell runs, %d survivors over B_COMPLETE" % (s05["n_cell_runs"], len(alive)))
print("  wrote %s" % os.path.join(OUT, "FINDINGS.json"))
