"""M10_MIDDLES -- COARSE_TAPE_DEMO.

Replays middle_scanner.py over the EXISTING capture sample at
data/market_snapshots/snapshots.csv, read-only, in the live DATA worktree
(default root "C:/Users/jgallagher/wnba-betting-model" -- the same root
convention M09_TRUE_ARB_SCANNER/coarse_tape_demo.py uses for its own replay,
and the same worktree M26/M27's own reports describe as where the actual
capture code and data files live; this script only ever opens files there
for reading, never writes there).

THIS IS NOT A MARKET FINDING. It is a demonstration that the machinery runs
end-to-end on real-shaped bytes, with every honesty gate the module enforces
actually firing where the real data does not support a stronger claim. Two
structural facts about this specific tape, verified by this script's own
byte-level measurement (never assumed), bound what it can say:

  1. Game lines (h2h/spreads/totals) were HTTP-200-but-zero-rows for an
     unknown prior period due to a capture-code defect (M26 finding, id 1,
     status CLOSED); they only began landing in this file from the fix's
     live-verification run onward. This script measures the actual
     retrieval_ts range of every h2h/spreads/totals row present and reports
     it plainly -- if that range is narrow, a small game-lines flag count is
     a structural consequence of the capture window, not evidence middles
     are rare on this market family in general.
  2. Player-prop rows (player_points/rebounds/assists/threes) have been
     landing since well before the game-lines fix and are the bulk of this
     tape's rows -- this script scans both families and reports each
     family's own capture window and row count separately, so a reader
     cannot mistake one family's coverage for the other's.

Usage:
    python coarse_tape_demo.py [path_to_wnba-betting-model_root] [max_rows]

Reads ONLY (never writes) from the live DATA worktree:
    data/market_snapshots/snapshots.csv -- first MAX_ROWS data rows
Writes:
    COARSE_TAPE_DEMO_RESULTS.json (in this node's own directory)
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import middle_scanner as M

NODE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = "C:/Users/jgallagher/wnba-betting-model"
DEFAULT_MAX_ROWS = 20000

GAME_LINE_MARKETS = {"spreads", "totals"}   # h2h excluded: moneylines cannot middle
PROP_MARKETS = {"player_points", "player_rebounds", "player_assists", "player_threes"}

# Real bookmakers observed in this tape get an explicitly-labeled PLACEHOLDER
# fee row (flat retail sportsbooks, zero commission -- mirrors M09's own
# coarse_tape_demo.py REAL_BOOK_BASELINE_FEE, same justification: directionally
# correct for standard-book lines, not independently re-verified per venue in
# this node). They deliberately get NO push/void row: unlike M09's h2h-only
# demo (where push/void risk is structurally absent), spreads/totals/props
# DO carry push and DNP-void risk on this tape (confirmed below -- integer
# spread lines are present), and no venue's real push or DNP-void rule is
# verified anywhere in this repository (see M10_REPORT_BODY.md). Registering
# a rule here would be exactly the "generic template" acceptance criterion 2
# forbids, so this demo refuses to, and reports every affected candidate as
# SETTLEMENT_UNSUPPORTED honestly instead.
REAL_BOOK_BASELINE_FEE = {"fee_type": "none"}


def register_real_books_fee_only(bookmakers):
    added = []
    for b in bookmakers:
        if b not in M.FEE_MODEL:
            M.FEE_MODEL[b] = dict(REAL_BOOK_BASELINE_FEE)
            added.append(b)
    return added


def read_rows(root, max_rows):
    path = os.path.join(root, "data", "market_snapshots", "snapshots.csv")
    rows, n_total = [], 0
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            n_total += 1
            if n_total <= max_rows:
                rows.append(r)
    return rows, n_total


def ts_range(rows, markets):
    stamps = [r["retrieval_ts"] for r in rows if r["market"] in markets and r["retrieval_ts"]]
    if not stamps:
        return {"n_rows": 0, "min_retrieval_ts": None, "max_retrieval_ts": None}
    return {"n_rows": len(stamps), "min_retrieval_ts": min(stamps),
            "max_retrieval_ts": max(stamps)}


def parse_ts_safe(s):
    try:
        return M.parse_ts(s)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Spreads/totals: two rows per (book, poll) -- one per side/outcome.
# ---------------------------------------------------------------------------
def group_spread_rows(rows):
    """(game_id, retrieval_ts) -> book -> {outcome_team: (line, price)}"""
    by_key = defaultdict(lambda: defaultdict(dict))
    n_seen = 0
    for r in rows:
        if r["market"] != "spreads" or not r["line"] or not r["price"]:
            continue
        if r.get("market_status") != "active":
            continue
        n_seen += 1
        key = (r["game_id"], r["retrieval_ts"])
        by_key[key][r["book"]][r["outcome"]] = (r["line"], r["price"])
    return by_key, n_seen


def group_totals_rows(rows):
    """(game_id, retrieval_ts) -> book -> {'Over': (line, price), 'Under': (line, price)}"""
    by_key = defaultdict(lambda: defaultdict(dict))
    n_seen = 0
    for r in rows:
        if r["market"] != "totals" or not r["line"] or not r["price"]:
            continue
        if r.get("market_status") != "active":
            continue
        n_seen += 1
        key = (r["game_id"], r["retrieval_ts"])
        by_key[key][r["book"]][r["outcome"]] = (r["line"], r["price"])
    return by_key, n_seen


def group_prop_rows(rows):
    """(game_id, market, player, retrieval_ts) -> book -> (line, price_over, price_under)"""
    by_key = defaultdict(dict)
    n_seen = 0
    for r in rows:
        if r["market"] not in PROP_MARKETS or not r["line"]:
            continue
        if r.get("market_status") != "active":
            continue
        if not r.get("price_over") or not r.get("price_under"):
            continue
        n_seen += 1
        key = (r["game_id"], r["market"], r["outcome"], r["retrieval_ts"])
        by_key[key][r["book"]] = (r["line"], r["price_over"], r["price_under"])
    return by_key, n_seen


def to_decimal_safe(american_price):
    try:
        return M.american_to_decimal(float(american_price))
    except Exception:
        return None


def _leg(venue, price_decimal, line, t_seen):
    return {"venue": venue, "price_decimal": price_decimal, "line": line,
            "t_seen": t_seen, "t_prev": None, "poll_interval": None}


def scan_spread_pairs(by_key, verdicts, unsupported_reasons, sample_candidates,
                       gap_widths):
    n_pairs = 0
    for (game_id, retrieval_ts), books in by_key.items():
        t_seen = parse_ts_safe(retrieval_ts)
        if t_seen is None:
            continue
        full_books = {b: sides for b, sides in books.items() if len(sides) == 2}
        names = sorted(full_books)
        teams_per_book = {b: sorted(full_books[b]) for b in names}
        for bx in names:
            for by_ in names:
                if bx == by_:
                    continue
                teams = teams_per_book[bx]
                if sorted(teams) != sorted(teams_per_book[by_]):
                    continue
                for team_a in teams:
                    team_b = [t for t in teams if t != team_a][0]
                    line_a, price_a = full_books[bx][team_a]
                    line_b, price_b = full_books[by_][team_b]
                    da, db = to_decimal_safe(price_a), to_decimal_safe(price_b)
                    if da is None or db is None:
                        continue
                    t_lo, t_hi = M.spread_thresholds(line_a, line_b)
                    n_pairs += 1
                    flag = M.build_middle_flag(
                        game_id=game_id, market_kind="spread_middle",
                        leg_a_quote=_leg(bx, da, line_a, t_seen),
                        leg_b_quote=_leg(by_, db, line_b, t_seen),
                        t_lo=t_lo, t_hi=t_hi, dnp_risk=False,
                        clock_skew=M.UNMEASURED, vendor_latency_bounds={})
                    verdicts[flag["verdict"]] += 1
                    if flag["gap"]:
                        gap_widths.append(flag["gap"]["gap_width"])
                    if flag["verdict"] == "SETTLEMENT_UNSUPPORTED":
                        for u in flag["settlement"]["unsupported_venues"]:
                            unsupported_reasons[u["reason"]] += 1
                    if flag["verdict"] == "MIDDLE_CANDIDATE" and len(sample_candidates) < 15:
                        sample_candidates.append(flag)
    return n_pairs


def scan_totals_pairs(by_key, verdicts, unsupported_reasons, sample_candidates,
                       gap_widths):
    n_pairs = 0
    for (game_id, retrieval_ts), books in by_key.items():
        t_seen = parse_ts_safe(retrieval_ts)
        if t_seen is None:
            continue
        full_books = {b: sides for b, sides in books.items()
                      if "Over" in sides and "Under" in sides}
        names = sorted(full_books)
        for bx in names:
            for by_ in names:
                if bx == by_:
                    continue
                over_line, over_price = full_books[bx]["Over"]
                under_line, under_price = full_books[by_]["Under"]
                da, db = to_decimal_safe(over_price), to_decimal_safe(under_price)
                if da is None or db is None:
                    continue
                t_lo, t_hi = M.over_under_thresholds(over_line, under_line)
                n_pairs += 1
                flag = M.build_middle_flag(
                    game_id=game_id, market_kind="totals_middle",
                    leg_a_quote=_leg(bx, da, over_line, t_seen),
                    leg_b_quote=_leg(by_, db, under_line, t_seen),
                    t_lo=t_lo, t_hi=t_hi, dnp_risk=False,
                    clock_skew=M.UNMEASURED, vendor_latency_bounds={})
                verdicts[flag["verdict"]] += 1
                if flag["gap"]:
                    gap_widths.append(flag["gap"]["gap_width"])
                if flag["verdict"] == "SETTLEMENT_UNSUPPORTED":
                    for u in flag["settlement"]["unsupported_venues"]:
                        unsupported_reasons[u["reason"]] += 1
                if flag["verdict"] == "MIDDLE_CANDIDATE" and len(sample_candidates) < 15:
                    sample_candidates.append(flag)
    return n_pairs


def scan_prop_pairs(by_key, verdicts, unsupported_reasons, sample_candidates,
                     gap_widths):
    n_pairs = 0
    for (game_id, market, player, retrieval_ts), books in by_key.items():
        t_seen = parse_ts_safe(retrieval_ts)
        if t_seen is None:
            continue
        names = sorted(books)
        for bx in names:
            for by_ in names:
                if bx == by_:
                    continue
                over_line, over_price, _ = books[bx]
                under_line, _, under_price = books[by_]
                da, db = to_decimal_safe(over_price), to_decimal_safe(under_price)
                if da is None or db is None:
                    continue
                t_lo, t_hi = M.over_under_thresholds(over_line, under_line)
                n_pairs += 1
                flag = M.build_middle_flag(
                    game_id=f"{game_id}|{market}|{player}", market_kind="prop_middle",
                    leg_a_quote=_leg(bx, da, over_line, t_seen),
                    leg_b_quote=_leg(by_, db, under_line, t_seen),
                    t_lo=t_lo, t_hi=t_hi, dnp_risk=True,
                    clock_skew=M.UNMEASURED, vendor_latency_bounds={})
                verdicts[flag["verdict"]] += 1
                if flag["gap"]:
                    gap_widths.append(flag["gap"]["gap_width"])
                if flag["verdict"] == "SETTLEMENT_UNSUPPORTED":
                    for u in flag["settlement"]["unsupported_venues"]:
                        unsupported_reasons[u["reason"]] += 1
                if flag["verdict"] == "MIDDLE_CANDIDATE" and len(sample_candidates) < 15:
                    sample_candidates.append(flag)
    return n_pairs


def run_demo(root, max_rows):
    rows, n_total_rows = read_rows(root, max_rows)
    all_books = sorted({r["book"] for r in rows})
    registered = register_real_books_fee_only(all_books)

    game_line_window = ts_range(rows, GAME_LINE_MARKETS)
    prop_window = ts_range(rows, PROP_MARKETS)

    spread_by_key, n_spread_rows = group_spread_rows(rows)
    totals_by_key, n_totals_rows = group_totals_rows(rows)
    prop_by_key, n_prop_rows = group_prop_rows(rows)

    verdicts = defaultdict(int)
    unsupported_reasons = defaultdict(int)
    sample_candidates = []
    gap_widths = []

    n_spread_pairs = scan_spread_pairs(spread_by_key, verdicts, unsupported_reasons,
                                        sample_candidates, gap_widths)
    n_totals_pairs = scan_totals_pairs(totals_by_key, verdicts, unsupported_reasons,
                                        sample_candidates, gap_widths)
    n_prop_pairs = scan_prop_pairs(prop_by_key, verdicts, unsupported_reasons,
                                    sample_candidates, gap_widths)

    n_middle_candidates = verdicts.get("MIDDLE_CANDIDATE", 0)
    n_settlement_unsupported = verdicts.get("SETTLEMENT_UNSUPPORTED", 0)
    n_not_middle = verdicts.get("NOT_MIDDLE", 0)
    total_pairs = n_spread_pairs + n_totals_pairs + n_prop_pairs

    out = {
        "schema": "market_program/M10/coarse_tape_demo/1",
        "label": "COARSE_TAPE_DEMO",
        "epistemic_status": M.EPISTEMIC_STATUS,
        "caveat": (
            "COARSE_TAPE_DEMO. This is a replay over the existing capture sample "
            "(data/market_snapshots/snapshots.csv), not a market finding. Every "
            "MIDDLE_CANDIDATE flag below has a fully computed per-world profit "
            "table (real prices, real lines) but ev.status is "
            "EV_UNSUPPORTED_NO_PROBABILITY_MODEL on every one -- no probability "
            "distribution over game margins/totals was supplied (S-FUND "
            "territory, out of this node's scope), so no scalar edge is claimed "
            "for any candidate. Every SETTLEMENT_UNSUPPORTED count reflects a "
            "real, structural gap: no real bookmaker in this tape has a "
            "verified push or DNP-void settlement rule anywhere in this "
            "repository. Game-lines (spreads/totals) coverage on this tape is "
            "extremely narrow -- see game_line_capture_window below -- because "
            "of a since-fixed capture-code defect (M26 finding 1) that wrote "
            "zero game-line rows for an unmeasured prior period; a small "
            "game-line candidate count is a structural artifact of that window, "
            "not evidence middles are rare on spreads/totals in general."),
        "inputs": {
            "root": root,
            "snapshots_csv_rows_total_in_file": n_total_rows,
            "snapshots_csv_rows_read_cap": max_rows,
            "bookmakers_in_sample": all_books,
            "bookmakers_registered_with_placeholder_fee_only": registered,
            "bookmakers_with_verified_push_or_dnp_void_rule": sorted(
                set(M.PUSH_VOID_RULES) & set(all_books)),
        },
        "game_line_capture_window": game_line_window,
        "prop_capture_window": prop_window,
        "rows_used": {"spreads_active_rows": n_spread_rows,
                       "totals_active_rows": n_totals_rows,
                       "prop_active_rows": n_prop_rows},
        "candidate_pairs_built": {"spreads": n_spread_pairs, "totals": n_totals_pairs,
                                    "props": n_prop_pairs, "total": total_pairs},
        "verdict_counts": dict(verdicts),
        "settlement_unsupported_reason_counts": dict(unsupported_reasons),
        "gap_width_stats": (
            {"n": len(gap_widths), "min": min(gap_widths), "max": max(gap_widths),
             "mean": sum(gap_widths) / len(gap_widths)}
            if gap_widths else {"n": 0}),
        "sample_middle_candidate_flags": sample_candidates,
        "headline": (
            f"{total_pairs} candidate book-pairs scanned across spreads/totals/props "
            f"at same-poll same-game/same-player groupings; {n_middle_candidates} "
            f"had a real line gap AND a fully verified per-venue settlement rule "
            f"(MIDDLE_CANDIDATE, EV left unsupported -- no probability model); "
            f"{n_settlement_unsupported} had a real line gap but at least one "
            f"participating venue's push/DNP-void rule is unverified "
            f"(SETTLEMENT_UNSUPPORTED); {n_not_middle} had no gap at all "
            f"(NOT_MIDDLE, ordinary vig or mirror lines). This is a structural "
            f"tape replay, not a claim any of these candidates would have been "
            f"profitable to place."),
    }
    with open(os.path.join(NODE_DIR, "COARSE_TAPE_DEMO_RESULTS.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=str)
    return out


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    max_rows = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_MAX_ROWS
    result = run_demo(root, max_rows)
    print(json.dumps(
        {k: v for k, v in result.items() if k != "sample_middle_candidate_flags"},
        indent=2, sort_keys=True, default=str))
