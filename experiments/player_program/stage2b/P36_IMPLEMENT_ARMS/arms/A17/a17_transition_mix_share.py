#!/usr/bin/env python3
"""a17_transition_mix_share.py -- A17_transition_mix_share arm module, RUNNER_INTERFACE.md
conformant.

Card: P35_FREEZE_TASK_CARDS/SPEC.json (sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards.A17
(A17_transition_mix_share), carried by hash reference from P33_PREREGISTRATION_DRAFT/SPEC.json
(sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) arms[A17].

Model (frozen, verbatim): eta = log_exposure + [nuisance incl. is_playoff_game with the section-4
fold-2026 fallback] + coef * x; x = (short_off(t,g) + short_def(opp(g,t),g))/2; mu = exp(eta);
NO global intercept in arm or null (P35 intercept_structure -> A17 in ARMS_WITHOUT_GLOBAL_
INTERCEPT). Single fitted element -- LAGGED_TEMPO_MIX is now a single-member family {A17}
(P35 multiplicity_recomputed; A19 withdrawn, the joint-scoring/weaker-member-drop rule VOIDED
explicitly), single test at alpha 0.05.

k0_matched (P35 task_cards.A17.k0_matched_frozen, verbatim): "identical machinery plus nuisance
incl. is_playoff_game; treatment adds ONLY x". comparison: term_removal. treatment_terms: ["x
(symmetric transition mix)"]. tested_parameters: [{name: coef(x), role: coefficient,
null_value: 0, meaning: "duration composition adds nothing beyond scalar pace"}].

fold_local_fallback (P35 amendment FOLDS F2, verbatim): "a team-side trailing share with an EMPTY
prior-game set imputes that side's share := the fold's TRAINING-row mean of the defined values of
that share, computed once per fold, held fixed across bootstrap refits, identical in arm and null
(numeric trigger |P| = 0; 7 offense-side rows / 5 clusters measured, incl. fold-4/5 TEST rows)".
RUNNER_INTERFACE.md section 3 names this exact convention as A17's own worked example of a
training-fold-computed constant.

guard_invocation: declared_family SUBSTANTIVE, recalibration_declaration NOT_APPLICABLE, offset
log_exposure, incumbent_projection projected_team_off_possessions.

amendments_applied (P35 task_cards.A17, verbatim list):
  - FOLDS F2: the empty-prior-set imputation rule above (numeric trigger |P|=0).
  - LAGGED_TEMPO_MIX restated: single-member family {A17}; the joint-scoring / weaker-member-drop
    rule is VOIDED explicitly (A19 withdrawn); the arm's own primary gate governs alone.
  - K0 K2: no global intercept; OP-5 team_cities pin (cross-season decay operator).
  - MULT mechanism_split_disclaimer: F14 split funding (A17/A18) acknowledged; both-pass rule
    names the pair.

kill_conditions_frozen (P35, verbatim): "preregistered score/LR-equivalent bootstrap test vs K0
fails; P25 rejection". Because LAGGED_TEMPO_MIX is now a single-member family (single test, alpha
0.05, no Holm correction), this is operationally the arm's own primary gate (P33 inference.
primary_gate: delta_MAE > 0 AND two-sided cluster-bootstrap p-value < alpha AND no kill AND P28
ordering) -- there is no separate coefficient-interval kill declared for A17 the way there is for
A05/A08 (P33 k0_matched carries no `tested_parameters`-interval kill text for A17; the card's own
kill_conditions_frozen names the score/LR-equivalent bootstrap test itself as the kill).
`evaluate_kill_conditions` below implements exactly this reading and is DECIDABLE independent of
any comparative performance number (it is a pure function of an already-computed p-value/delta_MAE
pair, never itself computing one from real data).

Carried verbatim from P33 (fields not named in the P35 card's amendments_applied list, therefore
binding as-is per the P35 carry_convention):
  formula: "short_off(t,g) = w-weighted share of t's offensive possessions in P(t,g) with
      duration_sec <= 8; x = (short_off(t,g) + short_def(opp(g,t),g)) / 2; 1 df; weights:
      exponential decay half-life 10 games, season-boundary discount 0.5, FIXED"
  hyperparameters.fixed: {short_threshold_sec: 8, half_life_games: 10, season_boundary_discount: 0.5}
  fallback: "none needed; defined on every resolved row, bounded [0,1]" -- SUPERSEDED for the
      empty-prior-set stratum by P35 FOLDS F2 above (the P33 "|P| >= 1 by universe construction"
      claim is corrected by F2's own measured counterexample; both texts are carried, not
      silently reconciled -- see feature_construction.py module docstring and REPORT.md).
  precondition: "P23 franchise-continuity receipt (cross-season decay operator)" -- A17 is named
      in P33 shared_arm_invariants.p23_franchise_continuity_precondition.
  preserved_disagreement: "formulation divergence with A18 (symmetric tail-share vs antisymmetric
      median) deliberately both carried" -- not adjudicated by this module; recorded, not erased.

Ownership: experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A17/ ONLY. This module
imports the frozen RUNNER_INTERFACE.md contract (runner/*.py) but never writes to runner/ or to
any other arm's directory.

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
if str(_RUNNER) not in sys.path:
    sys.path.insert(0, str(_RUNNER))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import runner_constants as rc                   # noqa: E402  (frozen; imported, never edited)
import feature_construction as feat              # noqa: E402  (this unit's own module)

ARM_ID = "A17_transition_mix_share"
CARD_ID = ARM_ID
TREATMENT_COL = "x_transition_mix"          # x = (short_off(t,g) + short_def(opp(g,t),g)) / 2
NUISANCE_COL = "is_playoff_indicator"       # materialised 0.0/1.0, 1[is_playoff_game]

P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"


def _sidespec(fold_ids):
    return {
        "intercept_treatment": "none -- no global intercept in arm or null (P35 K0 K2 pin)",
        "calibration_freedom": "none -- coef(x) is a single fixed-shape coefficient, no post-fit "
                               "rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": "log_exposure = log(projected_team_off_possessions)",
        "training_rows": "fold train_idx, per the runner's per-fold split",
        "evaluation_rows": "fold test_idx, per the runner's per-fold split",
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": "x_transition_mix: recency- and season-discount-weighted trailing share "
                         "(feature_construction.py); empty-prior-set entries imputed with the "
                         "fold's TRAINING-row mean of defined values (P35 FOLDS F2), computed "
                         "once per fold and held fixed across bootstrap refits. "
                         "is_playoff_indicator: 0.0/1.0 casting of the raw pre-tipoff schedule flag.",
        "missing_value_handling": "P35 FOLDS F2 empty-prior-set imputation (numeric trigger "
                                  "|P(side)| = 0), identical in arm and null; is_playoff_game is "
                                  "a complete-case schedule fact, never missing pre-tipoff",
        "companion_components": "none",
        "fallback_rules": "P35 FOLDS F2 fold-local imputation; GATE_INVOCATION_CONTRACT section 4 "
                          "fold-2026-style test-side non-discrimination note carried for the "
                          "is_playoff_game nuisance (see notes[] in p26_k0_record)",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the arm's declared team-game universe (frozen 2,982-row real "
                              "universe at P38; synthetic fixture rows in P36 tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A17TransitionMixShare:
    """One arm x one enumeration element (single-element arm: enumeration_element() == {})."""

    arm_id = ARM_ID

    def __init__(self, possessions: pd.DataFrame, fold_ids):
        """`possessions` must carry: game_id, game_date, season, offense_team_id,
        defense_team_id, duration_sec (P33 arms[A17].features). Prior-recency aggregates are
        computed ONCE here (they depend only on the possession history, never on a fold split);
        the fold-local FOLDS-F2 imputation means are computed per fold in `build_design`.
        """
        self._fold_ids = [str(f) for f in fold_ids]
        history_agg = feat.aggregate_possession_counts(possessions)
        self._prior_agg = feat.compute_prior_recency_aggregates(history_agg)

    # ---- metadata hooks ------------------------------------------------------------------
    def card_id(self):
        return CARD_ID

    def declared_family(self):
        return rc.DECLARED_FAMILY_ALL_FITTED_ARMS          # "SUBSTANTIVE" (P35 pinned)

    def recalibration_declaration(self):
        return rc.RECALIBRATION_DECLARATION                # "NOT_APPLICABLE" (P35 pinned)

    def enumeration_element(self):
        return {}

    def element_id(self):
        return f"{ARM_ID}__single"

    def uses_global_intercept(self):
        return False

    # ---- design ----------------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        """x_transition_mix (treatment) and is_playoff_indicator (nuisance), deterministic given
        `universe` and the fold's train_idx (the FOLDS F2 imputation means are a training-fold
        constant, per RUNNER_INTERFACE.md section 3 -- computed from fold['train_idx'] rows ONLY,
        once per fold, held fixed across bootstrap refits; this method never resamples).
        """
        for c in ("team_id", "opp_team_id", "game_id", "is_playoff_game"):
            if c not in universe.columns:
                raise KeyError(f"A17 build_design requires column '{c}' on the universe frame")

        own = feat.align_shares(self._prior_agg, universe["team_id"].to_numpy(),
                                universe["game_id"].to_numpy())
        opp = feat.align_shares(self._prior_agg, universe["opp_team_id"].to_numpy(),
                                universe["game_id"].to_numpy())
        own_share, own_defined = own["short_off_share"], own["short_off_defined"]
        opp_share, opp_defined = opp["short_def_share"], opp["short_def_defined"]

        n = len(universe)
        train_idx = np.asarray(fold["train_idx"], dtype=int)
        train_mask = np.zeros(n, dtype=bool)
        train_mask[train_idx] = True

        own_train_defined = train_mask & own_defined
        opp_train_defined = train_mask & opp_defined
        own_train_mean = float(np.mean(own_share[own_train_defined])) if own_train_defined.any() else 0.0
        opp_train_mean = float(np.mean(opp_share[opp_train_defined])) if opp_train_defined.any() else 0.0

        own_imputed = np.where(own_defined, own_share, own_train_mean)
        opp_imputed = np.where(opp_defined, opp_share, opp_train_mean)
        x = (own_imputed + opp_imputed) / 2.0

        raw_playoff = universe["is_playoff_game"].to_numpy()
        ind = raw_playoff.astype(float)
        bad = ~np.isin(ind, (0.0, 1.0))
        if np.any(bad):
            raise ValueError(f"is_playoff_game must be a strict 0/1 pre-tipoff schedule flag; "
                             f"{int(bad.sum())} non-{{0,1}} value(s) found")

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [NUISANCE_COL],           # x is continuous [0,1], not 0/1 indicator
            "columns": {TREATMENT_COL: x, NUISANCE_COL: ind},
            "diagnostics": {
                "fold_id": str(fold.get("fold_id")),
                "n_own_imputed": int((~own_defined).sum()),
                "n_opp_imputed": int((~opp_defined).sum()),
                "own_train_mean": own_train_mean, "opp_train_mean": opp_train_mean,
                "n_rows": int(n),
            },
        }

    # ---- P26 ---------------------------------------------------------------------------------
    def p26_k0_record(self):
        side = _sidespec(self._fold_ids)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "trailing recency- and season-discount-weighted transition-possession "
                             "share (own offense + opponent defense, symmetric) carries tempo "
                             "composition information the scalar offset does not",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "coef(x)", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "duration composition adds nothing "
                                                             "beyond scalar pace"}],
                "claimed_signal_axes": ["possession_observation"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": "removing x_transition_mix leaves the offset plus "
                                               "the is_playoff_game nuisance -- no remaining "
                                               "column carries any transition-mix composition "
                                               "information, so the mechanism is fully destroyed "
                                               "by term removal"}},
            "invariants": {
                "rows": "the arm's declared team-game universe (see side.candidate_universe)",
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
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
            "fold_local_fallback": {
                "required": False,
                "trigger": "not_applicable -- P35 FOLDS F2's empty-prior-set imputation is a "
                          "symmetric ROW-LEVEL fill (impute that side's share with the fold's "
                          "TRAINING-row mean of the defined values of that same share, computed "
                          "once per fold, held fixed across bootstrap refits, identical in arm "
                          "and null), not a P27 fold-collapse partition -- none of this schema's "
                          "four fold-collapse actions (drop_term_for_fold, "
                          "collapse_to_parent_tier, refuse_to_score_fold) describes a row-level "
                          "fill; same convention as A08/a08_arm.py's L_t empty-window zero-fill, "
                          "which is likewise recorded here as not_applicable and described fully "
                          "in fallback_rules/notes[] instead",
                "numeric_threshold": None,
                "action": "not_applicable",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature: eligible for feature-value labeling if "
                                    "it survives the LAGGED_TEMPO_MIX single-member primary gate "
                                    "(P35 multiplicity_recomputed; alpha 0.05, no Holm correction, "
                                    "family reduced to {A17} after A19's withdrawal)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "P35 amendment FOLDS F2 (verbatim): a team-side trailing share with an EMPTY "
                "prior-game set imputes that side's share := the fold's TRAINING-row mean of the "
                "defined values of that share, computed once per fold, held fixed across "
                "bootstrap refits, identical in arm and null (numeric trigger |P|=0; 7 "
                "offense-side rows / 5 clusters measured on the real universe, incl. fold-4/5 "
                "TEST rows). This module's own measurement is synthetic-only (see TESTS_A17.py); "
                "the real-universe count above is carried from the frozen card, not re-derived "
                "here (no real data is read by this node).",
                "GATE_INVOCATION_CONTRACT section 4 fold-2026-style note, carried identically "
                "from A05's frozen card for the SAME shared is_playoff_game schedule column under "
                "the same real universe (this module does not itself re-measure it, having no "
                "real-data access): on fold train_lt_2026 the TEST-side is_playoff_indicator "
                "column is identically zero (0 playoff test rows measured for A05; training "
                "support 17/40/60/82/106 playoff clusters across the five folds, all >= 10). The "
                "fold remains evaluable for A17's OWN treatment coefficient coef(x), which does "
                "not depend on is_playoff_game; only the nuisance term's own identification on "
                "that fold's test partition is affected, symmetrically in arm and null.",
                "D3-adjacent preserved disagreement, carried from P33 arms[A17] verbatim, not "
                "adjudicated by this module: 'formulation divergence with A18 (symmetric "
                "tail-share vs antisymmetric median) deliberately both carried.'",
                "P33 arms[A17].fallback text ('none needed; defined on every resolved row, "
                "bounded [0,1]') is SUPERSEDED by P35 FOLDS F2's own measured counterexample "
                "(7 offense-side rows with |P|=0); both texts are carried here, not silently "
                "reconciled -- flagged for P37.",
                "Weighting-formula closed-form ambiguity flagged for P37: see "
                "feature_construction.py module docstring (Delta_games 1-indexed convention "
                "pinned by this module; the 0-indexed alternative is equally defensible from the "
                "frozen prose alone and is not ruled out by any byte in this program).",
            ],
        }

    # ---- guards ------------------------------------------------------------------------------
    def lag_specs(self):
        return {
            TREATMENT_COL: {
                "column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                "source_artifact_id": "possessions_raw_v2",
                "rationale": "recency- and season-discount-weighted aggregate over a team's own "
                            "STRICTLY EARLIER games' possession-level duration_sec shares "
                            "(feature_construction.compute_prior_recency_aggregates); declared "
                            "DERIVED_NO_JOIN rather than PRIOR_GAME because the frozen P22 "
                            "postgame_surrogate_guard.verify_prior_game_lag re-derivation "
                            "supports only a single shift(n_back), not a multi-game recency-"
                            "weighted window -- this module's own strict-lagging identity tests "
                            "(TESTS_A17.py) independently verify the strict '< game_date(g)' "
                            "property the P22 shift-1 verifier cannot check for a windowed "
                            "aggregate (same convention as A08/features.py's L_t and A11's "
                            "dcur_t/dprev_t), flagged for P37/P38 rather than silently claimed "
                            "as PRIOR_GAME-verified.",
            },
            NUISANCE_COL: {
                "column": NUISANCE_COL, "kind": "SCHEDULE",
                "source_artifact_id": "schedule_contract/1",
                "entity_keys": ("game_id",),
                "rationale": "playoff/regular-season status is a fact fixed by the published "
                            "schedule before tipoff (P22 LagSpec docstring names 'playoff flag' "
                            "explicitly as a SCHEDULE-kind example); same construction as A05's "
                            "TREATMENT_COL: schedule indicator (season_type == 'Playoffs'), "
                            "lineage possession_features.py line 318, incumbent-carried column; "
                            "S8 table: season_type ELIGIBLE",
            },
        }

    def lag_sources(self):
        return {}          # DERIVED_NO_JOIN/SCHEDULE declare no PRIOR_GAME re-derivation source

    def preregistered_contrasts(self):
        return None          # A17 carries no "contrast_"-named column (only A02 does, P25 pins)

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self):
        return True           # P33 precondition: "P23 franchise-continuity receipt (cross-season
                              # decay operator)"; A17 is named in shared_arm_invariants
                              # .p23_franchise_continuity_precondition

    def p23_receipts(self):
        return [{"team_cities_sha256": rc.TEAM_CITIES_SHA256_PIN,
                 "note": "A17 requires the franchise-continuity receipt per P33 precondition / "
                         "P35 shared_frozen_amendments.franchise_continuity_receipt_pin (the "
                         "cross-season decay operator crosses the PHO/PHX rebrand boundary)"}]

    def p27_rule(self):
        return None            # A17's own card registers no P27 S7 active-set rule; its live
                                # risk is the P25 near-affinity-vs-offset/incumbent-projection
                                # gate (expected_failure_mode, P33 arms[A17], carried) and the
                                # FOLDS F2 fold-local imputation above, not a P27 fold-collapse
                                # partition


# ---------------------------------------------------------------------------------- kill hooks
def evaluate_kill_conditions(*, p_value: float | None, delta_mae: float | None,
                             alpha: float = 0.05, p25_rejected: bool = False) -> dict:
    """Mechanically decide the frozen A17 kill rule (P35 kill_conditions_frozen, verbatim:
    "preregistered score/LR-equivalent bootstrap test vs K0 fails; P25 rejection") from an
    already-computed pooled delta_MAE and its two-sided cluster-bootstrap p-value.

    LAGGED_TEMPO_MIX is a single-member family this cycle (P35 multiplicity_recomputed: "single
    test, alpha 0.05"; the joint-scoring/weaker-member-drop rule against A19 is VOIDED, "the
    arm's own primary gate governs alone") -- there is no Holm correction to apply and no
    separate coefficient-interval kill declared for A17 in either P33 or P35 the way there is for
    A05/A08/A09/A10/A11; the card's OWN kill condition names the primary score/LR-equivalent
    bootstrap test itself. This function reads no comparative performance number; it is a pure
    decision over whatever (p_value, delta_mae) pair the caller supplies, so the card's kill hook
    is DECIDABLE and independently testable without any real fold (see TESTS_A17.py::
    t08_kill_conditions_decidable).
    """
    if p25_rejected:
        return {"schema": "a17_kill_decision/1", "killed": True, "reason": "p25_rejection",
                "basis": "P35 task_cards.A17.kill_conditions_frozen",
                "p_value": p_value, "delta_mae": delta_mae, "alpha": alpha,
                "score_test_failed": None}
    if p_value is None or delta_mae is None:
        return {"schema": "a17_kill_decision/1", "killed": False,
                "reason": "not_evaluable_no_manufactured_positive",
                "basis": "standing rule 7: preserve nulls, do not manufacture a positive when "
                         "the inputs needed to decide are absent",
                "p_value": p_value, "delta_mae": delta_mae, "alpha": alpha,
                "score_test_failed": None}
    score_test_failed = not (float(delta_mae) > 0.0 and float(p_value) < float(alpha))
    return {"schema": "a17_kill_decision/1", "killed": bool(score_test_failed),
            "reason": ("score_lr_equivalent_bootstrap_test_failed" if score_test_failed
                      else "not_killed"),
            "basis": "P35 task_cards.A17.kill_conditions_frozen",
            "p_value": float(p_value), "delta_mae": float(delta_mae), "alpha": float(alpha),
            "score_test_failed": score_test_failed}
