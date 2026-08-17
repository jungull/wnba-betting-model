"""Shared out-of-fold machinery for PART C (calibration) and PART S (the points test).

Two schemes, both preregistered:
  WF   expanding window ordered by gdate, refit at every distinct date, min 600 training rows
  GKF  5-fold GroupKFold on player_id

Everything here is fit on the A4_CLEAN_DEC rows only.  No quantity crosses arms.
"""
import numpy as np
import pandas as pd

MIN_TRAIN = 600
N_GKF = 5


def _safe_solve(A, b):
    """solve, falling back to a least-norm solution when A is singular.

    A column that is CONSTANT on the training window makes A singular at lam = 0.  That is a
    property of the data, not an error: `pts__pred_sd` takes exactly one value per season on
    the decision stratum (measured in NOTES.md), so any model using it alone is degenerate.
    The least-norm fallback returns a zero coefficient for such a column, which is the correct
    answer -- a constant carries no slope information.
    """
    try:
        return np.linalg.solve(A, b), False
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(A, b, rcond=None)[0], True


def ridge_fit(Xtr, ytr, lam, standardise=True):
    """Ridge with an UNPENALISED intercept.  Returns (intercept, beta) on the raw scale."""
    Xtr = np.asarray(Xtr, float)
    mu = Xtr.mean(0)
    sd = Xtr.std(0)
    dead = ~(sd > 1e-12)
    sd = np.where(dead, 1.0, sd)
    Z = (Xtr - mu) / sd if standardise else Xtr - mu
    Z = Z.copy()
    Z[:, dead] = 0.0
    ym = ytr.mean()
    G = Z.T @ Z
    p = G.shape[0]
    b, _fb = _safe_solve(G + lam * np.eye(p), Z.T @ (ytr - ym))
    b = np.where(dead, 0.0, b)
    beta = b / sd if standardise else b
    a = ym - mu @ beta
    return a, beta


def wls_fit(Xtr, ytr, w, lam=0.0):
    """Weighted ridge with an unpenalised intercept."""
    Xtr = np.asarray(Xtr, float)
    w = np.asarray(w, float)
    sw = w.sum()
    mu = (w[:, None] * Xtr).sum(0) / sw
    ym = float((w * ytr).sum() / sw)
    Z = Xtr - mu
    sd = np.sqrt((w[:, None] * Z ** 2).sum(0) / sw)
    dead = ~(sd > 1e-12)
    sd = np.where(dead, 1.0, sd)
    Zs = (Z / sd).copy()
    Zs[:, dead] = 0.0
    G = Zs.T @ (w[:, None] * Zs)
    b, _fb = _safe_solve(G + lam * np.eye(G.shape[0]), Zs.T @ (w * (ytr - ym)))
    b = np.where(dead, 0.0, b)
    beta = b / sd
    a = ym - mu @ beta
    return a, beta


def tune_lambda(Xtr, ytr, grid, frac=0.75):
    """Inner time-ordered split of the training window; pick lambda by validation SSE."""
    m = len(ytr)
    k = int(np.floor(frac * m))
    if k < 30 or m - k < 15:
        return grid[0]
    best, bl = np.inf, grid[0]
    for lam in grid:
        a, b = ridge_fit(Xtr[:k], ytr[:k], lam)
        e = ytr[k:] - (a + Xtr[k:] @ b)
        s = float(e @ e)
        if s < best:
            best, bl = s, lam
    return bl


def folds_wf(gdate, min_train=MIN_TRAIN):
    """(train_idx, test_idx) per distinct date, expanding window.  Rows must be date-sorted."""
    d = np.asarray(gdate)
    uniq, first = np.unique(d, return_index=True)
    order = np.argsort(first)
    uniq = uniq[order]; first = first[order]
    out = []
    n = len(d)
    for i, u in enumerate(uniq):
        lo = first[i]
        hi = first[i + 1] if i + 1 < len(uniq) else n
        if lo < min_train:
            continue
        out.append((np.arange(lo), np.arange(lo, hi)))
    return out


def folds_gkf(groups, k=N_GKF, seed=20260808):
    """GroupKFold-style split on an integer group label; deterministic, size-balanced."""
    g = np.asarray(groups)
    uniq, cnt = np.unique(g, return_counts=True)
    rng = np.random.default_rng(seed)
    order = np.argsort(-cnt)
    uniq = uniq[order]; cnt = cnt[order]
    load = np.zeros(k)
    assign = {}
    for u, c in zip(uniq, cnt):
        j = int(np.argmin(load))
        assign[u] = j
        load[j] += c
    lab = np.array([assign[x] for x in g])
    return [(np.where(lab != j)[0], np.where(lab == j)[0]) for j in range(k)]


def signflip_p(d, cluster, R=5000, seed=20260808):
    """Cluster sign-flip test on a paired per-row difference.  Returns (obs_sum, p, draws)."""
    d = np.asarray(d, float)
    cl = pd.factorize(np.asarray(cluster))[0]
    K = cl.max() + 1
    cs = np.bincount(cl, weights=d, minlength=K)
    obs = float(cs.sum())
    rng = np.random.default_rng(seed)
    S = rng.integers(0, 2, size=(R, K)) * 2 - 1
    draws = S @ cs
    p = float((np.sum(np.abs(draws) >= abs(obs)) + 1) / (R + 1))
    return obs, p, draws


def decile_table(vhat, realised, q=10):
    """Reliability table by predicted-error decile."""
    r = pd.Series(vhat).rank(method="first", pct=True).to_numpy()
    edges = np.linspace(0, 1, q + 1)
    rows = []
    for i in range(q):
        m = (r > edges[i]) & (r <= edges[i + 1]) if i > 0 else (r <= edges[1])
        rows.append(dict(decile=i + 1, n=int(m.sum()),
                         mean_predicted=float(np.mean(vhat[m])),
                         mean_realised=float(np.mean(realised[m])),
                         median_realised=float(np.median(realised[m]))))
    return pd.DataFrame(rows)


def spearman(a, b):
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


def r2_oof(y, yhat):
    y = np.asarray(y, float); yhat = np.asarray(yhat, float)
    sse = float(((y - yhat) ** 2).sum())
    sst = float(((y - y.mean()) ** 2).sum())
    return 1.0 - sse / sst if sst > 0 else np.nan
