#!/usr/bin/env python3
"""arm_a22.py -- A22_lineup_churn_tv_distance, the P36 RUNNER_INTERFACE arm module.

Frozen card: experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/SPEC.json
(sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32) task_cards[A22], amended
by shared_frozen_amendments (intercept_structure, franchise_continuity_receipt_pin,
p26_k0_contract_enforcement).

  model:  eta = log_exposure + [A17/A21-null nuisance] + coef * x
          x = (churn(t,g) + churn(opp(g,t),g)) / 2; mu = exp(eta); no global intercept
  K0_MATCHED[A22]: "same machinery as A17/A21 nulls; treatment adds ONLY x; churn-by-depth
          interaction explicitly NOT in this arm" -- P33/P35 name A17's null as
          "identical machinery plus nuisance incl. is_playoff_game with the section-4 fold-2026
          fallback declared" and A21's null as "identical to A17's null". A22's
          p26_k0_record.invariants pins the resolved lower-order set explicitly:
          lower_order_structural_terms = ["is_playoff_game nuisance"], global_intercept = false.
          comparison = term_removal.
  elements: NONE enumerated -- P35 multiplicity_recomputed: PERSONNEL_CONTINUITY family =
          {"A22": 1}, single element, single test at alpha 0.05 (task_cards.A22 carries no
          "enumerated" hyperparameters; hyperparameters.fixed only). enumeration_element() == {}.

Per standing rule 3 (enforcement at the call site, never editing a shared gate) and this unit's
write scope (experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A22/ only), this module
imports the FROZEN runner contract (runner_constants, for the pinned column names, the frozen
intercept table and the frozen team_cities.csv hash) but writes nothing outside its own
directory and edits nothing under runner/ or any other arm's directory.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.
"""
from __future__ import annotations

import numpy as np

from feature_construction import (HALF_LIFE_GAMES, SEASON_BOUNDARY_DISCOUNT,
                                  aggregate_game_player_appearances, align_churn,
                                  compute_prior_last_and_base)
from runner_constants import INCUMBENT_PROJECTION_COL, OFFSET_COL, TEAM_CITIES_SHA256_PIN

ARM_ID = "A22_lineup_churn_tv_distance"

#: the card's own literal term names, reused VERBATIM as the design's column keys (A08/A09
#: precedent: "reused VERBATIM as the design's column keys ... rather than inventing a fresh
#: naming scheme, per 'implement EXACTLY it' / 'never improvise'").
TREATMENT_COL = "x (symmetric churn)"
#: materialised nuisance column for the card's "is_playoff_game nuisance" lower-order term
#: (A05/A17/A21 precedent construction: is_playoff_game schedule indicator, cast 0.0/1.0).
NUISANCE_COL = "is_playoff_indicator"
NUISANCE_SOURCE_COL = "is_playoff_game"


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
        "preprocessing": (
            "churn(t,g) = 0.5*sum_j|u_last(j)-u_base(j)| over lagged per-player offensive-"
            "possession usage shares (off_p1..off_p5, strictly earlier games only); u_last = the "
            "single immediately-preceding game's own raw usage shares; u_base = the recency-"
            "decayed (half_life_games=10, season_boundary_discount=0.5) usage-share aggregate of "
            "all STILL-earlier games, excluding the game named u_last; churn := 0 when "
            "n_prior_games <= 1 (fold_local_fallback numeric_trigger, verbatim); x = (churn(t,g) "
            "+ churn(opp(g,t),g))/2; is_playoff_indicator = 1.0/0.0 cast of the pre-tipoff "
            "schedule flag is_playoff_game (A05/A17/A21 shared construction)"),
        "missing_value_handling": "none beyond the |P|<=1 fallback above (complete-case otherwise)",
        "companion_components": "none",
        "fallback_rules": "churn := 0 at n_prior_games <= 1, identical in arm and null (a row-"
                          "level deterministic imputation, not a fold-partition indicator; "
                          "P35 task_cards.A22.p26_k0_record.fold_local_fallback)",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the contract-schedule team-game universe (synthetic in tests)",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


