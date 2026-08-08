"""Step 2 -- screen pre-game state against |residual| and residual^2, with correct-level
permutation nulls, the naive row-level null alongside, and a family-wise max-|t| correction."""
import json
import os

import numpy as np
import pandas as pd

import rh_base as B

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 80)
RNG_SEED = 20260807
N_DRAWS = 1000

f = pd.read_parquet(os.path.join(B.OUT, "analysis_frame.parquet"))
B.guard(f, "screen input")
f = f.sort_values(["season", "player_id", "gdate"]).reset_index(drop=True)
seas = f["season"].to_numpy()
n = len(f)

# ----------------------------------------------------------------- derived prediction-side state
for t in ["pts", "minutes", "fga"]:
    f["%s__pred_width" % t] = f["%s__pred_q95" % t] - f["%s__pred_q05" % t]
    f["%s__pred_iqr" % t] = f["%s__pred_q75" % t] - f["%s__pred_q25" % t]
    f["%s__pred_cv" % t] = f["%s__pred_sd" % t] / f["%s__pred_point" % t].replace(0, np.nan)
    for c in ["is_fallback", "is_cold_start"]:
        f["%s__%s" % (t, c)] = f["%s__%s" % (t, c)].astype(float)

PLAYER_CANDS = [
    # --- player sample depth ---
    "pl_games_prior", "pl_minutes_prior", "pl_career_games_prior", "pl_prior_season_games",
    "pl_is_rookie_window",
    # --- role level (contrast for the volatility terms) ---
    "pl_min_mean5", "pl_fga_mean5", "pl_pts_mean5", "pl_usg_mean5", "pl_start_frac5",
    # --- role volatility ---
    "pl_min_sd5", "pl_min_cv5", "pl_min_rng5", "pl_fga_sd5", "pl_pts_sd5", "pl_usg_sd5",
    "pl_min_trend5", "pl_abs_min_trend5", "pl_start_switch5",
    # --- player availability / schedule (AS-PLAYED dates) ---
    "pl_rest_days", "pl_teamgames_since_appear", "pl_dnp_frac5",
]
TEAM_CANDS = [
    # --- team schedule state (AS-PLAYED dates) ---
    "tm_rest_days", "tm_b2b", "tm_3in4", "tm_games_prior7d", "opp_rest_days", "tm_rest_diff",
    # --- roster stability ---
    "tm_roster_churn_prior", "tm_newfaces_prior", "tm_five_tenure_prior", "tm_five_changed_prior",
    # --- opponent unfamiliarity ---
    "tm_prior_meetings", "tm_first_meeting",
    # --- game / season context ---
    "tm_is_home", "tm_game_idx", "opp_game_idx", "tm_poss_mean_prior", "opp_poss_mean_prior",
]
PRED_CANDS = ["pred_point", "pred_sd", "pred_width", "pred_iqr", "pred_cv", "is_fallback",
              "fallback_level", "is_cold_start", "n_prior_games"]   # PLAYER scheme, target-specific

FAMILY = {}
for c in PLAYER_CANDS:
    FAMILY[c] = "player_depth" if c.startswith(("pl_games", "pl_minutes", "pl_career",
                                                "pl_prior_season", "pl_is_rookie")) else \
        ("role_level" if c.endswith("mean5") or c == "pl_start_frac5" else
         ("role_volatility" if ("sd5" in c or "cv5" in c or "rng5" in c or "trend5" in c
                                or "switch5" in c) else "player_availability"))
for c in TEAM_CANDS:
    FAMILY[c] = ("schedule_state" if c in ("tm_rest_days", "tm_b2b", "tm_3in4",
                                           "tm_games_prior7d", "opp_rest_days", "tm_rest_diff")
                 else "roster_stability" if c.startswith(("tm_roster", "tm_newfaces", "tm_five"))
                 else "opponent_unfamiliarity" if c.startswith(("tm_prior_meet", "tm_first"))
                 else "game_context")

