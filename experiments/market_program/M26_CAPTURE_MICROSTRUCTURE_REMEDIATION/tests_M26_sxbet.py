#!/usr/bin/env python3
"""
Regression tests for M26_CAPTURE_MICROSTRUCTURE_REMEDIATION defect 3,
exchange-capture half (capture_sxbet.py, PROGRAM worktree -- this file lives
in the same worktree, imported directly by relative path, no cross-worktree
sys.path needed).

Run: python tests_M26_sxbet.py

Covers: `compute_roster_transitions` (unit) and a full `run_cycle` sequence
across three cycles with a real (non-mocked) StateStore, demonstrating that
a market vanishing from /markets/active and later reappearing with
byte-identical content -- which build_envelope's dedup would otherwise
render completely invisible -- now produces witnessed roster_events rows on
both edges of the transition.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "EXCHANGE_CAPTURE" / "sxbet"))

import capture_sxbet as sx  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILURES.append(name)


def test_compute_roster_transitions_unit():
    tmp = Path(tempfile.mkdtemp(prefix="m26_sxbet_unit_"))
    try:
        state = sx.StateStore(path=str(tmp / "state.json"))

        ev1 = sx.compute_roster_transitions(state, {"A", "B", "C"}, "t1", 300.0, "cycle1")
        check("sxbet_first_cycle_no_transitions", ev1 == [], f"{ev1}")
        check("sxbet_roster_seeded_active", state.data["roster"] == {"A": "active", "B": "active", "C": "active"})

        # B vanishes.
        ev2 = sx.compute_roster_transitions(state, {"A", "C"}, "t2", 300.0, "cycle2")
        check("sxbet_vanish_detected", len(ev2) == 1 and ev2[0]["content"]["marketHash"] == "B", ev2)
        if ev2:
            check("sxbet_vanish_status_field", ev2[0]["content"]["roster_status"] == "vanished", ev2[0])
            check("sxbet_vanish_is_order_false", ev2[0]["is_order"] is False, ev2[0])
            check("sxbet_vanish_provenance", ev2[0]["provenance"] == sx.PROVENANCE, ev2[0])
            check("sxbet_vanish_note_present", "WITNESSED_ABSENCE" in ev2[0]["vendor_latency_note"], ev2[0])
            check("sxbet_vanish_status_never_suspended", ev2[0]["content"]["roster_status"] != "suspended",
                  "the roster_status FIELD must never fabricate a vendor suspension claim "
                  "/markets/active cannot support (the prose may still discuss the "
                  "possibility while declining to assert it)")
        check("sxbet_roster_marks_B_vanished", state.data["roster"]["B"] == "vanished")

        # B still absent -- must not re-fire.
        ev3 = sx.compute_roster_transitions(state, {"A", "C"}, "t3", 300.0, "cycle3")
        check("sxbet_no_repeat_vanish_while_absent", ev3 == [], f"{ev3}")

        # B reappears with (by definition, at this layer) identical content
        # -- compute_roster_transitions only sees the hash set, so this
        # models exactly the case build_envelope's dedup would otherwise
        # swallow silently.
        ev4 = sx.compute_roster_transitions(state, {"A", "B", "C"}, "t4", 300.0, "cycle4")
        check("sxbet_reappear_detected", len(ev4) == 1 and ev4[0]["content"]["marketHash"] == "B", ev4)
        if ev4:
            check("sxbet_reappear_status_field", ev4[0]["content"]["roster_status"] == "reappeared", ev4[0])
            check("sxbet_reappear_note_present", "WITNESSED_RETURN" in ev4[0]["vendor_latency_note"], ev4[0])
        check("sxbet_roster_marks_B_active_again", state.data["roster"]["B"] == "active")

        # New market D appears for the first time -- not a "reappearance"
        # (never seen before), so no event, just silently added to roster
        # (its regular `markets` row already represents first-sight).
        ev5 = sx.compute_roster_transitions(state, {"A", "B", "C", "D"}, "t5", 300.0, "cycle5")
        check("sxbet_brand_new_market_no_event", ev5 == [], f"{ev5}")
        check("sxbet_new_market_now_tracked_active", state.data["roster"]["D"] == "active")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class FakeClient:
    """Stands in for SxBetClient -- no network, deterministic sequenced
    /markets/active responses so a real, unmocked `run_cycle` can be driven
    through a vanish-then-return sequence."""

    def __init__(self, market_snapshots):
        self._snapshots = list(market_snapshots)
        self._i = 0
        self.poll_log = []

    def get_active_markets(self, league_id=None, cycle_id=""):
        markets = self._snapshots[min(self._i, len(self._snapshots) - 1)]
        self._i += 1
        log_row = {"ok": True, "finished_ts": sx.now_iso(), "n_returned": len(markets)}
        self.poll_log.append(log_row)
        return [dict(m) for m in markets], log_row

    def get_orders(self, market_hashes, cycle_id=""):
        return [], {"ok": True, "finished_ts": sx.now_iso(), "n_returned": 0}

    def get_trades(self, market_hashes, cycle_id=""):
        return [], {"ok": True, "finished_ts": sx.now_iso(), "n_returned": 0}


MARKET_M1 = {"marketHash": "m1", "sportXeventId": "g1", "type": 28, "gameTime": "2026-08-07T20:00:00", "status": "ACTIVE"}
MARKET_M2 = {"marketHash": "m2", "sportXeventId": "g1", "type": 226, "gameTime": "2026-08-07T20:00:00", "status": "ACTIVE"}


def test_run_cycle_end_to_end_vanish_and_return():
    tmp = Path(tempfile.mkdtemp(prefix="m26_sxbet_e2e_"))
    try:
        data_dir = str(tmp / "data")
        state = sx.StateStore.load(str(tmp / "state.json"))
        # Cycle 1: both markets present. Cycle 2: m2 vanishes (byte-identical
        # m1 stays). Cycle 3: m2 reappears with IDENTICAL content to cycle 1
        # -- build_envelope's own content-hash dedup would normally swallow
        # this reappearance in the `markets` table entirely.
        client = FakeClient([[MARKET_M1, MARKET_M2], [MARKET_M1], [MARKET_M1, MARKET_M2]])

        stats1 = sx.run_cycle(client, state, data_dir, cycle_id="c1", poll_interval_seconds=300.0)
        state.save()
        stats2 = sx.run_cycle(client, state, data_dir, cycle_id="c2", poll_interval_seconds=300.0)
        state.save()
        stats3 = sx.run_cycle(client, state, data_dir, cycle_id="c3", poll_interval_seconds=300.0)
        state.save()

        check("sxbet_e2e_cycle1_no_roster_events", stats1["rows_written"]["roster_events"] == 0, stats1)
        check("sxbet_e2e_cycle2_vanish_event", stats2["rows_written"]["roster_events"] == 1, stats2)
        check("sxbet_e2e_cycle3_reappear_event", stats3["rows_written"]["roster_events"] == 1, stats3)

        # m2's regular `markets` row on cycle 3 SHOULD be deduped (identical
        # content to cycle 1) -- confirming the roster_events table is doing
        # real, additional work the existing dedup layer cannot do.
        check("sxbet_e2e_cycle3_markets_row_deduped", stats3["rows_deduped"]["markets"] >= 1, stats3)

        roster_events_path = Path(data_dir) / "roster_events.jsonl"
        check("sxbet_e2e_roster_events_file_exists", roster_events_path.exists())
        events = []
        if roster_events_path.exists():
            with open(roster_events_path, encoding="utf-8") as f:
                events = [json.loads(line) for line in f if line.strip()]
        check("sxbet_e2e_two_events_total", len(events) == 2, f"{len(events)} events: {events}")
        statuses = [e["content"]["roster_status"] for e in events]
        check("sxbet_e2e_vanish_then_reappear_order", statuses == ["vanished", "reappeared"], statuses)
        check("sxbet_e2e_both_events_for_m2", all(e["content"]["marketHash"] == "m2" for e in events), events)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


ALL_TESTS = [
    test_compute_roster_transitions_unit,
    test_run_cycle_end_to_end_vanish_and_return,
]

if __name__ == "__main__":
    print(f"Testing production code at: {sx.__file__}")
    print("-" * 70)
    for t in ALL_TESTS:
        print(f"\n-- {t.__name__} --")
        t()
    print("-" * 70)
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        sys.exit(1)
    print(f"All {len(ALL_TESTS)} test functions passed.")
    sys.exit(0)
