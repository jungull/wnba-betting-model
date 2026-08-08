"""E1_I0022 STEP 0 -- inspect the frozen inputs.  READ ONLY.  No screen kit import (another
agent is editing it); everything this screen needs is implemented locally in ose_base.py."""
import os
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
D081 = os.path.join(ROOT, r"experiments\exploration\E0_I0015_points_skill_decomposition")
FRAME = os.path.join(D081, "decomp_frame.parquet")

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 300)
pd.set_option("display.max_rows", 400)

f = pd.read_parquet(FRAME)
print("shape", f.shape)
print("seasons", sorted(f["season"].unique()))
print("gdate min/max", f["gdate"].min(), f["gdate"].max())
print("\nCOLUMNS (%d):" % f.shape[1])
for i, c in enumerate(f.columns):
    print("  %3d  %-46s %-12s nnull=%d" % (i, c, str(f[c].dtype), int(f[c].isna().sum())))

print("\nn players:", f["player_id"].nunique())
print("rows per season:\n", f.groupby("season").size())

# prior-appearance depth
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
f["_depth"] = f.groupby(["season", "player_id"], sort=False).cumcount()
print("\ndepth distribution (prior appearances THIS season):")
print(f["_depth"].describe())
print(f["_depth"].value_counts().sort_index().head(20))

for c in ["y_pts", "y_minutes", "y_fga", "pts__pred_point", "minutes__pred_point",
          "fga__pred_point", "ref_pts", "ref_minutes", "ref_fga"]:
    if c in f.columns:
        print("%-24s mean=%10.4f sd=%10.4f min=%8.3f max=%8.3f" %
              (c, f[c].mean(), f[c].std(), f[c].min(), f[c].max()))

# is there any cross-season player history available in this frame?
pp = f.groupby("player_id")["season"].nunique()
print("\nplayers appearing in >1 season:", int((pp > 1).sum()), "of", len(pp))

# trailing-5 minutes column present?
cand = [c for c in f.columns if "trail" in c.lower() or "roll" in c.lower() or "l5" in c.lower()]
print("\ntrailing-ish columns:", cand)
