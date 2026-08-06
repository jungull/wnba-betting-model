#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for the P36 shared runner.

BLINDED: every frame here is synthetic (synthetic_fixture.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it (the unseal branch is exercised only through an
injected mapping).

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/runner/tests/TESTS.py
Writes: ../TEST_RECEIPT.json (machine-readable results).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNNER = HERE.parent
for p in (str(RUNNER), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import cluster_bootstrap as cb                                         # noqa: E402
import guard_harness as gh                                             # noqa: E402
import k0_flat as kf                                                   # noqa: E402
import quasipoisson_irls as qp                                         # noqa: E402
import receipts                                                        # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402
import seed_manifest as sm                                             # noqa: E402
import synthetic_fixture as fx                                         # noqa: E402
import toy_arm                                                         # noqa: E402

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
def t01_seed_identity():
    """The frozen derivation, recomputed independently."""
    m = {}
    for purpose, fid, b in (("test_bootstrap", "syn_lt_3002", 0),
                            ("train_refit", "syn_lt_3003", 1999),
                            ("test_bootstrap", "fold_x", 123456)):
        expected = int.from_bytes(hashlib.sha256(
            f"{rc.MASTER_SEED}|{fid}|{purpose}|{b}".encode("utf-8")).digest()[:4], "big")
        got = sm.derive_seed(purpose, fid, b)
        check(got == expected, f"seed mismatch for {(purpose, fid, b)}")
        m[f"{purpose}|{fid}|{b}"] = got
    check(sm.derive_seed("test_bootstrap", "f", 1) != sm.derive_seed("train_refit", "f", 1),
          "purposes must separate streams")
    check(sm.derive_seed("test_bootstrap", "f1", 1) != sm.derive_seed("test_bootstrap", "f2", 1),
          "folds must separate streams")
    check(sm.derive_seed("test_bootstrap", "f", 1) == sm.derive_seed("test_bootstrap", "f", 1),
          "derivation must be deterministic")
    return {"seeds": m}


def t02_irls_identities():
    rng = np.random.Generator(np.random.PCG64(11))
    n = 4000
    off = np.log(rng.uniform(60, 100, n))
    x = rng.normal(size=n)
    beta_true = 0.3
    y = rng.poisson(np.exp(off + beta_true * x)).astype(float)

    # zero-parameter identity: eta = offset exactly, no fit
    f0 = qp.fit(None, y, off)
    check(f0.converged and f0.n_iter == 0 and f0.beta.size == 0, "zero-parameter fit shape")
    check(np.allclose(qp.predict_mu(np.empty((n, 0)), f0.beta, off), np.exp(off)),
          "zero-parameter mu must equal exp(offset) exactly")

    # intercept-only-with-offset analytic identity: alpha = log(sum y / sum exp(off))
    f1 = qp.fit(np.ones((n, 1)), y, off, column_names=("intercept",))
    alpha_analytic = float(np.log(y.sum() / np.exp(off).sum()))
    check(f1.converged, "intercept fit converged")
    check(abs(f1.beta[0] - alpha_analytic) < 1e-10,
          f"intercept MLE {f1.beta[0]} != analytic {alpha_analytic}")

    # slope recovery on synthetic truth
    f2 = qp.fit(x[:, None], y, off, column_names=("x",))
    check(f2.converged, "slope fit converged")
    check(abs(f2.beta[0] - beta_true) < 0.05,
          f"slope {f2.beta[0]} not near synthetic truth {beta_true}")

    # determinism: bitwise identical repeat
    f2b = qp.fit(x[:, None], y, off, column_names=("x",))
    check(f2.beta.tobytes() == f2b.beta.tobytes() and f2.n_iter == f2b.n_iter,
          "IRLS must be bitwise deterministic")
    return {"alpha_analytic": alpha_analytic, "alpha_fit": float(f1.beta[0]),
            "beta_true": beta_true, "beta_fit": float(f2.beta[0]), "n_iter": f2.n_iter}


def t03_irls_nonconvergence_flag():
    rng = np.random.Generator(np.random.PCG64(12))
    n = 500
    off = np.zeros(n)
    x = rng.normal(size=n)
    y = rng.poisson(np.exp(3.0 + 1.0 * x)).astype(float)
    f = qp.fit(np.column_stack([np.ones(n), x]), y, off, max_iter=1)
    check(not f.converged and f.reason in ("iteration_cap", "nonfinite"),
          "1-iteration cap must be recorded as non-convergence")
    # frozen defaults are the pins
    import inspect
    sig = inspect.signature(qp.fit)
    check(sig.parameters["tol"].default == rc.IRLS_TOL
          and sig.parameters["max_iter"].default == rc.IRLS_MAX_ITER,
          "fit defaults must be the frozen pins")
    return {"reason": f.reason}


def t04_cluster_bootstrap_integrity():
    cl = np.repeat(np.arange(100, 130), 2)          # 30 clusters x 2 rows
    _, rows = cb.cluster_row_map(cl)
    idx_a = cb.test_bootstrap_draw_indices("syn_lt_3002", 7, rows)
    idx_b = cb.test_bootstrap_draw_indices("syn_lt_3002", 7, rows)
    check(np.array_equal(idx_a, idx_b), "same (fold, b) must give the identical draw (pairing)")
    idx_c = cb.test_bootstrap_draw_indices("syn_lt_3002", 8, rows)
    check(not np.array_equal(idx_a, idx_c), "different b must give a different draw")
    # games never split: every sampled cluster contributes BOTH rows
    vals, counts = np.unique(cl[idx_a], return_counts=True)
    check(np.all(counts % 2 == 0), "both team-rows of every sampled game must be carried")
    check(len(idx_a) == 2 * 30, "draw resamples n_clusters cluster slots")
    return {"n_rows_draw": int(len(idx_a)), "n_distinct_clusters_draw": int(len(vals))}


def t05_k7_symmetric_na_rule():
    rng = np.random.Generator(np.random.PCG64(13))
    n_cl = 12
    cl = np.repeat(np.arange(n_cl), 2)
    n = len(cl)
    off = np.log(rng.uniform(60, 100, n))
    x = rng.normal(size=n)
    ind = np.zeros(n)
    ind[cl == 3] = 1.0                    # indicator supported in exactly ONE cluster
    y = rng.poisson(np.exp(off)).astype(float)
    X_arm = np.column_stack([x, ind])
    X_null = ind[:, None]
    out = cb.train_refit_bootstrap("syn_lt_3002",
                                   X_arm=X_arm, arm_cols=["x", "ind"],
                                   X_null=X_null, null_cols=["ind"],
                                   y=y, offset=off, cluster_ids=cl,
                                   indicator_cols=["ind"], n_draws=300)
    n_na = out["n_na_draws"]
    check(n_na > 0, "draws omitting the single supported cluster must be NA")
    check(out["na_reasons"]["indicator_constant"] == n_na, "NA reason must be recorded")
    exp_frac = (1 - 1 / n_cl) ** n_cl          # P(cluster 3 never sampled) ~ 0.352
    check(abs(n_na / 300 - exp_frac) < 0.12, f"NA rate {n_na/300} far from expected {exp_frac}")
    check(out["arm_intervals"]["x"]["n_effective"] == 300 - n_na,
          "NA draws must be excluded from the ARM interval")
    check(out["null_intervals"]["ind"]["n_effective"] == 300 - n_na,
          "NA draws must be excluded from the NULL interval too (symmetric)")

    # (b) non-convergence branch: forcing a 1-iteration cap makes EVERY draw NA for both
    out2 = cb.train_refit_bootstrap("syn_lt_3002",
                                    X_arm=x[:, None], arm_cols=["x"],
                                    X_null=np.empty((n, 0)), null_cols=[],
                                    y=y, offset=off, cluster_ids=cl,
                                    indicator_cols=[], n_draws=50, max_iter=1)
    check(out2["n_na_draws"] == 50 and out2["na_reasons"]["nonconvergence"] == 50,
          "refit non-convergence must be NA for both members")
    check(out2["arm_intervals"]["x"]["n_effective"] == 0, "no interval from all-NA draws")
    return {"n_na_indicator": int(n_na), "expected_na_fraction": exp_frac,
            "n_na_nonconvergence": int(out2["n_na_draws"])}


def t06_blinding():
    check(rc.UNSEAL_ENV_FLAG not in os.environ,
          "P38_UNSEALED must NOT exist in the test environment")
    ok = blinding.assert_not_real(n_rows=144, n_clusters=72,
                                  fold_ids=["syn_lt_3002", "syn_lt_3003"], env={})
    check(ok["unsealed"] is False and not ok["real_signatures"], "synthetic must be admitted")
    expect_raises(blinding.BlindingViolation,
                  lambda: blinding.assert_not_real(n_rows=2982, env={}),
                  "real universe row count must refuse")
    expect_raises(blinding.BlindingViolation,
                  lambda: blinding.assert_not_real(n_rows=100, n_clusters=1495, env={}),
                  "contract-schedule cluster count must refuse")
    expect_raises(blinding.BlindingViolation,
                  lambda: blinding.assert_not_real(fold_ids=["train_lt_2024"], env={}),
                  "real D006 fold id must refuse")
    real_hash = next(iter(rc.REAL_ARTIFACT_SHA256))
    expect_raises(blinding.BlindingViolation,
                  lambda: blinding.assert_not_real(artifact_hashes=[real_hash], env={}),
                  "frozen real artifact hash must refuse")
    # unseal branch tested ONLY via an injected mapping; os.environ is never touched
    rec = blinding.assert_not_real(n_rows=2982, env={rc.UNSEAL_ENV_FLAG: "1"})
    check(rec["unsealed"] is True and rec["real_signatures"],
          "explicit flag in an injected mapping admits, with signatures recorded")
    check(rc.UNSEAL_ENV_FLAG not in os.environ, "flag still absent after the unseal-branch test")
    return {"refusals_tested": 4}


def t07_guard_pins():
    rec = gh.verify_guard_pins()
    check(rec["all_match"], f"guard pins must match the frozen bytes: {rec['mismatches']}")
    saved = gh.GUARD_SHA256_PINS
    try:
        gh.GUARD_SHA256_PINS = {**saved, "P22_postgame_surrogate_guard": "0" * 64}
        expect_raises(gh.GuardHarnessFailure, gh.verify_guard_pins,
                      "tampered pin must fail closed")
    finally:
        gh.GUARD_SHA256_PINS = saved
    return {"pins_checked": len(rec["measured"]), "all_match": True}


def t08_p26_wrapper():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    toy = toy_arm.ToyArm([f["fold_id"] for f in folds], len(df))
    rec = toy.p26_k0_record()
    out = gh.p26_check(rec)
    check(out["valid"] and not out["r8_filtered_findings"],
          "toy substantive record must validate with no adjudication")

    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = ["x_toy"]        # treatment survives in the null
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null retaining the treatment must be blocked")

    cal = json.loads(json.dumps(rec))
    cal["arm_id"] = "TOY_cal"
    cal["arm_kind"] = "calibration_only"
    cal["verdict_label_policy"] = ("CALIBRATION RESULT ONLY -- not eligible for a feature "
                                   "value label however large challenger_vs_k0 is")
    out_cal = gh.p26_check(cal)
    check(out_cal["valid"] and len(out_cal["r8_filtered_findings"]) >= 1,
          "calibration_only record must pass via the P35 R8 adjudication, recorded")
    check(out_cal["r8_adjudication_basis"] is not None, "adjudication basis must be recorded")

    cal_bad = json.loads(json.dumps(cal))
    cal_bad["treatment_mechanism"]["tested_parameters"] = []
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(cal_bad),
                  "calibration_only with no tested parameter must remain blocked")
    return {"r8_filtered_kinds": [f["kind"] for f in out_cal["r8_filtered_findings"]]}


def t09_guard_negative_paths():
    df = fx.build_universe()
    basis = fx.build_prohibited_basis(df)
    # P22: an honest same-game declaration blocks unconditionally
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        df, ["x_toy"], prohibited_basis=basis,
        lag_specs={"x_toy": {"column": "x_toy", "kind": "SAME_GAME",
                             "entity_keys": ("game_id",)}}),
        "SAME_GAME must block")
    # P22: an undeclared column blocks (absence of declaration is failure, never a pass)
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        df, ["x_toy"], prohibited_basis=basis, lag_specs={}),
        "missing LagSpec must block")
    # P25: a candidate affine in the offset blocks under SUBSTANTIVE
    df2 = df.copy()
    df2["aff"] = 2.0 * df2[rc.OFFSET_COL] + 1.0
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p25_check(
        df2, candidate_features=["aff"], nuisance_features=[]),
        "offset-affine candidate must block as calibration in a SUBSTANTIVE arm")
    # P25: contrast_ name without preregistration blocks
    df3 = df.copy()
    df3["contrast_fake"] = df3["x_toy"]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p25_check(
        df3, candidate_features=["contrast_fake"], nuisance_features=[]),
        "unregistered contrast_ column must block")
    # P23: required receipt missing / wrong pin
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p23_check(
        requires_franchise_continuity=True, receipts=[]),
        "missing franchise-continuity receipt must fail closed")
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p23_check(
        requires_franchise_continuity=True,
        receipts=[{"team_cities_sha256": "f" * 64}]),
        "wrong team_cities pin must fail closed")
    ok = gh.p23_check(requires_franchise_continuity=True,
                      receipts=[{"team_cities_sha256": rc.TEAM_CITIES_SHA256_PIN}])
    check(ok["valid"], "correct pin passes")
    # P27: both documented fold-policy readings run on synthetic data (choice recorded)
    for policy in ("SEASON_BLOCK", "EXPANDING_PRIOR_SEASONS"):
        rec27 = gh.p27_check(df, candidate_features=["x_toy"], nuisance_terms=["z_ind"],
                             cluster_col="game_id", fold_policy=policy,
                             null_features=[], null_nuisance=["z_ind"], arm_id="TOY")
        check(rec27["overall"] != "FAIL" and rec27["fold_policy"] == policy,
              f"P27 must run and record fold policy {policy}")
    return {"negative_paths": 6, "p27_policies_run": 2}


