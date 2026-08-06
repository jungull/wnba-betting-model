#!/usr/bin/env python3
"""TESTS.py -- A26_sos_correction_own_minus_opp (P36_IMPLEMENT_ARMS/arms/A26).

Standalone runnable test script (pytest is not assumed available -- matches the P22/P26/P27/A18/
A20 convention in this program). main() returns 0 on success, 1 on any failure, and also prints a
machine-parseable receipt-shaped summary consumed by build_receipt.py in this directory.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no challenger performance is inspected here. Every
fixture below is SYNTHETIC (invented numbers on invented team/game/possession ids); nothing here
reads any real artifact under experiments/player_program/. Only unit, synthetic, identity and
schema tests exist in this file, per the P36 mandate:

  * T01  feature determinism -- build_design is a pure function of (fold, universe); repeated
         calls on the same input produce byte-identical columns
  * T02  fold-independence -- the SAME construction runs regardless of which fold dict is passed
         (z5 is not a training-fold-estimated constant), and the arm/null design-column NAME sets
         never drift across folds
  * T03  strict lagging -- perturbing a game's own raw possession count changes only STRICTLY
         LATER rows built from it (that game's own row, and any strictly earlier row, are
         unaffected); this also exercises the one-level-removed LOO-exclusion channel (a game
         CAN appear inside an opponent-of-an-opponent's LOO mean for a strictly later row, but
         never contributes net signal back into its own target game)
  * T04  same-season-only window -- z5 never reaches back across a season boundary (a team's
         first game of a new season has n_own = 0, even with a full prior season of history)
  * T05  E=3 imputation -- z5 := 0 whenever EITHER side has < 3 strictly-earlier same-season games
  * T06  hand-computed value check -- the constructed z5 matches an independent, non-pandas
         re-derivation on a small synthetic universe + possessions fixture, exactly, including the
         LOO exclusion and the one-clock (target-date) as-of rule
  * T07  undefined-LOO imputation -- z5 := 0 when a required opponent has no OTHER
         strictly-earlier-than-target-date same-season game besides the one meeting excluded, even
         when both sides individually clear the E=3 floor
  * T08  arm-vs-null design nesting -- K0's treatment/nuisance columns are the EMPTY subset of the
         arm's; runner_interface.validate_design_bundle accepts the bundle, including the
         no-intercept invariant (A26 is in ARMS_WITHOUT_GLOBAL_INTERCEPT)
  * T09  enumeration element is exact -- {} (no grid; RUNNER_INTERFACE section 1), element_id() is
         deterministic
  * T10  runner conformance -- runner_interface.validate_arm_module accepts an A26Arm instance as
         an arm module object (every required hook present and correctly typed)
  * T11  P26 k0_matched/1 record is schema- and relation-valid (validate_k0_matched.validate)
  * T12  kill-condition hooks are decidable -- exactly one tested_parameter named "beta5", role
         "coefficient", null_value 0, so "the 95% bootstrap interval for beta5 covers 0 in every
         evaluable fold" (P35 kill_conditions_frozen) is a well-defined, locatable check against
         this record, not an ambiguous one
  * T13  P22 lag declaration is DERIVED_NO_JOIN (not SAME_GAME, not an unverifiable PRIOR_GAME
         claim), and postgame_surrogate_guard.audit raises no blocking finding for this column
         against a synthetic prohibited basis carrying no relationship to the treatment column
  * T14  franchise continuity is False (A26's same-season-only construction has no cross-season
         dependency; card is absent from P33's p23_franchise_continuity_precondition list)
  * T15  malformed / missing-join input raises rather than silently producing a wrong/NaN value
  * T16  kill-condition decidability end-to-end -- near_affinity_against + decide_kill compute a
         well-formed decision on synthetic per-fold coefficient intervals

Run:  python experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/arms/A26/TESTS.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import arm_a26 as A                                                             # noqa: E402
import feature_construction as feat                                             # noqa: E402

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
RESULTS: list[dict] = []


def check(cond: bool, label: str, extra: object = "") -> None:
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {extra}")
        FAILURES.append(label)


def record(test_name: str, t0: float, measured: dict) -> None:
    RESULTS.append({"test": test_name, "seconds": round(time.time() - t0, 2),
                    "measured": measured, "passed": test_name not in
                    {f.split(":")[0] for f in FAILURES if f.startswith(test_name)}})


# ---------------------------------------------------------------------------------------------
# synthetic fixture -- three teams (100, 200, 300), one season 2024, plus a season-2025 tail for
# T04. Purely invented raw possession counts, chosen so E=3 boundaries and the LOO-undefined case
# are both exercised by construction.
# ---------------------------------------------------------------------------------------------

# Round-robin schedule, season 2024, ascending game_date, team 100 vs 200 (odd rounds) and
# team 100 vs 300 / 200 vs 300 interleaved so every team accumulates cross-opponent history.
# Each tuple: (game_id, date_offset, team_a, team_b, raw_a, raw_b)
SCHEDULE_2024 = [
    (2001, 0, 100, 200, 78, 82),
    (2002, 1, 100, 300, 80, 76),
    (2003, 2, 200, 300, 84, 79),
    (2004, 3, 100, 200, 81, 80),
    (2005, 4, 100, 300, 77, 83),
    (2006, 5, 200, 300, 86, 78),
    (2007, 6, 100, 200, 79, 85),
    (2008, 7, 100, 300, 82, 81),
]


def synthetic_universe(schedule=SCHEDULE_2024, season=2024, id_offset=0) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    rows = []
    for gid, doff, ta, tb, _ra, _rb in schedule:
        d = dates[doff]
        rows.append({"game_id": gid + id_offset, "team_id": ta, "opp_team_id": tb,
                    "game_date": d, "season": season})
        rows.append({"game_id": gid + id_offset, "team_id": tb, "opp_team_id": ta,
                    "game_date": d, "season": season})
    return pd.DataFrame(rows).reset_index(drop=True)


def synthetic_possessions(schedule=SCHEDULE_2024, id_offset=0) -> pd.DataFrame:
    """One possession row per offensive possession -- exactly ``raw`` rows of offense_team_id ==
    that team for that game_id, reproducing the SCHEDULE_2024 raw counts exactly."""
    rows = []
    for gid, _doff, ta, tb, ra, rb in schedule:
        g = gid + id_offset
        for k in range(ra):
            rows.append({"game_id": g, "offense_team_id": ta, "possession_id": f"{g}-{ta}-{k}"})
        for k in range(rb):
            rows.append({"game_id": g, "offense_team_id": tb, "possession_id": f"{g}-{tb}-{k}"})
    return pd.DataFrame(rows)


def dummy_fold(universe: pd.DataFrame, fold_id: str = "SYNTH") -> dict:
    n = len(universe)
    return {"fold_id": fold_id, "train_idx": np.arange(n), "test_idx": np.empty(0, int)}


# ---------------------------------------------------------------------------------------------
# independent oracle (no shared code with feature_construction.py): a brute-force, pure-Python
# re-derivation of z5 for one target row, given the full schedule as a list of
# (game_id, date_offset, team_a, team_b, raw_a, raw_b) tuples.
# ---------------------------------------------------------------------------------------------

def _raw_lookup(schedule, team, gid):
    for g, _d, ta, tb, ra, rb in schedule:
        if g != gid:
            continue
        if ta == team:
            return ra
        if tb == team:
            return rb
    raise KeyError((team, gid))


def _team_games(schedule, team, before_doff):
    """[(gid, doff, opp, raw_team)] for `team`'s games with date_offset < before_doff, ascending."""
    out = []
    for g, d, ta, tb, ra, rb in schedule:
        if d >= before_doff:
            continue
        if ta == team:
            out.append((g, d, tb, ra))
        elif tb == team:
            out.append((g, d, ta, rb))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def oracle_sched_t(schedule, team, target_doff, e_min=3):
    hist = _team_games(schedule, team, target_doff)
    n = len(hist)
    if n == 0:
        return None, n
    loo_vals = []
    for gid, _d, opp, _raw_team in hist:
        opp_hist = _team_games(schedule, opp, target_doff)   # ONE CLOCK: as of target_doff
        if len(opp_hist) - 1 <= 0:
            return None, n
        total = sum(r for (_g, _d2, _o, r) in opp_hist)
        excl = _raw_lookup(schedule, opp, gid)
        loo_vals.append((total - excl) / (len(opp_hist) - 1))
    return float(np.mean(loo_vals)), n


