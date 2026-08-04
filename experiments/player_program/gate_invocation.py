#!/usr/bin/env python3
"""gate_invocation.py — PERMANENT invocation gate around ``feature_gate.audit``.

Born from the OPTIONAL-ARGUMENT defect. ``feature_gate.audit`` takes ``offset=``, ``target=``,
``outcome_mask=`` and ``test_df=`` as OPTIONAL keyword arguments defaulting to ``None``. Each
omission silently deletes checks from the audit:

    no ``offset``        -> ``deterministic_transform_of_offset`` cannot fire
    no ``target``        -> ``target_derived``, ``missingness_informative`` and the
                            target branch of ``missingness_encodes_outcome`` cannot fire
    no ``outcome_mask``  -> the exact off-diagonal branch of ``missingness_encodes_outcome``
                            cannot fire
    no ``test_df``       -> ``schema_mismatch`` cannot fire

The gate then returns ``"passed": true`` with ``"findings": []``, and that record is
**byte-indistinguishable from a real one**. Nothing in the output says four checks never ran.
That is the hole this module closes, and it is exactly the hole ``GATE_INVOCATION_CONTRACT.md``
§3.1 names: *"An audit record that omits an applicable argument is not a passing audit. It is an
incomplete audit and must be recorded as such."*

There is a second, larger hole with the same shape. Eight workstreams ran against a gate whose
implementation nobody recorded at the time, so no surviving record can say WHICH gate passed
them. A receipt that cannot identify the gate that ran, the caller that ran it, and the exact
rows, columns, offset, target, mask and test frame it examined, is not evidence. Every record
this module emits carries all of them, and is BOUND to them by a digest, so presenting it for
different inputs blocks instead of passing.

**This module does not modify, restate, weaken or extend ``feature_gate.py``.** The gate defines
*what* is checked and governs wherever the two appear to disagree. This module governs *how it is
called*, *when* (contract §6: every chronological training fold AND the final assembled design),
and *what the record must prove about its own inputs*.

What is closed here, all at the INVOCATION layer, all **before any fit occurs**:

1. **Omission and nullity.** A required argument that is absent or ``None`` blocks. There is no
   default that means "probably fine" — that default is the defect.
2. **Row identity.** ``feature_gate`` consumes these arguments POSITIONALLY
   (``np.asarray(offset, float)``, ``X[c].to_numpy(float)``). A pandas object whose index is a
   permutation of the design's is silently used in the wrong row order, and every correlation the
   gate computes is then a correlation between mismatched rows. Wrong length, wrong order, or a
   different universe of rows: all block.
3. **Silent reordering versus explicit alignment.** A reorder the caller did not ask for blocks.
   A reorder the caller explicitly requested — ``align={"offset": "reindex_to_design_index"}`` —
   is performed deterministically, is recorded in the receipt with the before and after index
   digests, and the REALIGNED objects are what the caller must fit; ``guarded_fit`` hands them
   back for exactly that reason. The distinction is not stylistic: the wrapper can reindex its own
   copy but not the object the caller fits, so an unrequested realignment would produce a record
   about a matrix nobody fits, which is the precise failure contract §1 exists to forbid.
4. **Silent defaults.** A freshly-constructed zero offset, an all-``True`` outcome mask, a
   constant target and a ``test_df`` that is the training frame itself are each formally supplied
   and each disable precisely the check they were supposed to enable. The all-``True`` mask is the
   sharpest instance: ``off_diag = min(k, n-k)`` computed against a constant mask can never reach
   zero for a column with both missing and observed rows, so the exact-indicator branch is dead
   while the record says the mask was supplied.
5. **Train/test schema drift**, pre-checked at the invocation layer so it blocks before the gate
   call rather than inside it.
6. **Unwritable receipts.** A receipt that cannot be written is a gate failure, not a warning. An
   arm that fits without an archivable record has no gate record, and "the gate exists in the
   repository" is not a gate record.
7. **Receipt reuse.** Every record is bound to a digest over its identity and all of its input
   digests. ``verify_receipt`` recomputes that binding from the inputs presented and blocks on
   divergence, so a passing receipt cannot be carried across to a different design, fold, arm,
   target or gate version.
8. **Absent per-fold records.** Contract §6. ``audit_run`` blocks when no chronological fold was
   audited, and names the pooled-healthy / fold-degenerate shape (ws3, ``proj_off_poss_share`` std
   ``7.80108356964482e-09`` in the 2022 fold against ``findings: []`` pooled) as its own finding.
9. **Pre-gate transformation** — the ws2 class, contract §8a. See below.

THE DUAL FRAME (contract §8a)
-----------------------------
ws2's ``build_constructions()`` imputed to ``0.0`` BEFORE the gate was called. What reached the
gate was a fully populated design with no missingness at all, a valid non-placeholder ``target``,
``offset``, ``outcome_mask`` and ``test_df``, and correctly aligned row identities. Every fold
passed. The null mask had already been converted into ordinary numeric values and survived as one:
``transfer_direct``, ``transfer_allocated`` and ``transfer_role_sensitive`` are non-zero on
25,522 / 25,522 / 9,577 appearers and on **zero** of the 8,278 non-appearers, so a non-zero value
certifies appearance. ``missingness_encodes_outcome`` cannot fire on a frame with no missingness,
and none of the checks in item 1-8 above can see this: the caller supplied every argument, all of
them valid. **A gate that only ever sees the transformed frame is blind to this by construction.**

**The rule: dual-frame provenance is MANDATORY for every fitted feature design.** It is NOT
conditional on a transformation being declared or detected, because a fully populated transformed
frame cannot reveal that a raw frame was withheld — that is precisely the failure class being
closed. There is no "the frame looked clean so we did not ask" branch; that branch IS the defect.
Two valid cases, and no third:

*Case 1, no transformation.* The pre-transformation frame and the fitted frame may be the same
object or byte-identical, and the caller is NOT forced to duplicate the frame — ``raw_df=df`` is
correct and sufficient. The caller must still declare ``transformation=no_transformation(reason)``
and the wrapper PROVES the two are identical rather than believing it. Recorded: transformation
kind ``none``, raw digest, fitted digest, the equality result, raw AND fitted per-column
missingness-mask digests, row and feature-order reconciliation.

*Case 2, transformation performed.* Requires the pre-transformation frame, an explicit
transformation specification, the fitted transformed frame, an audit of BOTH frames, row and
column reconciliation, and the exact digest of the matrix handed to the fitter.

No fit occurs if either frame or the declared transformation lineage is unavailable.

**Producer provenance.** A caller calling a matrix "raw" is a claim, not evidence. ``provenance=``
binds the raw frame to the upstream producer by source hash, input-manifest hashes, a
feature-construction receipt, experiment/arm identity and a row-universe digest, each of which is
verified against the filesystem and against the frame actually supplied. A claim that cannot be
verified BLOCKS. Provenance that is not claimed at all does not block, but it is not silently
given the assurance of a verified one either.

**Assurance level.** Every record reports exactly one:

    ``IDENTITY_VERIFIED``        raw and fitted frames proven identical, provenance verified
    ``TRANSFORMATION_VERIFIED``  both frames and the transformation lineage verified
    ``RAW_PROVENANCE_ASSERTED``  dual frames supplied, upstream provenance not demonstrable
    ``FAILED``                   at least one unadjudicated blocking finding

Only the first two are a full Stage 1 pass (``stage1_pass``). **In this repository there is no
feature-construction receipt or input manifest wired into the producers, so a caller who does not
supply ``provenance=`` explicitly reaches ``RAW_PROVENANCE_ASSERTED`` and no higher.** That is
reported as a limitation of the lineage, not smoothed over by redefining the levels.

Detection of the ws2 case itself is two-sided and neither side is trusted alone:

* the RAW frame is audited with ``feature_gate.audit(..., outcome_mask=...)``, where an
  outcome-encoding null mask fires ``missingness_encodes_outcome``; if the transformed frame then
  has fewer nulls in that column, the mask was converted into values —
  ``missingness_mask_converted_to_values``. Raw-blocks-plus-transformed-clean is the signature.
* independently, the TRANSFORMED frame's own values are checked for a pattern that separates the
  outcome mask: a value carried by every outcome-negative row and absent from at least one
  outcome-positive row means a row NOT carrying it certifies the outcome —
  ``value_pattern_encodes_outcome``. This is the ws2 shape stated as a property of the values, and
  it fires whether or not a raw frame was ever produced.

Imputation is **not** prohibited. It must be explicit, cutoff-valid, fitted only on chronological
training rows, frozen, applied unchanged to the held-out frame, and auditable. A caller who
declares all of that and whose raw missingness is not outcome-associated PASSES.

Usage::

    from gate_invocation import FoldInvocation, audit_fold, audit_run, guarded_fit, verify_receipt

    rec = audit_fold(train_df, names, experiment="turnover_p3", arm="A", fold="2022",
                     offset=off, target=y, outcome_mask=appeared, test_df=test_2023,
                     raw_df=train_df,                       # Case 1: same object is correct
                     transformation=no_transformation("producer emits the fitted frame"),
                     receipt_path="turnover_p3_v1/gate/fold_2022.json")

    rec = audit_fold(imputed_df, names, ...,                # Case 2: transformation performed
                     raw_df=pre_imputation_df,
                     transformation={"kind": "imputation", "description": "...",
                                     "operations": [{"columns": ["trailing_minutes_share"],
                                                     "method": "fill_constant", "value": 0.0,
                                                     "reason": "...", "cutoff_valid": True,
                                                     "frozen_parameters": {"value": 0.0},
                                                     "fitted_on_row_universe_digest": d}]},
                     fitted_matrix=X, provenance={"producer_source_path": "build.py", ...})

    receipt = audit_run(run_id="turnover_p3_arm_a", experiment="turnover_p3", arm="A",
                        folds=[FoldInvocation("2022", df22, names, off22, y22, m22, df23), ...],
                        final_design=FoldInvocation("final_design", pooled, names, ...),
                        receipt_path="turnover_p3_v1/GATE_INVOCATION_RECEIPT.json")

Every entry point returns a machine-readable dict and raises ``GateInvocationFailure`` on a
blocking condition unless it is explicitly adjudicated WITH A STATED REASON, which is then carried
in the record forever. An adjudicated argument defect is allowed; a HIDDEN one is not. Omission,
nullity, length, misalignment, universe mismatch, receipt reuse and an unwritable receipt are
``NON_ADJUDICABLE``: an escape hatch for "I did not supply it" would reopen the defect verbatim. A
genuinely inapplicable argument is declared through ``not_applicable={"test_df": "reason"}``,
which does not block but marks the record ``"complete": false`` and enumerates the checks that did
not run.

Pure stdlib + numpy/pandas. Python 3.13.

Run::  python experiments/player_program/gate_invocation.py
"""
from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np, pandas as pd                                               # noqa: E401

try:                                                                            # pragma: no cover
    import feature_gate
except ModuleNotFoundError:                                                     # pragma: no cover
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import feature_gate

_THIS_FILE = Path(__file__).resolve()

# --------------------------------------------------------------------------------------------
# the arguments that are optional in the signature and mandatory under the contract
#
# The right-hand columns are GATE_INVOCATION_CONTRACT.md §3.1, in code, so the obligation is
# executable rather than prose. `feature_gate.py` governs what each check does.
# --------------------------------------------------------------------------------------------
REQUIRED_ARGUMENTS: tuple[str, ...] = ("offset", "target", "outcome_mask", "test_df")

#: the three that must be row-aligned to the design. `test_df` is a different row universe by
#: construction and is checked separately.
ROW_ALIGNED_ARGUMENTS: tuple[str, ...] = ("offset", "target", "outcome_mask")

#: which `feature_gate` finding kinds each argument makes reachable. An argument that is not
#: supplied does not weaken these checks — it DELETES them.
ARGUMENT_ENABLES: dict[str, tuple[str, ...]] = {
    "offset": ("deterministic_transform_of_offset",),
    "target": ("target_derived", "missingness_informative", "missingness_encodes_outcome"),
    "outcome_mask": ("missingness_encodes_outcome",),
    "test_df": ("schema_mismatch",),
}

ARGUMENT_WHY: dict[str, str] = {
    "offset": "every turnover arm carries log(exposure) (and log(D)) in the offset",
    "target": "leakage from target-derived fields, and informative missingness",
    "outcome_mask": "the exact-indicator branch of the null-mask check",
    "test_df": "fold train/test schema drift",
}

#: the ONLY alignment a caller may request. It is deterministic, it is total (membership must
#: already match exactly), and it is recorded. Anything else is a repair, and repairs belong in
#: the producer, not in the gate wrapper.
ALIGNMENT_METHODS: tuple[str, ...] = ("reindex_to_design_index",)

#: `feature_gate` skips a pairwise check when fewer than ten rows are jointly finite
#: (``if m.sum() < 10: continue``). An argument with fewer than this many finite values is
#: supplied in form and absent in effect.
GATE_MIN_ROWS = 10

# --------------------------------------------------------------------------------------------
# dual-frame vocabulary -- contract §8a
# --------------------------------------------------------------------------------------------

#: exactly one of these is reported on every record. They are ordered worst-last for aggregation.
ASSURANCE_LEVELS: tuple[str, ...] = ("IDENTITY_VERIFIED", "TRANSFORMATION_VERIFIED",
                                     "RAW_PROVENANCE_ASSERTED", "FAILED")

#: only these two are a full Stage 1 pass.
STAGE1_PASS_LEVELS: tuple[str, ...] = ("IDENTITY_VERIFIED", "TRANSFORMATION_VERIFIED")

#: ``kind`` values a transformation declaration may carry. ``none`` asserts that the frame handed
#: to the fitter IS the frame the producer emitted, and that assertion is then PROVEN by digest.
TRANSFORMATION_KINDS: tuple[str, ...] = ("none", "imputation", "transformation")

#: a method whose name begins with one of these is treated as filling missing values, which
#: carries the extra obligation that the columns it names actually HAVE missing values in the
#: frame presented as raw. If they do not, the fill happened before the raw audit.
IMPUTATION_METHOD_PREFIXES: tuple[str, ...] = ("fill", "impute", "ffill", "bfill", "interpolat")

#: every field of a transformation operation that must be present and non-empty.
OPERATION_REQUIRED_FIELDS: tuple[str, ...] = ("columns", "method", "reason", "cutoff_valid")

#: finding kinds that invalidate an invocation.
BLOCKING = {
    # -- identity of the run, the caller and the gate ---------------------------------------
    "identity_unspecified", "caller_source_unidentifiable",
    # -- the four required arguments --------------------------------------------------------
    "argument_omitted", "argument_null", "argument_wrong_type", "argument_empty",
    "argument_length_mismatch", "argument_misaligned", "argument_universe_mismatch",
    "argument_row_identity_absent", "argument_is_placeholder_default", "argument_constant",
    "argument_all_non_finite", "argument_insufficient_finite_rows", "argument_not_boolean",
    "test_df_overlaps_design", "train_test_schema_mismatch",
    # -- explicit alignment ------------------------------------------------------------------
    "unknown_alignment_method", "alignment_ambiguous",
    # -- the design itself -------------------------------------------------------------------
    "feature_absent_from_design", "duplicate_feature_name",
    # -- declarations about arguments --------------------------------------------------------
    "not_applicable_without_reason", "not_applicable_contradicted", "unknown_argument_declared",
    "adjudication_without_reason",
    # -- the gate call -------------------------------------------------------------------------
    "gate_blocked", "gate_not_invoked",
    # -- the receipt itself --------------------------------------------------------------------
    "receipt_unwritable", "receipt_not_declared", "receipt_reuse_detected",
    "receipt_producer_divergence", "receipt_schema_unrecognised", "receipt_binding_absent",
    # -- the per-fold recording obligation, contract §6 -----------------------------------------
    "no_per_fold_record", "no_final_design_record", "fold_invocation_failed",
    "final_design_invocation_failed", "duplicate_fold_id", "fold_set_mismatch",
    # -- the DUAL FRAME, contract §8a -------------------------------------------------------------
    # presence and declaration
    "raw_frame_absent", "transformation_undeclared", "transformation_declaration_malformed",
    "declared_identity_contradicted",
    # reconciliation between the two frames
    "raw_transformed_row_identity_mismatch", "raw_transformed_column_mismatch",
    "column_transformation_undeclared", "imputation_precedes_raw_audit",
    "imputation_rule_fitted_off_training_rows",
    # what the two frames say together, and what the transformed values say alone
    "raw_frame_gate_blocked", "missingness_mask_converted_to_values",
    "value_pattern_encodes_outcome",
    # the matrix actually handed to the fitter
    "fitted_matrix_undeclared", "audited_matrix_is_not_the_fitted_matrix",
    # the producer behind the frame called "raw"
    "producer_provenance_unverifiable",
}

