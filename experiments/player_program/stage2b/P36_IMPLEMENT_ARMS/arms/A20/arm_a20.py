#!/usr/bin/env python3
"""arm_a20.py -- P36 arm module for A20_forced_turnover_contrast.

FROZEN CARD THIS IMPLEMENTS (verbatim binding source): P35_FREEZE_TASK_CARDS/SPEC.json, sha256
68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[arm_id ==
"A20_forced_turnover_contrast"], carrying the P33_PREREGISTRATION_DRAFT/SPEC.json arm record
(sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) by hash reference per
the card's carry_convention, amended only by the card's own ``amendments_applied``. Every pinned
clock, window, centering constant, dictionary and enumeration element below is taken from those
two documents; nothing here is invented.

MODEL (P35 task card, verbatim): eta = log_exposure + beta2 * z2; z2 = ftr_own - ftr_opp;
mu = exp(eta); no global intercept (P35 intercept_structure: A20 is in
ARMS_WITHOUT_GLOBAL_INTERCEPT). Single enumeration element (P33 arms[A20].hyperparameters:
enumerated {} -- "frozen by source"): this module binds ONE arm with no enumerated variant
(RUNNER_INTERFACE.md section 1: "{} for single-element arms").

ftr_team(t, g) = share of team t's DEFENSIVE possessions with a turnover-terminator end_reason,
over ALL of team t's STRICTLY EARLIER SAME-SEASON games (P33 arms[A20].hyperparameters.fixed.
window: "same-season flat (D6 preserved)" -- an EXPANDING mean across the whole season to date,
explicitly NOT a k-window like A16 and NOT a decayed window like A17/A19/A21/A22; P33 D6: "A18/
A20/A26 same-season flat E=3"). z2 = ftr_own - ftr_opp, defined per row exactly as the row's own
team vs. the opponent's own same-season trailing rate, evaluated at the same game.

E_TO (frozen dictionary, card ``dictionary_frozen`` verbatim): E_TO = {"turnover"} -- "the
artifact's COMPLETE turnover-terminator level set, frozen HERE before any fit (measured: 41,505 of
238,563 possessions, 17.40%, present in every season; P34 OP-1). Freezing the list is
specification, not tuning." A possession counts toward a team's DEFENSIVE denominator whenever
that team is the ``defense_team_id`` of the possession, regardless of ``end_reason``; it counts
toward the numerator additionally when ``end_reason in E_TO``.

E=3 IMPUTATION (frozen, "as A18" per this card's ``model`` field, and P33 hyperparameters.fixed.
E_min_prior_games=3): z2 := 0 for a row when EITHER the row's own team or its opponent has fewer
than 3 completed strictly-earlier same-season games in the source possessions data (mirrors A18's
"z1 = 0 when either team has < 3 completed prior same-season games" verbatim, substituting A20's
own trailing quantity). This is a per-row deterministic substitution of the CONTRAST z2 itself, not
of ftr_own/ftr_opp individually -- exactly as A18 pins it for z1.

DATA SOURCE AND WHY THIS MODULE IS A CLASS, NOT A PLAIN MODULE (disclosed, not silently assumed):
``end_reason`` and ``defense_team_id`` are NOT columns of the shared team-game universe that
``possession_features.load_universe`` builds (measured: that universe carries only
``team_possession_prior_v1`` pace columns plus a target aggregated from ``possessions_raw_v2``
possession COUNTS -- verified by reading ``possession_features.py`` at implementation time; no
``end_reason`` column reaches it). Constructing ftr_own/ftr_opp therefore requires possession-level
rows from ``possessions_raw_v2`` beyond what RUNNER_INTERFACE.md's frozen ``build_design(fold,
universe)`` signature can carry (exactly two positional arguments; no data-path parameter). This
program's own precedent for exactly this situation is A13
(``arms/A13/arm_a13.py``): a class constructed with the auxiliary frame(s) its card's construction
needs beyond ``universe`` (there: ``contract_schedule``/``history``/``lineup_membership``), whose
BOUND METHODS are the RUNNER_INTERFACE hooks. ``ArmA20`` follows that same convention with one
auxiliary frame, ``possessions_raw`` (game_id, defense_team_id, end_reason -- the possession-level
columns the card's mechanism needs; read-only, never mutated). Per A13's own precedent, the
resulting derived column is declared ``DERIVED_NO_JOIN`` (not ``PRIOR_GAME``): A13's
``CONT_MAIN_COL``/``DEV_PREV_COL`` are likewise built from constructor-injected auxiliary frames
(``lineup_membership``, ``history``) and declared ``DERIVED_NO_JOIN`` there too. Separately, the
card's expanding same-season mean is not expressible as ``postgame_surrogate_guard``'s
``PRIOR_GAME`` re-derivation (a single ``groupby(...).shift(n_back)``, per
``verify_prior_game_lag``) -- like A16's k=5 rolling window, it is a multi-row aggregate, not a
fixed single-step lag, which is the OTHER reason ``DERIVED_NO_JOIN`` (not ``PRIOR_GAME``) is the
correct frozen lag kind here, not just the nearest one.

K0_MATCHED (P35 k0_matched_frozen, verbatim): null = "identical machinery incl. E=3 imputation, no
other candidate column" (comparison: term_removal). This is a ZERO fitted-parameter null,
eta = log_exposure exactly -- the same character as A16's null (P35 intercept_structure.consequence
literally lists only A02/A03/A05/A16/A25 as the zero-parameter-nulls-recover-incumbent-exactly set;
A18/A20/A26 share that exact same construction by their own k0_matched_frozen text but are NOT
named in that consequence sentence. Flagged in REPORT as a document incompleteness this unit found,
not silently harmonized: nothing about A20's OWN frozen card is ambiguous, so this module implements
A20's card exactly as written, and the omission is reported rather than resolved here).

FRANCHISE CONTINUITY: A20 is NOT named in P33 shared_arm_invariants.p23_franchise_continuity_
precondition (that list is A08/A09/A10/A11/A12/A13/A14/A16/A17/A19/A21/A22/A24 -- all either
all-prior/EWMA or cross-season-window features). A20's "same-season flat" window never looks past
the start of the row's own season, so it has no cross-season history dependency and
requires_franchise_continuity() is False.

DICTIONARY-DRIFT DIAGNOSTIC (card amendment "OPERATIONAL OP-8", non-blocking, flagged for the fit
report, NOT computed by this module): the card registers a preregistered drift diagnostic --
"unmapped-level share > 1% in any team's trailing same-season window -> flagged in the fit report"
-- against the FULL end_reason level dictionary from P34 OP-1. This module has no access to that
full dictionary (only E_TO, the turnover-terminator subset, is frozen here); it cannot itself
compute "unmapped" vs. "known-non-turnover" without it, and does not fabricate that measurement.
This is stated as something this module could NOT establish, not silently skipped.

Epistemic status of this file: IMPLEMENTATION. Blinded: no challenger performance is inspected here
or anywhere in this module. Only unit, synthetic, identity and schema tests exist for it
(TESTS.py in this directory).
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

ARM_ID = "A20_forced_turnover_contrast"
TREATMENT_COL = "z2"

OFFSET_COL = "log_exposure"
TARGET_LABEL = "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"

#: E_TO -- frozen turnover-terminator level set (card ``dictionary_frozen``, verbatim). The
#: artifact's COMPLETE turnover-terminator level set for THIS mechanism, frozen before any fit.
E_TO = frozenset({"turnover"})

#: E_min_prior_games -- frozen E=3 imputation trigger (P33 hyperparameters.fixed.E_min_prior_games;
#: card ``model``: "E = 3 imputation as A18").
E_MIN_PRIOR_GAMES = 3

P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"

REQUIRED_UNIVERSE_COLS = ("game_id", "team_id", "opp_team_id", "game_date", "season")
REQUIRED_POSSESSIONS_COLS = ("game_id", "defense_team_id", "end_reason")


class A20ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No design is returned."""


