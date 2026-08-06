#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for arm module A03
(A03_cal_shallow_tier_intercept), against the frozen P36 shared runner contract.

BLINDED: every frame here is synthetic (synthetic_fixture_a03.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Epistemic status of this file and everything it exercises: IMPLEMENTATION. Blinded: no agent may
inspect challenger performance. Unit, synthetic, identity and schema tests only.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A03/tests/TESTS.py
Writes: ./artifacts/A03_TEST_RECEIPT.json (machine-readable results) and
        ../A03_TEST_RECEIPT.json (summary, for the arm directory).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent          # arms/A03/tests
ARM_DIR = HERE.parent                            # arms/A03
RUNNER = ARM_DIR.parents[1] / "runner"           # P36_IMPLEMENT_ARMS/runner
for p in (str(RUNNER), str(ARM_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a03 as A03                                                  # noqa: E402
import synthetic_fixture_a03 as fx                                     # noqa: E402

RESULTS = []


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def expect_raises(exc, fn, msg):
    try:
        fn()
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}: {msg}")


# ------------------------------------------------------------------------------- tests

def t01_conformance():
    """The module satisfies runner_interface.validate_arm_module (RUNNER_INTERFACE.md section 2)."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = A03.ArmA03(fids, len(df))
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], f"A03 module must conform: {rec}")
    check(arm.arm_id == "A03_cal_shallow_tier_intercept", "arm_id must match the frozen card")
    check(arm.card_id() == arm.arm_id, "card_id defaults to arm_id")
    check(arm.declared_family() == "SUBSTANTIVE", "P35 p25_guard_invocation_pins")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "no RECALIBRATION arm survives")
    check(arm.uses_global_intercept() is False,
          "P35 intercept table: A03 in without_any_global_intercept")
    return {"conformant": True}


def t02_enumeration_element_exact():
    """Single-element arm (P33: 'ENUMERATION OBLIGATION DISCHARGED: single element t = 3');
    RUNNER_INTERFACE.md section 2 pins '{} for single-element arms'."""
    arm = A03.ArmA03([], 0)
    check(arm.enumeration_element() == {}, "single-element arm must report {}")
    check(arm.element_id() == "A03_cal_shallow_tier_intercept__t3",
          "element_id must be deterministic and name the pinned threshold")
    check(A03.SHALLOW_THRESHOLD == 3, "the card's only defensible threshold is pinned at 3")
    return {"enumeration_element": arm.enumeration_element(), "element_id": arm.element_id()}


def t03_feature_determinism():
    """build_design is a pure, fold-independent function of pace_evidence_depth (P33: t=3 is
    fixed, never fitted, never fold-local)."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = A03.ArmA03([f["fold_id"] for f in folds], len(df))

    b1 = arm.build_design(folds[0], df)
    b2 = arm.build_design(folds[-1], df)
    v1 = np.asarray(b1["columns"][A03.SHALLOW_COL])
    v2 = np.asarray(b2["columns"][A03.SHALLOW_COL])
    check(np.array_equal(v1, v2),
          "the SHALLOW column must be byte-identical across folds (no training-fold constant)")

    expected = (df["pace_evidence_depth"].to_numpy(float) <= 3.0).astype(float)
    check(np.array_equal(v1, expected), "SHALLOW must equal 1[pace_evidence_depth <= 3] exactly")
    check(set(np.unique(v1)) <= {0.0, 1.0}, "SHALLOW must be a strict 0/1 indicator")

    # re-running build_design must reproduce the identical array (no hidden RNG / state)
    b3 = arm.build_design(folds[0], df)
    check(np.array_equal(v1, np.asarray(b3["columns"][A03.SHALLOW_COL])),
          "build_design must be deterministic across repeated calls")
    return {"n_shallow": int(v1.sum()), "n_rows": int(len(v1))}


def t04_no_intercept_no_nuisance():
    """P35 K0 K2 / intercept_structure: no global intercept, arm or null; P33 k0_matched:
    zero-parameter null IS the incumbent."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = A03.ArmA03([f["fold_id"] for f in folds], len(df))
    b = arm.build_design(folds[0], df)
    check(rc.INTERCEPT_COL not in b["treatment_cols"] + b["nuisance_cols"],
          "no implicit or explicit intercept in the arm design")
    check(b["nuisance_cols"] == [], "A03 carries no lower-order structural terms")
    ok = ri.validate_design_bundle(b, df, False, str(folds[0]["fold_id"]))
    check(ok["valid"], "bundle must validate under the frozen no-intercept invariant")
    return {"checked": True}


def t05_null_nesting():
    """Arm-vs-null design nesting the card declares: term_removal, null IS a proper subset of
    the arm's terms (here the empty set), and the null column set never exceeds the arm's."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = A03.ArmA03([f["fold_id"] for f in folds], len(df))
    b = arm.build_design(folds[0], df)
    k0 = b["k0_matched_design"]
    check(k0["comparison"] == "term_removal", "P33/P35: A03's comparison is term_removal")
    arm_terms = set(b["treatment_cols"]) | set(b["nuisance_cols"])
    null_terms = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(null_terms <= arm_terms, "the null's design must nest inside the arm's design")
    check(null_terms == set(), "A03's null is the zero-parameter incumbent exactly")
    check(A03.SHALLOW_COL not in null_terms,
          "the treatment term must not survive term_removal in the null")
    return {"arm_terms": sorted(arm_terms), "null_terms": sorted(null_terms)}


def t06_p26_record_passes_wrapper():
    """The P26 record validates via the shared wrapper, including the R8 calibration_only
    extended-rule adjudication (P35 r8_scope_adjudication)."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = A03.ArmA03(fids, len(df))
    rec = arm.p26_k0_record()
    check(rec["arm_kind"] == "calibration_only", "matches the frozen card's arm_kind")
    out = gh.p26_check(rec)
    check(out["valid"], f"A03's K0 record must pass the P26 wrapper: {out}")
    check(len(out["r8_filtered_findings"]) >= 1,
          "calibration_only must engage the P35 R8 extended-rule adjudication")
    check(out["r8_adjudication_basis"] is not None, "adjudication basis must be recorded")
    params = rec["treatment_mechanism"]["tested_parameters"]
    check(any(p["role"] == "intercept" and float(p["null_value"]) == 0.0 for p in params),
          "alpha_S must be declared with role intercept and null_value 0 (P33/P35 tested_parameters)")
    return {"r8_filtered_kinds": [f["kind"] for f in out["r8_filtered_findings"]]}


def t07_p26_record_rejects_survivor():
    """Negative control: a null that keeps the treatment term must fail the wrapper closed."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = A03.ArmA03([f["fold_id"] for f in folds], len(df))
    rec = json.loads(json.dumps(arm.p26_k0_record()))
    rec["k0_spec"]["substantive_features"] = [A03.SHALLOW_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(rec),
                  "a null retaining 1[SHALLOW] must be blocked")
    return {"negative_control": "blocked"}


def t08_strict_lagging_p22():
    """Strict lagging: 1[SHALLOW] passes P22 with its declared LagSpec on a synthetic frame with
    a synthetic prohibited basis, and an undeclared column is refused (absence is never a pass)."""
    df = fx.build_universe()
    basis = fx.build_prohibited_basis(df)
    arm = A03.ArmA03([], len(df))
    folds = fx.build_folds(df)
    b = arm.build_design(folds[0], df)
    W = df.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    rec = gh.p22_check(W, [A03.SHALLOW_COL], prohibited_basis=basis,
                       lag_specs=arm.lag_specs(), lag_sources=arm.lag_sources())
    check(not rec.get("blocking"), f"1[SHALLOW] must pass P22 with its declared LagSpec: {rec}")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, [A03.SHALLOW_COL], prohibited_basis=basis, lag_specs={}),
        "an undeclared LagSpec must block, never silently pass")

    # a dishonest SAME_GAME declaration for the same column must block unconditionally
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, [A03.SHALLOW_COL], prohibited_basis=basis,
        lag_specs={A03.SHALLOW_COL: {"column": A03.SHALLOW_COL, "kind": "SAME_GAME"}}),
        "SAME_GAME must block unconditionally regardless of the true construction")
    return {"p22_passed": True}


