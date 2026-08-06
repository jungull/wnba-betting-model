#!/usr/bin/env python3
"""A14_expansion_intercept_decay.py -- P36 arm module for A14_expansion_intercept_decay.

FROZEN CARD (verbatim binding source): experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/
SPEC.json, sha256 68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32 (verified at
implementation time), task_cards[].arm_id == "A14_expansion_intercept_decay", carrying P33
PREREGISTRATION_DRAFT/SPEC.json (sha256 066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072
d347d093) arms[A14_expansion_intercept_decay] by hash reference, amended exactly by the card's
amendments_applied list.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

STATUS (card, verbatim): FIT_READY_PROMOTION_INELIGIBLE (single-active-fold diagnostic; fixed
Holm slot). A14 occupies 1 element of the COLDSTART_FALLBACK budget as a FIXED SLOT: charged to
m, EXCLUDED from the Holm step-down ordering (p := 1, always last, never blocks). Nothing in this
module decides multiplicity; that is runner/fit-time territory. This module implements only the
feature construction, the K0_MATCHED design, the frozen fold-local active-set rule, and the
frozen single-fold kill-condition decision chain.

MODEL (frozen, card-pinned):
    eta = intercept + log_exposure + [gap | depth | opp_depth | exp(-n_i/5) league-common decay]
          + kappa * exp_i * exp(-n_i/5)
    mu  = exp(eta)
    free global intercept, arm AND null identically (P35 intercept_structure table: A14 in
    ARMS_WITH_FREE_GLOBAL_INTERCEPT).

TREATMENT: kappa * exp_i * exp(-n_i/5). exp_i = 1[team's first season in the contract schedule is
>= 2022 AND equals the row's own season] (P33 formula, verbatim). tau = 5 FIXED by source, never
tunable (shared with A07/A12/A13's h=5 / A15's s-scale=5 -- P35 construction_pins.not_fold_blind_
note names tau=5/h=5/k=5/s-scale=5 as the program's one recurring frozen trailing-evidence scale).

COLUMN LINEAGE (frozen, byte-exact names from the receipted incumbent path,
experiments/player_program/possession_features.py):
    gap       -> pace_gap                = team_pace_estimate - opp_pace_estimate
    depth     -> pace_evidence_depth     = trailing-window evidence count backing the team's own
                                           pace estimate, capped at WINDOW_K=10, 0 on league-prior
                                           fallback
    opp_depth -> opp_pace_evidence_depth = same, for the opponent
These three, PLUS the league-common decay term exp(-n_i/5) itself, PLUS the explicit intercept,
are K0 K5 (P35 amendment): "receipted incumbent-path features plus generic early-season drift
GRANTED TO THE NULL (S6 direction 1); NO expansion-indexed term (direction 2)". The null is
therefore deliberately STRONGER than the incumbent on early-season drift, and MAE(K0[A14]) is NOT
an incumbent benchmark. exp_i itself -- alone, outside the interaction -- is granted to NEITHER
the arm NOR the null: the arm's own frozen formula above carries no standalone exp_i term, only
the product kappa*exp_i*exp(-n_i/5). This is a deliberate, card-pinned asymmetric design (S6
direction 2 reads literally as "no expansion-indexed term" full stop, not "no expansion-indexed
term beyond what direction 1 already grants") -- see the NAMING DISCLOSURE below for how this
module avoids a P26 false-positive on that exact point.

n_i (frozen, card-pinned; construction "as A07" / shared construction_pins.n_clock_pin):
    "team's completed same-season contract games strictly before the target date (team clock,
    within-cluster variation possible)" -- computed on the CONTRACT SCHEDULE (the 2,990 team-game
    rows of team_possession_prior_v1, INCLUDING the four universe-excluded 2021 opening-day
    games). "The universe-row clock is barred." This module carries its OWN copy of the A07
    compute_n_i logic (never imports arms/A07 -- standing rule: this unit touches only arms/A14/)
    so it has no runtime dependency on any sibling arm module; the formula is identical by card
    construction, not by import.

exp_i (frozen, card formula, verbatim): "exp_i = 1[team's first season in contract schedule >=
2022 and equals season_i]". first_season(team) is computed on the SAME contract-schedule frame as
n_i (a team's first season is a pure schedule fact). Measured at P33/P35 freeze (support_measured_
by_this_node, carried, NOT re-measured by this node): the expansion teams in the frozen prior
artifact are 1611661331 (first season 2025) and 1611661327 / 1611661332 (first season 2026); team
1611661317 (the PHO/PHX rebrand) carries first season 2021 under the single team_id the artifact
uses, so it never satisfies exp_i's >= 2022 clause (shared_arm_invariants.p23_franchise_continuity_
precondition measured note, carried).

K0_MATCHED[A14] (frozen, card k0_matched_frozen):
    null: [log_exposure | gap | depth | opp_depth | exp(-n/5) league-common decay | intercept]
          (comparison: term_removal)
    treatment_terms (card prose): ["exp_i:exp(-n_i/5)"]
    tested_parameters: [{kappa, coefficient, null_value=0}]

NAMING DISCLOSURE, NOT SILENTLY RESOLVED (standing rule 1: frozen bytes govern over prose; a
contradiction is reported, never silently reconciled) -- flagged for P37, parallel to A07's SCHEDULE
lag-kind disclosure: the card's own prose spells the treatment term with a colon,
"exp_i:exp(-n_i/5)", the program's INTERACTION notation (e.g. A11's "w(n):dev_prev", A13's
"(cont - cbar_F):dev_prev"). The frozen P26 validator (validate_k0_matched.check_relation, rule
R6, "lower_order_term_missing_from_k0") reads any ":"-joined treatment-term STRING as an
interaction whose factors must each be either substantive in the arm or a structural (K0) term --
otherwise it raises a BLOCKING finding. A12/A13's own colon-named interactions satisfy R6 because
their card explicitly grants the OTHER factor (w(n)) a main-effect slot in K0 ("null ... owns the
w(n) main" / A12 carried into A13). A14's card does the opposite on purpose: K0_MATCHED[A14] is
frozen to hold "NO expansion-indexed term" AT ALL, and the arm's own eta has no standalone exp_i
term either (verified above from the model formula) -- there is no main-effect asymmetry to guard
against, because NEITHER side ever carries exp_i alone. Materialising the treatment column under
the literal colon-bearing string would trip R6 as a false positive: it would force this module to
either (a) fabricate an exp_i main-effect column nowhere pinned by the card, silently changing the
preregistered design, or (b) grant K0 an exp_i term the card explicitly forbids, silently
reconciling a real tension in the frozen text by editing the card's own null. Neither is
acceptable. This module instead materialises the interaction as ONE opaque column,
"expansion_decay_interaction" (no colon; see TREATMENT_COL below), exactly as A07 already
renamed the bare card expression "exp(-n_i/5)" to the opaque identifier "early_season_transient".
The underlying arithmetic (kappa multiplies exp_i * exp(-n_i/5), fitted as one column) is
UNCHANGED from the card; only the materialised column NAME differs from the card's prose spelling,
and that choice is recorded here, in p26_k0_record()'s notes, and in REPORT.md for P37 to affirm
or overrule -- nothing frozen pins the literal column-name string, so nothing frozen is silently
overridden. If P37 instead reads "exp_i:exp(-n_i/5)" as the LITERAL required column name, that
is itself in tension with the card's own "no expansion-indexed term" K0 clause and is a genuine
preregistration ambiguity, not an implementation defect this module can resolve unilaterally.

FOLD-LOCAL FALLBACK (frozen, card p26_k0_record.fold_local_fallback / single_active_fold_
licensing_amended): S7_TIER_SUPPORT_v1 instance -- "term enters a fold iff >= 10 training clusters
have exp_i = 1". Because exp(-n_i/5) > 0 for every finite n_i >= 0 (n_i is a non-negative count;
exp(-n_i/5) is strictly positive for all real n_i, in particular for n_i = 0), the materialised
treatment column expansion_decay_interaction is nonzero on EXACTLY the rows where exp_i = 1 --
so the generic P27 ActiveSetRule mechanism (cluster support of the TREATMENT column itself) is a
faithful, unmodified expression of the card's one-sided rule; unlike A03's SHALLOW/DEEP two-sided
rule, no task-specific symmetry wrapper is needed here. Measured at P33/P35 freeze (support_
measured_by_this_node, carried, NOT re-measured by this node): expansion training-cluster counts
by fold are 0/0/0/0/46 -- exactly ONE training fold (train_lt_2026) meets the 10-cluster floor.

SINGLE-ACTIVE-FOLD LICENSING CAVEATS (card, single_active_fold_licensing_amended, F4, carried
verbatim on every use of this arm's result): (a) all 46 expansion training clusters in
train_lt_2026 belong to ONE franchise (team_id 1611661331, 2025 cohort) -- the licensed statement
is about that single-franchise cohort; (b) kappa-hat is CONFOUNDED with that franchise's identity;
(c) effective decayed support is ~9-15 clusters (treatment >= 0.05: 15; >= 0.1: 12; >= 0.2: 9), not
the 46 nominal; (d) any PRELIMINARY_SUPPORTED_SINGLE_FOLD record MUST carry (a)-(c).

KILL CONDITIONS (frozen, card kill_conditions_frozen -- "carried verbatim from P33"):
    (i)  floor-fail (train_lt_2026 fails the >= 10-cluster floor at P27 re-invocation) -> retired
         unevaluated, itself informative under D010;
    (ii) active and the 95% interval for kappa covers 0 -> KILLED;
    (iii)active and the interval excludes 0 -> PRELIMINARY_SUPPORTED_SINGLE_FOLD, promotion-
         ineligible, carried to next cycle, WITH the F4 caveats above;
    (iv) sign instability is UNDEFINED with one fold and is REPLACED by the promotion-
         ineligibility declaration -- there is no sign-flip kill hook for this arm.
"""
from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ frozen pins, restated here so
# this module has no runtime dependency on the runner/ directory or any sibling arms/ directory
# (arms/A14 never imports from or writes to runner/ or arms/A07 etc.; these constants are copied
# VALUES, not references, and are asserted equal to the runner's own copies in TESTS.py so drift
# is caught rather than silently tolerated).
ARM_ID = "A14_expansion_intercept_decay"
OFFSET_COL = "log_exposure"
TARGET_LABEL = "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS"
INTERCEPT_COL = "intercept"

