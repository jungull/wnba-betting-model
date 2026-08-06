#!/usr/bin/env python3
"""arm_a16.py -- P36 arm module for A16_lag_residual_own_minus_opp.

FROZEN CARD THIS IMPLEMENTS (verbatim binding source): P35_FREEZE_TASK_CARDS/SPEC.json,
sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32, task_cards[arm_id ==
"A16_lag_residual_own_minus_opp"], amending the P33_PREREGISTRATION_DRAFT/SPEC.json arm record
(sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093) by hash reference per
the card's carry_convention. Every pinned clock, window, centering constant and enumeration
element below is taken from those two documents; nothing here is invented.

MODEL (P35 task card, verbatim): eta = log_exposure + beta * (dev_own - dev_opp); mu = exp(eta);
NO global intercept in arm or null (P35 intercept_structure: A16 is in
ARMS_WITHOUT_GLOBAL_INTERCEPT); single element k = 5 (P33 hyperparameters.fixed.k_window_games,
"ENUMERATION OBLIGATION DISCHARGED ... fixed here at k = 5"; not a genuine multi-value grid, so
this module binds ONE arm with no enumerated variant -- RUNNER_INTERFACE.md section 1: "{} for
single-element arms").

dev_team(t, g) = mean over the last k = 5 completed games of team t that are BOTH (a) strictly
earlier than g by (game_date, game_id) ascending -- the program's canonical row ordering, also
used by ``possession_features.load_universe`` (sort_values(["game_date","game_id","team_id"]))
and named explicitly for A08 (construction_pins.a08_window_tie_break); A16's card does not repeat
a tie-break rule of its own, so this module reuses the program's one existing canonical ordering
rather than inventing a second one. Flagged in REPORT for P37 as a card-silent choice, not
invented from nothing. -- and (b) RESOLVED (both member games are already restricted to
pace_resolved rows because they are drawn from the same universe frame this module is handed;
the 8 opening-day pace_resolved==False rows never enter any universe this module sees, matching
P35 opening_day_null_row_handling_frozen point (1)-(2)) of (realised_team_off_possessions_reg_equiv
- projected_team_off_possessions) for that prior game. Partial windows (1-4 resolved members) are
used as-is (P35 point 3). Zero resolved prior games -> dev_team := 0 (P35 point 4, empty_window
rule). The treatment is dev_own - dev_opp (P35 point 5), defined on every row.

dev_opp(t, g) is NOT dev computed on the CURRENT game's box score -- it is the OPPONENT team's
OWN dev_team value, i.e. the same trailing-window computation run for opp_team_id, evaluated at
the same game g (opp_team_id has its own row in the universe for game g; this module looks that
row's dev_team value up by (game_id, team_id)). This is what "own-minus-opp" residual momentum
means in the card's mechanism statement.

K0_MATCHED (P35 k0_matched_frozen, verbatim): null = "[log_exposure] identical machinery - zero
fitted parameters; IS the frozen incumbent" (comparison: term_removal). Under the P35
no_implementation_default_intercept_invariant and the intercept table, A16's zero-parameter null
recovers the incumbent projection EXACTLY (P35 intercept_structure.consequence names A16 by name).

FRANCHISE CONTINUITY: A16 is named in P33 shared_arm_invariants.p23_franchise_continuity_precondition
(cross-season trailing history feature) -> requires_franchise_continuity() is True and this module
supplies a P23 team_cities.csv receipt pinned to the frozen sha256
(P35 franchise_continuity_receipt_pin).

LAG DECLARATION: dev_own - dev_opp is declared DERIVED_NO_JOIN, not PRIOR_GAME. It is a k=5
ROLLING mean over prior rows of the SAME team, not a single n_back=1 shift of one column, so it
does not fit postgame_surrogate_guard.verify_prior_game_lag's re-derivation contract (which
re-derives a single groupby(...).shift(n_back)). It is built entirely from columns already
present in the audited universe frame (team_id, game_date, game_id, projected_team_off_possessions,
realised_team_off_possessions_reg_equiv -- all merged into the universe by
possession_features.load_universe before this module ever runs), with no additional external
join performed by this module. DERIVED_NO_JOIN still faces the full P22 dependency battery.

Epistemic status of this file: IMPLEMENTATION. Blinded: no challenger performance is inspected
here or anywhere in this module. Only unit, synthetic, identity and schema tests exist for it
(TESTS.py in this directory).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ARMS_DIR = HERE.parent                      # .../P36_IMPLEMENT_ARMS/arms
P36_DIR = ARMS_DIR.parent                   # .../P36_IMPLEMENT_ARMS
STAGE2B = P36_DIR.parent                    # .../stage2b
RUNNER_DIR = P36_DIR / "runner"
P22_DIR = STAGE2B / "P22_POSTGAME_SURROGATE_GUARD"

# read-only imports of frozen/shared modules this arm module depends on -- never edited here
# (standing rule 3: enforcement/consumption at the call site, never a shared-artifact edit).
for _p in (RUNNER_DIR, P22_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import runner_constants as RC                                                    # noqa: E402
import postgame_surrogate_guard as psg                                           # noqa: E402

# --------------------------------------------------------------------------------------------
# frozen pins this module binds to (restated from runner_constants.py / P35 SPEC.json, not
# re-invented -- see module docstring for the exact source lines)
# --------------------------------------------------------------------------------------------
ARM_ID = "A16_lag_residual_own_minus_opp"
K_WINDOW_GAMES = 5                          # P33 hyperparameters.fixed.k_window_games (frozen)
TREATMENT_COL = "dev_own - dev_opp"         # P35 k0_matched_frozen.treatment_terms[0], verbatim

TARGET_COL = RC.TARGET_COL_REAL                       # "realised_team_off_possessions_reg_equiv"
PROJECTION_COL = RC.INCUMBENT_PROJECTION_COL           # "projected_team_off_possessions"
OFFSET_COL = RC.OFFSET_COL                             # "log_exposure"
CLUSTER_COL = RC.CLUSTER_COL                           # "game_id"

TEAM_CITIES_SHA256_PIN = RC.TEAM_CITIES_SHA256_PIN
P35_SPEC_SHA256 = RC.P35_SPEC_SHA256

# module-level attribute required by RUNNER_INTERFACE.md section 2 (`arm_id: str attr`)
arm_id = ARM_ID


# --------------------------------------------------------------------------------------------
# required hooks
# --------------------------------------------------------------------------------------------

def card_id() -> str:
    return ARM_ID


def declared_family() -> str:
    return RC.DECLARED_FAMILY_ALL_FITTED_ARMS          # "SUBSTANTIVE" -- P35 p25_guard_invocation_pins


def recalibration_declaration() -> str:
    return RC.RECALIBRATION_DECLARATION                # "NOT_APPLICABLE"


def enumeration_element() -> dict:
    # k = 5 is a fixed constant, not a genuine multi-value grid (P33: "ENUMERATION OBLIGATION
    # DISCHARGED ... Single element charged; any other window length is ... NOT fitted this
    # cycle"). RUNNER_INTERFACE.md section 1 names {} for single-element arms.
    return {}


def element_id() -> str:
    return ARM_ID


def uses_global_intercept() -> bool:
    return False                                        # A16 in ARMS_WITHOUT_GLOBAL_INTERCEPT


def requires_franchise_continuity() -> bool:
    # P33 shared_arm_invariants.p23_franchise_continuity_precondition names A16 explicitly
    # (cross-season history feature: the k=5 trailing window can span a season boundary).
    return True


def p23_receipts() -> list:
    return [{
        "team_cities_sha256": TEAM_CITIES_SHA256_PIN,
        "artifact": "data/reference/team_cities.csv",
        "purpose": ("franchise continuity across the PHO/PHX rebrand (team_id 1611661317) for "
                    "A16's cross-season trailing team-history window (dev_own / dev_opp); "
                    "P33 shared_arm_invariants.p23_franchise_continuity_precondition names A16; "
                    "team_id is keyed directly through the universe's own team_id column, "
                    "matching A11's declared pattern"),
        "basis": "P35 shared_frozen_amendments.franchise_continuity_receipt_pin",
        "p35_spec_sha256": P35_SPEC_SHA256,
    }]


def p27_rule():
    # P33's A16 card states only prose fold-local considerations ("per-fold rank and condition
    # checks (contrast is a function of the same evidence stream the offset was built from)"),
    # not a registered numeric S7 ActiveSetRule/Preregistration pair (unlike A15's declared
    # absence of one, or A17/A18's registered empty-window share rules). No rule is frozen for
    # A16 at P35; the card does not name a fold_estimability_guard active-set rule for it.
    return None


def preregistered_contrasts():
    # A16 carries no P25-preregistered contrast record (that obligation is A02's alone --
    # P35 p25_guard_invocation_pins.a02_contrast_reconciliation).
    return None


def prereg_digest_expected():
    return None


def lag_specs() -> dict:
    return {
        TREATMENT_COL: dict(
            column=TREATMENT_COL,
            kind=psg.DERIVED_NO_JOIN,
            source_artifact_id="team_possession_prior_v1+possessions_raw_v2/via_universe",
            entity_keys=("team_id",),
            order_column="game_date",
            n_back=K_WINDOW_GAMES,
            strict=True,
            null_policy="deterministic_zero_on_zero_resolved_prior_games",
            rationale=(
                "k=5 trailing mean of (realised_team_off_possessions_reg_equiv - "
                "projected_team_off_possessions) over the row's own team's STRICTLY EARLIER "
                "resolved games, ordered (game_date, game_id) ascending (the program's canonical "
                "row ordering), minus the identical quantity computed for the opponent team as "
                "of the same game (P35 A16 card, opening_day_null_row_handling_frozen). Built "
                "entirely from columns already present in the audited universe frame -- no "
                "additional external join is performed by this module."),
        ),
    }


def lag_sources() -> dict:
    # DERIVED_NO_JOIN skips PRIOR_GAME re-derivation (postgame_surrogate_guard.audit only calls
    # verify_prior_game_lag for kind == PRIOR_GAME); no source frame is required or supplied.
    return {}


# --------------------------------------------------------------------------------------------
# feature construction
# --------------------------------------------------------------------------------------------

def _own_trailing_dev(frame: pd.DataFrame, k: int = K_WINDOW_GAMES) -> pd.Series:
    """dev_team(t, g) for every row, aligned to ``frame.index``.

    Strictly lagged: ``shift(1)`` before the rolling window guarantees the row's own game never
    enters its own trailing mean. ``min_periods=1`` admits partial windows (1-4 resolved prior
    games) as-is (P35 point 3). Rows with zero prior games in the team's history produce NaN from
    the shift, filled to 0.0 (P35 point 4, the empty-window rule).
    """
    dev = (frame[TARGET_COL].to_numpy(dtype=float) - frame[PROJECTION_COL].to_numpy(dtype=float))
    tmp = pd.DataFrame(
        {"team_id": frame["team_id"].to_numpy(),
         "game_date": pd.to_datetime(frame["game_date"]).to_numpy(),
         "game_id": frame["game_id"].to_numpy(),
         "dev": dev},
        index=frame.index)
    # canonical ordering: (game_date, game_id) ascending within each team, mergesort for a
    # deterministic stable tie-break (matches possession_features.load_universe's own sort).
    tmp = tmp.sort_values(["team_id", "game_date", "game_id"], kind="mergesort")
    trailing = tmp.groupby("team_id", sort=False)["dev"].transform(
        lambda s: s.shift(1).rolling(window=k, min_periods=1).mean())
    trailing = trailing.fillna(0.0)
    return trailing.reindex(frame.index)


def _dev_own_minus_opp(frame: pd.DataFrame, k: int = K_WINDOW_GAMES) -> np.ndarray:
    dev_own = _own_trailing_dev(frame, k=k)
    lookup = pd.Series(
        dev_own.to_numpy(dtype=float),
        index=pd.MultiIndex.from_arrays(
            [frame["game_id"].to_numpy(), frame["team_id"].to_numpy()]))
    if lookup.index.has_duplicates:
        raise ValueError(
            "A16: (game_id, team_id) is not unique in the supplied universe; dev_opp lookup "
            "requires exactly one row per team per game")
    opp_key = pd.MultiIndex.from_arrays(
        [frame["game_id"].to_numpy(), frame["opp_team_id"].to_numpy()])
    dev_opp = lookup.reindex(opp_key).to_numpy(dtype=float)
    if np.isnan(dev_opp).any():
        raise ValueError(
            "A16: opponent lookup failed for one or more rows -- every row's opp_team_id must "
            "have its own row in the same universe at the same game_id (two-sided game universe "
            "invariant); a NaN here means that invariant does not hold on the supplied frame")
    return dev_own.to_numpy(dtype=float) - dev_opp


def build_design(fold, universe) -> dict:
    """RUNNER_INTERFACE.md section 3. Fold-independent: dev_own/dev_opp is a deterministic,
    strictly-lagged per-row historical fact (not a training-fold-estimated nuisance constant like
    A13's cbar_F or A17's imputation means), so the SAME construction runs for every fold and for
    the FINAL_ASSEMBLED_DESIGN pseudo-fold; ``fold`` is accepted per the frozen signature and not
    otherwise used. It always uses every row STRICTLY EARLIER than a given row's own game_date
    that exists anywhere in the supplied universe, which is exactly what "prior-games-only" means
    regardless of which rows are in a given fold's train/test split.
    """
    del fold  # signature-required, unused: see docstring
    contrast = _dev_own_minus_opp(universe, k=K_WINDOW_GAMES)
    return {
        "treatment_cols": [TREATMENT_COL],
        "nuisance_cols": [],
        "k0_matched_design": {
            "treatment_cols": [],
            "nuisance_cols": [],
            "comparison": "term_removal",
        },
        "indicator_cols": [],
        "columns": {TREATMENT_COL: contrast},
    }


# --------------------------------------------------------------------------------------------
# P26 k0_matched/1 record
# --------------------------------------------------------------------------------------------

_ROWS_INVARIANT = ("P35 universe: 2,982 team-game rows / 1,491 game clusters (D006 chronological "
                   "folds); training/evaluation row sets identical between arm and null within "
                   "every fold -- both are drawn from the SAME universe frame")
_FOLDS_INVARIANT = ["train_lt_2022", "train_lt_2023", "train_lt_2024", "train_lt_2025",
                    "train_lt_2026"]
_OFFSET_INVARIANT = ("log_exposure = log(projected_team_off_possessions), frozen incumbent "
                     "D_ewma_shrunk (K=200, alpha=0.1), never retuned")
_FALLBACK_INVARIANT = (
    "deterministic empty/partial-window imputation: dev_team(t, g) is the mean of "
    "(realised_team_off_possessions_reg_equiv - projected_team_off_possessions) over team t's "
    "last k=5 STRICTLY EARLIER resolved games; partial windows (1-4 games) are used as-is; "
    "dev_team := 0 when a team has zero resolved prior games (P35 A16 card, "
    "opening_day_null_row_handling_frozen points 3-4). Identical machinery in arm and null: the "
    "null carries no dev term at all, so the rule is vacuously satisfied there, but no "
    "IMPLEMENTATION-side difference in fallback machinery exists between the two designs")

_DIMS = {
    "intercept_treatment": ("no global intercept in arm or null; fit_intercept=False identically "
                            "(P35 intercept_structure; the zero-parameter null recovers the "
                            "incumbent exactly, eta = offset exactly)"),
    "calibration_freedom": "none -- no post-fit rescaling of any kind",
    "penalty_treatment": "none -- quasi-Poisson IRLS, unpenalised, log link (P33 estimation_objective_frozen_here)",
    "exposure_offset": _OFFSET_INVARIANT,
    "training_rows": _ROWS_INVARIANT,
    "evaluation_rows": _ROWS_INVARIANT,
    "chronological_folds": list(_FOLDS_INVARIANT),
    "clipping": "none",
    "link_function": "log",
    "preprocessing": ("none -- no standardisation or centering; dev_own/dev_opp are computed "
                      "directly on the regulation-equivalent-possessions scale of the target"),
    "missing_value_handling": _FALLBACK_INVARIANT,
    "companion_components": "none",
    "fallback_rules": _FALLBACK_INVARIANT,
    "aggregation": "none -- the unit of prediction is the team-game row",
    "candidate_universe": "2,982 team-game rows / 1,491 game clusters (P35 universe; games never split across folds or bootstrap draws)",
    "post_processing": "none",
    "prediction_universe": "2,982 team-game rows / 1,491 game clusters (P35 universe; games never split across folds or bootstrap draws)",
}


def _side(name: str, role: str, substantive: list, structural: list) -> dict:
    import copy
    return {
        "name": name,
        "role": role,
        "pipeline_id": "stage2b_possession_runner/1",
        "substantive_features": list(substantive),
        "structural_terms": list(structural),
        "declaration_routing": {t: "substantive_features" for t in substantive},
        "comparison_gate_sidespec": copy.deepcopy(_DIMS),
    }


def p26_k0_record() -> dict:
    """The full ``k0_matched/1`` record (P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_SCHEMA.json),
    consistent with the frozen P35 card's ``p26_k0_record`` and ``k0_matched_frozen`` blocks.
    Called with no arguments (RUNNER_INTERFACE.md section 2): this is the STATIC contract
    declaration validated at fit initialisation, before any data is touched, not a per-run
    measurement.

    NOTED, NOT SILENTLY RESOLVED: ``fold_local_fallback.action`` is one of four frozen enum
    values (drop_term_for_fold / collapse_to_parent_tier / refuse_to_score_fold / not_applicable
    -- K0_MATCHED_SCHEMA.json), none of which literally names "deterministic value substitution
    for an empty/partial trailing window". That vocabulary was written for the tier/partition
    zero-variance failure mode (GATE_INVOCATION_CONTRACT section 4), which A16 does not have (no
    structural/tier terms). ``not_applicable`` is used as the nearest available label; the true,
    numeric, registered-before-results rule is stated in full in ``trigger`` below and in
    ``invariants.fallback_machinery`` above. This is flagged for P37, not resolved by inventing a
    fifth enum value in a frozen schema.
    """
    return {
        "schema": "k0_matched/1",
        "arm_id": ARM_ID,
        "arm_kind": "substantive_feature",
        "treatment_mechanism": {
            "statement": (
                "a team's realised-minus-projected pace residual persists into its next game; "
                "the arm tests whether the OWN-minus-OPPONENT trailing residual, each computed "
                "from that team's own strictly-earlier resolved games, carries information beyond "
                "the incumbent's own projection"),
            "treatment_terms": [TREATMENT_COL],
            "tested_parameters": [{
                "name": "beta", "role": "coefficient", "null_value": 0.0,
                "null_value_meaning": "no residual momentum beyond the offset",
            }],
            "claimed_signal_axes": ["team_identity", "opponent_identity"],
            "null_construction": {
                "method": "term_removal",
                "destroys_claimed_signal": (
                    "removing dev_own - dev_opp leaves eta = log_exposure exactly, i.e. the "
                    "frozen incumbent projection with zero fitted parameters; no team- or "
                    "opponent-specific residual-momentum quantity of any kind remains in the "
                    "design"),
            },
        },
        "invariants": {
            "rows": _ROWS_INVARIANT,
            "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
            "folds": list(_FOLDS_INVARIANT),
            "weights": "equal per team-game row",
            "offset": _OFFSET_INVARIANT,
            "fallback_machinery": _FALLBACK_INVARIANT,
            "nuisance_terms": [],
            "lower_order_structural_terms": [],
        },
        "arm_spec": _side("A16_arm", "challenger", [TREATMENT_COL], []),
        "k0_spec": _side("A16_k0", "k0", [], []),
        "fold_local_fallback": {
            "required": True,
            "trigger": ("0 resolved prior games in team t's trailing k=5 window (either own or "
                        "opponent side) -> dev_team(t, g) := 0; 1-4 resolved prior games -> mean "
                        "of however many exist, used as-is (P35 A16 card, "
                        "opening_day_null_row_handling_frozen points 3-4)"),
            "numeric_threshold": 0,
            "action": "not_applicable",  # see docstring NOTED section above
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
            "lagged_pace_contrast_family, members {A16: 1}, budget_elements 1, single test at "
            "alpha 0.05 (no Holm correction within this one-arm family).",
            "P35 shared_frozen_amendments.intercept_structure.consequence names A16 explicitly: "
            "'the zero-parameter nulls of A02, A03, A05, A16 and A25 ARE the frozen incumbent "
            "exactly'.",
        ],
    }
