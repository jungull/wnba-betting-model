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

TWO LAYERS, NOT ONE
===================

The first version of this gate enforced identical parity against BOTH the matched K0 control and
the frozen incumbent, all dimensions blocking. Against an unfitted frozen incumbent,
``intercept_treatment``, ``penalty_treatment`` and ``training_rows`` mismatch BY CONSTRUCTION — a
frozen formula has no fitted intercept, no penalty and no training rows. So every real comparison
opened with three mandatory adjudications that were always granted. That is how adjudication decays
into boilerplate, and boilerplate is exactly the failure mode this module exists to prevent.

So the gate now enforces two DIFFERENT contracts:

**Layer A — challenger versus matched K0. STRICT PIPELINE PARITY, and THE PRIMARY TEST OF WHETHER
THE SUBSTANTIVE FEATURES ADD VALUE.** K0 is the challenger's own pipeline with zero substantive
features. There is no legitimate reason for any dimension to differ, so ``challenger_vs_k0`` is
the only contrast in which a difference is attributable to the features and nothing else. A Layer
A mismatch is BLOCKING and is NOT adjudicable by an ordinary reason. (A deliberately high-friction
extraordinary override exists — see LAYER_A_OVERRIDE_CODE — and it is loud, permanent and
impossible to grant quietly.)

**Layer B — challenger versus the frozen substantive incumbent. OPERATIONAL RELEVANCE ONLY.**
Layer B establishes whether the challenger would improve the thing currently in production. It
CANNOT, by itself, attribute any part of that improvement to the features: the incumbent differs
from the challenger in fitting architecture as well as in features, so ``challenger_vs_incumbent``
confounds the two. A frozen formula legitimately has no training rows and no fitted intercept, so
structural differences here MAY be adjudicated — but only with BOTH a stated reason AND a named
reason code from the closed ``LAYER_B_REASON_CODES`` enum, and only when K0 is available to
quantify what the difference is worth. The challenger is explicitly DENIED credit for the
``k0_vs_incumbent`` flexibility that its own featureless control already captured.

**THE HARD RULE.** A challenger that beats the frozen incumbent but does not beat its own K0 has
NOT demonstrated feature value, and this gate will never describe it as beneficial. That state
(``challenger_vs_incumbent > 0`` with ``challenger_vs_k0 <= 0``) gets its own verdict,
``beats_incumbent_but_fails_k0``, a spelled-out NOT BENEFICIAL label, and
``feature_value_demonstrated = False`` — in words, in the decision table itself.

A third bucket, ``evidence``, holds everything that is neither pairwise contract: declaration
well-formedness, missing metrics, the three gains, fold coverage, adjudication hygiene.

THE LAYER A NAME MAPPING
========================
The Layer A strict list is stated in prose in the program's contract as: rows and universe; folds;
offset; intercept; penalty treatment; clipping; link; preprocessing; missingness; companion
components; fallback; aggregation; post-processing. Those prose names map onto the seventeen
machine dimension names in ``LAYER_A_STRICT`` — no dimension is duplicated, and an import-time
assertion proves the mapping covers every dimension exactly once. ``aggregation`` (how player-level
predictions aggregate to a team total) is genuinely new; the rest already existed under machine
names. ``calibration_freedom`` sits under the prose name "post-processing" because a post-fit
rescaling IS a post-processing step; it is separate in the machine list because it is the one that
must never be inferred from silence.

Usage::

    from comparison_gate import SideSpec, audit, audit_fold, require_matched_k0

    audit(manifest)                     # consolidated manifest, all folds
    audit_fold(challenger, incumbent, k0, metrics, fold="2022")   # one chronological fold

Both return a machine-readable audit and raise ``ComparisonGateFailure`` on a blocking condition.
Every report carries a ``decision_table`` (and a rendered ``decision_table_text``) that makes
unmatched flexibility impossible to miss.

Three quantities are always reported separately and are never collapsed into a headline:

    challenger_vs_incumbent   OPERATIONAL RELEVANCE — what the challenger claims over production
    challenger_vs_k0          FEATURE VALUE — what its features bought — THE PRIMARY TEST
    k0_vs_incumbent           FREE FLEXIBILITY — what pipeline freedom bought with no features

Each of the three carries an uncertainty slot. Standard errors and confidence intervals may be
supplied per contrast (``uncertainty={"challenger_vs_k0": {"se": ..., "ci": [lo, hi]}, ...}``);
where none is supplied the report SAYS SO for that contrast rather than dropping the field,
because a missing interval reads as a zero one.

REMAINING GAP — pipeline_id is ASSERTED, NOT DEMONSTRATED
========================================================
``SideSpec.pipeline_id`` is a string the author writes down. The gate compares K0's ``pipeline_id``
to the challenger's and blocks when they differ, but it CANNOT prove that the K0 artefact was in
fact produced by the challenger's code path. An author who mislabels a separately written control
defeats the load-bearing requirement of this module, and nothing here will notice.

The fix is PRODUCER-SOURCE DIGEST BINDING: the producing pipeline emits, alongside every artefact,
a digest over the exact source that produced it (module file contents + resolved config + library
versions), signed into the artefact itself; ``pipeline_id`` then becomes that digest, and matching
K0 to challenger becomes a cryptographic comparison rather than a declaration.

That is NOT implemented here and is NOT trivial: it requires the producers (turnover_p2_v1,
discovery_wave_1 and the fit harness) to emit digests at write time, a canonical source-set
definition, and a stable serialisation of resolved config. None of that can be tested from inside
this module against real artefacts. It is deliberately left as a documented gap rather than
half-built; see ``REMAINING_GAPS``, which is surfaced in every report.

Pure stdlib + numpy/pandas. Python 3.13.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any, Mapping

import numpy as np, pandas as pd                                              # noqa: E401

# --------------------------------------------------------------------------------------------
# the seventeen dimensions of comparison parity
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
    "aggregation",               # how player-level predictions roll up to the team total: over
                                 # which universe, with what treatment of non-appearers, and at
                                 # what point relative to clipping and post-processing
    "candidate_universe",        # which player-games are eligible at all
    "post_processing",           # renormalisation, shrinkage, blending, rounding
    "prediction_universe",       # which rows a prediction is emitted for
)

ROLES: tuple[str, ...] = ("challenger", "k0", "incumbent")

# --------------------------------------------------------------------------------------------
# the two layers
# --------------------------------------------------------------------------------------------
LAYER_A = "A"                #: challenger vs matched K0 — strict pipeline parity
LAYER_B = "B"                #: challenger vs frozen incumbent — comparability
LAYER_EVIDENCE = "evidence"  #: declaration well-formedness, metrics, gains, coverage, hygiene

PAIR_LAYER: dict[str, str] = {"challenger|k0": LAYER_A, "challenger|incumbent": LAYER_B}

LAYER_NAMES: dict[str, str] = {
    LAYER_A: ("strict pipeline parity (challenger vs matched featureless control) — THE PRIMARY "
              "TEST OF WHETHER THE SUBSTANTIVE FEATURES ADD VALUE"),
    LAYER_B: ("comparability (challenger vs frozen substantive incumbent) — OPERATIONAL RELEVANCE "
              "ONLY; cannot by itself attribute any gain to the features"),
    LAYER_EVIDENCE: "declaration, metrics and evidence",
}

