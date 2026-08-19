"""middle_ev.py -- attach an expected value to a middle, which nothing in this programme did.

THE GAP THIS FILLS. `M10_MIDDLES` built the scanner and said so explicitly in its own
"what could not be established": *"Any probability model for game margins or totals. No
scalar EV is reported for any real candidate."* So every middle this programme has ever
surfaced -- including on the `M28` board -- was shown with a payoff shape and no probability,
which means it was shown without the one number that decides whether to take it.

THE RESULT, and it changes what the board should display: **at standard -110/-110 pricing a
middle needs to hit 4.762% of the time to break even, and a window under roughly two points
does not get there.** Most middles this board has surfaced were negative expectation.

HOW THE PROBABILITY IS DERIVED, including what is assumed rather than measured:

  1. Dispersion of FINAL TOTALS, measured on the exploration partition only (2021-2024,
     888 games): sd = 17.30. No line is involved, so no market data enters this term.
  2. Dispersion of the POSTED LINE across games, measured from the capture tape: sd = 8.37.
     **This uses no outcome** -- only where books set their numbers -- so it raises no
     partition question.
  3. Residual dispersion around the line, by variance decomposition:
         sd_resid = sqrt(var_total - var_line) = 15.15

  ASSUMPTIONS, named because they are assumptions:
    * the line is an unbiased conditional mean and is uncorrelated with its own residual.
      Standard, and it is what makes the subtraction legitimate;
    * the residual is approximately Gaussian. Totals are discrete and mildly skewed, so this
      is an approximation whose error is second-order over a 1-5 point window;
    * the window sits CENTRED on the line. A middle whose window sits off-centre hits less
      often than this model says, so every number here is an UPPER bound;
    * `sd_line` rests on 48 games of tape. It is the weakest input.

  ROBUSTNESS, and the reason the headline survives: using the UNCONDITIONAL sd (17.30)
  instead of the residual (15.15) *lowers* every hit rate, because a wider distribution puts
  less mass in a narrow window. The favourable assumption is the one used, and even it calls
  1.0- and 1.5-point middles negative. The conclusion does not depend on the decomposition.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt

#: Measured on the exploration partition (2021-2024, 888 games). No market data.
SD_TOTAL_EXPLORATION = 17.30
#: Measured from the capture tape across 48 games. Uses no outcome.
SD_LINE_TAPE = 8.37
#: Variance decomposition of the two above.
SD_RESIDUAL = sqrt(max(SD_TOTAL_EXPLORATION ** 2 - SD_LINE_TAPE ** 2, 1.0))

PROVENANCE = (
    f"residual sd {SD_RESIDUAL:.2f} = sqrt({SD_TOTAL_EXPLORATION:.2f}^2 - {SD_LINE_TAPE:.2f}^2); "
    f"total sd from 888 exploration games (2021-2024), line sd from the capture tape with no "
    f"outcome used"
)


@dataclass(frozen=True)
class MiddleEV:
    window: float
    p_hit: float
    p_hit_conservative: float
    ev: float
    ev_per_unit_staked: float
    breakeven_p: float
    breakeven_window: float
    is_positive: bool
    basis: str
    caveat: str


def _p_window(width: float, sd: float) -> float:
    """P(residual falls inside a window of `width` centred on the line)."""
    if width <= 0:
        return 0.0
    return erf((width / 2.0) / (sd * sqrt(2.0)))


def breakeven_probability(dec_over: float, dec_under: float) -> float:
    """Hit rate at which a middle breaks even, from the two prices alone.

    Stake 1 unit each side. Hit: both win -> (dec_o - 1) + (dec_u - 1).
    Miss: one wins, one loses -> min of (dec_o - 2), (dec_u - 2), the worse branch.
    """
    hit = (dec_over - 1.0) + (dec_under - 1.0)
    miss = min(dec_over, dec_under) - 2.0
    if hit - miss <= 0:
        return 1.0
    return -miss / (hit - miss)


def breakeven_window(dec_over: float, dec_under: float, sd: float = SD_RESIDUAL) -> float:
    """The narrowest window that is not negative expectation, by bisection."""
    target = breakeven_probability(dec_over, dec_under)
    lo, hi = 0.0, 40.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if _p_window(mid, sd) < target:
            lo = mid
        else:
            hi = mid
    return round(hi, 3)


def evaluate(window: float, dec_over: float, dec_under: float,
             stake_each: float = 100.0) -> MiddleEV:
    p = _p_window(window, SD_RESIDUAL)
    p_cons = _p_window(window, SD_TOTAL_EXPLORATION)
    outlay = 2.0 * stake_each
    hit_profit = stake_each * (dec_over + dec_under) - outlay
    miss_profit = stake_each * min(dec_over, dec_under) - outlay
    ev = p * hit_profit + (1.0 - p) * miss_profit
    be_p = breakeven_probability(dec_over, dec_under)
    be_w = breakeven_window(dec_over, dec_under)
    return MiddleEV(
        window=window,
        p_hit=round(p, 6),
        p_hit_conservative=round(p_cons, 6),
        ev=round(ev, 2),
        ev_per_unit_staked=round(ev / outlay, 6),
        breakeven_p=round(be_p, 6),
        breakeven_window=be_w,
        is_positive=bool(ev > 0),
        basis=PROVENANCE,
        caveat=(
            "Upper bound. The window is assumed centred on the line; an off-centre window hits "
            "less. The residual is assumed Gaussian on a discrete, mildly skewed variable. "
            "Push branches on whole-number edges are not modelled here."
        ),
    )


if __name__ == "__main__":
    from oddsmath import american_to_decimal as a2d
    d = a2d(-110)
    print(f"residual sd {SD_RESIDUAL:.2f}   breakeven p {breakeven_probability(d, d) * 100:.3f}%"
          f"   breakeven window {breakeven_window(d, d):.2f} pts")
    print()
    print(f"{'window':>8}{'P(hit)':>10}{'P cons':>10}{'EV/$200':>10}   verdict")
    for w in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        r = evaluate(w, d, d)
        print(f"{w:8.1f}{r.p_hit * 100:9.2f}%{r.p_hit_conservative * 100:9.2f}%"
              f"{r.ev:10.2f}   {'+EV' if r.is_positive else '-EV'}")