#: adjudication cannot excuse the defect this module exists to close. "I did not supply the
#: target, and here is my reason" is the silent pass with a note attached. Nor can it excuse a
#: malformed adjudication, an unwritable receipt, a reused receipt, or the absence of the per-fold
#: record. A genuinely inapplicable argument is declared through ``not_applicable=``, which marks
#: the record INCOMPLETE rather than passing.
NON_ADJUDICABLE = {
    "argument_omitted", "argument_null",
    "argument_length_mismatch", "argument_misaligned", "argument_universe_mismatch",
    "adjudication_without_reason", "not_applicable_without_reason",
    "identity_unspecified",
    "receipt_unwritable", "receipt_not_declared", "receipt_reuse_detected",
    "receipt_binding_absent", "receipt_schema_unrecognised",
    "no_per_fold_record", "gate_not_invoked",
    # -- the dual frame. "I did not supply the frame the gate exists to see" is the ws2 defect
    # verbatim, and an escape hatch for it would reopen the class this module is closing. The two
    # deliberate exceptions are `raw_frame_gate_blocked` and `value_pattern_encodes_outcome`,
    # which are judgements about DATA rather than about what the caller withheld, and are
    # adjudicable with a stated reason exactly as `gate_blocked` is.
    "raw_frame_absent", "transformation_undeclared", "transformation_declaration_malformed",
    "declared_identity_contradicted", "raw_transformed_row_identity_mismatch",
    "raw_transformed_column_mismatch", "column_transformation_undeclared",
    "imputation_precedes_raw_audit", "imputation_rule_fitted_off_training_rows",
    "missingness_mask_converted_to_values", "fitted_matrix_undeclared",
    "audited_matrix_is_not_the_fitted_matrix", "producer_provenance_unverifiable",
}

#: recorded, never blocking. Listed so that "not in BLOCKING" is a deliberate statement.
INFORMATIONAL = {
    "argument_declared_not_applicable", "audit_incomplete", "adjudication_unused",
    "design_index_is_positional", "test_df_partially_overlaps_design",
    "test_frame_columns_differ", "argument_realigned", "alignment_unused",
    "pooled_healthy_fold_degenerate", "receipt_binding_verified",
    # -- the dual frame -------------------------------------------------------------------------
    "raw_provenance_asserted_not_verified", "raw_frame_is_the_fitted_frame",
    "raw_frame_columns_differ", "declared_transformation_had_no_effect",
    "authorised_row_operation", "authorised_column_operation", "raw_audit_restricted",
}

#: the ws3 case, kept in the module so the magnitude is never re-derived from memory.
REFERENCE_CASE = {
    "source": "discovery_wave_1/ws3, stage-2 within-team-centred design, 2022 training fold",
    "pooled_audit": {"n_features": 8, "n_rows": 35629, "findings": [], "passed": True},
    "fold_2022": {"proj_off_poss_share_std": 7.80108356964482e-09,
                  "p_active_std": 5.13611574504531e-17,
                  "gate_finding": "impossible_scaling"},
    "note": "the pooled audit passed the two columns the 2022 fold audit blocks; identifiability "
            "is a per-fold property and is not preserved under pooling",
}

RECORD_SCHEMA = "gate_invocation.record/2"
RECEIPT_SCHEMA = "gate_invocation.receipt/2"


class GateInvocationFailure(RuntimeError):
    """Raised when the gate was not invoked with arguments that can be shown to be the real ones."""


class _Unspecified:
    """Sentinel. Distinct from ``None`` so that "omitted" and "explicitly null" are separable.

    They are separable because they are different mistakes: omission is a caller who never
    thought about the argument, nullity is a caller who thought about it and passed the value
    that disables the check.
    """

    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self) -> str:                       # pragma: no cover - trivial
        return "<UNSPECIFIED>"

    def __bool__(self) -> bool:
        return False


UNSPECIFIED = _Unspecified()


# --------------------------------------------------------------------------------------------
# digests -- the evidence that a receipt can identify its own inputs
# --------------------------------------------------------------------------------------------

def _scalar_repr(v: Any) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "True" if bool(v) else "False"
    if isinstance(v, (float, np.floating)):
        return repr(float(v))
    if isinstance(v, (int, np.integer)):
        return repr(int(v))
    if v is None:
        return "None"
    if isinstance(v, tuple):
        return "\x1f".join(_scalar_repr(x) for x in v)
    return str(v)


def _digest(vals: Sequence[str], label: str) -> str:
    h = hashlib.sha256("\x00".join(vals).encode("utf-8")).hexdigest()
    return f"{label}:n={len(vals)}:sha256={h[:32]}"


def _values_list(v: Any) -> list:
    if isinstance(v, (pd.Series, pd.Index)):
        return v.tolist()
    if isinstance(v, np.ndarray):
        return v.tolist()
    return list(v)


def value_digest(v: Any, *, label: str = "values") -> str:
    """Digest of the VALUES in row order, independent of any index.

    Two arguments carrying the same numbers in the same order agree on this string. It is the
    half of argument identity that says *what was examined*.
    """
    if isinstance(v, pd.DataFrame):
        head = "\x1e".join(str(c) for c in v.columns)
        rows = ["\x1f".join(_scalar_repr(x) for x in t)
                for t in v.itertuples(index=False, name=None)]
        return _digest([head] + rows, label)
    return _digest([_scalar_repr(x) for x in _values_list(v)], label)


def index_digest(idx: Any, *, sort: bool = False, label: str | None = None) -> str:
    """Digest of ROW IDENTITY.

    ``sort=False`` digests the labels in order and therefore changes under a permutation.
    ``sort=True`` digests the label multiset and therefore does NOT change under a permutation
    but DOES change under a change of universe. The pair separates the two failures after the
    fact: equal membership with differing order is misalignment; differing membership at equal
    length is a different universe of rows. Neither is visible in a length.
    """
    labels = [_scalar_repr(x) for x in _values_list(idx)]
    if sort:
        labels = sorted(labels)
    return _digest(labels, label or ("index_membership" if sort else "index"))


def _index_of(v: Any) -> pd.Index | None:
    if isinstance(v, (pd.Series, pd.DataFrame)):
        return v.index
    if isinstance(v, pd.Index):
        return v
    return None


def _is_positional_index(idx: pd.Index) -> bool:
    """A default 0..n-1 RangeIndex is a row NUMBER, not a row IDENTITY."""
    if isinstance(idx, pd.RangeIndex):
        return idx.start == 0 and idx.step == 1
    try:
        return bool(idx.equals(pd.RangeIndex(len(idx))))
    except Exception:                                            # pragma: no cover - defensive
        return False


def _numeric(v: Any) -> np.ndarray | None:
    try:
        a = np.asarray(_values_list(v), dtype=float)
    except (TypeError, ValueError):
        return None
    return a.reshape(-1) if a.ndim else a.reshape(1)


def _summary(v: Any) -> dict:
    """A small, JSON-safe description of an argument. Evidence, not a substitute for the digest."""
    if isinstance(v, pd.DataFrame):
        return {"kind": "frame", "n_rows": int(len(v)), "n_columns": int(v.shape[1]),
                "columns": [str(c) for c in v.columns],
                "n_missing_cells": int(v.isna().to_numpy().sum())}
    vals = _values_list(v)
    out: dict[str, Any] = {"kind": "vector", "n": len(vals),
                           "n_unique": len({_scalar_repr(x) for x in vals})}
    a = _numeric(v)
    if a is None:
        out["numeric"] = False
        return out
    fin = np.isfinite(a)
    out.update({"numeric": True, "n_finite": int(fin.sum()),
                "n_non_finite": int((~fin).sum())})
    if fin.any():
        out.update({"min": float(np.min(a[fin])), "max": float(np.max(a[fin])),
                    "mean": float(np.mean(a[fin])), "std": float(np.std(a[fin]))})
    return out


# --------------------------------------------------------------------------------------------
# which gate ran, and which caller ran it
#
# This is the load-bearing part. Eight workstreams ran under a gate blob nobody recorded, so no
# surviving artifact can say which implementation passed them. Both hashes go in every record and
# both are part of the receipt binding.
# --------------------------------------------------------------------------------------------

def _sha256_file(p: str | Path | None) -> str | None:
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest() if p else None
    except Exception:                                            # pragma: no cover - defensive
        return None


def gate_module_identity() -> dict:
    """Identify the gate this invocation actually called, by source hash."""
    path = None
    try:
        path = inspect.getsourcefile(feature_gate)
    except Exception:                                            # pragma: no cover - defensive
        path = None
    return {"module": getattr(feature_gate, "__name__", "feature_gate"),
            "source_path": path, "source_sha256": _sha256_file(path),
            "RANK_TOL": float(getattr(feature_gate, "RANK_TOL", float("nan"))),
            "COND_MAX": float(getattr(feature_gate, "COND_MAX", float("nan"))),
            "blocking_kinds": sorted(getattr(feature_gate, "BLOCKING", set()))}


def caller_identity(explicit_path: str | Path | None = None) -> dict:
    """Identify the PRODUCER: the first frame on the stack outside this module, by source hash.

    ``explicit_path`` overrides the stack walk for callers that are generated, exec'd, or
    otherwise not on disk under their own name.
    """
    if explicit_path is not None:
        p = str(Path(explicit_path))
        return {"source_path": p, "source_sha256": _sha256_file(p),
                "function": None, "lineno": None, "resolution": "explicit"}
    try:
        for fr in inspect.stack()[1:]:
            fn = fr.filename
            if not fn:
                continue
            try:
                same = Path(fn).resolve() == _THIS_FILE
            except Exception:                                    # pragma: no cover - defensive
                same = False
            if same:
                continue
            return {"source_path": fn, "source_sha256": _sha256_file(fn),
                    "function": fr.function, "lineno": int(fr.lineno),
                    "resolution": "stack"}
    except Exception:                                            # pragma: no cover - defensive
        pass
    return {"source_path": None, "source_sha256": None, "function": None, "lineno": None,
            "resolution": "unresolved"}


def _gate_defaults() -> dict:
    sig = inspect.signature(feature_gate.audit)
    return {k: p.default for k, p in sig.parameters.items()
            if p.default is not inspect.Parameter.empty}


def _resolved_gate_thresholds(overrides: Mapping[str, float] | None) -> dict:
    """The thresholds the gate will actually use, resolved from ITS signature, not from memory."""
    d = _gate_defaults()
    out = {k: d.get(k) for k in ("corr_threshold", "target_corr_threshold",
                                 "missingness_corr_threshold")}
    for k, v in dict(overrides or {}).items():
        if k in out:
            out[k] = float(v)
    return {k: (float(v) if v is not None else None) for k, v in out.items()}


# --------------------------------------------------------------------------------------------
# findings, adjudication
# --------------------------------------------------------------------------------------------

def _finding(kind: str, **kw: Any) -> dict:
    return {"kind": kind, **kw}


def _normalise_adjudications(adj: Mapping[str, Any] | None) -> tuple[dict[str, dict], list[dict]]:
    """Adjudication keys are ``"<argument>:<kind>"`` or a bare ``"<kind>"``. A reason is mandatory."""
    norm: dict[str, dict] = {}
    bad: list[dict] = []
    for k, v in dict(adj or {}).items():
        key = str(k).strip()
        reason: Any = None
        if isinstance(v, str):
            reason = v
        elif isinstance(v, Mapping):
            reason = v.get("reason")
        if not (isinstance(reason, str) and reason.strip()):
            bad.append(_finding("adjudication_without_reason", adjudication_key=key,
                                detail="an adjudication must state a reason; it is carried in "
                                       "the record forever"))
            continue
        norm[key] = {"key": key, "reason": reason.strip()}
    return norm, bad


def _adjudication_candidates(f: Mapping[str, Any]) -> list[str]:
    kind = str(f.get("kind"))
    arg = f.get("argument")
    fold = f.get("fold")
    keys = []
    if arg is not None:
        if fold is not None:
            keys.append(f"{fold}:{arg}:{kind}")
        keys.append(f"{arg}:{kind}")
    if fold is not None:
        keys.append(f"{fold}:{kind}")
    keys.append(kind)
    return keys


def _resolve(findings: list[dict], norm: Mapping[str, dict]) -> tuple[list[dict], list[str]]:
    used: set[str] = set()
    out: list[dict] = []
    for f in findings:
        g = dict(f)
        if g["kind"] not in NON_ADJUDICABLE:
            for key in _adjudication_candidates(g):
                if key in norm:
                    g["adjudicated"] = True
                    g["adjudication_key"] = key
                    g["adjudication_reason"] = norm[key]["reason"]
                    used.add(key)
                    break
        out.append(g)
    return out, [k for k in norm if k not in used]


def _finalise(core: dict, raw: list[dict], norm: Mapping[str, dict], extra: list[dict],
              *, report_unused: bool) -> dict:
    resolved, unused = _resolve(list(extra) + list(raw), norm)
    if report_unused:
        resolved += [_finding("adjudication_unused", adjudication_key=k,
                              adjudication_reason=norm[k]["reason"],
                              detail="declared but matched no finding; it may be stale")
                     for k in unused]
    blocking = [f for f in resolved if f["kind"] in BLOCKING and not f.get("adjudicated")]
    applied = [{"kind": f["kind"], "argument": f.get("argument"), "fold": f.get("fold"),
                "adjudication_key": f["adjudication_key"],
                "adjudication_reason": f["adjudication_reason"]}
               for f in resolved if f.get("adjudicated")]
    out = dict(core)
    out.update({"findings": resolved, "blocking": blocking,
                "adjudications_declared": {k: v["reason"] for k, v in norm.items()},
                "adjudications_applied": applied,
                "n_adjudicated": len(applied), "passed": len(blocking) == 0})
    return out


# --------------------------------------------------------------------------------------------
# the design's own identity
# --------------------------------------------------------------------------------------------

def design_identity(df: pd.DataFrame, names: Sequence[str]) -> dict:
    """Digests that pin which rows and which columns, in which ORDER, the audit was about.

    Feature NAME membership and feature ORDER are digested separately. They are different facts:
    a design reordered between the fold audit and the fit has the same membership digest and a
    different order digest, and reordering matters because coefficient vectors, standardisation
    statistics and every positional consumer downstream are indexed by position.
    """
    names = [str(c) for c in names]
    idx = df.index
    present = [c for c in names if c in df.columns]
    return {"n_rows": int(len(df)), "n_features": len(names), "features": names,
            "feature_order_digest": _digest(names, "feature_order"),
            "feature_name_membership_digest": _digest(sorted(names), "feature_names"),
            "columns_digest": _digest([str(c) for c in df.columns], "columns"),
            "design_row_identity_digest": index_digest(idx, label="design_index"),
            "design_row_membership_digest": index_digest(idx, sort=True,
                                                         label="design_index_membership"),
            "index_dtype": str(idx.dtype),
            "index_is_positional": _is_positional_index(idx),
            "design_values_digest": value_digest(df[present] if present else df,
                                                 label="design_values"),
            "training_frame_digest": value_digest(df, label="training_frame")}


def _design_findings(df: Any, names: Sequence[str]) -> list[dict]:
    out: list[dict] = []
    if not isinstance(df, pd.DataFrame):
        return [_finding("argument_wrong_type", argument="design",
                         python_type=type(df).__name__,
                         detail="the design must be a pandas DataFrame")]
    names = [str(c) for c in names]
    seen: set[str] = set()
    for c in names:
        if c in seen:
            out.append(_finding("duplicate_feature_name", argument="names", feature=c,
                                detail="a repeated feature name makes the design trivially "
                                       "rank deficient and the audit ambiguous"))
        seen.add(c)
    missing = [c for c in names if c not in df.columns]
    if missing:
        out.append(_finding("feature_absent_from_design", argument="names",
                            missing_features=missing,
                            detail="feature_gate would raise KeyError; block cleanly first"))
    if _is_positional_index(df.index):
        out.append(_finding("design_index_is_positional", argument="design",
                            detail="a default 0..n-1 RangeIndex is a row NUMBER, not a row "
                                   "IDENTITY; universe checks on the arguments are correspondingly "
                                   "weaker and the receipt cannot prove which rows these were"))
    return out


# --------------------------------------------------------------------------------------------
# alignment: silent reorder blocks, explicit deterministic alignment is performed and recorded
# --------------------------------------------------------------------------------------------

