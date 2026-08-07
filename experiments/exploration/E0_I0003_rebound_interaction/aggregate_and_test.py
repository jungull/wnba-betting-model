"""
E0 I0003 scratch script 2/3 -- aggregate events.pkl (from build_events.py) into
player-season opportunity/secure counts, check year-over-year stability of the
decomposed rates vs a single fused box rate, and probe one interaction (opponent
season 3PA rate vs DRB secure rate). Run build_events.py first.

Everything here stays inside the 2021-2024 exploration partition because events.pkl
was built exclusively from partition-filtered possessions.parquet rows.
"""
import pandas as pd
import numpy as np
import os, pickle
from collections import defaultdict

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
HERE = os.path.dirname(__file__)
PARTITION_SEASONS = ['2021', '2022', '2023', '2024']

with open(os.path.join(HERE, "events.pkl"), "rb") as f:
    events = pickle.load(f)

poss = pd.read_parquet(os.path.join(ROOT, "data", "possessions", "possessions.parquet"), columns=['game_id', 'season'])
poss['game_id'] = poss['game_id'].astype(str)
poss['season'] = poss['season'].astype(str)
game_season = poss.drop_duplicates('game_id').set_index('game_id')['season'].to_dict()

mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"))
mp['season'] = mp['season'].astype(str)
mp = mp[mp['season'].isin(PARTITION_SEASONS)].copy()
mp['game_id'] = mp['game_id'].astype(str)
player_names = mp.drop_duplicates('player_id').set_index('player_id')['player_name'].to_dict()

counters = defaultdict(lambda: [0, 0, 0, 0])  # [orb_opp, orb_sec, drb_opp, drb_sec]
interaction_rows = []
for e in events:
    season = game_season.get(e['game_id'])
    if season not in PARTITION_SEASONS:
        continue
    for p in e['off_players']:
        if pd.isna(p) or p == 0:
            continue
        counters[(p, season)][0] += 1
        if e['is_off'] and p == e['rebounder']:
            counters[(p, season)][1] += 1
    for p in e['def_players']:
        if pd.isna(p) or p == 0:
            continue
        counters[(p, season)][2] += 1
        if (not e['is_off']) and p == e['rebounder']:
            counters[(p, season)][3] += 1
    interaction_rows.append({'game_id': e['game_id'], 'season': season, 'def_players': e['def_players'],
                              'off_players': e['off_players'], 'rebounder': e['rebounder'], 'is_off': e['is_off']})

rows = [{'player_id': p, 'season': s, 'player_name': player_names.get(p, f"id{p}"),
         'orb_opp': c[0], 'orb_sec': c[1], 'drb_opp': c[2], 'drb_sec': c[3],
         'reb_opp': c[0] + c[2], 'reb_sec': c[1] + c[3]} for (p, s), c in counters.items()]
ps = pd.DataFrame(rows)
ps['orb_rate'] = ps['orb_sec'] / ps['orb_opp'].replace(0, np.nan)
ps['drb_rate'] = ps['drb_sec'] / ps['drb_opp'].replace(0, np.nan)

mp_season = mp.groupby(['player_id', 'season']).agg(minutes=('minutes', 'sum'), reb=('reb', 'sum'),
                                                      games=('game_id', 'nunique')).reset_index()
mp_season['season'] = mp_season['season'].astype(str)
ps = ps.merge(mp_season, on=['player_id', 'season'], how='left')
ps['reb_per_min'] = ps['reb'] / ps['minutes'].replace(0, np.nan)
ps.to_csv(os.path.join(HERE, "player_season.csv"), index=False)

# --- stability: consecutive-season correlations, minutes>=300 both seasons ---
MIN_MIN = 300
vol = ps[ps['minutes'] >= MIN_MIN].copy()
vol['drb_opp_pm'] = vol['drb_opp'] / vol['minutes']
vol['orb_opp_pm'] = vol['orb_opp'] / vol['minutes']
season_order = {s: i for i, s in enumerate(PARTITION_SEASONS)}
vol['season_idx'] = vol['season'].map(season_order)

pairs = []
for pid, grp in vol.groupby('player_id'):
    grp = grp.sort_values('season_idx')
    for i in range(len(grp) - 1):
        a, b = grp.iloc[i], grp.iloc[i + 1]
        if b['season_idx'] - a['season_idx'] != 1:
            continue
        pairs.append(dict(player_id=pid, naive1=a['reb_per_min'], naive2=b['reb_per_min'],
                           drb_sec1=a['drb_rate'], drb_sec2=b['drb_rate'],
                           orb_sec1=a['orb_rate'], orb_sec2=b['orb_rate'],
                           drb_opp_pm1=a['drb_opp_pm'], drb_opp_pm2=b['drb_opp_pm'],
                           orb_opp_pm1=a['orb_opp_pm'], orb_opp_pm2=b['orb_opp_pm']))
pdf = pd.DataFrame(pairs)

def corr(a, b):
    m = a.notna() & b.notna()
    return (np.corrcoef(a[m], b[m])[0, 1], m.sum()) if m.sum() >= 5 else (np.nan, m.sum())

print("consecutive-season pairs:", len(pdf))
for label, (a, b) in {
    'naive REB/min': (pdf['naive1'], pdf['naive2']),
    'DRB opportunity/min': (pdf['drb_opp_pm1'], pdf['drb_opp_pm2']),
    'DRB secure rate': (pdf['drb_sec1'], pdf['drb_sec2']),
    'ORB opportunity/min': (pdf['orb_opp_pm1'], pdf['orb_opp_pm2']),
    'ORB secure rate': (pdf['orb_sec1'], pdf['orb_sec2']),
}.items():
    r, n = corr(a, b)
    print(f"{label:24s} r={r:.3f} n={n}")

# --- interaction probe: opponent season FG3A rate vs DRB secure rate, player-demeaned ---
team_season = mp.groupby(['team_id', 'season']).agg(fga=('fga', 'sum'), fg3a=('fg3a', 'sum')).reset_index()
team_season['fg3a_rate'] = team_season['fg3a'] / team_season['fga']
team_season['high3'] = team_season['fg3a_rate'] > team_season.groupby('season')['fg3a_rate'].transform('median')
prof_map = team_season.set_index(['team_id', 'season'])['high3'].to_dict()

player_team_season = mp.drop_duplicates(['player_id', 'season']).set_index(['player_id', 'season'])['team_id'].to_dict()

int_rows = []
for e in interaction_rows:
    teams = [player_team_season.get((p, e['season'])) for p in e['off_players'] if p != 0]
    teams = [t for t in teams if t is not None]
    if not teams:
        continue
    off_team = max(set(teams), key=teams.count)
    key = (off_team, e['season'])
    if key not in prof_map:
        continue
    high3 = prof_map[key]
    for p in e['def_players']:
        if p == 0 or pd.isna(p):
            continue
        int_rows.append({'player_id': p, 'season': e['season'], 'high3_opp': high3,
                          'secured': (not e['is_off']) and (p == e['rebounder'])})

idf = pd.DataFrame(int_rows)
own_avg = idf.groupby(['player_id', 'season'])['secured'].mean().rename('own_avg')
idf = idf.join(own_avg, on=['player_id', 'season'])
idf['resid'] = idf['secured'].astype(float) - idf['own_avg']

print("\nDRB secure rate by opponent 3PT-rate bucket (pooled):")
print(idf.groupby('high3_opp')['secured'].mean())
print("\nplayer-demeaned residual (net of that player-season's own average):")
print(idf.groupby('high3_opp')['resid'].mean())
print(idf.groupby('high3_opp')['resid'].size())