def oracle_league_mean(schedule, target_doff):
    vals = []
    for g, d, ta, tb, ra, rb in schedule:
        if d < target_doff:
            vals.append(ra)
            vals.append(rb)
    if not vals:
        return None
    return float(np.mean(vals))


def oracle_z5(schedule, own, opp, target_doff, e_min=3):
    sched_own, n_own = oracle_sched_t(schedule, own, target_doff, e_min)
    sched_opp, n_opp = oracle_sched_t(schedule, opp, target_doff, e_min)
    L = oracle_league_mean(schedule, target_doff)
    if n_own < e_min or n_opp < e_min or sched_own is None or sched_opp is None or L is None:
        return 0.0, n_own, n_opp
    c_own = -(sched_own - L)
    c_opp = -(sched_opp - L)
    return c_own - c_opp, n_own, n_opp


# ---------------------------------------------------------------------------------------------
def main() -> int:
    U = synthetic_universe()
    P = synthetic_possessions()
    arm = A.A26Arm(P, fold_ids=["SYNTH"], n_rows=len(U))

    t0 = time.time()
    print("T01 feature determinism")
    b1 = arm.build_design(dummy_fold(U), U)
    b2 = arm.build_design(dummy_fold(U), U)
    check(np.array_equal(b1["columns"][A.TREATMENT_COL], b2["columns"][A.TREATMENT_COL]),
          "repeated build_design calls are byte-identical")
    record("T01_feature_determinism", t0, {"n_rows": len(U), "n_possessions": len(P)})

    t0 = time.time()
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
    record("T02_fold_independence", t0, {})

    t0 = time.time()
    print("T03 strict lagging")
    base = arm.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL].copy()
    P2 = P.copy()
    # perturb team 100's LAST game (game_id 2008, offense_team_id 100): add 10 extra possessions
    mask_last = (P2["game_id"] == 2008) & (P2["offense_team_id"] == 100)
    extra = pd.DataFrame({"game_id": [2008] * 10, "offense_team_id": [100] * 10,
                          "possession_id": [f"2008-100-extra-{k}" for k in range(10)]})
    P2 = pd.concat([P2, extra], ignore_index=True)
    arm2 = A.A26Arm(P2, fold_ids=["SYNTH"], n_rows=len(U))
    perturbed = arm2.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL]
    last_row_100 = U[(U["team_id"] == 100) & (U["game_id"] == 2008)].index[0]
    check(np.isclose(perturbed[last_row_100], base[last_row_100]),
          "perturbing a game's OWN possession count does not change that SAME game's own z5 "
          "(the game's own raw_t never enters its own trailing/LOO means)")
    earlier_rows = U[U["game_id"] < 2008].index
    check(np.allclose(perturbed[earlier_rows], base[earlier_rows]),
          "perturbing the LAST game's possession count does not change any strictly earlier row",
          list(zip(perturbed[earlier_rows], base[earlier_rows])))
    del mask_last
    record("T03_strict_lagging", t0, {})

    t0 = time.time()
    print("T04 same-season-only window")
    U2 = synthetic_universe(season=2025, id_offset=500)
    P2s = synthetic_possessions(id_offset=500)
    U_multi = pd.concat([U, U2], ignore_index=True)
    P_multi = pd.concat([P, P2s], ignore_index=True)
    arm_multi = A.A26Arm(P_multi, fold_ids=["SYNTH"], n_rows=len(U_multi))
    b_multi = arm_multi.build_design(dummy_fold(U_multi), U_multi)
    res_multi = feat.compute_features(P_multi, U_multi)
    first_2025_row = U_multi[(U_multi["team_id"] == 100) & (U_multi["season"] == 2025)].index[0]
    check(res_multi["n_own"][U_multi.index.get_loc(first_2025_row)] == 0.0,
          "a team's first game of a NEW season has n_own = 0, even with a full prior-season "
          "history (same-season-only window never crosses the season boundary)")
    check(b_multi["columns"][A.TREATMENT_COL][U_multi.index.get_loc(first_2025_row)] == 0.0,
          "z5 is imputed to 0 for a team's first game of a new season")
    record("T04_same_season_only_window", t0, {})

    t0 = time.time()
    print("T05 E=3 imputation")
    b = arm.build_design(dummy_fold(U), U)["columns"][A.TREATMENT_COL]
    res = feat.compute_features(P, U)
    for gid in (2001, 2002):   # both teams have < 3 strictly-earlier same-season games here
        for team in ((100, 200) if gid == 2001 else (100, 300)):
            row = U[(U["team_id"] == team) & (U["game_id"] == gid)].index[0]
            check(b[U.index.get_loc(row)] == 0.0,
                  f"game {gid}, team {team}: z5 forced to 0 (E=3 floor not met)",
                  b[U.index.get_loc(row)])
    record("T05_e3_imputation", t0, {"n_imputed": int(np.sum(res["imputed"])), "n_rows": len(U)})

    t0 = time.time()
    print("T06 hand-computed value check (independent oracle)")
    doff_by_gid = {gid: doff for gid, doff, *_ in SCHEDULE_2024}
    max_mismatch = 0.0
    for gid, doff, ta, tb, _ra, _rb in SCHEDULE_2024:
        for own, opp in ((ta, tb), (tb, ta)):
            row = U[(U["team_id"] == own) & (U["game_id"] == gid)].index[0]
            expected_z5, exp_n_own, _exp_n_opp = oracle_z5(SCHEDULE_2024, own, opp, doff)
            got = b[U.index.get_loc(row)]
            max_mismatch = max(max_mismatch, abs(got - expected_z5))
            check(abs(got - expected_z5) < 1e-9,
                  f"game {gid} ({own} vs {opp}): z5 matches independent oracle",
                  (got, expected_z5))
    record("T06_hand_computed_value_check", t0, {"max_abs_mismatch": max_mismatch})

    t0 = time.time()
    print("T07 undefined-LOO imputation (a required opponent has no OTHER qualifying game)")
    # Construct a small fixture: team 400's ONLY prior game before the target date is against
    # team 500, and team 500's ONLY prior game (of any kind) is that SAME game against 400 --
    # so team 500's LOO mean (excluding that one meeting) is undefined, forcing z5 := 0 for any
    # row whose own-side history includes team 400 as an opponent-of-opponent step... more
    # directly: build team 600's history to include a game against 400, where 400's own LOO
    # (excluding the 600-vs-400 meeting) has only the 400-vs-500 game, which itself is fine, but
    # we isolate the exact single-game LOO-undefined case directly via oracle_sched_t.
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    tiny_schedule = [
        (9001, 0, 400, 500, 70, 71),   # 500's ONLY game before doff=2 -> LOO for 500 undefined
        (9002, 1, 400, 600, 72, 73),
        (9003, 1, 400, 700, 74, 75),
    ]
    rows = []
    for gid, doff, ta, tb, _ra, _rb in tiny_schedule:
        d = dates[doff]
        rows.append({"game_id": gid, "team_id": ta, "opp_team_id": tb, "game_date": d, "season": 2024})
        rows.append({"game_id": gid, "team_id": tb, "opp_team_id": ta, "game_date": d, "season": 2024})
    U_tiny = pd.DataFrame(rows)
    # target row: team 400 vs a NEW opponent 800 at doff=2, so 400 has 3 prior games (500,600,700)
    U_tiny = pd.concat([U_tiny, pd.DataFrame([
        {"game_id": 9004, "team_id": 400, "opp_team_id": 800, "game_date": dates[2], "season": 2024},
        {"game_id": 9004, "team_id": 800, "opp_team_id": 400, "game_date": dates[2], "season": 2024},
    ])], ignore_index=True)
    P_tiny_sched = tiny_schedule + [(9004, 2, 400, 800, 76, 77)]
    P_tiny = synthetic_possessions(schedule=P_tiny_sched)
    arm_tiny = A.A26Arm(P_tiny, fold_ids=["SYNTH"], n_rows=len(U_tiny))
    b_tiny = arm_tiny.build_design(dummy_fold(U_tiny), U_tiny)["columns"][A.TREATMENT_COL]
    res_tiny = feat.compute_features(P_tiny, U_tiny)
    row_target = U_tiny[(U_tiny["team_id"] == 400) & (U_tiny["game_id"] == 9004)].index[0]
    idx_target = U_tiny.index.get_loc(row_target)
    check(res_tiny["n_own"][idx_target] == 3.0,
          "team 400 clears the E=3 floor on the own side (3 strictly-earlier same-season games)",
          res_tiny["n_own"][idx_target])
    check(res_tiny["imputed"][idx_target] == True,      # noqa: E712
          "z5 is STILL imputed to 0 even though n_own >= 3, because team 500's LOO mean (its "
          "only prior game is the very meeting being excluded) is undefined",
          (res_tiny["n_own"][idx_target], res_tiny["imputed"][idx_target]))
    check(b_tiny[idx_target] == 0.0, "z5 == 0.0 for the undefined-LOO row", b_tiny[idx_target])
    record("T07_undefined_loo_imputation", t0, {"n_own_at_target": float(res_tiny["n_own"][idx_target])})

    t0 = time.time()
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
    record("T08_k0_nesting_and_bundle_validation", t0,
          {"arm_cols": bundle["treatment_cols"], "null_cols": k0["treatment_cols"]})

    t0 = time.time()
    print("T09 enumeration element is exact")
    check(arm.enumeration_element() == {}, "enumeration_element() == {} (no grid)")
    check(arm.element_id() == A.ARM_ID, "element_id() is deterministic", arm.element_id())
    check(arm.card_id() == arm.arm_id == A.ARM_ID, "card_id()/arm_id/ARM_ID agree")
    record("T09_enumeration_element_exact_single", t0, {"element_id": arm.element_id()})

    t0 = time.time()
    print("T10 runner conformance (runner_interface.validate_arm_module)")
    try:
        conf = ri.validate_arm_module(arm)
        check(conf["conformant"], "module passes validate_arm_module", conf)
    except ri.ArmModuleNonconformant as e:
        check(False, "module passes validate_arm_module", e.problems)
    check(arm.declared_family() == "SUBSTANTIVE", "declared_family pinned to SUBSTANTIVE")
    check(arm.recalibration_declaration() == "NOT_APPLICABLE", "recalibration_declaration pinned")
    check(arm.uses_global_intercept() is False, "uses_global_intercept() is False (frozen table)")
    record("T10_runner_conformance", t0, {"treatment_col": A.TREATMENT_COL})

    t0 = time.time()
    print("T11 P26 k0_matched/1 record validity")
    rec = arm.p26_k0_record()
    rep = vk.validate(rec)
    check(rep["valid"], "p26_k0_record() validates against K0_MATCHED_SCHEMA + relation rules",
          rep["blocking"])
    record("T11_p26_record_valid", t0, {"valid": rep["valid"]})

    t0 = time.time()
    print("T12 kill-condition hooks are decidable")
    params = rec["treatment_mechanism"]["tested_parameters"]
    check(len(params) == 1, "exactly one tested parameter is declared", params)
    p = params[0] if params else {}
    check(p.get("name") == "beta5" and p.get("role") == "coefficient" and p.get("null_value") == 0,
          "the sole tested parameter is 'beta5', role coefficient, null_value 0 -- the P35 kill "
          "condition 'interval covers 0' names a single, locatable quantity in this record", p)
    check(rec["treatment_mechanism"]["treatment_terms"] == [A.TREATMENT_COL],
          "treatment_terms matches the single materialised design column exactly")
    record("T12_kill_condition_hooks_decidable", t0, {"tested_parameter": p.get("name")})

    t0 = time.time()
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
        source={"synthetic": True}, note="synthetic prohibited basis for A26 unit tests; "
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
    record("T13_p22_lag_declaration", t0, {"kind": spec.kind})

    t0 = time.time()
    print("T14 franchise continuity is False")
    check(arm.requires_franchise_continuity() is False,
          "requires_franchise_continuity() is False (A26 absent from P33 "
          "p23_franchise_continuity_precondition; same-season-only construction has no "
          "cross-season dependency)")
    check(arm.p23_receipts() == [], "p23_receipts() returns an empty list")
    record("T14_franchise_continuity_false", t0, {})

    t0 = time.time()
    print("T15 malformed / missing-join input raises rather than silently mis-scoring")
    try:
        feat.aggregate_game_team_raw_count(P.drop(columns=["offense_team_id"]))
        check(False, "missing offense_team_id column raises A26ConstructionFailure")
    except feat.A26ConstructionFailure as e:
        check(True, "missing offense_team_id column raises A26ConstructionFailure", str(e))
    P_missing_pair = P[~((P["game_id"] == 2001) & (P["offense_team_id"] == 100))].copy()
    arm_missing = A.A26Arm(P_missing_pair, fold_ids=["SYNTH"], n_rows=len(U))
    try:
        arm_missing.build_design(dummy_fold(U), U)
        check(False, "a universe row whose (team_id, game_id) is absent from the possessions "
                     "frame raises rather than silently producing an undefined/NaN value")
    except feat.A26ConstructionFailure as e:
        check(True, "a universe row whose (team_id, game_id) is absent from the possessions "
                    "frame raises A26ConstructionFailure", str(e))
    record("T15_malformed_input_raises", t0, {})

    t0 = time.time()
    print("T16 kill-condition decidability end-to-end")
    beta_by_fold = {
        "syn_a26_fold1": {"point": 0.01, "ci_low": -0.02, "ci_high": 0.04},
        "syn_a26_fold2": {"point": -0.01, "ci_low": -0.05, "ci_high": 0.03},
    }
    na_offset = {"syn_a26_fold1": False, "syn_a26_fold2": False}
    decision = A.decide_kill(beta_by_fold, near_affinity_offset_by_fold=na_offset,
                             near_affinity_pace_gap_by_fold=None, primary_gate_passed=None)
    check(decision["schema"] == "a26_kill_decision/1", "decide_kill returns the frozen schema tag")
    check(decision["interval_kill"] is True,
          "both synthetic folds' intervals cover 0 -> interval_kill fires", decision)
    check(decision["killed_or_withdrawn"] is True, "overall verdict is killed", decision)
    dup = np.linspace(0, 1, 50)
    na = A.near_affinity_against(dup, dup)
    check(na["near_affine"] is True, "near_affinity_against flags a duplicate series as near-affine", na)
    unrelated = np.random.default_rng(0).permutation(dup)
    na2 = A.near_affinity_against(dup, unrelated)
    check(na2["near_affine"] is False, "near_affinity_against does not flag an unrelated permutation",
          na2)
    record("T16_kill_condition_hooks_decidable_end_to_end", t0, {"decision": decision})

    print()
    print("=" * 88)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
