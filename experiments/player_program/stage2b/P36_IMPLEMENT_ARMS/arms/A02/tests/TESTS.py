#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for arm_a02.ArmA02 (A02_cal_blend_
contrast).

BLINDED (P36 standing rules): every frame here is synthetic (synthetic_fixture_a02.py); no real
fold, no real MAE, no comparative historical performance anywhere. This suite never sets
P38_UNSEALED and asserts it is absent.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A02/tests/TESTS.py
Writes: ../TEST_RECEIPT.json (machine-readable results), scoped to this arm's own directory.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ARM_DIR = HERE.parent
RUNNER = ARM_DIR.parents[1] / "runner"
for p in (str(RUNNER), str(HERE), str(ARM_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a02 as A                                                    # noqa: E402
import synthetic_fixture_a02 as fx                                     # noqa: E402

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
def t01_p35_spec_hash_pin():
    """The P35 SPEC.json byte pin this module was implemented against, re-measured."""
    import hashlib
    spec_path = (ARM_DIR.parents[2] / "P35_FREEZE_TASK_CARDS" / "SPEC.json")
    got = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    check(got == A.P35_SPEC_SHA256,
          f"P35 SPEC.json sha256 drifted: {got} != {A.P35_SPEC_SHA256}")
    return {"p35_spec_sha256": got}


def t02_contrast_formula_determinism_and_antisymmetry():
    df = fx.build_universe()
    c1 = A.compute_contrast(df)
    c2 = A.compute_contrast(df)
    check(np.array_equal(c1, c2), "contrast computation must be bitwise deterministic")

    # antisymmetric: for each game, the two rows' contrasts must sum to exactly 0
    tmp = df.copy()
    tmp["_c"] = c1
    sums = tmp.groupby("game_id")["_c"].sum().to_numpy()
    check(np.allclose(sums, 0.0, atol=1e-12), "own-opp contrast must be antisymmetric per game")

    # reproduces own_est - opp_est directly (brute-force, independent recomputation)
    brute = (df["own_est"] - df["opp_est"]).to_numpy(float)
    max_dev = float(np.max(np.abs(brute - c1)))
    check(max_dev <= 1e-12, f"contrast formula max abs deviation {max_dev} exceeds 1e-12 "
                            f"(P25 PREREGISTERED_CONTRASTS.json admissibility condition)")

    A.validate_own_opp_pairing(df)   # upstream own_est/opp_est pairing invariant, fixture-level
    return {"n_rows": len(df), "max_abs_deviation_vs_brute_force": max_dev}


def t03_missing_columns_and_bad_pairing_rejected():
    df = fx.build_universe(n_games_per_season=6)
    missing = df.drop(columns=["opp_est"])
    expect_raises(KeyError, lambda: A.compute_contrast(missing),
                  "compute_contrast must fail closed when opp_est is absent")

    orphan = df.drop(df.index[0]).reset_index(drop=True)   # break the two-rows-per-game invariant
    expect_raises(ValueError, lambda: A.validate_own_opp_pairing(orphan),
                  "validate_own_opp_pairing must fail closed when a game_id lacks two rows")

    mismatched = df.copy()
    mismatched.loc[mismatched.index[0], "opp_est"] += 5.0   # break the pairing without breaking shape
    expect_raises(ValueError, lambda: A.validate_own_opp_pairing(mismatched),
                  "validate_own_opp_pairing must fail closed when opp_est disagrees with the "
                  "other row's own_est")


def t04_build_design_bundle_shape_and_intercept_invariant():
    df = fx.build_universe()
    arm = A.ArmA02(["f1"], len(df))
    fold = {"fold_id": "f1", "train_idx": np.arange(len(df)), "test_idx": np.empty(0, int)}
    bundle = arm.build_design(fold, df)
    rec = ri.validate_design_bundle(bundle, df, arm.uses_global_intercept(), "f1")
    check(rec["valid"], f"design bundle must validate: {rec}")
    check(bundle["treatment_cols"] == [A.TREATMENT_COL], "treatment column pinned")
    check(bundle["nuisance_cols"] == [], "no nuisance terms per the card")
    check(bundle["k0_matched_design"] == {"treatment_cols": [], "nuisance_cols": [],
                                          "comparison": "term_removal"},
          "K0_MATCHED design must be the frozen zero-parameter null")
    check(bundle["indicator_cols"] == [], "contrast is continuous, not a 0/1 indicator")
    return {"columns": list(bundle["columns"])}


def t05_null_nested_in_arm():
    """Arm-vs-null design nesting the card declares: K0's design is the EMPTY subset of the
    arm's design (term_removal comparison), never a disjoint or superset design."""
    df = fx.build_universe(n_games_per_season=6)
    arm = A.ArmA02(["f1"], len(df))
    fold = {"fold_id": "f1", "train_idx": np.arange(len(df)), "test_idx": np.empty(0, int)}
    bundle = arm.build_design(fold, df)
    arm_cols = set(bundle["treatment_cols"]) | set(bundle["nuisance_cols"])
    k0 = bundle["k0_matched_design"]
    null_cols = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(null_cols <= arm_cols, "K0's columns must nest inside the arm's columns")
    check(arm_cols - null_cols == {A.TREATMENT_COL},
          "the ONLY column the null excludes is the card's treatment term")
    check(k0["comparison"] == "term_removal", "card-pinned comparison type")


def t06_module_conformance():
    df = fx.build_universe(n_games_per_season=6)
    arm = A.ArmA02(["f1", "f2"], len(df))
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], f"arm module must conform to RUNNER_INTERFACE: {rec}")
    check(arm.declared_family() == "SUBSTANTIVE", "P35 p25_guard_invocation_pins")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "no RECALIBRATION arm survives")
    check(arm.uses_global_intercept() is False,
          "P35 intercept_structure: A02 is in without_any_global_intercept")
    check("A02" in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT, "frozen intercept table membership")
    check(arm.enumeration_element() == {}, "A02 is a single-element arm (no grid)")


