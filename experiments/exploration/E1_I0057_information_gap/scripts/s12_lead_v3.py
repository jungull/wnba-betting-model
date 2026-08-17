import pandas as pd, numpy as np, unicodedata, re
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
od=pd.read_csv(MAIN+'odds_capture/capture_log.csv',usecols=['commence_time','home_team','away_team']).drop_duplicates()
od['tip']=pd.to_datetime(od['commence_time'],utc=True)
long=pd.concat([od[['tip','home_team']].rename(columns={'home_team':'team'}),
                od[['tip','away_team']].rename(columns={'away_team':'team'})])
long['gd']=(long.tip-pd.Timedelta(hours=6)).dt.date
tt=long.groupby(['team','gd'])['tip'].min().reset_index()
def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z]','',s.lower())
inj=pd.read_csv(MAIN+'injury_capture/injury_log.csv')
inj['cap']=pd.to_datetime(inj['capture_utc'],format='%Y%m%dT%H%M%SZ',utc=True)
inj=inj[inj.game_date.astype(str).str.len()>0].copy()
inj['gd']=pd.to_datetime(inj['game_date']).dt.date
inj['pn']=inj.player.map(norm)
inj=inj.merge(tt,on=['team','gd'],how='left').dropna(subset=['tip'])
pre=inj[inj.cap<inj.tip].copy()
print('captures strictly before tip: %d of %d rows (%.1f%%)'%(len(pre),len(inj),100*len(pre)/len(inj)))
g=pre.sort_values('cap').groupby(['pn','gd'])
rec=pd.DataFrame({'first':g['cap'].min(),'last':g['cap'].max(),
                  'first_status':g['status'].first(),'last_status':g['status'].last(),
                  'n':g.size(),'tip':g['tip'].first()}).reset_index()
rec['lead_first_h']=(rec.tip-rec['first']).dt.total_seconds()/3600
rec['lead_last_h']=(rec.tip-rec['last']).dt.total_seconds()/3600
rec['changed']=rec.first_status!=rec.last_status
print('PRE-TIP player-gamedate series n=%d over %d game days'%(len(rec),rec.gd.nunique()))
for c,lab in [('lead_first_h','FIRST pre-tip appearance'),('lead_last_h','LAST pre-tip designation (what a bettor holds at tip)')]:
    v=rec[c]
    print('\n%s -- hours before tip:'%lab)
    print('   min %.2f  p10 %.2f  median %.2f  p90 %.2f  max %.2f'%(v.min(),v.quantile(.1),v.median(),v.quantile(.9),v.max()))
    print('   share inside T-24h %.1f%% | T-12h %.1f%% | T-6h %.1f%% | T-3h %.1f%% | T-1h %.1f%%'%(
      100*(v<24).mean(),100*(v<12).mean(),100*(v<6).mean(),100*(v<3).mean(),100*(v<1).mean()))
print('\nPRE-TIP designation changes: %d of %d series (%.1f%%)'%(rec.changed.sum(),len(rec),100*rec.changed.mean()))
ch=rec[rec.changed]
print((ch.first_status+' -> '+ch.last_status).value_counts().to_string())
v=ch.lead_last_h
print('\nwhen the resolving designation lands, hours before tip: median %.2f p10 %.2f p90 %.2f'%(v.median(),v.quantile(.1),v.quantile(.9)))
print('   share inside T-24h %.1f%% | T-12h %.1f%% | T-6h %.1f%% | T-3h %.1f%%'%(
  100*(v<24).mean(),100*(v<12).mean(),100*(v<6).mean(),100*(v<3).mean()))
print('\nFINAL PRE-TIP STATUS distribution:'); print(rec.last_status.value_counts().to_string())
rec.to_csv('../designation_series_pretip.csv',index=False)
