import os
import pandas as pd
import time
from tqdm import tqdm
from nba_api.stats.endpoints import playbyplayv2
from functools import partial
import requests

DATA_DIR = "data"
PBP_DIR = os.path.join(DATA_DIR, "playbyplay")
os.makedirs(PBP_DIR, exist_ok=True)

# Get all game IDs from all wnba_gamelog_*.parquet files
SEASON_FILES = [fname for fname in os.listdir(DATA_DIR) if fname.startswith('wnba_gamelog_') and fname.endswith('.parquet') and 'with_misc_stats' not in fname]
GAME_IDS = set()
for fname in SEASON_FILES:
    df = pd.read_parquet(os.path.join(DATA_DIR, fname))
    GAME_IDS.update(df['GAME_ID'].unique())
GAME_IDS = sorted(GAME_IDS)

FAILED_GAME_IDS = []

def make_api_request_with_retry(api_func, retries=5, backoff_factor=2):
    last_exception = None
    for i in range(retries):
        try:
            response = api_func()
            return response
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            last_exception = e
            wait_time = 30 * (2 ** i)  # 30s, 60s, 120s, 240s, 480s
            print(f"  > Request failed ({type(e).__name__}): {e}. Retrying in {wait_time}s... ({i+1}/{retries})")
            time.sleep(wait_time)
    print(f"❌ Request failed after {retries} retries. Last exception: {last_exception}")
    return None

def fetch_and_save_playbyplay(game_id, verbose=True):
    pbp_path = os.path.join(PBP_DIR, f"pbp_{game_id}.parquet")
    temp_path = f"{pbp_path}.tmp"
    if os.path.exists(pbp_path):
        return True  # checkpoint
    api_call = partial(playbyplayv2.PlayByPlayV2, game_id=game_id)
    pbp = make_api_request_with_retry(api_call)
    if pbp is not None and hasattr(pbp, 'get_data_frames'):
        dfs = pbp.get_data_frames()
        if dfs and len(dfs) > 0:
            df = dfs[0]
            df['GAME_ID'] = game_id
            df.to_parquet(temp_path, index=False)
            os.rename(temp_path, pbp_path)
            return True
    if verbose:
        print(f"[WARNING] Failed to fetch play-by-play for GAME_ID {game_id}")
    return False

if __name__ == "__main__":
    print(f"--- Fetching Play-by-Play Data for {len(GAME_IDS)} games ---")
    for gid in tqdm(GAME_IDS, desc="Fetching PBP"):
        success = fetch_and_save_playbyplay(gid)
        if not success:
            FAILED_GAME_IDS.append(gid)
        time.sleep(0.6)  # 0.6 second delay after every request
    print(f"--- Initial pass complete. {len(FAILED_GAME_IDS)} games failed. ---")

    # Retry failed games with increasing delay
    if FAILED_GAME_IDS:
        print(f"--- Retrying failed games with increasing delay ---")
        for i, gid in enumerate(FAILED_GAME_IDS):
            delay = 60 * (i + 1)  # 60s, 120s, 180s, ...
            print(f"[RETRY] Waiting {delay}s before retrying GAME_ID {gid}")
            time.sleep(delay)
            success = fetch_and_save_playbyplay(gid, verbose=True)
            if not success:
                print(f"[FINAL FAIL] Could not fetch play-by-play for GAME_ID {gid} after retry.")
    print("--- All play-by-play data fetched (with retries). ---")

    if FAILED_GAME_IDS:
        print(f"[SUMMARY] The following GAME_IDs could not be fetched:")
        for gid in FAILED_GAME_IDS:
            print(f"  - {gid}") 