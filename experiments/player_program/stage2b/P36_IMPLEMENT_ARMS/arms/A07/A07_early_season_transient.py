#!/usr/bin/env python3
"""A07_early_season_transient.py -- P36 arm module for A07_early_season_transient.

FROZEN CARD (verbatim binding source): experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/
SPEC.json, sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32 (verified at
implementation time), task_cards[].arm_id == "A07_early_season_transient", carrying P33
PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072
d347d093) arm A07 by hash reference, amended exactly by the card's amendments_applied list.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

MODEL (frozen, card-pinned):
    eta = intercept + log_exposure + b1*gap + b2*depth + b3*opp_depth + delta * exp(-n_i/5)
    mu  = exp(eta)
    free global intercept, arm AND null identically (P35 intercept_structure table: A07 in
    ARMS_WITH_FREE_GLOBAL_INTERCEPT).

TREATMENT: exp(-n_i/5), tau = 5 FIXED by source, never tunable (P33 hyperparameters.fixed.tau=5).

COLUMN LINEAGE (frozen, byte-exact names from the receipted incumbent path,
experiments/player_program/possession_features.py):
    gap      -> pace_gap                = team_pace_estimate - opp_pace_estimate
    depth    -> pace_evidence_depth     = trailing-window evidence count backing the team's own
                                          pace estimate, capped at WINDOW_K=10, 0 on league-prior
                                          fallback
    opp_depth-> opp_pace_evidence_depth = same, for the opponent
These three plus the explicit intercept are RECEIPTED INCUMBENT-PATH FEATURES GRANTED TO THE NULL
(K0 K5, S6 direction 1): the null [log_exposure | gap | depth | opp_depth | intercept] is
deliberately STRONGER than the incumbent, and MAE(K0[A07]) is NOT an incumbent benchmark.

n_i (frozen, card-pinned; K0 K6 / shared construction_pins.n_clock_pin):
    "team's completed same-season contract games strictly before the target date (team clock,
    within-cluster variation possible)" -- computed on the CONTRACT SCHEDULE (the 2,990 team-game
    rows of team_possession_prior_v1, INCLUDING the four universe-excluded 2021 opening-day
    games). "The universe-row clock is barred." This is why this module requires a separate
    ``contract_schedule`` frame at construction, distinct from and a strict superset of the
    ``universe`` argument ``build_design`` receives -- using ``universe`` alone to count n_i would
    silently drop the four excluded 2021 rows and violate the pin. n_i is a pure schedule fact
    (team_id, season, game_date only); no realised value of any game enters it, so it carries no
    dependency on the prohibited current-game-duration basis.

K0_MATCHED[A07] (frozen, card k0_matched_frozen):
    null: [log_exposure | gap | depth | opp_depth | intercept]   (comparison: term_removal)
    treatment_terms: ["exp(-n_i/5)"], tested_parameters: [{delta, coefficient, null_value=0}]

FOLD-LOCAL FALLBACK (frozen, card p26_k0_record.fold_local_fallback):
    S7 condition-number check of exp(-n_i/5) vs depth; arm/fold UNEVALUABLE (refuse_to_score_fold)
    on near-affinity (R2 >= 0.998001 OR |spearman| >= 0.999); measured pre-fit max 0.958, below
    threshold (P33 measurement, carried, NOT re-measured here: no real fold is touched by this
    node). Retirement rule: unevaluable in >= 2 folds retires the hypothesis.

KILL CONDITIONS (frozen, card kill_conditions_frozen): delta interval covers 0 in every evaluable
fold; improvement concentrating outside the n <= 5 stratum; sign FLIP across folds.

AMBIGUITY DISCLOSED, NOT RESOLVED SILENTLY: the frozen RUNNER_INTERFACE.md names four P22 LagSpec
kinds (SAME_GAME, PRIOR_GAME, SCHEDULE, DERIVED_NO_JOIN) but does not name which kind a
same-season COMPLETED-GAME COUNT (n_i) should carry -- PRIOR_GAME's re-derivation machinery is
built for a per-entity VALUE shift, not a cumulative count, and would not literally verify a count
via shift(n_back). This module declares n_i's lag kind SCHEDULE ("a fact fixed before tipoff ...
skips lag re-derivation because there is no lag to re-derive"), which is the closest frozen fit:
n_i depends on nothing but the schedule (team_id, season, game_date) and completedness, never on
any realised in-game quantity. This is an IMPLEMENTATION labelling choice with no effect on the
scientific content of the card (it does not change gap/depth/opp_depth/delta or any preregistered
number); it is recorded here and in REPORT.md for P37 to affirm or overrule, per standing rule 1
(frozen bytes govern over prose) -- nothing frozen names the correct kind, so nothing is silently
overridden.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ frozen pins, restated here so
# this module has no runtime dependency on the runner/ directory (arms/A07 never imports from or
# writes to runner/; these constants are copied VALUES, not references, and are asserted equal to
# the runner's own copies in TESTS.py so drift is caught rather than silently tolerated).
ARM_ID = "A07_early_season_transient"
OFFSET_COL = "log_exposure"
TARGET_LABEL = "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"
INTERCEPT_COL = "intercept"

GAP_COL = "pace_gap"
DEPTH_COL = "pace_evidence_depth"
OPP_DEPTH_COL = "opp_pace_evidence_depth"
TREATMENT_COL = "early_season_transient"          # exp(-n_i/5)

TAU = 5.0                                          # FIXED by source; never tunable (P33 pin)
NEAR_AFFINE_R2 = 0.998001                          # frozen S7 near-affinity threshold (arm/fold)
NEAR_AFFINE_SPEARMAN = 0.999
COLDSTART_STRATUM_N_MAX = 5                        # "n <= 5" cold-start stratum, card-pinned

REQUIRED_UNIVERSE_COLS = ("team_id", "season", "game_date", GAP_COL, DEPTH_COL, OPP_DEPTH_COL)
REQUIRED_SCHEDULE_COLS = ("team_id", "season", "game_date")


class A07ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No design is returned."""


