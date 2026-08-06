#!/usr/bin/env python3
"""synthetic_fixture_a13.py -- a fully synthetic contract-schedule-shaped universe, history frame
and lagged-lineup-membership frame for A13's own arm-module tests.

NOTHING here touches real data: synthetic seasons (6001..), synthetic game/team/player ids. Row
and cluster counts are far from the real 2,982/1,491 and 2,990/1,495 signatures, and no fold id
collides with the frozen D006 list, so the shared runner's blinding gate admits the fixture
without any flag.

Roster design: each team has an 8-player pool per season. Season-to-season, half the pool
persists and half turns over (by team, deterministically from the seed), so cont_i (the Jaccard
overlap between the team's evidence-so-far-this-season roster and its full-prior-season roster)
varies meaningfully both within and across teams -- the arm has real synthetic signal to find,
and both n_i=0 (openers) and n_i>0 rows are present in every season after the first.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (6001, 6002, 6003, 6004)
N_TEAMS = 6
POOL_SIZE = 8
GAMES_PER_TEAM_PER_SEASON = 16

TRUE_BETA3 = 6.0     # synthetic ground-truth interaction strength, so the arm has signal to find


def _lagged_pace(n_off_poss, max_period):
    denom = 40.0 + 5.0 * np.maximum(0.0, np.asarray(max_period, float) - 4.0)
    return np.asarray(n_off_poss, float) * 40.0 / denom


def _team_pool(team: str, season: int, seed: int) -> list[str]:
    """Deterministic 8-player pool for (team, season): persists ~50% of the PRIOR season's pool,
    replaces the rest, so cross-season Jaccard is neither 0 nor 1."""
    rng = np.random.Generator(np.random.PCG64(seed + hash((team, season)) % 1_000_000))
    if season == SEASONS[0]:
        return [f"{team}_P{k}" for k in range(POOL_SIZE)]
    prev_pool = _team_pool(team, season - 1, seed)
    keep = list(rng.choice(prev_pool, size=POOL_SIZE // 2, replace=False))
    new = [f"{team}_S{season}_N{k}" for k in range(POOL_SIZE - len(keep))]
    return keep + new


def build_universe_and_sources(seed: int = 4242):
    """Returns (universe, contract_schedule, history, lineup_membership)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    teams = [f"SYN{k}" for k in range(N_TEAMS)]
    uni_rows, sched_rows, hist_rows, lineup_rows = [], [], [], []
    gid = 600_000
    day = 0
    for s in SEASONS:
        pools = {t: _team_pool(t, s, seed) for t in teams}
        for _ in range(GAMES_PER_TEAM_PER_SEASON):
            order = list(teams)
            rng.shuffle(order)
            for i in range(0, len(order) - 1, 2):
                gid += 1
                day += 1
                game_date = s * 1000 + day
                home, away = order[i], order[i + 1]
                n_ot = int(rng.choice([0, 0, 0, 0, 1, 2]))
                max_period = 4 + n_ot
                for team, opp in ((home, away), (away, home)):
                    proj = float(rng.uniform(70.0, 90.0))
                    n_off_poss = float(rng.uniform(70.0, 95.0) * (1.0 + 0.05 * n_ot))
                    gap = float(rng.normal(0.0, 3.0))
                    depth = float(rng.integers(0, 11))
                    opp_depth = float(rng.integers(0, 11))
                    sched_rows.append({"team_id": team, "season": s, "game_date": game_date,
                                       "game_id": gid})
                    hist_rows.append({"team_id": team, "season": s, "game_id": gid,
                                      "n_off_poss": n_off_poss, "max_period": float(max_period)})
                    # lineup: 6 players drawn from the team's season pool, used this game
                    used = list(rng.choice(pools[team], size=6, replace=False))
                    for p in used:
                        lineup_rows.append({"team_id": team, "game_id": gid, "player_id": p})
                    uni_rows.append({
                        "game_id": gid, "season": s, "game_date": game_date,
                        "team_id": team, "opp_id": opp,
                        INCUMBENT_PROJECTION_COL: proj,
                        OFFSET_COL: float(np.log(proj)),
                        "n_off_poss": n_off_poss, "max_period": float(max_period),
                        "pace_gap": gap, "pace_evidence_depth": depth,
                        "opp_pace_evidence_depth": opp_depth,
                        "_game_minutes": 40.0 + 5.0 * n_ot,
                        "_overtime_periods": float(n_ot),
                        "_is_overtime": float(n_ot > 0),
                        "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
                    })
    universe = pd.DataFrame(uni_rows)
    universe[TARGET_COL_REAL] = _lagged_pace(universe["n_off_poss"], universe["max_period"])
    contract_schedule = pd.DataFrame(sched_rows)
    history = pd.DataFrame(hist_rows)
    lineup_membership = pd.DataFrame(lineup_rows)
    return universe, contract_schedule, history, lineup_membership


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Chronological expanding folds with synthetic fold ids (never colliding with D006)."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"a13_syn_lt_{test_season}",
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
        frame, source={"artifact_id": "a13_synthetic_fixture/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A13 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
