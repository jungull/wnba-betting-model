# -*- coding: utf-8 -*-
"""M24 tests -- the staking policy's guarantees.

The central claim of this node is that it stakes nothing BY ARITHMETIC rather than by
caution. That claim is only worth anything if the arithmetic would produce a non-zero stake
when the evidence justified one -- so the suite proves BOTH directions: zero on the measured
evidence, and non-zero on a hypothetical class that clears every gate. A policy that returns
zero unconditionally is not conservative, it is broken, and these tests can tell the
difference.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import policy  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %-4s %s%s" % ("ok" if cond else "FAIL", name,
                           ("  -- " + detail) if detail and not cond else ""))


def test_spec():
    print("\nA. THE FROZEN SPEC")
    p = os.path.join(HERE, "SPEC.json")
    s = json.load(open(p, encoding="utf-8"))          # the node's validation_command
    check("SPEC.json parses", isinstance(s, dict))
    check("spec declares it was frozen before evaluation", s["frozen_before_evaluation"] is True)
    check("real-money activation is USER_REQUIRED (criterion 5)",
          s["real_money_activation"]["status"] == "USER_REQUIRED")
    caps = s["exposure_caps_pct_of_bankroll"]
    for k in ("per_game", "per_market", "per_book", "per_day"):
        check("exposure cap present: %s (criterion 2)" % k, k in caps)
    d = s["drawdown_and_stop_rules"]
    check("drawdown rules frozen before evaluation (criterion 3)",
          d["frozen_before_evaluation"] is True)
    for k in ("daily_loss_cap_pct", "trailing_drawdown_stop_pct", "consecutive_losing_days_stop"):
        check("stop rule present: %s" % k, k in d)
    check("uncovered hard risk controls are NAMED, not glossed",
          any("NOT COVERED" in v for v in s["hard_risk_controls_coverage"].values()))
    check("known gaps are recorded", len(s["known_gaps"]) >= 3)


def test_kelly_uncertainty():
    print("\nB. KELLY IS EVALUATED AT THE LOWER BOUND (criterion 1)")
    check("a negative lower bound stakes nothing", policy.kelly_fraction(-0.05, 1.91) == 0.0)
    check("a lower bound of exactly zero stakes nothing", policy.kelly_fraction(0.0, 1.91) == 0.0)
    f = policy.kelly_fraction(0.10, 1.91)
    check("a POSITIVE lower bound produces a positive fraction", f > 0.0,
          "got %.6f" % f)
    check("the quarter-Kelly cap is applied",
          abs(f - (0.10 / 0.91) * 0.25) < 1e-9, "got %.6f" % f)
    check("a huge edge is still capped at 1.0", policy.kelly_fraction(100.0, 1.91) <= 1.0)
    # the direction that matters: point estimate vs lower bound
    check("an edge whose interval includes zero sizes smaller than its point estimate would",
          policy.kelly_fraction(0.0, 1.91) < policy.kelly_fraction(0.05, 1.91))


def test_gate_fails_closed():
    print("\nC. THE ELIGIBILITY GATE FAILS CLOSED")
    check("no class holds the required ladder rank today",
          policy.ladder_rank("PURE_MICROSTRUCTURE") < policy.LADDER_RANK_REQUIRED)
    r = policy.size_decision("PURE_MICROSTRUCTURE", 1000.0, 0.10, 1.91, 10.0, 49.01)
    check("even a POSITIVE edge is refused while the gate fails closed",
          r["stake_notional_usd"] == 0.0)
    check("the refusal reason names the gate",
          any("eligibility_gate" in x for x in r["reasons_stake_is_zero"]))
    check("binding constraint recorded as refused", r["binding_constraint"] == "refused")


def test_would_size_if_justified():
    print("\nD. THE ARITHMETIC WOULD PRODUCE A STAKE IF THE EVIDENCE JUSTIFIED ONE")
    # Without this the "stakes nothing" claim is untestable -- a broken policy that always
    # returns zero would pass every other test in this file.
    real = policy.ladder_rank
    policy.ladder_rank = lambda cid: 7
    try:
        r = policy.size_decision("PURE_MICROSTRUCTURE", 1000.0, 0.10, 1.91, 10.0, 49.01)
        check("a fully-qualified decision receives a NON-ZERO stake",
              r["stake_notional_usd"] > 0.0, "got %.2f" % r["stake_notional_usd"])
        check("the binding constraint is recorded, not just the number",
              r["binding_constraint"] in ("kelly", "per_single_decision", "per_game",
                                          "per_market", "per_book", "per_day",
                                          "measured_liquidity"))
        check("an exposure cap can bind", policy.size_decision(
            "PURE_MICROSTRUCTURE", 1000.0, 0.90, 1.91, 10.0, 49.01
        )["binding_constraint"] in ("per_market", "per_single_decision", "per_game",
                                    "measured_liquidity"))
        # a stale quote must still zero it, gate or no gate
        stale = policy.size_decision("PURE_MICROSTRUCTURE", 1000.0, 0.10, 1.91, 400.0, 49.01)
        check("a STALE quote zeroes the stake even when everything else qualifies",
              stale["stake_notional_usd"] == 0.0)
        check("the stale-quote reason is recorded",
              any("quote_age" in x for x in stale["reasons_stake_is_zero"]))
        # never size above measured depth
        deep = policy.size_decision("PURE_MICROSTRUCTURE", 1000.0, 0.90, 1.91, 10.0, 5.0)
        check("stake never exceeds measured liquidity",
              deep["stake_notional_usd"] <= 5.0, "got %.2f" % deep["stake_notional_usd"])
    finally:
        policy.ladder_rank = real


def test_s42_and_authorisation():
    print("\nE. S42 AND AUTHORISATION")
    raised = False
    try:
        policy.size_decision("MODEL_VS_MARKET_VALUE", 1000.0, 0.5, 1.91, 10.0, 49.01)
    except policy.StakeRefused:
        raised = True
    check("a fitted-scoring-model class is REFUSED outright, not sized to zero", raised)
    r = policy.size_decision("PURE_MICROSTRUCTURE", 1000.0, 0.10, 1.91, 10.0, 49.01)
    check("no result ever claims real-money authorisation",
          r["real_money_authorised"] is False)
    check("every result carries the USER_REQUIRED note",
          "USER_REQUIRED" in r["authorisation_note"])


def main():
    print("=" * 78)
    print("M24_STAKING -- tests")
    print("=" * 78)
    test_spec()
    test_kelly_uncertainty()
    test_gate_fails_closed()
    test_would_size_if_justified()
    test_s42_and_authorisation()
    print("\n" + "=" * 78)
    print("%d passed, %d failed" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  FAILED: %s" % f)
        sys.exit(1)
    print("=" * 78)


if __name__ == "__main__":
    main()