# --------------------------------------------------------------------------------------------- #
# n_i: strictly-earlier same-season CONTRACT-SCHEDULE completed-game count (frozen n_clock_pin)
# --------------------------------------------------------------------------------------------- #

def compute_n_i(contract_schedule: pd.DataFrame, team_id: np.ndarray, season: np.ndarray,
                game_date: np.ndarray) -> np.ndarray:
    """n_i for each row: count of the team's CONTRACT-SCHEDULE same-season games with
    game_date STRICTLY earlier than the row's own game_date.

    Deterministic, order-independent (the output does not depend on row order in either
    ``contract_schedule`` or the query arrays). Uses UNIQUE dates per (team_id, season) group so a
    hypothetical same-date duplicate never counts as prior to itself or to its own date's sibling
    row -- "strictly before" excludes ties by construction, not by tie-break convention.
    """
    missing = [c for c in REQUIRED_SCHEDULE_COLS if c not in contract_schedule.columns]
    if missing:
        raise A07ConstructionFailure(
            f"contract_schedule is missing required columns {missing}; n_i (K0 K6 / n_clock_pin) "
            f"cannot be computed on the contract-schedule clock")

    sched = contract_schedule[list(REQUIRED_SCHEDULE_COLS)].copy()
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
        # side='left': count of schedule dates strictly less than each queried date
        out[mask] = np.searchsorted(dates, gd[mask].to_numpy(), side="left").astype(float)

    unresolved = int((out < 0).sum())
    if unresolved:
        raise A07ConstructionFailure(
            f"{unresolved} universe row(s) have a (team_id, season) pair absent from the supplied "
            f"contract_schedule; n_i is undefined for them and the frozen n_clock_pin forbids "
            f"falling back to the universe-row clock")
    return out


def early_season_transient(n_i: np.ndarray) -> np.ndarray:
    """exp(-n_i / tau), tau = 5 FIXED by source (P33 hyperparameters.fixed.tau)."""
    return np.exp(-np.asarray(n_i, dtype=float) / TAU)


