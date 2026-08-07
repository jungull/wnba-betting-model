#!/usr/bin/env python3
"""SC11_LEAGUE_TOTAL_DRIFT -- lagged league scoring-environment drift. 1 element.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/9, arm_block_sha256 b43210b2...):

  LT_lag(d) = EWMA (half-life 60 league games) of strictly-prior settled totals, sequenced
              (game_date, game_id)
  x = LT_lag - fold-train mean total
  y = a + b*C_total + beta*x
  One fitted beta.

C3 / OBLIGATION O4 LIVES HERE. This arm carries a cross-estimand sanity receipt that fits the
IDENTICAL feature on the E2 head and receipts |Delta-MAE(E2)|. That number is computed on an
estimand SC11 is NOT registered for and that sits in NO family, so it is bound as
NON_CITABLE_INTEGRITY_DIAGNOSTIC and may be used for exactly one thing: firing or not firing the
card-pinned implementation-integrity kill at 0.10 MAE points.

`cross_estimand_receipt()` is the ONLY constructor for it in this node. It routes through
`obligations.label_sc11_cross_estimand`, then re-checks the label with
`assert_sc11_cross_estimand_labelled` before returning, and it deliberately does NOT name the
number `delta_mae` -- it is `abs_delta_mae_E2_NON_CITABLE`, so a downstream caller cannot lift it
out by habit and have it read like a result. The label travels with the number wherever it is
emitted, copied or cited.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head  # noqa: E402
from features_common import center_on_train, league_prior_ewma  # noqa: E402
from obligations import (C3_KILL_THRESHOLD_MAE_POINTS,  # noqa: E402
                         assert_sc11_cross_estimand_labelled, label_sc11_cross_estimand)
from runner_interface import ElementSpec  # noqa: E402

ARM_ID = "SC11_LEAGUE_TOTAL_DRIFT"
FORMULA = ("lagged league EWMA (half-life 60 league games) of settled totals, centred on the "
           "fold-train mean; one fitted beta")
HALFLIFE_LEAGUE_GAMES = 60.0


def lt_lag(universe) -> np.ndarray:
    g = universe.games.copy()
    g["total"] = g["home_pts"] + g["away_pts"]
    return league_prior_ewma(g, "total", halflife=HALFLIFE_LEAGUE_GAMES,
                             fill=0.0).to_numpy(dtype=float)


def build(universe, fold, cache=None):
    cache = {} if cache is None else cache
    raw = cache.setdefault("lt_lag", lt_lag(universe))
    x, mu = center_on_train(raw, fold["train_idx"])
    return linear_head(
        universe, "E1_GAME_TOTAL", {"league_total_drift_centered": x},
        fold_constants={"halflife_league_games": HALFLIFE_LEAGUE_GAMES,
                        "train_center": float(mu), "sequencing": "(game_date, game_id)",
                        "undefined_fallback": 0.0,
                        "identification": "centered on the training constant; null-granted "
                                          "columns keep the level"})


def build_cross_estimand_E2(universe, fold, cache=None):
    """The IDENTICAL feature fitted on the E2 head -- the C3 receipt's design.

    'Identical' is enforced by reusing the same cached column, not by re-deriving it, so the
    integrity diagnostic cannot silently test a different feature from the one it is diagnosing.
    NOTE the centring constant is recomputed on the same fold's training rows, which is the same
    rule, not a different one."""
    cache = {} if cache is None else cache
    raw = cache.setdefault("lt_lag", lt_lag(universe))
    x, mu = center_on_train(raw, fold["train_idx"])
    return linear_head(
        universe, "E2_FINAL_MARGIN_HOME", {"league_total_drift_centered": x},
        fold_constants={"halflife_league_games": HALFLIFE_LEAGUE_GAMES, "train_center": float(mu),
                        "purpose": "C3 cross-estimand integrity diagnostic ONLY",
                        "not_a_registered_element": True})


def cross_estimand_receipt(abs_delta_mae_e2, *, per_fold=None, n_matched_universe=None) -> dict:
    """The ONLY sanctioned constructor for the SC11 cross-estimand number (obligation O4 / C3)."""
    fired = None
    if abs_delta_mae_e2 is not None:
        fired = bool(float(abs_delta_mae_e2) > C3_KILL_THRESHOLD_MAE_POINTS)
    out = label_sc11_cross_estimand({
        "schema": "s36_sc11_cross_estimand/1",
        "applies_to": "SC11_LEAGUE_TOTAL_DRIFT::E1_GAME_TOTAL",
        "estimand_computed_on": "E2_FINAL_MARGIN_HOME (SC11 is NOT registered for it)",
        "abs_delta_mae_E2_NON_CITABLE": abs_delta_mae_e2,
        "per_fold": per_fold or {},
        "n_matched_universe": n_matched_universe,
        "integrity_kill_fired": fired,
        "why_the_mechanism_predicts_zero": ("the feature is a league TOTAL drift; on the margin "
                                            "head it should move nothing by construction, so a "
                                            "large |Delta| is an implementation defect, not a "
                                            "performance finding")})
    assert_sc11_cross_estimand_labelled(out)
    return out


KILLS = (
    "beta pooled 95% CI covers 0 AND covers 0 in >= 4 of 5 folds",
    "cross-estimand integrity: |Delta-MAE(E2)| in the receipted non-gating E2 diagnostic exceeds "
    "0.10 MAE points (card-pinned bound; violation is an implementation-integrity kill, not a "
    "performance kill)",
    "single-test-season dependence: leave-one-test-season-out receipt flips pooled Delta to <= 0",
)

ELEMENTS = [
    ElementSpec(
        element_id="SC11_LEAGUE_TOTAL_DRIFT::E1_GAME_TOTAL", arm_id=ARM_ID,
        estimand="E1_GAME_TOTAL", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_LEVEL_DRIFT",
        card_sha256="763b17d30e629c74266e0db6539e9651a5db71bead7bdad496a3dd5b1883b40d",
        build=build, kill_conditions=KILLS,
        mandatory_receipts=("coefficient_table",
                            "cross_estimand_sanity_receipt_NON_CITABLE_INTEGRITY_DIAGNOSTIC",
                            "leave_one_test_season_out_delta_table", "R-A1-EXCEPTIONS"),
        notes=("the cross-estimand |Delta-MAE(E2)| receipt is labelled "
               "NON_CITABLE_INTEGRITY_DIAGNOSTIC; it sits in no family, belongs to no "
               "registration, may never be quoted as a result, and may be used only to fire or "
               "not fire the 0.10-MAE-point integrity kill",)),
]
