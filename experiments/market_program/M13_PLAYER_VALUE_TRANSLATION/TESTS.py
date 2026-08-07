#!/usr/bin/env python3
"""TESTS.py -- M13_PLAYER_VALUE_TRANSLATION validation.

Two layers:
  (1) KNOWN-ANSWER fixtures for the distribution machinery build_translation.py
      implements from scratch (no scipy in this environment): the erf-based
      normal CDF, the Numerical-Recipes regularized-incomplete-beta Student-t
      CDF, the empirical CDF, Brier/log-loss, and the moment-statistics
      diagnostics -- checked against textbook closed-form / hand-computable
      values.
  (2) ARTIFACT consistency checks against the already-written FINDINGS.json
      and translation_rows.parquet (produced by `python build_translation.py`,
      which must be run first -- same two-step convention as every other
      market-lane node, e.g. SCORE_BASELINES/TESTS.py + build_score_baselines.py).

No git, no network, no SEALED_RESULTS. Exits nonzero on any failure.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_translation as bt  # noqa: E402

FAILURES = []


def check(name: str, cond: bool, detail: str = ""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# (1) known-answer fixtures -- distribution machinery
# ---------------------------------------------------------------------------

def test_normal_cdf():
    check("normal_cdf(0) == 0.5", math.isclose(bt.normal_cdf(0.0), 0.5, abs_tol=1e-12))
    # standard normal 97.5th percentile is z=1.959963985...
    check("normal_cdf(1.959964) ~= 0.975",
          math.isclose(float(bt.normal_cdf(1.959964)), 0.975, abs_tol=1e-5))
    check("normal_cdf symmetric: cdf(-x) == 1-cdf(x)",
          math.isclose(float(bt.normal_cdf(-1.3)), 1.0 - float(bt.normal_cdf(1.3)), abs_tol=1e-12))
    check("normal_cdf respects loc/scale shift",
          math.isclose(float(bt.normal_cdf(5.0, loc=5.0, scale=2.0)), 0.5, abs_tol=1e-12))


def test_betainc():
    # I_x(1,1) is the CDF of Uniform(0,1): I_x(1,1) = x
    for x in (0.1, 0.37, 0.5, 0.9):
        got = bt._betainc_scalar(1.0, 1.0, x)
        check(f"betainc(1,1,{x}) == {x}", math.isclose(got, x, abs_tol=1e-9))
    check("betainc(a,b,0) == 0", bt._betainc_scalar(2.0, 3.0, 0.0) == 0.0)
    check("betainc(a,b,1) == 1", bt._betainc_scalar(2.0, 3.0, 1.0) == 1.0)
    # symmetry identity: I_x(a,b) = 1 - I_{1-x}(b,a)
    a, b, x = 2.3, 4.7, 0.31
    lhs = bt._betainc_scalar(a, b, x)
    rhs = 1.0 - bt._betainc_scalar(b, a, 1.0 - x)
    check("betainc symmetry identity I_x(a,b) = 1 - I_(1-x)(b,a)", math.isclose(lhs, rhs, abs_tol=1e-9))


def test_student_t_cdf():
    # one-tailed 5% critical values (textbook Student-t table)
    known = {1: 6.314, 5: 2.015, 10: 1.812, 30: 1.697}
    for df, crit in known.items():
        got = float(bt.student_t_cdf(np.array([crit]), df=df)[0])
        check(f"student_t_cdf(t_crit={crit}, df={df}) ~= 0.95",
              math.isclose(got, 0.95, abs_tol=2e-3), f"got {got}")
    check("student_t_cdf(0, df) == 0.5 for any df",
          math.isclose(float(bt.student_t_cdf(np.array([0.0]), df=7)[0]), 0.5, abs_tol=1e-9))
    # large df converges to the normal CDF
    z = 1.5
    t_big = float(bt.student_t_cdf(np.array([z]), df=100000)[0])
    nrm = float(bt.normal_cdf(z))
    check("student_t_cdf(df->large) converges to normal_cdf",
          math.isclose(t_big, nrm, abs_tol=1e-3), f"t={t_big} normal={nrm}")


def test_empirical_cdf():
    ref = np.sort(np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
    check("empirical_cdf below min == 0", float(bt.empirical_cdf(np.array([0.5]), ref)[0]) == 0.0)
    check("empirical_cdf above max == 1", float(bt.empirical_cdf(np.array([5.5]), ref)[0]) == 1.0)
    check("empirical_cdf at median == 0.6 (right-continuous ECDF)",
          float(bt.empirical_cdf(np.array([3.0]), ref)[0]) == 0.6)


def test_brier_log_loss():
    y = np.array([1.0, 0.0, 1.0, 0.0])
    p_perfect = np.array([1.0, 0.0, 1.0, 0.0])
    p_const_half = np.array([0.5, 0.5, 0.5, 0.5])
    check("brier_score: perfect predictions == 0", bt.brier_score(p_perfect, y) == 0.0)
    check("brier_score: constant 0.5 predictions == 0.25",
          math.isclose(bt.brier_score(p_const_half, y), 0.25, abs_tol=1e-12))
    check("log_loss: constant 0.5 predictions == log(2)",
          math.isclose(bt.log_loss(p_const_half, y), math.log(2.0), abs_tol=1e-9))
    check("log_loss: near-perfect predictions ~= 0",
          bt.log_loss(np.array([0.999999, 0.000001]), np.array([1.0, 0.0])) < 1e-4)


def test_moment_stats():
    rng = np.random.default_rng(20260806)
    x = rng.normal(loc=3.0, scale=2.0, size=200000)
    d = bt.moment_stats(x)
    check("moment_stats recovers mean of a normal sample",
          math.isclose(d["mean"], 3.0, abs_tol=0.02), f"got {d['mean']}")
    check("moment_stats recovers std of a normal sample",
          math.isclose(d["std_ddof1"], 2.0, abs_tol=0.02), f"got {d['std_ddof1']}")
    check("moment_stats: normal sample has ~0 skewness",
          abs(d["skewness_fisher_pearson"]) < 0.03, f"got {d['skewness_fisher_pearson']}")
    check("moment_stats: normal sample has ~0 excess kurtosis",
          abs(d["excess_kurtosis"]) < 0.05, f"got {d['excess_kurtosis']}")


def test_reliability_table_bins_sum_to_n():
    rng = np.random.default_rng(1)
    n = 500
    p = rng.uniform(0, 1, n)
    y = (rng.uniform(0, 1, n) < p).astype(float)
    rows = bt.reliability_table(p, y, n_bins=10)
    check("reliability_table bins partition all n rows",
          sum(r["n"] for r in rows) == n, f"got {sum(r['n'] for r in rows)} vs n={n}")
    check("reliability_table has n_bins rows", len(rows) == 10)


def test_aic_formula():
    check("aic(ll=-100, k=2) == 204", bt.aic(-100.0, 2) == 204.0)


# ---------------------------------------------------------------------------
# (2) artifact consistency -- requires `python build_translation.py` to have
# already run (same two-step convention as every other market-lane node)
# ---------------------------------------------------------------------------

def test_findings_artifact():
    fpath = HERE / "FINDINGS.json"
    if not fpath.exists():
        check("FINDINGS.json exists (run build_translation.py first)", False)
        return
    f = json.loads(fpath.read_text(encoding="utf-8"))

    check("epistemic_status line present verbatim",
          f.get("epistemic_status", "").startswith("INTERFACE COMPONENT under the four-system separation"))
    check("no evidence-ladder label is claimed", f.get("evidence_ladder_labels_held") == [])
    check("m00 caveat hash matches TAXONOMY.json's frozen value",
          f["m00_bounded_use"]["caveat_hash"] == "39b8dbde2fc3407e5563752775c18e61f161946b216cbd0194c8d0c110997e7b")

    # integrity cross-check against MODEL_VS_MARKET.md's reported join
    xcheck = f["inventory"]["model_vs_market_prior_work"]["integrity_cross_check_vs_reproduced_join"]
    check("reconstructed join matches MODEL_VS_MARKET.json (matched/evaluable counts)",
          xcheck.get("matches_model_vs_market_json") is True, detail=json.dumps(xcheck))

    da = f["distributional_assumption"]
    check("AIC(normal) recomputes from reported loglik",
          math.isclose(da["normal_fit"]["aic"], bt.aic(da["normal_fit"]["loglik"], 2), abs_tol=1e-6))
    check("AIC(student_t) recomputes from reported loglik",
          math.isclose(da["student_t_fit"]["aic"], bt.aic(da["student_t_fit"]["loglik"], 3), abs_tol=1e-6))
    check("primary_family_selected matches the lower-AIC family",
          da["model_selection"]["primary_family_selected"] ==
          ("student_t" if da["student_t_fit"]["aic"] < da["normal_fit"]["aic"] else "normal"))
    check("fit_pool n is positive and plausible (thousands of rows)",
          da["fit_pool"]["n"] > 1000)

    calib = f["calibration"]
    head = calib["cells"]["A_primary"]
    check("A_primary reliability bins sum to n_player_games (market variant)",
          sum(r["n"] for r in head["market"]["reliability"]) == head["n_player_games"])
    primary = da["model_selection"]["primary_family_selected"]
    check("A_primary reliability bins sum to n_player_games (primary variant)",
          sum(r["n"] for r in head[primary]["reliability"]) == head["n_player_games"])
    check("headline_verdict is one of the three enumerated labels",
          calib["headline_verdict"] in ("TRANSLATION_BETTER_CALIBRATED_THAN_MARKET",
                                        "TRANSLATION_WORSE_CALIBRATED_THAN_MARKET",
                                        "INDISTINGUISHABLE_FROM_MARKET_AT_THIS_N"))
    # verdict must actually agree with the reported CI sign
    ci = head["primary_vs_market_brier_diff_ci95"]
    if ci["hi"] < 0:
        expect = "TRANSLATION_BETTER_CALIBRATED_THAN_MARKET"
    elif ci["lo"] > 0:
        expect = "TRANSLATION_WORSE_CALIBRATED_THAN_MARKET"
    else:
        expect = "INDISTINGUISHABLE_FROM_MARKET_AT_THIS_N"
    check("headline_verdict agrees with the primary-vs-market Brier CI sign",
          calib["headline_verdict"] == expect, f"ci={ci} verdict={calib['headline_verdict']}")

    check("could_not_establish is non-empty (nulls preserved, not hidden)",
          len(f.get("could_not_establish", [])) > 0)


def test_translation_rows_parquet():
    fpath = HERE / "FINDINGS.json"
    ppath = HERE / "translation_rows.parquet"
    if not (fpath.exists() and ppath.exists()):
        check("translation_rows.parquet exists (run build_translation.py first)", False)
        return
    f = json.loads(fpath.read_text(encoding="utf-8"))
    expected_hash = f["translation_function"]["per_row_output"]["sha256"]
    h = hashlib.sha256()
    with open(ppath, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    got_hash = h.hexdigest()
    check("translation_rows.parquet sha256 matches FINDINGS.json's recorded hash",
          got_hash == expected_hash)

    df = pd.read_parquet(ppath)
    n_expected = f["translation_function"]["per_row_output"]["n_rows"]
    check("translation_rows.parquet row count matches FINDINGS.json", len(df) == n_expected)
    required_cols = {"row_uid", "game_id", "player_id", "season", "evaluation_tier", "pred_point",
                      "consensus_line", "pts", "y_over", "p_over_normal", "p_over_student_t",
                      "p_over_empirical", "p_over_het_normal", "p_over_market_devig",
                      "model_version", "forecast_cutoff", "translation_schema_version"}
    check("translation_rows.parquet carries every required per-row field",
          required_cols.issubset(set(df.columns)), f"missing: {required_cols - set(df.columns)}")
    check("every row's p_over_* variants are valid probabilities in [0,1]",
          bool(((df[["p_over_normal", "p_over_student_t", "p_over_empirical", "p_over_het_normal"]]
                 .to_numpy() >= 0.0).all())
               and (df[["p_over_normal", "p_over_student_t", "p_over_empirical", "p_over_het_normal"]]
                    .to_numpy() <= 1.0).all()))
    check("y_over is a binary 0/1 indicator", set(df["y_over"].unique()) <= {0.0, 1.0})
    check("model_version is recorded on every row (non-null)", df["model_version"].notna().all())
    check("forecast_cutoff is recorded on every row (non-null)", df["forecast_cutoff"].notna().all())


def main():
    test_normal_cdf()
    test_betainc()
    test_student_t_cdf()
    test_empirical_cdf()
    test_brier_log_loss()
    test_moment_stats()
    test_reliability_table_bins_sum_to_n()
    test_aic_formula()
    test_findings_artifact()
    test_translation_rows_parquet()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        sys.exit(1)
    print("all checks passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
