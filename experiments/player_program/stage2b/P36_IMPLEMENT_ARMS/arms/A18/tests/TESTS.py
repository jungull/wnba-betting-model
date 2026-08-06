#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for A18_median_duration_contrast.

BLINDED: every frame here is synthetic (synthetic_fixture_a18.py); no real fold, no real MAE, no
comparative historical performance anywhere. The suite asserts the P38_UNSEALED flag is ABSENT
from the process environment and never sets it.

Covers (per this unit's mandate): feature determinism, strict lagging, arm-vs-null design
nesting, enumeration elements exact, and the card kill-condition hooks decidable.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A18/tests/TESTS.py
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
A18_DIR = HERE.parent
RUNNER = A18_DIR.parents[1] / "runner"
for p in (str(RUNNER), str(A18_DIR), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a18 as a18                                                  # noqa: E402
import feature_construction as fc                                      # noqa: E402
import synthetic_fixture_a18 as fx                                     # noqa: E402

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

def t01_feature_determinism():
    df = fx.build_universe(seed=101)
    poss = fx.build_possessions(df, seed=201)
    r1 = fc.compute_features(poss, df)
    r2 = fc.compute_features(poss, df)
    check(np.array_equal(r1["z1"], r2["z1"], equal_nan=True),
          "z1 must be bitwise deterministic on repeat")
    check(np.array_equal(r1["n_own"], r2["n_own"]) and np.array_equal(r1["n_opp"], r2["n_opp"]),
          "n_own/n_opp must be bitwise deterministic on repeat")

    # row-order invariance: shuffling the UNIVERSE rows must not change any row's OWN z1
    perm = np.random.Generator(np.random.PCG64(11)).permutation(len(df))
    dfp = df.iloc[perm].reset_index(drop=True)
    r3 = fc.compute_features(poss, dfp)
    back = np.empty(len(df), int)
    back[perm] = np.arange(len(df))
    check(np.allclose(r1["z1"], r3["z1"][back]),
          "z1 must be invariant to the universe frame's row order")

    # shuffling the POSSESSIONS rows must not change z1 either (pooled median is order-free)
    poss_perm = poss.sample(frac=1.0, random_state=13).reset_index(drop=True)
    r4 = fc.compute_features(poss_perm, df)
    check(np.allclose(r1["z1"], r4["z1"]),
          "z1 must be invariant to the possessions frame's row order")
    return {"n_rows": int(len(df)), "n_possessions": int(len(poss)),
            "n_imputed": int(np.sum(r1["imputed"]))}


def t02_strict_lagging_identity():
    """The card-defining property: z1(row) depends ONLY on possessions of STRICTLY EARLIER
    same-season games of the row's own team (or opponent)."""
    df = fx.build_universe(seed=202)
    poss = fx.build_possessions(df, seed=302)
    r0 = fc.compute_features(poss, df)

    # (a) perturbing possessions belonging to a row's OWN game_id must not move that row's OWN z1
    team0 = df["team_id"].iloc[0]
    own_game_id = int(df["game_id"].iloc[0])
    poss_a = poss.copy()
    mask_own_game = (poss_a["game_id"] == own_game_id) & (poss_a["offense_team_id"] == team0)
    check(mask_own_game.any(), "fixture must have possessions for the perturbed team's own game")
    poss_a.loc[mask_own_game, "duration_sec"] = poss_a.loc[mask_own_game, "duration_sec"] + 500.0
    ra = fc.compute_features(poss_a, df)
    row0 = 0
    check(df["team_id"].iloc[row0] == team0 and int(df["game_id"].iloc[row0]) == own_game_id,
          "test setup: row0 must be the perturbed team's own game row")
    check(abs(ra["z1"][row0] - r0["z1"][row0]) < 1e-9,
          "a row's own game's possessions must never feed its own z1")

    # (b) perturbing the LATEST-dated game's possessions must not move any EARLIER row's z1
    latest_gid = int(df.loc[df["game_date"].idxmax(), "game_id"])
    poss_b = poss.copy()
    mask_latest = poss_b["game_id"] == latest_gid
    check(mask_latest.any(), "fixture must have possessions for the latest game")
    poss_b.loc[mask_latest, "duration_sec"] = poss_b.loc[mask_latest, "duration_sec"] + 999.0
    rb = fc.compute_features(poss_b, df)
    earlier_rows = df["game_date"].to_numpy() < df["game_date"].max()
    check(np.allclose(r0["z1"][earlier_rows], rb["z1"][earlier_rows]),
          "perturbing the latest game's possessions must not change any strictly-earlier row's z1")

    # (c) perturbing an EARLY same-team same-season game's possessions DOES propagate to a
    #     strictly LATER same-team same-season row (the mechanism is responsive, not inert)
    team_rows = df[(df["team_id"] == team0) & (df["season"] == df["season"].iloc[0])]
    team_rows_sorted = team_rows.sort_values("game_date")
    check(len(team_rows_sorted) >= 4, "fixture must give a team >= 4 same-season games")
    early_gid = int(team_rows_sorted["game_id"].iloc[0])
    later_idx = int(team_rows_sorted.index[-1])
    poss_c = poss.copy()
    mask_early = (poss_c["game_id"] == early_gid) & (poss_c["offense_team_id"] == team0)
    check(mask_early.any(), "fixture must have possessions for the early perturbed game")
    poss_c.loc[mask_early, "duration_sec"] = poss_c.loc[mask_early, "duration_sec"] + 300.0
    rc_ = fc.compute_features(poss_c, df)
    check(abs(rc_["z1"][later_idx] - r0["z1"][later_idx]) > 1e-9,
          "perturbing an earlier same-team same-season game's possessions MUST move a later "
          "same-team row's z1 (unless the later row is E=3-imputed, which this fixture avoids "
          "by construction)")
    return {"early_row_effect_on_later_row_delta_z1":
            float(abs(rc_["z1"][later_idx] - r0["z1"][later_idx]))}


def t03_e3_imputation_exact():
    df = fx.build_universe(seed=303)
    poss = fx.build_possessions(df, seed=403)
    r = fc.compute_features(poss, df)
    check(fc.E_MIN_PRIOR_GAMES == 3, "frozen P33 E_min_prior_games pin")
    # every row flagged imputed must have z1 == 0.0 exactly
    check(np.all(r["z1"][r["imputed"]] == 0.0), "imputed rows must carry z1 == 0.0 exactly")
    # every row with BOTH sides >= 3 prior games must NOT be imputed
    both_ge3 = (r["n_own"] >= fc.E_MIN_PRIOR_GAMES) & (r["n_opp"] >= fc.E_MIN_PRIOR_GAMES)
    check(np.array_equal(both_ge3, ~r["imputed"]),
          "imputed must be true iff EITHER side has fewer than E_MIN_PRIOR_GAMES prior games")
    # a team's very first same-season game must always be imputed (n_own == 0 < 3)
    first_game_mask = df.groupby(["team_id", "season"])["game_date"].transform("min") == \
        df["game_date"]
    check(bool(np.all(r["imputed"][first_game_mask.to_numpy()])),
          "every team's first game of a season must be E=3-imputed")
    return {"n_imputed": int(np.sum(r["imputed"])), "n_rows": int(len(df))}


def t04_enumeration_element_exact_single():
    df = fx.build_universe(seed=404)
    poss = fx.build_possessions(df, seed=504)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arms = a18.make_arm(poss, fids, len(df))
    check(len(arms) == 1, "A18 has no enumerated grid: exactly one module instance")
    arm = arms[0]
    check(arm.enumeration_element() == {}, "single-element arm: enumeration_element() == {}")
    check(arm.element_id() == a18.ARM_ID, "element_id() must equal the frozen arm_id")
    check(arm.card_id() == a18.ARM_ID, "card_id() must equal the frozen arm_id")
    return {"element_id": arm.element_id()}


def t05_conformance_and_intercept_invariant():
    df = fx.build_universe(seed=505)
    poss = fx.build_possessions(df, seed=605)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = a18.A18Arm(poss, fids, len(df))
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], "A18 module must conform to RUNNER_INTERFACE")
    check(arm.uses_global_intercept() is False, "A18 is in ARMS_WITHOUT_GLOBAL_INTERCEPT")
    check("A18" in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT, "frozen intercept table must name A18")
    check(arm.requires_franchise_continuity() is False,
          "A18 is absent from the P33 franchise-continuity precondition arm list")

    bundle = arm.build_design(folds[0], df)
    bval = ri.validate_design_bundle(bundle, df, False, folds[0]["fold_id"])
    check(bval["valid"], "A18 design bundle must validate (no intercept, columns materialised)")
    check(bundle["treatment_cols"] == [a18.TREATMENT_COL], "treatment column name must be exact")
    check(bundle["nuisance_cols"] == [], "A18 requests no nuisance term (P33: 'no nuisance "
                                        "requested')")
    check(bundle["k0_matched_design"]["comparison"] == "term_removal",
          "A18's K0 comparison is term_removal")
    check(bundle["k0_matched_design"]["treatment_cols"] == [], "term_removal null has no "
                                                               "treatment")
    check(bundle["k0_matched_design"]["nuisance_cols"] == [],
          "A18's zero-parameter null carries no nuisance terms either -- it IS the incumbent")
    check(bundle["indicator_cols"] == [], "z1 is a continuous contrast, not a 0/1 indicator")

    # design columns must be identical across folds (values may differ; names may not)
    bundle2 = arm.build_design(folds[1], df)
    check(list(bundle2["columns"]) == list(bundle["columns"]),
          "column name set must be identical across folds")
    check(np.allclose(bundle2["columns"][a18.TREATMENT_COL], bundle["columns"][a18.TREATMENT_COL]),
          "z1 is not fold-dependent (schedule-fact construction, not a training-fold constant)")
    return {"treatment_col": a18.TREATMENT_COL}


