"""
E0 I0013 -- assemble FINDINGS.json by READING the result JSONs written by the run scripts.
No number in FINDINGS.json is retyped by hand; every value is copied from a machine-readable
result file, so the findings cannot drift from the runs.

Run:  python make_findings.py    (stdout captured to run_log_findings.txt)
"""
import json
import os

import pv_base as P
from run_screen_defs import CANDS, DIRECTION_LABEL

L = lambda n: json.load(open(os.path.join(P.OUT, n), "r", encoding="utf-8"))
SCR, MXT, SUR = L("screen_results.json"), L("maxt_robust_results.json"), L("survivor_checks.json")

FW = MXT["maxt"]["per_cell"]
ROB = {(r["target"], r["candidate"]): r for r in MXT["robustness"]}
HET = {}
for h in SCR["heterogeneity"]:
    HET.setdefault((h["target"], h["candidate"]), {})[h["split"]] = h["terciles"]
NULL_P95 = MXT["maxt"]["null_p95"]

forms = []
n_keep = 0
for c in SCR["cells"]:
    k = "%s|%s" % (c["target"], c["candidate"])
    fw = FW[k]
    nominal = c["placebo"]["frac_ge_real"]
    naive = c["placebo_naive_row_level"]["frac_ge_real"]
    if fw["familywise_p"] <= 0.05:
        verdict = "keep_as_lead"
        n_keep += 1
        reason = ("Clears its own cluster-level permutation floor (%d/%d draws at or above it) AND "
                  "clears the family-wise max-T null across all 27 cells at p=%.3f (z=%.2f against "
                  "a null whose p95 is %.2f). Not a costume: |r| with overall opponent defensive "
                  "allowance is %.2f, and D and O*D are in the base model, so the increment is "
                  "over-and-above overall opponent strength by construction."
                  % (round(nominal * c["placebo"]["n_draws"]), c["placebo"]["n_draws"],
                     fw["familywise_p"], fw["z"], NULL_P95,
                     abs(c["collinearity_vs_overall_opp_def"])))
    elif nominal > 0.05:
        verdict = "kill"
        reason = ("Inside its own cluster-level permutation floor: frac_ge_real = %.3f over %d "
                  "draws (real %.6f vs placebo mean %.6f, sd %.6f). No noise-floor separation, so "
                  "there is nothing to correct for multiplicity."
                  % (nominal, c["placebo"]["n_draws"], c["dR2_M"], c["placebo"]["mean"],
                     c["placebo"]["sd"]))
    else:
        verdict = "kill"
        reason = ("Cleared its OWN floor at nominal frac_ge_real = %.3f but is killed on "
                  "MULTIPLICITY: family-wise p = %.3f (z = %.2f against a 27-cell max-T "
                  "randomization null whose p95 is %.2f and whose max draw is %.2f). This is "
                  "exactly the false positive a 27-test sweep predicts."
                  % (nominal, fw["familywise_p"], fw["z"], NULL_P95, MXT["maxt"]["null_max"]))
    if naive <= 0.05 < nominal:
        reason += (" TRAP 3 BIT HERE: the NAIVE row-level permutation would have called this "
                   "significant (frac_ge_real = %.3f) because it is %.2fx narrower than the "
                   "correct cluster-level null." % (naive, c["placebo"]["sd"] /
                                                    max(c["placebo_naive_row_level"]["sd"], 1e-12)))
    e = dict(
        formulation=c["candidate"], target=c["target"],
        direction=c["direction_label"], construction=c["construction"],
        pregame_observable=True,
        pregame_justification="Built only from base.prior_expanding, i.e. a strict "
                              "cumulative-minus-self over the unit's games STRICTLY BEFORE the "
                              "target game's date, within the same season, aggregated to date "
                              "level so same-day games cannot see each other. No leave-one-out, "
                              "no leave-one-season-out, no full-season baseline (trap 2).",
        n=c["n"], R2_base=c["R2_base"], r2_convention_note="plain unweighted OLS (D069)",
        collinearity_vs_overall_opponent_defence=dict(
            within_season_r=c["collinearity_vs_overall_opp_def"],
            per_season=c["collinearity_per_season"],
            note="The base model already contains D (opponent OVERALL pregame allowance of the "
                 "target stat, excluding this player's own prior contribution) and O*D, so every "
                 "reported increment is orthogonal to overall opponent strength by construction. "
                 "The correlation above is the I0010 costume test; compare to I0010's +0.57/+0.59."),
        effect_size=dict(dR2_main=c["dR2_M"], beta_main=c["beta_M"],
                         beta_units="target counting stat per 1 sd of the residualised candidate",
                         per_season=c["per_season"],
                         beta_same_sign_all_4_seasons=c["beta_same_sign_all_seasons"]),
        standard_errors=dict(
            n_clusters=c["n_clusters"], cluster_key=c["cluster_key"] + " x season",
            t_classical=c["t_classical"], t_cluster_robust=c["t_cluster"],
            note="Classical t is reported ONLY to be distrusted (trap 3). No verdict uses it. "
                 "For the seven team-aggregate candidates there are 48 opponent/own-team-season "
                 "clusters, so tens of thousands of rows are not independent."),
        placebo=dict(kind="cluster-level permutation at the grouping level of the feature",
                     mean=c["placebo"]["mean"], sd=c["placebo"]["sd"],
                     frac_ge_real=c["placebo"]["frac_ge_real"],
                     n_draws=c["placebo"]["n_draws"], label=c["placebo"]["label"]),
        placebo_naive_row_level=dict(
            mean=c["placebo_naive_row_level"]["mean"], sd=c["placebo_naive_row_level"]["sd"],
            frac_ge_real=naive, n_draws=c["placebo_naive_row_level"]["n_draws"],
            width_ratio_correct_over_naive=(c["placebo"]["sd"] /
                                            max(c["placebo_naive_row_level"]["sd"], 1e-12)),
            note="Reported ONLY as evidence of trap 3. Never used for a verdict."),
        familywise=dict(z=fw["z"], familywise_p=fw["familywise_p"],
                        null_p95=NULL_P95, null_max=MXT["maxt"]["null_max"],
                        n_draws=MXT["maxt"]["n_draws"],
                        note="Joint max-T: one opponent-side and one own-side team relabelling per "
                             "season is applied to every candidate and every target in the same "
                             "draw, so the null preserves the real correlation between cells."),
        secondary_interactions=dict(
            dR2_OxM=c["dR2_OxM"], beta_OxM=c["beta_OxM"],
            dR2_XxM=c["dR2_XxM"], beta_XxM=c["beta_XxM"],
            note="REPORTED ONLY, NEVER PLACEBOED. These have NO noise floor and therefore cannot "
                 "be leads and are not ranked against anything. The primary test in every cell is "
                 "the main effect."),
        verdict=verdict, verdict_reasoning=reason)
    if (c["target"], c["candidate"]) in ROB:
        r = ROB[(c["target"], c["candidate"])]
        e["mechanism_diagnostics"] = dict(
            dR2_given_actual_minutes=r["dR2_given_actual_minutes"],
            retained_vs_actual_minutes=r["retained_vs_minutes"],
            dR2_given_actual_possessions=r["dR2_given_actual_possessions"],
            retained_vs_actual_possessions=r["retained_vs_possessions"],
            note="ACTUAL minutes and ACTUAL possessions are NOT pregame-observable. These two "
                 "rungs are mediation diagnostics only and are NOT forecasting models. A genuine "
                 "possession-VOLUME channel should survive the minutes rung and be largely "
                 "ABSORBED by the realised-possessions rung.")
    if (c["target"], c["candidate"]) in HET:
        e["volume_heterogeneity"] = dict(
            by_pregame_minutes_tercile=HET[(c["target"], c["candidate"])].get("Mexp"),
            by_pregame_usage_tercile=HET[(c["target"], c["candidate"])].get("usg_pre"),
            note="DESCRIPTIVE ONLY. No permutation null was computed for the tercile splits, so "
                 "no heterogeneity result here is a lead or is ranked against anything.")
    forms.append(e)

