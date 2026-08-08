"""E1_I0027 s02b -- READ-ONLY: decode D094's selected grid indices into (mode, memory, shrink, floor)."""
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
D094 = os.path.join(EXP, "E1_I0022_optimal_simple_estimator")

sk = pd.read_parquet(os.path.join(D094, "surface_keys.parquet"))
print("surface_keys shape=%s cols=%s" % (sk.shape, list(sk.columns)))
print(sk.head(5).to_string())
print("\nrows per target:")
print(sk.groupby("target").size() if "target" in sk.columns else "no target col")

z = np.load(os.path.join(D094, "selected_cells.npz"), allow_pickle=True)
sel = {k: int(z[k]) for k in z.files}
print("\nselected: %s" % sel)

print("\n--- GLOBAL indexing into surface_keys (15,048 rows) ---")
for t in ["pts", "minutes", "fga", "ppm"]:
    for tag in ["idx_A", "idx_B", "idx_insample"]:
        i = sel["%s_%s" % (t, tag)]
        r = sk.iloc[i].to_dict()
        print("%-8s %-13s idx=%-6d target_in_row=%-8s %s"
              % (t, tag, i, r["target"], {k: v for k, v in r.items() if k != "target"}))

print("\n--- WITHIN-TARGET indexing (for comparison) ---")
for t in ["pts", "minutes", "fga", "ppm"]:
    sub = sk.loc[sk["target"] == t].reset_index(drop=True)
    for tag in ["idx_A", "idx_B", "idx_insample"]:
        i = sel["%s_%s" % (t, tag)]
        if i < len(sub):
            print("%-8s %-13s idx=%-6d %s"
                  % (t, tag, i, {k: v for k, v in sub.iloc[i].to_dict().items() if k != "target"}))
        else:
            print("%-8s %-13s idx=%-6d OUT OF BOUNDS (n=%d)" % (t, tag, i, len(sub)))

surf = pd.read_csv(os.path.join(D094, "estimator_surface.csv"))
print("\nestimator_surface cols=%s shape=%s" % (list(surf.columns), surf.shape))
print(surf.head(3).to_string())
# marginal evidence for the two claims we reuse
if {"target", "shrink_kind", "floor"} <= set(surf.columns):
    mc = [c for c in surf.columns if "mae" in c.lower()][:1]
    if mc:
        m = mc[0]
        print("\nbest MAE by (target, shrink_kind):")
        print(surf.groupby(["target", "shrink_kind"])[m].min().unstack().to_string())
        print("\nbest MAE by (target, floor):")
        print(surf.groupby(["target", "floor"])[m].min().unstack().to_string())
        print("\nbest MAE by (target, memory_kind):")
        print(surf.groupby(["target", "memory_kind"])[m].min().unstack().to_string())
