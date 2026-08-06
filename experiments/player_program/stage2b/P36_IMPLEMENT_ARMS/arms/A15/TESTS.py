#!/usr/bin/env python3
"""TESTS.py -- identity/synthetic/schema tests for the A15_gap_by_depth_asymmetry arm module.

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

# arms/A15 imports its own module directly; it reads (never writes) the frozen runner/ and P26/
# directories to run conformance checks against the frozen contracts, per standing rule 2
# (write scope is arms/A15/ only -- nothing here writes outside it).
for p in (HERE, RUNNER, P26):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

import A15_gap_by_depth_asymmetry as arm_mod                                    # noqa: E402
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

def make_universe(n: int = 40, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "team_id": [f"T{i % 6}" for i in range(n)],
        "game_id": [f"SYNG_{i}" for i in range(n)],
        "pace_gap": rng.normal(0, 1.5, size=n),
        "pace_evidence_depth": rng.integers(0, 11, size=n).astype(float),
        "opp_pace_evidence_depth": rng.integers(0, 11, size=n).astype(float),
    })


UNIVERSE = make_universe()
FOLD_IDS = ["SYN_fold_1", "SYN_fold_2"]
FOLD = {"fold_id": "SYN_fold_1",
       "train_idx": np.arange(len(UNIVERSE)), "test_idx": np.array([], dtype=int)}


def make_module() -> "arm_mod.A15GapByDepthAsymmetry":
    return arm_mod.A15GapByDepthAsymmetry(fold_ids=FOLD_IDS, n_rows=len(UNIVERSE))


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
# 2. transform / treatment correctness ("strict lagging" analogue: asym is a pure function of
#    already-lagged evidence-depth columns, no new data, fixed transform s())
# ------------------------------------------------------------------------------------------- #

def test_s_transform_matches_formula():
    d = np.array([0.0, 5.0, 10.0])
    got = arm_mod.s_transform(d)
    expected = 1.0 / (1.0 + d / 5.0)     # s(0)=1, s(5)=0.5, s(10)=1/3
    check("s_transform_formula_and_scale_fixed_at_5",
         np.allclose(got, expected) and arm_mod.S_SCALE_H == 5.0,
         f"got {got}, expected {expected}, S_SCALE_H={arm_mod.S_SCALE_H}")
    check("s_transform_boundary_zero_depth_is_one", np.isclose(arm_mod.s_transform(0.0), 1.0))
    check("s_transform_is_bounded_in_0_1",
         bool(np.all((got > 0) & (got <= 1))), f"got {got}")


def test_asym_symmetry_and_zero_case():
    # equal depth/opp_depth -> asym == 0 exactly (own and opponent equally reliable)
    depth = np.array([3.0, 7.0, 0.0, 10.0])
    asym_equal = arm_mod.compute_asym(depth, depth)
    check("asym_zero_when_depths_equal", np.allclose(asym_equal, 0.0), f"got {asym_equal}")

    # antisymmetry: swapping depth <-> opp_depth negates asym
    depth2, opp2 = np.array([2.0, 8.0]), np.array([9.0, 1.0])
    a_fwd = arm_mod.compute_asym(depth2, opp2)
    a_swap = arm_mod.compute_asym(opp2, depth2)
    check("asym_antisymmetric_under_swap", np.allclose(a_fwd, -a_swap),
         f"forward {a_fwd}, swapped {a_swap}")

    # deeper own evidence (smaller s) than opponent -> more reliable own estimate -> asym < 0
    # (s is DECREASING in depth, so MORE own depth => SMALLER s(depth) => asym = s(depth) -
    # s(opp_depth) is negative when depth > opp_depth)
    check("asym_sign_when_own_deeper", arm_mod.compute_asym(np.array([9.0]),
         np.array([0.0]))[0] < 0)


def test_treatment_is_gap_times_asym():
    gap = np.array([1.0, -2.0, 0.0, 3.5])
    asym = np.array([0.5, -0.5, 1.0, 0.0])
    got = arm_mod.compute_treatment(gap, asym)
    expected = gap * asym
    check("treatment_column_is_elementwise_gap_times_asym", np.array_equal(got, expected),
         f"got {got}, expected {expected}")


def test_no_new_data_enters_asym_or_treatment():
    """asym/treatment are pure deterministic functions of (depth, opp_depth, gap) -- no team_id,
    game_id, season or any other column influences the value (P33 hyperparameters.handling:
    'transform frozen; no new data enters')."""
    mod = make_module()
    u1 = UNIVERSE.copy()
    u2 = UNIVERSE.copy()
    u2["team_id"] = u2["team_id"] + "_relabelled"     # perturb an irrelevant identity column
    u2["game_id"] = u2["game_id"] + "_X"
    b1 = mod.build_design(FOLD, u1)
    b2 = mod.build_design(FOLD, u2)
    check("asym_and_treatment_invariant_to_identity_columns",
         np.array_equal(b1["columns"][arm_mod.ASYM_COL], b2["columns"][arm_mod.ASYM_COL]) and
         np.array_equal(b1["columns"][arm_mod.TREATMENT_COL], b2["columns"][arm_mod.TREATMENT_COL]),
         "perturbing team_id/game_id changed asym or the treatment column")


# ------------------------------------------------------------------------------------------- #
# 3. arm-vs-null design nesting (K0_MATCHED[A15] = term_removal of exactly gap:asym; all mains,
#    including asym itself, are granted to the null -- lower-order closure R6/R5)
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
    check("asym_main_effect_granted_to_null", arm_mod.ASYM_COL in k0["nuisance_cols"],
         "the card blocks re-centring credit: asym's OWN main effect must be in the null")

    rec = ri.validate_design_bundle(bundle, UNIVERSE, mod.uses_global_intercept(), FOLD["fold_id"])
    check("runner_interface_validate_design_bundle_passes", rec["valid"], str(rec))


def test_k0_matched_contract_conformance():
    """The frozen P26 validator (shape + relation, including R6 lower-order/marginality closure
    on the gap:asym interaction) accepts this arm's K0_MATCHED record."""
    mod = make_module()
    rec = mod.p26_k0_record()
    rep = vk.validate(rec)
    check("p26_k0_matched_record_valid", rep["valid"], str(rep["blocking"]))
    check("p26_arm_kind_is_substantive_feature", rec["arm_kind"] == "substantive_feature")
    check("p26_k0_flat_role_diagnostic_only", rec["k0_flat_role"] == "diagnostic_only")


