"""M11_CONSENSUS_MODEL -- validation suite.

Run:  python experiments/market_program/M11_CONSENSUS_MODEL/TESTS.py

Synthetic-fixture tests (unit + identity + schema) validate the machinery
against arithmetic checkable by hand. The final test runs the coarse-tape
demo read-only against the live main worktree and SKIPs cleanly when that
worktree is absent, so the suite is location-independent.

No performance peeking: no test compares this module's output to any
comparative historical performance of any challenger, and no test reads
anything under experiments/player_program/stage2b/SEALED_RESULTS/.

Exit code 0 iff every non-skipped test passes.
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import consensus as C
import fixtures as F

RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append((name, "PASS", ""))
    except AssertionError as e:
        RESULTS.append((name, "FAIL", str(e)))
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, "FAIL", f"{type(e).__name__}: {e}"))


def skip(name, why):
    RESULTS.append((name, "SKIP", why))


AM4_FIELDS = ["t_lower", "t_upper", "poll_interval_event",
              "poll_interval_quote", "vendor_latency_bound",
              "clock_skew_bound", "censor_type", "tier",
              "n_trusted", "n_excluded", "exclusion_reasons"]


def assert_am4(obj, where):
    for f in AM4_FIELDS:
        assert f in obj, f"{where}: amendment-4 field {f!r} missing"
    assert obj["is_reaction_time_claim"] is False, \
        f"{where}: consensus objects must not claim to be reaction-time"
    assert obj["evidence_ladder_labels_held"] == [], \
        f"{where}: machinery output must never self-assign a ladder label"
    assert obj["not_a_fundamental_prediction"] is True
    assert obj["epistemic_status"] == C.EPISTEMIC_STATUS_LINE


# ---------------------------------------------------------------------------
# T01 no-vig arithmetic, all three registered methods, hand-checkable
# ---------------------------------------------------------------------------
def t01():
    probs, s = C.no_vig_multiplicative([-110, -110])
    raw = 110 / 210
    assert abs(probs[0] - 0.5) < 1e-9, probs
    assert abs(s - 2 * raw) < 1e-9, s

    probs_p, k = C.no_vig_power([-110, -110])
    assert abs(probs_p[0] - 0.5) < 1e-6, probs_p
    assert abs(sum(probs_p) - 1.0) < 1e-6

    probs_s, z = C.no_vig_shin([-110, -110])
    assert abs(probs_s[0] - 0.5) < 1e-6, probs_s
    assert abs(sum(probs_s) - 1.0) < 1e-6

    # asymmetric book: methods must all still sum to 1 and preserve order
    for fn in (C.no_vig_multiplicative, C.no_vig_power, C.no_vig_shin):
        p, _ = fn([-150, 130])
        assert abs(sum(p) - 1.0) < 1e-6, (fn.__name__, p)
        assert p[0] > p[1], (fn.__name__, p)   # favorite still favored


# ---------------------------------------------------------------------------
# T02 preregistration is frozen and hashed; registry rejects unknown methods
# ---------------------------------------------------------------------------
def t02():
    assert C.PREREGISTERED_VIG_METHOD == C.VIG_METHOD_MULTIPLICATIVE
    reg = dict(C.PREREGISTRATION)
    assert C.sha256_hex(C.canonical_json(reg)) == C.PREREGISTRATION_HASH
    assert reg["frozen_before_evaluation"] is True
    assert C.VIG_METHOD_POWER in reg["alternates_in_registry_not_used"]
    assert C.VIG_METHOD_SHIN in reg["alternates_in_registry_not_used"]
    try:
        C.no_vig([-110, -110], method="made_up_method")
        raise AssertionError("unregistered method accepted")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# T03 symmetric two-book consensus: exact 0.5, zero uncertainty/disagreement
# ---------------------------------------------------------------------------
def t03():
    fx = F.fx_two_books_symmetric()
    cons = C.consensus_fair_value(fx["quotes"])
    assert_am4(cons, "T03")
    assert abs(cons["consensus_fair_prob"] - fx["truth"]["consensus"]) < 1e-9
    assert cons["uncertainty_std"] < 1e-12, cons["uncertainty_std"]
    assert cons["disagreement_score"] < 1e-12, cons["disagreement_score"]
    assert cons["n_books_admitted"] == 2
    assert cons["vig_method"] == C.PREREGISTERED_VIG_METHOD
    assert cons["vig_method_preregistration_hash"] == C.PREREGISTRATION_HASH
    assert len(cons["capture_timestamps_all_contributing_quotes"]) == 2
    assert cons["tier"] == "T0"
    assert cons["channel"] == "WITNESSED"


# ---------------------------------------------------------------------------
# T04 disagreeing books: uncertainty/disagreement > 0, residuals sum-to-zero
# under uniform weights
# ---------------------------------------------------------------------------
def t04():
    fx = F.fx_two_books_disagree()
    cons = C.consensus_fair_value(fx["quotes"])
    assert cons["uncertainty_std"] > 0, cons["uncertainty_std"]
    assert cons["disagreement_score"] > 0, cons["disagreement_score"]
    resid = cons["book_residuals"]
    assert set(resid) == {"bookx", "booky"}
    # uniform weights -> residuals average to (near) zero
    total = sum(r["signed"] for r in resid.values())
    assert abs(total) < 1e-9, total
    for r in resid.values():
        assert abs(r["signed"]) - r["abs"] < 1e-12


# ---------------------------------------------------------------------------
# T05 weighted consensus responds to non-uniform weights
# ---------------------------------------------------------------------------
def t05():
    fx = F.fx_three_books_weighted()
    uniform = C.consensus_fair_value(fx["quotes"])
    skewed = C.consensus_fair_value(
        fx["quotes"], weights={"bookx": 10.0, "booky": 1.0, "bookz": 1.0},
        weights_status="TEST_OVERRIDE_NOT_PREREGISTERED")
    assert uniform["consensus_fair_prob"] != skewed["consensus_fair_prob"]
    bx = next(b for b in skewed["contributing_quotes"]
              if b["bookmaker"] == "bookx")
    assert abs(skewed["consensus_fair_prob"] - bx["no_vig_prob"]) < \
        abs(uniform["consensus_fair_prob"] - bx["no_vig_prob"]), \
        "heavier weight on bookx should pull consensus toward it"
    # missing weight entries refused, never silently defaulted
    try:
        C.consensus_fair_value(fx["quotes"], weights={"bookx": 1.0})
        raise AssertionError("partial weight map accepted")
    except C.ConsensusError:
        pass


# ---------------------------------------------------------------------------
# T06 T2-only input: TIER_INSUFFICIENT, excluded from n_trusted, channel
# VENDOR_ASSERTED, capture timestamp still carried (never dropped)
# ---------------------------------------------------------------------------
def t06():
    fx = F.fx_t2_only()
    cons = C.consensus_fair_value(fx["quotes"])
    assert cons["tier"] == "T2"
    assert cons["channel"] == "VENDOR_ASSERTED"
    assert cons["n_trusted"] == 0
    assert cons["n_excluded"] == 1
    assert cons["exclusion_reasons"].get(C.REASON_TIER_INSUFFICIENT) == 1
    assert cons["consensus_fair_prob"] is None
    assert len(cons["capture_timestamps_all_contributing_quotes"]) == 1
    assert cons["tier_admissible"] is False


# ---------------------------------------------------------------------------
# T07 mixed tier: T2 row excluded from the fitted consensus, T0 row alone
# determines it, both capture timestamps still listed
# ---------------------------------------------------------------------------
def t07():
    fx = F.fx_mixed_tier()
    cons = C.consensus_fair_value(fx["quotes"])
    assert cons["n_trusted"] == 1
    assert cons["n_excluded"] == 1
    assert cons["tier"] == "T2"          # weakest-tier inheritance
    assert cons["channel"] == "VENDOR_ASSERTED"
    assert len(cons["capture_timestamps_all_contributing_quotes"]) == 2
    assert len(cons["contributing_quotes"]) == 1
    assert cons["contributing_quotes"][0]["bookmaker"] == "bookx"


# ---------------------------------------------------------------------------
# T08 mismatched outcome refused, never silently blended
# ---------------------------------------------------------------------------
def t08():
    fx = F.fx_mismatched_outcome()
    try:
        C.consensus_fair_value(fx["quotes"])
        raise AssertionError("mixed-outcome quotes accepted")
    except C.ConsensusError:
        pass


# ---------------------------------------------------------------------------
# T09 determinism: same inputs -> same result_hash; contributing-quote order
# does not change the hash of the derived fields
# ---------------------------------------------------------------------------
def t09():
    fx = F.fx_three_books_weighted()
    c1 = C.consensus_fair_value(fx["quotes"], game_id="G1")
    c2 = C.consensus_fair_value(fx["quotes"], game_id="G1")
    assert c1["result_hash"] == c2["result_hash"]
    c3 = C.consensus_fair_value(list(reversed(fx["quotes"])), game_id="G1")
    assert c3["consensus_fair_prob"] == c1["consensus_fair_prob"]


# ---------------------------------------------------------------------------
# T10 book_vs_consensus_residual is the F5-input definition, not a claim
# ---------------------------------------------------------------------------
def t10():
    r = C.book_vs_consensus_residual(0.6, 0.5)
    assert abs(r["signed"] - 0.1) < 1e-12
    assert abs(r["abs"] - 0.1) < 1e-12
    r2 = C.book_vs_consensus_residual(0.4, 0.5)
    assert abs(r2["signed"] + 0.1) < 1e-12
    assert abs(r2["abs"] - 0.1) < 1e-12


# ---------------------------------------------------------------------------
# T11 book-reliability weighting hook: strict train/eval separation enforced
# ---------------------------------------------------------------------------
def t11():
    fx = F.fx_weight_training_obs(fit_end_offset=100 * 60,
                                   eval_start_offset=200 * 60)
    weights, prov = C.fit_book_weights(
        fx["observations"], fit_window_end_ts=fx["fit_window_end_ts"],
        evaluation_window_start_ts=fx["evaluation_window_start_ts"])
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert set(weights) == {"bookx", "booky"}
    assert prov["strictly_before_evaluation_window_enforced"] is True
    assert prov["method"] == "INVERSE_VARIANCE_OF_BOOK_VS_CONSENSUS_RESIDUAL"

    # violation: fit window ends AFTER the evaluation window starts
    try:
        C.fit_book_weights(fx["observations"],
                           fit_window_end_ts=fx["evaluation_window_start_ts"] + 1,
                           evaluation_window_start_ts=fx["evaluation_window_start_ts"])
        raise AssertionError("fit window overlapping eval window accepted")
    except C.WeightFittingViolation:
        pass

    # violation: an observation sits at/after the fit window end (leak)
    leaky_obs = fx["observations"] + [
        {"bookmaker": "bookx", "capture_ts": fx["fit_window_end_ts"],
         "residual": 0.0}]
    try:
        C.fit_book_weights(leaky_obs, fit_window_end_ts=fx["fit_window_end_ts"],
                           evaluation_window_start_ts=fx["evaluation_window_start_ts"])
        raise AssertionError("observation at fit_window_end_ts accepted")
    except C.WeightFittingViolation:
        pass


# ---------------------------------------------------------------------------
# T12 fit_book_weights falls back to uniform for insufficient-data books,
# never to a zero/undefined weight
# ---------------------------------------------------------------------------
def t12():
    obs = [{"bookmaker": "bookx", "capture_ts": F.T0 + i, "residual": 0.01}
           for i in range(8)]
    obs.append({"bookmaker": "booky", "capture_ts": F.T0, "residual": 0.02})
    weights, prov = C.fit_book_weights(
        obs, fit_window_end_ts=F.T0 + 1000,
        evaluation_window_start_ts=F.T0 + 2000, min_obs_per_book=5)
    assert "booky" in prov["books_uniform_fallback_insufficient_data"]
    assert weights["booky"] > 0
    assert abs(sum(weights.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# T13 no-vig registry values match the frozen TAXONOMY.json contract hashes
# quoted by this suite (defends against silent drift of cited constants)
# ---------------------------------------------------------------------------
def t13():
    assert C.CONTRACT_SHA256 == \
        "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"
    assert C.TAXONOMY_SHA256 == \
        "c83e25e783a4ee8642a26dd416362e46c2c34196ff8f8354977c28b72940a12c"


# ---------------------------------------------------------------------------
# T14 fixture M00-U5 caveat hash matches TAXONOMY.json exactly
# ---------------------------------------------------------------------------
def t14():
    measured = C.sha256_hex(F.M00_U5_CAVEAT_TEXT)
    assert measured == F.M00_U5_CAVEAT_SHA256, (measured, F.M00_U5_CAVEAT_SHA256)


# ---------------------------------------------------------------------------
# T15 coarse-tape demo: M00-U2 caveat hash matches, output honestly labelled,
# never crosses into a prohibited use. SKIPs cleanly if the live worktree
# (or its data files) are absent.
# ---------------------------------------------------------------------------
LIVE_ROOT = "C:/Users/jgallagher/wnba-betting-model"


def t15():
    import coarse_tape_demo as D
    out = D.run_demo(max_games=20, write_json=False)
    if out.get("status") == "SKIPPED_LIVE_WORKTREE_ABSENT":
        raise AssertionError("unexpected skip inside a non-skip test path")
    assert out["m00_use_class"] == "M00-U2"
    assert out["m00_caveat_hash_match"] is True, out["m00_caveat_sha256_measured"]
    assert out["m00_caveat_sha256_measured"] == D.M00_U2_CAVEAT_SHA256
    assert out["vig_method"] == C.PREREGISTERED_VIG_METHOD
    assert out["evidence_ladder_labels_held"] == []
    assert out["not_a_fundamental_prediction"] is True
    for g in out["per_game"]:
        co = g["consensus_object"]
        assert co["channel"] == "VENDOR_ASSERTED", \
            "T2 archive rows must never be presented as WITNESSED"
        assert co["tier"] == "T2"
        assert co["is_reaction_time_claim"] is False
    # sampling cap respected
    assert out["sampling"]["max_games_cap"] == 20
    assert out["sampling"]["n_games_sampled_from_odds_file"] <= 20


def main():
    tests = [
        ("T01_no_vig_arithmetic_all_methods", t01),
        ("T02_preregistration_frozen_and_hashed", t02),
        ("T03_symmetric_consensus_exact", t03),
        ("T04_disagreement_and_residuals", t04),
        ("T05_weighted_consensus_and_missing_weight_refused", t05),
        ("T06_t2_only_tier_insufficient_vendor_asserted", t06),
        ("T07_mixed_tier_weakest_tier_inheritance", t07),
        ("T08_mismatched_outcome_refused", t08),
        ("T09_determinism_and_order_invariance", t09),
        ("T10_book_vs_consensus_residual_definition", t10),
        ("T11_weight_fit_train_eval_separation_enforced", t11),
        ("T12_weight_fit_insufficient_data_fallback", t12),
        ("T13_cited_contract_hashes_match", t13),
        ("T14_fixture_m00u5_caveat_hash_matches", t14),
    ]
    for name, fn in tests:
        check(name, fn)

    if os.path.isdir(os.path.join(LIVE_ROOT, "data", "drive_masters")) and \
       os.path.isdir(os.path.join(LIVE_ROOT, "data", "masters")):
        check("T15_coarse_tape_demo_m00u2_labelled_correctly", t15)
    else:
        skip("T15_coarse_tape_demo_m00u2_labelled_correctly",
             "live worktree or its data files not present")

    n_fail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    for name, status, msg in RESULTS:
        line = f"{status:4s}  {name}"
        if msg:
            line += f"  -- {msg}"
        print(line)
    summary = {
        "suite": "M11_CONSENSUS_MODEL/TESTS.py",
        "n_pass": sum(1 for _, s, _ in RESULTS if s == "PASS"),
        "n_fail": n_fail,
        "n_skip": sum(1 for _, s, _ in RESULTS if s == "SKIP"),
    }
    print(json.dumps(summary))
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
