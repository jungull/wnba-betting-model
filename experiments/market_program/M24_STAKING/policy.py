# -*- coding: utf-8 -*-
"""M24 -- the staking policy, implemented from the frozen SPEC.json.

DECISION-SYSTEM SPECIFICATION. Activating any policy with money is USER_REQUIRED and is not
this node's decision. Every figure this module produces is NOTIONAL.

THE ONE IDEA THAT MATTERS HERE. Kelly evaluated at a point estimate treats an uncertain edge
as certain, and systematically oversizes. This policy evaluates Kelly at the **95% lower
confidence bound** of the edge instead. When the interval includes zero -- which is the case
for every class this programme has measured -- the lower bound is at or below zero, the Kelly
fraction is at or below zero, and the stake is ZERO **by arithmetic**, not by anyone's
judgement about whether a bet feels wise.

That distinction is the whole point. A policy that stakes nothing because a human decided to
be careful can be argued out of. A policy that stakes nothing because the arithmetic on the
measured evidence returns zero cannot.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(HERE, "SPEC.json")

with open(SPEC_PATH, encoding="utf-8") as _f:
    SPEC = json.load(_f)

LADDER_RANK_REQUIRED = 7            # PRODUCTION_ELIGIBLE
S42_FORBIDDEN = ("MODEL_VS_MARKET_VALUE",)


class StakeRefused(Exception):
    """Raised when a stake is refused outright rather than merely sized to zero."""


def kelly_fraction(edge_lcb: float, odds_decimal: float) -> float:
    """Fractional Kelly evaluated at the LOWER BOUND of the edge.

    `edge_lcb` is the 95% lower confidence bound on expected return per unit staked.
    A non-positive lower bound returns 0.0 -- there is no negative staking here, because
    this policy never takes the other side automatically.
    """
    if edge_lcb <= SPEC["sizing"]["min_edge_after_uncertainty"]:
        return 0.0
    b = max(odds_decimal - 1.0, 1e-9)
    f = edge_lcb / b
    return max(0.0, min(f * SPEC["sizing"]["kelly_fraction_cap"], 1.0))


def ladder_rank(class_id: str) -> int:
    """Current M00 evidence-ladder rank for a class.

    There is no machine-readable source for this, so the gate FAILS CLOSED at 0 for every
    class. This function exists so that the day a ladder registry is built, exactly one
    place changes.
    """
    return 0


def size_decision(class_id: str, bankroll: float, edge_lcb: float,
                  odds_decimal: float, quote_age_s: float,
                  liquidity_usd: float, exposure_used_pct: dict | None = None) -> dict:
    """Size one decision. Returns the stake and, always, the rule that bound it."""
    exposure_used_pct = exposure_used_pct or {}
    caps = SPEC["exposure_caps_pct_of_bankroll"]
    liq = SPEC["liquidity_and_quote_rules"]
    reasons = []

    if class_id in S42_FORBIDDEN:
        raise StakeRefused(
            "S42 is CLOSED: class %r derives from a fitted scoring model and may not be "
            "staked in any mode." % class_id)

    rank = ladder_rank(class_id)
    gate_ok = rank >= LADDER_RANK_REQUIRED
    if not gate_ok:
        reasons.append("eligibility_gate: ladder rank %d < %d required (fails closed: no "
                       "machine-readable ladder status exists)" % (rank, LADDER_RANK_REQUIRED))

    if quote_age_s > liq["max_quote_age_seconds"]:
        reasons.append("quote_age %.0fs > %ds" % (quote_age_s, liq["max_quote_age_seconds"]))

    f = kelly_fraction(edge_lcb, odds_decimal)
    if f <= 0.0:
        reasons.append("kelly fraction 0 at the 95%% lower bound (edge_lcb=%.4f)" % edge_lcb)

    # cap ladder -- the BINDING cap is recorded, never just the final number
    raw = f * bankroll
    binding, capped = "kelly", raw
    for name, key in (("per_single_decision", "per_single_decision"),
                      ("per_game", "per_game"), ("per_market", "per_market"),
                      ("per_book", "per_book"), ("per_day", "per_day")):
        headroom = (caps[key] - exposure_used_pct.get(key, 0.0)) / 100.0 * bankroll
        if headroom < capped:
            capped, binding = max(0.0, headroom), name
    if liquidity_usd < capped:
        capped, binding = liquidity_usd, "measured_liquidity"

    # ANY recorded reason zeroes the stake. A reason that is printed but does not bind is
    # decoration -- the same defect this programme has shipped before in its checks.
    if reasons:
        stake, binding = 0.0, "refused"
    else:
        stake = capped

    return {
        "class_id": class_id,
        "ladder_rank": rank,
        "eligibility_gate_passed": gate_ok,
        "edge_lcb": edge_lcb,
        "kelly_fraction_at_lcb": round(f, 6),
        "stake_notional_usd": round(stake, 2),
        "binding_constraint": binding,
        "reasons_stake_is_zero": reasons,
        "real_money_authorised": False,
        # composed from BOTH fields so the operative term travels with every result.
        # SPEC.json is declared frozen before evaluation and is NOT edited to fix this.
        "authorisation_note": "%s: %s" % (SPEC["real_money_activation"]["status"],
                                          SPEC["real_money_activation"]["statement"]),
    }
