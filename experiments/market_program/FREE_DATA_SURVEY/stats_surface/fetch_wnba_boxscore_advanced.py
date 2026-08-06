"""
fetch_wnba_boxscore_advanced.py
Track C capture script — advanced per-player/per-team box score
(offensive/defensive rating, usage%, pace, PIE, etc.).

Endpoint: nba_api.stats.endpoints.boxscoreadvancedv2.
Verified live 2026-08-06 against WNBA 2025 game_id 1022500001: returned
23 PlayerStats rows + 2 TeamStats rows, fully populated (OFF_RATING,
DEF_RATING, USG_PCT, PACE, PIE, etc. all present). GRADUATED — real,
non-empty for WNBA, same call shape as the already-production
boxscoretraditionalv2/boxscoremiscv2 fetchers.

Same host/headers/etiquette as scripts/01_acquisition/fetch_wnba_boxscores.py.
Follows the same checkpointed-per-season, atomic-write pattern.

NOT SCHEDULED. Capture tool only — coordinator decides cron/CI wiring.
"""
import os
import time
from functools import partial
from datetime import datetime, timezone

import pandas as pd
import requests
from nba_api.stats.endpoints import leaguegamelog, boxscoreadvancedv2

SEASON_YEARS = ["2021", "2022", "2023", "2024", "2025"]
WNBA_LEAGUE_ID_STRING = "10"
DATA_DIR = "data"
REQUEST_SPACING_SECONDS = 0.8

os.makedirs(DATA_DIR, exist_ok=True)


def make_api_request_with_retry(api_func, retries=5, backoff_factor=2):
    for i in range(retries):
        try:
            return api_func()
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            wait_time = backoff_factor ** i
            print(f"  > Request failed ({type(e).__name__}). Retrying in {wait_time}s... ({i + 1}/{retries})")
            time.sleep(wait_time)
    print("Request failed after retries. Skipping.")
    return None


def get_game_ids(season):
    api_call = partial(
        leaguegamelog.LeagueGameLog,
        league_id=WNBA_LEAGUE_ID_STRING,
        season=season,
        season_type_all_star="Regular Season",
    )
    log = make_api_request_with_retry(api_call)
    if log:
        return log.get_data_frames()[0]["GAME_ID"].unique().tolist()
    return []


def get_advanced_boxscore(game_id, retrieval_ts):
    api_call = partial(boxscoreadvancedv2.BoxScoreAdvancedV2, game_id=game_id)
    resp = make_api_request_with_retry(api_call)
    if resp is None:
        return pd.DataFrame()
    dfs = resp.get_data_frames()
    if not dfs or dfs[0].empty:
        return pd.DataFrame()
    df = dfs[0]  # PlayerStats
    df["vendor_ts_semantics"] = "not_a_timing_claim"  # box score stat snapshot, not an event-timing claim
    df["retrieval_ts"] = retrieval_ts
    df["provenance_class"] = "witnessed_direct_api_capture"
    return df


def fetch_and_save_season(season):
    out_path = os.path.join(DATA_DIR, f"wnba_boxscore_advanced_{season}.parquet")
    if os.path.exists(out_path):
        print(f"Checkpoint found for season {season}. Skipping.")
        return

    print(f"Fetching game IDs for {season} season...")
    game_ids = get_game_ids(season)
    if not game_ids:
        print(f"No games found for {season}.")
        return

    all_rows = []
    for gid in game_ids:
        retrieval_ts = datetime.now(timezone.utc).isoformat()
        df = get_advanced_boxscore(gid, retrieval_ts)
        if not df.empty:
            df["SEASON"] = season
            all_rows.append(df)
        time.sleep(REQUEST_SPACING_SECONDS)

    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)
        temp_path = f"{out_path}.tmp"
        combined.to_parquet(temp_path, index=False)
        os.rename(temp_path, out_path)
        print(f"Saved {len(combined)} advanced box score rows to {out_path}")
    else:
        print(f"No advanced box scores fetched for {season}.")


if __name__ == "__main__":
    for season in SEASON_YEARS:
        fetch_and_save_season(season)
    print("Done.")
