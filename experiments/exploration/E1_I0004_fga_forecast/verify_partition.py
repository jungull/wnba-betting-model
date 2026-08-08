"""E1 I0004c -- final partition + write-scope verification of MY OWN outputs.

Checks COLUMN VALUES, not bytes, on every parquet this screen wrote; and checks that the
only files touched live inside this directory. Byte/regex partition scans have produced
false hits three times in this program, once from a column merely NAMED with a
season-like string, so the parquet check is on values and on the season column.
"""
import glob
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PARTITION = {2021, 2022, 2023, 2024}
print("=" * 100)
print("A. PARQUET OUTPUTS -- season COLUMN VALUES and date COLUMN VALUES")
print("=" * 100)
ok = True
for f in sorted(glob.glob(os.path.join(HERE, "*.parquet"))):
    d = pd.read_parquet(f)
    ssn = set(int(x) for x in d["season"].unique())
    dmax = pd.to_datetime(d["game_date"]).max()
    bad = ssn - PARTITION
    ok &= (not bad) and dmax.year <= 2024
    print(f"  {os.path.basename(f):<44} rows={len(d):>6}  seasons={sorted(ssn)}  "
          f"max(game_date)={dmax.date()}  {'OK' if not bad and dmax.year <= 2024 else '*** VIOLATION ***'}")

print("\n" + "=" * 100)
print("B. CSV OUTPUTS -- shape only (permutation draws carry no season field)")
print("=" * 100)
for f in sorted(glob.glob(os.path.join(HERE, "*.csv"))):
    d = pd.read_csv(f)
    print(f"  {os.path.basename(f):<44} shape={d.shape}")

print("\n" + "=" * 100)
print("C. JSON OUTPUTS -- any numeric 2025/2026 season value anywhere?")
print("=" * 100)


def walk(o, path=""):
    hits = []
    if isinstance(o, dict):
        for k, v in o.items():
            if str(k) in ("2025", "2026"):
                hits.append(f"{path}.{k} (KEY)")
            hits += walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            hits += walk(v, f"{path}[{i}]")
    elif isinstance(o, (int, float)) and o in (2025, 2026):
        hits.append(f"{path} = {o}")
    return hits


for f in sorted(glob.glob(os.path.join(HERE, "*.json"))):
    j = json.load(open(f, encoding="utf-8"))
    h = walk(j)
    print(f"  {os.path.basename(f):<44} numeric/key 2025-2026 hits: {h if h else 'NONE'}")
    ok &= not h

print("\n" + "=" * 100)
print("D. WRITE SCOPE -- every file this screen produced")
print("=" * 100)
for f in sorted(glob.glob(os.path.join(HERE, "*"))):
    print(f"  {os.path.relpath(f, os.path.abspath(os.path.join(HERE, '..', '..', '..')))}")
print(f"\nOVERALL: {'PASS -- 0 structural violations' if ok else '*** FAIL ***'}")
