#!/usr/bin/env python3
"""estimators.py -- the four deterministic fitters the frozen cards name, and nothing else.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

SPEC_V2.seed_manifest_plan.fitting, verbatim:

    "all fits are deterministic (OLS, IRLS, closed-form MoM, pinned-init Newton for SC08
     dispersion); no fit-time seed exists; any implementation introducing a stochastic fitting
     step violates this preregistration"

So this module exposes exactly those four and no stochastic option. There is no random_state
parameter anywhere, no initialisation drawn from anything, and no early-stopping heuristic --
an implementation that needed one would be violating the preregistration, not configuring it.

THE INTERCEPT RULE (carried from the cycle-1 P36 interface, which the S37 audit will check):
no fitter here adds an intercept. A design has an intercept if and only if the caller supplies a
column of ones named "intercept", identically in arm and K0. There is no `fit_intercept` flag to
set differently on the two sides.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import runner_constants as K


class EstimationFailure(RuntimeError):
    """Non-convergence / singularity. The caller must record the fold UNEVALUABLE for BOTH
    members symmetrically -- never for one side only."""


@dataclass
class Fit:
    coef: np.ndarray
    columns: tuple[str, ...]
    converged: bool
    n_iter: int
    objective: str
    extra: dict = field(default_factory=dict)

    def predict_linear(self, X: np.ndarray) -> np.ndarray:
        return X @ self.coef


def _check(X: np.ndarray, y: np.ndarray) -> None:
    if X.ndim != 2:
        raise EstimationFailure("design must be 2-d")
    if len(X) != len(y):
        raise EstimationFailure(f"design/target length mismatch {len(X)} vs {len(y)}")
    if not np.isfinite(X).all():
        raise EstimationFailure("non-finite value in design matrix")
    if not np.isfinite(y).all():
        raise EstimationFailure("non-finite value in target")


def fit_ols(X: np.ndarray, y: np.ndarray, columns=(), *, ridge: float = 0.0,
            penalise: np.ndarray | None = None) -> Fit:
    """Least squares, optionally with a ridge penalty on a DECLARED subset of columns.

    `penalise` is a boolean mask the caller must supply when ridge > 0: the cards ridge the rating
    effects (SC01) or the two spread coefficients (SC10) and NOTHING else -- "ridge on (off, def)
    rating effects only, ... none on the head". Penalising an intercept silently is exactly the
    kind of unmatched flexibility Layer A exists to catch, so the mask is required rather than
    defaulted."""
    _check(X, y)
    if ridge < 0:
        raise EstimationFailure("ridge penalty must be non-negative")
    if ridge == 0:
        coef, *_ = np.linalg.lstsq(X, y, rcond=K.OLS_RCOND)
        return Fit(coef=coef, columns=tuple(columns), converged=True, n_iter=0,
                   objective="l2_squared_error/gaussian_identity")
    if penalise is None:
        raise EstimationFailure(
            "ridge > 0 requires an explicit `penalise` mask: the cards ridge a NAMED subset "
            "(rating effects / spread coefficients) and never the head or the intercept")
    penalise = np.asarray(penalise, dtype=bool)
    if penalise.shape != (X.shape[1],):
        raise EstimationFailure("penalise mask shape does not match the design")
    XtX = X.T @ X
    XtX[np.diag_indices_from(XtX)] += ridge * penalise
    try:
        coef = np.linalg.solve(XtX, X.T @ y)
    except np.linalg.LinAlgError as e:
        raise EstimationFailure(f"ridge normal equations singular: {e}") from e
    return Fit(coef=coef, columns=tuple(columns), converged=True, n_iter=0,
               objective="l2_squared_error/gaussian_identity+ridge",
               extra={"ridge": float(ridge), "penalised_columns":
                      [c for c, p in zip(columns, penalise) if p]})


def _logistic(z: np.ndarray) -> np.ndarray:
    out = np.empty_like(z, dtype=float)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def fit_logit_irls(X: np.ndarray, y: np.ndarray, columns=(), *,
                   tol: float = K.IRLS_TOL, max_iter: int = K.IRLS_MAX_ITER) -> Fit:
    """Bernoulli-logit IRLS. Deterministic: zero init, Newton steps, tol on deviance change.

    E3 elements fit `logit(p) = a + b*C_margin + c*<treatment>`; the K0 drops the treatment term.
    Convergence failure raises -- the caller marks the fold UNEVALUABLE symmetrically."""
    _check(X, y)
    if not np.all((y == 0) | (y == 1)):
        raise EstimationFailure("bernoulli_logit target must be 0/1")
    beta = np.zeros(X.shape[1])
    dev_prev = np.inf
    for it in range(1, max_iter + 1):
        eta = X @ beta
        p = _logistic(eta)
        p = np.clip(p, 1e-12, 1 - 1e-12)
        w = p * (1 - p)
        z = eta + (y - p) / w
        XtW = X.T * w
        try:
            beta_new = np.linalg.solve(XtW @ X, XtW @ z)
        except np.linalg.LinAlgError as e:
            raise EstimationFailure(f"IRLS normal equations singular at iter {it}: {e}") from e
        if not np.isfinite(beta_new).all():
            raise EstimationFailure(f"IRLS produced non-finite coefficients at iter {it}")
        beta = beta_new
        p = np.clip(_logistic(X @ beta), 1e-12, 1 - 1e-12)
        dev = -2.0 * np.sum(y * np.log(p) + (1 - y) * np.log(1 - p))
        if abs(dev_prev - dev) < tol:
            return Fit(coef=beta, columns=tuple(columns), converged=True, n_iter=it,
                       objective="bernoulli_logit", extra={"deviance": float(dev)})
        dev_prev = dev
    raise EstimationFailure(
        f"IRLS did not converge in {max_iter} iterations (tol {tol}); the fold is UNEVALUABLE for "
        f"BOTH members, symmetrically")


def fit_eb_shrinkage_mom(d_raw: np.ndarray, s2: np.ndarray) -> dict:
    """SC05's closed-form method-of-moments Empirical-Bayes shrinkage. No optimizer.

        tau2 = max(0, var_between(d_raw) - mean(s2));  w_i = tau2 / (tau2 + s2_i)

    'deterministic method-of-moments, no optimizer' is the card's own phrase; the max(0, .) is the
    card's, not a numerical guard added here."""
    d_raw = np.asarray(d_raw, dtype=float)
    s2 = np.asarray(s2, dtype=float)
    ok = np.isfinite(d_raw) & np.isfinite(s2)
    if ok.sum() < 2:
        return {"tau2": 0.0, "w": np.zeros_like(d_raw), "n_support": int(ok.sum())}
    var_between = float(np.var(d_raw[ok], ddof=1))
    mean_s2 = float(np.mean(s2[ok]))
    tau2 = max(0.0, var_between - mean_s2)
    with np.errstate(divide="ignore", invalid="ignore"):
        w = np.where(np.isfinite(s2) & (tau2 + s2 > 0), tau2 / (tau2 + s2), 0.0)
    return {"tau2": float(tau2), "w": w, "var_between": var_between, "mean_s2": mean_s2,
            "n_support": int(ok.sum())}


