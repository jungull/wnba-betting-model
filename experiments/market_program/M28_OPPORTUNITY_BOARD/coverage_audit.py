"""coverage_audit.py -- which market types does each surface actually cover?

WHY THIS EXISTS. Two bugs in this node produced SILENCE rather than errors:

  * every in-play game was scanned for arbitrage as though pre-game (D151), and
  * every SPREAD was silently discarded by three separate surfaces (D155),

and **174 assertions passed throughout both**, because no assertion said what SHOULD be
there. A test suite cannot catch an absence it was never told to expect. Fixing the two
instances is not the same as fixing the class.

So this inverts the question. Instead of asking "is what we produced correct?", it asks
**"for every market type present in the tape, does each surface produce anything at all?"**
A surface that returns nothing for a market that is quoted hundreds of times is either a
bug or a deliberate scope decision - and either way it must be visible, not silent.

Deliberate omissions are declared in DECLARED_SCOPE below. Anything absent that is NOT
declared is reported as a SILENT GAP. The point is that a scope decision has to be written
down before this file will accept it.

Run: python coverage_audit.py        (exit 1 if a silent gap is found)
"""
from __future__ import annotations

import sys
from collections import Counter

import board
import feed
import promos

# Omissions that are DELIBERATE. Each needs a reason, and writing one down is the whole
# barrier between "we chose not to" and "we never noticed".
DECLARED_SCOPE = {
    ("middles", "h2h"): (
        "A moneyline has no line to straddle, so a middle is undefined on it. Not a gap."),
    # NOTE: ("middles", "spreads") was declared out of scope here until the margin
    # dispersion was measured (signed sd 13.60, residual 13.05). It is now IMPLEMENTED,
    # which is what a declared gap is supposed to lead to rather than a permanent excuse.
}

#: Surfaces that scan a market but legitimately find nothing on a given day. Zero here means
#: "looked and found none", which is a RESULT, not a gap -- arbitrage runs at 0.18-0.25% of
#: markets (D151/robustness check), so zero on any one snapshot is the expected observation.
SCANS_BUT_MAY_FIND_NOTHING = {
    ("middles", "spreads"),
    ("arbitrage", "h2h"),
    ("arbitrage", "spreads"),
    ("arbitrage", "totals"),
}


def main() -> int:
    snap = feed.load_latest()
    live = board.build_board(snap)

    present = Counter(q.market for q in snap.quotes
                      if not q.is_in_play(snap.captured_at))
    print("=" * 78)
    print("MARKET TYPES PRESENT IN THE TAPE (pre-game quotes)")
    print("=" * 78)
    for m, n in present.most_common():
        print(f"  {m:<10} {n:5d} quotes")

    # what each surface actually produced, by market
    produced: dict[str, Counter] = {
        "arbitrage": Counter(), "middles": Counter(),
        "dispersion": Counter(), "best_price": Counter(), "promos": Counter(),
    }
    label_to_key = {v: k for k, v in board.MARKET_NAMES.items()}
    for o in live["opportunities"]:
        head = o["market"].split()[0].split("—")[0].strip()
        key = label_to_key.get(head, head.lower())
        cls = o["class_id"]
        if cls == "TRUE_CROSS_BOOK_ARBITRAGE":
            produced["arbitrage"][key] += 1
        elif cls == "MIDDLES_AND_DISLOCATIONS":
            produced["middles"][key] += 1
        elif cls == "PURE_MICROSTRUCTURE":
            produced["dispersion"][key] += 1
        elif cls == "PROMOTIONAL_VALUE":
            produced["promos"][key] += 1
    for r in live.get("best_prices", []):
        produced["best_price"][label_to_key.get(r["market"], r["market"].lower())] += 1

    print()
    print("=" * 78)
    print("COVERAGE BY SURFACE")
    print("=" * 78)
    gaps = []
    surfaces = ["arbitrage", "middles", "dispersion", "best_price"]
    print(f"  {'surface':<12}" + "".join(f"{m:>13}" for m in present))
    print(f"  {'':<12}" + "".join(f"{'':>13}" for m in present))
    for surf in surfaces:
        cells = []
        for m in present:
            n = produced[surf][m]
            if n:
                cells.append(f"{n:>13}")
            elif (surf, m) in SCANS_BUT_MAY_FIND_NOTHING:
                cells.append(f"{'0 (scanned)':>13}")
            elif (surf, m) in DECLARED_SCOPE:
                cells.append(f"{'out of scope':>13}")
            else:
                cells.append(f"{'SILENT GAP':>13}")
                gaps.append((surf, m, present[m]))
        print(f"  {surf:<12}" + "".join(cells))

    # promos are user-driven, so absence is not a gap -- but the VALUER must handle each type
    print()
    print("  promo valuation reachability (independent of whether an offer exists):")
    for m in present:
        sample = next((q for q in snap.quotes
                       if q.market == m and not q.is_in_play(snap.captured_at)), None)
        if sample is None:
            continue
        p, n = promos.consensus_fair_prob(
            snap, sample.matchup.split(" @ ")[-1][:10], m, sample.outcome, sample.point)
        ok = "prices" if p is not None else "CANNOT PRICE"
        print(f"    {m:<10} {ok:<14} ({n} books)")
        if p is None:
            gaps.append(("promo_valuation", m, present[m]))

    print()
    print("=" * 78)
    if gaps:
        print(f"  {len(gaps)} SILENT GAP(S) -- a market is quoted but a surface produces nothing")
        for surf, m, n in gaps:
            print(f"    {surf} produces nothing for {m}, which has {n} pre-game quotes")
        print()
        print("  Either fix it, or declare it in DECLARED_SCOPE with a reason.")
        return 1
    print("  NO SILENT GAPS. Every market quoted is covered, scanned, or declared out of scope.")
    print()
    print("  Legend:  a number = produced that many rows")
    print("           0 (scanned) = the surface ran and legitimately found none")
    print("           out of scope = a deliberate omission with a written reason")
    print("           SILENT GAP = quoted market, no output, no reason. This is the bug class")
    print("                        that hid in-play arbitrage (D151) and every spread (D155).")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
