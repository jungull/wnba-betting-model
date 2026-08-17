import pandas as pd
R=r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/"
P=pd.read_parquet(R+'data/masters/master_player.parquet',
   columns=['game_id','season','season_type','game_date','player_id','minutes','dnp_reason','era','in_gamelog','in_misc','in_advanced'])
for label,sub in [('ALL rows',P),
                  ('played rows (minutes>0)',P[P.minutes.fillna(0)>0]),
                  ('regular season only',P[P.season_type.astype(str).str.lower().str.contains('reg')]),
                  ('regular+played',P[(P.season_type.astype(str).str.lower().str.contains('reg'))&(P.minutes.fillna(0)>0)])]:
    e=sub[sub.season<=2024]; c=sub[sub.season>=2025]
    print(f'--- {label}: expl n={len(e)} old%={100*(e.era=="gamelog_old").mean():.2f}  conf n={len(c)} old_rows={int((c.era=="gamelog_old").sum())} new%={100*(c.era=="gamelog_new").mean():.2f}')
print()
print('season_type values:',P.season_type.value_counts().to_dict())
print()
# which columns are null in which era -> the actual measurement difference
cols=['points_off_turnovers','points_paint','fouls_drawn','blocks_against','estimated_pace','pie','possessions','usage_percentage','true_shooting_percentage','plus_minus']
Q=pd.read_parquet(R+'data/masters/master_player.parquet')
print('NULL RATE BY ERA (the measurement-regime difference):')
print(Q.groupby('era')[[c for c in cols if c in Q.columns]].apply(lambda d: d.isna().mean().round(3)))
print()
print('mean by era (scale shift check):')
print(Q.groupby('era')[['minutes','pts','possessions','estimated_pace','fouls_drawn']].mean().round(3))
