#!/usr/bin/env python3
"""feature_construction.py -- A21_garbage_time_contamination frozen feature construction.

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A21/ only.

Card (verbatim binding source): experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, verified at implementation
time), task_cards[].arm_id == "A21_garbage_time_contamination", carrying P33
PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072
d347d093) arm A21 by hash reference, amended exactly by the card's amendments_applied list.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

FROZEN FORMULA (P33 A21.formula, verbatim):
    nc(t,g) = w-weighted share of t's offensive possessions in P(t,g) flagged
              non_competitive_conservative
    x = (nc(t,g) + nc(opp(g,t),g)) / 2 ; 1 df

FROZEN HYPERPARAMETERS (P33 A21.hyperparameters.fixed; D6 restated verbatim in P33 notes.D6:
"A17/A19/A21/A22 decay h=10 lambda=0.5"):
    half_life_games           = 10    (exponential decay half-life, counted in GAMES back)
    season_boundary_discount  = 0.5   (multiplicative discount per season boundary crossed)
    both FIXED BY SOURCE; not enumerated, not tunable at P36 (P33 hyperparameters.enumerated={}).

IMPLEMENTATION AMBIGUITY DISCLOSED, NOT RESOLVED SILENTLY (parallel in kind to A07's own disclosed
n_i lag-kind choice, A07_early_season_transient.py docstring): the frozen record pins the two
decay NUMBERS above and the qualitative shape ("exponential decay ... season-boundary discount"),
but no frozen document spells out the exact per-game weighting KERNEL that combines them into one
scalar weight per historical game. This module uses:

    weight(j; g) = 0.5 ** ((rank_back(j; g) - 1) / half_life_games)
                 * season_boundary_discount ** max(0, season(g) - season(j))

  where rank_back(j; g) is the 1-indexed count-back among team t's own STRICTLY-EARLIER games,
  ordered (game_date, game_id) descending (rank_back = 1 is the most recent strictly-earlier
  game -- so decay_factor(rank_back=1) = 1.0, halving every 10 games back), and
  season(g) - season(j) is the (non-negative, because j is strictly earlier) integer count of
  season boundaries crossed under an integer season-numbering convention (matching every other
  season-keyed construction in this program, e.g. A07's n_i, A26's LOO strength-of-schedule).
  This is an IMPLEMENTATION LABELLING CHOICE with no effect on the two PINNED numbers
  (half_life_games=10, season_boundary_discount=0.5) or on the pinned formula's shape (a
  w-weighted share); it is recorded here and in REPORT.md for P37 to affirm or overrule (standing
  rule 1: frozen bytes govern over prose) -- nothing frozen names the kernel shape, so nothing is
  silently overridden.

STRICT LAGGING (own identity/synthetic tests: tests/TESTS.py::t02/t03): nc(t,g) is built ONLY from
team t's own games with game_date STRICTLY earlier than g's game_date (ties are excluded, matching
the (game_date, game_id) tie-break convention pinned elsewhere in this program's shared
construction_pins.a08_window_tie_break). No possession of game g itself, and no possession of any
game on or after g's date, enters nc(t,g) or nc(opp(g,t),g).

EMPTY-PRIOR-SET IMPUTATION (P35 A21 amendments "FOLDS F2: A17's empty-prior-set imputation rule
adopted identically"): when a side's prior-game set P(side) is empty (the team's first archive
appearance), that side's nc share is undefined (NaN here) and MUST be imputed by the caller as the
fold's TRAINING-row mean of the DEFINED nc values, computed ONCE per fold from the fold's
train_idx and held FIXED across every bootstrap refit -- identical machinery to A17, identical in
arm and null (the null carries no nc column at all, but the imputation CONSTANT itself must not
vary by bootstrap draw). ``impute_empty_prior_set`` below implements exactly this.

PRECONDITION (P33 A21 "precondition": "P23 franchise-continuity receipt"): franchise continuity is
enforced by the arm module's ``requires_franchise_continuity``/``p23_receipts`` hooks (arm_a21.py),
not by this feature-construction module, which is pure numpy/pandas arithmetic over whatever
possessions/target frames it is handed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HALF_LIFE_GAMES = 10.0
SEASON_BOUNDARY_DISCOUNT = 0.5

REQUIRED_POSSESSION_COLS = ("game_id", "game_date", "season", "offense_team_id",
                            "non_competitive_conservative")
REQUIRED_TARGET_COLS = ("team_id", "opponent_team_id", "game_id", "game_date", "season")


class A21ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No feature is returned."""


def _per_game_team_share(possessions: pd.DataFrame) -> pd.DataFrame:
    """One row per (offense_team_id, game_id): that team's OWN offensive-possession share of
    ``non_competitive_conservative`` in that one game, plus the game's date/season for ordering.

    Deterministic and row-order independent (a groupby-aggregate keyed on identity columns, never
    on row position).
    """
    g = possessions.groupby(["offense_team_id", "game_id"], sort=False)
    share = g["non_competitive_conservative"].mean()
    meta = g[["game_date", "season"]].first()
    out = share.to_frame("share").join(meta).reset_index()
    return out


