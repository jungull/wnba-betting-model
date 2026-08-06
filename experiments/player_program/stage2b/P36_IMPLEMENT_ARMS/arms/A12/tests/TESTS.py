#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for arm module A12
(A12_carryover_additive_decay), against the frozen P36 shared runner contract.

BLINDED: every frame here is synthetic (synthetic_fixture_a12.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Epistemic status of this file and everything it exercises: IMPLEMENTATION. Blinded: no agent may
inspect challenger performance. Unit, synthetic, identity and schema tests only.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A12/tests/TESTS.py
Writes: ./artifacts/A12_TEST_RECEIPT.json (machine-readable results) and
        ../A12_TEST_RECEIPT.json (summary, for the arm directory).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent          # arms/A12/tests
ARM_DIR = HERE.parent                            # arms/A12
RUNNER = ARM_DIR.parents[1] / "runner"           # P36_IMPLEMENT_ARMS/runner
P26 = ARM_DIR.parents[2] / "P26_ARM_SPECIFIC_K0_CONTRACT"
for p in (str(RUNNER), str(ARM_DIR), str(HERE), str(P26)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402
import validate_k0_matched as vk                                       # noqa: E402

import A12_carryover_additive_decay as A12                             # noqa: E402
import synthetic_fixture_a12 as fx                                     # noqa: E402

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


def make_module(df, folds=None):
    fids = [] if folds is None else [f["fold_id"] for f in folds]
    return A12.A12CarryoverAdditiveDecay(df, fold_ids=fids, n_rows=len(df),
                                         pace_col=fx.PACE_COL)


# ------------------------------------------------------------------------------- tests

def t01_conformance():
    """The module satisfies runner_interface.validate_arm_module (RUNNER_INTERFACE.md section 2)."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = make_module(df, folds)
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], f"A12 module must conform: {rec}")
    check(arm.arm_id == "A12_carryover_additive_decay", "arm_id must match the frozen card")
    check(arm.card_id() == arm.arm_id, "card_id defaults to arm_id")
    check(arm.declared_family() == "SUBSTANTIVE", "P35 p25_guard_invocation_pins")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "no RECALIBRATION arm survives")
    check(arm.uses_global_intercept() is True,
          "P35 intercept table: A12 in ARMS_WITH_FREE_GLOBAL_INTERCEPT")
    return {"conformant": True}


def t02_enumeration_element_exact():
    """h=5 is FIXED by source (P33 hyperparameters.fixed.h): single element, no grid."""
    df = fx.build_universe()
    arm = make_module(df)
    check(arm.enumeration_element() == {}, "A12 has no enumerated grid; element must be {}")
    check(arm.element_id() == "A12_carryover_additive_decay__single", arm.element_id())
    check(A12.H == 5.0, "h must be pinned at 5, never tunable")
    check(arm.p23_receipts()[0]["team_cities_sha256"] == rc.TEAM_CITIES_SHA256_PIN,
          "franchise-continuity receipt must pin the frozen team_cities sha256")
    check(arm.requires_franchise_continuity() is True,
          "A12 IS in the P33 p23_franchise_continuity_precondition arm list")
    return {"enumeration_element": arm.enumeration_element(), "element_id": arm.element_id()}


def t03_feature_determinism():
    """build_design is a pure, deterministic function of (fold, universe) -- no hidden RNG,
    no mutable state carried across calls or instances."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = make_module(df, folds)

    b1 = arm.build_design(folds[-1], df)
    b2 = arm.build_design(folds[-1], df)
    same = all(np.array_equal(b1["columns"][k], b2["columns"][k]) for k in b1["columns"])
    check(same, "build_design produced different columns on an identical, repeated call")

    arm2 = make_module(df, folds)
    b3 = arm2.build_design(folds[-1], df)
    same2 = all(np.array_equal(b1["columns"][k], b3["columns"][k]) for k in b1["columns"])
    check(same2, "a fresh module instance over identical inputs produced different columns")

    check(set(np.unique(b1["columns"][A12.INTERCEPT_COL])) == {1.0}, "intercept must be all-ones")
    check(np.allclose(b1["columns"][A12.INTERACTION_COL],
                      b1["columns"][A12.W_N_COL] * b1["columns"][A12.DEV_PREV_COL]),
          "the interaction column must equal w_n * dev_prev exactly")
    return {"n_rows": int(len(df))}


def t04_n_i_and_w_n_strict_lagging():
    """n_i counts strictly-earlier SAME-SEASON contract-schedule games; w(n) = 1/(1+n/5)."""
    probe = pd.DataFrame({
        "team_id": ["T00"] * 5, "season": [4001] * 5,
        "game_date": pd.date_range("2000-01-01", periods=5, freq="D"),
    })
    n_i = A12.compute_n_i(probe, probe["team_id"].to_numpy(), probe["season"].to_numpy(),
                          probe["game_date"].to_numpy())
    check(np.array_equal(n_i, np.array([0.0, 1.0, 2.0, 3.0, 4.0])),
          f"n_i must count strictly-earlier same-season rows; got {n_i}")

    w = A12.w_of_n(n_i)
    expected_w = 1.0 / (1.0 + n_i / 5.0)
    check(np.allclose(w, expected_w), "w(n) must equal 1/(1+n/5) exactly, h=5 fixed")
    check(w[0] == 1.0, "w(0) must equal exactly 1.0 (no decay at season start)")
    check(w[-1] < w[0], "w(n) must be strictly decreasing in n")

    # season reset: a fresh season resets n_i to 0 despite prior-season history
    probe2 = pd.DataFrame({
        "team_id": ["T00", "T00"], "season": [4001, 4002],
        "game_date": [pd.Timestamp("2000-01-01"), pd.Timestamp("2001-01-01")],
    })
    hist2 = pd.concat([probe, probe2.iloc[[1]]], ignore_index=True)
    n_i2 = A12.compute_n_i(hist2, probe2["team_id"].to_numpy(), probe2["season"].to_numpy(),
                           probe2["game_date"].to_numpy())
    check(n_i2[1] == 0.0, f"n_i must reset to 0 at a season boundary; got {n_i2}")

    # unresolved (team, season) fails CLOSED, never silently imputes
    bad = pd.DataFrame({"team_id": ["T99"], "season": [4001],
                        "game_date": [pd.Timestamp("2000-01-01")]})
    expect_raises(A12.A12ConstructionFailure,
                 lambda: A12.compute_n_i(probe, bad["team_id"].to_numpy(),
                                        bad["season"].to_numpy(), bad["game_date"].to_numpy()),
                 "an unresolved (team_id, season) pair must raise, not silently produce a value")
    return {"n_i": n_i.tolist(), "w_n": w.tolist()}


def t05_dev_prev_strict_season_lagging():
    """dev_prev_i = team's PRIOR-season mean(pace) - PRIOR-season league mean(pace); no-prior-
    season teams get exactly 0.0 (D010), never an exception."""
    hist = pd.DataFrame({
        "team_id": ["A", "A", "B", "B", "A", "B", "C"],
        "season": [4001, 4001, 4001, 4001, 4002, 4002, 4002],
        "game_date": pd.date_range("2000-01-01", periods=7, freq="D"),
        "pace": [10.0, 12.0, 20.0, 22.0, 99.0, 99.0, 99.0],
    })
    # season 4001: team A mean = 11.0, team B mean = 21.0, league mean = 16.0
    # season 4002 rows: dev_prev(A) = 11.0 - 16.0 = -5.0; dev_prev(B) = 21.0 - 16.0 = 5.0;
    # dev_prev(C) = 0.0 (C has no season-4001 games at all -- no-prior-season, D010)
    query = pd.DataFrame({"team_id": ["A", "B", "C"], "season": [4002, 4002, 4002]})
    dev = A12.compute_dev_prev(hist, query["team_id"].to_numpy(), query["season"].to_numpy(),
                               pace_col="pace")
    check(np.allclose(dev, np.array([-5.0, 5.0, 0.0])), f"got {dev}, expected [-5.0, 5.0, 0.0]")

    # a team's FIRST-ever season (no season < its own in `hist` at all) also zero-fills
    query2 = pd.DataFrame({"team_id": ["A"], "season": [4001]})
    dev2 = A12.compute_dev_prev(hist, query2["team_id"].to_numpy(), query2["season"].to_numpy(),
                                pace_col="pace")
    check(dev2[0] == 0.0, "the very first season must zero-fill dev_prev, never raise (D010)")

    # determinism
    dev_again = A12.compute_dev_prev(hist, query["team_id"].to_numpy(),
                                     query["season"].to_numpy(), pace_col="pace")
    check(np.array_equal(dev, dev_again), "compute_dev_prev must be deterministic")

    # missing pace_col fails closed
    expect_raises(A12.A12ConstructionFailure,
                 lambda: A12.build_prior_season_index(hist.drop(columns=["pace"]), "pace"),
                 "a missing realised pace column must fail closed, never silently impute")
    return {"dev_prev": dev.tolist()}


def t06_arm_vs_null_nesting():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = make_module(df, folds)
    bundle = arm.build_design(folds[-1], df)
    k0 = bundle["k0_matched_design"]

    check(k0["comparison"] == "term_removal", "A12's comparison is term_removal")
    check(k0["treatment_cols"] == [], "K0_MATCHED[A12] holds no form of dev_prev (S6 direction 2)")
    check(set(k0["nuisance_cols"]) == set(bundle["nuisance_cols"]),
         f"null={k0['nuisance_cols']} arm={bundle['nuisance_cols']}")
    check(not (set(bundle["treatment_cols"]) & set(k0["nuisance_cols"])),
         "neither treatment term may re-enter the null through the nuisance side")
    check(set(k0["nuisance_cols"]) | set(k0["treatment_cols"]) <
         set(bundle["nuisance_cols"]) | set(bundle["treatment_cols"]),
         "the null's column set must be a STRICT subset of the arm's (nesting)")
    check(set(bundle["treatment_cols"]) == {A12.DEV_PREV_COL, A12.INTERACTION_COL},
         "the arm's treatment must be exactly the pair {dev_prev, w_n:dev_prev}, tested jointly")

    rec = ri.validate_design_bundle(bundle, df, arm.uses_global_intercept(),
                                    folds[-1]["fold_id"])
    check(rec["valid"], f"runner_interface.validate_design_bundle must pass: {rec}")
    return {"treatment": sorted(bundle["treatment_cols"]), "null": sorted(k0["nuisance_cols"])}


def t07_p26_record_passes_wrapper():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = make_module(df, folds)
    rec = arm.p26_k0_record()
    check(rec["arm_kind"] == "substantive_feature", "matches the frozen card's arm_kind")
    out = gh.p26_check(rec)
    check(out["valid"], f"A12's K0 record must pass the P26 wrapper: {out}")
    rep = vk.validate(rec)
    check(rep["valid"], f"the frozen P26 validator must accept the record directly: {rep}")
    params = rec["treatment_mechanism"]["tested_parameters"]
    check(any(float(p["null_value"]) == 0.0 for p in params),
         "the joint test's null_value must be 0 (no carryover information)")
    check(rec["k0_flat_role"] == "diagnostic_only", "K0_FLAT must be diagnostic_only")
    # R6 lower-order marginality: w_n:dev_prev's factor "w_n" must sit in structural_terms
    check("w_n" in rec["arm_spec"]["structural_terms"],
         "the interaction's lower-order factor w_n must be a declared structural term (R6)")
    return {"r6_lower_order_present": True}


def t08_p26_record_rejects_survivor():
    """Negative control: a null that keeps a treatment term must fail the wrapper closed."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = make_module(df, folds)
    rec = json.loads(json.dumps(arm.p26_k0_record()))
    rec["k0_spec"]["substantive_features"] = [A12.DEV_PREV_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(rec),
                 "a null retaining dev_prev must be blocked")
    return {"negative_control": "blocked"}


def t09_lag_specs_cover_every_design_column():
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = make_module(df, folds)
    bundle = arm.build_design(folds[-1], df)
    declared = set(bundle["treatment_cols"]) | set(bundle["nuisance_cols"])
    specs = arm.lag_specs()
    needing_spec = declared - {A12.INTERCEPT_COL}
    check(needing_spec <= set(specs), f"missing specs for {needing_spec - set(specs)}")
    check(A12.INTERCEPT_COL not in specs, "the structural intercept must not carry a LagSpec")
    check(all(s["kind"] in ("SAME_GAME", "PRIOR_GAME", "SCHEDULE", "DERIVED_NO_JOIN")
             for s in specs.values()), "every declared kind must be a frozen P22 kind")
    check(all(s["kind"] != "SAME_GAME" for s in specs.values()),
         "SAME_GAME blocks unconditionally; none of A12's columns should ever declare it")
    check(specs[A12.W_N_COL]["kind"] == "SCHEDULE", "w_n is a pure schedule fact (disclosed)")
    check(specs[A12.DEV_PREV_COL]["kind"] == "DERIVED_NO_JOIN",
         "dev_prev is a season-level aggregate, not a single-shift PRIOR_GAME lag")
    return {"kinds": {k: v["kind"] for k, v in specs.items()}}


def t10_lag_sources_supplies_history():
    df = fx.build_universe()
    arm = make_module(df)
    sources = arm.lag_sources()
    check("history" in sources, "lag_sources must expose the history frame")
    check(sources["history"] is arm._history, "lag_sources must return the SAME frame supplied "
                                              "at construction, never a copy or a subset")
    return {"has_history": True}


def t11_strict_lagging_p22():
    """Every declared design column passes P22 with its declared LagSpec on a synthetic prohibited
    basis; an undeclared column is refused (absence is never a pass)."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    basis = fx.build_prohibited_basis(df)
    arm = make_module(df, folds)
    b = arm.build_design(folds[-1], df)
    W = df.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    names = [c for c in list(b["treatment_cols"]) + list(b["nuisance_cols"])
             if c != A12.INTERCEPT_COL]
    rec = gh.p22_check(W, names, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                       lag_sources=arm.lag_sources())
    check(not rec.get("blocking"), f"every declared A12 column must pass P22: {rec}")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, [A12.DEV_PREV_COL], prohibited_basis=basis, lag_specs={}),
        "an undeclared LagSpec must block, never silently pass")
    return {"p22_passed": True}


