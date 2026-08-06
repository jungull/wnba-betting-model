#!/usr/bin/env python3
"""synthetic_fixture.py -- a fully synthetic contract-schedule-shaped universe for A10 tests.

NOTHING here touches real data: synthetic seasons (4001..), synthetic game/team ids. Row/cluster
counts are deliberately far from the real 2,982/1,491 and 2,990/1,495 signatures, and fold ids
never collide with the frozen D006 list, so the shared runner's blinding gate admits the fixture
without any flag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (4001, 4002, 4003)
N_TEAMS = 6


def _lagged_pace(n_off_poss, max_period):
    denom = 40.0 + 5.0 * np.maximum(0.0, np.asarray(max_period, float) - 4.0)
    return np.asarray(n_off_poss, float) * 40.0 / denom


def build_universe(n_games_per_team_per_season: int = 14, seed: int = 8484) -> pd.DataFrame:
    """One row per team-game (both sides of every game), ordered by (season, day)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 700_000
    day = 0
    teams = [f"REC{k}" for k in range(N_TEAMS)]
    for s in SEASONS:
        for _ in range(n_games_per_team_per_season):
            order = list(teams)
            rng.shuffle(order)
            for i in range(0, len(order) - 1, 2):
                gid += 1
                day += 1
                home, away = order[i], order[i + 1]
                n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
                max_period = 4 + n_ot
                for team, opp in ((home, away), (away, home)):
                    proj = float(rng.uniform(70.0, 90.0))
                    n_off_poss = float(rng.uniform(70.0, 95.0) * (1.0 + 0.05 * n_ot))
                    rows.append({
                        "game_id": gid, "season": s, "day": day,
                        "game_date": s * 1000 + day,        # monotone synthetic date, integer
                        "team_id": team, "opp_id": opp,
                        INCUMBENT_PROJECTION_COL: proj,
                        OFFSET_COL: float(np.log(proj)),
                        "n_off_poss": n_off_poss, "max_period": float(max_period),
                        "_game_minutes": 40.0 + 5.0 * n_ot,
                        "_overtime_periods": float(n_ot),
                        "_is_overtime": float(n_ot > 0),
                        "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                    })
    df = pd.DataFrame(rows)
    df[TARGET_COL_REAL] = _lagged_pace(df["n_off_poss"], df["max_period"])
    return df


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_a10_lt_{test_season}",
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
        frame, source={"artifact_id": "a10_synthetic_fixture/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A10 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
