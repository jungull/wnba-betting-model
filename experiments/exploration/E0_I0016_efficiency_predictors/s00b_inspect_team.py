"""E0_I0016 s00b -- inspect master_team + key master_player value ranges. READ ONLY."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
sys.path.insert(0, os.path.join(ROOT, r"experiments\exploration\_screen_kit"))
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 300)
pd.set_option("display.max_rows", 300)

mt = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_team.parquet"))
print("master_team shape", mt.shape)
print("columns:", list(mt.columns))
print()
print(mt.head(2).T.to_string())

mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"))
print("\nmaster_player seasons:", sorted(mp["season"].unique()))
print("season_type:", mp["season_type"].value_counts().to_dict())
print("source:", mp["source"].value_counts().to_dict())
print("era:", mp["era"].value_counts().to_dict())
mp4 = mp[mp["season"].isin([2021, 2022, 2023, 2024])].copy()
print("\n2021-2024 rows:", len(mp4))
print("game_date sample:", mp4["game_date"].head(3).tolist())
for c in ["minutes", "fga", "fta", "pts", "fouls_drawn", "pf", "points_paint",
          "points_fast_break", "possessions", "blocks_against", "starter_flag",
          "true_shooting_percentage", "effective_field_goal_percentage",
          "estimated_usage_percentage", "opp_points_paint"]:
    s = pd.to_numeric(mp4[c], errors="coerce")
    print("  %-32s nonnull=%6d  min=%9.3f  med=%9.3f  max=%9.3f"
          % (c, s.notna().sum(), np.nanmin(s), np.nanmedian(s), np.nanmax(s)))
print("\nrows with minutes>0:", int((pd.to_numeric(mp4['minutes'], errors='coerce') > 0).sum()))
print("dnp_reason nonempty:", int(mp4["dnp_reason"].notna().sum()))
print("distinct games:", mp4["game_id"].nunique(), " distinct players:", mp4["player_id"].nunique())
print("\nteam_id/opp_team_id null:", mp4["team_id"].isna().sum(), mp4["opp_team_id"].isna().sum())
print("\nper-game team row counts (players per team-game) describe:")
print(mp4.groupby(["game_id", "team_id"]).size().describe().to_string())
