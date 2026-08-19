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
  2. Dispersion of the POSTED LINE across games: sd = 8.445, measured over **457 distinct
     games** from the 2025 historical archive plus the 2026 live tape. **This uses no
     outcome** -- only where books set their numbers.

     ON PARTITION, stated plainly rather than glossed: 2025 and 2026 are both holdout
     seasons, and there is no alternative, because no exploration-era totals lines exist in
     this repository at all -- `drive_masters/master_odds.csv` carries spreads and moneyline
     only (D147). So the line term MUST come from holdout-era data. It is admissible because
     it uses no outcome and therefore cannot carry outcome information across the boundary;
     the outcome term in (1) is exploration-only and never mixes with it.

  3. Residual dispersion around the line, by variance decomposition:
         sd_resid = sqrt(var_total - var_line) = 15.099

  SENSITIVITY TO THE LINE SAMPLE, because this was the weakest input and was re-measured:

        scope              games   sd_line   sd_resid   breakeven window
        2025 only            198     6.077     16.198        1.935
        2026 only            259     7.920     15.380        1.837
        2025+2026 pooled     457     8.445     15.099        1.803
        (original estimate)   48     8.370     15.140        1.810

     **The breakeven window is 1.80-1.94 points under every scope**, so the verdict on 1.0-
     and 1.5-point middles does not depend on the choice. The POOLED figure is used because
     it has the most data AND yields the NARROWEST breakeven, i.e. it is the estimate most
     favourable to middles -- and they still lose.

  ASSUMPTIONS, named because they are assumptions:
    * the line is an unbiased conditional mean and is uncorrelated with its own residual.
      Standard, and it is what makes the subtraction legitimate;
    * the residual is approximately Gaussian. Totals are discrete and mildly skewed, so this
      is an approximation whose error is second-order over a 1-5 point window;
    * the window sits CENTRED on the line. A middle whose window sits off-centre hits less
      often than this model says, so every number here is an UPPER bound;
    * `sd_line` now rests on 457 games rather than the original 48. It was the weakest
      input, was re-measured, and the conclusion did not move (see the table above).

  ROBUSTNESS, and the reason the headline survives: using the UNCONDITIONAL sd (17.30)
  instead of the residual (15.15) *lowers* every hit rate, because a wider distribution puts
  less mass in a narrow window. The favourable assumption is the one used, and even it calls
  1.0- and 1.5-point middles negative. The conclusion does not depend on the decomposition.
