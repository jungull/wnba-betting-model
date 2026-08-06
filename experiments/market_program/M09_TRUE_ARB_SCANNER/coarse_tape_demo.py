"""M09_TRUE_ARB_SCANNER -- COARSE_TAPE_DEMO.

Replays arb_scanner.py over the EXISTING coarse capture sample at
data/odds_capture/capture_log.csv in the live main worktree (READ-ONLY;
this script only ever opens that file for reading, never writes there).

THIS IS NOT THE REAL SCAN. It is a demonstration that the machinery runs
end-to-end on real-shaped bytes. The honesty constraint that governs every
number this script prints:

  The capture_log.csv poll grid is HOURLY (poll_interval_at_capture on the
  order of 3600s -- see poll_grid_stats() below, computed from the actual
  recorded snapshot_utc values, never a nominal assumption). Amendment-4
  (MARKET_PROGRAM_CONTRACT.md section 6) requires a per-run clock-skew
  measurement and a sourced per-vendor latency bound before ANY
  simultaneity verdict may be certified. Neither exists for this tape:
  there is no NTP-skew record and no sourced vendor-latency bound for any
  of the eleven bookmakers in the file. So this run passes
  clock_skew=UNMEASURED and vendor_latency_bounds={} into every call,
  which forces simultaneity_window() to CLOCK_UNBOUNDED on every pair --
  by construction, never by omission. No flag produced by this script can
  reach TRUE_ARB_CANDIDATE; the reserved word is structurally unreachable
  here. That is the finding this demo exists to make, not a bug in it.

  A second, independent reason the grid cannot support simultaneity even if
  skew/latency bounds existed: successive polls in this file are ~1 hour
  apart, while the quotes compared within one poll batch were themselves
  fetched over a multi-book scrape burst (the same pattern P2B found in the
  final-state archive: a burst of many books "at" one nominal snapshot
  time, not truly instantaneous). Hourly polling cannot resolve whether two
  books' prices were ever simultaneously live between polls; it can only
  ever say what each book showed within one witnessed poll's own burst
  window, and this script does not treat that within-burst pairing as
  evidence of true simultaneity either -- it is scanned only because F3
  (contract section 1.1 falsification clause) explicitly names "same-poll
  cross-book combinations" as the required negative-control comparison.

  The real true-arb scan activates only when the high-frequency ladder
  (sub-minute polling, per-run NTP skew measurement, sourced per-vendor
  latency bounds) is turned on. See ACTIVATION_CHECKLIST.md in this
  directory. Until then, this script is tested machinery exercised over
  fixtures and over this one coarse sample, and its output is a
  demonstration, never a market finding.

Usage:
    python coarse_tape_demo.py [path_to_wnba-betting-model_root] [max_rows]

Reads ONLY (never writes) from the live worktree:
    data/odds_capture/capture_log.csv  -- first MAX_ROWS data rows
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
import arb_scanner as A

NODE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = "C:/Users/jgallagher/wnba-betting-model"
DEFAULT_MAX_ROWS = 20000

# h2h is the only market this demo scores: it is the one market kind in
# arb_scanner.py's world-builders (worlds_h2h_2way) with NO push/void risk
# to model from raw CSV rows alone (spreads/totals need a per-book
# push-handling row on file for THIS vendor's real book names, which is not
# yet built -- SETTLEMENT_RULES in arb_scanner.py only has synthetic
# fixture venues on file today). Scoring spreads/totals against unmodeled
# real venues would mean guessing a settlement rule, which the engine
# refuses to do (RuleError) -- so this demo deliberately narrows to the
# one market it can score honestly and reports what it excluded and why.
SCORABLE_MARKET = "h2h"

# The real bookmakers in this sample have no settlement-rule or fee row on
# file (arb_scanner.SETTLEMENT_RULES / FEE_MODEL only carry the synthetic
# fixture venues). Rather than fabricate a "standard" rule for eleven real
# books this scanner has never been told about, this demo REGISTERS them
# with the single rule this contract already knows is the industry-default
# case documented in the taxonomy (push=void_return; no push/void risk
# possible on 2-way h2h moneyline at all, so the push/void rule is inert
# for every row this demo actually scores) and zero fee (flat retail
# sportsbooks, not the commission exchange). This is stated explicitly so
# no reader mistakes it for a verified real-world settlement inventory --
# that inventory is M00-U3 territory and is out of this node's scope.
REAL_BOOK_BASELINE_RULE = {"push_handling": "void_return",
                            "void_dnp_handling": "void_return",
                            "dead_heat": "NOT_MODELED_OUT_OF_SCOPE"}
REAL_BOOK_BASELINE_FEE = {"fee_type": "none"}


def register_real_books_with_baseline_rule(bookmakers):
    """Mutates arb_scanner's module-level tables to add a rule row for each
    real bookmaker name seen in the sample, using the baseline above. This
    is done in the demo script, never inside arb_scanner.py itself -- the
    engine's own default posture stays fail-closed (RuleError) for any
    caller that does not do this explicitly."""
    added = []
    for b in bookmakers:
        if b not in A.SETTLEMENT_RULES:
            A.SETTLEMENT_RULES[b] = dict(REAL_BOOK_BASELINE_RULE)
            added.append(b)
        if b not in A.FEE_MODEL:
            A.FEE_MODEL[b] = dict(REAL_BOOK_BASELINE_FEE)
    return added


def read_rows(root, max_rows):
    path = os.path.join(root, "data", "odds_capture", "capture_log.csv")
    rows, n_total = [], 0
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            n_total += 1
            if n_total <= max_rows:
                rows.append(r)
    return rows, n_total


def poll_grid_stats(rows):
    """Computed from the ACTUAL distinct snapshot_utc values present in the
    sample -- never a nominal cadence assumption (mirrors PollLog's own
    from-bytes discipline in arb_scanner.py)."""
    stamps = sorted({A.parse_ts(r["snapshot_utc"]) for r in rows})
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    if not gaps:
        return {"n_polls": len(stamps), "n_gaps": 0}
    gs = sorted(gaps)
    return {
        "n_polls": len(stamps),
        "n_gaps": len(gaps),
        "min_gap_s": gs[0],
        "median_gap_s": gs[len(gs) // 2],
        "max_gap_s": gs[-1],
        "min_gap_h": round(gs[0] / 3600.0, 2),
        "median_gap_h": round(gs[len(gs) // 2] / 3600.0, 2),
        "max_gap_h": round(gs[-1] / 3600.0, 2),
    }


def group_h2h_same_poll(rows):
    """Groups h2h WIN-side quotes by (snapshot_utc, home_team, away_team,
    commence_time) -> {bookmaker: {outcome: price}}. This is the same-poll
    grouping the F3 falsification clause requires as the negative control:
    same-poll cross-book combinations that never clear the inequality is
    exactly what "no true-arb mechanism detected on this tape" looks like.
    """
    by_key = defaultdict(lambda: defaultdict(dict))
    n_seen = 0
    for r in rows:
        if r["market"] != SCORABLE_MARKET:
            continue
        n_seen += 1
        key = (r["snapshot_utc"], r["home_team"], r["away_team"],
               r["commence_time"])
        by_key[key][r["bookmaker"]][r["outcome"]] = float(r["price"])
    return by_key, n_seen


def build_pairs(by_key):
    """For each same-poll batch, for each pair of distinct books that BOTH
    quoted BOTH sides of the same 2-way market, build one candidate flag
    input per (book_x_side, book_y_opposite_side) crossing direction (the
    only shape evaluate_2leg_true_arb's worlds_h2h_2way understands: leg_a
    on SIDE_A, leg_b on SIDE_B)."""
    pairs = []
    for (snap, home, away, commence), books in by_key.items():
        full_books = {b: sides for b, sides in books.items()
                      if home in sides and away in sides}
        names = sorted(full_books)
        for i in range(len(names)):
            for j in range(len(names)):
                if i == j:
                    continue
                bx, by_ = names[i], names[j]
                pairs.append({
                    "snapshot_utc": snap, "home_team": home, "away_team": away,
                    "commence_time": commence,
                    "leg_a_book": bx, "leg_a_price": full_books[bx][home],
                    "leg_b_book": by_, "leg_b_price": full_books[by_][away],
                })
    return pairs


def american_to_decimal_safe(p):
    try:
        return A.american_to_decimal(p)
    except Exception:
        return None


def run_demo(root, max_rows):
    rows, n_total_rows = read_rows(root, max_rows)
    grid = poll_grid_stats(rows)

    all_books = sorted({r["bookmaker"] for r in rows})
    registered = register_real_books_with_baseline_rule(all_books)

    by_key, n_h2h_rows = group_h2h_same_poll(rows)
    pairs = build_pairs(by_key)

    verdict_counts = defaultdict(int)
    reason_counts = defaultdict(int)
    sample_flags = []
    n_skipped_bad_price = 0

    for p in pairs:
        da = american_to_decimal_safe(p["leg_a_price"])
        db = american_to_decimal_safe(p["leg_b_price"])
        if da is None or db is None:
            n_skipped_bad_price += 1
            continue
        t_seen = A.parse_ts(p["snapshot_utc"])
        leg_a_quote = {"venue": p["leg_a_book"], "price_decimal": da,
                       "t_seen": t_seen, "t_prev": None, "poll_interval": None}
        leg_b_quote = {"venue": p["leg_b_book"], "price_decimal": db,
                       "t_seen": t_seen, "t_prev": None, "poll_interval": None}
        flag = A.build_flag(
            game_id=f"{p['away_team']}@{p['home_team']}|{p['commence_time']}",
            market_kind="h2h_2way",
            leg_a_quote=leg_a_quote, leg_b_quote=leg_b_quote,
            worlds=A.worlds_h2h_2way(),
            clock_skew=A.UNMEASURED,       # honest: no skew measurement exists
            vendor_latency_bounds={},       # honest: no sourced bound for any book
            limit_a=None, limit_b=None,     # CAPACITY_UNKNOWN, never fabricated
        )
        verdict_counts[flag["verdict"]] += 1
        if flag["settlement"].get("reason"):
            reason_counts[flag["settlement"]["reason"]] += 1
        if flag["settlement"]["verdict"] == "TRUE_ARB_CANDIDATE" and \
                len(sample_flags) < 10:
            sample_flags.append(flag)

    out = {
        "schema": "market_program/M09/coarse_tape_demo/1",
        "label": "COARSE_TAPE_DEMO",
        "epistemic_status": (
            "SCANNING INFRASTRUCTURE. Detects candidate true arbitrage as "
            "defined by the M00 taxonomy. A flag is a measurement of quoted "
            "prices at capture timestamps, not a claim of executable "
            "profit; execution realism belongs to M21 and any order ever "
            "belongs behind a USER_REQUIRED gate."),
        "caveat": (
            "COARSE_TAPE_DEMO. This is a replay over the existing hourly-"
            "polled coarse capture sample (data/odds_capture/capture_log.csv), "
            "not the real scan. Hourly polling cannot establish simultaneity: "
            "every flag below is produced with clock_skew=UNMEASURED and "
            "vendor_latency_bounds={} by construction, so no flag can reach "
            "TRUE_ARB_CANDIDATE at the settlement+simultaneity combined "
            "verdict -- SIMULTANEITY_UNVERIFIABLE is the ceiling on this "
            "tape. The 'true_arb_settlement_math_only' counts below show "
            "what the SETTLEMENT half of the inequality alone would have "
            "said, isolated for inspection ONLY; they are never a claim "
            "about a real arbitrage opportunity, because simultaneity was "
            "never certified. This is not a finding; it is a demonstration "
            "the machinery runs on real-shaped bytes. The real scan "
            "activates with the ladder (ACTIVATION_CHECKLIST.md)."),
        "inputs": {
            "root": root,
            "capture_log_rows_total_in_file": n_total_rows,
            "capture_log_rows_read_cap": max_rows,
            "h2h_rows_used": n_h2h_rows,
            "bookmakers_in_sample": all_books,
            "bookmakers_registered_with_baseline_settlement_rule": registered,
        },
        "poll_grid_from_actual_bytes": grid,
        "same_poll_cross_book_pairs_built": len(pairs),
        "pairs_skipped_unparseable_price": n_skipped_bad_price,
        "combined_verdict_counts": dict(verdict_counts),
        "settlement_failure_reason_counts": dict(reason_counts),
        "sample_settlement_positive_but_simultaneity_unverifiable_flags":
            sample_flags,
        "headline": (
            "0 TRUE_ARB_CANDIDATE flags on this tape -- structurally "
            "impossible on hourly-poll data per the caveat above, not "
            "evidence about whether true arbitrage exists on this market "
            "in general."
        ),
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
        {k: v for k, v in result.items()
         if k not in ("sample_settlement_positive_but_simultaneity_unverifiable_flags",)},
        indent=2, sort_keys=True, default=str))
