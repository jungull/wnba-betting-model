#!/usr/bin/env python3
"""TESTS.py -- A20_forced_turnover_contrast (P36_IMPLEMENT_ARMS/arms/A20).

Standalone runnable test script (pytest is not assumed available -- matches the P22/P26/P27/A16
convention in this program). main() returns 0 on success, 1 on any failure.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no challenger performance is inspected here. Every
fixture below is SYNTHETIC (invented numbers on invented team/game/possession ids); nothing here
reads any real artifact under experiments/player_program/. Only unit, synthetic, identity and
schema tests exist in this file, per the P36 mandate:

  * T01  feature determinism -- build_design is a pure function of (fold, universe); repeated
         calls on the same input produce byte-identical columns
  * T02  fold-independence -- the SAME construction runs regardless of which fold dict is passed
         (ftr_own/ftr_opp are not training-fold-estimated constants), and the arm/null
         design-column NAME sets never drift across folds
  * T03  strict lagging -- a game's own possession-level rows never enter that SAME game's own
         z2; perturbing a game's end_reason mix changes only STRICTLY LATER same-season rows of
         the same team, never that game's own row and never any strictly earlier row
  * T04  same-season-only window -- a team's trailing rate NEVER reaches back across a season
         boundary, unlike A16's cross-season k=5 window (E=3 imputation additionally zeroes it
         out early, but this checks the window itself, isolated from the E=3 rule)
  * T05  E=3 imputation -- z2 := 0 whenever EITHER side has < 3 strictly-earlier same-season
         games, even when the raw contrast would be nonzero
  * T06  hand-computed value check -- the constructed z2 matches an independent, non-pandas
         re-derivation on a small synthetic universe + possessions frame, exactly
  * T07  dictionary determinism -- E_TO = {"turnover"} exactly; a possession with any other
         end_reason never contributes to a team's turnover-forced numerator
  * T08  arm-vs-null design nesting -- K0's treatment/nuisance columns are the EMPTY subset of the
         arm's; RUNNER_INTERFACE.md's validate_design_bundle accepts the bundle, including the
         no-intercept invariant (A20 is in ARMS_WITHOUT_GLOBAL_INTERCEPT)
  * T09  enumeration element is exact -- {} (no grid; RUNNER_INTERFACE section 1), element_id() is
         deterministic
  * T10  runner conformance -- runner_interface.validate_arm_module accepts an ArmA20 instance as
         an arm module object (every required hook present and correctly typed)
  * T11  P26 k0_matched/1 record is schema- and relation-valid (validate_k0_matched.validate)
  * T12  kill-condition hooks are decidable -- exactly one tested_parameter named "beta2", role
         "coefficient", null_value 0, so "the 95% bootstrap interval for beta2 covers 0 in every
         evaluable fold" (P35 kill_conditions_frozen) is a well-defined, locatable check against
         this record, not an ambiguous one
  * T13  P22 lag declaration is DERIVED_NO_JOIN (not SAME_GAME, not an unverifiable PRIOR_GAME
         claim), and postgame_surrogate_guard.audit raises no blocking finding for this column
         against a synthetic prohibited basis carrying no relationship to the treatment column
  * T14  franchise continuity is False (A20's same-season-flat window has no cross-season
         dependency; card is absent from P33's p23_franchise_continuity_precondition list)
  * T15  two-sided universe invariant enforced -- a universe missing an opponent's row for some
         game_id raises rather than silently producing NaN
  * T16  malformed possessions input (missing required columns, a universe row whose team-game
         pair is absent from the possessions frame) raises rather than silently producing a
         wrong/NaN rate

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A20/TESTS.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_a20 as A                                                             # noqa: E402

RUNNER_DIR = HERE.parents[1] / "runner"
P26_DIR = HERE.parents[2] / "P26_ARM_SPECIFIC_K0_CONTRACT"
P22_DIR = HERE.parents[2] / "P22_POSTGAME_SURROGATE_GUARD"
for _p in (RUNNER_DIR, P26_DIR, P22_DIR):
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
# synthetic fixture -- two teams, 6 same-season meetings + a 2nd season, purely invented numbers
# ---------------------------------------------------------------------------------------------

# team 100's defensive share of turnover-terminator possessions in each of its games, in
# chronological order within season 2024 (index 0..5); team 200's likewise.
FTR_100 = [0.30, 0.10, 0.50, 0.20, 0.40, 0.60]
FTR_200 = [0.20, 0.40, 0.10, 0.50, 0.30, 0.10]
N_DEF_PER_GAME = 20          # constant defensive-possession count per team per game, for simplicity


def synthetic_universe(n_games: int = 6, season: int = 2024) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n_games, freq="D")
    game_ids = [1000 + i for i in range(n_games)]
    rows = []
    for i in range(n_games):
        rows.append({"game_id": game_ids[i], "team_id": 100, "opp_team_id": 200,
                    "game_date": dates[i], "season": season})
        rows.append({"game_id": game_ids[i], "team_id": 200, "opp_team_id": 100,
                    "game_date": dates[i], "season": season})
    return pd.DataFrame(rows).reset_index(drop=True)


def synthetic_possessions(n_games: int = 6, game_id_offset: int = 1000) -> pd.DataFrame:
    """Possession-level rows reproducing FTR_100/FTR_200 exactly: N_DEF_PER_GAME defensive
    possessions per team per game, with round(FTR * N_DEF_PER_GAME) of them end_reason="turnover"
    and the rest a mix of other, non-turnover end_reason values (never counted)."""
    rows = []
    for i in range(n_games):
        gid = game_id_offset + i
        for team, ftr_seq in ((100, FTR_100), (200, FTR_200)):
            n_to = round(ftr_seq[i] * N_DEF_PER_GAME)
            for k in range(N_DEF_PER_GAME):
                end_reason = "turnover" if k < n_to else ("made_shot" if k % 2 == 0 else "missed_shot")
                rows.append({"game_id": gid, "defense_team_id": team, "end_reason": end_reason,
                            "possession_id": f"{gid}-{team}-{k}"})
    return pd.DataFrame(rows)


def expected_trailing_expanding(ftrs: list[float]) -> list[float]:
    """Independent (non-pandas) re-derivation: mean of ALL strictly-earlier values, 0 if none."""
    out = []
    for i in range(len(ftrs)):
        window = ftrs[:i]
        out.append(float(np.mean(window)) if window else 0.0)
    return out


def dummy_fold(universe: pd.DataFrame, fold_id: str = "SYNTH") -> dict:
    n = len(universe)
    return {"fold_id": fold_id, "train_idx": np.arange(n), "test_idx": np.empty(0, int)}


# ---------------------------------------------------------------------------------------------
def main() -> int:
    U = synthetic_universe()
    P = synthetic_possessions()
    arm = A.ArmA20(P, fold_ids=["SYNTH"], n_rows=len(U))

    print("T01 feature determinism")
    b1 = arm.build_design(dummy_fold(U), U)
    b2 = arm.build_design(dummy_fold(U), U)
    check(np.array_equal(b1["columns"][A.TREATMENT_COL], b2["columns"][A.TREATMENT_COL]),
          "repeated build_design calls are byte-identical")

    print("T02 fold-independence")
    fold_a = {"fold_id": "train_lt_2025", "train_idx": np.arange(0, 8), "test_idx": np.arange(8, 12)}
    fold_b = {"fold_id": "FINAL_ASSEMBLED_DESIGN", "train_idx": np.arange(len(U)),
              "test_idx": np.empty(0, int)}
    ba = arm.build_design(fold_a, U)
    bb = arm.build_design(fold_b, U)
    check(np.array_equal(ba["columns"][A.TREATMENT_COL], bb["columns"][A.TREATMENT_COL]),
          "construction does not depend on which fold dict is passed")
    check(list(ba["treatment_cols"]) == list(bb["treatment_cols"]) and
          list(ba["nuisance_cols"]) == list(bb["nuisance_cols"]),
          "design column NAME sets are identical across folds")

    print("T03 strict lagging (no leakage from a game's own rows into that game's own z2)")
    base = arm.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL].copy()
    P2 = P.copy()
    # perturb team 100's LAST game (index 5): flip every non-turnover possession to turnover
    last_gid = 1000 + 5
    mask = (P2["game_id"] == last_gid) & (P2["defense_team_id"] == 100)
    P2.loc[mask, "end_reason"] = "turnover"
    arm2 = A.ArmA20(P2, fold_ids=["SYNTH"], n_rows=len(U))
    perturbed = arm2.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL]
    last_row_100 = U[(U["team_id"] == 100) & (U["game_id"] == last_gid)].index[0]
    check(np.isclose(perturbed[last_row_100], base[last_row_100]),
          "perturbing a game's OWN possession mix does not change that SAME game's own z2 "
          "(the game's own rate never enters its own trailing mean)")
    earlier_rows = U[(U["game_id"] < last_gid)].index
    check(np.allclose(perturbed[earlier_rows], base[earlier_rows]),
          "perturbing the LAST game's possession mix does not change any strictly earlier row")

    print("T04 same-season-only window (no cross-season reach)")
    U2 = synthetic_universe(n_games=2, season=2025)
    U2["game_id"] = U2["game_id"] + 500          # disjoint game ids from season-2024 fixture
    P2s = synthetic_possessions(n_games=2, game_id_offset=1500)
    U_multi = pd.concat([U, U2], ignore_index=True)
    P_multi = pd.concat([P, P2s], ignore_index=True)
    arm_multi = A.ArmA20(P_multi, fold_ids=["SYNTH"], n_rows=len(U_multi))
    own = arm_multi._own_trailing_rate(U_multi)
    first_2025_row = U_multi[(U_multi["team_id"] == 100) & (U_multi["season"] == 2025)].index[0]
    check(own.loc[first_2025_row, "own_count"] == 0.0,
          "a team's first game of a NEW season has own_count 0, even though it played 6 games "
          "the PRIOR season (same-season flat window never crosses the season boundary)")

    print("T05 E=3 imputation (z2 := 0 when either side has < 3 strictly-earlier same-season games)")
    b = arm.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL]
    for i in range(2):     # games 0 and 1 (0-based): own_count < 3 for BOTH teams
        gid = 1000 + i
        row100 = U[(U["team_id"] == 100) & (U["game_id"] == gid)].index[0]
        row200 = U[(U["team_id"] == 200) & (U["game_id"] == gid)].index[0]
        check(b[row100] == 0.0 and b[row200] == 0.0,
              f"game index {i}: z2 forced to 0 for both teams (own_count < 3)", (b[row100], b[row200]))
    row3_100 = U[(U["team_id"] == 100) & (U["game_id"] == 1003)].index[0]  # 3 prior games each side
    check(b[row3_100] != 0.0,
          "game index 3: both teams have exactly 3 strictly-earlier same-season games; the E=3 "
          "floor is satisfied and z2 is the RAW (non-imputed) contrast", b[row3_100])

    print("T06 hand-computed value check (independent oracle, no shared code with arm_a20)")
    exp_own100 = expected_trailing_expanding(FTR_100)
    exp_own200 = expected_trailing_expanding(FTR_200)
    b_series = pd.Series(b, index=U.index)
    for i in range(6):
        gid = 1000 + i
        r100 = U[(U["team_id"] == 100) & (U["game_id"] == gid)].index[0]
        r200 = U[(U["team_id"] == 200) & (U["game_id"] == gid)].index[0]
        insufficient = i < 3   # both sides have i strictly-earlier same-season games
        expected_100 = 0.0 if insufficient else (exp_own100[i] - exp_own200[i])
        expected_200 = 0.0 if insufficient else (exp_own200[i] - exp_own100[i])
        check(abs(b_series.loc[r100] - expected_100) < 1e-9,
              f"game {i}: team 100's z2 matches independent re-derivation",
              (b_series.loc[r100], expected_100))
        check(abs(b_series.loc[r200] - expected_200) < 1e-9,
              f"game {i}: team 200's z2 matches independent re-derivation (own/opp swapped)",
              (b_series.loc[r200], expected_200))

    print("T07 dictionary determinism (E_TO = {'turnover'} exactly)")
    check(A.E_TO == frozenset({"turnover"}), "E_TO is exactly the frozen single-level dictionary")
    rate_check = A.aggregate_game_team_rate(P)
    manual_rate_100_g0 = FTR_100[0]
    check(abs(rate_check.loc[(100, 1000)] - manual_rate_100_g0) < 1e-9,
          "aggregate_game_team_rate reproduces the exact fixture rate for team 100's first game",
          (rate_check.loc[(100, 1000)], manual_rate_100_g0))
    P_relabel = P.copy()
    P_relabel.loc[P_relabel["end_reason"] == "made_shot", "end_reason"] = "SOME_OTHER_NONTURNOVER_LABEL"
    rate_relabel = A.aggregate_game_team_rate(P_relabel)
    check(np.isclose(rate_relabel.loc[(100, 1000)], rate_check.loc[(100, 1000)]),
          "relabelling a NON-turnover end_reason string leaves the rate unchanged (only exact "
          "membership in the frozen E_TO set matters, nothing else)")

    print("T08 arm-vs-null design nesting + RUNNER_INTERFACE bundle validation")
    bundle = arm.build_design(dummy_fold(U), U)
    k0 = bundle["k0_matched_design"]
    check(k0["treatment_cols"] == [] and k0["nuisance_cols"] == [],
          "K0's design is the empty subset of the arm's (term_removal null)")
    try:
        bval = ri.validate_design_bundle(bundle, U, arm.uses_global_intercept(), "SYNTH")
        check(bval["valid"], "validate_design_bundle accepts the bundle", bval)
    except ri.ArmModuleNonconformant as e:
        check(False, "validate_design_bundle accepts the bundle", e.problems)

    print("T09 enumeration element is exact")
    check(arm.enumeration_element() == {}, "enumeration_element() == {} (no grid)")
    check(arm.element_id() == A.ARM_ID, "element_id() is deterministic", arm.element_id())
    check(arm.card_id() == arm.arm_id == A.ARM_ID, "card_id()/arm_id/ARM_ID agree")

    print("T10 runner conformance (runner_interface.validate_arm_module)")
    try:
        conf = ri.validate_arm_module(arm)
        check(conf["conformant"], "module passes validate_arm_module", conf)
    except ri.ArmModuleNonconformant as e:
        check(False, "module passes validate_arm_module", e.problems)
    check(arm.declared_family() == "SUBSTANTIVE", "declared_family pinned to SUBSTANTIVE")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "recalibration_declaration pinned")
    check(arm.uses_global_intercept() is False, "uses_global_intercept() is False (frozen table)")

    print("T11 P26 k0_matched/1 record validity")
    rec = arm.p26_k0_record()
    rep = vk.validate(rec)
    check(rep["valid"], "p26_k0_record() validates against K0_MATCHED_SCHEMA + relation rules",
          rep["blocking"])

    print("T12 kill-condition hooks are decidable")
    params = rec["treatment_mechanism"]["tested_parameters"]
    check(len(params) == 1, "exactly one tested parameter is declared", params)
    p = params[0] if params else {}
    check(p.get("name") == "beta2" and p.get("role") == "coefficient" and
          p.get("null_value") == 0,
          "the sole tested parameter is 'beta2', role coefficient, null_value 0 -- the P35 kill "
          "condition 'beta2 interval covers 0' names a single, locatable quantity in this record",
          p)
    check(rec["treatment_mechanism"]["treatment_terms"] == [A.TREATMENT_COL],
          "treatment_terms matches the single materialised design column exactly")

    print("T13 P22 lag declaration (DERIVED_NO_JOIN, dependency battery clean)")
    specs_kw = arm.lag_specs()
    check(set(specs_kw) == {A.TREATMENT_COL}, "exactly one column carries a LagSpec")
    spec = psg.LagSpec(**specs_kw[A.TREATMENT_COL])
    check(spec.kind == psg.DERIVED_NO_JOIN, "declared kind is DERIVED_NO_JOIN, not SAME_GAME",
          spec.kind)
    frame_for_guard = U.copy()
    frame_for_guard[A.TREATMENT_COL] = bundle["columns"][A.TREATMENT_COL]
    rng = np.random.default_rng(1)
    prohibited = psg.ProhibitedBasis(
        frame=pd.DataFrame({"synthetic_prohibited_quantity":
                            rng.integers(0, 4, size=len(U)).astype(float)}, index=U.index),
        source={"synthetic": True}, note="synthetic prohibited basis for A20 unit tests; "
                                         "low-cardinality by construction, no relationship to any "
                                         "real prohibited quantity")
    try:
        audit = psg.audit(frame_for_guard, [A.TREATMENT_COL], prohibited=prohibited,
                          lag_specs={A.TREATMENT_COL: spec}, lag_sources=arm.lag_sources(),
                          raise_on_block=True)
        check(audit["passed"], "P22 audit raises no blocking finding for the declared column",
              audit["findings"])
    except psg.PostgameSurrogateFailure as e:
        check(False, "P22 audit raises no blocking finding for the declared column", str(e))

    print("T14 franchise continuity is False")
    check(arm.requires_franchise_continuity() is False,
          "requires_franchise_continuity() is False (A20 absent from P33 "
          "p23_franchise_continuity_precondition; same-season-flat window has no cross-season "
          "dependency)")
    check(arm.p23_receipts() == [], "p23_receipts() returns an empty list")

    print("T15 two-sided universe invariant enforced")
    U_broken = U[~((U["team_id"] == 200) & (U["game_id"] == 1000))].reset_index(drop=True)
    try:
        arm.build_design(dummy_fold(U_broken), U_broken)
        check(False, "a universe missing an opponent row raises rather than silently NaN-ing")
    except A.A20ConstructionFailure as e:
        check(True, "a universe missing an opponent row raises rather than silently NaN-ing",
              str(e))

    print("T16 malformed possessions input raises rather than silently mis-scoring")
    try:
        A.aggregate_game_team_rate(P.drop(columns=["end_reason"]))
        check(False, "missing end_reason column raises A20ConstructionFailure")
    except A.A20ConstructionFailure as e:
        check(True, "missing end_reason column raises A20ConstructionFailure", str(e))
    P_missing_pair = P[~((P["game_id"] == 1000) & (P["defense_team_id"] == 100))].copy()
    arm_missing = A.ArmA20(P_missing_pair, fold_ids=["SYNTH"], n_rows=len(U))
    try:
        arm_missing.build_design(dummy_fold(U), U)
        check(False, "a universe row whose (team_id, game_id) is absent from the possessions "
                     "frame raises rather than silently producing an undefined/NaN rate")
    except A.A20ConstructionFailure as e:
        check(True, "a universe row whose (team_id, game_id) is absent from the possessions "
                    "frame raises A20ConstructionFailure", str(e))

    print()
    print("=" * 88)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
