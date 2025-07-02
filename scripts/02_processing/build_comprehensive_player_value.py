import os
import pandas as pd
import numpy as np
from tqdm import tqdm
import glob
from datetime import datetime, timedelta

DATA_DIR = "data"
PBP_DIR = os.path.join(DATA_DIR, "playbyplay")

def load_game_data():
    """Load all game data to build comprehensive opponent metrics."""
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

def calculate_comprehensive_opponent_metrics(game_df):
    """Calculate comprehensive offensive and defensive metrics for both teams in a game."""
    teams = game_df['TEAM_ID'].unique()
    if len(teams) != 2:
        return {}
    
    team1, team2 = teams
    game_metrics = {}
    
    for team_id in teams:
        # Get team's stats and opponent's stats
        team_stats = game_df[game_df['TEAM_ID'] == team_id]
        opponent_stats = game_df[game_df['TEAM_ID'] != team_id]
        
        if len(team_stats) == 0 or len(opponent_stats) == 0:
            continue
        
        # Calculate offensive metrics (what this team did)
        team_points = team_stats['PTS'].sum()
        team_fga = team_stats['FGA'].sum()
        team_fg3a = team_stats['FG3A'].sum()
        team_fta = team_stats['FTA'].sum()
        team_tov = team_stats['TOV'].sum()
        team_oreb = team_stats['OREB'].sum()
        team_ast = team_stats['AST'].sum()
        
        # Calculate defensive metrics (what opponent did against this team)
        opp_points = opponent_stats['PTS'].sum()
        opp_fga = opponent_stats['FGA'].sum()
        opp_fg3a = opponent_stats['FG3A'].sum()
        opp_fta = opponent_stats['FTA'].sum()
        opp_tov = opponent_stats['TOV'].sum()
        opp_oreb = opponent_stats['OREB'].sum()
        opp_ast = opponent_stats['AST'].sum()
        
        # Team's defensive stats (steals, blocks, etc.)
        team_stl = team_stats['STL'].sum()
        team_blk = team_stats['BLK'].sum()
        team_pf = team_stats['PF'].sum()
        
        # Estimate possessions
        team_possessions = team_fga + 0.44 * team_fta + team_tov
        opp_possessions = opp_fga + 0.44 * opp_fta + opp_tov
        
        # Offensive efficiency
        offensive_efficiency = (team_points / max(team_possessions, 1)) * 100
        
        # Defensive efficiency (points allowed per 100 possessions)
        defensive_efficiency = (opp_points / max(opp_possessions, 1)) * 100
        
        # Shooting percentages
        team_fg_pct = team_stats['FG_PCT'].mean() if team_fga > 0 else 0
        team_fg3_pct = team_stats['FG3_PCT'].mean() if team_fg3a > 0 else 0
        team_ft_pct = team_stats['FT_PCT'].mean() if team_fta > 0 else 0
        
        opp_fg_pct = opponent_stats['FG_PCT'].mean() if opp_fga > 0 else 0
        opp_fg3_pct = opponent_stats['FG3_PCT'].mean() if opp_fg3a > 0 else 0
        opp_ft_pct = opponent_stats['FT_PCT'].mean() if opp_fta > 0 else 0
        
        # Rate-based metrics
        turnover_rate = team_tov / max(team_possessions, 1)
        offensive_rebound_rate = team_oreb / max(team_fga - team_stats['FG_PCT'].fillna(0) * team_fga, 1)
        assist_rate = team_ast / max(team_fga, 1)
        
        opp_turnover_rate = opp_tov / max(opp_possessions, 1)
        opp_offensive_rebound_rate = opp_oreb / max(opp_fga - opponent_stats['FG_PCT'].fillna(0) * opp_fga, 1)
        opp_assist_rate = opp_ast / max(opp_fga, 1)
        
        # Defensive rate metrics
        steal_rate = team_stl / max(opp_possessions, 1)
        block_rate = team_blk / max(opp_fga, 1)
        ft_rate_allowed = opp_fta / max(opp_fga, 1)
        
        game_metrics[team_id] = {
            # Offensive metrics (team's offensive performance)
            'offensive_efficiency': offensive_efficiency,
            'fg_pct': team_fg_pct,
            'fg3_pct': team_fg3_pct,
            'ft_pct': team_ft_pct,
            'turnover_rate': turnover_rate,
            'offensive_rebound_rate': offensive_rebound_rate,
            'assist_rate': assist_rate,
            'points': team_points,
            'possessions': team_possessions,
            
            # Defensive metrics (team's defensive performance)
            'defensive_efficiency': defensive_efficiency,
            'opp_fg_pct': opp_fg_pct,
            'opp_fg3_pct': opp_fg3_pct,
            'opp_ft_pct': opp_ft_pct,
            'opp_turnover_rate': opp_turnover_rate,
            'opp_offensive_rebound_rate': opp_offensive_rebound_rate,
            'opp_assist_rate': opp_assist_rate,
            'steal_rate': steal_rate,
            'block_rate': block_rate,
            'ft_rate_allowed': ft_rate_allowed,
            'opp_points': opp_points,
            'opp_possessions': opp_possessions
        }
    
    return game_metrics

