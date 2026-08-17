"""E1_I0054 -- INDEPENDENT re-implementation of E0_I0014's screen matrices.

Written from the SPECIFICATION in E0_I0014/s04_screen.py + rh_base.py.  E1_I0044's and
E1_I0050's scripts were read for specification and are NEVER imported or exec'd here --
that is the whole point of the reproduction.  The only inputs are source artifacts:

    E0_I0014/analysis_frame.parquet     (the frame)
    E0_I0014/screen_results.csv         (the published statistics, for anchoring)
    E0_I0014/permutation_nulls.npz      (the published draws, for the bar-anatomy check)

PARTITION GUARD: 2021-2024 only.  2025/26 is a sealed confirmation holdout and is never
opened.  Asserted on `season` and on `gdate`.

Nothing in this module or any caller writes outside
experiments/exploration/E1_I0054_absres_to_skill/.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
S49 = os.path.join(EXPL, "E1_I0049_benchmark_constants")
S50 = os.path.join(EXPL, "E1_I0050_queue_typeI")

RAW = os.path.join(HERE, "raw")
Z80 = 0.8416212335729143
SEEDS = [20260808, 20260809, 20260810]
R_NULL_COMPOSED2 = 2000
TOL_TYPEI = 0.075
TOL_BLIND = 0.20
FLOOR_POINTS_K1 = 0.00072
FLOOR_POINTS_K132 = 0.00181

# ----------------------------------------------------------------------- the frame
f = pd.read_parquet(os.path.join(S14, "analysis_frame.parquet"))
assert int(f["season"].max()) <= 2024, "PARTITION VIOLATION: season > 2024"
assert int(f["season"].min()) >= 2021, "PARTITION VIOLATION: season < 2021"
assert pd.to_datetime(f["gdate"]).max() < pd.Timestamp("2025-01-01"), "PARTITION VIOLATION: gdate"
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
seas = f["season"].to_numpy()
n = len(f)
SEASONS_PRESENT = sorted(set(int(s) for s in seas))

# ----------------------------------------------------- derived prediction-side state
for _t in ["pts", "minutes", "fga"]:
    f["%s__pred_width" % _t] = f["%s__pred_q95" % _t] - f["%s__pred_q05" % _t]
    f["%s__pred_iqr" % _t] = f["%s__pred_q75" % _t] - f["%s__pred_q25" % _t]
    _den = f["%s__pred_point" % _t].to_numpy(float).copy()
    _den[_den == 0] = np.nan
    f["%s__pred_cv" % _t] = f["%s__pred_sd" % _t].to_numpy(float) / _den
    for _c in ["is_fallback", "is_cold_start"]:
        f["%s__%s" % (_t, _c)] = f["%s__%s" % (_t, _c)].astype(float)

PLAYER_CANDS = ["pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
                "pl_prior_season_games", "pl_is_rookie_window",
                "pl_min_mean5", "pl_fga_mean5", "pl_pts_mean5", "pl_usg_mean5",
                "pl_start_frac5",
                "pl_min_sd5", "pl_min_cv5", "pl_min_rng5", "pl_fga_sd5", "pl_pts_sd5",
                "pl_usg_sd5", "pl_min_trend5", "pl_abs_min_trend5", "pl_start_switch5",
                "pl_rest_days", "pl_teamgames_since_appear", "pl_dnp_frac5"]
TEAM_CANDS = ["tm_rest_days", "tm_b2b", "tm_3in4", "tm_games_prior7d", "opp_rest_days",
              "tm_rest_diff", "tm_roster_churn_prior", "tm_newfaces_prior",
              "tm_five_tenure_prior", "tm_five_changed_prior", "tm_prior_meetings",
              "tm_first_meeting", "tm_is_home", "tm_game_idx", "opp_game_idx",
              "tm_poss_mean_prior", "opp_poss_mean_prior"]
PRED_CANDS = ["pred_point", "pred_sd", "pred_width", "pred_iqr", "pred_cv", "is_fallback",
              "fallback_level", "is_cold_start", "n_prior_games"]

_cols, _schemes, _names = [], [], []


def _add(name, v):
    scheme = "TEAM" if name in TEAM_CANDS else "PLAYER"
    v = pd.to_numeric(v, errors="coerce").astype(float).to_numpy()
    out = v.copy()
    for s in np.unique(seas):
        m = seas == s
        x = out[m]
        med = np.nanmedian(x[np.isfinite(x)]) if np.isfinite(x).any() else 0.0
        x[~np.isfinite(x)] = med
        out[m] = x
    if np.nanstd(out) == 0:
        return
    _cols.append(out); _schemes.append(scheme); _names.append(name)


for _c in PLAYER_CANDS:
    _add(_c, f[_c])
for _c in TEAM_CANDS:
    _add(_c, f[_c])
for _t in ["pts", "minutes", "fga"]:
    for _c in PRED_CANDS:
        _add("%s__%s" % (_t, _c), f["%s__%s" % (_t, _c)])

# dedupe byte-identical candidate columns (the screen's own rule)
_seen, _keep = {}, []
for _j, _nm in enumerate(_names):
    _k = _cols[_j].tobytes()
    if _k in _seen:
        continue
    _seen[_k] = _nm
    _keep.append(_j)
cols = [_cols[_j] for _j in _keep]
schemes = [_schemes[_j] for _j in _keep]
names = [_names[_j] for _j in _keep]
X = np.column_stack(cols)
C = X.shape[1]
is_player = np.array([s == "PLAYER" for s in schemes])
NAME_IX = {nm: j for j, nm in enumerate(names)}


def zwithin(v, s):
    v = np.asarray(v, float)
    out = np.full(len(v), np.nan)
    for ss in np.unique(s):
        m = s == ss
        x = v[m]
        fi = np.isfinite(x)
        if fi.sum() < 5:
            continue
        mu, sd = x[fi].mean(), x[fi].std(ddof=1)
        out[m] = (x - mu) / (sd if sd > 0 else 1.0)
    return out


DEP_NAMES = []
DEP_VALS = {}
for _t in ["pts", "minutes", "fga"]:
    for _k in ["absres", "sqres"]:
        _nm = "%s_%s" % (_t, _k)
        DEP_NAMES.append(_nm)
        DEP_VALS[_nm] = f["%s_%s" % (_k, _t)].to_numpy(float)

# ------------------------------------------------------------------------- strata
DEC_MASK = (f["pl_games_prior"].to_numpy(float) >= 8) & (f["pl_min_mean5"].to_numpy(float) >= 24)
ARM_MASKS = {
    "A4_CLEAN_DEC": (seas >= 2023) & DEC_MASK,
    "A1_FULL": np.ones(n, bool),
}

# volume-proxy bases (PREREG section 4)
MATCHED_LEVEL = {"pts": "pl_pts_mean5", "minutes": "pl_min_mean5", "fga": "pl_fga_mean5"}
MATCHED_PRED = {"pts": "pts__pred_point", "minutes": "minutes__pred_point",
                "fga": "fga__pred_point"}
ALL_LEVEL_COLS = ["pl_pts_mean5", "pl_min_mean5", "pl_fga_mean5", "pl_usg_mean5",
                  "pl_start_frac5", "pts__pred_point", "minutes__pred_point",
                  "fga__pred_point"]


def base_cols_for(base_id, dep):
    """Extra (beyond season FE) base columns for a dependent, as candidate-matrix names."""
    tgt = dep.split("_")[0]
    if base_id == "B0":
        return []
    if base_id == "B1":
        return [MATCHED_LEVEL[tgt]]
    if base_id == "B2":
        return [MATCHED_LEVEL[tgt], MATCHED_PRED[tgt]]
    if base_id == "B3":
        return list(ALL_LEVEL_COLS)
    raise KeyError(base_id)


# --------------------------------------------------------------------- arm context
def arm_context(mask, extra_base=None):
    """Self-contained arm: own rows, own season dummies, own SST, own base, own blocks.

    extra_base : list of candidate names residualised out of BOTH the response and every
                 candidate column, in addition to season fixed effects (FWL).
    """
    m = int(mask.sum())
    ss = seas[mask]
    sc = np.asarray(pd.Categorical(ss).codes, dtype=np.int64)
    nsn = int(sc.max() + 1)
    oh = np.zeros((m, nsn))
    oh[np.arange(m), sc] = 1.0
    cnt = oh.sum(0)

    def dm(M):
        M = np.asarray(M, float)
        two = M.ndim == 2
        if not two:
            M = M.reshape(-1, 1)
        out = M - oh @ ((oh.T @ M) / cnt[:, None])
        return out if two else out[:, 0]

    Xa = X[mask, :]
    Xza = np.nan_to_num(np.column_stack([zwithin(Xa[:, j], ss) for j in range(C)]))

    extra_base = list(extra_base or [])
    k_extra = nsn
    if extra_base:
        Bx = dm(np.column_stack([Xza[:, NAME_IX[c]] for c in extra_base]))
        # orthonormalise for a numerically clean projection
        Q, R_ = np.linalg.qr(Bx)
        keep = np.abs(np.diag(R_)) > 1e-9 * max(1.0, np.abs(np.diag(R_)).max())
        Q = Q[:, keep]
        k_extra = nsn + int(Q.shape[1])

        def resid(M):
            M = dm(M)
            two = M.ndim == 2
            if not two:
                M = M.reshape(-1, 1)
            out = M - Q @ (Q.T @ M)
            return out if two else out[:, 0]
    else:
        Q = None

        def resid(M):
            return dm(M)

    Xzt = resid(Xza)
    Y, Yt, SST = {}, {}, {}
    for k in DEP_NAMES:
        y = DEP_VALS[k][mask]
        Y[k] = y
        Yt[k] = resid(y.reshape(-1, 1))[:, 0]
        SST[k] = float(Yt[k] @ Yt[k])
    return dict(m=m, ss=ss, nsn=nsn, dm=dm, resid=resid, Q=Q, Xza=Xza, Xzt=Xzt,
                Y=Y, Yt=Yt, SST=SST, df=m - k_extra - 1, k_extra=k_extra, mask=mask,
                extra_base=extra_base)


def blocks_on(mask, keycol):
    """(season, key) blocks in subset-local row indices, grouped by season."""
    idx = np.where(mask)[0]
    sub = pd.DataFrame({"loc": np.arange(len(idx)), "s": seas[idx],
                        "k": f[keycol].to_numpy()[idx]})
    sub = sub.sort_values(["s", "k"])
    g = {}
    for (s, k), gg in sub.groupby(["s", "k"], sort=False):
        g.setdefault(s, []).append(np.sort(gg["loc"].to_numpy()))
    return g


def t_many(Ytil, Mt, df):
    """SIGNED t for every (col of Mt) x (col of Ytil).  Mt and Ytil ALREADY residualised."""
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Mt * Mt).sum(0)[:, None]
        sxy = Mt.T @ Ytil
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        yy = (Ytil * Ytil).sum(0)[None, :]
        sse = yy - beta * sxy
        se = np.sqrt(np.maximum(sse, 0.0) / df / np.where(sxx > 0, sxx, np.nan))
        return np.where(se > 0, beta / se, np.nan)


def t_and_dr2(ytil, Mt, df, sst):
    """SIGNED t and one-column increment dR2 of each column of Mt on ytil."""
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Mt * Mt).sum(0)
        sxy = Mt.T @ ytil
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        sse = float(ytil @ ytil) - beta * sxy
        se = np.sqrt(np.maximum(sse, 0.0) / df / np.where(sxx > 0, sxx, np.nan))
        t = np.where(se > 0, beta / se, np.nan)
        dr2 = (sst - sse) / sst
        return beta, t, dr2


# ------------------------------------------------------------------ null generators
def idx_composed2(groups, m, rng):
    """COMPOSED-2 (E1_I0044 spec): receiving block filled by a uniform resample of the
    WHOLE donor block, donor blocks assigned by a within-season permutation."""
    idx = np.arange(m)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[rng.integers(0, len(don), len(b))]
    return idx


def idx_within(groups, m, rng):
    idx = np.arange(m)
    for s, blocks in groups.items():
        for b in blocks:
            idx[b] = b[rng.permutation(len(b))]
    return idx


def idx_between(groups, m, rng):
    idx = np.arange(m)
    for s, blocks in groups.items():
        order = rng.permutation(len(blocks))
        for i, b in enumerate(blocks):
            don = blocks[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx


def flat_blocks(groups):
    bl, bs = [], []
    for s, blocks in groups.items():
        for b in blocks:
            bl.append(b); bs.append(s)
    return bl, bs