def t06_k0_nesting_and_p26():
    df = fx.build_universe(seed=606)
    poss = fx.build_possessions(df, seed=706)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = a18.A18Arm(poss, fids, len(df))
    rec = arm.p26_k0_record()
    check(rec["arm_kind"] == "substantive_feature", "A18 is a substantive_feature arm")
    out = gh.p26_check(rec)
    check(out["valid"], f"A18 P26 K0_MATCHED record must validate: "
                        f"{out['blocking_after_adjudication']}")
    # exclusion minimality (R4): arm substantive - k0 substantive == treatment_terms
    a_sub = set(rec["arm_spec"]["substantive_features"])
    k_sub = set(rec["k0_spec"]["substantive_features"])
    treat = set(rec["treatment_mechanism"]["treatment_terms"])
    check(a_sub - k_sub == treat, "K0 must exclude EXACTLY the treatment terms")
    check(k_sub == set(), "A18's K0 substantive set must be empty (zero-parameter null)")

    # design bundle's k0_matched_design must literally nest inside the arm's own design
    bundle = arm.build_design(folds[0], df)
    arm_cols = set(bundle["treatment_cols"]) | set(bundle["nuisance_cols"])
    null_cols = set(bundle["k0_matched_design"]["treatment_cols"]) | \
        set(bundle["k0_matched_design"]["nuisance_cols"])
    check(null_cols < arm_cols, "K0 design columns must be a STRICT subset of the arm's own "
                                "design columns (proper nesting)")
    check(arm_cols - null_cols == {a18.TREATMENT_COL}, "the only column K0 excludes is z1")
    check(null_cols == set(), "A18's null design is empty: eta = log_exposure exactly")
    return {"arm_cols": sorted(arm_cols), "null_cols": sorted(null_cols)}


