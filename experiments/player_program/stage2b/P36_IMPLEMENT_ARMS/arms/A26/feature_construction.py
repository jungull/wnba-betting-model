#!/usr/bin/env python3
"""feature_construction.py -- A26_sos_correction_own_minus_opp feature construction (z5).

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A26/ only. This module
touches nothing outside that directory and performs no cross-arm import (each arm module in this
tree is self-contained; A08/A09/A11/A18/A20 independently re-derive their own constructions
rather than importing one another, and this module follows the same convention).

Implements EXACTLY the pinned construction the frozen sources name for A26:

  * P35_FREEZE_TASK_CARDS/SPEC.json (sha256
    68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32), task_cards[arm_id ==
    "A26_sos_correction_own_minus_opp"]:
        model: eta = log_exposure + beta5 * z5; z5 = c_own - c_opp, c_t = -sched_t; mu = exp(eta);
               no global intercept; RAW counts per D9 (no OT reweighting - convention distinct
               from A12/A16, never harmonized).
        k0_matched_frozen.null: "identical machinery incl. the E=3-plus-undefined-LOO imputation;
               treatment adds ONLY z5; league-mean centering is feature DEFINITION, not design
               change" -- comparison: term_removal.
        amendments_applied names "LEAKAGE L6: LOO as-of date PINNED - every raw_opp mean and the
               league trailing mean are evaluated as of the TARGET game date g (all games strictly
               earlier than g); one clock, deterministic" -- this is the ONE-CLOCK rule this module
               implements exactly (see below); it resolves REVIEW_LEAKAGE.md L6's two-reading gap
               ("as of the meeting date j, or as of the target date g ... pin one") in favour of g.
  * P33_PREREGISTRATION_DRAFT/SPEC.json (sha256
    066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093), carried by the P35 card's
    carry_convention, arm A26_sos_correction_own_minus_opp:
        "formula": "raw_t = mean per-team-game possession row count over strictly earlier
               same-season games; sched_t = LOO mean of raw_{opp}; both centered on league trailing
               mean; c_t = -sched_t; z5 = c_own - c_opp; expected beta5 > 0; OT games enter raw on
               BOTH sides of every mean, preregistered AS-IS"
        "hyperparameters.fixed": {"E_min_prior_games": 3, "imputation": "z5 = 0 when either team
               has < 3 prior same-season games or any required LOO opponent mean is undefined -
               deterministic, symmetric"}

    P35's own ``model`` field states z5's formula using ONLY ``c_t = -sched_t`` (no ``raw_t`` term
    anywhere in it), matching the originating hypothesis record in full (below): ``raw_t`` is
    defined in P33's prose as the conceptual "team's own raw signature" the mechanism narrative
    refers to, but it is never itself consumed by z5 -- only ``sched_t`` (via ``c_t``) is. This
    module implements the P35 model string literally: ``raw_t`` per-team-game counts are computed
    (as the atomic quantity every ``sched_t``/``Lbar`` average is built from) but the STANDALONE
    "team's own raw_t, centered" term is never added into ``c_t`` or ``z5``, because neither the
    P35 card's own model formula nor the originating hypothesis's formula sketch does so. Flagged
    for P37 as a P33-prose-vs-P35-model-string completeness note, not silently harmonized (same
    posture as A18's median-pooling reading and A20's dictionary-freeze note).

  * stage2b/P31_FINAL_V3_IDEATION/HYPOTHESES_opponent_mechanism.md, OPPONENT_MECHANISM_H5 (the
    originating hypothesis record this arm was drafted from -- same posture as A18's own originating
    hypothesis citation), states the formula in full:
        "For team t before date d, let raw_t = mean over t's strictly earlier same-season games g
         of (t's possession count in g, i.e. that game's per-team row count in the possessions
         artifact), and let sched_t = mean over those same games g of raw_{opp(g)} computed
         leave-one-out (opponent's trailing mean EXCLUDING game g itself), each centred on the
         league trailing mean at d. The correction term is c_t = -sched_t ... Candidate:
         z5(row) = c_own - c_opp."
    "each centred on the league trailing mean" describes centering EACH raw_{opp(g)} value before
    it enters the sched_t average; because every raw_{opp(g)} value in one row's sched_t average is
    evaluated against the SAME league trailing mean under the one-clock pin below (all evaluated as
    of the row's own target date g, never as of each meeting date), centering per-term before
    averaging and centering the finished average by the same constant are numerically identical
    (a linear operation with one shared subtrahend); this module centers AFTER averaging for
    clarity, without changing the value.

ONE-CLOCK PIN (P35 amendments_applied "LEAKAGE L6", verbatim rule; REVIEW_LEAKAGE.md L6 named the
gap and P35 closed it): for a target row with own team's game date g and season S, EVERY quantity
this module touches -- each history game's opponent's LOO raw-count mean, and the league trailing
mean -- is evaluated using ONLY that opponent's (or the league's) games with game_date STRICTLY
EARLIER than g, within season S; never using the meeting date of the specific historical game
being iterated over. One shared cutoff date per target row, not one cutoff per historical meeting.

SAME-SEASON SCOPE OF THE LEAGUE TRAILING MEAN (card-silent construction detail, resolved and
flagged, not fabricated): neither P33's formula string nor P35's LOO-as-of-date amendment states
explicitly whether "the league trailing mean" is restricted to the target row's own season or
pooled across all seasons. This module reads it as SAME-SEASON, for two reasons stated on the
record: (1) every other quantity in this construction (``raw_t``, ``sched_t``, the E=3 prior-game
counts) is explicitly scoped "over strictly earlier SAME-SEASON games" in both P33's formula
string and the H5 hypothesis text, and the league-mean phrase immediately follows that same-season
framing with no scope change signalled; (2) the mechanism's own stated rationale ("in a 12-13 team
league, early-season trailing pace means are heavily confounded by opponent mix") is an explicitly
WITHIN-SEASON phenomenon -- a cross-season league mean would import between-season pace-level
shifts (rule changes, league-wide tempo drift year over year) that have nothing to do with the
schedule-imbalance mechanism z5 is built to isolate. This is a DIFFERENT quantity, on RAW
possession counts, from the ALL-PRIOR/K-FREE ``Lbar`` construction_pins.d_t_league_mean_pin uses
for A08/A09/A10/A11 (that pin is defined on the lagged REGULATION-EQUIVALENT target column, not on
raw counts, and is not named as applying to A26); it is not silently reused here. Flagged for P37.

E_MIN_PRIOR_GAMES = 3 counts DISTINCT prior same-season games (P33 hyperparameter name is
literally "E_min_prior_games", the same convention as A18/A20).

STRICT LAGGING: a target row's z5 depends ONLY on possession rows and schedule rows whose
game_date is STRICTLY LESS than the target row's own game_date (within the same season, for the
relevant teams and their opponents' opponents). A possession or schedule row sharing the target's
own game_id is therefore never included on the OWN or OPP side's own-history term; it CAN appear
one level removed, as the excluded meeting inside an opponent's own leave-one-out mean, but is
always subtracted out there by construction (the LOO exclusion), never contributing net signal
from the target game itself. Verified directly by TESTS.py in this directory.

Every function here is a pure, deterministic transform of its inputs -- no I/O, no randomness.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

E_MIN_PRIOR_GAMES: int = 3     # P33 hyperparameters.fixed.E_min_prior_games (frozen, verbatim)

REQUIRED_POSSESSIONS_COLS = ("game_id", "offense_team_id")
REQUIRED_UNIVERSE_COLS = ("team_id", "opp_team_id", "game_id", "game_date", "season")


class A26ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No design is returned."""


