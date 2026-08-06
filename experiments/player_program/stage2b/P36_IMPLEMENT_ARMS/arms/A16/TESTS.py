#!/usr/bin/env python3
"""TESTS.py -- A16_lag_residual_own_minus_opp (P36_IMPLEMENT_ARMS/arms/A16).

Standalone runnable test script (pytest is not assumed available -- matches the P22/P26/P27
convention in this program). main() returns 0 on success, 1 on any failure.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no challenger performance is inspected here. Every
fixture below is SYNTHETIC (invented numbers on invented team/game ids); nothing here reads any
real artifact under experiments/player_program/. Only unit, synthetic, identity and schema tests
exist in this file, per the P36 mandate:

  * T01  feature determinism -- build_design is a pure function of (fold, universe); repeated
         calls on the same input produce byte-identical columns
  * T02  fold-independence -- the SAME construction runs regardless of which fold dict is passed
         (dev_own/dev_opp is not a training-fold-estimated constant, unlike A13/A17's imputation
         means), and the arm/null design-column NAME sets never drift across folds
  * T03  strict lagging -- a row's own realised/projected values never enter its own dev_team;
         perturbing row i's target changes only STRICTLY LATER rows of the same team, never row i
         itself and never any strictly earlier row
  * T04  k=5 cap -- the trailing window never averages over more than 5 prior games, even when
         more exist
  * T05  empty/partial-window rule -- a team's first game gets dev_team := 0 (P35 point 4); a
         team's 2nd-5th games use a partial window as-is (P35 point 3)
  * T06  hand-computed value check -- the constructed contrast matches an independent, non-pandas
         re-derivation on a small synthetic universe, exactly
  * T07  arm-vs-null design nesting -- K0's treatment/nuisance columns are the EMPTY subset of the
         arm's; RUNNER_INTERFACE.md's validate_design_bundle accepts the bundle, including the
         no-intercept invariant (A16 is in ARMS_WITHOUT_GLOBAL_INTERCEPT)
  * T08  enumeration element is exact -- {} (k=5 is a fixed constant, not a grid; RUNNER_INTERFACE
         section 1), element_id() is deterministic
  * T09  runner conformance -- runner_interface.validate_arm_module accepts this module as an arm
         module object (every required hook present and correctly typed)
  * T10  P26 k0_matched/1 record is schema- and relation-valid (validate_k0_matched.validate)
  * T11  kill-condition hooks are decidable -- exactly one tested_parameter named "beta",
         role "coefficient", null_value 0.0, so "the 95% bootstrap interval for beta covers 0 in
         every evaluable fold" (P35 kill_conditions_frozen) is a well-defined, locatable check
         against this record, not an ambiguous one
  * T12  P22 lag declaration is DERIVED_NO_JOIN (not SAME_GAME, not an unverifiable PRIOR_GAME
         claim), and postgame_surrogate_guard.audit raises no blocking finding for this column
         against a synthetic prohibited basis carrying no relationship to the treatment column
  * T13  franchise-continuity receipt pins team_cities.csv at the frozen P35 sha256 and
         requires_franchise_continuity() is True (A16 is named in P33
         shared_arm_invariants.p23_franchise_continuity_precondition)
  * T14  two-sided universe invariant enforced -- a universe missing an opponent's row for some
         game_id raises rather than silently producing NaN

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A16/TESTS.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_a16 as A                                                             # noqa: E402

RUNNER_DIR = HERE.parents[1] / "runner"
P26_DIR = HERE.parents[2] / "P26_ARM_SPECIFIC_K0_CONTRACT"
for _p in (RUNNER_DIR, P26_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import runner_interface as ri                                                   # noqa: E402
import validate_k0_matched as vk                                                # noqa: E402
import postgame_surrogate_guard as psg                                          # noqa: E402

FAILURES: list[str] = []


def check(cond: bool, label: str, extra: object = "") -> None:
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {extra}")
        FAILURES.append(label)


# ---------------------------------------------------------------------------------------------
# synthetic fixture -- two teams, 8 meetings, purely invented numbers
# ---------------------------------------------------------------------------------------------

def synthetic_universe(n_games: int = 8, seed: int = 0) -> pd.DataFrame:
    """Two teams (100, 200) meeting ``n_games`` times on consecutive days. Every row carries
    exactly the columns build_design/P22/P25 need. dev sequences are hand-chosen so T06 can
    independently recompute the expected trailing means without re-using arm_a16's own code."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n_games, freq="D")
    game_ids = [1000 + i for i in range(n_games)]

    proj1 = 80.0 + rng.normal(0, 0.01, n_games)   # near-constant projection, team 100
    proj2 = 82.0 + rng.normal(0, 0.01, n_games)   # near-constant projection, team 200
    dev1 = np.array([1.0, -2.0, 3.0, 0.5, -1.5, 4.0, -0.5, 2.0])[:n_games]
    dev2 = np.array([-1.0, 2.0, -3.0, 1.0, 0.5, -2.0, 1.5, -1.0])[:n_games]
    real1 = proj1 + dev1
    real2 = proj2 + dev2

    rows = []
    for i in range(n_games):
        rows.append({"game_id": game_ids[i], "team_id": 100, "opp_team_id": 200,
                    "game_date": dates[i], "season": 2024,
                    A.PROJECTION_COL: proj1[i], A.TARGET_COL: real1[i],
                    A.OFFSET_COL: np.log(proj1[i])})
        rows.append({"game_id": game_ids[i], "team_id": 200, "opp_team_id": 100,
                    "game_date": dates[i], "season": 2024,
                    A.PROJECTION_COL: proj2[i], A.TARGET_COL: real2[i],
                    A.OFFSET_COL: np.log(proj2[i])})
    df = pd.DataFrame(rows).reset_index(drop=True)
    return df


