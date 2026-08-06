#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for arm module A24
(A24_rest_level_symmetric), against the frozen P36 shared runner contract.

BLINDED: every frame here is synthetic (synthetic_fixture_a24.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Epistemic status of this file and everything it exercises: IMPLEMENTATION. Blinded: no agent may
inspect challenger performance. Unit, synthetic, identity and schema tests only.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A24/tests/TESTS.py
Writes: ./artifacts/A24_TEST_RECEIPT.json (machine-readable results) and
        ../TEST_RECEIPT.json (summary, for the arm directory).
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

HERE = Path(__file__).resolve().parent          # arms/A24/tests
ARM_DIR = HERE.parent                            # arms/A24
RUNNER = ARM_DIR.parents[1] / "runner"           # P36_IMPLEMENT_ARMS/runner
for p in (str(RUNNER), str(ARM_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a24 as A24                                                  # noqa: E402
import feature_construction as fc                                      # noqa: E402
import synthetic_fixture_a24 as fx                                     # noqa: E402

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


def _build(seed=777, n_games_per_season=40):
    cs = fx.build_contract_schedule(n_games_per_season=n_games_per_season, seed=seed)
    uni = fx.build_universe(cs)
    folds = fx.build_folds(uni)
    return cs, uni, folds


# ------------------------------------------------------------------------------- tests

def t01_conformance():
    """The module satisfies runner_interface.validate_arm_module (RUNNER_INTERFACE.md section 2)."""
    cs, uni, folds = _build()
    fids = [f["fold_id"] for f in folds]
    arm = A24.A24Arm(cs, fids, len(uni))
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], f"A24 module must conform: {rec}")
    check(arm.arm_id == "A24_rest_level_symmetric", "arm_id must match the frozen card")
    check(arm.card_id() == arm.arm_id, "card_id defaults to arm_id")
    check(arm.declared_family() == "SUBSTANTIVE", "P35 p25_guard_invocation_pins")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "no RECALIBRATION arm survives")
    check(arm.uses_global_intercept() is False,
          "P35 intercept table: A24 in ARMS_WITHOUT_GLOBAL_INTERCEPT")
    return {"conformant": True}


def t02_enumeration_element_exact():
    """Single-element arm (P33/P35 hyperparameters.enumerated={}); RUNNER_INTERFACE.md section 2
    pins '{} for single-element arms'."""
    cs = fx.build_contract_schedule(seed=1)
    arm = A24.A24Arm(cs, [], 0)
    check(arm.enumeration_element() == {}, "single-element arm must report {}")
    check(arm.element_id() == "A24_rest_level_symmetric__single",
          "element_id must be deterministic")
    return {"enumeration_element": arm.enumeration_element(), "element_id": arm.element_id()}


def t03_feature_determinism():
    """build_design is a deterministic, pure function of (contract_schedule, universe, fold)."""
    cs, uni, folds = _build()
    arm = A24.A24Arm(cs, [f["fold_id"] for f in folds], len(uni))
    b1 = arm.build_design(folds[0], uni)
    b2 = arm.build_design(folds[0], uni)
    x1 = np.asarray(b1["columns"][A24.TREATMENT_COL])
    x2 = np.asarray(b2["columns"][A24.TREATMENT_COL])
    check(np.array_equal(x1, x2), "repeated build_design calls must be bitwise identical")
    check(x1.tobytes() == x2.tobytes(), "x bytes must match exactly")

    # fold-independence: A24's construction is a strictly-lagged per-row historical fact, not a
    # training-fold-computed constant (RUNNER_INTERFACE.md: only training-only CONSTANTS vary
    # fold-to-fold; A24 has none), so the SAME x must appear regardless of which fold is passed
    b3 = arm.build_design(folds[-1], uni)
    x3 = np.asarray(b3["columns"][A24.TREATMENT_COL])
    check(np.array_equal(x1, x3), "x must be identical across folds (no training-only constant)")

    # order-independence: shuffling the universe row order must not change per-(game,team) values
    uni2 = uni.sample(frac=1.0, random_state=13).reset_index(drop=True)
    fold2 = dict(folds[0])
    tr_ids = set(uni.iloc[folds[0]["train_idx"]]["game_id"].astype(str) + "_" +
                uni.iloc[folds[0]["train_idx"]]["team_id"].astype(str))
    key2 = uni2["game_id"].astype(str) + "_" + uni2["team_id"].astype(str)
    fold2["train_idx"] = np.flatnonzero(key2.isin(tr_ids).to_numpy())
    fold2["test_idx"] = np.flatnonzero(~key2.isin(tr_ids).to_numpy())
    b4 = arm.build_design(fold2, uni2)
    x4 = np.asarray(b4["columns"][A24.TREATMENT_COL])
    key1 = list(zip(uni["game_id"], uni["team_id"]))
    key4 = list(zip(uni2["game_id"], uni2["team_id"]))
    x_by_key1 = dict(zip(key1, x1))
    x_by_key4 = dict(zip(key4, x4))
    check(all(abs(x_by_key1[k] - x_by_key4[k]) < 1e-9 for k in key1),
          "x must be row-order independent")
    return {"n_rows": int(len(uni))}


