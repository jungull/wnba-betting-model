from nba_api.stats.endpoints import leaguegamelog, boxscoretraditionalv2, boxscoremiscv2
import pandas as pd
import time
import os
from tqdm import tqdm
from functools import partial
import requests
import datetime

print("--- Fetching All Player Box Scores (Robust, Checkpointed, Atomic Save Version) ---")

# --- Configuration ---
SEASON_YEARS = ['2021', '2022', '2023', '2024', '2025']
WNBA_LEAGUE_ID_STRING = "10" 
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# --- Robust Request Function with Retries ---
def make_api_request_with_retry(api_func, retries=5, backoff_factor=2):
    for i in range(retries):
        try:
            response = api_func()
            return response
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
            wait_time = backoff_factor ** i
            print(f"  > Request failed ({type(e).__name__}). Retrying in {wait_time}s... ({i+1}/{retries})")
            time.sleep(wait_time)
    print(f"❌ Request failed after {retries} retries. Skipping.")
    return None

def get_game_ids(season):
    api_call = partial(leaguegamelog.LeagueGameLog, league_id=WNBA_LEAGUE_ID_STRING, season=season, season_type_all_star="Regular Season")
    log = make_api_request_with_retry(api_call)
    if log:
        return log.get_data_frames()[0]['GAME_ID'].unique().tolist()
    return []

def get_boxscore(game_id):
    api_call_trad = partial(boxscoretraditionalv2.BoxScoreTraditionalV2, game_id=game_id)
    api_call_misc = partial(boxscoremiscv2.BoxScoreMiscV2, game_id=game_id)
    box_trad = make_api_request_with_retry(api_call_trad)
    box_misc = make_api_request_with_retry(api_call_misc)
    df_trad = box_trad.player_stats.get_data_frame() if (box_trad is not None and hasattr(box_trad, 'player_stats') and box_trad.player_stats is not None) else None
    df_misc = box_misc.player_stats.get_data_frame() if (box_misc is not None and hasattr(box_misc, 'player_stats') and box_misc.player_stats is not None) else None
    if df_trad is not None and df_misc is not None:
        merged = pd.merge(df_trad, df_misc, on=["GAME_ID", "PLAYER_ID"], how="outer", suffixes=("", "_MISC"))
        return merged
    elif df_trad is not None:
        return df_trad
    elif df_misc is not None:
        return df_misc
    return pd.DataFrame()

def fetch_and_save_boxscores(season):
    print(f"\n🔎 Fetching game IDs for {season} season...")
    game_ids = get_game_ids(season)
    
    if not game_ids:
        print(f"⚠️ No games found or API request failed for {season}.")
        return

    print(f"✅ Found {len(game_ids)} games for {season}.")
    all_boxscores = []
    for gid in tqdm(game_ids, desc=f"Fetching Box Scores for {season}"):
        box = get_boxscore(gid)
        if not box.empty:
            box['SEASON'] = season
            all_boxscores.append(box)
        time.sleep(0.8)
    
    if all_boxscores:
        df = pd.concat([pd.DataFrame(box) if not isinstance(box, pd.DataFrame) else box for box in all_boxscores], ignore_index=True)
        df = df[df['MIN'].notnull()]
        final_path = os.path.join(DATA_DIR, f"wnba_gamelog_{season}.parquet")
        temp_path = f"{final_path}.tmp"

        # --- NEW: For in-progress season, append only new games ---
        current_year = str(datetime.datetime.now().year)
        if season == current_year and os.path.exists(final_path):
            print(f"🔄 In-progress season detected. Loading existing data to append only new games.")
            existing_df = pd.read_parquet(final_path)
            # Identify new games not already in the file
            existing_game_ids = list(existing_df['GAME_ID'].unique())
            if not isinstance(df, pd.DataFrame):
                df = pd.DataFrame(df)
            new_df = df[~df['GAME_ID'].isin(existing_game_ids)]
            if isinstance(new_df, pd.DataFrame) and not new_df.empty:
                print(f"Appending {len(new_df)} new player box score rows.")
                combined_df = pd.concat([existing_df, new_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['GAME_ID', 'PLAYER_ID'])
            else:
                print(f"No new games to append for {season}.")
                return
        else:
            combined_df = df

        print(f"Writing to temporary file: {temp_path}")
        combined_df.to_parquet(temp_path, index=False)
        os.rename(temp_path, final_path)
        print(f"💾 Saved {len(combined_df)} player box score rows to {final_path}")
    else:
        print(f"⚠️ No box scores were successfully fetched for the {season} season.")

if __name__ == "__main__":
    print(f"Attempting to fetch data for seasons: {', '.join(SEASON_YEARS)}")
    current_year = str(datetime.datetime.now().year)
    for season in SEASON_YEARS:
        output_path = os.path.join(DATA_DIR, f"wnba_gamelog_{season}.parquet")
        # For in-progress season, always run; for past seasons, use checkpoint logic
        if season != current_year and os.path.exists(output_path):
            print(f"✅ Checkpoint found for season {season}. Skipping.")
            continue
        fetch_and_save_boxscores(season)
    print("\n🎉 All available season data has been fetched.")