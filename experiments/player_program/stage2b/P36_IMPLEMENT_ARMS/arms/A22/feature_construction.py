#!/usr/bin/env python3
"""feature_construction.py -- A22_lineup_churn_tv_distance feature construction (churn(t,g), x).

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A22/ only. This module
touches nothing outside that directory and performs no cross-arm import (each arm module in this
tree is self-contained -- A08/A09/A11/A17 independently re-derive their own shared formulas
rather than importing one another; this module follows the same convention. A17's
feature_construction.py -- read-only cross-reference, not imported -- establishes the precedent
recurrence this module reuses for its own half-life/season-boundary-discount weighting).

Implements EXACTLY the pinned construction the frozen P35 task card names for A22
(experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A22_lineup_churn_tv_
distance]), carried by hash reference from P33_PREREGISTRATION_DRAFT/SPEC.json (sha256
066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) arms[A22].

  * Mechanism (P33 arms[A22].mechanism, verbatim): "personnel discontinuity between the trailing
    evidence and the most recent observation mis-projects pace; churn is the cutoff-valid
    footprint."
  * Formula (P33 arms[A22].formula, verbatim):
        u_last(j) vs u_base(j) usage shares
        churn(t,g) = 0.5 * sum_j |u_last(j) - u_base(j)|
        x = (churn(t,g) + churn(opp(g,t),g)) / 2
        churn := 0 when |P(t,g)| = 1 (preregistered, symmetric, training-support-independent)
    P(t,g) = team t's own contract-schedule games with game_date STRICTLY before game_date(g)
    (the shared lag operator L every H1-family hypothesis inherits, per A17's own module-level
    citation of P31 HYPOTHESES_cutoff_leakage.md section 0).
  * features (P33 arms[A22].features, verbatim): "off_p1..off_p5 of STRICTLY EARLIER games" --
    "usage vectors over unordered player-id sets"; lineage "derive_lineups -> source pbp, lagged
    only"; cutoff_evidence "S8 LAGGED_USE_ONLY; P22 guard".
  * hyperparameters.fixed (P35 task_cards.A22, carried from P33): half_life_games = 10,
    season_boundary_discount = 0.5 -- "frozen by source", not tunable.
  * P35 amendment OP-7 (verbatim, corrects a P33 measured-false parenthetical): "|P|=1 rows
    number 15 (12 in 2021, 1 in 2025, 2 in 2026: expansion second games; the 2025/2026 rows are
    test-fold rows). The churn := 0 rule is symmetric and covers them; |P|=0 is covered by the
    cold-start text (churn := 0)."
  * p26_k0_record.fold_local_fallback (P35 task_cards.A22, verbatim): "churn := 0 when
    |P(t,g)| <= 1 (no base window / no evidence of change), symmetric, training-support-
    independent"; numeric_trigger "|P| <= 1".

AMBIGUITY FLAGGED FOR P37 (not resolved silently; same precedent A17/feature_construction.py and
A08/features.py set for their own closed-form readings): no frozen document spells out, in closed
form, what "u_last(j)" and "u_base(j)" mean at the level of an exact discrete index over a team's
own game history. This module pins the reading, converging FOUR independent frozen facts onto one
unique closed form:

  (1) mechanism text distinguishes exactly TWO evidence pools: "the trailing evidence" (plural,
      an aggregate) and "the most recent observation" (singular, one game) -- so u_last must be a
      SINGLE game's own usage vector, unweighted, and u_base must be an AGGREGATE over the
      remaining, STRICTLY OLDER games;
  (2) the fold_local_fallback trigger is |P(t,g)| <= 1, i.e. it fires the instant there are FEWER
      THAN TWO strictly-earlier games -- this is exactly the condition under which a
      "most-recent-single-game vs. aggregate-of-the-rest" split has no non-degenerate "rest" left
      (|P|=1: one game total, it IS "last", no games remain for "base"; |P|=0: no games at all).
      No other u_last/u_base split produces a fallback trigger at exactly |P| <= 1 rather than
      |P| = 0 alone;
  (3) the cold_start_behaviour text ("churn := 0 with no base window ('no evidence of change')")
      names the BASE window specifically as the thing that can be absent, confirming u_base (not
      u_last) is the aggregate quantity;
  (4) half_life_games=10 / season_boundary_discount=0.5 are the SAME fixed hyperparameters A17
      and A21 use for their own trailing-evidence aggregates (P33/P35 hyperparameters.fixed,
      identical field names and values) -- so u_base is constructed with the SAME recency-decay
      recurrence A17/feature_construction.py implements (base = 0.5**(1/10), aged by
      season_boundary_discount per season crossing), applied here to per-player possession
      counts instead of a scalar share numerator/denominator, and EXCLUDING the single most
      recent game (which is u_last instead).

Closed-form pin: for team t's own games sorted ascending by (game_date, game_id), let v_i be the
raw (undecayed) per-player offensive-possession-appearance count vector of t's i-th own game (0
indexed). For target row i (the (i+1)-th game chronologically, i.e. i strictly-earlier games exist):

    u_last_raw(i)  := v_{i-1}                                      (i >= 1, else undefined)
    u_base_raw(i)  := sum_{k=0}^{i-2} w(k, i) * v_k                 (i >= 2, else empty/undefined)
    w(k, i)        := base**(i-k) * season_boundary_discount**(season(row_i) - season(row_k))
    base           := 0.5 ** (1 / half_life_games)

i.e. u_last is the single immediately-preceding game's OWN raw counts (Delta_games = 1, always at
full unweighted strength -- "the most recent observation"), and u_base is the SAME A17-style
decayed running sum but restricted to Delta_games >= 2 ("the trailing evidence" excluding the one
just-named "most recent" game). u_last(j)/u_base(j) usage SHARES normalise each raw count vector
to sum to 1 over players (0.5*sum_j|share_last(j)-share_base(j)| is then a proper total-variation
distance in [0, 1], matching the formula's 0.5 coefficient). When i <= 1 (|P(t,g)| <= 1), u_base
is empty by construction (no Delta>=2 game exists) and churn(t,g) := 0 per the frozen fallback --
this module implements the fallback via the EXPLICIT numeric trigger n_prior_games <= 1, matching
the card's own stated numeric_trigger literally, not merely as an emergent property of empty-dict
arithmetic (belt-and-braces: both hold simultaneously, checked by TESTS.py).

`compute_prior_last_and_base` computes u_last_raw(i)/u_base_raw(i) in O(n) per team via a single
running-sum recurrence (verified algebraically against the naive O(n^2) double-sum definition in
TESTS.py::t02_recurrence_matches_naive_definition), reusing A17's proven aging discipline: age the
running per-player dict by w(1, ., .)=base*discount**gap BEFORE reading it at each row, so a
value read at row i that was added raw at row k has accumulated exactly (i-k) aging factors by the
time it is read -- i.e. weight base**(i-k) -- matching Delta_games(k, i) = i-k counted the way
A17's own docstring pins it (the game immediately preceding row i has Delta_games = 1).

None of this module touches real data, the SEALED_RESULTS tree, or any comparative performance
number. It is pure, deterministic dict/array arithmetic over whatever frame is handed to it.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HALF_LIFE_GAMES = 10.0            # task_cards.A22.hyperparameters.fixed.half_life_games
SEASON_BOUNDARY_DISCOUNT = 0.5    # task_cards.A22.hyperparameters.fixed.season_boundary_discount

_LINEUP_SLOTS = ("off_p1", "off_p2", "off_p3", "off_p4", "off_p5")
_TARGET_KEY_COLS = ("team_id", "game_id", "game_date", "season")
_ZERO_TOL = 1e-12


def _recency_weight_base(half_life_games: float) -> float:
    """base**1 == 0.5**(1/half_life_games); base**half_life_games == 0.5 exactly (A17 precedent)."""
    return 0.5 ** (1.0 / float(half_life_games))


def aggregate_game_player_appearances(lineups: pd.DataFrame) -> pd.DataFrame:
    """Collapse a possession-level lineup frame to one row per (team_id, game_id, player_id):
    the count of that team's own OFFENSIVE possessions in that game on which player_id appeared
    among off_p1..off_p5 (P33 arms[A22].features: "off_p1..off_p5 of STRICTLY EARLIER games" --
    "unordered player-id sets"; order/slot number carries no meaning -- S8's own "ascending-
    order-statistics caveat harmless" note, carried verbatim across A12/A22's P33 records).

    `lineups` must carry: game_id, game_date, season, offense_team_id, off_p1..off_p5. This
    function performs NO lagging itself -- pure same-row aggregation; restricting to STRICTLY
    earlier games happens in `compute_prior_last_and_base` below, exactly mirroring A17's
    aggregate_possession_counts / compute_prior_recency_aggregates split.
    """
    required = ("game_id", "game_date", "season", "offense_team_id") + _LINEUP_SLOTS
    for c in required:
        if c not in lineups.columns:
            raise KeyError(f"aggregate_game_player_appearances requires column '{c}'")
    long_parts = []
    for slot in _LINEUP_SLOTS:
        part = lineups[["offense_team_id", "game_id", "game_date", "season", slot]].rename(
            columns={"offense_team_id": "team_id", slot: "player_id"})
        long_parts.append(part)
    long = pd.concat(long_parts, ignore_index=True)
    long = long[long["player_id"].notna()]
    out = (long.groupby(["team_id", "game_id", "game_date", "season", "player_id"], sort=False)
           .size().rename("appearances").reset_index())
    out["appearances"] = out["appearances"].astype(float)
    return out


def compute_prior_last_and_base(appearances_long: pd.DataFrame, *,
                                half_life_games: float = HALF_LIFE_GAMES,
                                season_boundary_discount: float = SEASON_BOUNDARY_DISCOUNT
                                ) -> pd.DataFrame:
    """For every (team_id, game_id) appearing in `appearances_long`, compute u_last_raw (dict),
    u_base_raw (dict) and n_prior_games, per the closed-form recurrence pinned in the module
    docstring. Returns one row per (team_id, game_id, game_date, season) with object-dtype dict
    columns "last_counts" / "base_counts" (python dict[player_id -> float], possibly empty) and
    an int column "n_prior_games".

    Strict lagging is structural, exactly as A17: at row i, `last_counts`/`base_counts` are
    computed and returned BEFORE row i's own appearance counts are folded into the running state,
    so a row's own game NEVER contributes to its own feature and no later game ever contributes
    (the running state only ever reflects rows already visited in ascending date order).
    """
    for c in ("team_id", "game_id", "game_date", "season", "player_id", "appearances"):
        if c not in appearances_long.columns:
            raise KeyError(f"compute_prior_last_and_base requires column '{c}'")
    base = _recency_weight_base(half_life_games)

    game_index = (appearances_long[list(_TARGET_KEY_COLS)].drop_duplicates()
                 .sort_values(["team_id", "game_date", "game_id"], kind="mergesort")
                 .reset_index(drop=True))
    counts_lut: dict = {}
    for (tid, gid), grp in appearances_long.groupby(["team_id", "game_id"], sort=False):
        counts_lut[(tid, gid)] = dict(zip(grp["player_id"].tolist(),
                                          grp["appearances"].astype(float).tolist()))

    n = len(game_index)
    out_last = [None] * n
    out_base = [None] * n
    out_nprior = [0] * n

    run: dict = {}
    prev_team = object()
    prev_season = None
    prev_raw: dict = {}
    team_game_idx = 0

    tids = game_index["team_id"].to_numpy()
    gids = game_index["game_id"].to_numpy()
    seasons = game_index["season"].to_numpy()

    for i in range(n):
        tid = tids[i]
        season = seasons[i]
        if tid != prev_team:
            run = {}
            prev_season = None
            prev_raw = {}
            team_game_idx = 0

        if prev_season is not None:
            gap = season - prev_season
            factor = base * (float(season_boundary_discount) ** gap)
            run = {k: v * factor for k, v in run.items()}
        else:
            factor = None

        prior_full = run                      # decayed sum over ALL strictly earlier games
        if factor is not None and prev_raw:
            keys = set(prior_full) | set(prev_raw)
            base_only = {k: prior_full.get(k, 0.0) - factor * prev_raw.get(k, 0.0) for k in keys}
            base_only = {k: v for k, v in base_only.items() if abs(v) > _ZERO_TOL}
        else:
            base_only = {}

        out_last[i] = dict(prev_raw) if prev_raw else {}
        out_base[i] = base_only
        out_nprior[i] = team_game_idx

        raw_i = counts_lut.get((tid, gids[i]), {})
        for k, v in raw_i.items():
            run[k] = run.get(k, 0.0) + v
        prev_raw = raw_i
        prev_team = tid
        prev_season = season
        team_game_idx += 1

    out = game_index.copy()
    out["last_counts"] = out_last
    out["base_counts"] = out_base
    out["n_prior_games"] = out_nprior
    return out.reset_index(drop=True)


def _to_shares(counts: dict) -> dict:
    total = sum(counts.values())
    if total <= _ZERO_TOL:
        return {}
    return {k: v / total for k, v in counts.items()}


def tv_churn(last_counts: dict, base_counts: dict, n_prior_games: int) -> float:
    """0.5 * sum_j |u_last(j) - u_base(j)| over usage SHARES (each raw dict normalised to sum 1),
    with the frozen fallback churn := 0 when n_prior_games <= 1 (numeric_trigger, verbatim)."""
    if n_prior_games <= 1:
        return 0.0
    u_last = _to_shares(last_counts or {})
    u_base = _to_shares(base_counts or {})
    if not u_last or not u_base:
        return 0.0
    keys = set(u_last) | set(u_base)
    return 0.5 * sum(abs(u_last.get(k, 0.0) - u_base.get(k, 0.0)) for k in keys)


def align_churn(prior_df: pd.DataFrame, team_id: np.ndarray, game_id: np.ndarray) -> dict:
    """Look up (churn, n_prior_games) for an arbitrary (team_id, game_id) key array, aligned to
    input order (A17's align_shares precedent: the opponent's own row for the SAME game_id
    supplies its own team-side prior state, evaluated as of the same game_date)."""
    lut = prior_df.drop_duplicates(subset=["team_id", "game_id"]).set_index(["team_id", "game_id"])
    key = pd.MultiIndex.from_arrays([np.asarray(team_id), np.asarray(game_id)])
    missing = ~key.isin(lut.index)
    if missing.any():
        bad = list(zip(np.asarray(team_id)[missing][:5], np.asarray(game_id)[missing][:5]))
        raise KeyError(f"{int(missing.sum())} (team_id, game_id) target key(s) not found in the "
                       f"supplied lineup-prior table (first few: {bad}); every target row's own "
                       f"game must itself be a row of the supplied lineup history")
    rows = lut.loc[key]
    churn = np.array([tv_churn(lc, bc, int(npg)) for lc, bc, npg in
                      zip(rows["last_counts"], rows["base_counts"], rows["n_prior_games"])],
                     dtype=float)
    n_prior = rows["n_prior_games"].to_numpy(int)
    return {"churn": churn, "n_prior_games": n_prior}