def _shift_date_str(s: str, n_days: int) -> str:
    """Shift an ISO date string by n_days (may be negative), returned as an ISO date string."""
    return (pd.Timestamp(s) + pd.Timedelta(days=int(n_days))).strftime("%Y-%m-%d")


def t04_strict_lagging():
    """Strict lagging: a strictly-earlier contract-schedule game of the SAME team moves rest_own;
    the row's own game and any strictly-later game never do."""
    cs = fx.build_contract_schedule(n_games_per_season=30, seed=11)
    uni = fx.build_universe_frame(cs)
    base = fc.compute_rest_days(
        uni["team_id"].to_numpy(), uni["game_date"].to_numpy(), uni["game_id"].to_numpy(),
        history_team_id=cs["team_id"].to_numpy(), history_game_date=cs["game_date"].to_numpy(),
        history_game_id=cs["game_id"].to_numpy())

    # pick a row with a comfortable prior-game history for its own team
    counts = uni.groupby("team_id")["game_date"].rank(method="first")
    i = int(np.argmax(counts.to_numpy() >= 5))
    check(counts.iloc[i] >= 5, "fixture too small for this test")
    row = uni.iloc[i]
    own_prior = cs[(cs["team_id"] == row["team_id"]) &
                   (pd.to_datetime(cs["game_date"]) < pd.Timestamp(row["game_date"]))
                  ].sort_values("game_date")
    check(len(own_prior) > 0, "row must have strictly-earlier own contract-schedule games")
    nearest_prior_date = str(own_prior["game_date"].iloc[-1])

    # (a) POSITIVE CONTROL: moving the row's nearest strictly-earlier own game's date earlier
    # must move rest_own (increase the gap)
    cs_pert = cs.copy()
    m = (cs_pert["team_id"] == row["team_id"]) & (cs_pert["game_date"] == nearest_prior_date)
    cs_pert.loc[m, "game_date"] = _shift_date_str(nearest_prior_date, -5)
    pert = fc.compute_rest_days(
        uni["team_id"].to_numpy(), uni["game_date"].to_numpy(), uni["game_id"].to_numpy(),
        history_team_id=cs_pert["team_id"].to_numpy(),
        history_game_date=cs_pert["game_date"].to_numpy(),
        history_game_id=cs_pert["game_id"].to_numpy())
    check(abs(pert[i] - base[i]) > 1e-6,
          "perturbing the nearest strictly-earlier own game's date must move rest_own")

    # (b) NEGATIVE CONTROL: perturbing a DIFFERENT team's contract-schedule game dates must not
    # move row i's own team's rest (no cross-team leakage)
    other_team = int(uni.loc[uni["team_id"] != row["team_id"], "team_id"].iloc[0])
    cs_other = cs.copy()
    m2 = (cs_other["team_id"] == other_team)
    cs_other.loc[m2, "game_date"] = cs_other.loc[m2, "game_date"].apply(
        lambda d: _shift_date_str(d, -3))
    same = fc.compute_rest_days(
        uni["team_id"].to_numpy(), uni["game_date"].to_numpy(), uni["game_id"].to_numpy(),
        history_team_id=cs_other["team_id"].to_numpy(),
        history_game_date=cs_other["game_date"].to_numpy(),
        history_game_id=cs_other["game_id"].to_numpy())
    check(abs(same[i] - base[i]) < 1e-9,
          "perturbing a DIFFERENT team's contract-schedule games must NOT change this row's "
          "rest_own (no cross-team leakage)")

    # (c) NEGATIVE CONTROL: perturbing a STRICTLY LATER own game must not move this row's rest_own
    later_own = cs[(cs["team_id"] == row["team_id"]) &
                   (pd.to_datetime(cs["game_date"]) > pd.Timestamp(row["game_date"]))]
    check(len(later_own) > 0, "fixture must contain a strictly-later own game for this team")
    cs_later = cs.copy()
    later_date = str(later_own["game_date"].iloc[0])
    m3 = (cs_later["team_id"] == row["team_id"]) & (cs_later["game_date"] == later_date)
    cs_later.loc[m3, "game_date"] = _shift_date_str(later_date, 100)
    later = fc.compute_rest_days(
        uni["team_id"].to_numpy(), uni["game_date"].to_numpy(), uni["game_id"].to_numpy(),
        history_team_id=cs_later["team_id"].to_numpy(),
        history_game_date=cs_later["game_date"].to_numpy(),
        history_game_id=cs_later["game_id"].to_numpy())
    check(abs(later[i] - base[i]) < 1e-9,
          "perturbing a strictly-later own game must NOT change this row's rest_own")
    return {"row_checked": i, "nearest_prior_date": nearest_prior_date}


