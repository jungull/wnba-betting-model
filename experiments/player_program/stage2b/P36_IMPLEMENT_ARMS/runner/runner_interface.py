#!/usr/bin/env python3
"""runner_interface.py -- programmatic form of RUNNER_INTERFACE.md.

`validate_arm_module` is the conformance gate every arm module passes before the runner will
touch it, and `validate_design_bundle` checks each per-fold build_design return, including the
frozen intercept invariant (P35 no_implementation_default_intercept_invariant) and the frozen
intercept table.
"""
from __future__ import annotations

import numpy as np

from runner_constants import (ARMS_WITH_FREE_GLOBAL_INTERCEPT, ARMS_WITHOUT_GLOBAL_INTERCEPT,
                              DECLARED_FAMILY_ALL_FITTED_ARMS, INTERCEPT_COL,
                              RECALIBRATION_DECLARATION)

REQUIRED_CALLABLES = (
    "card_id", "declared_family", "recalibration_declaration", "enumeration_element",
    "element_id", "uses_global_intercept", "build_design", "p26_k0_record", "lag_specs",
    "lag_sources", "preregistered_contrasts", "prereg_digest_expected",
    "requires_franchise_continuity", "p23_receipts", "p27_rule")

REQUIRED_BUNDLE_KEYS = ("treatment_cols", "nuisance_cols", "k0_matched_design",
                        "indicator_cols", "columns")
REQUIRED_K0_KEYS = ("treatment_cols", "nuisance_cols", "comparison")
VALID_COMPARISONS = ("term_removal", "parameter_fixed_at_null")

#: toy/synthetic arm ids are exempt from the intercept table (they are not P35 cards); every
#: real card id starts with 'A' + two digits and MUST appear in exactly one table.
_TABLE = {}
for _a in ARMS_WITH_FREE_GLOBAL_INTERCEPT:
    _TABLE[_a] = True
for _a in ARMS_WITHOUT_GLOBAL_INTERCEPT:
    _TABLE[_a] = False


class ArmModuleNonconformant(RuntimeError):
    def __init__(self, problems: list):
        self.problems = problems
        super().__init__(f"arm module nonconformant: {problems[:6]}")


def _card_prefix(arm_id: str) -> str:
    return str(arm_id).split("_")[0]


def validate_arm_module(mod) -> dict:
    problems = []
    if not isinstance(getattr(mod, "arm_id", None), str) or not getattr(mod, "arm_id", ""):
        problems.append({"kind": "missing_attr", "name": "arm_id"})
    for name in REQUIRED_CALLABLES:
        if not callable(getattr(mod, name, None)):
            problems.append({"kind": "missing_hook", "name": name})
    if problems:
        raise ArmModuleNonconformant(problems)

    fam = mod.declared_family()
    if fam != DECLARED_FAMILY_ALL_FITTED_ARMS:
        problems.append({"kind": "declared_family_not_pinned", "got": fam,
                         "pinned": DECLARED_FAMILY_ALL_FITTED_ARMS,
                         "basis": "P35 p25_guard_invocation_pins"})
    rd = mod.recalibration_declaration()
    if rd != RECALIBRATION_DECLARATION:
        problems.append({"kind": "recalibration_declaration_not_pinned", "got": rd,
                         "pinned": RECALIBRATION_DECLARATION})
    elem = mod.enumeration_element()
    if not isinstance(elem, dict):
        problems.append({"kind": "enumeration_element_not_dict", "got": type(elem).__name__})
    prefix = _card_prefix(mod.arm_id)
    uses = bool(mod.uses_global_intercept())
    if prefix in _TABLE and uses != _TABLE[prefix]:
        problems.append({"kind": "intercept_table_violation", "arm": prefix,
                         "declared": uses, "frozen_table": _TABLE[prefix],
                         "basis": "P35 intercept_structure"})
    if mod.requires_franchise_continuity() and not isinstance(mod.p23_receipts(), list):
        problems.append({"kind": "p23_receipts_not_list"})
    rec = {"schema": "p36_arm_module_conformance/1", "arm_id": mod.arm_id,
           "element_id": mod.element_id(), "enumeration_element": elem,
           "problems": problems, "conformant": not problems}
    if problems:
        raise ArmModuleNonconformant(problems)
    return rec


