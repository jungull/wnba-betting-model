"""E1_I0042 s03 -- THE PRIMARY CELLS.

Does the +1.73% replicate?  Three questions, in this order:

  1  SHARED vs FROZEN INTERCEPT on C's own decision-stratum rows.  PREREG s5's prediction, fixed
     before the numbers existed: a genuine component survives the freeze; a recalibration artefact
     does not.
  2  THE SPLIT of the one clean window into its two disjoint scored folds, 2023 and 2024.  Labelled
     PRIMARY_WINDOW_SPLIT everywhere, never "a second window".
  3  THE VACUOUS SPLIT.  Does the gain live on the rows the treatment touches?

Every cell reports n_blocks.  A cell with n_blocks < 6 is UNDECIDABLE, never a null.
Every cell is ORACLEABS -- the absence is realised, not forecast.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rr_base as R  # noqa: E402
import rr_frames as F  # noqa: E402

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 400)
R.check_prereg()

W = R.ADMISSIBLE_SCORED
f = F.load_u39()
v = F.vectors(f)
SC, DEC, TC, tg, FR = v["SCORED"], v["DECISION"], v["TC"], v["tg"], v["freed"]
finite = np.ones(len(f), bool)
for t in F.RESP:
    finite &= np.isfinite(v["y_" + t]) & np.isfinite(v["ch_" + t])
U = SC & finite
season = v["season"]

# ---------------- A/B pre-arm, rebuilt exactly as E1_I0039 (used only to price A and B)
TA = (pd.to_numeric(f["fallback_level"], errors="coerce").to_numpy(float) == 2.0)
TB = f["is_fallback"].to_numpy(bool)
nprior = pd.to_numeric(f["n_prior_games"], errors="coerce").to_numpy(float)


def build_pre(t):
    y = v["y_" + t]
    own = pd.to_numeric(f["base5_" + t], errors="coerce").to_numpy(float)
    lam = np.where(np.isfinite(own), nprior / (nprior + 2.0), 0.0)
    own0 = np.where(np.isfinite(own), own, 0.0)
    struct = np.full(len(f), np.nan)
    for s in (2022,) + tuple(W):
        tr = TB & (season < s) & (season >= 2021) & np.isfinite(y)
        te = (season == s)
        if tr.sum() < 50:
            continue
        league = float(y[tr].mean())
        dev = {}
        for col in ("depth_bucket", "draft_bucket"):
            g = f[col].to_numpy()
            d = {}
            for lev in pd.unique(g[tr]):
                if pd.isna(lev):
                    continue
                mm = tr & (g == lev)
                d[lev] = float(y[mm].mean() - league) if mm.sum() >= 20 else 0.0
            dev[col] = d
        sv = np.full(int(te.sum()), league)
        for col in ("depth_bucket", "draft_bucket"):
            g = f[col].to_numpy()[te]
            sv = sv + np.array([dev[col].get(x, 0.0) if not pd.isna(x) else 0.0 for x in g])
        struct[te] = sv
    A_hat = lam * own0 + (1.0 - lam) * struct
    B_hat = pd.to_numeric(f["e_full_" + t], errors="coerce").to_numpy(float)
    p = v["ch_" + t].copy()
    mA = TA & np.isfinite(A_hat)
    mB = TB & (~TA) & np.isfinite(B_hat)
    p[mA] = A_hat[mA]
    p[mB] = B_hat[mB]
    return p


# =====================================================================================
R.hdr("1. THE ARMS.  Gate at 25 minutes freed, exactly as published.")
# =====================================================================================
ARM = {}
for t in F.RESP:
    y = v["y_" + t]
    Cu = np.where(TC, v["u_" + t], 0.0)
    Cuz = np.where(TC, v["uz_" + t], 0.0)
    base_sh = R.wf_shared(v["ch_" + t], [], y, season, W)
    C_sh = R.wf_shared(v["ch_" + t], [Cu, Cuz], y, season, W)
    C_fz, base_fz = R.wf_frozen(v["ch_" + t], [Cu, Cuz], y, season, W)
    pre = build_pre(t)
    baseABC_sh = R.wf_shared(pre, [], y, season, W)
    ABC_sh = R.wf_shared(pre, [Cu, Cuz], y, season, W)
    ABC_fz, baseABC_fz = R.wf_frozen(pre, [Cu, Cuz], y, season, W)

    # ---- GUARD 1: the frozen base must equal the shared intercept-only base, bit for bit
    d1 = np.nanmax(np.abs(base_fz[U] - base_sh[U]))
    R.anchor("G1  %-7s frozen base == shared base (max|d|)" % t, d1, 0.0)
    # ---- GUARD 2: the frozen arm must be BIT-IDENTICAL to base off the treated rows
    off = U & ~TC
    d2 = float(np.max(np.abs(C_fz[off] - base_fz[off])))
    R.anchor("G2  %-7s frozen C == base on UNTREATED rows (max|d|)" % t, d2, 0.0)
    # ---- GUARD 3: the shared arm is NOT identical there -- if it were, there is nothing to test
    d3 = float(np.max(np.abs(C_sh[off] - base_sh[off])))
    print("  G3  %-7s shared C moves UNTREATED rows by up to %.6f minutes/points  "
          "(this is the recalibration channel)" % (t, d3))
    assert d3 > 0, "shared arm does not move untreated rows -- the comparison is vacuous"
    ARM[t] = dict(base_sh=base_sh, C_sh=C_sh, base_fz=base_fz, C_fz=C_fz,
                  baseABC_sh=baseABC_sh, ABC_sh=ABC_sh, baseABC_fz=baseABC_fz, ABC_fz=ABC_fz,
                  Cu=Cu, Cuz=Cuz, untreated_shift=d3)

# =====================================================================================
R.hdr("2. PRIMARY CELLS.  Decision stratum FIRST.  Both intercept regimes side by side.")
# =====================================================================================
STRATA = [
    ("C_TREATED_and_DECISION", lambda: U & TC & DEC),        # THE commercial population
    ("C_TREATED_all", lambda: U & TC),
    ("DECISION_all", lambda: U & DEC),
    ("POOLED", lambda: U),
    ("VACUOUS_freed_eq_0", lambda: U & (FR == 0.0)),
    ("VACUOUS_freed_0_to_25", lambda: U & (FR > 0) & (FR < 25.0)),
]
WINDOWS = [("PRIMARY_WINDOW_2023_2024", W),
           ("PRIMARY_WINDOW_SPLIT_2023", (2023,)),
           ("PRIMARY_WINDOW_SPLIT_2024", (2024,))]

rows, NPZ = [], {}
for t in F.RESP:
    y = v["y_" + t]
    A = ARM[t]
    for wname, ws in WINDOWS:
        wm = np.isin(season, np.array(ws))
        for sname, sfn in STRATA:
            m = sfn() & wm
            if m.sum() == 0:
                continue
            for arm, fa, fb in (("C_SHARED_INTERCEPT", A["C_sh"], A["base_sh"]),
                                ("C_FROZEN_INTERCEPT", A["C_fz"], A["base_fz"]),
                                ("ABC_SHARED_INTERCEPT", A["ABC_sh"], A["base_sh"]),
                                ("ABC_FROZEN_INTERCEPT", A["ABC_fz"], A["baseABC_fz"]),
                                ("AB_ONLY_baseABC_vs_base", A["baseABC_sh"], A["base_sh"])):
                keep = (sname == "C_TREATED_and_DECISION")
                r = R.cell(y, fa, fb, tg, m, "%s|%s|%s" % (arm, sname, wname), t,
                           return_draws=keep)
                if keep and "draws" in r:
                    NPZ["%s__%s__%s" % (t, arm, wname)] = r.pop("draws")
                r.update(dict(arm=arm, stratum=sname, window=wname,
                              n_treated_in_cell=int((m & TC).sum()),
                              MDE80_carried=R.mde80_carried(r["null_sd"], t),
                              verdict_vs_analytic=R.verdict(r["dMAE"],
                                                            r["MDE80_analytic"], r["n_blocks"]),
                              verdict_vs_carried=R.verdict(r["dMAE"],
                                                           R.mde80_carried(r["null_sd"], t),
                                                           r["n_blocks"])))
                rows.append(r)

P = pd.DataFrame(rows)
COLS = ["response", "window", "stratum", "arm", "n", "n_blocks", "mae_base", "mae_arm", "dMAE",
        "pct_of_MAE", "p", "null_sd", "MDE80_analytic", "MDE80_carried", "p_min_attainable",
        "max_attainable_abs_t", "six_block_floor_ok", "verdict_vs_analytic",
        "verdict_vs_carried", "n_treated_in_cell", "conditioning"]
P = P[COLS]
P.to_csv(os.path.join(R.OUT, "PRIMARY_CELLS.csv"), index=False)

R.hdr("   THE COMMERCIAL CELL: C's own decision-stratum rows, minutes")
h = P[(P.stratum == "C_TREATED_and_DECISION") & (P.response == "minutes")]
print(h.to_string(index=False))

R.hdr("   THE SAME CELL ON POINTS -- never compared to the minutes number (D101)")
hp = P[(P.stratum == "C_TREATED_and_DECISION") & (P.response == "pts")]
print(hp.to_string(index=False))

R.hdr("   THE VACUOUS SPLIT -- rows where C's own term is identically zero")
vs = P[P.stratum.isin(["VACUOUS_freed_eq_0", "VACUOUS_freed_0_to_25"])
       & P.arm.isin(["C_SHARED_INTERCEPT", "C_FROZEN_INTERCEPT"])
       & (P.window == "PRIMARY_WINDOW_2023_2024")]
print(vs.to_string(index=False))

# =====================================================================================
R.hdr("3. RECALIBRATION SHARE -- how much of each published number is not the component")
# =====================================================================================
rec = []
for t in F.RESP:
    for wname, _ in WINDOWS:
        for sname, _ in STRATA:
            a = P[(P.response == t) & (P.window == wname) & (P.stratum == sname)]
            sh = a[a.arm == "C_SHARED_INTERCEPT"]
            fz = a[a.arm == "C_FROZEN_INTERCEPT"]
            if not len(sh) or not len(fz):
                continue
            s0, f0 = float(sh.dMAE.iloc[0]), float(fz.dMAE.iloc[0])
            rec.append(dict(response=t, window=wname, stratum=sname, n=int(sh.n.iloc[0]),
                            n_blocks=int(sh.n_blocks.iloc[0]),
                            dMAE_shared=s0, dMAE_frozen=f0,
                            attributable_to_recalibration=s0 - f0,
                            pct_of_shared_that_is_recalibration=(100.0 * (s0 - f0) / s0)
                            if s0 != 0 else np.nan))
RC = pd.DataFrame(rec)
RC.to_csv(os.path.join(R.OUT, "RECALIBRATION_SHARE.csv"), index=False)
print(RC.to_string(index=False))

# =====================================================================================
R.hdr("4. WHAT A AND B ARE WORTH ON THE DECISION STRATUM, AND WHY")
# =====================================================================================
ab = P[(P.arm == "AB_ONLY_baseABC_vs_base") & (P.window == "PRIMARY_WINDOW_2023_2024")]
print(ab.to_string(index=False))
for t in F.RESP:
    A = ARM[t]
    m = U & DEC
    d = float(np.max(np.abs(A["baseABC_fz"][m] - A["base_fz"][m])))
    nz = int((np.abs(A["baseABC_fz"][m] - A["base_fz"][m]) > 0).sum())
    print("  %-7s  A/B substitute %d of %d decision-stratum rows; the ONLY difference their arm "
          "makes there is the shared intercept, max |d| = %.6f" % (t, int((m & (TA | TB)).sum()),
                                                                   int(m.sum()), d))
    print("           frozen-base rows that differ at all: %d" % nz)
    # ABC_frozen vs C_frozen, restricted to the decision stratum where A and B treat nothing
    mm = U & TC & DEC
    dd = float(np.max(np.abs(A["ABC_fz"][mm] - A["C_fz"][mm]))) if mm.sum() else np.nan
    print("           max |ABC_frozen - C_frozen| on the commercial cell: %.6e" % dd)

np.savez_compressed(os.path.join(R.OUT, "nulls", "primary_signflip_draws.npz"), **NPZ)
R.dump({"primary": P.to_dict("records"), "recalibration": RC.to_dict("records"),
        "n_npz_cells": len(NPZ)}, "_s03.json")
print("\n  wrote PRIMARY_CELLS.csv, RECALIBRATION_SHARE.csv, nulls/primary_signflip_draws.npz")