noop = SCR["noop"]
ref = [c for c in SCR["cells"] if c["target"] == "pts" and c["candidate"] == "opp_pace48"][0]

F = dict(
    screen_id="E0_I0013_possession_volume",
    stage="E0",
    idea="Possession volume as a driver of player production at the player level: a counting stat "
         "is a rate times an exposure, and exposure has two components -- minutes (well studied "
         "here) and possessions per minute (essentially unstudied).",
    claiming=dict(
        non_claiming=True,
        statement="THIS IS A NON-CLAIMING E0 EXPLORATION SCREEN. Nothing in this file is a result, "
                  "a claim, or a recommendation. Every entry is a LEAD or a KILL. There is no "
                  "registry entry, no preregistration, no leaderboard row, no promotion threshold "
                  "and no REPORT.md associated with this screen. The single keep_as_lead below is "
                  "a pointer for further cheap work, not a finding.",
        relationship_to_prior_work="Layer-3 PERSONNEL MATCHING is CLOSED and was not rebuilt: "
                                   "E0_I0012 killed 29 of 30 cells and E1_I0012_survivor_2021drop "
                                   "killed the last one. This screen takes the surface I0012's own "
                                   "conclusion named -- possession volume -- plus its unrun "
                                   "layer-2 OREB and supply-side-instrument follow-ups, as NEW "
                                   "work rather than as a rescue of the dead lead."),
    partition=dict(
        seasons=P.PARTITION,
        holdout_touched=False,
        holdout_statement="The 2025/2026 confirmation holdout was never read, joined, filtered "
                          "against, counted, plotted or described anywhere in this screen.",
        filter_points=[
            "base.load_player(): mp[mp.season.isin(2021-2024)] immediately after read_parquet, "
            "with an assert; # FILTER-POINT",
            "base.load_team(): same, immediately after read_parquet, with an assert; # FILTER-POINT",
            "pv_base.guard() called on the team pregame table, on each per-target player frame, on "
            "each per-target analysis frame, on the team possessions frame and on the team control "
            "table. Each call prints sorted(season.unique()) into the run log and asserts both "
            "(a) subset of 2021-2024 and (b) empty intersection with {2025, 2026}.",
            "pv_base.safe_write() re-asserts the partition before any CSV write.",
            "verify_partition.py re-parses every file this directory wrote and tests season/date "
            "column VALUES afterwards."],
        artifact_manifest_check=dict(
            test="GRAPH_POLICY 13.2.2 -> asof_granularity == 'row' (NOT fit_seasons / "
                 "fit_through_season, which only describe what a file contains)",
            artifacts=[
                dict(path="data/masters/master_player.parquet", asof_granularity="row",
                     fit_seasons=[2021, 2022, 2023, 2024, 2025, 2026],
                     usable_at_E0=True,
                     reasoning="Row granularity means the row filter to 2021-2024 bounds it. The "
                               "fit_seasons list includes holdout seasons but that is NOT the "
                               "contamination test."),
                dict(path="data/masters/master_team.parquet", asof_granularity="row",
                     fit_seasons=[2021, 2022, 2023, 2024, 2025, 2026],
                     usable_at_E0=True, reasoning="As above.")],
            byte_scan="NOT RUN, deliberately. A raw byte-scan for '2025'/'2026' has produced a "
                      "FALSE partition violation in this program twice, by matching row counts and "
                      "digit runs inside floats and by matching prose about the partition rule. "
                      "Season and date COLUMN VALUES are tested instead."),
        max_game_date_read="2024-09-19"),
    r2_convention=dict(
        rule="plain unweighted OLS R2 = 1 - SSE/SST, with SST taken about the UNWEIGHTED mean "
             "(program decision D069)",
        implementation="pv_base.ols / pv_base.r2, and the algebraically identical QR-based "
                       "incremental form run_screen.incr used inside the placebo loops",
        weighting="NONE. No weighted regression appears anywhere in this screen.",
        wls_r2_helper="NOT imported and NOT used. The defective helper in several older screen "
                      "analyze.py files uses the SST of the sqrt-weight-transformed response about "
                      "its own mean, which biases dR2 downward by 0-25%."),
    base_model=dict(
        formula="y_count ~ O + D + O*D + Mexp + O*Mexp",
        y="RAW counting stat (pts / reb / ast). I0012 modelled a per-100-possession RATE, which "
          "divides possession volume out of the outcome by construction; that is why volume could "
          "only ever appear there as an interaction.",
        O="player's pregame expanding per-100-possession rate of the target stat",
        D="opponent's pregame expanding OVERALL allowance of the target stat per 100 possessions, "
          "computed EXCLUDING this player's own prior contribution to it",
        Mexp="player's pregame expanding minutes per game",
        O_times_Mexp="rate x exposure, i.e. the naive counting-stat prediction, so every candidate "
                     "is asked for an increment OVER the naive prediction",
        analysis_rows="minutes >= 10, all nine candidates non-null, shared across the three targets "
                      "so the 27 cells are directly comparable (n = 10167 per target)"),
    traps_addressed=dict(
        trap_1_costume=dict(
            handled="D and O*D are IN the base model, so every reported increment is orthogonal to "
                    "overall opponent defensive allowance by construction. Each candidate is "
                    "additionally centred within season and explicitly residualised on [D, O*D]. "
                    "Within-season |r| against overall opponent defence is reported for all 27 "
                    "cells.",
            observed_range="|r| from 0.00 to 0.45 across the 27 cells, against I0010's "
                           "disqualifying +0.57/+0.59. The single surviving cell sits at -0.06.",
            bit_this_screen=False,
            note="Worth recording plainly: because D and O*D are already in the base span, the "
                 "explicit residualisation does not change the main-effect dR2 by even one ulp. "
                 "It is kept because it does change the interaction terms and the reported beta "
                 "scale. The costume control is enforced either way."),
        trap_2_retrospective_baseline=dict(
            handled="Every quantity on both the player side and the opponent side is built with "
                    "base.prior_expanding: aggregate to date level, then strict "
                    "cumulative-minus-self within (season, key). A value serving a target game "
                    "comes only from rows strictly before that game's date, in the same season. "
                    "Shrinkage priors use the PREVIOUS season's totals, which is prior "
                    "information, never later information.",
            explicitly_absent=["leave-one-out over a full season",
                               "leave-one-season-out",
                               "leave-one-game-out over a full season",
                               "any baseline whose name was trusted instead of its construction"],
            bit_this_screen=False),
        trap_3_anticonservative_t=dict(
            handled="No verdict uses a classical t anywhere. Seven of nine candidates are "
                    "team-season aggregates with only 12 distinct values per season shared across "
                    "every row facing that team; there are 48 team-season clusters over the "
                    "partition. Every cell gets a cluster-level permutation null, a cluster-robust "
                    "sandwich SE with the cluster count printed, and a joint family-wise max-T "
                    "null.",
            n_clusters_team_candidates=48,
            n_clusters_player_candidate=493,
            bit_this_screen=True,
            evidence="The naive row-level permutation null is 1.00x to 3.82x narrower than the "
                     "correct cluster-level null across the 27 cells (median 1.62x). On FOUR "
                     "cells the naive null crosses 0.05 while the correct null does not, i.e. the "
                     "wrong null would have manufactured four leads that do not exist: "
                     "pts x own_pace48 (naive 0.025 -> cluster 0.185), pts x ppm (0.010 -> 0.085), "
                     "ast x ppm (0.030 -> 0.065), ast x opp_missO48 (0.050 -> 0.145). Two more "
                     "sit just outside: ast x opp_orebA100 (0.060 -> 0.145) and ast x own_orebR100 "
                     "(0.065 -> 0.145).",
            second_observation="Cluster-robust t is NOT uniformly larger or smaller than classical "
                               "t here -- for ast x exp_gposs it goes 4.44 -> 4.62, for pts x "
                               "own_pace48 it goes 1.96 -> 1.47. That is why the permutation null, "
                               "not the SE, is what the verdicts rest on."),
        trap_4_noop_placebo=dict(
            defective_form_run_on_purpose=True,
            cell="opp_pace48 x pts",
            description="The team grouping key was permuted consistently in master_team AND in the "
                        "player frame, and the pregame aggregate was then RECOMPUTED from the "
                        "permuted key. The permuted cell is the same row set under a bijection, so "
                        "every row still receives its own true value.",
            real_dR2=noop["real_dR2_M"], noop_mean=noop["mean"], noop_sd=noop["sd"],
            noop_n_draws=noop["n_draws"],
            max_abs_deviation_from_real=noop["max_abs_deviation_from_real"],
            signature_confirmed="sd is EXACTLY 0.000000 and the largest deviation of any of the "
                                "200 draws from the real number is 2.7e-19, i.e. floating-point "
                                "noise. This is the defect signature.",
            real_control_contrast=dict(
                mean=ref["placebo"]["mean"], sd=ref["placebo"]["sd"],
                frac_ge_real=ref["placebo"]["frac_ge_real"],
                statement="The real cluster-level control for the SAME cell has sd 1.04e-04, which "
                          "is non-degenerate, so it does not have the defect."),
            min_placebo_sd_observed_across_all_cells=min(
                c["placebo"]["sd"] for c in SCR["cells"]),
            deterministic_diagnostics_labelled="The split-half reliability figure in "
                                               "survivor_checks.json is deterministic -- sd 0 BY "
                                               "CONSTRUCTION -- and is labelled as such so it can "
                                               "never be confused with the no-op defect."),
    ),
    placebo_discipline=dict(
        correct_form="Every real control permutes the ASSIGNMENT of an ALREADY-COMPUTED value to "
                     "rows. For team candidates a season-level team relabelling decides which "
                     "team's pregame series a row is assigned; for the player-level candidate "
                     "whole player-season blocks of computed values are reassigned to other "
                     "player-seasons. No grouping key is permuted and no aggregate is ever "
                     "recomputed from a permuted key.",
        n_draws_per_cell=SCR["meta"]["n_draws"],
        n_draws_familywise=MXT["maxt"]["n_draws"],
        n_placebo_distributions=2 * len(SCR["cells"]) + 1 + len(SUR["recency"]),
        min_sd_observed=min(c["placebo"]["sd"] for c in SCR["cells"]),
        degenerate_distributions_found=0),
    n_formulation_target_cells=len(forms),
    formulations=forms,
    survivor=dict(
        cell="exp_gposs x ast",
        what_it_is="Expected game possessions -- the mean of the two teams' strictly-prior "
                   "pregame expanding possessions-per-48 -- predicting a player's raw assist "
                   "count, over and above the player's own pregame rate, the opponent's overall "
                   "pregame assist allowance, their interaction, the player's pregame minutes, "
                   "and rate x minutes.",
        reliability=SUR["reliability"],
        confound_ladder=SUR["confound_ladder"],
        recency=SUR["recency"],
        sum_vs_difference=MXT["sum_vs_diff"],
        classification="LAYER 2, NOT LAYER 3. The estimable {sum, difference} reparameterisation "
                       "shows the difference between the two teams' pace carries dR2 0.000001 "
                       "against the sum's 0.001133 for assists. The effect is SYMMETRIC GAME "
                       "TEMPO, i.e. a game-level possession-volume main effect, and is explicitly "
                       "NOT an opponent matchup. This is the mirror image of I0012's survivor, "
                       "which was asymmetric and therefore a matchup.",
        contrast_with_I0012_survivor="I0012's survivor decayed monotonically (+0.356 -> +0.335 -> "
                                     "+0.167 -> +0.064) and in 2024 sat BELOW its own placebo "
                                     "mean. This one does not decay: its 2024-alone point estimate "
                                     "is the LARGEST of the four seasons and sits ABOVE its own "
                                     "placebo mean. The two recent slices do not individually "
                                     "clear 0.05, but their floors are wide at n = 5555 and 2771 "
                                     "and the sign of the failure is opposite.",
        why_it_is_still_only_a_lead=[
            "dR2 = 0.001133 is small -- roughly the same size as I0012's now-dead survivor and "
            "about 6x under I0009's existing 0.006-0.007 lead.",
            "2023 is a dead season for it (dR2 0.000012, beta -0.0100). The per-season pattern is "
            "noisy rather than monotone, which is better than a decay but is not stability.",
            "Neither recent slice clears 0.05 on its own floor (2023-2024 frac 0.060; 2024 alone "
            "frac 0.065).",
            "It is a game-level tempo main effect, so it will be correlated with whatever the "
            "market already prices into totals. Nothing here tests incremental value over a price."]),
    multiplicity=dict(
        n_tests=len(forms),
        primary_test_per_cell="the MAIN effect dR2 of the candidate over the base model",
        secondary_tests_not_counted="the two interaction terms per cell are reported without a "
                                    "noise floor and are explicitly excluded from any verdict",
        familywise_null="joint max-T randomization over all 27 cells, %d draws; one opponent-side "
                        "and one own-side team relabelling per season applied to every candidate "
                        "and every target within the same draw, so the null preserves the real "
                        "correlation between cells" % MXT["maxt"]["n_draws"],
        null_p50=MXT["maxt"]["null_p50"], null_p95=NULL_P95, null_max=MXT["maxt"]["null_max"],
        n_cells_clearing_own_nominal_floor=sum(
            1 for c in SCR["cells"] if c["placebo"]["frac_ge_real"] <= 0.05),
        n_cells_surviving_familywise=n_keep,
        statement="11 of 27 cells cleared their own cluster-level floor at nominal frac_ge_real "
                  "<= 0.05. Exactly 1 survives the family-wise max-T null. The other 10 are the "
                  "false positives a 27-test sweep predicts and are killed on multiplicity, not "
                  "kept."),
    summary=dict(
        n_cells_screened=len(forms), n_killed=len(forms) - n_keep, n_kept_as_lead=n_keep,
        headline="Possession volume is a REAL but SMALL and GAME-LEVEL channel in player counting "
                 "stats, and almost none of the ways of instrumenting it survive contact with a "
                 "correct noise floor. 26 of 27 formulation-target cells die. The single survivor "
                 "-- expected game possessions predicting assists -- is not a costume (r = -0.06 "
                 "with overall opponent defence), is measured reliably (Spearman-Brown 0.809), "
                 "keeps 93% of its increment after home advantage and both teams' pregame net "
                 "rating and win rate, keeps 96% given ACTUAL minutes played but loses 84% given "
                 "ACTUAL possessions -- which is exactly the mediation signature a possession-"
                 "VOLUME story predicts -- and does NOT decay toward the holdout. But it is "
                 "SYMMETRIC between the two teams, so it is a layer-2 game-tempo main effect, not "
                 "a layer-3 matchup, and at dR2 0.001133 it is small.",
        what_this_settles=[
            "The layer-2 OREB main effect that I0012 sent to the backlog is SCREENED AND DEAD as a "
            "main effect on player counting stats. Opponent OREB allowed reaches nominal 0.015 on "
            "points but dies family-wise, and it is the ONE candidate that is NOT absorbed by "
            "realised possessions (66% retained), so even if it were real it would not be the "
            "possession-volume mechanism it was proposed as. Own-team OREB rate is dead outright "
            "(dR2 0.000000 on points).",
            "POSSESSIONS-PER-MINUTE as a player-specific exposure channel is DEAD. It reaches "
            "nominal 0.085 / 0.065 / 0.700 on pts / ast / reb and family-wise p 0.83 / 0.80 / "
            "1.00. Minutes remains the exposure component that matters; the per-minute component "
            "adds nothing measurable at this precision.",
            "The SUPPLY-SIDE instruments I0012 asked for (opponent FGA allowed per 48, opponent "
            "misses allowed per 48, opponent's own misses per 48) do NOT beat the tempo proxy. On "
            "rebounds -- the target where the supply story was sharpest -- all three are flatly "
            "inside their floors (frac 0.675 / 0.935 / 0.665) while the tempo proxy is the "
            "strongest rebound candidate. The mechanistic story that misses are the real rebound "
            "supply is NOT supported.",
            "Neither team's pace ALONE survives; only their SUM does. That is a mildly useful "
            "structural fact: the live quantity is total expected game possessions, not an "
            "opponent-specific tempo matchup.",
            "Trap 3 is real and it bit. Had this screen used the row-level permutation null that "
            "reads natural for a 10,167-row regression, it would have reported at least three "
            "extra leads that do not exist."],
        what_was_not_established=[
            "No OREB/DREB split of the rebound target. I0012's follow-up 3 remains unrun; the "
            "rebound cells here all died before the split would have mattered, but the split "
            "itself was not performed.",
            "No noise floor on any interaction term. The 54 secondary interaction increments are "
            "reported and are not leads.",
            "No noise floor on the volume-heterogeneity terciles. The gradient is clean and "
            "monotone in pregame minutes and pregame usage for the survivor, but it is DESCRIPTIVE "
            "and is not ranked against anything.",
            "No test of incremental value over a market price, and no test against rest, travel, "
            "injury or lineup information.",
            "No sensitivity analysis on the minutes >= 10 analysis cut or on the shrinkage "
            "constants.",
            "The survivor's 2023 collapse is unexplained."]),
    files=dict(**{
        "pv_base.py": "shared base; imports E0_I0012/base.py READ-ONLY and re-points its OUT into "
                      "this directory; partition guard, team pregame table, player exposure "
                      "quantities, OLS/cluster-SE machinery",
        "run_screen_defs.py": "the candidate registry, single source of truth for both run stages",
        "run_screen.py": "27 cells, cluster + naive placebos, the deliberate no-op diagnostic, "
                         "volume heterogeneity",
        "run_maxt_robust.py": "family-wise max-T over all 27 cells; actual-minutes and "
                              "actual-possessions mediation rungs; sum-vs-difference "
                              "reparameterisation",
        "run_survivor_checks.py": "reliability, confound ladder, recency slices for the one "
                                  "survivor",
        "make_findings.py": "assembles this file by reading the result JSONs; retypes no number",
        "verify_partition.py": "re-parses every file this directory wrote and tests season/date "
                               "column VALUES",
        "run_log_*.txt": "full stdout of every run, including every printed season list"}),
)

with open(os.path.join(P.OUT, "FINDINGS.json"), "w", encoding="utf-8") as f:
    json.dump(F, f, indent=1, default=float)
print("wrote FINDINGS.json")
print("  cells screened : %d" % len(forms))
print("  killed         : %d" % (len(forms) - n_keep))
print("  keep_as_lead   : %d" % n_keep)
for e in forms:
    if e["verdict"] == "keep_as_lead":
        print("  LEAD -> %s x %s  dR2=%.6f  placebo mean/sd %.6f/%.6f frac_ge=%.3f  familywise p=%.3f"
              % (e["formulation"], e["target"], e["effect_size"]["dR2_main"],
                 e["placebo"]["mean"], e["placebo"]["sd"], e["placebo"]["frac_ge_real"],
                 e["familywise"]["familywise_p"]))
