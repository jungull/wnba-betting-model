#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for arm module A21
(A21_garbage_time_contamination), against the frozen P36 shared runner contract.

BLINDED: every frame here is synthetic (synthetic_fixture_a21.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Epistemic status of this file and everything it exercises: IMPLEMENTATION. Blinded: no agent may
inspect challenger performance. Unit, synthetic, identity and schema tests only.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A21/tests/TESTS.py
Writes: ./artifacts/A21_TEST_RECEIPT.json (machine-readable results) and
        ../A21_TEST_RECEIPT.json (summary, for the arm directory).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent          # arms/A21/tests
ARM_DIR = HERE.parent                            # arms/A21
RUNNER = ARM_DIR.parents[1] / "runner"           # P36_IMPLEMENT_ARMS/runner
for p in (str(RUNNER), str(ARM_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a21 as A21                                                  # noqa: E402
import feature_construction as fc                                      # noqa: E402
import synthetic_fixture_a21 as fx                                     # noqa: E402

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


def _build(seed_games=777, seed_poss=321, n_games_per_season=50):
    games = fx.build_games(n_games_per_season=n_games_per_season, seed=seed_games)
    poss = fx.build_possessions(games, seed=seed_poss)
    uni = fx.build_universe(games, poss)
    folds = fx.build_folds(uni)
    return games, poss, uni, folds


# ------------------------------------------------------------------------------- tests

def t01_conformance():
    """The module satisfies runner_interface.validate_arm_module (RUNNER_INTERFACE.md section 2)."""
    _, poss, uni, folds = _build()
    fids = [f["fold_id"] for f in folds]
    arm = A21.A21Arm(poss, fids, len(uni))
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], f"A21 module must conform: {rec}")
    check(arm.arm_id == "A21_garbage_time_contamination", "arm_id must match the frozen card")
    check(arm.card_id() == arm.arm_id, "card_id defaults to arm_id")
    check(arm.declared_family() == "SUBSTANTIVE", "P35 p25_guard_invocation_pins")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "no RECALIBRATION arm survives")
    check(arm.uses_global_intercept() is False,
          "P35 intercept table: A21 in ARMS_WITHOUT_GLOBAL_INTERCEPT")
    return {"conformant": True}


def t02_enumeration_element_exact():
    """Single-element arm (P33 hyperparameters.enumerated={}); RUNNER_INTERFACE.md section 2
    pins '{} for single-element arms'."""
    arm = A21.A21Arm(fx.build_possessions(fx.build_games(seed=1), seed=2), [], 0)
    check(arm.enumeration_element() == {}, "single-element arm must report {}")
    check(arm.element_id() == "A21_garbage_time_contamination__single",
          "element_id must be deterministic")
    return {"enumeration_element": arm.enumeration_element(), "element_id": arm.element_id()}


def t03_feature_determinism():
    """build_design is a deterministic, pure function of (possessions, universe, fold)."""
    _, poss, uni, folds = _build()
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    b1 = arm.build_design(folds[0], uni)
    b2 = arm.build_design(folds[0], uni)
    x1 = np.asarray(b1["columns"][A21.TREATMENT_COL])
    x2 = np.asarray(b2["columns"][A21.TREATMENT_COL])
    check(np.array_equal(x1, x2), "repeated build_design calls must be bitwise identical")
    check(x1.tobytes() == x2.tobytes(), "x bytes must match exactly")

    # order-independence: shuffling the universe row order must not change per-(game,team) values
    uni2 = uni.sample(frac=1.0, random_state=13).reset_index(drop=True)
    fold2 = dict(folds[0])
    tr_ids = set(uni.iloc[folds[0]["train_idx"]]["game_id"].astype(str) + "_" +
                uni.iloc[folds[0]["train_idx"]]["team_id"].astype(str))
    key2 = uni2["game_id"].astype(str) + "_" + uni2["team_id"].astype(str)
    fold2["train_idx"] = np.flatnonzero(key2.isin(tr_ids).to_numpy())
    fold2["test_idx"] = np.flatnonzero(~key2.isin(tr_ids).to_numpy())
    b3 = arm.build_design(fold2, uni2)
    x3 = np.asarray(b3["columns"][A21.TREATMENT_COL])
    key1 = list(zip(uni["game_id"], uni["team_id"]))
    key3 = list(zip(uni2["game_id"], uni2["team_id"]))
    x_by_key1 = dict(zip(key1, x1))
    x_by_key3 = dict(zip(key3, x3))
    check(all(abs(x_by_key1[k] - x_by_key3[k]) < 1e-9 for k in key1),
          "x must be row-order independent")
    return {"n_rows": int(len(uni))}


