#!/usr/bin/env python3
"""Damped online within-season totals bias correction — registered experiment
``totals_online_correction_v1``.

Registered 2026-07-31T00:02:30Z in experiments/registry.jsonl (BEFORE this code
was written). This script never registers; it evaluates the registered
hypothesis exactly as recorded:

    challenger(g) = str_total_cal(g) + (n / (n + 15)) * mean(pool)

    * pool — the incumbent's own residuals (total_true - str_total_cal) over
      SAME-SEASON games on STRICTLY EARLIER dates than g (walk-forward,
      shifted; same-date games never see each other).
    * n — pool size. Season openers: n = 0 -> correction = 0 exactly (the
      registered explicit no-info state; nothing is imputed).
    * K = 15 — FIXED A PRIORI in the registration. Zero fitted or tuned
      parameters anywhere in this script. K in {5, 30} is computed as a
      registered DIAGNOSTIC ONLY (reported, never used for selection).

    Inputs frozen: experiments/channel_reval/predictions_v2.csv
    (str_total_cal, total_true, dates, seasons) — the 673 chanreval test
    games. predictions_v2.csv holds test seasons only, so the mechanism's
    "applies to train seasons identically" clause is vacuous here: there is
    nothing to fit and nothing fit.

    Incumbent: chanreval_str_total_cal — str_total_cal from the committed
    predictions_v2.csv. Hard assert before any comparison: pooled total MAE
    on the 673 test games == 14.2236 within 1e-3.

    MARGIN INVARIANCE IS STRUCTURAL (registered audit, asserted not fitted):
    the challenger shifts only the TOTAL. This script writes no margin column
    anywhere, and asserts (i) no output column mentions margin,
    (ii) predictions_v2.csv is byte-identical before and after the run.

    Primary (gated): game-total MAE, challenger vs incumbent, the identical
    673 games, evalharness.compare_to_incumbent (loss absolute, cluster=date,
    n_boot 2000, seed 20260730, team-cluster sensitivity via franchise
    TEAM_ID). Registered secondaries (recorded, NOT gated): per-season mean
    bias vs the preregistered bar (max |seasonal bias| < 2.5; incumbent 2026
    -4.97); bookie-paired context on the 365 covered games (bookie 14.909);
    per-game correction magnitude distribution by season.

Predecessors: totals_head_v1 (FAIL — train-frozen coefficients cannot apply a
level shift the training era never exhibited) and the totals_groundwork §4.4
UNdamped online correction (exploratory, pooled-negative 14.278 vs 14.224).
This registration tests whether a-priori damping rescues the online family;
a FAIL kills the family cleanly.

Usage:
    python totals_online.py --smoke   # scratch COPY of the registry (tempdir)
                                      # passed as registry_path + scratch
                                      # outdir; the real ledger is never
                                      # touched; --outdir overrides the
                                      # artifact target
    python totals_online.py --real    # records the evaluation on the REAL
                                      # ledger, artifacts -> experiments/
                                      # totals_online/ (orchestrator only)

No network. Python 3.13 + pandas/numpy only. Deterministic (fixed seeds).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

import evalharness as eh                      # noqa: E402

EXPERIMENT_ID = "totals_online_correction_v1"
INCUMBENT_ID = "chanreval_str_total_cal"
OUTDIR = REPO / "experiments" / "totals_online"
CHANREVAL = REPO / "experiments" / "channel_reval"
PREDICTIONS = CHANREVAL / "predictions_v2.csv"
CHANNEL_BASE = CHANREVAL / "channel_base_v2.csv"      # read-only: franchise ids + coverage denominator
BOOKIE_TOTALS = REPO / "experiments" / "totals_groundwork" / "bookie_totals_per_game.csv"
GROUNDWORK_UNDAMPED = REPO / "experiments" / "totals_groundwork" / "exploratory_bias_fix_per_game.csv"

K_REGISTERED = 15                             # registered constant — never tuned
K_DIAGNOSTIC = [5, 30]                        # registered DIAGNOSTIC ONLY grid
TEST_YEARS = [2024, 2025, 2026]
N_UNIVERSE = 673                              # registered game universe
INCUMBENT_ANCHOR = 14.2236                    # registered reproduction anchor
ANCHOR_TOL = 1e-3
BOOKIE_ANCHOR = 14.909                        # registered bookie context anchor
BOOKIE_N = 365                                # registered covered subset size
BIAS_BAR = 2.5                                # preregistered seasonal-bias success bar
SEED = 20260730                               # harness bootstrap seed (default)
AUDIT_SEED = 20260730
AUDIT_RANDOM_PER_SEASON = 4                   # + openers + season-final games -> >= 15 total
EXPECTED_THRESHOLDS = {"min_improvement": 0.05, "harm_ci_bound": 0.05,
                       "per_season_tolerance": 0.25, "coverage_tolerance": 0.0}
TOL = 1e-9


def log(msg: str) -> None:
    print(f"[totals_online] {msg}")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. frozen universe + incumbent reproduction (registered hard assert)
# ---------------------------------------------------------------------------

def load_universe() -> pd.DataFrame:
    """The 673 chanreval test games, sorted (season, date, game_id), with the
    incumbent reproduction hard assert applied before anything else runs."""
    pv = pd.read_csv(PREDICTIONS)
    need = ["GAME_ID", "GAME_DATE_h", "season_h", "season_type_h", "total_true",
            "str_total_cal", "TEAM_ABBREVIATION_h"]
    missing = [c for c in need if c not in pv.columns]
    if missing:
        raise SystemExit(f"predictions_v2.csv missing columns {missing}")
    if len(pv) != N_UNIVERSE:
        raise SystemExit(f"UNIVERSE FAILED: predictions_v2.csv has {len(pv)} rows, "
                         f"registered universe is {N_UNIVERSE}")
    if pv.GAME_ID.duplicated().any():
        raise SystemExit("UNIVERSE FAILED: duplicate GAME_ID in predictions_v2.csv")
    if sorted(pv.season_h.unique()) != TEST_YEARS:
        raise SystemExit(f"UNIVERSE FAILED: seasons {sorted(pv.season_h.unique())} "
                         f"!= registered test seasons {TEST_YEARS}")
    if pv[["total_true", "str_total_cal"]].isna().any().any():
        raise SystemExit("UNIVERSE FAILED: NaN in total_true / str_total_cal")

    # ---- the registered hard assert: incumbent reproduction from the COMMITTED file
    inc_mae = float((pv.str_total_cal - pv.total_true).abs().mean())
    if abs(inc_mae - INCUMBENT_ANCHOR) > ANCHOR_TOL:
        raise SystemExit(
            f"INCUMBENT REPRODUCTION FAILED: pooled total MAE {inc_mae:.6f} vs "
            f"registered anchor {INCUMBENT_ANCHOR} (tol {ANCHOR_TOL}); stopping.")
    log(f"incumbent reproduction certified: pooled total MAE {inc_mae:.6f} "
        f"(anchor {INCUMBENT_ANCHOR} +- {ANCHOR_TOL}) over {len(pv)} games")

    pv = pv.copy()
    pv["date"] = pd.to_datetime(pv.GAME_DATE_h)
    pv["resid"] = pv.total_true - pv.str_total_cal          # incumbent residual
    pv = pv.sort_values(["season_h", "date", "GAME_ID"]).reset_index(drop=True)
    for _, g in pv.groupby("season_h"):
        assert g.date.is_monotonic_increasing, "within-season date sort violated"
    return pv


def attach_franchise_and_coverage(pv: pd.DataFrame) -> tuple[pd.DataFrame, float, int]:
    """Franchise-stable home TEAM_ID for the team-cluster sensitivity CI (16
    abbreviations -> 15 franchises: PHO/PHX are one), plus the coverage
    fraction vs ALL distinct test-season games in channel_base_v2.csv."""
    cb = pd.read_csv(CHANNEL_BASE, usecols=["GAME_ID", "TEAM_ID", "year", "is_home"])
    home = cb[cb.is_home == 1][["GAME_ID", "TEAM_ID"]].drop_duplicates()
    assert not home.GAME_ID.duplicated().any(), "multiple home rows for a game"
    pv = pv.merge(home, on="GAME_ID", how="left", validate="one_to_one")
    assert pv.TEAM_ID.notna().all(), "unmatched franchise id for some game"
    n_franchise = int(pv.TEAM_ID.nunique())
    assert n_franchise == 15, f"expected 15 franchises, got {n_franchise}"
    denom = int(cb[cb.year.isin(TEST_YEARS)].GAME_ID.nunique())
    cov = len(pv) / denom
    log(f"coverage: {len(pv)}/{denom} distinct test-season games = {cov:.4f} "
        f"(identical for challenger and incumbent by construction); "
        f"team sensitivity clustering: {n_franchise} franchises")
    return pv, cov, denom


# ---------------------------------------------------------------------------
# 2. the mechanism — walk-forward within-season residual pools (nothing fit)
# ---------------------------------------------------------------------------

def compute_pools(pv: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Per game g: n_prior = count of same-season games on STRICTLY earlier
    dates; pool_mean = mean incumbent residual over those games (NaN when
    n_prior = 0). K-independent — every K shares these pools.

    Vectorized per season: with rows date-sorted, searchsorted(side='left')
    counts strictly-earlier-dated games, and a shifted cumulative sum yields
    the pool mean. Same-date games share identical (n_prior, pool_mean) — the
    shift is by DATE, not by row."""
    n_prior = np.empty(len(pv), dtype=int)
    pool_mean = np.full(len(pv), np.nan)
    for _, g in pv.groupby("season_h", sort=True):
        idx = g.index.to_numpy()
        dates = g.date.to_numpy()
        res = g.resid.to_numpy(float)
        k = np.searchsorted(dates, dates, side="left")
        csum = np.concatenate([[0.0], np.cumsum(res)])
        pm = np.where(k > 0, csum[k] / np.maximum(k, 1), np.nan)
        n_prior[idx] = k
        pool_mean[idx] = pm
    return n_prior, pool_mean


