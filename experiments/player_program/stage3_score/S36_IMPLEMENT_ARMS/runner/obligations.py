#!/usr/bin/env python3
"""obligations.py -- the S35 downstream obligations, as executable objects rather than prose.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

WHY THIS FILE EXISTS. The program's own recorded lesson is that "an obligation that lives only in
a report is an obligation that gets lost" -- S34's Severity C notes existed only in a reviewer's
returned text and were nearly lost. So each obligation below is:

  * carried VERBATIM as a module constant (the bytes travel, not a paraphrase);
  * attached to a MECHANISM that refuses to emit the thing it governs without it.

The verbatim strings are transcribed from
  experiments/player_program/stage3_score/S35_FREEZE_TASK_CARDS/SPEC.json .downstream_obligations
and `verify_obligation_text()` re-reads that frozen file and fails closed on any drift, so a typo
here cannot silently weaken an obligation.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from runner_constants import FREEZE_SPEC_PATH, artifact_path

# ============================================================================================
# O1 / ROOT_PATH_RULE -- discharged in universe.py (load_master_team) and runner_constants.
# ============================================================================================
O1_MASTER_TEAM_PIN = (
    "S36 MUST read data/masters/master_team.parquet from the PROGRAM WORKTREE and verify its "
    "sha256 equals the pin below BEFORE building anything. It must NEVER read the live "
    "data-worktree / main-working-tree copy, which legitimately keeps growing as the season is "
    "captured.")
O1_ON_MISMATCH = ("HALT. Do not build. Report to the coordinator. A silent rebuild on drifted "
                  "bytes voids the preregistration.")

# ============================================================================================
# O2 / C4_s36_prebuild_game_id_digest -- THIS NODE'S OWN MANDATORY OBLIGATION.
# Discharged in prebuild/PREBUILD_GAME_ID_DIGEST.py, which runs BEFORE any design matrix exists
# and whose receipt universe.build_universe() refuses to proceed without.
# ============================================================================================
O2_PREBUILD_DIGEST = (
    "before any design matrix is constructed, S36 MUST emit a pre-build digest of the game_id set "
    "of the 1,491-cluster universe and pin it into its own receipt, converting invariants.rows - "
    "deferred to S36 on all 17 records - from a deferred invariant into a receipted one BEFORE "
    "any fit runs.")
O2_DIGEST_RULE = (
    "sha256 over the U+001F-joined canonicalised game_id values, sorted lexicographically on "
    "str(game_id) ascending, UTF-8 (the S32B column-digest canonicalisation, so the number is "
    "comparable to every other pin in this program)")
O2_ON_MISMATCH = "HALT before fitting."

# ============================================================================================
# C1 / program alpha disclosure -- discharged by stamping BOTH bounds on every receipt.
# ============================================================================================
C1_PROGRAM_ALPHA = {
    "GOVERNING_BOUND": 0.40,
    "governing_basis": ("8 primary families x 0.05, the intersection rule (a disputed element "
                        "must survive Holm under EVERY registered partition, so the realized "
                        "decision rule is the INTERSECTION and the governing additive bound is "
                        "min(0.40, 0.50) = 0.40)"),
    "DISCLOSED_BOUND": 0.50,
    "disclosed_basis": "10 maximal-partition families x 0.05",
    "both_are_stated": True,
    "which_governs": "0.40 GOVERNS",
    "no_program_wide_FWER_claim": True,
    "what_the_bound_is_not": ("an additive expectation bound on program-wide false positives, "
                             "NOT an FWER guarantee. No claim of program-wide family-wise error "
                             "control is made anywhere in this cycle."),
}

# ============================================================================================
# C2 / SC06 era-kill power statement -- MANDATORY, prints adjacent to any verdict the kill produces.
# ============================================================================================
C2_POWER_STATEMENT = (
    "POWER STATEMENT (MANDATORY, prints adjacent to any verdict this kill produces): SC06's "
    "era-instability kill is essentially UNPOWERED. Its pre-2024 support is 17 pooled-TEST "
    "clusters (8 in 2022 + 9 in 2023) of the 77 test-fold clusters at |F_H - F_A| >= 1 (78 pooled "
    "including the 2021 training season; rest components only, tz component added at sealed-run "
    "receipt time). CONSEQUENCE: a kill that does NOT fire is NOT evidence that the fatigue-by-era "
    "interaction is stable; it is evidence that this slate cannot tell. Any report of the "
    "era-split table that omits this statement is a reporting defect.")
C2_APPLIES_TO_KILL = "era_instability"
C2_APPLIES_TO_ELEMENTS = ("SC06_SCHED_FATIGUE_DIFF::E2_FINAL_MARGIN_HOME",
                          "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB")
C2_KILL_NOT_WEAKENED = ("the kill stays exactly as carded and stays arm-killing. Only the reading "
                        "of a NON-firing kill is constrained.")

# ============================================================================================
# C3 / SC11 E2 cross-estimand receipt label -- travels WITH the number, everywhere.
# ============================================================================================
C3_LABEL = "NON_CITABLE_INTEGRITY_DIAGNOSTIC"
C3_APPLIES_TO = "SC11_LEAGUE_TOTAL_DRIFT::E1_GAME_TOTAL"
C3_BINDING_RULE = (
    "the |Delta-MAE(E2)| number produced by this receipt is computed on an estimand SC11 is NOT "
    "registered for and that sits in NO family. It MUST be emitted carrying the literal label "
    "'NON_CITABLE_INTEGRITY_DIAGNOSTIC', it may NEVER be quoted as a performance result, it enters "
    "no Holm family, no pass tally and no multi-survivor comparison, and it may be used for "
    "exactly one thing: firing or not firing SC11's card-pinned implementation-integrity kill at "
    "|Delta-MAE(E2)| > 0.10 MAE points.")
C3_KILL_THRESHOLD_MAE_POINTS = 0.10

# ============================================================================================
# reporting_rule -- the two labels travel with their numbers.
# ============================================================================================
REPORTING_RULE = (
    "the C2 power statement prints adjacent to any verdict SC06's era kill produces, and the C3 "
    "label travels with the number wherever it is emitted, copied or cited.")

# ============================================================================================
# O5 / R_SC08_FLOOR, O6 / R-A1-EXCEPTIONS, O7 / identity-set extension reviewability
# ============================================================================================
O5_RECEIPT_ID = "R_SC08_FLOOR"
O5_GATING_ON = "SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB"
O5_NON_GATING_AGREEMENT_ON = ("SC01_OPP_ADJ_INTERACTING::E3_HOME_WIN_PROB",
                              "SC06_SCHED_FATIGUE_DIFF::E3_HOME_WIN_PROB")
O5_ABSENCE_IS_A_CARD_DEFECT = True
O5_BELOW_FLOOR_LABEL = "FEATURE VALUE OVER OWN NULL ONLY - BELOW-FLOOR NULL"

O6_RECEIPT_ID = "R-A1-EXCEPTIONS"
O6_RULE = (
    "the enumerated exception set (10 release-order displaced + 6 clusters without a "
    "second-endpoint witness) is a mandatory non-gating sensitivity receipt on every element, and "
    "on SC06 it additionally carries an arm-killing A1-SENSITIVITY kill. master_team.game_date is "
    "frozen at CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS - never at unconditional CUTOFF_VALID.")
O6_CUTOFF_STATUS = "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS"

O7_RULE = (
    "the current-game-deletion invariance receipt runs at COLUMN grain, retaining the S30 "
    "section-1 base closed set PLUS the six adjudicated extension columns and nulling every other "
    "column of every consumed source on the current game's rows. If a later reviewer rejects any "
    "extension member, the affected element set is mechanically readable from the "
    "current_game_row_consumed flags.")
O7_BASE_CLOSED_SET = ("game_id", "season", "season_type", "game_date", "team_id", "opp_team_id",
                      "is_home")
O7_EXTENSION_COLUMNS = ("pred_home", "pred_away", "pred_total", "pred_margin", "p_home",
                        "projected_team_off_possessions")

# ============================================================================================
# Enforcement mechanisms
# ============================================================================================


class ObligationViolation(RuntimeError):
    """Raised when a receipt would be emitted without the label/statement its obligation binds."""


def stamp_program_alpha(receipt: dict) -> dict:
    """C1. Every receipt this node emits carries BOTH bounds and names which one governs."""
    receipt["program_alpha_disclosure"] = dict(C1_PROGRAM_ALPHA)
    return receipt


def stamp_sc06_power_statement(receipt: Mapping[str, Any], element_id: str) -> dict:
    """C2 + reporting_rule. Any object carrying an SC06 era-kill verdict slot must carry the
    power statement in the SAME object. Refuses to return an era-kill carrier without it."""
    out = dict(receipt)
    if element_id not in C2_APPLIES_TO_ELEMENTS:
        raise ObligationViolation(
            f"C2 power statement stamped on {element_id}, which the obligation does not bind")
    out["era_kill_power_statement"] = C2_POWER_STATEMENT
    out["era_kill_power_statement_is_mandatory"] = True
    out["era_kill_not_weakened"] = C2_KILL_NOT_WEAKENED
    return out


def assert_sc06_era_verdict_carries_power_statement(obj: Mapping[str, Any]) -> None:
    """C2, checked at emission. An era-split table or era-kill verdict without the statement is a
    reporting defect by the obligation's own words -- so it is refused, not warned about."""
    keys = set(obj)
    carries_verdict = bool(keys & {"era_kill_verdict", "era_split_table", "era_kill_fired"})
    if carries_verdict and obj.get("era_kill_power_statement") != C2_POWER_STATEMENT:
        raise ObligationViolation(
            "C2: an SC06 era-kill verdict / era-split table was emitted without the verbatim "
            "power statement. The obligation calls this a reporting defect.")