# ----------------------------------------------------------------- build candidate matrix
cols, schemes, names, fams, missfrac = [], [], [], [], []


def add(name, v, scheme, fam):
    v = pd.to_numeric(v, errors="coerce").astype(float).to_numpy()
    mf = float(np.mean(~np.isfinite(v)))
    # within-season median imputation so one shared block-permutation index serves every candidate
    out = v.copy()
    for s in np.unique(seas):
        m = seas == s
        x = out[m]
        med = np.nanmedian(x[np.isfinite(x)]) if np.isfinite(x).any() else 0.0
        x[~np.isfinite(x)] = med
        out[m] = x
    if np.nanstd(out) == 0:
        print("  SKIP (constant) %s" % name)
        return
    cols.append(out); schemes.append(scheme); names.append(name); fams.append(fam)
    missfrac.append(mf)


for c in PLAYER_CANDS:
    add(c, f[c], "PLAYER", FAMILY[c])
for c in TEAM_CANDS:
    add(c, f[c], "TEAM", FAMILY[c])
for t in ["pts", "minutes", "fga"]:
    for c in PRED_CANDS:
        add("%s__%s" % (t, c), f["%s__%s" % (t, c)], "PLAYER", "prediction_side[%s]" % t)

# --- dedupe EXACTLY identical candidate columns (fallback_level / is_fallback / n_prior_games are
#     shared verbatim across the three targets in the v15 artifact; keeping three copies would
#     triple-count them in the family) ---
_seen, keep = {}, []
for j, nm in enumerate(names):
    key = cols[j].tobytes()
    if key in _seen:
        print("  DEDUPE %-28s identical to %s" % (nm, _seen[key]))
        continue
    _seen[key] = nm
    keep.append(j)
cols = [cols[j] for j in keep]; schemes = [schemes[j] for j in keep]
names = [names[j] for j in keep]; fams = [fams[j] for j in keep]
missfrac = [missfrac[j] for j in keep]

X = np.column_stack(cols)
C = X.shape[1]
print("\n  candidates: %d  (PLAYER-scheme %d, TEAM-scheme %d)  rows=%d"
      % (C, schemes.count("PLAYER"), schemes.count("TEAM"), n))

# z-score within season (does not change t, keeps beta comparable)
Xz = np.column_stack([B.zwithin(X[:, j], seas) for j in range(C)])
Xz = np.nan_to_num(Xz)

# ----------------------------------------------------------------- fast season-demeaning
season_codes = np.asarray(pd.Categorical(seas).codes, dtype=np.int64)
NS = int(season_codes.max() + 1)
onehot = np.zeros((n, NS))
onehot[np.arange(n), season_codes] = 1.0
cnt = onehot.sum(0)


def demean_mat(M):
    sums = onehot.T @ M                      # NS x C
    return M - onehot @ (sums / cnt[:, None])


def tvec(ytil, Mtil, k_extra):
    sxx = (Mtil * Mtil).sum(0)
    sxy = Mtil.T @ ytil
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

B.hdr("REAL EFFECTS")
real_t = {}
real_beta = {}
real_dr2 = {}
for k, y in DEPS:
    yt = Ytil[k]
    beta, tt, sse = tvec(yt, Xztil, NS)
    sst = float(yt @ yt)
    real_t[k] = tt
    real_beta[k] = beta
    real_dr2[k] = (sst - sse) / sst
print("  computed %d dependent x %d candidate cells" % (len(DEPS), C))

# ----------------------------------------------------------------- practical spread
def spread(vraw, y, seas):
    """decile / quartile spread by WITHIN-SEASON rank (method='first' so binaries still split)"""
    s = pd.Series(vraw)
    rk = s.groupby(pd.Series(seas)).rank(method="first", pct=True).to_numpy()
    out = {}
    for tag, lo, hi in [("dec", 0.10, 0.90), ("qrt", 0.25, 0.75)]:
        mlo, mhi = rk <= lo, rk >= hi
        out["%s_lo_mean" % tag] = float(y[mlo].mean())
        out["%s_hi_mean" % tag] = float(y[mhi].mean())
        out["%s_n_lo" % tag] = int(mlo.sum())
        out["%s_n_hi" % tag] = int(mhi.sum())
        out["%s_spread" % tag] = float(y[mhi].mean() - y[mlo].mean())
        out["%s_ratio" % tag] = float(y[mhi].mean() / y[mlo].mean()) if y[mlo].mean() > 0 else np.nan
    return out


