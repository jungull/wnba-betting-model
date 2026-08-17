"""E1_I0056 -- machinery added AFTER the preregistration was hashed.

This module never modifies `_common.py` (s00 depends on it byte for byte).  It ADDS:
  * a strictly-prior (leak-free) imputation, replacing `_common._impute_by_season`, which fills
    from the season median over ALL rows including the future -- a T1 exposure measured at
    385/3549 rows for every `x53_*` column and 3 rows for `pl_dnp_frac5`;
  * the preregistered level ladder and non-level blocks, as literal lists;
  * cyclic / shuffle within-player-season permutation of a whole column block;
  * paired cluster sign-flip and block bootstrap on stored out-of-fold predictions.

Nothing here writes outside experiments/exploration/E1_I0056_minutes_variance/.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (ALL_CANDS, ARM_MASKS, HERE, MIN_TRAIN, f, folds_wf, n,  # noqa: F401
                     ridge_fit, seas, tune_lambda)

RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)

SEED_NULL = 20260817
SEED_BOOT = 20260817
SEED_INJ = 20260901
LAM_GRID = [10.0 ** e for e in range(-3, 4)]

# --------------------------------------------------------------- preregistered column blocks
L1 = ["pl_min_mean5"]
L2 = L1 + ["pl_min_mean5__sq", "pl_min_mean5__cu"]
L3 = L2 + ["minutes__pred_point", "minutes__pred_point__sq", "inv_min_pred_point"]
L4 = ["pl_min_mean5", "pl_pts_mean5", "pl_fga_mean5", "pl_usg_mean5", "pl_start_frac5",
      "minutes__pred_point", "pts__pred_point", "fga__pred_point"]
L5 = L4 + ["pl_min_mean5__sq", "pl_min_mean5__cu", "minutes__pred_point__sq",
           "pts__pred_point__sq", "inv_pl_min_mean5", "inv_min_pred_point", "inv_pts_pred_point"]
LADDER = {"L0": [], "L1": L1, "L2": L2, "L3": L3, "L4": L4, "L5": L5}

N_VOL = ["pl_min_sd5", "pl_min_cv5", "pl_min_rng5", "pl_min_trend5", "pl_abs_min_trend5",
         "pl_start_switch5", "pl_dnp_frac5", "pl_pts_sd5", "pl_fga_sd5", "pl_usg_sd5"]
N_EXP = ["pl_games_prior", "pl_minutes_prior", "pl_career_games_prior", "pl_prior_season_games",
         "pl_is_rookie_window", "pl_rest_days", "pl_teamgames_since_appear",
         "minutes__n_prior_games", "pts__n_prior_games"]
N_TEAM = ["tm_rest_days", "tm_b2b", "tm_3in4", "tm_games_prior7d", "opp_rest_days",
          "tm_rest_diff", "tm_roster_churn_prior", "tm_newfaces_prior", "tm_five_tenure_prior",
          "tm_five_changed_prior", "tm_prior_meetings", "tm_first_meeting", "tm_is_home",
          "tm_game_idx", "opp_game_idx", "tm_poss_mean_prior", "opp_poss_mean_prior"]
BLOCK_N = N_VOL + N_EXP + N_TEAM
X53_OK = ["x53_C1_player_rest", "x53_C2_foul_rate", "x53_C3_blowout_adj", "x53_C5_starter_delta",
          "x53_starter_rate_prior", "x53_starter_rate_recent3", "x53_prior5_sd_minutes",
          "x53_prior5_minutes", "x53_n_prior", "x53_C6_team_rest", "x53_C7_sched_density",
          "x53_absence8"]
BLOCK_N2 = BLOCK_N + X53_OK
VSIG = ["pl_abs_min_trend5", "pl_dnp_frac5", "pl_min_rng5", "pl_min_sd5", "pl_start_switch5",
        "pts__pred_cv", "pts__pred_width"]

DERIVED_SQ = {"pl_min_mean5__sq": ("pl_min_mean5", 2), "pl_min_mean5__cu": ("pl_min_mean5", 3),
              "minutes__pred_point__sq": ("minutes__pred_point", 2),
              "pts__pred_point__sq": ("pts__pred_point", 2)}

RAW_NEEDED = sorted(set(
    L5 + BLOCK_N2 + VSIG + ["minutes__pred_sd", "pl_min_mean5", "minutes__pred_point"]
) - set(DERIVED_SQ))


# ------------------------------------------------------------------- leak-free imputation
def impute_prior(v, gdate, season):
    """Fill non-finite entries from the expanding median over STRICTLY EARLIER dates in the same
    season.  0.0 when no prior row exists.  Never reads a row at or after the target date."""
    v = np.asarray(pd.to_numeric(v, errors="coerce"), float).copy()
    out = v.copy()
    nfill = 0
    for s in np.unique(season):
        m = np.where(season == s)[0]
        d = gdate[m]
        order = np.argsort(d, kind="stable")
        mi = m[order]
        du = d[order]
        vals = v[mi]
        pool = []
        i = 0
        run_med = 0.0
        while i < len(mi):
            j = i
            while j < len(mi) and du[j] == du[i]:
                j += 1
            for k in range(i, j):
                if not np.isfinite(vals[k]):
                    out[mi[k]] = run_med
                    nfill += 1
            for k in range(i, j):
                if np.isfinite(vals[k]):
                    pool.append(vals[k])
            if pool:
                run_med = float(np.median(pool))
            i = j
    return out, nfill


def impute_season_median(v, season):
    """The INHERITED rule from `_common._impute_by_season` -- reads the whole season, future
    included.  Kept only to reproduce the sibling's anchors."""
    out = np.asarray(pd.to_numeric(v, errors="coerce"), float).copy()
    for s in np.unique(season):
        m = season == s
        x = out[m]
        med = np.nanmedian(x[np.isfinite(x)]) if np.isfinite(x).any() else 0.0
        x[~np.isfinite(x)] = med
        out[m] = x
    return out