# --------------------------------------------------------------------------------------------- #
# ftr_game(t, g): per-team-game defensive turnover-forced rate, from possession-level rows
# --------------------------------------------------------------------------------------------- #

def aggregate_game_team_rate(possessions_raw: pd.DataFrame) -> pd.Series:
    """One rate per (team_id, game_id): share of that team's DEFENSIVE possessions in that ONE
    game whose end_reason is in the frozen E_TO dictionary. This is an intermediate, SAME-GAME
    quantity -- it is never itself a design column; only the STRICTLY EARLIER same-season mean of
    it (computed in ``_own_trailing_rate`` below) ever reaches a row's own feature value.
    """
    missing = [c for c in REQUIRED_POSSESSIONS_COLS if c not in possessions_raw.columns]
    if missing:
        raise A20ConstructionFailure(
            f"possessions_raw is missing required columns {missing}; ftr_game(t, g) cannot be "
            f"constructed")
    p = possessions_raw[list(REQUIRED_POSSESSIONS_COLS)].copy()
    n_def = p.groupby(["defense_team_id", "game_id"]).size()
    is_to = p["end_reason"].isin(E_TO)
    n_to = p.loc[is_to].groupby(["defense_team_id", "game_id"]).size()
    n_to = n_to.reindex(n_def.index, fill_value=0)
    if (n_def == 0).any():
        raise A20ConstructionFailure(
            "a (defense_team_id, game_id) pair has zero recorded defensive possessions; ftr_game "
            "is undefined for it")
    rate = (n_to.astype(float) / n_def.astype(float)).rename("ftr_game")
    rate.index = rate.index.set_names(["team_id", "game_id"])
    return rate


