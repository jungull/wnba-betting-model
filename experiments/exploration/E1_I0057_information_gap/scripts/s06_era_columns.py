import pandas as pd, numpy as np, os, glob, re
R=r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/"
Q=pd.read_parquet(R+'data/masters/master_player.parquet')
P=Q[(Q.season_type=='Regular Season')&(Q.minutes.fillna(0)>0)]
e=P[P.season<=2024]; c=P[P.season>=2025]
print('regular+played: expl n=%d (100%% gamelog_old), conf n=%d (100%% gamelog_new)'%(len(e),len(c)))
rows=[]
for col in Q.columns:
    if col in ('game_id','season','game_date','player_id','player_name','source','observed_time','era','first_name','family_name','name_i','team_abbreviation'): continue
    a=e[col].isna().mean(); b=c[col].isna().mean()
    if abs(a-b)>0.02: rows.append((col,round(100*a,2),round(100*b,2)))
print('\ncolumns whose NULL RATE differs by >2pp across the partition:')
for r in rows: print('   %-40s expl_null%%=%6.2f  conf_null%%=%6.2f'%r)
if not rows: print('   NONE')
# scale shifts
num=[c2 for c2 in Q.columns if pd.api.types.is_numeric_dtype(Q[c2]) and c2 not in ('season','player_id','team_id','opp_team_id')]
print('\nlargest standardised mean shifts across the partition (|d| = (mean_conf-mean_expl)/sd_expl):')
out=[]
for col in num:
    x=e[col].astype('float64'); y=c[col].astype('float64')
    sd=x.std()
    if not np.isfinite(sd) or sd==0: continue
    out.append((col,(y.mean()-x.mean())/sd))
for col,d in sorted(out,key=lambda t:-abs(t[1]))[:12]:
    print('   %-40s d=%+.3f'%(col,d))

print('\n=== raw pbp / possessions coverage (Q3 confirmability) ===')
pbp=glob.glob(r"C:/Users/jgallagher/wnba-betting-model/data/playbyplay/*.parquet")
print('playbyplay files:',len(pbp))
ids=set()
for f in pbp:
    m=re.search(r'(\d{10})',os.path.basename(f))
    if m: ids.add(m.group(1))
G=Q[['game_id','season']].drop_duplicates()
G['has_pbp']=G.game_id.astype(str).isin(ids)
print(G.groupby('season')['has_pbp'].agg(['sum','count']).assign(pct=lambda d:(100*d['sum']/d['count']).round(1)))
pp=r"C:/Users/jgallagher/wnba-betting-model/data/possessions/possessions.parquet"
if os.path.exists(pp):
    import pyarrow.parquet as pq
    t=pq.ParquetFile(pp)
    print('\npossessions.parquet rows',t.metadata.num_rows,'cols',len(t.schema_arrow.names))
    dfp=pd.read_parquet(pp,columns=['game_id'])
    gp=set(dfp.game_id.astype(str).unique()); print('distinct games in possessions:',len(gp))
    G['has_poss']=G.game_id.astype(str).isin(gp)
    print(G.groupby('season')['has_poss'].agg(['sum','count']).assign(pct=lambda d:(100*d['sum']/d['count']).round(1)))
else: print('possessions.parquet ABSENT at',pp)
