#!/usr/bin/env python3
"""TESTS.py -- P26_ARM_SPECIFIC_K0_CONTRACT.

Standalone runnable test script (pytest is NOT available in this environment -- measured).
main() returns 0 on success, 1 on any failure.

Covers, one test per acceptance criterion plus the negative case for each:
  T01  K0_MATCHED is a MAP keyed by arm_id, not one universal object
  T02  every invariant held identical; any parity difference blocks
  T03  the null excludes ONLY the treatment mechanism (both directions)
  T04  calibration-only: slope fixed at exactly 1, lower-order intercept structure present
  T05  substantive-feature: every non-substantive structural DOF is in K0
  T06  tier interactions require lower-order tier main effects in K0
  T07  no free re-centring / changed fallback / more flexible estimator
  T08  K0_FLAT is diagnostic only
  T09  the schema validates a K0 specification against its arm (shape half)
  T10  S9: a permutation null on an unclaimed axis is rejected
  T11  S7: a partition term without a registered fold-local fallback is rejected
  T12  the frozen gate accepts the contract-valid record, and blocks the two mis-routings
  T13  the wrapper's dimension list has not drifted from the frozen gate's

Run:  python experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/TESTS.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))

import validate_k0_matched as V                                            # noqa: E402

FAILURES: list[str] = []


def check(cond: bool, label: str, extra: object = "") -> None:
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {extra}")
        FAILURES.append(label)


def kinds(rep: dict) -> set[str]:
    return {f["kind"] for f in rep["findings"]}


# ---------------------------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------------------------
FOLDS = ["2021", "2022", "2023", "2024", "2025", "2026"]
ROWS = "rows:n=2982:sha256=0000000000000000000000000000000f"

DIMS = {
    "intercept_treatment": "free_unpenalised_single_intercept",
    "calibration_freedom": "none -- no post-fit rescaling of any kind",
    "penalty_treatment": "ridge lambda=0.0; intercept unpenalised",
    "exposure_offset": "projected_team_off_possessions (incumbent team_possession_prior/1)",
    "training_rows": ROWS,
    "evaluation_rows": ROWS,
    "chronological_folds": FOLDS,
    "clipping": "none",
    "link_function": "identity",
    "preprocessing": ("standardise on the training fold only; structural terms carried: "
                      "TIER main effects {L1, L2, L3}"),
    "missing_value_handling": "none -- complete case on the 2982 resolved team-games",
    "companion_components": "none",
    "fallback_rules": "incumbent pace ladder L1 -> L2 -> L3; unresolved rows excluded",
    "aggregation": "none -- the unit of prediction is the team-game",
    "candidate_universe": "2982 resolved team-game rows over 1491 game clusters",
    "post_processing": "none",
    "prediction_universe": "2982 resolved team-game rows over 1491 game clusters",
}

STRUCTURAL = ["TIER_L1", "TIER_L2", "TIER_L3"]
ROUTES = {t: "preprocessing" for t in STRUCTURAL}


def side(name: str, role: str, sub: list[str], structural: list[str], dims: dict) -> dict:
    # copy.deepcopy of the dims dict, NOT a shared reference. Sharing one dict object between the
    # arm side and the K0 side makes every parity check trivially pass -- the two sides ARE the
    # same object. That aliasing bug appeared while writing these tests and is exactly the class
    # of defect the row/fold digests exist to prevent, so it is called out here rather than
    # silently fixed.
    return {"name": name, "role": role, "pipeline_id": "stage2b_possession_runner/1",
            "substantive_features": list(sub), "structural_terms": list(structural),
            "declaration_routing": {**{t: "preprocessing" for t in structural},
                                    **{t: "substantive_features" for t in sub}},
            "comparison_gate_sidespec": copy.deepcopy(dims)}


def substantive_record() -> dict:
    """A substantive-feature arm with TIER interactions -- the S6 shape."""
    treat = ["opp_pace_trailing", "TIER_L2:opp_pace_trailing", "TIER_L3:opp_pace_trailing"]
    return {
        "schema": "k0_matched/1",
        "arm_id": "EXAMPLE_opponent_pace_adjustment_v1",
        "arm_kind": "substantive_feature",
        "treatment_mechanism": {
            "statement": ("the opponent's own trailing pace tendency carries information the "
                          "incumbent's symmetric two-sided mean discards"),
            "treatment_terms": treat,
            "tested_parameters": [],
            "claimed_signal_axes": ["opponent_identity"],
            "null_construction": {
                "method": "term_removal",
                "destroys_claimed_signal": ("removing the opponent term and its tier interactions "
                                            "leaves the incumbent's symmetric projection, in which "
                                            "no opponent-specific quantity appears"),
            },
        },
        "invariants": {
            "rows": ROWS,
            "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
            "folds": FOLDS,
            "weights": "equal per team-game row",
            "offset": DIMS["exposure_offset"],
            "fallback_machinery": DIMS["fallback_rules"],
            "nuisance_terms": [],
            "lower_order_structural_terms": STRUCTURAL,
        },
        "arm_spec": side("arm", "challenger", treat, STRUCTURAL, DIMS),
        "k0_spec": side("k0", "k0", [], STRUCTURAL, DIMS),
        "fold_local_fallback": {
            "required": True,
            "trigger": "fold-local standard deviation of any TIER indicator on the training fold",
            "numeric_threshold": 1e-8,
            "action": "collapse_to_parent_tier",
            "registered_before_results": True,
        },
        "verdict_label_policy": ("eligible for FEATURE VALUE DEMONSTRATED only via "
                                 "challenger_vs_k0 against this record"),
        "k0_flat_role": "diagnostic_only",
        "registered_before_results": True,
    }


def calibration_record() -> dict:
    """A calibration-only arm -- the S4 shape."""
    dims = copy.deepcopy(DIMS)
    return {
        "schema": "k0_matched/1",
        "arm_id": "EXAMPLE_offset_recalibration_v1",
        "arm_kind": "calibration_only",
        "treatment_mechanism": {
            "statement": ("an affine re-map of the incumbent's own projection: it adds no "
                          "information and can only re-scale what the incumbent already emits"),
            "treatment_terms": ["projected_team_off_possessions_as_column"],
            "tested_parameters": [{"name": "b1", "role": "slope", "null_value": 1.0,
                                   "null_value_meaning": "the incumbent's own slope on its own "
                                                         "output, i.e. no recalibration"}],
            "claimed_signal_axes": ["league_time"],
            "null_construction": {
                "method": "parameter_fixed_at_null",
                "destroys_claimed_signal": ("fixing b1 at exactly 1 leaves the incumbent's "
                                            "projection entering at unit slope through the offset, "
                                            "which is the incumbent itself"),
            },
        },
        "invariants": {
            "rows": ROWS,
            "target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
            "folds": FOLDS,
            "weights": "equal per team-game row",
            "offset": dims["exposure_offset"],
            "fallback_machinery": dims["fallback_rules"],
            "nuisance_terms": [],
            "lower_order_structural_terms": STRUCTURAL,
        },
        "arm_spec": side("arm", "challenger", ["projected_team_off_possessions_as_column"],
                         STRUCTURAL, dims),
        "k0_spec": side("k0", "k0", [], STRUCTURAL, dims),
        "fold_local_fallback": {
            "required": True, "trigger": "fold-local sd of any TIER indicator",
            "numeric_threshold": 1e-8, "action": "collapse_to_parent_tier",
            "registered_before_results": True,
        },
        "verdict_label_policy": ("CALIBRATION RESULT ONLY -- this arm is NOT eligible for a "
                                 "feature value label however large challenger_vs_k0 is"),
        "k0_flat_role": "diagnostic_only",
        "registered_before_results": True,
    }


# ---------------------------------------------------------------------------------------------
def main() -> int:
    print("T00 baseline: both example records validate")
    r_sub, r_cal = substantive_record(), calibration_record()
    v_sub, v_cal = V.validate(r_sub), V.validate(r_cal)
    check(v_sub["valid"], "substantive-feature record is valid", v_sub["blocking"])
    check(v_cal["valid"], "calibration-only record is valid", v_cal["blocking"])

    print("T01 K0_MATCHED is a MAP keyed by arm_id")
    reg = V.validate_registry([r_sub, r_cal])
    check(reg["valid"] and reg["n_records"] == 2 and len(reg["arm_ids"]) == 2,
          "two arms yield two distinct K0 records", reg["blocking"])
    dupe = copy.deepcopy(r_cal)
    dupe["arm_id"] = r_sub["arm_id"]
    reg2 = V.validate_registry([r_sub, dupe])
    check(not reg2["valid"] and any(f["kind"] == "arm_id_duplicated" for f in reg2["blocking"]),
          "one arm_id may not resolve to two records")
    noid = copy.deepcopy(r_sub)
    noid["arm_id"] = ""
    check("arm_id_missing" in kinds(V.validate(noid)) or
          "schema_violation" in kinds(V.validate(noid)),
          "a record without an arm_id is rejected")

    print("T02 invariants held identical")
    for dim, bad in (("training_rows", "rows:n=2900:sha256=deadbeef"),
                     ("chronological_folds", ["2022", "2023"]),
                     ("exposure_offset", "raw_full_game_possessions"),
                     ("aggregation", "player-level roll-up")):
        r = copy.deepcopy(r_sub)
        r["k0_spec"]["comparison_gate_sidespec"][dim] = bad
        check("invariant_mismatch" in kinds(V.validate(r)), f"differing {dim} blocks")

    print("T03 the null excludes ONLY the treatment mechanism")
    r = copy.deepcopy(r_sub)
    r["k0_spec"]["structural_terms"] = ["TIER_L1"]          # K0 stripped of structure -> straw
    check("structural_closure_violated" in kinds(V.validate(r)),
          "a K0 stripped of structural terms is a straw control and blocks")
    r = copy.deepcopy(r_sub)
    r["k0_spec"]["structural_terms"] = STRUCTURAL + ["opp_pace_trailing"]
    check("treatment_term_survives_in_k0" in kinds(V.validate(r)),
          "a treatment term re-entering through the structural list blocks")
    r = copy.deepcopy(r_sub)
    r["treatment_mechanism"]["treatment_terms"] = ["opp_pace_trailing"]
    check("exclusion_not_minimal" in kinds(V.validate(r)),
          "removing more than the declared treatment blocks")

    print("T04 calibration-only fixes the tested parameter at its null value")
    r = copy.deepcopy(r_cal)
    r["treatment_mechanism"]["tested_parameters"][0]["null_value"] = 0.0
    check("null_value_not_null" in kinds(V.validate(r)), "slope null value must be exactly 1")
    r = copy.deepcopy(r_cal)
    r["treatment_mechanism"]["tested_parameters"] = []
    check("tested_parameter_missing" in kinds(V.validate(r)),
          "a calibration arm must name its tested slope")
    r = copy.deepcopy(r_cal)
    r["k0_spec"]["structural_terms"] = []
    r["arm_spec"]["structural_terms"] = []
    check("lower_order_term_missing_from_k0" in kinds(V.validate(r)),
          "the preregistered lower-order intercept structure must be in K0")
    r = copy.deepcopy(r_cal)
    r["verdict_label_policy"] = "eligible for a feature value label like any other arm"
    check("verdict_label_exceeds_arm_kind" in kinds(V.validate(r)),
          "a calibration arm may not claim feature value")

    print("T05 substantive-feature arm: every structural DOF is in K0")
    r = copy.deepcopy(r_sub)
    r["arm_spec"]["structural_terms"] = STRUCTURAL + ["SUPPORT_SIZE_SPLINE"]
    r["arm_spec"]["declaration_routing"]["SUPPORT_SIZE_SPLINE"] = "preprocessing"
    check("structural_closure_violated" in kinds(V.validate(r)),
          "a structural DOF granted to the arm but withheld from K0 blocks")

    print("T06 tier interactions require lower-order tier main effects in K0")
    r = copy.deepcopy(r_sub)
    r["arm_spec"]["structural_terms"] = ["TIER_L1"]
    r["k0_spec"]["structural_terms"] = ["TIER_L1"]
    r["invariants"]["lower_order_structural_terms"] = ["TIER_L1"]
    ks = kinds(V.validate(r))
    check("lower_order_term_missing_from_k0" in ks,
          "TIER_L2:x without TIER_L2 in K0 blocks", ks)

    print("T07 no free re-centring, changed fallback or more flexible estimator")
    for dim, bad in (("intercept_treatment", "fixed_at_zero"),
                     ("calibration_freedom", "free affine post-fit rescaling"),
                     ("penalty_treatment", "no penalty at all"),
                     ("fallback_rules", "a different ladder"),
                     ("link_function", "log")):
        r = copy.deepcopy(r_sub)
        r["k0_spec"]["comparison_gate_sidespec"][dim] = bad
        check("free_flexibility_granted" in kinds(V.validate(r)),
              f"asymmetric {dim} blocks as free flexibility")

    print("T08 K0_FLAT is diagnostic only")
    r = copy.deepcopy(r_sub)
    r["k0_flat_role"] = "promotion_control"
    ks = kinds(V.validate(r))
    check("schema_violation" in ks or "k0_flat_used_as_promotion_control" in ks,
          "K0_FLAT may not be declared a promotion control", ks)
    check(r_sub["k0_flat_role"] == "diagnostic_only" and r_cal["k0_flat_role"] == "diagnostic_only",
          "every record marks K0_FLAT diagnostic only")

    print("T09 the schema validates shape")
    schema = json.loads((HERE / "K0_MATCHED_SCHEMA.json").read_text(encoding="utf-8"))
    check(schema["$id"] == "player_program/stage2b/k0_matched/1", "schema is loadable and keyed")
    r = copy.deepcopy(r_sub)
    del r["fold_local_fallback"]
    check("schema_violation" in kinds(V.validate(r, schema)), "a missing required block blocks")
    r = copy.deepcopy(r_sub)
    r["arm_kind"] = "vibes"
    check("schema_violation" in kinds(V.validate(r, schema)), "an unknown arm_kind blocks")
    r = copy.deepcopy(r_sub)
    r["invariants"]["target"] = "raw_full_game_possessions"
    check("schema_violation" in kinds(V.validate(r, schema)),
          "the primary target is pinned by the schema and cannot be swapped")
    r = copy.deepcopy(r_sub)
    del r["k0_spec"]["comparison_gate_sidespec"]["clipping"]
    check("schema_violation" in kinds(V.validate(r, schema)),
          "an unstated parity dimension blocks -- UNSPECIFIED is never 'same as the other side'")

    print("T10 S9: a permutation null must act on a CLAIMED axis")
    r = copy.deepcopy(r_cal)
    r["treatment_mechanism"]["null_construction"] = {
        "method": "targeted_permutation", "permutation_axis": "team_identity",
        "destroys_claimed_signal": "permutes team identities within each game date"}
    check("permutation_axis_not_claimed" in kinds(V.validate(r)),
          "team-identity permutation cannot null a league-time claim")
    r2 = copy.deepcopy(r)
    r2["treatment_mechanism"]["null_construction"]["permutation_axis"] = "league_time"
    check("permutation_axis_not_claimed" not in kinds(V.validate(r2)),
          "permuting the claimed axis is accepted")

    print("T11 S7: a partition term needs a registered fold-local fallback")
    r = copy.deepcopy(r_sub)
    r["fold_local_fallback"]["registered_before_results"] = False
    check("fold_local_fallback_unregistered" in kinds(V.validate(r)),
          "an unregistered fold-local fallback blocks")
    r = copy.deepcopy(r_sub)
    r["fold_local_fallback"]["numeric_threshold"] = None
    check("fold_local_fallback_unregistered" in kinds(V.validate(r)),
          "a trigger with no numeric threshold blocks")

    print("T12 delegation to the FROZEN comparison_gate")
    import comparison_gate as CG                                            # noqa: PLC0415
    b = V.bind_and_require_matched_k0(r_sub)
    check(b["matched"] is True, "contract-valid record also passes the frozen Layer A gate", b)

    # mis-routing 1: structural terms declared in K0.substantive_features
    r = copy.deepcopy(r_sub)
    r["k0_spec"]["substantive_features"] = STRUCTURAL
    check("k0_declares_substantive_features" in kinds(V.validate(r)),
          "the contract blocks structural terms routed into k0.substantive_features")
    try:
        CG.require_matched_k0(
            CG.SideSpec(name="a", role="challenger", pipeline_id="p",
                        substantive_features=("x",), **DIMS),
            CG.SideSpec(name="b", role="k0", pipeline_id="p",
                        substantive_features=tuple(STRUCTURAL), **DIMS))
        gate_blocked = False
    except CG.ComparisonGateFailure as e:
        gate_blocked = "k0_has_substantive_features" in str(e)
    check(gate_blocked, "the FROZEN gate independently blocks the same mis-routing")

    # mis-routing 2: the S4 free slope hidden in substantive_features passes the frozen gate alone
    try:
        CG.require_matched_k0(
            CG.SideSpec(name="a", role="challenger", pipeline_id="p",
                        substantive_features=("projected_team_off_possessions",), **DIMS),
            CG.SideSpec(name="b", role="k0", pipeline_id="p",
                        substantive_features=(), **DIMS))
        s4_passes_gate_alone = True
    except CG.ComparisonGateFailure:
        s4_passes_gate_alone = False
    check(s4_passes_gate_alone,
          "S4 confirmed: the frozen gate ALONE passes a pure recalibration arm -- which is why "
          "arm_kind and verdict_label_policy must be enforced at the call site")

    print("T13 the wrapper has not drifted from the frozen gate")
    check(tuple(CG.DIMENSIONS) == V.GATE_DIMENSIONS,
          "wrapper dimension list equals comparison_gate.DIMENSIONS")
    check(len(CG.DIMENSIONS) == 17, "seventeen parity dimensions", len(CG.DIMENSIONS))

    print()
    if FAILURES:
        print(f"FAILED {len(FAILURES)}: {FAILURES}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
