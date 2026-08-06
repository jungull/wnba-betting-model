#!/usr/bin/env python3
"""arm_a13.py -- P36 arm module for A13_carryover_roster_continuity_moderator.

FROZEN CARD (verbatim binding source): experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/
SPEC.json, sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32 (verified at
implementation time), task_cards[].arm_id == "A13_carryover_roster_continuity_moderator", carrying
P33 PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8
d072d347d093) arm A13 by hash reference, amended exactly by the card's amendments_applied list.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

MODEL (frozen, card-pinned):
    eta = A12's FULL arm design + b_c*cont_i + beta3*(cont_i - cbar_F)*dev_prev_i
    mu  = exp(eta)
    free global intercept, arm AND null identically (P35 intercept_structure table: A13 in
    ARMS_WITH_FREE_GLOBAL_INTERCEPT).
    treatment = the single centered interaction, 1 df: (cont_i - cbar_F) * dev_prev_i

A12's FULL ARM DESIGN (this module's own self-contained reconstruction -- A12 is not yet
implemented anywhere in this shared directory, and per standing rule 2 this unit may write and
import ONLY inside arms/A13/, so the A12 machinery A13's own card names as its base is
reconstructed here, byte-for-byte from the frozen A12 card, rather than imported):
    intercept + gap + depth + opp_depth + w(n_i) [main] + dev_prev_i + w(n_i)*dev_prev_i
    w(n) = 1/(1 + n/5), h = 5 FIXED (A12 hyperparameters.fixed.h; A13 "inherits A12's frozen h").

CONT_I -- roster-continuity Jaccard moderator (frozen construction). The P35/P33 SPEC.json card
text states only the condensed formula "cont_i = Jaccard(P_curr_i, P_prev_i) over player-id sets
from off_p1..off_p5 / def_p1..def_p5 of strictly earlier games" -- on its own this leaves WHICH
strictly-earlier games P_curr_i and P_prev_i denote underdetermined. That full definition is
established, without ambiguity, in this arm's SOLE NAMED PROVENANCE record (P32_CANDIDATE_
SYNTHESIS/SPEC.json line 301: "provenance": HYPOTHESES_coldstart_fallback.md, section
COLDSTART_FALLBACK_H4 -- the frozen hypothesis text P32/P33/P35 all condense from, never
superseded or amended by any P34/P35 amendment):

    P_curr_i = union of player ids in off_p1..off_p5 / def_p1..def_p5 rows of team i's COMPLETED
               SAME-SEASON games strictly before the target game_date (empty when n_i = 0)
    P_prev_i = same construction over team i's FULL PRIOR SEASON (season_i - 1), entirely in the
               past relative to the target game, so no per-game "strictly before" restriction is
               needed within that season
    cont_i   = Jaccard(P_curr_i, P_prev_i); fallback: cont_i := training-fold mean of the DEFINED
               (n_i > 0) values of cont, held IDENTICAL in arm and null, when n_i = 0
               (HYPOTHESES_coldstart_fallback.md H4 "Formula sketch"; P35 A13 amendment LEAKAGE
               L4: "the n=0 imputation constant is likewise the TRAINING-row mean").

This resolution is disclosed here and in this module's tests rather than silently assumed --
per standing rule 1 (frozen bytes govern over prose): nothing in P34/P35 restates or amends the H4
provenance text, and the P32/P33/P35 formula strings are verbatim condensations of it, not a
competing definition. If P37 finds a different reading intended, this is the single place that
reading changes.

n_i (frozen, card-pinned; K0 K6 / shared construction_pins.n_clock_pin, "as A12"):
    same-season completed prior game count, computed on the CONTRACT SCHEDULE (the 2,990-row
    superset), per the frozen n_clock_pin ("the universe-row clock is barred").

dev_prev_i (frozen, "as A12"; TARGETUNITS B2 / lagged_regulation_equivalent_pin, which names A12
explicitly): team's prior-SEASON mean of the lagged regulation-equivalent realised value
    n_off_poss * 40 / (40 + 5*max(0, max_period - 4))
minus that PRIOR SEASON's own league mean of the same quantity (a per-season aggregate, distinct
from A08-A11's ALL-PRIOR d_t_league_mean_pin, which this arm's card never invokes). dev_prev_i :=
0, identically in arm and null, for a team with no games in season_i - 1 (A12's own "no-prior-
season teams get dev_prev = 0 identically" rule, carried).

K0_MATCHED[A13] (frozen, card k0_matched_frozen): null = A12's full arm design PLUS the cont main
effect, with identical n=0 fallback machinery, arm and null; comparison = term_removal; the
treatment adds ONLY the centered interaction. "uniform carryover belongs to the null; credit only
for continuity-CONDITIONING."

FOLD-LOCAL FALLBACK (frozen, card p26_k0_record.fold_local_fallback / P35 registry_append
S7_TIER_SUPPORT_v1__A13): >= 10 training clusters with a defined, nonconstant interaction column
-- activates train_lt_2023..train_lt_2026 (train_lt_2022 has zero training clusters with a
resolved prior season, so the generic S7 mechanism drops the treatment there by construction; no
separate structural-deactivation hook is needed, matching A12's own carried rule).

KILL CONDITIONS (frozen, card kill_conditions_frozen): beta3 interval covers 0 given A12's terms;
beta3 < 0 (refutes mechanism); P22 adjudication failure (inadmissible, not null) -- the card's own
declaration that a failed lagged-lineup admissibility check makes the HYPOTHESIS inadmissible, not
a null result.

FIXED SEQUENCE (P35 shared a13_fixed_sequence_level_pinned / card multiplicity): A13's result is
confirmatory only if A12 rejects under the stricter of its dual-family Holm corrections; otherwise
EXPLORATORY. A13's element always occupies its COLDSTART_FALLBACK slot regardless. This module
records the rule as decidable machinery (`fixed_sequence_label`) but performs no fit and consults
no A12 result -- that adjudication happens downstream of this unit's scope.

D4 preserved disagreement (carried verbatim, card): the opponent_mechanism source held the lineup
family EMPTY this wave; the packet's S8 LAGGED_USE_ONLY licence governs here; the narrower reading
is preserved, not silently harmonized.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------------------------
# frozen pins, restated here as COPIED VALUES (never a runtime import from runner/), per this
# unit's write scope (arms/A13/ only) and A07's precedent (module docstring, same convention).
# ---------------------------------------------------------------------------------------------
ARM_ID = "A13_carryover_roster_continuity_moderator"
OFFSET_COL = "log_exposure"
TARGET_LABEL = "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"
INTERCEPT_COL = "intercept"

GAP_COL = "pace_gap"
DEPTH_COL = "pace_evidence_depth"
OPP_DEPTH_COL = "opp_pace_evidence_depth"
WN_COL = "w_n"                                  # A12's w(n_i) main term
DEV_PREV_COL = "dev_prev"                       # A12's dev_prev_i
WN_DEV_PREV_COL = "w_n:dev_prev"                # A12's second treatment term (carried into A13's K0)
CONT_MAIN_COL = "cont_i"                        # A13's own main effect (lower-order rule)
#: A13's single centered-interaction treatment. NAMED "cont_i:dev_prev" (not the mathematically
#: fuller "(cont_i - cbar_F):dev_prev", which the P33/P35 card prose itself uses) because the
#: FROZEN P26 validator (validate_k0_matched.check_relation, rule R6) splits any treatment_terms
#: entry on ":" and requires each resulting factor to be a LITERAL structural_terms entry in K0 --
#: "(cont_i - cbar_F)" is not itself a design column and would fail that literal-name match even
#: though cont_i (its centered form) correctly is. Per standing rule 3 this shared gate is never
#: edited; the compound name is chosen to satisfy its marginality-closure convention while the
#: COMPUTED VALUES remain exactly the card's centered interaction -- see build_design() below.
TREATMENT_COL = "cont_i:dev_prev"

H_FIXED = 5.0                                    # A12's h, "inherited" verbatim by A13
TIER_FLOOR_CLUSTERS = 10                         # S7_TIER_SUPPORT_v1 numeric trigger
S7_RULE_ID = "S7_TIER_SUPPORT_v1"
ACTIVE_SET_RULE_PREREGISTRATION_SHA256 = (
    "327fa8ec9fb54e3635ae70b540573b4121c6136fc5034cbdb689cabbe2986db7")
P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"
TEAM_CITIES_SHA256_PIN = "10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d"

REQUIRED_UNIVERSE_COLS = ("team_id", "season", "game_date", GAP_COL, DEPTH_COL, OPP_DEPTH_COL)
REQUIRED_SCHEDULE_COLS = ("team_id", "season", "game_date", "game_id")
REQUIRED_HISTORY_COLS = ("team_id", "season", "game_id", "n_off_poss", "max_period")
REQUIRED_LINEUP_COLS = ("team_id", "game_id", "player_id")


class A13ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No design is returned."""


