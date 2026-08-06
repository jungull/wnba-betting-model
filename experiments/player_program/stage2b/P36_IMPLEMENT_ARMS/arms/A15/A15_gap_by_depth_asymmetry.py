#!/usr/bin/env python3
"""A15_gap_by_depth_asymmetry.py -- P36 arm module for A15_gap_by_depth_asymmetry.

FROZEN CARD (verbatim binding source): experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/
SPEC.json, sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32 (verified at
implementation time), task_cards[].arm_id == "A15_gap_by_depth_asymmetry", carrying P33
PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072
d347d093) arm A15 by hash reference, amended exactly by the card's amendments_applied list.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

MODEL (frozen, card-pinned):
    asym_i = s(depth_i) - s(opp_depth_i);  s(d) = 1 / (1 + d/5)   [s_scale_h = 5, FIXED, P33
             hyperparameters.fixed]
    eta = intercept + log_exposure + b1*gap + b2*depth + b3*opp_depth + b4*asym
                     + beta4 * gap * asym
    mu  = exp(eta)
    free global intercept, arm AND null identically (P35 intercept_structure table: A15 in
    ARMS_WITH_FREE_GLOBAL_INTERCEPT / runner_constants.ARMS_WITH_FREE_GLOBAL_INTERCEPT).

TREATMENT: the interaction gap * asym (1 df). asym is built ONLY through the fixed bounded
transform s(); no new data enters (P33 hyperparameters.handling).

COLUMN LINEAGE (frozen, byte-exact names from the receipted incumbent path,
experiments/player_program/possession_features.py):
    gap       -> pace_gap                = team_pace_estimate - opp_pace_estimate
    depth     -> pace_evidence_depth     = trailing-window evidence count backing the team's own
                                            pace estimate, capped at WINDOW_K=10, 0 on league-prior
                                            fallback
    opp_depth -> opp_pace_evidence_depth = same, for the opponent
gap is the SAME admissible own-opp contrast A02 treats (== A02's treatment column; A15 is
credited only for the gap:asym INTERACTION, never the gap main effect -- both are granted whole
to the null, so no credit-collision is possible by construction; the frozen card additionally
records the K0 review's measured cross-fold orthogonality of the two arms' treatment columns
(corr <= 2.7e-18 every fold) -- a REAL-DATA measurement, carried by citation and NOT re-measured
by this node, which touches no real fold).

NAMING DISCLOSURE (implementation choice, not silently resolved): the frozen card's prose names
the treatment "gap:asym" and the mains "gap | depth | opp_depth | asym | intercept". This module
follows A07's established convention of using the receipted PRODUCER column names themselves
(pace_gap, pace_evidence_depth, opp_pace_evidence_depth) as the term names carried into
p26_k0_record's structural_terms / treatment_mechanism, so that P26's factor-splitting relation
check (R6, splitting a term on ":") sees the SAME identifiers used to materialise the design. The
interaction term is registered as "pace_gap:asym" (materialised column name == mechanism term
name); "asym" itself has no receipted producer name (it is built here, from receipted columns,
through the frozen fixed transform s()) and is named literally "asym" throughout. This is a
labelling choice with no effect on the scientific content of the card (it does not change
gap/depth/opp_depth/asym/beta4 or any preregistered number); recorded here and in REPORT.md for
P37 to affirm or overrule, per standing rule 1 (frozen bytes govern over prose) -- nothing frozen
names a correct materialised-column convention, so nothing is silently overridden.

K0_MATCHED[A15] (frozen, card k0_matched_frozen):
    null: [log_exposure | gap | depth | opp_depth | asym | intercept]  (comparison: term_removal)
    -- ALL mains including asym granted to the null; blocks re-centring credit.
    treatment_terms: ["gap:asym"], tested_parameters: [{beta4, coefficient, null_value=0}]

FOLD-LOCAL FALLBACK (frozen, card p26_k0_record.fold_local_fallback):
    "NO active-set rule; S7 failure -> arm/fold prospectively unevaluable, accepted in advance."
    No ActiveSetRule is registered for this arm (p27_rule() returns None), mirroring A07's
    handling of an arm whose only registered fallback is the generic S7 rank/condition-number
    check rather than a cluster-support ActiveSetRule instance.

KILL CONDITIONS (frozen, card kill_conditions_frozen): "beta4 interval covers 0; improvement not
concentrated in top-|asym| bucket; beta4 < 0 refutes the reliability mechanism."

KILL-CONDITION OPERATIONALISATION DISCLOSED, NOT SILENTLY RESOLVED: the third clause ("beta4 < 0
refutes the reliability mechanism") is a DIRECTIONAL refutation, distinct from A07/A11's
"sign-flip-across-folds" instability check (this arm has no preregistered sign-stability
requirement; a consistently negative estimate is itself a refutation, not merely unstable). This
module operationalises it as: any evaluable fold whose 95% training-cluster bootstrap interval for
beta4 lies ENTIRELY BELOW ZERO (upper bound < 0) triggers the kill -- the same interval machinery
the first clause already uses, read for a stronger (entirely-negative, not merely
covers-zero-or-negative-point-estimate) directional signal. This is the conservative reading (it
requires interval evidence, not a bare point-estimate sign) and is recorded so P37 can affirm or
overrule it; nothing frozen operationalises "beta4 < 0" more specifically than the prose quoted
above.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ frozen pins, restated here so
# this module has no runtime dependency on the runner/ directory (arms/A15 never imports from or
# writes to runner/; these constants are copied VALUES, not references, and are asserted equal to
# the runner's own copies in TESTS.py so drift is caught rather than silently tolerated).
ARM_ID = "A15_gap_by_depth_asymmetry"
OFFSET_COL = "log_exposure"
TARGET_LABEL = "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"
INTERCEPT_COL = "intercept"

GAP_COL = "pace_gap"
DEPTH_COL = "pace_evidence_depth"
OPP_DEPTH_COL = "opp_pace_evidence_depth"
ASYM_COL = "asym"
TREATMENT_COL = "pace_gap:asym"                    # gap * asym, 1 df interaction

S_SCALE_H = 5.0                                     # FIXED by source; never tunable (P33 pin)
TOP_ASYM_BUCKET_QUANTILE = 0.75                     # "top-|asym| bucket": top quartile by |asym|,
                                                     # the plain-English majority reading of "top
                                                     # bucket" -- disclosed default, never varied
                                                     # per call (mirrors A07's concentration_kill
                                                     # convention)

REQUIRED_UNIVERSE_COLS = (GAP_COL, DEPTH_COL, OPP_DEPTH_COL)


class A15ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No design is returned."""


