#!/usr/bin/env python3
"""arm_a02.py -- P36 arm module for A02_cal_blend_contrast.

Frozen source: experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32),
task_cards[arm_id == "A02_cal_blend_contrast"]. That card is law; nothing here introduces a
value the card does not carry.

Model (card, verbatim): eta = log_exposure + gamma * contrast_own_minus_opp_pace_estimate;
mu = exp(eta); no global intercept in arm or null.

K0_MATCHED (card): arm_kind calibration_only; null = [log_exposure] with ZERO fitted
parameters and IS the frozen incumbent exactly (P35 intercept_structure: A02 is in
without_any_global_intercept, so the zero-parameter null recovers the incumbent literally);
comparison = term_removal; treatment_terms = [contrast_own_minus_opp_pace_estimate]
(bytes == pace_gap, the registered P25 contrast); tested_parameters = [{gamma, coefficient,
null_value 0, "equal-weight blend correct"}].

Epistemic status of this module and its tests: IMPLEMENTATION. Blinded: no agent may inspect
challenger performance. Unit, synthetic, identity and schema tests only.

Ownership: this file and everything under this arm's directory
(experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A02/) is this unit's write scope.
It imports the frozen RUNNER_INTERFACE contract and the frozen P22/P25/P26/P27 guards
read-only; it edits none of them (standing rule 3: call-site enforcement only, never a shared
gate). It never touches another arm's directory or the runner directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ARM_ID = "A02_cal_blend_contrast"
TREATMENT_COL = "contrast_own_minus_opp_pace_estimate"
GAME_COL = "game_id"
TEAM_COL = "team_id"
# P25 PREREGISTERED_CONTRASTS.json contrasts[0].input_definitions: own_est/opp_est are ALREADY
# RESOLVED team_possession_prior_v1.team_pace_estimate values the frame carries in from
# upstream (own_est on the row's own team-game, opp_est the same game_id's other team_id);
# this module performs no join to produce them -- it only combines two already-present columns.
OWN_EST_COL = "own_est"
OPP_EST_COL = "opp_est"

# -------------------------------------------------------------------------------- frozen source
_HERE = Path(__file__).resolve().parent
_PLAYER_PROGRAM = _HERE.parents[3]                 # .../experiments/player_program
_STAGE2B = _PLAYER_PROGRAM / "stage2b"
_PREREG_PATH = _STAGE2B / "P25_OFFSET_DEPENDENCY_GUARD" / "PREREGISTERED_CONTRASTS.json"

# P35 SPEC.json byte pin this module was implemented against (STEP 1 of the node prompt).
P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"


def _canonical_digest(obj) -> str:
    """IDENTICAL algorithm to offset_dependency_guard.canonical_digest / P27's sha256_of:
    sha256 of json.dumps(obj, sort_keys=True, separators=(',', ':'), default=str).
    Reimplemented here (not imported) so this module has no import-time dependency on a
    frozen guard file existing at a particular path; the two are cross-checked by TESTS.py
    against the live P25 module.
    """
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def load_preregistered_contrasts() -> list[dict]:
    """Read-only load of the frozen P25 preregistration record's 'contrasts' list."""
    return json.loads(_PREREG_PATH.read_text(encoding="utf-8"))["contrasts"]


def preregistered_contrast_digest() -> str:
    return _canonical_digest(load_preregistered_contrasts())


def _row_digest(n: int) -> str:
    return f"rows:n={n}:A02_synthetic_or_test_fixture"


