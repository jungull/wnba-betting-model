"""M10_MIDDLES -- validation suite. Exit 0 iff all tests pass.

Run: python experiments/market_program/M10_MIDDLES/TESTS.py
"""
from __future__ import annotations

import inspect
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import middle_scanner as M
import fixtures as F

_M09_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "M09_TRUE_ARB_SCANNER"))
if _M09_DIR not in sys.path:
    sys.path.append(_M09_DIR)  # appended, never inserted at 0 -- see
    # middle_scanner.py's own comment: M09's directory also has a
    # fixtures.py, and giving it priority would shadow M10's fixtures.py.
import arb_scanner as ARB

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


# ---------------------------------------------------------------------------
# T01-Tn: fixture-level verdicts against ground truth
# ---------------------------------------------------------------------------
def run_fixture_tests():
    for key, builder in F.ALL_FIXTURES.items():
        fx = builder()
        flag = F.run_fixture(fx)
        truth = fx["truth"]
        exp = truth["verdict"]
        check(f"fixture[{key}].verdict", flag["verdict"] == exp,
              f"expected {exp}, got {flag['verdict']}")

        if "n_worlds" in truth:
            n = len(flag["worlds"]) if flag["worlds"] is not None else 0
            check(f"fixture[{key}].n_worlds", n == truth["n_worlds"],
                  f"expected {truth['n_worlds']}, got {n}")

        if "gap_win_win_integers" in truth:
            got = flag["gap"]["gap_win_win_integers"] if flag["gap"] else None
            check(f"fixture[{key}].gap_win_win_integers",
                  got == truth["gap_win_win_integers"],
                  f"expected {truth['gap_win_win_integers']}, got {got}")

        if truth.get("push_at_a_equals_win"):
            wp = flag["settlement"]["world_profit"]
            wc_a = flag["settlement"]["win_coef_a"]
            expected_profit = wc_a * flag["settlement"]["stake_a"] + \
                flag["settlement"]["win_coef_b"] * flag["settlement"]["stake_b"]
            check(f"fixture[{key}].push_at_a_equals_win",
                  abs(wp["PUSH_AT_A"] - expected_profit) < 1e-9,
                  f"got {wp['PUSH_AT_A']}, expected {expected_profit}")

        if truth.get("push_at_a_equals_void"):
            wp = flag["settlement"]["world_profit"]
            expected_profit = 0.0 * flag["settlement"]["stake_a"] + \
                flag["settlement"]["win_coef_b"] * flag["settlement"]["stake_b"]
            check(f"fixture[{key}].push_at_a_equals_void",
                  abs(wp["PUSH_AT_A"] - expected_profit) < 1e-9,
                  f"got {wp['PUSH_AT_A']}, expected {expected_profit}")

        if truth.get("push_at_b_equals_void"):
            wp = flag["settlement"]["world_profit"]
            expected_profit = flag["settlement"]["win_coef_a"] * \
                flag["settlement"]["stake_a"] + 0.0 * flag["settlement"]["stake_b"]
            check(f"fixture[{key}].push_at_b_equals_void",
                  abs(wp["PUSH_AT_B"] - expected_profit) < 1e-9,
                  f"got {wp['PUSH_AT_B']}, expected {expected_profit}")

        if truth.get("dnp_world_present"):
            wp = flag["settlement"]["world_profit"]
            check(f"fixture[{key}].dnp_world_present", "SUBJECT_DNP" in wp,
                  f"worlds: {list(wp)}")
            check(f"fixture[{key}].dnp_world_is_void_both",
                  abs(wp["SUBJECT_DNP"]) < 1e-9, f"got {wp['SUBJECT_DNP']}")


# ---------------------------------------------------------------------------
# T: EV computation -- computed only with an explicit probability model;
# unsupported (None) otherwise. Never a generic/invented default.
# ---------------------------------------------------------------------------
def test_ev_unsupported_without_probabilities():
    fx = F.fx_clean_half_point_middle()
    flag = F.run_fixture(fx)
    check("ev_unsupported_status",
          flag["ev"]["status"] == "EV_UNSUPPORTED_NO_PROBABILITY_MODEL")
    check("ev_unsupported_value_none", flag["ev"]["value"] is None)


