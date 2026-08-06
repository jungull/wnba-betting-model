"""Fixture tests for BOOKIE_BASELINE metric math -- synthetic games with
known answers. Per M00-U5-style discipline (schema fixtures / test corpora):
timestamps here are SYNTHETIC, not archive bytes, and carry no evidentiary
weight; they test the arithmetic only.

Run: python experiments/market_program/BOOKIE_BASELINE/TESTS.py
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\market_program\M11_CONSENSUS_MODEL")

import build_baseline as bb  # noqa: E402
import consensus as m11  # noqa: E402

FAILURES = []


def check(name, cond):
    if not cond:
        FAILURES.append(name)
        print(f"FAIL: {name}")
    else:
        print(f"ok:   {name}")


# ---------------------------------------------------------------------------
# mae_bias
# ---------------------------------------------------------------------------

def test_mae_bias_known():
    # errors = predicted - actual: [+2, -4, +1, -1] -> MAE=2.0, bias=-0.5
    errs = [2.0, -4.0, 1.0, -1.0]
    mae, bias, n = bb.mae_bias(errs)
    check("mae_bias mae==2.0", math.isclose(mae, 2.0))
    check("mae_bias bias==-0.5", math.isclose(bias, -0.5))
    check("mae_bias n==4", n == 4)


def test_mae_bias_empty():
    mae, bias, n = bb.mae_bias([])
    check("mae_bias empty -> None,None,0", mae is None and bias is None and n == 0)


def test_mae_bias_zero_error_market_perfect():
    # a "perfectly calibrated" market: predicted always equals actual
    errs = [0.0, 0.0, 0.0]
    mae, bias, n = bb.mae_bias(errs)
    check("mae_bias perfect market mae==0", mae == 0.0)
    check("mae_bias perfect market bias==0", bias == 0.0)


# ---------------------------------------------------------------------------
# brier / log loss
# ---------------------------------------------------------------------------

def test_brier_known():
    # p=0.7 y=1 -> (0.3)^2=0.09 ; p=0.3 y=0 -> (0.3)^2=0.09 ; mean=0.09
    pairs = [(0.7, 1.0), (0.3, 0.0)]
    brier, ll, n = bb.brier_logloss(pairs)
    check("brier known value", math.isclose(brier, 0.09, abs_tol=1e-9))
    check("brier n==2", n == 2)


def test_brier_perfect_predictions():
    pairs = [(1.0, 1.0), (0.0, 0.0)]
    brier, ll, n = bb.brier_logloss(pairs)
    check("brier perfect ==0", math.isclose(brier, 0.0, abs_tol=1e-9))
    check("logloss perfect ~0 (clipped)", ll < 1e-6)


def test_brier_random_market_baseline():
    # a coin-flip market always quoting p=0.5 has Brier 0.25 regardless of
    # outcome mix -- the textbook "uninformative baseline" value.
    pairs = [(0.5, 1.0), (0.5, 0.0), (0.5, 1.0), (0.5, 0.0)]
    brier, ll, n = bb.brier_logloss(pairs)
    check("brier coin-flip baseline == 0.25", math.isclose(brier, 0.25, abs_tol=1e-9))


def test_logloss_known():
    # p=0.8 y=1 -> -ln(0.8) ; p=0.2 y=0 -> -ln(0.8) ; mean = -ln(0.8)
    pairs = [(0.8, 1.0), (0.2, 0.0)]
    brier, ll, n = bb.brier_logloss(pairs)
    expect = -math.log(0.8)
    check("logloss known value", math.isclose(ll, expect, abs_tol=1e-9))


def test_brier_empty():
    brier, ll, n = bb.brier_logloss([])
    check("brier empty -> None,None,0", brier is None and ll is None and n == 0)


# ---------------------------------------------------------------------------
# calibration table
# ---------------------------------------------------------------------------

def test_calibration_table_bins_and_counts():
    pairs = [(0.05, 0.0), (0.15, 0.0), (0.15, 1.0), (0.95, 1.0)]
    table = bb.calibration_table(pairs, n_bins=10)
    check("calibration table has 10 bins", len(table) == 10)
    check("calibration bin[0,0.1) has n=1", table[0]["n"] == 1)
    check("calibration bin[0.1,0.2) has n=2", table[1]["n"] == 2)
    check("calibration bin[0.1,0.2) empirical rate == 0.5",
          math.isclose(table[1]["empirical_home_win_rate"], 0.5))
    check("calibration bin[0.9,1.0) has n=1 rate=1.0",
          table[9]["n"] == 1 and table[9]["empirical_home_win_rate"] == 1.0)
    check("calibration empty bin has None rate", table[2]["mean_predicted_p_home"] is None)


def test_calibration_boundary_p_equals_1_falls_in_last_bin():
    table = bb.calibration_table([(1.0, 1.0)], n_bins=10)
    check("p==1.0 falls in the [0.9,1.0) bin, not overflowed",
          table[9]["n"] == 1)


# ---------------------------------------------------------------------------
# match_outcome (join logic) on a tiny synthetic frame
# ---------------------------------------------------------------------------

def _row(game_id, game_date, team, opp, pts, opp_pts, season=2099):
    class R:
        pass
    r = R()
    r.game_id, r.game_date = game_id, game_date
    r.team_abbreviation, r.opp_team_abbreviation = team, opp
    r.pts, r.opp_pts = pts, opp_pts
    r.season, r.season_type = season, "Regular Season"
    return r


def test_match_outcome_exact_date():
    import datetime as dt
    by_pair = {("AAA", "BBB"): [_row("g1", dt.date(2099, 6, 1), "AAA", "BBB", 80, 70)]}
    row, reason = bb.match_outcome(["AAA"], ["BBB"], dt.date(2099, 6, 1), by_pair)
    check("match_outcome exact date matches", row is not None and reason == "MATCHED_EXACT_DATE")


def test_match_outcome_exact_date_resolves_uniquely_even_with_nearby_rematch():
    import datetime as dt
    by_pair = {("AAA", "BBB"): [
        _row("g1", dt.date(2099, 6, 1), "AAA", "BBB", 80, 70),
        _row("g2", dt.date(2099, 6, 2), "AAA", "BBB", 75, 90),
    ]}
    row, reason = bb.match_outcome(["AAA"], ["BBB"], dt.date(2099, 6, 1), by_pair)
    check("exact date still resolves uniquely even with a same-pair 2nd game nearby",
          row is not None and reason == "MATCHED_EXACT_DATE" and row.game_id == "g1")


def test_match_outcome_ambiguous_within_window_never_silently_guessed():
    import datetime as dt
    # No exact-date row exists for the estimate (2099-06-01); both g1
    # (06-02, +1 day) and g0 (05-31, -1 day) fall inside the +/-1 day
    # fallback window -- this must report AMBIGUOUS, never guess one.
    by_pair = {("AAA", "BBB"): [
        _row("g0", dt.date(2099, 5, 31), "AAA", "BBB", 65, 60),
        _row("g1", dt.date(2099, 6, 2), "AAA", "BBB", 75, 90),
    ]}
    row, reason = bb.match_outcome(["AAA"], ["BBB"], dt.date(2099, 6, 1), by_pair)
    check("ambiguous window is reported, not guessed",
          row is None and reason.startswith("AMBIGUOUS_WITHIN_1_DAY"))


def test_match_outcome_far_off_estimate_unmatched():
    import datetime as dt
    by_pair = {("AAA", "BBB"): [_row("g1", dt.date(2099, 6, 1), "AAA", "BBB", 80, 70)]}
    row, reason = bb.match_outcome(["AAA"], ["BBB"], dt.date(2099, 9, 9), by_pair)
    check("far-off estimate with no exact or windowed match -> unmatched",
          row is None and reason.startswith("NO_MASTER_ROW"))


def test_match_outcome_no_pair():
    import datetime as dt
    row, reason = bb.match_outcome(["ZZZ"], ["YYY"], dt.date(2099, 1, 1), {})
    check("match_outcome missing pair -> NO_MASTER_ROW_FOR_TEAM_PAIR",
          row is None and reason == "NO_MASTER_ROW_FOR_TEAM_PAIR")


# ---------------------------------------------------------------------------
# spread/total prediction sign convention -- synthetic game, known answer
# ---------------------------------------------------------------------------

def test_spread_prediction_sign_convention():
    # Home team favored by 8 (home_point = -8.0) -> predicted home margin
    # = -(-8.0) = +8.0. Actual home margin (home_pts - away_pts) = 90-82=8.
    # Error should be exactly 0 (a perfectly calibrated favorite call).
    home_point = -8.0
    pred_home_margin = -home_point
    actual_margin = 90 - 82
    check("spread sign convention: favored home team, perfect call",
          pred_home_margin == 8.0 and (pred_home_margin - actual_margin) == 0.0)

    # Home team underdog by 3.5 (home_point = +3.5) -> predicted home margin
    # = -3.5 (home expected to lose by 3.5). Home actually loses by 10.
    home_point2 = 3.5
    pred2 = -home_point2
    actual2 = 70 - 80  # home lost by 10
    check("spread sign convention: home underdog, error magnitude",
          pred2 == -3.5 and math.isclose(pred2 - actual2, 6.5))


def test_total_prediction_known():
    pred_total = 165.5
    actual_total = 90 + 82
    check("total error known value", math.isclose(pred_total - actual_total, -6.5))


# ---------------------------------------------------------------------------
# M11 delegation sanity -- BOOKIE_BASELINE must never reimplement vig removal
# ---------------------------------------------------------------------------

def test_m11_delegation_two_way_even_market():
    # two books quoting -110/-110 (standard vig): no-vig prob should be 0.5
    probs, param, method, prereg_hash = m11.no_vig([-110, -110])
    check("M11 no_vig even book -> 0.5/0.5",
          math.isclose(probs[0], 0.5, abs_tol=1e-9) and
          math.isclose(probs[1], 0.5, abs_tol=1e-9))
    check("M11 preregistered method is multiplicative_proportional",
          method == m11.VIG_METHOD_MULTIPLICATIVE)


def test_m11_consensus_carries_capture_timestamps():
    quotes = []
    for book, price, opp in (("bookA", -150, 130), ("bookB", -140, 120)):
        q = m11.make_quote(bookmaker=book, price=price,
                            capture_ts="2026-08-06T00:00:00Z", tier="T1",
                            vendor_ts="2026-08-05T16:00:00Z",
                            vendor_ts_semantics="vendor_asserted_unwitnessed",
                            market="h2h", outcome="HOME")
        q["opposite_price"] = opp
        quotes.append(q)
    obj = m11.consensus_fair_value(quotes, allow_t1=True, game_id="synthetic")
    check("M11 consensus object carries capture timestamps",
          len(obj["capture_timestamps_all_contributing_quotes"]) >= 1)
    check("M11 consensus is not a fundamental prediction",
          obj["not_a_fundamental_prediction"] is True)
    check("M11 consensus prob is in (0,1)",
          0.0 < obj["consensus_fair_prob"] < 1.0)


# ---------------------------------------------------------------------------
# caveat text integrity -- the frozen text must hash-match its own constant
# ---------------------------------------------------------------------------

def test_caveat_hash_matches_text():
    import hashlib
    h = hashlib.sha256(bb.CAVEAT_TEXT.encode("utf-8")).hexdigest()
    check("caveat sha256 matches frozen constant", h == bb.CAVEAT_SHA256)


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
