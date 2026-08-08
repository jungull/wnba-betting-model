"""E1_I0042 s02 -- THE DECISION-STRATUM INTERSECTION FIRST, THEN THE ANCHORS.

PREREG s3 is a standing programme requirement: the decision-stratum intersection is printed and
written to disk BEFORE any effect size in this screen is computed.  s02 therefore does the counts
first, and only then reproduces A5-A16 through this screen's own code.

The run HALTS on any anchor failure.  Reading a published number out of a CSV is not an anchor.
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

# =====================================================================================
R.hdr("1. THE DECISION-STRATUM INTERSECTION -- BEFORE ANY EFFECT SIZE (PREREG s3)")
# =====================================================================================
f = F.load_u39()
v = F.vectors(f)
SC, DEC, TC = v["SCORED"], v["DECISION"], v["TC"]
tg = v["tg"]

# U = the common scored row set: every arm must be finite on it (D101 identical rows)
finite = np.ones(len(f), bool)
for t in F.RESP:
    finite &= np.isfinite(v["y_" + t]) & np.isfinite(v["ch_" + t])
U = SC & finite

rows = []


def count_row(label, seasons, m):
    sel = m & np.isin(v["season"], np.array(seasons))
    d = sel & DEC
    c = sel & TC
    cd = sel & TC & DEC
    rows.append(dict(scope=label,
                     n_rows=int(sel.sum()), n_team_games=int(pd.unique(tg[sel]).size),
                     n_decision=int(d.sum()),
                     n_C_treated=int(c.sum()),
                     n_C_treated_AND_decision=int(cd.sum()),
                     n_blocks_C_treated_AND_decision=int(pd.unique(tg[cd]).size),
                     pct_of_scope_in_decision=100.0 * d.sum() / max(sel.sum(), 1),
                     pct_of_C_treated_in_decision=100.0 * cd.sum() / max(c.sum(), 1)))


count_row("U39 pooled window 2023-2024", W, U)
for s in W:
    count_row("U39 fold %d" % s, (s,), U)
inter = pd.DataFrame(rows)
print(inter.to_string(index=False))
inter.to_csv(os.path.join(R.OUT, "DECISION_STRATUM_INTERSECTION.csv"), index=False)
print("""
  READ THIS FIRST.  The commercially relevant population is the last-but-two column: rows that
  component C actually treats AND that clear the decision stratum.  Anything measured outside it
  is not a commercial result and is not reported as one.""")

# =====================================================================================
R.hdr("2. ANCHORS A10-A12 -- E1_I0039's published counts, recomputed here")
# =====================================================================================
R.anchor("A10 |U| common scored row set", int(U.sum()), 9022)
R.anchor("A11 |DECISION| on U", int((U & DEC).sum()), 3158)
R.anchor("A12 |C-treated AND DECISION| on U", int((U & TC & DEC).sum()), 1051)

# =====================================================================================
R.hdr("3. ANCHORS A5-A9 -- E1_I0034 / D116 reproduced on E1_I0034's OWN row set (REM)")
# =====================================================================================
rem = F.load_rem()
vr = F.vectors(rem)
sel25 = np.isin(vr["season"], np.array(W)) & (vr["freed"] >= 25.0)

# P04: champion base vs champion + [u, uz], shared intercept -- E1_I0034's own construction
y = vr["y_minutes"]
M0 = R.wf_shared(vr["ch_minutes"], [], y, vr["season"], W)
M1 = R.wf_shared(vr["ch_minutes"], [vr["u_minutes"], vr["uz_minutes"]], y, vr["season"], W)
mae0 = float(np.mean(np.abs(y[sel25] - M0[sel25])))
mae1 = float(np.mean(np.abs(y[sel25] - M1[sel25])))
R.anchor("A5  E1_I0034 P04 minutes n (>=25)", int(sel25.sum()), 2475)
R.anchor("A6  E1_I0034 P04 minutes MAE(M0)", mae0, 5.101386713527127, tol=1e-9)
R.anchor("A7  E1_I0034 P04 minutes dMAE", mae0 - mae1, 0.09269264623364977, tol=1e-9)

yp = vr["y_pts"]
P0 = R.wf_shared(vr["ch_pts"], [], yp, vr["season"], W)
P1 = R.wf_shared(vr["ch_pts"], [vr["u_pts"], vr["uz_pts"]], yp, vr["season"], W)
pm0 = float(np.mean(np.abs(yp[sel25] - P0[sel25])))
pm1 = float(np.mean(np.abs(yp[sel25] - P1[sel25])))
R.anchor("A8  E1_I0034 P04 points dMAE (>=25)", pm0 - pm1, -0.048450995372577264, tol=1e-9)

# P03: the tuned trailing-5 base.  E1_I0034 s06 builds this as an ABSENCE-BLIND REGRESSION
# M0 = [1, base5, z] and M1 = M0 + [u, u*z], with min_train_season = 2021 -- NOT an offset arm and
# NOT the champion's 2022 floor, because no champion forecast enters it and the degenerate 2021
# champion fold therefore cannot poison it.  (My first draft used offset=base5, min_train=2022 and
# A9 missed by 2.03e-2: DEFECTS DEF-2.)
selall = np.isin(vr["season"], np.array(W))
b5 = pd.to_numeric(rem["base5_minutes"], errors="coerce").to_numpy(float)
zz = vr["z_minutes"] if "z_minutes" in vr else pd.to_numeric(rem["z_minutes"]).to_numpy(float)
zz = np.nan_to_num(pd.to_numeric(rem["z_minutes"], errors="coerce").to_numpy(float))
zero = np.zeros(len(rem))
T0 = R.wf_shared(zero, [b5, zz], y, vr["season"], W, min_train=2021)
T1 = R.wf_shared(zero, [b5, zz, vr["u_minutes"], vr["uz_minutes"]], y, vr["season"], W,
                 min_train=2021)
t0 = float(np.mean(np.abs(y[selall] - T0[selall])))
t1 = float(np.mean(np.abs(y[selall] - T1[selall])))
R.anchor("A9a E1_I0034 P03 minutes n (ALL)", int(selall.sum()), 8118)
R.anchor("A9  E1_I0034 P03 minutes dMAE (ALL)", t0 - t1, 0.02949664894847303, tol=1e-9)

# =====================================================================================
R.hdr("4. ANCHORS A13-A16 -- E1_I0039's C cells, recomputed here on U39")
# =====================================================================================
yU = v["y_minutes"]
C0 = R.wf_shared(v["ch_minutes"], [], yU, v["season"], W)
Cu = np.where(TC, v["u_minutes"], 0.0)
Cuz = np.where(TC, v["uz_minutes"], 0.0)
C1 = R.wf_shared(v["ch_minutes"], [Cu, Cuz], yU, v["season"], W)

m = U & TC & DEC
c13 = R.cell(yU, C1, C0, tg, m, "A13_C_on_own_decision_rows", "minutes", n_draws=2000)
R.anchor("A13 C decision-own-rows minutes dMAE", c13["dMAE"], 0.07599108674339723, tol=1e-9)
R.anchor("A13n n", c13["n"], 1051)
R.anchor("A13b n_blocks", c13["n_blocks"], 264)

# ABC needs A and B.  Built exactly as E1_I0039 stk_components.
sys.path.insert(0, os.path.join(R.SRC_STACK39, "scripts"))
TA = (pd.to_numeric(f["fallback_level"], errors="coerce").to_numpy(float) == 2.0)
TB = f["is_fallback"].to_numpy(bool)
nprior = pd.to_numeric(f["n_prior_games"], errors="coerce").to_numpy(float)
own = pd.to_numeric(f["base5_minutes"], errors="coerce").to_numpy(float)
lam = np.where(np.isfinite(own), nprior / (nprior + 2.0), 0.0)
own0 = np.where(np.isfinite(own), own, 0.0)
struct = np.full(len(f), np.nan)
for s in (2022,) + tuple(W):
    tr = TB & (v["season"] < s) & (v["season"] >= 2021) & np.isfinite(yU)
    te = (v["season"] == s)
    if tr.sum() < 50:
        continue
    league = float(yU[tr].mean())
    dev = {}
    for col in ("depth_bucket", "draft_bucket"):
        g = f[col].to_numpy()
        d = {}
        for lev in pd.unique(g[tr]):
            if pd.isna(lev):
                continue
            mm = tr & (g == lev)
            d[lev] = float(yU[mm].mean() - league) if mm.sum() >= 20 else 0.0
        dev[col] = d
    sv = np.full(int(te.sum()), league)
    for col in ("depth_bucket", "draft_bucket"):
        g = f[col].to_numpy()[te]
        sv = sv + np.array([dev[col].get(x, 0.0) if not pd.isna(x) else 0.0 for x in g])
    struct[te] = sv
A_hat = lam * own0 + (1.0 - lam) * struct
B_hat = pd.to_numeric(f["e_full_minutes"], errors="coerce").to_numpy(float)
p_abc = v["ch_minutes"].copy()
mA = TA & np.isfinite(A_hat)
mB = TB & (~TA) & np.isfinite(B_hat)
p_abc[mA] = A_hat[mA]
p_abc[mB] = B_hat[mB]
ABC = R.wf_shared(p_abc, [Cu, Cuz], yU, v["season"], W)
c14 = R.cell(yU, ABC, C0, tg, m, "A14_ABC_on_own_decision_rows", "minutes", n_draws=2000)
R.anchor("A14 ABC decision-own-rows minutes dMAE  [THE +1.73%]",
         c14["dMAE"], 0.07758861005075739, tol=1e-9)
print("       and as a percentage of base MAE: %.4f%%  (published 1.73%%)" % c14["pct_of_MAE"])

# A15/A16 -- the threshold strata, on the FULL scored set (not decision), gated arm
FR = v["freed"]
m15 = U & (FR > 0) & (FR < 25.0)
c15 = R.cell(yU, C1, C0, tg, m15, "A15_freed_0_to_25", "minutes", n_draws=2000)
R.anchor("A15 C minutes freed_0_to_25 dMAE", c15["dMAE"], -0.023018530431078568, tol=1e-9)
R.anchor("A15n n", c15["n"], 3189)

# A16 is a STRATIFICATION of the SAME gated-at-25 arm, not a re-gated arm.  E1_I0039 VERDICT.md
# s4 is explicit that these are "a stratification of the same cells, not a new one".  My first
# draft re-gated at 30 and A16 missed by 1.28e-3: DEFECTS DEF-3.  The re-gated arm is kept below
# as a labelled DIAGNOSTIC, because the difference between the two is exactly the gate question
# s05 tests.
m16 = U & (FR >= 30.0)
c16 = R.cell(yU, C1, C0, tg, m16, "A16_freed_ge_30_same_gate25_arm", "minutes", n_draws=2000)
R.anchor("A16 C minutes freed_ge_30 dMAE", c16["dMAE"], 0.144255239602443, tol=1e-9)
R.anchor("A16n n", c16["n"], 2091)

R.hdr("5. ANCHOR RECORD")
print("  16 anchors reproduced through this screen's own code before any new statistic.")
print("  A5-A9 on E1_I0034's row set, A10-A16 on E1_I0039's, A1-A4 on the champion's receipts.")

R.dump({"intersection": inter.to_dict("records"),
        "anchors_reproduced": 16,
        "A13": R.jsonable(c13), "A14": R.jsonable(c14),
        "A15": R.jsonable(c15), "A16": R.jsonable(c16)}, "_s02.json")
print("\n  wrote DECISION_STRATUM_INTERSECTION.csv, _s02.json")
