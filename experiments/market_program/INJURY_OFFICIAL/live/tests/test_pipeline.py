#!/usr/bin/env python3
"""
Fixture tests for the capture orchestrator (capture_injury_live.py):
hash-dedup, status-supersession, the absent-row-is-not-healthy rule, and
unmatched/rejects reporting -- D033 mandate item 3/4, run regardless of
live network accessibility. Network and entity-resolution calls are
monkeypatched; only the parser and CSV-writing logic are exercised for
real, against a temp directory so this never touches the track's actual
raw/ or *.csv files.
"""
import csv
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import capture_injury_live as cil  # noqa: E402
from fetch_official_report import FetchResult  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture_bytes(name):
    return (FIXTURES / name).read_bytes()


class _RedirectedPaths:
    """Point every module-level path constant at a fresh temp dir for the
    duration of the test, so pipeline tests never touch the real
    injury_snapshots.csv / status_transitions.csv / raw/ this track owns."""

    def __enter__(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self._patches = [
            mock.patch.object(cil, "ROOT", root),
            mock.patch.object(cil, "RAWDIR", root / "raw"),
            mock.patch.object(cil, "CAPTURE_LOG_CSV", root / "capture_log.csv"),
            mock.patch.object(cil, "SNAPSHOTS_CSV", root / "injury_snapshots.csv"),
            mock.patch.object(cil, "TRANSITIONS_CSV", root / "status_transitions.csv"),
            mock.patch.object(cil, "COVERAGE_CSV", root / "report_coverage.csv"),
            mock.patch.object(cil, "REJECTS_CSV", root / "rejects.csv"),
        ]
        for p in self._patches:
            p.start()
        return root

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()
        self.tmpdir.cleanup()


def _fake_fetch(body_fixture, status=200, headers=None):
    def _fetch(url, retries=2, backoff_seconds=3.0):
        return FetchResult(
            url=url, status_code=status, body=_fixture_bytes(body_fixture),
            headers=headers or {}, retrieval_ts_utc="2026-08-06T19:00:00+00:00",
        )
    return _fetch


class TestHashDedup(unittest.TestCase):
    def test_identical_bytes_second_fetch_is_deduped(self):
        with _RedirectedPaths():
            with mock.patch.object(cil, "fetch_pdf",
                                    _fake_fetch("reference_prod_wnba_official_20260806T190009Z.pdf")), \
                 mock.patch.object(cil, "try_load_index", return_value=({}, "no index in test")):
                r1 = cil.run_one_cycle("https://example.invalid/a.pdf")
                r2 = cil.run_one_cycle("https://example.invalid/a.pdf")
            self.assertEqual(r1["outcome"], "NOVEL")
            self.assertEqual(r2["outcome"], "DUPLICATE_OF_PRIOR")
            self.assertGreater(r1["snapshot_rows"], 0)
            self.assertEqual(r2["snapshot_rows"], 0)

            with cil.SNAPSHOTS_CSV.open() as f:
                rows = list(csv.DictReader(f))
            # Only ONE capture's worth of snapshot rows exist, despite two
            # fetch attempts -- proves dedup did not double-write.
            self.assertEqual(len({row["capture_id"] for row in rows}), 1)

            with cil.CAPTURE_LOG_CSV.open() as f:
                log_rows = list(csv.DictReader(f))
            self.assertEqual(len(log_rows), 2)
            self.assertEqual(log_rows[0]["outcome"], "NOVEL")
            self.assertEqual(log_rows[1]["outcome"], "DUPLICATE_OF_PRIOR")
            self.assertEqual(log_rows[1]["dedup_of_capture_id"],
                              log_rows[0]["capture_id"])


class TestSupersessionAndAbsentRowRule(unittest.TestCase):
    def test_status_change_produces_a_transition_row(self):
        """Fixture pair: same report content across ~1h, so a REAL status
        change is synthesized by using two different fixtures where at
        least one player's status differs, to exercise the transition
        path deterministically."""
        with _RedirectedPaths():
            with mock.patch.object(cil, "try_load_index",
                                    return_value=({}, "no index in test")):
                with mock.patch.object(
                        cil, "fetch_pdf",
                        _fake_fetch("reference_prod_wnba_official_20260731T205354Z.pdf")):
                    r1 = cil.run_one_cycle("https://example.invalid/day1.pdf")
                with mock.patch.object(
                        cil, "fetch_pdf",
                        _fake_fetch("reference_prod_wnba_official_20260805T230003Z.pdf")):
                    r2 = cil.run_one_cycle("https://example.invalid/day2.pdf")

            self.assertEqual(r1["outcome"], "NOVEL")
            self.assertEqual(r2["outcome"], "NOVEL")
            self.assertGreater(r2["transitions"], 0)

            with cil.TRANSITIONS_CSV.open() as f:
                trans = list(csv.DictReader(f))
            self.assertGreater(len(trans), 0)
            for t in trans:
                self.assertIn(t["censor_type"], ("interval",))
                self.assertEqual(t["tier"], "T0")
                self.assertTrue(t["t_upper_utc_bound"])

    def test_player_absent_from_next_report_is_removed_not_healthy(self):
        """A player present in the first fixture but absent from the
        second must appear in status_transitions.csv as
        REMOVED_FROM_REPORT, never silently disappear, and NEVER appear in
        injury_snapshots.csv as 'Available' (which this pipeline never
        synthesizes)."""
        with _RedirectedPaths():
            with mock.patch.object(cil, "try_load_index",
                                    return_value=({}, "no index in test")):
                with mock.patch.object(
                        cil, "fetch_pdf",
                        _fake_fetch("reference_prod_wnba_official_20260731T205354Z.pdf")):
                    cil.run_one_cycle("https://example.invalid/day1.pdf")
                with mock.patch.object(
                        cil, "fetch_pdf",
                        _fake_fetch("reference_prod_wnba_official_20260805T230003Z.pdf")):
                    cil.run_one_cycle("https://example.invalid/day2.pdf")

            with cil.TRANSITIONS_CSV.open() as f:
                trans = list(csv.DictReader(f))
            removed = [t for t in trans
                       if t["status_after"] == "REMOVED_FROM_REPORT"]
            self.assertGreater(len(removed), 0)

            with cil.SNAPSHOTS_CSV.open() as f:
                snaps = list(csv.DictReader(f))
            self.assertTrue(all(s["status"] != "Available" for s in snaps),
                             "pipeline must never synthesize an Available "
                             "row for an absent player")

    def test_not_yet_submitted_writes_coverage_row_not_a_player_row(self):
        with _RedirectedPaths():
            with mock.patch.object(cil, "try_load_index",
                                    return_value=({}, "no index in test")), \
                 mock.patch.object(
                     cil, "fetch_pdf",
                     _fake_fetch("reference_prod_wnba_official_20260806T190009Z.pdf")):
                r = cil.run_one_cycle("https://example.invalid/a.pdf")
            self.assertGreater(r["coverage_rows"], 0)
            with cil.COVERAGE_CSV.open() as f:
                cov = list(csv.DictReader(f))
            self.assertEqual(len(cov), r["coverage_rows"])
            for row in cov:
                self.assertEqual(row["coverage_status"], "NOT_YET_SUBMITTED")
            with cil.SNAPSHOTS_CSV.open() as f:
                snaps = list(csv.DictReader(f))
            self.assertTrue(all("NOT YET SUBMITTED" not in s["status"].upper()
                                 for s in snaps))


class TestRejectsReported(unittest.TestCase):
    def test_parser_rejects_flow_through_to_rejects_csv(self):
        with _RedirectedPaths():
            with mock.patch.object(cil, "try_load_index",
                                    return_value=({}, "no index in test")), \
                 mock.patch.object(
                     cil, "fetch_pdf",
                     _fake_fetch("reference_prod_wnba_official_20260805T230003Z.pdf")):
                r = cil.run_one_cycle("https://example.invalid/a.pdf")
            self.assertGreater(r["rejects"], 0)
            with cil.REJECTS_CSV.open() as f:
                rej = list(csv.DictReader(f))
            self.assertEqual(len(rej), r["rejects"])
            for row in rej:
                self.assertTrue(row["reason"])


class TestBotBlockAndNetworkUnavailablePropagate(unittest.TestCase):
    def test_bot_block_is_logged_and_reraised_not_swallowed(self):
        from fetch_official_report import BotBlockDetected

        def _blocked(url, retries=2, backoff_seconds=3.0):
            raise BotBlockDetected(url, 403, b"cf-challenge")

        with _RedirectedPaths():
            with mock.patch.object(cil, "fetch_pdf", _blocked):
                with self.assertRaises(BotBlockDetected):
                    cil.run_one_cycle("https://example.invalid/blocked.pdf")
            with cil.CAPTURE_LOG_CSV.open() as f:
                log_rows = list(csv.DictReader(f))
            self.assertEqual(log_rows[0]["outcome"], "BOT_BLOCK")
            self.assertEqual(log_rows[0]["http_status"], "403")

    def test_network_unavailable_is_logged_and_reraised_not_swallowed(self):
        from fetch_official_report import NetworkUnavailable

        def _timeout(url, retries=2, backoff_seconds=3.0):
            raise NetworkUnavailable(url, "TimeoutError: simulated")

        with _RedirectedPaths():
            with mock.patch.object(cil, "fetch_pdf", _timeout):
                with self.assertRaises(NetworkUnavailable):
                    cil.run_one_cycle("https://example.invalid/timeout.pdf")
            with cil.CAPTURE_LOG_CSV.open() as f:
                log_rows = list(csv.DictReader(f))
            self.assertEqual(log_rows[0]["outcome"], "NETWORK_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
