#!/usr/bin/env python3
"""feature_construction.py -- A10_recency_contrast feature construction.

Implements EXACTLY the pinned clocks/constructions the frozen P35 task card names for A10
(experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A10] amended by
shared_frozen_amendments.construction_pins), plus P33's own A10 formula (carried by hash
reference per the P35 carry_convention):

  * formula (P33 SPEC.json, arms[A10]): ``log E[y] = log_exposure + beta0*d_t + beta1*c_t;
    c_t = ewma_lambda{pace(j) - Lbar_<j} - d_t``.
  * ``lagged_regulation_equivalent_pin``: prior-game realized regulation-equivalent possessions
    (pace) := n_off_poss * 40 / (40 + 5*max(0, max_period - 4)).
  * ``d_t_league_mean_pin``: d_t's inner lagged league mean is ALL-PRIOR and K-FREE --
    Lbar_<g = mean of lagged pace over ALL completed league games strictly before game_date(g).
    d_t = mean_{j in P(t,<g)} pace(j) - Lbar_<g, where P(t,<g) is team t's own completed games
    strictly before g. This is the SAME shared d_t column as A08/A09 (byte-identical
    construction; not re-derived differently here).
  * ``n_clock_pin``: n_t ("n_prior_games") is counted on the CONTRACT SCHEDULE clock (every
    completed prior game the team has in the supplied frame, including universe-excluded rows
    where present). Callers at real-fold time are responsible for supplying the
    contract-schedule frame, not the universe-excluded fit frame.
  * A10's own frozen ``fold_local_fallback`` (p26_k0_record, card): d_t := 0 and c_t := 0 on the
    empty window (n_t == 0). Deterministic and symmetric, identical for both lambda elements.

Definition of c_t, made fully operational here (P33's formula is exact on its own terms; the
per-game recency weighting scheme is genuinely underspecified by the frozen bytes beyond
"ewma_lambda" -- this module pins ONE deterministic, standard reading and states it plainly
rather than silently choosing among several, per standing rule 1):

  For team t's target row g, let j_1 < j_2 < ... < j_{n_t} be team t's own games strictly before
  g, in chronological order (game_date, then game_id as the tie-break -- the same deterministic
  ordering A08's ``a08_window_tie_break`` pins for its own trailing-K window). For each such prior
  game j, define the row-level deviation

      dev(j) = pace(j) - Lbar_<j

  where Lbar_<j is the ALL-PRIOR, K-free league mean evaluated AS OF game j's OWN date (exactly
  the same "mean_league" quantity computed for row j when row j is itself scored as a target row
  -- i.e. dev(j) is a property of row j alone, independent of which later row is asking about
  it). ewma_lambda{dev(j_1), ..., dev(j_{n_t})} is the STANDARD recursive exponentially-weighted
  moving average with the most recent prior game weighted by lambda and the average of all
  strictly-earlier prior games weighted (1-lambda), matching the recursive convention already in
  use elsewhere in this program for exponential recency weighting (D_ewma_shrunk):

      S_1 = dev(j_1)
      S_k = lambda * dev(j_k) + (1 - lambda) * S_{k-1},  k = 2 .. n_t
      ewma_lambda{...} := S_{n_t}

  c_t(g) := S_{n_t} - d_t(g)   (== 0 identically whenever n_t == 0, by the frozen empty-window
  rule, since both terms are separately forced to 0).

Every function here is a pure, deterministic transform of its inputs -- no I/O, no randomness, no
same-row (current-game) dependency. STRICT LAGGING (a row's own d_t/c_t depend only on OTHER rows
with a strictly earlier game_date, never on the row's own game outcome and never on any later
game) is verified directly by TESTS.py against these pure functions.

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
    other's prior aggregate -- leak-free under same-day ties. Deterministic, vectorised, no
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


def compute_n_t_d_t_dev(team_id, game_date, n_off_poss, max_period
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """n_t, d_t AND dev (== pace - Lbar_<own_date, i.e. league-wide, group=None) for every row of
    the supplied (history) frame, aligned to input row order.

    dev is a per-row quantity (pace(row) - Lbar as of row's OWN date), used directly by
    ``compute_c_t`` below to build each target row's EWMA over its OWN team's strictly-prior
    dev values.
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
    d_t = np.where(n_t > 0, raw_d_t, 0.0)               # empty-window rule
    dev = pace - mean_league                            # row's OWN deviation as of its OWN date
    return n_t, d_t, dev


def compute_c_t(team_id, game_date, game_id, dev, n_t, lam: float) -> np.ndarray:
    """The recency contrast c_t = ewma_lambda{dev(j) : j strictly prior, same team} - d_t.

    `dev` must be the per-row deviation from ``compute_n_t_d_t_dev`` (league-wide, evaluated as
    of each row's OWN date); `n_t` must be the matching prior-count column (used only to confirm
    the empty-window rows, d_t is applied by the caller). This function returns
    ``ewma_lambda{...}`` alone (NOT yet minus d_t); ``compute_n_t_d_t_c_t`` below combines it with
    d_t into the final c_t per the card formula.

    Deterministic ordering within a team: (game_date, game_id) ascending -- the same tie-break
    A08's own trailing window uses (LEAKAGE L6 convention, applied here for consistency; A10's
    own card is silent on ties and this reading is the only one already frozen elsewhere in the
    preregistration for an analogous chronological window).
    """
    if not (0.0 < lam <= 1.0):
        raise ValueError(f"lambda must be in (0, 1], got {lam}")
    team_id = np.asarray(team_id)
    game_date = np.asarray(game_date)
    game_id = np.asarray(game_id)
    dev = np.asarray(dev, dtype=float)

    n = len(team_id)
    df = pd.DataFrame({"team_id": team_id, "game_date": game_date, "game_id": game_id,
                       "dev": dev})
    df["_orig_idx"] = np.arange(n)
    ordered = df.sort_values(["team_id", "game_date", "game_id"], kind="mergesort")

    ewma_prior = np.zeros(n, dtype=float)
    for _, grp in ordered.groupby("team_id", sort=False):
        idxs = grp["_orig_idx"].to_numpy()
        devs = grp["dev"].to_numpy(dtype=float)
        s = 0.0
        n_prior = 0
        for k in range(len(devs)):
            ewma_prior[idxs[k]] = s if n_prior > 0 else 0.0
            if n_prior == 0:
                s = devs[k]
            else:
                s = lam * devs[k] + (1.0 - lam) * s
            n_prior += 1
    return ewma_prior


def compute_n_t_d_t_c_t(team_id, game_date, game_id, n_off_poss, max_period, lam: float
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convenience: n_t, d_t, c_t together, exactly per the frozen A10 formula and empty-window
    rule (d_t := 0 and c_t := 0 when n_t == 0)."""
    n_t, d_t, dev = compute_n_t_d_t_dev(team_id, game_date, n_off_poss, max_period)
    ewma_prior = compute_c_t(team_id, game_date, game_id, dev, n_t, lam)
    raw_c_t = ewma_prior - d_t
    c_t = np.where(n_t > 0, raw_c_t, 0.0)                # A10 empty-window rule (p26_k0_record)
    return n_t, d_t, c_t


def align_n_t_d_t_c_t_by_key(history: pd.DataFrame, target_keys: pd.DataFrame, lam: float,
                             key_cols=("team_id", "game_id")) -> tuple[np.ndarray, np.ndarray,
                                                                       np.ndarray]:
    """Compute n_t/d_t/c_t over `history` and align the result onto `target_keys`' row order.

    `history` must carry team_id, game_date, game_id, n_off_poss, max_period and the join key
    columns. `target_keys` carries the join key columns in the row order the caller wants
    n_t/d_t/c_t returned in (normally: the universe frame's own row order, since every fit-frame
    row is itself one of the history rows).
    """
    h = history.reset_index(drop=True).copy()
    n_t, d_t, c_t = compute_n_t_d_t_c_t(h["team_id"].to_numpy(), h["game_date"].to_numpy(),
                                        h["game_id"].to_numpy(), h["n_off_poss"].to_numpy(),
                                        h["max_period"].to_numpy(), lam)
    h["_n_t"], h["_d_t"], h["_c_t"] = n_t, d_t, c_t
    key_cols = list(key_cols)
    lut = h[key_cols + ["_n_t", "_d_t", "_c_t"]].drop_duplicates(subset=key_cols)
    tk = target_keys[key_cols].reset_index(drop=True).copy()
    tk["_orig_order"] = np.arange(len(tk))
    merged = tk.merge(lut, on=key_cols, how="left")
    if merged["_n_t"].isna().any():
        missing = merged.loc[merged["_n_t"].isna(), key_cols].to_dict("records")
        raise KeyError(f"{len(missing)} target row(s) not found in the supplied history frame "
                       f"(first few: {missing[:3]}); n_t/d_t/c_t are undefined for a row that is "
                       f"not itself part of the contract-schedule history it is scored against")
    merged = merged.sort_values("_orig_order", kind="mergesort")
    return (merged["_n_t"].to_numpy(dtype=float), merged["_d_t"].to_numpy(dtype=float),
            merged["_c_t"].to_numpy(dtype=float))


ENUMERATED_LAMBDA: tuple[float, ...] = (0.2, 0.5)          # frozen P35 A10 card elements
