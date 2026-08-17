import pandas as pd, numpy as np
R=r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/"
Q=pd.read_parquet(R+'data/masters/master_player.parquet')
Q['played']=Q.minutes.fillna(0)>0
print('=== minutes granularity by era (played rows) ===')
p=Q[Q.played]
p=p.assign(frac=(p.minutes*60).round(3)%60)
for e,g in p.groupby('era'):
    isint=(np.isclose(g.minutes%1,0))
    print(f'  {e:12s} n={len(g):6d}  share minutes exactly integer = {100*isint.mean():6.2f}%   n distinct minute values={g.minutes.nunique()}')
print('\nby season (played rows):')
for s,g in p.groupby('season'):
    print(f'  {s}  n={len(g):5d}  integer-minutes share {100*np.isclose(g.minutes%1,0).mean():6.2f}%  distinct {g.minutes.nunique():5d}  minutes_source {dict(g.minutes_source.value_counts())}')

print('\n=== starter_flag / dnp_reason coverage by season ===')
for s,g in Q.groupby('season'):
    sf=g.starter_flag
    print(f'  {s}  rows={len(g):5d}  starter_flag notnull={100*sf.notna().mean():6.2f}%  ==1 share={100*(sf==1).mean():6.2f}%  dnp_reason notnull={100*g.dnp_reason.notna().mean():6.2f}%  position nonblank={100*(g.position.fillna("").str.len()>0).mean():6.2f}%')

print('\n=== DNP rows (minutes null or 0) by season ===')
for s,g in Q.groupby('season'):
    d=g[~(g.minutes.fillna(0)>0)]
    print(f'  {s}  dnp/inactive rows={len(d):5d} ({100*len(d)/len(g):5.2f}%)  dnp_reason populated on them={100*d.dnp_reason.notna().mean():6.2f}%')
