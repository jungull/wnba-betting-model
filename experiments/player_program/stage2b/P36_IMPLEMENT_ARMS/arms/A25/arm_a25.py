#!/usr/bin/env python3
"""arm_a25.py -- P36 arm module for A25_home_offense_contrast.

FROZEN CARD THIS IMPLEMENTS (verbatim binding source): P35_FREEZE_TASK_CARDS/SPEC.json,
sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[arm_id ==
"A25_home_offense_contrast"], amending the P33_PREREGISTRATION_DRAFT/SPEC.json arm record
(sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) by hash reference per
the card's carry_convention. Every P33 field not named in the card's amendments_applied list is
carried verbatim and binding; nothing here is invented beyond what those two documents say.

MODEL (P35 task card, verbatim): "eta = log_exposure + beta * is_home_offense; mu = exp(eta); no
global intercept in arm or null; null has zero fitted parameters and IS the frozen incumbent".
(P33 formula, carried, unamended): "y ~ offset(log_exposure) + beta * is_home_offense (0/1; +/-1
coding affinely identical)" -- the 0/1 vs +/-1 remark is a coding-equivalence note, not a design
choice this module must resolve; the card's own formula and k0_matched_frozen both use the 0/1
form, so 0/1 is what this module materialises.

SINGLE ELEMENT: P33 hyperparameters.enumerated is empty ({}), handling "none; coding equivalence
is not a hyperparameter" -- A25 carries no enumeration grid. RUNNER_INTERFACE.md section 1: "{}
for single-element arms".

K0_MATCHED (P35 k0_matched_frozen, verbatim): arm_kind "substantive_feature" (NOT
calibration_only -- contrast with A02/A03/A05/A06, which the P35 intercept table's "consequence"
clause names by kind even though A25 is also listed there among the no-global-intercept arms
whose zero-parameter null equals the incumbent). null = "[log_exposure] identical everything;
excludes only the home term" (comparison: term_removal). tested_parameters: beta, role
coefficient, null_value 0, meaning "offset already prices home tempo". P35 intercept_structure's
"consequence" clause names A25 explicitly among {A02, A03, A05, A16, A25}: "the zero-parameter
nulls ... ARE the frozen incumbent exactly ... 'recovers the incumbent exactly' is literally true
for them."

FOLD_LOCAL_FALLBACK: P35/P33 "not_applicable - exactly 50/50 balanced within every fold by
construction (games never split)" -- games are never split across folds or cluster-bootstrap
draws (P36 scientific-state pin), so every fold that carries a game carries BOTH its home and
away team-game rows, and every game contributes exactly one row with is_home_offense=1 and one
with is_home_offense=0. No numeric trigger exists because the balance is a structural property of
the universe, not a data-dependent condition; there is no P27 active-set-rule registry entry for
A25 (only A03/A12/A13/A14 are registered -- P35 registry_append payloads).

FRANCHISE CONTINUITY: A25 is absent from P33 shared_arm_invariants.p23_franchise_continuity_
precondition's arm list (A08, A09, A10, A11, A12, A13, A14, A16, A17, A19, A21, A22, A24 -- A25
is not among them), and A25's own P33 record carries no "precondition" field at all. This tracks
the mechanism: is_home_offense is a same-game schedule fact, never a cross-season history lookup,
so it never touches the PHO/PHX cross-season rebrand issue the P23 receipt exists for.
requires_franchise_continuity() is therefore False and p23_receipts() returns [].

LAG DECLARATION: is_home_offense is declared SCHEDULE, not PRIOR_GAME or DERIVED_NO_JOIN -- P22's
own LagSpec docstring names "opponent, venue, playoff flag" as the canonical SCHEDULE examples
(see A05's identical SCHEDULE declaration for is_playoff_game); home/away assignment is exactly
the same kind of pre-tipoff schedule fact as venue. The P33 feature record's own construction
note -- "identity join (drop_duplicates) per the S8 hazard note - never a row aggregate" -- is
carried verbatim in lag_specs()'s rationale below; it documents that the join is a 1:1 identity
lookup on the schedule (never a possession- or game-log row aggregate), which is exactly the
posture SCHEDULE lag-kind re-derivation assumes and DERIVED_NO_JOIN or PRIOR_GAME would not fit.

GUARD POSITIVE CONTROL (P35 amendments_applied, verbatim): "GUARD POSITIVE CONTROL role
preserved verbatim (any guard declaring this arm UNEVALUABLE indicts the guard configuration, not
the arm)". P33 secondary_diagnostics carries the same clause from both preregistration sources.
A25 is the maximally simple, maximally supported design in the entire fit set (single pre-tipoff
0/1 schedule flag, no imputation, no fold-local fallback, all five folds evaluable by
construction) -- if any guard in the shared runner declares A25 UNEVALUABLE, that is evidence
against the guard's own configuration, not against this arm. This module records the note in
p26_k0_record()['notes'] and in TESTS_A25.py; it does not and cannot special-case any guard
(standing rule 3: enforcement lives at the call site, never inside a shared gate, and this module
owns no guard).

Epistemic status of this file: IMPLEMENTATION. Blinded: no challenger performance is inspected
here or anywhere in this module. Only unit, synthetic, identity and schema tests exist for it
(tests/TESTS_A25.py in this directory).

Ownership: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A25/ ONLY. This module
imports the frozen RUNNER_INTERFACE.md contract (runner/*.py) but never writes to runner/ or to
any other arm's directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
_RUNNER = _HERE.parents[1] / "runner"          # stage2b/P36_IMPLEMENT_ARMS/runner -- READ ONLY
for _p in (str(_RUNNER), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import runner_constants as rc                     # noqa: E402  (frozen; imported, never edited)

ARM_ID = "A25_home_offense_contrast"
P35_SPEC_SHA256 = rc.P35_SPEC_SHA256

SOURCE_COL = "is_home_offense"      # raw pre-tipoff schedule flag on the input universe
TREATMENT_COL = "is_home_offense"   # materialised 0.0/1.0 design column; card's own name, no
                                    # registered-name reconciliation is needed (contrast A02)


def _sidespec(fold_ids) -> dict:
    return {
        "intercept_treatment": ("none -- no global intercept in arm or null (P35 intercept_"
                                "structure: A25 in ARMS_WITHOUT_GLOBAL_INTERCEPT)"),
        "calibration_freedom": "none -- beta is a single fixed-shape indicator coefficient, no "
                               "post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{rc.OFFSET_COL} = log({rc.INCUMBENT_PROJECTION_COL}), frozen "
                           "incumbent D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": "fold train_idx, per the runner's per-fold split",
        "evaluation_rows": "fold test_idx, per the runner's per-fold split",
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": "none beyond 0.0/1.0 casting of the raw schedule flag",
        "missing_value_handling": "none -- is_home_offense is a complete-case schedule fact "
                                  "(identity join, drop_duplicates, per the S8 hazard note -- "
                                  "never a row aggregate), fixed at schedule-publication time, "
                                  "never missing pre-tipoff",
        "companion_components": "none",
        "fallback_rules": "none -- P33/P35 fold_local_fallback is not_applicable: is_home_"
                          "offense is exactly 50/50 balanced within every fold by construction "
                          "(games are never split across folds or cluster-bootstrap draws, and "
                          "every game contributes exactly one home row and one away row); no "
                          "P27 active-set rule is registered for A25",
        "aggregation": "none -- the unit of prediction is the team-game row",
        "candidate_universe": "the arm's declared team-game universe (frozen 2,982-row real "
                              "universe at P38; synthetic fixture rows in P36 tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A25Arm:
    """The single A25 module instance (no enumerated grid; RUNNER_INTERFACE.md section 1: '{}
    for single-element arms')."""

    arm_id = ARM_ID

    def __init__(self, fold_ids):
        self._fold_ids = [str(f) for f in fold_ids]

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return rc.DECLARED_FAMILY_ALL_FITTED_ARMS            # "SUBSTANTIVE" (P35 pinned)

    def recalibration_declaration(self) -> str:
        return rc.RECALIBRATION_DECLARATION                  # "NOT_APPLICABLE" (P35 pinned)

    def enumeration_element(self) -> dict:
        return {}                                             # single-element arm

    def element_id(self) -> str:
        return f"{ARM_ID}__single"

    def uses_global_intercept(self) -> bool:
        return False                                          # A25 in ARMS_WITHOUT_GLOBAL_INTERCEPT

    def requires_franchise_continuity(self) -> bool:
        # A25 is absent from P33 shared_arm_invariants.p23_franchise_continuity_precondition's
        # arm list, and A25's own P33 record carries no "precondition" field at all. is_home_
        # offense is a same-game schedule fact -- it never crosses a season boundary and never
        # touches the PHO/PHX cross-season rebrand issue the P23 receipt exists for.
        return False

    def p23_receipts(self) -> list:
        return []

    def p27_rule(self):
        # No S7 active-set-rule registry entry names A25 (only A03, A12, A13, A14 do, per the
        # P35 registry_append payloads). No rule is frozen for A25 at P35: the fold_local_
        # fallback is a structural "not_applicable" note, not a P27 hook.
        return None

    def preregistered_contrasts(self):
        # A25 carries no P25-preregistered contrast record (that obligation is A02's alone --
        # P35 p25_guard_invocation_pins.a02_contrast_reconciliation).
        return None

    def prereg_digest_expected(self):
        return None

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe) -> dict:
        """Deterministic pass-through of the pre-tipoff home/away schedule flag. No fold-computed
        constant exists for this arm: the treatment column is identical across every fold and
        across repeated calls on the same universe (feature determinism), exactly like A05's
        is_playoff_game pass-through."""
        del fold  # signature-required, unused: is_home_offense is not fold-dependent
        if SOURCE_COL not in universe.columns:
            raise KeyError(f"A25 build_design requires column '{SOURCE_COL}' on the universe frame")
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

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": (
                    "home offenses play marginally faster than the frozen offset prices; beta "
                    "is a pure within-cluster contrast (every game contributes one home row and "
                    "one away row, so the treatment is exactly 50/50 balanced within every fold "
                    "by construction) testing whether a residual home-tempo effect survives "
                    "beyond what the incumbent's own possession-count offset already carries"),
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{
                    "name": "beta", "role": "coefficient", "null_value": 0.0,
                    "null_value_meaning": "offset already prices home tempo",
                }],
                "claimed_signal_axes": ["venue"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        "removing is_home_offense leaves eta = log_exposure exactly -- the "
                        "null IS the frozen incumbent exactly, zero fitted parameters (P35 "
                        "intercept_structure names A25 explicitly among the zero-parameter-"
                        "null arms whose null 'recovers the incumbent exactly' literally)"),
                },
            },
            "invariants": {
                "rows": "the arm's declared team-game universe (see side.candidate_universe)",
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": list(self._fold_ids),
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": [],
                "lower_order_structural_terms": [],
            },
            "arm_spec": _side("A25_arm", "challenger", [TREATMENT_COL], [], side),
            "k0_spec": _side("A25_k0", "k0", [], [], side),
            "fold_local_fallback": {
                "required": False,
                "trigger": "not_applicable -- exactly 50/50 balanced within every fold by "
                          "construction (games never split)",
                "numeric_threshold": None,
                "action": "not_applicable",
                "registered_before_results": True,
            },
            "verdict_label_policy": "eligible for FEATURE VALUE DEMONSTRATED via "
                                    "challenger_vs_k0 against this record (arm_kind "
                                    "substantive_feature; NOT calibration_only, so no "
                                    "verdict-label ceiling applies)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "P35 shared_frozen_amendments.multiplicity_recomputed.families_this_cycle: "
                "schedule_context_family, members {A23: 2, A25: 1}, budget_elements 3, Holm "
                "alpha 0.05.",
                "GUARD POSITIVE CONTROL role (P33 secondary_diagnostics AND P35 "
                "amendments_applied, both verbatim): if ANY guard in the shared runner "
                "declares A25 UNEVALUABLE, that indicts the guard configuration, not the arm "
                "-- A25 is the maximally simple, maximally supported design in the fit set.",
                "Feature construction (P33-carried, not amended by P35): is_home_offense is "
                "built by an identity join (drop_duplicates) per the S8 hazard note -- never a "
                "row aggregate; lineage: schedule-determined home/away mapping; S8 table: "
                "ELIGIBLE ('schedule-determined and known pregame').",
                "Expected failure mode, stated before any fit (P33, carried verbatim): high "
                "prior probability of a covered-zero interval, whose preregistered "
                "interpretation is a GENUINE NULL certifying the offset already prices home "
                "tempo -- accepted, not a defect if it occurs (standing rule 7).",
            ],
        }

    # ---- guards -----------------------------------------------------------------------
    def lag_specs(self) -> dict:
        return {
            TREATMENT_COL: {
                "column": TREATMENT_COL,
                "kind": "SCHEDULE",
                "source_artifact_id": "schedule_contract/1",
                "entity_keys": ("game_id",),
                "rationale": "home/away assignment is a fact fixed by the published schedule "
                            "before tipoff (P22 LagSpec docstring names 'opponent, venue, "
                            "playoff flag' as the canonical SCHEDULE examples; home/away is the "
                            "same kind of pre-tipoff schedule fact as venue). P33-carried "
                            "construction: identity join (drop_duplicates) per the S8 hazard "
                            "note -- never a row aggregate; lineage: schedule-determined "
                            "home/away mapping; S8 table: ELIGIBLE ('schedule-determined and "
                            "known pregame').",
            },
        }

    def lag_sources(self) -> dict:
        return {}


