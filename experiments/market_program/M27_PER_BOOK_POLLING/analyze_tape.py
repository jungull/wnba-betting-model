#!/usr/bin/env python3
"""
M27_PER_BOOK_POLLING -- pre-implementation tape analysis.

Reads the live tape at the DATA worktree root
(C:/Users/jgallagher/wnba-betting-model/data/market_snapshots/) directly --
never re-derives numbers by hand. Produces the two inputs the scope
declaration needs:

  1. Per-book row/change density across the existing tape -> which 2-3 books
     are the densest-covered (justifies the declared book subset).
  2. A per-game tip-time estimate (back-computed from market_ladder_scheduler
     rung labels recorded in poll_log.csv, since snapshots.csv itself carries
     no commence_time column) -> bucket every observed price CHANGE by hours-
     before-tip, to justify the declared pre-tip polling window from where
     movement actually concentrates in this tape.

Run: python analyze_tape.py   (from this directory; stdlib only)
Writes: tape_analysis.json (this directory)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_ROOT = Path(r"C:\Users\jgallagher\wnba-betting-model")
SNAP_DIR = DATA_ROOT / "data" / "market_snapshots"
sys.path.insert(0, str(DATA_ROOT))

import market_ladder_scheduler as ladder  # noqa: E402

RUNG_HOURS = dict(ladder.LADDER_RUNGS)


def _parse_ts(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_snapshots():
    path = SNAP_DIR / "snapshots.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_poll_log():
    path = SNAP_DIR / "poll_log.csv"
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_internal_to_vendor_map(poll_rows):
    """poll_log.csv's `game_id` column is OUR internal id (set once at the
    top of _poll_and_write and never overwritten for the log entry); the
    props-endpoint URL embeds the VENDOR's event id
    (.../events/<vendor_id>/odds). snapshots.csv's own `game_id` column is
    the VENDOR id (M26 defect-1 fix). Build the mapping from the URL, not by
    guessing."""
    mapping = {}
    for r in poll_rows:
        ep = r.get("endpoint", "")
        if "/events/" in ep and ep.endswith("/odds"):
            vendor_id = ep.split("/events/")[1].split("/odds")[0]
            internal_id = r.get("game_id")
            if internal_id and internal_id != "nan":
                mapping[internal_id] = vendor_id
    return mapping


def estimate_tip_times(poll_rows, internal_to_vendor):
    """For every (internal game_id, label) poll row, back-compute an
    implied tip time = poll_ts + hours_before_tip(label). Average across all
    labels observed for a game to get one tip estimate per vendor event id.
    Also report the spread (max-min) across labels as a sanity check on how
    tight the ladder's actual firing was around its intended cutoff."""
    per_game_estimates = defaultdict(list)
    for r in poll_rows:
        label = r.get("label")
        if label not in RUNG_HOURS:
            continue
        internal_id = r.get("game_id")
        vendor_id = internal_to_vendor.get(internal_id)
        if not vendor_id:
            continue
        try:
            poll_ts = _parse_ts(r["poll_ts"])
        except (ValueError, KeyError):
            continue
        implied_tip = poll_ts + timedelta(hours=RUNG_HOURS[label])
        per_game_estimates[vendor_id].append((label, poll_ts, implied_tip))

    tip_by_vendor_id = {}
    spread_by_vendor_id = {}
    for vendor_id, obs in per_game_estimates.items():
        tips = [t for (_l, _p, t) in obs]
        avg_epoch = sum(t.timestamp() for t in tips) / len(tips)
        avg_tip = datetime.fromtimestamp(avg_epoch, tz=timezone.utc)
        tip_by_vendor_id[vendor_id] = avg_tip
        spread_by_vendor_id[vendor_id] = {
            "n_labels_observed": len(obs),
            "labels": sorted({l for (l, _p, _t) in obs}),
            "min_implied_tip": min(tips).isoformat(),
            "max_implied_tip": max(tips).isoformat(),
            "spread_seconds": (max(tips) - min(tips)).total_seconds(),
        }
    return tip_by_vendor_id, spread_by_vendor_id