def fit_dispersion_newton(resid: np.ndarray, Z: np.ndarray, columns=(), *,
                          tol: float = K.NEWTON_TOL,
                          max_iter: int = K.NEWTON_MAX_ITER) -> Fit:
    """SC08's Gaussian-MLE dispersion fit, pinned initialisation, deterministic Newton.

        sigma_g^2 = sigma0^2 * exp(Z @ gamma)
        theta     = (log sigma0, gamma...)
        init      : log sigma0 = log(sd(resid)), gammas = 0     <- the card's pin
        objective : Gaussian NLL on the FROZEN mean map's residuals

    K0 is this same routine with Z of width 0 (sigma0 only), so arm and null share the machinery
    exactly, as `matched_identically_for_arm_and_k0` requires."""
    resid = np.asarray(resid, dtype=float)
    Z = np.asarray(Z, dtype=float).reshape(len(resid), -1)
    if not np.isfinite(resid).all() or not np.isfinite(Z).all():
        raise EstimationFailure("non-finite input to the dispersion fit")
    sd = float(np.std(resid, ddof=1))
    if not (sd > 0):
        raise EstimationFailure("degenerate residual sd; dispersion fit undefined")
    theta = np.concatenate([[np.log(sd)], np.zeros(Z.shape[1])])
    D = np.column_stack([np.ones(len(resid)), Z]) * 1.0
    D[:, 0] = 2.0                      # d(log sigma^2)/d(log sigma0) = 2
    r2 = resid ** 2

    def nll(th):
        log_s2 = 2.0 * th[0] + (Z @ th[1:] if Z.shape[1] else 0.0)
        return 0.5 * float(np.sum(log_s2 + r2 * np.exp(-log_s2)))

    prev = nll(theta)
    for it in range(1, max_iter + 1):
        log_s2 = 2.0 * theta[0] + (Z @ theta[1:] if Z.shape[1] else 0.0)
        u = r2 * np.exp(-log_s2)                       # r^2 / sigma^2
        grad = 0.5 * (D.T @ (1.0 - u))
        H = 0.5 * (D.T * u) @ D                        # expected information, always PD
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError as e:
            raise EstimationFailure(f"dispersion Hessian singular at iter {it}: {e}") from e
        theta = theta - step
        if not np.isfinite(theta).all():
            raise EstimationFailure(f"dispersion Newton diverged at iter {it}")
        cur = nll(theta)
        if abs(prev - cur) < tol:
            return Fit(coef=theta, columns=("log_sigma0",) + tuple(columns), converged=True,
                       n_iter=it, objective="gaussian_mle_dispersion",
                       extra={"sigma0": float(np.exp(theta[0])), "nll": float(cur),
                              "init": {"log_sigma0": float(np.log(sd)), "gammas": 0.0}})
        prev = cur
    raise EstimationFailure(
        f"dispersion Newton did not converge in {max_iter} iterations (tol {tol})")


def sigma_from_dispersion(fit: Fit, Z: np.ndarray, n_rows: int | None = None) -> np.ndarray:
    """Predicted per-game sd from a dispersion fit. `Z` may be an (n, k) block or an (n, 0) /
    empty array for the K0 (sigma0 only), in which case `n_rows` names the length."""
    k = len(fit.coef) - 1
    Z = np.asarray(Z, dtype=float)
    if k == 0:
        n = int(n_rows if n_rows is not None else (Z.shape[0] if Z.ndim else 0))
        return np.full(n, float(np.exp(fit.coef[0])))
    Z = Z.reshape(-1, k)
    log_s2 = 2.0 * fit.coef[0] + Z @ fit.coef[1:]
    return np.sqrt(np.exp(log_s2))