def t10_conformance_and_intercept_invariant():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    toy = toy_arm.ToyArm(fids, len(df))
    rec = ri.validate_arm_module(toy)
    check(rec["conformant"], "toy arm must conform")

    class Broken(toy_arm.ToyArm):
        def declared_family(self):
            return "RECALIBRATION"
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(Broken(fids, len(df))),
                  "non-SUBSTANTIVE declared_family must be refused")

    class WrongIntercept(toy_arm.ToyArm):
        arm_id = "A07_early_season_transient"     # frozen table pins free intercept
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(WrongIntercept(fids, len(df))),
                  "intercept-table violation must be refused")

    # bundle-level: intercept present without the pin
    b = toy.build_design(folds[0], df)
    b["nuisance_cols"] = ["z_ind", "intercept"]
    b["k0_matched_design"]["nuisance_cols"] = ["z_ind", "intercept"]
    b["columns"]["intercept"] = np.ones(len(df))
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_design_bundle(b, df, False, "f"),
                  "unpinned intercept column must be refused")
    # intercept pinned but missing from the null
    ti = toy_arm.ToyArmWithIntercept(fids, len(df))
    b2 = ti.build_design(folds[0], df)
    b2["k0_matched_design"]["nuisance_cols"] = ["z_ind"]
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_design_bundle(b2, df, True, "f"),
                  "intercept must be in arm AND null identically")
    # a constant non-intercept column is a silent intercept
    b3 = toy.build_design(folds[0], df)
    b3["columns"]["x_toy"] = np.full(len(df), 3.14)
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_design_bundle(b3, df, False, "f"),
                  "constant design column must be refused as a silent intercept")
    ok = ri.validate_design_bundle(ti.build_design(folds[0], df), df, True, "f")
    check(ok["valid"], "pinned-intercept bundle validates")
    return {"checks": 6}


