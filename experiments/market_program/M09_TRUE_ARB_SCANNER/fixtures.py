"""Synthetic fixtures for M09_TRUE_ARB_SCANNER.

All timestamps are synthetic (year 2030); all venues are fictional
(book_alpha/book_beta/book_gamma_push_pays/book_delta_dnp_pays/
exchange_epsilon) so no test can lean on real capture bytes (mirrors the
M00-U5 principle applied to fully synthetic data -- no T2 or real T0 bytes
are used at all). Each fixture states its ground truth by construction.
"""
from __future__ import annotations

import arb_scanner as A

T0 = A.parse_ts("2030-01-01T00:00:00Z")
MIN = 60


def _mk(t):
    return A.fmt_ts(T0 + t)


MEASURED_SKEW = {"epsilon_max_s": 2, "method": "synthetic NTP fixture"}
VENDOR_BOUNDS = {
    "book_alpha": {"seconds": 20, "source": "synthetic bound"},
    "book_beta": {"seconds": 20, "source": "synthetic bound"},
    "book_gamma_push_pays": {"seconds": 20, "source": "synthetic bound"},
    "book_delta_dnp_pays": {"seconds": 20, "source": "synthetic bound"},
    "exchange_epsilon": {"seconds": 20, "source": "synthetic bound"},
}


def _quote(venue, price_decimal, t_seen_off, *, t_prev_off=None,
           poll_interval=300):
    return {
        "venue": venue, "price_decimal": price_decimal,
        "t_seen": T0 + t_seen_off,
        "t_prev": None if t_prev_off is None else T0 + t_prev_off,
        "poll_interval": poll_interval,
    }


# ---------------------------------------------------------------------------
# 1. Clean h2h true arb: both books polled seconds apart, prices cross.
# ---------------------------------------------------------------------------
def fx_clean_h2h_arb():
    # book_alpha side A at decimal 2.10 (imp .4762), book_beta side B at
    # decimal 2.20 (imp .4545); sum .9307 < 1 -> classic arb.
    leg_a = _quote("book_alpha", 2.10, 300, t_prev_off=0)
    leg_b = _quote("book_beta", 2.20, 305, t_prev_off=0)
    return {
        "game_id": "G_SYN_1", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "TRUE_ARB_CANDIDATE"},
    }


# ---------------------------------------------------------------------------
# 2. h2h, no crossing: normal vig, not an arb.
# ---------------------------------------------------------------------------
def fx_no_arb_h2h():
    leg_a = _quote("book_alpha", 1.90, 300)
    leg_b = _quote("book_beta", 1.95, 305)
    return {
        "game_id": "G_SYN_2", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "NOT_TRUE_ARB"},
    }


# ---------------------------------------------------------------------------
# 3. Fee erodes an otherwise-crossing price: paper-positive without the fee,
#    not locked positive with it.
# ---------------------------------------------------------------------------
def fx_fee_erodes_arb():
    # book_alpha 2.00 (imp .5000) vs exchange_epsilon 2.01 (imp .49751);
    # raw sum .99751 < 1 is a small paper edge (~0.25%), but
    # exchange_epsilon charges 2% commission on net win, which cuts its
    # effective decimal to ~1.9898 (imp .50256) -- effective sum > 1, no
    # longer locked positive. The fixture pair fx_fee_erodes_arb_no_fee
    # below runs the identical prices through a zero-fee venue to show the
    # SAME crossing prices WOULD have been an arb absent the fee -- the fee
    # is what the inequality is actually pricing in, not a downstream haircut.
    leg_a = _quote("book_alpha", 2.00, 300)
    leg_b = _quote("exchange_epsilon", 2.01, 302)
    return {
        "game_id": "G_SYN_3", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "NOT_TRUE_ARB"},
    }


def fx_fee_erodes_arb_no_fee_control():
    """Same two prices, but leg_b priced at a zero-fee venue instead of the
    commission exchange -- control showing the crossing is real and only
    the fee flips the verdict."""
    leg_a = _quote("book_alpha", 2.00, 300)
    leg_b = _quote("book_beta", 2.01, 302)
    return {
        "game_id": "G_SYN_3B", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "TRUE_ARB_CANDIDATE"},
    }


