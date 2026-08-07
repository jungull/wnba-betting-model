"""
E0 I0009 (family F_TURNOVER_PRESSURE) -- build frame for the ADDITIVE opponent-pressure screen.

Adapted from experiments/exploration/E0_I0005_turnover_interaction/build_data.py (unmodified
original; this is a copy with additions). New vs I0005:
  * game_date carried through, so a PREGAME (strictly-before-date, expanding) opponent pressure
    can be built alongside the season LOO one.
  * opponent points-allowed-per-100-def-poss carried through (LOO and pregame) as the
    opponent-quality confound control.
  * a team-game defensive table is emitted so the placebo (analyze.py) and the persistence
    check (rung 4) run off the same tallies.

HARD RULE (GRAPH_POLICY 13.2): exploration partition ONLY = seasons 2021-2024.
Filter applied immediately after each parquet load, before any other computation.
2025/2026 rows are touched only by the boolean mask -- never counted, described, or joined.

Artifact safety (13.2.2): neither input has a sibling <artifact>.manifest.json; both are
row-per-game/row-per-possession raw artifacts with an explicit `season` column, so row-level
filtering is sufficient.
"""
import numpy as np
import pandas as pd

from pressure_lib import PregamePressure, EXPLORATION_SEASONS, SHRINK_K

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program"
OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0009_additive_pressure"

RNG_SEED = 20260807

# ---------------------------------------------------------------------------
# 1. Player turnover targets -- partition filter FIRST
# ---------------------------------------------------------------------------
tov = pd.read_parquet(f"{ROOT}/turnover_targets_v1/player_turnover_targets_v1.parquet")
tov = tov[tov["season"].isin(EXPLORATION_SEASONS)].copy()
print("turnover targets rows after partition filter:", len(tov),
      "seasons present:", sorted(tov["season"].unique()))
tov = tov[tov["rate_defined"] == True].copy()
print("rows with rate_defined:", len(tov))

# ---------------------------------------------------------------------------
# 2. Possessions v2 -- season col is STRING in this parquet; cast then filter FIRST
# ---------------------------------------------------------------------------
poss = pd.read_parquet(
    f"{ROOT}/possessions_v2/possessions_raw_v2.parquet",
    columns=["game_id", "season", "offense_team_id", "defense_team_id",
             "end_reason", "points_scored", "game_date"])
poss["season"] = poss["season"].astype(int)
poss = poss[poss["season"].isin(EXPLORATION_SEASONS)].copy()
print("possessions rows after partition filter:", len(poss),
      "seasons present:", sorted(poss["season"].unique()))
