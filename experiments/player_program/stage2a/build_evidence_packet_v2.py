#!/usr/bin/env python3
"""build_evidence_packet_v2.py — corrected Stage 2A evidence packet.

Composes EVIDENCE_PACKET_V2 from:
  * the VALID contents of the original packet (immutable, hash preserved);
  * the immutable correction addendum;
  * the coordinator's possession-unit ruling;
  * the accepted game-cluster inference specification;
  * the K0_FLAT / K0_MATCHED control ruling;
  * explicit documentation of the operational exposure-target mismatch.

The original packet is READ and REFERENCED. It is never modified.
Read-only over artifacts. Nothing fitted, nothing scored.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIG = HERE / "EVIDENCE_PACKET.json"
ADD = HERE / "CORRECTION_ADDENDUM.json"
OUT = HERE / "EVIDENCE_PACKET_V2.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    o = json.loads(ORIG.read_text(encoding="utf-8"))
    a = json.loads(ADD.read_text(encoding="utf-8"))
    c = a["corrections"]

    v2 = {
        "schema": "stage2a_evidence_packet/2",
        "task": "TEAM_POSSESSION_PRIOR_V2 Stage 2A (corrected)",
        "lane": "DIAGNOSTIC ONLY — nothing fitted, selected, tuned or scored",
        "supersedes": {
            "file": "EVIDENCE_PACKET.json", "sha256": sha(ORIG),
            "status": "IMMUTABLE AND PRESERVED — v1 is not modified, deleted or corrected in "
                      "place. Its hash is unchanged. V2 composes v1's VALID contents with the "
                      "correction addendum and the coordinator rulings."},
        "correction_addendum": {"file": "CORRECTION_ADDENDUM.json", "sha256": sha(ADD)},

        # ------------------------------------------------------------------ RULING 1
        "possession_unit_ruling": {
            "authoritative_target": "REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS",
            "ruled_by": "coordinator",
            "basis": "the experiment's COMPONENT BOUNDARY, not observed performance",
            "reasoning": [
                "Stage 2 improves the existing regulation-equivalent possession-prior component",
                "raw full-game possessions combine regulation pace with REALISED overtime",
                "realised overtime and game duration are unavailable pregame and are PROHIBITED "
                "as predictive inputs",
                "an expected-raw-possession target would require a separate preregistered "
                "overtime-probability component, which is OUTSIDE this wave",
            ],
            "use_the_frozen_canonical_target": True,
            "do_not_regenerate_canonical_artifact": True,
            "permitted_use_of_realised_duration": (
                "historical realised duration MAY be used solely to construct or normalise the "
                "COMPLETED-GAME regulation-equivalent outcome — which is what build_pace already "
                "does over strictly earlier games"),
            "prohibited_use_of_realised_duration": (
                "it may NOT enter the fitted feature matrix, fallback logic, arm selection, or "
                "the prediction path. game_minutes is an exact overtime indicator; any function "
                "of it used predictively is target leakage"),
        },

        # ------------------------------------------------------------------ RULING 2
        "downstream_operational_boundary": {
            "frozen_scorer_unchanged": True,
            "recorded_pairing": {
                "exposure": "regulation-equivalent projected possessions",
                "outcome": "RAW full-game turnovers",
                "consumer": "run_turnover_p1_universe_fix.py:149, operational track",
                "status": "A KNOWN, DOCUMENTED MISMATCH on overtime games"},
            "measured_mismatch": c["C5_unit_diagnostics"]["diagnostics_under_both_units"],
            "what_stage2_may_claim": (
                "Stage 2 MAY evaluate whether an improved regulation-equivalent exposure improves "
                "RAW turnover MAE through the FROZEN downstream scorer."),
            "what_stage2_may_NOT_claim": (
                "it may NOT claim to resolve the overtime mismatch. OT and non-OT downstream "
                "diagnostics are SECONDARY and cannot overturn the primary registered decision."),
            "reporting_requirement": "report OT and non-OT downstream diagnostics separately",
        },

        # ------------------------------------------------------------------ RULING 3
        "inference_specification": {
            "team_game_rows": 2982,
            "game_clusters": 1491,
            "do_not_substitute": ("do NOT replace the row count with 'effective n = 1491'. "
                                  "Report BOTH the row count and the dependence structure."),
            "dependence_structure": c["C11_effective_sample_size"]["measurement"],
            "row_weighting": "equal per team-game row, unless the task card PROSPECTIVELY "
                             "specifies otherwise",
            "fold_construction": "chronological, nested by season; a game is NEVER split across "
                                 "folds — both team-rows always fall in the same fold",
            "resampling": "game-clustered: resample the 1,491 game clusters with replacement, "
                          "carrying BOTH team-rows of a sampled game together; never resample "
                          "team-rows independently",
            "shared_across_arms": "identical rows, weights, folds AND target units for K0_FLAT, "
                                  "K0_MATCHED, the frozen incumbent and every challenger",
        },

        # ------------------------------------------------------------------ RULING 4
        "control_specification": {
            "K0_FLAT": {
                "definition": "intercept-only",
                "role": "DIAGNOSTIC REFERENCE",
                "promotion_value": "NONE — beating K0_FLAT alone has no promotion value"},
            "K0_MATCHED": {
                "definition": "identical pipeline, folds, offsets, fallback tiers, switching "
                              "rules and allowed estimation flexibility as the challenger",
                "excludes": ["basketball", "opponent", "schedule", "roster", "injury", "travel",
                             "venue", "coaching", "any contextual predictor"],
                "role": "AUTHORITATIVE PROMOTION CONTROL",
                "tier_partition_rule": "a tier or fallback partition may appear in K0_MATCHED "
                                       "ONLY when it reproduces architecture already present in "
                                       "the incumbent or challenger comparison path",
                "label": "MATCHED STRUCTURAL CONTROL — not a literally featureless model",
                "why_this_is_not_feature_absorption": (
                    "pace_level > 1 is algebraically identical to game_no_in_season <= 3 "
                    "(2982/2982, zero off-diagonal), so a tier indicator encodes ONLY the "
                    "incumbent's own switching rule and carries no information the incumbent "
                    "lacks. The risk runs the other way: if K0 OMITS the tier structure, an "
                    "intercept-plus-tier-dummy challenger beats a straw control by removing "
                    "stratum bias with no substantive features at all")},
            "decision_rule": "a challenger must beat K0_MATCHED",
        },

        # ------------------------------------------------------------------ CARRIED FORWARD
        "sources": o["sources"],
        "incumbent": o["incumbent"],
        "coverage": o["coverage"],
        "chronological_possession_error": o["chronological_possession_error"],
        "bias_variance": o["bias_variance"],
        "downstream_turnover_team_error": o["downstream_turnover_team_error"],

        "error_strata_CORRECTED": {
            "note": "strata the correction addendum found defective are REPLACED here; the rest "
                    "are carried forward unchanged from v1",
            "carried_forward_unchanged": {
                "by_pace_level": o["error_strata"]["by_pace_level"],
                "by_season_type": o["error_strata"]["by_season_type"],
                "by_overtime": o["error_strata"]["by_overtime"]},
            "REPLACED_days_rest": {
                "v1_status": "WITHDRAWN — computed across season boundaries",
                "v1_defect": c["C1_days_rest"]["measured_defect"],
                "corrected_within_season": c["C1_days_rest"]["recomputed_within_season"],
                "season_openers_separated": c["C1_days_rest"]["season_openers_reported_separately"]},
            "REPLACED_support": {
                "v1_status": "WITHDRAWN — built on a column with two meanings",
                "source_column_semantics": c["C2_support_axis"]["source_column_semantics"],
                "corrected_team_support_only": c["C2_support_axis"]["recomputed_TEAM_support_only"],
                "zero_team_support_rows": c["C2_support_axis"]["zero_team_support_rows"]},
            "WITHDRAWN_game_no_in_season": {
                "reason": "algebraically identical to pace_level > 1 (2982/2982). Reporting both "
                          "was double-counting ONE partition",
                "evidence": c["C3_pace_level_equals_early_season"]},
        },

        "overtime_window_contamination": c["C4_ot_window_contamination"],

        "cutoff_valid_availability_table_CORRECTED": {
            "rule": o["cutoff_valid_availability_table"]["rule"],
            "warning": o["cutoff_valid_availability_table"]["warning"],
            "available": o["cutoff_valid_availability_table"]["available"],
            "CORRECTED_now_available": [
                {"field": "venue, travel distance, elevation, time zone",
                 "source": "data/reference/team_cities.csv (16 rows: team_id, franchise, "
                           "first_season, last_season, city, arena, lat, lon, elevation_ft)",
                 "v1_verdict": "ABSENT — WITHDRAWN, this was a coordinator error",
                 "v2_verdict": "AVAILABLE — Category A", "cutoff_valid": True,
                 "basis": "static reference; venue is schedule-determined and known pregame"}],
            "CORRECTED_availability_yes_cutoff_unproven": [
                {"field": "injury / transaction history",
                 "source": "data/injury_history/injury_history.csv (8,340 rows, "
                           "2021-01-07 .. 2026-07-29, full contract span)",
                 "v1_verdict": "UNAVAILABLE HISTORICALLY — WITHDRAWN, coordinator error",
                 "v2_verdict": "AVAILABILITY ESTABLISHED; CUTOFF VALIDITY NOT ESTABLISHED",
                 "reason": "no observation timestamp; cutoff status rests on `date` being an "
                           "event date rather than a compilation date",
                 "category": "B — on cutoff grounds, NOT availability grounds"}],
            "unavailable_or_insufficient": o["cutoff_valid_availability_table"][
                "unavailable_or_insufficient"],
            "capture_provenance_caution": c["C9_retrospective_bulk_scrape"],
        },

        "unavailable_but_potentially_valuable": o["unavailable_but_potentially_valuable"],

        "UNRESOLVED_do_not_force": {
            "head_to_head_coverage": {
                "status": "UNRESOLVED — preserve as unresolved unless independently reproduced",
                "detail": c["C6_head_to_head_coverage"],
                "instruction": "do NOT force reconciliation. No head-to-head coverage figure may "
                               "be quoted in a task card until independently reproduced."},
            "game_no_in_season_defect_claim": c["C10_game_no_in_season"],
        },

        "statement_classification": a["original_statement_classification"],
    }
    OUT.write_text(json.dumps(v2, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"wrote {OUT.name}")
    print(f"  sha256   : {sha(OUT)}")
    print(f"  v1 packet: {sha(ORIG)}  (UNCHANGED)")
    print(f"  addendum : {sha(ADD)}")
    print(f"  unit     : {v2['possession_unit_ruling']['authoritative_target']}")
    print(f"  sections : {len(v2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
