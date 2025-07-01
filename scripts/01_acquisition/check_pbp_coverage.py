import os
import pandas as pd

PBP_DIR = 'data/playbyplay'
DATA_DIR = 'data'

# Count play-by-play files
pbp_files = [f for f in os.listdir(PBP_DIR) if f.endswith('.parquet')]
print('Play-by-play files:', len(pbp_files))

# Count total unique games
files = [f for f in os.listdir(DATA_DIR) if f.startswith('wnba_gamelog_') and f.endswith('.parquet') and 'with_misc_stats' not in f]
game_ids = set()
for f in files:
    df = pd.read_parquet(os.path.join(DATA_DIR, f))
    game_ids.update(df['GAME_ID'].unique())
print('Total unique games:', len(game_ids))

# Calculate missing and percentage
pbp_game_ids = set(f.split('_')[1].replace('.parquet', '') for f in pbp_files)
missing_ids = set(str(gid) for gid in game_ids) - pbp_game_ids
missing = len(missing_ids)
percent_missing = 100 * missing / len(game_ids) if game_ids else 0
print(f'Missing: {missing}')
print(f'Percent missing: {percent_missing:.2f}%')

# Print missing GAME_IDs
if missing_ids:
    print('Missing GAME_IDs:')
    for gid in sorted(missing_ids):
        print(' ', gid) 