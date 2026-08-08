"""S11 -- assemble FINDINGS.json, add the two remaining cells, and write the run log."""
import glob, json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agg_base as ab
import s04_prereg

NDRAW = 20000


def main():
    ab.hdr("S11 FINDINGS")
    pre = s04_prereg.assert_unchanged()
    tf = pd.read_parquet(os.path.join(ab.OUT, "_team_frame_scored.parquet"))
    rs1 = tf["RS1"].to_numpy()
    y = tf.loc[rs1, "pts"].to_numpy(float)
    ts = (tf["season"].astype(str) + "_" + tf["team_id"].astype(str)).to_numpy()[rs1]

    ab.hdr("EXTRA CELLS (EXPLORATORY, added after the hash, both AGAINST the headline)")
    extra = {}
    for cid, a, b in [("X1_EXPLORATORY", "B4N_NORMALISED_CAL", "A_TEAM"),
                      ("X2_EXPLORATORY", "R2_TEAM_EWMA", "B4N_NORMALISED_CAL")]:
        la = np.abs(y - tf.loc[rs1, a].to_numpy(float))
        lb = np.abs(y - tf.loc[rs1, b].to_numpy(float))
        n1 = ab.paired_signflip_block(la, lb, ts, NDRAW, ab.SEED + 81)
        extra[cid] = {"cell": cid, "arm_A": a, "arm_B": b, "MAE_A": float(np.mean(la)),
                      "MAE_B": float(np.mean(lb)), "MAE_advantage_A_over_B": n1["real"],
                      "p": n1["p"], "null_mean": n1["null_mean"], "null_sd": n1["null_sd"],
                      "MDE80": float(2.80 * n1["null_sd"]),
                      "observed_in_null_sds": float(n1["real"] / n1["null_sd"]),
                      "exploratory": True,
                      "why_added": ("both make the FULLY REPAIRED bottom-up arm look as good as "
                                    "possible and therefore work AGAINST this screen's headline; "
                                    "adding them is the conservative direction.")}
        print("  %s %-22s vs %-22s dMAE %+.5f p %.4f (null_mean %+.2e sd %.5f) MDE80 %.5f"
              % (cid, a, b, n1["real"], n1["p"], n1["null_mean"], n1["null_sd"],
                 2.80 * n1["null_sd"]))
    pd.DataFrame(list(extra.values())).to_csv(os.path.join(ab.OUT, "exploratory_cells.csv"),
                                              index=False)

    ab.hdr("ASSEMBLE")
    F = {"screen_id": "E1_I0033_aggregation_level",
         "title": ("Does the aggregation level determine what is knowable?  Top-down versus "
                   "bottom-up on team points, walk-forward, 2022-2024 regular season."),
         "prereg_sha256": pre["prereg_sha256"],
         "prereg_cells_hashed": 14,
         "prereg_cells_added_after_hash": 5,
         "prereg_cells_dropped": 0,
         "cells_added_after_hash": [
             "B1A_TIER_A_ONLY (arm)", "B1N_ROSTER_NORMALISED (arm)",
             "P07b_EXPLORATORY (FT_COMPOSED_OVER_FLAT vs FT_FLAT)",
             "X1_EXPLORATORY (B4N vs A_TEAM)", "X2_EXPLORATORY (R2 vs B4N)"],
         "additions_direction": ("EVERY ONE of the five additions makes the BOTTOM-UP / PLAYER "
                                 "side look BETTER than the preregistered construction did, i.e. "
                                 "all five push AGAINST this screen's headline. none was added to "
                                 "rescue a result."),
         "partition": list(ab.EXPLORATION_SEASONS),
         "holdout_never_touched": [2025, 2026],
         "scored_seasons": list(ab.SCORED_SEASONS),
         "seed": ab.SEED,
         "no_champion_fitting": ("NO champion arm was refitted, retrained or modified. both arms' "
                                 "stored forecasts were read and scored as-is. every reference, "
                                 "recalibration and composition fitted here is my own and is "
                                 "authorised by D091."),
         "extra_cells": extra}
    for tag, fn in [("s05_build", "_s05.json"), ("s06_topdown_vs_bottomup", "_s06.json"),
                    ("s07_gap_decomposition", "_s07.json"), ("s08_which_level", "_s08.json"),
                    ("s09_ft_composition", "_s09.json"), ("s10_player_value", "_s10.json"),
                    ("s10b_absence_precision", "_s10b.json")]:
        p = os.path.join(ab.OUT, fn)
        if os.path.exists(p):
            F[tag] = json.load(open(p, encoding="utf-8"))

    F["defects_disclosed"] = {
        "D-1": ("the first injection-power construction was uninformative -- it measured power "
                "against ONE cell's loss-difference variance and reported it as the screen's "
                "power, and its type-I 'pass' of p=1.0000 at exactly zero effect was "
                "mechanically forced rather than measured. repaired in s07 with a PER-CELL "
                "minimum detectable effect and a genuine 400-dataset type-I check "
                "(rejection rate 0.0425). the defective file is kept on disk as "
                "injection_power.csv."),
        "D-2": ("B1_BOTTOMUP_AVAIL as preregistered carries a +8.14 point level bias driven by "
                "the champion's tier-B fallback universe, whose p_active is a declared constant "
                "of 0.8 against a realised appearance rate of 0.10. that is the LITERAL "
                "bottom-up arm and it is reported as such, but three repaired variants were "
                "added so the comparison is not a strawman."),
        "D-3": ("the preregistered DR4 gap shares do not partition the gap (roster 79.5%, level "
                "98.6%, residual -78.1%) because the ORACLE arm repairs both at once. the "
                "preregistration said shares would not be clipped; s07 adds a SEQUENTIAL "
                "decomposition whose steps do sum to the total, and both are published."),
        "file": "DEFECTS.md"}

    F["where_this_screen_could_have_cheated"] = {
        "declared_in_advance": "COMPARISONS_PRESELECTED.md section C-1..C-7",
        "C-1_realised_roster": ("summing only players who appeared. that is B3_ORACLE_ROSTER, "
                                "labelled ORACLE, excluded from every headline and every ranking. "
                                "it is the largest available cheat here and it would have made "
                                "bottom-up look BETTER (MAE 10.65 against B1's 18.26)."),
        "C-2_tuning_on_the_scored_season": ("every half-life, shrinkage constant, blend weight, "
                                            "affine calibration and beta is fitted on STRICTLY "
                                            "EARLIER SEASONS. the 2022 fold sees only 2021 and "
                                            "its thin fits are visible in the per-season tables."),
        "C-3_level_recalibration": "B4 uses earlier seasons only.",
        "C-4_rung_shopping": ("all three team reference rungs are published. the conclusion does "
                              "not depend on which is chosen: A_TEAM loses to R1 and R2 and beats "
                              "only R0."),
        "C-5_dropping_the_playoffs": ("excluded BEFORE any statistic, for D104's structural "
                                      "reason, and reported separately anyway. on the playoff "
                                      "stratum the ordering is the same."),
        "C-6_unmanifested_contract_v5": ("the identity map was RECONSTRUCTED from "
                                         "cbs_obligation_key and verified EXACT against the "
                                         "manifest-verified contract v4 on all 22,659 shared "
                                         "rows. v5 was opened once, to DESCRIBE 40 rows that "
                                         "were then dropped, and no number depends on it."),
        "C-7_cross_level_dR2": ("no team-level dR2 is compared to any player-level dR2 anywhere. "
                                "where both levels appear together only "
                                "skill-against-a-matched-reference is shown, with the response "
                                "difference stated in the same sentence."),
        "one_more_not_in_the_prereg": ("I could have quoted P02 (the team arm losing to its own "
                                       "matched reference) without noting that its observed "
                                       "effect of 0.205 MAE sits BELOW its own 80%-power MDE of "
                                       "0.251. it is significant at p 0.0159 and underpowered, "
                                       "and both facts are stated wherever it is quoted.")}

    with open(os.path.join(ab.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
        json.dump(ab.jsonable(F), fh, indent=1)
    print("  wrote FINDINGS.json (%d bytes)"
          % os.path.getsize(os.path.join(ab.OUT, "FINDINGS.json")))

    # combined run log
    parts = sorted(glob.glob(os.path.join(ab.OUT, "run_log_s*.txt")))
    with open(os.path.join(ab.OUT, "run_log.txt"), "w", encoding="utf-8") as out:
        out.write("E1_I0033_aggregation_level -- combined run log\n")
        out.write("prereg sha256 %s\n" % pre["prereg_sha256"])
        out.write("=" * 100 + "\n\n")
        for p in parts:
            out.write("\n\n" + "#" * 100 + "\n# " + os.path.basename(p) + "\n"
                      + "#" * 100 + "\n\n")
            out.write(open(p, encoding="utf-8", errors="replace").read())
    print("  wrote run_log.txt from %d step logs" % len(parts))


if __name__ == "__main__":
    main()
