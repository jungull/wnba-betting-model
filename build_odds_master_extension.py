#!/usr/bin/env python3
"""
Build data/odds_capture/master_odds_extension.csv — the new-era continuation of
data/drive_masters/master_odds.csv (which ends 2025-07-04).

Inputs (local only, no network):
  data/odds_capture/historical/hist_YYYY-MM-DD_HHZ.json
      The Odds API /historical format: {timestamp, previous_timestamp,
      next_timestamp, data:[games]}. Two per game date (15Z, 22Z).
  data/odds_capture/live_YYYYmmddTHHMMSSZ.json
      The Odds API live format: [games] (no wrapper). Snapshot time = filename.

Outputs (CSV, hand-inspectable):
  data/odds_capture/master_odds_extension.csv
      SPREADS market only. Exactly the 17 columns of the old master, same order.
      One row per (event, bookmaker, team-side, snapshot).
  data/odds_capture/master_odds_extension_other_markets.csv
      h2h + totals. Same shared columns; (team, odds_spread, odds_price) are
      replaced by (market_key, outcome_name, outcome_point, outcome_price).

Column semantics (mirroring the old master, verified against it):
  odds_snapshot_timestamp  actual archive time of the snapshot (wrapper
                           "timestamp" for hist; filename UTC stamp for live)
  odds_previous_timestamp / odds_next_timestamp
                           wrapper values for hist; empty for live
  odds_odds_time_check     the REQUESTED time of the snapshot (old master:
                           commence-1h on a 5-min grid; here: the 15Z/22Z hour
                           from the hist filename, or the capture time for live)
  odds_last_update         market-level last_update, falling back to
                           bookmaker-level when the market has none
  matchup_date             ET (America/New_York) date of commence, MM/DD/YYYY
  season                   ET calendar year of commence (WNBA seasons are
                           within one calendar year)
  game_id                  stats.wnba.com GAME_ID mapped via
                           (ET date of commence, home team, away team) against
                           data/refresh_2026/gamelog_team_{2025,2026}_*.parquet;
                           empty when the game has no completed gamelog entry
                           (future games, or non-gamelog games such as the
                           Commissioner's Cup final).

NOTE: snapshots taken AFTER commence_time (in-play lines from the 15Z/22Z grid
catching games already underway) are kept — they are real captures and are
identifiable via odds_snapshot_timestamp > odds_commence_time. Closing-line
work must filter to pre-tip rows (see experiments/w5_closing_line/).

Walk-forward safety: this script only unifies raw captures; every row carries
its own snapshot timestamp so downstream consumers can enforce the
"information timestamped before the prediction moment" rule.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parent
CAP = ROOT / "data" / "odds_capture"
HIST = CAP / "historical"
REFRESH = ROOT / "data" / "refresh_2026"
ET = ZoneInfo("America/New_York")

# The 15 franchises (2026 era). Odds API uses these exact full names.
TEAMS = {
    "Atlanta Dream": "ATL", "Chicago Sky": "CHI", "Connecticut Sun": "CON",
    "Dallas Wings": "DAL", "Golden State Valkyries": "GSV",
    "Indiana Fever": "IND", "Las Vegas Aces": "LVA",
    "Los Angeles Sparks": "LAS", "Minnesota Lynx": "MIN",
    "New York Liberty": "NYL", "Phoenix Mercury": "PHX",
    "Portland Fire": "PDX", "Seattle Storm": "SEA",
    "Toronto Tempo": "TOR", "Washington Mystics": "WAS",
}

# Hand-adjudicated event -> GAME_ID decisions for events whose quoted
# commence date never matches a completed gamelog game exactly. Each entry was
# verified by tracing the event across every snapshot file (see W5 report).
# "" means: intentionally unmatched (not a stats.wnba.com gamelog game).
MANUAL_GAME_ID_OVERRIDES = {
    # Seen only in hist_2025-09-21_22Z with provisional commence 9/22 21:00 ET.
    # It is the transient early listing of semifinal Game 2 (LVA vs IND),
    # which was finalized as event b4edd1f9 and played 9/23 (GAME_ID
    # 1042500212). Game 1 (9/21) has its own event c1c951f4.
    "4f02664e99904bf1491e7dcdb619e9ac": "1042500212",
    # Listed 7/14-7/16 with commence 7/16 21:00 ET, then vanished from the
    # feed (postponed) and was relisted as event f8d499fa on 7/19, played
    # 7/20 (GAME_ID 1022600183 - its out-of-sequence id vs the 7/19 game's
    # 1022600191 corroborates the reschedule). Same physical game.
    "51f9e00bb8d7debd5a922a21f0736e36": "1022600183",
    # NYL vs LVA quoted for 6/30/2026 during a league-wide 6/29-7/01 gamelog
    # gap; no gamelog entry exists. Consistent with the 2026 Commissioner's
    # Cup final (real franchises, but not a regular-season game, so it has
    # no stats.wnba.com regular-season GAME_ID). Intentionally unmatched.
    "c72d086a53d7b9b49f1daaf8754bd4e9": "",
}

MAIN_COLS = ["api_event_id", "home_team", "away_team", "odds_commence_time",
             "bookmaker_key", "bookmaker_title", "odds_last_update", "team",
             "odds_spread", "odds_price", "odds_snapshot_timestamp",
             "odds_previous_timestamp", "odds_next_timestamp", "game_id",
             "matchup_date", "odds_odds_time_check", "season"]
OTHER_COLS = ["api_event_id", "home_team", "away_team", "odds_commence_time",
              "bookmaker_key", "bookmaker_title", "odds_last_update",
              "market_key", "outcome_name", "outcome_point", "outcome_price",
              "odds_snapshot_timestamp", "odds_previous_timestamp",
              "odds_next_timestamp", "game_id", "matchup_date",
              "odds_odds_time_check", "season"]


def et_date(commence_iso):
    """UTC commence time -> ET date (proper tz conversion, handles DST)."""
    dt = datetime.fromisoformat(commence_iso.replace("Z", "+00:00"))
    return dt.astimezone(ET).date()


def load_game_index():
    """(et_date, home_name, away_name) -> GAME_ID from the refresh gamelogs."""
    files = sorted(REFRESH.glob("gamelog_team_2025_*.parquet")) + \
            sorted(REFRESH.glob("gamelog_team_2026_*.parquet"))
    if not files:
        sys.exit("No refresh gamelogs found under data/refresh_2026/")
    frames = [pd.read_parquet(f, columns=["GAME_ID", "GAME_DATE", "MATCHUP",
                                          "TEAM_NAME", "TEAM_ABBREVIATION"])
              for f in files]
    g = pd.concat(frames, ignore_index=True)

    # Sanity-check the hardcoded team map against the data itself.
    seen = dict(g[["TEAM_NAME", "TEAM_ABBREVIATION"]].drop_duplicates().values)
    for name, ab in seen.items():
        if TEAMS.get(name) != ab:
            sys.exit(f"Team map mismatch: gamelogs have {name!r}->{ab!r}, "
                     f"script has {TEAMS.get(name)!r}. Fix TEAMS.")

    home = g[g["MATCHUP"].str.contains("vs.", regex=False)]
    away = g[g["MATCHUP"].str.contains("@", regex=False)]
    pair = home.merge(away[["GAME_ID", "TEAM_NAME"]], on="GAME_ID",
                      suffixes=("_home", "_away"))
    index, collisions = {}, []
    for _, r in pair.iterrows():
        key = (str(r["GAME_DATE"]), r["TEAM_NAME_home"], r["TEAM_NAME_away"])
        if key in index and index[key] != r["GAME_ID"]:
            collisions.append(key)
        index[key] = r["GAME_ID"]
    if collisions:
        print(f"WARNING: {len(collisions)} (date,home,away) collisions in "
              f"gamelogs: {collisions}")
    dates = sorted({k[0] for k in index})
    print(f"Game index: {len(index)} completed games, "
          f"{dates[0]} .. {dates[-1]}")
    return index, dates[-1]


def snapshots():
    """Yield (snapshot_ts, prev_ts, next_ts, time_check, games, source_file)."""
    for f in sorted(HIST.glob("hist_*.json")):
        m = re.match(r"hist_(\d{4}-\d{2}-\d{2})_(\d{2})Z\.json", f.name)
        if not m:
            print(f"WARNING: skipping unrecognized filename {f.name}")
            continue
        d = json.loads(f.read_text())
        check = f"{m.group(1)}T{m.group(2)}:00:00+00:00"
        yield (d["timestamp"], d.get("previous_timestamp") or "",
               d.get("next_timestamp") or "", check, d.get("data", []), f.name)
    for f in sorted(CAP.glob("live_*.json")):
        m = re.match(r"live_(\d{8})T(\d{6})Z\.json", f.name)
        if not m:
            print(f"WARNING: skipping unrecognized filename {f.name}")
            continue
        ds, ts = m.group(1), m.group(2)
        iso = (f"{ds[:4]}-{ds[4:6]}-{ds[6:]}T{ts[:2]}:{ts[2:4]}:{ts[4:]}Z")
        check = iso.replace("Z", "+00:00")
        yield iso, "", "", check, json.loads(f.read_text()), f.name


def resolve_events(sightings, index):
    """Event-level GAME_ID resolution.

    sightings: eid -> ordered list of (snapshot_ts, et_date_str, home, away).
    Priority: exact (et_date, home, away) match on the LATEST sighting (the
    final schedule is authoritative), then exact match on any earlier
    sighting (catches events whose provisional time drifted), then the
    hand-adjudicated override table. No blind date+-1 or home/away-swap
    fallbacks — those were tried and produced a provably wrong match
    (playoff Game 2 provisional listing grabbing Game 1's GAME_ID).
    """
    gid, kind = {}, {}
    for eid, seen in sightings.items():
        gid[eid], kind[eid] = "", "unmatched"
        for i, (_, d, home, away) in enumerate(reversed(seen)):
            if (d, home, away) in index:
                gid[eid] = index[(d, home, away)]
                kind[eid] = "exact" if i == 0 else "exact-earlier-listing"
                break
        else:
            if eid in MANUAL_GAME_ID_OVERRIDES:
                gid[eid] = MANUAL_GAME_ID_OVERRIDES[eid]
                kind[eid] = ("manual-override" if gid[eid]
                             else "non-gamelog-event")
    return gid, kind


def main():
    index, max_gamelog_date = load_game_index()
    main_rows, other_rows = [], []
    sightings = {}        # eid -> [(snapshot_ts, et_date, home, away)]
    n_files = 0

    for snap_ts, prev_ts, next_ts, check, games, fname in snapshots():
        n_files += 1
        for g in games:
            eid, home, away = g["id"], g["home_team"], g["away_team"]
            commence = g["commence_time"]
            if home not in TEAMS or away not in TEAMS:
                print(f"WARNING: non-franchise names in {fname}: "
                      f"{away} @ {home} — kept, will not match a game_id")
            d = et_date(commence)
            sightings.setdefault(eid, []).append((snap_ts, str(d), home, away))
            season = str(d.year)
            mdate = f"{d.month:02d}/{d.day:02d}/{d.year}"
            gid = None  # filled in the second pass
            for b in g.get("bookmakers", []):
                bk, bt = b["key"], b["title"]
                b_upd = b.get("last_update", "")
                for mk in b.get("markets", []):
                    upd = mk.get("last_update") or b_upd
                    if mk["key"] == "spreads":
                        for o in mk.get("outcomes", []):
                            main_rows.append([eid, home, away, commence, bk,
                                              bt, upd, o["name"],
                                              o.get("point"), o.get("price"),
                                              snap_ts, prev_ts, next_ts, gid,
                                              mdate, check, season])
                    elif mk["key"] in ("h2h", "totals"):
                        for o in mk.get("outcomes", []):
                            other_rows.append([eid, home, away, commence, bk,
                                               bt, upd, mk["key"], o["name"],
                                               o.get("point"), o.get("price"),
                                               snap_ts, prev_ts, next_ts, gid,
                                               mdate, check, season])
                    else:
                        print(f"WARNING: unexpected market {mk['key']!r} "
                              f"in {fname} — skipped")

    gid_map, kind_map = resolve_events(sightings, index)

    dfm = pd.DataFrame(main_rows, columns=MAIN_COLS)
    dfo = pd.DataFrame(other_rows, columns=OTHER_COLS)
    dfm["game_id"] = dfm["api_event_id"].map(gid_map)
    dfo["game_id"] = dfo["api_event_id"].map(gid_map)

    # Dedupe (belt and suspenders — snapshot grids should never overlap).
    before = len(dfm), len(dfo)
    dfm = dfm.drop_duplicates(subset=["api_event_id", "bookmaker_key", "team",
                                      "odds_snapshot_timestamp"], keep="first")
    dfo = dfo.drop_duplicates(subset=["api_event_id", "bookmaker_key",
                                      "market_key", "outcome_name",
                                      "odds_snapshot_timestamp"], keep="first")
    dropped = (before[0] - len(dfm)) + (before[1] - len(dfo))
    if dropped:
        print(f"Deduped {dropped} duplicate rows")

    sort = ["odds_snapshot_timestamp", "odds_commence_time", "home_team",
            "bookmaker_key"]
    dfm = dfm.sort_values(sort + ["team"]).reset_index(drop=True)
    dfo = dfo.sort_values(sort + ["market_key", "outcome_name"]).reset_index(drop=True)

    out_main = CAP / "master_odds_extension.csv"
    out_other = CAP / "master_odds_extension_other_markets.csv"
    dfm.to_csv(out_main, index=False)
    dfo.to_csv(out_other, index=False)

    # ---- report ----
    last_seen = {eid: s[-1] for eid, s in sightings.items()}  # latest sighting
    kinds = pd.Series(kind_map).value_counts().to_dict()
    def describe(eid):
        _, d, home, away = last_seen[eid]
        return (eid, d, f"{away} @ {home}", f"n_snapshots={len(sightings[eid])}")
    unmatched = [describe(e) for e, k in kind_map.items() if k == "unmatched"]
    special = [(kind_map[e], gid_map[e] or "(none)", *describe(e))
               for e, k in kind_map.items()
               if k in ("exact-earlier-listing", "manual-override",
                        "non-gamelog-event")]
    completed_unmatched = [u for u in unmatched if u[1] <= max_gamelog_date]
    future_unmatched = [u for u in unmatched if u[1] > max_gamelog_date]
    multi = (dfm[dfm.game_id != ""].groupby("game_id")["api_event_id"]
             .nunique())
    multi = multi[multi > 1]

    print(f"\n=== master_odds_extension build report ===")
    print(f"snapshot files parsed: {n_files}")
    print(f"rows: spreads={len(dfm)} -> {out_main}")
    print(f"rows: other (h2h+totals)={len(dfo)} -> {out_other}")
    print(f"unique events: {len(sightings)} | match kinds: {kinds}")
    print(f"distinct completed games with odds: "
          f"{dfm.loc[dfm.game_id != '', 'game_id'].nunique()} "
          f"(of {len(index)} completed games in gamelogs)")
    print(f"rows by season (spreads): "
          f"{dfm['season'].value_counts().sort_index().to_dict()}")
    ip = (pd.to_datetime(dfm['odds_snapshot_timestamp']) >=
          pd.to_datetime(dfm['odds_commence_time'])).sum()
    print(f"in-play spread rows (snapshot >= commence, kept & flagged "
          f"by timestamps): {ip}")
    if special:
        print(f"\nSpecial-cased events ({len(special)}):")
        for row in special:
            print("  ", row)
    if len(multi):
        print(f"\ngame_ids fed by >1 api_event_id (reschedule dups — "
              f"closing-line work should note these): "
              f"{multi.to_dict()}")
    print(f"\nUnmatched events: {len(unmatched)} total")
    print(f"  future / not-yet-completed (ET date > last gamelog date "
          f"{max_gamelog_date}): {len(future_unmatched)}")
    for u in future_unmatched:
        print("    ", u)
    print(f"  UNEXPLAINED (date inside completed-gamelog range): "
          f"{len(completed_unmatched)}")
    for u in completed_unmatched:
        print("    ", u)
    if not completed_unmatched:
        print("    (none — every completed-game snapshot maps)")


if __name__ == "__main__":
    main()