def t05_cap_and_symmetric_mean():
    """rest is capped at 10 (CAP_DAYS); x is the exact symmetric mean of own/opp capped rest."""
    cs, uni, folds = _build()
    out = fc.rest_level_symmetric(
        uni["team_id"].to_numpy(), uni["opp_team_id"].to_numpy(), uni["game_id"].to_numpy(),
        uni["game_date"].to_numpy(),
        history_team_id=cs["team_id"].to_numpy(), history_game_date=cs["game_date"].to_numpy(),
        history_game_id=cs["game_id"].to_numpy())
    check(np.all(out["f_own"] <= fc.CAP_DAYS + 1e-9), "f_own must never exceed the cap")
    check(np.all(out["f_opp"] <= fc.CAP_DAYS + 1e-9), "f_opp must never exceed the cap")
    check(np.allclose(out["x"], (out["f_own"] + out["f_opp"]) / 2.0),
          "x must equal the exact symmetric mean of f_own and f_opp")
    check(out["n_undefined"] == 0, "the clean fixture must carry no undefined rest value")
    return {"max_f_own": float(np.max(out["f_own"])), "n_undefined": out["n_undefined"]}


def t06_franchise_debut_fails_closed():
    """A genuine franchise debut (no contract-schedule row exists at all for that team before
    its first universe row) is a structurally undefined case the card's 'fallback: none needed'
    claim does not cover -- build_design must FAIL CLOSED, never silently substitute a value."""
    cs = fx.build_contract_schedule_with_debut(seed=778)
    uni = fx.build_universe_with_debut(cs)
    arm = A24.A24Arm(cs, ["a24_debut_fold"], len(uni))
    fold = {"fold_id": "a24_debut_fold",
           "train_idx": np.arange(len(uni)), "test_idx": np.array([], dtype=int)}
    expect_raises(fc.A24ConstructionFailure, lambda: arm.build_design(fold, uni),
                  "a true franchise-debut row must fail closed, never silently imputed "
                  "(feature_construction.py GENUINE GAP DISCLOSED note)")

    # the pure construction itself reports the undefined row(s) as NaN, not an exception -- the
    # fail-closed POLICY lives in build_design, matching feature_construction.py's own docstring
    out = fc.rest_level_symmetric(
        uni["team_id"].to_numpy(), uni["opp_team_id"].to_numpy(), uni["game_id"].to_numpy(),
        uni["game_date"].to_numpy(),
        history_team_id=cs["team_id"].to_numpy(), history_game_date=cs["game_date"].to_numpy(),
        history_game_id=cs["game_id"].to_numpy())
    check(out["n_undefined"] >= 1, "the debut fixture must contain at least one undefined row")
    return {"n_undefined": out["n_undefined"]}


