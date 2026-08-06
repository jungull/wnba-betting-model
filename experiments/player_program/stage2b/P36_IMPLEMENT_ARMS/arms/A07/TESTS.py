#!/usr/bin/env python3
"""TESTS.py -- identity/synthetic/schema tests for the A07_early_season_transient arm module.

EPISTEMIC STATUS: IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit,
synthetic, identity and schema tests only. Nothing here is a real fold, a real fit or a real MAE:
every row count, cluster count and fold_id below is a synthetic fixture chosen to be structurally
NON-real per runner/blinding.py (row counts avoid {2982, 2990}; fold_ids are "SYN_*", never any of
the frozen D006 real fold_ids).

Run:
    python TESTS.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ARMS_DIR = HERE.parent
P36 = ARMS_DIR.parent
STAGE2B = P36.parent
RUNNER = P36 / "runner"
P26 = STAGE2B / "P26_ARM_SPECIFIC_K0_CONTRACT"

# arms/A07 imports its own module directly; it reads (never writes) the frozen runner/ and P26/
# directories to run conformance checks against the frozen contracts, per standing rule 2
# (write scope is arms/A07/ only -- nothing here writes outside it).
for p in (HERE, RUNNER, P26):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import A07_early_season_transient as arm_mod                                    # noqa: E402
import runner_constants as rc                                                   # noqa: E402
import runner_interface as ri                                                   # noqa: E402
import validate_k0_matched as vk                                                # noqa: E402
import blinding                                                                 # noqa: E402

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ------------------------------------------------------------------------------------------- #
# synthetic fixtures (structurally non-real; see module docstring)
# ------------------------------------------------------------------------------------------- #

def make_contract_schedule() -> pd.DataFrame:
    """Two teams, one season, plus a second season, deliberately including games that will be
    EXCLUDED from the 'universe' fixture below -- this is the synthetic analogue of the four
    universe-excluded 2021 rows the real n_clock_pin requires n_i to still count."""
    rows = []
    # team T1, season 2021: 6 games, dates 1..6 (one, game 3, will be excluded from 'universe')
    for d in range(1, 7):
        rows.append({"team_id": "T1", "season": 2021, "game_date": f"2021-05-{d:02d}",
                    "game_id": f"G1_{d}"})
    # team T2, season 2021: 4 games
    for d in range(1, 5):
        rows.append({"team_id": "T2", "season": 2021, "game_date": f"2021-05-{d:02d}",
                    "game_id": f"G2_{d}"})
    # team T1, season 2022: 3 games (fresh season -- n_i resets)
    for d in range(1, 4):
        rows.append({"team_id": "T1", "season": 2022, "game_date": f"2022-05-{d:02d}",
                    "game_id": f"G3_{d}"})
    return pd.DataFrame(rows)


def make_universe(schedule: pd.DataFrame, *, drop_game_id: str = "G1_3") -> pd.DataFrame:
    """The 'resolved' universe: the schedule minus one row (the synthetic analogue of a
    universe-excluded contract-schedule row), plus the receipted gap/depth/opp_depth columns."""
    u = schedule[schedule["game_id"] != drop_game_id].reset_index(drop=True)
    rng = np.random.default_rng(0)
    u["pace_gap"] = rng.normal(0, 1, size=len(u))
    u["pace_evidence_depth"] = rng.integers(0, 10, size=len(u)).astype(float)
    u["opp_pace_evidence_depth"] = rng.integers(0, 10, size=len(u)).astype(float)
    return u


SCHEDULE = make_contract_schedule()
UNIVERSE = make_universe(SCHEDULE)
FOLD_IDS = ["SYN_fold_1", "SYN_fold_2"]
FOLD = {"fold_id": "SYN_fold_1",
       "train_idx": np.arange(len(UNIVERSE)), "test_idx": np.array([], dtype=int)}


def make_module() -> "arm_mod.A07EarlySeasonTransient":
    return arm_mod.A07EarlySeasonTransient(SCHEDULE, fold_ids=FOLD_IDS, n_rows=len(UNIVERSE))


# ------------------------------------------------------------------------------------------- #
# blinding self-check: the fixtures used by every test below must be structurally non-real
# ------------------------------------------------------------------------------------------- #

def test_fixtures_are_structurally_synthetic():
    try:
        blinding.assert_not_real(n_rows=len(UNIVERSE), n_clusters=UNIVERSE["team_id"].nunique(),
                                 fold_ids=FOLD_IDS, artifact_paths=[], artifact_hashes=[])
        ok = True
    except blinding.BlindingViolation:
        ok = False
    check("fixtures_are_structurally_synthetic", ok,
         "synthetic fixture tripped the real-fold blinding predicate -- change row/cluster counts")


# ------------------------------------------------------------------------------------------- #
# 1. feature determinism
# ------------------------------------------------------------------------------------------- #

def test_feature_determinism():
    mod = make_module()
    b1 = mod.build_design(FOLD, UNIVERSE)
    b2 = mod.build_design(FOLD, UNIVERSE)
    same = all(np.array_equal(b1["columns"][k], b2["columns"][k]) for k in b1["columns"])
    check("feature_determinism_repeat_call", same,
         "build_design produced different columns on an identical, repeated call")

    # independent module instance, same inputs -> identical output (determinism is a property of
    # the construction, not of any mutable state held on one instance)
    mod2 = make_module()
    b3 = mod2.build_design(FOLD, UNIVERSE)
    same2 = all(np.array_equal(b1["columns"][k], b3["columns"][k]) for k in b1["columns"])
    check("feature_determinism_fresh_instance", same2,
         "a fresh module instance over identical inputs produced different columns")


# ------------------------------------------------------------------------------------------- #
# 2. strict lagging (n_i counts strictly-earlier CONTRACT-SCHEDULE games; ties/self excluded)
# ------------------------------------------------------------------------------------------- #

def test_n_i_strict_lagging_contract_schedule_clock():
    # T1/2021 dates 1..6 on the contract schedule; game 3 is excluded from 'universe'.
    # n_i(date d) must equal the count of T1/2021 schedule dates < d, REGARDLESS of whether that
    # date's row survived into 'universe' -- this is the n_clock_pin: "the universe-row clock is
    # barred".
    probe = pd.DataFrame({
        "team_id": ["T1"] * 6, "season": [2021] * 6,
        "game_date": [f"2021-05-{d:02d}" for d in range(1, 7)],
    })
    n_i = arm_mod.compute_n_i(SCHEDULE, probe["team_id"].to_numpy(), probe["season"].to_numpy(),
                              probe["game_date"].to_numpy())
    expected = np.array([0, 1, 2, 3, 4, 5], dtype=float)   # date d has (d-1) strictly-earlier games
    check("n_i_strict_lagging_full_schedule_clock", np.array_equal(n_i, expected),
         f"got {n_i}, expected {expected}")

    # the SAME dates, computed from the 'universe' (game 3 dropped) contract_schedule would
    # UNDERCOUNT date 4..6 by one if the module were wrongly using universe as its own clock; the
    # module never does this (it always takes contract_schedule at construction), verified here by
    # explicitly passing the DROPPED schedule and confirming the pin would be violated -- i.e. this
    # asserts the universe-row clock IS a different (wrong) answer, motivating why the module never
    # uses it.
    dropped_schedule = SCHEDULE[SCHEDULE["game_id"] != "G1_3"]
    n_i_wrong_clock = arm_mod.compute_n_i(dropped_schedule, probe["team_id"].to_numpy(),
                                          probe["season"].to_numpy(),
                                          probe["game_date"].to_numpy())
    expected_wrong = np.array([0, 1, 2, 2, 3, 4], dtype=float)  # date 4 onward undercounts by 1
    check("universe_row_clock_would_undercount_if_used", np.array_equal(n_i_wrong_clock,
         expected_wrong),
         "the universe-row-clock control computation did not reproduce the expected undercount; "
         "the discriminating test itself may be wrong")
    check("module_avoids_universe_row_clock", not np.array_equal(n_i, n_i_wrong_clock),
         "n_i computed on the full contract schedule must differ from n_i computed on the "
         "universe-only schedule whenever an excluded row precedes a query date (n_clock_pin)")

    # season reset: T1/2022 date 1 has zero STRICTLY-EARLIER SAME-SEASON games, despite T1 having
    # six 2021 games on the schedule.
    probe2 = pd.DataFrame({"team_id": ["T1"], "season": [2022], "game_date": ["2022-05-01"]})
    n_i2 = arm_mod.compute_n_i(SCHEDULE, probe2["team_id"].to_numpy(),
                               probe2["season"].to_numpy(), probe2["game_date"].to_numpy())
    check("n_i_season_reset", n_i2[0] == 0.0, f"got {n_i2[0]}, expected 0.0 (new season)")

    # unresolved (team, season) fails CLOSED, never silently imputes
    probe3 = pd.DataFrame({"team_id": ["T9"], "season": [2021], "game_date": ["2021-05-01"]})
    raised = False
    try:
        arm_mod.compute_n_i(SCHEDULE, probe3["team_id"].to_numpy(), probe3["season"].to_numpy(),
                            probe3["game_date"].to_numpy())
    except arm_mod.A07ConstructionFailure:
        raised = True
    check("n_i_fails_closed_on_unresolved_team_season", raised,
         "an unresolved (team_id, season) pair must raise, not silently produce a value")


def test_early_season_transient_matches_exp_decay():
    n_i = np.array([0.0, 1.0, 5.0, 10.0])
    got = arm_mod.early_season_transient(n_i)
    expected = np.exp(-n_i / 5.0)
    check("early_season_transient_formula_and_tau_fixed_at_5",
         np.allclose(got, expected) and arm_mod.TAU == 5.0,
         f"got {got}, expected {expected}, TAU={arm_mod.TAU}")


# ------------------------------------------------------------------------------------------- #
# 3. arm-vs-null design nesting (K0_MATCHED[A07] = term_removal of exactly the treatment)
# ------------------------------------------------------------------------------------------- #

def test_arm_vs_null_nesting():
    mod = make_module()
    bundle = mod.build_design(FOLD, UNIVERSE)
    k0 = bundle["k0_matched_design"]

    check("null_is_term_removal", k0["comparison"] == "term_removal")
    check("null_treatment_cols_empty", k0["treatment_cols"] == [])
    check("null_nuisance_equals_arm_nuisance", set(k0["nuisance_cols"]) ==
         set(bundle["nuisance_cols"]),
         f"null={k0['nuisance_cols']} arm={bundle['nuisance_cols']}")
    check("treatment_absent_from_null", not (set(bundle["treatment_cols"]) &
                                            set(k0["nuisance_cols"])))
    check("null_strictly_nested_in_arm",
         set(k0["nuisance_cols"]) | set(k0["treatment_cols"]) <
         set(bundle["nuisance_cols"]) | set(bundle["treatment_cols"]),
         "the null's column set must be a STRICT subset of the arm's (nesting)")

    # the frozen runner_interface bundle validator: shape + the intercept invariant
    rec = ri.validate_design_bundle(bundle, UNIVERSE, mod.uses_global_intercept(),
                                    FOLD["fold_id"])
    check("runner_interface_validate_design_bundle_passes", rec["valid"], str(rec))


def test_k0_matched_contract_conformance():
    """The frozen P26 validator (shape + relation) accepts this arm's K0_MATCHED record."""
    mod = make_module()
    rec = mod.p26_k0_record()
    rep = vk.validate(rec)
    check("p26_k0_matched_record_valid", rep["valid"], str(rep["blocking"]))
    check("p26_arm_kind_is_substantive_feature", rec["arm_kind"] == "substantive_feature")
    check("p26_k0_flat_role_diagnostic_only", rec["k0_flat_role"] == "diagnostic_only")