def t11_k0_flat_identities():
    rng = np.random.Generator(np.random.PCG64(14))
    n = 600
    off = np.log(rng.uniform(60, 100, n))
    y = rng.poisson(np.exp(off)).astype(float)
    out = kf.fit_k0_flat(y[:400], off[:400], y[400:], off[400:])
    check(out["role"] == "diagnostic_only", "K0_FLAT must be labelled diagnostic_only")
    v1 = out["variants"]["k0_flat_offset_intercept"]
    alpha = v1["fit"]["beta"][0]
    alpha_analytic = float(np.log(y[:400].sum() / np.exp(off[:400]).sum()))
    check(abs(alpha - alpha_analytic) < 1e-10, "offset-intercept variant analytic identity")
    v2 = out["variants"]["k0_flat_pure_intercept"]
    check(abs(np.exp(v2["fit"]["beta"][0]) - y[:400].mean()) < 1e-8,
          "pure-intercept variant must predict the training mean")
    check(v1["test_mae"] is not None and v2["test_mae"] is not None, "diagnostic MAEs computed")
    return {"alpha": alpha, "alpha_analytic": alpha_analytic}


def t12_receipts():
    tmp = HERE / "artifacts"
    tmp.mkdir(exist_ok=True)
    probe = tmp / "probe.bin"
    probe.write_bytes(b"p36-probe")
    expected = hashlib.sha256(b"p36-probe").hexdigest()
    rec = receipts.build_receipt(
        arm_id="TOY", element_id="TOY__single", enumeration_element={},
        declared_family="SUBSTANTIVE", blinding={"unsealed": False}, guard_pins={},
        guard_records={}, seed_manifest=sm.build_manifest(["f1"], 10, 10),
        folds=[], results={}, input_paths={"probe": probe}, run_git=False)
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(rec["inputs"]["probe"]["sha256"] == expected, "input hashing must be exact")
    check(rec["code"]["git_invoked"] is False and rec["code"]["commit"] is None,
          "tests never invoke git (standing rule 4); recorded honestly")
    check(len(rec["code"]["sources"]) >= 9, "runner source closure hashed")
    body = {k: v for k, v in rec.items() if k not in ("recorded_utc", "manifest_digest")}
    check(rec["manifest_digest"] == receipts.canonical_digest(body),
          "manifest digest must recompute")
    return {"n_sources_hashed": len(rec["code"]["sources"])}