def build_comprehensive_opponent_history(boxscores):
    """Build comprehensive offensive and defensive history for each team."""
    print("Building comprehensive opponent history...")
    
    # Sort by date or game order
    if 'GAME_DATE' in boxscores.columns:
        boxscores = boxscores.sort_values(['TEAM_ID', 'GAME_DATE'])
    else:
        boxscores = boxscores.sort_values(['TEAM_ID', 'GAME_ID'])
    
    # Group by team and game
    team_games = boxscores.groupby(['TEAM_ID', 'GAME_ID']).first().reset_index()
    
    all_metrics = []
    
    for team_id in tqdm(team_games['TEAM_ID'].unique(), desc="Processing teams"):
        team_games_subset = team_games[team_games['TEAM_ID'] == team_id]
        
        for idx, game_row in team_games_subset.iterrows():
            game_id = game_row['GAME_ID']
            
            # Get the full game data
            game_data = boxscores[boxscores['GAME_ID'] == game_id]
            
            if len(game_data) == 0:
                continue
                
            game_metrics = calculate_comprehensive_opponent_metrics(game_data)
            
            if team_id in game_metrics:
                metrics = game_metrics[team_id]
                metrics['TEAM_ID'] = team_id
                metrics['GAME_ID'] = game_id
                if 'GAME_DATE' in game_row:
                    metrics['GAME_DATE'] = game_row['GAME_DATE']
                all_metrics.append(metrics)
    
    if all_metrics:
        metrics_df = pd.DataFrame(all_metrics)
        print(f"Generated comprehensive metrics for {len(metrics_df)} team-games")
        return metrics_df
    else:
        print("No comprehensive metrics generated!")
        return pd.DataFrame()

def calculate_weighted_opponent_ratings(team_id, game_id, opponent_history, lookback_games=10, recent_weight=1.5):
    """Calculate weighted offensive and defensive ratings for opponent strength assessment."""
    
    # Get team's history up to this game
    team_history = opponent_history[
        (opponent_history['TEAM_ID'] == team_id) & 
        (opponent_history['GAME_ID'] < game_id)
    ].sort_values('GAME_ID').tail(lookback_games)
    
    if len(team_history) == 0:
        return None
    
    # Split into recent and older games
    if len(team_history) >= 5:
        recent_games = team_history.tail(5)
        older_games = team_history.head(len(team_history) - 5)
    else:
        recent_games = team_history
        older_games = pd.DataFrame()
    
    # Calculate weighted averages for all metrics
    weighted_metrics = {}
    
    metric_columns = [
        'offensive_efficiency', 'fg_pct', 'fg3_pct', 'ft_pct', 'turnover_rate', 
        'offensive_rebound_rate', 'assist_rate', 'defensive_efficiency', 
        'opp_fg_pct', 'opp_fg3_pct', 'opp_ft_pct', 'opp_turnover_rate',
        'opp_offensive_rebound_rate', 'opp_assist_rate', 'steal_rate', 
        'block_rate', 'ft_rate_allowed'
    ]
    
    for metric in metric_columns:
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

