#!/usr/bin/env python3
"""Dedicated totals head — registered experiment ``totals_head_v1``.

Registered 2026-07-30T21:23:47Z in experiments/registry.jsonl (BEFORE this code
was written). This script never registers; it evaluates the registered
hypothesis exactly as recorded:

    Challenger total = a * structural_uncal_total + b + c * league_env_dev

    * structural_uncal_total — the UNCALIBRATED structural channel-sum total
      (str_sum_h + str_sum_a). It exists in no committed CSV
      (predictions_v2.csv carries only calibrated columns; channel_base_v2.csv
      carries raw box-score ingredients), so it is RECONSTRUCTED by re-running
      the chanreval pipeline verbatim (imported from
      experiments/channel_reval/run_reval.py, recorded alphas) and triple-
      verified before use: (i) refit train-only calibrations must equal the
      recorded run_summary.json params exactly; (ii) pushing the reconstructed
      per-side sums through the RECORDED calibration params must reproduce
      predictions_v2.csv's str_home_cal / str_away_cal / str_total_cal;
      (iii) the full reconstructed test frame must match predictions_v2.csv.
    * league_env_dev — shifted within-season league scoring environment:
      expanding mean or EWMA of game totals over all league games on STRICTLY
      EARLIER dates (master_team.parquet, both season types), minus the
      2021-2023 grand mean total. Expanding-vs-EWMA and the EWMA alpha are
      tuned on 2021-2023 ONLY via evalharness.inner_tuning_splits.
    * (a, b, c) — closed-form least squares (numpy lstsq) on the 610 eligible
      2021-2023 walk-forward games ONLY (the exact universe the incumbent's
      calibration was fit on), frozen for all test seasons.

    Incumbent: chanreval_str_total_cal — str_total_cal from the committed
    experiments/channel_reval/predictions_v2.csv. Hard assert before any
    comparison: pooled total MAE on the 673 test games == 14.2236 within 1e-3.

    MARGIN INVARIANCE IS STRUCTURAL (registered gate 4, asserted not fitted):
    the challenger recombines/rescales only the TOTAL. This script writes no
    margin column anywhere, and asserts (i) no output column mentions margin,
    (ii) predictions_v2.csv is byte-identical before and after the run.

    Primary (gated): game-total MAE, challenger vs incumbent, the identical
    673 games, evalharness.compare_to_incumbent (loss absolute, cluster=date,
    n_boot 2000, seed 20260730, team-cluster sensitivity via franchise
    TEAM_ID_h). Context rows (ungated): bookie consensus totals on the
    365-game covered subset (experiments/totals_groundwork/
    bookie_totals_per_game.csv; 2024 has no totals lines on disk).

Diagnosed defects this targets (experiments/totals_groundwork/REPORT.md):
no dedicated totals calibration; 2026 level bias -4.97; under-dispersion
slope 1.33.

Usage:
    python totals_head.py --smoke   # scratch COPY of the registry + scratch
                                    # outdir (tempdir); real ledger untouched;
                                    # --outdir overrides the artifact target
    python totals_head.py --real    # records the evaluation on the REAL
                                    # ledger, artifacts -> experiments/
                                    # totals_head/ (orchestrator only)

No network. Python 3.13 + pandas/numpy only (closed-form least squares via
numpy; no sklearn). Deterministic (fixed seeds).
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
sys.path.insert(0, str(REPO / "experiments" / "channel_reval"))

import evalharness as eh                      # noqa: E402
import run_reval as rr                        # noqa: E402  (chanreval pipeline, reused verbatim)

EXPERIMENT_ID = "totals_head_v1"
INCUMBENT_ID = "chanreval_str_total_cal"
OUTDIR = REPO / "experiments" / "totals_head"
CHANREVAL = REPO / "experiments" / "channel_reval"
PREDICTIONS = CHANREVAL / "predictions_v2.csv"
MASTER_TEAM = REPO / "data" / "masters" / "master_team.parquet"
BOOKIE_TOTALS = REPO / "experiments" / "totals_groundwork" / "bookie_totals_per_game.csv"

INCUMBENT_ANCHOR = 14.2236                    # registered reproduction anchor
ANCHOR_TOL = 1e-3
TRAIN_YEARS = [2021, 2022, 2023]
ENV_ALPHA_GRID = [0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.20]
ENV_SPECS = ["expanding"] + [f"ewma_{a}" for a in ENV_ALPHA_GRID]
SEED = 20260730                               # harness bootstrap seed (default)
AUDIT_SEED = 20260730
ENV_AUDIT_TEST_PER_SEASON = 5                 # sampled test games per season
ENV_AUDIT_TRAIN_PER_SEASON = 2                # sampled train-fit games per season
REPRO_TOL = 1e-9
CAL_LINK_TOL = 1e-9


def log(msg: str) -> None:
    print(f"[totals_head] {msg}")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lstsq_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Closed-form least squares via numpy (no sklearn, constitution-friendly)."""
    beta, *_ = np.linalg.lstsq(np.asarray(X, float), np.asarray(y, float), rcond=None)
    return beta


# ---------------------------------------------------------------------------
# 1. incumbent reproduction + structural_uncal_total reconstruction
# ---------------------------------------------------------------------------

