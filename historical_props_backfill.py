#!/usr/bin/env python3
"""
Historical WNBA player_points props backfill (The Odds API v4 /historical).

One near-tip snapshot per game — tip_utc minus 65 minutes, mirroring the old
spreads master's ~T-64m near-tip convention — of markets=player_points,
regions=us (ONLY: historical event-odds cost is 10 credits per market per
region per event), for every 2024/2025/2026 game in
data/masters/master_team.parquet (regular season + playoffs).

Cost model (verified by the 2026-07-30 probe, experiments/props_capture_setup/):
  historical /events listing  = 1 credit per call (batched: ONE call per
                                (season, game_date) group, at the earliest
                                remaining game's snapshot timestamp)
  historical event-odds call  = 10 credits (1 market x 1 region)
  failed requests             = 0 credits

BUDGET DISCIPLINE: HARD FLOOR — if x-requests-remaining would drop below
FLOOR (2,500, the August live-capture reserve) the run STOPS CLEANLY at the
game checkpoint. Credit headers logged every call; running consumption
printed every 25 games. Seasons processed newest-first (2026, 2025, 2024),
newest date first within a season, so a shortfall keeps the most relevant
data complete.

Resumable: data/props_capture/historical/backfill_done.csv is the per-game
checkpoint; re-running skips games already there (any terminal status).
Games that errored are NOT checkpointed and are retried on the next run.
Partial master rows from a mid-game crash (game_id in master but not in the
done list) are dropped at startup and the game is refetched.

Outputs (file boundary — nothing else is written):
  data/props_capture/historical/raw/hist_props_<gameid>_<snapshotstamp>.json
  data/props_capture/historical/master_props_historical.csv
  data/props_capture/historical/backfill_done.csv        (checkpoint state)

The LIVE table data/props_capture/master_props.csv is never touched.
API key: ODDS_API_KEY env var, else .env at repo root — never printed.
Politeness: >= 0.5s between calls; never starts calls 08:25-08:45 local.
"""
import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from odds_capture_daily import api_key

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
HISTDIR = ROOT / "data" / "props_capture" / "historical"
RAWDIR = HISTDIR / "raw"
MASTER = HISTDIR / "master_props_historical.csv"
DONE = HISTDIR / "backfill_done.csv"
BASE = "https://api.the-odds-api.com/v4/historical/sports/basketball_wnba"

SEASONS = [2026, 2025, 2024]          # newest first — binding process order
MARKET = "player_points"
SNAP_LEAD_MIN = 65                    # tip - 65 min (house ~T-64m convention)
MATCH_WINDOW_H = 6                    # event commence must be within 6h of tip
FALLBACK_SNAP = "23:00:00"            # probe timestamp when tip time unknown
FLOOR = 2500                          # August live-capture reserve — hard stop
ODDS_COST, LIST_COST = 10, 1
SLEEP = 0.5
MAX_CONSEC_ERRORS = 8

# The 15 franchises (2026 era) — Odds API uses these exact full names
# (TEAMS map from props capture / build_odds_master_extension.py). 2024
# gamelogs abbreviate Phoenix as PHO; 2025+ use PHX — both map to the same
# franchise name.
TEAMS = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV",
    "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
    "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX",
    "Portland Fire": "PDX", "Seattle Storm": "SEA",
    "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}
NAME_BY_ABBR = {v: k for k, v in TEAMS.items()}
NAME_BY_ABBR["PHO"] = "Phoenix Mercury"

COLUMNS = ["game_id", "api_event_id", "home_team", "away_team",
           "commence_time", "snapshot_requested_utc", "snapshot_returned_utc",
           "bookmaker_key", "market_key", "player_name", "line",
           "over_price", "under_price", "last_update"]
DONE_COLS = ["game_id", "season", "game_date", "status", "api_event_id",
             "tip_known", "snapshot_requested_utc", "snapshot_returned_utc",
             "n_rows", "n_books", "n_players", "note", "finished_utc"]


def sanitize(msg, key):
    return str(msg).replace(key, "***KEY***")


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def stamp_of(snap_iso):
    return snap_iso.replace("-", "").replace(":", "")


def avoid_quiet_window():
    """Never issue calls 08:25-08:45 local (keeps host load clean)."""
    now = datetime.now()
    if now.hour == 8 and 25 <= now.minute < 45:
        wait = (45 - now.minute) * 60 - now.second
        print(f"In 08:25-08:45 local quiet window — sleeping {wait}s")
        time.sleep(wait + 1)


