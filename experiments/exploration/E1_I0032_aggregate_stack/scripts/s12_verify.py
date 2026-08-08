import pandas as pd, numpy as np, json, os
OUT=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0032_aggregate_stack"
w=pd.read_parquet(os.path.join(OUT,"_work.parquet"))
C=w["COMMON"].to_numpy(bool); D=w["DECISION"].to_numpy(bool)
fl=w["fbl_pts"].to_numpy(float)
print("common",C.sum(),"decision",D.sum())
print("routed (fbl==2) in common:",int(((fl==2)&C).sum()))
print("routed in DECISION      :",int(((fl==2)&D).sum()))
print("fbl==3 in DECISION      :",int(((fl==3)&D).sum()))
print("max n_prior among routed:",float(np.nanmax(w['n_prior'].to_numpy(float)[(fl==2)&C])))
print("max min5 among routed   :",float(np.nanmax(w['min5'].to_numpy(float)[(fl==2)&C])))
j=json.load(open(os.path.join(OUT,"FINDINGS.json"),encoding="utf-8"))
print("FINDINGS.json OK, top keys:",len(j))