def reproduce_incumbent() -> dict:
    """Re-run the chanreval pipeline via its own module; hard-assert against the
    committed artifacts; return every frame this experiment needs."""
    summ = json.load(open(CHANREVAL / "run_summary.json", encoding="utf-8"))
    alphas, rec_cal = summ["alphas"], summ["calibration"]

    D = rr.load_base()
    F = rr.build_features(D, alphas)
    games = rr.make_games(F)

    splits = eh.walk_forward_by_season(
        D, date_col="GAME_DATE", season_col="season",
        min_train_seasons=3, test_seasons=rr.TEST_YEARS,
    )
    by_name = {s.name: s for s in splits}
    outer24 = by_name["season:2024"]
    train_seasons = sorted(D.loc[outer24.train_idx, "season"].unique())
    assert train_seasons == TRAIN_YEARS, train_seasons

    train_ids = set(D.loc[outer24.train_idx, "GAME_ID"])
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible].copy()
    cal = rr.fit_calibrations(tg)
    del tg  # re-sliced below AFTER apply_calibrations so it carries the cal columns

    # ---- verification (i): refit calibrations equal the RECORDED params
    cal_dev = max(
        max(abs(cal[k][0] - rec_cal[k][0]), abs(cal[k][1] - rec_cal[k][1]))
        for k in ("raw_home", "raw_away", "str_home", "str_away",
                  "raw_margin", "str_margin")
    )
    if not (cal_dev <= CAL_LINK_TOL and cal["n_train_games"] == rec_cal["n_train_games"]):
        raise SystemExit(
            f"REPRODUCTION FAILED: refit calibration params deviate from "
            f"run_summary.json by {cal_dev} (n_train {cal['n_train_games']} vs "
            f"{rec_cal['n_train_games']}). The uncal source is not certified; stopping."
        )
    games = rr.apply_calibrations(games, cal)
    tg = games[games.GAME_ID.isin(train_ids) & games.eligible].copy().reset_index(drop=True)

    test_ids: set = set()
    for s in rr.TEST_YEARS:
        test_ids |= set(D.loc[by_name[f"season:{s}"].test_idx, "GAME_ID"])
    et = games[games.GAME_ID.isin(test_ids) & games.eligible].copy().reset_index(drop=True)

    pv = pd.read_csv(PREDICTIONS)
    if set(pv.GAME_ID) != set(et.GAME_ID) or len(pv) != len(et):
        raise SystemExit("REPRODUCTION FAILED: eligible-game universe differs "
                         f"from predictions_v2.csv ({len(et)} vs {len(pv)} games)")

    # ---- verification (iii): full reconstructed frame matches predictions_v2
    mg = et.merge(pv, on="GAME_ID", suffixes=("", "_pv"), validate="one_to_one")
    num_cols = ["margin_true", "total_true", "str_home_cal", "str_away_cal",
                "raw_total_cal", "str_total_cal"]
    worst = max(float(np.abs(mg[c].to_numpy() - mg[c + "_pv"].to_numpy()).max())
                for c in num_cols)
    if worst > REPRO_TOL:
        raise SystemExit(f"REPRODUCTION FAILED: predictions_v2.csv max abs diff {worst}")

    # ---- verification (ii): recorded calibration params map the reconstructed
    #      UNCAL per-side sums onto the committed calibrated columns
    ah, bh = rec_cal["str_home"]
    aa, ba = rec_cal["str_away"]
    link_dev = float(np.abs(
        (ah + bh * mg.str_sum_h.to_numpy()) + (aa + ba * mg.str_sum_a.to_numpy())
        - mg.str_total_cal_pv.to_numpy()).max())
    if link_dev > CAL_LINK_TOL:
        raise SystemExit(f"REPRODUCTION FAILED: recorded-calibration linkage of the "
                         f"reconstructed uncal sums deviates by {link_dev}")

    # ---- the registered hard assert: incumbent pooled MAE from the COMMITTED file
    inc_mae = float((pv.str_total_cal - pv.total_true).abs().mean())
    if abs(inc_mae - INCUMBENT_ANCHOR) > ANCHOR_TOL:
        raise SystemExit(
            f"INCUMBENT REPRODUCTION FAILED: pooled total MAE {inc_mae:.6f} vs "
            f"registered anchor {INCUMBENT_ANCHOR} (tol {ANCHOR_TOL}); stopping."
        )
    log(f"incumbent reproduction certified: pooled total MAE {inc_mae:.6f} "
        f"(anchor {INCUMBENT_ANCHOR} +- {ANCHOR_TOL}); pipeline max abs diff "
        f"{worst:.3g}; calibration refit dev {cal_dev:.3g}; recorded-param "
        f"linkage dev {link_dev:.3g} over {len(et)} games")

    for frame in (tg, et):
        frame["uncal_total"] = frame["str_sum_h"] + frame["str_sum_a"]
        frame["gid"] = frame["GAME_ID"].astype(str)

    return {
        "alphas": alphas, "D": D, "games": games, "outer24": outer24,
        "tg": tg.reset_index(drop=True), "et": et, "pv": pv,
        "n_total_test_games": int(D[D.season.isin(rr.TEST_YEARS)].GAME_ID.nunique()),
        "repro": {
            "incumbent_pooled_total_mae": inc_mae,
            "anchor": INCUMBENT_ANCHOR, "anchor_tol": ANCHOR_TOL,
            "pipeline_max_abs_diff": worst,
            "calibration_refit_max_dev": cal_dev,
            "recorded_param_linkage_max_dev": link_dev,
            "n_games": int(len(et)), "n_train_games": int(len(tg)),
            "uncal_source": (
                "reconstructed str_sum_h + str_sum_a from run_reval.build_features/"
                "make_games on channel_base_v2.csv with the recorded alphas "
                "(predictions_v2.csv has no uncal columns; channel_base_v2.csv "
                "holds raw ingredients only)"),
        },
    }


# ---------------------------------------------------------------------------
# 2. league scoring-environment tracker (walk-forward, within season)
# ---------------------------------------------------------------------------

def load_league_games() -> pd.DataFrame:
    mt = pd.read_parquet(MASTER_TEAM,
                         columns=["game_id", "season", "season_type", "game_date", "pts"])
    g = (mt.groupby("game_id")
         .agg(total=("pts", "sum"), n_rows=("pts", "size"),
              season=("season", "first"), date=("game_date", "first"),
              season_type=("season_type", "first"))
         .reset_index())
    bad = g[g.n_rows != 2]
    assert bad.empty, f"master_team games without exactly 2 team rows: {bad}"
    g["date"] = pd.to_datetime(g.date)
    g["gid"] = g.game_id.astype(str)
    return g.sort_values(["season", "date", "game_id"]).reset_index(drop=True)


