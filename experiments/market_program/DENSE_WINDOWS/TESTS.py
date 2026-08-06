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
from datetime import datetime, timedelta, timezone
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
# 1. Cost model — recomputed for the D033 event-adaptive grid. The scenario
#    constants are themselves computed from adaptive_snapshot_schedule() at
#    import time (see dense_window_puller.py), so these checks pin the
#    numbers reported in the module docstring, not re-derive them independently.
# ---------------------------------------------------------------------------

def test_cost_model():
    check("cost_per_snapshot_call == 30 (unchanged by the redesign)",
          dwp.COST_PER_SNAPSHOT_CALL == 30, f"got {dwp.COST_PER_SNAPSHOT_CALL}")

    check("UNKNOWN_TS fallback: 49 snapshots / 1471 credits",
          dwp.n_snapshots_for_event_offset(None) == 49 and dwp.COST_PER_EVENT_UNKNOWN_TS == 1471,
          f"got n={dwp.n_snapshots_for_event_offset(None)} cost={dwp.COST_PER_EVENT_UNKNOWN_TS}")
    check("KNOWN_TS typical (T-2h): 35 snapshots / 1051 credits",
          dwp.COST_PER_EVENT_KNOWN_TYPICAL == 1051, f"got {dwp.COST_PER_EVENT_KNOWN_TYPICAL}")
    check("KNOWN_TS worst (T-24h, window edge): 64 snapshots / 1921 credits",
          dwp.COST_PER_EVENT_KNOWN_WORST == 1921, f"got {dwp.COST_PER_EVENT_KNOWN_WORST}")
    check("KNOWN_TS best (T-15m): 19 snapshots / 571 credits",
          dwp.COST_PER_EVENT_KNOWN_BEST == 571, f"got {dwp.COST_PER_EVENT_KNOWN_BEST}")

    check("planning default is the UNKNOWN_TS (fallback) cost — conservative, catalog assumed partial/absent",
          dwp.COST_PER_EVENT_PLANNING_DEFAULT == dwp.COST_PER_EVENT_UNKNOWN_TS)

    # The headline number this redesign reports: pricier per-event cost under
    # the adaptive grid pulls N well below the old uniform grid's 89.
    check("n_events_under_cap(35000) == 23 (new N, under the old grid's 89)",
          dwp.n_events_under_cap(35000) == 23, f"got {dwp.n_events_under_cap(35000)}")
    check("23 events fits under cap",
          23 * dwp.COST_PER_EVENT_PLANNING_DEFAULT <= 35000,
          f"23*{dwp.COST_PER_EVENT_PLANNING_DEFAULT}={23 * dwp.COST_PER_EVENT_PLANNING_DEFAULT}")
    check("24 events would NOT fit under cap",
          24 * dwp.COST_PER_EVENT_PLANNING_DEFAULT > 35000,
          f"24*{dwp.COST_PER_EVENT_PLANNING_DEFAULT}={24 * dwp.COST_PER_EVENT_PLANNING_DEFAULT}")
    check("new N (23) is strictly under the old grid's N (89)", dwp.n_events_under_cap(35000) < 89)


# ---------------------------------------------------------------------------
# 2. Snapshot scheduling — D033 event-adaptive grid
# ---------------------------------------------------------------------------

def test_snapshot_schedule_fallback():
    """Unknown event ts: uniform 30-min grid over the full 24h before tip."""
    tip = datetime(2024, 7, 13, 19, 0, 0, tzinfo=timezone.utc)
    sched = dwp.adaptive_snapshot_schedule(tip)
    check("fallback schedule has 49 points", len(sched) == 49, f"got {len(sched)}")
    check("fallback first point is T-24h", sched[0] == tip - timedelta(hours=24), f"got {sched[0]}")
    check("fallback last point is tip", sched[-1] == tip, f"got {sched[-1]}")
    deltas = [(sched[i + 1] - sched[i]).total_seconds() for i in range(len(sched) - 1)]
    check("fallback gaps are exactly 30 min", all(d == 1800 for d in deltas), f"got {deltas}")

    # back-compat wrapper
    check("snapshot_schedule() wrapper matches the fallback grid",
          dwp.snapshot_schedule(tip) == sched)


def test_snapshot_schedule_known_event():
    """Known event ts: baselines + 5-min dense window + medium grid + final sprint."""
    tip = datetime(2024, 7, 13, 19, 0, 0, tzinfo=timezone.utc)
    event_ts = tip - timedelta(hours=2)  # exact-instant event, 2h before tip
    sched = dwp.adaptive_snapshot_schedule(tip, event_ts, event_ts)

    check("known-event schedule has 35 points (matches KNOWN_TS_TYPICAL cost scenario)",
          len(sched) == 35, f"got {len(sched)}")
    check("schedule is sorted and within [tip-24h, tip]",
          sched == sorted(sched) and sched[0] >= tip - timedelta(hours=24) and sched[-1] <= tip)
    check("last point is tip", sched[-1] == tip, f"got {sched[-1]}")

    # baselines present
    for h in (24, 12, 6):
        check(f"baseline T-{h}h present", (tip - timedelta(hours=h)) in sched)

    # dense window (event +/- 60min) at 5-min resolution
    dense_pts = [t for t in sched if event_ts - timedelta(minutes=60) <= t <= event_ts + timedelta(minutes=60)]
    check("dense window has 25 points (2h @ 5min inclusive)", len(dense_pts) == 25, f"got {len(dense_pts)}")

    # final 30-minute sprint at 5-min resolution
    final_pts = [t for t in sched if tip - timedelta(minutes=30) <= t <= tip]
    check("final sprint has 7 points (30min @ 5min inclusive)", len(final_pts) == 7, f"got {len(final_pts)}")


