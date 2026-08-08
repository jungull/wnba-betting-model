"""E1_I0038 lab -- this screen's own copy of the machinery.

DELIBERATELY A LOCAL COPY.  The shared kit at experiments/exploration/_screen_kit/ is held open
by concurrent agents and is NEVER imported, modified or written by this screen.  The dR2 /
null / injection machinery below is line-for-line compatible with E1_I0036/scripts/lab.py so
that this screen's numbers are directly comparable to the ones it is auditing; the ONLY
additions are `amended_injection` (PREREG 6.4) and the flag helpers.

No column is ever chosen by name matching.  Every caller passes an explicit list.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, r"experiments\exploration")
OUT = os.path.join(EXP, "E1_I0038_within_entity_null_audit")
LEDGER = os.path.join(ROOT, r"experiments\player_program\orchestration\DECISION_LEDGER.jsonl")

SEED = 20260809
PARTITION_SEASONS = {2021, 2022, 2023, 2024}
R_DRAWS = 601                      # min attainable p = 1/601 = 0.001664
FLOOR_1CELL = 0.00102
FLOOR_132 = 0.00235
BEST_LIVE = 0.002057
EXPOSURE_THRESHOLD = 0.50          # PREREG 3 (E2); the programme's own existing threshold
SENSITIVITY_THRESHOLDS = (0.30, 0.50, 0.80)

DELTAS_D04 = [0.0, 0.000129, 0.000500, 0.001127, 0.002057]
NREP_D04 = 60
BENCH = {0.002057: "D089 largest measured, ALIVE",
         0.001127: "D079 shot mix, DEAD",
         0.000500: "(intermediate)",
         0.000129: "D084 opp conversion, DEAD",
         0.0: "TYPE-I CHECK"}

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 120)
pd.set_option("display.max_rows", 400)


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
    assert isinstance(cols, list), "columns must be an explicit list literal"
    missing = [c for c in cols if c not in df.columns]
    assert not missing, f"{label}: columns absent from frame: {missing}"
    assert len(cols) == expect_n, f"{label}: expected {expect_n} columns, got {len(cols)}"
    print(f"  RESOLVED {label} ({len(cols)}): {cols}")
    return cols


# ------------------------------------------------------------------ incremental R2
class BaseFit:
    """dR2 of adding x to [1, base] via Frisch-Waugh.  Same construction as
    E0_I0024/rb_base.BaseFit and E1_I0036/lab.BaseFit."""

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
        self.Q, _ = np.linalg.qr(X)

    def resid_x(self, x):
        x = np.asarray(x, float)
        return x - self.X @ (self.XtXi @ (self.X.T @ x))

    def resid_X(self, Xp):
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


def r2_twofit(y, X):
    A = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - A @ b
    return 1.0 - float(r @ r) / float(((y - y.mean()) ** 2).sum())


# ------------------------------------------------------------------ nulls
def null_draws(kind, x, rng, groups=None, order_key=None, blocks=None, R=R_DRAWS):
    """n x R matrix of null realisations of the candidate x.

    N_ROW    free permutation across all rows                       -> ROW
    N_CYCLIC within each group, cyclic shift by a random offset     -> WITHIN-ENTITY
    N_SWAP   swap each group's WHOLE ordered series within a block  -> BETWEEN-ENTITY
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
    draws = np.asarray(draws, float)
    return (1.0 + float((draws >= obs).sum())) / (1.0 + len(draws))


def var_share_between(x, groups):
    """Fraction of the candidate's variance that is BETWEEN groups.  A fact about the
    regressor alone -- computed before any response is touched."""
    s = pd.Series(np.asarray(x, float))
    g = pd.Series(np.asarray(groups))
    gm = s.groupby(g).transform("mean")
    tot = float(np.var(s, ddof=0))
    btw = float(np.var(gm, ddof=0))
    return btw / tot if tot > 0 else np.nan


def components(x, groups):
    """Split a carrier into its BETWEEN-group and WITHIN-group parts."""
    x = np.asarray(x, float)
    xb = pd.Series(x).groupby(pd.Series(np.asarray(groups))).transform("mean").to_numpy()
    return xb, x - xb


# ------------------------------------------------------------------ injection
def _dr2_at(ey0, ex, exx, sst_fn, c):
    ey = ey0 + c * ex
    num = float(ey @ ex)
    return (num * num / exx) / sst_fn(c)


def solve_c_for_delta(ey0, ex, sst_fn, delta, lo=0.0, hi=None, iters=80):
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


