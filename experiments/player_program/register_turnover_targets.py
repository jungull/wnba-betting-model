#!/usr/bin/env python3
"""register_turnover_targets.py — freeze the turnover P0 target contract BEFORE execution.

Registers `turnover_target_contract_v1` and the artifact `player_turnover_targets_v1`.

**Authorised through P0 target construction and validation ONLY. No model may be fitted.**

The mechanism crosswalk below was derived EMPIRICALLY from the canonical event artifact's own
description text (modal description per legacy action code), not guessed from convention.

Run::  python experiments/player_program/register_turnover_targets.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REG = HERE / "arm_registry.jsonl"
EXP = "turnover_target_contract_v1"
EVENTS = "experiments/player_program/event_contract_v1/canonical_player_events_v1.parquet"
POSS = "experiments/player_program/possessions_v2/possessions_raw_v2.parquet"
MP = "data/masters/master_player.parquet"


def _sha(rel: str) -> str | None:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


#: fine mechanism, keyed by canonical name -> (legacy raw codes, CDN subtypes)
MECHANISM_CROSSWALK = {
    "bad_pass": {"legacy": ["5/1"], "cdn": ["Bad Pass"], "group": "bad_pass"},
    "bad_pass_out_of_bounds": {"legacy": ["5/45"], "cdn": ["Out of Bounds - Bad Pass Turnover"],
                               "group": "bad_pass"},
    "lost_ball": {"legacy": ["5/2"], "cdn": ["Lost Ball"], "group": "lost_ball"},
    "lost_ball_out_of_bounds": {"legacy": ["5/40"], "cdn": ["Out of Bounds Lost Ball Turnover"],
                                "group": "lost_ball"},
    "offensive_foul": {"legacy": ["5/37"], "cdn": ["Offensive Foul Turnover"],
                       "group": "offensive_foul"},
    "offensive_goaltending": {"legacy": ["5/15"], "cdn": ["Offensive Goaltending"],
                              "group": "offensive_foul"},
    "traveling": {"legacy": ["5/4"], "cdn": ["Traveling"], "group": "travel_footwork"},
    "double_dribble": {"legacy": ["5/6"], "cdn": ["Double Dribble"], "group": "travel_footwork"},
    "discontinue_dribble": {"legacy": ["5/7"], "cdn": ["Discontinue Dribble"],
                            "group": "travel_footwork"},
    "palming": {"legacy": ["5/21"], "cdn": ["Palming Turnover"], "group": "travel_footwork"},
    "step_out_of_bounds": {"legacy": ["5/39"], "cdn": ["Step Out of Bounds Turnover"],
                           "group": "travel_footwork"},
    "shot_clock": {"legacy": ["5/11"], "cdn": ["Shot Clock Turnover"], "group": "shot_clock"},
    "three_second": {"legacy": ["5/8"], "cdn": ["3 Second Violation"], "group": "other_violation"},
    "five_second": {"legacy": ["5/9"], "cdn": ["5 Second Violation"], "group": "other_violation"},
    "eight_second": {"legacy": ["5/10"], "cdn": ["8 Second Violation"], "group": "other_violation"},
    "backcourt": {"legacy": ["5/13"], "cdn": ["Backcourt Turnover"], "group": "other_violation"},
    "inbound": {"legacy": ["5/12"], "cdn": ["Inbound Turnover"], "group": "other_violation"},
    "lane_violation": {"legacy": ["5/17"], "cdn": ["Lane Violation"], "group": "other_violation"},
    "jump_ball_violation": {"legacy": ["5/18"], "cdn": ["Jump Ball Violation"],
                            "group": "other_violation"},
    "kicked_ball": {"legacy": ["5/19"], "cdn": ["Kicked Ball Violation"], "group": "other_violation"},
    "excess_timeout": {"legacy": ["5/42"], "cdn": ["Excess Timeout Turnover"],
                       "group": "other_violation"},
    "unresolved": {"legacy": ["5/0"], "cdn": [""], "group": "unknown"},
}

RECORD = {
    "schema": "player_program_arm_registry/1",
    "kind": "arm",
    "experiment_id": EXP,
    "arm_id": "turnover_target_contract/1",
    "artifact_id": "player_turnover_targets/1",
    "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "registered_before_execution": True,
    "registered_at_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                           capture_output=True, text=True).stdout.strip(),
    "extra": {
        "authorised_scope": "P0 target construction and validation ONLY",
        "explicitly_not_authorised": [
            "fitting a pooled turnover model", "testing windows or decay rates",
            "constructing player-specific effects", "tuning mechanism groupings",
            "linking steals by event adjacency",
            "using actual target-game possession exposure in an operational forecast",
            "feeding turnover outputs into the team model", "beginning another event channel",
        ],
        "current_conclusion_wording": (
            "Turnover observations and possession exposure are available from validated canonical "
            "artifacts, making turnovers the strongest first candidate for target-contract "
            "development. The canonical EVENTS are validated; the derived player-game turnover "
            "labels, mechanism reconciliation and cross-schema equivalence are NOT yet validated."),
        "inputs": {
            "events": {"path": EVENTS, "sha256": _sha(EVENTS)},
            "possessions": {"path": POSS, "sha256": _sha(POSS)},
            "external_truth": {"path": MP, "sha256": _sha(MP), "column": "tov"},
        },
        "grain": {
            "player_artifact": ["game_id", "team_id", "player_id"],
            "team_artifact": ["game_id", "team_id"],
            "canonical_keys": "canonical game_id, team_id and player_id as in the masters",
        },
        "row_universe": {
            "rule": ("the player artifact contains ALL SCOREABLE player-game rows, including "
                     "ZERO-turnover games. It is not restricted to players who committed one."),
            "included": {
                "positive_realised_offensive_possessions": "INCLUDED, scoreable=True",
                "recorded_minutes_but_zero_reconstructed_possessions": (
                    "INCLUDED, scoreable=True, flagged zero_possession_exposure=True; the rate is "
                    "undefined and the count target is still valid"),
            },
            "excluded": {
                "candidates_who_did_not_appear": (
                    "EXCLUDED. An inactive candidate is NOT a zero-turnover observation. Counted "
                    "separately as not_scoreable_did_not_appear."),
                "unresolved_player_or_team_identity": "EXCLUDED and counted",
            },
            "players_changing_teams_within_a_season": (
                "one row per (game_id, team_id, player_id); a player who changes club has rows "
                "under each club for the games played there. The grain makes this unambiguous."),
        },
        "target_hierarchy": [
            "1. total player-attributed turnovers",
            "2. turnovers by normalised mechanism",
            "3. team or unattributed turnovers",
            "4. total team turnovers",
        ],
        "conservation_requirement": (
            "mechanism counts must sum EXACTLY to player-attributed turnover totals after "
            "explicitly documented exclusions or unresolved categories"),
        "mechanism_taxonomy": {
            "derivation": ("EMPIRICAL. Each legacy action code was mapped by its MODAL DESCRIPTION "
                           "text in the canonical event artifact, then matched to the CDN subtype "
                           "with the same meaning. Not guessed from convention."),
            "crosswalk": MECHANISM_CROSSWALK,
            "levels": ["mechanism (fine)", "mechanism_group (top level)"],
            "groups": ["bad_pass", "lost_ball", "travel_footwork", "offensive_foul", "shot_clock",
                       "other_violation", "unknown"],
            "preservation": ("source_subtype_raw and the source-specific subtype are preserved on "
                             "every event row and are carried into the audit table"),
            "no_forced_equivalence": (
                "legacy and CDN labels are grouped only where the empirical descriptions agree in "
                "meaning, not merely in wording. Legacy 5/0 ('Turnover Turnover', 26 rows) has NO "
                "CDN counterpart and maps to 'unresolved', never to a real mechanism."),
            "frozen": "the taxonomy is NOT revised after looking at model performance",
        },
        "steal_linkage_prohibited": (
            "turnovers are NOT classified as stolen, forced or unforced in v1. Linking adjacent "
            "CDN standalone steal rows is a separate derived inference requiring its own "
            "registration."),
        "denominator": {
            "v1_name": "offensive-possession exposure",
            "v1_source": "realised player offensive possessions from player_possessions/2",
            "explicitly_not": (
                "a complete turnover-opportunity denominator. It does not observe touches, passes, "
                "drives, possession usage or ball-handler responsibility."),
            "tiers": {
                "realised_offensive_possessions": (
                    "allowable for constructing historical rates and conditional diagnostic "
                    "evaluation ONLY"),
                "projected_offensive_possessions": (
                    "REQUIRED for operational pregame expected-turnover forecasts; supplied by "
                    "projected_player_possessions_v1"),
                "touches_passes_drives_possessions_used": "unavailable; future challenger denominators",
            },
            "hard_rule": ("actual target-game offensive possessions must NEVER be used as an "
                          "operational forecast input"),
        },
        "team_and_unattributed_turnovers": {
            "detection": "the person field carries a TEAM id rather than a player id",
            "treatment": "a SEPARATE target component; never assigned proportionally to players",
        },
        "scoreability_rules": {
            "team_turnover_without_a_player": "team component; not scoreable to any player",
            "team_id_in_a_player_field": "detected by membership in the master team-id set",
            "offensive_fouls": "scoreable, mechanism offensive_foul",
            "shot_clock_violation": "TEAM component unless the source attributes a player",
            "five_and_eight_second_violations": "as the source attributes them; mechanism preserved",
            "double_or_offsetting_turnovers": "each event keeps its own disposition; no merging",
            "period_boundary_sequences": "retained; the event artifact's flags are carried through",
            "events_without_a_valid_possession_link": (
                "retained; v1 asserts no possession linkage, so this does not affect the count"),
            "games_or_players_missing_from_player_possessions_2": (
                "count target retained, exposure NULL, flagged no_exposure=True"),
        },
        "cross_schema_equivalence_reporting": {
            "required_by_source": ["total turnover events", "player-attributed turnovers",
                                   "team or unattributed turnovers", "mechanism counts and shares",
                                   "missing-player rates", "unresolved-subtype rates",
                                   "turnover rate per team offensive possession",
                                   "turnover rate per player offensive possession",
                                   "distributions by season and season type"],
            "confounding_warning": (
                "ALL 2021-2025 playoff games are CDN and the regular season changes source during "
                "2025, so source and season type are PARTIALLY CONFOUNDED. A raw legacy-versus-CDN "
                "rate difference must NOT be interpreted as a basketball effect."),
            "source_as_feature": "PROHIBITED as a production predictive feature; diagnostics only",
        },
        "external_reconciliation": {
            "source": f"{MP} column 'tov' (and master_team 'tov')",
            "report_separately": ["exact matches", "differences of one", "larger disagreements",
                                  "missing comparison records",
                                  "differences caused by team turnovers",
                                  "differences caused by replay/correction/administrative rows",
                                  "differences caused by source attribution"],
            "prohibition": ("do NOT tune the parser solely to force agreement. Investigate and "
                            "preserve documented source truth where the external total is itself "
                            "ambiguous."),
            "downgrade_rule": ("if no trustworthy frozen comparison source exists, say so and "
                               "downgrade the validation claim rather than treating internal "
                               "arithmetic as external verification"),
        },
        "duplicate_and_correction_policy": [
            "no double counting of replay snapshots, amended events, repeated source identifiers, "
            "administrative corrections, paired descriptive and structural rows, technical or "
            "dead-ball sequences, or simultaneous events at the same clock",
            "only rows with event_family == 'turnover' are counted; replay_or_administrative rows "
            "are never counted as turnovers",
            "the canonical event key is already unique, so a repeated source identifier cannot "
            "double count",
        ],
        "conservation_checks": [
            "player mechanism counts sum to player-attributed turnovers",
            "player-attributed plus team/unattributed sum to total normalised team turnovers",
            "every turnover event has exactly one final target disposition",
            "no player turnover is assigned to both teams",
            "player identities are valid for the event team where attribution exists",
            "zero-turnover player-game rows are retained",
            "unresolved events remain visible and are not silently dropped",
        ],
        "future_evaluation_contract": {
            "intrinsic_rate_evaluation": (
                "ORACLE-EXPOSURE diagnostic using REALISED offensive possessions, to test whether "
                "a rate model contains genuine turnover signal conditional on known exposure"),
            "operational_evaluation": (
                "the primary production-relevant test, using CUTOFF-VALID PROJECTED offensive "
                "possessions from projected_player_possessions_v1"),
            "the_distinction_is_binding": (
                "a model may improve the intrinsic conditional rate and still fail operationally "
                "if projected exposure is poor. This is exactly what happened to P3 and the "
                "distinction is preserved throughout."),
            "frozen_metrics": [
                "player-game turnover count MAE", "player-game count RMSE", "bias",
                "Poisson or negative-binomial deviance / log score",
                "calibration by predicted-count bucket",
                "team-game aggregate turnover MAE and bias", "mechanism-level performance",
                "paired differences against simple baselines", "game-clustered uncertainty",
                "season and source diagnostics", "coverage and scoreability",
            ],
            "prohibition": "accuracy must NOT be used to select the target taxonomy or denominator",
        },
        "outputs": {
            "player": "experiments/player_program/turnover_targets_v1/player_turnover_targets_v1.parquet",
            "team": "experiments/player_program/turnover_targets_v1/team_turnover_reconciliation_v1.parquet",
            "receipt": "experiments/player_program/turnover_targets_v1/TURNOVER_TARGET_RECEIPT.json",
            "validation": "experiments/player_program/turnover_targets_v1/TURNOVER_VALIDATION.json",
            "discrepancy_audit": "experiments/player_program/turnover_targets_v1/TURNOVER_DISCREPANCY_AUDIT.json",
            "contract_doc": "experiments/player_program/turnover_targets_v1/TURNOVER_TARGET_CONTRACT.md",
        },
        "stop_boundary": ("stop after the target artifacts validate; then RECOMMEND the exact "
                          "registered P1 baseline wave and WAIT for authorisation"),
    },
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    have = {json.loads(l).get("experiment_id")
            for l in REG.read_text(encoding="utf-8").splitlines() if l.strip()}
    if a.list:
        print(f"{'PRESENT' if EXP in have else 'ABSENT '}  {EXP}")
        return
    if EXP in have:
        print(f"skip (already registered): {EXP}")
        return
    with REG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(RECORD, sort_keys=False) + "\n")
    print(f"appended: {EXP}\nat commit {RECORD['registered_at_commit']}")


if __name__ == "__main__":
    main()