def t09_tier_symmetry_check_decidable():
    """The card's full (both-tier) S7_TIER_SUPPORT_v1 rule, evaluated directly, is decidable in
    both directions: ESTIMABLE on a balanced synthetic universe, UNEVALUABLE_PROSPECTIVELY on a
    deep-starved one -- the half of the rule the generic P27 mechanism cannot express (module
    docstring)."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    tr = folds[-1]["train_idx"]
    dec = A03.tier_symmetry_check(df, tr)
    check(dec["evaluable"] and dec["verdict"] == "ESTIMABLE",
          f"balanced synthetic universe must be estimable on both tiers: {dec}")
    check(dec["shallow_ok"] and dec["deep_ok"], "both tiers must clear the 10-cluster floor")
    check(dec["trigger_fired_on"] == [], "no trigger fires when both tiers clear")

    starved = fx.build_universe_deep_starved()
    sfolds = fx.build_folds(starved)
    str_ = A03.tier_symmetry_check(starved, sfolds[-1]["train_idx"])
    check(not str_["evaluable"] and str_["verdict"] == "UNEVALUABLE_PROSPECTIVELY",
          f"deep-starved universe must trip the DEEP-tier floor: {str_}")
    check(not str_["deep_ok"], "DEEP tier must be the one under floor in the starved fixture")
    check(("DEEP", str_["n_deep_training_clusters"]) in str_["trigger_fired_on"],
          "the fired trigger must name the DEEP tier and its measured count")

    # determinism: identical inputs, identical decision
    dec2 = A03.tier_symmetry_check(df, tr)
    check(dec == dec2, "tier_symmetry_check must be a pure function of its inputs")
    return {"balanced": dec, "starved": str_}


def t10_p27_rule_shape_and_digest():
    """p27_rule() returns (ActiveSetRule kwargs, Preregistration kwargs) whose digest matches the
    frozen P27 module's own canonicalisation, and the pair is accepted by the shared P27 wrapper."""
    arm = A03.ArmA03([], 0)
    rule_kwargs, prereg_kwargs = arm.p27_rule()
    check(rule_kwargs["rule_id"] == "S7_TIER_SUPPORT_v1", "rule id must match the card's name")
    check(rule_kwargs["min_nonzero_clusters"] == 10, "numeric trigger: 10-cluster floor")
    check(prereg_kwargs["results_visible_at_registration"] is False,
          "GATE_INVOCATION_CONTRACT section 4: registered before any result is visible")

    feg = A03._load_feg()
    recomputed = feg.ActiveSetRule(**rule_kwargs).spec_sha256
    check(prereg_kwargs["rule_spec_sha256"] == recomputed,
          "the Preregistration digest must match the rule actually being applied")

    df = fx.build_universe()
    folds = fx.build_folds(df)
    a03 = A03.ArmA03([f["fold_id"] for f in folds], len(df))
    b = a03.build_design(folds[-1], df)
    W = df.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    rec = gh.p27_check(W, candidate_features=[A03.SHALLOW_COL], nuisance_terms=[],
                       cluster_col="game_id", fold_policy="EXPANDING_PRIOR_SEASONS",
                       null_features=[], null_nuisance=[],
                       rule_kwargs=rule_kwargs, prereg_kwargs=prereg_kwargs,
                       arm_id=a03.arm_id)
    check(rec.get("overall") != "FAIL", f"P27 must accept the preregistered rule: {rec}")
    return {"rule_spec_sha256": prereg_kwargs["rule_spec_sha256"], "p27_overall": rec["overall"]}


