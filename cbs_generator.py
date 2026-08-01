#!/usr/bin/env python3
"""cbs_generator.py — the end-to-end generator for `contract_baseline_suite_v4`.

WHAT THIS IS
------------
v3's `cbs_builders.py` proved useful *primitives*. This module is the registered
**pipeline**: given contract-shaped frames it emits, for every required
obligation row, a contract-schema prediction that `prediction_contract_v2.
validate_predictions()` accepts.

**It has no file I/O whatsoever.** There is no path, no read, no write. Every
input arrives as a DataFrame argument, so it *cannot* touch the real contract
even by accident; `tests/test_cbs_generator.py` drives it entirely with
synthetic frames. Running it produces no artifact, no accuracy figure and no
coverage score.

THE FIVE v3 DEFECTS THIS CLOSES
-------------------------------
1. **Team split cut on rows.** T1/T2/T3 were shares of team-game *rows*, so the
   two rows of one game — and two games on one date — could land in different
   segments, leaking one team's outcome into the segment fitting the other's
   calibration map. v4 cuts on **distinct dates**.
2. **Selection was not split-bound.** Returning disjoint arrays does not make
   contamination unrepresentable; nothing stopped a caller handing calibration
   rows to a tuner. v4 selection APIs require a `SplitContext` and **reject** any
   index outside the tuning segment.
3. **Obligation order was unpinned**, so tie-breaking silently depended on input
   row order. v4 orders by `(forecast_cutoff, game_id)` within player-season and
   **fails closed** on indistinguishable duplicates.
4. **A constant residual pool yields `sd == 0`**, which is finite and passed v3's
   check but violates the contract's `pred_sd > 0`. v4 treats nonfinite *and*
   nonpositive sd as insufficient and routes to the declared fallback.
5. **Base rates and fallback means were not restricted to the prefix.** v4
   computes them from tuning indices only, through the same guard.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from cbs_builders import (ALPHA_GRID, DEFAULT_ALPHA, DEFAULT_LAMBDA, LAMBDA_GRID,
                          MIN_RESID_PLAYER, MIN_RESID_TEAM, QUANTILE_LEVELS,
                          QUANTILE_Z, SelectionLeakage, TEAM_POINTS_FLOOR,
                          emit_quantiles, shifted_ewma, shifted_ratio_ewma)

# --------------------------------------------------------------------------
# frozen v4 constants
# --------------------------------------------------------------------------

#: the registered arm this pipeline emits under
ARM_ID = "contract_baseline_suite_v4"

#: player split: calibration tail as a share of DISTINCT training dates
PLAYER_TAIL_FRACTION = 0.25
MIN_TUNING_DATES = 8
MIN_CALIBRATION_DATES = 4

#: team split: T2 and T3 each take this share of DISTINCT training dates
TEAM_T2_FRACTION = 0.25
TEAM_T3_FRACTION = 0.25
MIN_T1_DATES = 8
MIN_T2_DATES = 4
MIN_T3_DATES = 4

#: declared dispersion fallbacks (v2 §9 constants, carried forward)
DECLARED = {
    "p_active": {"point": 0.800, "sd": None},
    "e_minutes_given_active": {"point": 20.0, "sd": 9.0, "low": 0.0, "high": 48.0},
    "attempts_usage": {"point": 7.0, "sd": 4.0, "low": 0.0, "high": None},
    "player_scoring_distribution": {"point": 8.2, "sd": 5.0, "low": 0.0, "high": None},
    "team_game_distribution": {"point": 82.0, "sd": 10.0, "low": TEAM_POINTS_FLOOR,
                               "high": None},
}

#: the canonical positional p_active feature order (identical to the v3/v4 record)
P_ACTIVE_FEATURES = [
    "p_plays_prior", "min_ewma", "started_last", "start_share_l5",
    "played_last_team_game", "played_share_l10_team_games",
    "days_since_last_appearance", "games_missed_streak",
    "prev_dnp_cd", "prev_dnp_inj", "prev_dnp_nwt", "returning_flag",
    "player_gp_season", "team_gp_season",
]
DAYS_CAP, MISS_CAP = 45.0, 20.0


class ObligationOrderError(RuntimeError):
    """Raised when two obligations in a player-season cannot be distinguished."""


# --------------------------------------------------------------------------
# 1. split context — makes contaminated selection unrepresentable
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class SplitContext:
    """Named index segments, with a guard every selection call must pass.

    v3 returned disjoint arrays and trusted callers. That is not the same as
    making leakage impossible: a tuner handed calibration rows would have
    happily used them. Here every selection API takes the context and calls
    `require_tuning`, so a contaminated call raises instead of returning a
    plausible number.
    """
    tuning_idx: np.ndarray
    calibration_idx: np.ndarray
    test_idx: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    degenerate: bool = False
    reason: str = ""
    label: str = ""

    def __post_init__(self) -> None:
        for a, b, n in ((self.tuning_idx, self.calibration_idx, "tuning/calibration"),
                        (self.tuning_idx, self.test_idx, "tuning/test"),
                        (self.calibration_idx, self.test_idx, "calibration/test")):
            if len(np.intersect1d(a, b)):
                raise SelectionLeakage(f"{n} segments overlap in {self.label or 'split'}")

    def require_tuning(self, idx) -> np.ndarray:
        """Assert `idx` lies entirely inside the tuning segment, or raise."""
        idx = np.asarray(idx)
        forbidden = np.intersect1d(idx, np.concatenate([self.calibration_idx,
                                                        self.test_idx]))
        if len(forbidden):
            raise SelectionLeakage(
                f"selection touched {len(forbidden)} calibration/test rows "
                f"(e.g. {forbidden[:3].tolist()}) in {self.label or 'split'}")
        outside = np.setdiff1d(idx, self.tuning_idx)
        if len(outside):
            raise SelectionLeakage(
                f"selection touched {len(outside)} rows outside the tuning segment "
                f"in {self.label or 'split'}")
        return idx

    def mask_to_tuning(self, mask: pd.Series) -> np.ndarray:
        """Resolve a boolean mask to indices and validate it against tuning."""
        idx = np.asarray(mask[mask.astype(bool)].index)
        return self.require_tuning(idx)


def _cut_dates(dates: list, n_tail: int) -> tuple[list, list]:
    return (dates[:-n_tail], dates[-n_tail:]) if n_tail else (dates, [])


def player_split(df: pd.DataFrame, *, date_col: str = "game_date",
                 label: str = "player") -> SplitContext:
    """Tuning prefix / calibration tail, cut on DISTINCT dates."""
    if len(df) == 0:
        return SplitContext(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                            degenerate=True, reason="empty window", label=label)
    dates = sorted(pd.unique(df[date_col]))
    n_tail = int(np.floor(len(dates) * PLAYER_TAIL_FRACTION))
    if len(dates) < MIN_TUNING_DATES + MIN_CALIBRATION_DATES or n_tail < MIN_CALIBRATION_DATES:
        return SplitContext(np.asarray(df.index), np.array([], dtype=np.int64),
                            degenerate=True,
                            reason=f"{len(dates)} distinct dates; need "
                                   f"{MIN_TUNING_DATES}+{MIN_CALIBRATION_DATES}",
                            label=label)
    tune_d, cal_d = _cut_dates(dates, n_tail)
    m = df[date_col].isin(tune_d)
    return SplitContext(np.asarray(df.index[m]), np.asarray(df.index[~m]), label=label)


@dataclass(frozen=True)
class TeamSplit:
    t1: np.ndarray
    t2: np.ndarray
    t3: np.ndarray
    t1_dates: list
    t2_dates: list
    t3_dates: list
    degenerate: bool = False
    reason: str = ""

    def context_for_alpha(self) -> SplitContext:
        """Channel-α selection may see T1 only; T2 and T3 are off limits."""
        return SplitContext(self.t1, self.t2, self.t3, self.degenerate,
                            self.reason, "team:T1")

    def context_for_calibration_map(self) -> SplitContext:
        """The calibration map is fitted on T2 only; T3 must stay untouched."""
        return SplitContext(self.t2, self.t3, self.t1, self.degenerate,
                            self.reason, "team:T2")


def team_split(df: pd.DataFrame, *, date_col: str = "game_date") -> TeamSplit:
    """Three chronological segments cut on DISTINCT DATES.

    Cutting on dates — not team-game rows — is what keeps **both rows of a game**
    and **every game on a date** inside exactly one segment. A row-based cut let
    one team's outcome sit in the segment that fits the other team's calibration
    map.

    Rounding is frozen: `n_t3 = floor(n*0.25)`, `n_t2 = floor(n*0.25)`,
    `n_t1 = n - n_t2 - n_t3` (T1 absorbs the remainder).
    """
    empty = np.array([], dtype=np.int64)
    if len(df) == 0:
        return TeamSplit(empty, empty, empty, [], [], [], True, "empty window")

    dates = sorted(pd.unique(df[date_col]))
    n = len(dates)
    n_t3 = int(np.floor(n * TEAM_T3_FRACTION))
    n_t2 = int(np.floor(n * TEAM_T2_FRACTION))
    n_t1 = n - n_t2 - n_t3

    if n_t1 < MIN_T1_DATES or n_t2 < MIN_T2_DATES or n_t3 < MIN_T3_DATES:
        return TeamSplit(np.asarray(df.index), empty, empty, dates, [], [], True,
                         f"{n} distinct dates -> T1={n_t1}, T2={n_t2}, T3={n_t3}; "
                         f"need {MIN_T1_DATES}/{MIN_T2_DATES}/{MIN_T3_DATES}")

    d1, d2, d3 = dates[:n_t1], dates[n_t1:n_t1 + n_t2], dates[n_t1 + n_t2:]
    in1, in2, in3 = (df[date_col].isin(d1), df[date_col].isin(d2), df[date_col].isin(d3))
    return TeamSplit(np.asarray(df.index[in1]), np.asarray(df.index[in2]),
                     np.asarray(df.index[in3]), list(d1), list(d2), list(d3))


# --------------------------------------------------------------------------
# 2. deterministic obligation ordering, fail-closed on ties
# --------------------------------------------------------------------------

def order_obligations(df: pd.DataFrame, *, player_col: str = "player_id",
                      season_col: str = "season",
                      cutoff_col: str = "forecast_cutoff",
                      game_col: str = "game_id") -> pd.DataFrame:
    """Order candidate obligations by (forecast_cutoff, game_id) within
    player-season, and refuse to proceed on indistinguishable duplicates.

    Leaving the order to however the frame arrived would make every shifted
    feature depend on input order — reproducible only by accident.
    """
    for c in (player_col, season_col, cutoff_col, game_col):
        if c not in df.columns:
            raise ObligationOrderError(f"cannot order obligations: missing {c!r}")

    dup = df.duplicated(subset=[player_col, season_col, cutoff_col, game_col], keep=False)
    if bool(dup.any()):
        ex = df.loc[dup, [player_col, season_col, cutoff_col, game_col]].head(3)
        raise ObligationOrderError(
            f"{int(dup.sum())} indistinguishable candidate obligations "
            f"(same player, season, forecast_cutoff and game_id):\n{ex.to_string()}")

    return df.sort_values([player_col, season_col, cutoff_col, game_col],
                          kind="mergesort")


# --------------------------------------------------------------------------
# 3. prefix-only statistics
# --------------------------------------------------------------------------

def active_shifted_ewma(frame: pd.DataFrame, value: pd.Series, alpha: float, *,
                        active_col: str = "appeared", player_col: str = "player_id",
                        season_col: str = "season") -> pd.Series:
    """Shifted EWMA over the ACTIVE subsequence only, aligned to every row.

    The conditional targets are conditional **on activity**, so their history
    must be the history of *active* games. Running the EWMA over all obligations
    lets a DNP row's recorded outcome (a zero) move the estimate — which made an
    inactive row's outcome change the selected conditional alphas, exactly what
    the target-specific masks are supposed to prevent.

    The value is shifted inside the active subsequence, then carried forward to
    intervening inactive rows, so it is strictly as-of: no row ever reads its
    own outcome or any later one, and inactive outcomes are never read at all.
    """
    d = frame.sort_values([player_col, season_col], kind="mergesort")
    act = d[active_col].astype(bool)
    keys = [d[player_col], d[season_col]]
    v = value.reindex(d.index).astype(float).where(act)

    post = v.groupby(keys, sort=False).transform(
        lambda s: s.dropna().ewm(alpha=alpha, adjust=True).mean().reindex(s.index))
    shifted = post.where(act).groupby(keys, sort=False).shift(1)
    filled = shifted.groupby(keys, sort=False).ffill()
    return filled.reindex(frame.index)


def active_shifted_ratio_ewma(frame: pd.DataFrame, num: pd.Series, den: pd.Series,
                              alpha: float, scale: float = 36.0, **kw) -> pd.Series:
    """Shifted ratio-of-EWMAs over the ACTIVE subsequence only.

    A zero denominator becomes NaN and routes the row to the declared fallback,
    never a silent zero.
    """
    n = active_shifted_ewma(frame, num, alpha, **kw)
    q = active_shifted_ewma(frame, den, alpha, **kw)
    return (n / q.replace(0.0, np.nan)) * scale


def prefix_mean(values: pd.Series, ctx: SplitContext, mask: pd.Series) -> float:
    """Mean over TUNING rows only, through the leakage guard.

    Used for the `p_active` base rate and for every target's fallback mean, so
    calibration-tail and outer-test outcomes cannot reach either.
    """
    idx = ctx.mask_to_tuning(mask)
    v = values.reindex(idx).astype(float)
    v = v[np.isfinite(v)]
    return float(v.mean()) if len(v) else float("nan")


# --------------------------------------------------------------------------
# 4. dispersion — nonpositive sd is INSUFFICIENT, not a value
# --------------------------------------------------------------------------

def dispersion(resid: np.ndarray, *, min_resid: int) -> tuple[float, np.ndarray, str]:
    """(sd, quantile offsets, method), failing closed on a degenerate pool.

    v3 accepted any finite sd. A **constant** residual pool is finite and gives
    `sd == 0`, which the contract forbids (`pred_sd > 0`) — so it must be
    treated as insufficient and routed to the declared fallback, not emitted.
    """
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
# 5. Stage-A features, standardisation, IRLS logistic, λ selection
# --------------------------------------------------------------------------

def stage_a_features(df: pd.DataFrame, hist: pd.DataFrame, base_rate: float) -> pd.DataFrame:
    """The 14 canonical features, in canonical order, with declared defaults."""
    X = pd.DataFrame(index=df.index)
    X["p_plays_prior"] = hist["p_plays_prior"].where(hist["has_prior_obligation"], base_rate)
    X["min_ewma"] = df.get("min_ewma", pd.Series(0.0, index=df.index)).fillna(0.0)
    X["started_last"] = df.get("started_last", pd.Series(0.0, index=df.index)).fillna(0.0)
    X["start_share_l5"] = df.get("start_share_l5", pd.Series(0.0, index=df.index)).fillna(0.0)
    X["played_last_team_game"] = df.get("played_last_team_game",
                                        pd.Series(0.0, index=df.index)).fillna(0.0)
    X["played_share_l10_team_games"] = df.get(
        "played_share_l10_team_games", pd.Series(0.0, index=df.index)).fillna(0.0)
    X["days_since_last_appearance"] = df.get(
        "days_since_last_appearance", pd.Series(DAYS_CAP, index=df.index)
    ).fillna(DAYS_CAP).clip(upper=DAYS_CAP)
    X["games_missed_streak"] = df.get(
        "games_missed_streak", pd.Series(0.0, index=df.index)).fillna(0.0).clip(upper=MISS_CAP)
    for c in ("prev_dnp_cd", "prev_dnp_inj", "prev_dnp_nwt", "returning_flag"):
        X[c] = df.get(c, pd.Series(0.0, index=df.index)).fillna(0.0)
    X["player_gp_season"] = hist["n_prior_appearances"].astype(float)
    X["team_gp_season"] = df.get("team_gp_season",
                                 pd.Series(0.0, index=df.index)).fillna(0.0)
    return X[P_ACTIVE_FEATURES].astype(float)


class Standardizer:
    def __init__(self, X: pd.DataFrame):
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0, ddof=0)
        self.keep = self.std[self.std > 1e-12].index.tolist()
        self.dropped = [c for c in X.columns if c not in self.keep]

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        Z = (X[self.keep] - self.mean[self.keep]) / self.std[self.keep]
        return Z.to_numpy(dtype=float)


def logistic_fit(Z: np.ndarray, y: np.ndarray, lam: float,
                 max_iter: int = 100, tol: float = 1e-9) -> np.ndarray:
    n, p = Z.shape
    X1 = np.hstack([np.ones((n, 1)), Z])
    beta = np.zeros(p + 1)
    ybar = max(float(np.mean(y)), 1e-6)
    beta[0] = np.log(ybar / max(1 - ybar, 1e-6))
    pen = lam * np.eye(p + 1)
    pen[0, 0] = 0.0
    for _ in range(max_iter):
        eta = np.clip(X1 @ beta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        W = np.maximum(mu * (1 - mu), 1e-10)
        grad = X1.T @ (mu - y) + pen @ beta
        H = (X1 * W[:, None]).T @ X1 + pen
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        beta = beta - step
        if np.max(np.abs(step)) < tol:
            break
    return beta


def logistic_predict(Z: np.ndarray, beta: np.ndarray) -> np.ndarray:
    eta = np.clip(np.hstack([np.ones((Z.shape[0], 1)), Z]) @ beta, -30, 30)
    return 1.0 / (1.0 + np.exp(-eta))


def select_lambda(X: pd.DataFrame, y: pd.Series, ctx: SplitContext,
                  mask: pd.Series) -> tuple[float, bool]:
    """Brier-minimising λ on an inner cut of the TUNING segment. Ties → smallest."""
    idx = ctx.mask_to_tuning(mask)
    if len(idx) < 20 or len(np.unique(y.reindex(idx))) < 2:
        return DEFAULT_LAMBDA, True
    cut = int(len(idx) * 0.75)
    tr, va = idx[:cut], idx[cut:]
    if len(va) < 5 or len(np.unique(y.reindex(tr))) < 2:
        return DEFAULT_LAMBDA, True
    best, best_loss = DEFAULT_LAMBDA, np.inf
    for lam in LAMBDA_GRID:                        # ascending; first minimum wins
        std = Standardizer(X.loc[tr])
        beta = logistic_fit(std.transform(X.loc[tr]), y.reindex(tr).to_numpy(float), lam)
        p = logistic_predict(std.transform(X.loc[va]), beta)
        loss = float(np.mean((y.reindex(va).to_numpy(float) - np.clip(p, 0, 1)) ** 2))
        if loss < best_loss - 1e-15:
            best, best_loss = lam, loss
    return best, False


# --------------------------------------------------------------------------
# 6. ordered α selection, split-bound
# --------------------------------------------------------------------------

def select_alpha_bound(predict_fn, y: pd.Series, ctx: SplitContext,
                       mask: pd.Series, grid=ALPHA_GRID) -> tuple[float, bool, str]:
    """MAE-minimising α over TUNING rows only. Ties → smallest α."""
    idx = ctx.mask_to_tuning(mask)
    if len(idx) < 1:
        return DEFAULT_ALPHA, True, ""
    best, best_loss = None, np.inf
    for a in grid:                                  # ascending; first minimum wins
        pred = predict_fn(a).reindex(idx)
        err = (pred - y.reindex(idx)).abs()
        err = err[np.isfinite(err)]
        loss = float(err.mean()) if len(err) else np.inf
        if loss < best_loss - 1e-15:
            best, best_loss = a, loss
    if best is None:
        return DEFAULT_ALPHA, True, ""
    boundary = "lower" if best == grid[0] else "upper" if best == grid[-1] else ""
    return best, False, boundary


# --------------------------------------------------------------------------
# 7. emission helpers
# --------------------------------------------------------------------------

def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True,
                                     separators=(",", ":"), default=str).encode()).hexdigest()


def emit_rows(uni: pd.DataFrame, target: str, point: pd.Series, sd: pd.Series,
              offsets: np.ndarray | None, *, arm_id: str, fold_id: str,
              config_hash: str, model_hash: str, snapshot_hash: str,
              is_fallback: pd.Series, is_cold_start: pd.Series,
              n_prior: pd.Series, exclusion: pd.Series,
              low: float | None, high: float | None,
              want_quantiles: bool) -> pd.DataFrame:
    """Build contract-schema rows for EVERY obligation, predicted or excluded."""
    out = pd.DataFrame({
        "row_uid": uni["row_uid"].to_numpy(),
        "target_key": target, "arm_id": arm_id, "fold_id": fold_id,
        "forecast_cutoff": uni["forecast_cutoff"].to_numpy(),
        "pred_point": point.to_numpy(dtype=float),
        "pred_sd": sd.to_numpy(dtype=float) if sd is not None else np.nan,
        "is_fallback": is_fallback.to_numpy(),
        "is_cold_start": is_cold_start.to_numpy(),
        "n_prior_games": n_prior.to_numpy(),
        "feature_asof": uni["feature_asof"].to_numpy(),
        "model_hash": model_hash, "config_hash": config_hash,
        "data_snapshot_hash": snapshot_hash,
        "exclusion_reason": exclusion.to_numpy(),
    })
    for q in ("pred_q05", "pred_q25", "pred_q50", "pred_q75", "pred_q95"):
        out[q] = np.nan
    if want_quantiles and offsets is not None and np.all(np.isfinite(offsets)):
        q = emit_quantiles(out["pred_point"].to_numpy(dtype=float), offsets,
                           low=low, high=high)
        for i, name in enumerate(("pred_q05", "pred_q25", "pred_q50",
                                  "pred_q75", "pred_q95")):
            out[name] = q[:, i]

    if low is not None:
        out.loc[out.exclusion_reason.isna(), "pred_point"] = \
            out.loc[out.exclusion_reason.isna(), "pred_point"].clip(lower=low)
    if high is not None:
        out.loc[out.exclusion_reason.isna(), "pred_point"] = \
            out.loc[out.exclusion_reason.isna(), "pred_point"].clip(upper=high)

    excl = out.exclusion_reason.notna()
    out.loc[excl, ["pred_point", "pred_sd"]] = np.nan
    return out


def exclusion_crosstab(pred: pd.DataFrame, uni: pd.DataFrame) -> dict:
    """Cross-tab every excluded row by `in_target_box` and `appeared`.

    Standing obligation: if exclusion predicts non-appearance, the run is VOID —
    that is outcome selection wearing a coverage costume.
    """
    j = pred[["row_uid", "exclusion_reason"]].merge(
        uni[["row_uid"] + [c for c in ("in_target_box", "appeared") if c in uni.columns]],
        on="row_uid", how="left")
    ex = j[j.exclusion_reason.notna()]
    out = {"n_excluded": int(len(ex)), "by_reason":
           ex.exclusion_reason.value_counts().to_dict()}
    if "appeared" in j.columns and len(ex):
        out["excluded_appeared_rate"] = float(ex["appeared"].astype(float).mean())
        out["overall_appeared_rate"] = float(j["appeared"].astype(float).mean())
        out["outcome_selection_alarm"] = bool(out["excluded_appeared_rate"] == 0.0
                                              and out["n_excluded"] > 0)
    else:
        out["outcome_selection_alarm"] = False
    return out
