#!/usr/bin/env python3
"""A12_carryover_additive_decay.py -- P36 arm module for A12_carryover_additive_decay.

FROZEN CARD (verbatim binding source): experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/
SPEC.json, sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32 (verified at
implementation time), task_cards[].arm_id == "A12_carryover_additive_decay", carrying P33
PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072
d347d093) arm A12 by hash reference, amended exactly by the card's amendments_applied list, plus
shared_frozen_amendments (intercept_structure, construction_pins, franchise_continuity_receipt_pin).

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

MODEL (frozen, card-pinned):
    eta = intercept + log_exposure + [w(n_i) main | gap | depth | opp_depth]
          + beta1*dev_prev_i + beta2*w(n_i)*dev_prev_i
    w(n) = 1/(1 + n/5), h = 5 FIXED by source, never tunable (P33 hyperparameters.fixed.h)
    mu = exp(eta)
    free global intercept, arm AND null identically (P35 intercept_structure table: A12 in
    ARMS_WITH_FREE_GLOBAL_INTERCEPT).
    treatment = the pair {dev_prev, w(n):dev_prev}, 2 df, tested JOINTLY.

MATERIALISED COLUMN NAMES (this module's own naming; the card's own prose notation is preserved
in every docstring and record so the mapping is never silently lost):
    dev_prev      -> "dev_prev"          (card's dev_prev_i)
    w(n) main     -> "w_n"               (card's w(n_i))
    w(n):dev_prev -> "w_n:dev_prev"      (card's beta2 interaction; COLON-separated so the frozen
                                          P26 validator's `_factors()` splits it into ["w_n",
                                          "dev_prev"] and can verify the lower-order marginality
                                          closure (R6): "w_n" must -- and does -- appear in both
                                          designs' structural terms)
    gap           -> pace_gap                = team_pace_estimate - opp_pace_estimate
    depth         -> pace_evidence_depth     = trailing-window evidence count backing the team's
                                               own pace estimate, capped at WINDOW_K=10, 0 on
                                               league-prior fallback
    opp_depth     -> opp_pace_evidence_depth = same, for the opponent
(gap/depth/opp_depth column lineage is byte-identical to A07's -- both arms draw the SAME receipted
incumbent-path columns from experiments/player_program/possession_features.py.)

K0_MATCHED[A12] (frozen, card k0_matched_frozen / p26_k0_record):
    null: [log_exposure | w(n) main | gap | depth | opp_depth | intercept]  (comparison:
    term_removal). "the null owns every depth-indexed level degree of freedom (S6 direction 1)
    but does NOT hold dev_prev in any form (S6 direction 2)" -- MAE(K0[A12]) is NOT an incumbent
    benchmark; the null is deliberately STRONGER than the bare incumbent (same K0 K5 amendment
    A07 carries).
    treatment_terms: ["dev_prev", "w_n:dev_prev"], tested_parameters: [{beta1,beta2 joint,
    coefficient, null_value=0, meaning="no carryover information"}]
    claimed_signal_axes: the card's own prose ("prior-season deviation carryover decaying in
    same-season evidence") does not name any of the frozen K0_MATCHED_SCHEMA.json enum values
    directly; this module maps it onto the closest pair the schema accepts -- ["season_time",
    "support_size"] -- mirroring A07's identical two-axis choice for the identical
    COLDSTART_FALLBACK-family "decays in n_i" shape. Recorded, not silently substituted.

dev_prev_i (frozen, card features[0] + construction_pins.lagged_regulation_equivalent_pin, D9
struck in favour of the period-based formula, amendments_applied[2]/[3]):
    "prior-season mean regulation-equivalent offensive possessions per team-game minus
    prior-season league mean, strictly earlier" -- i.e. for a row in season s:
        dev_prev = mean_{team t's games in season s-1}(pace(j)) - mean_{ALL teams' games in
                   season s-1}(pace(j))
    where pace(j) := lagged realised_team_off_possessions_reg_equiv (construction_pins
    .lagged_regulation_equivalent_pin, the SAME frozen target construction A08/A09/A10/A11/A16
    use: n_off_poss * 40 / (40 + 5*max(0, max_period-4))), i.e. the REALIZED value of a COMPLETED
    prior-SEASON game, used only as a historical observation. "no-prior-season teams get
    dev_prev = 0 identically in arm and null" (P33 A12 formula, verbatim) -- an entire missing
    prior season (team absent from season s-1, or season s-1 itself absent from the supplied
    history, e.g. the 2021 season's own opener) zero-fills rather than raising, because D010
    ("a null does NOT license 'carryover useless at n=0'") forbids treating the cold-start row as
    anything OTHER than a defined zero. Because season s-1 is, by schedule construction, entirely
    chronologically prior to every row of season s, dev_prev carries no dependency on any
    same-season or future information: the "strictly earlier" qualifier in the card's prose is a
    season-level fact, not an additional within-season date filter.

n_i (frozen, card-pinned; shared K0 K6 / construction_pins.n_clock_pin -- SAME clock A07 uses):
    "team's completed same-season contract games strictly before the target date (team clock,
    within-cluster variation possible)" -- computed on the CONTRACT SCHEDULE (the 2,990 team-game
    rows of team_possession_prior_v1, INCLUDING the four universe-excluded 2021 opening-day
    games). "The universe-row clock is barred." A pure schedule fact (team_id, season, game_date
    only); no realised value of any game enters it. This module owns its OWN copy of the n_i
    construction (mirrored from, never imported from, arms/A07 -- standing rule 2: this unit
    touches nothing outside arms/A12/).

FOLD-LOCAL FALLBACK (frozen, card p26_k0_record.fold_local_fallback / registry_append
S7_TIER_SUPPORT_v1__A12): "treatment enters a fold iff >= 10 training clusters carry
|dev_prev| > 0; structural deactivation of train_lt_2022; arm AND null identically." Two
DISTINCT mechanisms, both implemented:
  (a) an S7 ActiveSetRule (min_nonzero_clusters=10, min_std=0.0) on the terms "dev_prev" and
      "w_n:dev_prev", registered via `p27_rule()` -- the generic P27 mechanism honestly expresses
      this because both treatment columns ARE declared design columns (unlike A03's DEEP-tier
      gap, dev_prev's own nonzero-support IS the frozen trigger, with nothing implicit to add);
  (b) train_lt_2022 (2021-only training set, no archived prior season -- a SCHEDULE FACT, not a
      measured degeneracy) is STRUCTURALLY deactivated via the optional `structurally_deactivated_
      folds()` hook (RUNNER_INTERFACE.md section 2a), identically for arm and null.

MULTIPLICITY (card `multiplicity`, P35 dual_holm_compositions_pinned): primary
COLDSTART_FALLBACK (m=5, ordering over 4, A14 fixed slot); alternate timeseries_shrinkage + A12 =
m=11; stricter governs. Not enforced by this construction module (a P37/promotion-stage concern);
recorded here so the card's full obligation is visible from the implementation alone.

KILL CONDITIONS (frozen, card kill_conditions_frozen, verbatim): "joint treatment adds no
out-of-fold improvement on the preregistered n <= 5 stratum; all-rows-only improvement; beta2
sign contradicting decay; a null does NOT license 'carryover useless at n = 0' (D010)." The first
three are implemented below as pure decision functions (`evaluate_kill_conditions`); D010 is NOT
a decidable rule -- it is a standing prohibition on a downstream INTERPRETIVE claim ("carryover is
useless when n=0"), not a computable trigger, and is carried here as a documented, non-decision
constant (`D010_NON_LICENSE`) rather than silently folded into a numeric test.

AMBIGUITIES DISCLOSED, NOT RESOLVED SILENTLY (standing rule 1 -- frozen bytes govern over prose;
flagged for P37 rather than adjudicated here):
  1. n_i's P22 lag kind. Identical to A07's disclosed reading: RUNNER_INTERFACE.md names
     SAME_GAME/PRIOR_GAME/SCHEDULE/DERIVED_NO_JOIN but does not name which kind a same-season
     COMPLETED-GAME COUNT should carry. This module declares n_i's derived column ("w_n") kind
     SCHEDULE, for the identical reasons A07 states (a pure pre-tipoff schedule fact; PRIOR_GAME's
     shift-based re-derivation machinery is built for a per-entity VALUE lag, not a cumulative
     count or a function of one).
  2. beta2's "contradicts decay" sign convention. The card names the rule but not the arithmetic
     sign relation. This module's reading (documented in full at `beta2_contradicts_decay_kill`):
     because the FITTED coefficient on dev_prev is (beta1 + beta2*w(n_i)), and w(n_i) is LARGEST
     at season start (n_i=0, w=1) and decays toward 0 as evidence accumulates, "decay" predicts
     the carryover effect is STRONGEST at season start and fades -- i.e. beta2 REINFORCES beta1's
     sign (|beta1+beta2| > |beta1|). A beta2 with the OPPOSITE sign of beta1 would instead predict
     the effect is weakest at season start, contradicting the decay claim. This reading is stated,
     not hidden, and is independently testable in isolation from any fit.
  3. dev_prev's season-history source. The frozen construction_pins name the VALUE formula
     (period-based regulation-equivalent rescale) but not which artifact enumerates "every
     team-game with a realised outcome, across every season" -- that data does not live in the
     2,982-row candidate universe alone (which is restricted to `pace_resolved` rows) nor in the
     2,990-row team_possession_prior_v1 schedule alone (which carries no realised outcome column).
     This module therefore takes a `history` argument at construction (mirroring A08's `history`
     parameter for the SAME shared construction_pins.lagged_regulation_equivalent_pin lineage):
     a frame carrying team_id/season/game_date and one realised-outcome column, assembled by
     whichever P38-time caller has access to the frozen possessions artifact across every season.
     This module performs no I/O and reads no real data itself.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ frozen pins, restated here so
# this module has no runtime dependency on the runner/ directory (arms/A12 never imports from or
# writes to runner/; these constants are copied VALUES, not references, and are asserted equal to
# the runner's own copies in TESTS.py so drift is caught rather than silently tolerated).
ARM_ID = "A12_carryover_additive_decay"
OFFSET_COL = "log_exposure"
TARGET_LABEL = "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"
INTERCEPT_COL = "intercept"

GAP_COL = "pace_gap"
DEPTH_COL = "pace_evidence_depth"
OPP_DEPTH_COL = "opp_pace_evidence_depth"
W_N_COL = "w_n"                                    # card's w(n_i) main term
DEV_PREV_COL = "dev_prev"                          # card's dev_prev_i
INTERACTION_COL = "w_n:dev_prev"                   # card's beta2*w(n_i)*dev_prev_i

H = 5.0                                            # FIXED by source; never tunable (P33 pin)
ACTIVE_SET_FLOOR_CLUSTERS = 10                      # S7_TIER_SUPPORT_v1 numeric trigger
DEACTIVATED_FOLD_ID = "train_lt_2022"               # structural: 2021-only, no archived prior season
S7_RULE_ID = "S7_TIER_SUPPORT_v1"
ACTIVE_SET_RULE_PREREGISTRATION_SHA256 = (
    "327fa8ec9fb54e3635ae70b540573b4121c6136fc5034cbdb689cabbe2986db7")
COLDSTART_STRATUM_N_MAX = 5                         # "n <= 5" thin-evidence stratum, card-pinned
P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"

D010_NON_LICENSE = (
    "D010: a null result on this arm does NOT license the claim 'carryover is useless at n=0' -- "
    "dev_prev is defined and evaluated on the thin-evidence (n<=5) stratum, never at n=0 itself "
    "as a claim boundary. Not a decidable rule; recorded as a standing interpretive constraint.")

REQUIRED_UNIVERSE_COLS = ("team_id", "season", "game_date", GAP_COL, DEPTH_COL, OPP_DEPTH_COL)
REQUIRED_HISTORY_COLS = ("team_id", "season", "game_date")


class A12ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No design is returned."""


