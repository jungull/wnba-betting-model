"""E1_I0036 shared lab -- incremental R2, level-matched permutation nulls, injection power.

Implements PREREG sections 5.1-5.5.  No column is ever chosen by name matching: every caller
passes an explicit python list and this module asserts its length.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E1_I0036_level_artefact_sweep")
EXP = os.path.join(ROOT, r"experiments\exploration")

SEED = 20260808
PARTITION_SEASONS = {2021, 2022, 2023, 2024}
R_DRAWS = 601                      # min attainable p = 1/601 = 0.001664, matches the screens
NREP = 100                         # injection replicates per delta
DELTAS = [0.0, 0.000050, 0.000129, 0.000500, 0.001127, 0.002057]
BENCH = {0.002057: "D089 largest measured, ALIVE",
         0.001127: "D079 shot mix, DEAD",
         0.000500: "(intermediate)",
         0.000129: "D084 opp conversion, DEAD",
         0.000050: "(below every benchmark)",
         0.0: "TYPE-I CHECK"}
FLOOR_1CELL = 0.00102
FLOOR_132 = 0.00235
BEST_LIVE = 0.002057

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 120)


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     default=str).encode("utf-8")).hexdigest()


def assert_partition(df, where=""):
    s = set(pd.unique(df["season"]))
    bad = s - PARTITION_SEASONS
    assert not bad, f"A_PARTITION FAILED {where}: seasons outside exploration partition: {bad}"
    print(f"  A_PARTITION ok {where}: seasons={sorted(s)}")


def resolve(df, cols, expect_n, label):
    """EXPLICIT allowlist resolution.  Prints the list and asserts the count (PREREG 3)."""
    assert isinstance(cols, list), "columns must be an explicit list literal"
    missing = [c for c in cols if c not in df.columns]
    assert not missing, f"{label}: columns absent from frame: {missing}"
    assert len(cols) == expect_n, f"{label}: expected {expect_n} columns, got {len(cols)}"
    print(f"  RESOLVED {label} ({len(cols)}): {cols}")
    return cols


# ------------------------------------------------------------------ incremental R2
class BaseFit:
    """dR2 of adding x to [1, base] via Frisch-Waugh.  Same construction as rb_base.BaseFit
    (E0_I0024) so D097's numbers are reproducible bit-for-bit."""

    def __init__(self, y, base):
        y = np.asarray(y, float)
        base = np.asarray(base, float)
        if base.ndim == 1:
            base = base[:, None]
        self.n = len(y)
        X = np.column_stack([np.ones(self.n), base])
        self.X = X
        self.XtXi = np.linalg.pinv(X.T @ X)
        self.y = y
        self.e = y - X @ (self.XtXi @ (X.T @ y))
        self.sst = float(((y - y.mean()) ** 2).sum())
        self.r2_base = 1.0 - float(self.e @ self.e) / self.sst if self.sst > 0 else np.nan
        # orthonormal basis for fast batched residualisation of many x at once
        self.Q, _ = np.linalg.qr(X)

    def resid_x(self, x):
        x = np.asarray(x, float)
        return x - self.X @ (self.XtXi @ (self.X.T @ x))

    def resid_X(self, Xp):
        """Residualise a MATRIX of candidate columns (n x R) on the base, in one shot."""
        Xp = np.asarray(Xp, float)
        return Xp - self.Q @ (self.Q.T @ Xp)

    def dr2(self, x):
        xt = self.resid_x(x)
        den = float(xt @ xt)
        if not np.isfinite(den) or den <= 1e-12:
            return 0.0
        num = float(self.e @ xt)
        return (num * num / den) / self.sst

    def beta(self, x):
        xt = self.resid_x(x)
        den = float(xt @ xt)
        return 0.0 if den <= 1e-12 else float((self.e @ xt) / den)

    def dr2_batch_ey(self, EY, EX, sst):
        """dR2 for many responses (residualised, n x M) against many carriers (n x R).

        Returns M x R.  EY columns must already be residualised on the base; sst is per-column.
        """
        num = EY.T @ EX                      # M x R
        den = np.einsum("ij,ij->j", EX, EX)  # R
        out = (num ** 2) / den[None, :]
        return out / np.asarray(sst, float)[:, None]


def r2_twofit(y, X):
    """Literal R2 from a refit -- used only to verify the fast dR2 identity."""
    A = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - A @ b
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum())


# ------------------------------------------------------------------ nulls
def _order_within(groups, order_key):
    """Return, per row, its 0-based rank within its group under order_key."""
    df = pd.DataFrame({"g": groups, "k": order_key})
    return df.groupby("g", sort=False)["k"].rank(method="first").to_numpy() - 1.0


