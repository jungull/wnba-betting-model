"""E1_I0027 s06 -- FINDINGS.json and NOTES.md.  Reads only this screen's own artefacts."""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import refladder as RL          # noqa: E402

OUT = HERE
L = lambda p: pd.read_csv(os.path.join(OUT, p))                                    # noqa: E731
pre = json.load(open(os.path.join(OUT, "_prereg.json"), encoding="utf-8"))
s05 = json.load(open(os.path.join(OUT, "_s05.json"), encoding="utf-8"))
lt, lp = L("ladder_table.csv"), L("ladder_pairwise.csv")
rs, rq = L("reference_spread.csv"), L("rung_quality_by_rowset.csv")
rt, rk = L("reprice_table.csv"), L("ranking_change.csv")
rbr, d92, cyc = L("reprice_by_rung.csv"), L("d092_reprice_by_rung.csv"), L("cyclic_null.csv")
D = s05["diag"]


def g(lead, resp, rung, col="dr2_common_sst"):
    m = (rbr.lead == lead) & (rbr.response == resp) & (rbr.base_rung == rung)
    return float(rbr.loc[m, col].iloc[0])


F = {}
F["screen"] = "E1_I0027_reference_ladder"
F["question"] = ("Build one canonical, strictly-prior-games-only reference ladder; re-price the "
                 "ledger's live and recently-killed leads against the SAME rung; and answer whether "
                 "the ranking of those leads changes when they are measured consistently.")

F["HEADLINE"] = {
    "does_the_ranking_change":
        "NO AMONG THE LEADS THAT CAN BE RANKED AT ALL -- AND ONLY TWO OF THE FIVE CAN BE. On the "
        "identical %d-row set with one denominator, D099's opponent-defence effect outranks D089's "
        "teammate-volume channel both before (+0.003335 vs +0.002349) and after (+0.004550 vs "
        "+0.003572) re-pricing. Zero rank swaps. SO THE REFERENCE PROBLEM IS A REPORTING PROBLEM "
        "FOR THE ORDERING, NOT A DECISION PROBLEM." % D["common_row_set"]["n"],
    "BUT_THE_EVIDENTIAL_STANDING_DOES_CHANGE_AND_THAT_IS_A_DECISION_PROBLEM":
        "D089 -- filed by its own decision entry as 'the programme's best usable lead' -- clears a "
        "correct-level null against its OWN reference (cluster p 0.0377 on these rows) and DOES NOT "
        "clear one against the canonical rung: cluster sign-flip p %.4f, within-player cyclic p "
        "%.4f. D099 clears against every rung (p %.4f and %.4f). The magnitudes keep their order; "
        "the confidence does not."
        % (g("D089_teammate_volume", "points", RL.CANONICAL_RUNG, "p_cluster"),
           float(cyc.loc[cyc.feature == "P01_c04_prevgame", "p"].iloc[0]),
           g("D099_opponent_defence", "points", RL.CANONICAL_RUNG, "p_cluster"),
           float(cyc.loc[cyc.feature == "A10_opp_defrtg", "p"].iloc[0])),
    "THREE_OF_FIVE_LEADS_ARE_NOT_RANKABLE_AGAINST_EACH_OTHER_AT_ALL":
        "D074/D079 (zone attempt counts), D072 (turnovers per 100 possessions) and D092 (an MAE "
        "skill ratio, not a dR2) fail the same-response or same-metric test. No denominator repairs "
        "that. The programme has been ordering them anyway. THAT is the larger defect this screen "
        "found: the ranking was not merely measured against inconsistent references, it was "
        "assembled from quantities that are not commensurable in the first place.",
    "the_reference_moves_numbers_in_BOTH_directions":
        "Once the row-set change is held separate from the reference change, D089's increment GROWS "
        "1.52x on a stronger reference while D099's points increment SHRINKS to 0.85x. A programme "
        "that assumed 'a better reference always shrinks a lead' would have been wrong half the "
        "time here.",
}