# --------------------------------------------------------------------------------------------- #
# n_i: strictly-earlier same-season CONTRACT-SCHEDULE completed-game count (shared n_clock_pin,
# mirrored -- not imported -- from arms/A07; see module docstring ambiguity note 1).
# --------------------------------------------------------------------------------------------- #

def compute_n_i(history: pd.DataFrame, team_id: np.ndarray, season: np.ndarray,
                game_date: np.ndarray) -> np.ndarray:
    """n_i for each row: count of the team's CONTRACT-SCHEDULE same-season games with
    game_date STRICTLY EARLIER than the row's own game_date.

    Deterministic, order-independent. Unique dates per (team_id, season) group so a hypothetical
    same-date duplicate never counts as prior to itself or its own date's sibling row.
    """
    missing = [c for c in REQUIRED_HISTORY_COLS if c not in history.columns]
    if missing:
        raise A12ConstructionFailure(
            f"history is missing required columns {missing}; n_i (n_clock_pin) cannot be "
            f"computed on the contract-schedule clock")

    sched = history[list(REQUIRED_HISTORY_COLS)].copy()
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
        raise A12ConstructionFailure(
            f"{unresolved} universe row(s) have a (team_id, season) pair absent from the "
            f"supplied history; n_i is undefined for them and the frozen n_clock_pin forbids "
            f"falling back to the universe-row clock")
    return out


