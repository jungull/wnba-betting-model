import os,re,json
import numpy as np, pandas as pd
EXPL=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
cov=pd.read_csv(os.path.join(EXPL,"E1_I0038_within_entity_null_audit","CENSUS_COVERAGE.csv"))
CENSUS={"E0_I0014_residual_heterogeneity","E0_I0016_efficiency_predictors","E0_I0017_shot_quality_efficiency","E0_I0019_availability_forecast","E0_I0024_reb_ast_characterisation","E0_I0029_freethrow_hurdle","E1_I0018_teammate_volume_channel","E1_I0023_usage_defence_interaction"}
TARGETS=[s for s in sorted(cov["screen"].unique()) if s not in CENSUS]
CEIL=re.compile(r"(^|_)ceiling|ceil_|arithmetic_max|max_attainable|upper_bound",re.I)
KILL=re.compile(r"(^|_)(kill|verdict|clears|survives?|decision|reject|is_dead|disposition)",re.I)
rows=[]
for sc in TARGETS:
    for root,_dd,files in os.walk(os.path.join(EXPL,sc)):
        for fn in files:
            if not fn.lower().endswith(".csv"): continue
            fp=os.path.join(root,fn)
            try: full=pd.read_csv(fp)
            except Exception: continue
            cols=list(full.columns)
            cc=[c for c in cols if CEIL.search(c)]; ck=[c for c in cols if KILL.search(c)]
            if cc or ck:
                vals={}
                for c in (cc+ck)[:6]:
                    vals[c]={str(k):int(v) for k,v in full[c].astype(str).value_counts().head(6).items()}
                rows.append(dict(screen=sc,file=os.path.relpath(fp,EXPL).replace("\\","/"),nrows=len(full),
                                 ceiling_cols="|".join(cc),kill_cols="|".join(ck),vc=json.dumps(vals)[:1200]))
K=pd.DataFrame(rows); K.to_csv(os.path.join(HERE,"INVENTORY_KILL_COLS.csv"),index=False)
print("tables with ceiling/verdict cols:",len(K))
for _,rr in K.iterrows():
    print("\n%s :: %s  rows=%d" % (rr["screen"],os.path.basename(rr["file"]),rr["nrows"]))
    print("   ceiling:",rr["ceiling_cols"]," verdict:",rr["kill_cols"])
    print("   ",rr["vc"][:800])
