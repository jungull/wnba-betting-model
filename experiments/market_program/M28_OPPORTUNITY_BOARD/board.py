"""board.py -- detect, classify and rank every actionable opportunity in one place.

This is the node that answers the product question: *of everything available across every
book right now, what would you actually bet, in what order, and how much?*

FOUR RULES THIS MODULE ENFORCES, ALL FROM THE M00 CONTRACT

  1. `arbitrage` names ONE class and one only. Everything else that looks profitable is a
     middle or a dislocation and is labelled that way.

  2. A suggested stake is emitted ONLY where sizing is deterministic arithmetic -- that is,
     for locked arbitrage, where the split follows from the prices and the bankroll with
     no probability estimate anywhere. For every probabilistic class, sizing requires a
     staking policy that is still gated (M24 <- M23 <- M22), and this module returns the
     gate rather than a number it cannot justify.

  3. Nothing here is an executability claim. Opportunities are FLAGS. The capture grid is
     hourly, so a detected arbitrage describes a price that existed somewhere in the last
     hour, and `stale_by_design` records exactly that.

  4. Model-vs-market opportunities are GATED SHUT. S42 reserves any wager-shaped use of a
     fitted score model to the user, and D141 measured the model as behind the market on
     the population books price. The lane exists in the output so the board is honest
     about what it is not showing.
"""
from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass, field, asdict

import oddsmath as om
import promos as _promos
import contract as _contract
import feed as _feed
from oddsmath import Leg

# --------------------------------------------------------------------------------------
# Ranking tiers. Frozen here so a reordering is a visible code change, never a judgement
# call made at render time.
# --------------------------------------------------------------------------------------
TIER_LOCKED = 1        # guaranteed positive in every settlement branch
TIER_SUBSIDISED = 2    # venue-subsidised positive EV, capped by the offer; no edge required
TIER_BOUNDED = 3       # both legs can win; downside bounded by vig, not stake
TIER_INFORMATIONAL = 4 # descriptive; no position implied
TIER_GATED = 9         # cannot be actioned until a named gate clears

TIER_NAMES = {
    TIER_LOCKED: "Locked",
    TIER_SUBSIDISED: "Subsidised",
    TIER_BOUNDED: "Bounded risk",
    TIER_INFORMATIONAL: "Informational",
    TIER_GATED: "Gated",
}

MARKET_NAMES = {"h2h": "Moneyline", "spreads": "Spread", "totals": "Total"}


@dataclass
class Opportunity:
    opp_id: str
    class_id: str              # an M00 opportunity_taxonomy class id
    tier: int
    matchup: str
    commence_time: str
    market: str
    headline: str
    detail: str
    legs: list[dict] = field(default_factory=list)
    rank_score: float = 0.0
    suggested_stake: dict | None = None
    stake_gate: str | None = None
    evidence: str = ""
    caveats: list[str] = field(default_factory=list)
    executability_claimed: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def _leg_dict(leg: Leg, stake: float | None = None) -> dict:
    return {
        "book": leg.book, "outcome": leg.outcome, "price": leg.price,
        "point": leg.point, "last_update": leg.last_update,
        "stake": stake,
    }


# --------------------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------------------


def _by_game_market(quotes, as_of=None, pre_game_only=False):
    """Group quotes by (game, market), optionally dropping games already under way.

    `pre_game_only` exists because in-play quotes generate phantom arbitrage at ~90x the
    pre-game rate (24.56% vs 0.27% measured over 179 snapshots). A price a book has not
    moved off since tip is not an opportunity.
    """
    out = defaultdict(list)
    for q in quotes:
        if pre_game_only and as_of is not None and q.is_in_play(as_of):
            continue
        out[(q.game_id, q.market)].append(q)
    return out


def count_in_play(snapshot) -> int:
    """How many distinct games in this snapshot have already started."""
    return len({q.game_id for q in snapshot.quotes if q.is_in_play(snapshot.captured_at)})


def _best_by_outcome(quotes, point=None):
    """Best (highest decimal) price per outcome name, optionally pinned to a point."""
    best = {}
    for q in quotes:
        if point is not None and q.point != point:
            continue
        cur = best.get(q.outcome)
        if cur is None or om.american_to_decimal(q.price) > om.american_to_decimal(cur.price):
            best[q.outcome] = q
    return best


def _to_leg(q) -> Leg:
    return Leg(book=q.book_title, outcome=q.outcome, price=q.price,
               point=q.point, last_update=q.last_update)


# --------------------------------------------------------------------------------------
# Detector 1 -- TRUE_CROSS_BOOK_ARBITRAGE
# --------------------------------------------------------------------------------------


