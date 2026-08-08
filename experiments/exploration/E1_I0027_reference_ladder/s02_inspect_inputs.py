"""E1_I0027 s02 -- READ-ONLY: D094's selected cells, the defence frame's keys, D092's artefacts."""
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("D094 (E1_I0022) selected_cells.npz -- the tuned estimator per target")
z = np.load(os.path.join(EXP, r"E1_I0022_optimal_simple_estimator\selected_cells.npz"),
            allow_pickle=True)
for k in z.files:
    print("  %-30s %s" % (k, z[k]))

hdr("D094 _s04.json selection block")
j = json.load(open(os.path.join(EXP, r"E1_I0022_optimal_simple_estimator\_s04.json"),
                   encoding="utf-8"))
print(json.dumps(j, indent=1, default=str)[:5000])

hdr("D094 estimator_surface.csv -- header + the rows for the selected forms")
sf = pd.read_csv(os.path.join(EXP, r"E1_I0022_optimal_simple_estimator\estimator_surface.csv"))
print("  shape=%s  cols=%s" % (sf.shape, list(sf.columns)))
print(sf.head(3).to_string())

hdr("D085/D098 defence frame E0_I0016 screen_frame.parquet -- keys and A10")
ef = pd.read_parquet(os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_frame.parquet"))
print("  shape=%s" % (ef.shape,))
print("  cols: %s" % list(ef.columns))

hdr("D092 placeholders_pts.csv header")
ph = pd.read_csv(os.path.join(EXP, r"E1_I0020_coldstart_tiering\placeholders_pts.csv"), nrows=5)
print("  cols: %s" % list(ph.columns))
print(ph.to_string())

hdr("D092 pooled_operating_rule.csv")
print(pd.read_csv(os.path.join(EXP,
      r"E1_I0020_coldstart_tiering\pooled_operating_rule.csv")).to_string())

hdr("D089 walkforward_points.csv")
print(pd.read_csv(os.path.join(EXP,
      r"E1_I0018_teammate_volume_channel\walkforward_points.csv")).to_string())
