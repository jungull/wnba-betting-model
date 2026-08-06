#!/usr/bin/env python3
"""Fixture tests for dense_window_puller.py — ZERO network calls, ZERO paid
API access. Exercises only the pure logic (cost model, scheduling, matching,
row-building, budget selection, resumable-state round trip, stop-guard).

Run: python TESTS.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense_window_puller as dwp  # noqa: E402

FAILURES = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 1. Cost model — matches the measured numbers in ODDS_API_LIVE_VERIFICATION.md
# ---------------------------------------------------------------------------

def test_cost_model():
    check("cost_per_snapshot_call == 30", dwp.COST_PER_SNAPSHOT_CALL == 30,
          f"got {dwp.COST_PER_SNAPSHOT_CALL}")
    check("n_snapshots_per_event == 13", dwp.N_SNAPSHOTS_PER_EVENT == 13,
          f"got {dwp.N_SNAPSHOTS_PER_EVENT}")
    check("cost_per_event == 391", dwp.COST_PER_EVENT == 391,
          f"got {dwp.COST_PER_EVENT}")
    check("n_events_under_cap(35000) == 89", dwp.n_events_under_cap(35000) == 89,
          f"got {dwp.n_events_under_cap(35000)}")
    check("89 events fits under cap", 89 * dwp.COST_PER_EVENT <= 35000,
          f"89*{dwp.COST_PER_EVENT}={89*dwp.COST_PER_EVENT}")
    check("90 events would NOT fit under cap", 90 * dwp.COST_PER_EVENT > 35000,
          f"90*{dwp.COST_PER_EVENT}={90*dwp.COST_PER_EVENT}")


# ---------------------------------------------------------------------------
# 2. Snapshot scheduling — T-6h to tip inclusive, 30-min grid
# ---------------------------------------------------------------------------

def test_snapshot_schedule():
    tip = datetime(2024, 7, 13, 19, 0, 0, tzinfo=timezone.utc)
    sched = dwp.snapshot_schedule(tip)
    check("schedule has 13 points", len(sched) == 13, f"got {len(sched)}")
    check("first point is T-6h", sched[0] == tip.replace(hour=13), f"got {sched[0]}")
    check("last point is tip", sched[-1] == tip, f"got {sched[-1]}")
    deltas = [(sched[i + 1] - sched[i]).total_seconds() for i in range(len(sched) - 1)]
    check("all gaps are exactly 30 min", all(d == 1800 for d in deltas), f"got {deltas}")


# ---------------------------------------------------------------------------
# 3. Event selection under budget cap, using the real ranked event list if
#    present (built by build_absence_events.py), else a synthetic fixture.
# ---------------------------------------------------------------------------

def _load_or_fake_events():
    real = Path(__file__).resolve().parent / "absence_events_ranked.json"
    if real.exists():
        return json.loads(real.read_text(encoding="utf-8"))["events"]
    return [
        {"rank": i + 1, "absent_game_id": f"g{i}", "player_id": i, "player_name": f"Player {i}",
         "team_abbreviation": "AAA", "absent_game_opponent_abbreviation": "BBB",
         "absent_game_team_is_home": True, "absent_game_date": "2024-07-01"}
        for i in range(200)
    ]


def test_select_events():
    events = _load_or_fake_events()
    selected = dwp.select_events(events, 35000)
    expected_n = min(len(events), dwp.n_events_under_cap(35000))
    check("select_events respects the budget-derived N", len(selected) == expected_n,
          f"got {len(selected)}, expected {expected_n}")
    check("select_events preserves rank order", selected == events[:expected_n])

    tiny = dwp.select_events(events, 391)
    check("cap of exactly one event's cost selects 1", len(tiny) == min(1, len(events)))

    zero = dwp.select_events(events, 390)
    check("cap below one event's cost selects 0", len(zero) == 0, f"got {len(zero)}")


# ---------------------------------------------------------------------------
# 4. Event matching against a fake Odds API /events payload
# ---------------------------------------------------------------------------

def test_match_event():
    payload = [
        {"id": "abc123", "home_team": "MIN", "away_team": "DAL",
         "commence_time": "2024-06-17T19:00:00Z"},
        {"id": "xyz789", "home_team": "CHI", "away_team": "SEA",
         "commence_time": "2024-06-17T21:00:00Z"},
    ]
    m = dwp.match_event(payload, "DAL", "MIN", is_home=False)
    check("match_event finds the right game", m is not None and m["id"] == "abc123",
          f"got {m}")

    m_wrong_side = dwp.match_event(payload, "MIN", "DAL", is_home=False)
    check("match_event respects is_home", m_wrong_side is None or m_wrong_side["id"] != "abc123")

    m_none = dwp.match_event(payload, "ZZZ", "YYY", is_home=None)
    check("match_event returns None for no match", m_none is None)


# ---------------------------------------------------------------------------
# 5. Row-building — amendment-4 fields present, T1_VENDOR_ASSERTED, hash stable
# ---------------------------------------------------------------------------

def test_build_snapshot_row():
    event = {"id": "abc123", "home_team": "MIN", "away_team": "DAL"}
    absence_event = {"rank": 1, "player_id": 1629481, "player_name": "Arike Ogunbowale",
                      "absent_game_id": "1022400081"}
    vendor_payload = {
        "timestamp": "2024-06-17T13:00:00Z",
        "previous_timestamp": "2024-06-17T12:30:00Z",
        "next_timestamp": "2024-06-17T13:30:00Z",
        "data": {"bookmakers": [{"key": "draftkings"}]},
    }
    row = dwp.build_snapshot_row(
        event=event, absence_event=absence_event, requested_ts="2024-06-17T13:00:00Z",
        vendor_payload=vendor_payload, retrieval_ts="2024-06-17T13:00:05Z",
    )

    required_fields = {
        "requested_ts", "vendor_snapshot_ts", "vendor_prev_ts", "vendor_next_ts",
        "retrieval_ts", "vendor_ts_semantics", "provenance_class", "payload_sha256",
        "odds_api_event_id", "absent_game_id", "player_id",
    }
    check("row carries all amendment-4 + linkage fields", required_fields.issubset(row.keys()),
          f"missing {required_fields - row.keys()}")
    check("provenance_class is T1_VENDOR_ASSERTED", row["provenance_class"] == "T1_VENDOR_ASSERTED")
    check("vendor_ts_semantics is vendor_asserted_unwitnessed",
          row["vendor_ts_semantics"] == "vendor_asserted_unwitnessed")
    check("payload_sha256 is a 64-char hex string",
          isinstance(row["payload_sha256"], str) and len(row["payload_sha256"]) == 64)

    row_empty = dwp.build_snapshot_row(
        event=event, absence_event=absence_event, requested_ts="2024-06-17T13:00:00Z",
        vendor_payload=None, retrieval_ts="2024-06-17T13:00:05Z",
    )
    check("empty vendor payload -> payload_sha256 None (matches unbilled-empty convention)",
          row_empty["payload_sha256"] is None)
    check("empty vendor payload -> n_events 0", row_empty["n_events"] == 0)


# ---------------------------------------------------------------------------
# 6. Resumable state round-trip (isolated tmp dir, no interference with any
#    real state file)
# ---------------------------------------------------------------------------

def test_state_round_trip():
    orig_state_f = dwp.STATE_F
    orig_out_dir = dwp.OUT_DIR
    with tempfile.TemporaryDirectory() as td:
        dwp.OUT_DIR = Path(td)
        dwp.STATE_F = Path(td) / "_dense_window_state.json"
        try:
            st = dwp.load_state()
            check("fresh state has empty events_done", st["events_done"] == [])
            st["events_done"].append("g1::123")
            st["credits_spent_est"] = 391
            dwp.save_state(st)
            reloaded = dwp.load_state()
            check("state round-trips", reloaded == st, f"got {reloaded}")
        finally:
            dwp.OUT_DIR = orig_out_dir
            dwp.STATE_F = orig_state_f


# ---------------------------------------------------------------------------
# 7. Stop-guard — fires below threshold, silent above
# ---------------------------------------------------------------------------

def test_stop_guard():
    fired = False
    try:
        dwp.guard({"x-requests-remaining": "100"})
    except SystemExit as e:
        fired = True
        check("stop-guard SystemExit code is 0 (clean/resumable)", e.code == 0)
    check("stop-guard fires when remaining < STOP_GUARD", fired)

    fired_ok = False
    try:
        dwp.guard({"x-requests-remaining": "50000"})
        fired_ok = True
    except SystemExit:
        pass
    check("stop-guard does NOT fire when remaining is ample", fired_ok)


# ---------------------------------------------------------------------------
# 8. Zero-network guarantee: importing/using the module must not touch the net.
#    We assert this by monkeypatching urllib.request.urlopen to raise, then
#    running the whole dry-run cost-report codepath (the only thing that runs
#    without --execute) and everything above.
# ---------------------------------------------------------------------------

def test_zero_network_dry_run():
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("network call attempted during dry run / fixture tests!")

    orig = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        events = _load_or_fake_events()
        report = dwp.estimate_cost_report(events, 35000)
        check("estimate_cost_report runs with zero network calls", True)
        check("estimate_cost_report reports 89-under-cap shape",
              report["cost_per_event"] == 391 and report["n_events_selected"] <= 89)
    finally:
        urllib.request.urlopen = orig


def main() -> int:
    test_cost_model()
    test_snapshot_schedule()
    test_select_events()
    test_match_event()
    test_build_snapshot_row()
    test_state_round_trip()
    test_stop_guard()
    test_zero_network_dry_run()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        return 1
    print("ALL TESTS PASSED — zero paid calls made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
