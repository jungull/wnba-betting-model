"""BOOKIE_BASELINE / book_ranking.py -- FIXED bookmaker identity ranking.

Governed by D036 point 4 (experiments/player_program/orchestration/
DECISION_LEDGER.jsonl, decision_id D036_SCOREBOARD_MEASUREMENT_SEMANTICS):

    "Best/worst book = FIXED bookmaker identities ranked over the same
    matched universe and cutoff with a minimum common-sample threshold;
    per-game closest-book selection prohibited."

and by MARKET_PROGRAM_CONTRACT.md (sha256
1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de) and
D034_GRADUATION_STANDARD under the same ledger: de-vigged threshold
probabilities are the primary quantity; no distributional-margin claim is
made anywhere in this module.

REUSE, NOT REIMPLEMENTATION (read-only imports):
  * build_baseline.py            -- load_outcomes, load_archive,
                                     match_outcome, extract_market,
                                     mae_bias, brier_logloss, NAME_TO_ABBR,
                                     ET_OFFSET_HOURS, parse_dt, CAVEAT_TEXT,
                                     CAVEAT_SHA256. This module calls these
                                     exactly as build_baseline defines them;
                                     it does not alter or fork any of them.
  * M11_CONSENSUS_MODEL/consensus.py -- no_vig() is the ONLY vig-removal
                                     path used here. Vig math is delegated
                                     to M11 per the coordinator's explicit
                                     instruction; this module never computes
                                     a de-vigged probability by any other
                                     route.

WHAT "FIXED IDENTITY" MEANS HERE: a bookmaker key (e.g. "fanduel",
"draftkings") is ranked as itself, across the same set of games as every
other ranked book. This module never selects, per game, whichever book
happens to have the tightest line that game -- point 4 explicitly names
that "per-game closest-book selection" and prohibits it. A book is only
eligible to be ranked on a market/class if it has an admissible quote on at
least MIN_COMMON_THRESHOLD matched games; the games actually scored for a
ranked group of books are the INTERSECTION of their individual game sets
("the same matched universe"), not each book's own most favorable subset.
Books are dropped from the candidate pool, smallest individual footprint
first, until either the intersection clears the threshold or fewer than
two books remain -- reported explicitly in both cases, never silently
guessed at a smaller n or a mismatched universe.

Stdlib + pandas + pyarrow only (via build_baseline). No git, no network, no
subagents.
"""
from __future__ import annotations

import json
import sys
import os
import hashlib
import datetime as dt
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import build_baseline as bb  # noqa: E402 -- read-only reuse, never forked

M11_DIR = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\M11_CONSENSUS_MODEL"
sys.path.insert(0, M11_DIR)
import consensus as m11  # noqa: E402 -- vig math delegated here, only here

OUT_DIR = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\BOOKIE_BASELINE"

MIN_COMMON_THRESHOLD = 200  # D036 point 4 "minimum common-sample threshold"
# (task instruction: >=200 common games per snapshot class/market ranking)

D036_DECISION_ID = "D036_SCOREBOARD_MEASUREMENT_SEMANTICS"
D036_LEDGER_PATH = "experiments/player_program/orchestration/DECISION_LEDGER.jsonl"
D036_POINT4_TEXT = (
    "Best/worst book = FIXED bookmaker identities ranked over the same "
    "matched universe and cutoff with a minimum common-sample threshold; "
    "per-game closest-book selection prohibited."
)


# ---------------------------------------------------------------------------
# 1. Rebuild the matched-game universe -- calls build_baseline's own join
#    primitives verbatim (NAME_TO_ABBR / parse_dt / ET_OFFSET_HOURS /
#    match_outcome); this ~15-line loop is orchestration, not new matching
#    logic -- the same procedure build_baseline.main() runs, reused so this
#    module can attach per-book quote data build_baseline's own output
#    files (outcome_rows.json) do not carry.
# ---------------------------------------------------------------------------

def build_matched_games():
    mt, by_pair = bb.load_outcomes()
    per_game, load_audit = bb.load_archive()

    matched = {}
    unmatched_n = 0
    for gid, rec in per_game.items():
        meta = rec["meta"]
        home, away = meta["home_team"], meta["away_team"]
        home_abbrs = bb.NAME_TO_ABBR.get(home)
        away_abbrs = bb.NAME_TO_ABBR.get(away)
        if not home_abbrs or not away_abbrs:
            unmatched_n += 1
            continue
        ct = bb.parse_dt(meta["commence_time"])
        et_date = (ct - dt.timedelta(hours=bb.ET_OFFSET_HOURS)).date()
        row, reason = bb.match_outcome(home_abbrs, away_abbrs, et_date, by_pair)
        if row is None:
            unmatched_n += 1
            continue
        matched[gid] = {
            "season": int(row.season),
            "home_pts": float(row.pts),
            "away_pts": float(row.opp_pts),
        }
    return per_game, matched, load_audit, unmatched_n