class A22Arm:
    """Single-element arm (enumeration_element() == {}): PERSONNEL_CONTINUITY family = {A22: 1}."""

    arm_id = ARM_ID

    def __init__(self, fold_ids, n_rows: int, lineups=None):
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows)
        # `lineups`: the raw possession-level (or pre-aggregated) frame carrying off_p1..off_p5
        # for STRICTLY EARLIER games. build_design accepts it via the constructor (rather than
        # only via `universe`) because it is a DIFFERENT grain (possession-level lineup rows,
        # not one row per team-game) -- exactly the situation RUNNER_INTERFACE.md section 2
        # names `lag_sources()` for ("source frames for PRIOR_GAME re-derivation"). When None,
        # `universe` itself is required to already carry off_p1..off_p5 per team-game row (one
        # possession-level frame collapsed 1:1 with the game, as the synthetic fixture supplies).
        self._lineups = lineups
        self._prior_cache = None            # computed lazily, memoised per (id(lineups_source))
        self._prior_cache_key = None

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        return {}

    def element_id(self) -> str:
        return f"{ARM_ID}__single"

    def uses_global_intercept(self) -> bool:
        return False

    # ---- design ---------------------------------------------------------------------
    def _prior_table(self, universe):
        """Memoised churn-prior computation: deterministic pure function of the lineup source,
        never fold-dependent (P(t,g) is defined over the FULL strictly-earlier history regardless
        of which fold's train/test split is being materialised -- exactly A09's d_t precedent:
        "d_t/n_t are NOT fold-dependent constants ... deterministic functions of schedule facts
        strictly earlier than each row's own game")."""
        source = self._lineups if self._lineups is not None else universe
        key = id(source)
        if self._prior_cache is not None and self._prior_cache_key == key:
            return self._prior_cache
        appearances = aggregate_game_player_appearances(source)
        prior = compute_prior_last_and_base(appearances, half_life_games=HALF_LIFE_GAMES,
                                            season_boundary_discount=SEASON_BOUNDARY_DISCOUNT)
        self._prior_cache = prior
        self._prior_cache_key = key
        return prior

    def build_design(self, fold, universe) -> dict:
        for col in ("team_id", "opp_id", "game_id", NUISANCE_SOURCE_COL):
            if col not in universe.columns:
                raise KeyError(f"A22 build_design requires column '{col}' on the universe frame")
        prior = self._prior_table(universe)
        team_id = universe["team_id"].to_numpy()
        opp_id = universe["opp_id"].to_numpy()
        game_id = universe["game_id"].to_numpy()

        own = align_churn(prior, team_id, game_id)
        opp = align_churn(prior, opp_id, game_id)
        x = 0.5 * (own["churn"] + opp["churn"])

        raw_play = universe[NUISANCE_SOURCE_COL].to_numpy()
        play_ind = raw_play.astype(float)
        bad = ~np.isin(play_ind, (0.0, 1.0))
        if np.any(bad):
            raise ValueError(f"{NUISANCE_SOURCE_COL} must be a strict 0/1 pre-tipoff schedule "
                             f"flag; {int(bad.sum())} non-{{0,1}} value(s) found")

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [NUISANCE_COL],
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": [NUISANCE_COL],
                                  "comparison": "term_removal"},
            "indicator_cols": [NUISANCE_COL],
            "columns": {TREATMENT_COL: x, NUISANCE_COL: play_ind},
        }

    # ---- P26 ------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        side = _sidespec(self._fold_ids, self._n_rows)
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "Personnel discontinuity between the trailing lineup evidence and "
                             "the most recent observed game mis-projects pace; churn is the "
                             "cutoff-valid footprint of that discontinuity, symmetrised over "
                             "both sides of the game.",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "coef(x)", "role": "coefficient",
                                       "null_value": 0,
                                       "null_value_meaning": "personnel discontinuity carries no "
                                                             "pace signal"}],
                "claimed_signal_axes": ["roster"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": "removing x leaves log_exposure plus the "
                                               "is_playoff_game nuisance term -- the same "
                                               "machinery as A17/A21's null -- in which the "
                                               "lineup-churn footprint never appears; "
                                               "churn-by-depth interaction is explicitly NOT in "
                                               "this arm (P35 task_cards.A22.k0_matched_frozen)"}},
            "invariants": {
                "rows": _row_digest(self._n_rows),
                "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
                "folds": self._fold_ids,
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": "churn := 0 at n_prior_games <= 1, identical arm and null "
                                      "(P35 task_cards.A22 fold_local_fallback)",
                "nuisance_terms": [NUISANCE_COL],
                "lower_order_structural_terms": ["is_playoff_game nuisance"]},
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
                "trigger": "n_prior_games <= 1 (row-level deterministic imputation, not a "
                          "fold-partition indicator)",
                "numeric_threshold": 1,
                "action": "not_applicable",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature result: eligible for a PERSONNEL "
                                    "CONTINUITY mechanism verdict against K0_MATCHED[A22], "
                                    "subject to the primary gate and the PERSONNEL_CONTINUITY "
                                    "family single-test alpha 0.05 (P35 multiplicity_recomputed); "
                                    "a null or a depth-absorption result ALSO removes the "
                                    "mechanistic warrant for prospective injury capture on this "
                                    "target (P33 arms[A22] declared consequence, carried).",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "P35 amendment OP-7 (verbatim): '|P|=1 rows number 15 (12 in 2021, 1 in 2025, 2 "
                "in 2026: expansion second games; the 2025/2026 rows are test-fold rows). The "
                "churn := 0 rule is symmetric and covers them; |P|=0 is covered by the "
                "cold-start text (churn := 0).'",
                "K0 K2 (P35): no global intercept pinned; OP-5 team_cities pin required "
                "(franchise continuity); D4 preserved disagreement carried -- 'D4 travels with "
                "the arm; injury family contributes ZERO candidates (P24 measured)' (P33, not "
                "adjudicated by this module).",
                "P37 AMBIGUITY FLAG (feature_construction.py module docstring, in full): the "
                "exact u_last(j)/u_base(j) split is not spelled out in closed form by any frozen "
                "byte; this module pins u_last = the single immediately-preceding game's raw "
                "usage, u_base = the half-life-decayed aggregate of all STILL-earlier games, "
                "from FOUR convergent frozen facts (mechanism text's two-pool distinction, the "
                "|P|<=1 fallback trigger, the cold-start text naming the BASE window as the "
                "absent quantity, and the half_life_games/season_boundary_discount hyperparameter "
                "identity with A17/A21). Not a HALT: the reading is forced, not invented -- see "
                "the module docstring for the full convergence argument.",
            ],
        }

    # ---- guards -----------------------------------------------------------------------
    def lag_specs(self) -> dict:
        churn_rationale = (
            "x is built by feature_construction.py from the supplied lineup source's OWN rows "
            "(off_p1..off_p5, team_id/opp_id, game_id, game_date, season), restricted per-row to "
            "STRICTLY earlier game_date entries only (the shared lag operator P(t,g) every "
            "H1-family hypothesis inherits, per A17's own citation). No external artifact join is "
            "performed by this module for churn itself (the possession-level lineup source IS the "
            "contract-schedule lineup history) -- DERIVED_NO_JOIN, not a single-column PRIOR_GAME "
            "shift; P22's generic groupby+shift(n_back) re-derivation cannot verify an all-prior "
            "decayed usage-share aggregate, so it is not the correct declared kind here. Strict "
            "lagging is instead established directly by identity/synthetic tests in this unit "
            "(TESTS.py) against feature_construction.py's pure functions: a row's "
            "last_counts/base_counts are shown to be invariant to perturbing its OWN game's "
            "lineup and to perturbing any LATER game's lineup."
        )
        return {
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "DERIVED_NO_JOIN",
                            "source_artifact_id": "contract_schedule_lineup_history/1",
                            "rationale": churn_rationale},
            NUISANCE_COL: {
                "column": NUISANCE_COL, "kind": "SCHEDULE",
                "source_artifact_id": "schedule_contract/1", "entity_keys": ("game_id",),
                "rationale": "playoff/regular-season status is a fact fixed by the published "
                            "schedule before tipoff (P22 LagSpec docstring names 'playoff flag' "
                            "explicitly as a SCHEDULE-kind example; A05/A17/A21 precedent "
                            "construction); P33-carried: schedule indicator (season_type == "
                            "'Playoffs'), possession_features.py line 318, incumbent-carried "
                            "column; S8 table: season_type ELIGIBLE.",
            },
        }

    def lag_sources(self) -> dict:
        # DERIVED_NO_JOIN needs no external re-derivation source for P22's generic PRIOR_GAME
        # check; strict lagging for the churn column is established by this unit's own
        # identity/synthetic tests instead (see lag_specs() rationale above).
        return {}

    def preregistered_contrasts(self):
        return None

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 p23_franchise_continuity_precondition names A22 explicitly: churn is a cross-season
        # (all-prior, half-life-decayed) history feature, so the PHO/PHX rebrand receipt is
        # required before gate invocation.
        return True

    def p23_receipts(self) -> list:
        return [{
            "team_cities_sha256": TEAM_CITIES_SHA256_PIN,
            "scope": "A22: churn is keyed directly on team_id/opp_id across seasons via the "
                    "lineup-history recurrence; this receipt attests the frozen franchise-"
                    "continuity pin per P35 franchise_continuity_receipt_pin / the P33 "
                    "p23_franchise_continuity_precondition naming A22.",
        }]

    def p27_rule(self):
        # No S7 active-set-rule registry entry names A22 in P35 registry_append (only A03, A12,
        # A13, A14 do); A22's own fold_local_fallback is a row-level deterministic imputation
        # (n_prior_games <= 1), not an S7 training-support tier/partition rule, so there is
        # nothing to register here (A09/A21 precedent: same reasoning, same None return).
        return None


