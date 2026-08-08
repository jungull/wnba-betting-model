#!/usr/bin/env python3
"""E1_I0035 s01 -- inspect inputs. NOTHING is computed for publication here.

PARTITION GUARD: 2021-2024 only. 2025/2026 files exist on disk in the same directories and
are NEVER opened. Every loader below enumerates seasons explicitly.
"""
from __future__ import annotations
import json
import os
import sys

import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "E1_I0035_availability_sum")
PLAYER_ARM = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
CV4 = os.path.join(ROOT, "experiments", "prediction_contract_v4")
CV5 = os.path.join(ROOT, "experiments", "prediction_contract_v5")
MASTER_PLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
MASTER_TEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
BIOS = os.path.join(ROOT, "data", "reference", "player_bios.csv")

SEASONS = (2021, 2022, 2023, 2024)
FORBIDDEN = (2025, 2026)

sys.dont_write_bytecode = True
pd.set_option("display.width", 220)


def hdr(s):
    print("\n" + "=" * 96)
    print(s)
    print("=" * 96)


def cols(path, n=3):
    d = pd.read_parquet(path)
    print("  %s" % os.path.basename(path))
    print("    rows=%d  cols=%d" % (len(d), d.shape[1]))
    print("    %s" % list(d.columns))
    return d


hdr("0. PARTITION GUARD")
print("  seasons opened   : %s" % (SEASONS,))
print("  seasons forbidden: %s  (files exist; never read)" % (FORBIDDEN,))

hdr("1. CHAMPION ARM p_active PREDICTIONS")
pa = cols(os.path.join(PLAYER_ARM, "predictions__p_active__2022.parquet"))
print("\n  head:")
print(pa.head(4).to_string())
print("\n  pred_point describe:")
print(pa["pred_point"].describe().to_string())
print("\n  fallback_level value counts:")
print(pa["fallback_level"].value_counts(dropna=False).to_string())
print("\n  component_id value counts:")
print(pa["component_id"].value_counts(dropna=False).to_string())
print("\n  pred_point value counts (top 12):")
print(pa["pred_point"].round(6).value_counts().head(12).to_string())

hdr("2. CONTRACT v4 player_game")
v4 = cols(os.path.join(CV4, "player_game.parquet"))
print(v4.head(3).to_string())

hdr("3. CONTRACT v5 player_game  (UNVERIFIABLE -- described only, backs no number)")
for f in ("player_game.parquet", "player_game_enriched.parquet"):
    p = os.path.join(CV5, f)
    if os.path.exists(p):
        d = pd.read_parquet(p)
        print("  %s rows=%d cols=%s" % (f, len(d), list(d.columns)))

hdr("4. MASTERS")
mp = pd.read_parquet(MASTER_PLAYER)
print("  master_player rows=%d cols=%s" % (len(mp), list(mp.columns)))
print("  seasons present: %s" % sorted(mp["season"].unique().tolist()))
mt = pd.read_parquet(MASTER_TEAM)
print("  master_team rows=%d" % len(mt))
print("  seasons present: %s" % sorted(mt["season"].unique().tolist()))

hdr("5. PLAYER BIOS")
if os.path.exists(BIOS):
    b = pd.read_csv(BIOS)
    print("  rows=%d cols=%s" % (len(b), list(b.columns)))
    print(b.head(5).to_string())
else:
    print("  ABSENT: %s" % BIOS)

hdr("6. MANIFEST STATUS OF EVERY INPUT")
for p in (os.path.join(PLAYER_ARM, "predictions__p_active__2022.parquet"),
          os.path.join(CV4, "player_game.parquet"),
          os.path.join(CV5, "player_game.parquet"),
          MASTER_PLAYER, MASTER_TEAM, BIOS):
    m = p + ".manifest.json"
    if os.path.exists(m):
        j = json.loads(open(m, encoding="utf-8").read())
        print("  %-60s MANIFEST granularity=%s" % (os.path.basename(p),
                                                   j.get("granularity", j.get("grain", "?"))))
    else:
        print("  %-60s NO MANIFEST -> UNVERIFIABLE" % os.path.basename(p))

print("\nDONE s01")
