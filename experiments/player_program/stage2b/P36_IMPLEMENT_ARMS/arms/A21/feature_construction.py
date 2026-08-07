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

P37/PIN-A21 REMEDIATION (D039/D040 EXEC-M6/PIN-A21 ratified rulings; supersedes the prior
implementation flagged by auditor_3_arms_A14_A26 as finding A3-B2/B-2): the frozen phrase
"nc(t,g) = w-weighted share of t's offensive possessions in P(t,g) flagged
non_competitive_conservative" is IDENTICAL IN SHAPE to A17's own formula ("short_off(t,g) =
w-weighted share of t's offensive possessions in P(t,g) with duration_sec <= 8"), and D6 ("A17/
A19/A21/A22 decay h=10 lambda=0.5") binds A17 and A21 to the SAME shared trailing-evidence
convention family. The prior implementation computed a decayed weighted MEAN OF PER-GAME SHARES
(one "share" value per game, decay-weighted across games) -- a GAME-weighted construction. That is
NOT the literal reading: "a w-weighted share of t's offensive POSSESSIONS" denotes a ratio of two
decayed SUMS OF POSSESSION COUNTS (numerator: decayed sum of non_competitive_conservative
possession counts; denominator: decayed sum of ALL offensive possession counts) -- a
POSSESSION-weighted construction, identical in shape to A17's own `compute_prior_recency_
aggregates` recurrence (short_off_share = prior_short_off / prior_n_off). Measured divergence on
identical inputs, pre-remediation: 0.27 absolute on a [0,1] share (auditor 3, A3-B2). This module
now reuses A17's own recurrence SHAPE verbatim (per-game possession COUNTS aggregated first, then
a single decayed-sum ratio), substituting only the flagged-possession definition
(non_competitive_conservative in place of duration_sec <= 8); nothing about A17's own module is
imported or modified (each arm module in this program is self-contained; the shape is
re-derived here, not shared code).

DECAY KERNEL INDEXING (P37 finding A3-C4, "affirm one fleet convention on the record"): A17's own
Delta=1-indexed convention is adopted verbatim here, superseding this module's prior 0-indexed
convention (which the P37 audit verified was VALUE-IRRELEVANT for the old game-weighted mean --
it cancels in a normalised average -- but is NOT value-irrelevant for a decayed-SUM numerator/
denominator ratio, so the fleet convention must now be pinned exactly, not left as a labelling
choice): the game immediately preceding g has Delta_games = 1 (weight = base**1, base =
0.5**(1/half_life_games)), the one before that Delta_games = 2, and so on -- see A17's
feature_construction.py module docstring for the identical reasoning, restated here rather than
imported (self-contained modules).

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


_HISTORY_AGG_COLS = ("team_id", "game_id", "game_date", "season", "n_off", "n_nc_off")


def aggregate_possession_counts(possessions: pd.DataFrame) -> pd.DataFrame:
    """Collapse a possession-level frame to one row per (offense_team_id, game_id): the total
    offensive-possession COUNT and the COUNT of those possessions flagged
    non_competitive_conservative, plus the game's date/season for ordering.

    This is A17's own `aggregate_possession_counts` SHAPE (per-game possession COUNTS, not a
    per-game mean/share), re-derived here rather than imported (self-contained modules; see
    module docstring's P37/PIN-A21 remediation note). Deterministic and row-order independent (a
    groupby-aggregate keyed on identity columns, never on row position). Performs NO lagging
    itself -- lagging happens in `compute_prior_recency_aggregates` below.
    """
    g = possessions.groupby(["offense_team_id", "game_id"], sort=False)
    n_off = g.size().rename("n_off")
    n_nc_off = g["non_competitive_conservative"].sum().rename("n_nc_off")
    meta = g[["game_date", "season"]].first()
    out = (n_off.to_frame().join(n_nc_off).join(meta).reset_index()
           .rename(columns={"offense_team_id": "team_id"}))
    for c in ("n_off", "n_nc_off"):
        out[c] = out[c].astype(float)
    return out[list(_HISTORY_AGG_COLS)].reset_index(drop=True)


def compute_prior_recency_aggregates(history_agg: pd.DataFrame, *,
                                     half_life_games: float = HALF_LIFE_GAMES,
                                     season_boundary_discount: float = SEASON_BOUNDARY_DISCOUNT
                                     ) -> pd.DataFrame:
    """For every row of `history_agg` (one row per team-game), the recency- and season-discount-
    weighted SUM of that TEAM's own STRICTLY EARLIER games' offensive possession counts (total and
    non_competitive_conservative-flagged), and the resulting ratio share -- A17's own
    `compute_prior_recency_aggregates` recurrence SHAPE (re-derived here, not imported; see module
    docstring's P37/PIN-A21 remediation note), substituting only the flagged-possession definition.

    Recurrence: sort a team's own rows ascending by (game_date, game_id); maintain a running
    weighted sum; at each row, BEFORE adding that row's own counts, age the running sum by
    `base * season_boundary_discount ** (season[i] - season[i-1])`
    (base = 0.5**(1/half_life_games)), record the (now up-to-date) running sum as this row's PRIOR
    aggregate, then add this row's own raw counts unweighted (they enter at Delta_games = 1
    relative to the NEXT row) -- reproduces w(p) = base**Delta_games(p,g) *
    season_boundary_discount**(season(g)-season(p)) for every strictly-earlier own-team game p
    relative to target g, Delta_games(p,g) counted 1, 2, 3, ... back from g (A17's Delta=1-indexed
    convention, pinned fleet-wide by P37 finding A3-C4).

    Strict lagging is structural: row i's PRIOR aggregate is computed and returned BEFORE row i's
    own counts are folded into the running sum, so a row's own game NEVER contributes to its own
    feature, and no later game ever contributes.
    """
    for c in _HISTORY_AGG_COLS:
        if c not in history_agg.columns:
            raise A21ConstructionFailure(f"compute_prior_recency_aggregates requires column '{c}'")
    base = 0.5 ** (1.0 / float(half_life_games))

    h = history_agg.sort_values(["team_id", "game_date", "game_id"],
                                kind="mergesort").reset_index(drop=True)
    n = len(h)
    team_ids = h["team_id"].to_numpy()
    seasons = h["season"].to_numpy()
    v_n_off = h["n_off"].to_numpy(float)
    v_n_nc = h["n_nc_off"].to_numpy(float)

    prior_n_off = np.zeros(n)
    prior_n_nc = np.zeros(n)
    run_n_off = run_n_nc = 0.0
    prev_team = object()
    prev_season = None
    for i in range(n):
        t = team_ids[i]
        if t != prev_team:
            run_n_off = run_n_nc = 0.0
            prev_season = None
        if prev_season is not None:
            gap = seasons[i] - prev_season
            factor = base * (season_boundary_discount ** gap)
            run_n_off *= factor
            run_n_nc *= factor

        prior_n_off[i] = run_n_off
        prior_n_nc[i] = run_n_nc

        run_n_off += v_n_off[i]
        run_n_nc += v_n_nc[i]
        prev_team = t
        prev_season = seasons[i]

    defined = prior_n_off > 1e-12
    share = np.divide(prior_n_nc, prior_n_off, out=np.full(n, np.nan), where=defined)

    out = h[["team_id", "game_id", "game_date", "season"]].copy()
    out["prior_n_off"] = prior_n_off
    out["prior_n_nc"] = prior_n_nc
    out["share"] = share
    out["defined"] = defined
    return out.reset_index(drop=True)


def align_share(prior_agg: pd.DataFrame, team_id: np.ndarray, game_id: np.ndarray) -> np.ndarray:
    """Look up `share` (NaN where undefined -- an empty prior-game set) for an arbitrary
    (team_id, game_id) key array, aligned to input order (A17's `align_shares` pattern)."""
    lut = prior_agg.drop_duplicates(subset=["team_id", "game_id"]).set_index(["team_id", "game_id"])
    key = pd.MultiIndex.from_arrays([np.asarray(team_id), np.asarray(game_id)])
    missing = ~key.isin(lut.index)
    if missing.any():
        bad = list(zip(np.asarray(team_id)[missing][:5], np.asarray(game_id)[missing][:5]))
        raise A21ConstructionFailure(
            f"{int(missing.sum())} (team_id, game_id) target key(s) not found in the supplied "
            f"possession history (first few: {bad}); every target row's own game must itself be a "
            f"row of the supplied possessions frame")
    return lut.loc[key, "share"].to_numpy(dtype=float)


def compute_nc(possessions: pd.DataFrame, target: pd.DataFrame, *,
              half_life_games: float = HALF_LIFE_GAMES,
              season_boundary_discount: float = SEASON_BOUNDARY_DISCOUNT) -> dict:
    """Compute nc(t,g) and nc(opp(g,t),g) for every row of ``target``: a possession-weighted
    decayed-SUM ratio identical in shape to A17's short_off/short_def (P37/PIN-A21), strictly
    lagged, deterministic and row-order independent.

    Returns ``{"nc_own": ndarray, "nc_opp": ndarray}``, NaN where the corresponding side's
    prior-game set is empty (caller imputes per ``impute_empty_prior_set``).
    """
    missing_p = [c for c in REQUIRED_POSSESSION_COLS if c not in possessions.columns]
    if missing_p:
        raise A21ConstructionFailure(f"possessions frame is missing required columns {missing_p}")
    missing_t = [c for c in REQUIRED_TARGET_COLS if c not in target.columns]
    if missing_t:
        raise A21ConstructionFailure(f"target frame is missing required columns {missing_t}")

    history_agg = aggregate_possession_counts(possessions)
    prior_agg = compute_prior_recency_aggregates(
        history_agg, half_life_games=half_life_games,
        season_boundary_discount=season_boundary_discount)

    nc_own = align_share(prior_agg, target["team_id"].to_numpy(), target["game_id"].to_numpy())
    nc_opp = align_share(prior_agg, target["opponent_team_id"].to_numpy(),
                         target["game_id"].to_numpy())
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
