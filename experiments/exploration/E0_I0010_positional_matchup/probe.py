"""Probe master_player schema. E0 I0010. Partition: 2021-2024 only."""
import pandas as pd
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
mp = pd.read_parquet(ROOT + r"\data\masters\master_player.parquet")
# FILTER-POINT: exploration partition, applied immediately after load
mp = mp[mp["season"].isin([2021, 2022, 2023, 2024])].copy()
assert set(mp["season"].unique()) <= {2021, 2022, 2023, 2024}
print("seasons:", sorted(mp["season"].unique()))
print("shape:", mp.shape)
print("\ncolumns:")
for c in mp.columns:
    print("  ", c, mp[c].dtype)
print("\nseason_type:", mp["season_type"].value_counts().to_dict())
print("\nhead:")
pd.set_option("display.width", 250)
print(mp.head(3).T.to_string())
