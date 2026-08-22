# -*- coding: utf-8 -*-
"""M23 -- the append-only shadow ledger.

DECISION-SYSTEM VALIDATION WITHOUT MONEY. Every paper decision is committed with a
pre-decision timestamp against a price that was capturable at that moment, with M21/M22
execution assumptions applied. Shadow results earn at most the M00 ladder status the
contract assigns them; they are never a licence to trade.

WHY THIS CANNOT BE BACKTESTED. The node's first acceptance criterion is that every shadow
decision is logged BEFORE its outcome window opens. That property cannot be manufactured
after the fact: a decision written once the game has started is not a shadow decision, it is
a retrospective annotation. So this ledger only ever appends decisions on games that have not
yet commenced, and it refuses -- loudly -- to do anything else.

WHAT IS ACTUALLY GUARANTEED HERE:

  1. `decision_ts_utc` is stamped before the record is built, and a record whose
     `commence_time` is not strictly in the future is REFUSED, not silently dropped.
  2. The quote acted on is carried with ITS OWN capture timestamp, so the decision can later
     be audited against what was actually visible at the time.
  3. The ledger is append-only. Nothing is ever edited. A revised decision is a NEW record
     carrying `supersedes`, and the superseded record stays exactly as written.
  4. M21 slippage and M22 capacity are applied to every fill, and the UNADJUSTED figure is
     retained beside the adjusted one -- never replaced by it.
  5. No order is placed. There is no venue client here, no credential read, and
     `order_placed` is a literal False on every record.

THE UNCOMFORTABLE PART, CARRIED ON EVERY RECORD. M22 already measured what these classes are
worth: arbitrage is "NOT A BUSINESS", line shopping is "A DISCOUNT, NOT INCOME", middles were
measured as negative expectation, and model-vs-market showed no edge on any slice tested. A
shadow decision is therefore NOT a claim that the opportunity is good. Each record carries its
class's M22 verdict so it can never be read as one.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "SHADOW_LEDGER.jsonl")

#: M21_EXECUTION_REALISM, measured against real resting orders on the exchange.
M21 = {
    "median_depth_at_best_usdc": 49.01,
    "p25_depth_usdc": 25.70,
    "p90_depth_usdc": 275.15,
    "slip_pct_fill_50_median": 0.0,
    "slip_pct_fill_50_p90": 1.351,
    "slip_pct_fill_100_median": 0.081,
    "slip_pct_fill_100_p90": 5.229,
    "insufficient_depth_rate_50": 290 / 2273,
    "insufficient_depth_rate_100": 417 / 2273,
    "book_side_limits": "ABSENT -- M21 marked sportsbook maximum-stake UNMEASURED rather "
                        "than estimating it. Any stake above exchange depth is unbounded "
                        "by evidence, not bounded generously.",
}

#: M22_CAPACITY verdicts, carried verbatim so a decision cannot be read as an endorsement.
M22_VERDICT = {
    "TRUE_CROSS_BOOK_ARBITRAGE": "NOT A BUSINESS. 0.20-0.83 USD per occurrence at median depth.",
    "PURE_MICROSTRUCTURE": "A DISCOUNT, NOT INCOME. It stops a fixed percentage of your own "
                           "money leaking; bet nothing and it is worth nothing.",
    "MIDDLES_AND_DISLOCATIONS": "D152 measured most as NEGATIVE EXPECTATION. Capacity for a "
                                "losing bet is moot.",
    "MODEL_VS_MARKET_VALUE": "D141/D150 measured NO EDGE on any slice tested.",
    "PROMOTIONAL_VALUE": "Largest per-unit value measured, but no REAL offer has ever been "
                         "entered; the offers on file are invented examples.",
    "STALE_LINE_DELAYED_REACTION": "M08 finds 52% of apparent stale windows sit at the "
                                   "capture resolution floor and carry no duration "
                                   "information. Unproven.",
}

#: S42 is CLOSED. No fitted scoring model may drive anything wager-shaped, so a decision
#: derived from one may not enter this ledger at all.
S42_FORBIDDEN_CLASSES = ("MODEL_VS_MARKET_VALUE",)

STAMP = "%Y-%m-%dT%H:%M:%S.%fZ"


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def _parse(ts):
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    try:
        v = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)


class OutcomeWindowOpen(Exception):
    """Raised when a decision would be logged at or after its outcome window opens."""


class S42Violation(Exception):
    """Raised when a decision derived from a fitted scoring model would be logged."""


def apply_execution(stake_unadjusted: float, class_id: str) -> dict:
    """Apply M21 slippage and M22 capacity, RETAINING the unadjusted figure.

    The adjusted number never replaces the unadjusted one; both are written. Where the
    requested stake exceeds measured exchange depth the record says so rather than
    inventing a fill.
    """
    depth = M21["median_depth_at_best_usdc"]
    if stake_unadjusted <= 50:
        slip = M21["slip_pct_fill_50_p90"]
        short_rate = M21["insufficient_depth_rate_50"]
    else:
        slip = M21["slip_pct_fill_100_p90"]
        short_rate = M21["insufficient_depth_rate_100"]
    fillable = min(stake_unadjusted, depth)
    return {
        "stake_unadjusted_usd": round(stake_unadjusted, 2),
        "stake_fillable_at_median_depth_usd": round(fillable, 2),
        "exceeds_median_depth": bool(stake_unadjusted > depth),
        "slippage_pct_applied_p90": slip,
        "slippage_basis": "M21 p90 price move from best, real resting orders",
        "insufficient_depth_rate": round(short_rate, 4),
        "capacity_verdict_M22": M22_VERDICT.get(class_id, "UNCLASSIFIED"),
        "book_side_limits": M21["book_side_limits"],
    }


def build_decision(opp: dict, snapshot_utc: str, captured_at: str,
                   stake_unadjusted: float = 50.0, supersedes: str | None = None,
                   now: dt.datetime | None = None) -> dict:
    """Build one shadow decision, refusing anything that breaks the node's guarantees."""
    now = now or utcnow()
    cid = opp.get("class_id", "")

    if cid in S42_FORBIDDEN_CLASSES:
        raise S42Violation(
            "S42 is CLOSED: a decision in class %r derives from a fitted scoring model and "
            "may not enter the shadow ledger." % cid)

    commence = _parse(opp.get("commence_time"))
    if commence is None:
        raise OutcomeWindowOpen(
            "opportunity %r has no commence_time; its outcome window cannot be shown to be "
            "closed, so it is refused" % opp.get("opp_id"))
    if commence <= now:
        raise OutcomeWindowOpen(
            "outcome window already open (commence %s <= decision %s); a decision logged now "
            "is a retrospective annotation, not a shadow decision"
            % (commence.isoformat(), now.isoformat()))

    rec = {
        "decision_ts_utc": now.strftime(STAMP),
        "opp_id": opp.get("opp_id"),
        "class_id": cid,
        "tier": opp.get("tier"),
        "matchup": opp.get("matchup"),
        "market": opp.get("market"),
        "commence_time": opp.get("commence_time"),
        "lead_seconds_to_outcome_window": round((commence - now).total_seconds(), 1),
        "headline": opp.get("headline"),
        # the quote acted on, with ITS OWN capture time -- criterion 1
        "quote_snapshot_utc": snapshot_utc,
        "quote_captured_at": captured_at,
        "quote_age_at_decision_s": round(
            (now - _parse(captured_at)).total_seconds(), 1) if _parse(captured_at) else None,
        "legs": opp.get("legs", []),
        "execution": apply_execution(stake_unadjusted, cid),
        "execution_mode": "SHADOW",
        "order_placed": False,
        "real_money_touched": False,
        "supersedes": supersedes,
        "not_an_endorsement": (
            "A logged decision is NOT a claim that this opportunity is profitable. See "
            "capacity_verdict_M22 on this record."),
    }
    rec["record_sha256"] = hashlib.sha256(
        json.dumps(rec, sort_keys=True).encode("utf-8")).hexdigest()
    return rec


def append(records, path: str = LEDGER) -> int:
    """Append records. Never rewrites, never truncates, never edits."""
    n = 0
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")
            n += 1
    return n


def read(path: str = LEDGER) -> list:
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
