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

Usage::

    from gate_invocation import FoldInvocation, audit_fold, audit_run, guarded_fit, verify_receipt

    rec = audit_fold(train_df, names, experiment="turnover_p3", arm="A", fold="2022",
                     offset=off, target=y, outcome_mask=appeared, test_df=test_2023,
                     receipt_path="turnover_p3_v1/gate/fold_2022.json")

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
}

#: recorded, never blocking. Listed so that "not in BLOCKING" is a deliberate statement.
INFORMATIONAL = {
    "argument_declared_not_applicable", "audit_incomplete", "adjudication_unused",
    "design_index_is_positional", "test_df_partially_overlaps_design",
    "test_frame_columns_differ", "argument_realigned", "alignment_unused",
    "pooled_healthy_fold_degenerate", "receipt_binding_verified",
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
# the receipt binding -- what makes a receipt un-reusable
# --------------------------------------------------------------------------------------------

def binding_fields(identity: Mapping[str, Any], design: Mapping[str, Any] | None,
                   arguments: Mapping[str, Mapping[str, Any]],
                   gate: Mapping[str, Any], caller: Mapping[str, Any]) -> dict:
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
       for s in ("value_digest", "index_digest", "n", "declared_not_applicable")])


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
            require_receipt: bool) -> tuple[dict, dict]:
    identity = {"experiment": experiment, "arm": arm, "fold": fold, "scope": scope}
    args_report, bound, raw = _validate(df, names, supplied, not_applicable, adjudications,
                                        align, identity, caller)
    norm, bad = _normalise_adjudications(adjudications)

    gate: dict | None = None
    extra: list[dict] = []
    stage_failed: str | None = None

    if args_report["blocking"]:
        stage_failed = "arguments"
        extra.append(_finding("gate_not_invoked", fold=fold,
                              blocked_by=sorted({f["kind"] for f in args_report["blocking"]}),
                              detail="argument validation blocked, so feature_gate was never "
                                     "called and no fit can have occurred; the failure precedes "
                                     "the model, which is the point"))
    else:
        gate = _call_gate(df, names, bound, gate_adjudicated, thresholds)
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
                            gate_ident, caller)

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
        "stage_failed": stage_failed,
        "binding": {"binding_digest": binding_digest(fields), "fields": fields,
                    "note": "this record is bound to these inputs; verify_receipt recomputes the "
                            "digest from the inputs presented and blocks on divergence"},
        "receipt_path": str(receipt_path) if receipt_path is not None else None,
        "receipt_written": False,
        "note": "a converging optimiser does not validate an unidentified design, and a gate "
                "record that cannot identify its own inputs does not validate anything at all",
    })
    rep = _finalise(core, raw + extra, norm, bad, report_unused=True)

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
            rep = _finalise(core, raw + extra, norm, bad, report_unused=True)
    return rep, bound


def audit_fold(df: pd.DataFrame, names: Sequence[str], *,
               experiment: str, arm: str, fold: str,
               offset: Any = UNSPECIFIED, target: Any = UNSPECIFIED,
               outcome_mask: Any = UNSPECIFIED, test_df: Any = UNSPECIFIED,
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
    """Audit ONE chronological training fold, with every required argument bound.

    Argument validation runs first and, if it blocks, ``feature_gate.audit`` is never called at
    all — so the failure precedes both the gate and the fit. If ``receipt_path`` is given the
    receipt is written before this function returns, and a failed write is itself blocking.
    """
    rep, _ = _invoke(df, names, {"offset": offset, "target": target,
                                 "outcome_mask": outcome_mask, "test_df": test_df},
                     experiment=experiment, arm=arm, fold=str(fold), scope=scope,
                     not_applicable=not_applicable, adjudications=adjudications, align=align,
                     gate_adjudicated=gate_adjudicated, thresholds=thresholds,
                     caller=caller_identity(caller_path), receipt_path=receipt_path,
                     require_receipt=require_receipt)
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
    with no gate record.
    """
    rep, bound = _invoke(df, names, {"offset": offset, "target": target,
                                     "outcome_mask": outcome_mask, "test_df": test_df},
                         experiment=experiment, arm=arm, fold=str(fold), scope=scope,
                         not_applicable=not_applicable, adjudications=adjudications, align=align,
                         gate_adjudicated=gate_adjudicated, thresholds=thresholds,
                         caller=caller_identity(caller_path), receipt_path=receipt_path,
                         require_receipt=True)
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
    fields = binding_fields(identity, args_report.get("design"), args_report["arguments"],
                            gate_module_identity(), caller)
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
                         receipt_path=receipt_path, require_receipt=False)
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
    rep = _finalise(core, raw, norm, bad, report_unused=True)

    if receipt_path is not None:
        try:
            payload = dict(rep)
            payload["receipt_written"] = True
            write_receipt(payload, receipt_path)
            rep = payload
        except Exception as e:
            raw.append(_finding("receipt_unwritable", path=str(receipt_path), error=repr(e),
                                detail="an unwritable receipt is a gate failure, not a warning"))
            rep = _finalise(core, raw, norm, bad, report_unused=True)

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
    print(f"non-adjudicable     : {', '.join(sorted(NON_ADJUDICABLE))}")
    print(f"informational kinds : {', '.join(sorted(INFORMATIONAL))}")
    return 0


if __name__ == "__main__":                                       # pragma: no cover
    raise SystemExit(_main())
