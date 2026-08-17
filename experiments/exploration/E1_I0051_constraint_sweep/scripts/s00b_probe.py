"""E1_I0051 -- s00b PROBE 2.  The other candidate constrained families.

(1) player `possessions` -- does it close on a team-game total, and is that total FIXED?
(2) player `usage_percentage` -- does it sum to a fixed number per team-game (a percentage budget)?
(3) D104's possessions claim -- locate the definition actually used.
(4) the minutes budget seen as a FORECASTING constraint: how much of it is knowable before tip-off?
"""
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
MP = os.path.join(ROOT, r"data\masters\master_player.parquet")
MT = os.path.join(ROOT, r"data\masters\master_team.parquet")
ALLOWED = {2021, 2022, 2023, 2024}


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


COLS = ["game_id", "season", "season_type", "team_id", "player_id", "minutes", "pts", "fga",
        "fta", "oreb", "dreb", "reb", "ast", "tov", "possessions", "usage_percentage",
        "estimated_usage_percentage", "pace"]
mp = pd.read_parquet(MP, columns=COLS)
mp = mp[(mp["season"].isin(sorted(ALLOWED))) & (mp["season_type"] == "Regular Season")].copy()
for c in COLS:
    if c in ("game_id", "season", "season_type", "team_id", "player_id"):
        continue
    mp[c] = pd.to_numeric(mp[c], errors="coerce")
mp["minutes"] = mp["minutes"].fillna(0.0)
d = mp[mp["minutes"] > 0].copy()
d["tg"] = d["game_id"].astype(str) + "|" + d["team_id"].astype(str)

hdr("NULLITY of the two candidate columns on the appeared roster")
for c in ("possessions", "usage_percentage", "estimated_usage_percentage", "pace"):
    v = d[c]
    print("  %-28s  non-null %6d / %6d (%.4f)   mean %10.4f  sd %9.4f"
          % (c, int(v.notna().sum()), len(v), float(v.notna().mean()),
             float(v.mean()) if v.notna().any() else np.nan,
             float(v.std(ddof=1)) if v.notna().any() else np.nan))

hdr("(1) PLAYER POSSESSIONS -- team-game sum")
sub = d[d["possessions"].notna()].copy()
if len(sub):
    g = sub.groupby("tg", sort=False).agg(P=("possessions", "sum"), n=("possessions", "size"))
    full = d.groupby("tg", sort=False).size().rename("n_all")
    g = g.join(full)
    g_complete = g[g["n"] == g["n_all"]]
    print("  team-games with a possessions value on EVERY appeared player: %d of %d"
          % (len(g_complete), len(g)))
    s = g_complete["P"]
    if len(s):
        print("  team-game sum of player possessions: mean %.4f  sd %.4f  cv %.5f  min %.2f  max %.2f"
              % (s.mean(), s.std(ddof=1), s.std(ddof=1) / s.mean(), s.min(), s.max()))
    mt = pd.read_parquet(MT, columns=["game_id", "season", "season_type", "team_id",
                                      "fga", "fta", "oreb", "tov"])
    mt = mt[(mt["season"].isin(sorted(ALLOWED))) & (mt["season_type"] == "Regular Season")].copy()
    mt["tg"] = mt["game_id"].astype(str) + "|" + mt["team_id"].astype(str)
    mt["poss_box"] = (mt["fga"].astype(float) + 0.44 * mt["fta"].astype(float)
                      - mt["oreb"].astype(float) + mt["tov"].astype(float))
    j = g_complete.join(mt.set_index("tg")["poss_box"], how="inner")
    if len(j):
        dd = j["P"] - j["poss_box"]
        print("  vs box-derived team possessions: n %d  mean diff %+.4f  sd %.4f  max|.| %.4f  "
              "corr %.5f" % (len(j), dd.mean(), dd.std(ddof=1), np.abs(dd).max(),
                             float(np.corrcoef(j["P"], j["poss_box"])[0, 1])))

hdr("(2) PLAYER usage_percentage -- team-game sum (is there a percentage budget?)")
for col in ("usage_percentage", "estimated_usage_percentage"):
    sub = d[d[col].notna()].copy()
    if not len(sub):
        print("  %s : all null" % col)
        continue
    g = sub.groupby("tg", sort=False).agg(U=("%s" % col, "sum"), n=(col, "size"))
    full = d.groupby("tg", sort=False).size().rename("n_all")
    g = g.join(full)
    gc = g[g["n"] == g["n_all"]]
    s = gc["U"]
    print("  %-28s complete team-games %d   sum: mean %9.4f  sd %8.4f  cv %.5f  "
          "min %8.3f  max %8.3f" % (col, len(gc), s.mean(), s.std(ddof=1),
                                    s.std(ddof=1) / s.mean() if s.mean() else np.nan,
                                    s.min(), s.max()))
    for tgt in (1.0, 5.0, 100.0, 500.0):
        print("       frac within 1%% of %7.2f : %.5f" % (tgt, float((np.abs(s - tgt) / tgt < .01).mean())))

hdr("(4) THE MINUTES BUDGET AS A FORECASTING CONSTRAINT")
agg = d.groupby("tg", sort=False).agg(T_min=("minutes", "sum"), n=("minutes", "size"))
reg = (np.abs(agg["T_min"] - 200.0) < 0.5)
print("  regulation (T_min == 200 +/- 0.5): %d of %d = %.6f" % (int(reg.sum()), len(agg),
                                                                float(reg.mean())))
print("  If a forecaster assumes 200 for every team-game:")
err = agg["T_min"] - 200.0
print("     mean signed error %+.5f  MAE %.5f  sd %.5f  max %.4f  as %% of budget %.4f%%"
      % (err.mean(), np.abs(err).mean(), err.std(ddof=1), np.abs(err).max(),
         100.0 * np.abs(err).mean() / 200.0))
print("  Contrast, assuming the MEAN team points for every team-game:")
aggp = d.groupby("tg", sort=False)["pts"].sum()
ep = aggp - aggp.mean()
print("     MAE %.5f  as %% of mean total %.4f%%" % (np.abs(ep).mean(),
                                                     100.0 * np.abs(ep).mean() / aggp.mean()))
aggf = d.groupby("tg", sort=False)["fga"].sum()
ef = aggf - aggf.mean()
print("  Contrast, assuming the MEAN team attempts:")
print("     MAE %.5f  as %% of mean total %.4f%%" % (np.abs(ef).mean(),
                                                     100.0 * np.abs(ef).mean() / aggf.mean()))

hdr("ROSTER SIZE -- the denominator of the minutes budget")
print(agg["n"].describe().to_string())
print("  realised appeared roster mean %.4f" % agg["n"].mean())

hdr("DONE s00b")