# ---------------------------------------------------------------------------
# 2. Per-book, per-market, per-class raw value collection
#    (game_id -> value), keyed by snapshot class then market then book.
#    "value" is exactly the per-book input build_baseline's Series.add_*
#    would have received for the cross_book/best_book pass, but retained
#    per FIXED book identity instead of pooled/single-book-only.
# ---------------------------------------------------------------------------

def collect_book_data(per_game, matched):
    # data[class][market][book][game_id] = value
    #   market "moneyline" value = (p_home, y_home_won) pair
    #   market "spread"/"total" value = signed error (pred - actual)
    data = {
        cls: {"moneyline": defaultdict(dict), "spread": defaultdict(dict),
              "total": defaultdict(dict)}
        for cls in ("EARLY", "LATE")
    }
    n_matched_per_class = {"EARLY": 0, "LATE": 0}

    for gid, rec in per_game.items():
        if gid not in matched:
            continue
        out = matched[gid]
        meta = rec["meta"]
        home, away = meta["home_team"], meta["away_team"]
        actual_margin = out["home_pts"] - out["away_pts"]
        actual_total = out["home_pts"] + out["away_pts"]
        y_home_won = 1.0 if out["home_pts"] > out["away_pts"] else 0.0

        for cls, snap in rec["snaps"].items():
            n_matched_per_class[cls] += 1

            h2h = bb.extract_market(snap, "h2h", home, away)
            for book, q in h2h.items():
                try:
                    # vig removal delegated to M11 -- no other route used
                    probs, _param, _method, _hash = m11.no_vig(
                        [q["home_price"], q["away_price"]])
                    p_home = probs[0]
                except Exception:
                    continue
                data[cls]["moneyline"][book][gid] = (p_home, y_home_won)

            sp = bb.extract_market(snap, "spreads", home, away)
            for book, q in sp.items():
                if q.get("home_point") is None:
                    continue
                pred_home_margin = -q["home_point"]
                data[cls]["spread"][book][gid] = pred_home_margin - actual_margin

            tt = bb.extract_market(snap, "totals", home, away)
            for book, q in tt.items():
                if q.get("point") is None:
                    continue
                data[cls]["total"][book][gid] = q["point"] - actual_total

    return data, n_matched_per_class


# ---------------------------------------------------------------------------
# 3. Common-universe ranking for one (class, market)
# ---------------------------------------------------------------------------

