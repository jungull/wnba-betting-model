#!/usr/bin/env python3
"""cbs_v5.py — corrected implementation for `contract_baseline_suite_v5`.

v4's *specification* was sound; its implementation differed from it in ways that
would have produced confidently wrong numbers. v4's files are left untouched as
the historical record (its registry record names them); this module is the
corrected one.

**No file I/O.** No path argument exists. Frames arrive from the caller, so this
cannot reach the real contract even by accident, and it emits no artifact.

WHAT WAS ACTUALLY WRONG IN v4
-----------------------------
1. **λ tuning was not chronological.** `order_obligations` sorts by player first,
   so slicing the tuning indices 75/25 cut by *player*: fit held P0-P5, validation
   held P6-P7, and **all 36 dates appeared on both sides**. The registered rule is
   an inner *chronological* cut. Fixed in `chronological_inner_split`.
2. **The team runner never ordered its rows.** Shifted EWMAs were taken in
   whatever order the frame arrived, so a later game could become history for an
   earlier one. Shuffling identical frames moved team predictions by up to ~6-16
   points and changed dispersion. Fixed by sorting on frozen keys everywhere.
3. **One pooled calibration map** where the spec requires separate home/away
   maps, with no side indicator required at all.
4. **The residual sign was inverted.** Residuals were `prediction - outcome`
   while `emit_quantiles` *adds* offsets to the point, so asymmetric empirical
   quantiles came out reversed — a long lower tail was emitted as a long upper
   tail. For additive offsets the residual must be `outcome - prediction`.
5. **Missing channels were silently dropped**, quietly turning the registered
   four-channel estimator into a different model.
6. **Fitted-state hashes were incomplete** — the activity hash covered only the
   coefficients, so two runs with different scalers, λ or feature order could
   share one `model_hash`.
7. **Cold-start accounting ignored the target.** A player with prior obligations
   but zero prior *appearances* has no conditional history at all, yet was marked
   non-cold; team rows always reported zero prior games.
8. **Stage-A features were silently zero-filled** and `feature_asof` was taken on
   trust.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from cbs_builders import QUANTILE_LEVELS, QUANTILE_Z, SelectionLeakage
from cbs_generator import (ALPHA_GRID, DECLARED, LAMBDA_GRID, MIN_RESID_PLAYER,
                           MIN_RESID_TEAM, P_ACTIVE_FEATURES, SplitContext,
                           Standardizer, TEAM_POINTS_FLOOR, active_shifted_ewma,
                           active_shifted_ratio_ewma, emit_quantiles, logistic_fit,
                           logistic_predict, player_split, prefix_mean, team_split)

ARM_ID = "contract_baseline_suite_v5"

# ---- frozen: λ inner chronological cut ------------------------------------
LAMBDA_INNER_TAIL_FRACTION = 0.25
MIN_LAMBDA_FIT_DATES = 6
MIN_LAMBDA_VAL_DATES = 2
DEFAULT_LAMBDA = 1.0
DEFAULT_ALPHA = 0.10

# ---- frozen: team history, matching the registered run_reval family -------
TEAM_SORT_KEYS = ("team_id", "game_date", "game_id")
TEAM_HISTORY_GROUP = ("team_id", "season")     # resets at each season boundary
TEAM_MIN_PRIOR = 5                             # run_reval.MIN_PRIOR
REQUIRED_CHANNELS = ("ft", "3pt", "paint", "np2")   # run_reval.CHANNELS
SIDE_COL = "side"
REQUIRED_SIDES = ("home", "away")

PLAYER_SORT_KEYS = ("player_id", "season", "forecast_cutoff", "game_id")


class MissingRequiredInput(RuntimeError):
    """A required channel, side, feature or provenance field is absent."""


class AdapterBoundaryError(RuntimeError):
    """Real-data identity was not supplied where it is mandatory."""


# --------------------------------------------------------------------------
# 1. chronological inner split for λ  (v4 defect 1)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class InnerSplit:
    fit_idx: np.ndarray
    val_idx: np.ndarray
    fit_dates: list
    val_dates: list
    degenerate: bool = False
    reason: str = ""


def chronological_inner_split(frame: pd.DataFrame, ctx: SplitContext, *,
                              date_col: str = "game_date") -> InnerSplit:
    """Cut the TUNING segment into fit/validation on DISTINCT DATES.

    v4 sliced row indices, which — because obligations are ordered by player
    first — split by player and left every date on both sides. Cutting on dates
    is what makes the inner validation genuinely out-of-time.

    Rounding frozen: `n_val = floor(n_dates * 0.25)`; minimums 6 fit dates and
    2 validation dates; below that the fold is degenerate and λ takes its
    declared default.
    """
    idx = np.asarray(ctx.tuning_idx)
    if len(idx) == 0:
        return InnerSplit(idx, idx[:0], [], [], True, "empty tuning segment")

    sub = frame.loc[idx]
    dates = sorted(pd.unique(sub[date_col]))
    n_val = int(np.floor(len(dates) * LAMBDA_INNER_TAIL_FRACTION))
    if len(dates) < MIN_LAMBDA_FIT_DATES + MIN_LAMBDA_VAL_DATES \
            or n_val < MIN_LAMBDA_VAL_DATES:
        return InnerSplit(idx, idx[:0], dates, [], True,
                          f"{len(dates)} tuning dates; need "
                          f"{MIN_LAMBDA_FIT_DATES}+{MIN_LAMBDA_VAL_DATES}")

    fit_d, val_d = dates[:-n_val], dates[-n_val:]
    m = sub[date_col].isin(fit_d)
    fit_idx, val_idx = np.asarray(sub.index[m]), np.asarray(sub.index[~m])
    if set(fit_d) & set(val_d):
        raise SelectionLeakage("lambda inner split shares a date")
    return InnerSplit(fit_idx, val_idx, list(fit_d), list(val_d))


def select_lambda_chronological(X: pd.DataFrame, y: pd.Series, ctx: SplitContext,
                                frame: pd.DataFrame) -> tuple[float, bool, InnerSplit]:
    """Brier-minimising λ on a DATE-disjoint inner cut. Ties → smallest λ."""
    inner = chronological_inner_split(frame, ctx)
    if inner.degenerate or len(inner.val_idx) == 0:
        return DEFAULT_LAMBDA, True, inner
    ytr = y.reindex(inner.fit_idx)
    if len(np.unique(ytr.dropna())) < 2:
        return DEFAULT_LAMBDA, True, inner
    best, best_loss = DEFAULT_LAMBDA, np.inf
    for lam in LAMBDA_GRID:                       # ascending; first minimum wins
        std = Standardizer(X.loc[inner.fit_idx])
        beta = logistic_fit(std.transform(X.loc[inner.fit_idx]),
                            ytr.to_numpy(float), lam)
        p = logistic_predict(std.transform(X.loc[inner.val_idx]), beta)
        loss = float(np.mean((y.reindex(inner.val_idx).to_numpy(float)
                              - np.clip(p, 0, 1)) ** 2))
        if loss < best_loss - 1e-15:
            best, best_loss = lam, loss
    return best, False, inner


# --------------------------------------------------------------------------
# 2. residual sign  (v4 defect 4)
# --------------------------------------------------------------------------

def residuals(outcome: pd.Series, prediction: pd.Series) -> np.ndarray:
    """`outcome - prediction`.

    The offsets are ADDED to the point prediction, so the residual must point
    from prediction toward outcome. v4 computed `prediction - outcome`, which
    mirrored every asymmetric empirical quantile: a long lower tail in the data
    was emitted as a long upper tail.
    """
    return (pd.Series(outcome).astype(float)
            - pd.Series(prediction).astype(float)).to_numpy(dtype=float)


def dispersion(resid: np.ndarray, *, min_resid: int) -> tuple[float, np.ndarray, str]:
    """(sd, additive quantile offsets, method); fails closed on a degenerate pool."""
    r = np.asarray(resid, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return float("nan"), np.full(len(QUANTILE_LEVELS), np.nan), "insufficient"
    sd = float(np.std(r, ddof=1))
    if not np.isfinite(sd) or sd <= 0.0:
        return float("nan"), np.full(len(QUANTILE_LEVELS), np.nan), "insufficient"
    if len(r) >= min_resid:
        return sd, np.quantile(r, QUANTILE_LEVELS, method="linear"), "empirical"
    return sd, np.asarray(QUANTILE_Z) * sd, "gaussian"


# --------------------------------------------------------------------------
# 3. team history — explicit chronological keys, frozen reset  (defects 2,3,5)
# --------------------------------------------------------------------------

def require_team_inputs(frame: pd.DataFrame) -> None:
    """Fail closed when a registered channel or the side indicator is absent.

    v4 silently dropped missing channels, turning the registered four-channel
    estimator into a different model without saying so.
    """
    missing = [c for c in REQUIRED_CHANNELS if f"ch_{c}" not in frame.columns]
    if missing:
        raise MissingRequiredInput(
            f"required team channels absent: {missing}; the registered estimator "
            f"is four-channel and may not silently become a different model")
    if SIDE_COL not in frame.columns:
        raise MissingRequiredInput(
            f"required side indicator {SIDE_COL!r} absent; separate home/away "
            f"calibration maps cannot be fitted without it")
    bad = set(pd.unique(frame[SIDE_COL].dropna())) - set(REQUIRED_SIDES)
    if bad:
        raise MissingRequiredInput(f"unexpected {SIDE_COL} values: {sorted(bad)}")
    for k in TEAM_SORT_KEYS:
        if k not in frame.columns:
            raise MissingRequiredInput(f"team frame missing ordering key {k!r}")


def order_team_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Frozen chronological order, matching `run_reval`'s sort exactly."""
    return frame.sort_values(list(TEAM_SORT_KEYS), kind="mergesort")