def _normalise_align(align: Any) -> tuple[dict[str, str], list[dict]]:
    """``align`` is a mapping ``{argument: method}``. Nothing is aligned unless it is named."""
    out: dict[str, str] = {}
    bad: list[dict] = []
    if align is None:
        return out, bad
    if isinstance(align, str):
        bad.append(_finding("unknown_alignment_method", alignment_spec=align,
                            detail="alignment must be requested per argument, as "
                                   "{'offset': 'reindex_to_design_index'}; a blanket alignment "
                                   "is not an explicit step"))
        return out, bad
    for k, v in dict(align).items():
        key = str(k)
        method = str(v)
        if key not in ROW_ALIGNED_ARGUMENTS:
            bad.append(_finding("unknown_argument_declared", argument=key,
                                known_arguments=list(ROW_ALIGNED_ARGUMENTS),
                                detail="only the row-aligned arguments can be realigned"))
            continue
        if method not in ALIGNMENT_METHODS:
            bad.append(_finding("unknown_alignment_method", argument=key, method=method,
                                known_methods=list(ALIGNMENT_METHODS),
                                detail="an alignment this module cannot perform deterministically "
                                       "is a repair, and repairs belong in the producer"))
            continue
        out[key] = method
    return out, bad


def _apply_alignment(name: str, value: Any, df: pd.DataFrame,
                     method: str) -> tuple[Any, list[dict]]:
    """Deterministic realignment, or a blocking finding explaining why it cannot be deterministic."""
    idx = _index_of(value)
    if idx is None:
        return value, [_finding("alignment_ambiguous", argument=name, method=method,
                                detail="an object with no index cannot be reindexed; alignment "
                                       "would be a positional no-op dressed as a step")]
    if idx.has_duplicates or df.index.has_duplicates:
        return value, [_finding("alignment_ambiguous", argument=name, method=method,
                                argument_index_has_duplicates=bool(idx.has_duplicates),
                                design_index_has_duplicates=bool(df.index.has_duplicates),
                                detail="reindexing against duplicate labels is not a function; "
                                       "the result depends on which duplicate wins")]
    before_order = index_digest(idx, label=f"{name}_index")
    before_values = value_digest(value, label=f"{name}_values")
    try:
        aligned = value.reindex(df.index)
    except Exception as e:                                       # pragma: no cover - defensive
        return value, [_finding("alignment_ambiguous", argument=name, method=method,
                                error=repr(e), detail="reindex failed")]
    step = {"kind": "argument_realigned", "argument": name, "method": method,
            "index_digest_as_supplied": before_order,
            "value_digest_as_supplied": before_values,
            "index_digest_as_audited": index_digest(aligned.index, label=f"{name}_index"),
            "value_digest_as_audited": value_digest(aligned, label=f"{name}_values"),
            "detail": "an EXPLICIT deterministic alignment step, requested by the caller and "
                      "recorded here; the realigned object is what was audited and is what the "
                      "caller must fit"}
    return aligned, [step]


# --------------------------------------------------------------------------------------------
# per-argument checks
# --------------------------------------------------------------------------------------------

def _alignment_findings(name: str, value: Any, df: pd.DataFrame) -> tuple[str, list[dict]]:
    """Length, order and universe. Returns ``(status, findings)``.

    ``feature_gate`` consumes these POSITIONALLY. Anything that is not the design's own rows, in
    the design's own order, is silently audited against the wrong rows.
    """
    n_design = int(len(df))
    try:
        n_arg = int(len(value))
    except TypeError:
        return "wrong_type", [_finding("argument_wrong_type", argument=name,
                                       python_type=type(value).__name__,
                                       detail="a row-aligned argument must be sized; got an "
                                              "object with no length")]
    if n_arg != n_design:
        return "length_mismatch", [_finding(
            "argument_length_mismatch", argument=name,
            n_argument=n_arg, n_design_rows=n_design,
            detail="the gate would index mismatched rows, or numpy would broadcast silently")]

    idx = _index_of(value)
    if idx is None:
        return "row_identity_absent", [_finding(
            "argument_row_identity_absent", argument=name,
            python_type=type(value).__name__, n=n_arg,
            detail="a bare array carries no row identity, so a right-length argument drawn from "
                   "a DIFFERENT universe of rows is undetectable; pass a pandas Series indexed "
                   "on the design's index, or adjudicate with a stated reason")]

    d_idx = df.index
    if bool(d_idx.equals(idx)):
        return "identical", []
    try:
        same_members = bool(d_idx.sort_values().equals(idx.sort_values()))
    except TypeError:                                            # pragma: no cover - defensive
        same_members = (sorted(_scalar_repr(x) for x in d_idx)
                        == sorted(_scalar_repr(x) for x in idx))

    if same_members:
        diff = [int(i) for i in range(n_arg)
                if _scalar_repr(d_idx[i]) != _scalar_repr(idx[i])]
        return "misaligned", [_finding(
            "argument_misaligned", argument=name, n=n_arg,
            n_positions_differing=len(diff), first_differing_positions=diff[:8],
            design_index_digest=index_digest(d_idx),
            argument_index_digest=index_digest(idx),
            detail="same rows, different order, and no explicit alignment step was requested. "
                   "The gate reads positionally, so every correlation would be computed across "
                   "mismatched rows. NOT silently realigned: the wrapper can reindex its own "
                   "copy but not the object the caller fits, and a record about a realigned "
                   "copy is a record about a matrix nobody fits. Request "
                   "align={'%s': 'reindex_to_design_index'} to make the reorder an explicit, "
                   "recorded step" % name)]

    d_set = {_scalar_repr(x) for x in d_idx}
    a_set = {_scalar_repr(x) for x in idx}
    return "universe_mismatch", [_finding(
        "argument_universe_mismatch", argument=name, n=n_arg,
        n_shared_labels=len(d_set & a_set),
        n_only_in_argument=len(a_set - d_set),
        n_only_in_design=len(d_set - a_set),
        examples_only_in_argument=sorted(a_set - d_set)[:5],
        examples_only_in_design=sorted(d_set - a_set)[:5],
        design_index_membership_digest=index_digest(d_idx, sort=True),
        argument_index_membership_digest=index_digest(idx, sort=True),
        detail="right length, wrong rows; the lengths agree so nothing downstream raises, and "
               "the audit is evidence about somebody else's rows")]


def _placeholder_findings(name: str, value: Any, df: pd.DataFrame) -> list[dict]:
    """Refuse defaults that are indistinguishable from "not supplied".

    Each of these is formally supplied and materially absent: the check it was meant to enable
    cannot fire against it, for any design.
    """
    out: list[dict] = []

    if name == "test_df":
        if isinstance(value, pd.DataFrame) and isinstance(df, pd.DataFrame):
            same = (value is df) or (
                value.shape == df.shape
                and [str(c) for c in value.columns] == [str(c) for c in df.columns]
                and index_digest(value.index) == index_digest(df.index)
                and value_digest(value) == value_digest(df))
            if same:
                out.append(_finding("argument_is_placeholder_default", argument="test_df",
                                    placeholder="the training design itself",
                                    detail="schema_mismatch compares test columns to the declared "
                                           "features; handing the design back to itself makes it "
                                           "unfireable by construction"))
        return out

    a = _numeric(value)
    if a is None:
        return [_finding("argument_wrong_type", argument=name,
                         python_type=type(value).__name__,
                         detail="not coercible to a numeric array; the gate calls "
                                "np.asarray(x, float) on it")]

    fin = np.isfinite(a)
    if not fin.any():
        return [_finding("argument_all_non_finite", argument=name, n=int(a.size),
                         detail="every value is NaN or inf; the gate's finite masks empty out "
                                "and every check it enables is skipped")]

    if name == "outcome_mask":
        vals = _values_list(value)
        boolish = all(isinstance(x, (bool, np.bool_)) for x in vals) or (
            bool(fin.all()) and set(np.unique(a[fin]).tolist()) <= {0.0, 1.0})
        if not boolish:
            out.append(_finding("argument_not_boolean", argument=name,
                                n_non_finite=int((~fin).sum()),
                                observed_values=sorted({_scalar_repr(x) for x in vals})[:6],
                                detail="np.asarray(mask, bool) turns NaN and every non-zero float "
                                       "into True, so a non-boolean mask silently becomes a "
                                       "different mask"))
        b = np.asarray(a[fin] != 0.0, bool)
        if b.all() or (~b).all():
            out.append(_finding("argument_is_placeholder_default", argument=name,
                                placeholder="all True" if b.all() else "all False",
                                n=int(b.size),
                                detail="the exact-indicator branch computes "
                                       "off_diag = min(k, n-k) against this mask; with a constant "
                                       "mask it can never reach zero for any column that has both "
                                       "missing and observed rows, so the branch is dead while the "
                                       "record says the mask was supplied"))
        return out

    n_fin = int(fin.sum())
    if n_fin < GATE_MIN_ROWS:
        out.append(_finding("argument_insufficient_finite_rows", argument=name,
                            n_finite=n_fin, gate_minimum=GATE_MIN_ROWS,
                            detail="feature_gate skips a pairwise check when fewer than ten rows "
                                   "are jointly finite; supplied in form, absent in effect"))

    sd = float(np.std(a[fin]))
    if name == "offset":
        if float(np.max(np.abs(a[fin]))) <= 1e-12:
            out.append(_finding("argument_is_placeholder_default", argument="offset",
                                placeholder="identically zero", std=sd,
                                detail="a zero offset is arithmetically identical to passing no "
                                       "offset at all under a log link, and its zero variance "
                                       "makes deterministic_transform_of_offset unfireable "
                                       "(the gate skips when np.std(o[m]) == 0)"))
        elif sd == 0.0:
            out.append(_finding("argument_constant", argument="offset",
                                constant_value=float(a[fin][0]),
                                detail="a constant offset carries no per-row exposure; the gate "
                                       "skips the check when np.std(o[m]) == 0"))
    elif name == "target":
        if sd == 0.0:
            out.append(_finding("argument_is_placeholder_default", argument="target",
                                placeholder="constant", constant_value=float(a[fin][0]),
                                detail="target_derived, missingness_informative and the target "
                                       "branch of missingness_encodes_outcome all skip on "
                                       "np.std(y[m]) == 0; a constant target supplies the "
                                       "argument and deletes all three checks"))
    return out


def _test_df_findings(value: Any, df: Any, names: Sequence[str]) -> tuple[str, list[dict]]:
    out: list[dict] = []
    if not isinstance(value, pd.DataFrame):
        return "wrong_type", [_finding(
            "argument_wrong_type", argument="test_df", python_type=type(value).__name__,
            detail="test_df must be a pandas DataFrame; the gate reads test_df.columns")]
    if len(value) == 0:
        out.append(_finding("argument_empty", argument="test_df", n_rows=0,
                            detail="a zero-row test frame is a schema assertion about nothing"))

    # train/test schema, pre-checked here so it blocks BEFORE the gate call and before any fit.
    # This mirrors feature_gate's own schema_mismatch rule; feature_gate governs.
    missing = [str(c) for c in names if c not in value.columns]
    if missing:
        out.append(_finding("train_test_schema_mismatch", argument="test_df",
                            missing_in_test=missing,
                            detail="a declared feature is absent from the test frame; the fold "
                                   "cannot be scored on the design it was fitted on"))
    if isinstance(df, pd.DataFrame):
        train_cols = [str(c) for c in df.columns]
        test_cols = [str(c) for c in value.columns]
        if set(train_cols) != set(test_cols):
            out.append(_finding("test_frame_columns_differ", argument="test_df",
                                only_in_train=sorted(set(train_cols) - set(test_cols))[:12],
                                only_in_test=sorted(set(test_cols) - set(train_cols))[:12],
                                detail="reported, not blocking: only the declared features are "
                                       "required to be present"))
        if not _is_positional_index(df.index):
            d_set = {_scalar_repr(x) for x in df.index}
            t_set = {_scalar_repr(x) for x in value.index}
            shared = d_set & t_set
            if t_set and shared == t_set:
                out.append(_finding("test_df_overlaps_design", argument="test_df",
                                    n_test_rows=int(len(value)),
                                    n_overlapping_labels=len(shared),
                                    detail="every test row label is a training row label; this is "
                                           "not a held-out frame, and a schema check against the "
                                           "training rows cannot detect fold train/test drift"))
            elif shared:
                out.append(_finding("test_df_partially_overlaps_design", argument="test_df",
                                    n_overlapping_labels=len(shared),
                                    n_test_rows=int(len(value)),
                                    detail="some test rows are also training rows"))
    status = "held_out" if not any(f["kind"] in BLOCKING for f in out) else "rejected"
    return status, out


def _argument_record(name: str, value: Any, *, supplied: bool, null: bool,
                     not_applicable: str | None, alignment: dict | None) -> dict:
    rec: dict[str, Any] = {
        "argument": name,
        "required_because": ARGUMENT_WHY[name],
        "enables": list(ARGUMENT_ENABLES[name]),
        "supplied": bool(supplied and not null),
        "declared_not_applicable": not_applicable,
        "python_type": None, "dtype": None, "n": None,
        "value_digest": None, "index_digest": None, "index_membership_digest": None,
        "alignment": alignment or {"status": "not_evaluated", "method": None},
        "summary": None,
    }
    if not supplied or null:
        return rec
    rec["python_type"] = type(value).__name__
    rec["dtype"] = str(getattr(value, "dtype", getattr(value, "dtypes", "")))[:200] or None
    try:
        rec["n"] = int(len(value))
    except TypeError:
        rec["n"] = None
    try:
        rec["value_digest"] = value_digest(value, label=f"{name}_values")
    except Exception as e:                                       # pragma: no cover - defensive
        rec["value_digest"] = f"<undigestable: {e!r}>"
    idx = _index_of(value)
    if idx is not None:
        rec["index_digest"] = index_digest(idx, label=f"{name}_index")
        rec["index_membership_digest"] = index_digest(idx, sort=True,
                                                      label=f"{name}_index_membership")
    try:
        rec["summary"] = _summary(value)
    except Exception as e:                                       # pragma: no cover - defensive
        rec["summary"] = {"error": repr(e)}
    return rec


# --------------------------------------------------------------------------------------------
# THE DUAL FRAME -- contract §8a
#
# Everything below concerns the pair (raw frame as the producer emitted it, transformed frame as
# the fitter receives it) and the declared lineage between them. It is mandatory for every fitted
# design; there is no branch in which the wrapper decides the frame "looked clean enough".
# --------------------------------------------------------------------------------------------

def _is_supplied(v: Any) -> bool:
    return not (isinstance(v, _Unspecified) or v is None)


def _is_imputation_method(method: str) -> bool:
    m = str(method).strip().lower()
    return m.startswith(IMPUTATION_METHOD_PREFIXES) or "impute" in m


def no_transformation(description: str) -> dict:
    """The Case-1 declaration: the frame handed to the fitter IS the frame the producer emitted.

    It is an assertion, and the wrapper proves it by digest rather than believing it. Supply it
    together with ``raw_df=df`` — the same object is correct, and no copy is required.
    """
    return {"kind": "none", "description": str(description), "operations": []}


def matrix_digest(m: Any, names: Sequence[str], *, label: str = "audited_matrix") -> str | None:
    """Digest of a feature MATRIX, comparable across DataFrame and ndarray presentations.

    The point is condition 5: the matrix a receipt is about and the matrix handed to the fitter
    must be the same bytes. A caller who audits ``df`` and fits ``df[names].to_numpy()`` is
    fitting the audited matrix; a caller who audits ``df`` and fits a standardised copy is not,
    and the digest is what tells them apart.
    """
    names = [str(c) for c in names]
    try:
        if isinstance(m, pd.DataFrame):
            cols = [c for c in names if c in m.columns]
            sub = m.loc[:, cols] if len(cols) == len(names) else m
            sub = sub.copy()
            sub.columns = [str(c) for c in sub.columns]
        else:
            a = np.asarray(m)
            if a.ndim == 1:
                a = a.reshape(-1, 1)
            if a.ndim != 2:
                return None
            cols = (list(names) if a.shape[1] == len(names)
                    else [f"__col{i}__" for i in range(a.shape[1])])
            sub = pd.DataFrame(a, columns=cols)
        return value_digest(sub, label=label)
    except Exception:                                            # pragma: no cover - defensive
        return None


