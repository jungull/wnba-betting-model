"""E1_I0041 s02 -- PROBE: the real structural parameters the simulation must match.

Read-only.  Establishes block counts, family-wise thresholds, the folded-sd correction that is
directly recoverable from E0_I0014's own saved draws, and each screen's OWN family-wise max|t|
null (which is the like-for-like t-scale threshold D103 should have used).
"""
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D103 = os.path.join(EXPL, "E1_I0026_detection_floor")
P14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
P19 = os.path.join(EXPL, "E0_I0019_availability_forecast")
Z80 = 0.8416212335729143
O = {}


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


hdr("A. THE FAMILY-WISE t_crit VALUES D103 ACTUALLY PASSED TO mde80_tscale")
FWT = pd.read_csv(os.path.join(D103, "out", "s04_familywise_thresholds.csv"))
print(FWT.to_string(index=False))
tc14 = float(FWT[(FWT["arm"] == "N1_within") & (FWT["K"] == 348)]["q95_maxt"].iloc[0])
tc19 = float(FWT[(FWT["arm"] == "N2_entity_swap") & (FWT["K"] == 318)]["q95_maxt"].iloc[0])
print("\n  E0_I0014 (K=348, N1_within)      t_crit = %.6f" % tc14)
print("  E0_I0019 (K=318, N2_entity_swap) t_crit = %.6f" % tc19)
print("  These are q95 of max over K of (dR2 - mu)/sd  -- a standardised DELTA-R^2 statistic")
print("  (s04_power.py:70-72), i.e. a RIGHT-SKEWED chi-square-like quantity, not a t.")
O["t_crit_used"] = dict(E0_I0014=tc14, E0_I0019=tc19)

hdr("B. EACH SCREEN'S OWN FAMILY-WISE max|t| NULL -- the like-for-like t-scale threshold")
m14 = pd.read_csv(os.path.join(P14, "maxt_null_draws_whole_screen.csv"))
print("  E0_I0014 maxt_null_draws_whole_screen.csv cols=%s rows=%d" % (list(m14.columns), len(m14)))
c14 = [c for c in m14.columns if "cor" in c.lower() or "correct" in c.lower()] or list(m14.columns)
print("    columns available: %s" % list(m14.columns))
for c in m14.columns:
    v = pd.to_numeric(m14[c], errors="coerce").dropna().to_numpy()
    if len(v) > 100:
        print("    %-28s n=%d  mean=%.4f  q95=%.4f  max=%.4f"
              % (c, len(v), v.mean(), np.quantile(v, .95), v.max()))
m19 = pd.read_csv(os.path.join(P19, "maxt_null_draws.csv"))
print("\n  E0_I0019 maxt_null_draws.csv cols=%s rows=%d" % (list(m19.columns), len(m19)))
for c in m19.columns:
    v = pd.to_numeric(m19[c], errors="coerce").dropna().to_numpy()
    if len(v) > 100:
        print("    %-28s n=%d  mean=%.4f  q95=%.4f  max=%.4f"
              % (c, len(v), v.mean(), np.quantile(v, .95), v.max()))

hdr("C. THE FOLDED-sd CORRECTION, RECOVERED EXACTLY FROM E0_I0014'S OWN SAVED DRAWS")
print("  If the signed null t has mean 0 then  E[t^2] = E[|t|^2] = var(|t|) + mean(|t|)^2,")
print("  so  sd(t) = sqrt( sd(|t|)^2 + mean(|t|)^2 )  EXACTLY -- no normality assumed.")
z14 = np.load(os.path.join(P14, "permutation_nulls.npz"))
names = [str(x) for x in z14["names"]]
deps = [str(x) for x in z14["dependents"]]
use_between = z14["use_between"]
s14 = pd.read_csv(os.path.join(P14, "screen_results.csv"))
rows = []
for j, nm in enumerate(names):
    pref = "bet__" if use_between[j] else "win__"
    for k in deps:
        A = z14[pref + k][:, j].astype(float)
        A = A[np.isfinite(A)]
        if len(A) < 100:
            continue
        sd_abs = float(A.std(ddof=1))
        mu_abs = float(A.mean())
        sd_signed = float(np.sqrt(sd_abs ** 2 + mu_abs ** 2))
        rows.append(dict(candidate=nm, dependent=k, sd_abs=sd_abs, mean_abs=mu_abs,
                         sd_signed_recovered=sd_signed,
                         fold_factor_sd=(sd_signed / sd_abs) if sd_abs > 0 else np.nan))
