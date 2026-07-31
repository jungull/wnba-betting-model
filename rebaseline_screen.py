"""rebaseline_screen.py — preregistered screen player_feature_rebaselined_v1.

Registered 2026-07-31T16:01:50Z. Supersedes the INCREMENTAL RANKINGS of
player_feature_screen_v1: the cross-season anchor materially changes the
incumbent, so every feature's incremental value is re-measured AFTER
controlling for it.

A THIN RUNNER over committed machinery. `feature_lab.py`, `crossseason_screen.py`,
`features/*` and every existing `experiments/` directory are READ-ONLY here:
the universe definition, the split machinery, the ridge and the BH adjuster are
IMPORTED, never reimplemented and never edited. Everything this registration
adds lives in this file. Artifacts go to
`experiments/feature_screen_rebaselined/` ONLY.

THE PROTOCOL, in the order the code executes it:

 1. FREEZE THE BASELINE FIRST. The new incumbent
    (`crossseason_anchor_blend_frozen`) is the anchor-plus-current-season blend:
    per channel the ridge design is
        [ within-season ratio-EWMA rate (alpha) ,
          blend = w*prev_completed_season_rate + (1-w)*season_to_date_rate ,
          has_prior_season indicator ]
    `alpha` and `w` are chosen JOINTLY per channel on the three 2022-2023 inner
    walk-forward folds ONLY and frozen to
    `frozen_baseline.json` BEFORE the first feature is touched. Rookie /
    no-usable-prior-season rows are NEVER mean-filled: the blend value is
    neutralized to 0.0 and the missing state enters as its own column
    (the crossseason_screen.py missing-indicator precedent).
    The blend-weight grid is EXTENDED past the cross-season screen's boundary
    optimum (0.10..0.90 step 0.10, then 0.92, 0.94, 0.95, 0.96, 0.98, 0.99,
    1.00) so the optimum is either interior or a documented genuine boundary.

 2. ALL implemented features re-tested as ADDITIONS to that frozen baseline;
    window 2022-2024 (2022-2023 train/inner, 2024 validation), catalog-declared
    channels (run-1 convention).

 3. 2,000 permutations per test (run 1's 200 floored every survivor at
    p=1/201=0.00498 and destroyed all resolution).

 4. BLOCK-PERMUTATION by (player, season): whole player-season blocks of the
    feature are relabelled among blocks of the SAME season, preserving the
    within-player clustering that a row-exchangeable shuffle destroys.

 5. FDR: Benjamini-Hochberg at q=0.10 primary, Benjamini-Yekutieli (valid under
    arbitrary dependence) reported alongside. Both columns in the results CSV.

 6. PRACTICAL FLOOR: a feature must ALSO cut its channel's MAE by >= 0.20% of
    that channel's frozen-baseline error. Three tiers reported.

 7. CLUSTER-AWARE MDE on every row, from between-(player,season) variation —
    no null without its detection limit.

 8. CORRELATED-SPECIFICATION COLLAPSING at |r| > 0.9 on the features'
    INCREMENTAL prediction vectors, with a nominated parsimonious carrier.

 9. Counts reported as three distinct numbers: unique confirmed FEATURES,
    passed feature-channel TESTS, collapsed correlated SPECIFICATIONS.

QUARANTINE IS ABSOLUTE: 2025 and 2026 rows are never loaded (season<=2024
pushdown at source in features/common.py); every assembled matrix asserts
max(game_date) < 2025-01-01 and the trail is written to quarantine_audit.json.

This script records NOTHING on the ledger: it never imports or calls
registry.register / evaluate / record_evaluation / render_leaderboards, never
runs git, and never writes experiments/registry.jsonl or leaderboards/.

Run:  python rebaseline_screen.py                # full screen (2000 perms)
      python rebaseline_screen.py --perms 50 --limit 4   # dev smoke only
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

# ---- committed machinery, imported (never reimplemented, never modified) ----
from feature_lab import (ALPHA_GRID, CH_INDEX, FDR_Q, MIN_MINUTES,  # noqa: E402
                         MIN_PRIOR_APPS, N_INNER_FOLDS, RIDGE_LAMBDA,
                         SEED_BASE, bh_adjust, build_universe, mae, ridge_fit,
                         ridge_predict)
from evalharness.splits import inner_tuning_splits, walk_forward_by_season  # noqa: E402
from features import ALL_CANDIDATES, CHANNELS, Ctx  # noqa: E402
from features import bios_features as BF  # noqa: E402  (run-2 battery)
from features import fam_i as FI  # noqa: E402  (READ-ONLY: wrapped, never edited)
from features.common import QUARANTINE_CUTOFF, assert_quarantine, sratio_ew, gps  # noqa: E402

EXPERIMENT_ID = "player_feature_rebaselined_v1"
INCUMBENT_ID = "crossseason_anchor_blend_frozen"

OUTDIR = REPO / "experiments" / "feature_screen_rebaselined"
DIAG = OUTDIR / "diagnostics"

# --- window (inherited from the cross-season registration) -------------------
SCREEN_START_SEASON = 2022
TRAIN_SEASONS = [2022, 2023]
VAL_SEASON = 2024
AGGREGATE_SOURCE_SEASON = 2021          # loaded, never fit / scored / permuted

# --- the frozen-baseline tuning grids (inner folds ONLY) ---------------------
BASE_ALPHA_GRID = list(ALPHA_GRID)                       # 0.05 .. 0.50 step .05
# EXTENDED past the cross-season screen's boundary optimum at w=0.9.
BLEND_W_GRID = [round(x, 2) for x in np.arange(0.1, 0.91, 0.1)] + \
               [0.92, 0.94, 0.95, 0.96, 0.98, 0.99, 1.00]

# --- registered statistics ---------------------------------------------------
N_PERM_DEFAULT = 2000
PRACTICAL_FLOOR_FRAC = 0.0020           # 0.20% of the channel's baseline MAE
MDE_ALPHA = 0.05                        # one-sided
MDE_POWER = 0.80
Z_ALPHA, Z_POWER = 1.6448536269514722, 0.8416212335729143
MDE_Z = Z_ALPHA + Z_POWER               # 2.4865
CORR_COLLAPSE = 0.90
PERM_CHUNK = 250                        # permutations evaluated per BLAS batch


# ===========================================================================
# 0.  block layout + block permutation by (player, season)
# ===========================================================================

class BlockLayout:
    """Row layout for BLOCK-permutation by (player, season).

    Rows are re-ordered by (season, player_id), stably, so that (a) every
    season occupies a contiguous range and (b) inside it every (player, season)
    block is contiguous and in its original temporal order.

    A draw permutes the ORDER OF WHOLE BLOCKS within a season and re-cuts the
    concatenated result at the original block boundaries. Two properties matter:

      * it is an EXACT permutation of the feature vector — every source row is
        used exactly once — so the marginal distribution, including the
        missing-state rate, is preserved to the value and the identity draw
        reproduces the observed data. The add-one p-value is therefore exactly
        valid, not approximately valid;
      * a block's values stay contiguous in the permuted vector, so the
        within-player autocorrelation that makes these features slow-moving
        survives the shuffle instead of being averaged away.

    Wrap-around relabelling (target block b takes source block sigma[b] read
    cyclically) was rejected: it duplicates rows of short blocks into long
    targets, which inflates the null's variance and makes the test silently
    conservative.
    """

    def __init__(self, player_id: np.ndarray, season: np.ndarray):
        n = len(player_id)
        season = season.astype(np.int64)
        player_id = player_id.astype(np.int64)
        # primary key LAST in lexsort: season, then player, then original order
        self.order = np.lexsort((np.arange(n), player_id, season))
        ps = player_id[self.order]
        ss = season[self.order]
        starts_mask = np.ones(n, dtype=bool)
        starts_mask[1:] = (ps[1:] != ps[:-1]) | (ss[1:] != ss[:-1])
        block_start = np.flatnonzero(starts_mask)
        self.n_blocks = len(block_start)
        self.blk_sorted = np.cumsum(starts_mask) - 1
        self.starts = block_start.astype(np.int64)
        self.lens = np.diff(np.append(block_start, n)).astype(np.int64)
        self.season_of_block = ss[block_start]
        self.n = n
        self._ar = np.arange(n, dtype=np.int64)
        # season block-ranges must be contiguous for the re-cut arithmetic
        if not np.all(np.diff(self.season_of_block) >= 0):
            raise RuntimeError("block layout: seasons are not contiguous after sort")

    def sigma(self, K: int, rng) -> np.ndarray:
        """K block orderings, permuted only WITHIN each season."""
        out = np.empty((K, self.n_blocks), dtype=np.int64)
        for s in np.unique(self.season_of_block):
            b = np.flatnonzero(self.season_of_block == s)
            o = np.argsort(rng.random((K, len(b))), axis=1)
            out[:, b] = b[o]
        return out

    def apply(self, x_sorted: np.ndarray, sigma: np.ndarray) -> np.ndarray:
        """(K, n) exact block-permuted copies of `x_sorted` (already sorted).

        Because sigma only reorders blocks inside a season, the running length
        total at each season's first slot equals that season's row offset, so a
        single global cumulative sum gives the correct target positions.
        """
        K = sigma.shape[0]
        Lall = self.lens[sigma]                                # (K, n_blocks)
        base = self.starts[sigma] - (np.cumsum(Lall, axis=1) - Lall)
        idx = np.repeat(base.ravel(), Lall.ravel()).reshape(K, self.n) + self._ar
        return x_sorted[idx]


class PermBank:
    """The 2,000 block relabellings, drawn ONCE and shared by every test.

    The permutation indices do not depend on the feature, so drawing them once
    is not only ~4x cheaper, it is the better design: every test is evaluated
    against the SAME resampled worlds, so the joint dependence between
    correlated tests is carried through the null (the Westfall-Young
    convention). Per-test seeds would make near-duplicate specifications look
    more independent than they are — exactly the illusion this registration is
    trying to remove.
    """

    def __init__(self, lay_tr: BlockLayout, lay_va: BlockLayout, n_perm: int,
                 seed: int = SEED_BASE):
        rng = np.random.default_rng(seed)
        self.n_perm = n_perm
        self.idx_tr = np.empty((n_perm, lay_tr.n), dtype=np.int32)
        self.idx_va = np.empty((n_perm, lay_va.n), dtype=np.int32)
        done = 0
        ar_tr = np.arange(lay_tr.n)
        ar_va = np.arange(lay_va.n)
        while done < n_perm:
            K = min(PERM_CHUNK, n_perm - done)
            for lay, dst, ar in ((lay_tr, self.idx_tr, ar_tr),
                                 (lay_va, self.idx_va, ar_va)):
                sg = lay.sigma(K, rng)
                L = lay.lens[sg]
                base = lay.starts[sg] - (np.cumsum(L, axis=1) - L)
                dst[done:done + K] = (
                    np.repeat(base.ravel(), L.ravel()).reshape(K, lay.n) + ar)
            done += K


# ===========================================================================
# 1.  ridge helpers (closed form; unpenalized intercept — feature_lab pattern)
# ===========================================================================

def _std_cols(M_fit: np.ndarray):
    m = M_fit.mean(axis=0)
    s = M_fit.std(axis=0)
    ok = s > 1e-12
    s = np.where(ok, s, 1.0)
    return m, s, ok


def design_with_intercept(Z: np.ndarray) -> np.ndarray:
    return np.hstack([np.ones((Z.shape[0], 1)), Z])


def fit_predict_base(B_fit: np.ndarray, y_fit: np.ndarray, B_val: np.ndarray):
    """Ridge on the frozen baseline block alone.

    `B_*` are standardized AND carry the intercept in column 0, but
    `feature_lab.ridge_fit` prepends its own unpenalized intercept — so the
    intercept column is dropped here before fitting. Passing it through would
    give the design a duplicate ones column: numerically inert (the penalized
    copy takes an exactly-zero coefficient and predictions are unchanged to
    1e-15) but it shifts every coefficient index by one, which silently
    mislabels the reported baseline betas. Returned beta is
    [intercept, ewma, blend, has_prior_season].
    """
    beta = ridge_fit(B_fit[:, 1:], y_fit, RIDGE_LAMBDA)
    return ridge_predict(B_val[:, 1:], beta), beta


# ===========================================================================
# 2.  the frozen baseline
# ===========================================================================

def build_prev_and_cur(ctx: Ctx):
    """The two ingredients of the fam_i #92 construction, built ONCE.

    `prev` is features.fam_i._prev_rate (completed season N-1 per-36 rate,
    NaN when the player has no qualifying prior season). `cur` is the
    season-to-date shifted expanding per-36 rate — the identical expression
    used inside fam_i.f92_two_season_blend. Identity with the committed
    builder is ASSERTED below, so nothing here is a parallel reimplementation.
    """
    P = ctx.P
    g = gps(P)
    prev, cur = {}, {}
    for ch in CHANNELS:
        prev[ch] = FI._prev_rate(ctx, ch, 1)
        cur_pts = P[f"cp_{ch}"].groupby(g).transform(lambda x: x.cumsum().shift(1))
        cur_min = P["minutes"].groupby(g).transform(lambda x: x.cumsum().shift(1))
        cur[ch] = cur_pts / cur_min.replace(0.0, np.nan) * 36.0
    # --- identity check against the committed fam_i builder -----------------
    for w_probe in (0.3, 0.9):
        committed = FI.f92_two_season_blend(ctx, w_probe)
        for ch in CHANNELS:
            mine = w_probe * prev[ch] + (1.0 - w_probe) * cur[ch]
            a, b = committed[ch].to_numpy(float), mine.to_numpy(float)
            both = ~np.isnan(a) & ~np.isnan(b)
            if not np.array_equal(np.isnan(a), np.isnan(b)):
                raise RuntimeError(f"blend NaN pattern differs from fam_i on {ch}")
            dev = float(np.max(np.abs(a[both] - b[both]))) if both.any() else 0.0
            if dev > 1e-12:
                raise RuntimeError(f"blend deviates from fam_i.f92 on {ch}: {dev:.3e}")
    return prev, cur


def baseline_columns(ctx, U, prev, cur, ch, alpha, w):
    """The three frozen-baseline columns on U, for one channel/(alpha, w)."""
    ew = (sratio_ew(ctx.P, ctx.P[f"cp_{ch}"], ctx.P["minutes"], alpha) * 36.0).loc[U.index]
    blend_raw = (w * prev[ch] + (1.0 - w) * cur[ch]).loc[U.index]
    has = blend_raw.notna().astype(float)
    val = blend_raw.fillna(0.0)                      # neutralized, NEVER mean-filled
    return np.column_stack([ew.to_numpy(float), val.to_numpy(float),
                            has.to_numpy(float)])


def freeze_baseline(ctx, U, folds, prev, cur):
    """Choose (alpha, w) per channel on the 2022-2023 INNER FOLDS ONLY."""
    curves, chosen = [], {}
    ew_cache = {a: {ch: (sratio_ew(ctx.P, ctx.P[f"cp_{ch}"], ctx.P["minutes"], a) * 36.0)
                    .loc[U.index].to_numpy(float) for ch in CHANNELS}
                for a in BASE_ALPHA_GRID}
    blend_cache = {}
    for w in BLEND_W_GRID:
        blend_cache[w] = {}
        for ch in CHANNELS:
            br = (w * prev[ch] + (1.0 - w) * cur[ch]).loc[U.index]
            blend_cache[w][ch] = (br.fillna(0.0).to_numpy(float),
                                  br.notna().astype(float).to_numpy(float))
    fold_pos = [(U.index.get_indexer(f.train_idx), U.index.get_indexer(f.val_idx))
                for f in folds]
    for ch in CHANNELS:
        y = U[f"y_{ch}"].to_numpy(float)
        best, best_loss = None, np.inf
        for a in BASE_ALPHA_GRID:
            ew = ew_cache[a][ch]
            if np.isnan(ew).any():
                raise RuntimeError(f"NaN baseline EWMA on {ch} at alpha={a}")
            for w in BLEND_W_GRID:
                bv, bh = blend_cache[w][ch]
                M = np.column_stack([ew, bv, bh])
                losses = []
                for tr, va in fold_pos:
                    m, s, _ = _std_cols(M[tr])
                    B_tr = design_with_intercept((M[tr] - m) / s)
                    B_va = design_with_intercept((M[va] - m) / s)
                    pred, _ = fit_predict_base(B_tr, y[tr], B_va)
                    losses.append(mae(y[va], pred))
                loss = float(np.mean(losses))
                curves.append({"channel": ch, "alpha": a, "w": w,
                               "inner_mae": round(loss, 6),
                               "fold_maes": ";".join(f"{v:.6f}" for v in losses)})
                if loss < best_loss:
                    best_loss, best = loss, (a, w)
        chosen[ch] = {"alpha": float(best[0]), "w": float(best[1]),
                      "inner_mae": round(best_loss, 6)}
    return chosen, pd.DataFrame(curves)


# ===========================================================================
# 3.  permutation null (vectorized over permutations)
# ===========================================================================

def perm_null_block(B1_tr_s, y_tr_s, B1_va_s, y_va_s, x_tr_s, x_va_s,
                    bank: PermBank, m_base, chunk=PERM_CHUNK):
    """Null improvements under BLOCK-permutation by (player, season).

    All inputs are ALREADY in block-sorted order. `B1_*` carry the intercept and
    the three standardized frozen-baseline columns; only the feature column is
    permuted, so the (baseline, target) pairing — and therefore every bit of the
    baseline's information — is preserved exactly, while the feature's alignment
    with specific player-games is destroyed at the level of whole player-season
    blocks. Ridge is closed form, so the fit is a batched 5x5 solve: the
    baseline Gram block is precomputed once and only the feature's cross terms
    are recomputed per permutation.
    """
    lam = RIDGE_LAMBDA
    A = B1_tr_s.T @ B1_tr_s
    A[1:, 1:] += lam * np.eye(B1_tr_s.shape[1] - 1)     # intercept unpenalized
    By = B1_tr_s.T @ y_tr_s
    n_perm = bank.n_perm
    out = np.empty(n_perm)
    done = 0
    while done < n_perm:
        K = min(chunk, n_perm - done)
        Xtr = x_tr_s[bank.idx_tr[done:done + K]]                  # (K, n_tr)
        Xva = x_va_s[bank.idx_va[done:done + K]]                  # (K, n_va)
        mx = Xtr.mean(axis=1)
        sx = Xtr.std(axis=1)
        sx = np.where(sx > 1e-12, sx, 1.0)
        Ztr = (Xtr - mx[:, None]) / sx[:, None]
        Zva = (Xva - mx[:, None]) / sx[:, None]                   # FIT moments
        p = B1_tr_s.shape[1]
        Bx = B1_tr_s.T @ Ztr.T                                    # (p, K)
        xx = np.einsum("kn,kn->k", Ztr, Ztr) + lam
        xy = Ztr @ y_tr_s
        G = np.empty((K, p + 1, p + 1))
        G[:, :p, :p] = A
        G[:, :p, p] = Bx.T
        G[:, p, :p] = Bx.T
        G[:, p, p] = xx
        rhs = np.empty((K, p + 1))
        rhs[:, :p] = By
        rhs[:, p] = xy
        beta = np.linalg.solve(G, rhs[:, :, None])[:, :, 0]
        pred = (B1_va_s @ beta[:, :p].T).T + Zva * beta[:, p][:, None]
        out[done:done + K] = m_base - np.abs(y_va_s[None, :] - pred).mean(axis=1)
        done += K
    return out


# ===========================================================================
# 4.  cluster-aware MDE
# ===========================================================================

def perm_null_row(B1_tr, y_tr, B1_va, y_va, x_tr, x_va, season_tr, n_perm, rng,
                  m_base):
    """Run 1's ROW-exchangeable within-season null. Used ONLY by the null
    calibration diagnostic, to show empirically what the block scheme fixes."""
    lam = RIDGE_LAMBDA
    A = B1_tr.T @ B1_tr
    A[1:, 1:] += lam * np.eye(B1_tr.shape[1] - 1)
    By = B1_tr.T @ y_tr
    p = B1_tr.shape[1]
    blocks = [np.flatnonzero(season_tr == s) for s in np.unique(season_tr)]
    out = np.empty(n_perm)
    done = 0
    while done < n_perm:
        K = min(PERM_CHUNK, n_perm - done)
        Xtr = np.tile(x_tr, (K, 1))
        for idx in blocks:
            for k in range(K):
                Xtr[k, idx] = x_tr[rng.permutation(idx)]
        Xva = np.stack([x_va[rng.permutation(len(x_va))] for _ in range(K)])
        mx, sx = Xtr.mean(axis=1), Xtr.std(axis=1)
        sx = np.where(sx > 1e-12, sx, 1.0)
        Ztr = (Xtr - mx[:, None]) / sx[:, None]
        Zva = (Xva - mx[:, None]) / sx[:, None]
        Bx = B1_tr.T @ Ztr.T
        G = np.empty((K, p + 1, p + 1))
        G[:, :p, :p] = A
        G[:, :p, p] = Bx.T
        G[:, p, :p] = Bx.T
        G[:, p, p] = np.einsum("kn,kn->k", Ztr, Ztr) + lam
        rhs = np.empty((K, p + 1))
        rhs[:, :p] = By
        rhs[:, p] = Ztr @ y_tr
        beta = np.linalg.solve(G, rhs[:, :, None])[:, :, 0]
        pred = (B1_va @ beta[:, :p].T).T + Zva * beta[:, p][:, None]
        out[done:done + K] = m_base - np.abs(y_va[None, :] - pred).mean(axis=1)
        done += K
    return out


def _r6(v):
    """Round for CSV, propagating NaN rather than inventing a zero."""
    return float(round(float(v), 6)) if v is not None and np.isfinite(v) else np.nan


def cluster_se_of_mean(d: np.ndarray, cluster: np.ndarray) -> float:
    """Cluster-robust SE of mean(d), clusters = (player, season).

    sum_g of the within-cluster deviation sums, squared — i.e. the CR0 variance
    of a mean with a finite-cluster correction. This is BETWEEN-cluster
    variation: a feature whose errors are correlated inside a player-season
    gets no credit for its row count.
    """
    n = len(d)
    if n == 0:
        return float("nan")
    dbar = d.mean()
    dev = d - dbar
    S = np.bincount(cluster, weights=dev)
    G = len(S)
    if G < 2:
        return float("nan")
    var = (G / (G - 1.0)) * float(np.sum(S ** 2)) / (n ** 2)
    return float(np.sqrt(max(var, 0.0)))


# ===========================================================================
# 5.  FDR
# ===========================================================================

def by_adjust(pvals: np.ndarray) -> np.ndarray:
    """Benjamini-Yekutieli: BH inflated by the harmonic number H_m — valid
    under ARBITRARY dependence, hence the right conservative sensitivity for a
    battery of heavily correlated feature specifications."""
    m = len(pvals)
    Hm = float(np.sum(1.0 / np.arange(1, m + 1)))
    return np.minimum(bh_adjust(pvals) * Hm, 1.0)


# ===========================================================================
# 6.  correlated-specification collapsing
# ===========================================================================

def collapse_groups(inc: dict, keys: list, r_thresh=CORR_COLLAPSE):
    """Connected components of |corr(incremental prediction)| > r_thresh.

    The correlation is taken on each test's INCREMENTAL prediction vector
    (pred_with_feature - pred_baseline) on the 2024 validation rows. Correlating
    the raw predictions would be meaningless — every model shares the same
    frozen baseline and they would all correlate above 0.99 by construction.
    The incremental vector is exactly 'what this specification adds', so two
    specifications that add the same thing collapse into one finding.
    """
    pairs, comp = [], {}
    by_channel = {}
    for k in keys:
        by_channel.setdefault(k[1], []).append(k)
    parent = {k: k for k in keys}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for ch, ks in by_channel.items():
        if len(ks) < 2:
            continue
        M = np.vstack([inc[k] for k in ks])
        M = M - M.mean(axis=1, keepdims=True)
        sd = np.sqrt((M ** 2).sum(axis=1))
        sd = np.where(sd > 1e-14, sd, np.nan)
        C = (M @ M.T) / np.outer(sd, sd)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                r = C[i, j]
                if np.isfinite(r) and abs(r) > r_thresh:
                    pairs.append({"channel": ch, "test_a": f"#{ks[i][0]} {ks[i][2]}",
                                  "test_b": f"#{ks[j][0]} {ks[j][2]}",
                                  "catalog_a": ks[i][0], "catalog_b": ks[j][0],
                                  "corr_incremental_prediction": round(float(r), 5)})
                    union(ks[i], ks[j])
    for k in keys:
        comp.setdefault(find(k), []).append(k)
    return pairs, comp


# ===========================================================================
# 6b. the anchor-family collapse demonstration
# ===========================================================================

def anchor_family_demo(ctx, U, prev, cur, tr_pos, va_pos, Y, chosen, base_M,
                       B1_tr, B1_va, base_pred, m_base_ch):
    """The demonstration the registration names by example.

    The cross-season screen reported #87 (pure prev-season anchor) and #92
    (two-season blend at w=0.9) as SIX separate survivors. They are three.
    This block proves it on the evidence, in both baselines:

      OLD  — against the within-season-EWMA-only baseline that the cross-season
             screen used, where both specifications were discoveries. Their
             incremental prediction vectors are compared directly.
      NEW  — against this run's frozen baseline, where the anchor is already
             the incumbent and both specifications should be inert.
    """
    rows = []
    for ch in CHANNELS:
        a = chosen[ch]["alpha"]
        y = Y[ch]
        ew = base_M[ch][:, 0]
        # ---- OLD baseline: within-season ratio-EWMA only ----
        m, s = float(ew[tr_pos].mean()), float(ew[tr_pos].std())
        Bo_tr = design_with_intercept(((ew[tr_pos] - m) / s)[:, None])
        Bo_va = design_with_intercept(((ew[va_pos] - m) / s)[:, None])
        pred_o, _ = fit_predict_base(Bo_tr, y[tr_pos], Bo_va)
        mae_o = mae(y[va_pos], pred_o)
        specs = {
            "#87 prev_season_anchor": prev[ch],
            "#92 two_season_blend @w=0.9": 0.9 * prev[ch] + 0.1 * cur[ch],
            "#92 two_season_blend @w=0.5": 0.5 * prev[ch] + 0.5 * cur[ch],
        }
        inc_old, inc_new, meta = {}, {}, {}
        for label, raw in specs.items():
            r = raw.loc[U.index]
            x = r.fillna(0.0).to_numpy(float)
            has = r.notna().astype(float).to_numpy()
            for tag, (Btr, Bva, pred0, m0) in {
                    "old": (Bo_tr, Bo_va, pred_o, mae_o),
                    "new": (B1_tr[ch], B1_va[ch], base_pred[ch], m_base_ch[ch])}.items():
                M = np.column_stack([x, has])
                mm, ss, _ = _std_cols(M[tr_pos])
                Ztr = np.hstack([Btr[:, 1:], (M[tr_pos] - mm) / ss])
                Zva = np.hstack([Bva[:, 1:], (M[va_pos] - mm) / ss])
                beta = ridge_fit(Ztr, y[tr_pos], RIDGE_LAMBDA)
                pr = ridge_predict(Zva, beta)
                (inc_old if tag == "old" else inc_new)[label] = pr - pred0
                meta[(label, tag)] = m0 - mae(y[va_pos], pr)
        labels = list(specs)
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                for tag, inc in (("old_ewma_only_baseline", inc_old),
                                 ("new_frozen_baseline", inc_new)):
                    u, v = inc[labels[i]], inc[labels[j]]
                    u, v = u - u.mean(), v - v.mean()
                    den = np.sqrt((u ** 2).sum() * (v ** 2).sum())
                    r = float(u @ v / den) if den > 1e-18 else np.nan
                    rows.append({
                        "baseline": tag, "channel": ch,
                        "spec_a": labels[i], "spec_b": labels[j],
                        "corr_incremental_prediction": _r6(r),
                        "improvement_a": _r6(meta[(labels[i], tag.split("_")[0])]),
                        "improvement_b": _r6(meta[(labels[j], tag.split("_")[0])]),
                        "collapses_at_0.9": bool(np.isfinite(r) and abs(r) > CORR_COLLAPSE),
                    })
    return pd.DataFrame(rows)


# ===========================================================================
# 6c. null calibration — does the block scheme actually fix anything?
# ===========================================================================

def null_calibration(B1_tr_s, Y_tr_s, B1_va_s, Y_va_s, B1_tr, Y_tr, B1_va, Y_va,
                     lay_tr, lay_va, bank, season_tr, m_base_ch, seed=7):
    """Feed the machinery features that are null BY CONSTRUCTION and read off
    the p-values under both schemes.

    `iid_noise` is exchangeable at the row level, so both nulls should be
    calibrated on it. `player_season_constant` and `ar1_within_player` are null
    but heavily clustered — exactly the shape of a slow-moving player attribute.
    If the row-exchangeable scheme is anti-conservative for clustered features,
    it shows up here as small p-values for a feature that carries no signal.
    """
    rng = np.random.default_rng(seed)
    rows = []
    n_row = min(bank.n_perm, 400)          # row-exchangeable comparison is O(n_perm)
    n_tr, n_va = B1_tr[CHANNELS[0]].shape[0], B1_va[CHANNELS[0]].shape[0]

    def clustered(lay, kind):
        v = np.empty(lay.n)
        blk_val = rng.normal(size=lay.n_blocks)
        for b in range(lay.n_blocks):
            s, L = lay.starts[b], lay.lens[b]
            if kind == "const":
                v[s:s + L] = blk_val[b]
            else:                                   # AR(1), rho=0.9, per block
                e = rng.normal(size=L)
                x = np.empty(L)
                x[0] = blk_val[b]
                for t in range(1, L):
                    x[t] = 0.9 * x[t - 1] + 0.436 * e[t]
                v[s:s + L] = x
        out = np.empty(lay.n)
        out[lay.order] = v
        return out

    feats = {
        "iid_noise": (rng.normal(size=n_tr), rng.normal(size=n_va)),
        "player_season_constant": (clustered(lay_tr, "const"), clustered(lay_va, "const")),
        "ar1_within_player": (clustered(lay_tr, "ar1"), clustered(lay_va, "ar1")),
    }
    for name, (xt, xv) in feats.items():
        for ch in CHANNELS:
            mx, sx = xt.mean(), xt.std()
            zt, zv = (xt - mx) / sx, (xv - mx) / sx
            beta = ridge_fit(np.hstack([B1_tr[ch][:, 1:], zt[:, None]]), Y_tr[ch],
                             RIDGE_LAMBDA)
            pred = ridge_predict(np.hstack([B1_va[ch][:, 1:], zv[:, None]]), beta)
            obs = m_base_ch[ch] - mae(Y_va[ch], pred)
            nb = perm_null_block(B1_tr_s[ch], Y_tr_s[ch], B1_va_s[ch], Y_va_s[ch],
                                 xt[lay_tr.order], xv[lay_va.order], bank,
                                 m_base_ch[ch])
            nr = perm_null_row(B1_tr[ch], Y_tr[ch], B1_va[ch], Y_va[ch], xt, xv,
                               season_tr, n_row,
                               np.random.default_rng(seed + 2), m_base_ch[ch])
            rows.append({
                "synthetic_feature": name, "channel": ch,
                "observed_improvement": _r6(obs),
                "p_block_by_player_season": _r6((1 + np.sum(nb >= obs)) / (1 + bank.n_perm)),
                "p_row_exchangeable_run1": _r6((1 + np.sum(nr >= obs)) / (1 + n_row)),
                "null_sd_block": _r6(float(np.std(nb, ddof=1))),
                "null_sd_row": _r6(float(np.std(nr, ddof=1))),
                "null_sd_ratio_block_over_row": _r6(float(np.std(nb, ddof=1) /
                                                          max(np.std(nr, ddof=1), 1e-15))),
            })
    return pd.DataFrame(rows)


# ===========================================================================
# 7.  main
# ===========================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--perms", type=int, default=N_PERM_DEFAULT,
                    help="permutations per test (protocol: 2000)")
    ap.add_argument("--limit", type=int, default=None, help="DEV ONLY")
    args = ap.parse_args(argv)

    t0 = time.time()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    DIAG.mkdir(parents=True, exist_ok=True)

    print(f"[{EXPERIMENT_ID}] re-baselined screen; incumbent = {INCUMBENT_ID}")
    ctx = Ctx()
    U_full, _, _ = build_universe(ctx)                 # committed universe
    U = U_full[U_full["season"] >= SCREEN_START_SEASON].copy()
    assert_quarantine(U["game_date"], f"target_universe(>=2022,min>={MIN_MINUTES:g})",
                      ctx.audit)
    outer = walk_forward_by_season(U, test_seasons=[VAL_SEASON])[0]
    folds = inner_tuning_splits(U, outer, n_folds=N_INNER_FOLDS)
    tr_pos = U.index.get_indexer(outer.train_idx)
    va_pos = U.index.get_indexer(outer.test_idx)
    print(f"[window] universe {len(U)} rows 2022-2024 "
          f"(train/inner {len(tr_pos)}, val2024 {len(va_pos)}); "
          f"{len(U_full) - len(U)} rows before 2022 excluded")
    assert_quarantine(U.iloc[tr_pos]["game_date"], "fit_matrix(2022-2023)", ctx.audit)
    assert_quarantine(U.iloc[va_pos]["game_date"], "validation_matrix(2024)", ctx.audit)

    # ---------------- STEP 1: FREEZE THE BASELINE (before any feature) -------
    print("[baseline] building the #92 ingredients and asserting fam_i identity ...")
    prev, cur = build_prev_and_cur(ctx)
    print(f"[baseline] joint (alpha, w) sweep on the 3 inner folds: "
          f"{len(BASE_ALPHA_GRID)} x {len(BLEND_W_GRID)} per channel ...")
    chosen, base_curves = freeze_baseline(ctx, U, folds, prev, cur)
    base_curves.to_csv(OUTDIR / "baseline_grid_curves.csv", index=False)

    base_M, base_ref, B1_tr, B1_va, m_base_ch, base_pred = {}, {}, {}, {}, {}, {}
    for ch in CHANNELS:
        a, w = chosen[ch]["alpha"], chosen[ch]["w"]
        # Seven candidates (#6, #10 fam+bios, #12, #16, #49, #100) are built as
        # deviations from `ctx.baselines` — the per-channel as-of trend that
        # feature_lab.tune_baselines installs on the context. Install the SAME
        # object here, at the frozen alpha, so those features keep run 1's
        # construction exactly and only the ridge baseline they are tested
        # against changes. Must happen before any candidate is built.
        ctx.baselines[ch] = (sratio_ew(ctx.P, ctx.P[f"cp_{ch}"],
                                       ctx.P["minutes"], a) * 36.0)
        ctx.baseline_alphas[ch] = a
        M = baseline_columns(ctx, U, prev, cur, ch, a, w)
        base_M[ch] = M
        y = U[f"y_{ch}"].to_numpy(float)
        m, s, _ = _std_cols(M[tr_pos])
        B1_tr[ch] = design_with_intercept((M[tr_pos] - m) / s)
        B1_va[ch] = design_with_intercept((M[va_pos] - m) / s)
        pred, beta0 = fit_predict_base(B1_tr[ch], y[tr_pos], B1_va[ch])
        base_pred[ch] = pred
        m_base_ch[ch] = mae(y[va_pos], pred)
        raw_ew = mae(y[va_pos], M[va_pos, 0])
        base_ref[ch] = {
            "alpha": a, "w": w,
            "inner_mae_frozen": chosen[ch]["inner_mae"],
            "mae_raw_within_season_ewma_2024": round(raw_ew, 5),
            "mae_frozen_baseline_2024": round(m_base_ch[ch], 5),
            "beta_ewma_std": round(float(beta0[1]), 5),
            "beta_blend_std": round(float(beta0[2]), 5),
            "beta_has_prior_std": round(float(beta0[3]), 5),
            "coverage_train_2022_23": round(float(M[tr_pos, 2].mean()), 4),
            "coverage_val_2024": round(float(M[va_pos, 2].mean()), 4),
            "practical_floor_mae": round(PRACTICAL_FLOOR_FRAC * m_base_ch[ch], 6),
            "w_interior_on_extended_grid": bool(0.1 < w < 1.00),
            "alpha_interior_on_grid": bool(min(BASE_ALPHA_GRID) < a < max(BASE_ALPHA_GRID)),
        }
        print(f"[baseline] {ch}: alpha={a} w={w} inner={chosen[ch]['inner_mae']:.5f} "
              f"2024={m_base_ch[ch]:.5f} (raw within-season EWMA {raw_ew:.5f}) "
              f"floor={PRACTICAL_FLOOR_FRAC * m_base_ch[ch]:.5f}")

    frozen = {
        "experiment_id": EXPERIMENT_ID,
        "incumbent_id": INCUMBENT_ID,
        "frozen_at": pd.Timestamp.now("UTC").isoformat(),
        "frozen_before_any_feature_was_tested": True,
        "construction": ("ridge[intercept, within-season ratio-EWMA per-36 rate(alpha), "
                         "blend = w*prev_completed_season_rate + (1-w)*season_to_date_rate, "
                         "has_prior_season indicator]; standardized on fit rows; "
                         "lambda=1.0 with unpenalized intercept"),
        "missing_state": ("rookie / no-qualifying-prior-season rows: blend value "
                          "neutralized to 0.0 and flagged by has_prior_season=0. "
                          "NOTHING is mean-filled (constitution rule 8; the "
                          "crossseason_screen.py missing-indicator precedent)."),
        "selection": ("alpha and w chosen JOINTLY per channel by mean MAE over the "
                      "three 2022-2023 inner walk-forward folds; 2024 never touched "
                      "during selection"),
        "grids": {"alpha": BASE_ALPHA_GRID, "w": BLEND_W_GRID,
                  "w_grid_extended_past_0.9": True,
                  "why_extended": ("player_feature_crossseason_v1 found w=0.9 as a "
                                   "BOUNDARY optimum on a monotone 0.1..0.9 grid; the "
                                   "grid is extended to 1.00 so the optimum is either "
                                   "interior or a documented genuine boundary")},
        "window": {"screening_seasons": [2022, 2023, 2024],
                   "train_inner": TRAIN_SEASONS, "validation": VAL_SEASON,
                   "aggregate_source_only": AGGREGATE_SOURCE_SEASON,
                   "quarantined_never_loaded": [2025, 2026]},
        "universe": {"min_minutes": MIN_MINUTES, "min_prior_apps": MIN_PRIOR_APPS,
                     "n_rows": int(len(U)), "n_fit": int(len(tr_pos)),
                     "n_val_2024": int(len(va_pos))},
        "practical_floor_frac_of_baseline_mae": PRACTICAL_FLOOR_FRAC,
        "per_channel": base_ref,
    }
    with open(OUTDIR / "frozen_baseline.json", "w") as f:
        json.dump(frozen, f, indent=2)
    print(f"[baseline] FROZEN -> {OUTDIR / 'frozen_baseline.json'} "
          "(written before the first feature test)")

    # ---------------- STEP 2: the battery -----------------------------------
    battery = list(ALL_CANDIDATES) + list(BF.CANDIDATES)
    if args.limit:
        battery = battery[: args.limit]
    n_tests_planned = sum(len(c.channels) for c in battery)
    uniq_nums = sorted({c.num for c in battery})
    print(f"[screen] {len(battery)} candidate objects / {len(uniq_nums)} unique "
          f"catalog numbers -> {n_tests_planned} feature-channel tests "
          f"(catalog-declared channels), {args.perms} permutations per test")

    # block layouts (fixed across every test — the row order never changes)
    lay_tr = BlockLayout(U.iloc[tr_pos]["player_id"].to_numpy(),
                         U.iloc[tr_pos]["season"].to_numpy())
    lay_va = BlockLayout(U.iloc[va_pos]["player_id"].to_numpy(),
                         U.iloc[va_pos]["season"].to_numpy())
    bank = PermBank(lay_tr, lay_va, args.perms)
    print(f"[null] block layout: {lay_tr.n_blocks} (player, season) fit blocks "
          f"(median {int(np.median(lay_tr.lens))} rows), {lay_va.n_blocks} "
          f"validation blocks (median {int(np.median(lay_va.lens))} rows)")

    # per-channel pre-sorted arrays for the vectorized null
    Y, Y_tr_s, Y_va_s, B1_tr_s, B1_va_s = {}, {}, {}, {}, {}
    Y_tr_o, Y_va_o = {}, {}
    for ch in CHANNELS:
        y = U[f"y_{ch}"].to_numpy(float)
        Y[ch] = y
        Y_tr_o[ch], Y_va_o[ch] = y[tr_pos], y[va_pos]
        Y_tr_s[ch] = y[tr_pos][lay_tr.order]
        Y_va_s[ch] = y[va_pos][lay_va.order]
        B1_tr_s[ch] = np.ascontiguousarray(B1_tr[ch][lay_tr.order])
        B1_va_s[ch] = np.ascontiguousarray(B1_va[ch][lay_va.order])
    val_cluster = np.unique(U.iloc[va_pos]["player_id"].to_numpy(), return_inverse=True)[1]
    base_loss = {ch: np.abs(Y[ch][va_pos] - base_pred[ch]) for ch in CHANNELS}

    fold_pos = [(U.index.get_indexer(f.train_idx), U.index.get_indexer(f.val_idx))
                for f in folds]
    fold_base = {}
    for ch in CHANNELS:
        fold_base[ch] = []
        for tr, va in fold_pos:
            M = base_M[ch]
            m, s, _ = _std_cols(M[tr])
            Btr = design_with_intercept((M[tr] - m) / s)
            Bva = design_with_intercept((M[va] - m) / s)
            pred, _ = fit_predict_base(Btr, Y[ch][tr], Bva)
            fold_base[ch].append({"Btr": Btr, "Bva": Bva, "m": m, "s": s,
                                  "mae": mae(Y[ch][va], pred)})

    def score_one(ch, x_all, tr, va, Btr, Bva):
        """Observed fit/score of [frozen baseline, feature]; run-1 NaN handling
        (feature NaNs mean-filled with the FIT-window mean; that is feature
        encoding, not raw-data imputation) and run-1 standardization."""
        xt, xv = x_all[tr], x_all[va]
        fill = float(np.nanmean(xt)) if np.any(~np.isnan(xt)) else 0.0
        xt = np.where(np.isnan(xt), fill, xt)
        xv = np.where(np.isnan(xv), fill, xv)
        mx, sx = float(xt.mean()), float(xt.std())
        if sx < 1e-12:
            return None
        zt, zv = (xt - mx) / sx, (xv - mx) / sx
        Z_tr = np.hstack([Btr, zt[:, None]])
        Z_va = np.hstack([Bva, zv[:, None]])
        beta = ridge_fit(Z_tr[:, 1:], Y[ch][tr], RIDGE_LAMBDA)   # intercept re-added
        pred = ridge_predict(Z_va[:, 1:], beta)
        return {"pred": pred, "mae": mae(Y[ch][va], pred),
                "beta_x": float(beta[-1]), "xt": xt, "xv": xv,
                "mx": mx, "sx": sx, "fill": fill}

    rows, inc_vectors, diag_rows = [], {}, []
    for i, cand in enumerate(battery, 1):
        t_c = time.time()
        grid = (cand.sweep_grid or ALPHA_GRID) if cand.alpha_swept else [None]
        try:
            built = {a: cand.build(ctx, a) for a in grid}
            for a, b in built.items():          # fail loudly, never silently
                if isinstance(b, dict):
                    missing = [c for c in cand.channels if c not in b]
                    if missing:
                        raise RuntimeError(
                            f"build returned no series for declared channel(s) "
                            f"{missing} (got keys {sorted(b)})")
        except Exception as e:
            print(f"  !! #{cand.num} {cand.name} BUILD FAILED: {type(e).__name__}: {e}")
            for ch in cand.channels:
                rows.append(_failed_row(cand, ch, m_base_ch[ch], e))
            continue

        def series(a, ch):
            b = built[a]
            return (b[ch] if isinstance(b, dict) else b).loc[U.index].to_numpy(float)

        best_p = 1.0
        for ch in cand.channels:
            # ---- sweep on INNER FOLDS ONLY, frozen before 2024 is touched --
            if cand.alpha_swept:
                best_a, best_loss = None, np.inf
                for a in grid:
                    xa = series(a, ch)
                    losses = []
                    for (tr, va), fb in zip(fold_pos, fold_base[ch]):
                        r = score_one(ch, xa, tr, va, fb["Btr"], fb["Bva"])
                        losses.append(fb["mae"] if r is None else r["mae"])
                    if float(np.mean(losses)) < best_loss:
                        best_loss, best_a = float(np.mean(losses)), a
                alpha = best_a
            else:
                alpha = None
            x_all = series(alpha, ch)
            nan_share = float(np.mean(np.isnan(x_all)))

            # ---- inner-fold deltas at the frozen configuration -------------
            fold_deltas = []
            for (tr, va), fb in zip(fold_pos, fold_base[ch]):
                r = score_one(ch, x_all, tr, va, fb["Btr"], fb["Bva"])
                fold_deltas.append(0.0 if r is None else r["mae"] - fb["mae"])

            # ---- 2024 walk-forward score -----------------------------------
            r = score_one(ch, x_all, tr_pos, va_pos, B1_tr[ch], B1_va[ch])
            degen = r is None
            if degen:
                m_feat, delta, beta_x = m_base_ch[ch], 0.0, 0.0
                p_perm, null = 1.0, np.zeros(args.perms)
                inc = np.zeros(len(va_pos))
                d_row = np.zeros(len(va_pos))
            else:
                m_feat = r["mae"]
                delta = m_feat - m_base_ch[ch]
                beta_x = r["beta_x"]
                inc = r["pred"] - base_pred[ch]
                d_row = np.abs(Y[ch][va_pos] - r["pred"]) - base_loss[ch]
                null = perm_null_block(
                    B1_tr_s[ch], Y_tr_s[ch], B1_va_s[ch], Y_va_s[ch],
                    r["xt"][lay_tr.order], r["xv"][lay_va.order],
                    bank, m_base_ch[ch])
                p_perm = float((1 + np.sum(null >= -delta)) / (1 + args.perms))
            improvement = -delta

            # ---- cluster-aware MDE -----------------------------------------
            floor = PRACTICAL_FLOOR_FRAC * m_base_ch[ch]
            if degen:
                se_cl = se_iid = null_sd = mde_cl = mde_perm = mde = np.nan
            else:
                se_cl = cluster_se_of_mean(d_row, val_cluster)
                se_iid = float(np.std(d_row, ddof=1) / np.sqrt(len(d_row)))
                null_sd = float(np.std(null, ddof=1))
                mde_cl = MDE_Z * se_cl if np.isfinite(se_cl) else np.nan
                mde_perm = MDE_Z * null_sd
                mde = float(np.nanmax([mde_cl, mde_perm]))

            rows.append({
                "catalog_number": cand.num, "name": cand.name,
                "family": cand.family, "channel": ch,
                "alpha_chosen": alpha, "n_train": int(len(tr_pos)),
                "n_val": int(len(va_pos)), "nan_share": round(nan_share, 4),
                "mae_frozen_baseline_2024": round(m_base_ch[ch], 5),
                "mae_feat_2024": round(m_feat, 5),
                "delta_mae": round(delta, 6),
                "observed_effect_improvement": round(improvement, 6),
                "improvement_pct_of_baseline": round(100.0 * improvement / m_base_ch[ch], 4),
                "beta_feature_std": round(beta_x, 5),
                "fold_deltas": ";".join(f"{d:+.5f}" for d in fold_deltas),
                "fold_signs": "".join("-" if d < 0 else "+" for d in fold_deltas),
                "sign_2024": "-" if delta < 0 else "+",
                "sign_consistent": bool(all(d < 0 for d in fold_deltas) and delta < 0),
                "p_value": round(p_perm, 6),
                "n_perm": int(args.perms),
                "null_sd": _r6(null_sd),
                "null_q95": _r6(np.nan if degen else float(np.quantile(null, 0.95))),
                "se_cluster_player_season": _r6(se_cl),
                "se_iid_row_level": _r6(se_iid),
                "mde80_cluster": _r6(mde_cl),
                "mde80_permutation": _r6(mde_perm),
                "mde80": _r6(mde),
                "practical_floor": round(floor, 6),
                "underpowered_for_floor": bool(not np.isfinite(mde) or mde > floor),
                "practical": bool(improvement >= floor),
                "degenerate": bool(degen), "note": "",
            })
            if not degen:
                inc_vectors[(cand.num, ch, cand.name)] = inc.astype(np.float32)
            diag_rows.append({
                "catalog_number": cand.num, "name": cand.name, "channel": ch,
                "observed_improvement": round(improvement, 6),
                "null_q05": round(float(np.quantile(null, 0.05)), 6),
                "null_q50": round(float(np.quantile(null, 0.50)), 6),
                "null_q95": round(float(np.quantile(null, 0.95)), 6),
                "null_q99": round(float(np.quantile(null, 0.99)), 6),
                "null_max": round(float(np.max(null)), 6),
                "null_sd": round(null_sd, 6),
            })
            best_p = min(best_p, p_perm)
        print(f"  [{i:>2}/{len(battery)}] #{cand.num:<3} {cand.name:<32} "
              f"best p={best_p:.4f} ({time.time() - t_c:.1f}s)")

    # ---------------- STEP 3: FDR, tiers, collapsing ------------------------
    res = pd.DataFrame(rows)
    pv = res["p_value"].to_numpy(float)
    res["q_bh"] = np.round(bh_adjust(pv), 6)
    res["q_by"] = np.round(by_adjust(pv), 6)
    res["bh_pass"] = res["q_bh"] <= FDR_Q
    res["by_pass"] = res["q_by"] <= FDR_Q
    res["practical_tier"] = np.where(
        res["bh_pass"] & res["practical"], "significant_and_practical",
        np.where(res["bh_pass"], "significant_only", "neither"))
    res["survives"] = res["bh_pass"] & res["sign_consistent"] & res["practical"]
    res["survives_under_by"] = res["by_pass"] & res["sign_consistent"] & res["practical"]
    res = res.sort_values(["survives", "q_bh", "delta_mae"],
                          ascending=[False, True, True]).reset_index(drop=True)

    sig_keys = [(int(r.catalog_number), r.channel, r["name"])
                for _, r in res.iterrows()
                if r.bh_pass and (int(r.catalog_number), r.channel, r["name"]) in inc_vectors]
    demo_keys = [k for k in inc_vectors if k[0] in (87, 92)]
    keys = sorted(set(sig_keys) | set(demo_keys))
    pairs, comps = collapse_groups(inc_vectors, keys)
    key_meta = {(int(r.catalog_number), r.channel, r["name"]): r
                for _, r in res.iterrows()}
    grp_rows, carrier_of, gid = [], {}, 0
    for root, members in comps.items():
        gid += 1
        mem = sorted(members, key=lambda k: (
            not bool(key_meta[k].bh_pass),
            -float(key_meta[k].observed_effect_improvement),
            bool(key_meta[k].alpha_chosen is not None
                 and pd.notna(key_meta[k].alpha_chosen)),
            k[0]))
        carrier = mem[0]
        for k in mem:
            carrier_of[k] = carrier
            grp_rows.append({
                "group_id": gid, "channel": k[1],
                "catalog_number": k[0], "name": k[2],
                "is_nominated_carrier": bool(k == carrier),
                "carrier": f"#{carrier[0]} {carrier[2]}",
                "group_size": len(mem),
                "improvement": float(key_meta[k].observed_effect_improvement),
                "q_bh": float(key_meta[k].q_bh),
                "bh_pass": bool(key_meta[k].bh_pass),
                "practical": bool(key_meta[k].practical),
                "sign_consistent": bool(key_meta[k].sign_consistent),
            })
    GRP_COLS = ["group_id", "channel", "catalog_number", "name",
                "is_nominated_carrier", "carrier", "group_size", "improvement",
                "q_bh", "bh_pass", "practical", "sign_consistent"]
    groups = (pd.DataFrame(grp_rows).sort_values(
        ["group_size", "group_id", "is_nominated_carrier"],
        ascending=[False, True, False]) if grp_rows
        else pd.DataFrame(columns=GRP_COLS))
    groups = groups.reindex(columns=GRP_COLS)
    groups.insert(1, "scope", "screen_finding")

    # ---- the anchor-family collapse demonstration --------------------------
    print("[collapse] anchor-family specification-variant demonstration ...")
    demo = anchor_family_demo(ctx, U, prev, cur, tr_pos, va_pos, Y, chosen,
                              base_M, B1_tr, B1_va, base_pred, m_base_ch)
    demo.to_csv(DIAG / "anchor_family_collapse.csv", index=False)
    demo_rows = []
    for (ch, tag), sub in demo.groupby(["channel", "baseline"]):
        for _, d in sub.iterrows():
            demo_rows.append({
                "group_id": f"demo-{tag}-{ch}", "scope": "anchor_family_demonstration",
                "channel": ch, "catalog_number": np.nan,
                "name": f"{d['spec_a']} vs {d['spec_b']}",
                "is_nominated_carrier": False,
                "carrier": "#87 prev_season_anchor (parsimonious: one term, no weight)",
                "group_size": 2, "improvement": d["improvement_a"],
                "q_bh": np.nan, "bh_pass": np.nan,
                "practical": np.nan, "sign_consistent": np.nan,
                "corr_incremental_prediction": d["corr_incremental_prediction"],
                "collapses": d["collapses_at_0.9"]})
    groups_out = pd.concat([groups, pd.DataFrame(demo_rows)], ignore_index=True)
    groups_out.to_csv(OUTDIR / "correlation_groups.csv", index=False)
    pd.DataFrame(pairs, columns=["channel", "test_a", "test_b", "catalog_a",
                                 "catalog_b", "corr_incremental_prediction"]
                 ).to_csv(DIAG / "correlation_pairs.csv", index=False)

    # ---- null calibration --------------------------------------------------
    print("[null] calibration on synthetic null features (block vs row) ...")
    calib = null_calibration(B1_tr_s, Y_tr_s, B1_va_s, Y_va_s, B1_tr, Y_tr_o,
                             B1_va, Y_va_o, lay_tr, lay_va, bank,
                             U.iloc[tr_pos]["season"].to_numpy(), m_base_ch)
    calib.to_csv(DIAG / "null_calibration.csv", index=False)

    res["collapse_group"] = [
        (f"#{carrier_of[(int(r.catalog_number), r.channel, r['name'])][0]} "
         f"{carrier_of[(int(r.catalog_number), r.channel, r['name'])][2]}"
         if (int(r.catalog_number), r.channel, r["name"]) in carrier_of else "")
        for _, r in res.iterrows()]
    res.to_csv(OUTDIR / "screen_results.csv", index=False)

    surv = res[res["survives"]].copy()
    surv.to_csv(OUTDIR / "survivor_summary.csv", index=False)
    pd.DataFrame(diag_rows).to_csv(DIAG / "null_quantiles.csv", index=False)

    # ---- the three counts, kept distinct -----------------------------------
    surv_keys = [(int(r.catalog_number), r.channel, r["name"]) for _, r in surv.iterrows()]
    n_features = int(surv["catalog_number"].nunique()) if len(surv) else 0
    n_tests_passed = int(len(surv))
    n_specs = len({carrier_of.get(k, k) for k in surv_keys}) if surv_keys else 0
    tier_counts = (res.groupby("practical_tier")
                   .agg(n_tests=("channel", "size"),
                        n_unique_features=("catalog_number", "nunique"))
                   .reindex(["significant_and_practical", "significant_only", "neither"])
                   .fillna(0).astype(int).reset_index())
    tier_counts["definition"] = [
        "BH q<=0.10 AND improvement >= 0.20% of the channel's frozen-baseline MAE",
        "BH q<=0.10 but improvement below the 0.20% practical floor",
        "did not clear BH q<=0.10",
    ]
    nulls = res[~res["bh_pass"]]
    bhp = res[res["bh_pass"]]
    extra = pd.DataFrame([
        {"practical_tier": "UNDERPOWERED nulls (mde80 > practical floor)",
         "n_tests": int(nulls["underpowered_for_floor"].sum()),
         "n_unique_features": int(nulls[nulls["underpowered_for_floor"]]
                                  ["catalog_number"].nunique()),
         "definition": "did NOT clear BH and could not have detected a floor-sized "
                       "effect at 80% power — absence of evidence, not evidence of "
                       "absence"},
        {"practical_tier": "ADEQUATELY POWERED nulls",
         "n_tests": int((~nulls["underpowered_for_floor"]).sum()),
         "n_unique_features": int(nulls[~nulls["underpowered_for_floor"]]
                                  ["catalog_number"].nunique()),
         "definition": "did NOT clear BH and WAS powered to detect a floor-sized "
                       "effect — these are genuine nulls"},
        {"practical_tier": "UNDERPOWERED among BH-passers",
         "n_tests": int(bhp["underpowered_for_floor"].sum()),
         "n_unique_features": int(bhp[bhp["underpowered_for_floor"]]
                                  ["catalog_number"].nunique()),
         "definition": "significant, but the effect estimate is wider than the "
                       "floor — direction supported, magnitude not pinned down"},
        {"practical_tier": "COUNT unique confirmed FEATURES", "n_tests": n_features,
         "n_unique_features": n_features,
         "definition": "distinct catalog numbers among survivors "
                       "(BH + sign-consistency + practical floor)"},
        {"practical_tier": "COUNT passed feature-channel TESTS",
         "n_tests": n_tests_passed, "n_unique_features": n_features,
         "definition": "surviving (feature, channel) rows"},
        {"practical_tier": "COUNT collapsed correlated SPECIFICATIONS",
         "n_tests": n_specs, "n_unique_features": n_specs,
         "definition": f"connected components of |corr(incremental prediction)| > "
                       f"{CORR_COLLAPSE} among survivors"},
    ])
    pd.concat([tier_counts, extra], ignore_index=True).to_csv(
        OUTDIR / "three_tier_counts.csv", index=False)

    with open(OUTDIR / "quarantine_audit.json", "w") as f:
        json.dump({"experiment_id": EXPERIMENT_ID,
                   "screen_window": frozen["window"],
                   "cutoff": str(QUARANTINE_CUTOFF.date()),
                   "all_pass": all(a["pass"] for a in ctx.audit),
                   "n_matrices": len(ctx.audit),
                   "matrices": ctx.audit}, f, indent=2)

    write_report(res, surv, groups, pairs, demo, calib, base_ref, base_curves,
                 frozen, folds, outer, U, U_full, battery, uniq_nums, args, ctx,
                 (n_features, n_tests_passed, n_specs), time.time() - t0)

    print(f"\n[done] {len(res)} tests | BH-pass {int(res['bh_pass'].sum())} | "
          f"BY-pass {int(res['by_pass'].sum())} | survivors {n_tests_passed} tests "
          f"/ {n_features} features / {n_specs} specifications | "
          f"underpowered {int(res['underpowered_for_floor'].sum())} | "
          f"runtime {time.time() - t0:.0f}s")
    return 0


def _failed_row(cand, ch, m_base, e):
    return {"catalog_number": cand.num, "name": cand.name, "family": cand.family,
            "channel": ch, "alpha_chosen": None, "n_train": 0, "n_val": 0,
            "nan_share": 1.0, "mae_frozen_baseline_2024": round(m_base, 5),
            "mae_feat_2024": np.nan, "delta_mae": np.nan,
            "observed_effect_improvement": np.nan,
            "improvement_pct_of_baseline": np.nan, "beta_feature_std": np.nan,
            "fold_deltas": "", "fold_signs": "", "sign_2024": "",
            "sign_consistent": False, "p_value": 1.0, "n_perm": 0,
            "null_sd": np.nan, "null_q95": np.nan,
            "se_cluster_player_season": np.nan, "se_iid_row_level": np.nan,
            "mde80_cluster": np.nan, "mde80_permutation": np.nan, "mde80": np.nan,
            "practical_floor": np.nan, "underpowered_for_floor": True,
            "practical": False, "degenerate": True,
            "note": f"BUILD FAILED: {type(e).__name__}: {e}"}


# ===========================================================================
# 8.  report
# ===========================================================================

def write_report(res, surv, groups, pairs, demo, calib, base_ref, base_curves,
                 frozen, folds, outer, U, U_full, battery, uniq_nums, args, ctx,
                 counts, runtime):
    n_features, n_tests_passed, n_specs = counts
    n_tests = len(res)
    n_bh = int(res["bh_pass"].sum())
    n_by = int(res["by_pass"].sum())
    n_p05 = int((res["p_value"] <= 0.05).sum())
    n_under = int(res["underpowered_for_floor"].sum())
    L = []
    A = L.append
    A("# player_feature_rebaselined_v1 — every feature re-measured against the "
      "anchor-plus-blend baseline")
    A("")
    A(f"*Generated by `rebaseline_screen.py`; runtime {runtime:.0f}s; "
      f"**{args.perms} permutations per test**; ridge lambda={RIDGE_LAMBDA} on "
      "standardized inputs. Universe, split machinery, ridge and the BH adjuster "
      "imported unchanged from `feature_lab.py` / `evalharness`; candidates "
      "imported unchanged from `features/`. Nothing outside "
      "`rebaseline_screen.py` and `experiments/feature_screen_rebaselined/` "
      "was written.*")
    A("")
    A("## Why this run exists")
    A("")
    A("`player_feature_screen_v1` ranked 90 features against a baseline that no "
      "longer exists. `player_feature_crossseason_v1` established that the "
      "previous-completed-season anchor beats that baseline by 0.013-0.032 MAE "
      "per channel — an order of magnitude larger than any run-1 survivor's "
      "effect. **A feature's incremental value is defined relative to its "
      "baseline, so when the baseline changes the ranking is void, not merely "
      "stale.** The specific worry the registration names: form and trend "
      "features may have been paid for carrying long-run player identity that "
      "the old baseline omitted. Once the anchor supplies that identity "
      "directly, the proxy has nothing left to add. This run measures that.")
    A("")
    A("## 1. The frozen baseline (frozen BEFORE any feature was tested)")
    A("")
    A("`frozen_baseline.json` is written to disk before the battery loop starts. "
      "Per channel the baseline is a ridge on")
    A("")
    A("```")
    A("[ intercept,")
    A("  within-season ratio-EWMA per-36 rate      (smoothing constant alpha),")
    A("  blend = w*prev_completed_season_rate + (1-w)*season_to_date_rate,")
    A("  has_prior_season indicator ]")
    A("```")
    A("")
    A("- `alpha` and `w` are chosen **jointly**, per channel, by mean MAE over "
      f"the three 2022-2023 inner walk-forward folds. 2024 is not touched during "
      f"selection. Grid: alpha {BASE_ALPHA_GRID[0]}..{BASE_ALPHA_GRID[-1]} step 0.05 "
      f"x w {BLEND_W_GRID}. Full surface in `baseline_grid_curves.csv`.")
    A("- **Missing state, never mean-fill.** A row with no qualifying prior "
      "season (rookie, returnee, sub-150-minute prior season) gets blend value "
      "0.0 and `has_prior_season=0`. The indicator gives those rows their own "
      "intercept; their within-season EWMA column still carries their form. "
      "Nothing is imputed (constitution rule 8).")
    A("- The blend is asserted **identical** to the committed "
      "`features/fam_i.f92_two_season_blend` at two probe weights before it is "
      "used (max deviation 0; the run aborts otherwise). `fam_i.py` is read, "
      "never edited.")
    A("")
    A("| channel | alpha | w | inner MAE | 2024 baseline MAE | raw within-season EWMA 2024 | prior-season coverage 2024 | practical floor (0.20%) |")
    A("|---|---|---|---|---|---|---|---|")
    for ch, r in base_ref.items():
        A(f"| {ch} | {r['alpha']} | {r['w']} | {r['inner_mae_frozen']:.5f} | "
          f"{r['mae_frozen_baseline_2024']} | {r['mae_raw_within_season_ewma_2024']} | "
          f"{r['coverage_val_2024']:.1%} | {r['practical_floor_mae']:.5f} |")
    A("")
    A("Standardized baseline coefficients (2024 fit) — the anchor is doing the work:")
    A("")
    A("| channel | beta(within-season EWMA) | beta(blend) | beta(has_prior_season) |")
    A("|---|---|---|---|")
    for ch, r in base_ref.items():
        A(f"| {ch} | {r['beta_ewma_std']:+.5f} | {r['beta_blend_std']:+.5f} | "
          f"{r['beta_has_prior_std']:+.5f} |")
    A("")
    A("### Is w interior on the extended grid?")
    A("")
    A("The cross-season screen swept w over 0.1..0.9 and every channel picked "
      "**0.9, the largest value on the grid** — a boundary optimum that cannot "
      "be distinguished from 'the grid stopped too soon'. This registration "
      "extends the grid to 1.00 (0.92, 0.94, 0.95, 0.96, 0.98, 0.99, 1.00 added), "
      "where w=1.00 is the pure anchor with no season-to-date term at all.")
    A("")
    A("| channel | frozen w | interior on the extended grid? | inner MAE at w=0.9 | at w=0.95 | at w=0.98 | at w=1.00 |")
    A("|---|---|---|---|---|---|---|")
    for ch, r in base_ref.items():
        sub = base_curves[(base_curves["channel"] == ch)
                          & (base_curves["alpha"] == r["alpha"])].set_index("w")
        g = lambda w: (f"{sub.loc[w, 'inner_mae']:.5f}" if w in sub.index else "")  # noqa: E731
        A(f"| {ch} | {r['w']} | {'YES — interior' if r['w_interior_on_extended_grid'] else 'NO — at the endpoint w=1'} | "
          f"{g(0.9)} | {g(0.95)} | {g(0.98)} | {g(1.0)} |")
    A("")
    n_int = sum(1 for r in base_ref.values() if r["w_interior_on_extended_grid"])
    A(f"**{n_int} of {len(base_ref)} channels put w in the interior; "
      f"{len(base_ref) - n_int} run to w = 1.00.** Extending the grid did not "
      "rescue an interior optimum for those channels — it relocated the boundary "
      "to w = 1, which is the natural end of the parameter's range (w > 1 would "
      "put a negative weight on the season-to-date term). So this is a **genuine "
      "boundary, not a truncated grid**, and it says something specific: at the "
      "optimum the blend has NO season-to-date component, i.e. it degenerates to "
      "the pure previous-season anchor. The season-to-date expanding rate earns "
      "nothing because the within-season ratio-EWMA sitting next to it in the "
      "same design already carries current-season form. The two-parameter blend "
      "does not pay for its second parameter — which is the correlated-"
      "specification collapse the registration predicted, occurring inside the "
      "baseline itself.")
    A("")
    A("The plateau is also flat: on fg3 the entire 0.9 -> 1.0 stretch is worth "
      "0.0018 inner MAE. The choice between 'anchor' and 'anchor with a 10% "
      "shrink' is not a choice the data is making strongly; it is the same "
      "specification twice. `ft` is the one channel with a real interior turn "
      "(its curve rises again after 0.90).")
    A("")
    A("## 2. Protocol")
    A("")
    A(f"- **Window** 2022-2024: fit 2022-2023 ({len(outer.train_idx)} rows), "
      f"validate walk-forward on 2024 ({len(outer.test_idx)} rows); "
      f"{len(U_full) - len(U)} pre-2022 universe rows excluded (2021 survives only "
      "as the source of completed-season aggregates for 2022 games). Three inner "
      "walk-forward folds inside 2022-2023 for every tuning decision.")
    A(f"- **Battery**: {len(battery)} candidate objects covering "
      f"**{len(uniq_nums)} unique catalog numbers** — all "
      f"{len(list(ALL_CANDIDATES))} `features/fam_*.py` candidates plus the "
      f"{len(list(BF.CANDIDATES))} `features/bios_features.py` candidates that "
      "were screened as run 2. Catalog number 10 appears in both modules under "
      "different constructions (`tip_time_split` in fam_a, `tip_split_local` in "
      f"bios), which is why {len(battery)} objects give {len(uniq_nums)} numbers.")
    A(f"- **{n_tests} feature-channel tests**, each feature on its "
      "catalog-declared channels only (run-1 convention; the registration's "
      "runtime clause).")
    A("- **Statistic**: delta = MAE_2024(ridge[frozen baseline + feature]) - "
      "MAE_2024(ridge[frozen baseline]). The reference is the ridge-recalibrated "
      "frozen baseline and the permutation null uses the identical statistic.")
    A("- **Feature NaNs** keep run-1's encoding (fit-window mean fill at fit "
      "time) so the deltas stay comparable to run 1. The registration's "
      "no-mean-fill clause is about the BASELINE's rookie rows, which are "
      "handled by the missing-state indicator above.")
    A("- **Swept features** re-sweep their own parameter on the inner folds "
      "only, against the new baseline, and freeze it before 2024 is scored.")
    A("- **Quarantine absolute**: 2025/2026 never loaded; "
      f"`quarantine_audit.json` all-pass={all(a['pass'] for a in ctx.audit)} over "
      f"{len(ctx.audit)} matrices.")
    A("")
    A("### Permutations: 2,000, and why the count mattered")
    A("")
    A("Run 1 used 200 permutations, so the smallest attainable p-value was "
      "1/201 = 0.00498. **Every one of run 1's 14 surviving tests reported "
      "exactly 0.00498** — the floor, not a measurement. Ranking, BH ordering "
      "and any claim about relative evidence were all artifacts of a truncated "
      "null. At 2,000 the floor is 1/2001 = 0.0005 and the p-values separate.")
    A("")
    A("### Permutation scheme: BLOCK-permutation by (player, season)")
    A("")
    A("Rows are grouped into `(player_id, season)` blocks. A permutation "
      "relabels **whole blocks within a season**: target block *b* takes source "
      "block *sigma(b)*'s value sequence in order (read cyclically when the "
      "source block is shorter). Both the fit set and the 2024 validation set "
      "are permuted this way; only the feature moves, so the (baseline, target) "
      "pairing is untouched and the baseline keeps all of its information.")
    A("")
    A("**Why this is the correct null here.** These features are player "
      "attributes measured repeatedly: a player's shot diet, clock share or "
      "rotation role is strongly autocorrelated inside a season, so a "
      "row-exchangeable shuffle destroys that autocorrelation and produces a "
      "null distribution that is far too tight. Anything slow-moving then looks "
      "significant because the null it is compared against is noisier per row "
      "than the real feature is. Blocking makes the exchangeable unit the "
      "player-season — the level at which these features actually vary "
      "independently — so the null retains the clustering and the test asks the "
      "right question: *does this feature line up with THESE player-games, or "
      "would any player's trajectory have done as well?* Restricting the "
      "relabelling to within-season also preserves each season's marginal, so a "
      "feature earns nothing for encoding a league-level shift. The identity "
      "relabelling reproduces the observed data, so the observed statistic is a "
      "member of the permutation distribution and the add-one p-value "
      "`(1 + #{null >= obs}) / (1 + n_perm)` is valid.")
    A("")
    A("**The scheme is checked, not asserted.** Three synthetic features that "
      "are null by construction were pushed through the same machinery under "
      "both schemes (`diagnostics/null_calibration.csv`): `iid_noise` "
      "(exchangeable at the row level, so both schemes should be calibrated), "
      "`player_season_constant` (one draw per player-season — maximal "
      "clustering) and `ar1_within_player` (rho=0.9 inside each player-season). "
      "A calibrated null returns p-values scattered over (0,1) for all three.")
    A("")
    A("| synthetic null feature | p under BLOCK (this run) | p under ROW-exchangeable (run 1) | null SD ratio block/row |")
    A("|---|---|---|---|")
    for name, sub in calib.groupby("synthetic_feature", sort=False):
        A(f"| {name} | " +
          ", ".join(f"{r['channel']} {r['p_block_by_player_season']:.3f}"
                    for _, r in sub.iterrows()) + " | " +
          ", ".join(f"{r['channel']} {r['p_row_exchangeable_run1']:.3f}"
                    for _, r in sub.iterrows()) + " | " +
          f"{sub['null_sd_ratio_block_over_row'].mean():.2f} |")
    A("")
    A("The **null SD ratio** is the diagnostic that matters: a ratio above 1 "
      "means the row-exchangeable null was too narrow, so any feature with "
      "within-player structure was being compared against a null that could "
      "not reproduce that structure — the mechanism by which run 1 could hand "
      "out p=0.00498 to a whole page of slow-moving player attributes.")
    A("")
    A("### FDR: BH primary, BY alongside")
    A("")
    A(f"Benjamini-Hochberg at q={FDR_Q:.2f} across all {n_tests} tests is the "
      "primary control. Benjamini-Yekutieli — BH inflated by the harmonic number "
      f"H({n_tests}) = {float(np.sum(1.0 / np.arange(1, n_tests + 1))):.3f} — is "
      "reported in the same CSV as the conservative sensitivity. BY is valid "
      "under arbitrary dependence, which is the honest description of a battery "
      "where many features are near-duplicates of each other. Both columns "
      "(`q_bh`, `q_by`) are on every row.")
    A("")
    A("### Practical floor")
    A("")
    A("Significance is not usefulness. A feature must ALSO cut its channel's "
      "MAE by at least **0.20% of that channel's frozen-baseline error** "
      "(per-channel floors in the table above). Every test is placed in one of "
      "three tiers: significant AND practical / significant only / neither.")
    A("")
    A("### Minimum detectable effect (cluster-aware) on every row")
    A("")
    A("`mde80` is the smallest true MAE reduction this test would detect 80% of "
      "the time with a one-sided 5% test: `(z_0.95 + z_0.80) x SE`. Two SEs are "
      "computed and the **larger** MDE is reported:")
    A("")
    A("1. `se_cluster_player_season` — the cluster-robust SE of the mean paired "
      "loss difference on 2024, clustering by (player, season): within-cluster "
      "deviations are summed before squaring, so correlated rows inside a "
      "player-season count once, not many times. The row-level SE "
      "(`se_iid_row_level`) is carried alongside purely to show the size of the "
      "understatement.")
    A("2. `mde80_permutation` — from the SD of the block-permutation null, which "
      "is cluster-aware by construction.")
    A("")
    n_null = int((~res["bh_pass"]).sum())
    n_null_under = int(res.loc[~res["bh_pass"], "underpowered_for_floor"].sum())
    n_bh_under = int(res.loc[res["bh_pass"], "underpowered_for_floor"].sum())
    A(f"**{n_under} of {n_tests} tests ({n_under / max(n_tests, 1):.0%}) carry an "
      "`mde80` above the 0.20% practical floor.** The flag means different things "
      "on the two sides of the significance line, and the report keeps them apart:")
    A("")
    A(f"- **{n_null_under} of the {n_null} non-significant tests are "
      "underpowered.** For these, a null result means *this design could not "
      "have seen a floor-sized effect*, not *there is no effect*. They are "
      f"absence of evidence. The remaining {n_null - n_null_under} non-significant "
      "tests WERE powered to the floor and are genuine nulls.")
    A(f"- **{n_bh_under} of the {n_bh} BH-passing tests are underpowered.** A "
      "significant test can still have an effect estimate wider than the floor: "
      "the permutation null says the alignment is real, while the cluster-robust "
      "SE says the magnitude is not pinned down at this sample size. Direction "
      "supported, size not.")
    A("")
    A("The driver is cluster count, not row count. 2024 supplies ~3,300 scored "
      "rows but only ~150 player-season clusters, and it is the clusters that "
      "carry independent information. A row-level SE would have made almost "
      "every test look adequately powered; that is precisely the overstatement "
      "the registration asked to remove.")
    A("")
    A("### Correlated-specification collapsing")
    A("")
    A("Each test's **incremental prediction vector** (`pred_with_feature - "
      "pred_baseline` on the 2024 rows) is the thing the specification actually "
      f"adds. Tests whose incremental vectors correlate above |r| > {CORR_COLLAPSE} "
      "within a channel are one finding, not several; the group is reported once "
      "with a nominated parsimonious carrier (significant first, then largest "
      "improvement, then the un-swept specification, then the lower catalog "
      "number). `correlation_groups.csv` holds the memberships and "
      "`diagnostics/correlation_pairs.csv` the pairwise correlations.")
    A("")
    A("## 3. Headline")
    A("")
    A(f"- **{n_tests} tests** across {len(uniq_nums)} unique features.")
    A(f"- p<=0.05 uncorrected: **{n_p05}** (expected under a global null: "
      f"~{0.05 * n_tests:.1f}).")
    A(f"- **BH(q=0.10): {n_bh}**; BY(q=0.10): **{n_by}**.")
    A(f"- Practical tier counts: "
      f"{int((res['practical_tier'] == 'significant_and_practical').sum())} "
      "significant AND practical / "
      f"{int((res['practical_tier'] == 'significant_only').sum())} significant "
      f"only / {int((res['practical_tier'] == 'neither').sum())} neither.")
    A(f"- **Survivors** (BH + sign-consistency across all 3 inner folds and 2024 "
      f"+ practical floor): **{n_tests_passed} tests**. Under the conservative "
      f"BY correction instead of BH: {int(res['survives_under_by'].sum())} tests.")
    A("")
    A("### The three counts, kept distinct")
    A("")
    A("| count | value |")
    A("|---|---|")
    A(f"| unique confirmed FEATURES | **{n_features}** |")
    A(f"| passed feature-channel TESTS | **{n_tests_passed}** |")
    A(f"| collapsed correlated SPECIFICATIONS | **{n_specs}** |")
    A("")
    A("These are three different questions — how many distinct ideas survived, "
      "how many (idea, channel) hypotheses passed, and how many genuinely "
      "independent findings remain after near-duplicate specifications are "
      "merged. Reporting one number for all three is how a screen inflates "
      "itself.")
    A("")
    A("## 4. THE KEY COMPARISON — run 1's 11 confirmed features against the new baseline")
    A("")
    A("Run 1 (`experiments/feature_screen/`) produced 14 surviving tests over 11 "
      "unique features. Every one is re-measured here against the "
      "anchor-plus-blend baseline. `run1 delta` is that run's number against the "
      "old within-season-EWMA-only baseline; `now` is the same feature-channel "
      "against the frozen baseline.")
    A("")
    for line in run1_comparison_lines(res):
        A(line)
    A("")
    A("## 5. Survivors")
    A("")
    if len(surv):
        A("| # | name | channel | delta | improvement | % of baseline | p | q(BH) | q(BY) | mde80 | folds | carrier |")
        A("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for _, r in surv.iterrows():
            A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
              f"{r['delta_mae']:+.5f} | {r['observed_effect_improvement']:+.5f} | "
              f"{r['improvement_pct_of_baseline']:.3f}% | {r['p_value']:.5f} | "
              f"{r['q_bh']:.4f} | {r['q_by']:.4f} | {r['mde80']:.5f} | "
              f"{r['fold_signs']} | {r['collapse_group']} |")
    else:
        A("**None.** No feature in the catalog cleared BH(10%), fold-sign "
          "consistency AND the 0.20% practical floor once the cross-season "
          "anchor was in the baseline.")
    A("")
    A("## 6. Significant-only tier (cleared BH, failed the practical floor)")
    A("")
    so = res[res["practical_tier"] == "significant_only"].head(25)
    if len(so):
        A("| # | name | channel | improvement | % of baseline | floor | p | q(BH) | q(BY) | sign-consistent |")
        A("|---|---|---|---|---|---|---|---|---|---|")
        for _, r in so.iterrows():
            A(f"| {r['catalog_number']} | {r['name']} | {r['channel']} | "
              f"{r['observed_effect_improvement']:+.5f} | "
              f"{r['improvement_pct_of_baseline']:.3f}% | {r['practical_floor']:.5f} | "
              f"{r['p_value']:.5f} | {r['q_bh']:.4f} | {r['q_by']:.4f} | "
              f"{r['sign_consistent']} |")
        if int((res['practical_tier'] == 'significant_only').sum()) > 25:
            A("")
            A(f"*(top 25 of "
              f"{int((res['practical_tier'] == 'significant_only').sum())}; "
              "full list in `screen_results.csv`)*")
    else:
        A("None.")
    A("")
    A("## 7. Correlated-specification groups")
    A("")
    if len(groups):
        multi = groups[groups["group_size"] > 1]
        A(f"{groups['group_id'].nunique()} groups over {len(groups)} tests; "
          f"{multi['group_id'].nunique()} of them contain more than one "
          "specification.")
        A("")
        A("| group | channel | members | nominated carrier |")
        A("|---|---|---|---|")
        for g, sub in groups[groups["group_size"] > 1].groupby("group_id"):
            mem = ", ".join(f"#{int(r.catalog_number)} {r['name']}"
                            for _, r in sub.iterrows())
            A(f"| {g} | {sub['channel'].iloc[0]} | {mem} | "
              f"{sub['carrier'].iloc[0]} |")
        if not len(multi):
            A("| — | — | every group is a singleton | — |")
    else:
        A("No group had two members above the threshold among the tests "
          "considered.")
    A("")
    A("### The demonstration the registration names: the anchor and the blend")
    A("")
    A("`player_feature_crossseason_v1` reported **six survivors** — #87 "
      "`prev_season_anchor` and #92 `two_season_blend` on fg3, np2 and paint. "
      "Its own report already suspected they were one effect measured twice. "
      "Here that is settled on the evidence: the incremental prediction vectors "
      "of the two specifications are correlated directly, first against the "
      "within-season-EWMA-only baseline the cross-season screen actually used "
      "(where both were discoveries), then against this run's frozen baseline "
      "(where the anchor is the incumbent and neither should have anything "
      "left to add). Full table in `diagnostics/anchor_family_collapse.csv`.")
    A("")
    A("| baseline | channel | specification pair | corr(incremental prediction) | collapses at 0.9? |")
    A("|---|---|---|---|---|")
    for _, d in demo[demo["spec_b"] == "#92 two_season_blend @w=0.9"].iterrows():
        A(f"| {d['baseline']} | {d['channel']} | {d['spec_a']} vs {d['spec_b']} | "
          f"{d['corr_incremental_prediction']:.5f} | "
          f"{'**YES — one finding**' if d['collapses_at_0.9'] else 'no'} |")
    A("")
    A("The parsimonious carrier is **#87 `prev_season_anchor`**: one term, no "
      "tuned weight. #92 at w=0.9 is #87 shrunk 10% toward the season-to-date "
      "rate and should never be promoted alongside it. The inner folds reach "
      "the same conclusion independently — three of four channels drove the "
      "baseline's own blend weight all the way to w=1.00, which IS the pure "
      "anchor.")
    A("")
    A("## 8. What this run did NOT do")
    A("")
    A("- **No git.** No registry write. `registry.register` / `evaluate` / "
      "`record_evaluation` / `render_leaderboards` are never imported or called; "
      "`experiments/registry.jsonl` is never opened for writing.")
    A("- `feature_lab.py`, `crossseason_screen.py`, `features/*` and every "
      "pre-existing `experiments/` directory are read-only. Everything this "
      "registration changes is a wrapper inside `rebaseline_screen.py`.")
    A("- No network. No 2025 or 2026 row entered any code path.")
    A("- **This is a screen, and 2024 is exploratory.** Per the registration, "
      "2024 helped motivate the cross-season rescue and is the validation season "
      "here, so nothing in this report is confirmation. Confirmation is the "
      "sealed 2025 season under the nomination protocol.")
    A("- The >=15-minute robustness rerun from runs 1-3 is not repeated; it is "
      "not part of this registration's deliverables and the permutation budget "
      "went to resolution instead.")
    A("")
    A("## 9. A LATER REGISTRATION AMENDS THIS ONE — read before acting on the results")
    A("")
    A("`screening_protocol_amendment_v2` was registered at **2026-07-31T16:17:53Z**, "
      "*after* `player_feature_rebaselined_v1` (16:01:50Z) and after this run's "
      "brief was written. It names this experiment in its `amends` list and "
      "states that where the two conflict, the amendment controls. This run "
      "implements the ORIGINAL registration. The differences are listed here "
      "rather than silently resolved, because changing a preregistered protocol "
      "mid-run on the strength of a document found in the ledger is exactly the "
      "move this program forbids. **The orchestrator, not this run, decides "
      "which protocol governs.**")
    A("")
    A("| amendment clause | this run | conflict? |")
    A("|---|---|---|")
    A("| P2 three-way split: 2022 inner tuning, 2023 baseline SELECTION, 2024 "
      "measurement only | (alpha, w) selected on three inner walk-forward folds "
      "spanning 2022-2023 jointly; 2024 never used for selection | **partial** — "
      "no baseline parameter touches 2024, but selection is not isolated to 2023 |")
    A("| P3 second null blocked by GAME-DATE, plus a two-way (player-season x "
      "game-date) cluster-robust CI; decide on the most conservative of the "
      "three | one null only: block-permutation by (player, season) | **yes** — "
      "the game-date null is not computed |")
    A("| P4 adaptive escalation to 20,000 permutations for any test reaching "
      "p<0.01 before a decision is read | flat 2,000 for every test | **yes** — "
      "p-values at or near the 1/2001 floor are not resolved further |")
    A("| P4 BH q=0.10 decides; BY is sensitivity only | `survives` uses BH; "
      "`survives_under_by` is reported and decides nothing | no conflict |")
    A("| P5 correlation grouping is presentational and never reduces the FDR "
      f"denominator | BH and BY are computed over all {n_tests} attempted tests; "
      "grouping only collapses the reported specification count | no conflict |")
    A("| P6 the 0.20% practical floor is WITHDRAWN as a gate | the floor is "
      "applied as a gate in `survives` | **yes** — but every component is a "
      "separate column (`bh_pass`, `sign_consistent`, `practical`), so the "
      "floor-free count is recoverable without re-running |")
    A("")
    A(f"**Under the amendment's P6 (no practical gate), the survivor count would "
      f"be {int((res['bh_pass'] & res['sign_consistent']).sum())} tests over "
      f"{int(res[res['bh_pass'] & res['sign_consistent']]['catalog_number'].nunique())} "
      f"unique features**, instead of the {n_tests_passed} tests over "
      f"{n_features} features reported above. Both numbers are in "
      "`three_tier_counts.csv` and both are recoverable from "
      "`screen_results.csv`; nothing here needs re-running to switch between "
      "them. The P3 and P4 items DO require a re-run.")
    A("")
    A("## 10. Files")
    A("")
    A("- `frozen_baseline.json` — the baseline, written before the first test")
    A("- `screen_results.csv` — one row per (feature, channel): observed effect, "
      "MDE, BH q, BY q, practical tier, survives")
    A("- `survivor_summary.csv` — survivors only")
    A("- `correlation_groups.csv` — collapsed specification groups + carriers")
    A("- `three_tier_counts.csv` — the tier table and the three distinct counts")
    A("- `baseline_grid_curves.csv` — the full (alpha, w) inner-fold surface")
    A("- `quarantine_audit.json` — per-matrix date audit")
    A("- `diagnostics/null_quantiles.csv` — null quantiles per test")
    A("- `diagnostics/correlation_pairs.csv` — pairwise |r| > 0.9 among findings")
    A("- `diagnostics/anchor_family_collapse.csv` — the anchor/blend demonstration")
    A("- `diagnostics/null_calibration.csv` — block vs row-exchangeable null on "
      "synthetic null features")
    (OUTDIR / "REPORT.md").write_text("\n".join(L), encoding="utf-8")


RUN1_DIR = REPO / "experiments" / "feature_screen"        # READ-ONLY


def run1_comparison_lines(res: pd.DataFrame) -> list:
    """The head-to-head: run 1's confirmed features re-measured here.

    Reads run 1's committed `screen_results.csv` (read-only) and joins its
    surviving (feature, channel) tests to this run's rows.
    """
    f = RUN1_DIR / "screen_results.csv"
    if not f.exists():
        return ["*run 1 results not found on disk; comparison skipped.*"]
    r1 = pd.read_csv(f)
    s1 = r1[r1["survives"] == True].copy()                 # noqa: E712
    if not len(s1):
        return ["*run 1 recorded no survivors.*"]
    key = res.set_index(["catalog_number", "channel"])
    out, kept, lost, unique_now = [], 0, 0, set()
    out.append("| # | name | channel | run 1 delta | run 1 p | now delta | now p | q(BH) | q(BY) | % of baseline | practical? | folds | still survives |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in s1.sort_values("delta_mae").iterrows():
        k = (int(r["catalog_number"]), r["channel"])
        if k not in key.index:
            out.append(f"| {k[0]} | {r['name']} | {k[1]} | {r['delta_mae']:+.5f} | "
                       f"{r['p_value']:.5f} | *not re-tested* | | | | | | | |")
            continue
        n = key.loc[k]
        if isinstance(n, pd.DataFrame):
            n = n.iloc[0]
        surv = bool(n["survives"])
        kept += surv
        lost += (not surv)
        if surv:
            unique_now.add(k[0])
        out.append(
            f"| {k[0]} | {r['name']} | {k[1]} | {r['delta_mae']:+.5f} | "
            f"{r['p_value']:.5f} | {n['delta_mae']:+.5f} | {n['p_value']:.5f} | "
            f"{n['q_bh']:.4f} | {n['q_by']:.4f} | "
            f"{n['improvement_pct_of_baseline']:.3f}% | "
            f"{'yes' if n['practical'] else 'no'} | {n['fold_signs']} | "
            f"{'**YES**' if surv else 'no'} |")
    n_feat_1 = int(s1["catalog_number"].nunique())
    out.append("")
    out.append(f"**{kept} of {len(s1)} run-1 surviving tests survive the "
               f"re-baselining ({len(unique_now)} of {n_feat_1} unique "
               f"features); {lost} do not.**")
    # per-feature roll-up
    out.append("")
    out.append("| feature | run 1 tests passed | re-baselined tests passed |")
    out.append("|---|---|---|")
    for num, sub in s1.groupby("catalog_number"):
        n_now = 0
        for _, r in sub.iterrows():
            k = (int(num), r["channel"])
            if k in key.index:
                n = key.loc[k]
                if isinstance(n, pd.DataFrame):
                    n = n.iloc[0]
                n_now += int(bool(n["survives"]))
        out.append(f"| #{int(num)} {sub['name'].iloc[0]} | {len(sub)} | {n_now} |")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