LAYER_ROLES: dict[str, str] = {
    LAYER_A: "primary_test_of_feature_value",
    LAYER_B: "operational_relevance_only",
    LAYER_EVIDENCE: "well_formedness",
}

LAYER_POLICY: dict[str, str] = {
    LAYER_A: ("K0 is the challenger's OWN pipeline with zero substantive features; no dimension "
              "has a legitimate reason to differ. A mismatch is BLOCKING and is NOT adjudicable "
              "by an ordinary reason. challenger_vs_k0 is the PRIMARY test of feature value "
              "because it is the only contrast in which the features are the sole difference."),
    LAYER_B: ("a frozen formula legitimately has no training rows and no fitted intercept. A "
              "structural difference MAY be adjudicated, but only with a stated reason AND a "
              "named code from LAYER_B_REASON_CODES, and only when K0 quantifies its size. This "
              "layer establishes OPERATIONAL RELEVANCE only: challenger_vs_incumbent confounds "
              "features with fitting architecture and can never attribute a gain to features."),
    LAYER_EVIDENCE: ("well-formedness and arithmetic; adjudicable with a stated reason where the "
                     "kind permits it at all."),
}

#: the three paired contrasts. Every report states all three, and an uncertainty slot for each.
CONTRASTS: tuple[str, ...] = ("challenger_vs_incumbent", "k0_vs_incumbent", "challenger_vs_k0")

#: the prose Layer A strict list, mapped onto the machine dimension names. Documented, not
#: duplicated: every prose name resolves to existing dimensions, and the union is exactly
#: ``DIMENSIONS`` (asserted at import).
LAYER_A_STRICT: dict[str, tuple[str, ...]] = {
    "rows and universe": ("training_rows", "evaluation_rows",
                          "candidate_universe", "prediction_universe"),
    "folds": ("chronological_folds",),
    "offset": ("exposure_offset",),
    "intercept": ("intercept_treatment",),
    "penalty treatment": ("penalty_treatment",),
    "clipping": ("clipping",),
    "link": ("link_function",),
    "preprocessing": ("preprocessing",),
    "missingness": ("missing_value_handling",),
    "companion components": ("companion_components",),
    "fallback": ("fallback_rules",),
    "aggregation": ("aggregation",),
    # a post-fit rescaling IS a post-processing step; calibration_freedom stays a separate machine
    # dimension because it is the one that must never be inferred from silence.
    "post-processing": ("post_processing", "calibration_freedom"),
}

#: reverse map: machine dimension -> the prose Layer A name it belongs to.
DIMENSION_TO_LAYER_A_NAME: dict[str, str] = {
    d: prose for prose, dims in LAYER_A_STRICT.items() for d in dims}

_covered = [d for dims in LAYER_A_STRICT.values() for d in dims]
assert sorted(_covered) == sorted(DIMENSIONS), "LAYER_A_STRICT must cover every dimension once"
assert len(_covered) == len(set(_covered)), "LAYER_A_STRICT must not duplicate a dimension"
del _covered

# --------------------------------------------------------------------------------------------
# named reason codes — a closed enum. Free text alone is not an adjudication any more.
#
# The point is that a reader can see AT A GLANCE which structural allowance was invoked and how
# often. A reason is prose and cannot be counted; a code can.
# --------------------------------------------------------------------------------------------
LAYER_B_REASON_CODES: dict[str, str] = {
    "incumbent_is_frozen_formula":
        "the incumbent is a registered, frozen formula. It is not fitted at all, so fitting-"
        "architecture dimensions cannot match by construction.",
    "incumbent_has_no_training_rows":
        "the incumbent was never fitted, so there is no training row set for it to match. Note "
        "this NEVER excuses evaluation_rows, which must be identical.",
    "incumbent_has_no_fitted_intercept":
        "the incumbent's intercept is frozen at registration; it structurally cannot carry a "
        "fitted one. This is the P2 confound; K0 measures exactly what it is worth.",
    "incumbent_is_unpenalised_by_construction":
        "penalty treatment is undefined for an unfitted formula; there are no coefficients being "
        "estimated to penalise.",
    "calibration_difference_quantified_by_k0":
        "the incumbent's calibration freedom differs from the challenger's, and the size of that "
        "difference is measured by k0_vs_incumbent, which challenger_vs_k0 must exceed.",
    "incumbent_predates_this_rule":
        "the dimension postdates the incumbent's registration; a frozen arm cannot be retrofitted "
        "with a rule that did not exist when it was frozen.",
    "incumbent_registered_with_narrower_scope":
        "the incumbent's registration fixes a companion-component, fallback or aggregation choice "
        "that the challenger's pipeline supersedes.",
}

#: the extraordinary Layer A escape. Deliberately NOT in LAYER_B_REASON_CODES: it cannot be used
#: to excuse an incumbent difference, and it additionally requires ``layer_a_override: True``.
#: Using it emits a permanent, non-suppressible ``layer_a_parity_overridden`` notice which is
#: surfaced in the decision table's waved-through list.
LAYER_A_OVERRIDE_CODE = "layer_a_pipeline_difference_accepted_by_author"

REASON_CODES: dict[str, str] = {
    **LAYER_B_REASON_CODES,
    LAYER_A_OVERRIDE_CODE:
        "EXTRAORDINARY: the author accepts a difference between the challenger and its own K0 "
        "control. This means K0 is not in fact the challenger's pipeline with the features "
        "removed, and the free-flexibility measurement is to that extent unsound.",
}

#: Layer B dimensions that are NEVER adjudicable however good the reason. If the two sides are
#: scored on different rows or different folds, the metric comparison is not a comparison at all;
#: that is not a structural difference, it is an invalid experiment.
LAYER_B_NON_ADJUDICABLE_DIMENSIONS: frozenset[str] = frozenset(
    {"evaluation_rows", "chronological_folds"})

#: finding kinds that invalidate a comparison. Adjudicable WITH A REASON, except where noted.
BLOCKING = {"dimension_unspecified", "dimension_mismatch", "unknown_dimension",
            "pipeline_id_unspecified", "side_missing", "role_mismatch", "duplicate_side_name",
            "k0_missing", "k0_has_substantive_features", "k0_not_from_challenger_pipeline",
            "challenger_has_no_substantive_features",
            "metric_missing", "metric_non_finite",
            "gain_within_free_flexibility",
            "no_per_fold_audit", "no_consolidated_audit", "fold_set_mismatch",
            "adjudication_without_reason",
            "adjudication_code_missing", "adjudication_code_unrecognised",
            "layer_a_not_adjudicable", "layer_b_dimension_not_adjudicable",
            "layer_b_adjudication_unquantified"}

#: adjudication cannot excuse a malformed adjudication. Otherwise the escape hatch escapes itself.
NON_ADJUDICABLE = {"adjudication_without_reason",
                   "adjudication_code_missing", "adjudication_code_unrecognised",
                   "layer_a_not_adjudicable", "layer_b_dimension_not_adjudicable",
                   "layer_b_adjudication_unquantified"}