def team_prior_games(frame: pd.DataFrame) -> pd.Series:
    """Strictly-prior team games within (team_id, season) — resets each season."""
    d = order_team_rows(frame)
    return d.groupby(list(TEAM_HISTORY_GROUP), sort=False).cumcount().reindex(frame.index)


def team_channel_trend(frame: pd.DataFrame, channel: str, alpha: float) -> pd.Series:
    """Shifted EWMA of one channel within (team_id, season), chronologically.

    Grouping and reset follow the registered family: history does NOT carry
    across a season boundary, and the sort is explicit so input order cannot
    make a later game part of an earlier row's history.
    """
    d = order_team_rows(frame)
    col = f"ch_{channel}"
    e = d.groupby(list(TEAM_HISTORY_GROUP), sort=False)[col].transform(
        lambda s: s.ewm(alpha=alpha, adjust=True).mean().shift(1))
    return e.reindex(frame.index)


def team_structural(frame: pd.DataFrame, alphas: dict) -> pd.Series:
    total = None
    for ch in REQUIRED_CHANNELS:
        s = team_channel_trend(frame, ch, alphas[ch])
        total = s if total is None else total + s
    return total


def fit_side_maps(frame: pd.DataFrame, x: pd.Series, idx: np.ndarray) -> dict:
    """Separate two-parameter linear maps per side, fitted on T2 only."""
    maps: dict[str, tuple[float, float]] = {}
    for side in REQUIRED_SIDES:
        sel = np.asarray(frame.index[(frame[SIDE_COL] == side)])
        use = np.intersect1d(sel, idx)
        xs, ys = x.reindex(use), frame["team_points"].reindex(use)
        ok = np.isfinite(xs) & np.isfinite(ys)
        if int(ok.sum()) >= 3:
            slope, intercept = np.polyfit(xs[ok].to_numpy(float),
                                          ys[ok].to_numpy(float), 1)
            maps[side] = (float(intercept), float(slope))
        else:
            maps[side] = (float(DECLARED["team_game_distribution"]["point"]), 0.0)
    return maps


