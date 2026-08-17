"""S03 -- QUESTION 3 (is the increment worth anything) + POWER + REPLICATION.

Preregistered predictions tested here: P12, P13, P14, P15.

Power is run whether or not the answer is a null, per the brief.  The T8 discipline governs the
conversion arms: predicting error is not predicting skill, so the conversion is measured as skill
on the MINUTES LEVEL against a reference that faces the same rows.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _e56 import *  # noqa
from _common import HERE, MIN_TRAIN, Z80, folds_gkf, folds_wf  # noqa

t0 = time.time()
out = {}

sub, X, ix, meta = build("A4_CLEAN_DEC", impute="prior")
y = sub["absres_minutes"].to_numpy(float)
gd = meta["gdate"]
psb, tgb = meta["psblock"], meta["tgblock"]
folds = folds_wf(gd, MIN_TRAIN)
scored = np.sort(np.concatenate([te for _, te in folds]))
SST = sst_of(y, scored)
blocks = block_index_lists(psb, gd)
ARMS = dict(LADDER)
ARMS["C1"] = L1 + BLOCK_N
ARMS["C5"] = L5 + BLOCK_N
PRED = {k: oof(folds, y, X, [ix[c] for c in v]) for k, v in ARMS.items()}
best_level = max(["L1", "L2", "L3", "L4", "L5"],
                 key=lambda k: 1.0 - sse(y, PRED[k], scored) / SST)
dr2_obs = (sse(y, PRED["L5"], scored) - sse(y, PRED["C5"], scored)) / SST
print("n=%d scored=%d  dR2(C5 over L5)=%+.6f  strongest level rung=%s"
      % (len(sub), len(scored), dr2_obs, best_level), flush=True)

# ===================================================================== P15  POWER / INJECTION
print("\n" + "=" * 100)
print("S03a -- POWER.  Injection curve: y_inj = y + c*sd(y)*u, u an extra column inside block N.")
print("=" * 100)
sd_y = float(y[scored].std(ddof=1))
CGRID = [0.00, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60, 0.90]
NREP = 40
l5c = [ix[c] for c in L5]
nc = [ix[c] for c in BLOCK_N]
rows = []
for c in CGRID:
    det, drs = [], []
    for k in range(NREP):
        rng = np.random.default_rng(SEED_INJ + 1000 * CGRID.index(c) + k)
        u = rng.standard_normal(len(y))
        u = (u - u.mean()) / u.std(ddof=1)
        yi = y + c * sd_y * u
        Z = np.column_stack([X, u])
        ui = Z.shape[1] - 1
        ssti = sst_of(yi, scored)
        vr = oof(folds, yi, Z, l5c)
        vc = oof(folds, yi, Z, nc + l5c + [ui])
        dr = (sse(yi, vr, scored) - sse(yi, vc, scored)) / ssti
        d = (yi[scored] - vr[scored]) ** 2 - (yi[scored] - vc[scored]) ** 2
        p = signflip(d, psb[scored], 5000, SEED_NULL + k)[1]
        drs.append(dr)
        det.append(p < 0.05)
    rows.append(dict(c=c, implied_r2=c ** 2 / (1 + c ** 2), mean_realised_dr2=float(np.mean(drs)),
                     sd_realised_dr2=float(np.std(drs, ddof=1)),
                     detection_rate=float(np.mean(det)), n_rep=NREP))
    print("  c=%.2f  implied dR2 %.5f  realised dR2 %+.6f (sd %.6f)  DETECTION %.3f  (%.0fs)"
          % (c, rows[-1]["implied_r2"], rows[-1]["mean_realised_dr2"],
             rows[-1]["sd_realised_dr2"], rows[-1]["detection_rate"], time.time() - t0),
          flush=True)
POW = pd.DataFrame(rows)
POW.to_csv(os.path.join(HERE, "POWER_INJECTION.csv"), index=False)
r10 = POW[np.isclose(POW["c"], 0.10)].iloc[0]
P15 = bool(r10["detection_rate"] >= 0.80)
ok = POW[(POW["detection_rate"] >= 0.80) & (POW["c"] > 0)]
mde = float(ok["mean_realised_dr2"].min()) if len(ok) else np.nan
print("\n  P15 (detection >= 0.80 at an injected dR2 of ~0.010, c=0.10): %s  [rate %.3f, "
      "realised dR2 %+.6f]" % (P15, r10["detection_rate"], r10["mean_realised_dr2"]))
print("  smallest injected dR2 detected at >= 80%% power (MDE): %+.6f" % mde)
print("  false-positive rate at c=0 (should be near 0.05): %.3f"
      % POW[POW["c"] == 0]["detection_rate"].iloc[0])
out.update(dict(P15=P15, mde_dr2_at_80pct=mde,
                typeI_at_c0=float(POW[POW["c"] == 0]["detection_rate"].iloc[0]),
                power_rows=rows))

# ======================================================================== P12  ABSTENTION
print("\n" + "=" * 100)
print("S03b -- ABSTENTION, in minutes.  Rank by predicted |error|, drop the worst q%, measure "
      "the SHIPPED forecast's MAE on what is left.")
print("=" * 100)
base_mae = float(np.abs(y[scored]).mean())
base_rmse = float(np.sqrt((y[scored] ** 2).mean()))
print("  full sample: n=%d  MAE=%.4f min  RMSE=%.4f min" % (len(scored), base_mae, base_rmse))
ab = []
for arm in ["L1", best_level, "L5", "C5"]:
    v = PRED[arm][scored]
    r = pd.Series(v).rank(method="first", pct=True).to_numpy()
    for q in [0, 10, 20, 30, 40, 50]:
        keep = r <= 1.0 - q / 100.0
        mae = float(np.abs(y[scored][keep]).mean())
        rmse = float(np.sqrt((y[scored][keep] ** 2).mean()))
        ab.append(dict(arm=arm, drop_pct=q, n_kept=int(keep.sum()), mae=mae, rmse=rmse,
                       mae_reduction=1 - mae / base_mae, mse_reduction=1 - (rmse / base_rmse) ** 2))
AB = pd.DataFrame(ab)
AB.to_csv(os.path.join(HERE, "ABSTENTION.csv"), index=False)
piv = AB.pivot(index="drop_pct", columns="arm", values="mae_reduction")
print("\n  MAE reduction on the retained rows, by ranking arm:")
print((piv * 100).round(2).to_string())
c30 = float(AB[(AB.arm == "C5") & (AB.drop_pct == 30)]["mae_reduction"].iloc[0])
l30 = float(AB[(AB.arm == best_level) & (AB.drop_pct == 30)]["mae_reduction"].iloc[0])
P12 = bool(c30 >= 0.08)
print("\n  P12 (C5 ranking, drop 30%%, MAE reduction >= 8%%): %s  [%.2f%%]" % (P12, 100 * c30))
print("  the same abstention on the strongest LEVEL-ONLY ranking (%s): %.2f%%  -> the non-level "
      "block is worth %.2f percentage points of MAE reduction, not %.2f"
      % (best_level, 100 * l30, 100 * (c30 - l30), 100 * c30))
out.update(dict(P12=P12, abst_c5_drop30=c30, abst_level_drop30=l30, base_mae=base_mae))

# ============================================================== interval widths at matched cover
print("\n" + "=" * 100)
print("S03c -- WHAT AN 80% INTERVAL COSTS.  |resid| -> Gaussian sd via sqrt(pi/2).")
print("=" * 100)
resid = (sub["y_minutes"].to_numpy(float)
         - sub["minutes__pred_point"].to_numpy(float))[scored]
K = np.sqrt(np.pi / 2.0)
iv = []
shipped_sd = sub["minutes__pred_sd"].to_numpy(float)[scored]
for nm, sdv in [("SHIPPED_const_sd", shipped_sd), ("L1", np.maximum(PRED["L1"][scored], 1e-6) * K),
                (best_level, np.maximum(PRED[best_level][scored], 1e-6) * K),
                ("C5", np.maximum(PRED["C5"][scored], 1e-6) * K)]:
    cov = float((np.abs(resid) <= Z80 * sdv).mean())
    wid = float((2 * Z80 * sdv).mean())
    # matched-coverage comparison: one global scale so every arm covers exactly 80% on these rows.
    # DISCLOSED AS AN ORACLE SCALING -- it uses the scored outcomes and is applied identically to
    # every arm, so it compares WIDTHS at equal coverage and nothing else.
    k80 = float(np.percentile(np.abs(resid) / sdv, 80.0))
    iv.append(dict(model=nm, coverage_nominal80=cov, mean_width=wid,
                   matched_cover_scale=k80, mean_width_at_80pct_cover=float((2 * k80 * sdv).mean()),
                   sd_of_sd=float(np.std(sdv, ddof=1))))
    print("  %-17s coverage(nominal 80%%)=%.4f  mean width=%.3f min  |  at MATCHED 80%% cover: "
          "mean width=%.3f min  (sd of the per-row sd = %.4f)"
          % (nm, cov, wid, iv[-1]["mean_width_at_80pct_cover"], iv[-1]["sd_of_sd"]))
IV = pd.DataFrame(iv)
IV.to_csv(os.path.join(HERE, "INTERVALS.csv"), index=False)
w_ship = float(IV[IV.model == "SHIPPED_const_sd"]["mean_width_at_80pct_cover"].iloc[0])
w_lev = float(IV[IV.model == best_level]["mean_width_at_80pct_cover"].iloc[0])
w_c5 = float(IV[IV.model == "C5"]["mean_width_at_80pct_cover"].iloc[0])
print("\n  at matched 80%% coverage: constant sd %.3f -> level-only %.3f (%.2f%%) -> "
      "C5 %.3f (%.2f%% vs constant, %.2f%% vs level-only)"
      % (w_ship, w_lev, 100 * (w_lev / w_ship - 1), w_c5, 100 * (w_c5 / w_ship - 1),
         100 * (w_c5 / w_lev - 1)))
out["intervals"] = iv

# ============================================================ P13  DOES IT BUY A BETTER FORECAST
print("\n" + "=" * 100)
print("S03d -- T8: does the variance forecast convert into a better MINUTES LEVEL forecast?")
print("=" * 100)
ym = sub["y_minutes"].to_numpy(float)
SSTm = sst_of(ym, scored)
# The walk-forward warm-up rows (the first 604, never scored) have no out-of-fold prediction.
# They are used ONLY as training data here, never scored, so they are filled with the STRICTLY
# PRIOR expanding mean of the response -- which is exactly the L0 arm's own forecast, and
# therefore reads nothing a forecaster at that row could not have.  Disclosed in DEFECTS.md D-8.
_run = np.cumsum(y) - y
_cnt = np.arange(len(y), dtype=float)
_fill = np.empty(len(y))
_fill[0] = y[0]
_fill[1:] = _run[1:] / _cnt[1:]
vhat = np.maximum(np.where(np.isfinite(PRED["C5"]), PRED["C5"], _fill), 1e-6)
n_filled = int((~np.isfinite(PRED["C5"])).sum())
print("  warm-up rows with no OOF vhat, filled from the strictly-prior expanding mean: %d of %d "
      "(none of them is scored: %s)"
      % (n_filled, len(y), bool(not np.isin(np.where(~np.isfinite(PRED["C5"]))[0], scored).any())))
lev_ref = oof(folds, ym, X, l5c)
r2ref = 1.0 - sse(ym, lev_ref, scored) / SSTm
shipped = sub["minutes__pred_point"].to_numpy(float)
print("  reference: tuned ridge on the L5 level columns, response y_minutes.  "
      "OOF R2 = %+.6f  (shipped forecast OOF R2 = %+.6f)"
      % (r2ref, 1.0 - sse(ym, shipped, scored) / SSTm), flush=True)


def wridge_oof(w):
    o = np.full(len(ym), np.nan)
    for tr, te in folds:
        Xt = X[np.ix_(tr, l5c)]
        ww = w[tr] / w[tr].mean()
        mu, sdc = Xt.mean(0), Xt.std(0)
        sdc = np.where(sdc > 1e-12, sdc, 1.0)
        Zt = (Xt - mu) / sdc
        A = Zt * ww[:, None]
        G = A.T @ Zt
        ymw = float((ym[tr] * ww).sum() / ww.sum())
        b = np.linalg.solve(G + 1.0 * np.eye(G.shape[0]), A.T @ (ym[tr] - ymw))
        beta = b / sdc
        o[te] = (ymw - mu @ beta) + X[np.ix_(te, l5c)] @ beta
    return o


conv = []
# (a) variance-weighted refit of the level model
conv.append(("variance_weighted_refit", wridge_oof(1.0 / vhat ** 2)))
# (b) adaptive blend of the shipped forecast toward the level reference, weights linear in vhat
zv = (vhat - np.nanmean(vhat[scored])) / np.nanstd(vhat[scored])
bl = np.full(len(ym), np.nan)
for tr, te in folds:
    # lev_ref is itself out-of-fold, so it is undefined on the warm-up rows.  The blend's own
    # coefficients are fitted on the training rows where it IS defined.
    trf = tr[np.isfinite(lev_ref[tr])]
    if len(trf) < 30:
        bl[te] = lev_ref[te]
        continue
    A = np.column_stack([np.ones(len(trf)), shipped[trf] - lev_ref[trf],
                         (shipped[trf] - lev_ref[trf]) * zv[trf]])
    cf = np.linalg.lstsq(A, ym[trf] - lev_ref[trf], rcond=None)[0]
    At = np.column_stack([np.ones(len(te)), shipped[te] - lev_ref[te],
                          (shipped[te] - lev_ref[te]) * zv[te]])
    bl[te] = lev_ref[te] + At @ cf
conv.append(("adaptive_blend_shipped_vs_level", bl))
# (c) mean augmentation: vhat as an extra feature in the level model
Xa = np.column_stack([X, vhat])
conv.append(("mean_augmentation_vhat", oof(folds, ym, Xa, l5c + [Xa.shape[1] - 1])))
# (d) vhat interacted with the trailing level
Xb = np.column_stack([X, vhat, vhat * X[:, ix["pl_min_mean5"]]])
conv.append(("vhat_x_level_interaction",
             oof(folds, ym, Xb, l5c + [Xb.shape[1] - 2, Xb.shape[1] - 1])))

crows = []
for nm, yh in conv:
    dr = (sse(ym, lev_ref, scored) - sse(ym, yh, scored)) / SSTm
    d = (ym[scored] - lev_ref[scored]) ** 2 - (ym[scored] - yh[scored]) ** 2
    _, p, _ = signflip(d, psb[scored], 5000, SEED_NULL)
    crows.append(dict(arm=nm, oof_r2=1.0 - sse(ym, yh, scored) / SSTm, dr2_over_level_ref=dr,
                      signflip_p=p))
    print("  %-34s OOF R2 %+.6f   dR2 over level reference %+.6f   sign-flip p %.4f"
          % (nm, crows[-1]["oof_r2"], dr, p))
CV = pd.DataFrame(crows)
CV.to_csv(os.path.join(HERE, "CONVERSION.csv"), index=False)
bestc = CV.loc[CV["dr2_over_level_ref"].idxmax()]
P13 = bool(float(bestc["dr2_over_level_ref"]) <= 0.002 or float(bestc["signflip_p"]) >= 0.05)
print("\n  P13 (best conversion dR2 <= +0.002 OR p >= 0.05, i.e. NO conversion): %s  "
      "[best %s at %+.6f, p %.4f]"
      % (P13, bestc["arm"], bestc["dr2_over_level_ref"], bestc["signflip_p"]))
print("  D131: these four arms produce a SUMMING minutes forecast but are defined only on a "
      "3,549-row stratum, so no team-game sum is computable.  No team-aggregate mean is "
      "reported and no team-level claim is made.")
out.update(dict(P13=P13, conversion=crows, level_ref_r2=float(r2ref)))

# ================================================================ P14  REPLICATION + GKF
print("\n" + "=" * 100)
print("S03e -- REPLICATION on a second response, and the GKF scheme")
print("=" * 100)
rep = []
for resp in ["absres_minutes", "refabs_minutes"]:
    yy = sub[resp].to_numpy(float)
    st = sst_of(yy, scored)
    vr = oof(folds, yy, X, l5c)
    vb = oof(folds, yy, X, [ix[c] for c in LADDER[best_level]])
    vc = oof(folds, yy, X, [ix[c] for c in L5 + BLOCK_N])
    v1 = oof(folds, yy, X, [ix[c] for c in L1])
    dr = (sse(yy, vr, scored) - sse(yy, vc, scored)) / st
    drb = (sse(yy, vb, scored) - sse(yy, vc, scored)) / st
    d = (yy[scored] - vr[scored]) ** 2 - (yy[scored] - vc[scored]) ** 2
    _, p, _ = signflip(d, psb[scored], 5000, SEED_NULL)
    rep.append(dict(scheme="WF", response=resp, r2_L1=1 - sse(yy, v1, scored) / st,
                    r2_bestlevel=1 - sse(yy, vb, scored) / st,
                    r2_L5=1 - sse(yy, vr, scored) / st, r2_C5=1 - sse(yy, vc, scored) / st,
                    dr2_over_L5=dr, dr2_over_bestlevel=drb, signflip_p=p))
    print("  WF  %-16s  L1 %+.6f | %s %+.6f | L5 %+.6f | C5 %+.6f | dR2 over L5 %+.6f "
          "(p %.4f), over %s %+.6f"
          % (resp, rep[-1]["r2_L1"], best_level, rep[-1]["r2_bestlevel"], rep[-1]["r2_L5"],
             rep[-1]["r2_C5"], dr, p, best_level, drb), flush=True)
gfolds = folds_gkf(sub["player_id"].to_numpy())
gs = np.sort(np.concatenate([te for _, te in gfolds]))
for resp in ["absres_minutes"]:
    yy = sub[resp].to_numpy(float)
    st = sst_of(yy, gs)
    vr = oof(gfolds, yy, X, l5c)
    vb = oof(gfolds, yy, X, [ix[c] for c in LADDER[best_level]])
    vc = oof(gfolds, yy, X, [ix[c] for c in L5 + BLOCK_N])
    v1 = oof(gfolds, yy, X, [ix[c] for c in L1])
    rep.append(dict(scheme="GKF", response=resp, r2_L1=1 - sse(yy, v1, gs) / st,
                    r2_bestlevel=1 - sse(yy, vb, gs) / st, r2_L5=1 - sse(yy, vr, gs) / st,
                    r2_C5=1 - sse(yy, vc, gs) / st,
                    dr2_over_L5=(sse(yy, vr, gs) - sse(yy, vc, gs)) / st,
                    dr2_over_bestlevel=(sse(yy, vb, gs) - sse(yy, vc, gs)) / st,
                    signflip_p=np.nan))
    print("  GKF %-16s  L1 %+.6f | %s %+.6f | L5 %+.6f | C5 %+.6f | dR2 over L5 %+.6f"
          % (resp, rep[-1]["r2_L1"], best_level, rep[-1]["r2_bestlevel"], rep[-1]["r2_L5"],
             rep[-1]["r2_C5"], rep[-1]["dr2_over_L5"]))
RP = pd.DataFrame(rep)
RP.to_csv(os.path.join(HERE, "REPLICATION.csv"), index=False)
P14 = bool(float(RP[(RP.scheme == "WF") & (RP.response == "refabs_minutes")]
                 ["dr2_over_L5"].iloc[0]) > 0)
print("\n  P14 (increment > 0 on the trailing-mean-error response): %s" % P14)
out.update(dict(P14=P14, replication=rep, best_level=best_level))

np.savez_compressed(os.path.join(RAW, "s03_worth.npz"), scored=scored, y=y, ym=ym,
                    vhat_C5=PRED["C5"], vhat_best=PRED[best_level], vhat_L1=PRED["L1"],
                    lev_ref=lev_ref, shipped=shipped, resid=resid)
json.dump(out, open(os.path.join(HERE, "scripts", "_s03.json"), "w"), indent=2, default=str)
print("\nDONE s03 (%.0fs)" % (time.time() - t0))
