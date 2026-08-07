#!/usr/bin/env python3
"""SC09_FAV_GAP_COMPRESSION -- blowout-gap compression hinge. 1 element, CALIBRATION_ONLY.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/7, arm_block_sha256 7e2c511d...):

  g_hat = the element's OWN K0 prediction (per-fold train-OLS a + b*C_margin)
  h     = sign(g_hat) * max(0, |g_hat| - 8),  knee PINNED at 8
  y     = a + b*C_margin + gamma*h,  gamma SIGN-PINNED NEGATIVE

THIS ARM IS `calibration_only` (S34 finding B8, re-carded at S33R). Its treatment term is a
deterministic shape-restricted transform of the K0's OWN fitted prediction and introduces no
information the null lacks, so per P26 1.5 as carried by the S32B schema this element may NEVER
be reported as feature value. That is a labelling fact, carried on the ElementSpec, not something
the runner can be talked out of downstream.

A CONSEQUENCE OF THE CARD, STATED PLAINLY RATHER THAN WORKED AROUND. The feature is defined in
terms of a FITTED K0 prediction. Fitting is NOT authorised at S36 -- "Fitting requires a PASSED
S37 implementation audit" -- so this arm's design CANNOT be materialised on the real universe at
this node, and the S36 real-universe build harness records it as
`BUILD_REQUIRES_K0_FIT / DEFERRED_TO_S38` rather than quietly fitting to produce a column. The
construction itself is fully implemented and fully exercised on synthetic data, where fitting is
permitted; `build` takes the fold's K0 fit as an argument, so at S38 the runner supplies the same
K0 it is already fitting and no second, differently-fitted g_hat can come into existence.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head  # noqa: E402
from estimators import fit_ols  # noqa: E402
from runner_interface import ElementSpec  # noqa: E402

ARM_ID = "SC09_FAV_GAP_COMPRESSION"
FORMULA = ("deterministic hinge of the K0's own fitted margin prediction, knee pinned at 8, one "
           "sign-pinned head coefficient")
KNEE = 8.0
SIGN_PIN = "gamma_comp NEGATIVE"
HABITAT_KILL_MIN_SHARE = 0.10
BUILD_REQUIRES_K0_FIT = (
    "SC09's treatment feature is a transform of the element's OWN fitted K0 prediction. Fitting "
    "is not authorised until S37 passes, so this design is not materialisable on the real "
    "universe at S36. Deferred to S38; fully implemented and synthetically tested here.")


def hinge(g_hat: np.ndarray) -> np.ndarray:
    """h = sign(g_hat) * max(0, |g_hat| - 8). Deterministic; no data enters that the K0 lacks."""
    g_hat = np.asarray(g_hat, dtype=float)
    return np.sign(g_hat) * np.maximum(0.0, np.abs(g_hat) - KNEE)


def k0_prediction(universe, fold) -> np.ndarray:
    """The K0's own per-fold train-OLS prediction a + b*C_margin, over ALL rows.

    Calling this on the real universe IS a fit and is refused upstream by the blinding gate; it is
    exposed so S38 can hand the identical object to `build`."""
    C = universe.games["C_margin"].to_numpy(dtype=float)
    y = universe.games["E2_FINAL_MARGIN_HOME"].to_numpy(dtype=float)
    X = np.column_stack([np.ones(len(C)), C])
    f = fit_ols(X[fold["train_idx"]], y[fold["train_idx"]])
    return X @ f.coef


def build(universe, fold, cache=None, *, g_hat=None):
    """`g_hat` MUST be the fold's own K0 prediction. Passing it in (rather than refitting inside)
    is what guarantees the hinge is a transform of the SAME null the comparison uses."""
    if g_hat is None:
        g_hat = k0_prediction(universe, fold)
    h = hinge(np.asarray(g_hat, dtype=float))
    return linear_head(
        universe, "E2_FINAL_MARGIN_HOME", {"gap_compression_hinge": h},
        fold_constants={"knee": KNEE, "sign_pin": SIGN_PIN,
                        "g_hat_source": "the element's own per-fold train-OLS K0 prediction",
                        "arm_kind": "calibration_only",
                        "may_never_be_reported_as_feature_value": True,
                        "habitat_kill_min_share_of_pooled_test_clusters": HABITAT_KILL_MIN_SHARE,
                        "build_requires_k0_fit": BUILD_REQUIRES_K0_FIT})


KILLS = (
    "fitted gamma >= 0 pooled (wrong sign = dead, no re-spec)",
    "Delta <= 0 on the |g_hat| > 8 subset (no claim anywhere else)",
    "habitat too small: the |g_hat| > 8 subset is < 10% of pooled test clusters - the magnitude "
    "claim was not honest; kill rather than reinterpret",
)

ELEMENTS = [
    ElementSpec(
        element_id="SC09_FAV_GAP_COMPRESSION::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="calibration_only",
        family_primary="FAM_S2_BLOWOUT_DISCOUNT",
        card_sha256="4d32d181a7d01472f742848ef04d6e9bf701a4de4c64f38a0a599e4476ee650e",
        build=build, kill_conditions=KILLS, sign_pin=SIGN_PIN,
        mandatory_receipts=("coefficient_table", "subset_delta_table_gt_knee",
                            "subset_count_receipt", "R-A1-EXCEPTIONS"),
        notes=("calibration_only: per P26 1.5 as carried by the S32B schema this element may "
               "NEVER be reported as feature value",
               BUILD_REQUIRES_K0_FIT)),
]
