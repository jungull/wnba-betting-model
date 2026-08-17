import pandas as pd, os, json, glob
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
fs=sorted(glob.glob(MAIN+'odds_capture/historical/hist_*.json'))
print('historical odds files:',len(fs),'first',os.path.basename(fs[0]),'last',os.path.basename(fs[-1]))
import re, collections
dates=sorted(set(re.search(r'hist_(\d{4}-\d{2}-\d{2})',os.path.basename(f)).group(1) for f in fs))
print('date span',dates[0],'->',dates[-1],'n distinct dates',len(dates))
print('by year:',collections.Counter(d[:4] for d in dates))
j=json.load(open(fs[len(fs)//2],encoding='utf-8'))
print('mid-file type',type(j).__name__, (list(j.keys()) if isinstance(j,dict) else len(j)))
if isinstance(j,dict) and 'data' in j: 
    d=j['data']; print(' n events',len(d)); print(' event keys',sorted(d[0].keys()) if d else None)
    if d and d[0].get('bookmakers'): print(' books',[b['key'] for b in d[0]['bookmakers']][:8]); print(' markets',[m['key'] for m in d[0]['bookmakers'][0]['markets']])
print()
p=MAIN+'props_capture/historical/master_props_historical.csv'
if os.path.exists(p):
    h=pd.read_csv(p,low_memory=False)
    print('master_props_historical rows',len(h),'cols',list(h.columns))
    for c in ['commence_time','snapshot_utc','game_date']:
        if c in h.columns: print('  %s span %s -> %s'%(c,h[c].astype(str).min(),h[c].astype(str).max()))
    if 'market_key' in h: print('  markets',h.market_key.value_counts().to_dict())
    if 'commence_time' in h:
        h['yr']=h.commence_time.astype(str).str[:4]; print('  rows by year',h.yr.value_counts().to_dict())
print()
# drive_masters/master_odds span
mo=pd.read_csv(MAIN+'drive_masters/master_odds.csv',low_memory=False)
print('master_odds cols',list(mo.columns)[:20])
for c in mo.columns:
    if 'date' in c.lower() or 'time' in c.lower():
        print('  %s span %s -> %s'%(c,mo[c].astype(str).min(),mo[c].astype(str).max()))
