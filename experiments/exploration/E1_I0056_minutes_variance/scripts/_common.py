"""E1_I0056 -- shared machinery for the MINUTES-VARIANCE screen.

RESPONSE (D101): `absres_minutes` -- realised absolute error of the SHIPPED minutes point
forecast (`E0_I0014/analysis_frame.parquet`, column `absres_minutes`).  This is a THIRD
distinct response in the programme: not `y_pts`, not `y_ppm`, not `minutes` (the level).
Every SST in this screen is `sum((absres_minutes - mean)^2)` over the scored rows of the arm.
NOTHING here is comparable to any published points or minutes-level floor.

PARTITION GUARD: 2021-2024 only.  2025/26 is a sealed confirmation holdout, never opened.
Asserted on `season` and on the date column of every source read.

Sources (READ ONLY, never written):
    E0_I0014_residual_heterogeneity/analysis_frame.parquet   the frame + the response
    E1_I0053_minutes/scripts/_frame.parquet                  extra strictly-prior candidates
    E1_I0054_absres_to_skill/CALIBRATION.csv                 the anchors being reproduced

Nothing in this module or any caller writes outside
experiments/exploration/E1_I0056_minutes_variance/.
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")
S53 = os.path.join(EXPL, "E1_I0053_minutes")
S54 = os.path.join(EXPL, "E1_I0054_absres_to_skill")
S49 = os.path.join(EXPL, "E1_I0049_benchmark_constants")
RAW = os.path.join(HERE, "raw")

SEED = 20260809
MIN_TRAIN = 600
N_GKF = 5
Z80 = 0.8416212335729143

# ----------------------------------------------------------------------- the frame
f = pd.read_parquet(os.path.join(S14, "analysis_frame.parquet"))
assert int(f["season"].max()) <= 2024, "PARTITION VIOLATION: season > 2024"
assert int(f["season"].min()) >= 2021, "PARTITION VIOLATION: season < 2021"
assert pd.to_datetime(f["gdate"]).max() < pd.Timestamp("2025-01-01"), "PARTITION VIOLATION: gdate"
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)

# derived prediction-side state -- IDENTICAL construction to E1_I0054/_common.py
for _t in ["pts", "minutes", "fga"]:
    f["%s__pred_width" % _t] = f["%s__pred_q95" % _t] - f["%s__pred_q05" % _t]
    f["%s__pred_iqr" % _t] = f["%s__pred_q75" % _t] - f["%s__pred_q25" % _t]
    _den = f["%s__pred_point" % _t].to_numpy(float).copy()
    _den[_den == 0] = np.nan
    f["%s__pred_cv" % _t] = f["%s__pred_sd" % _t].to_numpy(float) / _den
    for _c in ["is_fallback", "is_cold_start"]:
        f["%s__%s" % (_t, _c)] = f["%s__%s" % (_t, _c)].astype(float)

seas = f["season"].to_numpy()
n = len(f)

# ------------------------------------------------- join E1_I0053's prior-only candidates
_m53 = pd.read_parquet(os.path.join(S53, "scripts", "_frame.parquet"))
assert int(_m53["season"].max()) <= 2024, "PARTITION VIOLATION (E1_I0053): season > 2024"
J53 = ["C1_player_rest", "C2_foul_rate", "C3_blowout_adj", "C5_starter_delta",
       "starter_rate_prior", "starter_rate_recent3", "foul_rate_prior",
       "prior5_sd_minutes", "prior5_minutes", "n_prior", "C6_team_rest",
       "C7_sched_density", "starter_flag", "blowout"]
_m53 = _m53[["game_id", "player_id"] + J53].copy()
_m53["game_id"] = _m53["game_id"].astype(str)
_m53["player_id"] = _m53["player_id"].astype(str)
_key = pd.DataFrame({"game_id": f["game_id"].astype(str), "player_id": f["player_id"].astype(str)})
_j = _key.merge(_m53, on=["game_id", "player_id"], how="left")
assert len(_j) == n, "join changed row count"
JOIN_HIT = float(np.isfinite(_j["C1_player_rest"].to_numpy(float)).mean())
for _c in J53:
    f["x53_%s" % _c] = pd.to_numeric(_j[_c], errors="coerce").to_numpy(float)

# `starter_flag` and `blowout` are CONTEMPORANEOUS (outcome-side).  They are carried ONLY for
# the leakage probe and the artefact checks and are NEVER placed in a forecasting feature set.
CONTEMPORANEOUS = {"x53_starter_flag", "x53_blowout"}

# ------------------------------------------------------------------- candidate columns
# Explicit literal lists.  NO substring/name-based selection anywhere in this screen.
LEVEL_COLS = ["pl_min_mean5", "pl_pts_mean5", "pl_fga_mean5", "pl_usg_mean5", "pl_start_frac5",
              "pts__pred_point", "minutes__pred_point", "fga__pred_point"]
VOLATILITY_COLS = ["pl_min_sd5", "pl_min_cv5", "pl_min_rng5", "pl_min_trend5",
                   "pl_abs_min_trend5", "pl_start_switch5", "pl_dnp_frac5",
                   "pl_pts_sd5", "pl_fga_sd5", "pl_usg_sd5"]
EXPERIENCE_COLS = ["pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
                   "pl_prior_season_games", "pl_is_rookie_window", "pl_rest_days",
                   "pl_teamgames_since_appear"]
PREDSIDE_COLS = ["pts__pred_sd", "minutes__pred_sd", "fga__pred_sd",
                 "pts__pred_cv", "minutes__pred_cv", "fga__pred_cv",
                 "pts__pred_width", "minutes__pred_width", "fga__pred_width",
                 "pts__pred_iqr", "minutes__pred_iqr", "fga__pred_iqr",
                 "pts__is_fallback", "pts__fallback_level", "pts__is_cold_start",
                 "pts__n_prior_games",
                 "minutes__is_fallback", "minutes__fallback_level",
                 "minutes__is_cold_start", "minutes__n_prior_games"]
TEAM_COLS = ["tm_rest_days", "tm_b2b", "tm_3in4", "tm_games_prior7d", "opp_rest_days",
             "tm_rest_diff", "tm_roster_churn_prior", "tm_newfaces_prior",
             "tm_five_tenure_prior", "tm_five_changed_prior", "tm_prior_meetings",
             "tm_first_meeting", "tm_is_home", "tm_game_idx", "opp_game_idx",
             "tm_poss_mean_prior", "opp_poss_mean_prior"]
X53_COLS = ["x53_C1_player_rest", "x53_C2_foul_rate", "x53_C3_blowout_adj",
            "x53_C5_starter_delta", "x53_starter_rate_prior", "x53_starter_rate_recent3",
            "x53_prior5_sd_minutes", "x53_prior5_minutes", "x53_n_prior",
            "x53_C6_team_rest", "x53_C7_sched_density"]

ALL_CANDS = (LEVEL_COLS + VOLATILITY_COLS + EXPERIENCE_COLS + PREDSIDE_COLS
             + TEAM_COLS + X53_COLS)


def _impute_by_season(v, s):
    """Season-median impute.  Same rule as E1_I0054/_common.py::_add."""
    out = np.asarray(pd.to_numeric(v, errors="coerce"), float).copy()
    for ss in np.unique(s):
        m = s == ss
        x = out[m]
        med = np.nanmedian(x[np.isfinite(x)]) if np.isfinite(x).any() else 0.0
        x[~np.isfinite(x)] = med
        out[m] = x
    return out


# derived columns that exist only in this screen, declared in the PREREG
f["inv_pts_pred_point"] = 1.0 / np.where(f["pts__pred_point"].to_numpy(float) == 0, np.nan,
                                         f["pts__pred_point"].to_numpy(float))
f["inv_min_pred_point"] = 1.0 / np.where(f["minutes__pred_point"].to_numpy(float) == 0, np.nan,
                                         f["minutes__pred_point"].to_numpy(float))
f["inv_pl_min_mean5"] = 1.0 / np.maximum(f["pl_min_mean5"].to_numpy(float), 1e-6)
f["x53_absence8"] = (f["x53_C1_player_rest"].to_numpy(float) >= 8.0).astype(float)
DERIVED_COLS = ["inv_pts_pred_point", "inv_min_pred_point", "inv_pl_min_mean5", "x53_absence8"]
ALL_CANDS = ALL_CANDS + DERIVED_COLS + sorted(CONTEMPORANEOUS)

COL = {}
for _c in ALL_CANDS:
    COL[_c] = _impute_by_season(f[_c], seas)

# ------------------------------------------------------------------------- strata
DEC_MASK = (f["pl_games_prior"].to_numpy(float) >= 8) & (f["pl_min_mean5"].to_numpy(float) >= 24)
ARM_MASKS = {
    "A4_CLEAN_DEC": (seas >= 2023) & DEC_MASK,   # the one clean window, decision stratum
    "A1_FULL": np.ones(n, bool),
}

RESP = "absres_minutes"


def arm_frame(arm="A4_CLEAN_DEC"):
    """Date-sorted arm, exactly as E1_I0054/s03 orders it (gdate, then row_uid)."""
    mask = ARM_MASKS[arm]
    idx = np.where(mask)[0]
    sub = f.iloc[idx]
    order = np.lexsort((sub["row_uid"].to_numpy(), sub["gdate"].to_numpy()))
    idx = idx[order]
    sub = f.iloc[idx].reset_index(drop=True)
    XA = np.column_stack([COL[c][idx] for c in ALL_CANDS])
    ix = {c: j for j, c in enumerate(ALL_CANDS)}
    return idx, sub, XA, ix


# ------------------------------------------------------------------- fitting helpers
def _safe_solve(A, b):
    try:
        return np.linalg.solve(A, b)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(A, b, rcond=None)[0]


def ridge_fit(Xtr, ytr, lam, standardise=True):
    """Ridge with an UNPENALISED intercept.  Zero-variance columns get a zero coefficient."""
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
    b = _safe_solve(G + lam * np.eye(G.shape[0]), Z.T @ (ytr - ym))
    b = np.where(dead, 0.0, b)
    beta = b / sd if standardise else b
    return ym - mu @ beta, beta


def tune_lambda(Xtr, ytr, grid, frac=0.75):
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
    d = np.asarray(gdate)
    uniq, first = np.unique(d, return_index=True)
    order = np.argsort(first)
    uniq = uniq[order]; first = first[order]
    out = []
    N = len(d)
    for i in range(len(uniq)):
        lo = first[i]
        hi = first[i + 1] if i + 1 < len(uniq) else N
        if lo < min_train:
            continue
        out.append((np.arange(lo), np.arange(lo, hi)))
    return out


def folds_gkf(groups, k=N_GKF, seed=20260808):
    g = np.asarray(groups)
    uniq, cnt = np.unique(g, return_counts=True)
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


def run_oof(folds, y, XA, cols, lam_grid=None, freeze_intercept=False, y_ref=None):
    """Out-of-fold prediction.  cols = list of column indices into XA.

    freeze_intercept: use the reference model's training-window mean as the intercept instead
    of refitting it (the FROZEN arm).  y_ref is the reference's own oof prediction, unused here
    except to keep the signature explicit.
    """
    lam_grid = lam_grid if lam_grid is not None else [10.0 ** e for e in range(-3, 4)]
    out = np.full(len(y), np.nan)
    for tr, te in folds:
        if len(cols) == 0:
            out[te] = y[tr].mean()
            continue
        Xt = XA[np.ix_(tr, cols)]
        lam = tune_lambda(Xt, y[tr], lam_grid) if len(cols) > 3 else 0.0
        a, b = ridge_fit(Xt, y[tr], lam)
        if freeze_intercept:
            a = y[tr].mean() - XA[np.ix_(tr, cols)].mean(0) @ b
        out[te] = a + XA[np.ix_(te, cols)] @ b
    return out


# ------------------------------------------------------------------------- metrics
def decile_table(vhat, realised, q=10):
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


def calib(vhat, realised):
    if np.std(vhat) < 1e-12:
        return np.nan, np.nan
    A = np.column_stack([np.ones(len(vhat)), vhat])
    inter, slope = np.linalg.lstsq(A, realised, rcond=None)[0]
    return float(slope), float(inter)


def signflip_p(d, cluster, R=5000, seed=SEED):
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


def block_boot(blocks_rows, stat_fn, R=2000, seed=SEED, scored=None):
    """Block bootstrap over player-season blocks.  stat_fn(row_index) -> float or nan."""
    rng = np.random.default_rng(seed)
    NB = len(blocks_rows)
    out = []
    for _ in range(R):
        take = np.concatenate([blocks_rows[b] for b in rng.integers(0, NB, NB)])
        if scored is not None:
            take = take[np.isin(take, scored)]
        if len(take) < 100:
            continue
        v = stat_fn(take)
        if np.isfinite(v):
            out.append(v)
    return np.array(out)