#: kinds that are always Layer A regardless of pair, because they are about the constitution of
#: the matched control itself.
_LAYER_A_KINDS = frozenset({"k0_missing", "k0_has_substantive_features",
                            "k0_not_from_challenger_pipeline", "duplicate_side_name"})

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

#: what this gate still cannot do. Surfaced in every report so it cannot be forgotten.
REMAINING_GAPS: tuple[dict, ...] = (
    {
        "gap": "pipeline_id_is_asserted_not_demonstrated",
        "detail": ("pipeline_id is a string the author writes down. The gate compares K0's "
                   "pipeline_id to the challenger's and blocks when they differ, but it cannot "
                   "prove the K0 artefact came from the challenger's code path. A mislabelled "
                   "control defeats the load-bearing requirement of this module."),
        "fix": ("producer-source digest binding: the producing pipeline emits a digest over the "
                "exact source that produced each artefact (module contents + resolved config + "
                "library versions) into the artefact itself, and pipeline_id becomes that digest"),
        "status": "NOT IMPLEMENTED — deliberately left open rather than half-built",
        "why_not": ("it requires changes in the producers (turnover_p2_v1, discovery_wave_1, the "
                    "fit harness), a canonical source-set definition and a stable config "
                    "serialisation; none of it is independently testable from inside this module"),
    },
)


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


def finding_layer(f: Mapping[str, Any]) -> str:
    """Which of the two contracts (or neither) a finding belongs to.

    A pairwise finding is placed by its pair. The K0-constitution kinds are Layer A wherever they
    arise: they are about whether the strict-parity contract has a counterparty at all.
    """
    p = f.get("pair")
    if isinstance(p, str) and p in PAIR_LAYER:
        return PAIR_LAYER[p]
    if f.get("kind") in _LAYER_A_KINDS:
        return LAYER_A
    return LAYER_EVIDENCE


# --------------------------------------------------------------------------------------------
# one side of a comparison
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SideSpec:
    """One side of a comparison, declared across all seventeen parity dimensions.

    Every dimension defaults to ``UNSPECIFIED`` and every unspecified dimension is a BLOCKING
    finding. There is no default that means "probably the same as the other side" — that default
    is what the free-intercept confound exploited.

    ``pipeline_id`` is a required assertion of code-path identity. It is how a K0 control claims
    to have come from the challenger's IDENTICAL pipeline; the dimensions cannot prove that on
    their own, and neither can the gate — see REMAINING_GAPS.
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
    aggregation: Any = UNSPECIFIED
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
                "pipeline_id_is_asserted_not_demonstrated": True,
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
                            detail=f"not one of the {len(DIMENSIONS)} parity dimensions; a typo'd "
                                   "key leaves the real dimension unspecified"))
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
    layer = PAIR_LAYER.get(pair, LAYER_EVIDENCE)
    out: list[dict] = []
    for d in DIMENSIONS:
        va, vb = getattr(a, d), getattr(b, d)
        if _is_unspecified(va) or _is_unspecified(vb):
            continue
        if _canon(va) != _canon(vb):
            out.append(_finding("dimension_mismatch", pair=pair, dimension=d,
                                layer_a_name=DIMENSION_TO_LAYER_A_NAME.get(d),
                                left=a.name, right=b.name,
                                left_value=_jsonable(va), right_value=_jsonable(vb),
                                detail=_mismatch_detail(layer, d, a, b, va, vb)))
    return out


def _mismatch_detail(layer: str, d: str, a: SideSpec, b: SideSpec, va: Any, vb: Any) -> str:
    """State the EXACT difference, not merely that one exists."""
    lead = (f"{d}: {a.name or a.role!r} declares {_jsonable(va)!r}; "
            f"{b.name or b.role!r} declares {_jsonable(vb)!r}")
    if layer == LAYER_A:
        return (lead + ". LAYER A: K0 is the challenger's own pipeline with the features removed; "
                       "this cannot legitimately differ and is not adjudicable by an ordinary "
                       "reason.")
    if layer == LAYER_B:
        return (lead + ". LAYER B: adjudicable only with a stated reason AND a code from "
                       "LAYER_B_REASON_CODES, quantified by k0_vs_incumbent.")
    return lead


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
                                   "separately written control measures a different thing. NOTE: "
                                   "equality here is an ASSERTION, not a demonstration — see "
                                   "REMAINING_GAPS.pipeline_id_is_asserted_not_demonstrated"))
    if challenger.name and challenger.name == k0.name:
        out.append(_finding("duplicate_side_name", name=challenger.name,
                            detail="challenger and K0 declare the same name; one of them is "
                                   "probably the other"))
    return out


# --------------------------------------------------------------------------------------------
# the three quantities
# --------------------------------------------------------------------------------------------

def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def uncertainty_block(uncertainty: Mapping[str, Any] | None,
                      gains: Mapping[str, Any]) -> dict:
    """An uncertainty slot for EVERY contrast, present whether or not one was supplied.

    A dropped field reads as a zero interval. So an unsupplied contrast still gets an entry that
    says, in words, that no uncertainty was supplied and the interval is unknown — not zero.

    Accepts, per contrast: a mapping with ``se``/``standard_error``, ``ci``/``interval`` (a two-
    element sequence), ``ci_level`` and ``method``; or a bare number, read as a standard error.
    """
    src = dict(uncertainty or {})
    out: dict[str, Any] = {}
    for c in CONTRASTS:
        raw = src.get(c)
        se = ci = ci_level = method = None
        if isinstance(raw, Mapping):
            se = _num(raw.get("se", raw.get("standard_error")))
            seq = raw.get("ci", raw.get("interval"))
            if isinstance(seq, (list, tuple)) and len(seq) == 2:
                lo, hi = _num(seq[0]), _num(seq[1])
                ci = None if (lo is None or hi is None) else [lo, hi]
            ci_level = _num(raw.get("ci_level"))
            method = str(raw["method"]) if raw.get("method") is not None else None
        elif raw is not None:
            se = _num(raw)
        supplied = se is not None or ci is not None
        if supplied:
            bits = []
            if se is not None:
                bits.append(f"se={se:.6f}")
            if ci is not None:
                lvl = f"{ci_level:g}" if ci_level is not None else "unstated-level"
                bits.append(f"{lvl} CI [{ci[0]:+.6f}, {ci[1]:+.6f}]")
            if method:
                bits.append(f"({method})")
            statement = " ".join(bits)
        else:
            statement = ("NO UNCERTAINTY SUPPLIED for this contrast; the interval is UNKNOWN, "
                         "not zero")
        out[c] = {"contrast": c, "available": gains.get(c) is not None, "supplied": supplied,
                  "se": se, "ci": ci, "ci_level": ci_level, "method": method,
                  "statement": statement}
    unknown = sorted(str(k) for k in src if k not in CONTRASTS)
    return {"by_contrast": out,
            "any_supplied": any(v["supplied"] for v in out.values()),
            "all_supplied": all(v["supplied"] for v in out.values()),
            "contrasts_without_uncertainty": [c for c in CONTRASTS if not out[c]["supplied"]],
            "unrecognised_contrast_keys": unknown,
            "contract": ("an uncertainty slot is reported for every contrast; where none was "
                         "supplied the report says so rather than omitting the field")}


def gain_report(metrics: Mapping[str, Any], *, lower_is_better: bool = True,
                metric_name: str = "metric",
                uncertainty: Mapping[str, Any] | None = None) -> dict:
    """The three quantities, always separate, never collapsed into one headline.

    ``challenger_vs_incumbent`` is what a challenger claims. ``k0_vs_incumbent`` is what a
    featureless control from the same pipeline already obtains. Their difference is exactly
    ``challenger_vs_k0`` — what the FEATURES bought — and that identity is asserted below so that
    a report can never present the three as if they were independently sourced.

    ``challenger_vs_k0`` is named here as the PRIMARY INCREMENTAL FEATURE TEST, and
    ``credit_denied_to_challenger`` states, as a number, the amount of apparent improvement the
    challenger does NOT get credit for because its own featureless control already captured it.
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
    gains = {
        "challenger_vs_incumbent": cvi,
        "challenger_vs_k0": cvk,
        "k0_vs_incumbent": kvi,
    }
    return {
        "metric_name": metric_name,
        "lower_is_better": bool(lower_is_better),
        "metrics": {"challenger": c, "k0": k, "incumbent": i},
        "gains": gains,
        "uncertainty": uncertainty_block(uncertainty, gains),
        "feature_value_demonstrated": None if cvk is None else bool(cvk > 0),
        "challenger_still_improves_frozen_incumbent": None if cvi is None else bool(cvi > 0),
        "free_flexibility_gain": kvi,
        "net_of_free_flexibility": net,
        "gain_identity_holds": identity,
        "primary_incremental_test": "challenger_vs_k0",
        "primary_incremental_value": cvk,
        "credit_denied_to_challenger": kvi,
        "reporting_contract": ("report all three gains; there is no single headline number. "
                               "challenger_vs_incumbent minus k0_vs_incumbent IS challenger_vs_k0. "
                               "challenger_vs_k0 is the PRIMARY incremental feature test; the "
                               "challenger receives no credit for k0_vs_incumbent"),
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
    point: it is what survives into every future report of this comparison. A code is checked
    LATER, against the layer of the finding it lands on — a code alone without a reason is still
    ``adjudication_without_reason``, which remains non-adjudicable.
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
                                       "an empty string or a reasonless mapping is not one. A "
                                       "reason code alone is not a reason either"))
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


