import pandas as pd, os, json, glob
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
def rep(name,path,tscols,extra=None):
    p=MAIN+path
    if not os.path.exists(p): print('%-28s ABSENT %s'%(name,p)); return
    try:
        df=pd.read_csv(p,low_memory=False)
    except Exception as e:
        print('%-28s ERR %s'%(name,e)); return
    sz=os.path.getsize(p)/1e6
    mt=pd.Timestamp(os.path.getmtime(p),unit='s')
    line='%-28s rows=%-8d cols=%-3d %6.1fMB mtime=%s'%(name,len(df),df.shape[1],sz,mt.strftime('%Y-%m-%d %H:%M'))
    for c in tscols:
        if c in df.columns:
            s=df[c].astype(str)
            line+=' | %s %s -> %s'%(c,s.min(),s.max())
            break
    print(line)
    if extra:
        for c in extra:
            if c in df.columns: print('      %s: %s'%(c,dict(list(df[c].value_counts().head(6).items()))))
rep('odds_capture/capture_log','odds_capture/capture_log.csv',['snapshot_utc'],['market','bookmaker'])
rep('injury_capture/injury_log','injury_capture/injury_log.csv',['capture_utc'],['status'])
rep('injury_official_live/snaps','injury_official_live/injury_snapshots.csv',['retrieval_ts_utc'],['status'])
rep('injury_official_live/trans','injury_official_live/status_transitions.csv',['t_upper_utc_bound'])
rep('market_snapshots/snapshots','market_snapshots/snapshots.csv',['retrieval_ts'],['market','book'])
rep('props_capture/master_props','props_capture/master_props.csv',['snapshot_utc'],['market_key','bookmaker_key'])
rep('news_capture/news_items','news_capture/news_items.csv',['capture_utc'],['source'])
rep('ref_assignments','ref_assignments/assignments_log.csv',['capture_utc'],['crew_role'])
rep('injury_history','injury_history/injury_history.csv',['date'],['category'])
rep('drive_masters/master_odds','drive_masters/master_odds.csv',[],[])
print()
for d in ['props_capture/historical','odds_capture/historical','market_snapshots/historical']:
    p=MAIN+d
    if os.path.isdir(p):
        fs=os.listdir(p); print('%-32s %d files: %s'%(d,len(fs),fs[:6]))
    else: print('%-32s ABSENT'%d)
print()
# sxbet jsonl
for f in ['best_line.jsonl','markets.jsonl','orderbook.jsonl','trades.jsonl','roster_events.jsonl']:
    p=MAIN+'sxbet_capture/'+f
    if not os.path.exists(p): continue
    n=0; first=None; last=None
    with open(p,encoding='utf-8',errors='replace') as fh:
        for line in fh:
            n+=1
            if first is None: first=line[:400]
            last=line
    print('sxbet/%-20s lines=%-9d %6.1fMB'%(f,n,os.path.getsize(p)/1e6))
    if f in ('markets.jsonl','trades.jsonl','best_line.jsonl'):
        try: print('     keys:',sorted(json.loads(first).keys()))
        except Exception as e: print('     first line unparsed',e)
