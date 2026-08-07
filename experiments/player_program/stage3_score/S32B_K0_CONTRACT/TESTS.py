#!/usr/bin/env python3
"""S32B_K0_CONTRACT/TESTS.py -- self-checks for K0_MATCHED_SCHEMA_SCORE.json.

T1  schema file parses as JSON.
T2  every const digest/count in the schema equals the value in MEASUREMENTS.json
    (which MEASURE.py computed from the frozen artifacts).
T3  the seventeen required sidespec dimension names equal the frozen
    comparison_gate.DIMENSIONS exactly.
T4  the frozen-store column-pin oneOf covers exactly the five prediction
    columns, each with its measured digest.
T5+ if the `jsonschema` package is importable: one valid E1 record validates;
    a set of deliberately broken records each FAIL (wrong digest; K0 with a
    substantive feature; E3 carried record missing the p_home/builder pin;
    CANNOT_HOST without the cannot_host block; target/estimand mismatch).
    If `jsonschema` is not installed, this block is SKIPPED and says so
    (the same gap P26 recorded).

Exit 0 on success, 1 on any failure.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # worktree root, machine-independent (verifier finding 5)
NODE = ROOT / "experiments/player_program/stage3_score/S32B_K0_CONTRACT"

failures: list[str] = []
passed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
    else:
        failures.append(f"{name}: {detail}")


# T1 -----------------------------------------------------------------------
schema = json.loads((NODE / "K0_MATCHED_SCHEMA_SCORE.json").read_text(encoding="utf-8"))
check("T1_schema_parses", True)
meas = json.loads((NODE / "MEASUREMENTS.json").read_text(encoding="utf-8"))

# T2 -----------------------------------------------------------------------
col_pin = schema["$defs"]["frozen_store_column_pin"]
comp = meas["per_method"]["composite_pace_x_eff_v1"]
check("T2_artifact_sha", col_pin["properties"]["artifact_sha256"]["const"]
      == meas["file_sha256"]["score_baseline_rows.parquet"])
check("T2_join_key_sha", col_pin["properties"]["join_key_sha256"]["const"]
      == comp["column_digests"]["game_id"]["sha256"])
check("T2_n_values", col_pin["properties"]["n_values"]["const"] == comp["n_rows"])
check("T2_sort_rule", col_pin["properties"]["sort_rule"]["const"] == comp["sort_rule"])

builder_pin = schema["$defs"]["builder_source_pin"]
check("T2_builder_sha", builder_pin["properties"]["builder_sha256"]["const"]
      == meas["file_sha256"]["build_score_baselines.py"])
rp = builder_pin["properties"]["resolved_parameters"]["const"]
brp = meas["builder_resolved_parameters"]
for k in ("EFF_EWMA_SPAN", "EFF_ALPHA", "EFF_MIN_HISTORY", "BLEND"):
    check(f"T2_param_{k}", rp[k] == brp[k], f"{rp.get(k)} != {brp.get(k)}")
check("T2_model_version", rp["model_version"] == brp["MODEL_VERSIONS"]["composite"])
ia = {a["path"]: a["sha256"] for a in builder_pin["properties"]["input_artifacts"]["const"]}
for key, rec in meas["input_artifacts_on_disk"].items():
    if key == "bookie_baseline_metrics":
        check("T2_bookie_excluded", rec["path"] not in ia,
              "bookie metrics must NOT be a rows-store input pin")
    else:
        check(f"T2_input_{key}", ia.get(rec["path"]) == rec["sha256_on_disk"])
gate_bind = schema["properties"]["comparison_gate_binding"]["properties"]
check("T2_gate_sha", gate_bind["module_sha256"]["const"]
      == meas["file_sha256"]["comparison_gate.py"])

# T3 -----------------------------------------------------------------------
sys.path.insert(0, str(ROOT / "experiments/player_program"))
import comparison_gate as cg  # noqa: E402
required_dims = schema["$defs"]["side"]["properties"]["comparison_gate_sidespec"]["required"]
check("T3_17_dims", sorted(required_dims) == sorted(cg.DIMENSIONS),
      "sidespec required list != frozen DIMENSIONS")
check("T3_n_dims_const", gate_bind["n_machine_dimensions"]["const"] == len(cg.DIMENSIONS))

# T4 -----------------------------------------------------------------------
one_of = col_pin["oneOf"]
pin_cols = {e["properties"]["column"]["const"]: e["properties"]["column_sha256"]["const"]
            for e in one_of}
expected = {c: comp["column_digests"][c]["sha256"]
            for c in ("pred_home", "pred_away", "pred_total", "pred_margin", "p_home")}
check("T4_pin_columns", pin_cols == expected, f"{pin_cols} != {expected}")
nan_pins = {e["properties"]["column"]["const"]: e["properties"]["n_nan"]["const"]
            for e in one_of}
check("T4_nan_counts", nan_pins == {c: comp["column_digests"][c]["n_nan"]
                                    for c in nan_pins})

# T5+ ----------------------------------------------------------------------
try:
    import jsonschema
    HAVE_JS = True
except ImportError:
    HAVE_JS = False

import re as _re


def _resolve_ref(ref: str, root: dict):
    assert ref.startswith("#/"), ref
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def _type_ok(v, t: str) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    return False


def _validate(inst, sch, root) -> list[str]:
    """stdlib subset of draft 2020-12 covering EXACTLY the keywords this schema
    uses: $ref (local), type (incl. unions), const (deep), enum, minLength,
    pattern, exclusiveMinimum/Maximum, minItems, maxItems, uniqueItems, items,
    contains, required, properties, additionalProperties (bool/schema), the
    boolean schemas true/false, allOf, anyOf, oneOf, if/then/else. A keyword
    outside this set would be silently ignored -- the same documented gap as
    P26's checker; hand the schema to a conformant processor when available."""
    if sch is True:
        return []
    if sch is False:
        return ["false-schema"]
    errs: list[str] = []
    if "$ref" in sch:
        errs += _validate(inst, _resolve_ref(sch["$ref"], root), root)
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_type_ok(inst, t) for t in ts):
            return errs + [f"type!={ts}"]
    if "const" in sch and inst != sch["const"]:
        errs.append("const")
    if "enum" in sch and inst not in sch["enum"]:
        errs.append("enum")
    if isinstance(inst, str):
        if len(inst) < sch.get("minLength", 0):
            errs.append("minLength")
        if "pattern" in sch and not _re.search(sch["pattern"], inst):
            errs.append("pattern")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "exclusiveMinimum" in sch and not inst > sch["exclusiveMinimum"]:
            errs.append("exclusiveMinimum")
        if "exclusiveMaximum" in sch and not inst < sch["exclusiveMaximum"]:
            errs.append("exclusiveMaximum")
    if isinstance(inst, list):
        if len(inst) < sch.get("minItems", 0):
            errs.append("minItems")
        if "maxItems" in sch and len(inst) > sch["maxItems"]:
            errs.append("maxItems")
        if sch.get("uniqueItems"):
            seen = [json.dumps(x, sort_keys=True, default=str) for x in inst]
            if len(set(seen)) != len(seen):
                errs.append("uniqueItems")
        if "items" in sch:
            for i, x in enumerate(inst):
                errs += [f"items[{i}].{e}" for e in _validate(x, sch["items"], root)]
        if "contains" in sch and not any(
                not _validate(x, sch["contains"], root) for x in inst):
            errs.append("contains")
    if isinstance(inst, dict):
        for r in sch.get("required", []):
            if r not in inst:
                errs.append(f"required:{r}")
        props = sch.get("properties", {})
        for k, sub in props.items():
            if k in inst:
                errs += [f"{k}.{e}" for e in _validate(inst[k], sub, root)]
        ap = sch.get("additionalProperties")
        if ap is not None:
            for k in inst:
                if k not in props:
                    if ap is False:
                        errs.append(f"additionalProperty:{k}")
                    elif isinstance(ap, dict):
                        errs += [f"{k}.{e}" for e in _validate(inst[k], ap, root)]
    for sub in sch.get("allOf", []):
        errs += _validate(inst, sub, root)
    if "anyOf" in sch and not any(not _validate(inst, s, root)
                                  for s in sch["anyOf"]):
        errs.append("anyOf")
    if "oneOf" in sch:
        n = sum(1 for s in sch["oneOf"] if not _validate(inst, s, root))
        if n != 1:
            errs.append(f"oneOf(matched={n})")
    if "if" in sch:
        if not _validate(inst, sch["if"], root):
            if "then" in sch:
                errs += _validate(inst, sch["then"], root)
        elif "else" in sch:
            errs += _validate(inst, sch["else"], root)
    return errs

