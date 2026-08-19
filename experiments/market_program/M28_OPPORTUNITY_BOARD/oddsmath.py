"""oddsmath.py -- price arithmetic and settlement-aware opportunity math.

PURE FUNCTIONS ONLY. No I/O, no data loading, no rendering. Everything here is exact
arithmetic on witnessed prices, which is why it is the one module in this node that can
carry a hard claim: an arbitrage is a statement about numbers, not a forecast.

WHAT THIS MODULE MAY AND MAY NOT CLAIM (M00 contract, opportunity_taxonomy):

  * `arbitrage` is a RESERVED TERM. It may be used ONLY for TRUE_CROSS_BOOK_ARBITRAGE:
    a set of wagers whose combined return is locked positive in EVERY settlement outcome
    after applying each venue's own settlement rules. Anything merely likely to profit is
    a MIDDLE or a DISLOCATION and is named as such. Misusing the word is a Severity A
    vocabulary breach, so `arb_two_way` refuses to return a positive result unless the
    worst settlement outcome is strictly positive -- including pushes.

  * Detecting a locked price set is NOT an executability claim. M00 requires
    EXECUTION_FEASIBLE before anything may be called executable, and that rung needs
    measured limits, latency and slippage (M21/M22). Every result here therefore carries
    `executability_claimed = False`. The caller must keep it that way.

SETTLEMENT RULES IMPLEMENTED

  Basketball has no draw, so a two-way moneyline cannot push and its arbitrage condition
  is the textbook one. Totals and spreads CAN push when the number is a whole number and
  the game lands exactly on it, and a push returns the stake rather than paying out. A
  combination that is positive on both win branches but NEGATIVE on the push branch is
  NOT an arbitrage under the M00 definition, and this module rejects it. That distinction
  is the whole reason this file exists rather than a two-line implied-probability check.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------------------
# American odds <-> decimal <-> implied probability
# --------------------------------------------------------------------------------------


def american_to_decimal(price: float) -> float:
    """Total return multiple per unit staked, stake included.

    -110 -> 1.909..., +150 -> 2.5. American odds have no value in (-100, 100) exclusive;
    0 is not a price. Raise rather than silently coercing, because a bad price that
    survives into an arbitrage calculation produces a confident wrong answer.
    """
    p = float(price)
    if -100.0 < p < 100.0:
        raise ValueError(f"not a valid American price: {price!r}")
    if p > 0:
        return 1.0 + p / 100.0
    return 1.0 + 100.0 / (-p)


def decimal_to_american(dec: float) -> float:
    if dec <= 1.0:
        raise ValueError(f"decimal odds must exceed 1.0: {dec!r}")
    if dec >= 2.0:
        return round((dec - 1.0) * 100.0, 4)
    return round(-100.0 / (dec - 1.0), 4)


def implied_prob(price: float) -> float:
    """Vig-inclusive implied probability. These sum to > 1 across a book's own market."""
    return 1.0 / american_to_decimal(price)


def overround(prices) -> float:
    """Sum of vig-inclusive implied probabilities minus 1. The book's margin."""
    return sum(implied_prob(p) for p in prices) - 1.0


def devig_proportional(prices) -> list[float]:
    """Proportional (multiplicative) de-vig -- the neutral, standard method.

    Assumes the book's margin is a common multiplicative factor on every outcome. It
    introduces no favourite-longshot correction of its own. Stated as an assumption
    because it is one.
    """
    raw = [implied_prob(p) for p in prices]
    total = sum(raw)
    if total <= 0:
        raise ValueError("degenerate price set")
    return [r / total for r in raw]


# --------------------------------------------------------------------------------------
# Arbitrage
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Leg:
    """One wager in a combination."""
    book: str
    outcome: str
    price: float
    point: float | None = None
    last_update: str | None = None

    @property
    def decimal(self) -> float:
        return american_to_decimal(self.price)


