#!/usr/bin/env python3
"""features.py -- A08_league_lag_level feature construction (d_t, L_t).

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A08/ only. This module
touches nothing outside that directory and imports nothing from the shared runner except its
frozen constants (read-only).

REMEDIATION (P37 finding A-1, Severity A): the prior implementation of this module defined
"strictly earlier" by dense GAME-RANK over (game_date, game_id), which let a same-calendar-date
game with a smaller game_id count as prior to another game on that same date -- contradicting the
frozen construction_pins, which are DATE-GRANULAR ("strictly before game_date(g)"; the
(game_date, game_id) ordering is a TIE-BREAK used only to order games that already share a
strictly-earlier date, never a redefinition of "earlier" itself). This module is rewritten to be
date-granular throughout: a game_id is never used to decide whether a game counts as prior, only
to order the (already date-prior) games within the K-window.

d_t is additionally rebuilt on the exact `_prior_sum_count_by_date` construction used verbatim by
A09 (`arms/A09/feature_construction.py::_prior_sum_count_by_date`/`compute_n_t_d_t`) and A10
(`arms/A10/feature_construction.py`, same helper) -- reconstructed byte-for-byte here rather than
imported (OWNERSHIP / directory-exclusive isolation, same precedent as A13 reconstructing A12's
design in `arms/A13/arm_a13.py`), so that d_t is provably the SAME shared column given the same
(team_id, game_date, pace) inputs. `tests/test_a08.py::test_cross_arm_d_t_parity_tie_heavy` proves
this by running A08, A09 and A10's d_t constructions on one tie-heavy synthetic fixture and
asserting bitwise equality -- the exact scenario (156/240 divergent rows) the P37 audit measured
against the old rank-strict code.

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
    P(t,<g) = team t's own games STRICTLY BEFORE game_date(g) (DATE-granular: a same-date game,
    however ordered by game_id, is never a member of P(t,<g)); ALL prior, no K-window (A08's
    K-window applies ONLY to L_t). Lbar_allprior(g) = mean of pace(j) over ALL contract-schedule
    team-game rows strictly before game_date(g) -- ALL-PRIOR, K-FREE and DATE-granular
    (construction_pins.d_t_league_mean_pin, verbatim).
    Empty-window convention (shared amendment, OPERATIONAL OP-2, applied identically here since
    d_t is the SAME shared column): d_t := 0 when the team has zero prior games (n_prior_own=0).
    Lbar_allprior(g) is likewise 0 wherever the league mean's own prior-count is 0 (the same
    empty-window symmetry the shared `_prior_sum_count_by_date` construction applies uniformly,
    matching A09/A10 exactly).
  * L_t (A08 treatment; task_cards.A08 + P31 HYPOTHESES TS4):
        L_t(g;K) = Lbar_K(g;K) - Lbar_train(K)
    Lbar_K(g;K) = trailing mean of pace(j) over ALL team-game rows belonging to the last K
    completed league GAMES STRICTLY BEFORE game_date(g) (date-granular membership), those
    strictly-earlier-dated games ordered by (game_date, game_id) ascending and the last K taken
    (construction_pins.a08_window_tie_break, verbatim: the (game_date, game_id) ordering is a
    TIE-BREAK for ordering games that are already strictly earlier by date -- it never admits a
    same-date game -- game granularity, not team-game granularity, for the K-count).
    FOLDS F1 / OPERATIONAL OP-3 (P35 A08 amendments, verbatim): rows whose game has fewer than K
    strictly-earlier (by DATE) completed league games take L_t := 0 directly (no row dropped),
    identically in arm and null.
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


# ------------------------------------------------------------------------- strictly-prior sums
#
# Reconstructed byte-for-byte from arms/A09/feature_construction.py::_prior_sum_count_by_date
# (identical logic also carried independently in A10/A11; the P37 audit measured A09 == A10 ==
# A11 exactly). Kept as a private, task-specific copy per OWNERSHIP -- not imported across arm
# directories (same precedent as A13 reconstructing A12's design rather than importing it).
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


def compute_d_t(team_id, game_date, pace) -> tuple[np.ndarray, np.ndarray]:
    """n_prior_own, d_t for every row of the supplied (history) frame, aligned to input row order.

    Byte-identical construction to A09's `compute_n_t_d_t` / A10's `compute_n_t_d_t_dev` given the
    same (team_id, game_date, pace) triple -- proves K4 (d_t is ONE shared column across
    A08/A09/A10). Date-granular throughout: `_prior_sum_count_by_date` excludes same-date rows
    from both the own-team and league prior aggregates.
    """
    team_id = np.asarray(team_id)
    game_date = np.asarray(game_date)
    pace = np.asarray(pace, dtype=float)

    n_own, sum_own = _prior_sum_count_by_date(game_date, pace, groups=team_id)
    n_league, sum_league = _prior_sum_count_by_date(game_date, pace, groups=None)

    mean_own = np.divide(sum_own, n_own, out=np.zeros_like(sum_own), where=n_own > 0)
    mean_league = np.divide(sum_league, n_league, out=np.zeros_like(sum_league),
                            where=n_league > 0)
    raw_d_t = mean_own - mean_league
    d_t = np.where(n_own > 0, raw_d_t, 0.0)              # shared empty-window rule (OP-2)
    return n_own.astype(int), d_t


# ------------------------------------------------------------------------ game-level L_t window

def _game_date_boundary_map(history: pd.DataFrame) -> pd.DataFrame:
    """For every DISTINCT game (game_date, game_id), its `game_rank` (dense rank over
    (game_date, game_id) ascending, 0-indexed -- construction_pins.a08_window_tie_break's
    within-date tie-break) and its `date_boundary`: the COUNT of distinct games whose date is
    STRICTLY EARLIER than this game's own date (i.e. the number of strictly-date-prior games,
    date-granular -- NEVER incremented by a same-date game regardless of game_id).

    Because games are sorted primarily by game_date, all games sharing a date occupy a contiguous
    block of `game_rank` values; `date_boundary` for every game in that block equals the block's
    starting `game_rank` (the count of games strictly before that date).
    """
    games = (history[list(GAME_ORDER_COLS)].drop_duplicates()
             .sort_values(list(GAME_ORDER_COLS), kind="mergesort")
             .reset_index(drop=True))
    games["game_rank"] = np.arange(len(games))
    date_start_rank = games.groupby("game_date", sort=True)["game_rank"].transform("min")
    games["date_boundary"] = date_start_rank
    return games


def build_history_index(history: pd.DataFrame, pace_col: str) -> dict:
    """Precompute per-game-rank league aggregates (for the L_t window) and the shared d_t inputs.

    `history` must carry at least: team_id, game_id, game_date, and `pace_col` (the realized
    lagged-use-only pace value of that historical row). Every aggregate here is STRICTLY
    backward-looking by DATE, never by game_rank/game_id alone (enforced via `date_boundary`,
    computed here; consumed in `compute_features`).
    """
    h = history.copy()
    gmap = _game_date_boundary_map(h)
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

    return {"n_games": n_games, "cum_sum": cum_sum, "cum_cnt": cum_cnt, "game_rank_map": gmap}


def compute_features(history: pd.DataFrame, targets: pd.DataFrame, K: int,
                     pace_col: str = "pace") -> dict:
    """d_t and (uncentered) L_t for every row of `targets`, strictly lagged, DATE-granular.

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

    date_boundary = tgt["date_boundary"].to_numpy(int)   # DATE-strict count of strictly-earlier games
    n = len(tgt)

    cum_sum, cum_cnt = idx["cum_sum"], idx["cum_cnt"]

    n_prior_league = date_boundary                       # strictly-earlier-DATED games, by construction
    windowed_defined = n_prior_league >= K

    all_prior_league_mean = np.zeros(n)
    L_raw = np.zeros(n)
    for i in range(n):
        b = int(date_boundary[i])
        if b > 0:
            all_prior_league_mean[i] = cum_sum[b - 1] / cum_cnt[b - 1]
        else:
            all_prior_league_mean[i] = 0.0        # empty-window symmetry at the league's own start

        if windowed_defined[i]:
            lo, hi = b - K, b - 1
            s = cum_sum[hi] - (cum_sum[lo - 1] if lo > 0 else 0.0)
            c = cum_cnt[hi] - (cum_cnt[lo - 1] if lo > 0 else 0.0)
            L_raw[i] = s / c
        else:
            L_raw[i] = 0.0

    # d_t via the exact shared (A08/A09/A10) construction -- date-granular, K-free, all-prior.
    # compute_d_t must run over the FULL history (every row is simultaneously a potential prior
    # observation for later rows of the same/other teams -- exactly A09's align_n_t_d_t_by_key
    # pattern), then align the result onto `targets`' row order by (team_id, game_id).
    h = history.reset_index(drop=True).copy()
    h_n_prior_own, h_d_t = compute_d_t(h["team_id"].to_numpy(), h["game_date"].to_numpy(),
                                       h[pace_col].to_numpy())
    h["_n_prior_own"] = h_n_prior_own
    h["_d_t"] = h_d_t
    key_cols = ["team_id", "game_id"]
    lut = h[key_cols + ["_n_prior_own", "_d_t"]].drop_duplicates(subset=key_cols)
    tk = tgt[key_cols].copy()
    tk["_orig_order"] = np.arange(len(tk))
    merged = tk.merge(lut, on=key_cols, how="left")
    if merged["_d_t"].isna().any():
        missing = merged.loc[merged["_d_t"].isna(), key_cols].to_dict("records")
        raise KeyError(f"{len(missing)} target row(s) not found in the supplied contract-schedule "
                       f"history (first few: {missing[:3]}); d_t is undefined for a row that is "
                       f"not itself part of the history it is scored against")
    merged = merged.sort_values("_orig_order", kind="mergesort")
    n_prior_own = merged["_n_prior_own"].to_numpy(dtype=int)
    d_t = merged["_d_t"].to_numpy(dtype=float)

    return {"d_t": d_t, "L_raw": L_raw, "windowed_defined": windowed_defined,
            "n_prior_own": n_prior_own, "n_prior_league": n_prior_league,
            "all_prior_league_mean": all_prior_league_mean, "game_rank": tgt["game_rank"].to_numpy(int)}


def center_L(L_raw: np.ndarray, windowed_defined: np.ndarray, train_mask: np.ndarray) -> tuple:
    """Lbar_train(K) and the centered L_t, per features.py module docstring's pinned reading."""
    train_defined = train_mask & windowed_defined
    lbar_train = float(np.mean(L_raw[train_defined])) if train_defined.any() else 0.0
    L_t = np.where(windowed_defined, L_raw - lbar_train, 0.0)
    return lbar_train, L_t
