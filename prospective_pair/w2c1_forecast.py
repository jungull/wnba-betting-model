"""W2-C1 ridge score-level extension — PROSPECTIVE FORECASTER. FROZEN 2026-08-03.

This is the frozen prospective challenger selected by Wave 2. It is deliberately tiny:
the whole model is the champion ridge's existing solve, read off at score level.

    fit, on regular-season games with game_date < slate_date in the SAME season:
        pts_for ~ offence(team) - defence(opp) + hca * is_home,  ridge penalty 1.0
    then
        home = mu + off[home] - dfn[away] + hca
        away = mu + off[away] - dfn[home]
        margin = home - away        (identical to BENCH-R margin, verified to 2.8e-14)
        total  = home + away

FROZEN CONTRACT — do not change any of this without a new registered wave:
  * ridge penalty is a literal 1.0. Nothing is tuned. Ever.
  * training frame is strictly-prior, same-season, regular season only.
  * warm-up: both sides need >= 10 prior same-season games, and the solve needs
    >= 20 prior team-rows. Below that the game is NOT forecast — it is reported
    as ineligible. It is never filled with a fallback (Amendment 002 rule 0).
  * no calibration layer. W2-C1's score-level calibration slopes were 0.895 /
    0.950 / 1.081 on home/away/total, already close to 1. Its margin slope is
    0.739 — a PREREGISTERED WATCH ITEM, not a defect to repair. Per L-W1-001 an
    MSE-shaped slope diagnostic does NOT license MAE shrinkage.

Usage:
    from w2c1_forecast import forecast_slate, MODEL_ID, model_config
    preds = forecast_slate(slate_date, team_master_path)
"""
from __future__ import annotations
import hashlib
import numpy as np
import pandas as pd

MODEL_ID = "ridge_score_level_w2c1_v1"
FROZEN_AT = "2026-08-03"
RIDGE_LAMBDA = 1.0
MIN_PRIOR = 10          # both sides, prior same-season games
MIN_SOLVE_ROWS = 20     # prior team-rows needed before the ridge is solved


def model_config() -> dict:
    """The frozen configuration. Hash this into the log's model_version_hash."""
    return {
        "model_id": MODEL_ID,
        "frozen_at": FROZEN_AT,
        "ridge_lambda": RIDGE_LAMBDA,
        "min_prior_games_per_side": MIN_PRIOR,
        "min_solve_rows": MIN_SOLVE_ROWS,
        "training_frame": "same-season, regular season only, game_date < slate_date",
        "targets": ["home_score", "away_score", "margin", "total"],
        "calibration": None,
        "tuned_parameters": [],
        "selected_by": "Wave 2, 2026-08-03, development-candidate selection",
        "promotion_status": "FROZEN PROSPECTIVE CHALLENGER — not production",
    }


def model_version_hash() -> str:
    cfg = model_config()
    blob = "|".join(f"{k}={cfg[k]!r}" for k in sorted(cfg))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _solve(hs: pd.DataFrame):
    teams = sorted(set(hs.team) | set(hs.opp))
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    X = np.zeros((len(hs), 2 * T + 1))
    rr = np.arange(len(hs))
    X[rr, [idx[t] for t in hs.team]] = 1.0
    X[rr, [T + idx[t] for t in hs.opp]] = -1.0
    X[:, -1] = hs.is_home.values
    y = hs.pf.values.astype(float)
    mu = y.mean()
    b = np.linalg.solve(X.T @ X + RIDGE_LAMBDA * np.eye(2 * T + 1), X.T @ (y - mu))
    return mu, {t: b[idx[t]] for t in teams}, {t: b[T + idx[t]] for t in teams}, b[-1]


def load_team_long(team_master_path: str) -> pd.DataFrame:
    tm = pd.read_parquet(team_master_path)
    tm["game_date"] = pd.to_datetime(tm.game_date)
    tm = tm[tm.season_type == "Regular Season"]
    return tm.sort_values(["game_date", "game_id"]).reset_index(drop=True)


def forecast_slate(slate_date, team_master_path: str, matchups=None) -> pd.DataFrame:
    """Forecast every game on `slate_date` using ONLY games strictly before it.

    matchups: optional list of (home_team_id, away_team_id). If None, the slate is
    taken from the master itself (historical replay / verification).
    Returns one row per game with eligibility explicitly stated.
    """
    slate_date = pd.Timestamp(slate_date)
    tm = load_team_long(team_master_path)
    season = tm.loc[tm.game_date == slate_date, "season"]
    if not len(season):
        prior = tm[tm.game_date < slate_date]
        if not len(prior):
            raise ValueError(f"no data before {slate_date.date()}")
        season = prior.season.tail(1)
    season = int(season.iloc[0])

    hist = tm[(tm.game_date < slate_date) & (tm.season == season)]
    LONG = hist[["game_id", "season", "game_date", "team_id", "opp_team_id", "pts", "is_home"]] \
        .rename(columns={"team_id": "team", "opp_team_id": "opp", "pts": "pf"})
    played = LONG.groupby("team").size().to_dict()

    if matchups is None:
        day = tm[(tm.game_date == slate_date) & (tm.is_home == 1)]
        matchups = list(zip(day.team_id, day.opp_team_id))
        gids = list(day.game_id.astype(str))
    else:
        gids = [None] * len(matchups)

    solvable = len(LONG) >= MIN_SOLVE_ROWS
    if solvable:
        mu, off, dfn, hca = _solve(LONG)

    rows = []
    for (h, a), gid in zip(matchups, gids):
        nh, na = played.get(h, 0), played.get(a, 0)
        eligible = solvable and nh >= MIN_PRIOR and na >= MIN_PRIOR
        rec = {
            "game_id": gid, "slate_date": slate_date.date().isoformat(), "season": season,
            "home_team_id": h, "away_team_id": a,
            "home_prior_games": nh, "away_prior_games": na,
            "eligible": eligible,
            "ineligible_reason": None if eligible else (
                "solve frame < %d prior team-rows" % MIN_SOLVE_ROWS if not solvable
                else "warm-up: min(prior games)=%d < %d" % (min(nh, na), MIN_PRIOR)),
            "n_train_rows": int(len(LONG)),
            "max_source_date": str(LONG.game_date.max().date()) if len(LONG) else None,
        }
        if eligible:
            ph = mu + off.get(h, 0.0) - dfn.get(a, 0.0) + hca
            pa = mu + off.get(a, 0.0) - dfn.get(h, 0.0)
            rec.update(home_score=float(ph), away_score=float(pa),
                       margin=float(ph - pa), total=float(ph + pa))
        else:
            rec.update(home_score=None, away_score=None, margin=None, total=None)
        rows.append(rec)
    out = pd.DataFrame(rows)
    if len(out) and out.max_source_date.notna().any():
        assert pd.Timestamp(out.max_source_date.dropna().iloc[0]) < slate_date, \
            "LEAKAGE: training frame reaches the slate date"
    return out
