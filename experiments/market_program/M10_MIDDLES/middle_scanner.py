"""M10_MIDDLES -- middle-opportunity detection with per-book push semantics.

Implements TAXONOMY.json class MIDDLES_AND_DISLOCATIONS (MARKET_PROGRAM_CONTRACT.md
section 1.2): "Line pairs where both wagers can win simultaneously (middles) or
related markets within/across books are mutually inconsistent beyond combined vig
(dislocations). Positive expectation is probabilistic, never locked. Not arbitrage."
This module implements the MIDDLES half of that class (two legs on the SAME market
family with DIFFERENT lines). Cross-market dislocations (F7, e.g. spread vs h2h
coherence) are named in the taxonomy but are a distinct hypothesis family this node
does not build -- see M10_REPORT_BODY.md.

DISTINCT FROM M09_TRUE_ARB_SCANNER (arb_scanner.py), in the ways the M00 taxonomy
requires and that this module enforces in code, not merely states in prose:

  1. Same-line requirement, dropped. A TRUE_CROSS_BOOK_ARBITRAGE candidate in
     arb_scanner.py needs the SAME line (or no line, e.g. h2h) at both legs and a
     settlement table that is locked positive in EVERY enumerated world. A middle is
     defined by DIFFERENT, non-mirror lines at the two legs that open a gap in which
     BOTH bets independently win. At ordinary vig this can never satisfy M09's
     locked-positive test, because the worlds outside the gap (one leg wins, the
     other loses) are not simultaneously hedgeable into positive territory -- see
     TESTS.py's test_middle_worlds_not_locked_positive_at_ordinary_vig, which feeds
     this module's own worlds through M09's own arb_scanner.find_arb_stake_ratio and
     checks the result. That test is stated honestly, not universally: in the
     degenerate case of an extremely mispriced book pair where literally every
     settlement world is profitable, the M00 taxonomy's own §1.1 wording would call
     that TRUE_CROSS_BOOK_ARBITRAGE regardless of whether the lines are equal --
     this module does not special-case that boundary away.
  2. Simultaneity is not a gate. TRUE_CROSS_BOOK_ARBITRAGE requires legs
     "simultaneously executable at witnessed prices" and arb_scanner.py withholds
     its verdict under SIMULTANEITY_UNVERIFIABLE. Nothing in the
     MIDDLES_AND_DISLOCATIONS definition requires simultaneous execution -- a middle
     is still a middle if leg A is bet now and leg B an hour later, as long as both
     lines were real at their own capture times. This module never gates its verdict
     on simultaneity. It still RECORDS the same amendment-4-compliant simultaneity
     window arb_scanner.py computes (imported, not reimplemented) on every flag,
     because acceptance criterion 3 requires both legs' capture timestamps and the
     inter-leg latency window on every flag -- here that is descriptive metadata,
     never a gate.
  3. The gating uncertainty is different. arb_scanner.py gates its reserved-word
     verdict on SIMULTANEITY uncertainty. This module gates its verdict on
     SETTLEMENT-RULE uncertainty: a middle's outcome depends on what happens when
     the result lands exactly on an integer line (a push) or when a prop's subject
     does not play (a void) -- and that answer is a per-venue rule, not a market
     universal. Where a participating venue's push/void rule is not verified, this
     module withholds the MIDDLE_CANDIDATE verdict (SETTLEMENT_UNSUPPORTED) rather
     than assume a default -- mirroring arb_scanner.py's own RuleError fail-closed
     discipline, applied to the dimension middles actually depend on.
  4. Reserved-term discipline. "Arbitrage"/"arb" is never used by this module to
     describe anything IT produces (TAXONOMY.json reserved_terms). References to
     M09's own names (arb_scanner, find_arb_stake_ratio, etc.) are citations of the
     other engine, not a use of the reserved word for this module's own output --
     TESTS.py checks this distinction precisely, not by blanket string absence.

Design commitments enforced in code, not in prose:
  * Gap geometry (does a middle exist at all) is PURE ARITHMETIC on the two legs'
    lines and sides -- always computable, no venue-rule dependency. Reported on
    every candidate pair regardless of settlement support.
  * Push/void semantics are a DATA TABLE, per venue (PUSH_VOID_RULES below), never
    hard-coded or assumed for a market. A venue whose rule is not on file is refused
    (RuleError via require_push_void_rule()), not defaulted.
  * EV is never asserted from an invented probability model. evaluate_middle_
    settlement() computes the exact, deterministic profit in EVERY enumerated
    settlement world for the ACTUAL prices and the ACTUAL per-venue push/void rule
    -- this IS the "push and half-point semantics per book's actual rules"
    requirement. A scalar expected value is produced ONLY if the caller supplies an
    explicit probability-per-world mapping (expected_value()). Absent that mapping,
    ev.status is EV_UNSUPPORTED_NO_PROBABILITY_MODEL and no numeric EV is produced
    -- a probability distribution over margins/totals is S-FUND territory (M00
    section 2, four-system separation) and out of this node's scope to invent.
  * Output is FLAG-ONLY, append-only (reuses arb_scanner.AppendOnlyFlagLog
    unchanged -- that class is fully generic over any flag dict and has no
    venue-table state to leak). No field is order-shaped; is_order and
    is_order_intent are always False.
  * Stdlib only. No network, no writes outside the caller's chosen path.
"""
from __future__ import annotations

