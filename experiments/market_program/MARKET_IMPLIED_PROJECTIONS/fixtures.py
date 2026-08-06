"""MARKET_IMPLIED_PROJECTIONS -- synthetic fixtures with KNOWN answers.

M00-U5 use class (schema fixtures / test corpora): all timestamps and prices
here are SYNTHETIC, constructed forward from a chosen true mean/probability
via the exact algebraic inverse of the machinery under test, so a passing
test proves the pipeline recovers a value it did not see, not that it
echoes an input. No caveat-hash cross-check against TAXONOMY.json is
performed here (this fixture set is local to this track and does not touch
the T2 archive); the M00-U5 caveat text is still carried for consistency
with the lane-wide fixture-labelling convention M11 established.

Stdlib only.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M11_DIR = os.path.normpath(os.path.join(_HERE, "..", "M11_CONSENSUS_MODEL"))
sys.path = [p for p in sys.path if p not in (_M11_DIR, _HERE)]
sys.path.insert(0, _M11_DIR)
sys.path.insert(0, _HERE)

import consensus as m11   # noqa: E402
import implied_mean as im  # noqa: E402

M00_U5_CAVEAT_TEXT = (
    "Fixture data only. Timing fields are synthetic or T2 and carry no "
    "evidentiary weight."
)


def price_pair_for_probability(p_over: float, overround: float):
    """Build (american_over, american_under) whose PREREGISTERED
    multiplicative-proportional no-vig transform recovers EXACTLY
    (p_over, 1-p_over) -- by construction, since this is the exact forward
    map of no_vig_multiplicative's inverse.

    overround > 1.0 is the book's total (e.g. 1.05 == 5% vig).
    """
    p_under = 1.0 - p_over
    raw_over = p_over * overround
    raw_under = p_under * overround
    dec_over = 1.0 / raw_over
    dec_under = 1.0 / raw_under
    return (m11.decimal_to_american(dec_over), m11.decimal_to_american(dec_under))


def make_synthetic_quote(*, bookmaker, p_over, overround, capture_ts,
                          market="player_points", point=20.5, tier="T1"):
    american_over, american_under = price_pair_for_probability(p_over, overround)
    q = m11.make_quote(
        bookmaker=bookmaker, price=american_over, capture_ts=capture_ts,
        tier=tier, market=market, outcome="over", point=point,
    )
    q["opposite_price"] = american_under
    return q


def synthetic_market_from_true_mean(*, market_key, line, true_mean, books,
                                     base_ts=1_700_000_000):
    """books: list of (bookmaker_name, overround) pairs. Every book prices
    the SAME true p_over (derived from true_mean via the module under
    test's own forward map), so the consensus is expected to recover
    true_mean exactly modulo American-price rounding (decimal_to_american
    rounds to 4 dp)."""
    p_over = im.forward_probability_from_mean(
        market_key=market_key, line=line, mean=true_mean)
    quotes = []
    for i, (book, overround) in enumerate(books):
        quotes.append(make_synthetic_quote(
            bookmaker=book, p_over=p_over, overround=overround,
            capture_ts=base_ts + i, market=market_key, point=line))
    return quotes, p_over
