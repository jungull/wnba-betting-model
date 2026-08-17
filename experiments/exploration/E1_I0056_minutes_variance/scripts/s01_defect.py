"""S01 -- QUESTION 1.  Is the shipped per-row uncertainty a per-season constant?

Settled on the SHIPPED PREDICTION PARQUET BYTES, not on the derived analysis frame and not on a
column name (D086: a name may nominate, only a value convicts).  Then the anchors P4/P5.

Preregistered predictions tested here: P1, P2, P3, P4, P5.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _e56 import *  # noqa
from _common import ARM_MASKS, HERE, MIN_TRAIN, f, folds_wf  # noqa

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OOFD = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
TARGETS = {"minutes": "e_minutes_given_active", "pts": "player_scoring_distribution",
           "fga": "attempts_usage"}
SEASONS = [2022, 2023, 2024]
out = {}

print("=" * 100)
print("S01a -- THE SHIPPED UNCERTAINTY, ON THE PREDICTION PARQUET BYTES")
print("=" * 100)
rows = []
for tgt, key in TARGETS.items():
    for s in SEASONS:
        p = os.path.join(OOFD, "predictions__%s__%d.parquet" % (key, s))
        man = json.load(open(p + ".manifest.json"))
        assert int(man["fit_through_season"]) <= 2024, "PARTITION: %s" % p
        d = pd.read_parquet(p)
        pt = d["pred_point"].to_numpy(float)
        sd = d["pred_sd"].to_numpy(float)
        rec = dict(target=tgt, season=s, n=int(len(d)),
                   pred_sd_distinct=int(pd.Series(sd).nunique()),
                   pred_sd_value=float(sd[0]), pred_sd_ptp=float(np.ptp(sd)),
                   pred_point_distinct=int(pd.Series(pt).nunique()))
        for q in ("q05", "q25", "q50", "q75", "q95"):
            off = d["pred_" + q].to_numpy(float) - pt
            rec["off_%s_distinct" % q] = int(len(np.unique(np.round(off, 9))))
            rec["off_%s_min" % q] = float(off.min())
            rec["off_%s_max" % q] = float(off.max())
        # P3: is every q05 exactly the unclipped offset clipped at the support floor 0?
        off05 = float((d["pred_q05"].to_numpy(float) - pt).min())
        rebuilt = np.maximum(pt + off05, 0.0)
        rec["q05_clip_max_abs_dev"] = float(np.max(np.abs(d["pred_q05"].to_numpy(float) - rebuilt)))
        off95 = float((d["pred_q95"].to_numpy(float) - pt).max())
        rebuilt95 = np.minimum(pt + off95, 48.0)
        rec["q95_clip_max_abs_dev"] = float(np.max(np.abs(d["pred_q95"].to_numpy(float)
                                                          - rebuilt95)))
        rows.append(rec)
        print("  %-8s %d  n=%5d  pred_sd distinct=%d value=%.12f ptp=%.3e | "
              "off q50 distinct=%d  q75 distinct=%d  q05 distinct=%d | "
              "q05 clip dev=%.3e  q95 clip dev=%.3e"
              % (tgt, s, len(d), rec["pred_sd_distinct"], rec["pred_sd_value"],
                 rec["pred_sd_ptp"], rec["off_q50_distinct"], rec["off_q75_distinct"],
                 rec["off_q05_distinct"], rec["q05_clip_max_abs_dev"],
                 rec["q95_clip_max_abs_dev"]))
BY = pd.DataFrame(rows)
BY.to_csv(os.path.join(HERE, "SHIPPED_UNCERTAINTY.csv"), index=False)

mn = BY[BY.target == "minutes"]
P1 = bool((mn["pred_sd_distinct"] == 1).all())
P2 = bool((mn["off_q75_distinct"] == 1).all() and (mn["off_q50_distinct"] == 1).all())
P3 = bool(mn["q05_clip_max_abs_dev"].max() < 1e-9)
print("\n  P1 pred_sd 1 distinct value per season (minutes, all 3 seasons): %s" % P1)
print("  P2 q75/q50 offsets 1 distinct value per season               : %s" % P2)
print("  P3 q05 is exactly max(point + off05, 0)  max dev %.3e        : %s"
      % (mn["q05_clip_max_abs_dev"].max(), P3))
print("  ALL THREE TARGETS pred_sd distinct==1 in every season        : %s"
      % bool((BY["pred_sd_distinct"] == 1).all()))

# is the dispersion method empirical or gaussian?  a value test, not a name test.
QZ75 = 0.6744897501960817
print("\n  dispersion method, decided on values (gaussian would give off_q75 == z75*sd exactly):")
for _, r in mn.iterrows():
    print("    minutes %d  off_q75=%.9f  z75*sd=%.9f  diff=%+.9f  off_q50=%+.9f  -> %s"
          % (r["season"], r["off_q75_max"], QZ75 * r["pred_sd_value"],
             r["off_q75_max"] - QZ75 * r["pred_sd_value"], r["off_q50_max"],
             "EMPIRICAL" if abs(r["off_q75_max"] - QZ75 * r["pred_sd_value"]) > 1e-9
             else "GAUSSIAN"))
out["shipped_uncertainty"] = rows
out["P1"] = P1
out["P2"] = P2
out["P3"] = P3

# what a per-season constant sd implies for the interval it produces
print("\n  consequence: the shipped 90%% interval width q95-q05 on the decision stratum")
mask = ARM_MASKS["A4_CLEAN_DEC"]
w = (f.loc[mask, "minutes__pred_q95"].to_numpy(float)
     - f.loc[mask, "minutes__pred_q05"].to_numpy(float))
print("    n=%d  distinct widths=%d  min=%.6f  max=%.6f  sd=%.6f"
      % (len(w), len(np.unique(np.round(w, 9))), w.min(), w.max(), w.std(ddof=1)))
out["stratum_width_distinct"] = int(len(np.unique(np.round(w, 9))))
out["stratum_width_sd"] = float(w.std(ddof=1))

print("\n" + "=" * 100)
print("S01b -- ANCHORS (P4, P5).  Season-median imputation, exactly the sibling's construction.")
print("=" * 100)
sub, X, ix, meta = build("A4_CLEAN_DEC", impute="season_median")
y = sub["absres_minutes"].to_numpy(float)
folds = folds_wf(meta["gdate"], MIN_TRAIN)
scored = np.sort(np.concatenate([te for _, te in folds]))
SST = sst_of(y, scored)
print("  n=%d  folds=%d  scored=%d  SST=%.6f  mean=%.6f"
      % (len(sub), len(folds), len(scored), SST, y[scored].mean()))
assert len(sub) == 3549 and len(scored) == 2945

anch = []
for nm, cl in [("A_L1_eq_VLEV", L1), ("A_VSIG", VSIG), ("A_VSD", ["minutes__pred_sd"])]:
    vh = oof(folds, y, X, [ix[c] for c in cl])
    r2 = 1.0 - sse(y, vh, scored) / SST
    rat, lo, hi = decile_ratio(vh[scored], y[scored])
    sl, it = calib_slope(vh[scored], y[scored])
    anch.append(dict(arm=nm, n_features=len(cl), oof_r2=r2, decile_ratio=rat,
                     decile1=lo, decile10=hi, calib_slope=sl))
    print("  %-14s nf=%2d  oofR2=%+.6f  decile ratio=%.4f  slope=%+.4f"
          % (nm, len(cl), r2, rat, sl))

REF = pd.read_csv(os.path.join(os.path.dirname(HERE), "E1_I0054_absres_to_skill",
                               "CALIBRATION.csv"))
rr = REF[(REF.arm == "A4_CLEAN_DEC") & (REF.target == "minutes") & (REF.scheme == "WF")]
pub = {r["model"]: r for _, r in rr.iterrows()}
a = {r["arm"]: r for r in anch}
d4 = abs(a["A_L1_eq_VLEV"]["oof_r2"] - float(pub["VLEV"]["oof_r2_of_vhat_on_absres"]))
d5r = abs(a["A_VSIG"]["oof_r2"] - float(pub["VSIG"]["oof_r2_of_vhat_on_absres"]))
d5d = abs(a["A_VSIG"]["decile_ratio"] - float(pub["VSIG"]["top_over_bottom_decile_ratio"]))
P4 = bool(d4 < 1e-6)
P5 = bool(d5r < 1e-4 and d5d < 2e-3)
print("\n  P4 VLEV  mine %.9f  published %.9f  |diff|=%.3e  (bar 1e-6)  -> %s"
      % (a["A_L1_eq_VLEV"]["oof_r2"], float(pub["VLEV"]["oof_r2_of_vhat_on_absres"]), d4, P4))
print("  P5 VSIG  R2 mine %.9f  published %.9f  |diff|=%.3e  (bar 1e-4)"
      % (a["A_VSIG"]["oof_r2"], float(pub["VSIG"]["oof_r2_of_vhat_on_absres"]), d5r))
print("     VSIG  ratio mine %.6f published %.6f  |diff|=%.3e  (bar 2e-3)  -> %s"
      % (a["A_VSIG"]["decile_ratio"], float(pub["VSIG"]["top_over_bottom_decile_ratio"]),
         d5d, P5))
print("  incumbent A_VSD oofR2 = %+.6f  (published %+.6f)"
      % (a["A_VSD"]["oof_r2"], float(pub["VSD"]["oof_r2_of_vhat_on_absres"])))
out["anchors"] = anch
out["P4"] = P4
out["P5"] = P5
out["published"] = {k: {kk: (float(vv) if isinstance(vv, (int, float, np.floating)) else str(vv))
                        for kk, vv in dict(v).items()
                        if kk in ("oof_r2_of_vhat_on_absres", "top_over_bottom_decile_ratio",
                                  "calibration_slope", "n_scored")}
                    for k, v in pub.items()}

print("\n" + "=" * 100)
print("S01c -- T1 EXPOSURE OF THE INHERITED IMPUTATION, and the leak-free replacement")
print("=" * 100)
sub2, X2, ix2, meta2 = build("A4_CLEAN_DEC", impute="prior")
fills = {k: v for k, v in meta2["fills"].items() if v}
print("  rows imputed by the STRICTLY-PRIOR rule (primary arms):")
for k, v in sorted(fills.items(), key=lambda t: -t[1]):
    print("    %-28s %4d / %d  (%.2f%%)" % (k, v, len(sub2), 100.0 * v / len(sub2)))
mx = max([abs(X[:, ix[c]] - X2[:, ix2[c]]).max() for c in RAW_NEEDED])
print("  max |season-median  -  strictly-prior| over all candidate cells: %.6f" % mx)
out["imputation_fills_prior"] = fills
out["imputation_max_abs_diff_vs_season_median"] = float(mx)

print("\n" + "=" * 100)
print("S01d -- D131 DISCLOSURE: dispersion of the shipped minutes forecast against the "
      "200-minute budget")
print("=" * 100)
full = f[ARM_MASKS["A1_FULL"]]
g = full.groupby(["game_id", "team_id"], sort=False).agg(
    ysum=("y_minutes", "sum"), psum=("minutes__pred_point", "sum"), k=("row_uid", "size"))
for lab, col in [("realised", "ysum"), ("shipped forecast", "psum")]:
    v = g[col].to_numpy(float)
    print("  %-18s team-games=%d  MAE vs 200 = %.4f  RMSE = %.4f  within +-5 = %.2f%%  "
          "exactly 200 = %.2f%%"
          % (lab, len(v), np.abs(v - 200).mean(), np.sqrt(((v - 200) ** 2).mean()),
             100.0 * (np.abs(v - 200) <= 5).mean(), 100.0 * (np.abs(v - 200) < 1e-9).mean()))
    out["budget_%s" % col] = dict(team_games=int(len(v)), mae_vs_200=float(np.abs(v - 200).mean()),
                                  rmse_vs_200=float(np.sqrt(((v - 200) ** 2).mean())),
                                  frac_within_5=float((np.abs(v - 200) <= 5).mean()),
                                  frac_exact=float((np.abs(v - 200) < 1e-9).mean()))
print("  (mean deliberately NOT reported -- D131: a mean of 201.56 concealed an MAE of 13.09)")

json.dump(out, open(os.path.join(HERE, "scripts", "_s01.json"), "w"), indent=2, default=str)
print("\nDONE s01")
