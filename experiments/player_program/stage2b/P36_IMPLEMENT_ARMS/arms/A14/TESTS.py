#!/usr/bin/env python3
"""TESTS.py -- identity/synthetic/schema tests for the A14_expansion_intercept_decay arm module.

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

# arms/A14 imports its own module directly; it reads (never writes) the frozen runner/ and P26/
# directories to run conformance checks against the frozen contracts, per standing rule 2
# (write scope is arms/A14/ only -- nothing here writes outside it, and nothing here imports any
# sibling arms/ directory).
for p in (HERE, RUNNER, P26):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import A14_expansion_intercept_decay as arm_mod                                # noqa: E402
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
    """Three teams: T1 an "original" team (first season 2021, never expansion), T2 an expansion
    team debuting 2023 (>= 2022, so exp_i=1 in its debut season only), T3 a control team debuting
    2021 with a SECOND season 2022 (first season 2021 < 2022, so exp_i is always 0 for T3 even
    though it has a genuinely "early" first season under the >= 2022 clause's complement)."""
    rows = []
    for d in range(1, 7):                                  # T1, season 2021: 6 games
        rows.append({"team_id": "T1", "season": 2021, "game_date": f"2021-05-{d:02d}",
                    "game_id": f"G1_{d}"})
    for d in range(1, 4):                                  # T1, season 2022: 3 games
        rows.append({"team_id": "T1", "season": 2022, "game_date": f"2022-05-{d:02d}",
                    "game_id": f"G1b_{d}"})
    for d in range(1, 5):                                  # T2, season 2023: 4 games (debut)
        rows.append({"team_id": "T2", "season": 2023, "game_date": f"2023-05-{d:02d}",
                    "game_id": f"G2_{d}"})
    for d in range(1, 3):                                  # T2, season 2024: 2 games
        rows.append({"team_id": "T2", "season": 2024, "game_date": f"2024-05-{d:02d}",
                    "game_id": f"G2b_{d}"})
    for d in range(1, 3):                                  # T3, season 2021: 2 games (debut, but
        rows.append({"team_id": "T3", "season": 2021, "game_date": f"2021-06-{d:02d}",  # < 2022)
                    "game_id": f"G3_{d}"})
    for d in range(1, 3):                                  # T3, season 2022: 2 games
        rows.append({"team_id": "T3", "season": 2022, "game_date": f"2022-06-{d:02d}",
                    "game_id": f"G3b_{d}"})
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


def make_module() -> "arm_mod.A14ExpansionInterceptDecay":
    return arm_mod.A14ExpansionInterceptDecay(SCHEDULE, fold_ids=FOLD_IDS, n_rows=len(UNIVERSE))


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

    mod2 = make_module()
    b3 = mod2.build_design(FOLD, UNIVERSE)
    same2 = all(np.array_equal(b1["columns"][k], b3["columns"][k]) for k in b1["columns"])
    check("feature_determinism_fresh_instance", same2,
         "a fresh module instance over identical inputs produced different columns")


# ------------------------------------------------------------------------------------------- #
# 2. strict lagging: n_i (contract-schedule clock, "as A07") + exp_i (first-season identity)
# ------------------------------------------------------------------------------------------- #

def test_n_i_strict_lagging_contract_schedule_clock():
    probe = pd.DataFrame({
        "team_id": ["T1"] * 6, "season": [2021] * 6,
        "game_date": [f"2021-05-{d:02d}" for d in range(1, 7)],
    })
    n_i = arm_mod.compute_n_i(SCHEDULE, probe["team_id"].to_numpy(), probe["season"].to_numpy(),
                              probe["game_date"].to_numpy())
    expected = np.array([0, 1, 2, 3, 4, 5], dtype=float)
    check("n_i_strict_lagging_full_schedule_clock", np.array_equal(n_i, expected),
         f"got {n_i}, expected {expected}")

    dropped_schedule = SCHEDULE[SCHEDULE["game_id"] != "G1_3"]
    n_i_wrong_clock = arm_mod.compute_n_i(dropped_schedule, probe["team_id"].to_numpy(),
                                          probe["season"].to_numpy(),
                                          probe["game_date"].to_numpy())
    expected_wrong = np.array([0, 1, 2, 2, 3, 4], dtype=float)
    check("universe_row_clock_would_undercount_if_used",
         np.array_equal(n_i_wrong_clock, expected_wrong),
         "the universe-row-clock control computation did not reproduce the expected undercount")
    check("module_avoids_universe_row_clock", not np.array_equal(n_i, n_i_wrong_clock),
         "n_i computed on the full contract schedule must differ from n_i computed on the "
         "universe-only schedule whenever an excluded row precedes a query date (n_clock_pin)")

    probe2 = pd.DataFrame({"team_id": ["T1"], "season": [2022], "game_date": ["2022-05-01"]})
    n_i2 = arm_mod.compute_n_i(SCHEDULE, probe2["team_id"].to_numpy(),
                               probe2["season"].to_numpy(), probe2["game_date"].to_numpy())
    check("n_i_season_reset", n_i2[0] == 0.0, f"got {n_i2[0]}, expected 0.0 (new season)")

    probe3 = pd.DataFrame({"team_id": ["T9"], "season": [2021], "game_date": ["2021-05-01"]})
    raised = False
    try:
        arm_mod.compute_n_i(SCHEDULE, probe3["team_id"].to_numpy(), probe3["season"].to_numpy(),
                            probe3["game_date"].to_numpy())
    except arm_mod.A14ConstructionFailure:
        raised = True
    check("n_i_fails_closed_on_unresolved_team_season", raised,
         "an unresolved (team_id, season) pair must raise, not silently produce a value")


def test_league_common_decay_matches_exp_decay():
    n_i = np.array([0.0, 1.0, 5.0, 10.0])
    got = arm_mod.league_common_decay(n_i)
    expected = np.exp(-n_i / 5.0)
    check("league_common_decay_formula_and_tau_fixed_at_5",
         np.allclose(got, expected) and arm_mod.TAU == 5.0,
         f"got {got}, expected {expected}, TAU={arm_mod.TAU}")
    check("league_common_decay_strictly_positive_everywhere",
         bool(np.all(got > 0.0)),
         "exp(-n/5) must be strictly positive for every finite n_i -- this is what makes the "
         "treatment column's cluster support exactly equal exp_i's cluster support")


def test_exp_i_first_season_identity():
    # T1 first season 2021 -> exp_i = 0 in BOTH 2021 and 2022 (< 2022 floor)
    probe_t1 = pd.DataFrame({"team_id": ["T1", "T1"], "season": [2021, 2022]})
    exp_t1 = arm_mod.compute_exp_i(SCHEDULE, probe_t1["team_id"].to_numpy(),
                                   probe_t1["season"].to_numpy())
    check("exp_i_zero_for_pre_2022_first_season_team",
         np.array_equal(exp_t1, np.array([0.0, 0.0])), f"got {exp_t1}")

    # T2 first season 2023 (>= 2022) -> exp_i = 1 ONLY in the debut season 2023, 0 in 2024
    probe_t2 = pd.DataFrame({"team_id": ["T2", "T2"], "season": [2023, 2024]})
    exp_t2 = arm_mod.compute_exp_i(SCHEDULE, probe_t2["team_id"].to_numpy(),
                                   probe_t2["season"].to_numpy())
    check("exp_i_one_only_in_debut_season_when_first_season_ge_2022",
         np.array_equal(exp_t2, np.array([1.0, 0.0])), f"got {exp_t2}")

    # T3 first season 2021 (< 2022, despite a genuine debut) -> exp_i = 0 in both its seasons
    probe_t3 = pd.DataFrame({"team_id": ["T3", "T3"], "season": [2021, 2022]})
    exp_t3 = arm_mod.compute_exp_i(SCHEDULE, probe_t3["team_id"].to_numpy(),
                                   probe_t3["season"].to_numpy())
    check("exp_i_zero_for_early_debut_team_below_2022_floor",
         np.array_equal(exp_t3, np.array([0.0, 0.0])), f"got {exp_t3}")

    # unresolved team fails closed
    probe4 = pd.DataFrame({"team_id": ["T9"], "season": [2023]})
    raised = False
    try:
        arm_mod.compute_exp_i(SCHEDULE, probe4["team_id"].to_numpy(),
                              probe4["season"].to_numpy())
    except arm_mod.A14ConstructionFailure:
        raised = True
    check("exp_i_fails_closed_on_unresolved_team", raised,
         "an unresolved team_id must raise, not silently produce a value")


def test_treatment_column_nonzero_support_equals_exp_i_support():
    mod = make_module()
    bundle = mod.build_design(FOLD, UNIVERSE)
    treatment = bundle["columns"][arm_mod.TREATMENT_COL]
    exp_i = bundle["diagnostics"]["exp_i"]
    check("treatment_nonzero_iff_exp_i_one",
         np.array_equal(treatment != 0.0, exp_i == 1.0),
         "expansion_decay_interaction must be nonzero on EXACTLY the exp_i=1 rows (this is what "
         "licenses the unmodified generic P27 ActiveSetRule mechanism, see p27_rule())")
    expected_expansion_rows = int(((UNIVERSE["team_id"] == "T2").to_numpy(dtype=bool) &
                                   (UNIVERSE["season"] == 2023).to_numpy(dtype=bool)).sum())
    check("t2_debut_season_2023_rows_are_the_only_expansion_rows",
         int(exp_i.sum()) == expected_expansion_rows,
         f"got {int(exp_i.sum())}, expected {expected_expansion_rows} (only T2's 2023 debut "
         ">= 2022 rows should carry exp_i = 1)")


# ------------------------------------------------------------------------------------------- #
# 3. arm-vs-null design nesting (K0_MATCHED[A14] = term_removal of exactly the treatment)
# ------------------------------------------------------------------------------------------- #

def test_arm_vs_null_nesting():
    mod = make_module()
    bundle = mod.build_design(FOLD, UNIVERSE)
    k0 = bundle["k0_matched_design"]

    check("null_is_term_removal", k0["comparison"] == "term_removal")
    check("null_treatment_cols_empty", k0["treatment_cols"] == [])
    check("null_nuisance_equals_arm_nuisance",
         set(k0["nuisance_cols"]) == set(bundle["nuisance_cols"]),
         f"null={k0['nuisance_cols']} arm={bundle['nuisance_cols']}")
    check("null_carries_decay_but_not_expansion_interaction",
         arm_mod.DECAY_COL in k0["nuisance_cols"] and
         arm_mod.TREATMENT_COL not in k0["nuisance_cols"],
         "K0 K5: the league-common decay term is GRANTED to the null (S6 direction 1); the "
         "expansion-decay interaction is NOT (S6 direction 2)")
    check("treatment_absent_from_null",
         not (set(bundle["treatment_cols"]) & set(k0["nuisance_cols"])))
    check("null_strictly_nested_in_arm",
         set(k0["nuisance_cols"]) | set(k0["treatment_cols"]) <
         set(bundle["nuisance_cols"]) | set(bundle["treatment_cols"]),
         "the null's column set must be a STRICT subset of the arm's (nesting)")

    rec = ri.validate_design_bundle(bundle, UNIVERSE, mod.uses_global_intercept(),
                                    FOLD["fold_id"])
    check("runner_interface_validate_design_bundle_passes", rec["valid"], str(rec))


def test_k0_matched_contract_conformance():
    """The frozen P26 validator (shape + relation) accepts this arm's K0_MATCHED record. This is
    also the regression test for the NAMING DISCLOSURE in the module docstring: a colon-bearing
    treatment-term name here would trip R6 (lower_order_term_missing_from_k0) as a false positive
    against the card's own 'no expansion-indexed term' K0 clause."""
    mod = make_module()
    rec = mod.p26_k0_record()
    rep = vk.validate(rec)
    check("p26_k0_matched_record_valid", rep["valid"], str(rep["blocking"]))
    check("p26_arm_kind_is_substantive_feature", rec["arm_kind"] == "substantive_feature")
    check("p26_k0_flat_role_diagnostic_only", rec["k0_flat_role"] == "diagnostic_only")
    check("treatment_column_name_has_no_colon",
         ":" not in arm_mod.TREATMENT_COL,
         "the materialised column name must avoid the interaction-notation colon (see NAMING "
         "DISCLOSURE) to prevent a false-positive R6 finding")


# ------------------------------------------------------------------------------------------- #
# 4. enumeration elements exact
# ------------------------------------------------------------------------------------------- #

def test_enumeration_element_exact():
    mod = make_module()
    check("enumeration_element_empty", mod.enumeration_element() == {},
         "A14 has no enumerated grid; element must be {}")
    check("element_id_exact",
         mod.element_id() == "A14_expansion_intercept_decay__single", mod.element_id())
    check("arm_id_exact", mod.arm_id == "A14_expansion_intercept_decay", mod.arm_id)
    check("card_id_matches_arm_id", mod.card_id() == mod.arm_id)
    check("declared_family_pinned", mod.declared_family() == "SUBSTANTIVE")
    check("recalibration_declaration_pinned", mod.recalibration_declaration() == "NOT_APPLICABLE")
    check("uses_global_intercept_true_per_frozen_table", mod.uses_global_intercept() is True)
    check("requires_franchise_continuity_true", mod.requires_franchise_continuity() is True)
    check("p23_receipts_nonempty_and_pinned",
         len(mod.p23_receipts()) == 1 and
         mod.p23_receipts()[0]["team_cities_sha256"] == rc.TEAM_CITIES_SHA256_PIN)
    check("preregistered_contrasts_none", mod.preregistered_contrasts() is None)
    check("prereg_digest_expected_none", mod.prereg_digest_expected() is None)

    p27 = mod.p27_rule()
    check("p27_rule_registered", p27 is not None,
         "A14 registers an S7_TIER_SUPPORT_v1 active-set rule (card, single_active_fold_"
         "licensing_amended)")
    rule_kwargs, prereg_kwargs = p27
    check("p27_rule_floor_is_10", rule_kwargs["min_nonzero_clusters"] == 10)
    check("p27_rule_id_is_s7_tier_support_v1", rule_kwargs["rule_id"] == "S7_TIER_SUPPORT_v1")
    check("p27_prereg_not_registered_after_results",
         prereg_kwargs["results_visible_at_registration"] is False)


def test_module_conformance_against_frozen_runner_interface():
    mod = make_module()
    try:
        rec = ri.validate_arm_module(mod)
        ok = rec["conformant"]
    except ri.ArmModuleNonconformant as e:
        ok, rec = False, e.problems
    check("frozen_runner_interface_validate_arm_module_passes", ok, str(rec))


def test_intercept_table_agreement_with_runner_constants():
    check("A14_in_ARMS_WITH_FREE_GLOBAL_INTERCEPT", "A14" in rc.ARMS_WITH_FREE_GLOBAL_INTERCEPT)
    check("A14_not_in_ARMS_WITHOUT_GLOBAL_INTERCEPT",
         "A14" not in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT)
    check("offset_col_name_agrees_with_runner", arm_mod.OFFSET_COL == rc.OFFSET_COL)
    check("intercept_col_name_agrees_with_runner", arm_mod.INTERCEPT_COL == rc.INTERCEPT_COL)
    check("team_cities_pin_agrees_with_runner",
         arm_mod.TEAM_CITIES_SHA256_PIN == rc.TEAM_CITIES_SHA256_PIN)


def test_lag_specs_cover_every_design_column_except_structural_intercept():
    mod = make_module()
    bundle = mod.build_design(FOLD, UNIVERSE)
    declared = set(bundle["treatment_cols"]) | set(bundle["nuisance_cols"])
    specs = mod.lag_specs()
    needing_spec = declared - {arm_mod.INTERCEPT_COL}
    check("every_non_intercept_design_column_has_a_lag_spec",
         needing_spec <= set(specs), f"missing specs for {needing_spec - set(specs)}")
    check("intercept_has_no_lag_spec", arm_mod.INTERCEPT_COL not in specs,
         "the structural intercept column must not be declared as a P22 feature")
    check("lag_spec_kinds_are_frozen_p22_kinds",
         all(s["kind"] in ("SAME_GAME", "PRIOR_GAME", "SCHEDULE", "DERIVED_NO_JOIN")
             for s in specs.values()))
    check("no_lag_spec_declares_SAME_GAME",
         all(s["kind"] != "SAME_GAME" for s in specs.values()),
         "SAME_GAME blocks unconditionally at P22; none of A14's columns should ever declare it")
    check("decay_lag_kind_is_SCHEDULE", specs[arm_mod.DECAY_COL]["kind"] == "SCHEDULE")
    check("treatment_lag_kind_is_SCHEDULE", specs[arm_mod.TREATMENT_COL]["kind"] == "SCHEDULE")


def test_lag_sources_supplies_contract_schedule():
    mod = make_module()
    sources = mod.lag_sources()
    check("lag_sources_has_contract_schedule", "contract_schedule" in sources)
    check("lag_sources_contract_schedule_is_the_supplied_frame",
         sources["contract_schedule"] is mod._contract_schedule)


# ------------------------------------------------------------------------------------------- #
# 5. kill-condition / single-fold-verdict hooks decidable
# ------------------------------------------------------------------------------------------- #

def test_single_fold_verdict_decidable():
    ev = arm_mod.evaluate_single_fold_verdict

    r_floor_fail = ev(floor_met=False, kappa_interval=None)
    check("floor_fail_retires_unevaluated",
         r_floor_fail["verdict"] == "RETIRED_UNEVALUATED", r_floor_fail)

    r_ci_covers_zero = ev(floor_met=True, kappa_interval=(-0.2, 0.3))
    check("interval_covers_zero_kills", r_ci_covers_zero["verdict"] == "KILLED", r_ci_covers_zero)

    r_ci_excludes_zero = ev(floor_met=True, kappa_interval=(0.1, 0.5))
    check("interval_excludes_zero_is_preliminary_supported",
         r_ci_excludes_zero["verdict"] == "PRELIMINARY_SUPPORTED_SINGLE_FOLD",
         r_ci_excludes_zero)
    check("preliminary_supported_carries_f4_caveats",
         r_ci_excludes_zero["f4_caveats"] == arm_mod.F4_CAVEATS)
    check("killed_and_retired_verdicts_carry_no_f4_caveats",
         r_ci_covers_zero["f4_caveats"] is None and r_floor_fail["f4_caveats"] is None)

    r_ci_excludes_zero_negative = ev(floor_met=True, kappa_interval=(-0.5, -0.1))
    check("interval_excludes_zero_negative_is_also_preliminary_supported",
         r_ci_excludes_zero_negative["verdict"] == "PRELIMINARY_SUPPORTED_SINGLE_FOLD")

    raised = False
    try:
        ev(floor_met=True, kappa_interval=None)
    except ValueError:
        raised = True
    check("floor_met_without_interval_raises", raised,
         "floor_met=True must be accompanied by an actual kappa_interval (the fold was fit)")

    raised2 = False
    try:
        ev(floor_met=True, kappa_interval=(0.5, 0.1))
    except ValueError:
        raised2 = True
    check("malformed_interval_raises", raised2, "ci_low > ci_high must raise")

    check("verdict_deterministic",
         ev(floor_met=True, kappa_interval=(0.1, 0.4)) ==
         ev(floor_met=True, kappa_interval=(0.1, 0.4)))


def test_evaluate_kill_conditions_wrapper():
    ev = arm_mod.evaluate_kill_conditions
    check("retired_is_killed", ev(floor_met=False, kappa_interval=None)["killed"] is True)
    check("ci_covers_zero_is_killed",
         ev(floor_met=True, kappa_interval=(-0.1, 0.1))["killed"] is True)
    check("preliminary_supported_is_not_killed",
         ev(floor_met=True, kappa_interval=(0.2, 0.4))["killed"] is False)


def test_no_sign_instability_hook_exists():
    # card, verbatim: "sign instability is UNDEFINED with one fold and is replaced by the
    # promotion-ineligibility declaration above" -- there must be no sign-flip kill function.
    check("no_sign_flip_kill_function_defined",
         not hasattr(arm_mod, "sign_flip_kill"),
         "A14 (single active fold) must not expose a cross-fold sign-instability kill hook; "
         "that check is UNDEFINED for this arm by card construction")


def test_missing_universe_columns_fail_closed():
    mod = make_module()
    bad = UNIVERSE.drop(columns=["pace_gap"])
    raised = False
    try:
        mod.build_design(FOLD, bad)
    except arm_mod.A14ConstructionFailure:
        raised = True
    check("missing_gap_column_fails_closed", raised)


def test_p35_spec_hash_pin_matches_runner_constant():
    check("p35_spec_sha256_matches_runner_pin",
         rc.P35_SPEC_SHA256 ==
         "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32")
    check("module_own_pin_matches_runner_pin",
         arm_mod.P35_SPEC_SHA256 == rc.P35_SPEC_SHA256)


def test_tau_and_floor_pinned_exactly():
    check("tau_pinned_and_never_tunable", arm_mod.TAU == 5.0)
    check("first_season_floor_pinned", arm_mod.FIRST_SEASON_FLOOR == 2022)
    check("s7_tier_floor_pinned", arm_mod.S7_TIER_FLOOR_CLUSTERS == 10)


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print("=" * 88)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print(f"ALL {len(tests)} TEST FUNCTIONS PASSED (arms/A14, IMPLEMENTATION -- synthetic/"
         "identity/schema only, no real fold touched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