def calculate_player_comprehensive_value(player_stats_df, opponent_history, boxscores):
    """Calculate comprehensive player value with opponent-specific normalization."""
    print("Calculating comprehensive player value...")
    
    # Load box scores for minutes data
    boxscore_files = glob.glob(os.path.join(DATA_DIR, "wnba_gamelog_*.parquet"))
    all_boxscores = []
    for file in boxscore_files:
        df = pd.read_parquet(file)
        all_boxscores.append(df)
    
    if all_boxscores:
        all_boxscores_df = pd.concat(all_boxscores, ignore_index=True)
    else:
        print("No box score data found for minutes!")
        return pd.DataFrame()
    
    comprehensive_stats = []
    
    for idx, player_row in tqdm(player_stats_df.iterrows(), total=len(player_stats_df), desc="Calculating player value"):
        game_id = player_row['GAME_ID']
        team_id = player_row['TEAM_ID']
        player_id = player_row['PLAYER_ID']
        
        # Get player's minutes from box scores
        player_boxscore = all_boxscores_df[
            (all_boxscores_df['GAME_ID'] == game_id) & 
            (all_boxscores_df['PLAYER_ID'] == player_id)
        ]
        
        if len(player_boxscore) == 0:
            continue
            
        minutes = player_boxscore['MIN'].iloc[0]
        if pd.isna(minutes) or minutes == 0:
            continue
        
        # Get opponent's weighted ratings for this game
        opponent_ratings = calculate_weighted_opponent_ratings(
            team_id, game_id, opponent_history
        )
        
        if opponent_ratings is None:
            continue
        
        # Create comprehensive player value record
        player_value = player_row.copy()
        player_value['minutes'] = minutes
        player_value['normalization_method'] = 'comprehensive_opponent'
        
        # Normalize offensive stats against opponent's defensive strength
        if 'offensive_possessions' in player_row and player_row['offensive_possessions'] > 0:
            raw_ppp = player_row['offensive_points'] / player_row['offensive_possessions']
            
            # Normalize against opponent's defensive efficiency
            opp_def_eff = opponent_ratings['weighted_defensive_efficiency']
            player_value['normalized_offensive_ppp'] = raw_ppp / max(opp_def_eff / 100, 0.1)
            
            # Calculate offensive value contribution (points above opponent's defensive average)
            baseline_ppp = opp_def_eff / 100
            player_value['offensive_value'] = (raw_ppp - baseline_ppp) * player_row['offensive_possessions']
        
        # Get player's defensive stats from box score
        player_defensive_stats = {
            'steals': player_boxscore['STL'].iloc[0] if 'STL' in player_boxscore.columns else 0,
            'blocks': player_boxscore['BLK'].iloc[0] if 'BLK' in player_boxscore.columns else 0,
            'defensive_rebounds': player_boxscore['DREB'].iloc[0] if 'DREB' in player_boxscore.columns else 0,
            'personal_fouls': player_boxscore['PF'].iloc[0] if 'PF' in player_boxscore.columns else 0
        }
        
        # Normalize defensive stats against opponent's offensive strength
        opp_off_eff = opponent_ratings['weighted_offensive_efficiency']
        opp_turnover_rate = opponent_ratings['weighted_opp_turnover_rate']
        opp_assist_rate = opponent_ratings['weighted_opp_assist_rate']
        
        # Calculate defensive value (preventing opponent points)
        defensive_value = 0
        
        # Steals (prevent opponent possessions)
        if player_defensive_stats['steals'] > 0:
            opp_ppp = opp_off_eff / 100
            steal_value = player_defensive_stats['steals'] * opp_ppp
            defensive_value += steal_value
            player_value['steal_value'] = steal_value
        
        # Blocks (prevent opponent field goals)
        if player_defensive_stats['blocks'] > 0:
            opp_fg_pct = opponent_ratings['weighted_opp_fg_pct']
            block_value = player_defensive_stats['blocks'] * 2 * opp_fg_pct  # Assume 2 points prevented
            defensive_value += block_value
            player_value['block_value'] = block_value
        
        # Defensive rebounds (prevent opponent offensive rebounds)
        if player_defensive_stats['defensive_rebounds'] > 0:
            opp_oreb_rate = opponent_ratings['weighted_opp_offensive_rebound_rate']
            opp_ppp = opp_off_eff / 100
            dreb_value = player_defensive_stats['defensive_rebounds'] * opp_oreb_rate * opp_ppp
            defensive_value += dreb_value
            player_value['defensive_rebound_value'] = dreb_value
        
        player_value['defensive_value'] = defensive_value
        
        # Calculate net value (offensive + defensive)
        offensive_value = player_value.get('offensive_value', 0)
        player_value['net_value'] = offensive_value + defensive_value
        
        # Calculate per-minute value
        player_value['offensive_value_per_minute'] = offensive_value / minutes
        player_value['defensive_value_per_minute'] = defensive_value / minutes
        player_value['net_value_per_minute'] = player_value['net_value'] / minutes
        
        # Store opponent ratings for reference
        for metric, value in opponent_ratings.items():
            player_value[metric] = value
        
        comprehensive_stats.append(player_value)
    
    return pd.DataFrame(comprehensive_stats)

