#!/usr/bin/env python3
"""a05_cal_playoff_intercept.py -- P36 arm module for A05_cal_playoff_intercept.

Frozen card (experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[A05_cal_playoff_intercept]):

    model: eta = log_exposure + pi * 1[is_playoff_game]; mu = exp(eta)
    no global intercept in arm or null (P35 intercept_structure -> A05 in
    ARMS_WITHOUT_GLOBAL_INTERCEPT)
    k0_matched: null = [log_exposure] -- zero fitted parameters; IS the frozen incumbent exactly
    comparison: term_removal
    treatment_terms: ["1[is_playoff_game]"]
    tested_parameters: [{name: pi, role: intercept, null_value: 0,
                          meaning: "incumbent playoff sizing correct"}]
    fold_local_fallback: fold non-discriminating when test playoff rows == 0 (train_lt_2026,
        measured); four evaluable folds. Numeric trigger: test playoff rows == 0.
        registered_before_results: true.
    guard_invocation: declared_family SUBSTANTIVE, recalibration_declaration NOT_APPLICABLE,
        offset log_exposure, incumbent_projection projected_team_off_possessions.
    amendments_applied: MULT B-5 ('family-corrected' struck from kill conditions); K0 K2 (no
        global intercept pinned); FOLDS F8 (bespoke test-side degeneracy trigger stands; no
        general test-side rule exists -- shared note); D3 preserved disagreement carried
        (recorded verbatim below, not resolved here).
    kill_conditions_frozen: "pi = 0 not rejected (UNCORRECTED interval covers 0 in every
        evaluable fold - four folds), or sign instability across them"

No enumeration grid: A05 is a single fitted element (P35 multiplicity_recomputed:
CALIBRATION_CONTROL_FAMILY members {A02:1, A03:1, A05:1}).

Carried verbatim from P33_PREREGISTRATION_DRAFT/SPEC.json (sha256
066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093, verified on disk by this
module's own test suite) per the P35 carry_convention -- these P33 fields are NOT named in the
P35 card's amendments_applied list, so they remain binding as-is:

    features: [{name: "is_playoff_game", construction: "schedule indicator (season_type ==
        'Playoffs')", lineage: "possession_features.py line 318, incumbent-carried column",
        cutoff_evidence: "S8 table: season_type ELIGIBLE ('schedule fact known at the cutoff')"}]
    fallback (GATE_INVOCATION_CONTRACT section 4, declared with numeric trigger): "on fold
        train_lt_2026 the TEST-side treatment column is identically zero (measured: 0 playoff
        test rows; training support 106 playoff clusters), the arm's prediction reduces to the
        null's by construction, and the fold contributes no discriminating information for pi.
        Effective evidence base: four folds (measured training playoff clusters
        17/40/60/82/106, all >= 10)."
    folds: "five fitted, four evaluable for pi (train_lt_2026 declared non-discriminating)"
        -- this is the direct confirmation that the real folds use EXPANDING_PRIOR_SEASONS
        naming (train_lt_YYYY), not SEASON_BLOCK; RUNNER_INTERFACE.md section 4 leaves the two
        readings open at the shared-runner level, but for A05 specifically the P33-carried
        record disambiguates it.
    preserved_disagreement (D3, in full): "the coldstart source excludes any new is_playoff_game
        term as fold-degenerate; the calibration source proposes it WITH the section-4
        fallback. Both preserved; retention follows the packet's own S7 clause." Not adjudicated
        by this module; carried forward for P37.

The P35 card's own kill_conditions_frozen strikes "family-corrected" from the P33 wording (MULT
B-5); this module implements the P35 (uncorrected) wording, not the P33 wording, exactly as the
amendment requires.

Ownership: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A05/ ONLY. This module
imports the frozen RUNNER_INTERFACE.md contract (runner/*.py) but never writes to runner/ or to
any other arm's directory.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np

ARM_ID = "A05_cal_playoff_intercept"
SOURCE_COL = "is_playoff_game"          # raw pre-tipoff schedule flag on the input universe
TREATMENT_COL = "is_playoff_indicator"  # materialised 0.0/1.0 design column, 1[is_playoff_game]

P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"


def _sidespec(fold_ids):
    return {
        "intercept_treatment": "none -- no global intercept in arm or null (P35 K0 K2 pin)",
        "calibration_freedom": "none -- pi is a single fixed-shape indicator coefficient, no "
                               "post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": "log_exposure = log(projected_team_off_possessions)",
        "training_rows": "fold train_idx, per the runner's per-fold split",
        "evaluation_rows": "fold test_idx, per the runner's per-fold split",
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": "none beyond 0.0/1.0 casting of the raw schedule flag",
        "missing_value_handling": "none -- is_playoff_game is a complete-case schedule fact "
                                  "fixed at schedule-publication time, never missing pre-tipoff",
        "companion_components": "none",
        "fallback_rules": "fold-local test-side non-discrimination note only (see "
                          "fold_local_fallback); no training-side active-set rule registered",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the arm's declared team-game universe (frozen 2,982-row real "
                              "universe at P38; synthetic fixture rows in P36 tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A05CalPlayoffIntercept:
    """One arm x one enumeration element (single-element arm: enumeration_element() == {})."""

    arm_id = ARM_ID

    def __init__(self, fold_ids):
        self._fold_ids = [str(f) for f in fold_ids]

    # ---- metadata hooks ------------------------------------------------------------------
    def card_id(self):
        return self.arm_id

    def declared_family(self):
        return "SUBSTANTIVE"

    def recalibration_declaration(self):
        return "NOT_APPLICABLE"

    def enumeration_element(self):
        return {}

    def element_id(self):
        return f"{ARM_ID}__single"

    def uses_global_intercept(self):
        return False

    # ---- design ----------------------------------------------------------------------------
    def build_design(self, fold, universe):
        """Deterministic pass-through of the pre-tipoff playoff schedule flag. No fold-computed
        constant exists for this arm: the treatment column is identical across every fold and
        across repeated calls on the same universe (feature determinism)."""
        raw = universe[SOURCE_COL].to_numpy()
        ind = raw.astype(float)
        bad = ~np.isin(ind, (0.0, 1.0))
        if np.any(bad):
            raise ValueError(f"{SOURCE_COL} must be a strict 0/1 pre-tipoff schedule flag; "
                             f"{int(bad.sum())} non-{{0,1}} value(s) found")
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [],
                                  "comparison": "term_removal"},
            "indicator_cols": [TREATMENT_COL],
            "columns": {TREATMENT_COL: ind},
        }

    # ---- P26 ---------------------------------------------------------------------------------
    def p26_k0_record(self):
        """Shape and cross-field relations are enforced by P26 validate_k0_matched.validate
        (K0_MATCHED_SCHEMA.json, additionalProperties: false throughout -- every key here is one
        the schema names, nothing extra). The two schema-legal R8 findings this record trips
        (tested_parameter_missing[missing_role=slope]; lower_order_term_missing_from_k0 with
        empty lower_order_structural_terms) are the expected, filtered R8 findings for a
        calibration_only arm under P35 r8_scope_adjudication -- see guard_harness.p26_check and
        TESTS_A05.t03_p26_k0_contract."""
        side = _sidespec(self._fold_ids)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "calibration_only",
            "treatment_mechanism": {
                "statement": "the incumbent's playoff-game sizing may carry a residual level "
                             "error; pi absorbs it as a fixed log-linear shift on playoff rows",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "pi", "role": "intercept", "null_value": 0,
                                       "null_value_meaning": "incumbent playoff sizing correct"}],
                "claimed_signal_axes": ["season_time"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": "removing 1[is_playoff_game] leaves log_exposure "
                                               "alone -- the null IS the frozen incumbent "
                                               "exactly, zero fitted parameters (P35 "
                                               "intercept_structure: no-intercept reading)"}},
            "invariants": {
                "rows": "the arm's declared team-game universe (see side.candidate_universe)",
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": "none beyond the descriptive fold-local note in notes[]; "
                                      "no training-side P27 active-set rule is registered for "
                                      "this arm",
                "nuisance_terms": [],
                "lower_order_structural_terms": []},
            "arm_spec": {
                "name": "arm", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [TREATMENT_COL],
                "structural_terms": [],
                "declaration_routing": {TREATMENT_COL: "substantive_features"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "k0", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": [],
                "declaration_routing": {},
                "comparison_gate_sidespec": side},
            "fold_local_fallback": {
                "required": False,
                "trigger": "test playoff rows == 0",
                "numeric_threshold": 0,
                "action": "not_applicable",
                "registered_before_results": True},
            "verdict_label_policy": "calibration_only: eligible for a CALIBRATION result label "
                                    "only, never a substantive feature-value claim, per P35 "
                                    "p26_k0_contract_enforcement.r8_scope_adjudication",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "P35 fold_local_fallback (FOLDS F8) + P33-carried detail (P33 SPEC.json sha256 "
                "066b2a04...d347d093, field not amended, binding verbatim): fold train_lt_2026's "
                "TEST-side treatment column is identically zero (measured: 0 playoff test rows; "
                "training support 106 playoff clusters); the arm's prediction reduces to the "
                "null's by construction; the fold contributes no discriminating information for "
                "pi. Effective evidence base: four evaluable folds (measured training playoff "
                "clusters 17/40/60/82/106, all >= 10). The fold remains evaluable and is merely "
                "recorded non-discriminating; there is no P27 hook for it (P35 "
                "test_side_support_note: no general test-side rule exists).",
                "D3 preserved disagreement, carried verbatim from P33 (NOT adjudicated by this "
                "module, travels with the arm per the P33 card's own text): 'the coldstart "
                "source excludes any new is_playoff_game term as fold-degenerate; the "
                "calibration source proposes it WITH the section-4 fallback. Both preserved; "
                "retention follows the packet's own S7 clause.'",
                "Feature construction (P33-carried, not amended by P35): is_playoff_game is a "
                "schedule indicator (season_type == 'Playoffs'), lineage "
                "possession_features.py line 318, an incumbent-carried column; S8 table: "
                "season_type ELIGIBLE ('schedule fact known at the cutoff').",
            ],
        }

    # ---- guards ------------------------------------------------------------------------------
    def lag_specs(self):
        return {
            TREATMENT_COL: {
                "column": TREATMENT_COL,
                "kind": "SCHEDULE",
                "source_artifact_id": "schedule_contract/1",
                "entity_keys": ("game_id",),
                "rationale": "playoff/regular-season status is a fact fixed by the published "
                            "schedule before tipoff (P22 LagSpec docstring names 'playoff flag' "
                            "explicitly as a SCHEDULE-kind example); P33-carried construction: "
                            "schedule indicator (season_type == 'Playoffs'), lineage "
                            "possession_features.py line 318, incumbent-carried column; S8 "
                            "table: season_type ELIGIBLE ('schedule fact known at the cutoff')",
            },
        }

    def lag_sources(self):
        return {}

    def preregistered_contrasts(self):
        return None

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self):
        return False

    def p23_receipts(self):
        return []

    def p27_rule(self):
        # No training-side P27 active-set rule is registered for A05 in the frozen card; the
        # only fallback is the descriptive test-side note carried in fold_local_fallback above.
        return None


# ---------------------------------------------------------------------------------- kill hooks
def evaluate_kill_conditions(per_fold_pi: dict) -> dict:
    """Mechanically decide the frozen A05 kill rule from per-fold training-cluster-bootstrap
    results for `pi` (P35 kill_conditions_frozen, UNCORRECTED per MULT B-5):

        KILLED if (a) the 95% training-cluster bootstrap interval for pi covers 0 in EVERY
        evaluable fold, OR (b) the sign of pi-hat is unstable across evaluable folds.

    `per_fold_pi`: {fold_id: {"lo": float|None, "hi": float|None, "beta": float}} -- normally
    fold_results[fid]["train_refit"]["arm_intervals"][TREATMENT_COL] plus the point estimate
    fold_results[fid]["point_fits"]["arm"]["beta"][idx_of(TREATMENT_COL)], gathered per
    evaluable fold only (STRUCTURALLY_DEACTIVATED / UNEVALUABLE folds excluded upstream).
    """
    folds = sorted(per_fold_pi)
    covers, signs = {}, {}
    for fid in folds:
        rec = per_fold_pi[fid]
        lo, hi, beta = rec.get("lo"), rec.get("hi"), rec.get("beta")
        covers[fid] = (lo is None or hi is None) or (lo <= 0.0 <= hi)
        signs[fid] = 0 if beta is None or beta == 0 else (1 if beta > 0 else -1)
    nonzero_signs = {s for s in signs.values() if s != 0}
    sign_unstable = len(nonzero_signs) > 1
    all_cover = bool(folds) and all(covers.values())
    killed = bool(all_cover or sign_unstable)
    basis = []
    if all_cover:
        basis.append("pi 95% training-cluster bootstrap interval covers 0 in every evaluable "
                     "fold")
    if sign_unstable:
        basis.append("pi-hat sign unstable across evaluable folds")
    if not basis:
        basis.append("pi interval excludes 0 in at least one evaluable fold; sign stable -- "
                     "not killed")
    return {"schema": "a05_kill_decision/1", "n_evaluable_folds": len(folds),
            "covers_zero": covers, "signs": signs, "all_cover_zero": all_cover,
            "sign_unstable": sign_unstable, "killed": killed, "basis": basis}