def t07_guard_negative_paths():
    df = fx.build_universe(seed=707)
    poss = fx.build_possessions(df, seed=807)
    basis = fx.build_prohibited_basis(df)
    arm = a18.A18Arm(poss, ["f1"], len(df))

    bundle = arm.build_design({"fold_id": "f1", "train_idx": np.arange(len(df)),
                              "test_idx": np.array([], int)}, df)
    W = df.copy()
    for name, v in bundle["columns"].items():
        W[name] = np.asarray(v, float)
    names = list(dict.fromkeys(bundle["treatment_cols"] + bundle["nuisance_cols"]))

    # P22 must pass on the honestly-declared DERIVED_NO_JOIN design column
    ok = gh.p22_check(W, names, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                      lag_sources=arm.lag_sources())
    check(not ok["blocking"], "A18's honestly-declared DERIVED_NO_JOIN design must clear P22")

    # an undeclared column must still fail closed (absence of declaration is failure, never pass)
    expect_raises(gh.GuardHarnessFailure,
                  lambda: gh.p22_check(W, names, prohibited_basis=basis, lag_specs={}),
                  "missing LagSpec must block even for A18's own column")

    # P25 on the training rows: z1 must not be near-affine in the offset on a clean synthetic
    # fixture (S7/near-affinity is the arm's own STATED withdrawal condition per its card)
    tr = np.arange(len(df))
    p25 = gh.p25_check(W.iloc[tr], candidate_features=bundle["treatment_cols"],
                       nuisance_features=bundle["nuisance_cols"])
    check(p25["passed"], "A18's synthetic design must clear P25 (no offset near-affinity)")

    # P23: A18 does NOT require franchise continuity; an empty receipt list must be accepted
    check(arm.requires_franchise_continuity() is False, "A18 is absent from the P33 precondition "
                                                        "list")
    ok23 = gh.p23_check(requires_franchise_continuity=False, receipts=arm.p23_receipts())
    check(ok23["valid"], "A18 requires no franchise-continuity receipt; an empty list must pass")
    return {"p22_columns_checked": names}


