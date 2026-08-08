"""S03 -- probe the raw permutation-draw archives.  If the draws are on disk, the
`null_mean > observed` flag is computable even where the screen never recorded a null mean.
Also: what STATISTIC are the draws on?  The flag is only meaningful for a NON-NEGATIVE
statistic (dR2); for a signed t the analogue is mean(|t_null|) vs |t_obs|.
"""
import os
import numpy as np
import pandas as pd

EXP = (r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees"
       r"\player-model-program\experiments\exploration")

FILES = [
    ("E0_I0014_residual_heterogeneity", "permutation_nulls.npz"),
    ("E0_I0016_efficiency_predictors", "permutation_draws.npz"),
    ("E0_I0017_shot_quality_efficiency", "permutation_draws.npz"),
    ("E0_I0019_availability_forecast", "permutation_nulls.npz"),
    ("E0_I0024_reb_ast_characterisation", "permutation_draws.npz"),
    ("E0_I0029_freethrow_hurdle", "permutation_draws.npz"),
    ("E1_I0018_teammate_volume_channel", "permutation_draws.npz"),
]

for scr, fn in FILES:
    p = os.path.join(EXP, scr, fn)
    print("\n" + "=" * 100)
    print(scr, "/", fn)
    print("=" * 100)
    z = np.load(p, allow_pickle=True)
    for k in z.files:
        a = z[k]
        try:
            desc = (f"shape={a.shape} dtype={a.dtype} "
                    f"min={np.nanmin(a):.5g} max={np.nanmax(a):.5g} "
                    f"mean={np.nanmean(a):.5g} neg_frac={float(np.nanmean(a < 0)):.3f}")
        except Exception:
            desc = f"shape={getattr(a, 'shape', '?')} dtype={a.dtype} (non-numeric) {a[:5]}"
        print(f"  {k:34s} {desc}")
