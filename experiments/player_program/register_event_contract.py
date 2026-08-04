#!/usr/bin/env python3
"""register_event_contract.py — freeze `canonical_player_events_v1` BEFORE it is built.

Every frozen field below is grounded in the source inventory
(`event_contract_v1/EVENT_SOURCE_INVENTORY.json`), which was run FIRST precisely so the
registration states the real boundary, the real keys and the real taxonomy rather than assumed
ones. Several assumptions I had been carrying were wrong and are corrected here.

**Nothing is fitted and nothing is scored.** This registration authorises normalisation and
validation only. No event model may be fitted and no opportunity denominator may be selected.

Run::

    python experiments/player_program/register_event_contract.py
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
ARM_REGISTRY = HERE / "arm_registry.jsonl"
SCHEMA = "player_program_arm_registry/1"
EXP = "canonical_player_events_v1"
INVENTORY = "experiments/player_program/event_contract_v1/EVENT_SOURCE_INVENTORY.json"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(rel: str) -> str | None:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()


RECORD = {
    "schema": SCHEMA,
    "kind": "arm",
    "experiment_id": EXP,
    "arm_id": "canonical_player_events/1",
    "registered_at": _utc(),
    "registered_before_execution": True,
    "registered_at_commit": _head(),
    "extra": {
        "purpose": (
            "normalise the two play-by-play stores into ONE stable event contract across the full "
            "1,495-game historical universe. The blocker is canonical event NORMALISATION, not "
            "event acquisition."),
        "authorises": ["the event contract", "the normalising producer", "its validation"],
        "does_not_authorise": [
            "fitting any rebound, assist, turnover, steal, block, foul, free-throw or shot model",
            "selecting opportunity denominators", "modifying player_possessions/2",
            "repairing the rate-model sensitivity arm", "touching gate_receipt.py",
            "changing the team incumbent", "beginning simulation",
            "using event outputs in the team forecast",
        ],
        "grounding_receipt": {"path": INVENTORY, "sha256": _sha(INVENTORY)},

        # ---------------------------------------------------------------- 1 sources
        "sources_and_precedence": {
            "legacy": {"id": "nba_playbyplayv2", "path": "data/playbyplay/pbp_<game_id>.parquet",
                       "games_in_universe": 996, "event_rows": 383377},
            "cdn": {"id": "nba_cdn_playbyplay", "path": "data/refresh_2026/pbp/pbp_<game_id>.parquet",
                    "games_in_universe": 499, "event_rows": 205753},
            "precedence": (
                "NOT EXERCISED. The two stores are exactly disjoint -- 0 games appear in both -- so "
                "no game requires a precedence decision. A rule is registered only as a guard: if a "
                "future refresh ever places a game in both stores, the CDN row wins (richer schema) "
                "AND the collision is reported as a DEGRADED state. It is never resolved silently."),
            "collision_policy": "fail closed on any game present in both stores",
        },

        # ---------------------------------------------------------------- 2 universe
        "universe": {
            "definition": "the 1,495 distinct game_ids of prediction_contract_v5",
            "source": "experiments/prediction_contract_v5/player_game_enriched.parquet",
            "games": 1495,
            "reconciliation_verified": "996 + 499 + 0 both + 0 neither = 1495",
            "files_outside_the_universe": "excluded and counted; never silently dropped",
        },

        # ---------------------------------------------------------------- 3 boundary
        "schema_change_boundary": {
            "shape": "TWO-DIMENSIONAL, not a single changeover date",
            "dimension_1_season_type": (
                "EVERY playoff game in 2021-2025 comes from the CDN store, regardless of season: "
                "17 (2021), 23 (2022), 20 (2023), 22 (2024), 24 (2025) = 106 games. They were "
                "backfilled from the CDN source."),
            "dimension_2_date_within_2025_regular_season": (
                "legacy through 2025-06-29 (108 games); CDN from 2025-07-03 (178 games). Verified "
                "clean: zero legacy games on or after the CDN first date, zero CDN games on or "
                "before the legacy last date."),
            "2026": "entirely CDN (215 games)",
            "correction_of_a_prior_claim": (
                "an earlier summary described this as 'a hard mid-2025 changeover' with legacy "
                "covering 2021 to mid-2025. That is WRONG. The CDN span begins 2021-09-23 because "
                "of the playoff backfill. A global first/last-date test is misleading and must not "
                "be used; the boundary is only clean when tested STRATIFIED by season and "
                "season_type."),
        },

        # ---------------------------------------------------------------- 4 key
        "canonical_event_key": {
            "rule": "event_uid = sha1(game_id | source_system | source_event_id)[:16]",
            "source_event_id": {
                "legacy": "EVENTNUM — verified unique within every sampled game file",
                "cdn": "actionId — verified unique in 60 of 60 sampled files",
            },
            "explicitly_rejected": {
                "cdn.actionNumber": (
                    "NOT unique. It repeats within a game in 60 of 60 sampled files (e.g. "
                    "actionNumber 102 carries actionId 73 and 74). Using it as the key would "
                    "silently collide."),
                "file_row_number": (
                    "rejected outright — the canonical identity must not depend only on row "
                    "position within a file"),
            },
            "fallback": (
                "if a file's source event id is absent or non-unique, fall back to "
                "(period, clock_seconds_remaining, file_row_index), set key_fallback_used = True "
                "and quality = 'degraded'. Reported per game; never silent."),
            "canonical_event_seq": "dense integer per game under the registered ordering rule",
        },

        # ---------------------------------------------------------------- 5 ordering
        "event_ordering_rule": {
            "sort": "(period ASC, elapsed_seconds ASC, source_event_id ASC)",
            "tie_break": "source_event_id only",
            "prohibition": (
                "simultaneous events are NOT reordered to make later possession or lineup "
                "reconstruction easier. The source's own sequence is the tie-break, because it is "
                "the only ordering the source actually asserts."),
        },

        # ---------------------------------------------------------------- 6 clock
        "period_and_clock_normalisation": {
            "legacy_clock": "PCTIMESTRING, 'MM:SS' counting DOWN within the period",
            "cdn_clock": "clock, ISO-8601 duration 'PT10M00.00S' counting DOWN within the period",
            "canonical": {
                "period": "integer as supplied",
                "clock_seconds_remaining": "float seconds remaining in the period",
                "elapsed_seconds": (
                    "cumulative seconds from tip: "
                    "600*(period-1) for period <= 4; 2400 + 300*(period-5) for period >= 5; "
                    "plus (period_length - clock_seconds_remaining), where period_length is 600 "
                    "for periods 1-4 and 300 for overtime"),
            },
            "wnba_period_lengths": {"regulation_quarter_seconds": 600, "overtime_seconds": 300},
            "unparsable_clock": "clock_unparsed = True, value NULL, quality 'degraded'",
        },

        # ---------------------------------------------------------------- 7 identity
        "identity_resolution": {
            "players": ("legacy PLAYER1_ID / PLAYER2_ID / PLAYER3_ID; CDN personId. Resolved "
                        "against data/masters/master_player.parquet."),
            "teams": ("legacy PLAYER*_TEAM_ID; CDN teamId and teamTricode. Resolved against "
                      "data/masters/master_team.parquet on (game_id, team_abbreviation)."),
            "zero_or_null_ids": "canonical NULL, never 0",
            "unresolvable": ("identity_unresolved = True, value NULL, row RETAINED. An identity is "
                             "never invented and a row is never dropped for it."),
        },

        # ---------------------------------------------------------------- 8 taxonomy
        "event_taxonomy": {
            "families": [
                "made_field_goal", "missed_field_goal", "free_throw", "rebound", "turnover",
                "foul", "violation", "substitution", "jump_ball", "timeout", "period_start",
                "period_end", "ejection", "replay_or_administrative",
                "steal", "block", "unknown",
            ],
            "steal_and_block_asymmetry": {
                "correction_of_my_own_draft": (
                    "an earlier draft of this registration asserted that steals, assists and blocks "
                    "are attributions on other events in BOTH schemas. That is WRONG for the CDN "
                    "store and the inventory caught it before execution."),
                "legacy": (
                    "ATTRIBUTIONS. A steal is PLAYER2 on the turnover row (PLAYER1 commits it); a "
                    "block is PLAYER3 on the missed-shot row; an assist is PLAYER2 on the "
                    "made-shot row. Verified: 'Robinson Bad Pass Turnover' with PLAYER2 "
                    "'Kylee Shook' and description 'Shook STEAL (1 STL)'."),
                "cdn": (
                    "STANDALONE ROWS carrying an EMPTY actionType, e.g. 'Nye STEAL (1 STL)' and "
                    "'Timpson BLOCK (1 BLK)' -- 533 such rows in a 25-game sample. The turnover row "
                    "itself does not name the stealer. CDN assists appear only inside made-shot "
                    "description text, e.g. '(Mitchell 1 AST)'."),
                "canonical_treatment": (
                    "BOTH representations are preserved as they are. CDN standalone steal and block "
                    "rows become families 'steal' and 'block'. Legacy attributions populate the "
                    "columns steal_player_id / block_player_id / assist_player_id. Neither form is "
                    "converted into the other in v1, because linking a CDN steal row to its "
                    "turnover row is a DERIVED adjacency inference, not an observation."),
                "consequence_recorded": (
                    "steal, block and assist counts are therefore NOT directly comparable across "
                    "the two stores in v1. Any channel using them must either restrict to one "
                    "store or register an explicit linkage rule first. This is a real limitation, "
                    "not a defect to paper over."),
            },
            "rebound_typing": {
                "finding": (
                    "NEITHER schema supplies offensive-versus-defensive rebound type as a "
                    "structural field. Legacy uses EVENTMSGACTIONTYPE 0 for 80,005 of its rebound "
                    "rows; CDN uses subType 'Unknown' for 1,988 of 2,081 sampled rebound rows. In "
                    "both, the distinction survives only inside description text as running "
                    "counters, e.g. 'Young REBOUND (Off:0 Def:1)'."),
                "canonical_rule": (
                    "rebound_type = 'team' where the source structurally identifies a team rebound "
                    "(no player identity / team id in the person field, e.g. 'Aces Rebound'); "
                    "otherwise 'unresolved'. v1 does NOT parse the Off:/Def: counters and does NOT "
                    "infer type from possession context."),
                "why": (
                    "offensive-versus-defensive typing is a DERIVATION, not an observation. "
                    "Deciding it here would pre-decide the rebound channel's denominator, which "
                    "this registration explicitly forbids."),
            },
            "raw_values_to_cover": {"legacy_pairs": 165, "cdn_pairs": 162,
                                    "source": "the inventory receipt"},
            "unmapped_policy": (
                "an unmapped raw value is labelled event_family='unknown', taxonomy_unmapped=True, "
                "and REPORTED with its raw value and count. It is NEVER collapsed silently into "
                "'other'."),
            "subtype_preservation": (
                "source_subtype_raw is preserved alongside the canonical event_subtype on every "
                "row, so no source distinction is lost"),
        },

        # ---------------------------------------------------------------- 9/10/11
        "source_specific_mappings": {
            "document": "experiments/player_program/event_contract_v1/EVENT_CROSSWALK.md",
            "machine_readable": "experiments/player_program/event_contract_v1/event_crosswalk.json",
            "rule": "frozen before execution; NOT altered after viewing any downstream accuracy",
        },
        "duplicate_policy": {
            "duplicate_source_key_within_a_file": (
                "all rows RETAINED, duplicate_source_key = True, quality 'degraded', counts "
                "reported. Never deduplicated silently."),
            "duplicate_game_files": "the partition test asserts zero; a collision fails closed",
        },
        "amended_event_policy": {
            "v1_behaviour": (
                "amendments, corrections and replay events are PRESERVED as their own rows under "
                "family 'replay_or_administrative'. v1 does NOT retro-apply a correction to an "
                "earlier row and does not delete a superseded row."),
            "why": ("resolving amendments requires semantics the sources do not state uniformly. "
                    "Preserving them keeps the artifact faithful and auditable; resolution can be "
                    "a later registered revision."),
        },

        # ---------------------------------------------------------------- 12 subs
        "substitution_handling": {
            "legacy": ("EVENTMSGTYPE 8. Verified encoding: PLAYER1 is the player going OUT and "
                       "PLAYER2 the player coming IN (description reads 'SUB: {IN} FOR {OUT}'). "
                       "Both sides are structurally observed."),
            "cdn": ("actionType 'Substitution'. subType is an EMPTY string and personId identifies "
                    "ONLY the player going OUT. The incoming player appears solely in free-text "
                    "description."),
            "canonical": {
                "sub_player_out_id": "observed in both sources",
                "sub_player_in_id": (
                    "observed for legacy; CANONICAL NULL for CDN, with "
                    "substitution_in_supported = False"),
            },
            "prohibition": (
                "v1 does NOT parse the incoming player out of CDN description text. A canonical "
                "null is preferable to an inferred value presented as observed. Text parsing may "
                "be a later registered enrichment with field_origin='parsed'."),
            "fidelity_note": (
                "this is a real information asymmetry between the schemas and is recorded rather "
                "than papered over"),
        },

        # ---------------------------------------------------------------- 13 possession
        "possession_linking_policy": {
            "v1_links_nothing": True,
            "player_possessions_2_remains_canonical": True,
            "what_v1_provides": ("period and elapsed_seconds on every row, which is what a FUTURE "
                                 "registered linker would need"),
            "prohibition": ("v1 asserts no possession membership and does not rebuild or supersede "
                            "the possession pipeline. Structural comparison only, after validation."),
        },

        # ---------------------------------------------------------------- 14 coords
        "coordinate_normalisation": {
            "legacy": "supplies NO coordinates. coordinates_supported = False on every legacy row.",
            "cdn": "xLegacy / yLegacy / shotDistance",
            "critical_finding": (
                "xLegacy and yLegacy are populated on EVERY CDN row, including non-shot events, "
                "where the value is (0,0). In a 40-game sample, 0 of 5,447 field-goal rows sit at "
                "(0,0) while every sampled non-shot row does. (0,0) is therefore a NULL SENTINEL, "
                "not an observed location at the basket."),
            "rule": (
                "coordinates are canonical-observed ONLY where isFieldGoal == 1. On every other "
                "row they are canonical NULL. A (0,0) on a field-goal row is retained as observed."),
            "coordinate_system": "nba_legacy_xy, origin at basket centre, tenths of feet",
            "no_reorientation": "v1 does not flip or re-origin coordinates",
            "no_shotchart_backfill": (
                "v1 does NOT backfill legacy coordinates from data/shotcharts/. That is a join to a "
                "different artifact with its own provenance, and it would break the one-raw-source-"
                "per-row traceability rule. Registered as a possible later enrichment."),
        },

        # ---------------------------------------------------------------- 15 provenance
        "provenance_fields": [
            "source_system", "source_file", "source_file_sha256", "source_event_id",
            "source_row_index", "mapping_rule_id", "parser_version", "contract_version",
            "field_origin per key field: observed | parsed | derived | unresolved",
        ],
        "producer_fails_closed_if": [
            "a required source column is missing",
            "a mapping rule is missing for a raw value that the crosswalk claims to cover",
            "a game appears in both stores",
            "the universe reconciliation does not close",
        ],

        # ---------------------------------------------------------------- 16 states
        "quality_states": {
            "quality": ["ok", "degraded", "unresolved"],
            "flags": ["key_fallback_used", "duplicate_source_key", "identity_unresolved",
                      "taxonomy_unmapped", "clock_unparsed", "coordinates_supported",
                      "substitution_in_supported"],
        },

        # ---------------------------------------------------------------- 17 gates
        "validation_gates": [
            "all 1,495 universe games accounted for",
            "source-store overlap and exclusivity reconcile",
            "canonical keys unique",
            "deterministic byte-identical rebuilds",
            "event counts reconcile to the raw sources after documented exclusions",
            "period and clock ranges valid",
            "score progression internally coherent where score data exists",
            "made shots and free throws reconcile with scoring totals where supported",
            "substitutions have valid in/out identities where the source supplies them",
            "no impossible player-team mappings introduced",
            "event subtype mappings cover all raw values or label them unresolved",
            "coordinate ranges and orientation rules valid",
            "postseason and overtime games included",
            "parser failures produce no partial artifact",
            "no target-game information from outside the event file introduced",
            "no future roster, transaction or availability data used to reinterpret events",
        ],
        "stratified_manual_audit": [
            "early 2021 legacy games", "late legacy games immediately before the changeover",
            "first CDN games after the changeover", "2026 games", "playoff games",
            "overtime games", "high-substitution games", "games missing shot coordinates",
            "games containing technical fouls, reviews or unusual administrative events",
        ],

        # ---------------------------------------------------------------- 18 boundary
        "opportunity_denominator_boundary": {
            "directly_observed": [
                "shot attempts, makes and misses", "free-throw attempts",
                "rebound events (as events)", "turnovers and their subtype",
                "fouls and their subtype", "the player leaving the floor on a substitution",
                "legacy steal/assist/block attributions",
                "CDN standalone steal and block rows",
            ],
            "deterministically_derivable": [
                "elapsed time", "period structure",
                "score progression where score fields exist",
                "team rebound versus player rebound",
            ],
            "heuristically_reconstructed_and_NOT_done_in_v1": [
                "CDN incoming substitute (description text only)",
                "offensive versus defensive rebound type (description counters or possession context)",
                "CDN assist attribution (description text only)",
                "linking a CDN standalone steal/block row to the event it belongs to (adjacency)",
            ],
            "NOT_currently_supportable": [
                "potential assists", "rebound chances in the tracking-data sense", "touches",
                "drives", "defender proximity", "blockable attempts", "substitution intentions",
            ],
            "rule": ("the contract must SUPPORT later construction of defensible denominators "
                     "without pre-deciding or fabricating them"),
        },
        "stop_boundary": (
            "stop after the canonical event artifact validates. Then RECOMMEND a first granular "
            "event target and its proposed opportunity denominator, and WAIT for authorisation "
            "before registering or fitting it."),
        "outputs": {
            "artifact": "experiments/player_program/event_contract_v1/canonical_player_events_v1.parquet",
            "inventory": INVENTORY,
            "crosswalk": "experiments/player_program/event_contract_v1/EVENT_CROSSWALK.md",
            "receipt": "experiments/player_program/event_contract_v1/EVENT_NORMALISATION_RECEIPT.json",
            "validation": "experiments/player_program/event_contract_v1/EVENT_VALIDATION.json",
            "limitations": "experiments/player_program/event_contract_v1/EVENT_LIMITATIONS.md",
        },
    },
}


def existing_ids() -> set[str]:
    if not ARM_REGISTRY.exists():
        return set()
    return {json.loads(l).get("experiment_id")
            for l in ARM_REGISTRY.read_text(encoding="utf-8").splitlines() if l.strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    have = existing_ids()
    if a.list:
        print(f"{'PRESENT' if EXP in have else 'ABSENT '}  {EXP}")
        return
    if EXP in have:
        print(f"skip (already registered): {EXP}")
        return
    with ARM_REGISTRY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(RECORD, sort_keys=False) + "\n")
    print(f"appended: {EXP}\nat commit {RECORD['registered_at_commit']}")


if __name__ == "__main__":
    main()