import math
import os
import sys

_M09_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "M09_TRUE_ARB_SCANNER"))
if _M09_DIR not in sys.path:
    # Appended, never inserted at position 0: M09_TRUE_ARB_SCANNER/ also has
    # its own fixtures.py, and giving it priority over the importer's own
    # directory would silently shadow M10's fixtures.py for any caller that
    # imports this module before its own fixtures module (bit us once during
    # development -- kept as an explicit comment, not just a fixed bug).
    sys.path.append(_M09_DIR)
import arb_scanner as ARB  # noqa: E402  -- M09's engine, READ-ONLY reuse of its
    # stateless timestamp/simultaneity primitives (this module never writes to
    # M09_TRUE_ARB_SCANNER/ and never mutates arb_scanner's module-level tables
    # SETTLEMENT_RULES/FEE_MODEL/POSTED_LIMITS -- this module defines its own,
    # below, independently, so the two engines can never leak state into each
    # other even though they run in the same process during the demo/tests).

# Reused verbatim from M09 -- these are pure/stateless (no reliance on
# arb_scanner's mutable module-level venue tables).
parse_ts = ARB.parse_ts
fmt_ts = ARB.fmt_ts
PollLog = ARB.PollLog
simultaneity_window = ARB.simultaneity_window
canonical_json = ARB.canonical_json
sha256_hex = ARB.sha256_hex
american_to_decimal = ARB.american_to_decimal
AppendOnlyFlagLog = ARB.AppendOnlyFlagLog
UNBOUNDED = ARB.UNBOUNDED
UNMEASURED = ARB.UNMEASURED


class RuleError(Exception):
    pass


# ---------------------------------------------------------------------------
# Push/void handling and fee tables -- M10's OWN, independent of arb_scanner's.
# Same 3-value push/void vocabulary as M09 (void_return / counts_as_win /
# counts_as_loss) for lane-wide consistency, but a venue verified for M09's
# arb purposes is NOT automatically verified here, and vice versa: the two
# nodes ask different questions of the same venue's rules page (M09: does a
# push ever break a locked-positive arb pair; M10: how does a push change a
# middle's per-world profit). Only synthetic fixture venues are registered
# below -- see M10_REPORT_BODY.md for why zero real bookmakers have a
# verified push/void row, and coarse_tape_demo.py for the explicit, labeled
# fee-only placeholder used for the real-tape replay.
# ---------------------------------------------------------------------------
PUSH_VOID_RULES = {
    "book_alpha": {"push_handling": "void_return", "void_dnp_handling": "void_return"},
    "book_beta": {"push_handling": "void_return", "void_dnp_handling": "void_return"},
    "book_gamma_push_pays": {"push_handling": "counts_as_win",
                              "void_dnp_handling": "void_return"},
    "book_delta_dnp_pays": {"push_handling": "void_return",
                             "void_dnp_handling": "counts_as_win"},
}

