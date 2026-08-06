#!/usr/bin/env python3
"""arm_a24.py -- A24_rest_level_symmetric arm module, RUNNER_INTERFACE.md conformant.

Card: P35_FREEZE_TASK_CARDS/SPEC.json (sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards.A24, carrying P33
PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072
d347d093) arm A24 by hash reference, amended exactly by the card's amendments_applied list.

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A24/ only. This module
IMPORTS the frozen runner contract (runner_constants) READ-ONLY, to build conformant records; it
edits nothing under runner/.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

MODEL (frozen, card-pinned, task_cards.A24.model verbatim):
    eta = log_exposure + coef * x
    rest(t, g) = min(days since max prior contract game date of t, 10)
    x   = (rest(t, g) + rest(opp(g, t), g)) / 2
    mu  = exp(eta)
    NO global intercept (P35 intercept_structure table: A24 in ARMS_WITHOUT_GLOBAL_INTERCEPT).

K0_MATCHED[A24] (frozen, card k0_matched_frozen, verbatim): "same machinery; treatment adds ONLY
x" -- the arm's own model carries NO nuisance term of any kind (just the offset plus coef*x), so
removing x leaves null = [log_exposure] with ZERO fitted parameters, IS the frozen incumbent
exactly (P35 no_implementation_default_intercept_invariant + intercept table; the same reading
already established for A16/A25 -- see NOTE below on the shared_frozen_amendments.intercept_
structure.consequence list, which happens not to name A24 by name even though the underlying fact
is identical; flagged as a documentation-completeness observation in REPORT.md, not a substantive
contradiction). comparison: term_removal. treatment_terms: ["x (rest level)"]. tested_parameters:
[{coef(x), coefficient, null_value 0}].

Single enumeration element (P33/P35 A24.hyperparameters.enumerated = {}) -- one module instance IS
the whole arm (RUNNER_INTERFACE.md section 1: "{} for single-element arms").

CLOCK READING and the GENUINE GAP left open by the card (franchise-debut rows) are both disclosed
in full in feature_construction.py's module docstring -- read it before reading this file's
build_design(). Summary: rest(t, g) is computed against the CONTRACT-SCHEDULE history of team t
(construction_pins.n_clock_pin's clock, extended here by the card's own "contract game date"
wording), and build_design FAILS CLOSED if any row's x is structurally undefined rather than
inventing a fallback the card never pinned.

PRECONDITION (P33 A24 "precondition": "P23 franchise-continuity receipt (cross-season prior
game)"; P33 shared_arm_invariants.p23_franchise_continuity_precondition names A24 explicitly).

MULTIPLICITY: SCHEDULE_FATIGUE family, {A24: 1}, single test at alpha 0.05 (P35
multiplicity_recomputed.families_this_cycle); A23/A24 both-pass pair named
(mechanism_split_disclaimer) -- adjudicated by the runner's caller, not by this module.

SECONDARY / KILL CONDITION (task_cards.A24.kill_conditions_frozen, verbatim): "null vs K0; P25
flag (itself evidence the incumbent already encodes schedule structure - the arm dies)". Unlike
most other arms, a P25 flag here is read literally as it is worded: NOT a generic design-failure
withdrawal, but itself POSITIVE evidence for the null hypothesis (the incumbent already prices
schedule structure) -- so it kills the arm rather than merely voiding it as inadmissible. Also
carried verbatim: "LAG OPERATOR POSITIVE CONTROL role preserved verbatim (if the machinery cannot
cleanly evaluate this arm, no lagged-arm result should be trusted)" -- A24 is the maximally
provable lagged construction; any guard/runner failure on THIS arm indicts the machinery, not the
arm (same positive-control role A25 carries for the guard configuration).
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

import runner_constants as rc                    # noqa: E402  (frozen; imported, never edited)
import feature_construction as fc                 # noqa: E402  (this unit's own module)

CARD_ID = "A24_rest_level_symmetric"
TREATMENT_COL = "x_rest_level_symmetric"


class A24Arm:
    """One instance = the whole arm (no enumerated grid; P33/P35 hyperparameters.enumerated={}).

    `contract_schedule` is the CONTRACT-SCHEDULE reference frame (team_possession_prior_v1's own
    2,990 team-game rows at P38 time; a synthetic superset frame in these blinded tests) carrying
    at least team_id, game_date, game_id -- it must be a SUPERSET of every row this module will
    ever see in `universe` (feature_construction.compute_rest_days enforces this and fails closed
    if it does not hold). Mirrors A08Arm's own `history` constructor argument for the identical
    reason: rest(t, g) is a CONTRACT-SCHEDULE clock, not a universe-row clock (module docstring).
    """

    arm_id = CARD_ID

    def __init__(self, contract_schedule: pd.DataFrame, fold_ids=(), n_rows: int | None = None):
        missing = [c for c in ("team_id", "game_date", "game_id")
                  if c not in contract_schedule.columns]
        if missing:
            raise fc.A24ConstructionFailure(
                f"contract_schedule frame missing required columns {missing}")
        self._contract_schedule = contract_schedule.reset_index(drop=True)
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
        return "A24_rest_level_symmetric__single"

    def uses_global_intercept(self) -> bool:
        return False                                        # A24 in ARMS_WITHOUT_GLOBAL_INTERCEPT

    # ---- design ----------------------------------------------------------------------------
    def _required_target_cols(self):
        return ("team_id", "opp_team_id", "game_id", "game_date")

    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        # rest(t, g) is a deterministic, strictly-lagged per-row historical fact (like A16's
        # dev_own/dev_opp): the SAME construction runs for every fold and for the
        # FINAL_ASSEMBLED_DESIGN pseudo-fold; fold is accepted per the frozen signature but
        # contributes only to diagnostics below (no training-fold-computed constant exists in
        # A24's construction, unlike A13's cbar_F or A17's imputation means).
        missing = [c for c in self._required_target_cols() if c not in universe.columns]
        if missing:
            raise fc.A24ConstructionFailure(
                f"universe is missing required columns {missing} (team/opponent/game identity)")

        out = fc.rest_level_symmetric(
            universe["team_id"].to_numpy(), universe["opp_team_id"].to_numpy(),
            universe["game_id"].to_numpy(), universe["game_date"].to_numpy(),
            history_team_id=self._contract_schedule["team_id"].to_numpy(),
            history_game_date=self._contract_schedule["game_date"].to_numpy(),
            history_game_id=self._contract_schedule["game_id"].to_numpy(),
        )
        if out["n_undefined"] > 0:
            # FAIL CLOSED: the card's "fallback: none needed" claim does not cover a true
            # franchise debut (feature_construction.py module docstring, GENUINE GAP DISCLOSED);
            # no numeric substitution is authorized anywhere in A24's frozen text, so this module
            # refuses rather than invents one.
            bad_rows = np.flatnonzero(np.isnan(out["x"]))
            raise fc.A24ConstructionFailure(
                f"A24: x is structurally undefined on {out['n_undefined']} row(s) "
                f"(indices {bad_rows[:10].tolist()}...) -- no frozen fallback rule covers a true "
                f"franchise-debut row (see feature_construction.py GENUINE GAP DISCLOSED note); "
                f"failing closed rather than silently substituting a value the card never pinned")

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {
                "treatment_cols": [],
                "nuisance_cols": [],
                "comparison": "term_removal",
            },
            "indicator_cols": [],
            "columns": {TREATMENT_COL: out["x"]},
            "diagnostics": {
                "fold_id": str(fold.get("fold_id")) if isinstance(fold, dict) else None,
                "n_rows": int(len(universe)),
                "n_undefined": out["n_undefined"],
            },
        }

    # ---- P26 --------------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = {
            "intercept_treatment": "none -- no global intercept in arm or null (P35 intercept_"
                                   "structure: A24 in ARMS_WITHOUT_GLOBAL_INTERCEPT)",
            "calibration_freedom": "none -- no post-fit rescaling of any kind",
            "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
            "exposure_offset": f"{rc.OFFSET_COL} = log({rc.INCUMBENT_PROJECTION_COL})",
            "training_rows": f"rows:n={self._n_rows}:contract_schedule_clock",
            "evaluation_rows": f"rows:n={self._n_rows}:contract_schedule_clock",
            "chronological_folds": list(self._fold_ids),
            "clipping": "none",
            "link_function": "log",
            "preprocessing": (f"{TREATMENT_COL} = symmetric mean of own/opponent capped "
                              "(cap=10 days) rest, each side's rest = days since that team's "
                              "own most recent strictly-earlier CONTRACT-SCHEDULE game, "
                              "cross-season -- see feature_construction.py"),
            "missing_value_handling": ("NONE authorized by the card ('fallback: none needed "
                                       "(cross-season prior game covers openers)'); a "
                                       "structurally-undefined row (true franchise debut) fails "
                                       "the arm/fold closed rather than being imputed -- see "
                                       "feature_construction.py GENUINE GAP DISCLOSED note"),
            "companion_components": "none",
            "fallback_rules": "none (card-declared; see missing_value_handling)",
            "aggregation": "none -- the unit of prediction is the team-game",
            "candidate_universe": "the resolved possession universe, per row",
            "post_processing": "none",
            "prediction_universe": "same as candidate_universe",
        }
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "symmetric (own+opponent)/2 capped rest-day level predicts overall "
                            "tempo depression beyond what the frozen offset prices",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "coef(x)", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "no rest-level depression"}],
                "claimed_signal_axes": ["team_identity", "opponent_identity"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        f"removing {TREATMENT_COL} leaves eta = log_exposure exactly -- zero "
                        "fitted parameters, the frozen incumbent projection with no schedule-"
                        "fatigue information of any kind remaining (P35 task_cards.A24."
                        "k0_matched_frozen: 'same machinery; treatment adds ONLY x')")}},
            "invariants": {
                "rows": f"rows:n={self._n_rows}:contract_schedule_clock",
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": list(self._fold_ids),
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": [],
                "lower_order_structural_terms": []},
            "arm_spec": {
                "name": "arm", "role": "challenger", "pipeline_id": rc.RUNNER_VERSION,
                "substantive_features": [TREATMENT_COL],
                "structural_terms": [],
                "declaration_routing": {TREATMENT_COL: "substantive_features"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "k0", "role": "k0", "pipeline_id": rc.RUNNER_VERSION,
                "substantive_features": [],
                "structural_terms": [],
                "declaration_routing": {},
                "comparison_gate_sidespec": side},
            "fold_local_fallback": {"required": False,
                                    "trigger": "not_applicable -- cross-season contract-schedule "
                                               "clock covers every season opener; a true "
                                               "franchise debut fails the arm/fold closed rather "
                                               "than triggering a registered fallback (no S7 "
                                               "ActiveSetRule is registered for A24)",
                                    "numeric_threshold": None, "action": "not_applicable",
                                    "registered_before_results": True},
            "verdict_label_policy": "substantive_feature arm: eligible for FEATURE VALUE "
                                    "DEMONSTRATED via challenger_vs_k0 against this record; "
                                    "K0_FLAT carries no promotion value whatsoever "
                                    "(k0_flat_role diagnostic_only)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "K0_MATCHED[A24] is a zero-fitted-parameter null identical in structure to "
                "A16/A25's own nulls (P35 shared_frozen_amendments.intercept_structure."
                "consequence names A02/A03/A05/A16/A25 explicitly but not A24 by name; the "
                "underlying fact -- 'same machinery; treatment adds ONLY x', no nuisance term of "
                "any kind in the arm's own model -- makes A24's zero-parameter null recover the "
                "incumbent exactly under the identical no-intercept reading. Flagged as a "
                "documentation-completeness observation for REPORT.md, not a substantive "
                "contradiction requiring a HALT.)",
                "SCHEDULE_FATIGUE family: {A24: 1} element, single test at alpha 0.05 (P35 "
                "multiplicity_recomputed) -- no multiplicity correction beyond alpha=0.05 "
                "itself. Both-pass exposure named with A23 (mechanism_split_disclaimer); "
                "adjudicated outside this module.",
                "LAG OPERATOR POSITIVE CONTROL role (P33 A24 card, secondary_diagnostics, "
                "carried verbatim): 'this is the maximally provable lagged construction - if the "
                "machinery cannot cleanly evaluate it, no lagged-arm result should be trusted'.",
            ],
        }

    # ---- guards ---------------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale = (
            "days since team t's own most recent STRICTLY EARLIER CONTRACT-SCHEDULE game "
            "(feature_construction.py's game-rank + groupby-shift construction over the "
            "supplied contract_schedule history frame), symmetrised with the opponent's "
            "identical own-side quantity and capped at 10 days. Declared DERIVED_NO_JOIN "
            "rather than PRIOR_GAME because the frozen P22 postgame_surrogate_guard."
            "verify_prior_game_lag re-derivation compares a single shifted SOURCE COLUMN "
            "value-for-value against the frame's own column; A24's column is a DAY-DIFFERENCE "
            "derived from a shifted date, not the shifted value itself, matching the identical "
            "disclosure precedent A08/A16/A21 already established for their own derived-not-"
            "raw-shift constructions. This module's OWN strict-lagging identity tests "
            "(tests/TESTS.py) independently verify the strict '< own game' property the P22 "
            "shift-1 verifier cannot check for this derived quantity.")
        return {
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "team_possession_prior_v1",
                            "rationale": rationale},
        }

    def lag_sources(self) -> dict:
        return {}          # DERIVED_NO_JOIN declares no PRIOR_GAME re-derivation source

    def preregistered_contrasts(self):
        return None          # A24 carries no "contrast_"-named column

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 shared_arm_invariants.p23_franchise_continuity_precondition names A24 explicitly
        # ("cross-season prior game"); P35 A24 card amendments_applied: "OP-5 team_cities pin
        # (cross-season prior game)".
        return True

    def p23_receipts(self) -> list:
        return [{"team_cities_sha256": rc.TEAM_CITIES_SHA256_PIN,
                 "note": "A24 requires the franchise-continuity receipt per P33 precondition / "
                         "P35 shared_frozen_amendments.franchise_continuity_receipt_pin "
                         "(cross-season prior contract game)"}]

    def p27_rule(self):
        return None            # A24's own card fold_local_fallback is "none needed (cross-season
                                # prior game covers openers)" -- no S7 ActiveSetRule/Preregistration
                                # pair is registered for it (contrast A03/A12/A13/A14's
                                # S7_TIER_SUPPORT_v1 registrations). Same reading as A08/A16/A21's
                                # p27_rule() for the identical reason.


# ---------------------------------------------------------------------------------------------
# kill-condition decidability (task_cards.A24.kill_conditions_frozen, verbatim):
#   "null vs K0; P25 flag (itself evidence the incumbent already encodes schedule structure - the
#    arm dies)"
# Unlike most sibling arms' "P25 rejection = design-failure withdrawal before any performance
# number", A24's own card reads a P25 flag LITERALLY as substantive evidence for the null (the
# incumbent already prices schedule structure) -- so p25_flagged kills for a DIFFERENT, carded
# reason than p25_rejected does elsewhere in this program. This is a pure decision function over
# already-computed per-fold coef(x) intervals -- it fits no model and reads no comparative
# performance; it exists so the card's kill hooks are DECIDABLE and independently testable (see
# tests/TESTS.py::t_kill_condition_hooks_decidable).
# ---------------------------------------------------------------------------------------------
def decide_kill(coef_by_fold: dict, *, p25_flagged: bool = False) -> dict:
    """coef_by_fold: {fold_id: {"point": float, "ci_low": float, "ci_high": float}}."""
    covers_zero = {}
    for fid, v in coef_by_fold.items():
        lo, hi = float(v["ci_low"]), float(v["ci_high"])
        if lo > hi:
            raise ValueError(f"malformed interval for fold {fid}: ci_low > ci_high")
        covers_zero[fid] = bool(lo <= 0.0 <= hi)
    null_vs_k0_kill = bool(coef_by_fold) and all(covers_zero.values())

    if p25_flagged and null_vs_k0_kill:
        reason = "p25_flag_and_null_vs_k0"
    elif p25_flagged:
        reason = "p25_flag_evidence_of_schedule_encoding"
    elif null_vs_k0_kill:
        reason = "null_vs_k0_covers_zero_every_evaluable_fold"
    else:
        reason = "not_killed"

    return {"schema": "a24_kill_decision/1",
            "killed": bool(null_vs_k0_kill or p25_flagged),
            "reason": reason,
            "basis": "P35 task_cards.A24.kill_conditions_frozen",
            "per_fold_covers_zero": covers_zero,
            "null_vs_k0_kill": null_vs_k0_kill,
            "p25_flag_kill": bool(p25_flagged)}
