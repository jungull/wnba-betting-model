"""Runs the MARKET_IMPLIED_PROJECTIONS engine over:
  (a) the full discovered props-historical archive (READ ONLY, live worktree)
  (b) a sample of the live master_props.csv (READ ONLY, live worktree)

Writes JSONL output rows + a coverage report into ./OUTPUT/, inside this
track's own write scope. Never writes to the live worktree.

Also computes the mandate's specific coverage question: how many distinct
player-games in the 2024-2026 window get at least one implied-mean row.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import engine as eng  # noqa: E402

LIVE_WORKTREE_ROOT = r"C:\Users\jgallagher\wnba-betting-model"
HISTORICAL_PATH = os.path.join(
    LIVE_WORKTREE_ROOT, "data", "props_capture", "historical",
    "master_props_historical.csv")
LIVE_SAMPLE_PATH = os.path.join(
    LIVE_WORKTREE_ROOT, "data", "props_capture", "master_props.csv")

OUTPUT_DIR = os.path.join(_HERE, "OUTPUT")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def year_of_commence(ts):
    if not ts:
        return None
    try:
        return int(str(ts)[:4])
    except Exception:
        return None


def main():
    report = {}

    # ---- (a) historical archive, full run, T1_VENDOR_ASSERTED per D027 ----
    print(f"Reading historical archive (read-only): {HISTORICAL_PATH}")
    hist_rows, hist_cov = eng.run_engine(
        HISTORICAL_PATH, source_label="master_props_historical.csv (T1, D027)")
    hist_out = os.path.join(OUTPUT_DIR, "market_implied_historical.jsonl")
    eng.write_rows_jsonl(hist_rows, hist_out)
    print(f"  -> {len(hist_rows)} rows written to {hist_out}")

    # 2024-2026 window breakdown by scheduled_tipoff_ts year
    by_year_seen = Counter()
    by_year_covered = Counter()
    raw = list(eng.load_props_rows(HISTORICAL_PATH))
    groups = eng.group_rows(raw)
    pg_year = {}
    for (game_key, player_name, market_key), rows in groups.items():
        yr = year_of_commence(rows[0].get("commence_time"))
        pg_year[(game_key, player_name)] = yr
    pg_seen = {(r["game_id"] or r["api_event_id"], r["player_name"]) for r in raw}
    for pg in pg_seen:
        yr = pg_year.get(pg)
        by_year_seen[yr] += 1
    covered_pg = {(r["game_id"], r["player_key_raw"]) for r in hist_rows}
    for pg in covered_pg:
        yr = pg_year.get(pg)
        by_year_covered[yr] += 1

    report["historical_archive"] = {
        **hist_cov,
        "coverage_by_year_seen": dict(sorted(by_year_seen.items(), key=lambda x: (x[0] is None, x[0]))),
        "coverage_by_year_with_implied_mean_row": dict(sorted(by_year_covered.items(), key=lambda x: (x[0] is None, x[0]))),
        "note_market_coverage": "master_props_historical.csv carries player_points ONLY (verified: single distinct market_key across all 36,946 rows); rebounds/assists/threes are 0-coverage by construction of the source file, not this engine.",
    }

    # ---- (b) live master_props.csv, sample run ----
    print(f"Reading live sample (read-only): {LIVE_SAMPLE_PATH}")
    live_rows, live_cov = eng.run_engine(
        LIVE_SAMPLE_PATH, max_rows=None, source_label="master_props.csv (T1, live sample)")
    live_out = os.path.join(OUTPUT_DIR, "market_implied_live_sample.jsonl")
    eng.write_rows_jsonl(live_rows, live_out)
    print(f"  -> {len(live_rows)} rows written to {live_out}")
    report["live_sample"] = live_cov

    report_path = os.path.join(OUTPUT_DIR, "coverage_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"Coverage report -> {report_path}")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
