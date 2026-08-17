import pandas as pd, numpy as np, unicodedata, re
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
od=pd.read_csv(MAIN+'odds_capture/capture_log.csv',usecols=['commence_time','home_team','away_team'])
od=od.drop_duplicates()
od['tip']=pd.to_datetime(od['commence_time'],utc=True)
long=pd.concat([od[['tip','home_team']].rename(columns={'home_team':'team'}),
                od[['tip','away_team']].rename(columns={'away_team':'team'})])
long['gd']=(long.tip-pd.Timedelta(hours=6)).dt.date   # ET game date
tt=long.groupby(['team','gd'])['tip'].min().reset_index()
print('team-gamedate tip table:',len(tt),'| date span',tt.gd.min(),'->',tt.gd.max())

def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z]','',s.lower())
inj=pd.read_csv(MAIN+'injury_capture/injury_log.csv')
inj['cap']=pd.to_datetime(inj['capture_utc'],format='%Y%m%dT%H%M%SZ',utc=True)
inj=inj[inj.game_date.astype(str).str.len()>0].copy()
inj['gd']=pd.to_datetime(inj['game_date']).dt.date
inj['pn']=inj.player.map(norm)
inj=inj.merge(tt,on=['team','gd'],how='left')
print('injury rows matched to a real tip: %d of %d (%.1f%%)'%(inj.tip.notna().sum(),len(inj),100*inj.tip.notna().mean()))
inj=inj.dropna(subset=['tip'])
g=inj.sort_values('cap').groupby(['pn','gd'])
rec=pd.DataFrame({'first':g['cap'].min(),'last':g['cap'].max(),
                  'first_status':g['status'].first(),'last_status':g['status'].last(),
                  'n':g.size(),'tip':g['tip'].first()}).reset_index()
rec['lead_first_h']=(rec.tip-rec['first']).dt.total_seconds()/3600
rec['lead_last_h']=(rec.tip-rec['last']).dt.total_seconds()/3600
rec['changed']=rec.first_status!=rec.last_status
print('\nplayer-gamedate designation series n=%d over %d game days'%(len(rec),rec.gd.nunique()))
for c,lab in [('lead_first_h','FIRST appearance on the official report'),('lead_last_h','LAST captured designation before/at tip')]:
    v=rec[c]
    print('\n%s -- hours before that team\'s actual tip:'%lab)
    print('   min %.1f  p10 %.1f  median %.1f  p90 %.1f  max %.1f'%(v.min(),v.quantile(.1),v.median(),v.quantile(.9),v.max()))
    print('   share landing inside T-24h: %.1f%%   T-12h: %.1f%%   T-6h: %.1f%%   T-3h: %.1f%%'%(
      100*(v<24).mean(),100*(v<12).mean(),100*(v<6).mean(),100*(v<3).mean()))
print('\nseries that CHANGE designation: %d of %d (%.1f%%)'%(rec.changed.sum(),len(rec),100*rec.changed.mean()))
ch=rec[rec.changed]
if len(ch):
    print((ch.first_status+' -> '+ch.last_status).value_counts().to_string())
    v=ch.lead_last_h
    print('\nwhen the CHANGE lands (hours before tip): median %.1f  p10 %.1f  p90 %.1f'%(v.median(),v.quantile(.1),v.quantile(.9)))
    print('   share of resolutions landing inside T-24h: %.1f%%  T-12h: %.1f%%  T-6h: %.1f%%  T-3h: %.1f%%'%(
      100*(v<24).mean(),100*(v<12).mean(),100*(v<6).mean(),100*(v<3).mean()))
