#!/usr/bin/env python3
"""features.py -- A08_league_lag_level feature construction (d_t, L_t).

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A08/ only. This module
touches nothing outside that directory and imports nothing from the shared runner except its
frozen constants (read-only).

Frozen construction, exactly as pinned by P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32), task_cards.A08 plus
shared_frozen_amendments.construction_pins:

  * pace(j) := lagged realised_team_off_possessions_reg_equiv (construction_pins
    .lagged_regulation_equivalent_pin), i.e. the REALIZED value of a COMPLETED prior game, used
    only as a historical observation feeding later rows' features -- never the target row's own
    realized outcome.
  * d_t (K0 lower-order term, shared verbatim across A08/A09/A10 by
    construction_pins.d_t_league_mean_pin):
        d_t(g,t) = mean_{j in P(t,<g)} pace(j) - Lbar_allprior(g)
    P(t,<g) = team t's own games strictly before game_date(g); ALL prior, no K-window (A08's
    K-window applies ONLY to L_t). Lbar_allprior(g) = mean of pace(j) over ALL contract-schedule
    team-game rows strictly before g -- ALL-PRIOR and K-FREE (construction_pins
    .d_t_league_mean_pin, verbatim).
    Empty-window convention (shared amendment, OPERATIONAL OP-2, applied identically here since
    d_t is the SAME shared column): d_t := 0 when the team has zero prior games (n_prior_own=0).
    Lbar_allprior(g) := 0 at the league's own start (zero strictly-earlier league rows exist) --
    the same empty-window symmetry, extended here because no frozen document names this single
    boundary row; recorded, not hidden.
  * L_t (A08 treatment; task_cards.A08 + P31 HYPOTHESES TS4):
        L_t(g;K) = Lbar_K(g;K) - Lbar_train(K)
    Lbar_K(g;K) = trailing mean of pace(j) over ALL team-game rows belonging to the last K
    completed league GAMES strictly before game_date(g), games ordered by (game_date, game_id)
    ascending and the last K taken (construction_pins.a08_window_tie_break, verbatim -- game
    granularity, not team-game granularity, for the K-count).
    FOLDS F1 / OPERATIONAL OP-3 (P35 A08 amendments, verbatim): rows whose game has fewer than K
    strictly-earlier completed league games take L_t := 0 directly (no row dropped), identically
    in arm and null.
    Lbar_train(K) = "training-fold constant" (P33/P31 formula text; the exact averaging formula is
    NOT spelled out character-for-character in any frozen document -- see REPORT.md). This module
    takes the single natural reading consistent with "centred on the training constant" (P31
    HYPOTHESES_timeseries_shrinkage.md TS4) and with RUNNER_INTERFACE.md's own worked example
    (A13's cbar_F, A17's imputation means: "computed from fold['train_idx'] rows ONLY, once per
    fold"): Lbar_train(K) := mean, over TRAINING rows whose K-window is FULLY DEFINED (>= K
    strictly-earlier league games), of that row's own Lbar_K(g;K). Training rows below the K
    floor are excluded from this average (they have no Lbar_K value to contribute); if NO
    training row has a fully-defined window, Lbar_train(K) := 0 and every training-fold row's L_t
    is 0 for that fold (recorded, not silently different).

None of this module touches real data, the SEALED_RESULTS tree, or any comparative performance
number. It is pure, deterministic array arithmetic over whatever frame is handed to it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GAME_ORDER_COLS = ("game_date", "game_id")


def _game_rank_map(history: pd.DataFrame) -> pd.DataFrame:
    """Dense rank of DISTINCT games by (game_date, game_id) ascending, 0-indexed.

    Deterministic, date-granular tie-break (construction_pins.a08_window_tie_break /
    .a26_loo_as_of_pin's sibling rule; LEAKAGE L6): ties broken by game_id, never by row order.
    """
    games = (history[list(GAME_ORDER_COLS)].drop_duplicates()
             .sort_values(list(GAME_ORDER_COLS), kind="mergesort")
             .reset_index(drop=True))
    games["game_rank"] = np.arange(len(games))
    return games


def build_history_index(history: pd.DataFrame, pace_col: str) -> dict:
    """Precompute per-game-rank league aggregates and per-team cumulative sums.

    `history` must carry at least: team_id, game_id, game_date, and `pace_col` (the realized
    lagged-use-only pace value of that historical row). Every aggregate here is STRICTLY
    backward-looking by construction: row i's contribution to any target row's feature requires
    row i's game_rank to be strictly less than the target's game_rank (enforced in
    `compute_features`, not here -- this function only builds the lookup tables).
    """
    h = history.copy()
    gmap = _game_rank_map(h)
    h = h.merge(gmap, on=list(GAME_ORDER_COLS), how="left")
    if h["game_rank"].isna().any():
        raise ValueError("internal: every history row must map to a game_rank")
    h = h.sort_values(["game_rank"], kind="mergesort").reset_index(drop=True)

    n_games = int(h["game_rank"].max()) + 1 if len(h) else 0
    game_sum = np.zeros(n_games)
    game_cnt = np.zeros(n_games)
    ranks = h["game_rank"].to_numpy(int)
    paces = h[pace_col].to_numpy(float)
    np.add.at(game_sum, ranks, paces)
    np.add.at(game_cnt, ranks, 1.0)
    cum_sum = np.cumsum(game_sum)          # cum_sum[r] = sum of pace over games 0..r inclusive
    cum_cnt = np.cumsum(game_cnt)

    # own-team cumulative EXCLUDING the current row, ordered by game_rank (strict, per-team)
    h_sorted = h.sort_values(["team_id", "game_rank"], kind="mergesort").reset_index(drop=True)
    grp = h_sorted.groupby("team_id", sort=False)
    own_prior_sum = grp[pace_col].cumsum().to_numpy() - h_sorted[pace_col].to_numpy()
    own_prior_cnt = grp.cumcount().to_numpy().astype(float)
    own_lookup = pd.DataFrame({
        "team_id": h_sorted["team_id"].to_numpy(),
        "game_rank": h_sorted["game_rank"].to_numpy(),
        "own_prior_sum": own_prior_sum,
        "own_prior_cnt": own_prior_cnt,
    }).set_index(["team_id", "game_rank"])
    if own_lookup.index.has_duplicates:
        raise ValueError("a team appears more than once in the same game_rank in `history`")

    return {"n_games": n_games, "cum_sum": cum_sum, "cum_cnt": cum_cnt,
            "own_lookup": own_lookup, "game_rank_map": gmap}


def compute_features(history: pd.DataFrame, targets: pd.DataFrame, K: int,
                     pace_col: str = "pace") -> dict:
    """d_t and (uncentered) L_t for every row of `targets`, strictly lagged.

    `targets` must carry: game_date, game_id, team_id (row order is preserved in the output).
    `history` is the CONTRACT-SCHEDULE source table (construction_pins.n_clock_pin: n counts and
    every aggregate here are built on the contract schedule, including the four
    universe-excluded 2021 opening-day rows when `history` is supplied as such); it must be a
    SUPERSET of the games appearing in `targets` (every target row's own game must itself be a
    history row, since a team's own current-game row is a legitimate row of the contract
    schedule; it never contributes to that row's OWN feature, only to LATER rows').
    """
    if K < 1:
        raise ValueError(f"K must be >= 1, got {K}")
    idx = build_history_index(history, pace_col)
    gmap = idx["game_rank_map"]
    tgt = targets.reset_index(drop=True).merge(gmap, on=list(GAME_ORDER_COLS), how="left")
    if tgt["game_rank"].isna().any():
        bad = tgt.loc[tgt["game_rank"].isna(), list(GAME_ORDER_COLS)]
        raise ValueError(f"target rows absent from the contract-schedule history: "
                         f"{bad.head(5).to_dict('records')}")

    ranks = tgt["game_rank"].to_numpy(int)
    team_ids = tgt["team_id"].to_numpy()
    n = len(tgt)

    cum_sum, cum_cnt = idx["cum_sum"], idx["cum_cnt"]
    own_lookup = idx["own_lookup"]

    n_prior_league = ranks.copy()                       # strictly-earlier GAMES, by construction
    windowed_defined = n_prior_league >= K

    all_prior_league_mean = np.zeros(n)
    d_t = np.zeros(n)
    n_prior_own = np.zeros(n, dtype=int)
    L_raw = np.zeros(n)

    for i in range(n):
        r = int(ranks[i])
        if r > 0:
            all_prior_league_mean[i] = cum_sum[r - 1] / cum_cnt[r - 1]
        else:
            all_prior_league_mean[i] = 0.0        # empty-window symmetry at the league's own start

        key = (team_ids[i], r)
        if key in own_lookup.index:
            row = own_lookup.loc[key]
            cnt = float(row["own_prior_cnt"])
            n_prior_own[i] = int(cnt)
            d_t[i] = 0.0 if cnt == 0 else (float(row["own_prior_sum"]) / cnt
                                           - all_prior_league_mean[i])
        else:
            raise ValueError(f"target row {i} (team_id={team_ids[i]!r}, game_rank={r}) is not a "
                             f"row of the supplied contract-schedule history; the history must be "
                             f"a superset of every target row's own game")

        if windowed_defined[i]:
            lo, hi = r - K, r - 1
            s = cum_sum[hi] - (cum_sum[lo - 1] if lo > 0 else 0.0)
            c = cum_cnt[hi] - (cum_cnt[lo - 1] if lo > 0 else 0.0)
            L_raw[i] = s / c
        else:
            L_raw[i] = 0.0

    return {"d_t": d_t, "L_raw": L_raw, "windowed_defined": windowed_defined,
            "n_prior_own": n_prior_own, "n_prior_league": n_prior_league,
            "all_prior_league_mean": all_prior_league_mean, "game_rank": ranks}


def center_L(L_raw: np.ndarray, windowed_defined: np.ndarray, train_mask: np.ndarray) -> tuple:
    """Lbar_train(K) and the centered L_t, per features.py module docstring's pinned reading."""
    train_defined = train_mask & windowed_defined
    lbar_train = float(np.mean(L_raw[train_defined])) if train_defined.any() else 0.0
    L_t = np.where(windowed_defined, L_raw - lbar_train, 0.0)
    return lbar_train, L_t
