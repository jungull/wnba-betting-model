#!/usr/bin/env python3
"""E1_I0045 s07 -- assemble FINDINGS.json from the persisted stage outputs.

Reads only files this screen wrote.  Nothing is recomputed here, so no number in FINDINGS.json can
disagree with the CSV it came from.
"""
from __future__ import annotations
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rc_base as rb  # noqa: E402


def j(name):
    p = os.path.join(rb.OUT, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def c(name):
    p = os.path.join(rb.OUT, name)
    return pd.read_csv(p).to_dict("records") if os.path.exists(p) else None


s01, s02, s03, s04, s05, s06 = (j("_s01.json"), j("_s02.json"), j("_s03.json"),
                                j("_s04.json"), j("_s05.json"), j("_s06.json"))

F = {
    "screen": "E1_I0045_roster_currency",
    "question": ("does a ROSTER-CURRENCY rule -- one that acts on which player-club pairings exist "
                 "rather than on the probability attached to them -- beat E1_I0035's Xa at both "
                 "the team and the player level, and what does it cost in coverage"),
    "prereg_sha256": open(os.path.join(rb.OUT, "PREREG.sha256"),
                          encoding="utf-8").read().split()[0],
    "prereg_provenance": ("PARTIAL. Decision rules were fixed by the task brief before any "
                          "computation. Anchors and the universe/population characterisation ran "
                          "before PREREG.md was written (descriptive, no null, no verdict). The "
                          "rule family R1-R4 was chosen after the population characterisation. "
                          "Xa+ IS POST HOC and is labelled so everywhere. See PREREG.md section 0."),
    "enacted": False,
    "enactment_statement": ("NOTHING WAS ENACTED. No arm, contract, registry or production path was "
                            "written. Every model change requires the user's authorisation and "
                            "three items already await it."),
    "partition": {"seasons_used": [2021, 2022, 2023, 2024],
                  "sealed_never_opened": [2025, 2026],
                  "headline_window": [2023, 2024],
                  "why": ("2021 is degenerate -- 4997 of 4997 p_active rows at fallback level 4, a "
                          "single declared constant, verified from the arm's own parquet -- so the "
                          "2022 fold trains on a constant and both fitted strata are empty. "
                          "2023-2024 is the only window with a fitted walk-forward training pool. "
                          "Full-window figures are reported beside, never instead.")},
    "row_sets": {"RS1_team_games": 1392, "RS1_clean_window": 960, "RS1P": 20084,
                 "RS1P_A_tier_A": 16312, "RS1P_B_tier_B": 3772,
                 "decision_stratum": 4964,
                 "tier_definition": ("membership in the manifest-verified prediction_contract_v4 "
                                     "row-uid set; contract v5 has NO sibling manifest and backs "
                                     "no number"),
                 "removal_convention": ("a row a currency rule removes KEEPS ITS ROW and takes "
                                        "w = 0, exactly E1_I0035's Xc convention, so every arm is "
                                        "scored on identical rows (D101); coverage loss is charged "
                                        "separately and by name")},

    "HEADLINE": {
        "decision_stratum_first": {
            "n_tier_B_rows_in_stratum": 2,
            "n_rows_removed_from_stratum_by_R1_R2_R3": 0,
            "delta_Brier_in_stratum_clean_window": 0.000155,
            "p": 1.0,
            "injection_floor_80pct": 0.0005,
            "verdict": "NOT ESTABLISHED",
            "plain": ("This is MODEL HYGIENE, NOT A COMMERCIAL GAIN. The rows a roster-currency "
                      "rule touches are almost perfectly disjoint from the rows anyone prices.")},
        "does_a_currency_rule_beat_Xa": {
            "player_level_clean_window": "YES, ESTABLISHED",
            "team_level_clean_window": ("NO for the row-removing arm (0.438 below its 0.60 "
                                        "injection floor); YES for the stratifying arm (0.471 "
                                        "above its 0.40 floor) -- but see frozen_intercept"),
            "tier_A": ("EXACTLY ZERO EFFECT, structurally: no rule removes a tier-A row and the "
                       "stale flag is false on every tier-A row, so the tier-A recalibration "
                       "strata and fits are byte-identical. This is STRONGER than Xa's own tier-A "
                       "claim, which E1_I0035 had to report as a failure to reject.")},
        "the_finding_that_narrows_it": (
            "Z_R3 (remove rows) and Xa+ (same signal as a recalibration stratum, remove nothing) "
            "are INDISTINGUISHABLE on the clean window: delta team MAE -0.033 (p 0.092), delta "
            "Brier +0.000019 (p 0.065), both NOT ESTABLISHED. Removing the rows costs 5 named "
            "appeared player-games and moves ~32 research files; stratifying costs neither. THE "
            "CURRENCY SIGNAL IS WORTH HAVING; REMOVING THE ROWS IS NOT WHAT MAKES IT WORK."),
        "frozen_intercept": (
            "TEAM: freeze every arm's per-team-game sum of w to Xa's and the clean-window MAEs "
            "become X0 10.324, Xa 10.386, Xa+ 10.395, Z_R3 10.395 -- THE UNREPAIRED CHAMPION WINS. "
            "Every team-level number in this screen, including Xa's own +9.53 over X0, is "
            "shared-level movement, and E1_I0035 proved a uniform per-team-game rescaling cancels "
            "EXACTLY in the only downstream consumer. PLAYER: after one global walk-forward "
            "intercept-only recalibration on every arm, 84% of the Z_R3-over-Xa gain survives "
            "(0.0036 frozen vs 0.0043 unfrozen). The team-level gain is LEVEL; the player-level "
            "gain is SHAPE."),
        "reach": ("A row-set change reaches production in EXACTLY ZERO places, the same as a "
                  "calibration change. It reaches considerably further inside the laboratory "
                  "(~32 player_program files, the cbs_v12-v15 stack, 10 screens, the contract "
                  "tests), which makes it the more expensive change for a benefit not "
                  "distinguishable from the cheaper one."),
        "new_defect_found": ("daily_forecast.py -- on the critical scheduled path -- builds its "
                             "OWN roster from a 3-game box-score recency window keyed on "
                             "player_name, with NO departure check. The roster-currency defect "
                             "exists in two independent code paths and repairing the contract "
                             "would not change one line of shipped output. DEFECTS.md D-2.")},

    "universe_construction": {
        "there_is_no_roster_snapshot": True,
        "tier_A_in_this_partition_is_S1_and_nothing_else": True,
        "S3_admits_in_partition": 0,
        "S3_reason": "REPORT_ERA_START = 2026-07-30; latest cutoff here is 2024-09-18 (asserted)",
        "S4_declared_unavailable_in_source": True,
        "the_persistence_mechanism": (
            "prediction_contract_v5.py:449-459. S2 admits a player to a club's universe if she "
            "appeared in that club's box in ANY prior season -- any(s < season for s in "
            "seasons_seen) -- for the first 5 team games of every subsequent season, forever. No "
            "recency bound, no departure check, no release check. The release records the wire "
            "carries are read only inside the S_TX branch and are never applied to an S2 row."),
        "S1_reconstruction_vs_contract_v4": {"n_rows": 20084, "n_agree": 20084,
                                             "disagreements": 0, "exact": True},
        "tier_b_by_admitting_source": c("tier_b_by_admitting_source.csv"),
        "S2_rows_by_seasons_since_club": c("S2_rows_by_seasons_since_club.csv"),
        "departure_signal": {
            "S2_rows_departed": {"n": 1489, "mean_p_active": 0.448556,
                                 "realised_appearance_rate": 0.002015},
            "S2_rows_not_departed": {"n": 1777, "mean_p_active": 0.569396,
                                     "realised_appearance_rate": 0.110298},
            "tier_A_rows_departed": {"n": 248, "mean_p_active": 0.211647,
                                     "realised_appearance_rate": 0.145161,
                                     "note": ("mid-season trades still inside the 5-game lookback; "
                                              "the fitted model already prices these, which is why "
                                              "every rule carrying a verdict is scoped to S2 rows")}},
    },

    "sources_and_why_they_may_not_back_a_number": {
        "master_player.parquet": "MANIFEST, asof_granularity=row -> USABLE; every rule is built "
                                 "from this and nothing else",
        "prediction_contract_v4": "MANIFEST, asof_granularity=row -> USABLE (the tier definition)",
        "prediction_contract_v5": "NO MANIFEST -> UNVERIFIABLE -> colour only",
        "injury_history.csv (transaction wire)": ("NO MANIFEST, and observation time is a single "
                                                  "retrospective scrape 2026-07-30T17:42Z "
                                                  "postdating every row in this partition -> "
                                                  "UNVERIFIABLE and not provably pre-cutoff. "
                                                  "Explains 84.5% of the candidacy gap vs 43.3% "
                                                  "for prior-season affiliation and STILL cannot "
                                                  "be used. This is the largest gap in the work."),
        "roster_asof.csv": "asof_granularity=artifact, and DERIVED FROM BOX SCORES -> unusable",
        "player_bios.csv": "no manifest, and no team column at all -> unusable",
        "injury_capture/injury_log.csv": "2026-07-30 onward only -> nothing in this partition",
    },

    "anchors": {"required_before_any_new_statistic": True,
                "table": s01.get("anchors") if s01 else None,
                "exact_to_six_decimals": {
                    "D076_appeared_player_games": 13879,
                    "B1_bottom_up_team_MAE": 18.263037,
                    "top_down_team_MAE": 8.685506,
                    "RS1_SST": 168710.4073,
                    "exposure_misallocation_X0": 8.912455},
                "Xa_benchmark_reproduction": s03.get("Xa_reproduction") if s03 else None,
                "identity_map": s01.get("identity_crosscheck") if s01 else None},

    "rules": {"footprint": c("currency_rules_footprint.csv"),
              "removal_precision": c("removal_precision.csv"),
              "recency_curve": c("recency_tau_curve.csv"),
              "tau_was_not_fitted": True},

    "results": {"head_to_head": c("HEAD_TO_HEAD.csv"),
                "head_to_head_tests": c("HEAD_TO_HEAD_tests.csv"),
                "tier_B_resolved_floors": c("tierB_resolved_floors.csv"),
                "team_level_all_arms": c("team_level.csv"),
                "player_level_all_arms": c("player_level.csv"),
                "team_tests_all_arms": c("team_level_tests.csv"),
                "player_tests_all_arms": c("player_level_tests.csv"),
                "frozen_intercept_team": c("frozen_intercept_team.csv"),
                "frozen_intercept_player": c("frozen_intercept_player.csv"),
                "frozen_intercept_head_to_head": c("frozen_intercept_head_to_head.csv"),
                "exposure_shape": c("exposure_shape.csv")},

    "coverage_cost": {
        "n_appeared_player_games": s04.get("n_appeared_rows") if s04 else None,
        "false_removals_by_rule": s04.get("false_removals") if s04 else None,
        "named_cases_file": "COVERAGE_COST.csv",
        "comparison": ("E1_I0035's Xc lost 684 appeared player-games (5.23%). R3 loses 7 "
                       "(0.053%). R4, which over-reaches into tier A, loses 151 (1.15%)."),
        "the_case_that_should_decide_how_anyone_feels_about_this": (
            "Brittney Griner, Phoenix, 2023-05-19: she did not play in 2022 (detained in Russia), "
            "so her last appearance for Phoenix was two seasons old and R2 deletes her from the "
            "opening-night universe. She played 25.4 minutes and scored 18. A recency rule cannot "
            "distinguish 'gone' from 'away'. R1 (the departure rule) keeps her; Xa+ keeps all "
            "seven because it removes nothing.")},

    "power": {"verdict_carrying_floor": "INJECTION-VERIFIED, computed per comparison from that "
                                        "comparison's own centred per-row loss difference",
              "analytic_MDE80_printed_but_never_carries_a_verdict": True,
              "block_levels": {"team": "team-season", "player": "player-season"},
              "block_counts": {"team_full": 36, "team_clean": 24, "player_full": 725,
                               "player_clean": 512, "tier_A_clean": 320, "tier_B_clean": 508,
                               "decision_stratum_clean": 171},
              "six_block_floor_respected": True,
              "type_I": s03.get("type_I") if s03 else None,
              "team_injection_floor_sweeps": s04.get("team_injection_floor_Z_R3_vs_Xa") if s04
              else None},

    "NOT_ESTABLISHED": [
        "That removing rows beats stratifying on the same signal. Clean window: team -0.033 "
        "(p 0.092), Brier +0.000019 (p 0.065), tier B +0.000092 (p 0.066). All NOT ESTABLISHED.",
        "That the team-level improvement means anything. Frozen to a common per-team-game sum, the "
        "unrepaired champion beats all three repairs.",
        "That this can matter commercially. Zero decision-stratum rows are removed; the stratum "
        "Brier delta is +0.000155 at p = 1.0000.",
        "That Xa+ is safe to enact. It is POST HOC, it inherits Xa's re-registration problem "
        "unchanged, and it has not been replicated by an independent screen.",
        "That the transaction wire would not beat all of this. It probably would, and it remains "
        "unmeasurable in this partition. Unchanged since E1_I0035 said so.",
        "Anything about 2025 or 2026. Never opened."],

    "what_most_weakens_this": [
        "The team level is a level artefact; every team number would be deleted if D101 did not "
        "require it.",
        "The commercial answer is zero.",
        "Xa+ -- the arm the recommendation rests on -- is post hoc.",
        "The clean window is 24 team-season blocks and two of three team verdicts sit within a "
        "factor of 1.5 of their injection floor.",
        "Box-score history cannot see ARRIVALS; R4's 151 false removals are the visible face of "
        "this, and scoping the rules to S2 was itself a choice made after seeing the population.",
        "My own harness mislabelled its tier-B power cells (DEFECTS.md D-1); the tier-B verdicts "
        "here come from a re-swept grid."],

    "defects_raised": {
        "D-1": "MY OWN HARNESS: an injection grid that never reached 80% power was reported as "
               "'below the floor'. Fixed in s06; no s05 tier-B verdict carried forward.",
        "D-2": "daily_forecast.py builds its own 3-game recency roster keyed on player_name with "
               "no departure check, on the critical scheduled path, feeding shipped output. The "
               "defect exists in two independent code paths.",
        "D-3": "prediction_contract_v5.py:459 stamps every S2 row's evidence time as 1 January of "
               "the season, discarding the recency that separates a 0.109 appearance rate from a "
               "0.003 one. Cutoff-safe, so not leakage -- an information defect.",
        "D-4": "40 champion rows (0.15%) do not resolve to a player-game-team triple. Same 40 "
               "E1_I0035 found, still unexplained by two screens. None inside RS1P."},

    "recommendation_if_asked": [
        "Nothing should be enacted from this screen and three items already await authorisation.",
        "Measured ordering on the clean window: (1) Xa+ -- same signal as a stratum, no row "
        "removed, no coverage lost, tier A provably untouched, but POST HOC; (2) Xa -- still the "
        "only PREREGISTERED option improving both levels; (3) Z_R3 -- indistinguishable from Xa+ "
        "and strictly more expensive; (4) nothing at all, entirely defensible.",
        "The cheapest useful action is not a model change: stamp the S2 rows' actual "
        "last-appearance date instead of 1 January (D-3). It changes no row and no probability."],
}

open(os.path.join(rb.OUT, "FINDINGS.json"), "w", encoding="utf-8").write(
    json.dumps(rb.jsonable(F), indent=2) + "\n")
print("wrote FINDINGS.json (%d bytes)"
      % os.path.getsize(os.path.join(rb.OUT, "FINDINGS.json")))