def make_arms(fold_ids, n_rows, lineups=None) -> list[A22Arm]:
    """A22 carries no enumeration grid: one module instance (RUNNER_INTERFACE.md section 1: "one
    arm-module instance binds exactly one enumeration element"; {} for single-element arms)."""
    return [A22Arm(fold_ids, n_rows, lineups=lineups)]


# ---------------------------------------------------------------------------------- kill hooks
def evaluate_kill_conditions(per_fold_coef: dict) -> dict:
    """Mechanically decide the FIRST frozen A22 kill rule ("null vs K0") from per-fold
    training-cluster-bootstrap results for coef(x) (P35 kill_conditions_frozen: "null vs K0;
    depth-absorption check"). Mirrors A05/evaluate_kill_conditions's operationalisation of the
    shared inference block ("theta = 0 not rejected ... interval covers 0 in EVERY evaluable
    fold"; "sign instability ... any two evaluable folds ... opposite signs"), applied here to
    coef(x) rather than pi.

    `per_fold_coef`: {fold_id: {"lo": float|None, "hi": float|None, "beta": float}} -- normally
    fold_results[fid]["train_refit"]["arm_intervals"][TREATMENT_COL] plus the point estimate,
    gathered per evaluable fold only (STRUCTURALLY_DEACTIVATED / UNEVALUABLE folds excluded
    upstream).
    """
    folds = sorted(per_fold_coef)
    covers, signs = {}, {}
    for fid in folds:
        rec = per_fold_coef[fid]
        lo, hi, beta = rec.get("lo"), rec.get("hi"), rec.get("beta")
        covers[fid] = (lo is None or hi is None) or (lo <= 0.0 <= hi)
        signs[fid] = 0 if beta is None or beta == 0 else (1 if beta > 0 else -1)
    nonzero_signs = {s for s in signs.values() if s != 0}
    sign_unstable = len(nonzero_signs) > 1
    all_cover = bool(folds) and all(covers.values())
    killed = bool(all_cover or sign_unstable)
    basis = []
    if all_cover:
        basis.append("coef(x) 95% training-cluster bootstrap interval covers 0 in every "
                     "evaluable fold (null vs K0)")
    if sign_unstable:
        basis.append("coef(x)-hat sign unstable across evaluable folds")
    if not basis:
        basis.append("coef(x) interval excludes 0 in at least one evaluable fold; sign stable "
                     "-- primary null-vs-K0 kill not triggered (depth-absorption check is "
                     "separate, see evaluate_depth_absorption)")
    return {"schema": "a22_kill_decision/1", "n_evaluable_folds": len(folds),
            "covers_zero": covers, "signs": signs, "all_cover_zero": all_cover,
            "sign_unstable": sign_unstable, "killed": killed, "basis": basis}


