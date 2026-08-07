#!/usr/bin/env python3
"""SC04_HCA_LEAGUE_DRIFT -- lagged league home-court advantage, centred. 1 element.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/3, arm_block_sha256 9a35c1a8...):

  HCA_lag(d) = EWMA (alpha = 1 - 0.5^(1/60)) over strictly-prior settled universe games,
               sequenced (game_date, game_id), of (home_pts - away_pts)
  x = HCA_lag - fold-train mean(home - away)
  y = a + b*C_margin + beta*x
  One fitted beta; ZERO fitted parameters inside the construction.

The alpha the card writes, 1 - 0.5^(1/60), is exactly a 60-league-game half-life, which is how
`features_common.league_prior_ewma` is parameterised. Both spellings are recorded in the fold
constants so a third party can check they are the same number rather than take it on faith.

CENTERING IS THE IDENTIFICATION CONSTRAINT, not a convenience: "the training-constant level stays
owned by the null's intercept". The centring constant is computed on the fold's TRAINING rows
only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head  # noqa: E402
from features_common import center_on_train, league_prior_ewma  # noqa: E402
from runner_interface import ElementSpec  # noqa: E402

ARM_ID = "SC04_HCA_LEAGUE_DRIFT"
FORMULA = ("lagged league EWMA (half-life 60 league games) of settled home-away margins, centred "
           "on the fold-train mean; one fitted beta")
HALFLIFE_LEAGUE_GAMES = 60.0
ALPHA_EQUIVALENT = 1.0 - 0.5 ** (1.0 / 60.0)


def hca_lag(universe) -> np.ndarray:
    g = universe.games.copy()
    g["home_minus_away"] = g["home_pts"] - g["away_pts"]
    return league_prior_ewma(g, "home_minus_away", halflife=HALFLIFE_LEAGUE_GAMES,
                             fill=0.0).to_numpy(dtype=float)


def build(universe, fold, cache=None):
    cache = {} if cache is None else cache
    raw = cache.setdefault("hca_lag", hca_lag(universe))
    x, mu = center_on_train(raw, fold["train_idx"])
    return linear_head(
        universe, "E2_FINAL_MARGIN_HOME", {"hca_league_drift_centered": x},
        fold_constants={"halflife_league_games": HALFLIFE_LEAGUE_GAMES,
                        "alpha_as_carded": ALPHA_EQUIVALENT,
                        "alpha_equals_halflife_60": bool(
                            abs(ALPHA_EQUIVALENT - (1 - 0.5 ** (1 / HALFLIFE_LEAGUE_GAMES)))
                            < 1e-15),
                        "train_center": float(mu),
                        "sequencing": "(game_date, game_id)",
                        "undefined_fallback": 0.0,
                        "identification": ("centering IS the level-separation constraint: the "
                                           "training-constant level stays owned by the null's "
                                           "intercept")})


KILLS = (
    "beta pooled 95% CI covers 0 AND covers 0 in >= 4 of 5 folds",
    "single-test-season dependence: pooled Delta > 0 but Delta <= 0 after removing any single "
    "test season (2021 is never a test season under the pinned folds)",
    "fitted beta > 1.5 or < 0: outside the mechanically sensible range for a partially-absorbed "
    "drift term, indicating specification leak",
)

ELEMENTS = [
    ElementSpec(
        element_id="SC04_HCA_LEAGUE_DRIFT::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_HOME_COURT",
        card_sha256="d105831f8146bc358d735ad6bb2cbec1273a81b0fa5d51d8816a5d035f88ca59",
        build=build, kill_conditions=KILLS,
        mandatory_receipts=("coefficient_table_pooled_and_per_fold",
                            "leave_one_test_season_out_delta_table", "R-A1-EXCEPTIONS"),
        notes=("disputed partition: {SC04, SC05} vs {SC04, SC11} merged into "
               "FAM_S2_LAGGED_LEAGUE_DRIFT; the element runs under BOTH and the stricter governs",)),
]
