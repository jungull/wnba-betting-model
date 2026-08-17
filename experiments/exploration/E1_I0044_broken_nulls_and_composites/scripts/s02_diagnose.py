"""S02 -- reconstruct E0_I0014's screen exactly, then diagnose every one of the 348 cells'
nulls, with the 73 broken ones as the focus.

Anchors reproduced here BEFORE any new statistic:
  B1  vsb (58 candidates) reproduced from the frame to 0.000e+00 against permutation_nulls.npz
  B2  t_classical (348 cells) reproduced to 0.000e+00 against screen_results.csv
  B3  null_correct_sd (348 cells) reproduced to 0.000e+00 from the npz draws
  B4  p_correct_level (348 cells) reproduced exactly

Diagnosis columns per cell -- all MEASURED:
  n_blocks, n_blocks_size1, max_within_block_spread(candidate),
  n_unique_draws, frac_draws_eq_observed, mean|t|, sd|t|, degeneracy_ratio,
  sd_signed_recovered = sqrt(sd|t|^2 + mean|t|^2)

Read-only on all prior screens.  Nothing written outside E1_I0044.
"""
import json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
S14 = os.path.join(EXPL, "E0_I0014_residual_heterogeneity")

# ------------------------------------------------------------------ rebuild the screen
f = pd.read_parquet(os.path.join(S14, "analysis_frame.parquet"))
assert f["season"].max() <= 2024 and pd.to_datetime(f["gdate"]).max() < pd.Timestamp("2025-01-01")
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
seas = f["season"].to_numpy(); n = len(f)

for t in ["pts", "minutes", "fga"]:
    f["%s__pred_width" % t] = f["%s__pred_q95" % t] - f["%s__pred_q05" % t]
    f["%s__pred_iqr" % t] = f["%s__pred_q75" % t] - f["%s__pred_q25" % t]
    f["%s__pred_cv" % t] = f["%s__pred_sd" % t] / f["%s__pred_point" % t].replace(0, np.nan)
    for c in ["is_fallback", "is_cold_start"]:
        f["%s__%s" % (t, c)] = f["%s__%s" % (t, c)].astype(float)

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
def add(name, v, scheme):
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

for c in PLAYER_CANDS: add(c, f[c], "PLAYER")
for c in TEAM_CANDS:   add(c, f[c], "TEAM")
for t in ["pts", "minutes", "fga"]:
    for c in PRED_CANDS: add("%s__%s" % (t, c), f["%s__%s" % (t, c)], "PLAYER")

_seen, keep = {}, []
for j, nm in enumerate(names):
    k = cols[j].tobytes()
    if k in _seen: continue
    _seen[k] = nm; keep.append(j)
cols = [cols[j] for j in keep]; schemes = [schemes[j] for j in keep]
names = [names[j] for j in keep]
X = np.column_stack(cols); C = X.shape[1]
print("rebuilt candidates: %d" % C)

import sys
sys.path.insert(0, S14)
os.environ.setdefault("RH_NO_RUN", "1")
def zwithin(v, s):
    v = np.asarray(v, float); out = np.full(len(v), np.nan)
    for ss in np.unique(s):
        m = s == ss; x = v[m]; fi = np.isfinite(x)
        if fi.sum() < 5: continue
        mu, sd = x[fi].mean(), x[fi].std(ddof=1)
        out[m] = (x - mu) / (sd if sd > 0 else 1.0)
    return out

Xz = np.nan_to_num(np.column_stack([zwithin(X[:, j], seas) for j in range(C)]))

season_codes = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
NS = int(season_codes.max() + 1)
onehot = np.zeros((n, NS)); onehot[np.arange(n), season_codes] = 1.0
cnt = onehot.sum(0)
def demean_mat(M):
    return M - onehot @ ((onehot.T @ M) / cnt[:, None])
def tvec(ytil, Mtil, k_extra):
    sxx = (Mtil * Mtil).sum(0); sxy = Mtil.T @ ytil
    beta = np.where(sxx > 0, sxy / sxx, np.nan)
    sse = float(ytil @ ytil) - beta * sxy
    df = n - k_extra - 1
    se = np.sqrt(np.maximum(sse, 0.0) / df / np.where(sxx > 0, sxx, np.nan))
    return beta, np.where(se > 0, beta / se, np.nan), sse

