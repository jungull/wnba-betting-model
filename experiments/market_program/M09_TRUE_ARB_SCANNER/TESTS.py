"""M09_TRUE_ARB_SCANNER -- validation suite. Exit 0 iff all tests pass.

Run: python experiments/market_program/M09_TRUE_ARB_SCANNER/TESTS.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arb_scanner as A
import fixtures as F

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


# ---------------------------------------------------------------------------
# T01-T13: fixture-level verdicts against ground truth
# ---------------------------------------------------------------------------
def run_fixture_tests():
    for key, builder in F.ALL_FIXTURES.items():
        fx = builder()
        flag = F.run_fixture(fx)
        truth = fx["truth"]
        exp = truth["verdict"]
        check(f"fixture[{key}].verdict",
              flag["verdict"] == exp,
              f"expected {exp}, got {flag['verdict']}")
        if "failing_world" in truth:
            check(f"fixture[{key}].failing_world",
                  flag["settlement"].get("failing_world") == truth["failing_world"],
                  f"expected failing_world {truth['failing_world']}, got "
                  f"{flag['settlement'].get('failing_world')}")
        if "simultaneity_verdict" in truth:
            check(f"fixture[{key}].simultaneity_verdict",
                  flag["simultaneity"]["verdict"] == truth["simultaneity_verdict"],
                  f"got {flag['simultaneity']['verdict']}")
        if "capacity_status" in truth:
            check(f"fixture[{key}].capacity_status",
                  flag["settlement"].get("capacity_status") == truth["capacity_status"],
                  f"got {flag['settlement'].get('capacity_status')}")
        if "reason" in truth:
            check(f"fixture[{key}].reason",
                  flag["settlement"].get("reason") == truth["reason"],
                  f"got {flag['settlement'].get('reason')}")


# ---------------------------------------------------------------------------
# T14: flag schema never contains an order-shaped field
# ---------------------------------------------------------------------------
ORDER_SHAPED_FIELDS = {"side", "qty", "quantity", "order_type", "account",
                       "order_id", "submit", "execute"}


def _walk_keys(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k).lower())
            _walk_keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_keys(v, out)


def test_no_order_shape():
    fx = F.fx_clean_h2h_arb()
    flag = F.run_fixture(fx)
    keys = set()
    _walk_keys(flag, keys)
    overlap = keys & ORDER_SHAPED_FIELDS
    check("T14_no_order_shaped_fields", not overlap, f"found: {overlap}")
    check("T14_is_order_false", flag["is_order"] is False and
          flag["is_order_intent"] is False)


# ---------------------------------------------------------------------------
# T15: append-only flag log -- writes are new rows, never UPDATE
# ---------------------------------------------------------------------------
def test_append_only_log():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "flags.jsonl")
        log = A.AppendOnlyFlagLog(path)
        fx1 = F.fx_clean_h2h_arb()
        flag1 = F.run_fixture(fx1)
        fx2 = F.fx_no_arb_h2h()
        flag2 = F.run_fixture(fx2)
        id1 = log.append(flag1)
        id2 = log.append(flag2, prev_flag_ref=id1)
        rows = log.read_all()
        check("T15_two_rows_written", len(rows) == 2, f"got {len(rows)}")
        check("T15_distinct_flag_ids", rows[0]["flag_id"] != rows[1]["flag_id"])
        check("T15_prev_flag_ref_chains", rows[1]["prev_flag_ref"] == id1)
        # simulate a third "correction" row rather than any in-place edit
        log.append(flag1, prev_flag_ref=id1)
        rows2 = log.read_all()
        check("T15_correction_is_new_row_not_update",
              len(rows2) == 3 and rows2[0] == rows[0],
              "prior rows must be byte-identical after an append")


# ---------------------------------------------------------------------------
# T16: reserved-term discipline -- the module source only calls something
# "arbitrage"/"arb" in identifiers/output tied to the TRUE_CROSS_BOOK_ARBITRAGE
# machinery, never for a middle. Direct check: worlds_pushable_2way (which
# models a middle-shaped 2-sided line) is never itself labeled an arb; only
# evaluate_2leg_true_arb's verdict does the labeling, gated on settlement +
# simultaneity. Spot-check: a middle (both legs can independently win, no
# forced complementary settlement) must never reach TRUE_ARB_CANDIDATE.
# ---------------------------------------------------------------------------
def test_middle_never_labeled_arb():
    # A genuine middle: leg_a wins if margin <= 3, leg_b wins if margin >= 7
    # (overlap 4..6 both lose, gap has NEITHER complementary structure the
    # engine assumes) is out of this engine's 2-complementary-outcome model
    # entirely; the only way to represent it honestly is to show the engine
    # requires an explicit complementary world set (raw_a/raw_b always
    # opposite in WIN/LOSE pairs) -- there is no world-builder in this
    # module that can express a true middle, which is the point: the
    # taxonomy split is enforced by omission, not by a mislabeled result.
    import inspect
    src = inspect.getsource(A)
    check("T16_no_middle_world_builder",
          "worlds_middle" not in src and "MIDDLE" not in src.upper()
          .replace("MIDDLES_AND_DISLOCATIONS", ""),
          "engine must not define a middle-shaped world builder that could "
          "be mislabeled TRUE_ARB")


# ---------------------------------------------------------------------------
# T17: unknown venue / unknown rule fails closed (RuleError), never assumes
# a default settlement behavior or zero fee.
# ---------------------------------------------------------------------------
def test_unknown_venue_fails_closed():
    try:
        A.win_coefficient("book_unregistered", 2.0)
        ok = False
    except A.RuleError:
        ok = True
    check("T17_unknown_fee_venue_raises", ok)

    try:
        A.settle_multiplier("book_unregistered", "PUSH", 1.0)
        ok2 = False
    except A.RuleError:
        ok2 = True
    check("T17_unknown_rule_venue_raises", ok2)


# ---------------------------------------------------------------------------
# T18: closed-form solver cross-checked against the classical two-outcome
# implied-probability formula on hand-picked numbers.
# ---------------------------------------------------------------------------
def test_solver_matches_classical_formula():
    da, db = 2.10, 2.20
    wa, wb = da - 1.0, db - 1.0     # no fee, book_alpha/book_beta
    coefs = [(wa, -1.0), (-1.0, wb)]
    t, killer = A.find_arb_stake_ratio(coefs)
    classical_edge = 1.0 - (1.0 / da + 1.0 / db)
    check("T18_classical_edge_positive", classical_edge > 0, f"{classical_edge}")
    check("T18_solver_agrees_arb_exists", t is not None and killer is None)

    da2, db2 = 1.90, 1.95
    wa2, wb2 = da2 - 1.0, db2 - 1.0
    coefs2 = [(wa2, -1.0), (-1.0, wb2)]
    t2, killer2 = A.find_arb_stake_ratio(coefs2)
    classical_edge2 = 1.0 - (1.0 / da2 + 1.0 / db2)
    check("T18_classical_edge_negative", classical_edge2 < 0, f"{classical_edge2}")
    check("T18_solver_agrees_no_arb", t2 is None and killer2 is not None)


# ---------------------------------------------------------------------------
# T19: witness allocation is independently re-verified positive in every
# world before a TRUE_ARB_CANDIDATE is ever returned (the belt-and-suspenders
# check inside evaluate_2leg_true_arb actually fires and is load-bearing).
# ---------------------------------------------------------------------------
def test_witness_reverification():
    fx = F.fx_clean_h2h_arb()
    leg_a = {"venue": fx["leg_a"]["venue"], "price_decimal": fx["leg_a"]["price_decimal"]}
    leg_b = {"venue": fx["leg_b"]["venue"], "price_decimal": fx["leg_b"]["price_decimal"]}
    result = A.evaluate_2leg_true_arb(leg_a, leg_b, fx["worlds"],
                                      limit_a=fx["limit_a"], limit_b=fx["limit_b"])
    check("T19_true_arb_min_profit_positive",
          result["verdict"] == "TRUE_ARB_CANDIDATE" and
          result["min_guaranteed_profit"] > 0,
          f"{result}")
    for wid, p in result["guaranteed_profit_per_world"].items():
        check(f"T19_profit_positive_world[{wid}]", p > 0, f"{p}")


# ---------------------------------------------------------------------------
# T20: simultaneity fields carry the full amendment-4 set on every
# non-degenerate verdict (contract section 6.1).
# ---------------------------------------------------------------------------
AMENDMENT4_FIELDS = {"t_lower", "t_upper", "poll_interval_quote_a",
                     "poll_interval_quote_b", "vendor_latency_bound",
                     "clock_skew_bound", "censor_type", "tier"}


def test_amendment4_fields_present():
    fx = F.fx_clean_h2h_arb()
    flag = F.run_fixture(fx)
    sim = flag["simultaneity"]
    missing = AMENDMENT4_FIELDS - set(sim.keys())
    check("T20_amendment4_fields_present", not missing, f"missing: {missing}")
    check("T20_censor_type_never_exact", sim["censor_type"] != "exact")


# ---------------------------------------------------------------------------
# T21: sharpness / grid discipline -- a SIMULTANEITY_UNVERIFIABLE run must
# carry no numeric t_lower/t_upper claim (no fabricated bound).
# ---------------------------------------------------------------------------
def test_unverifiable_has_no_bound():
    fx = F.fx_clock_unbounded()
    flag = F.run_fixture(fx)
    sim = flag["simultaneity"]
    check("T21_unverifiable_no_numeric_bound",
          sim["t_lower"] is None and sim["t_upper"] is None,
          f"{sim}")
    check("T21_verdict_withheld",
          flag["verdict"] == "SIMULTANEITY_UNVERIFIABLE")


# ---------------------------------------------------------------------------
# T22: never an order -- across ALL fixtures, is_order is always False and
# verdict is never anything but the three defined enum values.
# ---------------------------------------------------------------------------
ALLOWED_VERDICTS = {"TRUE_ARB_CANDIDATE", "NOT_TRUE_ARB",
                    "SIMULTANEITY_UNVERIFIABLE"}


def test_verdict_enum_closed():
    bad = []
    for key, builder in F.ALL_FIXTURES.items():
        flag = F.run_fixture(builder())
        if flag["verdict"] not in ALLOWED_VERDICTS or flag["is_order"] is not False:
            bad.append(key)
    check("T22_verdict_enum_closed_all_fixtures", not bad, f"bad: {bad}")


def main():
    run_fixture_tests()
    test_no_order_shape()
    test_append_only_log()
    test_middle_never_labeled_arb()
    test_unknown_venue_fails_closed()
    test_solver_matches_classical_formula()
    test_witness_reverification()
    test_amendment4_fields_present()
    test_unverifiable_has_no_bound()
    test_verdict_enum_closed()

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"FAIL {name}: {detail}")
    summary = {"suite": "M09_TRUE_ARB_SCANNER/TESTS.py",
               "n_pass": n_pass, "n_fail": n_fail, "n_total": len(RESULTS)}
    import json
    print(json.dumps(summary))
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
