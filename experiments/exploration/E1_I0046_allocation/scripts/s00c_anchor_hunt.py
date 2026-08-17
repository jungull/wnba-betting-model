"""E1_I0046 s00c -- READ-ONLY anchor hunt: locate the exact row sets behind published anchors."""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")

mt = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_team.parquet"),
                     columns=["game_id", "season", "season_type", "team_id", "is_home", "pts"])
mt = mt[mt["season"].isin([2021, 2022, 2023, 2024])]
r = mt[mt["season_type"] == "Regular Season"]
print("D104 hunt: home-minus-away mean team points")
for lab, yrs in [("2021-24", [2021, 2022, 2023, 2024]), ("2022-24", [2022, 2023, 2024]),
                 ("2023-24", [2023, 2024]), ("2021", [2021]), ("2022", [2022])]:
    s = r[r["season"].isin(yrs)]
    print("  %-8s games=%4d teamgames=%4d  diff=%.6f"
          % (lab, s["game_id"].nunique(), len(s),
             s[s.is_home == 1]["pts"].mean() - s[s.is_home == 0]["pts"].mean()))
s = mt[mt["season_type"] == "Playoffs"]
print("  playoffs incl: 2021-24 all types games=%d diff=%.6f"
      % (mt["game_id"].nunique(), mt[mt.is_home == 1]["pts"].mean() - mt[mt.is_home == 0]["pts"].mean()))

print("\nD076 hunt: appeared player-games")
pf = pd.read_parquet(os.path.join(EXP, r"E1_I0033_aggregation_level\_player_frame.parquet"))
print("  I0033 _player_frame rows", len(pf), " appeared sum", int(pf["appeared"].sum()))
for yrs in [[2021, 2022, 2023, 2024], [2022, 2023, 2024], [2023, 2024]]:
    q = pf[pf["season"].isin(yrs)]
    print("   seasons %s rows %d appeared %d" % (yrs, len(q), int(q["appeared"].sum())))

mp = pd.read_parquet(os.path.join(ROOT, r"data\masters\master_player.parquet"),
                     columns=["game_id", "season", "season_type", "player_id", "minutes", "in_gamelog"])
mp = mp[mp["season"].isin([2021, 2022, 2023, 2024])]
for st in ["Regular Season", "Playoffs", "BOTH"]:
    q = mp if st == "BOTH" else mp[mp["season_type"] == st]
    m = pd.to_numeric(q["minutes"], errors="coerce").fillna(0)
    print("  master_player %-14s rows=%d in_gamelog=%d minutes>0=%d"
          % (st, len(q), int(q["in_gamelog"].sum()), int((m > 0).sum())))

print("\nE1_I0043 screen_results anchor (byte read)")
p = os.path.join(EXP, r"E0_I0016_efficiency_predictors\screen_results.csv")
print("  exists", os.path.exists(p))
if os.path.exists(p):
    sr = pd.read_csv(p)
    print("  cols", list(sr.columns)[:20], "rows", len(sr))