def apply_side_maps(frame: pd.DataFrame, x: pd.Series, maps: dict) -> pd.Series:
    out = pd.Series(np.nan, index=frame.index, dtype=float)
    for side, (a, b) in maps.items():
        m = frame[SIDE_COL] == side
        out.loc[m] = a + b * x.loc[m]
    return out


# --------------------------------------------------------------------------
# 4. target-specific history accounting  (v4 defect 7)
# --------------------------------------------------------------------------

def player_history_accounting(frame: pd.DataFrame) -> pd.DataFrame:
    """`n_prior_candidate_games` and `n_prior_appearances`, kept separate.

    Cold-start is then TARGET-SPECIFIC:
      * `p_active` is cold only with **no prior obligation** — 0-of-k is evidence;
      * the conditional targets are cold with **no prior APPEARANCE**, because
        their history is the active subsequence; a player with 4 obligations and
        0 appearances has no conditional history at all and must be both cold
        and fallback. v4 marked exactly those rows non-cold.
    """
    d = frame.sort_values(list(PLAYER_SORT_KEYS), kind="mergesort")
    g = d.groupby(["player_id", "season"], sort=False)
    n_oblig = g.cumcount()
    n_app = g["appeared"].transform(
        lambda s: s.astype(float).cumsum().shift(1)).fillna(0.0)
    out = pd.DataFrame(index=d.index)
    out["n_prior_candidate_games"] = n_oblig.astype(int)
    out["n_prior_appearances"] = n_app.astype(int)
    out["has_prior_obligation"] = out["n_prior_candidate_games"] > 0
    out["has_prior_appearance"] = out["n_prior_appearances"] > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        out["p_plays_prior"] = np.where(n_oblig > 0, n_app / n_oblig, np.nan)
    return out.reindex(frame.index)


