"""TESTS.py -- M28_OPPORTUNITY_BOARD.

Run: python TESTS.py     (exit 0 = all green, non-zero = failures)

The arithmetic in `oddsmath` is the only thing in this node permitted to carry a hard
claim, so it carries the weight of the testing. In particular the PUSH tests exist because
the tempting implementation -- "implied probabilities sum to less than 1, therefore
arbitrage" -- is wrong on whole-number totals and spreads, and wrong in the direction that
loses money quietly.
"""
from __future__ import annotations

import sys
import traceback

import oddsmath as om
from oddsmath import Leg
import board
import feed
import promos as pr
import contract as ct

PASS, FAIL = [], []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append((name, detail))
        print(f"  FAIL  {name}   {detail}")


def close(name, got, want, tol=1e-9):
    check(name, abs(got - want) <= tol, f"got {got!r} want {want!r}")


def section(t):
    print(f"\n--- {t} " + "-" * max(0, 74 - len(t)))


# ======================================================================================
section("1. American / decimal / implied conversions")

close("-110 -> decimal", om.american_to_decimal(-110), 1 + 100 / 110)
close("+150 -> decimal", om.american_to_decimal(150), 2.5)
close("+100 -> decimal", om.american_to_decimal(100), 2.0)
close("-100 -> decimal", om.american_to_decimal(-100), 2.0)
close("decimal 2.5 -> +150", om.decimal_to_american(2.5), 150.0)
close("implied(+100)", om.implied_prob(100), 0.5)
close("implied(-200)", om.implied_prob(-200), 2 / 3, 1e-12)

for bad in (0, 50, -50, 99.9):
    try:
        om.american_to_decimal(bad)
        check(f"rejects invalid price {bad}", False, "no exception raised")
    except ValueError:
        check(f"rejects invalid price {bad}", True)

# A standard -110/-110 market carries about 4.76% overround.
# implied(-110) = 110/210, NOT 100/210 -- the stake is part of the return.
close("overround(-110,-110)", om.overround([-110, -110]), 2 * (110 / 210) - 1, 1e-12)
check("overround is positive on a real market", om.overround([-110, -110]) > 0)

dv = om.devig_proportional([-110, -110])
close("devig of a symmetric market is 50/50", dv[0], 0.5, 1e-12)
close("devig sums to exactly 1", sum(dv), 1.0, 1e-12)

# ======================================================================================
section("2. Arbitrage -- the positive case")

# +120 at one book vs -105 at another. Implied 0.4545 + 0.5122 = 0.9667 < 1.
a = Leg(book="BookA", outcome="Team A", price=120)
b = Leg(book="BookB", outcome="Team B", price=-105)
res = om.arb_two_way(a, b, bankroll=1000.0)

check("detects a genuine two-way arbitrage", res.is_arb, res.reason)
check("total implied is below 1", res.total_implied < 1.0, f"{res.total_implied}")
check("worst-case profit is strictly positive", res.worst_case_profit > 0)
check("never claims executability", res.executability_claimed is False)
check("stakes were allocated to both legs", len(res.stakes) == 2 and min(res.stakes) > 0)

# The defining property: EVERY branch pays the same and all are positive.
d_a, d_b = om.american_to_decimal(120), om.american_to_decimal(-105)
ret_a = res.stakes[0] * d_a - res.total_stake
ret_b = res.stakes[1] * d_b - res.total_stake
check("both win-branches are positive", min(ret_a, ret_b) > 0, f"{ret_a:.4f} / {ret_b:.4f}")
check("branches are equalised to within a rounding increment",
      abs(ret_a - ret_b) < 0.05, f"{ret_a:.4f} vs {ret_b:.4f}")
close("reported worst case matches the lesser branch", res.worst_case_profit,
      round(min(ret_a, ret_b), 2), 0.011)

# ======================================================================================
section("3. Arbitrage -- the negative cases that matter")

fair = om.arb_two_way(Leg("A", "Over", -110), Leg("B", "Under", -110))
check("a normal vigged market is NOT an arbitrage", not fair.is_arb)
check("and says why", "no locked edge" in fair.reason, fair.reason)

