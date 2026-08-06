#!/usr/bin/env python3
"""synthetic_fixture_a03.py -- a fully synthetic universe carrying `pace_evidence_depth`, for
A03's own arm-module tests. Mirrors runner/tests/synthetic_fixture.py's conventions (synthetic
seasons 4001.., synthetic game ids, far from the real 2,982/1,491 and 2,990/1,495 signatures, no
fold id collides with the frozen D006 list) so the blinding gate admits it without any flag.

NOTHING here touches real data. No real fold, no real MAE, no comparative historical performance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (4001, 4002, 4003, 4004)
TRUE_ALPHA_S = 0.06        # real synthetic shallow-tier level bump, so the arm has signal to find


def build_universe(n_games_per_season: int = 40, seed: int = 4242) -> pd.DataFrame:
    """Two team-rows per game, `pace_evidence_depth` in {0..10} with mass on both sides of the
    t=3 threshold so every season contributes >=10 clusters to BOTH the SHALLOW and DEEP tiers.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 500_000
    for s in SEASONS:
        for _ in range(n_games_per_season):
            gid += 1
            n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
            for side in (0, 1):
                proj = float(rng.uniform(70.0, 90.0))
                # depth: mixture so both SHALLOW (<=3) and DEEP (>3) tiers are well populated
                if rng.random() < 0.35:
                    depth = float(rng.integers(0, 4))          # 0..3 -> SHALLOW
                else:
                    depth = float(rng.integers(4, 11))         # 4..10 -> DEEP
                shallow = 1.0 if depth <= 3 else 0.0
                mu = proj * np.exp(TRUE_ALPHA_S * shallow)
                rows.append({
                    "game_id": gid, "season": s, "side": side,
                    INCUMBENT_PROJECTION_COL: proj,
                    OFFSET_COL: float(np.log(proj)),
                    "pace_evidence_depth": depth,
                    TARGET_COL_REAL: float(rng.poisson(mu)),
                    "_game_minutes": 40.0 + 5.0 * n_ot,
                    "_overtime_periods": float(n_ot),
                    "_is_overtime": float(n_ot > 0),
                    "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                })
    return pd.DataFrame(rows)


def build_universe_deep_starved(n_games_per_season: int = 12, seed: int = 99) -> pd.DataFrame:
    """A universe where nearly every row is SHALLOW, so the DEEP tier starves below the
    10-cluster floor in at least one fold -- exercises `tier_symmetry_check`'s UNEVALUABLE path,
    the half of the S7 rule the generic P27 mechanism cannot see (module docstring).
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 700_000
    for s in SEASONS:
        for _ in range(n_games_per_season):
            gid += 1
            n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
            for side in (0, 1):
                proj = float(rng.uniform(70.0, 90.0))
                depth = float(rng.integers(0, 4)) if rng.random() < 0.97 else float(
                    rng.integers(4, 11))
                shallow = 1.0 if depth <= 3 else 0.0
                mu = proj * np.exp(TRUE_ALPHA_S * shallow)
                rows.append({
                    "game_id": gid, "season": s, "side": side,
                    INCUMBENT_PROJECTION_COL: proj,
                    OFFSET_COL: float(np.log(proj)),
                    "pace_evidence_depth": depth,
                    TARGET_COL_REAL: float(rng.poisson(mu)),
                    "_game_minutes": 40.0 + 5.0 * n_ot,
                    "_overtime_periods": float(n_ot),
                    "_is_overtime": float(n_ot > 0),
                    "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                })
    return pd.DataFrame(rows)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Chronological expanding folds with synthetic fold ids (never colliding with D006)."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"a03_syn_lt_{test_season}",
                      "train_idx": train, "test_idx": test})
    return folds


def build_prohibited_basis(df: pd.DataFrame):
    """Synthetic realised-duration basis, aligned row-for-row with the universe frame. At P38
    time the caller uses postgame_surrogate_guard.realised_duration_basis against the frozen
    possessions artifact instead."""
    import guard_harness as gh
    frame = pd.DataFrame({
        "game_minutes": df["_game_minutes"].to_numpy(float),
        "overtime_periods": df["_overtime_periods"].to_numpy(float),
        "is_overtime": df["_is_overtime"].to_numpy(float),
        "team_minutes": df["_team_minutes"].to_numpy(float),
    }, index=df.index)
    return gh.make_prohibited_basis(
        frame, source={"artifact_id": "synthetic_fixture_a03/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A03 tests"},
        note="synthetic: no overtime, game_minutes == 40 for every synthetic game")
