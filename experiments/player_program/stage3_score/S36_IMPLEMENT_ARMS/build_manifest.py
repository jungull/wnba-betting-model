#!/usr/bin/env python3
"""build_manifest.py -- assemble RUNNER_MANIFEST.json, the node's declared required output.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

Runs the whole node end to end, in the order the obligations require, and refuses to write a
manifest if any step fails:

    1. prebuild/PREBUILD_GAME_ID_DIGEST.py   (O2 -- before any design matrix exists)
    2. runner/build_all.py                   (16 designs x 5 folds, Layer-A parity, NO fit)
    3. runner/verify_carded_strata.py        (kill strata re-derived from this node's features)
    4. tests/TESTS.py                        (the suite; must be all green)

Run:  python build_manifest.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

NODE = Path(__file__).resolve().parent
sys.path.insert(0, str(NODE / "runner"))
sys.path.insert(0, str(NODE / "arms"))

import runner  # noqa: E402
import runner_constants as K  # noqa: E402
from canon import sha256_file  # noqa: E402
from obligations import (C1_PROGRAM_ALPHA, C2_POWER_STATEMENT, C3_BINDING_RULE,  # noqa: E402
                         C3_LABEL, O1_MASTER_TEAM_PIN, O2_PREBUILD_DIGEST, O5_RECEIPT_ID,
                         O6_RECEIPT_ID, O7_RULE, REPORTING_RULE, stamp_program_alpha,
                         verify_obligation_text)

STEPS = [("O2 pre-build game_id digest", ["prebuild/PREBUILD_GAME_ID_DIGEST.py"]),
         ("design build + Layer-A parity", ["runner/build_all.py"]),
         ("carded kill-stratum re-derivation", ["runner/verify_carded_strata.py"]),
         ("test suite", ["tests/TESTS.py"])]


def run_steps() -> list[dict]:
    out = []
    for name, args in STEPS:
        p = subprocess.run([sys.executable, *args], cwd=NODE, capture_output=True, text=True)
        out.append({"step": name, "script": args[0], "returncode": p.returncode,
                    "ok": p.returncode == 0,
                    "stderr_tail": (p.stderr or "")[-800:] if p.returncode else ""})
        if p.returncode:
            print(f"STEP FAILED: {name}\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}")
    return out


def main() -> int:
    steps = run_steps()
    if not all(s["ok"] for s in steps):
        print("refusing to write RUNNER_MANIFEST.json: a step failed")
        return 1

    def load(fn):
        return json.loads((NODE / fn).read_text(encoding="utf-8"))

    prebuild = load("PREBUILD_GAME_ID_DIGEST.json")
    parity = load("DESIGN_PARITY_RECEIPT.json")
    strata = load("CARDED_STRATA_RECEIPT.json")
    tests = load("TEST_RECEIPT.json")

    mods = runner.load_modules()
    elements = []
    for spec in runner.all_elements(mods):
        elements.append({
            "element_id": spec.element_id, "arm_id": spec.arm_id, "estimand": spec.estimand,
            "primary_metric": spec.primary_metric, "arm_kind": spec.arm_kind,
            "family_primary": spec.family_primary, "card_sha256": spec.card_sha256,
            "module": [f for f in runner.ARM_MODULE_FILES
                       if spec.arm_id.split("_")[0].lower() in f][0],
            "design_built_on_real_universe": spec.element_id in parity["elements"],
            "kill_conditions": list(spec.kill_conditions),
            "mandatory_receipts": list(spec.mandatory_receipts),
            "structurally_deactivated_folds": list(spec.structurally_deactivated_folds),
            "sign_pin": spec.sign_pin, "notes": list(spec.notes)})

    manifest = {
        "schema": "player_program/s36_implementation/1",
        "node": "S36_IMPLEMENT_ARMS", "lane": "score", "cycle": 2,
        "epistemic_status": ("IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no "
                             "comparative historical performance is revealed."),
        "root_stated_explicitly": str(K.PROGRAM_WORKTREE),

        "authorises": ("NOTHING beyond what S35 authorised. This node implements; it does not "
                       "fit, does not adjudicate and does not mark its own work accepted."),
        "not_authorised_fitting": K.NOT_AUTHORISED_FITTING,

        # ---------------------------------------------------------------- inputs, all re-pinned
        "inputs_verified_sha256": {rel: sha256_file(K.artifact_path(rel))
                                   for rel in list(K.INPUT_PINS)
                                   + [K.SPEC_V2_PATH, K.FREEZE_SPEC_PATH,
                                      K.COMPARISON_GATE_PATH]},
        "input_pins_all_matched": True,

        # ---------------------------------------------------------------- the slate
        "counts": {"arms_implemented": len(mods), "element_cards_implemented": len(elements),
                   "arms_withdrawn_not_implemented": list(K.WITHDRAWN_ARM_IDS),
                   "designs_built_on_real_universe": len(parity["elements"]),
                   "designs_deferred": len(parity["skipped"]),
                   "check": "11 arms, 17 element cards; SC07 withdrawn by measurement"},
        "elements": elements,
        "deferred": parity["skipped"],

        # ---------------------------------------------------------------- the obligations
        "obligations_discharged": {
            "O1_ROOT_PATH_RULE": {
                "obligation": O1_MASTER_TEAM_PIN,
                "where": ["prebuild/PREBUILD_GAME_ID_DIGEST.py::verify_root_path_rule",
                          "runner/universe.py::_verify_input_pins",
                          "runner/runner_constants.py::PROGRAM_WORKTREE / "
                          "KNOWN_DRIFTED_MASTER_TEAM_SHA256"],
                "mechanism": ("re-hashed independently at this node before anything was built; "
                              "the drifted data-worktree copy is refused BY NAME, not merely by "
                              "pin mismatch; the worktree root is derived from the module's own "
                              "location, never from cwd or an environment variable"),
                "verified_sha256": prebuild["root_path_rule"]["sha256"],
                "match": prebuild["root_path_rule"]["match"]},
            "O2_C4_PREBUILD_GAME_ID_DIGEST": {
                "obligation": O2_PREBUILD_DIGEST,
                "where": ["prebuild/PREBUILD_GAME_ID_DIGEST.py",
                          "PREBUILD_GAME_ID_DIGEST.json",
                          "runner/universe.py::build_universe (fails closed)"],
                "mechanism": ("emitted BEFORE any design matrix existed, and structurally so: "
                              "the discharging script imports only pure hashing, pure pins and "
                              "pure text, and cannot construct a design. build_universe() then "
                              "refuses to return a frame unless this receipt exists and the "
                              "built game_id set re-derives to it."),
                "GAME_ID_SET_SHA256": prebuild["GAME_ID_SET_SHA256"],
                "n_clusters": prebuild["n_clusters"],
                "n_team_game_rows": prebuild["n_team_game_rows"],
                "per_season_census": prebuild["per_season_census"],
                "league_average_v1_identity_holds":
                    prebuild["league_average_v1_identity"]["identity_holds"],
                "closes_invariants_rows_deferral_on_all_17_records": True},
            "C1_PROGRAM_ALPHA_DISCLOSURE": {
                "where": ["runner/obligations.py::stamp_program_alpha",
                          "every receipt this node writes"],
                "mechanism": "both bounds stamped on every receipt; 0.40 named GOVERNING",
                **C1_PROGRAM_ALPHA},
            "C2_SC06_ERA_KILL_POWER_STATEMENT": {
                "mandatory_text": C2_POWER_STATEMENT,
                "where": ["runner/obligations.py::stamp_sc06_power_statement / "
                          "assert_sc06_era_verdict_carries_power_statement",
                          "arms/sc06_sched_fatigue_diff.py::era_split_receipt",
                          "CARDED_STRATA_RECEIPT.json::checks.SC06_abs_F_diff_ge_1"],
                "mechanism": ("era_split_receipt is the ONLY emitter of an era-split table or "
                              "era-kill verdict in this node; it stamps the verbatim statement "
                              "and then re-asserts its presence before returning, so a verdict "
                              "without it cannot be constructed. The statement also travels with "
                              "the census that is its evidence."),
                "power_census_re_derived_at_S36": {
                    "pooled_at_abs_F_diff_ge_1":
                        strata["checks"]["SC06_abs_F_diff_ge_1"][
                            "measured_rest_components_only"]["pooled"],
                    "pooled_test":
                        strata["checks"]["SC06_abs_F_diff_ge_1"][
                            "measured_rest_components_only"]["pooled_test"],
                    "agrees_with_card": strata["checks"]["SC06_abs_F_diff_ge_1"]["all_agree"]}},
            "C3_SC11_E2_RECEIPT_LABEL": {
                "label": C3_LABEL, "binding_rule": C3_BINDING_RULE,
                "where": ["runner/obligations.py::label_sc11_cross_estimand / "
                          "assert_sc11_cross_estimand_labelled",
                          "arms/sc11_league_total_drift.py::cross_estimand_receipt"],
                "mechanism": ("cross_estimand_receipt is the ONLY constructor; it applies the "
                              "label, sets citable=False, enters_family=None, "
                              "enters_pass_tally=False, and names the number "
                              "abs_delta_mae_E2_NON_CITABLE rather than delta_mae so a caller "
                              "cannot lift it out by habit. The label is re-asserted before "
                              "return.")},
            "reporting_rule": {
                "rule": REPORTING_RULE,
                "where": ["the two self-checking emitters above",
                          "tests/TESTS.py (both refusals are tested in both directions)"]},
            "O5_R_SC08_FLOOR": {
                "receipt_id": O5_RECEIPT_ID,
                "where": ["arms/sc08_sigma_margin_map.py::r_sc08_floor_receipt"],
                "mechanism": ("built and schema-tested before S38 so its absence cannot be "
                              "discovered late; takes NO challenger argument, because the card "
                              "says the challenger's number is not part of this receipt; "
                              "registered as a non-gating agreement receipt on SC01::E3 and "
                              "SC06::E3 as well"),
                "gating_on": "SC08_SIGMA_MARGIN_MAP::E3_HOME_WIN_PROB",
                "absence_is_a_card_defect": True},
            "O6_R_A1_EXCEPTIONS": {
                "receipt_id": O6_RECEIPT_ID,
                "where": ["every ElementSpec.mandatory_receipts",
                          "arms/sc06_sched_fatigue_diff.py (A1-SENSITIVITY kill carried)"],
                "mechanism": ("declared mandatory on all 17 elements and asserted in tests; "
                              "SC06's game_date lineage is carried at "
                              "CUTOFF_VALID_WITH_ENUMERATED_EXCEPTIONS, never unconditional")},
            "O7_IDENTITY_SET_EXTENSION_REVIEWABLE": {
                "rule": O7_RULE,
                "where": ["runner/obligations.py::O7_EXTENSION_COLUMNS",
                          "tests/TESTS.py (column-grain classification check against SPEC_V2)"],
                "mechanism": ("the six extension columns and the base closed set are validated "
                              "at COLUMN grain against the frozen bytes, and every column "
                              "classified NEVER_READ is asserted to carry "
                              "current_game_row_consumed = false, so a later reviewer rejecting "
                              "any extension member can read off the affected elements")},
            "S35_CARRIED_JOIN_KEY_GAP": {
                "obligation": ("S36 must state the join-key separator convention explicitly when "
                               "it recomputes byte pins under R10, so the pin becomes "
                               "reproducible by a third party."),
                "where": ["runner/canon.py (UNIT_SEP / RECORD_SEP, join_key_digest)",
                          "BYTE_PIN_CANONICALISATION.md",
                          "tests/TESTS.py (positive AND negative control)"],
                "mechanism": ("closed BY MEASUREMENT over 576 candidate conventions; exactly one "
                              "reproduces the frozen join_key_sha256: components joined WITHIN a "
                              "row by U+001E RECORD SEPARATOR, rows joined by U+001F UNIT "
                              "SEPARATOR. NO DIGEST WAS CHANGED."),
                "status": "CLOSED"}},

        # ---------------------------------------------------------------- receipts written
        "receipts": {
            "PREBUILD_GAME_ID_DIGEST.json": sha256_file(NODE / "PREBUILD_GAME_ID_DIGEST.json"),
            "DESIGN_PARITY_RECEIPT.json": sha256_file(NODE / "DESIGN_PARITY_RECEIPT.json"),
            "CARDED_STRATA_RECEIPT.json": sha256_file(NODE / "CARDED_STRATA_RECEIPT.json"),
            "TEST_RECEIPT.json": sha256_file(NODE / "TEST_RECEIPT.json")},

        # ---------------------------------------------------------------- evidence
        "layer_a_parity": {
            "elements_checked": len(parity["elements"]), "folds_per_element": len(K.FOLD_IDS),
            "all_differ_only_by_treatment_terms": True,
            "mechanism": ("one column dictionary, two column-name lists; validate_design "
                          "reconstructs the K0 from the arm and refuses anything else")},
        "carded_strata_reproduction": {
            "all_agree": strata["all_strata_agree"],
            "strata": {k: (v.get("measured") or v.get("measured_rest_components_only"))["pooled"]
                       for k, v in strata["checks"].items()},
            "what_this_proves": ("every kill in this slate fires on a subset defined by a feature "
                                 "this node builds, so reproducing the carded censuses from this "
                                 "node's own feature code tests the implementations against the "
                                 "preregistration end to end -- clock, sequencing, support "
                                 "floors and row base -- without computing any metric")},
        "tests": {"run": tests["tests_run"], "passed": tests["tests_passed"],
                  "all_green": tests["all_green"],
                  "what_is_NOT_covered": tests["what_is_NOT_covered"]},
        "steps": steps,

        # ---------------------------------------------------------------- findings raised
        "findings_raised_to_S37": [
            {"id": "F1", "severity": "informational, RESOLVED BY MEASUREMENT",
             "finding": ("the slate-wide EWMA convention is unstated on every card. Sweeping 36 "
                         "combinations, exactly one reproduces all seven of SC12's carded habitat "
                         "numbers: the RECURSIVE form (pandas adjust=False). Applied uniformly to "
                         "SC04, SC10, SC11, SC12. Cycle-1 had flagged the same gap as an open "
                         "interpretive pin on A10."),
             "where": "runner/features_common.py, runner/verify_carded_strata.py"},
            {"id": "F2", "severity": "card-internal discrepancy, DISCLOSED, no inference changes",
             "finding": ("SC12's habitat census reproduces exactly only with the >= 3 prior-games "
                         "support floor NOT applied, while the same card's parameters and "
                         "fallback_cold_start make that floor normative. This node BUILDS the "
                         "normative reading and reports both. MEASURED CONSEQUENCE: neither kill "
                         "changes behaviour -- bite habitat 652 vs 649, both non-empty in every "
                         "fold; integrity p90 4.7058 vs 4.6795, both ~4.7x the 1.0 threshold."),
             "where": "arms/sc12_robust_input_winsor.py, CARDED_STRATA_RECEIPT.json"},
            {"id": "F3", "severity": "contradiction between two frozen fields, RAISED not resolved",
             "finding": ("three E3 cards (SC01::E3, SC06::E3, SC08::E3) list composite_p_home in "
                         "arm_spec.structural_terms while their own formula fields fit only the "
                         "composite MARGIN through the link, and a4_sc08_null_strength_receipt "
                         "describes the E3 K0s the same way. The fitted-column reading is also "
                         "not implementable as frozen: the column carries 188 structural NaN rows "
                         "(re-measured here; the byte pin records n_nan=188) and no card declares "
                         "an imputation. Implemented as a null-granted INGREDIENT, which is what "
                         "R_SC08_FLOOR consumes it as."),
             "where": "arms/_head.py::P_HOME_READING"},
            {"id": "F4", "severity": "consequence of the card, not a gap",
             "finding": ("SC09's treatment feature is a hinge of the element's OWN FITTED K0 "
                         "prediction, so its design cannot be materialised on the real universe "
                         "while fitting is unauthorised. Recorded as deferred, fully implemented, "
                         "and fully exercised on synthetic data. build() takes the fold's K0 fit "
                         "as an argument so no second, differently-fitted g_hat can exist."),
             "where": "arms/sc09_fav_gap_compression.py"},
            {"id": "F5", "severity": "interpretive pins, declared",
             "finding": ("SC05: var_m read as the pooled variance of team-game margins on the "
                         "fold's TRAINING rows, and tau2/var_m as fold-train constants while "
                         "n_home/n_away are the row's own strictly-prior counts. SC06: a "
                         "STANDARD-offset tz map covering exactly the six IANA zones in the "
                         "pinned team_cities.csv, enumerated so a seventh zone fails closed. "
                         "SC08: game-level pace read as the SUM of the two sides, which is "
                         "provably immaterial because z-scoring is scale-invariant (tested)."),
             "where": "arms/sc05_hca_team_offsets.py, arms/sc06_sched_fatigue_diff.py, "
                      "arms/sc08_sigma_margin_map.py"},
            {"id": "F6", "severity": "self-reported defect in this node's own first pass, FIXED",
             "finding": ("the lambda-selection record initially wrote train-tail MAE values into "
                         "DESIGN_PARITY_RECEIPT.json. Computing them is required by the cards' own "
                         "construction rule for SC01 and SC10; leaving them on disk violates 'no "
                         "performance number emitted anywhere'. They are now withheld, and the "
                         "test that caught it was strengthened from whole-word to substring "
                         "matching."),
             "where": "arms/_head.py::select_lambda_train_tail, tests/TESTS.py"}],

        "stop_condition": {
            "tripped": False,
            "detail": ("Nothing here changes the cycle-2 estimands (E1/E2/E3), the K0 structure, "
                       "the inference structure, the declared universe (1,491 / 2,982), the "
                       "cutoff-valid feature set or the leakage status. F2 and F3 are "
                       "contradictions WITHIN frozen bytes, raised and carried with both readings "
                       "preserved, not resolved inside this node. The cards are immutable from "
                       "the freeze onward; any repair is a new erratum record, never an edit.")},

        "prohibitions_honoured": (
            "No fit on real data. No MAE, Brier, accuracy or arm-vs-null comparison computed, "
            "reported or left on disk anywhere. Nothing under stage2b/SEALED_RESULTS or "
            "stage3_score/SEALED_RESULTS was read, listed or globbed. No frozen artifact "
            "modified. git was not run. All writes are inside "
            "experiments/player_program/stage3_score/S36_IMPLEMENT_ARMS/. Every measurement ran "
            "against the PROGRAM WORKTREE, whose master_team.parquet matches ad79ce5c...; the "
            "drifted copy was never read."),
        "does_not_mark_own_work_accepted": True,
        "code_state": runner.code_state(),
        "obligation_text_check": verify_obligation_text(),
    }
    stamp_program_alpha(manifest)
    manifest["manifest_digest"] = runner.manifest_digest(manifest)
    (NODE / "RUNNER_MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, default=str) + "\n", encoding="utf-8")
    print("RUNNER_MANIFEST.json written")
    print("  arms                :", manifest["counts"]["arms_implemented"])
    print("  element cards       :", manifest["counts"]["element_cards_implemented"])
    print("  designs built (real):", manifest["counts"]["designs_built_on_real_universe"])
    print("  tests               :", f"{tests['tests_passed']}/{tests['tests_run']}")
    print("  game_id digest      :", prebuild["GAME_ID_SET_SHA256"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
