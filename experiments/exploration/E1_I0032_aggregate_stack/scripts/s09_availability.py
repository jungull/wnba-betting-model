"""E1_I0032 s09 -- C2_AVAIL_LONGABSENCE_RECAL.  ONE preregistered test on a SEPARATE RESPONSE.

p_active is BINARY and is scored by Brier.  Under D101's rule D1 it is not commensurable with any
dR2 on points, minutes, attempts or points-per-minute, so it cannot enter the stack and its number
is reported BESIDE the stack, never inside it.  That was declared in the preregistration before any
statistic existed.

Because paired squared loss on a 0/1 response IS the Brier decomposition, the identical clustered
sign-flip machinery applies unchanged.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import OUT, AVAIL, SCORED, PLACEBO_SEED, prereg, paired

pd.set_option("display.width", 240)
spec = prereg()
print("prereg sha256 %s  MATCH" % spec["sha256"])

BINS = [0, 2, 4, 7, 11, np.inf]        # frozen in the preregistration
EPS = 1e-6

av = pd.read_parquet(AVAIL)
av = av[np.isin(av["season"].to_numpy(), SCORED)].copy()
y = pd.to_numeric(av["y"], errors="coerce").to_numpy(float)
dsa = pd.to_numeric(av["pl_days_since_appear"], errors="coerce").to_numpy(float)
season = av["season"].to_numpy()
groups = (av["season"].astype(str) + "_" + av["player_id"].astype(str)).to_numpy()

rows = []
for arm in ("v14", "v15"):
    p = pd.to_numeric(av["%s__pred_point" % arm], errors="coerce").to_numpy(float)
    m = np.isfinite(y) & np.isfinite(p) & np.isfinite(dsa)
    b = np.digitize(dsa, BINS[1:-1])
    pc = np.clip(p, EPS, 1 - EPS)
    logit = np.log(pc / (1 - pc))
    newp = p.copy()
    per = []
    for s in SCORED:
        tr = m & (season < s)
        te = m & (season == s)
        if tr.sum() < 200 or te.sum() == 0:
            continue
        for k in range(len(BINS) - 1):
            trk = tr & (b == k)
            tek = te & (b == k)
            if trk.sum() < 40 or tek.sum() == 0:
                continue
            # additive logit offset that matches the bin's OBSERVED rate on STRICTLY EARLIER seasons
            obs = float(np.clip(y[trk].mean(), EPS, 1 - EPS))
            pred = float(np.clip(p[trk].mean(), EPS, 1 - EPS))
            off = np.log(obs / (1 - obs)) - np.log(pred / (1 - pred))
            newp[tek] = 1.0 / (1.0 + np.exp(-(logit[tek] + off)))
            per.append(dict(arm=arm, season=int(s), bin=k, n_train=int(trk.sum()),
                            n_scored=int(tek.sum()), offset_logit=float(off),
                            train_obs=obs, train_pred=pred))
    sc = m & (season > min(SCORED))          # 2022 has no earlier season -> unscored
    pr = paired(y[sc], newp[sc], p[sc], groups[sc], name_a="RECAL", name_b="STORED")
    br_new = float(np.mean((y[sc] - newp[sc]) ** 2))
    br_old = float(np.mean((y[sc] - p[sc]) ** 2))
    rows.append(dict(component="C2_AVAIL_LONGABSENCE_RECAL", arm=arm, kind="REAL",
                     response="p_active (BINARY -- NOT commensurable with any dR2 here)",
                     n=int(sc.sum()), n_clusters=pr["n_clusters"],
                     brier_stored=br_old, brier_recalibrated=br_new,
                     brier_skill=1.0 - br_new / br_old,
                     dr2_on_binary_response=pr["dr2"], p=pr["p"],
                     null_mean=pr["null_mean"], null_sd=pr["null_sd"],
                     p_row_NAIVE=pr["p_row_NAIVE"], inflation=pr["inflation"]))
    print("  %-4s REAL     Brier %.6f -> %.6f (skill %+.4f%%) p %.4f  null_sd %.3e"
          % (arm, br_old, br_new, 100 * (1 - br_new / br_old), pr["p"], pr["null_sd"]))

    # PLACEBO: the identical recalibration driven by a SHUFFLED duration variable
    rng = np.random.default_rng(PLACEBO_SEED + 23)
    dsp = dsa.copy()
    idx = np.flatnonzero(m)
    dsp[idx] = dsa[rng.permutation(idx)]
    bp = np.digitize(dsp, BINS[1:-1])
    newp2 = p.copy()
    for s in SCORED:
        tr = m & (season < s)
        te = m & (season == s)
        if tr.sum() < 200 or te.sum() == 0:
            continue
        for k in range(len(BINS) - 1):
            trk = tr & (bp == k)
            tek = te & (bp == k)
            if trk.sum() < 40 or tek.sum() == 0:
                continue
            obs = float(np.clip(y[trk].mean(), EPS, 1 - EPS))
            pred = float(np.clip(p[trk].mean(), EPS, 1 - EPS))
            off = np.log(obs / (1 - obs)) - np.log(pred / (1 - pred))
            newp2[tek] = 1.0 / (1.0 + np.exp(-(logit[tek] + off)))
    pr2 = paired(y[sc], newp2[sc], p[sc], groups[sc], name_a="PLACEBO_RECAL", name_b="STORED")
    br_p = float(np.mean((y[sc] - newp2[sc]) ** 2))
    rows.append(dict(component="C2_AVAIL_LONGABSENCE_RECAL", arm=arm, kind="PLACEBO",
                     response="p_active (BINARY)", n=int(sc.sum()), n_clusters=pr2["n_clusters"],
                     brier_stored=br_old, brier_recalibrated=br_p,
                     brier_skill=1.0 - br_p / br_old,
                     dr2_on_binary_response=pr2["dr2"], p=pr2["p"],
                     null_mean=pr2["null_mean"], null_sd=pr2["null_sd"],
                     p_row_NAIVE=pr2["p_row_NAIVE"], inflation=pr2["inflation"]))
    print("  %-4s PLACEBO  Brier %.6f -> %.6f (skill %+.4f%%) p %.4f"
          % (arm, br_old, br_p, 100 * (1 - br_p / br_old), pr2["p"]))

pd.DataFrame(rows).to_csv(os.path.join(OUT, "availability_recalibration.csv"), index=False)
pd.DataFrame(per).to_csv(os.path.join(OUT, "availability_offsets.csv"), index=False)
print("\nwrote availability_recalibration.csv and availability_offsets.csv")
print("\nD102's BINDING COUNTEREXAMPLE is respected: the two arms are reported SEPARATELY and no")
print("blanket rule is proposed.  Route/recalibrate per target, verified per target.")
