#!/usr/bin/env python3
"""Fixture tests for the D036/D037/D038 scoreboard + leaderboard pipeline.

1. Coverage-count math: a tiny synthetic props jsonl and featured jsonl with
   hand-countable contents must reproduce the exact seven counts.
2. Golden generator fixture: small fixed inputs -> the generator must emit
   stable output (byte-identical across two runs) containing the mandated
   semantics (NOT-YET-EVALUATED-PENDING-AUDIT chips, banned-phrase discipline,
   caveat text, provenance hashes) and the manifest must hash-verify.
3. D038 acceptance checks (LEADERBOARD_SPEC.md, deterministic):
   AC1  every visible score generated from structured inputs
   AC2  higher score always = better skill
   AC3  no score for unevaluated targets
   AC4  Market Advantage uses matched universes + cutoffs only
   AC5  best/worst book never re-selected after outcomes
   AC6  tolerance bands fixed in config
   AC7  default sorting = strongest verified first
   AC8  all columns sort both ways
   AC9  filters never alter metric values
   AC10 hover values match source JSON
   AC11 byte-identical regeneration from unchanged inputs
   AC12 dropped-cells honesty log visible in methodology layer

Run: python TESTS.py
"""
import copy
import hashlib
import io
import json
import os
import re
import shutil
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

    # NOTE (AC5): the fixed pre-declared book (FanDuel, variant=best_book) is
    # deliberately WORSE (9.9) than the cross-book consensus (9.7) in this
    # fixture -- the generator must still display 9.9 for the fixed identity
    # and never re-select a better book after outcomes are known.
    baseline_rows = [
        brow("POOLED", "EARLY", "cross_book", 9.5, 100),
        brow("POOLED", "EARLY", "best_book", 9.52, 99),
        brow("POOLED", "LATE", "cross_book", 9.7, 90),
        brow("POOLED", "LATE", "best_book", 9.9, 88),
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
            {"row_id": "team_possessions_champion", "section": "predictive", "status": "MEASURED",
             "evidence_class": "MEASURED_BLIND_WALK_FORWARD_AUDITED fixture -- VERIFIED",
             "model_version": "Arm D fixture, K0_MATCHED null", "target": "possessions fixture",
             "cutoff": "pregame fixture", "universe": "fixture possessions universe", "date_range": "2021-2026",
             "metrics": {"mae": 2.86649, "rmse": None, "bias": None, "n_team_games": 2572, "n_clusters": 1286,
                          "ci95": None, "ci95_reason": "fixture"},
             "champion_note": "fixture champion note",
             "adjudication_summary": {"fitted_elements": 29, "n_pass_primary": 0, "n_fail_primary": 29,
                                       "champion_challenged": False},
             "provenance": prov},
            {"row_id": "challenger_program_summary", "section": "context", "status": "MEASURED",
             "evidence_class": "MEASURED_BLIND_WALK_FORWARD_AUDITED fixture -- VERIFIED",
             "model_version": "22 arms / 29 elements fixture", "target": "context fixture",
             "cutoff": "n/a", "universe": "fixture", "date_range": "2021-2026",
             "metrics": {"n_configurations_tested": 29, "n_passed_preregistered_bar": 0,
                          "strongest_lead": {"arm_id": "A07_fixture", "delta_mae_pooled": 0.054,
                                              "p_two_sided_uncorrected": 0.028, "verdict": "FAIL",
                                              "why_it_failed": "fixture reason"}},
             "plain_english": "Twenty-nine context-adjusted ideas were tested blind; none beat the champion "
                               "after correction for multiple testing.",
             "provenance": prov},
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


def copy_score_config(tmp):
    """The FROZEN real score_config.json is used verbatim in every fixture
    build, so fixture tests also pin the frozen formula, bands and tolerance
    bands."""
    shutil.copy(os.path.join(HERE, "score_config.json"), os.path.join(tmp, "score_config.json"))


def run_generator_tests(tmp):
    make_generator_fixture(tmp)
    make_granular_fixture(tmp)
    copy_score_config(tmp)
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
    check("golden: fixed identity displayed even though worse than consensus (AC5)",
          '9.9000</span><span class="sub">FanDuel fixed identity' in h1)
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
    check("manifest: all sha256 verify (6 inputs + generator + output)", ok)
    check("manifest: score_config.json is a manifested input", "score_config.json" in man["inputs"])
    check("manifest: carries the frozen score formula version", man.get("score_formula_version") == "prediction_score/1.0.0")
    check("manifest: carries generation timestamp", bool(man.get("generated_utc")))


# ==================================================================== D038
# acceptance checks (deterministic; LEADERBOARD_SPEC.md points 1-12)
LB_ROW_RE = re.compile(r'<tr class="lb-row" id="lb-([a-zA-Z_]+)" data-target="[^"]*" data-score="([^"]*)"')


def lb_scores(h):
    """[(target_id, data-score str), ...] in DOM order."""
    return LB_ROW_RE.findall(h)


def make_lb_fixture(tmp, our_model=None):
    """Full fixture input dir; optionally injects evaluated our_model rows
    into the granular metrics file (the ONLY structured path through which a
    model number may reach the leaderboard for player targets)."""
    os.makedirs(tmp, exist_ok=True)
    make_generator_fixture(tmp)
    make_granular_fixture(tmp)
    copy_score_config(tmp)
    if our_model is not None:
        p = os.path.join(tmp, "granular", "player_granular_metrics.json")
        gm = json.load(open(p, encoding="utf-8"))
        gm["our_model"] = our_model
        with open(p, "w", encoding="utf-8") as f:
            json.dump(gm, f, indent=2)
    out = os.path.join(tmp, "out")
    os.makedirs(out, exist_ok=True)
    build_scoreboard.main(tmp, out)
    return open(os.path.join(out, "scoreboard.html"), encoding="utf-8").read()


def model_row(mae, n, universe, cutoff, evidence_class, extra=None):
    r = {"mae": mae, "rmse": mae + 1.0, "bias": 0.0, "n_player_games": n,
         "universe": universe, "cutoff": cutoff, "evidence_class": evidence_class,
         "model_version": "our/fixture/1", "date_range": ["2022-05-08", "2026-07-31"]}
    if extra:
        r.update(extra)
    return r


BASE_UNI = "fixture regular-season player-games"
MKT_UNI = "fixture prop quote rows joined to player-game outcomes"
MKT_CUT = "vendor-asserted pre-game snapshot (FIXTURE)"


def run_acceptance_tests(tmp):
    cfg = json.load(open(os.path.join(HERE, "score_config.json"), encoding="utf-8"))

    # ---- variant A: two evaluated model rows matched to their BASELINE
    # universes (points VERIFIED score 75; rebounds PROMISING score 100);
    # market universe deliberately NOT matched.
    variant_a = {"lifecycle_state": "EVALUATED", "note": "fixture evaluated rows", "rows": {
        "points": {"pooled": model_row(3.0, 1000, BASE_UNI, "pregame fixture cutoff",
                                       "MEASURED_BLIND_WALK_FORWARD_AUDITED fixture")},
        "rebounds": {"pooled": model_row(2.5, 1000, BASE_UNI, "pregame fixture cutoff",
                                         "MEASURED_RETROSPECTIVE_POSITIVE fixture")},
    }}
    ha = make_lb_fixture(os.path.join(tmp, "va"), variant_a)

    # ---- variant B: model points row matched to the MARKET universe/cutoff/N
    # and carrying the market's own metric (devig_brier) -> market advantage
    # computable; baseline universe unmatched -> score stays TBD.
    variant_b = {"lifecycle_state": "EVALUATED", "note": "fixture evaluated rows", "rows": {
        "points": {"pooled": model_row(3.0, 5900, MKT_UNI, MKT_CUT,
                                       "MEASURED_BLIND_WALK_FORWARD_AUDITED fixture",
                                       extra={"devig_brier": 0.2})},
    }}
    hb = make_lb_fixture(os.path.join(tmp, "vb"), variant_b)

    # AC1 -- every visible score generated from structured inputs -----------
    gm_a = json.load(open(os.path.join(tmp, "va", "granular", "player_granular_metrics.json"), encoding="utf-8"))
    exp_points = build_scoreboard.compute_prediction_score(
        gm_a["our_model"]["rows"]["points"]["pooled"]["mae"],
        gm_a["naive_baselines"]["points"]["season_to_date_mean"]["pooled"]["mae"])[0]
    exp_rebounds = build_scoreboard.compute_prediction_score(
        gm_a["our_model"]["rows"]["rebounds"]["pooled"]["mae"],
        gm_a["naive_baselines"]["rebounds"]["season_to_date_mean"]["pooled"]["mae"])[0]
    got = dict(lb_scores(ha))
    check("AC1: points score in HTML == frozen formula on structured inputs",
          got.get("player_points") == str(exp_points) == "75", got.get("player_points"))
    check("AC1: rebounds score in HTML == frozen formula on structured inputs",
          got.get("player_rebounds") == str(exp_rebounds) == "100", got.get("player_rebounds"))
    check("AC1: the only numeric scores on the page are the two derivable ones",
          sorted(v for _, v in lb_scores(ha) if v != "") == ["100", "75"])

    # AC2 -- higher score always = better skill ------------------------------
    s = lambda m, b: build_scoreboard.compute_prediction_score(m, b)[0]
    seq = [s(m, 4.0) for m in (2.0, 3.0, 3.5, 4.0, 4.5, 5.0, 8.0)]
    check("AC2: score strictly non-increasing as model error grows on a fixed baseline",
          seq == sorted(seq, reverse=True) and seq[0] == 100 and seq[3] == 50 and seq[-1] == 0, seq)
    check("AC2: equal-to-baseline lands exactly on 50", s(4.0, 4.0) == 50)
    check("AC2: clamped to [0,100]", s(0.001, 4.0) == 100 and s(400.0, 4.0) == 0)

    # AC3 -- no score for unevaluated targets --------------------------------
    check("AC3: fixture unevaluated targets carry empty data-score",
          all(v == "" for k, v in lb_scores(ha) if k not in ("player_points", "player_rebounds")))
    check("AC3: variant B baseline-unmatched model row shows NO score (never normalized across universes)",
          all(v == "" for _, v in lb_scores(hb)))
    check("AC3: TBD chips, never placeholder numbers, on unevaluated rows",
          "no attractive placeholders" in ha)

    # AC4 -- market advantage only on matched universes + cutoffs ------------
    check("AC4: variant A (market universe unmatched) -> Not comparable, no number",
          "universes not matched — never compared" in ha and 'data-market=""' in ha.split('id="lb-player_points"')[1][:600])
    adv = build_scoreboard.compute_market_advantage(0.2, 0.2485, True)
    check("AC4: variant B advantage == frozen formula on structured inputs",
          f'data-market="{round(adv * 100, 1)}"' in hb, round(adv * 100, 1))
    check("AC4: variant B labeled Strong advantage with signed percent",
          "Strong advantage" in hb and "+19.5% lower de-vigged O/U Brier" in hb)
    check("AC4: unmatched flag hard-disables the computation",
          build_scoreboard.compute_market_advantage(0.2, 0.2485, False) is None)
    check("AC4: metric never mixed — a model without the market's metric is not compared",
          build_scoreboard.compute_market_advantage(None, 0.2485, True) is None)

    # AC5 -- best/worst book never re-selected after outcomes ----------------
    check("AC5: fixed-identity FanDuel value (9.9) displayed although consensus (9.7) is better",
          '9.9000</span><span class="sub">FanDuel fixed identity' in ha and "9.7000" in ha)
    check("AC5: fixed-identity framing text present",
          "FIXED pre-declared identity" in ha and "Per-game closest-book selection is prohibited" in ha)

    # AC6 -- tolerance bands fixed in config ---------------------------------
    tb = cfg["tolerance_bands"]
    expected_bands = {"player_points": (5, "points"), "player_rebounds": (2, "rebounds"),
                      "player_assists": (2, "assists"), "player_minutes": (5, "minutes"),
                      "game_total": (10, "points"), "margin": (8, "points")}
    check("AC6: config frozen flags set", cfg["frozen"] is True and tb["frozen"] is True
          and cfg["prediction_score"]["frozen"] is True)
    check("AC6: frozen tolerance values match the spec exactly",
          {k: (v["tolerance"], v["unit"]) for k, v in tb["bands"].items()} == expected_bands)
    check("AC6: every band rendered in the methodology layer verbatim from config",
          all(f'±{v["tolerance"]} {v["unit"]}' in ha for v in tb["bands"].values()))
    check("AC6: undeclared targets say so instead of inheriting a band",
          "no target range declared" in ha)

    # AC7 -- default sorting = strongest verified first ----------------------
    order_a = [k for k, _ in lb_scores(ha)]
    check("AC7: VERIFIED-scored row first, PROMISING-scored second (evidence before raw score)",
          order_a[:2] == ["player_points", "player_rebounds"], order_a[:4])
    check("AC7: evaluated-without-score VERIFIED row (team_possessions) outranks PRELIMINARY evaluated-without-score rows",
          order_a[2] == "team_possessions", order_a[2])
    check("AC7: evaluated-without-score row precedes unevaluated targets",
          order_a[3] == "team_attributed_turnovers", order_a[3])
    check("AC7: unevaluated targets last, in registry order",
          order_a[-4:] == ["team_total", "game_total", "margin", "win_probability"], order_a[-4:])

    # AC8 -- all columns sort both ways ---------------------------------------
    for key in ("target", "score", "miss", "range", "improve", "market", "n", "evidence", "updated"):
        check(f"AC8: column '{key}' is sortable", f'data-key="{key}"' in ha)
    check("AC8: sort direction toggles (both ways)", "state.dir = -state.dir" in ha)
    check("AC8: blank cells always last in both directions", "blanks last in BOTH directions" in ha)
    check("AC8: rows carry the sort datasets", 'data-evidence="' in ha and 'data-updated="' in ha)

    # AC9 -- filters never alter metric values --------------------------------
    check("AC9: no innerHTML anywhere in the page script", "innerHTML" not in ha and "insertAdjacentHTML" not in ha)
    check("AC9: filters only toggle row.hidden", "r.hidden = hide" in ha and
          "Filters only hide rows; they never alter a metric value" in ha)
    check("AC9: the only textContent write is the expander button label",
          ha.count("textContent") == ha.count("btn.textContent"))

    # AC10 -- hover values match source JSON -----------------------------------
    check("AC10: score hover carries model and baseline errors from the inputs",
          "model error: 3.0" in ha and "baseline error: 4.0" in ha and "prediction_score/1.0.0" in ha)
    check("AC10: baseline hover carries the source mae verbatim", "mae: 4.0" in ha)
    check("AC10: market hover carries the source devig_brier verbatim", "devig_brier: 0.2485" in ha)
    check("AC10: provenance hashes surface in hovers", ("f" * 64) in ha)

    # AC11 -- byte-identical regeneration (fixture) ----------------------------
    out2 = os.path.join(tmp, "va", "out2")
    os.makedirs(out2, exist_ok=True)
    build_scoreboard.main(os.path.join(tmp, "va"), out2)
    ha2 = open(os.path.join(out2, "scoreboard.html"), encoding="utf-8").read()
    check("AC11: byte-identical regeneration from unchanged fixture inputs", ha == ha2)

    # AC12 -- dropped-cells honesty log in the methodology layer ----------------
    m_pos = ha.find('id="methodology"')
    d_pos = ha.find("honesty log")
    check("AC12: dropped-cells honesty log lives inside the methodology layer",
          0 <= m_pos < d_pos and "fixture old cell" in ha and "fixture reason" in ha)


def run_real_input_tests(tmp):
    """The same acceptance guarantees against the REAL committed inputs."""
    o1 = os.path.join(tmp, "r1"); o2 = os.path.join(tmp, "r2")
    os.makedirs(o1); os.makedirs(o2)
    build_scoreboard.main(HERE, o1)
    build_scoreboard.main(HERE, o2)
    h1 = open(os.path.join(o1, "scoreboard.html"), encoding="utf-8").read()
    h2 = open(os.path.join(o2, "scoreboard.html"), encoding="utf-8").read()
    check("real/AC11: byte-identical regeneration from the real inputs", h1 == h2)
    scores = lb_scores(h1)
    check("real: leaderboard has 14 target rows", len(scores) == 14, len(scores))
    check("real/AC3: NO numeric Prediction Score exists yet (our model unevaluated everywhere)",
          all(v == "" for _, v in scores))
    # D038/D042 leaderboard integration: legacy_player_points and
    # team_possessions_champion (metrics.json, via build_metrics.py) give
    # player_points and team_possessions MEASURED, evaluated-without-score
    # rows. team_possessions carries a VERIFIED badge (rank 0), so it leads
    # the "evaluated, no score yet" group ahead of the two PRELIMINARY-badge
    # rows (player_points id 0, team_attributed_turnovers id 8, registry order).
    check("real/AC7: VERIFIED evaluated-without-score row (team_possessions) leads, then the PRELIMINARY group "
          "(player_points, then team_attributed_turnovers, registry order); unevaluated targets afterward",
          scores[0][0] == "team_possessions" and scores[1][0] == "player_points"
          and scores[2][0] == "team_attributed_turnovers", scores[:3])
    check("real: Betting Edge card = Not yet demonstrated (never accuracy-as-profitability)",
          "Betting Edge" in h1 and h1.count("Not yet demonstrated") >= 2)
    check("real: player leaderboard locked state",
          "Player-level leaderboards are collecting sufficient verified samples." in h1)
    check("real: no naive baseline is ever presented as our model",
          "our model has not been evaluated on this target yet" in h1.lower()
          or "no evaluated model run exists" in h1)

    # ---------------------------------------------- legacy_player_points row
    pp_start = h1.index('id="lb-player_points"')
    pp_next = h1.find('<tr class="lb-row"', pp_start + 1)
    pp_block = h1[pp_start:pp_next if pp_next != -1 else pp_start + 12000]

    check("real/legacy row: player_points carries NO Prediction Score yet",
          dict(scores)["player_points"] == "")
    check("real/legacy row: PRELIMINARY evidence badge on player_points",
          'data-evidence="2"' in pp_block and ">PRELIMINARY<" in pp_block)
    # The pin moved from 4.3 to 4.1 when the cold-start repair was bound as arm revision 9
    # (D167/D168): pooled_2022_2026 A_primary points MAE went 4.2671 -> 4.1308. It is still
    # pinned, because this check exists to assert what the PAGE renders -- but the pin is now
    # cross-checked against the source metric, so a future drift fails saying which of the two
    # moved instead of just that they disagree.
    _lvm = json.loads(io.open(os.path.join(HERE, "granular", "legacy_verified_metrics.json"),
                              encoding="utf-8").read())
    _src_mae = _lvm["our_model"]["points"]["tiers"]["A_primary"]["pooled_2022_2026"]["mae"]
    _pin = "4.1 points"
    check("real/legacy row: the pinned Typical Miss is 1dp of the source metric",
          _pin == f"{round(_src_mae, 1)} points",
          f"pin {_pin!r} vs source {_src_mae:.4f}")
    check("real/legacy row: Typical Miss shown as 1dp MAE from legacy_verified_metrics (pooled_2022_2026, A_primary)",
          _pin in pp_block)
    check("real/legacy row: Improvement vs Basic Model is pending-matched-universe, never faked from unmatched numbers",
          "Pending — matched universe" in pp_block and "paired legacy-vs-baseline run" in pp_block)
    check("real/legacy row: Market Advantage = Market currently better, -3.3 O/U accuracy points",
          "Market currently better" in pp_block and "-3.3 O/U accuracy points" in pp_block)
    # Derived from the source rather than hard-pinned. It was [-4.95, -1.76] under arm
    # revision 8 and is [-4.92, -1.72] under revision 9 (D169): repointing the node at
    # attempt_002 moved the paired difference from -0.03294 to -0.03277. A hard pin here would
    # have gone stale silently the moment the arm was rebound, which is what it just did.
    _mvm = json.loads(io.open(os.path.join(HERE, "..", "MODEL_VS_MARKET", "model_vs_market.json"),
                              encoding="utf-8").read())
    _lo, _hi = _mvm["headline"]["paired_diff_ci95"]
    _ci_txt = f"[{_lo * 100:.2f}, {_hi * 100:.2f}] pts"
    check("real/legacy row: Market Advantage CI matches model_vs_market.json headline verbatim",
          _ci_txt in pp_block, f"expected {_ci_txt!r}")
    check("real/legacy row: Market Advantage N=5,737 shown",
          "n=5,737" in pp_block)
    check("real/legacy row: hover carries the raw model-vs-market comparison and its provenance",
          (f"raw comparison: model {_mvm['headline']['model_ou_accuracy']:.4f}" in pp_block
           and f"market {_mvm['headline']['market_ou_accuracy']:.4f}" in pp_block)
          and "model_vs_market.json" in pp_block and "sha256=" in pp_block)
    check("real/legacy row: Betting Edge is never substituted for this predictive-accuracy row",
          "Betting Edge" in h1)

    # -------------------------------------------- D042 team_possessions row
    tp_start = h1.index('id="lb-team_possessions"')
    tp_next = h1.find('<tr class="lb-row"', tp_start + 1)
    tp_block = h1[tp_start:tp_next if tp_next != -1 else tp_start + 8000]

    check("real/D042: team_possessions carries NO Prediction Score yet (baseline still declared-pending)",
          dict(scores)["team_possessions"] == "")
    check("real/D042: VERIFIED evidence badge on team_possessions",
          'data-evidence="0"' in tp_block and ">VERIFIED<" in tp_block)
    check("real/D042: Typical Miss shows the VERIFIED pooled OOF possessions MAE (2.9 dp1, from 2.86649)",
          "2.9 possessions" in tp_block)
    check("real/D042: team_possessions sample N=2,572 team-games shown",
          "2,572" in tp_block)
    check("real/D042: headline tile shows the VERIFIED possessions MAE to 4dp",
          "2.8665" in h1 and ">VERIFIED<" in h1)
    check("real/D042: both possession and turnover MAEs correctly and separately labeled on the page",
          "2.9675" in h1 and "2.8665" in h1
          and "supersedes the 2.9675 turnover-lane figure" in h1.lower())
    check("real/D042: challenger program summary present in outsider-legible language",
          "Twenty-nine context-adjusted ideas were tested blind" in h1
          and "none beat the champion after correction for multiple testing" in h1
          and "early-season" in h1.lower())
    check("real/D042: 0 of 29 challenger elements promoted, stated plainly",
          "0/29 elements promoted" in h1 or "0 of 29" in h1 or "n_pass_primary=0" in h1)
    check("real/D042: challenger field lifecycle state is ADJUDICATED, not stuck at BUILT",
          ">ADJUDICATED<" in h1)

    # ---------------------------------------------------------- D045 checks
    # D043 score-family baselines wired to the board: composite rows are the
    # current-best-estimate rows, market comparison is paired matched-universe
    # only, and no Prediction Score is shown while universes are unmatched.
    check("real/D045: game_total typical miss shows the composite baseline (13.8 points)",
          "13.8 points" in h1 and "composite_pace_x_eff_v1" in h1)
    check("real/D045: NO Prediction Score for any score-family target (matched universe pending)",
          dict(scores)["game_total"] == "" and dict(scores)["margin"] == ""
          and dict(scores)["win_probability"] == "")
    check("real/D045: matched-universe pending state stated, never faked from unmatched numbers",
          "Pending — matched universe" in h1)
    check("real/D045: market advantage from the PAIRED comparison, market currently ahead on totals (-2.8)",
          "Market currently better" in h1 and "-2.8" in h1)
    check("real/D045: margin market advantage rendered (-8.2)",
          "-8.2" in h1)
    check("real/D045: win-probability Brier shown raw (0.2181)",
          "0.2181" in h1)
    check("real/D045: declared naive baseline is the season-to-date team scoring average (best of two)",
          "season-to-date team scoring average baseline" in h1)
    check("real/D045: the market bar framed as the bar to beat, not a defeat",
          "honest bar" in h1)
    gt_start = h1.find('data-for="lb-game_total"')
    gt_next = h1.find('data-for="lb-margin"')
    gt_block = h1[gt_start:gt_next if gt_next != -1 else gt_start + 8000]
    check("real/D045: game_total composite row carries PRELIMINARY badge, never VERIFIED",
          gt_start != -1 and ">PRELIMINARY<" in gt_block and ">VERIFIED<" not in gt_block)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        run_coverage_tests(tmp)
        run_generator_tests(tmp)
        run_acceptance_tests(os.path.join(tmp, "ac"))
        run_real_input_tests(os.path.join(tmp, "real"))
    print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} tests passed")
    if FAIL:
        print("FAILED:", FAIL)
        sys.exit(1)


if __name__ == "__main__":
    main()
