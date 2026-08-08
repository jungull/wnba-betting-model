"""
c00 -- PREREGISTRATION.  RUNS BEFORE ANY STATISTIC IN THIS SCREEN IS COMPUTED.

A confirmation that chooses its criterion after seeing the number confirms nothing.  This file fixes
the specification ladder, the scored rows, the nulls, and -- above all -- the NUMERIC DECISION RULE
that maps the result onto THRESHOLD / REFIT ARTEFACT / UNRESOLVED, and hashes all of it.  Every later
script re-hashes the live block, asserts equality against what is on disk, and reports added/dropped
specification counts.
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import cbase as cb  # noqa: E402

# --------------------------------------------------------------------------- the ladder
LADDER = [
    {"id": "L1_pooled_defence_main",
     "fit": "POOLED (all decision-stratum training rows, all tiers)",
     "arm_B": "[1, COMPLETE reference (5), prior usage]",
     "arm_A": "arm_B + defence",
     "why": "one pooled defence coefficient. The floor of the ladder."},
    {"id": "L2_pooled_linear_interaction",
     "fit": "POOLED",
     "arm_B": "[1, COMPLETE reference (5), prior usage]",
     "arm_A": "arm_B + defence + (usage - u_bar) x (defence - d_bar)",
     "why": "D098's interaction, scored as a FAMILY against a no-defence base so it is on the same "
            "footing as L3 and L4. A linear interaction cannot represent a step in volume."},
    {"id": "L3_pooled_tier_dummy_x_defence",
     "fit": "POOLED",
     "arm_B": "[1, COMPLETE reference (5), prior usage, tier dummies D2, D3]",
     "arm_A": "arm_B + defence + D2 x (defence - d_bar) + D3 x (defence - d_bar)",
     "why": "THE DECISIVE TEST. One model, all rows, a STEP FUNCTION in volume for the defence "
            "slope. This is exactly what the THRESHOLD reading claims exists and what D098 named "
            "and did not run."},
    {"id": "L4_tier_restricted_refit",
     "fit": "TIER-RESTRICTED (top-tercile training rows only) -- D098's construction",
     "arm_B": "[1, COMPLETE reference (5), prior usage]",
     "arm_A": "arm_B + defence",
     "why": "D098's +0.023863. Reproduced here as the anchor and as the top of the ladder."},
]

DECOMPOSITION = [
    {"id": "R_nodef_refit_only",
     "what": "no-defence base fitted POOLED vs the SAME no-defence base fitted TIER-RESTRICTED, "
             "scored on the identical top-tercile rows. NO DEFENCE COLUMN IN EITHER ARM.",
     "why": "THE SINGLE CLEANEST MEASUREMENT OF THE ARTEFACT HYPOTHESIS. Whatever this recovers is "
            "the refit's own contribution, with the defence term absent by construction."},
    {"id": "TRANSPLANT_tier_frozen",
     "what": "freeze the tier-restricted model's NON-DEFENCE coefficients, then fit only a defence "
             "coefficient on the frozen model's training residual (centred defence, no free "
             "intercept).",
     "why": "does the defence term still earn its keep when it may not re-shuffle the others?"},
    {"id": "TRANSPLANT_pooled_frozen",
     "what": "same, but the frozen non-defence coefficients come from the POOLED fit.",
     "why": "does defence earn its keep with NO tier refit anywhere?"},
]

PLACEBOS = [
    {"id": "PLACEBO_TIERS", "what": "the identical L4 machinery on the MIDDLE and BOTTOM terciles",
     "why": "if a big gain appears there too, the gain is about refitting a subset."},
    {"id": "RANDOM_TIER_ROWSHUFFLE",
     "what": "tier labels permuted among masked rows WITHIN SEASON, %d draws, L4 statistic "
             "recomputed in full inside every draw" % cb.N_RANDOM_TIER,
     "why": "the null distribution for 'refitting any 1,687 rows'."},
    {"id": "RANDOM_TIER_PLAYERBLOCK",
     "what": "tiers assigned to WHOLE PLAYER-SEASON BLOCKS at random, size-matched, %d draws"
             % cb.N_RANDOM_TIER,
     "why": "a row shuffle breaks the player-block structure and could make the null too easy; this "
            "keeps whole player-seasons together."},
    {"id": "NEGATIVE_CONTROL_noise_defence",
     "what": "the whole ladder and the whole decomposition with G01_noise in place of the defence "
             "column",
     "why": "does the machinery manufacture an increment from nothing?"},
    {"id": "NOOP_PLACEBO_identity_swap",
     "what": "the within-date opponent-swap null code path executed with the UNPERMUTED defence "
             "column; must return the observed dR2 to 0.",
     "why": "plumbing check. A vacuous control has bitten this programme twice, so the swap null is "
            "ALSO required to demonstrate that it actually perturbs: the mean fraction of team-game "
            "units whose defence value changes under a real draw, and corr(original, swapped), are "
            "both reported and the fraction must exceed 0.5."},
]

NULLS = [
    {"id": "within_date_opponent_swap",
     "what": "permute the defence value among the team-games played on the SAME date; the whole "
             "walk-forward fit is redone inside every draw. %d draws, seed %d." % (cb.N_SWAP, cb.SEED),
     "status": "THE HEADLINE NULL. It is D098's, so the numbers are comparable, and it is the "
               "correct level for a between-opponent question: it preserves the date's marginal "
               "distribution of defence exactly and destroys only WHICH opponent was faced. It also "
               "holds the refit fixed while permuting the defence column, which is precisely the "
               "contrast this screen needs."},
    {"id": "whole_cluster_sign_flip_opponent_team_season",
     "what": "flip the sign of every row's paired squared-error difference inside a whole "
             "opponent-team-season. %d draws." % 2000,
     "status": "reported alongside, at the level the defence term varies at."},
    {"id": "row_level_sign_flip",
     "status": "CONTRAST ONLY, known anticonservative (D098 measured a median width inflation of "
               "1.611). Never a verdict."},
    {"id": "plain_within_player_shuffle",
     "status": "NOT USED. Anticonservative for autocorrelated regressors; the cyclic variant is the "
               "honest one and is not needed here because no per-player slope is estimated."},
]

# --------------------------------------------------------------------------- THE DECISION RULE
# G_refit  = L4 on ppm / DECISION / top tercile  (D098's +0.023863, reproduced as the anchor)
# G_step   = L3 on the SAME scored rows          (the decisive number)
# F        = G_step / G_refit                    (the recovery fraction)
# R_nodef  = the refit's own contribution, defence absent from both arms
# Q95_rand = 95th percentile of the L4 statistic over size-matched RANDOM tiers (worse of the two
#            random-tier variants)
DECISION_RULE = {
    "primary_statistic": "L3_pooled_tier_dummy_x_defence, response ppm, DECISION stratum, COMPLETE "
                         "reference, walk-forward, scored on the SAME 1,687 top-tercile rows D098 "
                         "scored, dR2 against the rung's own no-defence arm.",
    "co_primary": "the same on response points.",
    "anchors": cb.D098_ANCHORS,
    "THRESHOLD_if": [
        "F = G_step / G_refit >= 0.60",
        "G_step > 0 at within-date opponent-swap p < 0.05",
        "R_nodef < 0.50 * G_refit",
        "Q95_rand < 0.50 * G_refit",
        "the negative control does not improve anything (one-sided p >= 0.05)",
        "max(|dR2_T1|, dR2_T2) < 0.50 * G_refit",
    ],
    "REFIT_ARTEFACT_if_any_of": [
        "R_nodef >= G_refit  -- refitting with no defence column at all buys as much as the "
        "defence term is credited with",
        "Q95_rand >= 0.60 * G_refit  -- refitting a random equally sized subset reproduces it",
        "the random-tier one-sided p for the real top tercile is >= 0.05",
        "F <= 0.15 AND Q95_rand >= 0.30 * G_refit  -- the gain is not representable without the "
        "full tier refit, and refitting subsets is worth a material fraction of it",
        "the negative control reproduces >= 0.50 * G_refit",
    ],
    "UNRESOLVED_otherwise": "state exactly which criterion failed and what would settle it. In "
                            "particular F <= 0.15 with a clean random-tier null means the gain is "
                            "REAL BUT NOT A STEP IN THE DEFENCE SLOPE -- it requires tier-specific "
                            "baseline coefficients -- and that is reported as its own outcome, not "
                            "silently folded into either verdict.",
    "reproduction_gate": "|reproduced - published| < 1e-9 on BOTH of D098's anchors "
                         "(+0.023862917871899772 ppm and +0.018702810112816066 points). IF THIS "
                         "FAILS THE SCREEN STOPS AND REPORTS, because everything downstream is "
                         "meaningless otherwise.",
    "axis_resolution_rule": "the axis is DECLARED SEPARABLE only if the defence gain is present on "
                            "one axis's top tercile and absent (< 0.30 x) on another's, measured on "
                            "the DISAGREEMENT rows where the two axes' top terciles differ. If the "
                            "disagreement sets are too small or all axes carry it, the honest "
                            "answer is COLLINEAR AND NOT SEPARABLE, and that is reported as the "
                            "result rather than as a failure.",
}

PREREG = {
    "screen": "E1_I0025_threshold_vs_refit",
    "confirms": "the lead raised by E1_I0023 / D098 and RAISED-AND-NOT-ACCEPTED by the coordinator",
    "question": "Is the top-tercile opponent-defence gain a THRESHOLD (genuinely concentrated in "
                "high-volume players, non-linear in volume, representable by a pooled step) or a "
                "REFIT ARTEFACT (the top tercile simply has different baseline relationships, so "
                "re-estimating every coefficient there improves fit regardless of defence)?",
    "partition": {"allowed_seasons": [2021, 2022, 2023, 2024], "scored_seasons": cb.SCORED,
                  "note": "2021 is a TRAINING fold only. 2025/2026 never read, joined, plotted or "
                          "described. Enforced on VALUES by D098's assert_partition inside every "
                          "load."},
    "reference": {
        "complete": cb.BASE,
        "why": "reference incompleteness is this programme's top-ranked source of false results and "
               "the same cell moved 6.66x between a single-column and a complete reference IN THE "
               "SCREEN BEING CONFIRMED. Every available strictly-prior measurement of the target is "
               "in the base of BOTH arms of EVERY rung.",
        "incomplete_contrast_only": ["refB_ppm"]},
    "usage_axis": cb.UCOL,
    "defence_term": cb.DEFENCE,
    "responses": ["ppm (points per minute)", "points (rate x prior-only minutes estimate)"],
    "strata": ["DECISION (n_prior >= 8 AND prior5_minutes >= 24) -- the headline",
               "POOLED -- reported alongside"],
    "tier_construction": "tercile cut points on the player's strictly-prior usage per game, "
                         "computed on the FIRST TRAINING FOLD (2021) only and applied forward, so a "
                         "tier label could genuinely have been attached before tip-off. D098's "
                         "`s07.tiers_for`, called unchanged.",
    "scored_rows": "EVERY rung is scored on the IDENTICAL walk-forward top-tercile rows (D098's "
                   "1,687 on ppm/DECISION), with SST taken on those rows, which is D098's dR2 "
                   "definition. Fold gating is D098's (tier training >= 300, tier test >= 80).",
    "ladder": LADDER,
    "decomposition": DECOMPOSITION,
    "placebos": PLACEBOS,
    "nulls": NULLS,
    "decision_rule": DECISION_RULE,
    "axes_for_resolution": [cb.UCOL, "refB_mpg", "refB_ppm"],
    "n_swap_draws": cb.N_SWAP,
    "n_random_tier_draws": cb.N_RANDOM_TIER,
    "n_signflip_draws": 2000,
    "seed": cb.SEED,
    "champion": "never loaded, scored, retrained or modified. Fitting comparison models is "
                "authorised by D091 ruling 1.",
    "write_scope": "experiments\\exploration\\E1_I0025_threshold_vs_refit only. D098's directory, "
                   "the frozen frames and the ledgers are READ-ONLY; scripts run under python -B so "
                   "not even a __pycache__ entry is created outside this directory.",
}


def spec_ids():
    """The specification list the hash is taken over, in a fixed order."""
    out = [x["id"] for x in LADDER] + [x["id"] for x in DECOMPOSITION] + [x["id"] for x in PLACEBOS]
    out += ["AXIS_%s" % a for a in PREREG["axes_for_resolution"]]
    return out


PREREG["spec_list"] = spec_ids()
PREREG_HASH = cb.sha({k: v for k, v in PREREG.items()})


def check():
    """Re-hash the LIVE block and assert it equals what is on disk.  Report added/dropped."""
    with open(os.path.join(cb.OUT, "_prereg.json"), encoding="utf-8") as fh:
        on_disk = json.load(fh)
    h = on_disk.pop("prereg_sha256")
    live = cb.sha({k: v for k, v in PREREG.items()})
    assert h == live, "PREREG HASH MISMATCH: disk %s live %s" % (h, live)
    added = [i for i in spec_ids() if i not in on_disk["spec_list"]]
    dropped = [i for i in on_disk["spec_list"] if i not in spec_ids()]
    return h, added, dropped


def main():
    os.makedirs(cb.OUT, exist_ok=True)
    body = dict(PREREG)
    body["prereg_sha256"] = PREREG_HASH
    with open(os.path.join(cb.OUT, "_prereg.json"), "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2, default=str)

    L = []
    A = L.append
    A("# E1_I0025 -- PRESELECTED SPECIFICATIONS (THRESHOLD vs REFIT ARTEFACT)")
    A("")
    A("**SHA-256 of the preregistered block:** `%s`" % PREREG_HASH)
    A("")
    A("Written by `c00_prereg.py` **before any statistic in this screen was computed**. Every later "
      "script re-hashes the live block, asserts equality against this file, and reports "
      "added/dropped specification counts.")
    A("")
    A("## The question")
    A("")
    A(PREREG["question"])
    A("")
    A("D098's anchors, quoted here before anything was recomputed:")
    A("")
    A("| anchor | value |")
    A("|---|---|")
    for k, v in cb.D098_ANCHORS.items():
        A("| `%s` | %s |" % (k, v))
    A("")
    A("## Reproduction gate")
    A("")
    A(DECISION_RULE["reproduction_gate"])
    A("")
    A("## The specification ladder")
    A("")
    A("Every rung is scored on the **identical** walk-forward top-tercile rows, with SST taken on "
      "those rows -- D098's dR2 definition. Each rung's arm B is that rung's model with **every "
      "defence-carrying column removed**, so each rung's dR2 is the increment attributable to the "
      "defence family *at that rung*.")
    A("")
    A("| rung | fit | arm B | arm A | why it is on the list |")
    A("|---|---|---|---|---|")
    for x in LADDER:
        A("| `%s` | %s | `%s` | `%s` | %s |" % (x["id"], x["fit"], x["arm_B"], x["arm_A"], x["why"]))
    A("")
    A("## Separating the refit from the signal")
    A("")
    A("| id | what | why |")
    A("|---|---|---|")
    for x in DECOMPOSITION:
        A("| `%s` | %s | %s |" % (x["id"], x["what"], x["why"]))
    A("")
    A("## Placebos and controls")
    A("")
    A("| id | what | why |")
    A("|---|---|---|")
    for x in PLACEBOS:
        A("| `%s` | %s | %s |" % (x["id"], x["what"], x["why"]))
    A("")
    A("## Nulls")
    A("")
    for x in NULLS:
        A("- **`%s`** -- %s %s" % (x["id"], x.get("what", ""), x["status"]))
    A("")
    A("## THE DECISION RULE, FIXED IN ADVANCE")
    A("")
    A("Let **G_refit** = the L4 statistic on ppm / DECISION / top tercile (D098's +0.023863), "
      "**G_step** = the L3 statistic on the same scored rows, **F = G_step / G_refit**, "
      "**R_nodef** = the refit's own contribution with no defence column in either arm, and "
      "**Q95_rand** = the 95th percentile of the L4 statistic over size-matched random tiers "
      "(the worse of the two random-tier variants).")
    A("")
    A("**THRESHOLD** requires ALL of:")
    A("")
    for c in DECISION_RULE["THRESHOLD_if"]:
        A("- %s" % c)
    A("")
    A("**REFIT ARTEFACT** on ANY of:")
    A("")
    for c in DECISION_RULE["REFIT_ARTEFACT_if_any_of"]:
        A("- %s" % c)
    A("")
    A("**UNRESOLVED** otherwise. %s" % DECISION_RULE["UNRESOLVED_otherwise"])
    A("")
    A("## Axis resolution rule")
    A("")
    A(DECISION_RULE["axis_resolution_rule"])
    A("")
    A("## Full specification list (%d)" % len(spec_ids()))
    A("")
    for s in spec_ids():
        A("- `%s`" % s)
    A("")
    A("## Scope")
    A("")
    A("- %s" % PREREG["write_scope"])
    A("- %s" % PREREG["champion"])
    A("- Partition: %s" % PREREG["partition"]["note"])
    A("")
    with open(os.path.join(cb.OUT, "SPECS_PRESELECTED.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print("PREREG SHA-256: %s" % PREREG_HASH)
    print("specifications: %d  (ladder %d, decomposition %d, placebos %d, axes %d)"
          % (len(spec_ids()), len(LADDER), len(DECOMPOSITION), len(PLACEBOS),
             len(PREREG["axes_for_resolution"])))
    print("wrote SPECS_PRESELECTED.md and _prereg.json")


if __name__ == "__main__":
    main()