def _validate_adjudication(f: Mapping[str, Any], layer: str, hit: Mapping[str, Any],
                           free_flex: float | None) -> tuple[bool, list[dict]]:
    """May this adjudication be applied to this finding? Layer decides.

    Returns ``(ok, aux_findings)``. ``aux_findings`` are emitted whether or not the adjudication
    is granted: a refused adjudication is itself a blocking, permanently visible finding, so a
    stale attempt to wave a Layer A defect through cannot sit in a manifest unnoticed.
    """
    key = hit["key"]
    code = str(hit.get("code") or "").strip()
    dim = f.get("dimension")
    common = {"adjudication_key": key, "adjudication_reason": hit["reason"],
              "reason_code": code or None, "target_kind": f["kind"], "dimension": dim,
              "pair": f.get("pair"), "target_layer": layer}

    if layer == LAYER_A:
        if code == LAYER_A_OVERRIDE_CODE and hit.get("layer_a_override") is True:
            return True, [_finding(
                "layer_a_parity_overridden", **common,
                detail=("EXTRAORDINARY: a challenger-vs-K0 parity defect was accepted by the "
                        "author. K0 is therefore not exactly the challenger's pipeline with the "
                        "features removed, and k0_vs_incumbent is to that extent an unsound "
                        "measurement of free flexibility. This notice cannot be suppressed."))]
        return False, [_finding(
            "layer_a_not_adjudicable", **common,
            detail=("LAYER A (challenger vs its own matched K0) is strict pipeline parity. K0 is "
                    "the challenger's pipeline with zero substantive features, so no dimension "
                    "has a legitimate reason to differ, and an ordinary reason cannot excuse one. "
                    f"The only route is code={LAYER_A_OVERRIDE_CODE!r} together with "
                    "layer_a_override=True, which is loud and permanent."))]

    if layer == LAYER_B:
        if not code:
            return False, [_finding(
                "adjudication_code_missing", **common,
                detail=("a LAYER B structural allowance must cite a named code from "
                        "LAYER_B_REASON_CODES, not free text alone, so that a reader can see at a "
                        "glance WHICH allowance was invoked and how often. Recognised codes: "
                        + ", ".join(sorted(LAYER_B_REASON_CODES))))]
        if code not in LAYER_B_REASON_CODES:
            return False, [_finding(
                "adjudication_code_unrecognised", **common, supplied_code=code,
                recognised_codes=sorted(LAYER_B_REASON_CODES),
                detail=(f"{code!r} is not in the closed LAYER_B_REASON_CODES enum. An unrecognised "
                        "code is blocking: an open vocabulary is free text with extra steps"))]
        if dim in LAYER_B_NON_ADJUDICABLE_DIMENSIONS:
            return False, [_finding(
                "layer_b_dimension_not_adjudicable", **common,
                detail=(f"{dim!r} is never adjudicable on either layer. If the two sides are "
                        "scored on different rows or different folds the metric comparison is not "
                        "a comparison; that is an invalid experiment, not a structural allowance"))]
        if free_flex is None:
            return False, [_finding(
                "layer_b_adjudication_unquantified", **common,
                detail=("a LAYER B structural difference may only be waved through when K0 "
                        "quantifies what it is worth. k0_vs_incumbent is unavailable in this "
                        "scope, so the size of the allowance is unknown and it cannot be granted"))]
        return True, []

    # evidence layer: a code is optional, but a supplied code must still be a real one.
    if code and code not in REASON_CODES:
        return False, [_finding(
            "adjudication_code_unrecognised", **common, supplied_code=code,
            recognised_codes=sorted(REASON_CODES),
            detail=f"{code!r} is not a recognised reason code")]
    return True, []


def _resolve(findings: list[dict], norm: Mapping[str, dict], *,
             free_flex: float | None = None) -> tuple[list[dict], list[str]]:
    used: set[str] = set()
    resolved: list[dict] = []
    aux: list[dict] = []
    for raw in findings:
        f = dict(raw)
        layer = finding_layer(f)
        f["layer"] = layer
        f["layer_name"] = LAYER_NAMES[layer]
        f["adjudicated"] = False
        if f["kind"] in BLOCKING and f["kind"] not in NON_ADJUDICABLE:
            for cand in _adjudication_candidates(f):
                hit = norm.get(cand)
                if not hit:
                    continue
                used.add(hit["key"])         # it matched a finding; it is not "unused"
                ok, extra = _validate_adjudication(f, layer, hit, free_flex)
                aux += extra
                if ok:
                    f["adjudicated"] = True
                    f["adjudication_key"] = hit["key"]
                    f["adjudication_reason"] = hit["reason"]
                    f["adjudication_layer"] = layer
                    f["adjudication_code"] = str(hit.get("code") or "").strip() or None
                    if layer == LAYER_B:
                        f["quantified_by_k0"] = free_flex
                    for a, b in hit.items():
                        if a not in ("key", "reason"):
                            f[f"adjudication_{a}"] = b
                break
        resolved.append(f)
    for a in aux:
        a = dict(a)
        a["layer"] = a.get("target_layer") or finding_layer(a)
        a["layer_name"] = LAYER_NAMES[a["layer"]]
        a["adjudicated"] = False
        resolved.append(a)
    return resolved, [k for k in norm if k not in used]


