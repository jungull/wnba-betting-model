# -*- coding: utf-8 -*-
"""M42 s02 -- does the line move SCALE with how much scoring the absence removes?

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model. S42 closed.

WHY s01 WAS THE WRONG TEST. s01 asked whether the total goes DOWN when a rotation regular
is ruled out, and got 3 of 7 -- a coin flip. But that pools a leading scorer with a defensive
specialist and asks them the same yes/no question. If the market reacts in PROPORTION to the
scoring removed, pooling by sign is exactly how a real reaction is destroyed: the small
absences add noise with the same weight as the large ones, and the binomial throws away the
magnitude that carries the signal.

THE BETTER TEST. Every absence has a size -- the player's trailing points per game, which is
what the market must reprice. So the question becomes a SLOPE, not a sign: does a bigger
absence move the line further? That uses every event, keeps the magnitude, and has far more
power than a 7-event binomial.

AND THE SPREAD, NOT ONLY THE TOTAL. A total nets two teams together, so a star sitting moves
it only through the scoring he removes. The SPREAD is directional by construction: the
affected team should get worse. That is a cleaner target and it is tested here beside totals.

WHAT WOULD MAKE THIS TRADEABLE, AND WHAT WOULD NOT. A slope that is real and estimated BEFORE
the market moves would let us predict the reprice and bet into the latency window s01 found.
A slope that only appears after the fact, or whose confidence interval spans zero, would not.
The interval is reported for every slope and no slope is quoted without it.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import s01_reprice_latency as s01  # noqa: E402

ROOT = s01.ROOT
MPLAYER = s01.MPLAYER
ODDS = s01.ODDS
NAME2ABV = s01.NAME2ABV
MIN_PRIOR = s01.MIN_PRIOR

WINDOW_H = 6          # hours either side of the news to look for coverage
SEED = 20260825


def player_size():
    """Trailing points per game and minutes, prior games only -- the size of the absence."""
    mp = pd.read_parquet(MPLAYER, columns=["player_id", "team_id", "team_abbreviation",
                                           "season", "game_date", "minutes", "pts"])
    mp["gd"] = pd.to_datetime(mp["game_date"])
    mp["min"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp["pts"] = pd.to_numeric(mp["pts"], errors="coerce").fillna(0.0)
    mp = mp.sort_values(["player_id", "gd"])
    for col, src in (("trail_pts", "pts"), ("trail_min", "min")):
        mp[col] = (mp.groupby(["player_id", "season"])[src]
                     .transform(lambda s: s.shift(1).expanding(min_periods=MIN_PRIOR).mean()))
    return mp


def spread_series():
    """Per (game, team) handicap over time -- the team-directional market."""
    d = pd.read_csv(ODDS, low_memory=False)
    d = d[d["market"] == "spreads"].copy()
    d["snap"] = pd.to_datetime(d["snapshot_utc"], format="%Y%m%dT%H%M%SZ",
                               errors="coerce", utc=True)
    d["point"] = pd.to_numeric(d["point"], errors="coerce")
    d = d.dropna(subset=["snap", "point"])
    d["h"] = d["home_team"].map(NAME2ABV)
    d["a"] = d["away_team"].map(NAME2ABV)
    d["tm"] = d["outcome"].map(NAME2ABV)
    d["tip"] = pd.to_datetime(d["commence_time"], errors="coerce", utc=True)
    d = d.dropna(subset=["h", "a", "tm", "tip"])
    # STRICTLY PRE-TIP -- same confound as the totals series. An in-play handicap tracks the
    # game being played, so a forward window that crosses tip reads the scoreboard as if it
    # were the market repricing an absence.
    d = d[d["snap"] < d["tip"]]
    return (d.groupby(["a", "h", "tm", "snap"])["point"].median()
             .rename("spread").reset_index().sort_values("snap"))


def slope_ci(x, y, n_boot=4000):
    """OLS slope with a bootstrap interval. Reported together, never apart."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if len(x) < 5 or np.std(x) == 0:
        return None
    b = np.polyfit(x, y, 1)[0]
    rng = np.random.default_rng(SEED)
    bs = []
    for _ in range(n_boot):
        i = rng.integers(0, len(x), len(x))
        if np.std(x[i]) == 0:
            continue
        bs.append(np.polyfit(x[i], y[i], 1)[0])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"slope": float(b), "lo": float(lo), "hi": float(hi), "n": int(len(x))}


def report(label, unit, r):
    if r is None:
        print("   %-34s too few events to estimate" % label)
        return
    spans = r["lo"] <= 0 <= r["hi"]
    print("   %-34s %+.3f %s  95%% [%+.3f, %+.3f]  n=%d  %s"
          % (label, r["slope"], unit, r["lo"], r["hi"], r["n"],
             "SPANS ZERO" if spans else "excludes zero"))
    return spans


