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
import consensus_edge as _cedge
import contract as _contract
import feed as _feed
import middle_ev as _mev
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


def _spread_middles(quotes, stake_each: float) -> list[Opportunity]:
    """Straddle a game's MARGIN: take one team at -a and the other at +b with b > a.

    Both bets win when the favourite's margin lands strictly between a and b. Priced with
    the MARGIN dispersion (residual sd 13.05), never the totals dispersion - margins are
    less dispersed, so the breakeven window is 1.56 points rather than 1.80, and borrowing
    the wrong distribution would have made these look worse than they are.
    """
    out: list[Opportunity] = []
    q0 = quotes[0]
    teams = {q.outcome for q in quotes}
    if len(teams) != 2:
        return out
    best: dict[tuple, Opportunity] = {}
    for a, b in itertools.product(quotes, quotes):
        if a.outcome == b.outcome or a.book == b.book:
            continue
        if a.point is None or b.point is None or a.point >= 0:
            continue
        lo, hi = -a.point, b.point          # favourite laying `lo`, dog getting `hi`
        if hi <= lo:
            continue
        width = round(hi - lo, 2)
        ev = _mev.evaluate(width, om.american_to_decimal(a.price),
                           om.american_to_decimal(b.price),
                           stake_each=stake_each, market="spreads",
                           push_points=[lo, hi])
        cand = Opportunity(
            opp_id=f"MIDS-{q0.game_id[:8]}-{lo:g}-{hi:g}",
            class_id="MIDDLES_AND_DISLOCATIONS",
            tier=TIER_BOUNDED,
            matchup=q0.matchup,
            commence_time=q0.commence_time,
            market=f"Spread {lo:g}-{hi:g}",
            headline=(f"{'+EV' if ev.is_positive else 'NEGATIVE EV'}: {ev.ev:+.2f} expected on "
                      f"{stake_each * 2:.0f} staked ({width:g}-point margin window, hits "
                      f"~{ev.p_hit * 100:.1f}% vs {ev.breakeven_p * 100:.1f}% needed)"),
            detail=(f"{a.outcome} {a.point:+g} at {a.price:+g} ({a.book_title}) with "
                    f"{b.outcome} {b.point:+g} at {b.price:+g} ({b.book_title}). Both win if "
                    f"{a.outcome} wins by more than {lo:g} and fewer than {hi:g}."),
            legs=[_leg_dict(_to_leg(a), stake_each), _leg_dict(_to_leg(b), stake_each)],
            rank_score=round(ev.ev, 4),
            stake_gate=("The hit probability is MODELLED from margin dispersion; sizing remains "
                        "gated (M24 <- M23 <- M22). Equal stakes illustrate payoff shape only."),
            evidence=(f"Prices are arithmetic on witnessed quotes; the hit rate is a MODEL. "
                      f"{ev.basis}. Breakeven window at these prices: {ev.breakeven_window:g} pts."),
            caveats=[
                ("NEGATIVE EXPECTATION at these prices -- the window is narrower than the "
                 f"{ev.breakeven_window:g}-point breakeven."
                 if not ev.is_positive else
                 f"Positive expectation, but the hit rate ({ev.p_hit * 100:.1f}%) is a MODEL."),
                ev.caveat,
                "This is NOT arbitrage. M00 reserves that word for locked-positive combinations.",
                "Priced on MARGIN dispersion, not totals dispersion -- they are different.",
            ] + ([
                # This started life as a caveat claiming the push branch was too small to
                # matter. Measuring it showed otherwise -- WNBA margins pile up on the low
                # key numbers -- so it is now PRICED rather than disclaimed.
                f"A leg sits on a whole number, so an exact margin refunds it and wins the "
                f"other: worth {ev.p_push * 100:.1f}pp, already included. Without it this "
                f"middle would score {ev.ev_no_push:+.2f}."
            ] if ev.p_push > 0 else []),
        )
        key = (lo, hi)
        prev = best.get(key)
        if prev is None or cand.rank_score > prev.rank_score:
            best[key] = cand
    ranked = sorted(best.values(), key=lambda o: -o.rank_score)
    return ranked[:2]