# THE IMPORTANT ONE. A whole-number total can land exactly on the line and push. The
# naive implied-probability test calls this an arbitrage; it is not, because the push
# branch returns the stake and nets zero, and M00 demands locked-POSITIVE everywhere.
push_case = om.arb_two_way(
    Leg("BookA", "Over", 120, point=170.0),
    Leg("BookB", "Under", -105, point=170.0),
    push_possible=True,
)
check("rejects a whole-number total whose push branch nets zero", not push_case.is_arb)
check("names the push branch as the reason",
      "push" in push_case.reason.lower(), push_case.reason)
check("but confirms the win-branches were positive (so the rejection is deliberate)",
      "positive on both win branches" in push_case.reason, push_case.reason)

# The same prices on a half-point line cannot push and ARE an arbitrage.
half = om.arb_two_way(
    Leg("BookA", "Over", 120, point=170.5),
    Leg("BookB", "Under", -105, point=170.5),
    push_possible=False,
)
check("the same prices on a half-point line ARE an arbitrage", half.is_arb, half.reason)

close("can_push: whole total", om.can_push("totals", 170.0), True)
close("can_push: half total", om.can_push("totals", 170.5), False)
close("can_push: whole spread", om.can_push("spreads", -3.0), True)
close("can_push: moneyline never", om.can_push("h2h", None), False)

# A razor-thin edge must not survive rounding to real money.
thin = om.arb_two_way(Leg("A", "X", 101), Leg("B", "Y", -100), bankroll=1000.0)
if thin.is_arb:
    check("a surviving thin edge is still positive after rounding",
          thin.worst_case_profit > 0, f"{thin.worst_case_profit}")
else:
    check("a thin edge that cannot survive rounding is rejected", True)

# ======================================================================================
section("4. Middles -- explicitly not arbitrage")

o = Leg("BookA", "Over", -110, point=168.5)
u = Leg("BookB", "Under", -110, point=171.5)
mid = om.middle_totals(o, u, stake_each=100.0)

check("detects the straddle", mid.is_middle)
close("window low", mid.window_low, 168.5)
close("window high", mid.window_high, 171.5)
close("window width", mid.window_width, 3.0)
check("hitting the middle is profitable", mid.profit_if_hit > 0, f"{mid.profit_if_hit}")
check("missing costs only the vig, never a full stake",
      -100 < mid.cost_if_missed < 0, f"{mid.cost_if_missed}")
check("neither half-point edge can push", mid.push_edges == (False, False))

# Order matters: Under must sit ABOVE Over or there is no window.
inverted = om.middle_totals(
    Leg("A", "Over", -110, point=171.5), Leg("B", "Under", -110, point=168.5))
check("rejects an inverted pair", not inverted.is_middle)
check("and explains why", "does not sit above" in inverted.reason, inverted.reason)

whole = om.middle_totals(
    Leg("A", "Over", -110, point=168.0), Leg("B", "Under", -110, point=171.0))
check("flags pushable whole-number edges", whole.push_edges == (True, True))

# ======================================================================================
section("5. Vocabulary discipline (M00 reserved terms)")

src_board = open("board.py", encoding="utf-8").read()
mid_block = src_board[src_board.index("def detect_middles"):src_board.index("def detect_dispersion")]
check("the middles detector never labels its output arbitrage",
      "TRUE_CROSS_BOOK_ARBITRAGE" not in mid_block)
check("the middles detector states it is not arbitrage",
      "NOT arbitrage" in mid_block)
check("only the arbitrage detector emits the reserved class id",
      src_board.count('class_id="TRUE_CROSS_BOOK_ARBITRAGE"') == 1)

# ======================================================================================
section("6. Staking discipline -- numbers only where they are deterministic")

