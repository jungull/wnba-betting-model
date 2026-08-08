"""S08 -- assemble FINDINGS.json and the concatenated run_log.txt.  Adds no new statistic."""
from __future__ import annotations

import glob
import json
import os

import ha_base as hb

STAGES = ["_s01.json", "_s02.json", "_s03.json", "_s04.json", "_s05.json", "_s06.json",
          "_s07.json"]
NAMES = {"_s01.json": "s01_guards_and_build", "_s02.json": "s02_team_effect",
         "_s03.json": "s03_player_reconcile", "_s04.json": "s04_main_effect",
         "_s05.json": "s05_heterogeneity", "_s06.json": "s06_travel",
         "_s07.json": "s07_attendance"}


def main():
    hb.hdr("S08 ASSEMBLE FINDINGS")
    with open(os.path.join(hb.OUT, "_prereg.json"), "r", encoding="utf-8") as fh:
        prereg = json.load(fh)

    F = {
        "screen_id": "E1_I0030_home_advantage_accounting",
        "question": ("the user's accounting argument: team points are the SUM of player points, so "
                     "a measurable team-level home advantage MUST be somewhere at player level.  "
                     "Locate it."),
        "partition": list(hb.EXPLORATION_SEASONS),
        "holdout_never_touched": [2025, 2026],
        "headline_stratum": "REGULAR SEASON 2021-2024, 888 games, 1776 team-games",
        "prereg_sha256": prereg["prereg_sha256"],
        "prereg_family_size": prereg["family_size"],
        "seed": hb.SEED,
        "screenkit_version": "1.0",
        "r2_convention": ("plain unweighted R2 of a GIVEN forecast, 1 - SSE/SST, SST about the "
                          "unweighted mean of y on the same rows (D069).  Nothing refit at "
                          "scoring."),
        "null_convention": ("verdicts on the home/away contrast come from the PER-GAME SIGN FLIP "
                            "(relabel which of the two teams in a game is home) -- the exact "
                            "randomisation test for a design in which the treatment is perfectly "
                            "balanced within the cluster.  Verdicts on travel come from a CYCLIC "
                            "SHIFT within (season, team).  Cluster-robust SEs are used nowhere."),
        "stages": {},
    }
    for s in STAGES:
        p = os.path.join(hb.OUT, s)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                F["stages"][NAMES[s]] = json.load(fh)

    # ---------------- the answers, in one place
    s02, s03, s04, s05, s06, s07 = (F["stages"].get(k, {}) for k in
                                    ["s02_team_effect", "s03_player_reconcile", "s04_main_effect",
                                     "s05_heterogeneity", "s06_travel", "s07_attendance"])
    F["ANSWERS"] = {
        "1_team_effect": {
            "regular_season_home_points_advantage": 0.96509,
            "p_pergame_signflip": 0.03580,
            "all_games_incl_playoffs": 1.36392,
            "playoffs_only_DO_NOT_USE": 5.68293,
            "playoff_caveat": ("home court in the playoffs is AWARDED to the better seed, so the "
                               "playoff contrast is a team-strength contrast, not a venue "
                               "contrast.  It is reported and labelled, never pooled into the "
                               "headline."),
        },
        "2_decomposition": {
            "PACE_CANNOT_CARRY_IT": ("possessions are a shared GAME property: corr(home poss, away "
                                     "poss) = 0.816 and the home-minus-away box-estimated gap is "
                                     "+0.135 possessions (p = 0.165, n.s.).  The pace channel "
                                     "carries +0.142 of the +0.965 point gap and does not clear "
                                     "its own null.  The user's most-likely hiding place is "
                                     "structurally almost unavailable."),
            "MINUTES_CANNOT_CARRY_IT": ("team minutes are IDENTICAL for both teams in 970 of 970 "
                                        "games (200 + 25 per shared overtime).  The gap is not "
                                        "small, it is exactly zero, in every game."),
            "EFFICIENCY_CARRIES_IT": ("+0.823 of the +0.965 gap is points per possession."),
            "AND_INSIDE_EFFICIENCY_IT_IS_FREE_THROWS": {
                "ft_makes_contribution": 0.94144,
                "share_of_points_gap": 0.9755,
                "two_point_makes_contribution": -0.17568,
                "three_point_makes_contribution": 0.19932,
                "ft_attempts_gap": 1.08671,
                "fouls_committed_gap": -0.59234,
                "fouls_drawn_gap": 0.59234,
                "note": ("the exact identity pts = 2*FG2M + 3*FG3M + FTM decomposes the gap with "
                         "ZERO residual.  Free-throw makes alone are 97.6% of it; two-point makes "
                         "are NEGATIVE.  FT attempts and the foul differential are the only cells "
                         "that survive family-wise correction across the 25 preselected team "
                         "cells (p_fw = 0.00005 and 0.00015); points itself sits at p_fw = 0.029 "
                         "and points-per-possession at 0.069."),
            },
        },
        "3_reconciliation": s03.get("reconciliation_points", {}),
        "3b_within_player_split": s03.get("within_player_split", {}),
        "3c_decomposition_term_nulls": s03.get("decomposition_term_nulls", {}),
        "4_main_effect_verdict": {
            "verdict": ("NO.  Adding a home/away main-effect term to a COMPLETE strictly-prior "
                        "reference does not improve a walk-forward player forecast in any of 16 "
                        "(target x reference) cells, pooled or on the decision stratum.  Best "
                        "cell: points on the decision stratum, dR2 = +1.07e-04 on the common "
                        "denominator, MAE improvement +0.028%, p = 0.168."),
            "AND_WHY_THAT_IS_NOT_A_CONTRADICTION": (
                "the a-priori ceiling computed BEFORE fitting anything says the largest dR2 a "
                "PERFECT home term could add to player points is 4.6e-05, because the increment "
                "relative to a venue-blended reference is +0.051 points -- 0.68% of one player-"
                "game standard deviation.  The observed dR2 of +6.5e-05 is at that ceiling.  The "
                "effect is not absent; it is exactly its predicted size, and its predicted size "
                "is below the noise floor of a 13,152-row walk-forward evaluation."),
            "detection_floor": s04.get("detection_floor_arithmetic", {}),
            "negative_control": s04.get("negative_control_fake_label", []),
        },
        "5_absorption_verdict": {
            "verdict": ("REFUTED AS THE EXPLANATION.  A reference built from the player's prior "
                        "games AT THE SAME VENUE TYPE is WORSE than one built from all their "
                        "prior games in all 8 (target x form) cells, by 3.3%-5.6% MAE, p = 0.0002 "
                        "in every cell."),
            "why": ("the venue-split reference halves the effective history behind every estimate.  "
                    "The information it buys (a ~0.05-point venue increment) is two orders of "
                    "magnitude smaller than the estimation noise it adds.  Absorption is REAL as "
                    "arithmetic -- a blended reference does sit at the blend -- but it is not why "
                    "the earlier screens returned null, and un-blending the reference makes the "
                    "forecast worse, not better."),
        },
        "6_heterogeneity_verdict": {
            "verdict": ("NO detectable per-player heterogeneity under the cyclic-shift null.  "
                        "Points p = 0.109, points-per-minute p = 0.077, FT attempts p = 0.054, FT "
                        "attempts per minute p = 0.691, over 149 players with >=20 home and >=20 "
                        "away appearances.  The observed spread of per-player home-minus-away "
                        "points is 1.216 against a null mean of 1.127 -- almost all of the "
                        "apparent 'players differ' signal is sampling noise."),
            "vacuous_arm_reported": ("the relabel-the-player-key control was run and is a "
                                     "CONFIRMED NO-OP at sd ~1e-17 in all four targets, exactly as "
                                     "K7 predicts.  It is reported as vacuous rather than as a "
                                     "pass."),
        },
        "7_travel_verdict": {
            "verdict": ("REFUTED, AGAINST THE PREREGISTERED DIRECTION.  Eastbound crossings were "
                        "preregistered to HURT (negative on points and points per possession).  "
                        "The adjusted coefficient is +0.856 points -- the WRONG SIGN -- with "
                        "p = 0.869 in the preregistered lower tail.  On points per possession it "
                        "is +0.0011, p = 0.471."),
            "internal_controls_refute_the_mechanism": (
                "westbound (the EASIER circadian direction) shows a LARGER positive coefficient on "
                "points per possession (+0.0076) than eastbound (+0.0011), and SAME-ZONE travel -- "
                "real travel with no circadian component -- is the most NEGATIVE arm (-0.0055 on "
                "ppp, -0.532 on points).  If the effect were circadian these three would be "
                "ordered east < same-zone < west.  They are not."),
            "sharpest_test": ("road games only, eastbound vs westbound, which removes the home "
                              "confound entirely: raw east-minus-west = +0.006 points, adjusted "
                              "beta = +0.308, p = 0.403 in the preregistered tail; on ppp, "
                              "beta = -0.005, p = 0.256.  n = 211 vs 212."),
            "is_it_the_dead_family": (
                "YES, and it is said plainly.  The raw arm contrasts are dominated by the home "
                "indicator, not by travel: the crossing arms are 30-38% home games while the "
                "no-travel arm is 87% home games.  Once is_home and rest are held fixed nothing "
                "survives.  This is the fifth death of the rest/schedule family in this "
                "programme and it looks exactly like the previous four."),
            "dose_response": "non-monotone; tz_delta = +2 is the highest-scoring cell and +3 the "
                             "lowest, which is noise, not a dose curve.",
        },
        "8_attendance_verdict": s07.get("verdict"),
    }
    with open(os.path.join(hb.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
        json.dump(hb.jsonable(F), fh, indent=2)
    print("  wrote FINDINGS.json")

    # concatenated run log
    logs = sorted(glob.glob(os.path.join(hb.OUT, "run_log_s0*.txt")))
    with open(os.path.join(hb.OUT, "run_log.txt"), "w", encoding="utf-8") as out:
        for lg in logs:
            out.write("\n\n" + "#" * 100 + "\n### %s\n" % os.path.basename(lg) + "#" * 100 + "\n")
            with open(lg, "r", encoding="utf-8", errors="replace") as fh:
                out.write(fh.read())
    print("  wrote run_log.txt from %d stage logs" % len(logs))


if __name__ == "__main__":
    main()
