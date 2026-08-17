"""E1_I0046 s00e -- READ-ONLY: does a from-scratch n_prior / prior5_minutes reproduce E1_I0018's?"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")

mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"),
                     columns=["game_id", "season", "season_type", "game_date", "team_id",
                              "player_id", "minutes", "pts", "fga", "starter_flag"])
mp = mp[(mp["season"].isin([2021, 2022, 2023, 2024])) & (mp["season_type"] == "Regular Season")].copy()
mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
app = mp[mp["minutes"] > 0].copy()
app["game_date"] = pd.to_datetime(app["game_date"])
app = app.sort_values(["season", "player_id", "game_date", "game_id"]).reset_index(drop=True)
g = app.groupby(["season", "player_id"], sort=False)
app["my_n_prior"] = g.cumcount().astype(float)
app["my_prior5_minutes"] = g["minutes"].transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())

b = pd.read_parquet(os.path.join(EXP, r"E1_I0018_teammate_volume_channel\screen_frame.parquet"),
                    columns=["season", "player_id", "game_id", "n_prior", "prior5_minutes", "minutes", "pts"])
j = b.merge(app[["season", "player_id", "game_id", "my_n_prior", "my_prior5_minutes", "minutes", "pts"]],
            on=["season", "player_id", "game_id"], how="left", suffixes=("_ref", "_mine"))
print("E1_I0018 rows", len(b), " matched into appeared universe", int(j["my_n_prior"].notna().sum()))
print("minutes match max|d| %.9f" % np.nanmax(np.abs(j["minutes_ref"] - j["minutes_mine"])))
print("pts     match max|d| %.9f" % np.nanmax(np.abs(j["pts_ref"] - j["pts_mine"])))
d = j["n_prior"] - j["my_n_prior"]
print("n_prior: exact %d / %d   max|d| %s   value counts of diff %s"
      % (int((d.abs() < 1e-9).sum()), int(d.notna().sum()), np.nanmax(np.abs(d)),
         d.value_counts(dropna=True).head(6).to_dict()))
d2 = j["prior5_minutes"] - j["my_prior5_minutes"]
both = j["prior5_minutes"].notna() & j["my_prior5_minutes"].notna()
print("prior5_minutes: both-present %d exact %d max|d| %.9f"
      % (int(both.sum()), int((d2.abs() < 1e-9).sum()), np.nanmax(np.abs(d2[both]))))
print("  ref NaN %d ; mine NaN %d" % (int(j['prior5_minutes'].isna().sum()), int(j['my_prior5_minutes'].isna().sum())))

# what does E1_I0018 do at n_prior==0 ?
q = j[j["my_n_prior"] == 0]
print("  at my_n_prior==0: ref prior5 NaN frac %.4f" % q["prior5_minutes"].isna().mean())
q1 = j[j["my_n_prior"] == 1]
print("  at my_n_prior==1: ref prior5 NaN frac %.4f  max|d| %.9f"
      % (q1["prior5_minutes"].isna().mean(), np.nanmax(np.abs(q1["prior5_minutes"] - q1["my_prior5_minutes"]))))
