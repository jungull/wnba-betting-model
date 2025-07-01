import os
import pandas as pd
import numpy as np

DATA_DIR = "data"
PBP_DIR = os.path.join(DATA_DIR, "playbyplay")

def validate_box_scores():
    print("=== BOX SCORE VALIDATION ===")
    files = [f for f in os.listdir(DATA_DIR) if f.startswith('wnba_gamelog_') and f.endswith('.parquet') and 'with_misc_stats' not in f]
    
    total_rows = 0
    total_games = set()
    
    for f in files:
        df = pd.read_parquet(os.path.join(DATA_DIR, f))
        season = f.split('_')[-1].replace('.parquet', '')
        print(f"\nSeason {season}:")
        print(f"  Rows: {len(df)}")
        print(f"  Games: {df['GAME_ID'].nunique()}")
        print(f"  Players: {df['PLAYER_ID'].nunique()}")
        print(f"  Columns: {len(df.columns)}")
        
        # Check key columns for non-nulls
        key_cols = ['GAME_ID', 'PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'MIN', 'PTS']
        for col in key_cols:
            if col in df.columns:
                null_pct = df[col].isnull().mean() * 100
                print(f"  {col} null %: {null_pct:.2f}%")
        
        total_rows += len(df)
        total_games.update(df['GAME_ID'].unique())
    
    print(f"\nTOTAL BOX SCORES:")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Total unique games: {len(total_games)}")
    return len(total_games)

def validate_misc_stats():
    print("\n=== MISC STATS VALIDATION ===")
    files = [f for f in os.listdir(DATA_DIR) if f.startswith('wnba_gamelog_') and 'with_misc_stats' in f and f.endswith('.parquet')]
    
    if not files:
        print("No misc stats files found!")
        return 0
    
    total_rows = 0
    total_games = set()
    
    for f in files:
        df = pd.read_parquet(os.path.join(DATA_DIR, f))
        season = f.split('_')[-2]  # Extract season from filename
        print(f"\nSeason {season} (with misc stats):")
        print(f"  Rows: {len(df)}")
        print(f"  Games: {df['GAME_ID'].nunique()}")
        print(f"  Columns: {len(df.columns)}")
        
        # Check for advanced stats
        advanced_cols = [col for col in df.columns if col not in ['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'GAME_ID', 'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS', 'SEASON']]
        print(f"  Advanced stats columns: {len(advanced_cols)}")
        for col in advanced_cols[:5]:  # Show first 5
            null_pct = df[col].isnull().mean() * 100
            print(f"    {col} null %: {null_pct:.2f}%")
        
        total_rows += len(df)
        total_games.update(df['GAME_ID'].unique())
    
    print(f"\nTOTAL MISC STATS:")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Total unique games: {len(total_games)}")
    return len(total_games)

def validate_playbyplay():
    print("\n=== PLAY-BY-PLAY VALIDATION ===")
    pbp_files = [f for f in os.listdir(PBP_DIR) if f.endswith('.parquet')]
    
    if not pbp_files:
        print("No play-by-play files found!")
        return 0
    
    total_events = 0
    total_games = len(pbp_files)
    
    # Sample a few files to check structure
    sample_files = pbp_files[:3]
    for f in sample_files:
        df = pd.read_parquet(os.path.join(PBP_DIR, f))
        game_id = f.split('_')[1].replace('.parquet', '')
        print(f"\nGame {game_id}:")
        print(f"  Events: {len(df)}")
        print(f"  Columns: {len(df.columns)}")
        print(f"  Periods: {df['PERIOD'].nunique()}")
        
        # Check key columns
        key_cols = ['EVENTNUM', 'EVENTMSGTYPE', 'PERIOD', 'HOMEDESCRIPTION', 'VISITORDESCRIPTION']
        for col in key_cols:
            if col in df.columns:
                null_pct = df[col].isnull().mean() * 100
                print(f"  {col} null %: {null_pct:.2f}%")
    
    # Count total events
    for f in pbp_files:
        df = pd.read_parquet(os.path.join(PBP_DIR, f))
        total_events += len(df)
    
    print(f"\nTOTAL PLAY-BY-PLAY:")
    print(f"  Total games: {total_games}")
    print(f"  Total events: {total_events:,}")
    print(f"  Avg events per game: {total_events/total_games:.1f}")
    
    return total_games

def main():
    print("=== COMPREHENSIVE DATA VALIDATION ===")
    
    box_games = validate_box_scores()
    misc_games = validate_misc_stats()
    pbp_games = validate_playbyplay()
    
    print(f"\n=== SUMMARY ===")
    print(f"Box score games: {box_games}")
    print(f"Misc stats games: {misc_games}")
    print(f"Play-by-play games: {pbp_games}")
    
    if box_games == pbp_games:
        print("✅ PERFECT: All games have both box scores and play-by-play data!")
    else:
        print(f"⚠️  MISMATCH: {box_games - pbp_games} games missing play-by-play data")
    
    if box_games == misc_games:
        print("✅ PERFECT: All games have misc stats!")
    else:
        print(f"⚠️  MISMATCH: {box_games - misc_games} games missing misc stats")

if __name__ == "__main__":
    main() 