def main():
    print("=== Comprehensive Player Value Calculation ===")
    
    # Load game data
    boxscores = load_game_data()
    if boxscores.empty:
        print("❌ No game data found!")
        return
    
    # Build comprehensive opponent history
    opponent_history = build_comprehensive_opponent_history(boxscores)
    if opponent_history.empty:
        print("❌ No opponent history generated!")
        return
    
    # Save comprehensive history
    history_path = os.path.join(DATA_DIR, "comprehensive_opponent_history.parquet")
    opponent_history.to_parquet(history_path, index=False)
    print(f"✅ Saved comprehensive opponent history to {history_path}")
    
    # Load existing player stats
    player_stats_path = os.path.join(DATA_DIR, "player_possession_features.parquet")
    if os.path.exists(player_stats_path):
        print("Loading existing player stats...")
        player_stats = pd.read_parquet(player_stats_path)
        
        # Calculate comprehensive player value
        comprehensive_stats = calculate_player_comprehensive_value(player_stats, opponent_history, boxscores)
        
        if not comprehensive_stats.empty:
            # Save comprehensive stats
            output_path = os.path.join(DATA_DIR, "player_comprehensive_value.parquet")
            comprehensive_stats.to_parquet(output_path, index=False)
            print(f"✅ Saved comprehensive player value to {output_path}")
            
            # Print summary
            print(f"\n=== COMPREHENSIVE PLAYER VALUE SUMMARY ===")
            print(f"Total player-game records: {len(comprehensive_stats)}")
            print(f"Players with comprehensive normalization: {len(comprehensive_stats[comprehensive_stats['normalization_method'] == 'comprehensive_opponent'])}")
            
            # Show value statistics
            if 'net_value_per_minute' in comprehensive_stats.columns:
                print(f"\nNet Value Per Minute Statistics:")
                print(f"Mean: {comprehensive_stats['net_value_per_minute'].mean():.4f}")
                print(f"Std: {comprehensive_stats['net_value_per_minute'].std():.4f}")
                print(f"Min: {comprehensive_stats['net_value_per_minute'].min():.4f}")
                print(f"Max: {comprehensive_stats['net_value_per_minute'].max():.4f}")
            
            if 'offensive_value_per_minute' in comprehensive_stats.columns:
                print(f"\nOffensive Value Per Minute Statistics:")
                print(f"Mean: {comprehensive_stats['offensive_value_per_minute'].mean():.4f}")
                print(f"Std: {comprehensive_stats['offensive_value_per_minute'].std():.4f}")
            
            if 'defensive_value_per_minute' in comprehensive_stats.columns:
                print(f"\nDefensive Value Per Minute Statistics:")
                print(f"Mean: {comprehensive_stats['defensive_value_per_minute'].mean():.4f}")
                print(f"Std: {comprehensive_stats['defensive_value_per_minute'].std():.4f}")
            
            return comprehensive_stats
        else:
            print("❌ No comprehensive stats generated!")
            return None
    else:
        print("❌ No existing player stats found. Run build_possession_based_features.py first.")
        return None

if __name__ == "__main__":
    main()
