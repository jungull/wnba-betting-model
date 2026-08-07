r"""Subset JSON-Schema 2020-12 validator that RAISES on any keyword it does not implement,
plus the S32B cross-field rules R1-R5 / R11 and the S33R additions N1-N5.

Deliberately stricter than the S33 validator, which silently ignored unknown keywords and
matched R5 by intent rather than by key (S34 finding B1).
"""
import re

ANNOTATION = {"$schema", "$id", "title", "description", "$comment", "default", "examples",
              "deprecated", "readOnly", "writeOnly"}
IMPLEMENTED = {"type", "const", "enum", "required", "properties", "additionalProperties",
               "items", "minItems", "maxItems", "uniqueItems", "minLength", "maxLength",
               "pattern", "allOf", "anyOf", "oneOf", "not", "if", "then", "else",
               "$ref", "$defs", "contains", "minimum", "maximum",
               "exclusiveMinimum", "exclusiveMaximum", "propertyNames"}

TYPES = {"object": dict, "array": list, "string": str, "boolean": bool,
         "number": (int, float), "integer": int, "null": type(None)}


class UnhandledKeyword(Exception):
    pass


def _typeok(inst, t):
    if t == "integer":
        return isinstance(inst, int) and not isinstance(inst, bool)
    if t == "number":
        return isinstance(inst, (int, float)) and not isinstance(inst, bool)
    if t == "boolean":
        return isinstance(inst, bool)
    py = TYPES[t]
    if isinstance(inst, bool) and t in ("number", "integer"):
        return False
    return isinstance(inst, py)


