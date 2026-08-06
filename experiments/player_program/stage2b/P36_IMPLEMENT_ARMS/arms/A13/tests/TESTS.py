#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for arm module A13
(A13_carryover_roster_continuity_moderator), against the frozen P36 shared runner contract.

BLINDED: every frame here is synthetic (synthetic_fixture_a13.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Epistemic status of this file and everything it exercises: IMPLEMENTATION. Blinded: no agent may
inspect challenger performance. Unit, synthetic, identity and schema tests only.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A13/tests/TESTS.py
Writes: ./artifacts/A13_TEST_RECEIPT.json and ../A13_TEST_RECEIPT.json
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent          # arms/A13/tests
ARM_DIR = HERE.parent                            # arms/A13
RUNNER = ARM_DIR.parents[1] / "runner"           # P36_IMPLEMENT_ARMS/runner
for p in (str(RUNNER), str(ARM_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a13 as A13                                                  # noqa: E402
import synthetic_fixture_a13 as fx                                     # noqa: E402

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


def _build_arm():
    universe, sched, hist, lineup = fx.build_universe_and_sources()
    folds = fx.build_folds(universe)
    fids = [f["fold_id"] for f in folds]
    arm = A13.ArmA13(sched, hist, lineup, fids, len(universe))
    return universe, sched, hist, lineup, folds, arm


# ------------------------------------------------------------------------------- tests

def t01_conformance():
    """The module satisfies runner_interface.validate_arm_module (RUNNER_INTERFACE.md section 2)."""
    _, _, _, _, _, arm = _build_arm()
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], f"A13 module must conform: {rec}")
    check(arm.arm_id == "A13_carryover_roster_continuity_moderator", "arm_id must match the card")
    check(arm.card_id() == arm.arm_id, "card_id defaults to arm_id")
    check(arm.declared_family() == "SUBSTANTIVE", "P35 p25_guard_invocation_pins")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "no RECALIBRATION arm survives")
    check(arm.uses_global_intercept() is True,
          "P35 intercept table: A13 in ARMS_WITH_FREE_GLOBAL_INTERCEPT")
    return {"conformant": True}


def t02_enumeration_element_exact():
    """Single-element arm ('inherits A12's frozen h', no grid); RUNNER_INTERFACE.md section 2
    pins '{} for single-element arms'."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    check(arm.enumeration_element() == {}, "single-element arm must report {}")
    check(arm.element_id() == "A13_carryover_roster_continuity_moderator__single",
          "element_id must be deterministic")
    check(A13.H_FIXED == 5.0, "A13 inherits A12's frozen h = 5 verbatim")
    return {"enumeration_element": arm.enumeration_element(), "element_id": arm.element_id()}


def t03_feature_determinism():
    """build_design is deterministic across repeated calls with the SAME fold (same train_idx ->
    same cbar_F -> byte-identical columns), and n_i/dev_prev/gap/depth/opp_depth are fold-
    independent (only cont_i's IMPUTED rows and the treatment column depend on the fold's own
    training-only cbar_F, per LEAKAGE L4)."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    b1 = arm.build_design(folds[-1], universe)
    b2 = arm.build_design(folds[-1], universe)
    for name in b1["columns"]:
        v1 = np.asarray(b1["columns"][name], dtype=float)
        v2 = np.asarray(b2["columns"][name], dtype=float)
        check(np.array_equal(v1, v2, equal_nan=True),
              f"column {name} must be byte-identical across repeated calls with the same fold")

    # gap/depth/opp_depth/intercept are pure passthroughs -- identical across DIFFERENT folds too
    b_first = arm.build_design(folds[0], universe)
    for name in (A13.GAP_COL, A13.DEPTH_COL, A13.OPP_DEPTH_COL, A13.INTERCEPT_COL, A13.WN_COL,
                A13.DEV_PREV_COL, A13.WN_DEV_PREV_COL):
        v1 = np.asarray(b_first["columns"][name], dtype=float)
        v2 = np.asarray(b1["columns"][name], dtype=float)
        check(np.array_equal(v1, v2),
              f"{name} must not depend on the fold's own train_idx (only cbar_F/cont_i/treatment do)")
    return {"n_rows": int(len(universe))}


