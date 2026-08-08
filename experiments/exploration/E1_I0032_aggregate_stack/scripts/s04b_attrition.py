"""E1_I0032 s04b -- WHY DID THE ROUTED POPULATION VANISH?

Pure coverage accounting.  NO OUTCOME STATISTIC IS COMPUTED HERE, and none had been computed when
this was written: the trigger was a row count of ZERO routed rows printed by s04, nothing else.
That is disclosed in NOTES.md and the failed s04 log is kept on disk.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stack_base import EXP, OUT, TV, EFF, TIER, TARGETS, SCORED, prereg

pd.set_option("display.width", 220)
prereg()

tv = pd.read_parquet(TV)
eff = pd.read_parquet(EFF)
tier = pd.read_parquet(TIER)
K = ["season", "player_id", "game_id"]
for df in (tv, eff, tier):
    df["game_id"] = df["game_id"].astype(str)
tv = tv.merge(eff[K + ["A10_opp_defrtg"]].drop_duplicates(K), on=K, how="left")
cols = ["pts__fallback_level", "minutes__fallback_level", "fga__fallback_level",
        "pts__pred_point", "minutes__pred_point", "fga__pred_point", "tm_is_home"]
tv = tv.merge(tier[K + cols].drop_duplicates(K), on=K, how="left")

m = np.isin(tv["season"].to_numpy(), SCORED) & tv["pts__pred_point"].notna().to_numpy()
sub = tv[m].copy()
fl = pd.to_numeric(sub["pts__fallback_level"], errors="coerce").to_numpy(float)
print("rows with a champion forecast in 2022-2024: %d" % len(sub))
print("  fallback_level distribution: %s"
      % pd.Series(fl).value_counts(dropna=False).sort_index().to_dict())

print("\nper-feature finite coverage, split by fallback_level")
feats = ["O01_own_usg_pg", "P01_c04_prevgame", "G01_noise", "A10_opp_defrtg", "tm_is_home",
         "n_prior", "prior5_minutes", "used"]
rows = []
for c in feats:
    v = pd.to_numeric(sub[c], errors="coerce").to_numpy(float)
    ok = np.isfinite(v)
    rows.append({"feature": c,
                 "finite_all": int(ok.sum()),
                 "finite_fl0": int((ok & (fl == 0)).sum()),
                 "n_fl0": int((fl == 0).sum()),
                 "finite_fl2": int((ok & (fl == 2)).sum()),
                 "n_fl2": int((fl == 2).sum()),
                 "finite_fl3": int((ok & (fl == 3)).sum()),
                 "n_fl3": int((fl == 3).sum())})
t = pd.DataFrame(rows)
print(t.to_string(index=False))
t.to_csv(os.path.join(OUT, "attrition_by_feature.csv"), index=False)

print("\nCONCLUSION")
print("  The rows the D102 routing targets are, by construction, the rows with almost no prior")
print("  history -- which is exactly where the prior-history FEATURES (own usage, teammate")
print("  volume) are undefined.  Requiring every component's feature to be finite on one common")
print("  row set therefore DELETES the single largest component's entire target population.")
