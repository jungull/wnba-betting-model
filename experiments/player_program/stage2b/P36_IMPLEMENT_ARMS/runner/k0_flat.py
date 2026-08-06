#!/usr/bin/env python3
"""k0_flat.py -- the shared K0_FLAT diagnostic control module.

K0_FLAT is DIAGNOSTIC ONLY (P33 inference.k0_flat, carried by P35): it appears in no promotion
decision; K0_MATCHED is authoritative and per-arm. Every record this module emits carries
role = "diagnostic_only" so no downstream consumer can cite it as a control.

DEFINITIONAL NOTE (flagged for P37, RUNNER_INTERFACE.md section 7): the frozen prose pins only
"(intercept-only)". Both readings are computed and labelled:

  * k0_flat_offset_intercept -- design [intercept] WITH the receipted log_exposure offset,
    identical quasi-Poisson pipeline, zero features (the program's receipted K0 lineage:
    comparison_gate.py docstring; discovery-wave fit_k0 "intercept-only control arm, identical
    pipeline"). Default diagnostic.
  * k0_flat_pure_intercept -- design [intercept] with NO offset; a literally flat mu.

Neither variant enters any promotion decision, so carrying both changes no inference.
"""
from __future__ import annotations

import numpy as np

import quasipoisson_irls as qp


def fit_k0_flat(y_train: np.ndarray, offset_train: np.ndarray,
                y_test: np.ndarray, offset_test: np.ndarray) -> dict:
    """Fit both K0_FLAT readings on one fold's training rows; report test MAE diagnostics."""
    ones_tr = np.ones((len(np.asarray(y_train)), 1))
    ones_te = np.ones((len(np.asarray(y_test)), 1))

    out = {"schema": "p36_k0_flat/1", "role": "diagnostic_only",
           "note": ("K0_FLAT appears in NO promotion decision; K0_MATCHED is the sole "
                    "authoritative control. Two intercept-only readings computed; see "
                    "RUNNER_INTERFACE.md section 7."),
           "variants": {}}

    fit_off = qp.fit(ones_tr, y_train, offset_train, column_names=("intercept",))
    mu_off = qp.predict_mu(ones_te, fit_off.beta, offset_test) if fit_off.converged else None
    out["variants"]["k0_flat_offset_intercept"] = {
        "definition": "[intercept] with the receipted log_exposure offset, zero features",
        "fit": fit_off.as_record(),
        "test_mae": (None if mu_off is None or not len(np.asarray(y_test))
                     else float(np.mean(np.abs(np.asarray(y_test, float) - mu_off))))}

    zero_off_tr = np.zeros(len(np.asarray(y_train)))
    zero_off_te = np.zeros(len(np.asarray(y_test)))
    fit_pure = qp.fit(ones_tr, y_train, zero_off_tr, column_names=("intercept",))
    mu_pure = qp.predict_mu(ones_te, fit_pure.beta, zero_off_te) if fit_pure.converged else None
    out["variants"]["k0_flat_pure_intercept"] = {
        "definition": "[intercept] with NO offset; mu constant",
        "fit": fit_pure.as_record(),
        "test_mae": (None if mu_pure is None or not len(np.asarray(y_test))
                     else float(np.mean(np.abs(np.asarray(y_test, float) - mu_pure))))}
    return out