# --------------------------------------------------------------------------------------------- #
# raw_t(team, game): per-team-game raw possession row count, from possession-level rows
# --------------------------------------------------------------------------------------------- #

def aggregate_game_team_raw_count(possessions: pd.DataFrame) -> pd.Series:
    """One count per (team_id, game_id): the number of possession rows with offense_team_id ==
    team_id in that ONE game (P33 formula: "that game's per-team row count in the possessions
    artifact"). RAW per D9 -- no OT reweighting, no normalization of any kind."""
    missing = [c for c in REQUIRED_POSSESSIONS_COLS if c not in possessions.columns]
    if missing:
        raise A26ConstructionFailure(
            f"possessions frame is missing required columns {missing}; raw_t(t, g) cannot be "
            f"constructed")
    counts = possessions.groupby(["offense_team_id", "game_id"]).size()
    counts.index = counts.index.set_names(["team_id", "game_id"])
    return counts.astype(float)


def _schedule_with_raw(universe: pd.DataFrame, raw_counts: pd.Series) -> pd.DataFrame:
    """The team-game schedule (team_id, opp_team_id, game_id, game_date, season) from ``universe``,
    joined to each row's own raw_t count. Every (team_id, game_id) pair in ``universe`` MUST have a
    matching entry in ``raw_counts`` -- an undefined join is never silently imputed."""
    missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in universe.columns]
    if missing:
        raise A26ConstructionFailure(f"universe is missing required columns {missing}")
    sched = universe[list(REQUIRED_UNIVERSE_COLS)].copy().reset_index(drop=True)
    sched["game_date"] = pd.to_datetime(sched["game_date"])
    key = pd.MultiIndex.from_arrays([sched["team_id"].to_numpy(), sched["game_id"].to_numpy()])
    raw_vals = raw_counts.reindex(key)
    if raw_vals.isna().any():
        bad = sched.loc[raw_vals.isna().to_numpy(), ["team_id", "game_id"]]
        raise A26ConstructionFailure(
            f"{len(bad)} (team_id, game_id) row(s) in the universe have no matching raw_t entry "
            f"in the supplied possessions frame (first few: {bad.head(3).to_dict('records')})")
    sched["raw"] = raw_vals.to_numpy(dtype=float)
    return sched