FEE_MODEL = {
    "book_alpha": {"fee_type": "none"},
    "book_beta": {"fee_type": "none"},
    "book_gamma_push_pays": {"fee_type": "none"},
    "book_delta_dnp_pays": {"fee_type": "none"},
}


def require_push_void_rule(venue):
    if venue not in PUSH_VOID_RULES:
        raise RuleError(f"venue {venue!r} has no push/void settlement rule on "
                         "file; refusing to assume a default")
    return PUSH_VOID_RULES[venue]


def require_fee(venue):
    if venue not in FEE_MODEL:
        raise RuleError(f"venue {venue!r} has no fee-model row on file; "
                         "refusing to assume zero fee")
    return FEE_MODEL[venue]


def win_coefficient(venue, price_decimal) -> float:
    """Net profit per $1 staked if the leg wins, after the venue's fee."""
    fee = require_fee(venue)
    gross = price_decimal - 1.0
    if fee["fee_type"] == "none":
        return gross
    if fee["fee_type"] == "commission_on_net_win":
        return gross * (1.0 - fee["rate"])
    raise RuleError(f"unknown fee_type {fee['fee_type']!r} for venue {venue!r}")


def settle_multiplier(venue, raw_outcome, win_coef) -> float:
    """Map a leg's raw settlement type (WIN/LOSE/PUSH/VOID) to a stake
    multiplier at this venue, per the venue's own push/void rule row."""
    if raw_outcome == "WIN":
        return win_coef
    if raw_outcome == "LOSE":
        return -1.0
    rules = require_push_void_rule(venue)
    if raw_outcome == "PUSH":
        rule = rules["push_handling"]
    elif raw_outcome == "VOID":
        rule = rules["void_dnp_handling"]
    else:
        raise RuleError(f"unknown raw_outcome {raw_outcome!r}")
    if rule == "void_return":
        return 0.0
    if rule == "counts_as_win":
        return win_coef
    if rule == "counts_as_loss":
        return -1.0
    raise RuleError(f"unknown settlement rule {rule!r} for venue {venue!r}")


# ---------------------------------------------------------------------------
# Gap geometry -- pure arithmetic, no venue-rule dependency. Assumes the
# outcome variable (a basketball game's margin, or a total/prop's summed
# points) is integer-valued -- true by construction for any basketball score
# difference or sum, stated here as an explicit assumption, not hidden.
# ---------------------------------------------------------------------------

def is_integer_line(line) -> bool:
    v = float(line)
    return v == math.floor(v)


def gap_geometry(t_lo: float, t_hi: float):
    """t_lo: threshold leg_a's outcome variable must STRICTLY EXCEED for leg_a
    to win (spread: -leg_a's own posted line; totals/props Over: the Over
    line). t_hi: threshold leg_b's outcome variable must STRICTLY UNDERCUT
    for leg_b to win (spread: leg_b's own posted line for the opposite team;
    totals/props Under: the Under line).

    Returns None if no gap exists (t_lo >= t_hi: the lines are mirror images,
    or crossed the wrong way -- no outcome makes both bets win). Otherwise a
    dict describing the gap, including which boundary(ies) are pushable
    (integer-valued) and the outcome integers that land strictly inside the
    gap (both-win, no push)."""
    if t_lo >= t_hi:
        return None
    return {
        "t_lo": t_lo, "t_hi": t_hi,
        "gap_width": t_hi - t_lo,
        "a_push_point": t_lo if is_integer_line(t_lo) else None,
        "b_push_point": t_hi if is_integer_line(t_hi) else None,
        "gap_win_win_integers": [
            v for v in range(math.floor(t_lo), math.ceil(t_hi) + 1)
            if t_lo < v < t_hi
        ],
    }


