"""
E0 I0008 -- RUNG 1 / RUNG 2: pregame-observable height/size mismatch vs rebound efficiency.
No on-court lineup attribution used anywhere in this script (no possessions_v2 join, no
clock-time matching) -- this is the coordinator-redirected priority path because a null
result here is directly interpretable, unlike a rung-3 (on-court) null.

HARD PARTITION FILTER: master_player.parquet filtered to season in {2021,2022,2023,2024}
immediately after load (FILTER-POINT below). 2025/2026 never read into any dataframe.
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0008_height_differential"
EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]

mp = pd.read_parquet("data/masters/master_player.parquet")
bios = pd.read_csv("data/reference/player_bios.csv")

# FILTER-POINT
mp = mp[mp["season"].isin(EXPLORATION_SEASONS)].copy()
print("master_player after partition filter:", mp.shape, sorted(mp["season"].unique()))

# only rows with real minutes played (DNP rows carry no rebound signal)
mp = mp[(mp["minutes"].fillna(0) > 0)].copy()
print("after minutes>0 filter:", mp.shape)

bios_h = bios[["player_id", "season", "height_inches", "position_raw"]].drop_duplicates(["player_id", "season"])

mp = mp.merge(bios_h, on=["player_id", "season"], how="left")
print("own height matched:", mp["height_inches"].notna().mean().round(3), "of rows")

# ---- team roster height profile (RUNG 1): season minutes-weighted mean height per team ----
team_roster = mp.merge(bios_h.rename(columns={"player_id": "player_id"}), on=["player_id", "season"], how="left", suffixes=("", "_dup")) \
    if False else mp  # height already merged above; just aggregate

team_height_profile = (
    mp.dropna(subset=["height_inches"])
    .groupby(["team_id", "season"])
    .apply(lambda g: np.average(g["height_inches"], weights=g["minutes"]), include_groups=False)
    .rename("team_wtd_mean_height")
    .reset_index()
)
print("team-season height profiles:", team_height_profile.shape)

# ---- RUNG 2: top-rotation-only (top 8 by total season minutes) team height profile ----
season_minutes = mp.groupby(["team_id", "season", "player_id"])["minutes"].sum().reset_index()
season_minutes["rot_rank"] = season_minutes.groupby(["team_id", "season"])["minutes"].rank(ascending=False, method="first")
rotation_players = season_minutes[season_minutes["rot_rank"] <= 8][["team_id", "season", "player_id"]]
rot_h = rotation_players.merge(bios_h, on=["player_id", "season"], how="left").dropna(subset=["height_inches"])
rot_minutes = season_minutes.merge(rotation_players, on=["team_id", "season", "player_id"], how="inner") \
    .merge(bios_h, on=["player_id", "season"], how="left").dropna(subset=["height_inches"])
rotation_height_profile = (
    rot_minutes.groupby(["team_id", "season"])
    .apply(lambda g: np.average(g["height_inches"], weights=g["minutes"]), include_groups=False)
    .rename("rotation_wtd_mean_height")
    .reset_index()
)
print("rotation(top-8)-season height profiles:", rotation_height_profile.shape)

# ---- attach opponent's profiles to each player-game row ----
df = mp.dropna(subset=["height_inches", "opp_team_id"]).copy()
df = df.merge(
    team_height_profile.rename(columns={"team_id": "opp_team_id", "team_wtd_mean_height": "opp_roster_mean_height"}),
    on=["opp_team_id", "season"], how="left",
)
df = df.merge(
    rotation_height_profile.rename(columns={"team_id": "opp_team_id", "rotation_wtd_mean_height": "opp_rotation_mean_height"}),
    on=["opp_team_id", "season"], how="left",
)

df["rung1_height_diff"] = df["height_inches"] - df["opp_roster_mean_height"]
df["rung2_height_diff"] = df["height_inches"] - df["opp_rotation_mean_height"]

print("rows with rung1 diff:", df["rung1_height_diff"].notna().sum())
print("rows with rung2 diff:", df["rung2_height_diff"].notna().sum())

# ---- own recent rebound rate (partition-internal, no lookahead): trailing 5-game EWMA ----
df = df.sort_values(["player_id", "season", "game_date"]).copy()

def trailing_ewma(s, halflife=5):
    # shift(1) so the current game's own outcome never leaks into its own "recent rate" feature
    return s.shift(1).ewm(halflife=halflife, min_periods=3).mean()

df["own_recent_oreb_pct"] = df.groupby(["player_id", "season"])["offensive_rebound_percentage"].transform(trailing_ewma)
df["own_recent_dreb_pct"] = df.groupby(["player_id", "season"])["defensive_rebound_percentage"].transform(trailing_ewma)

keep = [
    "game_id", "season", "game_date", "player_id", "player_name", "team_id", "opp_team_id",
    "position", "position_raw", "minutes", "height_inches",
    "opp_roster_mean_height", "opp_rotation_mean_height",
    "rung1_height_diff", "rung2_height_diff",
    "offensive_rebound_percentage", "defensive_rebound_percentage",
    "own_recent_oreb_pct", "own_recent_dreb_pct",
]
df[keep].to_csv(f"{OUT}/player_game_height_vs_opponent.csv", index=False)
print(f"wrote {OUT}/player_game_height_vs_opponent.csv:", df.shape[0], "rows")
print("DONE build_rung1_rung2")