def t11_kill_conditions_decidable():
    """The card's kill_conditions_frozen, evaluated as a pure decision function on synthetic
    numbers: no-rejection kill fires when every evaluable fold's interval covers 0; sign
    instability fires independently; neither fires on genuine, sign-stable, non-zero evidence."""
    killed = A03.evaluate_kill_conditions({
        "a03_syn_lt_4002": (-0.02, 0.03),
        "a03_syn_lt_4003": (-0.01, 0.05),
        "a03_syn_lt_4004": (-0.04, 0.02),
    })
    check(killed["killed"] is True and killed["no_rejection_kill"] is True,
          "interval covering 0 in every evaluable fold must kill")

    survives = A03.evaluate_kill_conditions({
        "a03_syn_lt_4002": (0.01, 0.09),
        "a03_syn_lt_4003": (0.02, 0.11),
        "a03_syn_lt_4004": (0.03, 0.08),
    }, fold_alpha_point={"a03_syn_lt_4002": 0.05, "a03_syn_lt_4003": 0.06,
                         "a03_syn_lt_4004": 0.055})
    check(survives["killed"] is False, "consistently positive, non-zero-covering evidence must "
                                       "not be killed")

    unstable = A03.evaluate_kill_conditions({
        "a03_syn_lt_4002": (0.01, 0.09),
        "a03_syn_lt_4003": (-0.11, -0.02),
    }, fold_alpha_point={"a03_syn_lt_4002": 0.05, "a03_syn_lt_4003": -0.06})
    check(unstable["killed"] is True and unstable["sign_instability"] is True,
          "opposite-signed point estimates across evaluable folds must kill")

    empty = A03.evaluate_kill_conditions({})
    check(empty["killed"] is None, "an empty evaluable-fold set is undecidable, not a fired kill")
    return {"no_rejection_kill": killed, "survives": survives, "unstable": unstable}


