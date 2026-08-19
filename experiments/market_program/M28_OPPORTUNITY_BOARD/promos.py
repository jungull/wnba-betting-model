"""promos.py -- value venue promotions against a de-vigged cross-book consensus.

WHY THIS IS NOT GATED BY S42. A promotion's value is computed against the MARKET's own
de-vigged consensus probability, never against this programme's fundamental model. That is
a deliberate design choice, not an oversight: routing promo valuation through our model
would put it behind the adoption gate and, worse, would make a subsidy that anyone can
capture look like it depended on an edge we do not have (D141). The subsidy is disclosed
by the venue. No informational advantage is required to take it, and none is claimed here.

WHAT IS AND IS NOT COMPUTED

  * Expected value per unit staked: computed exactly, given the offer's stated terms and a
    consensus probability. This is arithmetic plus one clearly-named assumption.
  * The assumption: the de-vigged multi-book consensus is the best available estimate of
    the true probability. It is an ESTIMATE. Promo EV is therefore expectation, not a lock,
    and PROMOTIONAL_VALUE is explicitly "EV-positive-in-expectation, not locked".
  * Stake sizing: NOT computed beyond the offer's own maximum. Sizing below a cap still
    needs the gated staking policy (M24 <- M23 <- M22).

This module reads offers the USER has entered. It does not scrape promotions, does not
enrol in offers, and does not contact any venue. Enrolment is USER_REQUIRED like every
other account action.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import oddsmath as om

HERE = Path(__file__).resolve().parent
PROMOS_PATH = HERE / "promos.json"

PROMO_KINDS = ("odds_boost", "profit_boost", "free_bet", "bonus_back")


@dataclass(frozen=True)
class PromoValue:
    kind: str
    ev_per_unit: float          # expected profit per 1.0 of stake (or of face value, free bets)
    ev_total: float             # at the offer's max stake
    fair_prob: float
    n_books: int
    baseline_ev_per_unit: float # EV of the same wager WITHOUT the promotion
    uplift_per_unit: float      # promo EV minus baseline EV
    basis: str
    assumption: str


def consensus_fair_prob(snapshot, matchup_contains: str, market: str,
                        outcome: str, point: float | None = None):
    """De-vigged consensus probability for one outcome, across every book quoting it.

    Each book's own two-sided market is de-vigged proportionally FIRST, then the fair
    probabilities are averaged across books. De-vigging per book before averaging is the
    correct order: averaging vigged prices first would bake an average margin into the
    result and bias every promo valuation downward.
    """
    key = matchup_contains.lower()

    # SPREADS ARE MIRRORED, TOTALS ARE NOT, AND CONFLATING THEM SILENTLY BREAKS SPREADS.
    # A total's two sides share one number (Over 181.5 / Under 181.5), so matching on
    # equality is right. A spread's sides carry OPPOSITE numbers (-9 / +9), so equality
    # matching finds only one side, the two-sided de-vig never fires, and every spread
    # offer reports "0 books" -- which is what this function did until it was pointed at
    # a real spread.
    def _point_ok(qp) -> bool:
        if point is None or qp is None:
            return point is None
        if market == "spreads":
            return abs(abs(qp) - abs(point)) < 1e-9
        return abs(qp - point) < 1e-9

    rows = [q for q in snapshot.quotes
            if key in q.matchup.lower() and q.market == market and _point_ok(q.point)]
    if not rows:
        return None, 0

    by_book: dict[str, list] = {}
    for q in rows:
        by_book.setdefault(q.book, []).append(q)

    fair = []
    for book, quotes in by_book.items():
        sides = {}
        for q in quotes:
            prev = sides.get(q.outcome)
            if prev is None or abs(q.price) < abs(prev.price):
                sides[q.outcome] = q
        if len(sides) != 2 or outcome not in sides:
            continue
        names = list(sides)
        probs = om.devig_proportional([sides[n].price for n in names])
        fair.append(probs[names.index(outcome)])

    if not fair:
        return None, 0
    return sum(fair) / len(fair), len(fair)


def value_promo(kind: str, fair_prob: float, base_price: float,
                boosted_price: float | None = None, boost_pct: float | None = None,
                max_stake: float = 0.0, free_bet_stake_returned: bool = False,
                bonus_back_recovery: float = 0.70) -> PromoValue:
    """Expected value of one promotional offer.

    kind:
      odds_boost   -- the price itself is improved; `boosted_price` required.
      profit_boost -- profit multiplied by (1 + boost_pct); `boost_pct` required (0.5 = +50%).
      free_bet     -- a stake-not-returned token at `base_price`; EV is on FACE VALUE.
      bonus_back   -- lose and the stake returns as a bonus worth `bonus_back_recovery` of face.
    """
    p = float(fair_prob)
    d_base = om.american_to_decimal(base_price)
    baseline_ev = p * d_base - 1.0     # EV per unit of an ordinary wager at the base price

    if kind == "odds_boost":
        if boosted_price is None:
            raise ValueError("odds_boost requires boosted_price")
        d = om.american_to_decimal(boosted_price)
        ev = p * d - 1.0
        basis = (f"boosted {boosted_price:+g} (decimal {d:.4f}) versus base {base_price:+g} "
                 f"(decimal {d_base:.4f})")

    elif kind == "profit_boost":
        if boost_pct is None:
            raise ValueError("profit_boost requires boost_pct")
        d = 1.0 + (d_base - 1.0) * (1.0 + float(boost_pct))
        ev = p * d - 1.0
        basis = (f"profit boosted {boost_pct * 100:.0f}% on base {base_price:+g}; "
                 f"effective decimal {d:.4f}")

    elif kind == "free_bet":
        # Stake is not at risk and, conventionally, is not returned on a win.
        payout = (d_base - 1.0) if not free_bet_stake_returned else d_base
        ev = p * payout
        baseline_ev = 0.0   # a free bet has no unpromoted counterpart; nothing was risked
        basis = (f"free bet at {base_price:+g}; "
                 f"{'stake returned' if free_bet_stake_returned else 'stake not returned'}. "
                 f"EV is per unit of FACE VALUE, not of your own money at risk")

    elif kind == "bonus_back":
        # Win: profit as normal. Lose: stake back as a bonus worth `bonus_back_recovery`.
        ev = p * (d_base - 1.0) + (1.0 - p) * (-1.0 + float(bonus_back_recovery))
        basis = (f"bonus-back at {base_price:+g}; a losing stake returns as a bonus valued at "
                 f"{bonus_back_recovery * 100:.0f}% of face")

    else:
        raise ValueError(f"unknown promo kind {kind!r}; expected one of {PROMO_KINDS}")

    return PromoValue(
        kind=kind,
        ev_per_unit=round(ev, 6),
        ev_total=round(ev * float(max_stake), 2),
        fair_prob=round(p, 6),
        n_books=0,
        baseline_ev_per_unit=round(baseline_ev, 6),
        uplift_per_unit=round(ev - baseline_ev, 6),
        basis=basis,
        assumption=(
            "Fair probability is the de-vigged cross-book consensus at the snapshot "
            "timestamp, de-vigged per book before averaging. It is an ESTIMATE, so this EV "
            "is an expectation and not a lock. Our own model is deliberately not used."
        ),
    )


def load_offers(path: Path | None = None) -> list[dict]:
    path = Path(path or PROMOS_PATH)
    if not path.is_file():
        return []
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [o for o in doc.get("offers", []) if o.get("enabled", True)]


def evaluate_offers(snapshot, path: Path | None = None) -> list[dict]:
    """Value every user-entered offer that can be matched to a live market."""
    out = []
    for off in load_offers(path):
        p, n_books = consensus_fair_prob(
            snapshot,
            matchup_contains=off["matchup_contains"],
            market=off["market"],
            outcome=off["outcome"],
            point=off.get("point"),
        )
        rec = dict(off)
        if p is None:
            rec["status"] = "UNMATCHED"
            rec["note"] = (
                "No live two-sided market matched this offer, so no consensus probability "
                "exists and the offer cannot be valued. It is listed rather than dropped."
            )
            out.append(rec)
            continue
        v = value_promo(
            kind=off["kind"], fair_prob=p, base_price=off["base_price"],
            boosted_price=off.get("boosted_price"), boost_pct=off.get("boost_pct"),
            max_stake=off.get("max_stake", 0.0),
            free_bet_stake_returned=off.get("free_bet_stake_returned", False),
            bonus_back_recovery=off.get("bonus_back_recovery", 0.70),
        )
        rec["status"] = "VALUED"
        rec["value"] = {**v.__dict__, "n_books": n_books}
        out.append(rec)
    return out
