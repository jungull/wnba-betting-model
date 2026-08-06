#!/usr/bin/env python3
"""guard_harness.py -- the P22/P23/P25/P26/P27 invocation harness at the P36 call site.

Standing rule 3: enforcement belongs at the CALL SITE. This module edits no shared gate; it
imports the FROZEN guard modules by file path, verifies their bytes against the pins measured
into runner_constants.py, and invokes them with the frozen argument pins:

  * P26 validate_k0_matched runs at fit initialisation, per arm, BEFORE the P25 invocation
    (P35 p26_k0_contract_enforcement.call_site), with the R8 slope rule applied under the P35
    r8_scope_adjudication (raw findings AND the adjudicated disposition both recorded).
  * P25 offset_dependency_guard is invoked with offset = log_exposure AND incumbent_projection =
    projected_team_off_possessions, declared_family = SUBSTANTIVE, recalibration NOT_APPLICABLE
    (P35 p25_guard_invocation_pins).
  * P22 postgame_surrogate_guard runs on the complete design with a prohibited basis; absence of
    a basis or of a column's LagSpec is a failure, never a pass.
  * P23 is a construction-time guard (guarded_merge); at the runner call site the harness pins
    its bytes, pins team_cities.csv, and fails closed when a card requires a franchise-continuity
    receipt the arm module did not supply or whose team_cities pin mismatches
    (P35 franchise_continuity_receipt_pin).
  * P27 fold_estimability_guard runs once per arm on the final assembled frame (it audits every
    season-block training fold internally plus the final design).

Every wrapper fails CLOSED: a blocking finding raises GuardHarnessFailure carrying the guard's
own machine-readable record.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

from runner_constants import (DECLARED_FAMILY_ALL_FITTED_ARMS, GUARD_SHA256_PINS,
                              INCUMBENT_PROJECTION_COL, OFFSET_COL,
                              TEAM_CITIES_SHA256_PIN)

_RUNNER = Path(__file__).resolve().parent
PROGRAM = _RUNNER.parents[2]                      # experiments/player_program
ROOT = _RUNNER.parents[4]                         # repository root
STAGE2B = PROGRAM / "stage2b"

GUARD_PATHS = {
    "P22_postgame_surrogate_guard": STAGE2B / "P22_POSTGAME_SURROGATE_GUARD" / "postgame_surrogate_guard.py",
    "P23_merge_guard": STAGE2B / "P23_DIMENSION_CARDINALITY_GUARD" / "merge_guard.py",
    "P25_offset_dependency_guard": STAGE2B / "P25_OFFSET_DEPENDENCY_GUARD" / "offset_dependency_guard.py",
    "P26_validate_k0_matched": STAGE2B / "P26_ARM_SPECIFIC_K0_CONTRACT" / "validate_k0_matched.py",
    "P27_fold_estimability_guard": STAGE2B / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD" / "fold_estimability_guard.py",
}
TEAM_CITIES_PATH = ROOT / "data" / "reference" / "team_cities.csv"


class GuardHarnessFailure(RuntimeError):
    """Fail closed. Carries the guard record on .record."""

    def __init__(self, msg: str, record=None):
        self.record = record
        super().__init__(msg)


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_guard_pins() -> dict:
    """Re-hash every frozen guard plus team_cities.csv against the pins. Fail closed on drift."""
    measured, mismatches = {}, []
    for name, path in GUARD_PATHS.items():
        got = _sha256_file(path) if path.exists() else None
        measured[name] = {"path": str(path.relative_to(ROOT)), "sha256": got,
                          "pinned": GUARD_SHA256_PINS[name],
                          "match": got == GUARD_SHA256_PINS[name]}
        if got != GUARD_SHA256_PINS[name]:
            mismatches.append(name)
    tc = _sha256_file(TEAM_CITIES_PATH) if TEAM_CITIES_PATH.exists() else None
    measured["team_cities.csv"] = {"path": str(TEAM_CITIES_PATH.relative_to(ROOT)),
                                   "sha256": tc, "pinned": TEAM_CITIES_SHA256_PIN,
                                   "match": tc == TEAM_CITIES_SHA256_PIN}
    if tc != TEAM_CITIES_SHA256_PIN:
        mismatches.append("team_cities.csv")
    rec = {"schema": "p36_guard_pins/1", "measured": measured, "mismatches": mismatches,
           "all_match": not mismatches}
    if mismatches:
        raise GuardHarnessFailure(f"guard byte-pin mismatch: {mismatches}", rec)
    return rec


_MODULE_CACHE: dict = {}


def _load(name: str):
    """Import a frozen guard module by file path (guard directories are not packages)."""
    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]
    path = GUARD_PATHS[name]
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(path.stem, mod)
    spec.loader.exec_module(mod)
    _MODULE_CACHE[name] = mod
    return mod


# --------------------------------------------------------------------------------------- P26
_R8_SLOPE_FINDING_KINDS = ("tested_parameter_missing", "null_value_not_null",
                           "lower_order_term_missing_from_k0")


def p26_check(record: dict, *, bind: bool = False) -> dict:
    """validate_k0_matched.validate at fit initialisation, BEFORE P25.

    R8 adjudication (P35 p26_k0_contract_enforcement.r8_scope_adjudication, frozen): R8's slope
    rule is scoped to SLOPE-recalibration arms, all withdrawn. For a calibration_only arm the
    validator's R8-branch findings are re-adjudicated to the extended rule: the record must
    declare >= 1 tested parameter whose null value recovers the incumbent exactly (null_value
    0, term absent = incumbent, zero-parameter null IS the incumbent under the frozen intercept
    table). Findings from OTHER rules are never filtered. Raw and adjudicated findings are both
    returned; the shared validator is not edited.
    """
    vk = _load("P26_validate_k0_matched")
    raw = vk.validate(record)
    kind = record.get("arm_kind")
    adjudicated = list(raw["blocking"])
    r8_filtered = []
    if kind == "calibration_only":
        keep = []
        empty_lower = list(record.get("invariants", {})
                           .get("lower_order_structural_terms") or []) == []
        for f in adjudicated:
            fk = f.get("kind")
            is_r8 = (
                (fk == "tested_parameter_missing" and f.get("missing_role") == "slope")
                or (fk == "null_value_not_null" and f.get("expected") == 1.0)
                or (fk == "lower_order_term_missing_from_k0"
                    and f.get("arm_kind") == "calibration_only" and empty_lower))
            (r8_filtered if is_r8 else keep).append(f)
        adjudicated = keep
        params = record.get("treatment_mechanism", {}).get("tested_parameters") or []
        extended_ok = bool(params) and all(float(p.get("null_value", np.nan)) == 0.0
                                           for p in params)
        if not extended_ok:
            adjudicated.append({"kind": "r8_extended_rule_failed", "blocking": True,
                                "detail": "calibration_only arm must declare >= 1 tested "
                                          "parameter with null_value 0 (term absent = "
                                          "incumbent) -- P35 r8_scope_adjudication"})
    out = {"schema": "p36_p26_wrapper/1", "arm_id": record.get("arm_id"),
           "raw_validation": raw, "r8_filtered_findings": r8_filtered,
           "r8_adjudication_basis": ("P35 shared_frozen_amendments.p26_k0_contract_enforcement"
                                     ".r8_scope_adjudication" if r8_filtered else None),
           "blocking_after_adjudication": adjudicated,
           "valid": not adjudicated}
    if bind and not adjudicated:
        out["binding"] = vk.bind_and_require_matched_k0(record)
    if adjudicated:
        raise GuardHarnessFailure(
            f"P26 K0 contract failure for {record.get('arm_id')}: "
            f"{json.dumps(adjudicated[:4], default=str)}", out)
    return out


# --------------------------------------------------------------------------------------- P25
def p25_check(df, *, candidate_features, nuisance_features, fold_ids=None,
              preregistered_contrasts=None, prereg_digest_expected=None) -> dict:
    """offset_dependency_guard.audit_augmented_design with the frozen invocation pins."""
    odg = _load("P25_offset_dependency_guard")
    for col in (OFFSET_COL, INCUMBENT_PROJECTION_COL):
        if col not in df.columns:
            raise GuardHarnessFailure(f"P25 invocation requires column '{col}' in the frame")
    rec = odg.audit_augmented_design(
        df, list(candidate_features), df[OFFSET_COL].to_numpy(float),
        nuisance_features=list(nuisance_features),
        incumbent_projection=df[INCUMBENT_PROJECTION_COL].to_numpy(float),
        fold_ids=fold_ids,
        declared_family=DECLARED_FAMILY_ALL_FITTED_ARMS,
        recalibration_declaration=None,
        preregistered_contrasts=preregistered_contrasts,
        prereg_digest_expected=prereg_digest_expected,
        raise_on_block=False)
    if not rec["passed"]:
        raise GuardHarnessFailure(
            f"P25 blocking findings: {[f['kind'] for f in rec['blocking']][:6]}", rec)
    return rec


# --------------------------------------------------------------------------------------- P22
def p22_check(frame, names, *, prohibited_basis, lag_specs: dict, lag_sources=None) -> dict:
    """postgame_surrogate_guard.audit on the complete design; LagSpec kwargs -> frozen LagSpec."""
    psg = _load("P22_postgame_surrogate_guard")
    specs = {c: psg.LagSpec(**kw) for c, kw in (lag_specs or {}).items()}
    try:
        rec = psg.audit(frame, list(names), prohibited=prohibited_basis,
                        lag_specs=specs, lag_sources=dict(lag_sources or {}),
                        raise_on_block=False)
    except psg.PostgameSurrogateFailure as e:
        raise GuardHarnessFailure(f"P22 refused: {e}") from e
    if rec.get("blocking"):
        raise GuardHarnessFailure(
            f"P22 blocking findings: {[f['kind'] for f in rec['blocking']][:6]}", rec)
    return rec


def make_prohibited_basis(frame, source: dict, note: str = ""):
    """Construct a ProhibitedBasis from an aligned frame of prohibited quantities. At P38 time
    the caller uses postgame_surrogate_guard.realised_duration_basis against the frozen
    possessions artifact instead; this constructor exists for the synthetic path."""
    psg = _load("P22_postgame_surrogate_guard")
    return psg.ProhibitedBasis(frame=frame, source=dict(source), note=note)


# --------------------------------------------------------------------------------------- P23
def p23_check(*, requires_franchise_continuity: bool, receipts: list) -> dict:
    """Call-site enforcement of the franchise-continuity receipt pin (P35 OP-5)."""
    problems = []
    if requires_franchise_continuity:
        if not receipts:
            problems.append({"kind": "franchise_continuity_receipt_missing",
                             "detail": "the card's P23 precondition names a receipt; absence "
                                       "fails closed (arm/fold unevaluable)"})
        for i, r in enumerate(receipts or []):
            if str(r.get("team_cities_sha256", "")).lower() != TEAM_CITIES_SHA256_PIN:
                problems.append({"kind": "team_cities_pin_mismatch", "receipt_index": i,
                                 "got": r.get("team_cities_sha256"),
                                 "pinned": TEAM_CITIES_SHA256_PIN})
    rec = {"schema": "p36_p23_wrapper/1",
           "requires_franchise_continuity": bool(requires_franchise_continuity),
           "n_receipts": len(receipts or []), "problems": problems, "valid": not problems}
    if problems:
        raise GuardHarnessFailure(f"P23 receipt failure: {problems}", rec)
    return rec


# --------------------------------------------------------------------------------------- P27
def p27_check(df, *, candidate_features, nuisance_terms, cluster_col, season_col="season",
              fold_policy="SEASON_BLOCK", null_features=(), null_nuisance=None,
              rule_kwargs=None, prereg_kwargs=None, arm_id="unnamed_arm") -> dict:
    """fold_estimability_guard.guard once per arm; the guard audits folds internally.

    `fold_policy` is the guard's OWN documented ambiguity (its FOLD_POLICIES docstring: the
    caller must name the reading; the receipt records the choice). Default SEASON_BLOCK is the
    reading under which the S7 finding was stated; the P38 executor may name
    EXPANDING_PRIOR_SEASONS instead -- the choice is recorded in the guard's receipt either way
    and is flagged in the P36 report for P37 adjudication rather than resolved silently here.
    """
    feg = _load("P27_fold_estimability_guard")
    rule = None if rule_kwargs is None else feg.ActiveSetRule(**rule_kwargs)
    prereg = None if prereg_kwargs is None else feg.Preregistration(**prereg_kwargs)
    rec = feg.guard(df, list(candidate_features), list(nuisance_terms), OFFSET_COL,
                    cluster_col, season_col=season_col, fold_policy=fold_policy,
                    null_features=list(null_features),
                    null_nuisance=(None if null_nuisance is None else list(null_nuisance)),
                    rule=rule, prereg=prereg, arm_id=arm_id)
    if rec.get("overall") == "FAIL":
        raise GuardHarnessFailure(f"P27 overall FAIL for {arm_id}", rec)
    return rec