def test_r6_lower_order_closure_would_fire_if_asym_main_were_missing():
    """Adversarial check: if the null's structural_terms dropped the asym main effect (the
    re-centring-credit defect the card explicitly blocks), the frozen P26 relation checker (R6)
    must catch it. Proves the module's passing record is not passing vacuously."""
    mod = make_module()
    rec = mod.p26_k0_record()
    broken = {**rec,
             "k0_spec": {**rec["k0_spec"],
                         "structural_terms": [c for c in rec["k0_spec"]["structural_terms"]
                                              if c != arm_mod.ASYM_COL]},
             "arm_spec": {**rec["arm_spec"],
                          "structural_terms": [c for c in rec["arm_spec"]["structural_terms"]
                                               if c != arm_mod.ASYM_COL]}}
    rep = vk.validate(broken)
    check("r6_fires_when_asym_main_effect_dropped_from_k0", not rep["valid"],
         "removing asym's main effect from K0's structural terms should trip R5/R6 -- it did not")


# ------------------------------------------------------------------------------------------- #
# 4. enumeration elements exact
# ------------------------------------------------------------------------------------------- #

def test_enumeration_element_exact():
    mod = make_module()
    check("enumeration_element_empty", mod.enumeration_element() == {},
         "A15 has no enumerated grid (unlike A08/A09/A10/A11/A23); element must be {}")
    check("element_id_exact", mod.element_id() == "A15_gap_by_depth_asymmetry__single",
         mod.element_id())
    check("arm_id_exact", mod.arm_id == "A15_gap_by_depth_asymmetry", mod.arm_id)
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
    check("A15_in_ARMS_WITH_FREE_GLOBAL_INTERCEPT", "A15" in rc.ARMS_WITH_FREE_GLOBAL_INTERCEPT)
    check("A15_not_in_ARMS_WITHOUT_GLOBAL_INTERCEPT",
         "A15" not in rc.ARMS_WITHOUT_GLOBAL_INTERCEPT)
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
         "SAME_GAME blocks unconditionally at P22; none of A15's columns should ever declare it")
    check("all_lag_specs_are_derived_no_join",
         all(s["kind"] == "DERIVED_NO_JOIN" for s in specs.values()),
         "every A15 column is a deterministic function of already-cutoff-valid producer columns; "
         "none require a join or a schedule re-derivation")


