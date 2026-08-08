#!/usr/bin/env python3
"""build_translation.py -- M13_PLAYER_VALUE_TRANSLATION: model point-prediction -> priceable terms.

MANDATE (see M13_PLAYER_VALUE_TRANSLATION.md, the node's contract): a player-points model emits a
POINT PREDICTION; a prop market quotes a THRESHOLD (a line plus two prices). These are different
objects. This node builds the explicit, versioned, deterministic function that converts one into
the other -- a distributional assumption fit from the model's own out-of-fold residuals -- and
reports whether the resulting probability is honestly calibrated against realized outcomes, out of
sample, against the market's own de-vigged probability at the same lines.

EPISTEMIC STATUS (write verbatim wherever this module's output is cited): "INTERFACE COMPONENT
under the four-system separation: fundamental system out, market terms in. Consumes only frozen,
versioned model snapshots from the forecast log; it never reads sealed possession results and never
reaches into a model's internals."

INPUTS (read-only; nothing here is modified):
  * experiments/cbs_v15_player_oof_v5/attempt_001/  -- RECEIPTED legacy points model, forecast log
    SCHEMA/2, generation-only, verified 7/7 in SCOREBOARD/granular/VERIFICATION_REPORT.md (D037).
  * data/props_capture/historical/master_props_historical.csv -- T1_VENDOR_ASSERTED props archive
    (D027 extension of M00-U2). Reused via M11_CONSENSUS_MODEL/consensus.py (vig math DELEGATED,
    never reimplemented) and MODEL_VS_MARKET/compute_model_vs_market.py (join/entity-resolution
    machinery IMPORTED AND REUSED, never reimplemented, so this node's matched universe is
    byte-identical to the one MODEL_VS_MARKET.md already reports).
  * owned regular-season gamelogs (outcomes), via compute_model_vs_market.load_outcomes().

NO SEALED_RESULTS. No git. No network. Deterministic under SEED. numpy/pandas only (no scipy in
this environment) -- the Student-t CDF used below is a from-scratch regularized-incomplete-beta
implementation (Numerical-Recipes betacf), documented at its definition.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# --- MEASUREMENT HARNESS PATCH (MEASURE_F1_m13_fitpool) -------------------
# This file is a VERBATIM COPY of
#   experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/build_translation.py
# with EXACTLY ONE change: the four path constants below, which in the
# original are derived from __file__, are pinned to the ORIGINAL M13
# location so that this copy resolves the same inputs from a different
# directory. NOTHING ELSE IS CHANGED. main() is never called from here.
_MEASURE_DIR = Path(__file__).resolve().parent          # .../exploration/MEASURE_F1_m13_fitpool
WORKTREE = _MEASURE_DIR.parents[2]                      # .../player-model-program
MARKET_PROGRAM = WORKTREE / "experiments" / "market_program"
HERE = _MEASURE_DIR / "repro_out"                       # writes land HERE, never in M13
HERE.mkdir(exist_ok=True)
LIVE_ROOT = WORKTREE.parents[2]                         # .../wnba-betting-model (DATA worktree root)

sys.path.insert(0, str(MARKET_PROGRAM / "M11_CONSENSUS_MODEL"))
sys.path.insert(0, str(MARKET_PROGRAM / "MODEL_VS_MARKET"))
import consensus  # noqa: E402  -- vig math DELEGATED to this module
import compute_model_vs_market as mvm  # noqa: E402  -- join/entity-resolution machinery REUSED

CONTRACT_MD = MARKET_PROGRAM / "M00_MARKET_PROGRAM_CONTRACT" / "MARKET_PROGRAM_CONTRACT.md"
TAXONOMY = MARKET_PROGRAM / "M00_MARKET_PROGRAM_CONTRACT" / "TAXONOMY.json"
MODEL_VS_MARKET_JSON = MARKET_PROGRAM / "MODEL_VS_MARKET" / "model_vs_market.json"
CONTRACT_SHA256_EXPECTED = "1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de"

SEED = 20260806            # same seed as every other market-lane node's cluster bootstrap
N_BOOT = 1000
HEADLINE_TIER = "A_primary"
FIT_SEASONS = [2022, 2023, 2024, 2025, 2026]   # excludes 2021 -- degenerate, no-train, fallback-only fold
STABILITY_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
EPS_LOGLOSS = 1e-6

TRANSLATION_SCHEMA_VERSION = "m13_translation_v1"

EPISTEMIC_STATUS_LINE = (
    "INTERFACE COMPONENT under the four-system separation: fundamental system out, market terms "
    "in. Consumes only frozen, versioned model snapshots from the forecast log; it never reads "
    "sealed possession results and never reaches into a model's internals."
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


# ---------------------------------------------------------------------------
# distribution machinery -- no scipy in this environment; from-scratch,
# documented implementations. Normal via erf; Student-t via the regularized
# incomplete beta function (Numerical Recipes continued-fraction algorithm).
# ---------------------------------------------------------------------------

_erf_vec = np.vectorize(math.erf, otypes=[float])


def normal_cdf(x, loc=0.0, scale=1.0):
    z = (np.asarray(x, dtype=float) - loc) / scale
    return 0.5 * (1.0 + _erf_vec(z / math.sqrt(2.0)))


def normal_logpdf(x, loc=0.0, scale=1.0):
    z = (np.asarray(x, dtype=float) - loc) / scale
    return -0.5 * z * z - math.log(scale) - 0.5 * math.log(2.0 * math.pi)


def _betacf(a: float, b: float, x: float, maxit: int = 300, eps: float = 3e-16,
            fpmin: float = 1e-300) -> float:
    """Continued-fraction evaluation for the incomplete beta function (Numerical
    Recipes, Press et al., 'betacf'). Standard textbook algorithm; no scipy
    available in this environment."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def _betainc_scalar(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a,b), scalar. Numerical Recipes 'betai'."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                   + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _student_t_cdf_scalar(x: float, df: float) -> float:
    xt = df / (df + x * x)
    p = _betainc_scalar(df / 2.0, 0.5, xt)
    return 1.0 - 0.5 * p if x > 0 else 0.5 * p


