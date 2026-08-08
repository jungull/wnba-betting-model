"""Does player_bios.csv carry PER-SEASON values, or one current-state pull replicated
across a player's season rows? Decides whether a 2021 row's `age`/`weight_lbs`/`position_raw`
is an as-of-2021 fact or an as-of-pull-date (2026) fact.

EXPLORATION PARTITION: this probe reads ONLY rows whose season is in 2021-2024.
No 2025/2026 row is loaded into the comparison.
"""
import os
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
PART = [2021, 2022, 2023, 2024]

b = pd.read_csv(os.path.join(ROOT, "data", "reference", "player_bios.csv"))
print("raw seasons present in file:", sorted(b["season"].unique()))
b = b[b["season"].isin(PART)].copy()          # FILTER-POINT (column values, not bytes)
print("after partition filter, seasons:", sorted(b["season"].unique()), "rows:", len(b))

multi = b.groupby("player_id")["season"].nunique()
multi = multi[multi > 1].index
m = b[b["player_id"].isin(multi)]
print("players with >1 partition season:", len(multi), " rows:", len(m))

for col in ["age", "height_inches", "weight_lbs", "position_raw", "college", "country"]:
    if col not in m.columns:
        continue
    nun = m.groupby("player_id")[col].nunique(dropna=True)
    varying = int((nun > 1).sum())
    print("  %-14s varies across seasons for %d / %d multi-season players"
          % (col, varying, len(multi)))

# If `age` is a current-state pull it will be CONSTANT across a player's seasons.
if "age" in m.columns:
    sub = m[m["player_id"].isin(multi)].sort_values(["player_id", "season"])
    ex = sub.groupby("player_id").filter(lambda g: g["season"].nunique() >= 3).head(12)
    print("\nexample rows (age by season):")
    print(ex[["player_id", "player_name", "season", "age", "height_inches", "weight_lbs",
              "position_raw"]].to_string(index=False))