def book_density(rows):
    """Row counts and CHANGE counts per book. A change = a row whose
    (price, price_over, price_under) differs from the immediately preceding
    row of the same (game_id, book, market, outcome, line) series -- same
    series-key convention M07 adopted (DB-1 per-line variant), sub-1s
    echo-poll duplicate ticks excluded (M07 Section 4)."""
    rows_per_book = defaultdict(int)
    series = defaultdict(list)
    for r in rows:
        rows_per_book[r["book"]] += 1
        key = (r["game_id"], r["book"], r["market"], r["outcome"], r["line"])
        series[key].append(r)

    changes_per_book = defaultdict(int)
    for key, srows in series.items():
        srows.sort(key=lambda r: r["retrieval_ts"])
        prev = None
        for r in srows:
            if prev is not None:
                gap = (_parse_ts(r["retrieval_ts"]) - _parse_ts(prev["retrieval_ts"])).total_seconds()
                if gap < 1.0:
                    prev = r
                    continue  # echo-poll duplicate tick, zero information (M07)
                state_now = (r["price"], r["price_over"], r["price_under"])
                state_prev = (prev["price"], prev["price_over"], prev["price_under"])
                if state_now != state_prev:
                    changes_per_book[r["book"]] += 1
            prev = r

    books = sorted(set(rows_per_book) | set(changes_per_book))
    return {
        b: {"rows": rows_per_book.get(b, 0), "changes": changes_per_book.get(b, 0)}
        for b in books
    }


def change_events_with_hours_to_tip(rows, tip_by_vendor_id):
    """Every price CHANGE (same definition as book_density), each tagged
    with hours-before-tip using the change's own retrieval_ts and the
    per-game tip estimate. Games with no tip estimate (no ladder poll_log
    rows observed for them) are excluded and reported as such -- never
    imputed."""
    series = defaultdict(list)
    for r in rows:
        key = (r["game_id"], r["book"], r["market"], r["outcome"], r["line"])
        series[key].append(r)

    events = []
    n_excluded_no_tip = 0
    for key, srows in series.items():
        srows.sort(key=lambda r: r["retrieval_ts"])
        prev = None
        for r in srows:
            if prev is not None:
                gap = (_parse_ts(r["retrieval_ts"]) - _parse_ts(prev["retrieval_ts"])).total_seconds()
                if gap < 1.0:
                    prev = r
                    continue
                state_now = (r["price"], r["price_over"], r["price_under"])
                state_prev = (prev["price"], prev["price_over"], prev["price_under"])
                if state_now != state_prev:
                    tip = tip_by_vendor_id.get(r["game_id"])
                    if tip is None:
                        n_excluded_no_tip += 1
                    else:
                        hrs = (tip - _parse_ts(r["retrieval_ts"])).total_seconds() / 3600.0
                        events.append({
                            "game_id": r["game_id"], "book": r["book"],
                            "market": r["market"], "retrieval_ts": r["retrieval_ts"],
                            "hours_before_tip": round(hrs, 3),
                        })
            prev = r
    return events, n_excluded_no_tip


def bucket_hours_before_tip(events):
    """Fixed bucket edges spanning the ladder's own rungs plus a catch-all
    for anything outside [0h, 24h] (post-tip or pre-T-24h)."""
    edges = [(24.0, 999.0, ">24h"), (8.0, 24.0, "8h-24h"), (4.0, 8.0, "4h-8h"),
             (2.0, 4.0, "2h-4h"), (1.0, 2.0, "1h-2h"), (0.5, 1.0, "30m-1h"),
             (0.25, 0.5, "15m-30m"), (0.0, 0.25, "0-15m"), (-999.0, 0.0, "post-tip")]
    counts = {label: 0 for (_lo, _hi, label) in edges}
    for e in events:
        h = e["hours_before_tip"]
        for lo, hi, label in edges:
            if lo <= h < hi:
                counts[label] += 1
                break
    return counts


def main():
    snap_rows = load_snapshots()
    poll_rows = load_poll_log()
    internal_to_vendor = build_internal_to_vendor_map(poll_rows)
    tip_by_vendor_id, spread_by_vendor_id = estimate_tip_times(poll_rows, internal_to_vendor)

    density = book_density(snap_rows)
    events, n_excluded_no_tip = change_events_with_hours_to_tip(snap_rows, tip_by_vendor_id)
    buckets = bucket_hours_before_tip(events)

    out = {
        "n_snapshot_rows": len(snap_rows),
        "n_poll_log_rows": len(poll_rows),
        "internal_to_vendor_game_id_map": internal_to_vendor,
        "tip_estimates": {
            vid: {"avg_implied_tip_utc": t.isoformat(), **spread_by_vendor_id[vid]}
            for vid, t in tip_by_vendor_id.items()
        },
        "book_density": density,
        "n_price_change_events_total": len(events),
        "n_price_change_events_excluded_no_tip_estimate": n_excluded_no_tip,
        "price_change_events_by_hours_before_tip_bucket": buckets,
    }
    out_path = Path(__file__).resolve().parent / "tape_analysis.json"
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
