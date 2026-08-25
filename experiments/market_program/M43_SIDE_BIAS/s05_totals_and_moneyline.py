# -*- coding: utf-8 -*-
"""M43 s05 -- totals and MONEYLINES across 2022-2026. Two markets never properly tested.

E0-style diagnostic, NON-CLAIMING. S42 closed.

TWO GAPS. s03 tested totals on 60 games, because capture_log spans 26 days. The D028
backfill covers 1,245 games and carries totals AND h2h for every one of them, and neither
has been tested at that scale.

WHY THE MONEYLINE MATTERS MOST. The favourite-longshot bias is classically measured on
MONEYLINES, not spreads, and it is strongest there: a big underdog pays plus-money, and
plus-money prices are where recreational money is most systematically shaded. s04 found the
bias concentrated in large spreads on the point-spread market. The same mechanism predicts
it should appear, larger, on the moneyline of the same games. That prediction is stated
before the test.

WHY A PLUS-MONEY BET IS NOT THE SAME ARITHMETIC. A -110 spread bet risks 1 to win 0.91; a
+250 moneyline risks 1 to win 2.50. The variance per bet is far higher, so a moneyline edge
of the same percentage needs MORE games to confirm, not fewer. The per-game standard
deviation is reported with every result so the sample requirement is visible rather than
assumed.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s01_flat_side_bias as s01  # noqa: E402
import s04_extended_history as s04  # noqa: E402

NAME2ABV = s01.NAME2ABV
MTEAM = os.path.join(s01.ROOT, "data", "masters", "master_team.parquet")


def load_market(market_key):
    """Every pre-tip quote for one market, last per (event, book, outcome)."""
    rows = []
    with open(s04.HIST, encoding="utf-8") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:                      # noqa: BLE001
                continue
            payload = rec.get("payload")
            if not isinstance(payload, list):
                continue
            snap = rec.get("vendor_snapshot_ts") or rec.get("requested_ts")
            for ev in payload:
                tip = ev.get("commence_time")
                if not tip:
                    continue
                for bk in ev.get("bookmakers", []):
                    for mk in bk.get("markets", []):
                        if mk.get("key") != market_key:
                            continue
                        for oc in mk.get("outcomes", []):
                            rows.append({
                                "event_id": ev.get("id"), "tip": tip, "snap": snap,
                                "home_team": ev.get("home_team"),
                                "away_team": ev.get("away_team"),
                                "book": bk.get("key"), "name": oc.get("name"),
                                "point": oc.get("point"), "price": oc.get("price")})
    d = pd.DataFrame(rows)
    d["tip"] = pd.to_datetime(d["tip"], utc=True, errors="coerce")
    d["snap"] = pd.to_datetime(d["snap"], utc=True, errors="coerce")
    d = d.dropna(subset=["tip", "snap", "price"])
    d = d[d["snap"] < d["tip"]]
    d["h"] = d["home_team"].map(NAME2ABV)
    d["a"] = d["away_team"].map(NAME2ABV)
    d = d.dropna(subset=["h", "a"])
    return (d.sort_values("snap")
             .groupby(["event_id", "book", "name"], as_index=False).last())


def game_results():
    mt = pd.read_parquet(MTEAM, columns=["game_id", "game_date", "team_abbreviation",
                                         "is_home", "pts"])
    mt["game_id"] = mt["game_id"].astype(str)
    hm = mt[mt["is_home"] == 1][["game_id", "game_date", "team_abbreviation", "pts"]]
    hm = hm.rename(columns={"team_abbreviation": "h", "pts": "hp"})
    aw = mt[mt["is_home"] == 0][["game_id", "team_abbreviation", "pts"]]
    aw = aw.rename(columns={"team_abbreviation": "a", "pts": "ap"})
    g = hm.merge(aw, on="game_id", how="inner")
    g["gd"] = pd.to_datetime(g["game_date"]).dt.date
    g["game_total"] = g["hp"] + g["ap"]
    return g


def join_results(d, g):
    out = []
    for shift in (0, 1):
        x = d.copy()
        x["gd"] = (x["tip"] - pd.Timedelta(days=shift)).dt.date
        out.append(x.merge(g, on=["h", "a", "gd"], how="inner"))
    m = pd.concat(out, ignore_index=True)
    return m.drop_duplicates(subset=["event_id", "book", "name"])


def summarise(label, sub, rng, res):
    r = s01.clustered_ci(sub, rng)
    if r is None:
        print("   %-26s no data" % label)
        return
    pg = sub.groupby("game_id")["profit"].mean()
    sd = float(pg.std())
    se = sd / np.sqrt(len(pg)) if len(pg) else float("nan")
    need = int(np.ceil((1.96 * sd / r["roi"]) ** 2)) if r["roi"] > 0 else None
    flag = "  <-- CLEARS ZERO" if r["lo"] > 0 else ""
    print("   %-26s %4d games  hit %5.1f%%  ROI %+7.2f%%  [%+.2f%%, %+.2f%%]  sd %.2f%s"
          % (label, r["n_games"], 100 * r["hit"], 100 * r["roi"],
             100 * r["lo"], 100 * r["hi"], sd, flag))
    if need:
        print("      -> %.2f SE from zero; ~%d games would resolve it" % (r["roi"] / se, need))
    res[label] = {**r, "sd": round(sd, 4), "games_needed": need}


def main():
    res = {}
    print("=" * 94)
    print("M43 s05 -- totals and moneylines, 2022-2026")
    print("=" * 94)
    rng = np.random.default_rng(s01.SEED)
    g = game_results()

    # ---------------- TOTALS -----------------------------------------------
    t = join_results(load_market("totals"), g)
    t = t.dropna(subset=["point"])
    t["side"] = t["name"].astype(str).str.strip().str.title()
    t = t[t["side"].isin(["Over", "Under"])]
    diff = t["game_total"] - t["point"]
    t["won"] = np.where(t["side"] == "Over", diff > 0, diff < 0)
    t["push"] = diff == 0
    t["profit"] = s01.american_profit(t["price"].to_numpy(float),
                                      t["won"].to_numpy(), t["push"].to_numpy())
    print("\nTOTALS -- %d quotes over %d games" % (len(t), t["game_id"].nunique()))
    tot = {}
    for side in ("Over", "Under"):
        summarise(side, t[t["side"] == side], rng, tot)
    # best price per game on the better side
    for side in ("Over", "Under"):
        s = t[t["side"] == side]
        best = (s.sort_values(["point", "price"],
                              ascending=[side == "Under", False])
                 .groupby("game_id", as_index=False).first())
        summarise("%s @ best price" % side, best, rng, tot)
    res["totals"] = tot

    # ---------------- MONEYLINE --------------------------------------------
    h = join_results(load_market("h2h"), g)
    h["abv"] = h["name"].map(NAME2ABV)
    h = h.dropna(subset=["abv"])
    h["is_home_side"] = h["abv"] == h["h"]
    h["team_pts"] = np.where(h["is_home_side"], h["hp"], h["ap"])
    h["opp_pts"] = np.where(h["is_home_side"], h["ap"], h["hp"])
    h["won"] = h["team_pts"] > h["opp_pts"]
    h["push"] = False
    h["profit"] = s01.american_profit(h["price"].to_numpy(float),
                                      h["won"].to_numpy(), h["push"].to_numpy())
    h["is_dog"] = h["price"] > 0
    print("\nMONEYLINE -- %d quotes over %d games" % (len(h), h["game_id"].nunique()))
    ml = {}
    summarise("favourite (minus price)", h[~h["is_dog"]], rng, ml)
    summarise("underdog (plus price)", h[h["is_dog"]], rng, ml)

    dog = h[h["is_dog"]].copy()
    # BIG dogs, by the same spirit as s04's spread bands: price is the natural size measure
    per_game = dog.groupby("game_id")["price"].median()
    q1, q2 = per_game.quantile([1 / 3, 2 / 3])
    band = pd.cut(per_game, [-np.inf, q1, q2, np.inf],
                  labels=["short (<=+%.0f)" % q1, "mid", "long (>+%.0f)" % q2])
    dog["band"] = dog["game_id"].map(band)
    print("   by underdog price (prediction: the LONGEST dogs are most shaded)")
    for lbl in band.cat.categories:
        summarise("  %s" % lbl, dog[dog["band"] == lbl], rng, ml)
    best = (dog.sort_values("price", ascending=False)
               .groupby("game_id", as_index=False).first())
    summarise("underdog @ best price", best, rng, ml)
    res["moneyline"] = ml

    with open(os.path.join(HERE, "FINDINGS_s05.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    print("\nwrote FINDINGS_s05.json")


if __name__ == "__main__":
    main()