def t04_strict_lagging():
    """Strict lagging on the raw nc construction: a strictly-earlier game's flags move nc(t,g);
    the row's own game and any strictly-later game never do (feature_construction.py contract)."""
    games = fx.build_games(n_games_per_season=30, seed=11)
    poss = fx.build_possessions(games, seed=13)
    uni = fx.build_universe(games, poss)
    target = uni[["team_id", "opponent_team_id", "game_id", "game_date", "season"]]
    base = fc.compute_nc(poss, target)

    # pick a row with a comfortable prior-game history for its own team
    counts = uni.groupby("team_id")["game_date"].rank(method="first")
    i = int(np.argmax(counts.to_numpy() >= 8))
    check(counts.iloc[i] >= 8, "fixture too small for this test")
    row = uni.iloc[i]
    own_prior_games = poss[(poss["offense_team_id"] == row["team_id"]) &
                           (poss["game_date"] < row["game_date"])]["game_id"].unique()
    check(len(own_prior_games) > 0, "row must have strictly-earlier own games")
    earlier_gid = int(own_prior_games[-1])

    # (a) POSITIVE CONTROL: flipping ALL flags of a strictly-earlier own game must move nc_own
    poss_pert = poss.copy()
    m = (poss_pert["game_id"] == earlier_gid) & (poss_pert["offense_team_id"] == row["team_id"])
    poss_pert.loc[m, "non_competitive_conservative"] = \
        1.0 - poss_pert.loc[m, "non_competitive_conservative"]
    pert = fc.compute_nc(poss_pert, target)
    check(abs(pert["nc_own"][i] - base["nc_own"][i]) > 1e-6,
          "perturbing a strictly-earlier own game must move nc_own")

    # (b) NEGATIVE CONTROL: perturbing the row's OWN game must not move its own nc_own/nc_opp
    poss_same = poss.copy()
    m2 = (poss_same["game_id"] == int(row["game_id"])) & \
        (poss_same["offense_team_id"] == row["team_id"])
    poss_same.loc[m2, "non_competitive_conservative"] = \
        1.0 - poss_same.loc[m2, "non_competitive_conservative"]
    same = fc.compute_nc(poss_same, target)
    check(abs(same["nc_own"][i] - base["nc_own"][i]) < 1e-9,
          "perturbing the row's OWN game must NOT change its own nc_own (no same-game leakage)")

    # (c) NEGATIVE CONTROL: perturbing a STRICTLY LATER own game must not move this row's nc_own
    later_games = poss[(poss["offense_team_id"] == row["team_id"]) &
                       (poss["game_date"] > row["game_date"])]["game_id"].unique()
    check(len(later_games) > 0, "fixture must contain a strictly-later own game for this team")
    poss_later = poss.copy()
    m3 = (poss_later["game_id"] == int(later_games[0])) & \
        (poss_later["offense_team_id"] == row["team_id"])
    poss_later.loc[m3, "non_competitive_conservative"] = \
        1.0 - poss_later.loc[m3, "non_competitive_conservative"]
    later = fc.compute_nc(poss_later, target)
    check(abs(later["nc_own"][i] - base["nc_own"][i]) < 1e-9,
          "perturbing a strictly-later own game must NOT change this row's nc_own")
    return {"row_checked": i, "earlier_game_id": earlier_gid}