# ---------------------------------------------------------------------------
# 4. Identical-line spread, both venues STANDARD push rule (void_return):
#    paper-positive win/lose worlds, but PUSH world is 0-0 -> never locked
#    positive -> NOT_TRUE_ARB, and the failing world must be PUSH.
# ---------------------------------------------------------------------------
def fx_pushable_standard_rules_not_arb():
    leg_a = _quote("book_alpha", 2.10, 300)   # side A -4 at book_alpha
    leg_b = _quote("book_beta", 2.20, 303)    # side B +4 at book_beta
    return {
        "game_id": "G_SYN_4", "market_kind": "spread_pushable",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_pushable_2way(pushable=True),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "NOT_TRUE_ARB", "failing_world": "PUSH"},
    }


# ---------------------------------------------------------------------------
# 5. Same crossing prices, but book_gamma_push_pays' rule pays push as a
#    win: the PUSH world is now (win_coef_a, 0) or similar and can be made
#    positive alongside the other two worlds -> TRUE_ARB_CANDIDATE. This is
#    the settlement-rule-compatibility check actually doing work.
# ---------------------------------------------------------------------------
def fx_pushable_nonstandard_rule_is_arb():
    leg_a = _quote("book_gamma_push_pays", 2.10, 300)   # side A, push pays
    leg_b = _quote("book_beta", 2.20, 303)              # side B, standard
    return {
        "game_id": "G_SYN_5", "market_kind": "spread_pushable",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_pushable_2way(pushable=True),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "TRUE_ARB_CANDIDATE"},
    }


# ---------------------------------------------------------------------------
# 6. Half-point spread (not pushable): same crossing prices as #4 but no
#    PUSH world exists -> behaves like clean h2h, TRUE_ARB_CANDIDATE.
# ---------------------------------------------------------------------------
def fx_half_point_spread_is_arb():
    leg_a = _quote("book_alpha", 2.10, 300)
    leg_b = _quote("book_beta", 2.20, 303)
    return {
        "game_id": "G_SYN_6", "market_kind": "spread_half_point",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_pushable_2way(pushable=False),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "TRUE_ARB_CANDIDATE"},
    }


# ---------------------------------------------------------------------------
# 7. Player prop, standard DNP-void rule at both books: crossing O/U prices
#    but the DNP world is 0-0 at both -> NOT_TRUE_ARB.
# ---------------------------------------------------------------------------
def fx_prop_dnp_standard_not_arb():
    leg_a = _quote("book_alpha", 2.05, 300)
    leg_b = _quote("book_beta", 2.15, 302)
    return {
        "game_id": "G_SYN_7", "market_kind": "prop_over_under",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_prop_over_under(pushable=False, dnp_risk=True),
        "limit_a": 200.0, "limit_b": 200.0,
        "truth": {"verdict": "NOT_TRUE_ARB", "failing_world": "PLAYER_DNP"},
    }


# ---------------------------------------------------------------------------
# 8. Same prop, book_delta_dnp_pays pays a DNP as a win on that leg -> arb.
# ---------------------------------------------------------------------------
def fx_prop_dnp_nonstandard_is_arb():
    leg_a = _quote("book_delta_dnp_pays", 2.05, 300)
    leg_b = _quote("book_beta", 2.15, 302)
    return {
        "game_id": "G_SYN_8", "market_kind": "prop_over_under",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_prop_over_under(pushable=False, dnp_risk=True),
        "limit_a": 200.0, "limit_b": 200.0,
        "truth": {"verdict": "TRUE_ARB_CANDIDATE"},
    }


# ---------------------------------------------------------------------------
# 9. Zero posted limit on one leg -> CAPACITY_ZERO, NOT_TRUE_ARB even though
#    the math crosses.
# ---------------------------------------------------------------------------
def fx_capacity_zero():
    leg_a = _quote("book_alpha", 2.10, 300)
    leg_b = _quote("book_beta", 2.20, 303)
    return {
        "game_id": "G_SYN_9", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 0.0,
        "truth": {"verdict": "NOT_TRUE_ARB", "reason": "CAPACITY_ZERO"},
    }


# ---------------------------------------------------------------------------
# 10. Capacity unknown (no limits table row / limits passed as None): the
#     existence check still runs, but capacity_status must read
#     CAPACITY_UNKNOWN, never a number pulled out of nowhere.
# ---------------------------------------------------------------------------
def fx_capacity_unknown():
    leg_a = _quote("book_alpha", 2.10, 300)
    leg_b = _quote("book_beta", 2.20, 303)
    return {
        "game_id": "G_SYN_10", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": None, "limit_b": None,
        "truth": {"verdict": "TRUE_ARB_CANDIDATE",
                  "capacity_status": "CAPACITY_UNKNOWN"},
    }