def detect_arbitrage(snapshot, bankroll: float = 1000.0) -> list[Opportunity]:
    opps: list[Opportunity] = []
    # PRE-GAME ONLY. In-play quotes produce phantom arbitrage at ~90x the pre-game rate.
    groups = _by_game_market(snapshot.quotes, snapshot.captured_at, pre_game_only=True)

    for (game_id, market), quotes in groups.items():
        q0 = quotes[0]
        if market == "h2h":
            best = _best_by_outcome(quotes)
            if len(best) != 2:
                continue
            (n_a, qa), (n_b, qb) = list(best.items())
            if qa.book == qb.book:
                continue
            res = om.arb_two_way(_to_leg(qa), _to_leg(qb), bankroll=bankroll,
                                 push_possible=False)
            if res.is_arb:
                opps.append(_arb_opportunity(q0, market, res, None))
        else:
            points = sorted({q.point for q in quotes if q.point is not None},
                            key=lambda p: abs(p))
            seen_pairs = set()
            for pt in points:
                # Complementary sides carry mirrored points for spreads, identical for totals.
                if market == "totals":
                    sides = _best_by_outcome(quotes, point=pt)
                    if set(sides) != {"Over", "Under"}:
                        continue
                    qa, qb = sides["Over"], sides["Under"]
                    key = ("totals", pt)
                else:
                    at_pt = _best_by_outcome(quotes, point=pt)
                    at_neg = _best_by_outcome(quotes, point=-pt)
                    if not at_pt or not at_neg:
                        continue
                    qa = next(iter(at_pt.values()))
                    qb = next(iter(at_neg.values()))
                    if qa.outcome == qb.outcome:
                        continue
                    key = ("spreads", tuple(sorted([pt, -pt])), qa.outcome, qb.outcome)
                if key in seen_pairs or qa.book == qb.book:
                    continue
                seen_pairs.add(key)
                res = om.arb_two_way(
                    _to_leg(qa), _to_leg(qb), bankroll=bankroll,
                    push_possible=om.can_push(market, pt),
                )
                if res.is_arb:
                    opps.append(_arb_opportunity(q0, market, res, pt))
    return opps


def _arb_opportunity(q0, market, res, point) -> Opportunity:
    a, b = res.legs
    pct = res.worst_case_return * 100.0
    line = f" {point:+g}" if point is not None and market == "spreads" else (
        f" {point:g}" if point is not None else "")
    return Opportunity(
        opp_id=f"ARB-{q0.game_id[:8]}-{market}{('-' + str(point)) if point is not None else ''}",
        class_id="TRUE_CROSS_BOOK_ARBITRAGE",
        tier=TIER_LOCKED,
        matchup=q0.matchup,
        commence_time=q0.commence_time,
        market=MARKET_NAMES.get(market, market) + line,
        headline=f"Locked {pct:.2f}% across {a.book} and {b.book}",
        detail=(
            f"{a.outcome} at {a.price:+g} ({a.book}) against {b.outcome} at "
            f"{b.price:+g} ({b.book}). Implied total {res.total_implied:.4f} < 1."
        ),
        legs=[_leg_dict(a, res.stakes[0]), _leg_dict(b, res.stakes[1])],
        rank_score=res.worst_case_return,
        suggested_stake={
            "kind": "DETERMINISTIC_SPLIT",
            "basis": "deterministic arbitrage split -- no probability estimate involved",
            "total": res.total_stake,
            "legs": [
                {"book": a.book, "outcome": a.outcome, "stake": res.stakes[0]},
                {"book": b.book, "outcome": b.outcome, "stake": res.stakes[1]},
            ],
            "worst_case_profit": res.worst_case_profit,
            "worst_case_return_pct": round(pct, 3),
        },
        evidence="Exact arithmetic on witnessed prices. Not an executability claim.",
        caveats=[
            "Both legs must be struck before either book reprices; otherwise this is a "
            "one-sided position, not an arbitrage.",
            "Stake limits, account restrictions and line availability are unmeasured "
            "(M21/M22 not run on this tape).",
        ],
    )


# --------------------------------------------------------------------------------------
# Detector 2 -- MIDDLES_AND_DISLOCATIONS
# --------------------------------------------------------------------------------------