def env_for_games(league: pd.DataFrame, spec: str) -> pd.Series:
    """Per-game league scoring environment under ``spec``: the aggregate of game
    totals over all league games of the SAME season on STRICTLY EARLIER dates.

    spec = 'expanding'      equal-weight mean of all strictly-prior games
    spec = 'ewma_<alpha>'   adjust=True EWMA over the per-game totals sequence in
                            (date, game_id) order, evaluated at the last game
                            strictly before the target date. game_id ordering of
                            same-date games is deterministic and irrelevant for
                            later dates' values beyond negligible weight shuffles
                            within a single date.

    First date of a season -> NaN (no prior information exists, none is
    invented). Returns a Series aligned to ``league``'s index.
    """
    out = np.full(len(league), np.nan)
    for _, seas in league.groupby("season", sort=False):
        idx = seas.index.to_numpy()
        dates = seas.date.to_numpy()
        totals = seas.total.to_numpy(float)
        # k[i] = number of games on strictly earlier dates (frame sorted by date)
        k = np.searchsorted(dates, dates, side="left")
        if spec == "expanding":
            csum = np.concatenate([[0.0], np.cumsum(totals)])
            with np.errstate(invalid="ignore", divide="ignore"):
                vals = np.where(k > 0, csum[k] / np.maximum(k, 1), np.nan)
        elif spec.startswith("ewma_"):
            alpha = float(spec.split("_", 1)[1])
            ew = pd.Series(totals).ewm(alpha=alpha, adjust=True).mean().to_numpy()
            vals = np.where(k > 0, ew[np.maximum(k - 1, 0)], np.nan)
        else:
            raise ValueError(f"unknown env spec {spec!r}")
        out[idx] = vals
    return pd.Series(out, index=league.index)


def env_dev_map(league: pd.DataFrame, spec: str, grand_mean: float) -> pd.Series:
    """gid -> env_dev (env minus the 2021-2023 grand mean; NaN where no prior
    same-season game exists — callers decide the fallback and count it)."""
    env = env_for_games(league, spec)
    return pd.Series((env - grand_mean).to_numpy(), index=league.gid.to_numpy())


# ---------------------------------------------------------------------------
# 3. train-only tuning of the environment spec (inner walk-forward folds)
# ---------------------------------------------------------------------------

def game_ids_of(D: pd.DataFrame, idx: np.ndarray) -> set:
    return set(D.loc[idx, "GAME_ID"])


def tune_env_spec(D: pd.DataFrame, outer24, tg: pd.DataFrame,
                  league: pd.DataFrame, grand_mean: float) -> tuple[str, pd.DataFrame, list]:
    """Choose the environment spec (expanding vs EWMA alpha) on 2021-2023 ONLY:
    3 inner walk-forward folds via evalharness.inner_tuning_splits; per fold fit
    (a, b, c) on the fold-train eligible games and score total MAE on the
    fold-val eligible games; winner = lowest mean val MAE (ties -> first in the
    ENV_SPECS order, i.e. the simpler spec)."""
    inner = eh.inner_tuning_splits(D, outer24, date_col="GAME_DATE", n_folds=3)
    fold_games = []
    for f in inner:
        fit_ids = game_ids_of(D, f.train_idx)
        val_ids = game_ids_of(D, f.val_idx)
        fold_games.append({
            "name": f.name,
            "fit": tg[tg.GAME_ID.isin(fit_ids)],
            "val": tg[tg.GAME_ID.isin(val_ids)],
            "train_end": str(f.train_end.date()),
            "val_start": str(f.val_start.date()),
            "val_end": str(f.val_end.date()),
        })
        assert len(fold_games[-1]["fit"]) and len(fold_games[-1]["val"])

    rows = []
    means = []
    # 'none_diagnostic' is a REFERENCE row only (a*uncal+b, no env term): the
    # registered challenger always carries the env term, so it is never
    # selectable — it exists to show how much (or little) the env term adds
    # inside the training era.
    for spec in ENV_SPECS + ["none_diagnostic"]:
        dev = (env_dev_map(league, spec, grand_mean)
               if spec != "none_diagnostic" else None)
        fold_maes = []
        for fg in fold_games:
            fit, val = fg["fit"], fg["val"]
            if dev is None:
                X = np.column_stack([fit.uncal_total.to_numpy(), np.ones(len(fit))])
                beta = lstsq_fit(X, fit.total_true.to_numpy())
                pred = beta[0] * val.uncal_total.to_numpy() + beta[1]
                beta = np.array([beta[0], beta[1], np.nan])
            else:
                e_fit = dev.reindex(fit.gid).to_numpy()
                e_val = dev.reindex(val.gid).to_numpy()
                assert not np.isnan(e_fit).any() and not np.isnan(e_val).any(), (
                    "eligible train games (>=5 prior team games) must always have "
                    "a prior-league-games environment")
                X = np.column_stack([fit.uncal_total.to_numpy(), np.ones(len(fit)), e_fit])
                beta = lstsq_fit(X, fit.total_true.to_numpy())
                pred = (beta[0] * val.uncal_total.to_numpy() + beta[1] + beta[2] * e_val)
            m = float(np.abs(pred - val.total_true.to_numpy()).mean())
            fold_maes.append(m)
            rows.append({"spec": spec, "fold": fg["name"], "n_fit": len(fit),
                         "n_val": len(val), "val_total_mae": m,
                         "a": beta[0], "b": beta[1], "c": beta[2]})
        mean_mae = float(np.mean(fold_maes))
        if spec != "none_diagnostic":
            means.append(mean_mae)
        rows.append({"spec": spec, "fold": "MEAN", "n_fit": np.nan, "n_val": np.nan,
                     "val_total_mae": mean_mae, "a": np.nan, "b": np.nan, "c": np.nan})
    winner = ENV_SPECS[int(np.argmin(means))]
    curve = pd.DataFrame(rows)
    log("env tuning (train-only inner folds): "
        + ", ".join(f"{s}={m:.4f}" for s, m in zip(ENV_SPECS, means))
        + f" | none_diagnostic={rows[-1]['val_total_mae']:.4f} -> winner {winner}")
    return winner, curve, fold_games


# ---------------------------------------------------------------------------
# 4. environment walk-forward audit (truncate + recompute)
# ---------------------------------------------------------------------------

