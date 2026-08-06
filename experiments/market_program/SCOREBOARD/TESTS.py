#!/usr/bin/env python3
"""Fixture tests for the D036 scoreboard pipeline.

1. Coverage-count math: a tiny synthetic props jsonl and featured jsonl with
   hand-countable contents must reproduce the exact seven counts.
2. Golden generator fixture: small fixed inputs -> the generator must emit
   stable output (byte-identical across two runs) containing the mandated
   semantics (NOT-YET-EVALUATED-PENDING-AUDIT chips, banned-phrase discipline,
   caveat text, provenance hashes) and the manifest must hash-verify.

Run: python TESTS.py
"""
import copy
import hashlib
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import audit_coverage
import build_scoreboard

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


# ---------------------------------------------------------------- fixtures
def make_props_fixture(path):
    """2 calendar dates, 2 events, 3 event-snapshot pairs (one empty), 3
    player-games, 6 normalized rows, 2 books, 2 market families."""
    recs = [
        {"requested_ts": "2023-05-21T20:00:00Z", "event_id": "E1", "day": "2023-05-21",
         "n_bookmakers": 1, "payload": {"bookmakers": [
             {"key": "bookA", "markets": [
                 {"key": "player_points", "outcomes": [
                     {"name": "Over", "description": "P One", "price": -110, "point": 10.5},
                     {"name": "Under", "description": "P One", "price": -110, "point": 10.5}]}]}]}},
        {"requested_ts": "2023-05-21T23:30:00Z", "event_id": "E1", "day": "2023-05-21",
         "n_bookmakers": 1, "payload": {"bookmakers": [
             {"key": "bookB", "markets": [
                 {"key": "player_rebounds", "outcomes": [
                     {"name": "Over", "description": "P Two", "price": -115, "point": 7.5},
                     {"name": "Under", "description": "P Two", "price": -105, "point": 7.5}]}]}]}},
        {"requested_ts": "2023-05-22T20:00:00Z", "event_id": "E2", "day": "2023-05-22",
         "n_bookmakers": 1, "payload": {"bookmakers": [
             {"key": "bookA", "markets": [
                 {"key": "player_points", "outcomes": [
                     {"name": "Over", "description": "P Three", "price": -120, "point": 12.5},
                     {"name": "Under", "description": "P Three", "price": 100, "point": 12.5}]}]}]}},
        {"requested_ts": "2023-05-23T20:00:00Z", "event_id": "E3", "day": "2023-05-23",
         "n_bookmakers": 0, "payload": None},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")


def make_featured_fixture(path):
    """2 snapshots, 2 dates, 2 events, 3 event-snapshot pairs, 2 books,
    2 market families, 8 outcome rows."""
    recs = [
        {"requested_ts": "2022-05-21T16:00:00Z", "n_events": 2, "payload": [
            {"id": "G1", "commence_time": "2022-05-21T19:00:00Z", "bookmakers": [
                {"key": "bookA", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "T1", "price": -200}, {"name": "T2", "price": 170}]},
                    {"key": "totals", "outcomes": [{"name": "Over", "price": -110, "point": 160.5},
                                                    {"name": "Under", "price": -110, "point": 160.5}]}]}]},
            {"id": "G2", "commence_time": "2022-05-21T21:00:00Z", "bookmakers": [
                {"key": "bookB", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "T3", "price": 120}, {"name": "T4", "price": -140}]}]}]}]},
        {"requested_ts": "2022-05-22T23:30:00Z", "n_events": 1, "payload": [
            {"id": "G1", "commence_time": "2022-05-21T19:00:00Z", "bookmakers": [
                {"key": "bookA", "markets": [
                    {"key": "h2h", "outcomes": [{"name": "T1", "price": -210}, {"name": "T2", "price": 175}]}]}]}]},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")


