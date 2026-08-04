#!/usr/bin/env python3
"""feature_gate.py — PERMANENT prefit feature-matrix gate.

Born from the P2 defect: proj_minutes_share and proj_off_poss_share were registered as two
features but are algebraically ONE column under the v1 minutes-to-possession mapping. The Poisson
IRLS converged anyway and produced predictions ~4.8e8 per row.

A model optimiser converging does NOT validate an unidentified design.

Call `audit(X, names, offset=..., target=...)` before ANY fit. It returns a machine-readable audit
and raises FeatureGateFailure on a blocking condition unless it is explicitly adjudicated.
"""
from __future__ import annotations
import json

import numpy as np, pandas as pd                                               # noqa: E401

BLOCKING = {"exact_duplicate", "near_collinear", "deterministic_transform_of_offset",
            "zero_variance", "non_finite", "impossible_scaling", "schema_mismatch",
            "target_derived", "rank_deficient", "ill_conditioned"}

#: multivariate identifiability thresholds
RANK_TOL = 1e-8      # relative singular-value tolerance
COND_MAX = 1e6       # condition-number ceiling


def design_rank_report(df: pd.DataFrame, names: list[str]) -> dict:
    """Multivariate identifiability of the standardised complete-case design.

    The pairwise checks below cannot see a three-term dependency such as ``c = a - b``. That is
    not hypothetical: a five-feature design containing proj_minutes_share, trailing_minutes_share
    and role_change (== proj - trailing) has numerical rank 4 of 5, smallest singular value 0.0
    and condition 3.7e15, yet its largest pairwise correlation is only 0.659. The pairwise gate
    passed it and Poisson ridge returned a plausible finite fit whose coefficients are a property
    of the penalty rather than of the data.

    Reference implementation: discovery_wave_1/ws1/run_ws1.py::design_rank_report.
    """
    if len(names) == 0:                      # intercept-only control
        return {"checked": True, "n_complete_rows": int(len(df)), "n_features": 0,
                "singular_values": [], "numerical_rank": 0, "full_rank": True,
                "condition_number": 1.0, "condition_ok": True,
                "note": "zero-feature design is trivially identified"}
    X = df[names].to_numpy(float)
    m = np.all(np.isfinite(X), axis=1)
    Xc = X[m]
    if len(Xc) < 10:
        return {"checked": False, "n_complete_rows": int(m.sum()), "n_features": len(names),
                "singular_values": [], "numerical_rank": 0, "full_rank": False,
                "condition_number": float("inf"), "condition_ok": False,
                "note": "insufficient complete rows to assess rank"}
    sd = Xc.std(0)
    sd = np.where(sd == 0, 1.0, sd)
    Z = (Xc - Xc.mean(0)) / sd
    sv = np.linalg.svd(Z, compute_uv=False)
    rank = int((sv > RANK_TOL * sv.max()).sum())
    cond = float(sv.max() / sv.min()) if sv.min() > 0 else float("inf")
    return {"checked": True, "n_complete_rows": int(m.sum()), "n_features": len(names),
            "singular_values": [float(x) for x in np.round(sv, 8)],
            "numerical_rank": rank, "full_rank": bool(rank == len(names)),
            "condition_number": cond, "condition_ok": bool(cond <= COND_MAX),
            "note": "exact rank deficiency means ridge chooses a point in a flat direction; the "
                    "coefficients are then a property of the penalty, not of the data"}


class FeatureGateFailure(RuntimeError):
    pass


