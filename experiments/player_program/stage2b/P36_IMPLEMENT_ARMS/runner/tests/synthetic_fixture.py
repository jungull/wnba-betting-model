#!/usr/bin/env python3
"""synthetic_fixture.py -- a fully synthetic toy universe for the P36 runner tests.

NOTHING here touches real data: synthetic seasons (3001..), synthetic game ids, synthetic
Poisson counts. Row/cluster counts are deliberately far from the real 2,982/1,491 and 2,990/
1,495 signatures, and fold ids never collide with the frozen D006 list, so the blinding gate
admits the fixture without any flag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (3001, 3002, 3003)
TRUE_BETA_X = 0.05          # real synthetic effect, so the toy arm has signal to find


def build_universe(n_games_per_season: int = 24, seed: int = 777) -> pd.DataFrame:
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 90_000
    for s in SEASONS:
        for _ in range(n_games_per_season):
            gid += 1
            n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
            for side in (0, 1):
                proj = float(rng.uniform(70.0, 90.0))
                x = float(rng.normal())
                z = int(rng.integers(0, 2))
                mu = proj * np.exp(TRUE_BETA_X * x)
                rows.append({
                    "game_id": gid, "season": s, "side": side,
                    INCUMBENT_PROJECTION_COL: proj,
                    OFFSET_COL: float(np.log(proj)),
                    "x_toy": x, "z_ind": z,
                    TARGET_COL_REAL: float(rng.poisson(mu)),
                    "_game_minutes": 40.0 + 5.0 * n_ot,
                    "_overtime_periods": float(n_ot),
                    "_is_overtime": float(n_ot > 0),
                    "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                })
    return pd.DataFrame(rows)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_lt_{test_season}",
                      "train_idx": train, "test_idx": test})
    return folds


def build_prohibited_basis(df: pd.DataFrame):
    """Synthetic realised-duration basis, aligned row-for-row with the universe frame.

    At P38 time the caller builds this with postgame_surrogate_guard.realised_duration_basis
    from the frozen possessions artifact; the synthetic basis has the same four
    parameterisations of the one prohibited quantity.
    """
    import guard_harness as gh
    frame = pd.DataFrame({
        "game_minutes": df["_game_minutes"].to_numpy(float),
        "overtime_periods": df["_overtime_periods"].to_numpy(float),
        "is_overtime": df["_is_overtime"].to_numpy(float),
        "team_minutes": df["_team_minutes"].to_numpy(float),
    }, index=df.index)
    return gh.make_prohibited_basis(
        frame, source={"artifact_id": "synthetic_fixture/1", "path": None,
                       "note": "synthetic prohibited basis for blinded P36 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