def run_coverage_tests(tmp):
    props = os.path.join(tmp, "props_fixture.jsonl")
    feat = os.path.join(tmp, "featured_fixture.jsonl")
    make_props_fixture(props)
    make_featured_fixture(feat)

    pa = audit_coverage.audit_props(props)
    c = pa["seven_counts"]
    check("props.unique_calendar_dates_with_prop_lines == 2", c["unique_calendar_dates_with_prop_lines"] == 2, c)
    check("props.unique_event_ids_with_prop_lines == 2", c["unique_event_ids_with_prop_lines"] == 2, c)
    check("props.unique_event_snapshot_pairs == 3", c["unique_event_snapshot_pairs_with_prop_lines"] == 3, c)
    check("props.unique_player_games == 3", c["unique_player_games"] == 3, c)
    check("props.normalized_prop_rows == 6", c["normalized_prop_rows"] == 6, c)
    check("props.unique_books == 2", c["unique_books"] == 2, c)
    check("props.unique_market_families == 2", c["unique_market_families"] == 2, c)
    check("props.context.dates_queried == 3", pa["context_counts"]["unique_calendar_dates_queried"] == 3)
    check("props: no 'game day' phrase in emitted keys",
          "game day" not in json.dumps(pa).lower().replace("game days' is banned", ""))

    fa = audit_coverage.audit_featured(feat)
    fc = fa["seven_counts"]
    check("featured.unique_calendar_dates_requested == 2", fc["unique_calendar_dates_requested"] == 2, fc)
    check("featured.unique_event_ids == 2", fc["unique_event_ids"] == 2, fc)
    check("featured.unique_event_snapshot_pairs == 3", fc["unique_event_snapshot_pairs"] == 3, fc)
    check("featured.normalized_outcome_rows == 8", fc["normalized_outcome_rows"] == 8, fc)
    check("featured.unique_books == 2", fc["unique_books"] == 2, fc)
    check("featured.unique_market_families == 2", fc["unique_market_families"] == 2, fc)
    check("featured.snapshot_lines_total == 2", fa["snapshot_lines_total"] == 2, fa)