assert set(poss["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"

# schedule: (game_id, team_id) -> opponent_team_id
sched = poss[["game_id", "offense_team_id", "defense_team_id"]].drop_duplicates()
sched = sched.rename(columns={"offense_team_id": "team_id", "defense_team_id": "opponent_team_id"})
sched = sched.drop_duplicates(subset=["game_id", "team_id"])
print("schedule rows (game,team):", len(sched))

# ---------------------------------------------------------------------------
# 3. Team-game DEFENSIVE tallies: possessions defended, turnovers forced, points allowed
# ---------------------------------------------------------------------------
poss["is_tov"] = (poss["end_reason"] == "turnover").astype(int)
team_game = (poss.groupby(["game_id", "defense_team_id", "season"], as_index=False)
                  .agg(def_poss=("is_tov", "size"),
                       def_tov=("is_tov", "sum"),
                       def_pts_allowed=("points_scored", "sum"),
                       game_date=("game_date", "min")))
team_game = team_game.rename(columns={"defense_team_id": "team_id"})
team_game["game_date"] = pd.to_datetime(team_game["game_date"])
print("team-game defensive tallies:", len(team_game))
assert set(team_game["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"

# --- 3a. LOO (whole-season-minus-this-game) pressure and points-allowed -- RUNG 1 measure
tot = (team_game.groupby(["team_id", "season"], as_index=False)
                 .agg(s_poss=("def_poss", "sum"), s_tov=("def_tov", "sum"),
                      s_pts=("def_pts_allowed", "sum"), s_games=("def_poss", "size")))
team_game = team_game.merge(tot, on=["team_id", "season"], how="left")
loo_poss = team_game["s_poss"] - team_game["def_poss"]
team_game["pressure_loo"] = np.where(loo_poss > 0,
                                     100.0 * (team_game["s_tov"] - team_game["def_tov"]) / loo_poss,
                                     np.nan)
team_game["defrtg_loo"] = np.where(loo_poss > 0,
                                   100.0 * (team_game["s_pts"] - team_game["def_pts_allowed"]) / loo_poss,
                                   np.nan)

# --- 3b. PREGAME (strictly before this game's date, expanding, shrunk) -- RUNG 2 measure
pp = PregamePressure(team_game[["team_id", "season", "game_date",
                                "def_poss", "def_tov", "def_pts_allowed"]])
pre_rate, pre_n = [], []
pre_dr = []
for t, s, d in zip(team_game["team_id"], team_game["season"], team_game["game_date"]):
    r, k = pp.lookup(t, s, d)
    dr, _ = pp.lookup_defrtg(t, s, d)
    pre_rate.append(r); pre_n.append(k); pre_dr.append(dr)
team_game["pressure_pregame"] = pre_rate
team_game["pregame_games"] = pre_n
team_game["defrtg_pregame"] = pre_dr

team_game.to_csv(f"{OUT}/team_game_defense.csv", index=False)
print("wrote team_game_defense.csv")
print("shrinkage pseudo-count K (def possessions):", SHRINK_K)
print("anchor rule: prior-season team rate when season-1 is inside 2021-2024, else that season's "
      "league mean (a scalar, non-discriminating across opponents). 2021 therefore always uses "
      "the league-mean anchor -- 2020 is outside the exploration partition and was never read.")

# ---------------------------------------------------------------------------
# 4. Player-season LOO tendency (identical construction to I0005)
# ---------------------------------------------------------------------------
sp = (tov.groupby(["player_id", "season"], as_index=False)
          .agg(season_tov=("turnovers", "sum"), season_poss=("realised_off_possessions", "sum")))
tov = tov.merge(sp, on=["player_id", "season"], how="left")
tov["loo_poss"] = tov["season_poss"] - tov["realised_off_possessions"]
tov["loo_tov"] = tov["season_tov"] - tov["turnovers"]
tov["player_tendency_loo"] = np.where(tov["loo_poss"] > 0,
                                      100.0 * tov["loo_tov"] / tov["loo_poss"], np.nan)

# ---------------------------------------------------------------------------
# 5. Attach opponent + both pressure flavours + both opponent-quality flavours
# ---------------------------------------------------------------------------
tov = tov.merge(sched, on=["game_id", "team_id"], how="left")
print("player-game rows missing an opponent match:", int(tov["opponent_team_id"].isna().sum()))

opp = team_game[["game_id", "team_id", "game_date", "pressure_loo", "pressure_pregame",
                 "pregame_games", "defrtg_loo", "defrtg_pregame"]].rename(columns={
    "team_id": "opponent_team_id",
    "pressure_loo": "opponent_pressure_loo",
    "pressure_pregame": "opponent_pressure_pregame",
    "pregame_games": "opponent_pregame_games",
    "defrtg_loo": "opponent_defrtg_loo",
    "defrtg_pregame": "opponent_defrtg_pregame"})
tov = tov.merge(opp, on=["game_id", "opponent_team_id"], how="left")

keep = ["game_id", "game_date", "team_id", "player_id", "season", "season_type", "minutes",
        "realised_off_possessions", "turnovers", "turnovers_per_100_off_poss",
        "player_tendency_loo", "opponent_team_id",
        "opponent_pressure_loo", "opponent_pressure_pregame", "opponent_pregame_games",
        "opponent_defrtg_loo", "opponent_defrtg_pregame"]
frame = tov[keep].copy()

before = len(frame)
frame = frame.dropna(subset=["player_tendency_loo", "opponent_pressure_loo",
                             "opponent_pressure_pregame", "opponent_defrtg_loo",
                             "opponent_defrtg_pregame"])
print(f"dropped {before - len(frame)} rows with undefined LOO/pregame predictors (thin support)")
print("final analysis frame rows:", len(frame))
print("season counts:", frame["season"].value_counts().sort_index().to_dict())
assert set(frame["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
assert frame["game_date"].dt.year.between(2021, 2024).all(), "PARTITION VIOLATION (game_date)"

frame.to_csv(f"{OUT}/player_game_analysis.csv", index=False)
print("wrote player_game_analysis.csv")

print("\n=== predictor summaries (2021-2024 only) ===")
print(frame[["turnovers_per_100_off_poss", "player_tendency_loo",
             "opponent_pressure_loo", "opponent_pressure_pregame",
             "opponent_defrtg_loo", "opponent_defrtg_pregame"]].describe().round(3))
print("\ncorr(LOO pressure, pregame pressure) =",
      round(float(frame["opponent_pressure_loo"].corr(frame["opponent_pressure_pregame"])), 4))
print("rows with 0 prior opponent games (pure anchor):",
      int((frame["opponent_pregame_games"] == 0).sum()))
