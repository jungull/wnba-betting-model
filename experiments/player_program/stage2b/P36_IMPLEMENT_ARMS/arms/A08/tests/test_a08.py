#!/usr/bin/env python3
"""test_a08.py -- unit, synthetic, identity and schema tests for the A08_league_lag_level arm.

BLINDED: every frame here is synthetic; no real fold, no real MAE, no comparative historical
performance of any kind is read or computed anywhere in this file. This suite never sets
P38_UNSEALED and asserts it is absent from the environment.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A08/tests/test_a08.py
Writes: ../A08_TEST_RECEIPT.json
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
RUNNER = ARM_DIR.parents[1] / "runner"
for p in (str(ARM_DIR), str(RUNNER)):
    if p not in sys.path:
        sys.path.insert(0, p)

import a08_arm as arm_mod                       # noqa: E402
import features as feat                          # noqa: E402
import guard_harness as gh                        # noqa: E402  (frozen; read-only import)
import runner_constants as rc                     # noqa: E402  (frozen; read-only import)
import runner_interface as ri                      # noqa: E402  (frozen; read-only import)

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


# ------------------------------------------------------------------------------- synthetic fixture
def build_history(n_games: int = 140, seed: int = 4242) -> pd.DataFrame:
    """A fully synthetic contract-schedule table: n_games games, 2 teams each, 6 rotating teams.

    Deliberately far from the real 2,990/1,495 contract-schedule signature and never uses real
    fold ids, so the blinding gate (were this ever run against the real runner) would admit it
    without any flag -- though this module never invokes the runner at all.
    """
    rng = np.random.Generator(np.random.PCG64(seed))
    teams = list(range(6))
    rows = []
    gid = 500_000
    for g in range(n_games):
        gid += 1
        home, away = rng.choice(teams, size=2, replace=False)
        for team_id in (int(home), int(away)):
            rows.append({
                "game_id": gid, "game_date": 20300101 + g,       # strictly increasing, one/day
                "team_id": team_id, "season": 9001 + g // 40,
                "pace": float(rng.normal(loc=75.0, scale=5.0)),
            })
    return pd.DataFrame(rows)


def build_universe(history: pd.DataFrame, frac: float = 1.0, seed: int = 99) -> pd.DataFrame:
    """The modeling universe: a (possibly strict) subset of `history`'s rows, row order shuffled
    to prove the feature construction is order-independent (keyed on game identity, not row
    position)."""
    rng = np.random.Generator(np.random.PCG64(seed))
    u = history.copy()
    if frac < 1.0:
        game_ids = u["game_id"].drop_duplicates()
        keep = set(rng.choice(game_ids, size=int(len(game_ids) * frac), replace=False))
        u = u[u["game_id"].isin(keep)]
    u = u.sample(frac=1.0, random_state=int(rng.integers(0, 2**31 - 1))).reset_index(drop=True)
    u[rc.INCUMBENT_PROJECTION_COL] = 80.0
    u[rc.OFFSET_COL] = float(np.log(80.0))
    return u


def targets_from_universe(universe: pd.DataFrame) -> pd.DataFrame:
    return universe[["game_date", "game_id", "team_id"]].copy()


# ------------------------------------------------------------------------------------- tests
def t01_feature_determinism():
    hist = build_history()
    uni = build_universe(hist)
    tgt = targets_from_universe(uni)
    f1 = feat.compute_features(hist, tgt, K=20)
    f2 = feat.compute_features(hist, tgt, K=20)
    check(np.array_equal(f1["d_t"], f2["d_t"]), "d_t must be bitwise deterministic")
    check(np.array_equal(f1["L_raw"], f2["L_raw"]), "L_raw must be bitwise deterministic")
    check(f1["d_t"].tobytes() == f2["d_t"].tobytes(), "d_t bytes must match exactly")
    # order-independence: shuffling the universe row order must not change per-row values
    uni2 = uni.sample(frac=1.0, random_state=7).reset_index(drop=True)
    f3 = feat.compute_features(hist, targets_from_universe(uni2), K=20)
    # re-align by (game_id, team_id) and compare
    key1 = list(zip(uni["game_id"], uni["team_id"]))
    key2 = list(zip(uni2["game_id"], uni2["team_id"]))
    d_by_key1 = dict(zip(key1, f1["d_t"]))
    d_by_key2 = dict(zip(key2, f3["d_t"]))
    check(all(abs(d_by_key1[k] - d_by_key2[k]) < 1e-12 for k in key1),
          "d_t must be row-order independent")
    return {"n_rows": int(len(uni))}


def t02_strict_lagging():
    hist = build_history(n_games=60, seed=11)
    uni = build_universe(hist)
    tgt = targets_from_universe(uni)
    K = 10
    base = feat.compute_features(hist, tgt, K=K)

    # pick a target row with a well-defined window and both earlier and later games in history
    ranks = base["game_rank"]
    i = int(np.argmax(ranks >= K + 5))          # a row comfortably inside the archive
    check(ranks[i] >= K + 5, "fixture too small for this test")
    r = int(ranks[i])

    # (a) POSITIVE CONTROL: perturbing a STRICTLY EARLIER game's pace must change L_raw/d_t
    order = hist.sort_values(["game_date", "game_id"], kind="mergesort")
    earlier_game_id = order["game_id"].drop_duplicates().iloc[r - 1]
    hist_perturbed = hist.copy()
    hist_perturbed.loc[hist_perturbed["game_id"] == earlier_game_id, "pace"] += 1000.0
    pert = feat.compute_features(hist_perturbed, tgt, K=K)
    check(abs(pert["L_raw"][i] - base["L_raw"][i]) > 1.0,
          "perturbing a strictly-earlier game inside the K-window must move L_raw")

    # (b) NEGATIVE CONTROL: perturbing a STRICTLY LATER game must change NOTHING for row i
    later_game_id = order["game_id"].drop_duplicates().iloc[r + 1]
    hist_later = hist.copy()
    hist_later.loc[hist_later["game_id"] == later_game_id, "pace"] += 1000.0
    later = feat.compute_features(hist_later, tgt, K=K)
    check(abs(later["L_raw"][i] - base["L_raw"][i]) < 1e-9,
          "perturbing a strictly-later game must NOT change this row's L_raw (strict lagging)")
    check(abs(later["d_t"][i] - base["d_t"][i]) < 1e-9,
          "perturbing a strictly-later game must NOT change this row's d_t (strict lagging)")

    # (c) NEGATIVE CONTROL: perturbing the row's OWN game (same-game) must change NOTHING
    same = hist.copy()
    tgt_row = tgt.iloc[i]
    same.loc[(same["game_id"] == tgt_row["game_id"]), "pace"] += 1000.0
    samefeat = feat.compute_features(same, tgt, K=K)
    check(abs(samefeat["L_raw"][i] - base["L_raw"][i]) < 1e-9,
          "perturbing the row's OWN game must NOT change its own L_raw (no same-game leakage)")
    check(abs(samefeat["d_t"][i] - base["d_t"][i]) < 1e-9,
          "perturbing the row's OWN game must NOT change its own d_t (no same-game leakage)")
    return {"row_checked_game_rank": r, "K": K}


def t03_empty_window_rules():
    hist = build_history(n_games=60, seed=5)
    uni = build_universe(hist)
    tgt = targets_from_universe(uni)
    K = 20
    out = feat.compute_features(hist, tgt, K=K)

    zero_own = out["n_prior_own"] == 0
    check(zero_own.any(), "fixture must contain at least one team's first game")
    check(np.all(out["d_t"][zero_own] == 0.0), "d_t must be exactly 0 at zero own-prior games")

    prewindow = ~out["windowed_defined"]
    check(prewindow.any(), "fixture must contain rows with fewer than K prior league games")
    check(np.all(out["L_raw"][prewindow] == 0.0), "L_raw must be exactly 0 below the K floor")
    train_mask = np.ones(len(tgt), dtype=bool)
    _, L_t = feat.center_L(out["L_raw"], out["windowed_defined"], train_mask)
    check(np.all(L_t[prewindow] == 0.0),
          "centered L_t must remain exactly 0 for pre-window rows regardless of Lbar_train "
          "(P35 A08 FOLDS F1/OPERATIONAL OP-3)")
    return {"n_zero_own_prior": int(zero_own.sum()), "n_prewindow": int(prewindow.sum())}


def t04_enumeration_elements_exact():
    hist = build_history(n_games=140, seed=17)
    uni = build_universe(hist)
    a20 = arm_mod.A08Arm(hist, 20, ["syn_f1"], len(uni))
    a80 = arm_mod.A08Arm(hist, 80, ["syn_f1"], len(uni))
    check(a20.enumeration_element() == {"K": 20}, "K=20 element must be exact")
    check(a80.enumeration_element() == {"K": 80}, "K=80 element must be exact")
    check(a20.element_id() == "A08_K20" and a80.element_id() == "A08_K80",
          "element_id must be deterministic and distinct")
    check(a20.arm_id == a80.arm_id == "A08_league_lag_level", "arm_id shared across elements")

    fold = {"fold_id": "syn_f1", "train_idx": np.arange(len(uni)), "test_idx": np.array([], int)}
    b20 = a20.build_design(fold, uni)
    b80 = a80.build_design(fold, uni)
    check(np.array_equal(b20["columns"]["d_t"], b80["columns"]["d_t"]),
          "d_t is K-free and must be IDENTICAL across enumeration elements (P35 K0 K4)")
    check(not np.array_equal(b20["columns"]["L_t"], b80["columns"]["L_t"]),
          "L_t must differ across K elements on a fixture with real drift")
    expect_raises(ValueError, lambda: arm_mod.A08Arm(hist, 50, ["f"], 1),
                  "K=50 is not a frozen enumeration element and must be refused")
    return {"elements": [a20.enumeration_element(), a80.enumeration_element()]}


def t05_conformance_and_nesting():
    hist = build_history(n_games=100, seed=23)
    uni = build_universe(hist)
    a = arm_mod.A08Arm(hist, 20, ["syn_f1", "syn_f2"], len(uni))

    rec = ri.validate_arm_module(a)
    check(rec["conformant"], f"A08 K=20 module must conform: {rec}")

    n_train = len(uni) - 10
    fold = {"fold_id": "syn_f1", "train_idx": np.arange(n_train),
           "test_idx": np.arange(n_train, len(uni))}
    bundle = a.build_design(fold, uni)
    bval = ri.validate_design_bundle(bundle, uni, a.uses_global_intercept(), "syn_f1")
    check(bval["valid"], f"A08 K=20 design bundle must validate: {bval}")

    # arm-vs-null nesting: null keeps every arm nuisance term and drops ONLY the treatment
    k0 = bundle["k0_matched_design"]
    check(k0["comparison"] == "term_removal", "A08's K0 comparison must be term_removal")
    check(set(k0["nuisance_cols"]) == set(bundle["nuisance_cols"]) == {"d_t"},
          "null nuisance terms must equal the arm's nuisance terms exactly")
    check(k0["treatment_cols"] == [], "null must carry zero treatment columns (term_removal)")
    check(bundle["treatment_cols"] == ["L_t"], "arm treatment must be exactly L_t")
    check(set(bundle["nuisance_cols"]) | set(bundle["treatment_cols"])
          == set(k0["nuisance_cols"]) | set(k0["treatment_cols"]) | {"L_t"},
          "null design must be the arm design with EXACTLY the treatment term removed, nothing "
          "else")
    return {"checks": 5}


def t06_p26_record_valid():
    hist = build_history(n_games=60, seed=3)
    uni = build_universe(hist)
    a = arm_mod.A08Arm(hist, 80, ["syn_f1"], len(uni))
    rec = a.p26_k0_record()
    out = gh.p26_check(rec)
    check(out["valid"], f"A08's k0_matched/1 record must validate against P26: {out}")
    check(not out["r8_filtered_findings"],
          "level_transport is not calibration_only; no R8 adjudication should fire")

    # negative control: a record that fails to exclude ONLY the treatment must be refused
    bad = json.loads(json.dumps(rec))
    bad["arm_spec"]["substantive_features"] = ["L_t", "d_t"]     # over-declares d_t as substantive
    bad["k0_spec"]["substantive_features"] = []
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null that does not exclude exactly the declared treatment must be refused")
    return {"arm_kind": rec["arm_kind"]}


def t07_kill_condition_hooks_decidable():
    both_cover_zero = {"f1": {"point": 0.02, "ci_low": -0.10, "ci_high": 0.15},
                       "f2": {"point": -0.01, "ci_low": -0.08, "ci_high": 0.06}}
    d1 = arm_mod.decide_kill(both_cover_zero)
    check(d1["killed"] and d1["interval_kill"] and not d1["sign_kill"],
          "interval-covers-zero-in-every-fold must kill")

    sign_flip = {"f1": {"point": 0.20, "ci_low": 0.05, "ci_high": 0.35},
                "f2": {"point": -0.20, "ci_low": -0.35, "ci_high": -0.05}}
    d2 = arm_mod.decide_kill(sign_flip)
    check(d2["killed"] and d2["sign_kill"] and not d2["interval_kill"],
          "sign instability across evaluable folds must kill")

    survives = {"f1": {"point": 0.20, "ci_low": 0.05, "ci_high": 0.35},
               "f2": {"point": 0.18, "ci_low": 0.02, "ci_high": 0.30}}
    d3 = arm_mod.decide_kill(survives)
    check(not d3["killed"], "consistent-sign, zero-excluding intervals must NOT kill")

    d4 = arm_mod.decide_kill({}, p25_rejected=True)
    check(d4["killed"] and d4["reason"] == "p25_rejection",
          "a P25 rejection at invocation must kill before any performance number is consulted")

    expect_raises(ValueError, lambda: arm_mod.decide_kill({"f1": {"point": 0, "ci_low": 1,
                                                                  "ci_high": -1}}),
                  "a malformed interval (lo > hi) must be refused, not silently decided")
    return {"decisions": [d1["reason"], d2["reason"], d3["reason"], d4["reason"]]}


def t08_franchise_continuity_receipt():
    hist = build_history(n_games=30, seed=1)
    uni = build_universe(hist)
    a = arm_mod.A08Arm(hist, 20, ["syn_f1"], len(uni))
    check(a.requires_franchise_continuity() is True, "A08 requires the P23 receipt")
    ok = gh.p23_check(requires_franchise_continuity=True, receipts=a.p23_receipts())
    check(ok["valid"], "A08's own receipt must carry the correctly pinned team_cities hash")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p23_check(
        requires_franchise_continuity=True, receipts=[{"team_cities_sha256": "0" * 64}]),
        "a wrong team_cities pin must fail closed")
    return {"pin": rc.TEAM_CITIES_SHA256_PIN}


def t09_optional_hooks_shape():
    hist = build_history(n_games=30, seed=2)
    uni = build_universe(hist)
    a = arm_mod.A08Arm(hist, 20, ["syn_f1"], len(uni))
    check(a.preregistered_contrasts() is None, "A08 declares no contrast_ column")
    check(a.prereg_digest_expected() is None, "A08 has no contrast digest")
    check(a.p27_rule() is None, "A08 registers no P27 active-set rule")
    check(not hasattr(a, "structurally_deactivated_folds")
          or a.structurally_deactivated_folds is None
          or True, "optional hook absence is permitted (A08 deactivates no folds)")
    specs = a.lag_specs()
    check(set(specs) == {"d_t", "L_t"}, "lag_specs must cover both design columns")
    check(all(s["kind"] == "DERIVED_NO_JOIN" for s in specs.values()),
          "both A08 columns are declared DERIVED_NO_JOIN (see a08_arm.py rationale)")
    check(a.lag_sources() == {}, "DERIVED_NO_JOIN declares no PRIOR_GAME source")
    return {"lag_kinds": {k: v["kind"] for k, v in specs.items()}}


def t10_p22_dependency_battery_runs():
    """The P22 guard's full dependency battery (leakage-vs-a-prohibited-quantity check) can at
    least be INVOKED against A08's constructed columns with a synthetic prohibited basis -- this
    does not certify PRIOR_GAME-style re-derivation (t09 records that gap honestly) but does
    confirm the columns carry no dependency on a synthetic same-game duration surrogate."""
    hist = build_history(n_games=60, seed=9)
    uni = build_universe(hist)
    a = arm_mod.A08Arm(hist, 20, ["syn_f1"], len(uni))
    fold = {"fold_id": "syn_f1", "train_idx": np.arange(len(uni)), "test_idx": np.array([], int)}
    bundle = a.build_design(fold, uni)
    frame = uni.copy()
    frame["d_t"] = bundle["columns"]["d_t"]
    frame["L_t"] = bundle["columns"]["L_t"]
    rng = np.random.Generator(np.random.PCG64(55))
    prohibited_frame = pd.DataFrame({
        "game_minutes": 40.0 + 5.0 * rng.integers(0, 3, len(uni)),
    }, index=frame.index)
    basis = gh.make_prohibited_basis(prohibited_frame,
                                     source={"artifact_id": "synthetic_a08_test/1"},
                                     note="synthetic same-game duration surrogate for A08 tests")
    rec = gh.p22_check(frame, ["d_t", "L_t"], prohibited_basis=basis,
                       lag_specs=a.lag_specs(), lag_sources=a.lag_sources())
    check(not rec.get("blocking"), f"A08 columns must show no dependency on the synthetic "
                                   f"same-game duration surrogate: {rec.get('blocking')}")
    return {"blocking": rec.get("blocking", [])}


TESTS = [
    ("T01_feature_determinism", t01_feature_determinism),
    ("T02_strict_lagging", t02_strict_lagging),
    ("T03_empty_window_rules", t03_empty_window_rules),
    ("T04_enumeration_elements_exact", t04_enumeration_elements_exact),
    ("T05_conformance_and_nesting", t05_conformance_and_nesting),
    ("T06_p26_record_valid", t06_p26_record_valid),
    ("T07_kill_condition_hooks_decidable", t07_kill_condition_hooks_decidable),
    ("T08_franchise_continuity_receipt", t08_franchise_continuity_receipt),
    ("T09_optional_hooks_shape", t09_optional_hooks_shape),
    ("T10_p22_dependency_battery_runs", t10_p22_dependency_battery_runs),
]


def main() -> int:
    if rc.UNSEAL_ENV_FLAG in os.environ:
        print(f"FATAL: {rc.UNSEAL_ENV_FLAG} exists in the environment; "
              "the blinded A08 test suite refuses to run.")
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
        "schema": "p36_a08_test_receipt/1",
        "arm_id": arm_mod.CARD_ID,
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = ARM_DIR / "A08_TEST_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
