"""S03 -- PART C.  What is the conditional-variance forecast worth ON ITS OWN TERMS?

Out-of-fold predicted |residual| for each of the three targets, five variance models, two
schemes.  Reliability, decile spread, calibration slope, out-of-fold R2, all with block
bootstrap CIs over the 174 player-season blocks.

Run whatever PART S says.  This is the fallback value and nobody has measured it.

D101: response = absres_<target> on the A4_CLEAN_DEC SCORED rows; SST = about the unweighted
mean of that response on those rows; unweighted; base = intercept (the variance models carry
their own).  Nothing here is compared to a points statistic.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa
from _wf import *      # noqa

ARM = "A4_CLEAN_DEC"
mask = ARM_MASKS[ARM]
idx = np.where(mask)[0]
sub = f.iloc[idx].copy()
order = np.lexsort((sub["row_uid"].to_numpy(), sub["gdate"].to_numpy()))
idx = idx[order]
sub = f.iloc[idx].reset_index(drop=True)
XA = X[idx, :]                                  # raw-scale, median-imputed candidate matrix
gdate = sub["gdate"].to_numpy()
pid = sub["player_id"].to_numpy()
psblock = pd.factorize(pd.Series(list(zip(sub["season"], sub["player_id"]))))[0]
NB = psblock.max() + 1
m = len(sub)
print("ARM %s  n=%d  player-season blocks=%d  dates=%d"
      % (ARM, m, NB, len(np.unique(gdate))), flush=True)
assert m == 3549 and NB == 174

s01 = json.load(open(os.path.join(HERE, "scripts", "_s01.json")))
THE16 = s01["sets"][str(SEEDS[0])]
assert len(THE16) == 16

# feature sets, formed NUMERICALLY from the reproduced 16 (no substring selection of names:
# the dependent field of each surviving cell decides which target it informs)
VSIG_FEATS = {}
for tgt in ("pts", "minutes", "fga"):
    fe = sorted({c.split("|")[0] for c in THE16 if c.split("|")[1].split("_")[0] == tgt})
    VSIG_FEATS[tgt] = fe
    print("  VSIG[%s] = %s" % (tgt, fe))

LAM_GRID = [10.0 ** e for e in range(-3, 4)]
MODELS = ["V0", "VSD", "VSIG", "VALL", "VLEV"]


def feats_for(model, tgt):
    if model == "V0":
        return []
    if model == "VSD":
        return ["%s__pred_sd" % tgt]
    if model == "VSIG":
        return VSIG_FEATS[tgt]
    if model == "VALL":
        return list(names)
    if model == "VLEV":
        return [MATCHED_LEVEL[tgt]]
    raise KeyError(model)


def run_scheme(folds, y, cols):
    """out-of-fold prediction; cols = list of candidate-matrix column indices."""
    out = np.full(len(y), np.nan)
    for tr, te in folds:
        if len(cols) == 0:
            out[te] = y[tr].mean()
            continue
        Xt = XA[np.ix_(tr, cols)]
        lam = tune_lambda(Xt, y[tr], LAM_GRID) if len(cols) > 3 else 0.0
        a, b = ridge_fit(Xt, y[tr], lam)
        out[te] = a + XA[np.ix_(te, cols)] @ b
    return out


FOLDS = {"WF": folds_wf(gdate, MIN_TRAIN), "GKF": folds_gkf(pid)}
print("  WF folds %d (scored rows %d) | GKF folds %d"
      % (len(FOLDS["WF"]), sum(len(t) for _, t in FOLDS["WF"]), len(FOLDS["GKF"])), flush=True)

t0 = time.time()
rows, dec_rows, store = [], [], {}
rng_boot = np.random.default_rng(20260808)
BOOT = np.stack([rng_boot.integers(0, NB, NB) for _ in range(2000)])
blk_rows = [np.where(psblock == b)[0] for b in range(NB)]

for tgt in ("pts", "minutes", "fga"):
    y = sub["absres_%s" % tgt].to_numpy(float)
    for scheme, folds in FOLDS.items():
        scored = np.concatenate([te for _, te in folds])
        scored = np.sort(scored)
        for model in MODELS:
            cols = [NAME_IX[c] for c in feats_for(model, tgt)]
            vh = run_scheme(folds, y, cols)
            s = scored[np.isfinite(vh[scored])]
            v, r = vh[s], y[s]
            store["%s__%s__%s" % (tgt, scheme, model)] = np.column_stack([s.astype(float), v, r])
            dt = decile_table(v, r)
            dt.insert(0, "model", model); dt.insert(0, "scheme", scheme)
            dt.insert(0, "target", tgt); dt.insert(0, "arm", ARM)
            dec_rows.append(dt)
            lo, hi = dt["mean_realised"].iloc[0], dt["mean_realised"].iloc[-1]
            slope = np.nan; inter = np.nan
            if v.std() > 1e-12:
                A = np.column_stack([np.ones(len(v)), v])
                inter, slope = np.linalg.lstsq(A, r, rcond=None)[0]
            # block bootstrap on the two headline quantities
            bs_ratio, bs_r2 = [], []
            for bi in range(len(BOOT)):
                take = np.concatenate([blk_rows[b] for b in BOOT[bi]])
                take = take[np.isin(take, s)]
                if len(take) < 100:
                    continue
                vv = vh[take]; rr = y[take]
                q = pd.Series(vv).rank(method="first", pct=True).to_numpy()
                lo_m, hi_m = q <= 0.1, q > 0.9
                if lo_m.sum() < 5 or hi_m.sum() < 5:
                    continue
                a_ = rr[lo_m].mean()
                bs_ratio.append(rr[hi_m].mean() / a_ if a_ > 0 else np.nan)
                bs_r2.append(r2_oof(rr, vv))
            bs_ratio = np.array([x for x in bs_ratio if np.isfinite(x)])
            bs_r2 = np.array([x for x in bs_r2 if np.isfinite(x)])
            rows.append(dict(
                arm=ARM, target=tgt, response="absres_%s" % tgt, scheme=scheme, model=model,
                features=";".join(feats_for(model, tgt)), n_features=len(cols),
                n_scored=int(len(s)), n_blocks=NB,
                mean_realised=float(r.mean()), sd_realised=float(r.std(ddof=1)),
                decile1_mean_realised=float(lo), decile10_mean_realised=float(hi),
                top_minus_bottom_decile_spread=float(hi - lo),
                top_over_bottom_decile_ratio=float(hi / lo) if lo > 0 else np.nan,
                ratio_boot_lo=float(np.percentile(bs_ratio, 2.5)) if len(bs_ratio) else np.nan,
                ratio_boot_hi=float(np.percentile(bs_ratio, 97.5)) if len(bs_ratio) else np.nan,
                spearman_vhat_vs_realised=spearman(v, r),
                calibration_slope=float(slope), calibration_intercept=float(inter),
                oof_r2_of_vhat_on_absres=r2_oof(r, v),
                r2_boot_lo=float(np.percentile(bs_r2, 2.5)) if len(bs_r2) else np.nan,
                r2_boot_hi=float(np.percentile(bs_r2, 97.5)) if len(bs_r2) else np.nan,
                mean_abs_calibration_error=float(np.mean(np.abs(r - v))),
                mean_predicted=float(v.mean()),
                n_boot_used=int(len(bs_r2))))
            print("  %-8s %-4s %-5s  n=%4d  dec1 %.3f dec10 %.3f ratio %.3f  rho %.3f  "
                  "oofR2 %+.4f  slope %.3f  (%.0fs)"
                  % (tgt, scheme, model, len(s), lo, hi, hi / lo if lo > 0 else np.nan,
                     rows[-1]["spearman_vhat_vs_realised"], rows[-1]["oof_r2_of_vhat_on_absres"],
                     slope, time.time() - t0), flush=True)

CAL = pd.DataFrame(rows)
CAL.to_csv(os.path.join(HERE, "CALIBRATION.csv"), index=False)
DEC = pd.concat(dec_rows, ignore_index=True)
DEC.to_csv(os.path.join(HERE, "CALIBRATION_DECILES.csv"), index=False)
np.savez_compressed(os.path.join(RAW, "calibration_oof.npz"),
                    arm=np.array([ARM]), n=np.array([m]),
                    row_uid=sub["row_uid"].to_numpy().astype(str),
                    season=sub["season"].to_numpy(), player_id=pid,
                    gdate=sub["gdate"].to_numpy().astype("datetime64[D]").astype(int),
                    player_season_block=psblock, **store)
print("\nwrote CALIBRATION.csv %s and CALIBRATION_DECILES.csv %s" % (CAL.shape, DEC.shape))

# --- the WF/VSIG line for each target, which is the headline of PART C
print("\n=== headline (WF scheme) ===")
print(CAL[CAL.scheme == "WF"][["target", "model", "n_scored", "decile1_mean_realised",
                               "decile10_mean_realised", "top_over_bottom_decile_ratio",
                               "ratio_boot_lo", "ratio_boot_hi", "spearman_vhat_vs_realised",
                               "oof_r2_of_vhat_on_absres", "calibration_slope"]]
      .round(4).to_string(index=False))
json.dump(dict(vsig_features=VSIG_FEATS,
               n_scored_wf=int(CAL[(CAL.scheme == "WF")]["n_scored"].max()),
               n_scored_gkf=int(CAL[(CAL.scheme == "GKF")]["n_scored"].max())),
          open(os.path.join(HERE, "scripts", "_s03.json"), "w"), indent=2)
print("DONE s03 (%.0fs)" % (time.time() - t0))