def w_of_n(n_i: np.ndarray) -> np.ndarray:
    """w(n) = 1 / (1 + n/H), H = 5 FIXED by source (P33 hyperparameters.fixed.h)."""
    return 1.0 / (1.0 + np.asarray(n_i, dtype=float) / H)


# --------------------------------------------------------------------------------------------- #
# dev_prev: prior-SEASON team deviation from the prior-season league mean (construction_pins
# .lagged_regulation_equivalent_pin; the period-based reg-equiv formula, D9 duration_sec reading
# struck). "no-prior-season teams get dev_prev = 0 identically in arm and null."
# --------------------------------------------------------------------------------------------- #

def build_prior_season_index(history: pd.DataFrame, pace_col: str) -> dict:
    """Per-(team, season) mean and per-season LEAGUE mean of the realised pace column.

    `history` must carry team_id, season and `pace_col` (the realised, LAGGED-USE-ONLY, period-
    based regulation-equivalent value of a COMPLETED historical team-game -- see module docstring
    ambiguity note 3). Every value here is a season-level aggregate; a season is complete before
    any later season begins, so nothing here can depend on any same- or later-season row.
    """
    missing = [c for c in ("team_id", "season", pace_col) if c not in history.columns]
    if missing:
        raise A12ConstructionFailure(
            f"history is missing required columns {missing}; dev_prev "
            f"(lagged_regulation_equivalent_pin) cannot be computed")
    h = history[["team_id", "season", pace_col]].copy()
    h[pace_col] = pd.to_numeric(h[pace_col], errors="coerce")
    team_season_mean = h.groupby(["team_id", "season"])[pace_col].mean()
    league_season_mean = h.groupby("season")[pace_col].mean()
    return {"team_season_mean": team_season_mean, "league_season_mean": league_season_mean}


