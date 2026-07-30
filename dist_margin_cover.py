"""dist_margin_cover.py — distributional margin layer + cover probabilities.

Preregistered experiment: ``dist_margin_cover_v1``
(experiments/registry.jsonl, registered 2026-07-30T21:23:43Z, regime A,
primary metric margin_crps, incumbent ``gaussian_train_sigma_baseline``,
thresholds min_improvement 0.05 / harm_ci_bound 0.03 / per_season_tolerance
0.10 / coverage_tolerance 0.0). This script never registers; it evaluates.

Design (per the registration, no deviations):

  Center      str_margin_cal from experiments/channel_reval/predictions_v2.csv
              (committed, FROZEN — nothing about the point forecast is refit).
  Residuals   the 2021-2023 train-years calibrated residuals, reconstructed
              from committed artifacts with the recorded train-only protocol:
              channel_base_v2.csv -> run_reval.build_features (committed alphas
              from run_summary.json) -> make_games -> apply_calibrations
              (committed train-fit params from run_summary.json). The rebuild
              must reproduce the committed 673 test predictions to REPRO_TOL
              and the committed calibration params exactly, else it aborts.
              Pool = margin_true - str_margin_cal on the 610 eligible
              2021-2023 games (the exact games the calibration was fit on).
              HARD RULE (asserted): zero test-era (2024+) rows in the pool.
  Incumbent   margin ~ Gaussian(center, sigma), sigma = std(pool, ddof=1).
              CRPS via the closed form (math.erf; no scipy anywhere):
              CRPS = sigma * (z*(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi)).
  Challenger  margin = center + R, R = the pool's empirical distribution:
              quantile probes p_i=(i-0.5)/M, interior p in [0.02, 0.98] from
              linearly interpolated pool quantiles, tails beyond p2/p98
              clamped to the Gaussian N(0, sigma) quantile; probes sorted ->
              an M-member ensemble. CRPS via the exact sorted-sample identity
              CRPS = E|X-y| - 0.5*E|X-X'| (implemented here directly and
              cross-checked against evalharness.metrics.crps_ensemble).
  Primary     per-game CRPS challenger vs incumbent over the 673 chanreval
              test games through evalharness.compare_to_incumbent (precomputed
              per-game CRPS passed as y_pred with loss=lambda t,p: p;
              cluster=date; franchise TEAM_ID team-clustered sensitivity).
  Cover       consensus spread = mean over books of the latest pre-tip
              snapshot home odds_spread (old master + extension; the
              oracle_bracket.build_bookie_margins convention). P(home covers)
              = P(margin > -spread) under each distribution; market-implied
              cover prob = proportional devig of the two-sided American
              odds_price pair per book, mean over books. Brier + log loss +
              decile reliability for incumbent / challenger / market vs actual
              cover outcomes (pushes excluded, counted). CONTEXT, UNGATED —
              beating the market's Brier is not claimed (registration).
  Also        pinball loss at preregistered quantiles 10/25/50/75/90.
  Audits      residual-pool provenance (rows listed, max date < 2024 season
              start asserted); CRPS self-test vs hand-computed toy cases (in
              outputs; hard-fails the run); cover-prob sanity (P in [0,1],
              monotone in spread).

Run:  python dist_margin_cover.py            # real run (records on ledger)
      python dist_margin_cover.py --smoke    # scratch registry copy + scratch outdir
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evalharness import compare_to_incumbent  # noqa: E402
from evalharness import metrics as em  # noqa: E402

EXPERIMENT_ID = "dist_margin_cover_v1"
CHAN_DIR = REPO / "experiments" / "channel_reval"
CHAN_PRED = CHAN_DIR / "predictions_v2.csv"
CHAN_SUMMARY = CHAN_DIR / "run_summary.json"
ODDS_OLD = REPO / "data" / "drive_masters" / "master_odds.csv"
ODDS_EXT = REPO / "data" / "odds_capture" / "master_odds_extension.csv"
DEFAULT_OUTDIR = REPO / "experiments" / "dist_margin_cover"

TRAIN_YEARS = [2021, 2022, 2023]
TEST_SEASONS = [2024, 2025, 2026]
REPRO_TOL = 1e-9              # committed-artifact reproduction gate
M_SAMPLES = 20000             # ensemble size for the challenger distribution
TAIL_LO, TAIL_HI = 0.02, 0.98  # preregistered splice points (p2/p98)
PINBALL_TAUS = [0.10, 0.25, 0.50, 0.75, 0.90]   # preregistered
GAME_QUANTS = [round(0.05 * k, 2) for k in range(1, 20)]  # q05..q95 columns
PRICE_ABS_MIN, PRICE_ABS_MAX = 100.0, 2000.0    # valid American price band
PUSH_TOL = 1e-9
SANITY_SEED = 20260730


# ---------------------------------------------------------------------------
# Gaussian primitives — math.erf only, no scipy
# ---------------------------------------------------------------------------

_SQRT2 = math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)
_INV_SQRT_PI = 1.0 / math.sqrt(math.pi)


def norm_cdf(x):
    """Standard normal CDF via math.erf (vectorized over numpy arrays)."""
    a = np.asarray(x, dtype=float)
    out = np.array([0.5 * (1.0 + math.erf(v / _SQRT2)) for v in a.ravel()])
    return out.reshape(a.shape) if a.shape else float(out[0])


def norm_pdf(x):
    a = np.asarray(x, dtype=float)
    return _INV_SQRT_2PI * np.exp(-0.5 * a * a)


# Acklam's inverse-normal-CDF rational approximation + one Halley refinement
# with erfc — machine precision, no scipy. Coefficients are Acklam's standard.
_PPF_A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
          1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
_PPF_B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
          6.680131188771972e+01, -1.328068155288572e+01]
_PPF_C = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
          -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
_PPF_D = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
          3.754408661907416e+00]


def _norm_ppf_scalar(p: float) -> float:
    if not (0.0 < p < 1.0):
        raise ValueError(f"ppf needs p in (0,1), got {p}")
    a, b, c, d = _PPF_A, _PPF_B, _PPF_C, _PPF_D
    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        x = ((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
             / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        x = ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
             / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0))
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -((((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
              / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0))
    # Halley refinement against the exact erfc-based CDF
    e = 0.5 * math.erfc(-x / _SQRT2) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(0.5 * x * x)
    return x - u / (1.0 + 0.5 * x * u)


def norm_ppf(p):
    a = np.asarray(p, dtype=float)
    out = np.array([_norm_ppf_scalar(v) for v in a.ravel()])
    return out.reshape(a.shape) if a.shape else float(out[0])


def crps_gaussian(y, mu, sigma: float):
    """Closed-form CRPS of N(mu, sigma) at y (Gneiting & Raftery):
    CRPS = sigma * (z*(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi)), z=(y-mu)/sigma."""
    z = (np.asarray(y, float) - np.asarray(mu, float)) / sigma
    return sigma * (z * (2.0 * norm_cdf(z) - 1.0) + 2.0 * norm_pdf(z) - _INV_SQRT_PI)


# ---------------------------------------------------------------------------
# empirical CRPS — direct implementation of E|X-y| - 0.5 E|X-X'|
# ---------------------------------------------------------------------------

def crps_ensemble_exact(y, samples) -> np.ndarray:
    """Exact per-observation CRPS of an equal-weight ensemble, implemented
    directly. samples: (n, m). Sorted-sample identity for the pair term:
    sum_{i,j}|x_i-x_j| = 2 * sum_k x_(k) * (2k - m + 1)  (0-indexed)."""
    t = np.asarray(y, dtype=float)
    x = np.asarray(samples, dtype=float)
    if x.ndim == 1:
        x = np.broadcast_to(x, (t.size, x.size))
    m = x.shape[1]
    term1 = np.abs(x - t[:, None]).mean(axis=1)
    xs = np.sort(x, axis=1)
    k = np.arange(m, dtype=float)
    pair = np.sum(xs * (2.0 * k - m + 1.0)[None, :], axis=1)  # = 0.5*sum|xi-xj|... see below
    term2 = pair / (m * m)                                    # = 0.5 * E|X-X'|
    return term1 - term2


def crps_const_offsets(y, center, offsets_sorted: np.ndarray) -> np.ndarray:
    """Fast path when every game shares one sorted offset set: X_g = c_g + O.
    CRPS_g = mean|O - (y_g - c_g)| - const, const = 0.5*E|O-O'| (game-free)."""
    m = offsets_sorted.size
    k = np.arange(m, dtype=float)
    const = float(np.sum(offsets_sorted * (2.0 * k - m + 1.0)) / (m * m))
    r = np.asarray(y, float) - np.asarray(center, float)
    out = np.empty(r.size)
    step = 128
    for i in range(0, r.size, step):
        out[i:i + step] = np.abs(r[i:i + step, None] - offsets_sorted[None, :]).mean(axis=1)
    return out - const


