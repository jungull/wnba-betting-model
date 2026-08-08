"""Matched prior-history references and matched-construction estimators, both levels.

EVERYTHING HERE IS STRICTLY PRIOR.  The prefix accumulators write the statistic for row i BEFORE
folding row i in, so a row is never in its own reference.  Half-lives and shrinkage constants are
selected on STRICTLY EARLIER SEASONS ONLY by grid search.

D091 authorises fitting references and compositions in the exploration lane.  NO CHAMPION IS
REFIT ANYWHERE -- the champion arms are read as stored forecasts and scored as-is.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HALF_LIFE_GRID = [1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 40.0]
K_GRID = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0]


def expanding_league_by_date(dates, values):
    """Mean of `values` over all rows with a STRICTLY EARLIER date.

    Same-date rows never see each other, which matters because a slate of games shares a date and
    a within-date leak would be invisible in a row-order check.
    """
    d = pd.Series(pd.to_datetime(dates)).to_numpy()
    v = np.asarray(values, float)
    order = np.argsort(d, kind="stable")
    ds = d[order]; vs = v[order]
    uniq, first = np.unique(ds, return_index=True)
    csum = np.r_[0.0, np.cumsum(np.nan_to_num(vs))]
    ccnt = np.r_[0, np.cumsum(np.isfinite(vs).astype(int))]
    # for each unique date, the prefix ending just before its first row
    s_at = csum[first]; n_at = ccnt[first]
    idx = np.searchsorted(uniq, ds)
    out_sorted = np.where(n_at[idx] > 0, s_at[idx] / np.maximum(n_at[idx], 1), np.nan)
    out = np.empty_like(out_sorted)
    out[order] = out_sorted
    return out


def prior_prefix(frame, entity_cols, num_col, den_col, half_life, date_col="game_date",
                 tie_col="game_id"):
    """Strictly-prior weighted sums for every row, returned as (S_num, S_den, S_w, n_prior).

    half_life is in GAMES BACK.  half_life=None gives unweighted expanding sums.
    Returns arrays aligned to `frame`'s ORIGINAL index order.
    """
    f = frame.reset_index(drop=False).rename(columns={"index": "_orig"})
    f = f.sort_values(list(entity_cols) + [date_col, tie_col], kind="stable")
    num = pd.to_numeric(f[num_col], errors="coerce").to_numpy(float)
    den = (np.ones(len(f)) if den_col is None
           else pd.to_numeric(f[den_col], errors="coerce").to_numpy(float))
    codes = f.groupby(list(entity_cols), sort=False).ngroup().to_numpy()
    change = np.flatnonzero(np.r_[True, codes[1:] != codes[:-1]])
    ns = np.diff(np.r_[change, len(codes)])
    Sn = np.zeros(len(f)); Sd = np.zeros(len(f)); Sw = np.zeros(len(f)); Np = np.zeros(len(f))
    decay = 1.0 if half_life is None else 0.5 ** (1.0 / float(half_life))
    for a, n in zip(change, ns):
        sn = 0.0; sd = 0.0; sw = 0.0; c = 0
        for j in range(a, a + n):
            Sn[j] = sn; Sd[j] = sd; Sw[j] = sw; Np[j] = c
            sn *= decay; sd *= decay; sw *= decay
            v = num[j]; w = den[j]
            if np.isfinite(v) and np.isfinite(w) and w > 0:
                sn += v; sd += w; sw += 1.0; c += 1
    orig = f["_orig"].to_numpy()
    out = np.empty((4, len(f)))
    out[0, orig] = Sn; out[1, orig] = Sd; out[2, orig] = Sw; out[3, orig] = Np
    return out[0], out[1], out[2], out[3]


def shrunk(S_num, S_den, S_w, target, k):
    """(weighted prior mean, shrunk toward `target` with pseudo-count k).

    Ratio of sums, never mean of ratios.  Where S_den is 0 the estimate is the target exactly.
    """
    num = np.where(S_den > 0, S_num, 0.0) + k * np.asarray(target, float)
    den = np.where(S_den > 0, S_den, 0.0) + k
    return num / den


def _sse(y, yhat, mask):
    r = np.asarray(y, float)[mask] - np.asarray(yhat, float)[mask]
    r = r[np.isfinite(r)]
    return float(np.sum(r * r)), int(len(r))


def tune_walk_forward(frame, y_col, season_col, build_fn, grid, scored_seasons, verbose=False):
    """Choose a grid point per SCORED SEASON using STRICTLY EARLIER SEASONS ONLY.

    build_fn(param) -> forecast array aligned to `frame`.  Every candidate forecast is itself
    strictly prior, so evaluating it on earlier seasons uses no information from the scored one.
    Returns (forecast array assembled season by season, {season: chosen param}).
    """
    y = pd.to_numeric(frame[y_col], errors="coerce").to_numpy(float)
    season = frame[season_col].to_numpy()
    cache = {g: build_fn(g) for g in grid}
    out = np.full(len(frame), np.nan)
    chosen = {}
    for s in scored_seasons:
        earlier = np.isin(season, [x for x in sorted(set(season.tolist())) if x < s])
        best = None; bestsse = np.inf
        for g in grid:
            sse, n = _sse(y, cache[g], earlier & np.isfinite(cache[g]))
            if n > 0 and sse < bestsse:
                bestsse = sse; best = g
        if best is None:
            best = grid[len(grid) // 2]
        chosen[s] = best
        m = season == s
        out[m] = cache[best][m]
        if verbose:
            print("      season %s -> param %s (fitted on %d earlier rows)"
                  % (s, best, int(earlier.sum())))
    return out, chosen


def walk_forward_affine(frame, y_col, x_col, season_col, scored_seasons):
    """a + b*x with (a,b) from OLS on STRICTLY EARLIER SEASONS ONLY."""
    y = pd.to_numeric(frame[y_col], errors="coerce").to_numpy(float)
    x = pd.to_numeric(frame[x_col], errors="coerce").to_numpy(float)
    season = frame[season_col].to_numpy()
    out = np.full(len(frame), np.nan)
    coefs = {}
    for s in scored_seasons:
        m = np.isin(season, [v for v in sorted(set(season.tolist())) if v < s]) \
            & np.isfinite(y) & np.isfinite(x)
        if m.sum() < 20:
            a, b = 0.0, 1.0
        else:
            X = np.c_[np.ones(m.sum()), x[m]]
            beta, *_ = np.linalg.lstsq(X, y[m], rcond=None)
            a, b = float(beta[0]), float(beta[1])
        coefs[s] = {"a": a, "b": b, "n_train": int(m.sum())}
        sm = season == s
        out[sm] = a + b * x[sm]
    return out, coefs


def walk_forward_blend(frame, y_col, a_col, b_col, season_col, scored_seasons):
    """w*A + (1-w)*B with w minimising squared error on STRICTLY EARLIER SEASONS, clipped [0,1]."""
    y = pd.to_numeric(frame[y_col], errors="coerce").to_numpy(float)
    A = pd.to_numeric(frame[a_col], errors="coerce").to_numpy(float)
    B = pd.to_numeric(frame[b_col], errors="coerce").to_numpy(float)
    season = frame[season_col].to_numpy()
    out = np.full(len(frame), np.nan)
    ws = {}
    for s in scored_seasons:
        m = np.isin(season, [v for v in sorted(set(season.tolist())) if v < s]) \
            & np.isfinite(y) & np.isfinite(A) & np.isfinite(B)
        if m.sum() < 20:
            w = 0.5
        else:
            d = A[m] - B[m]
            denom = float(np.sum(d * d))
            w = 0.5 if denom <= 0 else float(np.sum(d * (y[m] - B[m])) / denom)
            w = min(1.0, max(0.0, w))
        ws[s] = {"w": w, "n_train": int(m.sum())}
        sm = season == s
        out[sm] = w * A[sm] + (1.0 - w) * B[sm]
    return out, ws


def walk_forward_beta(frame, resid_col, x_col, season_col, scored_seasons):
    """Single slope on a centred regressor, fitted on STRICTLY EARLIER SEASONS ONLY."""
    r = pd.to_numeric(frame[resid_col], errors="coerce").to_numpy(float)
    x = pd.to_numeric(frame[x_col], errors="coerce").to_numpy(float)
    season = frame[season_col].to_numpy()
    out = np.full(len(frame), np.nan)
    betas = {}
    for s in scored_seasons:
        m = np.isin(season, [v for v in sorted(set(season.tolist())) if v < s]) \
            & np.isfinite(r) & np.isfinite(x)
        if m.sum() < 20 or float(np.sum(x[m] * x[m])) <= 0:
            b = 0.0
        else:
            b = float(np.sum(x[m] * r[m]) / np.sum(x[m] * x[m]))
        betas[s] = {"beta": b, "n_train": int(m.sum())}
        sm = season == s
        out[sm] = b * x[sm]
    return out, betas
