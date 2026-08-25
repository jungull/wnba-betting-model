# -*- coding: utf-8 -*-
"""M41 s03 -- PREREGISTRATION of the arm revision. Loads NO data and computes NO statistic.

This file fixes and hashes every choice in the proposed revision BEFORE it is built, so that
what is later reported can be checked against what was intended rather than against memory.
It is the same discipline as E0_I0029 s01, applied to an implementation rather than a screen.

WHY A PREREGISTRATION IS WORTH THE TROUBLE HERE. The number this revision chases has already
changed twice under examination. M38 s03 recorded 21.3%; D206 found the constant it used is one
the arm may not read and the arm-legal equivalent is 6.2%; D207 then found a better legal rule
worth 28.3%. A target that has moved that much is exactly the kind that acquires a flattering
figure during implementation unless the criterion is fixed first.

WHAT IS BEING PREREGISTERED IS AN IMPLEMENTATION, NOT A DISCOVERY. The rule is already chosen
and the holdout is already spent (see REPORT.md, "the holdout is being spent"). This revision is
therefore CONFIRMATORY: it is not permitted to search variants, and a disagreement between the
arm's result and the diagnostic's is a FINDING ABOUT THE DIAGNOSTIC'S FIDELITY, never a reason
to adjust the arm until the numbers agree.

NOTHING HERE AUTHORISES A WAGER. S42 remains closed. The model still loses to the market on the
priced population after this repair; closing part of a deficit is not an edge.
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "_prereg.json")

PREREG = {
    "prereg_id": "M41_arm_legal_fallback_repair_v1",
    "supersedes_claim_of": "M38 s03 / D184 (21.3%, not arm-legal -- see D206)",
    "authority": ["D206", "D207", "M38 s03", "M00 evidence ladder"],

    # ---------------------------------------------------------------- the change
    "change": {
        "level_3": {
            "current": "prefix-mean / league constant for e_minutes_given_active",
            "revised": "the player's OWN mean minutes across strictly PRIOR SEASONS; "
                       "fall back to the all-rows prior-season mean only where she has none",
            "coverage_expected": "93% of level-3 rows carry own prior-season minutes",
        },
        "level_2": {
            "current": "fitted rate, unshrunk",
            "revised": "shrink the fitted rate toward the player's OWN prior-season rate "
                       "(prior points / prior minutes, a RATIO OF SUMS, not a mean of "
                       "per-game ratios); fall back to the all-rows prior-season rate "
                       "where she has none",
            "coverage_expected": "95% of level-2 rows carry own prior-season rate",
        },
        "shrinkage_weight_w": 0.60,
        "shrinkage_weight_status": "FROZEN from M38 s03, selected on 2024-2025. NOT re-tuned. "
                                   "Re-tuning it now would spend a holdout already consulted "
                                   "about a dozen times.",
    },

    # ---------------------------------------------------------------- the boundary
    # This is the defect D206 found, stated as a rule so the revision cannot repeat it.
    "data_the_revision_MAY_read": ["data/masters/master_player.parquet",
                                   "data/masters/master_team.parquet",
                                   "the prediction contract"],
    "data_the_revision_MAY_NOT_read": [
        "any market or odds artifact",
        "any statistic computed over the PRICED population (this is what D206 caught)",
        "the target game's own box score",
        "any row at or after the row's own forecast_cutoff",
    ],
    "boundary_rule": "A DIAGNOSTIC may read the priced frame, because that is where the "
                     "competitive question lives. AN ARM MAY NOT. Any diagnostic finding "
                     "destined to become a model change must first be re-derived using only "
                     "what the arm may read.",

    # ---------------------------------------------------------------- what must not move
    "must_not_change": [
        "the candidate universe and the prediction contract",
        "the fallback ladder's DEFINITION (levels 0/2/3/4 and their thresholds)",
        "alphas, EWMA half-lives and every calibration read from run_summary.json",
        "the other three targets: p_active, attempts_usage, player_scoring_distribution",
        "walk-forward discipline: season S reads only seasons < S plus strictly earlier "
        "games within S",
    ],
    "emit_to": "a NEW artifact directory under a new registration; the existing arm output "
               "is not overwritten, so the two can be compared row by row",

    # ---------------------------------------------------------------- the criterion
    "success_criterion": {
        "primary": "On the priced 2026 rows, the revision's mean competitive response must "
                   "land in [-0.26, -0.21]. The diagnostic measured -0.2230 against a "
                   "current -0.3108; the band admits implementation differences without "
                   "admitting a null result.",
        "direction_is_not_enough": "An improvement smaller than half the diagnostic's "
                                   "(response worse than -0.26) is a FAILED REPRODUCTION and "
                                   "must be reported as one, not described as a partial win.",
        "if_it_misses": "Report the miss and diagnose the DIFFERENCE between the arm and the "
                        "diagnostic. Do NOT adjust the arm until the numbers agree -- that "
                        "converts a fidelity check into a fitting exercise.",
        "no_variant_search": "Exactly one rule is implemented: the one specified above. If it "
                             "fails, that is the result.",
    },

    # ---------------------------------------------------------------- honesty clauses
    "expected_side_effects": [
        "Level-3 predictions will RISE for players with substantial prior seasons and FALL "
        "for those without. Unpriced rows are affected too and are not measured by the "
        "criterion above; a large shift there is worth reporting even though nothing scores it.",
        "The revision changes e_minutes_given_active only. Any movement in the other three "
        "targets indicates a leak between targets and is a defect, not a bonus.",
    ],
    "defects_are_recorded_not_repaired": True,
    "claims_authorised": "NONE. This closes part of a deficit; the model still loses to the "
                         "market on the priced population. S42 remains closed and no "
                         "wager-shaped claim follows from this revision.",
    "holdout_status": "2026 is SPENT for variant selection (REPORT.md). This revision is "
                      "confirmatory. The next clean evidence is prospective: 2026 games not "
                      "yet played, scored forward.",
}


def main():
    blob = repr(PREREG)
    sha = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"prereg": blob, "sha256": sha}, f, indent=1)
    print("=" * 94)
    print("M41 s03 -- PREREGISTRATION FROZEN")
    print("=" * 94)
    print("sha256: %s" % sha)
    print("wrote  : %s" % OUT)
    print("")
    print("Any later change to the revision is reported as a diff against this hash.")
    print("The criterion is fixed BEFORE the arm is built: the revision must land in")
    print("[-0.26, -0.21] on priced 2026 rows, and a smaller improvement is a FAILED")
    print("REPRODUCTION rather than a partial win.")
    print("")
    print("NOTHING HERE AUTHORISES A WAGER. The model still loses after this repair.")
    print("=" * 94)


if __name__ == "__main__":
    main()
