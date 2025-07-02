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

def calculate_phd_opponent_metrics(game_df):
    """Calculate PhD-level offensive and defensive metrics with advanced context."""
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
        
        # Basic offensive stats
        team_points = team_stats['PTS'].sum()
        team_fga = team_stats['FGA'].sum()
        team_fg2a = team_fga - team_stats['FG3A'].sum()  # 2PT attempts
        team_fg3a = team_stats['FG3A'].sum()
        team_fg2m = team_stats['FGM'].sum() - team_stats['FG3M'].sum()  # 2PT makes
        team_fg3m = team_stats['FG3M'].sum()  # 3PT makes
        team_fta = team_stats['FTA'].sum()
        team_ftm = team_stats['FTM'].sum()
        team_tov = team_stats['TOV'].sum()
        team_oreb = team_stats['OREB'].sum()
        team_ast = team_stats['AST'].sum()
        team_fgm = team_stats['FGM'].sum()
        
        # Opponent stats
        opp_points = opponent_stats['PTS'].sum()
        opp_fga = opponent_stats['FGA'].sum()
        opp_fg2a = opp_fga - opponent_stats['FG3A'].sum()
        opp_fg3a = opponent_stats['FG3A'].sum()
        opp_fg2m = opponent_stats['FGM'].sum() - opponent_stats['FG3M'].sum()
        opp_fg3m = opponent_stats['FG3M'].sum()
        opp_fta = opponent_stats['FTA'].sum()
        opp_ftm = opponent_stats['FTM'].sum()
        opp_tov = opponent_stats['TOV'].sum()
        opp_oreb = opponent_stats['OREB'].sum()
        opp_ast = opponent_stats['AST'].sum()
        opp_fgm = opponent_stats['FGM'].sum()
        
        # Team's defensive stats
        team_stl = team_stats['STL'].sum()
        team_blk = team_stats['BLK'].sum()
        team_pf = team_stats['PF'].sum()
        
        # Estimate possessions
        team_possessions = team_fga + 0.44 * team_fta + team_tov
        opp_possessions = opp_fga + 0.44 * opp_fta + opp_tov
        
        # Offensive efficiency
        offensive_efficiency = (team_points / max(team_possessions, 1)) * 100
        
        # Defensive efficiency
        defensive_efficiency = (opp_points / max(opp_possessions, 1)) * 100
        
        # Shooting percentages
        team_fg_pct = team_stats['FG_PCT'].mean() if team_fga > 0 else 0
        team_fg2_pct = team_fg2m / max(team_fg2a, 1) if team_fg2a > 0 else 0
        team_fg3_pct = team_stats['FG3_PCT'].mean() if team_fg3a > 0 else 0
        team_ft_pct = team_stats['FT_PCT'].mean() if team_fta > 0 else 0
        
        opp_fg_pct = opponent_stats['FG_PCT'].mean() if opp_fga > 0 else 0
        opp_fg2_pct = opp_fg2m / max(opp_fg2a, 1) if opp_fg2a > 0 else 0
        opp_fg3_pct = opponent_stats['FG3_PCT'].mean() if opp_fg3a > 0 else 0
        opp_ft_pct = opponent_stats['FT_PCT'].mean() if opp_fta > 0 else 0
        
        # PhD-Level: Expected Points Per Shot
        team_expected_pts_per_shot = (team_fg2a * team_fg2_pct * 2 + team_fg3a * team_fg3_pct * 3) / max(team_fga, 1)
        opp_expected_pts_per_shot = (opp_fg2a * opp_fg2_pct * 2 + opp_fg3a * opp_fg3_pct * 3) / max(opp_fga, 1)
        
        # True Shooting Percentage
        team_ts_pct = team_points / (2 * (team_fga + 0.44 * team_fta)) if (team_fga + 0.44 * team_fta) > 0 else 0
        opp_ts_pct = opp_points / (2 * (opp_fga + 0.44 * opp_fta)) if (opp_fga + 0.44 * opp_fta) > 0 else 0
        
        # Effective Field Goal Percentage
        team_efg_pct = (team_fgm + 0.5 * team_fg3m) / max(team_fga, 1) if team_fga > 0 else 0
        opp_efg_pct = (opp_fgm + 0.5 * opp_fg3m) / max(opp_fga, 1) if opp_fga > 0 else 0
        
        # Rate-based metrics
        turnover_rate = team_tov / max(team_possessions, 1)
        offensive_rebound_rate = team_oreb / max(team_fga - team_fgm, 1)
        assist_rate = team_ast / max(team_fgm, 1)
        ft_rate = team_fta / max(team_fga, 1)
        
        opp_turnover_rate = opp_tov / max(opp_possessions, 1)
        opp_offensive_rebound_rate = opp_oreb / max(opp_fga - opp_fgm, 1)
        opp_assist_rate = opp_ast / max(opp_fgm, 1)
        opp_ft_rate = opp_fta / max(opp_fga, 1)
        
        # Defensive rate metrics
        steal_rate = team_stl / max(opp_possessions, 1)
        block_rate = team_blk / max(opp_fga, 1)
        ft_rate_allowed = opp_fta / max(opp_fga, 1)
        
        # Second chance points (improved estimate)
        second_chance_ppp = (opp_oreb * opp_expected_pts_per_shot) / max(opp_oreb, 1)
        
        # Transition efficiency (simplified - would need play-by-play for true calculation)
        # For now, use a league-average estimate
        transition_bonus = 0.2  # This would be dynamic in a full implementation
        
        game_metrics[team_id] = {
            # Offensive metrics
            'offensive_efficiency': offensive_efficiency,
            'fg_pct': team_fg_pct,
            'fg2_pct': team_fg2_pct,
            'fg3_pct': team_fg3_pct,
            'ft_pct': team_ft_pct,
            'ts_pct': team_ts_pct,
            'efg_pct': team_efg_pct,
            'expected_pts_per_shot': team_expected_pts_per_shot,
            'turnover_rate': turnover_rate,
            'offensive_rebound_rate': offensive_rebound_rate,
            'assist_rate': assist_rate,
            'ft_rate': ft_rate,
            'points': team_points,
            'possessions': team_possessions,
            'fgm': team_fgm,
            'fg2m': team_fg2m,
            'fg3m': team_fg3m,
            'ftm': team_ftm,
            'fga': team_fga,
            'fg2a': team_fg2a,
            'fg3a': team_fg3a,
            'fta': team_fta,
            
            # Defensive metrics
            'defensive_efficiency': defensive_efficiency,
            'opp_fg_pct': opp_fg_pct,
            'opp_fg2_pct': opp_fg2_pct,
            'opp_fg3_pct': opp_fg3_pct,
            'opp_ft_pct': opp_ft_pct,
            'opp_ts_pct': opp_ts_pct,
            'opp_efg_pct': opp_efg_pct,
            'opp_expected_pts_per_shot': opp_expected_pts_per_shot,
            'opp_turnover_rate': opp_turnover_rate,
            'opp_offensive_rebound_rate': opp_offensive_rebound_rate,
            'opp_assist_rate': opp_assist_rate,
            'opp_ft_rate': opp_ft_rate,
            'steal_rate': steal_rate,
            'block_rate': block_rate,
            'ft_rate_allowed': ft_rate_allowed,
            'opp_points': opp_points,
            'opp_possessions': opp_possessions,
            'opp_fgm': opp_fgm,
            'opp_fg2m': opp_fg2m,
            'opp_fg3m': opp_fg3m,
            'opp_ftm': opp_ftm,
            'opp_fga': opp_fga,
            'opp_fg2a': opp_fg2a,
            'opp_fg3a': opp_fg3a,
            'opp_fta': opp_fta,
            'second_chance_ppp': second_chance_ppp,
            'transition_bonus': transition_bonus
        }
    
    return game_metrics