FD = pd.DataFrame(rows)
FD.to_csv(os.path.join(HERE, "_fold_factors_E0_I0014.csv"), index=False)
print("  cells recovered: %d" % len(FD))
ff = FD["fold_factor_sd"].replace([np.inf, -np.inf], np.nan).dropna()
print("  fold factor on sd   : min=%.4f p10=%.4f median=%.4f p90=%.4f max=%.4f"
      % (ff.min(), ff.quantile(.1), ff.median(), ff.quantile(.9), ff.max()))
print("  fold factor on MDE  : median=%.4f  (MDE scales as sd^2)" % (ff.median() ** 2))
print("  half-normal reference (t exactly N(0,s)): sd factor 1.658855, MDE factor 2.752110")

# cross-check that sd_abs reproduces the screen's published null_correct_sd
mg = s14.merge(FD, on=["candidate", "dependent"], how="inner")
d = (mg["sd_abs"] - mg["null_correct_sd"]).abs()
print("\n  CROSS-CHECK  |recomputed sd(|t|) - published null_correct_sd|:")
print("    matched %d cells, max abs diff = %.3e, median = %.3e"
      % (len(mg), d.max(), d.median()))
O["fold"] = dict(cells=int(len(FD)), sd_factor_median=float(ff.median()),
                 sd_factor_p10=float(ff.quantile(.1)), sd_factor_p90=float(ff.quantile(.9)),
                 mde_factor_median=float(ff.median() ** 2),
                 crosscheck_max_abs_diff=float(d.max()), crosscheck_cells=int(len(mg)))

hdr("D. E0_I0019 -- is nullsd_between ever missing, and what does D103 then record?")
s19 = pd.read_csv(os.path.join(P19, "screen_results_repaired.csv"))
print("  rows=%d  nullsd_between NaN: %d  n NaN: %d"
      % (len(s19), int(s19["nullsd_between"].isna().sum()), int(s19["n"].isna().sum())))
print("  scheme_between value counts: %s" % s19["scheme_between"].value_counts().to_dict())
RP = pd.read_csv(os.path.join(D103, "out", "retrospective_power.csv"))
t19 = RP[RP["screen"] == "E0_I0019_availability_forecast"]
print("  D103 rows for E0_I0019: %d   mde80_fw NaN: %d"
      % (len(t19), int(t19["mde80_fw"].isna().sum())))
t14 = RP[RP["screen"] == "E0_I0014_residual_heterogeneity"]
print("  D103 rows for E0_I0014: %d   mde80_fw NaN: %d"
      % (len(t14), int(t14["mde80_fw"].isna().sum())))
O["nan_audit"] = dict(E0_I0019_nullsd_nan=int(s19["nullsd_between"].isna().sum()),
                      E0_I0019_mde_nan=int(t19["mde80_fw"].isna().sum()),
                      E0_I0014_mde_nan=int(t14["mde80_fw"].isna().sum()))

hdr("E. BLOCK / CLUSTER COUNTS actually used by the two screens")
for tag, log, pat in (("E0_I0014", os.path.join(P14, "run_log_screen.txt"), "blocks"),
                      ("E0_I0019", os.path.join(P19, "run_log_s04.txt"), "block")):
    if os.path.exists(log):
        txt = open(log, "r", encoding="utf-8", errors="replace").read().splitlines()
        for ln in txt:
            if pat in ln.lower() and any(ch.isdigit() for ch in ln):
                print("  [%s] %s" % (tag, ln.strip()[:150]))
lv = pd.read_csv(os.path.join(P19, "grouping_levels.csv"))
print("\n  E0_I0019 grouping_levels.csv cols: %s" % list(lv.columns))
print(lv.head(8).to_string(index=False))
for c in lv.columns:
    if "block" in c.lower() and lv[c].dtype.kind in "if":
        print("    %-40s min=%.1f median=%.1f max=%.1f"
              % (c, lv[c].min(), lv[c].median(), lv[c].max()))

json.dump(O, open(os.path.join(HERE, "_s02_probe.json"), "w"), indent=2, default=str)
print("\nwrote _s02_probe.json, _fold_factors_E0_I0014.csv")
print("DONE s02 probe")