# ------------------------------------------------------------- golden fixture
def make_generator_fixture(tmp):
    """Small but schema-complete inputs for build_scoreboard."""
    coverage = {
        "schema": "market_program/SCOREBOARD/data_coverage/1",
        "generated_utc": "2026-08-06T00:00:00+00:00",
        "props_archive": {
            "path": "fixture/props.jsonl", "sha256": "a" * 64,
            "seven_counts": {
                "unique_calendar_dates_with_prop_lines": 2,
                "unique_event_ids_with_prop_lines": 2,
                "unique_event_snapshot_pairs_with_prop_lines": 3,
                "unique_player_games": 3,
                "normalized_prop_rows": 6,
                "unique_books": 2,
                "unique_market_families": 1},
            "context_counts": {"unique_calendar_dates_queried": 3, "unique_event_ids_queried": 3},
            "market_families": ["player_points"],
            "date_range_with_lines": ["2023-05-21", "2023-05-22"],
            "tier_caveat": "vendor-asserted, unwitnessed FIXTURE caveat"},
        "featured_archive": {
            "path": "fixture/featured.jsonl", "sha256": "b" * 64,
            "snapshot_lines_total": 2,
            "seven_counts": {
                "unique_calendar_dates_requested": 2,
                "unique_calendar_dates_with_events": 2,
                "unique_event_ids": 2,
                "unique_event_snapshot_pairs": 3,
                "normalized_outcome_rows": 8,
                "unique_books": 2,
                "unique_market_families": 2},
            "market_families": ["h2h", "totals"],
            "commence_time_range_of_events": ["2022-05-21T19:00:00Z", "2022-05-22T21:00:00Z"]},
    }

    def ml(brier, n):
        return {"brier": brier, "log_loss": brier * 2.9, "n": n, "calibration_10bin": []}

    def brow(season, sc, variant, s_mae, n):
        return {"season": season, "snapshot_class": sc, "variant": variant,
                "spread": {"mae": s_mae, "bias": 0.02, "n": n},
                "total": {"mae": s_mae + 4.0, "bias": -0.9, "n": n - 5},
                "moneyline": ml(0.2, n)}

    baseline_rows = [
        brow("POOLED", "EARLY", "cross_book", 9.5, 100),
        brow("POOLED", "EARLY", "best_book", 9.52, 99),
        brow("POOLED", "LATE", "cross_book", 9.7, 90),
        brow("POOLED", "LATE", "best_book", 9.68, 88),
    ]
    prov = {
        "source_artifact": {"path": "fixture/source.json", "sha256": "c" * 64},
        "commit_lineage": {"recorded_head": "deadbeef", "note": "fixture"},
        "computation_timestamp_utc": "2026-08-06T00:00:00+00:00"}
    metrics = {
        "schema": "market_program/SCOREBOARD/metrics/1",
        "generated_utc": "2026-08-06T00:00:00+00:00",
        "rows": [
            {"row_id": "incumbent_operational_team_attributed_turnovers", "section": "predictive",
             "status": "MEASURED", "evidence_class": "MEASURED_FIXTURE",
             "model_version": "Arm D fixture", "target": "team-attributed turnovers",
             "cutoff": "pregame", "universe": "fixture universe", "date_range": "2021-2026",
             "metrics": {"mae": 2.9675, "rmse": 3.71, "bias": 0.08, "n_team_games": 2914,
                          "ci95": None, "ci95_reason": "fixture"},
             "season_splits": {}, "provenance": prov},
            {"row_id": "incumbent_intrinsic_team_attributed_turnovers", "section": "predictive",
             "status": "MEASURED", "evidence_class": "MEASURED_FIXTURE",
             "model_version": "Arm D fixture", "target": "team-attributed turnovers (intrinsic)",
             "cutoff": "intrinsic track DEFINITION fixture", "universe": "fixture", "date_range": "2021-2026",
             "metrics": {"mae": 2.896, "rmse": 3.62, "bias": 0.07, "n_team_games": 2982,
                          "ci95": None, "ci95_reason": "fixture"},
             "season_splits": {}, "provenance": prov},
            {"row_id": "bookie_baseline", "section": "predictive", "status": "MEASURED",
             "evidence_class": "MEASURED_T1_VENDOR_ASSERTED fixture",
             "model_version": "market fixture", "target": "spread/total/moneyline",
             "cutoff": "EARLY/LATE vendor-asserted only", "universe": "fixture", "date_range": "2022-2026",
             "vig_method": "multiplicative_proportional",
             "vig_preregistration_hash": "d" * 64,
             "caveat_text_verbatim": "FIXTURE CAVEAT: vendor-asserted and unwitnessed.",
             "caveat_sha256": "e" * 64,
             "metrics": {"rows": baseline_rows, "ci95": None, "ci95_reason": "fixture"},
             "provenance": prov},
            {"row_id": "naive_baseline_league_mean", "section": "predictive", "status": "DECLARED_PENDING",
             "evidence_class": "DECLARED_PENDING fixture", "model_version": "league_mean",
             "target": "all", "cutoff": "pregame", "universe": None, "date_range": None,
             "metrics": {"value": None}, "provenance": {"computation_timestamp_utc": "2026-08-06T00:00:00+00:00"}},
            {"row_id": "naive_baseline_rolling_team_average", "section": "predictive", "status": "DECLARED_PENDING",
             "evidence_class": "DECLARED_PENDING fixture", "model_version": "rolling_team_average",
             "target": "all", "cutoff": "pregame", "universe": None, "date_range": None,
             "metrics": {"value": None}, "provenance": {"computation_timestamp_utc": "2026-08-06T00:00:00+00:00"}},
            {"row_id": "naive_baseline_last_five_games", "section": "predictive", "status": "DECLARED_PENDING",
             "evidence_class": "DECLARED_PENDING fixture", "model_version": "last_five_games",
             "target": "all", "cutoff": "pregame", "universe": None, "date_range": None,
             "metrics": {"value": None}, "provenance": {"computation_timestamp_utc": "2026-08-06T00:00:00+00:00"}},
            {"row_id": "fixed_identity_book_ranking", "section": "predictive", "status": "DECLARED_PENDING",
             "evidence_class": "DECLARED_PENDING fixture", "model_version": "per-book ranking",
             "target": "per-book", "cutoff": "EARLY/LATE", "universe": ">=200 matched games threshold",
             "date_range": "2022-2026", "metrics": {"value": None},
             "declared_reason": "per-book rows do not exist in the fixture baseline", "provenance": prov},
        ]}
    lifecycle = {
        "schema": "market_program/SCOREBOARD/lifecycle/1",
        "ladder": ["BUILT", "AUDITED", "FITTING", "EVALUATED/SEALED", "ADJUDICATED"],
        "sealed_replacement_rule": "SEALED is replaced by NOT-YET-EVALUATED-PENDING-AUDIT wherever blind fits have not run; 322/322 is labeled implementation tests, never predictive evidence",
        "challenger_field": {"lifecycle_state": "BUILT",
                              "statement": "fixture: 21/22 arms built, 322/322 implementation tests",
                              "source": {"path": "fixture", "record": "fixture-record", "kind": "fixture"}},
        "model_cell_chip": "NOT-YET-EVALUATED-PENDING-AUDIT",
        "pipeline": [{"label": "Now", "text": "fixture step", "now": True}],
        "cells_dropped": [{"old_cell": "fixture old cell", "why_dropped": "fixture reason", "disposition": "fixture disposition"}],
        "operational_progress": [{"text": "fixture op item", "chip": "BUILT", "source": "fixture-source"}],
        "updated_note": "fixture note"}

    for name, doc in (("data_coverage.json", coverage), ("metrics.json", metrics), ("lifecycle.json", lifecycle)):
        with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
    return coverage, metrics, lifecycle


