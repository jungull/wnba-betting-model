"""consensus_edge.py -- is this price better than what the rest of the market thinks?

M30 measured what a cross-book disagreement is actually worth, on 54,524 live quotes and a
reserved 66,967-quote replication that agreed to two decimal places. The finding the board
needs is a threshold:

    betting blind                    -4.43% a stake
    always taking the best of 11     -2.05%
    book generous by >= 1.0pp        -1.76%
    book generous by >= 1.5pp        -0.63%
    book generous by >= 2.0pp        +0.02%   (breaks even; CI spans zero)
    book generous by >= 3.0pp        +1.44%   (and +2.74% in replication)

So dispersion below about 2 percentage points of de-vigged opinion is NOT an opportunity,
and the board must stop presenting it as one. 3pp is where acting is justified.

The arithmetic here is deliberately identical to M30's so that the threshold means on the
live board exactly what it meant in the measurement: de-vig each book across its own two
sides FIRST, then take the MEDIAN of every OTHER book, requiring at least three peers.

None of this involves a scoring model. The edge, where it exists, comes entirely from books
disagreeing with each other, so this lane is untouched by S42 and by D141/D150's finding
that our model trails the market.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import oddsmath as om

# THE GATE IS ON `edge`, NOT ON THE OPINION GAP, and that distinction was found by running
# this on live quotes: a BetRivers price of -910 sat 2.12pp clear of peer opinion and still
# returned -3.07%, because at a heavy favourite the vig eats a 2pp dislocation whole. The
# opinion gap is what M30 BUCKETED BY; the edge is what you are paid. So the board gates on
# the payoff and uses the gap only to grade strength.
#
# Note what each number is worth. "edge > 0" is directly implementable at quote time with no
# lookahead, and M30 found it on 1.18% of quotes in BOTH samples, worth +1.68% and +2.24%.
# The >= 3pp grade is the stronger claim, because gap and edge are different quantities and
# finding that a 3pp gap implies positive edge is a real finding rather than a truncation.
MIN_EDGE = 0.0        # the price must beat peer consensus AFTER that book's own vig
ACT_PP = 0.030        # gap grade at which M30 measured +1.44% live, +2.74% replication
WATCH_PP = 0.020      # gap grade where M30 measured break-even, CI spanning zero
MIN_PEERS = 3         # two peers cannot outvote a disagreement in any meaningful sense

PROVENANCE = ("D157 / M30: thresholds measured on 54,524 live quotes over 48 games and "
              "replicated on 66,967 quotes over 411 games reserved by preregistration. "
              "Market prices only -- no model, and no game outcome was read.")


@dataclass(frozen=True)
class Dislocation:
    game_id: str
    matchup: str
    commence_time: str
    market: str
    outcome: str
    point: float | None
    book: str
    book_title: str
    price: float
    last_update: str
    p_raw: float          # vigged implied probability -- what you actually pay
    p_devig: float        # this book's opinion, vig removed
    consensus: float      # median de-vigged opinion of every OTHER book
    n_peers: int

    @property
    def opinion_gap(self) -> float:
        """How generous this book is, in de-vigged probability points. Positive = generous."""
        return self.consensus - self.p_devig

    @property
    def edge(self) -> float:
        """Expected return per unit staked if the peer consensus is the fair price."""
        return self.consensus / self.p_raw - 1.0

    @property
    def actionable(self) -> bool:
        """Beats consensus after vig AND is dislocated enough that M30 measured a return."""
        return self.edge > MIN_EDGE and self.opinion_gap >= ACT_PP

    @property
    def grade(self) -> str:
        if self.actionable:
            return "ACT"
        if self.opinion_gap >= WATCH_PP:
            return "WATCH"
        return "THIN"


def _median(vals: list[float]) -> float:
    vals = sorted(vals)
    n = len(vals)
    mid = n // 2
    return vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def find_dislocations(snapshot, min_edge: float = MIN_EDGE) -> list[Dislocation]:
    """Every pre-game quote that beats its peers' de-vigged consensus after its own vig."""
    # (game, market, book) -> the two sides, so each book can be de-vigged against itself
    per_book = defaultdict(list)
    for q in snapshot.quotes:
        if q.is_in_play(snapshot.captured_at):
            continue                       # in-play is a different process entirely (D151)
        per_book[(q.game_id, q.market, q.book, q.point)].append(q)

    devig: dict[tuple, float] = {}
    raw: dict[tuple, float] = {}
    for (gid, market, book, point), sides in per_book.items():
        if len(sides) != 2:
            continue                       # de-vigging assumes a complete two-sided market
        ps = [om.implied_prob(s.price) for s in sides]
        booksum = sum(ps)
        if booksum <= 0:
            continue
        for s, p in zip(sides, ps):
            devig[(gid, market, s.outcome, s.point, book)] = p / booksum
            raw[(gid, market, s.outcome, s.point, book)] = p

    by_side = defaultdict(dict)
    for key, p in devig.items():
        gid, market, outcome, point, book = key
        by_side[(gid, market, outcome, point)][book] = p

    quote_of = {}
    for q in snapshot.quotes:
        quote_of[(q.game_id, q.market, q.outcome, q.point, q.book)] = q

    out: list[Dislocation] = []
    for (gid, market, outcome, point), books in by_side.items():
        if len(books) < MIN_PEERS + 1:
            continue
        for book, p_dv in books.items():
            peers = [v for b, v in books.items() if b != book]
            if len(peers) < MIN_PEERS:
                continue
            cons = _median(peers)
            q = quote_of.get((gid, market, outcome, point, book))
            if q is None:
                continue
            p_raw = raw[(gid, market, outcome, point, book)]
            if p_raw <= 0 or cons / p_raw - 1.0 <= min_edge:
                continue
            out.append(Dislocation(
                game_id=gid, matchup=q.matchup, commence_time=q.commence_time,
                market=market, outcome=outcome, point=point,
                book=book, book_title=q.book_title, price=q.price,
                last_update=q.last_update,
                p_raw=p_raw,
                p_devig=p_dv, consensus=cons, n_peers=len(peers),
            ))
    out.sort(key=lambda d: -d.edge)
    return out
