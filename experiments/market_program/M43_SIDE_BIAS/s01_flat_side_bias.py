# -*- coding: utf-8 -*-
"""M43 s01 -- does the WNBA spread market carry a flat, bettable side bias?

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model. S42 closed.

WHY THIS, AFTER EVERYTHING ELSE. The six closed routes and M42's news test all asked the
market to be WRONG ABOUT A PARTICULAR GAME, and required us to identify which one. That has
failed every time, because the market's per-game number is better than ours.

This asks something weaker and therefore more plausible: is the market wrong about a WHOLE
CATEGORY, always in the same direction? Small markets sometimes carry a standing bias --
favourites shaded, home sides shaded, unders shaded -- that needs no per-game skill at all,
only the discipline to take one side every time. It is the cheapest possible strategy to
run, which is exactly why it is worth ruling out before anything cleverer.

WHY THE BOOTSTRAP IS CLUSTERED BY GAME. Eleven books quote the same game, and those quotes
are nearly the same bet. Resampling rows would treat eleven correlated observations as
eleven independent ones and shrink every interval by roughly the square root of eleven,
manufacturing significance out of duplication. The resample is over GAMES.

WHY FOUR TESTS AND NOT FORTY. Home, away, favourite, underdog -- the four standing sides of
a spread market. They are declared here, before the numbers, and the multiple-comparison
burden is stated with the result rather than discovered afterwards. Any bias that only
appears once the categories are sliced by book, month or line size is a search, not a
finding, and this file does not slice.

WHAT A POSITIVE RESULT WOULD REQUIRE. Beating zero is not enough: a flat side must clear
the vig it pays. The break-even at -110 is 52.4%, and the interval must exclude the flat
-4.5% that betting a random side returns, not merely exclude zero return.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
EXT = os.path.join(ROOT, "data", "odds_capture", "master_odds_extension.csv")
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")

SEED = 20260825
N_BOOT = 4000

NAME2ABV = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Los Angeles Sparks": "LAS", "Las Vegas Aces": "LVA", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Portland Fire": "PDX", "Phoenix Mercury": "PHX",
    "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}


def american_profit(price, won, push):
    """Profit on a 1-unit stake. A push returns the stake, not a win."""
    p = np.where(push, 0.0,
                 np.where(won,
                          np.where(price > 0, price / 100.0, 100.0 / np.abs(price)),
                          -1.0))
    return p


def build():
    e = pd.read_csv(EXT, low_memory=False)
    e = e.dropna(subset=["game_id", "team", "odds_spread", "odds_price"])
    e["game_id"] = e["game_id"].astype("int64").astype(str)
    e["abv"] = e["team"].map(NAME2ABV)
    e = e.dropna(subset=["abv"])
    e["snap"] = pd.to_datetime(e["odds_snapshot_timestamp"], utc=True, errors="coerce")
    e["tip"] = pd.to_datetime(e["odds_commence_time"], utc=True, errors="coerce")
    e = e.dropna(subset=["snap", "tip"])
    # STRICTLY PRE-TIP. An in-play quote is not a bet anyone could have placed on the
    # pre-game side, and it tracks the game rather than the market's prior belief.
    e = e[e["snap"] < e["tip"]]
    # one quote per (game, book, team): the LAST pre-tip one, i.e. the closing price we
    # could actually have taken
    e = (e.sort_values("snap")
           .groupby(["game_id", "bookmaker_key", "abv"], as_index=False).last())

    mt = pd.read_parquet(MTEAM, columns=["game_id", "game_date", "team_abbreviation",
                                         "is_home", "pts", "opp_team_abbreviation"])
    mt["game_id"] = mt["game_id"].astype(str)
    opp = mt[["game_id", "team_abbreviation", "pts"]].rename(
        columns={"team_abbreviation": "opp_team_abbreviation", "pts": "opp_pts"})
    mt = mt.merge(opp, on=["game_id", "opp_team_abbreviation"], how="left")
    mt = mt.rename(columns={"team_abbreviation": "abv"})

    d = e.merge(mt[["game_id", "abv", "is_home", "pts", "opp_pts", "game_date"]],
                on=["game_id", "abv"], how="inner")
    d = d.dropna(subset=["pts", "opp_pts"])
    d["margin"] = d["pts"] - d["opp_pts"]
    d["ats"] = d["margin"] + d["odds_spread"]        # >0 cover, <0 loss, ==0 push
    d["won"] = d["ats"] > 0
    d["push"] = d["ats"] == 0
    d["profit"] = american_profit(d["odds_price"].to_numpy(float),
                                  d["won"].to_numpy(), d["push"].to_numpy())
    d["is_fav"] = d["odds_spread"] < 0
    return d


def clustered_ci(sub, rng):
    """Bootstrap the mean return, RESAMPLING GAMES -- eleven books on one game are one bet."""
    if sub.empty:
        return None
    games = sub["game_id"].unique()
    by = {g: s["profit"].to_numpy(float) for g, s in sub.groupby("game_id")}
    out = []
    for _ in range(N_BOOT):
        pick = rng.choice(games, len(games), replace=True)
        vals = np.concatenate([by[g] for g in pick])
        out.append(vals.mean())
    lo, hi = np.percentile(out, [2.5, 97.5])
    return {"roi": float(sub["profit"].mean()), "lo": float(lo), "hi": float(hi),
            "n_quotes": int(len(sub)), "n_games": int(len(games)),
            "hit": float(sub.loc[~sub["push"], "won"].mean())}


def main():
    res = {}
    print("=" * 94)
    print("M43 s01 -- flat side bias in the WNBA spread market")
    print("=" * 94)

    d = build()
    print("\nsettled pre-tip quotes: %d over %d games, %d books"
          % (len(d), d["game_id"].nunique(), d["bookmaker_key"].nunique()))
    print("date span: %s -> %s" % (d["game_date"].min(), d["game_date"].max()))
    res["n_quotes"], res["n_games"] = int(len(d)), int(d["game_id"].nunique())

    rng = np.random.default_rng(SEED)
    sides = (("HOME", d[d["is_home"] == 1]),
             ("AWAY", d[d["is_home"] == 0]),
             ("FAVOURITE", d[d["is_fav"]]),
             ("UNDERDOG", d[~d["is_fav"]]))

    print("\nFLAT BET ON EACH STANDING SIDE (1 unit, last pre-tip price)")
    print("%-11s %8s %8s %9s %26s" % ("side", "games", "quotes", "hit", "ROI  95% CI (by game)"))
    tbl = {}
    for name, sub in sides:
        r = clustered_ci(sub, rng)
        if r is None:
            continue
        flag = "  <-- CLEARS ZERO" if r["lo"] > 0 else ""
        print("%-11s %8d %8d %8.1f%%   %+6.2f%%  [%+.2f%%, %+.2f%%]%s"
              % (name, r["n_games"], r["n_quotes"], 100 * r["hit"], 100 * r["roi"],
                 100 * r["lo"], 100 * r["hi"], flag))
        tbl[name] = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()}
    res["sides"] = tbl

    print("\n" + "=" * 94)
    winners = [k for k, v in tbl.items() if v["lo"] > 0]
    if winners:
        print("A SIDE CLEARING ZERO: %s." % ", ".join(winners))
        print("FOUR tests were run, so at 95%% one false positive is expected roughly one")
        print("time in five. This needs prospective confirmation before it is anything.")
    else:
        print("NO STANDING SIDE CLEARS ZERO. The spread market carries no flat bias large")
        print("enough to bet on this sample -- betting every home side, every road side,")
        print("every favourite or every underdog all lose, which is what an efficient")
        print("market with vig looks like.")
    print("")
    print("Break-even at -110 is 52.4%. A hit rate below that loses however it is dressed.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s01.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s01.json")


if __name__ == "__main__":
    main()
