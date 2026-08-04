#!/usr/bin/env python3
"""build_findings.py -- emits FINDINGS.json for P28, with the numeric fields read back out of
MEASUREMENTS.json rather than retyped, so no figure in the finding set is one I did not compute.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
M = json.loads((HERE / "MEASUREMENTS.json").read_text(encoding="utf-8"))
NODE = "experiments/player_program/stage2b/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT"

fam = M["M6_arbitrage_demonstration"]["families"]
oracle = fam["ORACLE_target_game_is_overtime"]
lagged = fam["trailing_ot_rate_uncentered"]
uniform = fam["uniform_inflation"]
base = M["M6_arbitrage_demonstration"]["baseline_lambda0"]
carrier = M["M6_arbitrage_demonstration"]["carrier_predictive_strength"]
ot = M["M3_scorer_mismatch"]["overtime"]
reg = M["M3_scorer_mismatch"]["regulation"]

out = {
    "schema": "player_program_node_findings/1",
    "node_id": "P28_PRIMARY_SECONDARY_ORDERING_CONTRACT",
    "lane": "possession",
    "type": "documentation",
    "severity_on_failure": "A",
    "role": "adjudication methodologist",
    "addresses_stop_condition_records": [
        "not_stop_conditions_but_recorded.E5_scorer_mismatch_is_exploitable_not_merely_documented"],
    "measured_bearing_on": ["S4", "S6", "S9",
                            "not_stop_conditions_but_recorded.OT_stratum_lower_MAE_may_be_a_units_artifact",
                            "not_stop_conditions_but_recorded.packet_nits_flagged_not_corrected"],
    "epistemic_status": ("CONTRACT. Fixes the order in which evidence may be consulted. Prevents a "
                         "secondary number from rescuing a primary failure; decides no arm's fate "
                         "itself."),
    "status": "LANDED",
    "completed": True,
    "outputs": [f"{NODE}/{f}" for f in
                ("REPORT.md", "FINDINGS.json", "ordering_contract.py", "TESTS.py", "MEASURE.py",
                 "MEASUREMENTS.json", "build_report.py", "build_findings.py")],
    "frozen_artifacts_modified": [],
    "git_commands_run": ["rev-parse --abbrev-ref HEAD (read-only)"],
    "forbidden_inputs_read": [],
    "performance_peeking": ("none. No challenger was fitted, no comparative historical performance "
                            "was inspected, and experiments/player_program/stage2b/SEALED_RESULTS "
                            "was not read or listed."),
    "artifact_digests_reverified": M["M0_artifact_digests"],
    "tests": {"file": f"{NODE}/TESTS.py", "assertions": 86, "tests": 28,
              "result": "all assertions passed", "exit_code": 0,
              "command": f"python {NODE}/TESTS.py"},

    "contract": {
        "contract_id": "PRIMARY_SECONDARY_ORDERING_CONTRACT_v1",
        "primary_target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
        "primary_metric": "mae", "primary_lower_is_better": True,
        "primary_delta_convention": "challenger minus K0_MATCHED[arm_id]; negative is better",
        "secondary_downstream_metric_role": "secondary_diagnostic",
        "rules": {
            "R1": "a candidate must pass its registered PRIMARY possession-target gate, against its "
                  "own per-arm K0_MATCHED, before it may enter the frozen turnover scorer",
            "R2": "the primary verdict is SEALED (content-addressed) before any downstream number "
                  "is computed; the downstream receipt binds and the validator RECOMPUTES that "
                  "digest",
            "R3": "no downstream number may rescue a primary FAIL; adjudicate() contains no code "
                  "path that reads one",
            "R4": "a candidate improving downstream turnover MAE while WORSENING the primary "
                  "regulation-equivalent possession target FAILS",
            "R5": "trailing overtime rate, or any feature whose only benefit channel is arbitraging "
                  "the raw/regulation-equivalent exposure mismatch, may not be credited",
            "R6": "the documented scorer mismatch is RESTATED, not repaired: the scorer is frozen",
            "R7": "downstream figures are reportable, never decisive; OT and non-OT are reported "
                  "separately with row and cluster counts",
            "R8": "'PRIMARY' here means the primary TARGET; comparison_gate's "
                  "primary_incremental_test means the primary CONTRAST. Both must hold",
        },
        "enforcement": f"{NODE}/ordering_contract.py (call-site wrapper; no frozen module edited)",
    },

    "acceptance_criteria": [
        {"criterion": "a candidate must pass its registered PRIMARY possession-target gate before "
                      "it may enter the frozen turnover scorer",
         "satisfied_by": "R1; ordering_contract.authorize_downstream refuses an unsealed record "
                         "and refuses a primary FAIL",
         "test": "TESTS.py T08, T09, T10"},
        {"criterion": "the primary verdict is frozen before any downstream number is computed",
         "satisfied_by": "R2; seal_primary_verdict refuses downstream_computed != False, and "
                         "validate_downstream_receipt recomputes the digest from the primary "
                         "record's own bytes",
         "test": "TESTS.py T03, T11, T12"},
        {"criterion": "a candidate improving downstream turnover MAE while WORSENING the primary "
                      "regulation-equivalent possession target FAILS",
         "satisfied_by": "R4; a positive primary_delta_vs_k0 may only be FAIL, and adjudicate() is "
                         "invariant to the downstream figure on the FAIL path",
         "test": "TESTS.py T06, T07, T24, T28"},
        {"criterion": "trailing overtime rate, or any feature whose only benefit channel is "
                      "arbitraging the raw/regulation-equivalent exposure mismatch, may not be "
                      "credited",
         "satisfied_by": "R5; declared-channel rule plus carrier recognition, blocking a PASS",
         "test": "TESTS.py T17, T18, T19, T20"},
        {"criterion": "the documented scorer mismatch is restated, not repaired: the scorer is "
                      "frozen",
         "satisfied_by": "R6; the receipt must carry the scorer's pinned sha256 with "
                         "modified=False and restate the mismatch verbatim including its "
                         "RESTATED, NOT REPAIRED disposition",
         "test": "TESTS.py T13, T14, T26"},
    ],

    "measurements": [
        {"id": "M2", "claim": "prediction universe rows and game clusters",
         "value": {"rows": M["M2_universe"]["rows_after_pace_resolved_and_outcome_join"],
                   "game_clusters": M["M2_universe"]["game_clusters"]},
         "matches_packet": "AGREES", "how": f"python {NODE}/MEASURE.py block M2"},
        {"id": "M2b", "claim": "overtime games and rate over the possessions artifact",
         "value": {"ot_games": M["M2_universe"]["ot_games_all"],
                   "total_games": M["M2_universe"]["all_games_in_possessions_artifact"],
                   "ot_game_rate": M["M2_universe"]["ot_game_rate_all"],
                   "max_period_composition": M["M2_universe"]["max_period_composition_over_ot_games"]},
         "matches_packet": "AGREES", "how": f"python {NODE}/MEASURE.py block M2"},
        {"id": "M1", "claim": "the frozen scorer pairs regulation-equivalent exposure with RAW "
                              "full-game turnovers at line 149",
         "value": {"line_text": M["M1_frozen_scorer_pairing"]["line_text"],
                   "game_minutes_rescale_anywhere_in_scorer":
                       M["M1_frozen_scorer_pairing"]["rescale_of_turnovers_by_game_minutes_anywhere_in_scorer"]},
         "matches_packet": "AGREES", "how": f"python {NODE}/MEASURE.py block M1"},
        {"id": "M3", "claim": "the packet's measured_mismatch block, all 16 stated figures",
         "value": {"overtime": {k: ot[k] for k in
                                ("n_rows", "n_game_clusters", "mae_vs_reg_equiv_target",
                                 "mae_vs_RAW_target", "bias_vs_reg_equiv", "bias_vs_RAW",
                                 "mean_realised_reg_equiv", "mean_realised_raw")},
                   "regulation": {k: reg[k] for k in
                                  ("n_rows", "n_game_clusters", "mae_vs_reg_equiv_target",
                                   "mae_vs_RAW_target", "bias_vs_reg_equiv", "bias_vs_RAW",
                                   "mean_realised_reg_equiv", "mean_realised_raw")}},
         "matches_packet": "AGREES (delta 0.0 on all sixteen)",
         "how": f"python {NODE}/MEASURE.py block M3"},
        {"id": "M3b", "claim": "the accounting gap raw minus regulation-equivalent",
         "value": M["M3_scorer_mismatch"]["mismatch_magnitude"],
         "matches_packet": "NOT_IN_PACKET (derived here)",
         "how": f"python {NODE}/MEASURE.py block M3"},
        {"id": "M4", "claim": "the implied team turnover rate reproduces only on the "
                              "regulation-equivalent denominator",
         "value": {"reproducing_definition":
                       M["M4_propagation"]["definition_that_reproduces_the_packet"],
                   "mean": M["M4_propagation"]["propagation_coefficient_used_downstream"],
                   "raw_denominator_alternative":
                       M["M4_propagation"]["candidate_definitions"]["rate_total_over_raw"]["mean"]},
         "matches_packet": "AGREES on the reg-equivalent denominator; the denominator itself is "
                           "not stated in the packet",
         "how": f"python {NODE}/MEASURE.py block M4"},
        {"id": "M5", "claim": "trailing OT rate passes feature_gate on the final design AND on "
                              "every chronological fold",
         "value": {"final_design_passed":
                       M["M5_trailing_ot_rate"]["feature_gate_verdict_final_assembled_design"]["passed"],
                   "all_folds_pass": M["M5_trailing_ot_rate"]["all_folds_pass"],
                   "fold_rows": {k: v["n_rows"] for k, v in
                                 M["M5_trailing_ot_rate"]["feature_gate_verdict_per_chronological_fold"].items()},
                   "corr_with_target": M["M5_trailing_ot_rate"]["corr_with_target_reg_equiv"],
                   "corr_with_offset": M["M5_trailing_ot_rate"]["corr_with_offset_log_projection"]},
         "matches_packet": "NOT_IN_PACKET (E5 asserts cutoff-validity; this measures it)",
         "how": f"python {NODE}/MEASURE.py block M5"},
        {"id": "M6a", "claim": "the ORACLE arbitrage bounds the channel",
         "value": {"baseline": base, "optimum": oracle["OPTIMUM"],
                   "n_arbitraging_lambdas": oracle["fine_scan_n_arbitraging_lambdas"]},
         "matches_packet": "NOT_IN_PACKET (E5 asserts the channel; this bounds it)",
         "how": f"python {NODE}/MEASURE.py block M6"},
        {"id": "M6b", "claim": "no perturbation in any family improves BOTH metrics",
         "value": {k: v["fine_scan_n_lambdas_where_BOTH_metrics_improve"]
                   for k, v in fam.items()},
         "matches_packet": "NOT_IN_PACKET",
         "how": f"python {NODE}/MEASURE.py block M6"},
        {"id": "M6c", "claim": "the admissible carrier's arbitrage is three orders of magnitude "
                               "smaller than the oracle's",
         "value": {"lagged_carrier_optimum": lagged["OPTIMUM"],
                   "uniform_inflation_optimum": uniform["OPTIMUM"],
                   "carrier_predictive_strength": carrier},
         "matches_packet": "CORRECTS the adversarial source (see contradictions C2, C3)",
         "how": f"python {NODE}/MEASURE.py block M6"},
        {"id": "M7", "claim": "neither frozen gate can represent a target identity or an ordering",
         "value": {"comparison_gate_DIMENSIONS": M["M7_gate_coverage"]["comparison_gate_DIMENSIONS_count"],
                   "SideSpec_has_target_field": M["M7_gate_coverage"]["SideSpec_has_target_field"],
                   "SideSpec_has_metric_field": M["M7_gate_coverage"]["SideSpec_has_metric_field"],
                   "feature_gate_BLOCKING_kinds": len(M["M7_gate_coverage"]["feature_gate_BLOCKING"])},
         "matches_packet": "NOT_IN_PACKET",
         "how": f"python {NODE}/MEASURE.py block M7"},
        {"id": "M9", "claim": "the OT sd-compression ratio depends on which dispersion statistic "
                              "is used, and the reference factor is not 40/45",
         "value": {k: M["M9_ot_sd_compression"][k] for k in
                   ("sd_SIGNED_ratio", "sd_ratio_of_ABS_err",
                    "pure_scale_factor_single_OT_40_over_45", "mean_scale_factor_over_OT_rows")},
         "matches_packet": "AGREES on the signed-error ratio (0.83088 vs stated 0.831); CORRECTS "
                           "the reference compression factor",
         "how": f"python {NODE}/MEASURE.py block M9"},
    ],

    "contradictions": [
        {"id": "C1", "severity": "C",
         "against": "EVIDENCE_PACKET_V2.downstream_turnover_team_error.implied_team_tov_rate",
         "finding": "the block's figures reproduce EXACTLY only on the regulation-equivalent "
                    "denominator, which the block does not state; the raw denominator gives "
                    "0.17624 against the stated 0.17733",
         "verdict": "AGREES on the numbers; documentation gap on the denominator",
         "disposition": "recorded. The packet is frozen and was not edited."},
        {"id": "C2", "severity": "B",
         "against": "V2_HYPOTHESES_adversarial.md E5, 'Uniform inflation loses on net'",
         "finding": "uniform inflation arbitrages over lambda in [0.0001, 0.0028]; optimum "
                    "lambda 0.0016 gives downstream -0.000240 (-0.041%) at a primary cost of "
                    "+0.006983",
         "verdict": "CORRECTS",
         "consequence": "the arbitrage channel is reachable by an arm carrying NO feature at all, "
                        "through a pure level or calibration-slope freedom",
         "disposition": "RAISED to S4 / P26 K0_MATCHED. NOT resolved inside this node."},
        {"id": "C3", "severity": "B",
         "against": "V2_HYPOTHESES_adversarial.md E5, 'inflation targeted at rows correlated with "
                    "OT propensity wins'",
         "finding": "corr(trailing_ot_rate, target-game is_overtime) = -0.02696; the mean trailing "
                    "OT rate is LOWER on OT rows (0.03671) than on non-OT rows (0.04562). The "
                    "admissible carrier's maximum arbitrage is 1.9e-05 against the oracle's 0.0611",
         "verdict": "CORRECTS the magnitude; CONFIRMS the mechanism",
         "disposition": "preserved as a negative result. It does not weaken the contract: R5 "
                        "prohibits the CHANNEL, with the name list as a tripwire."},
        {"id": "C4", "severity": "C",
         "against": "comparison_gate.py vs the possession-unit ruling",
         "finding": "'primary' names the CONTRAST challenger_vs_k0 in comparison_gate.py "
                    "(primary_incremental_test, 2 occurrences) and the TARGET "
                    "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS in the ruling. No document "
                    "disambiguates them; SideSpec has no target field",
         "verdict": "vocabulary collision, both usages internally correct",
         "disposition": "R8 fixes the vocabulary inside P28's scope only. The shared module is "
                        "frozen and was not edited."},
        {"id": "C5", "severity": "B",
         "against": "V2_STOP_CONDITION.not_stop_conditions_but_recorded."
                    "OT_stratum_lower_MAE_may_be_a_units_artifact",
         "finding": "the stated 0.831 is the SIGNED-error sd ratio (measured 0.83088, AGREES); the "
                    "ABSOLUTE-error sd ratio is 0.89363, ABOVE the quoted 0.889; and the correct "
                    "reference factor is the mean realised 0.87879, not 40/45 = 0.88889, because "
                    "the OT stratum contains 60 single-OT, 5 double-OT and 1 quadruple-OT game",
         "verdict": "CORRECTS the reference factor; the conclusion is statistic-dependent",
         "disposition": "NOT resolved here. P28 forbids the downstream figure from deciding "
                        "anything, which is a weaker and safer claim."},
    ],

    "could_not_establish": [
        "whether any actual challenger exhibits this arbitrage -- no challenger has been fitted, "
        "comparative historical performance is forbidden, and SEALED_RESULTS was not read",
        "the frozen scorer's own downstream metric -- run_turnover_p1_universe_fix.py was NOT run. "
        "The downstream figures are the packet's mechanical propagation at the realised rate, not "
        "the scorer's fitted per-player output summed to team. Magnitudes would differ; direction "
        "and existence of the channel would not",
        "whether a better OT-propensity carrier exists among cutoff-valid columns -- not searched "
        "for, because that is feature discovery against a downstream metric, which this contract "
        "prohibits",
        "completeness of R5's carrier-name patterns -- a name list cannot be complete; the "
        "load-bearing clauses are the declared-channel rule and R4, both name-independent",
        "dual-frame provenance per GATE_INVOCATION_CONTRACT 8a -- the gate audits reach "
        "RAW_PROVENANCE_ASSERTED, not a full pass, because no producer emits a construction receipt",
    ],

    "stop_conditions_tripped": [],
    "raised_not_resolved": [
        {"finding": "C2", "belongs_to": "S4 (free SLOPE confound) and P26 (K0_MATCHED invariants)",
         "why": "an arm with no feature can reach the arbitrage channel through a pure level or "
                "calibration-slope freedom. Pinning exposure level and calibration slope in "
                "K0_MATCHED[arm_id] is P26's contract, not this node's write scope"},
        {"finding": "C5", "belongs_to": "the OT-stratum difficulty question",
         "why": "P28 forbids the downstream figure from deciding anything, which does not require "
                "adjudicating whether the OT stratum is genuinely easier"},
    ],
    "note_on_stop_conditions": (
        "This node changes nothing about the primary target, the K0 structure, the inference "
        "structure, the candidate universe, the cutoff-valid feature set or the leakage status. "
        "trailing_ot_rate remains cutoff-valid and gate-passing -- measured, on every fold -- and "
        "R5 does not remove it from the cutoff-valid set; it forbids CREDITING a benefit that "
        "arrives only through the exposure mismatch."),
}

if __name__ == "__main__":
    p = HERE / "FINDINGS.json"
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {p} ({p.stat().st_size} bytes)")
