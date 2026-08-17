"""E1_I0051_constraint_sweep -- s00 PROBE.

PURPOSE.  Before any prereg is written, establish -- arithmetically, on the real data -- WHICH of
the programme's candidate responses actually sit under a budget that is FIXED AT A HIGHER LEVEL.

This is the distinction the whole screen turns on and it is not a matter of opinion:

  * player MINUTES sum to a team-game budget that is fixed by the RULES (5 on the floor x 40 min
    = 200, plus 25 per overtime period).  Known before tip-off, exactly.
  * player POINTS sum to the team total, but the TEAM TOTAL IS ITSELF THE OUTCOME.  It is not
    fixed at a higher level; it is the sum.  Modelling player points independently implies a team
    total, it does not violate a budget.
  * player POSSESSIONS -- D104 says the two teams' possessions are IDENTICAL in 970 of 970 games.
    That is a cross-team identity at the team-game level.

PARTITION: 2021-2024 only.  2025/2026 never read.
NO WRITES outside E1_I0051_constraint_sweep/.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
pd.set_option("display.width", 200)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
MP = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT = os.path.join(ROOT, r"data\masters\master_team.parquet")
ALLOWED = {2021, 2022, 2023, 2024}


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


hdr("COLUMNS AVAILABLE")
pmeta = pd.read_parquet(MP).head(0)
tmeta = pd.read_parquet(MT).head(0)
print("master_player  n_cols=%d" % len(pmeta.columns))
print(sorted(pmeta.columns.tolist()))
print()
print("master_team    n_cols=%d" % len(tmeta.columns))
print(sorted(tmeta.columns.tolist()))

hdr("MINUTES BUDGET -- IS THE TEAM-GAME SUM FIXED?")
mp = pd.read_parquet(MP, columns=["game_id", "season", "season_type", "game_date", "team_id",
                                  "player_id", "minutes", "pts", "fga"])
mp = mp[(mp["season"].isin(sorted(ALLOWED))) & (mp["season_type"] == "Regular Season")].copy()
mp["minutes"] = pd.to_numeric(mp["minutes"], errors="coerce").fillna(0.0)
for c in ("pts", "fga"):
    mp[c] = pd.to_numeric(mp[c], errors="coerce").fillna(0.0)
d = mp[mp["minutes"] > 0].copy()
d["tg"] = d["game_id"].astype(str) + "|" + d["team_id"].astype(str)
agg = d.groupby("tg", sort=False).agg(T_min=("minutes", "sum"), T_pts=("pts", "sum"),
                                      T_fga=("fga", "sum"), n_roster=("pts", "size"))
print("team-games: %d   appeared player-games: %d" % (len(agg), len(d)))
print()
print("T_min  describe:")
print(agg["T_min"].describe(percentiles=[.001, .01, .25, .5, .75, .99, .999]).to_string())
print()
vc = agg["T_min"].round(4).value_counts().sort_index()
print("T_min distinct rounded values (top 20 by count):")
print(vc.sort_values(ascending=False).head(20).to_string())
print()
for target in (200.0, 225.0, 250.0, 275.0):
    n = int((np.abs(agg["T_min"] - target) < 0.5).sum())
    print("  within 0.5 of %6.1f : %5d  (%.4f)" % (target, n, n / len(agg)))
resid = agg["T_min"] - 25.0 * np.round(agg["T_min"] / 25.0)
print()
print("residual off the nearest multiple of 25:  mean %+.6f  sd %.6f  max|.| %.6f  "
      "frac |.|<0.5 %.6f" % (resid.mean(), resid.std(ddof=1), np.abs(resid).max(),
                             float((np.abs(resid) < 0.5).mean())))

hdr("CONTRAST -- T_pts AND T_fga ARE NOT FIXED")
for c in ("T_pts", "T_fga"):
    s = agg[c]
    print("%-6s  mean %8.3f  sd %7.3f  cv %.5f  min %6.1f  max %6.1f  n_distinct %d"
          % (c, s.mean(), s.std(ddof=1), s.std(ddof=1) / s.mean(), s.min(), s.max(), s.nunique()))
s = agg["T_min"]
print("%-6s  mean %8.3f  sd %7.3f  cv %.5f  min %6.1f  max %6.1f  n_distinct %d"
      % ("T_min", s.mean(), s.std(ddof=1), s.std(ddof=1) / s.mean(), s.min(), s.max(), s.nunique()))

hdr("POSSESSIONS -- IS THERE A POSSESSIONS COLUMN, AND ARE THE TWO SIDES EQUAL? (D104)")
mt = pd.read_parquet(MT)
mt = mt[(mt["season"].isin(sorted(ALLOWED))) & (mt["season_type"] == "Regular Season")].copy()
poss_cols = [c for c in mt.columns if "poss" in str(c).lower()]
print("columns whose name contains 'poss' (diagnostic only, not a selection rule):", poss_cols)
need = ["fga", "fta", "oreb", "tov"]
have = [c for c in need if c in mt.columns]
print("box columns present for a possessions estimate:", have)
if len(have) == 4:
    mt["poss_est"] = (mt["fga"].astype(float) + 0.44 * mt["fta"].astype(float)
                      - mt["oreb"].astype(float) + mt["tov"].astype(float))
    piv = mt.pivot_table(index="game_id", columns=None, values="poss_est", aggfunc=list)
    both = mt.groupby("game_id")["poss_est"].agg(["count", "min", "max"])
    both = both[both["count"] == 2]
    dif = (both["max"] - both["min"])
    print("games with both sides: %d   |diff| mean %.4f  sd %.4f  max %.4f  "
          "frac exactly 0 %.6f  frac <=1 %.6f"
          % (len(both), dif.mean(), dif.std(ddof=1), dif.max(),
             float((dif == 0).mean()), float((dif <= 1).mean())))

hdr("ZERO-SHARE CENSUS (why a log-ratio transform is unavailable)")
for num, lab in ((d["pts"], "pts"), (d["fga"], "fga"), (d["minutes"], "minutes")):
    print("  %-8s exact zeros among appeared player-games: %5d / %5d  (%.4f)"
          % (lab, int((num == 0).sum()), len(num), float((num == 0).mean())))

hdr("DONE s00")