def build_phd_opponent_history(boxscores):
    """Build PhD-level offensive and defensive history for each team."""
    print("Building PhD-level opponent history...")
    
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
                
            game_metrics = calculate_phd_opponent_metrics(game_data)
            
            if team_id in game_metrics:
                metrics = game_metrics[team_id]
                metrics['TEAM_ID'] = team_id
                metrics['GAME_ID'] = game_id
                if 'GAME_DATE' in game_row:
                    metrics['GAME_DATE'] = game_row['GAME_DATE']
                all_metrics.append(metrics)
    
    if all_metrics:
        metrics_df = pd.DataFrame(all_metrics)
        print(f"Generated PhD-level metrics for {len(metrics_df)} team-games")
        return metrics_df
    else:
        print("No PhD-level metrics generated!")
        return pd.DataFrame()

def calculate_weighted_phd_ratings(team_id, game_id, opponent_history, lookback_games=10, recent_weight=1.5):
    """Calculate weighted PhD-level ratings for opponent strength assessment."""
    
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
        'offensive_efficiency', 'fg_pct', 'fg2_pct', 'fg3_pct', 'ft_pct', 'ts_pct', 'efg_pct', 
        'expected_pts_per_shot', 'turnover_rate', 'offensive_rebound_rate', 'assist_rate', 
        'ft_rate', 'defensive_efficiency', 'opp_fg_pct', 'opp_fg2_pct', 'opp_fg3_pct', 
        'opp_ft_pct', 'opp_ts_pct', 'opp_efg_pct', 'opp_expected_pts_per_shot',
        'opp_turnover_rate', 'opp_offensive_rebound_rate', 'opp_assist_rate', 'opp_ft_rate', 
        'steal_rate', 'block_rate', 'ft_rate_allowed', 'second_chance_ppp', 'transition_bonus'
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