def t07_p26_raw_r8_finding_filtered_by_extended_rule():
    """Demonstrates the P35 r8_scope_adjudication end to end: the RAW P26 validator flags
    calibration_only R8 (missing a role='slope' parameter) because A02's tested parameter has
    role='coefficient', not 'slope'; guard_harness.p26_check re-adjudicates that specific
    finding to the extended rule (>=1 tested parameter with null_value==0) and PASSES."""
    df = fx.build_universe(n_games_per_season=6)
    arm = A.ArmA02(["f1"], len(df))
    rec = arm.p26_k0_record()

    vk = gh._load("P26_validate_k0_matched")
    raw = vk.validate(rec)
    raw_kinds = {f["kind"] for f in raw["blocking"]}
    check("tested_parameter_missing" in raw_kinds,
          f"raw validator must flag the slope-role R8 rule for a non-slope calibration_only "
          f"arm; got {raw_kinds}")

    out = gh.p26_check(rec)
    check(out["valid"], f"adjudicated P26 check must pass for A02: {out['blocking_after_adjudication']}")
    check(out["r8_filtered_findings"], "the slope finding must be recorded as filtered, not erased")
    return {"raw_blocking_kinds": sorted(raw_kinds),
           "n_r8_filtered": len(out["r8_filtered_findings"])}


def t08_prereg_digest_matches_frozen_p25_measurement():
    """Cross-checks this module's own canonical-digest reimplementation against the live P25
    module's canonical_digest on the SAME preregistration bytes, and against the digest P25's
    own TESTS.py measured into MEASUREMENTS.json (30e32e4f...)."""
    EXPECTED = "30e32e4f41bb8cca28e238babc2388772ebf28d2fd14d5bcfdbfcf9ef6a2e8a8"
    got = A.preregistered_contrast_digest()
    check(got == EXPECTED, f"prereg digest drifted from the P25-measured value: {got} != {EXPECTED}")

    odg = gh._load("P25_offset_dependency_guard")
    pre = A.load_preregistered_contrasts()
    live = odg.canonical_digest(pre)
    check(got == live, "this module's canonical digest must match the live P25 implementation")
    return {"digest": got}


def t09_p22_strict_lagging_derived_no_join():
    """A02's sole design column is declared DERIVED_NO_JOIN. Confirms it PASSES the P22
    postgame-surrogate battery on synthetic data with a synthetic prohibited basis, and that a
    dishonest SAME_GAME relabelling of the SAME column BLOCKS (proving the guard is actually
    discriminating, not vacuously passing everything)."""
    df = fx.build_universe(n_games_per_season=10)
    arm = A.ArmA02(["f1"], len(df))
    fold = {"fold_id": "f1", "train_idx": np.arange(len(df)), "test_idx": np.empty(0, int)}
    bundle = arm.build_design(fold, df)
    W = df.copy()
    for name, v in bundle["columns"].items():
        W[name] = np.asarray(v, float)
    basis = fx.build_prohibited_basis(df)

    rec = gh.p22_check(W, [A.TREATMENT_COL], prohibited_basis=basis,
                       lag_specs=arm.lag_specs(), lag_sources=arm.lag_sources())
    check(not rec.get("blocking"), f"P22 must pass the honestly-declared DERIVED_NO_JOIN column: {rec}")

    bad_specs = {A.TREATMENT_COL: dict(arm.lag_specs()[A.TREATMENT_COL], kind="SAME_GAME")}
    expect_raises(gh.GuardHarnessFailure,
                  lambda: gh.p22_check(W, [A.TREATMENT_COL], prohibited_basis=basis,
                                       lag_specs=bad_specs, lag_sources={}),
                  "SAME_GAME must block unconditionally per P22's own contract")


