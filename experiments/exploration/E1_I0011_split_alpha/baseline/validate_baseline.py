"""Validate corrected_baseline.py end to end and emit BASELINE_PERFORMANCE.json.

Three jobs:
  1. EQUIVALENCE. The module, run from master_player.parquet, must reproduce the
     E1 grid's MAE for the same (alpha_eff, alpha_exp) cell to 1e-9. If it does
     not, the module and the screen are two different estimators and neither
     number means anything.
  2. PERFORMANCE. Per-season and per-fold MAE of the corrected baseline against
     the program incumbent and the naive season-to-date mean.
  3. WARM-UP. What the baseline does on rows the gate excludes (n_prior 1-2),
     so the downstream screen knows what it is inheriting there.

PARTITION: 2021-2024 only. The 2025/2026 holdout is never read.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from corrected_baseline import (ALPHA_EFF, ALPHA_EXP, ALPHA_EXP_PER_TARGET,  # noqa: E402
                                BASELINE_ID, CorrectedOwnRateBaseline)

PARTITION = [2021, 2022, 2023, 2024]
TARGETS = ["pts", "reb", "ast"]

frame = pd.read_parquet(os.path.join(EXP, "frame.parquet"))
if not set(frame["season"].unique()) <= set(PARTITION):
    raise SystemExit("PARTITION VIOLATION")
print("[partition-check] frame seasons:",
      sorted(int(x) for x in frame["season"].unique()), frame.shape)

grid = pd.read_parquet(os.path.join(EXP, "grid_metrics.parquet"))
grid = grid[(grid["slice"] == "ALL") & (grid.half == 0)]

INC = CorrectedOwnRateBaseline(0.30, 0.30)                    # props_edge.py
BASE = CorrectedOwnRateBaseline(ALPHA_EFF, ALPHA_EXP)         # the corrected baseline
BASE_PT = CorrectedOwnRateBaseline(ALPHA_EFF, "per_target")   # per-target exposure


def mae(pred, y, m):
    e = (pred - y).abs()[m]
    e = e[np.isfinite(e)]
    return float(e.mean()), int(len(e))


report = {"baseline_id": BASELINE_ID, "alpha_eff": ALPHA_EFF, "alpha_exp": ALPHA_EXP,
          "alpha_exp_per_target": ALPHA_EXP_PER_TARGET, "min_prior": 3,
          "partition": PARTITION, "eval_gate": "minutes > 0 and n_prior >= 3",
          "equivalence_check": {}, "per_season": {}, "folds": {}, "warmup": {}}

# ------------------------------------------------------------------ 1. equivalence
print("\n" + "=" * 96)
print("EQUIVALENCE CHECK -- module output vs the E1 grid, same cell, same rows")
print("=" * 96)
preds = {}
for tgt in TARGETS:
    y = frame[tgt].astype(float)
    gate = BASE.n_prior(frame, tgt) >= 3
    m_all = gate & (frame["minutes"] > 0)
    preds[tgt] = {"BASE": BASE.project(frame, tgt), "INC": INC.project(frame, tgt),
                  "BASE_PT": BASE_PT.project(frame, tgt)}
    for nm, obj, cell in [("corrected", preds[tgt]["BASE"], (ALPHA_EFF, ALPHA_EXP)),
                          ("incumbent", preds[tgt]["INC"], (0.30, 0.30))]:
        for s in PARTITION:
            mod, n = mae(obj, y, m_all & (frame["season"] == s))
            g = grid[(grid.target == tgt) & (grid.form == "PER36") &
                     np.isclose(grid.alpha_eff, cell[0]) &
                     np.isclose(grid.alpha_exp, cell[1]) & (grid.season == s)]
            ref, nref = float(g["mae"].iloc[0]), int(g["n"].iloc[0])
            d = abs(mod - ref)
            ok = d < 1e-9 and n == nref
            print(f"  {tgt:<4} {nm:<10} {s}  module {mod:.9f}  grid {ref:.9f}  "
                  f"|d| {d:.2e}  n {n}/{nref}  {'MATCH' if ok else 'MISMATCH'}")
            report["equivalence_check"][f"{tgt}_{nm}_{s}"] = dict(
                module_mae=mod, grid_mae=ref, abs_diff=d, n_module=n, n_grid=nref, match=ok)
            if not ok:
                raise SystemExit("EQUIVALENCE FAILED -- module != screen")
print("  all equivalence checks MATCH.")

# --------------------------------------------------------------- 2. per-season MAE
print("\n" + "=" * 96)
print("PER-SEASON MAE. The corrected baseline is a FROZEN estimator -- nothing is fit")
print("on any season -- so every season below is out-of-sample in the only sense that")
print("matters for a baseline.")
print("=" * 96)
print(f"{'target':<7}{'season':<8}{'n':>7}{'corrected':>12}{'per-target':>12}"
      f"{'incumbent':>12}{'naive STD':>12}{'vs INC%':>10}{'vs naive%':>11}")
for tgt in TARGETS:
    y = frame[tgt].astype(float)
    gate = BASE.n_prior(frame, tgt) >= 3
    m_all = gate & (frame["minutes"] > 0)
    report["per_season"][tgt] = {}
    for s in PARTITION:
        m = m_all & (frame["season"] == s)
        b, n = mae(preds[tgt]["BASE"], y, m)
        bp, _ = mae(preds[tgt]["BASE_PT"], y, m)
        i, _ = mae(preds[tgt]["INC"], y, m)
        nv = float(grid[(grid.target == tgt) & (grid.form == "STD") &
                        (grid.season == s)]["mae"].iloc[0])
        print(f"{tgt:<7}{s:<8}{n:>7}{b:>12.4f}{bp:>12.4f}{i:>12.4f}{nv:>12.4f}"
              f"{100 * (i - b) / i:>10.3f}{100 * (nv - b) / nv:>11.3f}")
        report["per_season"][tgt][str(s)] = dict(
            n=n, mae_corrected=b, mae_corrected_per_target=bp, mae_incumbent=i,
            mae_naive_std=nv, pct_better_than_incumbent=100 * (i - b) / i,
            pct_better_than_naive=100 * (nv - b) / nv)

print("\nAcross the four seasons (mean +- sd of the % gap):")
for tgt in TARGETS:
    d = report["per_season"][tgt]
    vi = np.array([d[str(s)]["pct_better_than_incumbent"] for s in PARTITION])
    vn = np.array([d[str(s)]["pct_better_than_naive"] for s in PARTITION])
    print(f"  {tgt:<5} vs incumbent {vi.mean():+.3f}% sd {vi.std(ddof=1):.3f} "
          f"(4/4 positive: {bool((vi > 0).all())})   "
          f"vs naive {vn.mean():+.3f}% sd {vn.std(ddof=1):.3f} "
          f"(4/4 positive: {bool((vn > 0).all())})")
    report["per_season"][tgt]["summary"] = dict(
        mean_vs_incumbent_pct=float(vi.mean()), sd_vs_incumbent_pct=float(vi.std(ddof=1)),
        mean_vs_naive_pct=float(vn.mean()), sd_vs_naive_pct=float(vn.std(ddof=1)),
        all_seasons_positive_vs_incumbent=bool((vi > 0).all()),
        all_seasons_positive_vs_naive=bool((vn > 0).all()))

# ------------------------------------------- 2b. hygiene variant: refit per LOSO fold
print("\n" + "=" * 96)
print("HYGIENE VARIANT -- alphas REFIT with .fit() on the three training seasons of")
print("each LOSO fold, then scored on the held-out season. Confirms the frozen")
print("constants are not doing work that per-fold refitting would undo.")
print("NOTE: .fit() here uses a COARSE grid purely to exercise the public API at")
print("acceptable cost. The full 14x14 per-fold re-selection is done efficiently in")
print("../folds.py (arm SPLIT_tuned) and that is the authoritative version.")
print("=" * 96)
COARSE = (0.00, 0.03, 0.10, 0.20, 0.30, 0.50)
print(f"{'target':<7}{'held-out':<10}{'refit eff/exp':<16}{'refit MAE':>11}"
      f"{'frozen MAE':>12}{'frozen - refit':>16}")
for tgt in TARGETS:
    y = frame[tgt].astype(float)
    gate = BASE.n_prior(frame, tgt) >= 3
    m_all = gate & (frame["minutes"] > 0)
    report["folds"][tgt] = {}
    for s in PARTITION:
        tr = frame[frame["season"].isin([x for x in PARTITION if x != s])]
        fitted = BASE.fit(tr, tgt, alphas=COARSE)
        m = m_all & (frame["season"] == s)
        rm, _ = mae(fitted.project(frame, tgt), y, m)
        fm, _ = mae(preds[tgt]["BASE"], y, m)
        print(f"{tgt:<7}{s:<10}{'%.2f / %.2f' % (fitted.alpha_eff, fitted.alpha_exp):<16}"
              f"{rm:>11.4f}{fm:>12.4f}{fm - rm:>+16.5f}")
        report["folds"][tgt][str(s)] = dict(
            refit_alpha_eff=fitted.alpha_eff, refit_alpha_exp=fitted.alpha_exp,
            mae_refit=rm, mae_frozen=fm, frozen_minus_refit=fm - rm)

# ------------------------------------------------------------------- 3. warm-up rule
print("\n" + "=" * 96)
print("WARM-UP -- rows the gate EXCLUDES (n_prior 1-2). What should a caller do there?")
print("=" * 96)
print(f"{'target':<7}{'n rows':>8}{'warmup=std MAE':>17}{'split-alpha MAE':>18}"
      f"{'incumbent MAE':>16}{'best option':>16}")
# warmup="std" only fires on 1 <= n_prior < min_prior, so min_prior must stay at 3.
WARM = CorrectedOwnRateBaseline(ALPHA_EFF, ALPHA_EXP, min_prior=3, warmup="std")
NOGATE = CorrectedOwnRateBaseline(ALPHA_EFF, ALPHA_EXP, min_prior=1)
INC1 = CorrectedOwnRateBaseline(0.30, 0.30, min_prior=1)
for tgt in TARGETS:
    y = frame[tgt].astype(float)
    npri = BASE.n_prior(frame, tgt)
    m = (npri >= 1) & (npri <= 2) & (frame["minutes"] > 0)
    a, n = mae(WARM.project(frame, tgt), y, m)
    b, _ = mae(NOGATE.project(frame, tgt), y, m)
    c, _ = mae(INC1.project(frame, tgt), y, m)
    best = min([("warmup_std", a), ("split_alpha", b), ("incumbent", c)],
               key=lambda t: t[1])[0]
    print(f"{tgt:<7}{n:>8}{a:>17.4f}{b:>18.4f}{c:>16.4f}{best:>16}")
    report["warmup"][tgt] = dict(n=n, mae_warmup_std=a, mae_split_alpha_ungated=b,
                                 mae_incumbent_ungated=c, best=best)

with open(os.path.join(HERE, "BASELINE_PERFORMANCE.json"), "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2)
print("\nwrote BASELINE_PERFORMANCE.json")
