"""
E0 I0005 -- build player x game turnover exposure/rate + opponent defensive pressure.

HARD RULE (GRAPH_POLICY 13.2): exploration partition ONLY = seasons 2021-2024.
Filter is applied immediately after each parquet load, before any other computation.
2025/2026 rows are dropped and never read further (no counts, no describes on them).

Leakage discipline: both the player's own "tendency" and the opponent's "pressure" are
computed LEAVE-ONE-GAME-OUT at the season level (this game's own contribution subtracted
out) so neither predictor is mechanically part of the outcome it is used to explain.
"""
import pandas as pd
import numpy as np

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program"
OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0005_turnover_interaction"

EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]

# ---------------------------------------------------------------------------
# 1. Player turnover targets (exposure + rate), partition filter applied first
# ---------------------------------------------------------------------------
tov = pd.read_parquet(f"{ROOT}/turnover_targets_v1/player_turnover_targets_v1.parquet")
tov = tov[tov["season"].isin(EXPLORATION_SEASONS)].copy()
print("turnover targets rows after partition filter:", len(tov), "seasons present:", sorted(tov["season"].unique()))

# keep only rows where a rate is even definable (mirrors the frozen artifact's own flag)
tov = tov[tov["rate_defined"] == True].copy()
print("rows with rate_defined:", len(tov))

# ---------------------------------------------------------------------------
# 2. Possessions v2 -> per (game_id, team_id) opponent id + defensive forced-TO tally
# ---------------------------------------------------------------------------
poss = pd.read_parquet(f"{ROOT}/possessions_v2/possessions_raw_v2.parquet",
                        columns=["game_id", "season", "offense_team_id", "defense_team_id",
                                 "end_reason", "lineup_valid_ten"])
poss["season"] = poss["season"].astype(int)
poss = poss[poss["season"].isin(EXPLORATION_SEASONS)].copy()
print("possessions rows after partition filter:", len(poss), "seasons present:", sorted(poss["season"].unique()))

# schedule: game_id, team_id -> opponent_team_id (each game has exactly one offense/defense pair,
# symmetric across the two possession directions)
sched = poss[["game_id", "offense_team_id", "defense_team_id"]].drop_duplicates()
sched = sched.rename(columns={"offense_team_id": "team_id", "defense_team_id": "opponent_team_id"})
sched = sched.drop_duplicates(subset=["game_id", "team_id"])
print("schedule rows (game,team):", len(sched))

# defensive possessions per (game, defense_team) + whether it ended in a turnover
poss["is_tov"] = (poss["end_reason"] == "turnover").astype(int)
game_def = (poss.groupby(["game_id", "defense_team_id", "season"], as_index=False)
                 .agg(def_poss=("is_tov", "size"), def_tov=("is_tov", "sum")))
game_def = game_def.rename(columns={"defense_team_id": "team_id"})
print("game-level defensive tallies:", len(game_def))

# season-team totals (for leave-one-game-out)
season_def_tot = (game_def.groupby(["team_id", "season"], as_index=False)
                            .agg(season_def_poss=("def_poss", "sum"), season_def_tov=("def_tov", "sum")))

game_def = game_def.merge(season_def_tot, on=["team_id", "season"], how="left")
game_def["loo_def_poss"] = game_def["season_def_poss"] - game_def["def_poss"]
game_def["loo_def_tov"] = game_def["season_def_tov"] - game_def["def_tov"]
game_def["opp_pressure_loo"] = np.where(game_def["loo_def_poss"] > 0,
                                         100.0 * game_def["loo_def_tov"] / game_def["loo_def_poss"],
                                         np.nan)
# this is: "team_id's" own defensive forced-TO rate for the rest of the season, excluding this game

# ---------------------------------------------------------------------------
# 3. Player-season totals -> leave-one-game-out player tendency
# ---------------------------------------------------------------------------
season_player_tot = (tov.groupby(["player_id", "season"], as_index=False)
                         .agg(season_tov=("turnovers", "sum"),
                              season_poss=("realised_off_possessions", "sum")))
tov = tov.merge(season_player_tot, on=["player_id", "season"], how="left")
tov["loo_poss"] = tov["season_poss"] - tov["realised_off_possessions"]
tov["loo_tov"] = tov["season_tov"] - tov["turnovers"]
tov["player_tendency_loo"] = np.where(tov["loo_poss"] > 0,
                                       100.0 * tov["loo_tov"] / tov["loo_poss"],
                                       np.nan)

# ---------------------------------------------------------------------------
# 4. Attach opponent for each player-game, then attach that opponent's LOO pressure
#    (as it applies to THIS game -- opponent's defense against this player's team)
# ---------------------------------------------------------------------------
tov = tov.merge(sched, on=["game_id", "team_id"], how="left")
missing_opp = tov["opponent_team_id"].isna().sum()
print("player-game rows missing an opponent match:", missing_opp)

opp_pressure = game_def[["game_id", "team_id", "opp_pressure_loo"]].rename(
    columns={"team_id": "opponent_team_id", "opp_pressure_loo": "opponent_pressure_loo"})
tov = tov.merge(opp_pressure, on=["game_id", "opponent_team_id"], how="left")

# ---------------------------------------------------------------------------
# 5. Final analysis frame
# ---------------------------------------------------------------------------
keep_cols = ["game_id", "team_id", "player_id", "season", "season_type", "minutes",
             "realised_off_possessions", "turnovers", "turnovers_per_100_off_poss",
             "player_tendency_loo", "opponent_team_id", "opponent_pressure_loo"]
frame = tov[keep_cols].copy()

before = len(frame)
frame = frame.dropna(subset=["player_tendency_loo", "opponent_pressure_loo"])
print(f"dropped {before - len(frame)} rows with undefined LOO tendency/pressure (thin season support)")
print("final analysis frame rows:", len(frame))
print("season counts in final frame:", frame["season"].value_counts().sort_index().to_dict())
assert set(frame["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"

frame.to_csv(f"{OUT}/player_game_analysis.csv", index=False)
print("wrote", f"{OUT}/player_game_analysis.csv")

# quick sanity prints
print(frame[["turnovers_per_100_off_poss", "player_tendency_loo", "opponent_pressure_loo"]].describe())
