#!/usr/bin/env python3
"""synthetic_fixture_a21.py -- fully synthetic possession-level + team-game universe fixtures for
A21's own arm-module tests. Mirrors A03/A08's fixture conventions: synthetic seasons (9101..),
synthetic game/team ids, far from the real 2,982/1,491 and 2,990/1,495 signatures, no fold id
collides with the frozen D006 list, so the blinding gate would admit these frames without any
flag (the module never invokes the runner against anything else).

NOTHING here touches real data. No real fold, no real MAE, no comparative historical performance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (9101, 9102, 9103, 9104)
TEAMS = tuple(range(6))
TRUE_COEF_X = 0.20          # synthetic ground-truth garbage-time-contamination effect (log-scale)


def build_games(n_games_per_season: int = 50, seed: int = 777) -> pd.DataFrame:
    """One row per game: game_id, game_date (strictly increasing int, one per day), season,
    home/away team_id, is_playoff_game."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 900_000
    day = 20400101
    for s in SEASONS:
        for k in range(n_games_per_season):
            gid += 1
            day += 1
            home, away = rng.choice(TEAMS, size=2, replace=False)
            playoff = 1.0 if k >= n_games_per_season - 6 else 0.0     # last 6 games "playoff"
            rows.append({"game_id": gid, "game_date": day, "season": s,
                        "home_team_id": int(home), "away_team_id": int(away),
                        "is_playoff_game": playoff})
    return pd.DataFrame(rows)


def build_possessions(games: pd.DataFrame, possessions_per_team: int = 70,
                      seed: int = 321) -> pd.DataFrame:
    """One row per (game, offense_team, possession): a fully synthetic possession-level frame
    carrying `non_competitive_conservative`. The per-game non-competitive RATE drifts slowly and
    smoothly by game_date so trailing decay-weighted shares carry genuine, non-degenerate signal
    (needed so the empty-prior-set / strict-lagging tests have something to detect)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    # a smooth per-team latent "garbage-time propensity" that drifts across the archive, so a
    # trailing decayed share is informative and strictly-later perturbations are detectable
    drift = {t: rng.uniform(0.10, 0.15) for t in TEAMS}
    for _, g in games.iterrows():
        for side_col, team_col in (("home_team_id", "home"), ("away_team_id", "away")):
            team_id = int(g[side_col])
            base_rate = float(np.clip(drift[team_id] + 0.15 * np.sin(g["game_date"] / 37.0)
                                      + (0.20 if g["is_playoff_game"] == 0.0 else -0.05),
                                      0.02, 0.9))
            flags = rng.random(possessions_per_team) < base_rate
            for f in flags:
                rows.append({"game_id": int(g["game_id"]), "game_date": int(g["game_date"]),
                            "season": int(g["season"]), "offense_team_id": team_id,
                            "non_competitive_conservative": float(bool(f))})
    return pd.DataFrame(rows)


def build_universe(games: pd.DataFrame, possessions: pd.DataFrame) -> pd.DataFrame:
    """Two team-game rows per game. `realised_team_off_possessions_reg_equiv` is generated so the
    synthetic contamination share x has a genuine (weak) effect on the target, on top of the
    is_playoff_game nuisance -- purely for end-to-end runner exercise, never inspected as evidence
    of anything about the real arm."""
    import feature_construction as fc

    rows = []
    for _, g in games.iterrows():
        for side_col, opp_col in (("home_team_id", "away_team_id"),
                                  ("away_team_id", "home_team_id")):
            rows.append({"game_id": int(g["game_id"]), "game_date": int(g["game_date"]),
                        "season": int(g["season"]), "team_id": int(g[side_col]),
                        "opponent_team_id": int(g[opp_col]),
                        "is_playoff_game": float(g["is_playoff_game"])})
    uni = pd.DataFrame(rows)

    rng = np.random.Generator(np.random.PCG64(55))
    uni["pace_evidence_depth"] = rng.uniform(1.0, 10.0, len(uni))
    proj = rng.uniform(70.0, 90.0, len(uni))
    uni[INCUMBENT_PROJECTION_COL] = proj
    uni[OFFSET_COL] = np.log(proj)

    raw = fc.compute_nc(possessions, uni[["team_id", "opponent_team_id", "game_id", "game_date",
                                          "season"]])
    train_mask_all = np.ones(len(uni), dtype=bool)     # a full-archive constant for target gen
    filled = fc.impute_empty_prior_set(raw["nc_own"], raw["nc_opp"], train_mask_all)
    x_true = fc.contamination_share(filled["nc_own"], filled["nc_opp"])
    eta = np.log(proj) + (-0.15) * uni["is_playoff_game"].to_numpy() + TRUE_COEF_X * x_true
    mu = np.exp(eta)
    uni[TARGET_COL_REAL] = rng.poisson(mu).astype(float)

    n_ot = (rng.random(len(uni)) < 0.05).astype(float) * rng.integers(1, 3, len(uni))
    uni["_game_minutes"] = 40.0 + 5.0 * n_ot
    uni["_overtime_periods"] = n_ot
    uni["_is_overtime"] = (n_ot > 0).astype(float)
    uni["_team_minutes"] = 5.0 * uni["_game_minutes"]
    return uni.reset_index(drop=True)


def build_folds(df: pd.DataFrame) -> list[dict]:
    """Chronological expanding folds with synthetic fold ids (never colliding with D006)."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(df["season"].to_numpy() < test_season)
        test = np.flatnonzero(df["season"].to_numpy() == test_season)
        folds.append({"fold_id": f"a21_syn_lt_{test_season}", "train_idx": train,
                      "test_idx": test})
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
        frame, source={"artifact_id": "synthetic_fixture_a21/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A21 tests"},
        note="synthetic: rare synthetic overtime, unrelated to the arm's own construction")