def _spec_digest(spec: Any) -> str | None:
    if spec is None:
        return None
    try:
        payload = json.dumps(spec, sort_keys=True, default=str)
    except Exception:                                            # pragma: no cover - defensive
        payload = repr(spec)
    return "transformation:sha256=" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalise_transformation(spec: Any) -> tuple[dict | None, list[dict]]:
    """Parse and validate a transformation declaration. Returns ``(normalised_or_None, findings)``.

    A declaration is not a label. Every operation must name its columns, its method, a stated
    reason, and must assert ``cutoff_valid=True`` — the gate cannot verify cutoff validity (see
    contract §7, construction-time provenance is a producer obligation) but it can refuse to
    proceed without the assertion, and it binds the assertion into the receipt forever.
    """
    if spec is None:
        return None, []
    if not isinstance(spec, Mapping):
        return None, [_finding(
            "transformation_declaration_malformed", python_type=type(spec).__name__,
            detail="the transformation must be a mapping carrying 'kind' and 'operations'; a bare "
                   "label names a transformation without declaring one")]

    bad: list[dict] = []
    kind = spec.get("kind")
    if not (isinstance(kind, str) and kind.strip() in TRANSFORMATION_KINDS):
        bad.append(_finding("transformation_declaration_malformed", field="kind",
                            supplied=kind, known_kinds=list(TRANSFORMATION_KINDS),
                            detail="kind must be one of %s; 'none' asserts the fitted frame IS "
                                   "the producer's frame and is then proven by digest"
                                   % (TRANSFORMATION_KINDS,)))
        kind = None
    else:
        kind = kind.strip()

    desc = spec.get("description")
    if not (isinstance(desc, str) and desc.strip()):
        bad.append(_finding("transformation_declaration_malformed", field="description",
                            detail="a transformation declaration carries a stated description; it "
                                   "is carried in the record forever"))

    ops_in = spec.get("operations", [])
    if ops_in is None:
        ops_in = []
    if isinstance(ops_in, (str, bytes)) or not isinstance(ops_in, Sequence):
        bad.append(_finding("transformation_declaration_malformed", field="operations",
                            python_type=type(ops_in).__name__,
                            detail="operations must be a list of operation mappings"))
        ops_in = []

    ops: list[dict] = []
    for i, op in enumerate(ops_in):
        if not isinstance(op, Mapping):
            bad.append(_finding("transformation_declaration_malformed", operation_index=i,
                                python_type=type(op).__name__,
                                detail="every operation must be a mapping"))
            continue
        problems: list[str] = []
        cols = op.get("columns")
        if isinstance(cols, (str, bytes)) or not isinstance(cols, Sequence) or not len(cols):
            problems.append("columns")
        method = op.get("method")
        if not (isinstance(method, str) and method.strip()):
            problems.append("method")
        reason = op.get("reason")
        if not (isinstance(reason, str) and reason.strip()):
            problems.append("reason")
        if op.get("cutoff_valid") is not True:
            problems.append("cutoff_valid")
        if problems:
            bad.append(_finding(
                "transformation_declaration_malformed", operation_index=i,
                malformed_fields=problems, required_fields=list(OPERATION_REQUIRED_FIELDS),
                detail="an operation missing any of these is a name for a transformation rather "
                       "than a declaration of one; cutoff_valid must be asserted explicitly"))
            continue
        ops.append({
            "columns": [str(c) for c in cols],
            "method": str(method).strip(),
            "reason": str(reason).strip(),
            "cutoff_valid": True,
            "value": op.get("value"),
            "frozen_parameters": op.get("frozen_parameters"),
            "fitted_on_row_universe_digest": op.get("fitted_on_row_universe_digest"),
            "applied_to_test_frame": bool(op.get("applied_to_test_frame", False)),
            "imputes_missing": _is_imputation_method(str(method)),
        })

    def _authorisations(field: str) -> list[dict]:
        got = spec.get(field) or []
        if isinstance(got, (str, bytes)) or not isinstance(got, Sequence):
            bad.append(_finding("transformation_declaration_malformed", field=field,
                                detail="%s must be a list of authorisation mappings" % field))
            return []
        out = []
        for j, a in enumerate(got):
            if not (isinstance(a, Mapping) and isinstance(a.get("reason"), str)
                    and a["reason"].strip() and a.get("cutoff_valid") is True):
                bad.append(_finding("transformation_declaration_malformed", field=field,
                                    operation_index=j,
                                    detail="an authorisation must state a reason and assert "
                                           "cutoff_valid=True"))
                continue
            out.append({"kind": str(a.get("kind") or field), "reason": a["reason"].strip(),
                        "cutoff_valid": True})
        return out

    row_ops = _authorisations("row_operations")
    col_ops = _authorisations("column_operations")

    if kind == "none" and ops:
        bad.append(_finding("transformation_declaration_malformed", field="operations",
                            n_operations=len(ops),
                            detail="kind 'none' asserts that nothing happened between the two "
                                   "frames; it cannot also declare operations"))
    if kind in ("imputation", "transformation") and not ops:
        bad.append(_finding("transformation_declaration_malformed", field="operations",
                            transformation_kind=kind,
                            detail="a transformation was declared but no operation describes it"))

    norm = {"kind": kind, "description": (desc.strip() if isinstance(desc, str) else None),
            "operations": ops, "n_operations": len(ops),
            "row_operations": row_ops, "column_operations": col_ops,
            "declared_columns": sorted({c for o in ops for c in o["columns"]})}
    return (None if bad else norm), bad


def _missingness_profile(frame: Any, names: Sequence[str],
                         outcome_mask: Any = None) -> dict:
    """Per-column null-mask digests and their relation to the outcome mask.

    The digest is the evidence the contract asks for ("raw missingness-mask digest, per column").
    ``off_diagonal_rows`` mirrors ``feature_gate``'s own exact-indicator arithmetic so the record
    carries the number, not just the verdict.
    """
    out: dict[str, Any] = {"per_column": {}, "n_missing_cells": None, "columns_with_missing": []}
    if not isinstance(frame, pd.DataFrame):
        return out
    om = None
    if outcome_mask is not None:
        try:
            om = np.asarray(_values_list(outcome_mask), dtype=bool)
        except Exception:                                        # pragma: no cover - defensive
            om = None
    total = 0
    for c in [str(x) for x in names]:
        if c not in frame.columns:
            continue
        miss = frame[c].isna().to_numpy()
        n_miss = int(miss.sum())
        total += n_miss
        rec: dict[str, Any] = {
            "missing_mask_digest": _digest([("1" if b else "0") for b in miss.tolist()],
                                           f"missing_mask[{c}]"),
            "n_missing": n_miss, "n_rows": int(miss.size),
            "missing_rate": round(n_miss / miss.size, 8) if miss.size else None,
            "off_diagonal_rows": None, "is_exact_outcome_indicator": None}
        if om is not None and om.size == miss.size and 0 < n_miss < miss.size:
            off = int(np.sum(miss & om) + np.sum(~miss & ~om))
            off = min(off, int(miss.size) - off)
            rec["off_diagonal_rows"] = off
            rec["is_exact_outcome_indicator"] = bool(off == 0)
        out["per_column"][c] = rec
        if n_miss:
            out["columns_with_missing"].append(c)
    out["n_missing_cells"] = total
    per = out["per_column"]
    out["aggregate_digest"] = _digest(
        [f"{c}={per[c]['missing_mask_digest']}" for c in sorted(per)], "missingness")
    return out


def _outcome_separating_values(frame: pd.DataFrame, names: Sequence[str], outcome_mask: Any,
                               fill_values: Mapping[str, set]) -> tuple[list[dict], list[dict]]:
    """Does a VALUE in the transformed frame do the work the null mask used to do?

    ws2 stated as a property of the values: ``transfer_direct`` is zero on every one of the 8,278
    non-appearers and non-zero on 25,522 appearers, so a non-zero value certifies appearance. The
    criterion is exactly that one-directional shape — a value carried by EVERY row on one side of
    the outcome mask and absent from at least one row on the other — which is strictly weaker than
    an exact indicator and is what survives a partial fill.

    Candidate values are the caller's declared fill constants, plus ``0.0``, plus the three most
    frequent repeated values of the column. Anything rarer than ``GATE_MIN_ROWS`` is not a fill.
    """
    analysis: list[dict] = []
    findings: list[dict] = []
    if not isinstance(frame, pd.DataFrame) or outcome_mask is None:
        return analysis, findings
    try:
        om = np.asarray(_values_list(outcome_mask), dtype=bool)
    except Exception:                                            # pragma: no cover - defensive
        return analysis, findings
    if om.size != len(frame):
        return analysis, findings
    neg = ~om
    if int(om.sum()) < GATE_MIN_ROWS or int(neg.sum()) < GATE_MIN_ROWS:
        return analysis, findings

    for c in [str(x) for x in names]:
        if c not in frame.columns:
            continue
        a = _numeric(frame[c])
        if a is None or a.size != om.size:
            continue
        vc = pd.Series(a).value_counts(dropna=True)
        cands: list[float] = [float(v) for v, k in vc.items() if int(k) >= GATE_MIN_ROWS][:3]
        for v in sorted(fill_values.get(c, set())):
            if v not in cands:
                cands.append(float(v))
        if 0.0 not in cands and int((a == 0.0).sum()) >= GATE_MIN_ROWS:
            cands.append(0.0)
        for v in cands:
            is_v = (a == v)
            n_v = int(is_v.sum())
            if n_v == 0 or n_v == a.size:
                continue
            for side, held, other in (("outcome_negative", neg, om),
                                      ("outcome_positive", om, neg)):
                if bool(is_v[held].all()) and bool((~is_v[other]).any()):
                    rec = {"feature": c, "value": float(v), "side_carrying_value": side,
                           "n_rows_with_value": n_v,
                           "n_rows_on_that_side": int(held.sum()),
                           "n_other_side_without_value": int((~is_v[other]).sum()),
                           "n_other_side_with_value": int(is_v[other].sum())}
                    analysis.append(rec)
                    findings.append(_finding(
                        "value_pattern_encodes_outcome", **rec,
                        detail="every %s row carries the value %r in this column and %d rows on "
                               "the other side do not, so a value OTHER than %r certifies the "
                               "outcome. This is the ws2 shape read off the transformed frame: a "
                               "null mask that encoded the outcome survives the fill as an "
                               "ordinary number, and missingness_encodes_outcome cannot fire on a "
                               "frame with no missingness"
                               % (side, float(v), int((~is_v[other]).sum()), float(v))))
                    break
    return analysis, findings


def _verify_provenance(provenance: Any, identity: Mapping[str, Any],
                       raw_row_membership_digest: str | None) -> tuple[dict, list[dict]]:
    """Bind the frame called "raw" to the producer that emitted it, or block the claim.

    A caller naming a matrix "raw" is a claim about lineage, and this module's whole subject is
    claims that cannot be checked. What CAN be checked here is checked: the producer source is
    hashed off disk, declared hashes are recompared against the files, and the declared row
    universe is recompared against the frame actually supplied. A claim that fails any of these
    blocks (``producer_provenance_unverifiable``). No claim at all does not block — it caps the
    assurance level at ``RAW_PROVENANCE_ASSERTED``, which is a recorded fact, not a silent one.
    """
    rec: dict[str, Any] = {
        "claimed": provenance is not None, "verified": False,
        "producer_source_path": None, "producer_source_sha256": None,
        "input_manifest": {}, "feature_construction_receipt": None,
        "feature_construction_receipt_sha256": None,
        "row_universe_digest_declared": None, "row_universe_digest_matches": None,
        "row_universe_digest_recomputed": raw_row_membership_digest,
        "provenance_digest": None, "problems": [],
        "note": "this repository has no feature-construction receipt or input manifest wired into "
                "the producers; a caller who does not supply provenance= reaches "
                "RAW_PROVENANCE_ASSERTED and no higher"}
    if provenance is None:
        return rec, []
    if not isinstance(provenance, Mapping):
        rec["problems"] = ["provenance:not_a_mapping"]
        return rec, [_finding("producer_provenance_unverifiable",
                              python_type=type(provenance).__name__,
                              problems=rec["problems"],
                              detail="provenance must be a mapping naming the producer source, "
                                     "its inputs and the row universe it emitted")]

    problems: list[str] = []

    p = provenance.get("producer_source_path")
    if not (isinstance(p, str) and p.strip()):
        problems.append("producer_source_path:absent")
    else:
        rec["producer_source_path"] = p
        h = _sha256_file(p)
        rec["producer_source_sha256"] = h
        if h is None:
            problems.append("producer_source_path:unreadable")
        else:
            declared = provenance.get("producer_source_sha256")
            if isinstance(declared, str) and declared.strip() and declared.strip() != h:
                problems.append("producer_source_sha256:mismatch")

    man = provenance.get("input_manifest") or {}
    if isinstance(man, Mapping):
        items = list(man.items())
    elif isinstance(man, Sequence) and not isinstance(man, (str, bytes)):
        items = [(x, None) for x in man]
    else:
        items = []
        problems.append("input_manifest:not_a_mapping_or_list")
    for path, declared in items:
        h = _sha256_file(path)
        rec["input_manifest"][str(path)] = h
        if h is None:
            problems.append(f"input_manifest:{path}:unreadable")
        elif isinstance(declared, str) and declared.strip() and declared.strip() != h:
            problems.append(f"input_manifest:{path}:mismatch")

    fcr = provenance.get("feature_construction_receipt")
    if fcr is not None:
        rec["feature_construction_receipt"] = str(fcr)
        h = _sha256_file(fcr)
        rec["feature_construction_receipt_sha256"] = h
        if h is None:
            problems.append("feature_construction_receipt:unreadable")

    rud = provenance.get("row_universe_digest")
    if not (isinstance(rud, str) and rud.strip()):
        problems.append("row_universe_digest:absent")
    else:
        rec["row_universe_digest_declared"] = rud
        rec["row_universe_digest_matches"] = bool(rud == raw_row_membership_digest)
        if not rec["row_universe_digest_matches"]:
            problems.append("row_universe_digest:mismatch")

    for key in ("experiment", "arm"):
        v = provenance.get(key)
        if v is not None and str(v) != str(identity.get(key)):
            problems.append(f"{key}:mismatch")

    rec["problems"] = problems
    rec["verified"] = not problems
    rec["provenance_digest"] = "provenance:sha256=" + hashlib.sha256(
        json.dumps({k: rec[k] for k in ("producer_source_sha256", "input_manifest",
                                        "feature_construction_receipt_sha256",
                                        "row_universe_digest_declared")},
                   sort_keys=True, default=str).encode("utf-8")).hexdigest()
    if problems:
        return rec, [_finding(
            "producer_provenance_unverifiable", problems=problems,
            producer_source_path=rec["producer_source_path"],
            row_universe_digest_declared=rec["row_universe_digest_declared"],
            row_universe_digest_recomputed=raw_row_membership_digest,
            detail="producer provenance was CLAIMED and could not be verified. An unverifiable "
                   "claim is worse than no claim: it is the appearance of lineage without the "
                   "lineage, which is the whole subject of this module")]
    return rec, []


def dual_frame_identity(df: Any, names: Sequence[str], raw_df: Any = UNSPECIFIED,
                        transformation: Any = None, fitted_matrix: Any = UNSPECIFIED,
                        outcome_mask: Any = None) -> dict:
    """Digests ONLY, no findings. Shared by ``_invoke`` and ``verify_receipt``.

    Keeping identity separate from judgement is what lets ``verify_receipt`` recompute a receipt's
    dual-frame binding from the inputs presented and detect a receipt carried across to a
    different raw frame or a different transformation specification.
    """
    names = [str(c) for c in names]
    raw_ok = _is_supplied(raw_df) and isinstance(raw_df, pd.DataFrame)
    df_ok = isinstance(df, pd.DataFrame)
    out: dict[str, Any] = {
        "raw_frame_supplied": bool(_is_supplied(raw_df)),
        "raw_frame_is_frame": bool(raw_ok),
        "raw_frame_is_same_object": bool(raw_ok and df_ok and raw_df is df),
        "raw_frame_values_digest": None,
        "raw_row_identity_digest": None,
        "raw_row_membership_digest": None,
        "raw_feature_order_digest": None,
        "raw_columns_digest": None,
        "raw_missingness": {},
        "raw_missingness_digest": None,
        "raw_n_rows": int(len(raw_df)) if raw_ok else None,
        "transformation_declared": transformation is not None,
        "transformation_kind": None,
        "transformation_spec_digest": _spec_digest(transformation),
        "transformed_feature_order_digest": None,
        "transformed_missingness": {},
        "transformed_missingness_digest": None,
        "audited_matrix_digest": matrix_digest(df, names) if df_ok else None,
        "fitted_matrix_declared": bool(_is_supplied(fitted_matrix)),
        "fitted_matrix_digest": None,
        "frames_identical": None,
    }
    if isinstance(transformation, Mapping):
        k = transformation.get("kind")
        out["transformation_kind"] = str(k) if isinstance(k, str) else None

    if df_ok:
        out["transformed_feature_order_digest"] = _digest(
            [str(c) for c in df.columns if str(c) in set(names)], "feature_order_in_frame")
        prof = _missingness_profile(df, names, outcome_mask)
        out["transformed_missingness"] = prof
        out["transformed_missingness_digest"] = prof.get("aggregate_digest")

    if raw_ok:
        out["raw_row_identity_digest"] = index_digest(raw_df.index, label="raw_index")
        out["raw_row_membership_digest"] = index_digest(raw_df.index, sort=True,
                                                        label="raw_index_membership")
        out["raw_columns_digest"] = _digest([str(c) for c in raw_df.columns], "raw_columns")
        out["raw_feature_order_digest"] = _digest(
            [str(c) for c in raw_df.columns if str(c) in set(names)], "feature_order_in_frame")
        present = [c for c in names if c in raw_df.columns]
        if len(present) == len(names):
            out["raw_frame_values_digest"] = matrix_digest(raw_df, names)
        prof = _missingness_profile(raw_df, names, outcome_mask)
        out["raw_missingness"] = prof
        out["raw_missingness_digest"] = prof.get("aggregate_digest")
        out["frames_identical"] = bool(
            out["raw_frame_values_digest"] is not None
            and out["raw_frame_values_digest"] == out["audited_matrix_digest"]
            and out["raw_row_identity_digest"] == (index_digest(df.index, label="raw_index")
                                                   if df_ok else None))

    out["fitted_matrix_digest"] = (matrix_digest(fitted_matrix, names)
                                   if _is_supplied(fitted_matrix)
                                   else out["audited_matrix_digest"])
    return out


