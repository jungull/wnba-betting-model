#!/usr/bin/env python3
"""cluster_bootstrap.py -- game-cluster bootstrap scaffolding (P33 inference block, carried).

Two streams, both cluster-level, both seeded from the frozen manifest:

  * TEST bootstrap (B = 10,000): resample a fold's TEST game-clusters with replacement, carrying
    BOTH team-rows of every sampled game; never resample team-rows independently. Draw b's
    cluster index set is a pure function of (fold_id, b), so it is IDENTICAL for the arm, its
    K0_MATCHED null, and every other arm evaluated in that fold (paired comparisons).

  * TRAINING refit bootstrap (B = 2,000): resample TRAINING game-clusters with replacement,
    refit BOTH members per draw, percentile 95% coefficient intervals. K7 symmetric NA rule
    (P35 estimator_symmetry_rules.bootstrap_draw_rule): a draw in which (a) any treatment or
    nuisance INDICATOR column of either member's design is constant on the resampled rows, or
    (b) either member's IRLS refit fails to converge within the frozen cap (including singular /
    non-finite refits, which are the same failure observed earlier), is recorded NA for BOTH
    members; NA draws are excluded from BOTH interval constructions and their count is reported.
"""
from __future__ import annotations

import numpy as np

import quasipoisson_irls as qp
from runner_constants import (B_TEST_BOOTSTRAP, B_TRAIN_REFIT, COEF_INTERVAL_LEVEL,
                              SEED_PURPOSE_TEST, SEED_PURPOSE_TRAIN)
from seed_manifest import rng_for


def cluster_row_map(cluster_ids: np.ndarray) -> tuple[np.ndarray, list[np.ndarray]]:
    """Deterministic cluster ordering (sorted unique) -> list of row-index arrays per cluster."""
    cl = np.asarray(cluster_ids)
    uniq = np.unique(cl)                      # sorted -- deterministic across processes
    rows = [np.flatnonzero(cl == u) for u in uniq]
    return uniq, rows