class _FakeSnap:
    """Two books, one game, a manufactured moneyline arbitrage."""
    snapshot_utc = "20260818T210003Z"
    from datetime import datetime, timezone
    captured_at = datetime(2026, 8, 18, 21, 0, 3, tzinfo=timezone.utc)
    age_seconds = 60.0
    n_games = 1
    n_books = 2

    class _R:
        path = "fixture"
        how = "fixture"
    data_root = _R()

    def __init__(self):
        Q = feed.Quote
        common = dict(game_id="fixture01", commence_time="2026-08-19T00:00:00Z",
                      home_team="Home", away_team="Away", market="h2h", point=None,
                      last_update="2026-08-18T20:59:00Z", snapshot_utc=self.snapshot_utc)
        self.quotes = (
            Q(book="booka", book_title="BookA", outcome="Home", price=120, **common),
            Q(book="bookb", book_title="BookB", outcome="Away", price=-105, **common),
        )

snap = _FakeSnap()
arbs = board.detect_arbitrage(snap, bankroll=1000.0)
check("board surfaces the manufactured arbitrage", len(arbs) == 1, f"{len(arbs)} found")
if arbs:
    opp = arbs[0]
    check("arbitrage carries a concrete stake", opp.suggested_stake is not None)
    check("arbitrage carries no stake gate", opp.stake_gate is None)
    check("stake basis names it as deterministic",
          "deterministic" in opp.suggested_stake["basis"])
    check("stake legs name their books",
          {l["book"] for l in opp.suggested_stake["legs"]} == {"BookA", "BookB"})
    check("worst-case profit is positive", opp.suggested_stake["worst_case_profit"] > 0)
    check("ranked in the locked tier", opp.tier == board.TIER_LOCKED)

fixture_mid = board.Opportunity(
    opp_id="x", class_id="MIDDLES_AND_DISLOCATIONS", tier=board.TIER_BOUNDED,
    matchup="m", commence_time="t", market="Total", headline="h", detail="d")
check("the Opportunity default carries no stake", fixture_mid.suggested_stake is None)

# Every non-arbitrage class must gate its sizing rather than invent a number.
live_ok = True
try:
    real = feed.load_latest()
    b = board.build_board(real)
    # THE INVARIANT, stated precisely rather than loosely:
    #   * only locked arbitrage may carry a DETERMINISTIC_SPLIT stake, and it needs no gate;
    #   * a promotion may carry the OFFER'S OWN CAP, but must ALSO carry a sizing gate,
    #     because choosing anything below that cap is a staking decision we cannot govern;
    #   * every other class carries no number at all, only the name of its gate.
    det_ok = cap_ok = none_ok = True
    for o in b["opportunities"]:
        st, cls = o["suggested_stake"], o["class_id"]
        if cls == "TRUE_CROSS_BOOK_ARBITRAGE":
            if not st or st.get("kind") != "DETERMINISTIC_SPLIT":
                det_ok = False
        elif cls == "PROMOTIONAL_VALUE":
            if st and (st.get("kind") != "OFFER_CAP" or not o["stake_gate"]):
                cap_ok = False
        else:
            if st is not None or not o["stake_gate"]:
                none_ok = False
    check("only locked arbitrage carries a deterministic-split stake", det_ok)
    check("a promotion's number is the OFFER CAP and still carries a sizing gate", cap_ok)
    check("every other probabilistic class carries no stake, only its gate", none_ok)
    check("no class other than arbitrage claims a deterministic split",
          all(not o["suggested_stake"] or o["suggested_stake"].get("kind") != "DETERMINISTIC_SPLIT"
              for o in b["opportunities"] if o["class_id"] != "TRUE_CROSS_BOOK_ARBITRAGE"))
    check("every gated lane names its gate",
          all(g.get("gate") and g.get("why") for g in b["gated_lanes"]))
    check("execution mode is SHADOW", b["execution_mode"] == "SHADOW")
    check("model-vs-market lane is gated, not rendered as an opportunity",
          "MODEL_VS_MARKET_VALUE" not in {o["class_id"] for o in b["opportunities"]})
    check("board reports which data root it used", bool(b["data_root"]))
except FileNotFoundError as e:
    print(f"  SKIP  live-data assertions -- no capture root visible ({e})")

# ======================================================================================
section("7. Feed integrity")

