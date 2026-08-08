"""E0_I0016 s06 -- add the narrative sections to FINDINGS.json (kit feedback, design defect, leads).

Kept as a separate step because the two items it records were both found AFTER the screen ran:
the superseded decomposition (found by the E06 sanity anchor) and kit defect K0 (found by the
final partition sweep in s05).  Recording them by hand-editing FINDINGS.json would have been
untraceable; this script makes the addition reproducible.
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ep_base import OUT, hdr

P = os.path.join(OUT, "FINDINGS.json")
with open(P, encoding="utf-8") as fh:
    fi = json.load(fh)

fi["headline"] = (
    "THREE candidates clear a family-wise correction against a matched strictly-prior reference, "
    "and NONE of them is a defensive matchup. The opponent defensive-matchup family is DEAD: 0 of "
    "36 cells survive, best dR2 0.00144. Attrition 132 cells -> 21 per-candidate -> 8 family-wise "
    "-> 3 distinct candidates, of which 2 fail their own follow-up kill tests. LEADS, NOT RESULTS."
)

fi["per_family_attrition"] = json.loads(
    pd.read_csv(os.path.join(OUT, "family_attrition.csv")).to_json(orient="records"))

fi["leads"] = [
    {"rank": 1, "cell": "ppm | E06_pl_efg_prior", "dr2": 0.007171,
     "p_correct_level": 0.001664, "p_familywise": 0.001664,
     "practical_spread": "-0.0795 points/minute across outer deciles ~= -1.72 points per game",
     "what_it_is": "NOT a new observable. This is the player's own prior eFG, and it says the "
                   "points-per-minute REFERENCE IS INCOMPLETE: conditional on prior points per "
                   "minute, higher prior shooting efficiency predicts a LOWER rate per minute "
                   "(the volume/efficiency trade-off a single-rate reference cannot see).",
     "survives_kill_tests": True,
     "kill_tests": "holds under reliability controls (0.0049), in the decision stratum "
                   "(0.0028, n=5673), at the alternate entity, and in all four seasons with the "
                   "same sign.",
     "caveat": "declared in the preselection file as a SANITY ANCHOR, and it returns dR2 exactly "
               "0.000000 against y_efg where it IS the reference by construction. Report it as a "
               "reference-construction lead, never as a discovered predictor."},
    {"rank": 2, "cell": "ppm | C04_teammate_usg_present", "dr2": 0.003300,
     "p_correct_level": 0.001664, "p_familywise": 0.001664,
     "practical_spread": "-0.0406 points/minute across outer deciles ~= -0.88 points per game",
     "what_it_is": "Sum of the prior usage-per-game of the OTHER players in today's box. The only "
                   "survivor that gets STRONGER under pressure: dR2 rises to 0.00496 in the "
                   "decision stratum (n=5673) against 0.00330 overall.",
     "survives_kill_tests": True,
     "kill_tests": "holds under reliability controls (0.00164), at the alternate player_season "
                   "entity (p_N1 0.010, p_N2 0.0017), and in all four seasons with the same sign.",
     "caveat": "TWO load-bearing caveats. (1) TIP-TIME, not strictly prior: the usage values are "
               "prior, but the SET MEMBERSHIP is today's box, known ~30 min before tip. (2) DEAD "
               "on y_ts (fw p 0.885) and y_efg (fw p 1.000), the pure conversion measures. The "
               "channel is therefore SHOTS PER MINUTE, not points per shot -- a real "
               "points-per-minute lead, and NOT an efficiency-of-conversion lead.",
     "tip_time_observable": True},
    {"rank": 3, "cell": "C07_pl_usage_rank (ppm 0.00659, ts 0.00447, efg 0.00314)",
     "dr2": 0.006592, "p_correct_level": 0.001664, "p_familywise": 0.001664,
     "practical_spread": "-0.0425 points/minute across outer deciles ~= -0.92 points per game (ppm)",
     "what_it_is": "The player's rank by prior usage among the team's prior-active roster.",
     "survives_kill_tests": False,
     "kill_tests": "LARGELY A RELIABILITY/ROLE PROXY. Adding n_prior and trailing-5 prior minutes "
                   "to the base collapses it 0.00447 -> 0.000001 on ts (p 0.92/0.94) and "
                   "0.00314 -> 0.000061 on efg (p 0.46/0.46); both also die in the decision "
                   "stratum. Only ppm partly survives, shrinking 7.3x to 0.00090. Fails N1 at the "
                   "alternate player_season entity (p = 1.000).",
     "caveat": "reads as 'how noisy is this player's own reference', i.e. a shrinkage signal, "
               "not a mechanism."},
]

fi["principal_kills"] = {
    "opponent_defensive_matchup_family_A": {
        "cells": 36, "candidates": 12, "cleared_familywise": 0, "best_dr2": 0.001443,
        "constructions_tried": ["eFG allowed", "TS allowed", "paint points allowed", "blocks",
                                "3P% allowed", "3PA-share allowed", "FT-rate allowed",
                                "fouls committed", "steals", "defensive rating",
                                "fast-break allowed", "second-chance allowed"],
        "pattern": "19 of 36 cells clear N2 (the between-opponent null) and then fail N1 badly "
                   "(typically p_N1 0.83-0.998) -- the signature of a pure level difference "
                   "between opponents carrying no within-season information.",
        "conclusion": "Box-score-derived opponent defensive quality does not predict an individual "
                      "player's scoring efficiency beyond that player's own prior rate."},
    "foul_draw_matchup_interaction_B05": {
        "cleared_familywise_raw": 3,
        "dr2_with_own_main_effects_in_base": {"ts": 0.000000, "ppm": 0.000025, "efg": 0.000001},
        "p_with_own_main_effects": {"ts": "0.95/0.95", "ppm": "0.50/0.50", "efg": "0.90/0.90"},
        "conclusion": "NOT an interaction. B05 = B03_pl_fouls_drawn_per36 x A08_opp_pf goes to "
                      "exactly zero once its own two main effects are in the base. It was "
                      "B03 wearing an opponent term as a hat, and B03 itself fails N1 at p=0.998. "
                      "This is the cleanest kill in the screen and the reason an interaction must "
                      "always be screened against its own main effects."},
    "rest_and_load_family_F": {
        "cells": 12, "cleared_familywise": 0,
        "conclusion": "HONEST ANSWER TO THE QUESTION THE BRIEF ASKED: yes, this is the already-dead "
                      "schedule-state family in new clothes. F03_minutes_load_7d is a genuinely "
                      "different construction and does have a real BETWEEN-player association "
                      "(p_N2 0.0017 on all three outcomes), but N1 kills it at p 0.58-0.86 -- i.e. "
                      "'some players play more minutes and are better', not 'accumulated load "
                      "degrades shooting'."},
    "pace_transition_family_D": {
        "cells": 18, "cleared_familywise": 0, "best_dr2": 0.001061,
        "conclusion": "Pace does not interact with efficiency. D05_transition_x_pace, the specific "
                      "fast-game/transition-shot mechanism, is nowhere near."},
}

fi["design_defect_found_and_corrected"] = {
    "what": "The FIRST pass split every candidate into an entity-season MEAN and the mean-free "
            "remainder so each piece would have a permutation scheme screenkit calls valid. It ran "
            "clean and cleared 47 of 264 cells family-wise.",
    "why_it_was_wrong": "THE ENTITY-SEASON MEAN OF A ROW IN GAME 5 INCLUDES GAMES 6..40. Both "
                        "components read the future, so no survivor on either could be a pre-game "
                        "lead. This is the retrospective-baseline trap (5 prior instances in this "
                        "program) entering through the INFERENCE MACHINERY rather than through a "
                        "baseline column.",
    "how_it_was_caught": "The preselected sanity anchor. E06_pl_efg_prior IS the eFG reference by "
                         "construction, so its increment against y_efg must be zero; instead its "
                         "two components returned an IDENTICAL dR2 of 0.040729 -- the algebraic "
                         "signature of adding b to a base already containing b+w.",
    "generalisation_for_the_program": "Any construction that centres, standardises, ranks or "
                                      "residualises within a group spanning the whole season is a "
                                      "future-reading transform, however statistical it looks. The "
                                      "TIME-WINDOW TABLE discipline should cover columns built by "
                                      "the ANALYSIS, not only columns built by the feature "
                                      "pipeline.",
    "artifacts_kept": ["s02_screen_SUPERSEDED.py", "screen_results_SUPERSEDED.csv",
                       "run_log_s02_SUPERSEDED_decomposition_read_future.txt"],
    "corrected_pass_uses_no_derived_columns": True,
}

fi["kit_feedback"] = {
    "K0_assert_partition_false_positive_on_candidate": {
        "severity": "report and fix",
        "reproduction": "KIT_BUG_REPRO.py (exit 0 = reproduced), run_log_kit_bug.txt",
        "what": "assert_partition auto-detects date columns by `\"date\" in name.lower()`. The word "
                "candi-DATE contains 'date' (so do upDATE_flag and valiDATEd). Columns named "
                "candidate / n_candidates / mae_with_candidate are parsed with pd.to_datetime, "
                "which on FLOATS does not raise -- it reads them as epoch nanoseconds, returns "
                "1970, and raises PartitionViolation on a frame whose every real value is inside "
                "2021-2024. Hit here on screen_results.csv, family_attrition.csv and "
                "FINDINGS.json::all_cells.",
        "the_actual_defect_is_an_asymmetry": "The SEASON branch has a value-plausibility guard "
                                             "(_is_season_valued) added for exactly this class of "
                                             "false hit, with a regression test in TESTS.py. The "
                                             "DATE branch has NO equivalent guard. REPRO 3 shows "
                                             "both branches on one frame: the season-named column "
                                             "holding dR2 draws is correctly SKIPPED; the "
                                             "date-named column holding MAE floats is wrongly "
                                             "CHECKED and FLAGGED.",
        "why_not_cosmetic": "The direction is conservative, but the natural workaround "
                            "date_cols=[] DISABLES the date check. REPRO 4: a frame containing a "
                            "real 2026-06-01 game date is caught by default and passes clean under "
                            "that workaround. A guard that cries wolf on the program's most common "
                            "column name trains callers to switch it off.",
        "suggested_fix": "Mirror the season branch: accept datetime64 outright; require a high "
                         "parse-success rate for object/string columns; and for NUMERIC columns "
                         "refuse the epoch reading entirely, recording them under "
                         "skipped_name_only. Add a regression test in the shape of the existing "
                         "trap-3 test: a clean 2021-2024 frame with a column named "
                         "mae_with_candidate holding MAE floats must PASS.",
        "what_this_screen_did_instead": "Named the real date columns explicitly AND added a "
                                        "compensating value-based sweep over every non-numeric "
                                        "column regardless of name (s05_verify.py). The "
                                        "unconditional numeric year-value sweep inside "
                                        "assert_partition was unaffected and stayed active. All 10 "
                                        "written artifacts verify clean.",
    },
    "K1_future_leakage_probe_verdict_overclaims": {
        "severity": "wording, but it caused a false alarm on a clean column",
        "what": "Run on refB_ppm (suspect) vs refA_ppm (clean), the probe returned 'That is only "
                "possible because it CONTAINS the future.' That sentence is FALSE here. Both "
                "columns are strictly prior by the same .shift(1)-before-.expanding() window and "
                "differ only as ESTIMATORS -- REF-B is a ratio of prior sums, REF-A a mean of prior "
                "ratios. A lower-variance estimator of a persistent quantity out-predicts a "
                "noisier one on the future without containing any of it.",
        "measured": {"corr_refB_with_future": 0.6741, "corr_refA_with_future": 0.6571,
                     "dr2_refB_over_refA_predicting_future": 0.0235},
        "positive_control_fired_correctly": {"suspect": "player's FULL-SEASON mean y_ppm",
                                             "corr_with_future": 0.8465,
                                             "dr2_over_refB_predicting_future": 0.2731},
        "suggested_fix": "State the alternative in the verdict: 'either it contains the future, OR "
                         "it is a lower-variance estimator of a persistent quantity; read the "
                         "construction to distinguish them.' The machinery is right; only the "
                         "wording over-claims, and it over-claims in the direction that makes a "
                         "caller discard a clean baseline.",
    },
    "K2_missing_machinery_between_entity_null": {
        "severity": "real gap, not a misuse",
        "what": "SCHEME_BETWEEN requires constancy within groups; forcing it with "
                "allow_nonconstant=True is what the kit itself documents as a p 'manufactured "
                "rather than measured'. SCHEME_WITHIN is refused when the feature IS constant. "
                "ANY EXPANDING PRIOR falls between the two -- and detect_grouping_level confirms "
                "empirically that NO candidate is constant within its declared entity-season in "
                "any of the 132 cells. So the between-entity question ('does WHICH opponent you "
                "face matter'), which is the entire point of a defensive-matchup family, has no "
                "valid scheme in the kit today.",
        "what_this_screen_built": "ep_base.EntitySwap / entity_swap_null -- whole entity-season "
                                  "series reassigned to other entity-seasons within the season at "
                                  "PROPORTIONAL positions, so series length and within-season "
                                  "temporal shape survive while identity dies. The proportional "
                                  "alignment is the non-obvious part: an early-season expanding "
                                  "prior is mechanically noisier than a late-season one, and a "
                                  "null that scrambled that would not compare like with like -- "
                                  "which is exactly the bias that makes the within-scheme "
                                  "conservative here.",
        "suggested_kit_addition": "permutation_null(..., scheme='entity_swap', entity_cols=..., "
                                  "order_col=...) with the same refusal discipline as the existing "
                                  "schemes. Docstring caveats: it does not preserve the exact "
                                  "marginal distribution when partners differ in length, and it is "
                                  "a randomisation of labels, not a bootstrap.",
    },
    "K3_noop_placebo_earned_its_keep": {
        "severity": "none -- a compliment",
        "what": "The identity control returned sd 1.084202e-19 (1 distinct draw value) and the "
                "'permute the grouping key and recompute' control returned 2.168404e-19, "
                "confirming that the obvious-looking control this screen might have used instead "
                "of an entity swap is the identity in disguise. Reporting the observed sd rather "
                "than asserting zero is the right call. detect_grouping_level's P2 fix also worked: "
                "it returned None with NO_COARSER_LEVEL_EXISTS on 69 cells rather than nudging "
                "toward the row null.",
    },
}

fi["limitations"] = [
    "NO SHOT-CHART DATA. data/shotcharts/*.parquet carries NO sibling manifest -> UNVERIFIABLE -> "
    "not used. Assisted-shot share, average shot distance and early-clock share -- three of the "
    "shot-quality proxies the brief specifically suggested -- were NOT SCREENED AT ALL. Family E "
    "is box-score shadows only. Getting manifests onto the shotchart files would open the single "
    "largest unscreened surface for this question.",
    "E0_I0014/analysis_frame.parquet also has no manifest, so this screen rebuilt its frame from "
    "master_player/master_team (both row-granular). Consequence: these numbers are NOT directly "
    "comparable to D076/D081 skill percentages, which are measured against the champion's "
    "walk-forward predictions. This screen never touches the champion.",
    "IN-SAMPLE ONLY. No walk-forward, no held-out season. A lead here is an association, not a "
    "forecast.",
    "N1 (within-entity-season) is biased CONSERVATIVE for any candidate that is itself an expanding "
    "prior, because permuting it destroys its collinearity with the reference and inflates the "
    "null draws. Signature: p_N1 ~ 1.000 beside a positive dR2 (B03, B06, F03, and E06 vs y_ts). "
    "Candidates killed only by N1 are NOT SHOWN, not SHOWN ABSENT.",
    "2021 is included here (D076/D081 excluded it because the champion's 2021 fold is degenerate). "
    "Since no model is scored here, 2021 is usable; per-season tables are reported for every "
    "survivor and no survivor depends on it.",
]

fi["hygiene"] = {
    "wrote_only_inside": "experiments/exploration/E0_I0016_efficiency_predictors/",
    "registry_jsonl_written": False, "decision_ledger_written": False,
    "graph_events_written": False, "idea_log_written": False,
    "E1_I0004_efficiency_transfer": "never read, never written",
    "forbidden_artifacts_not_opened": ["data/zone_maps/*",
                                       "data/w1_truth/player_game_availability.csv",
                                       "data/w1_truth/roster_asof.csv"],
    "holdout_seasons_touched": "none -- 2025/2026 never loaded, joined, plotted, described or "
                               "summarised. Verified by s05_verify.py on every written artifact.",
    "champion_model_loaded_or_retrained": False,
}

with open(P, "w", encoding="utf-8") as fh:
    json.dump(fi, fh, indent=2, default=str)

hdr("FINDINGS.json finalised")
print("  keys: %s" % list(fi.keys()))
print("  bytes: %d" % os.path.getsize(P))
print("\n  HEADLINE: %s" % fi["headline"])
for l in fi["leads"]:
    print("\n  LEAD %d  %-38s dR2=%.6f  fw p=%.4f  survives kill tests: %s"
          % (l["rank"], l["cell"], l["dr2"], l["p_familywise"], l["survives_kill_tests"]))
    print("          spread: %s" % l["practical_spread"])