def t05_empty_prior_set_imputation():
    """Team openers (no strictly-earlier own game) are NaN before imputation, and are filled with
    the fold's TRAINING-row mean of DEFINED nc values, identically for own/opp (P35 A21 FOLDS F2 /
    A17's rule)."""
    _, poss, uni, folds = _build()
    target = uni[["team_id", "opponent_team_id", "game_id", "game_date", "season"]]
    raw = fc.compute_nc(poss, target)
    check(np.isnan(raw["nc_own"]).any(), "fixture must contain at least one team opener")

    fold = folds[-1]
    train_mask = np.zeros(len(uni), dtype=bool)
    train_mask[fold["train_idx"]] = True
    filled = fc.impute_empty_prior_set(raw["nc_own"], raw["nc_opp"], train_mask)
    check(not np.isnan(filled["nc_own"]).any() and not np.isnan(filled["nc_opp"]).any(),
          "imputed arrays must carry no NaN")

    pooled_train = np.concatenate([raw["nc_own"][train_mask], raw["nc_opp"][train_mask]])
    expected_fill = float(np.nanmean(pooled_train))
    check(abs(filled["imputation_constant"] - expected_fill) < 1e-9,
          "imputation constant must equal the training-row mean of DEFINED nc values")

    nan_own = np.isnan(raw["nc_own"])
    check(np.all(filled["nc_own"][nan_own] == filled["imputation_constant"]),
          "every NaN own-side row must be filled with the single fold constant")

    # held-fixed-across-refits: calling impute again on the SAME raw+mask reproduces the SAME
    # constant (no hidden randomness / no dependence on call order)
    filled2 = fc.impute_empty_prior_set(raw["nc_own"], raw["nc_opp"], train_mask)
    check(filled2["imputation_constant"] == filled["imputation_constant"],
          "imputation constant must be a pure function of (raw nc, train_mask)")

    expect_raises(fc.A21ConstructionFailure,
                  lambda: fc.impute_empty_prior_set(
                      raw["nc_own"], raw["nc_opp"], np.zeros(len(uni), dtype=bool)),
                  "an all-false train_mask must fail closed, never silently fill with 0")
    return {"n_nan_own": int(nan_own.sum()), "fill": filled["imputation_constant"]}


def t06_arm_vs_null_nesting():
    """Arm-vs-null design nesting the card declares: term_removal, null == K0_MATCHED[A17] ==
    [log_exposure | is_playoff_game] exactly, and the arm design is the null plus ONLY x."""
    _, poss, uni, folds = _build()
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    b = arm.build_design(folds[0], uni)
    bval = ri.validate_design_bundle(b, uni, arm.uses_global_intercept(), str(folds[0]["fold_id"]))
    check(bval["valid"], f"A21 design bundle must validate: {bval}")

    k0 = b["k0_matched_design"]
    check(k0["comparison"] == "term_removal", "A21's K0 comparison must be term_removal")
    check(k0["nuisance_cols"] == [A21.NUISANCE_COL] == b["nuisance_cols"],
          "null nuisance terms must equal the arm's nuisance terms exactly (A17's null, carried)")
    check(k0["treatment_cols"] == [], "null must carry zero treatment columns (term_removal)")
    check(b["treatment_cols"] == [A21.TREATMENT_COL], "arm treatment must be exactly x")
    arm_terms = set(b["treatment_cols"]) | set(b["nuisance_cols"])
    null_terms = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(null_terms < arm_terms, "the null's design must be a PROPER subset of the arm's design")
    check(arm_terms - null_terms == {A21.TREATMENT_COL},
          "the null must differ from the arm by EXACTLY the treatment term")
    check(rc.INTERCEPT_COL not in arm_terms | null_terms,
          "no implicit or explicit intercept in either design (P35 K0 K2)")
    return {"arm_terms": sorted(arm_terms), "null_terms": sorted(null_terms)}


def t07_p26_record_valid():
    """The P26 record validates via the shared wrapper; observation_purification is not
    calibration_only, so no R8 slope adjudication should fire."""
    _, poss, uni, folds = _build()
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    rec = arm.p26_k0_record()
    check(rec["arm_kind"] == "observation_purification", "matches the frozen card's arm_kind")
    out = gh.p26_check(rec)
    check(out["valid"], f"A21's k0_matched/1 record must validate against P26: {out}")
    check(not out["r8_filtered_findings"],
          "observation_purification is not calibration_only; no R8 adjudication should fire")

    # negative control: a null that keeps the treatment term must be refused
    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = [A21.TREATMENT_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null retaining x must be blocked")
    return {"arm_kind": rec["arm_kind"]}


def t08_strict_lagging_p22():
    """The constructed design columns pass P22 with their declared LagSpecs on a synthetic frame
    with a synthetic prohibited basis; an undeclared column, and a dishonest SAME_GAME
    declaration, are both refused."""
    _, poss, uni, folds = _build()
    basis = fx.build_prohibited_basis(uni)
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    b = arm.build_design(folds[0], uni)
    W = uni.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    cols = [A21.TREATMENT_COL, A21.NUISANCE_COL]
    rec = gh.p22_check(W, cols, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                       lag_sources=arm.lag_sources())
    check(not rec.get("blocking"), f"A21 columns must pass P22 with their declared LagSpecs: {rec}")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, cols, prohibited_basis=basis, lag_specs={A21.NUISANCE_COL: arm.lag_specs()[
            A21.NUISANCE_COL]}),
        "an undeclared LagSpec (x missing) must block, never silently pass")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, cols, prohibited_basis=basis,
        lag_specs={**arm.lag_specs(),
                  A21.TREATMENT_COL: {"column": A21.TREATMENT_COL, "kind": "SAME_GAME"}}),
        "SAME_GAME must block unconditionally regardless of the true construction")
    return {"p22_passed": True}