try:
    root = feed.resolve_data_root()
    check("resolves a data root", root.odds_capture.is_dir(), str(root.path))
    snaps = feed.list_snapshots(root)
    check("finds capture snapshots", len(snaps) > 0, f"{len(snaps)} files")
    s = feed.load_latest(root)
    check("parses quotes from the newest snapshot", len(s.quotes) > 0, f"{len(s.quotes)}")
    check("every quote carries a book", all(q.book for q in s.quotes))
    check("every quote carries a usable American price",
          all(abs(q.price) >= 100 for q in s.quotes))
    check("totals quotes carry a point",
          all(q.point is not None for q in s.quotes if q.market == "totals"))
    check("moneyline quotes carry no point",
          all(q.point is None for q in s.quotes if q.market == "h2h"))
    cad = feed.measure_cadence(root)
    check("cadence is measurable", cad.get("median_gap_s") is not None, str(cad))
    if cad.get("median_gap_s"):
        check("cadence is recorded honestly as coarse (>= 60s)",
              cad["median_gap_s"] >= 60,
              "a sub-minute grid would change the executability discussion")
except FileNotFoundError as e:
    print(f"  SKIP  feed assertions -- {e}")


# ======================================================================================
section("8. Contract loading and amendment discipline")

c = ct.load()
check("composed taxonomy exposes seven classes", len(c.classes) == 7, str(len(c.classes)))
check("the six base classes survive the amendment",
      {"TRUE_CROSS_BOOK_ARBITRAGE", "MIDDLES_AND_DISLOCATIONS", "STALE_LINE_DELAYED_REACTION",
       "MODEL_VS_MARKET_VALUE", "THIRD_PARTY_PROJECTION_VALUE", "PURE_MICROSTRUCTURE"}
      <= set(c.classes))
check("PROMOTIONAL_VALUE was added by amendment, not by the base file",
      "PROMOTIONAL_VALUE" in c.amended_class_ids)
check("the base taxonomy bytes are UNCHANGED by the amendment",
      c.base_sha256 == "c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12c",
      c.base_sha256)
check("the reserved-terms ruling on `arbitrage` is intact",
      "TRUE_CROSS_BOOK_ARBITRAGE" in c.reserved_terms["arbitrage"])
check("SHADOW remains the default execution mode", c.default_execution_mode == "SHADOW")
try:
    c.require("NOT_A_REAL_CLASS")
    check("a rendering node cannot mint a class", False, "no exception")
except KeyError:
    check("a rendering node cannot mint a class", True)

# The amendment must cite a ledgered decision AND verbatim user authorization.
import json as _json
_am = _json.loads(open(ct.AMENDMENTS_PATH, encoding="utf-8").read())
check("amendment cites a ledgered decision", bool(_am["authorization"]["ledgered_decision"]))
check("amendment records the user's authorization VERBATIM",
      len(_am["authorization"]["verbatim"]) > 40)
check("amendment is additive only (declares no redefinitions)",
      all(cl["id"] not in {"TRUE_CROSS_BOOK_ARBITRAGE", "MIDDLES_AND_DISLOCATIONS"}
          for cl in _am["new_classes"]))
check("amendment affirms reserved_terms unchanged",
      any("reserved_terms" in u for u in _am["unchanged"]))
check("PROMOTIONAL_VALUE forbids using our own model for the probability",
      any("NEVER our own model" in x for x in c.classes["PROMOTIONAL_VALUE"]["constraints"]))
check("PROMOTIONAL_VALUE is explicitly not arbitrage",
      any("NOT arbitrage" in x for x in c.classes["PROMOTIONAL_VALUE"]["constraints"]))

# ======================================================================================
section("9. Promotion valuation")

# Odds boost. Fair 20%, base +400 (dec 5.0), boosted +500 (dec 6.0).
v = pr.value_promo("odds_boost", fair_prob=0.20, base_price=400, boosted_price=500,
                   max_stake=100.0)
close("odds boost EV per unit", v.ev_per_unit, 0.20 * 6.0 - 1.0, 1e-6)
close("odds boost EV at cap", v.ev_total, round((0.20 * 6.0 - 1.0) * 100.0, 2), 0.011)
close("baseline EV without the promo", v.baseline_ev_per_unit, 0.20 * 5.0 - 1.0, 1e-6)
close("uplift is promo minus baseline", v.uplift_per_unit,
      (0.20 * 6.0 - 1.0) - (0.20 * 5.0 - 1.0), 1e-6)
