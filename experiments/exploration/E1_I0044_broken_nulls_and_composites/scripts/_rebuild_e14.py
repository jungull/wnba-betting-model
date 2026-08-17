"""Exact re-construction of E0_I0014's screen matrices.  exec()'d by later steps.
Verified in s02: vsb reproduces to 0.000e+00, t_classical to 3.9e-15 relative
(276/348 bitwise), null_correct_sd to 2.2e-16, p_correct_level exactly.
PARTITION GUARD: asserts season <= 2024 and gdate < 2025-01-01.
"""
import os
import numpy as np
import pandas as pd

f = pd.read_parquet(os.path.join(S14, "analysis_frame.parquet"))
assert f["season"].max() <= 2024, "PARTITION VIOLATION"
assert pd.to_datetime(f["gdate"]).max() < pd.Timestamp("2025-01-01"), "PARTITION VIOLATION"
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
seas = f["season"].to_numpy(); n = len(f)

for _t in ["pts", "minutes", "fga"]:
    f["%s__pred_width" % _t] = f["%s__pred_q95" % _t] - f["%s__pred_q05" % _t]
    f["%s__pred_iqr" % _t] = f["%s__pred_q75" % _t] - f["%s__pred_q25" % _t]
    f["%s__pred_cv" % _t] = f["%s__pred_sd" % _t] / f["%s__pred_point" % _t].replace(0, np.nan)
    for _c in ["is_fallback", "is_cold_start"]:
        f["%s__%s" % (_t, _c)] = f["%s__%s" % (_t, _c)].astype(float)

PLAYER_CANDS = ["pl_games_prior", "pl_minutes_prior", "pl_career_games_prior",
                "pl_prior_season_games", "pl_is_rookie_window",
                "pl_min_mean5", "pl_fga_mean5", "pl_pts_mean5", "pl_usg_mean5", "pl_start_frac5",
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

cols, schemes, names = [], [], []
def _add(name, v, scheme):
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
    cols.append(out); schemes.append(scheme); names.append(name)

for _c in PLAYER_CANDS: _add(_c, f[_c], "PLAYER")
for _c in TEAM_CANDS:   _add(_c, f[_c], "TEAM")
for _t in ["pts", "minutes", "fga"]:
    for _c in PRED_CANDS: _add("%s__%s" % (_t, _c), f["%s__%s" % (_t, _c)], "PLAYER")

_seen, _keep = {}, []
for _j, _nm in enumerate(names):
    _k = cols[_j].tobytes()
    if _k in _seen: continue
    _seen[_k] = _nm; _keep.append(_j)
cols = [cols[_j] for _j in _keep]; schemes = [schemes[_j] for _j in _keep]
names = [names[_j] for _j in _keep]
X = np.column_stack(cols); C = X.shape[1]

def zwithin(v, s):
    v = np.asarray(v, float); out = np.full(len(v), np.nan)
    for ss in np.unique(s):
        m = s == ss; x = v[m]; fi = np.isfinite(x)
        if fi.sum() < 5: continue
        mu, sd = x[fi].mean(), x[fi].std(ddof=1)
        out[m] = (x - mu) / (sd if sd > 0 else 1.0)
    return out
Xz = np.nan_to_num(np.column_stack([zwithin(X[:, _j], seas) for _j in range(C)]))

_sc = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
NS = int(_sc.max() + 1)
onehot = np.zeros((n, NS)); onehot[np.arange(n), _sc] = 1.0
_cnt = onehot.sum(0)
def demean_mat(M):
    return M - onehot @ ((onehot.T @ M) / _cnt[:, None])
def tvec(ytil, Mtil, k_extra):
    with np.errstate(invalid="ignore", divide="ignore"):
        sxx = (Mtil * Mtil).sum(0); sxy = Mtil.T @ ytil
        beta = np.where(sxx > 0, sxy / sxx, np.nan)
        sse = float(ytil @ ytil) - beta * sxy
        df = n - k_extra - 1
        se = np.sqrt(np.maximum(sse, 0.0) / df / np.where(sxx > 0, sxx, np.nan))
        return beta, np.where(se > 0, beta / se, np.nan), sse

DEPS = []
for _t in ["pts", "minutes", "fga"]:
    DEPS.append(("%s_absres" % _t, f["absres_" + _t].to_numpy(float)))
    DEPS.append(("%s_sqres" % _t, f["sqres_" + _t].to_numpy(float)))
Ytil = {k: demean_mat(v.reshape(-1, 1))[:, 0] for k, v in DEPS}
Xztil = demean_mat(Xz)

def make_blocks(frame, keycols):
    df = pd.DataFrame({"i": np.arange(len(frame)), "s": frame["season"].to_numpy()})
    df["k"] = list(map(tuple, frame[keycols].to_numpy()))
    df = df.sort_values(["s", "k"])
    groups = {}
    for (s, k), g in df.groupby(["s", "k"], sort=False):
        groups.setdefault(s, []).append(g["i"].to_numpy())
    return groups
gp = make_blocks(f, ["player_id"]); gt = make_blocks(f, ["team_id"])
is_player = np.array([s == "PLAYER" for s in schemes])

z = np.load(os.path.join(S14, "permutation_nulls.npz"), allow_pickle=True)
assert [str(s) for s in z["names"]] == names
use_between = z["use_between"]
draws = {k: np.where(use_between[None, :], z["bet__" + k], z["win__" + k]) for k, _ in DEPS}
real_t = {k: tvec(Ytil[k], Xztil, NS)[1] for k, _ in DEPS}

# ---- DECISION STRATUM (standing programme requirement): >=8 prior appearances AND
#      >=24 trailing-5 minutes.  Columns are the screen's own.
DEC_MASK = (f["pl_games_prior"].to_numpy(float) >= 8) & (f["pl_min_mean5"].to_numpy(float) >= 24)
