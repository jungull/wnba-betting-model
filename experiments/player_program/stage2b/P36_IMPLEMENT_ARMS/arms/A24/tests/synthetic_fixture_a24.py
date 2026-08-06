#!/usr/bin/env python3
"""synthetic_fixture_a24.py -- fully synthetic contract-schedule + team-game universe fixtures
for A24's own arm-module tests. Mirrors A08/A21's fixture conventions: synthetic seasons
(9101..), synthetic game/team ids, far from the real 2,982/1,491 and 2,990/1,495 signatures, no
fold id collides with the frozen D006 list, so the blinding gate would admit these frames without
any flag (the module never invokes the runner against anything else).

NOTHING here touches real data. No real fold, no real MAE, no comparative historical performance.

Two schedule builders:
  * build_contract_schedule / build_universe -- the "clean" fixture: every team has already
    played at least one contract-schedule game before its own first UNIVERSE row (the synthetic
    analogue of the real archive's 2021-opening-day rows: present in the contract schedule,
    excluded from the modeled universe). No true franchise debut anywhere in this fixture.
  * build_contract_schedule_with_debut / build_universe_with_debut -- adds one expansion team
    whose FIRST-EVER row (contract-schedule row, not just universe row) appears mid-archive, to
    exercise A24's fail-closed franchise-debut path (feature_construction.py's GENUINE GAP
    DISCLOSED note) deliberately and safely, on synthetic data only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL

SEASONS = (9101, 9102, 9103, 9104)
TEAMS = tuple(range(6))
TRUE_COEF_X = -0.015        # synthetic ground-truth rest-level effect (log-scale; small & tidy)

_BASE_DATE = pd.Timestamp("2030-01-01")


def _date_str(day_index: int) -> str:
    """Real calendar date string for a synthetic day-index counter. feature_construction.py's
    compute_rest_days runs pd.to_datetime() on game_date and then divides by a 1-day timedelta to
    get a day COUNT -- an integer like 20300101 fed to pd.to_datetime is silently (mis)parsed as
    nanoseconds-since-epoch, not as a calendar date, which would make every 'days since' gap
    collapse to ~1e-14 (a real bug caught by t04_strict_lagging during this unit's own test
    development). Emitting genuine ISO date strings here is what makes pd.to_datetime behave as
    the real archive's own date column would."""
    return (_BASE_DATE + pd.Timedelta(days=int(day_index))).strftime("%Y-%m-%d")


