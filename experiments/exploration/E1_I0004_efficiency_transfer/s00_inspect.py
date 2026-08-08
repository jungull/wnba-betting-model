"""S00 -- inspect the two anchor frames and the join keys, BEFORE building anything.

No statistics here.  This exists so that every join key used later is one whose dtype and
overlap were checked rather than assumed.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 200)
pd.set_option("display.max_rows", 300)

DECOMP = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition"
                            r"\decomp_frame.parquet")
REPRO = os.path.join(ROOT, r"experiments\exploration\E1_I0004_shot_selection"
                           r"\repro_ra_common.parquet")
CONVF = os.path.join(ROOT, r"experiments\exploration\E1_I0004_shot_selection"
                           r"\conversion_frame.parquet")

print("=" * 100)
print("A. MANIFEST CHECKS (kit check_manifest -- missing manifest is UNVERIFIABLE, never a pass)")
print("=" * 100)
for p in [DECOMP, REPRO, CONVF,
          os.path.join(ROOT, r"data\shotcharts\shots_2022_regular.parquet")]:
    try:
        r = sk.check_manifest(p, verbose=True)
        print("  %-70s -> %s" % (os.path.basename(p), r.get("verdict", r)))
    except Exception as e:  # noqa: BLE001
        print("  %-70s -> RAISED %s" % (os.path.basename(p), e))

print("\n" + "=" * 100)
print("B. decomp_frame.parquet")
print("=" * 100)
d = pd.read_parquet(DECOMP)
print("  shape", d.shape)
print("  columns:")
for c in sorted(d.columns):
    print("     %-34s %s" % (c, d[c].dtype))
sk.assert_partition(d, verbose=True)
print("\n  seasons:", sorted(d["season"].unique()))
for c in ["player_id", "game_id", "gdate", "team_id", "opp_team_id", "opponent_id"]:
    if c in d.columns:
        print("  %-14s dtype=%-10s n_unique=%d  head=%s"
              % (c, d[c].dtype, d[c].nunique(), list(d[c].head(3))))

print("\n" + "=" * 100)
print("C. repro_ra_common.parquet (E1_I0004_shot_selection, frozen)")
print("=" * 100)
r = pd.read_parquet(REPRO)
print("  shape", r.shape)
print(r.dtypes.to_string())
print(r.head(3).to_string())

print("\n" + "=" * 100)
print("D. conversion_frame.parquet (E1_I0004_shot_selection, frozen)")
print("=" * 100)
cv = pd.read_parquet(CONVF)
print("  shape", cv.shape)
print(cv.dtypes.to_string())
print(cv["zone_name"].value_counts().to_string())

print("\n" + "=" * 100)
print("E. raw shot file schema (2022 regular) -- zones come from SHOT_ZONE_BASIC only")
print("=" * 100)
s = pd.read_parquet(os.path.join(ROOT, r"data\shotcharts\shots_2022_regular.parquet"))
print("  shape", s.shape)
print(s.dtypes.to_string())
print("\n  SHOT_ZONE_BASIC:", sorted(s["SHOT_ZONE_BASIC"].unique()))
if "SHOT_TYPE" in s.columns:
    print("  SHOT_TYPE:", sorted(s["SHOT_TYPE"].unique()))
print("\n  key dtypes: PLAYER_ID=%s GAME_ID=%s TEAM_ID=%s"
      % (s["PLAYER_ID"].dtype, s["GAME_ID"].dtype, s["TEAM_ID"].dtype))
print("  GAME_ID head:", list(s["GAME_ID"].head(3)))
print("  PLAYER_ID head:", list(s["PLAYER_ID"].head(3)))

print("\n" + "=" * 100)
print("F. JOIN FEASIBILITY decomp_frame <-> shots")
print("=" * 100)
if "game_id" in d.columns:
    dg = set(d["game_id"].astype(str).str.lstrip("0"))
    sg = set(s["GAME_ID"].astype(str).str.lstrip("0"))
    print("  decomp game_id n=%d ; 2022 shots game_id n=%d ; overlap(after lstrip 0)=%d"
          % (len(dg), len(sg), len(dg & sg)))
dp = set(pd.to_numeric(d["player_id"], errors="coerce").dropna().astype(np.int64))
sp = set(pd.to_numeric(s["PLAYER_ID"], errors="coerce").dropna().astype(np.int64))
print("  decomp player_id n=%d ; shots PLAYER_ID n=%d ; overlap=%d" % (len(dp), len(sp), len(dp & sp)))
print("\nDONE s00")