def t12_end_to_end_synthetic():
    """Full synthetic exercise of the shared runner against this arm module: blinding, guard byte
    pins, conformance, P26-before-P25, per-fold P22/P25, P27, paired point fits, test bootstrap,
    train-refit bootstrap, K0_FLAT diagnostic, receipt -- all on synthetic rows only."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    basis = fx.build_prohibited_basis(df)
    arm = A03.ArmA03([f["fold_id"] for f in folds], len(df))
    out_path = HERE / "artifacts" / "A03_receipt.json"
    out_path.parent.mkdir(exist_ok=True)
    t0 = time.time()
    rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                     out_path=out_path, run_git=False)
    dt = time.time() - t0
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(out_path.exists(), "receipt file written")
    check(rec["arm_id"] == arm.arm_id, "receipt must carry the arm id")
    check(set(rec["results"]["evaluable_folds"]) <= {f["fold_id"] for f in folds},
          "evaluable folds must be a subset of the supplied folds")
    check(rec["seeds"]["master_seed"] == rc.MASTER_SEED, "seed manifest master pin")
    check(rec["guard_records"]["p26"]["valid"], "P26 must pass on the synthetic universe")
    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict must not be FAIL")

    # determinism: an identical second run reproduces the results bit-for-bit
    rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={}, run_git=False)
    import receipts as rp
    d1 = rp.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = rp.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: the runner must refuse a frame carrying a real D006 fold id, flag absent
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, df, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED")
    check(rc.UNSEAL_ENV_FLAG not in os.environ, "flag must remain absent from the real environment")

    return {"seconds": round(dt, 2), "evaluable_folds": rec["results"]["evaluable_folds"],
           "results_digest": d1,
           "note": "synthetic-only numbers; no real fold or real MAE was touched"}


def t13_arm_d_untouched_and_ownership():
    """Sanity: this unit writes nothing outside arms/A03/, never reads SEALED_RESULTS, and never
    opens/imports the incumbent Arm D implementation (D_ewma_shrunk is only ever cited
    descriptively as the offset's provenance -- this arm module never constructs, fits, or
    re-derives it)."""
    src = (ARM_DIR / "arm_a03.py").read_text(encoding="utf-8")
    check("SEALED_RESULTS" not in src, "must never reference the forbidden sealed-results path")
    import ast
    tree = ast.parse(src)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)
    check(not any("ewma" in n.lower() or "arm_d" in n.lower() for n in imported_names),
          f"arm_a03.py must not import any Arm D / D_ewma_shrunk implementation: {imported_names}")
    for p in ARM_DIR.rglob("*"):
        check(str(p.resolve()).startswith(str(ARM_DIR.resolve())),
              f"write scope violation: {p}")
    return {"ownership_ok": True, "imports": sorted(imported_names)}


TESTS = [t01_conformance, t02_enumeration_element_exact, t03_feature_determinism,
        t04_no_intercept_no_nuisance, t05_null_nesting, t06_p26_record_passes_wrapper,
        t07_p26_record_rejects_survivor, t08_strict_lagging_p22,
        t09_tier_symmetry_check_decidable, t10_p27_rule_shape_and_digest,
        t11_kill_conditions_decidable, t12_end_to_end_synthetic,
        t13_arm_d_untouched_and_ownership]


def main():
    check(rc.UNSEAL_ENV_FLAG not in os.environ,
          "P36_UNSEALED must never be set by this blinded suite")
    passed, failed = 0, 0
    for fn in TESTS:
        name = fn.__name__
        t0 = time.time()
        try:
            detail = fn()
            RESULTS.append({"test": name, "status": "PASS", "seconds": round(time.time() - t0, 3),
                           "detail": detail})
            passed += 1
            print(f"PASS  {name}")
        except Exception as e:                                       # noqa: BLE001
            RESULTS.append({"test": name, "status": "FAIL", "seconds": round(time.time() - t0, 3),
                           "error": str(e), "traceback": traceback.format_exc()})
            failed += 1
            print(f"FAIL  {name}: {e}")

    summary = {
        "schema": "p36_arm_a03_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "arm_id": "A03_cal_shallow_tier_intercept",
        "n_tests": len(TESTS), "passed": passed, "failed": failed,
        "unseal_flag_present": rc.UNSEAL_ENV_FLAG in os.environ,
        "results": RESULTS,
    }
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "A03_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (ARM_DIR / "A03_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\n{passed}/{len(TESTS)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