# --------------------------------------------------------------------------------------------- #
# s(d) = 1 / (1 + d/5); asym = s(depth) - s(opp_depth); treatment = gap * asym
# --------------------------------------------------------------------------------------------- #

def s_transform(d: np.ndarray) -> np.ndarray:
    """The fixed bounded reliability transform s(d) = 1 / (1 + d / S_SCALE_H), S_SCALE_H = 5."""
    d = np.asarray(d, dtype=float)
    return 1.0 / (1.0 + d / S_SCALE_H)


def compute_asym(depth: np.ndarray, opp_depth: np.ndarray) -> np.ndarray:
    """asym = s(depth) - s(opp_depth). Built ONLY through the fixed bounded transform s(); no new
    data enters (P33 hyperparameters.handling)."""
    return s_transform(depth) - s_transform(opp_depth)


def compute_treatment(gap: np.ndarray, asym: np.ndarray) -> np.ndarray:
    """The 1-df treatment column: gap * asym."""
    return np.asarray(gap, dtype=float) * np.asarray(asym, dtype=float)


# --------------------------------------------------------------------------------------------- #
# kill-condition hooks (frozen card kill_conditions_frozen) -- PURE functions of synthetic /
# fold-summary inputs. They decide nothing about real performance; they exist so a downstream
# fitting node can call one deterministic decision function per rule rather than re-deriving the
# card's prose per implementation.
# --------------------------------------------------------------------------------------------- #

def beta4_ci_kill(fold_intervals: Sequence[tuple[float, float]]) -> bool:
    """Kill iff the beta4 95% training-cluster bootstrap interval covers 0 in EVERY evaluable
    fold (card: "beta4 interval covers 0"; operationalised per the shared inference block's
    "theta = 0 not rejected ... is operationalised as: the 95% interval covers 0 in EVERY
    evaluable fold"). No evaluable folds -> the condition cannot fire (nothing to evaluate); this
    is decided FALSE, not KILLED, and the caller is responsible for recording zero-evaluable-folds
    as its own separate finding.
    """
    if not fold_intervals:
        return False
    return all(lo <= 0.0 <= hi for lo, hi in fold_intervals)


def negative_refutation_kill(fold_intervals: Sequence[tuple[float, float]]) -> bool:
    """Kill iff ANY evaluable fold's 95% interval for beta4 lies ENTIRELY below zero (card:
    "beta4 < 0 refutes the reliability mechanism"; see module docstring for the disclosed
    directional-refutation operationalisation). Distinct from beta4_ci_kill: an interval that
    covers 0 is indecisive, not a refutation; an interval whose upper bound is < 0 is the
    directional refutation the card names.
    """
    return any(hi < 0.0 for _lo, hi in fold_intervals)


