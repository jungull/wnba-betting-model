#!/usr/bin/env python3
"""a08_arm.py -- A08_league_lag_level arm module, RUNNER_INTERFACE.md conformant.

Card: P35_FREEZE_TASK_CARDS/SPEC.json (sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards.A08.

OWNERSHIP: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A08/ only. This module
IMPORTS the frozen runner contract (runner_constants, runner_interface) READ-ONLY, to build
conformant records and to reuse frozen validation -- it edits nothing under runner/.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

Model (frozen, verbatim): log E[y] = log_exposure + beta0*d_t + gamma*L_t; mu = exp(log-predictor);
NO global intercept in arm or null. Two enumerated elements, K in {20, 80}, each fitted end-to-end
as its own module instance -- one arm-module instance binds exactly one enumeration element
(RUNNER_INTERFACE.md section 1).
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

import runner_constants as rc                  # noqa: E402  (frozen; imported, never edited)
import features as feat                         # noqa: E402  (this unit's own module)

CARD_ID = "A08_league_lag_level"
K_ELEMENTS = (20, 80)


def element_id_for(K: int) -> str:
    return f"A08_K{K}"


class A08Arm:
    """One instance = one enumeration element (fixed K). arm_id is shared across elements."""

    arm_id = CARD_ID

    def __init__(self, history: pd.DataFrame, K: int, fold_ids, n_rows: int,
                pace_col: str = "pace"):
        if K not in K_ELEMENTS:
            raise ValueError(f"K={K} is not a frozen A08 enumeration element; must be one of "
                             f"{K_ELEMENTS} (P35 task_cards.A08.hyperparameters)")
        self._history = history
        self._K = int(K)
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows)
        self._pace_col = pace_col

    # ---- metadata hooks ------------------------------------------------------------------
    def card_id(self) -> str:
        return CARD_ID

    def declared_family(self) -> str:
        return rc.DECLARED_FAMILY_ALL_FITTED_ARMS          # "SUBSTANTIVE" (P35 pinned)

    def recalibration_declaration(self) -> str:
        return rc.RECALIBRATION_DECLARATION                # "NOT_APPLICABLE" (P35 pinned)

    def enumeration_element(self) -> dict:
        return {"K": self._K}

    def element_id(self) -> str:
        return element_id_for(self._K)

    def uses_global_intercept(self) -> bool:
        return False                                        # A08 in ARMS_WITHOUT_GLOBAL_INTERCEPT

    # ---- design ----------------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        targets = pd.DataFrame({
            "game_date": universe["game_date"].to_numpy(),
            "game_id": universe["game_id"].to_numpy(),
            "team_id": universe["team_id"].to_numpy(),
        })
        out = feat.compute_features(self._history, targets, self._K, pace_col=self._pace_col)
        d_t = out["d_t"]

        train_idx = np.asarray(fold["train_idx"], dtype=int)
        train_mask = np.zeros(len(universe), dtype=bool)
        train_mask[train_idx] = True
        lbar_train, L_t = feat.center_L(out["L_raw"], out["windowed_defined"], train_mask)

        return {
            "treatment_cols": ["L_t"],
            "nuisance_cols": ["d_t"],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": ["d_t"],
                                  "comparison": "term_removal"},
            "indicator_cols": [],
            "columns": {"d_t": d_t, "L_t": L_t},
            "diagnostics": {
                "K": self._K, "fold_id": str(fold.get("fold_id")),
                "lbar_train": lbar_train,
                "n_rows": int(len(universe)),
                "n_prewindow_rows": int((~out["windowed_defined"]).sum()),
                "n_zero_own_prior_rows": int((out["n_prior_own"] == 0).sum()),
            },
        }

    # ---- P26 ----------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = {
            "intercept_treatment": "none -- no global intercept in arm or null (P35 intercept_"
                                   "structure: A08 in ARMS_WITHOUT_GLOBAL_INTERCEPT)",
            "calibration_freedom": "none -- no post-fit rescaling of any kind",
            "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
            "exposure_offset": f"{rc.OFFSET_COL} = log({rc.INCUMBENT_PROJECTION_COL})",
            "training_rows": f"rows:n={self._n_rows}:contract_schedule_clock",
            "evaluation_rows": f"rows:n={self._n_rows}:contract_schedule_clock",
            "chronological_folds": list(self._fold_ids),
            "clipping": "none",
            "link_function": "log",
            "preprocessing": "none -- raw constructed columns (d_t, L_t); see features.py",
            "missing_value_handling": ("empty-window symmetric zero-fill: d_t := 0 at zero own "
                                       "prior games; L_t := 0 for rows with fewer than K "
                                       "strictly-earlier completed league games (P35 A08 FOLDS "
                                       "F1/OPERATIONAL OP-3); identical in arm and null"),
            "companion_components": "none",
            "fallback_rules": "symmetric training-support-based window rule (R12 discipline), "
                              "identical in arm and null",
            "aggregation": "none -- the unit of prediction is the team-game",
            "candidate_universe": "contract-schedule team-game rows",
            "post_processing": "none",
            "prediction_universe": "contract-schedule team-game rows",
        }
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "level_transport",
            "treatment_mechanism": {
                "statement": "trailing realized league pace over the last K completed league "
                             "games (strictly before game_date(g)) carries residual level "
                             "information the frozen offset lags",
                "treatment_terms": ["L_t"],
                "tested_parameters": [{"name": "gamma", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "offset already tracks league level"}],
                "claimed_signal_axes": ["league_time"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        "removing L_t leaves only the offset and d_t (the team's own flat "
                        "lagged deviation); no column remaining in the null carries any trailing "
                        "LEAGUE-WIDE time-varying level information, so the league-time-transport "
                        "mechanism is fully destroyed by term removal. A team-identity "
                        "permutation control is explicitly NOT a valid null for this arm (S9, "
                        "P33 k0_matched, carried verbatim): L_t is common across teams within a "
                        "date window, so permuting team identity leaves the league-level time "
                        "signal completely intact.")}},
            "invariants": {
                "rows": f"rows:n={self._n_rows}:contract_schedule_clock",
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": list(self._fold_ids),
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": ["d_t"],
                "lower_order_structural_terms": []},
            "arm_spec": {
                "name": "arm", "role": "challenger", "pipeline_id": rc.RUNNER_VERSION,
                "substantive_features": ["L_t"],
                "structural_terms": ["d_t"],
                "declaration_routing": {"L_t": "substantive_features", "d_t": "preprocessing"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "k0", "role": "k0", "pipeline_id": rc.RUNNER_VERSION,
                "substantive_features": [],
                "structural_terms": ["d_t"],
                "declaration_routing": {"d_t": "preprocessing"},
                "comparison_gate_sidespec": side},
            "fold_local_fallback": {"required": False,
                                    "trigger": "not_applicable -- no partition term "
                                               "(the K-window empty-window rule is a symmetric "
                                               "zero-fill, not a fold-collapse partition)",
                                    "numeric_threshold": None, "action": "not_applicable",
                                    "registered_before_results": True},
            "verdict_label_policy": "level_transport arm: eligible for feature-value labeling "
                                    "only if it survives the Holm-corrected primary gate within "
                                    "the timeseries_shrinkage family (P35 multiplicity_recomputed)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
        }

    # ---- guards ----------------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale_common = (
            "computed strictly from contract-schedule rows whose (game_date, game_id) precedes "
            "the target row's own game (construction_pins.a08_window_tie_break / "
            ".d_t_league_mean_pin); declared DERIVED_NO_JOIN rather than PRIOR_GAME because the "
            "frozen P22 postgame_surrogate_guard.verify_prior_game_lag re-derivation supports "
            "only a single shift(n_back), not an aggregate over a K-game (or all-prior) window -- "
            "this module's OWN strict-lagging identity tests (tests/test_a08.py) independently "
            "verify the strict '< game_date(g)' property the P22 shift-1 verifier cannot check "
            "for a windowed aggregate; flagged for P37/P38 rather than silently claimed as "
            "PRIOR_GAME-verified.")
        return {
            "d_t": {"column": "d_t", "kind": "DERIVED_NO_JOIN",
                   "source_artifact_id": "team_possession_prior_v1",
                   "rationale": "team's own ALL-PRIOR (K-free) lagged mean deviation from the "
                                "ALL-PRIOR K-free league mean. " + rationale_common},
            "L_t": {"column": "L_t", "kind": "DERIVED_NO_JOIN",
                   "source_artifact_id": "team_possession_prior_v1",
                   "rationale": f"trailing K={self._K}-game league-level deviation, centered on "
                                f"the training-fold constant. " + rationale_common},
        }

    def lag_sources(self) -> dict:
        return {}          # DERIVED_NO_JOIN declares no PRIOR_GAME re-derivation source; see
                            # lag_specs() rationale above (flagged, not silently resolved)

    def preregistered_contrasts(self):
        return None          # A08 carries no "contrast_"-named column

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        return True           # P33 precondition: P23 franchise-continuity receipt (carried)

    def p23_receipts(self) -> list:
        return [{"team_cities_sha256": rc.TEAM_CITIES_SHA256_PIN,
                 "note": "A08 requires the franchise-continuity receipt per P33 precondition / "
                         "P35 shared_frozen_amendments.franchise_continuity_receipt_pin"}]

    def p27_rule(self):
        return None            # A08 registers no P27 S7 active-set rule; its live risk is the
                                # P25 near-affinity-vs-offset gate (task_cards.A08.kill_conditions_
                                # frozen), not a P27 fold-collapse partition


# ---------------------------------------------------------------------------------------------
# kill-condition decidability (task_cards.A08.kill_conditions_frozen, verbatim):
#   "P25 rejection at invocation (withdrawal, design failure, before any performance number);
#    gamma interval covers 0 in every evaluable fold; sign instability"
# This is a pure decision function over already-computed per-fold gamma intervals -- it fits no
# model and reads no comparative performance; it exists so the card's kill hooks are DECIDABLE
# and independently testable (see tests/test_a08.py::test_kill_condition_hooks_decidable).
# ---------------------------------------------------------------------------------------------
def decide_kill(gamma_by_fold: dict, *, p25_rejected: bool = False) -> dict:
    """gamma_by_fold: {fold_id: {"point": float, "ci_low": float, "ci_high": float}}."""
    if p25_rejected:
        return {"schema": "a08_kill_decision/1", "killed": True, "reason": "p25_rejection",
                "basis": "P35 task_cards.A08.kill_conditions_frozen",
                "per_fold_covers_zero": {}, "interval_kill": None, "sign_kill": None}

    covers_zero = {}
    for fid, v in gamma_by_fold.items():
        lo, hi = float(v["ci_low"]), float(v["ci_high"])
        if lo > hi:
            raise ValueError(f"malformed interval for fold {fid}: ci_low > ci_high")
        covers_zero[fid] = bool(lo <= 0.0 <= hi)
    interval_kill = bool(gamma_by_fold) and all(covers_zero.values())

    signs = set()
    for fid, v in gamma_by_fold.items():
        if not covers_zero[fid]:
            signs.add(1 if float(v["point"]) > 0 else -1)
    sign_kill = len(signs) > 1

    return {"schema": "a08_kill_decision/1",
            "killed": bool(interval_kill or sign_kill),
            "reason": ("interval_covers_zero_every_evaluable_fold" if interval_kill else
                      "sign_instability" if sign_kill else "not_killed"),
            "basis": "P35 task_cards.A08.kill_conditions_frozen",
            "per_fold_covers_zero": covers_zero,
            "interval_kill": interval_kill, "sign_kill": sign_kill}
