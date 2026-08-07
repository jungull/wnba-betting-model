#!/usr/bin/env python3
"""verify_carded_strata.py -- re-derive the carded kill-stratum censuses from the BUILT features.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

WHY THIS IS THE STRONGEST CHECK AVAILABLE AT S36. Every kill in this slate fires on a subset
defined by a feature this node builds. The frozen cards pin the SIZE of those subsets, measured at
S33R/S35 from the same pinned bytes. So re-deriving the censuses from THIS node's own feature code
tests the implementations against the preregistration end to end -- clock, sequencing, support
floors, row base and all -- WITHOUT computing a single performance number. A census is a count of
games, not a metric.

An uncheckable kill is a card defect (primary_gate_per_element.c). A kill whose stratum this
implementation cannot reproduce is an IMPLEMENTATION defect, and this script is how it surfaces
here rather than at S38.

Strata re-derived:
  SC01  max(n_H, n_A) <= 12          pinned 472 pooled; 75/76/74/81/92 per test season; 74 in 2021
  SC02  min(n_H, n_A) <= 5           pinned 249 pooled
  SC03  min(n_H, n_A) < 10           pinned 399 pooled
  SC12  |w_H - w_A| >= 2.0           pinned 652 pooled (43.7%); 97/118/102/141/107; 87 in 2021
  SC06  |F_H - F_A| >= 1, rest only  pinned 78 pooled / 77 pooled-test / 17 pre-2024 test
        (the C2 power-statement census; "rest components only, tz component added at sealed-run
         receipt time" -- so the rest-only variant is what is checkable here, by the card's own
         wording)

Run:  python runner/verify_carded_strata.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "arms"))

import numpy as np  # noqa: E402

import runner_constants as K  # noqa: E402
import universe as U  # noqa: E402
from features_common import prior_count  # noqa: E402
from obligations import C2_POWER_STATEMENT, stamp_program_alpha  # noqa: E402
from universe import attach_side  # noqa: E402

OUT = K.NODE_DIR / "CARDED_STRATA_RECEIPT.json"
TEST_SEASONS = (2022, 2023, 2024, 2025, 2026)


def _census(u, mask) -> dict:
    s = u.games["season"].to_numpy()
    return {"pooled": int(mask.sum()),
            "per_test_season": {int(y): int(mask[s == y].sum()) for y in TEST_SEASONS},
            "in_2021_training_only": int(mask[s == 2021].sum()),
            "pooled_test": int(mask[np.isin(s, TEST_SEASONS)].sum())}


def main() -> dict:
    u = U.build_universe()
    pc = prior_count(u.team_rows, same_season=True).rename(columns={"n_prior": "n"})
    g = attach_side(u.games, pc, "n", "n_H", "n_A", fill=0.0)
    nh, na = g["n_H"].to_numpy(float), g["n_A"].to_numpy(float)

    import sc06_sched_fatigue_diff as SC06
    import sc12_robust_input_winsor as SC12
    f = SC06.fatigue_terms(u)
    w = SC12.winsor_terms(u)

    checks = {}

    checks["SC01_max_n_le_12"] = {
        "predicate": "max(n_H, n_A) <= 12",
        "measured": _census(u, np.maximum(nh, na) <= 12),
        "carded": {"pooled": 472, "per_test_season": {2022: 75, 2023: 76, 2024: 74, 2025: 81,
                                                      2026: 92},
                   "in_2021_training_only": 74},
        "rejected_min_reading_count": int((np.minimum(nh, na) <= 12).sum()),
        "rejected_min_reading_carded": 516}

    checks["SC02_min_n_le_5"] = {
        "predicate": "min(n_H, n_A) <= 5",
        "measured": _census(u, np.minimum(nh, na) <= 5), "carded": {"pooled": 249}}

    checks["SC03_min_n_lt_10"] = {
        "predicate": "min(n_H, n_A) < 10",
        "measured": _census(u, np.minimum(nh, na) < 10), "carded": {"pooled": 399}}

    # SC12 -- the one card whose census does NOT close under its own normative construction.
    # Both readings are measured; neither is silently preferred. See sc12 module docstring (2).
    w_nofloor = SC12.winsor_terms(u, apply_support_floor=False)
    wd = np.abs(w["winsor_correction_diff"])
    wd_nf = np.abs(w_nofloor["winsor_correction_diff"])
    carded_12 = {"pooled": 652,
                 "per_test_season": {2022: 97, 2023: 118, 2024: 102, 2025: 141, 2026: 107},
                 "in_2021_training_only": 87}
    q = lambda a: {"median": float(np.median(a)), "p90": float(np.quantile(a, 0.90)),
                   "max": float(np.max(a))}
    checks["SC12_high_bite"] = {
        "predicate": "|w_H - w_A| >= 2.0",
        "measured": _census(u, wd_nf >= SC12.BITE_THRESHOLD),
        "carded": carded_12,
        "reading_that_reproduces_the_card": "RECURSIVE EWMA (adjust=False), support floor NOT "
                                            "applied",
        "measured_NORMATIVE_floor_applied": _census(u, wd >= SC12.BITE_THRESHOLD),
        "abs_w_diff_quantiles_measured_no_floor": q(wd_nf),
        "abs_w_diff_quantiles_measured_floor_applied": q(wd),
        "abs_w_diff_quantiles_carded": {"median": 1.704, "p90": 4.7058, "max": 13.0},
        "S36_FINDING": (
            "CARD-INTERNAL DISCREPANCY, DISCLOSED, NOT RECONCILED. The card's habitat census "
            "reproduces EXACTLY (all 4 counts + all 3 quantiles) only with the >= 3 prior-games "
            "support floor NOT applied, while the same card's parameters.fixed_pinned and "
            "fallback_cold_start make that floor normative. This node BUILDS the normative "
            "reading and reports both. MEASURED CONSEQUENCE: neither kill changes behaviour -- "
            "the bite habitat is non-empty in every fold under both readings (652 vs 649) and "
            "the integrity p90 is ~4.7x its 1.0 threshold under both (4.7058 vs 4.6795). Raised "
            "to S37; the cards are immutable, so any repair is a new erratum record."),
        "note": ("these quantiles gate the IMPLEMENTATION-INTEGRITY inertness kill (p90 < 1.0 "
                 "means the built transform is not the registered one). They describe a feature "
                 "distribution, not a performance metric.")}

    fd_rest = np.abs(f["fatigue_diff_rest_only"])
    fd_full = np.abs(f["fatigue_diff"])
    checks["SC06_abs_F_diff_ge_1"] = {
        "predicate": "|F_H - F_A| >= 1",
        "measured_rest_components_only": _census(u, fd_rest >= 1.0),
        "measured_including_tz": _census(u, fd_full >= 1.0),
        "carded_rest_only": {"pooled": 78, "pooled_test": 77,
                             "per_test_season": {2022: 8, 2023: 9, 2024: 19, 2025: 29, 2026: 12},
                             "pre_2024_test_clusters": 17},
        "card_wording": ("rest components only, tz component added at sealed-run receipt time"),
        "C2_POWER_STATEMENT": C2_POWER_STATEMENT,
        "why_the_power_statement_is_here": (
            "this census IS the C2 power figure's support. The obligation binds the statement to "
            "any verdict the era kill produces; carrying it alongside the census it rests on is "
            "the earliest point at which it can travel with the number.")}

    # verdicts
    for name, c in checks.items():
        m = c.get("measured") or c.get("measured_rest_components_only")
        carded = c.get("carded") or c.get("carded_rest_only")
        agree = {}
        for k2, v in carded.items():
            if k2 in m:
                got = m[k2]
                if isinstance(v, dict):
                    got = {int(a): b for a, b in got.items()}
                    v = {int(a): b for a, b in v.items()}
                agree[k2] = (got == v)
        c["agrees_with_card"] = agree
        c["all_agree"] = all(agree.values()) if agree else None

    # the EWMA-convention reproduction, re-run live rather than cited from a comment
    checks["SC12_high_bite"]["ewma_convention_reproduction"] = {
        "convention": "RECURSIVE EWMA, pandas adjust=False",
        "reproduces_all_seven_carded_numbers": bool(
            checks["SC12_high_bite"]["measured"]["pooled"] == carded_12["pooled"]
            and {int(a): b for a, b in
                 checks["SC12_high_bite"]["measured"]["per_test_season"].items()}
            == carded_12["per_test_season"]
            and checks["SC12_high_bite"]["measured"]["in_2021_training_only"]
            == carded_12["in_2021_training_only"]
            and abs(q(wd_nf)["median"] - 1.704) < 5e-4
            and abs(q(wd_nf)["p90"] - 4.7058) < 5e-5
            and abs(q(wd_nf)["max"] - 13.0) < 1e-9),
        "settles": ("the slate-wide EWMA convention, which no card states and which cycle-1 "
                    "flagged as an open interpretive pin")}

    rec = {"schema": "s36_carded_strata/1",
           "epistemic_status": ("IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no "
                                "comparative historical performance is revealed."),
           "what_this_is": ("game COUNTS of kill strata, re-derived from this node's own feature "
                            "code and compared to the frozen carded censuses. No metric, no "
                            "comparison, no fit."),
           "game_id_digest": u.game_id_digest,
           "strictly_prior_row_base": K.STRICTLY_PRIOR_ROW_BASE,
           "checks": checks,
           "all_strata_agree": all(bool(c["all_agree"]) for c in checks.values()
                                   if c["all_agree"] is not None)}
    stamp_program_alpha(rec)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8")
    return rec


if __name__ == "__main__":
    r = main()
    for name, c in r["checks"].items():
        m = c.get("measured") or c.get("measured_rest_components_only")
        print("%-24s pooled=%-5s per_test=%s  agree=%s"
              % (name, m["pooled"], m["per_test_season"], c["all_agree"]))
    print("ALL STRATA AGREE:", r["all_strata_agree"])
    print("receipt ->", OUT)
