#!/usr/bin/env python3
"""synthetic_fixture_a17.py -- a fully synthetic universe + possession-level history for
A17_transition_mix_share tests.

NOTHING here touches real data: synthetic seasons (9001..), synthetic team/game ids, synthetic
Poisson counts and possession durations. Row/cluster counts are deliberately far from the real
2,982/1,491 and 2,990/1,495 signatures, and fold ids never collide with the frozen D006 list, so
the runner's blinding gate admits the fixture without any flag.

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A17/ only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

TEAMS = ("TA", "TB", "TC", "TD")
SEASONS = (9001, 9002, 9003)
TRUE_COEF = 0.6          # real synthetic x_transition_mix effect, so the arm has signal to recover
POSSESSIONS_PER_SIDE = 12


def _round_robin_pairs(teams):
    pairs = []
    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            pairs.append((teams[i], teams[j]))
    return pairs


def build_possessions(seed: int = 1717) -> pd.DataFrame:
    """Possession-level rows: game_id, game_date, season, offense_team_id, defense_team_id,
    duration_sec. Each team's per-game 'transition propensity' is a fixed per-team trait so the
    trailing share is genuinely informative (not required for blinded testing, just a sane
    fixture) -- irrelevant to any promotion decision, which this suite never computes.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    trait = {t: rng.uniform(0.2, 0.6) for t in TEAMS}     # per-team short-possession propensity
    rows = []
    gid = 900_000
    day = 0
    for s in SEASONS:
        pairs = _round_robin_pairs(TEAMS)
        rng.shuffle(pairs)
        for (home, away) in pairs:
            gid += 1
            day += 3
            for offense, defense in ((home, away), (away, home)):
                p_short = 0.5 * (trait[offense] + (1.0 - trait[defense]))
                durs = np.where(rng.uniform(size=POSSESSIONS_PER_SIDE) < p_short,
                                rng.uniform(2.0, 7.9, POSSESSIONS_PER_SIDE),
                                rng.uniform(8.1, 22.0, POSSESSIONS_PER_SIDE))
                for d in durs:
                    rows.append({"game_id": gid, "game_date": day, "season": s,
                                "offense_team_id": offense, "defense_team_id": defense,
                                "duration_sec": float(d)})
    return pd.DataFrame(rows)


def build_universe(possessions: pd.DataFrame, seed: int = 2024) -> pd.DataFrame:
    """One row per (game_id, team_id), both sides of every game in `possessions`. The LAST
    season's games are all forced is_playoff_game=0 (mirrors synthetic_fixture_a05.py), so the
    card's fold_local_fallback note (GATE_INVOCATION_CONTRACT section 4 fold-2026-style
    degeneracy) is exercised on at least one evaluable fold, not merely asserted.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    games = (possessions[["game_id", "game_date", "season", "offense_team_id", "defense_team_id"]]
            .drop_duplicates(subset=["game_id"]).sort_values("game_id"))
    rows = []
    for _, g in games.iterrows():
        is_playoff = 0 if g["season"] == SEASONS[-1] else int(rng.choice([0, 0, 0, 1]))
        n_ot = int(rng.choice([0, 0, 0, 0, 1]))
        for team, opp in ((g["offense_team_id"], g["defense_team_id"]),
                          (g["defense_team_id"], g["offense_team_id"])):
            proj = float(rng.uniform(70.0, 90.0))
            rows.append({
                "game_id": int(g["game_id"]), "game_date": int(g["game_date"]),
                "season": int(g["season"]), "team_id": team, "opp_team_id": opp,
                "is_playoff_game": is_playoff,
                INCUMBENT_PROJECTION_COL: proj, OFFSET_COL: float(np.log(proj)),
                TARGET_COL_REAL: float(rng.poisson(proj)),
                "_game_minutes": 40.0 + 5.0 * n_ot, "_overtime_periods": float(n_ot),
                "_is_overtime": float(n_ot > 0), "_team_minutes": 5.0 * (40.0 + 5.0 * n_ot),
            })
    df = pd.DataFrame(rows).sort_values(["game_date", "game_id", "team_id"], kind="mergesort")
    return df.reset_index(drop=True)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Two chronological expanding folds with synthetic fold ids (train on season i, test on
    season i+1), exactly the A05 fixture's convention."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"syn_a17_lt_{test_season}", "train_idx": train, "test_idx": test})
    return folds


def build_prohibited_basis(df: pd.DataFrame):
    """Synthetic realised-duration basis, aligned row-for-row with the universe frame -- same
    construction as synthetic_fixture_a05.py."""
    import guard_harness as gh
    frame = pd.DataFrame({
        "game_minutes": df["_game_minutes"].to_numpy(float),
        "overtime_periods": df["_overtime_periods"].to_numpy(float),
        "is_overtime": df["_is_overtime"].to_numpy(float),
        "team_minutes": df["_team_minutes"].to_numpy(float),
    }, index=df.index)
    return gh.make_prohibited_basis(
        frame, source={"artifact_id": "synthetic_fixture_a17/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A17 tests"},
        note="synthetic: game_minutes = 40 + 5*n_ot per synthetic game")