def challenger_for(pv: pd.DataFrame, n_prior: np.ndarray, pool_mean: np.ndarray,
                   K: int) -> tuple[np.ndarray, np.ndarray]:
    """correction = (n/(n+K)) * pool_mean (0 exactly when n = 0);
    challenger = str_total_cal + correction."""
    weight = n_prior / (n_prior + float(K))
    correction = weight * np.where(n_prior > 0, pool_mean, 0.0)
    assert (correction[n_prior == 0] == 0.0).all(), "opener correction must be exactly 0"
    challenger = pv.str_total_cal.to_numpy() + correction
    return correction, challenger


def structural_asserts(pv: pd.DataFrame, n_prior: np.ndarray, pool_mean: np.ndarray) -> dict:
    """Registered no-leak structure, asserted for ALL 673 games (not sampled):
    (i) same-date games share identical (n_prior, pool_mean) — no same-date
    peeking; (ii) each season's first date has n_prior = 0; (iii) n_prior
    increments only across date boundaries and counts every prior game."""
    df = pv[["season_h", "date"]].copy()
    df["n_prior"], df["pool_mean"] = n_prior, pool_mean
    for (s, d), g in df.groupby(["season_h", "date"]):
        assert g.n_prior.nunique() == 1, f"same-date n_prior differs ({s} {d})"
        pmvals = g.pool_mean.to_numpy()
        assert np.all(np.isnan(pmvals)) or float(np.nanmax(pmvals) - np.nanmin(pmvals)) <= TOL, \
            f"same-date pool_mean differs ({s} {d})"
    n_openers = 0
    for s, g in df.groupby("season_h"):
        first = g[g.date == g.date.min()]
        assert (first.n_prior == 0).all(), f"season {s} opener has n_prior != 0"
        n_openers += len(first)
        # counts: for every row, n_prior == number of season rows strictly earlier
        dates = g.date.to_numpy()
        k = np.array([(dates < d).sum() for d in dates])
        assert (k == g.n_prior.to_numpy()).all(), f"n_prior counting mismatch in {s}"
    log(f"structural asserts PASS over all {len(df)} games: same-date pools "
        f"identical, {n_openers} opener rows at n_prior=0, counts exact")
    return {"n_opener_rows": int(n_openers), "n_games_checked": int(len(df))}


# ---------------------------------------------------------------------------
# 3. walk-forward residual-pool audit (registered: truncate + recompute, >= 15)
# ---------------------------------------------------------------------------