def _sidespec(fold_ids, n_rows) -> dict:
    """The 17 comparison_gate.DIMENSIONS, IDENTICAL between arm_spec and k0_spec (R2/R7):
    the ONLY permitted difference between arm and null is the treatment mechanism, which lives
    in substantive_features, never in this dict.
    """
    return {
        "intercept_treatment": ("none -- no global intercept in arm or null "
                                "(P35 intercept_structure.without_any_global_intercept: A02)"),
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": "log_exposure = log(projected_team_off_possessions), frozen incumbent",
        "training_rows": _row_digest(n_rows),
        "evaluation_rows": _row_digest(n_rows),
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": "none -- raw contrast column, no standardisation, no re-centring",
        "missing_value_handling": ("none -- complete case; degenerate folds are handled by the "
                                   "registered fold-local fallback (sd(contrast)==0), never by "
                                   "row-level imputation"),
        "companion_components": "none",
        "fallback_rules": ("none at the row level; fold-local collapse only, per "
                          "fold_local_fallback, identical trigger arm and null"),
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "team-game rows with resolved own_pace_estimate on both sides of the game",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


def compute_contrast(universe) -> np.ndarray:
    """own_est - opp_est, EXACTLY the registered formula (P25 PREREGISTERED_CONTRASTS.json
    contrasts[0].formula == "own_est - opp_est"), evaluated over the frame's own already-
    resolved own_est/opp_est columns.

    Deliberately the simplest possible reproduction of the registered formula: the P25
    offset_dependency_guard independently re-derives this same formula from the SAME two named
    columns and requires byte-for-byte agreement (max |deviation| <= 1e-12); this function must
    therefore compute nothing the guard cannot already recompute from the frame it audits. No
    join is performed here -- DERIVED_NO_JOIN, per lag_specs().
    """
    for col in (OWN_EST_COL, OPP_EST_COL):
        if col not in universe.columns:
            raise KeyError(f"A02 requires column '{col}' in the audited frame "
                            f"(P25 PREREGISTERED_CONTRASTS.json input_definitions)")
    own = universe[OWN_EST_COL].to_numpy(float)
    opp = universe[OPP_EST_COL].to_numpy(float)
    return own - opp


def validate_own_opp_pairing(universe) -> None:
    """Defensive, fixture/upstream-construction invariant (NOT part of the registered formula
    itself, and not re-run by build_design on every call): with exactly two team-rows per
    game_id, each row's opp_est must equal the OTHER row's own_est. A violation means the
    upstream own_est/opp_est construction, not this arm's formula, is broken. Used by tests and
    available to callers that want to audit a candidate universe before fitting.
    """
    counts = universe.groupby(GAME_COL)[OWN_EST_COL].transform("count").to_numpy()
    if not np.all(counts == 2):
        bad = sorted(set(universe.loc[counts != 2, GAME_COL].tolist()))
        raise ValueError(f"A02 requires exactly two team-rows per game_id; violated for "
                          f"game_id(s) {bad[:10]}{'...' if len(bad) > 10 else ''}")
    own = universe[OWN_EST_COL].to_numpy(float)
    group_sum_own = universe.groupby(GAME_COL)[OWN_EST_COL].transform("sum").to_numpy()
    other_own = group_sum_own - own          # the OTHER row's own_est, by construction
    opp = universe[OPP_EST_COL].to_numpy(float)
    if not np.allclose(other_own, opp, atol=1e-12):
        raise ValueError("opp_est does not match the other team-row's own_est for at least one "
                         "game_id: the upstream own_est/opp_est construction is inconsistent")


class ArmA02:
    """A02_cal_blend_contrast, single enumeration element (no grid)."""

    arm_id = ARM_ID

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
        return "A02_cal_blend_contrast__single"

    def uses_global_intercept(self):
        return False

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe):
        contrast = compute_contrast(universe)
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {TREATMENT_COL: contrast},
        }

    # ---- P26 ------------------------------------------------------------------------
    def p26_k0_record(self):
        side = _sidespec(self._fold_ids, self._n_rows)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "calibration_only",
            "treatment_mechanism": {
                "statement": ("the incumbent's equal-weight two-sided pace blend may be "
                              "miscalibrated; the own-minus-opponent pace gap tests a "
                              "log-linear correction to that blend (P35 A02 card, P25 "
                              "PREREGISTERED_CONTRASTS.json contrast_own_minus_opp_pace_"
                              "estimate)"),
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{
                    "name": "gamma", "role": "coefficient", "null_value": 0,
                    "null_value_meaning": "equal-weight blend correct"}],
                "claimed_signal_axes": ["opponent_identity"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": ("removing gamma*contrast leaves "
                                                "eta = log_exposure exactly, which is the "
                                                "frozen incumbent with no blend-weight "
                                                "correction of any kind")},
            },
            "invariants": {
                "rows": _row_digest(self._n_rows),
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": "none -- calibration_only; fold-local collapse only",
                "nuisance_terms": [],
                "lower_order_structural_terms": [],
            },
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
                "required": True,
                "trigger": "exact own=opp across a whole training fold",
                "numeric_threshold": 1e-08,
                "action": "refuse_to_score_fold",
                "registered_before_results": True},
            "verdict_label_policy": ("CALIBRATION RESULT ONLY -- this arm is NOT eligible for "
                                     "a feature value label however large challenger_vs_k0 is"),
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
        }

    # ---- guards -----------------------------------------------------------------
    def lag_specs(self):
        return {
            TREATMENT_COL: {
                "column": TREATMENT_COL,
                "kind": "DERIVED_NO_JOIN",
                "source_artifact_id": ("P25_OFFSET_DEPENDENCY_GUARD/PREREGISTERED_CONTRASTS.json"
                                       "#contrasts[contrast_own_minus_opp_pace_estimate]"),
                "rationale": ("own_est - opp_est; both are already-resolved "
                             "team_possession_prior_v1.team_pace_estimate values present in "
                             "the audited frame (own_est on the row's own team-game, opp_est "
                             "the same game_id's other team_id); no same-game or prior-game "
                             "join is performed beyond what own_pace_estimate already "
                             "resolves (P25 PREREGISTERED_CONTRASTS.json contrasts[0]; P35 "
                             "A02 card amendments_applied OFFSET C-5)."),
            },
        }

    def lag_sources(self):
        return {}

    def preregistered_contrasts(self):
        return load_preregistered_contrasts()

    def prereg_digest_expected(self):
        return preregistered_contrast_digest()

    def requires_franchise_continuity(self):
        # A02 is not in P33 p23_franchise_continuity_precondition's arm list.
        return False

    def p23_receipts(self):
        return []

    def p27_rule(self):
        """The card's own registered S7-style fold-local fallback (p26_k0_record.fold_local_
        fallback): 'exact own=opp across a whole training fold -> arm/fold prospectively
        UNEVALUABLE', numeric trigger sd(contrast)==0 on training rows. Expressed as a P27
        ActiveSetRule with min_std pinned at the card's degeneracy threshold and
        min_nonzero_clusters disabled (0), so only the variance criterion is live.
        """
        rule_kwargs = {
            "rule_id": "A02_S7_CONTRAST_DEGENERACY_v1",
            "min_nonzero_clusters": 0,
            "min_std": 1e-08,
            "rationale": ("card-frozen fold-local fallback: "
                         "sd(contrast_own_minus_opp_pace_estimate)==0 on training rows -> "
                         "arm/fold prospectively UNEVALUABLE (P35 A02 card "
                         "p26_k0_record.fold_local_fallback)"),
        }
        spec = {
            "rule_id": rule_kwargs["rule_id"],
            "min_nonzero_clusters": int(rule_kwargs["min_nonzero_clusters"]),
            "min_std": float(rule_kwargs["min_std"]),
            "rationale": rule_kwargs["rationale"],
            "conditions_on": "SupportSummary (training-fold counts only)",
            "applied_to": "candidate AND null, identically, once per fold",
        }
        prereg_kwargs = {
            "registered_at_utc": (
                "UNPINNED_BY_P35_CARD: the P35 SPEC.json freezes this rule by content (task_cards"
                "[A02].p26_k0_record.fold_local_fallback) but carries no separate registration "
                "timestamp for it; this module records the P36 implementation date "
                "2026-08-06T00:00:00Z as a receipted lower bound and flags the gap for P37."),
            "registered_by": "P36_IMPLEMENT_ARMS/A02 (task card frozen at P35, hash-pinned)",
            "rule_spec_sha256": _canonical_digest(spec),
            "results_visible_at_registration": False,
            "record_path": ("experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json"
                           "#task_cards[A02_cal_blend_contrast].p26_k0_record.fold_local_fallback"),
        }
        return (rule_kwargs, prereg_kwargs)