# --------------------------------------------------------------------------------------------- #
# the arm module
# --------------------------------------------------------------------------------------------- #

class ArmA20:
    """P36 RUNNER_INTERFACE-conformant module for A20_forced_turnover_contrast.

    Constructed with ONE auxiliary frame beyond ``universe`` (A13's precedent: the frozen hooks
    take no per-call arguments, so any data the card's construction needs beyond the universe frame
    is bound at construction time): ``possessions_raw`` -- possession-level rows carrying
    (game_id, defense_team_id, end_reason), read-only, never mutated.
    """

    arm_id = ARM_ID

    def __init__(self, possessions_raw: pd.DataFrame, fold_ids: Sequence[str] = (),
                n_rows: int | None = None):
        self._rate = aggregate_game_team_rate(possessions_raw)
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows) if n_rows is not None else None

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"                    # P35 p25_guard_invocation_pins

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        # P33 arms[A20].hyperparameters.enumerated == {} ("frozen by source"); RUNNER_INTERFACE.md
        # section 1 names {} for single-element arms.
        return {}

    def element_id(self) -> str:
        return self.arm_id

    def uses_global_intercept(self) -> bool:
        return False                            # A20 in ARMS_WITHOUT_GLOBAL_INTERCEPT

    def requires_franchise_continuity(self) -> bool:
        # A20 is NOT named in P33 p23_franchise_continuity_precondition (same-season flat window
        # never looks past the row's own season start -- no cross-season history dependency).
        return False

    def p23_receipts(self) -> list:
        return []

    def preregistered_contrasts(self):
        return None                             # not A02's obligation

    def prereg_digest_expected(self):
        return None

    def p27_rule(self):
        # The card's kill_conditions_frozen names only "interval covers 0 or no primary-gate
        # improvement; P25 rejection"; no registered S7 numeric active-set rule for A20 (unlike
        # A13/A12's tier-support rules). No rule is frozen at P35 for this card.
        return None

    # ---- feature construction --------------------------------------------------------
    def _own_trailing_rate(self, universe: pd.DataFrame) -> pd.DataFrame:
        """Per-row (own_mean, own_count) for the row's OWN team, aligned to ``universe.index``.

        own_mean(t, g) = mean of ftr_game(t, g') over every g' with the SAME season as g and
        game_date STRICTLY earlier than g's own game_date (P33 "same-season flat" window -- an
        EXPANDING mean, not a k-window). own_count(t, g) = the number of such strictly-earlier
        same-season games (used only to decide the E=3 imputation trigger, never itself a design
        column). A team's first same-season game gets own_mean := 0 (vacuous expanding mean,
        harmless because own_count = 0 < 3 always forces z2 := 0 for that row anyway).
        """
        missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in universe.columns]
        if missing:
            raise A20ConstructionFailure(
                f"universe is missing required columns {missing}")
        tmp = pd.DataFrame({
            "team_id": universe["team_id"].to_numpy(),
            "game_id": universe["game_id"].to_numpy(),
            "season": universe["season"].to_numpy(),
            "game_date": pd.to_datetime(universe["game_date"]).to_numpy(),
        }, index=universe.index)

        key = pd.MultiIndex.from_arrays([tmp["team_id"].to_numpy(), tmp["game_id"].to_numpy()])
        rate_vals = self._rate.reindex(key)
        if rate_vals.isna().any():
            n_missing = int(rate_vals.isna().sum())
            raise A20ConstructionFailure(
                f"{n_missing} universe row(s) have no matching (team_id, game_id) in the supplied "
                f"possessions_raw frame; ftr_game cannot be constructed for them")
        tmp["ftr_game"] = rate_vals.to_numpy(dtype=float)

        # canonical ordering within (team, season): game_date then game_id ascending, mergesort
        # for a deterministic stable tie-break (matches possession_features.load_universe's own
        # sort and A16's precedent, since A20's card names no tie-break rule of its own).
        tmp_sorted = tmp.sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort")
        grp = tmp_sorted.groupby(["team_id", "season"], sort=False)["ftr_game"]
        prior_mean = grp.transform(lambda s: s.shift(1).expanding().mean())
        prior_count = grp.cumcount()

        tmp_sorted = tmp_sorted.assign(
            own_mean=prior_mean.fillna(0.0).to_numpy(),
            own_count=prior_count.to_numpy(dtype=float))
        return tmp_sorted.reindex(universe.index)[["own_mean", "own_count"]]

    def build_design(self, fold, universe: pd.DataFrame) -> dict:
        """RUNNER_INTERFACE.md section 3. Fold-independent, like A16's dev_own/dev_opp: ftr_own is
        a deterministic, strictly-lagged per-row historical fact built from every row STRICTLY
        earlier (by game_date) in the row's own season that exists anywhere in the supplied
        universe, which is exactly what "prior-games-only, same-season" means regardless of which
        rows are in a given fold's train/test split; ``fold`` is accepted per the frozen signature
        and not otherwise used.
        """
        del fold  # signature-required, unused: see docstring
        own = self._own_trailing_rate(universe)
        own_mean = own["own_mean"].to_numpy(dtype=float)
        own_count = own["own_count"].to_numpy(dtype=float)

        lookup_mean = pd.Series(
            own_mean,
            index=pd.MultiIndex.from_arrays(
                [universe["game_id"].to_numpy(), universe["team_id"].to_numpy()]))
        lookup_count = pd.Series(own_count, index=lookup_mean.index)
        if lookup_mean.index.has_duplicates:
            raise A20ConstructionFailure(
                "A20: (game_id, team_id) is not unique in the supplied universe; opponent lookup "
                "requires exactly one row per team per game")
        opp_key = pd.MultiIndex.from_arrays(
            [universe["game_id"].to_numpy(), universe["opp_team_id"].to_numpy()])
        opp_mean = lookup_mean.reindex(opp_key).to_numpy(dtype=float)
        opp_count = lookup_count.reindex(opp_key).to_numpy(dtype=float)
        if np.isnan(opp_mean).any():
            raise A20ConstructionFailure(
                "A20: opponent lookup failed for one or more rows -- every row's opp_team_id must "
                "have its own row in the same universe at the same game_id (two-sided game "
                "universe invariant); a NaN here means that invariant does not hold on the "
                "supplied frame")

        insufficient = (own_count < E_MIN_PRIOR_GAMES) | (opp_count < E_MIN_PRIOR_GAMES)
        z2_raw = own_mean - opp_mean
        z2 = np.where(insufficient, 0.0, z2_raw)

        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": [],
            "k0_matched_design": {
                "treatment_cols": [],
                "nuisance_cols": [],
                "comparison": "term_removal",
            },
            "indicator_cols": [],
            "columns": {TREATMENT_COL: z2},
        }

    # ---- P22 lag declaration ---------------------------------------------------------
    def lag_specs(self) -> dict:
        return {
            TREATMENT_COL: dict(
                column=TREATMENT_COL,
                kind="DERIVED_NO_JOIN",
                source_artifact_id="possessions_raw_v2/via_constructor_injection",
                entity_keys=("team_id", "game_id", "season"),
                order_column="game_date",
                n_back=1,
                strict=True,
                null_policy="deterministic_zero_on_either_side_under_E_min_prior_games",
                rationale=(
                    "z2 = ftr_own - ftr_opp; ftr_team(t, g) is the mean, over team t's STRICTLY "
                    "EARLIER SAME-SEASON games only, of that game's own share of team t's "
                    "DEFENSIVE possessions whose end_reason is in the frozen E_TO={'turnover'} "
                    "dictionary (P34 OP-1). Built from a possession-level auxiliary frame bound "
                    "at this module's construction (A13's own precedent for exactly this "
                    "situation: CONT_MAIN_COL/DEV_PREV_COL are likewise constructor-injected and "
                    "declared DERIVED_NO_JOIN), and from an expanding (not fixed-shift) mean, "
                    "which postgame_surrogate_guard.verify_prior_game_lag's single-shift "
                    "re-derivation contract does not express (A16's own precedent for that "
                    "second, independent reason). z2 := 0 whenever EITHER side has fewer than "
                    "E_min_prior_games=3 strictly-earlier same-season games (card 'E=3 imputation "
                    "as A18')."),
            ),
        }

    def lag_sources(self) -> dict:
        # DERIVED_NO_JOIN skips PRIOR_GAME re-derivation (postgame_surrogate_guard.audit only
        # calls verify_prior_game_lag for kind == PRIOR_GAME); no source frame is required.
        return {}

    # ---- P26 k0_matched/1 record --------------------------------------------------------
    def p26_k0_record(self) -> dict:
        """The full ``k0_matched/1`` record (P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_SCHEMA.json),
        consistent with the frozen P35 card's ``p26_k0_record`` and ``k0_matched_frozen`` blocks.
        Called with no arguments: a STATIC contract declaration, not a per-run measurement.
        """
        rows_invariant = ("P35 universe: 2,982 team-game rows / 1,491 game clusters (D006 "
                          "chronological folds); training/evaluation row sets identical between "
                          "arm and null within every fold -- both are drawn from the SAME "
                          "universe frame")
        folds_invariant = ["train_lt_2022", "train_lt_2023", "train_lt_2024", "train_lt_2025",
                           "train_lt_2026"]
        offset_invariant = ("log_exposure = log(projected_team_off_possessions), frozen "
                            "incumbent D_ewma_shrunk (K=200, alpha=0.1), never retuned")
        fallback_invariant = (
            "deterministic per-row substitution: z2 := 0 whenever team t's or opponent team's "
            "count of strictly-earlier SAME-SEASON completed games is < E_min_prior_games=3 "
            "(P33 hyperparameters.fixed.E_min_prior_games; card 'E = 3 imputation as A18'); "
            "ftr_team(t, g) itself is an EXPANDING same-season mean of the per-game defensive "
            "turnover-forced share ('same-season flat' window, P33 D6), zero-based when a team "
            "has no strictly-earlier same-season games. Identical machinery in arm and null: the "
            "null carries no z2 term at all, so the rule is vacuously satisfied there, but no "
            "IMPLEMENTATION-side difference in fallback machinery exists between the two designs")

        dims = {
            "intercept_treatment": ("no global intercept in arm or null; fit_intercept=False "
                                    "identically (P35 intercept_structure; A20's zero-parameter "
                                    "null recovers the incumbent exactly, eta = offset exactly, "
                                    "the same construction as A16's -- see module docstring for "
                                    "the P35 consequence-sentence omission this unit flags)"),
            "calibration_freedom": "none -- no post-fit rescaling of any kind",
            "penalty_treatment": ("none -- quasi-Poisson IRLS, unpenalised, log link (P33 "
                                  "estimation_objective_frozen_here)"),
            "exposure_offset": offset_invariant,
            "training_rows": rows_invariant,
            "evaluation_rows": rows_invariant,
            "chronological_folds": list(folds_invariant),
            "clipping": "none",
            "link_function": "log",
            "preprocessing": ("none -- no standardisation or centering; ftr_own/ftr_opp/z2 are "
                              "computed directly as possession-count shares on [-1, 1] and are "
                              "not rescaled"),
            "missing_value_handling": fallback_invariant,
            "companion_components": "none",
            "fallback_rules": fallback_invariant,
            "aggregation": "none -- the unit of prediction is the team-game row",
            "candidate_universe": ("2,982 team-game rows / 1,491 game clusters (P35 universe; "
                                   "games never split across folds or bootstrap draws)"),
            "post_processing": "none",
            "prediction_universe": ("2,982 team-game rows / 1,491 game clusters (P35 universe; "
                                    "games never split across folds or bootstrap draws)"),
        }

        def side(name: str, role: str, substantive: list) -> dict:
            import copy
            return {
                "name": name, "role": role, "pipeline_id": "p36_shared_runner/1",
                "substantive_features": list(substantive), "structural_terms": [],
                "declaration_routing": {t: "substantive_features" for t in substantive},
                "comparison_gate_sidespec": copy.deepcopy(dims),
            }

        return {
            "schema": "k0_matched/1",
            "arm_id": ARM_ID,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": (
                    "which side of a game forces more turnovers on defense predicts possession "
                    "creation (P31 OPPONENT_MECHANISM_H2); the arm tests whether the OWN-minus-"
                    "OPPONENT same-season trailing forced-turnover-share contrast carries "
                    "information beyond the incumbent's own projection"),
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{
                    "name": "beta2", "role": "coefficient", "null_value": 0,
                    "null_value_meaning": "no forcing asymmetry signal",
                }],
                "claimed_signal_axes": ["team_identity", "opponent_identity"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        "removing z2 leaves eta = log_exposure exactly, i.e. the frozen incumbent "
                        "projection with zero fitted parameters; no team- or opponent-specific "
                        "turnover-forcing asymmetry of any kind remains in the design"),
                },
            },
            "invariants": {
                "rows": rows_invariant,
                "target": TARGET_LABEL,
                "folds": list(folds_invariant),
                "weights": "equal per team-game row",
                "offset": offset_invariant,
                "fallback_machinery": fallback_invariant,
                "nuisance_terms": [],
                "lower_order_structural_terms": [],
            },
            "arm_spec": side("A20_arm", "challenger", [TREATMENT_COL]),
            "k0_spec": side("A20_k0", "k0", []),
            "fold_local_fallback": {
                "required": True,
                "trigger": ("either team's count of strictly-earlier same-season completed games "
                           "< E_min_prior_games=3 -> z2 := 0 for that row (card 'E = 3 imputation "
                           "as A18')"),
                "numeric_threshold": E_MIN_PRIOR_GAMES,
                # See A16's identically-reasoned NOTED comment: the frozen K0_MATCHED_SCHEMA
                # action enum (drop_term_for_fold / collapse_to_parent_tier / refuse_to_score_fold
                # / not_applicable) was written for the tier/partition zero-variance failure mode,
                # which A20 does not have (no structural/tier terms). "not_applicable" is used as
                # the nearest available label; the true, numeric, registered-before-results rule
                # is stated in full in "trigger" above and in "fallback_machinery" above. Flagged
                # for P37, not resolved by inventing a fifth enum value in a frozen schema.
                "action": "not_applicable",
                "registered_before_results": True,
            },
            "verdict_label_policy": (
                "eligible for FEATURE VALUE DEMONSTRATED via challenger_vs_k0 against this record "
                "(arm_kind substantive_feature; NOT calibration_only, so no verdict-label ceiling "
                "applies)"),
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "P35 shared_frozen_amendments.multiplicity_recomputed / P33 multiplicity_family: "
                "OPPONENT_MECHANISM_F1, members {A18: 1, A20: 1, A26: 1}, budget_elements 3, "
                "Holm correction alpha 0.05 -- A20's single test is NOT evaluated at alpha 0.05 "
                "unadjusted; it shares a 3-element Holm family with A18 and A26.",
                "P35 intercept_structure.consequence names only A02/A03/A05/A16/A25 as the "
                "zero-parameter-nulls-recover-incumbent-exactly set; A20's own k0_matched_frozen "
                "text ('identical machinery ... no other candidate column') is the SAME "
                "zero-fitted-parameter construction. This module implements A20's own frozen card "
                "exactly as written; the consequence-sentence omission is reported, not silently "
                "harmonized (see module docstring).",
                "Card amendment 'OPERATIONAL OP-8': a non-blocking dictionary-drift diagnostic "
                "(unmapped end_reason level share > 1% of a team's trailing same-season window) "
                "is registered for the fit report. This module cannot compute it (no access to "
                "the full P34 OP-1 level dictionary, only the frozen E_TO subset) and does not "
                "fabricate the measurement; flagged as could-not-establish.",
                "Card amendment 'K0 K2: no global intercept pinned' -- see intercept_treatment "
                "dimension above.",
            ],
        }


def make_arms(possessions_raw: pd.DataFrame, fold_ids: Sequence[str] = (),
             n_rows: int | None = None) -> list[ArmA20]:
    """Single-element arm -- one module instance, per RUNNER_INTERFACE.md section 1."""
    return [ArmA20(possessions_raw, fold_ids, n_rows)]