def concentration_kill(improvement_share_top_asym_bucket: float, *, threshold: float = 0.5) -> bool:
    """Kill iff the out-of-fold improvement is NOT concentrated in the top-|asym| bucket (card:
    "improvement not concentrated in top-|asym| bucket" -- the required secondary diagnostic).
    A majority-share convention (>= 0.5) is the decision rule; ``threshold`` is exposed, defaulting
    to the plain-English majority reading of "concentrated", and is never silently varied per call
    -- every caller in this program uses the default (mirrors A07's concentration_kill).
    """
    return float(improvement_share_top_asym_bucket) < float(threshold)


def evaluate_kill_conditions(*, fold_intervals: Sequence[tuple[float, float]],
                             improvement_share_top_asym_bucket: float) -> dict:
    """One decidable verdict per frozen kill rule, plus the OR-combined arm verdict."""
    ci = beta4_ci_kill(fold_intervals)
    neg = negative_refutation_kill(fold_intervals)
    conc = concentration_kill(improvement_share_top_asym_bucket)
    return {
        "beta4_ci_covers_zero_every_fold": ci,
        "beta4_negative_refutation_any_fold": neg,
        "improvement_not_concentrated_top_asym_bucket": conc,
        "killed": bool(ci or neg or conc),
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
                               "table: A15 in ARMS_WITH_FREE_GLOBAL_INTERCEPT)",
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
                         f"challenger_input); {ASYM_COL} = s({DEPTH_COL}) - s({OPP_DEPTH_COL}), "
                         f"s(d) = 1/(1+d/{S_SCALE_H:.0f}) fixed; {TREATMENT_COL} = "
                         f"{GAP_COL} * {ASYM_COL}"),
        "missing_value_handling": "none -- complete-case receipted frame; gap/depth/opp_depth are "
                                  "defined on every resolved universe row by the producer's own "
                                  "contract",
        "companion_components": "none",
        "fallback_rules": "NO active-set rule; a generic S7 rank/condition-number failure in a "
                          "fold makes that arm/fold prospectively UNEVALUABLE, accepted in "
                          "advance (no numeric threshold beyond the shared S7 checks)",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the 2,982-row resolved possession universe (1,491 game clusters)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


# --------------------------------------------------------------------------------------------- #
# the arm module
# --------------------------------------------------------------------------------------------- #

