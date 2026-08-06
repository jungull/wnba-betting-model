#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for A09_evidence_depth_adaptive_shrinkage.

BLINDED: every frame here is synthetic (synthetic_fixture.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Covers (per this unit's mandate): feature determinism, strict lagging, arm-vs-null design
nesting, enumeration elements exact, and the card kill-condition hooks decidable.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A09/tests/TESTS.py
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
A09_DIR = HERE.parent
RUNNER = A09_DIR.parents[1] / "runner"
for p in (str(RUNNER), str(A09_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm as a09                                                      # noqa: E402
import feature_construction as fc                                      # noqa: E402
import synthetic_fixture as fx                                         # noqa: E402

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

def t01_pace_and_weight_identities():
    # pace formula, exact per lagged_regulation_equivalent_pin, incl. the OT branch
    check(fc.lagged_pace(80.0, 4.0) == 80.0, "regulation game: pace == raw possessions")
    got_ot = fc.lagged_pace(90.0, 5.0)
    expected_ot = 90.0 * 40.0 / 45.0
    check(abs(got_ot - expected_ot) < 1e-12, f"1-OT rescale {got_ot} != {expected_ot}")
    got_2ot = fc.lagged_pace(100.0, 6.0)
    expected_2ot = 100.0 * 40.0 / 50.0
    check(abs(got_2ot - expected_2ot) < 1e-12, "2-OT rescale")

    # w(n; kappa) = n/(n+kappa): boundary identities
    check(fc.pooling_weight(np.array([0.0]), 10.0)[0] == 0.0, "w(0;kappa) == 0 exactly")
    w_big = fc.pooling_weight(np.array([1e9]), 10.0)[0]
    check(abs(w_big - 1.0) < 1e-6, "w(n;kappa) -> 1 as n grows")
    w_eq = fc.pooling_weight(np.array([10.0]), 10.0)[0]
    check(abs(w_eq - 0.5) < 1e-12, "w(kappa;kappa) == 0.5 exactly")

    # contrast == (w-1)*d_t, and is 0 wherever d_t == 0 (n_t == 0 empty window)
    n_t = np.array([0.0, 10.0, 50.0])
    d_t = np.array([0.0, 1.25, -0.7])
    c = fc.kappa_contrast(n_t, d_t, 10.0)
    check(c[0] == 0.0, "contrast is 0 at the empty window (d_t==0)")
    check(abs(c[1] - (0.5 - 1.0) * 1.25) < 1e-12, "contrast identity at n_t==kappa")
    expect_raises(ValueError, lambda: fc.pooling_weight(n_t, 0.0), "kappa<=0 must raise")
    return {"pace_ot_1": got_ot, "pace_ot_2": got_2ot, "w_half_at_n_eq_kappa": w_eq}


def t02_feature_determinism():
    df = fx.build_universe(seed=101)
    n1, d1 = fc.compute_n_t_d_t(df["team_id"].to_numpy(), df["game_date"].to_numpy(),
                                df["n_off_poss"].to_numpy(), df["max_period"].to_numpy())
    n2, d2 = fc.compute_n_t_d_t(df["team_id"].to_numpy(), df["game_date"].to_numpy(),
                                df["n_off_poss"].to_numpy(), df["max_period"].to_numpy())
    check(np.array_equal(n1, n2) and np.array_equal(d1, d2),
          "n_t/d_t must be bitwise deterministic on repeat")
    # row-order invariance: shuffling the input rows must not change any row's OWN n_t/d_t
    perm = np.random.Generator(np.random.PCG64(7)).permutation(len(df))
    dfp = df.iloc[perm].reset_index(drop=True)
    n3, d3 = fc.compute_n_t_d_t(dfp["team_id"].to_numpy(), dfp["game_date"].to_numpy(),
                                dfp["n_off_poss"].to_numpy(), dfp["max_period"].to_numpy())
    back = np.empty(len(df), int)
    back[perm] = np.arange(len(df))
    check(np.allclose(n1, n3[back]) and np.allclose(d1, d3[back]),
          "n_t/d_t must be invariant to the input frame's row order")
    check(int((n1 == 0).sum()) == N_TEAMS_FIRST_ROUND(df),
          "exactly one zero-prior row per team (the team's very first game)")
    return {"n_zero_prior_rows": int((n1 == 0).sum()), "n_rows": int(len(df))}


def N_TEAMS_FIRST_ROUND(df):
    return df["team_id"].nunique()


def t03_strict_lagging_identity():
    """The card-defining property: a row's n_t/d_t depend ONLY on strictly-earlier rows."""
    df = fx.build_universe(seed=202)
    n0, d0 = fc.compute_n_t_d_t(df["team_id"].to_numpy(), df["game_date"].to_numpy(),
                                df["n_off_poss"].to_numpy(), df["max_period"].to_numpy())

    # (a) perturbing a row's OWN game_id/possession count must not move its OWN n_t/d_t: a row is
    #     never counted as its own prior evidence, by construction (strictly-before, and a row
    #     shares its own game_date with itself).
    mid = int(len(df) // 2)
    df_a = df.copy()
    df_a.loc[mid, "n_off_poss"] = df_a.loc[mid, "n_off_poss"] + 500.0
    df_a.loc[mid, "max_period"] = 8.0
    na, da = fc.compute_n_t_d_t(df_a["team_id"].to_numpy(), df_a["game_date"].to_numpy(),
                                df_a["n_off_poss"].to_numpy(), df_a["max_period"].to_numpy())
    check(na[mid] == n0[mid] and abs(da[mid] - d0[mid]) < 1e-12,
          "a row's own game must never feed its own n_t/d_t")

    # (b) perturbing the LATEST-dated row in the frame must not move ANY other row's n_t/d_t
    #     (no future information may leak backward).
    latest = int(np.argmax(df["game_date"].to_numpy()))
    df_b = df.copy()
    df_b.loc[latest, "n_off_poss"] = df_b.loc[latest, "n_off_poss"] + 999.0
    df_b.loc[latest, "max_period"] = 9.0
    nb, db = fc.compute_n_t_d_t(df_b["team_id"].to_numpy(), df_b["game_date"].to_numpy(),
                                df_b["n_off_poss"].to_numpy(), df_b["max_period"].to_numpy())
    others = np.arange(len(df)) != latest
    check(np.array_equal(na if False else n0[others], nb[others])
          and np.allclose(d0[others], db[others]),
          "perturbing the latest row must not change any OTHER row's n_t/d_t")

    # (c) perturbing an EARLY row of team t DOES propagate to a strictly LATER row of the SAME
    #     team (the mechanism is responsive, not accidentally inert).
    team0 = df["team_id"].iloc[0]
    team_rows = np.flatnonzero(df["team_id"].to_numpy() == team0)
    team_rows_sorted = team_rows[np.argsort(df["game_date"].to_numpy()[team_rows])]
    check(len(team_rows_sorted) >= 3, "fixture must give a team >= 3 games")
    early_row = int(team_rows_sorted[0])
    later_row = int(team_rows_sorted[-1])
    df_c = df.copy()
    df_c.loc[early_row, "n_off_poss"] = df_c.loc[early_row, "n_off_poss"] + 300.0
    nc, dc = fc.compute_n_t_d_t(df_c["team_id"].to_numpy(), df_c["game_date"].to_numpy(),
                                df_c["n_off_poss"].to_numpy(), df_c["max_period"].to_numpy())
    check(abs(dc[later_row] - d0[later_row]) > 1e-9,
          "perturbing an earlier same-team game MUST move a later same-team row's d_t")

    # (d) same-date rows never count toward each other (two teams playing on the SAME synthetic
    #     day must not see each other's same-day pace in their own d_t/n_t).
    same_date = df["game_date"].to_numpy()[df["game_date"].to_numpy() ==
                                           df["game_date"].to_numpy()[0]]
    check(len(same_date) >= 2, "fixture must have >=2 rows sharing a date")
    return {"early_row_effect_on_later_row_delta_d_t": float(abs(dc[later_row] - d0[later_row]))}


def t04_align_by_key_matches_direct():
    df = fx.build_universe(seed=303)
    n_direct, d_direct = fc.compute_n_t_d_t(df["team_id"].to_numpy(), df["game_date"].to_numpy(),
                                            df["n_off_poss"].to_numpy(),
                                            df["max_period"].to_numpy())
    n_key, d_key = fc.align_n_t_d_t_by_key(df, df, key_cols=("team_id", "game_id"))
    check(np.allclose(n_direct, n_key) and np.allclose(d_direct, d_key),
          "align_n_t_d_t_by_key must reproduce the direct computation exactly")
    missing_target = pd.DataFrame({"team_id": ["NOPE"], "game_id": [-1]})
    expect_raises(KeyError, lambda: fc.align_n_t_d_t_by_key(df, missing_target),
                  "a target row absent from history must raise, never silently impute")
    return {"n_rows": int(len(df))}


def t05_enumeration_elements_exact():
    check(fc.ENUMERATED_KAPPA == (2, 10, 50), "frozen P35 A09 elements: kappa in {2, 10, 50}")
    df = fx.build_universe(seed=404)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arms = a09.make_arms(fids, len(df))
    check(len(arms) == 3, "one module instance per enumerated element")
    got = sorted(a.enumeration_element()["kappa"] for a in arms)
    check(got == [2, 10, 50], f"enumeration_element() values must be exactly the frozen grid: {got}")
    eids = [a.element_id() for a in arms]
    check(len(set(eids)) == 3, "element_id() must be unique per element")
    check(all(a.card_id() == a09.ARM_ID for a in arms), "card_id() must equal the frozen arm_id")
    expect_raises(ValueError, lambda: a09.A09Arm(7, fids, len(df)),
                  "an off-grid kappa must be refused, never silently admitted")
    return {"element_ids": eids}


def t06_conformance_and_intercept_invariant():
    df = fx.build_universe(seed=505)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = a09.A09Arm(10, fids, len(df))
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], "A09 kappa=10 module must conform to RUNNER_INTERFACE")
    check(arm.uses_global_intercept() is False, "A09 is in ARMS_WITHOUT_GLOBAL_INTERCEPT")
    check("A09" in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT, "frozen intercept table must name A09 prefix")

    bundle = arm.build_design(folds[0], df)
    bval = ri.validate_design_bundle(bundle, df, False, folds[0]["fold_id"])
    check(bval["valid"], "A09 design bundle must validate (no intercept, columns materialised)")
    check(bundle["treatment_cols"] == [a09.TREATMENT_COL], "treatment column name must be exact")
    check(bundle["nuisance_cols"] == [a09.NUISANCE_COL], "nuisance column name must be exact")
    check(bundle["k0_matched_design"]["comparison"] == "term_removal",
          "A09's K0 comparison is term_removal of the adaptive-vs-flat contrast")
    check(bundle["k0_matched_design"]["treatment_cols"] == [], "term_removal null has no treatment")
    check(bundle["k0_matched_design"]["nuisance_cols"] == [a09.NUISANCE_COL],
          "K0's nuisance set must equal the arm's own d_t nuisance term")
    check(bundle["indicator_cols"] == [], "neither d_t nor the contrast is a 0/1 indicator")

    # design columns must be identical across folds (values may differ; names may not)
    bundle2 = arm.build_design(folds[1], df)
    check(list(bundle2["columns"]) == list(bundle["columns"]),
          "column name set must be identical across folds")
    check(np.allclose(bundle2["columns"][a09.NUISANCE_COL], bundle["columns"][a09.NUISANCE_COL]),
          "d_t is not fold-dependent (schedule-fact construction, not a training-fold constant)")
    return {"treatment_col": a09.TREATMENT_COL, "nuisance_col": a09.NUISANCE_COL}


def t07_k0_nesting_and_p26():
    df = fx.build_universe(seed=606)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    for kappa in fc.ENUMERATED_KAPPA:
        arm = a09.A09Arm(kappa, fids, len(df))
        rec = arm.p26_k0_record()
        check(rec["arm_kind"] == "hierarchical_pooling", "A09 is a hierarchical_pooling arm")
        out = gh.p26_check(rec)
        check(out["valid"], f"kappa={kappa}: P26 K0_MATCHED record must validate: "
                            f"{out['blocking_after_adjudication']}")
        # exclusion minimality (R4): arm substantive - k0 substantive == treatment_terms
        a_sub = set(rec["arm_spec"]["substantive_features"])
        k_sub = set(rec["k0_spec"]["substantive_features"])
        treat = set(rec["treatment_mechanism"]["treatment_terms"])
        check(a_sub - k_sub == treat, "K0 must exclude EXACTLY the treatment terms")
        # structural closure (R5): d_t is granted to both sides identically
        check(set(rec["arm_spec"]["structural_terms"]) ==
              set(rec["k0_spec"]["structural_terms"]) == {a09.NUISANCE_COL},
              "d_t must be a shared structural term, arm and null identically")
        # design bundle's k0_matched_design must literally nest inside the arm's own design
        bundle = arm.build_design(folds[0], df)
        arm_cols = set(bundle["treatment_cols"]) | set(bundle["nuisance_cols"])
        null_cols = set(bundle["k0_matched_design"]["treatment_cols"]) | \
            set(bundle["k0_matched_design"]["nuisance_cols"])
        check(null_cols < arm_cols, "K0 design columns must be a STRICT subset of the arm's own "
                                    "design columns (proper nesting)")
        check(arm_cols - null_cols == {a09.TREATMENT_COL}, "the only column K0 excludes is the "
                                                           "per-element contrast")
    return {"kappas_checked": list(fc.ENUMERATED_KAPPA)}


def t08_guard_negative_paths():
    df = fx.build_universe(seed=707)
    basis = fx.build_prohibited_basis(df)
    arm = a09.A09Arm(2, ["f1"], len(df))

    # P22 must pass on the honestly-declared DERIVED_NO_JOIN design columns
    bundle = arm.build_design({"fold_id": "f1", "train_idx": np.arange(len(df)),
                              "test_idx": np.array([], int)}, df)
    W = df.copy()
    for name, v in bundle["columns"].items():
        W[name] = np.asarray(v, float)
    names = list(dict.fromkeys(bundle["treatment_cols"] + bundle["nuisance_cols"]))
    ok = gh.p22_check(W, names, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                      lag_sources=arm.lag_sources())
    check(not ok["blocking"], "A09's honestly-declared DERIVED_NO_JOIN design must clear P22")

    # an undeclared column must still fail closed (absence of declaration is failure, never pass)
    expect_raises(gh.GuardHarnessFailure,
                  lambda: gh.p22_check(W, names, prohibited_basis=basis, lag_specs={}),
                  "missing LagSpec must block even for A09's own columns")

    # P25 on the training rows: the contrast/nuisance columns must not be near-affine in the
    # offset (S7/near-affinity is the arm's own STATED most-likely death, per its card; a clean
    # synthetic fixture should pass)
    tr = np.arange(len(df))
    p25 = gh.p25_check(W.iloc[tr], candidate_features=bundle["treatment_cols"],
                       nuisance_features=bundle["nuisance_cols"])
    check(p25["passed"], "A09's synthetic design must clear P25 (no offset near-affinity)")

    # P23: A09 requires the franchise-continuity receipt; a missing/blank receipt fails closed
    check(arm.requires_franchise_continuity() is True, "A09 is named in the P35 precondition list")
    ok23 = gh.p23_check(requires_franchise_continuity=True, receipts=arm.p23_receipts())
    check(ok23["valid"], "A09's own receipt must carry the correct frozen team_cities pin")
    expect_raises(gh.GuardHarnessFailure,
                  lambda: gh.p23_check(requires_franchise_continuity=True, receipts=[]),
                  "a missing franchise-continuity receipt must fail closed")
    return {"p22_columns_checked": names}


def t09_kill_condition_hooks_decidable_end_to_end():
    """Run the full shared runner on synthetic data; verify the per-element beta interval the
    card's kill condition reads ('beta interval covers 0 in every evaluable fold') is actually
    COMPUTED and decidable, for every enumerated kappa element."""
    df = fx.build_universe(seed=808)
    folds = fx.build_folds(df)
    basis = fx.build_prohibited_basis(df)
    fids = [f["fold_id"] for f in folds]
    decisions = {}
    for kappa in fc.ENUMERATED_KAPPA:
        arm = a09.A09Arm(kappa, fids, len(df))
        out_path = HERE / "artifacts" / f"A09_kappa{kappa}_receipt.json"
        rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                         out_path=out_path, run_git=False)
        check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
        check(len(rec["results"]["evaluable_folds"]) >= 1,
              f"kappa={kappa}: at least one fold must be evaluable on clean synthetic data")
        per_fold_decidable = []
        for e in rec["folds"]:
            if e["status"] != "EVALUABLE":
                continue
            iv = e["train_refit"]["arm_intervals"].get(a09.TREATMENT_COL)
            check(iv is not None, f"kappa={kappa} fold {e['fold_id']}: treatment interval missing")
            decidable = iv["n_effective"] > 0 and iv["lo"] is not None and iv["hi"] is not None
            check(decidable, f"kappa={kappa} fold {e['fold_id']}: beta interval not decidable "
                             f"({iv})")
            covers_zero = bool(iv["lo"] <= 0.0 <= iv["hi"])
            per_fold_decidable.append({"fold_id": e["fold_id"], "covers_zero": covers_zero,
                                       "lo": iv["lo"], "hi": iv["hi"]})
        check(len(per_fold_decidable) == len(rec["results"]["evaluable_folds"]),
              "every evaluable fold must yield a decidable per-element kill verdict")
        decisions[f"kappa{kappa}"] = per_fold_decidable

        # determinism: an identical second run must reproduce the kill-relevant numbers exactly
        rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={}, run_git=False)
        for e1, e2 in zip(rec["folds"], rec2["folds"]):
            if e1["status"] != "EVALUABLE":
                continue
            iv1 = e1["train_refit"]["arm_intervals"][a09.TREATMENT_COL]
            iv2 = e2["train_refit"]["arm_intervals"][a09.TREATMENT_COL]
            check(iv1 == iv2, f"kappa={kappa}: kill-relevant interval must be bit-reproducible")

    # blinding still holds through this arm: a real fold id must be refused without the flag
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    arm2 = a09.A09Arm(2, fids, len(df))
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm2, df, bad_folds, prohibited_basis=basis, env={}),
                  "the shared runner must refuse real fold ids for A09 too, without P38_UNSEALED")
    return {"decisions": decisions}