def evaluate_depth_absorption(baseline_coef: dict, depth_augmented_coef: dict) -> dict:
    """Mechanically decide the SECOND frozen A22 kill rule: the depth-absorption robustness
    check (P33 arms[A22].secondary_diagnostics, verbatim: "depth-absorption robustness (churn
    proxying thin evidence) - kills the arm AND the priority claim of prospective injury capture
    on this target"; P35 kill_conditions_frozen names it a KILL condition directly, not merely a
    secondary diagnostic, for A22 -- mirroring A21's identically-worded robustness check).

    AMBIGUITY FLAGGED FOR P37: no frozen byte gives a numeric threshold for "absorption"; this
    module operationalises it as the SAME evaluable-fold coverage rule already pinned for the
    primary kill (a bootstrap interval that excludes 0 in the baseline design but covers 0 once
    an evidence-depth proxy is added to the nuisance set, in every evaluable fold where it did
    not before, is decided ABSORBED). This is the natural symmetric extension of the frozen
    "interval covers 0 in every evaluable fold" operationalisation already pinned for kill
    condition 1 (P33 inference.coefficient_inference), applied comparatively rather than in
    isolation; it is a decidable, deterministic, preregistered-shape function, not an invented
    numeric constant, and it is flagged for P37 rather than silently promoted to a frozen pin.

    `baseline_coef` / `depth_augmented_coef`: same shape as `evaluate_kill_conditions`'s
    `per_fold_coef` argument, for the arm WITHOUT and WITH pace_evidence_depth (own+opp mean, or
    an equivalent evidence-volume proxy) added to the nuisance set, over the SAME evaluable-fold
    set.
    """
    base_folds = set(baseline_coef)
    depth_folds = set(depth_augmented_coef)
    common = sorted(base_folds & depth_folds)
    reversed_folds = []
    for fid in common:
        b, d = baseline_coef[fid], depth_augmented_coef[fid]
        b_excludes = not ((b.get("lo") is None or b.get("hi") is None)
                          or (b["lo"] <= 0.0 <= b["hi"]))
        d_covers = ((d.get("lo") is None or d.get("hi") is None)
                   or (d["lo"] <= 0.0 <= d["hi"]))
        if b_excludes and d_covers:
            reversed_folds.append(fid)
    # ABSORBED (killed) iff every evaluable fold that rejected the null at baseline flips to
    # covering 0 once the depth proxy enters -- a diffuse or partial reversal is NOT decided
    # absorption (mirrors the "EVERY evaluable fold" operationalisation of the primary kill).
    baseline_excluding = [fid for fid in common
                          if not ((baseline_coef[fid].get("lo") is None
                                   or baseline_coef[fid].get("hi") is None)
                                  or (baseline_coef[fid]["lo"] <= 0.0 <= baseline_coef[fid]["hi"]))]
    absorbed = bool(baseline_excluding) and set(reversed_folds) == set(baseline_excluding)
    return {"schema": "a22_depth_absorption_decision/1", "n_common_evaluable_folds": len(common),
           "baseline_excluding_zero_folds": baseline_excluding,
           "reversed_to_cover_zero_folds": reversed_folds, "absorbed": absorbed,
           "basis": (["every baseline fold that excluded 0 reverses to covering 0 once the "
                     "evidence-depth proxy enters the nuisance set -- decided ABSORBED "
                     "(churn proxies evidence volume, mechanism falsified even on a positive "
                     "naive test)"] if absorbed else
                    ["baseline excluded no fold, or at least one baseline-excluding fold "
                     "remains excluding 0 with the depth proxy present -- NOT absorbed"])}
