"""line_shopping.py -- what is taking the best available price actually worth?

MARKET-LANE MEASUREMENT, not an exploration screen. It uses no outcome, tests no hypothesis
about player performance, and therefore raises no partition question: there is nothing here
that could leak information from the confirmation seasons, because `pts` never appears. This
is the same footing M07, M17 and M27 operated on.

THE QUESTION. `D150` closed the fundamental-model path to a points edge and observed that the
lanes which remain live need no forecasting edge at all -- one of which is line shopping,
described there as "free, mechanical, and currently unexploited". Free is a claim. This
measures it.

WHAT IS MEASURED. For every two-sided market quoted by at least two books:

  * `overround at one book`   -- the median individual book's own two-sided margin. This is
    what you pay if you always bet at the same place.
  * `overround at best cross-book` -- taking the best available price on EACH side, possibly
    from different books. This is what you pay if you shop.

The difference is the vig line shopping removes. It is not an edge and does not make a losing
bet winning; it lowers the breakeven win rate on bets you were going to place anyway.

A market whose best cross-book overround is NEGATIVE is a true arbitrage, so the same pass
also measures how close this market routinely comes to one -- which is the honest context for
`M28` reporting zero locked opportunities.
"""
from __future__ import annotations

import glob
import json
import statistics as st
from datetime import datetime

import feed
import oddsmath as om


def decimal_prices(side_quotes):
    """side_quotes: list of (book, american_price) -> list of decimal odds."""
    return [om.american_to_decimal(p) for _, p in side_quotes]


