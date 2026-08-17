"""S04 -- POST-HOC, NOT PREREGISTERED.  A second power curve with a CLUSTERED injection.

WHY THIS EXISTS.  The preregistered injection (s03) uses an iid N(0,1) column.  A cluster
sign-flip null over player-seasons is at its MOST powerful against an iid per-row signal, so that
curve OVERSTATES the design's power against the real block N, whose columns have a median
within-player-season lag-1 acf of ~0.57 and live substantially between player-seasons.

This stage brackets the truth by repeating the identical procedure with a signal that is CONSTANT
within a player-season -- the maximally clustered case.  The real effect sits between the two.

NOTHING HERE CHANGES A PREREGISTERED THRESHOLD OR VERDICT.  It is a diagnostic, added after seeing
the s03 curve, and it is labelled POST-HOC everywhere it appears.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _e56 import *  # noqa
from _common import HERE, MIN_TRAIN, folds_wf  # noqa

t0 = time.time()
sub, X, ix, meta = build("A4_CLEAN_DEC", impute="prior")
y = sub["absres_minutes"].to_numpy(float)
psb = meta["psblock"]
folds = folds_wf(meta["gdate"], MIN_TRAIN)
scored = np.sort(np.concatenate([te for _, te in folds]))
sd_y = float(y[scored].std(ddof=1))
l5c = [ix[c] for c in L5]
nc = [ix[c] for c in BLOCK_N]
NBps = int(psb.max()) + 1

CGRID = [0.00, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60, 0.90]
NREP = 40
rows = []
print("POST-HOC clustered injection: u is CONSTANT within each of the %d player-seasons." % NBps)
for c in CGRID:
    det, drs = [], []
    for k in range(NREP):
        rng = np.random.default_rng(SEED_INJ + 7_000_000 + 1000 * CGRID.index(c) + k)
        ub = rng.standard_normal(NBps)
        u = ub[psb]
        u = (u - u.mean()) / u.std(ddof=1)
        yi = y + c * sd_y * u
        Z = np.column_stack([X, u])
        ui = Z.shape[1] - 1
        ssti = sst_of(yi, scored)
        vr = oof(folds, yi, Z, l5c)
        vc = oof(folds, yi, Z, nc + l5c + [ui])
        drs.append((sse(yi, vr, scored) - sse(yi, vc, scored)) / ssti)
        d = (yi[scored] - vr[scored]) ** 2 - (yi[scored] - vc[scored]) ** 2
        det.append(signflip(d, psb[scored], 5000, SEED_NULL + k)[1] < 0.05)
    rows.append(dict(c=c, implied_r2=c ** 2 / (1 + c ** 2), mean_realised_dr2=float(np.mean(drs)),
                     sd_realised_dr2=float(np.std(drs, ddof=1)),
                     detection_rate=float(np.mean(det)), n_rep=NREP))
    print("  c=%.2f  implied dR2 %.5f  realised dR2 %+.6f (sd %.6f)  DETECTION %.3f  (%.0fs)"
          % (c, rows[-1]["implied_r2"], rows[-1]["mean_realised_dr2"],
             rows[-1]["sd_realised_dr2"], rows[-1]["detection_rate"], time.time() - t0),
          flush=True)

P = pd.DataFrame(rows)
P.to_csv(os.path.join(HERE, "POWER_INJECTION_CLUSTERED_POSTHOC.csv"), index=False)
ok = P[(P["detection_rate"] >= 0.80) & (P["c"] > 0)]
mde = float(ok["mean_realised_dr2"].min()) if len(ok) else float("nan")
print("\n  POST-HOC MDE at 80%% power against a PLAYER-SEASON-CONSTANT signal: dR2 = %s"
      % ("%+.6f" % mde if np.isfinite(mde) else "NOT REACHED on this grid"))

# ------------------------------------------------------------------------------------------
# POST-HOC #2: the reference-incompleteness claim deserves its own null.  L4 (level-only, 8
# columns) vs L1 (the single trailing-level column D134 used).  Both are REFERENCES; this asks
# whether the stronger one is really stronger or whether the gap is noise.
# ------------------------------------------------------------------------------------------
print("\nPOST-HOC #2 -- is the level ladder really stronger than the single trailing-level "
      "column?  (not preregistered)")
y_ = y
blocks = block_index_lists(psb, meta["gdate"])
v1 = oof(folds, y_, X, [ix[c] for c in L1])
v4 = oof(folds, y_, X, [ix[c] for c in L4])
v5 = oof(folds, y_, X, [ix[c] for c in L5])
SST = sst_of(y_, scored)
d41 = (sse(y_, v1, scored) - sse(y_, v4, scored)) / SST
dd = (y_[scored] - v1[scored]) ** 2 - (y_[scored] - v4[scored]) ** 2
_, p41, dr41 = signflip(dd, psb[scored], 5000, SEED_NULL)
B41 = block_boot_dr2(y_, v1, v4, scored, blocks, 2000, SEED_BOOT)
ci41 = (float(np.percentile(B41, 2.5)), float(np.percentile(B41, 97.5)))
print("  dR2(L4 over L1) = %+.6f   sign-flip p = %.6f   bootstrap CI [%+.6f, %+.6f]   "
      "frac<=0 = %.4f" % (d41, p41, ci41[0], ci41[1], float((B41 <= 0).mean())))
d51 = (sse(y_, v1, scored) - sse(y_, v5, scored)) / SST
dd5 = (y_[scored] - v1[scored]) ** 2 - (y_[scored] - v5[scored]) ** 2
_, p51, _ = signflip(dd5, psb[scored], 5000, SEED_NULL)
print("  dR2(L5 over L1) = %+.6f   sign-flip p = %.6f" % (d51, p51))
np.savez_compressed(os.path.join(RAW, "s04_posthoc.npz"), boot_L4_over_L1=B41,
                    signflip_L4_over_L1=dr41)

json.dump(dict(posthoc=True, rows=rows, mde_dr2_at_80pct_clustered=mde,
               dr2_L4_over_L1=float(d41), signflip_p_L4_over_L1=float(p41),
               boot_ci_L4_over_L1=ci41, boot_frac_le0_L4_over_L1=float((B41 <= 0).mean()),
               dr2_L5_over_L1=float(d51), signflip_p_L5_over_L1=float(p51)),
          open(os.path.join(HERE, "scripts", "_s04.json"), "w"), indent=2, default=str)
print("DONE s04 (%.0fs)" % (time.time() - t0))
