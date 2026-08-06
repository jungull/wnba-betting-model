"""M09_TRUE_ARB_SCANNER -- true cross-book arbitrage scanner: flags only.

Implements TAXONOMY.json class TRUE_CROSS_BOOK_ARBITRAGE (MARKET_PROGRAM_CONTRACT.md
section 1.1) exactly as defined there: "A set of wagers across two or more venues,
simultaneously executable at witnessed prices, whose combined return is locked
positive in every settlement outcome after applying each venue's own settlement
rules (push handling, void/DNP rules, dead-heat, listed-player rules)."

Design commitments enforced in code, not in prose:

  * The word "arbitrage" is reserved (contract section 1, TAXONOMY.json
    reserved_terms). This module's public API only ever calls something
    TRUE_CROSS_BOOK_ARBITRAGE / "true arb" when it has survived (a) the
    settlement-rule-compatibility check in EVERY enumerated settlement world,
    (b) the simultaneity check under amendment-4 bounds, and (c) fees and
    posted limits inside the same inequality that produced the verdict.
    Anything that fails any one of those is a candidate, never an arb.
  * Settlement rules (push handling, void/DNP handling, dead-heat) are a
    DATA TABLE (SETTLEMENT_RULES below), never hard-coded per market. A
    market whose rule is not on file is refused (UNKNOWN_RULE), not assumed.
  * Fees and posted limits are inside the SAME inequality that decides
    true-arb status, not a downstream filter: a paper-positive combination
    that only clears because a fee or a limit was ignored is not flagged.
  * Simultaneity is derived from POLL-LOG timestamps (first-seen, witnessed)
    widened by vendor-latency and clock-skew bounds per contract section 6 /
    the B.1 calculus adopted from EVENT_LINKAGE_AND_METHODOLOGY.md. A
    CLOCK_UNBOUNDED run or an UNBOUNDED vendor cannot certify simultaneity;
    the scanner refuses to flag TRUE_ARB in that condition and says why.
  * Output is FLAG-ONLY. A flag object has no field that could be replayed
    directly as an order (no side/qty/order-type/venue-account tuple ready
    for submission) and the flag log is append-only (new rows only, never
    an update -- mirrors the market-snapshot-table discipline of contract
    section 6.3).
  * Stdlib only. No network, no writes outside the caller's chosen path.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import re

# ---------------------------------------------------------------------------
# Timestamps and poll logs (self-contained; mirrors the B.1/B.2 calculus of
# M05_EVENT_MARKET_LINKAGE/linkage.py by design, reimplemented here rather
# than imported so M09 has no runtime dependency on another node's write
# scope -- both modules cite the same frozen baseline,
# EVENT_LINKAGE_AND_METHODOLOGY.md sections A/B, adopted by
# MARKET_PROGRAM_CONTRACT.md section 0.4).
# ---------------------------------------------------------------------------

_EPOCH = _dt.datetime(1970, 1, 1)
_TS_RE = re.compile(r"^(\d{4})-?(\d{2})-?(\d{2})[T ]?(\d{2}):?(\d{2}):?(\d{2})")

UNBOUNDED = "UNBOUNDED"     # vendor latency without a sourced bound
UNMEASURED = "UNMEASURED"   # clock skew without a per-run measurement


def parse_ts(s) -> int:
    if isinstance(s, int):
        return s
    m = _TS_RE.match(str(s).strip())
    if not m:
        raise ValueError(f"unparseable timestamp: {s!r}")
    y, mo, d, h, mi, se = (int(g) for g in m.groups())
    return int((_dt.datetime(y, mo, d, h, mi, se) - _EPOCH).total_seconds())


def fmt_ts(t: int) -> str:
    return (_EPOCH + _dt.timedelta(seconds=int(t))).strftime("%Y-%m-%dT%H:%M:%SZ")


class PollLog:
    """Sorted unique successful-poll instants for ONE venue's odds stream.
    Intervals derive from the ACTUAL recorded polls, never a nominal cadence
    (contract section 4.1)."""

    def __init__(self, instants):
        self.polls = sorted(set(int(parse_ts(t)) for t in instants))
        if not self.polls:
            raise ValueError("empty poll log")
        self.log_hash = sha256_hex(",".join(str(p) for p in self.polls))

    def prev(self, t: int):
        lo, hi, ans = 0, len(self.polls) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.polls[mid] < t:
                ans = self.polls[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        return ans

    def gap_at(self, t: int):
        p = self.prev(t)
        return None if p is None else t - p


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def widen_interval(lo, up, l_max, eps):
    """B.1: t_true in [t_prev - L_max - eps, t_seen + eps].
    l_max None (UNBOUNDED vendor) -> lower bound unbounded (None).
    eps None (UNMEASURED clock skew) -> refuse to widen (caller must exclude
    the row as CLOCK_UNBOUNDED rather than fabricate a bound)."""
    if eps is None:
        raise ValueError("cannot widen with UNMEASURED clock skew; the "
                          "quote is CLOCK_UNBOUNDED and must be excluded")
    w_up = up + eps
    w_lo = None if l_max is None else lo - l_max - eps
    return w_lo, w_up


def simultaneity_window(leg_a_capture, leg_b_capture, *, clock_skew,
                         vendor_latency_bounds):
    """Determine whether two witnessed quotes could have been simultaneously
    live (amendment-4 field set attached; contract section 6.1/6.2).

    leg_*_capture: dict with 'venue', 't_prev' (poll strictly before first-
    seen, or None), 't_seen' (the witnessed first-seen instant), and
    'poll_interval' (gap on that leg's own poll stream at t_seen, or None
    if t_seen is the stream's first poll).

    Returns a dict with the full amendment-4 field set plus a verdict:
      'SIMULTANEOUS_WITNESSED'   -- widened intervals overlap; both legs
                                     could have been struck together
      'NOT_SIMULTANEOUS'         -- widened intervals provably do not overlap
      'SIMULTANEITY_UNVERIFIABLE'-- CLOCK_UNBOUNDED or vendor UNBOUNDED;
                                     no bounded claim is possible either way
    A TRUE_ARB flag may only ever be built on 'SIMULTANEOUS_WITNESSED'.
    """
    skew = clock_skew
    eps = None if skew == UNMEASURED else int(skew["epsilon_max_s"])

    def _lmax(venue):
        b = vendor_latency_bounds.get(venue, UNBOUNDED)
        return None if b == UNBOUNDED else int(b["seconds"])

    la_lmax = _lmax(leg_a_capture["venue"])
    lb_lmax = _lmax(leg_b_capture["venue"])
    field_common = {
        "poll_interval_event": None,   # not applicable: no event stream here
        "poll_interval_quote_a": leg_a_capture.get("poll_interval"),
        "poll_interval_quote_b": leg_b_capture.get("poll_interval"),
        "vendor_latency_bound": {
            leg_a_capture["venue"]: vendor_latency_bounds.get(
                leg_a_capture["venue"], UNBOUNDED),
            leg_b_capture["venue"]: vendor_latency_bounds.get(
                leg_b_capture["venue"], UNBOUNDED),
        },
        "clock_skew_bound": skew,
        "censor_type": "interval",
        "tier": "T0",
        "leg_a_capture_ts": fmt_ts(leg_a_capture["t_seen"]),
        "leg_b_capture_ts": fmt_ts(leg_b_capture["t_seen"]),
    }

    if eps is None or la_lmax is None or lb_lmax is None:
        return {
            **field_common,
            "t_lower": None, "t_upper": None,
            "verdict": "SIMULTANEITY_UNVERIFIABLE",
            "reason": "CLOCK_UNBOUNDED" if eps is None else "VENDOR_UNBOUNDED",
        }

    a_lo, a_up = widen_interval(
        leg_a_capture.get("t_prev") if leg_a_capture.get("t_prev") is not None
        else leg_a_capture["t_seen"], leg_a_capture["t_seen"], la_lmax, eps)
    b_lo, b_up = widen_interval(
        leg_b_capture.get("t_prev") if leg_b_capture.get("t_prev") is not None
        else leg_b_capture["t_seen"], leg_b_capture["t_seen"], lb_lmax, eps)

    overlap_lo = max(a_lo, b_lo)
    overlap_up = min(a_up, b_up)
    inter_leg_latency_s = abs(leg_a_capture["t_seen"] - leg_b_capture["t_seen"])
    verdict = "SIMULTANEOUS_WITNESSED" if overlap_lo <= overlap_up \
        else "NOT_SIMULTANEOUS"
    return {
        **field_common,
        "t_lower": overlap_lo, "t_upper": overlap_up,
        "inter_leg_latency_s": inter_leg_latency_s,
        "verdict": verdict,
        "reason": None,
    }


# ---------------------------------------------------------------------------
# Settlement rules -- data-driven table, per venue. Never hard-coded per
# market. Reserved vocabulary: WIN / LOSE / PUSH / VOID are the only raw
# per-leg settlement types the engine understands; a market builder maps its
# own outcome space onto these before calling evaluate_true_arb.
# ---------------------------------------------------------------------------

# push_handling: how a push (line hit exactly) settles at this venue.
#   "void_return"     -- stake returned, net 0 (the standard, default rule)
#   "counts_as_win"   -- venue pays the bet out as a win despite the push
#                        (rare "push insurance" style promos)
#   "counts_as_loss"  -- venue takes the stake despite the push (not seen in
#                        practice at licensed books; carried for completeness
#                        so the table can express whatever a venue actually
#                        does, never assumed)
# void_dnp_handling: same three-value vocabulary, for listed-player /
#   did-not-play voids on prop markets.
# dead_heat: this scanner's market builders (h2h, spreads, totals, simple
#   O/U props) never produce a dead-heat world -- dead-heat applies to
#   placing/outright markets, which are out of this node's scope. The field
#   is carried so the table is honest about what it does NOT model rather
#   than silently omitting it.
SETTLEMENT_RULES = {
    "book_alpha": {"push_handling": "void_return",
                   "void_dnp_handling": "void_return",
                   "dead_heat": "NOT_MODELED_OUT_OF_SCOPE"},
    "book_beta": {"push_handling": "void_return",
                  "void_dnp_handling": "void_return",
                  "dead_heat": "NOT_MODELED_OUT_OF_SCOPE"},
    "book_gamma_push_pays": {"push_handling": "counts_as_win",
                              "void_dnp_handling": "void_return",
                              "dead_heat": "NOT_MODELED_OUT_OF_SCOPE"},
    "book_delta_dnp_pays": {"push_handling": "void_return",
                             "void_dnp_handling": "counts_as_win",
                             "dead_heat": "NOT_MODELED_OUT_OF_SCOPE"},
}

# Fee model, per venue. fee_type in {"none", "commission_on_net_win"}.
FEE_MODEL = {
    "book_alpha": {"fee_type": "none"},
    "book_beta": {"fee_type": "none"},
    "book_gamma_push_pays": {"fee_type": "none"},
    "book_delta_dnp_pays": {"fee_type": "none"},
    "exchange_epsilon": {"fee_type": "commission_on_net_win", "rate": 0.02},
}

# Posted limits, per venue per market_id. A venue/market absent from this
# table has NO posted limit on file -- treated as CAPACITY_UNKNOWN, never as
# unlimited (a missing row is not evidence of "no limit").
POSTED_LIMITS = {}


class RuleError(Exception):
    pass


def _require_rule(venue):
    if venue not in SETTLEMENT_RULES:
        raise RuleError(f"venue {venue!r} has no settlement-rule row on "
                         "file; refusing to assume a default")
    return SETTLEMENT_RULES[venue]


def _require_fee(venue):
    if venue not in FEE_MODEL:
        raise RuleError(f"venue {venue!r} has no fee-model row on file; "
                         "refusing to assume zero fee")
    return FEE_MODEL[venue]


def american_to_decimal(price) -> float:
    p = float(price)
    if p > 0:
        return 1.0 + p / 100.0
    if p < 0:
        return 1.0 + 100.0 / abs(p)
    raise ValueError("American odds of exactly 0 are not a valid price")


def win_coefficient(venue, price_decimal) -> float:
    """Net profit per $1 staked if the leg wins, after the venue's fee."""
    fee = _require_fee(venue)
    gross = price_decimal - 1.0
    if fee["fee_type"] == "none":
        return gross
    if fee["fee_type"] == "commission_on_net_win":
        return gross * (1.0 - fee["rate"])
    raise RuleError(f"unknown fee_type {fee['fee_type']!r} for venue {venue!r}")


def settle_multiplier(venue, raw_outcome, win_coef) -> float:
    """Map a leg's raw settlement type (WIN/LOSE/PUSH/VOID) to a stake
    multiplier at this venue, per the venue's own settlement-rule row.
    This is the settlement-rule-compatibility check applied to ONE leg."""
    if raw_outcome == "WIN":
        return win_coef
    if raw_outcome == "LOSE":
        return -1.0
    rules = _require_rule(venue)
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
# The 2-leg maximin solver: does a stake ratio exist making EVERY world's
# combined profit strictly positive, within posted limits?  Worlds are
# expressed as (c0, c1) coefficient pairs: profit(world) = c0*s0 + c1*s1.
# Since the system is homogeneous in stake, feasibility is decided on the
# ratio t = s1/s0 (t in [0, +inf]); each world's positivity constraint is a
# half-line on t, intersected exactly (closed form, no iterative LP).
# ---------------------------------------------------------------------------

INF = float("inf")


def _t_bounds(c0, c1):
    """Range of t=s1/s0 (t in [0,+inf]) for which c0 + c1*t > 0.
    Returns (lo, hi) with lo<hi, or None if infeasible for all t>=0."""
    if c1 > 0:
        if c0 >= 0:
            return (0.0, INF)
        return (-c0 / c1, INF)
    if c1 < 0:
        if c0 > 0:
            return (0.0, -c0 / c1)
        return None
    # c1 == 0
    return (0.0, INF) if c0 > 0 else None


def find_arb_stake_ratio(world_coefs):
    """world_coefs: list of (c0, c1) pairs, one per settlement world.
    Returns witness t=s1/s0 (float, possibly with s0 pinned to 1) if a
    strictly-positive-in-every-world allocation exists, else None with the
    world index that killed feasibility (for diagnostics)."""
    lo, hi = 0.0, INF
    for idx, (c0, c1) in enumerate(world_coefs):
        b = _t_bounds(c0, c1)
        if b is None:
            return None, idx
        lo = max(lo, b[0])
        hi = min(hi, b[1])
        if lo >= hi:
            return None, idx
    if hi == INF:
        t_mid = lo + 1.0
    elif lo == 0.0:
        t_mid = hi / 2.0
    else:
        t_mid = (lo + hi) / 2.0
    return t_mid, None


def evaluate_2leg_true_arb(leg_a, leg_b, worlds, *, limit_a=None, limit_b=None):
    """leg_a/leg_b: {'venue', 'price_decimal'}.
    worlds: list of {'world_id', 'raw_a': WIN|LOSE|PUSH|VOID,
                      'raw_b': WIN|LOSE|PUSH|VOID}.
    limit_a/limit_b: posted per-leg stake caps, or None if CAPACITY_UNKNOWN
    (a missing limit blocks a capacity claim but not the existence check --
    the taxonomy's "locked positive" is about the inequality, capacity is a
    separate, honestly-labeled quantity per contract section 8.5).

    Returns a result dict; never raises for a normal negative outcome (only
    for a data problem -- unknown venue/rule)."""
    wa = win_coefficient(leg_a["venue"], leg_a["price_decimal"])
    wb = win_coefficient(leg_b["venue"], leg_b["price_decimal"])
    coefs = []
    world_detail = []
    for w in worlds:
        ca = settle_multiplier(leg_a["venue"], w["raw_a"], wa)
        cb = settle_multiplier(leg_b["venue"], w["raw_b"], wb)
        coefs.append((ca, cb))
        world_detail.append({"world_id": w["world_id"], "mult_a": ca,
                             "mult_b": cb})

    t, killer_idx = find_arb_stake_ratio(coefs)
    if t is None:
        return {
            "verdict": "NOT_TRUE_ARB",
            "reason": "SETTLEMENT_WORLD_NOT_LOCKED_POSITIVE",
            "failing_world": worlds[killer_idx]["world_id"],
            "worlds": world_detail,
        }

    # Witness allocation s0=1, s1=t; scale to fit posted limits if known.
    s0, s1 = 1.0, t
    capacity_status = "CAPACITY_UNKNOWN"
    scale = 1.0
    if limit_a is not None and limit_b is not None:
        if limit_a <= 0 or limit_b <= 0:
            return {
                "verdict": "NOT_TRUE_ARB",
                "reason": "CAPACITY_ZERO",
                "worlds": world_detail,
            }
        k_candidates = [limit_a / s0]
        if s1 > 0:
            k_candidates.append(limit_b / s1)
        scale = min(k_candidates)
        capacity_status = "BOUNDED"
    stake_a, stake_b = s0 * scale, s1 * scale

    profits = {}
    min_profit = INF
    for w, (ca, cb) in zip(worlds, coefs):
        p = ca * stake_a + cb * stake_b
        profits[w["world_id"]] = p
        min_profit = min(min_profit, p)
    if not (min_profit > 0):
        # Belt-and-suspenders: the closed-form witness must independently
        # verify positive in every world before anything is flagged.
        return {
            "verdict": "NOT_TRUE_ARB",
            "reason": "WITNESS_VERIFICATION_FAILED",
            "worlds": world_detail,
        }

    return {
        "verdict": "TRUE_ARB_CANDIDATE",
        "stake_ratio_b_per_a": t,
        "stake_plan": {"leg_a": stake_a, "leg_b": stake_b},
        "capacity_status": capacity_status,
        "guaranteed_profit_per_world": profits,
        "min_guaranteed_profit": min_profit,
        "worlds": world_detail,
    }


# ---------------------------------------------------------------------------
# Market-scoped world builders. Each returns the (raw_a, raw_b) world list
# for evaluate_2leg_true_arb given the two legs' declared sides. These are
# the only places market semantics enter the engine.
# ---------------------------------------------------------------------------

def worlds_h2h_2way():
    """Two-outcome moneyline, no ties (WNBA team games), no push/void risk
    on this market type: leg_a wins on SIDE_A, leg_b wins on SIDE_B."""
    return [
        {"world_id": "SIDE_A_WINS", "raw_a": "WIN", "raw_b": "LOSE"},
        {"world_id": "SIDE_B_WINS", "raw_a": "LOSE", "raw_b": "WIN"},
    ]


def worlds_pushable_2way(*, pushable: bool):
    """Spread or total, identical numeric line at both books, opposite
    sides. If the line is an integer the exact-tie margin is reachable and
    a PUSH world exists; a half-point line cannot push."""
    worlds = [
        {"world_id": "SIDE_A_COVERS", "raw_a": "WIN", "raw_b": "LOSE"},
        {"world_id": "SIDE_B_COVERS", "raw_a": "LOSE", "raw_b": "WIN"},
    ]
    if pushable:
        worlds.append({"world_id": "PUSH", "raw_a": "PUSH", "raw_b": "PUSH"})
    return worlds


def worlds_prop_over_under(*, pushable: bool, dnp_risk: bool):
    """Same-player O/U prop at two books. If the named player does not
    play, BOTH legs void (both legs reference the same real-world player)."""
    worlds = [
        {"world_id": "OVER_HITS", "raw_a": "WIN", "raw_b": "LOSE"},
        {"world_id": "UNDER_HITS", "raw_a": "LOSE", "raw_b": "WIN"},
    ]
    if pushable:
        worlds.append({"world_id": "PUSH", "raw_a": "PUSH", "raw_b": "PUSH"})
    if dnp_risk:
        worlds.append({"world_id": "PLAYER_DNP", "raw_a": "VOID",
                       "raw_b": "VOID"})
    return worlds


# ---------------------------------------------------------------------------
# End-to-end candidate builder: simultaneity + settlement-rule check, in
# that combined inequality. Flag-only output.
# ---------------------------------------------------------------------------

FLAG_SCHEMA = "market_program/M09/true_arb_flag/1"


def build_flag(*, game_id, market_kind, leg_a_quote, leg_b_quote, worlds,
               clock_skew, vendor_latency_bounds, limit_a=None, limit_b=None):
    """leg_*_quote: {'venue', 'price_decimal', 't_prev', 't_seen',
                      'poll_interval'} (all from the actual poll log, never
                      a nominal cadence).
    Returns a flag dict. verdict is one of:
      TRUE_ARB_CANDIDATE  -- both simultaneity AND settlement checks passed
      NOT_TRUE_ARB        -- settlement/limits inequality failed (see reason)
      SIMULTANEITY_UNVERIFIABLE -- settlement math may be positive, but
                                    simultaneity cannot be certified, so the
                                    reserved word is withheld
    A flag NEVER contains an order-shaped field (no qty/side/order-type
    ready for submission) -- see TESTS.py schema check.
    """
    sim = simultaneity_window(
        {"venue": leg_a_quote["venue"], "t_prev": leg_a_quote.get("t_prev"),
         "t_seen": leg_a_quote["t_seen"],
         "poll_interval": leg_a_quote.get("poll_interval")},
        {"venue": leg_b_quote["venue"], "t_prev": leg_b_quote.get("t_prev"),
         "t_seen": leg_b_quote["t_seen"],
         "poll_interval": leg_b_quote.get("poll_interval")},
        clock_skew=clock_skew, vendor_latency_bounds=vendor_latency_bounds)

    settlement = evaluate_2leg_true_arb(
        {"venue": leg_a_quote["venue"], "price_decimal": leg_a_quote["price_decimal"]},
        {"venue": leg_b_quote["venue"], "price_decimal": leg_b_quote["price_decimal"]},
        worlds, limit_a=limit_a, limit_b=limit_b)

    if sim["verdict"] == "SIMULTANEOUS_WITNESSED" and \
            settlement["verdict"] == "TRUE_ARB_CANDIDATE":
        verdict = "TRUE_ARB_CANDIDATE"
    elif sim["verdict"] == "SIMULTANEITY_UNVERIFIABLE" and \
            settlement["verdict"] == "TRUE_ARB_CANDIDATE":
        # Settlement math alone is never enough; the reserved term is
        # withheld until simultaneity is certified (contract section 1.1:
        # "simultaneously executable at witnessed prices").
        verdict = "SIMULTANEITY_UNVERIFIABLE"
    else:
        verdict = "NOT_TRUE_ARB"

    flag = {
        "schema": FLAG_SCHEMA,
        "flag_id": None,   # filled by caller at append time (needs a clock)
        "game_id": game_id,
        "market_kind": market_kind,
        "leg_a": {"venue": leg_a_quote["venue"],
                  "capture_ts": fmt_ts(leg_a_quote["t_seen"]),
                  "price_decimal": leg_a_quote["price_decimal"]},
        "leg_b": {"venue": leg_b_quote["venue"],
                  "capture_ts": fmt_ts(leg_b_quote["t_seen"]),
                  "price_decimal": leg_b_quote["price_decimal"]},
        "simultaneity": sim,
        "settlement": settlement,
        "verdict": verdict,
        "epistemic_status": (
            "SCANNING INFRASTRUCTURE. Detects candidate true arbitrage as "
            "defined by the M00 taxonomy. A flag is a measurement of quoted "
            "prices at capture timestamps, not a claim of executable "
            "profit; execution realism belongs to M21 and any order ever "
            "belongs behind a USER_REQUIRED gate."),
        "is_order": False,
        "is_order_intent": False,
    }
    flag["flag_hash"] = sha256_hex(canonical_json(
        {k: v for k, v in flag.items() if k not in ("flag_id", "flag_hash")}))
    return flag


class AppendOnlyFlagLog:
    """Append-only JSONL flag log. A correction is a new row referencing the
    prior flag_hash via 'prev_flag_ref'; there is never an UPDATE (contract
    section 6.3 append-only discipline, applied to this lane's own output)."""

    def __init__(self, path):
        self.path = path
        self._n_written = 0

    def append(self, flag, *, seq=None, prev_flag_ref=None):
        seq = self._n_written if seq is None else seq
        flag = dict(flag)
        flag["flag_id"] = f"FLAG_{seq:08d}_{flag['flag_hash'][:12]}"
        flag["prev_flag_ref"] = prev_flag_ref
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(canonical_json(flag) + "\n")
        self._n_written += 1
        return flag["flag_id"]

    def read_all(self):
        out = []
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        except FileNotFoundError:
            pass
        return out
