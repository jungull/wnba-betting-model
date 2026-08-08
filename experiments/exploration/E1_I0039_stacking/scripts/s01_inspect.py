"""E1_I0039 s01 -- INSPECT ONLY.  Reads nothing outside 2021-2024.  Writes nothing but a log.

Purpose: find the columns that define each of the three components' row sets, and confirm a
common key exists across the three source screens' frames.
"""
import os
import sys

import numpy as np
import pandas as pd

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 100)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")

FRAMES = {
    "I0032_work": os.path.join(EXP, "E1_I0032_aggregate_stack", "_work.parquet"),
    "I0020_tier": os.path.join(EXP, "E1_I0020_coldstart_tiering", "tier_frame.parquet"),
    "I0034_rem": os.path.join(EXP, "E1_I0034_redistribution", "_rem_frame.parquet"),
    "I0034_player": os.path.join(EXP, "E1_I0034_redistribution", "_player_frame.parquet"),
    "I0034_tg": os.path.join(EXP, "E1_I0034_redistribution", "_tg_frame.parquet"),
}

for name, path in FRAMES.items():
    print("=" * 110)
    print(name, path)
    if not os.path.exists(path):
        print("  MISSING")
        continue
    d = pd.read_parquet(path)
    print("  shape", d.shape)
    if "season" in d.columns:
        print("  seasons", sorted(pd.unique(d["season"]).tolist()))
    print("  columns (%d):" % len(d.columns))
    for i in range(0, len(d.columns), 6):
        print("     ", list(d.columns[i:i + 6]))
    print("  head:")
    print(d.head(3).to_string())