def main():
    res = {}
    print("=" * 94)
    print("M42 s02 -- does the reprice SCALE with the scoring removed?")
    print("=" * 94)

    ev = s01.news_events()
    ev = ev[ev["is_new"]].copy()
    ps = player_size()
    tp = ps.set_index(["player_id", "gd"])["trail_pts"].to_dict()
    tm = ps.set_index(["player_id", "gd"])["trail_min"].to_dict()
    ev["trail_pts"] = [tp.get((int(r.player_id), r.gd), np.nan) for r in ev.itertuples()]
    ev["trail_min"] = [tm.get((int(r.player_id), r.gd), np.nan) for r in ev.itertuples()]
    ev = ev.dropna(subset=["trail_pts"])
    ev["a"] = ev["matchup"].astype(str).str.upper().str.split("@").str[0].str.strip()
    ev["h"] = ev["matchup"].astype(str).str.upper().str.split("@").str[-1].str.strip()
    for c in ("a", "h"):
        ev[c] = ev[c].replace({"PHO": "PHX", "POR": "PDX"})
    # The injury tape carries the team as a FULL NAME ("Las Vegas Aces"), not an
    # abbreviation. A first version uppercased it and matched against "LVA", which produced
    # ZERO spread coverage -- and a broken join reports exactly like an absent market.
    ev["team"] = ev["team"].map(NAME2ABV)

    print("\nstate-change absences with a trailing scoring rate: %d" % len(ev))
    print("scoring removed: median %.1f pts, max %.1f"
          % (ev["trail_pts"].median(), ev["trail_pts"].max()))
    res["n_events"] = int(len(ev))

    tot = s01.line_series()
    spr = spread_series()

    rows = []
    for e in ev.itertuples():
        lo_t, hi_t = e.news_ts - pd.Timedelta(hours=WINDOW_H), e.news_ts + pd.Timedelta(hours=WINDOW_H)
        t = tot[(tot["a"] == e.a) & (tot["h"] == e.h) & (tot["snap"] >= lo_t) & (tot["snap"] <= hi_t)]
        tb, ta = t[t["snap"] <= e.news_ts], t[t["snap"] > e.news_ts]
        r = {"trail_pts": e.trail_pts, "trail_min": e.trail_min}
        if len(tb) and len(ta):
            r["d_total"] = float(ta.iloc[-1]["total"]) - float(tb.iloc[-1]["total"])
        s = spr[(spr["a"] == e.a) & (spr["h"] == e.h) & (spr["tm"] == e.team)
                & (spr["snap"] >= lo_t) & (spr["snap"] <= hi_t)]
        sb, sa = s[s["snap"] <= e.news_ts], s[s["snap"] > e.news_ts]
        if len(sb) and len(sa):
            # a team getting WORSE means its handicap rises (more points given)
            r["d_spread"] = float(sa.iloc[-1]["spread"]) - float(sb.iloc[-1]["spread"])
        rows.append(r)

    d = pd.DataFrame(rows)
    n_tot = int(d["d_total"].notna().sum()) if "d_total" in d else 0
    n_spr = int(d["d_spread"].notna().sum()) if "d_spread" in d else 0
    print("events with coverage -- totals: %d, spreads: %d" % (n_tot, n_spr))
    res["n_total_cov"], res["n_spread_cov"] = n_tot, n_spr

    print("\nDOES THE MOVE SCALE WITH THE ABSENCE? (slope per point of scoring removed)")
    out = {}
    if n_tot:
        r = slope_ci(d["trail_pts"], d["d_total"])
        out["total_vs_pts"] = r
        report("total move / pt removed", "pts", r)
    if n_spr:
        r = slope_ci(d["trail_pts"], d["d_spread"])
        out["spread_vs_pts"] = r
        report("spread move / pt removed", "pts", r)
    if n_tot:
        r = slope_ci(d["trail_min"], d["d_total"])
        out["total_vs_min"] = r
        report("total move / min removed", "pts", r)
    res["slopes"] = {k: v for k, v in out.items()}

    print("\n" + "=" * 94)
    real = [k for k, v in out.items() if v and not (v["lo"] <= 0 <= v["hi"])]
    if real:
        print("A SLOPE EXCLUDING ZERO: %s." % ", ".join(real))
        print("That is necessary, not sufficient. To trade it the slope must be estimable")
        print("BEFORE the move, and the predicted reprice must exceed the price paid to")
        print("enter. Neither is shown here.")
    else:
        print("EVERY SLOPE SPANS ZERO. The market's reaction does not measurably scale with")
        print("the scoring removed on this sample, so s01's coin-flip direction is not")
        print("rescued by conditioning on the size of the absence.")
        print("")
        print("This is UNDERPOWERED, not refuted: the events are few and the odds coverage")
        print("thinner still. It says the route is unmeasured, not that it is closed.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s02.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=float)
    print("\nwrote FINDINGS_s02.json")


if __name__ == "__main__":
    main()