def cold_start_flag(hist: pd.DataFrame, target: str) -> pd.Series:
    if target == "p_active":
        return ~hist["has_prior_obligation"]
    return ~hist["has_prior_appearance"]


def n_prior_for(hist: pd.DataFrame, target: str) -> pd.Series:
    """The contract's `n_prior_games` = strictly-prior APPEARANCES readable at
    the cutoff, for every player target."""
    return hist["n_prior_appearances"].astype(int)


# --------------------------------------------------------------------------
# 5. complete fitted-state hashing + adapter boundary  (v4 defects 6, 8)
# --------------------------------------------------------------------------

def _canon(obj):
    if isinstance(obj, dict):
        return {str(k): _canon(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return None if not np.isfinite(float(obj)) else round(float(obj), 12)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, pd.Series):
        return _canon(obj.tolist())
    if isinstance(obj, np.ndarray):
        return _canon(obj.tolist())
    return obj


def fitted_state_hash(state: dict) -> str:
    """SHA-256 over the COMPLETE fitted state.

    v4 hashed only the coefficient vector, so two fits differing in scaler
    means, dropped columns, λ, feature order, fallback mean or dispersion could
    share a `model_hash` — which makes the hash useless for telling predictions
    apart. Every element that changes a prediction belongs in here.
    """
    return hashlib.sha256(json.dumps(_canon(state), sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def require_identity(config_hash: str, snapshot_hash: str, *, synthetic: bool) -> None:
    """Fail closed at the real-data boundary.

    A caller-supplied config hash and a default `snapshot_hash="synthetic"` are
    fine for a synthetic test and unacceptable for real data. Real runs must
    pass `synthetic=False` and supply both identities explicitly.
    """
    if synthetic:
        return
    for name, val in (("config_hash", config_hash), ("snapshot_hash", snapshot_hash)):
        if not isinstance(val, str) or len(val) != 64 or not all(
                c in "0123456789abcdef" for c in val.lower()):
            raise AdapterBoundaryError(
                f"{name} must be an explicit 64-hex digest for a real run; got {val!r}")
        if val.lower() in {"synthetic", "0" * 64}:
            raise AdapterBoundaryError(f"{name} is a placeholder, not a real identity")


def stage_a_features_strict(frame: pd.DataFrame, hist: pd.DataFrame, base_rate: float,
                            *, allow_declared_defaults: bool = False) -> pd.DataFrame:
    """Build the 14 canonical features, failing closed on absence.

    v4 silently substituted zeros for whatever the caller had not supplied, so a
    frame missing half the vector still produced confident probabilities. Real
    use must pass every feature; synthetic tests may opt into declared defaults
    explicitly.
    """
    supplied = {c for c in P_ACTIVE_FEATURES if c in frame.columns}
    derived = {"p_plays_prior", "player_gp_season"}          # from history
    missing = [c for c in P_ACTIVE_FEATURES if c not in supplied | derived]
    if missing and not allow_declared_defaults:
        raise MissingRequiredInput(
            f"Stage-A features absent and declared defaults not permitted: {missing}")

    X = pd.DataFrame(index=frame.index)
    for c in P_ACTIVE_FEATURES:
        if c == "p_plays_prior":
            X[c] = hist["p_plays_prior"].where(hist["has_prior_obligation"], base_rate)
        elif c == "player_gp_season":
            X[c] = hist["n_prior_appearances"].astype(float)
        elif c in frame.columns:
            X[c] = frame[c].astype(float)
        else:
            X[c] = 45.0 if c == "days_since_last_appearance" else 0.0
    return X[P_ACTIVE_FEATURES].astype(float)


def resolve_feature_asof(frame: pd.DataFrame, source_cols: list[str]) -> pd.Series:
    """The row's MAXIMUM actual source timestamp, failing closed on absence.

    v4 trusted whatever `feature_asof` the caller wrote. A real adapter must
    derive it from the sources actually read and prove it is strictly prior to
    the cutoff.
    """
    present = [c for c in source_cols if c in frame.columns]
    if not present:
        raise MissingRequiredInput(
            "cannot derive feature_asof: no source timestamp columns present")
    ts = frame[present].apply(pd.to_datetime, utc=True, errors="coerce")
    if ts.isna().any().any():
        raise MissingRequiredInput("unparseable source timestamp; provenance ambiguous")
    asof = ts.max(axis=1)
    cutoff = pd.to_datetime(frame["forecast_cutoff"], utc=True, errors="coerce")
    if (asof >= cutoff).any():
        raise MissingRequiredInput(
            f"{int((asof >= cutoff).sum())} rows have feature_asof >= forecast_cutoff")
    return asof.dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace(
        r"(\+0000)$", "+00:00", regex=True)
