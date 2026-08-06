#!/usr/bin/env python3
"""TESTS.py -- unit, synthetic, identity and schema tests for arm_a11.A11Arm (A11_carryover_
blend_rho).

BLINDED (P36 standing rules): every frame here is synthetic (synthetic_fixture_a11.py); no real
fold, no real MAE, no comparative historical performance anywhere. This suite never sets
P38_UNSEALED and asserts it is absent. The one real fold id this arm's card names
("train_lt_2022") is used ONLY as a bare string-equality check against
`structurally_deactivated_folds()` and, separately, to prove the blinded runner refuses it as an
actual fold id -- never to drive an actual fit.

Epistemic status: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A11/tests/TESTS.py
Writes: ../TEST_RECEIPT.json (machine-readable results), scoped to this arm's own directory.
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
RUNNER = ARM_DIR.parents[1] / "runner"
for p in (str(RUNNER), str(HERE), str(ARM_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import blinding                                                        # noqa: E402
import guard_harness as gh                                             # noqa: E402
import runner as rn                                                    # noqa: E402
import runner_constants as rc                                          # noqa: E402
import runner_interface as ri                                          # noqa: E402

import arm_a11 as A                                                    # noqa: E402
import feature_construction as feat                                    # noqa: E402
import synthetic_fixture_a11 as fx                                     # noqa: E402

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


# ------------------------------------------------------------------------------------- tests
def t01_p35_spec_hash_pin():
    import hashlib
    spec_path = ARM_DIR.parents[2] / "P35_FREEZE_TASK_CARDS" / "SPEC.json"
    got = hashlib.sha256(spec_path.read_bytes()).hexdigest()
    check(got == A.P35_SPEC_SHA256, f"P35 SPEC.json sha256 drifted: {got} != {A.P35_SPEC_SHA256}")
    return {"p35_spec_sha256": got}


def t02_feature_determinism_and_order_independence():
    hist = fx.build_universe()
    targets = hist[["team_id", "game_id"]].copy()
    f1 = feat.compute_features(hist, targets)
    f2 = feat.compute_features(hist, targets)
    for k in ("n_cur", "dcur", "m_prev", "dprev"):
        check(np.array_equal(f1[k], f2[k]), f"{k} must be bitwise deterministic")
        check(f1[k].tobytes() == f2[k].tobytes(), f"{k} bytes must match exactly")

    # order independence: shuffling the target row order must not change per-row values
    shuffled = targets.sample(frac=1.0, random_state=7).reset_index(drop=True)
    f3 = feat.compute_features(hist, shuffled)
    key1 = list(zip(targets["team_id"], targets["game_id"]))
    key3 = list(zip(shuffled["team_id"], shuffled["game_id"]))
    d1 = dict(zip(key1, f1["dcur"]))
    d3 = dict(zip(key3, f3["dcur"]))
    check(all(abs(d1[k] - d3[k]) < 1e-12 for k in key1), "dcur_t must be row-order independent")
    return {"n_rows": int(len(hist))}


def t03_strict_lagging_current_and_previous_season():
    hist = fx.build_universe(n_games_per_team_per_season=10, seed=13)
    targets = hist[["team_id", "game_id"]].copy()
    base = feat.compute_features(hist, targets)

    # pick a row deep enough in season 2 (index 1) to have both a same-season earlier game and a
    # (fully resolved) preceding season
    row_mask = (hist["season"].to_numpy() == fx.SEASONS[1]) & (base["n_cur"] >= 3)
    check(row_mask.any(), "fixture too small: need a season-2 row with n_cur>=3")
    i = int(np.flatnonzero(row_mask)[0])
    team_i, game_i, date_i = hist["team_id"].iloc[i], hist["game_id"].iloc[i], hist["game_date"].iloc[i]

    # (a) POSITIVE CONTROL: perturbing a strictly-earlier SAME-SEASON game of this team must
    #     move dcur_t for row i
    same_season_earlier = hist[(hist["team_id"] == team_i) & (hist["season"] == hist["season"].iloc[i])
                               & (hist["game_date"] < date_i)]
    check(len(same_season_earlier) > 0, "fixture must contain an earlier same-season game")
    earlier_gid = same_season_earlier["game_id"].iloc[0]
    hist_pert = hist.copy()
    hist_pert.loc[hist_pert["game_id"] == earlier_gid, "n_off_poss"] += 1000.0
    pert = feat.compute_features(hist_pert, targets)
    check(abs(pert["dcur"][i] - base["dcur"][i]) > 1.0,
          "perturbing a strictly-earlier same-season game must move dcur_t")

    # (b) POSITIVE CONTROL: perturbing a game in the immediately-PRECEDING season must move
    #     dprev_t for row i (m_prev must be > 0 for this row)
    check(base["m_prev"][i] > 0, "fixture row must have a nonzero preceding-season count")
    prev_season_game = hist[(hist["team_id"] == team_i) & (hist["season"] == hist["season"].iloc[i] - 1)]
    check(len(prev_season_game) > 0, "fixture must contain a preceding-season game")
    prev_gid = prev_season_game["game_id"].iloc[0]
    hist_pert2 = hist.copy()
    hist_pert2.loc[hist_pert2["game_id"] == prev_gid, "n_off_poss"] += 1000.0
    pert2 = feat.compute_features(hist_pert2, targets)
    check(abs(pert2["dprev"][i] - base["dprev"][i]) > 1.0,
          "perturbing a preceding-season game must move dprev_t")

    # (c) NEGATIVE CONTROL: perturbing a STRICTLY LATER game (any team) must change NOTHING
    later = hist[hist["game_date"] > date_i]
    check(len(later) > 0, "fixture must contain later games")
    later_gid = later["game_id"].iloc[0]
    hist_later = hist.copy()
    hist_later.loc[hist_later["game_id"] == later_gid, "n_off_poss"] += 1000.0
    later_feat = feat.compute_features(hist_later, targets)
    check(abs(later_feat["dcur"][i] - base["dcur"][i]) < 1e-9,
          "perturbing a strictly-later game must NOT change dcur_t (strict lagging)")
    check(abs(later_feat["dprev"][i] - base["dprev"][i]) < 1e-9,
          "perturbing a strictly-later game must NOT change dprev_t (strict lagging)")

    # (d) NEGATIVE CONTROL: perturbing the row's OWN game must change NOTHING for its own dcur/dprev
    hist_same = hist.copy()
    hist_same.loc[hist_same["game_id"] == game_i, "n_off_poss"] += 1000.0
    same_feat = feat.compute_features(hist_same, targets)
    check(abs(same_feat["dcur"][i] - base["dcur"][i]) < 1e-9,
          "perturbing the row's OWN game must NOT change its own dcur_t (no same-game leakage)")
    check(abs(same_feat["dprev"][i] - base["dprev"][i]) < 1e-9,
          "perturbing the row's OWN game must NOT change its own dprev_t (no same-game leakage)")
    return {"row_checked": int(i)}


def t04_empty_window_rules():
    hist = fx.build_universe(n_games_per_team_per_season=10, seed=21)
    targets = hist[["team_id", "game_id"]].copy()
    out = feat.compute_features(hist, targets)

    zero_ncur = out["n_cur"] == 0
    check(zero_ncur.any(), "fixture must contain at least one team's season-opening game")
    check(np.all(out["dcur"][zero_ncur] == 0.0), "dcur_t must be exactly 0 at n_cur==0")

    zero_mprev = out["m_prev"] == 0
    check(zero_mprev.any(), "fixture must contain rows with no preceding season (season 1, or "
                            "the expansion team's debut season)")
    check(np.all(out["dprev"][zero_mprev] == 0.0), "dprev_t must be exactly 0 at m_prev==0")

    # the expansion team's very first game: BOTH n_cur==0 AND m_prev==0 simultaneously
    exp_mask = (hist["team_id"] == fx.EXPANSION_TEAM).to_numpy()
    check(exp_mask.any(), "fixture must contain the synthetic expansion team")
    exp_first = int(np.flatnonzero(exp_mask)[np.argmin(hist.loc[exp_mask, "game_date"].to_numpy())])
    check(out["n_cur"][exp_first] == 0 and out["m_prev"][exp_first] == 0,
          "expansion team's first game must have zero current- and previous-season evidence")
    for rho in feat.ENUMERATED_RHO + (feat.NULL_RHO,):
        blend = feat.dblend(out["dcur"], out["dprev"], out["n_cur"], out["m_prev"], rho)
        check(blend[exp_first] == 0.0,
              f"dblend_t(rho={rho}) must be exactly 0 at the double-empty window "
              f"(n_cur+rho*m_prev==0)")
    return {"n_zero_ncur": int(zero_ncur.sum()), "n_zero_mprev": int(zero_mprev.sum()),
           "expansion_first_row": exp_first}


def t05_enumeration_elements_exact():
    hist = fx.build_universe(seed=17)
    a25 = A.A11Arm(hist, 0.25, ["f1"], len(hist))
    a50 = A.A11Arm(hist, 0.5, ["f1"], len(hist))
    a75 = A.A11Arm(hist, 0.75, ["f1"], len(hist))
    check(a25.enumeration_element() == {"rho": 0.25}, "rho=0.25 element must be exact")
    check(a50.enumeration_element() == {"rho": 0.5}, "rho=0.5 element must be exact")
    check(a75.enumeration_element() == {"rho": 0.75}, "rho=0.75 element must be exact")
    ids = {a25.element_id(), a50.element_id(), a75.element_id()}
    check(len(ids) == 3, "element_id must be distinct across elements")
    check(a25.arm_id == a50.arm_id == a75.arm_id == "A11_carryover_blend_rho",
          "arm_id shared across elements")
    expect_raises(ValueError, lambda: A.A11Arm(hist, 0.4, ["f"], 1),
                  "rho=0.4 is not a frozen enumeration element and must be refused")

    fold = {"fold_id": "syn_f1", "train_idx": np.arange(len(hist)), "test_idx": np.array([], int)}
    b25 = a25.build_design(fold, hist)
    b75 = a75.build_design(fold, hist)
    check(not np.array_equal(b25["columns"][A.TREATMENT_COL], b75["columns"][A.TREATMENT_COL]),
          "dblend_t(rho) must differ across rho elements on a fixture with real season-to-season drift")
    check(np.array_equal(b25["columns"][A.NULL_COL], b75["columns"][A.NULL_COL]),
          "dblend_t(1) (the null column) must be IDENTICAL across rho elements -- it does not "
          "depend on the module's own rho")
    return {"elements": [a25.enumeration_element(), a50.enumeration_element(),
                         a75.enumeration_element()]}


def t06_build_design_and_conformance_and_nesting():
    hist = fx.build_universe(seed=23)
    arm = A.A11Arm(hist, 0.5, ["syn_f1", "syn_f2"], len(hist))

    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], f"A11 rho=0.5 module must conform: {rec}")
    check(arm.uses_global_intercept() is False,
          "P35 intercept_structure: A11 is in without_any_global_intercept")
    check("A11" in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT, "frozen intercept table membership")

    n_train = len(hist) - 20
    fold = {"fold_id": "syn_f1", "train_idx": np.arange(n_train),
           "test_idx": np.arange(n_train, len(hist))}
    bundle = arm.build_design(fold, hist)
    bval = ri.validate_design_bundle(bundle, hist, arm.uses_global_intercept(), "syn_f1")
    check(bval["valid"], f"A11 rho=0.5 design bundle must validate: {bval}")

    check(bundle["treatment_cols"] == [A.TREATMENT_COL], "arm treatment must be exactly dblend_t(rho)")
    check(bundle["nuisance_cols"] == [], "A11 carries no nuisance term")
    check(bundle["indicator_cols"] == [], "dblend_t is continuous, not a 0/1 indicator")

    k0 = bundle["k0_matched_design"]
    check(k0["comparison"] == "parameter_fixed_at_null",
          "A11's K0 comparison must be parameter_fixed_at_null (a11_repair)")
    check(k0["treatment_cols"] == [A.NULL_COL],
          "the null's own free column dblend_t(1) must appear in k0_matched_design.treatment_cols "
          "(RUNNER_INTERFACE.md section 3)")
    check(k0["nuisance_cols"] == [], "the null carries no nuisance term either")
    # nesting semantics specific to parameter_fixed_at_null: the null's column is NOT a subset of
    # the arm's own column set (a DIFFERENT rho), which is exactly why this comparison type
    # exists (distinct from term_removal's strict column-subset nesting)
    check(A.NULL_COL not in (set(bundle["treatment_cols"]) | set(bundle["nuisance_cols"])),
          "the null's free column must be a DISTINCT materialised column from the arm's own "
          "treatment column (different rho), not a literal subset")
    return {"checks": 6}


def t07_p26_record_valid():
    hist = fx.build_universe(seed=3)
    arm = A.A11Arm(hist, 0.25, ["syn_f1"], len(hist))
    rec = arm.p26_k0_record()
    out = gh.p26_check(rec)
    check(out["valid"], f"A11's k0_matched/1 record must validate against P26: {out}")
    check(not out["r8_filtered_findings"],
          "hierarchical_pooling is not calibration_only; no R8 slope-role adjudication fires")

    # negative control: a record whose null declares a non-empty substantive_features must be
    # refused (R3: comparison_gate blocks any K0 with substantive_features)
    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = [A.NULL_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a K0 declaring a non-empty substantive_features must be refused")

    # negative control: removing tested_parameters must trip the base R8 fixed-parameter check
    bad2 = json.loads(json.dumps(rec))
    bad2["treatment_mechanism"]["tested_parameters"] = []
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad2),
                  "hierarchical_pooling with no tested_parameters must fail R8's base check")
    return {"arm_kind": rec["arm_kind"], "comparison": rec["treatment_mechanism"]
           ["null_construction"]["method"]}


def t08_structural_deactivation_hook_and_mechanism():
    hist = fx.build_universe(seed=9)
    arm = A.A11Arm(hist, 0.5, ["syn_f1"], len(hist))
    check(arm.structurally_deactivated_folds() == ["train_lt_2022"],
          "structurally_deactivated_folds() must return exactly the card-pinned real fold id "
          "(a11_repair.fold1_evaluability_pinned) -- a bare string, never passed to the blinded "
          "runner as an actual fold_id in this suite")

    # demonstrate the MECHANISM the card's deactivation is based on using a synthetic first fold
    # (never named "train_lt_2022"): 100% of training rows have m_prev==0 because season 1 has
    # no preceding season in the archive
    folds = fx.build_folds(hist)
    first_fold = folds[0]
    targets = hist.iloc[first_fold["train_idx"]][["team_id", "game_id"]].reset_index(drop=True)
    feats = feat.compute_features(hist, targets)
    check(np.all(feats["m_prev"] == 0.0),
          "first-season synthetic fold: m_prev must be 0 on 100% of training rows, reproducing "
          "the mechanism a11_repair.fold1_evaluability_pinned deactivates train_lt_2022 for")
    return {"first_fold_id": first_fold["fold_id"], "n_train_rows": int(len(targets))}


def t09_kill_condition_hooks_decidable():
    both_cover_zero = {"f1": {"point": 0.02, "ci_low": -0.10, "ci_high": 0.15},
                       "f2": {"point": -0.01, "ci_low": -0.08, "ci_high": 0.06}}
    d1 = A.decide_kill(both_cover_zero)
    check(d1["killed"] and d1["interval_kill"] and not d1["sign_kill"] and not d1["thin_stratum_kill"],
          "interval-covers-zero-in-every-fold must kill (i)")

    sign_flip = {"f1": {"point": 0.20, "ci_low": 0.05, "ci_high": 0.35},
                "f2": {"point": -0.20, "ci_low": -0.35, "ci_high": -0.05}}
    d2 = A.decide_kill(sign_flip)
    check(d2["killed"] and d2["sign_kill"] and not d2["interval_kill"],
          "sign instability across evaluable folds must kill (iii)")

    survives = {"f1": {"point": 0.20, "ci_low": 0.05, "ci_high": 0.35},
               "f2": {"point": 0.18, "ci_low": 0.02, "ci_high": 0.30}}
    d3 = A.decide_kill(survives, thin_stratum_concentrated=True)
    check(not d3["killed"], "consistent-sign, zero-excluding intervals with concentrated "
                            "improvement must NOT kill")

    d4 = A.decide_kill(survives, thin_stratum_concentrated=False)
    check(d4["killed"] and d4["thin_stratum_kill"],
          "improvement not concentrated on the n_cur<=5 stratum must kill (ii)")

    d5 = A.decide_kill({}, p25_rejected=True)
    check(d5["killed"] and d5["reason"] == "p25_rejection",
          "a P25 rejection at invocation must kill before any performance number is consulted")

    expect_raises(ValueError, lambda: A.decide_kill({"f1": {"point": 0, "ci_low": 1, "ci_high": -1}}),
                  "a malformed interval (lo > hi) must be refused, not silently decided")
    return {"decisions": [d1["reason"], d2["reason"], d3["reason"], d4["reason"], d5["reason"]]}


def t10_franchise_continuity_receipt():
    hist = fx.build_universe(seed=1)
    arm = A.A11Arm(hist, 0.75, ["syn_f1"], len(hist))
    check(arm.requires_franchise_continuity() is True, "A11 requires the P23 receipt")
    ok = gh.p23_check(requires_franchise_continuity=True, receipts=arm.p23_receipts())
    check(ok["valid"], "A11's own receipt must carry the correctly pinned team_cities hash")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p23_check(
        requires_franchise_continuity=True, receipts=[{"team_cities_sha256": "0" * 64}]),
        "a wrong team_cities pin must fail closed")
    return {"pin": rc.TEAM_CITIES_SHA256_PIN}


def t11_optional_hooks_shape():
    hist = fx.build_universe(seed=2)
    arm = A.A11Arm(hist, 0.25, ["syn_f1"], len(hist))
    check(arm.preregistered_contrasts() is None, "A11 declares no contrast_ column")
    check(arm.prereg_digest_expected() is None, "A11 has no contrast digest")
    check(arm.p27_rule() is None, "A11 registers no P27 active-set rule (its deactivation is "
                                  "structural, not an S7 rule)")
    specs = arm.lag_specs()
    check(set(specs) == {A.TREATMENT_COL, A.NULL_COL}, "lag_specs must cover both design columns")
    check(all(s["kind"] == "DERIVED_NO_JOIN" for s in specs.values()),
          "both A11 columns are declared DERIVED_NO_JOIN")
    check(arm.lag_sources() == {}, "DERIVED_NO_JOIN declares no PRIOR_GAME source")
    return {"lag_kinds": {k: v["kind"] for k, v in specs.items()}}


def t12_p22_dependency_battery_runs():
    hist = fx.build_universe(n_games_per_team_per_season=10, seed=55)
    arm = A.A11Arm(hist, 0.5, ["syn_f1"], len(hist))
    fold = {"fold_id": "syn_f1", "train_idx": np.arange(len(hist)), "test_idx": np.array([], int)}
    bundle = arm.build_design(fold, hist)
    frame = hist.copy()
    for name, v in bundle["columns"].items():
        frame[name] = v
    basis = fx.build_prohibited_basis(hist)
    rec = gh.p22_check(frame, [A.TREATMENT_COL, A.NULL_COL], prohibited_basis=basis,
                       lag_specs=arm.lag_specs(), lag_sources=arm.lag_sources())
    check(not rec.get("blocking"), f"A11 columns must show no dependency on the synthetic "
                                   f"same-game duration surrogate: {rec.get('blocking')}")
    return {"blocking": rec.get("blocking", [])}


def t13_end_to_end_synthetic_run_deterministic():
    hist = fx.build_universe(seed=4211)
    folds = fx.build_folds(hist)
    basis = fx.build_prohibited_basis(hist)
    arm = A.A11Arm(hist, 0.5, [f["fold_id"] for f in folds], len(hist))
    out_path = HERE / "artifacts" / "A11_rho0.5_receipt.json"
    out_path.parent.mkdir(exist_ok=True)

    t0 = time.time()
    rec = rn.run_arm(arm, hist, folds, prohibited_basis=basis, env={}, out_path=out_path,
                     run_git=False)
    dt = time.time() - t0

    check(rec["schema"] == rc.RECEIPT_SCHEMA, "receipt schema pin")
    check(out_path.exists(), "receipt file written")
    check(rec["results"]["structurally_deactivated_folds"] == ["train_lt_2022"],
          "the receipt must carry the arm module's own structurally_deactivated_folds() value "
          "verbatim (runner.py copies the hook's return value into results); none of THIS "
          "synthetic run's fold ids happens to equal it, so every synthetic fold is still "
          "evaluated (checked below via evaluable_folds)")
    check(rec["results"]["evaluable_folds"] == [f["fold_id"] for f in folds],
          "since no synthetic fold id collides with the card-pinned real deactivation id, every "
          "synthetic fold must be EVALUABLE in this run")
    check(rec["guard_records"]["p26"]["valid"], "P26 must pass for A11's own record")
    check(rec["guard_records"]["module_conformance"]["conformant"], "module conformance")
    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict")

    # determinism: an identical second run must reproduce results and fold records exactly
    rec2 = rn.run_arm(arm, hist, folds, prohibited_basis=basis, env={}, run_git=False)
    import receipts
    d1 = receipts.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = receipts.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: refuses the card's own real fold id without P38_UNSEALED
    bad_folds = [dict(folds[0], fold_id="train_lt_2022")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, hist, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse the real fold id train_lt_2022 without P38_UNSEALED")

    return {"seconds": round(dt, 2), "evaluable_folds": rec["results"]["evaluable_folds"],
           "results_digest": d1}


def t14_no_p38_unsealed_flag_in_environment():
    check(rc.UNSEAL_ENV_FLAG not in os.environ,
          "this suite must never run with the real unseal flag set")


# ------------------------------------------------------------------------------------- driver
def main():
    tests = [
        t01_p35_spec_hash_pin, t02_feature_determinism_and_order_independence,
        t03_strict_lagging_current_and_previous_season, t04_empty_window_rules,
        t05_enumeration_elements_exact, t06_build_design_and_conformance_and_nesting,
        t07_p26_record_valid, t08_structural_deactivation_hook_and_mechanism,
        t09_kill_condition_hooks_decidable, t10_franchise_continuity_receipt,
        t11_optional_hooks_shape, t12_p22_dependency_battery_runs,
        t13_end_to_end_synthetic_run_deterministic, t14_no_p38_unsealed_flag_in_environment,
    ]
    passed, failed = 0, 0
    for fn in tests:
        name = fn.__name__
        t0 = time.time()
        try:
            measured = fn() or {}
            RESULTS.append({"test": name, "status": "PASS", "seconds": round(time.time() - t0, 4),
                            "measured": measured})
            passed += 1
            print(f"PASS  {name}")
        except Exception as e:                                     # noqa: BLE001
            RESULTS.append({"test": name, "status": "FAIL", "seconds": round(time.time() - t0, 4),
                            "error": repr(e), "traceback": traceback.format_exc()})
            failed += 1
            print(f"FAIL  {name}: {e}")

    out = {
        "schema": "p36_a11_test_receipt/1",
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "arm_id": A.ARM_ID, "p35_spec_sha256": A.P35_SPEC_SHA256,
        "n_tests": len(tests), "n_passed": passed, "n_failed": failed,
        "results": RESULTS,
    }
    (ARM_DIR / "TEST_RECEIPT.json").write_text(json.dumps(out, indent=2, default=str),
                                                encoding="utf-8")
    print(f"\n{passed}/{len(tests)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
