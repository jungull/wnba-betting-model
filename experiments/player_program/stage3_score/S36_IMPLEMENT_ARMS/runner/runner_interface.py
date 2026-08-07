#!/usr/bin/env python3
"""runner_interface.py -- the frozen element-module contract, and the validator that enforces it.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

ONE MODULE = ONE ARM. ONE `ElementSpec` = ONE FROZEN ELEMENT CARD. The slate is 11 arms over 17
element cards, so there are 11 modules and 17 specs, and the mapping is checked against the frozen
S35 bytes rather than trusted.

The contract's whole job is to make the ONE thing Layer A cares about impossible to get wrong:

    the arm and its K0_MATCHED must differ ONLY by the declared treatment terms.

So a module does not hand the runner two independently-built designs -- it hands over one column
dictionary plus two column NAME lists, and `validate_design` refuses the pair unless
`arm_cols` minus `treatment_cols` is exactly `k0_cols`, in order. Two separately constructed
designs could drift in a preprocessing step, a fallback, or a fold constant; two views of one
dictionary cannot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

import runner_constants as K


class InterfaceViolation(RuntimeError):
    """The module does not satisfy the frozen contract. Fail closed; never 'fix up' a design."""


@dataclass(frozen=True)
class DesignPair:
    """What `ElementSpec.build` returns for one fold.

    columns          -- name -> float ndarray of length len(universe.games), aligned to game order
    arm_cols         -- the arm's design columns, IN ORDER
    k0_cols          -- the K0_MATCHED design columns, IN ORDER
    treatment_cols   -- the card's treatment terms (a subset of arm_cols, absent from k0_cols)
    structural_cols  -- null-granted structural terms, present IDENTICALLY on both sides
    indicator_cols   -- 0/1 columns in either design; the K7 bootstrap NA rule conditions on these
    comparison       -- the card's null_construction.method, e.g. "term_removal"
    fold_constants   -- train-only constants materialised for this fold, receipted verbatim
    """
    columns: dict[str, np.ndarray]
    arm_cols: tuple[str, ...]
    k0_cols: tuple[str, ...]
    treatment_cols: tuple[str, ...]
    structural_cols: tuple[str, ...]
    comparison: str
    indicator_cols: tuple[str, ...] = ()
    fold_constants: dict = field(default_factory=dict)
    deactivated: bool = False           # declared structural deactivation of the TERM, not rows
    deactivation_reason: str | None = None

    def matrix(self, cols: Sequence[str]) -> np.ndarray:
        return np.column_stack([self.columns[c] for c in cols]) if cols else \
            np.zeros((len(next(iter(self.columns.values()))), 0))


@dataclass(frozen=True)
class ElementSpec:
    """One frozen element card, bound to executable code."""
    element_id: str
    arm_id: str
    estimand: str
    primary_metric: str
    arm_kind: str
    family_primary: str
    card_sha256: str
    build: Callable[..., DesignPair]
    kill_conditions: tuple[str, ...]
    mandatory_receipts: tuple[str, ...] = ()
    structurally_deactivated_folds: tuple[str, ...] = ()
    sign_pin: str | None = None
    notes: tuple[str, ...] = ()

    def check_static(self) -> None:
        if self.estimand not in K.ESTIMANDS:
            raise InterfaceViolation(f"{self.element_id}: unregistered estimand {self.estimand}")
        if self.primary_metric != K.PRIMARY_METRIC[self.estimand]:
            raise InterfaceViolation(
                f"{self.element_id}: primary_metric {self.primary_metric} != frozen "
                f"{K.PRIMARY_METRIC[self.estimand]} for {self.estimand}")
        if self.arm_id not in K.ARM_IDS:
            raise InterfaceViolation(f"{self.element_id}: {self.arm_id} is not a retained arm")
        if not self.element_id.startswith(self.arm_id + "::"):
            raise InterfaceViolation(f"{self.element_id}: element_id/arm_id disagree")
        if not self.kill_conditions:
            raise InterfaceViolation(
                f"{self.element_id}: no kill conditions carried. Every card in this slate pins at "
                f"least one, and 'an uncheckable kill is a card defect'.")


def validate_design(spec: ElementSpec, dp: DesignPair, n_rows: int) -> dict:
    """Layer-A parity, checked structurally. Every failure here is Severity A by name."""
    # The slate pins exactly two null constructions: 16 cards term_removal, SC08 alone
    # parameter_fixed_at_null (gamma1 = gamma2 = 0). Anything else would be a card change.
    if dp.comparison not in ("term_removal", "parameter_fixed_at_null"):
        raise InterfaceViolation(
            f"{spec.element_id}: null_construction.method {dp.comparison!r} is neither frozen "
            f"method ('term_removal' / 'parameter_fixed_at_null')")

    for name, col in dp.columns.items():
        a = np.asarray(col)
        if a.shape != (n_rows,):
            raise InterfaceViolation(
                f"{spec.element_id}: column {name!r} has shape {a.shape}, expected ({n_rows},) -- "
                f"columns must be aligned to the full game order")
        if not np.isfinite(a).all():
            raise InterfaceViolation(f"{spec.element_id}: column {name!r} carries a non-finite "
                                     f"value; imputation must be declared, never implicit")

    missing = [c for c in set(dp.arm_cols) | set(dp.k0_cols) if c not in dp.columns]
    if missing:
        raise InterfaceViolation(f"{spec.element_id}: design names undeclared columns {missing}")

    # --- THE PARITY CHECK -------------------------------------------------------------------
    expected_k0 = tuple(c for c in dp.arm_cols if c not in set(dp.treatment_cols))
    if expected_k0 != tuple(dp.k0_cols):
        raise InterfaceViolation(
            f"{spec.element_id}: SEVERITY A -- unmatched comparison flexibility. The K0 design is "
            f"{tuple(dp.k0_cols)} but arm-minus-treatment is {expected_k0}. The two sides must "
            f"differ ONLY by the declared treatment terms.")
    if set(dp.treatment_cols) & set(dp.k0_cols):
        raise InterfaceViolation(
            f"{spec.element_id}: SEVERITY A -- a treatment term survives in the K0 design")
    for c in dp.structural_cols:
        if c not in dp.arm_cols or c not in dp.k0_cols:
            raise InterfaceViolation(
                f"{spec.element_id}: null-granted structural term {c!r} is not present on BOTH "
                f"sides; 'NULL_GRANTED_INGREDIENTS_CARRIED' means the null keeps it")
    if not dp.deactivated and not dp.treatment_cols:
        raise InterfaceViolation(
            f"{spec.element_id}: no treatment column, and no declared structural deactivation")

    # --- the intercept rule ------------------------------------------------------------------
    for side, cols in (("arm", dp.arm_cols), ("k0", dp.k0_cols)):
        n_ones = [c for c in cols if np.allclose(dp.columns[c], 1.0)]
        if "intercept" in cols:
            if not np.allclose(dp.columns["intercept"], 1.0):
                raise InterfaceViolation(f"{spec.element_id}/{side}: 'intercept' is not all-ones")
        extra = [c for c in n_ones if c != "intercept"]
        if extra:
            raise InterfaceViolation(
                f"{spec.element_id}/{side}: constant column(s) {extra} act as a silent second "
                f"intercept; a design has an intercept iff a ones column NAMED 'intercept' is "
                f"declared, identically on both sides")
    if ("intercept" in dp.arm_cols) != ("intercept" in dp.k0_cols):
        raise InterfaceViolation(f"{spec.element_id}: intercept present on one side only")

    for c in dp.indicator_cols:
        v = np.unique(dp.columns[c])
        if not set(v.tolist()) <= {0.0, 1.0}:
            raise InterfaceViolation(f"{spec.element_id}: {c!r} declared an indicator but is not "
                                     f"0/1")
    return {"schema": "s36_design_parity/1", "element_id": spec.element_id,
            "arm_cols": list(dp.arm_cols), "k0_cols": list(dp.k0_cols),
            "treatment_cols": list(dp.treatment_cols),
            "structural_cols": list(dp.structural_cols),
            "indicator_cols": list(dp.indicator_cols),
            "comparison": dp.comparison,
            "differ_only_by_treatment_terms": True,
            "intercept_declared": "intercept" in dp.arm_cols,
            "deactivated": dp.deactivated, "deactivation_reason": dp.deactivation_reason,
            "fold_constants": dp.fold_constants}


def validate_module(mod) -> dict:
    """A module must expose ARM_ID, ELEMENTS and FORMULA. Fails closed on anything else."""
    for attr in ("ARM_ID", "ELEMENTS", "FORMULA"):
        if not hasattr(mod, attr):
            raise InterfaceViolation(f"{mod.__name__}: missing required attribute {attr}")
    if mod.ARM_ID not in K.ARM_IDS:
        raise InterfaceViolation(f"{mod.__name__}: {mod.ARM_ID} is not a retained arm")
    if not mod.ELEMENTS:
        raise InterfaceViolation(f"{mod.__name__}: no elements")
    for s in mod.ELEMENTS:
        s.check_static()
        if s.arm_id != mod.ARM_ID:
            raise InterfaceViolation(f"{mod.__name__}: element {s.element_id} belongs to "
                                     f"{s.arm_id}")
    return {"module": mod.__name__, "arm_id": mod.ARM_ID,
            "elements": [s.element_id for s in mod.ELEMENTS], "formula": mod.FORMULA}