def _side(name: str, role: str, substantive: list, structural: list, dims: dict) -> dict:
    import copy
    return {
        "name": name, "role": role, "pipeline_id": rc.RUNNER_VERSION,
        "substantive_features": list(substantive), "structural_terms": list(structural),
        "declaration_routing": {t: "substantive_features" for t in substantive},
        "comparison_gate_sidespec": copy.deepcopy(dims),
    }


def make_arm(fold_ids) -> list:
    """One module instance -- A25 has no enumerated grid (RUNNER_INTERFACE.md section 1: '{}
    for single-element arms'). Returned as a length-1 list for interface symmetry with
    A08/A09/A11's `make_arms`."""
    return [A25Arm(fold_ids)]


# ---------------------------------------------------------------------------------- kill hooks
def evaluate_kill_conditions(per_fold_beta: dict) -> dict:
    """Mechanically decide the frozen A25 kill rule from per-fold training-cluster-bootstrap
    results for `beta` (P35/P33 kill_conditions_frozen, verbatim):

        "cluster-resampled interval for beta covers 0 (GENUINE NULL - preregistered
        interpretation: the offset already prices home tempo)"

    Unlike most other arms' cards, A25's kill condition names NO sign-instability clause and NO
    UNCORRECTED-family caveat (A25 was never in CALIBRATION_CONTROL_FAMILY, so MULT B-5's
    "family-corrected" strike does not apply to it -- A25 sits in schedule_context_family and is
    Holm-corrected at the PRIMARY GATE as usual; this function decides only the single frozen
    kill clause, verbatim, nothing added or removed).

    `per_fold_beta`: {fold_id: {"lo": float|None, "hi": float|None, "beta": float}} -- normally
    fold_results[fid]["train_refit"]["arm_intervals"][TREATMENT_COL] plus the point estimate
    fold_results[fid]["point_fits"]["arm"]["beta"][idx_of(TREATMENT_COL)], gathered per
    evaluable fold only (UNEVALUABLE folds excluded upstream; A25 has no structurally
    deactivated fold).
    """
    folds = sorted(per_fold_beta)
    covers = {}
    for fid in folds:
        rec = per_fold_beta[fid]
        lo, hi = rec.get("lo"), rec.get("hi")
        covers[fid] = (lo is None or hi is None) or (lo <= 0.0 <= hi)
    all_cover = bool(folds) and all(covers.values())
    killed = bool(all_cover)
    basis = []
    if all_cover:
        basis.append("beta 95% training-cluster bootstrap interval covers 0 in every evaluable "
                     "fold -- GENUINE NULL, preregistered interpretation: the offset already "
                     "prices home tempo")
    else:
        basis.append("beta interval excludes 0 in at least one evaluable fold -- not killed")
    return {"schema": "a25_kill_decision/1", "n_evaluable_folds": len(folds),
            "covers_zero": covers, "all_cover_zero": all_cover, "killed": killed, "basis": basis}
