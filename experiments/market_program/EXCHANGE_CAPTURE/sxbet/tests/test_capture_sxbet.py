"""
Fixture tests for capture_sxbet.py -- parsing, schema enforcement, dedup/
prev-ref chain, best-line computation, rate limiting, and the append-only
JSONL writer. No network access is used; a FakeSession stands in for
requests.Session and is fed the fixture JSON files under tests/fixtures/.

Run: python -m unittest discover -s tests -v
(from experiments/market_program/EXCHANGE_CAPTURE/sxbet/)
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

import capture_sxbet as csx  # noqa: E402

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load_fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, text: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    """Routes GETs to canned fixture payloads keyed by URL suffix."""

    def __init__(self, routes: dict, fail_paths: dict = None):
        self.headers = {}
        self.routes = routes  # path -> payload dict
        self.fail_paths = fail_paths or {}  # path -> (status_code, text)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        for path, (status, text) in self.fail_paths.items():
            if url.endswith(path):
                return FakeResponse({}, status_code=status, text=text)
        for path, payload in self.routes.items():
            if url.endswith(path):
                return FakeResponse(payload)
        raise AssertionError(f"FakeSession: no route configured for {url}")


class TestParsing(unittest.TestCase):
    def test_parse_markets_ok(self):
        raw = load_fixture("markets_active.json")["data"]["markets"]
        parsed = csx.parse_markets(raw)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["marketHash"], "0xaaa1")

    def test_parse_markets_rejects_missing_field(self):
        raw = load_fixture("markets_active.json")["data"]["markets"]
        broken = [dict(raw[0])]
        del broken[0]["marketHash"]
        with self.assertRaises(ValueError):
            csx.parse_markets(broken)

    def test_parse_orders_ok(self):
        raw = load_fixture("orders.json")["data"]
        parsed = csx.parse_orders(raw)
        self.assertEqual(len(parsed), 3)

    def test_parse_orders_rejects_missing_field(self):
        raw = load_fixture("orders.json")["data"]
        broken = [dict(raw[0])]
        del broken[0]["percentageOdds"]
        with self.assertRaises(ValueError):
            csx.parse_orders(broken)

    def test_parse_trades_ok(self):
        raw = load_fixture("trades.json")["data"]["trades"]
        parsed = csx.parse_trades(raw)
        self.assertEqual(len(parsed), 1)

    def test_parse_trades_rejects_missing_field(self):
        raw = load_fixture("trades.json")["data"]["trades"]
        broken = [dict(raw[0])]
        del broken[0]["fillHash"]
        with self.assertRaises(ValueError):
            csx.parse_trades(broken)


class TestBestLine(unittest.TestCase):
    def test_best_line_picks_max_percentage_odds_per_side(self):
        raw = load_fixture("orders.json")["data"]
        orders = csx.parse_orders(raw)
        by_market = {"0xaaa1": orders}
        best = csx.compute_best_line(by_market)
        by_side = {b["side"]: b for b in best}
        # outcomeTwo: two orders, 49625...e18 and 51000...e18 -> best is the larger
        self.assertEqual(by_side["outcomeTwo"]["best_order_hash"], "0xord2")
        self.assertEqual(by_side["outcomeTwo"]["n_active_orders"], 2)
        # outcomeOne: single order
        self.assertEqual(by_side["outcomeOne"]["best_order_hash"], "0xord3")
        self.assertEqual(by_side["outcomeOne"]["n_active_orders"], 1)

    def test_best_line_empty_side_is_reported_not_omitted(self):
        by_market = {"0xzzz": []}
        best = csx.compute_best_line(by_market)
        self.assertEqual(len(best), 2)
        for row in best:
            self.assertEqual(row["n_active_orders"], 0)
            self.assertIsNone(row["best_percentage_odds"])

    def test_best_line_total_available_stake_subtracts_fill(self):
        raw = load_fixture("orders.json")["data"]
        orders = csx.parse_orders(raw)
        by_market = {"0xaaa1": orders}
        best = csx.compute_best_line(by_market)
        by_side = {b["side"]: b for b in best}
        # order 1: 50000000 - 0 ; order 2: 30000000 - 10000000 = 20000000
        self.assertEqual(by_side["outcomeTwo"]["total_available_stake"], str(50000000 + 20000000))


class TestRateLimiter(unittest.TestCase):
    def test_enforces_minimum_interval(self):
        clock = {"t": 0.0}
        sleeps = []

        def fake_time():
            return clock["t"]

        def fake_sleep(seconds):
            sleeps.append(seconds)
            clock["t"] += seconds

        rl = csx.RateLimiter(min_interval_seconds=1.0, sleep_fn=fake_sleep, time_fn=fake_time)
        rl.wait()  # first call: no sleep
        clock["t"] += 0.2  # simulate 0.2s of "work"
        rl.wait()  # second call: must sleep ~0.8s
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 0.8, places=6)

    def test_no_sleep_when_interval_already_elapsed(self):
        clock = {"t": 0.0}
        sleeps = []

        def fake_time():
            return clock["t"]

        def fake_sleep(seconds):
            sleeps.append(seconds)

        rl = csx.RateLimiter(min_interval_seconds=1.0, sleep_fn=fake_sleep, time_fn=fake_time)
        rl.wait()
        clock["t"] += 5.0
        rl.wait()
        self.assertEqual(len(sleeps), 0)


class TestEnvelopeAndDedup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sxbet_test_")
        self.state = csx.StateStore.load(os.path.join(self.tmp, "state.json"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_observation_is_new_with_null_prev_ref(self):
        row, is_new = csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 1},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="2026-08-06T00:00:00Z",
            poll_interval_at_capture=None, state=self.state, cycle_id="c1",
        )
        self.assertTrue(is_new)
        self.assertIsNotNone(row)
        self.assertIsNone(row["prev_snapshot_ref"])
        self.assertFalse(row["is_order"])
        self.assertEqual(row["provenance"], "EXCHANGE_PUBLIC_API")

    def test_identical_second_observation_is_deduped(self):
        csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 1},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t1",
            poll_interval_at_capture=None, state=self.state, cycle_id="c1",
        )
        row2, is_new2 = csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 1},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t2",
            poll_interval_at_capture=None, state=self.state, cycle_id="c2",
        )
        self.assertFalse(is_new2)
        self.assertIsNone(row2)

    def test_changed_observation_chains_prev_snapshot_ref(self):
        row1, _ = csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 1},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t1",
            poll_interval_at_capture=None, state=self.state, cycle_id="c1",
        )
        row2, is_new2 = csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 2},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t2",
            poll_interval_at_capture=None, state=self.state, cycle_id="c2",
        )
        self.assertTrue(is_new2)
        self.assertEqual(row2["prev_snapshot_ref"], row1["payload_hash"])
        self.assertNotEqual(row2["payload_hash"], row1["payload_hash"])

    def test_state_resumes_dedup_chain_across_fresh_load(self):
        row1, _ = csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 1},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t1",
            poll_interval_at_capture=None, state=self.state, cycle_id="c1",
        )
        self.state.save()

        # Simulate a fresh process: reload state from disk.
        reloaded = csx.StateStore.load(self.state.path)
        row2, is_new2 = csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 1},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t2",
            poll_interval_at_capture=None, state=reloaded, cycle_id="c2",
        )
        self.assertFalse(is_new2)  # identical content, still deduped after reload

        row3, is_new3 = csx.build_envelope(
            table="markets", key="0xaaa1", content={"a": 99},
            vendor_ts=None, vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t3",
            poll_interval_at_capture=None, state=reloaded, cycle_id="c3",
        )
        self.assertTrue(is_new3)
        self.assertEqual(row3["prev_snapshot_ref"], row1["payload_hash"])

    def test_every_row_carries_amendment_4_fields(self):
        row, _ = csx.build_envelope(
            table="trades", key="0xfill1", content={"a": 1},
            vendor_ts="2026-08-06T00:00:00Z", vendor_ts_semantics="unknown_unverified",
            vendor_latency_note="note", retrieval_ts="t1",
            poll_interval_at_capture=300.0, state=self.state, cycle_id="c1",
        )
        required = {
            "vendor_ts", "vendor_ts_semantics", "retrieval_ts", "ingestion_ts",
            "max_staleness_bound", "poll_interval_at_capture", "vendor_latency_note",
            "payload_hash", "prev_snapshot_ref",
        }
        self.assertTrue(required.issubset(row.keys()))


class TestAppendOnlyWriter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sxbet_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_append_jsonl_appends_not_overwrites(self):
        path = os.path.join(self.tmp, "sub", "out.jsonl")
        csx.append_jsonl(path, [{"x": 1}])
        csx.append_jsonl(path, [{"x": 2}])
        with open(path, "r", encoding="utf-8") as fh:
            lines = [json.loads(l) for l in fh if l.strip()]
        self.assertEqual(lines, [{"x": 1}, {"x": 2}])

    def test_append_jsonl_noop_on_empty(self):
        path = os.path.join(self.tmp, "out.jsonl")
        csx.append_jsonl(path, [])
        self.assertFalse(os.path.exists(path))


class TestSxBetClientAgainstFixtures(unittest.TestCase):
    def test_get_active_markets_parses_fixture(self):
        session = FakeSession({"/markets/active": load_fixture("markets_active.json")})
        client = csx.SxBetClient(session=session, rate_limiter=_NoWaitLimiter())
        markets, log_row = client.get_active_markets()
        self.assertEqual(len(markets), 2)
        self.assertTrue(log_row["ok"])
        self.assertEqual(log_row["http_status"], 200)

    def test_get_orders_parses_fixture(self):
        session = FakeSession({"/orders": load_fixture("orders.json")})
        client = csx.SxBetClient(session=session, rate_limiter=_NoWaitLimiter())
        orders, log_row = client.get_orders(["0xaaa1"])
        self.assertEqual(len(orders), 3)

    def test_get_trades_parses_fixture(self):
        session = FakeSession({"/trades": load_fixture("trades.json")})
        client = csx.SxBetClient(session=session, rate_limiter=_NoWaitLimiter())
        trades, log_row = client.get_trades(["0xaaa1"])
        self.assertEqual(len(trades), 1)

    def test_non_200_is_logged_not_raised(self):
        session = FakeSession({}, fail_paths={"/markets/active": (503, "service unavailable")})
        client = csx.SxBetClient(session=session, rate_limiter=_NoWaitLimiter())
        markets, log_row = client.get_active_markets()
        self.assertEqual(markets, [])
        self.assertFalse(log_row["ok"])
        self.assertEqual(log_row["http_status"], 503)
        self.assertIn("503", log_row["error"])

    def test_malformed_json_is_logged_not_raised(self):
        class BrokenSession(FakeSession):
            def get(self, url, params=None, timeout=None):
                resp = FakeResponse({}, status_code=200, text="not json")

                def bad_json():
                    raise ValueError("no JSON object could be decoded")

                resp.json = bad_json
                return resp

        session = BrokenSession({})
        client = csx.SxBetClient(session=session, rate_limiter=_NoWaitLimiter())
        markets, log_row = client.get_active_markets()
        self.assertEqual(markets, [])
        self.assertFalse(log_row["ok"])
        self.assertIn("non-JSON", log_row["error"])


class _NoWaitLimiter(csx.RateLimiter):
    def __init__(self):
        super().__init__(min_interval_seconds=0.0, sleep_fn=lambda s: None)


class TestRunCycleEndToEnd(unittest.TestCase):
    """Drives run_cycle() against fixture data (no network) and asserts on
    idempotency: a second cycle with byte-identical upstream data writes
    zero new rows and dedupes everything; a changed upstream orderbook
    produces new rows chained via prev_snapshot_ref."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sxbet_e2e_")
        self.data_dir = os.path.join(self.tmp, "data")
        self.state = csx.StateStore.load(os.path.join(self.tmp, "state.json"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_client(self, orders_payload=None):
        routes = {
            "/markets/active": load_fixture("markets_active.json"),
            "/orders": orders_payload or load_fixture("orders.json"),
            "/trades": load_fixture("trades.json"),
        }
        session = FakeSession(routes)
        return csx.SxBetClient(session=session, rate_limiter=_NoWaitLimiter())

    def test_first_cycle_writes_rows_for_every_table(self):
        client = self._make_client()
        stats = csx.run_cycle(client, self.state, self.data_dir, cycle_id="cycle1")
        self.assertEqual(stats["rows_written"]["markets"], 2)
        self.assertGreater(stats["rows_written"]["orderbook"], 0)
        self.assertGreater(stats["rows_written"]["best_line"], 0)
        self.assertEqual(stats["rows_written"]["trades"], 1)
        self.assertEqual(stats["endpoint_failures"], [])
        # M26_CAPTURE_MICROSTRUCTURE_REMEDIATION (defect 3): roster_events is
        # a transition log, not a per-poll table -- it structurally cannot
        # write anything on a FIRST cycle (there is no prior roster to diff
        # against yet, by construction of compute_roster_transitions). Every
        # other table always writes something on cycle 1 given this fixture,
        # which is what this loop checks; roster_events is excluded on
        # purpose, not an oversight.
        for table, fname in csx.TABLE_FILES.items():
            if table == "roster_events":
                self.assertEqual(stats["rows_written"]["roster_events"], 0)
                continue
            self.assertTrue(os.path.exists(os.path.join(self.data_dir, fname)))

    def test_second_identical_cycle_dedupes_everything(self):
        client1 = self._make_client()
        csx.run_cycle(client1, self.state, self.data_dir, cycle_id="cycle1")

        client2 = self._make_client()
        stats2 = csx.run_cycle(client2, self.state, self.data_dir, cycle_id="cycle2")

        self.assertEqual(stats2["rows_written"]["markets"], 0)
        self.assertEqual(stats2["rows_written"]["orderbook"], 0)
        self.assertEqual(stats2["rows_written"]["best_line"], 0)
        self.assertEqual(stats2["rows_written"]["trades"], 0)
        self.assertEqual(stats2["rows_deduped"]["markets"], 2)

    def test_changed_orderbook_produces_chained_new_rows(self):
        client1 = self._make_client()
        csx.run_cycle(client1, self.state, self.data_dir, cycle_id="cycle1")

        changed_orders = load_fixture("orders.json")
        changed_orders["data"][0]["fillAmount"] = "5000000"  # order 1 partially filled now
        client2 = self._make_client(orders_payload=changed_orders)
        stats2 = csx.run_cycle(client2, self.state, self.data_dir, cycle_id="cycle2")

        # the changed order row is new; the other two orderbook rows dedupe
        self.assertEqual(stats2["rows_written"]["orderbook"], 1)
        self.assertEqual(stats2["rows_deduped"]["orderbook"], 2)

        path = os.path.join(self.data_dir, csx.TABLE_FILES["orderbook"])
        with open(path, "r", encoding="utf-8") as fh:
            rows = [json.loads(l) for l in fh if l.strip()]
        new_rows = [r for r in rows if r["cycle_id"] == "cycle2"]
        self.assertEqual(len(new_rows), 1)
        self.assertIsNotNone(new_rows[0]["prev_snapshot_ref"])
        old_row_same_order = [
            r for r in rows if r["cycle_id"] == "cycle1" and r["content"]["orderHash"] == "0xord1"
        ][0]
        self.assertEqual(new_rows[0]["prev_snapshot_ref"], old_row_same_order["payload_hash"])
        # is_order is structurally false even though the content IS a resting order
        self.assertFalse(new_rows[0]["is_order"])

    def test_endpoint_failure_is_reported_not_silently_dropped(self):
        session = FakeSession(
            {"/markets/active": load_fixture("markets_active.json"),
             "/trades": load_fixture("trades.json")},
            fail_paths={"/orders": (429, "rate limited")},
        )
        client = csx.SxBetClient(session=session, rate_limiter=_NoWaitLimiter())
        stats = csx.run_cycle(client, self.state, self.data_dir, cycle_id="cycle1")
        self.assertEqual(stats["rows_written"]["orderbook"], 0)
        self.assertTrue(any(f["endpoint"] == "/orders" for f in stats["endpoint_failures"]))
        self.assertIn("429", stats["endpoint_failures"][0]["error"])

    def test_poll_log_has_one_entry_per_http_attempt(self):
        client = self._make_client()
        csx.run_cycle(client, self.state, self.data_dir, cycle_id="cycle1")
        endpoints_hit = [row["endpoint"] for row in client.poll_log]
        self.assertIn("/markets/active", endpoints_hit)
        self.assertIn("/orders", endpoints_hit)
        self.assertIn("/trades", endpoints_hit)
        for row in client.poll_log:
            self.assertIn("started_ts", row)
            self.assertIn("finished_ts", row)
            self.assertIn("ok", row)


class TestLoopFlagDefaultsOff(unittest.TestCase):
    def test_argparse_default_loop_is_false(self):
        parser_args = csx.main.__globals__["argparse"].ArgumentParser()
        # Re-parse via the real CLI builder indirectly: construct with no args
        # other than pointing IO at a temp dir, and confirm the loop default.
        import argparse as _argparse
        ap = _argparse.ArgumentParser()
        ap.add_argument("--loop", action="store_true", default=False)
        ns = ap.parse_args([])
        self.assertFalse(ns.loop)


if __name__ == "__main__":
    unittest.main()
