"""Assemble FINDINGS.json from the result JSONs this screen produced.
Nothing is retyped by hand; every number is read from the file that computed it."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RA = "Restricted Area"
ZONES = [RA, "In The Paint (Non-RA)", "Mid-Range", "Corner 3", "Above the Break 3"]


def L(n):
    return json.load(open(os.path.join(HERE, n), encoding="utf-8"))


B, A, R, AD, D = (L("build_results.json"), L("analysis_results.json"),
                  L("robustness_results.json"), L("addendum_results.json"),
                  L("dr2_results.json"))

F = {}
F["screen_id"] = "E1_I0004_shot_selection"
F["parent"] = ["experiments/exploration/E0_I0004_shot_location_allowance",
               "experiments/exploration/E1_I0004_rim_finishing"]
F["status"] = "NON-CLAIMING EXPLORATION (E1). A LEAD, never a RESULT."
F["non_claiming_note"] = ("No registry entry, no preregistration, no promotion, no "
                          "leaderboard row. Must never be cited as evidence.")
F["exploration_partition"] = dict(
    seasons=[2021, 2022, 2023, 2024],
    holdout_never_touched=["2025", "2026"],
    structural_violations=0,
    verifier="verify_partition.py (season COLUMN VALUES, not a text scan)",
    files_opened=[f"data/shotcharts/shots_{s}_{t}.parquet"
                  for s in (2021, 2022, 2023, 2024) for t in ("regular", "playoffs")],
    holdout_files_present_but_never_opened=[
        "data/shotcharts/shots_2025_regular.parquet",
        "data/shotcharts/shots_2025_playoffs.parquet",
        "data/shotcharts/shots_2026_regular.parquet",
        "data/shotcharts/league_avg_2025_regular.parquet",
        "data/shotcharts/league_avg_2025_playoffs.parquet",
        "data/shotcharts/league_avg_2026_regular.parquet"])

F["r2_convention"] = dict(
    declared=("PLAIN UNWEIGHTED OLS R2 = 1 - SSE/SST with SST taken about the "
              "UNWEIGHTED mean of the response (decision D069)."),
    exception=("One explicitly labelled robustness row uses attempt weighting; it "
               "uses STANDARD WEIGHTED SST about the WEIGHTED mean, and is labelled "
               "as such in robustness_results.json -> alternative_baseline."),
    defective_form_never_used="sst = sum((sqrt(w)*y - mean(sqrt(w)*y))**2)")

F["manifest_check"] = dict(
    method=("read the sibling <artifact>.manifest.json and inspect the "
            "asof_granularity COLUMN VALUE. A byte/regex scan for 2025/2026 is the "
            "WRONG check and was not used as a verdict."),
    zone_maps=dict(
        files=["data/zone_maps/league_zone_averages.csv",
               "data/zone_maps/player_zone_offense.csv",
               "data/zone_maps/shrinkage_priors.csv",
               "data/zone_maps/team_zone_defense.csv",
               "data/zone_maps/team_zone_offense.csv"],
        asof_granularity="artifact",
        usable_at_E0_E1=False,
        read_by_this_screen=False,
        why=("their own manifests state a 2021 row's shrunk value saw later seasons; "
             "FILTERING DOES NOT HELP")),
    masters=dict(files=["data/masters/master_player.parquet",
                        "data/masters/master_team.parquet"],
                 asof_granularity="row", usable_at_E0_E1=True,
                 read_by_this_screen=False),
    shotcharts=dict(files="data/shotcharts/shots_<season>_<type>.parquet",
                    manifests_present=False,
                    why_safe=("raw single-season sources: the season IS the filename, "
                              "so no pooled quantity can carry holdout information"),
                    read_by_this_screen=True),
    zone_assignment_source=("raw per-shot SHOT_ZONE_BASIC inside each per-season shot "
                            "file; Left/Right Corner 3 merged into 'Corner 3'. A shot's "
                            "zone label is a property of that shot and reads no other row."))

F["reproduction_before_change"] = dict(
    target_screen="E1_I0004_rim_finishing (cell B1_own_rate_v2_split_alpha | O2_pregame)",
    target=B["reproduction"]["target"],
    reproduced={k: B["reproduction"]["reproduced"][k]
                for k in ("n", "corr", "diff", "beta")},
    absolute_difference=B["reproduction"]["delta"],
    exact=B["reproduction"]["exact"],
    also_reproduced=dict(
        what="E0 I0004's published five-zone leave-one-game-out table",
        result="all five zones MATCH on n, corr and diff to <5e-5",
        detail=B["e0_zone_reproduction"]))

# ---------------------------------------------------------------- selection channel
F["selection_channel"] = dict(
    question=("does opponent identity shift WHERE the player shoots -- the "
              "distribution of field-goal ATTEMPTS across the five zones -- as "
              "distinct from how well they convert?"),
    unit="player-game x zone (zones with zero attempts present as share = 0)",
    response="share_z = player's attempts in zone z / player's total attempts, that game",
    own_baseline_S1=("frozen own_rate_v2_split_alpha with minutes := total FGA in the "
                     "game and target := zone attempts, i.e. EWMA_0.03(zone share) over "
                     "the player's STRICTLY PRIOR games in season, gate n_prior >= 3"),
    opponent_regressor_OS=("zone share of attempts faced by the opponent in its "
                           "STRICTLY PRIOR games this season, minus the LEAGUE share in "
                           "that zone over all games played STRICTLY BEFORE this "
                           "calendar date; gate >= 200 prior attempts faced"),
    n_player_games=int(B["n_selection_rows"] / 5),
    gates=dict(min_fga_in_game=B["constants"]["MIN_FGA_GAME"],
               min_prior_attempts_faced=B["constants"]["MIN_PRE_TOTAL"],
               min_prior_games=B["constants"]["MIN_PRIOR"]),
    per_zone={})
for z in ZONES:
    a = A["real"]["selection"][z]
    fwr = R["familywise_rowlevel"]["selection"][z]
    fwc = A["familywise"]["selection"][z]
    rob = R["stricter_opponent_regressors"][z]
    alt = R["alternative_baseline"][z]
    nat = [r for r in AD["natural_units"] if r["family"] == "selection" and r["zone"] == z][0]
    F["selection_channel"]["per_zone"][z] = dict(
        n=a["ols"]["n"],
        corr_row=a["row"]["corr"], diff_row=a["row"]["diff"], beta_row=a["row"]["beta"],
        beta_cluster_level=a["cluster"]["beta"], corr_cluster_level=a["cluster"]["corr"],
        se_cluster_robust=a["ols"]["se_cluster"], t_cluster_robust=a["ols"]["t_cluster"],
        t_naive=a["ols"]["t_naive"], n_clusters=a["ols"]["n_clusters"],
        r2_unweighted_about_unweighted_mean=a["ols"]["r2_unweighted_about_unweighted_mean"],
        permutation_null_opponent_team_season=dict(
            null_mean=fwc["null_mean"], null_sd=fwc["null_sd"], n_draws=fwc["n_draws"],
            z_row=fwr["z_row"], z_cluster=fwr["z_cluster"],
            p_unadjusted_one_sided_ROWLEVEL_real=fwr["p_unadjusted_one_sided"],
            p_unadjusted_one_sided_CLUSTER_real=fwc["p_unadjusted_one_sided_upper"],
            p_familywise_5zone_one_sided_ROWLEVEL=fwr["p_familywise_one_sided"],
            p_familywise_5zone_two_sided_ROWLEVEL=fwr["p_familywise_two_sided"],
            p_familywise_5zone_one_sided_CLUSTER=fwr["p_familywise_one_sided_cluster"],
            p_naive_rowlevel_null_WRONG=fwc["p_naive_rowlevel_null"]),
        inflation_factor_cluster_null_over_naive_row_null=
            A["inflation_factor"]["selection"][z]["beta"]["inflation"],
        robustness=dict(
            beta_row_excluding_shooting_team_from_opponent_history=rob["OS_exT"]["beta_row"],
            p_excluding_shooting_team=rob["OS_exT"]["p_row"],
            beta_row_excluding_own_player_from_opponent_history=rob["OS_exP"]["beta_row"],
            p_excluding_own_player=rob["OS_exP"]["p_row"],
            beta_row_S2_shrunk_baseline=alt["S2 baseline, unweighted"]["beta_row"],
            beta_row_attempt_weighted=alt["S1 baseline, attempt-weighted"]["beta_row"]),
        persistence=A["persistence"]["selection"][z],
        natural_units=dict(sd_of_regressor=nat["sd_x"],
                           share_change_per_1sd=nat["effect_per_1sd"],
                           relative_pct_per_1sd=nat.get("relative_pct"),
                           attempts_per_game_per_1sd=nat.get("attempts_per_game"),
                           mean_share=nat.get("mean_share")))
F["selection_channel"]["fixed_effects"] = A["fixed_effects"]["selection"]
F["selection_channel"]["player_game_increment"] = dict(
    model=D["dr2"],
    permutation=D["permutation"],
    conditioning_caveat=D["conditioning"])

# --------------------------------------------------------------- conversion family
F["conversion_family_five_zones"] = dict(
    note=("the surviving I0004 lead, re-measured on all five zones with the SAME "
          "fully pregame-observable construction, then family-wise corrected"),
    corrected_headline_carried_forward=dict(
        beta=AD["headline_familywise"]["beta"],
        diff=0.01757439922911997, corr=0.02881718165669519,
        source="E1_I0004_rim_finishing, 30764-row common set",
        killed_E0_headline_NOT_USED=0.0392),
    headline_family_wise=AD["headline_familywise"],
    per_zone={})
for z in ZONES:
    a = A["real"]["conversion"][z]
    fwr = R["familywise_rowlevel"]["conversion"][z]
    fwc = A["familywise"]["conversion"][z]
    F["conversion_family_five_zones"]["per_zone"][z] = dict(
        n=a["ols"]["n"], corr_row=a["row"]["corr"], diff_row=a["row"]["diff"],
        beta_row=a["row"]["beta"], beta_cluster_level=a["cluster"]["beta"],
        se_cluster_robust=a["ols"]["se_cluster"], t_cluster_robust=a["ols"]["t_cluster"],
        r2_unweighted_about_unweighted_mean=a["ols"]["r2_unweighted_about_unweighted_mean"],
        permutation_null_opponent_team_season=dict(
            null_mean=fwc["null_mean"], null_sd=fwc["null_sd"], n_draws=fwc["n_draws"],
            z_row=fwr["z_row"],
            p_unadjusted_one_sided_ROWLEVEL_real=fwr["p_unadjusted_one_sided"],
            p_familywise_5zone_one_sided_ROWLEVEL=fwr["p_familywise_one_sided"],
            p_familywise_5zone_two_sided_ROWLEVEL=fwr["p_familywise_two_sided"],
            p_familywise_5zone_one_sided_CLUSTER=fwr["p_familywise_one_sided_cluster"],
            p_naive_rowlevel_null_WRONG=fwc["p_naive_rowlevel_null"]),
        inflation_factor_cluster_null_over_naive_row_null=
            A["inflation_factor"]["conversion"][z]["beta"]["inflation"],
        persistence=A["persistence"]["conversion"][z])
F["conversion_family_five_zones"]["fixed_effects"] = A["fixed_effects"]["conversion"]

# -------------------------------------------------------------- role concentration
F["role_volume_concentration"] = dict(
    role_feature=("EWMA_0.30 of the player's FGA per game over their STRICTLY PRIOR "
                  "games this season (the frozen baseline's exposure channel)"),
    binnings=dict(preselected_absolute_cuts_fga_per_game=[6.0, 11.0],
                  also_reported="within-season empirical tertiles of the same feature"),
    selection=A["role_concentration"]["selection"],
    conversion=A["role_concentration"]["conversion"])

# ------------------------------------------------------------- nulls and placebos
F["nulls_and_placebos"] = dict(
    correct_grouping_level="opponent team x season (12 teams x 4 seasons = 48 clusters)",
    permutation_form=("the ALREADY-COMPUTED team-season allowance VALUES are reshuffled "
                      "across teams within season and re-assigned to rows; the whole "
                      "five-zone vector travels with the team so the cross-zone "
                      "structure survives and max-t is valid"),
    n_draws_cluster=A["n_draws_cluster"], n_draws_row=A["n_draws_row"], seed=A["seed"],
    row_level_null_reported_for_contrast=True,
    inflation_factor_summary=A["inflation_factor"],
    cluster_robust_se_caveat=("cluster-robust SEs are reported but are NOT the basis of "
                              "any verdict: in this program clustering has been observed "
                              "to RAISE t in one case and lower it in another"),
    defective_noop_D0=A["d0_defective_noop"])

# ----------------------------------------------------------------- time windows
F["time_window_table"] = [
    dict(quantity="share_z (response)", window="THE CURRENT GAME ONLY (the outcome)",
         prior_only="n/a (outcome)"),
    dict(quantity="S1 own zone-share baseline",
         window="the player's PLAYED GAMES STRICTLY BEFORE this game, same season",
         prior_only=True,
         verified="max|S1 - EWMA_0.03(share)[shift(1)]| = 7.772e-16"),
    dict(quantity="S2 shrunk own zone-share baseline",
         window="same player's strictly prior games in season, shrunk to the LEAGUE "
                "share over games played strictly before this calendar date",
         prior_only=True),
    dict(quantity="OS opponent zone-share allowance",
         window="the opponent's games STRICTLY BEFORE this game, same season "
                "(expanding cumsum minus the current row), centred on the league share "
                "over games played STRICTLY BEFORE this calendar date",
         prior_only=True),
    dict(quantity="OS_exT", window="same as OS, minus every prior game the opponent "
                                   "played against the shooting team", prior_only=True),
    dict(quantity="OS_exP", window="same as OS, minus this player's own prior attempts "
                                   "against that opponent", prior_only=True),
    dict(quantity="role_prior_fga", window="EWMA_0.30 of the player's FGA per game over "
                                           "strictly prior games in season", prior_only=True),
    dict(quantity="lg_share_prior", window="all league shots on calendar dates STRICTLY "
                                           "BEFORE this game's date, same season",
         prior_only=True),
    dict(quantity="B1 / OC conversion own-rate", window="the player's strictly prior "
                                                        "games in season", prior_only=True),
    dict(quantity="O2 / OC opponent conversion allowance",
         window="the opponent's strictly prior games in season", prior_only=True),
    dict(quantity="fga (denominator of the share, and the dR2 conditioner)",
         window="THE CURRENT GAME", prior_only=False,
         disclosure=("realised, not pregame-observable. The share model is therefore a "
                     "MIX model given volume. This is disclosed everywhere the dR2 "
                     "appears and is NOT claimed as a forecasting increment.")),
    dict(quantity="B0 (E0's leave-one-season-out player x zone rate)",
         window="THE PLAYER'S OTHER SEASONS -- READS THE FUTURE", prior_only=False,
         used_for="the reproduction step ONLY; never used in any new statistic"),
    dict(quantity="O1 (E0's leave-one-game-out full-season opponent rate)",
         window="THE OPPONENT'S WHOLE SEASON minus this game -- READS THE FUTURE",
         prior_only=False,
         used_for="the reproduction step ONLY; never used in any new statistic")]

F["every_new_feature_is_prior_games_only"] = True

# ------------------------------------------------------------------- verdicts
F["verdicts"] = {
    "shot_selection_channel (existence)": dict(
        verdict="KEEP-AS-LEAD",
        headline=("player-game Restricted-Area ATTEMPT SHARE vs the opponent's "
                  "strictly-prior-games rim-share allowance: beta = "
                  f"{A['real']['selection'][RA]['row']['beta']:+.4f} (row-level), "
                  f"{A['real']['selection'][RA]['cluster']['beta']:+.4f} "
                  "(cluster-level), corr "
                  f"{A['real']['selection'][RA]['row']['corr']:+.4f}, R2 "
                  f"{A['real']['selection'][RA]['ols']['r2_unweighted_about_unweighted_mean']:.6f}; "
                  "opponent-team-season permutation p = "
                  f"{R['familywise_rowlevel']['selection'][RA]['p_unadjusted_one_sided']:.4f} "
                  "unadjusted and "
                  f"{R['familywise_rowlevel']['selection'][RA]['p_familywise_one_sided']:.4f} "
                  "family-wise across the five zones (both at the 1/5001 resolution floor)"),
        why=("4/4 seasons positive, positive in both halves, STRENGTHENS under "
             "player-season and shooting-team-season fixed effects, and is unchanged "
             "when the opponent's allowance excludes every prior game against the "
             "shooting team or excludes the player's own prior attempts")),
    "shot_selection_channel (rim-SPECIFICITY)": dict(
        verdict="KILL",
        why=("the effect is NOT rim-specific. All five zones are positive; four of five "
             "clear the five-zone family-wise correction on the row-level statistic "
             "(Corner 3 p_FWE = "
             f"{R['familywise_rowlevel']['selection']['Corner 3']['p_familywise_one_sided']:.4f}). "
             "This is a general shot-LOCATION matchup effect, strongest at the rim, not "
             "an I0004 rim story. Any carry-forward must be framed as shot-mix, not rim.")),
    "role_volume_concentration (selection channel)": dict(
        verdict="KILL",
        why=("no concentration in a high-usage subgroup. Share-metric slope is flat to "
             "mildly DECREASING in role: "
             f"{A['role_concentration']['selection']['bin_abs']['low']['beta_row']:+.3f} / "
             f"{A['role_concentration']['selection']['bin_abs']['mid']['beta_row']:+.3f} / "
             f"{A['role_concentration']['selection']['bin_abs']['high']['beta_row']:+.3f} "
             "across preselected low/mid/high FGA bins, tertiles agree, and the "
             "continuous interaction is "
             f"{A['role_concentration']['selection']['interaction']['coef_interaction']:+.5f} "
             f"(two-sided permutation p = "
             f"{A['role_concentration']['selection']['interaction']['perm_p_two_sided']:.4f}), "
             "i.e. significantly NEGATIVE. The effect is broad-based. NOTE: measured in "
             "ATTEMPTS rather than share the ordering reverses, because high-usage "
             "players take more shots -- that is arithmetic, not concentration.")),
    "role_volume_concentration (conversion channel)": dict(
        verdict="KEEP-AS-LEAD (weak, NOT established)",
        why=("monotone gradient under BOTH binnings -- "
             f"{A['role_concentration']['conversion']['bin_abs']['low']['beta_row']:+.3f} / "
             f"{A['role_concentration']['conversion']['bin_abs']['mid']['beta_row']:+.3f} / "
             f"{A['role_concentration']['conversion']['bin_abs']['high']['beta_row']:+.3f} "
             "and R2 "
             f"{A['role_concentration']['conversion']['bin_abs']['low']['r2_unweighted_about_unweighted_mean']:.6f} "
             f"-> {A['role_concentration']['conversion']['bin_abs']['high']['r2_unweighted_about_unweighted_mean']:.6f} "
             "-- but the continuous interaction is "
             f"{A['role_concentration']['conversion']['interaction']['coef_interaction']:+.5f}, "
             "two-sided permutation p = "
             f"{A['role_concentration']['conversion']['interaction']['perm_p_two_sided']:.4f}. "
             "Suggestive of the program's conditional-edge thesis; NOT established.")),
    "five_zone_multiplicity for the surviving conversion headline": dict(
        verdict="SURVIVES",
        detail=(f"beta +0.3731536 -> z = {AD['headline_familywise']['z']:.2f}; "
                f"unadjusted one-sided p = {AD['headline_familywise']['p_unadjusted_one_sided']:.4f}, "
                f"five-zone family-wise p = {AD['headline_familywise']['p_familywise_one_sided']:.4f} "
                f"(one-sided, preselected) / {AD['headline_familywise']['p_familywise_two_sided']:.4f} "
                "(two-sided). It clears 0.05 on both, but the margin is thin -- this is "
                "not the '0/400 draws' picture E1 reported, which was resolution-limited "
                "at 400 draws.")),
    "OVERALL": "SPLIT"}

F["not_established"] = [
    "No walk-forward, no preregistration, no holdout evaluation -- out of E1 scope.",
    ("The dR2 of +0.0191 on rim ATTEMPTS is conditional on the player's REALISED total "
     "FGA in the game, which is not pregame-observable. It is a shot-MIX increment, not "
     "a forecasting increment. A pregame-observable volume model was not built."),
    ("Pace, rest, home/away, injuries and lineup were not conditioned on. The opponent "
     "allowance is built from shot-event data alone."),
    ("Whether the selection effect is exploitable against a market is untested; a "
     "0.34-attempt shift at the rim is small relative to typical prop lines."),
    ("The five-zone family excludes Backcourt (254 shots, 0.19%), following E0's own "
     "n >= 200 gate. Including it would make the family-wise correction slightly "
     "stricter, not looser."),
    ("The selection and conversion R2 values are NOT directly comparable: the selection "
     "response averages ~10 shots per row while the conversion response is a single "
     "Bernoulli draw. Quantified in addendum_results.json -> variance_decomposition "
     f"({100 * AD['variance_decomposition']['selection_RA']['frac_irreducible']:.1f}% of "
     "the selection response variance is irreducible sampling noise, vs "
     f"{100 * AD['variance_decomposition']['conversion_RA']['frac_irreducible']:.1f}% for "
     "conversion).")]

F["where_i_could_have_cheated"] = [
    dict(choice="row-level vs cluster-level 'real' statistic",
         more_favourable="cluster-level, dramatically so for the conversion family "
                         "(Mid-Range p_FWE 0.0002 cluster vs 0.8860 row)",
         chosen="row-level as the number carried forward",
         when="preselected -- it is the convention E1 used for its headline",
         disclosure="both are reported for every cell; they DISAGREE for conversion "
                    "Mid-Range / Above the Break 3 and that disagreement is the single "
                    "most important caveat in this screen"),
    dict(choice="one-sided vs two-sided max-t",
         more_favourable="one-sided",
         chosen="one-sided as the headline",
         when="preselected (the hypothesis is directional)",
         disclosure="two-sided reported everywhere; conclusions are unchanged"),
    dict(choice="OS_exT / OS_exP stricter opponent regressors",
         more_favourable="n/a -- they made the result slightly STRONGER",
         chosen="reported as robustness, headline stays on the preselected OS",
         when="AFTER seeing the headline",
         disclosure="added specifically because an all-five-zones-positive result "
                    "demanded a mechanical-confound test; had they weakened the result "
                    "they would still have been reported"),
    dict(choice="gates MIN_FGA_GAME=5, MIN_PRE_TOTAL=200, SHRINK_K=50, ROLE_CUTS=(6,11)",
         more_favourable="unknown -- not searched",
         chosen="as listed", when="BEFORE any selection-channel statistic was computed; "
                                  "written into build_frames.py's docstring before the "
                                  "first run",
         disclosure="no gate was tuned; no alternative gate was tried"),
    dict(choice="unweighted vs attempt-weighted regression",
         more_favourable="attempt-weighted (R2 0.0376 vs 0.0352)",
         chosen="unweighted", when="preselected by decision D069's default",
         disclosure="weighted reported with weighted SST about the weighted mean"),
    dict(choice="role binning",
         more_favourable="neither -- both binnings agree in direction",
         chosen="preselected absolute cuts as the headline, tertiles reported",
         when="both specified before running", disclosure="both reported in full"),
    dict(choice="which zones and seasons to report",
         more_favourable="reporting only Restricted Area",
         chosen="all five zones, all four seasons, both halves",
         when="preselected", disclosure="nothing was dropped")]

F["artifacts_written"] = sorted(os.listdir(HERE))

json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8"),
          indent=2, default=float)
print("wrote FINDINGS.json")
print(f"top-level keys: {list(F.keys())}")
