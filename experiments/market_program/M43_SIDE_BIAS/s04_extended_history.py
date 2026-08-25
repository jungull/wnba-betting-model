# -*- coding: utf-8 -*-
"""M43 s04 -- the same test on FOUR AND A HALF SEASONS instead of one.

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model. S42 closed.

WHY. s02's blocker was arithmetic, not analysis: at +3.46% and a per-game sd near 0.95, the
underdog candidate needs roughly 2,878 games to resolve, and s01 had 406. The answer to a
power problem is data, and the data already existed -- `backfill_market_history.py` (D028,
user-authorised 2026-08-06) pulled two snapshots a day from 2022-05-21 and nobody had used
it for this question.

WHAT THIS DATA IS, AND ITS ONE WEAKNESS. Provenance is T1_VENDOR_ASSERTED: the vendor's
snapshot timestamps were never witnessed by our capture. For a LATENCY question that would
be disqualifying. For a BIAS question it is not -- this needs a price that existed before
tip and an outcome, and both survive the vendor asserting the timestamp. The weakness is
recorded rather than waved away, and it is why this file tests bias and not timing.

STRICTLY PRE-TIP, ENFORCED PER EVENT. Snapshots land at ~16:00Z and ~23:30Z. WNBA games tip
between roughly 23:00Z and 02:00Z, so the SECOND daily snapshot is after tip for some games
and before it for others. Every quote is filtered against its own event's commence_time
rather than by a rule of thumb.

WHAT WOULD FALSIFY THE CANDIDATE. s01-s03 found underdogs +2.49% flat, +3.46% best-price,
and a monotone rise with spread size (+0.05%, +1.74%, +5.98%). If the bias is real those
should broadly survive on four times the data. If they were noise, they will shrink toward
zero -- and that is the expected outcome for most candidates found this way, which is
exactly why this test is worth running before anything is bet.
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

ROOT = s01.ROOT
NAME2ABV = s01.NAME2ABV
HIST = os.path.join(ROOT, "data", "market_snapshots", "historical",
                    "featured_backfill.jsonl")
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")


def load_hist():
    """Every pre-tip spread quote in the backfill, one row per (event, book, team, snap)."""
    rows = []
    with open(HIST, encoding="utf-8") as fh:
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
                        if mk.get("key") != "spreads":
                            continue
                        for oc in mk.get("outcomes", []):
                            rows.append({
                                "event_id": ev.get("id"), "tip": tip, "snap": snap,
                                "home_team": ev.get("home_team"),
                                "away_team": ev.get("away_team"),
                                "book": bk.get("key"), "team": oc.get("name"),
                                "point": oc.get("point"), "price": oc.get("price")})
    d = pd.DataFrame(rows)
    d["tip"] = pd.to_datetime(d["tip"], utc=True, errors="coerce")
    d["snap"] = pd.to_datetime(d["snap"], utc=True, errors="coerce")
    d = d.dropna(subset=["tip", "snap", "point", "price"])
    # PRE-TIP PER EVENT, not by a rule of thumb about snapshot slots
    d = d[d["snap"] < d["tip"]]
    d["abv"] = d["team"].map(NAME2ABV)
    d["h"] = d["home_team"].map(NAME2ABV)
    d["a"] = d["away_team"].map(NAME2ABV)
    d = d.dropna(subset=["abv", "h", "a"])
    # the LAST pre-tip quote each book showed: the price we could actually have taken
    d = (d.sort_values("snap")
           .groupby(["event_id", "book", "abv"], as_index=False).last())
    return d


def attach_outcomes(d):
    mt = pd.read_parquet(MTEAM, columns=["game_id", "game_date", "team_abbreviation",
                                         "is_home", "pts", "opp_team_abbreviation"])
    mt["game_id"] = mt["game_id"].astype(str)
    opp = mt[["game_id", "team_abbreviation", "pts"]].rename(
        columns={"team_abbreviation": "opp_team_abbreviation", "pts": "opp_pts"})
    mt = mt.merge(opp, on=["game_id", "opp_team_abbreviation"], how="left")
    mt = mt.rename(columns={"team_abbreviation": "abv"})
    mt["gd"] = pd.to_datetime(mt["game_date"]).dt.date

    # an ET evening game carries the NEXT UTC date, so try the tip date and the day before
    out = []
    for shift in (0, 1):
        x = d.copy()
        x["gd"] = (x["tip"] - pd.Timedelta(days=shift)).dt.date
        m = x.merge(mt[["game_id", "abv", "gd", "is_home", "pts", "opp_pts"]],
                    on=["abv", "gd"], how="inner")
        out.append(m)
    m = pd.concat(out, ignore_index=True)
    m = m.drop_duplicates(subset=["event_id", "book", "abv"])
    m = m.dropna(subset=["pts", "opp_pts"])
    m["margin"] = m["pts"] - m["opp_pts"]
    m["ats"] = m["margin"] + m["point"]
    m["won"] = m["ats"] > 0
    m["push"] = m["ats"] == 0
    m["profit"] = s01.american_profit(m["price"].to_numpy(float),
                                      m["won"].to_numpy(), m["push"].to_numpy())
    m["is_fav"] = m["point"] < 0
    m["odds_spread"] = m["point"]
    return m


def main():
    res = {}
    print("=" * 94)
    print("M43 s04 -- the underdog candidate on four and a half seasons")
    print("=" * 94)

    d = attach_outcomes(load_hist())
    d["season"] = pd.to_datetime(d["tip"]).dt.year
    print("\nsettled pre-tip spread quotes: %d over %d games, %d books"
          % (len(d), d["game_id"].nunique(), d["book"].nunique()))
    print("seasons: %s" % sorted(d["season"].unique().tolist()))
    res["n_quotes"] = int(len(d))
    res["n_games"] = int(d["game_id"].nunique())

    rng = np.random.default_rng(s01.SEED)
    print("\n1. THE FOUR STANDING SIDES, RE-TESTED")
    tbl = {}
    for name, sub in (("HOME", d[d["is_home"] == 1]), ("AWAY", d[d["is_home"] == 0]),
                      ("FAVOURITE", d[d["is_fav"]]), ("UNDERDOG", d[~d["is_fav"]])):
        r = s01.clustered_ci(sub, rng)
        if r is None:
            continue
        flag = "  <-- CLEARS ZERO" if r["lo"] > 0 else ""
        print("   %-11s %5d games  hit %5.1f%%  ROI %+6.2f%%  [%+.2f%%, %+.2f%%]%s"
              % (name, r["n_games"], 100 * r["hit"], 100 * r["roi"],
                 100 * r["lo"], 100 * r["hi"], flag))
        tbl[name] = r
    res["sides"] = tbl

    print("\n2. DOES THE UNDERDOG EDGE STILL GROW WITH THE SPREAD?")
    dog = d[~d["is_fav"]].copy()
    per_game = dog.groupby("game_id")["odds_spread"].median().abs()
    q1, q2 = per_game.quantile([1 / 3, 2 / 3])
    band = pd.cut(per_game, [-np.inf, q1, q2, np.inf],
                  labels=["small (<=%.1f)" % q1, "mid", "large (>%.1f)" % q2])
    dog["band"] = dog["game_id"].map(band)
    conc = {}
    for lbl in band.cat.categories:
        sub = dog[dog["band"] == lbl]
        r = s01.clustered_ci(sub, rng)
        if r is None:
            continue
        flag = "  <-- CLEARS ZERO" if r["lo"] > 0 else ""
        print("   %-16s %5d games  hit %5.1f%%  ROI %+6.2f%%  [%+.2f%%, %+.2f%%]%s"
              % (lbl, r["n_games"], 100 * r["hit"], 100 * r["roi"],
                 100 * r["lo"], 100 * r["hi"], flag))
        conc[str(lbl)] = r
    rois = [conc[str(l)]["roi"] for l in band.cat.categories if str(l) in conc]
    mono = len(rois) == 3 and rois[0] < rois[1] < rois[2]
    print("   monotonic with spread size, as s03 predicted? %s" % ("YES" if mono else "NO"))
    res["concentration"] = conc
    res["monotonic"] = bool(mono)

    print("\n3. SEASON BY SEASON (underdog, flat) -- is it a persistent effect?")
    per_season = {}
    for s, g in dog.groupby("season"):
        r = s01.clustered_ci(g, rng)
        if r is None:
            continue
        print("   %-6s %5d games  hit %5.1f%%  ROI %+6.2f%%  [%+.2f%%, %+.2f%%]"
              % (s, r["n_games"], 100 * r["hit"], 100 * r["roi"],
                 100 * r["lo"], 100 * r["hi"]))
        per_season[int(s)] = r
    res["per_season"] = per_season
    pos = sum(1 for v in per_season.values() if v["roi"] > 0)
    print("   seasons with a positive return: %d of %d" % (pos, len(per_season)))
    res["seasons_positive"] = [pos, len(per_season)]

    with open(os.path.join(HERE, "FINDINGS_s04.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    print("\nwrote FINDINGS_s04.json")


if __name__ == "__main__":
    main()
