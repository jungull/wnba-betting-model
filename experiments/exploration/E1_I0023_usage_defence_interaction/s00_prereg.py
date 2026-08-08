"""
s00 -- PREREGISTRATION.  RUNS BEFORE ANY STATISTIC IN THIS SCREEN IS COMPUTED.

Writes SPECS_PRESELECTED.md and _prereg.json, both carrying a SHA-256 over the specification list,
the strata, the bases, the primary cell and the inference settings.  Every later script re-hashes
the list it actually uses, asserts equality, and reports added/dropped counts.  That converts
"we preregistered" from a claim into a checkable fact (D085 ruling 4).
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import uid_base as ub  # noqa: E402

# ------------------------------------------------------------------ the reference (COMPLETE)
# EVERY available strictly-prior measurement of the target the frozen frames carry.  D090 showed the
# same forecast scoring +46.4% or +7.1% by reference choice alone, and D091 ranked reference
# incompleteness as the top explanation for this programme's nulls.  An incomplete base is the most
# likely way a structural correlation turns into a fake forecasting increment.
BASE_COMPLETE = [
    "refB_ppm",            # prior points per minute
    "refB_spm",            # prior true-shooting attempts per minute
    "refB_pps",            # prior points per shooting attempt
    "refB_mpg",            # prior minutes per game
    "refB_own_usg_pg",     # prior usage per game (ratio of sums)
]
# A DELIBERATELY INCOMPLETE base, preregistered as a CONTRAST so the reference-sensitivity of any
# result is measurable rather than asserted.  It is NEVER the headline.
BASE_SINGLE = ["refB_ppm"]

# Both arms of every contrast additionally carry the two MAIN EFFECTS.  The interaction is therefore
# tested strictly NESTED: with-interaction vs without-interaction, identical rows, identical base,
# identical main effects.  Without this the "interaction" could be main effects in disguise.
USAGE_MAIN = "O01_own_usg_pg"          # the player's own strictly-prior usage per game (D093's axis)

# ------------------------------------------------------------------ the interaction specifications
# Three opponent-defence terms: the D093 winner plus the two other preregistered opponent-allowance
# terms from the same family.  Nothing is added later.
DEFENCE_TERMS = [
    {"id": "A10_opp_defrtg", "why": "D093's decisive axis: Spearman +0.320, family-wise p 0.0035"},
    {"id": "A01_opp_efg_allowed", "why": "same D085 opponent-allowance family; D093 r +0.167"},
    {"id": "A02_opp_ts_allowed", "why": "same D085 opponent-allowance family; D093 r +0.198"},
]

# Negative controls: an interaction built on a PURE NOISE column, run through the identical path.
# One noise column per source frame, exactly as D093 did.
NEGATIVE_CONTROLS = [
    {"id": "NC1_noise_x_defrtg", "usage": "G01_noise", "defence": "A10_opp_defrtg",
     "why": "noise x the real defence term: does the machinery manufacture an increment?"},
    {"id": "NC2_usage_x_noise", "usage": USAGE_MAIN, "defence": "G01_noise_tvframe",
     "why": "the real usage term x noise: is the usage side alone enough to fake it?"},
]

RESPONSES = [
    {"id": "ppm", "rate_col": "y_ppm", "target_col": "y_ppm", "scale_by_minutes": False,
     "units": "points per minute"},
    {"id": "points", "rate_col": "y_ppm", "target_col": "y_pts", "scale_by_minutes": True,
     "units": "points per game"},
    {"id": "attempts", "rate_col": "y_spm", "target_col": "TSA", "scale_by_minutes": True,
     "units": "true-shooting attempts per game"},
]

STRATA = [
    {"id": "POOLED", "why": "all rows in the screen frame"},
    {"id": "DECISION", "why": "D081's decision-relevant stratum: n_prior >= 8 AND "
                              "prior5_minutes >= 24 -- the players anyone would actually bet on"},
]

# ------------------------------------------------------------------ the primary cell, fixed a priori
PRIMARY = {"defence": "A10_opp_defrtg", "response": "points", "stratum": "DECISION",
           "base": "B_COMPLETE", "fit": "walk_forward",
           "why": "D093's decisive axis, on the bettable target, on the stratum D081 identified as "
                  "decision-relevant, against the complete reference, with the coefficient fitted "
                  "strictly on earlier seasons. Declared BEFORE any statistic was computed."}
CO_PRIMARY = {"defence": "A10_opp_defrtg", "response": "ppm", "stratum": "DECISION",
              "base": "B_COMPLETE", "fit": "walk_forward",
              "why": "the mechanism check on the rate the interaction is actually fitted on"}

# ------------------------------------------------------------------ inference
N_DRAWS = 2000
CLUSTER_LEVEL = ["opp_team_id", "season"]
MIN_GAMES_PER_PLAYER = 8           # D093's per-player eligibility, reused for the reproduction
D093_HEADLINE_FLOOR = 20           # D093's preregistered realised-minutes floor
D093_PREREG_SHA = "8d7c8af4fce21746ce4e1ec3b58dc346a8ea696075b5149c05b9ad4817a96cbb"

# The three arithmetic ceilings this screen must be judged against (D079/D084/D089), quoted from the
# decision ledger BEFORE this screen's own ceiling was computed.
CEILING_BENCHMARKS = {"D079_shot_mix": 0.001127, "D084_conversion": 0.000129,
                      "D089_teammate_volume_prior_only": 0.002057}

PREREG = {
    "screen": "E1_I0023_usage_defence_interaction",
    "tests": "D093's structural usage x opponent-defence correlation, as a FORECASTING term",
    "partition": {"allowed_seasons": [2021, 2022, 2023, 2024],
                  "scored_seasons": [2022, 2023, 2024],
                  "note": "2021 appears ONLY as a training fold in the walk-forward, exactly as "
                          "D089 used it. No figure is reported on 2021 rows. 2025/2026 never read."},
    "base_complete": BASE_COMPLETE,
    "base_single_CONTRAST_ONLY": BASE_SINGLE,
    "usage_main_effect": USAGE_MAIN,
    "defence_terms": DEFENCE_TERMS,
    "negative_controls": NEGATIVE_CONTROLS,
    "responses": RESPONSES,
    "strata": STRATA,
    "primary_cell": PRIMARY,
    "co_primary_cell": CO_PRIMARY,
    "n_real_cells": len(DEFENCE_TERMS) * len(RESPONSES) * len(STRATA),
    "n_control_cells": len(NEGATIVE_CONTROLS) * len(RESPONSES) * len(STRATA),
    "n_draws": N_DRAWS,
    "seed": ub.SEED,
    "cluster_level": CLUSTER_LEVEL,
    "cluster_level_why": "the defence term is constant within opponent-team-season, so rows sharing "
                         "an opponent-season are not independent; the row-level null is "
                         "anticonservative and is reported only as the contrast",
    "contrast_form": "NESTED. Arm B = [1, base, usage, defence]; Arm A = [1, base, usage, defence, "
                     "usage x defence]. Identical rows, identical base, identical main effects. The "
                     "only difference is the interaction column.",
    "fit_windows": ["walk_forward (coefficients fitted on seasons < s, applied to season s) -- the "
                    "HEADLINE", "in_sample (whole partition) -- DIAGNOSTIC ONLY, reported as one"],
    "decision_rule": "The interaction is KEPT only if (a) the PRIMARY cell's walk-forward paired "
                     "dR2 is positive at cluster-level p < 0.05, (b) it survives the max-statistic "
                     "family-wise correction across the %d real cells, (c) both negative controls "
                     "fail, and (d) the arithmetic ceiling is not smaller than D084's 0.000129. "
                     "Any one of these failing is a KILL or at most a lead."
                     % (len(DEFENCE_TERMS) * len(RESPONSES) * len(STRATA)),
    "ceiling_benchmarks": CEILING_BENCHMARKS,
    "ceiling_form": "D084/D089 form: ceiling dR2 <= (points moved by 1 sd of the centred interaction "
                    "term / sd of the response)^2. The ORACLE variant (best rescaling chosen with "
                    "hindsight) is a DIAGNOSTIC and is excluded from every headline.",
    "d093_reproduction_targets": {
        "R04_opp_defrtg_spearman": 0.3200431235648813,
        "R06_own_usage_spearman": 0.2805225231952508,
        "family_wise_p": 0.0035,
        "NC1_p": 0.20439780109945027,
        "NC2_p": 0.9385307346326837,
        "prereg_sha256_of_D093": D093_PREREG_SHA,
        "floor": D093_HEADLINE_FLOOR,
        "min_games_per_player": MIN_GAMES_PER_PLAYER,
    },
}

PREREG_HASH = ub.sha({k: v for k, v in PREREG.items()})


def cells(include_controls=True):
    """The preregistered cell list, in a fixed order.  The ONLY source of cells in this screen."""
    out = []
    for d in DEFENCE_TERMS:
        for r in RESPONSES:
            for s in STRATA:
                out.append(dict(cell_id="%s|%s|%s" % (d["id"], r["id"], s["id"]),
                                kind="REAL", usage=USAGE_MAIN, defence=d["id"],
                                response=r["id"], stratum=s["id"]))
    if include_controls:
        for c in NEGATIVE_CONTROLS:
            for r in RESPONSES:
                for s in STRATA:
                    out.append(dict(cell_id="%s|%s|%s" % (c["id"], r["id"], s["id"]),
                                    kind="CONTROL", usage=c["usage"], defence=c["defence"],
                                    response=r["id"], stratum=s["id"]))
    return out


def check_prereg():
    """Re-hash the LIVE list and assert it equals what is on disk.  Report added/dropped."""
    with open(os.path.join(ub.OUT, "_prereg.json"), encoding="utf-8") as fh:
        on_disk = json.load(fh)
    h = on_disk.pop("prereg_sha256")
    live = ub.sha({k: v for k, v in PREREG.items() if k != "prereg_sha256"})
    assert h == live, "PREREG HASH MISMATCH: disk %s live %s" % (h, live)
    ids_disk = [c["cell_id"] for c in on_disk["cell_list"]]
    ids_live = [c["cell_id"] for c in cells()]
    added = [i for i in ids_live if i not in ids_disk]
    dropped = [i for i in ids_disk if i not in ids_live]
    return h, added, dropped


def main():
    os.makedirs(ub.OUT, exist_ok=True)
    body = dict(PREREG)
    body["cell_list"] = cells()
    body["prereg_sha256"] = PREREG_HASH
    with open(os.path.join(ub.OUT, "_prereg.json"), "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2)

    L = []
    L.append("# E1_I0023 -- PRESELECTED SPECIFICATIONS")
    L.append("")
    L.append("**SHA-256 of the preregistered block:** `%s`" % PREREG_HASH)
    L.append("")
    L.append("Written by `s00_prereg.py` **before any statistic in this screen was computed**. "
             "Every later script re-hashes the list it uses and asserts equality, and reports "
             "added/dropped counts against this file.")
    L.append("")
    L.append("## What is being tested")
    L.append("")
    L.append("D093 (E1_I0021) established a **structural** fact: per-player sensitivity to opponent "
             "defence rises with the player's own strictly-prior usage (Spearman +0.320, "
             "family-wise p 0.0035 under the cyclic-shift null, both negative controls null). "
             "This screen asks the **different** question of whether a pooled usage x defence "
             "**interaction term improves a forecast**.")
    L.append("")
    L.append("## Partition")
    L.append("")
    L.append("Seasons 2021-2024. **Every scored figure is on 2022-2024**; 2021 appears only as a "
             "training fold in the walk-forward, exactly as D089 used it. 2025 and 2026 are never "
             "read, joined, plotted or described.")
    L.append("")
    L.append("## The COMPLETE reference (the base in both arms)")
    L.append("")
    for c in BASE_COMPLETE:
        L.append("- `%s`" % c)
    L.append("")
    L.append("Plus the two **main effects** `%s` and the defence term, in BOTH arms. The contrast is "
             "strictly nested: the only difference between the arms is the interaction column." % USAGE_MAIN)
    L.append("")
    L.append("`B_SINGLE` = `%s` is preregistered as a **contrast only**, so the "
             "reference-sensitivity of any result is measurable. It is never the headline." % BASE_SINGLE)
    L.append("")
    L.append("## Defence terms (%d)" % len(DEFENCE_TERMS))
    L.append("")
    L.append("| term | why it is on the list |")
    L.append("|---|---|")
    for d in DEFENCE_TERMS:
        L.append("| `%s` | %s |" % (d["id"], d["why"]))
    L.append("")
    L.append("## Negative controls (%d)" % len(NEGATIVE_CONTROLS))
    L.append("")
    L.append("| id | usage side | defence side | what it tests |")
    L.append("|---|---|---|---|")
    for c in NEGATIVE_CONTROLS:
        L.append("| `%s` | `%s` | `%s` | %s |" % (c["id"], c["usage"], c["defence"], c["why"]))
    L.append("")
    L.append("## Responses (%d) and strata (%d)" % (len(RESPONSES), len(STRATA)))
    L.append("")
    for r in RESPONSES:
        L.append("- `%s` -- %s (rate fitted on `%s`, scaled by a prior-only minutes estimate: %s)"
                 % (r["id"], r["units"], r["rate_col"], r["scale_by_minutes"]))
    L.append("")
    for s in STRATA:
        L.append("- `%s` -- %s" % (s["id"], s["why"]))
    L.append("")
    L.append("## Cell count")
    L.append("")
    L.append("**%d real cells** (%d defence x %d responses x %d strata) and **%d control cells**. "
             "Family-wise correction is taken across the %d real cells."
             % (PREREG["n_real_cells"], len(DEFENCE_TERMS), len(RESPONSES), len(STRATA),
                PREREG["n_control_cells"], PREREG["n_real_cells"]))
    L.append("")
    L.append("## PRIMARY cell, fixed a priori")
    L.append("")
    L.append("`%s` x `%s` x `%s`, base `%s`, `%s`."
             % (PRIMARY["defence"], PRIMARY["response"], PRIMARY["stratum"], PRIMARY["base"],
                PRIMARY["fit"]))
    L.append("")
    L.append("%s" % PRIMARY["why"])
    L.append("")
    L.append("Co-primary (mechanism check): `%s` x `%s` x `%s`."
             % (CO_PRIMARY["defence"], CO_PRIMARY["response"], CO_PRIMARY["stratum"]))
    L.append("")
    L.append("## Inference")
    L.append("")
    L.append("- Contrast form: %s" % PREREG["contrast_form"])
    L.append("- Null: whole-cluster sign-flip at **%s** (%d draws, seed %d). %s"
             % (CLUSTER_LEVEL, N_DRAWS, ub.SEED, PREREG["cluster_level_why"]))
    L.append("- Fit windows: %s" % "; ".join(PREREG["fit_windows"]))
    L.append("- Decision rule: %s" % PREREG["decision_rule"])
    L.append("")
    L.append("## Arithmetic ceiling")
    L.append("")
    L.append("%s" % PREREG["ceiling_form"])
    L.append("")
    L.append("Benchmarks quoted from the decision ledger **before** this screen's ceiling was "
             "computed: D079 shot-mix `%.6f`, D084 conversion `%.6f`, D089 teammate-volume "
             "(prior-only) `%.6f` -- the largest the programme has measured."
             % (CEILING_BENCHMARKS["D079_shot_mix"], CEILING_BENCHMARKS["D084_conversion"],
                CEILING_BENCHMARKS["D089_teammate_volume_prior_only"]))
    L.append("")
    L.append("## Step-1 reproduction targets (D093, `structure_decisive.csv`)")
    L.append("")
    for k, v in PREREG["d093_reproduction_targets"].items():
        L.append("- `%s` = `%s`" % (k, v))
    L.append("")
    L.append("## Full cell list (%d)" % len(cells()))
    L.append("")
    L.append("| cell_id | kind | usage | defence | response | stratum |")
    L.append("|---|---|---|---|---|---|")
    for c in cells():
        L.append("| `%s` | %s | `%s` | `%s` | %s | %s |"
                 % (c["cell_id"], c["kind"], c["usage"], c["defence"], c["response"],
                    c["stratum"]))
    L.append("")
    with open(os.path.join(ub.OUT, "SPECS_PRESELECTED.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")

    print("PREREG SHA-256: %s" % PREREG_HASH)
    print("real cells=%d control cells=%d total=%d"
          % (PREREG["n_real_cells"], PREREG["n_control_cells"], len(cells())))
    print("PRIMARY = %s x %s x %s (base %s, %s)"
          % (PRIMARY["defence"], PRIMARY["response"], PRIMARY["stratum"], PRIMARY["base"],
             PRIMARY["fit"]))
    print("wrote SPECS_PRESELECTED.md and _prereg.json")


if __name__ == "__main__":
    main()