def original_injection(bf, carrier, EX, rng, deltas, nrep):
    """*** D108's ORIGINAL PROTOCOL, as implemented in E1_I0036/lab.py::injection_power. ***

    Reproduced here VERBATIM in behaviour so that R1 tests the real thing rather than a
    paraphrase of it.  Per replicate: the base fit is retained and the base RESIDUALS ARE
    SHUFFLED (this is the step D-04 says is the defect), then a synthetic effect of exactly
    `delta` is planted along the carrier.
    """
    ex = bf.resid_x(carrier)
    fitted = bf.y - bf.e
    n = bf.n
    rows = []
    for delta in deltas:
        det = 0
        ach = []
        for _ in range(nrep):
            e_sh = bf.e[rng.permutation(n)]
            y0 = fitted + e_sh
            bf0 = BaseFit(y0, bf.X[:, 1:])
            c = solve_c_for_delta(bf0.e, ex, lambda cc: float(
                ((y0 + cc * ex - (y0 + cc * ex).mean()) ** 2).sum()), delta)
            y1 = y0 + c * ex
            bf1 = BaseFit(y1, bf.X[:, 1:])
            obs = bf1.dr2(carrier)
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
    """Smallest delta at which power >= 0.80, linearly interpolated.  INJECTION-VERIFIED --
    this screen quotes no analytic MDE80 anywhere (D113)."""
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


# ------------------------------------------------------------------ THE AMENDMENT (PREREG 6.4)
def amended_injection(bf, x, EX, groups, rng, deltas=None, nrep=None, best_live=BEST_LIVE):
    """*** THE AMENDED D108 INJECTION PROTOCOL.  PREREG section 6.4. ***

    Difference from `original_injection`, in one sentence: the original asks "can this null
    detect a signal planted along the whole carrier, on a response whose entity structure has
    been shuffled away"; the amended one asks "can this null detect a signal planted along THE
    COMPONENT OF THE CARRIER THAT CARRIES THE MAJORITY OF THIS CANDIDATE'S MEASURED EFFECT".

    Returns (verdict_dict, per_component_power_table).
    """
    deltas = DELTAS_D04 if deltas is None else deltas
    nrep = NREP_D04 if nrep is None else nrep

    # 1-3: decompose the carrier at the null's own entity and find the dominant component
    xb, xw = components(x, groups)
    d_b, d_w = bf.dr2(xb), bf.dr2(xw)
    tot = d_b + d_w
    w_between = float(d_b / tot) if tot > 0 else np.nan
    dominant = "BETWEEN" if (np.isfinite(w_between) and w_between >= 0.50) else "WITHIN"

    # 4: inject once per component
    tabs = {}
    for cname, cvec in [("FULL", x), ("BETWEEN", xb), ("WITHIN", xw)]:
        tabs[cname] = original_injection(bf, cvec, EX,
                                         np.random.default_rng(rng.integers(0, 2 ** 31)),
                                         deltas, nrep).assign(planted_along=cname)
    pw = pd.concat(tabs.values(), ignore_index=True)

    def _pow(comp, delta):
        s = pw[(pw["planted_along"] == comp) & (np.isclose(pw["delta"], delta))]
        return float(s["power"].iloc[0]) if len(s) else np.nan

    pow_dom = _pow(dominant, best_live)
    pow_full = _pow("FULL", best_live)
    type_i = _pow("FULL", 0.0)

    # 5: the verdict
    if not np.isfinite(pow_dom):
        verdict = "UNDETERMINED"
    elif pow_dom < 0.80:
        verdict = "VOID_FOR_THIS_CANDIDATE"
    elif type_i > 0.10:
        verdict = "ANTICONSERVATIVE"
    else:
        verdict = "USABLE"

    return dict(
        w_between=w_between, dominant_component=dominant,
        dr2_between_component=d_b, dr2_within_component=d_w,
        power_dominant_at_best_live=pow_dom, power_full_at_best_live=pow_full,
        type_I_at_zero=type_i,
        mde80_injection_verified_full=mde80(tabs["FULL"]),
        mde80_injection_verified_dominant=mde80(tabs[dominant]),
        AMENDED_VERDICT=verdict,
        ORIGINAL_VERDICT=("CERTIFIED" if (np.isfinite(pow_full) and pow_full >= 0.80
                                          and type_i <= 0.10) else "REJECTED"),
    ), pw


def flag_null_mean(observed, null_mean):
    """Step 6 of the amendment: unconditional, advisory alone, decisive with a VOID verdict."""
    if observed is None or null_mean is None:
        return None
    if not (np.isfinite(observed) and np.isfinite(null_mean)):
        return None
    return bool(null_mean > observed)