def detect_middles(snapshot, stake_each: float = 100.0) -> list[Opportunity]:
    opps: list[Opportunity] = []
    groups = _by_game_market(snapshot.quotes, snapshot.captured_at, pre_game_only=True)

    for (game_id, market), quotes in groups.items():
        if market == "spreads":
            opps.extend(_spread_middles(quotes, stake_each))
            continue
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
            # EVERY MIDDLE NOW CARRIES AN EXPECTED VALUE. M10_MIDDLES built the scanner and
            # recorded in its own limitations that it computed no probability model, so every
            # middle this programme ever surfaced was shown without the number that decides
            # whether to take it. At -110/-110 the breakeven window is 1.81 points, so a
            # 1.0- or 1.5-point middle -- the majority this board was surfacing -- is
            # NEGATIVE expectation.
            ev = _mev.evaluate(res.window_width,
                               om.american_to_decimal(o.price),
                               om.american_to_decimal(u.price),
                               stake_each=stake_each,
                               push_points=[o.point, u.point])
            key = (res.window_low, res.window_high)
            cand = Opportunity(
                opp_id=f"MID-{q0.game_id[:8]}-{res.window_low:g}-{res.window_high:g}",
                class_id="MIDDLES_AND_DISLOCATIONS",
                tier=TIER_BOUNDED,
                matchup=q0.matchup,
                commence_time=q0.commence_time,
                market=f"Total {res.window_low:g}–{res.window_high:g}",
                headline=(
                    f"{'+EV' if ev.is_positive else 'NEGATIVE EV'}: "
                    f"{ev.ev:+.2f} expected on {stake_each * 2:.0f} staked "
                    f"({res.window_width:g}-point window, hits ~{ev.p_hit * 100:.1f}% vs "
                    f"{ev.breakeven_p * 100:.1f}% needed)"
                ),
                detail=(
                    f"Over {o.point:g} at {o.price:+g} ({o.book_title}) with Under "
                    f"{u.point:g} at {u.price:+g} ({u.book_title}). Hit pays "
                    f"{res.profit_if_hit:+.2f} on {stake_each * 2:.0f} staked; miss costs "
                    f"{res.cost_if_missed:+.2f}."
                ),
                legs=[_leg_dict(_to_leg(o), stake_each), _leg_dict(_to_leg(u), stake_each)],
                rank_score=round(ev.ev, 4),
                stake_gate=(
                    "The hit probability is now MODELLED (see middle_ev.py) but sizing is "
                    "still gated: M24_STAKING depends on M23_SHADOW_TRADING, which depends "
                    "on M22_CAPACITY. Equal stakes are shown to illustrate the payoff shape, "
                    "not as a recommended size."
                ),
                evidence=(
                    f"Prices are arithmetic on witnessed quotes; the hit probability is a "
                    f"MODEL. {ev.basis}. Breakeven window at these prices: "
                    f"{ev.breakeven_window:g} points."
                ),
                caveats=[
                    ("NEGATIVE EXPECTATION at these prices -- the window is narrower than the "
                     f"{ev.breakeven_window:g}-point breakeven. Shown rather than hidden so the "
                     "omission is not silent."
                     if not ev.is_positive else
                     f"Positive expectation, but the edge is thin and the hit rate "
                     f"({ev.p_hit * 100:.1f}%) is a MODEL, not a measurement."),
                    ev.caveat,
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
# Best-price table -- line shopping made operational
# --------------------------------------------------------------------------------------


def best_price_table(snapshot, min_books: int = 3) -> list[dict]:
    """For every pre-game market, WHERE to bet each side and what shopping is worth.

    Line shopping is the only thing this programme has measured that is simultaneously
    real, free and requires no opinion about a game: taking the best available price on
    each side removes a median 24.3% of the vig (4.758% -> 3.600% overround, 1.157 points
    removed) across 4,460 two-sided markets (D155, correcting D151's 26.8%, which had been
    computed on a sample that silently excluded every spread).

    M29/D157 puts the same thing on a returns footing: betting blind loses 4.43% a stake,
    and always taking the best of eleven books still loses 2.05%. Shopping is necessary and
    is nowhere near sufficient.

    That finding was a statistic. This turns it into an instruction: the book to use, the
    price it is offering, and how much better that is than betting at a typical book. It is
    NOT a recommendation to bet -- it is a statement that IF you are betting this side, this
    is where.
    """
    rows: list[dict] = []
    groups: dict = defaultdict(lambda: defaultdict(list))
    for q in snapshot.quotes:
        if q.is_in_play(snapshot.captured_at):
            continue
        # SPREADS PAIR ON MAGNITUDE, EVERYTHING ELSE ON THE NUMBER ITSELF.
        # A total's two sides share one number (Over 181.5 / Under 181.5). A spread's sides
        # carry OPPOSITE numbers (-8.5 / +8.5), so keying on the signed point puts each side
        # in its own group, no group ever has two outcomes, and EVERY SPREAD IS SILENTLY
        # DROPPED. That is what this table did until it was audited: 98 spread quotes across
        # 5 games produced 0 rows, on a market where line shopping matters as much as any
        # other.
        key_point = abs(q.point) if (q.market == "spreads" and q.point is not None) else q.point
        groups[(q.game_id, q.market, key_point)][q.outcome].append(q)

    for (game_id, market, point), sides in groups.items():
        if len(sides) != 2:
            continue
        if min(len(v) for v in sides.values()) < min_books:
            continue
        q0 = next(iter(sides.values()))[0]
        entry = {
            "matchup": q0.matchup,
            "commence_time": q0.commence_time,
            "market": MARKET_NAMES.get(market, market),
            "point": point,
            "sides": [],
        }
        shop_gain = []
        for outcome, quotes in sides.items():
            decs = sorted(((om.american_to_decimal(q.price), q) for q in quotes),
                          key=lambda t: -t[0])
            best_dec, best_q = decs[0]
            mid = decs[len(decs) // 2][0]
            worst_dec = decs[-1][0]
            gain_vs_median = (best_dec / mid - 1.0) * 100.0
            shop_gain.append(gain_vs_median)
            entry["sides"].append({
                "outcome": outcome,
                # EACH SIDE CARRIES ITS OWN SIGNED LINE. The group is keyed on magnitude so
                # mirrored spreads pair at all, but "Spread 8.5" alone does not tell a reader
                # which team is -8.5 and which is +8.5 -- and a table whose job is to say
                # where to bet must not be ambiguous about WHAT to bet.
                "point": best_q.point,
                "best_book": best_q.book_title,
                "best_price": best_q.price,
                "n_books": len(quotes),
                "median_price": om.decimal_to_american(mid),
                "worst_price": om.decimal_to_american(worst_dec),
                "gain_vs_median_pct": round(gain_vs_median, 3),
                "gain_vs_worst_pct": round((best_dec / worst_dec - 1.0) * 100.0, 3),
            })
        entry["mean_gain_vs_median_pct"] = round(sum(shop_gain) / len(shop_gain), 3)
        # Overround at best prices vs at the median book, for this market.
        best_probs = [1.0 / om.american_to_decimal(sd["best_price"]) for sd in entry["sides"]]
        med_probs = [1.0 / om.american_to_decimal(sd["median_price"]) for sd in entry["sides"]]
        entry["overround_best_pct"] = round((sum(best_probs) - 1.0) * 100.0, 3)
        entry["overround_median_pct"] = round((sum(med_probs) - 1.0) * 100.0, 3)
        entry["vig_removed_pct"] = round(entry["overround_median_pct"]
                                         - entry["overround_best_pct"], 3)
        rows.append(entry)

    rows.sort(key=lambda r: -r["vig_removed_pct"])
    return rows


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


def detect_stale_lines(snapshot) -> list[Opportunity]:
    """Quotes that beat the de-vigged consensus of their peers, graded by how dislocated.

    This is the first lane on this board carrying a positive-expectation claim, and the
    claim rests on a measurement rather than on a forecast. M29/D157 asked who moves when a
    book disagrees with its peers, and found the OUTLIER does essentially all of the moving:
    a >=1.5pp dislocation closes 0.491pp [0.426,0.574] over an hour, of which only
    0.131pp [-0.047,0.235] is consensus drifting toward the outlier. No book leads. That
    makes peer consensus the attractor, and therefore the right thing to price against.

    What it is NOT is a claim about truth. Consensus is where prices settle, not a referee.
    If the whole market is wrong about a game, this lane cannot see it and would score the
    one correct book as the mistake. Every number below is closing-line value against the
    market's own settling point.

    No scoring model is involved anywhere, so this lane is untouched by S42 and by
    D141/D150's finding that our model trails the market.
    """
    opps: list[Opportunity] = []
    for d in _cedge.find_dislocations(snapshot):
        pt = f" {d.point:+g}" if d.point is not None and d.market == "spreads" else (
            f" {d.point:g}" if d.point is not None else "")
        strong = d.grade == "ACT"
        opps.append(Opportunity(
            opp_id=f"STALE-{d.game_id[:8]}-{d.market}-{d.book}-{d.outcome[:10]}".replace(" ", ""),
            class_id="STALE_LINE_DELAYED_REACTION",
            tier=TIER_BOUNDED if strong else TIER_INFORMATIONAL,
            matchup=d.matchup,
            commence_time=d.commence_time,
            market=f"{MARKET_NAMES.get(d.market, d.market)}{pt} — {d.outcome}",
            headline=(f"[{d.grade}] {d.book_title} pays {d.price:+g}, worth {d.edge * 100:+.2f}% "
                      f"against the other {d.n_peers} books' de-vigged consensus"),
            detail=(f"{d.book_title} implies {d.p_devig * 100:.1f}% for this side; the median "
                    f"of the other {d.n_peers} books implies {d.consensus * 100:.1f}%. That is "
                    f"{d.opinion_gap * 100:.2f} points of disagreement, and after "
                    f"{d.book_title}'s own vig it leaves {d.edge * 100:+.2f}% per unit staked "
                    f"if the consensus is fair."),
            legs=[{"book": d.book, "outcome": d.outcome, "price": d.price,
                   "point": d.point, "last_update": d.last_update, "stake": None}],
            rank_score=round(d.edge * 100, 4),
            stake_gate=("Sizing stays gated (M24 <- M23 <- M22). A measured edge is not a "
                        "staking policy, and this lane emits no number."),
            evidence=_cedge.PROVENANCE,
            caveats=([
                "Measured against the OTHER BOOKS' opinion, not against truth. If the market "
                "is collectively wrong, this scores the correct book as the error.",
                "SHADOW mode. Nothing is placed, no venue is contacted, no account is held.",
            ] + ([
                f"Graded ACT: at least {_cedge.ACT_PP * 100:g}pp of dislocation, the band where "
                f"M29 measured +1.44% live and +2.74% in a reserved replication."]
                if strong else [
                f"Graded {d.grade}: the return looks large but rests on only "
                f"{d.opinion_gap * 100:.2f}pp of disagreement. At long-shot prices a small "
                f"probability difference becomes a big percentage, and the consensus estimate "
                f"is proportionally noisier there. M29 measured a reliable return only at "
                f"{_cedge.ACT_PP * 100:g}pp and above."])),
        ))
    return opps


def build_board(snapshot, bankroll: float = 1000.0, stake_each: float = 100.0) -> dict:
    arbs = detect_arbitrage(snapshot, bankroll=bankroll)
    mids = detect_middles(snapshot, stake_each=stake_each)
    disp = detect_dispersion(snapshot)
    promo = detect_promos(snapshot)
    stale = detect_stale_lines(snapshot)

    opportunities = arbs + promo + stale + mids + disp
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
            "STALE_LINE_DELAYED_REACTION": len(stale),
        },
        "stale_line_note": (
            "The only lane on this board carrying a positive-expectation claim. It flags a "
            "quote that beats the de-vigged median of the other books after that book's own "
            "vig. M29/D157 measured this on 54,524 live quotes and a reserved 66,967-quote "
            "replication: 1.18% of quotes qualify in BOTH samples, worth +1.68% and +2.24%. "
            "Grades: ACT means at least 3pp of dislocation, where the measured return was "
            "+1.44% live and +2.74% replicated. Anything less is shown but not recommended. "
            "The comparison is against the market's own settling point, never against truth."),
        "opportunities": [o.as_dict() for o in opportunities],
        "best_prices": best_price_table(snapshot),
        "best_prices_note": (
            "Where to bet each side IF you are betting it. Taking the best available price "
            "removes a median 24.3% of the vig (D155) -- free, mechanical, and requiring no "
            "opinion about any game. It is not enough on its own: M29/D157 measured that "
            "always taking the best of eleven books still returns -2.05% a stake against "
            "-4.43% for betting blind. This is not a recommendation to bet."),
        "gated_lanes": GATED_LANES,
        "execution_mode": "SHADOW",
        "execution_mode_note": (
            "D024 default and the only mode this node will ever operate in. It generates "
            "flags; it places nothing. Every transition above SHADOW is USER_REQUIRED."
        ),
    }
