#!/usr/bin/env python3
"""SC03_SEASON_CARRYOVER_PRIOR -- shrunk, faded prior-season carryover. 2 elements.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/2, arm_block_sha256 013d8477...):

  carry_net(team) = 0.5 * prior-season mean(pts - opp_pts)
  carry_env(team) = 0.5 * (prior-season mean team total - prior-season league mean total)
  shrink lambda = 0.5 PINNED; fade g(n) = max(0, 1 - n/10), K = 10 PINNED, n = min(n_H, n_A)
  E2: y = a + b*C_margin + beta*g(n)*(carry_net_H - carry_net_A)
  E1: y = a + b*C_total  + beta*g(n)*(carry_env_H + carry_env_A)
  One fitted beta per element. Expansion/2021 carry = 0.

READING OF "shrink lambda = 0.5": the 0.5 multiplier that opens each carry definition IS the
pinned shrink -- carry = lambda * (prior-season aggregate) with lambda = 0.5, shrinking toward
the league-mean prior of 0. The card states the multiplier and the lambda as one pinned pair and
this implementation applies it exactly once, never twice.

DECLARED STRUCTURAL DEACTIVATION (fold_local_fallback, required=true, registered before results):
fold train_lt_2022 trains on 2021 only, which has no prior season in-universe, so carry = 0
identically there. The TERM is dropped for that fold on BOTH sides -- rows are never dropped, and
the coverage stays 100%. This is a pre-known instance of the P26 zero-variance-on-the-control
pattern, declared before any fit, symmetric by construction.

S33 MEASUREMENT-DRIVEN JUDGMENT CALL, carried: the composite's efficiency EWMAs were MEASURED
continuous across seasons at full weight, so the deficiency S32 conditioned on is absent in that
form. The slate's 'fitted beta <= 0' directional kill is therefore REPLACED by a sign-consistency
kill -- the correction's direction is no longer derivable a priori.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head  # noqa: E402
from features_common import prior_count, prior_season_aggregates  # noqa: E402
from runner_interface import ElementSpec  # noqa: E402
from universe import attach_side  # noqa: E402

ARM_ID = "SC03_SEASON_CARRYOVER_PRIOR"
FORMULA = ("prior-season settled aggregates, shrunk (lambda = 0.5) and faded "
           "(g(n) = max(0, 1 - n/10)), one fitted beta per element")
SHRINK_LAMBDA = 0.5     # PINNED
FADE_K = 10.0           # PINNED
DEACTIVATED_FOLDS = ("train_lt_2022",)
EARLY_SUBSET_PREDICATE = "min(n_H, n_A) < 10"
EARLY_SUBSET_POOLED = 399


def carryover_terms(universe) -> dict[str, np.ndarray]:
    agg = prior_season_aggregates(universe.team_rows)
    agg["carry_net"] = SHRINK_LAMBDA * agg["mean_net"]
    agg["carry_env"] = SHRINK_LAMBDA * (agg["mean_env"] - agg["league_mean_env"])

    tr = universe.team_rows[["game_id", "team_id", "season"]].copy()
    tr = tr.merge(agg[["team_id", "target_season", "carry_net", "carry_env"]],
                  left_on=["team_id", "season"], right_on=["team_id", "target_season"],
                  how="left")
    # expansion teams and all 2021 rows have no prior season in-universe: carry = 0 exactly
    tr[["carry_net", "carry_env"]] = tr[["carry_net", "carry_env"]].fillna(0.0)

    g = attach_side(universe.games, tr, "carry_net", "cn_H", "cn_A", fill=0.0)
    g = attach_side(g, tr, "carry_env", "ce_H", "ce_A", fill=0.0)

    pc = prior_count(universe.team_rows, same_season=True)
    n = attach_side(universe.games, pc.rename(columns={"n_prior": "n"}), "n", "n_H", "n_A", fill=0.0)
    nmin = np.minimum(n["n_H"].to_numpy(float), n["n_A"].to_numpy(float))
    fade = np.maximum(0.0, 1.0 - nmin / FADE_K)

    return {"carryover_net_faded": fade * (g["cn_H"].to_numpy(float) - g["cn_A"].to_numpy(float)),
            "carryover_env_faded": fade * (g["ce_H"].to_numpy(float) + g["ce_A"].to_numpy(float)),
            "fade": fade, "n_min": nmin}


def _build(estimand: str, term: str):
    def build(universe, fold, cache=None):
        cache = {} if cache is None else cache
        t = cache.setdefault("terms", carryover_terms(universe))
        fc = {"shrink_lambda": SHRINK_LAMBDA, "fade_K": FADE_K,
              "expansion_and_2021_carry": 0.0,
              "s33_judgment_call": ("directional 'beta <= 0' kill REPLACED by a sign-consistency "
                                    "kill: the composite's EWMAs were measured continuous across "
                                    "seasons, so the correction's direction is not derivable a "
                                    "priori")}
        if fold["fold_id"] in DEACTIVATED_FOLDS:
            return linear_head(
                universe, estimand, {}, fold_constants=fc, deactivated=True,
                deactivation_reason=("declared fold_local_fallback (registered before results): "
                                     "carry = 0 identically on 2021-only training rows, so the "
                                     "TERM is dropped for this fold on BOTH sides; no row is "
                                     "dropped and coverage stays 100%"))
        return linear_head(universe, estimand, {term: t[term]}, fold_constants=fc)
    return build


KILLS = (
    f"early-subset failure: pooled Delta <= 0 on the {EARLY_SUBSET_PREDICATE} subset (measured "
    f"{EARLY_SUBSET_POOLED} pooled / 62-78 per test season); a pooled pass driven by the "
    "late-season complement is spurious and the arm dies regardless of the pooled number",
    "sign inconsistency: fitted beta does not carry the same sign in >= 3 of the 4 evaluable "
    "folds (train_lt_2023..train_lt_2026; fold 1 structurally deactivated)",
    "single-season dependence: leave-one-test-season-out receipt flips the early-subset Delta to "
    "<= 0",
)
RECEIPTS = ("early_subset_delta_table", "per_fold_coefficient_table",
            "leave_one_test_season_out_delta_table", "R-A1-EXCEPTIONS")

ELEMENTS = [
    ElementSpec(
        element_id="SC03_SEASON_CARRYOVER_PRIOR::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_EARLY_SEASON",
        card_sha256="0da4472b2c8aa052b6fc0ff220a2458673a28bbb928457ca3af552c2694b0dd8",
        build=_build("E2_FINAL_MARGIN_HOME", "carryover_net_faded"),
        kill_conditions=KILLS, mandatory_receipts=RECEIPTS,
        structurally_deactivated_folds=DEACTIVATED_FOLDS),
    ElementSpec(
        element_id="SC03_SEASON_CARRYOVER_PRIOR::E1_GAME_TOTAL", arm_id=ARM_ID,
        estimand="E1_GAME_TOTAL", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_EARLY_SEASON",
        card_sha256="95c0174b1078ad09634181c25a172a7964c547dc13521375e5012d78f7b070eb",
        build=_build("E1_GAME_TOTAL", "carryover_env_faded"),
        kill_conditions=KILLS, mandatory_receipts=RECEIPTS,
        structurally_deactivated_folds=DEACTIVATED_FOLDS),
]