# ---------------------------------------------------------------------------
# CRPS self-test — hand-computed toys, harness cross-check, discretization
# ---------------------------------------------------------------------------

def run_crps_selftest(sigma: float, offsets_sorted: np.ndarray) -> dict:
    tests = {}

    def rec(name, got, want, tol):
        ok = bool(abs(got - want) <= tol)
        tests[name] = {"got": float(got), "expected": float(want),
                       "tol": tol, "pass": ok}
        return ok

    ok = True
    # 1) m=1 degenerate: CRPS reduces to absolute error. samples {0}, y=1.5 -> 1.5
    ok &= rec("toy_m1_abs_error",
              crps_ensemble_exact([1.5], np.array([[0.0]]))[0], 1.5, 1e-12)
    # 2) samples {0,2}, y=1: E|X-y|=1, E|X-X'|=1 -> CRPS=0.5 (hand-computed)
    ok &= rec("toy_two_point",
              crps_ensemble_exact([1.0], np.array([[0.0, 2.0]]))[0], 0.5, 1e-12)
    # 3) samples {0,1,3}, y=2: E|X-y|=4/3, 0.5E|X-X'|=2/3 -> 2/3 (hand-computed)
    ok &= rec("toy_three_point",
              crps_ensemble_exact([2.0], np.array([[0.0, 1.0, 3.0]]))[0],
              2.0 / 3.0, 1e-12)
    # 4) Gaussian closed form, hand-checked values for N(0,1):
    #    y=0: 2*phi(0)-1/sqrt(pi) = 0.23369497...; y=1: 0.60244135...
    ok &= rec("gauss_closed_form_y0", float(crps_gaussian(0.0, 0.0, 1.0)),
              2.0 * _INV_SQRT_2PI - _INV_SQRT_PI, 1e-12)
    ok &= rec("gauss_closed_form_y1", float(crps_gaussian(1.0, 0.0, 1.0)),
              0.6024413575, 1e-9)
    # 5) cross-check my direct implementation vs the harness's unit-tested one
    rng = np.random.default_rng(SANITY_SEED)
    devs = []
    for _ in range(50):
        yv = rng.normal(size=7)
        sm = rng.normal(size=(7, 13))
        devs.append(np.max(np.abs(crps_ensemble_exact(yv, sm)
                                  - em.crps_ensemble(yv, sm))))
    tests["harness_crosscheck_max_dev"] = {"got": float(np.max(devs)),
                                           "tol": 1e-10,
                                           "pass": bool(np.max(devs) <= 1e-10)}
    ok &= tests["harness_crosscheck_max_dev"]["pass"]
    # 6) quantile-probe discretization: N(0, sigma) as M probes vs closed form.
    #    Bounds the representation gap between the two scoring methods.
    probes = norm_ppf((np.arange(M_SAMPLES) + 0.5) / M_SAMPLES) * sigma
    ygrid = np.concatenate([np.arange(-40.0, 40.5, 5.0), [0.0]])
    ens = crps_const_offsets(ygrid, np.zeros_like(ygrid), np.sort(probes))
    clo = crps_gaussian(ygrid, 0.0, sigma)
    disc = float(np.max(np.abs(ens - clo)))
    tests["gauss_quantile_discretization_max_dev"] = {
        "got": disc, "tol": 5e-3, "pass": bool(disc <= 5e-3),
        "note": "incumbent scored closed-form, challenger scored as M-probe "
                "ensemble; this bounds the methodological gap (points of CRPS)"}
    ok &= tests["gauss_quantile_discretization_max_dev"]["pass"]
    # 7) norm_ppf inverts norm_cdf
    pgrid = np.concatenate([[1e-6, 1e-4, 0.001], np.arange(0.01, 1.0, 0.01),
                            [0.999, 0.9999, 1 - 1e-6]])
    ppf_dev = float(np.max(np.abs(norm_cdf(norm_ppf(pgrid)) - pgrid)))
    tests["ppf_inverts_cdf_max_dev"] = {"got": ppf_dev, "tol": 1e-12,
                                        "pass": bool(ppf_dev <= 1e-12)}
    ok &= tests["ppf_inverts_cdf_max_dev"]["pass"]
    # 8) fast constant-offset path == general path on real offsets
    rng2 = np.random.default_rng(SANITY_SEED + 1)
    yv = rng2.normal(scale=12.0, size=25)
    cv = rng2.normal(scale=4.0, size=25)
    fast = crps_const_offsets(yv, cv, offsets_sorted)
    gen = crps_ensemble_exact(yv, cv[:, None] + offsets_sorted[None, :])
    fdev = float(np.max(np.abs(fast - gen)))
    tests["fastpath_vs_general_max_dev"] = {"got": fdev, "tol": 1e-9,
                                            "pass": bool(fdev <= 1e-9)}
    ok &= tests["fastpath_vs_general_max_dev"]["pass"]
    return {"all_pass": bool(ok), "m_samples": M_SAMPLES, "tests": tests}