# ------------------------------------------------------------------------------- the arm
def build(arm="A4_CLEAN_DEC", impute="prior"):
    """Date-ordered arm matrix.  Returns (sub, X, ix, meta)."""
    mask = ARM_MASKS[arm]
    idx = np.where(mask)[0]
    s0 = f.iloc[idx]
    order = np.lexsort((s0["row_uid"].to_numpy(), s0["gdate"].to_numpy()))
    idx = idx[order]
    sub = f.iloc[idx].reset_index(drop=True)
    gd = sub["gdate"].to_numpy()
    ss = sub["season"].to_numpy()
    cols, fills = {}, {}
    for c in RAW_NEEDED:
        raw = pd.to_numeric(f[c], errors="coerce").to_numpy(float)[idx]
        if impute == "prior":
            v, k = impute_prior(raw, gd, ss)
        else:
            v, k = impute_season_median(raw, ss), int((~np.isfinite(raw)).sum())
        cols[c] = v
        fills[c] = int(k)
    for name, (src, p) in DERIVED_SQ.items():
        cols[name] = cols[src] ** p
    names = sorted(cols)
    X = np.column_stack([cols[c] for c in names])
    ix = {c: j for j, c in enumerate(names)}
    meta = dict(n=len(sub), fills=fills,
                psblock=pd.factorize(pd.Series(list(zip(sub["season"], sub["player_id"]))))[0],
                tgblock=pd.factorize(sub["game_id"].astype(str) + "|"
                                     + sub["team_id"].astype(str))[0],
                gdate=gd, season=ss)
    return sub, X, ix, meta


# ------------------------------------------------------------------------------- OOF engine
def oof(folds, y, X, cols):
    out = np.full(len(y), np.nan)
    for tr, te in folds:
        if len(cols) == 0:
            out[te] = y[tr].mean()
            continue
        Xt = X[np.ix_(tr, cols)]
        lam = tune_lambda(Xt, y[tr], LAM_GRID) if len(cols) > 3 else 0.0
        a, b = ridge_fit(Xt, y[tr], lam)
        out[te] = a + X[np.ix_(te, cols)] @ b
    return out