F["step1_the_ladder"] = {
    "definition": "REFERENCE_LADDER.md; implementation refladder.py; spec sha256 %s, frozen by "
                  "s03_prereg.py BEFORE any re-priced figure" % pre["sha256"],
    "rungs": RL.RUNGS, "canonical_rung": RL.CANONICAL_RUNG, "targets": RL.TARGETS,
    "canon_per_target": pre["canon"],
    "reused_from_D094_not_re_derived": [
        "EWMA beats SMA beats expanding on all four measured targets",
        "half-lives: minutes 2, attempts 5, points 8, points-per-minute 40 (a ~20x spread)",
        "shrinkage is weak and never toward the league; always toward the player's own prior season",
        "a realised-minutes floor on the history hurts monotonically, so the floor is 0 everywhere",
    ],
    "measured_here_because_D094_never_measured_them": {
        "rebound_half_life": pre["half_life_selection"]["reb"]["chosen_half_life"],
        "assist_half_life": pre["half_life_selection"]["ast"]["chosen_half_life"],
        "selection_set": pre["train_seasons_for_selection"],
        "note": "selected on train seasons only, frozen and hashed before any re-priced figure; "
                "NOT used in any re-priced figure (all re-prices are points or points-per-minute)"},
    "ladder_table": json.loads(lt.to_json(orient="records")),
    "adjacent_rung_tests": json.loads(lp.to_json(orient="records")),
    "reference_spread": json.loads(rs.to_json(orient="records")),
    "IS_THE_LADDER_ORDERED":
        "By R2 on a common denominator, yes, on all six targets: R0 < R1 < {R2, R3} < R4. Every "
        "adjacent step from R0 to R2 clears the clustered paired sign-flip at the 4,000-draw floor. "
        "BY MAE THE ORDER IS NOT IDENTICAL -- R3 edges R4 on points and assists, and R2 edges R4 on "
        "minutes. Reported rather than smoothed: MAE and R2 do not have to agree, and a ladder that "
        "claimed they did would be the same class of error this screen exists to fix.",
    "THE_LADDERS_ORDER_IS_NOT_STRATUM_INVARIANT":
        "On the DECISION stratum R4 is still best by R2 (points +0.3221 against R2_EWMA's +0.3176), "
        "but on the cold-start-heavy tier frame R4 is the WORST of R2/R3/R4 by MAE (4.2398 against "
        "4.0165). A rung is not 'strong' in the abstract; it is strong on a row set. Any future "
        "screen quoting a rung must quote the row set with it.",
    "grand_fallback_rows": 78,
    "r3_degenerate_for": "minutes (rate x minutes is minutes/minutes x minutes); returned as NaN "
                         "rather than silently duplicating R2",
}

F["step2_reprice_table"] = json.loads(rt.to_json(orient="records"))
F["step2_by_rung"] = json.loads(rbr.to_json(orient="records"))
F["step2_D092_by_rung"] = json.loads(d92.to_json(orient="records"))
F["step2_anchors_separate_the_rowset_effect_from_the_reference_effect"] = {
    "why": "The canonical rung R4 is undefined in a frame's FIRST season (its blend has no earlier "
           "season to fit on), and that cascades into the walk-forward regression, so the common "
           "scored set is 2023-2024 (n=%d) rather than the leads' published 2022-2024 sets "
           "(n=4517 / n=4514). Comparing a published figure straight to a re-priced one would "
           "therefore confound the row set with the reference. Each lead's OWN construction was "
           "re-run on the common rows first." % D["common_row_set"]["n"],
    "D089_points": {"published": 0.0023492235735382717,
                    "own_construction_on_common_rows": D["D089_anchor"]["dr2_common_sst"],
                    "row_set_effect": D["D089_anchor"]["dr2_common_sst"] / 0.0023492235735382717,
                    "repriced_on_canonical_rung": g("D089_teammate_volume", "points",
                                                    RL.CANONICAL_RUNG),
                    "REFERENCE_EFFECT": g("D089_teammate_volume", "points", RL.CANONICAL_RUNG)
                    / D["D089_anchor"]["dr2_common_sst"]},
    "D099_points": {"published": 0.0033354248642841694,
                    "own_construction_on_common_rows":
                        D["D099_anchor_points"]["dr2_common_sst"],
                    "row_set_effect": D["D099_anchor_points"]["dr2_common_sst"]
                    / 0.0033354248642841694,
                    "repriced_on_canonical_rung": g("D099_opponent_defence", "points",
                                                    RL.CANONICAL_RUNG),
                    "REFERENCE_EFFECT": g("D099_opponent_defence", "points", RL.CANONICAL_RUNG)
                    / D["D099_anchor_points"]["dr2_common_sst"]},
    "D099_ppm": {"published": 0.005028055896625616,
                 "own_construction_on_common_rows": D["D099_anchor_ppm"]["dr2_common_sst"],
                 "row_set_effect": D["D099_anchor_ppm"]["dr2_common_sst"] / 0.005028055896625616,
                 "repriced_on_canonical_rung": g("D099_opponent_defence", "ppm",
                                                 RL.CANONICAL_RUNG),
                 "REFERENCE_EFFECT": g("D099_opponent_defence", "ppm", RL.CANONICAL_RUNG)
                 / D["D099_anchor_ppm"]["dr2_common_sst"]},
}
F["step2_skipped_not_approximated"] = [
    r for r in json.loads(rt.to_json(orient="records")) if str(r["status"]).startswith("SKIPPED")]