def t09_franchise_continuity_receipt():
    _, poss, uni, folds = _build()
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    check(arm.requires_franchise_continuity() is True, "A21 requires the P23 receipt")
    ok = gh.p23_check(requires_franchise_continuity=True, receipts=arm.p23_receipts())
    check(ok["valid"], "A21's own receipt must carry the correctly pinned team_cities hash")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p23_check(
        requires_franchise_continuity=True, receipts=[{"team_cities_sha256": "0" * 64}]),
        "a wrong team_cities pin must fail closed")
    return {"pin": rc.TEAM_CITIES_SHA256_PIN}


def t10_optional_hooks_shape():
    _, poss, uni, folds = _build()
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    check(arm.preregistered_contrasts() is None, "A21 declares no contrast_ column")
    check(arm.prereg_digest_expected() is None, "A21 has no contrast digest")
    check(arm.p27_rule() is None, "A21 registers no ActiveSetRule-shaped P27 rule")
    specs = arm.lag_specs()
    check(set(specs) == {A21.TREATMENT_COL, A21.NUISANCE_COL}, "lag_specs must cover both columns")
    check(specs[A21.TREATMENT_COL]["kind"] == "DERIVED_NO_JOIN", "x is DERIVED_NO_JOIN")
    check(specs[A21.NUISANCE_COL]["kind"] == "SCHEDULE", "is_playoff_game is a SCHEDULE fact")
    check(arm.lag_sources() == {}, "DERIVED_NO_JOIN/SCHEDULE declare no PRIOR_GAME source")
    return {"lag_kinds": {k: v["kind"] for k, v in specs.items()}}


def t11_depth_robustness_variant():
    """build_design_depth_robustness adds pace_evidence_depth to BOTH members' nuisance set,
    changes nothing else, and still nests correctly (secondary diagnostic per task_cards.A21)."""
    _, poss, uni, folds = _build()
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    base = arm.build_design(folds[0], uni)
    rob = arm.build_design_depth_robustness(folds[0], uni)
    check(rob["treatment_cols"] == base["treatment_cols"], "treatment set must be unchanged")
    check(set(rob["nuisance_cols"]) == set(base["nuisance_cols"]) | {A21.DEPTH_COL},
          "robustness variant must add EXACTLY pace_evidence_depth to the nuisance set")
    k0 = rob["k0_matched_design"]
    check(set(k0["nuisance_cols"]) == {A21.NUISANCE_COL, A21.DEPTH_COL},
          "the null's robustness variant must carry the same added nuisance term")
    check(np.array_equal(np.asarray(rob["columns"][A21.TREATMENT_COL]),
                         np.asarray(base["columns"][A21.TREATMENT_COL])),
          "x itself must be unchanged by the robustness variant")
    bval = ri.validate_design_bundle(rob, uni, arm.uses_global_intercept(),
                                     str(folds[0]["fold_id"]))
    check(bval["valid"], f"robustness design bundle must also validate: {bval}")
    return {"robustness_nuisance": sorted(rob["nuisance_cols"])}


