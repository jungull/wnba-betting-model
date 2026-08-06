"""
fetch_wnba_officials.py
Track C capture script — referee/official assignments per game.

Endpoint: nba_api.stats.endpoints.boxscoresummaryv2, `Officials` resultSet.
Verified live 2026-08-06 against WNBA 2025 game_ids 1022500001 and
1022500002: both returned 3 officials/game (OFFICIAL_ID, FIRST_NAME,
LAST_NAME, JERSEY_NUM). GRADUATED — real, non-empty for WNBA.

Same host/headers/etiquette as scripts/01_acquisition/fetch_wnba_boxscores.py
(nba_api default STATS_HEADERS -> stats.nba.com, no key, no auth).

Follows the existing repo fetcher pattern: checkpointed per-game-id parquet
file, atomic tmp-then-rename write, retry-with-backoff on transient network
errors, polite fixed delay between requests.

NOT SCHEDULED. This script is a capture tool only — the coordinator decides
if/when it is added to cron/CI. Running it end-to-end against a full season
of game_ids is a deliberate, larger pull than this survey's own live-
verification budget and should be a conscious choice, not a side effect of
importing this file.
"""
import os
import time
import json
from functools import partial
from datetime import datetime, timezone

import pandas as pd
import requests
from nba_api.stats.endpoints import boxscoresummaryv2

DATA_DIR = "data"
OFFICIALS_DIR = os.path.join(DATA_DIR, "officials")
REQUEST_SPACING_SECONDS = 0.8  # same order of magnitude as existing box score fetcher

os.makedirs(OFFICIALS_DIR, exist_ok=True)


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


def get_known_game_ids():
    """Pull game_ids from the season gamelog parquet files already on disk."""
    game_ids = set()
    for fname in os.listdir(DATA_DIR):
        if fname.startswith("wnba_gamelog_") and fname.endswith(".parquet") and "with_misc_stats" not in fname:
            df = pd.read_parquet(os.path.join(DATA_DIR, fname))
            game_ids.update(df["GAME_ID"].unique())
    return sorted(game_ids)


def fetch_officials_for_game(game_id):
    out_path = os.path.join(OFFICIALS_DIR, f"officials_{game_id}.parquet")
    temp_path = f"{out_path}.tmp"
    if os.path.exists(out_path):
        return True  # checkpoint: already captured

    retrieval_ts = datetime.now(timezone.utc).isoformat()
    api_call = partial(boxscoresummaryv2.BoxScoreSummaryV2, game_id=game_id)
    resp = make_api_request_with_retry(api_call)
    if resp is None:
        return False

    try:
        data = json.loads(resp.get_json())
        result_sets = data.get("resultSets") or []
        officials_rs = next((rs for rs in result_sets if rs.get("name") == "Officials"), None)
        if officials_rs is None:
            print(f"[WARNING] No Officials resultSet for GAME_ID {game_id}")
            return False
        df = pd.DataFrame(officials_rs["rowSet"], columns=officials_rs["headers"])
        df["GAME_ID"] = game_id
        # Amendment-4 timestamp discipline
        df["vendor_ts_semantics"] = "not_a_timing_claim"  # official assignment, not a market/injury event time
        df["retrieval_ts"] = retrieval_ts
        df["provenance_class"] = "witnessed_direct_api_capture"
        df.to_parquet(temp_path, index=False)
        os.rename(temp_path, out_path)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] Failed to parse Officials for GAME_ID {game_id}: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    game_ids = get_known_game_ids()
    print(f"--- Fetching official assignments for {len(game_ids)} known games ---")
    failed = []
    for gid in game_ids:
        ok = fetch_officials_for_game(gid)
        if not ok:
            failed.append(gid)
        time.sleep(REQUEST_SPACING_SECONDS)
    print(f"--- Done. {len(game_ids) - len(failed)} succeeded, {len(failed)} failed. ---")
    if failed:
        print("Failed GAME_IDs:", failed)