def _reconcile_frames(raw_df: pd.DataFrame, df: pd.DataFrame, names: Sequence[str],
                      norm: Mapping[str, Any] | None) -> tuple[dict, list[dict], Any]:
    """Row and column reconciliation. Returns ``(record, findings, raw_frame_to_audit_or_None)``.

    A row universe that differs, or a column set that was added to, removed from or reordered, is
    a transformation whether or not the caller called it one. It is allowed only when the
    declaration authorises it explicitly, and the surviving rows are what the raw audit then runs
    on, so the audit is about the rows that were actually fitted.
    """
    names = [str(c) for c in names]
    kind = (norm or {}).get("kind")
    row_authorised = bool((norm or {}).get("row_operations"))
    col_authorised = bool((norm or {}).get("column_operations"))
    findings: list[dict] = []
    rec: dict[str, Any] = {"rows": None, "columns": None, "n_rows_raw": int(len(raw_df)),
                           "n_rows_transformed": int(len(df)), "n_rows_dropped": 0,
                           "features_absent_from_raw": [], "columns_only_in_raw": [],
                           "columns_only_in_transformed": [], "feature_order_reconciles": None,
                           "columns_changed": [], "columns_unchanged": [],
                           "undeclared_changed_columns": [],
                           "declared_columns_with_no_effect": []}

    # ---- rows ------------------------------------------------------------------------------
    raw_for_audit: Any = None
    if raw_df.index.equals(df.index):
        rec["rows"] = "identical"
        raw_for_audit = raw_df
    else:
        d_set = {_scalar_repr(x) for x in df.index}
        r_set = {_scalar_repr(x) for x in raw_df.index}
        subset = d_set <= r_set and not df.index.has_duplicates and not raw_df.index.has_duplicates
        if subset and row_authorised:
            rec["rows"] = "authorised_subset"
            rec["n_rows_dropped"] = len(r_set) - len(d_set)
            findings.append(_finding(
                "authorised_row_operation", n_rows_dropped=rec["n_rows_dropped"],
                authorisations=[a["reason"] for a in (norm or {}).get("row_operations", [])],
                detail="the fitted rows are a declared subset of the producer's rows; the raw "
                       "audit runs on exactly the surviving rows so it is about the rows fitted"))
            try:
                raw_for_audit = raw_df.loc[df.index]
            except Exception:                                    # pragma: no cover - defensive
                raw_for_audit = None
        else:
            same_members = (d_set == r_set)
            rec["rows"] = ("order" if same_members else
                           ("subset" if subset else "universe"))
            findings.append(_finding(
                "raw_transformed_row_identity_mismatch", relation=rec["rows"],
                n_rows_raw=int(len(raw_df)), n_rows_transformed=int(len(df)),
                n_only_in_raw=len(r_set - d_set), n_only_in_transformed=len(d_set - r_set),
                row_operations_declared=row_authorised,
                detail="the raw and fitted frames are not about the same rows, and no row "
                       "operation authorises the difference. A raw audit run against a different "
                       "row universe is evidence about somebody else's rows, which is the failure "
                       "this module exists to refuse"))

    # ---- columns ---------------------------------------------------------------------------
    raw_cols = [str(c) for c in raw_df.columns]
    tr_cols = [str(c) for c in df.columns]
    absent = [c for c in names if c not in raw_cols]
    rec["features_absent_from_raw"] = absent
    rec["columns_only_in_raw"] = sorted(set(raw_cols) - set(tr_cols))
    rec["columns_only_in_transformed"] = sorted(set(tr_cols) - set(raw_cols))
    raw_order = [c for c in raw_cols if c in set(names)]
    tr_order = [c for c in tr_cols if c in set(names)]
    rec["feature_order_reconciles"] = bool(raw_order == tr_order)

    declared_cols = set((norm or {}).get("declared_columns") or [])
    if absent:
        constructed_and_declared = set(absent) <= declared_cols
        if col_authorised or constructed_and_declared:
            rec["columns"] = "authorised_construction"
            findings.append(_finding(
                "authorised_column_operation", features_absent_from_raw=absent,
                detail="these features do not exist in the producer's frame and their "
                       "construction is declared; the raw audit is restricted to the features "
                       "that do exist there"))
        else:
            rec["columns"] = "features_absent_from_raw"
            findings.append(_finding(
                "raw_transformed_column_mismatch", relation="added",
                features_absent_from_raw=absent,
                detail="a fitted feature does not exist in the frame presented as raw and no "
                       "operation declares its construction; columns added without a declared "
                       "transformation are exactly the pre-gate construction step §8a forbids"))
    else:
        rec["columns"] = "reconciled"

    if not rec["feature_order_reconciles"] and not col_authorised:
        findings.append(_finding(
            "raw_transformed_column_mismatch", relation="reordered",
            raw_feature_order=raw_order[:12], transformed_feature_order=tr_order[:12],
            detail="the declared features appear in a different order in the two frames and no "
                   "column operation authorises the reorder; every positional consumer downstream "
                   "is indexed by position"))
    if kind == "none" and set(raw_cols) != set(tr_cols):
        findings.append(_finding(
            "raw_transformed_column_mismatch", relation="column_set_differs_under_kind_none",
            only_in_raw=rec["columns_only_in_raw"][:12],
            only_in_transformed=rec["columns_only_in_transformed"][:12],
            detail="kind 'none' asserts the two frames are the same frame; they do not even carry "
                   "the same columns"))
    elif set(raw_cols) != set(tr_cols):
        findings.append(_finding("raw_frame_columns_differ",
                                 only_in_raw=rec["columns_only_in_raw"][:12],
                                 only_in_transformed=rec["columns_only_in_transformed"][:12],
                                 detail="reported, not blocking: a producer frame may legitimately "
                                        "carry columns the design does not declare"))

    # ---- per-column change, only meaningful when the rows line up ---------------------------
    if rec["rows"] in ("identical", "authorised_subset") and raw_for_audit is not None:
        for c in names:
            if c not in raw_for_audit.columns or c not in df.columns:
                continue
            same = (value_digest(raw_for_audit[c], label="col")
                    == value_digest(df[c], label="col"))
            (rec["columns_unchanged"] if same else rec["columns_changed"]).append(c)
        for c in rec["columns_changed"]:
            if c not in declared_cols:
                rec["undeclared_changed_columns"].append(c)
        rec["declared_columns_with_no_effect"] = sorted(
            declared_cols & set(rec["columns_unchanged"]))
        if rec["undeclared_changed_columns"]:
            findings.append(_finding(
                "column_transformation_undeclared",
                columns=sorted(rec["undeclared_changed_columns"]),
                declared_columns=sorted(declared_cols),
                detail="these columns hold different values in the fitted frame than in the "
                       "producer's frame and no declared operation names them. An undeclared "
                       "value change between the audited frame and the fitted frame is the ws2 "
                       "step itself"))
        if rec["declared_columns_with_no_effect"]:
            findings.append(_finding(
                "declared_transformation_had_no_effect",
                columns=rec["declared_columns_with_no_effect"],
                detail="reported, not blocking: a declared operation left these columns "
                       "byte-identical, so the declaration may be stale"))

    return rec, findings, raw_for_audit


def _imputation_obligations(raw_for_audit: Any, df: Any, names: Sequence[str],
                            norm: Mapping[str, Any] | None,
                            design_row_membership_digest: str | None) -> list[dict]:
    """Condition 3, and the cutoff obligations §5 puts on a legitimate imputation.

    An operation that says it fills missing values in a column that has none in the frame
    presented as raw is not describing this pair of frames: either the fill happened before the
    frame was handed over — so the raw audit never saw the null mask, which is the whole point —
    or the declaration is false. Both block, and they block for the same reason.
    """
    out: list[dict] = []
    if not (norm and isinstance(raw_for_audit, pd.DataFrame)):
        return out
    names_set = {str(c) for c in names}
    for i, op in enumerate(norm.get("operations", [])):
        unknown = [c for c in op["columns"] if c not in names_set]
        if unknown:
            out.append(_finding(
                "transformation_declaration_malformed", operation_index=i,
                unknown_columns=unknown, declared_features=sorted(names_set),
                detail="the operation names columns that are not declared features of this "
                       "design; a typo'd declaration is indistinguishable from an absent one"))
        if op["imputes_missing"]:
            no_nulls = [c for c in op["columns"]
                        if c in raw_for_audit.columns
                        and int(raw_for_audit[c].isna().sum()) == 0]
            if no_nulls:
                out.append(_finding(
                    "imputation_precedes_raw_audit", operation_index=i,
                    method=op["method"], columns=no_nulls,
                    detail="this operation fills missing values in columns that have NO missing "
                           "values in the frame presented as raw. Either the fill already "
                           "happened before that frame was produced — so the raw audit never saw "
                           "the null mask, which is exactly the ws2 defect — or the declaration "
                           "does not describe these frames"))
        d = op.get("fitted_on_row_universe_digest")
        if isinstance(d, str) and d.strip() and design_row_membership_digest is not None:
            if d.strip() != design_row_membership_digest:
                out.append(_finding(
                    "imputation_rule_fitted_off_training_rows", operation_index=i,
                    declared=d.strip(), training_row_membership_digest=design_row_membership_digest,
                    detail="the imputation rule declares that it was fitted on a row universe "
                           "that is not this fold's training rows; a fill constant learned off "
                           "the training rows carries information the fold does not have"))
    return out


def _conversion_findings(raw_audit: Mapping[str, Any] | None, ident: Mapping[str, Any],
                         names: Sequence[str]) -> list[dict]:
    """Condition 6. Raw-blocks-plus-transformed-clean is the signature.

    Two independent sources are unioned so neither can be silently disabled: ``feature_gate``'s
    own verdict on the RAW frame, and this module's per-column off-diagonal count against the
    outcome mask.
    """
    out: list[dict] = []
    raw_prof = dict((ident.get("raw_missingness") or {}).get("per_column") or {})
    tr_prof = dict((ident.get("transformed_missingness") or {}).get("per_column") or {})

    flagged: dict[str, str] = {}
    for f in list((raw_audit or {}).get("findings", [])):
        if f.get("kind") in ("missingness_encodes_outcome", "missingness_informative"):
            feat = str(f.get("feature") or "")
            if feat:
                flagged[feat] = str(f.get("kind"))
    for c, rec in raw_prof.items():
        if rec.get("is_exact_outcome_indicator"):
            flagged.setdefault(c, "exact_outcome_indicator_off_diagonal_zero")

    for c in [str(x) for x in names]:
        if c not in flagged:
            continue
        n_raw = int((raw_prof.get(c) or {}).get("n_missing") or 0)
        n_tr = int((tr_prof.get(c) or {}).get("n_missing") or 0)
        if n_raw and n_tr < n_raw:
            out.append(_finding(
                "missingness_mask_converted_to_values", feature=c, source=flagged[c],
                n_missing_raw=n_raw, n_missing_transformed=n_tr,
                n_nulls_filled=n_raw - n_tr,
                off_diagonal_rows=(raw_prof.get(c) or {}).get("off_diagonal_rows"),
                raw_missing_mask_digest=(raw_prof.get(c) or {}).get("missing_mask_digest"),
                detail="the RAW null mask of this column is outcome-associated and the fitted "
                       "frame has fewer nulls in it, so the mask was converted into ordinary "
                       "numeric values. missingness_encodes_outcome cannot fire on the fitted "
                       "frame because there is no missingness left to fire on; this is the ws2 "
                       "class and it is not adjudicable"))
    return out


def _dual_frame_structure(df: Any, names: Sequence[str], raw_df: Any, transformation: Any,
                          provenance: Any, fitted_matrix: Any, identity: Mapping[str, Any],
                          ident: Mapping[str, Any],
                          design_row_membership_digest: str | None) -> tuple[list[dict], dict, Any]:
    """Everything about the pair of frames that is decidable WITHOUT calling the gate."""
    findings: list[dict] = []
    norm, spec_bad = normalise_transformation(transformation)
    findings += spec_bad

    raw_supplied = _is_supplied(raw_df)
    declared = transformation is not None
    kind = (norm or {}).get("kind") or ident.get("transformation_kind")

    rec: dict[str, Any] = {
        "policy": "MANDATORY for every fitted feature design (contract §8a); it is never "
                  "conditional on a transformation being declared or detected, because a fully "
                  "populated transformed frame cannot reveal that a raw frame was withheld",
        "case": None,
        "transformation_kind": kind,
        "raw_frame_supplied": bool(raw_supplied),
        "transformation_declared": bool(declared),
        "transformation": norm,
        "identity": dict(ident),
        "reconciliation": None,
        "raw_audit": None,
        "raw_gate_invoked": False,
        "value_pattern_analysis": [],
        "fitted_matrix": {"declared": bool(ident.get("fitted_matrix_declared")),
                          "digest": ident.get("fitted_matrix_digest"),
                          "audited_matrix_digest": ident.get("audited_matrix_digest"),
                          "matches": None},
        "provenance": None,
        "assurance": None,
        "stage1_pass": False,
    }

    if not raw_supplied:
        findings.append(_finding(
            "raw_frame_absent",
            detail="no pre-transformation frame was supplied. The dual frame is mandatory for "
                   "every fitted design and is not conditional on a transformation being declared "
                   "or detected: a fully populated transformed frame cannot reveal that a raw "
                   "frame was withheld, which is precisely the failure class §8a closes. If no "
                   "transformation occurred, pass raw_df=df with "
                   "transformation=no_transformation(reason); the same object is correct and no "
                   "copy is required"))
    elif not isinstance(raw_df, pd.DataFrame):
        findings.append(_finding("argument_wrong_type", argument="raw_df",
                                 python_type=type(raw_df).__name__,
                                 detail="the raw frame must be a pandas DataFrame"))
    if not declared:
        findings.append(_finding(
            "transformation_undeclared",
            detail="no transformation specification was declared. Either a transformation "
                   "occurred and is undeclared, or none did and that must be asserted as "
                   "kind 'none' and proven by digest; silence is not one of the two cases"))

    prov, prov_findings = _verify_provenance(provenance, identity,
                                             ident.get("raw_row_membership_digest"))
    rec["provenance"] = prov
    findings += prov_findings
    if provenance is None:
        findings.append(_finding(
            "raw_provenance_asserted_not_verified",
            detail="the frame presented as raw is caller-asserted: no producer source, input "
                   "manifest or feature-construction receipt was supplied, so its lineage cannot "
                   "be demonstrated independently. Recorded, not blocking, and it caps the "
                   "assurance level at RAW_PROVENANCE_ASSERTED rather than silently granting the "
                   "assurance of a producer-backed frame"))

    raw_for_audit: Any = None
    if raw_supplied and isinstance(raw_df, pd.DataFrame) and isinstance(df, pd.DataFrame):
        if ident.get("raw_frame_is_same_object"):
            findings.append(_finding(
                "raw_frame_is_the_fitted_frame",
                detail="the raw frame and the fitted frame are the same object; this is the "
                       "correct Case-1 form and no copy is required. Identity is still proven by "
                       "digest below rather than inferred from object identity"))
        recon, recon_findings, raw_for_audit = _reconcile_frames(raw_df, df, names, norm)
        rec["reconciliation"] = recon
        findings += recon_findings
        findings += _imputation_obligations(raw_for_audit, df, names, norm,
                                            design_row_membership_digest)

        identical = bool(ident.get("frames_identical"))
        if kind == "none":
            rec["case"] = "identity"
            if not identical:
                findings.append(_finding(
                    "declared_identity_contradicted",
                    raw_frame_values_digest=ident.get("raw_frame_values_digest"),
                    audited_matrix_digest=ident.get("audited_matrix_digest"),
                    raw_row_identity_digest=ident.get("raw_row_identity_digest"),
                    n_columns_changed=len(recon.get("columns_changed") or []),
                    columns_changed=sorted(recon.get("columns_changed") or [])[:12],
                    detail="the caller declared transformation kind 'none' and the two frames are "
                           "not identical. A transformation occurred; it must be specified"))
        elif kind in ("imputation", "transformation"):
            rec["case"] = "transformation"
            if not ident.get("fitted_matrix_declared"):
                findings.append(_finding(
                    "fitted_matrix_undeclared",
                    detail="a transformation was performed, so the exact matrix handed to the "
                           "fitter must be declared and digested. Without it the receipt is about "
                           "a frame and the fit is about a matrix, and nothing connects them"))
        if ident.get("fitted_matrix_declared"):
            same = (ident.get("fitted_matrix_digest") == ident.get("audited_matrix_digest"))
            rec["fitted_matrix"]["matches"] = bool(same)
            if not same:
                findings.append(_finding(
                    "audited_matrix_is_not_the_fitted_matrix",
                    audited_matrix_digest=ident.get("audited_matrix_digest"),
                    fitted_matrix_digest=ident.get("fitted_matrix_digest"),
                    detail="the matrix declared as the one handed to the fitter is not the matrix "
                           "this record audits. A gate record about a matrix nobody fits is the "
                           "precise failure contract §1 exists to forbid"))
    return findings, rec, raw_for_audit


