import pandas as pd, numpy as np
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
h=pd.read_csv(MAIN+'props_capture/historical/master_props_historical.csv',low_memory=False)
h['ct']=pd.to_datetime(h.commence_time,utc=True)
h['yr']=h.ct.dt.year
print('rows',len(h))
print('\nby year: rows / distinct api_event_id / distinct game_id / distinct players / books')
for y,g in h.groupby('yr'):
    print('  %d  rows=%-7d events=%-5d game_id=%-5d players=%-4d books=%d  span %s -> %s'%(
      y,len(g),g.api_event_id.nunique(),g.game_id.nunique(),g.player_name.nunique(),g.bookmaker_key.nunique(),
      str(g.ct.min())[:10],str(g.ct.max())[:10]))
print('\ngame_id null share: %.1f%%'%(100*h.game_id.isna().mean()))
print('game_id null by year:',h.groupby('yr').game_id.apply(lambda s:round(100*s.isna().mean(),1)).to_dict())
# snapshot timing relative to tip
h['sq']=pd.to_datetime(h.snapshot_requested_utc,utc=True,errors='coerce')
h['sr']=pd.to_datetime(h.snapshot_returned_utc,utc=True,errors='coerce')
h['lead_h']=(h.ct-h.sr).dt.total_seconds()/3600
print('\nsnapshot lead before tip (h): by year')
for y,g in h.groupby('yr'):
    v=g.lead_h.dropna()
    if len(v): print('  %d n=%d  min %.2f p10 %.2f median %.2f p90 %.2f max %.2f | n distinct snapshots per event median %.1f'%(
        y,len(v),v.min(),v.quantile(.1),v.median(),v.quantile(.9),v.max(),g.groupby('api_event_id').sr.nunique().median()))
# join to master 2024
Q=pd.read_parquet(MAIN+'masters/master_player.parquet',columns=['game_id','season','game_date','player_name','minutes','pts'])
g24=set(Q[Q.season==2024].game_id.astype(str))
h24=h[h.yr==2024].copy(); h24['gid']=h24.game_id.astype(str).str.replace(r'\.0$','',regex=True)
print('\n2024 props: distinct game_id %d ; of these present in master 2024: %d ; master 2024 games total %d'%(
  h24.gid.nunique(), len(set(h24.gid)&g24), len(g24)))
print('2024 coverage of the season: %.1f%% of games'%(100*len(set(h24.gid)&g24)/len(g24)))
import unicodedata,re
def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode(); return re.sub(r'[^a-z]','',s.lower())
Q24=Q[Q.season==2024].copy(); Q24['pn']=Q24.player_name.map(norm); Q24['gid']=Q24.game_id.astype(str)
h24['pn']=h24.player_name.map(norm)
last=h24.sort_values('sr').groupby(['gid','pn']).tail(1)[['gid','pn','line','over_price','under_price','lead_h']]
J=Q24.merge(last,on=['gid','pn'],how='inner')
print('\nJOINED 2024 player-game rows with a closing points line: %d  (of %d master 2024 rows = %.1f%%)'%(len(J),len(Q24),100*len(J)/len(Q24)))
J=J[J.minutes.fillna(0)>0]
print('played rows joined: %d'%len(J))
print('line vs realised pts:  corr %.4f  MAE %.3f  mean line %.2f mean pts %.2f'%(
  J.line.corr(J.pts.astype(float)), (J.line-J.pts.astype(float)).abs().mean(), J.line.mean(), J.pts.astype(float).mean()))
J.to_csv('../joined_2024_points_props.csv',index=False)
