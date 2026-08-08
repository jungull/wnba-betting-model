"""Probe: shot-chart schema + manifest inventory. Partition 2021-2024 only."""
import glob
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARTITION = [2021, 2022, 2023, 2024]

d = pd.read_parquet(os.path.join(REPO, "data", "shotcharts", "shots_2021_regular.parquet"))
print("shots_2021_regular columns:")
print(list(d.columns))
print(d.dtypes.to_string())
print("\nhead:")
print(d.head(3).to_string())
print("\nSHOT_ZONE_BASIC value counts:")
print(d["SHOT_ZONE_BASIC"].value_counts().to_string())
print("\nSHOT_ZONE_AREA:")
print(d["SHOT_ZONE_AREA"].value_counts().to_string())
if "SHOT_ZONE_RANGE" in d.columns:
    print("\nSHOT_ZONE_RANGE:")
    print(d["SHOT_ZONE_RANGE"].value_counts().to_string())
print("\nACTION_TYPE top:")
if "ACTION_TYPE" in d.columns:
    print(d["ACTION_TYPE"].value_counts().head(10).to_string())

print("\n=== manifests under data/shotcharts ===")
print(glob.glob(os.path.join(REPO, "data", "shotcharts", "*.manifest.json")))
print("\n=== manifests under data/masters ===")
for p in glob.glob(os.path.join(REPO, "data", "masters", "*.manifest.json")):
    m = json.load(open(p))
    print(f"  {os.path.basename(p):<45} asof_granularity={m.get('asof_granularity')!r}")
print("\n=== manifests under data/zone_maps ===")
for p in glob.glob(os.path.join(REPO, "data", "zone_maps", "*.manifest.json")):
    m = json.load(open(p))
    print(f"  {os.path.basename(p):<45} asof_granularity={m.get('asof_granularity')!r}")

print("\n=== playbyplay dir ===")
pbp = os.path.join(REPO, "data", "playbyplay")
print(sorted(os.listdir(pbp))[:20] if os.path.isdir(pbp) else "missing")
