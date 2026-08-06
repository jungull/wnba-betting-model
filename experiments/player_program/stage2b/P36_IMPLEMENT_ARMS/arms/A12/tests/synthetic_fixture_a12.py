#!/usr/bin/env python3
"""synthetic_fixture_a12.py -- a fully synthetic multi-season universe/history for A12's own
arm-module tests. Mirrors runner/tests/synthetic_fixture.py and arms/A03's fixture conventions:
synthetic seasons 4001.., synthetic game/team ids, far from the real 2,982/1,491 and 2,990/1,495
row/cluster signatures, no fold_id colliding with the frozen D006 list -- the blinding gate admits
these fixtures without any P38_UNSEALED flag.

NOTHING here touches real data. No real fold, no real MAE, no comparative historical performance.

One frame serves BOTH roles A12CarryoverAdditiveDecay needs: `history` (team_id/season/game_date
+ a realised `pace` column, for n_i and dev_prev) and `universe` (the same rows, carrying the
receipted gap/depth/opp_depth columns plus the offset/target/incumbent-projection columns the
shared runner requires) -- this mirrors A08's own synthetic convention (`history` is a superset of
the rows `build_design` will be handed) taken to its simplest case: superset == same set.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (4001, 4002, 4003, 4004, 4005)
TEAMS = tuple(f"T{i:02d}" for i in range(14))
PACE_COL = "pace"
TRUE_QUALITY_SCALE = 0.35   # mild true dependence of the target on team quality, for realism only


def build_universe(n_games_per_season: int = 70, seed: int = 121212) -> pd.DataFrame:
    """Two team-rows per game, teams recur across seasons (so dev_prev is non-trivially defined
    from season 4002 onward), gap/depth/opp_depth well-populated on both sides of everywhere."""
    rng = np.random.default_rng(seed)
    team_quality = {t: float(rng.normal(0.0, 3.0)) for t in TEAMS}
    rows = []
    gid = 900_000
    for si, s in enumerate(SEASONS):
        for g in range(n_games_per_season):
            gid += 1
            date = pd.Timestamp("2000-01-01") + pd.Timedelta(days=si * 250 + g)
            t1, t2 = rng.choice(np.array(TEAMS), size=2, replace=False)
            n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
            game_minutes = 40.0 + 5.0 * n_ot
            for team, opp in ((t1, t2), (t2, t1)):
                proj = float(rng.uniform(70.0, 90.0))
                pace_true = max(1.0, proj + team_quality[team] + float(rng.normal(0.0, 1.5)))
                mu = proj * np.exp(TRUE_QUALITY_SCALE * team_quality[team] / 20.0)
                rows.append({
                    "team_id": team, "opp_team_id": opp, "season": s, "game_date": date,
                    "game_id": f"G{gid}",
                    "pace_gap": float(rng.normal(0.0, 2.0)),
                    "pace_evidence_depth": float(rng.integers(0, 11)),
                    "opp_pace_evidence_depth": float(rng.integers(0, 11)),
                    OFFSET_COL: float(np.log(proj)),
                    INCUMBENT_PROJECTION_COL: proj,
                    TARGET_COL_REAL: float(rng.poisson(max(mu, 1.0))),
                    PACE_COL: pace_true,
                    "_game_minutes": game_minutes, "_overtime_periods": float(n_ot),
                    "_is_overtime": float(n_ot > 0), "_team_minutes": 5.0 * game_minutes,
                })
    return pd.DataFrame(rows)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Chronological expanding folds with synthetic fold ids (never colliding with D006)."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"a12_syn_lt_{test_season}",
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
        frame, source={"artifact_id": "synthetic_fixture_a12/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A12 tests"},
        note="synthetic: no overtime, game_minutes == 40 for every synthetic game")