def residual_pool_audit(pv: pd.DataFrame, n_prior: np.ndarray, pool_mean: np.ndarray,
                        correction: np.ndarray, challenger: np.ndarray) -> pd.DataFrame:
    """For sampled games (>= 15; here every season's opener + season-final game
    + 4 random mid-season games per season, fixed seed): TRUNCATE the frame to
    same-season rows strictly before the game's date, recompute n and the pool
    mean INDEPENDENTLY (plain boolean filtering — a different code path from
    the searchsorted/cumsum production computation), re-derive the damped
    correction and the challenger, and require exact agreement."""
    rng = np.random.default_rng(AUDIT_SEED)
    stored = pv.copy()
    stored["n_prior"], stored["pool_mean"] = n_prior, pool_mean
    stored["correction"], stored["challenger"] = correction, challenger

    picks: list[int] = []
    for s, g in stored.groupby("season_h"):
        openers = g.index[g.date == g.date.min()].tolist()
        final = [g.index[g.date.argmax()]]
        mid_pool = [i for i in g.index if i not in set(openers) | set(final)]
        rand = rng.choice(mid_pool, size=min(AUDIT_RANDOM_PER_SEASON, len(mid_pool)),
                          replace=False).tolist()
        picks += openers + rand + final
    picks = sorted(set(picks))
    assert len(picks) >= 15, f"audit sample {len(picks)} < registered minimum 15"

    rows = []
    for i in picks:
        r = stored.loc[i]
        hist = stored[(stored.season_h == r.season_h) & (stored.date < r.date)]
        n_re = int(len(hist))
        pm_re = float(hist.resid.mean()) if n_re > 0 else np.nan
        corr_re = (n_re / (n_re + float(K_REGISTERED))) * (pm_re if n_re > 0 else 0.0)
        chall_re = float(r.str_total_cal) + corr_re
        pm_ok = (np.isnan(pm_re) and np.isnan(r.pool_mean)) or abs(pm_re - r.pool_mean) <= TOL
        diffs = [abs(corr_re - r.correction), abs(chall_re - r.challenger)]
        ok = (n_re == r.n_prior) and pm_ok and max(diffs) <= TOL
        rows.append({
            "game_id": r.GAME_ID, "season": int(r.season_h),
            "date": str(pd.Timestamp(r.date).date()),
            "n_prior_stored": int(r.n_prior), "n_prior_recomputed": n_re,
            "pool_mean_stored": float(r.pool_mean), "pool_mean_recomputed": pm_re,
            "correction_stored": float(r.correction), "correction_recomputed": corr_re,
            "challenger_stored": float(r.challenger), "challenger_recomputed": chall_re,
            "max_abs_diff": float(max(diffs)),
            "role": ("season_opener" if r.n_prior == 0 else
                     "season_final" if r.date == stored[stored.season_h == r.season_h].date.max()
                     else "random_mid_season"),
            "identical": bool(ok),
        })
    audit = pd.DataFrame(rows)
    if not audit.identical.all():
        raise SystemExit(f"RESIDUAL-POOL WALK-FORWARD AUDIT FAILED:\n{audit[~audit.identical]}")
    log(f"residual-pool walk-forward audit PASS: {len(audit)} sampled games "
        f"(all openers + season finals + {AUDIT_RANDOM_PER_SEASON}/season random, "
        f"seed {AUDIT_SEED}), truncate-and-recompute identical "
        f"(max abs diff {audit.max_abs_diff.max():.3g})")
    return audit


# ---------------------------------------------------------------------------
# 4. registered secondaries (recorded, never gated)
# ---------------------------------------------------------------------------

def bias_by_season(pv: pd.DataFrame, challenger: np.ndarray) -> pd.DataFrame:
    """Per-season mean bias (pred - true), challenger vs incumbent, plus the
    preregistered success bar: max |seasonal bias| across test seasons < 2.5."""
    y = pv.total_true.to_numpy()
    ic = pv.str_total_cal.to_numpy()
    seasons = pv.season_h.to_numpy()
    rows = []
    for label, m in [(str(s), seasons == s) for s in TEST_YEARS] + [("pooled", np.ones(len(pv), bool))]:
        rows.append({
            "season": label, "n": int(m.sum()),
            "bias_incumbent": float((ic[m] - y[m]).mean()),
            "bias_challenger": float((challenger[m] - y[m]).mean()),
            "abs_bias_incumbent": float(abs((ic[m] - y[m]).mean())),
            "abs_bias_challenger": float(abs((challenger[m] - y[m]).mean())),
            "mae_incumbent": float(np.abs(ic[m] - y[m]).mean()),
            "mae_challenger": float(np.abs(challenger[m] - y[m]).mean()),
            "delta_mae_pos_better": float(np.abs(ic[m] - y[m]).mean() - np.abs(challenger[m] - y[m]).mean()),
            "bias_bar": BIAS_BAR,
        })
    tbl = pd.DataFrame(rows)
    per = tbl[tbl.season != "pooled"]
    tbl["max_abs_seasonal_bias_challenger"] = float(per.abs_bias_challenger.max())
    tbl["max_abs_seasonal_bias_incumbent"] = float(per.abs_bias_incumbent.max())
    tbl["bias_bar_met_challenger"] = bool(per.abs_bias_challenger.max() < BIAS_BAR)
    return tbl


def k_diagnostic(pv: pd.DataFrame, n_prior: np.ndarray, pool_mean: np.ndarray) -> pd.DataFrame:
    """The same pipeline at K in {5, 30} — registered DIAGNOSTIC ONLY, one
    table, never used for selection. K=15 rows are the registered challenger."""
    y = pv.total_true.to_numpy()
    ic = pv.str_total_cal.to_numpy()
    seasons = pv.season_h.to_numpy()
    rows = []
    for K in sorted(K_DIAGNOSTIC + [K_REGISTERED]):
        corr, chall = challenger_for(pv, n_prior, pool_mean, K)
        role = "REGISTERED" if K == K_REGISTERED else "DIAGNOSTIC ONLY"
        for label, m in [("pooled", np.ones(len(pv), bool))] + [(str(s), seasons == s) for s in TEST_YEARS]:
            rows.append({
                "K": K, "role": role, "season": label, "n": int(m.sum()),
                "mae_challenger": float(np.abs(chall[m] - y[m]).mean()),
                "mae_incumbent": float(np.abs(ic[m] - y[m]).mean()),
                "delta_mae_pos_better": float(np.abs(ic[m] - y[m]).mean() - np.abs(chall[m] - y[m]).mean()),
                "bias_challenger": float((chall[m] - y[m]).mean()),
                "bias_incumbent": float((ic[m] - y[m]).mean()),
                "mean_correction": float(corr[m].mean()),
                "mean_abs_correction": float(np.abs(corr[m]).mean()),
                "max_abs_correction": float(np.abs(corr[m]).max()),
            })
    return pd.DataFrame(rows)


