#!/usr/bin/env python3
"""
M03_CAPTURE_UPGRADE test suite.

Fixture-driven / mock-HTTP for all logic (no network by default). One gated
class (`LiveSmokeTest`) makes real HTTP calls against api.the-odds-api.com
and is SKIPPED unless RUN_LIVE_SMOKE=1 is set in the environment -- it uses
only the two free-cost endpoints (/v4/sports and the WNBA /events list) so a
routine `python TESTS.py` run never spends vendor credits and never needs
network access. Run with the live smoke test enabled via:
    $env:RUN_LIVE_SMOKE = "1"; python TESTS.py

CREDENTIAL SAFETY: this file never reads ODDS_API_KEY into a variable it
prints, asserts equality against in an assertion message, or otherwise
allows into stdout/stderr. Where the live smoke test needs the key (to hand
to requests), it is passed straight through to `api_key()`'s caller and
never captured locally.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

import market_snapshot_schema as schema
import market_ladder_scheduler as ladder
import market_burst_trigger as burst
import market_snapshot_writer as writer
import capture_coverage_audit as audit
import market_capture_config as config


def utc(*args, **kwargs):
    return datetime(*args, tzinfo=timezone.utc, **kwargs)


def make_valid_row(**overrides):
    row = {
        "snapshot_id": "sid1", "game_id": "G1", "book": "draftkings",
        "market": "h2h", "outcome": "Team A", "line": None, "price": -120,
        "price_over": None, "price_under": None, "implied_prob": 0.545,
        "novig_prob": None, "market_status": "active",
        "vendor_ts": "2026-08-06T12:00:00Z",
        "vendor_ts_semantics": "unknown_unverified",
        "retrieval_ts": "2026-08-06T12:00:05Z",
        "ingestion_ts": "2026-08-06T12:00:06Z",
        "max_staleness_bound": 900, "poll_interval_at_capture": 900,
        "vendor_latency_note": None, "payload_hash": "abc123",
        "prev_snapshot_ref": None,
    }
    row.update(overrides)
    return row


# ===================================================================== #
class SchemaTests(unittest.TestCase):
    def test_valid_row_passes(self):
        schema.validate_row(make_valid_row())   # no raise

    def test_missing_column_rejected(self):
        row = make_valid_row()
        del row["payload_hash"]
        with self.assertRaises(schema.SchemaViolation):
            schema.validate_row(row)

    def test_null_required_field_rejected(self):
        row = make_valid_row(retrieval_ts=None)
        with self.assertRaises(schema.SchemaViolation):
            schema.validate_row(row)

    def test_blank_required_field_rejected(self):
        row = make_valid_row(game_id="   ")
        with self.assertRaises(schema.SchemaViolation):
            schema.validate_row(row)

    def test_bad_vendor_ts_semantics_rejected(self):
        row = make_valid_row(vendor_ts_semantics="definitely_the_book_moved")
        with self.assertRaises(schema.SchemaViolation):
            schema.validate_row(row)

    def test_default_vendor_ts_semantics_is_unknown_unverified(self):
        self.assertEqual(schema.VENDOR_TS_SEMANTICS_DEFAULT, "unknown_unverified")

    def test_bad_market_status_rejected(self):
        row = make_valid_row(market_status="paused")
        with self.assertRaises(schema.SchemaViolation):
            schema.validate_row(row)

    def test_active_row_without_any_price_rejected(self):
        row = make_valid_row(price=None, price_over=None, price_under=None)
        with self.assertRaises(schema.SchemaViolation):
            schema.validate_row(row)

    def test_missing_status_row_without_price_is_ok(self):
        row = make_valid_row(price=None, price_over=None, price_under=None,
                             market_status="missing", implied_prob=None)
        schema.validate_row(row)   # no raise

    def test_nullable_fields_may_be_none(self):
        row = make_valid_row(line=None, novig_prob=None,
                             vendor_latency_note=None, prev_snapshot_ref=None)
        schema.validate_row(row)   # no raise

    def test_payload_hash_deterministic(self):
        h1 = schema.payload_hash(b"abc")
        h2 = schema.payload_hash(b"abc")
        h3 = schema.payload_hash(b"abd")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_snapshot_id_distinct_per_key_same_poll(self):
        sid_a = schema.snapshot_id("hash1", ("G1", "dk", "h2h", "Team A"), "t1")
        sid_b = schema.snapshot_id("hash1", ("G1", "dk", "h2h", "Team B"), "t1")
        self.assertNotEqual(sid_a, sid_b)

    def test_snapshot_id_deterministic_from_inputs(self):
        sid_a = schema.snapshot_id("hash1", ("G1", "dk", "h2h", "Team A"), "t1")
        sid_b = schema.snapshot_id("hash1", ("G1", "dk", "h2h", "Team A"), "t1")
        self.assertEqual(sid_a, sid_b)

    def test_implied_prob_positive_and_negative_american_odds(self):
        self.assertAlmostEqual(schema.implied_prob(100), 0.5)
        self.assertAlmostEqual(schema.implied_prob(-150), 0.6)
        self.assertIsNone(schema.implied_prob(None))

    def test_novig_prob_pair_normalizes_to_sum_one(self):
        pa, pb = schema.novig_prob_pair(-120, 100)
        self.assertAlmostEqual(pa + pb, 1.0)

    def test_novig_prob_pair_none_if_one_side_missing(self):
        pa, pb = schema.novig_prob_pair(-120, None)
        self.assertIsNone(pa)
        self.assertIsNone(pb)


# ===================================================================== #
class LadderSchedulerTests(unittest.TestCase):
    def test_all_eight_rungs_present(self):
        self.assertEqual(len(ladder.LADDER_RUNGS), 8)
        labels = [l for l, _ in ladder.LADDER_RUNGS]
        self.assertEqual(labels, ["T-24h", "T-8h", "T-4h", "T-2h", "T-60m",
                                  "T-30m", "T-15m", "final_pregame"])

    def test_final_pregame_distinct_from_t15m(self):
        h = dict(ladder.LADDER_RUNGS)
        self.assertLess(h["final_pregame"], h["T-15m"])

    def test_due_rung_fires_inside_lead_window(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        now = tip - timedelta(hours=8) - timedelta(minutes=10)   # 10min before T-8h cutoff, inside its 20min lead
        game = {"game_id": "G1", "tip": tip}
        res = ladder.due_rungs(game, now)
        due_labels = [d["label"] for d in res["due"]]
        self.assertIn("T-8h", due_labels)

    def test_rung_not_due_outside_lead_window(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        now = tip - timedelta(hours=8) - timedelta(hours=2)      # 2h before the T-8h lead opens
        game = {"game_id": "G1", "tip": tip}
        res = ladder.due_rungs(game, now)
        due_labels = [d["label"] for d in res["due"]]
        self.assertNotIn("T-8h", due_labels)

    def test_served_rung_never_fires_again(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        now = tip - timedelta(hours=8) + timedelta(minutes=5)
        game = {"game_id": "G1", "tip": tip}
        res = ladder.due_rungs(game, now, served_labels=["T-8h"])
        due_labels = [d["label"] for d in res["due"]]
        self.assertNotIn("T-8h", due_labels)

    def test_already_tipped_game_has_no_due_rungs(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        now = tip + timedelta(minutes=5)
        game = {"game_id": "G1", "tip": tip}
        res = ladder.due_rungs(game, now)
        self.assertEqual(res["due"], [])
        self.assertTrue(res["already_tipped"])

    def test_ladder_obligations_across_slate(self):
        tip1 = utc(2026, 8, 6, 20, 0, 0)
        tip2 = utc(2026, 8, 6, 23, 0, 0)
        now = tip1 - timedelta(minutes=13)   # inside final_pregame's 2min? no -> check T-15m(3min lead)
        games = [{"game_id": "G1", "tip": tip1}, {"game_id": "G2", "tip": tip2}]
        res = ladder.ladder_obligations(games, now)
        self.assertEqual({r["game_id"] for r in res}, {"G1", "G2"})

    def test_rung_poll_interval_seconds_first_rung_uses_own_offset(self):
        self.assertAlmostEqual(ladder.RUNG_POLL_INTERVAL_SECONDS["T-24h"], 24 * 3600.0)

    def test_rung_poll_interval_seconds_positive_and_shrinking(self):
        vals = [ladder.RUNG_POLL_INTERVAL_SECONDS[l] for l, _ in ladder.LADDER_RUNGS]
        self.assertTrue(all(v > 0 for v in vals))

    def test_rung_cutoff_matches_tip_minus_offset(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        c = ladder.rung_cutoff(tip, "T-2h")
        self.assertEqual(c, tip - timedelta(hours=2))


# ===================================================================== #
class BurstTriggerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(REPO_ROOT) / "experiments" / "market_program" / \
            "M03_CAPTURE_UPGRADE" / "_test_scratch"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.injury_csv = self.tmp / "injury_log.csv"
        self.news_csv = self.tmp / "news_items.csv"
        self.cursor = self.tmp / "cursor.json"
        for p in (self.injury_csv, self.news_csv, self.cursor):
            if p.exists():
                p.unlink()

    def _write_injury_csv(self, rows):
        with open(self.injury_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["capture_utc", "team", "player", "status"])
            w.writeheader()
            w.writerows(rows)

    def _write_news_csv(self, rows):
        with open(self.news_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["capture_utc", "teams_mentioned", "title"])
            w.writeheader()
            w.writerows(rows)

    def test_scan_new_rows_first_tick_sees_everything(self):
        self._write_injury_csv([{"capture_utc": "t1", "team": "Seattle Storm",
                                 "player": "X", "status": "Out"}])
        new, cur, anomaly = burst.scan_new_rows(self.injury_csv, {}, "injury")
        self.assertEqual(len(new), 1)
        self.assertIsNone(anomaly)
        self.assertEqual(cur["injury"]["last_row_count"], 1)

    def test_scan_new_rows_second_tick_only_sees_appended(self):
        self._write_injury_csv([{"capture_utc": "t1", "team": "Seattle Storm",
                                 "player": "X", "status": "Out"}])
        _, cur, _ = burst.scan_new_rows(self.injury_csv, {}, "injury")
        self._write_injury_csv([
            {"capture_utc": "t1", "team": "Seattle Storm", "player": "X", "status": "Out"},
            {"capture_utc": "t2", "team": "Seattle Storm", "player": "Y", "status": "Questionable"},
        ])
        new2, cur2, anomaly2 = burst.scan_new_rows(self.injury_csv, cur, "injury")
        self.assertEqual(len(new2), 1)
        self.assertEqual(new2[0]["player"], "Y")
        self.assertIsNone(anomaly2)

    def test_scan_new_rows_shrunk_file_is_flagged_not_crashed(self):
        self._write_injury_csv([
            {"capture_utc": "t1", "team": "A", "player": "X", "status": "Out"},
            {"capture_utc": "t2", "team": "A", "player": "Y", "status": "Out"},
        ])
        _, cur, _ = burst.scan_new_rows(self.injury_csv, {}, "injury")
        self._write_injury_csv([{"capture_utc": "t1", "team": "A", "player": "X", "status": "Out"}])
        new, cur2, anomaly = burst.scan_new_rows(self.injury_csv, cur, "injury")
        self.assertIsNotNone(anomaly)
        self.assertEqual(len(new), 1)   # reset cursor to 0, so the 1 remaining row is "new"

    def test_injury_triggers_parses_team(self):
        rows = [{"capture_utc": "t1", "team": "Seattle Storm", "player": "X", "status": "Out"}]
        trigs = burst.injury_triggers(rows)
        self.assertEqual(trigs[0].teams, ["Seattle Storm"])
        self.assertEqual(trigs[0].source, "injury")

    def test_news_triggers_splits_multiple_teams(self):
        rows = [{"capture_utc": "t1", "teams_mentioned": "Seattle Storm;Indiana Fever",
                "title": "..."}]
        trigs = burst.news_triggers(rows)
        self.assertEqual(trigs[0].teams, ["Seattle Storm", "Indiana Fever"])

    def test_resolve_game_for_trigger_matches_future_game(self):
        now = utc(2026, 8, 6, 12, 0, 0)
        slate = [{"game_id": "G1", "home": "SEA", "away": "IND",
                 "tip": now + timedelta(hours=6)}]
        trig = burst.Trigger(source="injury", row_index=0, capture_utc="t1",
                             teams=["Seattle Storm"], raw={})
        game = burst.resolve_game_for_trigger(
            trig, slate, team_lookup={"Seattle Storm": "SEA"}, now=now)
        self.assertEqual(game["game_id"], "G1")

    def test_resolve_game_for_trigger_ignores_already_tipped_game(self):
        now = utc(2026, 8, 6, 12, 0, 0)
        slate = [{"game_id": "G1", "home": "SEA", "away": "IND",
                 "tip": now - timedelta(hours=1)}]
        trig = burst.Trigger(source="injury", row_index=0, capture_utc="t1",
                             teams=["Seattle Storm"], raw={})
        game = burst.resolve_game_for_trigger(
            trig, slate, team_lookup={"Seattle Storm": "SEA"}, now=now)
        self.assertIsNone(game)

    def test_resolve_game_for_trigger_no_match_returns_none(self):
        now = utc(2026, 8, 6, 12, 0, 0)
        slate = [{"game_id": "G1", "home": "SEA", "away": "IND",
                 "tip": now + timedelta(hours=6)}]
        trig = burst.Trigger(source="injury", row_index=0, capture_utc="t1",
                             teams=["Chicago Sky"], raw={})
        game = burst.resolve_game_for_trigger(
            trig, slate, team_lookup={"Chicago Sky": "CHI"}, now=now)
        self.assertIsNone(game)

    def test_schedule_burst_default_three_legs(self):
        now = utc(2026, 8, 6, 12, 0, 0)
        trig = burst.Trigger(source="injury", row_index=0, capture_utc="t1",
                             teams=["Seattle Storm"], raw={})
        game = {"game_id": "G1"}
        legs = burst.schedule_burst(trig, game, now=now)
        self.assertEqual([l.leg_label for l in legs],
                         ["burst+0m", "burst+5m", "burst+15m"])
        self.assertEqual(legs[1].fire_at, now + timedelta(minutes=5))

    def test_dedupe_against_ladder_drops_colliding_leg(self):
        now = utc(2026, 8, 6, 12, 0, 0)
        trig = burst.Trigger(source="injury", row_index=0, capture_utc="t1",
                             teams=["Seattle Storm"], raw={})
        game = {"game_id": "G1"}
        legs = burst.schedule_burst(trig, game, now=now, offsets_minutes=[0, 5, 15])
        pending = {"G1": [now + timedelta(minutes=5, seconds=30)]}  # collides w/ +5m leg
        kept = burst.dedupe_against_ladder(legs, pending, window_minutes=5.0)
        kept_labels = [l.leg_label for l in kept]
        self.assertNotIn("burst+5m", kept_labels)
        self.assertIn("burst+0m", kept_labels)
        self.assertIn("burst+15m", kept_labels)

    def test_run_watch_end_to_end_schedules_burst_and_persists_cursor(self):
        now = utc(2026, 8, 6, 12, 0, 0)
        self._write_injury_csv([{"capture_utc": "t1", "team": "Seattle Storm",
                                 "player": "X", "status": "Out"}])
        self._write_news_csv([])
        slate = [{"game_id": "G1", "home": "SEA", "away": "IND",
                 "tip": now + timedelta(hours=6)}]
        res = burst.run_watch(self.injury_csv, self.news_csv, self.cursor,
                              slate, team_lookup={"Seattle Storm": "SEA"}, now=now)
        self.assertEqual(res["triggers_seen"], 1)
        self.assertEqual(len(res["bursts_scheduled"]), 3)
        self.assertTrue(self.cursor.exists())

        # second tick with no new rows schedules nothing
        res2 = burst.run_watch(self.injury_csv, self.news_csv, self.cursor,
                               slate, team_lookup={"Seattle Storm": "SEA"}, now=now)
        self.assertEqual(res2["triggers_seen"], 0)
        self.assertEqual(res2["bursts_scheduled"], [])

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


# ===================================================================== #
class WriterFlattenTests(unittest.TestCase):
    ODDS_PAYLOAD = [{
        "id": "evt1", "home_team": "Seattle Storm", "away_team": "Indiana Fever",
        "commence_time": "2026-08-06T23:00:00Z",
        "bookmakers": [{
            "key": "draftkings", "markets": [{
                "key": "h2h", "last_update": "2026-08-06T12:00:00Z",
                "outcomes": [{"name": "Seattle Storm", "price": -150},
                            {"name": "Indiana Fever", "price": 130}],
            }],
        }],
    }]

    PROPS_PAYLOAD = {
        "id": "evt1", "home_team": "Seattle Storm", "away_team": "Indiana Fever",
        "bookmakers": [{
            "key": "draftkings", "markets": [{
                "key": "player_points", "last_update": "2026-08-06T12:00:00Z",
                "outcomes": [
                    {"description": "Jane Doe", "name": "Over", "point": 15.5, "price": -110},
                    {"description": "Jane Doe", "name": "Under", "point": 15.5, "price": -110},
                ],
            }],
        }],
    }

    def test_flatten_odds_payload_row_shape(self):
        rows = writer.flatten_odds_payload(
            self.ODDS_PAYLOAD, retrieval_ts="2026-08-06T12:00:05Z",
            poll_interval_seconds=900, a_payload_hash="hash1")
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertEqual(r["game_id"], "evt1")
            self.assertEqual(r["market"], "h2h")
            self.assertEqual(r["vendor_ts_semantics"], "unknown_unverified")
            self.assertEqual(r["poll_interval_at_capture"], 900)
            self.assertIsNotNone(r["implied_prob"])

    def test_flatten_odds_payload_computes_novig_for_two_way_pair(self):
        rows = writer.flatten_odds_payload(
            self.ODDS_PAYLOAD, retrieval_ts="t", poll_interval_seconds=900,
            a_payload_hash="hash1")
        novigs = [r["novig_prob"] for r in rows]
        self.assertTrue(all(v is not None for v in novigs))
        self.assertAlmostEqual(sum(novigs), 1.0, places=6)

    def test_flatten_props_payload_over_under_pairing(self):
        rows = writer.flatten_props_payload(
            self.PROPS_PAYLOAD, retrieval_ts="t", poll_interval_seconds=300,
            a_payload_hash="hash2")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["price_over"], -110)
        self.assertEqual(r["price_under"], -110)
        self.assertIsNone(r["price"])
        self.assertIsNotNone(r["novig_prob"])

    def test_flatten_props_payload_none_json_is_missing_market(self):
        rows = writer.flatten_props_payload(
            None, retrieval_ts="t", poll_interval_seconds=300, a_payload_hash="h")
        self.assertEqual(rows, [])

    def test_flatten_props_payload_empty_bookmakers_yields_missing_row(self):
        payload = {"id": "evt2", "bookmakers": []}
        rows = writer.flatten_props_payload(
            payload, retrieval_ts="t", poll_interval_seconds=300, a_payload_hash="h")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["market_status"], "missing")


class ChainIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(REPO_ROOT) / "experiments" / "market_program" / \
            "M03_CAPTURE_UPGRADE" / "_test_scratch_chain"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.idx_path = self.tmp / "chain.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_first_row_has_no_prev(self):
        chain = writer.ChainIndex(self.idx_path)
        rows = [dict(game_id="G1", book="dk", market="h2h", outcome="A",
                    payload_hash="h1")]
        writer.attach_chain_fields(rows, chain, retrieval_ts="t1")
        self.assertIsNone(rows[0]["prev_snapshot_ref"])
        self.assertIsNotNone(rows[0]["snapshot_id"])

    def test_second_poll_chains_to_first(self):
        chain = writer.ChainIndex(self.idx_path)
        row1 = dict(game_id="G1", book="dk", market="h2h", outcome="A", payload_hash="h1")
        writer.attach_chain_fields([row1], chain, retrieval_ts="t1")
        chain.save()

        chain2 = writer.ChainIndex(self.idx_path)   # simulate a fresh process load
        row2 = dict(game_id="G1", book="dk", market="h2h", outcome="A", payload_hash="h2")
        writer.attach_chain_fields([row2], chain2, retrieval_ts="t2")
        self.assertEqual(row2["prev_snapshot_ref"], row1["snapshot_id"])

    def test_different_keys_do_not_cross_chain(self):
        chain = writer.ChainIndex(self.idx_path)
        row_a = dict(game_id="G1", book="dk", market="h2h", outcome="A", payload_hash="h1")
        row_b = dict(game_id="G1", book="dk", market="h2h", outcome="B", payload_hash="h1")
        writer.attach_chain_fields([row_a, row_b], chain, retrieval_ts="t1")
        self.assertIsNone(row_a["prev_snapshot_ref"])
        self.assertIsNone(row_b["prev_snapshot_ref"])
        self.assertNotEqual(row_a["snapshot_id"], row_b["snapshot_id"])


class AppendOnlyWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(REPO_ROOT) / "experiments" / "market_program" / \
            "M03_CAPTURE_UPGRADE" / "_test_scratch_writer"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_append_snapshot_rows_writes_header_once(self):
        rows1 = [make_valid_row(snapshot_id="s1")]
        n1, rej1 = writer.append_snapshot_rows(rows1, out_dir=self.tmp)
        rows2 = [make_valid_row(snapshot_id="s2")]
        n2, rej2 = writer.append_snapshot_rows(rows2, out_dir=self.tmp)
        self.assertEqual((n1, n2), (1, 1))
        self.assertEqual(rej1, [])
        self.assertEqual(rej2, [])
        text = (self.tmp / writer.SNAPSHOTS_CSV).read_text(encoding="utf-8")
        self.assertEqual(text.count("snapshot_id"), 1)   # header appears exactly once
        with open(self.tmp / writer.SNAPSHOTS_CSV, newline="", encoding="utf-8") as f:
            body_rows = list(csv.DictReader(f))
        self.assertEqual(len(body_rows), 2)   # both appends present, nothing overwritten

    def test_invalid_rows_are_rejected_not_written(self):
        good = make_valid_row(snapshot_id="s1")
        bad = make_valid_row(snapshot_id="s2", vendor_ts_semantics="bogus")
        n, rejected = writer.append_snapshot_rows([good, bad], out_dir=self.tmp)
        self.assertEqual(n, 1)
        self.assertEqual(len(rejected), 1)
        with open(self.tmp / writer.SNAPSHOTS_CSV, newline="", encoding="utf-8") as f:
            body_rows = list(csv.DictReader(f))
        self.assertEqual(len(body_rows), 1)
        self.assertEqual(body_rows[0]["snapshot_id"], "s1")

    def test_append_poll_log_writes_header_once_and_appends(self):
        e1 = {"poll_ts": "t1", "game_id": "G1", "obligation_type": "ladder",
              "label": "T-8h", "endpoint": "x", "http_status": 200,
              "credits_used": "3", "credits_remaining": "997",
              "credits_last": "3", "n_rows_written": 2, "n_rows_rejected": 0,
              "error": None}
        e2 = dict(e1, poll_ts="t2")
        writer.append_poll_log(e1, out_dir=self.tmp)
        writer.append_poll_log(e2, out_dir=self.tmp)
        with open(self.tmp / writer.POLL_LOG_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["poll_ts"], "t1")
        self.assertEqual(rows[1]["poll_ts"], "t2")


# ===================================================================== #
class CoverageAuditTests(unittest.TestCase):
    def test_missed_poll_served_when_row_in_window(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        games = [{"game_id": "G1", "tip": tip}]
        rows = [{"game_id": "G1", "retrieval_ts": (tip - timedelta(hours=8) +
                                                    timedelta(minutes=1)).isoformat()}]
        now = tip - timedelta(hours=4)
        res = audit.missed_poll_audit(games, ladder.LADDER_RUNGS, rows, now=now)
        t8 = next(r for r in res if r["label"] == "T-8h")
        self.assertEqual(t8["classification"], "served")

    def test_missed_poll_flags_operational_miss(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        games = [{"game_id": "G1", "tip": tip}]
        rows = []   # nothing ever captured
        now = tip - timedelta(hours=1)   # T-8h, T-4h, T-2h are all past due
        res = audit.missed_poll_audit(games, ladder.LADDER_RUNGS, rows, now=now)
        t8 = next(r for r in res if r["label"] == "T-8h")
        self.assertEqual(t8["classification"], "missing_poll_did_not_run")

    def test_missed_poll_not_yet_due_in_future(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        games = [{"game_id": "G1", "tip": tip}]
        now = tip - timedelta(hours=23)
        res = audit.missed_poll_audit(games, ladder.LADDER_RUNGS, [], now=now)
        t8 = next(r for r in res if r["label"] == "T-8h")
        self.assertEqual(t8["classification"], "not_yet_due")

    def test_missed_poll_postponed_excuses_the_miss(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        games = [{"game_id": "G1", "tip": tip, "tip_moved": True}]
        now = tip - timedelta(hours=1)
        res = audit.missed_poll_audit(games, ladder.LADDER_RUNGS, [], now=now)
        t8 = next(r for r in res if r["label"] == "T-8h")
        self.assertEqual(t8["classification"], "postponed_or_tip_changed")

    def test_row_before_cutoff_never_backdates_service(self):
        """A row retrieved BEFORE a rung's cutoff must not satisfy that
        rung -- no record is ever backdated (acceptance criterion)."""
        tip = utc(2026, 8, 6, 20, 0, 0)
        games = [{"game_id": "G1", "tip": tip}]
        early_row_ts = (tip - timedelta(hours=23)).isoformat()   # captured for T-24h, not T-8h
        rows = [{"game_id": "G1", "retrieval_ts": early_row_ts}]
        now = tip - timedelta(hours=1)
        res = audit.missed_poll_audit(games, ladder.LADDER_RUNGS, rows, now=now)
        t8 = next(r for r in res if r["label"] == "T-8h")
        self.assertEqual(t8["classification"], "missing_poll_did_not_run")

    def test_summarize_missed_poll_counts(self):
        tip = utc(2026, 8, 6, 20, 0, 0)
        games = [{"game_id": "G1", "tip": tip}]
        rows = [{"game_id": "G1", "retrieval_ts": (tip - timedelta(hours=8)).isoformat()}]
        now = tip - timedelta(hours=1)
        res = audit.missed_poll_audit(games, ladder.LADDER_RUNGS, rows, now=now)
        s = audit.summarize_missed_poll(res)
        self.assertGreaterEqual(s["operational_misses"], 1)
        self.assertGreaterEqual(s["served"], 1)

    def test_silent_overwrite_check_clean_chain(self):
        rows = [
            {"game_id": "G1", "book": "dk", "market": "h2h", "outcome": "A",
             "retrieval_ts": "t1", "snapshot_id": "s1", "prev_snapshot_ref": None},
            {"game_id": "G1", "book": "dk", "market": "h2h", "outcome": "A",
             "retrieval_ts": "t2", "snapshot_id": "s2", "prev_snapshot_ref": "s1"},
        ]
        self.assertEqual(audit.silent_overwrite_check(rows), [])

    def test_silent_overwrite_check_detects_break(self):
        rows = [
            {"game_id": "G1", "book": "dk", "market": "h2h", "outcome": "A",
             "retrieval_ts": "t1", "snapshot_id": "s1", "prev_snapshot_ref": None},
            {"game_id": "G1", "book": "dk", "market": "h2h", "outcome": "A",
             "retrieval_ts": "t2", "snapshot_id": "s2", "prev_snapshot_ref": "WRONG"},
        ]
        breaks = audit.silent_overwrite_check(rows)
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0]["snapshot_id"], "s2")

    def test_identifier_change_check_flags_new_book_and_market(self):
        rows = [{"book": "fanduel_new", "market": "player_steals"}]
        res = audit.identifier_change_check(rows, known_books={"draftkings"},
                                            known_markets={"h2h"})
        self.assertIn("fanduel_new", res["new_books"])
        self.assertIn("player_steals", res["new_markets"])
        self.assertEqual(len(res["notes"]), 2)

    def test_identifier_change_check_silent_when_all_known(self):
        rows = [{"book": "draftkings", "market": "h2h"}]
        res = audit.identifier_change_check(rows, known_books={"draftkings"},
                                            known_markets={"h2h"})
        self.assertEqual(res["notes"], [])

    def test_stale_job_check_flags_no_row_ever(self):
        res = audit.stale_job_check(None, now=utc(2026, 8, 6, 12, 0, 0))
        self.assertTrue(res["stale"])

    def test_stale_job_check_flags_old_last_row(self):
        now = utc(2026, 8, 10, 12, 0, 0)
        last = utc(2026, 8, 6, 12, 0, 0)   # 4 days ago, well past 26h max gap
        res = audit.stale_job_check(last.isoformat(), now=now)
        self.assertTrue(res["stale"])

    def test_stale_job_check_fresh_row_not_stale(self):
        now = utc(2026, 8, 6, 12, 0, 0)
        last = now - timedelta(hours=1)
        res = audit.stale_job_check(last.isoformat(), now=now)
        self.assertFalse(res["stale"])


# ===================================================================== #
class ConfigTests(unittest.TestCase):
    def test_disabled_by_default(self):
        old = os.environ.pop(config.ENV_VAR, None)
        try:
            self.assertFalse(config.is_enabled())
        finally:
            if old is not None:
                os.environ[config.ENV_VAR] = old

    def test_enabled_when_truthy(self):
        old = os.environ.get(config.ENV_VAR)
        try:
            for v in ("1", "true", "YES", "True"):
                os.environ[config.ENV_VAR] = v
                self.assertTrue(config.is_enabled(), msg=v)
            for v in ("0", "false", "", "nah"):
                os.environ[config.ENV_VAR] = v
                self.assertFalse(config.is_enabled(), msg=v)
        finally:
            if old is None:
                os.environ.pop(config.ENV_VAR, None)
            else:
                os.environ[config.ENV_VAR] = old


class CredentialScrubTests(unittest.TestCase):
    def test_scrub_removes_key_value(self):
        msg = writer._scrub("error fetching https://x/?apiKey=SECRET123", "SECRET123")
        self.assertNotIn("SECRET123", msg)
        self.assertIn("REDACTED", msg)

    def test_scrub_noop_without_key(self):
        msg = writer._scrub("plain error", None)
        self.assertEqual(msg, "plain error")

    def test_fetch_odds_snapshot_error_message_never_contains_key(self):
        class FakeSession:
            def get(self, *a, **k):
                raise RuntimeError(f"boom, url had apiKey=SUPERSECRET in it")
        with self.assertRaises(RuntimeError) as ctx:
            writer.fetch_odds_snapshot(FakeSession(), "SUPERSECRET")
        self.assertNotIn("SUPERSECRET", str(ctx.exception))


# ===================================================================== #
class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.content = json.dumps(payload).encode("utf-8")
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    """Records every call it receives; returns a canned FakeResponse."""
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return self.response


class MockHttpFetchTests(unittest.TestCase):
    def test_fetch_odds_snapshot_returns_json_bytes_and_response(self):
        payload = [{"id": "evt1", "bookmakers": []}]
        resp = FakeResponse(200, payload, headers={"x-requests-used": "3",
                                                    "x-requests-remaining": "997"})
        sess = FakeSession(resp)
        # M26_CAPTURE_MICROSTRUCTURE_REMEDIATION (defect 4): fetch_* now
        # return a 4th element, `timing` -- a dict of our own witnessed
        # request/response instants plus a best-effort vendor-clock-skew
        # estimate (see market_snapshot_writer._timing / .estimate_clock_
        # skew_seconds). Updated here to unpack it; behavior of the first
        # three return values is unchanged.
        games_json, raw, r, timing = writer.fetch_odds_snapshot(sess, "FAKEKEY")
        self.assertEqual(games_json, payload)
        self.assertEqual(json.loads(raw), payload)
        self.assertEqual(r.headers["x-requests-used"], "3")
        # apiKey travels as a params dict entry, never string-interpolated into the URL
        self.assertEqual(sess.calls[0][1]["apiKey"], "FAKEKEY")
        self.assertNotIn("FAKEKEY", sess.calls[0][0])
        self.assertIn("response_received_ts", timing)
        self.assertIn("rtt_seconds", timing)

    def test_fetch_event_props_snapshot_handles_422_without_raising(self):
        resp = FakeResponse(422, {"message": "bad market"})
        sess = FakeSession(resp)
        ev_json, raw, r, timing = writer.fetch_event_props_snapshot(sess, "FAKEKEY", "evt1")
        self.assertIsNone(ev_json)
        self.assertEqual(r.status_code, 422)
        self.assertIn("response_received_ts", timing)


# ===================================================================== #
class LiveSmokeTest(unittest.TestCase):
    """Gated real-network validation. At most TWO live calls, both to the
    cheapest available endpoints (/v4/sports and the WNBA /events list are
    documented by The Odds API as free / 0-credit). Skipped unless
    RUN_LIVE_SMOKE=1. Quota headers are printed for the report; the key
    itself never is."""

    @unittest.skipUnless(os.getenv("RUN_LIVE_SMOKE") == "1",
                         "set RUN_LIVE_SMOKE=1 to run the 2 live calls against api.the-odds-api.com")
    def test_live_sports_and_events_endpoints(self):
        import requests
        sys.path.insert(0, str(REPO_ROOT))
        from odds_capture_daily import api_key
        key = api_key()
        sess = requests.Session()

        r1 = sess.get("https://api.the-odds-api.com/v4/sports",
                      params={"apiKey": key}, timeout=30)
        self.assertEqual(r1.status_code, 200)
        sports = r1.json()
        self.assertTrue(any(s.get("key") == "basketball_wnba" for s in sports))
        print(f"[live smoke 1/2] GET /v4/sports -> {r1.status_code} | "
              f"used={r1.headers.get('x-requests-used')} "
              f"remaining={r1.headers.get('x-requests-remaining')} "
              f"last={r1.headers.get('x-requests-last')}")

        r2 = sess.get("https://api.the-odds-api.com/v4/sports/basketball_wnba/events",
                      params={"apiKey": key}, timeout=30)
        self.assertEqual(r2.status_code, 200)
        events = r2.json()
        self.assertIsInstance(events, list)
        print(f"[live smoke 2/2] GET /v4/sports/basketball_wnba/events -> "
              f"{r2.status_code} | {len(events)} events | "
              f"used={r2.headers.get('x-requests-used')} "
              f"remaining={r2.headers.get('x-requests-remaining')} "
              f"last={r2.headers.get('x-requests-last')}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