def make_valid_e1() -> dict:
    side = {
        "name": "EXAMPLE_arm_total_v1", "role": "challenger",
        "pipeline_id": "score_fit_harness_v1",
        "substantive_features": ["rest_days_diff"],
        "structural_terms": ["composite_pred_total"],
        "declaration_routing": {"rest_days_diff": "substantive_features",
                                "composite_pred_total": "companion_components"},
        "comparison_gate_sidespec": {d: ("none" if d != "calibration_freedom" else "none")
                                     for d in cg.DIMENSIONS},
    }
    k0 = copy.deepcopy(side)
    k0.update({"name": "EXAMPLE_k0_total_v1", "role": "k0", "substantive_features": []})
    k0["declaration_routing"] = {"composite_pred_total": "companion_components"}
    return {
        "schema": "k0_matched_score/1",
        "arm_id": "EXAMPLE_arm_total_v1",
        "estimand": "E1_GAME_TOTAL",
        "element_id": "EXAMPLE_arm_total_v1::E1_GAME_TOTAL",
        "primary_metric": "mae",
        "arm_kind": "substantive_feature",
        "treatment_mechanism": {
            "statement": "rest differential shifts realized scoring totals via fatigue",
            "treatment_terms": ["rest_days_diff"],
            "tested_parameters": [],
            "claimed_signal_axes": ["schedule_rest_travel"],
            "null_construction": {
                "method": "term_removal",
                "destroys_claimed_signal": "removing the rest term removes the only schedule-axis signal carrier",
            },
        },
        "invariants": {
            "rows": "rows:n=1465:sha256=deadbeefdeadbeefdeadbeefdeadbeef",
            "target": "E1_GAME_TOTAL",
            "folds": ["train_lt_2022", "train_lt_2023", "train_lt_2024",
                      "train_lt_2025", "train_lt_2026"],
            "weights": "unit",
            "offset": "none",
            "fallback_machinery": "none",
            "nuisance_terms": [],
            "lower_order_structural_terms": [],
            "independent_unit": "game_cluster",
        },
        "estimation_objective": {
            "training_loss": "l2_squared_error",
            "response_family": "gaussian_identity",
            "shrinkage_regularization": "none",
            "p_clipping": {"applicable": False, "lower": None, "upper": None,
                           "statement": "not applicable to a points target"},
            "matched_identically_for_arm_and_k0": True,
            "s36_deviation_consequence": "ANY_PER_ARM_DEVIATION_DISCOVERED_AT_S36_VOIDS_THE_ARM",
        },
        "null_strength_floor": {
            "status": "NULL_GRANTED_INGREDIENTS_CARRIED",
            "delta_semantics": "CHALLENGER_VS_K0_MEASURES_VALUE_BEYOND_THE_PUBLIC_FLOOR",
            "null_granted_structural_terms": [{
                "term_name": "composite_pred_total",
                "routed_dimension": "companion_components",
                "byte_pin": {
                    "pin_kind": "frozen_store_column_digest",
                    "artifact_path": "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet",
                    "artifact_sha256": meas["file_sha256"]["score_baseline_rows.parquet"],
                    "method_filter": "composite_pace_x_eff_v1",
                    "sort_rule": "lexicographic on str(game_id) ascending",
                    "canonicalisation": "floats via repr(float(v)) (NaN->'nan'); ints via str(int(v)); timestamps via .isoformat(); else str(v); joined with U+001F; UTF-8; sha256 hexdigest",
                    "join_key_column": "game_id",
                    "join_key_sha256": comp["column_digests"]["game_id"]["sha256"],
                    "column": "pred_total",
                    "column_sha256": comp["column_digests"]["pred_total"]["sha256"],
                    "n_values": 1465,
                    "n_nan": 0,
                },
            }],
        },
        "nesting_reading": {
            "canonical_reading": "CYCLE1_CONTAINMENT_NULL_GRANTED_TERMS_PRESENT_IN_ARM_DESIGN",
            "arm_design_contains_null_granted_terms": True,
            "deviation": None,
        },
        "coverage_predicate": {
            "predicate_text": "both teams have >= 3 strictly-prior games with possession data and the incumbent pace prior resolves",
            "information_based_cutoff_valid_only": True,
            "market_fields_barred": True,
            "identical_for_arm_and_k0": True,
            "base_universe_game_clusters": 1491,
            "base_universe_team_game_rows": 2982,
            "pooled_retention_floor": 0.9,
            "per_fold_test_retention_floor": 0.8,
            "lower_floor_justification": None,
            "all_covered_sensitivity_row": "MANDATORY_NON_GATING",
            "whole_fold_structural_deactivation": {"declared": False},
            "selection_visibility": "ADJUDICATION_REPORT_STATES_DROPPED_GAME_COUNT_AND_NAIVE_FLOOR_ERROR_ON_DROPPED_VS_KEPT",
        },
        "comparison_gate_binding": {
            "module_path": "experiments/player_program/comparison_gate.py",
            "module_sha256": meas["file_sha256"]["comparison_gate.py"],
            "n_machine_dimensions": 17,
            "prose_to_machine_mapping": "comparison_gate.LAYER_A_STRICT",
        },
        "arm_spec": side,
        "k0_spec": k0,
        "fold_local_fallback": {"required": False, "trigger": "none",
                                "numeric_threshold": None, "action": "not_applicable",
                                "registered_before_results": True},
        "verdict_label_policy": "substantive_feature arm: eligible for feature-value label via challenger_vs_k0 only",
        "k0_flat_role": "diagnostic_only",
        "registered_before_results": True,
    }