def correction_distribution(pv: pd.DataFrame, n_prior: np.ndarray,
                            correction: np.ndarray) -> pd.DataFrame:
    """Registered secondary: per-game correction magnitude distribution by
    season (the registered K=15 correction)."""
    seasons = pv.season_h.to_numpy()
    rows = []
    for label, m in [(str(s), seasons == s) for s in TEST_YEARS] + [("pooled", np.ones(len(pv), bool))]:
        c = correction[m]
        rows.append({
            "season": label, "n": int(m.sum()),
            "n_zero_correction": int((c == 0.0).sum()),
            "share_positive": float((c > 0).mean()),
            "mean_correction": float(c.mean()), "sd_correction": float(c.std(ddof=1)),
            "min": float(c.min()), "q10": float(np.quantile(c, 0.10)),
            "q25": float(np.quantile(c, 0.25)), "median": float(np.quantile(c, 0.50)),
            "q75": float(np.quantile(c, 0.75)), "q90": float(np.quantile(c, 0.90)),
            "max": float(c.max()),
            "mean_abs_correction": float(np.abs(c).mean()),
            "max_abs_correction": float(np.abs(c).max()),
            "mean_n_prior": float(n_prior[m].mean()), "max_n_prior": int(n_prior[m].max()),
        })
    return pd.DataFrame(rows)


def bookie_context(pv: pd.DataFrame, challenger: np.ndarray) -> pd.DataFrame:
    """Registered context (ungated): the 365-game covered subset vs consensus
    pre-tip bookie totals (2024 has no totals lines on disk)."""
    bk = pd.read_csv(BOOKIE_TOTALS)
    assert not bk.game_id.duplicated().any(), "duplicate game_id in bookie file"
    work = pv[["GAME_ID", "date", "season_h", "total_true", "str_total_cal"]].copy()
    work["challenger"] = challenger
    j = work.merge(bk[["game_id", "consensus_total", "actual_total", "n_books"]],
                   left_on="GAME_ID", right_on="game_id", how="inner", validate="one_to_one")
    assert len(j) == BOOKIE_N, f"expected the registered {BOOKIE_N}-game covered subset, got {len(j)}"
    assert float((j.actual_total - j.total_true).abs().max()) <= TOL, \
        "bookie file truth disagrees with predictions_v2 truth — misjoin"
    bk_mae = float((j.consensus_total - j.total_true).abs().mean())
    assert abs(bk_mae - BOOKIE_ANCHOR) < 1e-3, f"bookie MAE {bk_mae} != registered context {BOOKIE_ANCHOR}"

    rows = []
    for label, g in [("pooled", j)] + [(str(s), g) for s, g in j.groupby("season_h")]:
        eb = (g.consensus_total - g.total_true).abs().to_numpy()
        ec = (g.challenger - g.total_true).abs().to_numpy()
        ei = (g.str_total_cal - g.total_true).abs().to_numpy()
        dates = pd.to_datetime(g.date).dt.normalize().to_numpy()
        ci_ch = eh.cluster_bootstrap_ci(eb - ec, dates, n_boot=2000, seed=SEED)
        ci_inc = eh.cluster_bootstrap_ci(eb - ei, dates, n_boot=2000, seed=SEED)
        rows.append({
            "season": label, "n": len(g),
            "challenger_mae": float(ec.mean()), "incumbent_mae": float(ei.mean()),
            "bookie_mae": float(eb.mean()),
            "challenger_minus_bookie": float(ec.mean() - eb.mean()),
            "incumbent_minus_bookie": float(ei.mean() - eb.mean()),
            "paired_delta_bookie_minus_challenger": float((eb - ec).mean()),
            "delta_ci90_lo": ci_ch["low"], "delta_ci90_hi": ci_ch["high"],
            "incumbent_delta_ci90_lo": ci_inc["low"], "incumbent_delta_ci90_hi": ci_inc["high"],
            "share_challenger_closer_than_bookie": float((ec < eb).mean()),
        })
    log(f"bookie context: {BOOKIE_N} covered games, bookie MAE {bk_mae:.4f} "
        f"(anchor {BOOKIE_ANCHOR})")
    return pd.DataFrame(rows)


