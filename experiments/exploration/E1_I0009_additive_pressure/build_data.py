"""
E1 I0009 (family F_TURNOVER_PRESSURE) -- build the E1 frame.

E1 question: does the E0 additive opponent-pressure effect PERSIST out-of-sample inside the
exploration partition, AFTER controlling home/away?

Adds over the E0 build:
  * player_is_home / opponent_def_is_home  (VENUE -- the uncontrolled confound E0 flagged)
  * venue-split pregame opponent pressure (opponent's forced-TO rate on this side of the venue)
  * a FULLY pregame-observable player tendency baseline, so the incremental number is not
    silently stated against E0's hindsight LOO baseline
  * team-game venue tallies for the variance decomposition

HARD RULE (GRAPH_POLICY 13.2): exploration partition ONLY = seasons 2021-2024.
Filter applied immediately after each parquet load, before any other computation.
2025/2026 rows are touched only by the boolean mask -- never counted, described, or joined.

Artifact safety (13.2.2): both inputs are checked for a sibling <artifact>.manifest.json.
Neither has one; both are row-per-game / row-per-possession raw artifacts with an explicit
`season` column and no fitted cross-season parameter, so row-level filtering is sufficient.
Partition verification is done on COLUMN VALUES of season/date columns -- NOT on raw file
bytes (a byte scan produced a false violation for a previous coordinator).
"""
import json
import os

import numpy as np
import pandas as pd

from pressure_lib_e1 import (EXPLORATION_SEASONS, PregamePlayerTendency,
                             PregameTeamPressure, SHRINK_K_PLAYER, SHRINK_K_TEAM, _ns)

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\player_program"
OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E1_I0009_additive_pressure"

TOV_PARQUET = f"{ROOT}/turnover_targets_v1/player_turnover_targets_v1.parquet"
POSS_PARQUET = f"{ROOT}/possessions_v2/possessions_raw_v2.parquet"

# ---------------------------------------------------------------------------
# 0. Artifact contamination check (13.2.2)
# ---------------------------------------------------------------------------
for p in (TOV_PARQUET, POSS_PARQUET):
    man = p + ".manifest.json"
    if os.path.exists(man):
        with open(man) as fh:
            m = json.load(fh)
        gran = m.get("asof_granularity")
        print(f"manifest for {os.path.basename(p)}: asof_granularity={gran!r}")
        assert gran == "row", (
            f"UNUSABLE AT E1: {p} has asof_granularity={gran!r}; filtering does not bound it.")
    else:
        print(f"no sibling manifest for {os.path.basename(p)} "
              f"(raw row-per-game/possession artifact with explicit season column)")

# ---------------------------------------------------------------------------
# 1. Player turnover targets -- partition filter FIRST
# ---------------------------------------------------------------------------
tov = pd.read_parquet(TOV_PARQUET)
tov = tov[tov["season"].isin(EXPLORATION_SEASONS)].copy()
print("turnover targets rows after partition filter:", len(tov),
      "seasons present:", sorted(tov["season"].unique()))
tov = tov[tov["rate_defined"] == True].copy()
print("rows with rate_defined:", len(tov))

# ---------------------------------------------------------------------------
# 2. Possessions v2 -- season col is STRING here; cast then filter FIRST
# ---------------------------------------------------------------------------
poss = pd.read_parquet(POSS_PARQUET,
                       columns=["game_id", "season", "offense_team_id", "defense_team_id",
                                "end_reason", "points_scored", "game_date", "is_home_offense"])
poss["season"] = poss["season"].astype(int)
poss = poss[poss["season"].isin(EXPLORATION_SEASONS)].copy()
print("possessions rows after partition filter:", len(poss),
      "seasons present:", sorted(poss["season"].unique()))
