"""
Robustness fix: the first-pass interaction test computed each opponent's
season-zone allowed rate INCLUDING the very shots being tested against it
(and the player's own game inside that season aggregate). That is a
self-inclusion / mechanical-correlation risk -- a made shot directly
inflates the very "opponent allowance" number used to explain it, and the
bias is largest exactly where sample sizes are thinnest (Corner 3), which
is suspicious given Corner 3 showed NO real between-team dispersion in the
season-level test yet the LARGEST interaction correlation in the first pass.

This script recomputes the opponent zone_conv_residual as a LEAVE-ONE-GAME-OUT
statistic (excise the current game's makes/attempts from that opponent's
season-zone tally before computing the rate the shot is compared against),
and re-runs the same correlation test. Still 2021-2024 only.
"""
import pandas as pd
import numpy as np

SEASONS = [2021, 2022, 2023, 2024]
TYPES = ["regular", "playoffs"]
FILES = [f"data/shotcharts/shots_{s}_{t}.parquet" for s in SEASONS for t in TYPES]

dfs = []
for f in FILES:
    d = pd.read_parquet(f)
    d["season"] = int(f.split("shots_")[1][:4])
    dfs.append(d)
shots = pd.concat(dfs, ignore_index=True)
assert shots["season"].max() <= 2024

def merge_zone(z):
    return "Corner 3" if z in ("Left Corner 3", "Right Corner 3") else z

shots["zone"] = shots["SHOT_ZONE_BASIC"].map(merge_zone)
shots["made"] = shots["SHOT_MADE_FLAG"].astype(int)

game_teams = shots.groupby("GAME_ID")["TEAM_ID"].unique()
opp_lookup = {}
for gid, teams in game_teams.items():
    if len(teams) == 2:
        opp_lookup[(gid, teams[0])] = teams[1]
        opp_lookup[(gid, teams[1])] = teams[0]
shots["OPP_TEAM_ID"] = [opp_lookup.get((g, t), np.nan) for g, t in zip(shots["GAME_ID"], shots["TEAM_ID"])]
shots = shots[shots["OPP_TEAM_ID"].notna()].copy()
shots["OPP_TEAM_ID"] = shots["OPP_TEAM_ID"].astype(shots["TEAM_ID"].dtype)

# season-zone totals per opponent (defense)
season_tot = (
    shots.groupby(["OPP_TEAM_ID", "season", "zone"])
    .agg(season_att=("made", "size"), season_mk=("made", "sum"))
    .reset_index()
)
season_pool = (
    shots.groupby(["OPP_TEAM_ID", "season"])
    .agg(pool_att=("made", "size"), pool_mk=("made", "sum"))
    .reset_index()
)
# per-game-zone totals per opponent (defense), i.e. what happened in THIS game in THIS zone against this defense
game_zone = (
    shots.groupby(["OPP_TEAM_ID", "season", "GAME_ID", "zone"])
    .agg(game_att=("made", "size"), game_mk=("made", "sum"))
    .reset_index()
)
game_pool = (
    shots.groupby(["OPP_TEAM_ID", "season", "GAME_ID"])
    .agg(gpool_att=("made", "size"), gpool_mk=("made", "sum"))
    .reset_index()
)

shots = shots.merge(season_tot, on=["OPP_TEAM_ID", "season", "zone"], how="left")
shots = shots.merge(season_pool, on=["OPP_TEAM_ID", "season"], how="left")
shots = shots.merge(game_zone, on=["OPP_TEAM_ID", "season", "GAME_ID", "zone"], how="left")
shots = shots.merge(game_pool, on=["OPP_TEAM_ID", "season", "GAME_ID"], how="left")

# leave-one-GAME-out opponent zone rate and pooled rate
shots["loo_att"] = shots["season_att"] - shots["game_att"]
shots["loo_mk"] = shots["season_mk"] - shots["game_mk"]
shots["loo_pool_att"] = shots["pool_att"] - shots["gpool_att"]
shots["loo_pool_mk"] = shots["pool_mk"] - shots["gpool_mk"]

MIN_LOO = 20
ok = (shots["loo_att"] >= MIN_LOO) & (shots["loo_pool_att"] >= MIN_LOO)
print(f"Shots with usable leave-one-game-out opponent sample (zone att>={MIN_LOO}): {ok.sum()} / {len(shots)}")
shots = shots[ok].copy()

shots["loo_zone_rate"] = shots["loo_mk"] / shots["loo_att"]
shots["loo_pool_rate"] = shots["loo_pool_mk"] / shots["loo_pool_att"]
shots["zone_conv_residual_loo"] = shots["loo_zone_rate"] - shots["loo_pool_rate"]

# player-zone baseline: same leave-current-season-out construction as first pass
pz = (
    shots.groupby(["PLAYER_ID", "season", "zone"])
    .agg(att=("made", "size"), mk=("made", "sum"))
    .reset_index()
)
records = []
for (pid, zone), g in pz.groupby(["PLAYER_ID", "zone"]):
    for _, row in g.iterrows():
        other = g[g["season"] != row["season"]]
        if other["att"].sum() >= 10:
            records.append((pid, row["season"], zone, other["mk"].sum() / other["att"].sum()))
baseline = pd.DataFrame(records, columns=["PLAYER_ID", "season", "zone", "player_zone_baseline"])

shots_b = shots.merge(baseline, on=["PLAYER_ID", "season", "zone"], how="inner")
shots_b["shooting_residual"] = shots_b["made"] - shots_b["player_zone_baseline"]

print(f"\nShots with both LOO opponent measure and player baseline: {len(shots_b)}")
print("\n=== LEAVE-ONE-GAME-OUT interaction test: corr(shooting_residual, opp zone_conv_residual_loo) ===")
for zone, g in shots_b.groupby("zone"):
    if len(g) < 200:
        continue
    corr = g["shooting_residual"].corr(g["zone_conv_residual_loo"])
    med = g["zone_conv_residual_loo"].median()
    hi = g[g["zone_conv_residual_loo"] > med]["shooting_residual"].mean()
    lo = g[g["zone_conv_residual_loo"] <= med]["shooting_residual"].mean()
    n_hi = (g["zone_conv_residual_loo"] > med).sum()
    n_lo = (g["zone_conv_residual_loo"] <= med).sum()
    # quick SE of the mean-difference for a rough sense of noise
    se = np.sqrt(g["shooting_residual"].var() / n_hi + g["shooting_residual"].var() / n_lo)
    print(f"{zone:<24} n={len(g):>6}  corr={corr:+.4f}  diff(hi-lo)={hi-lo:+.4f}  approx_SE(diff)~={se:.4f}")

shots_b.to_csv("experiments/exploration/E0_I0004_shot_location_allowance/shot_level_residuals_LOO_2021_2024.csv", index=False)
print("\nDone.")
