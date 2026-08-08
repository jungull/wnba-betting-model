#!/usr/bin/env python3
"""E1_I0035 s06 -- assemble FINDINGS.json from the step files, with verdicts."""
from __future__ import annotations
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import av_base as ab  # noqa: E402


def load(n):
    p = os.path.join(ab.OUT, "_s%s.json" % n)
    return json.loads(open(p, encoding="utf-8").read())


s02, s03, s04, s05 = load("02"), load("03"), load("04"), load("05")

prereg_hash = open(os.path.join(ab.OUT, "PREREG.sha256"),
                   encoding="utf-8-sig").read().strip()

F = {
    "screen": "E1_I0035_availability_sum",
    "question": ("Reproduce E1_I0033's availability-sum defect independently, locate the "
                 "mechanism in code, characterise the tier-B population, measure candidate "
                 "repairs at BOTH the team and the player level, and determine whether the "
                 "defect reaches production."),
    "prereg_sha256": prereg_hash,
    "seed": ab.SEED,
    "partition": {"opened": list(ab.EXPLORATION_SEASONS),
                  "scored": list(ab.SCORED_SEASONS),
                  "sealed_never_opened": list(ab.FORBIDDEN_SEASONS)},
    "no_repair_enacted": True,
    "enactment_note": ("Nothing in this screen writes to any arm, contract, registry or "
                       "production path. Every model change requires the user's authorisation."),

    # ------------------------------------------------------------------ 1
    "step_1_reproduction": {
        "verdict": "CONFIRMED -- every disputed quantity reproduced within 5e-4",
        "anchor_reproduced_before_any_new_statistic": s02["anchor_D076_appeared"],
        "identity_map": s02["identity_crosscheck"],
        "identity_map_note": ("row_uid -> (player_id, game_id, team_id) RECOMPUTED from "
                              "cbs_obligation_key/1 over 519,920 triples and verified EXACT on "
                              "all 22,659 contract-v4 rows. prediction_contract_v5 carries the "
                              "arm's real universe_tier column but has NO sibling manifest -> "
                              "UNVERIFIABLE -> used for no number."),
        "row_set_RS1": s02["RS1"],
        "table": s02["reproduction"],
        "level_bias": s02["level_bias"],
        "exact_matches": ["B1_BOTTOMUP_AVAIL MAE 18.263037 (6 dp)",
                          "A_TEAM MAE 8.685506 (6 dp)",
                          "RS1 = 1392 team-games, 432/480/480",
                          "D076 appeared player-games 13,879"],
    },

    # ------------------------------------------------------------------ correction
    "correction_to_E1_I0033": {
        "status": "SIBLING SCREEN CORRECTED -- one user-facing sentence is wrong",
        "wrong_claim": ("WHICH_LEVEL_WINS.md section 2(b): 'The excess sits in the universe's "
                        "tier-B fallback rows, which receive a declared-constant p_active of "
                        "0.80 against a realised appearance rate of 0.10.'"),
        "why_wrong": ("Only 1,625 of 3,772 tier-B rows (43.1%) carry the declared constant "
                      "0.800. The other 2,147 (56.9%) carry a FITTED ridge-logistic value "
                      "averaging 0.3167 against a realised appearance rate of 0.0172."),
        "the_screens_own_NOTES_md_is_correct": ("NOTES.md section 4.4 states the tier-B mean as "
                                                "0.5249, which reproduces exactly."),
        "propagated_to": ["E1_I0033/DEFECTS.md", "E1_I0033/player_value_scope.md"],
        "what_survives_unchanged": ("Every NUMBER in E1_I0033 reproduces exactly. The gap "
                                    "decomposition, the 81.7% share, the +8.14 level bias and "
                                    "the whole which-level-wins conclusion are untouched. Only "
                                    "the one-sentence mechanism attribution is wrong."),
        "second_refinement": ("The excess is not confined to tier B. Tier A contributes "
                              "-0.2107 players per team-game (it slightly UNDER-predicts "
                              "availability). The net +0.9365 is tier-B-constant +0.6853, "
                              "tier-B-fitted +0.4618, tier-A -0.2107."),
        "tier_B_share_declared_constant": s02["tier_B_share_declared_constant"],
        "tier_A_share_declared_constant": s02["tier_A_share_declared_constant"],
        "excess_attribution": s02["excess_attribution"],
    },

    # ------------------------------------------------------------------ 2
    "step_2_mechanism": {
        "declared_constant": {
            "value": s02["declared_p_active_constant"],
            "defined_at": "cbs_generator.py:71-78, DECLARED['p_active']['point'] = 0.800",
            "applied_at": ("cbs_v7.py:1341  pa_point = p_hat.where(lvl_pa == 0, "
                           "DECLARED['p_active']['point'])  -- the FITTED logistic output is "
                           "DISCARDED and replaced by the constant on EVERY row whose "
                           "player_fallback_level is nonzero"),
            "level_rule": ("cbs_v7.player_fallback_level, driven by n_prior_candidate_games: "
                           "1-2 prior -> level 2; 0 prior or non-finite centre -> level 3; "
                           "season 2021 -> level 4"),
            "is_it_learned": "NO",
            "is_it_a_derived_prior": "NO",
            "provenance": ("project_docs/CONTRACT_BASELINE_SUITE_V2.md section 9 derives the "
                           "four sibling constants arithmetically (200/10=20.0 minutes; "
                           "70*(20/200)=7.0 attempts; 82*(20/200)=8.2 player points; 82.0 team "
                           "points). experiments/registry.jsonl's contract_baseline_suite_v2 "
                           "record carries a 'derivations' dict with exactly those FOUR keys. "
                           "p_active is in the value table and is NOT in the derivations dict. "
                           "It is an undefended round number."),
            "frozen": ("Registered in experiments/registry.jsonl (v2 frozen_config, carried "
                       "forward by supersession to v14) behind an explicit no-retuning clause. "
                       "ABSENT from experiments/player_program/arm_registry.jsonl."),
            "UNAUTHORISED_SCOPE": ("The spec scopes declared constants to ladder level 4 "
                                   "(season:2021, no training fold exists) and level 1 "
                                   "(degenerate fold). NO DOCUMENT authorises the level-2 or "
                                   "level-3 substitution for p_active on fully-fitted seasons. "
                                   "tests/test_cbs_generator.py:191 tests only the 2021 path."),
        },
        "train_score_population_mismatch": {
            "rule": ("prediction_contract_v5.py seam 3: 'TRAIN FILTER -- the training frame is "
                     "Tier A rows only'. The ridge logistic is FIT on a population with base "
                     "rate 0.7788 and APPLIED to a population with base rate 0.1015."),
            "consequence": ("The fitted tier-B rows carry mean p_active 0.3167 against a "
                            "realised 0.0172 -- an 18x over-statement, with no constant "
                            "involved anywhere. This half of the defect is NOT a fallback "
                            "constant."),
            "nothing_reads_the_label": ("The contract carefully labels these rows tier B and "
                                        "states that current roster membership is NOT "
                                        "established. No line in the emission path reads "
                                        "universe_tier. The arm throws the label away."),
        },
        "is_this_a_third_instance_of_the_fallback_constant_pattern": {
            "answer": ("PARTLY, AND THE PROGRAMME ALREADY LOGGED IT AS THE THIRD. "
                       "DECISION_LEDGER D111 ruling 3 names the availability sum as 'the third "
                       "structural defect this programme has found by looking at what the model "
                       "EMITS rather than at what predicts the outcome.'"),
            "prior_instance_1": ("D092 / D102 -- the champion emits a constant at "
                                 "fallback_level <= 2 for minutes/points/attempts and keeps "
                                 "emitting it after it has started to know something."),
            "prior_instance_2": ("E0_I0028 DEFECT_A (raised under D102 ruling 4, no D-number) "
                                 "-- pred_sd is exactly one value per season on every "
                                 "continuous target, correlation with realised absolute error "
                                 "indistinguishable from zero."),
            "where_this_one_DIFFERS": ("Only 73.2% of the net excess is the constant. The "
                                       "remaining 49.3% (tier-B fitted) minus 22.5% (tier-A, "
                                       "negative) is a TRAIN/SCORE POPULATION MISMATCH, which "
                                       "neither prior instance has. A pure fallback-constant "
                                       "repair would leave roughly half the excess in place."),
            "documented_counterexample_not_overlooked": ("E0_I0028 found that routing the v15 "
                                                         "p_active declared-constant region to "
                                                         "a prior-appearance-rate estimator "
                                                         "LOSES 4.96% of pooled Brier skill -- "
                                                         "the flat 0.8 beats that particular "
                                                         "replacement there. Repair Xa below is "
                                                         "a RECALIBRATION of the constant, not "
                                                         "a replacement estimator, so it is not "
                                                         "the comparison E0_I0028 ran."),
        },
        "by_tier_and_fallback_level": s02["by_tier_and_level"],
    },

    # ------------------------------------------------------------------ D090
    "reconciling_D090": {
        "question": "D090 called this forecast GOOD. Both can be true. How?",
        "answer_one_sentence": ("AUC is invariant to any monotone transform of the scores; a "
                                "SUM is not. A forecast can rank every player correctly and "
                                "still add up to the wrong number of basketball players."),
        "answer_two_the_row_set": ("D090 scored n = 17,809 player-games at base rate 0.7793 -- "
                                   "essentially the tier-A set. Its own DEF-2 records that "
                                   "3,808 v15 forecasts were EXCLUDED because "
                                   "prediction_contract_v5 has no manifest, and those are "
                                   "exactly the marginal-roster tier-B rows where the defect "
                                   "lives. D090's constant-detection probe counted only "
                                   "is_cold_start rows -- 18 rows on v15 -- against the 2,239 "
                                   "rows that actually carry 0.800. It saw under 1% of the "
                                   "affected population."),
        "recomputed_on_my_rows": s02["per_player_calibration"],
        "the_arithmetic": ("On tier A alone: n=16,312, base 0.7788, mean_p 0.7608, Brier "
                           "0.0932, AUC 0.8979 -- D090's picture, reproduced. Add tier B and "
                           "AUC RISES to 0.9026 while mean_p 0.7165 sits 0.0649 above a base "
                           "rate of 0.6516. Discrimination improves; the level breaks. That is "
                           "the whole paradox."),
        "D090_is_not_wrong": ("D090's verdict is correct on the rows it scored and its AUC "
                              "reproduces to 0.8979 vs 0.9016 on a slightly different row set. "
                              "It is not in dispute and is not corrected here."),
    },

    # ------------------------------------------------------------------ 3
    "step_3_population": {
        "verdict": ("PREDOMINANTLY A DATA-FRESHNESS / ROSTER-MEMBERSHIP DEFECT, with a "
                    "calibration defect layered on top. The task's distinction matters and it "
                    "falls on the freshness side."),
        "footprint": s03["P01_footprint_by_tier"],
        "headline": s03["P03_headline"],
        "staleness_by_last_appearance_anywhere": s03["P03b_anywhere_tierB"],
        "reading": {
            "definitional": ("100% of tier-B rows are for players with NO prior admitted box "
                             "row (DNP included) for that club that season. That is what makes "
                             "them tier B."),
            "stale_prior_season": ("69.9% (2,637 rows) last appeared ANYWHERE over 200 days "
                                   "earlier, i.e. in a prior season. p_active 0.5355 against a "
                                   "realised 0.1107; 82.4% never appear for that club again "
                                   "that season. Carries 0.805 of the 1.147 tier-B excess."),
            "wrong_team": ("23.4% (882 rows) appeared somewhere within the last 7 days -- for "
                           "a DIFFERENT club. Realised appearance rate for THIS club: 0.0068 "
                           "(6 of 882). 98.1% never appear for this club. p_active 0.4723. "
                           "These are wrong-team rows: the player is active in the league and "
                           "is not on this roster."),
            "genuine_debutants": ("5.2% (195 rows) had never appeared anywhere before. "
                                  "Realised rate 0.3692, p_active 0.6939 -- the only band "
                                  "where a high value is defensible, and still ~1.9x too "
                                  "high."),
            "never_played_at_all": "0.95% of tier-B rows are players with no appearance anywhere in 2021-2024.",
            "not_deep_bench": ("These are not deep-bench or two-way players. Named examples "
                               "carrying the most excess mass are established starters held "
                               "against clubs they had left: Crystal Dangerfield (44 rows, 3 "
                               "appearances), Tina Charles, Liz Cambage, Courtney Williams, "
                               "Natasha Howard."),
        },
        "why_this_changes_the_fix": ("A calibration repair lowers the probability attached to a "
                                     "player-club pairing that mostly does not exist. A "
                                     "freshness repair stops manufacturing the pairing. The "
                                     "first is measurable here and is what Xa does; the second "
                                     "requires a roster source the contract explicitly declines "
                                     "to trust (prediction_contract_v5.py: tier B is 'included "
                                     "through weaker but cutoff-safe evidence; current roster "
                                     "membership is NOT established') and cannot be evaluated "
                                     "from these artifacts."),
        "bios_UNVERIFIABLE": s03["P02_bios_UNVERIFIABLE"],
        "retrospective_use_declared": ("'never appears for this team again this season' looks "
                                       "FORWARD. It is used ONLY to characterise the "
                                       "population. No repair is built or tuned on it and no "
                                       "number in step 4 depends on it."),
    },

    # ------------------------------------------------------------------ 4
    "step_4_repairs": {
        "no_repair_enacted": True,
        "team_level": {"row_set": "RS1, n=1392, response master_team.pts, SST 168710.4073, "
                                  "no weighting, no base",
                       "table": s04["team_table"], "tests": s04["team_tests"]},
        "player_level": {"row_sets": "RS1P n=20084 / RS1P-A n=16312 / RS1P-B n=3772; responses "
                                     "`appeared` (Brier, logloss, AUC) and `pts` (uncond. E[pts])",
                         "table": s04["player_table"], "tests": s04["player_tests"]},
        "conditional_invariance": s04["conditional_pts_hat_MAE"],
        "Xc_coverage_cost": s04["Xc_coverage"],
        "Xd_affine": s04["Xd_affine"],
        "Xa_walkforward_fits": s04["Xa_fits"],
        "exposure_shape": s05["exposure_shape"],
        "verdicts": {
            "Xa_recalibrate_per_tier": ("THE ONLY REPAIR THAT PASSES BOTH LEVELS. Team MAE "
                                        "18.263 -> 10.957 (+7.306, p<0.0001, injection floor "
                                        "2.00). Player Brier 0.1302 -> 0.0947 overall and "
                                        "0.2905 -> 0.1004 on tier B, both ESTABLISHED. Tier-A "
                                        "Brier moves -0.000148, far below the 0.0025 injection "
                                        "floor -> NOT ESTABLISHED, i.e. no harm demonstrated "
                                        "(and none COULD be demonstrated below the floor -- "
                                        "this is a failure to detect, not proof of safety). "
                                        "Conditional pts_hat untouched. Exposure "
                                        "misallocation 8.91 -> 4.01 minutes per team-game."),
            "Xb_normalise_the_sum": ("FAILS THE PLAYER LEVEL. Best honest team result "
                                     "(MAE 9.453, +8.810) but tier-A Brier degrades by 0.01424, "
                                     "5.7x the injection floor -> ESTABLISHED HARM, and the "
                                     "tier-A calibration slope falls from 1.059 to 0.710. It "
                                     "fixes the team sum by shrinking the ~13,600 tier-A rows "
                                     "that were already well calibrated. AND it does NOTHING "
                                     "downstream: the exposure producer renormalises to 200 "
                                     "team-minutes, so a per-team-game uniform rescaling "
                                     "cancels exactly -- Xb's misallocation is 8.91, identical "
                                     "to X0 to the last digit. This is precisely the case the "
                                     "task warned about."),
            "Xc_prune_the_universe": ("FAILS EVERYTHING. Weakest team gain (+2.249), tier-A "
                                      "Brier harm 0.01256 (5.0x floor, ESTABLISHED), log-loss "
                                      "0.406 -> 0.775, calibration slope collapses to 0.221, "
                                      "and 684 appeared player-games (5.23%) are left with NO "
                                      "FORECAST AT ALL. A props book cannot price a player it "
                                      "has deleted."),
            "Xd_correct_downstream": ("BEST TEAM MAE, ZERO INFORMATION, ZERO PLAYER EFFECT. "
                                      "MAE 8.794 (+9.469) but the walk-forward affine slope is "
                                      "0.000 / -0.016 / -0.021 and correlation with the "
                                      "response is -0.021: it emits a near-constant. It "
                                      "sharpens E1_I0033's counterweight -- the slope is not "
                                      "merely small, it is NEGATIVE. And it changes nothing at "
                                      "the player level, which is where the product is."),
            "Xa_oracle_ceiling": ("The same construction fitted in-sample reaches team MAE "
                                  "10.414, player Brier 0.0910 and misallocation 1.76 minutes. "
                                  "The walk-forward version captures most of it. ORACLE -- "
                                  "carries no verdict."),
        },
    },

    # ------------------------------------------------------------------ 5
    "step_5_production_reach": {
        "verdict": "THE DEFECT DOES NOT REACH PRODUCTION. It is confined to research paths.",
        "urgency": ("LOW as a live risk. HIGH as a GATE: it must be repaired before anything "
                    "bottom-up, exposure-based or props-facing that consumes p_active is "
                    "promoted."),
        "nothing_shipped_reads_p_active": ("Zero hits for p_active in daily_forecast.py, "
                                           "daily_refresh.py, daily_certify.py, props_edge.py, "
                                           "props_capture_daily.py, conditional_edge.py, "
                                           "calibrated_prob_edge.py, and in the "
                                           "wnba-prediction-engine, wnba_odds_system, "
                                           "wnba-odds-aggregator, forecasts, leaderboards and "
                                           "modeling_v2 trees."),
        "per_player_product_is_conditional": ("props_edge.py computes proj = per36_pts_ewma * "
                                              "expected_minutes / 36, where the minutes EWMA is "
                                              "taken over PLAYED rows only. There is no "
                                              "x P(active) term anywhere. A miscalibrated "
                                              "p_active CANNOT corrupt the shipped per-player "
                                              "forecast; p_active is a separate, currently "
                                              "unscored side output."),
        "the_only_multiply_site": ("experiments/player_program/build_projected_exposure.py:238, "
                                   "raw_expected_minutes = p_active * e_minutes_given_active. "
                                   "Registered production_eligible: False on ALL THREE "
                                   "regimes."),
        "does_anything_sum_p_active_per_team_game": ("NO production path does. Every "
                                                     "groupby(game,team).sum() on p_active in "
                                                     "the repository lives in three exploration "
                                                     "screens: E1_I0033, E1_I0034 and this "
                                                     "one."),
        "the_one_sensitive_path": ("build_projected_exposure allocates a FIXED 200 team-minutes "
                                   "proportionally to p_active * e_min, so a uniform p_active "
                                   "error cancels exactly and only the RELATIVE SHAPE survives. "
                                   "Measured: 14.44 of every 200 team-minutes are allocated to "
                                   "tier-B rows against 5.53 actually played -- 8.91 minutes "
                                   "per team-game taken from players who do play and given to "
                                   "players who mostly do not. Xa cuts that to 4.01; Xb leaves "
                                   "it unchanged at 8.91."),
        "the_live_champion": ("MISSION_LEDGER freeze-v0 (tag f1b6ce5), run by daily_forecast "
                              "--live, emits a core-only TEAM prediction with no player arm "
                              "wired in. The player arm is BUILT-U and its scoring is "
                              "unauthorised and still open."),
    },

    "power_and_nulls": {
        "null": ("paired block sign-flip on the per-row loss difference; TEAM cells block at "
                 "team-season (36 blocks), PLAYER cells at player-season (725/488/709 blocks). "
                 "The within-player cyclic shift is NOT USED ANYWHERE (D108)."),
        "injection_floor_team_MAE": s05["injection_floor_team_MAE"],
        "injection_floor_player_tierA_Brier": s05["injection_floor_player_tierA_Brier"],
        "analytic_vs_injection": ("The analytic MDE80 = 2.802 x null_sd is computed from a "
                                  "difference vector that CARRIES the effect, which inflates "
                                  "the sign-flip null sd. On the team cell it reads 4.596 "
                                  "against an injection-derived floor of 2.00 (conservative); "
                                  "on the tier-A player cell it reads 0.00038 against an "
                                  "injection floor of 0.0025 (ANTI-conservative by 6.6x). Both "
                                  "are published and the INJECTION IS THE AUTHORITY. No verdict "
                                  "in this screen changes under either."),
        "type_I": s04["type_I"],
        "team_injection_power": s04["team_injection_power"],
        "player_injection_power_tierA": s04["player_injection_power_tierA"],
    },

    "not_established": [
        "Nothing about 2025 or 2026. Never read, joined, plotted or described.",
        ("That Xa is SAFE for tier-A player forecasts. Its -0.000148 Brier effect sits far "
         "below the 0.0025 injection floor, so the correct statement is NOT ESTABLISHED -- no "
         "harm was detected and none could have been at that magnitude (D103)."),
        ("That any repair is the RIGHT one. Four were measured on a fixed row set; the space "
         "of repairs is larger, and a freshness repair -- not manufacturing the tier-B "
         "obligation at all -- was NOT measurable from these artifacts."),
        ("That the tier-B population is what player_bios.csv says it is. That file has no "
         "sibling manifest and backs no number here."),
        ("That the exposure-shape number transfers to the real producer. It is a faithful "
         "proxy of the proportional step but omits the 40-minute cap and the water-filling."),
        ("That E1_I0033's conclusions are affected. Every number of theirs reproduces exactly; "
         "only a one-sentence mechanism attribution is corrected."),
    ],
}

