"""Could the heterogeneity screen have found individual effects if they existed?

Decomposes per-36 scoring into signal vs noise, then computes the minimum
detectable per-player interaction effect. If the minimum detectable effect is
larger than any plausible real effect, the null result is VACUOUS (a power
failure), not evidence of absence.
"""
import numpy as np
import pandas as pd

REPO = r"C:\Users\jgallagher\wnba-betting-model"
mp = pd.read_parquet(REPO + r"\data\masters\master_player.parquet")
mp = mp[(mp.season_type == "Regular Season") & (mp.minutes.fillna(0) >= 8)].copy()
mp = mp[mp.season.between(2021, 2024)]
mp["game_date"] = pd.to_datetime(mp["game_date"])

# channel rates per 36
mp["r_fg3"] = 3 * mp.fg3m / mp.minutes * 36
mp["r_paint"] = mp.points_paint / mp.minutes * 36
mp["r_ft"] = mp.ftm / mp.minutes * 36
mp["r_np2"] = (mp.pts - 3 * mp.fg3m - mp.ftm - mp.points_paint) / mp.minutes * 36
mp["r_pts"] = mp.pts / mp.minutes * 36

print("=" * 68)
print("1. HOW MUCH OF GAME-TO-GAME SCORING IS EVEN PREDICTABLE?")
print("=" * 68)
for ch in ["r_pts", "r_fg3", "r_paint", "r_ft", "r_np2"]:
    d = mp[["player_id", "season", ch]].dropna()
    g = d.groupby(["player_id", "season"])[ch]
    keep = g.transform("size") >= 20
    d = d[keep]
    g = d.groupby(["player_id", "season"])[ch]
    # variance decomposition: between player-seasons vs within (game-to-game)
    grand = d[ch].mean()
    means = g.mean()
    sizes = g.size()
    between = float((sizes * (means - grand) ** 2).sum() / sizes.sum())
    within = float(g.transform(lambda x: ((x - x.mean()) ** 2).mean()).mean())
    total = between + within
    # split-half reliability of a player-season mean at n=20 games
    rel20 = between / (between + within / 20)
    print(f"{ch:8s}  between-player var {between:6.2f} | within-player (noise) var "
          f"{within:7.2f} | signal share {between/total:5.1%} | "
          f"reliability of a 20-game mean {rel20:.2f}")

print()
print("=" * 68)
print("2. MINIMUM DETECTABLE INDIVIDUAL EFFECT (the decisive number)")
print("=" * 68)
# Per player: how many games, and what is the residual sd around their own mean?
for ch, label in [("r_pts", "total points/36"), ("r_np2", "non-paint 2s/36"),
                  ("r_fg3", "3pt points/36")]:
    d = mp[["player_id", "season", ch]].dropna()
    per = d.groupby("player_id")[ch].agg(["size", "std"])
    per = per[per["size"] >= 40]
    med_n = per["size"].median()
    med_sd = per["std"].median()
    # a binary condition splits a player's games ~half/half; detecting a
    # difference in means between the two halves at 80% power, alpha .05
    # needs delta >= 2.8 * sd * sqrt(2/(n/2))
    n_half = med_n / 2
    mde = 2.8 * med_sd * np.sqrt(2 / n_half)
    print(f"{label:18s} median player: {med_n:5.0f} games, game-to-game sd "
          f"{med_sd:5.2f} -> smallest detectable split difference = {mde:5.2f} per 36")
    print(f"{'':18s} as a share of a typical rate: {mde / d[ch].mean():.0%} of average production")

print()
print("=" * 68)
print("3. WHAT WE ACTUALLY LOOKED FOR vs WHAT WE COULD SEE")
print("=" * 68)
print("The pooled screen's confirmed features move error by 0.1-0.9%.")
print("An INTERACTION is a modulation of that already-tiny main effect.")
print("Section 2 says the smallest individual split difference we could")
print("reliably detect is printed above -- compare to the league-wide home")
print("effect of +0.38 pts/36 (the only condition effect we have measured).")

# 4. is minutes response the missing channel?
print()
print("=" * 68)
print("4. UNTESTED CHANNEL: do players differ in MINUTES response?")
print("=" * 68)
mt = pd.read_parquet(REPO + r"\data\masters\master_team.parquet")
mt = mt[(mt.season_type == "Regular Season") & mt.season.between(2021, 2024)].copy()
mt["game_date"] = pd.to_datetime(mt["game_date"])
sched = mt[["team_id", "season", "game_date"]].drop_duplicates().sort_values(
    ["team_id", "season", "game_date"])
sched["rest"] = sched.groupby(["team_id", "season"])["game_date"].diff().dt.days
m = mp.merge(sched, on=["team_id", "season", "game_date"], how="left")
m["b2b"] = (m.rest <= 1).astype(float)
sub = m[m.rest.notna()]
per = sub.groupby("player_id").agg(n=("minutes", "size"), n_b2b=("b2b", "sum"))
elig = per[(per.n >= 60) & (per.n_b2b >= 10)].index
sub = sub[sub.player_id.isin(elig)]
diffs = sub.groupby(["player_id", "b2b"])["minutes"].mean().unstack()
diffs = diffs.dropna()
diffs["delta"] = diffs[1.0] - diffs[0.0]
print(f"players with >=60 games and >=10 back-to-backs: {len(diffs)}")
print(f"league mean back-to-back MINUTES change: {diffs['delta'].mean():+.2f} min "
      f"| spread across players (sd): {diffs['delta'].std():.2f}")
# is the per-player minutes response stable across seasons? (the trait test)
ps = sub.groupby(["player_id", "season", "b2b"])["minutes"].mean().unstack().dropna()
ps["delta"] = ps[1.0] - ps[0.0]
ps = ps.reset_index()
pair = ps.merge(ps.assign(season=ps.season + 1), on=["player_id", "season"],
                suffixes=("", "_prev"))
if len(pair) > 20:
    r = pair["delta"].corr(pair["delta_prev"])
    print(f"year-over-year correlation of a player's own back-to-back MINUTES "
          f"response (n={len(pair)} pairs): r = {r:+.3f}")
    print("  (compare: personal home-lift SCORING response was r=+0.054)")
