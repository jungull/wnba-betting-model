#!/usr/bin/env python3
"""quasipoisson_irls.py -- the frozen estimation objective, as code.

Poisson quasi-likelihood IRLS, log link, additive offset, for every arm and every K0_MATCHED
null identically (P33 inference_spec_gap_resolution.estimation_objective_frozen_here, carried by
P35). Deterministic: no stochastic fitting component exists in this module, and no seed argument
is accepted. Convergence: absolute change in Poisson deviance < 1e-10, max 100 iterations.

INTERCEPT SEMANTICS (P35 no_implementation_default_intercept_invariant): this fitter has NO
intercept option. The design matrix is fitted exactly as supplied; a model has an intercept if
and only if the caller's design carries an explicit column of ones. Nothing here can add one.

Quasi-likelihood note (P35 quasi_poisson_v2_retirement_disposal): only the mean-variance relation
enters point estimation; the constant dispersion factor cancels from the quasi-score equations,
and NO likelihood-based standard error is ever computed here or consumed anywhere downstream --
all inference is game-cluster bootstrap.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from runner_constants import IRLS_MAX_ITER, IRLS_TOL

#: numeric ceiling applied to the linear predictor ONLY to detect divergence: exp(700) overflows
#: float64. Crossing it is recorded as non-convergence (fail closed), never silently clipped.
_ETA_DIVERGED = 700.0


@dataclass(frozen=True)
class FitResult:
    beta: np.ndarray            # (p,) fitted coefficients; empty for zero-parameter designs
    converged: bool
    n_iter: int
    deviance: float
    reason: str                 # "" when converged; else "iteration_cap" | "singular" | "nonfinite"
    column_names: tuple = field(default_factory=tuple)

    def as_record(self) -> dict:
        return {"beta": [float(b) for b in self.beta],
                "column_names": list(self.column_names),
                "converged": bool(self.converged), "n_iter": int(self.n_iter),
                "deviance": (None if not np.isfinite(self.deviance) else float(self.deviance)),
                "reason": self.reason}


def poisson_deviance(y: np.ndarray, mu: np.ndarray) -> float:
    """2 * sum(y*log(y/mu) - (y - mu)), with the y == 0 limit taken exactly."""
    y = np.asarray(y, float)
    mu = np.asarray(mu, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = np.where(y > 0, y * np.log(y / mu), 0.0)
    return float(2.0 * np.sum(term - (y - mu)))


def predict_mu(X: np.ndarray, beta: np.ndarray, offset: np.ndarray) -> np.ndarray:
    """mu = exp(offset + X @ beta); mu = exp(offset) exactly for zero-parameter designs."""
    offset = np.asarray(offset, float)
    if X is None or X.size == 0 or beta.size == 0:
        return np.exp(offset)
    return np.exp(offset + np.asarray(X, float) @ np.asarray(beta, float))


def fit(X: np.ndarray | None, y: np.ndarray, offset: np.ndarray, *,
        column_names: tuple = (),
        tol: float = IRLS_TOL, max_iter: int = IRLS_MAX_ITER) -> FitResult:
    """Fit the frozen objective. `X` may be None or (n, 0): a ZERO-PARAMETER design is not
    fitted at all -- eta = offset exactly, converged trivially (this is how the [log_exposure]
    nulls of A02/A03/A05/A16/A25 ARE the incumbent).

    `tol`/`max_iter` default to the FROZEN pins and exist as parameters only so the K7 unit
    tests can exercise the non-convergence path on synthetic data; `runner.py` never overrides
    them.
    """
    y = np.asarray(y, float)
    offset = np.asarray(offset, float)
    n = y.shape[0]
    if offset.shape[0] != n:
        raise ValueError("offset length != y length")

    if X is None:
        X = np.empty((n, 0), float)
    X = np.asarray(X, float)
    if X.ndim != 2 or X.shape[0] != n:
        raise ValueError(f"design shape {X.shape} incompatible with n={n}")
    p = X.shape[1]

    if p == 0:
        mu = np.exp(offset)
        return FitResult(beta=np.empty(0), converged=True, n_iter=0,
                         deviance=poisson_deviance(y, mu), reason="",
                         column_names=tuple(column_names))

    if not (np.all(np.isfinite(X)) and np.all(np.isfinite(y)) and np.all(np.isfinite(offset))):
        return FitResult(beta=np.full(p, np.nan), converged=False, n_iter=0,
                         deviance=float("nan"), reason="nonfinite",
                         column_names=tuple(column_names))

    beta = np.zeros(p)
    dev_prev = float("inf")
    for it in range(1, max_iter + 1):
        eta = offset + X @ beta
        if np.max(np.abs(eta)) > _ETA_DIVERGED:
            return FitResult(beta=beta, converged=False, n_iter=it, deviance=float("nan"),
                             reason="nonfinite", column_names=tuple(column_names))
        mu = np.exp(eta)
        # IRLS working weights w = mu (canonical log link); working response
        # z = (eta - offset) + (y - mu) / mu
        w = mu
        z = (eta - offset) + (y - mu) / mu
        Xw = X * w[:, None]
        A = X.T @ Xw
        b = X.T @ (w * z)
        try:
            beta_new = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            return FitResult(beta=beta, converged=False, n_iter=it, deviance=float("nan"),
                             reason="singular", column_names=tuple(column_names))
        if not np.all(np.isfinite(beta_new)):
            return FitResult(beta=beta, converged=False, n_iter=it, deviance=float("nan"),
                             reason="nonfinite", column_names=tuple(column_names))
        beta = beta_new
        dev = poisson_deviance(y, np.exp(offset + X @ beta))
        if np.isfinite(dev) and abs(dev_prev - dev) < tol:
            return FitResult(beta=beta, converged=True, n_iter=it, deviance=dev, reason="",
                             column_names=tuple(column_names))
        dev_prev = dev

    return FitResult(beta=beta, converged=False, n_iter=max_iter, deviance=dev_prev,
                     reason="iteration_cap", column_names=tuple(column_names))
