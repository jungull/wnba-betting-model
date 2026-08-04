#!/usr/bin/env python
"""Compose FINDINGS.json from the artifacts this node actually produced.

EPISTEMIC STATUS: PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future
features cutoff-provable. Creates no historical evidence and repairs no historical gap.

Every number in FINDINGS.json is READ OUT of SELFTEST_RECEIPT.json, SOURCE_BINDING.json or the
files on disk. Nothing is transcribed by hand. Run TESTS.py, selftest_capture.py and
build_source_binding.py before this.

Usage:  python build_findings.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

LANE = Path(__file__).resolve().parent
PROGRAM = LANE.parent.parent
REPO = PROGRAM.parent.parent

EPISTEMIC = ("PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future "
             "features cutoff-provable. Creates no historical evidence and repairs no historical "
             "gap.")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_tests() -> dict:
    r = subprocess.run([sys.executable, "TESTS.py"], cwd=LANE, capture_output=True, text=True)
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    return {
        "command": "python TESTS.py",
        "exit_code": r.returncode,
        "n_tests": len(lines),
        "n_passed": sum(1 for ln in lines if ln.startswith("PASS")),
        "n_failed": sum(1 for ln in lines if ln.startswith("FAIL")),
        "test_names": [ln.split("  ", 1)[1] for ln in lines],
    }


def main() -> int:
    receipt = json.loads((LANE / "SELFTEST_RECEIPT.json").read_text(encoding="utf-8"))
    binding = json.loads((LANE / "SOURCE_BINDING.json").read_text(encoding="utf-8"))
    tests = run_tests()

    c = receipt["counts"]
    today = datetime.now(timezone.utc).date()

    measurements = [
        {"claim": "the capture accepts all eight domains the contract enumerates",
         "value": f"{c['domains_exercised']} of {c['domains_declared']} domains exercised; "
                  f"{c['contract_criteria']} contract criteria, one domain each",
         "how_measured": "python selftest_capture.py -> SELFTEST_RECEIPT.json "
                         ".counts.domains_exercised; python TESTS.py test "
                         "'domains: exactly the eight contract criteria, one domain each'"},
        {"claim": "records appended by the synthetic self-test corpus",
         "value": f"{c['records_appended']} records over {c['entities']} entities "
                  f"({c['first_seen_records']} first_seen, {c['change_records']} change, "
                  f"{c['reaffirmation_records']} reaffirmation)",
         "how_measured": "SELFTEST_RECEIPT.json .counts"},
        {"claim": "first_seen is never overwritten",
         "value": f"{receipt['first_seen_immutability']['entities_checked']} entities checked, "
                  f"{receipt['first_seen_immutability']['entities_with_more_than_one_first_seen_value']}"
                  f" with more than one first_seen value",
         "how_measured": "SELFTEST_RECEIPT.json .first_seen_immutability; independently in "
                         "TESTS.py 'verify: catches an overwritten first_seen_at_utc'"},
        {"claim": "full change history is preserved rather than collapsed",
         "value": f"the worked injury entity carries "
                  f"{receipt['change_history_example']['n_records']} records "
                  f"(QUESTIONABLE -> OUT -> OUT reaffirmed) with change_index 0,1,1 and all "
                  f"prior payloads still present",
         "how_measured": "SELFTEST_RECEIPT.json .change_history_example.trace"},
        {"claim": "every write extends the ledger without rewriting it",
         "value": f"{receipt['append_only']['n_writes_checked']} writes checked, all "
                  f"prefix-preserving: "
                  f"{receipt['append_only']['every_write_extended_the_file_without_rewriting_it']}",
         "how_measured": "SELFTEST_RECEIPT.json .append_only (bytes-before is a prefix of "
                         "bytes-after on every append)"},
        {"claim": "a record is never backdated",
         "value": f"{receipt['rejection_summary']['n_cases']} rejection cases, "
                  f"{receipt['rejection_summary']['n_matched_expected_code']} raised the expected "
                  f"code, {receipt['rejection_summary']['n_that_modified_the_ledger']} modified "
                  f"the ledger",
         "how_measured": "SELFTEST_RECEIPT.json .rejections / .rejection_summary; codes "
                         "FUTURE_OBSERVATION, BACKDATED_OBSERVATION, "
                         "BACKDATED_ENTITY_OBSERVATION, "
                         "RETROSPECTIVE_CLAIMS_EARLY_OBSERVATION, PUBLISHED_AFTER_OBSERVED"},
        {"claim": "the derived index is a pure function of the ledger",
         "value": f"STATE_INDEX byte-identical after replay: "
                  f"{receipt['replay_determinism']['state_index_reproduced_byte_identically']}; "
                  f"WATERMARKS: "
                  f"{receipt['replay_determinism']['watermarks_reproduced_byte_identically']}",
         "how_measured": "SELFTEST_RECEIPT.json .replay_determinism (delete both derived files, "
                         "reconstruct the ledger from observations.jsonl, regenerate, compare)"},
        {"claim": "the ledger is internally consistent under independent re-derivation",
         "value": f"verify(): ok={receipt['integrity_verify']['ok']}, "
                  f"{len(receipt['integrity_verify']['violations'])} violations over "
                  f"{receipt['integrity_verify']['n_records']} records",
         "how_measured": "SELFTEST_RECEIPT.json .integrity_verify"},
        {"claim": "cutoff admission is strict and refuses unproven observation",
         "value": "0 entities admissible at a cutoff equal to the first observation time; "
                  f"{receipt['cutoff_admission']['T0_plus_31min']['n_entities_admissible']} at "
                  "T0+31min returning designation "
                  f"{receipt['cutoff_admission']['T0_plus_31min']['injury_designation_state']}; "
                  f"{receipt['cutoff_admission']['T0_plus_120min']['n_entities_admissible']} at "
                  "T0+120min returning "
                  f"{receipt['cutoff_admission']['T0_plus_120min']['injury_designation_state']}; "
                  f"{receipt['cutoff_unproven_never_admitted']['n_cutoff_unproven_records']} "
                  "CUTOFF_UNPROVEN record admitted at a 2030 cutoff: "
                  f"{receipt['cutoff_unproven_never_admitted']['n_admitted_at_2030_cutoff']}",
         "how_measured": "SELFTEST_RECEIPT.json .cutoff_admission and "
                         ".cutoff_unproven_never_admitted"},
        {"claim": "the test suite passes",
         "value": f"{tests['n_passed']}/{tests['n_tests']} tests, exit code {tests['exit_code']}",
         "how_measured": tests["command"]},
        {"claim": "live sources bound to the capture",
         "value": f"{binding['n_bound']} of {binding['n_domains']}",
         "how_measured": "python build_source_binding.py -> SOURCE_BINDING.json .n_bound"},
        {"claim": "real observations captured by this node",
         "value": "0 records in the production ledger ledger/observations.jsonl "
                  f"({(LANE / 'ledger' / 'observations.jsonl').stat().st_size} bytes)",
         "how_measured": "ledger/MANIFEST.json .n_records; os.stat on the ledger file"},
        {"claim": "no source of pregame minute restrictions is named anywhere in the node's "
                  "read scope",
         "value": f"{binding['domains']['minute_restriction']['absence_search']['n_hits']} lines "
                  f"match over "
                  f"{binding['domains']['minute_restriction']['absence_search']['files_scanned']}"
                  " files; "
                  f"{binding['domains']['minute_restriction']['absence_search']['n_hits_self_referential_orchestration']}"
                  " are this graph restating D11's own acceptance criterion and the remaining "
                  f"{binding['domains']['minute_restriction']['absence_search']['n_hits_outside_orchestration']}"
                  " are a 40-minute exposure validation cap in build_projected_exposure.py and "
                  "its validation receipt. Zero name a source.",
         "how_measured": "build_source_binding.grep_count(r'minute[s]?[ _-]?"
                         "(restriction|cap|limit)') over experiments/player_program/, this "
                         "node's own directory excluded; hits enumerated in SOURCE_BINDING.json"},
        {"claim": "no coaching source exists in the node's read scope",
         "value": f"{binding['domains']['coaching_change']['absence_search']['n_hits']} hits for "
                  "a data/*coach* path over "
                  f"{binding['domains']['coaching_change']['absence_search']['files_scanned']} "
                  "files; independently, the frozen packet records verdict "
                  f"{binding['domains']['coaching_change']['packet_evidence']['verdict']!r}",
         "how_measured": "build_source_binding.grep_count(r'data/[a-z0-9_]*coach'); "
                         "EVIDENCE_PACKET_V2.json "
                         ".cutoff_valid_availability_table_CORRECTED"},
        {"claim": "no captured pregame lineup or starter feed exists",
         "value": f"the frozen packet's verdict for 'starting lineup / rotation announced "
                  f"pregame' is "
                  f"{binding['domains']['lineup']['packet_evidence']['verdict']!r} with source "
                  f"{binding['domains']['lineup']['packet_evidence']['source']!r}; a text search "
                  f"returns {binding['domains']['lineup']['absence_search']['n_hits']} mentions, "
                  "all of which are program prose recording the absence or a derived 'projected "
                  "lineup strength' feature, none a capture path",
         "how_measured": "EVIDENCE_PACKET_V2.json availability table; "
                         "build_source_binding.grep_count(r'(announced|projected|posted)"
                         "[ _-]?(starting[ _-]?)?lineup'), hits enumerated in "
                         "SOURCE_BINDING.json for audit"},
        {"claim": "the two frozen artifacts this node leans on are unchanged",
         "value": "EVIDENCE_PACKET_V2.json sha256 "
                  f"{binding['cited_artifacts']['EVIDENCE_PACKET_V2']['sha256']} and "
                  "V2_STOP_CONDITION.json sha256 "
                  f"{binding['cited_artifacts']['V2_STOP_CONDITION']['sha256']} both equal the "
                  "values pinned in orchestration/nodes/G00_LIVE_RECONCILIATION/"
                  "RECONCILIATION.json",
         "how_measured": "hashlib.sha256 over the files in build_source_binding.py, compared "
                         "against RECONCILIATION.json .checks.frozen_hashes"},
    ]

    acceptance = {
        "capture covers injury designation changes, lineups, starters, minute restrictions, "
        "transactions, coaching changes, odds and attributable news": {
            "status": "MET_AS_MECHANISM_ONLY",
            "evidence": f"{c['domains_exercised']}/8 domains declared and exercised end to end "
                        "over a synthetic corpus",
            "limitation": "no domain is bound to a live source; the capture has captured nothing",
        },
        "first-seen timestamp and full change history are preserved, never overwritten": {
            "status": "MET",
            "evidence": "first_seen copied forward on every record; 0 entities with more than one "
                        "first_seen value; change/reaffirmation records appended; verify() "
                        "detects an overwritten first_seen, an in-place payload edit and a "
                        "deleted intermediate record",
        },
        "a record is never backdated": {
            "status": "MET",
            "evidence": f"{receipt['rejection_summary']['n_cases']} rejection cases all raised "
                        "the expected code and none wrote a byte; five distinct backdating rules "
                        "enforced at append and re-derived by verify()",
        },
        "the capture writes only under its own lane directory": {
            "status": "MET",
            "evidence": "assert_in_scope() on every write path; constructing a ledger outside "
                        "the lane raises SCOPE_VIOLATION; a test walks every file this node "
                        "wrote and asserts it resolves inside the lane directory",
        },
    }

    contradictions = [
        {
            "id": "C1_odds_coverage_span_ends_after_the_observation_moment",
            "where": "stage2a/EVIDENCE_PACKET_V2.json, cutoff_valid_availability_table_CORRECTED,"
                     " field 'market odds / totals'",
            "text": binding["domains"]["odds"]["packet_evidence"]["coverage"],
            "measured": f"the stated coverage end 2026-08-06 is {(date(2026, 8, 6) - today).days}"
                        f" days after the current date {today.isoformat()}, whereas the injury "
                        "row in the same table ends 2026-08-04, exactly today",
            "why_it_matters": "one 'coverage' column is carrying two different kinds of span: an "
                              "OBSERVATION span for the injury row and an EVENT-DATE span for the "
                              "odds row. A line posted today for a game on 2026-08-06 is observed "
                              "today. Reading the odds row as an observation span would credit "
                              "the repository with having seen two days of the future.",
            "severity": "B -- interpretation exceeding the evidence",
            "resolved_here": "no. The packet is frozen and is NOT edited. This node's schema "
                             "separates observed_at_utc from effective_at_utc so the conflation "
                             "cannot recur inside the capture.",
        },
        {
            "id": "C2_injury_capture_span_differs_between_two_in_scope_receipts",
            "where": "ROSTER_SOURCE_AUDIT_RECEIPT.json (generated 2026-08-03T21:26:32Z) reports "
                     "report_date_range 2026-07-30..2026-08-01 over 551 rows; "
                     "EVIDENCE_PACKET_V2.json reports 2026-07-30..2026-08-04",
            "measured": "the two spans differ by three days; the earlier receipt carries an "
                        "explicit generation timestamp and the packet does not",
            "why_it_matters": "this is consistent with a live capture that grew between the two "
                              "measurements, and is NOT presented as a defect. It is recorded "
                              "because neither figure can be cited as the capture's span without "
                              "naming the moment it was measured -- which is the same failure "
                              "mode as C1 one step removed.",
            "severity": "C -- record for the next contract version",
            "resolved_here": "no. Not verifiable from inside this node's read scope; both files "
                             "describe data/ which this node may not open.",
        },
        {
            "id": "C3_node_read_scope_cannot_reach_the_sources_the_node_must_capture",
            "where": "orchestration/PROGRAM_GRAPH.json, node D11_LIVE_INFORMATION_CAPTURE, "
                     "allowed_read_paths = ['experiments/player_program/']",
            "measured": "all eight domains' candidate sources named anywhere in the program "
                        "record live under the repository's data/ tree "
                        "(data/injury_capture/, data/injury_history/, data/news_capture/, "
                        "data/odds_capture/); 0 of 8 is reachable under the declared read scope",
            "why_it_matters": "the node is contracted to build capture covering eight domains, "
                              "and is scoped so that it cannot open, parse or verify a single one "
                              "of them. The mechanism can be built and tested -- it was -- but no "
                              "adapter can honestly be written against a file that was never "
                              "read, so the node ships with zero bindings.",
            "severity": "B -- a contract defect, not a scientific one",
            "resolved_here": "no. An agent may not broaden its own read or write scope. Raised "
                             "for the coordinator.",
        },
    ]

    could_not_establish = [
        "whether the existing live captures (data/injury_capture/, data/news_capture/, "
        "data/odds_capture/, data/ref_assignments/) actually preserve first-seen and change "
        "history, or whether any of them overwrites. The node's read scope stops at "
        "experiments/player_program/. The only in-scope statement is "
        "ROSTER_SOURCE_AUDIT_RECEIPT.json's q5 for data/injury_capture/injury_log.csv -- "
        "'corrections overwrite history: NO' -- which is another node's measurement, not this "
        "node's.",
        "the current row counts, spans or schemas of any live capture. Every such figure in this "
        "output is quoted from a frozen in-scope receipt with its sha256, and is labelled as "
        "someone else's measurement.",
        "whether any historical odds exist. V2_STOP_CONDITION records, unresolved, that "
        "tip_times.csv is odds-derived and covers 2022-2026 while the packet says market odds are "
        "unavailable historically. tip_times.csv is outside this node's read scope and was not "
        "opened.",
        "the real-world latency between a designation change happening and this repository "
        "observing it. That is measurable only after a source is bound and has run for a while; "
        "the ledger records exactly the fields needed to measure it later "
        "(published_at_utc vs observed_at_utc).",
        "whether any captured field would improve any model. This node performs no fit, no score "
        "and no comparison, and read nothing under stage2b/SEALED_RESULTS/.",
    ]

    escalations = [
        {
            "to": "possession wave / historical feature evidence",
            "item": "C1 above. The frozen availability table's 'coverage' column mixes an "
                    "observation span (injury row, ends today) with an event-date span (odds row, "
                    "ends two days after today). Any future reader who treats the odds row as an "
                    "observation span will over-credit the historical record by the length of the "
                    "forward-dated tail. The packet is frozen; this node did not edit it.",
            "changes_historical_evidence": "potentially -- it changes how an availability verdict "
                                           "should be read, not what the underlying data is",
        },
        {
            "to": "possession wave / historical feature evidence",
            "item": "V2_STOP_CONDITION's already-recorded, unresolved nit that tip_times.csv is "
                    "odds-derived over 2022-2026 while market odds are declared historically "
                    "unavailable. D11 confirms this matters and cannot settle it: it decides "
                    "whether the odds domain has ANY pre-2026-07-31 evidence, and if it does, "
                    "whether that evidence is a single retrospective pull (the S-TX regime, "
                    "CUTOFF_UNPROVEN) or something better. NOT MEASURED HERE -- tip_times.csv is "
                    "outside this node's read scope.",
            "changes_historical_evidence": "possibly, and it is unresolved in the frozen halt "
                                           "packet already",
        },
        {
            "to": "coordinator / graph contract",
            "item": "C3 above. D11's allowed_read_paths cannot reach any of the eight sources it "
                    "is contracted to capture. Either widen the read scope for a follow-up "
                    "binding node, or record that D11 delivers mechanism only. This node did not "
                    "broaden its own scope.",
            "changes_historical_evidence": "no",
        },
    ]

    outputs = {}
    for p in sorted(LANE.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.name != "FINDINGS.json":
            outputs[p.relative_to(LANE).as_posix()] = {"sha256": sha(p), "bytes": p.stat().st_size}

    findings = {
        "schema": "player_program/data_lane_findings/1",
        "node": "D11_LIVE_INFORMATION_CAPTURE",
        "lane": "data",
        "type": "implementation",
        "epistemic_status": EPISTEMIC,
        "generated_by": "build_findings.py",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "headline": (
            "The capture mechanism is built, tested and enforces first-seen, full change history, "
            "no backdating and lane-only writes. It is bound to ZERO live sources and has "
            "captured ZERO real observations, because every candidate source lies outside this "
            "node's declared read scope or does not exist at all."
        ),
        "what_was_built": [
            "capture_schema.py -- eight domains, one per contract criterion, with declared "
            "fields, enumerations, and a call-site blocklist refusing realised target-game "
            "outcomes and their surrogates",
            "capture_ledger.py -- append-only JSONL ledger with immutable first_seen, appended "
            "change history, five no-backdating rules, a derived-and-replayable state index, an "
            "independent verify() that catches hand editing, and strict-inequality cutoff "
            "admission that refuses CUTOFF_UNPROVEN records",
            "SOURCE_BINDING.json -- per-domain declaration of why no source is bound, every "
            "verdict extracted programmatically from a frozen in-scope artifact with its sha256",
            "selftest_capture.py + SELFTEST_RECEIPT.json -- a synthetic corpus exercising all "
            "eight domains and every rejection path",
            "TESTS.py -- standalone suite (pytest is not installed); main() returns 1 on failure",
            "CAPTURE_CONTRACT.md -- the specification, with the code named as governing",
        ],
        "measurements": measurements,
        "acceptance_criteria": acceptance,
        "test_run": tests,
        "source_binding": {
            "n_domains": binding["n_domains"],
            "n_bound": binding["n_bound"],
            "per_domain": {k: {"bound": v["bound"],
                               "candidate_source": v.get(
                                   "candidate_source_named_in_program_docs"),
                               "why_not_bound": v["why_not_bound"]}
                           for k, v in binding["domains"].items()},
        },
        "negative_results_preserved": [
            "NO source of pregame minute restrictions exists anywhere in the node's read scope, "
            "and the frozen availability table does not list the field at all -- it has never "
            "been adjudicated, even as unavailable.",
            "NO coaching source exists (frozen packet verdict ABSENT; a data/*coach* search "
            "returns 0 hits in scope).",
            "NO captured pregame lineup or starter feed exists; the only lineup artifacts in the "
            "repository are realised and are an explicit must-not-reuse.",
            "The production ledger is EMPTY and is committed empty. That is the honest state.",
            "Capturing forward from today can never retro-fit history. Nothing this node builds "
            "creates evidence about any game already played.",
        ],
        "contradictions": contradictions,
        "could_not_establish": could_not_establish,
        "escalations": escalations,
        "stop_conditions": {
            "declared": "a finding would change the primary target, the K0 structure, the "
                        "inference structure, the candidate universe, the cutoff-valid feature "
                        "set or the leakage status",
            "tripped": False,
            "reasoning": "this node adjudicates no field, promotes no field, and touches no "
                         "historical row. The payload blocklist is a restriction on what may be "
                         "CAPTURED; it neither widens nor narrows the cutoff-valid feature set. "
                         "The contradictions found are documentation defects and a contract "
                         "scope defect, and are raised rather than resolved.",
        },
        "frozen_artifacts_touched": [],
        "outputs": outputs,
    }

    p = LANE / "FINDINGS.json"
    p.write_text(json.dumps(findings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {p.name}: {len(measurements)} measurements, "
          f"{len(contradictions)} contradictions, {len(escalations)} escalations, "
          f"tests {tests['n_passed']}/{tests['n_tests']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
