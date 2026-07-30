#!/usr/bin/env python3
"""
Historical odds backfill: The Odds API /historical snapshots for every WNBA game date
from 2025-07-05 (master_odds.csv ends 2025-07-04) through yesterday.

Two snapshots per game date:
  15:00 UTC (11am ET)  - before matinees, evening lines already posted
  22:00 UTC (6pm ET)   - near-closing for the main evening slate

Cost: 10 credits x 3 markets x 1 region = 30 per snapshot, 60 per game date.
~150 game dates -> ~9,000 credits of the 20K monthly allowance. The script prints
remaining credits every call and stops cleanly on auth/credit errors.

Game dates come from data/refresh_2026/gamelog_team_{2025,2026}_*.parquet, so run
AFTER collect_refresh.py has finished. Resumable: one JSON per date+time in
data/odds_capture/historical/; existing files are skipped.
"""
import json
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from odds_capture_daily import api_key

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "data" / "odds_capture" / "historical"
OUTDIR.mkdir(parents=True, exist_ok=True)
MARKETS = "spreads,totals,h2h"
CUTOFF_LOW = "2025-07-05"
SNAP_TIMES = ("15:00:00Z", "22:00:00Z")


def game_dates():
    fr = ROOT / "data" / "refresh_2026"
    files = sorted(fr.glob("gamelog_team_2025_*.parquet")) + sorted(fr.glob("gamelog_team_2026_*.parquet"))
    if not files:
        sys.exit("No refresh gamelogs found - run collect_refresh.py first")
    dates = set()
    for f in files:
        d = pd.read_parquet(f)
        dates |= set(pd.to_datetime(d.GAME_DATE).dt.date)
    return sorted(x for x in dates if str(x) >= CUTOFF_LOW and x < date.today())


def main():
    key = api_key()
    dates = game_dates()
    todo = [(d, t) for d in dates for t in SNAP_TIMES
            if not (OUTDIR / f"hist_{d}_{t[:2]}Z.json").exists()]
    print(f"{len(dates)} game dates in range; {len(todo)} snapshots to fetch")
    for n, (d, t) in enumerate(todo, 1):
        r = requests.get(
            "https://api.the-odds-api.com/v4/historical/sports/basketball_wnba/odds",
            params={"apiKey": key, "regions": "us", "markets": MARKETS,
                    "oddsFormat": "american", "date": f"{d}T{t}"},
            timeout=30)
        if r.status_code != 200:
            print(f"  {d} {t}: HTTP {r.status_code} {r.text[:120]}")
            if r.status_code in (401, 402, 422, 429):
                sys.exit("Stopping (auth/credits/plan). Fix and rerun - it resumes.")
            time.sleep(3)
            continue
        payload = r.json()
        (OUTDIR / f"hist_{d}_{t[:2]}Z.json").write_text(json.dumps(payload, indent=1))
        games = payload.get("data", [])
        print(f"  [{n}/{len(todo)}] {d} {t[:2]}Z: {len(games)} games | "
              f"credits remaining {r.headers.get('x-requests-remaining')}")
        time.sleep(1)
    print("Backfill complete.")


if __name__ == "__main__":
    main()
