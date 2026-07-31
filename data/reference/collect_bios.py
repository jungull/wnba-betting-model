#!/usr/bin/env python3
"""
COLLECT-S reference collection — player bios, team city coordinates, tip times.
Unlocks FEATURE_LAB_CATALOG candidates #7, 9, 17, 18, 27-31, 33, 80, 86.

Phases (run all by default, or pick with --cities / --tips / --bios):

  cities  OFFLINE. Writes team_cities.csv from static, hand-verified facts embedded
          below (one row per (team_id, abbreviation) so both PHO and PHX join).
          Join-verified against data/masters/master_team.parquet.

  tips    OFFLINE. Writes tip_times.csv: per game_id, the scheduled tip from the
          odds tables' odds_commence_time (latest snapshot per game wins),
          converted to the HOME team's local timezone via team_cities.csv.
          Sources: data/drive_masters/master_odds.csv (2022-2025 partial era)
                   data/odds_capture/master_odds_extension.csv (2025-07-05 -> now)
          game_id-mapped rows only; extension preferred where both cover a game.

  bios    NETWORK (stats.nba.com via nba_api). Writes player_bios.csv.
          Primary endpoint: leaguedashplayerbiostats (league_id='10' = WNBA),
            one call per season 2021-2026, Regular Season (master audit: zero
            players appear ONLY in playoffs, so RS covers the universe).
            Gives: PLAYER_ID, AGE (per season), PLAYER_HEIGHT '6-2',
            PLAYER_HEIGHT_INCHES, PLAYER_WEIGHT, COLLEGE, COUNTRY,
            DRAFT_YEAR/ROUND/NUMBER. No birthdate, no position.
          Fallback endpoint: commonplayerinfo (league-agnostic, per player_id)
            ONLY for master-universe ids the primary pull missed. Adds
            BIRTHDATE, POSITION, HEIGHT, WEIGHT, DRAFT_*. Checkpointed per
            player to _bios_checkpoint/ - safe to interrupt and re-run.
          Enrichment sweep (same commonplayerinfo endpoint, on by default,
            skip with --no-sweep): the season endpoint carries NO position and
            NO birthdate. One checkpointed call per remaining master player_id
            fills position_raw + birthdate for every player, and fills
            height/weight ONLY where the season endpoint had none (null/0).
            Rows touched get cpi_enriched=True; primary fields are never
            overwritten. WNBA scale: ~370 calls, ~9 min at the polite floor.

Grain of player_bios.csv: ONE ROW PER (player_id, season) - the primary endpoint
is per-season (AGE changes); fallback players get one row per master season they
appear in, with identical bio fields and source='commonplayerinfo'.

Politeness: >= 0.6s + jitter between calls, exponential backoff on failure.
BLACKOUT: the one-stats-crawler rule - a scheduled task hits stats.nba.com daily
08:30 America/New_York. This script refuses to call the API 08:25-08:45 ET and
sleeps through the window instead.

Run from anywhere:  python data/reference/collect_bios.py [--cities] [--tips] [--bios]
Requires: nba_api, pandas, pyarrow (checkpoints), tzdata (zoneinfo on Windows).
Writes ONLY under data/reference/. Never touches masters or existing data files.
"""

import argparse
import datetime as dt
import json
import random
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]          # repo root
REF = ROOT / "data" / "reference"
CKPT = REF / "_bios_checkpoint"
MASTER_PLAYER = ROOT / "data" / "masters" / "master_player.parquet"
MASTER_TEAM = ROOT / "data" / "masters" / "master_team.parquet"
ODDS_DRIVE = ROOT / "data" / "drive_masters" / "master_odds.csv"
ODDS_EXT = ROOT / "data" / "odds_capture" / "master_odds_extension.csv"

LEAGUE = "10"  # WNBA
SEASONS = ["2021", "2022", "2023", "2024", "2025", "2026"]
BASE_SLEEP = 0.6  # matches collect_refresh.py politeness floor

ET = ZoneInfo("America/New_York")