def _build_games(teams, n_games_per_season, seed, extra_first_day_team=None,
                 extra_first_day_season=None):
    """One row per game (both sides), chronological, one game-DAY-SLATE per day. The archive's
    very first day is a full round-robin pairing of every team (so every team's true debut is on
    that single excluded day, never scattered across later days -- the 'clean' fixture must
    guarantee EVERY team has at least one contract-schedule appearance before its first UNIVERSE
    row, matching the real archive's 4-game 2021-opening-day slate covering multiple teams at
    once). `extra_first_day_team`, if given, is inserted as a debuting team playing its
    FIRST-EVER game on the first day of `extra_first_day_season` (a genuine mid-archive debut)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    rows = []
    gid = 800_000
    day = 0                    # day-INDEX counter, converted to a real calendar date at the end
    pool = list(teams)

    # day 1: every team plays exactly once (round-robin pairing), so the single excluded
    # opening day covers every team's true debut at once
    shuffled = list(pool)
    rng.shuffle(shuffled)
    for i in range(0, len(shuffled) - 1, 2):
        gid += 1
        rows.append({"game_id": gid, "game_date": day, "season": SEASONS[0],
                    "home_team_id": int(shuffled[i]), "away_team_id": int(shuffled[i + 1])})
    day += 1

    for s in SEASONS:
        season_teams = list(pool)
        start_k = 0
        if s == SEASONS[0]:
            start_k = len(shuffled) // 2          # day-1 games already emitted above
        for k in range(start_k, n_games_per_season):
            gid += 1
            if (extra_first_day_team is not None and s == extra_first_day_season and k == start_k):
                home = extra_first_day_team
                away = int(rng.choice([t for t in season_teams if t != home]))
            else:
                home, away = rng.choice(season_teams, size=2, replace=False)
                home, away = int(home), int(away)
            rows.append({"game_id": gid, "game_date": day, "season": s,
                        "home_team_id": home, "away_team_id": away})
            day += 1
    out = pd.DataFrame(rows)
    out["game_date"] = out["game_date"].apply(_date_str)
    return out


def _expand_sides(games: pd.DataFrame) -> pd.DataFrame:
    """Two team-game rows per game: team_id / opp_team_id, mirroring possession_features.py's
    own 'opp_team_id' column name (verified against the frozen module, not A21's own
    'opponent_team_id' naming -- see this unit's REPORT note on that cross-arm inconsistency)."""
    rows = []
    for _, g in games.iterrows():
        for side_col, opp_col in (("home_team_id", "away_team_id"),
                                  ("away_team_id", "home_team_id")):
            rows.append({"game_id": int(g["game_id"]), "game_date": str(g["game_date"]),
                        "season": int(g["season"]), "team_id": int(g[side_col]),
                        "opp_team_id": int(g[opp_col])})
    return pd.DataFrame(rows)


def build_contract_schedule(n_games_per_season: int = 40, seed: int = 777) -> pd.DataFrame:
    """The FULL synthetic contract schedule (analogue of team_possession_prior_v1's 2,990 rows):
    every game ever scheduled, including the archive's very first day (analogue of the real 2021
    opening-day rows, which the modeled universe excludes but the contract schedule carries)."""
    games = _build_games(TEAMS, n_games_per_season, seed)
    return _expand_sides(games)


def build_universe_frame(contract_schedule: pd.DataFrame) -> pd.DataFrame:
    """The modeled universe: the contract schedule MINUS its own very first day (the synthetic
    analogue of the real archive's 4 excluded 2021-opening-day games) -- so every universe row
    still has at least the excluded opening day as its own team's possible prior contract game,
    exercising exactly the case the card's 'cross-season prior game covers openers' claim
    describes (season 2's opener looks back into season 1; season 1's SECOND day looks back into
    season 1's first day, which is itself excluded from the universe but present in the contract
    schedule)."""
    first_day = str(contract_schedule["game_date"].min())          # ISO strings sort lexically
    uni = contract_schedule[contract_schedule["game_date"] > first_day].reset_index(drop=True)
    return uni


def _attach_target_columns(uni: pd.DataFrame, x_true: np.ndarray, seed: int = 55) -> pd.DataFrame:
    rng = np.random.Generator(np.random.PCG64(seed))
    uni = uni.copy()
    proj = rng.uniform(70.0, 90.0, len(uni))
    uni[INCUMBENT_PROJECTION_COL] = proj
    uni[OFFSET_COL] = np.log(proj)
    eta = np.log(proj) + TRUE_COEF_X * np.nan_to_num(x_true, nan=5.0)
    mu = np.exp(eta)
    uni[TARGET_COL_REAL] = rng.poisson(mu).astype(float)

    n_ot = (rng.random(len(uni)) < 0.05).astype(float) * rng.integers(1, 3, len(uni))
    uni["_game_minutes"] = 40.0 + 5.0 * n_ot
    uni["_overtime_periods"] = n_ot
    uni["_is_overtime"] = (n_ot > 0).astype(float)
    uni["_team_minutes"] = 5.0 * uni["_game_minutes"]
    return uni


def build_universe(contract_schedule: pd.DataFrame, seed: int = 55) -> pd.DataFrame:
    """Clean fixture universe with target/offset columns attached, no true franchise debut."""
    import feature_construction as fc

    uni = build_universe_frame(contract_schedule)
    out = fc.rest_level_symmetric(
        uni["team_id"].to_numpy(), uni["opp_team_id"].to_numpy(),
        uni["game_id"].to_numpy(), uni["game_date"].to_numpy(),
        history_team_id=contract_schedule["team_id"].to_numpy(),
        history_game_date=contract_schedule["game_date"].to_numpy(),
        history_game_id=contract_schedule["game_id"].to_numpy())
    return _attach_target_columns(uni, out["x"], seed=seed).reset_index(drop=True)


def build_contract_schedule_with_debut(n_games_per_season: int = 40, seed: int = 778,
                                       debut_team: int = 6,
                                       debut_season: int = SEASONS[2]) -> pd.DataFrame:
    """Contract schedule with one extra team whose first-ever row is mid-archive (season index
    2 by default) -- a genuine franchise debut, exercising the fail-closed path."""
    games = _build_games(TEAMS, n_games_per_season, seed,
                         extra_first_day_team=debut_team, extra_first_day_season=debut_season)
    return _expand_sides(games)


def build_universe_with_debut(contract_schedule: pd.DataFrame, seed: int = 56) -> pd.DataFrame:
    """Universe built from the debut-carrying contract schedule; the debuting team's own first
    row IS included in the universe (it is not the archive's very first day), so A24's own
    fail-closed check fires on it -- deliberately, for the negative test."""
    uni = build_universe_frame(contract_schedule)
    # do NOT attempt rest_level_symmetric here (it will raise by design); attach a minimal set
    # of the columns build_design's caller needs, target values are irrelevant for this test.
    rng = np.random.Generator(np.random.PCG64(seed))
    uni = uni.copy()
    proj = rng.uniform(70.0, 90.0, len(uni))
    uni[INCUMBENT_PROJECTION_COL] = proj
    uni[OFFSET_COL] = np.log(proj)
    uni[TARGET_COL_REAL] = rng.poisson(proj).astype(float)
    return uni.reset_index(drop=True)


def build_folds(uni: pd.DataFrame) -> list[dict]:
    """Chronological expanding folds with synthetic fold ids (never colliding with D006)."""
    folds = []
    for i in range(1, len(SEASONS)):
        test_season = SEASONS[i]
        train = np.flatnonzero(uni["season"].to_numpy() < test_season)
        test = np.flatnonzero(uni["season"].to_numpy() == test_season)
        if len(train) == 0 or len(test) == 0:
            continue
        folds.append({"fold_id": f"a24_syn_lt_{test_season}", "train_idx": train,
                      "test_idx": test})
    return folds


def build_prohibited_basis(df: pd.DataFrame):
    """Synthetic realised-duration basis, aligned row-for-row with the universe frame. At P38
    time the caller uses postgame_surrogate_guard.realised_duration_basis against the frozen
    possessions artifact instead."""
    import guard_harness as gh
    frame = pd.DataFrame({
        "game_minutes": df.get("_game_minutes", pd.Series(40.0, index=df.index)).to_numpy(float),
        "overtime_periods": df.get("_overtime_periods",
                                   pd.Series(0.0, index=df.index)).to_numpy(float),
        "is_overtime": df.get("_is_overtime", pd.Series(0.0, index=df.index)).to_numpy(float),
        "team_minutes": df.get("_team_minutes",
                               pd.Series(200.0, index=df.index)).to_numpy(float),
    }, index=df.index)
    return gh.make_prohibited_basis(
        frame, source={"artifact_id": "synthetic_fixture_a24/1", "path": None,
                       "note": "synthetic prohibited basis for blinded A24 tests"},
        note="synthetic: rare synthetic overtime, unrelated to the arm's own construction")
