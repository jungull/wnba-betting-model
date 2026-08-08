"""E1_I0039 s05 -- THE LATTICE.  8 arms x 2 responses x 2 strata, on ONE common row set.

D101: every number below shares the same row set, response, SST basis, weighting and base within
its (response, stratum) cell.  Nothing is compared across responses.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import stk_base as B  # noqa: E402
import stk_components as C  # noqa: E402
from stk_base import wf_arm  # noqa: E402

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 60)

spec = json.load(open(os.path.join(B.OUT, "_prereg.json"), encoding="utf-8"))
got = hashlib.sha256(open(os.path.join(B.OUT, "PREREG.md"), "rb").read()).hexdigest()
assert got == spec["sha256"], "PREREG HASH MISMATCH -- REFUSING TO RUN"
print("prereg sha256 %s  MATCH" % got)

f = C.load()
season = pd.to_numeric(f["season"]).to_numpy()
SCORED = np.isin(season, np.array(B.SCORED_W2))
tg = f["tg"].to_numpy()
RESP, ARMS = C.RESP, C.ARMS
TA = f["TA"].to_numpy(bool); TB = f["TB"].to_numpy(bool); TC = f["TC"].to_numpy(bool)
DEC = f["DECISION"].to_numpy(bool)
STRATA = {"POOLED": SCORED, "DECISION": SCORED & DEC}
print("  strata: " + "  ".join("%s n=%d" % (k, int(v.sum())) for k, v in STRATA.items()))

B.hdr("1-3. COMPONENTS")
A_hat, B_hat, Cu, Cuz, A_diag = C.build(f)
A_diag.to_csv(os.path.join(B.OUT, "component_A_walkforward_fits.csv"), index=False)

B.hdr("4. ARMS -- composition rule: A takes precedence on fallback_level==2, B covers ==3")
FC, pre_arm, arm_forecast = C.make_arms(f, A_hat, B_hat, Cu, Cuz)

# ---- ORDER CHECK: C applied to the raw champion instead of to the A/B-substituted forecast.
# Reported, not asserted to be zero.
order_rows = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    ch = pd.to_numeric(f[RESP[t]], errors="coerce").to_numpy(float)
    c_first = wf_arm(ch, [Cu[t], Cuz[t]], y, season)
    p = pre_arm(t, {"A", "B"})
    rep = TA | TB
    c_first_then_ab = np.where(rep, wf_arm(p, [], y, season), c_first)
    m = STRATA["POOLED"] & np.isfinite(FC[(t, "ABC")]) & np.isfinite(c_first_then_ab)
    order_rows.append(dict(response=t, n=int(m.sum()),
                           mae_ABC_C_last=B.mae(y[m], FC[(t, "ABC")][m]),
                           mae_ABC_C_first=B.mae(y[m], c_first_then_ab[m]),
                           delta_MAE=B.mae(y[m], c_first_then_ab[m])
                           - B.mae(y[m], FC[(t, "ABC")][m])))
pd.DataFrame(order_rows).to_csv(os.path.join(B.OUT, "order_sensitivity.csv"), index=False)
print(pd.DataFrame(order_rows).to_string(index=False))

B.hdr("5. MEASURE -- 28 preregistered cells + 8 declared sensitivity cells")
rows, NPZ = [], {}
for t in RESP:
    for sname, smask in STRATA.items():
        y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
        m = smask.copy()
        for a in ARMS + ["AB_Bwins", "ABC_Bwins"]:
            m = m & np.isfinite(FC[(t, a)])
        sst = B.sst_of(y[m])
        base = FC[(t, "base")][m]
        l_base = np.abs(y[m] - base)
        for a in ARMS + ["AB_Bwins", "ABC_Bwins"]:
            arm = FC[(t, a)][m]
            l_arm = np.abs(y[m] - arm)
            res = B.paired_signflip_block(l_arm, l_base, tg[m])
            rows.append(dict(
                cell="%s__%s__%s" % (a, t, sname), arm=a, response=t, stratum=sname,
                preregistered=(a in ARMS), n=int(m.sum()), n_blocks=res["n_blocks"],
                conditioning=("ORACLEABS" if "C" in a else "none"),
                mae_base=float(l_base.mean()), mae_arm=float(l_arm.mean()),
                dMAE=res["real"], pct_of_MAE=100.0 * res["real"] / float(l_base.mean()),
                dR2_common_sst=B.r2_common(y[m], arm, sst) - B.r2_common(y[m], base, sst),
                p=res["p"], null_mean=res["null_mean"], null_sd=res["null_sd"],
                null_mean_exceeds_observed=bool(abs(res["null_mean"]) > abs(res["real"])),
                MDE80_analytic=B.mde80_analytic(res["null_sd"]),
                MDE80_injection_D116carried=B.mde80_injection(res["null_sd"], t),
                sst_common=sst))
            if a in ARMS:
                NPZ["%s_%s_%s" % (a, t, sname)] = res["draws"]
        print("  %-8s %-9s  n=%d  base MAE %8.5f" % (t, sname, int(m.sum()), float(l_base.mean())))

lat = pd.DataFrame(rows)
lat.to_csv(os.path.join(B.OUT, "STACK_LATTICE.csv"), index=False)
np.savez_compressed(os.path.join(B.OUT, "nulls", "lattice_draws.npz"), **NPZ)

cols = ["arm", "n", "mae_base", "mae_arm", "dMAE", "pct_of_MAE", "dR2_common_sst", "p",
        "null_mean", "null_sd", "MDE80_analytic", "MDE80_injection_D116carried"]
for t in RESP:
    for sname in STRATA:
        B.hdr("LATTICE  response=%s  stratum=%s" % (t, sname))
        print(lat[(lat["response"] == t) & (lat["stratum"] == sname)][cols].to_string(index=False))

B.hdr("6. ADDITIVITY -- sum of parts over the whole, on the COMMON row set")
add = []
key = {(r["arm"], r["response"], r["stratum"]): r["dMAE"] for _, r in lat.iterrows()}
for t in RESP:
    for sname in STRATA:
        for combo in ("AB", "AC", "BC", "ABC"):
            parts = sum(key[(c, t, sname)] for c in combo)
            whole = key[(combo, t, sname)]
            best = max(key[(c, t, sname)] for c in combo)
            add.append(dict(response=t, stratum=sname, combo=combo,
                            sum_of_parts=parts, whole=whole, best_single_part=best,
                            ratio_parts_over_whole=(parts / whole if whole != 0 else np.nan),
                            whole_minus_sum=whole - parts,
                            whole_minus_best_single=whole - best))
adf = pd.DataFrame(add)
adf.to_csv(os.path.join(B.OUT, "additivity.csv"), index=False)
print(adf.to_string(index=False))
print("\n  wrote STACK_LATTICE.csv, additivity.csv, order_sensitivity.csv,")
print("        component_A_walkforward_fits.csv, nulls/lattice_draws.npz")