def validate_design_bundle(bundle: dict, universe, uses_global_intercept: bool,
                           fold_id: str) -> dict:
    """Shape + intercept invariant for one build_design return. Fails closed."""
    problems = []
    for k in REQUIRED_BUNDLE_KEYS:
        if k not in bundle:
            problems.append({"kind": "bundle_key_missing", "key": k})
    if problems:
        raise ArmModuleNonconformant(problems)
    k0 = bundle["k0_matched_design"]
    for k in REQUIRED_K0_KEYS:
        if k not in k0:
            problems.append({"kind": "k0_design_key_missing", "key": k})
    if k0.get("comparison") not in VALID_COMPARISONS:
        problems.append({"kind": "comparison_invalid", "got": k0.get("comparison"),
                         "valid": list(VALID_COMPARISONS)})

    n = len(universe)
    cols = bundle["columns"]
    for name, v in cols.items():
        if len(np.asarray(v)) != n:
            problems.append({"kind": "column_length_mismatch", "column": name,
                             "got": int(len(np.asarray(v))), "expected": n})

    arm_cols = list(bundle["treatment_cols"]) + list(bundle["nuisance_cols"])
    null_cols = list(k0.get("treatment_cols", [])) + list(k0.get("nuisance_cols", []))
    available = set(cols) | set(universe.columns)
    for c in set(arm_cols) | set(null_cols):
        if c not in available:
            problems.append({"kind": "design_column_unmaterialised", "column": c})

    # ---- frozen intercept invariant: explicit column iff pinned, IDENTICALLY arm and null ----
    in_arm, in_null = INTERCEPT_COL in arm_cols, INTERCEPT_COL in null_cols
    if uses_global_intercept:
        if not (in_arm and in_null):
            problems.append({"kind": "intercept_missing", "in_arm": in_arm, "in_null": in_null,
                             "detail": "free global intercept pinned for this arm: the explicit "
                                       "column of ones must appear in BOTH designs"})
        if INTERCEPT_COL in cols:
            v = np.asarray(cols[INTERCEPT_COL], float)
            if not np.all(v == 1.0):
                problems.append({"kind": "intercept_not_ones"})
        elif INTERCEPT_COL not in universe.columns:
            problems.append({"kind": "intercept_column_unmaterialised"})
    else:
        if in_arm or in_null:
            problems.append({"kind": "intercept_forbidden", "in_arm": in_arm, "in_null": in_null,
                             "detail": "no global intercept in arm or null for this card; a "
                                       "design that acquires one recreates the P2/S4 defect and "
                                       "VOIDS the arm"})
    # a constant non-intercept design column is a silent intercept -- refuse it here, on the
    # full universe (fold-local constancy is P25/P27's jurisdiction, not a silent pass here)
    for c in set(arm_cols) | set(null_cols):
        if c == INTERCEPT_COL or c not in cols:
            continue
        v = np.asarray(cols[c], float)
        if v.size and np.nanstd(v) == 0.0:
            problems.append({"kind": "constant_design_column_is_silent_intercept", "column": c})

    ind = set(bundle["indicator_cols"])
    if INTERCEPT_COL in ind:
        problems.append({"kind": "intercept_listed_as_indicator",
                         "detail": "the intercept is structural; listing it as an indicator "
                                   "would make every K7 draw NA"})
    unknown_ind = ind - set(arm_cols) - set(null_cols)
    if unknown_ind:
        problems.append({"kind": "indicator_not_in_design", "columns": sorted(unknown_ind)})

    rec = {"schema": "p36_design_bundle_validation/1", "fold_id": str(fold_id),
           "arm_design_columns": arm_cols, "null_design_columns": null_cols,
           "comparison": k0.get("comparison"), "indicator_cols": sorted(ind),
           "problems": problems, "valid": not problems}
    if problems:
        raise ArmModuleNonconformant(problems)
    return rec
