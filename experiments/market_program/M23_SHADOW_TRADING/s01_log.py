# -*- coding: utf-8 -*-
"""M23 s01 -- log shadow decisions against a LIVE board, before any outcome window opens.

Builds the opportunity board in memory rather than reading M28's `board.json`, for two
reasons: the file on disk may be hours stale, and writing M28's outputs from this node would
both dirty another node's artifacts and re-create the worktree-churn problem that previously
threatened the push gate.

Every opportunity whose game has already started is REFUSED, not skipped quietly -- the count
and the reason are printed, because a shadow ledger that silently drops the awkward half of
its input is worthless as evidence.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
M28 = os.path.abspath(os.path.join(HERE, "..", "M28_OPPORTUNITY_BOARD"))
sys.path.insert(0, HERE)
sys.path.insert(0, M28)

import shadow_ledger as sl  # noqa: E402

STAKE_UNADJUSTED = 50.0     # matches M21's measured fill scenario; not a recommendation


def main():
    import board as _board          # noqa: E402
    import feed as _feed            # noqa: E402

    print("=" * 94)
    print("M23 -- shadow decisions, logged before their outcome windows open")
    print("=" * 94)

    snap = _feed.load_latest()
    b = _board.build_board(snap)
    now = sl.utcnow()

    print("\nBOARD (built in memory, M28 artifacts untouched)")
    print("  snapshot        : %s" % snap.snapshot_utc)
    print("  captured at     : %s  (age %.0fs at decision time)"
          % (snap.captured_at.isoformat(), (now - snap.captured_at).total_seconds()))
    print("  games / books   : %d / %d" % (snap.n_games, snap.n_books))
    print("  opportunities   : %d" % len(b["opportunities"]))

    logged, refused = [], Counter()
    refusal_detail = []
    for o in b["opportunities"]:
        try:
            logged.append(sl.build_decision(
                o, snapshot_utc=b["snapshot_utc"], captured_at=b["captured_at"],
                stake_unadjusted=STAKE_UNADJUSTED, now=now))
        except sl.OutcomeWindowOpen as e:
            refused["outcome_window_open_or_unknown"] += 1
            refusal_detail.append((o.get("opp_id"), str(e)[:90]))
        except sl.S42Violation as e:
            refused["S42_fitted_model"] += 1
            refusal_detail.append((o.get("opp_id"), str(e)[:90]))

    print("\nDECISIONS")
    print("  logged  : %d" % len(logged))
    print("  refused : %d  %s" % (sum(refused.values()), dict(refused)))
    for oid, why in refusal_detail[:4]:
        print("     %-26s %s" % (oid, why))
    if len(refusal_detail) > 4:
        print("     ... and %d more" % (len(refusal_detail) - 4))

    if logged:
        byc = Counter(r["class_id"] for r in logged)
        print("\n  by class:")
        for c, n in byc.most_common():
            print("    %-30s %3d   M22: %s" % (c, n, sl.M22_VERDICT.get(c, "?")[:52]))
        leads = sorted(r["lead_seconds_to_outcome_window"] for r in logged)
        print("\n  lead time to outcome window: min %.0fs  median %.0fs  max %.0fs"
              % (leads[0], leads[len(leads) // 2], leads[-1]))
        ages = [r["quote_age_at_decision_s"] for r in logged if r["quote_age_at_decision_s"]]
        if ages:
            print("  quote age at decision      : min %.0fs  max %.0fs" % (min(ages), max(ages)))

    before = len(sl.read())
    n = sl.append(logged)
    after = len(sl.read())
    print("\nLEDGER (append-only)")
    print("  records before : %d" % before)
    print("  appended       : %d" % n)
    print("  records after  : %d" % after)
    assert after == before + n, "append-only violated: ledger did not grow by exactly n"

    print("\n" + "=" * 94)
    print("Every record carries order_placed=False, real_money_touched=False, the quote it")
    print("acted on with that quote's own capture timestamp, the unadjusted stake beside the")
    print("M21-adjusted one, and its class's M22 verdict -- so no record can be read as a")
    print("claim that the opportunity is profitable. M22 already measured that most are not.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8") as f:
        json.dump({"snapshot_utc": b["snapshot_utc"], "captured_at": b["captured_at"],
                   "opportunities": len(b["opportunities"]),
                   "logged": len(logged), "refused": dict(refused),
                   "by_class": dict(Counter(r["class_id"] for r in logged)),
                   "ledger_records_total": after,
                   "stake_unadjusted_usd": STAKE_UNADJUSTED}, f, indent=1)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
