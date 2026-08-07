#!/usr/bin/env python3
"""build_all.py -- materialise every design on the real pinned universe and receipt the parity.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

This is the authorised half of the node's work on real bytes: S35 authorises "construction of
feature matrices, K0_MATCHED constructions and the receipted diagnostics each card names, on the
pinned universe and the pinned row base", and forbids fitting. So this script builds 16 of the 17
element designs across all five folds, checks Layer-A parity on each, and writes
DESIGN_PARITY_RECEIPT.json. It performs NO fit and computes NO metric: `runner.build_designs`
never calls a fitter, and the blinding gate would refuse one if it tried.

SC09 is the seventeenth, and it is recorded as deferred rather than skipped quietly: its feature
is a hinge of the element's OWN FITTED K0 prediction, so it cannot be materialised without a fit.

Run:  python runner/build_all.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "arms"))

import runner  # noqa: E402
import runner_constants as K  # noqa: E402
import universe as U  # noqa: E402

OUT = K.NODE_DIR / "DESIGN_PARITY_RECEIPT.json"


def main() -> dict:
    mods = runner.load_modules()
    skip = {"SC09_FAV_GAP_COMPRESSION":
            sys.modules["sc09_fav_gap_compression"].BUILD_REQUIRES_K0_FIT}
    u = U.build_universe()
    rec = runner.build_designs(u, mods, skip=skip)
    rec["universe_receipt"] = u.receipt
    rec["code_state"] = runner.code_state()
    rec["obligation_text_check"] = runner.obligation_state()
    rec["seed_manifest"] = __import__("seed_manifest").build_manifest()
    rec["no_fit_performed"] = True
    rec["no_performance_number_computed"] = True
    rec["authority"] = ("S35 what_this_freeze_authorises.AUTHORISED item 2; "
                        "NOT_AUTHORISED_FITTING governs everything else")
    rec["manifest_digest"] = runner.manifest_digest(rec)
    OUT.write_text(json.dumps(rec, indent=1, default=str) + "\n", encoding="utf-8")
    return rec


if __name__ == "__main__":
    r = main()
    print("elements built :", len(r["elements"]))
    print("elements skipped:", list(r["skipped"]))
    for eid, e in r["elements"].items():
        f = e["per_fold"]["train_lt_2026"]
        print("  %-52s arm=%-2d k0=%-2d treat=%s" % (eid, len(f["arm_cols"]), len(f["k0_cols"]),
                                                     f["treatment_cols"]))
    print("receipt ->", OUT)
