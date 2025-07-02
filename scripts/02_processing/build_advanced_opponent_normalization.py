import os
import pandas as pd
import numpy as np
from tqdm import tqdm
import glob
from datetime import datetime, timedelta

DATA_DIR = "data"
PBP_DIR = os.path.join(DATA_DIR, "playbyplay")

def load_game_data():
    """Load all game data to build opponent defensive metrics."""
    print("Loading game data...")
    
    # Load box scores
    boxscore_files = glob.glob(os.path.join(DATA_DIR, "wnba_gamelog_*.parquet"))
    all_boxscores = []
    
    for file in boxscore_files:
        df = pd.read_parquet(file)
        all_boxscores.append(df)
    
    if all_boxscores:
        boxscores = pd.concat(all_boxscores, ignore_index=True)
        print(f"Loaded {len(boxscores)} box score records")
        return boxscores
    else:
        print("No box score files found!")
        return pd.DataFrame()

def calculate_defensive_metrics(game_df):
    """Calculate defensive metrics for a single game."""
    teams = game_df['TEAM_ID'].unique()
    if len(teams) != 2:
        return {}
    
    defensive_stats = {}
    
    for team_id in teams:
        # Get team's defensive stats (opponent's offensive stats)
        opponent_stats = game_df[game_df['TEAM_ID'] != team_id]
        team_stats = game_df[game_df['TEAM_ID'] == team_id]
        
        if len(opponent_stats) == 0 or len(team_stats) == 0:
            continue
            
        # Calculate defensive metrics
        opp_points = opponent_stats['PTS'].sum()
        opp_fga = opponent_stats['FGA'].sum()
        opp_fg3a = opponent_stats['FG3A'].sum()
        opp_fta = opponent_stats['FTA'].sum()
        opp_tov = opponent_stats['TOV'].sum()
        
        # Team's defensive stats
        team_stl = team_stats['STL'].sum()
        team_blk = team_stats['BLK'].sum()
        team_pf = team_stats['PF'].sum()
        
        # Calculate defensive efficiency (points allowed per 100 possessions)
        # Estimate possessions: FGA + 0.44*FTA + TOV
        opp_possessions = opp_fga + 0.44 * opp_fta + opp_tov
        defensive_efficiency = (opp_points / max(opp_possessions, 1)) * 100
        
        # Calculate shooting defense
        opp_fg_pct = opponent_stats['FG_PCT'].mean() if opp_fga > 0 else 0
        opp_fg3_pct = opponent_stats['FG3_PCT'].mean() if opp_fg3a > 0 else 0
        
        # Calculate steal and block rates
        steal_rate = team_stl / max(opp_possessions, 1)
        block_rate = team_blk / max(opp_fga, 1)
        
        # Calculate free throw rate allowed
        ft_rate_allowed = opp_fta / max(opp_fga, 1)
        
        defensive_stats[team_id] = {
            'defensive_efficiency': defensive_efficiency,
            'opp_fg_pct': opp_fg_pct,
            'opp_fg3_pct': opp_fg3_pct,
            'steal_rate': steal_rate,
            'block_rate': block_rate,
            'ft_rate_allowed': ft_rate_allowed,
            'opp_possessions': opp_possessions,
            'opp_points': opp_points
        }
    
    return defensive_stats

def build_opponent_defensive_history(boxscores):
    """Build historical defensive metrics for each team."""
    print("Building opponent defensive history...")
    
    # Sort by date (assuming there's a date column, if not we'll use game order)
    if 'GAME_DATE' in boxscores.columns:
        boxscores = boxscores.sort_values(['TEAM_ID', 'GAME_DATE'])
    else:
        # If no date, assume games are in chronological order
        boxscores = boxscores.sort_values(['TEAM_ID', 'GAME_ID'])
    
    # Group by team and game to calculate defensive metrics
    team_games = boxscores.groupby(['TEAM_ID', 'GAME_ID']).first().reset_index()
    
    all_defensive_metrics = []
    
    for team_id in tqdm(team_games['TEAM_ID'].unique(), desc="Processing teams"):
        team_games_subset = team_games[team_games['TEAM_ID'] == team_id]
        
        for idx, game_row in team_games_subset.iterrows():
            game_id = game_row['GAME_ID']
            
            # Get the full game data for this specific game
            game_data = boxscores[boxscores['GAME_ID'] == game_id]
            
            if len(game_data) == 0:
                continue
                
            defensive_metrics = calculate_defensive_metrics(game_data)
            
            if team_id in defensive_metrics:
                metrics = defensive_metrics[team_id]
                metrics['TEAM_ID'] = team_id
                metrics['GAME_ID'] = game_id
                if 'GAME_DATE' in game_row:
                    metrics['GAME_DATE'] = game_row['GAME_DATE']
                all_defensive_metrics.append(metrics)
    
    if all_defensive_metrics:
        defensive_df = pd.DataFrame(all_defensive_metrics)
        print(f"Generated defensive metrics for {len(defensive_df)} team-games")
        return defensive_df
    else:
        print("No defensive metrics generated!")
        return pd.DataFrame()