# --------------------------------------------------------------------------------------------
# the decision table — unmatched flexibility, made impossible to miss
# --------------------------------------------------------------------------------------------

_GAIN_MEANING = {
    "challenger_vs_incumbent": ("OPERATIONAL RELEVANCE: what the challenger claims over the "
                                "frozen incumbent. Confounds features with fitting architecture; "
                                "attributes nothing to the features"),
    "k0_vs_incumbent": ("FREE FLEXIBILITY: what a FEATURELESS control from the challenger's own "
                        "pipeline already obtains"),
    "challenger_vs_k0": ("PRIMARY TEST OF FEATURE VALUE: what the challenger's features bought "
                         "beyond its own featureless control. The only contrast in which the "
                         "features are the sole difference"),
}

#: the exact words used when a challenger beats production but not its own control. This state is
#: never described as beneficial, in any report this module produces.
#: ASCII only: this line must survive a cp1252 console without turning into mojibake.
NOT_BENEFICIAL_LABEL = ("NOT BENEFICIAL - NO FEATURE VALUE DEMONSTRATED: the challenger beats the "
                        "frozen incumbent but fails against its own featureless control")


def _headline_judgment(cvk: float | None, kvi: float | None, cvi: float | None) -> dict:
    beats_incumbent = None if cvi is None else bool(cvi > 0)
    base = {"challenger_still_improves_frozen_incumbent": beats_incumbent}
    if cvk is None:
        return {**base, "verdict": "undetermined",
                "label": "UNDETERMINED — feature value could not be evaluated",
                "features_bought_anything_beyond_k0": None,
                "feature_value_demonstrated": None,
                "statement": ("challenger_vs_k0 could not be computed, so nothing is established "
                              "about the challenger's features")}
    if cvk <= 0 and beats_incumbent:
        # THE HARD RULE. Beating production while failing your own featureless control is not a
        # feature result, and must never be worded as one.
        return {**base, "verdict": "beats_incumbent_but_fails_k0",
                "label": NOT_BENEFICIAL_LABEL,
                "features_bought_anything_beyond_k0": False,
                "feature_value_demonstrated": False,
                "statement": (
                    f"{NOT_BENEFICIAL_LABEL}. challenger_vs_incumbent = {cvi:+.6f} is positive, "
                    f"but challenger_vs_k0 = {cvk:+.6f} is not. The apparent improvement over the "
                    f"frozen incumbent is pipeline freedom, already worth "
                    f"{kvi:+.6f} to a model with zero substantive features. This must NOT be "
                    "described as a beneficial feature.")}
    if cvk <= 0:
        return {**base, "verdict": "features_bought_nothing_beyond_k0",
                "label": "NOT BENEFICIAL — no feature value demonstrated",
                "features_bought_anything_beyond_k0": False,
                "feature_value_demonstrated": False,
                "statement": (f"challenger_vs_k0 = {cvk:+.6f}: the features bought NOTHING beyond "
                              "the challenger's own featureless control")}
    if kvi is not None and kvi > 0 and cvk <= kvi:
        return {**base, "verdict": "features_bought_less_than_pipeline_freedom",
                "label": "FEATURE VALUE POSITIVE BUT SMALLER THAN FREE FLEXIBILITY",
                "features_bought_anything_beyond_k0": True,
                "feature_value_demonstrated": True,
                "statement": (f"challenger_vs_k0 = {cvk:+.6f} is positive but no larger than "
                              f"k0_vs_incumbent = {kvi:+.6f}: pipeline freedom contributed at "
                              "least as much as the features did")}
    return {**base, "verdict": "features_bought_incremental_value",
            "label": "FEATURE VALUE DEMONSTRATED beyond the matched featureless control",
            "features_bought_anything_beyond_k0": True,
            "feature_value_demonstrated": True,
            "statement": (f"challenger_vs_k0 = {cvk:+.6f}: the features bought incremental value "
                          f"beyond the featureless control"
                          + (f", which itself obtained {kvi:+.6f}" if kvi is not None else ""))}


def _layer_block(layer: str, resolved: list[dict], *,
                 gains: Mapping[str, Any] | None = None,
                 unc: Mapping[str, Any] | None = None) -> dict:
    fs = [f for f in resolved if f.get("layer") == layer]
    blocking = [f for f in fs if f["kind"] in BLOCKING and not f.get("adjudicated")]
    adjud = [f for f in fs if f.get("adjudicated")]
    mism = [f for f in fs if f["kind"] == "dimension_mismatch"]
    pair = next((p for p, v in PAIR_LAYER.items() if v == layer), None)
    block = {
        "layer": layer,
        "name": LAYER_NAMES[layer],
        "pair": pair,
        "policy": LAYER_POLICY[layer],
        "n_findings": len(fs),
        "n_blocking": len(blocking),
        "n_adjudicated": len(adjud),
        "blocking_kinds": sorted({f["kind"] for f in blocking}),
        "clean": len(fs) == 0,
    }
    block["role"] = LAYER_ROLES[layer]
    block["is_primary_test_of_feature_value"] = layer == LAYER_A
    g = dict(gains or {})
    if layer == LAYER_A:
        block["strict_dimension_map"] = {k: list(v) for k, v in LAYER_A_STRICT.items()}
        block["dimensions_in_mismatch"] = sorted({str(f.get("dimension")) for f in mism})
        block["n_overridden"] = sum(1 for f in fs if f["kind"] == "layer_a_parity_overridden")
        block["contrast"] = "challenger_vs_k0"
        block["contrast_value"] = g.get("challenger_vs_k0")
        block["uncertainty"] = (unc or {}).get("challenger_vs_k0")
        block["attribution"] = ("the ONLY contrast in which the substantive features are the sole "
                                "difference; feature value is established here or nowhere")
    if layer == LAYER_B:
        # everything a Layer B report is required to contain, in one machine-readable place.
        block["structural_differences"] = [
            {"dimension": f.get("dimension"),
             "layer_a_name": f.get("layer_a_name"),
             "challenger_value": f.get("left_value"),
             "incumbent_value": f.get("right_value"),
             "values_differ": True,
             "exact_difference": f.get("detail"),
             "adjudicated": bool(f.get("adjudicated")),
             "reason_code": f.get("adjudication_code"),
             "reason": f.get("adjudication_reason"),
             "quantified_by_k0": f.get("quantified_by_k0")}
            for f in mism]
        block["n_structural_differences"] = len(mism)
        block["never_adjudicable_dimensions"] = sorted(LAYER_B_NON_ADJUDICABLE_DIMENSIONS)
        cvi, cvk, kvi = (g.get("challenger_vs_incumbent"), g.get("challenger_vs_k0"),
                         g.get("k0_vs_incumbent"))
        block["contrasts"] = {"challenger_vs_incumbent": cvi, "k0_vs_incumbent": kvi,
                              "challenger_vs_k0": cvk}
        block["uncertainty"] = dict(unc or {})
        block["feature_adds_beyond_free_flexibility"] = None if cvk is None else bool(cvk > 0)
        block["challenger_still_improves_frozen_incumbent"] = \
            None if cvi is None else bool(cvi > 0)
        block["attribution_limit"] = (
            "LAYER B ESTABLISHES OPERATIONAL RELEVANCE ONLY. challenger_vs_incumbent confounds "
            "the features with the fitting architecture and cannot attribute any part of a gain "
            "to the features. Feature value is decided on Layer A, by challenger_vs_k0.")
    return block


