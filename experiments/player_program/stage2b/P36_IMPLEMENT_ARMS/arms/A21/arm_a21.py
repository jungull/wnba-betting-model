#!/usr/bin/env python3
"""arm_a21.py -- A21_garbage_time_contamination arm module, RUNNER_INTERFACE.md conformant.

Card: P35_FREEZE_TASK_CARDS/SPEC.json (sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards.A21, carrying P33
PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072
d347d093) arm A21 by hash reference, amended exactly by the card's amendments_applied list.

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A21/ only. This module
IMPORTS the frozen runner contract (runner_constants) READ-ONLY, to build conformant records; it
edits nothing under runner/.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

MODEL (frozen, card-pinned, task_cards.A21.model verbatim):
    eta = log_exposure + [A17-null nuisance] + coef * x
    x   = (nc(t,g) + nc(opp(g,t),g)) / 2
    mu  = exp(eta)
    NO global intercept (P35 intercept_structure table: A21 in ARMS_WITHOUT_GLOBAL_INTERCEPT).

K0_MATCHED[A21] (frozen, card k0_matched_frozen): "identical to A17's null; K0 granted NO
re-weighting of its evidence -- the arm must show the correction as an additive term". A17's own
frozen null (P35 task_cards.A17.k0_matched_frozen) is "identical machinery plus nuisance incl.
is_playoff_game ... treatment adds ONLY x" -- i.e. A17's null is [log_exposure | is_playoff_game].
A21 carries that SAME single nuisance term (no A17 treatment column, since A17's own treatment is
not part of A21's null): null = [log_exposure | is_playoff_game]. comparison: term_removal.
treatment_terms: ["x (contamination share)"]. tested_parameters: [{coef(x), coefficient, 0}].

Single enumeration element (P33 A21.hyperparameters.enumerated = {}; the two fixed decay constants
are NOT a grid) -- one module instance IS the whole arm (RUNNER_INTERFACE.md section 1: "{} for
single-element arms").

PRECONDITION (P33 A21 "precondition": "P23 franchise-continuity receipt"; A07_early_season_
transient.py's own docstring lists A21 among the arms this precondition names).

SECONDARY DIAGNOSTIC / KILL CONDITION (task_cards.A21.kill_conditions_frozen, verbatim): "null vs
K0; depth-absorption robustness check fails (x proxies evidence VOLUME - mechanism falsified even
on a positive naive test)". The robustness variant (adding pace_evidence_depth to the nuisance
set, P33 A21.primary_gate secondary_diagnostics) is a SEPARATE design, provided here as the
optional ``build_design_depth_robustness`` method -- outside the frozen RUNNER_INTERFACE contract
(build_design binds exactly one design per call), analogous to how A07 discloses its own
implementation choices beyond the strict interface. ``decide_kill`` below is the pure, decidable
function combining both frozen kill triggers.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_RUNNER = _HERE.parents[1] / "runner"          # stage2b/P36_IMPLEMENT_ARMS/runner -- READ ONLY
if str(_RUNNER) not in sys.path:
    sys.path.insert(0, str(_RUNNER))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import runner_constants as rc                   # noqa: E402  (frozen; imported, never edited)
import feature_construction as fc                # noqa: E402  (this unit's own module)

CARD_ID = "A21_garbage_time_contamination"
NUISANCE_COL = "is_playoff_game"          # A17's null, carried identically (K0_MATCHED[A21])
TREATMENT_COL = "x_garbage_time_contamination"
DEPTH_COL = "pace_evidence_depth"          # secondary robustness diagnostic column, P33 A21


class A21Arm:
    """One instance = the whole arm (no enumerated grid; P33 hyperparameters.enumerated={})."""

    arm_id = CARD_ID

    def __init__(self, possessions: pd.DataFrame, fold_ids=(), n_rows: int | None = None):
        missing = [c for c in fc.REQUIRED_POSSESSION_COLS if c not in possessions.columns]
        if missing:
            raise fc.A21ConstructionFailure(f"possessions frame missing required columns {missing}")
        self._possessions = possessions.reset_index(drop=True)
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows) if n_rows is not None else 0

    # ---- metadata hooks ------------------------------------------------------------------
    def card_id(self) -> str:
        return CARD_ID

    def declared_family(self) -> str:
        return rc.DECLARED_FAMILY_ALL_FITTED_ARMS          # "SUBSTANTIVE" (P35 pinned)

    def recalibration_declaration(self) -> str:
        return rc.RECALIBRATION_DECLARATION                # "NOT_APPLICABLE" (P35 pinned)

    def enumeration_element(self) -> dict:
        return {}                                          # single-element arm

    def element_id(self) -> str:
        return "A21_garbage_time_contamination__single"

    def uses_global_intercept(self) -> bool:
        return False                                        # A21 in ARMS_WITHOUT_GLOBAL_INTERCEPT

    # ---- design ----------------------------------------------------------------------------
    def _required_target_cols(self):
        return ("team_id", "opponent_team_id", "game_id", "game_date", "season", NUISANCE_COL)

    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        missing = [c for c in self._required_target_cols() if c not in universe.columns]
        if missing:
            raise fc.A21ConstructionFailure(
                f"universe is missing required columns {missing} (team/opponent/game identity, "
                f"or the {NUISANCE_COL!r} nuisance column carried from A17's null)")

        target = universe[["team_id", "opponent_team_id", "game_id", "game_date", "season"]]
        raw = fc.compute_nc(self._possessions, target)

        train_idx = np.asarray(fold["train_idx"], dtype=int)
        train_mask = np.zeros(len(universe), dtype=bool)
        train_mask[train_idx] = True
        filled = fc.impute_empty_prior_set(raw["nc_own"], raw["nc_opp"], train_mask)
        x = fc.contamination_share(filled["nc_own"], filled["nc_opp"])

        nuisance_cols = universe[NUISANCE_COL].to_numpy(dtype=float)

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [NUISANCE_COL],       # 0/1 playoff indicator; x is a continuous share
            "columns": {NUISANCE_COL: nuisance_cols, TREATMENT_COL: x},
            "diagnostics": {
                "fold_id": str(fold.get("fold_id")),
                "n_rows": int(len(universe)),
                "n_own_imputed": filled["n_own_imputed"],
                "n_opp_imputed": filled["n_opp_imputed"],
                "imputation_constant": filled["imputation_constant"],
            },
        }

    def build_design_depth_robustness(self, fold: dict, universe: pd.DataFrame) -> dict:
        """Secondary diagnostic ONLY (task_cards.A21.primary_gate.secondary_diagnostics):
        the same design with ``pace_evidence_depth`` added to BOTH members' nuisance set. This
        variant carries no independent promotion value; it exists solely to decide the
        depth-absorption kill condition (``decide_kill``'s ``depth_absorption_check_failed``
        argument, computed by the caller from a fit of THIS design, not by this method)."""
        if DEPTH_COL not in universe.columns:
            raise fc.A21ConstructionFailure(
                f"universe is missing {DEPTH_COL!r}, required for the card's PREREGISTERED "
                f"depth-absorption robustness check")
        base = self.build_design(fold, universe)
        depth = universe[DEPTH_COL].to_numpy(dtype=float)
        nuisance = list(base["nuisance_cols"]) + [DEPTH_COL]
        k0 = base["k0_matched_design"]
        k0_nuisance = list(k0["nuisance_cols"]) + [DEPTH_COL]
        columns = dict(base["columns"])
        columns[DEPTH_COL] = depth
        return {
            "treatment_cols": list(base["treatment_cols"]),
            "nuisance_cols": nuisance,
            "k0_matched_design": {"treatment_cols": list(k0["treatment_cols"]),
                                  "nuisance_cols": k0_nuisance, "comparison": k0["comparison"]},
            "indicator_cols": list(base["indicator_cols"]),
            "columns": columns,
            "diagnostics": dict(base.get("diagnostics", {}),
                               robustness_variant="depth_absorption_check"),
        }

    # ---- P26 --------------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = {
            "intercept_treatment": "none -- no global intercept in arm or null (P35 intercept_"
                                   "structure: A21 in ARMS_WITHOUT_GLOBAL_INTERCEPT)",
            "calibration_freedom": "none -- no post-fit rescaling of any kind",
            "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
            "exposure_offset": f"{rc.OFFSET_COL} = log({rc.INCUMBENT_PROJECTION_COL})",
            "training_rows": f"rows:n={self._n_rows}:contract_schedule_clock",
            "evaluation_rows": f"rows:n={self._n_rows}:contract_schedule_clock",
            "chronological_folds": list(self._fold_ids),
            "clipping": "none",
            "link_function": "log",
            "preprocessing": (f"{NUISANCE_COL} carried unchanged from the receipted schedule "
                              f"identity columns; {TREATMENT_COL} = decay-weighted trailing share "
                              "of possessions flagged non_competitive_conservative, averaged over "
                              "own and opponent sides -- see feature_construction.py"),
            "missing_value_handling": ("empty-prior-set symmetric fold-mean imputation: a side's "
                                       "nc share with no strictly-earlier games is filled with the "
                                       "fold's TRAINING-row mean of the defined nc values, computed "
                                       "once per fold and held fixed across bootstrap refits (P35 "
                                       "A21 FOLDS F2, A17's rule adopted identically); identical in "
                                       "arm and null (the null carries no nc column, but the "
                                       "imputation constant is shared machinery)"),
            "companion_components": "none",
            "fallback_rules": "empty-prior-set fold-mean imputation (above); no partition/tier "
                              "indicator, so no fold-collapse fallback is registered",
            "aggregation": "none -- the unit of prediction is the team-game",
            "candidate_universe": "the resolved possession universe, per row",
            "post_processing": "none",
            "prediction_universe": "same as candidate_universe",
        }
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "observation_purification",
            "treatment_mechanism": {
                "statement": "trailing evidence generated in non-competitive (garbage-time) game "
                            "states mis-projects competitive pace; the symmetric own/opponent "
                            "decay-weighted non-competitive-possession share corrects for this "
                            "contamination as an ADDITIVE term over K0's un-reweighted evidence",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "coef(x)", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "contamination does not bias the "
                                                             "offset"}],
                "claimed_signal_axes": ["possession_observation"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        f"removing {TREATMENT_COL} leaves only the offset and {NUISANCE_COL} in "
                        "the null; K0 is granted NO re-weighting of its evidence by any other "
                        "route, so no column remaining in the null carries any garbage-time "
                        "contamination-share information and the claimed evidence_contamination "
                        "signal is fully destroyed by term removal (P33/P35 k0_matched_frozen: "
                        "'K0 granted NO re-weighting of its evidence -- the arm must show the "
                        "correction as an additive term, no smuggled estimator')")}},
            "invariants": {
                "rows": f"rows:n={self._n_rows}:contract_schedule_clock",
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": list(self._fold_ids),
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": [NUISANCE_COL],
                "lower_order_structural_terms": [NUISANCE_COL]},
            "arm_spec": {
                "name": "arm", "role": "challenger", "pipeline_id": rc.RUNNER_VERSION,
                "substantive_features": [TREATMENT_COL],
                "structural_terms": [NUISANCE_COL],
                "declaration_routing": {TREATMENT_COL: "substantive_features",
                                        NUISANCE_COL: "preprocessing"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "k0", "role": "k0", "pipeline_id": rc.RUNNER_VERSION,
                "substantive_features": [],
                "structural_terms": [NUISANCE_COL],
                "declaration_routing": {NUISANCE_COL: "preprocessing"},
                "comparison_gate_sidespec": side},
            "fold_local_fallback": {"required": False,
                                    "trigger": "not_applicable -- no partition/tier indicator; "
                                               "the empty-prior-set rule is a symmetric fold-mean "
                                               "fill, not a fold-collapse partition",
                                    "numeric_threshold": None, "action": "not_applicable",
                                    "registered_before_results": True},
            "verdict_label_policy": "observation_purification arm: eligible for a feature_value "
                                    "verdict ONLY against K0_MATCHED[A21] (identical to A17's "
                                    "null); K0_FLAT carries no promotion value whatsoever "
                                    "(k0_flat_role diagnostic_only)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "K0_MATCHED[A21] == K0_MATCHED[A17] by the card's own words ('identical to A17's "
                "null'); A17's frozen null is [log_exposure | is_playoff_game] (P35 task_cards."
                "A17.k0_matched_frozen). This module reproduces that single nuisance term and adds "
                "no other machinery to the null.",
                "PRIMARY GATE / secondary diagnostics: shared primary gate vs K0_MATCHED[A21]; "
                "PREREGISTERED ROBUSTNESS (P33 A21.primary_gate.secondary_diagnostics): adding "
                "pace_evidence_depth to the nuisance set -- if it absorbs the effect, x proxies "
                "evidence VOLUME and the mechanism is falsified even on a positive naive test. "
                "See build_design_depth_robustness() and decide_kill().",
                "EVIDENCE_QUALITY_CORRECTION family: {A21: 1} element, single test at alpha 0.05 "
                "(P35 multiplicity_recomputed) -- no multiplicity correction beyond alpha=0.05 "
                "itself.",
            ],
        }

    # ---- guards ---------------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale_common = (
            "computed strictly from possessions whose game_date precedes the target row's own "
            "game (feature_construction.py strict-lagging construction); declared DERIVED_NO_JOIN "
            "rather than PRIOR_GAME because the frozen P22 postgame_surrogate_guard."
            "verify_prior_game_lag re-derivation supports only a single shift(n_back), not a "
            "decay-weighted aggregate over an arbitrary-length trailing window -- this module's "
            "OWN strict-lagging identity tests (tests/TESTS.py) independently verify the strict "
            "'< game_date(g)' property the P22 shift-1 verifier cannot check for a weighted "
            "aggregate; flagged for P37/P38 rather than silently claimed as PRIOR_GAME-verified "
            "(identical disclosure pattern to A08's L_t / A07's n_i).")
        return {
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "possessions_raw_v2",
                            "rationale": ("decay-weighted (half_life_games=10, "
                                         "season_boundary_discount=0.5) trailing share of "
                                         "non_competitive_conservative over own+opponent prior "
                                         "possessions. " + rationale_common)},
            NUISANCE_COL: {"column": NUISANCE_COL, "kind": "SCHEDULE",
                           "source_artifact_id": "team_possession_prior_v1",
                           "rationale": "a fact fixed before tipoff (playoff/regular-season "
                                       "status of the target game itself); no lag to re-derive, "
                                       "still subject to the full P22 dependency battery"},
        }

    def lag_sources(self) -> dict:
        return {}          # DERIVED_NO_JOIN / SCHEDULE declare no PRIOR_GAME re-derivation source

    def preregistered_contrasts(self):
        return None          # A21 carries no "contrast_"-named column

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        return True           # P33 precondition: P23 franchise-continuity receipt (carried)

    def p23_receipts(self) -> list:
        return [{"team_cities_sha256": rc.TEAM_CITIES_SHA256_PIN,
                 "note": "A21 requires the franchise-continuity receipt per P33 precondition / "
                         "P35 shared_frozen_amendments.franchise_continuity_receipt_pin"}]

    def p27_rule(self):
        return None            # A21 registers no ActiveSetRule-shaped S7 rule: its frozen
                                # fold_local_fallback is the deterministic empty-prior-set
                                # fold-mean fill (feature_construction.impute_empty_prior_set), not
                                # a cluster-support/min-std partition rule (contrast A03's
                                # S7_TIER_SUPPORT_v1). Same reading as A08's p27_rule() for the
                                # identical reason.


# ---------------------------------------------------------------------------------------------
# kill-condition decidability (task_cards.A21.kill_conditions_frozen, verbatim):
#   "null vs K0; depth-absorption robustness check fails (x proxies evidence VOLUME - mechanism
#    falsified even on a positive naive test)"
# This is a pure decision function over already-computed per-fold coef(x) intervals PLUS the
# externally-computed depth-absorption verdict -- it fits no model and reads no comparative
# performance; it exists so the card's kill hooks are DECIDABLE and independently testable
# (see tests/TESTS.py::t_kill_condition_hooks_decidable).
# ---------------------------------------------------------------------------------------------
def decide_kill(coef_by_fold: dict, *, depth_absorption_check_failed: bool = False,
                p25_rejected: bool = False) -> dict:
    """coef_by_fold: {fold_id: {"point": float, "ci_low": float, "ci_high": float}}."""
    if p25_rejected:
        return {"schema": "a21_kill_decision/1", "killed": True, "reason": "p25_rejection",
                "basis": "P35 task_cards.A21.kill_conditions_frozen",
                "per_fold_covers_zero": {}, "null_vs_k0_kill": None,
                "depth_absorption_kill": depth_absorption_check_failed}

    covers_zero = {}
    for fid, v in coef_by_fold.items():
        lo, hi = float(v["ci_low"]), float(v["ci_high"])
        if lo > hi:
            raise ValueError(f"malformed interval for fold {fid}: ci_low > ci_high")
        covers_zero[fid] = bool(lo <= 0.0 <= hi)
    null_vs_k0_kill = bool(coef_by_fold) and all(covers_zero.values())
    depth_kill = bool(depth_absorption_check_failed)

    if null_vs_k0_kill and depth_kill:
        reason = "null_vs_k0_and_depth_absorption"
    elif null_vs_k0_kill:
        reason = "null_vs_k0_covers_zero_every_evaluable_fold"
    elif depth_kill:
        reason = "depth_absorption_check_failed"
    else:
        reason = "not_killed"

    return {"schema": "a21_kill_decision/1",
            "killed": bool(null_vs_k0_kill or depth_kill),
            "reason": reason,
            "basis": "P35 task_cards.A21.kill_conditions_frozen",
            "per_fold_covers_zero": covers_zero,
            "null_vs_k0_kill": null_vs_k0_kill, "depth_absorption_kill": depth_kill}
