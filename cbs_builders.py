#!/usr/bin/env python3
"""cbs_builders.py — the executable core of `contract_baseline_suite_v3`.

WHAT THIS IS
------------
`contract_baseline_suite_v1` was frozen but not executable; v2 stated the
missing rules but still described them only in prose. This module makes the
parts that are easy to get subtly wrong **executable and testable on synthetic
data**, so the specification is demonstrably implementable before any real
prediction is generated.

**It generates no forecast.** There is no I/O here: no contract parquet is read,
no fitted artifact is written, no accuracy or coverage number is produced. Every
function is a pure transformation over frames the caller supplies, and
`tests/test_cbs_builders.py` exercises them on toy data only.

THE THREE THINGS THIS EXISTS TO GET RIGHT
-----------------------------------------
1. **Disjoint selection and calibration.** v2 derived dispersion from the same
   inner validation segments that selected the hyperparameters, so the residual
   spread was conditioned on outcomes already used to pick the estimator, and
   intervals would be optimistically narrow. v3 cuts the training window into a
   *tuning prefix* and a **disjoint chronological calibration tail** that no
   selection step may touch. `split_tuning_calibration` enforces it.

2. **Candidate-obligation history.** A player's play history must be built over
   prior **contract candidate obligations**, not prior appearances. A player who
   was a candidate 4 times and played 0 of them has history `0/4` — strong
   evidence of non-play — which is a completely different state from a player
   with no prior obligations at all, who has no evidence and must take the
   declared default. Conflating them was the defect. `prior_candidate_history`
   keeps `n_prior_candidate_games` and `n_prior_appearances` separate.

3. **Ordered, masked tuning.** The legs are not independent: attempts and points
   are compositions over the *selected* minutes leg, so minutes must be selected
   first and then held fixed. Each target also scores on its own mask.
   `select_alpha_ordered` implements that order explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# frozen constants -- these mirror the registered v3 config exactly
# ---------------------------------------------------------------------------

#: alpha grid for every rate estimator (minutes, attempts, points, team channels)
ALPHA_GRID: tuple[float, ...] = (0.01, 0.02, 0.03, 0.05, 0.075,
                                 0.10, 0.15, 0.20, 0.30, 0.40, 0.50)

#: lambda grid for the p_active logistic: round(np.logspace(-2, 4, 13), 6)
LAMBDA_GRID: tuple[float, ...] = (0.01, 0.031623, 0.1, 0.316228, 1.0, 3.162278,
                                  10.0, 31.622777, 100.0, 316.227766, 1000.0,
                                  3162.27766, 10000.0)

#: fraction of the outer training window's DISTINCT DATES reserved, at the end,
#: for dispersion calibration. Nothing in this tail may inform any selection.
CALIBRATION_TAIL_FRACTION: float = 0.25

#: minimum distinct dates required on each side of the split
MIN_TUNING_DATES: int = 8
MIN_CALIBRATION_DATES: int = 4

#: minimum residuals before empirical quantiles are trusted
MIN_RESID_PLAYER: int = 200
MIN_RESID_TEAM: int = 30

#: declared defaults when the low-data rule fires
DEFAULT_ALPHA: float = 0.10
DEFAULT_LAMBDA: float = 1.0

#: team points support floor, frozen numerically
TEAM_POINTS_FLOOR: float = 1e-6

#: contract quantile levels
QUANTILE_LEVELS: tuple[float, ...] = (0.05, 0.25, 0.50, 0.75, 0.95)

#: Gaussian fallback z-scores for QUANTILE_LEVELS
QUANTILE_Z: tuple[float, ...] = (-1.6448536269514722, -0.6744897501960817, 0.0,
                                 0.6744897501960817, 1.6448536269514722)


class SelectionLeakage(RuntimeError):
    """Raised when an outcome would serve both selection and calibration."""


# ---------------------------------------------------------------------------
# 1. disjoint chronological split
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrainSplit:
    """A training window cut into a tuning prefix and a calibration tail."""
    tuning_idx: np.ndarray
    calibration_idx: np.ndarray
    tuning_dates: list
    calibration_dates: list
    boundary_date: object
    degenerate: bool = False
    reason: str = ""

    def assert_disjoint(self) -> None:
        if set(self.tuning_dates) & set(self.calibration_dates):
            raise SelectionLeakage("tuning and calibration share a date")
        if len(np.intersect1d(self.tuning_idx, self.calibration_idx)):
            raise SelectionLeakage("tuning and calibration share a row")


def split_tuning_calibration(df: pd.DataFrame, *, date_col: str = "game_date",
                             tail_fraction: float = CALIBRATION_TAIL_FRACTION,
                             min_tuning_dates: int = MIN_TUNING_DATES,
                             min_calibration_dates: int = MIN_CALIBRATION_DATES,
                             ) -> TrainSplit:
    """Cut one outer training window into a tuning prefix and calibration tail.

    The cut is on **distinct dates**, not rows, so a single heavy slate cannot
    straddle the boundary: every row of a given date lands on exactly one side.

    Degenerate windows (too few dates) are reported, never silently split. The
    caller then falls back to declared constants -- it must not quietly reuse
    tuning outcomes for dispersion.
    """
    if len(df) == 0:
        return TrainSplit(np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                          [], [], None, True, "empty training window")

    dates = sorted(pd.unique(df[date_col]))
    n_tail = int(np.floor(len(dates) * tail_fraction))

    if len(dates) < (min_tuning_dates + min_calibration_dates) \
            or n_tail < min_calibration_dates:
        return TrainSplit(np.asarray(df.index), np.array([], dtype=np.int64),
                          dates, [], None, True,
                          f"only {len(dates)} distinct dates; need "
                          f"{min_tuning_dates}+{min_calibration_dates}")

    tuning_dates, calibration_dates = dates[:-n_tail], dates[-n_tail:]
    tmask = df[date_col].isin(tuning_dates)
    split = TrainSplit(
        tuning_idx=np.asarray(df.index[tmask]),
        calibration_idx=np.asarray(df.index[~tmask]),
        tuning_dates=list(tuning_dates),
        calibration_dates=list(calibration_dates),
        boundary_date=calibration_dates[0],
    )
    split.assert_disjoint()
    return split


# ---------------------------------------------------------------------------
# 2. candidate-obligation history
# ---------------------------------------------------------------------------

def prior_candidate_history(df: pd.DataFrame, *, player_col: str = "player_id",
                            season_col: str = "season",
                            date_col: str = "game_date",
                            appeared_col: str = "appeared") -> pd.DataFrame:
    """Strictly-prior play history over CONTRACT CANDIDATE OBLIGATIONS.

    Returns `n_prior_candidate_games`, `n_prior_appearances` and `p_plays_prior`
    per row, all shifted so the current row never informs its own features.

    The distinction that matters: a candidate with `k > 0` prior obligations and
    zero appearances has `p_plays_prior = 0/k`, which is real evidence. Only a
    candidate with **no prior obligations at all** has no evidence, and only
    that row may take the training-fold base rate.
    """
    d = df.sort_values([player_col, season_col, date_col], kind="mergesort")
    g = d.groupby([player_col, season_col], sort=False)[appeared_col]

    n_prior = g.cumcount()
    appeared = d[appeared_col].astype(float)
    n_prior_app = g.transform(lambda s: s.astype(float).cumsum().shift(1)).fillna(0.0)

    out = pd.DataFrame(index=d.index)
    out["n_prior_candidate_games"] = n_prior.astype(int)
    out["n_prior_appearances"] = n_prior_app.astype(int)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["p_plays_prior"] = np.where(n_prior > 0, n_prior_app / n_prior, np.nan)
    # NaN marks "no prior obligation" -- the ONLY case allowed the base-rate
    # default. It is deliberately not filled here.
    out["has_prior_obligation"] = out["n_prior_candidate_games"] > 0
    del appeared
    return out.reindex(df.index)


def apply_base_rate_default(hist: pd.DataFrame, base_rate: float) -> pd.Series:
    """Fill `p_plays_prior` ONLY where there is no prior candidate obligation."""
    p = hist["p_plays_prior"].copy()
    fill = ~hist["has_prior_obligation"]
    p.loc[fill] = base_rate
    return p


# ---------------------------------------------------------------------------
# 3. shifted estimators (mirrors features.common, restated so tests are pure)
# ---------------------------------------------------------------------------

def shifted_ewma(df: pd.DataFrame, value: pd.Series, alpha: float, *,
                 player_col: str = "player_id", season_col: str = "season",
                 date_col: str = "game_date") -> pd.Series:
    """Shifted within-(player, season) EWMA, pandas `adjust=True` convention."""
    d = df.sort_values([player_col, season_col, date_col], kind="mergesort")
    v = value.reindex(d.index).astype(float)
    e = v.groupby([d[player_col], d[season_col]], sort=False).transform(
        lambda s: s.ewm(alpha=alpha, adjust=True).mean())
    return e.groupby([d[player_col], d[season_col]], sort=False).shift(1).reindex(df.index)


def shifted_ratio_ewma(df: pd.DataFrame, num: pd.Series, den: pd.Series,
                       alpha: float, scale: float = 36.0, **kw) -> pd.Series:
    """Shifted ratio-of-EWMAs -- EWMA(num)/EWMA(den) * scale.

    A zero denominator becomes NaN and must route the row to the cold-start
    fallback; it must never become a silent zero.
    """
    d = df.sort_values([kw.get("player_col", "player_id"),
                        kw.get("season_col", "season"),
                        kw.get("date_col", "game_date")], kind="mergesort")
    keys = [d[kw.get("player_col", "player_id")], d[kw.get("season_col", "season")]]
    n = num.reindex(d.index).astype(float).groupby(keys, sort=False).transform(
        lambda s: s.ewm(alpha=alpha, adjust=True).mean())
    q = den.reindex(d.index).astype(float).groupby(keys, sort=False).transform(
        lambda s: s.ewm(alpha=alpha, adjust=True).mean())
    ratio = n / q.replace(0.0, np.nan)
    return (ratio.groupby(keys, sort=False).shift(1) * scale).reindex(df.index)


# ---------------------------------------------------------------------------
# 4. ordered, masked alpha selection
# ---------------------------------------------------------------------------

@dataclass
class AlphaSelection:
    alpha: float
    loss: float
    curve: list[tuple[float, float]] = field(default_factory=list)
    used_default: bool = False
    boundary: str = ""          # "lower" / "upper" / "" -- reported, never fixed


def select_alpha(predict_fn, y: pd.Series, mask: pd.Series, *,
                 grid: tuple[float, ...] = ALPHA_GRID,
                 min_rows: int = 1) -> AlphaSelection:
    """Pick alpha by MAE on `mask` rows. Ties go to the SMALLEST alpha.

    `predict_fn(alpha) -> Series`. The grid is evaluated in ascending order and
    the first minimum wins, which is `idxmin`'s first-occurrence rule made
    explicit rather than incidental.
    """
    m = mask.astype(bool)
    if int(m.sum()) < min_rows:
        return AlphaSelection(DEFAULT_ALPHA, float("nan"), [], True, "")

    curve: list[tuple[float, float]] = []
    for a in grid:                                   # ascending by construction
        pred = predict_fn(a)
        err = (pred[m] - y[m]).abs()
        err = err[np.isfinite(err)]
        curve.append((a, float(err.mean()) if len(err) else float("inf")))

    best_alpha, best_loss = min(curve, key=lambda kv: kv[1])
    for a, l in curve:                               # first minimum == smallest
        if l == best_loss:
            best_alpha = a
            break

    boundary = ("lower" if best_alpha == grid[0]
                else "upper" if best_alpha == grid[-1] else "")
    return AlphaSelection(best_alpha, best_loss, curve, False, boundary)


def select_alpha_ordered(builders: dict, y: dict, masks: dict) -> dict:
    """The frozen tuning ORDER. The legs are not independent.

    1. minutes alpha, by conditional-minutes MAE on active rows;
    2. attempts-rate alpha, by raw conditional-FGA MAE **after composition**,
       with the minutes leg held fixed at the alpha chosen in step 1;
    3. points-rate alpha, by conditional-points MAE after composition, with the
       **same** fixed minutes leg.

    Selecting attempts or points against a floating minutes leg would let a
    rate alpha compensate for a minutes error, which is not what either
    parameter means.
    """
    out: dict[str, AlphaSelection] = {}
    out["minutes"] = select_alpha(builders["minutes"], y["minutes"], masks["minutes"])
    fixed = out["minutes"].alpha

    for leg in ("attempts", "points"):
        if leg in builders:
            out[leg] = select_alpha(
                lambda a, _leg=leg: builders[_leg](a, fixed), y[leg], masks[leg])
    out["_minutes_alpha_held_fixed_at"] = fixed          # provenance, not a knob
    return out


# ---------------------------------------------------------------------------
# 5. dispersion from the calibration tail only
# ---------------------------------------------------------------------------

def dispersion_from_residuals(resid: np.ndarray, *, min_resid: int,
                              levels: tuple[float, ...] = QUANTILE_LEVELS,
                              ) -> tuple[float, np.ndarray, str]:
    """(sd, quantile offsets, method) from calibration-tail residuals.

    sd is the sample standard deviation with `ddof=1`. Quantiles are empirical
    (`numpy.quantile`, `method="linear"`, Hyndman-Fan type 7) when there are at
    least `min_resid` residuals, and Gaussian `z * sd` otherwise.
    """
    r = np.asarray(resid, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) < 2:
        return float("nan"), np.full(len(levels), np.nan), "insufficient"

    sd = float(np.std(r, ddof=1))
    if len(r) >= min_resid:
        return sd, np.quantile(r, levels, method="linear"), "empirical"
    return sd, np.asarray(QUANTILE_Z) * sd, "gaussian"


def emit_quantiles(point: np.ndarray, offsets: np.ndarray, *,
                   low: float | None = None, high: float | None = None,
                   ) -> np.ndarray:
    """Point + residual offsets, TRUNCATED to support, THEN monotone-sorted.

    Order matters: truncating after sorting can reintroduce a non-monotone
    sequence, and the contract validator rejects those.
    """
    q = np.asarray(point, dtype=float)[:, None] + np.asarray(offsets, dtype=float)[None, :]
    if low is not None:
        q = np.maximum(q, low)
    if high is not None:
        q = np.minimum(q, high)
    return np.sort(q, axis=1)