def build_decision_table(*, scope: str, metric_name: str, resolved: list[dict],
                         gains: Mapping[str, Any] | None, passed: bool,
                         gains_source: str | None = None,
                         identity_holds: bool | None = None,
                         uncertainty: Mapping[str, Any] | None = None) -> dict:
    """A compact table that makes unmatched flexibility immediately visible.

    Carries: the three gains (never collapsed) each with an uncertainty slot, which layer each
    adjudication belongs to, which named reason codes were invoked and how often, everything that
    was waved through, a fully machine-readable adjudication register, and the headline judgment
    on whether the challenger's features bought anything beyond K0.

    THE HARD RULE lives in the ROWS, not in a footnote: when the challenger beats the frozen
    incumbent but fails against K0, the ``challenger_vs_incumbent`` row itself carries the
    NOT BENEFICIAL verdict, so the state cannot be read off the table as a feature win.
    """
    g = dict(gains or {})
    cvi = g.get("challenger_vs_incumbent")
    cvk = g.get("challenger_vs_k0")
    kvi = g.get("k0_vs_incumbent")
    unc = dict((uncertainty or {}).get("by_contrast") or {})
    hj = _headline_judgment(cvk, kvi, cvi)
    not_beneficial = hj["verdict"] == "beats_incumbent_but_fails_k0"

    def row(name: str) -> dict:
        r = {"row": name, "value": g.get(name), "means": _GAIN_MEANING[name],
             "layer": {"challenger_vs_k0": LAYER_A, "challenger_vs_incumbent": LAYER_B,
                       "k0_vs_incumbent": LAYER_B}[name],
             "attributes_value_to_features": name == "challenger_vs_k0",
             "uncertainty": unc.get(name),
             "verdict": None, "label": None}
        if name == "challenger_vs_incumbent":
            r["verdict"] = hj["verdict"]
            r["label"] = (NOT_BENEFICIAL_LABEL if not_beneficial else
                          ("challenger improves the frozen incumbent"
                           if (cvi is not None and cvi > 0) else
                           "challenger does not improve the frozen incumbent"
                           if cvi is not None else "not evaluated"))
            r["operational_relevance_only"] = True
        elif name == "challenger_vs_k0":
            r["verdict"] = hj["verdict"]
            r["label"] = hj["label"]
            r["feature_value_demonstrated"] = hj["feature_value_demonstrated"]
            r["is_primary_test"] = True
        else:
            r["label"] = ("free flexibility the challenger is denied credit for"
                          if kvi is not None else "not evaluated")
        return r

    codes: dict[str, int] = {}
    waved: list[dict] = []
    adjudications: list[dict] = []
    for f in resolved:
        if f.get("adjudicated"):
            code = f.get("adjudication_code")
            if code:
                codes[code] = codes.get(code, 0) + 1
            entry = {"layer": f.get("layer"), "kind": f["kind"], "dimension": f.get("dimension"),
                     "pair": f.get("pair"), "side": f.get("side"), "reason_code": code,
                     "reason": f.get("adjudication_reason"),
                     "adjudication_key": f.get("adjudication_key"),
                     "quantified_by_k0": f.get("quantified_by_k0"),
                     "fold": f.get("fold")}
            adjudications.append(entry)
            waved.append(entry)
        elif f["kind"] == "layer_a_parity_overridden":
            code = f.get("reason_code")
            if code:
                codes[code] = codes.get(code, 0) + 1
            waved.append({"layer": LAYER_A, "kind": f["kind"], "dimension": f.get("dimension"),
                          "pair": f.get("pair"), "side": None, "reason_code": code,
                          "reason": f.get("adjudication_reason"),
                          "adjudication_key": f.get("adjudication_key"),
                          "quantified_by_k0": None, "fold": f.get("fold")})

    table = {
        "schema": "comparison_gate.decision_table/2",
        "scope": scope,
        "metric_name": metric_name,
        "gains_source": gains_source,
        "gains": [row(r) for r in CONTRASTS],
        "uncertainty": dict(uncertainty or {}),
        "identity": "challenger_vs_incumbent - k0_vs_incumbent == challenger_vs_k0",
        "identity_holds": identity_holds,
        "primary_incremental_test": "challenger_vs_k0",
        "primary_incremental_value": cvk,
        "primary_test_layer": LAYER_A,
        "credit_denied_to_challenger": kvi,
        "credit_denied_note": ("the challenger receives NO credit for k0_vs_incumbent: its own "
                               "featureless control already captured that much"),
        "feature_value_demonstrated": hj["feature_value_demonstrated"],
        "challenger_still_improves_frozen_incumbent":
            hj["challenger_still_improves_frozen_incumbent"],
        "beats_incumbent_but_fails_k0": not_beneficial,
        "not_beneficial_label": NOT_BENEFICIAL_LABEL if not_beneficial else None,
        "layers": [_layer_block(LAYER_A, resolved, gains=g, unc=unc),
                   _layer_block(LAYER_B, resolved, gains=g, unc=unc),
                   _layer_block(LAYER_EVIDENCE, resolved, gains=g, unc=unc)],
        # -- machine-readable adjudication register. A consumer can enumerate every adjudication,
        # its dimension, its reason code and its reason text without parsing any prose.
        "adjudication_register": adjudications,
        "n_adjudications": len(adjudications),
        "adjudications_by_layer": {
            LAYER_A: [a for a in adjudications if a["layer"] == LAYER_A],
            LAYER_B: [a for a in adjudications if a["layer"] == LAYER_B],
            LAYER_EVIDENCE: [a for a in adjudications if a["layer"] == LAYER_EVIDENCE],
        },
        "reason_codes_invoked": dict(sorted(codes.items())),
        "reason_codes_available": sorted(LAYER_B_REASON_CODES),
        "unmatched_flexibility_waved_through": waved,
        "n_waved_through": len(waved),
        "flexibility_was_waved_through": bool(waved),
        "headline_judgment": hj,
        "caveats": [dict(gap) for gap in REMAINING_GAPS],
        "passed": bool(passed),
    }
    table["text"] = render_decision_table(table)
    return table


def _fmt(v: Any) -> str:
    return "        n/a" if v is None else f"{float(v):+11.6f}"


