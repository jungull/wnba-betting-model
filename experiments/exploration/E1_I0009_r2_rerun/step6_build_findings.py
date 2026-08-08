"""STEP 6 -- assemble FINDINGS.json from the step outputs. Writes only inside this directory."""
import json

D = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0009_r2_rerun"
s1 = json.load(open(f"{D}/step1_audit.json"))
s23 = json.load(open(f"{D}/step23_results.json"))
s4 = json.load(open(f"{D}/step4_results.json"))
s5 = json.load(open(f"{D}/step5_results.json"))

F = {}
F["what_this_is"] = (
    "E1 re-measurement of idea I0009 (additive opponent pressure) under the adopted plain-OLS R2 "
    "convention, ordered by decision D069. NON-CLAIMING (GRAPH_POLICY 13.1): no registry entry, "
    "no preregistration, no leaderboard row, no promotion. A LEAD, never a RESULT.")
F["stage"] = "E1 re-run"
F["idea"] = "I0009"
F["family"] = "F_TURNOVER_PRESSURE"
F["partition"] = s1["partition_verification"]
F["manifest_check"] = s1["manifest_check"]

# --------------------------------------------------------------- headline correction
F["PREMISE_CORRECTION"] = dict(
    task_premise="both E0 and E1 analyze.py carry a defective weighted-R2 helper called wls_r2",
    finding_E0="TRUE. wls_r2 at analyze.py lines 40-48 feeds delta_r2 (lines 55-62) and therefore "
               "EVERY dR2 E0 published.",
    finding_E1="FALSE for the published numbers. E1 has no function named wls_r2. Its headline "
               "helper r2_in (lines 68-72) is already the STANDARD weighted R2, and its "
               "out-of-sample helper oos_delta (lines 281-301) uses the standard weighted SST "
               "about the TRAIN weighted mean. The defective form survives in E1 only inside "
               "delta_r2_e0convention (lines 220-228), which exists solely to reproduce E0's "
               "published figures as a frame-identity check and touches no E1 headline number.",
    consequence=("The headline +0.004003 was never a defective-convention number. Correcting the "
                 "SST does not raise it. What actually moves it is dropping the possession "
                 "WEIGHTS, which the adopted plain-OLS convention also requires -- and that moves "
                 "it DOWN by ~79%, not up."))

F["defective_helper_source"] = s1["defective_helper_source"]

# --------------------------------------------------------------- weight/centering audit
F["weight_and_centering_audit"] = dict(
    weights=s1["weights"],
    response=s1["response"],
    mechanism_checks=s1["mechanism_checks"],
    reading=("w = realised_off_possessions: min 1, max 95, mean 42.67, sd 21.21, CV 0.497, "
             "max/min 95x -- HEAVILY DISPERSED. y = turnovers_per_100_off_poss: mean 3.3957, "
             "sd 3.9884, mean/sd 0.8514, strictly non-negative -- NOT CENTERED. Both governing "
             "factors of the D069 defect are present, so a non-zero conservative bias is expected."))

F["analytic_prediction_vs_measurement"] = dict(
    prediction_rule=("Because SSE is identical under both conventions, dR2_defective/dR2_standard "
                     "equals SST_standard/SST_defective EXACTLY, for every model comparison fitted "
                     "on the same rows. SST_standard = sum(w*(y-mu_w)^2); "
                     "SST_defective = sum((sqrt(w)*y - mean(sqrt(w)*y))^2)."),
    predicted_before_measuring=dict(
        pooled_ratio_standard_over_defective=s1["analytic_prediction"]["E1"]["predicted_ratio_standard_over_defective"],
        pooled_predicted_bias_pct=-7.5355793006597,
        per_season_predicted_bias_pct={"2021": -5.770599, "2022": -5.236181,
                                       "2023": -8.775505, "2024": -9.758531}),
    measured=dict(
        pooled_measured_bias_pct=-7.535579,
        per_season_measured_bias_pct={"2021": -5.770599, "2022": -5.236181,
                                      "2023": -8.775505, "2024": -9.758531}),
    max_abs_discrepancy_prediction_vs_measurement_pct=5.04e-12,
    inside_predicted_0_to_25_pct_band=True,
    verdict=("EXACT MATCH to ~5e-12 percentage points. The mechanism is confirmed: the discrepancy "
             "is a pure denominator effect governed by weight dispersion and response non-centering."),
    caveat_on_D069_wording=(
        "D069 states a centered response gives a ratio of EXACTLY 1.0000. Measured here, centering y "
        "at its UNWEIGHTED mean gives 0.99931, not 1.0. Exact cancellation needs BOTH sum(w*y)=0 and "
        "sum(sqrt(w)*y)=0; centering delivers only the second-moment condition approximately, via "
        "corr(y, sqrt(w)) = -0.0496. Uniform weights DO give exactly 1.0000000000. So of the two "
        "stated escape hatches, only the uniform-weight one is exact."))