def draw_row_indices(rows_per_cluster: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    """One bootstrap draw: sample n_clusters cluster slots with replacement and concatenate ALL
    rows of each sampled cluster (games are never split)."""
    k = len(rows_per_cluster)
    picks = rng.integers(0, k, size=k)
    return np.concatenate([rows_per_cluster[i] for i in picks])


def test_bootstrap_draw_indices(fold_id: str, b: int,
                                rows_per_cluster: list[np.ndarray]) -> np.ndarray:
    return draw_row_indices(rows_per_cluster, rng_for(SEED_PURPOSE_TEST, fold_id, b))


def paired_delta_mae_draws(fold_id: str, abs_err_arm: np.ndarray, abs_err_null: np.ndarray,
                           cluster_ids: np.ndarray,
                           n_draws: int = B_TEST_BOOTSTRAP) -> np.ndarray:
    """delta_MAE_b = MAE(null) - MAE(arm) on the SAME resampled test cluster set, per draw.

    `abs_err_*` are per-row absolute errors on the fold's TEST rows (equal row weights).
    Returns the (n_draws,) vector of paired deltas.
    """
    abs_err_arm = np.asarray(abs_err_arm, float)
    abs_err_null = np.asarray(abs_err_null, float)
    if abs_err_arm.shape != abs_err_null.shape:
        raise ValueError("paired draws require identical row sets for arm and null")
    _, rows = cluster_row_map(cluster_ids)
    out = np.empty(n_draws)
    for b in range(n_draws):
        idx = test_bootstrap_draw_indices(fold_id, b, rows)
        out[b] = float(np.mean(abs_err_null[idx]) - np.mean(abs_err_arm[idx]))
    return out


def two_sided_bootstrap_p(deltas: np.ndarray) -> float:
    """Deterministic two-sided operationalisation, recorded in RUNNER_INTERFACE.md section 4."""
    d = np.asarray(deltas, float)
    n = d.size
    lo = (1 + int(np.sum(d <= 0.0))) / (n + 1)
    hi = (1 + int(np.sum(d >= 0.0))) / (n + 1)
    return float(min(1.0, 2.0 * min(lo, hi)))


def _member_draw_ok(X: np.ndarray, col_names: list[str], indicator_cols: set[str],
                    idx: np.ndarray) -> bool:
    """K7 clause (a) for one member: every declared indicator column among the member's design
    columns must be non-constant on the resampled rows. Non-indicator columns are not tested --
    the frozen rule names indicator columns; the explicit intercept column is structural and is
    never listed as an indicator."""
    for j, name in enumerate(col_names):
        if name in indicator_cols:
            v = X[idx, j]
            if v.size and np.all(v == v[0]):
                return False
    return True


def train_refit_bootstrap(fold_id: str, *,
                          X_arm: np.ndarray, arm_cols: list[str],
                          X_null: np.ndarray, null_cols: list[str],
                          y: np.ndarray, offset: np.ndarray,
                          cluster_ids: np.ndarray, indicator_cols,
                          n_draws: int = B_TRAIN_REFIT,
                          max_iter: int | None = None) -> dict:
    """The frozen training-cluster refit bootstrap for ONE fold, arm and null paired.

    `max_iter` exists ONLY so unit tests can force the non-convergence branch on synthetic
    data; `runner.py` never passes it (the frozen cap governs).
    """
    indicator_cols = set(indicator_cols)
    _, rows = cluster_row_map(cluster_ids)
    kw = {} if max_iter is None else {"max_iter": int(max_iter)}

    betas_arm = np.full((n_draws, X_arm.shape[1]), np.nan)
    betas_null = np.full((n_draws, X_null.shape[1]), np.nan)
    na_mask = np.zeros(n_draws, bool)
    na_reasons: dict[str, int] = {"indicator_constant": 0, "nonconvergence": 0}

    for b in range(n_draws):
        idx = draw_row_indices(rows, rng_for(SEED_PURPOSE_TRAIN, fold_id, b))
        if not (_member_draw_ok(X_arm, arm_cols, indicator_cols, idx)
                and _member_draw_ok(X_null, null_cols, indicator_cols, idx)):
            na_mask[b] = True
            na_reasons["indicator_constant"] += 1
            continue
        fa = qp.fit(X_arm[idx], y[idx], offset[idx], column_names=tuple(arm_cols), **kw)
        fn = qp.fit(X_null[idx], y[idx], offset[idx], column_names=tuple(null_cols), **kw)
        if not (fa.converged and fn.converged):
            na_mask[b] = True                     # NA for BOTH members, symmetrically
            na_reasons["nonconvergence"] += 1
            continue
        if fa.beta.size:
            betas_arm[b] = fa.beta
        if fn.beta.size:
            betas_null[b] = fn.beta

    ok = ~na_mask
    alpha = 1.0 - COEF_INTERVAL_LEVEL

    def _intervals(betas: np.ndarray, cols: list[str]) -> dict:
        out = {}
        for j, name in enumerate(cols):
            v = betas[ok, j]
            v = v[np.isfinite(v)]
            if v.size == 0:
                out[name] = {"lo": None, "hi": None, "n_effective": 0}
            else:
                out[name] = {"lo": float(np.quantile(v, alpha / 2)),
                             "hi": float(np.quantile(v, 1 - alpha / 2)),
                             "n_effective": int(v.size)}
        return out

    return {"schema": "p36_train_refit_bootstrap/1", "fold_id": str(fold_id),
            "n_draws": int(n_draws), "interval_level": COEF_INTERVAL_LEVEL,
            "n_na_draws": int(na_mask.sum()), "na_reasons": na_reasons,
            "na_rule": "K7 symmetric: NA for BOTH members; excluded from BOTH intervals",
            "arm_intervals": _intervals(betas_arm, arm_cols),
            "null_intervals": _intervals(betas_null, null_cols)}
