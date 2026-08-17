import pandas as pd, numpy as np, unicodedata, re
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
R=r"C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program/"
tt=pd.read_csv(R+'data/reference/tip_times.csv')
tt['tip']=pd.to_datetime(tt['tip_utc'],utc=True)
tt['gd']=pd.to_datetime(tt['game_date']).dt.date
day_tip=tt.groupby('gd')['tip'].agg(['min','max','count'])
print('REAL tip times, 2026 slate days in the capture window:')
print(day_tip[(day_tip.index>=pd.Timestamp('2026-07-30').date())].to_string())
first_tip=tt.groupby('gd')['tip'].min()

def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode()
    return re.sub(r'[^a-z]','',s.lower())
inj=pd.read_csv(MAIN+'injury_capture/injury_log.csv')
inj['cap']=pd.to_datetime(inj['capture_utc'],format='%Y%m%dT%H%M%SZ',utc=True)
inj=inj[inj.game_date.astype(str).str.len()>0].copy()
inj['gd']=pd.to_datetime(inj['game_date']).dt.date
inj['pn']=inj.player.map(norm)
inj['tip']=inj.gd.map(first_tip)
inj=inj.dropna(subset=['tip'])
print('\nrows with a real tip time:',len(inj),'over',inj.gd.nunique(),'game days')
g=inj.sort_values('cap').groupby(['pn','gd'])
rec=pd.DataFrame({'first':g['cap'].min(),'last':g['cap'].max(),
                  'first_status':g['status'].first(),'last_status':g['status'].last(),
                  'n':g.size(),'tip':g['tip'].first()}).reset_index()
rec['lead_first_h']=(rec.tip-rec['first']).dt.total_seconds()/3600
rec['lead_last_h']=(rec.tip-rec['last']).dt.total_seconds()/3600
rec['changed']=rec.first_status!=rec.last_status
print('\nplayer-gamedate series n=%d'%len(rec))
for c,lab in [('lead_first_h','FIRST appearance on the report'),('lead_last_h','LAST captured designation')]:
    v=rec[c]
    print('%s, hours before the first tip of that day:'%lab)
    print('   min %.1f  p10 %.1f  median %.1f  p90 %.1f  max %.1f | share <24h %.1f%%  <12h %.1f%%  <6h %.1f%%  <3h %.1f%%'%(
      v.min(),v.quantile(.1),v.median(),v.quantile(.9),v.max(),100*(v<24).mean(),100*(v<12).mean(),100*(v<6).mean(),100*(v<3).mean()))
print('\nseries that CHANGE designation: %d (%.1f%%)'%(rec.changed.sum(),100*rec.changed.mean()))
ch=rec[rec.changed]
print('their FIRST-status->LAST-status:'); print((ch.first_status+' -> '+ch.last_status).value_counts().to_string())
print('\nlead time of the LAST designation for the series that changed:')
v=ch.lead_last_h
print('   median %.1f h  p10 %.1f  p90 %.1f  | share resolving <12h before tip %.1f%%  <6h %.1f%%'%(
  v.median(),v.quantile(.1),v.quantile(.9),100*(v<12).mean(),100*(v<6).mean()))
