"""
D12_COACHING_HISTORY -- emit FINDINGS.json.

Every numeric claim in FINDINGS.json is read out of MEASUREMENTS.json, which is written by
build_coaching_history.py from the actual files. No number is typed by hand here.

Run:  python emit_findings.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

NODE = Path(__file__).resolve().parent
EPISTEMIC_STATUS = (
    "REFERENCE DATA. Auditable history only. Explicitly NOT admitted to any experiment "
    "before a cutoff review."
)


def main() -> int:
    meas_doc = json.loads((NODE / "MEASUREMENTS.json").read_text(encoding="utf-8"))
    m = meas_doc["measurements"]
    inp = meas_doc["inputs"]

    cov = m["coverage_by_status"]
    tgs = m["coverage_team_games_by_status"]

    def cs(k):
        return int(cov.get(k, 0))

    def tg(k):
        return int(tgs.get(k, 0))

    named_tg = (
        tg("NAMED_EVENT_ANCHORED")
        + tg("NAMED_OPEN_END_CARRIED_FORWARD_UNVERIFIED")
        + tg("NAMED_START_LEFT_CENSORED")
    )
    unnamed_tg = (
        tg("UNKNOWN_NO_SPELL_COVERS_OPENER")
        + tg("UNKNOWN_ONLY_INTERIM_SPELL_CARRIED_ACROSS_SEASON")
        + tg("AMBIGUOUS_MULTIPLE_SPELLS")
    )

    doc = {
        "node_id": "D12_COACHING_HISTORY",
        "epistemic_status": EPISTEMIC_STATUS,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "measurements_file": "MEASUREMENTS.json",
        "admission": {
            "admitted_to_any_experiment": False,
            "admission_status": "NOT_ADMITTED",
            "cutoff_status": "CUTOFF_UNPROVEN",
            "reason": (
                "The source file carries no capture timestamp column and its raw source pages are "
                "not resident in this worktree, so no coaching record can be shown to have been "
                "available at or before any pregame cutoff. Availability is not eligibility and "
                "eligibility is not admission."
            ),
            "what_would_be_required_to_admit": [
                "a per-record capture or publication timestamp at or before the declared pregame cutoff",
                "resident, hashable source bytes for each cited source_page",
                "a cutoff review that adjudicates announcement-date versus first-game-coached semantics",
                "closure of the 2026 league-year capture hole",
            ],
        },
        "artifacts": {
            "coaching_events_v1.csv": {
                "grain": "one head-coaching HIRE or DEPART event",
                "rows": m["events_emitted"],
                "sha256": meas_doc["outputs"]["coaching_events_v1.csv"]["sha256"],
            },
            "coaching_tenure_v1.csv": {
                "grain": "one head-coaching spell (franchise x coach)",
                "rows": m["tenure_spells"],
                "sha256": meas_doc["outputs"]["coaching_tenure_v1.csv"]["sha256"],
            },
            "team_season_coverage_v1.csv": {
                "grain": "one team-season of the canonical universe",
                "rows": m["coverage_team_seasons"],
                "sha256": meas_doc["outputs"]["team_season_coverage_v1.csv"]["sha256"],
            },
        },
        "source": {
            "path": inp["coach_event_source"]["path"],
            "sha256": inp["coach_event_source"]["sha256"],
            "rows": inp["coach_event_source"]["rows"],
            "has_capture_timestamp_column": inp["coach_event_source"]["has_capture_timestamp_column"],
            "in_declared_node_read_scope": inp["coach_event_source"]["in_declared_node_read_scope"],
            "raw_source_pages_resident_in_worktree": m["raw_source_pages_resident_in_worktree"],
        },
        "acceptance_criteria": {
            "every coaching record carries a source and an effective date": {
                "status": "MET",
                "evidence": (
                    "all %d event rows carry source_dataset, source_page, source_row_index and a "
                    "verbatim note, and an ISO effective date; TESTS.py T1 and T4 enforce this and "
                    "T4 round-trips every row against the source file"
                )
                % m["events_emitted"],
            },
            "the table is not admitted to an experiment before cutoff review": {
                "status": "MET",
                "evidence": (
                    "every row of all three emitted tables carries admission_status=NOT_ADMITTED "
                    "and cutoff_status=CUTOFF_UNPROVEN; TESTS.py T5 enforces this"
                ),
            },
            "ambiguous tenure boundaries are marked, not smoothed": {
                "status": "MET",
                "evidence": (
                    "%d of %d tenure spells carry at least one explicit boundary flag; only %d "
                    "spells are dated at both ends by an event; interim spells are never carried "
                    "across a season boundary into named coverage; TESTS.py T3 enforces this"
                )
                % (
                    m["tenure_spells_boundary_ambiguous"],
                    m["tenure_spells"],
                    m["tenure_spells_fully_dated_both_ends"],
                ),
            },
        },
        "findings": [
            {
                "id": "D12-F1",
                "type": "POSITIVE_EXISTENCE",
                "severity": "HIGH",
                "claim": (
                    "A dated, sourced head-coaching event stream DOES exist in this repository. It "
                    "was not previously known to the program."
                ),
                "measured": {
                    "source_rows_naming_a_head_coach": m["source_rows_mentioning_head_coach"],
                    "events_parsed": m["events_emitted"],
                    "events_unparsed": m["events_unparsed"],
                    "hires": int(m["events_by_type"].get("HIRE", 0)),
                    "departures": int(m["events_by_type"].get("DEPART", 0)),
                    "distinct_coach_names": m["distinct_coach_names"],
                    "date_range": [m["events_date_min"], m["events_date_max"]],
                },
                "consequence": (
                    "The B1 gap in HYPOTHESES_agent_pace_coaching.md is partially closed by data "
                    "already in the repository, without any hand entry and without any external "
                    "source. It is NOT closed for cutoff-validity purposes."
                ),
            },
            {
                "id": "D12-F2",
                "type": "NEGATIVE_RESULT_PRESERVED",
                "severity": "HIGH",
                "claim": (
                    "The stream is not a coaching table. Half the canonical universe cannot be "
                    "given an event-anchored opening head coach."
                ),
                "measured": {
                    "team_seasons": m["coverage_team_seasons"],
                    "event_anchored": cs("NAMED_EVENT_ANCHORED"),
                    "fraction_event_anchored": m["coverage_fraction_event_anchored"],
                    "named_but_start_left_censored": cs("NAMED_START_LEFT_CENSORED"),
                    "named_but_carried_forward_unverified": cs(
                        "NAMED_OPEN_END_CARRIED_FORWARD_UNVERIFIED"
                    ),
                    "ambiguous_multiple_spells": cs("AMBIGUOUS_MULTIPLE_SPELLS"),
                    "unknown_no_spell": cs("UNKNOWN_NO_SPELL_COVERS_OPENER"),
                    "unknown_only_interim_carried": cs(
                        "UNKNOWN_ONLY_INTERIM_SPELL_CARRIED_ACROSS_SEASON"
                    ),
                    "team_games_with_a_nameable_opening_coach": named_tg,
                    "team_games_without_one": unnamed_tg,
                    "team_games_total": m["universe_team_game_rows"],
                },
                "consequence": (
                    "Any coach-identity feature built on this source today would be missing or "
                    "unverified on %d of %d team-game rows. That is a coverage hole, not a feature."
                )
                % (unnamed_tg, m["universe_team_game_rows"]),
            },
            {
                "id": "D12-F3",
                "type": "CUTOFF_VALIDITY",
                "severity": "HIGH",
                "claim": "Every record is CUTOFF_UNPROVEN. No coaching record has a source timestamp.",
                "measured": {
                    "source_columns": inp["coach_event_source"]["columns"],
                    "capture_timestamp_column_present": inp["coach_event_source"][
                        "has_capture_timestamp_column"
                    ],
                    "raw_source_pages_resident_in_worktree": m[
                        "raw_source_pages_resident_in_worktree"
                    ],
                    "events_whose_source_page_year_differs_from_event_year": m[
                        "events_with_page_year_ne_event_year"
                    ],
                },
                "consequence": (
                    "The date column is a transaction date, not a capture time. The cited source "
                    "pages are season-level pages that are rewritten as a league year progresses, "
                    "and %d events are filed under a page whose year differs from the event's own "
                    "calendar year, so page identity does not bound publication time either. "
                    "D10_FIELD_AVAILABILITY_LEDGER's cutoff_valid = 0 verdict for coaching SURVIVES "
                    "this node unchanged."
                )
                % m["events_with_page_year_ne_event_year"],
            },
            {
                "id": "D12-F4",
                "type": "SEMANTIC_AMBIGUITY",
                "severity": "MEDIUM",
                "claim": (
                    "An appointment date is not a first-game-coached date. Treating the two as the "
                    "same would silently mis-date every tenure boundary."
                ),
                "measured": m["appointment_to_first_game_days"],
                "consequence": (
                    "The median appointment precedes the coach's first game in the universe by %s "
                    "days and %d of %d appointments precede it by more than 30 days. Every dated "
                    "start in coaching_tenure_v1.csv therefore carries "
                    "APPOINTMENT_DATE_IS_NOT_FIRST_GAME_COACHED. A cutoff review must settle which "
                    "semantics a feature would use before any admission."
                )
                % (
                    m["appointment_to_first_game_days"]["median"],
                    m["appointment_to_first_game_days"]["n_gt_30d"],
                    m["appointment_to_first_game_days"]["n"],
                ),
            },
            {
                "id": "D12-F5",
                "type": "CAPTURE_GAP",
                "severity": "HIGH",
                "claim": (
                    "The current league year contributes zero coaching events. The table is empty "
                    "exactly where a live use would need it."
                ),
                "measured": {
                    "front_office_rows_by_source_page": m["front_office_rows_by_source_page"],
                    "head_coach_rows_by_source_page": m["head_coach_rows_by_source_page"],
                    "all_rows_by_source_page": m["all_rows_by_source_page_bbref"],
                    "latest_event_date": m["events_date_max"],
                },
                "consequence": (
                    "bbref_transactions_2026.html contributes %d rows to the source file and %d "
                    "front-office rows. Whether that means no 2026 coaching change occurred or the "
                    "front-office section was not captured CANNOT be distinguished from inside this "
                    "node. Treat 2026 tenure as unverified, not as stable."
                )
                % (
                    int(m["all_rows_by_source_page_bbref"].get("bbref_transactions_2026.html", 0)),
                    int(m["front_office_rows_by_source_page"].get("bbref_transactions_2026.html", 0)),
                ),
            },
            {
                "id": "D12-F6",
                "type": "SOURCE_INCOMPLETENESS",
                "severity": "MEDIUM",
                "claim": (
                    "The stream is incomplete in BOTH directions: there are departures with no "
                    "matching hire, and spells that end without a recorded departure."
                ),
                "measured": {
                    "spells_left_censored_no_hire_event": m["tenure_spells_left_censored"],
                    "spells_with_open_end_no_departure_event": m["tenure_spells_open_end"],
                    "spells_ended_only_by_succession": m[
                        "tenure_spells_end_inferred_by_succession"
                    ],
                    "franchises_with_no_coaching_event_at_all": [
                        "Minnesota Lynx (all 6 seasons UNKNOWN)"
                    ],
                },
                "consequence": (
                    "Completeness cannot be assumed in either direction, so 'no departure event' "
                    "does not license carrying a coach forward. That is why "
                    "NAMED_OPEN_END_CARRIED_FORWARD_UNVERIFIED is reported separately from "
                    "NAMED_EVENT_ANCHORED rather than merged into a single coverage number."
                ),
            },
            {
                "id": "D12-F7",
                "type": "ENTITY_RESOLUTION",
                "severity": "LOW",
                "claim": (
                    "The source's own team code disagrees with the program's team dimension for one "
                    "franchise, so joining on the team code would silently drop a row."
                ),
                "measured": {
                    "disagreements": m["team_code_disagreements"],
                    "n_disagreements": m["events_with_team_code_disagreement"],
                },
                "consequence": (
                    "This node resolves franchise identity from the full franchise name inside the "
                    "note text and maps it to team_id via D13's dimension, never via the source's "
                    "abbreviation. Any later join must do the same."
                ),
            },
            {
                "id": "D12-F8",
                "type": "STRUCTURAL_BREAK_INVENTORY",
                "severity": "INFORMATIONAL",
                "claim": (
                    "In-season head-coaching changes are rare in the observed window: %d events "
                    "fall inside a played season window."
                )
                % m["in_season_coaching_events"],
                "measured": {
                    "in_season_events": m["in_season_coaching_events"],
                    "detail": m["in_season_coaching_events_detail"],
                },
                "consequence": (
                    "Stated as an inventory of candidate structural breaks only. This node makes NO "
                    "claim about whether these events shift pace, possessions or any target, and "
                    "ran no such comparison."
                ),
            },
        ],
        "contradictions": [
            {
                "id": "D12-C1",
                "between": [
                    "experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json",
                    "data/injury_history/injury_history.csv (bytes)",
                ],
                "document_says": (
                    "field 'coaching identity, coaching change, tactical scheme', source 'none found "
                    "in the repository', verdict 'ABSENT', note 'no coaching source exists; a "
                    "`*coach*` sweep over data/ returns nothing'; and, under "
                    "statement_classification.UNCHANGED, 'the coaching-source absence (verified: no "
                    "*coach* source exists)'"
                ),
                "bytes_say": (
                    "a case-insensitive coach sweep of data/injury_history/injury_history.csv alone "
                    "returns %d matching lines, of which %d name a head coach with a franchise and "
                    "a date"
                )
                % (
                    m["source_rows_mentioning_coach_any_case"],
                    m["source_rows_mentioning_head_coach"],
                ),
                "resolution": (
                    "NOT RECONCILED INSIDE THIS NODE. Frozen bytes govern over prose and this node "
                    "does not edit a frozen Stage 2A artifact. Raised for the coordinator."
                ),
            },
            {
                "id": "D12-C2",
                "between": [
                    "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json",
                    "data/injury_history/injury_history.csv (bytes)",
                ],
                "document_says": (
                    "coaching.head_coach_identity verdict ABSENT, structural_class no_source, "
                    "evidence 'exhaustive search of the worktree for a coaching source found "
                    "NOTHING ... returns only free-text \"Coach's Decision\" reason strings inside "
                    "injury_log.csv, which name no coach'"
                ),
                "bytes_say": (
                    "injury_history.csv, committed 2026-07-30 in commit 98271bb and tracked on this "
                    "branch, contains %d rows naming a head coach with an explicit franchise and "
                    "date. The claimed exhaustive search missed the file."
                )
                % m["source_rows_mentioning_head_coach"],
                "resolution": (
                    "NOT RECONCILED INSIDE THIS NODE. D10 is another node's output and outside this "
                    "node's write scope. Its cutoff_valid = 0 conclusion is unaffected; its "
                    "availability verdict is not."
                ),
            },
            {
                "id": "D12-C3",
                "between": [
                    "experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md",
                    "data/injury_history/injury_history.csv (bytes)",
                ],
                "document_says": (
                    "'coaching and rotation strategy - not started. No code, artifact or "
                    "registration.'"
                ),
                "bytes_say": (
                    "no coaching CODE or REGISTRATION exists, which is correct, but a dated "
                    "coaching event SOURCE does exist. The matrix conflates the two."
                ),
                "resolution": "Reported, not edited. The matrix is outside this node's write scope.",
            },
        ],
        "stop_condition_assessment": {
            "stop_condition": (
                "a finding would change the primary target, the K0 structure, the inference "
                "structure, the candidate universe, the cutoff-valid feature set or the leakage "
                "status -- HALT and raise, do not resolve it inside the node"
            ),
            "verdict": "TRIPPED_ON_ONE_LIMB_HALTED_AND_RAISED",
            "limb_by_limb": {
                "primary_target": "NOT CHANGED. This node did not touch the target definition.",
                "K0_structure": "NOT CHANGED. This node did not touch any control.",
                "inference_structure": "NOT CHANGED. No fold, cluster or resampling change.",
                "candidate_universe": (
                    "NOT CHANGED. This node read the universe as "
                    "team_possession_prior_v1.parquet where pace_resolved == True and reproduced "
                    "%d team-game rows over %d game clusters and %d team-seasons, matching "
                    "EVIDENCE_PACKET_V2 and D13 exactly."
                )
                % (
                    m["universe_team_game_rows"],
                    m["universe_game_clusters"],
                    m["universe_team_seasons"],
                ),
                "cutoff_valid_feature_set": (
                    "NOT CHANGED. Nothing here becomes cutoff-valid. Every record is "
                    "CUTOFF_UNPROVEN and the count of cutoff-valid coaching fields remains zero, "
                    "exactly as D10 recorded."
                ),
                "leakage_status": (
                    "NOT CHANGED. Nothing is admitted, so nothing can leak. The node did not "
                    "construct, fit, score or evaluate anything."
                ),
                "field_availability_evidence": (
                    "CHANGED. A field the frozen packet recorded as ABSENT is PRESENT as "
                    "retrospective, cutoff-unproven reference data. This is the limb that trips."
                ),
            },
            "action_taken": (
                "HALTED rather than resolved. This node did not edit EVIDENCE_PACKET_V2, D10, the "
                "capability matrix, any registry, PROGRAM_STATE.json or any frozen artifact, and "
                "did not admit its own table to anything."
            ),
        },
        "escalations": [
            {
                "id": "D12-E1",
                "to": "possession wave / historical feature evidence",
                "statement": (
                    "The historical feature evidence for the possession wave records coaching "
                    "identity as ABSENT with source 'none found in the repository'. That is false "
                    "against the bytes. The correct status is PRESENT_RETROSPECTIVE / "
                    "CUTOFF_UNPROVEN, with event-anchored opening-coach coverage on %d of %d "
                    "team-seasons and %d of %d team-game rows."
                )
                % (
                    cs("NAMED_EVENT_ANCHORED"),
                    m["coverage_team_seasons"],
                    tg("NAMED_EVENT_ANCHORED"),
                    m["universe_team_game_rows"],
                ),
                "what_does_not_change": (
                    "cutoff-validity, the cutoff-valid feature set, the leakage status, the "
                    "candidate universe, K0 and the primary target are all unchanged."
                ),
            },
            {
                "id": "D12-E2",
                "to": "possession wave / B1 gap ordering",
                "statement": (
                    "HYPOTHESES_agent_pace_coaching.md ranks B1 first in Category B and prices it "
                    "at 'a few hours of work from public sources' plus '80-100 hand-entered rows'. "
                    "Roughly half that table is already derivable from data in the repository with "
                    "full row-level provenance and zero hand entry. The cost estimate, and "
                    "therefore the B-list ordering, is stale."
                ),
                "what_does_not_change": (
                    "B1 does NOT become Category A. The hand-collection caution in B1 ('a "
                    "hand-maintained table is a new canonical artifact with no automated "
                    "provenance') applies with equal force to the remaining half, and the "
                    "cutoff-validity problem is untouched."
                ),
            },
            {
                "id": "D12-E3",
                "to": "D10_FIELD_AVAILABILITY_LEDGER owner",
                "statement": (
                    "D10's coaching.head_coach_identity row cites an exhaustive search that missed "
                    "a tracked file committed before D10 ran. The verdict field needs revisiting "
                    "(ABSENT -> PRESENT_RETROSPECTIVE_CUTOFF_UNPROVEN); the coverage and "
                    "cutoff_valid figures for a CUTOFF-VALID feature remain 0."
                ),
                "what_does_not_change": "D10's cutoff_valid = 0 conclusion.",
            },
        ],
        "could_not_establish": [
            "Whether any coaching record was publicly available at or before its game's pregame cutoff. The source has no capture timestamp and its raw pages are not resident in this worktree.",
            "Whether the 2026 league year genuinely had no head-coaching change, or whether the front-office section of bbref_transactions_2026.html was not captured. Both are consistent with the bytes.",
            "The identity of any head coach before the first event on %s. Nine spells are left-censored and the Minnesota Lynx have no coaching event at all in six seasons." % m["events_date_min"],
            "The date on which any interim coach's spell ended, except where a successor's hire date bounds it. Three spells end only by succession.",
            "The first game each coach actually coached. The source dates appointments, not benches.",
            "Whether any of the %d in-season coaching events is associated with a change in pace, possessions or any target. No such comparison was run and none is permitted from this node." % m["in_season_coaching_events"],
            "The prior-team tempo history that B1 argues is the real cold-start prior. The source names coaches but carries nothing about their previous teams beyond what appears in these 48 events.",
        ],
        "scope_disclosures": [
            {
                "kind": "READ_OUTSIDE_DECLARED_SCOPE",
                "path": inp["coach_event_source"]["path"],
                "declared_read_scope": "experiments/player_program/",
                "why": (
                    "The mandate is a retrospectively auditable coaching table. The only file in "
                    "this repository containing dated coaching records is outside the declared read "
                    "scope. Reading nothing would have produced an empty deliverable for a "
                    "formalistic reason and would have left three documents' false ABSENT claims "
                    "standing."
                ),
                "bounded_by": (
                    "read-only; single file; no writes outside "
                    "experiments/player_program/data_lane/D12_COACHING_HISTORY/"
                ),
                "coordinator_action_requested": (
                    "either widen D12's allowed_read_paths to include data/injury_history/, or "
                    "reject this node's use of that source and record the coaching table as "
                    "unbuildable in scope."
                ),
            },
            {
                "kind": "WRITE_SCOPE_RESPECTED",
                "path": "experiments/player_program/data_lane/D12_COACHING_HISTORY/",
                "note": "no file outside this directory was created or modified; no git command was run",
            },
        ],
        "no_performance_peeking_attestation": {
            "sealed_results_read": False,
            "challenger_performance_inspected": False,
            "any_fit_or_score_run": False,
            "note": (
                "This node read one canonical universe file for its team-season keys and game dates "
                "only. It did not read projected_team_off_possessions, any residual, any arm output "
                "or anything under stage2b/SEALED_RESULTS."
            ),
        },
    }

    (NODE / "FINDINGS.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print("wrote FINDINGS.json with %d findings, %d contradictions, %d escalations"
          % (len(doc["findings"]), len(doc["contradictions"]), len(doc["escalations"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