def t08_pace_gap_near_affinity_diagnostic():
    """near_affinity_against/decide_kill: the task-specific 'or pace_gap' kill-condition
    comparand the standard P25 invocation does not check (see arm_a18.py's kill-condition
    docstring). Pure measurement/decision functions, deterministic, no model fit."""
    rng = np.random.Generator(np.random.PCG64(909))
    n = 400
    z1 = rng.normal(size=n)
    unrelated = rng.normal(size=n)
    rep_offset = a18.near_affinity_against(z1, unrelated)
    check(rep_offset["near_affine"] is False, "unrelated columns must not be flagged near-affine")

    near_dup = z1 * 3.0 + 0.5 + rng.normal(scale=1e-6, size=n)   # near-exact affine transform
    rep_dup = a18.near_affinity_against(z1, near_dup)
    check(rep_dup["near_affine"] is True, "a near-exact affine transform must be flagged")

    # decide_kill: interval-covers-zero kill
    beta = {"f1": {"point": 0.01, "ci_low": -0.02, "ci_high": 0.03},
           "f2": {"point": -0.01, "ci_low": -0.04, "ci_high": 0.01}}
    dec = a18.decide_kill(beta)
    check(dec["interval_kill"] is True and dec["killed_or_withdrawn"] is True,
          "both-folds-cover-zero must kill")

    beta_ok = {"f1": {"point": 0.5, "ci_low": 0.1, "ci_high": 0.9},
              "f2": {"point": 0.4, "ci_low": 0.05, "ci_high": 0.8}}
    dec_ok = a18.decide_kill(beta_ok)
    check(dec_ok["interval_kill"] is False and dec_ok["killed_or_withdrawn"] is False,
          "excluding-zero-in-every-fold with no other trigger must not kill")

    dec_withdraw = a18.decide_kill(beta_ok, near_affinity_pace_gap_by_fold={"f1": True, "f2": True})
    check(dec_withdraw["is_withdrawal"] is True and dec_withdraw["killed_or_withdrawn"] is True,
          "pace_gap near-affinity in every fold must trigger the withdrawal path")
    return {"near_affine_unrelated": rep_offset["near_affine"],
           "near_affine_duplicate": rep_dup["near_affine"]}