def test_snapshot_schedule_clipped_to_window():
    """Event bounds at/near the 24h window edge never produce points before
    tip-24h or after tip, even with dense-window padding that would otherwise
    reach outside the window."""
    tip = datetime(2024, 7, 13, 19, 0, 0, tzinfo=timezone.utc)
    event_ts = tip - timedelta(hours=24)  # right at the window floor
    sched = dwp.adaptive_snapshot_schedule(tip, event_ts, event_ts)
    check("worst-case known-event schedule has 64 points", len(sched) == 64, f"got {len(sched)}")
    check("no point earlier than tip-24h", all(t >= tip - timedelta(hours=24) for t in sched))
    check("no point later than tip", all(t <= tip for t in sched))

    # event bounds entirely before the window (pathological/garbage catalog
    # row) must not crash and must still respect the window
    far_event = tip - timedelta(hours=100)
    sched2 = dwp.adaptive_snapshot_schedule(tip, far_event, far_event)
    check("far-past event ts does not crash and stays in-window",
          all(tip - timedelta(hours=24) <= t <= tip for t in sched2))


def test_estimate_event_cost_and_selection():
    """estimate_event_cost / select_events are catalog-aware and budget-safe."""
    tip_day = "2024-07-13"
    events = [
        {"rank": 1, "player_id": 1, "player_name": "A", "absent_game_id": "g1",
         "absent_game_date": tip_day, "team_abbreviation": "AAA",
         "absent_game_opponent_abbreviation": "BBB", "absent_game_team_is_home": True},
        {"rank": 2, "player_id": 2, "player_name": "B", "absent_game_id": "g2",
         "absent_game_date": tip_day, "team_abbreviation": "AAA",
         "absent_game_opponent_abbreviation": "BBB", "absent_game_team_is_home": True},
    ]
    # no catalog -> both fall back, uniform 1471 each
    no_catalog_selected = dwp.select_events(events, hard_budget_cap=1471, catalog_index=None)
    check("no catalog: budget for exactly 1 event selects 1", len(no_catalog_selected) == 1,
          f"got {len(no_catalog_selected)}")

    no_catalog_selected2 = dwp.select_events(events, hard_budget_cap=1470, catalog_index=None)
    check("no catalog: budget one credit short of 1 event selects 0",
          len(no_catalog_selected2) == 0, f"got {len(no_catalog_selected2)}")

    catalog_records = [
        {"player_id": 1, "game_id": "g1", "ts_lower": "2024-07-13T17:00:00Z",
         "ts_upper": "2024-07-13T17:00:00Z", "status_transition": "OUT", "confidence": "high"},
    ]
    idx = dwp.build_catalog_index(catalog_records)
    check("build_catalog_index indexes by (player_id, game_id)", (1, "g1") in idx)
    bounds = dwp.catalog_event_ts_bounds(events[0], idx)
    check("catalog_event_ts_bounds resolves a hit", bounds is not None)
    miss = dwp.catalog_event_ts_bounds(events[1], idx)
    check("catalog_event_ts_bounds returns None on a miss", miss is None)

    cost_hit = dwp.estimate_event_cost(events[0], idx)
    cost_miss = dwp.estimate_event_cost(events[1], idx)
    check("catalog hit and catalog miss produce different cost estimates",
          cost_hit != cost_miss, f"hit={cost_hit} miss={cost_miss}")
    check("catalog miss falls back to the UNKNOWN_TS cost",
          cost_miss == dwp.COST_PER_EVENT_UNKNOWN_TS, f"got {cost_miss}")


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
    # No catalog supplied -> every event uses the UNKNOWN_TS fallback cost;
    # select_events is a greedy budget walk over rank order, which reduces to
    # the same floor-division count as before when cost-per-event is uniform.
    selected = dwp.select_events(events, 35000)
    expected_n = min(len(events), dwp.n_events_under_cap(35000))
    check("select_events respects the budget-derived N", len(selected) == expected_n,
          f"got {len(selected)}, expected {expected_n}")
    check("select_events preserves rank order", selected == events[:expected_n])

    tiny = dwp.select_events(events, dwp.COST_PER_EVENT_UNKNOWN_TS)
    check("cap of exactly one event's cost selects 1", len(tiny) == min(1, len(events)))

    zero = dwp.select_events(events, dwp.COST_PER_EVENT_UNKNOWN_TS - 1)
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
        check("estimate_cost_report reports the new (<=23, catalog-absent) shape",
              report["planning_default_cost_per_event"] == 1471 and report["n_events_selected"] <= 23)
        check("estimate_cost_report notes no catalog supplied",
              report["catalog_coverage"] == "no event catalog supplied — all events use the fallback grid")
    finally:
        urllib.request.urlopen = orig


def main() -> int:
    test_cost_model()
    test_snapshot_schedule_fallback()
    test_snapshot_schedule_known_event()
    test_snapshot_schedule_clipped_to_window()
    test_estimate_event_cost_and_selection()
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