def main() -> int:
    root = feed.resolve_data_root()
    files = sorted(glob.glob(str(root.odds_capture / "live_*.json")))
    print(f"tape: {len(files)} snapshots from {root.path}")

    best_or: list[float] = []
    single_or: list[float] = []
    books_per_market: list[int] = []
    by_market: dict[str, list[float]] = {}
    sub_hundred = 0
    n_markets = 0
    live_markets = live_neg = 0

    for f in files:
        try:
            games = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        snap = datetime.strptime(f.split("live_")[-1].replace(".json", ""),
                                 "%Y%m%dT%H%M%SZ")
        for g in games:
            # IN-PLAY GAMES ARE MEASURED SEPARATELY, NEVER POOLED. 24.56% of in-play
            # two-sided markets show a negative overround against 0.27% pre-game: a book
            # that has not moved off its pre-game number after tip is not a competing
            # opinion, and pooling the two makes both numbers meaningless.
            try:
                ct = datetime.fromisoformat(
                    g["commence_time"].replace("Z", "+00:00")).replace(tzinfo=None)
                in_play = snap >= ct
            except Exception:
                in_play = False
            acc: dict[tuple, dict[str, list]] = {}
            for b in g.get("bookmakers", []):
                for m in b.get("markets", []):
                    for o in m.get("outcomes", []):
                        if o.get("price") is None:
                            continue
                        # Spreads pair on MAGNITUDE (-8.5 vs +8.5); totals and moneyline
                        # pair on the number itself. Keying spreads on the signed point
                        # splits every spread into two one-sided groups that are then
                        # discarded, which is why the first run of this script counted
                        # 29 spread markets against 1,657 totals.
                        _pt = o.get("point")
                        if m["key"] == "spreads" and _pt is not None:
                            _pt = abs(_pt)
                        key = (m["key"], _pt)
                        acc.setdefault(key, {}).setdefault(o["name"], []).append(
                            (b["key"], float(o["price"])))

            for (mkt, _point), sides in acc.items():
                names = list(sides)
                if len(names) != 2:
                    continue
                # Require both sides quoted by >=2 books, else "shopping" is not a choice.
                if min(len(sides[n]) for n in names) < 2:
                    continue

                if in_play:
                    live_markets += 1
                    bl = [max(decimal_prices(sides[n])) for n in names]
                    if sum(1.0 / d for d in bl) - 1.0 < 0:
                        live_neg += 1
                    continue
                n_markets += 1
                # Best available price on each side = highest decimal odds.
                best = [max(decimal_prices(sides[n])) for n in names]
                bo = sum(1.0 / d for d in best) - 1.0
                best_or.append(bo)
                by_market.setdefault(mkt, []).append(bo)
                if bo < 0:
                    sub_hundred += 1

                # Baseline: what a single book charges, taking the median across books that
                # quote BOTH sides.
                books = {bk for n in names for bk, _ in sides[n]}
                per_book = []
                for bk in books:
                    px = []
                    ok = True
                    for n in names:
                        hit = next((p for b2, p in sides[n] if b2 == bk), None)
                        if hit is None:
                            ok = False
                            break
                        px.append(hit)
                    if ok:
                        per_book.append(om.overround(px))
                if per_book:
                    single_or.append(st.median(per_book))
                books_per_market.append(len(books))

    if not n_markets:
        print("no comparable two-sided markets found")
        return 1

    s_one = st.median(single_or)
    s_best = st.median(best_or)
    srt = sorted(best_or)

    print()
    print("=" * 78)
    print("WHAT LINE SHOPPING IS WORTH")
    print("=" * 78)
    print(f"  two-sided markets measured        : {n_markets:,}")
    print(f"  mean books quoting both sides     : {st.mean(books_per_market):.1f}")
    print()
    print(f"  median overround AT ONE BOOK      : {s_one * 100:7.3f}%")
    print(f"  median overround AT BEST PRICES   : {s_best * 100:7.3f}%")
    print(f"  vig removed by shopping (median)  : {(s_one - s_best) * 100:7.3f} points")
    print(f"  share of the vig removed          : {(s_one - s_best) / s_one * 100:7.1f}%")
    print()
    print("  breakeven win rate on a two-way market:")
    print(f"    betting one book   : {(1 + s_one) / 2 * 100:6.2f}%")
    print(f"    shopping best price: {(1 + s_best) / 2 * 100:6.2f}%")
    print(f"    edge handed back   : {((1 + s_one) / 2 - (1 + s_best) / 2) * 100:6.2f} points of win rate")

    print()
    print("=" * 78)
    print("PRE-GAME vs IN-PLAY -- why they are never pooled")
    print("=" * 78)
    print(f"  PRE-GAME markets : {n_markets:6,}   negative overround: {sub_hundred:3d}"
          f"  = {sub_hundred / max(n_markets, 1) * 100:.4f}%")
    print(f"  IN-PLAY  markets : {live_markets:6,}   negative overround: {live_neg:3d}"
          f"  = {live_neg / max(live_markets, 1) * 100:.4f}%")
    if (live_neg + sub_hundred):
        print(f"  share of ALL apparent arbitrage that is in-play: "
              f"{live_neg / (live_neg + sub_hundred) * 100:.1f}%")
    print("  An in-play negative overround is a book that has not moved off its pre-game")
    print("  price after tip. It is not takeable and it is not counted below.")
    print()
    print("=" * 78)
    print("HOW CLOSE DOES THE PRE-GAME MARKET COME TO ARBITRAGE?")
    print("=" * 78)
    print(f"  pre-game best-price overround below 0: {sub_hundred} of {n_markets:,} "
          f"= {sub_hundred / n_markets * 100:.4f}%")
    for q, lab in ((0, "min"), (len(srt) // 1000, "p0.1"), (len(srt) // 100, "p1"),
                   (len(srt) // 10, "p10"), (len(srt) // 2, "median")):
        print(f"  {lab:>6} best-price overround: {srt[min(q, len(srt) - 1)] * 100:7.3f}%")

    print()
    print("  by market type (median best-price overround):")
    for mkt, vals in sorted(by_market.items()):
        print(f"    {mkt:<10} n={len(vals):>7,}  {st.median(vals) * 100:7.3f}%")

    print()
    print("  NOTE: line shopping is NOT an edge. It lowers the price of bets you were placing")
    print("  anyway. It cannot make a negative-expectation bet positive on its own.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