"""
from __future__ import annotations

import json as _json
import os as _os

from dataclasses import dataclass
from math import erf, sqrt

#: Measured on the exploration partition (2021-2024, 888 games). No market data.
SD_TOTAL_EXPLORATION = 17.30
#: Measured across 457 games (2025 archive + 2026 tape). Uses no outcome. See the
#: sensitivity table in the module docstring for the 2025-only and 2026-only values.
SD_LINE_TAPE = 8.445
#: Every scope measured, kept so a reader can see the conclusion is scope-invariant.
SD_LINE_BY_SCOPE = {"2025_only": 6.077, "2026_only": 7.920, "pooled": 8.445}
#: Variance decomposition of the two above.
SD_RESIDUAL = sqrt(max(SD_TOTAL_EXPLORATION ** 2 - SD_LINE_TAPE ** 2, 1.0))

# ---------------------------------------------------------------------------------------
# SPREADS. A margin is not a total and must not borrow its dispersion.
#
# The coverage audit (D155 follow-up) declared spread middles out of scope precisely
# BECAUSE this quantity had never been measured, and pricing them with the totals
# distribution would have been worse than not showing them. It has now been measured, so
# the omission is closed rather than merely documented.
#
# Signed margin sd is sqrt(E[m^2]) over 888 exploration games (the signed margin is
# mean-zero by construction, since either side may win): 13.60. Spread-line dispersion
# across 457 games of 2025-2026 tape, lines only and NO outcome: 3.852.
#: Signed margin dispersion, exploration partition (2021-2024, 970 games). No market data.
#: An earlier pass reported 13.60 on 888 games; that set was incomplete (2024 regular season is
#: absent from the team-level gamelogs and has to be recovered by aggregating player logs).
#: 970 games supersedes it. The same complete set reproduces the TOTALS sd at 17.396 against the
#: 17.30 carried here from M10, which corroborates that constant rather than disturbing it.
SD_MARGIN_EXPLORATION = 13.7311
#: Spread-line dispersion across games, 457 games of tape. Uses no outcome.
SD_SPREAD_LINE_TAPE = 3.852
#: Residual dispersion around the posted spread.
SD_RESIDUAL_SPREAD = sqrt(max(SD_MARGIN_EXPLORATION ** 2 - SD_SPREAD_LINE_TAPE ** 2, 1.0))

#: Margins are LESS dispersed than totals, so a spread middle needs a NARROWER window than
#: a totals middle to break even: 1.56 points against 1.80 at -110/-110.
RESIDUAL_BY_MARKET = {"totals": SD_RESIDUAL, "spreads": SD_RESIDUAL_SPREAD}

# ---------------------------------------------------------------------------------------
# THE PUSH BRANCH.
#
# _p_window is open at both ends, so it scores "the game landed exactly on the line" as a
# MISS. That is wrong, and wrong in a way that matters: the leg sitting on the whole number
# is refunded while the other leg wins, so an exact landing pays roughly a full extra stake
# against what the window model assumed. WNBA margins pile up on 3, 5, 6, 7 and 10 -- a 2.5/3
# spread middle carries a ~5.4% push branch, which is enough to flip its sign from -6.08 to
# positive. This was nearly shipped as a caveat saying the effect was too small to matter;
# measuring it showed the opposite.
_PMF_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "push_pmf.json")
try:
    with open(_PMF_PATH, encoding="utf-8") as _fh:
        _PMF = _json.load(_fh)
    PUSH_PMF_AVAILABLE = True
except FileNotFoundError:          # never silently zero -- callers must be able to tell
    _PMF = {"margin": {}, "total": {}, "_n_games": 0}
    PUSH_PMF_AVAILABLE = False

PUSH_PMF_GAMES = _PMF.get("_n_games", 0)
_PMF_KEY = {"totals": "total", "spreads": "margin"}


def push_probability(points, market: str = "totals") -> float:
    """Total probability that the settling number lands on one of `points`.

    Only whole numbers can push; a half-point line cannot. Returns 0.0 for half-points and
    for numbers outside the measured support, which is the conservative direction: the
    correction is always POSITIVE, so omitting it understates rather than oversells.
    """
    table = _PMF.get(_PMF_KEY.get(market, "total"), {})
    out = 0.0
    for x in points:
        if x is None or not float(x).is_integer():
            continue
        out += table.get(str(int(abs(x))), 0.0)
    return out

UNCONDITIONAL_BY_MARKET = {"totals": SD_TOTAL_EXPLORATION, "spreads": SD_MARGIN_EXPLORATION}

PROVENANCE = (
    f"residual sd {SD_RESIDUAL:.2f} = sqrt({SD_TOTAL_EXPLORATION:.2f}^2 - {SD_LINE_TAPE:.2f}^2); "
    f"total sd from 888 exploration games (2021-2024); line sd from 457 games of 2025-2026 "
f"tape with NO outcome used, which is the only era in which totals lines exist here"
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
    p_push: float = 0.0
    ev_no_push: float = 0.0


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


def breakeven_window(dec_over: float, dec_under: float, sd: float | None = None,
                     market: str = "totals") -> float:
    """The narrowest window that is not negative expectation, by bisection."""
    if sd is None:
        sd = RESIDUAL_BY_MARKET.get(market, SD_RESIDUAL)
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
             stake_each: float = 100.0, market: str = "totals",
             push_points=()) -> MiddleEV:
    sd = RESIDUAL_BY_MARKET.get(market, SD_RESIDUAL)
    sd_unc = UNCONDITIONAL_BY_MARKET.get(market, SD_TOTAL_EXPLORATION)
    p = _p_window(window, sd)
    p_cons = _p_window(window, sd_unc)
    outlay = 2.0 * stake_each
    hit_profit = stake_each * (dec_over + dec_under) - outlay
    miss_profit = stake_each * min(dec_over, dec_under) - outlay
    ev_raw = p * hit_profit + (1.0 - p) * miss_profit
    # A push refunds the leg on the number and pays the other, so relative to the modelled
    # miss the game is better off by one full stake. The window model already counted this
    # outcome as a miss, so the correction is exactly p_push * stake_each.
    p_push = push_probability(push_points, market) if push_points else 0.0
    ev = ev_raw + p_push * stake_each
    be_p = breakeven_probability(dec_over, dec_under)
    be_w = breakeven_window(dec_over, dec_under, market=market)
    return MiddleEV(
        window=window,
        p_hit=round(p, 6),
        p_hit_conservative=round(p_cons, 6),
        ev=round(ev, 2),
        ev_per_unit_staked=round(ev / outlay, 6),
        breakeven_p=round(be_p, 6),
        breakeven_window=be_w,
        is_positive=bool(ev > 0),
        p_push=round(p_push, 6),
        ev_no_push=round(ev_raw, 2),
        basis=(PROVENANCE if market == "totals" else
               f"residual sd {SD_RESIDUAL_SPREAD:.2f} = sqrt({SD_MARGIN_EXPLORATION:.2f}^2"
               f" - {SD_SPREAD_LINE_TAPE:.3f}^2); signed margin sd from 970 exploration"
               f" games, spread-line sd from 457 games of tape with NO outcome used"),
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