def compute_dev_prev(history: pd.DataFrame, team_id: np.ndarray, season: np.ndarray,
                     pace_col: str = "pace") -> np.ndarray:
    """dev_prev_i = team's PRIOR-season mean(pace) - league's PRIOR-season mean(pace).

    A team absent from season-1, or a season-1 wholly absent from `history` (the schedule fact
    that anchors train_lt_2022's structural deactivation), zero-fills rather than raising: "no-
    prior-season teams get dev_prev = 0" is the card's own construction, not an implementation
    convenience (D010 forbids treating the cold-start row as anything other than a defined zero).
    """
    idx = build_prior_season_index(history, pace_col)
    team_id = np.asarray(team_id)
    season = np.asarray(season, dtype=int)
    prior_season = season - 1

    tsm = idx["team_season_mean"]
    lsm = idx["league_season_mean"]
    out = np.zeros(len(team_id), dtype=float)
    for i in range(len(team_id)):
        key = (team_id[i], int(prior_season[i]))
        if key in tsm.index and int(prior_season[i]) in lsm.index:
            out[i] = float(tsm.loc[key]) - float(lsm.loc[int(prior_season[i])])
        # else: no-prior-season row -> dev_prev = 0.0 (card, verbatim; D010)
    return out


# --------------------------------------------------------------------------------------------- #
# kill-condition hooks (frozen card kill_conditions_frozen) -- PURE functions of synthetic /
# fold-summary inputs. They decide nothing about real performance; they exist so a downstream
# fitting node can call one deterministic decision function per rule rather than re-deriving the
# card's prose per implementation.
# --------------------------------------------------------------------------------------------- #

def stratum_no_improvement_kill(delta_mae_n_le_5: float) -> bool:
    """Kill iff the joint treatment adds NO out-of-fold improvement on the preregistered n<=5
    stratum (card: "joint treatment adds no out-of-fold improvement on the preregistered n <= 5
    stratum"). delta_mae is null_MAE - arm_MAE on that stratum; <= 0 means no improvement."""
    return float(delta_mae_n_le_5) <= 0.0


def concentration_kill(improvement_share_n_le_5: float, *, threshold: float = 0.5) -> bool:
    """Kill iff any all-rows improvement is NOT concentrated on the n<=5 stratum (card:
    "all-rows-only improvement" kills the arm AS A COLD-START CLAIM). Majority-share convention
    (>= 0.5), mirroring the identical A07 reading of the identical COLDSTART_FALLBACK-family
    prose; `threshold` is exposed but never varied per call in this program."""
    return float(improvement_share_n_le_5) < float(threshold)