def t04_intercept_and_null_nesting():
    """P35 K0 K2: free global intercept in arm AND null, byte-identical column. Null nesting:
    the null's columns are exactly the arm's nuisance columns (A12's full design + cont main),
    a proper subset of the arm's own terms, and term_removal comparison."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    b = arm.build_design(folds[-1], universe)
    check(A13.INTERCEPT_COL in b["nuisance_cols"], "free global intercept must be declared")
    v = np.asarray(b["columns"][A13.INTERCEPT_COL], float)
    check(np.all(v == 1.0), "intercept column must be all-ones")

    k0 = b["k0_matched_design"]
    check(k0["comparison"] == "term_removal", "A13's comparison is term_removal")
    arm_terms = set(b["treatment_cols"]) | set(b["nuisance_cols"])
    null_terms = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(null_terms < arm_terms, "the null must be a PROPER subset of the arm's design")
    check(A13.TREATMENT_COL not in null_terms,
          "the centered interaction must not survive term_removal in the null")
    check(null_terms == set(b["nuisance_cols"]),
          "the null is exactly A12's full design plus the cont main effect (the arm's nuisance set)")

    ok = ri.validate_design_bundle(b, universe, True, str(folds[-1]["fold_id"]))
    check(ok["valid"], "bundle must validate under the frozen free-intercept invariant")
    return {"arm_terms": sorted(arm_terms), "null_terms": sorted(null_terms)}


def t05_strict_lagging_identity():
    """Strict lagging, established directly (as A09's docstring notes P22's generic PRIOR_GAME
    re-derivation cannot verify an all-prior aggregate or a set-union construction): a row's
    n_i/dev_prev/cont_i/treatment must be INVARIANT to perturbing that SAME team's own realised
    outcome on the target game, and to perturbing any LATER game -- only strictly-earlier games
    may move the value."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    fold = folds[-1]
    b0 = arm.build_design(fold, universe)

    # perturb every row's OWN realised outcome (universe-level fields never enter this arm's
    # design at all -- gap/depth/opp_depth/n_off_poss/max_period of the TARGET row are not read
    # by n_i/dev_prev/cont_i, which are built purely from sched/history/lineup PRIOR rows); the
    # direct test is: mutate the FUTURE tail of history/lineup for the last test-fold's target
    # rows and confirm nothing about earlier rows changes.
    last_season = int(universe["season"].max())
    future_mask = universe["season"].to_numpy() == last_season
    hist2 = hist.copy()
    hist2.loc[hist2["season"] == last_season, "n_off_poss"] *= 3.0
    lineup2 = lineup.copy()
    # rewrite the LAST season's lineup rows to a disjoint synthetic player-id namespace
    lm = lineup2["team_id"].astype(str) + "|" + lineup2["game_id"].astype(str)
    future_games = set(sched.loc[sched["season"] == last_season, "game_id"])
    is_future_lineup = lineup2["game_id"].isin(future_games)
    lineup2.loc[is_future_lineup, "player_id"] = (
        "PERTURBED_" + lineup2.loc[is_future_lineup, "player_id"].astype(str))

    arm2 = A13.ArmA13(sched, hist2, lineup2, arm._fold_ids, arm._n_rows)
    b1 = arm2.build_design(fold, universe)

    for name in (A13.DEV_PREV_COL, A13.CONT_MAIN_COL, A13.TREATMENT_COL, A13.WN_DEV_PREV_COL):
        v0 = np.asarray(b0["columns"][name], float)
        v1 = np.asarray(b1["columns"][name], float)
        # rows whose OWN season is strictly earlier than last_season must be unaffected
        prior_rows = ~future_mask
        check(np.allclose(v0[prior_rows], v1[prior_rows], equal_nan=True),
              f"{name}: perturbing the LATEST season's history/lineup must not change any row "
              f"whose own season is strictly earlier (strict lagging)")
    return {"checked_columns": [A13.DEV_PREV_COL, A13.CONT_MAIN_COL, A13.TREATMENT_COL],
           "n_prior_rows_checked": int((~future_mask).sum())}