def enumerate_gap_worlds(t_lo: float, t_hi: float):
    """Build the (raw_a, raw_b) world list for the gap between t_lo/t_hi. At
    most 5 worlds: BELOW_GAP, PUSH_AT_A (only if t_lo is an integer),
    IN_GAP, PUSH_AT_B (only if t_hi is an integer), ABOVE_GAP. Returns None
    if no gap (mirrors gap_geometry)."""
    g = gap_geometry(t_lo, t_hi)
    if g is None:
        return None
    worlds = [{"world_id": "BELOW_GAP", "raw_a": "LOSE", "raw_b": "WIN"}]
    if g["a_push_point"] is not None:
        worlds.append({"world_id": "PUSH_AT_A", "raw_a": "PUSH", "raw_b": "WIN"})
    worlds.append({"world_id": "IN_GAP", "raw_a": "WIN", "raw_b": "WIN"})
    if g["b_push_point"] is not None:
        worlds.append({"world_id": "PUSH_AT_B", "raw_a": "WIN", "raw_b": "PUSH"})
    worlds.append({"world_id": "ABOVE_GAP", "raw_a": "WIN", "raw_b": "LOSE"})
    return worlds


def enumerate_gap_worlds_with_dnp(t_lo: float, t_hi: float, *, dnp_risk: bool):
    """Same as enumerate_gap_worlds, with an added SUBJECT_DNP world (both
    legs VOID) when dnp_risk is True -- the real condition for a same-player
    prop O/U pair, where the player not playing voids both legs regardless of
    where the gap sits."""
    worlds = enumerate_gap_worlds(t_lo, t_hi)
    if worlds is None:
        return None
    if dnp_risk:
        worlds = worlds + [{"world_id": "SUBJECT_DNP", "raw_a": "VOID", "raw_b": "VOID"}]
    return worlds


def spread_thresholds(leg_a_own_line, leg_b_own_line):
    """leg_a_own_line: leg_a's own posted spread number for ITS side (e.g.
    -5.5 if favored by 5.5). leg_b_own_line: leg_b's own posted spread number
    for the OPPOSITE team of the same game. Caller is responsible for the two
    legs being on opposite teams of the same game/market."""
    return -float(leg_a_own_line), float(leg_b_own_line)


def over_under_thresholds(over_line, under_line):
    """Shared math for totals and same-player props: leg_a is an Over bet at
    over_line, leg_b is an Under bet at under_line (possibly a different
    book)."""
    return float(over_line), float(under_line)


def worlds_need_rule(venue: str, worlds, *, which: str) -> bool:
    """which: 'a' or 'b'. True if any world requires a PUSH or VOID
    settlement rule for this leg's venue."""
    key = f"raw_{which}"
    return any(w[key] in ("PUSH", "VOID") for w in worlds)


# ---------------------------------------------------------------------------
# Settlement evaluation -- deterministic per-world profit table, refusing to
# assume a rule (push/void OR fee) for a venue that has none on file.
# ---------------------------------------------------------------------------