# ----------------------------------------------------------------- permutation nulls
B.hdr("PERMUTATION NULLS (%d draws, correct level + naive row level)" % N_DRAWS)
gp = B.make_blocks(f, ["player_id"])
gt = B.make_blocks(f, ["team_id"])
print("  PLAYER blocks (season,player_id): %d   TEAM blocks (season,team_id): %d"
      % (sum(len(v) for v in gp.values()), sum(len(v) for v in gt.values())))
is_player = np.array([s == "PLAYER" for s in schemes])

vsb = np.array([B.var_share_between(X[:, j], gp if is_player[j] else gt, n) for j in range(C)])
print("  candidates whose variance is mostly BETWEEN blocks: %d / %d"
      % (int(np.nansum(vsb > 0.5)), C))

rng = np.random.default_rng(RNG_SEED)
nonfinite = [0]
null_bet ={k: np.zeros((N_DRAWS, C)) for k, _ in DEPS}          # BETWEEN-block reassignment
null_win = {k: np.zeros((N_DRAWS, C)) for k, _ in DEPS}          # WITHIN-block shuffle
null_row = {k: np.zeros((N_DRAWS, C)) for k, _ in DEPS}          # naive row level
for d in range(N_DRAWS):
    ip, it = B.block_index(gp, n, rng), B.block_index(gt, n, rng)
    wp, wt = B.within_block_index(gp, n, rng), B.within_block_index(gt, n, rng)
    ir = B.row_index(seas, rng)
    Xb = demean_mat(np.where(is_player[None, :], Xz[ip], Xz[it]))
    Xw = demean_mat(np.where(is_player[None, :], Xz[wp], Xz[wt]))
    Xr = demean_mat(Xz[ir])
    for k, _ in DEPS:
        yt = Ytil[k]
        for arr, Xx in ((null_bet, Xb), (null_win, Xw), (null_row, Xr)):
            v = np.abs(tvec(yt, Xx, NS)[1])
            nbad = int((~np.isfinite(v)).sum())
            if nbad:
                nonfinite[0] += nbad
                v = np.where(np.isfinite(v), v, 0.0)   # a degenerate permuted column contributes
            arr[k][d] = v                              # nothing to the max-t family statistic
    if (d + 1) % 200 == 0:
        print("    draw %d/%d" % (d + 1, N_DRAWS))

# ----------------------------------------------------------------- family-wise max-|t|
print("  non-finite permuted t values coerced to 0: %d of %d"
      % (nonfinite[0], N_DRAWS * C * len(DEPS) * 3))
# --- CORRECT-LEVEL SELECTION -------------------------------------------------------------------
# A candidate is permuted at the level at which it ACTUALLY VARIES.  If most of its variance is
# BETWEEN blocks it is a block attribute and the between-block reassignment is its null; if most
# of its variance is WITHIN blocks it is a game-to-game attribute and the within-block shuffle is
# its null.  Applying the other one is not a null at all -- it leaves the effect standing and
# returns p ~ 1 by construction.  Both are reported for every cell regardless.
use_between = np.where(np.isfinite(vsb), vsb > 0.5, True)
null_cor = {k: np.where(use_between[None, :], null_bet[k], null_win[k]) for k, _ in DEPS}
print("  correct-level null = BETWEEN-block for %d candidates, WITHIN-block for %d"
      % (int(use_between.sum()), int((~use_between).sum())))

ABS_DEPS = [k for k, _ in DEPS if k.endswith("absres")]