def label_sc11_cross_estimand(receipt: Mapping[str, Any]) -> dict:
    """C3. The label is attached to the CARRIER of the number, and the number's key is renamed so
    that no caller can copy `delta_mae` out of it by habit."""
    out = dict(receipt)
    out["label"] = C3_LABEL
    out["binding_rule"] = C3_BINDING_RULE
    out["citable"] = False
    out["enters_family"] = None
    out["enters_pass_tally"] = False
    out["may_be_used_only_for"] = ("firing or not firing SC11's card-pinned "
                                   "implementation-integrity kill at |Delta-MAE(E2)| > 0.10 "
                                   "MAE points")
    out["kill_threshold_mae_points"] = C3_KILL_THRESHOLD_MAE_POINTS
    return out


def assert_sc11_cross_estimand_labelled(obj: Mapping[str, Any]) -> None:
    """C3, checked at emission and re-checkable at every citation."""
    if obj.get("label") != C3_LABEL:
        raise ObligationViolation(
            "C3: the SC11 cross-estimand |Delta-MAE(E2)| receipt was emitted without the literal "
            "label NON_CITABLE_INTEGRITY_DIAGNOSTIC. The label travels with the number.")


def verify_obligation_text() -> dict:
    """Re-read the FROZEN S35 SPEC.json and confirm every verbatim string above still matches the
    bytes. A transcription typo in this file cannot silently weaken an obligation."""
    spec = json.loads(artifact_path(FREEZE_SPEC_PATH).read_text(encoding="utf-8"))
    d = spec["downstream_obligations"]
    checks = {
        "O1_obligation": d["O1_S36_MASTER_TEAM_PIN"]["obligation"] == O1_MASTER_TEAM_PIN,
        "O1_on_mismatch": d["O1_S36_MASTER_TEAM_PIN"]["on_mismatch"] == O1_ON_MISMATCH,
        "O2_obligation": d["O2_S36_GAME_ID_PREBUILD_DIGEST"]["obligation"] == O2_PREBUILD_DIGEST,
        "O2_digest_rule": d["O2_S36_GAME_ID_PREBUILD_DIGEST"]["digest_rule"] == O2_DIGEST_RULE,
        "O2_on_mismatch": d["O2_S36_GAME_ID_PREBUILD_DIGEST"]["on_mismatch"] == O2_ON_MISMATCH,
        "C2_power_statement": (d["O3_SC06_ERA_KILL_POWER_STATEMENT"]["mandatory_text"]
                               == C2_POWER_STATEMENT),
        "C2_applies_to_elements": (tuple(d["O3_SC06_ERA_KILL_POWER_STATEMENT"]
                                         ["applies_to_elements"]) == C2_APPLIES_TO_ELEMENTS),
        "C2_kill_not_weakened": (d["O3_SC06_ERA_KILL_POWER_STATEMENT"]["the_kill_is_not_weakened"]
                                 == C2_KILL_NOT_WEAKENED),
        "C3_label": d["O4_SC11_E2_RECEIPT_NON_CITABLE"]["label"] == C3_LABEL,
        "C3_binding_rule": d["O4_SC11_E2_RECEIPT_NON_CITABLE"]["binding_rule"] == C3_BINDING_RULE,
        "C3_applies_to": d["O4_SC11_E2_RECEIPT_NON_CITABLE"]["applies_to"].startswith(C3_APPLIES_TO),
        "O5_receipt_id": d["O5_R_SC08_FLOOR"]["receipt_id"] == O5_RECEIPT_ID,
        "O5_gating_on": d["O5_R_SC08_FLOOR"]["gating_on"] == O5_GATING_ON,
        "O6_receipt_id": d["O6_R_A1_EXCEPTIONS"]["receipt_id"] == O6_RECEIPT_ID,
        "O6_rule": d["O6_R_A1_EXCEPTIONS"]["rule"] == O6_RULE,
        "O7_rule": d["O7_IDENTITY_SET_EXTENSION_IS_REVIEWABLE"]["rule"] == O7_RULE,
        "O7_extension_columns": (tuple(d["O7_IDENTITY_SET_EXTENSION_IS_REVIEWABLE"]
                                       ["six_extension_columns_verified_at_this_node"])
                                 == O7_EXTENSION_COLUMNS),
        "C1_governing": spec["program_alpha_declaration"]["GOVERNING_BOUND"] == 0.40,
        "C1_disclosed": spec["program_alpha_declaration"]["DISCLOSED_BOUND"] == 0.50,
        "C1_no_fwer": spec["program_alpha_declaration"]["no_program_wide_FWER_claim"] is True,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise ObligationViolation(
            f"obligation text drifted from the frozen S35 bytes: {failed}. The BYTES GOVERN.")
    return {"schema": "s36_obligation_text_check/1", "checks": checks, "all_pass": True,
            "source": FREEZE_SPEC_PATH}