def validate(inst, schema, root, path="$"):
    """returns list of error strings; raises UnhandledKeyword on an unimplemented keyword"""
    errs = []
    if schema is True or schema == {}:
        return errs
    if schema is False:
        return [f"{path}: schema is false (property forbidden)"]
    for kw in schema:
        if kw in ANNOTATION or kw in IMPLEMENTED or kw.startswith("x_"):
            continue
        raise UnhandledKeyword(f"{path}: unimplemented schema keyword {kw!r}")

    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            raise UnhandledKeyword(f"{path}: non-local $ref {ref}")
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        errs += validate(inst, node, root, path)

    if "type" in schema:
        t = schema["type"]
        ts = t if isinstance(t, list) else [t]
        if not any(_typeok(inst, x) for x in ts):
            errs.append(f"{path}: type {ts} violated by {type(inst).__name__}")
    if "const" in schema and inst != schema["const"]:
        errs.append(f"{path}: const mismatch")
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: {inst!r} not in enum")
    if isinstance(inst, str):
        if "minLength" in schema and len(inst) < schema["minLength"]:
            errs.append(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(inst) > schema["maxLength"]:
            errs.append(f"{path}: longer than maxLength")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: pattern {schema['pattern']} not matched")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append(f"{path}: below minimum")
        if "maximum" in schema and inst > schema["maximum"]:
            errs.append(f"{path}: above maximum")
        if "exclusiveMinimum" in schema and inst <= schema["exclusiveMinimum"]:
            errs.append(f"{path}: not > exclusiveMinimum")
        if "exclusiveMaximum" in schema and inst >= schema["exclusiveMaximum"]:
            errs.append(f"{path}: not < exclusiveMaximum")
    if isinstance(inst, dict):
        for r in schema.get("required", []):
            if r not in inst:
                errs.append(f"{path}: missing required {r!r}")
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props:
                errs += validate(v, props[k], root, f"{path}.{k}")
        if "additionalProperties" in schema:
            ap = schema["additionalProperties"]
            for k, v in inst.items():
                if k in props:
                    continue
                if ap is False:
                    errs.append(f"{path}: additional property {k!r} not allowed")
                elif ap is not True:
                    errs += validate(v, ap, root, f"{path}.{k}")
        if "propertyNames" in schema:
            for k in inst:
                errs += validate(k, schema["propertyNames"], root, f"{path}<key {k}>")
    if isinstance(inst, list):
        if "items" in schema:
            for i, v in enumerate(inst):
                errs += validate(v, schema["items"], root, f"{path}[{i}]")
        if schema.get("uniqueItems") and len(
                {repr(x) for x in inst}) != len(inst):
            errs.append(f"{path}: items not unique")
        if "minItems" in schema and len(inst) < schema["minItems"]:
            errs.append(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(inst) > schema["maxItems"]:
            errs.append(f"{path}: more than maxItems")
        if "contains" in schema:
            if not any(not validate(v, schema["contains"], root, path) for v in inst):
                errs.append(f"{path}: no item satisfies contains")
    for sub in schema.get("allOf", []):
        errs += validate(inst, sub, root, path)
    if "anyOf" in schema:
        if not any(not validate(inst, s, root, path) for s in schema["anyOf"]):
            errs.append(f"{path}: anyOf unsatisfied")
    if "oneOf" in schema:
        n = sum(1 for s in schema["oneOf"] if not validate(inst, s, root, path))
        if n != 1:
            errs.append(f"{path}: oneOf matched {n} subschemas")
    if "not" in schema:
        if not validate(inst, schema["not"], root, path):
            errs.append(f"{path}: 'not' subschema matched")
    if "if" in schema:
        cond = not validate(inst, schema["if"], root, path)
        branch = "then" if cond else "else"
        if branch in schema:
            errs += validate(inst, schema[branch], root, path)
    return errs


# ------------------------------------------------------------------ cross-field rules
def cross_field(rec):
    e = []
    arm, k0 = rec["arm_spec"], rec["k0_spec"]
    tm = rec["treatment_mechanism"]

    # R1
    if rec["element_id"] != rec["arm_id"] + "::" + rec["estimand"]:
        e.append("R1: element_id != arm_id::estimand")

    # R2 exclusion minimality + structural equality under containment
    if set(arm["substantive_features"]) - set(k0["substantive_features"]) != \
            set(tm["treatment_terms"]):
        e.append("R2: arm-minus-k0 substantive features != treatment_terms")
    if set(tm["treatment_terms"]) & set(k0["structural_terms"]):
        e.append("R2: a treatment term re-enters k0_spec.structural_terms")
    if rec["nesting_reading"]["arm_design_contains_null_granted_terms"] and \
            set(arm["structural_terms"]) != set(k0["structural_terms"]):
        e.append("R2: structural_terms differ across sides under containment")

    # R3
    for t in rec["null_strength_floor"].get("null_granted_structural_terms", []):
        if t["term_name"] not in k0["structural_terms"]:
            e.append(f"R3: {t['term_name']} not in k0_spec.structural_terms")
        if rec["nesting_reading"]["arm_design_contains_null_granted_terms"] and \
                t["term_name"] not in arm["structural_terms"]:
            e.append(f"R3: {t['term_name']} not in arm_spec.structural_terms")
        dim = t["routed_dimension"]
        if arm["comparison_gate_sidespec"][dim] != k0["comparison_gate_sidespec"][dim]:
            e.append(f"R3: routed dimension {dim} differs across sides")

    # R4
    for side, nm in ((arm, "arm"), (k0, "k0")):
        for t in list(side["structural_terms"]) + list(side["substantive_features"]):
            if t not in side["declaration_routing"]:
                e.append(f"R4: {nm} term {t} has no declaration_routing entry")

    # R5 -- LITERAL, by key, not by intent (S34 finding B1)
    subst = set(arm["substantive_features"])
    treat = set(tm["treatment_terms"])
    for t in treat:
        if ":" in t:
            factor = t.split(":")[0]
            if factor not in k0["structural_terms"] and factor not in subst and \
                    factor not in treat:
                e.append(f"R5: interaction {t} lacks main effect {factor!r} in "
                         f"k0_spec.structural_terms (literal key match)")

    # R11
    pc = rec["estimation_objective"]["p_clipping"]
    if rec["estimand"] == "E3_HOME_WIN_PROB":
        if not (pc["lower"] < pc["upper"]):
            e.append("R11: p_clipping lower !< upper")

    # P26 1.5 validator rule carried: kinds that FIX parameters need tested_parameters
    if rec["arm_kind"] in ("calibration_only", "structural_reparameterisation",
                           "hierarchical_pooling") and not tm["tested_parameters"]:
        e.append(f"P26-1.5: arm_kind {rec['arm_kind']} requires non-empty tested_parameters")

    # Layer A: all seventeen sidespec dimensions byte-identical except substantive content
    a, k = arm["comparison_gate_sidespec"], k0["comparison_gate_sidespec"]
    if set(a) != set(k):
        e.append("LayerA: sidespec dimension sets differ")
    for d in sorted(set(a) & set(k)):
        if a[d] != k[d]:
            e.append(f"LayerA: dimension {d} not byte-identical across sides")
    if len(a) != 17:
        e.append(f"LayerA: {len(a)} dimensions declared, expected 17")
    if k0["substantive_features"]:
        e.append("k0 carries substantive features (frozen gate blocks this)")
    return e
