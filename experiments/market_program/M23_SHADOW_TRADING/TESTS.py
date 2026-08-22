# -*- coding: utf-8 -*-
"""M23 tests -- the node's validation_commands entry point.

Each of the node's four acceptance criteria is tested with BOTH a conforming case and a
deliberate violation, because a check that cannot fail is worse than the noisy one it
replaced (D171). The live ledger on disk is audited too, so the guarantees are shown to hold
for records that actually exist rather than only for constructed ones.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import shadow_ledger as sl  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %-4s %s%s" % ("ok" if cond else "FAIL", name,
                           ("  -- " + detail) if detail and not cond else ""))


def _opp(commence, cid="PURE_MICROSTRUCTURE", oid="TEST-1"):
    return {"opp_id": oid, "class_id": cid, "tier": 2, "matchup": "A @ B",
            "market": "h2h", "commence_time": commence, "headline": "test",
            "legs": [{"book": "draftkings", "outcome": "A", "price": -110}]}


def test_pre_outcome():
    print("\nA. DECISIONS ARE LOGGED BEFORE THE OUTCOME WINDOW OPENS (criterion 1)")
    now = dt.datetime(2026, 8, 22, 12, 0, tzinfo=dt.timezone.utc)
    fut = (now + dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sl.build_decision(_opp(fut), "S1", now.strftime(sl.STAMP), now=now)
    check("a future outcome window is accepted", r["opp_id"] == "TEST-1")
    check("lead time to outcome window is recorded and positive",
          r["lead_seconds_to_outcome_window"] > 0)

    # violation: game already started
    past = (now - dt.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    raised = False
    try:
        sl.build_decision(_opp(past), "S1", now.strftime(sl.STAMP), now=now)
    except sl.OutcomeWindowOpen:
        raised = True
    check("an ALREADY-STARTED game is REFUSED", raised)

    # violation: exactly at commence -- boundary must be refused too
    raised = False
    try:
        sl.build_decision(_opp(now.strftime("%Y-%m-%dT%H:%M:%SZ")), "S1",
                          now.strftime(sl.STAMP), now=now)
    except sl.OutcomeWindowOpen:
        raised = True
    check("a game commencing EXACTLY now is refused (boundary closed)", raised)

    # violation: no commence_time at all
    raised = False
    try:
        sl.build_decision(_opp(""), "S1", now.strftime(sl.STAMP), now=now)
    except sl.OutcomeWindowOpen:
        raised = True
    check("an opportunity with NO commence_time is refused", raised)


def test_quote_provenance():
    print("\nB. THE QUOTE ACTED ON CARRIES ITS OWN CAPTURE TIMESTAMP (criterion 1)")
    now = dt.datetime(2026, 8, 22, 12, 0, tzinfo=dt.timezone.utc)
    cap = (now - dt.timedelta(seconds=300)).strftime(sl.STAMP)
    fut = (now + dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sl.build_decision(_opp(fut), "20260822T120000Z", cap, now=now)
    check("snapshot id retained", r["quote_snapshot_utc"] == "20260822T120000Z")
    check("quote capture time retained", r["quote_captured_at"] == cap)
    check("quote age at decision computed", abs(r["quote_age_at_decision_s"] - 300.0) < 1.0)
    check("decision timestamp is distinct from the quote's", r["decision_ts_utc"] != cap)


def test_execution_assumptions():
    print("\nC. M21 SLIPPAGE AND M22 CAPACITY APPLIED, UNADJUSTED RETAINED (criterion 3)")
    e = sl.apply_execution(50.0, "PURE_MICROSTRUCTURE")
    check("unadjusted stake retained", e["stake_unadjusted_usd"] == 50.0)
    check("slippage applied from M21", e["slippage_pct_applied_p90"] == sl.M21["slip_pct_fill_50_p90"])
    check("M22 verdict attached", "DISCOUNT" in e["capacity_verdict_M22"])
    check("book-side limits reported ABSENT, not estimated", "ABSENT" in e["book_side_limits"])

    big = sl.apply_execution(500.0, "MIDDLES_AND_DISLOCATIONS")
    check("a stake above median depth is flagged", big["exceeds_median_depth"] is True)
    check("fillable amount capped at measured depth",
          big["stake_fillable_at_median_depth_usd"] == sl.M21["median_depth_at_best_usdc"])
    check("unadjusted retained even when capped", big["stake_unadjusted_usd"] == 500.0)
    check("larger fills use the harsher M21 slippage bound",
          big["slippage_pct_applied_p90"] > e["slippage_pct_applied_p90"])
    check("negative-expectation class carries its verdict",
          "NEGATIVE EXPECTATION" in big["capacity_verdict_M22"])


def test_no_money_and_s42():
    print("\nD. NO ORDER IS PLACED, AND S42 IS ENFORCED (criterion 4)")
    now = dt.datetime(2026, 8, 22, 12, 0, tzinfo=dt.timezone.utc)
    fut = (now + dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sl.build_decision(_opp(fut), "S1", now.strftime(sl.STAMP), now=now)
    check("order_placed is literally False", r["order_placed"] is False)
    check("real_money_touched is literally False", r["real_money_touched"] is False)
    check("execution mode is SHADOW", r["execution_mode"] == "SHADOW")
    check("record disclaims endorsement", "NOT a claim" in r["not_an_endorsement"])

    raised = False
    try:
        sl.build_decision(_opp(fut, cid="MODEL_VS_MARKET_VALUE"), "S1",
                          now.strftime(sl.STAMP), now=now)
    except sl.S42Violation:
        raised = True
    check("a fitted-scoring-model class is REFUSED under S42", raised)


def test_append_only():
    print("\nE. THE LEDGER IS APPEND-ONLY; A REVISION IS A NEW RECORD (criterion 2)")
    recs = sl.read()
    check("ledger is readable", isinstance(recs, list))
    if not recs:
        check("ledger has records to audit (run s01_log.py first)", False)
        return

    # a revision must be a NEW record referencing the old, never an edit
    now = dt.datetime(2026, 8, 22, 12, 0, tzinfo=dt.timezone.utc)
    fut = (now + dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    orig = sl.build_decision(_opp(fut), "S1", now.strftime(sl.STAMP), now=now)
    rev = sl.build_decision(_opp(fut), "S1", now.strftime(sl.STAMP), now=now,
                            supersedes=orig["record_sha256"])
    check("a revision carries `supersedes`", rev["supersedes"] == orig["record_sha256"])
    check("the superseded record is untouched by the revision", orig["supersedes"] is None)
    check("revision and original are distinct records",
          rev["record_sha256"] != orig["record_sha256"])

    # audit every record actually on disk
    bad_hash = [r for r in recs
                if hashlib.sha256(json.dumps(
                    {k: v for k, v in r.items() if k != "record_sha256"},
                    sort_keys=True).encode("utf-8")).hexdigest() != r["record_sha256"]]
    check("every on-disk record's own hash verifies", not bad_hash,
          "%d bad" % len(bad_hash))

    late = []
    for r in recs:
        c = sl._parse(r["commence_time"])
        d = sl._parse(r["decision_ts_utc"])
        if c and d and d >= c:
            late.append(r["opp_id"])
    check("EVERY on-disk decision predates its outcome window", not late,
          "%d late" % len(late))
    check("no on-disk record claims an order was placed",
          all(r["order_placed"] is False for r in recs))
    check("no on-disk record is in an S42-forbidden class",
          all(r["class_id"] not in sl.S42_FORBIDDEN_CLASSES for r in recs))
    check("every on-disk record retains an unadjusted stake",
          all("stake_unadjusted_usd" in r["execution"] for r in recs))


def main():
    print("=" * 78)
    print("M23_SHADOW_TRADING -- tests")
    print("=" * 78)
    test_pre_outcome()
    test_quote_provenance()
    test_execution_assumptions()
    test_no_money_and_s42()
    test_append_only()
    print("\n" + "=" * 78)
    print("%d passed, %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  FAILED: %s" % f)
        sys.exit(1)
    print("=" * 78)


if __name__ == "__main__":
    main()