def _assurance_level(case: str | None, provenance_verified: bool, blocking: Sequence) -> str:
    if blocking:
        return "FAILED"
    if not provenance_verified:
        return "RAW_PROVENANCE_ASSERTED"
    if case == "identity":
        return "IDENTITY_VERIFIED"
    if case == "transformation":
        return "TRANSFORMATION_VERIFIED"
    return "RAW_PROVENANCE_ASSERTED"                             # pragma: no cover - defensive


def _blocking_after_adjudication(findings: Sequence[Mapping[str, Any]],
                                 norm: Mapping[str, dict]) -> list[dict]:
    resolved, _ = _resolve([dict(f) for f in findings], norm)
    return [f for f in resolved if f["kind"] in BLOCKING and not f.get("adjudicated")]


# --------------------------------------------------------------------------------------------
# the receipt binding -- what makes a receipt un-reusable
# --------------------------------------------------------------------------------------------

#: the dual-frame facts a receipt is bound to. Present a receipt alongside a different raw frame,
#: a different transformation specification, a different producer or a different fitted matrix and
#: the recomputed binding diverges.
DUAL_BINDING_FIELDS: tuple[str, ...] = (
    "raw_frame_supplied", "raw_frame_values_digest", "raw_row_identity_digest",
    "raw_row_membership_digest", "raw_feature_order_digest", "raw_columns_digest",
    "raw_missingness_digest", "transformation_declared", "transformation_kind",
    "transformation_spec_digest", "transformed_feature_order_digest",
    "transformed_missingness_digest", "audited_matrix_digest", "fitted_matrix_declared",
    "fitted_matrix_digest", "frames_identical")


def binding_fields(identity: Mapping[str, Any], design: Mapping[str, Any] | None,
                   arguments: Mapping[str, Mapping[str, Any]],
                   gate: Mapping[str, Any], caller: Mapping[str, Any],
                   dual: Mapping[str, Any] | None = None,
                   provenance: Mapping[str, Any] | None = None) -> dict:
    """The exact facts a receipt is bound to.

    A receipt is a claim about a specific gate, a specific caller, a specific arm and fold, and a
    specific set of input bytes. Every one of those is digested here and folded into a single
    ``binding_digest``. Present the receipt alongside different inputs and the recomputed digest
    differs, which is what makes reuse detectable rather than plausible.
    """
    d = dict(design or {})
    f: dict[str, Any] = {
        "experiment": str(identity.get("experiment") or ""),
        "arm": str(identity.get("arm") or ""),
        "fold": str(identity.get("fold") or ""),
        "scope": str(identity.get("scope") or ""),
        "gate_source_sha256": gate.get("source_sha256"),
        "caller_source_sha256": caller.get("source_sha256"),
        "n_design_rows": d.get("n_rows"),
        "n_features": d.get("n_features"),
        "feature_order_digest": d.get("feature_order_digest"),
        "feature_name_membership_digest": d.get("feature_name_membership_digest"),
        "design_row_identity_digest": d.get("design_row_identity_digest"),
        "design_row_membership_digest": d.get("design_row_membership_digest"),
        "design_values_digest": d.get("design_values_digest"),
        "training_frame_digest": d.get("training_frame_digest"),
    }
    for name in REQUIRED_ARGUMENTS:
        a = dict(arguments.get(name) or {})
        f[f"{name}_value_digest"] = a.get("value_digest")
        f[f"{name}_index_digest"] = a.get("index_digest")
        f[f"{name}_n"] = a.get("n")
        f[f"{name}_declared_not_applicable"] = a.get("declared_not_applicable")
    d2 = dict(dual or {})
    for k in DUAL_BINDING_FIELDS:
        f[k] = d2.get(k)
    p2 = dict(provenance or {})
    f["provenance_claimed"] = bool(p2.get("claimed", False))
    f["provenance_verified"] = bool(p2.get("verified", False))
    f["provenance_digest"] = p2.get("provenance_digest")
    return f


def binding_digest(fields: Mapping[str, Any]) -> str:
    payload = json.dumps({k: fields[k] for k in sorted(fields)}, sort_keys=True, default=str)
    return "binding:sha256=" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


#: fields whose divergence means the receipt is being presented for DIFFERENT INPUTS.
_INPUT_BINDING_FIELDS = tuple(
    ["experiment", "arm", "fold", "scope", "gate_source_sha256",
     "n_design_rows", "n_features", "feature_order_digest",
     "feature_name_membership_digest", "design_row_identity_digest",
     "design_row_membership_digest", "design_values_digest", "training_frame_digest"]
    + [f"{n}_{s}" for n in REQUIRED_ARGUMENTS
       for s in ("value_digest", "index_digest", "n", "declared_not_applicable")]
    + list(DUAL_BINDING_FIELDS)
    + ["provenance_claimed", "provenance_verified", "provenance_digest"])


# --------------------------------------------------------------------------------------------
# argument validation -- the whole point is that this precedes the fit
# --------------------------------------------------------------------------------------------

def _validate(df: Any, names: Sequence[str], supplied: Mapping[str, Any],
              not_applicable: Mapping[str, Any] | None,
              adjudications: Mapping[str, Any] | None,
              align: Any, identity: Mapping[str, Any],
              caller: Mapping[str, Any]) -> tuple[dict, dict, list[dict]]:
    raw: list[dict] = []
    na: dict[str, str] = {}

    for key in ("experiment", "arm", "fold"):
        v = identity.get(key)
        if not (isinstance(v, str) and v.strip()):
            raw.append(_finding("identity_unspecified", field=key,
                                detail="a record that cannot name its experiment, arm and "
                                       "chronological fold cannot be filed against anything"))
    if not caller.get("source_sha256"):
        raw.append(_finding("caller_source_unidentifiable",
                            resolution=caller.get("resolution"),
                            source_path=caller.get("source_path"),
                            detail="the producer's source could not be hashed, so a future reader "
                                   "cannot identify which implementation actually invoked the "
                                   "gate; pass caller_path= explicitly, or adjudicate with a "
                                   "stated reason"))

    align_map, align_bad = _normalise_align(align)
    raw += align_bad

    for k, v in dict(not_applicable or {}).items():
        key = str(k)
        if key not in REQUIRED_ARGUMENTS:
            raw.append(_finding("unknown_argument_declared", argument=key,
                                known_arguments=list(REQUIRED_ARGUMENTS),
                                detail="a typo'd declaration is indistinguishable from an "
                                       "omitted one unless it is surfaced"))
            continue
        if not (isinstance(v, str) and v.strip()):
            raw.append(_finding("not_applicable_without_reason", argument=key,
                                detail="declaring an argument inapplicable requires a stated "
                                       "reason; it is carried in the record forever"))
            continue
        na[key] = v.strip()

    raw += _design_findings(df, names)

    records: dict[str, dict] = {}
    bound: dict[str, Any] = {}
    alignment_steps: list[dict] = []
    checks_not_run: list[str] = []
    align_used: set[str] = set()

    for name in REQUIRED_ARGUMENTS:
        value = supplied.get(name, UNSPECIFIED)
        is_unspecified = isinstance(value, _Unspecified)
        is_null = (value is None)
        declared = na.get(name)

        if declared is not None:
            if not (is_unspecified or is_null):
                raw.append(_finding("not_applicable_contradicted", argument=name,
                                    reason=declared,
                                    detail="declared inapplicable and supplied anyway; the "
                                           "record cannot say both"))
            else:
                raw.append(_finding("argument_declared_not_applicable", argument=name,
                                    reason=declared,
                                    disabled_checks=list(ARGUMENT_ENABLES[name]),
                                    detail="not blocking, but the audit is INCOMPLETE and is "
                                           "recorded as such (contract §3.1)"))
                checks_not_run += list(ARGUMENT_ENABLES[name])
                records[name] = _argument_record(name, value, supplied=False, null=False,
                                                 not_applicable=declared,
                                                 alignment={"status": "not_applicable",
                                                            "method": None})
                continue

        if is_unspecified:
            raw.append(_finding("argument_omitted", argument=name,
                                required_because=ARGUMENT_WHY[name],
                                disabled_checks=list(ARGUMENT_ENABLES[name]),
                                detail="omitting it produces a passed audit that is "
                                       "indistinguishable from a real one"))
            records[name] = _argument_record(name, value, supplied=False, null=False,
                                             not_applicable=None,
                                             alignment={"status": "omitted", "method": None})
            continue
        if is_null:
            raw.append(_finding("argument_null", argument=name,
                                required_because=ARGUMENT_WHY[name],
                                disabled_checks=list(ARGUMENT_ENABLES[name]),
                                detail="None is the gate's own default; passing it explicitly "
                                       "disables the same checks as omitting it"))
            records[name] = _argument_record(name, value, supplied=True, null=True,
                                             not_applicable=None,
                                             alignment={"status": "null", "method": None})
            continue

        alignment: dict[str, Any] = {"status": "not_evaluated", "method": None}
        if isinstance(df, pd.DataFrame):
            if name in ROW_ALIGNED_ARGUMENTS:
                method = align_map.get(name)
                status, findings = _alignment_findings(name, value, df)
                if status == "misaligned" and method:
                    align_used.add(name)
                    value, steps = _apply_alignment(name, value, df, method)
                    if steps and steps[0]["kind"] == "argument_realigned":
                        alignment_steps.append(steps[0])
                        raw.append(steps[0])
                        alignment = {"status": "realigned_explicitly", "method": method,
                                     "index_digest_as_supplied":
                                         steps[0]["index_digest_as_supplied"],
                                     "value_digest_as_supplied":
                                         steps[0]["value_digest_as_supplied"]}
                        status = "identical"
                    else:
                        raw += steps + findings
                        alignment = {"status": "alignment_failed", "method": method}
                else:
                    if method and status == "identical":
                        raw.append(_finding("alignment_unused", argument=name, method=method,
                                            detail="an alignment step was requested but the "
                                                   "argument was already aligned; recorded so the "
                                                   "declaration is not mistaken for a repair"))
                        align_used.add(name)
                    elif method:
                        align_used.add(name)
                    raw += findings
                    alignment = {"status": status, "method": method}
                # a placeholder is a defect of the VALUES, so it is still checked when row
                # identity is merely unprovable -- otherwise adjudicating the missing index
                # would take the placeholder check down with it.
                if status in ("identical", "row_identity_absent"):
                    raw += _placeholder_findings(name, value, df)
            else:
                status, findings = _test_df_findings(value, df, [str(c) for c in names])
                raw += findings
                alignment = {"status": status, "method": None}
                if not any(f["kind"] == "argument_wrong_type" for f in findings):
                    raw += _placeholder_findings(name, value, df)

        records[name] = _argument_record(name, value, supplied=True, null=False,
                                         not_applicable=None, alignment=alignment)
        bound[name] = value

    for name in align_map:
        if name not in align_used:
            raw.append(_finding("alignment_unused", argument=name, method=align_map[name],
                                detail="an alignment step was declared for an argument that was "
                                       "not evaluated"))

    enabled = [k for name in REQUIRED_ARGUMENTS if name in bound
               for k in ARGUMENT_ENABLES[name]]
    if checks_not_run:
        raw.append(_finding("audit_incomplete", checks_not_run=sorted(set(checks_not_run)),
                            detail="an audit that does not run every applicable check is not a "
                                   "passing audit; it is an incomplete one (contract §3.1)"))

    design = design_identity(df, names) if isinstance(df, pd.DataFrame) else None
    row_counts = {"design_rows": int(len(df)) if isinstance(df, pd.DataFrame) else None}
    for name in REQUIRED_ARGUMENTS:
        row_counts[name] = records[name].get("n")

    core = {
        "schema": "gate_invocation.arguments/2",
        "identity": dict(identity),
        "caller": dict(caller),
        "design": design,
        "row_counts": row_counts,
        "required_arguments": list(REQUIRED_ARGUMENTS),
        "arguments": records,
        "alignment": {k: records[k]["alignment"]["status"] for k in REQUIRED_ARGUMENTS},
        "alignment_steps": alignment_steps,
        "checks_enabled": sorted(set(enabled)),
        "checks_not_run": sorted(set(checks_not_run)),
        "complete": len(checks_not_run) == 0,
        "contract": "GATE_INVOCATION_CONTRACT.md §3.1 and §6",
    }
    norm, bad = _normalise_adjudications(adjudications)
    report = _finalise(core, raw, norm, bad, report_unused=True)
    return report, bound, raw


def validate_arguments(df: pd.DataFrame, names: Sequence[str], *,
                       experiment: str = "", arm: str = "", fold: str = "",
                       offset: Any = UNSPECIFIED, target: Any = UNSPECIFIED,
                       outcome_mask: Any = UNSPECIFIED, test_df: Any = UNSPECIFIED,
                       align: Mapping[str, str] | None = None,
                       not_applicable: Mapping[str, Any] | None = None,
                       adjudications: Mapping[str, Any] | None = None,
                       caller_path: str | Path | None = None,
                       scope: str = "fold",
                       raise_on_block: bool = True) -> dict:
    """Validate the four required arguments WITHOUT calling the gate and WITHOUT fitting.

    Returns a machine-readable record carrying, per argument, its value digest, its ordered index
    digest, its order-insensitive membership digest and its alignment result. Raises
    ``GateInvocationFailure`` on a blocking finding unless ``raise_on_block=False``.

    **This entry point does NOT perform the dual-frame audit (contract §8a) and must never be used
    as a fit gate.** It is the argument layer alone, and the argument layer alone is exactly what
    ws2 satisfied in full: every argument supplied, valid, aligned and non-placeholder, against a
    design that had already been imputed. Use ``audit_fold`` or ``guarded_fit``.
    """
    identity = {"experiment": experiment, "arm": arm, "fold": fold, "scope": scope}
    report, _, _ = _validate(df, names,
                             {"offset": offset, "target": target,
                              "outcome_mask": outcome_mask, "test_df": test_df},
                             not_applicable, adjudications, align, identity,
                             caller_identity(caller_path))
    if report["blocking"] and raise_on_block:
        raise GateInvocationFailure(json.dumps(report["blocking"][:6], default=str))
    return report


# --------------------------------------------------------------------------------------------
# calling the gate
# --------------------------------------------------------------------------------------------

class _SuppressAll(dict):
    """An adjudicator that excuses everything, used ONLY to recover a complete finding list.

    ``feature_gate.audit`` raises before returning when it blocks, and the exception carries only
    the first six blocking findings. To archive the FULL record of a failing fold the call is
    repeated once with adjudication suppressed; the returned verdict is then discarded and
    recomputed from the gate's own ``BLOCKING`` set and the caller's real adjudications, so no
    ``"passed": true`` produced by the suppression ever survives into a receipt.
    """

    def get(self, key, default=False):                          # noqa: D102 - see class docstring
        return True

    def __bool__(self) -> bool:
        return True


