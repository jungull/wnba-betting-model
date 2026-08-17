"""S00 -- SCHEMA PROBE ONLY.  No statistic is computed here.

Purpose: establish (a) that the artifacts exist and are readable, (b) their columns,
(c) the partition they carry, so PREREG.md can name row sets concretely.
PARTITION: 2021-2024 only.  2025/2026 is NEVER read, joined, filtered against,
counted, described or plotted.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(os.path.join(HERE, ".."))
EXP = os.path.abspath(os.path.join(OUT, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
SRC = os.path.join(EXP, "E1_I0004_shot_selection")
PARTITION = [2021, 2022, 2023, 2024]

pd.set_option("display.width", 220)


def hdr(s):
    print("\n" + "=" * 96)
    print(s)
    print("=" * 96)


hdr("A. published selection_frame.parquet")
SEL = pd.read_parquet(os.path.join(SRC, "selection_frame.parquet"))
print("  columns:", list(SEL.columns))
print("  rows:", len(SEL))
print("  seasons:", sorted(SEL["season"].unique()))
assert set(SEL["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
print("  dtypes:\n", SEL.dtypes.to_string())
print("\n  rows per zone:")
print(SEL.groupby("zone").size().to_string())
print("\n  player-games (pid,season,game_id):",
      SEL[["player_id", "season", "game_id"]].drop_duplicates().shape[0])
print("  zones per player-game value_counts:")
print(SEL.groupby(["player_id", "season", "game_id"]).size().value_counts().to_string())

hdr("B. raw shotcharts, partition files only")
tot = 0
for ssn in PARTITION:
    for t in ["regular", "playoffs"]:
        f = os.path.join(ROOT, "data", "shotcharts", f"shots_{ssn}_{t}.parquet")
        d = pd.read_parquet(f)
        tot += len(d)
        if ssn == 2021 and t == "regular":
            print("  columns:", list(d.columns))
        print(f"    shots_{ssn}_{t}.parquet  rows={len(d)}")
print("  total shot rows 2021-2024 =", tot)

hdr("C. master_player.parquet (asof_granularity == 'row', usable filtered)")
mp = pd.read_parquet(os.path.join(ROOT, "data", "masters", "master_player.parquet"))
print("  columns:", list(mp.columns))
print("  all seasons present in file:", sorted(mp["season"].unique()))
# FILTER-POINT: partition restriction, immediately.
mp = mp[mp["season"].isin(PARTITION)].copy()
print("  AFTER FILTER seasons:", sorted(mp["season"].unique()))
assert set(mp["season"].unique()) <= set(PARTITION), "PARTITION VIOLATION"
print("  rows:", len(mp))
print("  season_type value_counts:")
print(mp["season_type"].value_counts().to_string())
print("  minutes>0 rows:", int((pd.to_numeric(mp["minutes"], errors="coerce") > 0).sum()))
print("\nDone.  NO STATISTIC WAS COMPUTED.")
