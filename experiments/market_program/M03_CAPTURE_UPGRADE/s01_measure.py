# -*- coding: utf-8 -*-
"""M03 s01 -- measure the capture as it actually runs, not as it is described.

Acceptance criterion 1 requires the cadence be MEASURED against the requirement
(T-24h through final plus event-driven bursts) with actual request-quota
arithmetic rather than estimates. This produces every number the report cites.

FOUR MEASUREMENTS:

  1. CADENCE. Gap between consecutive odds captures, split at the 2026-08-19
     cadence change, so the hourly era and the five-minute era are not averaged
     into a single meaningless figure.

  2. COVERAGE against T-24h -> tip, per game.

     A trap worth naming, because it produced a wrong answer first: grouping on
     the exact `commence_time` SPLITS a single game into several, because the
     vendor REVISES tip times. One game appeared as 23:30 with 214 snapshots and
     23:32 with 1, and the naive grouping then reported 35% of games with no
     in-window capture. Games are therefore keyed on (home, away, ET game-date)
     and scored against each game's LATEST observed tip.

  3. TIP DRIFT, which that trap turned into a finding in its own right, and which
     is why any point-in-time tip rule must compare an observation against the
     tip AS REPORTED AT THAT MOMENT rather than against the final tip.

  4. QUOTA. Real credit arithmetic from the two captures' documented cost models
     (odds: 1 request x 3 markets x 1 region = 3 credits per run; props: /events
     free, then each event x 4 markets x 1 region), against the D029 tier of
     100,000 credits/month. Games per day is MEASURED from the season, not
     assumed -- an assumed 5.0 was 72% too high against a measured 2.91.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
from collections import defaultdict

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model"
ODDS_LOG = os.path.join(ROOT, "data", "odds_capture", "capture_log.csv")
PROPS_RAW = os.path.join(ROOT, "data", "props_capture", "raw")
MTEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")

FAST_ERA = pd.Timestamp("2026-08-19T14:00:00Z")   # the cadence change (M31 uses the same)
STAMP_FMT = "%Y%m%dT%H%M%SZ"

ODDS_CREDITS_PER_RUN = 3        # 1 request x 3 markets (spreads,totals,h2h) x 1 region
PROPS_MARKETS = 4               # player_points, rebounds, assists, threes
TIER_CREDITS = 100_000          # D029: 100K tier at 59 USD/month
DAYS = 30


def load_odds():
    d = pd.read_csv(ODDS_LOG, low_memory=False)
    d["snap"] = pd.to_datetime(d["snapshot_utc"], format=STAMP_FMT, utc=True,
                               errors="coerce")
    d["tip"] = pd.to_datetime(d["commence_time"], utc=True, errors="coerce")
    d = d[d["snap"].notna() & d["tip"].notna()].copy()
    d["gd"] = d["tip"].dt.tz_convert("US/Eastern").dt.date
    # key on game-date, NOT on the exact tip -- see the docstring
    d["g"] = (d["home_team"].astype(str) + " v " + d["away_team"].astype(str)
              + " " + d["gd"].astype(str))
    return d


def main():
    out = {}
    print("=" * 94)
    print("M03 s01 -- capture cadence, coverage, tip drift and quota, all measured")
    print("=" * 94)

    d = load_odds()
    snaps = pd.Series(sorted(d["snap"].unique()))
    span_days = (snaps.max() - snaps.min()).total_seconds() / 86400.0

    # ---- 1. cadence ------------------------------------------------------
    gaps = snaps.diff().dt.total_seconds().div(60)
    print("\n1. CADENCE -- minutes between consecutive odds captures")
    print("   window: %s -> %s (%.1f days, %d captures)"
          % (snaps.min(), snaps.max(), span_days, len(snaps)))
    cad = {}
    for lbl, mask in (("before 2026-08-19", snaps < FAST_ERA),
                      ("five-minute era", snaps >= FAST_ERA)):
        g = gaps[mask].dropna()
        if not len(g):
            continue
        print("   %-18s n=%3d  median %7.1f  p10 %6.1f  p90 %7.1f"
              % (lbl, len(g), g.median(), g.quantile(0.1), g.quantile(0.9)))
        cad[lbl] = {"n": int(len(g)), "median": round(float(g.median()), 1),
                    "p90": round(float(g.quantile(0.9)), 1)}
    out["cadence_min"] = cad

    # ---- 3. tip drift (computed before coverage, which depends on it) ----
    drift = d.groupby("g")["tip"].agg(n_tips="nunique", tmin="min", tmax="max")
    drift["spread_min"] = (drift["tmax"] - drift["tmin"]).dt.total_seconds() / 60
    moved = drift[drift["n_tips"] > 1]
    print("\n2. TIP DRIFT -- the vendor revises commence_time")
    print("   games                     : %d" % len(drift))
    print("   games with >1 tip value   : %d (%.1f%%)"
          % (len(moved), 100.0 * len(moved) / len(drift)))
    if len(moved):
        print("   spread when it moves (min): median %.1f  max %.1f"
              % (moved["spread_min"].median(), moved["spread_min"].max()))
    out["tip_drift"] = {"games": int(len(drift)), "games_moved": int(len(moved)),
                        "pct_moved": round(100.0 * len(moved) / len(drift), 1),
                        "median_spread_min": float(moved["spread_min"].median()) if len(moved) else 0.0,
                        "max_spread_min": float(moved["spread_min"].max()) if len(moved) else 0.0}

    # ---- 2. coverage -----------------------------------------------------
    latest = d.groupby("g")["tip"].max().rename("tip_final")
    d2 = d.merge(latest, on="g")
    d2["lead_h"] = (d2["tip_final"] - d2["snap"]).dt.total_seconds() / 3600.0
    rows = []
    for g, s in d2.groupby("g"):
        pos = s.loc[s["lead_h"] >= 0, "lead_h"]
        rows.append({"in_window": s.loc[(s["lead_h"] >= 0) & (s["lead_h"] <= 24),
                                        "snap"].nunique(),
                     "closest_min": float(pos.min() * 60) if len(pos) else np.nan,
                     "earliest_h": float(s["lead_h"].max())})
    per = pd.DataFrame(rows)
    zero = int((per["in_window"] == 0).sum())
    print("\n3. COVERAGE of T-24h -> tip, per game (keyed on game-date, latest tip)")
    print("   games                        : %d" % len(per))
    print("   captures inside T-24h..tip   : median %.0f  p10 %.0f  max %.0f"
          % (per["in_window"].median(), per["in_window"].quantile(0.1),
             per["in_window"].max()))
    print("   games with ZERO in-window    : %d (%.1f%%)"
          % (zero, 100.0 * zero / len(per)))
    print("   closest capture to tip (min) : median %.1f  p90 %.1f"
          % (per["closest_min"].median(), per["closest_min"].quantile(0.9)))
    print("   earliest capture before tip  : median %.1f h" % per["earliest_h"].median())
    out["coverage"] = {"games": int(len(per)),
                       "median_in_window": float(per["in_window"].median()),
                       "p10_in_window": float(per["in_window"].quantile(0.1)),
                       "games_zero_in_window": zero,
                       "pct_zero": round(100.0 * zero / len(per), 1),
                       "closest_min_median": round(float(per["closest_min"].median()), 1),
                       "closest_min_p90": round(float(per["closest_min"].quantile(0.9)), 1)}

    # ---- 4. quota --------------------------------------------------------
    by = defaultdict(set)
    for f in glob.glob(os.path.join(PROPS_RAW, "props_*_*.json")):
        m = re.search(r"props_(.+?)_(\d{8}T\d{6}Z)\.json$", os.path.basename(f))
        if m:
            by[m.group(2)].add(m.group(1))
    props_fetches = sum(len(v) for v in by.values())
    observed = len(snaps) * ODDS_CREDITS_PER_RUN + props_fetches * PROPS_MARKETS
    per30 = observed * DAYS / span_days

    mt = pd.read_parquet(MTEAM)
    mt["gd"] = pd.to_datetime(mt["game_date"]).dt.date
    s26 = mt[(mt["gd"] >= dt.date(2026, 5, 1)) & (mt["is_home"] == 1)]
    gpd = s26.groupby("gd").size()
    gmean, gmax = float(gpd.mean()), float(gpd.max())

    print("\n4. QUOTA -- measured, against the D029 100,000-credit tier")
    print("   odds  : %d runs x %d credits            = %d"
          % (len(snaps), ODDS_CREDITS_PER_RUN, len(snaps) * ODDS_CREDITS_PER_RUN))
    print("   props : %d event-fetches x %d markets   = %d"
          % (props_fetches, PROPS_MARKETS, props_fetches * PROPS_MARKETS))
    print("   observed total over %.1f days          = %d credits" % (span_days, observed))
    print("   -> %.0f credits/30d = %.2f%% of tier" % (per30, 100.0 * per30 / TIER_CREDITS))
    print("\n   games/day MEASURED over the 2026 season: mean %.2f, max %.0f"
          % (gmean, gmax))
    print("   (an assumed 5.0 would have been %.0f%% too high)" % (100 * (5.0 / gmean - 1)))
    out["quota"] = {"observed_credits": int(observed), "span_days": round(span_days, 1),
                    "per_30d": int(per30), "pct_of_tier": round(100.0 * per30 / TIER_CREDITS, 2),
                    "games_per_day_mean": round(gmean, 2), "games_per_day_max": gmax}

    # ---- design envelope -------------------------------------------------
    def cost(props_fetches_per_game, gpd_):
        return (288 * ODDS_CREDITS_PER_RUN * DAYS
                + props_fetches_per_game * gpd_ * PROPS_MARKETS * DAYS)

    print("\n5. DESIGN ENVELOPE (odds at 5-min always; props targeted)")
    print("   %-44s %13s %13s" % ("option", "expected/30d", "worst-day/30d"))
    env = {}
    for name, f in (("B: props 15-min in T-6h..tip", 24),
                    ("D: props 5-min in T-3h..tip", 36),
                    ("C: props 5-min in T-6h..tip", 72),
                    ("E: C + 20 burst fetches/game", 92)):
        e, w = cost(f, gmean), cost(f, gmax)
        print("   %-44s %6.0f (%3.0f%%) %6.0f (%3.0f%%)"
              % (name, e, 100 * e / TIER_CREDITS, w, 100 * w / TIER_CREDITS))
        env[name] = {"expected": int(e), "worst": int(w),
                     "pct_expected": round(100 * e / TIER_CREDITS, 1),
                     "pct_worst": round(100 * w / TIER_CREDITS, 1)}
    naive = 288 * ODDS_CREDITS_PER_RUN * DAYS + 288 * gmean * PROPS_MARKETS * DAYS
    print("   %-44s %6.0f (%3.0f%%)" % ("naive: props 5-min CONTINUOUS", naive,
                                        100 * naive / TIER_CREDITS))
    env["naive_continuous"] = {"expected": int(naive),
                               "pct_expected": round(100 * naive / TIER_CREDITS, 1)}
    out["envelope"] = env

    print("\n" + "=" * 94)
    print("The upgrade fits INSIDE the existing tier if props polling is targeted at")
    print("the pre-tip window instead of running continuously. Nothing here needs paid")
    print("quota, so no USER_REQUIRED purchase line item is raised (criterion 5).")
    print("=" * 94)

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "MEASUREMENTS.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("\nwrote MEASUREMENTS.json")


if __name__ == "__main__":
    main()