def t10_p27_active_set_rule_decidable():
    """The card's registered fold-local fallback, expressed as a P27 ActiveSetRule, is decidable
    from training-fold support alone: drops the treatment on a degenerate (zero-variance)
    training fold, keeps it on a normal one. No target/result is consulted (SupportSummary has
    none)."""
    df = fx.build_universe(n_games_per_season=6)
    arm = A.ArmA02(["f1"], len(df))
    rule_kwargs, prereg_kwargs = arm.p27_rule()
    feg = gh._load("P27_fold_estimability_guard")
    rule = feg.ActiveSetRule(**rule_kwargs)
    prereg = feg.Preregistration(**prereg_kwargs)
    audit = feg.validate_preregistration(rule, prereg)
    check(audit["valid"], f"preregistration must validate (digest match, not registered post-hoc): {audit}")

    degenerate = feg.SupportSummary(
        fold_id="f1", n_rows=40, n_clusters=20,
        term_std={A.TREATMENT_COL: 0.0},
        term_unique_levels={A.TREATMENT_COL: 1},
        term_cluster_support={A.TREATMENT_COL: 20},
        term_nonzero_rows={A.TREATMENT_COL: 0})
    decision_degenerate = rule.decide(degenerate, [A.TREATMENT_COL])
    check(A.TREATMENT_COL in decision_degenerate["dropped"],
          "zero-variance training contrast must be DROPPED by the registered rule")

    healthy = feg.SupportSummary(
        fold_id="f2", n_rows=40, n_clusters=20,
        term_std={A.TREATMENT_COL: 3.2},
        term_unique_levels={A.TREATMENT_COL: 40},
        term_cluster_support={A.TREATMENT_COL: 20},
        term_nonzero_rows={A.TREATMENT_COL: 40})
    decision_healthy = rule.decide(healthy, [A.TREATMENT_COL])
    check(A.TREATMENT_COL in decision_healthy["kept"],
          "non-degenerate training contrast must be KEPT by the registered rule")
    return {"degenerate_dropped": decision_degenerate["dropped"],
           "healthy_kept": decision_healthy["kept"]}


def t11_degenerate_universe_fails_closed_at_bundle_validation():
    """A universe where the contrast is identically zero everywhere is caught by the FULL-
    universe silent-intercept check at design-bundle validation (a constant non-intercept design
    column), before any fit and before the fold-local P27 rule is even reached -- fail-closed,
    as the card requires."""
    df = fx.build_degenerate_fold_universe()
    arm = A.ArmA02(["f1"], len(df))
    fold = {"fold_id": "f1", "train_idx": np.arange(len(df)), "test_idx": np.empty(0, int)}
    bundle = arm.build_design(fold, df)
    check(np.allclose(bundle["columns"][A.TREATMENT_COL], 0.0),
          "fixture sanity: contrast must be exactly 0 on every row")
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_design_bundle(bundle, df, False, "f1"),
                  "a fully degenerate contrast column must fail closed as a silent intercept")