def calculate_weighted_defensive_rating(team_id, game_id, defensive_history, lookback_games=10, recent_weight=1.5):
    """Calculate weighted defensive rating based on recent performance."""
    
    # Get team's defensive history up to this game
    team_history = defensive_history[
        (defensive_history['TEAM_ID'] == team_id) & 
        (defensive_history['GAME_ID'] < game_id)
    ].sort_values('GAME_ID').tail(lookback_games)
    
    if len(team_history) == 0:
        return None
    
    # Split into recent (last 5) and older (previous 5) games
    if len(team_history) >= 5:
        recent_games = team_history.tail(5)
        older_games = team_history.head(len(team_history) - 5)
    else:
        recent_games = team_history
        older_games = pd.DataFrame()
    
    # Calculate weighted averages
    weighted_metrics = {}
    
    for metric in ['defensive_efficiency', 'opp_fg_pct', 'opp_fg3_pct', 'steal_rate', 'block_rate', 'ft_rate_allowed']:
        if metric not in team_history.columns:
            continue
            
        recent_avg = recent_games[metric].mean() if len(recent_games) > 0 else 0
        older_avg = older_games[metric].mean() if len(older_games) > 0 else 0
        
        # Weight recent games more heavily
        if len(older_games) > 0:
            total_weight = len(recent_games) * recent_weight + len(older_games)
            weighted_avg = (recent_avg * len(recent_games) * recent_weight + older_avg * len(older_games)) / total_weight
        else:
            weighted_avg = recent_avg
            
        weighted_metrics[f'weighted_{metric}'] = weighted_avg
    
    return weighted_metrics

def normalize_player_stats_with_opponent_strength(player_stats_df, defensive_history):
    """Normalize player stats using advanced opponent defensive metrics."""
    print("Normalizing player stats with opponent strength...")
    
    normalized_stats = []
    
    for idx, player_row in tqdm(player_stats_df.iterrows(), total=len(player_stats_df), desc="Normalizing stats"):
        game_id = player_row['GAME_ID']
        team_id = player_row['TEAM_ID']
        
        # Get opponent's defensive rating for this game
        opponent_defensive_rating = calculate_weighted_defensive_rating(
            team_id, game_id, defensive_history
        )
        
        if opponent_defensive_rating is None:
            # If no defensive history, use default normalization
            normalized_row = player_row.copy()
            normalized_row['normalization_method'] = 'default'
            normalized_stats.append(normalized_row)
            continue
        
        # Create normalized stats
        normalized_row = player_row.copy()
        normalized_row['normalization_method'] = 'advanced_opponent'
        
        # Normalize offensive efficiency metrics
        if 'offensive_possessions' in player_row and player_row['offensive_possessions'] > 0:
            raw_ppp = player_row['offensive_points'] / player_row['offensive_possessions']
            
            # Normalize against opponent's defensive efficiency
            opp_def_eff = opponent_defensive_rating['weighted_defensive_efficiency']
            normalized_row['normalized_ppp'] = raw_ppp / max(opp_def_eff / 100, 0.1)  # Convert to per-possession
            
            # Store opponent metrics for reference
            for metric, value in opponent_defensive_rating.items():
                normalized_row[metric] = value
        
        normalized_stats.append(normalized_row)
    
    return pd.DataFrame(normalized_stats)

def main():
    print("=== Advanced Opponent Strength Normalization ===")
    
    # Load game data
    boxscores = load_game_data()
    if boxscores.empty:
        print("❌ No game data found!")
        return
    
    # Build defensive history
    defensive_history = build_opponent_defensive_history(boxscores)
    if defensive_history.empty:
        print("❌ No defensive history generated!")
        return
    
    # Save defensive history
    defensive_history_path = os.path.join(DATA_DIR, "team_defensive_history.parquet")
    defensive_history.to_parquet(defensive_history_path, index=False)
    print(f"✅ Saved defensive history to {defensive_history_path}")
    
    # Load existing player stats if available
    player_stats_path = os.path.join(DATA_DIR, "player_possession_features.parquet")
    if os.path.exists(player_stats_path):
        print("Loading existing player stats...")
        player_stats = pd.read_parquet(player_stats_path)
        
        # Apply advanced normalization
        normalized_stats = normalize_player_stats_with_opponent_strength(player_stats, defensive_history)
        
        # Save normalized stats
        output_path = os.path.join(DATA_DIR, "player_stats_advanced_normalized.parquet")
        normalized_stats.to_parquet(output_path, index=False)
        print(f"✅ Saved advanced normalized stats to {output_path}")
        
        # Print summary
        print(f"\n=== NORMALIZATION SUMMARY ===")
        print(f"Total player-game records: {len(normalized_stats)}")
        print(f"Advanced normalization applied: {len(normalized_stats[normalized_stats['normalization_method'] == 'advanced_opponent'])}")
        print(f"Default normalization used: {len(normalized_stats[normalized_stats['normalization_method'] == 'default'])}")
        
        # Show sample of normalized metrics
        if 'normalized_ppp' in normalized_stats.columns:
            print(f"\nNormalized PPP Statistics:")
            print(f"Mean: {normalized_stats['normalized_ppp'].mean():.3f}")
            print(f"Std: {normalized_stats['normalized_ppp'].std():.3f}")
            print(f"Min: {normalized_stats['normalized_ppp'].min():.3f}")
            print(f"Max: {normalized_stats['normalized_ppp'].max():.3f}")
        
        return normalized_stats
    else:
        print("❌ No existing player stats found. Run build_possession_based_features.py first.")
        return None

if __name__ == "__main__":
    main() 