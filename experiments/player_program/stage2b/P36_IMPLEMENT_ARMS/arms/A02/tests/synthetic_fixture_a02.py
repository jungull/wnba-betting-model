#!/usr/bin/env python3
"""synthetic_fixture_a02.py -- a fully synthetic toy universe exercising arm_a02.ArmA02.

NOTHING here touches real data: synthetic seasons (3001..), synthetic game ids, synthetic
Poisson counts. Row/cluster counts are deliberately far from the real 2,982/1,491 and 2,990/
1,495 signatures, and fold ids never collide with the frozen D006 list, so the blinding gate
admits the fixture without any flag. Modeled on runner/tests/synthetic_fixture.py but adds the
A02-specific own_pace_estimate / game-pairing structure the contrast needs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_RUNNER = Path(__file__).resolve().parents[2] / "runner"
if str(_RUNNER) not in sys.path:
    sys.path.insert(0, str(_RUNNER))

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL  # noqa: E402

SEASONS = (3001, 3002, 3003)
TRUE_GAMMA = 0.04            # real synthetic effect on the log scale, so a fit has signal to find


def build_universe(n_games_per_season: int = 30, seed: int = 4202) -> pd.DataFrame:
    """Two team-rows per game_id, own_pace_estimate carried on each row, contrast recoverable
    as own - opp within the game_id group (exactly two rows per group).
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 80_000
    for s in SEASONS:
        for _ in range(n_games_per_season):
            gid += 1
            n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
            proj_a = float(rng.uniform(72.0, 88.0))
            proj_b = float(rng.uniform(72.0, 88.0))
            own_a = proj_a + float(rng.normal(scale=2.0))
            own_b = proj_b + float(rng.normal(scale=2.0))
            # own_est/opp_est are already-resolved upstream values (P25 PREREGISTERED_
            # CONTRASTS.json input_definitions); this fixture supplies both directly, exactly
            # as a real team_possession_prior_v1-derived frame would.
            for team_id, proj, own_est, opp_est in (
                (0, proj_a, own_a, own_b), (1, proj_b, own_b, own_a)):
                contrast = own_est - opp_est
                mu = proj * np.exp(TRUE_GAMMA * contrast)
                rows.append({
                    "game_id": gid, "season": s, "team_id": team_id,
                    INCUMBENT_PROJECTION_COL: proj,
                    OFFSET_COL: float(np.log(proj)),
                    "own_est": own_est, "opp_est": opp_est,
                    TARGET_COL_REAL: float(rng.poisson(mu)),
                    "_game_minutes": 40.0 + 5.0 * n_ot,
                    "_overtime_periods": float(n_ot),
                    "_is_overtime": float(n_ot > 0),
                    "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                })
    return pd.DataFrame(rows)


def build_degenerate_fold_universe(n_games: int = 20, seed: int = 909) -> pd.DataFrame:
    """A universe where own_pace_estimate is IDENTICAL for both teams in every game (contrast
    is exactly zero everywhere): exercises the card's registered fold-local fallback
    (sd(contrast) == 0 on training rows).
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 70_000
    for _ in range(n_games):
        gid += 1
        proj = float(rng.uniform(72.0, 88.0))
        own = proj + float(rng.normal(scale=2.0))
        for team_id in (0, 1):
            rows.append({
                "game_id": gid, "season": 3001, "team_id": team_id,
                INCUMBENT_PROJECTION_COL: proj,
                OFFSET_COL: float(np.log(proj)),
                "own_est": own, "opp_est": own,          # identical both sides -> contrast == 0
                TARGET_COL_REAL: float(rng.poisson(proj)),
                "_game_minutes": 40.0, "_overtime_periods": 0.0,
                "_is_overtime": 0.0, "_team_minutes": 200.0,
            })
    return pd.DataFrame(rows)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids (never real D006 ids)."""
    folds = []
    seasons = sorted(df["season"].unique())
    for i in range(1, len(seasons)):
        test_season = seasons[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"a02_syn_lt_{test_season}",
                      "train_idx": train, "test_idx": test})
    return folds


def build_prohibited_basis(df: pd.DataFrame):
    """Synthetic realised-duration basis, aligned row-for-row with the universe frame. At P38
    time the caller builds this with postgame_surrogate_guard.realised_duration_basis against
    the frozen possessions artifact; this constructor exists for the synthetic path only.
    """
    import guard_harness as gh
    frame = pd.DataFrame({
        "game_minutes": df["_game_minutes"].to_numpy(float),
        "overtime_periods": df["_overtime_periods"].to_numpy(float),
        "is_overtime": df["_is_overtime"].to_numpy(float),
        "team_minutes": df["_team_minutes"].to_numpy(float),
    }, index=df.index)
    return gh.make_prohibited_basis(
        frame, source={"artifact_id": "synthetic_fixture_a02/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A02 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
