"""E0_I0024 s00 -- INSPECT ONLY.  No statistics.  Establish column names, dtypes, manifest
status of every artifact this screen will consume, and the shotchart granularity evidence.

Writes nothing but a log and _s00.json.  2021-2024 only; 2025/2026 never read.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0024_reb_ast_characterisation")
MP = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT = os.path.join(ROOT, r"data\masters\master_team.parquet")
SHOTDIR = os.path.join(ROOT, r"data\shotcharts")

sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 200)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


def manifest_status(path):
    """Read the sidecar manifest FROM DISK.  A MISSING manifest is UNVERIFIABLE, never a pass."""
    mpath = path + ".manifest.json"
    if not os.path.exists(mpath):
        return dict(artifact=os.path.relpath(path, ROOT), manifest_present=False,
                    asof_granularity=None, fit_through_season=None,
                    status="UNVERIFIABLE_NO_MANIFEST")
    m = json.load(open(mpath))
    g = m.get("asof_granularity")
    fts = m.get("fit_through_season")
    if g == "row":
        st = "USABLE_IF_FILTERED"
    elif g == "artifact":
        st = "UNUSABLE" if (fts is None or fts > 2024) else "USABLE_ARTIFACT_WITHIN_PARTITION"
    else:
        st = "UNVERIFIABLE_UNKNOWN_GRANULARITY"
    return dict(artifact=os.path.relpath(path, ROOT), manifest_present=True,
                asof_granularity=g, fit_through_season=fts, status=st,
                content_sha256=m.get("content_sha256"))


rep = {}

hdr("1. MANIFEST STATUS OF EVERY ARTIFACT THIS SCREEN MAY CONSUME")
cands = [MP, MT]
for s in [2021, 2022, 2023, 2024]:
    for k in ["regular", "playoffs"]:
        cands.append(os.path.join(SHOTDIR, "shots_%d_%s.parquet" % (s, k)))
ms = [manifest_status(p) for p in cands]
for m in ms:
    print("  %-58s manifest=%-5s gran=%-9s fts=%-6s -> %s"
          % (m["artifact"], m["manifest_present"], m["asof_granularity"],
             m["fit_through_season"], m["status"]))
rep["manifests"] = ms

hdr("2. master_player.parquet COLUMNS")
mp = pd.read_parquet(MP)
print("  raw shape %s" % (mp.shape,))
print("  columns: %s" % list(mp.columns))
print(mp.dtypes.to_string())
rep["mp_columns"] = list(mp.columns)
rep["mp_raw_shape"] = list(mp.shape)
print("\n  seasons present in RAW file: %s" % sorted(pd.unique(mp["season"]).tolist()))

hdr("3. PARTITION FILTER TO 2021-2024 (VALUE test, never a byte scan)")
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
f = mp[mp["season"].isin([2021, 2022, 2023, 2024])].copy()
print("  after season filter: %s" % (f.shape,))
print("  date range: %s .. %s" % (f["game_date"].min().date(), f["game_date"].max().date()))
assert f["game_date"].max() < pd.Timestamp("2025-01-01"), "PARTITION VIOLATION"
assert set(pd.unique(f["season"]).tolist()) <= {2021, 2022, 2023, 2024}
print("  PARTITION OK -- no row on/after 2025-01-01, no season outside 2021-2024")
rep["partition"] = dict(ok=True, seasons=sorted(pd.unique(f["season"]).tolist()),
                        min_date=str(f["game_date"].min().date()),
                        max_date=str(f["game_date"].max().date()), n=int(len(f)))

hdr("4. TARGET COLUMNS: oreb / dreb / ast -- coverage and nulls")
for c in ["minutes", "oreb", "dreb", "ast", "pts", "fga", "fta", "tov", "reb"]:
    if c in f.columns:
        v = pd.to_numeric(f[c], errors="coerce")
        print("  %-10s present  n_nonnull=%-7d  null=%-6d  min=%-8s max=%-8s mean=%.4f"
              % (c, v.notna().sum(), v.isna().sum(), v.min(), v.max(), v.mean()))
    else:
        print("  %-10s ABSENT" % c)
rep["has_reb_col"] = bool("reb" in f.columns)

hdr("5. APPEARED ROWS (minutes>0) BY SEASON")
pl = f[pd.to_numeric(f["minutes"], errors="coerce") > 0].copy()
print(pl.groupby("season").agg(rows=("player_id", "size"),
                               players=("player_id", "nunique"),
                               games=("game_id", "nunique")).to_string())
rep["appeared_by_season"] = pl.groupby("season").size().to_dict()

hdr("6. SHOTCHART FILES -- columns and ROW-GRANULARITY EVIDENCE (D087 method)")
sf = pd.read_parquet(os.path.join(SHOTDIR, "shots_2023_regular.parquet"))
print("  shots_2023_regular shape %s" % (sf.shape,))
print("  columns: %s" % list(sf.columns))
print(sf.dtypes.to_string())
rep["shot_columns"] = list(sf.columns)
if "SHOT_ZONE_BASIC" in sf.columns:
    print("\n  SHOT_ZONE_BASIC values:")
    print(sf["SHOT_ZONE_BASIC"].value_counts().to_string())
    rep["shot_zone_basic_values"] = sf["SHOT_ZONE_BASIC"].value_counts().to_dict()
print("\n  head:")
print(sf.head(4).to_string())

hdr("7. TEAM MASTER COLUMNS (for opponent joins)")
mt = pd.read_parquet(MT)
print("  raw shape %s   columns: %s" % (mt.shape, list(mt.columns)))
rep["mt_columns"] = list(mt.columns)

json.dump(rep, open(os.path.join(OUT, "_s00.json"), "w"), indent=2, default=str)
print("\nWROTE _s00.json")