assert set(poss["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
poss["game_date"] = pd.to_datetime(poss["game_date"])
assert poss["game_date"].dt.year.between(2021, 2024).all(), "PARTITION VIOLATION (poss game_date)"

# schedule: (game_id, team_id) -> opponent_team_id
sched = poss[["game_id", "offense_team_id", "defense_team_id"]].drop_duplicates()
sched = sched.rename(columns={"offense_team_id": "team_id", "defense_team_id": "opponent_team_id"})
sched = sched.drop_duplicates(subset=["game_id", "team_id"])
print("schedule rows (game,team):", len(sched))

# ---------------------------------------------------------------------------
# 3. Team-game DEFENSIVE tallies, now carrying VENUE
# ---------------------------------------------------------------------------
poss["is_tov"] = (poss["end_reason"] == "turnover").astype(int)
# defence is at home iff the offence is NOT at home
poss["def_is_home"] = 1 - poss["is_home_offense"].astype(int)

team_game = (poss.groupby(["game_id", "defense_team_id", "season"], as_index=False)
                 .agg(def_poss=("is_tov", "size"),
                      def_tov=("is_tov", "sum"),
                      def_pts_allowed=("points_scored", "sum"),
                      game_date=("game_date", "min"),
                      def_is_home_mean=("def_is_home", "mean")))
team_game = team_game.rename(columns={"defense_team_id": "team_id"})
team_game["game_date"] = pd.to_datetime(team_game["game_date"])

# venue must be constant within a team-game
bad = team_game[~team_game["def_is_home_mean"].isin([0.0, 1.0])]
print("team-games with non-constant venue flag:", len(bad))
assert len(bad) == 0, "venue flag is not constant within a team-game"
team_game["def_is_home"] = team_game["def_is_home_mean"].astype(int)
team_game = team_game.drop(columns=["def_is_home_mean"])
print("team-game defensive tallies:", len(team_game),
      "| home-defence share:", round(float(team_game["def_is_home"].mean()), 4))
assert set(team_game["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
assert team_game["game_date"].dt.year.between(2021, 2024).all(), "PARTITION VIOLATION (team_game)"

team_game["def_tov_rate"] = 100.0 * team_game["def_tov"] / team_game["def_poss"]
team_game["def_pts_rate"] = 100.0 * team_game["def_pts_allowed"] / team_game["def_poss"]

# --- 3a. LOO (whole-season-minus-this-game) -- the E0 rung-1 measure, kept for comparability
tot = (team_game.groupby(["team_id", "season"], as_index=False)
                .agg(s_poss=("def_poss", "sum"), s_tov=("def_tov", "sum"),
                     s_pts=("def_pts_allowed", "sum")))
team_game = team_game.merge(tot, on=["team_id", "season"], how="left")
loo_poss = team_game["s_poss"] - team_game["def_poss"]
team_game["pressure_loo"] = np.where(loo_poss > 0,
                                     100.0 * (team_game["s_tov"] - team_game["def_tov"]) / loo_poss,
                                     np.nan)
team_game["defrtg_loo"] = np.where(loo_poss > 0,
                                   100.0 * (team_game["s_pts"] - team_game["def_pts_allowed"]) / loo_poss,
                                   np.nan)

# --- 3b. PREGAME measures (strictly before this game's date, expanding, shrunk)
tg_in = team_game[["team_id", "season", "game_date", "def_is_home",
                   "def_poss", "def_tov", "def_pts_allowed"]]
pp = PregameTeamPressure(tg_in, num_col="def_tov", den_col="def_poss")
pd_rtg = PregameTeamPressure(tg_in, num_col="def_pts_allowed", den_col="def_poss")

tg_ns = _ns(team_game["game_date"])
rows = []
for t, s, d, h in zip(team_game["team_id"], team_game["season"], tg_ns, team_game["def_is_home"]):
    r, k = pp.lookup(t, s, d)
    rv, kv = pp.lookup_venue(t, s, d, h)
    dr, _ = pd_rtg.lookup(t, s, d)
    rows.append((r, k, rv, kv, dr))
team_game[["pressure_pregame", "pregame_games",
           "pressure_pregame_venue", "pregame_venue_games",
           "defrtg_pregame"]] = pd.DataFrame(rows, index=team_game.index)

team_game.to_csv(f"{OUT}/team_game_defense.csv", index=False)
print("wrote team_game_defense.csv")
print("shrinkage: K_team =", SHRINK_K_TEAM, " K_player =", SHRINK_K_PLAYER)

# ---------------------------------------------------------------------------
# 4. Player tendency -- BOTH the E0 LOO baseline and a fully pregame-observable one
# ---------------------------------------------------------------------------
# attach game_date + venue to the player-game rows (player's own team's venue)
gm = team_game[["game_id", "team_id", "game_date", "def_is_home"]].rename(
    columns={"team_id": "opponent_team_id", "def_is_home": "opp_def_is_home"})
tov = tov.merge(sched, on=["game_id", "team_id"], how="left")
print("player-game rows missing an opponent match:", int(tov["opponent_team_id"].isna().sum()))
tov = tov.merge(gm, on=["game_id", "opponent_team_id"], how="left")
tov["game_date"] = pd.to_datetime(tov["game_date"])
# the player's team is at home iff the OPPONENT (defending) is not
tov["player_is_home"] = 1 - tov["opp_def_is_home"].astype("Int64")
assert tov["game_date"].dt.year.between(2021, 2024).all(), "PARTITION VIOLATION (tov game_date)"

# 4a. E0-comparable LOO tendency (hindsight; NOT pregame-observable)
sp = (tov.groupby(["player_id", "season"], as_index=False)
         .agg(season_tov=("turnovers", "sum"), season_poss=("realised_off_possessions", "sum")))
tov = tov.merge(sp, on=["player_id", "season"], how="left")
tov["loo_poss"] = tov["season_poss"] - tov["realised_off_possessions"]
tov["loo_tov"] = tov["season_tov"] - tov["turnovers"]
tov["player_tendency_loo"] = np.where(tov["loo_poss"] > 0,
                                      100.0 * tov["loo_tov"] / tov["loo_poss"], np.nan)

# 4b. fully pregame-observable tendency (expanding, strictly before date, shrunk)
ppt = PregamePlayerTendency(tov[["player_id", "season", "game_date",
                                 "turnovers", "realised_off_possessions"]])
tov_ns = _ns(tov["game_date"])
pt = [ppt.lookup(p, s, d) for p, s, d in zip(tov["player_id"], tov["season"], tov_ns)]
tov["player_tendency_pregame"] = [x[0] for x in pt]
tov["player_pregame_games"] = [x[1] for x in pt]

# ---------------------------------------------------------------------------
# 5. Attach opponent pressure flavours
# ---------------------------------------------------------------------------
opp = team_game[["game_id", "team_id", "pressure_loo", "pressure_pregame", "pregame_games",
                 "pressure_pregame_venue", "defrtg_loo", "defrtg_pregame",
                 "def_tov_rate"]].rename(columns={
    "team_id": "opponent_team_id",
    "pressure_loo": "opponent_pressure_loo",
    "pressure_pregame": "opponent_pressure_pregame",
    "pregame_games": "opponent_pregame_games",
    "pressure_pregame_venue": "opponent_pressure_pregame_venue",
    "defrtg_loo": "opponent_defrtg_loo",
    "defrtg_pregame": "opponent_defrtg_pregame",
    "def_tov_rate": "opponent_realised_tov_rate"})
tov = tov.merge(opp, on=["game_id", "opponent_team_id"], how="left")

keep = ["game_id", "game_date", "team_id", "player_id", "season", "season_type", "minutes",
        "realised_off_possessions", "turnovers", "turnovers_per_100_off_poss",
        "player_is_home", "player_tendency_loo", "player_tendency_pregame", "player_pregame_games",
        "opponent_team_id", "opponent_pressure_loo", "opponent_pressure_pregame",
        "opponent_pressure_pregame_venue", "opponent_pregame_games",
        "opponent_defrtg_loo", "opponent_defrtg_pregame", "opponent_realised_tov_rate"]
frame = tov[keep].copy()

before = len(frame)
frame = frame.dropna(subset=["player_tendency_loo", "player_tendency_pregame",
                             "player_is_home",
                             "opponent_pressure_loo", "opponent_pressure_pregame",
                             "opponent_pressure_pregame_venue",
                             "opponent_defrtg_loo", "opponent_defrtg_pregame"])
frame["player_is_home"] = frame["player_is_home"].astype(int)
print(f"dropped {before - len(frame)} rows with undefined predictors (thin support)")
print("final analysis frame rows:", len(frame))
print("season counts:", frame["season"].value_counts().sort_index().to_dict())
print("home share of player-games:", round(float(frame["player_is_home"].mean()), 4))

# ---------------------------------------------------------------------------
# 6. PARTITION VERIFICATION -- on COLUMN VALUES, not raw bytes
# ---------------------------------------------------------------------------
assert set(frame["season"].unique()).issubset(set(EXPLORATION_SEASONS)), "PARTITION VIOLATION"
assert frame["game_date"].dt.year.between(2021, 2024).all(), "PARTITION VIOLATION (game_date)"
assert "observed_time" not in frame.columns, "observed_time must never be written"
assert "observed_time" not in team_game.columns, "observed_time must never be written"
print("PARTITION VERIFIED on season/date COLUMN VALUES:",
      sorted(frame["season"].unique()), sorted(frame["game_date"].dt.year.unique()))

frame.to_csv(f"{OUT}/player_game_analysis.csv", index=False)
print("wrote player_game_analysis.csv")

print("\n=== predictor summaries (2021-2024 only) ===")
cols = ["turnovers_per_100_off_poss", "player_is_home", "player_tendency_loo",
        "player_tendency_pregame", "opponent_pressure_loo", "opponent_pressure_pregame",
        "opponent_pressure_pregame_venue", "opponent_defrtg_pregame"]
print(frame[cols].describe().round(3).to_string())
print("\ncorr(LOO pressure, pregame pressure)   =",
      round(float(frame["opponent_pressure_loo"].corr(frame["opponent_pressure_pregame"])), 4))
print("corr(pregame pressure, venue-split)    =",
      round(float(frame["opponent_pressure_pregame"].corr(frame["opponent_pressure_pregame_venue"])), 4))
print("corr(LOO tendency, pregame tendency)   =",
      round(float(frame["player_tendency_loo"].corr(frame["player_tendency_pregame"])), 4))
print("rows with 0 prior opponent games (pure anchor):",
      int((frame["opponent_pregame_games"] == 0).sum()))
