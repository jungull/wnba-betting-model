"""E1_I0047 shared base. READ-ONLY against every other screen's artifacts.

Nothing here writes outside experiments/exploration/E1_I0047_ceiling_validity/.
The shared screen kit is NOT imported and NOT modified (sibling agents hold it open).

D069 convention throughout: SST about the UNWEIGHTED mean of y on the scored rows.
BaseFit is re-derived here rather than imported so that the reproduction of D097's
numbers is an independent implementation, not a call into the same object.
"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
EXP = os.path.abspath(os.path.join(OUT, ".."))          # experiments/exploration
D097 = os.path.join(EXP, "E0_I0024_reb_ast_characterisation")
D098 = os.path.join(EXP, "E1_I0023_usage_defence_interaction")
D089 = os.path.join(EXP, "E1_I0018_teammate_volume_channel")
D036 = os.path.join(EXP, "E1_I0036_level_artefact_sweep")
D043 = os.path.join(EXP, "E1_I0043_opponent_defence")

SEED = 20260808
FLOOR_1CELL = 0.00102        # D103 injection-verified single-cell floor
FLOOR_132 = 0.00235          # D103 injection-verified 132-cell floor
BEST_LIVE = 0.002057         # D089 largest live effect

# PARTITION GUARD -- 2025/26 is a sealed holdout.
ALLOWED_SEASONS = (2021, 2022, 2023, 2024)
CLEAN_WINDOW = (2023, 2024)
# transcribed from E0_I0024/rb_base.py -- D097's own headline filter, 2021 excluded by D097
D097_HEADLINE_SEASONS = (2022, 2023, 2024)


def assert_partition(seasons):
    bad = sorted(set(int(s) for s in seasons) - set(ALLOWED_SEASONS))
    if bad:
        raise SystemExit("PARTITION VIOLATION: seasons %s outside 2021-2024" % bad)
    return True


def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)


class Fit:
    """Independent re-implementation of the incremental-R2 path.

    dR2 of adding x to [1, base] is ((e.xt)^2 / (xt.xt)) / SST, e = y residualised on
    [1, base], xt = x residualised on [1, base].  Identical to refitting and differencing.
    """

    def __init__(self, y, base, freeze_intercept=False):
        y = np.asarray(y, float)
        base = np.asarray(base, float)
        if base.ndim == 1:
            base = base[:, None]
        self.n = len(y)
        self.X = np.column_stack([np.ones(self.n), base])
        self.XtXi = np.linalg.pinv(self.X.T @ self.X)
        self.y = y
        self.bhat_base = self.XtXi @ (self.X.T @ y)
        self.yhat_base = self.X @ self.bhat_base
        self.e = y - self.yhat_base
        self.sst = float(((y - y.mean()) ** 2).sum())
        self.r2_base = 1.0 - float(self.e @ self.e) / self.sst if self.sst > 0 else np.nan
        self.freeze_intercept = bool(freeze_intercept)

    def resid_x(self, x):
        x = np.asarray(x, float)
        if self.freeze_intercept:
            # project on the base slopes only; the intercept stays at the base fit's value
            Xs = self.X[:, 1:]
            G = np.linalg.pinv(Xs.T @ Xs)
            return x - Xs @ (G @ (Xs.T @ x))
        return x - self.X @ (self.XtXi @ (self.X.T @ x))

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
        if den <= 1e-12:
            return 0.0
        return float((self.e @ xt) / den)

    def shift(self, x):
        """The forecast shift d that adding x produces: d = beta_hat * x_perp."""
        xt = self.resid_x(x)
        den = float(xt @ xt)
        if den <= 1e-12:
            return np.zeros_like(xt)
        return float((self.e @ xt) / den) * xt

    def resid_sd(self, x):
        return float(np.std(self.resid_x(x), ddof=1))


def ceiling_triplet(d, e, sst):
    """The three statistics, on ONE common (d, e, SST) triple. No scale is crossed here.

    Returns (varshare, oracle, realised, c_star).
      varshare = (d.d)/SST                      -- the D084/D089 'ceiling'
      oracle   = (d.e)^2/((d.d) SST)            -- the strict bound over rescalings of d
      realised = (2 d.e - d.d)/SST              -- what adding d actually buys
      c_star   = (d.e)/(d.d)                    -- the optimal rescaling of d
    """
    d = np.asarray(d, float)
    e = np.asarray(e, float)
    sdd = float(d @ d)
    sde = float(d @ e)
    if sdd <= 0 or sst <= 0:
        return (0.0, 0.0, 0.0, np.nan)
    return (sdd / sst, (sde * sde) / (sdd * sst), (2 * sde - sdd) / sst, sde / sdd)


def perm_p(real, draws):
    draws = np.asarray(draws, float)
    m = np.isfinite(draws)
    return float((1 + (draws[m] >= real).sum()) / (1 + m.sum()))
