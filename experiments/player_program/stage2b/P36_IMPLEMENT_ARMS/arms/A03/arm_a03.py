#!/usr/bin/env python3
"""arm_a03.py -- P36 arm module for A03_cal_shallow_tier_intercept.

Frozen source: P35_FREEZE_TASK_CARDS/SPEC.json (sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32), task_cards[A03], amended
from and carrying-by-hash-reference P33_PREREGISTRATION_DRAFT/SPEC.json (sha256
066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) arms[A03_cal_shallow_tier_intercept].

Mechanism (P33): shallow-evidence projections share a common level error from a drifted league
prior. Model: eta = log_exposure + alpha_S * 1[pace_evidence_depth <= 3]; DEEP is the reference
level; mu = exp(eta); no global intercept in arm or null (P35 intercept_structure: A03 is in
ARMS_WITHOUT_GLOBAL_INTERCEPT); alpha_S = 0 recovers the incumbent exactly.

K0_MATCHED (P35, unchanged from P33 by the freeze): null = [log_exposure], zero fitted
parameters, term_removal comparison, IS the frozen incumbent exactly under the P35 no-intercept
reading.

Enumeration (P33 hyperparameters.handling): "ENUMERATION OBLIGATION DISCHARGED: single element
t = 3, charged as 1 element." Per RUNNER_INTERFACE.md section 2, single-element arms report an
empty `enumeration_element()`; the pinned threshold (3) is a fixed card constant, not a grid
choice, and is recorded in `p26_k0_record()` and `lag_specs()` instead.

Fold-local fallback (P35 registers S7_TIER_SUPPORT_v1 for this arm via a registry-append
payload; P33 fallback names ACTIVE_SET_RULE_PREREGISTRATION.json sha256
327fa8ec9fb54e3635ae70b540573b4121c6136fc5034cbdb689cabbe2986db7): "if either tier falls below
the 10-cluster training floor in a fold, arm collapses to incumbent for that fold, fold
UNEVALUABLE for this member, identically for arm and null."

IMPLEMENTATION NOTE ON THE FALLBACK -- flagged for P37, not resolved here (standing rule 3: a
missing check is closed with a task-specific wrapper, never by editing a shared gate):
`fold_estimability_guard.ActiveSetRule.decide()` (the shared P27 mechanism `p27_rule()` binds
into) computes cluster support ONLY for the terms it is handed -- i.e. for the declared design
column "1[SHALLOW]" (the SHALLOW tier). The card's rule is symmetric ("EITHER tier"): it also
requires the DEEP reference tier (SHALLOW == 0, which has no design column of its own because
there is no global intercept) to carry >= 10 training clusters. The generic P27 mechanism cannot
see a tier that has no design column. `tier_symmetry_check()` below is a task-specific,
call-site-only wrapper that evaluates the CARD's actual two-sided rule directly against the
universe/fold; it supplements, and never edits or wraps-and-weakens, the frozen P27 guard that
`p27_rule()` still feeds honestly (SHALLOW-tier support only, exactly as the generic mechanism
can express it). Both checks are recorded; neither is silently dropped.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TARGET_COL_REAL  # noqa: F401

# ---------------------------------------------------------------------------------------------
# frozen card constants (P33/P35 A03 task card -- never a tuning knob)
# ---------------------------------------------------------------------------------------------
ARM_ID = "A03_cal_shallow_tier_intercept"
SHALLOW_THRESHOLD = 3                       # P33: "t = 3 ... the only threshold ... defensible"
SHALLOW_COL = "1[SHALLOW]"                  # materialised treatment column name (card's own name)
DEPTH_SOURCE_COL = "pace_evidence_depth"    # receipted Stage 1B path feature, already in-frame
TIER_FLOOR_CLUSTERS = 10                    # S7_TIER_SUPPORT_v1 numeric trigger, both tiers
S7_RULE_ID = "S7_TIER_SUPPORT_v1"
ACTIVE_SET_RULE_PREREGISTRATION_SHA256 = (
    "327fa8ec9fb54e3635ae70b540573b4121c6136fc5034cbdb689cabbe2986db7")
P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"

_HERE = Path(__file__).resolve().parent                    # .../P36_IMPLEMENT_ARMS/arms/A03
_STAGE2B = _HERE.parents[2]                                 # .../stage2b
_FEG_PATH = (_STAGE2B / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD" / "fold_estimability_guard.py")


def _load_feg():
    """Import the frozen P27 module by file path, read-only, exactly as guard_harness does.

    Never edited, never wrapped-and-weakened; used only to construct the ActiveSetRule the same
    way the shared runner will, so this module's spec digest is guaranteed to match at
    Preregistration-check time rather than risk drifting from a hand-copied hash.
    """
    name = "p27_fold_estimability_guard_for_A03"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _FEG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)     # dataclass() needs cls.__module__ resolvable, as
                                          # guard_harness._load does for the same frozen module
    spec.loader.exec_module(mod)
    return mod


def _row_digest(n: int) -> str:
    return f"rows:n={n}"


def _sidespec(fold_ids, n_rows) -> dict:
    return {
        "intercept_treatment": ("none -- no global intercept in arm or null "
                                "(P35 intercept_structure: A03 in "
                                "without_any_global_intercept)"),
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{OFFSET_COL} = log(projected_team_off_possessions), frozen "
                           "incumbent D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": _row_digest(n_rows),
        "evaluation_rows": _row_digest(n_rows),
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": (f"none beyond 1[{DEPTH_SOURCE_COL} <= {SHALLOW_THRESHOLD}], computed "
                          "once from the receipted, already-in-frame pace_evidence_depth "
                          "column; no per-fold recomputation, no training-fold-dependent "
                          "constant"),
        "missing_value_handling": ("none -- pace_evidence_depth is resolved for every universe "
                                   "row (pace_resolved restriction applied upstream in "
                                   "possession_features.py)"),
        "companion_components": "none",
        "fallback_rules": (f"{S7_RULE_ID}: either tier (SHALLOW = "
                           f"1[{DEPTH_SOURCE_COL} <= {SHALLOW_THRESHOLD}], or its DEEP "
                           f"complement) below the {TIER_FLOOR_CLUSTERS}-cluster training floor "
                           "in a fold collapses the arm to the incumbent for that fold, fold "
                           "UNEVALUABLE, identically arm and null"),
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS universe",
        "post_processing": "none",
        "prediction_universe": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS universe",
    }


class ArmA03:
    """A03_cal_shallow_tier_intercept -- one module, one (single) enumeration element."""

    arm_id = ARM_ID

    def __init__(self, fold_ids=(), n_rows: int = 0):
        # fold_ids / n_rows are carried only for the P26 record's descriptive invariants; the
        # design itself never depends on them (t=3 is fold-independent, per the card).
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows)

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        # single-element arm (P33 hyperparameters.handling: "ENUMERATION OBLIGATION
        # DISCHARGED"); RUNNER_INTERFACE.md section 2: "{} for single-element arms"
        return {}

    def element_id(self) -> str:
        return f"{self.arm_id}__t{SHALLOW_THRESHOLD}"

    def uses_global_intercept(self) -> bool:
        return False

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe: pd.DataFrame) -> dict:
        if DEPTH_SOURCE_COL not in universe.columns:
            raise KeyError(f"{self.arm_id}: universe frame is missing '{DEPTH_SOURCE_COL}'; "
                           "this arm cannot be built without the receipted Stage 1B depth "
                           "feature")
        depth = universe[DEPTH_SOURCE_COL].to_numpy(dtype=float)
        shallow = (depth <= float(SHALLOW_THRESHOLD)).astype(float)
        return {
            "treatment_cols": [SHALLOW_COL],
            "nuisance_cols": [],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [],
                                  "comparison": "term_removal"},
            "indicator_cols": [SHALLOW_COL],
            "columns": {SHALLOW_COL: shallow},
        }

    # ---- P26 ------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids, self._n_rows)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "calibration_only",
            "treatment_mechanism": {
                "statement": ("shallow-evidence projections share a common level error from a "
                             f"drifted league prior; alpha_S is the level correction on rows "
                             f"with {DEPTH_SOURCE_COL} <= {SHALLOW_THRESHOLD} (SHALLOW), DEEP "
                             "as the reference level"),
                "treatment_terms": [SHALLOW_COL],
                "tested_parameters": [{"name": "alpha_S", "role": "intercept", "null_value": 0,
                                       "null_value_meaning": "no shallow-tier level error"}],
                "claimed_signal_axes": ["support_size"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": ("removing 1[SHALLOW] leaves only the bare "
                                                "offset with no shallow/deep split; the "
                                                "tier-specific level correction the arm claims "
                                                "cannot appear in any prediction")}},
            "invariants": {
                "rows": _row_digest(self._n_rows),
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": [],
                "lower_order_structural_terms": []},
            "arm_spec": {
                "name": "arm", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [SHALLOW_COL],
                "structural_terms": [],
                "declaration_routing": {SHALLOW_COL: "substantive_features"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "k0", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": [],
                "declaration_routing": {},
                "comparison_gate_sidespec": dict(side)},
            "fold_local_fallback": {
                "required": True,
                "trigger": (f"either tier (SHALLOW=1[{DEPTH_SOURCE_COL}<="
                           f"{SHALLOW_THRESHOLD}]=1, or SHALLOW=0) has fewer than "
                           f"{TIER_FLOOR_CLUSTERS} distinct training game clusters"),
                "numeric_threshold": TIER_FLOOR_CLUSTERS,
                "action": "drop_term_for_fold",
                "registered_before_results": True},
            "verdict_label_policy": ("CALIBRATION RESULT ONLY -- not eligible for a feature "
                                     "value label however large challenger_vs_k0 is"),
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
        }

    # ---- guards ---------------------------------------------------------------------
    def lag_specs(self) -> dict:
        return {
            SHALLOW_COL: {
                "column": SHALLOW_COL,
                "kind": "DERIVED_NO_JOIN",
                "source_artifact_id": "possession_features/team_possession_prior_v1_depth",
                "source_value_column": DEPTH_SOURCE_COL,
                "rationale": (f"1[{DEPTH_SOURCE_COL} <= {SHALLOW_THRESHOLD}] is a deterministic "
                             f"threshold of {DEPTH_SOURCE_COL}, a column already present in the "
                             "audited universe frame (possession_features.py FEATURE_NAMES, "
                             "receipted Stage 1B path, D009 standard (a)); no join, no lag "
                             "re-derivation, the full P22 dependency battery still applies"),
            },
        }

    def lag_sources(self) -> dict:
        return {}

    def preregistered_contrasts(self):
        return None

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # A03 is absent from the P33 shared_arm_invariants.p23_franchise_continuity_precondition
        # arm list (A08, A09, A10, A11, A12, A13, A14, A16, A17, A19, A21, A22, A24)
        return False

    def p23_receipts(self) -> list:
        return []

    def p27_rule(self):
        """The generic P27 mechanism, fed honestly: SHALLOW-tier support only (see module
        docstring for the DEEP-tier gap this cannot express, closed by `tier_symmetry_check`).
        """
        feg = _load_feg()
        rule = feg.ActiveSetRule(
            rule_id=S7_RULE_ID,
            min_nonzero_clusters=TIER_FLOOR_CLUSTERS,
            min_std=0.0,
            rationale=("P33/P35 A03 fallback: either tier below the 10-cluster training floor "
                       "collapses the arm to the incumbent for that fold, fold UNEVALUABLE, "
                       "identically arm and null (ACTIVE_SET_RULE_PREREGISTRATION.json sha256 "
                       f"{ACTIVE_SET_RULE_PREREGISTRATION_SHA256}). This ActiveSetRule instance "
                       "expresses the SHALLOW-tier half of that rule -- the half the generic "
                       "P27 mechanism can see, because SHALLOW is the only declared design "
                       "column; the DEEP-tier half is evaluated separately by "
                       "tier_symmetry_check (see module docstring)."))
        rule_kwargs = {"rule_id": rule.rule_id,
                       "min_nonzero_clusters": rule.min_nonzero_clusters,
                       "min_std": rule.min_std, "rationale": rule.rationale}
        prereg_kwargs = {
            "registered_at_utc": ("P35_FREEZE_TASK_CARDS freeze (2026, exact UTC not carried "
                                  "in the frozen SPEC.json bytes -- recorded honestly as an "
                                  "unestablished precision, not fabricated)"),
            "registered_by": ("P35_FREEZE_TASK_CARDS, A03 card, amendments_applied[0] "
                              "('FOLDS F6: S7_TIER_SUPPORT_v1 registered for this arm via "
                              "registry append payload (this node)')"),
            "rule_spec_sha256": rule.spec_sha256,
            "results_visible_at_registration": False,
            "record_path": ("experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/"
                            f"SPEC.json (sha256 {P35_SPEC_SHA256}) #task_cards"
                            "[arm_id=A03_cal_shallow_tier_intercept]"),
        }
        return (rule_kwargs, prereg_kwargs)


# ---------------------------------------------------------------------------------------------
# task-specific decidability helpers (call-site only; never touch a shared gate)
# ---------------------------------------------------------------------------------------------

def tier_symmetry_check(universe: pd.DataFrame, train_idx, *,
                        cluster_col: str = "game_id",
                        depth_col: str = DEPTH_SOURCE_COL,
                        threshold: int = SHALLOW_THRESHOLD,
                        floor: int = TIER_FLOOR_CLUSTERS) -> dict:
    """The CARD's full S7_TIER_SUPPORT_v1 rule, both tiers, evaluated directly.

    Deterministic and performance-blind: it conditions only on TRAINING-row depth values and
    cluster ids, never on any target/residual/metric (same discipline as P27's SupportSummary).
    Returns a decision dict; the runner-facing `p27_rule()` above cannot express the DEEP-tier
    half of this rule because DEEP has no design column, so this function is this arm's own
    task-specific closure of that gap (standing rule 3).
    """
    tr = np.asarray(train_idx, dtype=int)
    depth = universe[depth_col].to_numpy(dtype=float)[tr]
    clusters = universe[cluster_col].to_numpy()[tr]
    shallow_mask = depth <= float(threshold)
    deep_mask = ~shallow_mask
    n_shallow_clusters = int(pd.unique(clusters[shallow_mask]).size)
    n_deep_clusters = int(pd.unique(clusters[deep_mask]).size)
    shallow_ok = n_shallow_clusters >= floor
    deep_ok = n_deep_clusters >= floor
    evaluable = shallow_ok and deep_ok
    return {
        "rule_id": S7_RULE_ID,
        "floor": int(floor),
        "n_shallow_training_clusters": n_shallow_clusters,
        "n_deep_training_clusters": n_deep_clusters,
        "shallow_ok": shallow_ok,
        "deep_ok": deep_ok,
        "evaluable": evaluable,
        "verdict": "ESTIMABLE" if evaluable else "UNEVALUABLE_PROSPECTIVELY",
        "trigger_fired_on": ([] if evaluable else
                             ([("SHALLOW", n_shallow_clusters)] if not shallow_ok else [])
                             + ([("DEEP", n_deep_clusters)] if not deep_ok else [])),
    }


def evaluate_kill_conditions(fold_alpha_intervals: dict, fold_alpha_point: dict | None = None
                             ) -> dict:
    """The card's kill_conditions_frozen, made decidable.

    'alpha_S = 0 not rejected (UNCORRECTED 95% training-cluster interval covers 0 in every
    evaluable fold), or sign instability across them; no post-hoc appeal to the missing opening
    day (D010)'.

    `fold_alpha_intervals`: {fold_id: (lo, hi)} training-cluster bootstrap interval for alpha_S,
    one entry per EVALUABLE fold only (folds the S7 rule marked UNEVALUABLE never enter this
    dict -- they are excluded from the evaluable-fold set, per P33 inference block).
    `fold_alpha_point`: optional {fold_id: point_estimate}; when given, sign instability is
    checked in addition to the no-rejection kill.

    Pure function of its arguments; no target/residual/fit is performed here -- this is the
    decision rule alone, exercised with synthetic numbers in tests.
    """
    if not fold_alpha_intervals:
        return {"killed": None, "reason": "no evaluable folds supplied; kill undecidable "
                                          "(distinct from a fired kill)"}
    covers_zero = {fid: (lo <= 0.0 <= hi) for fid, (lo, hi) in fold_alpha_intervals.items()}
    no_rejection_kill = all(covers_zero.values())

    sign_instability = False
    signs = {}
    if fold_alpha_point:
        for fid, v in fold_alpha_point.items():
            if v > 0:
                signs[fid] = 1
            elif v < 0:
                signs[fid] = -1
            else:
                signs[fid] = 0
        nonzero_signs = {s for s in signs.values() if s != 0}
        sign_instability = len(nonzero_signs) > 1

    killed = bool(no_rejection_kill or sign_instability)
    reasons = []
    if no_rejection_kill:
        reasons.append("alpha_S = 0 not rejected: interval covers 0 in every evaluable fold")
    if sign_instability:
        reasons.append(f"sign instability across folds: {signs}")
    return {"killed": killed, "covers_zero_by_fold": covers_zero,
           "no_rejection_kill": no_rejection_kill, "sign_instability": sign_instability,
           "signs_by_fold": signs, "reasons": reasons,
           "d010_note": ("no post-hoc appeal to the missing 2021 opening day is made or "
                        "possible here -- this function sees only the supplied fold intervals")}