def render_decision_table(table: Mapping[str, Any]) -> str:
    """Fixed-width rendering. A reader who skims cannot miss what was waved through."""
    L: list[str] = []
    L.append("=" * 96)
    L.append(f"COMPARISON DECISION TABLE  scope={table['scope']}  metric={table['metric_name']}"
             + (f"  (gains from {table['gains_source']})" if table.get("gains_source") else ""))
    L.append("=" * 96)
    for row in table["gains"]:
        L.append(f"  {row['row']:<26}{_fmt(row['value'])}   [layer {row['layer']}] {row['means']}")
        u = row.get("uncertainty")
        L.append(f"      uncertainty: {u['statement'] if u else 'NO UNCERTAINTY SUPPLIED'}")
        if row.get("label"):
            mark = "  *** " if row["row"] == "challenger_vs_incumbent" and \
                table.get("beats_incumbent_but_fails_k0") else "      "
            L.append(f"{mark}verdict: {row['label']}")
    L.append(f"  identity: {table['identity']}  [{table['identity_holds']}]")
    L.append(f"  credit DENIED to challenger:{_fmt(table['credit_denied_to_challenger'])}"
             "   already captured by K0, not by the features")
    if table.get("beats_incumbent_but_fails_k0"):
        L.append("  " + "!" * 92)
        L.append(f"  !! {table['not_beneficial_label']}")
        L.append("  !! This challenger must NOT be described as a beneficial feature.")
        L.append("  " + "!" * 92)
    L.append("-" * 96)
    for blk in table["layers"]:
        head = (f"  LAYER {blk['layer']:<8} {str(blk['pair'] or '-'):<22} "
                f"findings={blk['n_findings']:<3} blocking={blk['n_blocking']:<3} "
                f"adjudicated={blk['n_adjudicated']:<3}")
        if blk["layer"] == LAYER_A:
            head += f" overridden={blk.get('n_overridden', 0)}"
            head += "  CLEAN" if blk["clean"] else ""
        L.append(head)
        for sd in blk.get("structural_differences", []):
            mark = "ADJUDICATED" if sd["adjudicated"] else "BLOCKING"
            L.append(f"      - {sd['dimension']:<24} [{sd['reason_code'] or 'NO CODE'}] {mark}")
            L.append(f"          challenger: {sd['challenger_value']!r}")
            L.append(f"          incumbent : {sd['incumbent_value']!r}")
            if sd["quantified_by_k0"] is not None:
                L.append(f"          k0_vs_incumbent quantifies this at "
                         f"{float(sd['quantified_by_k0']):+.6f}")
        for d in blk.get("dimensions_in_mismatch", []):
            L.append(f"      - {d:<24} LAYER A MISMATCH - strict, not adjudicable by an "
                     "ordinary reason")
        if blk["layer"] == LAYER_B:
            L.append(f"      contrasts: cvi={_fmt(blk['contrasts']['challenger_vs_incumbent'])} "
                     f"kvi={_fmt(blk['contrasts']['k0_vs_incumbent'])} "
                     f"cvk={_fmt(blk['contrasts']['challenger_vs_k0'])}")
            L.append("      feature adds beyond free flexibility: "
                     f"{blk['feature_adds_beyond_free_flexibility']}"
                     "   |   challenger still improves the frozen incumbent: "
                     f"{blk['challenger_still_improves_frozen_incumbent']}")
            L.append(f"      {blk['attribution_limit']}")
    L.append("-" * 96)
    codes = table["reason_codes_invoked"]
    L.append("  REASON CODES INVOKED: "
             + (", ".join(f"{k} x{v}" for k, v in codes.items()) if codes else "none"))
    if table["flexibility_was_waved_through"]:
        L.append("  *** FLEXIBILITY WAVED THROUGH: "
                 f"{table['n_waved_through']} difference(s) accepted, listed above ***")
    else:
        L.append("  no flexibility waved through: every difference is either absent or blocking")
    hj = table["headline_judgment"]
    L.append(f"  VERDICT [{hj['verdict']}]: {hj['statement']}")
    L.append(f"  passed={table['passed']}   caveat: pipeline_id is ASSERTED, not demonstrated "
             "(see REMAINING_GAPS)")
    L.append("=" * 96)
    return "\n".join(L)


def _finalise(core: dict, raw: list[dict], norm: Mapping[str, dict],
              extra: list[dict], *, report_unused: bool, scope: str,
              gains: Mapping[str, Any] | None = None,
              gains_source: str | None = None,
              identity_holds: bool | None = None,
              metric_name: str = "metric",
              uncertainty: Mapping[str, Any] | None = None) -> dict:
    free_flex = None if gains is None else gains.get("k0_vs_incumbent")
    resolved, unused = _resolve(list(extra) + list(raw), norm, free_flex=free_flex)
    if report_unused:
        for k in unused:
            f = _finding("adjudication_unused", adjudication_key=k,
                         adjudication_reason=norm[k]["reason"],
                         reason_code=str(norm[k].get("code") or "").strip() or None,
                         detail="declared but matched no finding; it may be stale")
            f["layer"] = LAYER_EVIDENCE
            f["layer_name"] = LAYER_NAMES[LAYER_EVIDENCE]
            f["adjudicated"] = False
            resolved.append(f)
    blocking = [f for f in resolved if f["kind"] in BLOCKING and not f.get("adjudicated")]
    applied = [{"kind": f["kind"], "dimension": f.get("dimension"), "pair": f.get("pair"),
                "side": f.get("side"), "layer": f.get("layer"),
                "reason_code": f.get("adjudication_code"),
                "adjudication_key": f["adjudication_key"],
                "adjudication_reason": f["adjudication_reason"]}
               for f in resolved if f.get("adjudicated")]
    passed = len(blocking) == 0
    table = build_decision_table(scope=scope, metric_name=metric_name, resolved=resolved,
                                 gains=gains, passed=passed, gains_source=gains_source,
                                 identity_holds=identity_holds, uncertainty=uncertainty)
    out = dict(core)
    out.update({"findings": resolved, "blocking": blocking, "adjudications_applied": applied,
                "n_adjudicated": len(applied), "passed": passed,
                "layers": {LAYER_A: LAYER_NAMES[LAYER_A], LAYER_B: LAYER_NAMES[LAYER_B],
                           LAYER_EVIDENCE: LAYER_NAMES[LAYER_EVIDENCE]},
                "decision_table": table, "decision_table_text": table["text"],
                "remaining_gaps": [dict(g) for g in REMAINING_GAPS]})
    return out


# --------------------------------------------------------------------------------------------
# public entry points
# --------------------------------------------------------------------------------------------

