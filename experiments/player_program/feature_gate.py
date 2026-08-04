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
import numpy as np, pandas as pd                                               # noqa: E401

BLOCKING = {"exact_duplicate", "near_collinear", "deterministic_transform_of_offset",
            "zero_variance", "non_finite", "impossible_scaling", "schema_mismatch",
            "target_derived"}


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

    blocking = [f for f in findings
                if f["kind"] in BLOCKING and not adjudicated.get(f.get("feature", ""), False)]
    out = {"n_features": len(names), "n_rows": int(len(df)), "features": names,
           "findings": findings, "blocking": blocking,
           "passed": len(blocking) == 0,
           "note": "a converging optimiser does not validate an unidentified design"}
    if blocking:
        raise FeatureGateFailure(json.dumps(blocking[:6]) if (json := __import__("json")) else str(blocking[:6]))
    return out
