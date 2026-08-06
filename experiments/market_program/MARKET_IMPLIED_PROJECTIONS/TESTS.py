"""MARKET_IMPLIED_PROJECTIONS -- validation suite.

Run: python experiments/market_program/MARKET_IMPLIED_PROJECTIONS/TESTS.py

Verifies, against SYNTHETIC fixtures with algebraically known answers:
  * the no-vig -> consensus -> implied-mean pipeline recovers a true mean it
    was never shown, to within American-price rounding tolerance;
  * disagreement across books is measured, not averaged away silently;
  * unsupported markets and degenerate probabilities fail closed, never
    silently clip or impute;
  * the probit function is the correct inverse of the normal CDF;
  * the CSV-loading engine end-to-end, against tiny synthetic CSVs shaped
    exactly like the two real schemas (historical / live), with hand-
    computed expected coverage counts;
  * the frozen preregistration hashes (contract, dispersion) are stable.

Stdlib only.
"""
from __future__ import annotations

import csv
import math
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_M11_DIR = os.path.normpath(os.path.join(_HERE, "..", "M11_CONSENSUS_MODEL"))
sys.path = [p for p in sys.path if p not in (_M11_DIR, _HERE)]
sys.path.insert(0, _M11_DIR)
sys.path.insert(0, _HERE)  # local modules (fixtures.py) must shadow M11's own fixtures.py

