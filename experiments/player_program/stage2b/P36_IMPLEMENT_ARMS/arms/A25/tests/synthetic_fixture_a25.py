#!/usr/bin/env python3
"""synthetic_fixture_a25.py -- a fully synthetic universe for A25_home_offense_contrast tests.

NOTHING here touches real data: synthetic seasons (5001..), synthetic game ids, synthetic
Poisson counts, synthetic home/away flags. Row/cluster counts are deliberately far from the real
2,982/1,491 and 2,990/1,495 signatures, and fold ids never collide with the frozen D006 list, so
the runner's blinding gate admits the fixture without any flag.

Every synthetic game contributes exactly TWO rows -- one home (is_home_offense=1), one away
(is_home_offense=0) -- reproducing the card's own structural guarantee ("exactly 50/50 balanced
within every fold by construction: games never split") on every fold, not merely on the whole
universe.

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A25/ only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (5001, 5002, 5003)
TRUE_BETA = 0.03          # real synthetic home-tempo shift, so the arm has signal to recover


def build_universe(n_games_per_season: int = 24, seed: int = 2525) -> pd.DataFrame:
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 250_000
    for s in SEASONS:
        for _ in range(n_games_per_season):
            gid += 1
            n_ot = int(rng.choice([0, 0, 0, 0, 1]))
            # side 1 == home offense, side 0 == away offense; both rows share the same game_id
            # (game cluster), reproducing "games never split across folds or draws"
            rows.append(_row(rng, gid, s, is_home=1, n_ot=n_ot))
            rows.append(_row(rng, gid, s, is_home=0, n_ot=n_ot))
    return pd.DataFrame(rows)


def _row(rng, gid, season, is_home, n_ot):
    proj = float(rng.uniform(70.0, 90.0))
    mu = proj * np.exp(TRUE_BETA * is_home)
    return {
        "game_id": gid, "season": season,
        "is_home_offense": int(is_home),
        INCUMBENT_PROJECTION_COL: proj,
        OFFSET_COL: float(np.log(proj)),
        TARGET_COL_REAL: float(rng.poisson(mu)),
        "_game_minutes": 40.0 + 5.0 * n_ot,
        "_overtime_periods": float(n_ot),
        "_is_overtime": float(n_ot > 0),
        "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
    }


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids. Games are never split: every
    fold's train/test partition is drawn by SEASON, so both rows of every game_id fall on the
    same side of the split, and every fold's TEST partition carries exactly as many home rows as
    away rows (one of each per game)."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_a25_lt_{test_season}",
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
        frame, source={"artifact_id": "synthetic_fixture_a25/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A25 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
