"""E1_I0032 s04c -- can the CHAMPION's own universe carry the ladder?  Coverage only.

Still no outcome statistic.  This decides which frame the amended common row set is built on.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import EXP, OUT, TV, TIER, SCORED, prereg

pd.set_option("display.width", 220)
prereg()

tier = pd.read_parquet(TIER)
tv = pd.read_parquet(TV)
tier["game_id"] = tier["game_id"].astype(str)
tv["game_id"] = tv["game_id"].astype(str)

print("tier universe by season: %s" % tier["season"].value_counts().sort_index().to_dict())
print("tv   universe by season: %s" % tv["season"].value_counts().sort_index().to_dict())
K = ["season", "player_id", "game_id"]
st = set(map(tuple, tier[K].astype(str).to_numpy()))
sv = set(map(tuple, tv[K].astype(str).to_numpy()))
print("tier 2022-24 = %d ; tv 2022-24 = %d ; tier&tv = %d"
      % (len(tier), int((tv["season"] >= 2022).sum()), len(st & sv)))
print("tv 2022-24 rows NOT in tier: %d"
      % len(set(map(tuple, tv[tv["season"] >= 2022][K].astype(str).to_numpy())) - st))

print("\ntier columns needed by refladder:")
for c in ("season", "player_id", "gdate", "minutes", "pts", "fga"):
    print("  %-12s dtype=%s  finite/nonnull=%d/%d" % (c, tier[c].dtype, tier[c].notna().sum(), len(tier)))
print("  gdate range: %s .. %s" % (pd.to_datetime(tier["gdate"]).min(), pd.to_datetime(tier["gdate"]).max()))

print("\nDECISION-stratum ingredients present in tier:")
for c in ("pl_games_prior", "pl_min_mean5", "pl_minutes_prior", "pts__n_prior_games"):
    v = pd.to_numeric(tier[c], errors="coerce")
    print("  %-20s finite=%d  median=%.3f" % (c, v.notna().sum(), v.median()))

mg = tier.merge(tv[K + ["n_prior", "prior5_minutes"]], on=K, how="inner")
a = (pd.to_numeric(mg["pl_games_prior"], errors="coerce") >= 8) & \
    (pd.to_numeric(mg["pl_min_mean5"], errors="coerce") >= 24)
b = (pd.to_numeric(mg["n_prior"], errors="coerce") >= 8) & \
    (pd.to_numeric(mg["prior5_minutes"], errors="coerce") >= 24)
print("\nDECISION agreement on the %d-row overlap: tier-def %d, tv-def %d, agree %.4f, both %d"
      % (len(mg), int(a.sum()), int(b.sum()), float((a == b).mean()), int((a & b).sum())))
print("  corr(pl_games_prior, n_prior) = %.6f"
      % np.corrcoef(pd.to_numeric(mg["pl_games_prior"], errors="coerce").fillna(-1),
                    pd.to_numeric(mg["n_prior"], errors="coerce").fillna(-1))[0, 1])
print("  corr(pl_min_mean5, prior5_minutes) on both-finite = %.6f"
      % pd.to_numeric(mg["pl_min_mean5"], errors="coerce").corr(
          pd.to_numeric(mg["prior5_minutes"], errors="coerce")))

print("\nfeature coverage IF the base universe is tier (13,879 rows):")
mg2 = tier.merge(tv[K + ["P01_c04_prevgame", "O01_own_usg_pg", "G01_noise"]], on=K, how="left")
fl = pd.to_numeric(mg2["pts__fallback_level"], errors="coerce").to_numpy(float)
for c in ("P01_c04_prevgame", "O01_own_usg_pg"):
    v = pd.to_numeric(mg2[c], errors="coerce").to_numpy(float)
    print("  %-20s finite %d/%d ; on fallback_level==2 %d/%d"
          % (c, int(np.isfinite(v).sum()), len(mg2),
             int((np.isfinite(v) & (fl == 2)).sum()), int((fl == 2).sum())))