def null_draws(kind, x, rng, groups=None, order_key=None, blocks=None, R=R_DRAWS):
    """Return an n x R matrix of null realisations of the candidate x.

    kind:
      N_ROW    free permutation across all rows
      N_CYCLIC within each group, cyclic shift by a random offset (preserves serial structure)
      N_SWAP   swap each group's WHOLE ordered series with another group's, within a block
               (this is N_PSWAP / N_ENTITY / N_OSWAP depending on what `groups` is)
    """
    x = np.asarray(x, float)
    n = len(x)
    Xp = np.empty((n, R), float)

    if kind == "N_ROW":
        for r in range(R):
            Xp[:, r] = x[rng.permutation(n)]
        return Xp

    assert groups is not None, "grouped nulls need `groups`"
    g = pd.Series(groups).to_numpy()
    uniq, ginv = np.unique(g, return_inverse=True)
    idx_by_g = [np.where(ginv == i)[0] for i in range(len(uniq))]
    if order_key is not None:
        ok = np.asarray(order_key)
        idx_by_g = [ix[np.argsort(ok[ix], kind="stable")] for ix in idx_by_g]

    if kind == "N_CYCLIC":
        for r in range(R):
            for ix in idx_by_g:
                m = len(ix)
                s = rng.integers(0, m) if m > 1 else 0
                Xp[ix, r] = np.roll(x[ix], s)
        return Xp

    if kind == "N_SWAP":
        # permute group identities within blocks (default: one block = everything)
        b = np.zeros(len(uniq), int) if blocks is None else np.asarray(
            pd.Series(blocks).groupby(pd.Series(g)).first().reindex(uniq).to_numpy())
        vals = [x[ix] for ix in idx_by_g]
        for r in range(R):
            perm = np.arange(len(uniq))
            for bb in np.unique(b):
                w = np.where(b == bb)[0]
                perm[w] = w[rng.permutation(len(w))]
            for i, ix in enumerate(idx_by_g):
                src = vals[perm[i]]
                m, ms = len(ix), len(src)
                Xp[ix, r] = src[np.arange(m) % ms]
        return Xp

    raise ValueError(kind)


def perm_p(obs, draws):
    """One-sided permutation p on dR2 (dR2 is non-negative by construction)."""
    draws = np.asarray(draws, float)
    return (1.0 + float((draws >= obs).sum())) / (1.0 + len(draws))


# ------------------------------------------------------------------ injection
def solve_c_for_delta(ey0, ex, sst_fn, delta, lo=0.0, hi=None, iters=80):
    """Find c so that dR2 of the carrier against y = y0 + c*ex equals `delta`.

    Works on residualised quantities: adding c*ex to y adds c*ex to ey.
    dR2(c) = ((ey0+c*ex).ex)^2 / (ex.ex) / SST(c)
    """
    exx = float(ex @ ex)
    if delta <= 0:
        return 0.0
    if hi is None:
        hi = 1.0
        for _ in range(80):
            if _dr2_at(ey0, ex, exx, sst_fn, hi) >= delta:
                break
            hi *= 2.0
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if _dr2_at(ey0, ex, exx, sst_fn, mid) < delta:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _dr2_at(ey0, ex, exx, sst_fn, c):
    ey = ey0 + c * ex
    num = float(ey @ ex)
    return (num * num / exx) / sst_fn(c)


def injection_power(bf, x, EX, rng, deltas=DELTAS, nrep=NREP):
    """PREREG 5.3.  Returns a DataFrame: delta, power, achieved_dr2, crit, null_mean, null_sd.

    For each replicate the base fit is retained and the base RESIDUALS ARE SHUFFLED, which
    destroys any real response<->carrier association while preserving the residual
    distribution; a synthetic effect of exactly `delta` is then planted along the carrier.
    """
    ex = bf.resid_x(x)
    exx = float(ex @ ex)
    fitted = bf.y - bf.e
    n = bf.n
    rows = []
    # null distribution is a property of (y, EX); recomputed per replicate because y changes
    for delta in deltas:
        det = 0
        ach = []
        for rep in range(nrep):
            e_sh = bf.e[rng.permutation(n)]
            y0 = fitted + e_sh
            bf0 = BaseFit(y0, bf.X[:, 1:])
            c = solve_c_for_delta(bf0.e, ex, lambda cc: float(
                ((y0 + cc * ex - (y0 + cc * ex).mean()) ** 2).sum()), delta)
            y1 = y0 + c * ex
            bf1 = BaseFit(y1, bf.X[:, 1:])
            obs = bf1.dr2(x)
            ach.append(obs)
            num = bf1.e @ EX
            den = np.einsum("ij,ij->j", EX, EX)
            draws = (num ** 2 / den) / bf1.sst
            if perm_p(obs, draws) < 0.05:
                det += 1
        rows.append(dict(delta=delta, benchmark=BENCH.get(delta, ""),
                         achieved_dr2_med=float(np.median(ach)),
                         power=det / nrep, nrep=nrep))
    return pd.DataFrame(rows)


def mde80(pw):
    """Smallest delta at which power >= 0.80 (linear interpolation between grid points)."""
    d = pw.sort_values("delta").reset_index(drop=True)
    for i in range(len(d)):
        if d.loc[i, "power"] >= 0.80:
            if i == 0:
                return float(d.loc[i, "delta"])
            x0, y0 = d.loc[i - 1, "delta"], d.loc[i - 1, "power"]
            x1, y1 = d.loc[i, "delta"], d.loc[i, "power"]
            if y1 == y0:
                return float(x1)
            return float(x0 + (0.80 - y0) * (x1 - x0) / (y1 - y0))
    return float("inf")


def var_share_between(x, groups):
    """Fraction of the candidate's variance that is BETWEEN groups.  A fact about the
    regressor: it decides which null can possibly have power."""
    s = pd.Series(np.asarray(x, float))
    g = pd.Series(np.asarray(groups))
    gm = s.groupby(g).transform("mean")
    tot = float(np.var(s, ddof=0))
    btw = float(np.var(gm, ddof=0))
    return btw / tot if tot > 0 else np.nan