import consensus as m11              # noqa: E402
import implied_mean as im            # noqa: E402
import projection_schema as sch      # noqa: E402
import engine as eng                 # noqa: E402
import fixtures as fx                # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    status = "PASS" if cond else "FAIL"
    print(f"{status}  {name}" + (f"  -- {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------------------
# T01: probit is the correct inverse of the normal CDF
# ---------------------------------------------------------------------------
def t01_probit_roundtrip():
    ok = True
    worst = 0.0
    for x in [-3.5, -2.0, -1.0, -0.3, 0.0, 0.15, 0.9, 1.7, 2.8, 3.9]:
        p = im.norm_cdf(x)
        x2 = im.norm_ppf(p)
        worst = max(worst, abs(x - x2))
        if abs(x - x2) > 1e-6:
            ok = False
    # known quantiles
    ok = ok and abs(im.norm_ppf(0.5) - 0.0) < 1e-9
    ok = ok and abs(im.norm_ppf(0.975) - 1.959963985) < 1e-6
    ok = ok and abs(im.norm_ppf(0.025) - (-1.959963985)) < 1e-6
    check("T01_probit_roundtrip_and_known_quantiles", ok, f"worst_err={worst:.2e}")


# ---------------------------------------------------------------------------
# T02: symmetric market (p_over exactly 0.5) implies mean == line exactly
# ---------------------------------------------------------------------------
def t02_symmetric_market_mean_equals_line():
    quotes = [
        fx.make_synthetic_quote(bookmaker="bookA", p_over=0.5, overround=1.05,
                                 capture_ts=1_700_000_000, market="player_points", point=20.5),
        fx.make_synthetic_quote(bookmaker="bookB", p_over=0.5, overround=1.08,
                                 capture_ts=1_700_000_010, market="player_points", point=20.5),
    ]
    cobj = m11.consensus_fair_value(quotes, allow_t1=True)
    ok1 = cobj["n_trusted"] == 2
    ok2 = abs(cobj["consensus_fair_prob"] - 0.5) < 1e-6
    mu, sigma, note = im.implied_mean_from_probability(
        market_key="player_points", line=20.5, vig_free_over_prob=cobj["consensus_fair_prob"])
    ok3 = abs(mu - 20.5) < 1e-4
    check("T02_symmetric_market_mean_equals_line", ok1 and ok2 and ok3,
          f"n_trusted={cobj['n_trusted']} p={cobj['consensus_fair_prob']} mu={mu}")


# ---------------------------------------------------------------------------
# T03: known true mean recovered from a single book (up to price-rounding
# tolerance introduced by decimal_to_american's 4-dp rounding)
# ---------------------------------------------------------------------------
def t03_single_book_recovers_known_mean():
    true_mean = 23.7
    quotes, p_over_true = fx.synthetic_market_from_true_mean(
        market_key="player_points", line=20.5, true_mean=true_mean,
        books=[("bookA", 1.05)])
    cobj = m11.consensus_fair_value(quotes, allow_t1=True)
    mu, sigma, note = im.implied_mean_from_probability(
        market_key="player_points", line=20.5, vig_free_over_prob=cobj["consensus_fair_prob"])
    err = abs(mu - true_mean)
    check("T03_single_book_recovers_known_mean", err < 1e-2,
          f"true={true_mean} recovered={mu:.4f} err={err:.2e}")


# ---------------------------------------------------------------------------
# T04: multiple books, SAME true mean -> consensus recovers it, and
# book_dispersion (across-book spread) is ~0 since every book prices the
# same fair probability (only vig differs, which no-vig removes)
# ---------------------------------------------------------------------------
def t04_multi_book_same_truth_low_dispersion():
    true_mean = 18.2
    quotes, p_over_true = fx.synthetic_market_from_true_mean(
        market_key="player_rebounds", line=17.5, true_mean=true_mean,
        books=[("bookA", 1.03), ("bookB", 1.07), ("bookC", 1.12), ("bookD", 1.02)])
    cobj = m11.consensus_fair_value(quotes, allow_t1=True)
    mu, sigma, note = im.implied_mean_from_probability(
        market_key="player_rebounds", line=17.5, vig_free_over_prob=cobj["consensus_fair_prob"])
    ok1 = cobj["n_trusted"] == 4
    ok2 = cobj["uncertainty_std"] < 1e-4
    ok3 = abs(mu - true_mean) < 1e-2
    check("T04_multi_book_same_truth_low_dispersion", ok1 and ok2 and ok3,
          f"n={cobj['n_trusted']} std={cobj['uncertainty_std']:.2e} mu_err={abs(mu-true_mean):.2e}")


# ---------------------------------------------------------------------------
# T05: books DISAGREE (different true means priced) -> dispersion is
# measured as materially > 0, not averaged away silently
# ---------------------------------------------------------------------------
def t05_disagreeing_books_nonzero_dispersion():
    p_low = im.forward_probability_from_mean(market_key="player_points", line=20.5, mean=18.0)
    p_high = im.forward_probability_from_mean(market_key="player_points", line=20.5, mean=25.0)
    quotes = [
        fx.make_synthetic_quote(bookmaker="bookA", p_over=p_low, overround=1.05,
                                 capture_ts=1_700_000_000, market="player_points", point=20.5),
        fx.make_synthetic_quote(bookmaker="bookB", p_over=p_high, overround=1.05,
                                 capture_ts=1_700_000_010, market="player_points", point=20.5),
    ]
    cobj = m11.consensus_fair_value(quotes, allow_t1=True)
    ok = cobj["uncertainty_std"] > 0.05 and cobj["disagreement_score"] > 0.1
    check("T05_disagreeing_books_nonzero_dispersion", ok,
          f"std={cobj['uncertainty_std']:.4f} disagreement={cobj['disagreement_score']:.4f}")


# ---------------------------------------------------------------------------
# T06: unsupported market fails closed (no ad hoc sigma, no silent skip)
# ---------------------------------------------------------------------------
def t06_unsupported_market_fails_closed():
    raised = False
    try:
        im.implied_mean_from_probability(market_key="player_turnovers", line=2.5,
                                          vig_free_over_prob=0.5)
    except im.ImpliedMeanError:
        raised = True
    check("T06_unsupported_market_fails_closed", raised)


# ---------------------------------------------------------------------------
# T07: degenerate probability (0 or 1) fails closed, never clipped
# ---------------------------------------------------------------------------
def t07_degenerate_probability_fails_closed():
    raised_low = raised_high = False
    try:
        im.implied_mean_from_probability(market_key="player_points", line=20.5, vig_free_over_prob=0.0)
    except im.ImpliedMeanError:
        raised_low = True
    try:
        im.implied_mean_from_probability(market_key="player_points", line=20.5, vig_free_over_prob=1.0)
    except im.ImpliedMeanError:
        raised_high = True
    check("T07_degenerate_probability_fails_closed", raised_low and raised_high)


# ---------------------------------------------------------------------------
# T08: T2-only input is excluded (engine never silently treats T2 as trusted)
# ---------------------------------------------------------------------------
def t08_t2_only_input_excluded():
    q = fx.make_synthetic_quote(bookmaker="bookA", p_over=0.5, overround=1.05,
                                 capture_ts=1_700_000_000, market="player_points",
                                 point=20.5, tier="T2")
    cobj = m11.consensus_fair_value([q], allow_t1=True)
    ok = cobj["n_trusted"] == 0 and cobj["consensus_fair_prob"] is None
    check("T08_t2_only_input_excluded", ok, f"n_trusted={cobj['n_trusted']}")


# ---------------------------------------------------------------------------
# T09: preregistration hashes stable and contract hash matches
# ---------------------------------------------------------------------------
def t09_preregistration_hashes_and_contract_hash():
    ok1 = sch.CONTRACT_SHA256 == m11.CONTRACT_SHA256
    ok2 = im.DISPERSION_PREREGISTRATION_HASH == im.sha256_hex(
        im.canonical_json(im.DISPERSION_PREREGISTRATION))
    ok3 = im.DISPERSION_PREREGISTRATION["fitted_from_this_programs_data"] is False
    check("T09_preregistration_hashes_and_contract_hash", ok1 and ok2 and ok3)


# ---------------------------------------------------------------------------
# T10: end-to-end engine over a tiny synthetic HISTORICAL-schema CSV
# ---------------------------------------------------------------------------
HIST_HEADER = ["game_id", "api_event_id", "home_team", "away_team",
               "commence_time", "snapshot_requested_utc",
               "snapshot_returned_utc", "bookmaker_key", "market_key",
               "player_name", "line", "over_price", "under_price",
               "last_update"]


def _hist_row(game_id, player, line, over_price, under_price, book="draftkings",
              market="player_points", ts="2026-07-30T22:55:42Z"):
    return {
        "game_id": game_id, "api_event_id": "evt_" + game_id,
        "home_team": "Team A", "away_team": "Team B",
        "commence_time": "2026-07-31T02:10:00Z",
        "snapshot_requested_utc": ts, "snapshot_returned_utc": ts,
        "bookmaker_key": book, "market_key": market, "player_name": player,
        "line": line, "over_price": over_price, "under_price": under_price,
        "last_update": ts,
    }


def t10_engine_end_to_end_historical_schema():
    true_mean = 24.0
    line = 20.5
    quotes, p_over = fx.synthetic_market_from_true_mean(
        market_key="player_points", line=line, true_mean=true_mean,
        books=[("draftkings", 1.05), ("fanduel", 1.08)])

    rows = []
    for q in quotes:
        rows.append(_hist_row("g1", "Player One", line, q["price"], q["opposite_price"],
                               book=q["bookmaker"]))
    # a second player in the same game with an unsupported market -> must be
    # skipped, not crash the engine
    rows.append(_hist_row("g1", "Player Two", 2.5, -110, -110, market="player_turnovers"))
    # a player with only a missing/invalid price -> skipped
    rows.append(_hist_row("g1", "Player Three", 15.5, "", "-110"))

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "hist.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=HIST_HEADER)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        out_rows, cov = eng.run_engine(path, source_label="unit_test_historical")

    ok1 = len(out_rows) == 1
    ok2 = cov["n_distinct_player_games_seen"] == 3
    ok3 = cov["n_distinct_player_games_with_at_least_one_implied_mean_row"] == 1
    ok4 = cov["skip_reason_counts"].get(eng.REASON_UNSUPPORTED_MARKET) == 1
    ok5 = cov["skip_reason_counts"].get(eng.REASON_MISSING_PRICE) == 1
    mu_recovered = out_rows[0]["stat_projections"]["player_points"]["mean"] if out_rows else None
    ok6 = out_rows and abs(mu_recovered - true_mean) < 1e-2
    ok7 = out_rows and out_rows[0]["tier"] == "T1" and out_rows[0]["timestamp_quality"] == "VENDOR_ASSERTED"
    ok8 = out_rows and out_rows[0]["source_extra"]["d027_caveat_sha256"] == eng.D027_CAVEAT_SHA256
    check("T10_engine_end_to_end_historical_schema",
          ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and ok7 and ok8,
          f"n_out={len(out_rows)} cov={cov} mu={mu_recovered}")


# ---------------------------------------------------------------------------
# T11: end-to-end engine over a tiny synthetic LIVE-schema CSV (no game_id
# column -- api_event_id is the game key)
# ---------------------------------------------------------------------------
LIVE_HEADER = ["api_event_id", "home_team", "away_team", "commence_time",
               "bookmaker_key", "market_key", "player_name", "line",
               "over_price", "under_price", "snapshot_utc", "last_update"]


def _live_row(event_id, player, line, over_price, under_price, book="fanduel",
              market="player_assists", ts="2026-07-31T14:22:34Z"):
    return {
        "api_event_id": event_id, "home_team": "Team A", "away_team": "Team B",
        "commence_time": "2026-07-31T23:30:00Z", "bookmaker_key": book,
        "market_key": market, "player_name": player, "line": line,
        "over_price": over_price, "under_price": under_price,
        "snapshot_utc": "20260731T142234Z", "last_update": ts,
    }


def t11_engine_end_to_end_live_schema():
    true_mean = 6.3
    line = 5.5
    quotes, p_over = fx.synthetic_market_from_true_mean(
        market_key="player_assists", line=line, true_mean=true_mean,
        books=[("fanduel", 1.06)])
    rows = [_live_row("evtX", "Player Four", line, quotes[0]["price"], quotes[0]["opposite_price"])]

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "live.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=LIVE_HEADER)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        out_rows, cov = eng.run_engine(path, source_label="unit_test_live")

    ok1 = len(out_rows) == 1
    ok2 = out_rows[0]["game_id"] is None
    ok3 = out_rows[0]["game_key_raw"] == "evtX"
    ok4 = out_rows[0]["game_key_resolution"] == "RAW_EVENT_KEY_UNRESOLVED"
    mu_recovered = out_rows[0]["stat_projections"]["player_assists"]["mean"]
    ok5 = abs(mu_recovered - true_mean) < 1e-2
    check("T11_engine_end_to_end_live_schema", ok1 and ok2 and ok3 and ok4 and ok5,
          f"cov={cov} mu={mu_recovered}")


# ---------------------------------------------------------------------------
# T12: off-consensus-line rows are excluded from the trusted set and
# counted, not silently blended into the consensus at the wrong line
# ---------------------------------------------------------------------------
def t12_off_consensus_line_excluded_and_counted():
    line = 20.5
    quotes, _ = fx.synthetic_market_from_true_mean(
        market_key="player_points", line=line, true_mean=22.0,
        books=[("bookA", 1.05), ("bookB", 1.05)])
    rows = [
        _hist_row("g2", "Player Five", line, quotes[0]["price"], quotes[0]["opposite_price"], book="bookA"),
        _hist_row("g2", "Player Five", line, quotes[1]["price"], quotes[1]["opposite_price"], book="bookB"),
        # a third book quoting a DIFFERENT (off-consensus) line
        _hist_row("g2", "Player Five", 21.5, -110, -110, book="bookC"),
    ]
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "hist2.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=HIST_HEADER)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        out_rows, cov = eng.run_engine(path, source_label="unit_test_offline")
    ok1 = len(out_rows) == 1
    ok2 = out_rows[0]["source_extra"]["number_of_books"] == 2
    ok3 = out_rows[0]["source_extra"]["n_off_consensus_line"] == 1
    check("T12_off_consensus_line_excluded_and_counted", ok1 and ok2 and ok3,
          f"n_books={out_rows[0]['source_extra']['number_of_books'] if out_rows else None}")


def run_all():
    t01_probit_roundtrip()
    t02_symmetric_market_mean_equals_line()
    t03_single_book_recovers_known_mean()
    t04_multi_book_same_truth_low_dispersion()
    t05_disagreeing_books_nonzero_dispersion()
    t06_unsupported_market_fails_closed()
    t07_degenerate_probability_fails_closed()
    t08_t2_only_input_excluded()
    t09_preregistration_hashes_and_contract_hash()
    t10_engine_end_to_end_historical_schema()
    t11_engine_end_to_end_live_schema()
    t12_off_consensus_line_excluded_and_counted()

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    summary = {"suite": "MARKET_IMPLIED_PROJECTIONS/TESTS.py",
               "n_pass": n_pass, "n_fail": n_fail, "n_total": len(RESULTS)}
    print(summary)
    return n_fail == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
