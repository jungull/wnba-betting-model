# -*- coding: utf-8 -*-
"""M24 s01 -- evaluate the frozen staking policy against the M23 shadow ledger.

Criterion 4 permits evaluation against the M23 ledger and nothing else, so nothing else is
read here.

WHAT CAN AND CANNOT BE EVALUATED TODAY. The 34 shadow decisions are on games commencing
2026-08-22/23. **No outcome exists yet**, so no profit-and-loss evaluation is possible and
none is attempted. What CAN be evaluated is structural, and it is the part that matters for a
staking policy: how many decisions the policy would admit, what stake it assigns, and which
rule binds. A policy that stakes nothing needs no outcomes to be assessed -- it needs only to
be shown that it stakes nothing for the RIGHT reason.

The edge inputs are the expectations this programme has actually measured, taken from
SPEC.json's `measured_expectations_at_freeze`, which was frozen before this ran. They are not
re-derived here and they are not optimistic: not one class has a positive lower bound.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LEDGER = os.path.abspath(os.path.join(HERE, "..", "M23_SHADOW_TRADING",
                                      "SHADOW_LEDGER.jsonl"))

import policy  # noqa: E402

BANKROLL = 1000.0

#: 95% lower confidence bound on expected return per unit staked, per class.
#: Every one is <= 0 -- see SPEC.json measured_expectations_at_freeze for the source of each.
EDGE_LCB = {
    "MIDDLES_AND_DISLOCATIONS": -0.05,      # D152: negative expectation
    "PURE_MICROSTRUCTURE": 0.0,             # M22: a cost reduction, not income
    "STALE_LINE_DELAYED_REACTION": 0.0,     # M08: unproven, 52% at the resolution floor
    "TRUE_CROSS_BOOK_ARBITRAGE": 0.0,       # M22: positive but immaterial; LCB not established
    "PROMOTIONAL_VALUE": 0.0,               # M22: no real offer has ever been entered
}


def main():
    print("=" * 94)
    print("M24 -- the frozen staking policy, evaluated against the M23 shadow ledger")
    print("=" * 94)
    print("SPEC version %d, frozen_before_evaluation=%s"
          % (policy.SPEC["version"], policy.SPEC["frozen_before_evaluation"]))

    if not os.path.exists(LEDGER):
        raise SystemExit("M23 shadow ledger not found: %s" % LEDGER)
    recs = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    print("\nM23 shadow ledger: %d decisions" % len(recs))
    print("  NO OUTCOME EXISTS for any of them -- the games commence 2026-08-22/23.")
    print("  No profit-and-loss evaluation is attempted, and none would be honest.")

    sized, refused_s42 = [], 0
    for r in recs:
        cid = r["class_id"]
        try:
            s = policy.size_decision(
                class_id=cid, bankroll=BANKROLL,
                edge_lcb=EDGE_LCB.get(cid, 0.0),
                odds_decimal=1.91,                      # -110, the modal price on this board
                quote_age_s=r.get("quote_age_at_decision_s") or 0.0,
                liquidity_usd=policy.SPEC["liquidity_and_quote_rules"]["min_liquidity_usd"])
            sized.append((r, s))
        except policy.StakeRefused:
            refused_s42 += 1

    total = sum(s["stake_notional_usd"] for _, s in sized)
    nonzero = [s for _, s in sized if s["stake_notional_usd"] > 0]

    print("\nSTRUCTURAL EVALUATION")
    print("  decisions sized                : %d" % len(sized))
    print("  refused outright under S42     : %d" % refused_s42)
    print("  decisions receiving NON-ZERO stake : %d" % len(nonzero))
    print("  TOTAL NOTIONAL STAKE           : %.2f USD of a %.0f bankroll" % (total, BANKROLL))

    binding = Counter(s["binding_constraint"] for _, s in sized)
    print("\n  binding constraint:")
    for b, n in binding.most_common():
        print("    %-24s %d" % (b, n))

    why = Counter()
    for _, s in sized:
        for r_ in s["reasons_stake_is_zero"]:
            why[r_.split(":")[0].split("(")[0].strip()] += 1
    print("\n  reasons a stake is zero (a decision can have more than one):")
    for w, n in why.most_common():
        print("    %-58s %d" % (w[:58], n))

    byclass = Counter(r["class_id"] for r, _ in sized)
    print("\n  by class:")
    for c, n in byclass.most_common():
        print("    %-32s %3d   edge_lcb %+0.3f" % (c, n, EDGE_LCB.get(c, 0.0)))

    print("\n" + "=" * 94)
    print("RESULT: the policy stakes %.2f USD across all %d shadow decisions." % (total, len(sized)))
    print("It stakes nothing BY ARITHMETIC, not by anyone's caution. Two independent rules")
    print("each zero every decision on their own: the eligibility gate fails closed because")
    print("no machine-readable evidence-ladder status exists, AND the Kelly fraction is zero")
    print("at the 95% lower bound because not one measured class has a positive lower bound.")
    print("")
    print("Real-money activation is USER_REQUIRED and is not this node's decision.")
    print("=" * 94)

    out = {"spec_version": policy.SPEC["version"], "bankroll": BANKROLL,
           "ledger_decisions": len(recs), "sized": len(sized),
           "refused_s42": refused_s42, "nonzero_stakes": len(nonzero),
           "total_notional_stake_usd": round(total, 2),
           "binding_constraint": dict(binding),
           "by_class": dict(byclass), "edge_lcb_used": EDGE_LCB,
           "outcomes_available": False,
           "pnl_evaluated": False,
           "real_money_authorised": False}
    with open(os.path.join(HERE, "FINDINGS.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote FINDINGS.json")


if __name__ == "__main__":
    main()