_student_t_cdf_vec = np.vectorize(_student_t_cdf_scalar, otypes=[float])


def student_t_cdf(x, df: float, loc: float = 0.0, scale: float = 1.0):
    z = (np.asarray(x, dtype=float) - loc) / scale
    return _student_t_cdf_vec(z, df)


def student_t_logpdf(x, df: float, loc: float = 0.0, scale: float = 1.0):
    z = (np.asarray(x, dtype=float) - loc) / scale
    const = (math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0)
              - 0.5 * math.log(df * math.pi) - math.log(scale))
    return const - (df + 1.0) / 2.0 * np.log1p(z * z / df)


def empirical_cdf(x, sorted_ref: np.ndarray):
    x = np.asarray(x, dtype=float)
    n = len(sorted_ref)
    ranks = np.searchsorted(sorted_ref, x, side="right")
    return ranks / n


# ---------------------------------------------------------------------------
# moment statistics (no scipy.stats)
# ---------------------------------------------------------------------------

def moment_stats(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    n = len(x)
    mean = float(x.mean())
    std = float(x.std(ddof=1))
    m2 = float(np.mean((x - mean) ** 2))
    m3 = float(np.mean((x - mean) ** 3))
    m4 = float(np.mean((x - mean) ** 4))
    skew = m3 / (m2 ** 1.5) if m2 > 0 else float("nan")
    excess_kurt = m4 / (m2 ** 2) - 3.0 if m2 > 0 else float("nan")
    return {"n": int(n), "mean": mean, "std_ddof1": std, "median": float(np.median(x)),
            "skewness_fisher_pearson": skew, "excess_kurtosis": excess_kurt,
            "min": float(x.min()), "max": float(x.max()),
            "p05": float(np.percentile(x, 5)), "p95": float(np.percentile(x, 95))}


def fit_student_t_by_moment_ll_grid(x: np.ndarray, df_grid=None) -> dict:
    """Method-of-moments Student-t fit: loc = sample mean, scale chosen so the
    t(df) distribution's variance matches the sample variance
    (scale = std * sqrt((df-2)/df) for df>2), and df selected by maximizing the
    Student-t log-likelihood over a fixed grid (this is a grid profile search
    over df, NOT a joint MLE of loc/scale/df -- documented simplification,
    reported in FINDINGS.json's `could_not_establish`).
    """
    if df_grid is None:
        df_grid = [3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200]
    x = np.asarray(x, dtype=float)
    loc = float(x.mean())
    std = float(x.std(ddof=1))
    results = []
    for df in df_grid:
        scale = std * math.sqrt((df - 2.0) / df)
        ll = float(np.sum(student_t_logpdf(x, df, loc=loc, scale=scale)))
        results.append({"df": df, "scale": scale, "loglik": ll})
    best = max(results, key=lambda r: r["loglik"])
    return {"loc": loc, "df": best["df"], "scale": best["scale"],
            "loglik": best["loglik"], "grid": results}


def fit_normal(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=float)
    loc = float(x.mean())
    scale = float(x.std(ddof=1))
    ll = float(np.sum(normal_logpdf(x, loc=loc, scale=scale)))
    return {"loc": loc, "scale": scale, "loglik": ll}


def aic(loglik: float, k: int) -> float:
    return -2.0 * loglik + 2.0 * k


# ---------------------------------------------------------------------------
# calibration / scoring
# ---------------------------------------------------------------------------

def brier_score(p, y) -> float:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    return float(np.mean((p - y) ** 2))


def log_loss(p, y, eps: float = EPS_LOGLOSS) -> float:
    p = np.clip(np.asarray(p, dtype=float), eps, 1.0 - eps)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def reliability_table(p, y, n_bins: int = 10) -> list:
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (p >= lo) & (p < hi) if i < n_bins - 1 else (p >= lo) & (p <= hi)
        n = int(mask.sum())
        rows.append({
            "bin_lo": float(lo), "bin_hi": float(hi), "n": n,
            "mean_predicted_p": float(p[mask].mean()) if n > 0 else None,
            "observed_frequency": float(y[mask].mean()) if n > 0 else None,
        })
    return rows


def paired_cluster_bootstrap_diff(a, b, clusters, n_boot=N_BOOT, seed=SEED) -> dict:
    """CI on mean(a) - mean(b), game-date-cluster-bootstrapped -- delegates to
    MODEL_VS_MARKET's cluster_bootstrap_ci on the pointwise difference so the
    method is byte-identical to every other market-lane node's CI."""
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    return mvm.cluster_bootstrap_ci(diff, clusters, n_boot=n_boot, seed=seed)


def bootstrap_param_ci(residuals: np.ndarray, clusters: np.ndarray, n_boot=N_BOOT, seed=SEED) -> dict:
    """Cluster-bootstrap CI on (loc, scale) of the primary Normal fit -- this IS
    the propagated translation uncertainty (mandate: 'uncertainty propagated,
    not discarded'), not a per-row phantom precision."""
    codes, _ = pd.factorize(np.asarray(clusters), sort=True)
    n_clusters = int(codes.max()) + 1
    rng = np.random.default_rng(seed)
    locs, scales = [], []
    # group residuals by cluster once
    by_cluster = [residuals[codes == c] for c in range(n_clusters)]
    for _ in range(n_boot):
        draw = rng.integers(0, n_clusters, size=n_clusters)
        pooled = np.concatenate([by_cluster[c] for c in draw]) if n_clusters else np.array([])
        if len(pooled) < 2:
            continue
        locs.append(pooled.mean())
        scales.append(pooled.std(ddof=1))
    locs = np.asarray(locs)
    scales = np.asarray(scales)
    return {
        "loc_ci95": [float(np.percentile(locs, 2.5)), float(np.percentile(locs, 97.5))],
        "scale_ci95": [float(np.percentile(scales, 2.5)), float(np.percentile(scales, 97.5))],
        "n_boot": int(len(locs)), "seed": int(seed),
        "method": "cluster_bootstrap_over_game_dates_percentile_refit_per_draw",
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    got_contract = sha256_file(CONTRACT_MD)
    if got_contract != CONTRACT_SHA256_EXPECTED:
        raise RuntimeError(f"contract sha256 mismatch: {got_contract}")
    if consensus.CONTRACT_SHA256 != CONTRACT_SHA256_EXPECTED:
        raise RuntimeError("consensus.py pins a different contract hash")

    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    u2 = next(u for u in taxonomy["final_state_archive_ruling"]["permitted_uses"]
              if u["use_class"] == "M00-U2")
    u2_hash = hashlib.sha256(u2["caveat_text"].encode("utf-8")).hexdigest()
    if u2_hash != u2["caveat_sha256"]:
        raise RuntimeError("M00-U2 caveat hash does not reproduce from TAXONOMY.json")

    print("loading outcomes + scored model rows (REUSED from compute_model_vs_market)...")
    outcomes, name_rows, outcome_audit = mvm.load_outcomes()
    scored, model_audit = mvm.load_scored_points(outcomes)          # ALL out-of-fold rows, all tiers
    id_index = mvm.build_identity_index(name_rows)
    market, market_audit, unresolved = mvm.build_market_frame(id_index)

    # ---- reconstruct the IDENTICAL matched/evaluable universe MODEL_VS_MARKET.md reports ----
    m = scored.merge(market, on=["game_id", "player_id"], how="inner", validate="one_to_one")
    push = (m["pts"] == m["consensus_line"])
    model_nocall = (m["pred_point"] == m["consensus_line"])
    market_nocall = (m["p_over_devig"] == 0.5)
    ev = m[~push & ~model_nocall & ~market_nocall].copy()

    integrity = {
        "n_matched_player_games_this_run": int(len(m)),
        "n_evaluable_matched_player_games_this_run": int(len(ev)),
    }
    if MODEL_VS_MARKET_JSON.exists():
        mvm_json = json.loads(MODEL_VS_MARKET_JSON.read_text(encoding="utf-8"))
        ja = mvm_json["join_audit"]
        integrity["n_matched_player_games_model_vs_market_json"] = ja["n_matched_player_games"]
        integrity["n_evaluable_matched_player_games_model_vs_market_json"] = ja["n_evaluable_matched_player_games"]
        integrity["matches_model_vs_market_json"] = (
            integrity["n_matched_player_games_this_run"] == ja["n_matched_player_games"]
            and integrity["n_evaluable_matched_player_games_this_run"] == ja["n_evaluable_matched_player_games"]
        )
    else:
        integrity["matches_model_vs_market_json"] = None
        integrity["note"] = "MODEL_VS_MARKET/model_vs_market.json not found -- cross-check skipped, not blocking"
    print("integrity cross-check vs MODEL_VS_MARKET.md:", integrity)

    # =====================================================================
    # STEP 1 -- fit the residual distribution on OUT-OF-FOLD errors, HELD OUT
    # from the matched-market universe (no row used to fit the distribution
    # is ever scored for calibration below -- this is what makes the
    # calibration check below an honest out-of-sample test, not circular).
    # =====================================================================
    matched_row_uids = set(m["row_uid"])
    fit_pool = scored[
        (scored["evaluation_tier"] == HEADLINE_TIER)
        & (scored["season"].isin(FIT_SEASONS))
        & (~scored["row_uid"].isin(matched_row_uids))
    ].copy()
    fit_pool["residual"] = fit_pool["pred_point"] - fit_pool["pts"]  # pred - actual

    diag = moment_stats(fit_pool["residual"].to_numpy())
    print("fit_pool residual diagnostics:", diag)

    normal_fit = fit_normal(fit_pool["residual"].to_numpy())
    normal_fit["aic"] = aic(normal_fit["loglik"], k=2)

    t_fit = fit_student_t_by_moment_ll_grid(fit_pool["residual"].to_numpy())
    t_fit["aic"] = aic(t_fit["loglik"], k=3)

    primary_family = "student_t" if t_fit["aic"] < normal_fit["aic"] else "normal"

    # ---- heteroscedasticity check: does dispersion scale with pred_point? ----
    fp = fit_pool
    q = pd.qcut(fp["pred_point"], 10, duplicates="drop")
    het_bins = (fp.groupby(q, observed=True)
                .agg(mean_pred=("pred_point", "mean"),
                     std_resid=("residual", lambda s: float(s.std(ddof=1))),
                     n=("residual", "size"))
                .reset_index(drop=True))
    bin_means = het_bins["mean_pred"].to_numpy()
    bin_stds = het_bins["std_resid"].to_numpy()
    het_corr = float(np.corrcoef(bin_means, bin_stds)[0, 1]) if len(bin_means) > 1 else float("nan")

    # row-level Spearman-style rank correlation between |residual| and pred_point
    r_pred = pd.Series(fp["pred_point"]).rank().to_numpy()
    r_abs = pd.Series(fp["residual"].abs()).rank().to_numpy()
    spearman_abs_resid_vs_pred = float(np.corrcoef(r_pred, r_abs)[0, 1])

    # heteroscedastic normal: |residual| ~ a + b*pred_point (closed-form OLS), a
    # material fitted slope (|spearman| notably away from 0) is required before
    # this variant is offered as anything but a documented sensitivity probe.
    X = np.column_stack([np.ones(len(fp)), fp["pred_point"].to_numpy()])
    yv = fp["residual"].abs().to_numpy()
    beta, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid_ols = yv - X @ beta
    sse = float(np.sum(resid_ols ** 2))
    n_ols = len(fp)
    sxx = float(np.sum((X[:, 1] - X[:, 1].mean()) ** 2))
    se_b = math.sqrt((sse / (n_ols - 2)) / sxx)
    t_stat_b = float(beta[1] / se_b)
    # normal-approximation two-sided p-value (n is in the thousands; t≈z is fine)
    p_value_b = float(2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t_stat_b) / math.sqrt(2.0)))))
    het_model = {"intercept_mean_abs_resid": float(beta[0]), "slope_per_pred_point": float(beta[1]),
                 "t_stat": t_stat_b, "p_value_normal_approx": p_value_b,
                 "bin_level_pearson_r_meanpred_vs_stdresid": het_corr,
                 "row_level_spearman_absresid_vs_pred": spearman_abs_resid_vs_pred,
                 "heteroscedasticity_material": bool(p_value_b < 0.01 and abs(t_stat_b) > 3)}

    # ---- season-level parameter stability (diagnostic; full A_primary population, not fit_pool) ----
    season_stability = []
    for s in STABILITY_SEASONS:
        sub = scored[(scored["evaluation_tier"] == HEADLINE_TIER) & (scored["season"] == s)]
        if len(sub) == 0:
            continue
        r = (sub["pred_point"] - sub["pts"]).to_numpy()
        season_stability.append({"season": s, "n": int(len(sub)),
                                  "bias_mean_pred_minus_actual": float(r.mean()),
                                  "std_ddof1": float(r.std(ddof=1)),
                                  "fitted_fold": s != 2021})

    # ---- propagated parameter uncertainty (cluster bootstrap on fit_pool) ----
    param_ci = bootstrap_param_ci(fit_pool["residual"].to_numpy(),
                                   fit_pool["game_date"].to_numpy())

    # =====================================================================
    # STEP 2 -- build translation variants and apply to the HELD-OUT matched
    # market universe `ev` (disjoint from fit_pool by construction).
    # =====================================================================
    ev = ev.copy()
    threshold = ev["pred_point"].to_numpy() - ev["consensus_line"].to_numpy()   # pred - line

    sorted_resid = np.sort(fit_pool["residual"].to_numpy())

    p_normal = normal_cdf(threshold, loc=normal_fit["loc"], scale=normal_fit["scale"])
    p_t = student_t_cdf(threshold, df=t_fit["df"], loc=t_fit["loc"], scale=t_fit["scale"])
    p_empirical = empirical_cdf(threshold, sorted_resid)

    sigma_row = np.clip(beta[0] + beta[1] * ev["pred_point"].to_numpy(), 0.5, None) * math.sqrt(math.pi / 2.0)
    p_het_normal = normal_cdf(threshold, loc=normal_fit["loc"], scale=1.0) * 0.0  # placeholder overwritten below
    p_het_normal = 0.5 * (1.0 + _erf_vec((threshold - normal_fit["loc"]) / (sigma_row * math.sqrt(2.0))))

    ev["p_over_normal"] = p_normal
    ev["p_over_student_t"] = p_t
    ev["p_over_empirical"] = p_empirical
    ev["p_over_het_normal"] = p_het_normal
    ev["y_over"] = (ev["pts"] > ev["consensus_line"]).astype(float)
    ev["p_over_market_devig"] = ev["p_over_devig"]
    ev["diff_normal_minus_market"] = ev["p_over_normal"] - ev["p_over_market_devig"]

    variant_cols = {"normal": "p_over_normal", "student_t": "p_over_student_t",
                     "empirical": "p_over_empirical", "het_normal": "p_over_het_normal"}
    primary_col = variant_cols[primary_family]

    tiers = {HEADLINE_TIER: ev[ev["evaluation_tier"] == HEADLINE_TIER], "all_tiers": ev}

    def score_block(sub: pd.DataFrame) -> dict:
        if len(sub) == 0:
            return {"status": "NO_EVALUABLE_ROWS"}
        y = sub["y_over"].to_numpy()
        market_p = sub["p_over_market_devig"].to_numpy()
        out = {"n_player_games": int(len(sub)), "n_games": int(sub["game_id"].nunique()),
               "over_base_rate": float(y.mean()),
               "market": {"brier": brier_score(market_p, y), "log_loss": log_loss(market_p, y),
                          "reliability": reliability_table(market_p, y)}}
        for name, col in variant_cols.items():
            p = sub[col].to_numpy()
            out[name] = {"brier": brier_score(p, y), "log_loss": log_loss(p, y),
                         "reliability": reliability_table(p, y),
                         "mean_p_over": float(p.mean()), "call_over_rate": float((p > 0.5).mean())}
        # primary vs market paired CI (Brier and log-loss), clustered by game_date
        p_primary = sub[primary_col].to_numpy()
        sq_primary = (p_primary - y) ** 2
        sq_market = (market_p - y) ** 2
        out["primary_vs_market_brier_diff_ci95"] = paired_cluster_bootstrap_diff(
            sq_primary, sq_market, sub["game_date"].to_numpy())
        ll_primary = -(y * np.log(np.clip(p_primary, EPS_LOGLOSS, 1 - EPS_LOGLOSS))
                        + (1 - y) * np.log(1 - np.clip(p_primary, EPS_LOGLOSS, 1 - EPS_LOGLOSS)))
        ll_market = -(y * np.log(np.clip(market_p, EPS_LOGLOSS, 1 - EPS_LOGLOSS))
                       + (1 - y) * np.log(1 - np.clip(market_p, EPS_LOGLOSS, 1 - EPS_LOGLOSS)))
        out["primary_vs_market_logloss_diff_ci95"] = paired_cluster_bootstrap_diff(
            ll_primary, ll_market, sub["game_date"].to_numpy())
        # sensitivity: how much do translation VARIANTS disagree with each other?
        pn, pt_, pe, ph = (sub[c].to_numpy() for c in
                           ("p_over_normal", "p_over_student_t", "p_over_empirical", "p_over_het_normal"))
        out["sensitivity_across_variants"] = {
            "rmse_normal_vs_student_t": float(np.sqrt(np.mean((pn - pt_) ** 2))),
            "rmse_normal_vs_empirical": float(np.sqrt(np.mean((pn - pe) ** 2))),
            "rmse_normal_vs_het_normal": float(np.sqrt(np.mean((pn - ph) ** 2))),
            "max_abs_normal_vs_student_t": float(np.max(np.abs(pn - pt_))),
            "call_flip_rate_normal_vs_student_t": float(np.mean((pn > 0.5) != (pt_ > 0.5))),
            "call_flip_rate_normal_vs_empirical": float(np.mean((pn > 0.5) != (pe > 0.5))),
            "call_flip_rate_normal_vs_het_normal": float(np.mean((pn > 0.5) != (ph > 0.5))),
        }
        return out

    cells = {tname: score_block(tdf) for tname, tdf in tiers.items()}

    head = cells[HEADLINE_TIER]
    bdiff = head["primary_vs_market_brier_diff_ci95"]
    if bdiff["hi"] < 0:
        calib_verdict = "TRANSLATION_BETTER_CALIBRATED_THAN_MARKET"
    elif bdiff["lo"] > 0:
        calib_verdict = "TRANSLATION_WORSE_CALIBRATED_THAN_MARKET"
    else:
        calib_verdict = "INDISTINGUISHABLE_FROM_MARKET_AT_THIS_N"

    # =====================================================================
    # write per-row translation table (parquet) -- "every translated fair
    # line records the model version and snapshot timestamp it came from"
    # =====================================================================
    out_cols = ["row_uid", "game_id", "player_id", "player_name", "season", "evaluation_tier",
                "game_date", "forecast_cutoff", "pred_point", "consensus_line", "pts", "y_over",
                "p_over_normal", "p_over_student_t", "p_over_empirical", "p_over_het_normal",
                "p_over_market_devig", "diff_normal_minus_market", "n_books_at_consensus_line",
                "snap_ret_utc"]
    rows_out = ev[out_cols].copy()
    rows_out["model_version"] = "cbs_v15_player_oof_v5/1 (arm cbs_v15_player_oof_v5, rev 8)"
    rows_out["translation_schema_version"] = TRANSLATION_SCHEMA_VERSION
    rows_out["forecast_cutoff"] = rows_out["forecast_cutoff"].astype(str)
    rows_out.to_parquet(HERE / "translation_rows.parquet", index=False)
    rows_out_hash = sha256_file(HERE / "translation_rows.parquet")

    # =====================================================================
    # assemble FINDINGS.json
    # =====================================================================
    findings = {
        "schema": "market_program/M13_PLAYER_VALUE_TRANSLATION/findings/1",
        "generated_utc": utcnow(),
        "epistemic_status": EPISTEMIC_STATUS_LINE,
        "decision_authority": ["D023_MARKET_PROGRAM_AUTHORIZED", "D027_PROPS_HISTORICAL_BOUNDED_USES",
                                "D036_SCOREBOARD_MEASUREMENT_SEMANTICS", "D037", "D043"],
        "evidence_class": "PRELIMINARY",
        "evidence_class_reason": ("interface-component translation of a RECEIPTED legacy artifact "
                                  "against a T1 vendor-asserted props archive; not a preregistered "
                                  "family endpoint; no evidence-ladder label (contract section 3) is "
                                  "claimed or held"),
        "evidence_ladder_labels_held": [],
        "seed": SEED, "n_boot": N_BOOT,
        "contract_sha256_verified": got_contract,
        "commit_sha": ("UNAVAILABLE: no git in this worktree per task constraints; the legacy "
                       "producing run's clean-tree receipt asserts commit "
                       "0108ef86e9c085e1d701e40e53c24dcde177ac97 (reproduced, not independently "
                       "verified); manifest content hashes are the verified anchors"),
        "m00_bounded_use": {
            "m00_use_class": "M00-U2", "extended_to_this_archive_by": "D027_PROPS_HISTORICAL_BOUNDED_USES",
            "object": "data/props_capture/historical/master_props_historical.csv (T1_VENDOR_ASSERTED)",
            "caveat_text_verbatim": u2["caveat_text"], "caveat_hash": u2["caveat_sha256"],
            "additional_prohibitions_honored": ("no CLV, timing, lead-lag, stale-window or "
                                                "executability claim is made anywhere in this node"),
        },

        "inventory": {
            "legacy_model": {
                "path": "experiments/cbs_v15_player_oof_v5/attempt_001/",
                "run_id": "cbs_v15_player_oof_v5/1", "target": "player_scoring_distribution (points)",
                "verification": "SCOREBOARD/granular/VERIFICATION_REPORT.md -- 7/7 RECEIPTED",
                "n_scored_points_rows_all_tiers_all_seasons": int(len(scored)),
                "n_A_primary_pooled_2022_2026": int(len(scored[(scored.evaluation_tier == HEADLINE_TIER)
                                                                & (scored.season.isin(FIT_SEASONS))])),
            },
            "model_vs_market_prior_work": {
                "path": "experiments/market_program/MODEL_VS_MARKET/MODEL_VS_MARKET.md",
                "reused_functions": ["load_outcomes", "load_scored_points", "build_identity_index",
                                     "build_market_frame"],
                "finding_reused": "matched-universe binary-call comparison (model pred>line vs "
                                  "market P(over)>0.5); this node adds the missing piece -- an actual "
                                  "model PROBABILITY, which MODEL_VS_MARKET explicitly did not build "
                                  "('The model has NO Brier: it is a point prediction, not a "
                                  "probability.')",
                "integrity_cross_check_vs_reproduced_join": integrity,
            },
            "score_baselines_context": {
                "path": "experiments/market_program/SCORE_BASELINES/SCORE_BASELINES.md",
                "relevance": "team-level score-family composite, not player-level; not consumed by "
                             "this node's translation, cited here only as sibling market-lane context "
                             "for the same matched-universe discipline",
            },
            "props_archive": {
                "path": "data/props_capture/historical/master_props_historical.csv",
                "n_rows": market_audit["source"]["n_rows"], "n_games": market_audit["source"]["n_games"],
                "tier": "T1_VENDOR_ASSERTED per D027",
            },
        },

        "distributional_assumption": {
            "question": ("A point prediction is not a threshold probability. Converting one to the "
                        "other requires an explicit assumption about the distribution of the model's "
                        "own error around its point prediction. This assumption is fit from data, "
                        "not asserted."),
            "fit_pool": {
                "definition": ("A_primary tier, fitted folds only (seasons 2022-2026; 2021 excluded, "
                              "degenerate no-train fallback-only fold), and DISJOINT from the "
                              "matched-market evaluation universe below (no row used to fit the "
                              "distribution is ever scored for calibration -- this is what makes the "
                              "calibration check an honest out-of-sample test)."),
                "n": diag["n"],
            },
            "residual_diagnostics": diag,
            "normal_fit": normal_fit,
            "student_t_fit": {k: v for k, v in t_fit.items() if k != "grid"},
            "student_t_df_grid_loglik": t_fit["grid"],
            "model_selection": {
                "criterion": "AIC = -2*loglik + 2*k (k=2 normal: loc,scale; k=3 student-t: loc,scale,df)",
                "normal_aic": normal_fit["aic"], "student_t_aic": t_fit["aic"],
                "primary_family_selected": primary_family,
                "selection_note": ("Student-t's df was chosen by a log-likelihood GRID PROFILE, not a "
                                  "joint MLE of (loc, scale, df); this is a documented simplification "
                                  "(see could_not_establish)."),
            },
            "heteroscedasticity_check": het_model,
            "season_level_parameter_stability": season_stability,
            "propagated_parameter_uncertainty": param_ci,
        },

        "translation_function": {
            "version": TRANSLATION_SCHEMA_VERSION,
            "formula": ("P(points > line) = CDF_e(pred_point - line), where e = pred_point - actual "
                       "is the fitted out-of-fold residual distribution (location = fitted bias, "
                       "scale = fitted dispersion). Four named, deterministic variants are reported "
                       "(never blended): normal (homoscedastic), student_t (homoscedastic, "
                       "heavier-tailed), empirical (nonparametric ECDF of fit_pool residuals, no "
                       "shape assumption), het_normal (normal with dispersion linear in pred_point, "
                       "offered only as a sensitivity probe -- see heteroscedasticity_material)."),
            "primary_variant": primary_family,
            "deterministic": True,
            "per_row_fields_recorded": ["model_version", "forecast_cutoff", "translation_schema_version",
                                        "pred_point", "consensus_line", "all four p_over_* variants",
                                        "p_over_market_devig", "diff_normal_minus_market"],
            "per_row_output": {"path": "experiments/market_program/M13_PLAYER_VALUE_TRANSLATION/translation_rows.parquet",
                               "sha256": rows_out_hash, "n_rows": int(len(rows_out))},
        },

        "calibration": {
            "universe": f"{HEADLINE_TIER} matched player-games (headline) / all_tiers (labelled, "
                       "never headline) -- STRICT INTERSECTION of scored model rows and resolved "
                       "two-sided props, held out from the distribution fit",
            "cells": cells,
            "headline_verdict": calib_verdict,
            "headline_verdict_note": ("Compares the PRIMARY translation variant's squared/log-loss "
                                     "error to the market's de-vigged squared/log-loss error, paired "
                                     "per player-game, game-date-clustered 95% CI. "
                                     + {
                                         "TRANSLATION_BETTER_CALIBRATED_THAN_MARKET": "The translated "
                                         "probability's error is significantly LOWER than the "
                                         "market's on this universe.",
                                         "TRANSLATION_WORSE_CALIBRATED_THAN_MARKET": "The translated "
                                         "probability's error is significantly HIGHER than the "
                                         "market's on this universe -- report this plainly; it is the "
                                         "honest prerequisite to any future edge claim, per this "
                                         "node's mandate.",
                                         "INDISTINGUISHABLE_FROM_MARKET_AT_THIS_N": "The clustered CI "
                                         "on the paired error difference includes zero: not "
                                         "distinguishable from the market at this sample size.",
                                       }[calib_verdict]),
        },

        "could_not_establish": [
            "A joint MLE of (location, scale, degrees-of-freedom) for the Student-t alternative: no "
            "scipy is available in this environment, so df was chosen by a log-likelihood grid profile "
            "over loc/scale fixed by the method of moments, not a joint optimizer. The AIC comparison "
            "against the normal fit is still valid (both are fitted log-likelihoods evaluated on the "
            "same data) but the Student-t parameters are not the global MLE.",
            "A true parametric skew-normal fit: not attempted (no scipy). Skewness is reported as a "
            "moment diagnostic only (residual_diagnostics.skewness_fisher_pearson); if it is material "
            "and the normal/student-t variants both miss it, that is a limitation of both fitted "
            "variants, not resolved by this node.",
            "Whether the translated probability is calibrated CONDITIONAL on model confidence, injury "
            "context, or minutes-uncertainty (e.g. p_active from the same legacy run): not attempted; "
            "the translation is unconditional on anything but pred_point and the market line, per the "
            "mandate's scope (translate the point prediction, not re-model the player).",
            "Any timing, CLV, lead-lag, or stale-window claim from the props archive: structurally "
            "out of scope for this T1 archive (D016/P2B; contract section 5) and not attempted here.",
            "Calibration for stat families other than points (rebounds/assists/steals/blocks/threes/"
            "turnovers): the legacy lane never registered these targets (PROBE_LEGACY.md); the props "
            "archive's market_key is exclusively player_points (asserted in compute_model_vs_market.py); "
            "no translation exists for them because no matched model-and-market data exists for them.",
            "Whether the het_normal variant's fitted heteroscedasticity is causally meaningful (vs. an "
            "artifact of usage-tier composition at high/low predicted points): reported as a fitted "
            "sensitivity probe only, per heteroscedasticity_material's significance test, never adopted "
            "as the primary variant regardless of its p-value, per this node's mandate to report the "
            "assumption used and its sensitivity, not to search for the best-fitting one after seeing "
            "calibration results (which would be tuning-on-results).",
        ],

        "contradictions_found": [],
    }
    findings["result_hash"] = sha256_hex(canonical_json(
        {k: v for k, v in findings.items() if k != "generated_utc"}))

    (HERE / "FINDINGS.json").write_text(json.dumps(findings, indent=1, default=str), encoding="utf-8")

    print("primary_family:", primary_family)
    print("headline calibration verdict:", calib_verdict)
    print("A_primary Brier -- primary:", head[primary_family]["brier"],
          "market:", head["market"]["brier"])
    print("wrote FINDINGS.json and translation_rows.parquet")


if __name__ == "__main__":
    main()