def test_ev_computed_with_probabilities():
    fx = F.fx_clean_half_point_middle()
    flag_dry = F.run_fixture(fx)
    world_ids = list(flag_dry["settlement"]["world_profit"])
    # 3 worlds: BELOW_GAP, IN_GAP, ABOVE_GAP
    probs = {w: 1.0 / len(world_ids) for w in world_ids}
    flag = F.run_fixture(fx, probabilities=probs)
    check("ev_computed_status", flag["ev"]["status"] == "EV_COMPUTED")
    expected = sum(flag_dry["settlement"]["world_profit"][w] * probs[w] for w in world_ids)
    check("ev_computed_value_matches_hand_calc",
          abs(flag["ev"]["value"] - expected) < 1e-9,
          f"got {flag['ev']['value']}, expected {expected}")

    # Degenerate check: probability mass 1.0 entirely on IN_GAP must return
    # EXACTLY that world's profit.
    degenerate = {w: (1.0 if w == "IN_GAP" else 0.0) for w in world_ids}
    flag2 = F.run_fixture(fx, probabilities=degenerate)
    check("ev_degenerate_all_mass_in_gap",
          abs(flag2["ev"]["value"] - flag_dry["settlement"]["world_profit"]["IN_GAP"]) < 1e-9)


def test_expected_value_rejects_malformed_probabilities():
    profit = {"A": 1.0, "B": -1.0}
    bad_sum = False
    try:
        M.expected_value(profit, {"A": 0.5, "B": 0.4})
    except ValueError:
        bad_sum = True
    check("ev_rejects_bad_sum", bad_sum)

    bad_cover = False
    try:
        M.expected_value(profit, {"A": 1.0})
    except ValueError:
        bad_cover = True
    check("ev_rejects_incomplete_coverage", bad_cover)


# ---------------------------------------------------------------------------
# T: flag schema never contains an order-shaped field
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
    fx = F.fx_clean_half_point_middle()
    flag = F.run_fixture(fx)
    keys = set()
    _walk_keys(flag, keys)
    overlap = keys & ORDER_SHAPED_FIELDS
    check("no_order_shaped_fields", not overlap, f"found: {overlap}")
    check("is_order_false", flag["is_order"] is False and
          flag["is_order_intent"] is False)


def test_verdict_enum_closed_and_never_order():
    bad = []
    for key, builder in F.ALL_FIXTURES.items():
        flag = F.run_fixture(builder())
        if flag["verdict"] not in M.ALLOWED_VERDICTS or flag["is_order"] is not False:
            bad.append(key)
    check("verdict_enum_closed_all_fixtures", not bad, f"bad: {bad}")


# ---------------------------------------------------------------------------
# T: append-only flag log (reused unchanged from arb_scanner.py -- generic
# over any flag dict, no venue-table state).
# ---------------------------------------------------------------------------
def test_append_only_log():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "middle_flags.jsonl")
        log = M.AppendOnlyFlagLog(path)
        flag1 = F.run_fixture(F.fx_clean_half_point_middle())
        flag2 = F.run_fixture(F.fx_mirror_lines_not_middle())
        id1 = log.append(flag1)
        id2 = log.append(flag2, prev_flag_ref=id1)
        rows = log.read_all()
        check("two_rows_written", len(rows) == 2, f"got {len(rows)}")
        check("distinct_flag_ids", rows[0]["flag_id"] != rows[1]["flag_id"])
        check("prev_flag_ref_chains", rows[1]["prev_flag_ref"] == id1)
        log.append(flag1, prev_flag_ref=id1)
        rows2 = log.read_all()
        check("correction_is_new_row_not_update",
              len(rows2) == 3 and rows2[0] == rows[0],
              "prior rows must be byte-identical after an append")


