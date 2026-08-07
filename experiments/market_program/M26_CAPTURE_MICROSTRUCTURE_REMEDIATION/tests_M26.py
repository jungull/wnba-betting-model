#!/usr/bin/env python3
"""
Regression tests for M26_CAPTURE_MICROSTRUCTURE_REMEDIATION.

Run: python tests_M26.py
(stdlib only, plus `requests` which the production code already depends on
-- no pytest/pandas dependency, matching every sibling market-program node's
"stdlib-only, verified" discipline.)

Imports the REAL production capture code from the DATA worktree root
(C:/Users/jgallagher/wnba-betting-model) via sys.path insertion. These tests
call the actual `market_capture_run._poll_and_write` / `market_snapshot_writer`
functions with the HTTP layer monkeypatched (no network call, no vendor
credit spent by running this file) -- they are not reimplementations of the
logic under test.

One test group per defect:
  test_defect1_*  -- game-odds endpoint id-space mismatch (the zero-row bug)
  test_defect2_*  -- per-HTTP-call retrieval_ts independence
  test_defect3_*  -- witnessed absence / roster vanish-and-return detection
  test_defect4_*  -- vendor-latency / clock-skew fields recorded

DEFECT 1 evidence that this is a real regression test (fails on old code,
passes on fixed code), without needing to keep two copies of the module
around:
  (a) `test_defect1_old_filter_logic_yields_zero_rows_by_construction` -- runs
      the OLD filter expression, quoted verbatim from the pre-fix
      `market_capture_run.py` (see the code comment inline), against the
      real, unmodified `flatten_odds_payload()` output. This function was
      NOT changed by the fix (only `_poll_and_write`'s filter target was),
      so this is the actual production row-shape, not a stand-in. Zero rows,
      always, by construction of the id-space mismatch.
  (b) `test_defect1_fixed_end_to_end_writes_game_lines` -- calls the actual,
      CURRENT, fixed `_poll_and_write` end-to-end and proves it now writes
      h2h/spreads/totals rows.
  Additionally: this exact file was run once against the pre-fix
  `market_capture_run.py`/`market_snapshot_writer.py` bytes (before the
  fetch_* return-arity change made the old 3-tuple unpack incompatible with
  this file's 4-tuple fakes) using 3-tuple-compatible fakes; that run is
  transcribed in REPORT.md's "regression test evidence" section and showed
  n_written == 0 end-to-end, matching (a).
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DATA_ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model")
sys.path.insert(0, str(DATA_ROOT))

import market_capture_run as run          # noqa: E402
import market_snapshot_writer as writer   # noqa: E402

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


def _timing_stub(resp):
    """Reuses the REAL production `writer._timing()` (not a reimplementation)
    so fakes carry the same measurement-caveat text real HTTP calls do."""
    import time
    request_sent_ts = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    return writer._timing(request_sent_ts, t0, resp)


GAME = {"game_id": "1022600230", "home": "Las Vegas Aces", "away": "New York Liberty"}
VENDOR_EVENT_ID = "58beff9061f15ff3f416542cb51f4751"
EVENTS_BY_TEAMS = {("Las Vegas Aces", "New York Liberty"): VENDOR_EVENT_ID}


def _canned_games_json(include_totals=True):
    markets_dk = [
        {"key": "h2h", "last_update": "2026-08-07T12:00:00Z", "outcomes": [
            {"name": "Las Vegas Aces", "price": -150},
            {"name": "New York Liberty", "price": 130},
        ]},
        {"key": "spreads", "last_update": "2026-08-07T12:00:00Z", "outcomes": [
            {"name": "Las Vegas Aces", "point": -3.5, "price": -110},
            {"name": "New York Liberty", "point": 3.5, "price": -110},
        ]},
    ]
    bookmakers = [{"key": "draftkings", "markets": markets_dk}]
    if include_totals:
        bookmakers.append({"key": "fanduel", "markets": [
            {"key": "totals", "last_update": "2026-08-07T12:00:01Z", "outcomes": [
                {"name": "Over", "point": 165.5, "price": -105},
                {"name": "Under", "point": 165.5, "price": -115},
            ]},
        ]})
    return [
        {"id": VENDOR_EVENT_ID, "bookmakers": bookmakers},
        {"id": "unrelated-other-game-vendor-id", "bookmakers": [
            {"key": "draftkings", "markets": [
                {"key": "h2h", "last_update": "2026-08-07T12:00:00Z", "outcomes": [
                    {"name": "Team A", "price": -120}, {"name": "Team B", "price": 100},
                ]},
            ]},
        ]},
    ]


def _fake_fetch_odds_factory(include_totals=True, date_header="Fri, 07 Aug 2026 12:00:02 GMT"):
    games_json = _canned_games_json(include_totals)

    def _fake(session, key, timeout=30):
        raw = json.dumps(games_json).encode("utf-8")
        resp = FakeResp(200, {"x-requests-used": "3", "x-requests-remaining": "99997",
                              "x-requests-last": "3", "Date": date_header})
        return games_json, raw, resp, _timing_stub(resp)
    return _fake


def _fake_fetch_props_422(session, key, event_id, markets=None, timeout=30):
    resp = FakeResp(422, {})
    return None, b"", resp, _timing_stub(resp)


def _fake_fetch_props_ok(session, key, event_id, markets=None, timeout=30):
    event_json = {
        "id": event_id,
        "bookmakers": [{"key": "draftkings", "markets": [
            {"key": "player_points", "last_update": "2026-08-07T12:00:03Z", "outcomes": [
                {"description": "A'ja Wilson", "name": "Over", "point": 22.5, "price": -110},
                {"description": "A'ja Wilson", "name": "Under", "point": 22.5, "price": -110},
            ]},
        ]}],
    }
    resp = FakeResp(200, {"x-requests-used": "4", "x-requests-remaining": "99993",
                          "x-requests-last": "4", "Date": "Fri, 07 Aug 2026 12:00:05 GMT"})
    raw = json.dumps(event_json).encode("utf-8")
    return event_json, raw, resp, _timing_stub(resp)


def _patched(fetch_odds=None, fetch_props=None):
    """Context helper: monkeypatch writer.fetch_* for the duration of a call,
    always restoring originals even on exception."""
    class _Ctx:
        def __enter__(self):
            self.orig_odds = writer.fetch_odds_snapshot
            self.orig_props = writer.fetch_event_props_snapshot
            if fetch_odds is not None:
                writer.fetch_odds_snapshot = fetch_odds
            if fetch_props is not None:
                writer.fetch_event_props_snapshot = fetch_props
            return self

        def __exit__(self, *a):
            writer.fetch_odds_snapshot = self.orig_odds
            writer.fetch_event_props_snapshot = self.orig_props
            return False
    return _Ctx()


# ============================================================ DEFECT 1 ====
def test_defect1_old_filter_logic_yields_zero_rows_by_construction():
    rows = writer.flatten_odds_payload(
        _canned_games_json(), datetime.now(timezone.utc).isoformat(),
        poll_interval_seconds=900, a_payload_hash="deadbeef")
    check("defect1_canned_payload_nonempty_before_filter", len(rows) > 0,
          "fixture produced 0 rows before filtering -- fixture itself is broken")

    old_game_id = GAME["game_id"]  # "1022600230" -- OUR internal id
    # OLD (pre-fix) line, quoted verbatim from market_capture_run.py:
    #   rows = [r for r in rows if r["game_id"] == game_id]
    # where `game_id = game["game_id"]` -- our internal id, never the
    # vendor's event-id string every row actually carries.
    old_filtered = [r for r in rows if r["game_id"] == old_game_id]
    check("defect1_old_filter_logic_yields_zero_rows", len(old_filtered) == 0,
          f"expected 0 (this is the diagnosed bug), got {len(old_filtered)}")


def test_defect1_fixed_end_to_end_writes_game_lines():
    tmp = Path(tempfile.mkdtemp(prefix="m26_defect1_"))
    try:
        with _patched(fetch_odds=_fake_fetch_odds_factory(),
                     fetch_props=_fake_fetch_props_422):
            n_written, n_rejected = run._poll_and_write(
                session=None, key="test-key-not-real", game=GAME,
                obligation_type="ladder", label="T-4h", poll_interval_seconds=900,
                events_by_teams=EVENTS_BY_TEAMS, out_dir=tmp,
                now=datetime.now(timezone.utc))

        check("defect1_fixed_n_written_positive", n_written > 0,
              f"expected >0 rows written, got {n_written}")
        check("defect1_fixed_n_rejected_zero", n_rejected == 0,
              f"expected 0 rejected, got {n_rejected}")

        snap_path = tmp / writer.SNAPSHOTS_CSV
        check("defect1_fixed_snapshots_csv_exists", snap_path.exists())
        markets_seen, rows_out = set(), []
        if snap_path.exists():
            with open(snap_path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    rows_out.append(row)
                    markets_seen.add(row["market"])
        check("defect1_fixed_h2h_landed", "h2h" in markets_seen, f"markets seen: {markets_seen}")
        check("defect1_fixed_spreads_landed", "spreads" in markets_seen, f"markets seen: {markets_seen}")
        check("defect1_fixed_totals_landed", "totals" in markets_seen, f"markets seen: {markets_seen}")
        check("defect1_fixed_no_cross_game_leak",
              all(r["game_id"] == VENDOR_EVENT_ID for r in rows_out),
              "a row from the unrelated other game leaked into this game's write")

        poll_log = tmp / writer.POLL_LOG_CSV
        check("defect1_fixed_poll_log_exists", poll_log.exists())
        if poll_log.exists():
            with open(poll_log, newline="", encoding="utf-8") as f:
                log_rows = list(csv.DictReader(f))
            odds_row = next((r for r in log_rows if r["endpoint"] == writer.ODDS_URL), None)
            check("defect1_fixed_poll_log_shows_rows_written",
                  odds_row is not None and int(odds_row["n_rows_written"]) > 0,
                  f"poll_log odds row: {odds_row}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_defect1_no_event_id_is_explicit_not_silent_zero():
    """When /events can't resolve this game to a vendor event id, the game-
    odds endpoint's slate-wide response cannot be honestly attributed to
    this game at all -- confirm this now produces an explicit, readable
    SKIPPED reason in poll_log.csv rather than another unexplained zero."""
    tmp = Path(tempfile.mkdtemp(prefix="m26_defect1_noevent_"))
    try:
        with _patched(fetch_odds=_fake_fetch_odds_factory(), fetch_props=_fake_fetch_props_422):
            n_written, n_rejected = run._poll_and_write(
                session=None, key="test-key-not-real", game=GAME,
                obligation_type="ladder", label="T-4h", poll_interval_seconds=900,
                events_by_teams={}, out_dir=tmp, now=datetime.now(timezone.utc))
        check("defect1_noevent_zero_rows", n_written == 0)
        poll_log = tmp / writer.POLL_LOG_CSV
        with open(poll_log, newline="", encoding="utf-8") as f:
            log_rows = list(csv.DictReader(f))
        check("defect1_noevent_reason_is_explicit", len(log_rows) == 1
              and "SKIPPED" in (log_rows[0].get("error") or ""),
              f"poll_log rows: {log_rows}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================ DEFECT 2 ====
def test_defect2_odds_and_props_calls_get_distinct_retrieval_ts():
    tmp = Path(tempfile.mkdtemp(prefix="m26_defect2_"))
    try:
        with _patched(fetch_odds=_fake_fetch_odds_factory(), fetch_props=_fake_fetch_props_ok):
            run._poll_and_write(
                session=None, key="test-key-not-real", game=GAME,
                obligation_type="ladder", label="T-4h", poll_interval_seconds=900,
                events_by_teams=EVENTS_BY_TEAMS, out_dir=tmp, now=datetime.now(timezone.utc))

        with open(tmp / writer.SNAPSHOTS_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        odds_ts = {r["retrieval_ts"] for r in rows if r["market"] in ("h2h", "spreads", "totals")}
        props_ts = {r["retrieval_ts"] for r in rows if r["market"] == "player_points"}
        check("defect2_both_market_families_present", len(odds_ts) > 0 and len(props_ts) > 0,
              f"odds_ts={odds_ts} props_ts={props_ts}")
        check("defect2_odds_and_props_retrieval_ts_differ", odds_ts.isdisjoint(props_ts),
              "the odds call and the props call -- two genuinely separate HTTP round "
              f"trips -- still share a retrieval_ts: odds={odds_ts} props={props_ts}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_defect2_within_one_payload_books_still_share_one_timestamp_documented():
    """Honest negative result, not swept under the rug: within ONE HTTP
    response (e.g. draftkings + fanduel both inside the single odds-call
    payload above), the vendor bundles all books into one JSON body, so
    there is still exactly one retrieval_ts for that call. This is the
    NOT_CLOSED half of defect 2 -- asserted here so a future change that
    silently "fixes" this by fabricating per-book parse-order timestamps
    (which would carry zero real ordering information and could mislead a
    lead-lag reader) would be caught as an unreviewed behavior change."""
    tmp = Path(tempfile.mkdtemp(prefix="m26_defect2b_"))
    try:
        with _patched(fetch_odds=_fake_fetch_odds_factory(), fetch_props=_fake_fetch_props_422):
            run._poll_and_write(
                session=None, key="test-key-not-real", game=GAME,
                obligation_type="ladder", label="T-4h", poll_interval_seconds=900,
                events_by_teams=EVENTS_BY_TEAMS, out_dir=tmp, now=datetime.now(timezone.utc))
        with open(tmp / writer.SNAPSHOTS_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        books_seen = {r["book"] for r in rows}
        ts_seen = {r["retrieval_ts"] for r in rows}
        check("defect2_multi_book_fixture_has_2plus_books", len(books_seen) >= 2, f"books={books_seen}")
        check("defect2_still_one_ts_across_books_within_one_call", len(ts_seen) == 1,
              f"expected exactly 1 shared retrieval_ts across books in one HTTP payload "
              f"(structural vendor limitation, documented NOT_CLOSED), got {ts_seen}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================ DEFECT 3 ====
def test_defect3_roster_index_detects_vanish_and_reappear():
    tmp = Path(tempfile.mkdtemp(prefix="m26_defect3_unit_"))
    try:
        roster_path = tmp / writer.ROSTER_INDEX_JSON
        roster = writer.RosterIndex(roster_path)

        rows_poll1 = [
            {"game_id": "G1", "book": "draftkings", "market": "h2h", "outcome": "A", "market_status": "active"},
            {"game_id": "G1", "book": "draftkings", "market": "totals", "outcome": "Over", "market_status": "active"},
        ]
        vanish1 = writer.detect_vanished_chains(
            rows_poll1, roster, roster_key="G1:odds", game_id="G1",
            retrieval_ts="2026-08-07T00:00:00Z", ingestion_ts="2026-08-07T00:00:00Z",
            poll_interval_seconds=900, a_payload_hash="h1")
        check("defect3_first_poll_no_prior_roster_no_vanish", vanish1 == [], f"{vanish1}")

        # Poll 2: the totals chain disappears from the vendor response.
        rows_poll2 = [
            {"game_id": "G1", "book": "draftkings", "market": "h2h", "outcome": "A", "market_status": "active"},
        ]
        vanish2 = writer.detect_vanished_chains(
            rows_poll2, roster, roster_key="G1:odds", game_id="G1",
            retrieval_ts="2026-08-07T00:15:00Z", ingestion_ts="2026-08-07T00:15:00Z",
            poll_interval_seconds=900, a_payload_hash="h2")
        check("defect3_vanish_detected", len(vanish2) == 1, f"{vanish2}")
        if vanish2:
            v = vanish2[0]
            check("defect3_vanish_row_market_status_missing", v["market_status"] == "missing", v)
            check("defect3_vanish_row_not_labeled_suspended", v["market_status"] != "suspended",
                  "must never fabricate a vendor suspension signal this endpoint doesn't provide")
            check("defect3_vanish_row_correct_chain", (v["book"], v["market"], v["outcome"])
                  == ("draftkings", "totals", "Over"), v)
            check("defect3_vanish_row_has_witnessed_retrieval_ts",
                  v["retrieval_ts"] == "2026-08-07T00:15:00Z", v)

        # Poll 3: totals chain, still absent -- must NOT re-fire (roster
        # already reflects "not active"; this checks set_active updated
        # correctly on poll 2, not just that vanish2 fired once).
        vanish3 = writer.detect_vanished_chains(
            rows_poll2, roster, roster_key="G1:odds", game_id="G1",
            retrieval_ts="2026-08-07T00:30:00Z", ingestion_ts="2026-08-07T00:30:00Z",
            poll_interval_seconds=900, a_payload_hash="h3")
        check("defect3_no_repeat_vanish_while_still_absent", vanish3 == [], f"{vanish3}")

        # Poll 4: totals chain reappears with IDENTICAL content to poll 1.
        # market_snapshot_writer has no content-hash dedup layer at all (it
        # writes a fresh row every poll for every outcome present), so the
        # reappearance is captured simply by it showing up again as
        # market_status=active in the next poll's `rows` -- the defect-3 ask
        # here (M17) was specifically that VANISHING leaves no trace, which
        # is what poll 2/3 above close. Confirm the roster now tracks it
        # active again so a SUBSEQUENT vanish would be detected too.
        vanish4 = writer.detect_vanished_chains(
            rows_poll1, roster, roster_key="G1:odds", game_id="G1",
            retrieval_ts="2026-08-07T00:45:00Z", ingestion_ts="2026-08-07T00:45:00Z",
            poll_interval_seconds=900, a_payload_hash="h4")
        check("defect3_reappear_no_false_vanish", vanish4 == [], f"{vanish4}")
        roster.save()  # detect_vanished_chains mutates roster in memory only; the
                       # caller (market_capture_run._poll_and_write) is responsible
                       # for persisting, exactly like ChainIndex already works.
        check("defect3_roster_persisted_to_disk", roster_path.exists())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_defect3_end_to_end_via_poll_and_write():
    tmp = Path(tempfile.mkdtemp(prefix="m26_defect3_e2e_"))
    try:
        with _patched(fetch_odds=_fake_fetch_odds_factory(include_totals=True),
                     fetch_props=_fake_fetch_props_422):
            run._poll_and_write(session=None, key="k", game=GAME, obligation_type="ladder",
                               label="T-4h", poll_interval_seconds=900,
                               events_by_teams=EVENTS_BY_TEAMS, out_dir=tmp,
                               now=datetime.now(timezone.utc))
        with _patched(fetch_odds=_fake_fetch_odds_factory(include_totals=False),
                     fetch_props=_fake_fetch_props_422):
            run._poll_and_write(session=None, key="k", game=GAME, obligation_type="ladder",
                               label="T-2h", poll_interval_seconds=900,
                               events_by_teams=EVENTS_BY_TEAMS, out_dir=tmp,
                               now=datetime.now(timezone.utc))
        with open(tmp / writer.SNAPSHOTS_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        missing_rows = [r for r in rows if r["market_status"] == "missing" and r["market"] == "totals"]
        check("defect3_e2e_vanish_witnessed_in_snapshots_csv", len(missing_rows) >= 1,
              f"total rows={len(rows)} missing-totals rows={len(missing_rows)}")
        if missing_rows:
            check("defect3_e2e_vanish_note_present", "WITNESSED_ABSENCE" in (missing_rows[0].get("vendor_latency_note") or ""),
                  missing_rows[0].get("vendor_latency_note"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ============================================================ DEFECT 4 ====
def test_defect4_clock_skew_estimate_from_http_date():
    skew, parsed = writer.estimate_clock_skew_seconds(
        "Fri, 07 Aug 2026 12:00:00 GMT", "2026-08-07T12:00:03+00:00")
    check("defect4_skew_computed", skew is not None and abs(skew - 3.0) < 0.001, f"skew={skew}")
    check("defect4_skew_parsed_date_utc", parsed == "2026-08-07T12:00:00+00:00", parsed)

    skew_none, parsed_none = writer.estimate_clock_skew_seconds(None, "2026-08-07T12:00:03+00:00")
    check("defect4_skew_none_when_no_date_header", skew_none is None and parsed_none is None)


def test_defect4_vendor_timing_log_written_end_to_end():
    tmp = Path(tempfile.mkdtemp(prefix="m26_defect4_"))
    try:
        with _patched(fetch_odds=_fake_fetch_odds_factory(), fetch_props=_fake_fetch_props_ok):
            run._poll_and_write(session=None, key="k", game=GAME, obligation_type="ladder",
                               label="T-4h", poll_interval_seconds=900,
                               events_by_teams=EVENTS_BY_TEAMS, out_dir=tmp,
                               now=datetime.now(timezone.utc))
        log_path = tmp / writer.VENDOR_TIMING_LOG_CSV
        check("defect4_timing_log_exists", log_path.exists())
        if log_path.exists():
            with open(log_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            check("defect4_timing_log_has_two_calls", len(rows) == 2, f"{len(rows)} rows")
            check("defect4_timing_log_rtt_populated",
                  all(r.get("rtt_seconds") not in (None, "") for r in rows), rows)
            check("defect4_timing_log_caveat_present",
                  all("vendor+network+our-own latency" in (r.get("measurement_caveat") or "") for r in rows),
                  "the honest vendor_latency_bound caveat must travel with every row")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


ALL_TESTS = [
    test_defect1_old_filter_logic_yields_zero_rows_by_construction,
    test_defect1_fixed_end_to_end_writes_game_lines,
    test_defect1_no_event_id_is_explicit_not_silent_zero,
    test_defect2_odds_and_props_calls_get_distinct_retrieval_ts,
    test_defect2_within_one_payload_books_still_share_one_timestamp_documented,
    test_defect3_roster_index_detects_vanish_and_reappear,
    test_defect3_end_to_end_via_poll_and_write,
    test_defect4_clock_skew_estimate_from_http_date,
    test_defect4_vendor_timing_log_written_end_to_end,
]


if __name__ == "__main__":
    print(f"Testing production code at: {DATA_ROOT}")
    print(f"market_capture_run.py: {run.__file__}")
    print(f"market_snapshot_writer.py: {writer.__file__}")
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