# --------------------------------------------------------------------------------------------- #
# kill-condition hooks (frozen card kill_conditions_frozen) -- PURE functions of synthetic /
# fold-summary inputs. They decide nothing about real performance; they exist so a downstream
# fitting node can call one deterministic decision function per rule rather than re-deriving the
# card's prose per implementation.
# --------------------------------------------------------------------------------------------- #

def delta_ci_kill(fold_intervals: Sequence[tuple[float, float]]) -> bool:
    """Kill iff the delta 95% training-cluster bootstrap interval covers 0 in EVERY evaluable
    fold (card: "delta interval covers 0 in every evaluable fold"). No evaluable folds -> the
    condition cannot fire (nothing to evaluate); this is decided FALSE, not KILLED, and the
    caller is responsible for recording zero-evaluable-folds as its own separate finding.
    """
    if not fold_intervals:
        return False
    return all(lo <= 0.0 <= hi for lo, hi in fold_intervals)


def sign_flip_kill(fold_signs: Sequence[int]) -> bool:
    """Kill iff delta-hat's sign is not stable across evaluable folds (card: "sign FLIP across
    folds (direction not preregistered)"). Zero signs recorded on a degenerate/NA-only fold are
    excluded from the comparison (a true zero is neither a flip nor a confirmation)."""
    signs = {int(np.sign(s)) for s in fold_signs if s != 0}
    return len(signs) > 1


def concentration_kill(improvement_share_n_le_5: float, *, threshold: float = 0.5) -> bool:
    """Kill iff the out-of-fold improvement is NOT concentrated on the n <= 5 cold-start stratum
    (card: "improvement concentrating outside n <= 5" kills the arm AS A COLD-START CLAIM; the
    required-for-the-claim secondary diagnostic is 'improvement concentration on n <= 5'). A
    majority-share convention (>= 0.5) is the decision rule; ``threshold`` is exposed, defaulting
    to the plain-English majority reading of "concentrated", and is never silently varied per
    call -- every caller in this program uses the default.
    """
    return float(improvement_share_n_le_5) < float(threshold)


def evaluate_kill_conditions(*, fold_intervals: Sequence[tuple[float, float]],
                             fold_signs: Sequence[int],
                             improvement_share_n_le_5: float) -> dict:
    """One decidable verdict per frozen kill rule, plus the OR-combined arm verdict."""
    ci = delta_ci_kill(fold_intervals)
    sign = sign_flip_kill(fold_signs)
    conc = concentration_kill(improvement_share_n_le_5)
    return {
        "delta_ci_covers_zero_every_fold": ci,
        "sign_flip_across_folds": sign,
        "improvement_not_concentrated_on_coldstart_stratum": conc,
        "killed": bool(ci or sign or conc),
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
                               "table: A07 in ARMS_WITH_FREE_GLOBAL_INTERCEPT)",
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
                         f"challenger_input); {TREATMENT_COL} = exp(-n_i/5), n_i computed on the "
                         "contract-schedule clock (n_clock_pin), tau=5 fixed by source"),
        "missing_value_handling": "none -- complete-case receipted frame; n_i construction fails "
                                  "closed (A07ConstructionFailure) rather than imputing on any "
                                  "(team_id, season) absent from the contract schedule",
        "companion_components": "none",
        "fallback_rules": "S7 condition-number check of early_season_transient vs depth; "
                          "arm/fold UNEVALUABLE (refuse_to_score_fold) on near-affinity "
                          f"(R2 >= {NEAR_AFFINE_R2} or |spearman| >= {NEAR_AFFINE_SPEARMAN}); "
                          "retirement if unevaluable in >= 2 folds",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the 2,982-row resolved possession universe (1,491 game clusters); "
                              "n_i alone is computed on the 2,990-row contract schedule superset",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


# --------------------------------------------------------------------------------------------- #
# the arm module
# --------------------------------------------------------------------------------------------- #