def t12_structural_deactivation_hook():
    df = fx.build_universe()
    arm = make_module(df)
    deact = arm.structurally_deactivated_folds()
    check(deact == ["train_lt_2022"],
         "A12 structurally deactivates exactly train_lt_2022 (2021 has no archived prior season)")
    return {"structurally_deactivated_folds": deact}


def t13_p27_rule_shape_and_digest():
    """p27_rule() returns (ActiveSetRule kwargs, Preregistration kwargs) whose digest matches the
    frozen P27 module's own canonicalisation, and the pair is accepted by the shared P27 wrapper."""
    df = fx.build_universe()
    folds = fx.build_folds(df)
    arm = make_module(df, folds)
    rule_kwargs, prereg_kwargs = arm.p27_rule()
    check(rule_kwargs["rule_id"] == "S7_TIER_SUPPORT_v1", "rule id must match the registry_append")
    check(rule_kwargs["min_nonzero_clusters"] == 10, "numeric trigger: 10-cluster floor")
    check(prereg_kwargs["results_visible_at_registration"] is False,
         "GATE_INVOCATION_CONTRACT section 4: registered before any result is visible")

    import importlib.util
    _name = "p27_fold_estimability_guard_for_A12"
    spec = importlib.util.spec_from_file_location(
        _name,
        RUNNER.parents[1] / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD" / "fold_estimability_guard.py")
    feg = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(_name, feg)   # dataclass() needs cls.__module__ resolvable
    spec.loader.exec_module(feg)
    recomputed = feg.ActiveSetRule(**rule_kwargs).spec_sha256
    check(prereg_kwargs["rule_spec_sha256"] == recomputed,
         "the Preregistration digest must match the rule actually being applied")
    check(prereg_kwargs["rule_spec_sha256"] == A12._rule_spec_sha256(rule_kwargs),
         "this module's own digest helper must agree with the frozen guard's computation")

    b = arm.build_design(folds[-1], df)
    W = df.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    rec = gh.p27_check(W, candidate_features=[A12.DEV_PREV_COL, A12.INTERACTION_COL],
                       nuisance_terms=[A12.W_N_COL, A12.GAP_COL, A12.DEPTH_COL,
                                      A12.OPP_DEPTH_COL],
                       cluster_col="game_id", fold_policy="EXPANDING_PRIOR_SEASONS",
                       null_features=[], null_nuisance=[A12.W_N_COL, A12.GAP_COL, A12.DEPTH_COL,
                                                        A12.OPP_DEPTH_COL],
                       rule_kwargs=rule_kwargs, prereg_kwargs=prereg_kwargs, arm_id=arm.arm_id)
    check(rec.get("overall") != "FAIL", f"P27 must accept the preregistered rule: {rec}")
    return {"rule_spec_sha256": prereg_kwargs["rule_spec_sha256"], "p27_overall": rec["overall"]}


def t14_kill_conditions_decidable():
    ev = A12.evaluate_kill_conditions

    r_pass = ev(delta_mae_n_le_5=0.2, improvement_share_n_le_5=0.9,
               beta1_signs=[1, 1], beta2_signs=[1, 1])
    check(r_pass["killed"] is False, r_pass)

    r_stratum = ev(delta_mae_n_le_5=-0.01, improvement_share_n_le_5=0.9,
                  beta1_signs=[1, 1], beta2_signs=[1, 1])
    check(r_stratum["stratum_n_le_5_no_improvement"] is True and r_stratum["killed"] is True,
         r_stratum)

    r_conc = ev(delta_mae_n_le_5=0.2, improvement_share_n_le_5=0.1,
               beta1_signs=[1, 1], beta2_signs=[1, 1])
    check(r_conc["improvement_not_concentrated_on_coldstart_stratum"] is True and
         r_conc["killed"] is True, r_conc)

    r_sign = ev(delta_mae_n_le_5=0.2, improvement_share_n_le_5=0.9,
               beta1_signs=[1, 1], beta2_signs=[1, -1])
    check(r_sign["beta2_sign_contradicts_decay"] is True and r_sign["killed"] is True, r_sign)

    # zero-signed fold neither confirms nor contradicts
    r_zero = ev(delta_mae_n_le_5=0.2, improvement_share_n_le_5=0.9,
               beta1_signs=[1, 0], beta2_signs=[1, -1])
    check(r_zero["beta2_sign_contradicts_decay"] is False, r_zero)

    check(A12.D010_NON_LICENSE.startswith("D010"), "D010 must be recorded, not silently dropped")
    check(ev(delta_mae_n_le_5=0.2, improvement_share_n_le_5=0.9, beta1_signs=[1],
            beta2_signs=[1]) ==
         ev(delta_mae_n_le_5=0.2, improvement_share_n_le_5=0.9, beta1_signs=[1], beta2_signs=[1]),
         "kill decision must be a pure function")

    expect_raises(ValueError, lambda: A12.beta2_contradicts_decay_kill([1, 1], [1]),
                 "mismatched beta1/beta2 sign lists must raise, not silently truncate")
    return {"pass_case": r_pass, "stratum_kill": r_stratum, "conc_kill": r_conc,
           "sign_kill": r_sign}


def t15_missing_columns_fail_closed():
    df = fx.build_universe()
    arm = make_module(df)
    bad = df.drop(columns=["pace_gap"])
    expect_raises(A12.A12ConstructionFailure, lambda: arm.build_design(
        {"fold_id": "x", "train_idx": np.arange(len(bad)), "test_idx": np.array([], int)}, bad),
        "a missing receipted gap column must fail closed")

    expect_raises(A12.A12ConstructionFailure,
                 lambda: A12.A12CarryoverAdditiveDecay(df.drop(columns=["game_date"])),
                 "missing history columns must fail closed at construction")
    expect_raises(A12.A12ConstructionFailure,
                 lambda: A12.A12CarryoverAdditiveDecay(df, pace_col="nonexistent_col"),
                 "a missing pace column must fail closed at construction")
    return {"checked": True}


def t16_intercept_table_agreement_with_runner_constants():
    check("A12" in rc.ARMS_WITH_FREE_GLOBAL_INTERCEPT, "A12 must be in the free-intercept table")
    check("A12" not in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT, "A12 must not be in the no-intercept table")
    check(A12.OFFSET_COL == rc.OFFSET_COL, "offset column name must agree with the runner")
    check(A12.INTERCEPT_COL == rc.INTERCEPT_COL, "intercept column name must agree with the runner")
    check(A12.P35_SPEC_SHA256 == rc.P35_SPEC_SHA256, "P35 spec hash must agree with the runner pin")
    return {"checked": True}


def t17_end_to_end_synthetic():
    """Full synthetic exercise of the shared runner against this arm module: blinding, guard byte
    pins, conformance, P26-before-P25, per-fold P22/P25, P27, paired point fits, test bootstrap,
    train-refit bootstrap, K0_FLAT diagnostic, receipt -- all on synthetic rows only.

    FINDING, flagged for REPORT.md rather than worked around in the arm module (standing rule 1):
    the shared runner's P22/P25 per-fold loop (runner.run_arm step 5) audits EVERY fold in the
    `folds` argument UNCONDITIONALLY, before the `structurally_deactivated_folds()` skip is ever
    consulted (that skip lives only in the later FIT loop, step 7). A fold whose training rows are
    entirely the arm's own first archived season -- exactly train_lt_2022's real situation, and
    the reason the card structurally deactivates it -- has dev_prev and w_n:dev_prev IDENTICALLY
    ZERO on every training row (no prior season exists), which trips P25's augmented_rank_deficient
    finding and fails the run CLOSED before deactivation logic is reached. This module's own
    `structurally_deactivated_folds()` hook is therefore necessary but NOT sufficient to protect a
    `run_arm` call that still includes such a fold in its `folds` argument; the P38 caller must
    itself omit any fold the card structurally deactivates from `folds`, exactly as this test does
    (`fx.build_folds(df)[1:]`, dropping the synthetic analogue of train_lt_2022). Demonstrated
    directly here rather than silently avoided: `t17b_deactivated_fold_trips_p25_unconditionally`.
    """
    df = fx.build_universe()
    folds = fx.build_folds(df)[1:]     # drop the synthetic train_lt_2022 analogue -- see finding
                                       # above; a correct P38 caller never hands it to run_arm
    basis = fx.build_prohibited_basis(df)
    arm = make_module(df, folds)
    out_path = HERE / "artifacts" / "A12_receipt.json"
    out_path.parent.mkdir(exist_ok=True)
    t0 = time.time()
    rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={}, out_path=out_path,
                     run_git=False)
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
    # the first synthetic fold (train = first season only, prior season undefined for every row)
    # must trip the S7 active-set rule -- exactly the mechanism the real train_lt_2022 situation
    # motivates, exercised here structurally rather than via the literal (real) fold id.
    first_fold_id = folds[0]["fold_id"]
    first_p27_fold = next(f for f in rec["guard_records"]["p27"]["folds"]
                          if f["fold_id"] == f"train_{fx.SEASONS[0]}")
    check(first_p27_fold["active_set_rule"] is not None and
         first_p27_fold["active_set_rule"].get("applied"),
         f"the active-set rule must engage on the prior-season-undefined first fold: "
         f"{first_p27_fold.get('active_set_rule')}")

    rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={}, run_git=False)
    import receipts as rp
    d1 = rp.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = rp.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                 lambda: rn.run_arm(arm, df, bad_folds, prohibited_basis=basis, env={}),
                 "runner must refuse real fold ids without P38_UNSEALED")
    check(rc.UNSEAL_ENV_FLAG not in os.environ, "flag must remain absent from the real environment")

    return {"seconds": round(dt, 2), "evaluable_folds": rec["results"]["evaluable_folds"],
           "results_digest": d1,
           "note": "synthetic-only numbers; no real fold or real MAE was touched"}