# ---------------------------------------------------------------------------
# 11. Crossing prices, but the two legs' witnessed capture instants are far
#     enough apart (beyond the widened window) that simultaneity fails ->
#     NOT_TRUE_ARB via simultaneity, even though settlement math is clean.
# ---------------------------------------------------------------------------
def fx_not_simultaneous():
    leg_a = _quote("book_alpha", 2.10, 300, t_prev_off=0)
    leg_b = _quote("book_beta", 2.20, 60 * MIN, t_prev_off=55 * MIN)
    return {
        "game_id": "G_SYN_11", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 500.0,
        "truth": {"verdict": "NOT_TRUE_ARB",
                  "simultaneity_verdict": "NOT_SIMULTANEOUS"},
    }


# ---------------------------------------------------------------------------
# 12. Crossing prices, legs seconds apart, but clock skew UNMEASURED for
#     this run -> SIMULTANEITY_UNVERIFIABLE, reserved word withheld.
# ---------------------------------------------------------------------------
def fx_clock_unbounded():
    leg_a = _quote("book_alpha", 2.10, 300, t_prev_off=0)
    leg_b = _quote("book_beta", 2.20, 303, t_prev_off=0)
    return {
        "game_id": "G_SYN_12", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 500.0,
        "clock_skew": A.UNMEASURED,
        "truth": {"verdict": "SIMULTANEITY_UNVERIFIABLE"},
    }


# ---------------------------------------------------------------------------
# 13. Crossing prices, but one venue has no sourced vendor-latency bound ->
#     UNBOUNDED -> SIMULTANEITY_UNVERIFIABLE.
# ---------------------------------------------------------------------------
def fx_vendor_unbounded():
    leg_a = _quote("book_alpha", 2.10, 300, t_prev_off=0)
    leg_b = _quote("book_beta", 2.20, 303, t_prev_off=0)
    # book_alpha simply absent from the vendor-latency-bounds table passed
    # for this run -> simultaneity_window()'s lookup defaults it to
    # A.UNBOUNDED, exactly the "no sourced bound" real-world condition.
    thin_bounds = {k: v for k, v in VENDOR_BOUNDS.items() if k != "book_alpha"}
    return {
        "game_id": "G_SYN_13", "market_kind": "h2h_2way",
        "leg_a": leg_a, "leg_b": leg_b,
        "worlds": A.worlds_h2h_2way(),
        "limit_a": 500.0, "limit_b": 500.0,
        "vendor_latency_bounds": thin_bounds,
        "truth": {"verdict": "SIMULTANEITY_UNVERIFIABLE"},
    }


ALL_FIXTURES = {
    "clean_h2h_arb": fx_clean_h2h_arb,
    "no_arb_h2h": fx_no_arb_h2h,
    "fee_erodes_arb": fx_fee_erodes_arb,
    "fee_erodes_arb_no_fee_control": fx_fee_erodes_arb_no_fee_control,
    "pushable_standard_rules_not_arb": fx_pushable_standard_rules_not_arb,
    "pushable_nonstandard_rule_is_arb": fx_pushable_nonstandard_rule_is_arb,
    "half_point_spread_is_arb": fx_half_point_spread_is_arb,
    "prop_dnp_standard_not_arb": fx_prop_dnp_standard_not_arb,
    "prop_dnp_nonstandard_is_arb": fx_prop_dnp_nonstandard_is_arb,
    "capacity_zero": fx_capacity_zero,
    "capacity_unknown": fx_capacity_unknown,
    "not_simultaneous": fx_not_simultaneous,
    "clock_unbounded": fx_clock_unbounded,
    "vendor_unbounded": fx_vendor_unbounded,
}


def run_fixture(fx):
    skew = fx.get("clock_skew", MEASURED_SKEW)
    vbounds = fx.get("vendor_latency_bounds", VENDOR_BOUNDS)
    return A.build_flag(
        game_id=fx["game_id"], market_kind=fx["market_kind"],
        leg_a_quote=fx["leg_a"], leg_b_quote=fx["leg_b"], worlds=fx["worlds"],
        clock_skew=skew, vendor_latency_bounds=vbounds,
        limit_a=fx["limit_a"], limit_b=fx["limit_b"])