class A07EarlySeasonTransient:
    """P36 RUNNER_INTERFACE-conformant module for A07_early_season_transient.

    Constructed with the CONTRACT SCHEDULE (superset of ``universe``, carrying the four
    universe-excluded 2021 rows the n_clock_pin requires) plus the fold-id list and row count the
    caller will present to ``p26_k0_record`` (mirrors the shared runner's ToyArm convention:
    metadata the P26/receipt hooks need is bound at construction, not derived from ``build_design``
    arguments, since those hooks take no per-call arguments in the frozen interface).
    """

    arm_id = ARM_ID

    def __init__(self, contract_schedule: pd.DataFrame, fold_ids: Sequence[str] = (),
                n_rows: int | None = None):
        missing = [c for c in REQUIRED_SCHEDULE_COLS if c not in contract_schedule.columns]
        if missing:
            raise A07ConstructionFailure(
                f"contract_schedule missing required columns {missing}")
        self._contract_schedule = contract_schedule.reset_index(drop=True)
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows) if n_rows is not None else int(len(contract_schedule))

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        return {}                      # A07 has no enumerated grid; one module = the whole arm

    def element_id(self) -> str:
        return "A07_early_season_transient__single"

    def uses_global_intercept(self) -> bool:
        return True                    # P35 intercept_structure: A07 in ARMS_WITH_FREE_GLOBAL_...

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in universe.columns]
        if missing:
            raise A07ConstructionFailure(
                f"universe is missing required columns {missing} (receipted incumbent-path "
                f"gap/depth/opp_depth columns, or team_id/season/game_date identity columns)")

        n_i = compute_n_i(self._contract_schedule,
                          universe["team_id"].to_numpy(),
                          universe["season"].to_numpy(),
                          universe["game_date"].to_numpy())
        transient = early_season_transient(n_i)

        columns = {
            GAP_COL: universe[GAP_COL].to_numpy(dtype=float),
            DEPTH_COL: universe[DEPTH_COL].to_numpy(dtype=float),
            OPP_DEPTH_COL: universe[OPP_DEPTH_COL].to_numpy(dtype=float),
            INTERCEPT_COL: np.ones(len(universe), dtype=float),
            TREATMENT_COL: transient,
        }
        nuisance = [GAP_COL, DEPTH_COL, OPP_DEPTH_COL, INTERCEPT_COL]
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": nuisance,
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": list(nuisance),
                                  "comparison": "term_removal"},
            "indicator_cols": [],       # gap/depth/opp_depth/transient are continuous; intercept
                                       # is structural, never listed as an indicator
            "columns": columns,
        }

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        train_digest = _digest("A07_training_rows", self._fold_ids, self._n_rows)
        eval_digest = _digest("A07_evaluation_rows", self._fold_ids, self._n_rows)
        side = _sidespec(self._fold_ids, train_digest, eval_digest)
        structural = [GAP_COL, DEPTH_COL, OPP_DEPTH_COL, INTERCEPT_COL]
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "an early-season transient deviation from the incumbent's projected "
                            "pace that decays geometrically in the offense team's own count of "
                            "completed same-season contract-schedule games (cold-start signal "
                            "beyond what total evidence depth already carries)",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "delta", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "no early-season transient beyond "
                                                             "depth"}],
                "claimed_signal_axes": ["season_time", "support_size"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        f"removing {TREATMENT_COL} leaves only {GAP_COL}/{DEPTH_COL}/"
                        f"{OPP_DEPTH_COL}/intercept in the null; none of those four vary within a "
                        "season by the team's own same-season game count n_i, so the null cannot "
                        "express any decay in n_i and the claimed season_time/support_size "
                        "transient signal is destroyed by construction")}},
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
                "name": "A07_early_season_transient", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [TREATMENT_COL],
                "structural_terms": list(structural),
                "declaration_routing": {
                    TREATMENT_COL: "substantive_features",
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "A07_early_season_transient__K0_MATCHED", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": list(structural),
                "declaration_routing": {
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": dict(side)},
            "fold_local_fallback": {
                "required": True,
                "trigger": f"S7 condition-number check of {TREATMENT_COL} vs {DEPTH_COL}: "
                          f"near-affinity R2 >= {NEAR_AFFINE_R2} or |spearman| >= "
                          f"{NEAR_AFFINE_SPEARMAN} (measured pre-fit max R2 0.958 in "
                          "train_lt_2022, below threshold; P33 measurement, carried -- not "
                          "re-measured by this node)",
                "numeric_threshold": NEAR_AFFINE_R2,
                "action": "refuse_to_score_fold",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature arm: eligible for a feature_value verdict "
                                    "ONLY against K0_MATCHED[A07]; K0_FLAT carries no promotion "
                                    "value whatsoever (k0_flat_role diagnostic_only)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "K0 K5 (P35 amendment): the null's terms are 'receipted incumbent-path features "
                "granted to the null' (S6 direction 1); MAE(K0[A07]) is NOT an incumbent "
                "benchmark and this arm may not claim the null 'recovers the incumbent'.",
                "K0 K6 / n_clock_pin: n_i is counted on the CONTRACT SCHEDULE (2,990 rows, "
                "including the four universe-excluded 2021 opening-day games); the universe-row "
                "clock is barred.",
                "MULT B-3: dual-Holm alternate composition pinned -- primary COLDSTART_FALLBACK "
                "(m=5, ordering over 4, A14 fixed slot), alternate {A02,A03,A05,A07} m=4, "
                "hold-others-at-primary, stricter governs.",
                "MULT B-7: A03/A07 both-pass joint re-test is named (measured max fold R2 0.7134 "
                ">= 0.25): if both A03 and A07 pass their primary gates the joint nested re-test "
                "runs. Out of scope for this feature-construction module.",
            ],
        }

    # ---- guards ---------------------------------------------------------------------
    def lag_specs(self) -> dict:
        return {
            GAP_COL: {"column": GAP_COL, "kind": "DERIVED_NO_JOIN",
                      "source_artifact_id": "team_possession_prior/1",
                      "entity_keys": ("game_id", "team_id"),
                      "rationale": "difference of two prior-games-only trailing-window pace "
                                   "means (team_pace_estimate - opp_pace_estimate)"},
            DEPTH_COL: {"column": DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                       "source_artifact_id": "team_possession_prior/1",
                       "entity_keys": ("game_id", "team_id"),
                       "rationale": "count of prior games backing the team's own pace estimate, "
                                    "capped at WINDOW_K=10"},
            OPP_DEPTH_COL: {"column": OPP_DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "team_possession_prior/1",
                           "entity_keys": ("game_id", "team_id"),
                           "rationale": "same evidence-depth count, for the opponent"},
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "SCHEDULE",
                            "source_artifact_id": "team_possession_prior/1",
                            "entity_keys": ("team_id", "season"), "order_column": "game_date",
                            "rationale": (
                                "n_i = count of the offense team's completed same-season "
                                "CONTRACT-SCHEDULE games strictly before game_date(g) "
                                "(n_clock_pin); a pure schedule fact (team_id, season, game_date "
                                "and completedness only) fixed before tipoff, with no dependency "
                                "on any realised in-game quantity of the target game or any other "
                                "game. Declared SCHEDULE, not PRIOR_GAME, because PRIOR_GAME's "
                                "shift-based re-derivation verifies a per-entity VALUE lag, not a "
                                "cumulative count; this labelling choice is disclosed as an "
                                "implementation ambiguity in the module docstring and REPORT.md, "
                                "not resolved silently")},
            # INTERCEPT_COL carries no lag_spec: it is a structural constant, not a declared
            # feature (mirrors the shared runner's ToyArmWithIntercept convention).
        }

    def lag_sources(self) -> dict:
        return {"contract_schedule": self._contract_schedule}

    def preregistered_contrasts(self):
        return None            # A07 registers no P25 contrast column (that is A02's obligation)

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 p23_franchise_continuity_precondition names A08,A09,A10,A11,A12,A13,A14,A16,A17,
        # A19,A21,A22,A24 -- A07 is NOT in that list.
        return False

    def p23_receipts(self) -> list:
        return []

    def p27_rule(self):
        # A07's registered fold-local fallback is the S7 NEAR-AFFINITY / condition-number check
        # (fold_local_fallback above), not an ActiveSetRule-shaped cluster-support/min-std rule
        # (contrast A03's S7_TIER_SUPPORT_v1). The frozen card registers no ActiveSetRule for A07.
        return None
