"""E0 I0011 - quick EDA on the exploration partition only (2021-2024)."""
import pandas as pd, numpy as np

PARTITION = [2021, 2022, 2023, 2024]
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"

df = pd.read_parquet(ROOT + r"\data\masters\master_player.parquet")
df = df[df["season"].isin(PARTITION)].copy()  # FILTER-POINT
assert set(df["season"].unique()) <= set(PARTITION), df["season"].unique()
print("seasons after filter:", sorted(df["season"].unique()))
print("shape:", df.shape)
print("season_type:\n", df["season_type"].value_counts(dropna=False))
print("rows per season:\n", df.groupby("season").size())

for c in ["minutes", "pts", "reb", "ast", "possessions", "pace", "usage_percentage",
          "starter_flag", "position", "is_home", "dnp_reason"]:
    s = df[c]
    if s.dtype.kind in "if":
        print(c, s.dtype, "null%", round(s.isna().mean() * 100, 2),
              {k: round(v, 3) for k, v in s.describe().to_dict().items()})
    else:
        print(c, s.dtype, "null%", round(s.isna().mean() * 100, 2),
              s.value_counts(dropna=False).head(8).to_dict())

print("game_date dtype", df["game_date"].dtype, df["game_date"].min(), df["game_date"].max())
print("players per season:", df.groupby("season")["player_id"].nunique().to_dict())
d = df[df["minutes"] > 0]
print("minutes>0 rows:", len(d))
print("games per player-season (minutes>0) describe:",
      d.groupby(["season", "player_id"]).size().describe().to_dict())

# team master
tm = pd.read_parquet(ROOT + r"\data\masters\master_team.parquet")
tm = tm[tm["season"].isin(PARTITION)].copy()  # FILTER-POINT
print("team master seasons:", sorted(tm["season"].unique()), tm.shape)
print("team cols:", list(tm.columns))