def t12_kill_condition_hooks_decidable():
    """The card's kill_conditions_frozen, evaluated as a pure decision function: null-vs-K0
    interval-covers-zero kills; the depth-absorption robustness flag kills independently; either
    alone is sufficient; neither fires on genuine, zero-excluding evidence with a passing
    robustness check; a P25 rejection kills before any performance number."""
    both_cover_zero = {"f1": {"point": 0.02, "ci_low": -0.10, "ci_high": 0.15},
                       "f2": {"point": -0.01, "ci_low": -0.08, "ci_high": 0.06}}
    d1 = A21.decide_kill(both_cover_zero)
    check(d1["killed"] and d1["null_vs_k0_kill"] and not d1["depth_absorption_kill"],
          "interval-covers-zero-in-every-fold must kill via null_vs_k0")

    survives = {"f1": {"point": 0.20, "ci_low": 0.05, "ci_high": 0.35},
               "f2": {"point": 0.18, "ci_low": 0.02, "ci_high": 0.30}}
    d2 = A21.decide_kill(survives)
    check(not d2["killed"], "zero-excluding, consistent-sign evidence with no depth absorption "
                            "must NOT kill")

    d3 = A21.decide_kill(survives, depth_absorption_check_failed=True)
    check(d3["killed"] and d3["depth_absorption_kill"] and not d3["null_vs_k0_kill"],
          "the depth-absorption robustness check must be able to kill on its own, even when the "
          "naive null-vs-K0 test passes (mechanism falsified even on a positive naive test)")

    d4 = A21.decide_kill({}, p25_rejected=True)
    check(d4["killed"] and d4["reason"] == "p25_rejection",
          "a P25 rejection at invocation must kill before any performance number is consulted")

    expect_raises(ValueError, lambda: A21.decide_kill({"f1": {"point": 0, "ci_low": 1,
                                                              "ci_high": -1}}),
                  "a malformed interval (lo > hi) must be refused, not silently decided")
    return {"decisions": [d1["reason"], d2["reason"], d3["reason"], d4["reason"]]}


def t13_end_to_end_synthetic():
    """Full synthetic exercise of the shared runner against this arm module: blinding, guard byte
    pins, conformance, P26-before-P25, per-fold P22/P25, P27, paired point fits, test bootstrap,
    train-refit bootstrap, K0_FLAT diagnostic, receipt -- all on synthetic rows only."""
    _, poss, uni, folds = _build()
    basis = fx.build_prohibited_basis(uni)
    arm = A21.A21Arm(poss, [f["fold_id"] for f in folds], len(uni))
    out_path = HERE / "artifacts" / "A21_receipt.json"
    out_path.parent.mkdir(exist_ok=True)
    t0 = time.time()
    rec = rn.run_arm(arm, uni, folds, prohibited_basis=basis, env={},
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
    rec2 = rn.run_arm(arm, uni, folds, prohibited_basis=basis, env={}, run_git=False)
    import receipts as rp
    d1 = rp.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = rp.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: the runner must refuse a frame carrying a real D006 fold id, flag absent
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, uni, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED")
    check(rc.UNSEAL_ENV_FLAG not in os.environ, "flag must remain absent from the real environment")

    return {"seconds": round(dt, 2), "evaluable_folds": rec["results"]["evaluable_folds"],
           "results_digest": d1,
           "note": "synthetic-only numbers; no real fold or real MAE was touched"}


def t14_arm_d_untouched_and_ownership():
    """Sanity: this unit writes nothing outside arms/A21/, never reads SEALED_RESULTS, and never
    opens/imports the incumbent Arm D implementation."""
    for fname in ("arm_a21.py", "feature_construction.py"):
        src = (ARM_DIR / fname).read_text(encoding="utf-8")
        check("SEALED_RESULTS" not in src, f"{fname} must never reference SEALED_RESULTS")
        import ast
        tree = ast.parse(src)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module)
        check(not any("ewma" in n.lower() or "arm_d" in n.lower() for n in imported_names),
              f"{fname} must not import any Arm D / D_ewma_shrunk implementation: {imported_names}")
    for p in ARM_DIR.rglob("*"):
        check(str(p.resolve()).startswith(str(ARM_DIR.resolve())),
              f"write scope violation: {p}")
    return {"ownership_ok": True}


TESTS = [t01_conformance, t02_enumeration_element_exact, t03_feature_determinism,
        t04_strict_lagging, t05_empty_prior_set_imputation, t06_arm_vs_null_nesting,
        t07_p26_record_valid, t08_strict_lagging_p22, t09_franchise_continuity_receipt,
        t10_optional_hooks_shape, t11_depth_robustness_variant,
        t12_kill_condition_hooks_decidable, t13_end_to_end_synthetic,
        t14_arm_d_untouched_and_ownership]


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
        "schema": "p36_arm_a21_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "arm_id": "A21_garbage_time_contamination",
        "n_tests": len(TESTS), "passed": passed, "failed": failed,
        "unseal_flag_present": rc.UNSEAL_ENV_FLAG in os.environ,
        "results": RESULTS,
    }
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "A21_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (ARM_DIR / "A21_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\n{passed}/{len(TESTS)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
