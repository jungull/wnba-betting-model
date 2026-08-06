#!/usr/bin/env python3
"""arm_a26.py -- P36 arm module for A26_sos_correction_own_minus_opp.

FROZEN CARD THIS IMPLEMENTS (verbatim binding source): P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[arm_id ==
"A26_sos_correction_own_minus_opp"], carrying the P33_PREREGISTRATION_DRAFT/SPEC.json arm record
(sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) by hash reference per the
card's carry_convention, amended only by the card's own ``amendments_applied``. Every pinned clock,
window, centering constant and enumeration element below is taken from those two documents plus the
originating hypothesis record named in feature_construction.py's module docstring; nothing here is
invented beyond what those sources say.

MODEL (P35 task card, verbatim): eta = log_exposure + beta5 * z5; z5 = c_own - c_opp, c_t =
-sched_t; mu = exp(eta); NO global intercept (P35 intercept_structure: A26 is in
ARMS_WITHOUT_GLOBAL_INTERCEPT). RAW counts per D9 (no OT reweighting -- convention distinct from
A12/A16, never harmonized; P33 D9: "A26 raw with unmeasured symmetric-cancellation assertion
preserved as unmeasured").

SINGLE ELEMENT: P33 hyperparameters.enumerated is {} ("frozen by source"); the arm carries no
genuine multi-value grid (E_min_prior_games=3 is a FIXED constant, not an enumerated element).
RUNNER_INTERFACE.md section 1: "{} for single-element arms" -- this module binds exactly one arm
instance, no variant family.

K0_MATCHED (P35 k0_matched_frozen, verbatim): null = "identical machinery incl. the
E=3-plus-undefined-LOO imputation; treatment adds ONLY z5; league-mean centering is feature
DEFINITION, not design change" (comparison: term_removal). The null requests NO nuisance term, so
K0's design is exactly [log_exposure] -- zero fitted parameters, IS the frozen incumbent exactly
(P35 intercept_structure names only A02/A03/A05/A16/A25 by name as zero-parameter-null arms, but --
exactly as A18's and A20's own modules independently note for their own cards -- A26's OWN card
independently states "treatment adds ONLY z5" with no nuisance term requested; the zero-parameter
null follows directly from that plus the no-intercept pin, and is stated here, not silently
assumed. Flagged, same as A18/A20, as a document-completeness note for P37, not resolved by
editing the P35 consequence sentence).

DATA SOURCE AND WHY THIS MODULE IS A CLASS, NOT A PLAIN MODULE: z5's construction needs raw
per-team-game possession row counts (``raw_t``), which are NOT columns of the shared team-game
universe ``possession_features.load_universe`` builds (that universe carries pace-estimate and
target columns, not possession-level row counts -- the same gap A20's module docstring measures
for ``end_reason``/``defense_team_id``). Constructing ``raw_t`` therefore requires possession-level
rows from ``possessions_raw_v2`` beyond what RUNNER_INTERFACE.md's frozen ``build_design(fold,
universe)`` signature can carry. This program's precedent for exactly this situation is A13/A20
(auxiliary frame bound at CONSTRUCTION time, whose bound methods are the RUNNER_INTERFACE hooks).
``ArmA26`` follows the same convention with one auxiliary frame, ``possessions_raw`` (game_id,
offense_team_id -- the possession-level columns the card's mechanism needs; read-only, never
mutated). The schedule/identity keys the LOO strength-of-schedule term needs (team_id, opp_team_id,
game_id, game_date, season) come from ``universe`` itself at ``build_design`` call time, exactly as
A16/A18/A20 read their own schedule keys from ``universe``.

K0's LOO CONSTRUCTION IS SHARED: the P35 card's null explicitly carries the "identical machinery
incl. the E=3-plus-undefined-LOO imputation" -- there is no separate null-side LOO computation;
the null's design simply omits the z5 COLUMN (K0 = [log_exposure], term_removal), so this module's
single ``feature_construction.compute_features`` call, run once per fold, serves BOTH members
identically (the same posture A18/A20/A16 already document for their own zero-nuisance nulls).

FRANCHISE CONTINUITY: A26 is NOT named in P33 shared_arm_invariants.p23_franchise_continuity_
precondition's arm list (A08, A09, A10, A11, A12, A13, A14, A16, A17, A19, A21, A22, A24 -- A26 is
absent, matching A18's and A20's own absence from that same list). This tracks the mechanism
itself: every quantity z5 depends on (``raw_t``, ``sched_t``, the league trailing mean) is
explicitly SAME-SEASON-restricted (see feature_construction.py's module docstring); it never
crosses a season boundary and never touches the PHO/PHX cross-season rebrand issue the P23 receipt
exists for. ``requires_franchise_continuity()`` is therefore False and ``p23_receipts()`` returns
``[]``.

LAG DECLARATION: z5 is declared DERIVED_NO_JOIN, not PRIOR_GAME -- a nested leave-one-out mean over
a variable-length, cross-team set of strictly-earlier possession-level aggregates is not the
single-column groupby+shift(n_back) postgame_surrogate_guard.verify_prior_game_lag can re-derive
(same posture as A11's dblend_t(rho), A16's dev_own - dev_opp, and A18's/A20's own pooled/expanding
aggregates).

Epistemic status of this file: IMPLEMENTATION. Blinded: no challenger performance is inspected here
or anywhere in this module. Only unit, synthetic, identity and schema tests exist for it
(TESTS.py in this directory).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_RUNNER = _HERE.parents[1] / "runner"          # stage2b/P36_IMPLEMENT_ARMS/runner -- READ ONLY
for _p in (str(_RUNNER), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import feature_construction as feat              # noqa: E402  (this unit's own module)
import runner_constants as rc                     # noqa: E402  (frozen; imported, never edited)

ARM_ID = "A26_sos_correction_own_minus_opp"
P35_SPEC_SHA256 = rc.P35_SPEC_SHA256

TREATMENT_COL = "z5"                              # P35 k0_matched_frozen.treatment_terms[0]

# S7 near-affinity thresholds: the SAME numeric pins A07's frozen card names for its own S7
# condition-number check ("near-affinity thresholds R2 >= 0.998001 / |spearman| >= 0.999") --
# reused here, not re-invented, exactly as A18's own module reuses them for its own additional
# pace_gap comparand. A26's own expected_failure_mode (P33) names this explicitly: "most likely
# death is WITHDRAWAL ... P25 finding z5 near-affine in the offset or pace_gap within training
# folds". Standard P25 invocation checks only against the offset (log_exposure); the "or pace_gap"
# clause is the task-specific measurement standing rule 3 requires (never a shared-gate edit).
NEAR_AFFINITY_R2 = 0.998001
NEAR_AFFINITY_SPEARMAN = 0.999


def _row_digest(n: int) -> str:
    return f"rows:n={n}:contract_schedule_or_synthetic"


def _sidespec(fold_ids, n_rows) -> dict:
    return {
        "intercept_treatment": ("none -- no global intercept in arm or null (P35 intercept_"
                                "structure: A26 in ARMS_WITHOUT_GLOBAL_INTERCEPT)"),
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{rc.OFFSET_COL} = log({rc.INCUMBENT_PROJECTION_COL}), frozen "
                           "incumbent D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": _row_digest(n_rows),
        "evaluation_rows": _row_digest(n_rows),
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": ("none -- z5 enters untransformed, RAW possession-count scale (P33 D9: "
                          "raw counts, no OT reweighting); no standardisation beyond the league-"
                          "mean centering that is part of z5's own feature DEFINITION (P35 "
                          "k0_matched_frozen: 'league-mean centering is feature DEFINITION, not "
                          "design change')"),
        "missing_value_handling": (
            "E=3-plus-undefined-LOO deterministic symmetric imputation: z5 := 0 when EITHER team "
            f"has fewer than {feat.E_MIN_PRIOR_GAMES} distinct strictly-earlier same-season games, "
            "OR either side's leave-one-out schedule-correction mean cannot be formed because a "
            "required opponent has no OTHER strictly-earlier-than-target-date same-season game "
            "besides the one meeting being excluded (P33 hyperparameters.fixed.imputation; P35 "
            "fold_local_fallback). Identical machinery in arm and null: the null carries no z5 "
            "term at all, so the rule is vacuously satisfied there, but no IMPLEMENTATION-side "
            "difference in fallback machinery exists between the two designs"),
        "companion_components": "none",
        "fallback_rules": (
            "E=3-plus-undefined-LOO imputation (above); P33 k0_matched.fold_local_fallback: "
            "'none needed'"),
        "aggregation": "none -- the unit of prediction is the team-game row",
        "candidate_universe": "the contract-schedule team-game universe (synthetic in tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A26Arm:
    """The single A26 module instance (no enumerated grid; RUNNER_INTERFACE.md section 1)."""

    arm_id = ARM_ID

    def __init__(self, possessions: pd.DataFrame, fold_ids, n_rows: int):
        """``possessions``: a per-possession frame carrying game_id, offense_team_id --
        possessions_raw_v2 at P38 time (frozen sha256
        7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a, runner_constants.
        REAL_ARTIFACT_SHA256), a synthetic possession-level fixture in tests. Threaded at
        CONSTRUCTION time, per the A13/A18/A20 pattern (the module's build_design(fold, universe)
        signature carries no slot for a second data source, so per-arm auxiliary data is bound
        when the module instance is built)."""
        missing = [c for c in feat.REQUIRED_POSSESSIONS_COLS if c not in possessions.columns]
        if missing:
            raise KeyError(f"A26Arm requires columns {missing} on the supplied possessions frame")
        self._possessions = possessions
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows)

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
        return ARM_ID

    def uses_global_intercept(self) -> bool:
        return False                                          # A26 in ARMS_WITHOUT_GLOBAL_INTERCEPT

    def requires_franchise_continuity(self) -> bool:
        # A26 is absent from P33 shared_arm_invariants.p23_franchise_continuity_precondition's arm
        # list, and A26's construction never looks past the row's own season start (same-season
        # only, throughout: raw_t, sched_t, and the league trailing mean).
        return False

    def p23_receipts(self) -> list:
        return []

    def p27_rule(self):
        # P33's A26 card: "fold_local_fallback": "none needed". No S7 active-set-rule registry
        # entry names A26 (only A03, A12, A13, A14 do, per the P35 registry_append payloads). No
        # rule is frozen for A26 at P35.
        return None

    def preregistered_contrasts(self):
        # A26 carries no P25-preregistered contrast record (that obligation is A02's alone --
        # P35 p25_guard_invocation_pins.a02_contrast_reconciliation).
        return None

    def prereg_digest_expected(self):
        return None

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold, universe) -> dict:
        """z5 is NOT fold-dependent: it is a deterministic, strictly-lagged, same-season historical
        fact of the row's own team_id/opp_team_id/game_date/season (like A16's dev_own - dev_opp,
        A18's z1, and A20's z2), so the SAME construction runs for every fold and for the
        FINAL_ASSEMBLED_DESIGN pseudo-fold; ``fold`` is accepted per the frozen §3 signature and
        not otherwise used.
        """
        del fold  # signature-required, unused: see docstring
        for col in feat.REQUIRED_UNIVERSE_COLS:
            if col not in universe.columns:
                raise KeyError(f"A26 build_design requires column '{col}' on the universe frame")
        res = feat.compute_features(self._possessions, universe)
        z5 = res["z5"]
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {
                "treatment_cols": [],
                "nuisance_cols": [],
                "comparison": "term_removal",
            },
            "indicator_cols": [],
            "columns": {TREATMENT_COL: z5},
            "diagnostics": {
                "n_rows": int(len(universe)),
                "n_imputed_rows": int(np.sum(res["imputed"])),
                "n_own_lt_3": int(np.sum(res["n_own"] < feat.E_MIN_PRIOR_GAMES)),
                "n_opp_lt_3": int(np.sum(res["n_opp"] < feat.E_MIN_PRIOR_GAMES)),
            },
        }

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids, self._n_rows)
        rows = _row_digest(self._n_rows)
        folds = list(self._fold_ids)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": (
                    "a team's raw trailing pace signature is confounded by the opponents it "
                    "happened to draw; z5 is the leave-one-out strength-of-schedule CORRECTION "
                    "contrast (own minus opponent) -- the piece of that adjustment an offset built "
                    "on raw trailing signatures cannot contain. z5 tests whether this correction "
                    "carries information beyond the incumbent's count-based offset"),
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{
                    "name": "beta5", "role": "coefficient", "null_value": 0.0,
                    "null_value_meaning": "incumbent already implicitly schedule-adjusts",
                }],
                "claimed_signal_axes": ["team_identity", "opponent_identity"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        "removing z5 leaves eta = log_exposure exactly, i.e. the frozen incumbent "
                        "projection with zero fitted parameters; no schedule-correction quantity "
                        "of any kind remains in the design (P35 A26 card: 'treatment adds ONLY "
                        "z5')"),
                },
            },
            "invariants": {
                "rows": rows,
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": folds,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["missing_value_handling"],
                "nuisance_terms": [],
                "lower_order_structural_terms": [],
            },
            "arm_spec": _side("A26_arm", "challenger", [TREATMENT_COL], [], side),
            "k0_spec": _side("A26_k0", "k0", [], [], side),
            "fold_local_fallback": {
                "required": True,
                "trigger": (f"either team has fewer than {feat.E_MIN_PRIOR_GAMES} distinct "
                           "strictly-earlier same-season games (own or opponent side), OR either "
                           "side's leave-one-out schedule-correction mean is undefined -> "
                           "z5 := 0 (P33 hyperparameters.fixed.imputation; P35 model clause, "
                           "verbatim)"),
                "numeric_threshold": feat.E_MIN_PRIOR_GAMES,
                "action": "not_applicable",  # no frozen enum value names deterministic value
                                             # substitution for a nested LOO schedule-correction
                                             # aggregate; same posture as A16's/A18's/A20's
                                             # p26_k0_record docstring notes, flagged for P37
                                             # rather than inventing a fifth schema enum value
                "registered_before_results": True,
            },
            "verdict_label_policy": (
                "eligible for FEATURE VALUE DEMONSTRATED via challenger_vs_k0 against this record "
                "(arm_kind substantive_feature; NOT calibration_only, so no verdict-label ceiling "
                "applies)"),
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "P35 shared_frozen_amendments.multiplicity_recomputed.families_this_cycle: "
                "OPPONENT_MECHANISM_F1, members {A18: 1, A20: 1, A26: 1}, budget_elements 3, "
                "Holm alpha 0.05.",
                "P33 D9: three OT conventions frozen PER-ARM (A12 rescale; A16 regulation-"
                "equivalent normalization; A26 raw with unmeasured symmetric-cancellation "
                "assertion preserved as unmeasured); explicitly NOT harmonized. P35 amendment "
                "TARGETUNITS C3 brackets the OT prevalence (66/1,491 games, 4.43%) as a noise "
                "channel that can only hurt A26 against its own null; the symmetric-cancellation "
                "assertion itself remains preserved-as-unmeasured.",
                "P35 amendments_applied 'LEAKAGE L6': the LOO-as-of-date ambiguity REVIEW_LEAKAGE."
                "md L6 raised (meeting date j vs target date g) is PINNED to g, one clock, "
                "deterministic; implemented exactly in feature_construction.py.",
            ],
        }

    # ---- guards -----------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale = (
            "z5 = c_own - c_opp; c_t = -(sched_t - Lbar); sched_t is a leave-one-out mean, over a "
            "team's STRICTLY EARLIER SAME-SEASON games, of each historical opponent's own raw "
            "possession-count mean (itself computed leave-one-out, excluding the specific meeting, "
            "and evaluated as of the TARGET row's own game date -- P35 'LEAKAGE L6' one-clock pin, "
            "not as of each historical meeting's own date). This is a NESTED, cross-team, "
            "variable-length aggregate over possession-level rows -- not a single-column "
            "groupby+shift(n_back) lag -- so postgame_surrogate_guard.verify_prior_game_lag's "
            "generic PRIOR_GAME re-derivation contract cannot verify it (the same limitation A11's "
            "dblend_t(rho), A16's dev_own - dev_opp, A18's pooled median and A20's expanding mean "
            "already document for their own multi-row aggregates). DERIVED_NO_JOIN is therefore "
            "the honest declared kind; the source data here (possession-level offense_team_id row "
            "counts) is NOT already present in the team-game universe frame this module receives "
            "at build_design() time -- it is threaded in at MODULE CONSTRUCTION as a separate "
            "possession-level frame (possessions_raw_v2 at P38 time), so the join from "
            "possession-level to team-game-level happens once, in __init__, before build_design "
            "ever runs, and is never repeated inside a fold loop (A18's and A20's own precedent). "
            "Strict lagging is established directly by identity/synthetic tests in this unit "
            "(TESTS.py): a row's z5 is shown to be invariant to perturbing its OWN game's "
            "possessions and to perturbing any LATER game's possessions, and responsive to "
            "perturbing an EARLIER same-team same-season game's possessions."
        )
        return {
            TREATMENT_COL: {
                "column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                "source_artifact_id": "possessions_raw_v2/via_module_construction",
                "rationale": rationale,
            },
        }

    def lag_sources(self) -> dict:
        # DERIVED_NO_JOIN skips PRIOR_GAME re-derivation (postgame_surrogate_guard.audit only
        # calls verify_prior_game_lag for kind == PRIOR_GAME); no source frame is required or
        # supplied here (same as A11/A16/A18/A20).
        return {}


def _side(name: str, role: str, substantive: list, structural: list, dims: dict) -> dict:
    import copy
    return {
        "name": name, "role": role, "pipeline_id": rc.RUNNER_VERSION,
        "substantive_features": list(substantive), "structural_terms": list(structural),
        "declaration_routing": {t: "substantive_features" for t in substantive},
        "comparison_gate_sidespec": copy.deepcopy(dims),
    }


def make_arm(possessions: pd.DataFrame, fold_ids, n_rows: int) -> list:
    """One module instance -- A26 has no enumerated grid (RUNNER_INTERFACE.md section 1: '{} for
    single-element arms'). Returned as a length-1 list for interface symmetry with A08/A09/A11/
    A18/A20's ``make_arms``."""
    return [A26Arm(possessions, fold_ids, n_rows)]


# ---------------------------------------------------------------------------------------------
# kill-condition decidability (task_cards.A26.kill_conditions_frozen, verbatim):
#   "interval covers 0 or no primary-gate improvement; P25 withdrawal (design failure - the
#    incumbent's construction already implicitly schedule-adjusts)"
# P33's own A26 card additionally names "P25 margin vs offset and pace_gap" as a secondary
# diagnostic and states the expected_failure_mode explicitly: "most likely death is WITHDRAWAL
# before any performance number - P25 finding z5 near-affine in the offset or pace_gap within
# training folds". The standard P25 invocation (guard_harness.p25_check) tests near-affinity
# against the OFFSET only (P35 p25_guard_invocation_pins: offset = log_exposure,
# incumbent_projection = projected_team_off_possessions). "or pace_gap" names an ADDITIONAL
# comparand -- A02's contrast_own_minus_opp_pace_estimate column -- that the standard guard
# invocation does not check. Per standing rule 3 (enforcement at the call site, never editing a
# shared gate), this is a task-specific measurement this module supplies, not a change to
# offset_dependency_guard.py. near_affinity_against() below is a pure measurement function;
# decide_kill() is a pure decision function over already-computed inputs. Neither fits a model
# nor reads comparative performance.
# ---------------------------------------------------------------------------------------------

def near_affinity_against(z5: np.ndarray, comparand: np.ndarray) -> dict:
    """R2 (OLS, one predictor) and Spearman |rho| of z5 against `comparand` on one training fold.
    Uses the SAME frozen thresholds A07's/A18's cards name for their own S7 near-affinity check
    (NEAR_AFFINITY_R2 = 0.998001, NEAR_AFFINITY_SPEARMAN = 0.999): near-affine if EITHER is met.
    """
    z5 = np.asarray(z5, dtype=float)
    comparand = np.asarray(comparand, dtype=float)
    m = np.isfinite(z5) & np.isfinite(comparand)
    if int(m.sum()) < 3 or np.std(z5[m]) == 0.0 or np.std(comparand[m]) == 0.0:
        return {"r2": None, "spearman": None, "near_affine": False,
                "reason": "insufficient variation to measure"}
    r = float(np.corrcoef(z5[m], comparand[m])[0, 1])
    r2 = r * r
    rank_z5 = pd.Series(z5[m]).rank().to_numpy()
    rank_c = pd.Series(comparand[m]).rank().to_numpy()
    rs = float(np.corrcoef(rank_z5, rank_c)[0, 1])
    near_affine = (r2 >= NEAR_AFFINITY_R2) or (abs(rs) >= NEAR_AFFINITY_SPEARMAN)
    return {"r2": r2, "spearman": rs, "near_affine": bool(near_affine)}


def decide_kill(beta_by_fold: dict, *, near_affinity_offset_by_fold: dict | None = None,
                near_affinity_pace_gap_by_fold: dict | None = None,
                primary_gate_passed: bool | None = None) -> dict:
    """beta_by_fold: {fold_id: {"point": float, "ci_low": float, "ci_high": float}} over
    EVALUABLE folds. near_affinity_*_by_fold: {fold_id: bool} of TRAINING-fold near-affinity
    verdicts (near_affinity_against(...)['near_affine']), keyed the same way. `None` for a dict
    means that comparand was not measured for any fold (recorded, never assumed False).
    """
    covers_zero = {}
    for fid, v in beta_by_fold.items():
        lo, hi = float(v["ci_low"]), float(v["ci_high"])
        if lo > hi:
            raise ValueError(f"malformed interval for fold {fid}: ci_low > ci_high")
        covers_zero[fid] = bool(lo <= 0.0 <= hi)
    interval_kill = bool(beta_by_fold) and all(covers_zero.values())
    gate_kill = (primary_gate_passed is False)

    def _all_true(d):
        return bool(d) and all(bool(v) for v in d.values())

    offset_withdrawal = _all_true(near_affinity_offset_by_fold or {})
    pace_gap_withdrawal = _all_true(near_affinity_pace_gap_by_fold or {})
    withdrawal = offset_withdrawal or pace_gap_withdrawal

    reasons = []
    if interval_kill:
        reasons.append("beta5_interval_covers_zero_every_evaluable_fold")
    if gate_kill:
        reasons.append("primary_gate_failed")
    if withdrawal:
        reasons.append("p25_near_affinity_withdrawal_"
                       + ("offset" if offset_withdrawal else "")
                       + ("+" if offset_withdrawal and pace_gap_withdrawal else "")
                       + ("pace_gap" if pace_gap_withdrawal else ""))

    return {"schema": "a26_kill_decision/1",
            "killed_or_withdrawn": bool(interval_kill or gate_kill or withdrawal),
            "is_withdrawal": bool(withdrawal),
            "reason": "+".join(reasons) if reasons else "not_killed",
            "basis": "P35 task_cards.A26.kill_conditions_frozen",
            "per_fold_covers_zero": covers_zero,
            "interval_kill": interval_kill, "gate_kill": gate_kill,
            "offset_near_affinity_withdrawal": offset_withdrawal,
            "pace_gap_near_affinity_withdrawal": pace_gap_withdrawal}
