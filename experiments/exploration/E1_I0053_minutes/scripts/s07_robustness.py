"""s07 -- ROBUSTNESS OF THE ONLY SURVIVOR, run because it is the check most likely to kill it.

C1_player_rest is clipped at 21 days and its decision-stratum median is 2.  If the whole effect
lives in a thin tail of long absences, the cell is a handful of rows wearing a p-value.  Every
variant below is a DIFFERENT CELL with its own null, not a reweighting of the published one.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s07 ROBUSTNESS   PREREG sha256 %s" % A.prereg_sha())
d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "cached frame", verbose=True)
Z = np.load(os.path.join(A.SCR, "_base.npz"), allow_pickle=True)
season = d["season"].to_numpy()
dm = A.decision_mask(d)
clean = np.isin(season, A.CLEAN_EVAL_SEASONS)
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg).astype(float)
T_min_tg = np.bincount(tg_code, weights=d["T_min"].to_numpy(float), minlength=n_tg) / counts
y = d["R1_min"].to_numpy(float)
b = Z["R1_min|RAW"]
SW_TG = A.WithinTeamGameSwap(d)
SW_PS = A.PlayerSeriesSwap(d)
x = d["C1_player_rest"].to_numpy(float)

A.hdr("0. HOW MANY ROWS CARRY THE TAIL?  DECISION stratum, clean window")
m = dm & clean
for lo, hi in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 6), (6, 8), (8, 22)]:
    sel = m & (x >= lo) & (x < hi)
    print("  rest in [%2d,%2d)  n=%5d (%5.2f%% of 3,167)   mean minutes %6.3f"
          % (lo, hi, sel.sum(), 100 * sel.sum() / m.sum(), y[sel].mean() if sel.sum() else np.nan))
print("  imputed-to-mean rows inside the decision stratum: %d"
      % int((~np.isfinite(pd.to_numeric(
          (d["game_date"] - d["prev_appear_date"]).dt.days, errors="coerce").to_numpy(float)))[m].sum()))


def cell(vals, arm="FROZEN", mask_extra=None):
    sc = dm if mask_extra is None else (dm & mask_extra)
    return A.Cell(d, y, b, "ROB", vals, dm, sc, A.CLEAN_EVAL_SEASONS, arm, "RAW",
                  proj_totals=T_min_tg)


VARIANTS = [
    ("V0_published_clip21", np.clip(x, None, 21.0), None),
    ("V1_clip_at_7", np.clip(x, None, 7.0), None),
    ("V2_clip_at_4", np.clip(x, None, 4.0), None),
    ("V3_log1p", np.log1p(x), None),
    ("V4_binary_rest_ge_4", (x >= 4.0).astype(float), None),
    ("V5_binary_rest_ge_8", (x >= 8.0).astype(float), None),
    ("V6_drop_rows_rest_gt_7", np.clip(x, None, 21.0), (x <= 7.0)),
    ("V7_drop_rows_rest_gt_4", np.clip(x, None, 21.0), (x <= 4.0)),
]
rows = []
for name, vals, extra in VARIANTS:
    for arm in ["FROZEN", "UNFROZEN"]:
        c = cell(vals, arm, extra)
        full = c.full()
        r1 = A.run_null_family({name: c}, SW_TG, A.N_DRAWS, A.SEED, "ROB|N_TGSWAP")[name]
        r2 = A.run_null_family({name: c}, SW_PS, 600, A.SEED, "ROB|N_PSWAP")[name]
        rows.append(dict(variant=name, arm=arm, n=full["n"], dR2=full["dr2"], beta=full["beta"],
                         r2_base=full["r2_base"],
                         z_TGSWAP=r1["z"], p_TGSWAP=r1["p"], null_sd_TGSWAP=r1["null_sd"],
                         z_PSWAP=r2["z"], p_PSWAP=r2["p"],
                         MDE80_analytic=2.80 * r1["null_sd"]))
        A.save_null("ROBUST__R1_min__RAW__%s__%s__N_TGSWAP" % (arm, name), r1,
                    dict(variant=np.array([name]), arm=np.array([arm]),
                         n_rows=np.array([full["n"]])))
        print("  %-24s %-8s n=%5d  dR2 %+10.6f  TGSWAP z %+7.2f p %.4f | PSWAP z %+7.2f p %.4f"
              % (name, arm, full["n"], full["dr2"], r1["z"], r1["p"], r2["z"], r2["p"]))
R = pd.DataFrame(rows)
R.to_csv(os.path.join(A.OUT, "ROBUSTNESS.csv"), index=False)

A.hdr("2. SHAPE: mean base residual by rest bucket (is it monotone, or is it a spike?)")
c0 = cell(np.zeros(len(d)), "FROZEN")
f0 = c0.full()
resid = f0["y"] - f0["yb"]
xr = x[f0["idx"]]
sh = []
for lo, hi in [(0, 2), (2, 3), (3, 4), (4, 6), (6, 8), (8, 12), (12, 22)]:
    sel = (xr >= lo) & (xr < hi)
    sh.append(dict(rest_lo=lo, rest_hi=hi, n=int(sel.sum()),
                   mean_base_residual_minutes=float(resid[sel].mean()) if sel.sum() else np.nan,
                   se=float(resid[sel].std(ddof=1) / np.sqrt(sel.sum())) if sel.sum() > 1 else np.nan))
    print("  rest [%2d,%2d)  n=%5d  mean base residual %+7.3f min  (se %.3f)"
          % (lo, hi, sh[-1]["n"], sh[-1]["mean_base_residual_minutes"], sh[-1]["se"]))
pd.DataFrame(sh).to_csv(os.path.join(A.OUT, "REST_SHAPE.csv"), index=False)

A.dump("s07", dict(prereg_sha=A.prereg_sha(), variants=rows, shape=sh))
A.hdr("s07 done")