# ----------------------------------------------------------------------------
# politeness + the one-stats-crawler blackout window
# ----------------------------------------------------------------------------
def blackout_wait():
    """Never overlap the 08:30 ET scheduled crawler: dead zone 08:25-08:45 ET."""
    now = dt.datetime.now(ET)
    lo = now.replace(hour=8, minute=25, second=0, microsecond=0)
    hi = now.replace(hour=8, minute=45, second=0, microsecond=0)
    if lo <= now <= hi:
        wait = (hi - now).total_seconds() + 60
        print(f"  [blackout] inside the 08:25-08:45 ET crawler window - sleeping {wait:.0f}s")
        time.sleep(wait)


def polite():
    time.sleep(BASE_SLEEP + random.uniform(0.0, 0.4))


def fetch(fn, tag, retries=5):
    delay = 4
    for i in range(retries):
        blackout_wait()
        try:
            r = fn()
            polite()
            return r
        except Exception as e:  # noqa: BLE001 - network fetch, log and retry
            print(f"    retry {i + 1}/{retries} for {tag}: {str(e)[:90]}")
            time.sleep(delay)
            delay = min(delay * 2, 240)
    print(f"    FAILED permanently: {tag}")
    return None


# ----------------------------------------------------------------------------
# small parsers
# ----------------------------------------------------------------------------
def parse_height_inches(s):
    """'6-2' -> 74.0; tolerate blanks / weird values -> None. Never guess."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip()
    if not s or s.upper() in {"NAN", "NONE", "-"}:
        return None
    if "-" in s:
        try:
            ft, inch = s.split("-", 1)
            return float(int(ft) * 12 + float(inch))
        except ValueError:
            return None
    try:  # already numeric inches
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def to_num(x):
    try:
        v = pd.to_numeric(x)
        return None if pd.isna(v) else float(v)
    except (ValueError, TypeError):
        return None


def to_weight(x):
    """Weight in lbs; the stats API uses 0 as a missing sentinel -> None."""
    v = to_num(x)
    return None if (v is None or v <= 0) else v


def load_cpi(pid, fetch_missing=True):
    """commonplayerinfo for one player id, checkpointed. {} = known-empty."""
    from nba_api.stats.endpoints import commonplayerinfo
    ck = CKPT / f"cpi_{pid}.json"
    if ck.exists():
        return json.loads(ck.read_text(encoding="utf-8"))
    if not fetch_missing:
        return None
    r = fetch(
        lambda p=pid: commonplayerinfo.CommonPlayerInfo(player_id=int(p), league_id_nullable=LEAGUE, timeout=60),
        f"commonplayerinfo {pid}")
    if r is None:
        return None
    df = r.common_player_info.get_data_frame()
    if df is None or not len(df):
        ck.write_text(json.dumps({}), encoding="utf-8")
        return {}
    info = df.iloc[0].to_dict()
    ck.write_text(json.dumps({k: (None if pd.isna(v) else str(v)) for k, v in info.items()}), encoding="utf-8")
    return info


# ----------------------------------------------------------------------------
# Phase: cities (static facts - hand-entered 2026-07-31, city-level precision)
# ----------------------------------------------------------------------------
# One row per (team_id, abbreviation). PHO (2021-2024) and PHX (2025-) are the
# same franchise/team_id 1611661317 - the 2025 abbreviation rename.
# lat/lon = arena/metro, city-level precision. elevation_ft approximate.
# Note SEA 2021: Storm split early-2021 homes with Everett, WA (Angel of the
# Winds) while Climate Pledge Arena finished construction - city-level Seattle
# coordinates are still the honest call for travel/altitude features.
CITY_ROWS = [
    # team_id, abbr, franchise, first, last, city, arena, lat, lon, elev_ft, tz
    (1611661313, "NYL", "New York Liberty", 2021, None, "Brooklyn, NY", "Barclays Center", 40.6828, -73.9758, 30, "America/New_York"),
    (1611661317, "PHO", "Phoenix Mercury", 2021, 2024, "Phoenix, AZ", "Footprint Center", 33.4457, -112.0712, 1090, "America/Phoenix"),
    (1611661317, "PHX", "Phoenix Mercury", 2025, None, "Phoenix, AZ", "Footprint Center", 33.4457, -112.0712, 1090, "America/Phoenix"),
    (1611661319, "LVA", "Las Vegas Aces", 2021, None, "Las Vegas (Paradise), NV", "Michelob ULTRA Arena", 36.0905, -115.1767, 2030, "America/Los_Angeles"),
    (1611661320, "LAS", "Los Angeles Sparks", 2021, None, "Los Angeles, CA", "Crypto.com Arena", 34.0430, -118.2673, 285, "America/Los_Angeles"),
    (1611661321, "DAL", "Dallas Wings", 2021, None, "Arlington, TX", "College Park Center", 32.7299, -97.1081, 604, "America/Chicago"),
    (1611661322, "WAS", "Washington Mystics", 2021, None, "Washington, DC", "Entertainment & Sports Arena", 38.8621, -76.9978, 130, "America/New_York"),
    (1611661323, "CON", "Connecticut Sun", 2021, None, "Uncasville, CT", "Mohegan Sun Arena", 41.4910, -72.0910, 40, "America/New_York"),
    (1611661324, "MIN", "Minnesota Lynx", 2021, None, "Minneapolis, MN", "Target Center", 44.9795, -93.2760, 830, "America/Chicago"),
    (1611661325, "IND", "Indiana Fever", 2021, None, "Indianapolis, IN", "Gainbridge Fieldhouse", 39.7640, -86.1555, 715, "America/Indiana/Indianapolis"),
    (1611661327, "PDX", "Portland Fire", 2026, None, "Portland, OR", "Moda Center", 45.5316, -122.6668, 50, "America/Los_Angeles"),
    (1611661328, "SEA", "Seattle Storm", 2021, None, "Seattle, WA", "Climate Pledge Arena", 47.6221, -122.3540, 175, "America/Los_Angeles"),
    (1611661329, "CHI", "Chicago Sky", 2021, None, "Chicago, IL", "Wintrust Arena", 41.8534, -87.6193, 595, "America/Chicago"),
    (1611661330, "ATL", "Atlanta Dream", 2021, None, "College Park (Atlanta), GA", "Gateway Center Arena", 33.6545, -84.4477, 1010, "America/New_York"),
    (1611661331, "GSV", "Golden State Valkyries", 2025, None, "San Francisco, CA", "Chase Center", 37.7680, -122.3877, 20, "America/Los_Angeles"),
    (1611661332, "TOR", "Toronto Tempo", 2026, None, "Toronto, ON", "Coca-Cola Coliseum", 43.6353, -79.4185, 250, "America/Toronto"),
]


def phase_cities():
    print("== Phase: cities (offline) ==")
    df = pd.DataFrame(
        CITY_ROWS,
        columns=["team_id", "abbreviation", "franchise", "first_season",
                 "last_season", "city", "arena", "lat", "lon", "elevation_ft",
                 "timezone"],
    )
    # join-verify against the master before writing
    mt = pd.read_parquet(MASTER_TEAM, columns=["team_id", "team_abbreviation", "season"])
    master_keys = mt.groupby(["team_id", "team_abbreviation"])["season"].agg(["min", "max"]).reset_index()
    master_keys.columns = ["team_id", "abbreviation", "master_first", "master_last"]
    chk = master_keys.merge(df, on=["team_id", "abbreviation"], how="outer", indicator=True)
    missing = chk[chk["_merge"] == "left_only"]  # in master, not in table
    extra = chk[chk["_merge"] == "right_only"]   # in table, not in master
    if len(missing):
        print(missing[["team_id", "abbreviation"]].to_string(index=False))
        sys.exit("FATAL: master (team_id, abbreviation) keys missing from CITY_ROWS - fix the table.")
    if len(extra):
        print("  note: table rows not (yet) in master:", extra["abbreviation"].tolist())
    out = REF / "team_cities.csv"
    df.to_csv(out, index=False)
    print(f"  wrote {out}  ({len(df)} rows, {df['team_id'].nunique()} franchises; all master keys map)")
    return df


# ----------------------------------------------------------------------------
# Phase: tips (offline - odds commence times -> home-team local clock)
# ----------------------------------------------------------------------------
def load_odds(path, source):
    o = pd.read_csv(path, usecols=["game_id", "odds_commence_time", "odds_snapshot_timestamp", "home_team"])
    o = o[o["game_id"].notna()].copy()                      # game_id-mapped rows only
    o["game_id"] = o["game_id"].astype("int64").astype(str).str.zfill(10)
    o["snap"] = pd.to_datetime(o["odds_snapshot_timestamp"], errors="coerce", utc=True, format="mixed")
    o["commence_utc"] = pd.to_datetime(o["odds_commence_time"], errors="coerce", utc=True, format="mixed")
    o = o[o["commence_utc"].notna()]
    o["source_table"] = source
    return o


def phase_tips():
    print("== Phase: tips (offline) ==")
    cities = pd.read_csv(REF / "team_cities.csv")
    tz_map = cities.drop_duplicates("team_id").set_index("team_id")["timezone"].to_dict()

    frames = [load_odds(ODDS_DRIVE, "drive_master"), load_odds(ODDS_EXT, "extension")]
    odds = pd.concat(frames, ignore_index=True)

    # latest snapshot per (game_id, source) = final scheduled tip that source saw
    odds = odds.sort_values("snap")
    per_gid = (
        odds.groupby(["game_id", "source_table"])
        .agg(commence_utc=("commence_utc", "last"),
             n_commence_variants=("commence_utc", "nunique"),
             n_snapshots=("snap", "size"))
        .reset_index()
    )
    # prefer the extension (fresher capture pipeline) where both cover a game
    per_gid["pref"] = (per_gid["source_table"] == "extension").astype(int)
    per_gid = per_gid.sort_values(["game_id", "pref"]).groupby("game_id").last().reset_index().drop(columns="pref")

    # home team from the master (is_home == 1), never from name matching
    mt = pd.read_parquet(MASTER_TEAM, columns=["game_id", "season", "game_date", "team_id", "team_abbreviation", "is_home"])
    home = mt[mt["is_home"] == 1].rename(columns={"team_id": "home_team_id", "team_abbreviation": "home_abbr"})
    tips = per_gid.merge(home[["game_id", "season", "game_date", "home_team_id", "home_abbr"]], on="game_id", how="inner")
    dropped = len(per_gid) - len(tips)

    tips["timezone"] = tips["home_team_id"].map(tz_map)
    local_parts = []
    for tz, grp in tips.groupby("timezone"):
        loc = grp["commence_utc"].dt.tz_convert(ZoneInfo(tz))
        g = grp.copy()
        g["tip_local"] = loc.dt.strftime("%Y-%m-%d %H:%M:%S %z")
        g["tip_hour_local"] = loc.dt.hour
        g["tip_dow_local"] = loc.dt.strftime("%a")
        local_parts.append(g)
    tips = pd.concat(local_parts).sort_values("game_id")
    tips["tip_utc"] = tips["commence_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    cols = ["game_id", "season", "game_date", "home_team_id", "home_abbr", "timezone",
            "tip_utc", "tip_local", "tip_hour_local", "tip_dow_local",
            "source_table", "n_snapshots", "n_commence_variants"]
    out = REF / "tip_times.csv"
    tips[cols].to_csv(out, index=False)

    cov = tips.groupby("season").size()
    tot = mt[mt["is_home"] == 1].groupby("season").size()
    print(f"  wrote {out}  ({len(tips)} games; {dropped} odds game_ids not in master dropped)")
    for s in tot.index:
        print(f"    {s}: {cov.get(s, 0)}/{tot[s]} master games have tip times")
    return tips


# ----------------------------------------------------------------------------
# Phase: bios (network)
# ----------------------------------------------------------------------------
def phase_bios(sweep=True):
    print("== Phase: bios (network - stats.nba.com) ==")
    from nba_api.stats.endpoints import leaguedashplayerbiostats

    CKPT.mkdir(parents=True, exist_ok=True)
    mp = pd.read_parquet(MASTER_PLAYER, columns=["player_id", "season", "player_name", "team_id", "team_abbreviation"])
    universe = mp.drop_duplicates(["player_id", "season"])

    # -- primary: leaguedashplayerbiostats, one call per season ----------------
    season_frames = {}
    for season in SEASONS:
        ck = CKPT / f"bios_{season}.parquet"
        if ck.exists():
            season_frames[season] = pd.read_parquet(ck)
            print(f"  {season}: checkpoint hit ({len(season_frames[season])} rows)")
            continue
        r = fetch(
            lambda s=season: leaguedashplayerbiostats.LeagueDashPlayerBioStats(
                league_id=LEAGUE, season=s, season_type_all_star="Regular Season", timeout=60),
            f"leaguedashplayerbiostats {season}")
        if r is None:
            print(f"  {season}: PRIMARY ENDPOINT FAILED - continuing, fallback will cover")
            continue
        df = r.get_data_frames()[0]
        if df is None or not len(df):
            print(f"  {season}: primary endpoint returned EMPTY for WNBA")
            continue
        df.to_parquet(ck, index=False)
        season_frames[season] = df
        print(f"  {season}: pulled {len(df)} players")

    rows = []
    for season, df in season_frames.items():
        for _, x in df.iterrows():
            rows.append({
                "player_id": int(x["PLAYER_ID"]),
                "season": int(season),
                "player_name": x.get("PLAYER_NAME"),
                "age": to_num(x.get("AGE")),
                "birthdate": None,                       # not provided by this endpoint
                "height_str": x.get("PLAYER_HEIGHT"),
                "height_inches": to_num(x.get("PLAYER_HEIGHT_INCHES")) or parse_height_inches(x.get("PLAYER_HEIGHT")),
                "weight_lbs": to_weight(x.get("PLAYER_WEIGHT")),
                "draft_year": to_num(x.get("DRAFT_YEAR")),
                "draft_round": to_num(x.get("DRAFT_ROUND")),
                "draft_number": to_num(x.get("DRAFT_NUMBER")),
                "draft_raw": f'{x.get("DRAFT_YEAR")}|{x.get("DRAFT_ROUND")}|{x.get("DRAFT_NUMBER")}',
                "college": x.get("COLLEGE"),
                "country": x.get("COUNTRY"),
                "position_raw": None,                    # not provided by this endpoint
                "source": "leaguedashplayerbiostats",
            })
    bios = pd.DataFrame(rows)

    # -- fallback: commonplayerinfo for master ids the primary missed ---------
    have = set(zip(bios["player_id"], bios["season"])) if len(bios) else set()
    need = universe[~universe.apply(lambda r: (r["player_id"], r["season"]) in have, axis=1)]
    need_ids = sorted(need["player_id"].unique())
    print(f"  fallback needed for {len(need_ids)} player ids ({len(need)} player-seasons)")

    fb_rows = []
    for i, pid in enumerate(need_ids):
        info = load_cpi(pid)
        if not info:
            continue
        seasons_for = sorted(universe.loc[universe["player_id"] == pid, "season"].unique())
        for season in seasons_for:
            if (pid, season) in have:
                continue
            fb_rows.append({
                "player_id": int(pid),
                "season": int(season),
                "player_name": f'{info.get("FIRST_NAME", "")} {info.get("LAST_NAME", "")}'.strip(),
                "age": None,                              # derive from birthdate downstream
                "birthdate": info.get("BIRTHDATE"),
                "height_str": info.get("HEIGHT"),
                "height_inches": parse_height_inches(info.get("HEIGHT")),
                "weight_lbs": to_weight(info.get("WEIGHT")),
                "draft_year": to_num(info.get("DRAFT_YEAR")),
                "draft_round": to_num(info.get("DRAFT_ROUND")),
                "draft_number": to_num(info.get("DRAFT_NUMBER")),
                "draft_raw": f'{info.get("DRAFT_YEAR")}|{info.get("DRAFT_ROUND")}|{info.get("DRAFT_NUMBER")}',
                "college": info.get("SCHOOL"),
                "country": info.get("COUNTRY"),
                "position_raw": info.get("POSITION"),
                "source": "commonplayerinfo",
            })
        if (i + 1) % 25 == 0:
            print(f"    ...{i + 1}/{len(need_ids)} fallback ids")

    bios = pd.concat([bios, pd.DataFrame(fb_rows)], ignore_index=True) if fb_rows else bios
    if not len(bios):
        sys.exit("FATAL: no bios collected from either endpoint - see report; do not impute.")

    # keep only master-universe player-seasons, one row per (player_id, season)
    bios = bios.merge(universe[["player_id", "season"]], on=["player_id", "season"], how="inner")
    bios = bios.drop_duplicates(["player_id", "season"], keep="first").sort_values(["season", "player_id"])

    # -- enrichment sweep: position + birthdate for everyone ------------------
    # The season endpoint has neither; commonplayerinfo has both. One
    # checkpointed call per master player_id not already covered. Fills ONLY
    # fields the row lacks (position_raw, birthdate; height/weight if null).
    bios["cpi_enriched"] = False
    if sweep:
        todo = sorted(bios.loc[bios["position_raw"].isna() | bios["birthdate"].isna(), "player_id"].unique())
        print(f"  enrichment sweep: {len(todo)} player ids (checkpointed, ~{len(todo) * 1.5 / 60:.0f} min)")
        got = 0
        for i, pid in enumerate(todo):
            info = load_cpi(pid)
            if not info:
                continue
            m = bios["player_id"] == pid
            fill = {
                "position_raw": info.get("POSITION") or None,
                "birthdate": info.get("BIRTHDATE") or None,
                "height_str": info.get("HEIGHT") or None,
                "weight_lbs": to_weight(info.get("WEIGHT")),
                "college": info.get("SCHOOL") or None,
                "country": info.get("COUNTRY") or None,
            }
            fill["height_inches"] = parse_height_inches(fill["height_str"])
            touched = False
            for col in ("position_raw", "birthdate", "college", "country",
                        "height_str", "height_inches", "weight_lbs"):
                if fill[col] is None:
                    continue
                gap = m & bios[col].isna()
                if gap.any():
                    bios.loc[gap, col] = fill[col]
                    touched = True
            if touched:
                bios.loc[m, "cpi_enriched"] = True
                got += 1
            if (i + 1) % 50 == 0:
                print(f"    ...{i + 1}/{len(todo)} sweep ids")
        print(f"  sweep filled fields for {got} players")

    for c in ("draft_year", "draft_round", "draft_number"):
        bios[c] = bios[c].astype("Int64")
    bios["player_id"] = bios["player_id"].astype("int64")

    out = REF / "player_bios.csv"
    bios.to_csv(out, index=False)
    print(f"  wrote {out}  ({len(bios)} player-season rows, "
          f"{bios['player_id'].nunique()} unique players, "
          f"{bios['height_inches'].notna().mean() * 100:.1f}% with height)")
    return bios


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cities", action="store_true")
    ap.add_argument("--tips", action="store_true")
    ap.add_argument("--bios", action="store_true")
    ap.add_argument("--no-sweep", action="store_true",
                    help="skip the commonplayerinfo position/birthdate enrichment sweep")
    a = ap.parse_args()
    run_all = not (a.cities or a.tips or a.bios)
    REF.mkdir(parents=True, exist_ok=True)
    if a.cities or run_all:
        phase_cities()
    if a.tips or run_all:
        phase_tips()
    if a.bios or run_all:
        phase_bios(sweep=not a.no_sweep)
    print("done.")
