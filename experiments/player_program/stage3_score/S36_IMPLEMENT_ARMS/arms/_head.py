#!/usr/bin/env python3
"""_head.py -- the shared element head, so eleven arms cannot mean eleven different things by it.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

Sixteen of the seventeen frozen cards share the same head shape:

    E1 / E2 (gaussian_identity, l2):   y      = a + b*C + <treatment terms>
    E3      (bernoulli_logit)      :   logit p= a + b*C + <treatment terms>

with `C` the byte-pinned null-granted composite column (C_total for E1, C_margin for E2/E3), and
with the K0_MATCHED being EXACTLY that design minus the treatment terms. SC08 is the seventeenth
and carries its own dispersion head.

`linear_head` therefore takes the treatment columns and returns the pair. Building both sides
from one column dictionary in one place is what makes "differ only by the declared treatment
terms" structurally true instead of a claim each arm has to re-honour.

THE p_home READING (interpretive pin, RAISED TO S37, carried in every receipt this node writes).
Three E3 cards -- SC01::E3, SC06::E3, SC08::E3 -- list BOTH `composite_pred_margin` and
`composite_p_home` in `arm_spec.structural_terms`, while their own `formula` fields fit only the
composite MARGIN through the link:

    SC01 formula: "E3: logit(p) = a + b*C_margin + c*[strength margin]"
    SC06 formula: "E3: identical features through bernoulli-logit"   (i.e. C_margin, era, F-diff)
    SC08 formula: "mu_hat = a + b*C_margin ... p = Phi(mu_hat/sigma_g)"

and `a4_sc08_null_strength_receipt` describes those K0s as fitting "a per-fold logistic of the
composite margin on train seasons < Y, which is exactly the frozen builder's walk-forward
construction of p_home". Reading `composite_p_home` as a FITTED design column is additionally
UNIMPLEMENTABLE as frozen: the byte pin itself records n_nan = 188, this node re-measured 188
structural NaN rows on the universe, and no card declares an imputation for them (the frozen
contract's own §8a dual-frame gap is precisely about undeclared imputation).

So this node implements `composite_p_home` as a null-granted INGREDIENT -- byte-pinned, carried
identically on both sides, and consumed by the mandatory R_SC08_FLOOR receipt as the public-floor
control object -- and NOT as a fitted column. Both readings are recorded; the contradiction is
raised, not reconciled away.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from runner_interface import DesignPair  # noqa: E402

COMPOSITE_FOR_ESTIMAND = {"E1_GAME_TOTAL": ("C_total", "composite_pred_total"),
                          "E2_FINAL_MARGIN_HOME": ("C_margin", "composite_pred_margin"),
                          "E3_HOME_WIN_PROB": ("C_margin", "composite_pred_margin")}

P_HOME_READING = (
    "composite_p_home is carried as a NULL-GRANTED INGREDIENT (byte-pinned, identical on both "
    "sides, consumed by R_SC08_FLOOR as the public-floor control object), NOT as a fitted design "
    "column. Reason: the three E3 cards' own `formula` fields fit only the composite margin "
    "through the link, a4_sc08_null_strength_receipt describes the E3 K0s the same way, and the "
    "column carries 188 structural NaN rows (re-measured at S36; the byte pin itself records "
    "n_nan=188) for which no card declares an imputation, so the fitted-column reading is not "
    "implementable as frozen. CONTRADICTION RAISED TO S37, not reconciled: "
    "arm_spec.structural_terms lists composite_p_home alongside composite_pred_margin.")


def linear_head(universe, estimand: str, treatment: dict[str, np.ndarray], *,
                extra_structural: dict[str, np.ndarray] | None = None,
                fold_constants: dict | None = None,
                indicator_cols: tuple[str, ...] = (),
                comparison: str = "term_removal",
                deactivated: bool = False,
                deactivation_reason: str | None = None) -> DesignPair:
    """Build the arm/K0 pair for one element and one fold.

    treatment        -- the card's treatment terms, name -> column (empty dict = deactivated fold)
    extra_structural -- null-granted structural terms BEYOND the composite that are fitted
                        columns present identically on both sides (only SC06's ERA2024)
    """
    g = universe.games
    n = len(g)
    ccol, cname = COMPOSITE_FOR_ESTIMAND[estimand]

    columns: dict[str, np.ndarray] = {"intercept": np.ones(n, dtype=float),
                                      cname: g[ccol].to_numpy(dtype=float)}
    structural = [cname]
    for k, v in (extra_structural or {}).items():
        columns[k] = np.asarray(v, dtype=float)
        structural.append(k)
    for k, v in treatment.items():
        columns[k] = np.asarray(v, dtype=float)

    k0_cols = ("intercept", *structural)
    arm_cols = (*k0_cols, *treatment.keys())
    return DesignPair(columns=columns, arm_cols=arm_cols, k0_cols=k0_cols,
                      treatment_cols=tuple(treatment.keys()),
                      structural_cols=tuple(structural), comparison=comparison,
                      indicator_cols=indicator_cols,
                      fold_constants={**(fold_constants or {}),
                                      "null_granted_composite_column": cname,
                                      "p_home_reading": P_HOME_READING},
                      deactivated=deactivated, deactivation_reason=deactivation_reason)


def select_lambda_train_tail(train_idx: np.ndarray, grid, fit_and_score) -> dict:
    """The pinned 'train-tail 80/20' selection rule (SC01 grid {2,8,32,128}, SC10 grid {4,16,64}).

    The fold's TRAINING clusters, in chronological order, are split 80/20; each grid value is
    fitted on the first 80% and scored on the last 20%; the minimising value wins, ties broken by
    the SMALLER lambda (deterministic, declared, never data-dependent).

    Nothing here touches a test cluster, so no comparative out-of-fold number exists. The rule is
    a training-time selection over a 4- (or 3-) point pinned grid, exactly as carded -- it is not
    a tuning loop and the grid is not enlarged.

    THE SELECTION SCORES ARE WITHHELD FROM EVERY RECEIPT AT S36, and this is not fastidiousness.
    Computing them is unavoidable -- the frozen card makes per-fold lambda selection part of the
    CONSTRUCTION, so a design for SC01 or SC10 cannot exist without them -- but they are
    training-tail MAE values on real historical rows, and S36's acceptance criterion is "no
    performance number emitted anywhere". Constructing a number in memory to satisfy a carded
    construction rule is authorised; leaving it on disk is not. So the returned record carries the
    SELECTED lambda, the grid and the rule, and never the scores. (This node wrote them into a
    receipt on its first pass and its own test caught it; the redaction is the fix.)"""
    train_idx = np.asarray(train_idx)
    cut = int(round(0.8 * len(train_idx)))
    if cut < 1 or cut >= len(train_idx):
        raise ValueError("training fold too small for the pinned 80/20 train-tail split")
    inner, tail = train_idx[:cut], train_idx[cut:]
    scores = {float(lam): float(fit_and_score(lam, inner, tail)) for lam in grid}
    best = min(sorted(scores), key=lambda l: (scores[l], l))
    return {"selected": best, "grid": list(map(float, grid)),
            "rule": "80/20 chronological train-tail; ties broken by the smaller lambda",
            "n_inner": len(inner), "n_tail": len(tail),
            "no_test_cluster_touched": True,
            "selection_scores": "WITHHELD_AT_S36_NO_PERFORMANCE_NUMBER_EMITTED",
            "why_withheld": ("training-tail MAE values on real rows; computing them is required "
                             "by the card's own construction rule, emitting them is not "
                             "authorised until the sealed run")}
