#!/usr/bin/env python3
"""
Daily WNBA player-props snapshot capture (The Odds API v4, per-event odds endpoint).

Props cannot be backfilled (no historical props on our plan) - every day not
captured is gone. This script captures ONCE per invocation, designed to be run
at 3 fixed times daily (10:05, 15:05, 19:35 ET) by the orchestrator's scheduler
(intentionally NOT created here).

Cost per run: /events is free; each event costs [markets] x [regions] credits,
so 4 markets x us x N events = 4N credits per snapshot (verified 2026-07-31:
x-requests-last = 1 for 1 market x 1 region). Typical slate 2-4 events ->
8-16 credits/snapshot, ~25-50/day at 3 snapshots. Does NOT fit the 500/month
free tier; fine on the paid month (see experiments/props_capture_setup/REPORT.md).

Writes one raw JSON per event per snapshot to data/props_capture/raw/
(props_<eventid>_<UTCstamp>.json) and appends flattened over/under rows to
data/props_capture/master_props.csv. Idempotent per (event, book, market,
player, line, snapshot). Credit headers printed every call. Explicit counts on
empty slates and missing/suspended markets - never silent.
API key: ODDS_API_KEY env var, else .env at repo root (git-ignored, never logged).
"""
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from odds_capture_daily import api_key

ROOT = Path(__file__).resolve().parent
OUTDIR = ROOT / "data" / "props_capture"
RAWDIR = OUTDIR / "raw"
RAWDIR.mkdir(parents=True, exist_ok=True)
MASTER = OUTDIR / "master_props.csv"
BASE = "https://api.the-odds-api.com/v4/sports/basketball_wnba"
MARKETS = ["player_points", "player_rebounds", "player_assists", "player_threes"]
WINDOW_HOURS = 36
COLUMNS = ["api_event_id", "home_team", "away_team", "commence_time",
           "bookmaker_key", "market_key", "player_name", "line",
           "over_price", "under_price", "snapshot_utc", "last_update"]


def log_credits(r, label):
    print(f"  [{label}] HTTP {r.status_code} | credits used "
          f"{r.headers.get('x-requests-used')} | remaining "
          f"{r.headers.get('x-requests-remaining')} | last-cost "
          f"{r.headers.get('x-requests-last')}")


def upcoming_events(key):
    """Events commencing within the next WINDOW_HOURS (free call)."""
    r = requests.get(f"{BASE}/events", params={"apiKey": key}, timeout=30)
    log_credits(r, "events")
    r.raise_for_status()
    now = datetime.now(timezone.utc)
    lo = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    hi = (now + timedelta(hours=WINDOW_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    events = r.json()
    picked = [e for e in events if lo < e["commence_time"] <= hi]
    print(f"{len(events)} events listed; {len(picked)} commence within {WINDOW_HOURS}h")
    return picked


def fetch_event_props(key, ev, markets):
    """One call per event, markets comma-joined. On a 422 naming a bad market,
    drop it and retry once (failed requests cost 0 credits)."""
    r = requests.get(f"{BASE}/events/{ev['id']}/odds",
                     params={"apiKey": key, "regions": "us",
                             "markets": ",".join(markets),
                             "oddsFormat": "american"},
                     timeout=30)
    log_credits(r, f"{ev['away_team']} at {ev['home_team']}")
    if r.status_code == 422:
        bad = [m for m in markets if m in r.text]
        keep = [m for m in markets if m not in bad]
        print(f"  422 rejected markets {bad or ['<unparsed>']}: {r.text[:160]}")
        if keep and bad:
            print(f"  retrying with {keep}")
            return fetch_event_props(key, ev, keep)
        return None
    if r.status_code != 200:
        print(f"  skipping event: HTTP {r.status_code} {r.text[:160]}")
        return None
    return r.json()


def flatten(ev_json, stamp):
    """Row per (book, market, player, line): over/under paired on exact point,
    so alternate lines (same player, several points) each get their own row."""
    rows = {}
    for b in ev_json.get("bookmakers", []):
        for mk in b.get("markets", []):
            for o in mk.get("outcomes", []):
                k = (ev_json["id"], b["key"], mk["key"],
                     o.get("description"), o.get("point"), stamp)
                row = rows.setdefault(k, {
                    "api_event_id": ev_json["id"],
                    "home_team": ev_json.get("home_team"),
                    "away_team": ev_json.get("away_team"),
                    "commence_time": ev_json.get("commence_time"),
                    "bookmaker_key": b["key"], "market_key": mk["key"],
                    "player_name": o.get("description"), "line": o.get("point"),
                    "over_price": "", "under_price": "",
                    "snapshot_utc": stamp, "last_update": mk.get("last_update")})
                if o.get("name") == "Over":
                    row["over_price"] = o.get("price")
                elif o.get("name") == "Under":
                    row["under_price"] = o.get("price")
    return rows


def existing_keys_for_snapshot(stamp):
    """Guard against double-append if an invocation is somehow repeated."""
    keys = set()
    if MASTER.exists():
        with open(MASTER, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["snapshot_utc"] == stamp:
                    keys.add((row["api_event_id"], row["bookmaker_key"],
                              row["market_key"], row["player_name"],
                              row["line"], row["snapshot_utc"]))
    return keys


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = api_key()
    events = upcoming_events(key)
    if not events:
        print(f"{stamp}: empty slate - no events within {WINDOW_HOURS}h; "
              f"0 fetched, 0 rows appended")
        return

    all_rows, fetched, no_props = {}, 0, 0
    for ev in events:
        ev_json = fetch_event_props(key, ev, MARKETS)
        if ev_json is None:
            continue
        fetched += 1
        (RAWDIR / f"props_{ev['id']}_{stamp}.json").write_text(
            json.dumps(ev_json, indent=1))
        rows = flatten(ev_json, stamp)
        books = {b["key"] for b in ev_json.get("bookmakers", [])}
        got = {mk["key"] for b in ev_json.get("bookmakers", [])
               for mk in b.get("markets", [])}
        missing = [m for m in MARKETS if m not in got]
        players = {r["player_name"] for r in rows.values()}
        if not rows:
            no_props += 1
        print(f"  -> books={len(books)} markets={sorted(got) or 'NONE'} "
              f"players={len(players)} lines={len(rows)}"
              + (f" | MISSING/suspended: {missing}" if missing else ""))
        all_rows.update(rows)

    dup = existing_keys_for_snapshot(stamp)
    norm = lambda v: "" if v is None else str(v)
    new_rows = [v for k, v in all_rows.items()
                if tuple(norm(x) for x in k) not in dup] if dup else list(all_rows.values())
    is_new = not MASTER.exists()
    with open(MASTER, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            w.writeheader()
        w.writerows(new_rows)
    print(f"{stamp}: {fetched}/{len(events)} events fetched "
          f"({no_props} with no props posted), {len(new_rows)} rows appended "
          f"({len(all_rows) - len(new_rows)} already present) -> {MASTER}")


if __name__ == "__main__":
    main()
