#!/usr/bin/env python3
"""feature_construction.py -- A09_evidence_depth_adaptive_shrinkage feature construction.

Implements EXACTLY the pinned clocks/constructions the frozen P35 task card names for A09
(experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A09] amended by
shared_frozen_amendments.construction_pins):

  * ``lagged_regulation_equivalent_pin``: prior-game realized regulation-equivalent possessions
    (pace) := n_off_poss * 40 / (40 + 5*max(0, max_period - 4)).
  * ``d_t_league_mean_pin``: d_t's inner lagged league mean is ALL-PRIOR and K-FREE --
    Lbar_<g = mean of lagged pace over ALL completed league games strictly before game_date(g).
    d_t = mean_{j in P(t,<g)} pace(j) - Lbar_<g, where P(t,<g) is team t's own completed games
    strictly before g (ALL-PRIOR, i.e. NOT windowed by any K -- that is what makes d_t K-free and
    shared verbatim across A08/A09/A10, per the pin).
  * ``n_clock_pin``: n_t (P33 "n_prior_games") is counted on the CONTRACT SCHEDULE clock (every
    completed prior game the team has, including universe-excluded rows where present in the
    supplied frame). This module counts whatever rows the caller supplies as history; callers at
    real-fold time are responsible for supplying the contract-schedule frame, not the
    universe-excluded fit frame (P35 explicitly bars the universe-row clock for this count).
  * A09's own frozen ``fold_local_fallback``: d_t := 0 on the empty window (n_t == 0). This is a
    DETERMINISTIC SYMMETRIC rule, identical for every kappa element (P35 A09 card,
    ``p26_k0_record.fold_local_fallback``).
  * A09's frozen model (K0 K7 drafting-gap closure applied): the flat term beta0*d_t is explicit;
    the fitted treatment per kappa element is the adaptive-vs-flat CONTRAST column
    ``(w(n_t; kappa) - 1) * d_t``, w(n) = n/(n + kappa).

Every function here is a pure, deterministic transform of its inputs -- no I/O, no randomness, no
same-row (current-game) dependency. That last property (STRICT LAGGING) is what TESTS.py verifies
directly: a row's d_t/n_t depend only on OTHER rows with a strictly earlier game_date, never on
the row's own game outcome and never on any later game.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------------------- pace

def lagged_pace(n_off_poss, max_period) -> np.ndarray:
    """The frozen period-based regulation-equivalent possession construction.

    n_off_poss * 40 / (40 + 5*max(0, max_period - 4))  (P35 lagged_regulation_equivalent_pin).
    """
    n = np.asarray(n_off_poss, dtype=float)
    mp = np.asarray(max_period, dtype=float)
    denom = 40.0 + 5.0 * np.maximum(0.0, mp - 4.0)
    return n * 40.0 / denom


# ------------------------------------------------------------------------- strictly-prior sums

def _prior_sum_count_by_date(dates: np.ndarray, values: np.ndarray,
                             groups: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """For each row i, (prior_count[i], prior_sum[i]) = count/sum of `values` at rows whose
    `dates` are STRICTLY LESS than dates[i], optionally restricted to the same `groups` value.

    Same-date rows (of the same group, or globally when groups is None) NEVER count toward each
    other's prior aggregate -- this is what makes the construction leak-free under ties (e.g. two
    games, hence four team-rows, on the same calendar date). Deterministic, vectorised, no
    reliance on input row order.
    """
    n = len(dates)
    df = pd.DataFrame({"date": np.asarray(dates), "value": np.asarray(values, dtype=float)})
    key_cols = ["date"]
    if groups is not None:
        df["group"] = np.asarray(groups)
        key_cols = ["group", "date"]

    agg = df.groupby(key_cols, sort=True)["value"].agg(["sum", "count"])
    if groups is not None:
        cs = agg.groupby(level="group")[["sum", "count"]].cumsum()
    else:
        cs = agg[["sum", "count"]].cumsum()
    prior = cs - agg[["sum", "count"]]
    prior = prior.rename(columns={"sum": "prior_sum", "count": "prior_cnt"}).reset_index()

    df = df.reset_index().rename(columns={"index": "_orig_idx"})
    merged = df.merge(prior, on=key_cols, how="left")
    merged = merged.sort_values("_orig_idx", kind="mergesort")
    prior_cnt = merged["prior_cnt"].to_numpy(dtype=float)
    prior_sum = merged["prior_sum"].to_numpy(dtype=float)
    assert prior_cnt.shape[0] == n
    return prior_cnt, prior_sum


def compute_n_t_d_t(team_id, game_date, n_off_poss, max_period) -> tuple[np.ndarray, np.ndarray]:
    """n_t and d_t for every row of the supplied (history) frame, aligned to input row order.

    `team_id`, `game_date`, `n_off_poss`, `max_period` describe the CONTRACT-SCHEDULE history
    the caller supplies (real invocation: team_possession_prior_v1's own rows; tests: the
    synthetic archive). Every row of the input is simultaneously a TARGET row (its own n_t/d_t
    are returned) and potential HISTORY for later rows of the same or other teams -- exactly the
    K-free, all-prior construction the card pins.
    """
    team_id = np.asarray(team_id)
    game_date = np.asarray(game_date)
    pace = lagged_pace(n_off_poss, max_period)

    n_t, sum_own = _prior_sum_count_by_date(game_date, pace, groups=team_id)
    n_league, sum_league = _prior_sum_count_by_date(game_date, pace, groups=None)

    mean_own = np.divide(sum_own, n_t, out=np.zeros_like(sum_own), where=n_t > 0)
    mean_league = np.divide(sum_league, n_league, out=np.zeros_like(sum_league),
                            where=n_league > 0)
    raw_d_t = mean_own - mean_league
    d_t = np.where(n_t > 0, raw_d_t, 0.0)               # P35 A09 empty-window rule
    return n_t, d_t


def align_n_t_d_t_by_key(history: pd.DataFrame, target_keys: pd.DataFrame,
                         key_cols=("team_id", "game_id")) -> tuple[np.ndarray, np.ndarray]:
    """Compute n_t/d_t over `history` and align the result onto `target_keys`' row order.

    `history` must carry team_id, game_date, n_off_poss, max_period and the join key columns.
    `target_keys` carries the join key columns in the row order the caller wants n_t/d_t
    returned in (normally: the universe frame's own row order, since every fit-frame row is
    itself one of the history rows).
    """
    h = history.reset_index(drop=True).copy()
    n_t, d_t = compute_n_t_d_t(h["team_id"].to_numpy(), h["game_date"].to_numpy(),
                               h["n_off_poss"].to_numpy(), h["max_period"].to_numpy())
    h["_n_t"] = n_t
    h["_d_t"] = d_t
    key_cols = list(key_cols)
    lut = h[key_cols + ["_n_t", "_d_t"]].drop_duplicates(subset=key_cols)
    tk = target_keys[key_cols].reset_index(drop=True).copy()
    tk["_orig_order"] = np.arange(len(tk))
    merged = tk.merge(lut, on=key_cols, how="left")
    if merged["_n_t"].isna().any():
        missing = merged.loc[merged["_n_t"].isna(), key_cols].to_dict("records")
        raise KeyError(f"{len(missing)} target row(s) not found in the supplied history frame "
                       f"(first few: {missing[:3]}); n_t/d_t are undefined for a row that is not "
                       f"itself part of the contract-schedule history it is scored against")
    merged = merged.sort_values("_orig_order", kind="mergesort")
    return merged["_n_t"].to_numpy(dtype=float), merged["_d_t"].to_numpy(dtype=float)


# ------------------------------------------------------------------------------- pooling weight

def pooling_weight(n_t, kappa: float) -> np.ndarray:
    """w(n) = n / (n + kappa). kappa is FIXED per enumeration element, never fitted (P35
    multiplicity_recomputed.grid_element_regime_pinned)."""
    n_t = np.asarray(n_t, dtype=float)
    if kappa <= 0:
        raise ValueError(f"kappa must be > 0, got {kappa}")
    return n_t / (n_t + float(kappa))


def kappa_contrast(n_t, d_t, kappa: float) -> np.ndarray:
    """(w(n_t; kappa) - 1) * d_t -- the per-element treatment column (K0 K7 drafting closure:
    the null is w == 1, i.e. this contrast is identically 0, leaving only the flat beta0*d_t
    term)."""
    w = pooling_weight(n_t, kappa)
    return (w - 1.0) * np.asarray(d_t, dtype=float)


ENUMERATED_KAPPA: tuple[int, ...] = (2, 10, 50)          # frozen P35 A09 card elements
