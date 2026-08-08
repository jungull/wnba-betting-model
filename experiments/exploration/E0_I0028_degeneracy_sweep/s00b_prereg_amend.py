"""E0_I0028 -- STEP 00b: PREREG AMENDMENT, DECLARED AND HASHED.

*** THIS IS A DEVIATION FROM A PREREGISTERED PLAN AND IS RECORDED AS ONE. ***

WHAT TRIGGERED IT.  Step 01's own inventory print, before any defect statistic was computed:

    cbs_v15_player_oof_v5   21617 predicted rows for 2022-2024
    cbs_v14_player_oof      17809 predicted rows for 2022-2024
    prediction_contract_v4  17809 rows for 2022-2024

The original prereg named ONE truth source, `prediction_contract_v4\player_game.parquet`, for both
arms.  That is wrong: the two arms sit on DIFFERENT CONTRACTS.  `prediction_contract_v5\
player_game_enriched.parquet` has exactly 6333+7418+7866 = 21617 rows for 2022-2024, matching v15
row for row.

WHY THIS MATTERS MORE THAN A PLUMBING NIT.  Joining v15 to the v4 contract inner-joins away
*** 3808 rows, 17.6% of the v15 arm's output ***.  Those rows are not a random sample -- they are
precisely the obligations v5 added and v4 did not carry, which is exactly the population a
degeneracy sweep must not lose.  A degenerate region living in those rows would have been INVISIBLE
to this screen, and the screen would have reported a clean bill of health it had not earned.

WHAT CHANGES, AND WHAT DOES NOT.
  CHANGED  : the input path binding.  Each arm is now joined to ITS OWN contract.
  ADDED    : 6 partitions, available only on the v5 contract, which carries pre-game observables
             the v4 contract does not have.  Recorded as ADDITIONS, not as always-having-been-there.
  DROPPED  : 0.  No partition, no defect family, no threshold, no baseline and no deliverable
             definition is removed, relaxed or reworded.
  UNCHANGED: all 14 original partitions, all 6 defect families, every flag threshold, all 3
             baselines, the k grid, the walk-forward tuning rule, the ranking rule and the
             routing-gain definition.

WHERE THIS COULD HAVE CHEATED, STATED PLAINLY.  An amendment made after looking at data is the
classic route to a flattering result.  The protection here is that the amendment is made on a
ROW-COUNT MISMATCH ALONE -- no defect statistic, no error, no skill number had been computed when
it was written (step 01 crashed on a column-name collision before reaching any of them; the run log
`run_log_s01_FAILED.txt` is kept as evidence of exactly how far it got).  The amendment also makes
the screen's job HARDER, not easier: it restores 3808 rows that could contain defects and adds 6
more partitions that could flag.  An amendment that only ever adds falsification surface is not a
cherry-pick.
"""
import hashlib
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))
ORIGINAL_SHA = "895bac8bc2255c9d660ac956873884eefbc95ddab6128fd80cbf90b8cbc6dac0"

AMENDMENT = {
    "amends_prereg_sha256": ORIGINAL_SHA,
    "trigger": "row-count mismatch surfaced by step 01's inventory print, before any defect "
               "statistic, error or skill number was computed",
    "counts": {"added": 6, "dropped": 0, "corrected": 1, "reworded": 0, "relaxed": 0},

    "corrected_1_truth_source_binding": {
        "before": {"both_arms": r"experiments\prediction_contract_v4\player_game.parquet"},
        "after": {
            "cbs_v14_player_oof": r"experiments\prediction_contract_v4\player_game.parquet",
            "cbs_v15_player_oof_v5":
                r"experiments\prediction_contract_v5\player_game_enriched.parquet",
        },
        "evidence": {
            "v15_predicted_rows_2022_2024": 21617,
            "contract_v5_rows_2022_2024": 21617,
            "contract_v4_rows_2022_2024": 17809,
            "v14_predicted_rows_2022_2024": 17809,
            "rows_that_would_have_been_silently_dropped_from_v15": 3808,
            "share_of_v15_output_that_would_have_been_lost": 0.1761,
        },
        "why_it_is_material": "the dropped rows are not a random sample; they are exactly the "
                              "obligations contract v5 added. A degenerate region living there "
                              "would have been invisible and the screen would have reported a "
                              "clean bill of health it had not earned.",
    },

    "added_partitions_v5_contract_only": {
        "P15_universe_tier": "universe_tier",
        "P16_evaluation_tier": "evaluation_tier",
        "P17_fit_eligible": "fit_eligible",
        "P18_candidate_source": "candidate_source",
        "P19_team_assignment_confidence": "team_assignment_confidence",
        "P20_roster_evidence_regime": "roster_evidence_regime",
    },
    "added_partitions_note": "all six are PRE-GAME OBSERVABLE (they describe how the row entered "
                             "the forecasting universe, established at or before the cutoff) and "
                             "therefore satisfy constraint C3. On the v14 arm they do not exist "
                             "and are recorded as NOT_AVAILABLE rather than silently skipped.",

    "unchanged": ["all 14 original partitions", "all 6 defect families", "every flag threshold",
                  "B0/B1/B2 baseline definitions", "the k grid [0.5,1,2,3,5,8,12,20]",
                  "the walk-forward tuning rule and the untuned k=5 default for 2022",
                  "the ranking rule (by routing gain)", "the routing-gain definition",
                  "the block sign-flip inference rule", "the 2022-2024 partition constraint"],
}


def main():
    blob = json.dumps(AMENDMENT, sort_keys=True, separators=(",", ":")).encode("utf-8")
    h = hashlib.sha256(blob).hexdigest()
    AMENDMENT["_amendment_sha256"] = h
    p = os.path.join(OUT, "_prereg_amendment.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(AMENDMENT, fh, indent=2, sort_keys=True)
    print("=" * 100)
    print("PREREG AMENDMENT -- E0_I0028_degeneracy_sweep")
    print("=" * 100)
    print("  amends prereg  : %s" % ORIGINAL_SHA)
    print("  amendment sha  : %s" % h)
    print("  ADDED   : %d partitions (v5-contract-only pre-game observables)"
          % AMENDMENT["counts"]["added"])
    print("  DROPPED : %d" % AMENDMENT["counts"]["dropped"])
    print("  CORRECTED: %d (truth-source binding, per arm)" % AMENDMENT["counts"]["corrected"])
    print("  wrote %s" % p)
    return h


if __name__ == "__main__":
    main()
