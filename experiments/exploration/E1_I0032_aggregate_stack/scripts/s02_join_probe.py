"""E1_I0032 s02 -- READ-ONLY: can the four source frames be joined on one key, and what do the
component-bearing columns actually contain?  No statistic that could drive a decision is computed.
"""
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
pd.set_option("display.width", 220)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


tier = pd.read_parquet(os.path.join(EXP, r"E1_I0020_coldstart_tiering\tier_frame.parquet"))
tv = pd.read_parquet(os.path.join(EXP, r"E1_I0018_teammate_volume_channel\screen_frame.parquet"))
eff = pd.read_parquet(os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_frame.parquet"))

hdr("1. key dtypes")
for nm, df in (("tier", tier), ("tv", tv), ("eff", eff)):
    print("  %-5s game_id=%s player_id=%s season=%s n=%d" %
          (nm, df["game_id"].dtype, df["player_id"].dtype, df["season"].dtype, len(df)))
    print("        sample game_id: %s" % df["game_id"].head(3).tolist())
    print("        sample player_id: %s" % df["player_id"].head(3).tolist())

K = ["season", "player_id", "game_id"]
for df in (tier, tv, eff):
    for k in K:
        df[k] = df[k].astype(str)

hdr("2. key overlap")
st = set(map(tuple, tier[K].to_numpy()))
sv = set(map(tuple, tv[K].to_numpy()))
se = set(map(tuple, eff[K].to_numpy()))
print("  tier %d  tv %d  eff %d" % (len(st), len(sv), len(se)))
print("  tier&tv %d   tier&eff %d   tv&eff %d   all3 %d"
      % (len(st & sv), len(st & se), len(sv & se), len(st & sv & se)))
print("  tier dupes on key: %d ; tv %d ; eff %d"
      % (tier.duplicated(K).sum(), tv.duplicated(K).sum(), eff.duplicated(K).sum()))

hdr("3. champion fallback structure in tier_frame (by target)")
for t in ("pts", "minutes", "fga"):
    fl = tier["%s__fallback_level" % t]
    isf = tier["%s__is_fallback" % t]
    print("  %-8s fallback_level value counts: %s" % (t, fl.value_counts(dropna=False).to_dict()))
    print("           is_fallback: %s ; is_cold_start: %s"
          % (isf.value_counts(dropna=False).to_dict(),
             tier["%s__is_cold_start" % t].value_counts(dropna=False).to_dict()))
    sub = tier[fl == 2]
    if len(sub):
        print("           on fallback_level==2 (n=%d): pred_point mean=%.4f sd=%.4f"
              % (len(sub), sub["%s__pred_point" % t].mean(), sub["%s__pred_point" % t].std()))

hdr("4. tier_frame extras")
print("  depth_rank: %s" % tier["depth_rank"].describe().to_dict())
print("  draft_pick nonnull %d / %d ; undrafted %s"
      % (tier["draft_pick"].notna().sum(), len(tier), tier["undrafted"].value_counts().to_dict()))
print("  tm_is_home: %s" % tier["tm_is_home"].value_counts(dropna=False).to_dict())
print("  t_pts/t_minutes/t_ppm nonnull: %d %d %d"
      % (tier["t_pts"].notna().sum(), tier["t_minutes"].notna().sum(), tier["t_ppm"].notna().sum()))
print("  champ_pts vs pts__pred_point identical: %s"
      % bool(np.allclose(tier["champ_pts"].astype(float), tier["pts__pred_point"].astype(float),
                         equal_nan=True)))
print("  appeared: %s" % tier["appeared"].value_counts(dropna=False).to_dict())
print("  minutes>0 rows: %d" % int((pd.to_numeric(tier["minutes"], errors="coerce") > 0).sum()))

hdr("5. availability frame")
for f in ("scored_frame.parquet", "analysis_frame.parquet"):
    p = os.path.join(EXP, r"E0_I0019_availability_forecast", f)
    if not os.path.exists(p):
        print("  MISSING %s" % f)
        continue
    a = pd.read_parquet(p)
    print("  %-24s shape=%s" % (f, (a.shape,)))
    print("    cols(%d): %s" % (len(a.columns), list(a.columns)))

hdr("6. degeneracy work_frame")
p = os.path.join(EXP, r"E0_I0028_degeneracy_sweep\work_frame.parquet")
w = pd.read_parquet(p)
print("  shape=%s" % (w.shape,))
print("  cols(%d): %s" % (len(w.columns), list(w.columns)))
