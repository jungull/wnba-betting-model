#!/usr/bin/env python3
"""synthetic_fixture_a05.py -- a fully synthetic universe for A05_cal_playoff_intercept tests.

NOTHING here touches real data: synthetic seasons (5001..), synthetic game ids, synthetic
Poisson counts, synthetic playoff flags. Row/cluster counts are deliberately far from the real
2,982/1,491 and 2,990/1,495 signatures, and fold ids never collide with the frozen D006 list, so
the runner's blinding gate admits the fixture without any flag.

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A05/ only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (5001, 5002, 5003)
TRUE_PI = 0.08          # real synthetic playoff level shift, so the arm has signal to recover


def build_universe(n_reg_games_per_season: int = 20, n_playoff_games_per_season: int = 6,
                   seed: int = 505) -> pd.DataFrame:
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 500_000
    for s in SEASONS:
        # regular-season games: is_playoff_game = 0
        for _ in range(n_reg_games_per_season):
            gid += 1
            n_ot = int(rng.choice([0, 0, 0, 0, 1]))
            for side in (0, 1):
                rows.append(_row(rng, gid, s, side, n_ot, is_playoff=0))
        # playoff games: is_playoff_game = 1 (skipped for the LAST season, so one fold's TEST
        # partition has zero playoff rows -- exercises the card's fold_local_fallback note)
        n_po = 0 if s == SEASONS[-1] else n_playoff_games_per_season
        for _ in range(n_po):
            gid += 1
            n_ot = int(rng.choice([0, 0, 0, 1]))
            for side in (0, 1):
                rows.append(_row(rng, gid, s, side, n_ot, is_playoff=1))
    return pd.DataFrame(rows)


def _row(rng, gid, season, side, n_ot, is_playoff):
    proj = float(rng.uniform(70.0, 90.0))
    mu = proj * np.exp(TRUE_PI * is_playoff)
    return {
        "game_id": gid, "season": season, "side": side,
        "is_playoff_game": int(is_playoff),
        INCUMBENT_PROJECTION_COL: proj,
        OFFSET_COL: float(np.log(proj)),
        TARGET_COL_REAL: float(rng.poisson(mu)),
        "_game_minutes": 40.0 + 5.0 * n_ot,
        "_overtime_periods": float(n_ot),
        "_is_overtime": float(n_ot > 0),
        "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
    }


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids. The final fold's TEST season
    (SEASONS[-1]) has zero playoff rows by construction -- see build_universe."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_a05_lt_{test_season}",
                      "train_idx": train, "test_idx": test})
    return folds


def build_prohibited_basis(df: pd.DataFrame):
    """Synthetic realised-duration basis, aligned row-for-row with the universe frame. At P38
    time the caller builds this with postgame_surrogate_guard.realised_duration_basis from the
    frozen possessions artifact; the synthetic basis has the same four parameterisations of the
    one prohibited quantity."""
    import guard_harness as gh
    frame = pd.DataFrame({
        "game_minutes": df["_game_minutes"].to_numpy(float),
        "overtime_periods": df["_overtime_periods"].to_numpy(float),
        "is_overtime": df["_is_overtime"].to_numpy(float),
        "team_minutes": df["_team_minutes"].to_numpy(float),
    }, index=df.index)
    return gh.make_prohibited_basis(
        frame, source={"artifact_id": "synthetic_fixture_a05/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A05 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
