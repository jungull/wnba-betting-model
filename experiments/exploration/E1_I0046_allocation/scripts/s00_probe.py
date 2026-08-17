"""E1_I0046 s00 -- READ-ONLY probe of candidate source frames. Writes nothing outside this screen."""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 500)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")

paths = {
    "E0_I0016": os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_frame.parquet"),
    "E1_I0018": os.path.join(EXP, r"E1_I0018_teammate_volume_channel\screen_frame.parquet"),
    "I0033_player": os.path.join(EXP, r"E1_I0033_aggregation_level\_player_frame.parquet"),
    "I0033_team": os.path.join(EXP, r"E1_I0033_aggregation_level\_team_frame.parquet"),
    "I0034_player": os.path.join(EXP, r"E1_I0034_redistribution\_player_frame.parquet"),
    "I0034_tg": os.path.join(EXP, r"E1_I0034_redistribution\_tg_frame.parquet"),
    "master_player": os.path.join(ROOT, r"data\masters\master_player.parquet"),
    "master_team": os.path.join(ROOT, r"data\masters\master_team.parquet"),
}

for k, p in paths.items():
    print("=" * 100)
    print(k, p, "EXISTS" if os.path.exists(p) else "MISSING")
    if not os.path.exists(p):
        continue
    df = pd.read_parquet(p)
    print("  shape", df.shape)
    print("  cols:", list(df.columns))
    for c in df.columns:
        if "season" in c.lower():
            try:
                print("   ", c, "uniques:", sorted(pd.unique(df[c]))[:12])
            except Exception as e:
                print("   ", c, "unsortable", e)
    print(df.head(3).to_string())