# ---------------------------------------------------------------------------
# T: reserved-term discipline. "arbitrage"/"arb" as a WORD describing this
# module's OWN output is never used -- but legitimate references to M09's
# own names (arb_scanner, find_arb_stake_ratio, ARB module alias) are
# expected and fine, since M10 imports M09's real machinery per the
# dispatch's explicit "reuse rather than reinvent" instruction. This is a
# precise check, not a blanket string-absence check.
# ---------------------------------------------------------------------------
def test_reserved_term_discipline():
    check("verdicts_never_named_arbitrage",
          not any("ARB" in v.upper() for v in M.ALLOWED_VERDICTS),
          f"{M.ALLOWED_VERDICTS}")
    src = inspect.getsource(M)
    check("no_claim_a_middle_is_arbitrage",
          "is arbitrage" not in src.lower() and "is an arbitrage" not in src.lower())
    world_ids = set()
    for key, builder in F.ALL_FIXTURES.items():
        flag = F.run_fixture(builder())
        if flag["worlds"]:
            world_ids |= {w["world_id"] for w in flag["worlds"]}
    check("world_ids_never_arb_named",
          not any("ARB" in w.upper() for w in world_ids), f"{world_ids}")


# ---------------------------------------------------------------------------
# T: acceptance criterion 3 -- every flag records BOTH legs' capture
# timestamps and the inter-leg latency window, on every verdict including
# NOT_MIDDLE and SETTLEMENT_UNSUPPORTED (not just the headline positive).
# ---------------------------------------------------------------------------
def test_capture_timestamps_and_latency_always_present():
    for key, builder in F.ALL_FIXTURES.items():
        flag = F.run_fixture(builder())
        check(f"fixture[{key}].leg_a_capture_ts_present",
              bool(flag["leg_a"].get("capture_ts")))
        check(f"fixture[{key}].leg_b_capture_ts_present",
              bool(flag["leg_b"].get("capture_ts")))
        check(f"fixture[{key}].inter_leg_latency_s_present",
              isinstance(flag.get("inter_leg_latency_s"), (int, float)))
        check(f"fixture[{key}].inter_leg_latency_nonnegative",
              flag["inter_leg_latency_s"] >= 0)


AMENDMENT4_FIELDS = {"t_lower", "t_upper", "poll_interval_quote_a",
                     "poll_interval_quote_b", "vendor_latency_bound",
                     "clock_skew_bound", "censor_type", "tier"}


def test_simultaneity_recorded_but_not_gating():
    # Same lines/prices, but legs captured 60 minutes apart -- would fail
    # simultaneity outright (arb_scanner-style), but a middle's verdict must
    # NOT depend on it: still MIDDLE_CANDIDATE.
    fx = F.fx_clean_half_point_middle()
    far_leg_b = dict(fx["leg_b"])
    far_leg_b["t_seen"] = fx["leg_a"]["t_seen"] + 60 * F.MIN
    far_leg_b["t_prev"] = fx["leg_a"]["t_seen"] + 55 * F.MIN
    flag = M.build_middle_flag(
        game_id=fx["game_id"], market_kind=fx["market_kind"],
        leg_a_quote=fx["leg_a"], leg_b_quote=far_leg_b,
        t_lo=fx["t_lo"], t_hi=fx["t_hi"], dnp_risk=False,
        clock_skew=F.MEASURED_SKEW, vendor_latency_bounds=F.VENDOR_BOUNDS)
    check("verdict_unaffected_by_non_simultaneity",
          flag["verdict"] == "MIDDLE_CANDIDATE", f"got {flag['verdict']}")
    check("simultaneity_verdict_is_not_simultaneous",
          flag["simultaneity"]["verdict"] == "NOT_SIMULTANEOUS",
          f"got {flag['simultaneity']['verdict']}")
    missing = AMENDMENT4_FIELDS - set(flag["simultaneity"].keys())
    check("amendment4_fields_present_even_though_not_gating", not missing,
          f"missing: {missing}")
    check("inter_leg_latency_matches_the_60min_gap",
          abs(flag["inter_leg_latency_s"] - 60 * F.MIN) < 1e-6,
          f"got {flag['inter_leg_latency_s']}")