def maxt(nd, deps):
    return np.stack([nd[k] for k in deps], 0).max(axis=0).max(axis=1)


maxt_cor = maxt(null_cor, [k for k, _ in DEPS])
maxt_bet = maxt(null_bet, [k for k, _ in DEPS])
maxt_win = maxt(null_win, [k for k, _ in DEPS])
maxt_row = maxt(null_row, [k for k, _ in DEPS])
maxt_cor_abs = maxt(null_cor, ABS_DEPS)
real_max_all = max(np.nanmax(np.abs(real_t[k])) for k, _ in DEPS)
real_max_abs = max(np.nanmax(np.abs(real_t[k])) for k in ABS_DEPS)
p_fw_all = float((maxt_cor >= real_max_all).mean())
p_fw_abs = float((maxt_cor_abs >= real_max_abs).mean())
p_fw_bet = float((maxt_bet >= real_max_all).mean())
p_fw_win = float((maxt_win >= real_max_all).mean())
print("\n  WHOLE-SCREEN family (%d dependents x %d candidates = %d cells)"
      % (len(DEPS), C, len(DEPS) * C))
print("    observed max|t| = %.3f" % real_max_all)
for tag, a in [("CORRECT-level", maxt_cor), ("BETWEEN-block", maxt_bet),
               ("WITHIN-block", maxt_win), ("row NAIVE", maxt_row)]:
    print("      max|t| null %-14s mean=%7.3f p95=%7.3f max=%7.3f  p=%.4f"
          % (tag, a.mean(), np.percentile(a, 95), a.max(), float((a >= real_max_all).mean())))
print("    FAMILY-WISE p (whole screen, correct-level)          = %.4f" % p_fw_all)
print("    FAMILY-WISE p (|residual| dependents only, obs max|t|=%.3f) = %.4f"
      % (real_max_abs, p_fw_abs))

maxt_cor_dep = {k: null_cor[k].max(axis=1) for k, _ in DEPS}
np.savez_compressed(os.path.join(B.OUT, "permutation_nulls.npz"),
                    names=np.array(names), dependents=np.array([k for k, _ in DEPS]),
                    use_between=use_between, vsb=vsb,
                    **{("bet__" + k): null_bet[k] for k, _ in DEPS},
                    **{("win__" + k): null_win[k] for k, _ in DEPS},
                    **{("row__" + k): null_row[k] for k, _ in DEPS})

# ----------------------------------------------------------------- assemble results
rows = []
for j in range(C):
    for k, y in DEPS:
        rt = float(real_t[k][j])
        nb, nw, nr = null_bet[k][:, j], null_win[k][:, j], null_row[k][:, j]
        pb = float((nb >= abs(rt)).mean())
        pw = float((nw >= abs(rt)).mean())
        sp = spread(X[:, j], y, seas)
        sdb, sdw, sdr = nb.std(ddof=1), nw.std(ddof=1), nr.std(ddof=1)
        rows.append(dict(
            candidate=names[j], family=fams[j], perm_scheme=schemes[j],
            var_share_between_blocks=float(vsb[j]),
            missing_frac_before_impute=missfrac[j], dependent=k,
            beta_per_sd=float(real_beta[k][j]), t_classical=rt,
            delta_r2_plain_unweighted=float(real_dr2[k][j]),
            correct_null_level=("BETWEEN-block" if use_between[j] else "WITHIN-block"),
            p_correct_level=(pb if use_between[j] else pw),
            p_between_block_null=pb, p_within_block_null=pw,
            p_conservative_both=max(pb, pw),
            null_correct_sd=float(sdb if use_between[j] else sdw),
            null_between_sd=float(sdb), null_within_sd=float(sdw),
            p_row_level_NAIVE=float((nr >= abs(rt)).mean()), null_row_sd=float(sdr),
            null_inflation_factor=(float((sdb if use_between[j] else sdw) / sdr)
                                   if sdr > 0 else np.nan),
            p_familywise_within_dependent=float((maxt_cor_dep[k] >= abs(rt)).mean()),
            p_familywise_whole_screen=float((maxt_cor >= abs(rt)).mean()),
            p_familywise_absres_family=(float((maxt_cor_abs >= abs(rt)).mean())
                                        if k in ABS_DEPS else np.nan),
            **sp))
