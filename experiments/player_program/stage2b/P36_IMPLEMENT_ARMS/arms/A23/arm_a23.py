#!/usr/bin/env python3
"""arm_a23.py -- A23_rest_differential_contrast, the P36 RUNNER_INTERFACE arm module.

Frozen card: experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards
[A23_rest_differential_contrast], carrying P33_PREREGISTRATION_DRAFT/SPEC.json (sha256
066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) arms[A23_rest_differential_
contrast] by hash reference, amended exactly by the card's amendments_applied list plus
shared_frozen_amendments (intercept_structure, multiplicity_recomputed.grid_element_regime_
pinned, both_pass_adjudication_and_program_alpha [A23/A24 named pair]).

MODEL (card, verbatim): eta = log_exposure + beta * (f(rest_own) - f(rest_opp)); f = min(rest, c);
mu = exp(eta); no global intercept in arm or null (P35 intercept_structure: A23 is in
ARMS_WITHOUT_GLOBAL_INTERCEPT). TWO bundle elements (AI cap=7, OM cap=4), EACH fitted end-to-end
as its own module instance (RUNNER_INTERFACE.md section 1 names A23's two bundles explicitly:
"one arm-module instance binds exactly one enumeration element ... the runner never selects among
elements"). See feature_construction.py for the full construction, including the disclosed
opener-rule reading for bundle_AI.

K0_MATCHED[A23] (card k0_matched_frozen, verbatim): null = "identical everything per bundle;
excludes only the rest contrast; season-opener handling identical in arm and null under each
bundle" -- term_removal, treatment_terms = [f(rest_own) - f(rest_opp)], tested_parameters =
[{beta, coefficient, null_value 0, "no rest-differential drag"}]. The null carries NO nuisance
terms (the card's model has none beyond the offset), so K0_MATCHED[A23] IS the frozen incumbent
exactly under the no-global-intercept reading (P35 intercept_structure.consequence does not name
A23 among {A02,A03,A05,A16,A25} explicitly, but the same zero-fitted-parameter logic applies here
by direct construction: term_removal of the sole treatment term leaves eta = log_exposure).

PRECONDITION: "P23-receipted game_date join" (card, k0_matched_frozen / amendments_applied) -- a
NARROWER precondition than the cross-season franchise-continuity receipt (P35
franchise_continuity_receipt_pin: "A11's ... declaration stands; A23 carries the narrower P23
game_date-join receipt as declared"). A23 is same-season-only by construction (rest_own/rest_opp
never cross a season boundary) and is ABSENT from P33 shared_arm_invariants.p23_franchise_
continuity_precondition's named arm list (A08,A09,A10,A11,A12,A13,A14,A16,A17,A19,A21,A22,A24 --
not A23), so requires_franchise_continuity() returns False here, matching the A02/A03 precedent
for arms absent from that list. The narrower game_date-join precondition is documented but is not
a mechanism the shared guard_harness.p23_check enforces (that wrapper implements ONLY the
team_cities franchise-continuity pin); this gap is flagged for P37 rather than silently routed
through the wrong guard.

Per standing rule 3 (call-site enforcement, never editing a shared gate) and this unit's write
scope (experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A23/ only), this module imports
the FROZEN runner contract (runner_constants) read-only and writes nothing outside its own
directory; it never touches another arm's directory or the runner directory.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np

from feature_construction import BUNDLE_CAP, ENUMERATED_BUNDLES, bundle_contrast
from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TEAM_CITIES_SHA256_PIN

ARM_ID = "A23_rest_differential_contrast"

#: the card's own generic term name -- reused VERBATIM as the design's column key, per "implement
#: EXACTLY it" / "never improvise".
TREATMENT_COL = "f(rest_own) - f(rest_opp)"

REQUIRED_UNIVERSE_COLS = ("team_id", "opp_team_id", "season", "game_date", "game_id")


def _row_digest(n: int) -> str:
    return f"rows:n={n}:contract_schedule_or_synthetic"


def _sidespec(fold_ids, n_rows, bundle: str, cap: float) -> dict:
    opener_rule = (
        "S7 preregistered training-support-based symmetric fallback: either side's opener sets "
        "the row CONTRAST to 0 (deterministic, symmetric); an S7 ActiveSetRule additionally "
        f"requires >= 10 training clusters with a nonzero contrast per fold (fold-level, can "
        f"change fold evaluability, arm AND null identically)"
        if bundle == "AI" else
        "assign cap value (fully rested) independently per side, deterministic, no active-set "
        "rule"
    )
    return {
        "intercept_treatment": "none -- no global intercept in arm or null (P35 intercept_structure)",
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{OFFSET_COL} = log({INCUMBENT_PROJECTION_COL}), frozen incumbent "
                           "D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": _row_digest(n_rows),
        "evaluation_rows": _row_digest(n_rows),
        "chronological_folds": list(fold_ids),
        "clipping": f"f(rest) = min(rest, c), c={cap:g} (bundle_{bundle})",
        "link_function": "log",
        "preprocessing": (f"rest(t,g) = days since team t's previous COMPLETED same-season game, "
                          f"strictly earlier by (game_date, game_id) ascending; bundle_{bundle} "
                          f"cap c={cap:g}; opener rule: {opener_rule}"),
        "missing_value_handling": opener_rule,
        "companion_components": "none",
        "fallback_rules": opener_rule,
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the contract-schedule team-game universe (synthetic in tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A23Arm:
    """One A23 module instance == one bundle element (AI or OM).

    `contract_schedule` is the CONTRACT-SCHEDULE reference frame (team_possession_prior_v1's own
    2,990 team-game rows at P38 time; a synthetic superset frame in these blinded tests) carrying
    at least team_id, season, game_date, game_id -- it must be a SUPERSET of every row this module
    will ever see in `universe` (feature_construction.compute_rest_and_opener enforces this and
    fails closed if it does not hold). Mirrors A24Arm's own `contract_schedule` constructor
    argument for the identical reason (P37/EXEC-M6): rest(t, g) is a CONTRACT-SCHEDULE clock, not
    a universe-row clock.
    """

    arm_id = ARM_ID

    def __init__(self, bundle: str, contract_schedule, fold_ids, n_rows: int):
        if bundle not in ENUMERATED_BUNDLES:
            raise ValueError(f"bundle={bundle!r} is not one of the frozen P35 elements "
                             f"{ENUMERATED_BUNDLES}")
        missing = [c for c in REQUIRED_UNIVERSE_COLS
                  if c not in ("opp_team_id",) and c not in contract_schedule.columns]
        if missing:
            raise KeyError(f"A23 contract_schedule frame missing required columns {missing}")
        self.bundle = str(bundle)
        self.cap = BUNDLE_CAP[self.bundle]
        self._contract_schedule = contract_schedule.reset_index(drop=True)
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
        return {"bundle": self.bundle}

    def element_id(self) -> str:
        return f"A23_bundle_{self.bundle}"

    def uses_global_intercept(self) -> bool:
        return False

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe) -> dict:
        """rest_own/rest_opp/contrast are NOT fold-dependent constants (unlike e.g. A13's cbar_F):
        they are deterministic functions of schedule facts strictly earlier than each row's own
        game, so `fold` is accepted (per the frozen §3 contract) but not consulted for their
        construction -- the SAME reasoning A09/A16 document for their own all-prior constructions.
        """
        for col in REQUIRED_UNIVERSE_COLS:
            if col not in universe.columns:
                raise KeyError(f"A23 build_design requires column '{col}' on the universe frame")
        out = bundle_contrast(
            universe["team_id"].to_numpy(), universe["season"].to_numpy(),
            universe["game_date"].to_numpy(), universe["game_id"].to_numpy(),
            universe["opp_team_id"].to_numpy(),
            history_team_id=self._contract_schedule["team_id"].to_numpy(),
            history_season=self._contract_schedule["season"].to_numpy(),
            history_game_date=self._contract_schedule["game_date"].to_numpy(),
            history_game_id=self._contract_schedule["game_id"].to_numpy(),
            bundle=self.bundle)
        contrast = out["contrast"]
        if not np.all(np.isfinite(contrast)):
            raise ValueError(f"A23 bundle_{self.bundle}: the treatment contrast must be finite "
                             "on every row after the bundle's own opener rule is applied")
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {TREATMENT_COL: contrast},
        }

    # ---- P26 ------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids, self._n_rows, self.bundle, self.cap)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "rest differential predicts which team drags the tempo equilibrium: "
                             f"beta * (f(rest_own) - f(rest_opp)), f = min(rest, {self.cap:g}) "
                             f"(bundle_{self.bundle})",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "beta", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "no rest-differential drag"}],
                "claimed_signal_axes": ["team_identity", "opponent_identity"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": "removing beta*(f(rest_own)-f(rest_opp)) leaves "
                                               "eta = log_exposure exactly -- no rest-differential "
                                               "quantity of any kind remains in the design"}},
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
                "name": f"A23_bundle_{self.bundle}", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [TREATMENT_COL],
                "structural_terms": [],
                "declaration_routing": {TREATMENT_COL: "substantive_features"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": f"A23_bundle_{self.bundle}__K0_MATCHED", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": [],
                "declaration_routing": {},
                "comparison_gate_sidespec": dict(side)},
            "fold_local_fallback": {
                "required": self.bundle == "AI",
                "trigger": (side["fallback_rules"]),
                "numeric_threshold": 10 if self.bundle == "AI" else 0,
                "action": "drop_term_for_fold" if self.bundle == "AI" else "not_applicable",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature arm: eligible for a feature_value "
                                    f"verdict against K0_MATCHED[A23 bundle_{self.bundle}], "
                                    "subject to the primary gate, the schedule_context_family Holm "
                                    "correction (3 elements), and the A23/A24 both-pass "
                                    "joint-re-test naming (P35 mechanism_split_disclaimer).",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "LEAKAGE L2 / OPERATIONAL OP-4: bundle_AI's prior-game rule REDEFINED to "
                "'previous COMPLETED same-season game' (was 'previous SCHEDULED game', "
                "unimplementable on this archive); the two bundles now differ in cap and opener "
                "rule ONLY (P35 A23 card, bundles_frozen.distinction_honest).",
                "MULT B-4: both bundles fitted end-to-end, each with its own pooled OOF p-value; "
                "multi-survivor rule applies within schedule_context_family (Holm, 3 elements: "
                "A23 x2, A25 x1).",
                "K0 K8: the two bundles may be evaluated on different fold/row sets (AI's opener "
                "rule is a fold-level fallback, OM's is deterministic); the family Holm is not a "
                "like-for-like row-set comparison.",
            ],
        }

    # ---- guards -----------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale = (
            f"f(rest_own) - f(rest_opp), bundle_{self.bundle} (cap c={self.cap:g}): rest(t,g) is "
            "built by feature_construction.py against the SEPARATE contract_schedule history "
            "frame bound at this module's construction (P37/EXEC-M6 remediation; A24's own "
            "constructor-injected `contract_schedule` precedent for the identical reason -- the "
            "module's prior rationale, 'the universe frame IS the contract-schedule history', was "
            "measured false for the 8 opener teams' second 2021 games, P37 finding A3-B4), "
            "restricted per-row to the team's own strictly-earlier SAME-SEASON contract-schedule "
            "rows only. This is a DERIVED_NO_JOIN construction, matching every other all-prior/"
            "trailing construction in this program (A08 d_t/L_t, A09 d_t, A12 dev_prev, A16 "
            "dev_own-dev_opp, A24 rest(t,g) itself: none of them are declared PRIOR_GAME, because "
            "postgame_surrogate_guard's PRIOR_GAME re-derivation verifies a single "
            "groupby+shift(n_back) value column, not a derived difference/cap/opponent-lookup "
            "quantity). Strict lagging is instead established directly by identity/synthetic "
            "tests in this unit (TESTS.py) against feature_construction.py's pure functions."
        )
        return {
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "team_possession_prior_v1/via_constructor_injection",
                            "rationale": rationale},
        }

    def lag_sources(self) -> dict:
        return {}                       # DERIVED_NO_JOIN needs no external re-derivation source

    def preregistered_contrasts(self):
        return None

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # A23 is absent from P33 shared_arm_invariants.p23_franchise_continuity_precondition's
        # arm list (A08,A09,A10,A11,A12,A13,A14,A16,A17,A19,A21,A22,A24 -- not A23): rest_own/
        # rest_opp are same-season-only by construction, so no cross-season franchise-rebrand
        # dependency exists. The card's own precondition is the NARROWER "P23-receipted
        # game_date join" (see module docstring); requires_franchise_continuity() names the
        # cross-season team_cities pin specifically and correctly returns False here.
        return False

    def p23_receipts(self) -> list:
        # No cross-season franchise-continuity receipt is required (see requires_franchise_
        # continuity above). The card's narrower "P23-receipted game_date join" precondition is
        # documented here for the record even though guard_harness.p23_check (which enforces
        # ONLY the team_cities franchise-continuity pin) has no mechanism for it; flagged for P37
        # rather than silently routed through the wrong guard.
        return []

    def p27_rule(self):
        if self.bundle != "AI":
            # bundle_OM: "deterministic, no active-set rule" (card, verbatim)
            return None
        rule_kwargs = {
            "rule_id": "A23_S7_OPENER_SYMMETRIC_FALLBACK_v1",
            "min_nonzero_clusters": 10,
            "min_std": 0.0,
            "rationale": (
                "P35 A23 card bundle_AI opener rule: 'S7 preregistered training-support-based "
                "symmetric fallback (fold-level; can change fold evaluability, arm AND null "
                "identically)'. This module's disclosed reading (see feature_construction.py "
                f"module docstring): >= 10 training clusters must carry a nonzero {TREATMENT_COL} "
                "contrast (i.e. neither side an opener) for the fold to be estimable; a fold "
                "below that floor is prospectively UNEVALUABLE, identically for arm and null."),
        }
        spec = {
            "rule_id": rule_kwargs["rule_id"],
            "min_nonzero_clusters": int(rule_kwargs["min_nonzero_clusters"]),
            "min_std": float(rule_kwargs["min_std"]),
            "rationale": rule_kwargs["rationale"],
            "conditions_on": "SupportSummary (training-fold counts only)",
            "applied_to": "candidate AND null, identically, once per fold",
        }
        import hashlib
        import json
        digest = hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        prereg_kwargs = {
            "registered_at_utc": ("P35_FREEZE_TASK_CARDS freeze (2026, exact UTC not carried in "
                                  "the frozen SPEC.json bytes -- recorded honestly as an "
                                  "unestablished precision, not fabricated)"),
            "registered_by": ("P36_IMPLEMENT_ARMS/A23 (task card frozen at P35, hash-pinned; the "
                              "S7 rule's row-level numeric substitution is this module's own "
                              "disclosed reading of the card's prose -- see feature_construction"
                              ".py docstring, flagged for P37)"),
            "rule_spec_sha256": digest,
            "results_visible_at_registration": False,
            "record_path": ("experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json"
                            "#task_cards[arm_id=A23_rest_differential_contrast]"
                            ".bundles_frozen.bundle_AI"),
        }
        return (rule_kwargs, prereg_kwargs)


# ------------------------------------------------------------------------------ kill conditions
def evaluate_kill_conditions(per_fold_decidable: list[dict]) -> dict:
    """The card's kill_conditions_frozen, made decidable, from a run_arm() receipt's own
    per-fold summary alone (pure post-processing; computes no new fit).

    Card (kill_conditions_frozen, verbatim): "no gain over K0; opposite-sign rejection (interval
    excluding 0 with sign opposite to prediction kills the mechanism as stated); effect below
    resolution declared as a null, not deferred."

    AMBIGUITY DISCLOSED, NOT RESOLVED SILENTLY: "opposite-sign rejection" requires a PREDICTED
    direction for beta. Neither the P33 arm record nor the P35 card (the frozen bytes this module
    was implemented against) states that predicted sign numerically anywhere this module can
    cite. This function therefore decides the two SIGN-FREE kill components exactly (no gain over
    K0: pooled delta_MAE <= 0; effect below resolution: interval covers 0 in every evaluable
    fold) and reports interval-excludes-zero WITH its observed sign, but explicitly declines to
    manufacture a predicted-direction comparison -- 'opposite_sign_rejection' is returned as
    'UNDECIDABLE_NO_PREDICTED_DIRECTION_IN_FROZEN_CARD', flagged for P37, rather than an invented
    verdict. `per_fold_decidable`: the list this arm's TESTS.py already produces per evaluable
    fold, each {"fold_id", "lo", "hi", "no_gain_over_k0", "interval_excludes_zero"}.
    """
    if not per_fold_decidable:
        return {"killed": None, "reason": "no evaluable folds supplied; kill undecidable "
                                          "(distinct from a fired kill)"}
    covers_zero_all = all(not e["interval_excludes_zero"] for e in per_fold_decidable)
    no_gain_all = all(e["no_gain_over_k0"] for e in per_fold_decidable)
    below_resolution_kill = bool(covers_zero_all)
    return {
        "schema": "p36_a23_kill_conditions/1",
        "n_evaluable_folds": len(per_fold_decidable),
        "per_fold": per_fold_decidable,
        "no_gain_over_k0_every_fold": no_gain_all,
        "effect_below_resolution_kill": below_resolution_kill,
        "opposite_sign_rejection": "UNDECIDABLE_NO_PREDICTED_DIRECTION_IN_FROZEN_CARD",
        "any_kill_fired": below_resolution_kill,
    }


def make_arms(contract_schedule, fold_ids, n_rows) -> list[A23Arm]:
    """One module instance per frozen enumeration element (bundle in {AI, OM}); the runner never
    selects among them (RUNNER_INTERFACE.md section 1, which names A23's two bundles explicitly).
    """
    return [A23Arm(b, contract_schedule, fold_ids, n_rows) for b in ENUMERATED_BUNDLES]
