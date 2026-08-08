"""E1_I0032 s10 -- persist the permutation draws for every HEADLINE and PLACEBO_HEADLINE cell.

D103 ruling 2 requires null_mean and null_sd beside every p; those are in the CSVs.  The draws
themselves are kept so a reader can recompute the null rather than take it on trust.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import OUT, TARGETS, SEED, N_DRAWS, SK, prereg, prior_season_tercile_top
import s08_stack as S            # re-uses the exact same build() and strata

prereg()
out = {}
meta = []
for t in TARGETS:
    ch = S.work["champ_%s" % t].to_numpy(float)
    y = S.work["y_%s" % t].to_numpy(float)
    for s in S.ALL_STRATA:
        m = S.STRATA[s]
        for label, arm in (("REAL", S.FULL[t]), ("PLACEBO", S.PFULL[t])):
            r = SK.paired_forecast_comparison(y[m], arm[m], ch[m], groups=S.groups[m],
                                              n_draws=N_DRAWS, seed=SEED, name_a=label,
                                              name_b="CHAMPION", alternative="two_sided")
            k = "%s__%s__%s" % (label, t, s)
            d = np.asarray(r["draws"], float)
            out[k] = d
            meta.append(dict(cell=k, observed=float(r["dr2_a_minus_b"]), p=float(r["p"]),
                             null_mean=float(d.mean()), null_sd=float(d.std(ddof=1)),
                             n=int(r["n"]), n_clusters=int(r["n_groups"]), n_draws=N_DRAWS,
                             seed=SEED, scheme="clustered paired sign-flip on season x player"))
np.savez_compressed(os.path.join(OUT, "permutation_draws.npz"), **out)
pd.DataFrame(meta).to_csv(os.path.join(OUT, "permutation_draws_index.csv"), index=False)
print("wrote permutation_draws.npz (%d cells) and permutation_draws_index.csv" % len(out))
print(pd.DataFrame(meta)[["cell", "observed", "p", "null_mean", "null_sd"]].to_string(index=False))