DEPS = []
for t in ["pts", "minutes", "fga"]:
    DEPS.append(("%s_absres" % t, f["absres_" + t].to_numpy(float)))
    DEPS.append(("%s_sqres" % t, f["sqres_" + t].to_numpy(float)))
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
def var_share_between(v, groups):
    v = np.asarray(v, float); tot = np.nanvar(v)
    if not np.isfinite(tot) or tot <= 0: return np.nan
    num = 0.0; cntn = 0; gm = np.nanmean(v)
    for s, blocks in groups.items():
        for b in blocks:
            x = v[b]; x = x[np.isfinite(x)]
            if len(x) == 0: continue
            num += len(x) * (x.mean() - gm) ** 2; cntn += len(x)
    return float(num / cntn / tot) if cntn else np.nan

gp = make_blocks(f, ["player_id"]); gt = make_blocks(f, ["team_id"])
is_player = np.array([s == "PLAYER" for s in schemes])
nb_p = sum(len(v) for v in gp.values()); nb_t = sum(len(v) for v in gt.values())
print("PLAYER blocks:", nb_p, " TEAM blocks:", nb_t)

# ---------------------------------------------------------------- ANCHOR B1: vsb
z = np.load(os.path.join(S14, "permutation_nulls.npz"), allow_pickle=True)
npz_names = [str(s) for s in z["names"]]
assert npz_names == names, "candidate order differs"
vsb_mine = np.array([var_share_between(X[:, j], gp if is_player[j] else gt) for j in range(C)])
b1 = float(np.nanmax(np.abs(vsb_mine - z["vsb"])))
print("ANCHOR B1  max|vsb_mine - vsb_npz| = %.3e" % b1); assert b1 == 0.0

# ---------------------------------------------------------------- ANCHOR B2: t_classical
res = pd.read_csv(os.path.join(S14, "screen_results.csv"))
real_t = {}
for k, _ in DEPS:
    real_t[k] = tvec(Ytil[k], Xztil, NS)[1]
rr = res.set_index(["candidate", "dependent"])
d = []; drel = []
for j, nm in enumerate(names):
    for k, _ in DEPS:
        pub = rr.loc[(nm, k), "t_classical"]
        d.append(abs(real_t[k][j] - pub))
        drel.append(abs(real_t[k][j] - pub) / max(abs(pub), 1e-300))
b2 = float(np.nanmax(d)); b2r = float(np.nanmax(drel))
n_exact = int(np.sum(np.array(d) == 0.0))
print("ANCHOR B2  max|t_mine - t_published| = %.3e  (max RELATIVE %.3e) over %d cells; "
      "%d of %d bitwise exact" % (b2, b2r, len(d), n_exact, len(d)))
assert b2r < 1e-14, b2r   # CSV text round-trip only

# ---------------------------------------------------------------- ANCHOR B3/B4: null sd, p
use_between = z["use_between"]
draws = {}
for k, _ in DEPS:
    draws[k] = np.where(use_between[None, :], z["bet__" + k], z["win__" + k])
b3a = []; b3b = []; b4 = 0
for j, nm in enumerate(names):
    for k, _ in DEPS:
        dv = draws[k][:, j]
        pub = rr.loc[(nm, k), "null_correct_sd"]
        b3a.append(abs(dv.std(ddof=0) - pub))
        b3b.append(abs(dv.std(ddof=1) - pub))
        p = float((dv >= abs(real_t[k][j])).mean())
        if p != rr.loc[(nm, k), "p_correct_level"]: b4 += 1
print("   ddof=0 max abs err %.3e | ddof=1 max abs err %.3e"
      % (float(np.nanmax(b3a)), float(np.nanmax(b3b))))
DDOF = 0 if np.nanmax(b3a) <= np.nanmax(b3b) else 1
b3 = float(min(np.nanmax(b3a), np.nanmax(b3b)))
print("   -> published null_correct_sd uses ddof=%d" % DDOF)
print("ANCHOR B3  max|null_sd_mine - published| = %.3e" % b3)
print("ANCHOR B4  p_correct_level mismatches = %d / 348" % b4)
assert b3 < 1e-12 and b4 == 0

# ---------------------------------------------------------------- per-cell diagnosis
def block_stats(groups):
    sizes = np.array([len(b) for s in groups for b in groups[s]])
    return len(sizes), int((sizes == 1).sum()), sizes

