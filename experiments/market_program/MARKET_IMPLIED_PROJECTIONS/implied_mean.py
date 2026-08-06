"""MARKET_IMPLIED_PROJECTIONS -- implied-distribution-mean machinery.

Converts a vig-free over-probability at ONE line into an implied MEAN of
the underlying player-stat distribution. M11_CONSENSUS_MODEL removes vig
and combines books; it deliberately stops at a fair PROBABILITY (M11 is
market machinery, not a distributional model -- see its module docstring).
This module is the next stage this track owns: turning "book consensus
says P(over 20.5) = 0.54" into "book consensus implies a mean of ~20.9".

PREREGISTRATION (frozen before this module is run against any real props
row -- coarse-tape or live -- per the same no-tuning-on-results discipline
M11 applies to its vig method):

  1. DISTRIBUTIONAL SHAPE: the player-stat distribution around its line is
     assumed NORMAL. This is a declared modeling assumption, not a fitted
     one -- no distribution-shape parameter is estimated from any props
     data this track touches. It is the standard simplifying assumption
     used to invert a single-point probability into a mean when only one
     line is quoted (the props feeds here quote exactly one line per
     player-game-market on the modal book, so a two-parameter distribution
     is not separately identified from dispersion; see LIMITATION below).

  2. DISPERSION: sigma is a DECLARED, PREREGISTERED per-market-type
     constant (SIGMA_BY_MARKET below), not fitted to any outcome or price
     data in this repository. It is a coarse external heuristic informed by
     public WNBA per-game production-volatility ranges. It is frozen in
     this file before evaluation; changing it after seeing results is a new,
     separately-dated preregistration, exactly the discipline M11's
     PREREGISTRATION dict states for its vig method.

  3. VIG-REMOVAL METHOD: delegated entirely to M11_CONSENSUS_MODEL
     (consensus.py), which preregisters multiplicative-proportional as
     PRIMARY. This module never re-implements or overrides that choice.

LIMITATION, stated plainly and carried into every output row's
`method_note`: with one line and one probability, sigma is NOT identified
from the market data itself -- it is an assumption, and the resulting
`implied_mean` is only as good as that assumption. `book_dispersion` (the
spread of vig-free probabilities ACROSS books at the same line) is reported
separately and is NOT a measurement of the underlying stat's dispersion --
conflating the two would be a methodology error this module avoids.

Epistemic status (verbatim, carried in every output object):
"MARKET-REACTION SYSTEM COMPONENT under the four-system separation
(MARKET_PROGRAM_CONTRACT.md section 2). Estimates an implied mean from a
cross-book vig-free consensus probability at one line, under a declared,
preregistered, unfitted Normal-dispersion assumption. It models the market
plus a stated modeling assumption, never a fundamental prediction, and is
labelled per the M00 evidence ladder (always holds no label: []) ."

Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import math

EPISTEMIC_STATUS_LINE = (
    "MARKET-REACTION SYSTEM COMPONENT under the four-system separation. "
    "Estimates an implied mean from a cross-book vig-free consensus "
    "probability at one line, under a declared, preregistered, unfitted "
    "Normal-dispersion assumption. It models the market plus a stated "
    "modeling assumption, never a fundamental prediction, and is labelled "
    "per the M00 evidence ladder (always holds no label: [])."
)

# ---------------------------------------------------------------------------
# Preregistered dispersion table -- FROZEN before evaluation.
# Values are coarse external heuristics (typical WNBA per-game production
# std-dev ranges for the stat), NOT fitted to any props price or outcome
# data this program has captured. A market_key absent from this table is
# UNSUPPORTED and no implied_mean is computed for it (fail closed, per the
# no-imputation discipline in MARKET_PROGRAM_CONTRACT.md section 4.5).
# ---------------------------------------------------------------------------
SIGMA_BY_MARKET = {
    "player_points": 6.0,
    "player_rebounds": 2.6,
    "player_assists": 2.0,
    "player_threes": 1.3,
    "player_blocks": 0.9,
    "player_steals": 0.9,
}

DISPERSION_PREREGISTRATION = {
    "schema": "market_program/MARKET_IMPLIED_PROJECTIONS/dispersion_preregistration/1",
    "distributional_shape": "NORMAL",
    "sigma_by_market": dict(SIGMA_BY_MARKET),
    "fitted_from_this_programs_data": False,
    "frozen_before_evaluation": True,
    "rationale": (
        "Sigma is a declared external heuristic prior, not fitted to any "
        "props price or game-outcome data in this repository. It exists "
        "only to make the single-line-to-mean inversion computable; "
        "book_dispersion (cross-book probability spread) is reported "
        "separately and is never substituted for it."
    ),
}


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


DISPERSION_PREREGISTRATION_HASH = sha256_hex(canonical_json(DISPERSION_PREREGISTRATION))


# ---------------------------------------------------------------------------
# Standard normal inverse CDF (quantile function / probit).
# Peter Acklam's rational approximation, stdlib only, no scipy dependency.
# Accurate to better than 1.15e-9 absolute over (0, 1); see the fixture
# cross-check in TESTS.py against known standard-normal quantiles.
# ---------------------------------------------------------------------------
_A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
_B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01]
_C = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
_D = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00]

_P_LOW = 0.02425
_P_HIGH = 1.0 - _P_LOW


def norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF. p must be strictly in (0, 1)."""
    if not (0.0 < p < 1.0):
        raise ValueError(f"norm_ppf requires p in (0,1), got {p!r}")
    if p < _P_LOW:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
               ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    if p <= _P_HIGH:
        q = p - 0.5
        r = q * q
        return (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / \
               (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class ImpliedMeanError(Exception):
    pass


def implied_mean_from_probability(*, market_key: str, line: float,
                                   vig_free_over_prob: float):
    """The core inversion this module preregisters.

    P(X > line) = 1 - Phi((line - mu) / sigma)   [X ~ Normal(mu, sigma)]
    =>  mu = line - sigma * Phi^{-1}(1 - p_over)

    Returns (implied_mean, sigma_used, method_note) or raises
    ImpliedMeanError for an unsupported market or a degenerate probability
    (0 or 1, which is either a data error or a genuinely unbounded implied
    mean -- neither is silently clipped).
    """
    if market_key not in SIGMA_BY_MARKET:
        raise ImpliedMeanError(
            f"market_key {market_key!r} not in the preregistered dispersion "
            "table; no implied_mean is computed (fail closed, no ad hoc "
            "sigma)")
    p = vig_free_over_prob
    if not (0.0 < p < 1.0):
        raise ImpliedMeanError(
            f"vig_free_over_prob must be strictly in (0,1) for a finite "
            f"implied mean under the Normal assumption; got {p!r}")
    sigma = SIGMA_BY_MARKET[market_key]
    z = norm_ppf(1.0 - p)
    mu = line - sigma * z
    method_note = (
        "Normal(mu, sigma) inversion of P(X>line)=p_over with sigma a "
        "preregistered, unfitted per-market constant (see "
        "DISPERSION_PREREGISTRATION); sigma is NOT identified from the "
        "market data itself, only line and p_over are."
    )
    return mu, sigma, method_note


def forward_probability_from_mean(*, market_key: str, line: float, mean: float):
    """Inverse of implied_mean_from_probability -- used ONLY by fixtures to
    construct synthetic markets with a known-true mean (TESTS.py / M00-U5
    style fixture use: synthetic values, no evidentiary weight, exercises
    the math in both directions to prove they are exact inverses)."""
    if market_key not in SIGMA_BY_MARKET:
        raise ImpliedMeanError(f"market_key {market_key!r} not in dispersion table")
    sigma = SIGMA_BY_MARKET[market_key]
    p_over = 1.0 - norm_cdf((line - mean) / sigma)
    return p_over