R = pd.DataFrame(rows)
R.to_csv(os.path.join(B.OUT, "screen_results.csv"), index=False)
print("  wrote screen_results.csv (%d cells)" % len(R))

pd.DataFrame({"maxt_correct_level": maxt_cor, "maxt_correct_level_absres_family": maxt_cor_abs,
              "maxt_between_block": maxt_bet, "maxt_within_block": maxt_win,
              "maxt_row_naive": maxt_row}).to_csv(
    os.path.join(B.OUT, "maxt_null_draws_whole_screen.csv"), index=False)
for k, _ in DEPS:
    pd.DataFrame({"maxt_correct_level": maxt_cor_dep[k]}).to_csv(
        os.path.join(B.OUT, "maxt_null_draws__%s.csv" % k), index=False)

B.hdr("TOP 25 CELLS BY |t| (correct-level null selected by where the candidate varies)")
sh = R.reindex(R["t_classical"].abs().sort_values(ascending=False).index).head(25)
print(sh[["candidate", "family", "perm_scheme", "var_share_between_blocks", "correct_null_level",
          "dependent", "beta_per_sd", "t_classical", "p_correct_level", "p_between_block_null",
          "p_within_block_null", "p_row_level_NAIVE", "null_inflation_factor",
          "p_familywise_whole_screen", "dec_ratio"]].to_string(index=False))

B.hdr("TOP 20 CELLS BY PRACTICAL DECILE SPREAD ON |resid| (abs-residual dependents only)")
Ra = R[R["dependent"].str.endswith("absres")].copy()
Ra["abs_dec_spread"] = Ra["dec_spread"].abs()
sh2 = Ra.sort_values("abs_dec_spread", ascending=False).head(20)
print(sh2[["candidate", "family", "dependent", "dec_lo_mean", "dec_hi_mean", "dec_spread",
           "dec_ratio", "t_classical", "p_correct_level",
           "p_familywise_whole_screen"]].to_string(index=False))

json.dump(dict(n_draws=N_DRAWS, seed=RNG_SEED, n_rows=int(n), n_candidates=int(C),
               n_dependents=len(DEPS), n_cells=int(C * len(DEPS)),
               observed_max_abs_t_whole_screen=float(real_max_all),
               observed_max_abs_t_absres_family=float(real_max_abs),
               familywise_p_whole_screen_correct_level=p_fw_all,
               familywise_p_absres_family_correct_level=p_fw_abs,
               familywise_p_between_block_null=p_fw_bet,
               familywise_p_within_block_null=p_fw_win,
               n_correct_null_between=int(use_between.sum()),
               n_correct_null_within=int((~use_between).sum()),
               null_maxt_correct=dict(mean=float(maxt_cor.mean()),
                                      p95=float(np.percentile(maxt_cor, 95)),
                                      max=float(maxt_cor.max())),
               null_maxt_correct_absres_family=dict(
                   mean=float(maxt_cor_abs.mean()),
                   p95=float(np.percentile(maxt_cor_abs, 95)),
                   max=float(maxt_cor_abs.max())),
               null_maxt_between=dict(mean=float(maxt_bet.mean()),
                                      p95=float(np.percentile(maxt_bet, 95)),
                                      max=float(maxt_bet.max())),
               null_maxt_within=dict(mean=float(maxt_win.mean()),
                                     p95=float(np.percentile(maxt_win, 95)),
                                     max=float(maxt_win.max())),
               null_maxt_row_naive=dict(mean=float(maxt_row.mean()),
                                        p95=float(np.percentile(maxt_row, 95)),
                                        max=float(maxt_row.max()))),
          open(os.path.join(B.OUT, "familywise_summary.json"), "w"), indent=2)
print("\nDONE")
