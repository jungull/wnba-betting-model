"""E1_I0046 s00b -- READ-ONLY: can a COMPOSITION be built that closes exactly against master_team?"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 100)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
MP = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT = os.path.join(ROOT, r"data\masters\master_team.parquet")

ALLOWED = [2021, 2022, 2023, 2024]

mp = pd.read_parquet(MP, columns=["game_id", "season", "season_type", "game_date", "team_id",
                                  "opp_team_id", "is_home", "player_id", "minutes", "pts", "fga",
                                  "fta", "reb", "ast", "starter_flag", "dnp_reason", "in_gamelog",
                                  "position"])
mt = pd.read_parquet(MT, columns=["game_id", "season", "season_type", "game_date", "team_id",
                                  "opp_team_id", "is_home", "minutes", "pts", "fga", "fta"])

print("mp raw", mp.shape, "mt raw", mt.shape)
mp = mp[mp["season"].isin(ALLOWED)].copy()
mt = mt[mt["season"].isin(ALLOWED)].copy()
print("mp 21-24", mp.shape, "mt 21-24", mt.shape)
print("PARTITION CHECK mp seasons", sorted(mp['season'].unique()), "mt", sorted(mt['season'].unique()))

for st in ["Regular Season", "Playoffs"]:
    a = mp[mp["season_type"] == st]
    b = mt[mt["season_type"] == st]
    print(st, "player rows", len(a), "team rows", len(b))

mpr = mp[mp["season_type"] == "Regular Season"].copy()
mtr = mt[mt["season_type"] == "Regular Season"].copy()

mpr["minutes"] = pd.to_numeric(mpr["minutes"], errors="coerce")
print("\nminutes null", int(mpr['minutes'].isna().sum()), " ==0", int((mpr['minutes'] == 0).sum()),
      " >0", int((mpr['minutes'] > 0).sum()))
print("in_gamelog counts", mpr["in_gamelog"].value_counts(dropna=False).to_dict())
print("dnp_reason non-null", int(mpr['dnp_reason'].notna().sum()))

app = mpr[(mpr["minutes"].fillna(0) > 0)].copy()
print("\nAPPEARED (minutes>0) rows", len(app))
print("  by season", app.groupby('season').size().to_dict())
print("  2022-2024", int(app[app['season'] >= 2022].shape[0]))
print("  2023-2024", int(app[app['season'] >= 2023].shape[0]))

# closure test: sum of appeared player pts == team pts?
g = app.groupby(["game_id", "team_id"], as_index=False).agg(
    p_pts=("pts", "sum"), p_min=("minutes", "sum"), p_fga=("fga", "sum"), n_app=("pts", "size"))
j = mtr.merge(g, on=["game_id", "team_id"], how="left")
print("\nteam-games", len(j), "  unmatched", int(j['p_pts'].isna().sum()))
j["d_pts"] = j["p_pts"] - j["pts"]
j["d_fga"] = j["p_fga"] - j["fga"]
j["d_min"] = j["p_min"] - j["minutes"]
for c in ["d_pts", "d_fga", "d_min"]:
    v = j[c].to_numpy(float)
    print("  %-6s max|diff| %.6f   n_nonzero %d" % (c, np.nanmax(np.abs(v)), int((np.abs(v) > 1e-9).sum())))
print("  roster size mean %.4f  min %d  max %d" % (j['n_app'].mean(), j['n_app'].min(), j['n_app'].max()))
print("  team pts sd %.4f   team minutes mean %.4f" % (j['pts'].std(ddof=1), j['minutes'].mean()))
print("  team-games with pts==0: %d ; fga==0: %d" % (int((j['pts'] == 0).sum()), int((j['fga'] == 0).sum())))

# per season team-game counts
print("\nteam-games by season", j.groupby('season').size().to_dict())
print("games by season", mtr.groupby('season')['game_id'].nunique().to_dict())

# D104 anchor: home advantage on 888 games (2023-24 regular season)
for yrs, lab in [([2023, 2024], "2023-24"), ([2022, 2023, 2024], "2022-24")]:
    s = mtr[mtr["season"].isin(yrs)]
    ng = s["game_id"].nunique()
    h = s[s["is_home"] == 1]["pts"].mean()
    a2 = s[s["is_home"] == 0]["pts"].mean()
    print("  %s games=%d  home-away=%.6f" % (lab, ng, h - a2))
