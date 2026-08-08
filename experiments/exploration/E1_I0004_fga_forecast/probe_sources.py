"""E1 I0004c -- source probe. Read-only.

Establishes, BEFORE any statistic is computed:
  (a) which candidate data sources carry a sibling <artifact>.manifest.json and what
      asof_granularity they declare (MISSING MANIFEST == "UNVERIFIABLE", NOT A PASS);
  (b) the schema and the *column-value* season/date range of every candidate source
      (TEST COLUMN VALUES, NOT TEXT -- byte/regex partition scans have produced false
      hits three times in this program);
  (c) that the exploration partition (2021-2024) can be enforced on each.

2025/2026 files are NEVER opened. The only reason 2025/2026 filenames are printed is
that they appear in a directory listing; no such file is read.
"""
import glob
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARTITION = [2021, 2022, 2023, 2024]
FORBIDDEN_TOKENS = ("2025", "2026")


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("A. MANIFEST INVENTORY over data/ (recursive) -- asof_granularity COLUMN VALUE")
mans = sorted(glob.glob(os.path.join(REPO, "data", "**", "*.manifest.json"),
                        recursive=True))
print(f"  {len(mans)} manifest files found")
for m in mans:
    try:
        j = json.load(open(m, encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  {os.path.relpath(m, REPO):<62} UNREADABLE ({e})")
        continue
    print(f"  {os.path.relpath(m, REPO):<62} asof_granularity={j.get('asof_granularity')!r}")

hdr("B. CANDIDATE SOURCES -- manifest presence")
CANDIDATES = [
    "data/shotcharts/shots_2021_regular.parquet",
    "data/shotcharts/shots_2021_playoffs.parquet",
    "data/wnba_gamelog_2021.parquet",
    "data/wnba_gamelog_2022.parquet",
    "data/wnba_gamelog_2023.parquet",
    "data/wnba_gamelog_2024.parquet",
    "data/masters/master_player.parquet",
]
for c in CANDIDATES:
    p = os.path.join(REPO, c)
    mp = p + ".manifest.json"
    if os.path.exists(mp):
        j = json.load(open(mp, encoding="utf-8"))
        print(f"  {c:<52} MANIFEST asof_granularity={j.get('asof_granularity')!r}")
    else:
        print(f"  {c:<52} NO MANIFEST -> UNVERIFIABLE (not a pass)")

hdr("C. GAMELOG SCHEMA + COLUMN-VALUE PARTITION TEST (2021-2024 files only)")
for ssn in PARTITION:
    f = os.path.join(REPO, f"data/wnba_gamelog_{ssn}.parquet")
    d = pd.read_parquet(f)
    print(f"\n  --- wnba_gamelog_{ssn}.parquet  rows={len(d)}  cols={len(d.columns)}")
    print(f"      columns: {list(d.columns)}")
    if ssn == 2021:
        print("      dtypes:")
        for c in d.columns:
            print(f"        {c:<28} {str(d[c].dtype):<12} e.g. {d[c].dropna().iloc[0]!r}"
                  if d[c].notna().any() else f"        {c:<28} {d[c].dtype} ALL NULL")
    # COLUMN-VALUE scan: any cell in any object/str column containing 2025/2026?
    bad = {}
    for c in d.columns:
        s = d[c]
        if s.dtype == object or str(s.dtype).startswith("string"):
            sv = s.astype(str)
            hit = sv.str.contains("2025|2026", regex=True, na=False)
            if hit.any():
                bad[c] = (int(hit.sum()), sv[hit].iloc[0])
        elif pd.api.types.is_numeric_dtype(s):
            hit = s.isin([2025, 2026])
            if hit.any():
                bad[c] = (int(hit.sum()), "numeric 2025/2026")
    print(f"      column-VALUE hits on 2025/2026: {bad if bad else 'NONE'}")
    # date range from column values
    for dc in ("GAME_DATE", "game_date"):
        if dc in d.columns:
            dts = pd.to_datetime(d[dc], errors="coerce", format="mixed")
            print(f"      {dc} value range: {dts.min()} .. {dts.max()}")

hdr("D. SHOTCHART SCHEMA (2021 regular) -- confirm attempt/zone/points fields")
sh = pd.read_parquet(os.path.join(REPO, "data/shotcharts/shots_2021_regular.parquet"))
print(f"  rows={len(sh)}  columns: {list(sh.columns)}")
print("  SHOT_ZONE_BASIC values:", sorted(sh["SHOT_ZONE_BASIC"].dropna().unique()))
if "SHOT_TYPE" in sh.columns:
    print("  SHOT_TYPE values:", sorted(sh["SHOT_TYPE"].dropna().unique()))
print("  GAME_DATE range:", sh["GAME_DATE"].min(), "..", sh["GAME_DATE"].max())

hdr("E. PREDECESSOR FRAME -- selection_frame.parquet")
sf = pd.read_parquet(os.path.join(
    REPO, "experiments/exploration/E1_I0004_shot_selection/selection_frame.parquet"))
print(f"  rows={len(sf)}  columns: {list(sf.columns)}")
print(f"  seasons (column value) = {sorted(sf['season'].unique())}")
print(f"  game_date range = {sf['game_date'].min()} .. {sf['game_date'].max()}")
print(f"  player-games = {sf[['player_id','season','game_id']].drop_duplicates().shape[0]}")
print(sf.head(3).to_string())

print("\nDone (probe).")