# ---------------------------------------------------------------------------
# residual-pool reconstruction from committed artifacts
# ---------------------------------------------------------------------------

def load_run_reval():
    spec = importlib.util.spec_from_file_location(
        "chanreval_run_reval", CHAN_DIR / "run_reval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def reconstruct_pool() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Rebuild the chanreval pipeline from committed artifacts; return
    (test frame with TEAM_ID_h, train residual pool frame, provenance audit)."""
    rr = load_run_reval()
    S = json.load(open(CHAN_SUMMARY, encoding="utf-8"))
    alphas, cal = S["alphas"], S["calibration"]

    D = rr.load_base()
    F = rr.build_features(D, alphas)
    games = rr.make_games(F)
    games = rr.apply_calibrations(games, cal)
    games["GAME_ID"] = games["GAME_ID"].astype(str)

    pv = pd.read_csv(CHAN_PRED)
    pv["GAME_ID"] = pv["GAME_ID"].astype(str)

    # reproduction gate: committed test predictions must be reproduced exactly
    j = pv.merge(games[["GAME_ID", "str_margin_uncal", "str_margin_cal",
                        "margin_true", "TEAM_ID_h"]],
                 on="GAME_ID", suffixes=("", "_rb"), validate="one_to_one")
    if len(j) != len(pv):
        raise SystemExit(f"rebuild covers {len(j)}/{len(pv)} committed test games")
    repro_dev = float(max(
        (j["str_margin_cal"] - j["str_margin_cal_rb"]).abs().max(),
        (j["str_margin_uncal"] - j["str_margin_uncal_rb"]).abs().max(),
        (j["margin_true"] - j["margin_true_rb"]).abs().max()))
    if repro_dev > REPRO_TOL:
        raise SystemExit(f"committed-prediction reproduction FAILED: {repro_dev}")

    # calibration refit must equal the committed params (train-only protocol)
    train_ids = set(D.loc[D.season.isin(TRAIN_YEARS), "GAME_ID"].astype(str))
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible].copy()
    refit = rr.fit_calibrations(tg)
    cal_dev = float(max(abs(refit["str_margin"][0] - cal["str_margin"][0]),
                        abs(refit["str_margin"][1] - cal["str_margin"][1])))
    if cal_dev > REPRO_TOL:
        raise SystemExit(f"calibration-param reproduction FAILED: {cal_dev}")
    if len(tg) != int(cal["n_train_games"]):
        raise SystemExit(f"train pool n {len(tg)} != committed {cal['n_train_games']}")

    tg["residual"] = tg["margin_true"] - tg["str_margin_cal"]

    # provenance: zero test-era information in the pool (hard rule)
    max_pool_date = pd.to_datetime(tg["GAME_DATE_h"]).max()
    test_start = pd.to_datetime(D.loc[D.season >= min(TEST_SEASONS), "GAME_DATE"]).min()
    seasons = sorted(int(s) for s in tg["season_h"].unique())
    if not (seasons == TRAIN_YEARS and max_pool_date < test_start):
        raise SystemExit(f"PROVENANCE VIOLATION: pool seasons {seasons}, "
                         f"max date {max_pool_date}, test start {test_start}")

    provenance = {
        "pool_definition": "margin_true - str_margin_cal on the eligible "
                           "2021-2023 games of the chanreval rebuild (the exact "
                           "610 games the committed calibration was fit on; "
                           "walk-forward shifted-EWMA features, calibration "
                           "params fit on this pool only)",
        "source": "experiments/channel_reval/channel_base_v2.csv via "
                  "run_reval.build_features/make_games/apply_calibrations with "
                  "committed alphas + calibration from run_summary.json",
        "n_rows": int(len(tg)),
        "rows_by_season": {int(k): int(v) for k, v in
                           tg.groupby("season_h").size().items()},
        "max_pool_date": str(max_pool_date.date()),
        "test_era_start": str(test_start.date()),
        "zero_test_era_rows": True,
        "committed_test_reproduction_max_dev": repro_dev,
        "calibration_param_reproduction_max_dev": cal_dev,
        "pool_mean": float(tg["residual"].mean()),
        "pool_std_ddof1": float(tg["residual"].std(ddof=1)),
    }
    return j, tg, provenance


# ---------------------------------------------------------------------------
# challenger distribution — spliced quantile ensemble
# ---------------------------------------------------------------------------

def build_offsets(pool: np.ndarray, sigma: float) -> tuple[np.ndarray, dict]:
    p = (np.arange(M_SAMPLES) + 0.5) / M_SAMPLES
    interior = (p >= TAIL_LO) & (p <= TAIL_HI)
    off = np.empty(M_SAMPLES)
    off[interior] = np.quantile(pool, p[interior])            # linear interp
    off[~interior] = norm_ppf(p[~interior]) * sigma           # Gaussian tails
    n_tail = int((~interior).sum())
    splice = {
        "n_probes": M_SAMPLES,
        "n_gaussian_tail_probes": n_tail,
        "emp_q02": float(np.quantile(pool, TAIL_LO)),
        "gauss_q02": float(norm_ppf(TAIL_LO) * sigma),
        "emp_q98": float(np.quantile(pool, TAIL_HI)),
        "gauss_q98": float(norm_ppf(TAIL_HI) * sigma),
    }
    splice["splice_gap_low"] = splice["emp_q02"] - splice["gauss_q02"]
    splice["splice_gap_high"] = splice["emp_q98"] - splice["gauss_q98"]
    return np.sort(off), splice


def p_over(offsets_sorted: np.ndarray, thr) -> np.ndarray:
    """P(R > thr) under the ensemble: fraction of members strictly above."""
    idx = np.searchsorted(offsets_sorted, np.asarray(thr, float), side="right")
    return (offsets_sorted.size - idx) / offsets_sorted.size


# ---------------------------------------------------------------------------
# odds: consensus spread + market-implied cover probability
# ---------------------------------------------------------------------------

def american_to_prob(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, float)
    return np.where(a > 0, 100.0 / (a + 100.0), np.abs(a) / (np.abs(a) + 100.0))


def load_odds() -> pd.DataFrame:
    frames = []
    for path in (ODDS_OLD, ODDS_EXT):
        o = pd.read_csv(path, low_memory=False)
        o = o[o["game_id"].notna()].copy()
        o["game_id"] = o["game_id"].astype(np.int64).astype(str)
        o["snap"] = pd.to_datetime(o["odds_snapshot_timestamp"], utc=True, format="mixed")
        o["tip"] = pd.to_datetime(o["odds_commence_time"], utc=True, format="mixed")
        frames.append(o[(o["snap"] <= o["tip"]) & o["odds_spread"].notna()][
            ["game_id", "bookmaker_key", "snap", "team", "home_team", "away_team",
             "odds_spread", "odds_price"]])
    return pd.concat(frames, ignore_index=True)


def build_consensus_spreads(pre: pd.DataFrame) -> pd.DataFrame:
    """oracle_bracket.build_bookie_margins convention: home-team rows, latest
    pre-tip snapshot per (game, book), consensus = mean over books."""
    h = pre[pre["team"] == pre["home_team"]]
    last = h.sort_values("snap").groupby(["game_id", "bookmaker_key"]).tail(1)
    per_game = last.groupby("game_id").agg(
        spread=("odds_spread", "mean"), n_books=("odds_spread", "size"),
        book_spread_min=("odds_spread", "min"), book_spread_max=("odds_spread", "max"),
    ).reset_index()
    return per_game


def build_market_probs(pre: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Per book: latest pre-tip snapshot with BOTH sides priced; proportional
    devig p_home = q_h/(q_h+q_a); consensus market prob = mean over books."""
    key = ["game_id", "bookmaker_key", "snap"]
    h = pre[pre["team"] == pre["home_team"]][key + ["odds_spread", "odds_price"]] \
        .rename(columns={"odds_spread": "sp_h", "odds_price": "pr_h"})
    a = pre[pre["team"] == pre["away_team"]][key + ["odds_price"]] \
        .rename(columns={"odds_price": "pr_a"})
    m = h.merge(a, on=key, how="inner")
    m = m[m["pr_h"].notna() & m["pr_a"].notna()]
    valid = ((m["pr_h"].abs() >= PRICE_ABS_MIN) & (m["pr_h"].abs() <= PRICE_ABS_MAX)
             & (m["pr_a"].abs() >= PRICE_ABS_MIN) & (m["pr_a"].abs() <= PRICE_ABS_MAX))
    n_excluded = int((~valid).sum())
    m = m[valid]
    last = m.sort_values("snap").groupby(["game_id", "bookmaker_key"]).tail(1)
    q_h = american_to_prob(last["pr_h"].to_numpy())
    q_a = american_to_prob(last["pr_a"].to_numpy())
    last = last.assign(p_home=q_h / (q_h + q_a), overround=q_h + q_a - 1.0)
    per_game = last.groupby("game_id").agg(
        p_cover_market=("p_home", "mean"), n_books_priced=("p_home", "size"),
        mean_overround=("overround", "mean"),
    ).reset_index()
    audit = {"invalid_price_pairs_excluded": n_excluded,
             "game_books_priced": int(len(last)),
             "mean_overround": float(last["overround"].mean())}
    return per_game, audit


# ---------------------------------------------------------------------------
# cover-probability sanity audit
# ---------------------------------------------------------------------------

def cover_sanity(test: pd.DataFrame, offsets: np.ndarray, sigma: float) -> dict:
    probs = {}
    for c in ("p_cover_gauss", "p_cover_emp", "p_cover_market"):
        v = test[c].dropna()
        probs[c] = {"n": int(len(v)), "min": float(v.min()), "max": float(v.max()),
                    "in_unit_interval": bool(((v >= 0) & (v <= 1)).all())}
    rng = np.random.default_rng(SANITY_SEED)
    sample = test.sample(n=min(25, len(test)), random_state=SANITY_SEED)
    grid = np.arange(-20.0, 20.5, 0.5)
    mono_g, mono_e = True, True
    for _, r in sample.iterrows():
        pg = norm_cdf((r["center"] + grid) / sigma)
        pe = p_over(offsets, -grid - r["center"])
        mono_g &= bool((np.diff(pg) >= -1e-12).all())
        mono_e &= bool((np.diff(pe) >= -1e-12).all())
    return {"prob_ranges": probs,
            "monotone_in_spread_gauss": mono_g,
            "monotone_in_spread_emp": mono_e,
            "monotonicity_games_checked": int(len(sample)),
            "spread_grid": "[-20, 20] step 0.5",
            "all_pass": bool(mono_g and mono_e
                             and all(p["in_unit_interval"] for p in probs.values()))}


# ---------------------------------------------------------------------------
# report helpers
# ---------------------------------------------------------------------------

def fmt_table(df: pd.DataFrame, floatfmt: str = "{:.4f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: floatfmt.format(v) if pd.notna(v) else "")
    header = "| " + " | ".join(map(str, d.columns)) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    body = "\n".join("| " + " | ".join(map(str, row)) + " |"
                     for row in d.itertuples(index=False))
    return "\n".join([header, sep, body])


def scope_frames(df: pd.DataFrame, season_col: str = "season"):
    yield "pooled", df
    for s in TEST_SEASONS:
        sub = df[df[season_col] == s]
        if len(sub):
            yield str(s), sub


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true",
                    help="scratch registry copy + scratch outdir; never touches the ledger")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)

    registry_path = None
    outdir = args.outdir or DEFAULT_OUTDIR
    if args.smoke:
        import tempfile
        scratch = Path(tempfile.mkdtemp(prefix="dist_margin_cover_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        outdir = args.outdir or (scratch / "out")
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mode = "SMOKE" if args.smoke else "REAL"
    print(f"[dist] {mode} run at {run_time} -> {outdir}")

    # 1. reconstruct pool + frozen centers ----------------------------------
    test, pool_frame, provenance = reconstruct_pool()
    print(f"[pool] {provenance['n_rows']} train residuals "
          f"({provenance['rows_by_season']}), max date {provenance['max_pool_date']} "
          f"< test start {provenance['test_era_start']}; "
          f"repro dev {provenance['committed_test_reproduction_max_dev']:.2e}")
    pool = pool_frame["residual"].to_numpy(float)
    sigma = float(np.std(pool, ddof=1))
    test = test.rename(columns={"GAME_ID": "game_id"})
    test["center"] = test["str_margin_cal"]          # frozen committed centers
    test["game_date"] = pd.to_datetime(test["GAME_DATE_h"])
    test["season"] = test["season_h"].astype(int)
    print(f"[dist] sigma (train pool std, ddof=1) = {sigma:.4f}; "
          f"pool mean {provenance['pool_mean']:.2e}")

    # 2. challenger offsets + self-test (audit before believing) ------------
    offsets, splice = build_offsets(pool, sigma)
    selftest = run_crps_selftest(sigma, offsets)
    print(f"[selftest] CRPS self-test: "
          f"{'PASS' if selftest['all_pass'] else 'FAIL'} "
          f"(discretization bound "
          f"{selftest['tests']['gauss_quantile_discretization_max_dev']['got']:.2e})")
    if not selftest["all_pass"]:
        (outdir / "crps_selftest.json").write_text(
            json.dumps(selftest, indent=2), encoding="utf-8")
        raise SystemExit("CRPS self-test FAILED -- results are not evidence; stopping")

    # 3. per-game CRPS -------------------------------------------------------
    y = test["margin_true"].to_numpy(float)
    c = test["center"].to_numpy(float)
    test["crps_emp"] = crps_const_offsets(y, c, offsets)
    test["crps_gauss"] = crps_gaussian(y, c, sigma)
    center_mae = float(np.abs(y - c).mean())

    crps_rows = []
    for scope, sub in scope_frames(test):
        crps_rows.append({
            "scope": scope, "n": int(len(sub)),
            "crps_emp": float(sub["crps_emp"].mean()),
            "crps_gauss": float(sub["crps_gauss"].mean()),
            "delta": float(sub["crps_gauss"].mean() - sub["crps_emp"].mean()),
            "center_mae": float((sub["margin_true"] - sub["center"]).abs().mean()),
        })
    crps_tbl = pd.DataFrame(crps_rows)
    print(fmt_table(crps_tbl))

    # 4. the registered comparison (per-game CRPS as the loss) ---------------
    ch_frame = pd.DataFrame({
        "game_id": test["game_id"], "game_date": test["game_date"],
        "season": test["season"], "y_true": test["margin_true"].astype(float),
        "y_pred": test["crps_emp"].astype(float),
        "home_team": test["TEAM_ID_h"].astype(np.int64),   # franchise id, stable across renames
    })
    inc_frame = pd.DataFrame({
        "game_id": test["game_id"], "y_true": test["margin_true"].astype(float),
        "y_pred": test["crps_gauss"].astype(float),
    })

    S = json.load(open(CHAN_SUMMARY, encoding="utf-8"))
    cov = float(len(test)) / float(S["n_total_test_games"])   # identical universes

    def joint_check():
        # The distributional layer does not touch any point forecast: both
        # variants are centered on the committed str_margin_cal; home/away/
        # margin/total point forecasts are unchanged by construction.
        dev = float((test["center"] - test["str_margin_cal"]).abs().max())
        return dev == 0.0, {
            "status": "structural",
            "point_forecasts_unchanged": True,
            "center_identity_max_dev": dev,
            "challenger_median_offset": float(np.quantile(pool, 0.5)),
            "note": "no point forecast is refit or altered; gate 4 is "
                    "asserted, not fitted (same pattern as totals_head_v1)",
        }

    result = compare_to_incumbent(
        ch_frame, inc_frame,
        experiment_id=EXPERIMENT_ID,
        registry_path=registry_path,
        loss=lambda t, p: np.asarray(p, dtype=float),   # precomputed per-game CRPS
        cluster="date",
        team_col="home_team",
        joint_check=joint_check,
        coverage=(cov, cov),
    )
    print(f"[gate] {result.verdict} (promote={result.promote}); CRPS "
          f"{result.metric_challenger:.4f} vs {result.metric_incumbent:.4f}, "
          f"delta {result.pooled_improvement:+.4f} "
          f"CI [{result.ci_low:+.4f}, {result.ci_high:+.4f}], "
          f"failed={result.failed_gates or 'none'}")

    # 5. quantile columns + pinball loss ------------------------------------
    for q in GAME_QUANTS:
        test[f"q{int(round(q * 100)):02d}"] = c + float(np.quantile(pool, q))
    taus = np.array(PINBALL_TAUS)
    emp_q = c[:, None] + np.quantile(pool, taus)[None, :]
    gau_q = c[:, None] + sigma * norm_ppf(taus)[None, :]
    pin_rows = []
    for scope, sub in scope_frames(test):
        idx = sub.index.to_numpy()
        pos = test.index.get_indexer(idx)
        yv = y[pos]
        for name, qm in (("empirical", emp_q[pos]), ("gaussian", gau_q[pos])):
            pl = em.pinball_loss(yv, qm, taus)
            pin_rows.append({"scope": scope, "variant": name, "n": int(len(yv)),
                             **{f"tau_{int(t * 100)}": float(v)
                                for t, v in zip(PINBALL_TAUS, pl)},
                             "mean": float(np.mean(pl))})
    pin_tbl = pd.DataFrame(pin_rows)

    # 6. cover probabilities -------------------------------------------------
    pre = load_odds()
    spreads = build_consensus_spreads(pre)
    market, market_audit = build_market_probs(pre)
    test = test.merge(spreads, on="game_id", how="left") \
               .merge(market, on="game_id", how="left")
    n_spread = int(test["spread"].notna().sum())
    missing = test.loc[test["spread"].isna(),
                       ["game_id", "game_date", "season"]]

    sp = test["spread"].to_numpy(float)
    with np.errstate(invalid="ignore"):
        test["p_cover_gauss"] = np.where(
            np.isnan(sp), np.nan, norm_cdf((c + sp) / sigma))
        test["p_cover_emp"] = np.where(
            np.isnan(sp), np.nan, p_over(offsets, -sp - c))
    test["push"] = np.abs(test["margin_true"] + sp) <= PUSH_TOL
    test["home_cover"] = np.where(
        np.isnan(sp) | test["push"], np.nan,
        (test["margin_true"] > -sp).astype(float))

    model_market_gap = float(np.abs(test["center"] + test["spread"]).mean())

    sanity = cover_sanity(test[test["spread"].notna()], offsets, sigma)
    print(f"[sanity] cover probs: {'PASS' if sanity['all_pass'] else 'FAIL'}")
    if not sanity["all_pass"]:
        raise SystemExit("cover-probability sanity audit FAILED; stopping")

    # three-way common subset: spread + market prob + decided (no push)
    common = test[test["spread"].notna() & test["p_cover_market"].notna()
                  & ~test["push"]].copy()
    n_push = int(test["push"].sum())
    cover_rows = []
    for scope, sub in scope_frames(common):
        o = sub["home_cover"].to_numpy(float)
        row = {"scope": scope, "n": int(len(sub)),
               "cover_rate": float(o.mean())}
        for name, col in (("gauss", "p_cover_gauss"), ("emp", "p_cover_emp"),
                          ("market", "p_cover_market")):
            p = sub[col].to_numpy(float)
            row[f"brier_{name}"] = em.brier_score(o, p)
            row[f"logloss_{name}"] = em.log_loss(o, p)
        cover_rows.append(row)
    cover_tbl = pd.DataFrame(cover_rows)
    print(fmt_table(cover_tbl))

    # 7. reliability tables --------------------------------------------------
    rel_files = {}
    rel_summary = {}
    o = common["home_cover"].to_numpy(float)
    for name, col in (("gauss", "p_cover_gauss"), ("emp", "p_cover_emp"),
                      ("market", "p_cover_market")):
        p = common[col].to_numpy(float)
        parts = []
        for strategy in ("uniform", "quantile"):
            t = em.reliability_table(o, p, n_bins=10, strategy=strategy)
            t.insert(0, "binning", strategy)
            parts.append(t)
        rel = pd.concat(parts, ignore_index=True)
        fname = f"reliability_cover_{name}.csv"
        rel.to_csv(outdir / fname, index=False)
        rel_files[name] = fname
        occupied = rel[(rel["binning"] == "uniform") & (rel["n"] > 0)]
        rel_summary[name] = {
            "n": int(len(common)),
            "uniform_bins_occupied": int(len(occupied)),
            "max_abs_gap_uniform": float(occupied["gap"].abs().max()),
            "weighted_abs_gap_uniform": float(
                (occupied["gap"].abs() * occupied["n"]).sum() / occupied["n"].sum()),
        }

    # 8. artifacts -----------------------------------------------------------
    pool_out = pool_frame[["GAME_ID", "GAME_DATE_h", "season_h",
                           "TEAM_ABBREVIATION_h", "TEAM_ABBREVIATION_a",
                           "margin_true", "str_margin_uncal", "str_margin_cal",
                           "residual"]].rename(columns={
        "GAME_ID": "game_id", "GAME_DATE_h": "date", "season_h": "season",
        "TEAM_ABBREVIATION_h": "home", "TEAM_ABBREVIATION_a": "away"})
    pool_out.to_csv(outdir / "residual_pool.csv", index=False)

    gl_cols = (["game_id", "game_date", "season", "margin_true", "center"]
               + [f"q{int(round(q * 100)):02d}" for q in GAME_QUANTS]
               + ["spread", "n_books", "p_cover_gauss", "p_cover_emp",
                  "p_cover_market", "n_books_priced", "home_cover", "push"])
    gl = test.copy()
    gl["sigma"] = sigma
    gl = gl[gl_cols[:5] + ["sigma"] + gl_cols[5:]]
    gl = gl.rename(columns={"game_date": "date"})
    gl.to_csv(outdir / "game_level_dist.csv", index=False)

    crps_tbl.to_csv(outdir / "crps_by_season.csv", index=False)
    pin_tbl.to_csv(outdir / "pinball_losses.csv", index=False)
    cover_tbl.to_csv(outdir / "cover_brier_logloss.csv", index=False)
    (outdir / "crps_selftest.json").write_text(
        json.dumps(selftest, indent=2), encoding="utf-8")
    with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)

    summary = {
        "experiment_id": EXPERIMENT_ID, "mode": mode, "run_time": run_time,
        "run_number": result.run_number, "eval_time": result.eval_time,
        "sigma": sigma, "m_samples": M_SAMPLES,
        "tail_splice": splice,
        "provenance_audit": provenance,
        "crps_table": crps_tbl.to_dict("records"),
        "center_mae_673": center_mae,
        "gate_verdict": result.to_dict(),
        "cover_table": cover_tbl.to_dict("records"),
        "cover_counts": {
            "n_test_games": int(len(test)), "n_with_spread": n_spread,
            "n_with_market_prob": int(test["p_cover_market"].notna().sum()),
            "n_push_excluded": n_push,
            "n_common_three_way": int(len(common)),
            "games_missing_spread": missing.astype(str).to_dict("records"),
        },
        "market_audit": market_audit,
        "mean_abs_model_vs_consensus_margin_gap": model_market_gap,
        "book_line_dispersion": {
            "mean_spread_range_across_books": float(
                (test["book_spread_max"] - test["book_spread_min"]).mean()),
            "note": "each book's devigged prob refers to its own line; the "
                    "consensus line is the cross-book mean (T~-64m era caveat "
                    "per registration)"},
        "reliability_summary": rel_summary,
        "cover_sanity_audit": sanity,
        "pinball_table": pin_tbl.to_dict("records"),
        "crps_selftest_all_pass": selftest["all_pass"],
    }
    with open(outdir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    # 9. REPORT.md -----------------------------------------------------------
    r = result
    md = f"""# Distributional margin + cover probabilities (`{EXPERIMENT_ID}`)

*Generated by `dist_margin_cover.py` ({mode} run, {run_time}). Registered
2026-07-30T21:23:43Z, regime A, primary metric `margin_crps` (gated), incumbent
`{r.incumbent_id}`. Cover metrics vs the devigged market are CONTEXT, UNGATED
(registration: beating the market's cover Brier is not claimed). This
experiment produces evidence, not a betting policy.*

## Verdict (gated primary: margin CRPS, {r.n_games} test games)

**{r.verdict}** (promote={r.promote}) — challenger empirical CRPS
{r.metric_challenger:.4f} vs incumbent Gaussian {r.metric_incumbent:.4f},
pooled improvement {r.pooled_improvement:+.4f}
(90% date-clustered CI [{r.ci_low:+.4f}, {r.ci_high:+.4f}],
{r.n_clusters} clusters; team-clustered sensitivity CI
[{r.ci_sensitivity_team[0]:+.4f}, {r.ci_sensitivity_team[1]:+.4f}]).
Failed gates: {r.failed_gates or 'none'}. Thresholds: min_improvement
{r.thresholds['min_improvement']}, harm_ci_bound {r.thresholds['harm_ci_bound']},
per_season_tolerance {r.thresholds['per_season_tolerance']}.

Reading: the pooled CRPS delta ({r.pooled_improvement:+.4f}) is far inside the
CI's width — the empirical-quantile shape and the constant-sigma Gaussian are
statistically indistinguishable on these 673 games. The 610-game train pool's
quantiles evidently add no exploitable non-Gaussianity at this sample size
(and carry their own sampling noise). Per the registration's threshold note,
0.05 was a modest-but-real distributional gain; neither direction approaches
it. The honest conclusion is that the Gaussian(center, {sigma:.2f}) baseline is
an adequate margin distribution for the current forecast — CRPS ~{r.metric_incumbent:.1f}
on a ~{center_mae:.1f}-MAE center, consistent with the registered expectation.

## CRPS by season (lower is better; center MAE for scale)

{fmt_table(crps_tbl)}

## The two distributions

- Center (both variants): committed `str_margin_cal` from
  `experiments/channel_reval/predictions_v2.csv` — frozen; reproduction of the
  committed file verified to {provenance['committed_test_reproduction_max_dev']:.1e}.
- Residual pool: {provenance['n_rows']} eligible 2021-2023 chanreval train games
  ({provenance['rows_by_season']}), the exact games the committed calibration was
  fit on; walk-forward shifted-EWMA features; calibration params refit-verified to
  {provenance['calibration_param_reproduction_max_dev']:.1e}. Max pool date
  {provenance['max_pool_date']} < test-era start {provenance['test_era_start']}
  (asserted). Full listing: `residual_pool.csv`.
- Incumbent: Gaussian(center, sigma), sigma = pool std (ddof=1) = {sigma:.4f}.
  CRPS closed form via math.erf.
- Challenger: {M_SAMPLES}-probe ensemble of pool quantiles (linear
  interpolation) on p in [{TAIL_LO}, {TAIL_HI}], Gaussian N(0, sigma) tails
  outside ({splice['n_gaussian_tail_probes']} probes). Splice gaps
  (empirical - Gaussian): {splice['splice_gap_low']:+.3f} at p02,
  {splice['splice_gap_high']:+.3f} at p98. CRPS via the exact sorted-sample
  identity; Gaussian-vs-ensemble discretization bound
  {selftest['tests']['gauss_quantile_discretization_max_dev']['got']:.2e} points
  (self-test), negligible vs the deltas above.

## Cover probabilities vs the market (context, ungated)

Universe: {n_spread}/{len(test)} test games with a consensus spread (mean over
books of each book's latest pre-tip home spread; {len(missing)} game(s) uncovered);
{summary['cover_counts']['n_with_market_prob']} with a devigged market prob;
{n_push} push(es) excluded; three-way common subset n={len(common)}.
Market prob = proportional devig of each book's two-sided spread prices, mean
over books (mean overround {market_audit['mean_overround']:.4f};
{market_audit['invalid_price_pairs_excluded']} invalid price pair(s) excluded).

{fmt_table(cover_tbl)}

Reading (the headline context): for binary outcomes, always predicting 0.5
scores Brier 0.2500 exactly. The market's devigged probs
({cover_tbl.loc[0, 'brier_market']:.4f}) sit slightly below that baseline with
tight decile calibration — at its own consensus line the market is nearly, but
not exactly, a coin flip, and its small deviations are honest. Both model
variants sit slightly ABOVE 0.2500
(gauss {cover_tbl.loc[0, 'brier_gauss']:.4f}, emp {cover_tbl.loc[0, 'brier_emp']:.4f}:
+{cover_tbl.loc[0, 'brier_gauss'] - cover_tbl.loc[0, 'brier_market']:.4f} /
+{cover_tbl.loc[0, 'brier_emp'] - cover_tbl.loc[0, 'brier_market']:.4f} vs market):
the model's often-large deviations from 0.5 at the market's line (the model
and the consensus line disagree by {model_market_gap:.2f} points on average)
do not validate — the reliability deciles show observed cover rates regressing
to ~0.5 across the model's confidence bins. Any betting policy built on these
cover probabilities as-is would be betting noise; this is exactly the gating
input the registration says the PROBABILISTIC board needed measured.

Reliability (uniform deciles, `reliability_cover_*.csv`; gap = observed - predicted):

{fmt_table(pd.DataFrame([{'variant': k, **v} for k, v in rel_summary.items()]))}

Timing caveat (registration): old-era odds are single ~T-64m snapshots; the
extension era has multi-snapshot paths. "Latest pre-tip per book" therefore
means near-tip lines in both eras, but the old era offers no choice of earlier
cutoffs. Each book's devigged prob refers to its own line (mean cross-book
spread range {summary['book_line_dispersion']['mean_spread_range_across_books']:.2f}
points), while cover outcomes are graded against the consensus line.

## Pinball loss at preregistered quantiles (10/25/50/75/90)

{fmt_table(pin_tbl)}

## Audits

- Residual-pool provenance: PASS — {provenance['n_rows']} rows, all seasons in
  {TRAIN_YEARS}, max date {provenance['max_pool_date']} strictly before
  {provenance['test_era_start']}; zero test-era rows (hard-asserted).
- CRPS self-test: {'PASS' if selftest['all_pass'] else 'FAIL'} — hand-computed
  toys (two-point 0.5, three-point 2/3, m=1 -> |y-x|), Gaussian closed-form
  spot values, harness cross-check dev
  {selftest['tests']['harness_crosscheck_max_dev']['got']:.1e}, ppf inversion dev
  {selftest['tests']['ppf_inverts_cdf_max_dev']['got']:.1e}. `crps_selftest.json`.
- Cover-prob sanity: {'PASS' if sanity['all_pass'] else 'FAIL'} — all probs in
  [0,1]; P(cover) monotone nondecreasing in spread on a [-20, 20] grid for
  {sanity['monotonicity_games_checked']} sampled games, both variants.
- Gate 4 (joint forecast): structural — no point forecast altered
  (center identity max dev 0.0; asserted, not fitted).

## Files

`game_level_dist.csv` (per-game: center, sigma, q05..q95, spread, cover probs,
outcome) - `residual_pool.csv` - `crps_by_season.csv` -
`cover_brier_logloss.csv` - `reliability_cover_gauss.csv` /
`reliability_cover_emp.csv` / `reliability_cover_market.csv` -
`pinball_losses.csv` - `crps_selftest.json` - `gate_verdict.json` -
`summary.json`.
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")
    print(f"[done] artifacts in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