def detect_middles(snapshot, stake_each: float = 100.0) -> list[Opportunity]:
    opps: list[Opportunity] = []
    groups = _by_game_market(snapshot.quotes, snapshot.captured_at, pre_game_only=True)

    for (game_id, market), quotes in groups.items():
        if market != "totals":
            continue
        q0 = quotes[0]
        overs = [q for q in quotes if q.outcome == "Over" and q.point is not None]
        unders = [q for q in quotes if q.outcome == "Under" and q.point is not None]
        best: dict[tuple[float, float], Opportunity] = {}
        for o, u in itertools.product(overs, unders):
            if o.book == u.book or u.point <= o.point:
                continue
            res = om.middle_totals(_to_leg(o), _to_leg(u), stake_each=stake_each)
            if not res.is_middle:
                continue
            key = (res.window_low, res.window_high)
            cand = Opportunity(
                opp_id=f"MID-{q0.game_id[:8]}-{res.window_low:g}-{res.window_high:g}",
                class_id="MIDDLES_AND_DISLOCATIONS",
                tier=TIER_BOUNDED,
                matchup=q0.matchup,
                commence_time=q0.commence_time,
                market=f"Total {res.window_low:g}–{res.window_high:g}",
                headline=(
                    f"{res.window_width:g}-point middle: both legs win if the total lands "
                    f"between {res.window_low:g} and {res.window_high:g}"
                ),
                detail=(
                    f"Over {o.point:g} at {o.price:+g} ({o.book_title}) with Under "
                    f"{u.point:g} at {u.price:+g} ({u.book_title}). Hit pays "
                    f"{res.profit_if_hit:+.2f} on {stake_each * 2:.0f} staked; miss costs "
                    f"{res.cost_if_missed:+.2f}."
                ),
                legs=[_leg_dict(_to_leg(o), stake_each), _leg_dict(_to_leg(u), stake_each)],
                rank_score=round(res.window_width / max(abs(res.cost_if_missed), 1e-9), 4),
                stake_gate=(
                    "Sizing a middle needs a hit probability this node has not measured "
                    "and a staking policy that is gated: M24_STAKING depends on "
                    "M23_SHADOW_TRADING, which depends on M22_CAPACITY. The equal-stake "
                    "figures above illustrate the payoff shape only."
                ),
                evidence="Arithmetic on witnessed prices. Profit is probabilistic, never locked.",
                caveats=[
                    "This is NOT arbitrage. M00 reserves that word for locked-positive "
                    "combinations only.",
                    ("A whole-number edge can push, returning that leg's stake."
                     if any(res.push_edges) else
                     "Both edges are half-points, so neither leg can push."),
                ],
            )
            prev = best.get(key)
            if prev is None or cand.rank_score > prev.rank_score:
                best[key] = cand
        # Several book pairs produce overlapping windows on the same game. They are real
        # but near-duplicate trades, so the board shows the two most efficient and says
        # how many it folded rather than silently dropping them.
        ranked = sorted(best.values(), key=lambda o: -o.rank_score)
        for extra in ranked[:2]:
            if len(ranked) > 2:
                extra.caveats.append(
                    f"{len(ranked) - 2} further overlapping window(s) on this game were "
                    "folded away; they are variants of the same trade at worse prices.")
        opps.extend(ranked[:2])
    return opps


# --------------------------------------------------------------------------------------
# Detector 3 -- cross-book dispersion (informational)
# --------------------------------------------------------------------------------------


def detect_dispersion(snapshot, min_spread_pct: float = 4.0) -> list[Opportunity]:
    """Where books most disagree. Descriptive: no position is implied."""
    opps: list[Opportunity] = []
    groups = defaultdict(list)
    for q in snapshot.quotes:
        groups[(q.game_id, q.market, q.outcome, q.point)].append(q)

    for (game_id, market, outcome, point), quotes in groups.items():
        if len(quotes) < 3:
            continue
        ordered = sorted(quotes, key=lambda q: om.american_to_decimal(q.price), reverse=True)
        best, worst = ordered[0], ordered[-1]
        spread = (om.american_to_decimal(best.price) / om.american_to_decimal(worst.price) - 1.0) * 100.0
        if spread < min_spread_pct:
            continue
        q0 = quotes[0]
        pt = f" {point:g}" if point is not None else ""
        opps.append(Opportunity(
            opp_id=f"DISP-{game_id[:8]}-{market}-{outcome[:12]}{pt}".replace(" ", ""),
            class_id="PURE_MICROSTRUCTURE",
            tier=TIER_INFORMATIONAL,
            matchup=q0.matchup,
            commence_time=q0.commence_time,
            market=f"{MARKET_NAMES.get(market, market)}{pt} — {outcome}",
            headline=f"{spread:.1f}% price spread across {len(quotes)} books",
            detail=(
                f"Best {best.price:+g} at {best.book_title}; worst {worst.price:+g} at "
                f"{worst.book_title}. Taking the best available price is worth "
                f"{spread:.1f}% in return terms on this outcome alone."
            ),
            legs=[_leg_dict(_to_leg(best)), _leg_dict(_to_leg(worst))],
            rank_score=spread,
            stake_gate="Descriptive only. Line shopping is not a position.",
            evidence="Dispersion is where mispricings live, but dispersion is not itself an edge.",
            caveats=["No claim that either price is wrong is made or implied."],
        ))
    return opps


