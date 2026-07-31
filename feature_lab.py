"""feature_lab.py — screening harness for player_feature_screen_v1.

Implements the preregistered protocol EXACTLY (experiments/registry.jsonl,
experiment_id=player_feature_screen_v1, registered 2026-07-31T11:29:22Z):

  * Screening window 2021-2024 ONLY. THE QUARANTINE IS ABSOLUTE: 2025/2026
    rows are never loaded; every assembled matrix asserts
    max(game_date) < 2025-01-01 (features.common.assert_quarantine) and the
    audit trail is written to experiments/feature_screen/quarantine_audit.json.
  * Targets: per-player per-36 channel production (3*fg3m, points_paint, ftm,
    pts-3*fg3m-ftm-points_paint per 36) on played regular-season rows with
    >= 8 minutes (>= 15-minute robustness rerun) and >= 5 prior same-season
    appearances. Source: data/masters/master_player.parquet.
  * Baseline per channel: shifted per-player rate EWMA (ratio of EWMAs of
    channel points and minutes — a minutes-weighted rate trend), alpha tuned
    per channel on the 2021-2023 inner walk-forward folds
    (evalharness.splits.inner_tuning_splits), frozen before 2024 is touched.
  * Candidate evaluation: closed-form ridge (lambda=1.0 on standardized
    inputs, unpenalized intercept — minutes_twostage.py pattern) on
    [baseline, feature] (+ baseline*feature when the interaction flag is set;
    the catalog defines no baseline interactions, so it never fires), fit on
    2021-2023, scored on walk-forward 2024. Features carrying an EWMA sweep
    alpha {0.05..0.50 step 0.05} on the INNER folds only, frozen per channel.
  * Score: delta = MAE_2024(ridge[baseline+feature]) - MAE_2024(ridge[baseline]).
    The reference is the RIDGE-recalibrated baseline so the delta isolates the
    feature's marginal information (the raw-EWMA baseline MAE is reported
    alongside; the permutation null uses the identical statistic).
  * Null: 200 within-season permutations of the FEATURE VALUES on both train
    and validation, refit, rescore. Permuting the feature (not the target)
    leaves the baseline column and target aligned — the baseline's
    information is fully preserved — while destroying every alignment between
    the candidate and specific player-games; permuting WITHIN season keeps
    each season's marginal feature distribution intact, so a candidate gets
    no credit for merely encoding season-level shifts. p = (1 + #{null
    improvement >= observed}) / (1 + n_perm).
  * Benjamini-Hochberg FDR at 10% across ALL screened (candidate, channel)
    tests. Survival additionally requires sign-consistent improvement across
    the 3 inner folds AND 2024.

This script records NOTHING on the ledger: it never imports or calls
registry.register / evaluate / record_evaluation / render_leaderboards and
never writes to experiments/registry.jsonl. There is NO --real mode.
Artifacts go to experiments/feature_screen/ only.

Run:  python feature_lab.py                # full screen
      python feature_lab.py --perms 30 --limit 4   # dev smoke only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from evalharness.splits import inner_tuning_splits, walk_forward_by_season  # noqa: E402
from features import ALL_CANDIDATES, CHANNELS, SKIPPED, Ctx  # noqa: E402
from features.common import (QUARANTINE_CUTOFF, TRAIN_SEASONS, VAL_SEASON,  # noqa: E402
                             assert_quarantine, sratio_ew)

OUTDIR = REPO / "experiments" / "feature_screen"
DIAG = OUTDIR / "diagnostics"

ALPHA_GRID = [round(a, 2) for a in np.arange(0.05, 0.501, 0.05)]
RIDGE_LAMBDA = 1.0
N_PERM_DEFAULT = 200
N_INNER_FOLDS = 3
MIN_MINUTES = 8.0
MIN_MINUTES_ROBUST = 15.0
MIN_PRIOR_APPS = 5
FDR_Q = 0.10
SEED_BASE = 20260731
CH_INDEX = {ch: i for i, ch in enumerate(CHANNELS)}


# ---------------------------------------------------------------------------
# ridge machinery (closed form, unpenalized intercept; no sklearn)
# ---------------------------------------------------------------------------

def ridge_fit(Z: np.ndarray, y: np.ndarray, lam: float = RIDGE_LAMBDA) -> np.ndarray:
    n, p = Z.shape
    X1 = np.hstack([np.ones((n, 1)), Z])
    pen = lam * np.eye(p + 1)
    pen[0, 0] = 0.0
    return np.linalg.solve(X1.T @ X1 + pen, X1.T @ y)


def ridge_predict(Z: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return np.hstack([np.ones((Z.shape[0], 1)), Z]) @ beta


def mae(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean(np.abs(y - p)))


class Design:
    """Standardized design [baseline, feature (+ interaction)] built from fit
    rows only; NaN features mean-filled with the FIT-row mean."""

    def __init__(self, b_fit, x_fit, y_fit, interaction=False):
        self.interaction = interaction
        self.fill = float(np.nanmean(x_fit)) if np.any(~np.isnan(x_fit)) else 0.0
        xf = np.where(np.isnan(x_fit), self.fill, x_fit)
        self.mb, self.sb = float(np.mean(b_fit)), float(np.std(b_fit))
        self.mx, self.sx = float(np.mean(xf)), float(np.std(xf))
        self.degenerate = self.sx < 1e-12
        self.sb = self.sb if self.sb > 1e-12 else 1.0
        self.sx = self.sx if self.sx > 1e-12 else 1.0
        self.zb_fit = (b_fit - self.mb) / self.sb
        self.zx_fit = (xf - self.mx) / self.sx
        self.y_fit = y_fit

    def z(self, b, x):
        xf = np.where(np.isnan(x), self.fill, x)
        zb = (b - self.mb) / self.sb
        zx = (xf - self.mx) / self.sx
        cols = [zb, zx]
        if self.interaction:
            cols.append(zb * zx)
        return np.column_stack(cols)

    def fit_cols(self):
        cols = [self.zb_fit, self.zx_fit]
        if self.interaction:
            cols.append(self.zb_fit * self.zx_fit)
        return np.column_stack(cols)


def fit_score_pair(b_tr, x_tr, y_tr, b_va, x_va, y_va, interaction=False):
    """Returns (mae_base_ridge, mae_feat_ridge, beta_feature_std)."""
    # baseline-only ridge
    mb, sb = float(np.mean(b_tr)), float(np.std(b_tr))
    sb = sb if sb > 1e-12 else 1.0
    zb_tr = ((b_tr - mb) / sb)[:, None]
    zb_va = ((b_va - mb) / sb)[:, None]
    beta0 = ridge_fit(zb_tr, y_tr)
    m_base = mae(y_va, ridge_predict(zb_va, beta0))
    d = Design(b_tr, x_tr, y_tr, interaction)
    if d.degenerate:
        return m_base, m_base, 0.0, True
    beta = ridge_fit(d.fit_cols(), y_tr)
    m_feat = mae(y_va, ridge_predict(d.z(b_va, x_va), beta))
    return m_base, m_feat, float(beta[2]), False


def perm_null(b_tr, x_tr, y_tr, b_va, x_va, y_va, season_tr, n_perm, rng,
              interaction=False):
    """Null improvements: permute FEATURE VALUES within season on train and
    val, refit, rescore (see module docstring for why this preserves the
    baseline's information while destroying the feature's)."""
    d = Design(b_tr, x_tr, y_tr, interaction)
    if d.degenerate:
        return np.zeros(n_perm)
    xf_tr = np.where(np.isnan(x_tr), d.fill, x_tr)
    xf_va = np.where(np.isnan(x_va), d.fill, x_va)
    blocks = [np.flatnonzero(season_tr == s) for s in np.unique(season_tr)]
    mb, sb = float(np.mean(b_tr)), float(np.std(b_tr))
    sb = sb if sb > 1e-12 else 1.0
    zb_tr = ((b_tr - mb) / sb)[:, None]
    zb_va = ((b_va - mb) / sb)[:, None]
    beta0 = ridge_fit(zb_tr, y_tr)
    m_base = mae(y_va, ridge_predict(zb_va, beta0))
    out = np.empty(n_perm)
    for k in range(n_perm):
        xp_tr = xf_tr.copy()
        for idx in blocks:
            xp_tr[idx] = xf_tr[rng.permutation(idx)]
        xp_va = xf_va[rng.permutation(len(xf_va))]
        dk = Design(b_tr, xp_tr, y_tr, interaction)
        beta = ridge_fit(dk.fit_cols(), y_tr)
        m_feat = mae(y_va, ridge_predict(dk.z(b_va, xp_va), beta))
        out[k] = m_base - m_feat            # improvement
    return out


def bh_adjust(pvals: np.ndarray) -> np.ndarray:
    m = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order] * m / (np.arange(m) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(q, 1.0)
    return out


# ---------------------------------------------------------------------------
# universe + baseline
# ---------------------------------------------------------------------------

def build_universe(ctx: Ctx):
    P = ctx.P
    mask = (P["minutes"] >= MIN_MINUTES) & (P["prior_apps"] >= MIN_PRIOR_APPS)
    for ch in CHANNELS:
        mask &= P[f"r_{ch}"].notna()
    U = P.loc[mask, ["player_id", "game_id", "game_date", "season", "minutes"]].copy()
    for ch in CHANNELS:
        U[f"y_{ch}"] = P.loc[mask, f"r_{ch}"]
    assert_quarantine(U["game_date"], "target_universe(min>=8)", ctx.audit)
    outer = walk_forward_by_season(U, test_seasons=[VAL_SEASON])[0]
    folds = inner_tuning_splits(U, outer, n_folds=N_INNER_FOLDS)
    return U, outer, folds


def tune_baselines(ctx: Ctx, U, outer, folds):
    """Per-channel baseline alpha via raw-EWMA MAE on inner-fold val rows."""
    P = ctx.P
    curves = []
    chosen = {}
    for ch in CHANNELS:
        best_alpha, best_loss = None, np.inf
        for a in ALPHA_GRID:
            base = (sratio_ew(P, P[f"cp_{ch}"], P["minutes"], a) * 36.0)
            bu = base.loc[U.index]
            losses = []
            for f in folds:
                va = U.loc[f.val_idx]
                pred = bu.loc[f.val_idx].to_numpy(float)
                ok = ~np.isnan(pred)
                losses.append(mae(va[f"y_{ch}"].to_numpy(float)[ok], pred[ok]))
            loss = float(np.mean(losses))
            curves.append({"channel": ch, "alpha": a, "inner_mae": loss})
            if loss < best_loss:
                best_loss, best_alpha = loss, a
        chosen[ch] = best_alpha
        ctx.baselines[ch] = (sratio_ew(P, P[f"cp_{ch}"], P["minutes"], best_alpha) * 36.0)
        ctx.baseline_alphas[ch] = best_alpha
    return chosen, pd.DataFrame(curves)


# ---------------------------------------------------------------------------
# candidate evaluation
# ---------------------------------------------------------------------------

def series_for_channel(built, ch):
    if isinstance(built, dict):
        return built[ch]
    return built


def eval_candidate(ctx, cand, U, U15, outer, folds, n_perm, arr, arr15):
    """Full evaluation of one candidate: sweep, folds, 2024, null, robustness."""
    t0 = time.time()
    rows, robust_rows, alpha_rows, diag = [], [], [], {}
    grid = (cand.sweep_grid or ALPHA_GRID) if cand.alpha_swept else [None]
    built_by_alpha = {}
    for a in grid:
        built_by_alpha[a] = cand.build(ctx, a)

    for ch in cand.channels:
        A = arr[ch]
        # ---- alpha selection on inner folds only ----
        if cand.alpha_swept:
            best_a, best_loss = None, np.inf
            for a in grid:
                x_all = series_for_channel(built_by_alpha[a], ch).loc[U.index].to_numpy(float)
                losses = []
                for f in folds:
                    tr_pos = U.index.get_indexer(f.train_idx)
                    va_pos = U.index.get_indexer(f.val_idx)
                    _, m_feat, _, _ = fit_score_pair(
                        A["b"][tr_pos], x_all[tr_pos], A["y"][tr_pos],
                        A["b"][va_pos], x_all[va_pos], A["y"][va_pos],
                        cand.interaction_with_baseline)
                    losses.append(m_feat)
                loss = float(np.mean(losses))
                alpha_rows.append({"catalog_number": cand.num, "channel": ch,
                                   "alpha": a, "inner_mae": loss})
                if loss < best_loss:
                    best_loss, best_a = loss, a
            alpha = best_a
        else:
            alpha = None
        x_all = series_for_channel(built_by_alpha[alpha], ch).loc[U.index].to_numpy(float)
        nan_share = float(np.mean(np.isnan(x_all)))

        # ---- inner-fold deltas at the frozen config ----
        fold_deltas = []
        for f in folds:
            tr_pos = U.index.get_indexer(f.train_idx)
            va_pos = U.index.get_indexer(f.val_idx)
            m_b, m_f, _, _ = fit_score_pair(
                A["b"][tr_pos], x_all[tr_pos], A["y"][tr_pos],
                A["b"][va_pos], x_all[va_pos], A["y"][va_pos],
                cand.interaction_with_baseline)
            fold_deltas.append(m_f - m_b)

        # ---- 2024 walk-forward score ----
        tr_pos = U.index.get_indexer(outer.train_idx)
        va_pos = U.index.get_indexer(outer.test_idx)
        b_tr, x_tr, y_tr = A["b"][tr_pos], x_all[tr_pos], A["y"][tr_pos]
        b_va, x_va, y_va = A["b"][va_pos], x_all[va_pos], A["y"][va_pos]
        m_base, m_feat, beta_x, degen = fit_score_pair(
            b_tr, x_tr, y_tr, b_va, x_va, y_va, cand.interaction_with_baseline)
        delta = m_feat - m_base
        improvement = -delta

        # ---- permutation null ----
        rng = np.random.default_rng(SEED_BASE * 100 + cand.num * 10 + CH_INDEX[ch])
        if degen:
            null_imp = np.zeros(n_perm)
            p = 1.0
        else:
            null_imp = perm_null(b_tr, x_tr, y_tr, b_va, x_va, y_va,
                                 A["season"][tr_pos], n_perm, rng,
                                 cand.interaction_with_baseline)
            p = float((1 + np.sum(null_imp >= improvement)) / (1 + n_perm))

        sign_consistent = bool(all(d < 0 for d in fold_deltas) and delta < 0)
        rows.append({
            "catalog_number": cand.num, "name": cand.name, "family": cand.family,
            "channel": ch, "alpha_chosen": alpha, "n_train": int(len(tr_pos)),
            "n_val": int(len(va_pos)), "nan_share": round(nan_share, 4),
            "mae_base_ridge_2024": round(m_base, 5),
            "mae_feat_2024": round(m_feat, 5),
            "delta_mae": round(delta, 5), "improvement": round(improvement, 5),
            "beta_feature_std": round(beta_x, 5),
            "fold_deltas": ";".join(f"{d:+.5f}" for d in fold_deltas),
            "fold_signs": "".join("-" if d < 0 else "+" for d in fold_deltas),
            "sign_2024": "-" if delta < 0 else "+",
            "sign_consistent": sign_consistent,
            "p_value": round(p, 5), "degenerate": degen, "note": cand.note,
        })
        diag[ch] = {
            "null_improvement_q05": float(np.quantile(null_imp, 0.05)),
            "null_improvement_q50": float(np.quantile(null_imp, 0.50)),
            "null_improvement_q95": float(np.quantile(null_imp, 0.95)),
            "null_improvement_max": float(np.max(null_imp)),
            "observed_improvement": improvement,
        }

        # ---- >=15-minute robustness rerun (frozen alpha; documented) ----
        A15 = arr15[ch]
        x15 = series_for_channel(built_by_alpha[alpha], ch).loc[U15.index].to_numpy(float)
        tr15 = np.flatnonzero(np.isin(A15["season"], TRAIN_SEASONS))
        va15 = np.flatnonzero(A15["season"] == VAL_SEASON)
        m_b15, m_f15, _, degen15 = fit_score_pair(
            A15["b"][tr15], x15[tr15], A15["y"][tr15],
            A15["b"][va15], x15[va15], A15["y"][va15],
            cand.interaction_with_baseline)
        d15 = m_f15 - m_b15
        rng15 = np.random.default_rng(SEED_BASE * 100 + cand.num * 10 + CH_INDEX[ch] + 7_000_000)
        if degen15:
            p15 = 1.0
        else:
            null15 = perm_null(A15["b"][tr15], x15[tr15], A15["y"][tr15],
                               A15["b"][va15], x15[va15], A15["y"][va15],
                               A15["season"][tr15], n_perm, rng15,
                               cand.interaction_with_baseline)
            p15 = float((1 + np.sum(null15 >= -d15)) / (1 + n_perm))
        robust_rows.append({
            "catalog_number": cand.num, "name": cand.name, "channel": ch,
            "alpha_chosen": alpha,
            "delta_mae_min15": round(d15, 5), "p_value_min15": round(p15, 5),
            "sign_min15": "-" if d15 < 0 else "+",
            "agrees_with_primary": bool((d15 < 0) == (delta < 0)),
        })
    elapsed = time.time() - t0
    return rows, robust_rows, alpha_rows, diag, elapsed


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--perms", type=int, default=N_PERM_DEFAULT,
                    help="permutations per test (protocol: 200)")
    ap.add_argument("--limit", type=int, default=None,
                    help="DEV ONLY: screen only the first N candidates")
    args = ap.parse_args(argv)

    t_start = time.time()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)

    print("[load] building context (quarantine-filtered at source) ...")
    ctx = Ctx()
    U, outer, folds = build_universe(ctx)
    print(f"[universe] {len(U)} target rows (min>={MIN_MINUTES:g}, "
          f">={MIN_PRIOR_APPS} prior apps); train={len(outer.train_idx)}, "
          f"val2024={len(outer.test_idx)}")

    print("[baseline] tuning per-channel EWMA alpha on inner folds ...")
    chosen, base_curves = tune_baselines(ctx, U, outer, folds)
    print(f"[baseline] frozen alphas: {chosen}")

    # target/baseline arrays per channel on the two universes
    def make_arrays(Ux):
        assert_quarantine(Ux["game_date"], f"design_matrix(n={len(Ux)})", ctx.audit)
        out = {}
        for ch in CHANNELS:
            out[ch] = {
                "y": Ux[f"y_{ch}"].to_numpy(float),
                "b": ctx.baselines[ch].loc[Ux.index].to_numpy(float),
                "season": Ux["season"].to_numpy(int),
            }
            nb = np.isnan(out[ch]["b"])
            if nb.any():
                raise RuntimeError(f"{int(nb.sum())} NaN baseline values on {ch}")
        return out

    U15 = U[U["minutes"] >= MIN_MINUTES_ROBUST].copy()
    arr = make_arrays(U)
    arr15 = make_arrays(U15)

    # baseline reference MAEs for the report
    tr_pos = U.index.get_indexer(outer.train_idx)
    va_pos = U.index.get_indexer(outer.test_idx)
    base_ref = {}
    for ch in CHANNELS:
        A = arr[ch]
        raw = mae(A["y"][va_pos], A["b"][va_pos])
        mb, sb = float(np.mean(A["b"][tr_pos])), float(np.std(A["b"][tr_pos]))
        beta0 = ridge_fit(((A["b"][tr_pos] - mb) / sb)[:, None], A["y"][tr_pos])
        rid = mae(A["y"][va_pos], ridge_predict(((A["b"][va_pos] - mb) / sb)[:, None], beta0))
        base_ref[ch] = {"alpha": chosen[ch], "mae_raw_ewma_2024": round(raw, 5),
                        "mae_ridge_base_2024": round(rid, 5)}
        print(f"[baseline] {ch}: alpha={chosen[ch]} raw2024={raw:.4f} ridge2024={rid:.4f}")

    cands = ALL_CANDIDATES[: args.limit] if args.limit else ALL_CANDIDATES
    print(f"[screen] {len(cands)} candidates, {args.perms} permutations per test")

    all_rows, all_robust, all_alpha, all_diag = [], [], [], {}
    for i, cand in enumerate(cands, 1):
        try:
            rows, rob, arows, diag, dt = eval_candidate(
                ctx, cand, U, U15, outer, folds, args.perms, arr, arr15)
        except Exception as e:  # a candidate must never sink the screen
            print(f"  !! #{cand.num} {cand.name} FAILED: {type(e).__name__}: {e}")
            rows = [{"catalog_number": cand.num, "name": cand.name,
                     "family": cand.family, "channel": ch, "alpha_chosen": None,
                     "n_train": 0, "n_val": 0, "nan_share": 1.0,
                     "mae_base_ridge_2024": np.nan, "mae_feat_2024": np.nan,
                     "delta_mae": np.nan, "improvement": np.nan,
                     "beta_feature_std": np.nan, "fold_deltas": "",
                     "fold_signs": "", "sign_2024": "", "sign_consistent": False,
                     "p_value": 1.0, "degenerate": True,
                     "note": f"BUILD FAILED: {type(e).__name__}: {e}"}
                    for ch in cand.channels]
            rob, arows, diag, dt = [], [], {}, 0.0
        all_rows += rows
        all_robust += rob
        all_alpha += arows
        all_diag[cand.num] = diag
        best = min(rows, key=lambda r: r["p_value"])
        print(f"  [{i:>2}/{len(cands)}] #{cand.num:<3} {cand.name:<32} "
              f"best p={best['p_value']:.3f} delta={best['delta_mae']} "
              f"ch={best['channel']} ({dt:.1f}s)")

    res = pd.DataFrame(all_rows)
    # BH across ALL screened tests (candidate x channel)
    res["q_value"] = bh_adjust(res["p_value"].to_numpy(float))
    res["bh_pass"] = res["q_value"] <= FDR_Q
    res["survives"] = res["bh_pass"] & res["sign_consistent"]
    res = res.sort_values(["survives", "q_value", "delta_mae"],
                          ascending=[False, True, True]).reset_index(drop=True)
    res.to_csv(OUTDIR / "screen_results.csv", index=False)

    rob = pd.DataFrame(all_robust)
    rob.to_csv(OUTDIR / "robustness_min15.csv", index=False)
    pd.DataFrame(all_alpha).to_csv(OUTDIR / "alpha_curves.csv", index=False)
    base_curves.to_csv(OUTDIR / "baseline_alpha_curves.csv", index=False)

    surv = res[res["survives"]].copy()
    surv_rob = rob.set_index(["catalog_number", "channel"]) if len(rob) else None
    if len(surv) and surv_rob is not None:
        surv = surv.merge(rob[["catalog_number", "channel", "delta_mae_min15",
                               "sign_min15"]], on=["catalog_number", "channel"],
                          how="left")
    surv.to_csv(OUTDIR / "survivor_summary.csv", index=False)

    # top-20 diagnostics (by q, then delta) with null quantiles
    top = res.head(20).copy()
    drows = []
    for _, r in top.iterrows():
        d = all_diag.get(r["catalog_number"], {}).get(r["channel"], {})
        drows.append({**r.to_dict(), **d})
    pd.DataFrame(drows).to_csv(DIAG / "top20_diagnostics.csv", index=False)

    with open(OUTDIR / "quarantine_audit.json", "w") as f:
        json.dump({"cutoff": str(QUARANTINE_CUTOFF.date()),
                   "all_pass": all(a["pass"] for a in ctx.audit),
                   "matrices": ctx.audit}, f, indent=2)

    write_report(res, rob, surv, base_ref, chosen, args, ctx,
                 time.time() - t_start, len(cands))
    n_tests = len(res)
    print(f"\n[done] {n_tests} tests, {int(res['survives'].sum())} survivors "
          f"({int(res['bh_pass'].sum())} BH-pass), "
          f"expected false at q<={FDR_Q}: ~{FDR_Q * int(res['bh_pass'].sum()):.1f}; "
          f"runtime {time.time() - t_start:.0f}s")
    return 0


def write_report(res, rob, surv, base_ref, chosen, args, ctx, runtime, n_cands):
    n_tests = len(res)
    n_bh = int(res["bh_pass"].sum())
    n_surv = int(res["survives"].sum())
    n_p05 = int((res["p_value"] <= 0.05).sum())
    hist, edges = np.histogram(res["p_value"].dropna(), bins=np.arange(0, 1.05, 0.05))
    lines = []
    A = lines.append
    A("# player_feature_screen_v1 — screening report")
    A("")
    A(f"*Generated by feature_lab.py; runtime {runtime:.0f}s; {args.perms} "
      f"permutations per test; ridge lambda={RIDGE_LAMBDA} on standardized inputs.*")
    A("")
    A("## Protocol (as registered; deviations documented below)")
    A("")
    A("- Screening window 2021-2024 ONLY; quarantine asserted on every matrix "
      "(`quarantine_audit.json`, all-pass="
      f"{all(a['pass'] for a in ctx.audit)}, {len(ctx.audit)} matrices).")
    A("- Targets: per-36 channel production (fg3=3*fg3m, paint=points_paint, "
      "ft=ftm, np2=pts-3*fg3m-ftm-points_paint) on played RS rows, minutes>=8, "
      ">=5 prior same-season appearances. Robustness rerun at minutes>=15.")
    A("- Baseline: shifted per-player ratio-EWMA rate (EWMA(channel pts)/"
      "EWMA(minutes)*36), alpha tuned per channel on the 3 inner walk-forward "
      f"folds of 2021-2023 (evalharness.inner_tuning_splits), frozen: {chosen}.")
    A("- Candidate model: ridge [baseline, feature] fit 2021-2023, scored 2024. "
      "delta = MAE(ridge[b,f]) - MAE(ridge[b]) — the ridge-recalibrated "
      "baseline is the reference, so the delta isolates the feature's marginal "
      "information; the raw-EWMA baseline MAE is reported below and the "
      "permutation null uses the identical statistic.")
    A("- EWMA-carrying features sweep alpha {0.05..0.50 step 0.05} on inner "
      "folds only, frozen per channel before 2024 is touched (#92 sweeps its "
      "blend weight 0.1..0.9 through the same engine).")
    A(f"- Null: {args.perms} within-season permutations of the FEATURE VALUES "
      "on train AND validation, refit, rescore. Permuting the feature leaves "
      "the (baseline, target) pairing untouched — the baseline's information "
      "is fully preserved — while destroying the feature's alignment with "
      "specific player-games; within-season blocks keep each season's "
      "marginal feature distribution, so season-level shifts earn no credit. "
      "p = (1 + #{null >= obs}) / (1 + n_perm) (add-one correction).")
    A(f"- Benjamini-Hochberg FDR at {FDR_Q:.0%} across all {n_tests} "
      "(candidate x channel) tests; survival additionally requires "
      "sign-consistent improvement (all 3 inner folds AND 2024 negative delta).")
    A("")
    A("## Baseline reference (2024)")
    A("")
    A("| channel | alpha | raw EWMA MAE | ridge-recalibrated MAE |")
    A("|---|---|---|---|")
    for ch, r in base_ref.items():
        A(f"| {ch} | {r['alpha']} | {r['mae_raw_ewma_2024']} | {r['mae_ridge_base_2024']} |")
    A("")
    A("## Headline")
    A("")
    A(f"- **{n_tests} tests** ({n_cands} candidates x relevant channels).")
    A(f"- **p<=0.05 before any correction: {n_p05}** (expected under a global "
      f"null: ~{0.05 * n_tests:.1f}).")
    A(f"- **BH({FDR_Q:.0%}) significant: {n_bh}**; with sign-consistency: "
      f"**{n_surv} survivors**.")
    A(f"- Expected false discoveries among BH-passers at q<={FDR_Q}: "
      f"~{FDR_Q * n_bh:.1f}.")
    A("")
    A("p-value histogram (bin width 0.05, left edge 0):")
    A("")
    A("```")
    A(" ".join(f"{int(h):>4}" for h in hist))
    A("```")
    A("")
    A("## Survivors")
    A("")
    if len(surv):
        A("| # | name | channel | delta | p | q | alpha | folds | min15 |")
        A("|---|---|---|---|---|---|---|---|---|")
        for _, r in surv.iterrows():
            m15 = r.get("delta_mae_min15", "")
            A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
              f"{r['delta_mae']:+.4f} | {r['p_value']:.4f} | {r['q_value']:.4f} | "
              f"{r['alpha_chosen']} | {r['fold_signs']} | {m15} |")
    else:
        A("**None.** The catalog did not beat the trend baseline plus "
          "multiplicity control on this window.")
    A("")
    A("## Interpretation decisions (pinned before results were seen)")
    A("")
    A("- **Delta reference**: ridge-recalibrated baseline (see Protocol). Both "
      "reference MAEs are reported; the null uses the same statistic, so the "
      "p-values are internally consistent.")
    A("- **interaction_with_baseline**: the catalog defines no explicit "
      "baseline interactions — every 'x' in a catalog sketch is built INSIDE "
      "the feature. The mechanism exists in the harness but is False for all "
      "81 candidates.")
    A("- **Schedule facts** (venue, rest, tip hour, refs, opponent identity, "
      "trip position) attach unshifted — they are known pre-tip. Every "
      "performance trend is shifted within (player_id, season).")
    A("- **Cross-season candidates** (#19, 71, 77, 78, 87, 88, 89, 92) use "
      "strictly-prior information across seasons — the honest reading of "
      "'features reset per season' for the cross-season identity family.")
    A("- **Feature NaNs** are mean-filled with FIT-window means at fit time "
      "(inner-fold fills use fold-train means); this is feature encoding, "
      "not raw-data imputation.")
    A("- **Known limitation**: row-exchangeable permutation understates "
      "within-player clustering of slow-moving features (#87/#92 style); "
      "their p-values are honest against the registered null but the "
      "confirmation experiment on 2025-2026 is the real gate.")
    A("")
    A("## Deviations and skips")
    A("")
    A(f"- **Skipped**: {SKIPPED[0]['catalog_number']} "
      f"({SKIPPED[0]['name']}): {SKIPPED[0]['reason']}")
    A("- #10 tip times from PBP wall clock (odds commence times only exist in "
      "the quarantined era).")
    A("- #49/#56 use game-level star splits / team-ppp pair lift (player-level "
      "production attribution inside stint windows is not derivable from "
      "public data).")
    A("- #54 is a context share (possessions alongside >=3 own starters), not "
      "a production split, for the same attribution reason.")
    A("- Opponent/team/ref context EWMAs are fixed at alpha=0.10 "
      "(constitution rule 3 constant); the sweep applies to the candidate's "
      "own core player-trend EWMA.")
    A("- #6/#10/#12/#16 'pooled then personalized' profiles are "
      "personalized-only (shrunk to zero): a train-window pooled constant "
      "would leak across inner folds.")
    A("- Permutation p-values use the add-one correction (never exactly 0).")
    A("")
    A("## Failed builds")
    A("")
    failed = res[res["note"].astype(str).str.startswith("BUILD FAILED")]
    if len(failed):
        for _, r in failed.drop_duplicates("catalog_number").iterrows():
            A(f"- #{r['catalog_number']} {r['name']}: {r['note']}")
    else:
        A("None.")
    A("")
    A("## Case study: the venue features (#1-5)")
    A("")
    cs = res[res["catalog_number"].isin([1, 2, 3, 4, 5])]
    A("| # | name | channel | delta | p | q | survives |")
    A("|---|---|---|---|---|---|---|")
    for _, r in cs.iterrows():
        A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
          f"{r['delta_mae']} | {r['p_value']} | {r['q_value']:.4f} | {r['survives']} |")
    A("")
    A("The catalog's epistemics template predicted these would be weak "
      "(league home lift +0.38/36; personal-lift YoY r=+0.054).")
    A("")
    A("## Files")
    A("")
    A("- `screen_results.csv` — one row per (candidate, channel)")
    A("- `survivor_summary.csv` — survivors only (+ min15 robustness)")
    A("- `robustness_min15.csv` — full >=15-minute rerun (frozen alphas)")
    A("- `alpha_curves.csv`, `baseline_alpha_curves.csv` — inner-fold sweeps")
    A("- `diagnostics/top20_diagnostics.csv` — null quantiles for the top 20")
    A("- `quarantine_audit.json` — per-matrix date audit")
    (OUTDIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