def _recompute_gate_blocking(findings: Sequence[Mapping[str, Any]],
                             adjudicated: Mapping[str, Any]) -> list[dict]:
    """Mirror of ``feature_gate.audit``'s own blocking rule. ``feature_gate.py`` governs."""
    return [dict(f) for f in findings
            if f["kind"] in feature_gate.BLOCKING
            and not adjudicated.get(f.get("feature", ""), False)]


def _call_gate(df: pd.DataFrame, names: Sequence[str], bound: Mapping[str, Any],
               gate_adjudicated: Mapping[str, Any] | None,
               thresholds: Mapping[str, float] | None) -> dict:
    adj = dict(gate_adjudicated or {})
    kw = dict(_resolved_gate_thresholds(thresholds))
    call = dict(offset=bound.get("offset"), target=bound.get("target"),
                outcome_mask=bound.get("outcome_mask"), test_df=bound.get("test_df"),
                adjudicated=adj, **kw)
    try:
        out = dict(feature_gate.audit(df, list(names), **call))
        out["raised"] = False
        return out
    except feature_gate.FeatureGateFailure:
        recovered = dict(feature_gate.audit(df, list(names),
                                            **{**call, "adjudicated": _SuppressAll()}))
        findings = list(recovered.get("findings", []))
        recovered["blocking"] = _recompute_gate_blocking(findings, adj)
        recovered["passed"] = False
        recovered["raised"] = True
        recovered["recovery_note"] = (
            "feature_gate raised; the call was repeated once with adjudication suppressed solely "
            "to capture the complete finding list. The verdict here is recomputed from "
            "feature_gate.BLOCKING and the caller's real adjudications, never from the "
            "suppressed call")
        return recovered


def _invoke(df: Any, names: Sequence[str], supplied: Mapping[str, Any], *,
            experiment: str, arm: str, fold: str, scope: str,
            not_applicable: Mapping[str, Any] | None,
            adjudications: Mapping[str, Any] | None,
            align: Mapping[str, str] | None,
            gate_adjudicated: Mapping[str, Any] | None,
            thresholds: Mapping[str, float] | None,
            caller: Mapping[str, Any],
            receipt_path: str | Path | None,
            require_receipt: bool,
            raw_df: Any = UNSPECIFIED,
            transformation: Any = None,
            provenance: Any = None,
            fitted_matrix: Any = UNSPECIFIED) -> tuple[dict, dict]:
    identity = {"experiment": experiment, "arm": arm, "fold": fold, "scope": scope}
    args_report, bound, raw = _validate(df, names, supplied, not_applicable, adjudications,
                                        align, identity, caller)
    norm, bad = _normalise_adjudications(adjudications)

    gate: dict | None = None
    extra: list[dict] = []
    dual_findings: list[dict] = []
    stage_failed: str | None = None
    dual_rec: dict[str, Any] = {"policy": "MANDATORY for every fitted feature design "
                                          "(contract §8a)",
                                "evaluated": False, "case": None, "assurance": None,
                                "stage1_pass": False,
                                "note": "argument validation blocked first, so the dual-frame "
                                        "audit was not reached"}
    om_bound = bound.get("outcome_mask")
    dual_ident = dual_frame_identity(df, names, raw_df, transformation, fitted_matrix,
                                     outcome_mask=om_bound)

    if args_report["blocking"]:
        stage_failed = "arguments"
        dual_rec["identity"] = dict(dual_ident)
        extra.append(_finding("gate_not_invoked", fold=fold,
                              blocked_by=sorted({f["kind"] for f in args_report["blocking"]}),
                              detail="argument validation blocked, so feature_gate was never "
                                     "called and no fit can have occurred; the failure precedes "
                                     "the model, which is the point"))
    else:
        # ---- the dual frame, before the gate and long before the fit -----------------------
        design_membership = (args_report.get("design") or {}).get("design_row_membership_digest")
        dual_findings, dual_rec, raw_for_audit = _dual_frame_structure(
            df, names, raw_df, transformation, provenance, fitted_matrix, identity,
            dual_ident, design_membership)
        dual_rec["evaluated"] = True
        structural_blocking = _blocking_after_adjudication(dual_findings, norm)

        # The fitted frame's own value patterns are evidence whether or not a raw frame was ever
        # produced, so this runs even when the structure already blocked: it is what makes
        # withholding the raw frame VISIBLE rather than merely refused.
        fill_values: dict[str, set] = {}
        for op in (dual_rec.get("transformation") or {}).get("operations", []):
            v = op.get("value")
            if op.get("imputes_missing") and isinstance(v, (int, float, np.integer, np.floating)):
                for c in op["columns"]:
                    fill_values.setdefault(c, set()).add(float(v))
        vp_analysis, vp_findings = _outcome_separating_values(df, names, om_bound, fill_values)
        dual_rec["value_pattern_analysis"] = vp_analysis
        dual_findings += vp_findings

        if not structural_blocking:
            # the RAW frame is audited FIRST. An outcome-encoding null mask fires there, and the
            # transformed frame is only reached if the raw one is clean.
            if dual_rec.get("case") == "transformation" and isinstance(raw_for_audit,
                                                                       pd.DataFrame):
                raw_names = [c for c in [str(x) for x in names] if c in raw_for_audit.columns]
                if raw_names:
                    raw_audit = _call_gate(raw_for_audit, raw_names, bound, gate_adjudicated,
                                           thresholds)
                    dual_rec["raw_audit"] = raw_audit
                    dual_rec["raw_gate_invoked"] = True
                    if len(raw_names) != len(names):
                        dual_findings.append(_finding(
                            "raw_audit_restricted", audited_features=raw_names,
                            detail="the raw audit ran on the features that exist in the "
                                   "producer's frame; the constructed ones are declared"))
                    if not raw_audit.get("passed", False):
                        dual_findings.append(_finding(
                            "raw_frame_gate_blocked", fold=fold,
                            gate_blocking_kinds=sorted({f["kind"]
                                                        for f in raw_audit.get("blocking", [])}),
                            n_gate_blocking=len(raw_audit.get("blocking", [])),
                            detail="feature_gate blocked the PRE-TRANSFORMATION frame. The fitted "
                                   "frame may well be clean; that is what filling an "
                                   "outcome-encoding null mask looks like"))
                    dual_findings += _conversion_findings(raw_audit, dual_ident, names)
            else:
                dual_findings += _conversion_findings(None, dual_ident, names)

        dual_blocking = _blocking_after_adjudication(dual_findings, norm)
        if dual_blocking:
            stage_failed = "dual_frame"
            extra.append(_finding(
                "gate_not_invoked", fold=fold,
                blocked_by=sorted({f["kind"] for f in dual_blocking}),
                detail="the dual-frame audit blocked, so feature_gate was never called on the "
                       "fitted design and no fit can have occurred; the failure precedes the "
                       "model (contract §8a)"))
        else:
            gate = _call_gate(df, names, bound, gate_adjudicated, thresholds)
            if dual_rec.get("case") == "identity":
                dual_rec["raw_audit"] = {"same_call_as_transformed_audit": True, **gate}
                dual_rec["raw_gate_invoked"] = True
            if not gate.get("passed", False):
                stage_failed = "gate"
                extra.append(_finding("gate_blocked", fold=fold,
                                      gate_blocking_kinds=sorted({f["kind"]
                                                                  for f in gate.get("blocking", [])}),
                                      n_gate_blocking=len(gate.get("blocking", [])),
                                      detail="feature_gate blocked this design; see the nested gate "
                                             "record"))

    if require_receipt and receipt_path is None:
        extra.append(_finding("receipt_not_declared",
                              detail="a fit without an archivable per-fold record has no gate "
                                     "record; 'the gate exists in the repository' is not a gate "
                                     "record (contract §6)"))

    gate_ident = gate_module_identity()
    fields = binding_fields(identity, args_report.get("design"), args_report["arguments"],
                            gate_ident, caller, dual_ident, dual_rec.get("provenance"))

    core = dict(args_report)
    for k in ("findings", "blocking", "adjudications_declared", "adjudications_applied",
              "n_adjudicated", "passed"):
        core.pop(k, None)
    core.update({
        "schema": RECORD_SCHEMA,
        "gate_invoked": gate is not None,
        "gate": gate,
        "gate_findings": list((gate or {}).get("findings", [])),
        "gate_blocking": list((gate or {}).get("blocking", [])),
        "gate_arguments": _resolved_gate_thresholds(thresholds),
        "gate_adjudicated": {str(k): bool(v) for k, v in dict(gate_adjudicated or {}).items()},
        "gate_module": gate_ident,
        "dual_frame": dual_rec,
        "stage_failed": stage_failed,
        "binding": {"binding_digest": binding_digest(fields), "fields": fields,
                    "note": "this record is bound to these inputs; verify_receipt recomputes the "
                            "digest from the inputs presented and blocks on divergence"},
        "receipt_path": str(receipt_path) if receipt_path is not None else None,
        "receipt_written": False,
        "note": "a converging optimiser does not validate an unidentified design, and a gate "
                "record that cannot identify its own inputs does not validate anything at all",
    })

    def _stamp(rep: dict) -> dict:
        prov_ok = bool((dual_rec.get("provenance") or {}).get("verified"))
        level = _assurance_level(dual_rec.get("case"), prov_ok, rep["blocking"])
        rep["assurance"] = level
        rep["stage1_pass"] = level in STAGE1_PASS_LEVELS
        dual_rec["assurance"] = level
        dual_rec["stage1_pass"] = rep["stage1_pass"]
        rep["dual_frame"] = dual_rec
        return rep

    rep = _stamp(_finalise(core, raw + dual_findings + extra, norm, bad, report_unused=True))

    if receipt_path is not None:
        try:
            payload = dict(rep)
            payload["receipt_written"] = True
            write_receipt(payload, receipt_path)
            rep = payload
        except Exception as e:
            extra.append(_finding("receipt_unwritable", path=str(receipt_path), error=repr(e),
                                  detail="an unwritable receipt is a gate failure, not a warning; "
                                         "an arm that cannot archive its per-fold record has not "
                                         "produced one"))
            rep = _stamp(_finalise(core, raw + dual_findings + extra, norm, bad,
                                   report_unused=True))
    return rep, bound


def audit_fold(df: pd.DataFrame, names: Sequence[str], *,
               experiment: str, arm: str, fold: str,
               offset: Any = UNSPECIFIED, target: Any = UNSPECIFIED,
               outcome_mask: Any = UNSPECIFIED, test_df: Any = UNSPECIFIED,
               raw_df: Any = UNSPECIFIED,
               transformation: Any = None,
               provenance: Any = None,
               fitted_matrix: Any = UNSPECIFIED,
               align: Mapping[str, str] | None = None,
               not_applicable: Mapping[str, Any] | None = None,
               adjudications: Mapping[str, Any] | None = None,
               gate_adjudicated: Mapping[str, Any] | None = None,
               thresholds: Mapping[str, float] | None = None,
               caller_path: str | Path | None = None,
               receipt_path: str | Path | None = None,
               require_receipt: bool = False,
               scope: str = "fold",
               raise_on_block: bool = True) -> dict:
    """Audit ONE chronological training fold, with every required argument AND both frames bound.

    Three stages, in this order, and each is reached only if the previous one passed:

    1. **argument validation** — the four optional-in-the-signature arguments;
    2. **the dual frame** (contract §8a) — the pre-transformation frame, the declared
       transformation lineage, the reconciliation between the two, the RAW audit, and the
       transformed frame's own value patterns against the outcome mask;
    3. **``feature_gate.audit`` on the fitted design**.

    So a dual-frame failure leaves ``gate_invoked=False``: the failure precedes the gate and
    therefore the model. ``raw_df`` is MANDATORY. If no transformation occurred, pass
    ``raw_df=df, transformation=no_transformation("...")`` — the same object is correct, no copy
    is required, and the wrapper proves the identity by digest rather than believing it. If
    ``receipt_path`` is given the receipt is written before this function returns, and a failed
    write is itself blocking.
    """
    rep, _ = _invoke(df, names, {"offset": offset, "target": target,
                                 "outcome_mask": outcome_mask, "test_df": test_df},
                     experiment=experiment, arm=arm, fold=str(fold), scope=scope,
                     not_applicable=not_applicable, adjudications=adjudications, align=align,
                     gate_adjudicated=gate_adjudicated, thresholds=thresholds,
                     caller=caller_identity(caller_path), receipt_path=receipt_path,
                     require_receipt=require_receipt, raw_df=raw_df,
                     transformation=transformation, provenance=provenance,
                     fitted_matrix=fitted_matrix)
    if rep["blocking"] and raise_on_block:
        raise GateInvocationFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


def audit_final_design(df: pd.DataFrame, names: Sequence[str], *,
                       experiment: str, arm: str, fold: str = "final_design",
                       **kw: Any) -> dict:
    """Audit the FINAL ASSEMBLED design. Required in addition to, never instead of, the folds."""
    kw.setdefault("scope", "final_design")
    if kw.get("caller_path") is None:
        kw["caller_path"] = caller_identity().get("source_path")
    return audit_fold(df, names, experiment=experiment, arm=arm, fold=fold, **kw)


def guarded_fit(fit_fn: Callable[[dict, dict], Any], df: pd.DataFrame, names: Sequence[str], *,
                experiment: str, arm: str, fold: str, receipt_path: str | Path,
                offset: Any = UNSPECIFIED, target: Any = UNSPECIFIED,
                outcome_mask: Any = UNSPECIFIED, test_df: Any = UNSPECIFIED,
                raw_df: Any = UNSPECIFIED,
                transformation: Any = None,
                provenance: Any = None,
                fitted_matrix: Any = UNSPECIFIED,
                align: Mapping[str, str] | None = None,
                scope: str = "fold",
                not_applicable: Mapping[str, Any] | None = None,
                adjudications: Mapping[str, Any] | None = None,
                gate_adjudicated: Mapping[str, Any] | None = None,
                thresholds: Mapping[str, float] | None = None,
                caller_path: str | Path | None = None) -> tuple[dict, Any]:
    """Run ``fit_fn`` only if the invocation passes AND its receipt is on disk.

    ``fit_fn`` is called as ``fit_fn(record, bound)`` where ``bound`` holds the exact argument
    objects that were audited — post-alignment when an explicit alignment step was requested. The
    caller must fit THOSE, which is the whole reason alignment is returned rather than applied
    invisibly. ``receipt_path`` has no default: a fit whose record was never archived is a fit
    with no gate record. ``raw_df`` and ``transformation`` are mandatory: no fit occurs if either
    frame or the declared transformation lineage is unavailable (contract §8a).
    """
    rep, bound = _invoke(df, names, {"offset": offset, "target": target,
                                     "outcome_mask": outcome_mask, "test_df": test_df},
                         experiment=experiment, arm=arm, fold=str(fold), scope=scope,
                         not_applicable=not_applicable, adjudications=adjudications, align=align,
                         gate_adjudicated=gate_adjudicated, thresholds=thresholds,
                         caller=caller_identity(caller_path), receipt_path=receipt_path,
                         require_receipt=True, raw_df=raw_df, transformation=transformation,
                         provenance=provenance, fitted_matrix=fitted_matrix)
    if rep["blocking"]:
        raise GateInvocationFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep, fit_fn(rep, bound)


# --------------------------------------------------------------------------------------------
# receipt verification -- a receipt is bound to its inputs and cannot be carried elsewhere
# --------------------------------------------------------------------------------------------

