"""Synthetic fixtures for M10_MIDDLES.

All timestamps are synthetic (year 2030); all venues are fictional (mirrors
M09_TRUE_ARB_SCANNER's fixture discipline and reuses its venue names for
lane-wide vocabulary consistency: book_alpha/book_beta/book_gamma_push_pays/
book_delta_dnp_pays). No test leans on real capture bytes or the T2 archive.
Each fixture states its ground truth by construction.
"""
from __future__ import annotations

import middle_scanner as M

T0 = M.parse_ts("2030-01-01T00:00:00Z")
MIN = 60

MEASURED_SKEW = {"epsilon_max_s": 2, "method": "synthetic NTP fixture"}
VENDOR_BOUNDS = {
    "book_alpha": {"seconds": 20, "source": "synthetic bound"},
    "book_beta": {"seconds": 20, "source": "synthetic bound"},
    "book_gamma_push_pays": {"seconds": 20, "source": "synthetic bound"},
    "book_delta_dnp_pays": {"seconds": 20, "source": "synthetic bound"},
    "unregistered_book": {"seconds": 20, "source": "synthetic bound"},
}


def _quote(venue, price_decimal, line, t_seen_off, *, t_prev_off=None,
           poll_interval=300):
    return {
        "venue": venue, "price_decimal": price_decimal, "line": line,
        "t_seen": T0 + t_seen_off,
        "t_prev": None if t_prev_off is None else T0 + t_prev_off,
        "poll_interval": poll_interval,
    }


# ---------------------------------------------------------------------------
# 1. Clean half-point spread middle: book_alpha -5.5 (leg on the favorite),
#    book_beta +6.5 (leg on the underdog at a DIFFERENT, softer number) ->
#    gap (5.5, 6.5), margin==6 is the only win-win integer, no push worlds
#    (both lines half-point). Both venues on file -> MIDDLE_CANDIDATE.
# ---------------------------------------------------------------------------
def fx_clean_half_point_middle():
    leg_a = _quote("book_alpha", M.american_to_decimal(-110), -5.5, 300)
    leg_b = _quote("book_beta", M.american_to_decimal(-110), 6.5, 305)
    t_lo, t_hi = M.spread_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_1", "market_kind": "spread_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "MIDDLE_CANDIDATE", "gap_win_win_integers": [6],
                   "n_worlds": 3},
    }


# ---------------------------------------------------------------------------
# 2. Mirror-image lines (-5.5 / +5.5): no gap -> NOT_MIDDLE. This is the
#    ordinary single-line case arb_scanner.py's worlds_pushable_2way already
#    covers (a normal spread bet, or arb-scanner's own territory if prices
#    cross) -- never a middle.
# ---------------------------------------------------------------------------
def fx_mirror_lines_not_middle():
    leg_a = _quote("book_alpha", M.american_to_decimal(-110), -5.5, 300)
    leg_b = _quote("book_beta", M.american_to_decimal(-110), 5.5, 303)
    t_lo, t_hi = M.spread_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_2", "market_kind": "spread_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "NOT_MIDDLE"},
    }


# ---------------------------------------------------------------------------
# 3. Crossed the WRONG way (book_beta's line is TIGHTER than book_alpha's,
#    not looser): t_lo > t_hi -> no gap -> NOT_MIDDLE. Distinguishes "no
#    gap because equal" (fixture 2) from "no gap because inverted".
# ---------------------------------------------------------------------------
def fx_inverted_lines_not_middle():
    leg_a = _quote("book_alpha", M.american_to_decimal(-110), -7.5, 300)
    leg_b = _quote("book_beta", M.american_to_decimal(-110), 5.5, 303)
    t_lo, t_hi = M.spread_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_3", "market_kind": "spread_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "NOT_MIDDLE"},
    }


# ---------------------------------------------------------------------------
# 4. Integer line at leg_a only (-6.0 vs +7.5): PUSH_AT_A world exists.
#    book_gamma_push_pays pays a push as a win -> verify that world's profit
#    equals win_coef_a * stake_a, not 0.
# ---------------------------------------------------------------------------
def fx_push_at_a_nonstandard_rule():
    leg_a = _quote("book_gamma_push_pays", M.american_to_decimal(-110), -6.0, 300)
    leg_b = _quote("book_beta", M.american_to_decimal(-110), 7.5, 303)
    t_lo, t_hi = M.spread_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_4", "market_kind": "spread_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "MIDDLE_CANDIDATE",
                   "push_at_a_equals_win": True, "n_worlds": 4},
    }


# ---------------------------------------------------------------------------
# 5. Same geometry as #4, but leg_a is on book_alpha (standard void_return
#    push rule) -> PUSH_AT_A world profit must be exactly
#    0*stake_a + win_coef_b*stake_b (push voids leg_a, leg_b still wins).
# ---------------------------------------------------------------------------
def fx_push_at_a_standard_rule():
    leg_a = _quote("book_alpha", M.american_to_decimal(-110), -6.0, 300)
    leg_b = _quote("book_beta", M.american_to_decimal(-110), 7.5, 303)
    t_lo, t_hi = M.spread_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_5", "market_kind": "spread_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "MIDDLE_CANDIDATE",
                   "push_at_a_equals_void": True, "n_worlds": 4},
    }