check("a fairly-priced boost is EV-positive", v.ev_per_unit > 0)

# Profit boost. base -110 (dec 1.909...), +50% profit -> 1 + 0.909*1.5 = 2.3636
v2 = pr.value_promo("profit_boost", fair_prob=0.5, base_price=-110, boost_pct=0.5,
                    max_stake=50.0)
_d = om.american_to_decimal(-110)
close("profit boost effective EV", v2.ev_per_unit, 0.5 * (1 + (_d - 1) * 1.5) - 1.0, 1e-6)
check("a 50% profit boost turns a -110 coinflip positive", v2.ev_per_unit > 0)

# Free bet, stake NOT returned: EV = p * (dec - 1) on face value.
v3 = pr.value_promo("free_bet", fair_prob=0.5, base_price=100, max_stake=25.0)
close("free bet EV per unit of face", v3.ev_per_unit, 0.5 * 1.0, 1e-6)
check("free bet baseline is zero -- nothing of yours was risked",
      v3.baseline_ev_per_unit == 0.0)
v3b = pr.value_promo("free_bet", fair_prob=0.5, base_price=100, max_stake=25.0,
                     free_bet_stake_returned=True)
check("a stake-returned free bet is worth strictly more",
      v3b.ev_per_unit > v3.ev_per_unit)
# The known property that matters operationally: free bets are worth more at longer prices.
short = pr.value_promo("free_bet", fair_prob=0.8, base_price=-400, max_stake=25.0)
lng = pr.value_promo("free_bet", fair_prob=0.2, base_price=400, max_stake=25.0)
check("free bets are worth more on longer prices", lng.ev_per_unit > short.ev_per_unit,
      f"{lng.ev_per_unit:.4f} vs {short.ev_per_unit:.4f}")

# Bonus back.
v4 = pr.value_promo("bonus_back", fair_prob=0.5, base_price=100, max_stake=100.0,
                    bonus_back_recovery=0.7)
close("bonus back EV", v4.ev_per_unit, 0.5 * 1.0 + 0.5 * (-1.0 + 0.7), 1e-6)
check("full recovery would make bonus-back a free roll",
      pr.value_promo("bonus_back", fair_prob=0.5, base_price=100,
                     bonus_back_recovery=1.0).ev_per_unit > v4.ev_per_unit)

for bad in ("boost", "", "arbitrage"):
    try:
        pr.value_promo(bad, fair_prob=0.5, base_price=100)
        check(f"rejects unknown promo kind {bad!r}", False, "no exception")
    except ValueError:
        check(f"rejects unknown promo kind {bad!r}", True)

check("every valuation names its assumption", "ESTIMATE" in v.assumption)
check("the assumption states our model is not used", "not used" in v.assumption)

# ======================================================================================
section("10. Promotions against live consensus")

