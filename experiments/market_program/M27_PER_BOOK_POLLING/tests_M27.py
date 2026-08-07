#!/usr/bin/env python3
"""
Regression / behavior tests for M27_PER_BOOK_POLLING.

Run: python tests_M27.py
(stdlib only. Imports the REAL production capture code from the DATA
worktree root (C:/Users/jgallagher/wnba-betting-model) via sys.path
insertion -- same discipline as tests_M26.py. HTTP layer monkeypatched;
no network call, no vendor credit spent by running this file.)

Two things this file must prove, per the M27 authorization:
  1. Each book in the declared per-book subset now carries an INDEPENDENT
     witnessed retrieval_ts (test_perbook_* group) -- the actual deliverable.
  2. M26's anti-faking test
     (test_defect2_within_one_payload_books_still_share_one_timestamp_documented)
     still passes UNCHANGED against the current production code -- proven
     here by importing and re-running it directly from tests_M26.py rather
     than re-implementing it (a copy could silently drift from the real
     test; running the original guarantees this isn't a stale echo).
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model")
sys.path.insert(0, str(DATA_ROOT))

import market_capture_config as config       # noqa: E402
import market_capture_run as run             # noqa: E402
import market_per_book_scheduler as per_book  # noqa: E402
import market_snapshot_writer as writer      # noqa: E402

M26_DIR = (Path(__file__).resolve().parent.parent
           / "M26_CAPTURE_MICROSTRUCTURE_REMEDIATION")
sys.path.insert(0, str(M26_DIR))

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILURES.append(name)


class FakeResp:
    def __init__(self, status_code=200, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


GAME = {"game_id": "1022600230", "home": "Las Vegas Aces", "away": "New York Liberty",
        "tip": datetime(2026, 8, 7, 23, 0, 0, tzinfo=timezone.utc)}
VENDOR_EVENT_ID = "58beff9061f15ff3f416542cb51f4751"
EVENTS_BY_TEAMS = {("Las Vegas Aces", "New York Liberty"): VENDOR_EVENT_ID}


def _event_json_for_book(event_id, book, price_offset=0):
    return {
        "id": event_id,
        "bookmakers": [{"key": book, "markets": [
            {"key": "player_points", "last_update": "2026-08-07T22:00:00Z", "outcomes": [
                {"description": "A'ja Wilson", "name": "Over", "point": 22.5,
                 "price": -110 + price_offset},
                {"description": "A'ja Wilson", "name": "Under", "point": 22.5,
                 "price": -110 - price_offset},
            ]},
        ]}],
    }


def _fake_fetch_props_per_book_distinct_ts(call_log):
    """Simulates what the REAL fetch_event_props_snapshot does when called
    with a distinct `bookmakers=` value each time: a genuinely separate
    HTTP round trip -> a genuinely separate wall-clock
    `response_received_ts`. In production this separation comes from
    time.monotonic()/datetime.now() at each real HTTP response; here it is
    driven by a monotonically increasing fake clock so the test does not
    depend on real wall-clock timing jitter."""
    counter = {"n": 0}

    def _fake(session, key, event_id, markets=None, timeout=30, bookmakers=None):
        counter["n"] += 1
        call_log.append(bookmakers)
        # distinct, strictly increasing timestamp per call -- models the
        # real behavior of N sequential, independently-timed HTTP calls
        ts = (datetime(2026, 8, 7, 22, 0, 0, tzinfo=timezone.utc)
              + timedelta(milliseconds=100 * counter["n"])).isoformat()
        resp = FakeResp(200, {"x-requests-used": str(3 + counter["n"]),
                              "x-requests-remaining": str(99990 - counter["n"]),
                              "x-requests-last": "4",
                              "Date": "Fri, 07 Aug 2026 22:00:00 GMT"})
        event_json = _event_json_for_book(event_id, bookmakers or "bundled",
                                          price_offset=counter["n"])
        raw = json.dumps(event_json).encode("utf-8")
        timing = {
            "request_sent_ts": ts, "response_received_ts": ts,
            "rtt_seconds": 0.05, "vendor_http_date": resp.headers["Date"],
            "vendor_http_date_parsed_utc": "2026-08-07T22:00:00+00:00",
            "clock_skew_estimate_seconds": 0.0,
            "measurement_caveat": "test fixture",
        }
        return event_json, raw, resp, timing
    return _fake


def _patched_props(fetch_props):
    class _Ctx:
        def __enter__(self):
            self.orig = writer.fetch_event_props_snapshot
            writer.fetch_event_props_snapshot = fetch_props
            return self

        def __exit__(self, *a):
            writer.fetch_event_props_snapshot = self.orig
            return False
    return _Ctx()


# ===================================================================== #
# Deliverable 2, part 1: each declared book gets an INDEPENDENT
# witnessed retrieval_ts.
# ===================================================================== #
def test_perbook_declared_subset_is_three_books():
    check("perbook_config_declares_exactly_three_books",
          len(config.PER_BOOK_DECLARED_BOOKS) == 3,
          f"got {config.PER_BOOK_DECLARED_BOOKS}")
    check("perbook_config_books_are_the_measured_densest_three",
          set(config.PER_BOOK_DECLARED_BOOKS) == {"betrivers", "draftkings", "fanduel"},
          f"got {config.PER_BOOK_DECLARED_BOOKS}")


def test_perbook_calls_use_bookmakers_param_not_regions():
    """Confirms the real fetch_event_props_snapshot, when given
    bookmakers=X, sends `bookmakers` in the request params and does NOT
    send `regions` -- i.e. it actually scopes the vendor call to one book,
    not a cosmetic no-op."""
    class RecordingSession:
        def __init__(self):
            self.calls = []

        def get(self, url, params=None, timeout=None):
            self.calls.append(params)
            class R:
                status_code = 200
                headers = {"Date": "Fri, 07 Aug 2026 22:00:00 GMT"}
                content = b'{"id": "e1", "bookmakers": []}'

                def raise_for_status(self):
                    pass

                def json(self):
                    return {"id": "e1", "bookmakers": []}
            return R()

    sess = RecordingSession()
    writer.fetch_event_props_snapshot(sess, "FAKEKEY", "e1", bookmakers="draftkings")
    params = sess.calls[0]
    check("perbook_bookmakers_param_sent", params.get("bookmakers") == "draftkings", params)
    check("perbook_regions_param_absent_when_bookmakers_given", "regions" not in params, params)

    sess2 = RecordingSession()
    writer.fetch_event_props_snapshot(sess2, "FAKEKEY", "e1")
    params2 = sess2.calls[0]
    check("perbook_default_unchanged_regions_still_used", params2.get("regions") == "us", params2)
    check("perbook_default_unchanged_no_bookmakers_param", "bookmakers" not in params2, params2)


def test_perbook_end_to_end_independent_retrieval_ts():
    tmp = Path(tempfile.mkdtemp(prefix="m27_perbook_"))
    call_log = []
    try:
        with _patched_props(_fake_fetch_props_per_book_distinct_ts(call_log)):
            n_written, n_rejected, n_calls = run._poll_per_book(
                session=None, key="test-key-not-real", game=GAME,
                event_id=VENDOR_EVENT_ID, out_dir=tmp, now=datetime.now(timezone.utc))

        check("perbook_three_calls_made", n_calls == 3, f"got {n_calls}")
        check("perbook_call_order_matches_declared_books",
              call_log == config.PER_BOOK_DECLARED_BOOKS, call_log)
        check("perbook_rows_written", n_written > 0, f"n_written={n_written}")
        check("perbook_no_rejected_rows", n_rejected == 0, f"n_rejected={n_rejected}")

        with open(tmp / writer.SNAPSHOTS_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_book_ts = {}
        for r in rows:
            by_book_ts.setdefault(r["book"], set()).add(r["retrieval_ts"])

        check("perbook_all_three_declared_books_present",
              set(by_book_ts) == set(config.PER_BOOK_DECLARED_BOOKS),
              f"books seen: {set(by_book_ts)}")

        all_ts = set()
        for book, ts_set in by_book_ts.items():
            check(f"perbook_{book}_single_ts_within_its_own_call", len(ts_set) == 1, ts_set)
            all_ts |= ts_set
        # THE deliverable: the three books' retrieval_ts values are pairwise
        # distinct -- each book's poll is a genuinely separate, independently
        # witnessed HTTP call, not a shared batch timestamp.
        check("perbook_retrieval_ts_pairwise_distinct_across_books",
              len(all_ts) == len(config.PER_BOOK_DECLARED_BOOKS),
              f"expected {len(config.PER_BOOK_DECLARED_BOOKS)} distinct retrieval_ts values, "
              f"got {len(all_ts)}: {all_ts}")

        ordered_ts = sorted(all_ts)
        check("perbook_retrieval_ts_values_strictly_increasing",
              ordered_ts == sorted(set(ordered_ts)) and len(ordered_ts) > 1, ordered_ts)

        poll_log_path = tmp / writer.POLL_LOG_CSV
        with open(poll_log_path, newline="", encoding="utf-8") as f:
            log_rows = list(csv.DictReader(f))
        per_book_rows = [r for r in log_rows if r["obligation_type"] == "per_book"]
        check("perbook_poll_log_has_one_row_per_book", len(per_book_rows) == 3,
              f"{len(per_book_rows)} rows")
        check("perbook_poll_log_labels_identify_book",
              {r["label"] for r in per_book_rows}
              == {f"PER_BOOK:{b}" for b in config.PER_BOOK_DECLARED_BOOKS},
              {r["label"] for r in per_book_rows})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_perbook_roster_key_isolated_from_bundled_props_roster():
    """A per-book poll's roster bookkeeping must use its own roster_key
    (game_id:props:perbook:<book>), never the bundled props roster_key
    (game_id:props) -- otherwise a per-book call (which by construction only
    ever sees ONE book) would falsely mark every OTHER book's chains as
    vanished the moment per-book polling starts."""
    tmp = Path(tempfile.mkdtemp(prefix="m27_roster_"))
    call_log = []
    try:
        with _patched_props(_fake_fetch_props_per_book_distinct_ts(call_log)):
            run._poll_per_book(session=None, key="k", game=GAME, event_id=VENDOR_EVENT_ID,
                              out_dir=tmp, now=datetime.now(timezone.utc))
        roster = json.loads((tmp / writer.ROSTER_INDEX_JSON).read_text(encoding="utf-8"))
        expected_keys = {f"{GAME['game_id']}:props:perbook:{b}"
                         for b in config.PER_BOOK_DECLARED_BOOKS}
        check("perbook_roster_keys_are_per_book_scoped",
              expected_keys.issubset(set(roster.keys())), roster.keys())
        check("perbook_roster_does_not_use_bundled_props_key",
              f"{GAME['game_id']}:props" not in roster, roster.keys())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================== #
# Kill switch
# ===================================================================== #
def test_kill_switch_default_off():
    import os
    saved = os.environ.pop(config.PER_BOOK_ENV_VAR, None)
    try:
        check("perbook_kill_switch_defaults_disabled", config.is_per_book_polling_enabled() is False)
    finally:
        if saved is not None:
            os.environ[config.PER_BOOK_ENV_VAR] = saved


def test_kill_switch_explicit_enable():
    import os
    saved = os.environ.get(config.PER_BOOK_ENV_VAR)
    try:
        os.environ[config.PER_BOOK_ENV_VAR] = "true"
        check("perbook_kill_switch_true_enables", config.is_per_book_polling_enabled() is True)
        os.environ[config.PER_BOOK_ENV_VAR] = "0"
        check("perbook_kill_switch_zero_disables", config.is_per_book_polling_enabled() is False)
    finally:
        if saved is None:
            os.environ.pop(config.PER_BOOK_ENV_VAR, None)
        else:
            os.environ[config.PER_BOOK_ENV_VAR] = saved


def test_kill_switch_layered_on_ladder_switch():
    """Per the report: PER_BOOK_ENV_VAR is a SEPARATE gate layered on top of
    MARKET_LADDER_ENABLED, not a replacement. Confirm main() still checks
    is_enabled() first (unmodified from before this node) by reading the
    source rather than re-deriving the claim."""
    src = (DATA_ROOT / "market_capture_run.py").read_text(encoding="utf-8")
    check("perbook_main_still_gated_by_is_enabled_first",
          "if not is_enabled():" in src)
    idx_is_enabled = src.index("if not is_enabled():")
    idx_per_book = src.index("is_per_book_polling_enabled()")
    check("perbook_ladder_gate_checked_before_per_book_gate", idx_is_enabled < idx_per_book)


# ===================================================================== #
# Scheduling arithmetic (market_per_book_scheduler.py)
# ===================================================================== #
def test_scheduler_window_boundaries():
    tip = datetime(2026, 8, 7, 23, 0, 0, tzinfo=timezone.utc)
    inside = tip - timedelta(minutes=30)
    just_before_window = tip - timedelta(minutes=61)
    at_tip = tip
    after_tip = tip + timedelta(minutes=1)
    check("scheduler_inside_window_true", per_book.in_pre_tip_window(tip, inside) is True)
    check("scheduler_before_window_false", per_book.in_pre_tip_window(tip, just_before_window) is False)
    check("scheduler_at_tip_excluded", per_book.in_pre_tip_window(tip, at_tip) is False,
          "in-play exclusion: must never fire at or after tip")
    check("scheduler_after_tip_excluded", per_book.in_pre_tip_window(tip, after_tip) is False)


def test_scheduler_due_respects_interval():
    game = {"game_id": "G1", "tip": datetime(2026, 8, 7, 23, 0, 0, tzinfo=timezone.utc)}
    now = datetime(2026, 8, 7, 22, 30, 0, tzinfo=timezone.utc)
    check("scheduler_due_first_time_no_prior_poll",
          per_book.due_per_book(game, now, last_polled=None) is True)
    recent = now - timedelta(seconds=60)
    check("scheduler_not_due_within_interval",
          per_book.due_per_book(game, now, last_polled=recent) is False)
    stale = now - timedelta(seconds=config.PER_BOOK_POLL_INTERVAL_SECONDS + 1)
    check("scheduler_due_after_interval_elapsed",
          per_book.due_per_book(game, now, last_polled=stale) is True)
    outside_window_now = datetime(2026, 8, 7, 20, 0, 0, tzinfo=timezone.utc)
    check("scheduler_not_due_outside_window",
          per_book.due_per_book(game, outside_window_now, last_polled=None) is False)


def test_scheduler_cursor_persists():
    tmp = Path(tempfile.mkdtemp(prefix="m27_cursor_"))
    try:
        path = tmp / per_book.PER_BOOK_CURSOR_JSON
        cur = per_book.PerBookCursor(path)
        check("cursor_empty_initially", cur.last_polled("G1") is None)
        now = datetime(2026, 8, 7, 22, 30, 0, tzinfo=timezone.utc)
        cur.mark_polled("G1", now)
        cur.save()
        cur2 = per_book.PerBookCursor(path)
        check("cursor_reloads_from_disk", cur2.last_polled("G1") == now,
              f"got {cur2.last_polled('G1')}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===================================================================== #
# Deliverable 2, part 2: M26's anti-faking test still passes, run
# directly from its own module (not reimplemented).
# ===================================================================== #
def test_m26_anti_faking_test_still_passes():
    import tests_M26
    before = len(tests_M26.FAILURES)
    tests_M26.test_defect2_within_one_payload_books_still_share_one_timestamp_documented()
    after = len(tests_M26.FAILURES)
    check("m26_anti_faking_test_still_passes_unmodified", after == before,
          f"tests_M26.FAILURES grew by {after - before}")


ALL_TESTS = [
    test_perbook_declared_subset_is_three_books,
    test_perbook_calls_use_bookmakers_param_not_regions,
    test_perbook_end_to_end_independent_retrieval_ts,
    test_perbook_roster_key_isolated_from_bundled_props_roster,
    test_kill_switch_default_off,
    test_kill_switch_explicit_enable,
    test_kill_switch_layered_on_ladder_switch,
    test_scheduler_window_boundaries,
    test_scheduler_due_respects_interval,
    test_scheduler_cursor_persists,
    test_m26_anti_faking_test_still_passes,
]


if __name__ == "__main__":
    print(f"Testing production code at: {DATA_ROOT}")
    print(f"market_capture_run.py: {run.__file__}")
    print(f"market_snapshot_writer.py: {writer.__file__}")
    print(f"market_per_book_scheduler.py: {per_book.__file__}")
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
