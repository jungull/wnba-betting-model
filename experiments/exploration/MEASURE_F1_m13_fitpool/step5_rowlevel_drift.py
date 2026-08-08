#!/usr/bin/env python3
"""Per-row drift between the published pooled probabilities and each
counterfactual -- the number that answers "how wrong is any single quoted
p_over?". Compared against M13's own published cross-variant sensitivity
(rmse_normal_vs_student_t etc.) so the leak's size is put on the same scale as
a disagreement the node already treats as tolerable."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[2]
M13 = WORKTREE / "experiments" / "market_program" / "M13_PLAYER_VALUE_TRANSLATION"
PUB13 = json.loads((M13 / "FINDINGS.json").read_text(encoding="utf-8"))

VARS = ["normal", "student_t", "empirical", "het_normal"]
base = pd.read_parquet(M13 / "translation_rows.parquet").set_index("row_uid").sort_index()

out = {
    "m13_published_cross_variant_sensitivity_A_primary":
        PUB13["calibration"]["cells"]["A_primary"]["sensitivity_across_variants"],
    "drift_vs_published": {},
}
for tag in ("A_POOLED_PUBLISHED", "B_POOLED_2022_2024", "C_TIME_ORDERED",
            "D_TIME_ORDERED_2022_2024"):
    p = HERE / f"cf_{tag}" / "translation_rows.parquet"
    if not p.exists():
        continue
    cf = pd.read_parquet(p).set_index("row_uid").sort_index()
    common = base.index.intersection(cf.index)
    b, c = base.loc[common], cf.loc[common]
    rec = {"n_rows_compared": int(len(common)),
           "n_rows_published": int(len(base)), "n_rows_variant": int(len(cf))}
    for v in VARS:
        d = c[f"p_over_{v}"].to_numpy() - b[f"p_over_{v}"].to_numpy()
        rec[v] = {
            "rmse": float(np.sqrt(np.mean(d ** 2))),
            "mean_signed": float(d.mean()),
            "max_abs": float(np.abs(d).max()),
            "p95_abs": float(np.percentile(np.abs(d), 95)),
            "call_flip_rate_vs_0p5": float(np.mean((b[f"p_over_{v}"] > 0.5) != (c[f"p_over_{v}"] > 0.5))),
        }
    out["drift_vs_published"][tag] = rec
    print(tag, "student_t rmse", round(rec["student_t"]["rmse"], 6),
          "max_abs", round(rec["student_t"]["max_abs"], 6),
          "call_flip", round(rec["student_t"]["call_flip_rate_vs_0p5"], 6))

sens = out["m13_published_cross_variant_sensitivity_A_primary"]
c = out["drift_vs_published"].get("C_TIME_ORDERED", {}).get("student_t", {})
if c:
    out["scale_comparison"] = {
        "leak_rmse_student_t_pooled_vs_time_ordered": c["rmse"],
        "m13_own_rmse_normal_vs_student_t": sens["rmse_normal_vs_student_t"],
        "m13_own_rmse_normal_vs_empirical": sens["rmse_normal_vs_empirical"],
        "leak_rmse_as_multiple_of_normal_vs_student_t": c["rmse"] / sens["rmse_normal_vs_student_t"],
        "leak_rmse_as_multiple_of_normal_vs_empirical": c["rmse"] / sens["rmse_normal_vs_empirical"],
        "leak_call_flip_rate": c["call_flip_rate_vs_0p5"],
        "m13_own_call_flip_normal_vs_empirical": sens["call_flip_rate_normal_vs_empirical"],
    }
    print()
    print(json.dumps(out["scale_comparison"], indent=1))

(HERE / "step5_rowlevel_drift.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("wrote step5_rowlevel_drift.json")