def _team_season_index(sched: pd.DataFrame) -> dict:
    """{(team_id, season): {dates, raw, opp, cum}} -- per team-season, sorted by (game_date,
    game_id) ascending (mergesort, deterministic tie-break, matching the program's canonical
    ordering used elsewhere in this repository e.g. A08/A16). ``cum`` is an EXCLUSIVE prefix sum:
    cum[i] = sum(raw[:i]), so cum[i] is exactly the sum over the first i strictly-earlier-sorted
    games."""
    out = {}
    for (team, season), grp in sched.groupby(["team_id", "season"], sort=False):
        g = grp.sort_values(["game_date", "game_id"], kind="mergesort")
        raw = g["raw"].to_numpy(dtype=float)
        out[(team, season)] = {
            "dates": g["game_date"].to_numpy(),
            "raw": raw,
            "opp": g["opp_team_id"].to_numpy(),
            "game_ids": g["game_id"].to_numpy(),
            "cum": np.concatenate([[0.0], np.cumsum(raw)]),
        }
    return out


def _league_season_index(sched: pd.DataFrame) -> dict:
    """{season: {dates, cum}} -- ALL team-game raw_t values for that season, sorted by game_date
    (mergesort). Feeds the SAME-SEASON league trailing mean (see module docstring for the
    same-season scoping rationale)."""
    out = {}
    for season, grp in sched.groupby("season", sort=False):
        g = grp.sort_values(["game_date", "game_id", "team_id"], kind="mergesort")
        raw = g["raw"].to_numpy(dtype=float)
        out[season] = {"dates": g["game_date"].to_numpy(), "cum": np.concatenate([[0.0], np.cumsum(raw)])}
    return out


def _prior_count_and_sum(idx: dict, cutoff_date) -> tuple[int, float]:
    """(n, sum) over entries with date STRICTLY earlier than cutoff_date."""
    i = int(np.searchsorted(idx["dates"], cutoff_date, side="left"))
    return i, float(idx["cum"][i])


def _league_mean_prior(league_idx: dict, season, cutoff_date) -> float | None:
    st = league_idx.get(season)
    if st is None:
        return None
    n, s = _prior_count_and_sum(st, cutoff_date)
    if n == 0:
        return None
    return s / n