def sse(y, yhat, s):
    e = y[s] - yhat[s]
    return float(e @ e)


def sst_of(y, s):
    z = y[s] - y[s].mean()
    return float(z @ z)


def decile_ratio(vhat, realised, q=10):
    r = pd.Series(vhat).rank(method="first", pct=True).to_numpy()
    lo = realised[r <= 1.0 / q]
    hi = realised[r > 1.0 - 1.0 / q]
    return (float(hi.mean() / lo.mean()) if lo.mean() > 0 else np.nan,
            float(lo.mean()), float(hi.mean()))


def calib_slope(vhat, realised):
    if np.std(vhat) < 1e-12:
        return np.nan, np.nan
    A = np.column_stack([np.ones(len(vhat)), vhat])
    inter, slope = np.linalg.lstsq(A, realised, rcond=None)[0]
    return float(slope), float(inter)


def spearman(a, b):
    ra = pd.Series(a).rank().to_numpy()
    rb = pd.Series(b).rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return np.nan
    return float(np.corrcoef(ra, rb)[0, 1])


# --------------------------------------------------------- within-block permutation of a block
def block_index_lists(block, gdate):
    """Row indices of each block, in DATE ORDER -- the order a cyclic shift must respect."""
    out = []
    for b in range(int(block.max()) + 1):
        r = np.where(block == b)[0]
        out.append(r[np.argsort(gdate[r], kind="stable")])
    return out


def permute_block(X, cols, blocks, rng, scheme):
    """Return a COPY of X with the named columns permuted WITHIN each block.

    `cyclic`  -- one random cyclic shift per block, applied identically to every column, so the
                 serial structure of each column AND the alignment between columns survive; only
                 the alignment to the response is destroyed (D093).
    `shuffle` -- one random permutation per block, applied identically to every column.  Destroys
                 serial structure; run ONLY to measure the anticonservatism gap.
    `zero`    -- cyclic shift with offset 0.  The vacuity control: it must be the identity.
    """
    Z = X.copy()
    for rows in blocks:
        k = len(rows)
        if k < 2:
            continue
        if scheme == "cyclic":
            sft = int(rng.integers(0, k))
            take = rows[(np.arange(k) + sft) % k]
        elif scheme == "shuffle":
            take = rows[rng.permutation(k)]
        elif scheme == "zero":
            take = rows
        else:
            raise KeyError(scheme)
        for c in cols:
            Z[rows, c] = X[take, c]
    return Z


# ------------------------------------------------------------------------- paired sign-flip
def signflip(d, cluster, R, seed):
    d = np.asarray(d, float)
    cl = pd.factorize(np.asarray(cluster))[0]
    K = int(cl.max()) + 1
    cs = np.bincount(cl, weights=d, minlength=K)
    obs = float(cs.sum())
    rng = np.random.default_rng(seed)
    S = rng.integers(0, 2, size=(R, K)) * 2 - 1
    draws = S @ cs
    p = float((np.sum(np.abs(draws) >= abs(obs)) + 1) / (R + 1))
    return obs, p, draws


def block_boot_dr2(y, yref, ycand, scored, blocks, R, seed):
    """Block bootstrap of dR2 over player-season blocks, from STORED oof predictions."""
    rng = np.random.default_rng(seed)
    sset = set(scored.tolist())
    bl = [np.array([r for r in rows if r in sset]) for rows in blocks]
    bl = [b for b in bl if len(b)]
    NB = len(bl)
    out = []
    for _ in range(R):
        take = np.concatenate([bl[i] for i in rng.integers(0, NB, NB)])
        if len(take) < 100:
            continue
        yy = y[take]
        z = yy - yy.mean()
        sst = float(z @ z)
        if sst <= 0:
            continue
        e1 = yy - yref[take]
        e2 = yy - ycand[take]
        out.append(float((e1 @ e1 - e2 @ e2) / sst))
    return np.array(out)
