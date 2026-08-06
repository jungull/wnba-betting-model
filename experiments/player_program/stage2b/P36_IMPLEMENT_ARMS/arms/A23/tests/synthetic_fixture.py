#!/usr/bin/env python3
"""synthetic_fixture.py -- a fully synthetic contract-schedule-shaped universe for A23 tests.

NOTHING here touches real data: synthetic seasons (3001..), synthetic game/team ids. Row/cluster
counts are deliberately far from the real 2,982/1,491 and 2,990/1,495 signatures, and fold ids
never collide with the frozen D006 list, so the shared runner's blinding gate admits the fixture
without any flag.

Schedule shape is deliberately IRREGULAR within a season (each team's games land on a random
subset of days) so that some teams open a season later than others and rest days vary -- both
properties A23's construction and kill-condition tests need to be non-degenerate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (3001, 3002, 3003)
N_TEAMS = 8


def _lagged_pace(n_off_poss, max_period):
    denom = 40.0 + 5.0 * np.maximum(0.0, np.asarray(max_period, float) - 4.0)
    return np.asarray(n_off_poss, float) * 40.0 / denom


def build_universe(n_games_per_team_per_season: int = 16, seed: int = 4747) -> pd.DataFrame:
    """One row per team-game (both sides of every game), ordered by (season, round). Every
    "round" pairs up ALL N_TEAMS teams (N_TEAMS is even, so this always terminates in EXACTLY
    n_games_per_team_per_season rounds per season -- unlike a "random eligible subset" scheme,
    which can strand a single lagging team with nobody left to pair against).

    Each team tracks its OWN running "next available date"; a pair's game date is the max of
    each side's own (next-available + an independent random 1-3-day gap), and BOTH sides then
    advance to that same date. This deliberately makes rest_own and rest_opp INDEPENDENT and
    heterogeneous across games (unlike a shared "everyone plays on round day D" clock, which
    would make rest_own == rest_opp identically for every row -- a degenerate fixture this
    module's own P25/P27 conformance checks correctly rejected before this fix).
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 700_000
    teams = [f"SYN{k}" for k in range(N_TEAMS)]
    assert N_TEAMS % 2 == 0, "round-robin pairing requires an even team count"
    for s in SEASONS:
        next_avail = {t: 0.0 for t in teams}
        for _round in range(n_games_per_team_per_season):
            order = list(teams)
            rng.shuffle(order)
            for i in range(0, len(order), 2):
                home, away = order[i], order[i + 1]
                gap_home = float(rng.integers(1, 4))
                gap_away = float(rng.integers(1, 4))
                game_date = max(next_avail[home] + gap_home, next_avail[away] + gap_away)
                next_avail[home] = game_date
                next_avail[away] = game_date
                gid += 1
                n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
                max_period = 4 + n_ot
                for team, opp in ((home, away), (away, home)):
                    proj = float(rng.uniform(70.0, 90.0))
                    n_off_poss = float(rng.uniform(70.0, 95.0) * (1.0 + 0.05 * n_ot))
                    rows.append({
                        "game_id": gid, "season": s, "day": game_date,
                        "game_date": s * 1000.0 + game_date,
                        "team_id": team, "opp_team_id": opp,
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
    return df.reset_index(drop=True)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_a23_lt_{test_season}",
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
        frame, source={"artifact_id": "a23_synthetic_fixture/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A23 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