def rank_market(book_game_values: dict, n_matched_in_class: int, metric_kind: str,
                 min_threshold: int = MIN_COMMON_THRESHOLD):
    """book_game_values: {book: {game_id: value}}. metric_kind in
    {"mae_bias", "brier"}. Returns a result dict with either a computed
    ranking over a common intersected universe, or an explicit
    INSUFFICIENT status -- never a silently smaller or mismatched universe.
    """
    # Step 1: individual-footprint eligibility (D036: "minimum common-sample
    # threshold" -- a book cannot be ranked at all below this on its own
    # footprint, prior to any intersection).
    candidates = {b: set(gv.keys()) for b, gv in book_game_values.items()
                  if len(gv) >= min_threshold}
    dropped_individual_threshold = sorted(
        b for b, gv in book_game_values.items()
        if len(gv) < min_threshold)

    if len(candidates) < 2:
        return {
            "status": "INSUFFICIENT_CANDIDATE_BOOKS",
            "reason": (
                f"fewer than 2 books reach the individual "
                f"{min_threshold}-game threshold "
                f"({len(candidates)} qualify)"),
            "books_meeting_individual_threshold": sorted(candidates),
            "books_below_individual_threshold": dropped_individual_threshold,
            "min_common_threshold": min_threshold,
        }

    # Step 2: shrink to the SAME matched universe (intersection), dropping
    # the smallest individual footprint first, until either the
    # intersection clears the threshold or fewer than two books remain.
    dropped_for_intersection = []
    remaining = dict(candidates)
    universe = set.intersection(*remaining.values())
    while len(universe) < min_threshold and len(remaining) >= 2:
        smallest = min(remaining, key=lambda b: len(remaining[b]))
        dropped_for_intersection.append(
            {"book": smallest, "individual_n": len(remaining[smallest])})
        del remaining[smallest]
        universe = set.intersection(*remaining.values()) if remaining else set()

    if len(universe) < min_threshold or len(remaining) < 2:
        return {
            "status": "NO_COMMON_UNIVERSE_MEETS_THRESHOLD",
            "reason": (
                f"no combination of >=2 books among "
                f"{sorted(candidates)} shares an intersected matched "
                f"universe of >= {min_threshold} games (dropping down to "
                f"a single book to satisfy the threshold on its own "
                f"footprint is not a common-universe ranking and is "
                f"refused here)"),
            "books_meeting_individual_threshold": sorted(candidates),
            "books_below_individual_threshold": dropped_individual_threshold,
            "min_common_threshold": min_threshold,
        }

    # Step 3: compute the metric for every surviving book over the exact
    # same `universe` game-id set (never per-book-favorable subsets).
    books_out = {}
    for book in sorted(remaining):
        vals = [book_game_values[book][gid] for gid in universe]
        if metric_kind == "mae_bias":
            mae, bias, n = bb.mae_bias(vals)
            books_out[book] = {
                "mae": mae, "bias": bias, "n": n,
                "coverage_pct_of_class_matched_games": (
                    round(100.0 * n / n_matched_in_class, 2)
                    if n_matched_in_class else None),
            }
        elif metric_kind == "brier":
            brier, logloss, n = bb.brier_logloss(vals)
            books_out[book] = {
                "brier": brier, "log_loss": logloss, "n": n,
                "coverage_pct_of_class_matched_games": (
                    round(100.0 * n / n_matched_in_class, 2)
                    if n_matched_in_class else None),
            }
        else:
            raise ValueError(f"unknown metric_kind {metric_kind!r}")

    return {
        "status": "OK",
        "min_common_threshold": min_threshold,
        "common_universe_n": len(universe),
        "n_matched_games_in_class": n_matched_in_class,
        "books_ranked": sorted(remaining),
        "books_dropped_below_individual_threshold": dropped_individual_threshold,
        "books_dropped_to_reach_common_intersection": dropped_for_intersection,
        "per_book": books_out,
    }


# ---------------------------------------------------------------------------
# 4. Pooled rank across the three market metrics
# ---------------------------------------------------------------------------

