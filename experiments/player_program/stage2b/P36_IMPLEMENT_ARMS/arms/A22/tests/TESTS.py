#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for A22_lineup_churn_tv_distance.

BLINDED: every frame here is synthetic (synthetic_fixture_a22.py); no real fold, no real MAE,
no comparative historical performance anywhere. The suite asserts P38_UNSEALED is ABSENT from
the process environment and never sets it (the unseal branch is exercised only through an
injected mapping, exactly like the shared runner's own suite).

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A22/ only. Imports the
frozen shared runner (runner/*.py) as a contract; never writes to runner/ or to any other arm's
directory.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A22/tests/TESTS.py
Writes: ../TEST_RECEIPT.json (machine-readable results).
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

import arm_a22 as a22mod                                              # noqa: E402
import feature_construction as fc                                     # noqa: E402
import synthetic_fixture_a22 as fx                                    # noqa: E402

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
    lineups = fx.build_lineup_source(df)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = a22mod.A22Arm(fids, len(df), lineups=lineups)
    return arm, df, folds


# ------------------------------------------------------------------------------- tests
def t01_module_conformance():
    arm, df, folds = _fresh_arm()
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], "A22 module must conform to RUNNER_INTERFACE.md")
    check(rec["arm_id"] == a22mod.ARM_ID, "conformance record must carry the frozen arm_id")
    check(rec["enumeration_element"] == {}, "A22 has no enumeration grid (single element)")

    class WrongFamily(a22mod.A22Arm):
        def declared_family(self):
            return "RECALIBRATION"
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(
                      WrongFamily([f["fold_id"] for f in folds], len(df))),
                  "non-SUBSTANTIVE declared_family must be refused (P35 p25_guard_invocation_pins"
                  " pins SUBSTANTIVE for every fitted arm, A22 included)")

    class WrongIntercept(a22mod.A22Arm):
        def uses_global_intercept(self):
            return True
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(
                      WrongIntercept([f["fold_id"] for f in folds], len(df))),
                  "A22 is in P35 ARMS_WITHOUT_GLOBAL_INTERCEPT; claiming a free intercept must "
                  "be refused by the frozen intercept table")
    check(a22mod.ARM_ID.split("_")[0] in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT,
          "A22 must appear in the frozen no-intercept table")
    return {"conformant": True}


def t02_recurrence_matches_naive_definition():
    """Directly verifies feature_construction's O(n) recurrence against the naive O(n^2)
    double-sum definition of the recency-decayed base window, for a small synthetic team
    history with season boundaries -- the closed-form algebra check the module docstring names."""
    rng = np.random.default_rng(11)
    n_games = 9
    seasons = [9001] * 4 + [9002] * 3 + [9003] * 2
    rows = []
    for i in range(n_games):
        players = rng.choice([f"P{k}" for k in range(6)], size=5, replace=False)
        for p in players:
            rows.append({"team_id": "T", "game_id": 900_000 + i, "game_date": 9_000_00 + i,
                        "season": seasons[i], "player_id": p, "appearances": 1.0})
    long = pd.DataFrame(rows)
    prior = fc.compute_prior_last_and_base(long)
    prior = prior.sort_values("game_date").reset_index(drop=True)

    base = fc._recency_weight_base(fc.HALF_LIFE_GAMES)
    lut = {i: dict(zip(long[long["game_id"] == 900_000 + i]["player_id"],
                       long[long["game_id"] == 900_000 + i]["appearances"]))
          for i in range(n_games)}

    for i in range(n_games):
        # naive double sum: last = game i-1 raw; base = decayed sum over k = 0..i-2
        if i >= 1:
            naive_last = lut[i - 1]
        else:
            naive_last = {}
        naive_base = {}
        for k in range(max(0, i - 1)):
            w = base ** (i - k) * (0.5 ** (seasons[i] - seasons[k]))
            for pid, v in lut[k].items():
                naive_base[pid] = naive_base.get(pid, 0.0) + w * v
        got_last = prior.loc[i, "last_counts"]
        got_base = prior.loc[i, "base_counts"]
        check(got_last == naive_last, f"row {i}: last_counts must match the naive definition "
                                      f"exactly ({got_last} vs {naive_last})")
        all_keys = set(naive_base) | set(got_base)
        for k in all_keys:
            check(abs(naive_base.get(k, 0.0) - got_base.get(k, 0.0)) < 1e-9,
                  f"row {i}, player {k}: base_counts must match the naive double-sum definition "
                  f"to float precision")
    return {"n_games_checked": n_games}


def t03_fallback_numeric_trigger():
    """churn := 0 exactly when n_prior_games <= 1 (the frozen numeric_trigger, verbatim), and
    n_prior_games is the exact within-team chronological index."""
    df = fx.build_universe(n_games_per_team_per_season=6, seed=99)
    lineups = fx.build_lineup_source(df)
    appearances = fc.aggregate_game_player_appearances(lineups)
    prior = fc.compute_prior_last_and_base(appearances)
    for team, grp in prior.groupby("team_id"):
        grp = grp.sort_values(["game_date", "game_id"])
        for idx, (_, row) in enumerate(grp.iterrows()):
            check(row["n_prior_games"] == idx,
                  f"n_prior_games must equal the within-team chronological index ({idx})")
            churn = fc.tv_churn(row["last_counts"], row["base_counts"], row["n_prior_games"])
            if idx <= 1:
                check(churn == 0.0, f"idx={idx} (|P|<=1) must force churn := 0 exactly, got "
                                    f"{churn}")
            if idx == 0:
                check(row["last_counts"] == {} and row["base_counts"] == {},
                      "the very first game of a team's history must have BOTH pools empty "
                      "(no prior games at all -- cold-start text)")
            if idx == 1:
                check(row["base_counts"] == {}, "exactly one prior game means no base window "
                                                "exists yet ('no evidence of change')")
    return {"n_rows_checked": len(prior)}


def t04_tv_distance_bounds_and_symmetry():
    """0.5*sum|u_last(j)-u_base(j)| is a proper TV distance: bounded in [0,1], zero iff the two
    usage-share distributions are identical, and symmetric in its two arguments."""
    rng = np.random.default_rng(3)
    for _ in range(200):
        players = [f"P{k}" for k in range(rng.integers(2, 9))]
        last = {p: float(rng.integers(0, 5)) for p in rng.choice(players, size=len(players),
                                                                 replace=False)}
        base = {p: float(rng.integers(0, 5)) for p in rng.choice(players, size=len(players),
                                                                 replace=False)}
        if sum(last.values()) == 0 or sum(base.values()) == 0:
            continue
        c1 = fc.tv_churn(last, base, 5)
        c2 = fc.tv_churn(base, last, 5)          # symmetry
        check(abs(c1 - c2) < 1e-12, "TV churn must be symmetric in u_last/u_base")
        check(-1e-12 <= c1 <= 1.0 + 1e-12, f"TV churn must be bounded in [0,1], got {c1}")
    identical = {"P1": 3.0, "P2": 2.0}
    check(fc.tv_churn(identical, dict(identical), 5) == 0.0,
          "identical usage-share distributions must give churn == 0 exactly")
    disjoint = {"P1": 1.0}, {"P2": 1.0}
    check(abs(fc.tv_churn(disjoint[0], disjoint[1], 5) - 1.0) < 1e-12,
          "fully disjoint single-player usage distributions must give churn == 1 exactly")
    return {"n_random_checked": 200}


def t05_feature_determinism_and_strict_lagging():
    arm, df, folds = _fresh_arm()
    b1 = arm.build_design(folds[0], df)
    b2 = arm.build_design(folds[0], df)
    v1 = np.asarray(b1["columns"][a22mod.TREATMENT_COL])
    v2 = np.asarray(b2["columns"][a22mod.TREATMENT_COL])
    check(v1.tobytes() == v2.tobytes(), "build_design must be bitwise deterministic (repeat call)")
    v3 = np.asarray(arm.build_design(folds[1], df)["columns"][a22mod.TREATMENT_COL])
    check(v1.tobytes() == v3.tobytes(),
          "churn/x are NOT fold-dependent constants (A09 d_t precedent): the treatment column "
          "must be identical across folds too")

    # strict lagging: perturbing a row's OWN lineup, or any LATER game's lineup, must never
    # change any EARLIER row's churn value.
    lineups2 = fx.build_lineup_source(df).copy()
    mid = len(lineups2) // 2
    for slot in ("off_p1", "off_p2"):
        lineups2.loc[mid, slot] = "INTRUDER_PLAYER"
    arm2 = a22mod.A22Arm([f["fold_id"] for f in folds], len(df), lineups=lineups2)
    b1b = arm2.build_design(folds[0], df)
    v1b = np.asarray(b1b["columns"][a22mod.TREATMENT_COL])

    perturbed_date = lineups2.loc[mid, "game_date"]
    earlier_rows = np.flatnonzero(df["game_date"].to_numpy() < perturbed_date)
    check(len(earlier_rows) > 0, "fixture must contain rows strictly before the perturbed game")
    check(np.array_equal(v1[earlier_rows], v1b[earlier_rows]),
          "perturbing a game's lineup must never change any STRICTLY EARLIER row's churn "
          "(strict lagging)")
    same_or_later = np.flatnonzero(df["game_date"].to_numpy() >= perturbed_date)
    check(not np.array_equal(v1[same_or_later], v1b[same_or_later]),
          "the perturbation must actually be exercised: some same-or-later row's churn should "
          "change (the test is otherwise vacuous)")

    bval = ri.validate_design_bundle(b1, df, arm.uses_global_intercept(), folds[0]["fold_id"])
    check(bval["valid"], "design bundle must validate against the frozen intercept invariant")
    check(bval["comparison"] == "term_removal", "A22's K0 comparison is term_removal")
    return {"n_rows": len(df), "treatment_mean": float(v1.mean())}


def t06_p26_k0_contract():
    arm, df, folds = _fresh_arm()
    rec = arm.p26_k0_record()
    out = gh.p26_check(rec)
    check(out["valid"], f"A22's k0_matched record must validate: {out['blocking_after_adjudication']}")
    check(out["r8_filtered_findings"] == [],
          "substantive_feature is NOT calibration_only: R8's adjudication branch must never "
          "fire for A22 (it declares a coefficient, not a slope/intercept role)")

    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = [a22mod.TREATMENT_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null retaining the treatment term must be blocked")
    return {"r8_filtered": len(out["r8_filtered_findings"])}


def t07_p22_lag_declarations():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    b = arm.build_design(folds[0], df)
    frame = df.copy()
    frame[a22mod.TREATMENT_COL] = b["columns"][a22mod.TREATMENT_COL]
    frame[a22mod.NUISANCE_COL] = b["columns"][a22mod.NUISANCE_COL]
    names = [a22mod.TREATMENT_COL, a22mod.NUISANCE_COL]

    ok = gh.p22_check(frame, names, prohibited_basis=basis,
                      lag_specs=arm.lag_specs(), lag_sources=arm.lag_sources())
    check(not ok["blocking"], "the frozen DERIVED_NO_JOIN + SCHEDULE lag declarations must pass P22")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, names, prohibited_basis=basis, lag_specs={}),
        "missing LagSpec for either design column must block")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, names, prohibited_basis=basis,
        lag_specs={**arm.lag_specs(),
                  a22mod.TREATMENT_COL: {"column": a22mod.TREATMENT_COL, "kind": "SAME_GAME",
                                         "entity_keys": ("game_id",)}}),
        "SAME_GAME must block unconditionally regardless of the column's true provenance")
    return {"p22_passed": True, "negative_paths": 2}


def t08_p25_offset_family():
    arm, df, folds = _fresh_arm()
    fold = folds[0]
    b = arm.build_design(fold, df)
    frame = df.copy()
    frame[a22mod.TREATMENT_COL] = b["columns"][a22mod.TREATMENT_COL]
    frame[a22mod.NUISANCE_COL] = b["columns"][a22mod.NUISANCE_COL]
    tr = frame.iloc[fold["train_idx"]].reset_index(drop=True)
    rec = gh.p25_check(tr, candidate_features=[a22mod.TREATMENT_COL],
                       nuisance_features=[a22mod.NUISANCE_COL],
                       preregistered_contrasts=arm.preregistered_contrasts(),
                       prereg_digest_expected=arm.prereg_digest_expected())
    check(rec["passed"], "A22's symmetric churn contrast must pass P25 under SUBSTANTIVE: it is "
                         "not a function of the offset or the incumbent projection")
    check(arm.declared_family() == rc.DECLARED_FAMILY_ALL_FITTED_ARMS
          and arm.recalibration_declaration() == rc.RECALIBRATION_DECLARATION,
          "guard_invocation pins from the frozen card")
    return {"p25_passed": True}


def t09_arm_null_nesting():
    """comparison = term_removal: arm design minus x must equal EXACTLY the null design, which
    carries ONLY the is_playoff_game nuisance term -- the 'same machinery as A17/A21 nulls'."""
    arm, df, folds = _fresh_arm()
    b = arm.build_design(folds[0], df)
    arm_cols = set(b["treatment_cols"]) | set(b["nuisance_cols"])
    k0 = b["k0_matched_design"]
    null_cols = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(arm_cols - null_cols == {a22mod.TREATMENT_COL},
          "removing exactly the treatment term from the arm design must yield the null design")
    check(null_cols == {a22mod.NUISANCE_COL},
          "A22's K0_MATCHED null must carry ONLY the is_playoff_game nuisance term (P35 "
          "task_cards.A22.k0_matched_frozen: 'same machinery as A17/A21 nulls')")
    check(k0["comparison"] == "term_removal", "A22's frozen comparison type is term_removal")
    check(b["indicator_cols"] == [a22mod.NUISANCE_COL],
          "the 0/1 playoff nuisance is the K7 indicator column; churn (continuous) is not")
    return {"arm_cols": sorted(arm_cols), "null_cols": sorted(null_cols)}


def t10_enumeration_element_exact():
    arm, df, folds = _fresh_arm()
    check(arm.enumeration_element() == {}, "A22 carries no enumeration grid (single element, "
                                           "PERSONNEL_CONTINUITY family = {A22: 1})")
    check(arm.element_id() == f"{a22mod.ARM_ID}__single", "element_id must be the frozen literal")
    for f in folds:
        check(arm.enumeration_element() == {}, f"enumeration_element must not vary by fold {f}")
        check(arm.element_id() == f"{a22mod.ARM_ID}__single", "element_id must not vary by fold")
    return {"enumeration_element": {}, "element_id": arm.element_id()}


def t11_kill_conditions_decidable():
    ev = a22mod.evaluate_kill_conditions

    all_cover = {"f1": {"lo": -0.02, "hi": 0.03, "beta": 0.01},
                "f2": {"lo": -0.05, "hi": 0.01, "beta": 0.01},
                "f3": {"lo": -0.01, "hi": 0.04, "beta": 0.02}}
    out1 = ev(all_cover)
    check(out1["killed"] and out1["all_cover_zero"] and not out1["sign_unstable"],
          "coef(x) interval covering 0 in every evaluable fold must be decided KILLED")

    survives = {"f1": {"lo": 0.02, "hi": 0.09, "beta": 0.05},
               "f2": {"lo": 0.01, "hi": 0.07, "beta": 0.04},
               "f3": {"lo": 0.03, "hi": 0.10, "beta": 0.06}}
    out2 = ev(survives)
    check(not out2["killed"], "coef(x) excluding 0 with a stable sign must NOT be killed")

    sign_flip = {"f1": {"lo": 0.02, "hi": 0.09, "beta": 0.05},
                "f2": {"lo": -0.09, "hi": -0.02, "beta": -0.05},
                "f3": {"lo": 0.01, "hi": 0.06, "beta": 0.03}}
    out3 = ev(sign_flip)
    check(out3["killed"] and out3["sign_unstable"], "sign instability across evaluable folds "
                                                    "must be decided KILLED")

    empty = ev({})
    check(not empty["killed"] and empty["n_evaluable_folds"] == 0,
          "zero evaluable folds must decide NOT killed with an honest empty basis (standing rule 7)")

    # ---- depth-absorption check (second frozen kill condition) ----
    da = a22mod.evaluate_depth_absorption
    baseline_signal = {"f1": {"lo": 0.02, "hi": 0.09, "beta": 0.05},
                       "f2": {"lo": 0.01, "hi": 0.07, "beta": 0.04}}
    depth_reverses_all = {"f1": {"lo": -0.03, "hi": 0.02, "beta": -0.005},
                          "f2": {"lo": -0.02, "hi": 0.03, "beta": 0.003}}
    out4 = da(baseline_signal, depth_reverses_all)
    check(out4["absorbed"], "every baseline-excluding fold reversing to cover 0 once the depth "
                            "proxy enters must be decided ABSORBED")

    depth_partial = {"f1": {"lo": -0.03, "hi": 0.02, "beta": -0.005},
                     "f2": {"lo": 0.005, "hi": 0.06, "beta": 0.03}}   # f2 still excludes 0
    out5 = da(baseline_signal, depth_partial)
    check(not out5["absorbed"], "a partial reversal (not every fold) must NOT be decided absorbed")

    no_baseline_signal = {"f1": {"lo": -0.02, "hi": 0.03, "beta": 0.01}}
    out6 = da(no_baseline_signal, {"f1": {"lo": -0.02, "hi": 0.03, "beta": 0.01}})
    check(not out6["absorbed"], "no baseline signal to absorb must NOT be decided absorbed "
                                "(never a manufactured positive)")
    return {"primary_all_cover_killed": out1["killed"], "primary_survives": not out2["killed"],
           "primary_sign_flip_killed": out3["killed"], "depth_absorbed_full": out4["absorbed"],
           "depth_absorbed_partial": out5["absorbed"], "depth_absorbed_none": out6["absorbed"]}


def t12_end_to_end_synthetic():
    arm, df, folds = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    out_path = HERE / "artifacts" / "A22_receipt.json"
    t0 = time.time()
    rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                     p27_fold_policy="EXPANDING_PRIOR_SEASONS",
                     out_path=out_path, run_git=False)
    dt = time.time() - t0
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(out_path.exists(), "receipt file written")
    check(rec["results"]["pooled"] is not None
          and rec["results"]["pooled"]["n_draws"] == rc.B_TEST_BOOTSTRAP,
          "pooled inference at the frozen B")
    for e in rec["folds"]:
        if e["status"] != "EVALUABLE":
            continue
        check(e["train_refit"]["n_draws"] == rc.B_TRAIN_REFIT, "frozen train-refit B")
        check(e["k0_flat"]["role"] == "diagnostic_only", "K0_FLAT diagnostic label")
        arm_names = e["point_fits"]["arm"]["column_names"]
        check(list(arm_names) == [a22mod.TREATMENT_COL, a22mod.NUISANCE_COL],
              "the arm's fitted design must be exactly [treatment, nuisance]")
        null_names = e["point_fits"]["null"]["column_names"]
        check(list(null_names) == [a22mod.NUISANCE_COL],
              "the null's fitted design must carry only the nuisance term")

    check(rec["guard_records"]["p23"]["valid"], "franchise-continuity receipt must validate")
    check(rec["guard_records"]["p23"]["requires_franchise_continuity"] is True,
          "A22 is named in P33 p23_franchise_continuity_precondition")
    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict")
    check(rec["seeds"]["master_seed"] == rc.MASTER_SEED, "seed manifest master pin")

    rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                      p27_fold_policy="EXPANDING_PRIOR_SEASONS", run_git=False)
    d1 = receipts.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = receipts.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, df, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED, for A22 too")

    # negative control: absent franchise-continuity receipt must fail the run closed
    class NoReceiptArm(a22mod.A22Arm):
        def p23_receipts(self):
            return []
    bad_arm = NoReceiptArm([f["fold_id"] for f in folds], len(df),
                           lineups=fx.build_lineup_source(df))
    expect_raises(gh.GuardHarnessFailure,
                  lambda: rn.run_arm(bad_arm, df, folds, prohibited_basis=basis, env={},
                                     p27_fold_policy="EXPANDING_PRIOR_SEASONS", run_git=False),
                  "A22 requires franchise continuity; an absent receipt must fail the run closed")
    return {"seconds": round(dt, 2), "results_digest": d1,
           "note": "synthetic-only numbers; no real fold was touched"}


def t13_frozen_card_pins():
    p35 = gh.STAGE2B / "P35_FREEZE_TASK_CARDS" / "SPEC.json"
    check(receipts.sha256_file(p35) == rc.P35_SPEC_SHA256,
          "P35 SPEC bytes unchanged on disk and match this module's own pin")
    check(a22mod.ARM_ID == "A22_lineup_churn_tv_distance", "arm_id literal pin")
    check(a22mod.TREATMENT_COL not in ("intercept",), "treatment column must never be the "
                                                       "structural intercept name")
    check(fc.HALF_LIFE_GAMES == 10.0 and fc.SEASON_BOUNDARY_DISCOUNT == 0.5,
          "frozen hyperparameters must match task_cards.A22.hyperparameters.fixed exactly")
    return {"p35_verified": True}


TESTS = [
    ("T01_module_conformance", t01_module_conformance),
    ("T02_recurrence_matches_naive_definition", t02_recurrence_matches_naive_definition),
    ("T03_fallback_numeric_trigger", t03_fallback_numeric_trigger),
    ("T04_tv_distance_bounds_and_symmetry", t04_tv_distance_bounds_and_symmetry),
    ("T05_feature_determinism_and_strict_lagging", t05_feature_determinism_and_strict_lagging),
    ("T06_p26_k0_contract", t06_p26_k0_contract),
    ("T07_p22_lag_declarations", t07_p22_lag_declarations),
    ("T08_p25_offset_family", t08_p25_offset_family),
    ("T09_arm_null_nesting", t09_arm_null_nesting),
    ("T10_enumeration_element_exact", t10_enumeration_element_exact),
    ("T11_kill_conditions_decidable", t11_kill_conditions_decidable),
    ("T12_end_to_end_synthetic", t12_end_to_end_synthetic),
    ("T13_frozen_card_pins", t13_frozen_card_pins),
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
        "schema": "a22_arm_test_receipt/1",
        "arm_id": a22mod.ARM_ID,
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = ARM_DIR / "TEST_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