def groundwork_undamped_reference() -> dict:
    """Context from the COMMITTED groundwork artifact (nothing recomputed
    through this experiment's pipeline): the exploratory UNdamped correction
    (K=0 limit) — the registered motivation for damping."""
    g = pd.read_csv(GROUNDWORK_UNDAMPED)
    out = {"pooled_mae": float((g.adj_pred - g.total_true).abs().mean()),
           "pooled_bias": float((g.adj_pred - g.total_true).mean())}
    for s, gg in g.groupby("season"):
        out[f"mae_{s}"] = float((gg.adj_pred - gg.total_true).abs().mean())
        out[f"bias_{s}"] = float((gg.adj_pred - gg.total_true).mean())
    return out


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def write_report(outdir: Path, ctx: dict) -> None:
    r, reg = ctx["result"], ctx["registration"]
    per = {p["season"]: p for p in r.per_season}
    bias = ctx["bias_tbl"].set_index("season")
    kd = ctx["k_tbl"]
    cd = ctx["corr_tbl"].set_index("season")
    bk = ctx["bookie_tbl"].set_index("season")
    und = ctx["undamped"]
    inv = ctx["invariance"]
    bar_met = bool(bias["bias_bar_met_challenger"].iloc[0])
    max_bias_ch = float(bias["max_abs_seasonal_bias_challenger"].iloc[0])
    max_bias_inc = float(bias["max_abs_seasonal_bias_incumbent"].iloc[0])
    bar_gap = ("" if bar_met else
               f", and {max_bias_ch - BIAS_BAR:.2f} points remain above the bar")

    def prow(s):
        p = per[str(s)]
        return (f"| {s} | {p['n']} | {p['metric_challenger']:.4f} | "
                f"{p['metric_incumbent']:.4f} | {p['delta']:+.4f} |")

    def brow(s):
        b = bias.loc[str(s)]
        return (f"| {s} | {int(b.n)} | {b.bias_incumbent:+.4f} | {b.bias_challenger:+.4f} | "
                f"{b.abs_bias_challenger - b.abs_bias_incumbent:+.4f} | "
                f"{'yes' if b.abs_bias_challenger < BIAS_BAR else 'NO'} |")

    krows = []
    for K in sorted(set(kd.K)):
        sub = kd[kd.K == K].set_index("season")
        role = sub.role.iloc[0]
        krows.append(
            f"| {K}{' (registered)' if role == 'REGISTERED' else ''} | "
            f"{sub.loc['pooled', 'mae_challenger']:.4f} | "
            f"{sub.loc['pooled', 'delta_mae_pos_better']:+.4f} | "
            f"{sub.loc['2024', 'delta_mae_pos_better']:+.4f} | "
            f"{sub.loc['2025', 'delta_mae_pos_better']:+.4f} | "
            f"{sub.loc['2026', 'delta_mae_pos_better']:+.4f} | "
            f"{sub.loc['2026', 'bias_challenger']:+.4f} | "
            f"{sub.loc['pooled', 'mean_abs_correction']:.4f} |")

    md = f"""# totals_online_correction_v1 — Damped Online Within-Season Bias Correction ({r.verdict})

*{ctx['run_time']} · registered experiment `{EXPERIMENT_ID}` (registered
{reg['registered_at']}, regime {reg['regime']}, primary metric `{reg['primary_metric']}`,
incumbent `{reg['incumbent_id']}`) · run mode **{ctx['mode'].upper()}** — {ctx['mode_note']}
· code `totals_online.py` (repo root) · predecessors `experiments/totals_head/REPORT.md`
(train-frozen coefficients FAIL) and `experiments/totals_groundwork/REPORT.md` §4.4
(UNdamped online correction, exploratory, pooled-negative).*

## Verdict

**{r.verdict}{' — promote' if r.promote else ''}.** Challenger pooled game-total MAE **{r.metric_challenger:.4f}** vs
incumbent **{r.metric_incumbent:.4f}** on the identical {r.n_games} test games (pooled
improvement **{r.pooled_improvement:+.4f}**, 90% date-clustered bootstrap CI
[{r.ci_low:+.4f}, {r.ci_high:+.4f}], {r.n_clusters} date clusters; team-clustered
sensitivity [{r.ci_sensitivity_team[0]:+.4f}, {r.ci_sensitivity_team[1]:+.4f}],
{r.ci_sensitivity_team[2]} franchises).

| Gate (registered thresholds) | Result |
|---|---|
| 1. Pooled improvement >= {r.thresholds['min_improvement']} | {'PASS' if r.gates['gate1_pooled_improvement'] else 'FAIL'} ({r.pooled_improvement:+.4f}) |
| 2. 90% CI excludes harm > {r.thresholds['harm_ci_bound']} | {'PASS' if r.gates['gate2_ci_excludes_harm'] else 'FAIL'} (CI low {r.ci_low:+.4f}) |
| 3. No season degrades > {r.thresholds['per_season_tolerance']} | {'PASS' if r.gates['gate3_per_season_non_inferiority'] else 'FAIL'} (worst {r.gate_details['gate3_per_season_non_inferiority']['worst_delta']:+.4f}, {r.gate_details['gate3_per_season_non_inferiority']['worst_season']}) |
| 4. Joint forecast: margin invariance (structural) | {'PASS' if r.gates['gate4_joint_forecast'] else 'FAIL'} |
| 5. Coverage unchanged | {'PASS' if r.gates['gate5_coverage'] else 'FAIL'} ({r.gate_details['gate5_coverage']['coverage_challenger']:.4f} both models) |

### Per-season game-total MAE

| Season | n | Challenger | Incumbent | Delta (+ = better) |
|---|---|---|---|---|
{prow(2024)}
{prow(2025)}
{prow(2026)}
| pooled | {r.n_games} | {r.metric_challenger:.4f} | {r.metric_incumbent:.4f} | {r.pooled_improvement:+.4f} |

## The mechanism (nothing fitted, nothing tuned)

**challenger(g) = str_total_cal(g) + (n/(n+{K_REGISTERED})) * mean(same-season incumbent
residuals strictly before g's date)** — K = {K_REGISTERED} fixed a priori in the
registration; residual = total_true - str_total_cal; season openers (n = 0) get
correction = 0 exactly (registered no-info state). Same-date games never see each
other's residuals (the pool cut is strictly by DATE). Input universe: the committed
`experiments/channel_reval/predictions_v2.csv` — {N_UNIVERSE} games, seasons
{TEST_YEARS[0]}-{TEST_YEARS[-1]}; {ctx['structure']['n_opener_rows']} opener rows.
This script fits zero parameters: the only inputs to any challenger value are the
incumbent's own committed predictions and outcomes from strictly earlier dates.

## Seasonal bias — the registered success bar (the point of this experiment)

Preregistered bar: **max |seasonal mean bias| across test seasons < {BIAS_BAR}** points
(bias = mean(pred - total_true); incumbent 2026: -4.97).

| Season | n | Incumbent bias | Challenger bias | Delta abs bias (- = shrunk) | < {BIAS_BAR}? |
|---|---|---|---|---|---|
{brow(2024)}
{brow(2025)}
{brow(2026)}

**The bar is {'MET' if bar_met else 'NOT MET'}: max |seasonal bias| = {max_bias_ch:.4f}
(challenger) vs {max_bias_inc:.4f} (incumbent).** The 2026 bias moves
{bias.loc['2026', 'bias_incumbent']:+.4f} -> {bias.loc['2026', 'bias_challenger']:+.4f}
— about {abs(bias.loc['2026', 'bias_incumbent'] - bias.loc['2026', 'bias_challenger']) / abs(bias.loc['2026', 'bias_incumbent']):.0%} of the level shift is recovered{bar_gap}. {ctx['bias_narrative']}

## Correction trace (registered secondary)

Per-game K={K_REGISTERED} correction distribution by season (`correction_distribution.csv`):

| Season | n | zero (openers) | mean | q25 | median | q75 | max abs | mean n_prior |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {s} | {int(cd.loc[s, 'n'])} | {int(cd.loc[s, 'n_zero_correction'])} | "
        f"{cd.loc[s, 'mean_correction']:+.4f} | {cd.loc[s, 'q25']:+.4f} | "
        f"{cd.loc[s, 'median']:+.4f} | {cd.loc[s, 'q75']:+.4f} | "
        f"{cd.loc[s, 'max_abs_correction']:.4f} | {cd.loc[s, 'mean_n_prior']:.1f} |"
        for s in ["2024", "2025", "2026", "pooled"]) + f"""

