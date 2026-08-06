#!/usr/bin/env python3
"""D036 point 2 coverage re-audit.

Re-audits the props archive (props_discovery.jsonl) and the featured archive
(featured_backfill.jsonl) into the seven separate counts D036 names.  The
phrase "game days" is BANNED (D036 point 2): the only calendar-level count
emitted is `unique_calendar_dates`, which is literally the number of distinct
UTC calendar dates involved.

Reads the archives READ-ONLY.  Emits data_coverage.json next to this script.

Normalized prop row definition (stated, not implied): one row per
(event_id, snapshot_requested_ts, bookmaker_key, market_key, player, point, side).
A player-game is a distinct (player_description, event_id) pair.
A market family is a distinct vendor market key (e.g. player_points).
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROPS = "C:/Users/jgallagher/wnba-betting-model/data/market_snapshots/historical/props_discovery.jsonl"
DEFAULT_FEATURED = "C:/Users/jgallagher/wnba-betting-model/data/market_snapshots/historical/featured_backfill.jsonl"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def audit_props(path):
    dates_queried = set()
    dates_with_lines = set()
    event_ids = set()            # events with >=1 bookmaker prop line
    event_ids_queried = set()
    snapshot_pairs = set()       # (event_id, requested_ts) with >=1 line
    player_games = set()         # (player_description, event_id)
    books = set()
    market_families = set()
    normalized_rows = 0
    lines_total = 0
    lines_with_payload = 0
    min_day, max_day = None, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            lines_total += 1
            r = json.loads(line)
            day = r.get("day")
            if day:
                dates_queried.add(day)
                min_day = day if min_day is None or day < min_day else min_day
                max_day = day if max_day is None or day > max_day else max_day
            eid = r.get("event_id")
            if eid:
                event_ids_queried.add(eid)
            payload = r.get("payload")
            if not payload or not payload.get("bookmakers"):
                continue
            lines_with_payload += 1
            got_line = False
            for bk in payload["bookmakers"]:
                bkey = bk.get("key")
                for mkt in bk.get("markets", []):
                    mkey = mkt.get("key")
                    for out in mkt.get("outcomes", []):
                        got_line = True
                        books.add(bkey)
                        market_families.add(mkey)
                        player = out.get("description")
                        if player:
                            player_games.add((player, eid))
                        normalized_rows += 1
            if got_line:
                if day:
                    dates_with_lines.add(day)
                if eid:
                    event_ids.add(eid)
                    snapshot_pairs.add((eid, r.get("requested_ts")))
    return {
        "archive": "props_discovery",
        "path": path,
        "sha256": sha256_file(path),
        "read_only": True,
        "banned_phrase_notice": "the phrase 'game days' is banned per D036 point 2; only literal unique calendar dates are counted",
        "jsonl_lines_total": lines_total,
        "jsonl_lines_with_nonempty_payload": lines_with_payload,
        "seven_counts": {
            "unique_calendar_dates_with_prop_lines": len(dates_with_lines),
            "unique_event_ids_with_prop_lines": len(event_ids),
            "unique_event_snapshot_pairs_with_prop_lines": len(snapshot_pairs),
            "unique_player_games": len(player_games),
            "normalized_prop_rows": normalized_rows,
            "unique_books": len(books),
            "unique_market_families": len(market_families),
        },
        "context_counts": {
            "unique_calendar_dates_queried": len(dates_queried),
            "unique_event_ids_queried": len(event_ids_queried),
        },
        "books": sorted(books),
        "market_families": sorted(market_families),
        "date_range_queried": [min_day, max_day],
        "date_range_with_lines": [min(dates_with_lines) if dates_with_lines else None,
                                  max(dates_with_lines) if dates_with_lines else None],
        "row_definition": "one normalized prop row per (event_id, snapshot_requested_ts, bookmaker, market, player, point, side); a player-game is a distinct (player, event_id) pair",
        "provenance_class": "T1_VENDOR_ASSERTED",
        "tier_caveat": "vendor-asserted, unwitnessed snapshot timestamps; counts describe what the vendor returned on 2026-08-06 about past instants, not what was observable at any pregame moment",
    }


def audit_featured(path):
    dates = set()                 # UTC calendar date of requested_ts
    dates_with_events = set()
    event_ids = set()
    snapshot_pairs = set()        # (event_id, requested_ts)
    books = set()
    market_families = set()
    normalized_rows = 0           # outcome-level rows
    snapshots_total = 0
    snapshots_nonempty = 0
    min_c, max_c = None, None     # commence_time range of events seen
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            snapshots_total += 1
            r = json.loads(line)
            day = (r.get("requested_ts") or "")[:10]
            if day:
                dates.add(day)
            payload = r.get("payload") or []
            if payload:
                snapshots_nonempty += 1
                if day:
                    dates_with_events.add(day)
            for ev in payload:
                eid = ev.get("id")
                event_ids.add(eid)
                snapshot_pairs.add((eid, r.get("requested_ts")))
                ct = ev.get("commence_time")
                if ct:
                    min_c = ct if min_c is None or ct < min_c else min_c
                    max_c = ct if max_c is None or ct > max_c else max_c
                for bk in ev.get("bookmakers", []):
                    books.add(bk.get("key"))
                    for mkt in bk.get("markets", []):
                        market_families.add(mkt.get("key"))
                        normalized_rows += len(mkt.get("outcomes", []))
    return {
        "archive": "featured_backfill",
        "path": path,
        "sha256": sha256_file(path),
        "read_only": True,
        "banned_phrase_notice": "the phrase 'game days' is banned per D036 point 2; only literal unique calendar dates are counted",
        "snapshot_lines_total": snapshots_total,
        "snapshot_lines_with_events": snapshots_nonempty,
        "seven_counts": {
            "unique_calendar_dates_requested": len(dates),
            "unique_calendar_dates_with_events": len(dates_with_events),
            "unique_event_ids": len(event_ids),
            "unique_event_snapshot_pairs": len(snapshot_pairs),
            "normalized_outcome_rows": normalized_rows,
            "unique_books": len(books),
            "unique_market_families": len(market_families),
        },
        "books": sorted(b for b in books if b),
        "market_families": sorted(m for m in market_families if m),
        "commence_time_range_of_events": [min_c, max_c],
        "row_definition": "one normalized outcome row per (event, snapshot_requested_ts, bookmaker, market, outcome)",
        "provenance_class": "T1_VENDOR_ASSERTED",
        "tier_caveat": "vendor-asserted, unwitnessed snapshot timestamps; two vendor-asserted request classes per calendar date (EARLY ~16:00Z, LATE ~23:30Z); never opening or closing lines",
    }


def main(argv):
    props = argv[1] if len(argv) > 1 else DEFAULT_PROPS
    featured = argv[2] if len(argv) > 2 else DEFAULT_FEATURED
    out_path = argv[3] if len(argv) > 3 else os.path.join(HERE, "data_coverage.json")
    doc = {
        "schema": "market_program/SCOREBOARD/data_coverage/1",
        "decision_authority": "D036_SCOREBOARD_MEASUREMENT_SEMANTICS point 2",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "experiments/market_program/SCOREBOARD/audit_coverage.py",
        "props_archive": audit_props(props),
        "featured_archive": audit_featured(featured),
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=False)
        f.write("\n")
    print("wrote", out_path)


if __name__ == "__main__":
    main(sys.argv)
