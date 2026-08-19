"""add_promo.py -- add a real promotional offer and see immediately what it is worth.

WHY THIS EXISTS. `D153` measured promotions as the largest per-unit value in the whole
programme by two orders of magnitude -- roughly $10 on a $25 free bet against $0.20 for a
typical arbitrage -- and also recorded that their FREQUENCY is completely unmeasured,
because this programme has never seen a real offer. The only thing standing between those
two facts is that entering an offer meant hand-editing JSON with fields like
`matchup_contains` and `boosted_price`.

So this is friction removal on the highest-value lane, not a new capability.

USAGE

  List what you can attach an offer to right now:
      python add_promo.py --list

  Add an odds boost (the common case -- a price improved on a specific selection):
      python add_promo.py --kind odds_boost --team "Aces" --market h2h \\
                          --outcome "Las Vegas Aces" --base -150 --boosted -110 \\
                          --max-stake 25 --venue DraftKings

  Add a profit boost token (your winnings multiplied):
      python add_promo.py --kind profit_boost --team "Liberty" --market totals \\
                          --outcome Over --base -110 --boost-pct 50 --max-stake 50

  Add a free bet (stake not returned on a win, which is the usual term):
      python add_promo.py --kind free_bet --team "Sky" --market h2h \\
                          --outcome "Chicago Sky" --base 250 --max-stake 25

  Add a bonus-back (lose and the stake returns as site credit):
      python add_promo.py --kind bonus_back --team "Fever" --market h2h \\
                          --outcome "Indiana Fever" --base -120 --max-stake 50 \\
                          --recovery 0.7

  Remove the shipped examples once you have real ones:
      python add_promo.py --clear-examples

Every add prints the offer's expected value immediately, priced against the de-vigged
consensus of every book quoting that market -- never against this programme's own model,
which has no measured edge (D141/D150).

This writes a local JSON file. It contacts no venue, enrols in nothing, and holds no
credential. Enrolling in an offer is yours alone.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import feed
import promos

HERE = Path(__file__).resolve().parent
PROMOS = HERE / "promos.json"

MARKET_LABEL = {"h2h": "Moneyline", "spreads": "Spread", "totals": "Total"}


def load_doc() -> dict:
    return json.loads(PROMOS.read_text(encoding="utf-8"))


def save_doc(doc: dict) -> None:
    PROMOS.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def cmd_list() -> int:
    """Show every market an offer could be attached to, with its consensus price."""
    snap = feed.load_latest()
    print(f"snapshot {snap.snapshot_utc}  ({snap.age_seconds / 60:.0f} min old)\n")
    seen = {}
    for q in snap.quotes:
        if q.is_in_play(snap.captured_at):
            continue
        seen.setdefault((q.matchup, q.market, q.point), set()).add(q.outcome)

    last_match = None
    for (matchup, market, point), outcomes in sorted(seen.items()):
        if matchup != last_match:
            print(f"\n{matchup}")
            last_match = matchup
        pt = f" {point:g}" if point is not None else ""
        for o in sorted(outcomes):
            fair, n = promos.consensus_fair_prob(snap, matchup.split(" @ ")[-1][:10],
                                                 market, o, point)
            fair_s = f"consensus {fair * 100:5.1f}%" if fair else "consensus    n/a"
            print(f"   --market {market:<8} --outcome {o!r:<26}{pt:<7} {fair_s}  ({n} books)")
    print("\nPick a --team substring, a --market and an --outcome from the lines above.")
    return 0


def cmd_clear_examples() -> int:
    doc = load_doc()
    before = len(doc.get("offers", []))
    doc["offers"] = [o for o in doc.get("offers", []) if not o.get("example_only")]
    save_doc(doc)
    print(f"removed {before - len(doc['offers'])} example offer(s); "
          f"{len(doc['offers'])} real offer(s) remain")
    return 0


def cmd_add(a: argparse.Namespace) -> int:
    if a.kind == "odds_boost" and a.boosted is None:
        print("ERROR: --boosted is required for an odds_boost (the improved price).")
        return 2
    if a.kind == "profit_boost" and a.boost_pct is None:
        print("ERROR: --boost-pct is required for a profit_boost (50 means +50%).")
        return 2

    doc = load_doc()
    offers = doc.setdefault("offers", [])
    oid = a.id or f"{a.kind.upper()}-{len(offers) + 1:03d}"
    if any(o.get("id") == oid for o in offers):
        print(f"ERROR: an offer with id {oid} already exists. Pass a different --id.")
        return 2

    offer = {
        "enabled": True,
        "id": oid,
        "venue": a.venue or "your book",
        "kind": a.kind,
        "label": a.label or f"{a.kind.replace('_', ' ')} on {a.outcome}",
        "matchup_contains": a.team,
        "market": a.market,
        "outcome": a.outcome,
        "base_price": a.base,
        "max_stake": a.max_stake,
        "restrictions": a.restrictions or "as posted by the venue",
    }
    if a.point is not None:
        offer["point"] = a.point
    if a.kind == "odds_boost":
        offer["boosted_price"] = a.boosted
    if a.kind == "profit_boost":
        offer["boost_pct"] = a.boost_pct / 100.0 if a.boost_pct > 1 else a.boost_pct
    if a.kind == "free_bet":
        offer["free_bet_stake_returned"] = bool(a.stake_returned)
    if a.kind == "bonus_back":
        offer["bonus_back_recovery"] = a.recovery

    # Price it BEFORE saving, so a mistyped selection fails loudly rather than sitting
    # in the file producing an UNMATCHED row on the board.
    snap = feed.load_latest()
    fair, n_books = promos.consensus_fair_prob(
        snap, a.team, a.market, a.outcome, a.point)
    if fair is None:
        print(f"ERROR: no live two-sided {a.market} market matched team={a.team!r} "
              f"outcome={a.outcome!r}"
              + (f" point={a.point}" if a.point is not None else ""))
        print("       Nothing was saved. Run --list to see exactly what is quotable now.")
        return 2

    v = promos.value_promo(
        kind=a.kind, fair_prob=fair, base_price=a.base,
        boosted_price=a.boosted, boost_pct=offer.get("boost_pct"),
        max_stake=a.max_stake, free_bet_stake_returned=bool(a.stake_returned),
        bonus_back_recovery=a.recovery)

    offers.append(offer)
    save_doc(doc)

    print(f"\nSAVED {oid} to {PROMOS.name}\n")
    print(f"  {MARKET_LABEL.get(a.market, a.market)}  {a.outcome}"
          + (f" {a.point:g}" if a.point is not None else ""))
    print(f"  consensus fair probability : {fair * 100:.2f}%  (from {n_books} books)")
    print(f"  {v.basis}")
    print()
    print(f"  EXPECTED VALUE : {v.ev_per_unit * 100:+.1f}% per unit"
          + (f"  ->  ${v.ev_total:+,.2f} at the ${a.max_stake:,.0f} cap"
             if a.max_stake else ""))
    print(f"  the same wager UNPROMOTED is {v.baseline_ev_per_unit * 100:+.1f}%, "
          f"so the promotion itself is worth {v.uplift_per_unit * 100:+.1f} points")
    print()
    if v.ev_per_unit <= 0:
        print("  NOTE: this offer prices as NEGATIVE expected value. Worth re-checking the")
        print("        terms you entered before acting on it.")
    print("  It will appear on the board at the next refresh (within 10 minutes).")
    print("  This saved a local file. It contacted no venue and enrolled in nothing.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true", help="show what you can attach an offer to")
    p.add_argument("--clear-examples", action="store_true",
                   help="delete the shipped example offers")
    p.add_argument("--kind", choices=promos.PROMO_KINDS)
    p.add_argument("--team", help="substring of the matchup, e.g. 'Aces'")
    p.add_argument("--market", choices=("h2h", "spreads", "totals"))
    p.add_argument("--outcome", help="team name, or Over/Under")
    p.add_argument("--point", type=float, help="required for spreads and totals")
    p.add_argument("--base", type=float, help="the ORDINARY American price, before the promo")
    p.add_argument("--boosted", type=float, help="odds_boost only: the promoted price")
    p.add_argument("--boost-pct", type=float, dest="boost_pct",
                   help="profit_boost only: 50 means +50%%")
    p.add_argument("--max-stake", type=float, dest="max_stake", default=0.0,
                   help="the offer's own cap")
    p.add_argument("--stake-returned", action="store_true",
                   help="free_bet only: the stake IS returned on a win (unusual)")
    p.add_argument("--recovery", type=float, default=0.70,
                   help="bonus_back only: what a returned bonus is worth to you, 0..1")
    p.add_argument("--venue", help="which book")
    p.add_argument("--label")
    p.add_argument("--id")
    p.add_argument("--restrictions")
    a = p.parse_args()

    if a.list:
        return cmd_list()
    if a.clear_examples:
        return cmd_clear_examples()
    missing = [n for n in ("kind", "team", "market", "outcome", "base")
               if getattr(a, n) in (None, "")]
    if missing:
        p.print_help()
        print(f"\nMissing required argument(s): {', '.join('--' + m for m in missing)}")
        return 2
    return cmd_add(a)


if __name__ == "__main__":
    raise SystemExit(main())
