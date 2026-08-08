"""E1_I0032 s01 -- READ-ONLY inventory of every frame this stack needs.

Nothing is computed here beyond shapes, columns, dtypes and season coverage.
Forbidden directories (E0_I0029_freethrow_hurdle, E1_I0031_rapm_as_prior) are never touched.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
pd.set_option("display.width", 200)

FORBIDDEN = ("E0_I0029_freethrow_hurdle", "E1_I0031_rapm_as_prior")


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def describe(path, label, maxcols=400):
    if any(f in path for f in FORBIDDEN):
        raise SystemExit("REFUSED: forbidden directory %s" % path)
    if not os.path.exists(path):
        print("  MISSING: %s" % path)
        return None
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    print("  %-38s shape=%s" % (label, (df.shape,)))
    print("    cols(%d): %s" % (len(df.columns), list(df.columns)[:maxcols]))
    if "season" in df.columns:
        print("    seasons: %s" % sorted(pd.unique(df["season"].dropna()).tolist()))
    return df


hdr("A. candidate frames")
FRAMES = {
    "TV  E1_I0018 screen_frame": r"E1_I0018_teammate_volume_channel\screen_frame.parquet",
    "EFF E0_I0016 screen_frame": r"E0_I0016_efficiency_predictors\screen_frame.parquet",
    "TIER E1_I0020 tier_frame": r"E1_I0020_coldstart_tiering\tier_frame.parquet",
    "REBAST E0_I0024 screen_frame": r"E0_I0024_reb_ast_characterisation\screen_frame.parquet",
}
out = {}
for k, rel in FRAMES.items():
    out[k] = describe(os.path.join(EXP, rel), k)

hdr("B. directory listings for the champion-output screens")
for d in ("E0_I0028_degeneracy_sweep", "E0_I0019_availability_forecast",
          "E1_I0030_home_advantage_accounting", "E1_I0020_coldstart_tiering",
          "E1_I0018_teammate_volume_channel", "E1_I0022_optimal_simple_estimator",
          "E1_I0026_detection_floor"):
    p = os.path.join(EXP, d)
    if not os.path.isdir(p):
        print("  MISSING DIR %s" % d)
        continue
    names = sorted(os.listdir(p))
    print("  %-38s %s" % (d, [n for n in names if not n.startswith("run_log")]))

hdr("C. forecasts/ tree (the champion's stored outputs)")
FC = os.path.join(ROOT, "forecasts")
for dirpath, dirnames, filenames in os.walk(FC):
    rel = os.path.relpath(dirpath, FC)
    depth = 0 if rel == "." else rel.count(os.sep) + 1
    if depth > 2:
        dirnames[:] = []
        continue
    show = [f for f in filenames if f.endswith((".parquet", ".csv"))]
    if show or depth <= 1:
        print("  %-70s %d files %s" % (rel, len(filenames), show[:12]))