def t17b_deactivated_fold_trips_p25_unconditionally():
    """Substantiates the finding documented in t17_end_to_end_synthetic's docstring: the
    synthetic analogue of train_lt_2022 (training rows entirely the first archived season, so
    dev_prev/w_n:dev_prev are identically zero) trips P25's augmented_rank_deficient BLOCKING
    finding when audited directly, exactly as it would inside runner.run_arm's unconditional
    per-fold P22/P25 loop -- demonstrating why the caller, not the runner, must omit this fold."""
    df = fx.build_universe()
    all_folds = fx.build_folds(df)
    first_fold = all_folds[0]
    arm = make_module(df, all_folds)
    b = arm.build_design(first_fold, df)
    check(np.all(b["columns"][A12.DEV_PREV_COL][first_fold["train_idx"]] == 0.0),
         "the synthetic first-season fold must have dev_prev identically zero on training rows "
         "(no archived prior season), mirroring train_lt_2022's real situation")
    W = df.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    W_tr = W.iloc[first_fold["train_idx"]].reset_index(drop=True)
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p25_check(
        W_tr, candidate_features=[A12.DEV_PREV_COL, A12.INTERACTION_COL],
        nuisance_features=[A12.W_N_COL, A12.GAP_COL, A12.DEPTH_COL, A12.OPP_DEPTH_COL]),
        "P25 must block on the structurally-degenerate first fold when audited directly, "
        "confirming the runner-order finding rather than merely asserting it")
    return {"finding_substantiated": True}


