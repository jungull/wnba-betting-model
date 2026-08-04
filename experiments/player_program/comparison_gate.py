#!/usr/bin/env python3
"""comparison_gate.py — PERMANENT baseline-parity gate for challenger-vs-incumbent comparisons.

Born from the P1/P2 free-intercept confound: fitted challengers carried an unpenalised free
intercept that the unfitted frozen incumbent (Arm D) did not have. That flexibility ALONE was
worth about +0.0033 operational team MAE — the same magnitude as the effects being hunted. Three
independent workstreams reproduced an intercept-only, feature-free control (K0) built from the
challenger's own pipeline with zero substantive features:

    K0 operational team MAE          2.96419
    frozen Arm D operational team MAE 2.96745
    free-recalibration gain           0.00326

Every "gain" below 0.00326 that any of those challengers reported was already available to a model
with no substantive features at all.

A challenger that beats the frozen incumbent by less than a featureless control from its own
pipeline already obtains has demonstrated NOTHING about its features.

This is a property of the COMPARISON, not of the design matrix, so it deliberately does not live in
`feature_gate.py`. `feature_gate.audit` interrogates one design; this module interrogates the
relationship between two or three of them. No feature-matrix check can catch a parity defect: both
matrices can be individually impeccable while the comparison between their fits is meaningless.

The gate FAILS CLOSED. A comparison is invalid unless a manifest establishes matched treatment
across all sixteen dimensions in ``DIMENSIONS``. An omitted dimension is a hard error, never a
silent pass — an omitted dimension is exactly how the intercept confound survived four rounds of
review.

Usage::

    from comparison_gate import SideSpec, audit, audit_fold, require_matched_k0

    audit(manifest)                     # consolidated manifest, all folds
    audit_fold(challenger, incumbent, k0, metrics, fold="2022")   # one chronological fold

Both return a machine-readable audit and raise ``ComparisonGateFailure`` on a blocking condition
unless it is explicitly adjudicated WITH A STATED REASON — which is then carried in the report
forever. An adjudicated difference is allowed; a HIDDEN one is not.

Three quantities are always reported separately and are never collapsed into a headline:

    challenger_vs_incumbent   what the challenger claims
    challenger_vs_k0          what its FEATURES bought, net of pipeline freedom
    k0_vs_incumbent           the free-flexibility gain — what pipeline freedom bought alone

Pure stdlib + numpy/pandas. Python 3.13.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

import numpy as np, pandas as pd                                              # noqa: E401

# --------------------------------------------------------------------------------------------
# the sixteen dimensions of comparison parity
#
# Every one of these was, at some point in this program, silently different between a challenger
# and its baseline. `intercept_treatment` is the one that cost 0.0033 team MAE; the rest are here
# because "we only checked the one that bit us last time" is how the next one gets through.
# --------------------------------------------------------------------------------------------
DIMENSIONS: tuple[str, ...] = (
    "intercept_treatment",       # free / fixed / absent; the P2 defect
    "calibration_freedom",       # ANY post-fit rescaling, recentring, isotonic or affine fix-up
    "penalty_treatment",         # ridge/lasso/none AND whether the intercept itself is penalised
    "exposure_offset",           # log-exposure offset, its definition and its units
    "training_rows",             # the exact row set fitted on
    "evaluation_rows",           # the exact row set scored on
    "chronological_folds",       # fold boundaries and their ordering
    "clipping",                  # prediction floors/ceilings, winsorisation
    "link_function",             # identity / log / logit ...
    "preprocessing",             # standardisation, encoding, winsorising of inputs
    "missing_value_handling",    # impute / drop / mask, and with what
    "companion_components",      # minutes model, availability model, exposure bridge, priors
    "fallback_rules",            # what happens when a component declines to predict
    "candidate_universe",        # which player-games are eligible at all
    "post_processing",           # renormalisation, shrinkage, blending, rounding
    "prediction_universe",       # which rows a prediction is emitted for
)

ROLES: tuple[str, ...] = ("challenger", "k0", "incumbent")

#: finding kinds that invalidate a comparison. Adjudicable WITH A REASON, except where noted.
BLOCKING = {"dimension_unspecified", "dimension_mismatch", "unknown_dimension",
            "pipeline_id_unspecified", "side_missing", "role_mismatch", "duplicate_side_name",
            "k0_missing", "k0_has_substantive_features", "k0_not_from_challenger_pipeline",
            "challenger_has_no_substantive_features",
            "metric_missing", "metric_non_finite",
            "gain_within_free_flexibility",
            "no_per_fold_audit", "no_consolidated_audit", "fold_set_mismatch",
            "adjudication_without_reason"}

#: adjudication cannot excuse a malformed adjudication. Otherwise the escape hatch escapes itself.
NON_ADJUDICABLE = {"adjudication_without_reason"}

#: the WS2 reference case, kept in the module so the magnitude is never re-derived from memory.
REFERENCE_CASE = {
    "source": "discovery wave 1, workstream 2; reproduced independently by three workstreams",
    "metric": "operational_team_mae",
    "k0_intercept_only": 2.96419,
    "frozen_arm_d": 2.96745,
    "free_flexibility_gain": 0.00326,
    "note": "an unpenalised free intercept the unfitted incumbent did not have, worth the same "
            "as the effects being hunted",
}


class _Unspecified:
    """Sentinel. Distinct from ``None`` so that 'not applicable' can be stated explicitly."""

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

#: the value to use when a dimension genuinely does not apply. Say it out loud; never omit.
NONE = "none"


class ComparisonGateFailure(RuntimeError):
    """Raised when a comparison is not established as parity-matched."""


# --------------------------------------------------------------------------------------------
# canonicalisation helpers
# --------------------------------------------------------------------------------------------

def _scalar_repr(v: Any) -> str:
    if isinstance(v, float):
        return repr(float(v))
    return str(v)


def row_digest(keys: Any, *, sort: bool = True, label: str = "rows") -> str:
    """A stable, comparable descriptor for a ROW SET.

    Training and evaluation row sets are far too large to carry in a manifest and far too
    important to describe in prose ("the 2022 fold"). Digest them. Two sides that disagree on
    which rows they used will disagree on this string.

    Accepts a DataFrame (all columns, row-wise), Series/Index/ndarray, or any iterable of keys.
    """
    if isinstance(keys, pd.DataFrame):
        vals = ["\x1f".join(_scalar_repr(x) for x in t)
                for t in keys.itertuples(index=False, name=None)]
    elif isinstance(keys, (pd.Series, pd.Index)):
        vals = [_scalar_repr(v) for v in keys.tolist()]
    elif isinstance(keys, np.ndarray):
        vals = [_scalar_repr(v) for v in keys.tolist()]
    else:
        vals = [_scalar_repr(v) for v in list(keys)]
    if sort:
        vals = sorted(vals)
    h = hashlib.sha256("\x00".join(vals).encode("utf-8")).hexdigest()
    return f"{label}:n={len(vals)}:sha256={h[:32]}"


def _is_unspecified(v: Any) -> bool:
    if isinstance(v, _Unspecified) or v is None:
        return True
    return isinstance(v, str) and not v.strip()


def _jsonable(v: Any) -> Any:
    if isinstance(v, _Unspecified):
        return None
    if v is None or isinstance(v, (str, bool)):
        return v
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return float(v)
    if isinstance(v, (np.ndarray, pd.Series, pd.Index, pd.DataFrame)):
        return row_digest(v)
    if isinstance(v, Mapping):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (set, frozenset)):
        return sorted(repr(_jsonable(x)) for x in v)
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return repr(v)


def _canon(v: Any) -> Any:
    """A hashable, order-stable canonical form used only for equality of two dimension values."""
    if isinstance(v, _Unspecified) or v is None:
        return ("unspecified",)
    if isinstance(v, bool):
        return ("bool", v)
    if isinstance(v, (int, np.integer, float, np.floating)):
        return ("num", float(v))
    if isinstance(v, str):
        return ("str", v.strip())
    if isinstance(v, (np.ndarray, pd.Series, pd.Index, pd.DataFrame)):
        return ("str", row_digest(v))
    if isinstance(v, Mapping):
        return ("map", tuple(sorted(((str(k), _canon(x)) for k, x in v.items()),
                                    key=lambda kv: kv[0])))
    if isinstance(v, (set, frozenset)):
        return ("set", tuple(sorted(repr(_canon(x)) for x in v)))
    if isinstance(v, (list, tuple)):
        return ("seq", tuple(_canon(x) for x in v))
    return ("repr", repr(v))


def _finding(kind: str, **kw: Any) -> dict:
    return {"kind": kind, **kw}


# --------------------------------------------------------------------------------------------
# one side of a comparison
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SideSpec:
    """One side of a comparison, declared across all sixteen parity dimensions.

    Every dimension defaults to ``UNSPECIFIED`` and every unspecified dimension is a BLOCKING
    finding. There is no default that means "probably the same as the other side" — that default
    is what the free-intercept confound exploited.

    ``pipeline_id`` is a required assertion of code-path identity. It is how a K0 control claims
    to have come from the challenger's IDENTICAL pipeline; the sixteen dimensions cannot prove
    that on their own.
    """

    name: str
    role: str
    pipeline_id: str = ""
    substantive_features: tuple[str, ...] = ()

    intercept_treatment: Any = UNSPECIFIED
    calibration_freedom: Any = UNSPECIFIED
    penalty_treatment: Any = UNSPECIFIED
    exposure_offset: Any = UNSPECIFIED
    training_rows: Any = UNSPECIFIED
    evaluation_rows: Any = UNSPECIFIED
    chronological_folds: Any = UNSPECIFIED
    clipping: Any = UNSPECIFIED
    link_function: Any = UNSPECIFIED
    preprocessing: Any = UNSPECIFIED
    missing_value_handling: Any = UNSPECIFIED
    companion_components: Any = UNSPECIFIED
    fallback_rules: Any = UNSPECIFIED
    candidate_universe: Any = UNSPECIFIED
    post_processing: Any = UNSPECIFIED
    prediction_universe: Any = UNSPECIFIED

    #: keys handed to ``from_dict``/``with_overrides`` that are not dimensions. A typo'd key is
    #: indistinguishable from an omitted dimension unless it is surfaced, so it is surfaced.
    unknown_keys: tuple[str, ...] = field(default=(), compare=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "substantive_features",
                           tuple(str(f) for f in (self.substantive_features or ())))
        object.__setattr__(self, "unknown_keys", tuple(sorted(set(self.unknown_keys or ()))))

    # -- construction ------------------------------------------------------------------------
    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "SideSpec":
        allowed = set(DIMENSIONS) | {"name", "role", "pipeline_id", "substantive_features"}
        known = {k: v for k, v in d.items() if k in allowed}
        unknown = tuple(sorted(str(k) for k in d if k not in allowed))
        known.setdefault("name", "")
        known.setdefault("role", "")
        return cls(unknown_keys=unknown, **known)

    def with_overrides(self, **kw: Any) -> "SideSpec":
        """A per-fold variant. Only dimensions may be overridden; anything else is recorded."""
        unknown = tuple(k for k in kw if k not in DIMENSIONS)
        known = {k: v for k, v in kw.items() if k in DIMENSIONS}
        return replace(self, unknown_keys=tuple(sorted(set(self.unknown_keys) | set(unknown))),
                       **known)

    # -- introspection -----------------------------------------------------------------------
    @property
    def n_substantive_features(self) -> int:
        return len(self.substantive_features)

    def dimensions(self) -> dict[str, Any]:
        return {d: getattr(self, d) for d in DIMENSIONS}

    def unspecified_dimensions(self) -> tuple[str, ...]:
        return tuple(d for d in DIMENSIONS if _is_unspecified(getattr(self, d)))

    def as_dict(self) -> dict:
        return {"name": self.name, "role": self.role, "pipeline_id": self.pipeline_id,
                "n_substantive_features": self.n_substantive_features,
                "substantive_features": list(self.substantive_features),
                "dimensions": {d: _jsonable(getattr(self, d)) for d in DIMENSIONS},
                "unspecified_dimensions": list(self.unspecified_dimensions()),
                "unknown_keys": list(self.unknown_keys)}


def _coerce_side(obj: Any, slot: str) -> SideSpec | None:
    if obj is None:
        return None
    if isinstance(obj, SideSpec):
        return obj
    if isinstance(obj, Mapping):
        return SideSpec.from_dict({"role": slot, **dict(obj)})
    raise TypeError(f"{slot} must be a SideSpec, a mapping, or None; got {type(obj).__name__}")


# --------------------------------------------------------------------------------------------
# parity checks (raw findings; adjudication is applied centrally, once, later)
# --------------------------------------------------------------------------------------------

def side_findings(side: SideSpec | None, slot: str) -> list[dict]:
    """Well-formedness of one declared side."""
    if side is None:
        return [_finding("side_missing", side=slot,
                         detail=f"no {slot} was supplied; the gate cannot assume one")]
    out: list[dict] = []
    if side.role != slot:
        out.append(_finding("role_mismatch", side=slot, declared_role=side.role,
                            detail=f"a side declaring role={side.role!r} was passed as {slot!r}"))
    if not str(side.pipeline_id).strip():
        out.append(_finding("pipeline_id_unspecified", side=slot, name=side.name,
                            detail="pipeline_id is how a side asserts which code path produced "
                                   "it; K0 matching is unverifiable without it"))
    for k in side.unknown_keys:
        out.append(_finding("unknown_dimension", side=slot, key=k,
                            detail="not one of the sixteen parity dimensions; a typo'd key leaves "
                                   "the real dimension unspecified"))
    for d in side.unspecified_dimensions():
        out.append(_finding("dimension_unspecified", side=slot, name=side.name, dimension=d,
                            detail="unspecified is not 'same as the other side'; state it, or "
                                   "state comparison_gate.NONE"))
    return out


def dimension_parity(a: SideSpec, b: SideSpec, *, pair: str | None = None) -> list[dict]:
    """Raw ``dimension_mismatch`` findings between two sides.

    A dimension that is unspecified on either side is skipped here — ``side_findings`` has
    already blocked on it, and reporting it twice buries the real mismatches.
    """
    pair = pair or f"{a.role or 'a'}|{b.role or 'b'}"
    out: list[dict] = []
    for d in DIMENSIONS:
        va, vb = getattr(a, d), getattr(b, d)
        if _is_unspecified(va) or _is_unspecified(vb):
            continue
        if _canon(va) != _canon(vb):
            out.append(_finding("dimension_mismatch", pair=pair, dimension=d,
                                left=a.name, right=b.name,
                                left_value=_jsonable(va), right_value=_jsonable(vb)))
    return out


def k0_findings(challenger: SideSpec | None, k0: SideSpec | None) -> list[dict]:
    """Raw findings for the matched featureless control.

    K0 is the whole point. It is the challenger's IDENTICAL pipeline with zero substantive
    features, so the difference between K0 and the frozen incumbent is exactly the amount of
    "improvement" attributable to pipeline freedom rather than to anything the challenger learned.
    """
    out: list[dict] = []
    if k0 is None:
        out.append(_finding("k0_missing",
                            detail="every challenger must be accompanied by a matched featureless "
                                   "control built from its identical pipeline; without one the "
                                   "free-flexibility gain is unmeasured and the comparison is "
                                   "uninterpretable"))
    if challenger is None:
        return out
    if challenger.n_substantive_features == 0:
        out.append(_finding("challenger_has_no_substantive_features", side="challenger",
                            name=challenger.name,
                            detail="a challenger with zero substantive features IS a K0; there is "
                                   "no feature effect for this comparison to establish"))
    if k0 is None:
        return out
    if k0.n_substantive_features > 0:
        out.append(_finding("k0_has_substantive_features", side="k0", name=k0.name,
                            n_substantive_features=k0.n_substantive_features,
                            substantive_features=list(k0.substantive_features),
                            detail="K0 must carry ZERO substantive features"))
    cp, kp = str(challenger.pipeline_id).strip(), str(k0.pipeline_id).strip()
    if cp and kp and cp != kp:
        out.append(_finding("k0_not_from_challenger_pipeline", challenger_pipeline_id=cp,
                            k0_pipeline_id=kp,
                            detail="K0 must be produced by the challenger's identical pipeline; a "
                                   "separately written control measures a different thing"))
    if challenger.name and challenger.name == k0.name:
        out.append(_finding("duplicate_side_name", name=challenger.name,
                            detail="challenger and K0 declare the same name; one of them is "
                                   "probably the other"))
    return out


# --------------------------------------------------------------------------------------------
# the three quantities
# --------------------------------------------------------------------------------------------

def gain_report(metrics: Mapping[str, Any], *, lower_is_better: bool = True,
                metric_name: str = "metric") -> dict:
    """The three quantities, always separate, never collapsed into one headline.

    ``challenger_vs_incumbent`` is what a challenger claims. ``k0_vs_incumbent`` is what a
    featureless control from the same pipeline already obtains. Their difference is exactly
    ``challenger_vs_k0`` — what the FEATURES bought — and that identity is asserted below so that
    a report can never present the three as if they were independently sourced.
    """
    def val(role: str) -> float | None:
        v = metrics.get(role)
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if np.isfinite(f) else None

    c, k, i = val("challenger"), val("k0"), val("incumbent")
    sign = -1.0 if lower_is_better else 1.0

    def gain(better: float | None, worse: float | None) -> float | None:
        if better is None or worse is None:
            return None
        return float(sign * (better - worse))

    cvi, cvk, kvi = gain(c, i), gain(c, k), gain(k, i)
    net = None if (cvi is None or kvi is None) else float(cvi - kvi)
    identity = None
    if net is not None and cvk is not None:
        identity = bool(abs(net - cvk) <= 1e-9)
    return {
        "metric_name": metric_name,
        "lower_is_better": bool(lower_is_better),
        "metrics": {"challenger": c, "k0": k, "incumbent": i},
        "gains": {
            "challenger_vs_incumbent": cvi,
            "challenger_vs_k0": cvk,
            "k0_vs_incumbent": kvi,
        },
        "free_flexibility_gain": kvi,
        "net_of_free_flexibility": net,
        "gain_identity_holds": identity,
        "reporting_contract": ("report all three gains; there is no single headline number. "
                               "challenger_vs_incumbent minus k0_vs_incumbent IS challenger_vs_k0"),
    }


def gain_findings(rep: Mapping[str, Any], *, gain_margin: float = 0.0) -> list[dict]:
    """Raw findings about the three gains, including the one this module exists for."""
    out: list[dict] = []
    g = rep["gains"]
    cvi, cvk, kvi = g["challenger_vs_incumbent"], g["challenger_vs_k0"], g["k0_vs_incumbent"]
    net = rep["net_of_free_flexibility"]
    if cvi is None or kvi is None or net is None:
        return out
    if net <= gain_margin:
        out.append(_finding(
            "gain_within_free_flexibility",
            challenger_vs_incumbent=cvi, challenger_vs_k0=cvk, k0_vs_incumbent=kvi,
            net_of_free_flexibility=net, gain_margin=float(gain_margin),
            detail=("the apparent improvement over the frozen incumbent does not exceed what a "
                    "matched FEATURELESS control from the challenger's own pipeline already "
                    "obtains; nothing has been demonstrated about the challenger's features")))
    elif kvi > 0 and net <= kvi:
        out.append(_finding(
            "gain_marginal_over_free_flexibility",
            challenger_vs_incumbent=cvi, challenger_vs_k0=cvk, k0_vs_incumbent=kvi,
            net_of_free_flexibility=net,
            detail=("the challenger exceeds its featureless control, but pipeline freedom still "
                    "contributed at least as much as the features did")))
    if kvi < 0:
        out.append(_finding(
            "free_flexibility_gain_negative", k0_vs_incumbent=kvi,
            detail=("the featureless control is WORSE than the frozen incumbent; refitting cost "
                    "accuracy, so challenger_vs_incumbent understates rather than overstates")))
    if rep.get("gain_identity_holds") is False:                      # pragma: no cover - defensive
        out.append(_finding("gain_decomposition_inconsistent", **{k: v for k, v in g.items()},
                            detail="the three gains are not mutually consistent"))
    return out


# --------------------------------------------------------------------------------------------
# adjudication — a deliberate difference may be allowed; a hidden one may not
# --------------------------------------------------------------------------------------------

def _normalise_adjudications(adj: Mapping[str, Any] | None) -> tuple[dict[str, dict], list[dict]]:
    """Split declared adjudications into usable ones and ``adjudication_without_reason``.

    A bare ``True`` is not an adjudication. Neither is an empty string. The reason is the entire
    point: it is what survives into every future report of this comparison.
    """
    out: dict[str, dict] = {}
    bad: list[dict] = []
    for key, val in dict(adj or {}).items():
        k = str(key)
        if val is False or val is None:
            continue
        reason, meta = None, {}
        if isinstance(val, str):
            reason = val.strip() or None
        elif isinstance(val, Mapping):
            meta = {str(a): _jsonable(b) for a, b in val.items() if a != "reason"}
            r = val.get("reason")
            reason = r.strip() if isinstance(r, str) and r.strip() else None
        if not reason:
            bad.append(_finding("adjudication_without_reason", adjudication_key=k,
                                supplied=_jsonable(val),
                                detail="an adjudication must carry a stated reason; a bare True, "
                                       "an empty string or a reasonless mapping is not one"))
            continue
        out[k] = {"key": k, "reason": reason, **meta}
    return out, bad


def _adjudication_candidates(f: Mapping[str, Any]) -> list[str]:
    kind, dim, pair = f["kind"], f.get("dimension"), f.get("pair")
    side = f.get("side")
    keys: list[str] = []
    if dim and pair:
        keys.append(f"{pair}:{dim}")
    if dim and side:
        keys.append(f"{side}:{dim}")
    if dim:
        keys.append(str(dim))
    if pair:
        keys.append(f"{pair}:{kind}")
    if side:
        keys.append(f"{side}:{kind}")
    keys.append(str(kind))
    return keys


def _resolve(findings: list[dict], norm: Mapping[str, dict]) -> tuple[list[dict], list[str]]:
    used: set[str] = set()
    resolved: list[dict] = []
    for raw in findings:
        f = dict(raw)
        f["adjudicated"] = False
        if f["kind"] in BLOCKING and f["kind"] not in NON_ADJUDICABLE:
            for cand in _adjudication_candidates(f):
                hit = norm.get(cand)
                if hit:
                    f["adjudicated"] = True
                    f["adjudication_key"] = hit["key"]
                    f["adjudication_reason"] = hit["reason"]
                    for a, b in hit.items():
                        if a not in ("key", "reason"):
                            f[f"adjudication_{a}"] = b
                    used.add(hit["key"])
                    break
        resolved.append(f)
    return resolved, [k for k in norm if k not in used]


def _finalise(core: dict, raw: list[dict], norm: Mapping[str, dict],
              extra: list[dict], *, report_unused: bool) -> dict:
    resolved, unused = _resolve(list(extra) + list(raw), norm)
    if report_unused:
        resolved += [_finding("adjudication_unused", adjudication_key=k,
                              adjudication_reason=norm[k]["reason"],
                              detail="declared but matched no finding; it may be stale")
                     for k in unused]
    blocking = [f for f in resolved if f["kind"] in BLOCKING and not f.get("adjudicated")]
    applied = [{"kind": f["kind"], "dimension": f.get("dimension"), "pair": f.get("pair"),
                "side": f.get("side"), "adjudication_key": f["adjudication_key"],
                "adjudication_reason": f["adjudication_reason"]}
               for f in resolved if f.get("adjudicated")]
    out = dict(core)
    out.update({"findings": resolved, "blocking": blocking, "adjudications_applied": applied,
                "n_adjudicated": len(applied), "passed": len(blocking) == 0})
    return out


# --------------------------------------------------------------------------------------------
# public entry points
# --------------------------------------------------------------------------------------------

def require_matched_k0(challenger: SideSpec | Mapping[str, Any] | None,
                       k0: SideSpec | Mapping[str, Any] | None, *,
                       adjudications: Mapping[str, Any] | None = None) -> dict:
    """Assert that a matched featureless control accompanies this challenger.

    Checks that K0 exists, carries zero substantive features, comes from the challenger's declared
    pipeline, and matches it on all sixteen dimensions. Raises ``ComparisonGateFailure`` otherwise.

    This is the load-bearing requirement of the module. A comparison without K0 is blocked: the
    free-flexibility gain is then unmeasured, and an unmeasured confound of the size of the effect
    is indistinguishable from the effect.
    """
    c = _coerce_side(challenger, "challenger")
    k = _coerce_side(k0, "k0")
    raw: list[dict] = []
    raw += side_findings(c, "challenger")
    if k is not None:
        raw += side_findings(k, "k0")
    raw += k0_findings(c, k)
    if c is not None and k is not None:
        raw += dimension_parity(c, k, pair="challenger|k0")
    norm, bad = _normalise_adjudications(adjudications)
    core = {"schema": "comparison_gate.k0/1",
            "challenger": c.as_dict() if c else None,
            "k0": k.as_dict() if k else None,
            "dimensions_checked": list(DIMENSIONS), "n_dimensions": len(DIMENSIONS)}
    rep = _finalise(core, raw, norm, bad, report_unused=True)
    rep["matched"] = rep["passed"]
    if rep["blocking"]:
        raise ComparisonGateFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


def _fold_core_and_findings(challenger: SideSpec | None, incumbent: SideSpec | None,
                            k0: SideSpec | None, metrics: Mapping[str, Any], *,
                            fold: str, metric_name: str, lower_is_better: bool,
                            gain_margin: float) -> tuple[dict, list[dict]]:
    raw: list[dict] = []
    raw += side_findings(challenger, "challenger")
    raw += side_findings(incumbent, "incumbent")
    if k0 is not None:
        raw += side_findings(k0, "k0")
    raw += k0_findings(challenger, k0)

    if challenger is not None and k0 is not None:
        raw += dimension_parity(challenger, k0, pair="challenger|k0")
    if challenger is not None and incumbent is not None:
        raw += dimension_parity(challenger, incumbent, pair="challenger|incumbent")

    for role in ROLES:
        v = metrics.get(role)
        if v is None:
            if role == "k0" and k0 is None:
                continue                       # already blocked by k0_missing; do not double-count
            raw.append(_finding("metric_missing", side=role, fold=fold, metric=metric_name))
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            raw.append(_finding("metric_non_finite", side=role, fold=fold, metric=metric_name,
                                value=repr(v)))
            continue
        if not np.isfinite(f):
            raw.append(_finding("metric_non_finite", side=role, fold=fold, metric=metric_name,
                                value=f))

    rep = gain_report(metrics, lower_is_better=lower_is_better, metric_name=metric_name)
    raw += gain_findings(rep, gain_margin=gain_margin)

    core = {
        "schema": "comparison_gate/1",
        "fold": fold,
        "sides": {"challenger": challenger.as_dict() if challenger else None,
                  "k0": k0.as_dict() if k0 else None,
                  "incumbent": incumbent.as_dict() if incumbent else None},
        "dimensions_checked": list(DIMENSIONS),
        "n_dimensions": len(DIMENSIONS),
        "pairs_checked": ["challenger|k0", "challenger|incumbent"],
        **rep,
        "note": ("a challenger that beats the frozen incumbent by less than a featureless control "
                 "from its own pipeline has demonstrated nothing about its features"),
    }
    return core, raw


def audit_fold(challenger: SideSpec | Mapping[str, Any] | None,
               incumbent: SideSpec | Mapping[str, Any] | None,
               k0: SideSpec | Mapping[str, Any] | None,
               metrics: Mapping[str, Any], *,
               fold: str = "consolidated",
               metric_name: str = "operational_team_mae",
               lower_is_better: bool = True,
               adjudications: Mapping[str, Any] | None = None,
               gain_margin: float = 0.0,
               raise_on_block: bool = True) -> dict:
    """Audit ONE chronological fold (or a standalone consolidated comparison).

    ``metrics`` maps ``challenger`` / ``k0`` / ``incumbent`` to that side's value of
    ``metric_name`` on this fold. ``k0`` is positional and required: passing ``None`` is a
    deliberate, recorded refusal, not an omission.

    Per-fold invocation is not optional in this program. WS3 found a 2022 stage-2 fold with
    std 7.8e-9 while pooled variance looked healthy; a consolidated comparison can average away a
    fold in which the challenger's advantage was entirely free flexibility.
    """
    c = _coerce_side(challenger, "challenger")
    i = _coerce_side(incumbent, "incumbent")
    k = _coerce_side(k0, "k0")
    core, raw = _fold_core_and_findings(c, i, k, metrics, fold=fold, metric_name=metric_name,
                                        lower_is_better=lower_is_better, gain_margin=gain_margin)
    norm, bad = _normalise_adjudications(adjudications)
    rep = _finalise(core, raw, norm, bad, report_unused=True)
    if rep["blocking"] and raise_on_block:
        raise ComparisonGateFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


def audit(manifest: Mapping[str, Any], *, raise_on_block: bool = True) -> dict:
    """Audit a CONSOLIDATED comparison manifest: every chronological fold, then the consolidation.

    Manifest shape::

        {
          "comparison_id": "turnover_p2_arm_h_vs_D",
          "metric_name": "operational_team_mae",
          "lower_is_better": true,
          "challenger": SideSpec | {...},
          "k0":         SideSpec | {...},      # required; None is blocked, not defaulted
          "incumbent":  SideSpec | {...},
          "folds": {
             "2022": {"challenger": 2.97, "k0": 2.98, "incumbent": 2.99,
                      "overrides": {"challenger": {"training_rows": "..."}, ...}},
             ...
          },
          "consolidated": {"challenger": ..., "k0": ..., "incumbent": ...},
          "adjudications": {"challenger|incumbent:intercept_treatment": "reason ..."}
        }

    Per-fold ``overrides`` exist because ``training_rows`` and ``evaluation_rows`` legitimately
    differ between folds; everything else should not.
    """
    metric_name = str(manifest.get("metric_name", "operational_team_mae"))
    lower = bool(manifest.get("lower_is_better", True))
    gain_margin = float(manifest.get("gain_margin", 0.0))
    challenger = _coerce_side(manifest.get("challenger"), "challenger")
    incumbent = _coerce_side(manifest.get("incumbent"), "incumbent")
    k0 = _coerce_side(manifest.get("k0"), "k0")
    folds = dict(manifest.get("folds") or {})
    consolidated = manifest.get("consolidated")

    norm, bad = _normalise_adjudications(manifest.get("adjudications"))

    raw: list[dict] = []
    fold_reports: dict[str, dict] = {}

    def sides_for(entry: Mapping[str, Any]) -> tuple[SideSpec | None, ...]:
        ov = dict(entry.get("overrides") or {})
        out = []
        for side, slot in ((challenger, "challenger"), (incumbent, "incumbent"), (k0, "k0")):
            o = ov.get(slot) or {}
            out.append(side.with_overrides(**dict(o)) if (side is not None and o) else side)
        return tuple(out)

    for fid in sorted(folds, key=str):
        entry = folds[fid] if isinstance(folds[fid], Mapping) else {}
        m = entry.get("metrics") if isinstance(entry.get("metrics"), Mapping) else \
            {r: entry.get(r) for r in ROLES}
        c, i, k = sides_for(entry)
        core, fraw = _fold_core_and_findings(c, i, k, m, fold=str(fid), metric_name=metric_name,
                                             lower_is_better=lower, gain_margin=gain_margin)
        fold_reports[str(fid)] = _finalise(core, fraw, norm, [], report_unused=False)
        raw += [{**f, "fold": str(fid)} for f in fraw]

    cons_report = None
    if isinstance(consolidated, Mapping):
        m = consolidated.get("metrics") if isinstance(consolidated.get("metrics"), Mapping) else \
            {r: consolidated.get(r) for r in ROLES}
        c, i, k = sides_for(consolidated)
        core, craw = _fold_core_and_findings(c, i, k, m, fold="consolidated",
                                             metric_name=metric_name, lower_is_better=lower,
                                             gain_margin=gain_margin)
        cons_report = _finalise(core, craw, norm, [], report_unused=False)
        raw += [{**f, "fold": "consolidated"} for f in craw]
    else:
        raw.append(_finding("no_consolidated_audit",
                            detail="the manifest declares no consolidated comparison; the number "
                                   "that will be quoted must itself be audited"))

    if not folds:
        raw.append(_finding("no_per_fold_audit",
                            detail="a consolidated comparison cannot establish fold-level parity; "
                                   "a fold in which the whole advantage was free flexibility "
                                   "averages away"))
    elif challenger is not None:
        declared = challenger.chronological_folds
        if isinstance(declared, (list, tuple, set, frozenset)) and declared:
            want = {str(x) for x in declared}
            have = {str(x) for x in folds}
            if want != have:
                raw.append(_finding("fold_set_mismatch",
                                    declared_folds=sorted(want), audited_folds=sorted(have),
                                    missing=sorted(want - have), unexpected=sorted(have - want),
                                    detail="the folds audited are not the folds declared"))

    core = {
        "schema": "comparison_gate.manifest/1",
        "scope": "manifest",
        "comparison_id": manifest.get("comparison_id"),
        "metric_name": metric_name,
        "lower_is_better": lower,
        "dimensions_checked": list(DIMENSIONS),
        "n_dimensions": len(DIMENSIONS),
        "sides": {"challenger": challenger.as_dict() if challenger else None,
                  "k0": k0.as_dict() if k0 else None,
                  "incumbent": incumbent.as_dict() if incumbent else None},
        "folds": fold_reports,
        "n_folds": len(fold_reports),
        "consolidated": cons_report,
        "reference_case": dict(REFERENCE_CASE),
        "note": ("parity is a property of the comparison, not of the design matrix; feature_gate "
                 "cannot see any of this"),
    }
    rep = _finalise(core, raw, norm, bad, report_unused=True)
    if rep["blocking"] and raise_on_block:
        raise ComparisonGateFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep
