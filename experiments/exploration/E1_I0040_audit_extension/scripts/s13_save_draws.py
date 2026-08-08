"""S13 -- persist the draws this audit recovered as .npz, per the deliverable list.

Source: E1_I0031_rapm_as_prior/permutation_draws_plusminus.csv, 48,000 draws. Proved in
scripts/s06b_stratum_check.py to belong to the wf_eval_2023_24 stratum ONLY (its p95 reproduces the
recorded null_p95 to <1e-16 on all 24 wf_eval rows and misses all 24 decision_stratum rows).
Written here keyed on (target, over, added) with the stratum attribution the source file lacks --
that missing key is DEFECTS D-02. Raw values, never standardised.
"""
import os
import numpy as np, pandas as pd
EXPL=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE=r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0040_audit_extension"
dr=pd.read_csv(os.path.join(EXPL,"E1_I0031_rapm_as_prior","permutation_draws_plusminus.csv"))
d={}
for (t,o,a),g in dr.groupby(["target","over","added"]):
    d["%s|%s|%s|wf_eval_2023_24"%(t,o,a)]=g.sort_values("draw")["value"].to_numpy(float)
d["_PROVENANCE"]=np.array([
 "source: E1_I0031_rapm_as_prior/permutation_draws_plusminus.csv (read-only)",
 "stratum attribution PROVED by exact null_p95 match, scripts/s06b_stratum_check.py",
 "RAW draw values, not standardised; null mean = mean of each array",
 "the decision_stratum_wf arm was never written by E1_I0031 and cannot be recovered (DEFECTS D-02)",
 "partition: 2021-2024 exploration only"],dtype=object)
out=os.path.join(HERE,"nulls","E1_I0031_plusminus_wf_eval_recovered_draws.npz")
np.savez_compressed(out,**d)
z=np.load(out,allow_pickle=True)
arrs=[k for k in z.files if k!="_PROVENANCE"]
print("wrote",out,"(%d bytes)"%os.path.getsize(out))
print("keys:",len(arrs),"| draws per key:",len(z[arrs[0]]))
print("sanity -- not standardised: mean=%.6e sd=%.6e (a standardised archive would be 0 and 1)"
      %(float(z[arrs[0]].mean()),float(z[arrs[0]].std(ddof=1))))