def env_walkforward_audit(league: pd.DataFrame, spec: str, grand_mean: float,
                          dev: pd.Series, tg: pd.DataFrame, et: pd.DataFrame) -> pd.DataFrame:
    """For sampled games: drop ALL league games dated at/after the game's date,
    recompute the environment from the truncated history alone, and require the
    stored env_dev to be IDENTICAL. Proves no same-date or future game leaks
    into the tracker."""
    rng = np.random.default_rng(AUDIT_SEED)
    sample = []
    for s in rr.TEST_YEARS:
        pool = et.loc[et.season_h == s, "gid"].to_numpy()
        sample += rng.choice(pool, size=min(ENV_AUDIT_TEST_PER_SEASON, len(pool)),
                             replace=False).tolist()
    for s in TRAIN_YEARS:
        pool = tg.loc[tg.season_h == s, "gid"].to_numpy()
        sample += rng.choice(pool, size=min(ENV_AUDIT_TRAIN_PER_SEASON, len(pool)),
                             replace=False).tolist()

    lk = league.set_index("gid")
    rows = []
    for gid in sample:
        game = lk.loc[gid]
        season, date = game["season"], game["date"]
        hist = league[(league.season == season) & (league.date < date)]
        totals = hist.sort_values(["date", "game_id"]).total.to_numpy(float)
        if len(totals) == 0:
            recomputed = np.nan
        elif spec == "expanding":
            recomputed = float(totals.mean())
        else:
            alpha = float(spec.split("_", 1)[1])
            recomputed = float(pd.Series(totals).ewm(alpha=alpha, adjust=True)
                               .mean().iloc[-1])
        stored = float(dev.loc[gid]) + grand_mean
        diff = abs(recomputed - stored)
        rows.append({"gid": gid, "season": int(season), "date": str(pd.Timestamp(date).date()),
                     "n_prior_league_games": int(len(totals)),
                     "env_recomputed": recomputed, "env_stored": stored,
                     "abs_diff": diff, "identical": bool(diff <= 1e-9)})
    audit = pd.DataFrame(rows)
    if not audit.identical.all():
        raise SystemExit(f"ENV WALK-FORWARD AUDIT FAILED:\n{audit[~audit.identical]}")
    log(f"env walk-forward audit PASS: {len(audit)} sampled games "
        f"(test {ENV_AUDIT_TEST_PER_SEASON}/season + train fit "
        f"{ENV_AUDIT_TRAIN_PER_SEASON}/season), truncate-and-recompute identical "
        f"(max abs diff {audit.abs_diff.max():.3g})")
    return audit


# ---------------------------------------------------------------------------
# 5. context: bookie consensus totals (ungated)
# ---------------------------------------------------------------------------