def calculate_phd_player_value(player_stats_df, opponent_history, boxscores):
    """Calculate PhD-level player value with corrected statistical formulas."""
    print("Calculating PhD-level player value...")
    
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
    
    phd_stats = []
    
    for idx, player_row in tqdm(player_stats_df.iterrows(), total=len(player_stats_df), desc="Calculating PhD-level player value"):
        game_id = player_row['GAME_ID']
        team_id = player_row['TEAM_ID']
        player_id = player_row['PLAYER_ID']
        
        # Get player's minutes and stats from box scores
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
        opponent_ratings = calculate_weighted_phd_ratings(
            team_id, game_id, opponent_history
        )
        
        if opponent_ratings is None:
            continue
        
        # Create PhD-level player value record
        player_value = player_row.copy()
        player_value['minutes'] = minutes
        player_value['normalization_method'] = 'phd_level'
        
        # Get player's detailed stats
        player_stats = {
            'points': player_boxscore['PTS'].iloc[0] if 'PTS' in player_boxscore.columns else 0,
            'assists': player_boxscore['AST'].iloc[0] if 'AST' in player_boxscore.columns else 0,
            'steals': player_boxscore['STL'].iloc[0] if 'STL' in player_boxscore.columns else 0,
            'blocks': player_boxscore['BLK'].iloc[0] if 'BLK' in player_boxscore.columns else 0,
            'defensive_rebounds': player_boxscore['DREB'].iloc[0] if 'DREB' in player_boxscore.columns else 0,
            'turnovers': player_boxscore['TOV'].iloc[0] if 'TOV' in player_boxscore.columns else 0,
            'fg3m': player_boxscore['FG3M'].iloc[0] if 'FG3M' in player_boxscore.columns else 0,
            'fg3a': player_boxscore['FG3A'].iloc[0] if 'FG3A' in player_boxscore.columns else 0,
            'fg2m': player_boxscore['FGM'].iloc[0] - player_boxscore['FG3M'].iloc[0] if 'FGM' in player_boxscore.columns else 0,
            'fg2a': player_boxscore['FGA'].iloc[0] - player_boxscore['FG3A'].iloc[0] if 'FGA' in player_boxscore.columns else 0,
            'ftm': player_boxscore['FTM'].iloc[0] if 'FTM' in player_boxscore.columns else 0,
            'fta': player_boxscore['FTA'].iloc[0] if 'FTA' in player_boxscore.columns else 0,
            'personal_fouls': player_boxscore['PF'].iloc[0] if 'PF' in player_boxscore.columns else 0
        }
        
        # Get team stats for context
        team_boxscore = all_boxscores_df[
            (all_boxscores_df['GAME_ID'] == game_id) & 
            (all_boxscores_df['TEAM_ID'] == team_id)
        ]
        team_fgm = team_boxscore['FGM'].sum() if 'FGM' in team_boxscore.columns else 0
        team_ast = team_boxscore['AST'].sum() if 'AST' in team_boxscore.columns else 0
        team_minutes = team_boxscore['MIN'].sum() if 'MIN' in team_boxscore.columns else 0
        
        # Calculate PhD-level offensive value
        offensive_value = 0
        
        # 1. CORRECTED: Offensive Scoring Value using True Shooting %
        if player_stats['fga'] > 0 or player_stats['fta'] > 0:
            # Calculate player's True Shooting %
            player_ts_pct = player_stats['points'] / (2 * (player_stats['fga'] + 0.44 * player_stats['fta'])) if (player_stats['fga'] + 0.44 * player_stats['fta']) > 0 else 0
            
            # Get opponent's allowed eFG% (proxy for defensive efficiency)
            opp_efg_pct = opponent_ratings['weighted_opp_efg_pct']
            
            # Calculate offensive scoring value
            scoring_value = (player_ts_pct - opp_efg_pct) * 2 * player_stats['fga']
            offensive_value += scoring_value
            player_value['scoring_value'] = scoring_value
            player_value['ts_pct'] = player_ts_pct
        
        # 2. CORRECTED: 3PT Value Over Expectation
        if player_stats['fg3a'] > 0:
            opp_fg3_pct = opponent_ratings['weighted_opp_fg3_pct']
            expected_3pm = player_stats['fg3a'] * opp_fg3_pct
            three_pt_value = (player_stats['fg3m'] - expected_3pm) * 3
            offensive_value += three_pt_value
            player_value['three_pt_value'] = three_pt_value
        
        # 3. CORRECTED: Playmaking Value (Value Over Replacement)
        if player_stats['assists'] > 0 and team_minutes > 0:
            # Calculate expected assists based on teammate performance
            player_minute_share = minutes / team_minutes
            teammate_assists = team_ast - player_stats['assists']
            expected_assists = player_minute_share * teammate_assists
            
            # Average points per assist (typically ~2.2)
            avg_points_per_assist = 2.2
            
            playmaking_value = (player_stats['assists'] - expected_assists) * avg_points_per_assist
            offensive_value += playmaking_value
            player_value['playmaking_value'] = playmaking_value
        
        # 4. CORRECTED: FT Value Over Expectation
        if player_stats['fta'] > 0:
            opp_ft_rate = opponent_ratings['weighted_opp_ft_rate']
            team_fga = team_boxscore['FGA'].sum() if 'FGA' in team_boxscore.columns else 0
            expected_fta = team_fga * opp_ft_rate / 5  # Assume equal distribution
            ft_value = player_stats['fta'] - expected_fta
            offensive_value += ft_value
            player_value['ft_value'] = ft_value
        
        # 5. CORRECTED: Turnover Cost (not normalized, direct cost)
        if player_stats['turnovers'] > 0:
            opp_ppp = opponent_ratings['weighted_offensive_efficiency'] / 100
            turnover_cost = -player_stats['turnovers'] * opp_ppp  # Direct cost
            offensive_value += turnover_cost
            player_value['turnover_cost'] = turnover_cost
        
        # Calculate PhD-level defensive value
        defensive_value = 0
        
        # 6. CORRECTED: Steals with Transition Bonus
        if player_stats['steals'] > 0:
            opp_ppp = opponent_ratings['weighted_offensive_efficiency'] / 100
            transition_bonus = opponent_ratings.get('weighted_transition_bonus', 0.2)
            steal_value = player_stats['steals'] * (opp_ppp + transition_bonus)
            defensive_value += steal_value
            player_value['steal_value'] = steal_value
        
        # 7. CORRECTED: Defensive Rebounds with Second Chance Context
        if player_stats['defensive_rebounds'] > 0:
            opp_oreb_rate = opponent_ratings['weighted_opp_offensive_rebound_rate']
            second_chance_ppp = opponent_ratings.get('weighted_second_chance_ppp', opp_ppp)
            dreb_value = player_stats['defensive_rebounds'] * opp_oreb_rate * second_chance_ppp
            defensive_value += dreb_value
            player_value['defensive_rebound_value'] = dreb_value
        
        # 8. CORRECTED: Blocks with Expected Points Prevented
        if player_stats['blocks'] > 0:
            opp_expected_pts_per_shot = opponent_ratings['weighted_opp_expected_pts_per_shot']
            block_retention = 0.6  # Not all blocks become possession changes
            block_value = player_stats['blocks'] * opp_expected_pts_per_shot * block_retention
            defensive_value += block_value
            player_value['block_value'] = block_value
        
        # 9. CORRECTED: Personal Fouls as Direct Cost
        if player_stats['personal_fouls'] > 0:
            opp_ft_pct = opponent_ratings['weighted_opp_ft_pct']
            # Estimate FTA from fouls (not all fouls result in FTA)
            estimated_fta_from_fouls = player_stats['personal_fouls'] * 0.7  # ~70% of fouls result in FTA
            foul_cost = -estimated_fta_from_fouls * opp_ft_pct
            defensive_value += foul_cost
            player_value['foul_cost'] = foul_cost
        
        player_value['offensive_value'] = offensive_value
        player_value['defensive_value'] = defensive_value
        
        # Calculate net value
        player_value['net_value'] = offensive_value + defensive_value
        
        # Calculate per-minute value
        player_value['offensive_value_per_minute'] = offensive_value / minutes
        player_value['defensive_value_per_minute'] = defensive_value / minutes
        player_value['net_value_per_minute'] = player_value['net_value'] / minutes
        
        # Store opponent ratings for reference
        for metric, value in opponent_ratings.items():
            player_value[metric] = value
        
        phd_stats.append(player_value)
    
    return pd.DataFrame(phd_stats)

