"""E0_I0016 s00 -- inspect available inputs. READ ONLY. No results computed here."""
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 200)

D076 = os.path.join(ROOT, r"experiments\exploration\E0_I0014_residual_heterogeneity")
FRAME = os.path.join(D076, "analysis_frame.parquet")
MP = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT = os.path.join(ROOT, r"data\masters\master_team.parquet")

print("=" * 100)
print("MANIFEST CHECKS")
print("=" * 100)
for p in [FRAME, MP, MT]:
    r = sk.check_manifest(p, verbose=True)
    print("     status=%s usable=%s fit_through_season=%s"
          % (r["status"], r["usable_at_e0_e1"], r["fit_through_season"]))

print("\n" + "=" * 100)
print("D076 analysis_frame.parquet")
print("=" * 100)
f = pd.read_parquet(FRAME)
print("shape", f.shape)
print("columns:")
for c in sorted(f.columns):
    print("   %-40s %s" % (c, f[c].dtype))
print("\nseasons:", sorted(f["season"].unique()))
print("date range:", f["gdate"].min(), f["gdate"].max())

print("\n" + "=" * 100)
print("master_player.parquet")
print("=" * 100)
mp = pd.read_parquet(MP)
print("shape", mp.shape)
for c in sorted(mp.columns):
    print("   %-40s %s" % (c, mp[c].dtype))
print(mp.head(3).T)

print("\n" + "=" * 100)
print("master_team.parquet")
print("=" * 100)
mt = pd.read_parquet(MT)
print("shape", mt.shape)
for c in sorted(mt.columns):
    print("   %-40s %s" % (c, mt[c].dtype))
print(mt.head(3).T)
