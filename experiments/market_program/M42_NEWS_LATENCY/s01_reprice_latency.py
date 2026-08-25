# -*- coding: utf-8 -*-
"""M42 s01 -- when a rotation regular is ruled out, how long until the line moves?

E0-style diagnostic, NON-CLAIMING. Nothing here fits, adopts or ships a model, and no
wager-shaped claim is made. S42 remains closed.

WHY THIS MECHANISM AND NOT ANOTHER. Six routes are closed, and every one of them was a
PRICING or MODEL-ACCURACY play: beating the de-vigged consensus (-7.2%), model-vs-market on
props, middles, line shopping, arbitrage, and stale lines between books. They failed for the
same reason -- the market's number is better than ours. Attacking that again is attacking the
thing that has already been measured and lost six times.

This asks a different question. Not "is our number better than theirs" but "do we know
something before the price does". That only requires the market to be briefly slower than a
scraper, and M39 s02 established the setup: HALF OF ALL 'OUT' DESIGNATIONS BREAK INSIDE 90
MINUTES OF TIP, which is exactly when a book is least attended.

WHAT COUNTS AS NEWS, AND WHY MOST 'OUT' ROWS DO NOT. A player who has been out for three
weeks is not news; her absence is in the price already. An event here requires that the
player was NOT already out for her team's PREVIOUS game -- a state CHANGE, not a state. This
distinction is the difference between measuring a market's reaction and measuring its memory.

ROTATION REGULARS ONLY. A deep-bench absence should not move a total, and counting those
would dilute any real reaction toward zero. The 15-minute threshold is M39's, chosen there
for a different purpose and reused rather than tuned here.

WHAT A POSITIVE RESULT WOULD AND WOULD NOT MEAN. A latency window is necessary but NOT
sufficient for edge. If the line eventually moves DOWN by a predictable amount, a bet placed
in the window is only profitable if the direction was knowable in advance and the move
exceeds the spread we would have paid to enter. Latency is measured here; direction and
magnitude are measured beside it, and neither is a claim until both survive.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Users\jgallagher\wnba-betting-model"
INJ = os.path.join(ROOT, "data", "injury_official_live", "injury_snapshots.csv")
ODDS = os.path.join(ROOT, "data", "odds_capture", "capture_log.csv")
MPLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")

REGULAR_MIN = 15.0          # M39's rotation-regular threshold, reused not tuned
MIN_PRIOR = 3               # games before a trailing mean means anything
HORIZONS = (5, 10, 15, 30, 60, 120)   # minutes after the news

NAME2ABV = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV", "Indiana Fever": "IND",
    "Los Angeles Sparks": "LAS", "Las Vegas Aces": "LVA", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Portland Fire": "PDX", "Phoenix Mercury": "PHX",
    "Seattle Storm": "SEA", "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}


def regulars():
    """(player_id, game_date) -> trailing mean minutes, prior games only."""
    mp = pd.read_parquet(MPLAYER, columns=["player_id", "team_id", "season", "game_date",
                                           "minutes", "game_id"])
    mp["gd"] = pd.to_datetime(mp["game_date"])
    mp["min"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
    mp = mp.sort_values(["player_id", "gd"])
    mp["trail"] = (mp.groupby(["player_id", "season"])["min"]
                     .transform(lambda s: s.shift(1).expanding(min_periods=MIN_PRIOR).mean()))
    return mp


def news_events():
    """First-seen OUT designations that represent a STATE CHANGE, not a standing absence."""
    inj = pd.read_csv(INJ, low_memory=False)
    inj["ret"] = pd.to_datetime(inj["retrieval_ts_utc"], utc=True, errors="coerce")
    inj["gd"] = pd.to_datetime(inj["game_date"], errors="coerce")
    inj = inj.dropna(subset=["ret", "gd", "player_id"]).copy()
    inj["player_id"] = pd.to_numeric(inj["player_id"], errors="coerce")
    inj = inj.dropna(subset=["player_id"])
    inj["player_id"] = inj["player_id"].astype(int)

    out = inj[inj["status"] == "Out"]
    first = (out.groupby(["player_id", "gd", "matchup", "team"])["ret"]
                .min().rename("news_ts").reset_index())

    # a state CHANGE: she was not already Out for this team's previous game date
    first = first.sort_values(["player_id", "gd"])
    prev_gd = first.groupby("player_id")["gd"].shift(1)
    gap_days = (first["gd"] - prev_gd).dt.days
    #: a fresh absence is one with no Out on the immediately preceding game date. Where the
    #: previous Out is more than 3 days back, the intervening game(s) were played, so the
    #: designation is new again. 3 days is the modal WNBA rest gap and is NOT tuned.
    first["is_new"] = prev_gd.isna() | (gap_days > 3)
    return first


def line_series():
    """Consensus total per game over time -- the median across books at each snapshot."""
    d = pd.read_csv(ODDS, low_memory=False)
    d = d[d["market"] == "totals"].copy()
    d["snap"] = pd.to_datetime(d["snapshot_utc"], format="%Y%m%dT%H%M%SZ",
                               errors="coerce", utc=True)
    d["point"] = pd.to_numeric(d["point"], errors="coerce")
    d = d.dropna(subset=["snap", "point"])
    d["h"] = d["home_team"].map(NAME2ABV)
    d["a"] = d["away_team"].map(NAME2ABV)
    d = d.dropna(subset=["h", "a"])
    d["tip"] = pd.to_datetime(d["commence_time"], errors="coerce", utc=True)
    # STRICTLY PRE-TIP ONLY. The capture runs through games, so 6% of rows are IN-PLAY,
    # where the total tracks the game actually being played and its dispersion is far
    # wider (std 14.7 against 9.1). Out news usually breaks inside 90 minutes of tip, so a
    # forward window lands in live prices and reads the game's own scoring as though it
    # were the market repricing an absence. That confound produced a mean absolute "move"
    # of 4.36 points -- impossible pre-game -- and reversed the sign of every slope.
    d = d.dropna(subset=["tip"])
    d = d[d["snap"] < d["tip"]]
    # one consensus number per (game, snapshot): median over books and over/under rows
    g = (d.groupby(["a", "h", "snap"])["point"].median().rename("total").reset_index())
    return g.sort_values("snap")


def main():
    res = {}
    print("=" * 94)
    print("M42 s01 -- reprice latency after a rotation regular is ruled out")
    print("=" * 94)

    ev = news_events()
    mp = regulars()
    key = mp.set_index(["player_id", "gd"])["trail"].to_dict()
    ev["trail"] = [key.get((int(r.player_id), r.gd), np.nan) for r in ev.itertuples()]

    print("\nOut designations, first-seen per player-game : %d" % len(ev))
    print("  of which a STATE CHANGE (not a standing absence): %d" % int(ev["is_new"].sum()))
    ev = ev[ev["is_new"] & (ev["trail"] >= REGULAR_MIN)].copy()
    print("  of which a ROTATION REGULAR (trailing >= %.0f min) : %d" % (REGULAR_MIN, len(ev)))
    res["n_events"] = int(len(ev))
    if not len(ev):
        print("\nNO EVENTS. Nothing to measure; refusing to report an empty set as a result.")
        return

    ls = line_series()
    ev["a"] = ev["matchup"].astype(str).str.upper().str.split("@").str[0].str.strip()
    ev["h"] = ev["matchup"].astype(str).str.upper().str.split("@").str[-1].str.strip()
    ev["a"] = ev["a"].replace({"PHO": "PHX", "POR": "PDX"})
    ev["h"] = ev["h"].replace({"PHO": "PHX", "POR": "PDX"})

    rows, no_cover = [], 0
    for e in ev.itertuples():
        s = ls[(ls["a"] == e.a) & (ls["h"] == e.h)
               & (ls["snap"] >= e.news_ts - pd.Timedelta(hours=6))
               & (ls["snap"] <= e.news_ts + pd.Timedelta(hours=6))]
        before = s[s["snap"] <= e.news_ts]
        after = s[s["snap"] > e.news_ts]
        if before.empty or after.empty:
            no_cover += 1
            continue
        base = float(before.iloc[-1]["total"])
        r = {"player_id": e.player_id, "gd": e.gd, "news_ts": e.news_ts,
             "trail": e.trail, "base_total": base}
        for h in HORIZONS:
            w = after[after["snap"] <= e.news_ts + pd.Timedelta(minutes=h)]
            r["moved_%dm" % h] = (int(abs(float(w.iloc[-1]["total"]) - base) >= 0.5)
                                  if len(w) else np.nan)
            r["delta_%dm" % h] = (float(w.iloc[-1]["total"]) - base) if len(w) else np.nan
        fin = after.iloc[-1]
        r["final_delta"] = float(fin["total"]) - base
        rows.append(r)

    print("\nevents with odds coverage either side of the news: %d (dropped %d)"
          % (len(rows), no_cover))
    if not rows:
        print("\nNO EVENT HAS ODDS COVERAGE ON BOTH SIDES OF THE NEWS.")
        print("This is a COVERAGE result, not a market result: the capture is idle")
        print("03:00-14:00Z and most Out news breaks inside 90 minutes of tip.")
        res["n_covered"] = 0
        with open(os.path.join(HERE, "FINDINGS_s01.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)
        return

    d = pd.DataFrame(rows)
    res["n_covered"] = int(len(d))

    # THE HORIZONS MUST BE SCORED ON THE SAME EVENTS. Coverage differs by horizon, so a
    # first pass compared 7 events at +5m against 19 at +120m and read the difference as
    # latency. That is not a latency curve, it is a COVERAGE CURVE WEARING ONE.
    cols = ["delta_%dm" % h for h in HORIZONS]
    common = d.dropna(subset=cols)
    print("\nCOMMON SUBSET with coverage at EVERY horizon: n=%d (of %d covered)"
          % (len(common), len(d)))
    res["n_common"] = int(len(common))

    print("\n1. HAS THE LINE MOVED BY 0.5+ POINTS, THIS LONG AFTER THE NEWS?")
    tbl = {}
    for h in HORIZONS:
        col = d["moved_%dm" % h].dropna()
        if not len(col):
            continue
        print("   +%-4d min   moved in %5.1f%% of events   (n=%d)  <- varying n, NOT comparable"
              % (h, 100 * col.mean(), len(col)))
        tbl[h] = {"moved_pct": round(float(100 * col.mean()), 1), "n": int(len(col))}
    res["moved_by_horizon"] = tbl

    if len(common):
        print("   on the COMMON subset (the comparable figures):")
        for h in HORIZONS:
            c = common["delta_%dm" % h]
            print("     +%-4d min  moved in %5.1f%%   mean move %+.2f"
                  % (h, 100 * (c.abs() >= 0.5).mean(), c.mean()))
        res["moved_common"] = {h: round(float(100 * (common["delta_%dm" % h].abs() >= 0.5)
                                              .mean()), 1) for h in HORIZONS}

    print("\n2. WHICH WAY, AND HOW FAR? (negative = total came DOWN)")
    fd = (common if len(common) else d)["final_delta"].dropna()
    print("   final move: median %+.2f   mean %+.2f   down in %.0f%% of events"
          % (fd.median(), fd.mean(), 100 * (fd < 0).mean()))

    # A DIRECTION INDISTINGUISHABLE FROM A COIN FLIP CANNOT BE BET, however long the
    # latency window is. This is the test that decides the route, not the latency table.
    if len(fd) > 2:
        rng = np.random.default_rng(20260825)
        bs = [(rng.choice(fd.values, len(fd), replace=True) < 0).mean() for _ in range(4000)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        spans = bool(lo <= 0.5 <= hi)
        print("   down-rate 95%% bootstrap [%.0f%%, %.0f%%] on n=%d"
              % (100 * lo, 100 * hi, len(fd)))
        print("   a coin flip %s this interval." % ("SPANS" if spans else "does NOT span"))
        res["down_rate_ci"] = [round(float(100 * lo), 1), round(float(100 * hi), 1)]
        res["direction_indistinguishable_from_chance"] = spans

    res["final_delta"] = {"median": round(float(fd.median()), 2),
                          "mean": round(float(fd.mean()), 2),
                          "pct_down": round(float(100 * (fd < 0).mean()), 1),
                          "n": int(len(fd))}

    print("\n" + "=" * 94)
    print("A LATENCY WINDOW IS NECESSARY BUT NOT SUFFICIENT. Betting into it pays only if")
    print("the DIRECTION was knowable in advance and the move exceeds the price paid to")
    print("enter. Section 2 is the direction test and it is reported beside the latency,")
    print("never instead of it. Nothing here is a claim.")
    print("=" * 94)

    with open(os.path.join(HERE, "FINDINGS_s01.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    print("\nwrote FINDINGS_s01.json")


if __name__ == "__main__":
    main()
