"""Synthetic fixtures for M11_CONSENSUS_MODEL.

All timestamps are synthetic (year 2030), all bookmaker names fictional --
the M00-U5 principle applied to fully synthetic data, so no test can lean on
a real capture stamp or a real book's name/behavior. Prices are hand-picked
so the no-vig arithmetic is checkable exactly by hand (see TESTS.py).

m00_use_class: M00-U5 (Schema fixtures and test corpora). Caveat text
verbatim: "Fixture data only. Timing fields are synthetic or T2 and carry no
evidentiary weight." caveat_sha256
f2d6cfbc2f135d7e053da799217b44a8d686078ecf598a7c22286a26bdd53f7a
"""
from __future__ import annotations

import consensus as C

T0 = C.parse_ts("2030-01-01T00:00:00Z")
MIN = 60

M00_U5_CAVEAT_TEXT = ("Fixture data only. Timing fields are synthetic or T2 "
                       "and carry no evidentiary weight.")
M00_U5_CAVEAT_SHA256 = \
    "f2d6cfbc2f135d7e053da799217b44a8d686078ecf598a7c22286a26bdd53f7a"


def q(bookmaker, price, opposite_price, t_offset, *, tier="T0", point=None):
    return {
        **C.make_quote(bookmaker=bookmaker, price=price,
                        capture_ts=T0 + t_offset, tier=tier,
                        vendor_ts=None,
                        vendor_ts_semantics="unknown_unverified",
                        market="h2h", outcome="HOME", point=point),
        "opposite_price": opposite_price,
    }


def fx_two_books_symmetric():
    """Two books, both -110/-110: no-vig exactly 0.5/0.5 either side,
    overround exactly 1.9091/2 = 0.95238*2 = 1.0 - wait: raw(-110)=110/210
    = 0.523810; sum of two sides on ONE book = 1.047619 (overround). Both
    books identical -> consensus == 0.5, uncertainty == 0, disagreement == 0.
    """
    quotes = [q("bookx", -110, -110, 0 * MIN),
              q("booky", -110, -110, 5 * MIN)]
    return {"quotes": quotes, "truth": {
        "consensus": 0.5, "uncertainty": 0.0, "disagreement": 0.0,
        "raw_side": 110 / 210,
    }}


def fx_two_books_disagree():
    """bookx favors HOME more than booky: no-vig probs differ -> nonzero
    uncertainty and disagreement, residuals computable by hand."""
    quotes = [q("bookx", -150, 130, 0 * MIN),   # raw home = 150/250 = 0.6
              q("booky", -120, 100, 2 * MIN)]   # raw home = 120/220=0.5454..
    return {"quotes": quotes}


def fx_three_books_weighted():
    quotes = [q("bookx", -110, -110, 0 * MIN),
              q("booky", -105, -115, 1 * MIN),
              q("bookz", -120, 100, 2 * MIN)]
    return {"quotes": quotes}


def fx_t2_only():
    """A T2-tier snapshot: TIER_INSUFFICIENT, excluded from the fitted set,
    channel VENDOR_ASSERTED, but capture timestamp still carried."""
    quotes = [q("bookx", -110, -110, 0 * MIN, tier="T2")]
    return {"quotes": quotes}


def fx_mixed_tier():
    """One T0 quote, one T2 quote sharing a series: the T2 one is excluded
    from n_trusted but its capture timestamp is still listed."""
    quotes = [q("bookx", -110, -110, 0 * MIN, tier="T0"),
              q("booky", -115, -105, 1 * MIN, tier="T2")]
    return {"quotes": quotes}


def fx_mismatched_outcome():
    """Quotes spanning two different outcomes must be refused, never
    silently blended."""
    a = q("bookx", -110, -110, 0 * MIN)
    b = q("booky", -110, -110, 1 * MIN)
    b["outcome"] = "AWAY"
    return {"quotes": [a, b]}


def fx_weight_training_obs(fit_end_offset, eval_start_offset):
    """Training residual observations for fit_book_weights tests."""
    obs = []
    for i in range(8):
        obs.append({"bookmaker": "bookx", "capture_ts": T0 + i * MIN,
                    "residual": 0.01 * (i % 3 - 1)})
        obs.append({"bookmaker": "booky", "capture_ts": T0 + i * MIN,
                    "residual": 0.05 * (i % 2)})
    return {
        "observations": obs,
        "fit_window_end_ts": T0 + fit_end_offset,
        "evaluation_window_start_ts": T0 + eval_start_offset,
    }