# ---------------------------------------------------------------------------
# T: unknown venue fails closed -- push/void rule AND fee row, independently.
# ---------------------------------------------------------------------------
def test_unknown_venue_fails_closed():
    ok1 = False
    try:
        M.require_push_void_rule("book_unregistered")
    except M.RuleError:
        ok1 = True
    check("unknown_push_void_rule_raises", ok1)

    ok2 = False
    try:
        M.require_fee("book_unregistered")
    except M.RuleError:
        ok2 = True
    check("unknown_fee_raises", ok2)

    ok3 = False
    try:
        M.settle_multiplier("book_unregistered", "PUSH", 1.0)
    except M.RuleError:
        ok3 = True
    check("unknown_venue_settle_multiplier_raises", ok3)


# ---------------------------------------------------------------------------
# T: the central distinctness claim, checked by COMPUTATION, not vocabulary.
# Feed this module's own middle worlds, at ordinary (-110-class) vig prices,
# through M09's OWN arb solver (find_arb_stake_ratio). At ordinary vig this
# must NOT find a stake ratio making every world strictly positive -- the
# mathematical content behind "middles are probabilistic, not locked,
# therefore not arbitrage" (M00 section 1.2). This does not claim the
# implication runs the other way for all possible prices; see the module
# docstring for the explicit, honest boundary statement.
# ---------------------------------------------------------------------------
def test_middle_worlds_not_locked_positive_at_ordinary_vig():
    checked_any = False
    for key, builder in F.ALL_FIXTURES.items():
        fx = builder()
        flag = F.run_fixture(fx)
        if flag["verdict"] != "MIDDLE_CANDIDATE":
            continue
        checked_any = True
        coefs = [(wd["mult_a"], wd["mult_b"])
                 for wd in flag["settlement"]["world_detail"]]
        t, killer_idx = ARB.find_arb_stake_ratio(coefs)
        check(f"middle_not_locked_positive[{key}]",
              t is None and killer_idx is not None,
              f"middle fixture {key} unexpectedly solved as locked-positive "
              f"under M09's own arb solver (t={t}); at -110-class vig this "
              f"should never happen -- see module docstring point 1")
    check("at_least_one_middle_candidate_was_cross_checked", checked_any)


def test_no_middle_world_builder_reused_by_arb_scanner():
    # The inverse of arb_scanner.py's own T16 check: confirm arb_scanner.py's
    # source was NOT modified to define middle-shaped worlds (this node's
    # write scope forbids touching M09 at all; this is a belt-and-suspenders
    # regression guard, not a claim about this file).
    src = inspect.getsource(ARB)
    check("arb_scanner_still_has_no_middle_world_builder",
          "worlds_middle" not in src and "enumerate_gap_worlds" not in src)


def main():
    run_fixture_tests()
    test_ev_unsupported_without_probabilities()
    test_ev_computed_with_probabilities()
    test_expected_value_rejects_malformed_probabilities()
    test_no_order_shape()
    test_verdict_enum_closed_and_never_order()
    test_append_only_log()
    test_reserved_term_discipline()
    test_capture_timestamps_and_latency_always_present()
    test_simultaneity_recorded_but_not_gating()
    test_unknown_venue_fails_closed()
    test_middle_worlds_not_locked_positive_at_ordinary_vig()
    test_no_middle_world_builder_reused_by_arb_scanner()

    n_pass = sum(1 for _, ok, _ in RESULTS if ok)
    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"FAIL {name}: {detail}")
    import json
    summary = {"suite": "M10_MIDDLES/TESTS.py",
               "n_pass": n_pass, "n_fail": n_fail, "n_total": len(RESULTS)}
    print(json.dumps(summary))
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
