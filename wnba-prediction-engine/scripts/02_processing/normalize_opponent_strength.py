import os
import pandas as pd
import numpy as np
from tqdm import tqdm
from datetime import datetime

DATA_DIR = os.path.join('..', '..', 'data')
BOX_DIR = os.path.join(DATA_DIR, 'boxscores')
OUTPUT_FILE = os.path.join(DATA_DIR, 'player_stats_normalized.parquet')

# Parameters
ROLLING_WINDOW = 10
RECENT_WEIGHT = 2  # Last 5 games get double weight
RECENT_GAMES = 5

# Defensive metrics to use
DEF_METRICS = ['def_rating', 'stl_rate', 'blk_rate']

# Load all box score data
boxscore_files = [os.path.join(BOX_DIR, f) for f in os.listdir(BOX_DIR) if f.endswith('.parquet')]
all_boxscores = pd.concat([pd.read_parquet(f) for f in boxscore_files], ignore_index=True)

# Calculate defensive metrics for each team-game
def calc_def_metrics(df):
    # Defensive rating: points allowed per 100 possessions
    opp_points = df['OPP_PTS']
    opp_poss = df['OPP_POSS']
    def_rating = (opp_points / opp_poss.replace(0, np.nan)) * 100
    # Steal rate: steals per opponent possession
    stl_rate = df['STL'] / opp_poss.replace(0, np.nan)
    # Block rate: blocks per opponent FGA
    blk_rate = df['BLK'] / df['OPP_FGA'].replace(0, np.nan)
    return pd.DataFrame({
        'GAME_ID': df['GAME_ID'],
        'TEAM_ID': df['TEAM_ID'],
        'DATE': df['DATE'],
        'def_rating': def_rating,
        'stl_rate': stl_rate,
        'blk_rate': blk_rate
    })

def_metrics = calc_def_metrics(all_boxscores)
def_metrics = def_metrics.sort_values(['TEAM_ID', 'DATE'])

def rolling_weighted_avg(group, col):
    vals = group[col].rolling(ROLLING_WINDOW, min_periods=1)
    result = []
    for i in range(len(group)):
        window = group.iloc[max(0, i-ROLLING_WINDOW):i]
        if window.empty:
            result.append(np.nan)
            continue
        if len(window) <= RECENT_GAMES:
            weights = np.ones(len(window))
        else:
            weights = np.ones(len(window))
            weights[-RECENT_GAMES:] = RECENT_WEIGHT
        avg = np.average(window[col], weights=weights)
        result.append(avg)
    return pd.Series(result, index=group.index)

# Compute rolling, weighted averages for each metric
def add_rolling_metrics(df):
    for metric in DEF_METRICS:
        df[f'rolling_{metric}'] = df.groupby('TEAM_ID', group_keys=False).apply(
            lambda g: rolling_weighted_avg(g, metric)
        )
    return df

def_metrics = add_rolling_metrics(def_metrics)

def get_opponent_metric(row, metric):
    # Find opponent's rolling metric for this game
    game_id = row['GAME_ID']
    team_id = row['TEAM_ID']
    game = def_metrics[def_metrics['GAME_ID'] == game_id]
    opp = game[game['TEAM_ID'] != team_id]
    if not opp.empty:
        return opp.iloc[0][f'rolling_{metric}']
    return np.nan

# Merge with player stats and normalize
player_stats = all_boxscores.copy()  # Replace with your player stats DataFrame if different
for metric in DEF_METRICS:
    player_stats[f'opp_{metric}'] = player_stats.apply(lambda row: get_opponent_metric(row, metric), axis=1)
    player_stats[f'norm_{metric}'] = player_stats[metric] / player_stats[f'opp_{metric}']

# Save output
player_stats.to_parquet(OUTPUT_FILE, index=False)
print(f'Normalized player stats saved to {OUTPUT_FILE}') 