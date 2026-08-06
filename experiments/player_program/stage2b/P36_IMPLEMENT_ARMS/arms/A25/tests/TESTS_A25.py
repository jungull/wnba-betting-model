#!/usr/bin/env python3
"""TESTS_A25.py -- unit, synthetic, identity and schema tests for A25_home_offense_contrast.

BLINDED: every frame here is synthetic (synthetic_fixture_a25.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts P38_UNSEALED is ABSENT from the
process environment and never sets it (the unseal branch is exercised only through an injected
mapping, exactly like the shared runner's own suite).

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A25/ only. Imports the
frozen shared runner (runner/*.py) as a contract; never writes to runner/ or to any other arm's
directory.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A25/tests/TESTS_A25.py
Writes: ../TEST_RECEIPT_A25.json (machine-readable results).
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
RUNNER = ARM_DIR.parents[1] / "runner"          # .../P36_IMPLEMENT_ARMS/runner (read-only import)
for p in (str(RUNNER), str(ARM_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                       # noqa: E402
import guard_harness as gh                                            # noqa: E402
import receipts                                                       # noqa: E402
import runner as rn                                                   # noqa: E402
import runner_constants as rc                                         # noqa: E402
import runner_interface as ri                                         # noqa: E402

import arm_a25 as a25mod                                              # noqa: E402
import synthetic_fixture_a25 as fx                                    # noqa: E402

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


def _fresh_arm():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = a25mod.A25Arm(fids)
    return arm, df, folds


# ------------------------------------------------------------------------------- tests
def t01_module_conformance():
    arm, df, folds = _fresh_arm()
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], "A25 module must conform to RUNNER_INTERFACE.md")
    check(rec["arm_id"] == a25mod.ARM_ID, "conformance record must carry the frozen arm_id")
    check(rec["enumeration_element"] == {}, "A25 has no enumeration grid (single element)")

    class WrongFamily(a25mod.A25Arm):
        def declared_family(self):
            return "RECALIBRATION"
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(WrongFamily([f["fold_id"] for f in folds])),
                  "non-SUBSTANTIVE declared_family must be refused (P35 p25_guard_invocation_pins"
                  " pins SUBSTANTIVE for every fitted arm, A25 included)")

    class WrongIntercept(a25mod.A25Arm):
        def uses_global_intercept(self):
            return True
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(WrongIntercept([f["fold_id"] for f in folds])),
                  "A25 is in P35 ARMS_WITHOUT_GLOBAL_INTERCEPT; claiming a free intercept must "
                  "be refused by the frozen intercept table")
    check(a25mod.ARM_ID.split("_")[0] in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT,
          "A25 must appear in the frozen no-intercept table")
    return {"conformant": True}


def t02_feature_determinism_and_bundle():
    arm, df, folds = _fresh_arm()
    b1 = arm.build_design(folds[0], df)
    b2 = arm.build_design(folds[0], df)
    v1 = np.asarray(b1["columns"][a25mod.TREATMENT_COL])
    v2 = np.asarray(b2["columns"][a25mod.TREATMENT_COL])
    check(v1.tobytes() == v2.tobytes(), "build_design must be bitwise deterministic (repeat call)")
    v3 = np.asarray(arm.build_design(folds[1], df)["columns"][a25mod.TREATMENT_COL])
    check(v1.tobytes() == v3.tobytes(),
          "no training-fold-computed constant exists for A25: the treatment column must be "
          "identical across folds too (pure pass-through of a pre-tipoff schedule fact)")
    check(np.array_equal(v1, df["is_home_offense"].to_numpy(float)),
          "the materialised treatment column must equal the raw schedule flag exactly")

    bval = ri.validate_design_bundle(b1, df, arm.uses_global_intercept(), folds[0]["fold_id"])
    check(bval["valid"], "design bundle must validate against the frozen intercept invariant")
    check(bval["comparison"] == "term_removal", "A25's K0 comparison is term_removal")
    check(b1["k0_matched_design"]["treatment_cols"] == []
          and b1["k0_matched_design"]["nuisance_cols"] == [],
          "A25's null has zero fitted parameters -- it IS the frozen incumbent exactly")

    bad = df.copy()
    bad["is_home_offense"] = 2                          # not a strict 0/1 flag
    expect_raises(ValueError, lambda: arm.build_design(folds[0], bad),
                  "a non-0/1 home/away flag must be refused, not silently cast")

    missing = df.drop(columns=["is_home_offense"])
    expect_raises(KeyError, lambda: arm.build_design(folds[0], missing),
                  "a universe frame missing is_home_offense must be refused, not silently "
                  "defaulted")
    return {"n_rows": len(df), "treatment_mean": float(v1.mean())}


def t03_p26_k0_contract():
    arm, df, folds = _fresh_arm()
    rec = arm.p26_k0_record()
    check(rec["arm_kind"] == "substantive_feature",
          "A25 is substantive_feature per the frozen card, NOT calibration_only")
    out = gh.p26_check(rec)
    check(out["valid"], f"A25's k0_matched record must validate: {out['blocking_after_adjudication']}")
    check(out["r8_filtered_findings"] == [],
          "the R8 slope rule is scoped to calibration_only arms (P35 r8_scope_adjudication); a "
          "substantive_feature record must pass the RAW validator directly, with no R8 "
          "adjudication applied at all")
    check(out["r8_adjudication_basis"] is None,
          "no R8 adjudication basis should be recorded for a substantive_feature arm")

    # negative control: a null that let the treatment survive must be blocked
    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = [a25mod.TREATMENT_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null retaining the treatment term must be blocked")
    return {"r8_filtered_kinds": []}


def t04_p22_schedule_lag_declaration():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    b = arm.build_design(folds[0], df)
    frame = df.copy()
    frame[a25mod.TREATMENT_COL] = b["columns"][a25mod.TREATMENT_COL]

    ok = gh.p22_check(frame, [a25mod.TREATMENT_COL], prohibited_basis=basis,
                      lag_specs=arm.lag_specs(), lag_sources=arm.lag_sources())
    check(not ok["blocking"], "the frozen SCHEDULE lag declaration must pass P22")

    # negative: an undeclared column is a failure, never a pass (absence-of-declaration rule)
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, [a25mod.TREATMENT_COL], prohibited_basis=basis, lag_specs={}),
        "missing LagSpec for the treatment column must block")

    # negative: mislabelling the SAME pre-tipoff column SAME_GAME must still block unconditionally
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, [a25mod.TREATMENT_COL], prohibited_basis=basis,
        lag_specs={a25mod.TREATMENT_COL: {"column": a25mod.TREATMENT_COL, "kind": "SAME_GAME",
                                          "entity_keys": ("game_id",)}}),
        "SAME_GAME must block unconditionally regardless of the column's true provenance")
    return {"p22_passed": True, "negative_paths": 2}


def t05_p25_offset_family():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    fold = folds[0]
    b = arm.build_design(fold, df)
    frame = df.copy()
    frame[a25mod.TREATMENT_COL] = b["columns"][a25mod.TREATMENT_COL]
    tr = frame.iloc[fold["train_idx"]].reset_index(drop=True)
    rec = gh.p25_check(tr, candidate_features=[a25mod.TREATMENT_COL], nuisance_features=[],
                       preregistered_contrasts=arm.preregistered_contrasts(),
                       prereg_digest_expected=arm.prereg_digest_expected())
    check(rec["passed"], "A25's home-offense indicator must pass P25 under SUBSTANTIVE: it is "
                         "not a function of the offset or the incumbent projection")
    check(arm.declared_family() == rc.DECLARED_FAMILY_ALL_FITTED_ARMS
          and arm.recalibration_declaration() == rc.RECALIBRATION_DECLARATION,
          "guard_invocation pins from the frozen card")
    return {"p25_passed": True}


def t06_arm_null_nesting():
    """The card's comparison is term_removal with a zero-parameter null: arm design minus the
    treatment term must equal EXACTLY the null design (nesting), and the null must literally
    reduce to the bare offset (no columns at all) -- the incumbent exactly."""
    arm, df, folds = _fresh_arm()
    b = arm.build_design(folds[0], df)
    arm_cols = set(b["treatment_cols"]) | set(b["nuisance_cols"])
    k0 = b["k0_matched_design"]
    null_cols = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(arm_cols - null_cols == {a25mod.TREATMENT_COL},
          "removing exactly the treatment term from the arm design must yield the null design")
    check(null_cols == set(), "A25's K0_MATCHED null must carry NO design columns at all -- "
                              "eta_null = log_exposure exactly, the frozen incumbent")
    check(k0["comparison"] == "term_removal", "A25's frozen comparison type is term_removal")
    return {"arm_cols": sorted(arm_cols), "null_cols": sorted(null_cols)}


def t07_enumeration_element_exact():
    arm, df, folds = _fresh_arm()
    check(arm.enumeration_element() == {}, "A25 carries no enumeration grid (single element)")
    check(arm.element_id() == f"{a25mod.ARM_ID}__single", "element_id must be the frozen literal")
    # repeated calls and calls across folds must never drift (no training-time element selection)
    for f in folds:
        check(arm.enumeration_element() == {}, f"enumeration_element must not vary by fold {f}")
        check(arm.element_id() == f"{a25mod.ARM_ID}__single", "element_id must not vary by fold")
    return {"enumeration_element": {}, "element_id": arm.element_id()}


def t08_kill_conditions_decidable():
    ev = a25mod.evaluate_kill_conditions

    all_cover = {"f1": {"lo": -0.02, "hi": 0.03, "beta": 0.01},
                "f2": {"lo": -0.05, "hi": 0.01, "beta": 0.01}}
    out1 = ev(all_cover)
    check(out1["killed"] and out1["all_cover_zero"],
          "beta interval covering 0 in every evaluable fold must be decided KILLED (GENUINE "
          "NULL -- the preregistered interpretation is that the offset already prices home "
          "tempo)")

    survives = {"f1": {"lo": 0.02, "hi": 0.09, "beta": 0.05},
               "f2": {"lo": 0.01, "hi": 0.07, "beta": 0.04}}
    out2 = ev(survives)
    check(not out2["killed"], "beta excluding 0 in at least one evaluable fold must NOT be killed")

    # unlike A05/A11, A25's frozen kill clause names no sign-instability test: a sign flip with
    # every interval EXCLUDING zero is therefore not-killed under the card's own words
    sign_flip_but_excludes_zero = {"f1": {"lo": 0.02, "hi": 0.09, "beta": 0.05},
                                   "f2": {"lo": -0.09, "hi": -0.02, "beta": -0.05}}
    out3 = ev(sign_flip_but_excludes_zero)
    check(not out3["killed"],
          "A25's frozen kill clause is interval-covers-zero ONLY; a sign flip across folds with "
          "every interval excluding 0 must not be manufactured into an extra kill condition the "
          "card never states")

    empty = ev({})
    check(not empty["killed"] and empty["n_evaluable_folds"] == 0,
          "zero evaluable folds must decide NOT killed with an honest empty basis, never a "
          "manufactured positive (standing rule 7)")
    return {"all_cover_killed": out1["killed"], "excludes_zero_survives": not out2["killed"],
            "sign_flip_not_an_extra_kill": not out3["killed"]}


def t09_end_to_end_synthetic():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    out_path = HERE / "artifacts" / "A25_receipt.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                     p27_fold_policy="EXPANDING_PRIOR_SEASONS",
                     out_path=out_path, run_git=False)
    dt = time.time() - t0
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(out_path.exists(), "receipt file written")
    check(rec["results"]["evaluable_folds"] == [f["fold_id"] for f in folds],
          "the card guarantees all folds evaluable (positive control); both synthetic folds "
          "must be evaluable for A25 on the synthetic fixture, with NO structural deactivation")
    check(rec["results"]["pooled"] is not None
          and rec["results"]["pooled"]["n_draws"] == rc.B_TEST_BOOTSTRAP,
          "pooled inference at the frozen B")
    for e in rec["folds"]:
        if e["status"] != "EVALUABLE":
            continue
        check(e["train_refit"]["n_draws"] == rc.B_TRAIN_REFIT, "frozen train-refit B")
        check(e["k0_flat"]["role"] == "diagnostic_only", "K0_FLAT diagnostic label")
        arm_names = e["point_fits"]["arm"]["column_names"]
        check(list(arm_names) == [a25mod.TREATMENT_COL],
              "the arm's fitted design must be exactly the single treatment column")
        null_names = e["point_fits"]["null"]["column_names"]
        check(list(null_names) == [], "the null's fitted design must be empty (the incumbent)")

    # positive-control check, exercised not merely asserted: every evaluable fold's TEST
    # partition is exactly 50/50 home/away by construction (games never split)
    for f in folds:
        te = f["test_idx"]
        home_test = df["is_home_offense"].to_numpy()[te]
        check(home_test.sum() == len(te) - home_test.sum(),
              f"fold {f['fold_id']} TEST partition must be exactly 50/50 home/away by "
              "construction (P35/P33 fold_local_fallback: not_applicable)")

    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict")
    check(rec["seeds"]["master_seed"] == rc.MASTER_SEED, "seed manifest master pin")

    # determinism: an identical second run must reproduce results and fold records exactly
    rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                      p27_fold_policy="EXPANDING_PRIOR_SEASONS", run_git=False)
    d1 = receipts.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = receipts.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: the runner REFUSES a frame carrying a real fold id, flag absent
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, df, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED, for A25 too")
    return {"seconds": round(dt, 2), "results_digest": d1,
            "note": "synthetic-only numbers; no real fold was touched"}


def t10_frozen_card_pins():
    """The card bytes this module claims to implement are unchanged on disk, and the module's
    own declarations match the frozen intercept table and guard_invocation pins."""
    p35 = gh.STAGE2B / "P35_FREEZE_TASK_CARDS" / "SPEC.json"
    check(receipts.sha256_file(p35) == a25mod.P35_SPEC_SHA256 == rc.P35_SPEC_SHA256,
          "P35 SPEC bytes unchanged on disk and match this module's own pin")
    check(a25mod.ARM_ID == "A25_home_offense_contrast", "arm_id literal pin")
    check(a25mod.TREATMENT_COL not in ("intercept",), "treatment column must never be the "
                                                       "structural intercept name")
    return {"p35_verified": True}


TESTS = [
    ("T01_module_conformance", t01_module_conformance),
    ("T02_feature_determinism_and_bundle", t02_feature_determinism_and_bundle),
    ("T03_p26_k0_contract", t03_p26_k0_contract),
    ("T04_p22_schedule_lag_declaration", t04_p22_schedule_lag_declaration),
    ("T05_p25_offset_family", t05_p25_offset_family),
    ("T06_arm_null_nesting", t06_arm_null_nesting),
    ("T07_enumeration_element_exact", t07_enumeration_element_exact),
    ("T08_kill_conditions_decidable", t08_kill_conditions_decidable),
    ("T09_end_to_end_synthetic", t09_end_to_end_synthetic),
    ("T10_frozen_card_pins", t10_frozen_card_pins),
]


def main() -> int:
    if rc.UNSEAL_ENV_FLAG in os.environ:
        print(f"FATAL: {rc.UNSEAL_ENV_FLAG} exists in the environment; "
              "the blinded test suite refuses to run.")
        return 2
    n_pass = 0
    for name, fn in TESTS:
        t0 = time.time()
        try:
            measured = fn()
            RESULTS.append({"test": name, "passed": True,
                            "seconds": round(time.time() - t0, 2), "measured": measured})
            n_pass += 1
            print(f"PASS  {name}")
        except Exception as e:                                       # noqa: BLE001
            RESULTS.append({"test": name, "passed": False,
                            "seconds": round(time.time() - t0, 2),
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(limit=8)})
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    receipt = {
        "schema": "a25_arm_test_receipt/1",
        "arm_id": a25mod.ARM_ID,
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = ARM_DIR / "TEST_RECEIPT_A25.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