class Budget:
    """Tracks x-requests-remaining from headers; enforces the hard floor."""

    def __init__(self):
        self.remaining = None
        self.used_this_run = 0
        self.start_remaining = None

    def note(self, r, label):
        rem, last = r.headers.get("x-requests-remaining"), r.headers.get("x-requests-last")
        print(f"  [{label}] HTTP {r.status_code} | last-cost {last} | remaining {rem}")
        if rem is not None:
            self.remaining = int(float(rem))
            if self.start_remaining is None:
                self.start_remaining = self.remaining
        if last is not None:
            try:
                self.used_this_run += int(float(last))
            except ValueError:
                pass

    def can_afford(self, credits):
        return self.remaining is not None and self.remaining - credits >= FLOOR


def get(url, params, key, budget, label):
    """GET with politeness sleep, retries, credit logging. Returns response
    or None after persistent retryable failure. Exits on auth/credit errors."""
    for attempt in range(1, 4):
        avoid_quiet_window()
        try:
            r = requests.get(url, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  [{label}] request error ({type(e).__name__}: "
                  f"{sanitize(e, key)[:120]}) — attempt {attempt}/3")
            time.sleep(3 * attempt)
            continue
        budget.note(r, label)
        time.sleep(SLEEP)
        if r.status_code == 200:
            return r
        if r.status_code in (401, 403):
            sys.exit(f"AUTH FAILURE (HTTP {r.status_code}) — aborting. "
                     f"{sanitize(r.text[:160], key)}")
        if r.status_code == 402:
            print("HTTP 402 — OUT OF CREDITS. Stopping cleanly.")
            return "OUT_OF_CREDITS"
        if r.status_code == 429:
            print(f"  [{label}] 429 rate-limited — backing off {5 * attempt}s")
            time.sleep(5 * attempt)
            continue
        if r.status_code in (404, 422):
            return r          # caller decides — definitive, costs 0
        print(f"  [{label}] HTTP {r.status_code} {sanitize(r.text[:120], key)} "
              f"— attempt {attempt}/3")
        time.sleep(3 * attempt)
    return None


# --------------------------------------------------------------------------
# Game list
# --------------------------------------------------------------------------

def load_games():
    """One row per 2024-2026 game: id, season, date, home/away full names,
    snapshot timestamp (tip-65m, else 23:00Z fallback)."""
    t = pd.read_parquet(ROOT / "data" / "masters" / "master_team.parquet",
                        columns=["game_id", "season", "season_type", "game_date",
                                 "team_abbreviation", "opp_team_abbreviation",
                                 "is_home"])
    t = t[t["season"].isin(SEASONS)]
    home = t[t["is_home"] == 1].copy()
    n_games = t["game_id"].nunique()
    if len(home) != n_games or home["game_id"].duplicated().any():
        sys.exit(f"Dedup failure: {n_games} unique games but {len(home)} "
                 f"is_home rows")
    home["home_name"] = home["team_abbreviation"].map(NAME_BY_ABBR)
    home["away_name"] = home["opp_team_abbreviation"].map(NAME_BY_ABBR)
    bad = home[home["home_name"].isna() | home["away_name"].isna()]
    if len(bad):
        sys.exit(f"Unmapped abbreviations: "
                 f"{bad[['team_abbreviation', 'opp_team_abbreviation']].values}")

    tips = pd.read_csv(ROOT / "data" / "reference" / "tip_times.csv",
                       dtype={"game_id": str})[["game_id", "tip_utc"]]
    g = home.merge(tips, on="game_id", how="left")

    games = []
    for r in g.itertuples():
        tip_known = isinstance(r.tip_utc, str) and bool(r.tip_utc)
        if tip_known:
            tip = parse_iso(r.tip_utc)
            snap = tip - timedelta(minutes=SNAP_LEAD_MIN)
        else:
            snap = parse_iso(f"{r.game_date}T{FALLBACK_SNAP}Z")
            tip = snap                       # matching reference = probe time
        games.append({
            "game_id": r.game_id, "season": int(r.season),
            "game_date": str(r.game_date), "season_type": r.season_type,
            "home_name": r.home_name, "away_name": r.away_name,
            "tip_known": tip_known, "tip_utc": tip, "snapshot": snap,
        })
    # Newest-first: seasons in SEASONS order (2026, 2025, 2024), then date
    # descending within a season (stable two-pass sort), so a credit
    # shortfall costs the oldest, least relevant games first.
    games.sort(key=lambda x: (x["game_date"], x["game_id"]), reverse=True)
    games.sort(key=lambda x: SEASONS.index(x["season"]))
    return games


def load_done():
    if not DONE.exists():
        return {}
    with open(DONE, newline="", encoding="utf-8") as f:
        return {row["game_id"]: row["status"] for row in csv.DictReader(f)}


def reconcile_partial(done_ids):
    """Drop master rows for games not in the done list (mid-game crash)."""
    if not MASTER.exists():
        return
    m = pd.read_csv(MASTER, dtype=str)
    partial = set(m["game_id"]) - set(done_ids)
    if partial:
        print(f"Reconcile: dropping partial rows for {sorted(partial)} "
              f"(will refetch)")
        m[~m["game_id"].isin(partial)].to_csv(MASTER, index=False)


def append_rows(rows):
    new = not MASTER.exists()
    with open(MASTER, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerows(rows)


def append_done(rec):
    new = not DONE.exists()
    with open(DONE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DONE_COLS)
        if new:
            w.writeheader()
        w.writerow(rec)


# --------------------------------------------------------------------------
# Matching + flattening
# --------------------------------------------------------------------------

def match_event(game, events):
    """Exact home/away full-name match with commence within MATCH_WINDOW_H of
    our tip. Falls back to swapped orientation (still an exact team-pair +
    time identification, flagged in the note). Never guesses beyond that."""
    def candidates(home, away):
        out = []
        for e in events:
            if e.get("home_team") == home and e.get("away_team") == away:
                dt = abs((parse_iso(e["commence_time"]) - game["tip_utc"])
                         .total_seconds())
                if dt <= MATCH_WINDOW_H * 3600:
                    out.append((dt, e))
        return sorted(out, key=lambda x: x[0])

    exact = candidates(game["home_name"], game["away_name"])
    if exact:
        return exact[0][1], ""
    swapped = candidates(game["away_name"], game["home_name"])
    if swapped:
        return swapped[0][1], "swapped_orientation"
    return None, ""


def flatten(game, ev, snap_req, snap_ret):
    """Row per (book, market, player, line) — over/under paired on the exact
    point, so alternate lines each get their own row (house schema)."""
    rows = {}
    for b in ev.get("bookmakers", []):
        for mk in b.get("markets", []):
            for o in mk.get("outcomes", []):
                k = (b["key"], mk["key"], o.get("description"), o.get("point"))
                row = rows.setdefault(k, {
                    "game_id": game["game_id"], "api_event_id": ev["id"],
                    "home_team": ev.get("home_team"),
                    "away_team": ev.get("away_team"),
                    "commence_time": ev.get("commence_time"),
                    "snapshot_requested_utc": snap_req,
                    "snapshot_returned_utc": snap_ret,
                    "bookmaker_key": b["key"], "market_key": mk["key"],
                    "player_name": o.get("description"),
                    "line": o.get("point"),
                    "over_price": "", "under_price": "",
                    "last_update": mk.get("last_update")})
                if o.get("name") == "Over":
                    row["over_price"] = o.get("price")
                elif o.get("name") == "Under":
                    row["under_price"] = o.get("price")
    return list(rows.values())


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------

def run(max_games=None, dry_run=False):
    RAWDIR.mkdir(parents=True, exist_ok=True)
    key = api_key()
    budget = Budget()

    games = load_games()
    done = load_done()
    reconcile_partial(done)
    todo = [g for g in games if g["game_id"] not in done]
    no_tip = [g for g in todo if not g["tip_known"]]

    # Date groups (season, game_date) in processing order; one listing each.
    groups, order = {}, []
    for g in todo:
        k = (g["season"], g["game_date"])
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(g)

    est = len(todo) * ODDS_COST + len(order) * LIST_COST
    print(f"=== Historical player_points backfill ===")
    print(f"{len(games)} games total (2026/2025/2024: "
          f"{[sum(1 for x in games if x['season'] == s) for s in SEASONS]}); "
          f"{len(done)} already done; {len(todo)} to fetch "
          f"across {len(order)} date groups")
    print(f"{len(no_tip)} games without a known tip time -> {FALLBACK_SNAP}Z "
          f"fallback probe: {[(x['game_id'], x['game_date']) for x in no_tip]}")
    print(f"Estimated cost: {len(todo)}x{ODDS_COST} + {len(order)}x{LIST_COST} "
          f"= {est} credits | hard floor {FLOOR}")
    if dry_run:
        print("DRY RUN — no API calls made.")
        return
    if not todo:
        print("Nothing to do.")
        return

    # Free ping (non-historical /events costs 0) to learn current balance.
    r = requests.get(
        "https://api.the-odds-api.com/v4/sports/basketball_wnba/events",
        params={"apiKey": key}, timeout=30)
    budget.note(r, "free balance ping")
    budget.used_this_run = 0            # ping is free; reset any header noise
    print(f"Credits remaining at start: {budget.remaining}")
    time.sleep(SLEEP)

    processed = consec_errors = 0
    stopped = False
    for gkey in order:
        group = [g for g in groups[gkey] if g["game_id"] not in done]
        if not group:
            continue
        if max_games is not None and processed >= max_games:
            break
        # Budget gate: a listing is only worth it if >=1 odds call fits too.
        if not budget.can_afford(LIST_COST + ODDS_COST):
            stopped = True
            break

        season, gdate = gkey
        list_snap = iso(min(g["snapshot"] for g in group))
        r = get(f"{BASE}/events", {"apiKey": key, "date": list_snap},
                key, budget, f"events {gdate} @ {list_snap}")
        if r == "OUT_OF_CREDITS":
            stopped = True
            break
        if r is None or r.status_code != 200:
            print(f"  listing failed for {gdate} — {len(group)} games "
                  f"deferred to next run")
            consec_errors += 1
            if consec_errors >= MAX_CONSEC_ERRORS:
                sys.exit("Too many consecutive errors — aborting (resumable).")
            continue
        consec_errors = 0
        payload = r.json()
        events = payload.get("data", [])
        list_ret = payload.get("timestamp", "")

        for game in group:
            if max_games is not None and processed >= max_games:
                break
            if not budget.can_afford(ODDS_COST):
                stopped = True
                break
            gid = game["game_id"]
            snap_req = iso(game["snapshot"])
            ev, flag = match_event(game, events)
            now = iso(datetime.now(timezone.utc))
            if ev is None:
                near = [f"{e.get('away_team')}@{e.get('home_team')} "
                        f"{e.get('commence_time')}" for e in events][:6]
                print(f"  UNMATCHED {gid} {game['away_name']} @ "
                      f"{game['home_name']} {gdate} — listing had "
                      f"{len(events)} events")
                append_done({"game_id": gid, "season": season,
                             "game_date": gdate, "status": "unmatched",
                             "api_event_id": "", "tip_known": game["tip_known"],
                             "snapshot_requested_utc": snap_req,
                             "snapshot_returned_utc": list_ret,
                             "n_rows": 0, "n_books": 0, "n_players": 0,
                             "note": f"listing({list_ret}) had: "
                                     + "; ".join(near),
                             "finished_utc": now})
                done[gid] = "unmatched"
                processed += 1
                continue

            r2 = get(f"{BASE}/events/{ev['id']}/odds",
                     {"apiKey": key, "date": snap_req, "regions": "us",
                      "markets": MARKET, "oddsFormat": "american"},
                     key, budget,
                     f"{game['away_name']} at {game['home_name']} {gdate}")
            if r2 == "OUT_OF_CREDITS":
                stopped = True
                break
            if r2 is None:
                consec_errors += 1
                if consec_errors >= MAX_CONSEC_ERRORS:
                    sys.exit("Too many consecutive errors — aborting "
                             "(resumable).")
                continue
            consec_errors = 0
            now = iso(datetime.now(timezone.utc))
            if r2.status_code in (404, 422):
                status = f"no_odds_{r2.status_code}"
                append_done({"game_id": gid, "season": season,
                             "game_date": gdate, "status": status,
                             "api_event_id": ev["id"],
                             "tip_known": game["tip_known"],
                             "snapshot_requested_utc": snap_req,
                             "snapshot_returned_utc": "",
                             "n_rows": 0, "n_books": 0, "n_players": 0,
                             "note": sanitize(r2.text[:120], key),
                             "finished_utc": now})
                done[gid] = status
                processed += 1
                continue

            body = r2.json()
            ev_odds = body.get("data", {})
            snap_ret = body.get("timestamp", "")
            (RAWDIR / f"hist_props_{gid}_{stamp_of(snap_req)}.json").write_text(
                json.dumps(body, indent=1))
            rows = flatten(game, ev_odds, snap_req, snap_ret)
            books = {r_["bookmaker_key"] for r_ in rows}
            players = {r_["player_name"] for r_ in rows}
            if rows:
                append_rows(rows)
            status = "ok" if rows else "no_props"
            append_done({"game_id": gid, "season": season, "game_date": gdate,
                         "status": status, "api_event_id": ev["id"],
                         "tip_known": game["tip_known"],
                         "snapshot_requested_utc": snap_req,
                         "snapshot_returned_utc": snap_ret,
                         "n_rows": len(rows), "n_books": len(books),
                         "n_players": len(players), "note": flag,
                         "finished_utc": now})
            done[gid] = status
            processed += 1
            print(f"  {gid} {gdate}: {status} books={len(books)} "
                  f"players={len(players)} rows={len(rows)}"
                  + (f" [{flag}]" if flag else ""))
            if processed % 25 == 0:
                print(f"--- {processed} games this run | credits used "
                      f"{budget.used_this_run} | remaining {budget.remaining} ---")
        if stopped:
            break

    print(f"\n=== RUN {'STOPPED AT FLOOR' if stopped else 'COMPLETE'} ===")
    print(f"Games processed this run: {processed} | credits used this run: "
          f"{budget.used_this_run} | remaining: {budget.remaining}")
    remaining_todo = [g for g in games if g["game_id"] not in done]
    by_season = {s: sum(1 for g in remaining_todo if g["season"] == s)
                 for s in SEASONS}
    print(f"Games still to fetch: {len(remaining_todo)} {by_season}")
    if stopped:
        print(f"STOPPED CLEANLY: next call would take remaining below the "
              f"{FLOOR} floor (August live-capture reserve).")


# --------------------------------------------------------------------------
# Settlement-join preview (offline, no credits)
# --------------------------------------------------------------------------

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


def resolve_preview():
    """player_name -> our player_id per season, house resolver pattern:
    normalized exact match, unique-only (ambiguous = unresolved, never
    guessed). Second pass flips two-token 'Last First' names (seen in the
    2023 probe). Prints match rates and the unmatched list."""
    if not MASTER.exists():
        print("No master CSV yet — nothing to resolve.")
        return
    m = pd.read_csv(MASTER, dtype=str)
    m["season"] = m["game_id"].str[3:5].astype(int) + 2000
    mp = pd.read_parquet(ROOT / "data" / "masters" / "master_player.parquet",
                         columns=["season", "player_id", "player_name"])
    mp = mp[mp["season"].isin(SEASONS)].drop_duplicates()

    print("\n=== Settlement-join preview: player_name -> player_id ===")
    total_rows = matched_rows = 0
    unmatched_all = {}
    for season in sorted(m["season"].unique()):
        lut = {}
        for r in mp[mp["season"] == season].itertuples():
            lut.setdefault(_norm(r.player_name), set()).add(r.player_id)
        sub = m[m["season"] == season]
        names = sub["player_name"].dropna().unique()
        res, ambig, unres = {}, [], []
        for n in names:
            hit = lut.get(_norm(n))
            if hit is None:
                toks = str(n).split()
                if len(toks) == 2:      # 'Last First' books (2023 probe)
                    hit = lut.get(_norm(f"{toks[1]} {toks[0]}"))
            if hit is None:
                unres.append(n)
            elif len(hit) == 1:
                res[n] = next(iter(hit))
            else:
                ambig.append(n)
        nrows = len(sub)
        mrows = int(sub["player_name"].isin(res).sum())
        total_rows += nrows
        matched_rows += mrows
        print(f"{season}: {len(res)}/{len(names)} unique names resolved "
              f"({len(ambig)} ambiguous, {len(unres)} unmatched) | "
              f"{mrows}/{nrows} rows = {100 * mrows / max(nrows, 1):.1f}%")
        if ambig:
            print(f"  ambiguous (multiple player_ids, never guessed): {ambig}")
        if unres:
            unmatched_all[season] = sorted(unres)
    if total_rows:
        print(f"ALL: {matched_rows}/{total_rows} rows resolvable = "
              f"{100 * matched_rows / total_rows:.1f}%")
    for season, names in unmatched_all.items():
        print(f"  {season} unmatched names ({len(names)}): {names}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-games", type=int, default=None,
                    help="stop after N games this run (smoke test)")
    ap.add_argument("--dry-run", action="store_true",
                    help="plan + cost estimate only, no API calls")
    ap.add_argument("--resolve-only", action="store_true",
                    help="skip collection; just run the settlement preview")
    a = ap.parse_args()
    if not a.resolve_only:
        run(max_games=a.max_games, dry_run=a.dry_run)
    if not a.dry_run:
        resolve_preview()