## K sensitivity — DIAGNOSTIC ONLY (registered as such; never used for selection)

The identical pipeline at K in {{{', '.join(str(k) for k in sorted(set(kd.K)))}}}; K={K_REGISTERED} is the registered
constant (`k_diagnostic.csv`):

| K | Pooled MAE | Pooled delta | 2024 delta | 2025 delta | 2026 delta | 2026 bias | mean abs corr |
|---|---|---|---|---|---|---|---|
""" + "\n".join(krows) + f"""

{ctx['k_narrative']}

## Bookie context (ungated, registered as context rows)

Consensus pre-tip totals exist for {int(bk.loc['pooled', 'n'])} of the {N_UNIVERSE} test games
(2025 from Jul 5 + 2026; **2024 has no totals lines on disk**). Bookie MAE
**{bk.loc['pooled', 'bookie_mae']:.4f}** (verified vs the registered {BOOKIE_ANCHOR}).

| Season | n | Challenger | Incumbent | Bookie | Chall - bookie | 90% CI paired delta* | Chall closer |
|---|---|---|---|---|---|---|---|
""" + "\n".join(
        f"| {s} | {int(row.n)} | {row.challenger_mae:.4f} | {row.incumbent_mae:.4f} | "
        f"{row.bookie_mae:.4f} | {row.challenger_minus_bookie:+.4f} | "
        f"[{row.delta_ci90_lo:+.3f}, {row.delta_ci90_hi:+.3f}] | "
        f"{row.share_challenger_closer_than_bookie:.1%} |"
        for s, row in bk.iterrows()) + f"""

*delta = |bookie err| - |challenger err|, positive = challenger better; date-clustered
bootstrap (n_boot 2000, seed {SEED}). Context only — never gated; no betting claim.

## Audits (all PASS — the run stops on any failure)

1. **Incumbent reproduction (registered hard assert):** pooled total MAE of the
   committed `predictions_v2.csv` = **{ctx['repro']['incumbent_pooled_total_mae']:.6f}**,
   within 1e-3 of the registered {INCUMBENT_ANCHOR}, over exactly {N_UNIVERSE} games
   (universe asserted: row count, uniqueness, seasons, no NaN).
2. **Walk-forward residual-pool audit (registered):** {len(ctx['audit'])} sampled games
   (every season opener + every season-final game + {AUDIT_RANDOM_PER_SEASON}/season random,
   seed {AUDIT_SEED}) — all same-season games at/after each game's date TRUNCATED, n and
   pool mean recomputed independently (plain filtering, separate code path), correction and
   challenger re-derived: identical every time (max abs diff
   {ctx['audit'].max_abs_diff.max():.3g}; `residual_pool_audit.csv`). Structural asserts
   over ALL {ctx['structure']['n_games_checked']} games (not sampled): same-date games share
   identical pools (no same-date peeking), every season's first date has n = 0, and n_prior
   counts exactly the strictly-earlier-dated games.
3. **Margin invariance (registered, structural):** the challenger writes no margin
   column anywhere — output columns scanned for 'margin': {inv['margin_columns_in_outputs']};
   `predictions_v2.csv` byte-identical before/after (sha256 {inv['pred_sha256_before'][:12]}...,
   match={inv['pred_file_unchanged']}). The challenger shifts the TOTAL only; no margin
   forecast is produced or altered.
4. **K sensitivity (registered DIAGNOSTIC ONLY):** computed at K in {{5, 30}} alongside the
   registered K=15, reported above and in `k_diagnostic.csv`, and used for nothing else.
   No K was selected by any results-driven procedure in this script.

## Files