def test_lag_sources_empty():
    mod = make_module()
    check("lag_sources_empty_dict", mod.lag_sources() == {},
         "A15 needs no PRIOR_GAME re-derivation source frames -- every column is DERIVED_NO_JOIN")


# ------------------------------------------------------------------------------------------- #
# 5. kill-condition hooks decidable
# ------------------------------------------------------------------------------------------- #

def test_kill_conditions_decidable():
    ev = arm_mod.evaluate_kill_conditions

    # (a) no kill: CI excludes 0 and is positive in every fold, improvement concentrated in top
    #     bucket
    r_pass = ev(fold_intervals=[(0.1, 0.4), (0.05, 0.3)],
               improvement_share_top_asym_bucket=0.9)
    check("kill_conditions_pass_case_not_killed", r_pass["killed"] is False, r_pass)

    # (b) CI covers 0 in EVERY evaluable fold -> killed
    r_ci = ev(fold_intervals=[(-0.1, 0.2), (-0.05, 0.05)],
             improvement_share_top_asym_bucket=0.9)
    check("kill_conditions_ci_covers_zero_every_fold_kills",
         r_ci["beta4_ci_covers_zero_every_fold"] is True and r_ci["killed"] is True, r_ci)

    # CI covers 0 in only SOME folds -> that specific rule does not fire
    r_ci_partial = ev(fold_intervals=[(-0.1, 0.2), (0.05, 0.3)],
                      improvement_share_top_asym_bucket=0.9)
    check("kill_conditions_ci_partial_coverage_does_not_fire_ci_rule",
         r_ci_partial["beta4_ci_covers_zero_every_fold"] is False, r_ci_partial)

    # (c) any evaluable fold's interval entirely below zero -> directional refutation kill
    r_neg = ev(fold_intervals=[(0.1, 0.4), (-0.5, -0.1)],
              improvement_share_top_asym_bucket=0.9)
    check("kill_conditions_negative_interval_refutation_kills",
         r_neg["beta4_negative_refutation_any_fold"] is True and r_neg["killed"] is True, r_neg)

    # a fold whose interval merely touches zero from below (hi == 0) is NOT entirely negative
    r_touch = ev(fold_intervals=[(0.1, 0.4), (-0.5, 0.0)],
                improvement_share_top_asym_bucket=0.9)
    check("kill_conditions_interval_touching_zero_not_negative_refutation",
         r_touch["beta4_negative_refutation_any_fold"] is False, r_touch)

    # (d) improvement concentrated OUTSIDE the top-|asym| bucket -> killed
    r_conc = ev(fold_intervals=[(0.1, 0.4), (0.05, 0.3)],
              improvement_share_top_asym_bucket=0.1)
    check("kill_conditions_concentration_outside_top_bucket_kills",
         r_conc["improvement_not_concentrated_top_asym_bucket"] is True and
         r_conc["killed"] is True, r_conc)

    # zero evaluable folds: the CI/negative rules cannot fire, decided False not killed
    r_empty = ev(fold_intervals=[], improvement_share_top_asym_bucket=0.9)
    check("kill_conditions_zero_folds_ci_rule_not_fired",
         r_empty["beta4_ci_covers_zero_every_fold"] is False, r_empty)
    check("kill_conditions_zero_folds_negative_rule_not_fired",
         r_empty["beta4_negative_refutation_any_fold"] is False, r_empty)

    # every rule is a pure function: identical inputs -> identical outputs
    check("kill_conditions_deterministic",
         ev(fold_intervals=[(0.1, 0.4)], improvement_share_top_asym_bucket=0.7) ==
         ev(fold_intervals=[(0.1, 0.4)], improvement_share_top_asym_bucket=0.7))


def test_fixed_pins_exact():
    check("s_scale_h_pinned", arm_mod.S_SCALE_H == 5.0)
    check("top_asym_bucket_quantile_pinned", arm_mod.TOP_ASYM_BUCKET_QUANTILE == 0.75)


def test_missing_universe_columns_fail_closed():
    mod = make_module()
    bad = UNIVERSE.drop(columns=["pace_gap"])
    raised = False
    try:
        mod.build_design(FOLD, bad)
    except arm_mod.A15ConstructionFailure:
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
    print(f"ALL {len(tests)} TEST FUNCTIONS PASSED (arms/A15, IMPLEMENTATION -- synthetic/"
         "identity/schema only, no real fold touched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