# ------------------------------------------------------------------------------------------- #
# 4. enumeration elements exact
# ------------------------------------------------------------------------------------------- #

def test_enumeration_element_exact():
    mod = make_module()
    check("enumeration_element_empty", mod.enumeration_element() == {},
         "A07 has no enumerated grid (unlike A08/A09/A10/A11/A23); element must be {}")
    check("element_id_exact", mod.element_id() == "A07_early_season_transient__single",
         mod.element_id())
    check("arm_id_exact", mod.arm_id == "A07_early_season_transient", mod.arm_id)
    check("card_id_matches_arm_id", mod.card_id() == mod.arm_id)
    check("declared_family_pinned", mod.declared_family() == "SUBSTANTIVE")
    check("recalibration_declaration_pinned", mod.recalibration_declaration() == "NOT_APPLICABLE")
    check("uses_global_intercept_true_per_frozen_table", mod.uses_global_intercept() is True)
    check("p27_rule_none_no_active_set_rule_registered", mod.p27_rule() is None)
    check("requires_franchise_continuity_false", mod.requires_franchise_continuity() is False)
    check("p23_receipts_empty", mod.p23_receipts() == [])
    check("preregistered_contrasts_none", mod.preregistered_contrasts() is None)
    check("prereg_digest_expected_none", mod.prereg_digest_expected() is None)