`game_level.csv` ({N_UNIVERSE} rows: game_id, date, season, season_type, total_true,
incumbent, n_prior, prior_pool_mean, correction, challenger, abs errors,
bookie_consensus_total) · `bias_by_season.csv` · `k_diagnostic.csv` ·
`correction_distribution.csv` · `residual_pool_audit.csv` · `bookie_context.csv` ·
`gate_verdict.json` · `run_summary.json`.
"""
    (outdir / "REPORT.md").write_text(md, encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode_g = ap.add_mutually_exclusive_group(required=True)
    mode_g.add_argument("--smoke", action="store_true",
                        help="evaluate against a scratch COPY of the registry "
                             "(tempdir) passed as registry_path, artifacts to a "
                             "scratch outdir (or --outdir); the real ledger is "
                             "never touched")
    mode_g.add_argument("--real", action="store_true",
                        help="record the evaluation on the REAL ledger, artifacts "
                             "-> experiments/totals_online/ (orchestrator only)")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)
    mode = "smoke" if args.smoke else "real"

    registry_path = None
    scratch_note = None
    outdir = args.outdir or OUTDIR
    if args.smoke:
        scratch = Path(tempfile.mkdtemp(prefix="totals_online_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        scratch_note = str(registry_path)
        outdir = args.outdir or (scratch / "out")
        log(f"SMOKE mode: scratch registry copy at {registry_path}")
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log(f"{mode.upper()} run at {run_time} -> {outdir}")

    # registration echo (read-only, from the real ledger) -----------------------
    reg = eh.get_registration(EXPERIMENT_ID)
    assert reg["incumbent_id"] == INCUMBENT_ID, reg["incumbent_id"]
    assert reg["primary_metric"] == "total_mae", reg["primary_metric"]
    for k, v in EXPECTED_THRESHOLDS.items():
        assert abs(float(reg["thresholds"][k]) - v) < 1e-12, (k, reg["thresholds"])
    log(f"registration OK: {EXPERIMENT_ID} registered {reg['registered_at']} "
        f"(regime {reg['regime']}, primary {reg['primary_metric']}, "
        f"thresholds {reg['thresholds']})")

    pred_sha_before = sha256_of(PREDICTIONS)

    # 1. frozen universe + incumbent reproduction -------------------------------
    pv = load_universe()
    pv, cov, cov_denom = attach_franchise_and_coverage(pv)
    repro = {"incumbent_pooled_total_mae": float((pv.str_total_cal - pv.total_true).abs().mean()),
             "anchor": INCUMBENT_ANCHOR, "anchor_tol": ANCHOR_TOL,
             "n_games": int(len(pv)),
             "per_season_n": {int(k): int(v) for k, v in
                              pv.season_h.value_counts().sort_index().items()}}

    # 2. the mechanism ----------------------------------------------------------
    n_prior, pool_mean = compute_pools(pv)
    structure = structural_asserts(pv, n_prior, pool_mean)
    correction, challenger = challenger_for(pv, n_prior, pool_mean, K_REGISTERED)
    log(f"K={K_REGISTERED} challenger built: mean correction "
        f"{correction.mean():+.4f}, mean |correction| {np.abs(correction).mean():.4f}, "
        f"max |correction| {np.abs(correction).max():.4f}, "
        f"{int((n_prior == 0).sum())} openers at correction 0")

    # 3. registered audit -------------------------------------------------------
    audit = residual_pool_audit(pv, n_prior, pool_mean, correction, challenger)

    # 4. margin invariance (structural) -----------------------------------------
    pred_sha_mid = sha256_of(PREDICTIONS)
    invariance = {
        "pred_sha256_before": pred_sha_before,
        "pred_file_unchanged": bool(pred_sha_mid == pred_sha_before),
        "margin_columns_in_outputs": 0,       # asserted below after outputs exist
        "note": ("structural: the challenger adds a scalar correction to the "
                 "TOTAL only; no margin forecast is produced or altered "
                 "anywhere in this script"),
    }
    assert invariance["pred_file_unchanged"]

    def joint_check():
        ok = invariance["pred_file_unchanged"]
        return ok, {
            "mode": "structural margin invariance (registered: asserted, not fitted)",
            "predictions_v2_sha256_unchanged": invariance["pred_file_unchanged"],
            "challenger_margin_columns_written": 0,
        }

    # 5. the registered gated comparison ----------------------------------------
    ch_frame = pd.DataFrame({
        "game_id": pv.GAME_ID.to_numpy(),
        "game_date": pv.date.to_numpy(),
        "season": pv.season_h.to_numpy(),
        "y_true": pv.total_true.to_numpy(),
        "y_pred": challenger,
        "home_team": pv.TEAM_ID.to_numpy(),   # franchise id (PHO/PHX-stable)
    })
    inc_frame = pd.DataFrame({
        "game_id": pv.GAME_ID.to_numpy(),
        "y_true": pv.total_true.to_numpy(),
        "y_pred": pv.str_total_cal.to_numpy(),
    })
    result = eh.compare_to_incumbent(
        ch_frame, inc_frame,
        experiment_id=EXPERIMENT_ID,
        registry_path=registry_path,
        loss="absolute",
        cluster="date",
        n_boot=2000,
        seed=SEED,
        joint_check=joint_check,
        coverage=(cov, cov),
    )
    log(f"VERDICT: {result.verdict} (promote={result.promote}); challenger "
        f"{result.metric_challenger:.4f} vs incumbent {result.metric_incumbent:.4f}; "
        f"pooled improvement {result.pooled_improvement:+.4f} "
        f"[90% CI {result.ci_low:+.4f}, {result.ci_high:+.4f}]; "
        f"failed gates: {result.failed_gates}")

    # 6. registered secondaries -------------------------------------------------
    bias_tbl = bias_by_season(pv, challenger)
    k_tbl = k_diagnostic(pv, n_prior, pool_mean)
    corr_tbl = correction_distribution(pv, n_prior, correction)
    bookie_tbl = bookie_context(pv, challenger)
    undamped = groundwork_undamped_reference()

    bar_met = bool(bias_tbl["bias_bar_met_challenger"].iloc[0])
    max_bias = float(bias_tbl["max_abs_seasonal_bias_challenger"].iloc[0])
    b26_inc = float(bias_tbl.set_index("season").loc["2026", "bias_incumbent"])
    b26_ch = float(bias_tbl.set_index("season").loc["2026", "bias_challenger"])
    log(f"seasonal-bias bar (<{BIAS_BAR}): {'MET' if bar_met else 'NOT MET'} — "
        f"max |seasonal bias| {max_bias:.4f}; 2026 {b26_inc:+.4f} -> {b26_ch:+.4f}")

    # narratives for the report (every number computed above or right here) -----
    # Rigorous family bound: every weight n/(n+K) lies in [0, 1] whatever K is,
    # so the 2026 mean correction can never exceed the mean POSITIVE part of the
    # residual-pool means — an upper bound on bias recovery over ALL K in [0, inf].
    m26 = pv.season_h.to_numpy() == 2026
    sup_corr_26 = float(np.maximum(
        np.where(n_prior[m26] > 0, pool_mean[m26], 0.0), 0.0).mean())
    best_bias_26 = b26_inc + sup_corr_26
    kd26 = k_tbl[k_tbl.season == "2026"].set_index("K").bias_challenger
    bias_narrative = (
        "The mechanism cannot reach the bar on this data — not at K=15 and not at "
        "any other damping constant: the correction is estimated from the same "
        "season's own earlier games, so it lags the level shift it chases. "
        f"Observed 2026 bias across the family: {undamped['bias_2026']:+.4f} at "
        "K=0 (the committed groundwork UNdamped reference, which was also "
        f"pooled-NEGATIVE at {undamped['pooled_mae']:.4f} MAE), "
        f"{kd26.loc[5]:+.4f} / {kd26.loc[15]:+.4f} / {kd26.loc[30]:+.4f} at "
        f"K=5/15/30, {b26_inc:+.4f} at K=inf (the incumbent). A bound closes the "
        "family for good: every weight n/(n+K) lies in [0, 1], so the 2026 mean "
        "correction is at most the mean positive part of the residual-pool means "
        f"= {sup_corr_26:.4f} points — best conceivable 2026 bias "
        f"{best_bias_26:+.4f}, still outside the {BIAS_BAR} bar, for EVERY K in "
        "[0, inf]."
        if not bar_met else
        "The damped correction brings every test season inside the preregistered "
        "bar."
    )
    kd_p = k_tbl[k_tbl.season == "pooled"].set_index("K").sort_index()
    deltas = kd_p.delta_mae_pos_better
    mono = ("monotone increasing in K" if deltas.is_monotonic_increasing else
            "monotone decreasing in K" if deltas.is_monotonic_decreasing else
            "not monotone in K")
    kd_26 = k_tbl[k_tbl.season == "2026"].set_index("K").sort_index()
    bias26_spread = float(kd_26.bias_challenger.max() - kd_26.bias_challenger.min())
    best_delta = float(deltas.max())
    min_impr = float(reg["thresholds"]["min_improvement"])
    if best_delta < min_impr:
        k_close = (f"No K in the diagnostic grid comes near the registered "
                   f"+{min_impr} gate (best delta {best_delta:+.4f}): the "
                   f"{'FAIL is the family, not the constant' if result.verdict == 'FAIL' else 'result does not hinge on the constant'}.")
    else:
        k_close = (f"A diagnostic K reaches {best_delta:+.4f} (>= the registered "
                   f"+{min_impr}), but K is registered at {K_REGISTERED} and "
                   "diagnostics are never used for selection.")
    k_narrative = (
        f"Pooled delta is {mono} over the grid "
        f"({', '.join(f'K={k}: {deltas.loc[k]:+.4f}' for k in deltas.index)}): "
        "heavier damping (larger K, smaller corrections) tracks the incumbent more "
        "closely and bleeds less MAE in 2024/2025, while the 2026 bias recovery is "
        f"nearly flat in K (spread {bias26_spread:.4f} points across the grid — "
        "full precision in k_diagnostic.csv). " + k_close + " DIAGNOSTIC ONLY — "
        "nothing here was used to select anything.")

    # 7. outputs ----------------------------------------------------------------
    glt = pd.DataFrame({
        "game_id": pv.GAME_ID.to_numpy(),
        "date": pv.date.dt.date,
        "season": pv.season_h.to_numpy(),
        "season_type": pv.season_type_h.to_numpy(),
        "total_true": pv.total_true.to_numpy(),
        "incumbent": pv.str_total_cal.to_numpy(),
        "n_prior": n_prior,
        "prior_pool_mean": pool_mean,          # NaN on openers: explicit no-info state
        "correction": correction,
        "challenger": challenger,
        "abs_err_incumbent": np.abs(pv.str_total_cal.to_numpy() - pv.total_true.to_numpy()),
        "abs_err_challenger": np.abs(challenger - pv.total_true.to_numpy()),
    })
    bk = pd.read_csv(BOOKIE_TOTALS)
    glt = glt.merge(bk[["game_id", "consensus_total"]].rename(
        columns={"consensus_total": "bookie_consensus_total"}),
        on="game_id", how="left", validate="one_to_one")

    frames = {"game_level.csv": glt, "bias_by_season.csv": bias_tbl,
              "k_diagnostic.csv": k_tbl, "correction_distribution.csv": corr_tbl,
              "residual_pool_audit.csv": audit, "bookie_context.csv": bookie_tbl}
    n_margin_cols = sum("margin" in c.lower() for f in frames.values() for c in f.columns)
    invariance["margin_columns_in_outputs"] = n_margin_cols
    assert n_margin_cols == 0, "margin column leaked into an output file"
    for name, frame in frames.items():
        frame.to_csv(outdir / name, index=False)

    with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)

    pred_sha_after = sha256_of(PREDICTIONS)
    assert pred_sha_after == pred_sha_before, "predictions_v2.csv changed during the run"

    summary = {
        "experiment_id": EXPERIMENT_ID, "mode": mode, "run_time": run_time,
        "scratch_registry": scratch_note,
        "registration": {k: reg[k] for k in
                         ("experiment_id", "registered_at", "incumbent_id",
                          "primary_metric", "thresholds", "regime")},
        "reproduction": repro,
        "mechanism": {
            "formula": f"challenger = str_total_cal + (n/(n+{K_REGISTERED})) * "
                       "mean(same-season incumbent residuals strictly before the game date)",
            "K_registered": K_REGISTERED, "K_diagnostic_only": K_DIAGNOSTIC,
            "fitted_parameters": 0, "tuned_parameters": 0,
            "n_opener_rows_correction_zero": structure["n_opener_rows"],
            "mean_correction": float(correction.mean()),
            "mean_abs_correction": float(np.abs(correction).mean()),
            "max_abs_correction": float(np.abs(correction).max()),
        },
        "coverage": {"n_predicted": int(len(pv)), "n_test_season_games": cov_denom,
                     "fraction_both_models": cov},
        "seasonal_bias_bar": {
            "bar": BIAS_BAR, "met": bar_met,
            "max_abs_seasonal_bias_challenger": max_bias,
            "max_abs_seasonal_bias_incumbent": float(
                bias_tbl["max_abs_seasonal_bias_incumbent"].iloc[0]),
            "family_bound_2026": {
                "sup_over_all_K_mean_correction": sup_corr_26,
                "best_conceivable_2026_bias_any_K": best_bias_26,
                "note": "weights n/(n+K) lie in [0,1] for every K, so the 2026 "
                        "mean correction is bounded by the mean positive part "
                        "of the residual-pool means",
            },
            "table": bias_tbl.to_dict(orient="records"),
        },
        "k_diagnostic_only": k_tbl.to_dict(orient="records"),
        "correction_distribution": corr_tbl.to_dict(orient="records"),
        "bookie_context": bookie_tbl.to_dict(orient="records"),
        "groundwork_undamped_reference": undamped,
        "audits": {
            "incumbent_reproduction": repro,
            "residual_pool_walkforward": {
                "n_sampled": int(len(audit)), "all_identical": True,
                "max_abs_diff": float(audit.max_abs_diff.max()),
                "sampling": f"all season openers + all season finals + "
                            f"{AUDIT_RANDOM_PER_SEASON}/season random, seed {AUDIT_SEED}",
            },
            "structural_full_universe": structure,
            "margin_invariance": invariance | {"pred_sha256_after": pred_sha_after},
        },
        "gate_verdict": result.to_dict(),
    }
    with open(outdir / "run_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, default=str)

    write_report(outdir, {
        "result": result, "registration": reg, "mode": mode,
        "mode_note": ("evaluated against a scratch registry copy; the real ledger "
                      "is untouched — the ledgered evaluation is the "
                      "orchestrator's --real run" if mode == "smoke"
                      else "recorded on the real ledger"),
        "run_time": run_time, "repro": repro, "structure": structure,
        "audit": audit, "invariance": invariance,
        "bias_tbl": bias_tbl, "k_tbl": k_tbl, "corr_tbl": corr_tbl,
        "bookie_tbl": bookie_tbl, "undamped": undamped,
        "bias_narrative": bias_narrative, "k_narrative": k_narrative,
    })
    log(f"artifacts written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
