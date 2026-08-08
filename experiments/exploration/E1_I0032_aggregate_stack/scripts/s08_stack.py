"""E1_I0032 s08 -- STEPS 2, 3, 4 and 5.

  STEP 2  compose every reproducible component into ONE forecast per target and measure it ONCE.
  STEP 3  the ablation matrix -- remove each component in turn.  THE CENTREPIECE.
  STEP 4  the order-of-addition curve -- where does it flatten?
  STEP 5  the matched placebo stack through the IDENTICAL pipeline.

One row set.  One denominator per (target, stratum).  Every p carries null_mean and null_sd.
Every table is written to disk as it is produced.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import (OUT, TARGETS, SCORED, SEED, N_DRAWS, prereg, paired, r2c,
                        wf_correction, wf_feature_correction, prior_season_tercile_top)

pd.set_option("display.width", 250)
spec = prereg()
print("prereg sha256 %s  MATCH" % spec["sha256"])
amend = json.load(open(os.path.join(OUT, "_prereg_amendment.json"), encoding="utf-8"))
print("amend 1 sha256 %s" % amend["sha256"])

work = pd.read_parquet(os.path.join(OUT, "_work.parquet"))
COMMON = work["COMMON"].to_numpy(bool)
DEC = work["DECISION"].to_numpy(bool)
season = work["season"].to_numpy()
groups = work["groups"].to_numpy()
N = len(work)

usg = work["usg"].to_numpy(float)
TOP = prior_season_tercile_top(usg, season)
FEAT = {
    "C6_OPP_DEFENCE_SELECTIVE": dict(col="DEF", mask=COMMON & np.isfinite(work["DEF"].to_numpy(float)) & TOP),
    "C5_TEAMMATE_VOLUME_PRIOR_ONLY": dict(col="P01", mask=COMMON & np.isfinite(work["P01"].to_numpy(float))),
    "C7_HOME_AWAY": dict(col="HOME", mask=COMMON & np.isfinite(work["HOME"].to_numpy(float))),
}
PFEAT = {
    "C6_OPP_DEFENCE_SELECTIVE": dict(col="pDEF", mask=COMMON & np.isfinite(work["pDEF"].to_numpy(float)) & TOP),
    "C5_TEAMMATE_VOLUME_PRIOR_ONLY": dict(col="G01", mask=COMMON & np.isfinite(work["G01"].to_numpy(float))),
    "C7_HOME_AWAY": dict(col="pHOME", mask=COMMON & np.isfinite(work["pHOME"].to_numpy(float))),
}
FEATURE_ORDER = ["C6_OPP_DEFENCE_SELECTIVE", "C5_TEAMMATE_VOLUME_PRIOR_ONLY", "C7_HOME_AWAY"]
ALL_COMPONENTS = ["C1_FALLBACK_ROUTE", "C3_PER_TARGET_HALFLIFE", "C4_SHRINK_OWN_PRIOR_SEASON"] \
                 + FEATURE_ORDER
# POOLED_EXCL_ROUTED is a POST-HOC DIAGNOSTIC, labelled as such wherever it appears.  It was added
# after seeing that C1 carries almost all of the pooled gain, to answer the obvious next question --
# does anything aggregate on the rows the champion already models?  It is NOT a preregistered
# headline cell and is never quoted as one.  D094's precedent: the fallback/modelled split was
# labelled post hoc throughout and the label was preserved.
NOT_ROUTED = COMMON & (work["fbl_pts"].to_numpy(float) == 0)
STRATA = {"POOLED": COMMON, "DECISION": DEC, "POOLED_EXCL_ROUTED__POSTHOC": NOT_ROUTED}
HEADLINE_STRATA = ["POOLED", "DECISION"]
ALL_STRATA = ["POOLED", "DECISION", "POOLED_EXCL_ROUTED__POSTHOC"]
SST = {(t, s): float(((work["y_%s" % t].to_numpy(float)[m]
                       - work["y_%s" % t].to_numpy(float)[m].mean()) ** 2).sum())
       for t in TARGETS for s, m in STRATA.items()}


def est_name(comps, placebo):
    """Which estimator cell C1 routes to, given which of C3/C4 are present."""
    hl, sh = "C3_PER_TARGET_HALFLIFE" in comps, "C4_SHRINK_OWN_PRIOR_SEASON" in comps
    if placebo:
        return {(1, 1): "p_full", (1, 0): "p_hl", (0, 1): "p_shr", (0, 0): "naive"}[(int(hl), int(sh))]
    return {(1, 1): "full", (1, 0): "hl", (0, 1): "shr", (0, 0): "naive"}[(int(hl), int(sh))]


def build(t, comps, placebo=False):
    """The stack for target `t` from the component set `comps`.  Champion is NEVER refitted."""
    y = work["y_%s" % t].to_numpy(float)
    yhat = work["champ_%s" % t].to_numpy(float).copy()
    if "C1_FALLBACK_ROUTE" in comps:
        rm = (work["proute_%s" % t].to_numpy(bool) if placebo
              else (work["fbl_%s" % t].to_numpy(float) == 2)) & COMMON
        yhat[rm] = work["e_%s_%s" % (est_name(comps, placebo), t)].to_numpy(float)[rm]
    src = PFEAT if placebo else FEAT
    for cid in FEATURE_ORDER:
        if cid not in comps:
            continue
        d = src[cid]
        yhat = yhat + wf_feature_correction(y - yhat, work[d["col"]].to_numpy(float),
                                            season, d["mask"])
    return yhat


def measure(t, stratum, a, b, name_a, name_b):
    m = STRATA[stratum]
    y = work["y_%s" % t].to_numpy(float)
    sst = SST[(t, stratum)]
    pr = paired(y[m], a[m], b[m], groups[m], name_a=name_a, name_b=name_b)
    return dict(target=t, stratum=stratum, arm=name_a, base=name_b,
                dr2_common_sst=r2c(y[m], a[m], sst) - r2c(y[m], b[m], sst),
                dr2_kit=pr["dr2"], n=pr["n"], n_clusters=pr["n_clusters"], p=pr["p"],
                null_mean=pr["null_mean"], null_sd=pr["null_sd"],
                p_row_NAIVE=pr["p_row_NAIVE"], inflation=pr["inflation"],
                mae_arm=float(np.mean(np.abs(y[m] - a[m]))),
                mae_base=float(np.mean(np.abs(y[m] - b[m]))),
                sst_common=sst)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


FULL = {t: build(t, ALL_COMPONENTS, False) for t in TARGETS}
PFULL = {t: build(t, ALL_COMPONENTS, True) for t in TARGETS}

# ============================================================================ STEP 2
hdr("STEP 2 -- THE STACK, MEASURED ONCE.  8 preregistered headline cells.")
rows = []
for t in TARGETS:
    ch = work["champ_%s" % t].to_numpy(float)
    r4 = work["R4_%s" % t].to_numpy(float)
    for s in ALL_STRATA:
        rows.append(dict(family="HEADLINE", **measure(t, s, FULL[t], ch, "STACK", "CHAMPION")))
        rows.append(dict(family="SECONDARY_BASE",
                         **measure(t, s, FULL[t], r4, "STACK", "R4_COMPLETE")))
        rows.append(dict(family="CONTEXT",
                         **measure(t, s, ch, r4, "CHAMPION", "R4_COMPLETE")))
sm = pd.DataFrame(rows)
sm.to_csv(os.path.join(OUT, "stack_measurement.csv"), index=False)
print(sm[sm.family == "HEADLINE"][["target", "stratum", "dr2_common_sst", "p", "null_mean",
                                   "null_sd", "n", "n_clusters", "mae_arm", "mae_base"]]
      .to_string(index=False))
print("\nSECONDARY BASE (stack vs the COMPLETE reference R4):")
print(sm[sm.family == "SECONDARY_BASE"][["target", "stratum", "dr2_common_sst", "p", "null_mean",
                                         "null_sd"]].to_string(index=False))
print("\nCONTEXT (champion vs R4 -- where the champion itself sits):")
print(sm[sm.family == "CONTEXT"][["target", "stratum", "dr2_common_sst", "p"]].to_string(index=False))

# ---- controls
ctrl = []
for t in TARGETS:
    ch = work["champ_%s" % t].to_numpy(float)
    ctrl.append(dict(control="NOOP_stack_equals_champion",
                     **measure(t, "POOLED", build(t, [], False), ch, "NOOP", "CHAMPION")))
    ctrl.append(dict(control="SELF_champion_vs_champion",
                     **measure(t, "POOLED", ch, ch, "CHAMPION", "CHAMPION")))
cdf = pd.DataFrame(ctrl)
cdf.to_csv(os.path.join(OUT, "controls.csv"), index=False)
print("\nCONTROLS (must be exactly 0 at p=1):")
print(cdf[["control", "target", "dr2_common_sst", "p"]].to_string(index=False))

# ============================================================================ STEP 3
hdr("STEP 3 -- THE ABLATION MATRIX.  Remove each component from the FULL stack.")
ab = []
S2324 = COMMON & (season >= 2023)
for cid in ALL_COMPONENTS:
    less = [c for c in ALL_COMPONENTS if c != cid]
    for t in TARGETS:
        a = build(t, less, False)
        for s in ALL_STRATA:
            r = measure(t, s, FULL[t], a, "FULL_STACK", "MINUS_%s" % cid)
            r["component"] = cid
            r["identical_forecast"] = bool(np.allclose(FULL[t], a, equal_nan=True))
            # coverage: on how many scored rows can this component act at all?
            if cid == "C1_FALLBACK_ROUTE":
                cov = int(((work["fbl_%s" % t].to_numpy(float) == 2) & STRATA[s]).sum())
            elif cid in FEAT:
                cov = int((FEAT[cid]["mask"] & STRATA[s]).sum())
            else:
                cov = int(((work["fbl_%s" % t].to_numpy(float) == 2) & STRATA[s]).sum())
            r["rows_component_can_act_on"] = cov
            r["coverage_frac"] = cov / max(int(STRATA[s].sum()), 1)
            ab.append(r)
        pd.DataFrame(ab).to_csv(os.path.join(OUT, "ablation_matrix.csv"), index=False)
abd = pd.DataFrame(ab)
for s in ALL_STRATA:
    print("\n  --- stratum %s ---" % s)
    print(abd[abd.stratum == s][["component", "target", "dr2_common_sst", "p", "null_mean",
                                 "null_sd", "rows_component_can_act_on", "coverage_frac",
                                 "identical_forecast"]].to_string(index=False))

hdr("STEP 3b -- SUM OF PARTS versus THE WHOLE")
sop = []
for t in TARGETS:
    for s in ALL_STRATA:
        whole = float(sm[(sm.family == "HEADLINE") & (sm.target == t)
                         & (sm.stratum == s)]["dr2_common_sst"].iloc[0])
        parts = float(abd[(abd.target == t) & (abd.stratum == s)]["dr2_common_sst"].sum())
        sop.append(dict(target=t, stratum=s, whole_stack_gain=whole,
                        sum_of_ablation_deltas=parts,
                        shortfall=whole - parts,
                        ratio_parts_over_whole=parts / whole if whole else np.nan))
sopd = pd.DataFrame(sop)
sopd.to_csv(os.path.join(OUT, "sum_of_parts.csv"), index=False)
print(sopd.to_string(index=False))

# ============================================================================ STEP 4
hdr("STEP 4 -- ORDER OF ADDITION.  Largest published effect first.")
cum = []
order = spec["stack_order_largest_published_first"]
for t in TARGETS:
    ch = work["champ_%s" % t].to_numpy(float)
    prev = ch
    for i in range(len(order) + 1):
        comps = order[:i]
        a = build(t, comps, False)
        for s in ALL_STRATA:
            r = measure(t, s, a, ch, "STEP%d" % i, "CHAMPION")
            r["step"] = i
            r["added"] = "(champion)" if i == 0 else order[i - 1]
            r["components_so_far"] = "+".join(comps) if comps else "(none)"
            inc = measure(t, s, a, prev, "STEP%d" % i, "STEP%d" % (i - 1)) if i else None
            r["increment_dr2"] = inc["dr2_common_sst"] if inc else 0.0
            r["increment_p"] = inc["p"] if inc else 1.0
            r["increment_null_sd"] = inc["null_sd"] if inc else 0.0
            cum.append(r)
        prev = a
        pd.DataFrame(cum).to_csv(os.path.join(OUT, "cumulative_curve.csv"), index=False)
cud = pd.DataFrame(cum)
print(cud[cud.stratum == "POOLED"][["target", "step", "added", "dr2_common_sst",
                                    "increment_dr2", "increment_p", "increment_null_sd"]]
      .to_string(index=False))

# ============================================================================ STEP 5
hdr("STEP 5 -- THE PLACEBO STACK.  Identical pipeline, identical nulls, no information.")
pl = []
for t in TARGETS:
    ch = work["champ_%s" % t].to_numpy(float)
    r4 = work["R4_%s" % t].to_numpy(float)
    for s in ALL_STRATA:
        pl.append(dict(family="PLACEBO_HEADLINE",
                       **measure(t, s, PFULL[t], ch, "PLACEBO_STACK", "CHAMPION")))
        pl.append(dict(family="PLACEBO_SECONDARY",
                       **measure(t, s, PFULL[t], r4, "PLACEBO_STACK", "R4_COMPLETE")))
# per-placebo-component ablation, same pipeline
for cid in ALL_COMPONENTS:
    less = [c for c in ALL_COMPONENTS if c != cid]
    for t in TARGETS:
        a = build(t, less, True)
        for s in ALL_STRATA:
            r = measure(t, s, PFULL[t], a, "PLACEBO_FULL", "PLACEBO_MINUS_%s" % cid)
            r["family"] = "PLACEBO_ABLATION"
            r["component"] = cid
            pl.append(r)
    pd.DataFrame(pl).to_csv(os.path.join(OUT, "placebo_stack.csv"), index=False)
pld = pd.DataFrame(pl)
pld.to_csv(os.path.join(OUT, "placebo_stack.csv"), index=False)
print(pld[pld.family == "PLACEBO_HEADLINE"][["target", "stratum", "dr2_common_sst", "p",
                                             "null_mean", "null_sd"]].to_string(index=False))

hdr("REAL versus PLACEBO, side by side (the preregistered decision rule)")
cmp_rows = []
for t in TARGETS:
    for s in ALL_STRATA:
        rv = float(sm[(sm.family == "HEADLINE") & (sm.target == t) & (sm.stratum == s)]
                   ["dr2_common_sst"].iloc[0])
        rp = float(sm[(sm.family == "HEADLINE") & (sm.target == t) & (sm.stratum == s)]["p"].iloc[0])
        pv = float(pld[(pld.family == "PLACEBO_HEADLINE") & (pld.target == t) & (pld.stratum == s)]
                   ["dr2_common_sst"].iloc[0])
        pp = float(pld[(pld.family == "PLACEBO_HEADLINE") & (pld.target == t)
                       & (pld.stratum == s)]["p"].iloc[0])
        # The preregistered rule speaks about a placebo GAIN.  A placebo that loses is not evidence
        # against the real stack, so the sign is tested before the magnitude.
        if pv <= 0:
            v = "PLACEBO SHOWS NO GAIN (dR2 %+.6f, p %.4f) -- the control is clean here" % (pv, pp)
        elif abs(rv) < 3 * abs(pv):
            v = "UNINTERPRETABLE -- the placebo gain is the same order as the real one"
        else:
            v = "PLACEBO GAIN IS %.0fx SMALLER THAN THE REAL ONE" % (abs(rv) / abs(pv))
        if rv <= 0:
            v = "REAL STACK DOES NOT GAIN HERE (dR2 %+.6f, p %.4f); " % (rv, rp) + v
        cmp_rows.append(dict(target=t, stratum=s, real_dr2=rv, real_p=rp, placebo_dr2=pv,
                             placebo_p=pp,
                             placebo_shows_a_gain=bool(pv > 0),
                             ratio_real_over_placebo=rv / pv if pv else np.inf,
                             verdict=v))
cdf2 = pd.DataFrame(cmp_rows)
cdf2.to_csv(os.path.join(OUT, "real_vs_placebo.csv"), index=False)
print(cdf2.to_string(index=False))

json.dump({"n_common": int(COMMON.sum()), "n_decision": int(DEC.sum()),
           "n_clusters": int(pd.unique(groups[COMMON]).size),
           "top_tercile_rows": int((TOP & COMMON).sum()),
           "feature_masks": {k: int((v["mask"]).sum()) for k, v in FEAT.items()}},
          open(os.path.join(OUT, "_s08.json"), "w", encoding="utf-8"), indent=1)
print("\nDONE -- stack_measurement.csv, ablation_matrix.csv, sum_of_parts.csv, "
      "cumulative_curve.csv, placebo_stack.csv, real_vs_placebo.csv, controls.csv")

