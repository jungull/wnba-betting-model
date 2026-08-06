"""
fetch_wnba_lineups.py
Track C capture script — 5-man lineup on/off splits, season aggregate.

Endpoint: nba_api.stats.endpoints.leaguedashlineups.
Verified live 2026-08-06: LeagueDashLineups(league_id_nullable="10",
season="2025-26", season_type_all_star="Regular Season") returned 2000
lineup rows. GRADUATED — real, populated for WNBA.

IMPORTANT param note (this is what the fundamentals-survey starter script
got wrong): the WNBA/league filter kwarg on this endpoint is
`league_id_nullable`, NOT `league_id`. `league_id` raises a TypeError in
nba_api's current signature. Also note this endpoint takes a season string
in `YYYY-YY` form (e.g. "2025-26"), unlike leaguegamelog's plain "2025".

This is a SEASON-LEVEL aggregate endpoint, not per-game-id — one call per
season/measure-type combination, not one call per game. Far cheaper than
the per-game fetchers.

Same host/headers/etiquette as scripts/01_acquisition/fetch_wnba_boxscores.py.
NOT SCHEDULED. Capture tool only — coordinator decides cron/CI wiring.
"""
import os
import time
from functools import partial
from datetime import datetime, timezone

import pandas as pd
import requests
from nba_api.stats.endpoints import leaguedashlineups

WNBA_LEAGUE_ID = "10"
# nba_api season string convention for this endpoint: "YYYY-YY"
SEASON_STRINGS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
DATA_DIR = "data"
LINEUPS_DIR = os.path.join(DATA_DIR, "lineups")
REQUEST_SPACING_SECONDS = 2.0  # season-aggregate calls are heavier; be gentler

os.makedirs(LINEUPS_DIR, exist_ok=True)


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


def fetch_lineups_for_season(season_str):
    out_path = os.path.join(LINEUPS_DIR, f"lineups_{season_str.replace('-', '_')}.parquet")
    if os.path.exists(out_path):
        print(f"Checkpoint found for {season_str}. Skipping.")
        return

    retrieval_ts = datetime.now(timezone.utc).isoformat()
    api_call = partial(
        leaguedashlineups.LeagueDashLineups,
        league_id_nullable=WNBA_LEAGUE_ID,
        season=season_str,
        season_type_all_star="Regular Season",
    )
    resp = make_api_request_with_retry(api_call)
    if resp is None:
        print(f"No response for {season_str}.")
        return

    dfs = resp.get_data_frames()
    if not dfs or dfs[0].empty:
        print(f"Empty lineup data for {season_str}.")
        return

    df = dfs[0]
    df["SEASON_STR"] = season_str
    df["vendor_ts_semantics"] = "not_a_timing_claim"  # season-aggregate stat snapshot
    df["retrieval_ts"] = retrieval_ts
    df["provenance_class"] = "witnessed_direct_api_capture"

    temp_path = f"{out_path}.tmp"
    df.to_parquet(temp_path, index=False)
    os.rename(temp_path, out_path)
    print(f"Saved {len(df)} lineup rows to {out_path}")


if __name__ == "__main__":
    for season_str in SEASON_STRINGS:
        fetch_lineups_for_season(season_str)
        time.sleep(REQUEST_SPACING_SECONDS)
    print("Done.")