GAP_COL = "pace_gap"
DEPTH_COL = "pace_evidence_depth"
OPP_DEPTH_COL = "opp_pace_evidence_depth"
DECAY_COL = "league_common_decay"                  # exp(-n_i/5), GRANTED TO THE NULL (K0 K5)
TREATMENT_COL = "expansion_decay_interaction"       # kappa * exp_i * exp(-n_i/5); see NAMING
                                                    # DISCLOSURE in the module docstring

TAU = 5.0                                          # FIXED by source; never tunable (P33 pin)
FIRST_SEASON_FLOOR = 2022                          # exp_i's ">= 2022" clause, card-pinned
S7_TIER_FLOOR_CLUSTERS = 10                        # "term enters a fold iff >= 10 training
                                                    # clusters have exp_i = 1" (card, verbatim)
S7_RULE_ID = "S7_TIER_SUPPORT_v1"
P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"

REQUIRED_UNIVERSE_COLS = ("team_id", "season", "game_date", GAP_COL, DEPTH_COL, OPP_DEPTH_COL)
REQUIRED_SCHEDULE_COLS = ("team_id", "season", "game_date")

_HERE = Path(__file__).resolve().parent                    # .../P36_IMPLEMENT_ARMS/arms/A14
_STAGE2B = _HERE.parents[2]                                 # .../stage2b
_FEG_PATH = (_STAGE2B / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD" / "fold_estimability_guard.py")


class A14ConstructionFailure(RuntimeError):
    """Raised when the frozen card's construction cannot be honoured. No design is returned."""


# --------------------------------------------------------------------------------------------- #
# n_i: strictly-earlier same-season CONTRACT-SCHEDULE completed-game count (frozen n_clock_pin,
# "as A07" -- an independently authored copy so this module has no cross-arm runtime dependency).
# --------------------------------------------------------------------------------------------- #

def compute_n_i(contract_schedule: pd.DataFrame, team_id: np.ndarray, season: np.ndarray,
                game_date: np.ndarray) -> np.ndarray:
    """n_i for each row: count of the team's CONTRACT-SCHEDULE same-season games with
    game_date STRICTLY earlier than the row's own game_date. Deterministic, order-independent.
    """
    missing = [c for c in REQUIRED_SCHEDULE_COLS if c not in contract_schedule.columns]
    if missing:
        raise A14ConstructionFailure(
            f"contract_schedule is missing required columns {missing}; n_i (n_clock_pin) cannot "
            f"be computed on the contract-schedule clock")

    sched = contract_schedule[list(REQUIRED_SCHEDULE_COLS)].copy()
    sched["game_date"] = pd.to_datetime(sched["game_date"])
    team_id = np.asarray(team_id)
    season = np.asarray(season)
    gd = pd.to_datetime(pd.Series(np.asarray(game_date)))

    out = np.full(len(team_id), -1.0, dtype=float)
    for (tid, seas), grp in sched.groupby(["team_id", "season"], sort=False):
        dates = np.sort(grp["game_date"].unique())
        mask = (team_id == tid) & (season == seas)
        if not mask.any():
            continue
        out[mask] = np.searchsorted(dates, gd[mask].to_numpy(), side="left").astype(float)

    unresolved = int((out < 0).sum())
    if unresolved:
        raise A14ConstructionFailure(
            f"{unresolved} universe row(s) have a (team_id, season) pair absent from the supplied "
            f"contract_schedule; n_i is undefined for them and the frozen n_clock_pin forbids "
            f"falling back to the universe-row clock")
    return out


def league_common_decay(n_i: np.ndarray) -> np.ndarray:
    """exp(-n_i / tau), tau = 5 FIXED by source. Shared arithmetic with A07's early_season_
    transient (same tau=5 pin); granted to K0 here rather than tested as the treatment."""
    return np.exp(-np.asarray(n_i, dtype=float) / TAU)


# --------------------------------------------------------------------------------------------- #
# exp_i: 1[team's first season in the contract schedule >= 2022 AND equals the row's own season]
# --------------------------------------------------------------------------------------------- #

def compute_first_season(contract_schedule: pd.DataFrame) -> pd.Series:
    """A team's first season on the CONTRACT SCHEDULE -- a pure schedule fact, deterministic and
    order-independent. Indexed by team_id."""
    missing = [c for c in ("team_id", "season") if c not in contract_schedule.columns]
    if missing:
        raise A14ConstructionFailure(f"contract_schedule is missing required columns {missing}; "
                                     f"first-season computation (exp_i) cannot proceed")
    return contract_schedule.groupby("team_id")["season"].min()


def compute_exp_i(contract_schedule: pd.DataFrame, team_id: np.ndarray,
                  season: np.ndarray) -> np.ndarray:
    """exp_i = 1[first_season(team) >= FIRST_SEASON_FLOOR and season == first_season(team)],
    card-pinned verbatim. Fails closed on any team_id absent from the contract schedule."""
    first_season_map = compute_first_season(contract_schedule)
    team_id = np.asarray(team_id)
    season = np.asarray(season)

    unresolved_mask = ~pd.Index(team_id).isin(first_season_map.index)
    if unresolved_mask.any():
        n_unresolved = int(unresolved_mask.sum())
        raise A14ConstructionFailure(
            f"{n_unresolved} universe row(s) carry a team_id absent from the supplied "
            f"contract_schedule; exp_i (first-season identity) is undefined for them and this "
            f"is a pure schedule fact that must never be silently imputed")

    first_season = first_season_map.reindex(team_id).to_numpy()
    exp_i = ((first_season >= FIRST_SEASON_FLOOR) & (season == first_season)).astype(float)
    return exp_i


def expansion_decay_interaction(exp_i: np.ndarray, decay: np.ndarray) -> np.ndarray:
    """The materialised treatment column: exp_i * exp(-n_i/5) (kappa is the FITTED coefficient,
    never baked into the design column). See NAMING DISCLOSURE in the module docstring for why
    this column is named without a colon."""
    return np.asarray(exp_i, dtype=float) * np.asarray(decay, dtype=float)


# --------------------------------------------------------------------------------------------- #
# single-active-fold kill/verdict chain (frozen card kill_conditions_frozen) -- PURE functions of
# synthetic / fold-summary inputs. They decide nothing about real performance; they exist so a
# downstream fitting node can call one deterministic decision function per rule rather than
# re-deriving the card's prose per implementation.
# --------------------------------------------------------------------------------------------- #

F4_CAVEATS = (
    "(a) all 46 expansion training clusters in train_lt_2026 belong to ONE franchise (team_id "
    "1611661331, 2025 cohort) -- the licensed statement is about that single-franchise cohort "
    "only; (b) kappa-hat is CONFOUNDED with that franchise's identity -- 'expansion effect' and "
    "'this one team was fast/slow' are the same parameter in this design; (c) effective decayed "
    "support is ~9-15 clusters (treatment >= 0.05: 15; >= 0.1: 12; >= 0.2: 9), not the 46 "
    "nominal; (d) any PRELIMINARY_SUPPORTED_SINGLE_FOLD record MUST carry (a)-(c).")


def evaluate_single_fold_verdict(*, floor_met: bool,
                                 kappa_interval: tuple[float, float] | None) -> dict:
    """The card's kill_conditions_single_fold_decidable chain, made decidable.

    floor_met: whether train_lt_2026 met the >= 10-training-cluster floor at (re-)invocation.
    kappa_interval: the (lo, hi) 95% training-cluster bootstrap interval for kappa in that one
        active fold, or None if the floor was not met (no fit was attempted).

    Returns exactly one of: RETIRED_UNEVALUATED, KILLED, PRELIMINARY_SUPPORTED_SINGLE_FOLD.
    Sign instability is UNDEFINED with one fold (card, verbatim) and is never evaluated here.
    """
    if not floor_met:
        return {"verdict": "RETIRED_UNEVALUATED",
               "reason": "train_lt_2026 failed the >= 10-training-cluster floor at P27 "
                         "invocation -- itself informative under D010",
               "kappa_interval": None, "f4_caveats": None}
    if kappa_interval is None:
        raise ValueError("floor_met=True requires a kappa_interval (the fold was fit)")
    lo, hi = float(kappa_interval[0]), float(kappa_interval[1])
    if lo > hi:
        raise ValueError(f"malformed interval: ci_low={lo} > ci_high={hi}")
    if lo <= 0.0 <= hi:
        return {"verdict": "KILLED", "reason": "the 95% interval for kappa covers 0",
               "kappa_interval": (lo, hi), "f4_caveats": None}
    return {"verdict": "PRELIMINARY_SUPPORTED_SINGLE_FOLD",
           "reason": "active and the interval excludes 0; promotion-ineligible by structure "
                     "(single-active-fold), carried to next cycle",
           "kappa_interval": (lo, hi), "f4_caveats": F4_CAVEATS}


def evaluate_kill_conditions(*, floor_met: bool,
                             kappa_interval: tuple[float, float] | None) -> dict:
    """OR-combined verdict wrapper matching the shared arms' evaluate_kill_conditions naming
    convention: 'killed' is True only for the RETIRED_UNEVALUATED and KILLED verdicts (both
    remove the arm from any promotion consideration); PRELIMINARY_SUPPORTED_SINGLE_FOLD is NOT a
    kill (the card gives it its own carried-forward disposition, not death)."""
    v = evaluate_single_fold_verdict(floor_met=floor_met, kappa_interval=kappa_interval)
    return {**v, "killed": v["verdict"] in ("RETIRED_UNEVALUATED", "KILLED")}


# --------------------------------------------------------------------------------------------- #
# P27 loader (read-only; mirrors arms/A03's own convention -- never edits the frozen guard)
# --------------------------------------------------------------------------------------------- #

def _load_feg():
    name = "p27_fold_estimability_guard_for_A14"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _FEG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------------------------- #

def _digest(*parts: Any) -> str:
    import hashlib
    import json
    return "sha256:" + hashlib.sha256(
        json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _sidespec(fold_ids: Sequence[str], training_digest: str, evaluation_digest: str) -> dict:
    return {
        "intercept_treatment": "free unpenalised single global intercept, explicit 'intercept' "
                               "column of ones, identical in arm and null (P35 intercept_structure "
                               "table: A14 in ARMS_WITH_FREE_GLOBAL_INTERCEPT)",
        "calibration_freedom": "none -- no post-fit rescaling of any kind",
        "penalty_treatment": "none -- unpenalised quasi-Poisson IRLS",
        "exposure_offset": f"{OFFSET_COL} = log(projected_team_off_possessions), frozen incumbent "
                           "D_ewma_shrunk (K=200, alpha=0.1), never retuned",
        "training_rows": training_digest,
        "evaluation_rows": evaluation_digest,
        "chronological_folds": list(fold_ids),
        "clipping": "none",
        "link_function": "log",
        "preprocessing": (f"{GAP_COL}/{DEPTH_COL}/{OPP_DEPTH_COL} carried unchanged from the "
                         "receipted incumbent-path feature frame (possession_features."
                         f"challenger_input); {DECAY_COL} = exp(-n_i/5) and {TREATMENT_COL} = "
                         f"exp_i * exp(-n_i/5) both computed from n_i on the contract-schedule "
                         "clock (n_clock_pin) and exp_i on the contract-schedule first-season "
                         "identity; tau=5 fixed by source"),
        "missing_value_handling": "none -- complete-case receipted frame; n_i/exp_i construction "
                                  "fails closed (A14ConstructionFailure) rather than imputing on "
                                  "any (team_id, season) absent from the contract schedule",
        "companion_components": "none",
        "fallback_rules": f"{S7_RULE_ID}: term enters a fold iff >= {S7_TIER_FLOOR_CLUSTERS} "
                          "training clusters have exp_i = 1 (card, verbatim); measured pre-fit "
                          "training-cluster counts by fold 0/0/0/0/46 -- exactly ONE active fold "
                          "(train_lt_2026); P33 measurement, carried, NOT re-measured by this "
                          "node: no real fold is touched",
        "aggregation": "none -- the unit of prediction is the team-game",
        "candidate_universe": "the 2,982-row resolved possession universe (1,491 game clusters); "
                              "n_i and exp_i alone are computed on the 2,990-row contract "
                              "schedule superset",
        "post_processing": "none",
        "prediction_universe": "same as candidate_universe",
    }


# --------------------------------------------------------------------------------------------- #
# the arm module
# --------------------------------------------------------------------------------------------- #

class A14ExpansionInterceptDecay:
    """P36 RUNNER_INTERFACE-conformant module for A14_expansion_intercept_decay.

    Constructed with the CONTRACT SCHEDULE (superset of ``universe``, carrying the four
    universe-excluded 2021 rows the n_clock_pin requires and the full team/season history exp_i's
    first-season computation needs) plus the fold-id list and row count the caller will present to
    ``p26_k0_record`` (mirrors arms/A07's convention).
    """

    arm_id = ARM_ID

    def __init__(self, contract_schedule: pd.DataFrame, fold_ids: Sequence[str] = (),
                n_rows: int | None = None):
        missing = [c for c in REQUIRED_SCHEDULE_COLS if c not in contract_schedule.columns]
        if missing:
            raise A14ConstructionFailure(f"contract_schedule missing required columns {missing}")
        self._contract_schedule = contract_schedule.reset_index(drop=True)
        self._fold_ids = [str(f) for f in fold_ids]
        self._n_rows = int(n_rows) if n_rows is not None else int(len(contract_schedule))

    # ---- metadata hooks -------------------------------------------------------------
    def card_id(self) -> str:
        return self.arm_id

    def declared_family(self) -> str:
        return "SUBSTANTIVE"

    def recalibration_declaration(self) -> str:
        return "NOT_APPLICABLE"

    def enumeration_element(self) -> dict:
        return {}                      # A14 has no enumerated grid; one module = the whole arm

    def element_id(self) -> str:
        return "A14_expansion_intercept_decay__single"

    def uses_global_intercept(self) -> bool:
        return True                    # P35 intercept_structure: A14 in ARMS_WITH_FREE_GLOBAL_...

    # ---- design ---------------------------------------------------------------------
    def build_design(self, fold: dict, universe: pd.DataFrame) -> dict:
        missing = [c for c in REQUIRED_UNIVERSE_COLS if c not in universe.columns]
        if missing:
            raise A14ConstructionFailure(
                f"universe is missing required columns {missing} (receipted incumbent-path "
                f"gap/depth/opp_depth columns, or team_id/season/game_date identity columns)")

        n_i = compute_n_i(self._contract_schedule,
                          universe["team_id"].to_numpy(),
                          universe["season"].to_numpy(),
                          universe["game_date"].to_numpy())
        decay = league_common_decay(n_i)
        exp_i = compute_exp_i(self._contract_schedule,
                              universe["team_id"].to_numpy(),
                              universe["season"].to_numpy())
        interaction = expansion_decay_interaction(exp_i, decay)

        columns = {
            GAP_COL: universe[GAP_COL].to_numpy(dtype=float),
            DEPTH_COL: universe[DEPTH_COL].to_numpy(dtype=float),
            OPP_DEPTH_COL: universe[OPP_DEPTH_COL].to_numpy(dtype=float),
            DECAY_COL: decay,
            INTERCEPT_COL: np.ones(len(universe), dtype=float),
            TREATMENT_COL: interaction,
        }
        nuisance = [GAP_COL, DEPTH_COL, OPP_DEPTH_COL, DECAY_COL, INTERCEPT_COL]
        return {
            "treatment_cols": [TREATMENT_COL],
            "nuisance_cols": nuisance,
            "k0_matched_design": {"treatment_cols": [], "nuisance_cols": list(nuisance),
                                  "comparison": "term_removal"},
            "indicator_cols": [],       # gap/depth/opp_depth/decay/interaction are continuous
                                       # (interaction is 0 or a positive decay value, never a
                                       # strict 0/1 indicator); intercept is structural, never
                                       # listed as an indicator
            "columns": columns,
            "diagnostics": {           # not a declared design column; carried for tests/receipts
                "n_i": n_i, "exp_i": exp_i,
                "fold_id": str(fold.get("fold_id")),
                "n_expansion_rows": int(exp_i.sum()),
            },
        }

    # ---- P26 --------------------------------------------------------------------------
    def p26_k0_record(self) -> dict:
        train_digest = _digest("A14_training_rows", self._fold_ids, self._n_rows)
        eval_digest = _digest("A14_evaluation_rows", self._fold_ids, self._n_rows)
        side = _sidespec(self._fold_ids, train_digest, eval_digest)
        structural = [GAP_COL, DEPTH_COL, OPP_DEPTH_COL, DECAY_COL, INTERCEPT_COL]
        return {
            "schema": "k0_matched/1",
            "arm_id": self.arm_id,
            "arm_kind": "substantive_feature",
            "treatment_mechanism": {
                "statement": "a first-season expansion franchise deviates from the league-average "
                            "early-season decay level with its own decaying level term, beyond "
                            "the generic early-season drift the null already owns",
                "treatment_terms": [TREATMENT_COL],
                "tested_parameters": [{"name": "kappa", "role": "coefficient", "null_value": 0,
                                       "null_value_meaning": "expansion teams are league-average "
                                                             "after generic drift"}],
                "claimed_signal_axes": ["team_identity", "season_time"],
                "null_construction": {
                    "method": "term_removal",
                    "destroys_claimed_signal": (
                        f"removing {TREATMENT_COL} leaves only {GAP_COL}/{DEPTH_COL}/"
                        f"{OPP_DEPTH_COL}/{DECAY_COL}/intercept in the null; none of those five "
                        "distinguish an expansion franchise's first season from any other "
                        "team's, so the null cannot express any expansion-specific decay and the "
                        "claimed team_identity/season_time signal is destroyed by "
                        "construction")}},
            "invariants": {
                "rows": train_digest,
                "target": TARGET_LABEL,
                "folds": list(self._fold_ids),
                "weights": "equal per team-game row",
                "offset": side["exposure_offset"],
                "fallback_machinery": side["fallback_rules"],
                "nuisance_terms": list(structural),
                "lower_order_structural_terms": list(structural),
            },
            "arm_spec": {
                "name": "A14_expansion_intercept_decay", "role": "challenger",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [TREATMENT_COL],
                "structural_terms": list(structural),
                "declaration_routing": {
                    TREATMENT_COL: "substantive_features",
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", DECAY_COL: "preprocessing",
                    INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": side},
            "k0_spec": {
                "name": "A14_expansion_intercept_decay__K0_MATCHED", "role": "k0",
                "pipeline_id": "p36_shared_runner/1",
                "substantive_features": [],
                "structural_terms": list(structural),
                "declaration_routing": {
                    GAP_COL: "preprocessing", DEPTH_COL: "preprocessing",
                    OPP_DEPTH_COL: "preprocessing", DECAY_COL: "preprocessing",
                    INTERCEPT_COL: "intercept_treatment"},
                "comparison_gate_sidespec": dict(side)},
            "fold_local_fallback": {
                "required": True,
                "trigger": f"{S7_RULE_ID}: fewer than {S7_TIER_FLOOR_CLUSTERS} training clusters "
                          f"with exp_i = 1 in a fold (card, verbatim); measured pre-fit training "
                          "cluster counts by fold 0/0/0/0/46 -- P33 measurement, carried, NOT "
                          "re-measured by this node",
                "numeric_threshold": S7_TIER_FLOOR_CLUSTERS,
                "action": "refuse_to_score_fold",
                "registered_before_results": True},
            "verdict_label_policy": "substantive_feature arm: eligible ONLY for a fold-local "
                                    "diagnostic statement about the single active fold (D021) -- "
                                    "PROMOTION-INELIGIBLE THIS CYCLE BY STRUCTURE (card, "
                                    "verbatim); K0_FLAT carries no promotion value whatsoever "
                                    "(k0_flat_role diagnostic_only)",
            "k0_flat_role": "diagnostic_only",
            "registered_before_results": True,
            "notes": [
                "K0 K5 (P35 amendment): the null's terms are 'receipted incumbent-path features "
                "plus generic early-season drift GRANTED TO THE NULL' (S6 direction 1); "
                "'no expansion-indexed term' (S6 direction 2) -- MAE(K0[A14]) is NOT an incumbent "
                "benchmark and this arm may not claim the null 'recovers the incumbent'.",
                "K0 K6 / n_clock_pin: n_i is counted on the CONTRACT SCHEDULE (2,990 rows, "
                "including the four universe-excluded 2021 opening-day games); the universe-row "
                "clock is barred. exp_i's first-season identity is likewise a contract-schedule "
                "fact.",
                "NAMING DISCLOSURE (see module docstring): the materialised treatment column is "
                f"named '{TREATMENT_COL}' (no colon) rather than the card's literal prose "
                "spelling 'exp_i:exp(-n_i/5)', to avoid a P26 R6 false-positive against the "
                "card's own explicit 'no expansion-indexed term' K0 clause -- neither side of "
                "this design ever carries a standalone exp_i main effect, so there is no "
                "main-effect-credit asymmetry for R6 to guard against here. Disclosed, not "
                "silently resolved; flagged for P37.",
                "MULT: A14 is the COLDSTART_FALLBACK family's FIXED SLOT (charged to m=5, "
                "EXCLUDED from the Holm step-down ordering, p := 1, always last, never blocks) -- "
                "out of scope for this feature-construction module; enforced at the runner's "
                "Holm-ordering call site, not here.",
                "SINGLE-ACTIVE-FOLD LICENSING (D021, card verbatim): a result licenses ONLY a "
                "fold-local diagnostic statement about the 2026 test season. It licenses NO "
                "cross-fold stability claim, NO promotion, and NO cold-start generalization "
                "(D010). Any PRELIMINARY_SUPPORTED_SINGLE_FOLD verdict MUST carry the F4 caveats "
                "(see evaluate_single_fold_verdict / F4_CAVEATS in this module).",
            ],
        }

    # ---- guards ---------------------------------------------------------------------
    def lag_specs(self) -> dict:
        return {
            GAP_COL: {"column": GAP_COL, "kind": "DERIVED_NO_JOIN",
                      "source_artifact_id": "team_possession_prior/1",
                      "entity_keys": ("game_id", "team_id"),
                      "rationale": "difference of two prior-games-only trailing-window pace "
                                   "means (team_pace_estimate - opp_pace_estimate)"},
            DEPTH_COL: {"column": DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                       "source_artifact_id": "team_possession_prior/1",
                       "entity_keys": ("game_id", "team_id"),
                       "rationale": "count of prior games backing the team's own pace estimate, "
                                    "capped at WINDOW_K=10"},
            OPP_DEPTH_COL: {"column": OPP_DEPTH_COL, "kind": "DERIVED_NO_JOIN",
                           "source_artifact_id": "team_possession_prior/1",
                           "entity_keys": ("game_id", "team_id"),
                           "rationale": "same evidence-depth count, for the opponent"},
            DECAY_COL: {"column": DECAY_COL, "kind": "SCHEDULE",
                       "source_artifact_id": "team_possession_prior/1",
                       "entity_keys": ("team_id", "season"), "order_column": "game_date",
                       "rationale": ("exp(-n_i/5); n_i is a pure schedule fact (team_id, season, "
                                    "game_date and completedness only), fixed before tipoff, "
                                    "with no dependency on any realised in-game quantity. "
                                    "Declared SCHEDULE for the same reason A07's identical "
                                    "arithmetic is declared SCHEDULE (disclosed there and "
                                    "carried here, not re-argued)")},
            TREATMENT_COL: {"column": TREATMENT_COL, "kind": "SCHEDULE",
                            "source_artifact_id": "team_possession_prior/1",
                            "entity_keys": ("team_id", "season"), "order_column": "game_date",
                            "rationale": ("exp_i * exp(-n_i/5); exp_i is a pure schedule fact "
                                         "(the team's first season on the contract schedule, and "
                                         "whether the row's own season equals it), and n_i is the "
                                         "same schedule-fact count as above -- the product carries "
                                         "no dependency on any realised in-game quantity of the "
                                         "target game or any other game")},
            # INTERCEPT_COL carries no lag_spec: it is a structural constant, not a declared
            # feature (mirrors arms/A07's convention).
        }

    def lag_sources(self) -> dict:
        return {"contract_schedule": self._contract_schedule}

    def preregistered_contrasts(self):
        return None            # A14 registers no P25 contrast column (that is A02's obligation)

    def prereg_digest_expected(self):
        return None

    def requires_franchise_continuity(self) -> bool:
        # P33 shared_arm_invariants.p23_franchise_continuity_precondition names A14 explicitly
        # (A08, A09, A10, A11, A12, A13, A14, A16, A17, A19, A21, A22, A24); the measured note on
        # that same clause states no rebrand resolution can flip A14's expansion set (carried,
        # not re-measured here).
        return True

    def p23_receipts(self) -> list:
        return [{"team_cities_sha256": TEAM_CITIES_SHA256_PIN,
                 "note": "A14 requires the franchise-continuity receipt per P33 precondition / "
                         "P35 shared_frozen_amendments.franchise_continuity_receipt_pin; the same "
                         "clause's measured note (carried, not re-measured here) records that no "
                         "rebrand resolution can flip A14's expansion set"}]

    def p27_rule(self):
        """The generic P27 mechanism, fed honestly and completely: because exp(-n_i/5) > 0 for
        every finite n_i, the materialised treatment column's cluster support IS exactly the
        exp_i=1 cluster support the card's rule names -- no task-specific symmetry wrapper is
        needed (contrast arms/A03, whose two-sided rule the generic mechanism cannot fully see)."""
        feg = _load_feg()
        rule = feg.ActiveSetRule(
            rule_id=S7_RULE_ID,
            min_nonzero_clusters=S7_TIER_FLOOR_CLUSTERS,
            min_std=0.0,
            rationale=("P33/P35 A14 fallback: term enters a fold iff >= 10 training clusters "
                       "have exp_i = 1 (card, verbatim; single_active_fold_licensing_amended / "
                       "FOLDS F6: S7_TIER_SUPPORT_v1 registered via registry append). Because "
                       f"{DECAY_COL} > 0 for every finite n_i, cluster support of "
                       f"{TREATMENT_COL} equals cluster support of exp_i = 1 exactly, so this "
                       "single ActiveSetRule instance, fed the treatment column, is a complete "
                       "expression of the card's one-sided rule."))
        rule_kwargs = {"rule_id": rule.rule_id,
                       "min_nonzero_clusters": rule.min_nonzero_clusters,
                       "min_std": rule.min_std, "rationale": rule.rationale}
        prereg_kwargs = {
            "registered_at_utc": ("P35_FREEZE_TASK_CARDS freeze (2026, exact UTC not carried in "
                                  "the frozen SPEC.json bytes -- recorded honestly as an "
                                  "unestablished precision, not fabricated)"),
            "registered_by": ("P35_FREEZE_TASK_CARDS, A14 card, amendments_applied[2] "
                              "('FOLDS F6: S7_TIER_SUPPORT_v1 registered via registry append')"),
            "rule_spec_sha256": rule.spec_sha256,
            "results_visible_at_registration": False,
            "record_path": ("experiments/player_program/stage2b/P35_FREEZE_TASK_CARDS/"
                            f"SPEC.json (sha256 {P35_SPEC_SHA256}) #task_cards"
                            "[arm_id=A14_expansion_intercept_decay]"),
        }
        return (rule_kwargs, prereg_kwargs)


# ---------------------------------------------------------------------------------------------
# TEAM_CITIES pin, restated (value copy, not a runner/ import) -- see class docstring/p23_receipts
# ---------------------------------------------------------------------------------------------
TEAM_CITIES_SHA256_PIN = "10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d"
