#!/usr/bin/env python3
"""
Rebuild channel_base.csv — the per-team-game channel dataset the channel experiment runs on.
Inputs: master_team_cleaned.csv + master_player.csv (Drive exports, or rebuilt masters).
After the data refresh, regenerate the masters first (merge data/refresh_2026 into them), then run this.
"""
import pandas as pd

TEAM_CSV = 'data/master_team_cleaned.csv'
PLAYER_CSV = 'data/master_player.csv'
OUT = 'channel_base.csv'

team = pd.read_csv(TEAM_CSV)
player = pd.read_csv(PLAYER_CSV, low_memory=False).drop_duplicates(subset=['GAME_ID', 'PLAYER_ID'])

agg = player.groupby(['GAME_ID', 'TEAM_ID']).agg(
    team_pts_paint=('player_pts_paint', 'sum'),
    team_pfd=('player_pfd', 'sum'),
).reset_index()

df = team.merge(agg, on=['GAME_ID', 'TEAM_ID'], how='left')

# channels (box-score identity: ch_ft + ch_3pt + pts_2s == team_pts, verify below)
df['ch_ft'] = df.team_ftm
df['ch_3pt'] = df.team_fg3m * 3
df['pts_2s'] = (df.team_fgm - df.team_fg3m) * 2
df['ch_paint'] = df.team_pts_paint
df['ch_np2'] = df.pts_2s - df.team_pts_paint
df['is_home'] = df.MATCHUP.str.contains('vs').astype(int)
df['GAME_DATE'] = pd.to_datetime(df.GAME_DATE)

viol = (df.ch_ft + df.ch_3pt + df.pts_2s - df.team_pts).abs().gt(0).sum()
neg = (df.ch_np2 < 0).sum()
print(f'identity violations: {viol} | negative non-paint-2s: {neg} (both must be 0 on clean data)')

keep = ['GAME_ID', 'TEAM_ID', 'TEAM_ABBREVIATION', 'GAME_DATE', 'year', 'season_type', 'is_home',
        'team_pf', 'team_pfd', 'team_fta', 'team_ftm', 'team_ft_pct', 'team_fg3a', 'team_fg3m',
        'team_fga', 'team_fgm', 'team_pts_paint', 'team_pts',
        'ch_ft', 'ch_3pt', 'ch_paint', 'ch_np2', 'pts_2s']
d = df[keep].copy()

opp = d[['GAME_ID', 'TEAM_ID', 'team_pf', 'team_fta', 'team_fg3a', 'team_fg3m', 'team_ftm',
         'ch_3pt', 'ch_paint', 'ch_np2', 'ch_ft', 'team_pts']].copy()
opp.columns = ['GAME_ID', 'OPP_TEAM_ID', 'opp_pf', 'opp_fta', 'opp_fg3a', 'opp_fg3m', 'opp_ftm',
               'opp_ch_3pt', 'opp_ch_paint', 'opp_ch_np2', 'opp_ch_ft', 'opp_pts']
pairs = d.merge(opp, on='GAME_ID')
pairs = pairs[pairs.TEAM_ID != pairs.OPP_TEAM_ID].sort_values(['TEAM_ID', 'GAME_DATE']).reset_index(drop=True)
pairs.to_csv(OUT, index=False)
print(f'{len(pairs)} team-game rows -> {OUT}')
print(pairs.groupby('year')[['ch_ft', 'ch_3pt', 'ch_paint', 'ch_np2']].mean().round(1))
print('^ sanity: paint ~34-36 and np2 ~7-10 every season; a season with paint ~0 means broken misc data')
