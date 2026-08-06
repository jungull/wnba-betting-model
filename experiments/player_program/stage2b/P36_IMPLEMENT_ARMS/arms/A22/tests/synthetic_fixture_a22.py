#!/usr/bin/env python3
"""synthetic_fixture_a22.py -- a fully synthetic contract-schedule-shaped universe for A22 tests.

NOTHING here touches real data: synthetic seasons (7001..), synthetic team/game/player ids.
Row/cluster counts are deliberately far from the real 2,982/1,491 and 2,990/1,495 signatures, and
fold ids never collide with the frozen D006 list, so the shared runner's blinding gate admits the
fixture without any flag.

Lineup construction: each team has a fixed 8-player pool. Each game, 5 of those 8 are drawn as
the offensive lineup with PERSISTENCE (the previous game's 5, minus a few swapped out) so that
some team-games have high churn (many swaps) and some have low/zero churn (same 5 as last game),
giving the arm real synthetic signal to recover as well as exercising the |P|<=1 fallback and the
n>=2-game base window.

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A22/ only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (7001, 7002, 7003)
N_TEAMS = 6
POOL_SIZE = 8
LINEUP_SIZE = 5
TRUE_COEF = 0.06        # real synthetic churn effect, so the arm has signal to recover


def _draw_lineup(rng, pool, prev_lineup, n_swap):
    """prev_lineup: tuple of 5 player ids or None (first game). n_swap in [0, LINEUP_SIZE]."""
    if prev_lineup is None or n_swap >= LINEUP_SIZE:
        return tuple(rng.choice(pool, size=LINEUP_SIZE, replace=False))
    keep = rng.choice(prev_lineup, size=LINEUP_SIZE - n_swap, replace=False)
    bench = [p for p in pool if p not in keep]
    swap_in = rng.choice(bench, size=n_swap, replace=False)
    return tuple(list(keep) + list(swap_in))


def build_universe(n_games_per_team_per_season: int = 16, seed: int = 7373) -> pd.DataFrame:
    """One row per team-game (both sides of every game), ordered by (season, day)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    teams = [f"SYN{k}" for k in range(N_TEAMS)]
    pools = {t: [f"{t}_P{p}" for p in range(POOL_SIZE)] for t in teams}
    prev_lineup = {t: None for t in teams}

    rows = []
    gid = 700_000
    day = 0
    for s in SEASONS:
        for _ in range(n_games_per_team_per_season):
            order = list(teams)
            rng.shuffle(order)
            for i in range(0, len(order) - 1, 2):
                gid += 1
                day += 1
                home, away = order[i], order[i + 1]
                n_ot = int(rng.choice([0, 0, 0, 0, 1]))
                is_playoff = int(rng.random() < 0.15)          # one draw per GAME, both sides share it
                for team, opp in ((home, away), (away, home)):
                    n_swap = int(rng.choice([0, 0, 1, 1, 2, 3, 5], p=[0.30, 0.15, 0.15, 0.15,
                                                                      0.10, 0.10, 0.05]))
                    lineup = _draw_lineup(rng, pools[team], prev_lineup[team], n_swap)
                    prev_lineup[team] = lineup
                    proj = float(rng.uniform(70.0, 90.0))
                    row = {
                        "game_id": gid, "season": s, "day": day,
                        "game_date": s * 1000 + day,
                        "team_id": team, "opp_id": opp,
                        "offense_team_id": team,
                        "is_playoff_game": is_playoff,
                        INCUMBENT_PROJECTION_COL: proj,
                        OFFSET_COL: float(np.log(proj)),
                        "_game_minutes": 40.0 + 5.0 * n_ot,
                        "_overtime_periods": float(n_ot),
                        "_is_overtime": float(n_ot > 0),
                        "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                    }
                    for k, p in enumerate(lineup, start=1):
                        row[f"off_p{k}"] = p
                    rows.append(row)
    df = pd.DataFrame(rows)

    # Synthetic outcome carries a real churn effect: TRUE_COEF on the symmetric TV-distance churn
    # of the row's OWN team + opponent's own lineup history, computed via the module under test
    # (a legitimate use here: this is fixture CONSTRUCTION using the arm's own pure feature code,
    # not a comparative performance measurement -- no fold, no MAE, no fit anywhere in this file).
    import feature_construction as fc
    appearances = fc.aggregate_game_player_appearances(df)
    prior = fc.compute_prior_last_and_base(appearances)
    own = fc.align_churn(prior, df["team_id"].to_numpy(), df["game_id"].to_numpy())
    opp = fc.align_churn(prior, df["opp_id"].to_numpy(), df["game_id"].to_numpy())
    x_true = 0.5 * (own["churn"] + opp["churn"])
    mu = df[INCUMBENT_PROJECTION_COL].to_numpy(float) * np.exp(TRUE_COEF * x_true)
    df[TARGET_COL_REAL] = rng.poisson(mu).astype(float)
    return df


def build_lineup_source(df: pd.DataFrame) -> pd.DataFrame:
    """The possession-level (here: one-row-per-team-game, already collapsed) lineup source the
    arm module consumes via its constructor's `lineups` argument -- distinct from `universe` per
    RUNNER_INTERFACE.md's lag_sources() convention, even though in this fixture the two frames
    happen to share the same row grain (one row per team-game); the arm module never assumes
    `lineups is universe`."""
    cols = ["game_id", "game_date", "season", "offense_team_id",
           "off_p1", "off_p2", "off_p3", "off_p4", "off_p5"]
    return df[cols].copy()


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_a22_lt_{test_season}",
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
        frame, source={"artifact_id": "a22_synthetic_fixture/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A22 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