def verify_receipt(receipt: Mapping[str, Any], df: pd.DataFrame, names: Sequence[str], *,
                   experiment: str, arm: str, fold: str,
                   offset: Any = UNSPECIFIED, target: Any = UNSPECIFIED,
                   outcome_mask: Any = UNSPECIFIED, test_df: Any = UNSPECIFIED,
                   raw_df: Any = UNSPECIFIED,
                   transformation: Any = None,
                   provenance: Any = None,
                   fitted_matrix: Any = UNSPECIFIED,
                   align: Mapping[str, str] | None = None,
                   not_applicable: Mapping[str, Any] | None = None,
                   scope: str | None = None,
                   caller_path: str | Path | None = None,
                   raise_on_block: bool = True) -> dict:
    """Recompute a record's binding from the inputs PRESENTED and block on divergence.

    This is what makes a passing receipt un-reusable. Divergence in an INPUT field is
    ``receipt_reuse_detected`` and is non-adjudicable — the receipt is being offered as evidence
    about data it never saw. Divergence in the caller hash alone is
    ``receipt_producer_divergence``: the same inputs verified by a different producer, which is a
    weaker claim and is adjudicable with a stated reason.

    The raw frame, the transformation specification, the fitted matrix and the producer
    provenance are part of the binding, so a receipt cannot be carried across to a run whose
    pre-transformation frame, declared lineage or fitted matrix differ.
    """
    raw: list[dict] = []
    if str(receipt.get("schema")) != RECORD_SCHEMA:
        raw.append(_finding("receipt_schema_unrecognised", schema=receipt.get("schema"),
                            expected=RECORD_SCHEMA,
                            detail="this verifier knows one record schema; an unrecognised one "
                                   "cannot be checked and must not be trusted"))
    stored = dict((receipt.get("binding") or {}).get("fields") or {})
    stored_digest = (receipt.get("binding") or {}).get("binding_digest")
    if not stored or not stored_digest:
        raw.append(_finding("receipt_binding_absent",
                            detail="the record carries no binding, so it cannot be shown to be "
                                   "about any particular inputs"))

    identity = {"experiment": experiment, "arm": arm, "fold": str(fold),
                "scope": scope or str(receipt.get("identity", {}).get("scope") or "fold")}
    caller = caller_identity(caller_path)
    args_report, _, _ = _validate(df, names,
                                  {"offset": offset, "target": target,
                                   "outcome_mask": outcome_mask, "test_df": test_df},
                                  not_applicable, None, align, identity, caller)
    dual_ident = dual_frame_identity(df, names, raw_df, transformation, fitted_matrix,
                                     outcome_mask=(outcome_mask
                                                   if _is_supplied(outcome_mask) else None))
    prov, _prov_findings = _verify_provenance(provenance, identity,
                                              dual_ident.get("raw_row_membership_digest"))
    fields = binding_fields(identity, args_report.get("design"), args_report["arguments"],
                            gate_module_identity(), caller, dual_ident, prov)
    digest = binding_digest(fields)

    if stored:
        diverged = [k for k in _INPUT_BINDING_FIELDS if stored.get(k) != fields.get(k)]
        if diverged:
            raw.append(_finding("receipt_reuse_detected", n_diverging_fields=len(diverged),
                                diverging_fields=diverged[:12],
                                stored={k: stored.get(k) for k in diverged[:6]},
                                presented={k: fields.get(k) for k in diverged[:6]},
                                stored_binding_digest=stored_digest,
                                recomputed_binding_digest=digest,
                                detail="this receipt is bound to different inputs than the ones "
                                       "presented; it is evidence about data it never saw"))
        elif stored.get("caller_source_sha256") != fields.get("caller_source_sha256"):
            raw.append(_finding("receipt_producer_divergence",
                                stored=stored.get("caller_source_sha256"),
                                presented=fields.get("caller_source_sha256"),
                                detail="same inputs, different producer source; adjudicable with "
                                       "a stated reason"))
        else:
            raw.append(_finding("receipt_binding_verified", binding_digest=digest,
                                detail="every bound field matches the inputs presented"))

    core = {"schema": "gate_invocation.verification/1",
            "identity": identity,
            "stored_binding_digest": stored_digest,
            "recomputed_binding_digest": digest,
            "binding_matches": bool(stored_digest == digest),
            "caller": caller,
            "gate_module": gate_module_identity()}
    rep = _finalise(core, raw, {}, [], report_unused=False)
    if rep["blocking"] and raise_on_block:
        raise GateInvocationFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


# --------------------------------------------------------------------------------------------
# per-fold + final design, as one archivable receipt
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class FoldInvocation:
    """One chronological training fold's complete invocation, arguments included.

    Every required argument defaults to ``UNSPECIFIED`` rather than ``None``, so a fold declared
    without them is an omission this module can see, not a silent pass.
    """

    fold: str
    df: Any
    names: Sequence[str]
    offset: Any = UNSPECIFIED
    target: Any = UNSPECIFIED
    outcome_mask: Any = UNSPECIFIED
    test_df: Any = UNSPECIFIED
    align: Mapping[str, str] | None = None
    not_applicable: Mapping[str, Any] | None = None
    adjudications: Mapping[str, Any] | None = None
    gate_adjudicated: Mapping[str, Any] | None = None
    thresholds: Mapping[str, float] | None = None
    experiment: str | None = None
    arm: str | None = None
    #: the dual frame, contract §8a. ``raw_df`` defaults to ``UNSPECIFIED`` for the same reason
    #: the four gate arguments do: a fold declared without it is an omission this module can see,
    #: not a silent pass.
    raw_df: Any = UNSPECIFIED
    transformation: Any = None
    provenance: Any = None
    fitted_matrix: Any = UNSPECIFIED

    def invoke(self, *, experiment: str, arm: str, scope: str = "fold",
               caller: Mapping[str, Any] | None = None,
               receipt_path: str | Path | None = None) -> dict:
        rep, _ = _invoke(self.df, self.names,
                         {"offset": self.offset, "target": self.target,
                          "outcome_mask": self.outcome_mask, "test_df": self.test_df},
                         experiment=self.experiment or experiment, arm=self.arm or arm,
                         fold=str(self.fold), scope=scope,
                         not_applicable=self.not_applicable, adjudications=self.adjudications,
                         align=self.align, gate_adjudicated=self.gate_adjudicated,
                         thresholds=self.thresholds,
                         caller=dict(caller or caller_identity()),
                         receipt_path=receipt_path, require_receipt=False,
                         raw_df=self.raw_df, transformation=self.transformation,
                         provenance=self.provenance, fitted_matrix=self.fitted_matrix)
        return rep


def audit_run(*, run_id: str, experiment: str, arm: str,
              folds: Sequence[FoldInvocation],
              final_design: FoldInvocation | None = None,
              expected_folds: Sequence[str] | None = None,
              adjudications: Mapping[str, Any] | None = None,
              caller_path: str | Path | None = None,
              receipt_path: str | Path | None = None,
              raise_on_block: bool = True) -> dict:
    """Audit every chronological training fold AND the final assembled design, as one receipt.

    Contract §6: absence of the per-fold record is itself a gate failure. An empty ``folds`` is
    therefore blocking and non-adjudicable, and a missing ``final_design`` is blocking.

    When the final design passes while a fold blocks, the ws3 shape is named explicitly as
    ``pooled_healthy_fold_degenerate`` so the receipt states, in its own words, that the pooled
    audit is evidence about a matrix nobody fits.
    """
    caller = caller_identity(caller_path)
    raw: list[dict] = []
    fold_records: dict[str, dict] = {}
    seen: set[str] = set()

    for f in folds:
        fid = str(f.fold)
        if fid in seen:
            raw.append(_finding("duplicate_fold_id", fold=fid,
                                detail="two invocations claim the same fold identifier; one of "
                                       "them is not recorded"))
        seen.add(fid)
        rec = f.invoke(experiment=experiment, arm=arm, scope="fold", caller=caller)
        fold_records[fid] = rec
        if not rec["passed"]:
            raw.append(_finding("fold_invocation_failed", fold=fid,
                                stage=rec.get("stage_failed"),
                                blocking_kinds=sorted({b["kind"] for b in rec["blocking"]}),
                                gate_blocking_kinds=sorted(
                                    {b["kind"]
                                     for b in (rec.get("gate") or {}).get("blocking", [])}),
                                detail="a fold that does not pass may not be fitted, and may not "
                                       "be rescued by the pooled audit (contract §4)"))

    final_record = None
    if final_design is None:
        raw.append(_finding("no_final_design_record",
                            detail="the final assembled design must be audited in addition to "
                                   "every fold"))
    else:
        final_record = final_design.invoke(experiment=experiment, arm=arm, scope="final_design",
                                           caller=caller)
        if not final_record["passed"]:
            raw.append(_finding("final_design_invocation_failed",
                                stage=final_record.get("stage_failed"),
                                blocking_kinds=sorted({b["kind"]
                                                       for b in final_record["blocking"]})))

    if not folds:
        raw.append(_finding("no_per_fold_record", run_id=run_id,
                            detail="a pooled audit cannot establish that every training fold is "
                                   "identified; pooled variance is an average and identifiability "
                                   "is a per-fold property (contract §1, §6). 'The gate exists in "
                                   "the repository' is not a gate record"))
    elif expected_folds:
        want = {str(x) for x in expected_folds}
        have = set(fold_records)
        if want != have:
            raw.append(_finding("fold_set_mismatch", declared_folds=sorted(want),
                                audited_folds=sorted(have), missing=sorted(want - have),
                                unexpected=sorted(have - want),
                                detail="the folds audited are not the folds declared"))

    failed = [fid for fid, r in fold_records.items() if not r["passed"]]
    if failed and final_record is not None and final_record["passed"]:
        raw.append(_finding("pooled_healthy_fold_degenerate", failing_folds=sorted(failed),
                            reference_case=dict(REFERENCE_CASE),
                            detail="the final assembled design passed while a fold blocked. This "
                                   "is the ws3 shape exactly: the pooled matrix is never fitted, "
                                   "so a pooled pass is evidence about a matrix nobody fits"))

    incomplete = sorted({fid for fid, r in fold_records.items() if not r.get("complete", True)}
                        | ({str(final_design.fold)} if (final_record is not None
                                                        and not final_record.get("complete", True))
                           else set()))

    fold_bindings = {fid: (r.get("binding") or {}).get("binding_digest")
                     for fid, r in fold_records.items()}
    run_fields = {"run_id": run_id, "experiment": experiment, "arm": arm,
                  "gate_source_sha256": gate_module_identity().get("source_sha256"),
                  "caller_source_sha256": caller.get("source_sha256"),
                  "fold_binding_digests": dict(sorted(fold_bindings.items())),
                  "final_design_binding_digest":
                      (final_record or {}).get("binding", {}).get("binding_digest")}

    core = {
        "schema": RECEIPT_SCHEMA,
        "run_id": run_id,
        "identity": {"experiment": experiment, "arm": arm, "run_id": run_id},
        "contract": "GATE_INVOCATION_CONTRACT.md",
        "required_arguments": list(REQUIRED_ARGUMENTS),
        "argument_enables": {k: list(v) for k, v in ARGUMENT_ENABLES.items()},
        "gate_module": gate_module_identity(),
        "caller": caller,
        "n_folds": len(fold_records),
        "folds": fold_records,
        "final_design": final_record,
        "folds_failed": sorted(failed),
        "records_incomplete": incomplete,
        "complete": not incomplete,
        "binding": {"binding_digest": binding_digest(run_fields), "fields": run_fields},
        "reference_case": dict(REFERENCE_CASE),
        "receipt_path": str(receipt_path) if receipt_path is not None else None,
        "receipt_written": False,
        "note": "a feature audit must run on every chronological training fold AND on the final "
                "assembled design; a pooled audit alone discharges neither",
    }
    norm, bad = _normalise_adjudications(adjudications)

    def _stamp(rep: dict) -> dict:
        levels = [r.get("assurance") for r in fold_records.values()]
        if final_record is not None:
            levels.append(final_record.get("assurance"))
        if rep["blocking"] or not levels or "FAILED" in levels:
            level = "FAILED"
        elif "RAW_PROVENANCE_ASSERTED" in levels:
            level = "RAW_PROVENANCE_ASSERTED"
        elif "TRANSFORMATION_VERIFIED" in levels:
            level = "TRANSFORMATION_VERIFIED"
        else:
            level = "IDENTITY_VERIFIED"
        rep["assurance"] = level
        rep["assurance_by_fold"] = {fid: r.get("assurance") for fid, r in fold_records.items()}
        rep["stage1_pass"] = level in STAGE1_PASS_LEVELS
        return rep

    rep = _stamp(_finalise(core, raw, norm, bad, report_unused=True))

    if receipt_path is not None:
        try:
            payload = dict(rep)
            payload["receipt_written"] = True
            write_receipt(payload, receipt_path)
            rep = payload
        except Exception as e:
            raw.append(_finding("receipt_unwritable", path=str(receipt_path), error=repr(e),
                                detail="an unwritable receipt is a gate failure, not a warning"))
            rep = _stamp(_finalise(core, raw, norm, bad, report_unused=True))

    if rep["blocking"] and raise_on_block:
        raise GateInvocationFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


def verify_run_receipt(receipt: Mapping[str, Any], *, run_id: str, experiment: str, arm: str,
                       folds: Sequence[FoldInvocation],
                       final_design: FoldInvocation | None = None,
                       caller_path: str | Path | None = None,
                       raise_on_block: bool = True) -> dict:
    """Recompute a RUN receipt's per-fold bindings from the invocations presented."""
    caller = caller_identity(caller_path)
    raw: list[dict] = []
    if str(receipt.get("schema")) != RECEIPT_SCHEMA:
        raw.append(_finding("receipt_schema_unrecognised", schema=receipt.get("schema"),
                            expected=RECEIPT_SCHEMA))
    stored = dict((receipt.get("binding") or {}).get("fields") or {})
    if not stored:
        raw.append(_finding("receipt_binding_absent"))

    present = {str(f.fold): f.invoke(experiment=experiment, arm=arm, scope="fold",
                                     caller=caller).get("binding", {}).get("binding_digest")
               for f in folds}
    final_digest = None
    if final_design is not None:
        final_digest = final_design.invoke(experiment=experiment, arm=arm, scope="final_design",
                                           caller=caller).get("binding", {}).get("binding_digest")

    stored_folds = dict(stored.get("fold_binding_digests") or {})
    diverged = sorted(set(stored_folds) ^ set(present))
    diverged += [k for k in sorted(set(stored_folds) & set(present))
                 if stored_folds[k] != present[k]]
    if (stored.get("run_id") != run_id or stored.get("experiment") != experiment
            or stored.get("arm") != arm):
        diverged.append("identity")
    if stored.get("final_design_binding_digest") != final_digest:
        diverged.append("final_design")
    if stored and diverged:
        raw.append(_finding("receipt_reuse_detected", diverging_fields=sorted(set(diverged))[:12],
                            detail="this run receipt is bound to different folds or different "
                                   "inputs than the ones presented"))
    elif stored:
        raw.append(_finding("receipt_binding_verified",
                            binding_digest=(receipt.get("binding") or {}).get("binding_digest")))

    core = {"schema": "gate_invocation.run_verification/1",
            "run_id": run_id, "identity": {"experiment": experiment, "arm": arm},
            "n_folds_presented": len(present), "caller": caller,
            "gate_module": gate_module_identity()}
    rep = _finalise(core, raw, {}, [], report_unused=False)
    if rep["blocking"] and raise_on_block:
        raise GateInvocationFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


def write_receipt(report: Mapping[str, Any], path: str | Path) -> Path:
    """Write a receipt next to a run. Machine-readable, self-identifying, archivable.

    Raises on failure. Callers inside this module convert that into a blocking
    ``receipt_unwritable`` finding: an unwritable receipt is a gate failure, not a warning.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return p


# --------------------------------------------------------------------------------------------

def _main() -> int:                                              # pragma: no cover - descriptive
    ident = gate_module_identity()
    print("=" * 94)
    print("gate_invocation — the four optional arguments of feature_gate.audit are not optional")
    print("=" * 94)
    print(f"record schema  : {RECORD_SCHEMA}")
    print(f"receipt schema : {RECEIPT_SCHEMA}")
    print(f"gate source    : {ident['source_path']}")
    print(f"gate sha256    : {ident['source_sha256']}")
    print(f"thresholds     : {json.dumps(_resolved_gate_thresholds(None))}")
    print()
    for a in REQUIRED_ARGUMENTS:
        print(f"  {a:<13} {ARGUMENT_WHY[a]}")
        print(f"  {'':<13} enables: {', '.join(ARGUMENT_ENABLES[a])}")
    print()
    print(f"alignment methods   : {', '.join(ALIGNMENT_METHODS)}")
    print(f"blocking kinds      : {len(BLOCKING)}")
    print(f"non-adjudicable     : {len(NON_ADJUDICABLE)}")
    print(f"informational kinds : {len(INFORMATIONAL)}")
    print()
    print("dual frame (contract §8a) — MANDATORY for every fitted design, never conditional")
    print(f"  transformation kinds : {', '.join(TRANSFORMATION_KINDS)}")
    print(f"  assurance levels     : {', '.join(ASSURANCE_LEVELS)}")
    print(f"  full Stage 1 pass    : {', '.join(STAGE1_PASS_LEVELS)}")
    print(f"  bound into receipts  : {len(DUAL_BINDING_FIELDS)} dual fields + 3 provenance fields")
    print("  LIMITATION: no producer feature-construction receipt or input manifest is wired into")
    print("  this repository, so a caller who does not supply provenance= reaches")
    print("  RAW_PROVENANCE_ASSERTED and no higher, and no such run is a full Stage 1 pass.")
    return 0


if __name__ == "__main__":                                       # pragma: no cover
    raise SystemExit(_main())
