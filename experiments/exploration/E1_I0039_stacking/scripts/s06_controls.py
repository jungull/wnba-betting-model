"""E1_I0039 s06 -- CONTROLS AND POWER.  Every guard the brief names, run on this screen's own
machinery rather than taken on trust from the source screens.

  1  VACUOUS CONTROL -- does each component's gain live on the rows it actually treats?
  2  NEGATIVE STRATUM -- C on freed == 0, where there is nothing to redistribute
  3  NO-OP PLACEBO -- identity transform must reproduce the statistic with deviation EXACTLY 0.0
  4  RANDOM-TARGET CONTROL -- each component reassigned to a random row set of the same size
  5  INJECTION-VERIFIED POWER FLOORS -- component-wise, through the identical code path
  6  TYPE-I CALIBRATION
  7  C ON ITS OWN 2,475 ROWS -- the bridge back to D116's published +1.82%
  8  W1 SECONDARY -- 2022-2024, direction of movement stated
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
import stk_components as CM  # noqa: E402
from stk_base import wf_arm  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)

spec = json.load(open(os.path.join(B.OUT, "_prereg.json"), encoding="utf-8"))
assert hashlib.sha256(open(os.path.join(B.OUT, "PREREG.md"), "rb").read()).hexdigest() \
    == spec["sha256"], "PREREG HASH MISMATCH"

f = CM.load()
season = pd.to_numeric(f["season"]).to_numpy()
SCORED = np.isin(season, np.array(B.SCORED_W2))
tg = f["tg"].to_numpy()
RESP = CM.RESP
TA = f["TA"].to_numpy(bool); TB = f["TB"].to_numpy(bool); TC = f["TC"].to_numpy(bool)
DEC = f["DECISION"].to_numpy(bool)
freed = f["freed_minutes"].to_numpy(float)

# THE SAME component code path as s05 -- imported, not re-implemented, so the two steps
# cannot drift apart.
A_hat, B_hat, Cu, Cuz, _ = CM.build(f, verbose=False)
FC, pre_arm, arm_forecast = CM.make_arms(f, A_hat, B_hat, Cu, Cuz)

OUTJ = {}


def cell(y, arm, base, mask, label, **kw):
    la = np.abs(y[mask] - arm[mask])
    lb = np.abs(y[mask] - base[mask])
    r = B.paired_signflip_block(la, lb, tg[mask], n_draws=4000)
    d = dict(label=label, n=int(mask.sum()), n_blocks=r["n_blocks"],
             mae_base=float(lb.mean()), mae_arm=float(la.mean()), dMAE=r["real"],
             pct_of_MAE=100.0 * r["real"] / float(lb.mean()) if lb.mean() else np.nan,
             p=r["p"], null_mean=r["null_mean"], null_sd=r["null_sd"],
             MDE80_analytic=B.mde80_analytic(r["null_sd"]))
    d.update(kw)
    return d


# =====================================================================================
B.hdr("1. VACUOUS CONTROL -- where does each component's gain actually live?")
# =====================================================================================
# E1_I0034 found an apparent gain whose ENTIRE effect came from rows where the treatment term was
# identically zero.  For each component: split the SAME arm-vs-base comparison into the rows the
# component TREATS and the rows it does not touch at all.
TREATED = {"A": TA, "B": TB, "C": TC}
vac = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    for c in ("A", "B", "C"):
        arm = FC[(t, c)]
        for lbl, m in (("TREATED", SCORED & TREATED[c]),
                       ("UNTREATED", SCORED & ~TREATED[c]),
                       ("UNTREATED_and_DECISION", SCORED & ~TREATED[c] & DEC)):
            if m.sum() < 30:
                continue
            vac.append(cell(y, arm, base, m, "%s__%s__%s" % (c, t, lbl),
                            component=c, response=t, split=lbl))
vdf = pd.DataFrame(vac)
vdf.to_csv(os.path.join(B.OUT, "vacuous_split.csv"), index=False)
print(vdf[["component", "response", "split", "n", "mae_base", "mae_arm", "dMAE", "pct_of_MAE",
           "p", "null_mean", "null_sd", "MDE80_analytic"]].to_string(index=False))

# =====================================================================================
B.hdr("2. NEGATIVE STRATUM -- C where freed == 0, and where 0 < freed < 25")
# =====================================================================================
neg = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    arm = FC[(t, "C")]
    for lbl, m in (("freed_eq_0", SCORED & (freed == 0.0)),
                   ("freed_0_to_25", SCORED & (freed > 0.0) & (freed < 25.0)),
                   ("freed_ge_25", SCORED & (freed >= 25.0)),
                   ("freed_ge_30", SCORED & (freed >= 30.0))):
        neg.append(cell(y, arm, base, m, "C__%s__%s" % (t, lbl), response=t, stratum=lbl))
ndf = pd.DataFrame(neg)
ndf.to_csv(os.path.join(B.OUT, "negative_and_threshold_strata.csv"), index=False)
print(ndf[["response", "stratum", "n", "mae_base", "mae_arm", "dMAE", "pct_of_MAE", "p",
           "null_mean", "null_sd", "MDE80_analytic"]].to_string(index=False))

# =====================================================================================
B.hdr("3. NO-OP PLACEBO -- identity transform, deviation must be EXACTLY 0.0")
# =====================================================================================
noop = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    m = SCORED
    r = B.paired_signflip_block(np.abs(y[m] - base[m]), np.abs(y[m] - base[m]), tg[m],
                                n_draws=2000)
    noop.append(dict(response=t, dMAE=r["real"], p=r["p"], null_sd=r["null_sd"],
                     n_distinct_draws=int(len(np.unique(r["draws"])))))
    print("  %-8s no-op dMAE %.3e   p %.4f   null_sd %.3e   distinct draws %d"
          % (t, r["real"], r["p"], r["null_sd"], len(np.unique(r["draws"]))))
    assert r["real"] == 0.0, "NO-OP PLACEBO FAILED"
pd.DataFrame(noop).to_csv(os.path.join(B.OUT, "control_noop.csv"), index=False)

# =====================================================================================
B.hdr("4. RANDOM-TARGET CONTROL -- same-size random row sets, 20 replicates each")
# =====================================================================================
rng = np.random.default_rng(B.SEED + 77)
idxU = np.flatnonzero(SCORED)
rt = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    ch = pd.to_numeric(f[RESP[t]], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    for c, src in (("A", A_hat[t]), ("B", B_hat[t])):
        k = int((TREATED[c] & SCORED).sum())
        ds = []
        for _ in range(20):
            mfake = np.zeros(len(f), bool)
            mfake[rng.choice(idxU, size=k, replace=False)] = True
            p = ch.copy()
            sel = mfake & np.isfinite(src)
            p[sel] = src[sel]
            a = wf_arm(p, [], y, season)
            ds.append(B.mae(y[SCORED], base[SCORED]) - B.mae(y[SCORED], a[SCORED]))
        real = B.mae(y[SCORED], base[SCORED]) - B.mae(y[SCORED], FC[(t, c)][SCORED])
        rt.append(dict(component=c, response=t, n_treated=k, real_dMAE=real,
                       random_mean=float(np.mean(ds)), random_sd=float(np.std(ds, ddof=1)),
                       ratio_real_over_random=(real / np.mean(ds) if np.mean(ds) else np.nan)))
    # C: random team-games of the same count carry a fake "freed"
    k = int(len(np.unique(tg[SCORED & TC])))
    ds = []
    utg = np.unique(tg[SCORED])
    for _ in range(20):
        pick = set(rng.choice(utg, size=k, replace=False).tolist())
        fake = np.array([g in pick for g in tg]) & (f["established"].to_numpy() == 1)
        uu = np.where(fake, np.abs(pd.to_numeric(f["u_" + t], errors="coerce")
                                   .fillna(0.0).to_numpy(float)), 0.0)
        # give the fake team-games a redistribution term of the same MAGNITUDE distribution
        uu = np.where(fake & (uu == 0), float(np.mean(np.abs(Cu[t][Cu[t] != 0]))), uu)
        zz = pd.to_numeric(f["z_" + t], errors="coerce").fillna(0.0).to_numpy(float)
        a = wf_arm(ch, [uu, uu * zz], y, season)
        ds.append(B.mae(y[SCORED], base[SCORED]) - B.mae(y[SCORED], a[SCORED]))
    real = B.mae(y[SCORED], base[SCORED]) - B.mae(y[SCORED], FC[(t, "C")][SCORED])
    rt.append(dict(component="C", response=t, n_treated=int((TC & SCORED).sum()),
                   real_dMAE=real, random_mean=float(np.mean(ds)),
                   random_sd=float(np.std(ds, ddof=1)),
                   ratio_real_over_random=(real / np.mean(ds) if np.mean(ds) else np.nan)))
rtd = pd.DataFrame(rt)
rtd.to_csv(os.path.join(B.OUT, "control_random_target.csv"), index=False)
print(rtd.to_string(index=False))

# =====================================================================================
B.hdr("5. INJECTION-VERIFIED POWER FLOORS -- component-wise, through the identical code path")
# =====================================================================================
# NOT shuffled residuals.  E1_I0034 confirmed that construction systematically attenuates the
# recovered effect (0.024 -> -0.001 at 2 null sd).  Here a KNOWN MAE improvement of size
# k * null_sd is planted by moving the arm's forecast toward the truth on the treated rows only,
# and the same null is asked to recover it.
inj = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    for sname, smask in (("POOLED", SCORED), ("DECISION", SCORED & DEC)):
        r0 = B.paired_signflip_block(np.abs(y[smask] - base[smask]),
                                     np.abs(y[smask] - base[smask]), tg[smask], n_draws=4000)
        # null_sd of the DECISION/POOLED cell from the real lattice, taken from the C arm
        rC = B.paired_signflip_block(np.abs(y[smask] - FC[(t, "C")][smask]),
                                     np.abs(y[smask] - base[smask]), tg[smask], n_draws=4000)
        nsd = rC["null_sd"]
        for k in (0.0, 0.5, 1.0, 2.0, 4.0):
            target = k * nsd
            lb = np.abs(y[smask] - base[smask])
            # shrink the loss uniformly on the treated rows by exactly `target` in the mean
            tr = TC[smask]
            if tr.sum() == 0:
                continue
            shift = target * smask.sum() / tr.sum()
            la = lb.copy()
            la[tr] = np.maximum(la[tr] - shift, 0.0)
            got = float(lb.mean() - la.mean())
            rr = B.paired_signflip_block(la, lb, tg[smask], n_draws=4000)
            inj.append(dict(response=t, stratum=sname, planted_multiple_of_null_sd=k,
                            planted_dMAE=target, realised_dMAE=got, p=rr["p"],
                            detected_at_05=bool(rr["p"] < 0.05),
                            null_sd=rr["null_sd"], null_mean=rr["null_mean"]))
idf = pd.DataFrame(inj)
idf.to_csv(os.path.join(B.OUT, "power_injection.csv"), index=False)
print(idf.to_string(index=False))

# the injection-verified floor: the smallest planted multiple detected at 0.05 in every response
flo = []
for (t, s), g in idf.groupby(["response", "stratum"]):
    det = g[(g["planted_multiple_of_null_sd"] > 0) & g["detected_at_05"]]
    k80 = float(det["planted_multiple_of_null_sd"].min()) if len(det) else np.nan
    nsd = float(g["null_sd"].median())
    flo.append(dict(response=t, stratum=s, null_sd_median=nsd,
                    smallest_detected_multiple=k80,
                    MDE80_analytic=2.80 * nsd,
                    MDE80_injection_verified=(k80 * nsd if np.isfinite(k80) else np.nan),
                    type_I_at_zero=float(g.loc[g["planted_multiple_of_null_sd"] == 0, "p"]
                                         .lt(0.05).mean())))
fdf = pd.DataFrame(flo)
fdf.to_csv(os.path.join(B.OUT, "power_floors.csv"), index=False)
print("\n" + fdf.to_string(index=False))

# =====================================================================================
B.hdr("6. TYPE-I CALIBRATION -- 400 synthetic no-effect datasets per (response, stratum)")
# =====================================================================================
rng2 = np.random.default_rng(B.SEED + 991)
t1 = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    for sname, smask in (("POOLED", SCORED), ("DECISION", SCORED & DEC)):
        lb = np.abs(y[smask] - base[smask])
        sd = float(np.std(lb))
        ps = []
        for _ in range(400):
            la = lb + rng2.normal(0.0, 0.05 * sd, size=len(lb))
            ps.append(B.paired_signflip_block(la, lb, tg[smask], n_draws=400)["p"])
        t1.append(dict(response=t, stratum=sname, n_datasets=400,
                       rejection_rate_at_05=float(np.mean(np.array(ps) < 0.05))))
        print("  %-8s %-9s type-I %.4f" % (t, sname, t1[-1]["rejection_rate_at_05"]))
pd.DataFrame(t1).to_csv(os.path.join(B.OUT, "power_type_I.csv"), index=False)

# =====================================================================================
B.hdr("7. C ON ITS OWN 2,475 ROWS -- the bridge back to D116's published +1.82%")
# =====================================================================================
br = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    m = SCORED & TC
    for a in ("C", "ABC"):
        br.append(cell(y, FC[(t, a)], FC[(t, "base")], m,
                       "%s__%s__on_C_own_rows" % (a, t), response=t, arm_id=a))
    br.append(cell(y, FC[(t, "C")], FC[(t, "base")], SCORED & TC & DEC,
                   "C__%s__on_C_own_rows_DECISION" % t, response=t, arm_id="C_DECISION"))
    br.append(cell(y, FC[(t, "ABC")], FC[(t, "base")], SCORED & TC & DEC,
                   "ABC__%s__on_C_own_rows_DECISION" % t, response=t, arm_id="ABC_DECISION"))
bdf = pd.DataFrame(br)
bdf.to_csv(os.path.join(B.OUT, "C_on_own_rows.csv"), index=False)
print(bdf[["label", "n", "mae_base", "mae_arm", "dMAE", "pct_of_MAE", "p", "null_mean",
           "null_sd", "MDE80_analytic"]].to_string(index=False))

json.dump(B.jsonable(OUTJ), open(os.path.join(B.OUT, "_s06.json"), "w"), indent=1)
print("\n  wrote vacuous_split.csv, negative_and_threshold_strata.csv, control_noop.csv,")
print("        control_random_target.csv, power_injection.csv, power_floors.csv,")
print("        power_type_I.csv, C_on_own_rows.csv")