def evaluate_middle_settlement(leg_a, leg_b, worlds, *, stake_a=1.0, stake_b=1.0):
    """leg_a/leg_b: {'venue', 'price_decimal'}. worlds: from
    enumerate_gap_worlds[_with_dnp].

    Returns a dict:
      status='SETTLEMENT_UNSUPPORTED', unsupported_venues=[...], world_ids=[...]
        -- at least one participating venue lacks a rule this world set needs
           (push/void row, or a fee row -- a fee row is required unconditionally
           because win_coefficient always needs one, even in a market with no
           push/void risk at all).
      status='FULLY_SPECIFIED', world_profit={world_id: profit}, world_detail=[...],
        win_coef_a, win_coef_b, stake_a, stake_b
        -- every world's exact profit, computed from the real prices and the
           real, verified per-venue rules. This is the "push and half-point
           semantics per book's actual rules" deliverable.

    Never raises for a normal missing-rule condition -- that is the expected,
    honestly reported outcome, not a caller error."""
    needs_a = worlds_need_rule(leg_a["venue"], worlds, which="a")
    needs_b = worlds_need_rule(leg_b["venue"], worlds, which="b")

    unsupported = []
    for venue, leg_key, needs_pv in ((leg_a["venue"], "a", needs_a),
                                      (leg_b["venue"], "b", needs_b)):
        if needs_pv:
            try:
                require_push_void_rule(venue)
            except RuleError as e:
                unsupported.append({"venue": venue, "leg": leg_key,
                                     "reason": "push_or_void_rule_unverified",
                                     "detail": str(e)})
        try:
            require_fee(venue)
        except RuleError as e:
            unsupported.append({"venue": venue, "leg": leg_key,
                                 "reason": "fee_row_unverified", "detail": str(e)})

    if unsupported:
        seen, deduped = set(), []
        for u in unsupported:
            key = (u["venue"], u["leg"], u["reason"])
            if key not in seen:
                seen.add(key)
                deduped.append(u)
        return {"status": "SETTLEMENT_UNSUPPORTED", "unsupported_venues": deduped,
                "world_ids": [w["world_id"] for w in worlds]}

    wa = win_coefficient(leg_a["venue"], leg_a["price_decimal"])
    wb = win_coefficient(leg_b["venue"], leg_b["price_decimal"])
    world_profit, world_detail = {}, []
    for w in worlds:
        ca = settle_multiplier(leg_a["venue"], w["raw_a"], wa)
        cb = settle_multiplier(leg_b["venue"], w["raw_b"], wb)
        p = ca * stake_a + cb * stake_b
        world_profit[w["world_id"]] = p
        world_detail.append({"world_id": w["world_id"], "mult_a": ca, "mult_b": cb,
                              "profit": p})
    return {"status": "FULLY_SPECIFIED", "world_profit": world_profit,
            "world_detail": world_detail, "win_coef_a": wa, "win_coef_b": wb,
            "stake_a": stake_a, "stake_b": stake_b}


def expected_value(profit_per_world: dict, probabilities: dict) -> float:
    """probabilities must cover exactly the world set in profit_per_world and
    sum to 1.0 (within 1e-9). Raises ValueError on a malformed probability
    object -- that is a caller programming error, not an honest 'unknown'
    state (the honest-unknown state is handled by never calling this
    function at all when no probability model exists -- see
    build_middle_flag)."""
    missing = set(profit_per_world) - set(probabilities)
    extra = set(probabilities) - set(profit_per_world)
    if missing or extra:
        raise ValueError(f"probabilities must cover exactly the world set; "
                          f"missing={missing} extra={extra}")
    total = sum(probabilities.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"probabilities must sum to 1.0, got {total}")
    return sum(profit_per_world[w] * probabilities[w] for w in profit_per_world)


# ---------------------------------------------------------------------------
# End-to-end flag builder.
# ---------------------------------------------------------------------------

FLAG_SCHEMA = "market_program/M10/middle_flag/1"

EPISTEMIC_STATUS = (
    "SCANNING INFRASTRUCTURE. Middles are probabilistic, not risk-free: "
    "detection uses the M00 taxonomy's definition and the EV arithmetic must "
    "model push/no-push semantics per book rule set, never a generic "
    "template.")

ALLOWED_VERDICTS = {"MIDDLE_CANDIDATE", "NOT_MIDDLE", "SETTLEMENT_UNSUPPORTED"}


