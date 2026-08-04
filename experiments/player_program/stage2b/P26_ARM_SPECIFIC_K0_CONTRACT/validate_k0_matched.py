#!/usr/bin/env python3
"""validate_k0_matched.py -- validate a K0_MATCHED specification AGAINST ITS ARM.

Two halves, both binding:

  1. SHAPE.  K0_MATCHED_SCHEMA.json, checked by a deliberately small stdlib subset-validator
     (`check_schema`).  `jsonschema` is NOT installed in this environment (measured), so this is a
     SUBSET implementation covering exactly the keywords the schema uses: type, required,
     properties, additionalProperties (false or schema), enum, const, minLength, minItems,
     uniqueItems, items, $ref to local $defs.  It is not a conformant JSON Schema processor and is
     not offered as one.

  2. RELATION.  `check_relation` -- the cross-field rules JSON Schema cannot express.  These are
     the rules that make the null MATCHED to THIS arm rather than merely well-formed.

This module is a CALL-SITE wrapper.  It edits nothing frozen.  `bind_and_require_matched_k0`
runs the relation checks FIRST and only then delegates to the frozen
`comparison_gate.require_matched_k0`, because the frozen gate has no notion of arm_id, no
calibration-slope dimension, and no view of structural-term closure (all measured -- see
REPORT.md M7).

Python 3.13, stdlib only apart from the optional comparison_gate delegation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "K0_MATCHED_SCHEMA.json"

#: the seventeen comparison_gate parity dimensions, restated so this module can be run without
#: importing the frozen gate. `check_relation` asserts the two lists agree when the gate is
#: importable; a divergence is itself a blocking finding (`dimension_list_drift`).
GATE_DIMENSIONS: tuple[str, ...] = (
    "intercept_treatment", "calibration_freedom", "penalty_treatment", "exposure_offset",
    "training_rows", "evaluation_rows", "chronological_folds", "clipping", "link_function",
    "preprocessing", "missing_value_handling", "companion_components", "fallback_rules",
    "aggregation", "candidate_universe", "post_processing", "prediction_universe",
)

#: dimensions that encode FITTING FLEXIBILITY. A difference on any of these between an arm and its
#: matched null is free flexibility, not a feature effect, whatever the arm calls it.
FLEXIBILITY_DIMENSIONS: frozenset[str] = frozenset({
    "intercept_treatment", "calibration_freedom", "penalty_treatment", "link_function",
    "preprocessing", "fallback_rules", "companion_components", "post_processing",
})

#: kinds whose matched null must FIX a parameter rather than remove a term.
KINDS_REQUIRING_FIXED_PARAMETER: frozenset[str] = frozenset({
    "calibration_only", "structural_reparameterisation", "hierarchical_pooling",
})

BLOCKING_KINDS: frozenset[str] = frozenset({
    "schema_violation", "arm_id_missing", "arm_id_duplicated", "k0_not_keyed_by_arm",
    "invariant_mismatch", "exclusion_not_minimal", "treatment_term_survives_in_k0",
    "structural_closure_violated", "lower_order_term_missing_from_k0",
    "k0_declares_substantive_features", "free_flexibility_granted",
    "tested_parameter_missing", "null_value_not_null", "null_construction_inadequate",
    "permutation_axis_not_claimed", "fold_local_fallback_unregistered",
    "k0_flat_used_as_promotion_control", "verdict_label_exceeds_arm_kind",
    "dimension_list_drift", "term_unrouted",
})


class K0ContractFailure(RuntimeError):
    """Raised when a K0_MATCHED record is not a matched null for its arm."""


def _f(kind: str, **kw: Any) -> dict:
    return {"kind": kind, "blocking": kind in BLOCKING_KINDS, **kw}


# ---------------------------------------------------------------------------------------------
# 1. SHAPE -- stdlib subset validator
# ---------------------------------------------------------------------------------------------

_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
          "number": (int, float), "integer": int, "null": type(None)}


def _type_ok(v: Any, t: str) -> bool:
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    py = _TYPES.get(t)
    return py is not None and isinstance(v, py) and not (t != "boolean" and isinstance(v, bool))


def _resolve(ref: str, root: dict) -> dict:
    node: Any = root
    for part in ref.lstrip("#/").split("/"):
        if not part:
            continue
        node = node[part]
    return node


def check_schema(inst: Any, schema: dict, root: dict | None = None,
                 path: str = "$") -> list[dict]:
    """Subset JSON-Schema check. Returns ``schema_violation`` findings; [] means shape-valid."""
    root = root if root is not None else schema
    out: list[dict] = []
    if "$ref" in schema:
        return check_schema(inst, _resolve(schema["$ref"], root), root, path)
    if "const" in schema and inst != schema["const"]:
        out.append(_f("schema_violation", path=path, rule="const",
                      expected=schema["const"], got=inst))
    if "enum" in schema and inst not in schema["enum"]:
        out.append(_f("schema_violation", path=path, rule="enum",
                      expected=schema["enum"], got=inst))
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(inst, t) for t in ts):
            out.append(_f("schema_violation", path=path, rule="type", expected=ts,
                          got=type(inst).__name__))
            return out
    if isinstance(inst, str) and "minLength" in schema and len(inst) < schema["minLength"]:
        out.append(_f("schema_violation", path=path, rule="minLength",
                      expected=schema["minLength"], got=len(inst)))
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]:
            out.append(_f("schema_violation", path=path, rule="minItems",
                          expected=schema["minItems"], got=len(inst)))
        if schema.get("uniqueItems") and len(inst) != len({json.dumps(x, sort_keys=True)
                                                           for x in inst}):
            out.append(_f("schema_violation", path=path, rule="uniqueItems", got=inst))
        if "items" in schema:
            for i, v in enumerate(inst):
                out += check_schema(v, schema["items"], root, f"{path}[{i}]")
    if isinstance(inst, dict):
        for r in schema.get("required", []):
            if r not in inst:
                out.append(_f("schema_violation", path=path, rule="required", missing=r))
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props:
                out += check_schema(v, props[k], root, f"{path}.{k}")
            else:
                ap = schema.get("additionalProperties", True)
                if ap is False:
                    out.append(_f("schema_violation", path=path, rule="additionalProperties",
                                  unexpected=k))
                elif isinstance(ap, dict):
                    out += check_schema(v, ap, root, f"{path}.{k}")
    return out


# ---------------------------------------------------------------------------------------------
# 2. RELATION -- is this null MATCHED TO THIS ARM?
# ---------------------------------------------------------------------------------------------

def _factors(term: str) -> list[str]:
    """'TIER:opp_pace' -> ['TIER', 'opp_pace']. A bare term is its own single factor."""
    return [p for p in term.split(":") if p]


def check_relation(rec: dict) -> list[dict]:
    """The rules that make a well-formed record a MATCHED null. Returns findings; [] means valid."""
    out: list[dict] = []
    arm, k0 = rec.get("arm_spec", {}), rec.get("k0_spec", {})
    tm = rec.get("treatment_mechanism", {})
    arm_id = str(rec.get("arm_id") or "").strip()
    kind = rec.get("arm_kind")

    # R0 -- the record must be keyed by an arm_id, and both sides must name it.
    if not arm_id:
        out.append(_f("arm_id_missing", detail="K0_MATCHED is a MAP keyed by arm_id; a record "
                                               "without one is the universal object S9 rejects"))

    # R1 -- dimension list drift against the frozen gate.
    try:
        import sys
        sys.path.insert(0, str(HERE.parents[1]))
        import comparison_gate as CG                                        # noqa: PLC0415
        if tuple(CG.DIMENSIONS) != GATE_DIMENSIONS:
            out.append(_f("dimension_list_drift", gate=list(CG.DIMENSIONS),
                          contract=list(GATE_DIMENSIONS),
                          detail="this wrapper's dimension list no longer matches the frozen "
                                 "gate's; the wrapper, not the gate, must be corrected"))
    except Exception as e:                                    # pragma: no cover - env dependent
        out.append(_f("comparison_gate_unavailable", error=repr(e), blocking=False))

    a_dims = arm.get("comparison_gate_sidespec", {}) or {}
    k_dims = k0.get("comparison_gate_sidespec", {}) or {}

    # R2 -- INVARIANTS. Every dimension except the row/fold-local ones must be byte-identical.
    #       rows, folds, target, weights and offset are additionally pinned in `invariants`.
    for d in GATE_DIMENSIONS:
        if a_dims.get(d) != k_dims.get(d):
            out.append(_f("invariant_mismatch", dimension=d, arm=a_dims.get(d), k0=k_dims.get(d),
                          detail="the matched null holds every parity dimension identical; the "
                                 "ONLY permitted difference is the treatment mechanism, which "
                                 "lives in substantive_features"))
    inv = rec.get("invariants", {})
    if inv.get("offset") not in (None, a_dims.get("exposure_offset")):
        out.append(_f("invariant_mismatch", dimension="offset",
                      arm=a_dims.get("exposure_offset"), k0=inv.get("offset"),
                      detail="invariants.offset must be the same string the sidespec declares"))
    if list(inv.get("folds") or []) != list(a_dims.get("chronological_folds") or []):
        out.append(_f("invariant_mismatch", dimension="folds",
                      arm=a_dims.get("chronological_folds"), k0=inv.get("folds")))

    # R3 -- the frozen gate BLOCKS any K0 with non-empty substantive_features (measured).
    if list(k0.get("substantive_features") or []):
        out.append(_f("k0_declares_substantive_features",
                      substantive_features=list(k0.get("substantive_features")),
                      detail="comparison_gate.k0_findings raises k0_has_substantive_features when "
                             "k0.n_substantive_features > 0. Structural terms belong in "
                             "k0_spec.structural_terms and are carried in a structural dimension"))

    # R4 -- EXCLUSION MINIMALITY. The null excludes EXACTLY the treatment terms, no more, no less.
    treat = set(tm.get("treatment_terms") or [])
    a_sub = set(arm.get("substantive_features") or [])
    k_sub = set(k0.get("substantive_features") or [])
    removed = a_sub - k_sub
    if removed != treat:
        out.append(_f("exclusion_not_minimal", removed=sorted(removed),
                      declared_treatment=sorted(treat),
                      removed_but_not_treatment=sorted(removed - treat),
                      treatment_but_not_removed=sorted(treat - removed),
                      detail="the matched null must exclude ONLY the treatment mechanism under "
                             "test; anything else removed is a straw control, anything else "
                             "retained is feature absorption"))
    survivors = treat & set(k0.get("structural_terms") or [])
    if survivors:
        out.append(_f("treatment_term_survives_in_k0", terms=sorted(survivors),
                      detail="a treatment term re-entered the null through the structural list"))

    # R5 -- STRUCTURAL CLOSURE. Every non-substantive structural DOF granted to the arm is in K0.
    a_str, k_str = set(arm.get("structural_terms") or []), set(k0.get("structural_terms") or [])
    if a_str != k_str:
        out.append(_f("structural_closure_violated",
                      only_in_arm=sorted(a_str - k_str), only_in_k0=sorted(k_str - a_str),
                      detail="K0 must contain EVERY non-substantive structural degree of freedom "
                             "granted to the candidate, and no others"))

    # R6 -- LOWER-ORDER (MARGINALITY) CLOSURE. Tier interactions require tier main effects in K0.
    for t in sorted(treat):
        fs = _factors(t)
        if len(fs) < 2:
            continue
        for f in fs:
            if f in a_sub or f in treat:
                continue                       # a factor that is itself substantive/treatment
            if f not in k_str:
                out.append(_f("lower_order_term_missing_from_k0", interaction=t, lower_order=f,
                              detail="a candidate with tier interactions must have the lower-order "
                                     "tier MAIN EFFECTS in its K0; otherwise the interaction is "
                                     "credited with the main effect it never had to beat"))

    # R7 -- NO FREE FLEXIBILITY (restated with its own code, so the reason is countable).
    for d in sorted(FLEXIBILITY_DIMENSIONS):
        if a_dims.get(d) != k_dims.get(d):
            out.append(_f("free_flexibility_granted", dimension=d,
                          arm=a_dims.get(d), k0=k_dims.get(d),
                          detail="no arm receives credit for free re-centring, a changed fallback, "
                                 "or a more flexible estimator"))

    # R8 -- FIXED-PARAMETER KINDS. calibration_only fixes the slope at its null value.
    params = tm.get("tested_parameters") or []
    if kind in KINDS_REQUIRING_FIXED_PARAMETER and not params:
        out.append(_f("tested_parameter_missing", arm_kind=kind,
                      detail="this kind's matched null FIXES a parameter rather than removing a "
                             "term; the parameter and its null value must be named"))
    if kind == "calibration_only":
        slopes = [p for p in params if p.get("role") == "slope"]
        if not slopes:
            out.append(_f("tested_parameter_missing", arm_kind=kind, missing_role="slope"))
        for p in slopes:
            if float(p.get("null_value", float("nan"))) != 1.0:
                out.append(_f("null_value_not_null", parameter=p.get("name"),
                              null_value=p.get("null_value"), expected=1.0,
                              detail="the matched null for a calibration arm fixes the slope at "
                                     "EXACTLY 1 -- the incumbent's own value"))
        lower = set(rec.get("invariants", {}).get("lower_order_structural_terms") or [])
        if not lower or not lower <= k_str:
            out.append(_f("lower_order_term_missing_from_k0", arm_kind=kind,
                          declared=sorted(lower), in_k0=sorted(k_str),
                          detail="a calibration arm's K0 carries the PREREGISTERED lower-order "
                                 "intercept structure; without it the null is a straw"))

    # R9 -- NULL CONSTRUCTION ADEQUACY (S9).
    nc = tm.get("null_construction") or {}
    axes = set(tm.get("claimed_signal_axes") or [])
    if nc.get("method") == "targeted_permutation":
        ax = nc.get("permutation_axis")
        if ax not in axes:
            out.append(_f("permutation_axis_not_claimed", permutation_axis=ax,
                          claimed_signal_axes=sorted(axes),
                          detail="permuting an axis the arm does not exploit destroys nothing; a "
                                 "uniform team-identity permutation silently PASSES a "
                                 "league-time level-transport arm (S9)"))
    if kind == "level_transport" and nc.get("method") == "term_removal" and \
            "league_time" in axes and not str(nc.get("destroys_claimed_signal", "")).strip():
        out.append(_f("null_construction_inadequate", arm_kind=kind, method=nc.get("method"),
                      detail="state how the construction removes the LEAGUE-TIME signal"))

    # R10 -- FOLD-LOCAL FALLBACK must be registered before results when a partition term is used.
    flb = rec.get("fold_local_fallback") or {}
    partitionish = any(("tier" in s.lower() or "level" in s.lower() or "fallback" in s.lower())
                       for s in (a_str | k_str))
    if partitionish:
        if not flb.get("required") or not flb.get("registered_before_results"):
            out.append(_f("fold_local_fallback_unregistered", structural_terms=sorted(a_str),
                          detail="a partition indicator that is identically zero in a fold is a "
                                 "blocking zero_variance finding ON THE CONTROL; the remedy must "
                                 "be frozen with a numeric trigger before any result is visible"))
        elif flb.get("numeric_threshold") is None and flb.get("action") != "refuse_to_score_fold":
            out.append(_f("fold_local_fallback_unregistered", detail="trigger has no numeric "
                                                                    "threshold"))

    # R11 -- K0_FLAT is diagnostic only.
    if rec.get("k0_flat_role") != "diagnostic_only":
        out.append(_f("k0_flat_used_as_promotion_control", got=rec.get("k0_flat_role"),
                      detail="K0_FLAT is a DIAGNOSTIC REFERENCE; beating it has NO promotion "
                             "value. K0_MATCHED[arm_id] is the sole authoritative control"))

    # R12 -- verdict label must not exceed what the arm kind can support.
    vlp = str(rec.get("verdict_label_policy") or "").lower()
    if kind == "calibration_only" and "feature value" in vlp and "not" not in vlp:
        out.append(_f("verdict_label_exceeds_arm_kind", arm_kind=kind,
                      detail="a calibration_only arm may never be reported as feature value, "
                             "however large challenger_vs_k0 is"))

    # R13 -- every declared term must be ROUTED to a gate dimension, or it is invisible.
    routes = dict(arm.get("declaration_routing") or {})
    for t in sorted(a_str | a_sub):
        if t not in routes:
            out.append(_f("term_unrouted", term=t,
                          detail="a term with no declared comparison_gate dimension is invisible "
                                 "to the frozen gate and cannot be parity-checked"))
    return out


def validate(rec: dict, schema: dict | None = None) -> dict:
    schema = schema if schema is not None else json.loads(
        SCHEMA_PATH.read_text(encoding="utf-8"))
    shape = check_schema(rec, schema)
    rel = check_relation(rec) if not shape else []
    findings = shape + rel
    blocking = [f for f in findings if f.get("blocking")]
    return {"schema": "k0_matched_validation/1", "arm_id": rec.get("arm_id"),
            "arm_kind": rec.get("arm_kind"), "shape_findings": shape, "relation_findings": rel,
            "findings": findings, "blocking": blocking, "valid": not blocking,
            "shape_checker": "stdlib subset of JSON Schema 2020-12; jsonschema is NOT installed"}


def validate_registry(records: Iterable[dict]) -> dict:
    """A K0_MATCHED REGISTRY is a map arm_id -> record. Duplicate keys are blocking."""
    recs = list(records)
    reports, seen = [], {}
    dup: list[dict] = []
    for r in recs:
        aid = r.get("arm_id")
        if aid in seen:
            dup.append(_f("arm_id_duplicated", arm_id=aid,
                          detail="K0_MATCHED[arm_id] must resolve to exactly one record"))
        seen[aid] = True
        reports.append(validate(r))
    blocking = dup + [f for rep in reports for f in rep["blocking"]]
    return {"schema": "k0_matched_registry_validation/1", "n_records": len(recs),
            "arm_ids": sorted(str(k) for k in seen), "reports": reports,
            "registry_findings": dup, "blocking": blocking, "valid": not blocking}


def bind_and_require_matched_k0(rec: dict) -> dict:
    """CALL SITE: contract first, then the FROZEN gate. Never the gate alone.

    The frozen ``comparison_gate.require_matched_k0`` has no arm_id, no calibration-slope
    dimension and no view of structural closure (measured). Calling it without this wrapper leaves
    S4, S6 and S9 unenforced.
    """
    rep = validate(rec)
    if not rep["valid"]:
        raise K0ContractFailure(json.dumps(rep["blocking"][:6], default=str))
    import sys
    sys.path.insert(0, str(HERE.parents[1]))
    import comparison_gate as CG                                            # noqa: PLC0415
    ch = CG.SideSpec(name=rec["arm_spec"]["name"], role="challenger",
                     pipeline_id=rec["arm_spec"]["pipeline_id"],
                     substantive_features=tuple(rec["arm_spec"]["substantive_features"]),
                     **rec["arm_spec"]["comparison_gate_sidespec"])
    k0 = CG.SideSpec(name=rec["k0_spec"]["name"], role="k0",
                     pipeline_id=rec["k0_spec"]["pipeline_id"],
                     substantive_features=tuple(rec["k0_spec"]["substantive_features"]),
                     **rec["k0_spec"]["comparison_gate_sidespec"])
    gate = CG.require_matched_k0(ch, k0)
    return {"schema": "k0_matched_binding/1", "arm_id": rec["arm_id"],
            "contract_report": rep, "gate_report": gate,
            "matched": bool(rep["valid"] and gate["matched"])}


if __name__ == "__main__":                                    # pragma: no cover - CLI
    import sys
    for p in sys.argv[1:]:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        rs = validate_registry(d.values() if isinstance(d, dict) and "arm_id" not in d else [d])
        print(json.dumps(rs, indent=2))
        if not rs["valid"]:
            raise SystemExit(1)