F["step2_D092_is_the_largest_single_finding_in_the_table"] = (
    "D092's quoted +3.51%% pooled points skill is a statement about D076's expanding running mean, "
    "which D092's own screen showed is the LEAGUE MEAN WEARING A PLAYER'S NAME for 404 of 475 "
    "player-seasons. On the SAME 13,879 rows the identical operating rule scores %+.5f against "
    "R4_RICH_LOOKUP, %+.5f against R2_EWMA_TUNED and %+.5f against R3_RATE_X_MINUTES. THE SIGN OF "
    "THE HEADLINE DEPENDS ON THE RUNG. Against a tuned EWMA of the player's own prior games the "
    "cold-start rule is worth about two-tenths of one percent; against the rate x minutes composite "
    "it is NEGATIVE. Nothing about the rule changed."
    % (float(d92.loc[d92.rung == "R4_RICH_LOOKUP", "skill_vs_rung"].iloc[0]),
       float(d92.loc[d92.rung == "R2_EWMA_TUNED", "skill_vs_rung"].iloc[0]),
       float(d92.loc[d92.rung == "R3_RATE_X_MINUTES", "skill_vs_rung"].iloc[0])))

F["step3_ranking"] = {
    "table": json.loads(rk.to_json(orient="records")),
    "n_rank_swaps": D["ranking"]["n_swaps"],
    "order_by_quoted": D["ranking"]["order_quoted"],
    "order_by_repriced": D["ranking"]["order_repriced"],
    "n_rankable": D["ranking"]["n_rankable"], "n_not_rankable": D["ranking"]["n_not_rankable"],
    "VERDICT": "STABLE IN ORDER, UNSTABLE IN STANDING. State it as: the reference problem did not "
               "reorder the two leads that are commensurable, so past prioritisation between THOSE "
               "TWO was not an artefact. But it did move one of them from clearing a correct-level "
               "null to not clearing one, and three of the five leads were never commensurable at "
               "all. 'The ranking is stable' would be a true sentence and a misleading summary.",
}