# ------------------------------------------------------------------------------ kill conditions
def evaluate_kill_conditions(receipt: dict) -> dict:
    """Decide the card's frozen kill conditions from a run_arm() receipt alone.

    Card (kill_conditions_frozen, verbatim): "gamma = 0 not rejected (UNCORRECTED 95%
    training-cluster interval covers 0 in every evaluable fold) AND no out-of-fold improvement;
    sign flip of gamma-hat across folds; S7 near-collinearity with offset in any fold (yields to
    A01's question, which is itself structurally unanswerable -- recorded, the yield is to the
    incumbent)."

    This function is pure post-processing of the receipt's own JSON-safe fields; it computes no
    new fit and inspects no comparative historical performance -- it is decidable from
    structure, not from a real result.
    """
    evaluable = [e for e in receipt["folds"] if e.get("status") == "EVALUABLE"]
    per_fold = {}
    zero_not_rejected_all = True
    signs = []
    for e in evaluable:
        fid = e["fold_id"]
        interval = e["train_refit"]["arm_intervals"].get(TREATMENT_COL)
        covers_zero = None
        if interval is not None and interval["lo"] is not None:
            covers_zero = bool(interval["lo"] <= 0.0 <= interval["hi"])
            zero_not_rejected_all &= covers_zero
        else:
            zero_not_rejected_all = False  # no effective draws: cannot claim non-rejection
        cols = e["point_fits"]["arm"]["column_names"]
        beta = e["point_fits"]["arm"]["beta"]
        gamma_hat = None
        if TREATMENT_COL in cols:
            gamma_hat = float(beta[cols.index(TREATMENT_COL)])
            if gamma_hat != 0.0:
                signs.append(np.sign(gamma_hat))
        per_fold[fid] = {"interval": interval, "covers_zero": covers_zero,
                         "gamma_hat": gamma_hat}

    sign_flip = len(set(signs)) > 1

    pooled = receipt["results"].get("pooled")
    no_oof_improvement = None
    if pooled is not None:
        # improvement := arm beats null, i.e. delta_mae = mae_null - mae_arm > 0
        no_oof_improvement = not (pooled["delta_mae"] > 0.0)

    kill_beta_zero_and_no_improvement = bool(
        evaluable and zero_not_rejected_all and (no_oof_improvement is True))

    # S7: surfaced from the P25 per-fold audit's measured near-affinity statistic, if present.
    # A blocking near-affinity finding would already have raised GuardHarnessFailure before a
    # receipt could be built, so this is a diagnostic read of the passing measurement, not a
    # second gate.
    s7_measurements = {}
    for fid, rec in receipt["guard_records"].get("p25_per_fold", {}).items():
        s7_measurements[fid] = {
            k: rec.get(k) for k in ("passed", "blocking") if k in rec
        }

    return {
        "schema": "p36_a02_kill_conditions/1",
        "arm_id": ARM_ID,
        "n_evaluable_folds": len(evaluable),
        "per_fold": per_fold,
        "kill_beta_zero_not_rejected_and_no_oof_improvement": kill_beta_zero_and_no_improvement,
        "zero_not_rejected_in_every_evaluable_fold": zero_not_rejected_all if evaluable else None,
        "no_out_of_fold_improvement": no_oof_improvement,
        "kill_sign_flip": sign_flip,
        "s7_near_collinearity_per_fold": s7_measurements,
        "any_kill_fired": bool(kill_beta_zero_and_no_improvement or sign_flip),
    }