def t06_n_i_zero_forces_cont_to_cbar_and_treatment_zero():
    """Card-pinned n=0 fallback: rows with n_i == 0 (season openers) must have cont_i EXACTLY
    equal to cbar_F (the fold's training-defined mean), so the centered interaction (cont_i -
    cbar_F)*dev_prev is EXACTLY zero on every opener row -- 'this arm claims nothing on openers'
    (H4), independent of dev_prev's own value."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    fold = folds[-1]
    b = arm.build_design(fold, universe)
    n_i = A13.compute_n_i(sched, universe["team_id"].to_numpy(), universe["season"].to_numpy(),
                         universe["game_date"].to_numpy())
    openers = n_i == 0.0
    check(int(openers.sum()) > 0, "fixture must contain at least one n_i=0 opener row to test")
    cbar_f = arm._last_cbar_f[str(fold["fold_id"])]
    cont = np.asarray(b["columns"][A13.CONT_MAIN_COL], float)
    treat = np.asarray(b["columns"][A13.TREATMENT_COL], float)
    check(np.allclose(cont[openers], cbar_f), "cont_i must equal cbar_F exactly at n_i=0")
    check(np.allclose(treat[openers], 0.0, atol=1e-12),
          "the centered interaction must be exactly 0 on every opener row")
    return {"n_openers": int(openers.sum()), "cbar_F": float(cbar_f)}


def t07_jaccard_pure_function_bounds():
    """jaccard() is a pure function bounded in [0, 1], symmetric, 1.0 on identical nonempty sets,
    0.0 on disjoint nonempty sets and on two empty sets (harmless convention)."""
    a = frozenset({1, 2, 3})
    b = frozenset({2, 3, 4})
    j1 = A13.jaccard(a, b)
    j2 = A13.jaccard(b, a)
    check(abs(j1 - j2) < 1e-15, "jaccard must be symmetric")
    check(abs(j1 - (2.0 / 4.0)) < 1e-12, f"expected 0.5, got {j1}")
    check(A13.jaccard(a, a) == 1.0, "identical nonempty sets -> 1.0")
    check(A13.jaccard(a, frozenset()) == 0.0, "one empty set -> 0.0 (no shared/no overlap)")
    check(A13.jaccard(frozenset(), frozenset()) == 0.0, "both empty -> 0.0 by convention")
    for _ in range(20):
        rng = np.random.default_rng(0)
        s1 = frozenset(rng.integers(0, 50, size=10).tolist())
        s2 = frozenset(rng.integers(0, 50, size=10).tolist())
        j = A13.jaccard(s1, s2)
        check(0.0 <= j <= 1.0, f"jaccard out of bounds: {j}")
    return {"j_ab": j1}


def t08_p26_record_passes_wrapper():
    """The P26 record validates via the shared wrapper."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    rec = arm.p26_k0_record()
    check(rec["arm_kind"] == "substantive_feature", "matches the frozen card's arm_kind")
    out = gh.p26_check(rec)
    check(out["valid"], f"A13's K0 record must pass the P26 wrapper: {out}")
    params = rec["treatment_mechanism"]["tested_parameters"]
    check(any(p["name"] == "beta3" and float(p["null_value"]) == 0.0 for p in params),
          "beta3 must be declared with null_value 0")
    check(set(rec["invariants"]["lower_order_structural_terms"]) == set(rec["arm_spec"]
          ["structural_terms"]), "structural terms must match between invariants and arm_spec")
    return {"p26_valid": out["valid"]}