def audit(df: pd.DataFrame, names: list[str], offset: np.ndarray | None = None,
          target: np.ndarray | None = None, test_df: pd.DataFrame | None = None,
          adjudicated: dict | None = None, corr_threshold: float = 0.999,
          target_corr_threshold: float = 0.98) -> dict:
    adjudicated = adjudicated or {}
    X = df[names]
    findings: list[dict] = []

    for c in names:
        v = X[c].to_numpy(float)
        if not np.all(np.isfinite(v[~np.isnan(v)])):
            findings.append({"kind": "non_finite", "feature": c})
        sd = float(np.nanstd(v))
        if sd == 0.0:
            findings.append({"kind": "zero_variance", "feature": c})
        elif sd < 1e-8:
            findings.append({"kind": "impossible_scaling", "feature": c, "std": sd})
        if np.nanmax(np.abs(v)) > 1e12:
            findings.append({"kind": "impossible_scaling", "feature": c,
                             "max_abs": float(np.nanmax(np.abs(v)))})

    # exact duplicates and near-collinearity
    for i, a in enumerate(names):
        va = X[a].to_numpy(float)
        for b in names[i + 1:]:
            vb = X[b].to_numpy(float)
            m = np.isfinite(va) & np.isfinite(vb)
            if m.sum() < 10:
                continue
            if np.array_equal(va[m], vb[m]):
                findings.append({"kind": "exact_duplicate", "feature": a, "other": b})
                continue
            sa, sb = np.std(va[m]), np.std(vb[m])
            if sa > 0 and sb > 0:
                r = float(np.corrcoef(va[m], vb[m])[0, 1])
                if abs(r) >= corr_threshold:
                    findings.append({"kind": "near_collinear", "feature": a, "other": b,
                                     "corr": round(r, 6)})

    # deterministic transform of the offset / exposure
    if offset is not None:
        o = np.asarray(offset, float)
        for c in names:
            v = X[c].to_numpy(float)
            m = np.isfinite(v) & np.isfinite(o)
            if m.sum() < 10 or np.std(v[m]) == 0 or np.std(o[m]) == 0:
                continue
            r = float(np.corrcoef(v[m], o[m])[0, 1])
            if abs(r) >= corr_threshold:
                findings.append({"kind": "deterministic_transform_of_offset", "feature": c,
                                 "corr_with_offset": round(r, 6)})

    # leakage from target-derived fields
    if target is not None:
        y = np.asarray(target, float)
        for c in names:
            v = X[c].to_numpy(float)
            m = np.isfinite(v) & np.isfinite(y)
            if m.sum() < 10 or np.std(v[m]) == 0 or np.std(y[m]) == 0:
                continue
            r = float(np.corrcoef(v[m], y[m])[0, 1])
            if abs(r) >= target_corr_threshold:
                findings.append({"kind": "target_derived", "feature": c,
                                 "corr_with_target": round(r, 6)})

    # train/test schema differences
    if test_df is not None:
        miss = [c for c in names if c not in test_df.columns]
        if miss:
            findings.append({"kind": "schema_mismatch", "missing_in_test": miss})

    # multivariate identifiability -- the pairwise checks above cannot see c = a - b
    rank = design_rank_report(df, names)
    if rank["checked"]:
        if not rank["full_rank"]:
            findings.append({"kind": "rank_deficient", "feature": "__design__",
                             "numerical_rank": rank["numerical_rank"],
                             "n_features": rank["n_features"],
                             "smallest_singular_value": (rank["singular_values"][-1]
                                                         if rank["singular_values"] else None),
                             "condition_number": rank["condition_number"]})
        elif not rank["condition_ok"]:
            findings.append({"kind": "ill_conditioned", "feature": "__design__",
                             "condition_number": rank["condition_number"],
                             "ceiling": COND_MAX})

    blocking = [f for f in findings
                if f["kind"] in BLOCKING and not adjudicated.get(f.get("feature", ""), False)]
    out = {"n_features": len(names), "n_rows": int(len(df)), "features": names,
           "findings": findings, "blocking": blocking,
           "design_rank": rank,
           "passed": len(blocking) == 0,
           "note": "a converging optimiser does not validate an unidentified design"}
    if blocking:
        raise FeatureGateFailure(json.dumps(blocking[:6], default=str))
    return out