out = os.path.join(ab.OUT, "FINDINGS.json")
open(out, "w", encoding="utf-8").write(json.dumps(ab.jsonable(F), indent=2))
print("wrote %s (%d bytes)" % (out, os.path.getsize(out)))

# a compact headline CSV
pd.DataFrame([
    {"repair": "X0  none (champion as emitted)", "team_MAE": 18.263037, "d_team_MAE": 0.0,
     "player_Brier_all": 0.130248, "d_tierA_Brier": 0.0, "tierA_verdict": "-",
     "exposure_misalloc_min": 14.444148 - 5.531693, "coverage_loss": 0.0,
     "passes_both_levels": "-"},
    {"repair": "Xa  recalibrate per tier (walk-forward)", "team_MAE": 10.957277,
     "d_team_MAE": 7.305759, "player_Brier_all": 0.094677, "d_tierA_Brier": -0.000148,
     "tierA_verdict": "NOT ESTABLISHED (below floor)",
     "exposure_misalloc_min": 4.005280, "coverage_loss": 0.0, "passes_both_levels": "YES"},
    {"repair": "Xb  normalise the sum to roster size", "team_MAE": 9.452877,
     "d_team_MAE": 8.810159, "player_Brier_all": 0.107621, "d_tierA_Brier": -0.014239,
     "tierA_verdict": "ESTABLISHED HARM (5.7x floor)",
     "exposure_misalloc_min": 8.912455, "coverage_loss": 0.0, "passes_both_levels": "NO"},
    {"repair": "Xc  prune the universe", "team_MAE": 16.014120, "d_team_MAE": 2.248916,
     "player_Brier_all": 0.132237, "d_tierA_Brier": -0.012558,
     "tierA_verdict": "ESTABLISHED HARM (5.0x floor)",
     "exposure_misalloc_min": 5.520223, "coverage_loss": 0.0523, "passes_both_levels": "NO"},
    {"repair": "Xd  leave it, correct level downstream", "team_MAE": 8.793884,
     "d_team_MAE": 9.469153, "player_Brier_all": 0.130248, "d_tierA_Brier": 0.0,
     "tierA_verdict": "unchanged by construction",
     "exposure_misalloc_min": 8.912455, "coverage_loss": 0.0,
     "passes_both_levels": "NO (fixes nothing at the player level; slope negative)"},
]).to_csv(os.path.join(ab.OUT, "REPAIR_SUMMARY.csv"), index=False)
print("wrote REPAIR_SUMMARY.csv")