# --------------------------------------------------------------- reproduction
F["reproduction"] = dict(
    E0_published_reproduced_with_the_defective_helper_verbatim=True,
    E0_max_abs_delta=s23["E0_reproduction_max_abs_delta"],
    E1_published_reproduced_with_its_own_helper_verbatim=True,
    E1_max_abs_delta=s23["E1_reproduction_max_abs_delta"],
    note=("Both maxima sit at ~4e-7, which is the rounding granularity of the 6-decimal figures "
          "printed in the frozen run logs. Reproduction is exact to the precision at which the "
          "numbers were published, so every later difference is attributable to the convention "
          "change and not to this harness."),
    headline_check=dict(quantity="E1 walk-forward mean dR2, M_B_plus_venue",
                        published=0.004003,
                        reproduced=s23["E1_oos_table"]["E1_oos_wf_mean_M_B_plus_venue"]["reproduced_published_convention"],
                        abs_delta=s23["E1_oos_table"]["E1_oos_wf_mean_M_B_plus_venue"]["abs_repro_delta"]))

# --------------------------------------------------------------- three-column table
F["three_column_comparison_table"] = dict(
    column_definitions=dict(
        as_published=("the number the frozen screen actually printed, together with which convention "
                      "produced it"),
        defective_weighted="1 - SSE_w / sum((sqrt(w)*y - mean(sqrt(w)*y))^2)  [E0's wls_r2]",
        standard_weighted="1 - sum(w*r^2) / sum(w*(y - mu_w)^2), mu_w = sum(w*y)/sum(w)",
        plain_unweighted_ols=("ADOPTED. Unweighted OLS fit; R2 = 1 - SSE/SST with SST about the "
                              "UNWEIGHTED mean. Out-of-sample: fit on train unweighted, SST about "
                              "the TRAIN unweighted mean.")),
    E0_screen_published_numbers_are_defective=s23["E0_table"],
    E1_screen_in_sample_published_numbers_are_standard_weighted=s23["E1_insample_table"],
    E1_screen_in_sample_M_A_per_season=s23["E1_insample_M_A_per_season"],
    E1_screen_out_of_sample_published_numbers_are_standard_weighted=s23["E1_oos_table"])

F["headline_three_ways"] = {
    "quantity": "I0009 walk-forward mean dR2 (train<=t, test t+1; 2021-2024)",
    "M_B_plus_venue (retrospective LOO baseline, AS PUBLISHED)": {
        "as_published_standard_weighted": 0.004003,
        "defective_weighted": s23["E1_oos_table"]["E1_oos_wf_mean_M_B_plus_venue"]["defective_weighted"],
        "plain_unweighted_ols_ADOPTED": s23["E1_oos_table"]["E1_oos_wf_mean_M_B_plus_venue"]["plain_unweighted_ols"],
        "change_pct_adopted_vs_published": s23["E1_oos_table"]["E1_oos_wf_mean_M_B_plus_venue"]["change_pct_plain_vs_standard"]},
    "M_F_pregame_full_control (prior-games-only baseline, the FORECASTING-HONEST one)": {
        "as_published_standard_weighted": 0.002795,
        "defective_weighted": s23["E1_oos_table"]["E1_oos_wf_mean_M_F_pregame_full_control"]["defective_weighted"],
        "plain_unweighted_ols_ADOPTED": s23["E1_oos_table"]["E1_oos_wf_mean_M_F_pregame_full_control"]["plain_unweighted_ols"],
        "change_pct_adopted_vs_published": s23["E1_oos_table"]["E1_oos_wf_mean_M_F_pregame_full_control"]["change_pct_plain_vs_standard"]}}

