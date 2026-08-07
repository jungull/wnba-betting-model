"""
E0 I0003 scratch script 1/3 -- build rebound opportunity/secure events.

Partition guard: filters possessions.parquet to season in {2021,2022,2023,2024}
BEFORE deriving anything (EXPLORATION_PARTITION/1). Never touches 2025/2026.

For every individually-credited REBOUND event in play-by-play (EVENTMSGTYPE==4,
PERSON1TYPE in {4,5}, i.e. not a team rebound), matches it to the possessions.parquet
row whose [start_sec,end_sec] window is nearest the event's elapsed-in-period time,
and pulls that row's off_p1..5 / def_p1..5 as the 10 on-court players -- the
"opportunity" set. Whether the event was Off/Def and who grabbed it comes straight
out of the pbp description regex "REBOUND (Off:X Def:Y)".

KNOWN LIMITATION (see NOTES.md): row-matching by clock-time is noisy. Diagnostic
against the rebounder's actual side found ~99.4% of rebounders somewhere among the
10 on-court players, but only ~72% on the CORRECT side (84% for defensive boards,
43% for offensive boards) -- clock-string vs possession-builder second boundaries
disagree by a second or two often enough to occasionally pick the neighboring row.
Treat DRB numbers here as materially more trustworthy than ORB numbers.
"""
import pandas as pd
import numpy as np
import os, re, time, pickle

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
PARTITION_SEASONS = {'2021', '2022', '2023', '2024'}  # EXPLORATION_PARTITION/1 -- hard boundary

t0 = time.time()

poss = pd.read_parquet(os.path.join(ROOT, "data", "possessions", "possessions.parquet"))
poss['season'] = poss['season'].astype(str)
poss = poss[poss['season'].isin(PARTITION_SEASONS)].copy()
poss['game_id'] = poss['game_id'].astype(str)
print("possession rows in partition:", len(poss), "unique games:", poss['game_id'].nunique())

period_len = poss.groupby(['game_id', 'period'])['end_sec'].max().rename('period_len')
game_ids = set(poss['game_id'].unique())

poss_sorted = poss.sort_values(['game_id', 'period', 'start_sec'])
poss_by_game_period = {}
for (gid, per), grp in poss_sorted.groupby(['game_id', 'period']):
    poss_by_game_period[(gid, per)] = grp[['start_sec', 'end_sec', 'off_p1', 'off_p2', 'off_p3', 'off_p4', 'off_p5',
                                            'def_p1', 'def_p2', 'def_p3', 'def_p4', 'def_p5']].reset_index(drop=True)

pbp_dir = os.path.join(ROOT, "data", "playbyplay")
reb_pat = re.compile(r"REBOUND \(Off:(\d+) Def:(\d+)\)")

def parse_pctime(s):
    if pd.isna(s):
        return np.nan
    try:
        m, sec = s.split(':')
        return int(m) * 60 + int(sec)
    except Exception:
        return np.nan

event_records = []
n_games_processed = 0
n_events_total = 0
missing_lineup = 0

for gid in game_ids:
    fpath = os.path.join(pbp_dir, f"pbp_{gid}.parquet")
    if not os.path.exists(fpath):
        continue
    df = pd.read_parquet(fpath, columns=['GAME_ID', 'EVENTMSGTYPE', 'PERIOD', 'PCTIMESTRING',
                                          'HOMEDESCRIPTION', 'VISITORDESCRIPTION',
                                          'PLAYER1_ID', 'PLAYER1_TEAM_ID', 'PERSON1TYPE'])
    reb = df[df['EVENTMSGTYPE'] == 4].copy()
    if reb.empty:
        n_games_processed += 1
        continue
    desc = reb['HOMEDESCRIPTION'].fillna('') + reb['VISITORDESCRIPTION'].fillna('')
    parsed = desc.str.extract(reb_pat)
    reb['off_flag'] = pd.to_numeric(parsed[0], errors='coerce')
    reb['def_flag'] = pd.to_numeric(parsed[1], errors='coerce')
    reb = reb.dropna(subset=['off_flag', 'def_flag'])
    reb = reb[(reb['PLAYER1_ID'] > 0) & (reb['PERSON1TYPE'].isin([4, 5]))]
    if reb.empty:
        n_games_processed += 1
        continue
    reb['remaining_sec'] = reb['PCTIMESTRING'].apply(parse_pctime)

    for _, r in reb.iterrows():
        per = int(r['PERIOD'])
        plen = period_len.get((gid, per), np.nan)
        if pd.isna(plen) or pd.isna(r['remaining_sec']):
            missing_lineup += 1
            continue
        elapsed = plen - r['remaining_sec']
        key = (gid, per)
        if key not in poss_by_game_period:
            missing_lineup += 1
            continue
        block = poss_by_game_period[key]
        s = block['start_sec'].to_numpy()
        e = block['end_sec'].to_numpy()
        dist = np.where(elapsed < s, s - elapsed, np.where(elapsed > e, elapsed - e, 0.0))
        idx = int(np.argmin(dist))
        cand_row = block.iloc[idx]

        off_players = [cand_row['off_p1'], cand_row['off_p2'], cand_row['off_p3'], cand_row['off_p4'], cand_row['off_p5']]
        def_players = [cand_row['def_p1'], cand_row['def_p2'], cand_row['def_p3'], cand_row['def_p4'], cand_row['def_p5']]

        event_records.append({
            'game_id': gid, 'period': per, 'elapsed': elapsed,
            'off_players': tuple(off_players), 'def_players': tuple(def_players),
            'rebounder': r['PLAYER1_ID'], 'is_off': r['off_flag'] == 1,
        })
        n_events_total += 1

    n_games_processed += 1
    if n_games_processed % 150 == 0:
        print("games processed:", n_games_processed, "events:", n_events_total, "elapsed:", time.time() - t0)

print("DONE. games_processed:", n_games_processed, "events:", n_events_total,
      "missing_lineup:", missing_lineup, "elapsed:", time.time() - t0)

with open(os.path.join(os.path.dirname(__file__), "events.pkl"), "wb") as f:
    pickle.dump(event_records, f)
print("saved", len(event_records), "event records")