def t12_end_to_end_synthetic_run_deterministic():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    basis = fx.build_prohibited_basis(df)
    arm = A.ArmA02([f["fold_id"] for f in folds], len(df))
    out_path = HERE / "artifacts" / "A02_receipt.json"
    out_path.parent.mkdir(exist_ok=True)

    t0 = time.time()
    rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                     out_path=out_path, run_git=False)
    dt = time.time() - t0

    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(out_path.exists(), "receipt file written")
    check(rec["results"]["evaluable_folds"] == [f["fold_id"] for f in folds],
          "both synthetic folds evaluable")
    check(rec["guard_records"]["p26"]["valid"], "P26 must pass for A02's own record")
    check(rec["guard_records"]["module_conformance"]["conformant"], "module conformance")
    for e in rec["folds"]:
        if e["status"] != "EVALUABLE":
            continue
        beta = dict(zip(e["point_fits"]["arm"]["column_names"], e["point_fits"]["arm"]["beta"]))
        check(abs(beta[A.TREATMENT_COL] - fx.TRUE_GAMMA) < 0.03,
              f"synthetic gamma recovered loosely: {beta[A.TREATMENT_COL]} vs {fx.TRUE_GAMMA}")
    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict")

    # determinism: an identical second run must reproduce results and fold records exactly
    rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={}, run_git=False)
    import receipts
    d1 = receipts.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = receipts.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: refuses a real fold id, flag absent
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, df, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED")

    globals()["_LAST_RECEIPT"] = rec
    return {"seconds": round(dt, 2),
           "pooled_delta_mae": rec["results"]["pooled"]["delta_mae"],
           "results_digest": d1}


def t13_kill_condition_hooks_decidable():
    """arm_a02.evaluate_kill_conditions must be computable purely from a receipt's own JSON-safe
    fields (no re-fit, no external data), and must produce a definite verdict on the card's
    kill conditions for the synthetic run in t12."""
    rec = globals().get("_LAST_RECEIPT")
    check(rec is not None, "t12 must run first and populate a receipt")
    kc = A.evaluate_kill_conditions(rec)
    check(kc["schema"] == "p36_a02_kill_conditions/1", "kill-condition record schema")
    check(kc["n_evaluable_folds"] == len(rec["results"]["evaluable_folds"]),
          "kill-condition evaluation must cover every evaluable fold")
    check(kc["zero_not_rejected_in_every_evaluable_fold"] in (True, False),
          "the beta=0 non-rejection question must resolve to a definite boolean, not None")
    check(kc["no_out_of_fold_improvement"] in (True, False),
          "the OOF-improvement question must resolve to a definite boolean")
    check(isinstance(kc["kill_sign_flip"], bool), "sign-flip question must resolve to a boolean")
    check(isinstance(kc["any_kill_fired"], bool), "overall kill verdict must be a definite boolean")
    # round-trip through JSON to prove it is receipt-safe (no numpy scalars, no NaN leaks silently)
    blob = json.dumps(kc, default=str)
    check(json.loads(blob)["arm_id"] == A.ARM_ID, "kill-condition record must be JSON round-trippable")
    return {k: v for k, v in kc.items() if k not in ("per_fold", "s7_near_collinearity_per_fold")}


def t14_no_p38_unsealed_flag_in_environment():
    check(rc.UNSEAL_ENV_FLAG not in os.environ,
          "this suite must never run with the real unseal flag set")


# ------------------------------------------------------------------------------------- driver
def main():
    tests = [
        t01_p35_spec_hash_pin, t02_contrast_formula_determinism_and_antisymmetry,
        t03_missing_columns_and_bad_pairing_rejected, t04_build_design_bundle_shape_and_intercept_invariant,
        t05_null_nested_in_arm, t06_module_conformance,
        t07_p26_raw_r8_finding_filtered_by_extended_rule,
        t08_prereg_digest_matches_frozen_p25_measurement,
        t09_p22_strict_lagging_derived_no_join, t10_p27_active_set_rule_decidable,
        t11_degenerate_universe_fails_closed_at_bundle_validation,
        t12_end_to_end_synthetic_run_deterministic, t13_kill_condition_hooks_decidable,
        t14_no_p38_unsealed_flag_in_environment,
    ]
    passed, failed = 0, 0
    for fn in tests:
        name = fn.__name__
        t0 = time.time()
        try:
            measured = fn() or {}
            RESULTS.append({"test": name, "status": "PASS", "seconds": round(time.time() - t0, 4),
                            "measured": measured})
            passed += 1
            print(f"PASS  {name}")
        except Exception as e:                                     # noqa: BLE001
            RESULTS.append({"test": name, "status": "FAIL", "seconds": round(time.time() - t0, 4),
                            "error": repr(e), "traceback": traceback.format_exc()})
            failed += 1
            print(f"FAIL  {name}: {e}")

    out = {
        "schema": "p36_a02_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "arm_id": A.ARM_ID, "p35_spec_sha256": A.P35_SPEC_SHA256,
        "n_tests": len(tests), "n_passed": passed, "n_failed": failed,
        "results": RESULTS,
    }
    (ARM_DIR / "TEST_RECEIPT.json").write_text(json.dumps(out, indent=2, default=str),
                                                encoding="utf-8")
    print(f"\n{passed}/{len(tests)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
