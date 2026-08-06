#!/usr/bin/env python3
"""feature_construction.py -- A18_median_duration_contrast feature construction (z1).

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A18/ only. This module
touches nothing outside that directory and performs no cross-arm import (each arm module in this
tree is self-contained; A08/A09/A11 independently re-derive their own constructions rather than
importing one another, and this module follows the same convention).

Implements EXACTLY the pinned construction the frozen sources name for A18:

  * P35_FREEZE_TASK_CARDS/SPEC.json (sha256
    68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32), task_cards[arm_id ==
    "A18_median_duration_contrast"]:
        model: eta = log_exposure + beta1 * z1;
               z1 = med_dur_opp - med_dur_own (same-season strictly earlier, seconds);
               no global intercept; E = 3 imputation: z1 = 0 when either team has < 3 completed
               prior same-season games.
        k0_matched_frozen.null: "identical rows/target/folds/weights/offset and identical E=3
               imputation machinery; treatment adds ONLY z1" -- comparison: term_removal.
  * P33_PREREGISTRATION_DRAFT/SPEC.json (sha256
    066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093), carried by the P35 card's
    carry_convention, arm A18_median_duration_contrast:
        "formula": "z1 = med_dur_opp - med_dur_own over strictly earlier SAME-SEASON games;
               seconds, untransformed; expected beta1 > 0; E = 3 imputation: z1 = 0 when either
               team has < 3 completed prior same-season games"
        "hyperparameters.fixed": {"E_min_prior_games": 3, "window": "same-season flat (no decay)"}
        "features": [{"name": "duration_sec (lagged median)",
               "construction": "same-season strictly-earlier median per team",
               "lineage": "possessions_raw_v2 lagged rows", "cutoff_evidence":
               "S8 LAGGED_USE_ONLY; P22 guard"}, ...]
    Neither the P33 nor the P35 text specifies WHICH possessions of a team the pooled median is
    taken over, nor whether "median per team" pools every qualifying possession or averages
    per-game medians. That specific reading traces to the ORIGINATING hypothesis record this arm
    was drafted from -- stage2b/P31_FINAL_V3_IDEATION/HYPOTHESES_opponent_mechanism.md,
    OPPONENT_MECHANISM_H1 -- which states the formula in full:
        "med_dur_team = median of duration_sec over ALL of that team's offensive possessions
         (rows with offense_team_id == team) in strictly earlier same-season games."
    That is: ONE pooled median (not an average of per-game medians) over every possession row
    with offense_team_id == team drawn from games strictly earlier, by game_date, within the same
    season -- no filtering of zero-duration (technical free throw) possessions, matching the
    hypothesis text's "ALL". This module implements that reading literally and verbatim; nothing
    is invented beyond it. Flagged for P37 as a card-silent construction choice resolved by the
    arm's own originating hypothesis record, not fabricated from nothing (same posture as A16's
    tie-break choice and A11's DERIVED_NO_JOIN classification).

  E_MIN_PRIOR_GAMES = 3 counts DISTINCT prior game_id values (not possession rows, not calendar
  dates -- the P33 hyperparameter name is literally "E_min_prior_games").

STRICT LAGGING: a target row's med_dur_own/med_dur_opp depend ONLY on possession rows whose
`game_date` is STRICTLY LESS than the target row's own `game_date`, within the SAME `season`, for
the relevant `offense_team_id`. A possession row sharing the target's own game_id is therefore
never included (it shares the target's own game_date, which fails the strict inequality). This is
verified directly by TESTS.py in this directory (identity/synthetic perturbation tests), the same
posture P22's PRIOR_GAME re-derivation cannot certify for a pooled multi-game aggregate (see
arm_a18.py's lag_specs() docstring for why this is declared DERIVED_NO_JOIN, following A11's and
A16's precedent for aggregates outside the guard's single-shift re-derivation contract).

Every function here is a pure, deterministic transform of its inputs -- no I/O, no randomness.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

E_MIN_PRIOR_GAMES: int = 3     # P33 hyperparameters.fixed.E_min_prior_games (frozen, verbatim)


def _trailing_median_and_count_one_side(
    possessions: pd.DataFrame, side_team_ids: np.ndarray,
    target_game_dates: np.ndarray, target_seasons: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """For each target row i: (pooled median duration_sec, n distinct prior game_id) over
    possession rows with offense_team_id == side_team_ids[i], season == target_seasons[i],
    game_date STRICTLY LESS THAN target_game_dates[i].

    `possessions` must carry columns game_id, game_date, season, offense_team_id, duration_sec.
    Vectorised per (team, season) group: one sort plus one np.searchsorted per group, not per
    target row.
    """
    n = len(side_team_ids)
    med = np.full(n, np.nan, dtype=float)
    cnt = np.zeros(n, dtype=float)

    P = possessions[["game_id", "game_date", "season", "offense_team_id", "duration_sec"]].copy()
    P = P.sort_values(["offense_team_id", "season", "game_date"], kind="mergesort")

    targets = pd.DataFrame({
        "team": np.asarray(side_team_ids), "season": np.asarray(target_seasons),
        "date": np.asarray(target_game_dates), "_orig_idx": np.arange(n),
    })

    for (team, season), grp in P.groupby(["offense_team_id", "season"], sort=False):
        rows = targets[(targets["team"] == team) & (targets["season"] == season)]
        if rows.empty:
            continue
        dates = grp["game_date"].to_numpy()          # ascending within group (sorted above)
        durs = grp["duration_sec"].to_numpy(dtype=float)
        gids = grp["game_id"].to_numpy()
        for _, r in rows.iterrows():
            cutoff_idx = int(np.searchsorted(dates, r["date"], side="left"))
            if cutoff_idx > 0:
                med[int(r["_orig_idx"])] = float(np.median(durs[:cutoff_idx]))
                cnt[int(r["_orig_idx"])] = float(pd.unique(gids[:cutoff_idx]).shape[0])
    return med, cnt


def compute_z1(
    possessions: pd.DataFrame, team_ids: np.ndarray, opp_team_ids: np.ndarray,
    game_dates: np.ndarray, seasons: np.ndarray,
) -> dict:
    """z1(row) = med_dur_opp - med_dur_own; z1 := 0 when either side has fewer than
    E_MIN_PRIOR_GAMES distinct strictly-earlier same-season games (P33/P35 E=3 imputation,
    verbatim, symmetric in own and opponent).

    Returns a dict of arrays aligned to the input row order: z1, med_dur_own, med_dur_opp,
    n_own, n_opp, imputed (bool: True where the E=3 rule fired).
    """
    required = ("game_id", "game_date", "season", "offense_team_id", "duration_sec")
    for col in required:
        if col not in possessions.columns:
            raise KeyError(f"A18 compute_z1 requires column '{col}' on the possessions frame")

    med_own, n_own = _trailing_median_and_count_one_side(
        possessions, np.asarray(team_ids), np.asarray(game_dates), np.asarray(seasons))
    med_opp, n_opp = _trailing_median_and_count_one_side(
        possessions, np.asarray(opp_team_ids), np.asarray(game_dates), np.asarray(seasons))

    imputed = (n_own < E_MIN_PRIOR_GAMES) | (n_opp < E_MIN_PRIOR_GAMES)
    raw = np.where(np.isnan(med_own) | np.isnan(med_opp), 0.0, med_opp - med_own)
    z1 = np.where(imputed, 0.0, raw)

    return {"z1": z1, "med_dur_own": med_own, "med_dur_opp": med_opp,
            "n_own": n_own, "n_opp": n_opp, "imputed": imputed}


def align_by_key(result: dict, source_keys: pd.DataFrame, target_keys: pd.DataFrame,
                 key_cols=("team_id", "game_id")) -> dict:
    """Align a `compute_z1`-style result (computed row-for-row against `source_keys`) onto
    `target_keys`' row order via an exact (team_id, game_id) key match. Raises on any target row
    absent from the source -- an undefined alignment is never silently imputed."""
    key_cols = list(key_cols)
    h = source_keys[key_cols].reset_index(drop=True).copy()
    for k, v in result.items():
        h[f"_{k}"] = np.asarray(v)
    lut = h.drop_duplicates(subset=key_cols)

    tk = target_keys[key_cols].reset_index(drop=True).copy()
    tk["_orig_order"] = np.arange(len(tk))
    merged = tk.merge(lut, on=key_cols, how="left")
    first_val_col = f"_{next(iter(result))}"
    if merged[first_val_col].isna().any():
        missing = merged.loc[merged[first_val_col].isna(), key_cols].to_dict("records")
        raise KeyError(f"{len(missing)} target row(s) not found in the supplied source keys "
                       f"(first few: {missing[:3]})")
    merged = merged.sort_values("_orig_order", kind="mergesort")
    out = {}
    for k in result:
        col = merged[f"_{k}"]
        out[k] = col.to_numpy(dtype=bool) if k == "imputed" else col.to_numpy(dtype=float)
    return out


def compute_features(possessions: pd.DataFrame, targets: pd.DataFrame) -> dict:
    """z1 (and diagnostics) for every row of `targets`, aligned to its row order.

    `targets` must carry team_id, opp_team_id, game_id, game_date, season. `possessions` must
    carry game_id, game_date, season, offense_team_id, duration_sec (possessions_raw_v2 at P38
    time; a synthetic possession-level fixture in tests).
    """
    required = ("team_id", "opp_team_id", "game_id", "game_date", "season")
    for col in required:
        if col not in targets.columns:
            raise KeyError(f"A18 compute_features requires column '{col}' on the targets frame")
    res = compute_z1(possessions, targets["team_id"].to_numpy(), targets["opp_team_id"].to_numpy(),
                     targets["game_date"].to_numpy(), targets["season"].to_numpy())
    # compute_z1 is already aligned 1:1 to targets' own row order (no history/target key mismatch
    # possible: targets ARE the rows z1 is computed for directly), so no re-alignment is needed.
    # align_by_key exists for callers that compute against a DIFFERENT frame than they score
    # against (kept for interface symmetry with A11's pattern; unused in the direct call path).
    return res
