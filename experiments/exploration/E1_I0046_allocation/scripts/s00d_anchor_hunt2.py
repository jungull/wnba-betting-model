"""E1_I0046 s00d -- READ-ONLY: can this environment RECOMPUTE D085's dR2 and E1_I0043's stratum?"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")

a = pd.read_parquet(os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_frame.parquet"))
b = pd.read_parquet(os.path.join(EXP, r"E1_I0018_teammate_volume_channel\screen_frame.parquet"))
k = ["season", "player_id", "game_id"]
take_b = ["prior5_minutes", "y_pts", "y_spm", "TSA", "refB_spm", "refB_pps", "refB_mpg",
          "refB_own_usg_pg", "O01_own_usg_pg"]
m = a.merge(b[k + take_b], on=k, how="inner", suffixes=("", "_tv"))
print("merged", len(m))

dec = (pd.to_numeric(m["n_prior"], errors="coerce").to_numpy(float) >= 8.0) & \
      (pd.to_numeric(m["prior5_minutes"], errors="coerce").to_numpy(float) >= 24.0)
print("DECISION rows", int(dec.sum()), " players", m.loc[dec, "player_id"].nunique(),
      " games", m.loc[dec, "game_id"].nunique())
d2 = dec & m["season"].isin([2023, 2024]).to_numpy()
print("DECISION 2023-24 rows", int(d2.sum()))

sr = pd.read_csv(os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_results.csv"))
row = sr[(sr["candidate"] == "A10_opp_defrtg")]
print(row[["outcome", "candidate", "n", "dr2", "p_N2_entity_swap", "var_share_between_entity"]].to_string())


def r2d(y, Xb, Xf):
    def sse(X):
        c = np.linalg.lstsq(X, y, rcond=None)[0]
        return float(((y - X @ c) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    return (sse(Xb) - sse(Xf)) / sst


for ref in ["refB_ppm", "refA_ppm"]:
    y = m["y_ppm"].to_numpy(float)
    ok = np.isfinite(y) & np.isfinite(m[ref].to_numpy(float)) & np.isfinite(m["A10_opp_defrtg"].to_numpy(float))
    yy = y[ok]
    Xb = np.column_stack([np.ones(ok.sum()), m[ref].to_numpy(float)[ok]])
    Xf = np.column_stack([Xb, m["A10_opp_defrtg"].to_numpy(float)[ok]])
    print("  pooled dR2 over %s (n=%d): %.16f" % (ref, ok.sum(), r2d(yy, Xb, Xf)))