# --------------------------------------------------------------------------------------------- #
# n_i: strictly-earlier same-season CONTRACT-SCHEDULE completed-game count (frozen n_clock_pin,
# "as A12"). Self-contained re-derivation of the same pure logic A07's module documents.
# --------------------------------------------------------------------------------------------- #

def compute_n_i(contract_schedule: pd.DataFrame, team_id: np.ndarray, season: np.ndarray,
                game_date: np.ndarray) -> np.ndarray:
    """n_i for each row: count of the team's CONTRACT-SCHEDULE same-season games with
    game_date STRICTLY earlier than the row's own game_date. Deterministic, order-independent."""
    missing = [c for c in ("team_id", "season", "game_date") if c not in contract_schedule.columns]
    if missing:
        raise A13ConstructionFailure(
            f"contract_schedule is missing required columns {missing}; n_i (n_clock_pin) cannot "
            f"be computed on the contract-schedule clock")
    sched = contract_schedule[["team_id", "season", "game_date"]].copy()
    sched["game_date"] = pd.to_datetime(sched["game_date"])
    team_id = np.asarray(team_id)
    season = np.asarray(season)
    gd = pd.to_datetime(pd.Series(np.asarray(game_date)))

    out = np.full(len(team_id), -1.0, dtype=float)
    for (tid, seas), grp in sched.groupby(["team_id", "season"], sort=False):
        dates = np.sort(grp["game_date"].unique())
        mask = (team_id == tid) & (season == seas)
        if not mask.any():
            continue
        out[mask] = np.searchsorted(dates, gd[mask].to_numpy(), side="left").astype(float)

    unresolved = int((out < 0).sum())
    if unresolved:
        raise A13ConstructionFailure(
            f"{unresolved} universe row(s) have a (team_id, season) pair absent from the supplied "
            f"contract_schedule; n_i is undefined for them and the frozen n_clock_pin forbids "
            f"falling back to the universe-row clock")
    return out


