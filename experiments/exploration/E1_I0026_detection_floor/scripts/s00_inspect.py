"""s00_inspect.py -- read-only reconnaissance of candidate frames.
Writes a plain-text report; touches nothing outside E1_I0026_detection_floor.
"""
import os, sys, json
import pandas as pd
import numpy as np

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
OUT = os.path.join(EXPL, "E1_I0026_detection_floor", "out")
os.makedirs(OUT, exist_ok=True)

CANDIDATES = [
    ("E1_I0018_teammate_volume_channel", "screen_frame.parquet"),
    ("E0_I0016_efficiency_predictors", "screen_frame.parquet"),
    ("E0_I0017_shot_quality_efficiency", "screen_frame.parquet"),
    ("E0_I0024_reb_ast_characterisation", "screen_frame.parquet"),
    ("E0_I0015_points_skill_decomposition", "decomp_frame.parquet"),
]

lines = []
def p(s=""):
    lines.append(str(s))
    print(s)

for d, f in CANDIDATES:
    path = os.path.join(EXPL, d, f)
    p("=" * 100)
    p("FRAME: %s / %s" % (d, f))
    if not os.path.exists(path):
        p("  MISSING")
        continue
    try:
        df = pd.read_parquet(path)
    except Exception as e:
        p("  READ FAIL: %r" % (e,))
        continue
    p("  shape: %s" % (df.shape,))
    p("  columns (%d):" % len(df.columns))
    for c in df.columns:
        s = df[c]
        nn = int(s.notna().sum())
        try:
            nu = int(s.nunique(dropna=True))
        except Exception:
            nu = -1
        extra = ""
        if pd.api.types.is_numeric_dtype(s) and nn:
            extra = " min=%.6g max=%.6g mean=%.6g" % (
                float(np.nanmin(s.values.astype(float))),
                float(np.nanmax(s.values.astype(float))),
                float(np.nanmean(s.values.astype(float))),
            )
        p("    %-42s %-12s nn=%-7d nuniq=%-7d%s" % (c, str(s.dtype), nn, nu, extra))
    # season / date reconnaissance
    for c in df.columns:
        lc = c.lower()
        if lc == "season" or lc.endswith("_season"):
            try:
                p("  SEASONS in %s: %s" % (c, sorted(pd.unique(df[c].dropna()))[:12]))
            except Exception:
                pass
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            p("  DATERANGE %s: %s .. %s" % (c, df[c].min(), df[c].max()))

with open(os.path.join(OUT, "s00_inspect.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("\nwrote", os.path.join(OUT, "s00_inspect.txt"))