def t18_arm_d_untouched_and_ownership():
    """Sanity: this unit writes nothing outside arms/A12/, never reads SEALED_RESULTS, and never
    opens/imports the incumbent Arm D implementation."""
    src = (ARM_DIR / "A12_carryover_additive_decay.py").read_text(encoding="utf-8")
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
         f"must not import any Arm D / D_ewma_shrunk implementation: {imported_names}")
    check(not any(n.startswith("A07") or n.startswith("A08") or n.startswith("A03")
                 for n in imported_names),
         f"must never import another arm's module: {imported_names}")
    for p in ARM_DIR.rglob("*"):
        check(str(p.resolve()).startswith(str(ARM_DIR.resolve())), f"write scope violation: {p}")
    return {"ownership_ok": True, "imports": sorted(imported_names)}


TESTS = [t01_conformance, t02_enumeration_element_exact, t03_feature_determinism,
        t04_n_i_and_w_n_strict_lagging, t05_dev_prev_strict_season_lagging,
        t06_arm_vs_null_nesting, t07_p26_record_passes_wrapper,
        t08_p26_record_rejects_survivor, t09_lag_specs_cover_every_design_column,
        t10_lag_sources_supplies_history, t11_strict_lagging_p22,
        t12_structural_deactivation_hook, t13_p27_rule_shape_and_digest,
        t14_kill_conditions_decidable, t15_missing_columns_fail_closed,
        t16_intercept_table_agreement_with_runner_constants, t17_end_to_end_synthetic,
        t17b_deactivated_fold_trips_p25_unconditionally, t18_arm_d_untouched_and_ownership]


def main():
    check(rc.UNSEAL_ENV_FLAG not in os.environ,
         "P38_UNSEALED must never be set by this blinded suite")
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
        "schema": "p36_arm_a12_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "arm_id": "A12_carryover_additive_decay",
        "n_tests": len(TESTS), "passed": passed, "failed": failed,
        "unseal_flag_present": rc.UNSEAL_ENV_FLAG in os.environ,
        "results": RESULTS,
    }
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "A12_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (ARM_DIR / "A12_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\n{passed}/{len(TESTS)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