@dataclass(frozen=True)
class ArbResult:
    """The outcome of a two-way arbitrage test.

    `is_arb` is True ONLY when the worst settlement branch is strictly positive, pushes
    included. `worst_case_return` is that branch, as a fraction of total outlay.
    """
    is_arb: bool
    legs: tuple[Leg, ...]
    total_implied: float
    stakes: tuple[float, ...] = ()
    total_stake: float = 0.0
    worst_case_profit: float = 0.0
    worst_case_return: float = 0.0
    push_possible: bool = False
    push_profit: float | None = None
    reason: str = ""
    executability_claimed: bool = False


def arb_two_way(
    leg_a: Leg,
    leg_b: Leg,
    bankroll: float = 1000.0,
    push_possible: bool = False,
    round_to: float = 0.01,
) -> ArbResult:
    """Test two opposing legs for a locked-positive combination.

    `push_possible` must be set by the caller when the market can land exactly on the
    number (whole-number totals and spreads). When it is set, a combination is only an
    arbitrage if it also survives the push branch, where the pushing leg returns its
    stake and the other leg loses.

    Stakes are allocated to equalise return across the two win branches, then rounded to
    a real currency increment; the worst branch is recomputed AFTER rounding, because
    rounding can move a marginal combination across zero.
    """
    d_a, d_b = leg_a.decimal, leg_b.decimal
    total_implied = 1.0 / d_a + 1.0 / d_b

    if total_implied >= 1.0:
        return ArbResult(
            is_arb=False, legs=(leg_a, leg_b), total_implied=total_implied,
            push_possible=push_possible,
            reason=f"implied probabilities sum to {total_implied:.6f} >= 1; no locked edge",
        )

    # Equalise payout across the two win branches.
    raw_a = bankroll * (1.0 / d_a) / total_implied
    raw_b = bankroll * (1.0 / d_b) / total_implied
    stake_a = round(raw_a / round_to) * round_to
    stake_b = round(raw_b / round_to) * round_to
    total_stake = stake_a + stake_b
    if total_stake <= 0:
        return ArbResult(
            is_arb=False, legs=(leg_a, leg_b), total_implied=total_implied,
            push_possible=push_possible, reason="stake rounds to zero at this bankroll",
        )

    ret_a = stake_a * d_a - total_stake   # A wins, B loses
    ret_b = stake_b * d_b - total_stake   # B wins, A loses
    branches = [ret_a, ret_b]

    push_profit = None
    if push_possible:
        # Both legs push together: the number landed exactly on the line both sides took.
        # Each stake is returned, so the combination nets zero -- not positive. Under the
        # M00 definition ("locked positive in EVERY settlement outcome") a zero branch is
        # not positive, so such a combination is reported as NOT an arbitrage.
        push_profit = 0.0
        branches.append(push_profit)

    worst = min(branches)
    is_arb = worst > 0.0

    if not is_arb and push_possible and min(ret_a, ret_b) > 0:
        reason = (
            "positive on both win branches but the push branch returns exactly the stake "
            "(zero profit); M00 requires locked-POSITIVE in every settlement outcome, so "
            "this is reported as a dislocation, not an arbitrage"
        )
    elif not is_arb:
        reason = "rounding to a real stake increment removed the edge"
    else:
        reason = "locked positive in every settlement branch"

    return ArbResult(
        is_arb=is_arb,
        legs=(leg_a, leg_b),
        total_implied=total_implied,
        stakes=(round(stake_a, 2), round(stake_b, 2)),
        total_stake=round(total_stake, 2),
        worst_case_profit=round(worst, 2),
        worst_case_return=(worst / total_stake) if total_stake else 0.0,
        push_possible=push_possible,
        push_profit=push_profit,
        reason=reason,
    )


def can_push(market: str, point: float | None) -> bool:
    """Whether an exact landing on this number is possible.

    Half-point lines (-2.5, 170.5) cannot push. Whole numbers can. Moneyline in
    basketball has no draw and cannot push.
    """
    if market == "h2h" or point is None:
        return False
    return float(point).is_integer()


