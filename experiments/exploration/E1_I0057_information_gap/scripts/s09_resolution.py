import pandas as pd, numpy as np, unicodedata, re
from datetime import timedelta
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z]','',s.lower())
inj=pd.read_csv(MAIN+'injury_capture/injury_log.csv')
inj['cap']=pd.to_datetime(inj['capture_utc'],format='%Y%m%dT%H%M%SZ',utc=True)
inj=inj[inj.game_date.astype(str).str.len()>0].copy()
inj['gd']=pd.to_datetime(inj['game_date']).dt.date
inj['pn']=inj.player.map(norm)
Q=pd.read_parquet(MAIN+'masters/master_player.parquet',columns=['game_date','player_name','minutes','dnp_reason'])
Q['game_date']=pd.to_datetime(Q['game_date']).dt.date
Q['pn']=Q.player_name.map(norm)
W=Q[Q.game_date>=pd.Timestamp('2026-07-30').date()].copy()
W['played']=W.minutes.fillna(0)>0
last=inj.sort_values('cap').groupby(['pn','gd']).tail(1)[['pn','gd','status']]
J=W.merge(last,left_on=['pn','game_date'],right_on=['pn','gd'],how='left')
und=J[(~J.played)&(J.status.isna())]
print('UNDESIGNATED DNP rows: %d'%len(und))
print('their dnp_reason:'); print(und.dnp_reason.value_counts(dropna=False).to_string())
print()
des=J[(~J.played)&(J.status.notna())]
print('DESIGNATED-Out DNP rows: %d ; their dnp_reason:'%len(des))
print(des.dnp_reason.value_counts(dropna=False).to_string())

print('\n=== RESOLUTION TIMING: how a designation evolves within a game-day ===')
# per (player, game_date): sequence of statuses over captures
seq=inj.sort_values('cap').groupby(['pn','gd'])['status'].agg(list)
n_change=sum(1 for v in seq if len(set(v))>1)
print('player-gamedate designation series: %d ; %d (%.1f%%) change status at least once before the last capture'%(len(seq),n_change,100*n_change/len(seq)))
from collections import Counter
paths=Counter('->'.join(dict.fromkeys(v)) for v in seq)
print('top designation paths within a game-day:'); 
for k,v in paths.most_common(12): print('   %-40s %d'%(k,v))
# first appearance lead time relative to game date 19:00 ET (23:00 UTC) proxy
inj['first_seen']=inj.groupby(['pn','gd'])['cap'].transform('min')
f=inj.drop_duplicates(['pn','gd'])
tip=pd.to_datetime(f.gd.astype(str))+pd.Timedelta(hours=23)  # 19:00 ET proxy
lead=(tip.dt.tz_localize('UTC')-f.first_seen).dt.total_seconds()/3600
print('\nFIRST time a player appears on the report for a given game date, hours before a 19:00 ET tip proxy:')
print('  n=%d  min %.1f  p10 %.1f  median %.1f  p90 %.1f  max %.1f'%(len(lead),lead.min(),lead.quantile(.1),lead.median(),lead.quantile(.9),lead.max()))
print('  share first seen <6h before tip: %.1f%%   <2h: %.1f%%'%(100*(lead<6).mean(),100*(lead<2).mean()))