def beta2_contradicts_decay_kill(beta1_signs: Sequence[int], beta2_signs: Sequence[int]) -> bool:
    """Kill iff beta2's sign contradicts the decay prediction in ANY evaluable fold (card: "beta2
    sign contradicting decay"). Reading (module docstring ambiguity note 2): the fitted
    coefficient on dev_prev is (beta1 + beta2*w(n_i)); decay predicts the carryover effect is
    STRONGEST at season start (w(n_i) largest) and fades, i.e. beta2 must REINFORCE beta1 (same
    sign). Zero-signed folds (a coefficient estimated at exactly 0) are excluded from the
    comparison -- a true zero neither confirms nor contradicts the direction."""
    if len(beta1_signs) != len(beta2_signs):
        raise ValueError("beta1_signs and beta2_signs must be the same length, one per fold")
    for b1, b2 in zip(beta1_signs, beta2_signs):
        s1, s2 = int(np.sign(b1)), int(np.sign(b2))
        if s1 != 0 and s2 != 0 and s1 != s2:
            return True
    return False


def evaluate_kill_conditions(*, delta_mae_n_le_5: float, improvement_share_n_le_5: float,
                             beta1_signs: Sequence[int], beta2_signs: Sequence[int]) -> dict:
    """One decidable verdict per frozen kill rule (excluding D010, a non-decidable standing
    constraint -- see module docstring), plus the OR-combined arm verdict."""
    stratum = stratum_no_improvement_kill(delta_mae_n_le_5)
    conc = concentration_kill(improvement_share_n_le_5)
    sign = beta2_contradicts_decay_kill(beta1_signs, beta2_signs)
    return {
        "stratum_n_le_5_no_improvement": stratum,
        "improvement_not_concentrated_on_coldstart_stratum": conc,
        "beta2_sign_contradicts_decay": sign,
        "d010_non_license": D010_NON_LICENSE,
        "killed": bool(stratum or conc or sign),
    }


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
                               "table: A12 in ARMS_WITH_FREE_GLOBAL_INTERCEPT)",
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
                         "receipted incumbent-path feature frame (possession_features."
                         f"challenger_input, same lineage as A07); {W_N_COL} = 1/(1+n_i/{H:.0f}), "
                         f"n_i computed on the contract-schedule clock (n_clock_pin); "
                         f"{DEV_PREV_COL} = prior-season team mean(pace) - prior-season league "
                         "mean(pace), period-based reg-equiv rescale (lagged_regulation_"
                         f"equivalent_pin); {INTERACTION_COL} = {W_N_COL} * {DEV_PREV_COL}"),
        "missing_value_handling": (f"none beyond the card's own zero-fills: {DEV_PREV_COL} := 0 "
                                   "for a no-prior-season team-season (D010); n_i construction "
                                   "fails closed (A12ConstructionFailure) rather than imputing on "
                                   "any (team_id, season) absent from the supplied history"),
        "companion_components": "none",
        "fallback_rules": (f"{S7_RULE_ID}: treatment enters a fold iff >= "
                          f"{ACTIVE_SET_FLOOR_CLUSTERS} training clusters carry |{DEV_PREV_COL}| "
                          f"> 0; {DEACTIVATED_FOLD_ID} structurally deactivated (schedule fact: "
                          "2021 has no archived prior season), identically in arm and null"),
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the 2,982-row resolved possession universe (1,491 game clusters); "
                              "n_i and dev_prev alone are computed on cross-season history",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


# --------------------------------------------------------------------------------------------- #
# the arm module
# --------------------------------------------------------------------------------------------- #

