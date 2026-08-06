#!/usr/bin/env python3
"""feature_construction.py -- A17_transition_mix_share feature construction (short_off, short_def, x).

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A17/ only. This module
touches nothing outside that directory and performs no cross-arm import (each arm module in this
tree is self-contained -- A08/A09/A11 independently re-derive their own shared formulas rather
than importing one another; this module follows the same convention).

Implements EXACTLY the pinned construction the frozen P35 task card names for A17
(experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A17_transition_mix_
share]), carried by hash reference from P33_PREREGISTRATION_DRAFT/SPEC.json (sha256
066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) arms[A17] plus the P31
HYPOTHESES_cutoff_leakage.md CUTOFF_LEAKAGE_H1 formula sketch the P33 record is built from
(read-only cross-reference; not itself a frozen node input, cited for the arithmetic P33/P35 do
not spell out in closed form -- see the module-level ambiguity note at the bottom of this
docstring and REPORT.md).

  * Mechanism (P33 arms[A17].mechanism, verbatim): "trailing transition share (possessions <= 8 s)
    carries tempo information scalar pace averages away."
  * Formula (P33 arms[A17].formula, verbatim):
        short_off(t,g) = w-weighted share of t's offensive possessions in P(t,g) with
                          duration_sec <= 8
        x = (short_off(t,g) + short_def(opp(g,t),g)) / 2                      -- 1 df
        weights: exponential decay half-life 10 games, season-boundary discount 0.5, FIXED
    P(t,g) = team t's own contract-schedule games with game_date STRICTLY before game_date(g)
    (P31 HYPOTHESES_cutoff_leakage.md section 0, the shared lag operator L every H1-family
    hypothesis inherits). short_def(t,g) is the same construction over t's DEFENSIVE possessions
    (possessions ALLOWED, i.e. rows where defense_team_id = t) -- P33 formula, verbatim
    ("short_def(t,g) = same with defense_team_id = t").
  * short_threshold_sec = 8, half_life_games = 10, season_boundary_discount = 0.5:
    task_cards.A17 (P35, carried from P33 hyperparameters.fixed) -- "all constants frozen by
    source; not tunable".
  * P35 amendment FOLDS F2 (empty-prior-set imputation, verbatim): "a team-side trailing share
    with an EMPTY prior-game set imputes that side's share := the fold's TRAINING-row mean of the
    defined values of that share, computed once per fold, held fixed across bootstrap refits,
    identical in arm and null (numeric trigger |P| = 0; 7 offense-side rows / 5 clusters measured,
    incl. fold-4/5 TEST rows)". This module computes the RAW (possibly-undefined) short_off/
    short_def arrays and a definedness mask per side; the per-fold training-mean imputation itself
    is a FOLD-LOCAL operation and lives in the arm module's build_design (RUNNER_INTERFACE.md
    section 3: "training-fold-computed constants ... A17's imputation means ... computed from
    fold['train_idx'] rows ONLY, once per fold" -- RUNNER_INTERFACE.md names A17 by name as its
    own worked example of this convention).

AMBIGUITY FLAGGED FOR P37 (not resolved silently; documented per standing rule, matching the
precedent A08/features.py sets for its own Lbar_train reading): no frozen document spells out, in
closed form, what "exponential decay ... by game recency" means at the level of an exact discrete
index -- specifically, how many "games back" the game IMMEDIATELY PRECEDING g counts as. This
module pins the reading:

    Delta_games(p, g) := the number of team t's own contract-schedule games separating game p
    (exclusive) from game g (exclusive), COUNTING p's own game as 1 -- i.e. the game immediately
    preceding g has Delta_games = 1, the one before that has Delta_games = 2, and so on. This is
    the "how many games ago was this game played" reading of "game recency" (p was played
    "1 game ago" relative to g, never "0 games ago" -- the target game itself, at true distance 0,
    is definitionally excluded from P(t,g)).
    w(p) = 0.5 ** (Delta_games(p, g) / 10) * 0.5 ** (season(g) - season(p))

The alternative 0-indexed reading (immediately-preceding game at full weight 1, i.e.
Delta_games := Delta_games_here - 1) is equally defensible from the prose alone and is NOT ruled
out by any frozen byte in this program; no implementation of this weighting scheme exists
anywhere else in the repository to disambiguate it (grepped: no "half_life"/"season_boundary"/
"decay" hits outside the P31/P32/P33 prose). Both readings are deterministic, symmetric in arm
and null (the weighting is a NUISANCE-FREE property of the treatment column alone), and preregi-
stered before any fit; this module commits to the closed-form reading stated above and flags the
alternative for P37 adjudication, exactly as A08/features.py flags its own Lbar_train reading.

The recurrence below computes both quantities in closed form for every history row in one pass
per team (see `compute_prior_recency_aggregates`); the algebra is checked directly against the
naive O(n^2) double-sum definition in TESTS_A17.py::t02b_recency_weight_matches_naive_definition.

None of this module touches real data, the SEALED_RESULTS tree, or any comparative performance
number. It is pure, deterministic array arithmetic over whatever frame is handed to it.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SHORT_THRESHOLD_SEC = 8.0        # task_cards.A17.hyperparameters.fixed.short_threshold_sec
HALF_LIFE_GAMES = 10.0           # task_cards.A17.hyperparameters.fixed.half_life_games
SEASON_BOUNDARY_DISCOUNT = 0.5   # task_cards.A17.hyperparameters.fixed.season_boundary_discount

_HISTORY_AGG_COLS = ("team_id", "game_id", "game_date", "season",
                     "n_off", "n_short_off", "n_def", "n_short_def")


def _recency_weight_base(half_life_games: float) -> float:
    """base**1 == 0.5**(1/half_life_games): the per-game-step decay factor before any season
    crossing is applied. base**half_life_games == 0.5 exactly (the half-life property)."""
    return 0.5 ** (1.0 / float(half_life_games))


def aggregate_possession_counts(possessions: pd.DataFrame,
                                short_threshold_sec: float = SHORT_THRESHOLD_SEC) -> pd.DataFrame:
    """Collapse a possession-level frame to one row per (team_id, game_id): offensive and
    defensive possession counts and short-possession (duration_sec <= threshold) counts.

    `possessions` must carry: game_id, game_date, season, offense_team_id, defense_team_id,
    duration_sec (P33 arms[A17].features: "offense_team_id / defense_team_id / game_date" plus
    the lagged duration_sec share; S8 table: season_type/game_date ELIGIBLE, duration_sec
    LAGGED_USE_ONLY -- P22 proof lagged prior-game duration passes). This function performs NO
    lagging itself -- it is a pure same-row aggregation; lagging (restricting to STRICTLY earlier
    games) happens in `compute_prior_recency_aggregates` below, which only ever reads a game's own
    row as a candidate PRIOR contribution to a STRICTLY LATER target row.
    """
    required = ("game_id", "game_date", "season", "offense_team_id", "defense_team_id",
                "duration_sec")
    for c in required:
        if c not in possessions.columns:
            raise KeyError(f"aggregate_possession_counts requires column '{c}'")
    short = (possessions["duration_sec"].to_numpy(float) <= float(short_threshold_sec))

    off = (possessions.assign(_short=short)
           .groupby(["offense_team_id", "game_id", "game_date", "season"], sort=False)
           .agg(n_off=("_short", "size"), n_short_off=("_short", "sum"))
           .reset_index().rename(columns={"offense_team_id": "team_id"}))
    dfn = (possessions.assign(_short=short)
           .groupby(["defense_team_id", "game_id", "game_date", "season"], sort=False)
           .agg(n_def=("_short", "size"), n_short_def=("_short", "sum"))
           .reset_index().rename(columns={"defense_team_id": "team_id"}))

    merged = off.merge(dfn, on=["team_id", "game_id", "game_date", "season"], how="outer")
    for c in ("n_off", "n_short_off", "n_def", "n_short_def"):
        merged[c] = merged[c].fillna(0.0).astype(float)
    return merged[list(_HISTORY_AGG_COLS)].reset_index(drop=True)


def compute_prior_recency_aggregates(history_agg: pd.DataFrame, *,
                                     half_life_games: float = HALF_LIFE_GAMES,
                                     season_boundary_discount: float = SEASON_BOUNDARY_DISCOUNT
                                     ) -> pd.DataFrame:
    """For every row of `history_agg` (one row per team-game), compute the recency- and
    season-discount-weighted sum of that TEAM's own STRICTLY EARLIER games' offensive and
    defensive (short and total) possession counts, and the resulting shares.

    Recurrence (derived and checked against the closed-form double sum in TESTS_A17.py): sort a
    team's own rows ascending by (game_date, game_id); maintain a running weighted sum; at each
    row, BEFORE adding that row's own counts, age the running sum by
    `base * season_boundary_discount ** (season[i] - season[i-1])` (base = 0.5**(1/half_life_games)),
    record the (now up-to-date) running sum as this row's PRIOR aggregate, then add this row's own
    raw counts unweighted (they enter at Delta_games = 1 relative to the NEXT row). This reproduces
    w(p) = base**Delta_games(p,g) * season_boundary_discount**(season(g)-season(p)) for every
    strictly-earlier own-team game p relative to target g, with Delta_games(p,g) counted 1, 2, 3,
    ... back from g (see module docstring's pinned convention).

    Strict lagging is structural: row i's PRIOR aggregate is computed and returned BEFORE row i's
    own counts are folded into the running sum, so a row's own game NEVER contributes to its own
    feature, and no later game ever contributes (the running sum only ever accumulates rows already
    visited in ascending date order).
    """
    for c in _HISTORY_AGG_COLS:
        if c not in history_agg.columns:
            raise KeyError(f"compute_prior_recency_aggregates requires column '{c}'")
    base = _recency_weight_base(half_life_games)

    h = history_agg.sort_values(["team_id", "game_date", "game_id"], kind="mergesort").reset_index(drop=True)
    n = len(h)
    team_ids = h["team_id"].to_numpy()
    seasons = h["season"].to_numpy()
    v_n_off = h["n_off"].to_numpy(float)
    v_short_off = h["n_short_off"].to_numpy(float)
    v_n_def = h["n_def"].to_numpy(float)
    v_short_def = h["n_short_def"].to_numpy(float)

    prior_n_off = np.zeros(n)
    prior_short_off = np.zeros(n)
    prior_n_def = np.zeros(n)
    prior_short_def = np.zeros(n)

    run_n_off = run_short_off = run_n_def = run_short_def = 0.0
    prev_team = object()
    prev_season = None
    for i in range(n):
        t = team_ids[i]
        if t != prev_team:
            run_n_off = run_short_off = run_n_def = run_short_def = 0.0
            prev_season = None
        if prev_season is not None:
            gap = seasons[i] - prev_season
            factor = base * (season_boundary_discount ** gap)
            run_n_off *= factor
            run_short_off *= factor
            run_n_def *= factor
            run_short_def *= factor

        prior_n_off[i] = run_n_off
        prior_short_off[i] = run_short_off
        prior_n_def[i] = run_n_def
        prior_short_def[i] = run_short_def

        run_n_off += v_n_off[i]
        run_short_off += v_short_off[i]
        run_n_def += v_n_def[i]
        run_short_def += v_short_def[i]
        prev_team = t
        prev_season = seasons[i]

    off_defined = prior_n_off > 1e-12
    def_defined = prior_n_def > 1e-12
    short_off_share = np.divide(prior_short_off, prior_n_off,
                                out=np.full(n, np.nan), where=off_defined)
    short_def_share = np.divide(prior_short_def, prior_n_def,
                                out=np.full(n, np.nan), where=def_defined)

    out = h[["team_id", "game_id", "game_date", "season"]].copy()
    out["prior_n_off"] = prior_n_off
    out["prior_short_off"] = prior_short_off
    out["prior_n_def"] = prior_n_def
    out["prior_short_def"] = prior_short_def
    out["short_off_share"] = short_off_share
    out["short_off_defined"] = off_defined
    out["short_def_share"] = short_def_share
    out["short_def_defined"] = def_defined
    return out.reset_index(drop=True)


def align_shares(prior_agg: pd.DataFrame, team_id: np.ndarray, game_id: np.ndarray) -> dict:
    """Look up (short_off_share, short_off_defined, short_def_share, short_def_defined) for an
    arbitrary (team_id, game_id) key array, aligned to input order. Used both for a target row's
    OWN team (short_off(t,g)) and for its OPPONENT (short_def(opp(g,t),g)) -- the opponent has its
    own row in `prior_agg` for the SAME game_id (both teams of a game share one game_id), so its
    prior aggregate is, by construction, evaluated AS OF THE SAME game_date as the target row.
    """
    lut = prior_agg.drop_duplicates(subset=["team_id", "game_id"]).set_index(["team_id", "game_id"])
    key = pd.MultiIndex.from_arrays([np.asarray(team_id), np.asarray(game_id)])
    missing = ~key.isin(lut.index)
    if missing.any():
        bad = list(zip(np.asarray(team_id)[missing][:5], np.asarray(game_id)[missing][:5]))
        raise KeyError(f"{int(missing.sum())} (team_id, game_id) target key(s) not found in the "
                       f"supplied history aggregate (first few: {bad}); every target row's own "
                       f"game must itself be a row of the supplied possession history")
    rows = lut.loc[key]
    return {
        "short_off_share": rows["short_off_share"].to_numpy(float),
        "short_off_defined": rows["short_off_defined"].to_numpy(bool),
        "short_def_share": rows["short_def_share"].to_numpy(float),
        "short_def_defined": rows["short_def_defined"].to_numpy(bool),
    }