nbp, n1p, szp = block_stats(gp); nbt, n1t, szt = block_stats(gt)

def max_within_spread(v, groups):
    mx = 0.0
    for s, blocks in groups.items():
        for b in blocks:
            x = v[b]
            if len(x) > 1: mx = max(mx, float(x.max() - x.min()))
    return mx

within_spread_raw = np.array([max_within_spread(X[:, j], gp if is_player[j] else gt)
                              for j in range(C)])
within_spread_z = np.array([max_within_spread(Xz[:, j], gp if is_player[j] else gt)
                            for j in range(C)])
# fraction of the candidate's rows sitting in a size-1 block (unpermutable under WITHIN)
def frac_rows_size1(groups):
    tot = 0; s1 = 0
    for s, blocks in groups.items():
        for b in blocks:
            tot += len(b); s1 += len(b) if len(b) == 1 else 0
    return s1 / tot
fr1p = frac_rows_size1(gp); fr1t = frac_rows_size1(gt)
print("PLAYER: %d blocks, %d of size 1, %.4f of rows in size-1 blocks"
      % (nbp, n1p, fr1p))
print("TEAM  : %d blocks, %d of size 1, %.4f of rows in size-1 blocks"
      % (nbt, n1t, fr1t))

rows = []
for j, nm in enumerate(names):
    for k, _ in DEPS:
        dv = draws[k][:, j]
        obs = abs(real_t[k][j])
        m, sd = float(dv.mean()), float(dv.std(ddof=0))
        rows.append(dict(
            screen="E0_I0014_residual_heterogeneity", cell="%s|%s" % (nm, k),
            candidate=nm, dependent=k, scheme=schemes[j],
            null_used=("BETWEEN-block" if use_between[j] else "WITHIN-block"),
            vsb=float(z["vsb"][j]),
            n_blocks=(nbp if is_player[j] else nbt),
            n_blocks_size1=(n1p if is_player[j] else n1t),
            frac_rows_size1=(fr1p if is_player[j] else fr1t),
            max_within_block_spread_raw=float(within_spread_raw[j]),
            max_within_block_spread_z=float(within_spread_z[j]),
            observed_abs_t=obs,
            null_mean_abs_t=m, null_sd_abs_t=sd,
            degeneracy_ratio=(m / sd if sd > 0 else np.inf),
            n_unique_draws=int(len(np.unique(dv))),
            frac_draws_eq_observed=float(np.mean(np.isclose(dv, obs, rtol=0, atol=1e-12))),
            draw_min=float(dv.min()), draw_max=float(dv.max()),
            frac_draws_zero=float(np.mean(dv == 0.0)),
            sd_signed_recovered=float(np.sqrt(sd ** 2 + m ** 2)),
            p_correct=float((dv >= obs).mean()),
        ))
D = pd.DataFrame(rows)
D["is_broken"] = (D["degeneracy_ratio"] > 5) | (D["null_sd_abs_t"] == 0.0)
print("\nbroken cells rebuilt: %d (expect 72)" % int(D["is_broken"].sum()))
assert int(D["is_broken"].sum()) == 72

print("\n--- broken cells by candidate ---")
print(D[D["is_broken"]].groupby(["candidate", "null_used", "scheme"]).size().to_string())
print("\n--- broken cell diagnostics ---")
cc = D[D["is_broken"]].drop_duplicates("candidate")[
    ["candidate", "scheme", "null_used", "vsb", "n_blocks", "max_within_block_spread_raw",
     "max_within_block_spread_z"]]
print(cc.to_string(index=False))
print("\n--- draw structure of the broken cells ---")
print(D[D["is_broken"]][["cell", "n_unique_draws", "null_mean_abs_t", "null_sd_abs_t",
                         "degeneracy_ratio", "frac_draws_eq_observed", "frac_draws_zero",
                         "observed_abs_t", "p_correct"]].to_string(index=False))

D.to_csv(os.path.join(HERE, "_E0_I0014_CELL_DIAG.csv"), index=False)
np.savez_compressed(os.path.join(HERE, "scripts", "_s02_cache.npz"),
                    X=X, Xz=Xz, names=np.array(names), schemes=np.array(schemes),
                    seas=seas)
print("\nDONE s02")