def t09_kill_condition_hooks_decidable_end_to_end():
    """Run the full shared runner on synthetic data; verify the beta1 interval the card's kill
    condition reads ('cluster-resampled interval for beta1 covers 0') is actually COMPUTED and
    decidable."""
    df = fx.build_universe(seed=808)
    # give a real synthetic own-vs-opponent duration signal so the fixture is not degenerate
    bias = {f"SYN{k}": (k - 2.5) for k in range(fx.N_TEAMS)}
    poss = fx.build_possessions(df, seed=908, own_mean_bias=bias)
    folds = fx.build_folds(df)
    basis = fx.build_prohibited_basis(df)
    fids = [f["fold_id"] for f in folds]
    arm = a18.A18Arm(poss, fids, len(df))

    out_path = HERE / "artifacts" / "A18_receipt.json"
    rec = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                     out_path=out_path, run_git=False)
    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(len(rec["results"]["evaluable_folds"]) >= 1,
          "at least one fold must be evaluable on clean synthetic data")

    per_fold_decidable = []
    for e in rec["folds"]:
        if e["status"] != "EVALUABLE":
            continue
        iv = e["train_refit"]["arm_intervals"].get(a18.TREATMENT_COL)
        check(iv is not None, f"fold {e['fold_id']}: treatment interval missing")
        decidable = iv["n_effective"] > 0 and iv["lo"] is not None and iv["hi"] is not None
        check(decidable, f"fold {e['fold_id']}: beta1 interval not decidable ({iv})")
        per_fold_decidable.append({"fold_id": e["fold_id"],
                                   "covers_zero": bool(iv["lo"] <= 0.0 <= iv["hi"]),
                                   "lo": iv["lo"], "hi": iv["hi"]})
    check(len(per_fold_decidable) == len(rec["results"]["evaluable_folds"]),
          "every evaluable fold must yield a decidable beta1 kill verdict")

    beta_by_fold = {d["fold_id"]: {"point": (d["lo"] + d["hi"]) / 2.0, "ci_low": d["lo"],
                                   "ci_high": d["hi"]} for d in per_fold_decidable}
    decision = a18.decide_kill(beta_by_fold)
    check(decision["schema"] == "a18_kill_decision/1", "kill decision schema pin")

    # determinism: an identical second run must reproduce the kill-relevant numbers exactly
    rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={}, run_git=False)
    for e1, e2 in zip(rec["folds"], rec2["folds"]):
        if e1["status"] != "EVALUABLE":
            continue
        iv1 = e1["train_refit"]["arm_intervals"][a18.TREATMENT_COL]
        iv2 = e2["train_refit"]["arm_intervals"][a18.TREATMENT_COL]
        check(iv1 == iv2, "kill-relevant interval must be bit-reproducible")

    # blinding still holds through this arm: a real fold id must be refused without the flag
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    arm2 = a18.A18Arm(poss, fids, len(df))
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm2, df, bad_folds, prohibited_basis=basis, env={}),
                  "the shared runner must refuse real fold ids for A18 too, without P38_UNSEALED")
    return {"decision": decision, "per_fold": per_fold_decidable}


TESTS = [
    ("T01_feature_determinism", t01_feature_determinism),
    ("T02_strict_lagging_identity", t02_strict_lagging_identity),
    ("T03_e3_imputation_exact", t03_e3_imputation_exact),
    ("T04_enumeration_element_exact_single", t04_enumeration_element_exact_single),
    ("T05_conformance_and_intercept_invariant", t05_conformance_and_intercept_invariant),
    ("T06_k0_nesting_and_p26", t06_k0_nesting_and_p26),
    ("T07_guard_negative_paths", t07_guard_negative_paths),
    ("T08_pace_gap_near_affinity_diagnostic", t08_pace_gap_near_affinity_diagnostic),
    ("T09_kill_condition_hooks_decidable_end_to_end", t09_kill_condition_hooks_decidable_end_to_end),
]


def main() -> int:
    if rc.UNSEAL_ENV_FLAG in os.environ:
        print(f"FATAL: {rc.UNSEAL_ENV_FLAG} exists in the environment; "
              "the blinded A18 test suite refuses to run.")
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
        "schema": "p36_a18_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "arm_id": a18.ARM_ID, "enumerated_elements": "none (single-element arm)",
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = A18_DIR / "TEST_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
