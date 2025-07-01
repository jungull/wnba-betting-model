import os
import pandas as pd
import numpy as np
from tqdm import tqdm

DATA_DIR = "data"
SEASONS = [fname.split('_')[-1].replace('.parquet', '') for fname in os.listdir(DATA_DIR) if fname.startswith('wnba_gamelog_') and fname.endswith('.parquet')]

# List of standard/basic box score stats (expand as needed)
BASIC_STATS = [
    'PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'TEAM_ABBREVIATION', 'GAME_ID', 'MATCHUP', 'WL', 'MIN',
    'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT',
    'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS',
    'SEASON'
]

# MISC_STATS will be dynamically determined from columns not in BASIC_STATS

def validate_misc_stats(df, season, misc_stats):
    missing_cols = [col for col in misc_stats if col not in df.columns]
    if missing_cols:
        print(f"[ERROR] Season {season}: Missing columns: {missing_cols}")
    for col in misc_stats:
        if col in df.columns:
            null_pct = df[col].isnull().mean()
            print(f"[INFO] Season {season}: {col} null percentage: {null_pct:.2%}")
            if null_pct > 0.05:
                print(f"[WARNING] Season {season}: {col} has more than 5% missing values!")


def add_misc_stats_to_season(season):
    base_path = os.path.join(DATA_DIR, f"wnba_gamelog_{season}.parquet")
    enriched_path = os.path.join(DATA_DIR, f"wnba_gamelog_{season}_with_misc_stats.parquet")
    temp_path = f"{enriched_path}.tmp"
    
    # --- Checkpointing: Skip if already processed ---
    if os.path.exists(enriched_path):
        print(f"[CHECKPOINT] Enriched file already exists for season {season}. Skipping.")
        return
    if not os.path.exists(base_path):
        print(f"[SKIP] No base data for season {season}.")
        return
    df = pd.read_parquet(base_path)

    # --- Dynamically detect advanced/misc stats ---
    misc_stats = [col for col in df.columns if col not in BASIC_STATS]
    print(f"[INFO] Season {season}: Detected advanced/misc stats: {misc_stats}")

    # --- Validation ---
    validate_misc_stats(df, season, misc_stats)

    # --- Atomic Save ---
    print(f"[INFO] Writing to temporary file: {temp_path}")
    df.to_parquet(temp_path, index=False)
    os.rename(temp_path, enriched_path)
    print(f"[SUCCESS] Saved enriched data for season {season} to {enriched_path}")

if __name__ == "__main__":
    print(f"--- Adding and Validating Misc/Advanced Stats for Seasons: {SEASONS} ---")
    for season in tqdm(SEASONS, desc="Processing Seasons"):
        add_misc_stats_to_season(season)
    print("--- All seasons processed. ---") 