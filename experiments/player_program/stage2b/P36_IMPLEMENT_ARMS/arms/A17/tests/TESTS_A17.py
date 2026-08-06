#!/usr/bin/env python3
"""TESTS_A17.py -- unit, synthetic, identity and schema tests for A17_transition_mix_share.

BLINDED: every frame here is synthetic (synthetic_fixture_a17.py); no real fold, no real MAE,
no comparative historical performance anywhere. The suite asserts P38_UNSEALED is ABSENT from
the process environment and never sets it (the unseal branch is exercised only through an
injected mapping, exactly like the shared runner's own suite).

Owned by experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A17/ only. Imports the
frozen shared runner (runner/*.py) as a contract; never writes to runner/ or to any other arm's
directory.

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A17/tests/TESTS_A17.py
Writes: ../TEST_RECEIPT_A17.json (machine-readable results).
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

import a17_transition_mix_share as a17mod                             # noqa: E402
import feature_construction as feat                                   # noqa: E402
import synthetic_fixture_a17 as fx                                    # noqa: E402

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
    poss = fx.build_possessions()
    df = fx.build_universe(poss)
    folds = fx.build_folds(df)
    fids = [f["fold_id"] for f in folds]
    arm = a17mod.A17TransitionMixShare(poss, fids)
    return arm, df, folds, poss


# ------------------------------------------------------------------------------- tests
def t01_module_conformance():
    arm, df, folds, poss = _fresh_arm()
    rec = ri.validate_arm_module(arm)
    check(rec["conformant"], "A17 module must conform to RUNNER_INTERFACE.md")
    check(rec["arm_id"] == a17mod.ARM_ID, "conformance record must carry the frozen arm_id")
    check(rec["enumeration_element"] == {}, "A17 has no enumeration grid (single element)")

    class WrongFamily(a17mod.A17TransitionMixShare):
        def declared_family(self):
            return "RECALIBRATION"
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(WrongFamily(poss, [f["fold_id"] for f in folds])),
                  "non-SUBSTANTIVE declared_family must be refused (P35 p25_guard_invocation_pins"
                  " pins SUBSTANTIVE for every fitted arm, A17 included)")

    class WrongIntercept(a17mod.A17TransitionMixShare):
        def uses_global_intercept(self):
            return True
    expect_raises(ri.ArmModuleNonconformant,
                  lambda: ri.validate_arm_module(WrongIntercept(poss, [f["fold_id"] for f in folds])),
                  "A17 is in P35 ARMS_WITHOUT_GLOBAL_INTERCEPT; claiming a free intercept must be "
                  "refused by the frozen intercept table")
    check(a17mod.ARM_ID.split("_")[0] in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT,
          "A17 must appear in the frozen no-intercept table")
    return {"conformant": True}


def t02_feature_determinism_and_bundle():
    arm, df, folds, poss = _fresh_arm()
    b1 = arm.build_design(folds[0], df)
    b2 = arm.build_design(folds[0], df)
    v1 = np.asarray(b1["columns"][a17mod.TREATMENT_COL])
    v2 = np.asarray(b2["columns"][a17mod.TREATMENT_COL])
    check(v1.tobytes() == v2.tobytes(), "build_design must be bitwise deterministic (repeat call)")
    n1 = np.asarray(b1["columns"][a17mod.NUISANCE_COL])
    n2 = np.asarray(b2["columns"][a17mod.NUISANCE_COL])
    check(n1.tobytes() == n2.tobytes(), "nuisance column must also be bitwise deterministic")
    check(np.array_equal(n1, df["is_playoff_game"].to_numpy(float)),
          "the materialised nuisance column must equal the raw schedule flag exactly")
    check(np.all((v1 >= 0.0) & (v1 <= 1.0)), "x_transition_mix must be bounded in [0,1]")

    # a training-fold-computed constant DOES exist for A17 (the FOLDS F2 imputation means), so
    # (unlike A05) the treatment column MAY legitimately differ across folds whose train_idx
    # differs; still bitwise-deterministic per fold (checked above).
    v_fold1 = np.asarray(arm.build_design(folds[1], df)["columns"][a17mod.TREATMENT_COL])
    check(v1.shape == v_fold1.shape, "column length invariant across folds")

    bval = ri.validate_design_bundle(b1, df, arm.uses_global_intercept(), folds[0]["fold_id"])
    check(bval["valid"], "design bundle must validate against the frozen intercept invariant")
    check(bval["comparison"] == "term_removal", "A17's K0 comparison is term_removal")
    check(b1["k0_matched_design"]["treatment_cols"] == []
          and b1["k0_matched_design"]["nuisance_cols"] == [a17mod.NUISANCE_COL],
          "A17's null carries the nuisance term but no treatment column")
    check(b1["indicator_cols"] == [a17mod.NUISANCE_COL],
          "only the 0/1 playoff flag is an indicator column; x is continuous")

    bad = df.copy()
    bad["is_playoff_game"] = 2                          # not a strict 0/1 flag
    expect_raises(ValueError, lambda: arm.build_design(folds[0], bad),
                  "a non-0/1 playoff flag must be refused, not silently cast")
    return {"n_rows": len(df), "treatment_mean": float(v1.mean())}


def t02b_recency_weight_matches_naive_definition():
    """Check feature_construction's O(n) recurrence against the naive O(n^2) double-sum
    definition of w(p) = base**Delta_games(p,g) * discount**(season(g)-season(p)) directly, on a
    small hand-built team history spanning a season boundary (so both the game-recency decay and
    the season-crossing discount are simultaneously exercised)."""
    half_life, discount = 10.0, 0.5
    base = 0.5 ** (1.0 / half_life)
    # one team, 5 games: 3 in season 1, 2 in season 2 (season boundary crossed once, between
    # game index 2 and game index 3)
    hist = pd.DataFrame({
        "team_id": ["Z"] * 5, "game_id": [10, 11, 12, 13, 14],
        "game_date": [1, 2, 3, 10, 11], "season": [1, 1, 1, 2, 2],
        "n_off": [10.0, 10.0, 10.0, 10.0, 10.0],
        "n_short_off": [3.0, 4.0, 5.0, 6.0, 7.0],
        "n_def": [10.0, 10.0, 10.0, 10.0, 10.0],
        "n_short_def": [1.0, 2.0, 3.0, 4.0, 5.0],
    })
    got = feat.compute_prior_recency_aggregates(hist, half_life_games=half_life,
                                                 season_boundary_discount=discount)
    got = got.sort_values("game_id").reset_index(drop=True)

    for target_i in range(5):
        num, den = 0.0, 0.0
        for j in range(target_i):
            delta_games = target_i - j                     # 1-indexed "games ago" (module's pin)
            season_gap = hist["season"].iloc[target_i] - hist["season"].iloc[j]
            w = (base ** delta_games) * (discount ** season_gap)
            num += w * hist["n_short_off"].iloc[j]
            den += w * hist["n_off"].iloc[j]
        expected_share = (num / den) if den > 1e-12 else np.nan
        got_share = got["short_off_share"].iloc[target_i]
        if np.isnan(expected_share):
            check(bool(got["short_off_defined"].iloc[target_i]) is False,
                  f"row {target_i}: expected undefined, recurrence disagrees")
        else:
            check(abs(got_share - expected_share) < 1e-9,
                  f"row {target_i}: naive={expected_share!r} recurrence={got_share!r}")
    check(bool(got["short_off_defined"].iloc[0]) is False,
          "the very first game in a team's history has an empty prior-game set by construction")
    return {"checked_rows": 5}


def t02c_strict_lagging():
    """A row's prior aggregate must depend ONLY on its team's STRICTLY earlier games: perturbing
    a LATER game's (or the SAME game's) possession counts must never change an earlier row's
    computed share; perturbing an EARLIER game's counts MUST change a later row's share."""
    poss = fx.build_possessions()
    hist = feat.aggregate_possession_counts(poss)
    base = feat.compute_prior_recency_aggregates(hist)

    team = hist["team_id"].iloc[0]
    team_rows = hist[hist["team_id"] == team].sort_values(["game_date", "game_id"])
    check(len(team_rows) >= 3, "fixture must give this team at least 3 games")
    first_gid = int(team_rows["game_id"].iloc[0])
    mid_gid = int(team_rows["game_id"].iloc[len(team_rows) // 2])
    last_gid = int(team_rows["game_id"].iloc[-1])

    perturbed = hist.copy()
    row_mask = (perturbed["team_id"] == team) & (perturbed["game_id"] == last_gid)
    check(row_mask.sum() == 1, "exactly one history row for the perturbation target")
    perturbed.loc[row_mask, "n_short_off"] = perturbed.loc[row_mask, "n_off"]     # force share=1
    reagg = feat.compute_prior_recency_aggregates(perturbed)

    base_first = base.loc[(base.team_id == team) & (base.game_id == first_gid), "short_off_share"]
    reagg_first = reagg.loc[(reagg.team_id == team) & (reagg.game_id == first_gid), "short_off_share"]
    check(base_first.reset_index(drop=True).equals(reagg_first.reset_index(drop=True)),
          "perturbing team's LAST game must not change its FIRST game's (earlier) feature")

    base_mid = base.loc[(base.team_id == team) & (base.game_id == mid_gid), "short_off_share"]
    reagg_mid = reagg.loc[(reagg.team_id == team) & (reagg.game_id == mid_gid), "short_off_share"]
    check(base_mid.reset_index(drop=True).equals(reagg_mid.reset_index(drop=True)),
          "perturbing team's LAST game must not change a MIDDLE (earlier) game's feature")

    # now perturb the FIRST game and confirm the LAST game's feature DOES move
    perturbed2 = hist.copy()
    row_mask2 = (perturbed2["team_id"] == team) & (perturbed2["game_id"] == first_gid)
    perturbed2.loc[row_mask2, "n_short_off"] = perturbed2.loc[row_mask2, "n_off"]
    reagg2 = feat.compute_prior_recency_aggregates(perturbed2)
    base_last = base.loc[(base.team_id == team) & (base.game_id == last_gid), "short_off_share"].iloc[0]
    reagg2_last = reagg2.loc[(reagg2.team_id == team) & (reagg2.game_id == last_gid), "short_off_share"].iloc[0]
    check(not np.isclose(base_last, reagg2_last),
          "perturbing an EARLIER game MUST move a strictly-later row's feature (sanity: the "
          "recurrence is not accidentally always returning a constant)")
    return {"team": str(team), "first_gid": first_gid, "mid_gid": mid_gid, "last_gid": last_gid}


def t03_p26_k0_contract():
    arm, df, folds, poss = _fresh_arm()
    rec = arm.p26_k0_record()
    out = gh.p26_check(rec)
    check(out["valid"], f"A17's k0_matched record must validate: {out['blocking_after_adjudication']}")

    # negative control: a null that let the treatment survive must be blocked, never adjudicated away
    bad = json.loads(json.dumps(rec))
    bad["k0_spec"]["substantive_features"] = [a17mod.TREATMENT_COL]
    expect_raises(gh.GuardHarnessFailure, lambda: gh.p26_check(bad),
                  "a null retaining the treatment term must be blocked")
    return {"valid": True}


def t04_p22_lag_declarations():
    arm, df, folds, poss = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    b = arm.build_design(folds[0], df)
    frame = df.copy()
    frame[a17mod.TREATMENT_COL] = b["columns"][a17mod.TREATMENT_COL]
    frame[a17mod.NUISANCE_COL] = b["columns"][a17mod.NUISANCE_COL]
    cols = [a17mod.TREATMENT_COL, a17mod.NUISANCE_COL]

    ok = gh.p22_check(frame, cols, prohibited_basis=basis, lag_specs=arm.lag_specs(),
                      lag_sources=arm.lag_sources())
    check(not ok["blocking"], "the frozen DERIVED_NO_JOIN/SCHEDULE lag declarations must pass P22")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, cols, prohibited_basis=basis, lag_specs={a17mod.NUISANCE_COL: arm.lag_specs()[a17mod.NUISANCE_COL]}),
        "missing LagSpec for the treatment column must block")

    expect_raises(gh.GuardHarnessFailure, lambda: gh.p22_check(
        frame, cols, prohibited_basis=basis,
        lag_specs={a17mod.TREATMENT_COL: {"column": a17mod.TREATMENT_COL, "kind": "SAME_GAME",
                                          "entity_keys": ("game_id",)},
                  a17mod.NUISANCE_COL: arm.lag_specs()[a17mod.NUISANCE_COL]}),
        "SAME_GAME must block unconditionally regardless of the column's true provenance")
    return {"p22_passed": True, "negative_paths": 2}


def t05_p25_offset_family():
    arm, df, folds, poss = _fresh_arm()
    fold = folds[0]
    b = arm.build_design(fold, df)
    frame = df.copy()
    frame[a17mod.TREATMENT_COL] = b["columns"][a17mod.TREATMENT_COL]
    frame[a17mod.NUISANCE_COL] = b["columns"][a17mod.NUISANCE_COL]
    tr = frame.iloc[fold["train_idx"]].reset_index(drop=True)
    rec = gh.p25_check(tr, candidate_features=[a17mod.TREATMENT_COL],
                       nuisance_features=[a17mod.NUISANCE_COL],
                       preregistered_contrasts=arm.preregistered_contrasts(),
                       prereg_digest_expected=arm.prereg_digest_expected())
    check(rec["passed"], "A17's transition-mix treatment must pass P25 under SUBSTANTIVE on the "
                        "synthetic fixture: it is not a function of the offset or the incumbent "
                        "projection")
    check(arm.declared_family() == rc.DECLARED_FAMILY_ALL_FITTED_ARMS
          and arm.recalibration_declaration() == rc.RECALIBRATION_DECLARATION,
          "guard_invocation pins from the frozen card")
    return {"p25_passed": True}


def t06_arm_null_nesting():
    """comparison is term_removal: arm design minus the treatment term must equal EXACTLY the
    null design (nesting) -- the null retains the is_playoff_game nuisance, never the treatment."""
    arm, df, folds, poss = _fresh_arm()
    b = arm.build_design(folds[0], df)
    arm_cols = set(b["treatment_cols"]) | set(b["nuisance_cols"])
    k0 = b["k0_matched_design"]
    null_cols = set(k0["treatment_cols"]) | set(k0["nuisance_cols"])
    check(arm_cols - null_cols == {a17mod.TREATMENT_COL},
          "removing exactly the treatment term from the arm design must yield the null design")
    check(null_cols == {a17mod.NUISANCE_COL},
          "A17's K0_MATCHED null must carry the is_playoff_game nuisance and nothing else")
    check(k0["comparison"] == "term_removal", "A17's frozen comparison type is term_removal")
    return {"arm_cols": sorted(arm_cols), "null_cols": sorted(null_cols)}


def t07_enumeration_element_exact():
    arm, df, folds, poss = _fresh_arm()
    check(arm.enumeration_element() == {}, "A17 carries no enumeration grid (single element -- "
                                          "LAGGED_TEMPO_MIX is a single-member family this cycle)")
    check(arm.element_id() == f"{a17mod.ARM_ID}__single", "element_id must be the frozen literal")
    for f in folds:
        check(arm.enumeration_element() == {}, f"enumeration_element must not vary by fold {f}")
        check(arm.element_id() == f"{a17mod.ARM_ID}__single", "element_id must not vary by fold")
    return {"enumeration_element": {}, "element_id": arm.element_id()}


def t08_kill_conditions_decidable():
    ev = a17mod.evaluate_kill_conditions

    passes = ev(p_value=0.01, delta_mae=0.05, alpha=0.05)
    check(not passes["killed"], "delta_MAE>0 and p<alpha must NOT be killed")

    fails_pvalue = ev(p_value=0.20, delta_mae=0.05, alpha=0.05)
    check(fails_pvalue["killed"] and fails_pvalue["reason"] == "score_lr_equivalent_bootstrap_test_failed",
          "p-value >= alpha must be decided KILLED (the score/LR-equivalent test failed)")

    fails_sign = ev(p_value=0.01, delta_mae=-0.02, alpha=0.05)
    check(fails_sign["killed"], "delta_MAE <= 0 must be decided KILLED even with a small p-value")

    p25 = ev(p_value=0.01, delta_mae=0.05, alpha=0.05, p25_rejected=True)
    check(p25["killed"] and p25["reason"] == "p25_rejection",
          "P25 rejection must be decided KILLED unconditionally, before any performance number")

    empty = ev(p_value=None, delta_mae=None)
    check(not empty["killed"] and empty["reason"] == "not_evaluable_no_manufactured_positive",
          "missing inputs must decide NOT killed with an honest reason, never a manufactured "
          "positive (standing rule 7)")
    return {"passes_not_killed": not passes["killed"], "pvalue_kill": fails_pvalue["killed"],
            "sign_kill": fails_sign["killed"], "p25_kill": p25["killed"]}


def t09_end_to_end_synthetic():
    arm, df, folds, poss = _fresh_arm()
    basis = fx.build_prohibited_basis(df)
    out_path = HERE / "artifacts" / "A17_receipt.json"
    t0 = time.time()
    # RUNNER_INTERFACE.md section 4 leaves SEASON_BLOCK vs EXPANDING_PRIOR_SEASONS open at the
    # shared-runner level; named explicitly here (same convention as A05's suite), since P33's
    # folds block is expanding-window by construction (D006).
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
        arm_names = set(e["point_fits"]["arm"]["column_names"])
        check(arm_names == {a17mod.TREATMENT_COL, a17mod.NUISANCE_COL},
              "the arm's fitted design must be exactly treatment + nuisance")
        null_names = set(e["point_fits"]["null"]["column_names"])
        check(null_names == {a17mod.NUISANCE_COL},
              "the null's fitted design must be exactly the nuisance term")

    check(rec["guard_records"]["p27"]["overall"] in
          ("PASS", "PASS_UNDER_PREREGISTERED_ACTIVE_SET"), "P27 verdict")
    check(rec["seeds"]["master_seed"] == rc.MASTER_SEED, "seed manifest master pin")

    # determinism: an identical second run must reproduce results and fold records exactly
    rec2 = rn.run_arm(arm, df, folds, prohibited_basis=basis, env={},
                      p27_fold_policy="EXPANDING_PRIOR_SEASONS", run_git=False)
    d1 = receipts.canonical_digest({"results": rec["results"], "folds": rec["folds"]})
    d2 = receipts.canonical_digest({"results": rec2["results"], "folds": rec2["folds"]})
    check(d1 == d2, "end-to-end run must be bit-reproducible")

    # blinding: the runner REFUSES a frame carrying a real fold id, flag absent
    bad_folds = [dict(folds[0], fold_id="train_lt_2024")]
    expect_raises(blinding.BlindingViolation,
                  lambda: rn.run_arm(arm, df, bad_folds, prohibited_basis=basis, env={}),
                  "runner must refuse real fold ids without P38_UNSEALED, for A17 too")
    return {"seconds": round(dt, 2), "results_digest": d1,
            "note": "synthetic-only numbers; no real fold was touched"}


def t10_frozen_card_pins():
    p35 = gh.STAGE2B / "P35_FREEZE_TASK_CARDS" / "SPEC.json"
    check(receipts.sha256_file(p35) == a17mod.P35_SPEC_SHA256 == rc.P35_SPEC_SHA256,
          "P35 SPEC bytes unchanged on disk and match this module's own pin")
    check(a17mod.ARM_ID == "A17_transition_mix_share", "arm_id literal pin")
    check(a17mod.TREATMENT_COL not in ("intercept",), "treatment column must never be the "
                                                       "structural intercept name")
    check(a17mod.NUISANCE_COL not in ("intercept",), "nuisance column must never be the "
                                                      "structural intercept name")
    return {"p35_verified": True}


TESTS = [
    ("T01_module_conformance", t01_module_conformance),
    ("T02_feature_determinism_and_bundle", t02_feature_determinism_and_bundle),
    ("T02b_recency_weight_matches_naive_definition", t02b_recency_weight_matches_naive_definition),
    ("T02c_strict_lagging", t02c_strict_lagging),
    ("T03_p26_k0_contract", t03_p26_k0_contract),
    ("T04_p22_lag_declarations", t04_p22_lag_declarations),
    ("T05_p25_offset_family", t05_p25_offset_family),
    ("T06_arm_null_nesting", t06_arm_null_nesting),
    ("T07_enumeration_element_exact", t07_enumeration_element_exact),
    ("T08_kill_conditions_decidable", t08_kill_conditions_decidable),
    ("T09_end_to_end_synthetic", t09_end_to_end_synthetic),
    ("T10_frozen_card_pins", t10_frozen_card_pins),
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
        "schema": "a17_arm_test_receipt/1",
        "arm_id": a17mod.ARM_ID,
        "epistemic_status": ("IMPLEMENTATION. Blinded: no agent may inspect challenger "
                             "performance. Unit, synthetic, identity and schema tests only."),
        "unseal_flag_absent": rc.UNSEAL_ENV_FLAG not in os.environ,
        "n_tests": len(TESTS), "n_passed": n_pass,
        "results": RESULTS,
    }
    out = ARM_DIR / "TEST_RECEIPT_A17.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\n{n_pass}/{len(TESTS)} passed -> {out}")
    return 0 if n_pass == len(TESTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
