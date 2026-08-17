"""S02 -- QUESTION 2.  Is minutes-level variance forecastable beyond TRAILING LEVEL?

The reference is NOT the incumbent (`minutes__pred_sd` is a per-season constant -- see s01).
Per D134 the honest reference is trailing level alone, and per T4/D087 one reference is not
enough, so a six-rung level ladder is run and the increment is reported against BOTH the D134
single-column reference and the strongest level-only reference available.

Preregistered predictions tested here: P6, P7, P8a, P8b, P9, P10, P11, P16.
All arms use the STRICTLY-PRIOR imputation.  Draw counts and seeds are those hashed in PREREG.md.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _e56 import *  # noqa
from _common import HERE, MIN_TRAIN, folds_wf, folds_gkf  # noqa

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "_screen_kit"))
import screenkit as sk  # noqa

t0 = time.time()
out = {}

sub, X, ix, meta = build("A4_CLEAN_DEC", impute="prior")
y = sub["absres_minutes"].to_numpy(float)
gd = meta["gdate"]
psb = meta["psblock"]
tgb = meta["tgblock"]
folds = folds_wf(gd, MIN_TRAIN)
scored = np.sort(np.concatenate([te for _, te in folds]))
SST = sst_of(y, scored)
NB = int(psb.max()) + 1
blocks = block_index_lists(psb, gd)
print("ARM A4_CLEAN_DEC  n=%d  scored=%d  player-seasons=%d  team-games=%d  SST=%.6f  "
      "ybar=%.6f  sd=%.6f"
      % (len(sub), len(scored), NB, int(tgb.max()) + 1, SST, y[scored].mean(),
         y[scored].std(ddof=1)), flush=True)
assert len(sub) == 3549 and len(scored) == 2945 and NB == 174

# ------------------------------------------------------------------ grouping level + acf (P16)
print("\n" + "=" * 100)
print("S02a -- WHICH NULL IS CORRECT?  grouping level and within-player-season lag-1 acf (P16)")
print("=" * 100)
dfa = pd.DataFrame({"season": meta["season"], "player_id": sub["player_id"].to_numpy(),
                    "game_id": sub["game_id"].to_numpy(), "gdate": gd})
for c in BLOCK_N:
    dfa[c] = X[:, ix[c]]
acf_rows = []
for c in BLOCK_N:
    a = sk.within_group_acf1(dfa, c, ["season", "player_id"], order_col="gdate")
    vsb = sk.var_share_between(dfa, c, "game_id")
    a1 = a["acf1"] if isinstance(a, dict) else a
    vb = vsb["var_share_between"] if isinstance(vsb, dict) else vsb
    acf_rows.append(dict(column=c,
                         acf1=float(a1) if a1 is not None else np.nan,
                         n_pairs=int(a.get("n_pairs", 0)) if isinstance(a, dict) else -1,
                         var_share_between_gameid=float(vb) if vb is not None else np.nan))
ACF = pd.DataFrame(acf_rows).sort_values("acf1", ascending=False)
ACF.to_csv(os.path.join(HERE, "NULL_LEVEL.csv"), index=False)
med_acf = float(ACF["acf1"].median())
print("  columns with an undefined acf1 (constant within every player-season): %s"
      % list(ACF.loc[~np.isfinite(ACF["acf1"]), "column"]))
P16 = bool(med_acf >= 0.20)
print(ACF.to_string(index=False))
print("\n  median within-player-season lag-1 acf over the 36 columns of N = %.4f" % med_acf)
print("  P16 (>= 0.20, so the CYCLIC variant is required rather than a plain shuffle): %s" % P16)
lvl = sk.detect_grouping_level(dfa, "pl_min_sd5", verbose=False)
print("  detect_grouping_level(pl_min_sd5): keys = %s" % sorted(lvl.keys()))
print("    status = %s  recommended = %s  coarsest_constant = %s"
      % (lvl.get("status"), lvl.get("recommended_key_cols"), lvl.get("coarsest_constant_level")))
print("    -> no level coarser than the row is constant, so a BETWEEN-group scheme does not "
      "apply; the question is answered WITHIN the player-season, cyclically (D093 / kit K2, K6).")
out["acf_median"] = med_acf
out["P16"] = P16
out["grouping_level"] = {k: str(v) for k, v in lvl.items() if k != "levels"}

# ------------------------------------------------------------------------- the ladder + arms
print("\n" + "=" * 100)
print("S02b -- THE REFERENCE LADDER AND THE CANDIDATE ARMS (WF, n scored = 2945)")
print("=" * 100)
ARMS = dict(LADDER)
ARMS["C1"] = L1 + BLOCK_N
ARMS["C5"] = L5 + BLOCK_N
ARMS["NONLY"] = list(BLOCK_N)
ARMS["C5X"] = L5 + BLOCK_N2
ARMS["VSIG"] = list(VSIG)
ARMS["VSD"] = ["minutes__pred_sd"]

PRED, ROWS = {}, []
for nm, cl in ARMS.items():
    vh = oof(folds, y, X, [ix[c] for c in cl])
    PRED[nm] = vh
    r2 = 1.0 - sse(y, vh, scored) / SST
    rat, lo, hi = decile_ratio(vh[scored], y[scored])
    sl, it = calib_slope(vh[scored], y[scored])
    ROWS.append(dict(arm=nm, n_features=len(cl), oof_r2=r2, decile_ratio=rat,
                     decile1_mean=lo, decile10_mean=hi, calib_slope=sl, calib_intercept=it,
                     spearman=spearman(vh[scored], y[scored]),
                     mean_predicted=float(vh[scored].mean()),
                     sse=sse(y, vh, scored)))
    print("  %-6s nf=%2d  oofR2=%+.6f  decile ratio=%.4f (%.3f -> %.3f)  slope=%+.4f  rho=%+.4f"
          % (nm, len(cl), r2, rat, lo, hi, sl, ROWS[-1]["spearman"]), flush=True)
LAD = pd.DataFrame(ROWS)
LAD.to_csv(os.path.join(HERE, "REFERENCE_LADDER.csv"), index=False)
R2 = {r["arm"]: r["oof_r2"] for r in ROWS}
RAT = {r["arm"]: r["decile_ratio"] for r in ROWS}

best_level = max(["L1", "L2", "L3", "L4", "L5"], key=lambda k: R2[k])
spread = max(R2[k] for k in ["L1", "L2", "L3", "L4", "L5"]) - min(
    R2[k] for k in ["L1", "L2", "L3", "L4", "L5"])
print("\n  REFERENCE SPREAD (T4): level-only OOF R2 ranges %.6f (L1=%.6f) to %.6f (%s) "
      "-- a spread of %.6f, i.e. %.2fx"
      % (min(R2[k] for k in ["L1", "L2", "L3", "L4", "L5"]), R2["L1"],
         R2[best_level], best_level, spread,
         R2[best_level] / R2["L1"] if R2["L1"] > 0 else np.nan))
P6 = bool(R2["L5"] >= 0.030)
print("  P6 (L5 level-only OOF R2 >= 0.030): %s   [L5 = %+.6f]" % (P6, R2["L5"]))

dr2_over_L5 = (sse(y, PRED["L5"], scored) - sse(y, PRED["C5"], scored)) / SST
dr2_over_L1 = (sse(y, PRED["L1"], scored) - sse(y, PRED["C1"], scored)) / SST
dr2_over_best = (sse(y, PRED[best_level], scored) - sse(y, PRED["C5"], scored)) / SST
P7 = bool(dr2_over_L5 > 0)
P8a = bool(dr2_over_L1 >= 0.015)
P8b = bool(dr2_over_L5 >= 0.010)
print("\n  PRIMARY  dR2(C5 over L5) = %+.6f    P7(>0)=%s   P8b(>=0.010)=%s"
      % (dr2_over_L5, P7, P8b))
print("  SECOND   dR2(C1 over L1) = %+.6f    P8a(>=0.015)=%s" % (dr2_over_L1, P8a))
print("  dR2(C5 over strongest level rung %s) = %+.6f" % (best_level, dr2_over_best))
print("  decile ratio: L1 %.4f -> C1 %.4f | L5 %.4f -> C5 %.4f | VSIG %.4f"
      % (RAT["L1"], RAT["C1"], RAT["L5"], RAT["C5"], RAT["VSIG"]))
out.update(dict(r2=R2, decile_ratio=RAT, best_level=best_level, level_spread=float(spread),
                dr2_over_L5=float(dr2_over_L5), dr2_over_L1=float(dr2_over_L1),
                dr2_over_best=float(dr2_over_best), P6=P6, P7=P7, P8a=P8a, P8b=P8b,
                SST=float(SST), n_scored=int(len(scored)), n_blocks=NB))

# -------------------------------------------------------------------------- CI + sign-flip
print("\n" + "=" * 100)
print("S02c -- BLOCK BOOTSTRAP CI AND THE PAIRED CLUSTER SIGN-FLIP NULL (N2)")
print("=" * 100)
BOOT = block_boot_dr2(y, PRED["L5"], PRED["C5"], scored, blocks, 2000, SEED_BOOT)
ci = (float(np.percentile(BOOT, 2.5)), float(np.percentile(BOOT, 97.5)))
print("  block bootstrap over %d player-season blocks, R=2000: dR2 CI [%+.6f, %+.6f]  "
      "median %+.6f  frac<=0 %.4f"
      % (NB, ci[0], ci[1], float(np.median(BOOT)), float((BOOT <= 0).mean())))
BOOT1 = block_boot_dr2(y, PRED["L1"], PRED["C1"], scored, blocks, 2000, SEED_BOOT)
ci1 = (float(np.percentile(BOOT1, 2.5)), float(np.percentile(BOOT1, 97.5)))
print("  (over L1)  dR2 CI [%+.6f, %+.6f]  frac<=0 %.4f" % (ci1[0], ci1[1], (BOOT1 <= 0).mean()))

d = (y[scored] - PRED["L5"][scored]) ** 2 - (y[scored] - PRED["C5"][scored]) ** 2
obs_ps, p_ps, dr_ps = signflip(d, psb[scored], 5000, SEED_NULL)
obs_tg, p_tg, dr_tg = signflip(d, tgb[scored], 5000, SEED_NULL)
print("  sign-flip, player-season clusters (%d): sum d = %+.4f  p = %.6f  z = %+.3f"
      % (NB, obs_ps, p_ps, obs_ps / dr_ps.std()))
print("  sign-flip, team-game clusters      (%d): sum d = %+.4f  p = %.6f  z = %+.3f"
      % (int(tgb[scored].max()) + 1, obs_tg, p_tg, obs_tg / dr_tg.std()))
out.update(dict(boot_ci=ci, boot_ci_over_L1=ci1, boot_frac_le0=float((BOOT <= 0).mean()),
                signflip_p_playerseason=p_ps, signflip_p_teamgame=p_tg,
                signflip_z_playerseason=float(obs_ps / dr_ps.std())))

# ------------------------------------------------------------------- cyclic / shuffle nulls
print("\n" + "=" * 100)
print("S02d -- N1 CYCLIC AND N1b SHUFFLE NULLS (R=1000 each, seed 20260817)")
print("=" * 100)
ncols = [ix[c] for c in BLOCK_N]
c5cols = [ix[c] for c in ARMS["C5"]]
sse_ref = sse(y, PRED["L5"], scored)


def null_dr2(scheme, R, seed):
    rng = np.random.default_rng(seed)
    dr = np.empty(R)
    for i in range(R):
        Z = permute_block(X, ncols, blocks, rng, scheme)
        vh = oof(folds, y, Z, c5cols)
        dr[i] = (sse_ref - sse(y, vh, scored)) / SST
        if (i + 1) % 100 == 0:
            print("    %s %4d/%d  mean %+0.6f  sd %.6f  (%.0fs)"
                  % (scheme, i + 1, R, dr[:i + 1].mean(), dr[:i + 1].std(ddof=1),
                     time.time() - t0), flush=True)
    return dr


VZ = null_dr2("zero", 50, SEED_NULL)
print("  VACUITY CONTROL (offset 0, 50 draws): sd = %.3e  distinct values = %d  "
      "max|draw - observed| = %.3e"
      % (VZ.std(ddof=1), len(np.unique(VZ)), np.max(np.abs(VZ - dr2_over_L5))))
V_OK = bool(VZ.std(ddof=1) < 1e-15 and len(np.unique(VZ)) == 1)
print("  -> the permutation machinery IS the identity when the offset is 0: %s" % V_OK)

DRC = null_dr2("cyclic", 1000, SEED_NULL)
DRS = null_dr2("shuffle", 1000, SEED_NULL)
p_cyc = float((np.sum(DRC >= dr2_over_L5) + 1) / (len(DRC) + 1))
p_shf = float((np.sum(DRS >= dr2_over_L5) + 1) / (len(DRS) + 1))
print("\n  N1  CYCLIC : mean %+.6f  sd %.6f  distinct %d  q95 %+.6f  ONE-SIDED p = %.6f"
      % (DRC.mean(), DRC.std(ddof=1), len(np.unique(DRC)), np.percentile(DRC, 95), p_cyc))
print("  N1b SHUFFLE: mean %+.6f  sd %.6f  distinct %d  q95 %+.6f  ONE-SIDED p = %.6f"
      % (DRS.mean(), DRS.std(ddof=1), len(np.unique(DRS)), np.percentile(DRS, 95), p_shf))
print("  null-width ratio sd(shuffle)/sd(cyclic) = %.4f   (D093: shuffle too NARROW -> "
      "anticonservative)" % (DRS.std(ddof=1) / DRC.std(ddof=1)))
P9 = bool(p_cyc < 0.05)
P10 = bool(p_shf <= p_cyc)
print("  P9  (cyclic p < 0.05)          : %s" % P9)
print("  P10 (p_shuffle <= p_cyclic)    : %s" % P10)
NOT_VACUOUS = bool(DRC.std(ddof=1) > 1e-6 and len(np.unique(DRC)) > 100)
print("  control is NOT vacuous (sd>1e-6 and >100 distinct draws): %s" % NOT_VACUOUS)

# ------------------------------------------------------------------------- noise control N3
print("\n" + "=" * 100)
print("S02e -- N3 NOISE CONTROL (36 iid N(0,1) columns in place of block N, R=200)")
print("=" * 100)
rng = np.random.default_rng(SEED_NULL)
l5cols = [ix[c] for c in L5]
DRN = np.empty(200)
PN = np.empty(200)
for i in range(200):
    Z = np.column_stack([X[:, l5cols], rng.standard_normal((len(y), len(BLOCK_N)))])
    vh = oof(folds, y, Z, list(range(Z.shape[1])))
    DRN[i] = (sse_ref - sse(y, vh, scored)) / SST
    dd = (y[scored] - PRED["L5"][scored]) ** 2 - (y[scored] - vh[scored]) ** 2
    PN[i] = signflip(dd, psb[scored], 500, SEED_NULL + i)[1]
    if (i + 1) % 50 == 0:
        print("    noise %3d/200  mean dR2 %+.6f  (%.0fs)"
              % (i + 1, DRN[:i + 1].mean(), time.time() - t0), flush=True)
typeI = float((PN < 0.05).mean())
P11 = bool(abs(DRN.mean()) < 0.002 and typeI <= 0.10)
print("  noise dR2: mean %+.6f  sd %.6f  min %+.6f  max %+.6f  |  Type-I at 0.05 = %.3f"
      % (DRN.mean(), DRN.std(ddof=1), DRN.min(), DRN.max(), typeI))
print("  P11 (|mean| < 0.002 and Type-I <= 0.10): %s" % P11)

out.update(dict(P9=P9, P10=P10, P11=P11, p_cyclic=p_cyc, p_shuffle=p_shf,
                null_cyclic_mean=float(DRC.mean()), null_cyclic_sd=float(DRC.std(ddof=1)),
                null_shuffle_sd=float(DRS.std(ddof=1)),
                null_width_ratio=float(DRS.std(ddof=1) / DRC.std(ddof=1)),
                vacuity_sd=float(VZ.std(ddof=1)), vacuity_is_identity=V_OK,
                control_not_vacuous=NOT_VACUOUS,
                noise_mean_dr2=float(DRN.mean()), noise_typeI=typeI))

np.savez_compressed(os.path.join(RAW, "s02_nulls.npz"), cyclic=DRC, shuffle=DRS, vacuity=VZ,
                    noise_dr2=DRN, noise_p=PN, boot=BOOT, boot_over_L1=BOOT1,
                    signflip_ps=dr_ps, signflip_tg=dr_tg, scored=scored,
                    **{"pred_" + k: v for k, v in PRED.items()},
                    y=y, psblock=psb, tgblock=tgb)
json.dump(out, open(os.path.join(HERE, "scripts", "_s02.json"), "w"), indent=2, default=str)
print("\nDONE s02 (%.0fs)" % (time.time() - t0))
