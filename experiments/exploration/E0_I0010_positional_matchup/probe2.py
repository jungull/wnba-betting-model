"""Probe position-field coverage. E0 I0010. Partition: 2021-2024 only."""
import pandas as pd, numpy as np
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
mp = pd.read_parquet(ROOT + r"\data\masters\master_player.parquet")
# FILTER-POINT
mp = mp[mp["season"].isin([2021, 2022, 2023, 2024])].copy()
assert set(mp["season"].unique()) <= {2021, 2022, 2023, 2024}
print("seasons after filter:", sorted(mp["season"].unique()))

pos = mp["position"].fillna("").astype(str).str.strip()
print("\nposition value counts (all rows):")
print(pos.value_counts(dropna=False).head(20).to_string())
print("\nnonblank frac overall: %.4f" % (pos != "").mean())
print("\nnonblank frac by season:")
print(mp.assign(nb=(pos != "")).groupby("season")["nb"].mean().to_string())

# with minutes>0
m = mp["minutes"].fillna(0) > 0
print("\nrows with minutes>0:", int(m.sum()))
print("nonblank position | minutes>0: %.4f" % (pos[m] != "").mean())
print("by season (minutes>0):")
print(mp[m].assign(nb=(pos[m] != "")).groupby("season")["nb"].mean().to_string())

# does a player have a consistent position within a season?
mp["_pos"] = pos
sub = mp[m & (pos != "")]
g = sub.groupby(["player_id", "season"])["_pos"].nunique()
print("\nplayer-seasons with >1 distinct position label: %d / %d" % ((g > 1).sum(), len(g)))

# how many player-seasons total (minutes>0) and how many have ANY position label
allps = mp[m].groupby(["player_id", "season"]).size()
labps = sub.groupby(["player_id", "season"]).size()
print("player-seasons minutes>0: %d ; with >=1 labeled row: %d" % (len(allps), len(labps)))

# prior-season availability: players in season s who also played in s-1
for s in [2022, 2023, 2024]:
    cur = set(mp[m & (mp.season == s)]["player_id"])
    prv = set(mp[m & (mp.season == s - 1)]["player_id"])
    rows_cur = mp[m & (mp.season == s)]
    frac_rows = rows_cur["player_id"].isin(prv).mean()
    print("season %d: players %d, with prior-season history %d (%.3f of players); %.3f of player-games"
          % (s, len(cur), len(cur & prv), len(cur & prv) / len(cur), frac_rows))

# minutes / possessions sanity
print("\nminutes describe:", mp.loc[m, "minutes"].describe().to_dict())
print("possessions null frac (min>0): %.4f" % mp.loc[m, "possessions"].isna().mean())
print("possessions describe:", mp.loc[m, "possessions"].describe().to_dict())
print("pace null frac (min>0): %.4f" % mp.loc[m, "pace"].isna().mean())
# team-game possessions consistency
tg = mp[m].groupby(["game_id", "team_id"]).agg(mins=("minutes", "sum"), poss=("possessions", "sum"))
print("\nteam-game total minutes describe:", tg["mins"].describe().to_dict())
print("team-game summed player possessions describe:", tg["poss"].describe().to_dict())
print("\nn team-games:", len(tg), " n games:", mp["game_id"].nunique())