def require_matched_k0(challenger: SideSpec | Mapping[str, Any] | None,
                       k0: SideSpec | Mapping[str, Any] | None, *,
                       adjudications: Mapping[str, Any] | None = None) -> dict:
    """Assert that a matched featureless control accompanies this challenger — LAYER A only.

    Checks that K0 exists, carries zero substantive features, comes from the challenger's declared
    pipeline, and matches it on every dimension. Raises ``ComparisonGateFailure`` otherwise.

    This is the load-bearing requirement of the module and it is STRICT: a mismatch here is not
    adjudicable by an ordinary reason, because K0 is by definition the challenger's own pipeline
    with the substantive features removed. A comparison without K0 is blocked outright: the
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
    core = {"schema": "comparison_gate.k0/2",
            "layer": LAYER_A,
            "layer_name": LAYER_NAMES[LAYER_A],
            "challenger": c.as_dict() if c else None,
            "k0": k.as_dict() if k else None,
            "dimensions_checked": list(DIMENSIONS), "n_dimensions": len(DIMENSIONS),
            "layer_a_strict_map": {kk: list(vv) for kk, vv in LAYER_A_STRICT.items()}}
    rep = _finalise(core, raw, norm, bad, report_unused=True, scope="layer_a_k0_match",
                    gains=None, metric_name="n/a")
    rep["matched"] = rep["passed"]
    if rep["blocking"]:
        raise ComparisonGateFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep


def _fold_core_and_findings(challenger: SideSpec | None, incumbent: SideSpec | None,
                            k0: SideSpec | None, metrics: Mapping[str, Any], *,
                            fold: str, metric_name: str, lower_is_better: bool,
                            gain_margin: float,
                            uncertainty: Mapping[str, Any] | None = None
                            ) -> tuple[dict, list[dict]]:
    raw: list[dict] = []
    raw += side_findings(challenger, "challenger")
    raw += side_findings(incumbent, "incumbent")
    if k0 is not None:
        raw += side_findings(k0, "k0")
    raw += k0_findings(challenger, k0)

    # LAYER A first: the strict contract, and the one that decides whether k0_vs_incumbent means
    # anything at all.
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

    rep = gain_report(metrics, lower_is_better=lower_is_better, metric_name=metric_name,
                      uncertainty=uncertainty)
    raw += gain_findings(rep, gain_margin=gain_margin)

    core = {
        "schema": "comparison_gate/2",
        "fold": fold,
        "sides": {"challenger": challenger.as_dict() if challenger else None,
                  "k0": k0.as_dict() if k0 else None,
                  "incumbent": incumbent.as_dict() if incumbent else None},
        "dimensions_checked": list(DIMENSIONS),
        "n_dimensions": len(DIMENSIONS),
        "pairs_checked": ["challenger|k0", "challenger|incumbent"],
        "layer_a_strict_map": {k: list(v) for k, v in LAYER_A_STRICT.items()},
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
               uncertainty: Mapping[str, Any] | None = None,
               gain_margin: float = 0.0,
               raise_on_block: bool = True) -> dict:
    """Audit ONE chronological fold (or a standalone consolidated comparison).

    ``metrics`` maps ``challenger`` / ``k0`` / ``incumbent`` to that side's value of
    ``metric_name`` on this fold. ``k0`` is positional and required: passing ``None`` is a
    deliberate, recorded refusal, not an omission.

    ``uncertainty`` optionally maps each contrast to ``{"se": ..., "ci": [lo, hi], "ci_level":
    0.95, "method": "..."}``. Every contrast gets a slot in the report whether or not one is
    supplied; an unsupplied contrast says so.

    Per-fold invocation is not optional in this program. WS3 found a 2022 stage-2 fold with
    std 7.8e-9 while pooled variance looked healthy; a consolidated comparison can average away a
    fold in which the challenger's advantage was entirely free flexibility.
    """
    c = _coerce_side(challenger, "challenger")
    i = _coerce_side(incumbent, "incumbent")
    k = _coerce_side(k0, "k0")
    core, raw = _fold_core_and_findings(c, i, k, metrics, fold=fold, metric_name=metric_name,
                                        lower_is_better=lower_is_better, gain_margin=gain_margin,
                                        uncertainty=uncertainty)
    norm, bad = _normalise_adjudications(adjudications)
    rep = _finalise(core, raw, norm, bad, report_unused=True, scope=str(fold),
                    gains=core["gains"], identity_holds=core.get("gain_identity_holds"),
                    metric_name=metric_name, uncertainty=core["uncertainty"])
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
          "adjudications": {
             "challenger|incumbent:intercept_treatment": {
                 "code": "incumbent_has_no_fitted_intercept",       # LAYER B: required
                 "reason": "Arm D is frozen and unfitted ...",      # still required
             }
          }
        }

    Per-fold ``overrides`` exist because ``training_rows`` and ``evaluation_rows`` legitimately
    differ between folds; everything else should not.

    Layer B adjudications are validated per fold against that fold's own ``k0_vs_incumbent``; the
    manifest-level roll-up re-resolves the same findings against the CONSOLIDATED gains, so the
    per-fold reports are the authoritative quantification.
    """
    metric_name = str(manifest.get("metric_name", "operational_team_mae"))
    lower = bool(manifest.get("lower_is_better", True))
    gain_margin = float(manifest.get("gain_margin", 0.0))
    challenger = _coerce_side(manifest.get("challenger"), "challenger")
    incumbent = _coerce_side(manifest.get("incumbent"), "incumbent")
    k0 = _coerce_side(manifest.get("k0"), "k0")
    folds = dict(manifest.get("folds") or {})
    consolidated = manifest.get("consolidated")
    default_unc = manifest.get("uncertainty")

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
                                             lower_is_better=lower, gain_margin=gain_margin,
                                             uncertainty=entry.get("uncertainty", default_unc))
        fold_reports[str(fid)] = _finalise(core, fraw, norm, [], report_unused=False,
                                           scope=str(fid), gains=core["gains"],
                                           identity_holds=core.get("gain_identity_holds"),
                                           metric_name=metric_name,
                                           uncertainty=core["uncertainty"])
        raw += [{**f, "fold": str(fid)} for f in fraw]

    cons_report = None
    cons_gains = None
    cons_identity = None
    cons_unc = None
    if isinstance(consolidated, Mapping):
        m = consolidated.get("metrics") if isinstance(consolidated.get("metrics"), Mapping) else \
            {r: consolidated.get(r) for r in ROLES}
        c, i, k = sides_for(consolidated)
        core, craw = _fold_core_and_findings(
            c, i, k, m, fold="consolidated", metric_name=metric_name, lower_is_better=lower,
            gain_margin=gain_margin,
            uncertainty=consolidated.get("uncertainty", default_unc))
        cons_gains = core["gains"]
        cons_identity = core.get("gain_identity_holds")
        cons_unc = core["uncertainty"]
        cons_report = _finalise(core, craw, norm, [], report_unused=False, scope="consolidated",
                                gains=cons_gains, identity_holds=cons_identity,
                                metric_name=metric_name, uncertainty=cons_unc)
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
        "schema": "comparison_gate.manifest/2",
        "scope": "manifest",
        "comparison_id": manifest.get("comparison_id"),
        "metric_name": metric_name,
        "lower_is_better": lower,
        "dimensions_checked": list(DIMENSIONS),
        "n_dimensions": len(DIMENSIONS),
        "layer_a_strict_map": {k: list(v) for k, v in LAYER_A_STRICT.items()},
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
    rep = _finalise(core, raw, norm, bad, report_unused=True, scope="manifest",
                    gains=cons_gains, gains_source="consolidated" if cons_gains else None,
                    identity_holds=cons_identity, metric_name=metric_name,
                    uncertainty=cons_unc)
    if rep["blocking"] and raise_on_block:
        raise ComparisonGateFailure(json.dumps(rep["blocking"][:6], default=str))
    return rep