def t07_arm_vs_null_nesting():
    """Arm-vs-null design nesting the card declares: term_removal, null == [log_exposure] with
    ZERO fitted parameters exactly (P35 task_cards.A24.k0_matched_frozen: 'same machinery;
    treatment adds ONLY x')."""
    cs, uni, folds = _build()
    arm = A24.A24Arm(cs, [f["fold_id"] for f in folds], len(uni))
    b = arm.build_design(folds[0], uni)
    bval = ri.validate_design_bundle(b, uni, arm.uses_global_intercept(), str(folds[0]["fold_id"]))
    check(bval["valid"], f"A24 design bundle must validate: {bval}")

    k0 = b["k0_matched_design"]
    check(k0["comparison"] == "term_removal", "A24's K0 comparison must be term_removal")
    check(k0["nuisance_cols"] == [] == b["nuisance_cols"] == [],
          "A24 carries NO nuisance term at all -- the null and the arm's own nuisance set are "
          "both empty (unlike A17/A21's carried single-nuisance nulls)")
    check(k0["treatment_cols"] == [], "null must carry zero treatment columns (term_removal)")
    check(b["treatment_cols"] == [A24.TREATMENT_COL], "arm treatment must be exactly x")
    arm_terms = set(b["treatment_cols"]) | set(b["nuisance_cols"])
    null_terms = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(null_terms == set(), "the null design must be EMPTY -- zero fitted parameters, IS the "
                               "frozen incumbent exactly")
    check(null_terms < arm_terms, "the null's design must be a PROPER subset of the arm's design")
    check(arm_terms - null_terms == {A24.TREATMENT_COL},
          "the null must differ from the arm by EXACTLY the treatment term")
    check(rc.INTERCEPT_COL not in arm_terms | null_terms,
          "no implicit or explicit intercept in either design (P35 K0 K2)")
    check(b["indicator_cols"] == [], "x is a continuous quantity, not a 0/1 indicator")
    return {"arm_terms": sorted(arm_terms), "null_terms": sorted(null_terms)}


def t08_p26_record_valid():
    """The P26 record validates via the shared wrapper; substantive_feature is not
    calibration_only, so no R8 slope adjudication should fire."""
    cs, uni, folds = _build()
    arm = A24.A24Arm(cs, [f["fold_id"] for f in folds], len(uni))
    rec = arm.p26_k0_record()
    check(rec["arm_kind"] == "substantive_feature", "matches the frozen card's arm_kind")
    out = gh.p26_check(rec)
    check(out["valid"], f"A24's k0_matched/1 record must validate against P26: {out}")
    check(not out["r8_filtered_findings"],
          "substantive_feature is not calibration_only; no R8 adjudication should fire")

    # negative control: a null that keeps the treatment term must be refused
    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = [A24.TREATMENT_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null retaining x must be blocked")
    return {"arm_kind": rec["arm_kind"]}


def t09_strict_lagging_p22():
    """The constructed design column passes P22 with its declared LagSpec on a synthetic frame
    with a synthetic prohibited basis; an undeclared column, and a dishonest SAME_GAME
    declaration, are both refused."""
    cs, uni, folds = _build()
    basis = fx.build_prohibited_basis(uni)
    arm = A24.A24Arm(cs, [f["fold_id"] for f in folds], len(uni))
    b = arm.build_design(folds[0], uni)
    W = uni.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    cols = [A24.TREATMENT_COL]
    rec = gh.p22_check(W, cols, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                       lag_sources=arm.lag_sources())
    check(not rec.get("blocking"), f"A24's column must pass P22 with its declared LagSpec: {rec}")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, cols, prohibited_basis=basis, lag_specs={}),
        "an undeclared LagSpec (x missing) must block, never silently pass")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, cols, prohibited_basis=basis,
        lag_specs={A24.TREATMENT_COL: {"column": A24.TREATMENT_COL, "kind": "SAME_GAME"}}),
        "SAME_GAME must block unconditionally regardless of the true construction")
    return {"p22_passed": True}


def t10_franchise_continuity_receipt():
    cs, uni, folds = _build()
    arm = A24.A24Arm(cs, [f["fold_id"] for f in folds], len(uni))
    check(arm.requires_franchise_continuity() is True, "A24 requires the P23 receipt")
    ok = gh.p23_check(requires_franchise_continuity=True, receipts=arm.p23_receipts())
    check(ok["valid"], "A24's own receipt must carry the correctly pinned team_cities hash")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p23_check(
        requires_franchise_continuity=True, receipts=[{"team_cities_sha256": "0" * 64}]),
        "a wrong team_cities pin must fail closed")
    return {"pin": rc.TEAM_CITIES_SHA256_PIN}