# --------------------------------------------------------------------------------------
# Middles
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class MiddleResult:
    """A straddle where both legs can win, but profit is PROBABILISTIC, never locked.

    M00 is explicit: middles are "not arbitrage". No stake is suggested here, because
    sizing a probabilistic bet requires a hit probability this node has not measured and
    a staking policy that is still gated (M24 <- M23 <- M22).
    """
    is_middle: bool
    legs: tuple[Leg, ...]
    window_low: float | None = None
    window_high: float | None = None
    window_width: float = 0.0
    cost_if_missed: float = 0.0
    profit_if_hit: float = 0.0
    push_edges: tuple[bool, bool] = (False, False)
    reason: str = ""


def middle_totals(
    over_leg: Leg, under_leg: Leg, stake_each: float = 100.0
) -> MiddleResult:
    """Over X at one book, Under Y at another, with Y > X.

    Any total strictly between X and Y wins BOTH legs. Outside the window exactly one leg
    wins and the other loses, so the loss is bounded by the vig, not the stake.
    """
    x = over_leg.point
    y = under_leg.point
    if x is None or y is None:
        return MiddleResult(False, (over_leg, under_leg), reason="totals legs need a point")
    if y <= x:
        return MiddleResult(
            False, (over_leg, under_leg),
            reason=f"Under {y} does not sit above Over {x}; no straddle window exists",
        )

    d_o, d_u = over_leg.decimal, under_leg.decimal
    outlay = stake_each * 2.0
    profit_if_hit = stake_each * d_o + stake_each * d_u - outlay
    # Outside the window: one leg wins, one loses.
    miss_over = stake_each * d_o - outlay      # total lands above y
    miss_under = stake_each * d_u - outlay     # total lands below x
    cost_if_missed = min(miss_over, miss_under)

    return MiddleResult(
        is_middle=True,
        legs=(over_leg, under_leg),
        window_low=x,
        window_high=y,
        window_width=round(y - x, 2),
        cost_if_missed=round(cost_if_missed, 2),
        profit_if_hit=round(profit_if_hit, 2),
        push_edges=(can_push("totals", x), can_push("totals", y)),
        reason=(
            f"total strictly between {x} and {y} wins both legs; outside it exactly one "
            "leg wins, so the downside is the vig rather than a full stake"
        ),
    )


# --------------------------------------------------------------------------------------
# Cross-book dispersion -- a descriptive statistic, not an opportunity class
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Dispersion:
    market: str
    outcome: str
    n_books: int
    best_price: float
    worst_price: float
    best_book: str
    consensus_prob: float
    spread_pct: float


def price_dispersion(quotes) -> Dispersion | None:
    """How far apart the books are on the same outcome.

    Descriptive only. Wide dispersion is where mispricings live, but dispersion is not
    itself an edge and this function makes no claim that it is.
    """
    quotes = [q for q in quotes if q is not None]
    if len(quotes) < 2:
        return None
    by_value = sorted(quotes, key=lambda q: american_to_decimal(q.price), reverse=True)
    best, worst = by_value[0], by_value[-1]
    probs = devig_pair_free([q.price for q in quotes])
    return Dispersion(
        market="", outcome=best.outcome, n_books=len(quotes),
        best_price=best.price, worst_price=worst.price, best_book=best.book,
        consensus_prob=sum(probs) / len(probs),
        spread_pct=round(
            (american_to_decimal(best.price) / american_to_decimal(worst.price) - 1.0) * 100.0, 3
        ),
    )


def devig_pair_free(prices) -> list[float]:
    """Vig-inclusive probabilities, kept separate from `devig_proportional`.

    Named explicitly so no caller mistakes a raw implied probability for a fair one.
    """
    return [implied_prob(p) for p in prices]
