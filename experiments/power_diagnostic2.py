"""Follow-up: which TARGETS carry stable individual signal, and does the
individual signal appear when we stop asking single noisy games?"""
import numpy as np
import pandas as pd

REPO = r"C:\Users\jgallagher\wnba-betting-model"
mp = pd.read_parquet(REPO + r"\data\masters\master_player.parquet")
mp = mp[(mp.season_type == "Regular Season") & (mp.minutes.fillna(0) >= 8)].copy()
mp = mp[mp.season.between(2021, 2024)]
mp["game_date"] = pd.to_datetime(mp["game_date"])

mp["pts36"] = mp.pts / mp.minutes * 36
mp["fga36"] = mp.fga / mp.minutes * 36
mp["fg3a36"] = mp.fg3a / mp.minutes * 36
mp["fta36"] = mp.fta / mp.minutes * 36
mp["min_g"] = mp.minutes

print("=" * 72)
print("A. WHICH TARGETS ARE STABLE ENOUGH TO CARRY INDIVIDUAL SIGNAL?")
print("   (signal share = between-player variance / total)")
print("=" * 72)
rows = []
for col, label in [("min_g", "minutes played"), ("fga36", "shot attempts /36"),
                   ("fg3a36", "3pt attempts /36"), ("fta36", "FT attempts /36"),
                   ("pts36", "POINTS /36 (what we tested)")]:
    d = mp[["player_id", "season", col]].dropna()
    g = d.groupby(["player_id", "season"])[col]
    d = d[g.transform("size") >= 20]
    g = d.groupby(["player_id", "season"])[col]
    grand = d[col].mean()
    means, sizes = g.mean(), g.size()
    between = float((sizes * (means - grand) ** 2).sum() / sizes.sum())
    within = float(g.transform(lambda x: ((x - x.mean()) ** 2).mean()).mean())
    share = between / (between + within)
    # minimum detectable split difference for the median player
    per = d.groupby("player_id")[col].agg(["size", "std"])
    per = per[per["size"] >= 40]
    mde = 2.8 * per["std"].median() * np.sqrt(2 / (per["size"].median() / 2))
    rows.append((label, share, per["std"].median(), mde, mde / d[col].mean()))
    print(f"{label:28s} signal {share:5.1%} | game-to-game sd {per['std'].median():6.2f} "
          f"| smallest detectable split {mde:5.2f} ({mde/d[col].mean():4.0%} of typical)")

print()
print("=" * 72)
print("B. DOES INDIVIDUAL SIGNAL APPEAR AT THE 20-GAME LEVEL? (reliability)")
print("=" * 72)
for col, label in [("min_g", "minutes"), ("fga36", "shot attempts/36"),
                   ("pts36", "points/36")]:
    d = mp[["player_id", "season", col]].dropna()
    g = d.groupby(["player_id", "season"])[col]
    d = d[g.transform("size") >= 20]
    g = d.groupby(["player_id", "season"])[col]
    grand = d[col].mean(); means, sizes = g.mean(), g.size()
    between = float((sizes * (means - grand) ** 2).sum() / sizes.sum())
    within = float(g.transform(lambda x: ((x - x.mean()) ** 2).mean()).mean())
    for n in (1, 10, 20, 40):
        rel = between / (between + within / n)
        print(f"  {label:18s} reliability of an n={n:2d}-game average: {rel:.2f}")
    print()

print("=" * 72)
print("C. THE MINUTES CHANNEL: do players differ in back-to-back response?")
print("=" * 72)
mt = pd.read_parquet(REPO + r"\data\masters\master_team.parquet")
mt = mt[(mt.season_type == "Regular Season") & mt.season.between(2021, 2024)].copy()
mt["game_date"] = pd.to_datetime(mt["game_date"])
sched = (mt[["game_id", "team_id", "season", "game_date"]].drop_duplicates()
         .sort_values(["team_id", "season", "game_date"]))
sched["rest"] = sched.groupby(["team_id", "season"])["game_date"].diff().dt.days
m = mp.merge(sched[["game_id", "team_id", "rest"]], on=["game_id", "team_id"], how="left")
m = m[m.rest.notna()].copy()
m["b2b"] = (m.rest <= 1).astype(int)
print(f"rows with rest known: {len(m):,} | back-to-back share: {m.b2b.mean():.1%}")
per = m.groupby("player_id").agg(n=("minutes", "size"), nb=("b2b", "sum"))
elig = per[(per.n >= 60) & (per.nb >= 12)].index
sub = m[m.player_id.isin(elig)]
piv = sub.groupby(["player_id", "b2b"])["minutes"].mean().unstack()
piv = piv.dropna(); piv["delta"] = piv[1] - piv[0]
print(f"eligible players: {len(piv)} | league mean B2B minutes change "
      f"{piv['delta'].mean():+.2f} | across-player spread (sd) {piv['delta'].std():.2f}")
ps = sub.groupby(["player_id", "season", "b2b"])["minutes"].mean().unstack().dropna()
ps["delta"] = ps[1] - ps[0]; ps = ps.reset_index()
pair = ps.merge(ps.assign(season=ps.season + 1), on=["player_id", "season"],
                suffixes=("", "_prev"))
if len(pair) > 15:
    print(f"year-over-year correlation of a player's own B2B minutes response "
          f"(n={len(pair)}): r = {pair['delta'].corr(pair['delta_prev']):+.3f}")
