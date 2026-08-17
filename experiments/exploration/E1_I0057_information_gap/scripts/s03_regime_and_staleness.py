import pandas as pd, numpy as np
R=r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/"
P=pd.read_parquet(R+'data/masters/master_player.parquet',
   columns=['game_id','season','season_type','game_date','player_id','minutes','dnp_reason','era','source','in_gamelog','observed_time'])
P['game_date']=pd.to_datetime(P['game_date'])
print('rows',len(P),'games',P.game_id.nunique())
print('\n=== Q3: era x season (ALL rows) ===')
ct=pd.crosstab(P['season'],P['era'])
print(ct)
print('\nrow shares by season:')
print((ct.div(ct.sum(1),axis=0)*100).round(2))
print('\n=== source x season ===')
print(pd.crosstab(P['season'],P['source']))
# exploration vs confirmation partition
expl=P[P.season<=2024]; conf=P[P.season>=2025]
print('\nexploration (<=2024) rows %d  era mix:'%len(expl)); print(expl['era'].value_counts())
print('confirmation (>=2025) rows %d  era mix:'%len(conf)); print(conf['era'].value_counts())
print('\nexploration gamelog_old share: %.2f%%'%(100*(expl['era']=='gamelog_old').mean()))
print('confirmation gamelog_old rows: %d'%int((conf['era']=='gamelog_old').sum()))

print('\n=== observed_time provenance ===')
print(P['observed_time'].describe())
print(P.groupby('season')['observed_time'].agg(['min','max','count']))

print('\n=== Q2: information staleness (days since player last game) ===')
pl=P[P.minutes.notna() & (P.minutes>0)].sort_values(['player_id','game_date'])
pl['prev']=pl.groupby(['player_id','season'])['game_date'].shift(1)
gap=(pl['game_date']-pl['prev']).dt.days.dropna()
print('n rows with a prior same-season game:',len(gap))
print('days since prior game: mean %.2f median %.1f p25 %.0f p75 %.0f p90 %.0f max %.0f'%(
  gap.mean(),gap.median(),gap.quantile(.25),gap.quantile(.75),gap.quantile(.9),gap.max()))
print('share >=3 days: %.1f%%   >=5 days: %.1f%%   >=7: %.1f%%'%(100*(gap>=3).mean(),100*(gap>=5).mean(),100*(gap>=7).mean()))
print('\nfirst-appearance rows in season (no prior state at all):',int(pl.groupby(['player_id','season']).head(1).shape[0]))
