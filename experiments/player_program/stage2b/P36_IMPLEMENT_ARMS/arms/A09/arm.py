#!/usr/bin/env python3
"""arm.py -- A09_evidence_depth_adaptive_shrinkage, the P36 RUNNER_INTERFACE arm module.

Frozen card: experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards[A09],
amended by shared_frozen_amendments (intercept_structure, construction_pins,
multiplicity_recomputed.grid_element_regime_pinned, franchise_continuity_receipt_pin).

  model:  log E[y] = log_exposure + beta0*d_t + beta*((w(n_t; kappa) - 1)*d_t)
          w(n) = n / (n + kappa);  no global intercept
  K0_MATCHED[A09]: [log_exposure | d_t] with w == 1 (beta0 free), shared by all three kappa
          elements; comparison = term_removal of the adaptive-vs-flat contrast, per element
  elements: kappa in {2, 10, 50}, EACH fitted end-to-end as its own module instance
          (RUNNER_INTERFACE.md section 1: one arm-module instance binds exactly one
          enumeration element; the runner never selects among elements)

Per standing rule 3 (enforcement at the call site, never editing a shared gate) and this unit's
write scope (experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A09/ only), this module
imports the FROZEN runner contract (runner_constants, for the pinned column names, the frozen
intercept table and the frozen team_cities.csv hash) but writes nothing outside its own
directory and edits nothing under runner/.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np

from feature_construction import ENUMERATED_KAPPA, align_n_t_d_t_by_key, kappa_contrast
from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TEAM_CITIES_SHA256_PIN

ARM_ID = "A09_evidence_depth_adaptive_shrinkage"

#: the card's own generic (kappa-symbolic) term names -- reused VERBATIM as the design's column
#: keys and as the K0_MATCHED treatment_terms/substantive_features entry, rather than inventing
#: a fresh naming scheme, per "implement EXACTLY it" / "never improvise".
NUISANCE_COL = "d_t"
TREATMENT_COL = "(w(n_t; kappa) - 1)*d_t"


def _row_digest(n: int) -> str:
    return f"rows:n={n}:contract_schedule_or_synthetic"


def _sidespec(fold_ids, n_rows) -> dict:
    return {
        "intercept_treatment": "none -- no global intercept in arm or null (P35 intercept_structure)",
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{OFFSET_COL} = log({INCUMBENT_PROJECTION_COL}), frozen incumbent "
                           "D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": _row_digest(n_rows),
        "evaluation_rows": _row_digest(n_rows),
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": ("d_t := 0 when n_t == 0 (P35 A09 empty-window rule, deterministic and "
                          "symmetric, arm and null identical); pace(j) = n_off_poss*40/"
                          "(40+5*max(0,max_period-4)) (lagged_regulation_equivalent_pin); Lbar_<g "
                          "is the all-prior, K-free league mean of that pace (d_t_league_mean_pin)"),
        "missing_value_handling": "none beyond the empty-window rule above (complete-case "
                                  "otherwise)",
        "companion_components": "none",
        "fallback_rules": "d_t := 0 at n_t == 0, identical in arm and null (no fold-level "
                          "collapse; a row-level deterministic imputation, not a partition "
                          "indicator)",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the contract-schedule team-game universe (synthetic in tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A09Arm:
    """One A09 module instance == one kappa element."""

    arm_id = ARM_ID

    def __init__(self, kappa: int, fold_ids, n_rows: int):
        if kappa not in ENUMERATED_KAPPA:
            raise ValueError(f"kappa={kappa} is not one of the frozen P35 elements "
                             f"{ENUMERATED_KAPPA}")
        self.kappa = int(kappa)
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
        return {"kappa": self.kappa}

    def element_id(self) -> str:
        return f"A09_kappa{self.kappa}"

    def uses_global_intercept(self) -> bool:
        return False

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe) -> dict:
        """d_t/n_t are NOT fold-dependent constants (unlike e.g. A13's cbar_F): they are
        deterministic functions of schedule facts strictly earlier than each row's own game, so
        `fold` is accepted (per the frozen §3 contract) but not consulted for their construction.
        The supplied `universe` frame IS the contract-schedule history: every row is
        simultaneously a target row (its own n_t/d_t are returned) and, for later rows, part of
        the prior-game evidence -- this is the K-free, all-prior construction the card pins, and
        it is why no external join / lag_sources() frame is needed (see lag_specs() below).
        """
        for col in ("team_id", "game_id", "game_date", "n_off_poss", "max_period"):
            if col not in universe.columns:
                raise KeyError(f"A09 build_design requires column '{col}' on the universe frame")
        n_t, d_t = align_n_t_d_t_by_key(universe, universe, key_cols=("team_id", "game_id"))
        contrast = kappa_contrast(n_t, d_t, self.kappa)

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {NUISANCE_COL: d_t, TREATMENT_COL: contrast},
        }

    # ---- P26 ------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids, self._n_rows)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "hierarchical_pooling",
            "treatment_mechanism": {
                "statement": "Evidence-depth adaptive shrinkage: the flat prior-vs-league pace "
                             "deviation d_t should be pooled toward zero more aggressively when "
                             "a team has few completed prior games (n_t small, thin evidence) "
                             "and allowed to act at nearer full strength as evidence "
                             "accumulates; kappa sets the evidence depth at which the pooling "
                             "weight w(n)=n/(n+kappa) reaches one half.",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "beta", "role": "pooling_strength",
                                       "null_value": 0,
                                       "null_value_meaning": "flat weighting sufficient -- no "
                                                             "adaptive shrinkage beyond the "
                                                             "flat beta0*d_t term"}],
                "claimed_signal_axes": ["support_size"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": "removing the adaptive-vs-flat contrast column "
                                               "collapses w(n;kappa) to the constant 1 for every "
                                               "row, i.e. the evidence-depth-dependent pooling "
                                               "weight is destroyed identically across every "
                                               "n_t stratum, leaving only the flat, "
                                               "depth-independent beta0*d_t term the null "
                                               "shares with the arm"}},
            "invariants": {
                "rows": _row_digest(self._n_rows),
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": "d_t := 0 at n_t == 0, identical arm and null (P35 A09 "
                                      "card fold_local_fallback)",
                "nuisance_terms": [NUISANCE_COL],
                "lower_order_structural_terms": [NUISANCE_COL]},
            "arm_spec": {
                "name": "arm", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [TREATMENT_COL],
                "structural_terms": [NUISANCE_COL],
                "declaration_routing": {TREATMENT_COL: "substantive_features",
                                        NUISANCE_COL: "preprocessing"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "k0", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": [NUISANCE_COL],
                "declaration_routing": {NUISANCE_COL: "preprocessing"},
                "comparison_gate_sidespec": side},
            "fold_local_fallback": {
                "required": False,
                "trigger": "n_t == 0 (row-level empty-window imputation, not a fold-partition "
                          "indicator; R10's tier/level/fallback-name trigger does not apply "
                          "since no structural term here is a partition indicator)",
                "numeric_threshold": 0,
                "action": "not_applicable",
                "registered_before_results": True},
            "verdict_label_policy": "hierarchical_pooling result: eligible for a "
                                    "POOLING/SHRINKAGE mechanism verdict against "
                                    "K0_MATCHED[A09] for this kappa element, subject to the "
                                    "primary gate and the timeseries_shrinkage family Holm "
                                    "correction (10 elements); never a standalone 'feature "
                                    "value' claim absent that gate.",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
        }

    # ---- guards -----------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale = (
            "d_t and its per-kappa contrast are built by feature_construction.py from the "
            "supplied universe frame's OWN rows (n_off_poss, max_period, team_id, game_date), "
            "restricted per-row to strictly-earlier game_date entries only (P35 "
            "d_t_league_mean_pin / n_clock_pin, all-prior and K-free). No external artifact join "
            "is performed by this module -- the universe frame IS the contract-schedule history "
            "-- so this is a DERIVED_NO_JOIN construction, not a PRIOR_GAME single-column shift; "
            "postgame_surrogate_guard's generic PRIOR_GAME re-derivation (a groupby+shift(n_back) "
            "check) verifies single-step lags and cannot verify an all-prior expanding "
            "aggregate, so it is not the correct declared kind here. Strict lagging is instead "
            "established directly by identity/synthetic tests in this unit (TESTS.py) against "
            "feature_construction.py's pure functions: a row's d_t/n_t are shown to be invariant "
            "to perturbing its OWN game outcome and to perturbing any LATER game."
        )
        return {
            NUISANCE_COL: {"column": NUISANCE_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "contract_schedule_universe/1",
                           "rationale": rationale},
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "contract_schedule_universe/1",
                            "rationale": rationale + f" kappa={self.kappa} is a fixed constant "
                                        "of this module instance, never fitted."},
        }

    def lag_sources(self) -> dict:
        return {}                       # DERIVED_NO_JOIN needs no external re-derivation source

    def preregistered_contrasts(self):
        return None

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 p23_franchise_continuity_precondition names A09 explicitly: d_t is a cross-season
        # (all-prior) history feature, so the PHO/PHX rebrand receipt is required before gate
        # invocation for ANY cross-season history feature, regardless of this module's own
        # team_id-keyed (no team_cities join) construction.
        return True

    def p23_receipts(self) -> list:
        return [{
            "team_cities_sha256": TEAM_CITIES_SHA256_PIN,
            "scope": "A09: d_t is keyed directly on team_id across seasons; no team_cities.csv "
                    "join is performed by this module. This receipt attests the frozen "
                    "franchise-continuity pin per P35 franchise_continuity_receipt_pin / the "
                    "P33 p23_franchise_continuity_precondition naming A09.",
        }]

    def p27_rule(self):
        # No S7 active-set-rule registry entry names A09 in P35 registry_append (only A03, A12,
        # A13, A14 do); A09's own fold_local_fallback is a row-level deterministic imputation,
        # not an S7 tier/partition rule, so there is nothing to register here.
        return None


def make_arms(fold_ids, n_rows) -> list[A09Arm]:
    """One module instance per frozen enumeration element (kappa in {2, 10, 50}); the runner
    never selects among them (RUNNER_INTERFACE.md section 1)."""
    return [A09Arm(k, fold_ids, n_rows) for k in ENUMERATED_KAPPA]
