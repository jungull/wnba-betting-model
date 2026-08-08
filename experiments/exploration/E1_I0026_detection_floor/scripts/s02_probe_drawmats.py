"""s02_probe_drawmats.py -- READ-ONLY probe of the per-cell null draw MATRICES the completed
screens left on disk.  These carry the real between-cell correlation structure of this
programme's families, which is what a family-wise threshold actually depends on.
"""
import os
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"

for rel in ["E1_I0018_teammate_volume_channel/permutation_draws.npz",
            "E1_I0018_teammate_volume_channel/permutation_draws_s02.npz"]:
    p = os.path.join(EXPL, rel.replace("/", os.sep))
    print("=" * 90)
    print(rel, os.path.exists(p))
    if not os.path.exists(p):
        continue
    z = np.load(p, allow_pickle=True)
    for k in z.files:
        a = z[k]
        print("   %-22s %-14s %s" % (k, str(a.dtype), a.shape))
    if "keys" in z.files:
        print("   first 5 keys:", list(z["keys"][:5]))

for rel in ["E0_I0014_residual_heterogeneity/maxt_null_draws_whole_screen.csv",
            "E0_I0016_efficiency_predictors/maxt_null_draws.csv",
            "E0_I0019_availability_forecast/maxt_null_draws.csv",
            "E1_I0018_teammate_volume_channel/maxt_null_draws.csv"]:
    p = os.path.join(EXPL, rel.replace("/", os.sep))
    print("=" * 90)
    print(rel, os.path.exists(p))
    if os.path.exists(p):
        t = pd.read_csv(p)
        print("   shape", t.shape, "cols", list(t.columns)[:8])
