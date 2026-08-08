import os,json
import numpy as np, pandas as pd
EXPL=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
cov=pd.read_csv(os.path.join(EXPL,"E1_I0038_within_entity_null_audit","CENSUS_COVERAGE.csv"))
CENSUS={"E0_I0014_residual_heterogeneity","E0_I0016_efficiency_predictors","E0_I0017_shot_quality_efficiency","E0_I0019_availability_forecast","E0_I0024_reb_ast_characterisation","E0_I0029_freethrow_hurdle","E1_I0018_teammate_volume_channel","E1_I0023_usage_defence_interaction"}
TARGETS=[s for s in sorted(cov["screen"].unique()) if s not in CENSUS]
rows=[]
for sc in TARGETS:
    for root,_d,files in os.walk(os.path.join(EXPL,sc)):
        for fn in files:
            if not fn.lower().endswith(".csv") or ("draw" not in fn.lower() and "null" not in fn.lower()): continue
            fp=os.path.join(root,fn)
            try: df=pd.read_csv(fp)
            except Exception: continue
            num=df.select_dtypes("number"); stats={}
            for c in num.columns:
                a=num[c].to_numpy(float); a=a[np.isfinite(a)]
                if a.size>=50: stats[c]=dict(mean=float(a.mean()),sd=float(a.std(ddof=1)),n=int(a.size))
            std=[c for c,v in stats.items() if abs(v["mean"])<1e-6 and abs(v["sd"]-1)<1e-4]
            rows.append(dict(screen=sc,file=os.path.relpath(fp,EXPL).replace("\\","/"),rows=len(df),
                numeric_cols=len(stats),standardised_cols="|".join(std),RAW_RECOVERABLE=(len(std)==0),
                stats=json.dumps(stats)[:900]))
D=pd.DataFrame(rows); D.to_csv(os.path.join(HERE,"INVENTORY_CSV_DRAWS.csv"),index=False)
print("CSV draw/null dumps in the thirty:",len(D))
print(D[["screen","file","rows","numeric_cols","standardised_cols","RAW_RECOVERABLE"]].to_string())
print("\nfiles stored STANDARDISED (null mean destroyed):",int((~D.RAW_RECOVERABLE).sum()))
