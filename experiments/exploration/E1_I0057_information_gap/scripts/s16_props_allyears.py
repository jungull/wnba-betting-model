import pandas as pd, unicodedata, re, json
MAIN=r"C:/Users/jgallagher/wnba-betting-model/data/"
def norm(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode(); return re.sub(r'[^a-z]','',s.lower())
h=pd.read_csv(MAIN+'props_capture/historical/master_props_historical.csv',low_memory=False)
h['ct']=pd.to_datetime(h.commence_time,utc=True); h['yr']=h.ct.dt.year
h['sr']=pd.to_datetime(h.snapshot_returned_utc,utc=True,errors='coerce')
h['gid']=h.game_id.astype(str).str.replace(r'\.0$','',regex=True); h['pn']=h.player_name.map(norm)
Q=pd.read_parquet(MAIN+'masters/master_player.parquet',columns=['game_id','season','game_date','player_name','minutes','pts'])
Q['gid']=Q.game_id.astype(str); Q['pn']=Q.player_name.map(norm)
res={}
for y in [2024,2025,2026]:
    hy=h[h.yr==y]; Qy=Q[Q.season==y]
    last=hy.sort_values('sr').groupby(['gid','pn']).tail(1)[['gid','pn','line']]
    J=Qy.merge(last,on=['gid','pn'],how='inner'); J=J[J.minutes.fillna(0)>0]
    gcov=len(set(hy.gid)&set(Qy.gid))
    res[y]=dict(master_rows=len(Qy),games=Qy.gid.nunique(),games_with_props=gcov,
                joined_played_rows=len(J),players=int(hy.pn.nunique()),
                pct_rows=round(100*len(J)/len(Qy),1),
                corr=round(float(J.line.corr(J.pts.astype(float))),4),
                mae=round(float((J.line-J.pts.astype(float)).abs().mean()),3))
    print(y,res[y])
json.dump(res,open('../props_join_by_season.json','w'),indent=1)
