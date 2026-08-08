import pandas as pd, numpy as np, os
EXPL=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
dr=pd.read_csv(os.path.join(EXPL,"E1_I0031_rapm_as_prior","permutation_draws_plusminus.csv"))
q=dr.groupby(["target","over","added"])["value"].agg(p95=lambda s: float(np.quantile(s,0.95)),mean="mean",sd="std",n="size").reset_index()
pm=pd.read_csv(os.path.join(EXPL,"E1_I0031_rapm_as_prior","plusminus_separate.csv"))
pm=pm[pm["null"].notna()]
m=pm.merge(q,on=["target","over","added"],how="left")
m["p95_match"]=(m.null_p95-m.p95).abs()
print(m[["target","over","added","stratum","null_p95","p95","p95_match"]].to_string())
print("\nrows whose recorded null_p95 matches the archive to <1e-12:",int((m.p95_match<1e-12).sum()),"of",len(m))
print(m.groupby("stratum").p95_match.median())
