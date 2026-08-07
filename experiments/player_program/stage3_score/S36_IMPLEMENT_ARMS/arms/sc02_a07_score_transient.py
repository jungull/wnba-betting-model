#!/usr/bin/env python3
"""SC02_A07_SCORE_TRANSIENT -- early-season transient. 2 elements.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/1, arm_block_sha256 11ac16b7...):

  E1: y = a + b*C_total  + delta_sum *(exp(-n_H/5) + exp(-n_A/5))
  E2: y = a + b*C_margin + delta_diff*(exp(-n_H/5) - exp(-n_A/5))
  tau = 5 carried PINNED from the cycle-1 registration, NEVER retuned; ONE fitted treatment
  coefficient per element; direction NOT preregistered (cycle-1 convention); a sign flip across
  folds kills.

n = same-season strictly-prior COMPLETED resolved-universe games. Season openers have n = 0 --
the transient's maximum -- by construction, so no cold-start fallback is needed and the universe
is full.

Note the cycle-1 caveat the card carries: this is a FRESH registration. The cycle-1 near-miss is
never citable toward promotion.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head  # noqa: E402
from features_common import prior_count  # noqa: E402
from runner_interface import ElementSpec  # noqa: E402
from universe import attach_side  # noqa: E402

ARM_ID = "SC02_A07_SCORE_TRANSIENT"
FORMULA = ("exp(-n/5) recombinations of per-side same-season strictly-prior completed-game "
           "counts, one fitted coefficient per element")
TAU = 5.0                       # PINNED from cycle 1. Never retuned.
EARLY_STRATUM_PREDICATE = "min(n_H, n_A) <= 5"
EARLY_STRATUM_POOLED = 249
KAPPA2_UNEVALUABLE_THRESHOLD = 1000.0   # pinned convention, informed by no floor or bar value


def transient_terms(universe) -> dict[str, np.ndarray]:
    """exp(-n/tau) per side, then the sum and difference recombinations."""
    pc = prior_count(universe.team_rows, same_season=True)
    pc = pc.assign(decay=np.exp(-pc["n_prior"].to_numpy(dtype=float) / TAU))
    g = attach_side(universe.games, pc, "decay", "decay_H", "decay_A", fill=1.0)
    n = attach_side(universe.games, pc.rename(columns={"n_prior": "n"}), "n", "n_H", "n_A", fill=0.0)
    return {"a07_transient_sum": (g["decay_H"] + g["decay_A"]).to_numpy(dtype=float),
            "a07_transient_diff": (g["decay_H"] - g["decay_A"]).to_numpy(dtype=float),
            "n_H": n["n_H"].to_numpy(dtype=float), "n_A": n["n_A"].to_numpy(dtype=float)}


def _build(estimand: str, term: str):
    def build(universe, fold, cache=None):
        cache = {} if cache is None else cache
        t = cache.setdefault("terms", transient_terms(universe))
        return linear_head(universe, estimand, {term: t[term]},
                           fold_constants={"tau": TAU, "tau_provenance": "PINNED from the cycle-1 "
                                                                        "registration; never retuned",
                                           "clock": "same-season strictly-prior completed "
                                                    "resolved-universe games",
                                           "cold_start": "season openers have n = 0 by "
                                                         "construction; no fallback needed"})
    return build


KILLS = (
    "CONCENTRATION KILL (mandatory per D042/D043): improvement concentrating outside the early "
    f"stratum ({EARLY_STRATUM_PREDICATE}; measured {EARLY_STRATUM_POOLED} pooled / 40-49 per test "
    "season) kills the arm as an early-season claim regardless of pooled results",
    "delta 95% interval covers 0 pooled, or sign of delta-hat flips across folds",
    "unevaluable against null-granted columns: kappa_2 (2-norm condition number of the fold's "
    "TRAINING design [intercept, standardised null-granted column, standardised treatment term]) "
    ">= 1000 marks the fold UNEVALUABLE; failure in >= 2 folds retires the arm UNEVALUATED",
)
RECEIPTS = ("early_stratum_concentration_table", "per_fold_coefficient_table",
            "per_fold_kappa2_table", "R-A1-EXCEPTIONS")

ELEMENTS = [
    ElementSpec(
        element_id="SC02_A07_SCORE_TRANSIENT::E1_GAME_TOTAL", arm_id=ARM_ID,
        estimand="E1_GAME_TOTAL", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_EARLY_SEASON",
        card_sha256="89ec1bf1559b952dc0230f5466c9342175fd4927580db62d096eac7da0dc88e8",
        build=_build("E1_GAME_TOTAL", "a07_transient_sum"),
        kill_conditions=KILLS, mandatory_receipts=RECEIPTS),
    ElementSpec(
        element_id="SC02_A07_SCORE_TRANSIENT::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_EARLY_SEASON",
        card_sha256="63b3d2bcd2cecb736f1506c068d63a0cce16ffc6acb63c80c088ac2ca1d63fa5",
        build=_build("E2_FINAL_MARGIN_HOME", "a07_transient_diff"),
        kill_conditions=KILLS, mandatory_receipts=RECEIPTS),
]