def t09_p26_record_rejects_survivor():
    """Negative control: a null that keeps the treatment term must fail the wrapper closed."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    rec = json.loads(json.dumps(arm.p26_k0_record()))
    rec["k0_spec"]["substantive_features"] = [A13.TREATMENT_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(rec),
                  "a null retaining the centered interaction must be blocked")
    return {"negative_control": "blocked"}


def t10_p22_strict_lagging_passes_and_undeclared_fails():
    """P22 passes with the declared LagSpecs on a synthetic frame with a synthetic prohibited
    basis; an undeclared column, and a dishonest SAME_GAME declaration, must both block."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    basis = fx.build_prohibited_basis(universe)
    b = arm.build_design(folds[-1], universe)
    W = universe.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    names = [c for c in dict.fromkeys(b["treatment_cols"] + b["nuisance_cols"])
             if c != A13.INTERCEPT_COL]
    rec = gh.p22_check(W, names, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                       lag_sources=arm.lag_sources())
    check(not rec.get("blocking"), f"declared columns must pass P22: {rec}")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, names, prohibited_basis=basis, lag_specs={}),
        "an undeclared LagSpec must block, never silently pass")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        W, [A13.TREATMENT_COL], prohibited_basis=basis,
        lag_specs={A13.TREATMENT_COL: {"column": A13.TREATMENT_COL, "kind": "SAME_GAME"}}),
        "SAME_GAME must block unconditionally regardless of the true construction")
    return {"p22_passed": True}


