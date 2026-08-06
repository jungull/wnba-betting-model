#!/usr/bin/env python3
"""arm.py -- A10_recency_contrast, the P36 RUNNER_INTERFACE arm module.

Frozen card: experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards[A10],
amended by shared_frozen_amendments (intercept_structure, construction_pins,
multiplicity_recomputed.grid_element_regime_pinned, franchise_continuity_receipt_pin).

  model:  log E[y] = log_exposure + beta0*d_t + beta1*c_t
          c_t = ewma_lambda{pace(j) - Lbar_<j} - d_t; no global intercept
  K0_MATCHED[A10]: [log_exposure | d_t] -- lambda-free, shared by BOTH lambda elements;
          comparison = term_removal of c_t
  elements: lambda in {0.2, 0.5}, EACH fitted end-to-end as its own module instance
          (RUNNER_INTERFACE.md section 1: one arm-module instance binds exactly one
          enumeration element; the runner never selects among elements)

Per standing rule 3 (enforcement at the call site, never editing a shared gate) and this unit's
write scope (experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A10/ only), this module
imports the FROZEN runner contract (runner_constants, for the pinned column names, the frozen
intercept table and the frozen team_cities.csv hash) but writes nothing outside its own
directory and edits nothing under runner/.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

from feature_construction import ENUMERATED_LAMBDA, align_n_t_d_t_c_t_by_key
from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TEAM_CITIES_SHA256_PIN

ARM_ID = "A10_recency_contrast"

#: the card's own generic term names -- reused VERBATIM as the design's column keys and as the
#: K0_MATCHED treatment_terms/substantive_features entry, rather than inventing a fresh naming
#: scheme, per "implement EXACTLY it" / "never improvise".
NUISANCE_COL = "d_t"
TREATMENT_COL = "c_t"


def _row_digest(n: int) -> str:
    return f"rows:n={n}:contract_schedule_or_synthetic"


def _sidespec(fold_ids, n_rows, lam: float) -> dict:
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
        "preprocessing": ("d_t := 0 and c_t := 0 when n_t == 0 (P35 A10 empty-window rule, "
                          "deterministic and symmetric, arm and null identical); "
                          "pace(j) = n_off_poss*40/(40+5*max(0,max_period-4)) "
                          "(lagged_regulation_equivalent_pin); Lbar_<g is the all-prior, K-free "
                          "league mean of that pace (d_t_league_mean_pin), shared byte-identical "
                          f"with A08/A09; c_t = ewma_lambda{{pace(j)-Lbar_<j}} - d_t, lambda="
                          f"{lam} fixed, standard recursive EWMA over the team's own strictly-"
                          "prior games ordered (game_date, game_id)"),
        "missing_value_handling": "none beyond the empty-window rule above (complete-case "
                                  "otherwise)",
        "companion_components": "none",
        "fallback_rules": "d_t := 0 and c_t := 0 at n_t == 0, identical in arm and null (no "
                          "fold-level collapse; a row-level deterministic imputation, not a "
                          "partition indicator)",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the contract-schedule team-game universe (synthetic in tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A10Arm:
    """One A10 module instance == one lambda element."""

    arm_id = ARM_ID

    def __init__(self, lam: float, fold_ids, n_rows: int):
        if lam not in ENUMERATED_LAMBDA:
            raise ValueError(f"lambda={lam} is not one of the frozen P35 elements "
                             f"{ENUMERATED_LAMBDA}")
        self.lam = float(lam)
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
        return {"lambda": self.lam}

    def element_id(self) -> str:
        return f"A10_lambda{self.lam}"

    def uses_global_intercept(self) -> bool:
        return False

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe) -> dict:
        """d_t/c_t are NOT fold-dependent constants (unlike e.g. A13's cbar_F): they are
        deterministic functions of schedule facts strictly earlier than each row's own game, so
        `fold` is accepted (per the frozen §3 contract) but not consulted for their construction.
        The supplied `universe` frame IS the contract-schedule history: every row is
        simultaneously a target row (its own n_t/d_t/c_t are returned) and, for later rows, part
        of the prior-game evidence -- this is the K-free, all-prior construction the card pins
        for d_t, and the recency-weighted variant of the same prior evidence for c_t. No external
        join / lag_sources() frame is needed (see lag_specs() below).
        """
        for col in ("team_id", "game_id", "game_date", "n_off_poss", "max_period"):
            if col not in universe.columns:
                raise KeyError(f"A10 build_design requires column '{col}' on the universe frame")
        n_t, d_t, c_t = align_n_t_d_t_c_t_by_key(universe, universe, self.lam,
                                                  key_cols=("team_id", "game_id"))

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {NUISANCE_COL: d_t, TREATMENT_COL: c_t},
        }

    # ---- P26 ------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids, self._n_rows, self.lam)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "Within-window recency information: c_t contrasts a "
                             "recency-weighted (EWMA, lambda fixed per element) reading of the "
                             "team's own prior-vs-league pace deviation against the flat "
                             "(unweighted, all-prior) reading d_t already carried as a nuisance "
                             "term; beta1 tests whether the extra recency weighting carries "
                             "information beyond the flat window.",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "beta1", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "flat window sufficient -- no "
                                                             "additional recency information "
                                                             "beyond the flat beta0*d_t term"}],
                "claimed_signal_axes": ["league_time"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": "removing c_t collapses the design to the flat, "
                                               "recency-agnostic beta0*d_t term the null shares "
                                               "with the arm; no recency-weighted signal remains "
                                               "distinguishable from d_t under the null"}},
            "invariants": {
                "rows": _row_digest(self._n_rows),
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": "d_t := 0 and c_t := 0 at n_t == 0, identical arm and "
                                      "null (P35 A10 card fold_local_fallback)",
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
            "verdict_label_policy": "substantive_feature arm: eligible for a feature_value "
                                    "verdict ONLY against K0_MATCHED[A10] for this lambda "
                                    "element, subject to the primary gate and the "
                                    "timeseries_shrinkage family Holm correction (10 elements); "
                                    "K0_FLAT carries no promotion value whatsoever "
                                    "(k0_flat_role diagnostic_only)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
        }

    # ---- guards -----------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale = (
            "d_t and c_t are built by feature_construction.py from the supplied universe "
            "frame's OWN rows (n_off_poss, max_period, team_id, game_date, game_id), restricted "
            "per-row to strictly-earlier game_date entries only (P35 d_t_league_mean_pin / "
            "n_clock_pin, all-prior and K-free for d_t; the same strictly-prior restriction, "
            "recency-reweighted, for c_t). No external artifact join is performed by this "
            "module -- the universe frame IS the contract-schedule history -- so this is a "
            "DERIVED_NO_JOIN construction, not a PRIOR_GAME single-column shift; "
            "postgame_surrogate_guard's generic PRIOR_GAME re-derivation (a groupby+shift(n_back) "
            "check) verifies single-step lags and cannot verify an all-prior expanding "
            "aggregate or its EWMA reweighting, so it is not the correct declared kind here. "
            "Strict lagging is instead established directly by identity/synthetic tests in this "
            "unit (TESTS.py) against feature_construction.py's pure functions: a row's "
            "d_t/c_t/n_t are shown to be invariant to perturbing its OWN game outcome and to "
            "perturbing any LATER game."
        )
        return {
            NUISANCE_COL: {"column": NUISANCE_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "contract_schedule_universe/1",
                           "rationale": rationale},
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "contract_schedule_universe/1",
                            "rationale": rationale + f" lambda={self.lam} is a fixed constant "
                                        "of this module instance, never fitted."},
        }

    def lag_sources(self) -> dict:
        return {}                       # DERIVED_NO_JOIN needs no external re-derivation source

    def preregistered_contrasts(self):
        return None

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 p23_franchise_continuity_precondition names A10 explicitly: d_t/c_t are
        # cross-season (all-prior) history features, so the PHO/PHX rebrand receipt is required
        # before gate invocation for ANY cross-season history feature, regardless of this
        # module's own team_id-keyed (no team_cities join) construction.
        return True

    def p23_receipts(self) -> list:
        return [{
            "team_cities_sha256": TEAM_CITIES_SHA256_PIN,
            "scope": "A10: d_t/c_t are keyed directly on team_id across seasons; no "
                    "team_cities.csv join is performed by this module. This receipt attests the "
                    "frozen franchise-continuity pin per P35 franchise_continuity_receipt_pin / "
                    "the P33 p23_franchise_continuity_precondition naming A10.",
        }]

    def p27_rule(self):
        # No S7 active-set-rule registry entry names A10 in P35 registry_append (only A03, A12,
        # A13, A14 do); A10's own fold_local_fallback is a row-level deterministic imputation,
        # not an S7 tier/partition rule, so there is nothing to register here.
        return None


def make_arms(fold_ids, n_rows) -> list[A10Arm]:
    """One module instance per frozen enumeration element (lambda in {0.2, 0.5}); the runner
    never selects among them (RUNNER_INTERFACE.md section 1)."""
    return [A10Arm(lam, fold_ids, n_rows) for lam in ENUMERATED_LAMBDA]