# ---------------------------------------------------------------------------
# 6. Integer line at leg_b only (totals: Over 165.0 book_alpha / Under 168.5
#    book_delta_dnp_pays) -> PUSH_AT_B world exists, standard void_return
#    rule at book_delta_dnp_pays for PUSH (its nonstandard rule is DNP/void,
#    not push -- exercises that the two rule dimensions are independent).
# ---------------------------------------------------------------------------
def fx_push_at_b_totals():
    leg_a = _quote("book_alpha", M.american_to_decimal(-108), 165.5, 300)
    leg_b = _quote("book_delta_dnp_pays", M.american_to_decimal(-112), 168.0, 302)
    t_lo, t_hi = M.over_under_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_6", "market_kind": "totals_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "MIDDLE_CANDIDATE",
                   "push_at_b_equals_void": True, "n_worlds": 4},
    }


# ---------------------------------------------------------------------------
# 7. Both boundaries integer (totals 165.0 / 168.0) -> both PUSH_AT_A and
#    PUSH_AT_B worlds exist; 5 total worlds.
# ---------------------------------------------------------------------------
def fx_both_boundaries_integer():
    leg_a = _quote("book_alpha", M.american_to_decimal(-108), 165.0, 300)
    leg_b = _quote("book_beta", M.american_to_decimal(-112), 168.0, 302)
    t_lo, t_hi = M.over_under_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_7", "market_kind": "totals_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "MIDDLE_CANDIDATE", "n_worlds": 5,
                   "gap_win_win_integers": [166, 167]},
    }


# ---------------------------------------------------------------------------
# 8. Same-player prop O/U middle with DNP risk, both venues rule-verified:
#    book_alpha Over 15.5, book_beta Under 17.5 -> SUBJECT_DNP world added
#    (void_return at both -> multiplier 0/0).
# ---------------------------------------------------------------------------
def fx_prop_middle_dnp_supported():
    leg_a = _quote("book_alpha", M.american_to_decimal(-115), 15.5, 300)
    leg_b = _quote("book_beta", M.american_to_decimal(-105), 17.5, 301)
    t_lo, t_hi = M.over_under_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_8", "market_kind": "prop_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": True,
        "truth": {"verdict": "MIDDLE_CANDIDATE", "n_worlds": 4,
                   "dnp_world_present": True},
    }


# ---------------------------------------------------------------------------
# 9. Same geometry, but leg_b is on an unregistered venue -> the DNP/void
#    rule cannot be verified -> SETTLEMENT_UNSUPPORTED, even though the gap
#    itself is real and would otherwise be a clean middle.
# ---------------------------------------------------------------------------
def fx_prop_middle_dnp_unsupported():
    leg_a = _quote("book_alpha", M.american_to_decimal(-115), 15.5, 300)
    leg_b = _quote("unregistered_book", M.american_to_decimal(-105), 17.5, 301)
    t_lo, t_hi = M.over_under_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_9", "market_kind": "prop_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": True,
        "truth": {"verdict": "SETTLEMENT_UNSUPPORTED"},
    }


# ---------------------------------------------------------------------------
# 10. Half-point/half-point gap (no push/void risk at all) on an unregistered
#     venue -> STILL SETTLEMENT_UNSUPPORTED, because win_coefficient always
#     needs a verified fee row even when no push/void world exists. This is
#     the "fee row required unconditionally" behavior, exercised on its own.
# ---------------------------------------------------------------------------
def fx_half_point_unregistered_fee_unsupported():
    leg_a = _quote("book_alpha", M.american_to_decimal(-110), -5.5, 300)
    leg_b = _quote("unregistered_book", M.american_to_decimal(-110), 6.5, 303)
    t_lo, t_hi = M.spread_thresholds(leg_a["line"], leg_b["line"])
    return {
        "game_id": "G_SYN_10", "market_kind": "spread_middle",
        "leg_a": leg_a, "leg_b": leg_b, "t_lo": t_lo, "t_hi": t_hi,
        "dnp_risk": False,
        "truth": {"verdict": "SETTLEMENT_UNSUPPORTED"},
    }


ALL_FIXTURES = {
    "clean_half_point_middle": fx_clean_half_point_middle,
    "mirror_lines_not_middle": fx_mirror_lines_not_middle,
    "inverted_lines_not_middle": fx_inverted_lines_not_middle,
    "push_at_a_nonstandard_rule": fx_push_at_a_nonstandard_rule,
    "push_at_a_standard_rule": fx_push_at_a_standard_rule,
    "push_at_b_totals": fx_push_at_b_totals,
    "both_boundaries_integer": fx_both_boundaries_integer,
    "prop_middle_dnp_supported": fx_prop_middle_dnp_supported,
    "prop_middle_dnp_unsupported": fx_prop_middle_dnp_unsupported,
    "half_point_unregistered_fee_unsupported": fx_half_point_unregistered_fee_unsupported,
}


def run_fixture(fx, *, probabilities=None):
    return M.build_middle_flag(
        game_id=fx["game_id"], market_kind=fx["market_kind"],
        leg_a_quote=fx["leg_a"], leg_b_quote=fx["leg_b"],
        t_lo=fx["t_lo"], t_hi=fx["t_hi"], dnp_risk=fx["dnp_risk"],
        probabilities=probabilities,
        clock_skew=MEASURED_SKEW, vendor_latency_bounds=VENDOR_BOUNDS)