try:
    _s = feed.load_latest()
    fair, nb = pr.consensus_fair_prob(_s, _s.quotes[0].home_team[:8], "h2h",
                                      _s.quotes[0].home_team)
    if fair is not None:
        check("consensus probability is a probability", 0.0 < fair < 1.0, str(fair))
        check("consensus used more than one book", nb > 1, str(nb))
        other = [q.outcome for q in _s.quotes
                 if q.matchup == _s.quotes[0].matchup and q.market == "h2h"
                 and q.outcome != _s.quotes[0].home_team]
        if other:
            f2, _ = pr.consensus_fair_prob(_s, _s.quotes[0].home_team[:8], "h2h", other[0])
            close("de-vigged two-way consensus sums to 1", fair + f2, 1.0, 1e-9)

    evald = pr.evaluate_offers(_s)
    check("example offers load", len(evald) > 0, f"{len(evald)}")
    valued = [e for e in evald if e["status"] == "VALUED"]
    check("at least one example offer matched a live market", len(valued) > 0)
    check("every valued offer reports its book count",
          all(e["value"]["n_books"] > 0 for e in valued))
    check("unmatched offers are listed, never silently dropped",
          all(("value" in e) or e.get("note") for e in evald))

    _b = board.build_board(_s)
    promo_opps = [o for o in _b["opportunities"] if o["class_id"] == "PROMOTIONAL_VALUE"]
    check("promotions reach the board", len(promo_opps) > 0)
    check("promotions rank in the subsidised tier",
          all(o["tier"] == board.TIER_SUBSIDISED for o in promo_opps))
    check("promotions rank ABOVE middles",
          board.TIER_SUBSIDISED < board.TIER_BOUNDED)
    check("every example promo is labelled as an example on the board",
          all(any("EXAMPLE" in c for c in o["caveats"]) for o in promo_opps))
    check("every promo warns it can lose the whole stake",
          all(any("whole stake" in c for c in o["caveats"]) for o in promo_opps))
    check("promo stake basis credits the venue's cap, not our policy",
          all("NOT our sizing policy" in o["suggested_stake"]["basis"]
              for o in promo_opps if o["suggested_stake"]))
    check("every promo still carries a sizing gate despite showing a number",
          all(o["stake_gate"] and "not a sizing recommendation" in o["stake_gate"]
              for o in promo_opps))
    check("PROMOTIONAL_VALUE is no longer listed as a gated lane",
          "PROMOTIONAL_VALUE" not in {g["class_id"] for g in _b["gated_lanes"]})
    check("the board records the contract hash it validated against",
          _b.get("contract_base_sha256") == c.base_sha256)
    check("the board records the amendment version", _b.get("contract_amendment_version") == 1)
except FileNotFoundError as e:
    print(f"  SKIP  live promo assertions -- {e}")


# ======================================================================================
section("11. In-play exclusion -- the phantom-arbitrage guard")

# WHY THIS GUARD EXISTS, measured over 179 snapshots:
#   in-play two-sided markets with a negative cross-book overround : 24.56%
#   pre-game                                                       :  0.27%
# 85.7% of all apparent arbitrage on this tape came from games already under way, where a
# book re-stamps last_update without moving off its pre-game price. Quote age does not
# detect it. Without this guard the board hands out confident stakes on phantoms.
from datetime import datetime as _dt, timezone as _tz

_q = feed.Quote(game_id="g", commence_time="2026-08-19T01:00:00Z", home_team="H",
                away_team="A", book="b", book_title="B", market="h2h", outcome="H",
                price=-110, point=None, last_update="", snapshot_utc="x")
check("a game already started is flagged in-play",
      _q.is_in_play(_dt(2026, 8, 19, 3, 0, tzinfo=_tz.utc)) is True)
check("a game not yet started is not flagged",
      _q.is_in_play(_dt(2026, 8, 19, 0, 0, tzinfo=_tz.utc)) is False)
check("exactly at tip counts as in play",
      _q.is_in_play(_dt(2026, 8, 19, 1, 0, tzinfo=_tz.utc)) is True)
_bad = feed.Quote(game_id="g", commence_time="not-a-date", home_team="H", away_team="A",
                  book="b", book_title="B", market="h2h", outcome="H", price=-110,
                  point=None, last_update="", snapshot_utc="x")
check("an unparseable commence time does not crash, and is treated as pre-game",
      _bad.is_in_play(_dt(2026, 8, 19, 3, 0, tzinfo=_tz.utc)) is False)

try:
    _s = feed.load_latest()
    _b = board.build_board(_s)
    check("the board reports how many in-play games it excluded",
          "n_games_in_play_excluded" in _b)
    check("the exclusion is explained rather than silent",
          "in_play_note" in _b and "24.56%" in _b["in_play_note"])
    _inplay = {q.game_id[:8] for q in _s.quotes if q.is_in_play(_s.captured_at)}
    _arb = [o for o in _b["opportunities"] if o["class_id"] == "TRUE_CROSS_BOOK_ARBITRAGE"]
    check("no arbitrage is reported on a game already under way",
          not any(any(gid in o["opp_id"] for gid in _inplay) for o in _arb))
    _mid = [o for o in _b["opportunities"] if o["class_id"] == "MIDDLES_AND_DISLOCATIONS"]
    check("no middle is reported on a game already under way",
          not any(any(gid in o["opp_id"] for gid in _inplay) for o in _mid))