def _decay_weighted_nc(per_game_by_team: dict, team_id, game_date, season,
                       half_life_games: float, season_boundary_discount: float) -> float:
    """nc(team_id, g) for ONE target row: decay-weighted mean of ``share`` over team_id's own
    games strictly before ``game_date``. NaN if the prior-game set is empty (caller imputes).

    ``per_game_by_team`` is ``{team_id: DataFrame sorted (game_date, game_id) ascending}`` -- built
    once by the caller so a per-row lookup here is a slice, not a full-frame filter (O(n log n)
    total rather than O(n^2)); this changes nothing about the VALUE computed, only its cost.
    """
    own = per_game_by_team.get(team_id)
    if own is None or own.empty:
        return float("nan")
    # own is sorted (game_date, game_id) ascending; strictly-earlier games are a prefix
    idx = np.searchsorted(own["game_date"].to_numpy(), game_date, side="left")
    prior = own.iloc[:idx]
    if prior.empty:
        return float("nan")
    # rank_back = 1 for the LAST row of `prior` (most recent strictly-earlier game)
    m = len(prior)
    rank_back = np.arange(m, 0, -1, dtype=float)
    decay = 0.5 ** ((rank_back - 1.0) / half_life_games)
    season_gap = np.maximum(0.0, float(season) - prior["season"].to_numpy(dtype=float))
    discount = season_boundary_discount ** season_gap
    w = decay * discount
    wsum = float(w.sum())
    if wsum <= 0.0:
        return float("nan")
    return float(np.dot(w, prior["share"].to_numpy(dtype=float)) / wsum)


def compute_nc(possessions: pd.DataFrame, target: pd.DataFrame, *,
              half_life_games: float = HALF_LIFE_GAMES,
              season_boundary_discount: float = SEASON_BOUNDARY_DISCOUNT) -> dict:
    """Compute nc(t,g) and nc(opp(g,t),g) for every row of ``target``, strictly lagged,
    deterministic and row-order independent.

    Returns ``{"nc_own": ndarray, "nc_opp": ndarray}``, NaN where the corresponding side's
    prior-game set is empty (caller imputes per ``impute_empty_prior_set``).
    """
    missing_p = [c for c in REQUIRED_POSSESSION_COLS if c not in possessions.columns]
    if missing_p:
        raise A21ConstructionFailure(f"possessions frame is missing required columns {missing_p}")
    missing_t = [c for c in REQUIRED_TARGET_COLS if c not in target.columns]
    if missing_t:
        raise A21ConstructionFailure(f"target frame is missing required columns {missing_t}")

    per_game = _per_game_team_share(possessions)
    per_game_by_team = {
        tid: grp.sort_values(["game_date", "game_id"], kind="mergesort").reset_index(drop=True)
        for tid, grp in per_game.groupby("offense_team_id", sort=False)
    }

    n = len(target)
    nc_own = np.empty(n, dtype=float)
    nc_opp = np.empty(n, dtype=float)
    team_id = target["team_id"].to_numpy()
    opp_id = target["opponent_team_id"].to_numpy()
    gdate = target["game_date"].to_numpy()
    season = target["season"].to_numpy()

    for i in range(n):
        nc_own[i] = _decay_weighted_nc(per_game_by_team, team_id[i], gdate[i], season[i],
                                       half_life_games, season_boundary_discount)
        nc_opp[i] = _decay_weighted_nc(per_game_by_team, opp_id[i], gdate[i], season[i],
                                       half_life_games, season_boundary_discount)
    return {"nc_own": nc_own, "nc_opp": nc_opp}


def impute_empty_prior_set(nc_own: np.ndarray, nc_opp: np.ndarray,
                           train_mask: np.ndarray) -> dict:
    """Frozen empty-window rule (A17's imputation, adopted identically for A21 -- P35 FOLDS F2): a
    NaN side is filled with the fold's TRAINING-row mean of the DEFINED nc values (own and opp
    pooled -- both are realisations of the SAME quantity, "share"), computed ONCE from
    ``train_mask``. Returns the filled columns plus the single imputation constant used (recorded
    for the receipt so the fixed-across-refits property is auditable).
    """
    nc_own = np.asarray(nc_own, dtype=float)
    nc_opp = np.asarray(nc_opp, dtype=float)
    train_mask = np.asarray(train_mask, dtype=bool)
    if train_mask.shape != nc_own.shape:
        raise A21ConstructionFailure(
            f"train_mask shape {train_mask.shape} does not match nc_own shape {nc_own.shape}")
    pooled_train = np.concatenate([nc_own[train_mask], nc_opp[train_mask]])
    defined_train = pooled_train[~np.isnan(pooled_train)]
    if defined_train.size == 0:
        raise A21ConstructionFailure(
            "no training-row nc value is defined in this fold; the empty-prior-set imputation "
            "constant is undefined and the fold must be treated as unevaluable, not silently "
            "filled with an arbitrary number")
    fill = float(defined_train.mean())
    own_filled = np.where(np.isnan(nc_own), fill, nc_own)
    opp_filled = np.where(np.isnan(nc_opp), fill, nc_opp)
    return {"nc_own": own_filled, "nc_opp": opp_filled, "imputation_constant": fill,
           "n_own_imputed": int(np.isnan(nc_own).sum()), "n_opp_imputed": int(np.isnan(nc_opp).sum())}


def contamination_share(nc_own_filled: np.ndarray, nc_opp_filled: np.ndarray) -> np.ndarray:
    """x = (nc(t,g) + nc(opp(g,t),g)) / 2 (P33 A21.formula, verbatim)."""
    return (np.asarray(nc_own_filled, dtype=float) + np.asarray(nc_opp_filled, dtype=float)) / 2.0