def _sched_t(team, season, cutoff_date, team_idx: dict, raw_counts: pd.Series) -> tuple[float | None, int]:
    """sched_t (BEFORE league-mean centering) for ``team``, using ONLY that team's own
    strictly-earlier-than-``cutoff_date`` same-season games, per the ONE-CLOCK LOO-as-of-target-
    date rule (P35 amendments_applied "LEAKAGE L6"). Returns (sched_t_or_None, n_prior_games).
    ``sched_t`` is None iff n_prior_games == 0 OR any required opponent LOO mean is undefined
    (an opponent with no OTHER strictly-earlier-than-``cutoff_date`` same-season game besides the
    one meeting being excluded)."""
    st = team_idx.get((team, season))
    if st is None:
        return None, 0
    n_prior, _ = _prior_count_and_sum(st, cutoff_date)
    if n_prior == 0:
        return None, 0

    loo_vals = []
    for k in range(n_prior):
        opp = st["opp"][k]
        game_id_j = st["game_ids"][k]
        opp_st = team_idx.get((opp, season))
        if opp_st is None:
            return None, n_prior     # cannot happen if the universe is two-sided, but fail closed
        n_opp_prior, sum_opp_prior = _prior_count_and_sum(opp_st, cutoff_date)
        raw_opp_in_j = raw_counts.get((opp, game_id_j))
        if raw_opp_in_j is None:
            return None, n_prior
        n_excl = n_opp_prior - 1
        if n_excl <= 0:
            return None, n_prior     # the ONLY required LOO opponent mean is undefined
        sum_excl = sum_opp_prior - float(raw_opp_in_j)
        loo_vals.append(sum_excl / n_excl)

    return float(np.mean(loo_vals)), n_prior


def compute_z5(possessions: pd.DataFrame, universe: pd.DataFrame) -> dict:
    """z5 (and diagnostics) for every row of ``universe``, aligned to its row order.

    z5(row) = c_own - c_opp; c_t = -(sched_t - Lbar); z5 := 0 (P33/P35 E=3-plus-undefined-LOO
    imputation, verbatim, symmetric in own and opponent) when EITHER side has < E_MIN_PRIOR_GAMES
    strictly-earlier same-season games, OR either side's sched_t is undefined (an opponent LOO mean
    required by that side's average could not be formed).
    """
    raw_counts = aggregate_game_team_raw_count(possessions)
    sched = _schedule_with_raw(universe, raw_counts)
    team_idx = _team_season_index(sched)
    league_idx = _league_season_index(sched)

    n = len(universe)
    z5 = np.zeros(n, dtype=float)
    c_own = np.full(n, np.nan, dtype=float)
    c_opp = np.full(n, np.nan, dtype=float)
    n_own = np.zeros(n, dtype=float)
    n_opp = np.zeros(n, dtype=float)
    imputed = np.zeros(n, dtype=bool)
    lbar = np.full(n, np.nan, dtype=float)

    own_teams = universe["team_id"].to_numpy()
    opp_teams = universe["opp_team_id"].to_numpy()
    seasons = universe["season"].to_numpy()
    dates = pd.to_datetime(universe["game_date"]).to_numpy()

    for i in range(n):
        season = seasons[i]
        g = dates[i]
        sched_own, n_prior_own = _sched_t(own_teams[i], season, g, team_idx, raw_counts)
        sched_opp, n_prior_opp = _sched_t(opp_teams[i], season, g, team_idx, raw_counts)
        L = _league_mean_prior(league_idx, season, g)

        n_own[i] = n_prior_own
        n_opp[i] = n_prior_opp
        if L is not None:
            lbar[i] = L

        needs_imputation = (
            n_prior_own < E_MIN_PRIOR_GAMES or n_prior_opp < E_MIN_PRIOR_GAMES
            or sched_own is None or sched_opp is None or L is None
        )
        if needs_imputation:
            imputed[i] = True
            z5[i] = 0.0
            continue

        c_own[i] = -(sched_own - L)
        c_opp[i] = -(sched_opp - L)
        z5[i] = c_own[i] - c_opp[i]

    return {
        "z5": z5, "c_own": c_own, "c_opp": c_opp,
        "n_own": n_own, "n_opp": n_opp, "imputed": imputed, "league_trailing_mean": lbar,
    }


def compute_features(possessions: pd.DataFrame, targets: pd.DataFrame) -> dict:
    """z5 (and diagnostics) for every row of ``targets``, aligned to its row order. ``targets``
    must carry team_id, opp_team_id, game_id, game_date, season (the full schedule -- ``targets``
    IS the ``universe`` this construction reasons over; there is no separate history frame).
    ``possessions`` must carry game_id, offense_team_id (possessions_raw_v2 at P38 time; a
    synthetic possession-level fixture in tests)."""
    missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in targets.columns]
    if missing:
        raise A26ConstructionFailure(f"A26 compute_features requires column(s) {missing} on the "
                                     f"targets frame")
    return compute_z5(possessions, targets)
