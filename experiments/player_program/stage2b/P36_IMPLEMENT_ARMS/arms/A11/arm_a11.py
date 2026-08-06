#!/usr/bin/env python3
"""arm_a11.py -- A11_carryover_blend_rho, the P36 RUNNER_INTERFACE arm module.

Frozen card: experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards[A11]
("A11_carryover_blend_rho"), REPAIRED per D026 exactly as a11_repair words it (K0 K1, Severity
A), amended further by shared_frozen_amendments (intercept_structure, construction_pins,
multiplicity_recomputed.grid_element_regime_pinned, franchise_continuity_receipt_pin).

  model:  log E[y] = log_exposure + beta * dblend_t(rho)
          dblend_t(rho) = (n_cur*dcur_t + rho*m_prev*dprev_t) / (n_cur + rho*m_prev)
          mu = exp(log-predictor); NO global intercept
  K0_MATCHED[A11] (a11_repair.null_pinned): [log_exposure | dblend_t(1)] with FREE beta -- the
          single blended column at rho = 1 (the "undifferentiated pooling reference"; NOT
          incumbent-equivalent -- D1 resolution carried verbatim). comparison =
          parameter_fixed_at_null on rho (null value 1).
  elements: rho in {0.25, 0.5, 0.75}, EACH fitted end-to-end as its own module instance
          (RUNNER_INTERFACE.md section 1: one arm-module instance binds exactly one
          enumeration element; the runner never selects among elements).
  fold-1 (train_lt_2022) is STRUCTURALLY DEACTIVATED for arm AND null identically
          (a11_repair.fold1_evaluability_pinned): dprev_t is undefined (m_prev == 0) on 100% of
          that fold's training rows because the archive's first season has no preceding season.

Per standing rule 3 (enforcement at the call site, never editing a shared gate) and this unit's
write scope (experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A11/ only), this module
imports the FROZEN runner contract (runner_constants, for the pinned column names, the frozen
intercept table and the frozen team_cities.csv hash) but writes nothing outside its own directory
and edits nothing under runner/. It performs no cross-arm import; feature_construction.py
independently re-derives the shared pace/league-mean formula rather than importing another arm's
module (A08/A09 convention, followed here).

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
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

import feature_construction as feat             # noqa: E402  (this unit's own module)
import runner_constants as rc                    # noqa: E402  (frozen; imported, never edited)

ARM_ID = "A11_carryover_blend_rho"
P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"

#: the card's own generic (rho-symbolic) term names, reused VERBATIM as the design's column keys
#: and as the K0_MATCHED treatment_terms entry, per "implement EXACTLY it" / "never improvise".
TREATMENT_COL = "dblend_t(rho)"
NULL_COL = "dblend_t(1)"

STRUCTURALLY_DEACTIVATED_FOLDS = ("train_lt_2022",)   # a11_repair.fold1_evaluability_pinned


def _row_digest(n: int) -> str:
    return f"rows:n={n}:contract_schedule_or_synthetic"


def _sidespec(fold_ids, n_rows) -> dict:
    return {
        "intercept_treatment": "none -- no global intercept in arm or null (P35 intercept_"
                               "structure: A11 in ARMS_WITHOUT_GLOBAL_INTERCEPT)",
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{rc.OFFSET_COL} = log({rc.INCUMBENT_PROJECTION_COL}), frozen "
                           "incumbent D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": _row_digest(n_rows),
        "evaluation_rows": _row_digest(n_rows),
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": ("dcur_t := 0 at n_cur=0; dprev_t := 0 at m_prev=0; dblend_t(rho) := 0 "
                          "at n_cur+rho*m_prev==0 (a11_repair empty_window_rule, deterministic "
                          "and symmetric, arm and null identical); pace(j) = n_off_poss*40/"
                          "(40+5*max(0,max_period-4)) (lagged_regulation_equivalent_pin); Lbar_<g "
                          "is the all-prior, K-free league mean of that pace shared by dcur_t and "
                          "dprev_t (d_t_league_mean_pin)"),
        "missing_value_handling": "none beyond the empty-window rule above (complete-case "
                                  "otherwise)",
        "companion_components": "none",
        "fallback_rules": ("STRUCTURAL DEACTIVATION of fold train_lt_2022, identical in arm and "
                          "null (a11_repair.fold1_evaluability_pinned); no other fold-level "
                          "fallback"),
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the contract-schedule team-game universe (synthetic in tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A11Arm:
    """One A11 module instance == one rho element."""

    arm_id = ARM_ID

    def __init__(self, history: pd.DataFrame, rho: float, fold_ids, n_rows: int):
        if rho not in feat.ENUMERATED_RHO:
            raise ValueError(f"rho={rho} is not one of the frozen P35 elements "
                             f"{feat.ENUMERATED_RHO}")
        self._history = history
        self.rho = float(rho)
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
        return {"rho": self.rho}

    def element_id(self) -> str:
        return f"A11_rho{self.rho}"

    def uses_global_intercept(self) -> bool:
        return False                                          # A11 in ARMS_WITHOUT_GLOBAL_INTERCEPT

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        """dcur_t/dprev_t/n_cur/m_prev are NOT fold-dependent constants (unlike e.g. A13's
        cbar_F): they are deterministic functions of schedule facts strictly earlier than each
        row's own game (dcur_t) or of an entirely-completed prior season (dprev_t), so `fold` is
        accepted (per the frozen §3 contract) but not consulted for their construction. The
        supplied `universe` frame supplies the TARGET keys (team_id, game_id, game_date, season);
        `self._history` -- supplied at construction time, per the A08/A09 pattern -- is the
        contract-schedule frame the n_clock_pin requires for n_cur/m_prev counts.
        """
        for col in ("team_id", "game_id", "game_date", "season"):
            if col not in universe.columns:
                raise KeyError(f"A11 build_design requires column '{col}' on the universe frame")
        targets = pd.DataFrame({
            "team_id": universe["team_id"].to_numpy(),
            "game_id": universe["game_id"].to_numpy(),
        })
        aligned = feat.compute_features(self._history, targets)
        n_cur, dcur = aligned["n_cur"], aligned["dcur"]
        m_prev, dprev = aligned["m_prev"], aligned["dprev"]

        arm_col = feat.dblend(dcur, dprev, n_cur, m_prev, self.rho)
        null_col = feat.dblend(dcur, dprev, n_cur, m_prev, feat.NULL_RHO)

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {"treatment_cols": [NULL_COL], "nuisance_cols": [],
                                  "comparison": "parameter_fixed_at_null"},
            "indicator_cols": [],
            "columns": {TREATMENT_COL: arm_col, NULL_COL: null_col},
            "diagnostics": {
                "rho": self.rho, "fold_id": str(fold.get("fold_id")),
                "n_rows": int(len(universe)),
                "n_cur_le_5_rows": int(np.sum(n_cur <= 5)),
                "n_zero_denom_arm_rows": int(np.sum((n_cur + self.rho * m_prev) <= 0)),
                "n_zero_denom_null_rows": int(np.sum((n_cur + feat.NULL_RHO * m_prev) <= 0)),
            },
        }

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids, self._n_rows)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "hierarchical_pooling",
            "treatment_mechanism": {
                "statement": "Prior-season carryover evidence should be discounted toward zero "
                             "relative to current-season evidence at season boundaries: rho "
                             "sets how strongly the immediately-preceding season's deviation "
                             "dprev_t is downweighted, relative to the current season's own "
                             "dcur_t, inside the blended deviation dblend_t(rho); rho=1 is the "
                             "undifferentiated pooling reference at which prior- and "
                             "current-season evidence enter the blend with EQUAL weight per "
                             "game (no season-boundary discount whatsoever).",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "rho", "role": "shrinkage_weight",
                                       "null_value": 1,
                                       "null_value_meaning": "undifferentiated pooling "
                                                             "reference (NOT incumbent-"
                                                             "equivalent -- D1 resolution "
                                                             "carried)"}],
                "claimed_signal_axes": ["season_time", "support_size"],
                "null_construction": {
                    "method": "parameter_fixed_at_null",
                    "destroys_claimed_signal": "fixing rho at exactly 1 removes the "
                                               "season-boundary discount: prior-season evidence "
                                               "enters dblend_t with the SAME per-game weight as "
                                               "current-season evidence (undifferentiated "
                                               "pooling), destroying the claimed "
                                               "season-boundary carryover-discount mechanism "
                                               "identically across every n_cur/m_prev stratum, "
                                               "while leaving beta free to fit the blended "
                                               "column's overall coefficient exactly as the arm "
                                               "does"}},
            "invariants": {
                "rows": _row_digest(self._n_rows),
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"] + "; " + side["preprocessing"],
                "nuisance_terms": [],
                "lower_order_structural_terms": [NULL_COL]},
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
            "fold_local_fallback": {
                "required": True,
                "trigger": "dprev_t undefined (m_prev==0) on 100% of a fold's training rows -- "
                          "the fold's earliest season has no preceding season in the archive",
                "numeric_threshold": 1.0,
                "action": "refuse_to_score_fold",
                "registered_before_results": True},
            "verdict_label_policy": "hierarchical_pooling result: eligible for a "
                                    "POOLING/SHRINKAGE mechanism verdict against "
                                    "K0_MATCHED[A11] for this rho element, subject to the "
                                    "primary gate and the timeseries_shrinkage family Holm "
                                    "correction (10 elements) / the dual-Holm COLDSTART_FALLBACK "
                                    "alternate (stricter governs); never a standalone 'feature "
                                    "value' claim absent that gate.",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
        }

    # ---- guards -----------------------------------------------------------------------
    def lag_specs(self) -> dict:
        rationale = (
            "dcur_t/dprev_t/dblend_t(rho) are built by feature_construction.py from the supplied "
            "history frame's OWN rows (n_off_poss, max_period, team_id, game_date, season), "
            "restricted per-row to (a) strictly-earlier same-season game_date entries for "
            "dcur_t, and (b) the ENTIRE immediately-preceding season for dprev_t -- which is, by "
            "schedule construction, wholly in the past by the time the current season starts "
            "(P35 n_clock_pin / d_t_league_mean_pin, extended per a11_repair to the seasonal "
            "restriction). No external artifact join is performed by this module -- the supplied "
            "history frame IS the contract-schedule history -- so this is a DERIVED_NO_JOIN "
            "construction, not a PRIOR_GAME single-column shift; postgame_surrogate_guard's "
            "generic PRIOR_GAME re-derivation (a groupby+shift(n_back) check) verifies "
            "single-step lags and cannot verify an all-prior or whole-prior-season aggregate, so "
            "it is not the correct declared kind here. Strict lagging is instead established "
            "directly by identity/synthetic tests in this unit (TESTS.py) against "
            "feature_construction.py's pure functions: a row's dcur_t/dprev_t are shown to be "
            "invariant to perturbing its OWN game outcome and to perturbing any LATER game."
        )
        return {
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "contract_schedule_universe/1",
                            "rationale": rationale + f" rho={self.rho} is a fixed constant of "
                                        "this module instance, never fitted."},
            NULL_COL: {"column": NULL_COL, "kind": "DERIVED_NO_JOIN",
                      "source_artifact_id": "contract_schedule_universe/1",
                      "rationale": rationale + " rho=1 (null) is likewise a fixed constant, "
                                  "never fitted."},
        }

    def lag_sources(self) -> dict:
        return {}                       # DERIVED_NO_JOIN needs no external re-derivation source

    def preregistered_contrasts(self):
        return None

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P35 franchise_continuity_receipt_pin names A11 explicitly: "A11's 'team_id keyed
        # directly, no team_cities join' declaration stands" -- dcur_t/dprev_t are cross-season
        # (current-season and preceding-season) history features, so the PHO/PHX rebrand receipt
        # is required before gate invocation regardless of this module's own team_id-keyed
        # (no team_cities join) construction.
        return True

    def p23_receipts(self) -> list:
        return [{
            "team_cities_sha256": rc.TEAM_CITIES_SHA256_PIN,
            "scope": "A11: dcur_t/dprev_t are keyed directly on team_id across the current and "
                    "immediately-preceding season; no team_cities.csv join is performed by this "
                    "module. This receipt attests the frozen franchise-continuity pin per P35 "
                    "shared_frozen_amendments.franchise_continuity_receipt_pin, which names A11 "
                    "explicitly.",
        }]

    def p27_rule(self):
        # No S7 active-set-rule registry entry names A11 (only A03, A12, A13, A14 do); A11's
        # fold-1 evaluability is a card-pinned STRUCTURAL DEACTIVATION (a11_repair
        # .fold1_evaluability_pinned), expressed via structurally_deactivated_folds() below, not
        # a P27-registered active-set rule.
        return None

    # ---- optional hook (RUNNER_INTERFACE.md section 2a) -------------------------------
    def structurally_deactivated_folds(self) -> list:
        return list(STRUCTURALLY_DEACTIVATED_FOLDS)


def make_arms(history: pd.DataFrame, fold_ids, n_rows) -> list:
    """One module instance per frozen enumeration element (rho in {0.25, 0.5, 0.75}); the runner
    never selects among them (RUNNER_INTERFACE.md section 1)."""
    return [A11Arm(history, r, fold_ids, n_rows) for r in feat.ENUMERATED_RHO]


# ---------------------------------------------------------------------------------------------
# kill-condition decidability (task_cards.A11.kill_conditions_frozen / a11_repair
# .kill_conditions_replaced.decidable_per_element_set, verbatim):
#   (i)   per-element beta kill: the 95% training-cluster bootstrap interval for beta covers 0
#         in EVERY evaluable fold -> that element is killed.
#   (ii)  thin-stratum concentration kill: out-of-fold improvement not concentrated on the
#         thin-evidence stratum (n_cur <= 5) -> arm killed as a carryover claim.
#   (iii) sign kill: beta-hat sign instability across evaluable folds -> arm killed.
# "rho interval includes 1 (null value)" is STRUCK as never-fireable (rho is fixed per grid
# element, only beta receives bootstrap intervals, and every grid rho < 1).
# This is a pure decision function over already-computed per-fold beta intervals plus an
# externally-supplied concentration verdict -- it fits no model and reads no comparative
# performance; it exists so the card's kill hooks are DECIDABLE and independently testable.
# ---------------------------------------------------------------------------------------------
def decide_kill(beta_by_fold: dict, *, thin_stratum_concentrated: bool | None = None,
                p25_rejected: bool = False) -> dict:
    """beta_by_fold: {fold_id: {"point": float, "ci_low": float, "ci_high": float}} over
    EVALUABLE folds only (train_lt_2022 excluded per structurally_deactivated_folds).
    `thin_stratum_concentrated`: True if the out-of-fold improvement IS concentrated on the
    n_cur <= 5 stratum (kill ii does NOT fire), False if it is not (kill ii FIRES), None if the
    diagnostic was not evaluated (kill ii is not claimed either way, and is recorded as such)."""
    if p25_rejected:
        return {"schema": "a11_kill_decision/1", "killed": True, "reason": "p25_rejection",
                "basis": "P35 a11_repair.kill_conditions_replaced", "per_fold_covers_zero": {},
                "interval_kill": None, "sign_kill": None, "thin_stratum_kill": None}

    covers_zero = {}
    for fid, v in beta_by_fold.items():
        lo, hi = float(v["ci_low"]), float(v["ci_high"])
        if lo > hi:
            raise ValueError(f"malformed interval for fold {fid}: ci_low > ci_high")
        covers_zero[fid] = bool(lo <= 0.0 <= hi)
    interval_kill = bool(beta_by_fold) and all(covers_zero.values())

    signs = set()
    for fid, v in beta_by_fold.items():
        if not covers_zero[fid]:
            signs.add(1 if float(v["point"]) > 0 else -1)
    sign_kill = len(signs) > 1

    thin_stratum_kill = (thin_stratum_concentrated is False)

    reasons = []
    if interval_kill:
        reasons.append("beta_interval_covers_zero_every_evaluable_fold")
    if sign_kill:
        reasons.append("sign_instability")
    if thin_stratum_kill:
        reasons.append("improvement_not_concentrated_on_thin_evidence_stratum")

    return {"schema": "a11_kill_decision/1",
            "killed": bool(interval_kill or sign_kill or thin_stratum_kill),
            "reason": "+".join(reasons) if reasons else "not_killed",
            "basis": "P35 a11_repair.kill_conditions_replaced.decidable_per_element_set",
            "per_fold_covers_zero": covers_zero,
            "interval_kill": interval_kill, "sign_kill": sign_kill,
            "thin_stratum_kill": thin_stratum_kill,
            "thin_stratum_concentration_input": thin_stratum_concentrated}
