#!/usr/bin/env python3
"""feature_construction.py -- A11_carryover_blend_rho feature construction (dcur_t, dprev_t,
dblend_t(rho)).

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A11/ only. This module
touches nothing outside that directory and performs no cross-arm import (each arm module in this
tree is self-contained; A08/A09 independently re-derive the shared pace/league-mean formula
rather than importing one another, and this module follows the same convention).

Implements EXACTLY the pinned clocks/constructions the frozen P35 task card names for A11
(experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A11] amended by
a11_repair and shared_frozen_amendments.construction_pins):

  * ``lagged_regulation_equivalent_pin``: prior-game realized regulation-equivalent possessions
    (pace) := n_off_poss * 40 / (40 + 5*max(0, max_period - 4)).
  * ``d_t_league_mean_pin``: the inner lagged league mean Lbar_<g used by dcur_t AND dprev_t is
    ALL-PRIOR and K-FREE -- Lbar_<g = mean of lagged pace over ALL completed league games
    strictly before game_date(g). Same-date rows never count toward each other's prior
    aggregate (leak-free under date ties).
  * ``n_clock_pin``: every prior-game COUNT (n_cur, m_prev) is computed on the CONTRACT SCHEDULE
    clock -- the caller is responsible for supplying the contract-schedule history frame at
    real-fold time, not the universe-excluded fit frame; this module counts whatever rows the
    caller supplies as history.
  * A11's own model (a11_repair, verbatim):
      dblend_t(rho) = (n_cur*dcur_t + rho*m_prev*dprev_t) / (n_cur + rho*m_prev)
    where:
      - dcur_t(g)  = mean_{j in team t's CURRENT-SEASON games strictly before game_date(g)}
                     pace(j) - Lbar_<g ; n_cur(g) = the count of those games.
      - dprev_t(g) = mean_{j in team t's ENTIRE IMMEDIATELY-PRECEDING season} pace(j) - Lbar_<g ;
                     m_prev(g) = the count of those games. The preceding season is, by
                     construction, entirely in the past by the time the current season starts,
                     so using ALL of it (not date-restricted) introduces no forward leakage.
      - rho is FIXED per enumeration element (0.25, 0.5, 0.75), never fitted; the K0_MATCHED
        null fixes rho == 1 (the "undifferentiated pooling reference", NOT incumbent-equivalent).
  * ``empty_window_rule`` (a11_repair, deterministic, symmetric, identical in arm and null):
      dcur_t := 0 when n_cur = 0; dprev_t := 0 when m_prev = 0;
      dblend_t(rho) := 0 when n_cur + rho*m_prev == 0 (covers expansion-team debut rows with
      zero prior evidence of either kind).
  * ``fold1_evaluability_pinned``: fold train_lt_2022 is STRUCTURALLY DEACTIVATED for arm AND
    null identically because dprev_t is undefined (m_prev == 0) on 100% of that fold's training
    rows -- the first season in the archive has no preceding season. This module does not itself
    decide fold deactivation (that is the arm module's `structurally_deactivated_folds()` hook);
    it only guarantees the empty-window rule above holds so the runner's symmetric treatment is
    well-defined regardless.

Every function here is a pure, deterministic transform of its inputs -- no I/O, no randomness,
and no same-row (current-game) or later-game dependency. STRICT LAGGING is verified directly by
this arm's TESTS.py: a row's dcur_t/dprev_t/n_cur/m_prev depend only on OTHER rows (own team,
strictly earlier same-season date for dcur_t; own team's entire preceding season for dprev_t),
never on the row's own game outcome and never on any later game.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ENUMERATED_RHO: tuple[float, ...] = (0.25, 0.5, 0.75)          # frozen P35 A11 card elements
NULL_RHO: float = 1.0                                          # a11_repair.null_pinned


# ---------------------------------------------------------------------------------------- pace
def lagged_pace(n_off_poss, max_period) -> np.ndarray:
    """The frozen period-based regulation-equivalent possession construction.

    n_off_poss * 40 / (40 + 5*max(0, max_period - 4))  (construction_pins
    .lagged_regulation_equivalent_pin).
    """
    n = np.asarray(n_off_poss, dtype=float)
    mp = np.asarray(max_period, dtype=float)
    denom = 40.0 + 5.0 * np.maximum(0.0, mp - 4.0)
    return n * 40.0 / denom


# ------------------------------------------------------------------------- strictly-prior sums
def _prior_counts_sums(dates: np.ndarray, values: np.ndarray,
                       groups: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """For each row i, (prior_count[i], prior_sum[i]) = count/sum of `values` at rows whose
    `dates` are STRICTLY LESS than dates[i], optionally restricted to the same `groups` value.

    Same-date rows (of the same group, or globally when groups is None) never count toward each
    other's prior aggregate -- leak-free under calendar-date ties. Deterministic, vectorised, and
    independent of input row order.
    """
    n = len(dates)
    df = pd.DataFrame({"date": np.asarray(dates), "value": np.asarray(values, dtype=float)})
    key_cols = ["date"]
    if groups is not None:
        df["group"] = np.asarray(groups, dtype=object)
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


def compute_dcur_dprev(team_id, game_id, game_date, season, n_off_poss, max_period) -> dict:
    """n_cur, dcur_t, m_prev, dprev_t and Lbar_<g for every row of the supplied (history) frame,
    aligned to input row order. All inputs describe the CONTRACT-SCHEDULE history the caller
    supplies (real invocation: team_possession_prior_v1's own rows, including the four
    universe-excluded 2021 opening-day rows; tests: the synthetic archive).
    """
    team_id = np.asarray(team_id)
    game_id = np.asarray(game_id)
    game_date = np.asarray(game_date)
    season = np.asarray(season)
    pace = lagged_pace(n_off_poss, max_period)

    # all-prior, K-free league mean at each row's own date (shared by dcur_t and dprev_t)
    n_league, sum_league = _prior_counts_sums(game_date, pace, groups=None)
    Lbar = np.divide(sum_league, n_league, out=np.zeros_like(sum_league), where=n_league > 0)

    # dcur_t: current-season, same-team, strictly-prior-by-date
    cur_group = np.array([f"{t!r}|{s!r}" for t, s in zip(team_id, season)], dtype=object)
    n_cur, sum_cur = _prior_counts_sums(game_date, pace, groups=cur_group)
    dcur = np.where(n_cur > 0, np.divide(sum_cur, n_cur, out=np.zeros_like(sum_cur),
                                         where=n_cur > 0) - Lbar, 0.0)

    # dprev_t: ENTIRE immediately-preceding season (no date restriction needed -- the whole
    # preceding season is, by schedule construction, strictly in the past relative to any row of
    # the current season)
    df = pd.DataFrame({"team_id": team_id, "season": season, "pace": pace})
    totals = (df.groupby(["team_id", "season"], sort=True)["pace"].agg(["sum", "count"])
             .reset_index().rename(columns={"sum": "prev_sum", "count": "prev_cnt"}))
    tgt = pd.DataFrame({"team_id": team_id, "season": season - 1,
                        "_orig_idx": np.arange(len(team_id))})
    merged = tgt.merge(totals, on=["team_id", "season"], how="left")
    merged = merged.sort_values("_orig_idx", kind="mergesort")
    m_prev = merged["prev_cnt"].fillna(0.0).to_numpy(dtype=float)
    sum_prev = merged["prev_sum"].fillna(0.0).to_numpy(dtype=float)
    dprev = np.where(m_prev > 0, np.divide(sum_prev, m_prev, out=np.zeros_like(sum_prev),
                                           where=m_prev > 0) - Lbar, 0.0)

    return {"team_id": team_id, "game_id": game_id, "game_date": game_date, "season": season,
            "Lbar": Lbar, "n_cur": n_cur, "dcur": dcur, "m_prev": m_prev, "dprev": dprev}


def dblend(dcur, dprev, n_cur, m_prev, rho: float) -> np.ndarray:
    """dblend_t(rho) = (n_cur*dcur + rho*m_prev*dprev) / (n_cur + rho*m_prev); 0 at the empty
    window n_cur + rho*m_prev == 0 (a11_repair.empty_window_rule, verbatim)."""
    n_cur = np.asarray(n_cur, dtype=float)
    m_prev = np.asarray(m_prev, dtype=float)
    dcur = np.asarray(dcur, dtype=float)
    dprev = np.asarray(dprev, dtype=float)
    denom = n_cur + float(rho) * m_prev
    numer = n_cur * dcur + float(rho) * m_prev * dprev
    return np.where(denom > 0, np.divide(numer, denom, out=np.zeros_like(numer), where=denom > 0),
                    0.0)


def align_by_key(history_result: dict, target_keys: pd.DataFrame,
                 key_cols=("team_id", "game_id")) -> dict:
    """Align `compute_dcur_dprev`'s per-history-row output onto `target_keys`' row order."""
    key_cols = list(key_cols)
    h = pd.DataFrame({c: history_result[c] for c in key_cols})
    h["_n_cur"] = history_result["n_cur"]
    h["_dcur"] = history_result["dcur"]
    h["_m_prev"] = history_result["m_prev"]
    h["_dprev"] = history_result["dprev"]
    lut = h.drop_duplicates(subset=key_cols)

    tk = target_keys[key_cols].reset_index(drop=True).copy()
    tk["_orig_order"] = np.arange(len(tk))
    merged = tk.merge(lut, on=key_cols, how="left")
    if merged["_n_cur"].isna().any():
        missing = merged.loc[merged["_n_cur"].isna(), key_cols].to_dict("records")
        raise KeyError(f"{len(missing)} target row(s) not found in the supplied contract-schedule "
                       f"history frame (first few: {missing[:3]}); n_cur/dcur_t/m_prev/dprev_t "
                       f"are undefined for a row that is not itself part of the history it is "
                       f"scored against")
    merged = merged.sort_values("_orig_order", kind="mergesort")
    return {"n_cur": merged["_n_cur"].to_numpy(dtype=float),
            "dcur": merged["_dcur"].to_numpy(dtype=float),
            "m_prev": merged["_m_prev"].to_numpy(dtype=float),
            "dprev": merged["_dprev"].to_numpy(dtype=float)}


def compute_features(history: pd.DataFrame, targets: pd.DataFrame) -> dict:
    """n_cur/dcur/m_prev/dprev for every row of `targets`, aligned to its row order.

    `history` must carry team_id, game_id, game_date, season, n_off_poss, max_period and must be
    a SUPERSET of the games appearing in `targets` (n_clock_pin: the contract-schedule clock).
    """
    required = ("team_id", "game_id", "game_date", "season", "n_off_poss", "max_period")
    for col in required:
        if col not in history.columns:
            raise KeyError(f"A11 compute_features requires column '{col}' on the history frame")
    hist_result = compute_dcur_dprev(
        history["team_id"].to_numpy(), history["game_id"].to_numpy(),
        history["game_date"].to_numpy(), history["season"].to_numpy(),
        history["n_off_poss"].to_numpy(), history["max_period"].to_numpy())
    return align_by_key(hist_result, targets)