class A15GapByDepthAsymmetry:
    """P36 RUNNER_INTERFACE-conformant module for A15_gap_by_depth_asymmetry.

    No enumerated grid: one module instance binds the whole arm (mirrors A07's convention for a
    single-element arm; contrast A08/A09/A10/A11/A23 which need one instance per enumeration
    element).
    """

    arm_id = ARM_ID

    def __init__(self, fold_ids: Sequence[str] = (), n_rows: int | None = None):
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows) if n_rows is not None else 0

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        return {}                      # A15 has no enumerated grid; one module = the whole arm

    def element_id(self) -> str:
        return "A15_gap_by_depth_asymmetry__single"

    def uses_global_intercept(self) -> bool:
        return True                    # P35 intercept_structure: A15 in ARMS_WITH_FREE_GLOBAL_...

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in universe.columns]
        if missing:
            raise A15ConstructionFailure(
                f"universe is missing required columns {missing} (receipted incumbent-path "
                f"gap/depth/opp_depth columns)")

        gap = universe[GAP_COL].to_numpy(dtype=float)
        depth = universe[DEPTH_COL].to_numpy(dtype=float)
        opp_depth = universe[OPP_DEPTH_COL].to_numpy(dtype=float)
        asym = compute_asym(depth, opp_depth)
        treatment = compute_treatment(gap, asym)

        columns = {
            GAP_COL: gap,
            DEPTH_COL: depth,
            OPP_DEPTH_COL: opp_depth,
            ASYM_COL: asym,
            INTERCEPT_COL: np.ones(len(universe), dtype=float),
            TREATMENT_COL: treatment,
        }
        nuisance = [GAP_COL, DEPTH_COL, OPP_DEPTH_COL, ASYM_COL, INTERCEPT_COL]
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": nuisance,
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": list(nuisance),
                                  "comparison": "term_removal"},
            "indicator_cols": [],       # gap/depth/opp_depth/asym/treatment are all continuous;
                                       # intercept is structural, never listed as an indicator
            "columns": columns,
        }

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        train_digest = _digest("A15_training_rows", self._fold_ids, self._n_rows)
        eval_digest = _digest("A15_evaluation_rows", self._fold_ids, self._n_rows)
        side = _sidespec(self._fold_ids, train_digest, eval_digest)
        structural = [GAP_COL, DEPTH_COL, OPP_DEPTH_COL, ASYM_COL, INTERCEPT_COL]
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "the pace gap's predictive weight varies with the transformed depth "
                            "asymmetry between the two clubs (reliability weighting of the gap by "
                            "how unevenly-evidenced the two teams' pace estimates are)",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "beta4", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "gap weight does not vary with depth "
                                                             "asymmetry"}],
                "claimed_signal_axes": ["support_size"],   # P26 K0_MATCHED_SCHEMA enum; the closest
                                                           # frozen axis to "evidence-depth
                                                           # asymmetry" -- asym is built entirely
                                                           # from the two teams' evidence-depth
                                                           # (support size) counts
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        f"removing {TREATMENT_COL} leaves {GAP_COL}/{DEPTH_COL}/{OPP_DEPTH_COL}/"
                        f"{ASYM_COL}/intercept in the null -- every main effect the interaction "
                        "could otherwise be credited for absorbing, including asym's OWN main "
                        "effect (blocking re-centring credit), so the null cannot express any "
                        "gap-weight variation BY depth asymmetry and the claimed reliability "
                        "signal is destroyed by construction")}},
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
                "name": "A15_gap_by_depth_asymmetry", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [TREATMENT_COL],
                "structural_terms": list(structural),
                "declaration_routing": {
                    TREATMENT_COL: "substantive_features",
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", ASYM_COL: "preprocessing",
                    INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "A15_gap_by_depth_asymmetry__K0_MATCHED", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": list(structural),
                "declaration_routing": {
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", ASYM_COL: "preprocessing",
                    INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": dict(side)},
            "fold_local_fallback": {
                "required": True,
                "trigger": "generic S7 rank/condition-number check on the arm's full design "
                          "[offset | nuisance | candidate]; NO active-set rule is registered for "
                          "this arm (card p26_k0_record.fold_local_fallback: 'NO active-set rule; "
                          "S7 failure -> arm/fold prospectively unevaluable, accepted in advance')",
                "numeric_threshold": None,
                "action": "refuse_to_score_fold",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature arm: eligible for a feature_value verdict "
                                    "ONLY against K0_MATCHED[A15]; K0_FLAT carries no promotion "
                                    "value whatsoever (k0_flat_role diagnostic_only)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "K0 K2 (P35 amendment): free global intercept pinned, arm and null identically.",
                "A02/A15 accounting (P35 amendment, card's stronger K0-review verification): the "
                "two treatments (A02's pace_gap contrast, A15's pace_gap:asym interaction) are "
                "STRUCTURALLY orthogonal (cluster-symmetric vs cluster-antisymmetric); the card "
                "cites a measured cross-fold correlation <= 2.7e-18 -- a REAL-DATA measurement "
                "made by an earlier node, carried here by citation and NOT reproduced (this "
                "module touches no real fold). No double counting is possible by this "
                "construction regardless.",
                "asym is built ONLY through the fixed bounded transform s(d) = 1/(1+d/5), "
                "s_scale_h = 5 FIXED by source; no new data enters (P33 hyperparameters.handling).",
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
            ASYM_COL: {"column": ASYM_COL, "kind": "DERIVED_NO_JOIN",
                      "source_artifact_id": "team_possession_prior/1",
                      "entity_keys": ("game_id", "team_id"),
                      "rationale": f"s({DEPTH_COL}) - s({OPP_DEPTH_COL}) through the fixed bounded "
                                  "transform s(d) = 1/(1+d/5); a deterministic function of two "
                                  "already-lagged evidence-depth columns, no join, no new data"},
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "team_possession_prior/1",
                            "entity_keys": ("game_id", "team_id"),
                            "rationale": f"{GAP_COL} * {ASYM_COL}, a deterministic elementwise "
                                        "product of two already-lagged, already-DERIVED_NO_JOIN "
                                        "columns; no join, no new data"},
            # INTERCEPT_COL carries no lag_spec: it is a structural constant, not a declared
            # feature (mirrors the shared runner's ToyArmWithIntercept / A07 convention).
        }

    def lag_sources(self) -> dict:
        return {}                      # nothing needs PRIOR_GAME re-derivation; all DERIVED_NO_JOIN

    def preregistered_contrasts(self):
        return None            # A15 registers no P25 contrast column (that is A02's obligation)

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 p23_franchise_continuity_precondition names A08,A09,A10,A11,A12,A13,A14,A16,A17,
        # A19,A21,A22,A24 -- A15 is NOT in that list.
        return False

    def p23_receipts(self) -> list:
        return []

    def p27_rule(self):
        # A15's registered fold-local fallback is the generic S7 rank/condition-number check
        # (fold_local_fallback above), not an ActiveSetRule-shaped cluster-support/min-std rule
        # (contrast A03's S7_TIER_SUPPORT_v1). The frozen card registers no ActiveSetRule for A15.
        return None