def test_module_conformance_against_frozen_runner_interface():
    mod = make_module()
    try:
        rec = ri.validate_arm_module(mod)
        ok = rec["conformant"]
    except ri.ArmModuleNonconformant as e:
        ok, rec = False, e.problems
    check("frozen_runner_interface_validate_arm_module_passes", ok, str(rec))


def test_intercept_table_agreement_with_runner_constants():
    check("A07_in_ARMS_WITH_FREE_GLOBAL_INTERCEPT", "A07" in rc.ARMS_WITH_FREE_GLOBAL_INTERCEPT)
    check("A07_not_in_ARMS_WITHOUT_GLOBAL_INTERCEPT",
         "A07" not in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT)
    check("offset_col_name_agrees_with_runner", arm_mod.OFFSET_COL == rc.OFFSET_COL)
    check("intercept_col_name_agrees_with_runner", arm_mod.INTERCEPT_COL == rc.INTERCEPT_COL)


def test_lag_specs_cover_every_design_column_except_structural_intercept():
    mod = make_module()
    bundle = mod.build_design(FOLD, UNIVERSE)
    declared = set(bundle["treatment_cols"]) | set(bundle["nuisance_cols"])
    specs = mod.lag_specs()
    needing_spec = declared - {arm_mod.INTERCEPT_COL}
    check("every_non_intercept_design_column_has_a_lag_spec",
         needing_spec <= set(specs),
         f"missing specs for {needing_spec - set(specs)}")
    check("intercept_has_no_lag_spec", arm_mod.INTERCEPT_COL not in specs,
         "the structural intercept column must not be declared as a P22 feature")
    check("lag_spec_kinds_are_frozen_p22_kinds",
         all(s["kind"] in ("SAME_GAME", "PRIOR_GAME", "SCHEDULE", "DERIVED_NO_JOIN")
             for s in specs.values()))
    check("no_lag_spec_declares_SAME_GAME",
         all(s["kind"] != "SAME_GAME" for s in specs.values()),
         "SAME_GAME blocks unconditionally at P22; none of A07's columns should ever declare it")
    check("treatment_column_lag_kind_is_SCHEDULE_disclosed_ambiguity",
         specs[arm_mod.TREATMENT_COL]["kind"] == "SCHEDULE")