def expected_trailing(devs: list[float], k: int) -> list[float]:
    """Independent (non-pandas-rolling) re-derivation of dev_team for a single team's own
    chronological dev sequence: mean of the last <= k STRICTLY earlier values, 0 if none."""
    out = []
    for i in range(len(devs)):
        window = devs[max(0, i - k):i]
        out.append(float(np.mean(window)) if window else 0.0)
    return out


def dummy_fold(universe: pd.DataFrame, fold_id: str = "SYNTH") -> dict:
    n = len(universe)
    return {"fold_id": fold_id, "train_idx": np.arange(n), "test_idx": np.empty(0, int)}


# ---------------------------------------------------------------------------------------------
def main() -> int:
    U = synthetic_universe()

    print("T01 feature determinism")
    b1 = A.build_design(dummy_fold(U), U)
    b2 = A.build_design(dummy_fold(U), U)
    check(np.array_equal(b1["columns"][A.TREATMENT_COL], b2["columns"][A.TREATMENT_COL]),
          "repeated build_design calls are byte-identical")

    print("T02 fold-independence")
    fold_a = {"fold_id": "train_lt_2025", "train_idx": np.arange(0, 6), "test_idx": np.arange(6, 8)}
    fold_b = {"fold_id": "FINAL_ASSEMBLED_DESIGN", "train_idx": np.arange(len(U)),
              "test_idx": np.empty(0, int)}
    ba = A.build_design(fold_a, U)
    bb = A.build_design(fold_b, U)
    check(np.array_equal(ba["columns"][A.TREATMENT_COL], bb["columns"][A.TREATMENT_COL]),
          "construction does not depend on which fold dict is passed")
    check(list(ba["treatment_cols"]) == list(bb["treatment_cols"]) and
          list(ba["nuisance_cols"]) == list(bb["nuisance_cols"]),
          "design column NAME sets are identical across folds")

    print("T03 strict lagging (no leakage from a row into its own or any earlier row's feature)")
    base = A.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL].copy()
    U2 = U.copy()
    # perturb team 100's LAST game's realised value hugely
    last_row = U2[(U2["team_id"] == 100)].index[-1]
    U2.loc[last_row, A.TARGET_COL] += 1000.0
    perturbed = A.build_design(dummy_fold(U2), U2)["columns"][A.TREATMENT_COL]
    check(np.isclose(perturbed[last_row], base[last_row]),
          "perturbing a row's OWN target does not change that row's OWN contrast value "
          "(shift(1) excludes the current row)")
    earlier_rows = U2[(U2["team_id"].isin([100, 200]))].index[:-2]
    check(np.allclose(perturbed[earlier_rows], base[earlier_rows]),
          "perturbing the LAST game's target does not change any strictly earlier row")

    print("T04 k=5 cap")
    devs100 = [1.0, -2.0, 3.0, 0.5, -1.5, 4.0, -0.5, 2.0]
    exp100 = expected_trailing(devs100, k=A.K_WINDOW_GAMES)
    # by construction, row for the 7th game (index 6, 0-based) has 6 prior games available;
    # the k=5 cap must exclude the OLDEST of the 6 (index 0's dev = 1.0)
    manual_all6 = float(np.mean(devs100[0:6]))
    manual_last5 = float(np.mean(devs100[1:6]))
    check(abs(exp100[6] - manual_last5) < 1e-12 and abs(exp100[6] - manual_all6) > 1e-9,
          "the independent re-derivation itself respects the k=5 cap (sanity check on the test's "
          "own oracle)")

    print("T05 empty/partial-window rule")
    b = A.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL]
    own100 = A._own_trailing_dev(U)
    first100_idx = U[(U["team_id"] == 100)].index[0]
    check(own100.loc[first100_idx] == 0.0, "a team's first game gets dev_team := 0")
    third100_idx = U[(U["team_id"] == 100)].index[2]
    expected_partial = float(np.mean(devs100[0:2]))
    check(abs(own100.loc[third100_idx] - expected_partial) < 1e-9,
          "a team's 3rd game uses a partial (2-game) window as-is", own100.loc[third100_idx])

    print("T06 hand-computed value check (independent oracle, no shared code with arm_a16)")
    b_series = pd.Series(b, index=U.index)
    devs200 = [-1.0, 2.0, -3.0, 1.0, 0.5, -2.0, 1.5, -1.0]
    exp_own100 = expected_trailing(devs100, A.K_WINDOW_GAMES)
    exp_own200 = expected_trailing(devs200, A.K_WINDOW_GAMES)
    expected_contrast = [o - p for o, p in zip(exp_own100, exp_own200)]
    got_100 = [b_series.loc[U[(U["team_id"] == 100) & (U["game_id"] == 1000 + i)].index[0]]
              for i in range(8)]
    check(all(abs(g - e) < 1e-9 for g, e in zip(got_100, expected_contrast)),
          "constructed dev_own - dev_opp matches an independent re-derivation for every game "
          "of team 100", list(zip(got_100, expected_contrast)))
    got_200 = [b_series.loc[U[(U["team_id"] == 200) & (U["game_id"] == 1000 + i)].index[0]]
              for i in range(8)]
    expected_contrast_200 = [p - o for o, p in zip(exp_own100, exp_own200)]
    check(all(abs(g - e) < 1e-9 for g, e in zip(got_200, expected_contrast_200)),
          "constructed dev_own - dev_opp matches an independent re-derivation for every game "
          "of team 200 (own/opp correctly swapped)")

    print("T07 arm-vs-null design nesting + RUNNER_INTERFACE bundle validation")
    bundle = A.build_design(dummy_fold(U), U)
    k0 = bundle["k0_matched_design"]
    check(k0["treatment_cols"] == [] and k0["nuisance_cols"] == [],
          "K0's design is the empty subset of the arm's (term_removal null)")
    check(set(bundle["treatment_cols"]) <= set(bundle["treatment_cols"]) and
          set(k0["treatment_cols"] + k0["nuisance_cols"]) <=
          set(bundle["treatment_cols"] + bundle["nuisance_cols"]),
          "K0's columns are a subset of the arm's columns (nesting)")
    try:
        bval = ri.validate_design_bundle(bundle, U, A.uses_global_intercept(), "SYNTH")
        check(bval["valid"], "validate_design_bundle accepts the bundle", bval)
    except ri.ArmModuleNonconformant as e:
        check(False, "validate_design_bundle accepts the bundle", e.problems)

    print("T08 enumeration element is exact")
    check(A.enumeration_element() == {}, "enumeration_element() == {} (k=5 fixed, not a grid)")
    check(A.element_id() == A.ARM_ID, "element_id() is deterministic", A.element_id())
    check(A.card_id() == A.arm_id == A.ARM_ID, "card_id()/arm_id/ARM_ID agree")

    print("T09 runner conformance (runner_interface.validate_arm_module)")
    try:
        conf = ri.validate_arm_module(A)
        check(conf["conformant"], "module passes validate_arm_module", conf)
    except ri.ArmModuleNonconformant as e:
        check(False, "module passes validate_arm_module", e.problems)
    check(A.declared_family() == "SUBSTANTIVE", "declared_family pinned to SUBSTANTIVE")
    check(A.recalibration_declaration() == "NOT_APPLICABLE", "recalibration_declaration pinned")
    check(A.uses_global_intercept() is False, "uses_global_intercept() is False (frozen table)")

    print("T10 P26 k0_matched/1 record validity")
    rec = A.p26_k0_record()
    rep = vk.validate(rec)
    check(rep["valid"], "p26_k0_record() validates against K0_MATCHED_SCHEMA + relation rules",
          rep["blocking"])

    print("T11 kill-condition hooks are decidable")
    params = rec["treatment_mechanism"]["tested_parameters"]
    check(len(params) == 1, "exactly one tested parameter is declared", params)
    p = params[0] if params else {}
    check(p.get("name") == "beta" and p.get("role") == "coefficient" and
          p.get("null_value") == 0.0,
          "the sole tested parameter is 'beta', role coefficient, null_value 0 -- the P35 "
          "kill condition 'beta interval covers 0 in every evaluable fold' names a single, "
          "locatable quantity in this record", p)
    check(rec["treatment_mechanism"]["treatment_terms"] == [A.TREATMENT_COL],
          "treatment_terms matches the single materialised design column exactly, so a P25 "
          "rejection (withdrawal) kill condition also resolves unambiguously to this column")

    print("T12 P22 lag declaration (DERIVED_NO_JOIN, dependency battery clean)")
    specs_kw = A.lag_specs()
    check(set(specs_kw) == {A.TREATMENT_COL}, "exactly one column carries a LagSpec")
    spec = psg.LagSpec(**specs_kw[A.TREATMENT_COL])
    check(spec.kind == psg.DERIVED_NO_JOIN, "declared kind is DERIVED_NO_JOIN, not SAME_GAME",
          spec.kind)
    frame_for_guard = U.copy()
    frame_for_guard[A.TREATMENT_COL] = bundle["columns"][A.TREATMENT_COL]
    rng = np.random.default_rng(1)
    # a REALISTIC synthetic prohibited basis is low-cardinality (game_minutes/overtime_periods
    # take a handful of discrete values across a whole universe, never one distinct value per
    # row) -- draw from a small integer alphabet, independent of the treatment column, so the
    # partition test can discriminate genuine dependence from a per-row-unique artifact
    prohibited = psg.ProhibitedBasis(
        frame=pd.DataFrame({"synthetic_prohibited_quantity":
                            rng.integers(0, 4, size=len(U)).astype(float)}, index=U.index),
        source={"synthetic": True}, note="synthetic prohibited basis for A16 unit tests; low-"
                                         "cardinality by construction (matches the real "
                                         "game_minutes/overtime_periods basis shape), no "
                                         "relationship to any real prohibited quantity")
    try:
        audit = psg.audit(frame_for_guard, [A.TREATMENT_COL], prohibited=prohibited,
                          lag_specs={A.TREATMENT_COL: spec}, lag_sources=A.lag_sources(),
                          raise_on_block=True)
        check(audit["passed"], "P22 audit raises no blocking finding for the declared column",
              audit["findings"])
    except psg.PostgameSurrogateFailure as e:
        check(False, "P22 audit raises no blocking finding for the declared column", str(e))

    print("T13 franchise-continuity receipt")
    check(A.requires_franchise_continuity() is True,
          "requires_franchise_continuity() is True (A16 named in P33 p23_franchise_continuity_precondition)")
    receipts = A.p23_receipts()
    check(isinstance(receipts, list) and len(receipts) >= 1, "p23_receipts() returns >= 1 receipt")
    check(all(str(r.get("team_cities_sha256", "")).lower() == A.TEAM_CITIES_SHA256_PIN
              for r in receipts),
          "every receipt pins team_cities.csv at the frozen P35 sha256", receipts)

    print("T14 two-sided universe invariant enforced")
    U_broken = U[~((U["team_id"] == 200) & (U["game_id"] == 1000))].reset_index(drop=True)
    try:
        A.build_design(dummy_fold(U_broken), U_broken)
        check(False, "a universe missing an opponent row raises rather than silently NaN-ing")
    except ValueError as e:
        check(True, "a universe missing an opponent row raises rather than silently NaN-ing",
              str(e))

    print()
    print("=" * 88)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
