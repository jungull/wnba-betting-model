"""S06 -- VERIFICATION.  Every headline number must re-derive from the stored artifacts.

Re-reads the parquet bytes, the stored out-of-fold predictions and the stored null draws, and
re-derives each published quantity independently of the stage that produced it.  Any mismatch is
a FAIL and is printed as one.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _e56 import *  # noqa
from _common import HERE, MIN_TRAIN, Z80, folds_wf  # noqa

CHECKS = []


def chk(name, ok, detail=""):
    CHECKS.append((name, bool(ok), detail))
    print("  [%s] %-58s %s" % ("PASS" if ok else "FAIL", name, detail))


def close(a, b, tol):
    return bool(np.isfinite(a) and np.isfinite(b) and abs(float(a) - float(b)) <= tol)


print("=" * 100)
print("S06 -- VERIFICATION")
print("=" * 100)

# ---------------------------------------------------------------- 1. the prereg is unmodified
h = hashlib.sha256(open(os.path.join(HERE, "PREREG.md"), "rb").read()).hexdigest()
declared = open(os.path.join(HERE, "PREREG.sha256")).read().split()[0]
chk("PREREG.md matches PREREG.sha256", h == declared, h[:16])

F = json.load(open(os.path.join(HERE, "FINDINGS.json")))
s1 = json.load(open(os.path.join(HERE, "scripts", "_s01.json")))
s2 = json.load(open(os.path.join(HERE, "scripts", "_s02.json")))
s3 = json.load(open(os.path.join(HERE, "scripts", "_s03.json")))
s4p = os.path.join(HERE, "scripts", "_s04.json")
s4 = json.load(open(s4p)) if os.path.exists(s4p) else {}
chk("FINDINGS.json carries the same prereg hash", F["prereg_sha256"] == declared)

# ------------------------------------------------- 2. the defect, re-read from the parquet bytes
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OOFD = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
sdv = {}
allconst = True
for s in (2022, 2023, 2024):
    d = pd.read_parquet(os.path.join(OOFD, "predictions__e_minutes_given_active__%d.parquet" % s))
    allconst &= (d["pred_sd"].nunique() == 1)
    sdv[str(s)] = float(d["pred_sd"].iloc[0])
    pt = d["pred_point"].to_numpy(float)
    allconst &= (len(np.unique(np.round(d["pred_q75"].to_numpy(float) - pt, 9))) == 1)
chk("minutes pred_sd + q75 offset are 1 value per season (bytes)", allconst)
for k, v in sdv.items():
    chk("pred_sd %s re-reads as %.12f" % (k, v),
        close(v, F["Q1_the_defect"]["minutes_pred_sd_by_season"][k], 1e-12))

src = open(os.path.join(ROOT, "cbs_player_runner_v14.py")).read().splitlines()
chk("cbs_player_runner_v14.py:313 is the scalar broadcast",
    "pd.Series(sd_v, index=test.index)" in src[312], src[312].strip()[:60])
src5 = open(os.path.join(ROOT, "cbs_v5.py")).read().splitlines()
chk("cbs_v5.py:169 defines dispersion()", src5[168].strip().startswith("def dispersion("))

# ------------------------------------------------------- 3. the ladder, refit from the frame
sub, X, ix, meta = build("A4_CLEAN_DEC", impute="prior")
y = sub["absres_minutes"].to_numpy(float)
psb, tgb = meta["psblock"], meta["tgblock"]
folds = folds_wf(meta["gdate"], MIN_TRAIN)
scored = np.sort(np.concatenate([te for _, te in folds]))
SST = sst_of(y, scored)
chk("n rows = 3549, scored = 2945, blocks = 174",
    len(sub) == 3549 and len(scored) == 2945 and psb.max() + 1 == 174)
chk("SST re-derives", close(SST, F["SST"], 1e-6), "%.6f" % SST)

LAD = pd.read_csv(os.path.join(HERE, "REFERENCE_LADDER.csv")).set_index("arm")
ARMS = dict(LADDER)
ARMS["C1"] = L1 + BLOCK_N
ARMS["C5"] = L5 + BLOCK_N
ARMS["NONLY"] = list(BLOCK_N)
ARMS["C5X"] = L5 + BLOCK_N2
ARMS["VSIG"] = list(VSIG)
ARMS["VSD"] = ["minutes__pred_sd"]
P = {}
for nm, cl in ARMS.items():
    P[nm] = oof(folds, y, X, [ix[c] for c in cl])
    r2 = 1.0 - sse(y, P[nm], scored) / SST
    rat = decile_ratio(P[nm][scored], y[scored])[0]
    chk("arm %-6s OOF R2 re-derives" % nm, close(r2, LAD.loc[nm, "oof_r2"], 1e-12),
        "%+.6f" % r2)
    chk("arm %-6s decile ratio re-derives" % nm, close(rat, LAD.loc[nm, "decile_ratio"], 1e-10),
        "%.4f" % rat)

d5 = (sse(y, P["L5"], scored) - sse(y, P["C5"], scored)) / SST
d1 = (sse(y, P["L1"], scored) - sse(y, P["C1"], scored)) / SST
db = (sse(y, P[F["Q2_the_increment"]["strongest_level_rung"]], scored)
      - sse(y, P["C5"], scored)) / SST
chk("dR2(C5 over L5) re-derives", close(d5, F["Q2_the_increment"]["dr2_over_L5_PREREGISTERED_PRIMARY"], 1e-12),
    "%+.6f" % d5)
chk("dR2(C1 over L1) re-derives", close(d1, F["Q2_the_increment"]["dr2_over_L1_the_D134_reference"], 1e-12),
    "%+.6f" % d1)
chk("dR2(C5 over strongest rung) re-derives",
    close(db, F["Q2_the_increment"]["dr2_over_strongest_level_rung"], 1e-12), "%+.6f" % db)
chk("strongest level rung really is the argmax",
    F["Q2_the_increment"]["strongest_level_rung"]
    == max(["L1", "L2", "L3", "L4", "L5"], key=lambda k: LAD.loc[k, "oof_r2"]))

# ----------------------------------------------- 4. nulls and CI, from the stored raw draws
Z = np.load(os.path.join(RAW, "s02_nulls.npz"), allow_pickle=True)
# the walk-forward warm-up rows are NaN in both by construction, so compare on the scored rows
_d = float(np.max(np.abs(Z["pred_C5"][scored] - P["C5"][scored])))
chk("stored OOF predictions match a fresh refit (C5, scored rows)", _d < 1e-10,
    "max abs diff %.3e" % _d)
chk("both agree that exactly the 604 warm-up rows are unscored",
    int((~np.isfinite(Z["pred_C5"])).sum()) == int((~np.isfinite(P["C5"])).sum()) == 604)
DRC, DRS, VZ = Z["cyclic"], Z["shuffle"], Z["vacuity"]
p_cyc = float((np.sum(DRC >= d5) + 1) / (len(DRC) + 1))
p_shf = float((np.sum(DRS >= d5) + 1) / (len(DRS) + 1))
chk("cyclic null R = 1000 draws stored", len(DRC) == 1000, "n=%d" % len(DRC))
chk("cyclic p re-derives from the raw draws", close(p_cyc, F["Q2_the_increment"]["cyclic_null_p"], 1e-12),
    "p=%.6f" % p_cyc)
chk("shuffle p re-derives from the raw draws", close(p_shf, F["Q2_the_increment"]["shuffle_null_p"], 1e-12),
    "p=%.6f" % p_shf)
chk("vacuity control is the exact identity",
    float(np.std(VZ)) == 0.0 and len(np.unique(VZ)) == 1 and close(VZ[0], d5, 1e-12))
chk("cyclic control is NOT vacuous (moves)",
    float(np.std(DRC, ddof=1)) > 1e-6 and len(np.unique(DRC)) > 100,
    "sd=%.6f distinct=%d" % (float(np.std(DRC, ddof=1)), len(np.unique(DRC))))
BOOT = Z["boot"]
ci = (float(np.percentile(BOOT, 2.5)), float(np.percentile(BOOT, 97.5)))
chk("bootstrap CI re-derives from the raw draws",
    close(ci[0], F["Q2_the_increment"]["block_bootstrap_ci_95_over_L5"][0], 1e-12)
    and close(ci[1], F["Q2_the_increment"]["block_bootstrap_ci_95_over_L5"][1], 1e-12),
    "[%+.6f, %+.6f]" % ci)
chk("bootstrap CI spans zero <-> frac<=0 agrees",
    (ci[0] <= 0 <= ci[1]) == (0.025 <= F["Q2_the_increment"]["block_bootstrap_frac_le_zero"] <= 0.975),
    "frac<=0 = %.4f" % F["Q2_the_increment"]["block_bootstrap_frac_le_zero"])
dd = (y[scored] - P["L5"][scored]) ** 2 - (y[scored] - P["C5"][scored]) ** 2
_, pps, _ = signflip(dd, psb[scored], 5000, SEED_NULL)
chk("paired sign-flip p (player-season) re-derives",
    close(pps, F["Q2_the_increment"]["signflip_p_player_season"], 1e-12), "p=%.6f" % pps)
# NB: this verifies that the reported numbers RE-DERIVE.  It is not a pass/fail on the science --
# P11 FAILED and that failure is a reported finding, not a verification error.
DRN, PN = Z["noise_dr2"], Z["noise_p"]
chk("noise control mean dR2 re-derives from the raw draws",
    close(float(DRN.mean()), F["Q2_the_increment"]["noise_control_mean_dr2"], 1e-12),
    "%+.6f" % float(DRN.mean()))
chk("noise control Type-I re-derives from the raw draws",
    close(float((PN < 0.05).mean()), F["Q2_the_increment"]["signflip_typeI_on_noise"], 1e-12),
    "%.3f at nominal 0.05 -> the sign-flip p is UNCALIBRATED here" % float((PN < 0.05).mean()))
chk("every noise draw is negative (the statistic is not centred at zero)",
    bool((DRN < 0).all()), "max = %+.6f" % float(DRN.max()))
chk("observed sd above the noise placebo re-derives",
    close((d5 - DRN.mean()) / DRN.std(ddof=1),
          F["Q2_the_increment"]["observed_sd_above_noise_placebo"], 1e-9),
    "%+.2f sd" % ((d5 - DRN.mean()) / DRN.std(ddof=1)))
chk("observed sd above the CYCLIC null re-derives",
    close((d5 - DRC.mean()) / DRC.std(ddof=1),
          F["Q2_the_increment"]["observed_sd_above_cyclic_null"], 1e-9),
    "%+.2f sd" % ((d5 - DRC.mean()) / DRC.std(ddof=1)))
# the post-hoc reference-incompleteness result
if s4:
    v1 = oof(folds, y, X, [ix[c] for c in L1])
    v4 = oof(folds, y, X, [ix[c] for c in L4])
    d41 = (sse(y, v1, scored) - sse(y, v4, scored)) / SST
    chk("POSTHOC dR2(L4 over L1) re-derives", close(d41, s4["dr2_L4_over_L1"], 1e-12),
        "%+.6f" % d41)
    B41 = np.load(os.path.join(RAW, "s04_posthoc.npz"))["boot_L4_over_L1"]
    chk("POSTHOC dR2(L4 over L1) bootstrap CI excludes zero",
        float(np.percentile(B41, 2.5)) > 0,
        "CI [%+.6f, %+.6f], frac<=0 = %.4f" % (float(np.percentile(B41, 2.5)),
                                               float(np.percentile(B41, 97.5)),
                                               float((B41 <= 0).mean())))

# ---------------------------------------------------------- 5. Q3 numbers, from stored arrays
W = np.load(os.path.join(RAW, "s03_worth.npz"), allow_pickle=True)
sc = W["scored"]
yy = W["y"]
AB = pd.read_csv(os.path.join(HERE, "ABSTENTION.csv"))
base = float(np.abs(yy[sc]).mean())
chk("full-sample minutes MAE re-derives", close(base, F["Q3_is_it_worth_anything"]["full_sample_mae_minutes"], 1e-9),
    "%.4f min" % base)
for arm, key in [("C5", "vhat_C5"), ("bestlevel", "vhat_best")]:
    v = W[key][sc]
    r = pd.Series(v).rank(method="first", pct=True).to_numpy()
    keep = r <= 0.70
    red = 1 - float(np.abs(yy[sc][keep]).mean()) / base
    tgt = (F["Q3_is_it_worth_anything"]["abstention_drop30_mae_reduction_C5"] if arm == "C5"
           else F["Q3_is_it_worth_anything"]["abstention_drop30_mae_reduction_level_only"])
    chk("abstention drop-30%% MAE reduction (%s) re-derives" % arm, close(red, tgt, 1e-9),
        "%.4f" % red)
IV = pd.read_csv(os.path.join(HERE, "INTERVALS.csv"))
resid = W["resid"]
K = np.sqrt(np.pi / 2.0)
row = IV[IV.model == "C5"].iloc[0]
sdc = np.maximum(W["vhat_C5"][sc], 1e-6) * K
chk("C5 nominal-80%% interval coverage re-derives",
    close(float((np.abs(resid) <= Z80 * sdc).mean()), row["coverage_nominal80"], 1e-9),
    "%.4f" % float((np.abs(resid) <= Z80 * sdc).mean()))
chk("C5 matched-coverage mean width re-derives",
    close(float((2 * float(np.percentile(np.abs(resid) / sdc, 80.0)) * sdc).mean()),
          row["mean_width_at_80pct_cover"], 1e-9), "%.3f min" % row["mean_width_at_80pct_cover"])

# ------------------------------------------------------------------- 6. power table integrity
POW = pd.read_csv(os.path.join(HERE, "POWER_INJECTION.csv"))
chk("power grid is the 8 preregistered c values with 40 reps each",
    len(POW) == 8 and int(POW["n_rep"].min()) == 40 and int(POW["n_rep"].max()) == 40)
chk("P15 outcome matches the c=0.10 detection rate",
    (F["predictions"][15]["outcome"] == "HELD")
    == bool(float(POW[np.isclose(POW["c"], 0.10)]["detection_rate"].iloc[0]) >= 0.80),
    "detection at c=0.10 = %.3f" % float(POW[np.isclose(POW["c"], 0.10)]["detection_rate"].iloc[0]))

# ---------------------------------------------------------- 7. prediction ledger consistency
stage = {}
for d in (s1, s2, s3):
    stage.update({k: v for k, v in d.items() if k.startswith("P") and isinstance(v, bool)})
bad = [p["id"] for p in F["predictions"]
       if p["id"] in stage and (p["outcome"] == "HELD") != stage[p["id"]]]
chk("every prediction outcome in FINDINGS matches its stage json", not bad, str(bad))
chk("17 tested statements from the 16 numbered predictions (P8 has two parts)",
    F["n_predictions"] == 17 and F["n_held"] + F["n_failed"] == 17,
    "%d HELD / %d FAILED" % (F["n_held"], F["n_failed"]))

# ---------------------------------------------------------------- 8. partition guard, again
import _common as C  # noqa
chk("frame contains no season outside 2021-2024",
    int(C.f["season"].min()) >= 2021 and int(C.f["season"].max()) <= 2024)
chk("frame contains no date in 2025 or later",
    pd.to_datetime(C.f["gdate"]).max() < pd.Timestamp("2025-01-01"))

npass = sum(1 for _, ok, _ in CHECKS if ok)
print("\n" + "=" * 100)
print("VERIFICATION: %d of %d assertions PASS" % (npass, len(CHECKS)))
print("=" * 100)
json.dump([dict(check=c, passed=o, detail=d) for c, o, d in CHECKS],
          open(os.path.join(HERE, "VERIFICATION.json"), "w"), indent=2)
if npass != len(CHECKS):
    print("FAILED CHECKS: %s" % [c for c, o, _ in CHECKS if not o])
    sys.exit(1)
print("DONE s06")