def build_middle_flag(*, game_id, market_kind, leg_a_quote, leg_b_quote,
                       t_lo, t_hi, dnp_risk=False, probabilities=None,
                       stake_a=1.0, stake_b=1.0,
                       clock_skew=UNMEASURED, vendor_latency_bounds=None):
    """leg_*_quote: {'venue', 'price_decimal', 'line', 't_seen', 't_prev',
                      'poll_interval'} -- all from the actual poll log, never
                      a nominal cadence.
    t_lo/t_hi: from spread_thresholds()/over_under_thresholds().
    probabilities: optional {world_id: P}. If omitted, ev.status is
      EV_UNSUPPORTED_NO_PROBABILITY_MODEL and ev.value is None -- see module
      docstring point 3 / EV design commitment.

    verdict is one of:
      MIDDLE_CANDIDATE       -- a gap exists AND every venue's needed rules
                                 (push/void, fee) are on file; world_profit
                                 is the exact per-world payout table.
      NOT_MIDDLE              -- no gap exists (lines are mirror images or
                                 crossed the wrong way); a geometric, not a
                                 rule-availability, negative.
      SETTLEMENT_UNSUPPORTED  -- a gap exists but a participating venue's
                                 push/void or fee rule is not verified; the
                                 reserved verdict is withheld, mirroring
                                 arb_scanner.py's SIMULTANEITY_UNVERIFIABLE
                                 discipline applied to a different
                                 uncertainty.

    A flag NEVER contains an order-shaped field (see TESTS.py schema check).
    """
    vendor_latency_bounds = vendor_latency_bounds or {}
    worlds = enumerate_gap_worlds_with_dnp(t_lo, t_hi, dnp_risk=dnp_risk)
    gap = gap_geometry(t_lo, t_hi)

    sim = simultaneity_window(
        {"venue": leg_a_quote["venue"], "t_prev": leg_a_quote.get("t_prev"),
         "t_seen": leg_a_quote["t_seen"], "poll_interval": leg_a_quote.get("poll_interval")},
        {"venue": leg_b_quote["venue"], "t_prev": leg_b_quote.get("t_prev"),
         "t_seen": leg_b_quote["t_seen"], "poll_interval": leg_b_quote.get("poll_interval")},
        clock_skew=clock_skew, vendor_latency_bounds=vendor_latency_bounds)
    inter_leg_latency_s = abs(leg_a_quote["t_seen"] - leg_b_quote["t_seen"])

    if worlds is None:
        verdict = "NOT_MIDDLE"
        settlement = {"status": "NOT_APPLICABLE_NO_GAP"}
        ev = {"status": "NOT_APPLICABLE_NO_GAP", "value": None}
    else:
        settlement = evaluate_middle_settlement(
            {"venue": leg_a_quote["venue"], "price_decimal": leg_a_quote["price_decimal"]},
            {"venue": leg_b_quote["venue"], "price_decimal": leg_b_quote["price_decimal"]},
            worlds, stake_a=stake_a, stake_b=stake_b)
        if settlement["status"] == "SETTLEMENT_UNSUPPORTED":
            verdict = "SETTLEMENT_UNSUPPORTED"
            ev = {"status": "NOT_APPLICABLE_SETTLEMENT_UNSUPPORTED", "value": None}
        else:
            verdict = "MIDDLE_CANDIDATE"
            if probabilities is not None:
                ev = {"status": "EV_COMPUTED",
                      "value": expected_value(settlement["world_profit"], probabilities),
                      "probabilities": probabilities}
            else:
                ev = {"status": "EV_UNSUPPORTED_NO_PROBABILITY_MODEL", "value": None,
                      "reason": (
                          "no sourced probability distribution over the outcome "
                          "variable (margin/total) was supplied; assigning one is "
                          "S-FUND territory (MARKET_PROGRAM_CONTRACT.md section 2, "
                          "four-system separation) and out of this scanning node's "
                          "scope -- fabricating one would be exactly the 'generic "
                          "template' the acceptance criteria forbid")}

    flag = {
        "schema": FLAG_SCHEMA,
        "flag_id": None,
        "game_id": game_id,
        "market_kind": market_kind,
        "leg_a": {"venue": leg_a_quote["venue"],
                  "capture_ts": fmt_ts(leg_a_quote["t_seen"]),
                  "price_decimal": leg_a_quote["price_decimal"],
                  "line": leg_a_quote.get("line")},
        "leg_b": {"venue": leg_b_quote["venue"],
                  "capture_ts": fmt_ts(leg_b_quote["t_seen"]),
                  "price_decimal": leg_b_quote["price_decimal"],
                  "line": leg_b_quote.get("line")},
        "inter_leg_latency_s": inter_leg_latency_s,
        "simultaneity": sim,
        "gap": gap,
        "worlds": worlds,
        "settlement": settlement,
        "ev": ev,
        "verdict": verdict,
        "epistemic_status": EPISTEMIC_STATUS,
        "is_order": False,
        "is_order_intent": False,
    }
    flag["flag_hash"] = sha256_hex(canonical_json(
        {k: v for k, v in flag.items() if k not in ("flag_id", "flag_hash")}))
    return flag
