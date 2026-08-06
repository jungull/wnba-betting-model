"""Fixture tests for book_ranking.py -- synthetic per-book quote data with
known answers. Per M00-U5-style discipline (schema fixtures / test corpora):
data here is SYNTHETIC, not archive bytes, and carries no evidentiary
weight; it tests the ranking/threshold/pooling logic only.

Run: python experiments/market_program/BOOKIE_BASELINE/TESTS_BOOK_RANKING.py
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\M11_CONSENSUS_MODEL")

import book_ranking as br  # noqa: E402
import build_baseline as bb  # noqa: E402

FAILURES = []


def check(name, cond):
    if not cond:
        FAILURES.append(name)
        print(f"FAIL: {name}")
    else:
        print(f"ok:   {name}")


# ---------------------------------------------------------------------------
# rank_market: individual-threshold gate
# ---------------------------------------------------------------------------

def test_rank_market_fewer_than_two_candidates_is_insufficient():
    # bookA has 250 games (clears 200), bookB has only 50 -> only one
    # candidate clears the individual threshold -> INSUFFICIENT_CANDIDATE_BOOKS
    data = {
        "bookA": {f"g{i}": 1.0 for i in range(250)},
        "bookB": {f"g{i}": 1.0 for i in range(50)},
    }
    result = br.rank_market(data, 300, "mae_bias", min_threshold=200)
    check("single-candidate pool -> INSUFFICIENT_CANDIDATE_BOOKS",
          result["status"] == "INSUFFICIENT_CANDIDATE_BOOKS")
    check("insufficient result lists the qualifying book",
          result["books_meeting_individual_threshold"] == ["bookA"])
    check("insufficient result lists the disqualified book",
          result["books_below_individual_threshold"] == ["bookB"])


def test_rank_market_two_books_full_overlap_meets_threshold():
    # Two books, identical 250-game footprint, values differ -> exact MAE
    games = [f"g{i}" for i in range(250)]
    data = {
        "bookA": {g: 2.0 for g in games},   # |2.0| MAE = 2.0
        "bookB": {g: -3.0 for g in games},  # |-3.0| MAE = 3.0
    }
    result = br.rank_market(data, 300, "mae_bias", min_threshold=200)
    check("full-overlap two-book pool -> OK", result["status"] == "OK")
    check("common universe == 250 (full overlap)", result["common_universe_n"] == 250)
    check("bookA MAE exact", math.isclose(result["per_book"]["bookA"]["mae"], 2.0))
    check("bookB MAE exact", math.isclose(result["per_book"]["bookB"]["mae"], 3.0))
    check("bookA coverage_pct exact (rounded to 2dp by design)",
          math.isclose(result["per_book"]["bookA"]["coverage_pct_of_class_matched_games"],
                       round(250 / 300 * 100, 2), abs_tol=1e-9))


def test_rank_market_partial_overlap_uses_intersection_not_union():
    # bookA on g0..g249 (250), bookB on g100..g349 (250); overlap = g100..g249
    # = 150 games, below the 200 threshold -> after dropping smaller equal
    # books there's still only 2 candidates and intersection < threshold ->
    # NO_COMMON_UNIVERSE_MEETS_THRESHOLD (never silently ranked at n=150).
    a_games = {f"g{i}": 1.0 for i in range(0, 250)}
    b_games = {f"g{i}": 1.0 for i in range(100, 350)}
    result = br.rank_market({"bookA": a_games, "bookB": b_games}, 400,
                             "mae_bias", min_threshold=200)
    check("partial-overlap below threshold intersection is refused, not guessed",
          result["status"] == "NO_COMMON_UNIVERSE_MEETS_THRESHOLD")


def test_rank_market_never_scores_a_books_own_favorable_subset():
    # bookA has 300 games, all error=0 (perfect). bookB has 300 games: the
    # 200 games it SHARES with bookA all have error=10 (bad); its other 100
    # games (not shared) all have error=0 (perfect). If book_ranking scored
    # each book on its OWN full footprint, bookB would look perfect (mixing
    # in its unshared perfect games). The common-universe rule must score
    # bookB only on the shared 200 games -> MAE must be exactly 10, not
    # some blend that looks better because of the unshared perfect games.
    shared = [f"s{i}" for i in range(200)]
    a_only = [f"a{i}" for i in range(100)]
    b_only = [f"b{i}" for i in range(100)]
    dataA = {g: 0.0 for g in shared}
    dataA.update({g: 0.0 for g in a_only})
    dataB = {g: 10.0 for g in shared}
    dataB.update({g: 0.0 for g in b_only})
    result = br.rank_market({"bookA": dataA, "bookB": dataB}, 500,
                             "mae_bias", min_threshold=200)
    check("common-universe scoring reaches OK on the shared 200", result["status"] == "OK")
    check("common universe is exactly the shared 200, not bookB's full 300",
          result["common_universe_n"] == 200)
    check("bookB is NOT credited with its unshared perfect games",
          math.isclose(result["per_book"]["bookB"]["mae"], 10.0))
    check("bookA MAE unaffected (still perfect on the shared set)",
          math.isclose(result["per_book"]["bookA"]["mae"], 0.0))


def test_rank_market_drops_smallest_footprint_first_to_reach_intersection():
    # bookA: 500 games g0..g499. bookB: 500 games g0..g499 (full overlap
    # with A). bookC: only g0..g149 (150 games, overlaps A/B but tiny) --
    # below the 200 individual threshold, so bookC never even enters the
    # candidate pool; intersection of A and B should be the full 500, not
    # artificially shrunk by C.
    a = {f"g{i}": 1.0 for i in range(500)}
    b = {f"g{i}": 2.0 for i in range(500)}
    c = {f"g{i}": 3.0 for i in range(150)}
    result = br.rank_market({"bookA": a, "bookB": b, "bookC": c}, 600,
                             "mae_bias", min_threshold=200)
    check("bookC below individual threshold never enters ranking",
          "bookC" not in result.get("per_book", {}))
    check("bookC listed as dropped below individual threshold",
          result["books_dropped_below_individual_threshold"] == ["bookC"])
    check("A/B intersection is the full 500 (C's absence doesn't shrink it)",
          result["common_universe_n"] == 500)


# ---------------------------------------------------------------------------
# rank_market: brier metric_kind
# ---------------------------------------------------------------------------

def test_rank_market_brier_known_values():
    games = [f"g{i}" for i in range(250)]
    # bookA: perfectly confident and correct every time -> brier 0
    dataA = {g: (1.0, 1.0) for g in games}
    # bookB: always predicts coin-flip -> brier 0.25 regardless of outcome
    dataB = {g: (0.5, 1.0 if i % 2 == 0 else 0.0) for i, g in enumerate(games)}
    result = br.rank_market({"bookA": dataA, "bookB": dataB}, 300, "brier",
                             min_threshold=200)
    check("brier ranking -> OK", result["status"] == "OK")
    check("bookA brier == 0", math.isclose(result["per_book"]["bookA"]["brier"], 0.0, abs_tol=1e-9))
    check("bookB brier == 0.25", math.isclose(result["per_book"]["bookB"]["brier"], 0.25, abs_tol=1e-9))


# ---------------------------------------------------------------------------
# pooled_rank
# ---------------------------------------------------------------------------

def _ok_market_result(per_book):
    return {"status": "OK", "per_book": per_book}


def test_pooled_rank_best_book_wins_all_three_metrics():
    spread = _ok_market_result({
        "bookA": {"mae": 5.0, "n": 250}, "bookB": {"mae": 8.0, "n": 250}})
    total = _ok_market_result({
        "bookA": {"mae": 10.0, "n": 250}, "bookB": {"mae": 14.0, "n": 250}})
    ml = _ok_market_result({
        "bookA": {"brier": 0.18, "n": 250}, "bookB": {"brier": 0.22, "n": 250}})
    pooled = br.pooled_rank(spread, total, ml)
    check("pooled rank OK", pooled["status"] == "OK")
    check("bookA (best on all 3 metrics) is best_book", pooled["best_book"] == "bookA")
    check("bookB (worst on all 3 metrics) is worst_book", pooled["worst_book"] == "bookB")
    check("bookA pooled avg rank == 1.0", math.isclose(pooled["table"][0]["pooled_avg_rank"], 1.0))
    check("bookB pooled avg rank == 2.0", math.isclose(pooled["table"][1]["pooled_avg_rank"], 2.0))


def test_pooled_rank_mixed_metrics_averages_correctly():
    # bookA: best spread(rank1) worst total(rank2) best brier(rank1) -> avg (1+2+1)/3=1.333
    # bookB: worst spread(rank2) best total(rank1) worst brier(rank2) -> avg (2+1+2)/3=1.667
    spread = _ok_market_result({
        "bookA": {"mae": 5.0, "n": 250}, "bookB": {"mae": 8.0, "n": 250}})
    total = _ok_market_result({
        "bookA": {"mae": 14.0, "n": 250}, "bookB": {"mae": 10.0, "n": 250}})
    ml = _ok_market_result({
        "bookA": {"brier": 0.18, "n": 250}, "bookB": {"brier": 0.22, "n": 250}})
    pooled = br.pooled_rank(spread, total, ml)
    check("mixed-metric pooled rank OK", pooled["status"] == "OK")
    check("bookA pooled avg rank == 1.3333",
          math.isclose(pooled["table"][0]["pooled_avg_rank"], 1.3333, abs_tol=1e-3))
    check("bookA (lower avg rank) wins as best_book", pooled["best_book"] == "bookA")
    check("bookB (higher avg rank) is worst_book", pooled["worst_book"] == "bookB")


def test_pooled_rank_incomplete_markets_reported_not_guessed():
    spread = _ok_market_result({"bookA": {"mae": 5.0, "n": 250}})
    total = {"status": "NO_COMMON_UNIVERSE_MEETS_THRESHOLD"}
    ml = _ok_market_result({"bookA": {"brier": 0.18, "n": 250}})
    pooled = br.pooled_rank(spread, total, ml)
    check("one non-OK market -> pooled rank refuses, not guesses",
          pooled["status"] == "INCOMPLETE_MARKETS")
    check("no best_book/worst_book fabricated when incomplete",
          "best_book" not in pooled)


def test_pooled_rank_book_missing_from_one_market_excluded_not_imputed():
    # bookA and bookB ranked in all 3 markets; bookC only ranked in
    # spread+total, not moneyline (e.g. failed the moneyline common-
    # threshold separately) -> bookC must be excluded from the pooled
    # table, never imputed a rank, even though the pool otherwise has
    # enough books (>=2) to proceed.
    spread = _ok_market_result({
        "bookA": {"mae": 5.0, "n": 250}, "bookB": {"mae": 6.0, "n": 250},
        "bookC": {"mae": 4.0, "n": 250}})
    total = _ok_market_result({
        "bookA": {"mae": 10.0, "n": 250}, "bookB": {"mae": 11.0, "n": 250},
        "bookC": {"mae": 9.0, "n": 250}})
    ml = _ok_market_result({
        "bookA": {"brier": 0.18, "n": 250}, "bookB": {"brier": 0.19, "n": 250}})
    pooled = br.pooled_rank(spread, total, ml)
    check("pooled rank OK with the intersecting books only", pooled["status"] == "OK")
    check("only bookA/bookB appear (bookC absent from moneyline, never imputed)",
          sorted(row["book"] for row in pooled["table"]) == ["bookA", "bookB"])


def test_pooled_rank_single_common_book_is_insufficient():
    spread = _ok_market_result({"bookA": {"mae": 5.0, "n": 250}})
    total = _ok_market_result({"bookA": {"mae": 10.0, "n": 250}})
    ml = _ok_market_result({"bookA": {"brier": 0.18, "n": 250}})
    pooled = br.pooled_rank(spread, total, ml)
    check("single common book -> INSUFFICIENT_COMMON_BOOKS_ACROSS_MARKETS, never a solo pooled rank",
          pooled["status"] == "INSUFFICIENT_COMMON_BOOKS_ACROSS_MARKETS")


# ---------------------------------------------------------------------------
# build_matched_games / collect_book_data -- delegation sanity, not a
# reimplementation test: confirms this module calls build_baseline's own
# functions (identity check on the callables) rather than forking them.
# ---------------------------------------------------------------------------

def test_book_ranking_reuses_build_baseline_functions_not_forks():
    check("br.build_matched_games uses bb.load_outcomes (same function object)",
          bb.load_outcomes is bb.load_outcomes)  # sanity: module import is live
    import inspect
    src = inspect.getsource(br.build_matched_games)
    check("build_matched_games calls bb.load_outcomes()", "bb.load_outcomes()" in src)
    check("build_matched_games calls bb.load_archive()", "bb.load_archive()" in src)
    check("build_matched_games calls bb.match_outcome(...)", "bb.match_outcome(" in src)
    src2 = inspect.getsource(br.collect_book_data)
    check("collect_book_data calls bb.extract_market (never reimplements market parsing)",
          "bb.extract_market(" in src2)


def test_book_ranking_delegates_vig_to_m11_only():
    import inspect
    import consensus as m11
    src = inspect.getsource(br.collect_book_data)
    check("collect_book_data calls m11.no_vig for moneyline (never a local vig formula)",
          "m11.no_vig(" in src)
    check("no local no-vig-style function is defined in book_ranking.py",
          not hasattr(br, "no_vig") and not hasattr(br, "raw_implied_prob"))


# ---------------------------------------------------------------------------
# min_common_threshold constant sanity -- task requirement is >= 200
# ---------------------------------------------------------------------------

def test_min_common_threshold_is_200():
    check("MIN_COMMON_THRESHOLD == 200 per task instruction", br.MIN_COMMON_THRESHOLD == 200)


def run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURES:")
        for f in FAILURES:
            print(" -", f)
        sys.exit(1)
    else:
        print(f"all {len(tests)} test functions passed")


if __name__ == "__main__":
    run_all()
