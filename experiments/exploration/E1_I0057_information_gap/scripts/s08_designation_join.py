import pandas as pd, numpy as np, unicodedata, re
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
inj=pd.read_csv(MAIN+'injury_capture/injury_log.csv')
print('MAIN injury_log rows',len(inj))
inj['cap']=pd.to_datetime(inj['capture_utc'],format='%Y%m%dT%H%M%SZ',utc=True)
print('capture span',inj.cap.min(),'->',inj.cap.max(),' n captures',inj.capture_utc.nunique())
print('report_date span',inj.report_date.min(),'->',inj.report_date.max())
print('status',inj.status.value_counts().to_dict())
print('source',inj.source.value_counts().to_dict())
# cadence
c=inj.drop_duplicates('capture_utc').sort_values('cap')
gaps=c.cap.diff().dt.total_seconds().div(60).dropna()
print('capture cadence minutes: median %.0f  p10 %.0f  p90 %.0f  max %.0f'%(gaps.median(),gaps.quantile(.1),gaps.quantile(.9),gaps.max()))
print('captures per calendar day:'); print(c.groupby(c.cap.dt.date).size().to_string())

# join to outcomes
def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z]','',s.lower())
Q=pd.read_parquet(MAIN+'masters/master_player.parquet',columns=['game_id','season','game_date','team_abbreviation','player_name','minutes','dnp_reason'])
Q['game_date']=pd.to_datetime(Q['game_date']).dt.date
lo=pd.to_datetime(inj.game_date.replace('',np.nan).dropna()).dt.date
W=Q[(Q.game_date>=min(lo))&(Q.game_date<=Q.game_date.max())]
W=W[W.game_date>=pd.Timestamp('2026-07-30').date()]
print('\noutcome rows in the capture window (2026-07-30..%s): %d over %d game days'%(Q.game_date.max(),len(W),W.game_date.nunique()))
inj2=inj[inj.game_date.astype(str).str.len()>0].copy()
inj2['gd']=pd.to_datetime(inj2['game_date']).dt.date
inj2['pn']=inj2.player.map(norm)
W=W.copy(); W['pn']=W.player_name.map(norm)
# latest designation per (player, game_date)
last=inj2.sort_values('cap').groupby(['pn','gd']).tail(1)[['pn','gd','status','cap']]
J=W.merge(last,left_on=['pn','game_date'],right_on=['pn','gd'],how='left')
J['played']=J.minutes.fillna(0)>0
print('\njoin rate: %.1f%% of outcome rows carry a designation'%(100*J.status.notna().mean()))
print('\nCROSSTAB designation x played:')
ct=pd.crosstab(J.status.fillna('(no designation)'),J.played,dropna=False)
print(ct)
print('\nDNP rows (%d): %.1f%% had a captured designation; of those, status mix:'%(
   int((~J.played).sum()),100*J.loc[~J.played,'status'].notna().mean()))
print(J.loc[~J.played,'status'].value_counts(dropna=False).to_dict())
print('\nPLAYED rows (%d): status mix among those WITH a designation:'%int(J.played.sum()))
print(J.loc[J.played,'status'].value_counts(dropna=False).to_dict())