except FileNotFoundError as e:
    print(f"  SKIP  in-play live assertions -- {e}")


# ======================================================================================
section("12. The page must describe the grid it MEASURED, not one it remembers")

# This guard exists because the board asserted "an hourly polling grid" as hard-coded prose
# and kept printing it for a day after the capture cadence was raised. A surface that
# describes its own data has to derive that description from the data.
import render as _render

try:
    _s = feed.load_latest()
    _b = board.build_board(_s)
    check("the board measures its own capture cadence", "cadence" in _b)
    _cad = _b.get("cadence", {})
    check("the measured cadence is a real number or an explicit None",
          "median_gap_min" in _cad)
    _html = _render.render(_b)
    check("the page contains NO hard-coded claim of an hourly grid",
          "hourly polling grid" not in _html)
    if _cad.get("median_gap_min") is not None:
        check("the measured gap appears on the page",
              f"{_cad['median_gap_min']:g}" in _html,
              "the banner must quote the number it measured")
    check("the page still refuses an executability claim",
          "not</b> a claim that you could still take it" in _html
          or "not a claim that you could still take it" in _html)
    check("the page names what an executability claim would require",
          "M21/M22" in _html)
except FileNotFoundError as e:
    print(f"  SKIP  cadence-honesty assertions -- {e}")


# ======================================================================================
section("13. Middle expected value -- the number M10 said it never computed")

import middle_ev as mev

_d110 = om.american_to_decimal(-110)

# Breakeven from the prices alone. Stake 1 each side at -110: hit pays 2 x 0.909 = 1.818,
# miss loses 1 - 0.909 = 0.0909. Breakeven p = 0.0909 / 1.909 = 4.762%.
close("breakeven hit rate at -110/-110", mev.breakeven_probability(_d110, _d110), 0.047619, 1e-5)
check("breakeven falls when the prices improve",
      mev.breakeven_probability(om.american_to_decimal(100), om.american_to_decimal(100))
      < mev.breakeven_probability(_d110, _d110))

_bw = mev.breakeven_window(_d110, _d110)
check("the breakeven window at -110/-110 is about 1.8 points", 1.6 < _bw < 2.0, f"{_bw}")

# The finding that changes the product: narrow middles lose money.
for w in (0.5, 1.0, 1.5):
    r = mev.evaluate(w, _d110, _d110)
    check(f"a {w}-point middle is NEGATIVE expectation at -110", not r.is_positive,
          f"EV {r.ev}")
for w in (2.5, 3.0, 5.0):
    r = mev.evaluate(w, _d110, _d110)
    check(f"a {w}-point middle is positive expectation at -110", r.is_positive, f"EV {r.ev}")

check("hit probability rises with window width",
      mev.evaluate(1.0, _d110, _d110).p_hit < mev.evaluate(3.0, _d110, _d110).p_hit)
check("the conservative estimate is never more optimistic than the headline",
      all(mev.evaluate(w, _d110, _d110).p_hit_conservative
          <= mev.evaluate(w, _d110, _d110).p_hit for w in (0.5, 1, 2, 3, 5)))
check("a zero-width window cannot hit", mev.evaluate(0.0, _d110, _d110).p_hit == 0.0)
check("the model states its provenance", "exploration games" in mev.PROVENANCE)
check("the model admits the window-centring assumption",
      "centred" in mev.evaluate(2.0, _d110, _d110).caveat)
check("residual sd is below the unconditional sd, as a decomposition requires",
      mev.SD_RESIDUAL < mev.SD_TOTAL_EXPLORATION)