# --------------------------------------------------------------- baseline audit
F["retrospective_baseline_audit"] = s5["baseline_audit"]

# --------------------------------------------------------------- nulls
F["permutation_nulls"] = dict(
    grouping_level=s4["grouping_level_of_predictor"],
    plain_unweighted_ols=s4["permutation_nulls_plain_ols"],
    standard_weighted_walk_forward_for_contrast=s5["wf_null_standard_weighted_correct_level"],
    classical_t_statistics_plain_ols=s4["classical_t_statistics_plain_ols"],
    row_level_vs_correct_level=(
        "The correct-level (team-identity derangement within season) null is 2.5-3.2x WIDER than "
        "the row-level shuffle null on every statistic (e.g. wf_mean_M_F: sd 0.000712 vs 0.000207). "
        "Row-level shuffling is anti-conservative here, exactly as constraint 4 warns. The classical "
        "row-level t on the pressure coefficient is +8.2 to +9.0 and the opponent-team-game "
        "cluster-robust t is essentially identical (+8.3 to +9.0) -- the cluster correction does "
        "NOT reproduce the width the permutation null shows, confirming it is not a substitute."),
    noop_placebo_diagnostic=s4["noop_placebo_diagnostic"])

# --------------------------------------------------------------- verdict
F["verdict_impact"] = dict(
    frozen_E1_verdict="keep-as-lead",
    verdict_under_adopted_convention=s5["verdict_gate"]["verdict_under_adopted_convention"],
    gate_by_gate=s5["verdict_gate"],
    direction="WEAKENS on effect size; HOLDS on the pass/fail gate",
    detail=(
        "Every gate the frozen screen used still passes under plain OLS, so the formal verdict is "
        "unchanged at keep-as-lead. But the MAGNITUDE the lead is ranked on collapses out-of-sample. "
        "The in-sample and leave-one-season-out figures shrink only ~10%, because those folds are "
        "dominated by the same rows in train and test. The WALK-FORWARD figures -- the only genuinely "
        "prospective ones -- shrink ~79-85%: the headline 0.004003 becomes 0.000850, and the "
        "forecasting-honest M_F figure becomes 0.000413. Significance follows: under the published "
        "weighted convention the M_F walk-forward mean sat outside all 200 correct-level null draws "
        "(p<0.005); under plain OLS 7 of 200 draws equal or beat it (p=0.035). It survives, but "
        "marginally."),
    ranking_against_a_plain_ols_lead=(
        "Against three leads screened under plain OLS, I0009 must be entered at 0.000413 (fully "
        "pregame baseline, fully controlled, walk-forward) or at most 0.000850 (retrospective LOO "
        "baseline). NOT at 0.004003, and emphatically not at 0.004003 scaled UP for a supposed "
        "defective-SST understatement. The pre-existing ranking was invalid, but in the OPPOSITE "
        "direction to the one D069 anticipated: I0009 was flattered by possession weighting, not "
        "penalised by the SST bug."),
    caveats=(
        "Both the weighted and unweighted numbers are legitimate estimands -- weighting by "
        "possessions targets a possession-level effect, plain OLS a player-game-level one. The point "
        "is comparability: a like-for-like ranking against plain-OLS leads requires the plain-OLS "
        "number. The gap between them (0.004003 vs 0.000850) is itself informative: the effect is "
        "concentrated in high-possession player-games."))

F["non_claiming"] = ("E0/E1 output is NON-CLAIMING. No registry entry, no preregistration, no "
                     "leaderboard row, no promotion. This is a LEAD, never a RESULT. No file "
                     "outside experiments/exploration/E1_I0009_r2_rerun was created or modified.")

json.dump(F, open(f"{D}/FINDINGS.json", "w"), indent=2, default=float)
print("wrote FINDINGS.json")
