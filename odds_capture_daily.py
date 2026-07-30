#!/usr/bin/env python3
"""
Daily WNBA odds snapshot capture (The Odds API v4, live odds endpoint).

Cost per run: 1 credit x 3 markets x 1 region = 3 credits (trivial on any tier).
Scheduled twice daily (noon + 6:30pm local) via Windows Task Scheduler task
"WNBA_OddsCapture" so we get an early line and a near-closing line per game.

Writes one raw JSON per run to data/odds_capture/ and appends a flat
row-per-outcome log to data/odds_capture/capture_log.csv (hand-inspectable).
API key: ODDS_API_KEY env var, else .env at repo root (git-ignored).
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "data" / "odds_capture"
OUTDIR.mkdir(parents=True, exist_ok=True)
MARKETS = "spreads,totals,h2h"


def api_key():
    k = os.getenv("ODDS_API_KEY")
    if k:
        return k
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("ODDS_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("No ODDS_API_KEY in environment or .env")


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    r = requests.get(
        "https://api.the-odds-api.com/v4/sports/basketball_wnba/odds",
        params={"apiKey": api_key(), "regions": "us", "markets": MARKETS,
                "oddsFormat": "american"},
        timeout=30)
    r.raise_for_status()
    games = r.json()
    (OUTDIR / f"live_{stamp}.json").write_text(json.dumps(games, indent=1))

    logf = OUTDIR / "capture_log.csv"
    new = not logf.exists()
    with open(logf, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["snapshot_utc", "commence_time", "home_team", "away_team",
                        "bookmaker", "market", "outcome", "point", "price"])
        for g in games:
            for b in g.get("bookmakers", []):
                for mk in b.get("markets", []):
                    for o in mk.get("outcomes", []):
                        w.writerow([stamp, g["commence_time"], g["home_team"],
                                    g["away_team"], b["key"], mk["key"],
                                    o.get("name"), o.get("point"), o.get("price")])
    print(f"{stamp}: {len(games)} upcoming games captured | "
          f"credits used {r.headers.get('x-requests-used')}, "
          f"remaining {r.headers.get('x-requests-remaining')}")


if __name__ == "__main__":
    main()
