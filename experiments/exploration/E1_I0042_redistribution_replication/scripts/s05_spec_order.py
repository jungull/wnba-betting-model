"""E1_I0042 s05 -- CLAIM 2 (allocate evenly) and PREREG s8 (does order or specification matter).

Every row of every table below is measured on the SAME row set -- C's own decision-stratum rows,
n = 1051 -- with the SAME response, the SAME base and the SAME weighting.  D101 is satisfied by
construction: only the ARM changes.  Frozen intercept throughout, because s03 established that the
shared intercept moves rows the component does not treat.
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

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
R.check_prereg()

W = R.ADMISSIBLE_SCORED
f = F.load_u39()
v = F.vectors(f)
SC, DEC, TC, tg, FR, season = v["SCORED"], v["DECISION"], v["TC"], v["tg"], v["freed"], v["season"]
EST = v["established"]
y = v["y_minutes"]
ch = v["ch_minutes"]
U = SC & np.isfinite(y) & np.isfinite(ch)
CELL = U & TC & DEC                        # THE commercial population, held fixed
print("  the fixed row set for this whole step: n = %d in %d team-game blocks"
      % (int(CELL.sum()), int(pd.unique(tg[CELL]).size)))

# =====================================================================================
R.hdr("1. THE THREE ALLOCATIONS OF THE SAME FREED VOLUME (CLAIM 2)")
# =====================================================================================
# EVEN          u_i        = freed / n_rem                       (the published prescription)
# TILTED        u_i, u_i*z_i                                     (the published specification)
# PROPORTIONAL  u_prop_i   = freed * base5_i / sum_rem(base5)    (allocate in proportion to role)
b5 = pd.to_numeric(f["base5_minutes"], errors="coerce").to_numpy(float)
b5e = np.where(EST & np.isfinite(b5), b5, 0.0)
sb5 = pd.Series(b5e).groupby(pd.Series(tg)).transform("sum").to_numpy(float)
u_prop = np.where((sb5 > 0) & EST, FR * b5e / np.maximum(sb5, 1e-9), 0.0)
u_even = np.where(EST, v["u_minutes"], 0.0)
uz = np.where(EST, v["uz_minutes"], 0.0)
# gate them all identically at the published 25 so ONLY the allocation shape differs
GATE = (FR >= 25.0) & EST
u_even_g = np.where(GATE, u_even, 0.0)
uz_g = np.where(GATE, uz, 0.0)
u_prop_g = np.where(GATE, u_prop, 0.0)
print("  allocation totals per treated team-game agree: max |sum(even) - sum(prop)| = %.3e"
      % float(np.abs(pd.Series(u_even_g).groupby(pd.Series(tg)).sum()
                     - pd.Series(u_prop_g).groupby(pd.Series(tg)).sum()).max()))

SPECS = [
    ("EVEN_u_only", [u_even_g], "u = freed / n_rem"),
    ("TILTED_u_and_uz", [u_even_g, uz_g], "published: u + u*z"),
    ("PROPORTIONAL_to_base5", [u_prop_g], "u_prop = freed * base5 / sum_rem(base5)"),
    ("PROPORTIONAL_plus_tilt", [u_prop_g, uz_g], "u_prop + u*z"),
]
rows = []
for name, X, desc in SPECS:
    fz, bz = R.wf_frozen(ch, X, y, season, W)
    r = R.cell(y, fz, bz, tg, CELL, name, "minutes", n_draws=8000)
    rows.append(dict(allocation=name, description=desc, n=r["n"], n_blocks=r["n_blocks"],
                     dMAE=r["dMAE"], pct_of_MAE=r["pct_of_MAE"], p=r["p"], null_sd=r["null_sd"],
                     MDE80_analytic=r["MDE80_analytic"],
                     MDE80_carried=R.mde80_carried(r["null_sd"], "minutes"),
                     verdict=R.verdict(r["dMAE"], r["MDE80_analytic"], r["n_blocks"])))
AL = pd.DataFrame(rows)
print(AL.to_string(index=False))
AL.to_csv(os.path.join(R.OUT, "ALLOCATION.csv"), index=False)
even = float(AL[AL.allocation == "EVEN_u_only"].dMAE.iloc[0])
floor = float(AL[AL.allocation == "EVEN_u_only"].MDE80_analytic.iloc[0])
beat = AL[AL.dMAE > even + floor]
print("\n  EVEN = %+.5f.  Allocations beating it by MORE than EVEN's own floor (%.5f): %d"
      % (even, floor, len(beat)))
print("  CLAIM 2 verdict: %s"
      % ("EVEN NOT BEATEN -- upheld as the best available prescription" if len(beat) == 0
         else "EVEN BEATEN by %s" % list(beat.allocation)))

# =====================================================================================
R.hdr("2. ORDER -- C applied to the raw champion vs to the A/B-substituted forecast")
# =====================================================================================
TA = (pd.to_numeric(f["fallback_level"], errors="coerce").to_numpy(float) == 2.0)
TB = f["is_fallback"].to_numpy(bool)
nprior = pd.to_numeric(f["n_prior_games"], errors="coerce").to_numpy(float)
lam = np.where(np.isfinite(b5), nprior / (nprior + 2.0), 0.0)
own0 = np.where(np.isfinite(b5), b5, 0.0)
struct = np.full(len(f), np.nan)
for s in (2022,) + tuple(W):
    tr = TB & (season < s) & (season >= 2021) & np.isfinite(y)
    te = (season == s)
    if tr.sum() < 50:
        continue
    league = float(y[tr].mean())
    dev = {}
    for col in ("depth_bucket", "draft_bucket"):
        gg = f[col].to_numpy()
        dd = {}
        for lev in pd.unique(gg[tr]):
            if pd.isna(lev):
                continue
            mm = tr & (gg == lev)
            dd[lev] = float(y[mm].mean() - league) if mm.sum() >= 20 else 0.0
        dev[col] = dd
    sv = np.full(int(te.sum()), league)
    for col in ("depth_bucket", "draft_bucket"):
        gg = f[col].to_numpy()[te]
        sv = sv + np.array([dev[col].get(x, 0.0) if not pd.isna(x) else 0.0 for x in gg])
    struct[te] = sv
A_hat = lam * own0 + (1.0 - lam) * struct
B_hat = pd.to_numeric(f["e_full_minutes"], errors="coerce").to_numpy(float)
pre = ch.copy()
mA = TA & np.isfinite(A_hat)
mB = TB & (~TA) & np.isfinite(B_hat)
pre[mA] = A_hat[mA]
pre[mB] = B_hat[mB]
print("  A/B substitute %d rows in U, of which %d are in the commercial cell"
      % (int(((mA | mB) & U).sum()), int(((mA | mB) & CELL).sum())))

ords = []
for name, off in (("C_on_RAW_CHAMPION", ch), ("C_on_AB_SUBSTITUTED", pre)):
    fz, bz = R.wf_frozen(off, [u_even_g, uz_g], y, season, W)
    r = R.cell(y, fz, bz, tg, CELL, name, "minutes", n_draws=8000)
    ords.append(dict(order=name, n=r["n"], n_blocks=r["n_blocks"], dMAE=r["dMAE"],
                     pct_of_MAE=r["pct_of_MAE"], p=r["p"], null_sd=r["null_sd"],
                     MDE80_analytic=r["MDE80_analytic"]))
OD = pd.DataFrame(ords)
print(OD.to_string(index=False))
OD.to_csv(os.path.join(R.OUT, "ORDER_SENSITIVITY.csv"), index=False)
spread = float(OD.dMAE.max() - OD.dMAE.min())
print("\n  order spread = %.5f = %.1f%% of the effect.  E1_I0039 measured 19-22%% for the STACK;"
      % (spread, 100.0 * spread / OD.dMAE.max()))
print("  C ALONE is %s to order." % ("INSENSITIVE" if spread < 0.1 * OD.dMAE.max()
                                     else "SENSITIVE"))

# =====================================================================================
R.hdr("3. FRAME -- the same cell rebuilt on E1_I0034's own remaining-player frame")
# =====================================================================================
rem = F.load_rem()
vr = F.vectors(rem)
yr, chr_ = vr["y_minutes"], vr["ch_minutes"]
Ur = np.isin(vr["season"], np.array(W)) & np.isfinite(yr) & np.isfinite(chr_)
DECr = ((pd.to_numeric(rem["n_prior_games"], errors="coerce").to_numpy(float) >= 8)
        & (pd.to_numeric(rem["base5_minutes"], errors="coerce").to_numpy(float) >= 24))
TCr = (vr["freed"] >= 25.0) & vr["established"]
CELLr = Ur & TCr & DECr
gur = np.where(TCr, vr["u_minutes"], 0.0)
gzr = np.where(TCr, vr["uz_minutes"], 0.0)
fzr, bzr = R.wf_frozen(chr_, [gur, gzr], yr, vr["season"], W)
shr = R.wf_shared(chr_, [gur, gzr], yr, vr["season"], W)
bshr = R.wf_shared(chr_, [], yr, vr["season"], W)
fr_rows = []
for nm, fa, fb in (("REM_FROZEN", fzr, bzr), ("REM_SHARED", shr, bshr)):
    r = R.cell(yr, fa, fb, vr["tg"], CELLr, nm, "minutes", n_draws=8000)
    fr_rows.append(dict(frame="REM_E1_I0034", arm=nm, n=r["n"], n_blocks=r["n_blocks"],
                        dMAE=r["dMAE"], pct_of_MAE=r["pct_of_MAE"], p=r["p"],
                        null_sd=r["null_sd"], MDE80_analytic=r["MDE80_analytic"],
                        verdict=R.verdict(r["dMAE"], r["MDE80_analytic"], r["n_blocks"])))
FRM = pd.DataFrame(fr_rows)
print(FRM.to_string(index=False))
FRM.to_csv(os.path.join(R.OUT, "FRAME_CHECK.csv"), index=False)

# =====================================================================================
R.hdr("4. THE FULL SPECIFICATION SPREAD AGAINST THE HEADLINE")
# =====================================================================================
P = pd.read_csv(os.path.join(R.OUT, "PRIMARY_CELLS.csv"))
G = pd.read_csv(os.path.join(R.OUT, "GATE_SWEEP.csv"))
head = float(P[(P.response == "minutes") & (P.stratum == "C_TREATED_and_DECISION")
               & (P.window == "PRIMARY_WINDOW_2023_2024")
               & (P.arm == "C_FROZEN_INTERCEPT")].dMAE.iloc[0])
lat = []
lat.append(("headline C frozen, gate 25, U39, pooled window", head))
for _, r in AL.iterrows():
    lat.append(("allocation: " + r.allocation, float(r.dMAE)))
for _, r in OD.iterrows():
    lat.append(("order: " + r.order, float(r.dMAE)))
for _, r in FRM.iterrows():
    lat.append(("frame: " + r.arm, float(r.dMAE)))
for _, r in P[(P.response == "minutes") & (P.stratum == "C_TREATED_and_DECISION")
              & (P.arm.isin(["C_SHARED_INTERCEPT", "C_FROZEN_INTERCEPT"]))].iterrows():
    lat.append(("%s / %s" % (r.window, r.arm), float(r.dMAE)))
L = pd.DataFrame(lat, columns=["variant", "dMAE"])
L["pct_of_headline"] = 100.0 * L.dMAE / head
L["deviation_from_headline"] = L.dMAE - head
print(L.to_string(index=False))
L.to_csv(os.path.join(R.OUT, "SPEC_LATTICE.csv"), index=False)
sp = float(L.dMAE.max() - L.dMAE.min())
print("\n  SPEC SPREAD %.5f against a headline of %.5f  =  %.0f%% of the headline."
      % (sp, head, 100.0 * sp / head))
print("  PREREG s8: spread exceeding the headline => SPECIFICATION-DEPENDENT.  %s"
      % ("SPECIFICATION-DEPENDENT" if sp > head else "not specification-dependent"))
print("  Every variant in the lattice has the SAME SIGN: %s"
      % bool((L.dMAE > 0).all()))

R.dump({"allocation": AL.to_dict("records"), "order": OD.to_dict("records"),
        "frame": FRM.to_dict("records"), "lattice": L.to_dict("records"),
        "spec_spread": sp, "headline": head}, "_s05.json")
print("\n  wrote ALLOCATION.csv, ORDER_SENSITIVITY.csv, FRAME_CHECK.csv, SPEC_LATTICE.csv")