F["step4_denominator_rule"] = {
    "rule": pre["plan"]["denominator_rule"],
    "operational_form": "dR2_A is comparable to dR2_B iff they share (D1) the response variable and "
                        "its units, (D2) the scored row set, (D3) an SST taken on that full scored "
                        "row set about its own unweighted mean, (D4) the weighting in fit / SSE / "
                        "SST, and (D5) the base model. Failing D2 alone is repairable by "
                        "re-expressing both as SSE_reduction / SST_common. Failing D1 is not "
                        "repairable at all.",
    "how_this_screen_enforces_it": "refladder.paired_dr2 and every dR2 in s05 take the denominator "
                                   "as an explicit argument. There is no code path that can compute "
                                   "a subset's own SST by accident. D099's defect is made "
                                   "structurally impossible rather than merely discouraged.",
    "FLAGGED_QUOTED_FIGURES_ON_NON_COMPARABLE_DENOMINATORS": [
        {"figure": "D098 +0.023863 (opponent defence, top volume tercile)",
         "defect": "D3 -- subset SST. Computed on 1,687 rows whose SST is 36% of the stratum's.",
         "status": "ALREADY SUPERSEDED by D099 ruling 2; recorded here only because the ledger "
                   "still contains the number and D099 had to say 'is not comparable to anything "
                   "else in this ledger'."},
        {"figure": "D098's '6.2x the largest ceiling this programme has measured'",
         "defect": "D3 -- the ceiling was computed on the same inflated denominator.",
         "status": "WITHDRAWN by D099; no successor may cite it."},
        {"figure": "D089's ceiling comparisons: 'the prior-only ceiling is ~1.8x D079's mix ceiling "
                   "and ~16x D084's conversion ceiling'",
         "defect": "D1 -- D089's ceiling is on POINTS and D079's is on ZONE ATTEMPT COUNTS. These "
                   "are ratios of variance shares of different response variables. The comparison "
                   "reads as a size ordering and is not one.",
         "status": "NOT PREVIOUSLY FLAGGED. Raised here."},
        {"figure": "D072's pair 0.002795 (standard-weighted) and 0.000413 (plain OLS)",
         "defect": "D4 -- weighting. D072 itself ruled that both must be reported together and that "
                   "the ranking entry is the plain one.",
         "status": "ALREADY HANDLED by D072 rulings 2-3; the risk is a successor quoting one of "
                   "them alone."},
        {"figure": "D092's +3.51% pooled points skill",
         "defect": "D5 (a reference the same screen showed to be degenerate) and a METRIC mismatch "
                   "-- it is an MAE skill ratio, not a dR2, and cannot enter a dR2 ranking.",
         "status": "RE-PRICED HERE. Its sign depends on the rung."},
        {"figure": "D074's +0.019139 conditional-on-realised-FGA mix increment",
         "defect": "D2/D5 -- conditioned on a realised quantity, so it is not on the same footing "
                   "as D079's +0.016853 forecast increment.",
         "status": "ALREADY HANDLED by D079, which measured the forecast version. The pair must "
                   "never be quoted as one number."},
        {"figure": "D090's +46.4% and +7.1% for one availability forecast; D094's +3.71% and "
                   "-4.41% for one minutes forecast",
         "defect": "D5 -- different references, same forecast. These are the instances that "
                   "motivated this screen.",
         "status": "Both already corrected in their own entries; listed so the pattern is legible "
                   "as one pattern rather than four incidents."},
    ],
}

F["controls"] = {
    "negative_control_G01_noise_over_each_rung":
        json.loads(rbr.loc[rbr.lead == "NEGATIVE_CONTROL_noise"].to_json(orient="records")),
    "negative_control_verdict": "dead at every rung (|dR2| <= 3.0e-4, cluster p 0.57-0.98, cyclic "
                                "p 0.609) -- so the re-price machinery is not manufacturing "
                                "increments out of the rung's residual structure.",
    "cyclic_within_player_null": json.loads(cyc.to_json(orient="records")),
    "why_cyclic": "D093 measured that a plain within-player SHUFFLE is anticonservative for an "
                  "autocorrelated prior-history regressor (p 0.0015 where the honest null gave "
                  "0.39); the kit refuses it (K6). P01 and the defence column are exactly that "
                  "shape, so SCHEME_WITHIN_CYCLIC is the null used.",
    "row_level_p_reported_for_contrast_only": True,
    "reproductions": {
        "D092_pooled_MAE_of_the_operating_rule": {
            "recomputed": D["D092_reproduction"]["mae_rule"],
            "published": D["D092_reproduction"]["published_mae_rule"],
            "abs_delta": abs(D["D092_reproduction"]["mae_rule"]
                             - D["D092_reproduction"]["published_mae_rule"])},
        "D092_pooled_skill_vs_D076_reference": {
            "recomputed": D["D092_reproduction"]["skill_vs_refD076"],
            "published": D["D092_reproduction"]["published_skill"],
            "abs_delta": abs(D["D092_reproduction"]["skill_vs_refD076"]
                             - D["D092_reproduction"]["published_skill"])},
        "D089_own_construction_on_its_own_number":
            "The published 0.0023492 is on 4,517 rows spanning 2022-2024 and could not be "
            "reproduced on that row set here, because R4's first-season gap forces the common set "
            "to 2023-2024. Re-running D089's OWN construction on the common rows gives %.9f, i.e. "
            "the row-set change is worth 1.003x -- so the reproduction is close enough to anchor "
            "the reference comparison, and is reported as an anchor rather than claimed as an exact "
            "reproduction." % D["D089_anchor"]["dr2_common_sst"],
    },
    "champion_never_fitted": "Only stored forecast columns (pts__pred_point, pts__is_fallback) were "
                             "read. No retraining, refitting or modification of any kind.",
}

