"""E1_I0042 s00 -- STRUCTURAL PROBE ONLY.  No cell is evaluated here and no response is
compared between arms.  This step exists to establish which columns exist, at what level, and
with what season coverage, so the preregistration can name an EXPLICIT allowlist rather than a
substring match.  Runs BEFORE PREREG.md is hashed, and is declared as such in PREREG.md s0.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 300)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")
SRC_REDIST = os.path.join(EXP, "E1_I0034_redistribution")
SRC_STACK39 = os.path.join(EXP, "E1_I0039_stacking")

SEALED = (2025, 2026)


def guard(df, label):
    v = sorted(set(pd.unique(pd.to_numeric(df["season"], errors="coerce")).tolist()))
    bad = [s for s in v if s in SEALED]
    assert not bad, "PARTITION VIOLATION %s: %s" % (label, bad)
    print("  %-18s seasons=%s  n=%d  cols=%d" % (label, v, len(df), df.shape[1]))


for name, path in (("player_frame", os.path.join(SRC_REDIST, "_player_frame.parquet")),
                   ("rem_frame", os.path.join(SRC_REDIST, "_rem_frame.parquet")),
                   ("tg_frame", os.path.join(SRC_REDIST, "_tg_frame.parquet")),
                   ("fit39", os.path.join(SRC_STACK39, "_fit.parquet"))):
    d = pd.read_parquet(path)
    print("\n=== %s  %s" % (name, path))
    guard(d, name)
    print("  columns: %s" % list(d.columns))
    if name in ("rem_frame", "fit39"):
        print(d.groupby("season").size().to_string())

print("\n=== rem_frame numeric summary of the quantities the claim is about")
r = pd.read_parquet(os.path.join(SRC_REDIST, "_rem_frame.parquet"))
for c in ("freed_minutes", "u_minutes", "uz_minutes", "z_minutes", "n_rem", "n_absent"):
    if c in r.columns:
        v = pd.to_numeric(r[c], errors="coerce")
        print("  %-16s finite=%d  min=%.4f  med=%.4f  max=%.4f  nzero=%d"
              % (c, int(np.isfinite(v).sum()), np.nanmin(v), np.nanmedian(v), np.nanmax(v),
                 int((v == 0).sum())))

print("\n=== per-season team-game and row counts on rem_frame, RS only")
r["tg"] = r["game_id"].astype(str) + "_" + r["team_id"].astype(str)
g = r.groupby("season").agg(rows=("row_uid", "size"), tgs=("tg", "nunique"))
print(g.to_string())
