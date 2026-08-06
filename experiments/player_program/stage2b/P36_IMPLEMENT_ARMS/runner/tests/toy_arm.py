#!/usr/bin/env python3
"""toy_arm.py -- a synthetic arm module implementing the frozen RUNNER_INTERFACE contract.

Not a P35 card. Exists so the shared runner can be exercised end-to-end on synthetic data
without touching any real fold. Shape: one continuous treatment (x_toy), one indicator
nuisance (z_ind), term_removal null, no global intercept.
"""
from __future__ import annotations

import numpy as np

from runner_constants import OFFSET_COL, TARGET_COL_REAL


def _row_digest(n: int) -> str:
    return f"rows:n={n}:synthetic_fixture"


def _sidespec(fold_ids, n_rows):
    return {
        "intercept_treatment": "none -- no global intercept in arm or null",
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{OFFSET_COL} = log(projected_team_off_possessions) [synthetic]",
        "training_rows": _row_digest(n_rows),
        "evaluation_rows": _row_digest(n_rows),
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": "none -- raw synthetic columns",
        "missing_value_handling": "none -- complete case synthetic frame",
        "companion_components": "none",
        "fallback_rules": "none -- synthetic complete-case",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "synthetic team-game rows",
        "post_processing": "none",
        "prediction_universe": "synthetic team-game rows",
    }


class ToyArm:
    arm_id = "TOY_synthetic_arm"

    def __init__(self, fold_ids, n_rows):
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows)

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self):
        return self.arm_id

    def declared_family(self):
        return "SUBSTANTIVE"

    def recalibration_declaration(self):
        return "NOT_APPLICABLE"

    def enumeration_element(self):
        return {}

    def element_id(self):
        return "TOY_synthetic_arm__single"

    def uses_global_intercept(self):
        return False

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe):
        return {
            "treatment_cols": ["x_toy"],
            "nuisance_cols": ["z_ind"],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": ["z_ind"],
                                  "comparison": "term_removal"},
            "indicator_cols": ["z_ind"],
            "columns": {"x_toy": universe["x_toy"].to_numpy(float),
                        "z_ind": universe["z_ind"].to_numpy(float)},
        }

    # ---- P26 ------------------------------------------------------------------------
    def p26_k0_record(self):
        side = _sidespec(self._fold_ids, self._n_rows)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "synthetic toy treatment: a continuous per-row covariate carries "
                             "log-linear signal beyond the synthetic offset",
                "treatment_terms": ["x_toy"],
                "tested_parameters": [{"name": "beta_x", "role": "coefficient",
                                       "null_value": 0,
                                       "null_value_meaning": "no synthetic effect"}],
                "claimed_signal_axes": ["possession_observation"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": "removing x_toy leaves the synthetic offset "
                                               "plus the z_ind nuisance, in which the "
                                               "synthetic per-row signal never appears"}},
            "invariants": {
                "rows": _row_digest(self._n_rows),
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": "none -- synthetic complete-case",
                "nuisance_terms": ["z_ind"],
                "lower_order_structural_terms": []},
            "arm_spec": {
                "name": "arm", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": ["x_toy"],
                "structural_terms": ["z_ind"],
                "declaration_routing": {"x_toy": "substantive_features",
                                        "z_ind": "preprocessing"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "k0", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": ["z_ind"],
                "declaration_routing": {"z_ind": "preprocessing"},
                "comparison_gate_sidespec": side},
            "fold_local_fallback": {"required": False,
                                    "trigger": "not_applicable -- no partition term",
                                    "numeric_threshold": None,
                                    "action": "not_applicable",
                                    "registered_before_results": True},
            "verdict_label_policy": "synthetic test arm: eligible for no verdict label at all; "
                                    "exists only to exercise the shared runner",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
        }

    # ---- guards ---------------------------------------------------------------------
    def lag_specs(self):
        return {
            "x_toy": {"column": "x_toy", "kind": "DERIVED_NO_JOIN",
                      "source_artifact_id": "synthetic_fixture/1",
                      "rationale": "synthetic covariate drawn independently of any outcome"},
            "z_ind": {"column": "z_ind", "kind": "SCHEDULE",
                      "source_artifact_id": "synthetic_fixture/1",
                      "rationale": "synthetic pre-tipoff schedule-style indicator"},
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
        return None


class ToyArmWithIntercept(ToyArm):
    """Intercept-carrying variant used by the intercept-invariant tests (still synthetic)."""

    arm_id = "TOY_synthetic_arm_intercept"

    def element_id(self):
        return "TOY_synthetic_arm_intercept__single"

    def uses_global_intercept(self):
        return True

    def p26_k0_record(self):
        rec = super().p26_k0_record()
        rec["arm_id"] = self.arm_id
        label = "free unpenalised single intercept, explicit column, identical arm and null"
        rec["arm_spec"]["comparison_gate_sidespec"]["intercept_treatment"] = label
        rec["k0_spec"]["comparison_gate_sidespec"]["intercept_treatment"] = label
        return rec

    def build_design(self, fold, universe):
        b = super().build_design(fold, universe)
        b["nuisance_cols"] = ["z_ind", "intercept"]
        b["k0_matched_design"]["nuisance_cols"] = ["z_ind", "intercept"]
        b["columns"]["intercept"] = np.ones(len(universe))
        return b