def main():
    print("=== PhD-Level Player Value Calculation ===")
    
    # Load game data
    boxscores = load_game_data()
    if boxscores.empty:
        print("❌ No game data found!")
        return
    
    # Build PhD-level opponent history
    opponent_history = build_phd_opponent_history(boxscores)
    if opponent_history.empty:
        print("❌ No opponent history generated!")
        return
    
    # Save PhD-level history
    history_path = os.path.join(DATA_DIR, "phd_opponent_history.parquet")
    opponent_history.to_parquet(history_path, index=False)
    print(f"✅ Saved PhD-level opponent history to {history_path}")
    
    # Load existing player stats
    player_stats_path = os.path.join(DATA_DIR, "player_possession_features.parquet")
    if os.path.exists(player_stats_path):
        print("Loading existing player stats...")
        player_stats = pd.read_parquet(player_stats_path)
        
        # Calculate PhD-level player value
        phd_stats = calculate_phd_player_value(player_stats, opponent_history, boxscores)
        
        if not phd_stats.empty:
            # Save PhD-level stats
            output_path = os.path.join(DATA_DIR, "player_phd_value.parquet")
            phd_stats.to_parquet(output_path, index=False)
            print(f"✅ Saved PhD-level player value to {output_path}")
            
            # Print summary
            print(f"\n=== PhD-LEVEL PLAYER VALUE SUMMARY ===")
            print(f"Total player-game records: {len(phd_stats)}")
            print(f"Players with PhD-level normalization: {len(phd_stats[phd_stats['normalization_method'] == 'phd_level'])}")
            
            # Show value statistics
            if 'net_value_per_minute' in phd_stats.columns:
                print(f"\nNet Value Per Minute Statistics:")
                print(f"Mean: {phd_stats['net_value_per_minute'].mean():.4f}")
                print(f"Std: {phd_stats['net_value_per_minute'].std():.4f}")
                print(f"Min: {phd_stats['net_value_per_minute'].min():.4f}")
                print(f"Max: {phd_stats['net_value_per_minute'].max():.4f}")
            
            # Show component statistics
            components = ['offensive_value_per_minute', 'defensive_value_per_minute', 
                        'scoring_value', 'playmaking_value', 'steal_value', 'block_value', 
                        'defensive_rebound_value', 'turnover_cost', 'foul_cost']
            
            for component in components:
                if component in phd_stats.columns:
                    print(f"\n{component.replace('_', ' ').title()} Statistics:")
                    print(f"Mean: {phd_stats[component].mean():.4f}")
                    print(f"Std: {phd_stats[component].std():.4f}")
            
            return phd_stats
        else:
            print("❌ No PhD-level stats generated!")
            return None
    else:
        print("❌ No existing player stats found. Run build_possession_based_features.py first.")
        return None

if __name__ == "__main__":
    main()