def t13_end_to_end_synthetic():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    basis = fx.build_prohibited_basis(df)
    toy = toy_arm.ToyArm([f["fold_id"] for f in folds], len(df))
    out_path = HERE / "artifacts" / "TOY_receipt.json"
    t0 = time.time()
    rec = rn.run_arm(toy, df, folds, prohibited_basis=basis, env={},
                     out_path=out_path, run_git=False)
    dt = time.time() - t0
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema")
    check(out_path.exists(), "receipt file written")
    check(rec["results"]["evaluable_folds"] == [f["fold_id"] for f in folds],
          "both synthetic folds evaluable")
    check(rec["results"]["pooled"] is not None
          and rec["results"]["pooled"]["n_draws"] == rc.B_TEST_BOOTSTRAP,
          "pooled inference at the frozen B")
    for e in rec["folds"]:
        if e["status"] != "EVALUABLE":
            continue
        check(e["train_refit"]["n_draws"] == rc.B_TRAIN_REFIT, "frozen train-refit B")
        check(e["k0_flat"]["role"] == "diagnostic_only", "K0_FLAT diagnostic label")
        beta = dict(zip(e["point_fits"]["arm"]["column_names"],
                        e["point_fits"]["arm"]["beta"]))
        check(abs(beta["x_toy"] - fx.TRUE_BETA_X) < 0.15,
              f"synthetic effect recovered loosely: {beta['x_toy']}")
    check(set(rec["guard_records"]["p22_per_fold"]) ==
          {f["fold_id"] for f in folds} | {rn.FINAL_FOLD_ID},
          "P22 ran per fold plus the final assembled design")
    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict")
    check(rec["seeds"]["master_seed"] == rc.MASTER_SEED, "seed manifest master pin")

    # determinism: an identical second run must reproduce results and fold records exactly
    rec2 = rn.run_arm(toy, df, folds, prohibited_basis=basis, env={}, run_git=False)
    d1 = receipts.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = receipts.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: the same runner REFUSES a frame with a real fold id, flag absent
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(toy, df, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED")
    return {"seconds": round(dt, 2),
            "pooled_delta_mae": rec["results"]["pooled"]["delta_mae"],
            "pooled_p_two_sided": rec["results"]["pooled"]["p_two_sided"],
            "results_digest": d1,
            "note": "synthetic-only numbers; no real fold was touched"}


def t14_frozen_constant_pins():
    check(rc.IRLS_TOL == 1e-10 and rc.IRLS_MAX_ITER == 100, "IRLS pins")
    check(rc.B_TEST_BOOTSTRAP == 10_000 and rc.B_TRAIN_REFIT == 2_000, "bootstrap pins")
    check(rc.COEF_INTERVAL_LEVEL == 0.95, "interval level pin")
    check(rc.MASTER_SEED == 20260806, "master seed pin")
    check(rc.OFFSET_COL == "log_exposure"
          and rc.INCUMBENT_PROJECTION_COL == "projected_team_off_possessions", "column pins")
    check(rc.DECLARED_FAMILY_ALL_FITTED_ARMS == "SUBSTANTIVE"
          and rc.RECALIBRATION_DECLARATION == "NOT_APPLICABLE", "guard declaration pins")
    check(rc.P35_SPEC_SHA256 ==
          "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32", "P35 hash pin")
    check(rc.ARMS_WITH_FREE_GLOBAL_INTERCEPT == frozenset({"A07", "A12", "A13", "A14", "A15"}),
          "intercept table (with)")
    check(len(rc.ARMS_WITHOUT_GLOBAL_INTERCEPT) == 18, "intercept table (without)")
    # the P35 SPEC bytes on disk still hash to the pin (frozen input integrity)
    p35 = gh.STAGE2B / "P35_FREEZE_TASK_CARDS" / "SPEC.json"
    check(receipts.sha256_file(p35) == rc.P35_SPEC_SHA256, "P35 SPEC bytes unchanged on disk")
    return {"p35_verified": True}


TESTS = [
    ("T01_seed_identity", t01_seed_identity),
    ("T02_irls_identities", t02_irls_identities),
    ("T03_irls_nonconvergence_flag", t03_irls_nonconvergence_flag),
    ("T04_cluster_bootstrap_integrity", t04_cluster_bootstrap_integrity),
    ("T05_k7_symmetric_na_rule", t05_k7_symmetric_na_rule),
    ("T06_blinding", t06_blinding),
    ("T07_guard_pins", t07_guard_pins),
    ("T08_p26_wrapper", t08_p26_wrapper),
    ("T09_guard_negative_paths", t09_guard_negative_paths),
    ("T10_conformance_and_intercept_invariant", t10_conformance_and_intercept_invariant),
    ("T11_k0_flat_identities", t11_k0_flat_identities),
    ("T12_receipts", t12_receipts),
    ("T13_end_to_end_synthetic", t13_end_to_end_synthetic),
    ("T14_frozen_constant_pins", t14_frozen_constant_pins),
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
        except Exception as e:                                        # noqa: BLE001
            RESULTS.append({"test": name, "passed": False,
                            "seconds": round(time.time() - t0, 2),
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(limit=8)})
            print(f"FAIL  {name}: {type(e).__name__}: {e}")
    receipt = {
        "schema": "p36_runner_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = RUNNER / "TEST_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str),
                   encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
