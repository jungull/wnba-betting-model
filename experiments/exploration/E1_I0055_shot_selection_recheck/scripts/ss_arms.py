"""E1_I0055 -- arms, projection and null machinery.  Shared by s03/s04/s05.

THE PROJECTION (PREREG sec 5).  The candidate's fitted increment to the share vector is
    d_gz = b_z * (OS_gz - mean_g OS_.z)
The five forecast shares close iff Sum_z d_gz == 0 for every player-game g.  The
Euclidean projection onto that subspace is d^PROJ = d - rowmean(d), and the reported
per-zone effect is the slope of the PROJECTED increment on that zone's own regressor:

    beta_PROJ_z = cov(d^PROJ_.z, OS_.z) / var(OS_.z)
                = b_z - (1/5) * sum_w C[z,w] b_w / C[z,z]        (C = cov of OS columns)

Because sum_z OS_gz == 0 exactly (asserted in CLOSURE.md at 1.11e-16 over 10,245
player-games), a genuinely COMMON slope is INVARIANT under this projection.  The
projection removes only the part of the slope spread that cannot be a share increment.
"""
from __future__ import annotations

import numpy as np

NZ = 5


# ------------------------------------------------------------------ estimators ----
def slopes_frozen(X, Y):
    """Per-zone OLS slope of Y[:,z] on [1, X[:,z]].  Y is the offset response."""
    xm = X.mean(axis=0)
    ym = Y.mean(axis=0)
    dx = X - xm
    dy = Y - ym
    return (dx * dy).sum(axis=0) / (dx * dx).sum(axis=0)


def slopes_unfrozen(X, Yres, Q):
    """Per-zone coefficient on X[:,z] in OLS of share_z on [1, base_z, X[:,z]].

    `Yres` is the response already residualised on the (fixed) base, `Q` is a list of
    n x k orthonormal bases of the base design, one per zone.  Frisch-Waugh.
    """
    out = np.empty(NZ)
    for z in range(NZ):
        x = X[:, z]
        xr = x - Q[z] @ (Q[z].T @ x)
        out[z] = float(xr @ Yres[:, z] / (xr @ xr))
    return out


def cov_cols(X):
    Xc = X - X.mean(axis=0)
    return (Xc.T @ Xc) / (len(X) - 1)


def project_slopes(b, C):
    """beta_PROJ from the RAW per-zone slopes and the OS column covariance."""
    d = np.diag(C)
    return b - (C @ b) / (NZ * d)


def common_slope(X, Y):
    """PROJ_COMMON: the single closure-legal slope, zone-specific intercepts."""
    dx = X - X.mean(axis=0)
    dy = Y - Y.mean(axis=0)
    return float((dx * dy).sum() / (dx * dx).sum())


def arm_stats(X, Y_frozen, Yres_unfrozen, Q):
    """All four (projection x frozen) statistic vectors for one design."""
    C = cov_cols(X)
    bF = slopes_frozen(X, Y_frozen)
    bU = slopes_unfrozen(X, Yres_unfrozen, Q)
    return dict(RAW_FROZEN=bF, PROJ_FROZEN=project_slopes(bF, C),
                RAW_UNFROZEN=bU, PROJ_UNFROZEN=project_slopes(bU, C),
                COMMON_FROZEN=np.full(NZ, common_slope(X, Y_frozen)),
                COMMON_UNFROZEN=np.full(NZ, common_slope(X, Yres_unfrozen)))


ARMS = ["RAW_FROZEN", "PROJ_FROZEN", "RAW_UNFROZEN", "PROJ_UNFROZEN",
        "COMMON_FROZEN", "COMMON_UNFROZEN"]


# ------------------------------------------------------------------------ nulls ---
class OppGameIndex:
    """Opponent-game bookkeeping for the row set: each player-game points at the
    opponent-game whose five-zone allowance vector it consumes."""

    def __init__(self, season, opp, gdate, gid):
        key = np.array([f"{s}|{o}|{g}" for s, o, g in zip(season, opp, gid)])
        uk, self.unit = np.unique(key, return_inverse=True)
        M = len(uk)
        # one representative row per opponent-game, for ordering
        first = np.zeros(M, int)
        first[self.unit[::-1]] = np.arange(len(key))[::-1]
        self.og_season = np.asarray(season)[first]
        self.og_opp = np.asarray(opp)[first]
        self.og_date = np.asarray(gdate)[first]
        self.M = M
        # ordinal of each opponent-game inside its (season, opp) unit
        tskey = np.array([f"{s}|{o}" for s, o in zip(self.og_season, self.og_opp)])
        self.ts_keys, ts_inv = np.unique(tskey, return_inverse=True)
        self.ts_inv = ts_inv
        self.ord = np.zeros(M, int)
        self.ts_members = []
        for t in range(len(self.ts_keys)):
            idx = np.where(ts_inv == t)[0]
            idx = idx[np.argsort(self.og_date[idx], kind="stable")]
            self.ord[idx] = np.arange(len(idx))
            self.ts_members.append(idx)
        self.ts_season = np.array([k.split("|")[0] for k in self.ts_keys])
        self.season_groups = [np.where(self.ts_season == s)[0]
                              for s in np.unique(self.ts_season)]
        self.og_season_groups = [np.where(self.og_season.astype(str) == s)[0]
                                 for s in np.unique(self.og_season.astype(str))]

    # -- N_TSTRAJ: swap whole team-season TRAJECTORIES within season (the matched null)
    def draw_tstraj(self, rng):
        src = np.arange(self.M)
        for grp in self.season_groups:
            perm = rng.permutation(grp)
            for a, bpos in zip(grp, perm):
                ia, ib = self.ts_members[a], self.ts_members[bpos]
                k = np.minimum(np.arange(len(ia)), len(ib) - 1)
                src[ia] = ib[k]
        return src

    # -- N_OPPGAME: permute opponent-game vectors within season (KNOWN TOO NARROW)
    def draw_oppgame(self, rng):
        src = np.arange(self.M)
        for grp in self.og_season_groups:
            src[grp] = rng.permutation(grp)
        return src


def blind_player_map(pid, rng):
    """N_BLIND: cyclically shift the candidate WITHIN each player (a within-entity null
    applied to a between-opponent candidate).  Deliberately blind."""
    out = np.arange(len(pid))
    order = np.argsort(pid, kind="stable")
    up, starts = np.unique(np.asarray(pid)[order], return_index=True)
    bounds = list(starts) + [len(pid)]
    for i in range(len(up)):
        idx = order[bounds[i]:bounds[i + 1]]
        if len(idx) > 1:
            out[idx] = np.roll(idx, rng.integers(1, len(idx)))
    return out