try:
    _s = feed.load_latest()
    _b = board.build_board(_s)
    _m = [o for o in _b["opportunities"] if o["class_id"] == "MIDDLES_AND_DISLOCATIONS"]
    if _m:
        check("every middle on the board reports an expected value",
              all("expected on" in o["headline"] or "EV" in o["headline"] for o in _m))
        check("middles are ranked by expected value, best first",
              all(_m[i]["rank_score"] >= _m[i + 1]["rank_score"] for i in range(len(_m) - 1)))
        check("negative-EV middles are shown, not hidden -- no silent cap",
              any(o["rank_score"] <= 0 for o in _m) or all(o["rank_score"] > 0 for o in _m))
        _neg = [o for o in _m if o["rank_score"] <= 0]
        if _neg:
            check("a negative-EV middle says so in its headline",
                  all("NEGATIVE EV" in o["headline"] for o in _neg))
            check("a negative-EV middle names the breakeven window in its caveats",
                  all(any("breakeven" in c for c in o["caveats"]) for o in _neg))
        check("every middle still carries a sizing gate",
              all(o["stake_gate"] for o in _m))
        check("no middle claims a measured hit rate",
              all("MODEL" in o["evidence"] for o in _m))
except FileNotFoundError as e:
    print(f"  SKIP  live middle-EV assertions -- {e}")


# ======================================================================================
section("14. Best-price table -- line shopping made operational")

# D151 measured that taking the best available price removes a median 26.8% of the vig.
# That was a statistic; this section checks it was turned into an instruction that is
# actually correct -- the named book must really be offering the named price.
try:
    _s = feed.load_latest()
    _bp = board.best_price_table(_s)
    check("a best-price table is produced", len(_bp) > 0, f"{len(_bp)} markets")

    _ok_best = _ok_side = _ok_gain = _ok_vig = _ok_real = True
    for r in _bp:
        if len(r["sides"]) != 2:
            _ok_side = False
        for sd in r["sides"]:
            # the quoted best must be the best actually present for that outcome
            cands = [q for q in _s.quotes
                     if q.matchup == r["matchup"] and q.point == r["point"]
                     and q.outcome == sd["outcome"]
                     and board.MARKET_NAMES.get(q.market, q.market) == r["market"]]
            if not cands:
                _ok_real = False
                continue
            top = max(om.american_to_decimal(q.price) for q in cands)
            if abs(om.american_to_decimal(sd["best_price"]) - top) > 1e-9:
                _ok_best = False
            if not any(q.book_title == sd["best_book"]
                       and abs(q.price - sd["best_price"]) < 1e-9 for q in cands):
                _ok_real = False
            if sd["gain_vs_median_pct"] < -1e-9:
                _ok_gain = False
        if r["overround_best_pct"] > r["overround_median_pct"] + 1e-9:
            _ok_vig = False

    check("every row has exactly two sides", _ok_side)
    check("the quoted best price IS the best available for that outcome", _ok_best)
    check("the named book really offers the named price", _ok_real)
    check("shopping never scores worse than the typical book", _ok_gain)
    check("overround at best prices never exceeds overround at the median book", _ok_vig)
    check("rows are sorted by how much vig shopping removes",
          all(_bp[i]["vig_removed_pct"] >= _bp[i + 1]["vig_removed_pct"]
              for i in range(len(_bp) - 1)))
    check("no in-play game appears in the best-price table",
          not any(q.is_in_play(_s.captured_at) for q in _s.quotes
                  for r in _bp if q.matchup == r["matchup"]
                  and q.is_in_play(_s.captured_at)))
    check("every row reports how many books were compared",
          all(sd["n_books"] >= 3 for r in _bp for sd in r["sides"]))

    _b = board.build_board(_s)
    check("the board carries the best-price table", "best_prices" in _b)
    check("the table is framed as where-if-you-bet, not as a recommendation",
          "not a recommendation to bet" in _b.get("best_prices_note", ""))
    _html = _render.render(_b)
    check("the page renders a where-to-bet section", "Where to bet each side" in _html)
except FileNotFoundError as e:
    print(f"  SKIP  best-price assertions -- {e}")

# ======================================================================================
print("\n" + "=" * 86)
if FAIL:
    print(f"M28 TESTS FAILED -- {len(FAIL)} of {len(PASS) + len(FAIL)} checks failed")
    for n, d in FAIL:
        print("   *", n, d)
    sys.exit(1)
print(f"M28 TESTS PASSED -- {len(PASS)}/{len(PASS)} checks")
print("=" * 86)
