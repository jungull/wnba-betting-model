# -*- coding: utf-8 -*-
"""M23 s02 -- score the shadow ledger once outcomes exist.

DECISION-SYSTEM VALIDATION WITHOUT MONEY. Shadow results earn at most the M00 ladder status the
contract assigns them; they are never a licence to trade.

WHY THIS EXISTS SEPARATELY FROM s01. The decisions were logged before their outcome windows
opened -- a property that cannot be manufactured afterwards. Scoring them is a different act,
performed later, against outcomes nobody held at decision time. Keeping the two files apart is
deliberate: nothing in here can reach back and alter what was decided.

FAILS CLOSED. A decision whose game has no observed outcome is NOT scored, NOT assumed, and NOT
dropped quietly -- it is counted and reported as pending. Running this before the games have
settled correctly scores nothing, which is the honest answer on that day.

NOT EVERY LOGGED DECISION IS A BET, and scoring them as though they were would be the central
error available here:

  MIDDLES_AND_DISLOCATIONS -- a real two-leg wager with explicit stakes on both sides. Scoreable.
      Both legs settle against the final margin; the middle "hits" when the margin lands inside
      the window and both sides win.

  STALE_LINE_DELAYED_REACTION -- one side at one price, no stake attached. Scoreable as a
      notional unit bet on that side.

  PURE_MICROSTRUCTURE -- line shopping. It names WHERE to bet a side if you are betting it, with
      no stake and no independent position. It is a DISCOUNT ON A BET YOU WERE MAKING ANYWAY
      (M22: "a discount, not income"). Scoring it as a standalone wager would invent a position
      nobody took and would silently convert a cost reduction into fictitious P&L. It is
      REFUSED, with the reason recorded.

Everything is reported unadjusted AND under M21/M22 execution assumptions, never one alone.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from collections import Counter, defaultdict

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
LEDGER = os.path.join(HERE, "SHADOW_LEDGER.jsonl")

import shadow_ledger as sl  # noqa: E402

#: full club name -> masters abbreviation. PHO/PHX collapse to one club.
NAME2ABV = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Los Angeles Sparks": "LAS", "Las Vegas Aces": "LVA", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Portland Fire": "PDX", "Phoenix Mercury": "PHX",
    "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}

SCOREABLE = {"MIDDLES_AND_DISLOCATIONS", "STALE_LINE_DELAYED_REACTION"}
NOT_A_BET = {
    "PURE_MICROSTRUCTURE":
        "Line shopping names where to bet a side if you are betting it. There is no stake and "
        "no independent position; M22 calls it a discount, not income. Scoring it as a wager "
        "would invent a position nobody took.",
    "PROMOTIONAL_VALUE":
        "No real offer has ever been entered; the offers on file are invented examples.",
}


def american_profit(price: float, stake: float) -> float:
    """Profit (not return) on a winning bet at American odds."""
    return stake * (price / 100.0) if price > 0 else stake * (100.0 / abs(price))


def load_outcomes():
    mt = pd.read_parquet(MTEAM)
    mt["gd"] = pd.to_datetime(mt["game_date"]).dt.date
    home = mt[mt["is_home"] == 1]
    out = {}
    for _, r in home.iterrows():
        h = str(r["team_abbreviation"]).replace("PHO", "PHX")
        a = str(r["opp_team_abbreviation"]).replace("PHO", "PHX")
        out[(r["gd"], h, a)] = {"home_pts": float(r["pts"]), "away_pts": float(r["opp_pts"])}
    return out


def game_key(rec):
    """(ET game-date, home abv, away abv) from 'Away @ Home' plus commence_time."""
    m = rec.get("matchup") or ""
    if " @ " not in m:
        return None
    away, home = [x.strip() for x in m.split(" @ ", 1)]
    if away not in NAME2ABV or home not in NAME2ABV:
        return None
    ct = sl._parse(rec.get("commence_time"))
    if ct is None:
        return None
    gd = ct.astimezone(dt.timezone(dt.timedelta(hours=-4))).date()   # ET in August
    return (gd, NAME2ABV[home], NAME2ABV[away])


def settle_leg(leg, rec, oc):
    """Profit on one leg at its own price and stake. None when not settleable."""
    key = game_key(rec)
    home_abv, away_abv = key[1], key[2]
    side = leg.get("outcome")
    if side not in NAME2ABV:
        return None
    side_abv = NAME2ABV[side]
    hp, ap = oc["home_pts"], oc["away_pts"]
    margin_for_side = (hp - ap) if side_abv == home_abv else (ap - hp)
    stake = leg.get("stake")
    stake = 100.0 if stake is None else float(stake)
    point = leg.get("point")
    price = float(leg["price"])

    if point is None:                       # moneyline
        if margin_for_side > 0:
            return american_profit(price, stake)
        if margin_for_side < 0:
            return -stake
        return 0.0
    adj = margin_for_side + float(point)    # spread: side covers when adj > 0
    if adj > 0:
        return american_profit(price, stake)
    if adj < 0:
        return -stake
    return 0.0                              # push


def main():
    print("=" * 94)
    print("M23 s02 -- scoring the shadow ledger against observed outcomes")
    print("=" * 94)

    recs = [json.loads(l) for l in open(LEDGER, encoding="utf-8") if l.strip()]
    oc = load_outcomes()
    latest = max(k[0] for k in oc)
    print("\nledger decisions      : %d" % len(recs))
    print("outcomes available to : %s" % latest)

    scored, pending, refused = [], [], []
    for r in recs:
        cid = r["class_id"]
        if cid in NOT_A_BET:
            refused.append((r, NOT_A_BET[cid]))
            continue
        if cid not in SCOREABLE:
            refused.append((r, "class not recognised as bet-shaped; refused rather than guessed"))
            continue
        k = game_key(r)
        if k is None or k not in oc:
            pending.append(r)
            continue
        legs = r.get("legs") or []
        pnl = [settle_leg(l, r, oc[k]) for l in legs]
        if any(p is None for p in pnl) or not pnl:
            pending.append(r)
            continue
        stake_total = sum(100.0 if l.get("stake") is None else float(l["stake"]) for l in legs)
        scored.append({"opp_id": r["opp_id"], "class_id": cid, "matchup": r["matchup"],
                       "market": r["market"], "stake_total": stake_total,
                       "pnl_unadjusted": sum(pnl), "n_legs": len(legs)})

    print("\nDISPOSITION")
    print("  scored  : %d" % len(scored))
    print("  pending : %d  (game not yet settled -- fails closed, never assumed)" % len(pending))
    print("  refused : %d  (logged, but not a bet)" % len(refused))
    for cid, n in Counter(r["class_id"] for r, _ in refused).items():
        print("      %-30s %2d  %s" % (cid, n, NOT_A_BET.get(cid, "")[:44]))

    res = {"ledger_decisions": len(recs), "outcomes_available_to": str(latest),
           "scored": len(scored), "pending": len(pending), "refused": len(refused),
           "refused_by_class": dict(Counter(r["class_id"] for r, _ in refused)),
           "not_a_bet_rationale": NOT_A_BET, "results": scored}

    if not scored:
        print("\nNOTHING IS SCOREABLE YET. Every bet-shaped decision is on a game that has not")
        print("settled. That is the correct output today, not a failure: the decisions were")
        print("logged before their outcome windows opened, and those windows are still open.")
        res["headline"] = "no scoreable decision yet"
    else:
        tot_stake = sum(s["stake_total"] for s in scored)
        tot_pnl = sum(s["pnl_unadjusted"] for s in scored)
        print("\nRESULT (UNADJUSTED)")
        print("  decisions scored : %d" % len(scored))
        print("  total staked     : %.2f" % tot_stake)
        print("  total P&L        : %+.2f  (%+.2f%% of stake)"
              % (tot_pnl, 100.0 * tot_pnl / tot_stake if tot_stake else 0.0))
        byc = defaultdict(lambda: [0, 0.0, 0.0])
        for s in scored:
            b = byc[s["class_id"]]
            b[0] += 1; b[1] += s["stake_total"]; b[2] += s["pnl_unadjusted"]
        print("\n  by class:")
        for c, (n, st, pl) in byc.items():
            print("    %-30s n=%2d  staked %8.2f  P&L %+8.2f (%+.2f%%)"
                  % (c, n, st, pl, 100.0 * pl / st if st else 0.0))

        # M21/M22 adjustment -- reported BESIDE the unadjusted figure, never replacing it
        adj = []
        for s in scored:
            e = sl.apply_execution(s["stake_total"], s["class_id"])
            fill = e["stake_fillable_at_median_depth_usd"] / s["stake_total"]
            slip = e["slippage_pct_applied_p90"] / 100.0
            adj.append(s["pnl_unadjusted"] * fill * (1.0 - slip))
        print("\n  ADJUSTED under M21 depth and slippage: %+.2f" % sum(adj))
        print("  (unadjusted retained above; the adjusted figure never replaces it)")
        res["total_stake"] = tot_stake
        res["total_pnl_unadjusted"] = round(tot_pnl, 2)
        res["total_pnl_m21_adjusted"] = round(sum(adj), 2)
        res["headline"] = "scored %d decisions" % len(scored)

    print("\n" + "=" * 94)
    print("A scored shadow result is NOT a licence to trade and NOT evidence any class wins.")
    print("It earns at most the M00 ladder status the contract assigns it, and M37 found no")
    print("class holds any ladder label at all.")
    print("=" * 94)

    with open(os.path.join(HERE, "SCORING.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote SCORING.json")


if __name__ == "__main__":
    main()
