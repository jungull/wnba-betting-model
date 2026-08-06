#!/usr/bin/env python3
"""synthetic_fixture_a18.py -- a fully synthetic contract-schedule-shaped universe PLUS a
synthetic possession-level frame for A18 tests.

NOTHING here touches real data: synthetic seasons (3001..), synthetic game/team ids. Row/cluster
counts are deliberately far from the real 2,982/1,491 and 2,990/1,495 signatures, and fold ids
never collide with the frozen D006 list, so the shared runner's blinding gate admits the fixture
without any flag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (3001, 3002, 3003)
N_TEAMS = 6
MIN_POSS_PER_TEAM_GAME = 6
MAX_POSS_PER_TEAM_GAME = 14


def build_universe(n_games_per_team_per_season: int = 14, seed: int = 8181) -> pd.DataFrame:
    """One row per team-game (both sides of every game), ordered by (season, day)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 700_000
    day = 0
    teams = [f"SYN{k}" for k in range(N_TEAMS)]
    for s in SEASONS:
        for _ in range(n_games_per_team_per_season):
            order = list(teams)
            rng.shuffle(order)
            for i in range(0, len(order) - 1, 2):
                gid += 1
                day += 1
                home, away = order[i], order[i + 1]
                n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
                for team, opp in ((home, away), (away, home)):
                    proj = float(rng.uniform(70.0, 90.0))
                    rows.append({
                        "game_id": gid, "season": s, "day": day,
                        "game_date": s * 1000 + day,        # monotone synthetic date, integer
                        "team_id": team, "opp_team_id": opp,
                        INCUMBENT_PROJECTION_COL: proj,
                        OFFSET_COL: float(np.log(proj)),
                        TARGET_COL_REAL: float(rng.poisson(proj)),
                        "_game_minutes": 40.0 + 5.0 * n_ot,
                        "_overtime_periods": float(n_ot),
                        "_is_overtime": float(n_ot > 0),
                        "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                    })
    return pd.DataFrame(rows)


def build_possessions(universe: pd.DataFrame, seed: int = 9191,
                      own_mean_bias: dict | None = None) -> pd.DataFrame:
    """A synthetic possession-level frame: several possessions per (game_id, offense_team_id),
    carrying game_id/game_date/season/offense_team_id/duration_sec -- exactly the columns
    feature_construction.compute_z1 requires. `own_mean_bias`: optional {team_id: seconds} additive
    shift applied to that team's own possession durations (used to give a real, testable
    own-vs-opponent signal in synthetic data)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    games = universe[["game_id", "game_date", "season"]].drop_duplicates("game_id")
    rows = []
    for _, g in games.iterrows():
        # both sides of this game_id, from the universe frame
        sides = universe[universe["game_id"] == g["game_id"]]
        for _, side in sides.iterrows():
            team = side["team_id"]
            n_poss = int(rng.integers(MIN_POSS_PER_TEAM_GAME, MAX_POSS_PER_TEAM_GAME + 1))
            bias = float((own_mean_bias or {}).get(team, 0.0))
            durs = np.clip(rng.normal(14.0 + bias, 4.0, size=n_poss), 0.0, 24.0)
            for d in durs:
                rows.append({"game_id": int(g["game_id"]), "game_date": g["game_date"],
                            "season": int(g["season"]), "offense_team_id": team,
                            "duration_sec": float(d)})
    return pd.DataFrame(rows)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_a18_lt_{test_season}",
                      "train_idx": train, "test_idx": test})
    return folds


def build_prohibited_basis(df: pd.DataFrame):
    """Synthetic realised-duration basis, aligned row-for-row with the universe frame."""
    import guard_harness as gh
    frame = pd.DataFrame({
        "game_minutes": df["_game_minutes"].to_numpy(float),
        "overtime_periods": df["_overtime_periods"].to_numpy(float),
        "is_overtime": df["_is_overtime"].to_numpy(float),
        "team_minutes": df["_team_minutes"].to_numpy(float),
    }, index=df.index)
    return gh.make_prohibited_basis(
        frame, source={"artifact_id": "a18_synthetic_fixture/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A18 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
