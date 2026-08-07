#!/usr/bin/env python3
"""SC08_SIGMA_MARGIN_MAP -- matchup-varying dispersion on a frozen mean map. 1 element.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/6, arm_block_sha256 78bb3cee...):

  mu_hat  = a + b*C_margin      (per-fold train-OLS, FROZEN BEFORE any dispersion fit, identical
                                 on both sides)
  sigma_g^2 = sigma0^2 * exp(gamma1*z(pace_prior) + gamma2*z(sd20_H + sd20_A))
  p = Phi(mu_hat / sigma_g) clipped [0.001, 0.999]
  sigma parameters by Gaussian MLE on train margin residuals (deterministic Newton, pinned init:
  log sigma0 at train residual sd, gammas 0, tol 1e-10).
  K0: gamma1 = gamma2 = 0 (sigma0 only). Fitted: 3 (arm) / 1 (K0) dispersion parameters.

THIS IS THE ONE CARD IN THE SLATE WHOSE NULL IS `parameter_fixed_at_null`, not `term_removal`.
The identification is `mu-frozen`: mean and dispersion trade off in a probability-only fit, so
only the sigma parameters are free, and the mean map is fitted first and then held.

WHY THE GAME-LEVEL PACE AGGREGATION IS IMMATERIAL (measured, not asserted). The pinned pace
ingredient `projected_team_off_possessions` is per (game_id, team_id) and the card asks for a
"game-level" pace prior without naming sum or mean. It does not matter: the column is z-scored on
train moments, and z(sum) == z(2*mean) == z(mean) exactly, because z-scoring is invariant to a
positive scale factor. `tests/TESTS_arms.py` proves this to floating-point equality rather than
leaving it as a remark. The SUM is used.

THE 8 NaN. The byte pin records n_nan = 8 over 2,990 rows. This node measured those 8 to be
exactly the 4 games of 2021-05-14 (x2 sides) -- the D010 games the universe EXCLUDES -- so the
pace prior is resolved on all 1,491 universe games, matching the card's "measured resolved on all
1,491 universe games". `pace_prior()` asserts this rather than trusting it.

R_SC08_FLOOR (obligation O5) is MANDATORY and GATING here. Its absence is a card defect, not a
missing nice-to-have. `r_sc08_floor_receipt()` below is the builder; it compares two CONTROL
objects (this element's own K0 probability path and the frozen byte-pinned p_home column) and
never touches the challenger.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

import runner_constants as K  # noqa: E402
from _head import P_HOME_READING  # noqa: E402
from features_common import zscore_train  # noqa: E402
from obligations import (O5_BELOW_FLOOR_LABEL, O5_GATING_ON, O5_RECEIPT_ID)  # noqa: E402
from runner_interface import DesignPair, ElementSpec  # noqa: E402
from universe import attach_side  # noqa: E402

ARM_ID = "SC08_SIGMA_MARGIN_MAP"
FORMULA = ("frozen train-OLS mean map on C_margin plus a log-linear dispersion model in two "
           "z-scored pregame ingredients; p = Phi(mu_hat/sigma) clipped [0.001, 0.999]")
SD_WINDOW = 20
SD_SUPPORT_FLOOR = 4
P_CLIP = K.E3_P_CLIP


SYNTHETIC_PACE_COL = "_synthetic_pace_prior"


def pace_prior(universe) -> np.ndarray:
    """Game-level pace ingredient = sum of the two sides' projected_team_off_possessions.

    A synthetic frame has no rows in the pinned possession artifact, so a test fixture may supply
    its own column under `_synthetic_pace_prior`. That branch is guarded: it is refused outright
    on a frame carrying the real game_id digest, so a synthetic stand-in can never be substituted
    for the byte-pinned ingredient on the real universe."""
    if SYNTHETIC_PACE_COL in universe.games.columns:
        if universe.game_id_digest != "SYNTHETIC_NOT_A_REAL_DIGEST":
            raise ValueError(
                "a synthetic pace column was supplied on a frame carrying a real game_id digest; "
                "the pinned ingredient may never be stood in for. HALT.")
        return universe.games[SYNTHETIC_PACE_COL].to_numpy(dtype=float)
    tp = pd.read_parquet(K.artifact_path(
        "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet"))
    tp["game_id"] = tp["game_id"].astype(str)
    tp["team_id"] = tp["team_id"].astype("int64")
    g = attach_side(universe.games, tp, "projected_team_off_possessions", "pp_H", "pp_A",
                    fill=np.nan)
    tot = g["pp_H"].to_numpy(dtype=float) + g["pp_A"].to_numpy(dtype=float)
    n_bad = int(np.sum(~np.isfinite(tot)))
    if n_bad:
        raise ValueError(
            f"the pinned pace prior is unresolved on {n_bad} UNIVERSE clusters. The card measures "
            f"it resolved on all 1,491; the 8 NaN in the pin belong to the D010-excluded "
            f"2021-05-14 games. HALT rather than impute an undeclared value.")
    return tot


def lagged_margin_sd_sum(universe) -> np.ndarray:
    """sd20_H + sd20_A: per-side rolling sd of the last <= 20 strictly-prior own settled margins.

    Below the >= 4 support floor the card's fallback is the TRAIN pooled margin sd; that constant
    is a fold quantity, so the raw column carries NaN here and `build` fills it per fold. The
    card measures the fallback touching 36 of 1,491 clusters."""
    from features_common import prior_rolling_sd
    sd = prior_rolling_sd(universe.team_rows, "margin", window=SD_WINDOW,
                          min_periods=SD_SUPPORT_FLOOR)
    g = attach_side(universe.games, sd, "value", "sd_H", "sd_A", fill=np.nan)
    return g["sd_H"].to_numpy(dtype=float), g["sd_A"].to_numpy(dtype=float)


def build(universe, fold, cache=None):
    cache = {} if cache is None else cache
    tr = fold["train_idx"]
    pace = cache.setdefault("pace", pace_prior(universe))
    sd_h, sd_a = cache.setdefault("sd", lagged_margin_sd_sum(universe))

    train_games = set(universe.games.iloc[tr]["game_id"])
    pooled_sd = float(np.std(universe.team_rows.loc[
        universe.team_rows["game_id"].isin(train_games), "margin"].to_numpy(dtype=float), ddof=1))
    sd_sum = np.nan_to_num(sd_h, nan=pooled_sd) + np.nan_to_num(sd_a, nan=pooled_sd)
    n_fallback = int(np.sum(~np.isfinite(sd_h) | ~np.isfinite(sd_a)))

    z_pace, m_pace = zscore_train(pace, tr)
    z_sd, m_sd = zscore_train(sd_sum, tr)

    g = universe.games
    n = len(g)
    columns = {"intercept": np.ones(n), "composite_pred_margin": g["C_margin"].to_numpy(float),
               "sigma_z_pace_prior": z_pace, "sigma_z_lagged_margin_sd": z_sd}
    return DesignPair(
        columns=columns,
        arm_cols=("intercept", "composite_pred_margin",
                  "sigma_z_pace_prior", "sigma_z_lagged_margin_sd"),
        k0_cols=("intercept", "composite_pred_margin"),
        treatment_cols=("sigma_z_pace_prior", "sigma_z_lagged_margin_sd"),
        structural_cols=("composite_pred_margin",),
        comparison="parameter_fixed_at_null",
        fold_constants={
            "mean_map": "a + b*C_margin, per-fold train-OLS, FROZEN before any dispersion fit, "
                        "identical on both sides",
            "identification": "mu-frozen: only sigma parameters are free",
            "sd_window": SD_WINDOW, "sd_support_floor": SD_SUPPORT_FLOOR,
            "sd_fallback_train_pooled_sd": pooled_sd,
            "sd_fallback_clusters_this_fold": n_fallback,
            "z_moments_train_only": {"pace": m_pace, "sd_sum": m_sd},
            "pace_aggregation": "SUM of the two sides' projected_team_off_possessions; z-scoring "
                                "makes sum vs mean bit-identical (proved in TESTS_arms)",
            "p_clip": list(P_CLIP),
            "ot_rate_inflation": "folded into sigma0 (declared simplification)",
            "newton_init": "log sigma0 at train residual sd, gammas 0, tol 1e-10",
            "null_construction": "parameter_fixed_at_null (gamma1 = gamma2 = 0)",
            "p_home_reading": P_HOME_READING})


def r_sc08_floor_receipt(k0_brier, floor_brier, *, per_fold=None,
                         n_matched_universe=None, n_structural_nan_p_home=None) -> dict:
    """Build the MANDATORY R_SC08_FLOOR receipt (obligation O5).

    Both inputs are CONTROL objects: (i) this element's own K0_MATCHED probability path
    Phi(mu_hat/sigma0), and (ii) the frozen store's byte-pinned p_home column, on the identical
    matched universe string with identical handling of the 188 structural NaN p_home rows. THE
    CHALLENGER'S NUMBER IS NOT PART OF THIS RECEIPT -- that is the card's own sentence, and it is
    why this builder takes no challenger argument at all.

    S36 never calls this with real numbers; it exists so that the receipt is IMPLEMENTED and
    schema-tested before S38, and so that its absence cannot be discovered late."""
    below_floor = None
    if k0_brier is not None and floor_brier is not None:
        below_floor = not (float(k0_brier) < float(floor_brier))
    return {
        "schema": "s36_r_sc08_floor/1", "receipt_id": O5_RECEIPT_ID, "mandatory": True,
        "gating_on": O5_GATING_ON,
        "both_objects_are_controls": True, "challenger_number_included": False,
        "k0_matched_brier": k0_brier, "frozen_p_home_brier": floor_brier,
        "per_fold": per_fold or {},
        "n_matched_universe": n_matched_universe,
        "n_structural_nan_p_home": n_structural_nan_p_home,
        "identical_nan_handling_required": True,
        "k0_below_floor": below_floor,
        "verdict_label_if_below_floor": O5_BELOW_FLOOR_LABEL,
        "consequences_if_below_floor": [
            "the label is inseparable from every citation of the result",
            "the element is never counted in any unqualified pass tally",
            "S40 routes any would-be promotion to the S42 USER gate rather than promoting it",
            "the element additionally reports (non-gating) its metric against the D045 floor "
            "recomputed on its exact universe"],
        "absence_is_a_card_defect": True,
        "floor_bar_discipline": ("this receipt references the floor ARTIFACT COLUMN, prints no "
                                 "floor or bar VALUE, and is a LABELLING rule, not a kill, "
                                 "stopping rule, coverage predicate or grid choice"),
    }


KILLS = (
    "dispersion-spread inertness: ratio of 90th to 10th percentile predicted sd_margin < 1.15 "
    "pooled",
    "fictitious variance signal: pooled slope of squared OOF margin residuals on sigma_hat^2 has "
    "95% CI excluding 1 on the low side AND Delta-Brier <= 0",
    "calibration harm: the contract-mandated 10-bin calibration table shows the arm worse than K0 "
    "in >= 6 of 10 bins, regardless of pooled Delta-Brier sign",
)

ELEMENTS = [
    ElementSpec(
        element_id="SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB", arm_id=ARM_ID,
        estimand="E3_HOME_WIN_PROB", primary_metric="brier_raw_model_probability",
        arm_kind="substantive_feature", family_primary="FAM_S2_DISPERSION",
        card_sha256="348ddc3287230bf29428dd6cc33280c9b0e3af8508811d28743f61a13a749d8e",
        build=build, kill_conditions=KILLS,
        mandatory_receipts=("R_SC08_FLOOR", "dispersion_spread_diagnostic_per_fold",
                            "variance_calibration_slope_per_fold", "ten_bin_calibration_table",
                            "R-A1-EXCEPTIONS"),
        notes=("R_SC08_FLOOR is MANDATORY and GATING on this element; absence is a card defect",
               "verdict label is CONDITIONAL on that receipt: the unqualified feature-value label "
               "requires this K0 to reach the public floor")),
]
