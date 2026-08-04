#!/usr/bin/env python3
"""offset_dependency_guard.py — CALL-SITE guard for S4 / S5.

WHAT THIS IS
------------
A task-specific wrapper that runs at the *call site*, before any fit, on the COMPLETE design

        [ offset | nuisance | candidate ]

`feature_gate.py` audits ``X`` only. Its ``design_rank_report`` never sees the offset, and its
pairwise checks cannot see a three-term dependency. That is not a hypothetical gap: on the frozen
`team_possession_prior_v1` artifact, the design ``{own_est, opp_est}`` with
``offset = projected_team_off_possessions`` satisfies

        own_est + opp_est == 2 * projected_team_off_possessions      (max |deviation| = 0.0)

and `feature_gate.audit` returns ``findings: []``, ``passed: True``.

This module does NOT modify, weaken, extend or replace `feature_gate.py`. It IMPORTS it, reuses its
frozen constants (``RANK_TOL``, ``COND_MAX``) and its frozen ``design_rank_report``, and adds the
augmented-design and family-hygiene checks that must be enforced by the caller.

Epistemic status: INFRASTRUCTURE + task-specific INVARIANT. It proves a design cannot smuggle the
offset into ``substantive_features``. It establishes nothing about which mechanism is real.

THRESHOLDS
----------
``NEAR_R2 = 0.999 ** 2 = 0.998001``. For a single regressor R^2 == r^2, so this reduces EXACTLY to
`feature_gate`'s ``corr_threshold = 0.999`` in the pairwise case and extends the same strictness to
subsets. ``EXACT_R2 = 1 - 1e-9`` separates "exact" from "near-exact" for reporting only; both are
blocking.

BLOCKING FINDINGS
-----------------
    offset_missing                              the guard was invoked without an offset
    offset_is_placeholder                       offset constant / all-NaN / all-zero
    candidate_affine_in_offset                  R^2(c ~ 1 + offset) >= NEAR_R2
    candidate_monotone_transform_of_offset      |spearman(c, offset)| >= 0.999
    candidate_exactly_determined_by_offset       c constant within every offset tie-group
    candidate_is_function_of_incumbent_projection   same three tests against the projection
    pair_reconstructs_offset                    R^2(offset ~ 1 + a + b) >= NEAR_R2
    design_reconstructs_offset                  R^2(offset ~ 1 + [nuisance|candidates]) >= NEAR_R2
    augmented_rank_deficient                    rank([offset|nuisance|candidates]) < n_columns
    augmented_ill_conditioned                   condition number > feature_gate.COND_MAX
    fold_local_rank_deficient                   any of the above, inside a single fold
    fold_local_reconstructs_offset              per-fold offset reconstruction
    fold_local_zero_variance                    a design column is constant inside a fold
    contrast_not_preregistered                  a contrast column with no preregistration record
    contrast_prereg_digest_mismatch             the preregistration record was edited
    contrast_formula_mismatch                   column values != the declared exact formula
    calibration_parameter_in_substantive_arm    a calibration column inside a SUBSTANTIVE arm
    recalibration_family_incomplete             RECALIBRATION arm without nested null / multiplicity
    mixed_family_arm                            RECALIBRATION arm carrying a substantive column
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_PP = Path(__file__).resolve().parents[2]          # experiments/player_program
if str(_PP) not in sys.path:
    sys.path.insert(0, str(_PP))

import feature_gate as fg                                                    # noqa: E402

# frozen digest of the shared gate this guard is built against (bytes, not prose)
FEATURE_GATE_SHA256 = "b064c2c4675d354ec5cb5c6647782634c8139ca4233a5d732f408b6c2532f9a7"

NEAR_R2 = 0.999 ** 2          # == 0.998001; the multivariate generalisation of corr_threshold
EXACT_R2 = 1.0 - 1e-9
SPEARMAN_THRESHOLD = 0.999
MIN_TIE_GROUPS = 20           # below this, the exact-determination test is not informative
MIN_ROWS = 10                 # same floor feature_gate uses

BLOCKING = {
    "offset_missing", "offset_is_placeholder",
    "candidate_affine_in_offset", "candidate_monotone_transform_of_offset",
    "candidate_exactly_determined_by_offset",
    "candidate_is_function_of_incumbent_projection",
    "pair_reconstructs_offset", "design_reconstructs_offset",
    "augmented_rank_deficient", "augmented_ill_conditioned",
    "fold_local_rank_deficient", "fold_local_reconstructs_offset",
    "fold_local_zero_variance",
    "contrast_not_preregistered", "contrast_prereg_digest_mismatch",
    "contrast_formula_mismatch",
    "calibration_parameter_in_substantive_arm", "recalibration_family_incomplete",
    "mixed_family_arm",
}

SUBSTANTIVE = "SUBSTANTIVE"
RECALIBRATION = "RECALIBRATION"

RECALIBRATION_REQUIRED_KEYS = (
    "family_id",                 # names the family this arm belongs to
    "nested_null_id",            # the nested null this arm is tested against
    "k0_carries_offset_slope",   # the matched control must have the SAME slope freedom (S4)
    "n_hypotheses_in_family",    # family size, declared before results
    "multiplicity_procedure",    # e.g. holm / bh, declared before results
    "family_alpha",
)


class OffsetDependencyFailure(RuntimeError):
    """Raised on any blocking finding. Fail closed: the caller must not fit.

    Carries the COMPLETE blocking list on ``.blocking``; the message is truncated for readability.
    """

    def __init__(self, blocking: list[dict], record: dict | None = None):
        self.blocking = blocking
        self.record = record
        super().__init__(json.dumps(blocking[:6], default=str))


# --------------------------------------------------------------------------------------- helpers
def feature_gate_digest() -> str:
    return hashlib.sha256((_PP / "feature_gate.py").read_bytes()).hexdigest()


def canonical_digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _r2(y: np.ndarray, regressors: list[np.ndarray]) -> float:
    """R^2 of the OLS of y on [1 | regressors]. Rank-safe (lstsq min-norm solution)."""
    y = np.asarray(y, float)
    m = np.isfinite(y)
    cols = []
    for z in regressors:
        z = np.asarray(z, float)
        m &= np.isfinite(z)
        cols.append(z)
    if m.sum() < MIN_ROWS:
        return float("nan")
    yv = y[m]
    ss_tot = float(np.sum((yv - yv.mean()) ** 2))
    if ss_tot == 0.0:
        return float("nan")          # constant y: reconstruction is undefined, not "perfect"
    Z = np.column_stack([np.ones(m.sum())] + [c[m] for c in cols])
    b, *_ = np.linalg.lstsq(Z, yv, rcond=None)
    ss_res = float(np.sum((yv - Z @ b) ** 2))
    return 1.0 - ss_res / ss_tot


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < MIN_ROWS:
        return float("nan")
    ra = pd.Series(a[m]).rank().to_numpy()
    rb = pd.Series(b[m]).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def _exactly_determined(values: np.ndarray, by: np.ndarray) -> dict:
    """Is `values` constant within every exact tie-group of `by`?

    This is the fit-free, nonlinearity-proof test the pairwise/SVD checks cannot do. It is only
    informative when `by` actually has ties; the projection has 1,014 distinct values over 2,982
    rows, because both sides of a game share one projection, so it is informative here.
    """
    m = np.isfinite(values) & np.isfinite(by)
    if m.sum() < MIN_ROWS:
        return {"informative": False, "reason": "insufficient rows"}
    df = pd.DataFrame({"v": values[m], "k": by[m]})
    g = df.groupby("k")["v"].agg(["nunique", "size"])
    tied = g[g["size"] >= 2]
    if len(tied) < MIN_TIE_GROUPS:
        return {"informative": False, "reason": "too few tie groups", "n_tie_groups": int(len(tied))}
    n_const = int((tied["nunique"] == 1).sum())
    return {"informative": True, "n_tie_groups": int(len(tied)),
            "n_groups_where_constant": n_const,
            "determined": bool(n_const == len(tied))}


# ---------------------------------------------------------------- restricted formula evaluation
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


def eval_contrast_formula(formula: str, df: pd.DataFrame) -> np.ndarray:
    """Evaluate a preregistered EXACT formula. Whitelist only: names, numbers, + - * / and unary -.

    Deliberately not `eval`. A contrast is admissible only if its declared formula can be
    re-derived from named columns and reproduces the column's bytes.
    """
    tree = ast.parse(formula, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
            a, b = ev(node.left), ev(node.right)
            return {ast.Add: np.add, ast.Sub: np.subtract,
                    ast.Mult: np.multiply, ast.Div: np.divide}[type(node.op)](a, b)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = ev(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in df.columns:
                raise ValueError(f"formula references unknown column {node.id!r}")
            return df[node.id].to_numpy(float)
        raise ValueError(f"formula construct not permitted: {ast.dump(node)[:80]}")

    return np.asarray(ev(tree), float)


# ------------------------------------------------------------------------------------ the guard
def audit_augmented_design(
    df: pd.DataFrame,
    candidate_features: list[str],
    offset,                                   # REQUIRED and positional: no candidate-only audits
    *,
    nuisance_features: list[str] | None = None,
    incumbent_projection=None,
    fold_ids=None,
    declared_family: str = SUBSTANTIVE,
    recalibration_declaration: dict | None = None,
    preregistered_contrasts: list[dict] | None = None,
    prereg_digest_expected: str | None = None,
    contrast_atol: float = 1e-12,
    raise_on_block: bool = True,
) -> dict:
    """Audit the COMPLETE design. Returns a machine-readable record; raises on a blocking finding.

    `offset` is the exposure offset actually handed to the estimator, in the estimator's units.
    `incumbent_projection` is the incumbent's output on its own scale; supply it whenever it
    differs from `offset` (e.g. offset = log(projection)), because "an exact function of the
    incumbent projection" is a distinct rejection ground from "affine in the offset".
    """
    nuisance_features = list(nuisance_features or [])
    candidate_features = list(candidate_features)
    design_names = nuisance_features + candidate_features
    findings: list[dict] = []

    # ---- the offset must exist and must not be a placeholder ------------------------------
    if offset is None:
        findings.append({"kind": "offset_missing", "feature": "__offset__",
                         "detail": "the audit must run on [offset | nuisance | candidate]"})
        rec = _finalise(df, design_names, candidate_features, nuisance_features,
                        findings, None, declared_family, raise_on_block)
        return rec
    o = np.asarray(offset, float)
    if len(o) != len(df):
        raise ValueError(f"offset length {len(o)} != n_rows {len(df)}")
    fin_o = np.isfinite(o)
    if fin_o.sum() < MIN_ROWS or float(np.nanstd(o)) == 0.0 or np.allclose(o[fin_o], 0.0):
        findings.append({"kind": "offset_is_placeholder", "feature": "__offset__",
                         "n_finite": int(fin_o.sum()), "std": float(np.nanstd(o)),
                         "detail": "a constant, empty or all-zero offset neutralises every "
                                   "augmented check"})

    proj = None if incumbent_projection is None else np.asarray(incumbent_projection, float)
    if proj is not None and len(proj) != len(df):
        raise ValueError("incumbent_projection length != n_rows")

    # ---- per-candidate dependence on the offset and on the projection ----------------------
    for c in design_names:
        v = df[c].to_numpy(float)
        for ref_name, ref, kinds in (
            ("offset", o, ("candidate_affine_in_offset",
                           "candidate_monotone_transform_of_offset",
                           "candidate_exactly_determined_by_offset")),
            ("incumbent_projection", proj, ("candidate_is_function_of_incumbent_projection",) * 3),
        ):
            if ref is None:
                continue
            r2 = _r2(v, [ref])
            if np.isfinite(r2) and r2 >= NEAR_R2:
                findings.append({"kind": kinds[0], "feature": c, "reference": ref_name,
                                 "r2": round(float(r2), 12),
                                 "exact": bool(r2 >= EXACT_R2), "threshold": NEAR_R2})
                continue
            rho = _spearman(v, ref)
            if np.isfinite(rho) and abs(rho) >= SPEARMAN_THRESHOLD:
                findings.append({"kind": kinds[1], "feature": c, "reference": ref_name,
                                 "spearman": round(float(rho), 12),
                                 "threshold": SPEARMAN_THRESHOLD,
                                 "detail": "linear checks miss log/power/monotone reparameterisations"})
                continue
            det = _exactly_determined(v, ref)
            if det.get("informative") and det.get("determined"):
                findings.append({"kind": kinds[2], "feature": c, "reference": ref_name, **det})

    # ---- joint reconstruction: pairs, then the whole design --------------------------------
    for i, a in enumerate(design_names):
        for b in design_names[i + 1:]:
            r2 = _r2(o, [df[a].to_numpy(float), df[b].to_numpy(float)])
            if np.isfinite(r2) and r2 >= NEAR_R2:
                r2a, r2b = _r2(o, [df[a].to_numpy(float)]), _r2(o, [df[b].to_numpy(float)])
                findings.append({"kind": "pair_reconstructs_offset", "feature": a, "other": b,
                                 "r2_pair": round(float(r2), 12),
                                 "r2_a_alone": round(float(r2a), 12),
                                 "r2_b_alone": round(float(r2b), 12),
                                 "threshold": NEAR_R2,
                                 "detail": "neither column alone need trip any pairwise check"})

    r2_full = _r2(o, [df[c].to_numpy(float) for c in design_names]) if design_names else float("nan")
    if np.isfinite(r2_full) and r2_full >= NEAR_R2:
        findings.append({"kind": "design_reconstructs_offset", "feature": "__design__",
                         "r2": round(float(r2_full), 12), "threshold": NEAR_R2,
                         "n_design_columns": len(design_names),
                         "detail": "the offset supplies zero constraint: the arm is a free re-fit "
                                   "of the incumbent's own arithmetic"})

    # ---- augmented rank, reusing the FROZEN feature_gate implementation --------------------
    aug = df.copy()
    aug["__offset__"] = o
    aug_names = ["__offset__"] + design_names
    aug_rank = fg.design_rank_report(aug, aug_names)
    if aug_rank["checked"]:
        if not aug_rank["full_rank"]:
            findings.append({"kind": "augmented_rank_deficient", "feature": "__augmented_design__",
                             "numerical_rank": aug_rank["numerical_rank"],
                             "n_columns": aug_rank["n_features"],
                             "smallest_singular_value": (aug_rank["singular_values"][-1]
                                                         if aug_rank["singular_values"] else None),
                             "condition_number": aug_rank["condition_number"],
                             "columns": aug_names})
        elif not aug_rank["condition_ok"]:
            findings.append({"kind": "augmented_ill_conditioned", "feature": "__augmented_design__",
                             "condition_number": aug_rank["condition_number"],
                             "ceiling": fg.COND_MAX, "columns": aug_names})

    # ---- fold-local: identifiability is a per-fold property (GATE_INVOCATION_CONTRACT s1) --
    fold_records: dict[str, dict] = {}
    if fold_ids is not None:
        f = pd.Series(np.asarray(fold_ids)).reset_index(drop=True)
        for fold in sorted(f.unique(), key=str):
            m = (f == fold).to_numpy()
            sub = df.loc[m].reset_index(drop=True)
            osub = o[m]
            asub = sub.copy()
            asub["__offset__"] = osub
            rr = fg.design_rank_report(asub, aug_names)
            r2f = (_r2(osub, [sub[c].to_numpy(float) for c in design_names])
                   if design_names else float("nan"))
            zero_var = [c for c in design_names
                        if float(np.nanstd(sub[c].to_numpy(float))) == 0.0]
            fold_records[str(fold)] = {"n_rows": int(m.sum()), "rank_report": rr,
                                       "r2_offset_on_design": (None if not np.isfinite(r2f)
                                                               else round(float(r2f), 12)),
                                       "zero_variance_columns": zero_var}
            if rr["checked"] and not rr["full_rank"]:
                findings.append({"kind": "fold_local_rank_deficient", "feature": "__augmented_design__",
                                 "fold": str(fold), "numerical_rank": rr["numerical_rank"],
                                 "n_columns": rr["n_features"],
                                 "condition_number": rr["condition_number"]})
            if np.isfinite(r2f) and r2f >= NEAR_R2:
                findings.append({"kind": "fold_local_reconstructs_offset", "feature": "__design__",
                                 "fold": str(fold), "r2": round(float(r2f), 12)})
            for c in zero_var:
                findings.append({"kind": "fold_local_zero_variance", "feature": c,
                                 "fold": str(fold)})

    # ---- preregistered contrasts ----------------------------------------------------------
    prereg = {r["name"]: r for r in (preregistered_contrasts or [])}
    contrast_records = {}
    if preregistered_contrasts is not None:
        d = canonical_digest(preregistered_contrasts)
        contrast_records["prereg_digest"] = d
        if prereg_digest_expected is not None and d != prereg_digest_expected:
            findings.append({"kind": "contrast_prereg_digest_mismatch", "feature": "__prereg__",
                             "computed": d, "expected": prereg_digest_expected,
                             "detail": "the preregistration record does not match the frozen digest"})
    for c in design_names:
        rec = prereg.get(c)
        if rec is None:
            continue                              # ordinary column: not claimed as a contrast
        got = df[c].to_numpy(float)
        try:
            want = eval_contrast_formula(rec["formula"], df)
        except Exception as exc:                                             # noqa: BLE001
            findings.append({"kind": "contrast_formula_mismatch", "feature": c,
                             "error": str(exc)})
            continue
        m = np.isfinite(got) & np.isfinite(want)
        max_dev = float(np.max(np.abs(got[m] - want[m]))) if m.sum() else float("inf")
        n_bad = int(np.sum(np.isfinite(got) != np.isfinite(want)))
        contrast_records[c] = {"formula": rec["formula"], "max_abs_deviation": max_dev,
                               "n_finiteness_mismatches": n_bad, "n_compared": int(m.sum())}
        if max_dev > contrast_atol or n_bad > 0:
            findings.append({"kind": "contrast_formula_mismatch", "feature": c,
                             "formula": rec["formula"], "max_abs_deviation": max_dev,
                             "n_finiteness_mismatches": n_bad, "atol": contrast_atol})

    # a column DECLARED as a contrast by the caller must be preregistered
    for c in [n for n in design_names if str(n).startswith("contrast_")]:
        if c not in prereg:
            findings.append({"kind": "contrast_not_preregistered", "feature": c,
                             "detail": "a contrast column requires a preregistered exact formula"})

    # ---- hypothesis-family hygiene (S4) ---------------------------------------------------
    CALIBRATION_KINDS = ("candidate_affine_in_offset",
                         "candidate_monotone_transform_of_offset",
                         "candidate_exactly_determined_by_offset",
                         "candidate_is_function_of_incumbent_projection")
    calibration_cols = sorted({f["feature"] for f in findings if f["kind"] in CALIBRATION_KINDS})
    if declared_family == SUBSTANTIVE:
        for c in calibration_cols:
            findings.append({"kind": "calibration_parameter_in_substantive_arm", "feature": c,
                             "detail": "a free slope on the offset is RECALIBRATION, not feature "
                                       "value; it belongs to its own hypothesis family with its "
                                       "own nested null and multiplicity accounting"})
    elif declared_family == RECALIBRATION:
        decl = recalibration_declaration or {}
        missing = [k for k in RECALIBRATION_REQUIRED_KEYS if k not in decl]
        if missing:
            findings.append({"kind": "recalibration_family_incomplete", "feature": "__family__",
                             "missing_keys": missing})
        elif decl.get("k0_carries_offset_slope") is not True:
            findings.append({"kind": "recalibration_family_incomplete", "feature": "__family__",
                             "detail": "K0_MATCHED must carry the same offset-slope freedom as the "
                                       "challenger, else challenger_vs_k0 measures recalibration"})
        substantive = [c for c in design_names if c not in calibration_cols]
        if substantive:
            findings.append({"kind": "mixed_family_arm", "feature": "__family__",
                             "substantive_columns": substantive,
                             "detail": "a RECALIBRATION arm may carry only functions of the offset "
                                       "or the incumbent projection"})
        # Under a DECLARED recalibration family the offset redundancy IS the hypothesis, so the
        # redundancy findings are recorded but downgraded to non-blocking. The protection moves to
        # the nested null, the family accounting and mixed_family_arm -- all of which stay blocking.
        for f in findings:
            if f["kind"] in CALIBRATION_KINDS + ("pair_reconstructs_offset",
                                                 "design_reconstructs_offset",
                                                 "augmented_rank_deficient",
                                                 "augmented_ill_conditioned",
                                                 "fold_local_rank_deficient",
                                                 "fold_local_reconstructs_offset"):
                f["original_kind"] = f["kind"]
                f["kind"] = "expected_under_declared_recalibration"
    else:
        raise ValueError(f"declared_family must be {SUBSTANTIVE!r} or {RECALIBRATION!r}")

    return _finalise(df, design_names, candidate_features, nuisance_features, findings,
                     {"augmented_rank": aug_rank, "r2_offset_on_design": (
                         None if not np.isfinite(r2_full) else round(float(r2_full), 12)),
                      "folds": fold_records, "contrasts": contrast_records,
                      "audited_columns": aug_names},
                     declared_family, raise_on_block)


def _finalise(df, design_names, candidate_features, nuisance_features, findings, extra,
              declared_family, raise_on_block):
    blocking = [f for f in findings if f["kind"] in BLOCKING]
    out = {"schema": "offset_dependency_guard/1",
           "feature_gate_sha256": feature_gate_digest(),
           "feature_gate_sha256_expected": FEATURE_GATE_SHA256,
           "feature_gate_byte_unchanged": feature_gate_digest() == FEATURE_GATE_SHA256,
           "n_rows": int(len(df)),
           "declared_family": declared_family,
           "nuisance_features": list(nuisance_features),
           "candidate_features": list(candidate_features),
           "design_columns": list(design_names),
           "thresholds": {"NEAR_R2": NEAR_R2, "EXACT_R2": EXACT_R2,
                          "SPEARMAN": SPEARMAN_THRESHOLD,
                          "RANK_TOL": fg.RANK_TOL, "COND_MAX": fg.COND_MAX},
           "findings": findings, "blocking": blocking,
           "passed": len(blocking) == 0,
           "note": "the offset is part of the audited design; auditing X alone is not a pass"}
    if extra:
        out.update(extra)
    if blocking and raise_on_block:
        raise OffsetDependencyFailure(blocking, out)
    return out
