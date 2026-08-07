#!/usr/bin/env python3
"""SC05_HCA_TEAM_OFFSETS -- EB-shrunk per-team home-advantage offsets. 1 element.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

FROZEN FORMULA (SPEC_V2 /arms/4, arm_block_sha256 9cec5eaa...):

  d_raw(team, d) = 0.5*(mean own margin, strictly-prior HOME games
                        - mean own margin, strictly-prior AWAY games) - HCA_lag(d)
  EB weight  w_i = tau2 / (tau2 + s_i2),   s_i2 = (var_m/n_home + var_m/n_away) / 4
  tau2 = max(0, var_between(d_raw) - mean(s_i2)) once per fold on TRAINING rows
         (deterministic method-of-moments, no optimizer)
  feature = w * d_raw of the HOME club;  y = a + b*C_margin + c*feature
  PINNED: >= 2 prior home AND >= 2 prior away else offset = 0; MoM formulas as stated.

HCA_lag(d) is SC04's construction, reused unchanged -- the card says "HCA_lag as in SC04", so the
two arms must not be allowed to drift apart, and this module imports SC04's function rather than
re-deriving it.

TWO INTERPRETIVE PINS, both declared here and raised to S37 rather than left implicit:

 (1) `var_m` is the pooled variance of team-game margins on the FOLD'S TRAINING ROWS. The card
     names var_m inside a per-fold training-time MoM formula and gives it no other definition;
     computing it on anything but training rows would leak the test fold's dispersion into a
     training constant.
 (2) tau2 and var_m are fold-TRAIN constants, while n_home / n_away are the row's OWN
     strictly-prior counts, so w varies by row. That is the only reading under which "feature =
     w*d_raw of the HOME club" is a per-game feature at all; the alternative (one w per team per
     fold) would need a team-level n the card never pins.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runner"))

from _head import linear_head  # noqa: E402
from estimators import fit_eb_shrinkage_mom  # noqa: E402
from features_common import prior_home_away_split  # noqa: E402
from runner_interface import ElementSpec  # noqa: E402
from sc04_hca_league_drift import hca_lag  # noqa: E402
from universe import attach_side  # noqa: E402

ARM_ID = "SC05_HCA_TEAM_OFFSETS"
FORMULA = ("EB-shrunk per-team home-advantage deviation vs the lagged league HCA; closed-form "
           "method-of-moments shrinkage, one fitted head coefficient")
SUPPORT_FLOOR_HOME = 2
SUPPORT_FLOOR_AWAY = 2


def _d_raw_and_counts(universe) -> dict:
    split = prior_home_away_split(universe.team_rows, value_col="margin")
    split["half_diff"] = 0.5 * (split["mean_home"].fillna(0.0) - split["mean_away"].fillna(0.0))
    split["supported"] = ((split["n_home"] >= SUPPORT_FLOOR_HOME) &
                          (split["n_away"] >= SUPPORT_FLOOR_AWAY)).astype(float)
    g = universe.games
    out = attach_side(g, split, "half_diff", "hd_H", "hd_A", fill=0.0)
    out = attach_side(out, split, "supported", "sup_H", "sup_A", fill=0.0)
    out = attach_side(out, split, "n_home", "nh_H", "nh_A", fill=0.0)
    out = attach_side(out, split, "n_away", "na_H", "na_A", fill=0.0)
    lag = hca_lag(universe)
    d_raw = out["hd_H"].to_numpy(float) - lag          # HOME club's deviation
    d_raw = np.where(out["sup_H"].to_numpy(float) > 0, d_raw, 0.0)
    return {"d_raw": d_raw, "n_home": out["nh_H"].to_numpy(float),
            "n_away": out["na_H"].to_numpy(float), "supported": out["sup_H"].to_numpy(float),
            "hca_lag": lag}


def build(universe, fold, cache=None):
    cache = {} if cache is None else cache
    p = cache.setdefault("parts", _d_raw_and_counts(universe))
    tr = fold["train_idx"]

    # var_m on the fold's TRAINING clusters only (interpretive pin 1)
    train_games = set(universe.games.iloc[tr]["game_id"])
    train_margins = universe.team_rows.loc[
        universe.team_rows["game_id"].isin(train_games), "margin"].to_numpy(dtype=float)
    var_m = float(np.var(train_margins, ddof=1))

    with np.errstate(divide="ignore", invalid="ignore"):
        s2 = np.where((p["n_home"] > 0) & (p["n_away"] > 0),
                      (var_m / np.maximum(p["n_home"], 1.0)
                       + var_m / np.maximum(p["n_away"], 1.0)) / 4.0,
                      np.inf)
    mom = fit_eb_shrinkage_mom(p["d_raw"][tr], s2[tr])
    tau2 = mom["tau2"]
    w = np.where(np.isfinite(s2) & (tau2 + s2 > 0), tau2 / (tau2 + s2), 0.0)
    feat = np.where(p["supported"] > 0, w * p["d_raw"], 0.0)

    return linear_head(
        universe, "E2_FINAL_MARGIN_HOME", {"hca_team_offset_shrunk": feat},
        fold_constants={"tau2_mom": tau2, "var_m_train": var_m,
                        "var_between_train": mom.get("var_between"),
                        "mean_s2_train": mom.get("mean_s2"),
                        "support_floor": f">= {SUPPORT_FLOOR_HOME} prior home AND "
                                         f">= {SUPPORT_FLOOR_AWAY} prior away else offset = 0",
                        "shrinkage_is_deterministic_mom_no_optimizer": True,
                        "interpretive_pin_var_m": "pooled variance of team-game margins on the "
                                                  "fold's TRAINING rows (raised to S37)",
                        "interpretive_pin_w_grain": "tau2 and var_m are fold-train constants; "
                                                    "n_home/n_away are the row's own "
                                                    "strictly-prior counts (raised to S37)",
                        "hca_lag_source": "SC04's construction, imported unchanged"})


KILLS = (
    "shrinkage collapse: 90th-percentile shrunk |offset| < 0.5 points in EVERY fold AND pooled "
    "Delta-MAE(E2) CI covers zero (the team component is empty; its residue is SC04's mechanism)",
    "pooled OOF Delta-MAE(E2) <= 0 vs K0_MATCHED (uncorrected)",
)

ELEMENTS = [
    ElementSpec(
        element_id="SC05_HCA_TEAM_OFFSETS::E2_FINAL_MARGIN_HOME", arm_id=ARM_ID,
        estimand="E2_FINAL_MARGIN_HOME", primary_metric="mae", arm_kind="substantive_feature",
        family_primary="FAM_S2_HOME_COURT",
        card_sha256="af06a2100b2a0d56e621200af3691582049daa266e816ab57524efd3106dc6de",
        build=build, kill_conditions=KILLS,
        mandatory_receipts=("per_fold_shrinkage_report", "delta_table", "R-A1-EXCEPTIONS"),
        notes=("dual partition registered on the card itself (S34 finding B7): A = {SC04, SC05}; "
               "B leaves {SC05} ALONE; must survive Holm under both",)),
]