F["partition"] = {
    "seasons_touched": [2021, 2022, 2023, 2024],
    "assertion": "refladder.assert_partition runs inside every ladder() call and tests VALUES, "
                 "never file text. It checks the observation-season column and every datetime "
                 "column, and deliberately does NOT fire on year-valued player attributes such as "
                 "draft_year -- that is D092's K4 defect, whose obvious workaround (season_cols="
                 "['season']) hides real leaks.",
    "2025_2026": "never read, joined, plotted or described.",
    "season_disjointness": "asserted before any previous-season aggregate is used; without it a "
                           "prior-season value would not be strictly prior.",
}
F["time_window_table"] = RL.TIME_WINDOW_TABLE

F["WHERE_I_COULD_HAVE_CHEATED"] = [
    {"item": "R3 was implemented incorrectly on the first execution of s04 and was corrected.",
     "detail": "The first run gave points-per-minute R3 an MAE of 8.238 and an R2 of -1190, because "
               "the rate x minutes form was applied to a quantity that is already a rate. The fix "
               "defines R3 for a rate target as the ratio of prior component sums, and pins the "
               "minutes arm of the composite at half-life 2 for level targets -- which is what "
               "REFERENCE_LADDER.md already said. The first run's log is kept verbatim as "
               "run_log_s04_FIRSTRUN_r3_defect.txt.",
     "why_it_is_not_a_cheat": "No re-priced figure existed at that point; s05 had not been written. "
                              "But it is a rung changed after seeing a number, and the brief asks "
                              "for exactly this to be declared."},
    {"item": "THE CANONICAL RUNG FLATTERS D092 AND I SAY SO.",
     "detail": "R4_RICH_LOOKUP was fixed as canonical in the preregistration, before any re-price. "
               "On the DECISION stratum that choice is defensible on its merits (R4 has the best R2 "
               "there). On D092's cold-start-heavy tier frame it is NOT the strongest rung: by MAE "
               "R4 is 4.2398 against R3's 4.0165. D092's re-priced gain is therefore +4.83% against "
               "R4 and -0.46% against R3. HAD I CHOSEN R3 AS CANONICAL, D092 WOULD HAVE RE-PRICED "
               "NEGATIVE. Every rung is in d092_reprice_by_rung.csv and the R2/R3 figures are in "
               "the reprice table's note column, so the reader does not have to take the R4 "
               "headline."},
    {"item": "The re-price row set is smaller than the leads' published row sets.",
     "detail": "3,165 rows (2023-2024) against 4,517/4,514 (2022-2024), because R4 is undefined in "
               "a frame's first season and that cascades into the walk-forward fit. This is "
               "handled by re-running each lead's OWN construction on the common rows, so the "
               "reported reference effect is not contaminated by the row-set change -- but the "
               "re-priced figures are on 30% fewer rows than the quoted ones and no amount of "
               "arithmetic changes that."},
    {"item": "Rebound and assist half-lives were selected inside this screen.",
     "detail": "On seasons 2021-2022 only, from D094's unchanged grid, frozen and hashed before any "
               "re-priced figure. They are used in NO re-priced figure -- every re-price is on "
               "points or points-per-minute -- so they cannot have influenced the answer to step 3."},
    {"item": "Two leads were skipped rather than approximated.",
     "detail": "D074/D079 and D072. The tempting approximation for D074/D079 was to substitute the "
               "total-attempts rung for the zone-attempts response; it was not done, because that "
               "is a different quantity wearing the same name and would have produced a complete "
               "table that was not honest."},
    {"item": "The reference-effect direction was not predicted in advance.",
     "detail": "I did not preregister which way each lead would move. The finding that D089 GROWS "
               "and D099's points figure SHRINKS is therefore descriptive, not a confirmed "
               "prediction, and should be read that way."},
    {"item": "The D099 anchors are reconstructions, not byte reproductions.",
     "detail": "E1_I0025 stores no frame, so D099's construction was rebuilt from D098's "
               "preregistered base list (BASE_COMPLETE + the usage main effect) joined to the "
               "defence column in E0_I0016's frozen frame. The anchor on the common rows is "
               "+0.005343 (points) against a published +0.003335 on a larger row set. The "
               "reconstruction is close in form but is NOT certified equal to D099's code path."},
]

F["deliverables"] = sorted(os.listdir(OUT))
with open(os.path.join(OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(F, fh, indent=1, default=str)
print("FINDINGS.json written (%d bytes)" % os.path.getsize(os.path.join(OUT, "FINDINGS.json")))
print(json.dumps(F["HEADLINE"], indent=1)[:3000])
