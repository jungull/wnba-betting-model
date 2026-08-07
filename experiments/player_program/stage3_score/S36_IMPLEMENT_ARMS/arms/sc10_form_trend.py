#!/usr/bin/env python3
"""SC10_FORM_TREND -- damped multi-horizon form spreads. 2 elements.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/8, arm_block_sha256 e52f1820...):

  per side/channel over SAME-SEASON strictly-prior games:
      L_short = EWMA half-life 4, L_med = EWMA half-life 12, L_long = expanding same-season mean
      s1 = L_short - L_long,  s2 = L_med - L_long
  E1: y = a + b*C_total  + c1*(s1env_H + s1env_A) + c2*(s2env_H + s2env_A)   [env = pts + opp_pts]
  E2: y = a + b*C_margin + c1*(s1net_H - s1net_A) + c2*(s2net_H - s2net_A)   [net = pts - opp_pts]
  ridge (prior mean 0) on c1, c2 with lambda from the pinned grid {4, 16, 64} by the pinned
  train-tail rule. Support floor 4 same-season prior games; spreads = 0 below it.

S33 FREEZE, carried: the slate's optional L_prevseason_shrunk third term is NOT included --
cross-season initialization is FAM_S2_EARLY_SEASON's habitat. Documented judgment call, not an
omission.

THE ORTHOGONALISATION COVARIATE (S34 finding B4) is registered with full lineage on this arm and
is DECLARED SEALED-VARIANT ONLY -- never in the primary head. `trailing_opponent_strength_diff`
below builds it, and `build` never puts it in a design; the orthogonalised variant is a separate
sealed receipt at S38. Building it here, and keeping it out of the head here, is what makes the
"declared kill-bearing sealed variant only" clause checkable at S37 instead of aspirational.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head, select_lambda_train_tail  # noqa: E402
from estimators import fit_ols  # noqa: E402
from features_common import (prior_count, prior_ewma,  # noqa: E402
                             prior_expanding_mean)
from runner_interface import ElementSpec  # noqa: E402
from universe import attach_side  # noqa: E402

ARM_ID = "SC10_FORM_TREND"
FORMULA = ("damped multi-horizon same-season spreads vs the season-to-date anchor, ridge-shrunk "
           "toward 0 with lambda from the pinned grid {4, 16, 64}")
HL_SHORT, HL_MED = 4.0, 12.0
SUPPORT_FLOOR = 4
LAMBDA_GRID = (4.0, 16.0, 64.0)


def _spreads(universe, channel: str) -> pd.DataFrame:
    """s1 = EWMA(hl 4) - expanding mean; s2 = EWMA(hl 12) - expanding mean, per (game, team)."""
    tr = universe.team_rows
    short = prior_ewma(tr, channel, halflife=HL_SHORT, same_season=True,
                       min_periods=SUPPORT_FLOOR, fill=np.nan)
    med = prior_ewma(tr, channel, halflife=HL_MED, same_season=True,
                     min_periods=SUPPORT_FLOOR, fill=np.nan)
    lng = prior_expanding_mean(tr, channel, same_season=True, fill=np.nan)
    pc = prior_count(tr, same_season=True)
    out = short[["game_id", "team_id"]].copy()
    out["s1"] = short["value"].to_numpy() - lng["value"].to_numpy()
    out["s2"] = med["value"].to_numpy() - lng["value"].to_numpy()
    below = pc["n_prior"].to_numpy() < SUPPORT_FLOOR
    out.loc[below, ["s1", "s2"]] = 0.0            # card: spreads = 0 below the support floor
    out[["s1", "s2"]] = out[["s1", "s2"]].fillna(0.0)
    return out


def spread_terms(universe) -> dict[str, np.ndarray]:
    net = _spreads(universe, "margin")
    env = _spreads(universe, "env")
    g = universe.games
    a = attach_side(g, net, "s1", "s1n_H", "s1n_A"); a = attach_side(a, net, "s2", "s2n_H", "s2n_A")
    a = attach_side(a, env, "s1", "s1e_H", "s1e_A"); a = attach_side(a, env, "s2", "s2e_H", "s2e_A")
    return {
        "form_spread_short_net": a["s1n_H"].to_numpy(float) - a["s1n_A"].to_numpy(float),
        "form_spread_med_net": a["s2n_H"].to_numpy(float) - a["s2n_A"].to_numpy(float),
        "form_spread_short_env": a["s1e_H"].to_numpy(float) + a["s1e_A"].to_numpy(float),
        "form_spread_med_env": a["s2e_H"].to_numpy(float) + a["s2e_A"].to_numpy(float),
    }


def trailing_opponent_strength_diff(universe, window: int = 4) -> np.ndarray:
    """DECLARED SEALED-VARIANT COVARIATE ONLY. Never enters the primary head.

    Mean strictly-prior season-to-date net rating of the opponents faced in each side's last-4
    window, minus the same mean over all that side's season opponents to date, differenced across
    sides. Opponent identity and home/away are read as as-of-cutoff schedule identity; no
    current-game row of any score column is consumed."""
    tr = universe.team_rows.sort_values(["team_id", "season", "game_date", "game_id"],
                                        kind="mergesort").copy()
    std = prior_expanding_mean(universe.team_rows, "margin", same_season=True, fill=0.0)
    key = {(g, t): v for g, t, v in zip(std["game_id"], std["team_id"], std["value"])}
    tr["opp_std"] = [key.get((g, o), 0.0) for g, o in zip(tr["game_id"], tr["opp_team_id"])]
    grp = tr.groupby(["team_id", "season"], sort=False)["opp_std"]
    last_w = grp.transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
    all_td = grp.transform(lambda s: s.shift(1).expanding().mean())
    tr["tosd"] = (last_w - all_td).fillna(0.0)
    a = attach_side(universe.games, tr, "tosd", "t_H", "t_A", fill=0.0)
    return a["t_H"].to_numpy(dtype=float) - a["t_A"].to_numpy(dtype=float)


def _build(estimand: str, t1: str, t2: str):
    def build(universe, fold, cache=None):
        cache = {} if cache is None else cache
        t = cache.setdefault("terms", spread_terms(universe))
        y = universe.games[estimand].to_numpy(dtype=float)
        C = universe.games["C_total" if estimand == "E1_GAME_TOTAL" else "C_margin"].to_numpy(float)
        X = np.column_stack([np.ones(len(y)), C, t[t1], t[t2]])
        penalise = np.array([False, False, True, True])   # ridge on the SPREAD coefficients only

        def fit_and_score(lam, inner, tail):
            f = fit_ols(X[inner], y[inner], ridge=lam, penalise=penalise)
            return float(np.mean(np.abs(y[tail] - X[tail] @ f.coef)))

        key = ("lambda", fold["fold_id"], estimand)
        sel = cache.setdefault(key, select_lambda_train_tail(fold["train_idx"], LAMBDA_GRID,
                                                             fit_and_score))
        return linear_head(
            universe, estimand, {t1: t[t1], t2: t[t2]},
            fold_constants={"halflives": {"short": HL_SHORT, "med": HL_MED},
                            "support_floor_same_season_prior_games": SUPPORT_FLOOR,
                            "lambda_selection": sel,
                            "ridge_applies_to": [t1, t2],
                            "ridge_prior_mean": 0.0,
                            "l_prevseason_shrunk_term": "NOT included (S33 freeze judgment call: "
                                                        "cross-season initialization is "
                                                        "FAM_S2_EARLY_SEASON's habitat)",
                            "orthogonalisation_covariate": "declared SEALED-VARIANT ONLY; never "
                                                           "in the primary head"})
    return build


KILLS = (
    "spread-block emptiness: 95% train-refit CI for every spread coefficient covers 0 in >= 4 of "
    "5 folds",
    "schedule confounding: pooled Delta <= 0 once the spread block is orthogonalized against the "
    "trailing-opponent-strength differential (declared sealed variant)",
    "pooled OOF Delta-MAE <= 0 vs K0_MATCHED (uncorrected)",
)
RECEIPTS = ("per_fold_spread_coefficient_table", "orthogonalized_variant_delta_receipt",
            "delta_table", "R-A1-EXCEPTIONS")

ELEMENTS = [
    ElementSpec(
        element_id="SC10_FORM_TREND::E1_GAME_TOTAL", arm_id=ARM_ID, estimand="E1_GAME_TOTAL",
        primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_FORM_DYNAMICS",
        card_sha256="eb1a816f666e07dd4d5dfc4293cef9ebf55ca229c81a7fe3618124831d72a07d",
        build=_build("E1_GAME_TOTAL", "form_spread_short_env", "form_spread_med_env"),
        kill_conditions=KILLS, mandatory_receipts=RECEIPTS),
    ElementSpec(
        element_id="SC10_FORM_TREND::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_FORM_DYNAMICS",
        card_sha256="7f0254b96ea2d26423d2bfdc970a189b600d509a479677aa01915bc430292625",
        build=_build("E2_FINAL_MARGIN_HOME", "form_spread_short_net", "form_spread_med_net"),
        kill_conditions=KILLS, mandatory_receipts=RECEIPTS,
        notes=("partition D FAM_S2_LAGGED_OWN_FORM = {SC10, SC12} also applies; must survive Holm "
               "under both",)),
]