# --------------------------------------------------------------------------------------
# Detector 4 -- PROMOTIONAL_VALUE (added to the taxonomy by amendment v1 under D144)
# --------------------------------------------------------------------------------------


def detect_promos(snapshot) -> list[Opportunity]:
    """Value the user's own entered offers against de-vigged cross-book consensus.

    Deliberately model-free: the probability comes from the market, so this lane sits
    outside S42 and does not depend on an edge this programme has not demonstrated.
    """
    opps: list[Opportunity] = []
    for rec in _promos.evaluate_offers(snapshot):
        example = rec.get("example_only", False)
        ex_note = ("EXAMPLE OFFER - illustrative terms, not seen at a book. Replace it in "
                   "promos.json.")

        if rec["status"] != "VALUED":
            opps.append(Opportunity(
                opp_id="PROMO-" + rec["id"],
                class_id="PROMOTIONAL_VALUE",
                tier=TIER_SUBSIDISED,
                matchup=rec.get("matchup_contains", "-"),
                commence_time="",
                market=rec.get("market", ""),
                headline=rec.get("label", rec["id"]) + " - could not be valued",
                detail=rec.get("note", ""),
                rank_score=-1.0,
                stake_gate="No live two-sided market matched this offer.",
                evidence="Listed rather than dropped, so a silent match failure stays visible.",
                caveats=[ex_note if example else
                         "Offer terms are as you entered them and are not verified against the venue."],
            ))
            continue

        v = rec["value"]
        ev_pct = v["ev_per_unit"] * 100.0
        cap = float(rec.get("max_stake", 0.0) or 0.0)
        head = "{:+.1f}% expected value".format(ev_pct)
        if cap:
            head += " - ${:+,.2f} at the ${:,.0f} cap".format(v["ev_total"], cap)

        caveats = ([ex_note] if example else [])
        caveats += [
            "This can lose on any single bet - the worst case is the whole stake.",
            "Fair probability is an estimate from market consensus, not a certainty.",
            rec.get("restrictions") or "Check the offer's own restrictions before acting.",
        ]

        opps.append(Opportunity(
            opp_id="PROMO-" + rec["id"],
            class_id="PROMOTIONAL_VALUE",
            tier=TIER_SUBSIDISED,
            matchup=rec.get("matchup_contains", "-"),
            commence_time="",
            market="{} - {}".format(MARKET_NAMES.get(rec["market"], rec["market"]), rec["outcome"]),
            headline=head,
            detail=(
                "{} at {}. {}. Consensus fair probability {:.4f} from {} books; the same "
                "wager unpromoted is {:+.1f}%, so the promotion itself is worth {:+.1f} points."
            ).format(rec.get("label", rec["id"]), rec.get("venue", "your book"), v["basis"],
                     v["fair_prob"], v["n_books"], v["baseline_ev_per_unit"] * 100.0,
                     v["uplift_per_unit"] * 100.0),
            legs=[{"book": rec.get("venue", "your book"), "outcome": rec["outcome"],
                   "price": rec.get("boosted_price") or rec["base_price"],
                   "point": rec.get("point"), "last_update": "", "stake": cap or None}],
            rank_score=v["ev_total"] if cap else v["ev_per_unit"],
            stake_gate=(
                "The figure shown is the OFFER'S OWN CAP, not a sizing recommendation. "
                "Choosing any amount BELOW the cap is a staking decision and is still "
                "governed by the gated policy (M24 <- M23 <- M22). This row is "
                "EV-positive in expectation and can lose in full."),
            suggested_stake={
                "kind": "OFFER_CAP",
                "basis": ("the offer's OWN cap, published by the venue. With positive EV "
                          "per unit and a hard cap, expected value is maximised at the cap "
                          "-- but this is the venue's number, NOT our sizing policy"),
                "total": cap,
                "legs": [{"book": rec.get("venue", "your book"), "outcome": rec["outcome"],
                          "stake": cap}],
                "worst_case_profit": -cap,
                "worst_case_return_pct": -100.0,
            },
            evidence=("Arithmetic on the offer's stated terms plus a de-vigged consensus "
                      "probability. Positive in EXPECTATION, not locked."),
            caveats=caveats,
        ))
    return opps


