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
    for o in b["opportunities"]:
        if o["class_id"] != "TRUE_CROSS_BOOK_ARBITRAGE":
            if o["suggested_stake"] is not None or not o["stake_gate"]:
                live_ok = False
                break
    check("no probabilistic opportunity carries a suggested stake", live_ok)
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
print("\n" + "=" * 86)
if FAIL:
    print(f"M28 TESTS FAILED -- {len(FAIL)} of {len(PASS) + len(FAIL)} checks failed")
    for n, d in FAIL:
        print("   *", n, d)
    sys.exit(1)
print(f"M28 TESTS PASSED -- {len(PASS)}/{len(PASS)} checks")
print("=" * 86)