def make_granular_fixture(tmp):
    """Small but schema-complete D037 granular player inputs.

    Two stats get full naive_baselines[stat][variant]["pooled"] blocks
    (points, rebounds) so best-of-three selection is exercised (season-to-date
    beats trailing-5 beats league-mean by construction); the remaining six
    stats reuse the same shape via a helper so the generator's per-stat loop
    has real data for every GRANULAR_STATS entry.
    """
    gdir = os.path.join(tmp, "granular")
    os.makedirs(gdir, exist_ok=True)

    def pooled_row(target, variant, mae):
        return {
            "evidence_class": "NAIVE_BASELINE",
            "model_version": f"naive/{variant}/1",
            "target": target,
            "cutoff": "pregame-by-construction: strictly prior same-season games only (FIXTURE)",
            "universe": "fixture regular-season player-games",
            "season": "pooled",
            "n_player_games": 1000,
            "date_range": ["2022-05-08", "2026-07-31"],
            "mae": mae,
            "rmse": mae + 1.0,
            "bias": 0.01,
            "mae_ci95": {"lo": mae - 0.05, "hi": mae + 0.05, "n_boot": 1000, "n_clusters": 50,
                         "seed": 20260806, "method": "cluster_bootstrap_over_game_dates_percentile"},
            "n_cold_start_excluded": 10,
        }

    stats = ["points", "rebounds", "assists", "steals", "blocks", "threes_made", "turnovers", "minutes"]
    naive_baselines = {}
    for i, stat in enumerate(stats):
        # season_to_date_mean is always the lowest MAE (best) in this fixture,
        # by a margin large enough to be unambiguous.
        naive_baselines[stat] = {
            "trailing_5_mean": {"pooled": pooled_row(stat, "trailing_5_mean", 5.0 + i)},
            "season_to_date_mean": {"pooled": pooled_row(stat, "season_to_date_mean", 4.0 + i)},
            "league_mean": {"pooled": pooled_row(stat, "league_mean", 6.0 + i)},
        }

    granular_metrics = {
        "schema": "market_program/SCOREBOARD/granular/player_granular_metrics/1",
        "generated_utc": "2026-08-06T20:12:02+00:00",
        "contract_sha256": "f" * 64,
        "producer": "compute_player_granular.py",
        "producer_sha256": "1" * 64,
        "naive_baselines": naive_baselines,
        "market_threshold": {
            "points": {
                "pooled_books": {"pooled": {
                    "evidence_class": "MARKET_THRESHOLD",
                    "model_version": "market_lines/T1_vendor_asserted_snapshot/1",
                    "target": "points",
                    "cutoff": "vendor-asserted pre-game snapshot (FIXTURE)",
                    "universe": "fixture prop quote rows joined to player-game outcomes",
                    "date_range": ["2024-05-14", "2026-07-30"],
                    "bookmaker": "ALL_BOOKS_POOLED",
                    "n_quote_rows": 27916,
                    "n_player_games": 5900,
                    "threshold_mae": 5.0093,
                    "threshold_mae_note": "THRESHOLD MAE (line vs realized stat) per D036 point 5 -- NOT a projection MAE",
                    "devig_ou_accuracy": 0.5299,
                    "devig_brier": 0.2485,
                    "vig_method": "multiplicative_proportional",
                    "vig_preregistration_hash": "2" * 64,
                }},
                "per_book": {"betmgm": {}, "bovada": {}},
            }
        },
        "our_model": {"lifecycle_state": "NOT-YET-EVALUATED-PENDING-AUDIT",
                      "note": "D037 fixture: no legacy number appears in this file."},
    }
    granular_coverage = {
        "schema": "market_program/SCOREBOARD/granular/player_granular_coverage/1",
        "generated_utc": "2026-08-06T20:12:02+00:00",
        "seasons": [2022, 2023, 2024, 2025, 2026],
        "n_player_games_total": 22821,
        "unique_game_dates": 429,
        "unique_games": 1197,
        "market_join_audit": {
            "n_raw_rows": 36946,
            "n_quote_rows_matched": 27916,
            "n_quote_rows_unmatched": 3427,
            "n_matched_player_games": 5900,
            "n_unmatched_player_games": 645,
            "market_families_present": ["player_points"],
            "market_families_supported": ["player_points"],
        },
    }
    for name, doc in (("player_granular_metrics.json", granular_metrics),
                       ("player_granular_coverage.json", granular_coverage)):
        with open(os.path.join(gdir, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
    return granular_metrics, granular_coverage


def run_generator_tests(tmp):
    make_generator_fixture(tmp)
    make_granular_fixture(tmp)
    out1 = os.path.join(tmp, "run1")
    out2 = os.path.join(tmp, "run2")
    os.makedirs(out1); os.makedirs(out2)
    build_scoreboard.main(tmp, out1)
    build_scoreboard.main(tmp, out2)
    h1 = open(os.path.join(out1, "scoreboard.html"), encoding="utf-8").read()
    h2 = open(os.path.join(out2, "scoreboard.html"), encoding="utf-8").read()

    check("golden: output byte-stable across runs", h1 == h2)
    check("golden: pending-audit chip present", "NOT-YET-EVALUATED-PENDING-AUDIT" in h1)
    check("golden: no SEALED chip on model cells", "c-sealed\">SEALED" not in h1 and ">SEALED<" not in h1)
    check("golden: 322/322 framed as implementation tests", "implementation tests" in h1)
    check("golden: banned phrase absent (except explicit ban notices)",
          not re.search(r"game days(?!.{0,80}(banned|withdrawn))", h1, re.IGNORECASE))
    check("golden: caveat text verbatim", "FIXTURE CAVEAT: vendor-asserted and unwitnessed." in h1)
    # D036 point 3: the cutoffs may never be PRESENTED as opening/closing lines.
    # Negated mentions ("never opening or closing lines") are mandatory caveats
    # and allowed; any non-negated use fails.
    unnegated = [m.start() for m in re.finditer(r"(opening|closing) line", h1, re.IGNORECASE)
                 if not re.search(r"(never|not|no|neither)\b[^.<]{0,60}$", h1[max(0, m.start() - 70):m.start()], re.IGNORECASE)]
    check("golden: opening/closing only ever appears negated", not unnegated, unnegated)
    check("golden: incumbent MAE shown 4dp", "2.9675 MAE" in h1)
    check("golden: intrinsic shown with n", "2.8960" in h1 and "2,982" in h1)
    check("golden: LATE pooled market spread", "9.7000" in h1)
    check("golden: fixed-identity fanduel framing (best book not per-game)", "per-book rows" in h1.lower() or "fixed" in h1.lower())
    check("golden: operational section marker present", "Operational progress — NOT predictive evidence" in h1)
    check("golden: dropped-cells honesty log present", "fixture old cell" in h1 and "fixture reason" in h1)
    check("golden: provenance popover title attrs present", 'title="' in h1 and "sha256" in h1)
    check("golden: provenance sha256 of fixture source", "c" * 64 in h1)
    check("golden: declared-pending naive baselines", "DECLARED-PENDING" in h1)

    # ---------------------------------------------------------- D037 checks
    check("golden: granular section heading present", "Granular player outcomes (D037)" in h1)
    for label in ("Points", "Rebounds", "Assists", "Steals", "Blocks", "Threes made", "Turnovers", "Minutes"):
        check(f"golden: granular row present for {label}", f'<td class="metric">{label}</td>' in h1)
    check("golden: granular our-model cells pending", h1.count("NOT-YET-EVALUATED-PENDING-AUDIT") >= 8)
    check("golden: legacy badge appears exactly on points and minutes (2x)",
          h1.count("LEGACY RECEIPTABLE - VERIFICATION QUEUED") == 2)
    check("golden: no legacy number rendered (no MEASURED chip beside the legacy badge)",
          "LEGACY RECEIPTABLE" in h1 and "PROBE_LEGACY.md verdict: RECEIPTABLE" in h1)
    check("golden: naive baseline picks season-to-date (lowest fixture MAE) for every stat",
          h1.count("NAIVE_BASELINE") >= 8 and h1.count("season-to-date mean ·") >= 8)
    check("golden: naive footnote names all three baselines",
          "trailing-5 mean, season-to-date mean, league mean" in h1)
    check("golden: market OU accuracy / Brier / threshold MAE shown for points",
          "0.5299 OU acc." in h1 and "Brier 0.2485" in h1 and "threshold MAE 5.0093" in h1)
    check("golden: threshold MAE explicitly not a projection MAE",
          "NOT a projection MAE" in h1 and "line-vs-outcome distance" in h1)
    check("golden: D036 point 5 threshold-vs-projection sentence present",
          "A market line is a threshold, not a projection" in h1)
    check("golden: rebounds/assists/threes market cells NOT CAPTURED (single-family archive)",
          h1.count("NOT CAPTURED (single-family archive)") >= 7)
    check("golden: coverage strip shows granular player archive tile",
          "Granular player archive" in h1)
    check("golden: coverage strip shows the 22,821 player-game universe",
          "22,821" in h1 and "player-game universe" in h1)

    man = json.load(open(os.path.join(out1, "scoreboard_manifest.json"), encoding="utf-8"))
    ok = True
    for name, rec in man["inputs"].items():
        b = open(os.path.join(tmp, name), "rb").read()
        ok = ok and hashlib.sha256(b).hexdigest() == rec["sha256"]
    out_b = open(os.path.join(out1, "scoreboard.html"), "rb").read()
    ok = ok and hashlib.sha256(out_b).hexdigest() == man["output"]["sha256"]
    gen_b = open(build_scoreboard.__file__, "rb").read()
    ok = ok and hashlib.sha256(gen_b).hexdigest() == man["generator"]["sha256"]
    check("manifest: all sha256 verify (5 inputs + generator + output)", ok)
    check("manifest: carries generation timestamp", bool(man.get("generated_utc")))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        run_coverage_tests(tmp)
        run_generator_tests(tmp)
    print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} tests passed")
    if FAIL:
        print("FAILED:", FAIL)
        sys.exit(1)


if __name__ == "__main__":
    main()