def w_of_n(n_i: np.ndarray, h: float = H_FIXED) -> np.ndarray:
    """A12's w(n) = 1/(1 + n/h), h = 5 FIXED by source."""
    return 1.0 / (1.0 + np.asarray(n_i, dtype=float) / float(h))


# --------------------------------------------------------------------------------------------- #
# dev_prev_i: prior-SEASON mean lagged regulation-equivalent possessions minus that season's own
# league mean ("as A12"; TARGETUNITS B2 period-based rescale, D9 convention for A12/A13).
# --------------------------------------------------------------------------------------------- #

def lagged_reg_equiv(n_off_poss: np.ndarray, max_period: np.ndarray) -> np.ndarray:
    n_off_poss = np.asarray(n_off_poss, dtype=float)
    max_period = np.asarray(max_period, dtype=float)
    denom = 40.0 + 5.0 * np.maximum(0.0, max_period - 4.0)
    return n_off_poss * 40.0 / denom


def compute_dev_prev(history: pd.DataFrame, team_id: np.ndarray, season: np.ndarray
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Returns (dev_prev, has_prior_season). history carries EVERY team-game's own realised
    lagged reg-equiv value (n_off_poss, max_period), spanning every season the universe can query
    a "prior season" for -- an entirely-in-the-past aggregate per row, never restricted further by
    game_date within that prior season (A12 "prior-season mean ... strictly earlier [than the
    target's own season]")."""
    missing = [c for c in REQUIRED_HISTORY_COLS if c not in history.columns]
    if missing:
        raise A13ConstructionFailure(f"history frame is missing required columns {missing}")
    h = history.copy()
    h["_value"] = lagged_reg_equiv(h["n_off_poss"].to_numpy(), h["max_period"].to_numpy())
    team_season_mean = h.groupby(["team_id", "season"])["_value"].mean()
    league_season_mean = h.groupby("season")["_value"].mean()

    team_id = np.asarray(team_id)
    season = np.asarray(season, dtype=float)
    dev = np.zeros(len(team_id), dtype=float)
    has_prior = np.zeros(len(team_id), dtype=bool)
    for i, (t, s) in enumerate(zip(team_id, season)):
        prior = s - 1.0
        key = (t, prior)
        if key in team_season_mean.index and prior in league_season_mean.index:
            dev[i] = float(team_season_mean.loc[key] - league_season_mean.loc[prior])
            has_prior[i] = True
        # else: no archived prior season for this team -- dev_prev := 0 (A12's own rule, carried)
    return dev, has_prior


# --------------------------------------------------------------------------------------------- #
# cont_i: roster-continuity Jaccard moderator (H4 provenance; see module docstring)
# --------------------------------------------------------------------------------------------- #

def team_game_rosters(lineup_membership: pd.DataFrame) -> dict:
    """{(team_id, game_id): frozenset(player_id)} -- one row per team-game player membership,
    already collapsed from off_p1..off_p5/def_p1..def_p5 upstream of this module (a plain
    (team_id, game_id, player_id) long frame is the natural canonical form for "the set of player
    ids a team used in a game" and is what this module requires as its lineup source)."""
    missing = [c for c in REQUIRED_LINEUP_COLS if c not in lineup_membership.columns]
    if missing:
        raise A13ConstructionFailure(f"lineup_membership frame is missing required columns {missing}")
    out: dict = {}
    for (t, g), grp in lineup_membership.groupby(["team_id", "game_id"], sort=False):
        out[(t, g)] = frozenset(grp["player_id"].tolist())
    return out


def _union_rosters(rosters: dict, team_id, game_ids) -> frozenset:
    s: set = set()
    for g in game_ids:
        s |= rosters.get((team_id, g), frozenset())
    return frozenset(s)


def compute_p_curr_p_prev(contract_schedule: pd.DataFrame, rosters: dict,
                          team_id: np.ndarray, season: np.ndarray, game_date: np.ndarray
                          ) -> tuple[list, list]:
    """P_curr_i: union of rosters over team i's completed SAME-SEASON contract-schedule games
    strictly before game_date(i) (empty when n_i = 0).
    P_prev_i: union of rosters over ALL of team i's contract-schedule games in season_i - 1
    (the whole prior season is in the past; no further "strictly before" cut is needed).
    Deterministic, a pure function of (contract_schedule, rosters) and the query arrays."""
    missing = [c for c in REQUIRED_SCHEDULE_COLS if c not in contract_schedule.columns]
    if missing:
        raise A13ConstructionFailure(f"contract_schedule is missing required columns {missing}")
    sched = contract_schedule[list(REQUIRED_SCHEDULE_COLS)].copy()
    sched["game_date"] = pd.to_datetime(sched["game_date"])
    gd = pd.to_datetime(pd.Series(np.asarray(game_date))).to_numpy()
    team_id = np.asarray(team_id)
    season = np.asarray(season, dtype=float)

    by_team_season = {k: v for k, v in sched.groupby(["team_id", "season"], sort=False)}

    p_curr, p_prev = [], []
    for t, s, d in zip(team_id, season, gd):
        cur_grp = by_team_season.get((t, s))
        if cur_grp is None:
            cur_games = []
        else:
            cur_games = cur_grp.loc[cur_grp["game_date"].to_numpy() < d, "game_id"].tolist()
        p_curr.append(_union_rosters(rosters, t, cur_games))

        prev_grp = by_team_season.get((t, s - 1.0))
        prev_games = [] if prev_grp is None else prev_grp["game_id"].tolist()
        p_prev.append(_union_rosters(rosters, t, prev_games))
    return p_curr, p_prev


def jaccard(a: frozenset, b: frozenset) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def compute_cont_raw(p_curr: Sequence[frozenset], p_prev: Sequence[frozenset],
                     n_i: np.ndarray) -> np.ndarray:
    """NaN (undefined, to be imputed by the per-fold training mean) exactly where n_i == 0
    (P_curr_i is empty by construction there); the defined Jaccard value everywhere n_i > 0."""
    n = len(n_i)
    out = np.full(n, np.nan, dtype=float)
    n_i = np.asarray(n_i, dtype=float)
    for i in range(n):
        if n_i[i] > 0:
            out[i] = jaccard(p_curr[i], p_prev[i])
    return out


def fold_training_mean_defined(cont_raw: np.ndarray, train_idx: np.ndarray) -> float:
    """cbar_F: mean of cont's DEFINED values over the fold's TRAINING rows only (P35 LEAKAGE L4).
    Computed once per build_design call (once per fold, per the frozen §3 contract), never inside
    a bootstrap refit."""
    tr = np.asarray(train_idx, dtype=int)
    vals = np.asarray(cont_raw, dtype=float)[tr]
    defined = vals[~np.isnan(vals)]
    if defined.size == 0:
        # no training row has a resolved cont value in this fold (e.g. train_lt_2022, where no
        # team has an archived prior season): the S7 active-set rule will drop the treatment for
        # this fold on its own (0 nonzero-support clusters < the 10-cluster floor); the constant
        # itself is harmless here since (cont_i - cbar_F) is multiplied by dev_prev, which is
        # identically 0 for every such row too.
        return 0.0
    return float(np.mean(defined))


# --------------------------------------------------------------------------------------------- #
# kill-condition hooks (frozen card kill_conditions_frozen) -- pure functions of synthetic /
# fold-summary inputs, exactly mirroring A07/A03's precedent.
# --------------------------------------------------------------------------------------------- #

def beta3_ci_kill(fold_intervals: Sequence[tuple[float, float]]) -> bool:
    """Kill iff the beta3 95% training-cluster bootstrap interval covers 0 in EVERY evaluable
    fold (card: "beta3 interval covers 0 given A12's terms"). No evaluable folds -> undecidable,
    not killed; the caller records the empty-evaluable-set finding separately."""
    if not fold_intervals:
        return False
    return all(lo <= 0.0 <= hi for lo, hi in fold_intervals)


def beta3_negative_kill(fold_points: Sequence[float]) -> bool:
    """Kill iff the pooled/point estimate of beta3 is negative in a fold that rejects 0 (card:
    "beta3 < 0 (refutes mechanism)" -- a NEGATIVE, non-zero-covering estimate refutes the claimed
    direction outright, distinct from the no-rejection kill above)."""
    return any(v < 0.0 for v in fold_points)


def p22_inadmissible_kill(p22_blocking: bool) -> bool:
    """Card: "P22 adjudication failure (inadmissible, not null)" -- the lagged-lineup
    construction's own S8 LAGGED_USE_ONLY licence requires P22 to pass; failure makes the
    HYPOTHESIS inadmissible, a distinct verdict from a fitted null result."""
    return bool(p22_blocking)


def evaluate_kill_conditions(*, fold_intervals: Sequence[tuple[float, float]],
                             fold_points: Sequence[float],
                             p22_blocking: bool = False) -> dict:
    """One decidable verdict per frozen kill rule. P22 inadmissibility is checked FIRST and, if
    fired, is recorded as its own verdict rather than folded into "killed" -- the card explicitly
    distinguishes INADMISSIBLE from a fitted null/kill outcome."""
    if p22_inadmissible_kill(p22_blocking):
        return {"inadmissible": True, "killed": None,
               "reason": "P22 adjudication failure on the lagged-lineup construction -- "
                         "HYPOTHESIS INADMISSIBLE, not a fitted null result (card-pinned)"}
    ci = beta3_ci_kill(fold_intervals)
    neg = beta3_negative_kill(fold_points)
    return {
        "inadmissible": False,
        "beta3_ci_covers_zero_every_fold": ci,
        "beta3_negative_in_some_fold": neg,
        "killed": bool(ci or neg),
    }


def fixed_sequence_label(a12_rejects_under_stricter_correction: bool | None) -> str:
    """P35 shared a13_fixed_sequence_level_pinned: CONFIRMATORY iff A12 passes its own primary
    gate under the STRICTER of its two dual-family Holm corrections; else EXPLORATORY. This
    module never fits A12 or consults its result -- it exposes the decision rule only, as a pure
    function of a caller-supplied boolean, per the frozen wording."""
    if a12_rejects_under_stricter_correction is None:
        return "UNDECIDABLE_A12_RESULT_NOT_SUPPLIED"
    return "CONFIRMATORY" if a12_rejects_under_stricter_correction else "EXPLORATORY"


# --------------------------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------------------------- #

def _digest(*parts: Any) -> str:
    import hashlib
    import json
    return "sha256:" + hashlib.sha256(
        json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _sidespec(fold_ids: Sequence[str], training_digest: str, evaluation_digest: str) -> dict:
    return {
        "intercept_treatment": "free unpenalised single global intercept, explicit 'intercept' "
                               "column of ones, identical in arm and null (P35 intercept_structure "
                               "table: A13 in ARMS_WITH_FREE_GLOBAL_INTERCEPT)",
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{OFFSET_COL} = log(projected_team_off_possessions), frozen incumbent "
                           "D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": training_digest,
        "evaluation_rows": evaluation_digest,
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": (f"{GAP_COL}/{DEPTH_COL}/{OPP_DEPTH_COL} carried unchanged from the "
                         "receipted incumbent-path feature frame (as A07/A12); "
                         f"{WN_COL} = 1/(1+n_i/5), n_i on the contract-schedule clock; "
                         f"{DEV_PREV_COL} = prior-season mean lagged reg-equiv possessions minus "
                         "that season's league mean, 0 with no archived prior season (as A12); "
                         f"{CONT_MAIN_COL} = Jaccard(P_curr_i, P_prev_i) over lagged lineup "
                         "player-id sets (H4 provenance, see module docstring), imputed to the "
                         "fold's training-row mean at n_i = 0; treatment = "
                         f"({CONT_MAIN_COL} - cbar_F) * {DEV_PREV_COL}, cbar_F the SAME "
                         "training-fold mean, computed once per fold and held fixed across "
                         "bootstrap refits (P35 LEAKAGE L4), identical in arm and null"),
        "missing_value_handling": (f"{DEV_PREV_COL} := 0 for a team with no archived prior "
                                  f"season; {CONT_MAIN_COL} := cbar_F (training-fold mean of its "
                                  "defined values) at n_i = 0 -- both deterministic, symmetric, "
                                  "arm and null identical"),
        "companion_components": "none",
        "fallback_rules": f"{S7_RULE_ID}: >= {TIER_FLOOR_CLUSTERS} training clusters with a "
                          "defined, nonconstant interaction column required for the treatment to "
                          "enter a fold; identically arm and null (fixed-slot mechanism collapses "
                          "train_lt_2022 to 0 qualifying clusters by construction)",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the 2,982-row resolved possession universe (1,491 game clusters); "
                              "n_i/dev_prev/cont are computed on the 2,990-row contract-schedule "
                              "superset and the full lagged-lineup history",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


# --------------------------------------------------------------------------------------------- #
# the arm module
# --------------------------------------------------------------------------------------------- #

class ArmA13:
    """P36 RUNNER_INTERFACE-conformant module for A13_carryover_roster_continuity_moderator.

    Constructed with three frames beyond ``universe`` (mirrors A07/A09's convention of binding
    lag-source supersets at construction, since the frozen hooks take no per-call arguments):

      * ``contract_schedule``: (team_id, season, game_date, game_id) contract-schedule superset
        (2,990 rows in the real archive), used for n_i and the P_curr/P_prev game-set lookups.
      * ``history``: (team_id, season, game_id, n_off_poss, max_period) for every team-game whose
        realised value dev_prev's prior-season aggregates can draw on.
      * ``lineup_membership``: (team_id, game_id, player_id) long frame -- the set of players a
        team used in a game, already collapsed from off_p1..off_p5/def_p1..def_p5 upstream (P22
        adjudication REQUIRED on this construction per the card; failure is INADMISSIBLE).
    """

    arm_id = ARM_ID

    def __init__(self, contract_schedule: pd.DataFrame, history: pd.DataFrame,
                lineup_membership: pd.DataFrame, fold_ids: Sequence[str] = (),
                n_rows: int | None = None):
        missing = [c for c in REQUIRED_SCHEDULE_COLS if c not in contract_schedule.columns]
        if missing:
            raise A13ConstructionFailure(f"contract_schedule missing required columns {missing}")
        self._contract_schedule = contract_schedule.reset_index(drop=True)
        self._history = history.reset_index(drop=True)
        self._lineup_membership = lineup_membership.reset_index(drop=True)
        self._rosters = team_game_rosters(self._lineup_membership)
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows) if n_rows is not None else int(len(contract_schedule))
        self._last_cbar_f: dict[str, float] = {}   # fold_id -> cbar_F, for inspection/tests only

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        return {}                      # single-element arm ("inherits A12's frozen h", no grid)

    def element_id(self) -> str:
        return "A13_carryover_roster_continuity_moderator__single"

    def uses_global_intercept(self) -> bool:
        return True                    # P35 intercept table: A13 in ARMS_WITH_FREE_GLOBAL_...

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in universe.columns]
        if missing:
            raise A13ConstructionFailure(
                f"universe is missing required columns {missing} (receipted incumbent-path "
                f"gap/depth/opp_depth columns, or team_id/season/game_date identity columns)")

        team_id = universe["team_id"].to_numpy()
        season = universe["season"].to_numpy()
        game_date = universe["game_date"].to_numpy()

        n_i = compute_n_i(self._contract_schedule, team_id, season, game_date)
        w_n = w_of_n(n_i)
        dev_prev, _has_prior = compute_dev_prev(self._history, team_id, season)
        p_curr, p_prev = compute_p_curr_p_prev(self._contract_schedule, self._rosters,
                                               team_id, season, game_date)
        cont_raw = compute_cont_raw(p_curr, p_prev, n_i)
        cbar_f = fold_training_mean_defined(cont_raw, fold["train_idx"])
        self._last_cbar_f[str(fold["fold_id"])] = cbar_f
        cont_i = np.where(np.isnan(cont_raw), cbar_f, cont_raw)

        w_n_dev_prev = w_n * dev_prev
        treatment = (cont_i - cbar_f) * dev_prev

        columns = {
            GAP_COL: universe[GAP_COL].to_numpy(dtype=float),
            DEPTH_COL: universe[DEPTH_COL].to_numpy(dtype=float),
            OPP_DEPTH_COL: universe[OPP_DEPTH_COL].to_numpy(dtype=float),
            INTERCEPT_COL: np.ones(len(universe), dtype=float),
            WN_COL: w_n,
            DEV_PREV_COL: dev_prev,
            WN_DEV_PREV_COL: w_n_dev_prev,
            CONT_MAIN_COL: cont_i,
            TREATMENT_COL: treatment,
        }
        # A12's full arm design PLUS cont main effect -- this IS A13's null (K0_MATCHED[A13]).
        nuisance = [INTERCEPT_COL, GAP_COL, DEPTH_COL, OPP_DEPTH_COL, WN_COL,
                   DEV_PREV_COL, WN_DEV_PREV_COL, CONT_MAIN_COL]
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": nuisance,
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": list(nuisance),
                                  "comparison": "term_removal"},
            "indicator_cols": [],       # every column here is continuous; intercept is structural
            "columns": columns,
        }

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        train_digest = _digest("A13_training_rows", self._fold_ids, self._n_rows)
        eval_digest = _digest("A13_evaluation_rows", self._fold_ids, self._n_rows)
        side = _sidespec(self._fold_ids, train_digest, eval_digest)
        structural = [INTERCEPT_COL, GAP_COL, DEPTH_COL, OPP_DEPTH_COL, WN_COL,
                     DEV_PREV_COL, WN_DEV_PREV_COL, CONT_MAIN_COL]
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "prior-season carryover (A12's dev_prev mechanism) is heterogeneous "
                            "in how much of the roster that generated last season's identity is "
                            "still on the team this season; cont_i (Jaccard lineup overlap "
                            "between the team's evidence so far this season and its full prior "
                            "season) moderates dev_prev's coefficient via a single centered "
                            "interaction term, crediting the arm ONLY for the continuity-"
                            "conditioning, never for uniform carryover itself",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "beta3", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "carryover not moderated by "
                                                             "continuity"}],
                "claimed_signal_axes": ["roster", "support_size"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        f"removing {TREATMENT_COL} leaves A12's full carryover design plus the "
                        f"{CONT_MAIN_COL} main effect; the null can still express a uniform "
                        "continuity level shift and uniform carryover, but cannot let dev_prev's "
                        "own coefficient vary with continuity -- the claimed moderation signal is "
                        "destroyed by construction, exactly the S6 lower-order rule the card "
                        "requires")}},
            "invariants": {
                "rows": train_digest,
                "target": TARGET_LABEL,
                "folds": list(self._fold_ids),
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": list(structural),
                "lower_order_structural_terms": list(structural)},
            "arm_spec": {
                "name": "A13_carryover_roster_continuity_moderator", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [TREATMENT_COL],
                "structural_terms": list(structural),
                "declaration_routing": {
                    TREATMENT_COL: "substantive_features",
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", WN_COL: "preprocessing",
                    DEV_PREV_COL: "preprocessing", WN_DEV_PREV_COL: "preprocessing",
                    CONT_MAIN_COL: "preprocessing", INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "A13_carryover_roster_continuity_moderator__K0_MATCHED", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": list(structural),
                "declaration_routing": {
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", WN_COL: "preprocessing",
                    DEV_PREV_COL: "preprocessing", WN_DEV_PREV_COL: "preprocessing",
                    CONT_MAIN_COL: "preprocessing", INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": dict(side)},
            "fold_local_fallback": {
                "required": True,
                "trigger": (f"{S7_RULE_ID}: fewer than {TIER_FLOOR_CLUSTERS} training game "
                           f"clusters carry a defined, nonconstant {TREATMENT_COL} column "
                           "(mirrors A12's active-set rule; train_lt_2022 has zero such clusters "
                           "by construction -- no team has an archived prior season in a "
                           "2021-only training set, so the rule drops the treatment there "
                           "identically in arm and null without a separate structural-"
                           "deactivation declaration)"),
                "numeric_threshold": TIER_FLOOR_CLUSTERS,
                "action": "drop_term_for_fold",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature arm: eligible for a "
                                    "continuity-moderation verdict ONLY against K0_MATCHED[A13], "
                                    "and only as FIXED-SEQUENCE confirmatory if A12 rejects under "
                                    "the stricter of its dual-family Holm corrections (else "
                                    "EXPLORATORY, per P35 a13_fixed_sequence_level_pinned); "
                                    "K0_FLAT carries no promotion value whatsoever.",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "K0 K6 / n_clock_pin: n_i counted on the CONTRACT SCHEDULE (2,990 rows).",
                "LEAKAGE L4: cbar_F (the interaction's centering constant AND the n_i=0 cont_i "
                "imputation constant) is the mean of cont's DEFINED values over the fold's "
                "TRAINING rows ONLY, computed once per fold, held fixed across bootstrap refits, "
                "identical in arm and null.",
                "MULT B-6b / a13_fixed_sequence_level_pinned: confirmatory iff A12 passes its "
                "own primary gate under the stricter of its two dual-family Holm corrections; "
                "else EXPLORATORY. A13's element occupies its COLDSTART_FALLBACK slot either "
                "way. Out of scope for this feature-construction module (fixed_sequence_label() "
                "exposes the rule as a pure function of a caller-supplied A12 result).",
                "D4 preserved disagreement (carried verbatim): the opponent_mechanism source "
                "held the lineup-continuity family EMPTY this wave; the packet's S8 "
                "LAGGED_USE_ONLY licence governs this arm's construction; the narrower reading "
                "is preserved, not silently harmonized.",
                "cont_i's precise P_curr_i/P_prev_i game-set definition is resolved from this "
                "arm's sole named provenance (P31 HYPOTHESES_coldstart_fallback.md, section "
                "COLDSTART_FALLBACK_H4), not restated verbatim in the P33/P35 condensed card "
                "text -- disclosed in this module's docstring, not silently assumed.",
            ],
        }

    # ---- guards ---------------------------------------------------------------------
    def lag_specs(self) -> dict:
        gap_rationale = ("difference of two prior-games-only trailing-window pace means, "
                         "receipted incumbent-path feature already in the audited universe "
                         "frame (as A07/A12)")
        return {
            GAP_COL: {"column": GAP_COL, "kind": "DERIVED_NO_JOIN",
                      "source_artifact_id": "team_possession_prior/1",
                      "entity_keys": ("game_id", "team_id"), "rationale": gap_rationale},
            DEPTH_COL: {"column": DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                       "source_artifact_id": "team_possession_prior/1",
                       "entity_keys": ("game_id", "team_id"),
                       "rationale": "count of prior games backing the team's own pace estimate"},
            OPP_DEPTH_COL: {"column": OPP_DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "team_possession_prior/1",
                           "entity_keys": ("game_id", "team_id"),
                           "rationale": "same evidence-depth count, for the opponent"},
            WN_COL: {"column": WN_COL, "kind": "SCHEDULE",
                    "source_artifact_id": "team_possession_prior/1",
                    "entity_keys": ("team_id", "season"), "order_column": "game_date",
                    "rationale": "1/(1+n_i/5), a deterministic transform of the pure schedule "
                                "fact n_i (same-season completed-game count, contract-schedule "
                                "clock, n_clock_pin); no dependency on any realised in-game "
                                "quantity of the target game or any other game"},
            DEV_PREV_COL: {"column": DEV_PREV_COL, "kind": "DERIVED_NO_JOIN",
                          "source_artifact_id": "team_possession_history/1",
                          "entity_keys": ("team_id", "season"),
                          "rationale": "team's prior-SEASON mean lagged regulation-equivalent "
                                      "possessions minus that season's own league mean; "
                                      "TARGETUNITS B2 period-based construction (D9 convention "
                                      "for A12/A13); the entire prior season is strictly earlier "
                                      "than any row of the target season, so no further lag "
                                      "re-derivation applies within it"},
            WN_DEV_PREV_COL: {"column": WN_DEV_PREV_COL, "kind": "DERIVED_NO_JOIN",
                             "source_artifact_id": "team_possession_history/1",
                             "entity_keys": ("team_id", "season"),
                             "rationale": "product of two already-declared columns (w_n, "
                                         "dev_prev); carries no independent dependency"},
            CONT_MAIN_COL: {"column": CONT_MAIN_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "lagged_lineup_membership/1",
                           "entity_keys": ("team_id", "game_id"),
                           "rationale": "Jaccard(P_curr_i, P_prev_i) over off_p1..off_p5/"
                                       "def_p1..def_p5 player-id sets of STRICTLY EARLIER games "
                                       "only (S8 LAGGED_USE_ONLY; H4 provenance, see module "
                                       "docstring); P22 adjudication is REQUIRED by the card -- "
                                       "failure makes this hypothesis INADMISSIBLE, not null"},
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "lagged_lineup_membership/1",
                           "entity_keys": ("team_id", "game_id"),
                           "rationale": f"({CONT_MAIN_COL} - cbar_F) * {DEV_PREV_COL}; cbar_F is "
                                       "a fold-training-only constant (LEAKAGE L4), held fixed "
                                       "across bootstrap refits, so the treatment column carries "
                                       "no dependency beyond its two declared component columns"},
        }

    def lag_sources(self) -> dict:
        return {"contract_schedule": self._contract_schedule, "history": self._history,
               "lineup_membership": self._lineup_membership}

    def preregistered_contrasts(self):
        return None            # A13 registers no P25 contrast column (that is A02's obligation)

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 p23_franchise_continuity_precondition names A13 explicitly.
        return True

    def p23_receipts(self) -> list:
        return [{
            "team_cities_sha256": TEAM_CITIES_SHA256_PIN,
            "scope": "A13: dev_prev/cont_i are cross-season history features (team_id-keyed, no "
                    "team_cities join performed by this module); this receipt attests the "
                    "frozen franchise-continuity pin per P35 franchise_continuity_receipt_pin / "
                    "the P33 precondition naming A13.",
        }]

    def p27_rule(self):
        """The generic P27 mechanism, fed honestly: candidate_features == [TREATMENT_COL] at the
        runner call site, so this rule's cluster-support count is measured directly on the
        interaction column itself -- exactly the card's own "defined, nonconstant interaction"
        wording, unlike A03 where the card's rule spans a tier the design has no column for."""
        import importlib.util
        import sys
        from pathlib import Path
        here = Path(__file__).resolve().parent           # .../P36_IMPLEMENT_ARMS/arms/A13
        stage2b = here.parents[2]                          # .../stage2b
        feg_path = stage2b / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD" / "fold_estimability_guard.py"
        name = "p27_fold_estimability_guard_for_A13"
        if name in sys.modules:
            feg = sys.modules[name]
        else:
            spec = importlib.util.spec_from_file_location(name, feg_path)
            feg = importlib.util.module_from_spec(spec)
            sys.modules.setdefault(name, feg)
            spec.loader.exec_module(feg)

        rule = feg.ActiveSetRule(
            rule_id=S7_RULE_ID,
            min_nonzero_clusters=TIER_FLOOR_CLUSTERS,
            min_std=0.0,
            rationale=("P33/P35 A13 fallback: identical in form to A12's ('>= 10 training "
                       "clusters with a defined, nonconstant interaction term'), activating "
                       "train_lt_2023..train_lt_2026 (ACTIVE_SET_RULE_PREREGISTRATION.json "
                       f"sha256 {ACTIVE_SET_RULE_PREREGISTRATION_SHA256}). Symmetric arm/null "
                       "application: the runner passes the treatment column [(cont_i - "
                       "cbar_F):dev_prev] as the sole candidate feature, so this rule is applied "
                       "to exactly the term the card names, with no DEEP/SHALLOW-tier gap the "
                       "generic mechanism cannot see (contrast A03's module docstring)."))
        rule_kwargs = {"rule_id": rule.rule_id, "min_nonzero_clusters": rule.min_nonzero_clusters,
                       "min_std": rule.min_std, "rationale": rule.rationale}
        prereg_kwargs = {
            "registered_at_utc": ("P35_FREEZE_TASK_CARDS freeze (2026, exact UTC not carried "
                                  "in the frozen SPEC.json bytes -- recorded honestly as an "
                                  "unestablished precision, not fabricated)"),
            "registered_by": ("P35_FREEZE_TASK_CARDS, A13 card, amendments_applied "
                              "('FOLDS F6: S7_TIER_SUPPORT_v1 registered via registry append'); "
                              "registry_append.payloads[experiment_id="
                              "S7_TIER_SUPPORT_v1__A13]"),
            "rule_spec_sha256": rule.spec_sha256,
            "results_visible_at_registration": False,
            "record_path": ("experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/"
                            f"SPEC.json (sha256 {P35_SPEC_SHA256}) #task_cards"
                            "[arm_id=A13_carryover_roster_continuity_moderator]"),
        }
        return (rule_kwargs, prereg_kwargs)


def make_arms(contract_schedule, history, lineup_membership, fold_ids, n_rows) -> list[ArmA13]:
    """Single-element arm -- one module instance, per RUNNER_INTERFACE.md section 1."""
    return [ArmA13(contract_schedule, history, lineup_membership, fold_ids, n_rows)]