if HAVE_JS:
    _v = jsonschema.Draft202012Validator(schema)

    def valid(rec) -> bool:
        return not list(_v.iter_errors(rec))

    def errors_of(rec) -> str:
        return "; ".join(e.message for e in _v.iter_errors(rec))[:500]
else:
    def valid(rec) -> bool:
        return not _validate(rec, schema, schema)

    def errors_of(rec) -> str:
        return "; ".join(_validate(rec, schema, schema))[:500]

if True:
    rec = make_valid_e1()
    check("T5_valid_e1_validates", valid(rec), errors_of(rec))

    bad = copy.deepcopy(rec)
    bad["null_strength_floor"]["null_granted_structural_terms"][0]["byte_pin"]["column_sha256"] = "0" * 64
    check("T6_wrong_digest_fails", not valid(bad))

    bad = copy.deepcopy(rec)
    bad["k0_spec"]["substantive_features"] = ["sneaky_feature"]
    check("T7_k0_substantive_feature_fails", not valid(bad))

    bad = copy.deepcopy(rec)
    bad["estimand"] = "E3_HOME_WIN_PROB"
    bad["element_id"] = "EXAMPLE_arm_total_v1::E3_HOME_WIN_PROB"
    bad["primary_metric"] = "brier_raw_model_probability"
    bad["invariants"]["target"] = "E3_HOME_WIN_PROB"
    bad["estimation_objective"]["p_clipping"] = {
        "applicable": True, "lower": 0.01, "upper": 0.99, "statement": "clip"}
    # still carries only the pred_total ingredient -> must FAIL the E3 containment
    check("T8_e3_without_p_home_pin_fails", not valid(bad))

    bad = copy.deepcopy(rec)
    bad["null_strength_floor"] = {
        "status": "CANNOT_HOST",
        "delta_semantics": "CHALLENGER_VS_K0_MEASURES_VALUE_BEYOND_THE_PUBLIC_FLOOR"}
    check("T9_cannot_host_without_block_fails", not valid(bad))

    bad = copy.deepcopy(rec)
    bad["invariants"]["target"] = "E2_FINAL_MARGIN_HOME"
    check("T10_target_estimand_mismatch_fails", not valid(bad))

    bad = copy.deepcopy(rec)
    bad["invariants"]["folds"] = ["train_lt_2022"]
    check("T11_wrong_folds_fails", not valid(bad))

    bad = copy.deepcopy(rec)
    bad["nesting_reading"]["arm_design_contains_null_granted_terms"] = False
    check("T12_non_nested_without_deviation_fails", not valid(bad))

    bad = copy.deepcopy(rec)
    bad["arm_spec"]["comparison_gate_sidespec"].pop("calibration_freedom")
    check("T13_missing_calibration_freedom_fails", not valid(bad))

    # T14: the builder-pin path also satisfies the E3 containment
    e3 = copy.deepcopy(rec)
    e3["estimand"] = "E3_HOME_WIN_PROB"
    e3["element_id"] = "EXAMPLE_arm_total_v1::E3_HOME_WIN_PROB"
    e3["primary_metric"] = "brier_raw_model_probability"
    e3["invariants"]["target"] = "E3_HOME_WIN_PROB"
    e3["estimation_objective"]["p_clipping"] = {
        "applicable": True, "lower": 0.01, "upper": 0.99,
        "statement": "raw model p clipped to [0.01, 0.99] before Brier"}
    e3["null_strength_floor"]["null_granted_structural_terms"] = [{
        "term_name": "composite_builder_reconstruction",
        "routed_dimension": "companion_components",
        "byte_pin": {
            "pin_kind": "builder_source_and_resolved_parameters",
            "builder_path": "experiments/market_program/SCORE_BASELINES/build_score_baselines.py",
            "builder_sha256": meas["file_sha256"]["build_score_baselines.py"],
            "resolved_parameters": {
                "EFF_EWMA_SPAN": 10, "EFF_ALPHA": 0.18181818181818182,
                "EFF_MIN_HISTORY": 3, "BLEND": 0.5,
                "model_version": "composite_pace_x_eff_v1",
                "win_prob": "logistic(intercept + slope*pred_margin) fitted on strictly-prior seasons only, walk-forward, never pooled; 2021 has no prior season and gets no p_home"},
            "input_artifacts": [
                {"path": "data/masters/master_team.parquet",
                 "sha256": meas["input_artifacts_on_disk"]["master_team"]["sha256_on_disk"]},
                {"path": "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet",
                 "sha256": meas["input_artifacts_on_disk"]["team_possession_prior_v1"]["sha256_on_disk"]},
                {"path": "experiments/player_program/possessions_v2/possessions_raw_v2.parquet",
                 "sha256": meas["input_artifacts_on_disk"]["possessions_raw_v2"]["sha256_on_disk"]}],
            "regenerated_column_digests_must_match_frozen_store": True}}]
    check("T14_builder_pin_satisfies_e3", valid(e3), errors_of(e3))

    # T15: a builder pin with a WRONG resolved parameter fails (const is deep)
    bad = copy.deepcopy(e3)
    bad["null_strength_floor"]["null_granted_structural_terms"][0]["byte_pin"][
        "resolved_parameters"]["EFF_EWMA_SPAN"] = 20
    check("T15_wrong_builder_param_fails", not valid(bad))

print(f"passed: {passed}  failed: {len(failures)}"
      + ("  (jsonschema available)" if HAVE_JS
         else "  (jsonschema NOT available; stdlib subset validator used "
              "for T5-T15 -- documented gap, same class as P26's)"))
for f in failures:
    print("  FAIL:", f)
sys.exit(1 if failures else 0)