# --------------------------------------------------------------------------------------
# Gated lanes -- present so the board is honest about what it is NOT showing
# --------------------------------------------------------------------------------------


GATED_LANES = [
    {
        "class_id": "MODEL_VS_MARKET_VALUE",
        "label": "Our model vs the line",
        "gate": "S42_ADOPTION_DECISION (yours) + D141",
        "why": (
            "D141 measured the player-points model at 5.32 MAE against the de-vigged "
            "market's 4.90 on the population books price, and the combination adds "
            "nothing material. There is no measured edge to show, and any wager-shaped "
            "use of a fitted score model is reserved to you regardless."
        ),
    },
    {
        "class_id": "STALE_LINE_DELAYED_REACTION",
        "label": "Stale lines after news",
        "gate": "M08_STALE_WINDOW (parked)",
        "why": (
            "A line is only stale against a fresher quote that was demonstrably "
            "capturable at the same moment. On an hourly grid that comparison cannot be "
            "made, so staleness here would be an artifact of our own cadence rather than "
            "a property of the book."
        ),
    },
    {
        "class_id": "THIRD_PARTY_PROJECTION_VALUE",
        "label": "Vendor projections vs the line",
        "gate": "M02B_VENDOR_PURCHASE_DECISION (yours)",
        "why": "No vendor projection feed is licensed. Purchases are yours alone.",
    },
]


# --------------------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------------------


def _measure_cadence_safe(snapshot) -> dict:
    """Measure the capture grid rather than asserting it.

    The board used to state 'hourly' as a hard-coded fact. Cadence was raised on 2026-08-19,
    which made that sentence false while the page went on printing it. A surface that
    describes its own data must derive that description from the data.
    """
    try:
        c = _feed.measure_cadence(snapshot.data_root, sample=12)
        gap = c.get("median_gap_s")
        return {
            "median_gap_s": gap,
            "median_gap_min": round(gap / 60.0, 1) if gap else None,
            "min_gap_s": c.get("min_gap_s"),
            "n_sampled": c.get("n"),
        }
    except Exception:
        return {"median_gap_s": None, "median_gap_min": None, "min_gap_s": None, "n_sampled": 0}


def build_board(snapshot, bankroll: float = 1000.0, stake_each: float = 100.0) -> dict:
    arbs = detect_arbitrage(snapshot, bankroll=bankroll)
    mids = detect_middles(snapshot, stake_each=stake_each)
    disp = detect_dispersion(snapshot)
    promo = detect_promos(snapshot)

    opportunities = arbs + promo + mids + disp
    # Rank: tier first (locked before bounded before informational), then score within tier.
    opportunities.sort(key=lambda o: (o.tier, -o.rank_score))

    ctr = _contract.load()
    for o in opportunities:
        ctr.require(o.class_id)          # a rendering node may not mint a class

    return {
        "contract_base_sha256": ctr.base_sha256,
        "contract_amendment_version": ctr.amendment_version,
        "snapshot_utc": snapshot.snapshot_utc,
        "captured_at": snapshot.captured_at.isoformat(),
        "age_seconds": round(snapshot.age_seconds, 1),
        "data_root": str(snapshot.data_root.path),
        "data_root_how": snapshot.data_root.how,
        "n_games": snapshot.n_games,
        "n_books": snapshot.n_books,
        "n_quotes": len(snapshot.quotes),
        "n_games_in_play_excluded": count_in_play(snapshot),
        "cadence": _measure_cadence_safe(snapshot),
        "in_play_note": (
            "Games already under way are excluded from the arbitrage and middle "
            "detectors. Measured over 179 snapshots, 24.56% of in-play two-sided markets "
            "show a negative cross-book overround against 0.27% pre-game, so 85.7% of all "
            "apparent arbitrage on this tape is an artefact of books not moving off a "
            "pre-game price after tip. Excluding them is not a silent cap: the count is "
            "reported here."),
        "bankroll": bankroll,
        "counts": {
            "TRUE_CROSS_BOOK_ARBITRAGE": len(arbs),
            "PROMOTIONAL_VALUE": len(promo),
            "MIDDLES_AND_DISLOCATIONS": len(mids),
            "PURE_MICROSTRUCTURE": len(disp),
        },
        "opportunities": [o.as_dict() for o in opportunities],
        "gated_lanes": GATED_LANES,
        "execution_mode": "SHADOW",
        "execution_mode_note": (
            "D024 default and the only mode this node will ever operate in. It generates "
            "flags; it places nothing. Every transition above SHADOW is USER_REQUIRED."
        ),
    }
