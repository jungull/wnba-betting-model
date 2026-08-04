#!/usr/bin/env python
"""Drive the capture ledger over a SYNTHETIC corpus and write SELFTEST_RECEIPT.json.

EPISTEMIC STATUS: PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future
features cutoff-provable. Creates no historical evidence and repairs no historical gap.

Everything this script writes is SYNTHETIC. Teams are `SYNTH_A`/`SYNTH_B`, players are
`SYNTH PLAYER ONE`..., the book is `SYNTHBOOK`, and both sources are named `SELFTEST_*`. No real
observation of any kind is captured here, and the self-test ledger lives in `selftest/`, separate
from the empty production ledger in `ledger/`. Nothing in `selftest/` may ever be read as evidence
about the WNBA.

The corpus exists to MEASURE the four acceptance criteria against running code:
  1. all eight contract domains accepted;
  2. first-seen and full change history preserved, never overwritten;
  3. a record is never backdated (four distinct rejections, by code);
  4. every write lands inside the lane directory (a write outside it raises).

Usage:  python selftest_capture.py
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from capture_schema import (
    CONTRACT_CRITERIA,
    DOMAINS,
    CaptureError,
    domain_table,
    sha256_text,
)
from capture_ledger import (
    CUTOFF_PROVABLE,
    CUTOFF_UNPROVEN,
    CaptureLedger,
    SourceRegistry,
    assert_in_scope,
)

LANE_DIR = Path(__file__).resolve().parent
SELFTEST_DIR = LANE_DIR / "selftest"
PROD_DIR = LANE_DIR / "ledger"

T0 = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)


def ts(minutes: int) -> str:
    return (T0 + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeClock:
    """Deterministic write-moment clock, so the receipt is byte-reproducible."""

    def __init__(self):
        self.value = ts(0)

    def __call__(self) -> str:
        return self.value


REGISTRY = SourceRegistry({
    "SELFTEST_LIVE_FEED": {
        "observation_provable": True,
        "what_it_is": "synthetic stand-in for a feed this repository fetches and timestamps",
    },
    "SELFTEST_BULK_ARCHIVE": {
        "observation_provable": False,
        "what_it_is": "synthetic stand-in for a one-pass retrospective dump (the S-TX shape)",
    },
})

FIVE_A = ["SYNTH PLAYER ONE", "SYNTH PLAYER TWO", "SYNTH PLAYER THREE",
          "SYNTH PLAYER FOUR", "SYNTH PLAYER FIVE"]
FIVE_A2 = ["SYNTH PLAYER SIX", "SYNTH PLAYER TWO", "SYNTH PLAYER THREE",
           "SYNTH PLAYER FOUR", "SYNTH PLAYER FIVE"]

# (ingest_minute, observed_minute, domain, source, payload, kwargs)
ACCEPTED_EVENTS = [
    (0, 0, "injury_designation", "SELFTEST_LIVE_FEED",
     {"season": 2026, "team": "SYNTH_A", "player": "SYNTH PLAYER ONE",
      "designation": "QUESTIONABLE", "reason": "right ankle", "report_label": "1130ET"}, {}),
    (5, 5, "lineup", "SELFTEST_LIVE_FEED",
     {"game_key": "SYNTH-G1", "team": "SYNTH_A", "announced_five": FIVE_A,
      "lineup_status": "PROJECTED"}, {}),
    (5, 5, "starter", "SELFTEST_LIVE_FEED",
     {"game_key": "SYNTH-G1", "team": "SYNTH_A", "player": "SYNTH PLAYER ONE",
      "starter_status": "ANNOUNCED_STARTER"}, {}),
    (10, 10, "minute_restriction", "SELFTEST_LIVE_FEED",
     {"season": 2026, "team": "SYNTH_A", "player": "SYNTH PLAYER TWO",
      "restriction_type": "MINUTES_CAP", "minutes_cap": 24,
      "restriction_note": "return to play"}, {}),
    (15, 15, "transaction", "SELFTEST_LIVE_FEED",
     {"transaction_key": "SYNTH-TX-0001", "transaction_type": "SIGNING",
      "player": "SYNTH PLAYER SEVEN", "to_team": "SYNTH_B", "season": 2026},
     {"effective_at_utc": ts(1440)}),          # takes effect tomorrow: legitimately in the future
    (20, 20, "coaching_change", "SELFTEST_LIVE_FEED",
     {"season": 2026, "team": "SYNTH_B", "head_coach": "SYNTH COACH BETA",
      "change_type": "INTERIM", "predecessor": "SYNTH COACH ALPHA", "interim": True}, {}),
    (25, 25, "odds", "SELFTEST_LIVE_FEED",
     {"game_key": "SYNTH-G1", "book": "SYNTHBOOK", "market": "TOTAL", "line": 162.5,
      "price_over": -110, "price_under": -110}, {}),
    (30, 30, "news", "SELFTEST_LIVE_FEED",
     {"source_item_id": "SYNTH-NEWS-0001",
      "headline": "SYNTH PLAYER ONE listed questionable for SYNTH-G1",
      "attributed_to": "SYNTH BEAT REPORTER", "claim_type": "REPORT",
      "url": "https://example.invalid/synth/1", "teams": ["SYNTH_A"]},
     {"published_at_utc": ts(28)}),            # published before observed: legal
    # --- revisions: the same entities seen again -------------------------------------------
    (60, 60, "injury_designation", "SELFTEST_LIVE_FEED",
     {"season": 2026, "team": "SYNTH_A", "player": "SYNTH PLAYER ONE",
      "designation": "OUT", "reason": "right ankle", "report_label": "1600ET"}, {}),
    (65, 65, "odds", "SELFTEST_LIVE_FEED",
     {"game_key": "SYNTH-G1", "book": "SYNTHBOOK", "market": "TOTAL", "line": 163.5,
      "price_over": -108, "price_under": -112}, {}),
    (90, 90, "injury_designation", "SELFTEST_LIVE_FEED",
     {"season": 2026, "team": "SYNTH_A", "player": "SYNTH PLAYER ONE",
      "designation": "OUT", "reason": "right ankle", "report_label": "1600ET"}, {}),
    (95, 95, "lineup", "SELFTEST_LIVE_FEED",
     {"game_key": "SYNTH-G1", "team": "SYNTH_A", "announced_five": FIVE_A2,
      "lineup_status": "ANNOUNCED"}, {}),
    # --- a retrospective bulk record: real effective date, unprovable observation ------------
    (100, 100, "transaction", "SELFTEST_BULK_ARCHIVE",
     {"transaction_key": "SYNTH-TX-ARCHIVE-1955", "transaction_type": "WAIVER",
      "player": "SYNTH PLAYER EIGHT", "from_team": "SYNTH_A", "season": 2021},
     {"retrospective": True, "effective_at_utc": "2021-05-14T00:00:00Z"}),
]

# (label, ingest_minute, callable-kwargs) -> each MUST raise, with the expected code
REJECTION_CASES = [
    ("backdated_behind_source_watermark", 105, dict(
        domain="injury_designation", source_id="SELFTEST_LIVE_FEED",
        payload={"season": 2026, "team": "SYNTH_A", "player": "SYNTH PLAYER NINE",
                 "designation": "OUT"},
        observed_at_utc=ts(30)), "BACKDATED_OBSERVATION"),
    ("observation_dated_after_the_write", 105, dict(
        domain="odds", source_id="SELFTEST_LIVE_FEED",
        payload={"game_key": "SYNTH-G1", "book": "SYNTHBOOK", "market": "SPREAD", "line": -3.5},
        observed_at_utc=ts(200)), "FUTURE_OBSERVATION"),
    ("retrospective_claiming_early_observation", 105, dict(
        domain="transaction", source_id="SELFTEST_BULK_ARCHIVE",
        payload={"transaction_key": "SYNTH-TX-ARCHIVE-1956", "transaction_type": "SIGNING",
                 "player": "SYNTH PLAYER TEN"},
        observed_at_utc=ts(101), retrospective=True), "RETROSPECTIVE_CLAIMS_EARLY_OBSERVATION"),
    ("published_after_observed", 105, dict(
        domain="news", source_id="SELFTEST_LIVE_FEED",
        payload={"source_item_id": "SYNTH-NEWS-0002", "headline": "later",
                 "attributed_to": "SYNTH BEAT REPORTER", "claim_type": "REPORT"},
        observed_at_utc=ts(104), published_at_utc=ts(105)), "PUBLISHED_AFTER_OBSERVED"),
    ("realised_outcome_key_in_payload", 105, dict(
        domain="injury_designation", source_id="SELFTEST_LIVE_FEED",
        payload={"season": 2026, "team": "SYNTH_A", "player": "SYNTH PLAYER ONE",
                 "designation": "AVAILABLE", "minutes": 34},
        observed_at_utc=ts(104)), "PROHIBITED_PAYLOAD_KEY"),
    ("overtime_surrogate_key_in_payload", 105, dict(
        domain="odds", source_id="SELFTEST_LIVE_FEED",
        payload={"game_key": "SYNTH-G1", "book": "SYNTHBOOK", "market": "TOTAL", "line": 164.0,
                 "is_overtime": False},
        observed_at_utc=ts(104)), "PROHIBITED_PAYLOAD_KEY"),
    ("unattributed_news_item", 105, dict(
        domain="news", source_id="SELFTEST_LIVE_FEED",
        payload={"source_item_id": "SYNTH-NEWS-0003", "headline": "rumour with no source",
                 "attributed_to": "", "claim_type": "RUMOUR"},
        observed_at_utc=ts(104)), "SCHEMA_VIOLATION"),
    ("undeclared_enum_value", 105, dict(
        domain="injury_designation", source_id="SELFTEST_LIVE_FEED",
        payload={"season": 2026, "team": "SYNTH_A", "player": "SYNTH PLAYER ELEVEN",
                 "designation": "GAME_TIME_DECISION"},
        observed_at_utc=ts(104)), "SCHEMA_VIOLATION"),
    ("undeclared_field", 105, dict(
        domain="coaching_change", source_id="SELFTEST_LIVE_FEED",
        payload={"season": 2026, "team": "SYNTH_B", "head_coach": "SYNTH COACH BETA",
                 "change_type": "INTERIM", "salary": 1},
        observed_at_utc=ts(104)), "SCHEMA_VIOLATION"),
    ("unregistered_source", 105, dict(
        domain="odds", source_id="SOME_UNREGISTERED_FEED",
        payload={"game_key": "SYNTH-G1", "book": "SYNTHBOOK", "market": "TOTAL", "line": 1.0},
        observed_at_utc=ts(104)), "SCHEMA_VIOLATION"),
]


def run(fresh: bool = True) -> dict:
    if fresh and SELFTEST_DIR.exists():
        shutil.rmtree(SELFTEST_DIR)
    clock = FakeClock()
    led = CaptureLedger(SELFTEST_DIR, REGISTRY, clock=clock)

    append_only_prefix_checks = []
    accepted = []
    for ing, obs, domain, source, payload, kw in ACCEPTED_EVENTS:
        before = led.path.read_bytes() if led.path.exists() else b""
        clock.value = ts(ing)
        rec = led.append(domain=domain, source_id=source, payload=payload,
                         observed_at_utc=ts(obs), fetch_id=f"SYNTH-FETCH-{ing:04d}", **kw)
        after = led.path.read_bytes()
        append_only_prefix_checks.append(after.startswith(before) and len(after) > len(before))
        accepted.append(rec)

    rejections = []
    for label, ing, kwargs, want_code in REJECTION_CASES:
        clock.value = ts(ing)
        bytes_before = led.path.read_bytes()
        try:
            led.append(fetch_id="SYNTH-FETCH-REJECT", **kwargs)
            rejections.append({"case": label, "raised": False, "expected_code": want_code,
                               "actual_code": None, "matched": False,
                               "ledger_unchanged": led.path.read_bytes() == bytes_before})
        except CaptureError as exc:
            rejections.append({"case": label, "raised": True, "expected_code": want_code,
                               "actual_code": exc.code, "matched": exc.code == want_code,
                               "message": str(exc)[:200],
                               "ledger_unchanged": led.path.read_bytes() == bytes_before})

    # scope guard: a ledger rooted outside the lane directory must be refused outright
    scope_case = {"case": "write_outside_lane_directory", "raised": False, "actual_code": None}
    try:
        CaptureLedger(LANE_DIR.parent / "NOT_MY_LANE", REGISTRY, clock=clock)
    except CaptureError as exc:
        scope_case = {"case": "write_outside_lane_directory", "raised": True,
                      "actual_code": exc.code, "expected_code": "SCOPE_VIOLATION",
                      "matched": exc.code == "SCOPE_VIOLATION",
                      "attempted_path": str((LANE_DIR.parent / "NOT_MY_LANE").resolve())}

    led.write_derived()
    verify = led.verify()

    # --- replay determinism: derived files must be a pure function of the ledger -------------
    state_before = (SELFTEST_DIR / "STATE_INDEX.json").read_text(encoding="utf-8")
    wm_before = (SELFTEST_DIR / "WATERMARKS.json").read_text(encoding="utf-8")
    (SELFTEST_DIR / "STATE_INDEX.json").unlink()
    (SELFTEST_DIR / "WATERMARKS.json").unlink()
    led2 = CaptureLedger(SELFTEST_DIR, REGISTRY, clock=clock)
    led2.write_derived()
    replay_state_identical = (
        (SELFTEST_DIR / "STATE_INDEX.json").read_text(encoding="utf-8") == state_before)
    replay_wm_identical = (
        (SELFTEST_DIR / "WATERMARKS.json").read_text(encoding="utf-8") == wm_before)

    # --- first-seen immutability, measured per entity ----------------------------------------
    records = led.read_records()
    per_entity_first_seen: dict[str, set] = {}
    for r in records:
        per_entity_first_seen.setdefault(r["entity_key"], set()).add(r["first_seen_at_utc"])
    entities_with_multiple_first_seen = {k: sorted(v)
                                         for k, v in per_entity_first_seen.items() if len(v) > 1}

    # --- change history, measured -------------------------------------------------------------
    injury_key = [r["entity_key"] for r in records
                  if r["domain"] == "injury_designation"][0]
    injury_history = led.history(injury_key)
    injury_trace = [
        {"ingest_seq": r["ingest_seq"], "observed_at_utc": r["observed_at_utc"],
         "change_kind": r["change_kind"], "change_index": r["change_index"],
         "designation": r["payload"]["designation"],
         "first_seen_at_utc": r["first_seen_at_utc"]}
        for r in injury_history
    ]

    # --- cutoff admission, measured -----------------------------------------------------------
    cutoffs = {}
    for label, cut in [("before_any_capture", ts(-1)),
                       ("at_T0_exactly", ts(0)),
                       ("T0_plus_31min", ts(31)),
                       ("T0_plus_120min", ts(120)),
                       ("far_future_2030", "2030-01-01T00:00:00Z")]:
        adm = led.admissible_at(cut)
        cutoffs[label] = {
            "cutoff_utc": cut,
            "n_entities_admissible": len(adm),
            "by_domain": {d: sum(1 for r in adm.values() if r["domain"] == d)
                          for d in sorted(DOMAINS)},
            "injury_designation_state": next(
                (r["payload"]["designation"] for r in adm.values()
                 if r["domain"] == "injury_designation"), None),
        }

    unproven = [r for r in records if r["cutoff_basis"] == CUTOFF_UNPROVEN]
    unproven_admitted_far_future = [
        r for r in led.admissible_at("2030-01-01T00:00:00Z").values()
        if r["cutoff_basis"] == CUTOFF_UNPROVEN]

    domains_seen = sorted({r["domain"] for r in records})

    receipt = {
        "schema": "player_program/live_capture_selftest_receipt/1",
        "node": "D11_LIVE_INFORMATION_CAPTURE",
        "epistemic_status": (
            "PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future "
            "features cutoff-provable. Creates no historical evidence and repairs no historical "
            "gap."
        ),
        "corpus": "SYNTHETIC. No real observation. Fictional teams, players, book and sources.",
        "generated_by": "selftest_capture.py",
        "deterministic_clock_base_utc": ts(0),
        "domain_table_sha256": sha256_text(
            json.dumps(domain_table(), sort_keys=True, separators=(",", ":"))),
        "counts": {
            "records_appended": len(records),
            "entities": len(per_entity_first_seen),
            "domains_declared": len(DOMAINS),
            "domains_exercised": len(domains_seen),
            "contract_criteria": len(CONTRACT_CRITERIA),
            "first_seen_records": sum(1 for r in records if r["change_kind"] == "first_seen"),
            "change_records": sum(1 for r in records if r["change_kind"] == "change"),
            "reaffirmation_records": sum(
                1 for r in records if r["change_kind"] == "reaffirmation"),
            "cutoff_provable_records": sum(
                1 for r in records if r["cutoff_basis"] == CUTOFF_PROVABLE),
            "cutoff_unproven_records": len(unproven),
        },
        "domains_exercised": domains_seen,
        "domains_declared": sorted(DOMAINS),
        "domains_not_exercised": sorted(set(DOMAINS) - set(domains_seen)),
        "append_only": {
            "every_write_extended_the_file_without_rewriting_it":
                all(append_only_prefix_checks),
            "n_writes_checked": len(append_only_prefix_checks),
        },
        "first_seen_immutability": {
            "entities_checked": len(per_entity_first_seen),
            "entities_with_more_than_one_first_seen_value":
                len(entities_with_multiple_first_seen),
            "offending": entities_with_multiple_first_seen,
        },
        "change_history_example": {
            "entity_key": injury_key,
            "n_records": len(injury_history),
            "trace": injury_trace,
            "all_prior_payloads_still_present": len(injury_history) == 3,
        },
        "rejections": rejections + [scope_case],
        "rejection_summary": {
            "n_cases": len(rejections) + 1,
            "n_matched_expected_code": sum(1 for r in rejections if r.get("matched"))
                                       + (1 if scope_case.get("matched") else 0),
            "n_that_modified_the_ledger": sum(
                1 for r in rejections if not r.get("ledger_unchanged", True)),
        },
        "replay_determinism": {
            "state_index_reproduced_byte_identically": replay_state_identical,
            "watermarks_reproduced_byte_identically": replay_wm_identical,
        },
        "integrity_verify": verify,
        "cutoff_admission": cutoffs,
        "cutoff_unproven_never_admitted": {
            "n_cutoff_unproven_records": len(unproven),
            "n_admitted_at_2030_cutoff": len(unproven_admitted_far_future),
        },
        "ledger_sha256": sha256_text(led.path.read_text(encoding="utf-8")),
        "ledger_bytes": led.path.stat().st_size,
    }

    checks = {
        "all_eight_domains_exercised": len(domains_seen) == 8 == len(DOMAINS),
        "append_only_held": all(append_only_prefix_checks),
        "first_seen_never_mutated": not entities_with_multiple_first_seen,
        "change_history_complete": len(injury_history) == 3,
        "every_rejection_raised_expected_code":
            receipt["rejection_summary"]["n_matched_expected_code"]
            == receipt["rejection_summary"]["n_cases"],
        "no_rejection_touched_the_ledger":
            receipt["rejection_summary"]["n_that_modified_the_ledger"] == 0,
        "replay_deterministic": replay_state_identical and replay_wm_identical,
        "integrity_clean": verify["ok"],
        "cutoff_unproven_never_admitted": len(unproven_admitted_far_future) == 0,
        "strict_inequality_at_cutoff": cutoffs["at_T0_exactly"]["n_entities_admissible"] == 0,
    }
    receipt["checks"] = checks
    receipt["all_checks_pass"] = all(checks.values())

    out = assert_in_scope(LANE_DIR / "SELFTEST_RECEIPT.json")
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def init_production_ledger() -> dict:
    """Create the (empty) production ledger with no bound source. It captures nothing today."""
    PROD_DIR.mkdir(parents=True, exist_ok=True)
    empty = CaptureLedger(PROD_DIR, SourceRegistry({}))
    if not empty.path.exists():
        assert_in_scope(empty.path).write_text("", encoding="utf-8")
    manifest = empty.write_derived()
    readme = assert_in_scope(PROD_DIR / "README.md")
    readme.write_text(
        "# Production capture ledger — EMPTY\n\n"
        "`observations.jsonl` is the authoritative append-only ledger for real live capture.\n"
        "It contains **zero records**. No source is bound: see `../SOURCE_BINDING.json`.\n\n"
        "Do not hand-edit this directory. `STATE_INDEX.json` and `WATERMARKS.json` are derived\n"
        "and are regenerated by replaying `observations.jsonl`.\n",
        encoding="utf-8")
    return manifest


def main() -> int:
    prod = init_production_ledger()
    receipt = run(fresh=True)
    print(f"production ledger: {prod['n_records']} records, {prod['n_entities']} entities")
    print(f"selftest ledger:   {receipt['counts']['records_appended']} records, "
          f"{receipt['counts']['entities']} entities, "
          f"{receipt['counts']['domains_exercised']}/8 domains")
    for k, v in receipt["checks"].items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    return 0 if receipt["all_checks_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
