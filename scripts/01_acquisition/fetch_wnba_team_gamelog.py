import os
import pandas as pd
from nba_api.stats.endpoints import leaguegamelog

DATA_DIR = "data"
SEASON = '2024'  # Change as needed
WNBA_LEAGUE_ID_STRING = "10"

if __name__ == "__main__":
    print(f"Fetching WNBA team-level game log for season {SEASON}...")
    log = leaguegamelog.LeagueGameLog(league_id=WNBA_LEAGUE_ID_STRING, season=SEASON, season_type_all_star="Regular Season", player_or_team_abbreviation="T")
    df = log.get_data_frames()[0]
    print("Columns:", df.columns.tolist())
    print("Sample rows:")
    print(df.head())
    out_path = os.path.join(DATA_DIR, f"wnba_team_gamelog_{SEASON}.parquet")
    df.to_parquet(out_path, index=False)
    print(f"Saved to {out_path}") 