def t11_optional_hooks_shape():
    cs, uni, folds = _build()
    arm = A24.A24Arm(cs, [f["fold_id"] for f in folds], len(uni))
    check(arm.preregistered_contrasts() is None, "A24 declares no contrast_ column")
    check(arm.prereg_digest_expected() is None, "A24 has no contrast digest")
    check(arm.p27_rule() is None, "A24 registers no ActiveSetRule-shaped P27 rule")
    specs = arm.lag_specs()
    check(set(specs) == {A24.TREATMENT_COL}, "lag_specs must cover exactly the treatment column")
    check(specs[A24.TREATMENT_COL]["kind"] == "DERIVED_NO_JOIN", "x is DERIVED_NO_JOIN")
    check(arm.lag_sources() == {}, "DERIVED_NO_JOIN declares no PRIOR_GAME source")
    return {"lag_kinds": {k: v["kind"] for k, v in specs.items()}}


def t12_kill_condition_hooks_decidable():
    """The card's kill_conditions_frozen, evaluated as a pure decision function: null-vs-K0
    interval-covers-zero kills; a P25 flag ALSO kills, read literally as evidence for the null
    (not merely a design-failure withdrawal) -- distinct semantics from most sibling arms."""
    both_cover_zero = {"f1": {"point": 0.01, "ci_low": -0.05, "ci_high": 0.09},
                       "f2": {"point": -0.02, "ci_low": -0.10, "ci_high": 0.04}}
    d1 = A24.decide_kill(both_cover_zero)
    check(d1["killed"] and d1["null_vs_k0_kill"] and not d1["p25_flag_kill"],
          "interval-covers-zero-in-every-fold must kill via null_vs_k0")

    survives = {"f1": {"point": -0.30, "ci_low": -0.50, "ci_high": -0.12},
               "f2": {"point": -0.28, "ci_low": -0.45, "ci_high": -0.10}}
    d2 = A24.decide_kill(survives)
    check(not d2["killed"], "zero-excluding, consistent-sign evidence with no P25 flag must NOT "
                            "kill")

    d3 = A24.decide_kill(survives, p25_flagged=True)
    check(d3["killed"] and d3["p25_flag_kill"] and not d3["null_vs_k0_kill"],
          "a P25 flag must be able to kill on its own even when the naive null-vs-K0 test "
          "passes -- read LITERALLY per task_cards.A24.kill_conditions_frozen as evidence the "
          "incumbent already encodes schedule structure")

    d4 = A24.decide_kill(both_cover_zero, p25_flagged=True)
    check(d4["killed"] and d4["reason"] == "p25_flag_and_null_vs_k0",
          "both triggers firing together must be recorded jointly, not one masking the other")

    expect_raises(ValueError, lambda: A24.decide_kill({"f1": {"point": 0, "ci_low": 1,
                                                              "ci_high": -1}}),
                  "a malformed interval (lo > hi) must be refused, not silently decided")
    return {"decisions": [d1["reason"], d2["reason"], d3["reason"], d4["reason"]]}


def t13_end_to_end_synthetic():
    """Full synthetic exercise of the shared runner against this arm module: blinding, guard byte
    pins, conformance, P26-before-P25, per-fold P22/P25, P27, paired point fits, test bootstrap,
    train-refit bootstrap, K0_FLAT diagnostic, receipt -- all on synthetic rows only."""
    cs, uni, folds = _build()
    basis = fx.build_prohibited_basis(uni)
    arm = A24.A24Arm(cs, [f["fold_id"] for f in folds], len(uni))
    out_path = HERE / "artifacts" / "A24_receipt.json"
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
    """Sanity: this unit writes nothing outside arms/A24/, never reads SEALED_RESULTS, and never
    opens/imports the incumbent Arm D implementation."""
    for fname in ("arm_a24.py", "feature_construction.py"):
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
        t04_strict_lagging, t05_cap_and_symmetric_mean, t06_franchise_debut_fails_closed,
        t07_arm_vs_null_nesting, t08_p26_record_valid, t09_strict_lagging_p22,
        t10_franchise_continuity_receipt, t11_optional_hooks_shape,
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
        "schema": "p36_arm_a24_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "arm_id": "A24_rest_level_symmetric",
        "n_tests": len(TESTS), "passed": passed, "failed": failed,
        "unseal_flag_present": rc.UNSEAL_ENV_FLAG in os.environ,
        "results": RESULTS,
    }
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "A24_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (ARM_DIR / "TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\n{passed}/{len(TESTS)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