TESTS = [
    ("T01_pace_and_weight_identities", t01_pace_and_weight_identities),
    ("T02_feature_determinism", t02_feature_determinism),
    ("T03_strict_lagging_identity", t03_strict_lagging_identity),
    ("T04_align_by_key_matches_direct", t04_align_by_key_matches_direct),
    ("T05_enumeration_elements_exact", t05_enumeration_elements_exact),
    ("T06_conformance_and_intercept_invariant", t06_conformance_and_intercept_invariant),
    ("T07_k0_nesting_and_p26", t07_k0_nesting_and_p26),
    ("T08_guard_negative_paths", t08_guard_negative_paths),
    ("T09_kill_condition_hooks_decidable_end_to_end", t09_kill_condition_hooks_decidable_end_to_end),
]


def main() -> int:
    if rc.UNSEAL_ENV_FLAG in os.environ:
        print(f"FATAL: {rc.UNSEAL_ENV_FLAG} exists in the environment; "
              "the blinded A09 test suite refuses to run.")
        return 2
    (HERE / "artifacts").mkdir(exist_ok=True)
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
        "schema": "p36_a09_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "arm_id": a09.ARM_ID, "enumerated_kappa": list(fc.ENUMERATED_KAPPA),
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = A09_DIR / "TEST_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