class A12CarryoverAdditiveDecay:
    """P36 RUNNER_INTERFACE-conformant module for A12_carryover_additive_decay.

    Constructed with `history`: a frame that is a SUPERSET of the games appearing in any
    `universe` this module will be handed, carrying team_id/season/game_date (for n_i, the
    contract-schedule clock) AND a realised, lagged-use-only pace column (for dev_prev, the
    prior-season aggregate) -- see module docstring ambiguity note 3 for why this is one frame
    rather than two.
    """

    arm_id = ARM_ID

    def __init__(self, history: pd.DataFrame, fold_ids: Sequence[str] = (),
                n_rows: int | None = None, pace_col: str = "pace"):
        missing = [c for c in REQUIRED_HISTORY_COLS if c not in history.columns]
        if missing:
            raise A12ConstructionFailure(f"history missing required columns {missing}")
        if pace_col not in history.columns:
            raise A12ConstructionFailure(
                f"history missing the realised pace column '{pace_col}' dev_prev requires")
        self._history = history.reset_index(drop=True)
        self._pace_col = pace_col
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows) if n_rows is not None else int(len(history))

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        return {}                      # h=5 FIXED by source; no grid (P33 hyperparameters.fixed)

    def element_id(self) -> str:
        return "A12_carryover_additive_decay__single"

    def uses_global_intercept(self) -> bool:
        return True                    # P35 intercept_structure: A12 in ARMS_WITH_FREE_GLOBAL_...

    def structurally_deactivated_folds(self) -> list:
        return [DEACTIVATED_FOLD_ID]   # train_lt_2022: schedule fact, arm AND null identically

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in universe.columns]
        if missing:
            raise A12ConstructionFailure(
                f"universe is missing required columns {missing} (receipted incumbent-path "
                f"gap/depth/opp_depth columns, or team_id/season/game_date identity columns)")

        team_id = universe["team_id"].to_numpy()
        season = universe["season"].to_numpy()
        game_date = universe["game_date"].to_numpy()

        n_i = compute_n_i(self._history, team_id, season, game_date)
        w_n = w_of_n(n_i)
        dev_prev = compute_dev_prev(self._history, team_id, season, pace_col=self._pace_col)
        interaction = w_n * dev_prev

        columns = {
            W_N_COL: w_n,
            GAP_COL: universe[GAP_COL].to_numpy(dtype=float),
            DEPTH_COL: universe[DEPTH_COL].to_numpy(dtype=float),
            OPP_DEPTH_COL: universe[OPP_DEPTH_COL].to_numpy(dtype=float),
            INTERCEPT_COL: np.ones(len(universe), dtype=float),
            DEV_PREV_COL: dev_prev,
            INTERACTION_COL: interaction,
        }
        nuisance = [W_N_COL, GAP_COL, DEPTH_COL, OPP_DEPTH_COL, INTERCEPT_COL]
        treatment = [DEV_PREV_COL, INTERACTION_COL]
        return {
            "treatment_cols": treatment,
            "nuisance_cols": nuisance,
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": list(nuisance),
                                  "comparison": "term_removal"},
            "indicator_cols": [],       # w_n/gap/depth/opp_depth/dev_prev/interaction are all
                                       # continuous; intercept is structural, never an indicator
            "columns": columns,
        }

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        train_digest = _digest("A12_training_rows", self._fold_ids, self._n_rows)
        eval_digest = _digest("A12_evaluation_rows", self._fold_ids, self._n_rows)
        side = _sidespec(self._fold_ids, train_digest, eval_digest)
        structural = [W_N_COL, GAP_COL, DEPTH_COL, OPP_DEPTH_COL, INTERCEPT_COL]
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "a prior-season level deviation (dev_prev) enters additively, with a "
                            "weight decaying in current-season evidence (w(n_i)); the null owns "
                            "every depth-indexed level degree of freedom but holds no form of "
                            "dev_prev (S6 direction 2)",
                "treatment_terms": [DEV_PREV_COL, INTERACTION_COL],
                "tested_parameters": [{"name": "beta1, beta2 joint", "role": "coefficient",
                                       "null_value": 0,
                                       "null_value_meaning": "no carryover information"}],
                "claimed_signal_axes": ["season_time", "support_size"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        f"removing {DEV_PREV_COL}/{INTERACTION_COL} leaves only "
                        f"{W_N_COL}/{GAP_COL}/{DEPTH_COL}/{OPP_DEPTH_COL}/intercept in the null; "
                        "none of those carries any prior-SEASON deviation information, so the "
                        "claimed carryover mechanism is destroyed by construction")}},
            "invariants": {
                "rows": train_digest,
                "target": TARGET_LABEL,
                "folds": list(self._fold_ids),
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": list(structural),
                "lower_order_structural_terms": list(structural),
            },
            "arm_spec": {
                "name": "A12_carryover_additive_decay", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [DEV_PREV_COL, INTERACTION_COL],
                "structural_terms": list(structural),
                "declaration_routing": {
                    DEV_PREV_COL: "substantive_features", INTERACTION_COL: "substantive_features",
                    W_N_COL: "preprocessing", GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "A12_carryover_additive_decay__K0_MATCHED", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": list(structural),
                "declaration_routing": {
                    W_N_COL: "preprocessing", GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": dict(side)},
            "fold_local_fallback": {
                "required": True,
                "trigger": (f"{S7_RULE_ID}: treatment enters a fold iff >= "
                          f"{ACTIVE_SET_FLOOR_CLUSTERS} training clusters carry "
                          f"|{DEV_PREV_COL}| > 0"),
                "numeric_threshold": ACTIVE_SET_FLOOR_CLUSTERS,
                "action": "drop_term_for_fold",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature arm: eligible for a feature_value verdict "
                                    "ONLY against K0_MATCHED[A12]; K0_FLAT carries no promotion "
                                    "value whatsoever (k0_flat_role diagnostic_only)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "K0 K5 / S6 direction 1 (P35 amendment, shared with A07): the null's terms are "
                "'receipted incumbent-path features granted to the null'; MAE(K0[A12]) is NOT an "
                "incumbent benchmark.",
                "n_clock_pin: n_i is counted on the CONTRACT SCHEDULE (2,990 rows, including the "
                "four universe-excluded 2021 opening-day games); the universe-row clock is barred.",
                "lagged_regulation_equivalent_pin: dev_prev uses the period-based reg-equiv "
                "formula (D9 duration_sec reading struck for A12).",
                "S7_TIER_SUPPORT_v1__A12 (registry_append): >= 10 training clusters with "
                "|dev_prev| > 0; train_lt_2022 structurally deactivated (schedule fact).",
                "MULT B-3: dual-Holm alternate composition pinned -- primary COLDSTART_FALLBACK "
                "(m=5, ordering over 4), alternate timeseries_shrinkage + A12 = m=11, "
                "hold-others-at-primary, stricter governs.",
                "A12->A13 fixed sequence: A13's result is confirmatory only if A12's joint "
                "treatment rejects under the stricter of its two dual-family Holm corrections; "
                "out of scope for this feature-construction module.",
            ],
        }

    # ---- guards ---------------------------------------------------------------------
    def lag_specs(self) -> dict:
        return {
            GAP_COL: {"column": GAP_COL, "kind": "DERIVED_NO_JOIN",
                      "source_artifact_id": "team_possession_prior/1",
                      "entity_keys": ("game_id", "team_id"),
                      "rationale": "difference of two prior-games-only trailing-window pace "
                                   "means (team_pace_estimate - opp_pace_estimate); byte-identical "
                                   "lineage to A07's gap column"},
            DEPTH_COL: {"column": DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                       "source_artifact_id": "team_possession_prior/1",
                       "entity_keys": ("game_id", "team_id"),
                       "rationale": "count of prior games backing the team's own pace estimate, "
                                    "capped at WINDOW_K=10"},
            OPP_DEPTH_COL: {"column": OPP_DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "team_possession_prior/1",
                           "entity_keys": ("game_id", "team_id"),
                           "rationale": "same evidence-depth count, for the opponent"},
            W_N_COL: {"column": W_N_COL, "kind": "SCHEDULE",
                     "source_artifact_id": "team_possession_prior/1",
                     "entity_keys": ("team_id", "season"), "order_column": "game_date",
                     "rationale": (
                         "w(n_i) = 1/(1+n_i/5) is a deterministic function of n_i = count of the "
                         "offense team's completed same-season CONTRACT-SCHEDULE games strictly "
                         "before game_date(g) (n_clock_pin); a pure schedule fact fixed before "
                         "tipoff, with no dependency on any realised in-game quantity. Declared "
                         "SCHEDULE for the identical reason A07's treatment column is (see module "
                         "docstring ambiguity note 1): PRIOR_GAME's shift-based re-derivation "
                         "verifies a per-entity VALUE lag, not a cumulative count or a function of "
                         "one.")},
            DEV_PREV_COL: {"column": DEV_PREV_COL, "kind": "DERIVED_NO_JOIN",
                          "source_artifact_id": "team_possession_prior_v1_prior_season_history",
                          "entity_keys": ("team_id", "season"),
                          "rationale": (
                              "team's PRIOR-season mean realised regulation-equivalent possessions "
                              "minus the PRIOR-season league mean (lagged_regulation_equivalent_"
                              "pin); an aggregate over an entire strictly-earlier season, never "
                              "the target row's own season or game. Declared DERIVED_NO_JOIN "
                              "rather than PRIOR_GAME for the same reason A08's d_t/L_t are: the "
                              "P22 shift-based re-derivation machinery verifies a single "
                              "shift(n_back), not a season-level aggregate window.")},
            INTERACTION_COL: {"column": INTERACTION_COL, "kind": "DERIVED_NO_JOIN",
                             "source_artifact_id": "team_possession_prior_v1_prior_season_history",
                             "rationale": f"product of two already-declared columns in this same "
                                         f"audited frame ({W_N_COL} * {DEV_PREV_COL}); no "
                                         "additional join or lag beyond what those two columns "
                                         "already carry"},
            # INTERCEPT_COL carries no lag_spec: it is a structural constant, not a declared
            # feature (mirrors A07's / the shared runner's ToyArmWithIntercept convention).
        }

    def lag_sources(self) -> dict:
        return {"history": self._history}

    def preregistered_contrasts(self):
        return None            # A12 registers no P25 contrast column (that is A02's obligation)

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 p23_franchise_continuity_precondition names A08,A09,A10,A11,A12,A13,A14,A16,A17,
        # A19,A21,A22,A24 -- A12 IS in that list (dev_prev is a cross-season history feature).
        return True

    def p23_receipts(self) -> list:
        return [{
            "team_cities_sha256": "10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d",
            "note": "A12 requires the franchise-continuity receipt per P33 precondition / P35 "
                   "shared_frozen_amendments.franchise_continuity_receipt_pin: dev_prev spans a "
                   "season boundary and is therefore a cross-season history feature",
        }]

    def p27_rule(self):
        """S7_TIER_SUPPORT_v1__A12 (registry_append, rule_file_sha256 identical to A03's): >= 10
        training clusters carrying |dev_prev| > 0. Unlike A03's DEEP-tier gap, both treatment
        columns (dev_prev, w_n:dev_prev) are declared design columns, so the generic P27
        ActiveSetRule mechanism expresses the card's rule fully -- no task-specific wrapper gap
        exists here (contrast the module docstring's A03 citation)."""
        rule_kwargs = {
            "rule_id": S7_RULE_ID,
            "min_nonzero_clusters": ACTIVE_SET_FLOOR_CLUSTERS,
            "min_std": 0.0,
            "rationale": (
                "P33/P35 A12 fallback (registry_append S7_TIER_SUPPORT_v1__A12): treatment enters "
                f"a fold iff >= {ACTIVE_SET_FLOOR_CLUSTERS} training clusters carry "
                f"|{DEV_PREV_COL}| > 0, identically arm and null "
                f"(ACTIVE_SET_RULE_PREREGISTRATION.json sha256 "
                f"{ACTIVE_SET_RULE_PREREGISTRATION_SHA256})."),
        }
        prereg_kwargs = {
            "registered_at_utc": ("P35_FREEZE_TASK_CARDS freeze (2026, exact UTC not carried in "
                                  "the frozen SPEC.json bytes -- recorded honestly as an "
                                  "unestablished precision, not fabricated)"),
            "registered_by": ("P35_FREEZE_TASK_CARDS registry_append payload "
                              "'S7_TIER_SUPPORT_v1__A12'"),
            "rule_spec_sha256": _rule_spec_sha256(rule_kwargs),
            "results_visible_at_registration": False,
            "record_path": ("experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/"
                            f"SPEC.json (sha256 {P35_SPEC_SHA256}) #task_cards"
                            "[arm_id=A12_carryover_additive_decay] + #registry_append.payloads"
                            "[experiment_id=S7_TIER_SUPPORT_v1__A12]"),
        }
        return (rule_kwargs, prereg_kwargs)


def _rule_spec_sha256(rule_kwargs: dict) -> str:
    """Recompute the frozen P27 ActiveSetRule's own spec digest WITHOUT importing fold_estimability
    _guard.py at module load time (arms/A12 imports guard modules lazily, only inside tests, to
    keep this module import-independent of the runner/ and P27 directories at construction time).
    Mirrors `fold_estimability_guard.ActiveSetRule.spec_sha256` exactly; TESTS.py asserts byte
    equality against the frozen module's own computation so any drift is a loud test failure.
    """
    import hashlib
    import json
    spec = {"rule_id": rule_kwargs["rule_id"],
            "min_nonzero_clusters": int(rule_kwargs["min_nonzero_clusters"]),
            "min_std": float(rule_kwargs["min_std"]),
            "rationale": rule_kwargs["rationale"],
            "conditions_on": "SupportSummary (training-fold counts only)",
            "applied_to": "candidate AND null, identically, once per fold"}
    canon = json.dumps(spec, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()