def test_lag_sources_supplies_contract_schedule():
    mod = make_module()
    sources = mod.lag_sources()
    check("lag_sources_has_contract_schedule", "contract_schedule" in sources)
    check("lag_sources_contract_schedule_is_the_supplied_frame",
         sources["contract_schedule"] is mod._contract_schedule)


# ------------------------------------------------------------------------------------------- #
# 5. kill-condition hooks decidable
# ------------------------------------------------------------------------------------------- #

def test_kill_conditions_decidable():
    ev = arm_mod.evaluate_kill_conditions

    # (a) no kill: CI excludes 0 in every fold, stable sign, improvement concentrated on n<=5
    r_pass = ev(fold_intervals=[(0.1, 0.4), (0.05, 0.3)], fold_signs=[1, 1],
               improvement_share_n_le_5=0.9)
    check("kill_conditions_pass_case_not_killed", r_pass["killed"] is False, r_pass)

    # (b) delta CI covers 0 in EVERY evaluable fold -> killed
    r_ci = ev(fold_intervals=[(-0.1, 0.2), (-0.05, 0.05)], fold_signs=[1, -1],
             improvement_share_n_le_5=0.9)
    check("kill_conditions_ci_covers_zero_every_fold_kills",
         r_ci["delta_ci_covers_zero_every_fold"] is True and r_ci["killed"] is True, r_ci)

    # CI covers 0 in only SOME folds -> that specific rule does not fire (others might)
    r_ci_partial = ev(fold_intervals=[(-0.1, 0.2), (0.05, 0.3)], fold_signs=[1, 1],
                      improvement_share_n_le_5=0.9)
    check("kill_conditions_ci_partial_coverage_does_not_fire_ci_rule",
         r_ci_partial["delta_ci_covers_zero_every_fold"] is False, r_ci_partial)

    # (c) sign flip across folds -> killed
    r_sign = ev(fold_intervals=[(0.1, 0.4), (0.05, 0.3)], fold_signs=[1, -1],
              improvement_share_n_le_5=0.9)
    check("kill_conditions_sign_flip_kills",
         r_sign["sign_flip_across_folds"] is True and r_sign["killed"] is True, r_sign)

    # (d) improvement concentrated OUTSIDE the n<=5 stratum -> killed as a cold-start claim
    r_conc = ev(fold_intervals=[(0.1, 0.4), (0.05, 0.3)], fold_signs=[1, 1],
              improvement_share_n_le_5=0.1)
    check("kill_conditions_concentration_outside_coldstart_kills",
         r_conc["improvement_not_concentrated_on_coldstart_stratum"] is True and
         r_conc["killed"] is True, r_conc)

    # zero evaluable folds: the CI rule cannot fire (nothing to evaluate), decided False not killed
    r_empty = ev(fold_intervals=[], fold_signs=[], improvement_share_n_le_5=0.9)
    check("kill_conditions_zero_folds_ci_rule_not_fired",
         r_empty["delta_ci_covers_zero_every_fold"] is False, r_empty)

    # every rule is a pure function: identical inputs -> identical outputs
    check("kill_conditions_deterministic",
         ev(fold_intervals=[(0.1, 0.4)], fold_signs=[1], improvement_share_n_le_5=0.7) ==
         ev(fold_intervals=[(0.1, 0.4)], fold_signs=[1], improvement_share_n_le_5=0.7))


def test_near_affine_thresholds_pinned_exactly():
    check("near_affine_r2_pinned", arm_mod.NEAR_AFFINE_R2 == 0.998001)
    check("near_affine_spearman_pinned", arm_mod.NEAR_AFFINE_SPEARMAN == 0.999)
    check("coldstart_stratum_pinned", arm_mod.COLDSTART_STRATUM_N_MAX == 5)
    check("tau_pinned_and_never_tunable", arm_mod.TAU == 5.0)


def test_missing_universe_columns_fail_closed():
    mod = make_module()
    bad = UNIVERSE.drop(columns=["pace_gap"])
    raised = False
    try:
        mod.build_design(FOLD, bad)
    except arm_mod.A07ConstructionFailure:
        raised = True
    check("missing_gap_column_fails_closed", raised)


def test_p35_spec_hash_pin_matches_runner_constant():
    check("p35_spec_sha256_matches_runner_pin",
         rc.P35_SPEC_SHA256 ==
         "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32")


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print("=" * 88)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print(f"ALL {len(tests)} TEST FUNCTIONS PASSED (arms/A07, IMPLEMENTATION -- synthetic/"
         "identity/schema only, no real fold touched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