def pooled_rank(spread_result, total_result, ml_result):
    """Pooled rank = average of each metric's ascending rank (1 = best:
    lowest spread MAE, lowest total MAE, lowest Brier), restricted to books
    that were ranked (status OK, same-universe-per-market) in ALL THREE
    markets -- a book missing from one market's ranking is reported but
    excluded from the pooled best/worst call, never imputed."""
    ok = {"spread": spread_result, "total": total_result, "moneyline": ml_result}
    non_ok = {m: r["status"] for m, r in ok.items() if r["status"] != "OK"}
    if non_ok:
        return {
            "status": "INCOMPLETE_MARKETS",
            "reason": (
                "pooled rank requires all three markets to have an OK "
                "common-universe ranking; markets not OK: "
                f"{non_ok}"),
            "markets_not_ok": non_ok,
        }

    common_books = (set(spread_result["per_book"])
                     & set(total_result["per_book"])
                     & set(ml_result["per_book"]))
    if len(common_books) < 2:
        return {
            "status": "INSUFFICIENT_COMMON_BOOKS_ACROSS_MARKETS",
            "reason": (
                "fewer than 2 books were ranked in all three markets "
                f"({sorted(common_books)})"),
            "books_ranked_per_market": {
                "spread": sorted(spread_result["per_book"]),
                "total": sorted(total_result["per_book"]),
                "moneyline": sorted(ml_result["per_book"]),
            },
        }

    def ranks_for(metric_dict, key, book_set):
        # ascending: lowest value = rank 1 = best
        ordered = sorted(book_set, key=lambda b: metric_dict[b][key])
        return {b: i + 1 for i, b in enumerate(ordered)}

    spread_ranks = ranks_for(spread_result["per_book"], "mae", common_books)
    total_ranks = ranks_for(total_result["per_book"], "mae", common_books)
    brier_ranks = ranks_for(ml_result["per_book"], "brier", common_books)

    table = []
    for b in sorted(common_books):
        avg_rank = (spread_ranks[b] + total_ranks[b] + brier_ranks[b]) / 3.0
        table.append({
            "book": b,
            "spread_mae": spread_result["per_book"][b]["mae"],
            "spread_rank": spread_ranks[b],
            "spread_n": spread_result["per_book"][b]["n"],
            "total_mae": total_result["per_book"][b]["mae"],
            "total_rank": total_ranks[b],
            "total_n": total_result["per_book"][b]["n"],
            "moneyline_brier": ml_result["per_book"][b]["brier"],
            "moneyline_rank": brier_ranks[b],
            "moneyline_n": ml_result["per_book"][b]["n"],
            "pooled_avg_rank": round(avg_rank, 4),
        })
    table.sort(key=lambda r: r["pooled_avg_rank"])

    return {
        "status": "OK",
        "n_books_pooled": len(table),
        "pooling_method": (
            "unweighted mean of each metric's within-market ascending "
            "rank (spread MAE rank, total MAE rank, moneyline Brier "
            "rank); 1 = best on that metric. Each metric's ranks are "
            "computed over that metric's OWN common-universe result "
            "(possibly a different game-id set per market, per D036's "
            "per-market same-universe requirement) -- the pooled score "
            "combines RANKS, never raw metric values across markets, "
            "because spread MAE, total MAE, and Brier are not "
            "commensurable units."),
        "table": table,
        "best_book": table[0]["book"] if table else None,
        "worst_book": table[-1]["book"] if table else None,
    }


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main():
    per_game, matched, load_audit, unmatched_n = build_matched_games()
    data, n_matched_per_class = collect_book_data(per_game, matched)

    caveat_sha_check = hashlib.sha256(
        bb.CAVEAT_TEXT.encode("utf-8")).hexdigest()
    assert caveat_sha_check == bb.CAVEAT_SHA256, (
        "CAVEAT_TEXT / CAVEAT_SHA256 mismatch in build_baseline.py -- "
        "refusing to emit book_ranking.json against a drifted caveat")

    out = {
        "schema": "market_program/BOOKIE_BASELINE/book_ranking/1",
        "provenance": {
            "d036_decision_id": D036_DECISION_ID,
            "d036_ledger_path": D036_LEDGER_PATH,
            "d036_point4_text": D036_POINT4_TEXT,
            "contract_path": bb.CONTRACT_PATH,
            "contract_sha256": bb.CONTRACT_SHA256,
            "caveat_text": bb.CAVEAT_TEXT,
            "caveat_sha256": bb.CAVEAT_SHA256,
            "vig_method": m11.PREREGISTERED_VIG_METHOD,
            "vig_preregistration_hash": m11.PREREGISTRATION_HASH,
            "vig_delegated_to": "M11_CONSENSUS_MODEL/consensus.py::no_vig "
                                 "(never reimplemented in this module)",
            "min_common_threshold": MIN_COMMON_THRESHOLD,
            "per_game_closest_book_selection": "PROHIBITED (D036 point 4); "
                "this module ranks FIXED bookmaker identities on a common "
                "intersected game-id universe only.",
            "input_archive": bb.ARCHIVE_PATH,
            "input_archive_note": "LIVE worktree, read-only, same T1 "
                "vendor-asserted / vendor_ts_semantics=vendor_asserted_"
                "unwitnessed archive build_baseline.py uses; same "
                "in-play exclusion and EARLY/LATE snapshot-class "
                "definition (hour 16 / hour 23 of requested_ts).",
            "outcomes_source": bb.MASTER_TEAM_PATH,
        },
        "load_audit": {
            "n_distinct_games_in_archive": len(per_game),
            "n_games_matched_to_outcomes": len(matched),
            "n_games_unmatched": unmatched_n,
            "n_matched_games_by_class": n_matched_per_class,
        },
        "snapshot_classes": {},
    }

    for cls in ("EARLY", "LATE"):
        n_in_class = n_matched_per_class[cls]
        spread_result = rank_market(
            data[cls]["spread"], n_in_class, "mae_bias")
        total_result = rank_market(
            data[cls]["total"], n_in_class, "mae_bias")
        ml_result = rank_market(
            data[cls]["moneyline"], n_in_class, "brier")
        pooled = pooled_rank(spread_result, total_result, ml_result)

        out["snapshot_classes"][cls] = {
            "n_matched_games_in_class": n_in_class,
            "markets": {
                "spread": spread_result,
                "total": total_result,
                "moneyline": ml_result,
            },
            "pooled_rank": pooled,
        }

    with open(f"{OUT_DIR}/book_ranking.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)

    print("classes:", list(out["snapshot_classes"]))
    for cls, rec in out["snapshot_classes"].items():
        pr = rec["pooled_rank"]
        print(f"  {cls}: pooled_rank status={pr['status']}",
              f"best={pr.get('best_book')} worst={pr.get('worst_book')}"
              if pr["status"] == "OK" else "")
    return out


if __name__ == "__main__":
    main()