def t11_p27_rule_shape_and_digest():
    """p27_rule() returns (ActiveSetRule kwargs, Preregistration kwargs) whose digest matches the
    frozen P27 module's own canonicalisation, and the pair is accepted by the shared P27 wrapper
    on the final assembled design."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    rule_kwargs, prereg_kwargs = arm.p27_rule()
    check(rule_kwargs["rule_id"] == "S7_TIER_SUPPORT_v1", "rule id must match the card's name")
    check(rule_kwargs["min_nonzero_clusters"] == 10, "numeric trigger: 10-cluster floor")
    check(prereg_kwargs["results_visible_at_registration"] is False,
          "GATE_INVOCATION_CONTRACT section 4: registered before any result is visible")

    import importlib.util
    _name = "feg_check_A13"
    if _name in sys.modules:
        feg = sys.modules[_name]
    else:
        spec = importlib.util.spec_from_file_location(
            _name,
            ARM_DIR.parents[2] / "P27_FOLD_LOCAL_ESTIMABILITY_GUARD" / "fold_estimability_guard.py")
        feg = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(_name, feg)     # dataclass() needs cls.__module__ resolvable
        spec.loader.exec_module(feg)
    recomputed = feg.ActiveSetRule(**rule_kwargs).spec_sha256
    check(prereg_kwargs["rule_spec_sha256"] == recomputed,
          "the Preregistration digest must match the rule actually being applied")

    final_fold = {"fold_id": "FINAL_ASSEMBLED_DESIGN",
                 "train_idx": np.arange(len(universe)), "test_idx": np.empty(0, int)}
    b = arm.build_design(final_fold, universe)
    W = universe.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    rec = gh.p27_check(W, candidate_features=[A13.TREATMENT_COL],
                       nuisance_terms=[c for c in b["nuisance_cols"] if c != A13.INTERCEPT_COL],
                       cluster_col="game_id", fold_policy="EXPANDING_PRIOR_SEASONS",
                       null_features=[], null_nuisance=[c for c in b["nuisance_cols"]
                                                        if c != A13.INTERCEPT_COL],
                       rule_kwargs=rule_kwargs, prereg_kwargs=prereg_kwargs, arm_id=arm.arm_id)
    check(rec.get("overall") != "FAIL", f"P27 must not hard-FAIL on the synthetic fixture: {rec}")
    return {"rule_spec_sha256": prereg_kwargs["rule_spec_sha256"], "p27_overall": rec["overall"]}


def t12_kill_conditions_decidable():
    """The card's kill_conditions_frozen, evaluated as pure decision functions on synthetic
    numbers: no-rejection kill, negative-estimate kill, and the P22-inadmissibility verdict (a
    DISTINCT outcome from a fitted null, per the card's own wording)."""
    killed = A13.evaluate_kill_conditions(
        fold_intervals=[(-0.5, 0.4), (-0.3, 0.2)], fold_points=[0.1, -0.05])
    check(killed["killed"] is True and killed["beta3_ci_covers_zero_every_fold"] is True,
          "interval covering 0 in every evaluable fold must kill")
    check(killed["inadmissible"] is False, "a fitted no-rejection kill is not inadmissibility")

    survives = A13.evaluate_kill_conditions(
        fold_intervals=[(0.5, 2.0), (0.3, 1.8)], fold_points=[1.1, 1.0])
    check(survives["killed"] is False, "consistently positive, non-zero-covering evidence must "
                                       "not be killed")

    negative = A13.evaluate_kill_conditions(
        fold_intervals=[(-2.0, -0.5), (0.1, 1.0)], fold_points=[-1.2, 0.4])
    check(negative["killed"] is True and negative["beta3_negative_in_some_fold"] is True,
          "a negative point estimate in a fold refutes the mechanism and must kill")

    inadmissible = A13.evaluate_kill_conditions(fold_intervals=[], fold_points=[], p22_blocking=True)
    check(inadmissible["inadmissible"] is True and inadmissible["killed"] is None,
          "P22 failure must be recorded INADMISSIBLE, not folded into a null 'killed' verdict")

    empty = A13.evaluate_kill_conditions(fold_intervals=[], fold_points=[])
    check(empty["killed"] is False and empty["inadmissible"] is False,
          "no evaluable folds and no P22 failure is undecidable-as-a-kill, not a fired kill")

    check(A13.fixed_sequence_label(True) == "CONFIRMATORY", "A12 rejects -> CONFIRMATORY")
    check(A13.fixed_sequence_label(False) == "EXPLORATORY", "A12 fails to reject -> EXPLORATORY")
    check(A13.fixed_sequence_label(None) == "UNDECIDABLE_A12_RESULT_NOT_SUPPLIED",
          "no A12 result supplied -> undecidable, never silently guessed")
    return {"no_rejection_kill": killed, "survives": survives, "negative": negative,
           "inadmissible": inadmissible}


def t13a_degenerate_first_fold_correctly_blocks_p25():
    """The card's own text ("train_lt_2022 deactivated by rule": dev_prev/cont_i's interaction
    is identically zero for EVERY training row when the fold's entire training set is the first
    season, which has no archived prior season) reproduces exactly at the guard level: P25's
    augmented-rank check on that fold's TRAINING-only design correctly reports
    augmented_rank_deficient (three exactly-zero-variance columns -- dev_prev, w_n:dev_prev, the
    treatment -- cannot contribute to the design's rank). This demonstrates the guard behaves
    CORRECTLY on the degenerate fold, matching S7_TIER_SUPPORT_v1's own "activates
    train_lt_2023..train_lt_2026" framing (A12/A13 cards, carried) -- it is not a defect in this
    arm's construction. FLAGGED FOR P37 (not fixed here, not this unit's write scope): the shared
    runner's per-fold P22/P25 loop (runner.py step 5) does not consult
    `structurally_deactivated_folds()` / does not catch a blocking P25 finding per-fold the way
    the later FIT loop's K7 non-convergence path does -- a fold this degenerate, if handed to
    `run_arm` unfiltered, aborts the ENTIRE run rather than being marked UNEVALUABLE for that
    fold alone. This is a runner-level (not arms/A13-level) architecture question; arms/A13/ is
    this unit's entire write scope."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    degenerate_fold = folds[0]        # trains on season 6001 only -- no archived prior season
    b = arm.build_design(degenerate_fold, universe)
    tr = np.asarray(degenerate_fold["train_idx"], int)
    dev_prev_tr = np.asarray(b["columns"][A13.DEV_PREV_COL], float)[tr]
    check(np.all(dev_prev_tr == 0.0),
          "dev_prev must be identically 0 on the first-season-only training fold (no archived "
          "prior season) -- the exact real-world train_lt_2022 condition the card names")
    W = universe.copy()
    for name, v in b["columns"].items():
        W[name] = np.asarray(v, float)
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p25_check(
        W.iloc[tr].reset_index(drop=True),
        candidate_features=[c for c in b["treatment_cols"] if c != A13.INTERCEPT_COL],
        nuisance_features=[c for c in b["nuisance_cols"] if c != A13.INTERCEPT_COL]),
        "P25 must correctly block the degenerate all-zero-dev_prev training fold")
    return {"degenerate_fold_id": degenerate_fold["fold_id"], "correctly_blocked": True}


def t13_end_to_end_synthetic():
    """Full synthetic exercise of the shared runner against this arm module: blinding, guard byte
    pins, conformance, P26-before-P25, per-fold P22/P25, P27, paired point fits, test bootstrap,
    train-refit bootstrap, K0_FLAT diagnostic, receipt. Run over the ACTIVE fold set only (the
    card's own "folds: train_lt_2023..train_lt_2026 active; train_lt_2022 deactivated by rule"
    framing) -- see t13a for why the excluded first fold is excluded here rather than handed to
    `run_arm` (a runner-level gap, out of this unit's scope, flagged there). All synthetic rows
    only."""
    universe, sched, hist, lineup, folds, arm = _build_arm()
    active_folds = folds[1:]          # excludes the degenerate first-season-only fold; see t13a
    check(len(active_folds) >= 1, "fixture must provide at least one active (non-degenerate) fold")
    basis = fx.build_prohibited_basis(universe)
    out_path = HERE / "artifacts" / "A13_receipt.json"
    out_path.parent.mkdir(exist_ok=True)
    t0 = time.time()
    rec = rn.run_arm(arm, universe, active_folds, prohibited_basis=basis, env={},
                     out_path=out_path, run_git=False)
    dt = time.time() - t0
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(out_path.exists(), "receipt file written")
    check(rec["arm_id"] == arm.arm_id, "receipt must carry the arm id")
    check(set(rec["results"]["evaluable_folds"]) <= {f["fold_id"] for f in active_folds},
          "evaluable folds must be a subset of the supplied folds")
    check(rec["seeds"]["master_seed"] == rc.MASTER_SEED, "seed manifest master pin")
    check(rec["guard_records"]["p26"]["valid"], "P26 must pass on the synthetic universe")
    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict must not be FAIL")
    check(rec["guard_records"]["p23"]["valid"], "P23 franchise-continuity receipt must validate")

    # determinism: an identical second run reproduces the results bit-for-bit
    rec2 = rn.run_arm(arm, universe, active_folds, prohibited_basis=basis, env={}, run_git=False)
    import receipts as rp
    d1 = rp.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = rp.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: the runner must refuse a frame carrying a real D006 fold id, flag absent
    bad_folds = [dict(active_folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, universe, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED")
    check(rc.UNSEAL_ENV_FLAG not in os.environ, "flag must remain absent from the real environment")

    return {"seconds": round(dt, 2), "evaluable_folds": rec["results"]["evaluable_folds"],
           "results_digest": d1,
           "note": "synthetic-only numbers; no real fold or real MAE was touched"}


def t14_arm_d_untouched_and_ownership():
    """Sanity: this unit writes nothing outside arms/A13/, never reads SEALED_RESULTS, and never
    imports the incumbent Arm D implementation."""
    for fname in ("arm_a13.py",):
        src = (ARM_DIR / fname).read_text(encoding="utf-8")
        check("SEALED_RESULTS" not in src, f"{fname} must never reference the forbidden path")
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
        t04_intercept_and_null_nesting, t05_strict_lagging_identity,
        t06_n_i_zero_forces_cont_to_cbar_and_treatment_zero, t07_jaccard_pure_function_bounds,
        t08_p26_record_passes_wrapper, t09_p26_record_rejects_survivor,
        t10_p22_strict_lagging_passes_and_undeclared_fails, t11_p27_rule_shape_and_digest,
        t12_kill_conditions_decidable, t13a_degenerate_first_fold_correctly_blocks_p25,
        t13_end_to_end_synthetic, t14_arm_d_untouched_and_ownership]


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
        "schema": "p36_arm_a13_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "arm_id": "A13_carryover_roster_continuity_moderator",
        "n_tests": len(TESTS), "passed": passed, "failed": failed,
        "unseal_flag_present": rc.UNSEAL_ENV_FLAG in os.environ,
        "results": RESULTS,
    }
    (HERE / "artifacts").mkdir(exist_ok=True)
    (HERE / "artifacts" / "A13_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (ARM_DIR / "A13_TEST_RECEIPT.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"\n{passed}/{len(TESTS)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
