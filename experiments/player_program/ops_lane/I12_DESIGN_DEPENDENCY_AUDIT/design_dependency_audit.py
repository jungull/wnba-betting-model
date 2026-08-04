#!/usr/bin/env python3
"""design_dependency_audit.py — REUSABLE call-site audit of the COMPLETE design.

EPISTEMIC STATUS
================
INFRASTRUCTURE. Call-site enforcement. feature_gate.py is not touched.

WHAT PROBLEM THIS SOLVES
========================
``feature_gate.audit`` audits ``X`` and only ``X``. Its ``design_rank_report`` is handed
``names`` — the substantive feature list — so the offset and any nuisance/control columns are
outside the matrix whose rank it reports. Its offset check is PAIRWISE
(``deterministic_transform_of_offset``, |Pearson r| >= 0.999), so it cannot see a dependency that
needs two or more columns to express.

That gap is not hypothetical. On the frozen ``team_possession_prior_v1`` artifact,

    own_est + opp_est == 2 * projected_team_off_possessions        (max |deviation| = 0.0)

and ``feature_gate.audit(d, ["own_est","opp_est"], offset=projected, target=y)`` returns
``findings: []``, ``passed: True`` — because both pairwise correlations (0.7738, 0.1977) sit far
below 0.999 and the rank report never sees the offset column. See stage2a/V2_STOP_CONDITION.json
finding S5, whose stated fix direction is exactly "augmented-rank check over [X | offset]; a
CALL-SITE policy change requiring no edit to feature_gate.py".

WHAT THIS MODULE IS, AND IS NOT
===============================
It is a REUSABLE audit over a design declared as three blocks::

        [ X (substantive) | offset (fixed-coefficient) | nuisance (controls) ]

It is deliberately generic: block contents, fold column, cluster column and adjudications are all
caller-supplied, and nothing in this module knows about any particular arm, target or wave.

It is NOT a replacement for ``feature_gate.py``, and it does not weaken it:

* it IMPORTS the frozen gate, reuses its frozen constants ``RANK_TOL`` / ``COND_MAX``, and obtains
  the augmented rank/condition numbers by calling the gate's OWN frozen ``design_rank_report`` on a
  wider frame. The rank arithmetic is therefore the gate's arithmetic, not a re-implementation;
* when a ``target`` is supplied it runs ``feature_gate.audit`` on ``X`` FIRST and records the
  result verbatim. A ``feature_gate`` block is a block here too (``feature_gate_blocked``);
* it never edits, monkey-patches, subclasses or shadows anything in ``feature_gate``,
  ``comparison_gate`` or ``gate_invocation``. It pins their sha256 digests and refuses to run
  against changed bytes (``frozen_gate_digest_mismatch``).

It establishes NOTHING about which mechanism is real, about any arm's performance, or about
cutoff validity. Availability is not eligibility; identifiability is not admission.

THRESHOLDS — inherited, not invented
====================================
``NEAR_R2 = 0.999 ** 2 == 0.998001``. For a single regressor, R^2 == r^2, so on a one-column
reconstruction this reduces EXACTLY to ``feature_gate``'s default ``corr_threshold = 0.999`` and
extends the same strictness to multi-column subsets. ``EXACT_R2 = 1 - 1e-9`` separates "exact"
from "near-exact" for REPORTING only; both block. ``RANK_TOL`` and ``COND_MAX`` are read off
``feature_gate`` at import time and are never redefined here.

FINDING KINDS
=============
Blocking::

    frozen_gate_digest_mismatch      a pinned shared gate's bytes changed under this audit
    feature_gate_blocked             feature_gate.audit itself blocked on X
    block_membership_ambiguous       a column declared in more than one block
    column_missing_from_frame        a declared column is not in the frame
    column_not_numeric               a declared column will not cast to float
    offset_block_empty               the audit was invoked with no offset
    offset_is_placeholder            offset constant, all-zero or all-NaN
    insufficient_complete_rows       fewer than MIN_ROWS jointly finite rows
    design_column_non_finite         +/-inf, or every value NaN
    design_column_zero_variance      a design column is constant on the complete case
    augmented_rank_deficient         rank([X|offset|nuisance]) < n_columns
    augmented_ill_conditioned        condition number > feature_gate.COND_MAX
    affine_reconstruction            a design column is affine in the other design columns
    offset_reconstructed_by_design   R^2(offset ~ 1 + [X|nuisance]) >= NEAR_R2   (free slope)
    offset_reconstructed_by_x        ... and X alone suffices
    offset_reconstructed_by_nuisance ... and the nuisance block alone suffices
    candidate_affine_in_offset       a single X column is affine in the offset
    fold_local_rank_deficient        any rank/conditioning failure inside one fold
    fold_local_ill_conditioned
    fold_local_zero_variance         a design column is constant inside one fold
    fold_local_offset_reconstructed  per-fold offset reconstruction
    cluster_split_across_folds       one cluster's rows land in two folds
    adjudication_without_reason      an adjudication carrying no reason string

Report-only (never blocking)::

    complete_case_row_loss           rows dropped by joint finiteness
    offset_partially_explained       0.5 <= R^2(offset ~ design) < NEAR_R2
    condition_number_elevated        1e3 < cond <= COND_MAX

WHAT IT DOES NOT CATCH — read before citing a pass
==================================================
Everything in GATE_INVOCATION_CONTRACT.md section 7 still applies, and this module adds no
exemption to it. In particular the reconstruction tests here are AFFINE. A column that is an exact
NONLINEAR function of the others (a product, a ratio, a share, a threshold indicator) can leave
the augmented design full-rank with unremarkable R^2. ``offset_tie_group_probe`` is a narrow,
optional, explicitly non-exhaustive probe at that gap, not a solution to it. A pass here is a
necessary condition, never a sufficient one.

Pure stdlib + numpy/pandas. Python 3.13. No scipy.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

_PP = Path(__file__).resolve().parents[2]          # experiments/player_program
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

import feature_gate as fg                                                    # noqa: E402

__all__ = [
    "ALGORITHM_ID", "FROZEN_GATE_DIGESTS", "NEAR_R2", "EXACT_R2", "MIN_ROWS",
    "BLOCKING", "REPORT_ONLY",
    "DesignDependencyFailure", "Design",
    "frozen_gate_digests", "frozen_gate_status",
    "audit_design", "assert_design_identified", "audit_receipt",
    "affine_relations", "reconstruction_r2", "minimal_reconstructing_subset",
    "offset_tie_group_probe",
]

ALGORITHM_ID = "design_dependency_audit_v1"

#: sha256 of the shared gates this audit is built against. BYTES, not prose. These are the values
#: recorded by G00_LIVE_RECONCILIATION for the same three files; a mismatch is a blocking finding
#: rather than something this module silently tolerates.
FROZEN_GATE_DIGESTS: dict[str, str] = {
    "feature_gate.py": "b064c2c4675d354ec5cb5c6647782634c8139ca4233a5d732f408b6c2532f9a7",
    "comparison_gate.py": "c2d242581cc7551c6ce7d3aaf554f0cc18fd9b1f72677edd61ba95f91a7b5b92",
    "gate_invocation.py": "5c144b12c67910a4996aafe08e86e8939a2a1878168431850a99d22754ff9ded",
}

NEAR_R2 = 0.999 ** 2            # == 0.998001, the multivariate form of corr_threshold=0.999
EXACT_R2 = 1.0 - 1e-9
PARTIAL_R2 = 0.5                # report-only shoulder
COND_ELEVATED = 1e3             # report-only shoulder below feature_gate.COND_MAX
MIN_ROWS = 10                   # the floor feature_gate itself uses
MAX_SUBSET_SIZE = 3             # exhaustive minimal-subset search depth

BLOCKING = {
    "frozen_gate_digest_mismatch", "feature_gate_blocked",
    "block_membership_ambiguous", "column_missing_from_frame", "column_not_numeric",
    "offset_block_empty", "offset_is_placeholder", "insufficient_complete_rows",
    "design_column_non_finite", "design_column_zero_variance",
    "augmented_rank_deficient", "augmented_ill_conditioned", "affine_reconstruction",
    "offset_reconstructed_by_design", "offset_reconstructed_by_x",
    "offset_reconstructed_by_nuisance", "candidate_affine_in_offset",
    "fold_local_rank_deficient", "fold_local_ill_conditioned", "fold_local_zero_variance",
    "fold_local_offset_reconstructed", "cluster_split_across_folds",
    "adjudication_without_reason",
}

REPORT_ONLY = {"complete_case_row_loss", "offset_partially_explained", "condition_number_elevated"}

OFFSET_SUM = "__offset_sum__"   # synthetic column: the sum of the offset block


class DesignDependencyFailure(RuntimeError):
    """Raised on any blocking finding. FAIL CLOSED — the caller must not fit.

    ``.blocking`` carries the complete blocking list; ``.record`` the full audit record. The
    message is truncated for readability only.
    """

    def __init__(self, blocking: list[dict], record: dict | None = None):
        self.blocking = blocking
        self.record = record
        super().__init__(json.dumps(blocking[:6], default=str))


# ------------------------------------------------------------------------------------- utilities
def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def frozen_gate_digests() -> dict[str, str]:
    """Live sha256 of each pinned shared gate, computed from the bytes on disk right now."""
    return {name: _sha256_file(_PP / name) for name in FROZEN_GATE_DIGESTS}


def frozen_gate_status() -> dict[str, Any]:
    live = frozen_gate_digests()
    changed = sorted(n for n, d in live.items() if d != FROZEN_GATE_DIGESTS[n])
    return {"pinned": dict(FROZEN_GATE_DIGESTS), "live": live,
            "changed": changed, "all_unchanged": not changed,
            "feature_gate_RANK_TOL": float(fg.RANK_TOL),
            "feature_gate_COND_MAX": float(fg.COND_MAX)}


def canonical_digest(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _finding(kind: str, **kw) -> dict:
    out = {"kind": kind}
    out.update(kw)
    return out


def _as_float(frame: pd.DataFrame, col: str) -> np.ndarray:
    return pd.to_numeric(frame[col], errors="coerce").to_numpy(float)


def reconstruction_r2(y: np.ndarray, regressors: Sequence[np.ndarray]) -> float:
    """R^2 of the OLS of ``y`` on ``[1 | regressors]``, complete case, rank-safe (min-norm lstsq).

    Returns NaN — never 1.0 — when ``y`` is constant: "perfectly reconstructed" is not a
    meaningful claim about a column with no variance to reconstruct. Constant columns are caught
    by the zero-variance check instead.
    """
    y = np.asarray(y, float)
    m = np.isfinite(y)
    cols = []
    for z in regressors:
        z = np.asarray(z, float)
        m = m & np.isfinite(z)
        cols.append(z)
    if int(m.sum()) < MIN_ROWS:
        return float("nan")
    yv = y[m]
    ss_tot = float(np.sum((yv - yv.mean()) ** 2))
    if ss_tot == 0.0:
        return float("nan")
    if not cols:
        return 0.0
    Z = np.column_stack([np.ones(int(m.sum()))] + [c[m] for c in cols])
    b, *_ = np.linalg.lstsq(Z, yv, rcond=None)
    ss_res = float(np.sum((yv - Z @ b) ** 2))
    return float(1.0 - ss_res / ss_tot)


def minimal_reconstructing_subset(y: np.ndarray, frame_cols: Mapping[str, np.ndarray],
                                  threshold: float = NEAR_R2,
                                  max_size: int = MAX_SUBSET_SIZE) -> dict | None:
    """Smallest column subset (up to ``max_size``) whose affine span reaches ``threshold`` on y.

    Exhaustive within the depth limit, so "none found" means none of size <= max_size — never
    "none exists". The depth is reported in the result of the caller's record.
    """
    names = list(frame_cols)
    for k in range(1, min(max_size, len(names)) + 1):
        best = None
        for combo in itertools.combinations(names, k):
            r2 = reconstruction_r2(y, [frame_cols[c] for c in combo])
            if np.isfinite(r2) and r2 >= threshold and (best is None or r2 > best[1]):
                best = (combo, r2)
        if best is not None:
            return {"columns": list(best[0]), "size": k, "r2": round(float(best[1]), 12)}
    return None


def affine_relations(frame: pd.DataFrame, names: Sequence[str],
                     rank_tol: float | None = None) -> list[dict]:
    """Recover the EXACT affine relations spanning the design's numerical null space.

    Standardises exactly as ``feature_gate.design_rank_report`` does (mean-centre, divide by
    ``np.std``, sd==0 -> 1.0), takes the right singular vectors whose singular value is at or below
    ``RANK_TOL * sigma_max``, and maps each back to original units. Each relation is returned with

        sum_k coefficient[k] * column_k  ==  constant

    normalised so the largest |coefficient| is 1, plus the observed max |deviation| of that
    identity on the complete case — so the claim "this relation is exact" is checkable in the units
    of the data rather than in singular-value space.
    """
    rank_tol = float(fg.RANK_TOL if rank_tol is None else rank_tol)
    if not names:
        return []
    X = np.column_stack([_as_float(frame, c) for c in names])
    m = np.all(np.isfinite(X), axis=1)
    Xc = X[m]
    if len(Xc) < MIN_ROWS:
        return []
    mu = Xc.mean(0)
    sd = Xc.std(0)
    sd = np.where(sd == 0, 1.0, sd)
    Z = (Xc - mu) / sd
    U, sv, Vt = np.linalg.svd(Z, full_matrices=False)
    out: list[dict] = []
    if sv.size == 0 or sv.max() == 0:
        return out
    for j, s in enumerate(sv):
        if s > rank_tol * sv.max():
            continue
        v = Vt[j] / sd                        # back to original units
        scale = np.max(np.abs(v))
        if scale == 0:
            continue
        v = v / scale
        vals = Xc @ v
        const = float(vals.mean())
        dev = float(np.max(np.abs(vals - const)))
        coeffs = {c: float(round(v[i], 12)) for i, c in enumerate(names)}
        out.append({
            "coefficients": coeffs,
            "constant": round(const, 12),
            "max_abs_deviation": dev,
            "singular_value": float(s),
            "exact": bool(dev <= 1e-9 * max(1.0, abs(const))),
            "expression": _relation_text(coeffs, const),
        })
    return out


def _relation_text(coeffs: Mapping[str, float], const: float) -> str:
    parts = []
    for c, v in coeffs.items():
        if abs(v) < 1e-9:
            continue
        vr = round(v, 6)
        sign = "-" if vr < 0 else "+"
        mag = abs(vr)
        term = c if abs(mag - 1.0) < 1e-9 else f"{mag:g}*{c}"
        parts.append(f"{sign} {term}")
    body = " ".join(parts).lstrip("+ ").strip()
    return f"{body} == {round(const, 6):g}"


def offset_tie_group_probe(frame: pd.DataFrame, column: str, offset: np.ndarray,
                           min_groups: int = 20) -> dict:
    """NARROW, NON-EXHAUSTIVE probe at the nonlinear gap of GATE_INVOCATION_CONTRACT section 7.1.

    If ``column`` is constant within every tie group of the offset, it is a deterministic function
    of the offset regardless of the shape of that function. This detects exact functional
    determination; it detects nothing else, and a pass here is not evidence of nonlinear
    independence. Returns ``{"informative": False, ...}`` when the offset has too few tie groups.
    """
    o = np.asarray(offset, float)
    v = _as_float(frame, column)
    m = np.isfinite(o) & np.isfinite(v)
    if int(m.sum()) < MIN_ROWS:
        return {"informative": False, "reason": "insufficient rows"}
    df = pd.DataFrame({"o": o[m], "v": v[m]})
    g = df.groupby("o")["v"].nunique()
    multi = g[df.groupby("o")["v"].size() >= 2]
    n_groups = int(len(multi))
    if n_groups < min_groups:
        return {"informative": False, "reason": f"only {n_groups} tie groups of size >= 2",
                "tie_groups_size_ge_2": n_groups}
    constant_groups = int((multi == 1).sum())
    return {"informative": True, "tie_groups_size_ge_2": n_groups,
            "groups_where_column_constant": constant_groups,
            "exactly_determined": bool(constant_groups == n_groups)}


# ----------------------------------------------------------------------------------- the design
class Design:
    """A complete design declared as blocks. Nothing here is inferred; the caller declares it.

    ``offset`` may be a list of frame columns (multi-term offsets are real: a turnover arm carries
    ``log(exposure)`` and ``log(D)``), or a bare array, which is materialised as ``__offset__``.
    When the offset block has more than one column, its SUM is audited as well, because the sum is
    what actually enters the linear predictor at fixed coefficient 1.
    """

    def __init__(self, frame: pd.DataFrame, x: Sequence[str] = (),
                 offset: Sequence[str] | np.ndarray | pd.Series | None = None,
                 nuisance: Sequence[str] = (),
                 fold: str | Sequence | None = None,
                 cluster: str | Sequence | None = None,
                 label: str = ""):
        self.frame = frame.reset_index(drop=True)
        self.label = label
        self.x = list(x)
        self.nuisance = list(nuisance)
        self._synth: dict[str, np.ndarray] = {}
        if offset is None:
            self.offset: list[str] = []
        elif isinstance(offset, (list, tuple)) and all(isinstance(o, str) for o in offset):
            self.offset = list(offset)
        elif isinstance(offset, str):
            self.offset = [offset]
        else:
            arr = np.asarray(offset, float)
            if len(arr) != len(self.frame):
                raise ValueError(f"offset length {len(arr)} != frame rows {len(self.frame)}")
            self._synth["__offset__"] = arr
            self.frame = self.frame.assign(__offset__=arr)
            self.offset = ["__offset__"]
        self.fold_values = self._resolve(fold, "fold")
        self.cluster_values = self._resolve(cluster, "cluster")
        self.fold_name = fold if isinstance(fold, str) else ("__fold__" if fold is not None else None)
        self.cluster_name = (cluster if isinstance(cluster, str)
                             else ("__cluster__" if cluster is not None else None))

    def _resolve(self, spec, what: str):
        if spec is None:
            return None
        if isinstance(spec, str):
            if spec not in self.frame.columns:
                raise KeyError(f"{what} column {spec!r} not in frame")
            return self.frame[spec].to_numpy()
        arr = np.asarray(spec)
        if len(arr) != len(self.frame):
            raise ValueError(f"{what} length {len(arr)} != frame rows {len(self.frame)}")
        return arr

    @property
    def blocks(self) -> dict[str, list[str]]:
        return {"x": self.x, "offset": self.offset, "nuisance": self.nuisance}

    @property
    def all_columns(self) -> list[str]:
        return self.x + self.offset + self.nuisance

    def describe(self) -> dict:
        return {"label": self.label, "blocks": self.blocks, "n_rows": int(len(self.frame)),
                "fold": self.fold_name, "cluster": self.cluster_name}


# ------------------------------------------------------------------------------------- the audit
def audit_design(design: Design, target: np.ndarray | pd.Series | None = None,
                 adjudicated: Mapping[str, str] | None = None,
                 run_feature_gate: bool = True,
                 nonlinear_probe: bool = True,
                 max_subset_size: int = MAX_SUBSET_SIZE) -> dict:
    """Audit the COMPLETE design ``[X | offset | nuisance]``. Returns the record; never raises on a
    blocking finding — ``assert_design_identified`` is the fail-closed entry point.

    ``adjudicated`` maps ``"kind:column"`` (or bare ``"kind"``) to a non-empty REASON string. An
    adjudicated finding stays in ``findings`` and leaves ``blocking``, exactly as
    ``feature_gate`` treats its own adjudications. An adjudication with no reason is itself
    blocking, and is not itself adjudicable.
    """
    adjudicated = dict(adjudicated or {})
    findings: list[dict] = []
    rec: dict[str, Any] = {
        "algorithm_id": ALGORITHM_ID,
        "design": design.describe(),
        "thresholds": {"NEAR_R2": NEAR_R2, "EXACT_R2": EXACT_R2,
                       "RANK_TOL": float(fg.RANK_TOL), "COND_MAX": float(fg.COND_MAX),
                       "MIN_ROWS": MIN_ROWS, "max_subset_size": int(max_subset_size)},
        "adjudicated": {k: v for k, v in adjudicated.items()},
    }

    # --- 0. the shared gates must be the bytes this audit was built against ----------------
    gate = frozen_gate_status()
    rec["frozen_gates"] = gate
    for name in gate["changed"]:
        findings.append(_finding("frozen_gate_digest_mismatch", column=name,
                                 pinned=FROZEN_GATE_DIGESTS[name], live=gate["live"][name],
                                 detail="a pinned shared gate changed; this audit's thresholds and "
                                        "rank arithmetic are inherited from it and can no longer "
                                        "be assumed"))

    for k, v in adjudicated.items():
        if not isinstance(v, str) or not v.strip():
            findings.append(_finding("adjudication_without_reason", column=str(k),
                                     detail="an adjudication must carry a reason string"))

    # --- 1. structure ----------------------------------------------------------------------
    seen: dict[str, str] = {}
    for block, cols in design.blocks.items():
        for c in cols:
            if c in seen:
                findings.append(_finding("block_membership_ambiguous", column=c,
                                         blocks=[seen[c], block]))
            else:
                seen[c] = block
    missing = [c for c in design.all_columns if c not in design.frame.columns]
    for c in missing:
        findings.append(_finding("column_missing_from_frame", column=c))
    if not design.offset:
        findings.append(_finding("offset_block_empty",
                                 detail="an audit without an offset cannot test the free-slope "
                                        "dependency this module exists to test"))

    usable = [c for c in design.all_columns if c in design.frame.columns]
    for c in usable:
        raw = design.frame[c]
        num = pd.to_numeric(raw, errors="coerce")
        if num.isna().sum() > raw.isna().sum():
            findings.append(_finding("column_not_numeric", column=c,
                                     block=seen.get(c),
                                     n_uncastable=int(num.isna().sum() - raw.isna().sum())))

    if any(f["kind"] in {"column_missing_from_frame", "column_not_numeric"} for f in findings):
        return _finalise(rec, findings, adjudicated)

    # --- 2. complete case and per-column sanity --------------------------------------------
    cols = {c: _as_float(design.frame, c) for c in usable}
    if design.offset and len(design.offset) > 1:
        cols[OFFSET_SUM] = np.sum([cols[c] for c in design.offset], axis=0)
    offset_cols = list(design.offset) + ([OFFSET_SUM] if len(design.offset) > 1 else [])
    aug_names = design.x + design.offset + design.nuisance     # the audited augmented design

    if aug_names:
        M = np.column_stack([cols[c] for c in aug_names])
        complete = np.all(np.isfinite(M), axis=1)
    else:
        complete = np.ones(len(design.frame), bool)
    n_rows, n_complete = int(len(design.frame)), int(complete.sum())
    rec["n_rows"] = n_rows
    rec["n_complete_rows"] = n_complete
    if n_complete < n_rows:
        findings.append(_finding("complete_case_row_loss", n_rows=n_rows,
                                 n_complete_rows=n_complete, n_dropped=n_rows - n_complete))
    if n_complete < MIN_ROWS:
        findings.append(_finding("insufficient_complete_rows", n_complete_rows=n_complete,
                                 floor=MIN_ROWS))
        return _finalise(rec, findings, adjudicated)

    per_col: dict[str, dict] = {}
    for c in aug_names + [x for x in offset_cols if x not in aug_names]:
        v = cols[c]
        finite = np.isfinite(v)
        has_inf = bool(np.any(np.isinf(v)))
        if has_inf or not finite.any():
            findings.append(_finding("design_column_non_finite", column=c, block=seen.get(c),
                                     n_inf=int(np.sum(np.isinf(v))),
                                     n_finite=int(finite.sum())))
        vc = v[complete]
        sd = float(np.std(vc)) if len(vc) else float("nan")
        per_col[c] = {"block": seen.get(c, "offset_sum"), "std_complete_case": sd,
                      "n_missing": int((~finite).sum()),
                      "n_distinct": int(pd.Series(vc).nunique(dropna=True))}
        if np.isfinite(sd) and sd == 0.0:
            findings.append(_finding("design_column_zero_variance", column=c, block=seen.get(c)))
    rec["columns"] = per_col

    for c in design.offset:
        vc = cols[c][complete]
        if np.all(~np.isfinite(vc)) or float(np.std(vc)) == 0.0 or np.all(vc == 0.0):
            findings.append(_finding("offset_is_placeholder", column=c,
                                     std=float(np.std(vc)) if len(vc) else float("nan"),
                                     detail="a constant / zero / all-NaN offset carries no "
                                            "per-row exposure and makes every offset test vacuous"))

    # --- 3. feature_gate FIRST, on X, verbatim ---------------------------------------------
    if run_feature_gate and design.x:
        off_arg = None
        if design.offset:
            off_arg = cols[OFFSET_SUM] if OFFSET_SUM in cols else cols[design.offset[0]]
        tgt = None if target is None else np.asarray(target, float)
        try:
            fg_rec = fg.audit(design.frame, list(design.x), offset=off_arg, target=tgt)
            rec["feature_gate_record"] = {
                "passed": bool(fg_rec["passed"]),
                "finding_kinds": sorted({f["kind"] for f in fg_rec["findings"]}),
                "design_rank": fg_rec["design_rank"],
                "arguments_supplied": {"offset": off_arg is not None, "target": tgt is not None},
            }
        except fg.FeatureGateFailure as exc:
            blocked = json.loads(str(exc))
            rec["feature_gate_record"] = {"passed": False, "blocking": blocked,
                                          "arguments_supplied": {"offset": off_arg is not None,
                                                                 "target": tgt is not None}}
            findings.append(_finding("feature_gate_blocked",
                                     kinds=sorted({b["kind"] for b in blocked}),
                                     detail="the frozen gate blocked X; this audit never relaxes it"))
    else:
        rec["feature_gate_record"] = {"ran": False,
                                      "reason": "no substantive columns" if not design.x
                                                else "caller disabled"}

    # --- 4. augmented rank and conditioning, via feature_gate's OWN frozen function ----------
    aug_frame = pd.DataFrame({c: cols[c] for c in aug_names})
    rank = fg.design_rank_report(aug_frame, aug_names)
    rank["produced_by"] = "feature_gate.design_rank_report"
    rec["augmented_rank"] = rank
    if rank.get("checked"):
        if not rank["full_rank"]:
            findings.append(_finding("augmented_rank_deficient", column="__augmented_design__",
                                     numerical_rank=rank["numerical_rank"],
                                     n_columns=rank["n_features"],
                                     smallest_singular_value=(rank["singular_values"][-1]
                                                              if rank["singular_values"] else None),
                                     condition_number=rank["condition_number"],
                                     detail="rank([X|offset|nuisance]) < n_columns: some direction "
                                            "of the complete design is unidentified"))
        elif not rank["condition_ok"]:
            findings.append(_finding("augmented_ill_conditioned", column="__augmented_design__",
                                     condition_number=rank["condition_number"],
                                     ceiling=float(fg.COND_MAX)))
        elif rank["condition_number"] > COND_ELEVATED:
            findings.append(_finding("condition_number_elevated", column="__augmented_design__",
                                     condition_number=rank["condition_number"],
                                     shoulder=COND_ELEVATED, ceiling=float(fg.COND_MAX)))

    # --- 5. affine reconstruction, per column and as recovered relations ---------------------
    per_column_r2: dict[str, float] = {}
    for c in aug_names:
        others = [cols[o] for o in aug_names if o != c]
        r2 = reconstruction_r2(cols[c], others)
        per_column_r2[c] = None if not np.isfinite(r2) else round(float(r2), 12)
        if np.isfinite(r2) and r2 >= NEAR_R2:
            findings.append(_finding("affine_reconstruction", column=c, block=seen.get(c),
                                     r2=round(float(r2), 12),
                                     exact=bool(r2 >= EXACT_R2),
                                     regressors=[o for o in aug_names if o != c],
                                     threshold=NEAR_R2))
    relations = affine_relations(aug_frame, aug_names)
    rec["affine_reconstruction"] = {"r2_column_on_rest": per_column_r2,
                                    "null_space_relations": relations,
                                    "threshold": NEAR_R2}

    # --- 6. offset reconstruction — the free-slope dimension ---------------------------------
    off_report: dict[str, Any] = {}
    x_regs = [cols[c] for c in design.x]
    nu_regs = [cols[c] for c in design.nuisance]
    for oc in offset_cols:
        y = cols[oc]
        r2_x = reconstruction_r2(y, x_regs) if design.x else float("nan")
        r2_nu = reconstruction_r2(y, nu_regs) if design.nuisance else float("nan")
        r2_all = reconstruction_r2(y, x_regs + nu_regs) if (design.x or design.nuisance) else float("nan")
        pool = {c: cols[c] for c in design.x + design.nuisance}
        subset = (minimal_reconstructing_subset(y, pool, max_size=max_subset_size)
                  if pool and np.isfinite(r2_all) and r2_all >= NEAR_R2 else None)
        entry = {"r2_on_x": _r(r2_x), "r2_on_nuisance": _r(r2_nu), "r2_on_design": _r(r2_all),
                 "minimal_reconstructing_subset": subset,
                 "subset_search_depth": int(max_subset_size)}
        off_report[oc] = entry
        if np.isfinite(r2_all) and r2_all >= NEAR_R2:
            findings.append(_finding("offset_reconstructed_by_design", column=oc,
                                     r2=round(float(r2_all), 12), threshold=NEAR_R2,
                                     exact=bool(r2_all >= EXACT_R2),
                                     minimal_subset=subset,
                                     detail="the design's affine span contains the offset, so the "
                                            "fit has a FREE SLOPE on it that a featureless control "
                                            "with the same offset does not have"))
            if np.isfinite(r2_x) and r2_x >= NEAR_R2:
                findings.append(_finding("offset_reconstructed_by_x", column=oc,
                                         r2=round(float(r2_x), 12), threshold=NEAR_R2))
            if np.isfinite(r2_nu) and r2_nu >= NEAR_R2:
                findings.append(_finding("offset_reconstructed_by_nuisance", column=oc,
                                         r2=round(float(r2_nu), 12), threshold=NEAR_R2,
                                         detail="the NUISANCE block alone reconstructs the offset; "
                                                "an innocent X does not make the design innocent"))
        elif np.isfinite(r2_all) and r2_all >= PARTIAL_R2:
            findings.append(_finding("offset_partially_explained", column=oc,
                                     r2=round(float(r2_all), 12), threshold=NEAR_R2))

    # per-candidate affine-in-offset (the multivariate generalisation of feature_gate's pairwise
    # deterministic_transform_of_offset), plus the optional nonlinear probe
    cand_report: dict[str, Any] = {}
    primary_offset = cols[OFFSET_SUM] if OFFSET_SUM in cols else (
        cols[design.offset[0]] if design.offset else None)
    if primary_offset is not None:
        for c in design.x:
            r2 = reconstruction_r2(cols[c], [primary_offset])
            m = np.isfinite(cols[c]) & np.isfinite(primary_offset)
            corr = (float(np.corrcoef(cols[c][m], primary_offset[m])[0, 1])
                    if m.sum() >= MIN_ROWS and np.std(cols[c][m]) > 0
                    and np.std(primary_offset[m]) > 0 else float("nan"))
            entry = {"r2_on_offset": _r(r2), "pearson_r": _r(corr)}
            if nonlinear_probe:
                entry["tie_group_probe"] = offset_tie_group_probe(design.frame, c, primary_offset)
            cand_report[c] = entry
            if np.isfinite(r2) and r2 >= NEAR_R2:
                findings.append(_finding("candidate_affine_in_offset", column=c,
                                         r2=round(float(r2), 12), pearson_r=_r(corr),
                                         threshold=NEAR_R2))
    rec["offset_reconstruction"] = off_report
    rec["candidate_vs_offset"] = cand_report
    rec["grants_offset_slope_freedom"] = bool(
        any(f["kind"] in {"offset_reconstructed_by_design", "candidate_affine_in_offset"}
            for f in findings))

    # --- 7. fold-local repetition ------------------------------------------------------------
    if design.fold_values is not None:
        rec["folds"] = _fold_audits(design, cols, aug_names, offset_cols, findings)
        if design.cluster_values is not None:
            splits = _cluster_splits(design)
            rec["cluster_fold_check"] = splits
            if splits["n_clusters_split"] > 0:
                findings.append(_finding("cluster_split_across_folds",
                                         n_clusters_split=splits["n_clusters_split"],
                                         examples=splits["examples"],
                                         detail="a cluster's rows must never be split across folds"))
    return _finalise(rec, findings, adjudicated)


def _r(x) -> float | None:
    x = float(x)
    return None if not np.isfinite(x) else round(x, 12)


def _fold_audits(design: Design, cols: dict[str, np.ndarray], aug_names: list[str],
                 offset_cols: list[str], findings: list[dict]) -> dict:
    out: dict[str, Any] = {}
    folds = pd.Series(design.fold_values)
    for fv in sorted(folds.dropna().unique(), key=str):
        idx = (folds == fv).to_numpy()
        sub = pd.DataFrame({c: cols[c][idx] for c in set(aug_names) | set(offset_cols)})
        entry: dict[str, Any] = {"n_rows": int(idx.sum())}
        # zero variance inside the fold
        zero = []
        for c in aug_names:
            v = sub[c].to_numpy(float)
            v = v[np.isfinite(v)]
            if len(v) and float(np.std(v)) == 0.0:
                zero.append(c)
        entry["zero_variance_columns"] = zero
        for c in zero:
            findings.append(_finding("fold_local_zero_variance", column=c, fold=str(fv),
                                     n_rows=int(idx.sum()),
                                     detail="healthy pooled, degenerate in this fold"))
        rank = fg.design_rank_report(sub, aug_names) if aug_names else {"checked": False}
        entry["rank"] = {k: rank.get(k) for k in
                         ("checked", "n_complete_rows", "n_features", "numerical_rank",
                          "full_rank", "condition_number", "condition_ok")}
        if rank.get("checked"):
            if not rank["full_rank"]:
                findings.append(_finding("fold_local_rank_deficient", fold=str(fv),
                                         numerical_rank=rank["numerical_rank"],
                                         n_columns=rank["n_features"],
                                         condition_number=rank["condition_number"]))
            elif not rank["condition_ok"]:
                findings.append(_finding("fold_local_ill_conditioned", fold=str(fv),
                                         condition_number=rank["condition_number"],
                                         ceiling=float(fg.COND_MAX)))
        fo = {}
        regs = [sub[c].to_numpy(float) for c in design.x + design.nuisance]
        for oc in offset_cols:
            r2 = reconstruction_r2(sub[oc].to_numpy(float), regs) if regs else float("nan")
            fo[oc] = _r(r2)
            if np.isfinite(r2) and r2 >= NEAR_R2:
                findings.append(_finding("fold_local_offset_reconstructed", column=oc,
                                         fold=str(fv), r2=round(float(r2), 12)))
        entry["r2_offset_on_design"] = fo
        out[str(fv)] = entry
    return out


def _cluster_splits(design: Design) -> dict:
    df = pd.DataFrame({"cluster": design.cluster_values, "fold": design.fold_values})
    g = df.groupby("cluster")["fold"].nunique()
    split = g[g > 1]
    return {"n_clusters": int(len(g)), "n_clusters_split": int(len(split)),
            "examples": [str(c) for c in list(split.index[:5])]}


def _finalise(rec: dict, findings: list[dict], adjudicated: Mapping[str, str]) -> dict:
    def is_adjudicated(f: dict) -> bool:
        if f["kind"] == "adjudication_without_reason":
            return False                      # never self-adjudicable
        keys = [f"{f['kind']}:{f.get('column', '')}", f["kind"]]
        return any(isinstance(adjudicated.get(k), str) and adjudicated[k].strip() for k in keys)

    for f in findings:
        if f["kind"] in BLOCKING and is_adjudicated(f):
            f["adjudicated"] = True
    blocking = [f for f in findings
                if f["kind"] in BLOCKING and not f.get("adjudicated", False)]
    rec["findings"] = findings
    rec["finding_kinds"] = sorted({f["kind"] for f in findings})
    rec["blocking"] = blocking
    rec["passed"] = len(blocking) == 0
    rec["note"] = ("a converging optimiser does not validate an unidentified design; and a pass "
                   "here is necessary, never sufficient — the affine tests are blind to exact "
                   "nonlinear redundancy (GATE_INVOCATION_CONTRACT section 7.1)")
    rec["receipt_sha256"] = audit_receipt(rec)
    return rec


def audit_receipt(record: Mapping[str, Any]) -> str:
    """sha256 over the audit's decision-bearing content — stable across reruns, not over time."""
    payload = {
        "algorithm_id": record.get("algorithm_id"),
        "design": record.get("design"),
        "thresholds": record.get("thresholds"),
        "frozen_gates_live": (record.get("frozen_gates") or {}).get("live"),
        "augmented_rank": record.get("augmented_rank"),
        "affine_reconstruction": record.get("affine_reconstruction"),
        "offset_reconstruction": record.get("offset_reconstruction"),
        "finding_kinds": record.get("finding_kinds"),
        "passed": record.get("passed"),
    }
    return canonical_digest(payload)


def assert_design_identified(design: Design, **kw) -> dict:
    """FAIL-CLOSED entry point. Audit, and raise ``DesignDependencyFailure`` on any blocking
    finding. Call this BEFORE any fit; a returned record is the evidence the call site must keep."""
    rec = audit_design(design, **kw)
    if rec["blocking"]:
        raise DesignDependencyFailure(rec["blocking"], rec)
    return rec