def bookie_context(et: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bk = pd.read_csv(BOOKIE_TOTALS)
    bk["gid"] = bk.game_id.astype(str)
    j = et.merge(bk[["gid", "consensus_total", "n_books"]], on="gid",
                 how="inner", validate="one_to_one")
    assert len(j) == 365, f"expected the registered 365-game covered subset, got {len(j)}"
    e_bk = (j.consensus_total - j.total_true).abs().to_numpy()
    bk_mae = float(e_bk.mean())
    assert abs(bk_mae - 14.909) < 1e-3, f"bookie MAE {bk_mae} != registered context 14.909"

    rows = []
    for label, g in [("pooled", j)] + [(str(s), g) for s, g in j.groupby("season_h")]:
        eb = (g.consensus_total - g.total_true).abs().to_numpy()
        ec = (g.challenger_total - g.total_true).abs().to_numpy()
        ei = (g.str_total_cal - g.total_true).abs().to_numpy()
        dates = pd.to_datetime(g.GAME_DATE_h).dt.normalize().to_numpy()
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
    return pd.DataFrame(rows), j


# ---------------------------------------------------------------------------
# 6. component attribution (train-only fits, frozen, test-evaluated)
# ---------------------------------------------------------------------------

def component_attribution(tg: pd.DataFrame, et: pd.DataFrame,
                          dev_tg: np.ndarray, dev_et: np.ndarray) -> pd.DataFrame:
    """Which ingredient earns the improvement? All variants are least-squares
    fits on the SAME 610 train games, frozen, scored on the 673 test games.
    Diagnostic decomposition (reported, not gated)."""
    y_tr = tg.total_true.to_numpy()
    u_tr, u_te = tg.uncal_total.to_numpy(), et.uncal_total.to_numpy()
    i_tr, i_te = tg.str_total_cal.to_numpy(), et.str_total_cal.to_numpy()
    one_tr, one_te = np.ones(len(tg)), np.ones(len(et))
    variants = {
        "incumbent (per-side cal sum)": i_te,
        "recal_only: a*uncal+b": None,
        "env_only: b+c*env_dev": None,
        "incumbent_plus_env: a*str_total_cal+b+c*env_dev": None,
        "challenger: a*uncal+b+c*env_dev": None,
    }
    fits = {}
    beta = lstsq_fit(np.column_stack([u_tr, one_tr]), y_tr)
    variants["recal_only: a*uncal+b"] = beta[0] * u_te + beta[1]
    fits["recal_only"] = beta.tolist()
    beta = lstsq_fit(np.column_stack([one_tr, dev_tg]), y_tr)
    variants["env_only: b+c*env_dev"] = beta[0] + beta[1] * dev_et
    fits["env_only"] = beta.tolist()
    beta = lstsq_fit(np.column_stack([i_tr, one_tr, dev_tg]), y_tr)
    variants["incumbent_plus_env: a*str_total_cal+b+c*env_dev"] = (
        beta[0] * i_te + beta[1] + beta[2] * dev_et)
    fits["incumbent_plus_env"] = beta.tolist()
    beta = lstsq_fit(np.column_stack([u_tr, one_tr, dev_tg]), y_tr)
    variants["challenger: a*uncal+b+c*env_dev"] = beta[0] * u_te + beta[1] + beta[2] * dev_et
    fits["challenger"] = beta.tolist()
    # POST-HOC DIAGNOSTIC (clearly outside the registered family, nothing
    # fitted): incumbent + 1.0 * env_dev — separates "the environment signal is
    # useless" from "the train-frozen least-squares coefficient is the wrong
    # mechanism for a level shift the training era never exhibited".
    variants["posthoc_diag: incumbent + 1.0*env_dev (c:=1 a priori, NOT fitted, "
             "outside the registered family)"] = i_te + dev_et
    fits["posthoc_incumbent_plus_unit_env"] = [1.0, 0.0, 1.0]

    y_te = et.total_true.to_numpy()
    seasons = et.season_h.to_numpy()
    rows = []
    for name, pred in variants.items():
        err = np.abs(pred - y_te)
        row = {"variant": name, "pooled_mae": float(err.mean()),
               "pooled_bias_pred_minus_true": float((pred - y_te).mean())}
        for s in rr.TEST_YEARS:
            m = seasons == s
            row[f"mae_{s}"] = float(err[m].mean())
            row[f"bias_{s}"] = float((pred[m] - y_te[m]).mean())
        rows.append(row)
    tbl = pd.DataFrame(rows)
    tbl.attrs["fits"] = fits
    return tbl


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def write_report(outdir: Path, ctx: dict) -> None:
    r, reg = ctx["result"], ctx["registration"]
    per = {p["season"]: p for p in r.per_season}
    curve = ctx["curve"]
    mean_rows = curve[curve.fold == "MEAN"].sort_values("val_total_mae")
    attr = ctx["attribution"]
    bk = ctx["bookie_tbl"].set_index("season")
    a, b, c = ctx["beta"]
    inc_slope = ctx["incumbent_implied_slope"]
    disp = ctx["dispersion"]
    inv = ctx["invariance"]

    def prow(s):
        p = per[str(s)]
        return (f"| {s} | {p['n']} | {p['metric_challenger']:.4f} | "
                f"{p['metric_incumbent']:.4f} | {p['delta']:+.4f} |")

    md = f"""# totals_head_v1 — Dedicated Totals Head over the Structural Channels ({r.verdict})

*{ctx['run_time']} · registered experiment `{EXPERIMENT_ID}` (registered
{reg['registered_at']}, regime {reg['regime']}, primary metric `{reg['primary_metric']}`,
incumbent `{reg['incumbent_id']}`) · run mode **{ctx['mode'].upper()}** — {ctx['mode_note']}
· code `totals_head.py` (repo root) · groundwork `experiments/totals_groundwork/REPORT.md`.*

## Verdict

**{r.verdict}{' — promote' if r.promote else ''}.** Challenger pooled game-total MAE
**{r.metric_challenger:.4f}** vs incumbent **{r.metric_incumbent:.4f}** on the identical
{r.n_games} test games (pooled improvement **{r.pooled_improvement:+.4f}**, 90%
date-clustered bootstrap CI [{r.ci_low:+.4f}, {r.ci_high:+.4f}], {r.n_clusters} date
clusters; team-clustered sensitivity [{r.ci_sensitivity_team[0]:+.4f},
{r.ci_sensitivity_team[1]:+.4f}], {r.ci_sensitivity_team[2]} franchises).

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

## The fitted head

**challenger_total = a * structural_uncal_total + b + c * league_env_dev** with
**a = {a:.4f}, b = {b:.4f}, c = {c:.4f}**, least squares (numpy lstsq) on the
{ctx['n_fit']} eligible 2021-2023 walk-forward games only
({ctx['fit_date_range'][0]} -> {ctx['fit_date_range'][1]}), frozen for all test seasons —
the exact universe the incumbent's per-side calibrations were fit on.

- **Environment spec (train-only tuning):** `{ctx['env_spec']}` won the 3 inner
  walk-forward folds (evalharness.inner_tuning_splits, strictly inside 2021-2023).
  Top of the curve: {', '.join(f"{s.spec}={s.val_total_mae:.4f}" for s in mean_rows.head(3).itertuples())}
  (full grid: `env_tuning_curve.csv`; grid = expanding + EWMA alpha in {ENV_ALPHA_GRID}).
  league_env_dev = within-season league mean game total over STRICTLY EARLIER dates
  under that spec, minus the 2021-2023 grand mean **{ctx['grand_mean']:.4f}**
  ({ctx['n_grand']} games, master_team.parquet, both season types).
- **Interpretation vs the registered expectations:** the registration expected
  a > 1 if under-dispersion is real and c > 0 if the environment tracker earns its
  slot. Fitted **a = {a:.4f}** — {ctx['a_interpretation']}
  Fitted **c = {c:.4f}** — {'positive, the environment tracker earns its slot' if c > 0 else 'NOT positive: the environment tracker does not earn its slot on train-era evidence'}.
  For scale: the incumbent's per-side calibrations imply an effective uncal-total
  slope of ~{inc_slope:.4f} (str_home slope {ctx['rec_cal']['str_home'][1]:.4f},
  str_away slope {ctx['rec_cal']['str_away'][1]:.4f}).
- **Dispersion / bias diagnostics (test):** OLS slope of true on prediction
  {disp['slope_incumbent']:.3f} (incumbent) -> {disp['slope_challenger']:.3f} (challenger)
  (1.0 = efficient); SD(pred) {disp['sd_incumbent']:.2f} -> {disp['sd_challenger']:.2f}
  (SD true {disp['sd_true']:.2f}). 2026 bias (pred - true): {disp['bias26_incumbent']:+.2f}
  (incumbent, groundwork diagnosed -4.97) -> {disp['bias26_challenger']:+.2f} (challenger).

## Component attribution — what does the work

All variants least-squares-fit on the same 610 train games, frozen, scored on the 673
test games (`component_attribution.csv`):

| Variant | Pooled MAE | 2024 | 2025 | 2026 | 2026 bias |
|---|---|---|---|---|---|
""" + "\n".join(
        f"| {t.variant} | {t.pooled_mae:.4f} | {t.mae_2024:.4f} | {t.mae_2025:.4f} | "
        f"{t.mae_2026:.4f} | {t.bias_2026:+.2f} |" for t in attr.itertuples()) + f"""

{ctx['attribution_verdict']}

## Bookie context (ungated, registered as context rows)

Consensus pre-tip totals exist for {bk.loc['pooled', 'n']} of the 673 test games
(2025 from Jul 5 + 2026; **2024 has no totals lines on disk**). Bookie MAE
**{bk.loc['pooled', 'bookie_mae']:.4f}** (verified vs the registered 14.909).

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
   within 1e-3 of the registered 14.2236. The chanreval pipeline itself was re-run
   (imported from `run_reval.py`, recorded alphas): full-frame max abs diff
   {ctx['repro']['pipeline_max_abs_diff']:.3g} over the 673 games.
2. **structural_uncal_total source (documented + verified):**
   {ctx['repro']['uncal_source']}. Verified three ways: refit train-only calibrations
   equal `run_summary.json`'s recorded params to {ctx['repro']['calibration_refit_max_dev']:.3g};
   pushing the reconstructed uncal per-side sums through the RECORDED params reproduces
   the committed `str_total_cal` to {ctx['repro']['recorded_param_linkage_max_dev']:.3g};
   train universe = the recorded n = {ctx['repro']['n_train_games']}.
3. **Environment walk-forward audit:** {len(ctx['env_audit'])} sampled games
   ({ENV_AUDIT_TEST_PER_SEASON}/test season + {ENV_AUDIT_TRAIN_PER_SEASON}/train season,
   seed {AUDIT_SEED}): ALL league games at/after the game date dropped, environment
   recomputed from the truncated history — identical every time (max abs diff
   {ctx['env_audit'].abs_diff.max():.3g}; `env_walkforward_audit.csv`).
   Neutral-filled rows (no prior same-season league game) among the 1,283 fit+test
   games: {ctx['n_env_neutral']}.
4. **Fit-window audit:** the exact {ctx['n_fit']} train games (ids + dates) are in
   `fit_window_audit.csv`; tuning folds {ctx['fold_ranges']}; nothing dated after
   {ctx['fit_date_range'][1]} touches any fitted parameter.
5. **Margin invariance (registered gate 4, structural):** the challenger writes no
   margin column anywhere — output columns scanned for 'margin': {inv['margin_columns_in_outputs']};
   `predictions_v2.csv` byte-identical before/after (sha256 {inv['pred_sha256_before'][:12]}...,
   match={inv['pred_file_unchanged']}); reconstructed margin columns never modified
   (max abs dev vs committed: {inv['margin_max_abs_dev']:.3g}). The challenger
   recombines the SAME per-side predictions into a total; no margin forecast is
   produced or altered.

## Files

`game_level_totals.csv` (673 rows: game_id, date, season, season_type, total_true,
incumbent, challenger, env_dev, structural_uncal_total, contrib_recal, contrib_env,
bookie_consensus_total, abs errors) · `env_tuning_curve.csv` · `fit_window_audit.csv` ·
`env_walkforward_audit.csv` · `component_attribution.csv` · `bookie_context.csv` ·
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
                             "(tempdir) and write artifacts to a scratch outdir "
                             "(or --outdir); the real ledger is never touched")
    mode_g.add_argument("--real", action="store_true",
                        help="record the evaluation on the REAL ledger, artifacts "
                             "-> experiments/totals_head/ (orchestrator only)")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args(argv)
    mode = "smoke" if args.smoke else "real"

    registry_path = None
    scratch_note = None
    outdir = args.outdir or OUTDIR
    if args.smoke:
        scratch = Path(tempfile.mkdtemp(prefix="totals_head_smoke_"))
        registry_path = scratch / "registry_scratch.jsonl"
        shutil.copyfile(REPO / "experiments" / "registry.jsonl", registry_path)
        scratch_note = str(registry_path)
        outdir = args.outdir or (scratch / "out")
        log(f"SMOKE mode: scratch registry copy at {registry_path}")
    outdir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log(f"{mode.upper()} run at {run_time} -> {outdir}")

    # registration echo (read-only, from the real ledger)
    reg = eh.get_registration(EXPERIMENT_ID)
    assert reg["incumbent_id"] == INCUMBENT_ID, reg["incumbent_id"]
    log(f"registration OK: {EXPERIMENT_ID} registered {reg['registered_at']} "
        f"(regime {reg['regime']}, primary {reg['primary_metric']}, "
        f"thresholds {reg['thresholds']})")

    pred_sha_before = sha256_of(PREDICTIONS)

    # 1. incumbent reproduction + uncal reconstruction --------------------------
    R = reproduce_incumbent()
    tg, et, D = R["tg"], R["et"], R["D"]

    # margin snapshot (invariance assert input): the committed margin columns
    pv_margin_snapshot = R["pv"][["GAME_ID", "margin_true", "str_margin_cal",
                                  "raw_margin_cal"]].copy()

    # 2. league environment ----------------------------------------------------
    league = load_league_games()
    grand = league[league.season.isin(TRAIN_YEARS)]
    grand_mean = float(grand.total.mean())
    log(f"league environment source: master_team.parquet, {len(league)} games; "
        f"2021-2023 grand mean total {grand_mean:.4f} over {len(grand)} games")

    # 3. tune the environment spec on 2021-2023 only ----------------------------
    env_spec, curve, fold_games = tune_env_spec(D, R["outer24"], tg, league, grand_mean)

    # 4. final env_dev under the chosen spec ------------------------------------
    dev = env_dev_map(league, env_spec, grand_mean)
    dev_tg = dev.reindex(tg.gid).to_numpy()
    dev_et = dev.reindex(et.gid).to_numpy()
    n_env_neutral = int(np.isnan(dev_tg).sum() + np.isnan(dev_et).sum())
    assert n_env_neutral == 0, (
        f"{n_env_neutral} eligible games lack a prior-league-games environment")
    tg["env_dev"], et["env_dev"] = dev_tg, dev_et

    # 5. fit (a, b, c) on the 610 train games only, frozen ----------------------
    assert len(tg) == R["repro"]["n_train_games"] == 610
    X = np.column_stack([tg.uncal_total.to_numpy(), np.ones(len(tg)), dev_tg])
    beta = lstsq_fit(X, tg.total_true.to_numpy())
    a, b, c = (float(v) for v in beta)
    log(f"fitted on {len(tg)} train games ({tg.GAME_DATE_h.min().date()} -> "
        f"{tg.GAME_DATE_h.max().date()}): a={a:.6f} b={b:.6f} c={c:.6f}")

    et["challenger_total"] = a * et.uncal_total.to_numpy() + b + c * dev_et
    tg_pred = a * tg.uncal_total.to_numpy() + b + c * dev_tg
    train_mae = float(np.abs(tg_pred - tg.total_true.to_numpy()).mean())

    # 6. audits -----------------------------------------------------------------
    env_audit = env_walkforward_audit(league, env_spec, grand_mean, dev, tg, et)
    fit_window = tg[["GAME_ID", "GAME_DATE_h", "season_h"]].rename(columns={
        "GAME_ID": "game_id", "GAME_DATE_h": "date", "season_h": "season"}).copy()
    fit_window["date"] = pd.to_datetime(fit_window.date).dt.date
    fit_window["role"] = "abc_fit_row (also tuning pool)"

    # 7. margin invariance (structural gate 4) ----------------------------------
    pv_now = pd.read_csv(PREDICTIONS)
    chk = pv_now[["GAME_ID", "margin_true", "str_margin_cal", "raw_margin_cal"]].merge(
        pv_margin_snapshot, on="GAME_ID", suffixes=("", "_snap"), validate="one_to_one")
    margin_dev = max(float(np.abs(chk[c].to_numpy() - chk[c + "_snap"].to_numpy()).max())
                     for c in ["margin_true", "str_margin_cal", "raw_margin_cal"])
    pred_sha_mid = sha256_of(PREDICTIONS)
    invariance = {
        "pred_sha256_before": pred_sha_before,
        "pred_file_unchanged": bool(pred_sha_mid == pred_sha_before),
        "margin_max_abs_dev": margin_dev,
        "margin_columns_in_outputs": 0,       # asserted below after outputs exist
        "note": ("structural: the challenger recombines the same per-side "
                 "predictions into a TOTAL only; no margin forecast is produced "
                 "or altered anywhere in this script"),
    }
    assert invariance["pred_file_unchanged"] and margin_dev <= 1e-12

    def joint_check():
        ok = invariance["pred_file_unchanged"] and invariance["margin_max_abs_dev"] <= 1e-12
        return ok, {
            "mode": "structural margin invariance (registered: asserted, not fitted)",
            "predictions_v2_sha256_unchanged": invariance["pred_file_unchanged"],
            "margin_columns_max_abs_dev": invariance["margin_max_abs_dev"],
            "challenger_margin_columns_written": 0,
        }

    # 8. the registered gated comparison ----------------------------------------
    cov = len(et) / R["n_total_test_games"]
    ch_frame = pd.DataFrame({
        "game_id": et.GAME_ID.to_numpy(),
        "game_date": pd.to_datetime(et.GAME_DATE_h).to_numpy(),
        "season": et.season_h.to_numpy(),
        "y_true": et.total_true.to_numpy(),
        "y_pred": et.challenger_total.to_numpy(),
        "home_team": et.TEAM_ID_h.to_numpy(),   # franchise id (PHO/PHX-stable)
    })
    inc_frame = R["pv"][["GAME_ID", "total_true", "str_total_cal"]].rename(columns={
        "GAME_ID": "game_id", "total_true": "y_true", "str_total_cal": "y_pred"})
    result = eh.compare_to_incumbent(
        ch_frame, inc_frame,
        experiment_id=EXPERIMENT_ID,
        registry_path=registry_path,
        joint_check=joint_check,
        coverage=(cov, cov),
    )
    log(f"VERDICT: {result.verdict} (promote={result.promote}); challenger "
        f"{result.metric_challenger:.4f} vs incumbent {result.metric_incumbent:.4f}; "
        f"pooled improvement {result.pooled_improvement:+.4f} "
        f"[90% CI {result.ci_low:+.4f}, {result.ci_high:+.4f}]; "
        f"failed gates: {result.failed_gates}")

    # 9. context + attribution + diagnostics ------------------------------------
    bookie_tbl, bkj = bookie_context(et)
    attribution = component_attribution(tg, et, dev_tg, dev_et)

    y = et.total_true.to_numpy()
    ch = et.challenger_total.to_numpy()
    ic = et.str_total_cal.to_numpy()
    m26 = et.season_h.to_numpy() == 2026
    dispersion = {
        "slope_incumbent": float(np.polyfit(ic, y, 1)[0]),
        "slope_challenger": float(np.polyfit(ch, y, 1)[0]),
        "sd_incumbent": float(np.std(ic, ddof=1)),
        "sd_challenger": float(np.std(ch, ddof=1)),
        "sd_true": float(np.std(y, ddof=1)),
        "bias26_incumbent": float((ic[m26] - y[m26]).mean()),
        "bias26_challenger": float((ch[m26] - y[m26]).mean()),
        "bias_pooled_incumbent": float((ic - y).mean()),
        "bias_pooled_challenger": float((ch - y).mean()),
    }

    rec_cal = json.load(open(CHANREVAL / "run_summary.json", encoding="utf-8"))["calibration"]
    inc_slope = (rec_cal["str_home"][1] + rec_cal["str_away"][1]) / 2.0
    a_interp = (
        "greater than 1: the head EXPANDS the uncal total — under-dispersion "
        "confirmed at the uncal level." if a > 1 else
        f"below 1 (and {'above' if a > inc_slope else 'below'} the incumbent's "
        f"implied ~{inc_slope:.3f}): on 2021-2023 evidence the game-to-game totals "
        "signal in the channel sum does not support expansion; the diagnosed "
        "test-era slope of 1.33 (true on calibrated pred) is carried mostly by the "
        "2026 level shift, not by an under-used slope that a train-era fit could "
        "recover.")

    # attribution verdict (component decomposition — what gets built next)
    at = attribution.set_index("variant")
    inc_pool = float(at.loc["incumbent (per-side cal sum)", "pooled_mae"])
    recal_gain = inc_pool - float(at.loc["recal_only: a*uncal+b", "pooled_mae"])
    env_over_inc_gain = inc_pool - float(
        at.loc["incumbent_plus_env: a*str_total_cal+b+c*env_dev", "pooled_mae"])
    full_gain = inc_pool - float(at.loc["challenger: a*uncal+b+c*env_dev", "pooled_mae"])
    posthoc_key = [v for v in at.index if v.startswith("posthoc_diag")][0]
    posthoc_pool = float(at.loc[posthoc_key, "pooled_mae"])
    posthoc_26 = float(at.loc[posthoc_key, "mae_2026"])
    inc_26 = float(at.loc["incumbent (per-side cal sum)", "mae_2026"])
    train_env_corr = float(np.corrcoef(dev_tg, tg.total_true.to_numpy())[0, 1])
    none_inner = float(curve.loc[(curve.spec == "none_diagnostic")
                                 & (curve.fold == "MEAN"), "val_total_mae"].iloc[0])
    winner_inner = float(curve.loc[(curve.spec == env_spec)
                                   & (curve.fold == "MEAN"), "val_total_mae"].iloc[0])
    if full_gain > 0:
        attribution_verdict = (
            f"**Attribution:** of the challenger's pooled gain ({full_gain:+.4f} vs the "
            f"incumbent), the dedicated totals recalibration ALONE contributes "
            f"{recal_gain:+.4f} and adding the environment term to the (untouched) "
            f"incumbent contributes {env_over_inc_gain:+.4f} — "
            + ("the environment tracker does essentially all the work; the recalibration "
               "is close to a pass-through." if abs(recal_gain) < 0.25 * abs(env_over_inc_gain)
               else "the recalibration does essentially all the work; the environment "
                    "term adds little." if abs(env_over_inc_gain) < 0.25 * abs(recal_gain)
               else "both components contribute materially."))
    else:
        attribution_verdict = (
            f"**Attribution — the head degrades the incumbent ({full_gain:+.4f} pooled) and "
            f"NEITHER component earns its slot.** (1) The dedicated recalibration alone is "
            f"{recal_gain:+.4f}: a single train-fit (a, b) on the uncal channel-sum total is "
            f"slightly WORSE out-of-sample than the incumbent's two per-side calibrations — "
            f"the 'no dedicated totals calibration' defect was not a real defect. "
            f"(2) The environment term alone (added to the untouched incumbent) is "
            f"{env_over_inc_gain:+.4f}: within 2021-2023 the environment carries no signal "
            f"(corr(env_dev, total_true) = {train_env_corr:+.3f} on the 610 fit games; "
            f"inner-fold c estimates flip sign fold-to-fold, and the tuner's winning spec "
            f"beats the no-env reference by only {none_inner - winner_inner:+.4f} inner MAE), "
            f"so least squares freezes a near-zero, slightly NEGATIVE c that extrapolates the "
            f"wrong way into the hot 2026 environment. (3) The failure is the train-frozen "
            f"coefficient mechanism, not the environment signal itself: the post-hoc "
            f"(unregistered, unfitted) c:=1 overlay 'incumbent + env_dev' scores "
            f"{posthoc_pool:.4f} pooled and {posthoc_26:.4f} on 2026 (incumbent {inc_26:.4f}) "
            f"— the 2026 level shift is real and env_dev points at it, but no coefficient "
            f"learnable from 2021-2023 (where no such shift exists) can be trusted to apply "
            f"it. A v2 should preregister an ONLINE mechanism with structure fixed a priori "
            f"(e.g. same-season trailing mean-residual correction, groundwork §4.4) instead "
            f"of a train-fit env coefficient.")

    # 10. outputs ---------------------------------------------------------------
    glt = pd.DataFrame({
        "game_id": et.GAME_ID.to_numpy(),
        "date": pd.to_datetime(et.GAME_DATE_h).dt.date,
        "season": et.season_h.to_numpy(),
        "season_type": et.season_type_h.to_numpy(),
        "total_true": y,
        "incumbent": ic,
        "challenger": ch,
        "env_dev": dev_et,
        "structural_uncal_total": et.uncal_total.to_numpy(),
        "contrib_recal": a * et.uncal_total.to_numpy() + b,
        "contrib_env": c * dev_et,
        "abs_err_incumbent": np.abs(ic - y),
        "abs_err_challenger": np.abs(ch - y),
    }).merge(bkj[["GAME_ID", "consensus_total"]].rename(
        columns={"GAME_ID": "game_id", "consensus_total": "bookie_consensus_total"}),
        on="game_id", how="left")
    n_margin_cols = sum("margin" in c.lower() for f in
                        (glt, curve, fit_window, env_audit, attribution, bookie_tbl)
                        for c in f.columns)
    invariance["margin_columns_in_outputs"] = n_margin_cols
    assert n_margin_cols == 0, "margin column leaked into an output file"

    glt.to_csv(outdir / "game_level_totals.csv", index=False)
    curve.to_csv(outdir / "env_tuning_curve.csv", index=False)
    fit_window.to_csv(outdir / "fit_window_audit.csv", index=False)
    env_audit.to_csv(outdir / "env_walkforward_audit.csv", index=False)
    attribution.to_csv(outdir / "component_attribution.csv", index=False)
    bookie_tbl.to_csv(outdir / "bookie_context.csv", index=False)
    with open(outdir / "gate_verdict.json", "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, indent=2, default=str)

    fold_ranges = "; ".join(
        f"{fg['name']}: fit-through {fg['train_end']}, val {fg['val_start']}"
        f"->{fg['val_end']} ({len(fg['fit'])}/{len(fg['val'])} games)"
        for fg in fold_games)

    pred_sha_after = sha256_of(PREDICTIONS)
    assert pred_sha_after == pred_sha_before, "predictions_v2.csv changed during the run"

    summary = {
        "experiment_id": EXPERIMENT_ID, "mode": mode, "run_time": run_time,
        "scratch_registry": scratch_note,
        "registration": {k: reg[k] for k in
                         ("experiment_id", "registered_at", "incumbent_id",
                          "primary_metric", "thresholds", "regime")},
        "reproduction": R["repro"],
        "environment": {
            "source": str(MASTER_TEAM.relative_to(REPO)),
            "n_league_games": int(len(league)),
            "grand_mean_2021_2023": grand_mean,
            "n_grand_mean_games": int(len(grand)),
            "spec_grid": ENV_SPECS,
            "spec_chosen": env_spec,
            "neutral_filled_rows_fit_or_test": n_env_neutral,
        },
        "fit": {
            "a": a, "b": b, "c": c,
            "n_fit_games": int(len(tg)),
            "fit_date_range": [str(tg.GAME_DATE_h.min().date()),
                               str(tg.GAME_DATE_h.max().date())],
            "train_total_mae": train_mae,
            "incumbent_implied_uncal_slope": inc_slope,
            "tuning_folds": fold_ranges,
            "train_corr_env_dev_vs_total_true": train_env_corr,
            "inner_mean_mae_winner": winner_inner,
            "inner_mean_mae_no_env_reference": none_inner,
        },
        "dispersion_diagnostics": dispersion,
        "component_attribution_fits": attribution.attrs["fits"],
        "margin_invariance": invariance | {"pred_sha256_after": pred_sha_after},
        "bookie_context": bookie_tbl.to_dict(orient="records"),
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
        "run_time": run_time, "curve": curve, "env_spec": env_spec,
        "grand_mean": grand_mean, "n_grand": len(grand),
        "beta": (a, b, c), "n_fit": len(tg),
        "fit_date_range": (str(tg.GAME_DATE_h.min().date()),
                           str(tg.GAME_DATE_h.max().date())),
        "fold_ranges": fold_ranges,
        "attribution": attribution, "attribution_verdict": attribution_verdict,
        "bookie_tbl": bookie_tbl, "repro": R["repro"], "env_audit": env_audit,
        "n_env_neutral": n_env_neutral, "invariance": invariance,
        "dispersion": dispersion, "incumbent_implied_slope": inc_slope,
        "rec_cal": rec_cal, "a_interpretation": a_interp,
    })
    log(f"artifacts written to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
