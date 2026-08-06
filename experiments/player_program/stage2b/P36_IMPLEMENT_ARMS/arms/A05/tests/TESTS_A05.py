#!/usr/bin/env python3
"""TESTS_A05.py -- unit, synthetic, identity and schema tests for A05_cal_playoff_intercept.

BLINDED: every frame here is synthetic (synthetic_fixture_a05.py); no real fold, no real MAE,
no comparative historical performance anywhere. The suite asserts P38_UNSEALED is ABSENT from
the process environment and never sets it (the unseal branch is exercised only through an
injected mapping, exactly like the shared runner's own suite).

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A05/ only. Imports the
frozen shared runner (runner/*.py) as a contract; never writes to runner/ or to any other arm's
directory.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A05/tests/TESTS_A05.py
Writes: ../TEST_RECEIPT_A05.json (machine-readable results).
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

import a05_cal_playoff_intercept as a05mod                            # noqa: E402
import synthetic_fixture_a05 as fx                                    # noqa: E402

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
    arm = a05mod.A05CalPlayoffIntercept(fids)
    return arm, df, folds


# ------------------------------------------------------------------------------- tests
def t01_module_conformance():
    arm, df, folds = _fresh_arm()
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], "A05 module must conform to RUNNER_INTERFACE.md")
    check(rec["arm_id"] == a05mod.ARM_ID, "conformance record must carry the frozen arm_id")
    check(rec["enumeration_element"] == {}, "A05 has no enumeration grid (single element)")

    class WrongFamily(a05mod.A05CalPlayoffIntercept):
        def declared_family(self):
            return "RECALIBRATION"
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(WrongFamily([f["fold_id"] for f in folds])),
                  "non-SUBSTANTIVE declared_family must be refused (P35 p25_guard_invocation_pins"
                  " pins SUBSTANTIVE for every fitted arm, A05 included)")

    class WrongIntercept(a05mod.A05CalPlayoffIntercept):
        def uses_global_intercept(self):
            return True
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(WrongIntercept([f["fold_id"] for f in folds])),
                  "A05 is in P35 ARMS_WITHOUT_GLOBAL_INTERCEPT; claiming a free intercept must "
                  "be refused by the frozen intercept table")
    check(a05mod.ARM_ID.split("_")[0] in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT,
          "A05 must appear in the frozen no-intercept table")
    return {"conformant": True}


def t02_feature_determinism_and_bundle():
    arm, df, folds = _fresh_arm()
    b1 = arm.build_design(folds[0], df)
    b2 = arm.build_design(folds[0], df)
    v1 = np.asarray(b1["columns"][a05mod.TREATMENT_COL])
    v2 = np.asarray(b2["columns"][a05mod.TREATMENT_COL])
    check(v1.tobytes() == v2.tobytes(), "build_design must be bitwise deterministic (repeat call)")
    v3 = np.asarray(arm.build_design(folds[1], df)["columns"][a05mod.TREATMENT_COL])
    check(v1.tobytes() == v3.tobytes(),
          "no training-fold-computed constant exists for A05: the treatment column must be "
          "identical across folds too (pure pass-through of a pre-tipoff schedule fact)")
    check(np.array_equal(v1, df["is_playoff_game"].to_numpy(float)),
          "the materialised treatment column must equal the raw schedule flag exactly")

    bval = ri.validate_design_bundle(b1, df, arm.uses_global_intercept(), folds[0]["fold_id"])
    check(bval["valid"], "design bundle must validate against the frozen intercept invariant")
    check(bval["comparison"] == "term_removal", "A05's K0 comparison is term_removal")
    check(b1["k0_matched_design"]["treatment_cols"] == []
          and b1["k0_matched_design"]["nuisance_cols"] == [],
          "A05's null has zero fitted parameters -- it IS the frozen incumbent exactly")

    bad = df.copy()
    bad["is_playoff_game"] = 2                          # not a strict 0/1 flag
    expect_raises(ValueError, lambda: arm.build_design(folds[0], bad),
                  "a non-0/1 playoff flag must be refused, not silently cast")
    return {"n_rows": len(df), "treatment_mean": float(v1.mean())}


def t03_p26_k0_contract():
    arm, df, folds = _fresh_arm()
    rec = arm.p26_k0_record()
    out = gh.p26_check(rec)
    check(out["valid"], f"A05's k0_matched record must validate: {out['blocking_after_adjudication']}")
    check(len(out["r8_filtered_findings"]) >= 1,
          "calibration_only must pass ONLY via the P35 R8 adjudication (slope-role + empty "
          "lower-order findings filtered), never because the raw validator found nothing")
    kinds = {f["kind"] for f in out["r8_filtered_findings"]}
    check("tested_parameter_missing" in kinds,
          "A05 declares an intercept-role pi, not a slope -- the raw validator's slope-missing "
          "finding must be the one filtered")
    check(out["r8_adjudication_basis"] is not None, "adjudication basis must be recorded")

    # negative control: a null that let the treatment survive must be blocked (never filtered)
    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = [a05mod.TREATMENT_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null retaining the treatment term must be blocked, not adjudicated away")
    return {"r8_filtered_kinds": sorted(kinds)}


def t04_p22_schedule_lag_declaration():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    b = arm.build_design(folds[0], df)
    frame = df.copy()
    frame[a05mod.TREATMENT_COL] = b["columns"][a05mod.TREATMENT_COL]

    ok = gh.p22_check(frame, [a05mod.TREATMENT_COL], prohibited_basis=basis,
                      lag_specs=arm.lag_specs(), lag_sources=arm.lag_sources())
    check(not ok["blocking"], "the frozen SCHEDULE lag declaration must pass P22")

    # negative: an undeclared column is a failure, never a pass (absence-of-declaration rule)
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, [a05mod.TREATMENT_COL], prohibited_basis=basis, lag_specs={}),
        "missing LagSpec for the treatment column must block")

    # negative: mislabelling the SAME pre-tipoff column SAME_GAME must still block unconditionally
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, [a05mod.TREATMENT_COL], prohibited_basis=basis,
        lag_specs={a05mod.TREATMENT_COL: {"column": a05mod.TREATMENT_COL, "kind": "SAME_GAME",
                                          "entity_keys": ("game_id",)}}),
        "SAME_GAME must block unconditionally regardless of the column's true provenance")
    return {"p22_passed": True, "negative_paths": 2}


def t05_p25_offset_family():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    fold = folds[0]
    b = arm.build_design(fold, df)
    frame = df.copy()
    frame[a05mod.TREATMENT_COL] = b["columns"][a05mod.TREATMENT_COL]
    tr = frame.iloc[fold["train_idx"]].reset_index(drop=True)
    rec = gh.p25_check(tr, candidate_features=[a05mod.TREATMENT_COL], nuisance_features=[],
                       preregistered_contrasts=arm.preregistered_contrasts(),
                       prereg_digest_expected=arm.prereg_digest_expected())
    check(rec["passed"], "A05's playoff indicator must pass P25 under SUBSTANTIVE: it is not a "
                         "function of the offset or the incumbent projection")
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
    check(arm_cols - null_cols == {a05mod.TREATMENT_COL},
          "removing exactly the treatment term from the arm design must yield the null design")
    check(null_cols == set(), "A05's K0_MATCHED null must carry NO design columns at all -- "
                              "eta_null = log_exposure exactly, the frozen incumbent")
    check(k0["comparison"] == "term_removal", "A05's frozen comparison type is term_removal")
    return {"arm_cols": sorted(arm_cols), "null_cols": sorted(null_cols)}


def t07_enumeration_element_exact():
    arm, df, folds = _fresh_arm()
    check(arm.enumeration_element() == {}, "A05 carries no enumeration grid (single element)")
    check(arm.element_id() == f"{a05mod.ARM_ID}__single", "element_id must be the frozen literal")
    # repeated calls and calls across folds must never drift (no training-time element selection)
    for f in folds:
        check(arm.enumeration_element() == {}, f"enumeration_element must not vary by fold {f}")
        check(arm.element_id() == f"{a05mod.ARM_ID}__single", "element_id must not vary by fold")
    return {"enumeration_element": {}, "element_id": arm.element_id()}


def t08_kill_conditions_decidable():
    ev = a05mod.evaluate_kill_conditions

    all_cover = {"f1": {"lo": -0.02, "hi": 0.03, "beta": 0.01},
                "f2": {"lo": -0.05, "hi": 0.01, "beta": 0.01},
                "f3": {"lo": -0.01, "hi": 0.04, "beta": 0.02},
                "f4": {"lo": -0.03, "hi": 0.02, "beta": 0.005}}
    out1 = ev(all_cover)
    check(out1["killed"] and out1["all_cover_zero"] and not out1["sign_unstable"],
          "pi interval covering 0 in every evaluable fold must be decided KILLED")

    survives_stable = {"f1": {"lo": 0.02, "hi": 0.09, "beta": 0.05},
                       "f2": {"lo": 0.01, "hi": 0.07, "beta": 0.04},
                       "f3": {"lo": 0.03, "hi": 0.10, "beta": 0.06},
                       "f4": {"lo": 0.005, "hi": 0.08, "beta": 0.045}}
    out2 = ev(survives_stable)
    check(not out2["killed"], "pi excluding 0 with a stable sign must NOT be killed")

    sign_flip = {"f1": {"lo": 0.02, "hi": 0.09, "beta": 0.05},
                "f2": {"lo": -0.09, "hi": -0.02, "beta": -0.05},
                "f3": {"lo": 0.01, "hi": 0.06, "beta": 0.03},
                "f4": {"lo": -0.06, "hi": -0.01, "beta": -0.03}}
    out3 = ev(sign_flip)
    check(out3["killed"] and out3["sign_unstable"] and not out3["all_cover_zero"],
          "sign instability across evaluable folds must be decided KILLED even when no single "
          "fold's interval covers 0")

    empty = ev({})
    check(not empty["killed"] and empty["n_evaluable_folds"] == 0,
          "zero evaluable folds must decide NOT killed with an honest empty basis, never a "
          "manufactured positive (standing rule 7)")
    return {"all_cover_killed": out1["killed"], "stable_survives": not out2["killed"],
            "sign_flip_killed": out3["killed"]}


def t09_end_to_end_synthetic():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    out_path = HERE / "artifacts" / "A05_receipt.json"
    t0 = time.time()
    # RUNNER_INTERFACE.md section 4 leaves SEASON_BLOCK vs EXPANDING_PRIOR_SEASONS open at the
    # shared-runner level. For A05 specifically it is NOT ambiguous: the P33-carried record
    # (binding, not amended by P35) names the fold "train_lt_2026" and states "five fitted, four
    # evaluable for pi" -- that is EXPANDING_PRIOR_SEASONS naming and cardinality exactly, so
    # this test names it explicitly rather than relying on the runner's SEASON_BLOCK default.
    rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                     p27_fold_policy="EXPANDING_PRIOR_SEASONS",
                     out_path=out_path, run_git=False)
    dt = time.time() - t0
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(out_path.exists(), "receipt file written")
    check(rec["results"]["evaluable_folds"] == [f["fold_id"] for f in folds],
          "both synthetic folds must be evaluable for A05 on the synthetic fixture")
    check(rec["results"]["pooled"] is not None
          and rec["results"]["pooled"]["n_draws"] == rc.B_TEST_BOOTSTRAP,
          "pooled inference at the frozen B")
    for e in rec["folds"]:
        if e["status"] != "EVALUABLE":
            continue
        check(e["train_refit"]["n_draws"] == rc.B_TRAIN_REFIT, "frozen train-refit B")
        check(e["k0_flat"]["role"] == "diagnostic_only", "K0_FLAT diagnostic label")
        arm_names = e["point_fits"]["arm"]["column_names"]
        check(list(arm_names) == [a05mod.TREATMENT_COL],
              "the arm's fitted design must be exactly the single treatment column")
        null_names = e["point_fits"]["null"]["column_names"]
        check(list(null_names) == [], "the null's fitted design must be empty (the incumbent)")

    # the card's own fold_local_fallback note, measured on the synthetic fixture: the LAST test
    # season has zero playoff rows by construction (see synthetic_fixture_a05.build_universe)
    last_fold = rec["folds"][-1]
    te = folds[-1]["test_idx"]
    n_playoff_test = int(df["is_playoff_game"].to_numpy()[te].sum())
    check(n_playoff_test == 0,
          "fixture must reproduce the card's fold_local_fallback trigger (test playoff rows==0) "
          "on at least one evaluable fold, so the note is exercised, not merely asserted")
    check(last_fold["status"] == "EVALUABLE",
          "P35: a non-discriminating fold remains evaluable, it is not excluded (no P27 hook)")

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
                  "runner must refuse real fold ids without P38_UNSEALED, for A05 too")
    return {"seconds": round(dt, 2), "n_playoff_test_last_fold": n_playoff_test,
            "results_digest": d1, "note": "synthetic-only numbers; no real fold was touched"}


def t10_frozen_card_pins():
    """The card bytes this module claims to implement are unchanged on disk, and the module's
    own declarations match the frozen intercept table and guard_invocation pins."""
    p35 = gh.STAGE2B / "P35_FREEZE_TASK_CARDS" / "SPEC.json"
    check(receipts.sha256_file(p35) == a05mod.P35_SPEC_SHA256 == rc.P35_SPEC_SHA256,
          "P35 SPEC bytes unchanged on disk and match this module's own pin")
    check(a05mod.ARM_ID == "A05_cal_playoff_intercept", "arm_id literal pin")
    check(a05mod.TREATMENT_COL not in ("intercept",), "treatment column must never be the "
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
        "schema": "a05_arm_test_receipt/1",
        "arm_id": a05mod.ARM_ID,
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = ARM_DIR / "TEST_RECEIPT_A05.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
