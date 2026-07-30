"""Deterministic evaluation metrics — probability quality is first-class.

Implements the ROADMAP "Metrics" section: score/margin/total MAE and RMSE;
pinball loss on forecast quantiles; CRPS (distributional, for empirical /
ensemble forecasts); cover-probability Brier; log loss; reliability
(calibration) tables; coverage-of-interval checks.

Every function is a pure numpy computation: no randomness, no global state,
NaNs refuse loudly (silently dropping rows is how coverage declines hide —
gate 5 of the standard promotion gate). All are unit-tested against
hand-computed values in tests/test_evalharness.py.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd


def _arr(x, name: str, allow_nan: bool = False) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    if not allow_nan and np.isnan(a).any():
        raise ValueError(
            f"{name} contains {int(np.isnan(a).sum())} NaN(s). The harness "
            "never silently drops rows — resolve missingness explicitly "
            "(no-imputation rule, ROADMAP amended constitution)."
        )
    return a


def _paired(y_true, y_pred, names=("y_true", "y_pred")):
    t = _arr(y_true, names[0])
    p = _arr(y_pred, names[1])
    if t.shape != p.shape:
        raise ValueError(f"shape mismatch: {names[0]} {t.shape} vs {names[1]} {p.shape}")
    if t.size == 0:
        raise ValueError("empty input")
    return t, p


# ---------------------------------------------------------------------------
# point error
# ---------------------------------------------------------------------------

def mae(y_true, y_pred) -> float:
    """Mean absolute error."""
    t, p = _paired(y_true, y_pred)
    return float(np.mean(np.abs(t - p)))


def rmse(y_true, y_pred) -> float:
    """Root mean squared error."""
    t, p = _paired(y_true, y_pred)
    return float(np.sqrt(np.mean((t - p) ** 2)))


# ---------------------------------------------------------------------------
# quantile / distributional
# ---------------------------------------------------------------------------

def pinball_loss(y_true, quantile_preds, quantiles) -> np.ndarray:
    """Pinball (quantile) loss per quantile, averaged over observations.

    quantile_preds: shape (n,) for a single quantile or (n, k) for k quantiles.
    quantiles: length-k array of levels in (0, 1).
    Returns a length-k array (order matches ``quantiles``).
    pinball_tau(y, q) = tau*(y-q) if y >= q else (1-tau)*(q-y).
    """
    q = np.atleast_1d(np.asarray(quantiles, dtype=float))
    if np.any((q <= 0) | (q >= 1)):
        raise ValueError("quantile levels must lie strictly inside (0, 1)")
    t = _arr(y_true, "y_true")
    preds = _arr(quantile_preds, "quantile_preds")
    if preds.ndim == 1:
        preds = preds[:, None]
    if preds.shape != (t.size, q.size):
        raise ValueError(
            f"quantile_preds shape {preds.shape} != (n={t.size}, k={q.size})"
        )
    diff = t[:, None] - preds                      # y - q_hat
    loss = np.where(diff >= 0, q[None, :] * diff, (q[None, :] - 1.0) * diff)
    return loss.mean(axis=0)


def mean_pinball_loss(y_true, quantile_preds, quantiles) -> float:
    """Scalar pinball loss averaged over observations AND quantiles."""
    return float(np.mean(pinball_loss(y_true, quantile_preds, quantiles)))


def crps_ensemble(y_true, samples) -> np.ndarray:
    """Exact CRPS of an empirical/ensemble forecast, per observation.

    samples: shape (n, m) — m ensemble members per observation (equal weight).
    CRPS = E|X - y| - 0.5 * E|X - X'|  (Gneiting & Raftery form), computed
    exactly via the sorted-sample identity (no sampling, fully deterministic).
    Lower is better; reduces to absolute error when m == 1.
    """
    t = _arr(y_true, "y_true")
    x = _arr(samples, "samples")
    if x.ndim == 1:
        x = x[None, :] if t.size == 1 else x[:, None]
    if x.shape[0] != t.size:
        raise ValueError(f"samples first dim {x.shape[0]} != n obs {t.size}")
    m = x.shape[1]
    term1 = np.mean(np.abs(x - t[:, None]), axis=1)
    xs = np.sort(x, axis=1)
    k = np.arange(m, dtype=float)
    # sum_{i<j}(x_(j)-x_(i)) = sum_k x_(k) * (2k - m + 1)   (0-indexed)
    pair_sum = np.sum(xs * (2.0 * k - m + 1.0)[None, :], axis=1)
    term2 = pair_sum / (m * m)                      # = 0.5 * E|X - X'|
    return term1 - term2


def mean_crps(y_true, samples) -> float:
    return float(np.mean(crps_ensemble(y_true, samples)))


# ---------------------------------------------------------------------------
# probability scores
# ---------------------------------------------------------------------------

def _check_binary_probs(y_true, p_pred):
    t = _arr(y_true, "y_true")
    p = _arr(p_pred, "p_pred")
    if t.shape != p.shape:
        raise ValueError(f"shape mismatch {t.shape} vs {p.shape}")
    if not np.all((t == 0) | (t == 1)):
        raise ValueError("y_true must be binary 0/1")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("probabilities must lie in [0, 1]")
    return t, p


def brier_score(y_true, p_pred) -> float:
    """Brier score for binary outcomes (e.g. cover probability)."""
    t, p = _check_binary_probs(y_true, p_pred)
    return float(np.mean((p - t) ** 2))


def log_loss(y_true, p_pred, eps: float = 1e-15) -> float:
    """Binary log loss with probability clipping at ``eps``."""
    t, p = _check_binary_probs(y_true, p_pred)
    p = np.clip(p, eps, 1.0 - eps)
    return float(-np.mean(t * np.log(p) + (1.0 - t) * np.log(1.0 - p)))


def reliability_table(
    y_true,
    p_pred,
    n_bins: int = 10,
    strategy: str = "uniform",
) -> pd.DataFrame:
    """Binned predicted-vs-observed calibration table WITH counts.

    strategy='uniform': n_bins equal-width bins on [0, 1] (empty bins kept,
    n=0 — hiding empty bins hides miscalibration regions).
    strategy='quantile': bins at empirical quantiles of p_pred (all non-empty).
    Columns: bin_low, bin_high, n, mean_predicted, observed_rate, gap.
    """
    t, p = _check_binary_probs(y_true, p_pred)
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    if strategy == "uniform":
        edges = np.linspace(0.0, 1.0, n_bins + 1)
    elif strategy == "quantile":
        edges = np.unique(np.quantile(p, np.linspace(0.0, 1.0, n_bins + 1)))
        if len(edges) < 2:
            edges = np.array([0.0, 1.0])
    else:
        raise ValueError("strategy must be 'uniform' or 'quantile'")
    # right-closed bins, first bin left-closed
    which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    rows = []
    for b in range(len(edges) - 1):
        m = which == b
        n = int(m.sum())
        rows.append({
            "bin_low": float(edges[b]),
            "bin_high": float(edges[b + 1]),
            "n": n,
            "mean_predicted": float(p[m].mean()) if n else np.nan,
            "observed_rate": float(t[m].mean()) if n else np.nan,
        })
    out = pd.DataFrame(rows)
    out["gap"] = out["observed_rate"] - out["mean_predicted"]
    return out


# ---------------------------------------------------------------------------
# interval coverage
# ---------------------------------------------------------------------------

def interval_coverage(
    y_true,
    lower,
    upper,
    nominal: Optional[float] = None,
    tol: Optional[float] = None,
) -> dict:
    """Coverage-of-interval check: share of observations inside [lower, upper].

    Feeds gate 5 territory (coverage and operational reliability maintained)
    and the probabilistic leaderboard. Returns a dict:
      empirical, n, n_covered, nominal, tol, ok
    ``ok`` is None unless both nominal and tol are given, then
    ok = |empirical - nominal| <= tol.
    Raises if any lower > upper (a malformed interval is a bug, not a miss).
    """
    t = _arr(y_true, "y_true")
    lo = _arr(lower, "lower")
    hi = _arr(upper, "upper")
    if not (t.shape == lo.shape == hi.shape):
        raise ValueError("y_true / lower / upper shapes differ")
    if np.any(lo > hi):
        bad = int(np.sum(lo > hi))
        raise ValueError(f"{bad} interval(s) have lower > upper")
    covered = (t >= lo) & (t <= hi)
    emp = float(covered.mean())
    ok = None
    if nominal is not None and tol is not None:
        ok = bool(abs(emp - nominal) <= tol)
    return {
        "empirical": emp,
        "n": int(t.size),
        "n_covered": int(covered.sum()),
        "nominal": nominal,
        "tol": tol,
        "ok": ok,
    }
