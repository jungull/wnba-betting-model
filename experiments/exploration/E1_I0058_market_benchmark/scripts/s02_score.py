"""s02_score.py -- Q1 market accuracy, Q2 model accuracy, Q3 forecast encompassing.

Executes PREREG sections 4, 5 and 6 exactly. Seeds and draw counts are read from the frozen
PREREG and are not parameters of this script.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mb_base as mb  # noqa: E402

L = mb.Tee(os.path.join(mb.EXP_DIR, "run_log_s02.txt"))
PRE = open(os.path.join(mb.EXP_DIR, "PREREG.sha256")).read().split()[0]

# ---- FROZEN BY PREREG -----------------------------------------------------------------
SEED_BOOT, SEED_PERM, N_BOOT, N_PERM = 20240817, 20240818, 5000, 5000
MATERIALITY = 0.10
ALPHA = 0.05
POWER_K = 2.802  # z_.975 + z_.80

A = pd.read_csv(os.path.join(mb.OUT, "analysis_frame.csv"))
A["game_date"] = pd.to_datetime(A.game_date)
assert set(A.season.unique()) == {2024}, "PARTITION"
L(f"E1_I0058 s02 -- scoring under PREREG {PRE}")
L(f"  seeds boot={SEED_BOOT} perm={SEED_PERM}; draws {N_BOOT}/{N_PERM}; materiality "
  f"{MATERIALITY}; alpha {ALPHA}")
L(f"  n={len(A)}  players={A.player_id.nunique()}  games={A.gid.nunique()}  season 2024 only")
L("  POPULATION: book-priced player-games only (40.2% of played rows). Every number below")
L("              is conditional on that selection and does NOT generalise to unpriced players.")
L("=" * 92)

y = A.pts.values.astype(float)


def ols(X, yy):
    return np.linalg.lstsq(X, yy, rcond=None)[0]


def design(cols):
    return np.column_stack([np.ones(len(A))] + [A[c].values.astype(float) for c in cols])


# ============================================================================================
L("")
L("--- Q1/Q2. ACCURACY OF EACH FORECAST (reference-free headline metrics) -----------------")
L("")
L("  arm  what it is                                   MAE     RMSE     bias(f-y)   corr")
ARMS = [("M1", "raw consensus line (median over books)"),
        ("M2", "de-vigged central estimate, proportional [PRIMARY MARKET]"),
        ("M3", "de-vigged, additive margin [SENSITIVITY]"),
        ("F1", "model E[pts|active], cbs_v15_player_oof_v5 [PRIMARY MODEL]"),
        ("F2", "model E[pts|active], cbs_v14_player_oof [ROBUSTNESS]")]
acc = {}
for k, desc in ARMS:
    v = A[k].values.astype(float)
    ok = np.isfinite(v)
    e = v[ok] - y[ok]
    acc[k] = {"n": int(ok.sum()), "mae": float(np.abs(e).mean()),
              "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean()),
              "corr": float(np.corrcoef(v[ok], y[ok])[0, 1]), "desc": desc}
    L(f"  {k:<4} {desc:<44} {acc[k]['mae']:.4f}  {acc[k]['rmse']:.4f}  "
      f"{acc[k]['bias']:+.4f}     {acc[k]['corr']:.4f}")
L(f"  (n = {len(A)} for all arms except F2, n = {acc['F2']['n']})")

L("")
L("--- R-SQUARED, AGAINST A NAMED REFERENCE LADDER (D087/D136) ----------------------------")
L("  The reference is named beside every number because this program has seen the same")
L("  result move 6.5x, 4.6x and 8.12 points on reference choice alone.")
psm = A.groupby("player_id").pts.transform("mean").values
refs = {"R0_grand_mean": np.full(len(A), y.mean()),
        "R1_player_season_mean__RETROSPECTIVE": psm,
        "R2_market_raw": A.M1.values.astype(float)}
L("")
L(f"  {'arm':<5}" + "".join(f"{r:<40}" for r in refs))
r2tab = {}
for k, _ in ARMS:
    v = A[k].values.astype(float)
    ok = np.isfinite(v)
    row = {}
    for rn, rv in refs.items():
        sse = ((v[ok] - y[ok]) ** 2).sum()
        ssr = ((rv[ok] - y[ok]) ** 2).sum()
        row[rn] = float(1 - sse / ssr)
    r2tab[k] = row
    L(f"  {k:<5}" + "".join(f"{row[r]:<40.4f}" for r in refs))
L("")
L("  DECLARED HONEST REFERENCE: R0_grand_mean -- the only one defined on exactly the")
L("  population being scored and not itself a forecast. R1 is RETROSPECTIVE (it uses each")
L("  player's own realised 2024 season mean) and is a yardstick, NOT a forecast anyone could")
L("  have made. The spread across the ladder is reported so the reader can see the movement.")
L(f"  Movement for F1 across the ladder: {min(r2tab['F1'].values()):.4f} .. "
  f"{max(r2tab['F1'].values()):.4f}")

# ============================================================================================
L("")
L("--- Q3. FORECAST ENCOMPASSING (PREREG section 5) ---------------------------------------")
MODELS = {
    "UNI_M1":  ["M1"],
    "UNI_M2":  ["M2"],
    "UNI_F1":  ["F1"],
    "ENC_M2_F1": ["M2", "F1"],          # <<< THE DECISIVE REGRESSION
    "ENC_M1_F1": ["M1", "F1"],          # sensitivity on the market arm
    "ENC_M2_F2": ["M2", "F2"],          # robustness on the model anchor
}
sub = {k: A[["pts"] + v].dropna().index for k, v in MODELS.items()}

fits = {}
for name, cols in MODELS.items():
    idx = sub[name]
    X = np.column_stack([np.ones(len(idx))] + [A.loc[idx, c].values.astype(float) for c in cols])
    yy = A.loc[idx, "pts"].values.astype(float)
    b = ols(X, yy)
    res = yy - X @ b
    fits[name] = {"cols": cols, "coef": {"const": float(b[0]),
                                         **{c: float(b[i + 1]) for i, c in enumerate(cols)}},
                  "n": int(len(idx)),
                  "r2_R0": float(1 - (res ** 2).sum() / ((yy - yy.mean()) ** 2).sum()),
                  "mae": float(np.abs(res).mean()),
                  "rmse": float(np.sqrt((res ** 2).mean()))}
    L(f"  {name:<12} n={fits[name]['n']:<5} " +
      "  ".join(f"{c}={fits[name]['coef'][c]:+.4f}" for c in ["const"] + cols) +
      f"   R2(R0)={fits[name]['r2_R0']:.4f}  in-sample MAE={fits[name]['mae']:.4f}")

L("")
L(f"  collinearity: corr(M2, F1) = {A[['M2', 'F1']].corr().iloc[0, 1]:.4f}   "
  f"corr(M1, M2) = {A[['M1', 'M2']].corr().iloc[0, 1]:.4f}")
L("  ^ high market/model correlation INFLATES the variance of both encompassing")
L("    coefficients. That is exactly why the MDE below has to be read before the null.")

# ============================================================================================
L("")
L("--- 6.1 CLUSTER BOOTSTRAP (PREREG: wider of GAME and PLAYER is the headline) -----------")


def cluster_boot(cols, cluster_col, seed, ndraw):
    idx = A[["pts"] + cols].dropna().index
    D = A.loc[idx]
    yy = D.pts.values.astype(float)
    X = np.column_stack([np.ones(len(D))] + [D[c].values.astype(float) for c in cols])
    codes, uniq = pd.factorize(D[cluster_col])
    order = np.argsort(codes, kind="stable")
    Xs, ys, cs = X[order], yy[order], codes[order]
    starts = np.searchsorted(cs, np.arange(len(uniq)))
    ends = np.searchsorted(cs, np.arange(len(uniq)), side="right")
    members = [np.arange(s, e) for s, e in zip(starts, ends)]
    rng = np.random.default_rng(seed)
    out = np.empty((ndraw, X.shape[1]))
    G = len(uniq)
    for d in range(ndraw):
        pick = rng.integers(0, G, G)
        sel = np.concatenate([members[i] for i in pick])
        try:
            out[d] = ols(Xs[sel], ys[sel])
        except np.linalg.LinAlgError:
            out[d] = np.nan
    return out


BOOT = {}
for name in ["UNI_M2", "UNI_F1", "ENC_M2_F1", "ENC_M1_F1", "ENC_M2_F2"]:
    cols = MODELS[name]
    for cl, tag in (("gid", "GAME"), ("player_id", "PLAYER")):
        BOOT[(name, tag)] = cluster_boot(cols, cl, SEED_BOOT, N_BOOT)

L("")
L("  model        term    coef      BOOT_GAME 95% CI        BOOT_PLAYER 95% CI      "
  "HEADLINE (wider)         excl 0?")
CI = {}
for name in ["UNI_M2", "UNI_F1", "ENC_M2_F1", "ENC_M1_F1", "ENC_M2_F2"]:
    cols = MODELS[name]
    for i, c in enumerate(["const"] + cols):
        j = i
        g = BOOT[(name, "GAME")][:, j]
        p = BOOT[(name, "PLAYER")][:, j]
        gi = (np.nanpercentile(g, 2.5), np.nanpercentile(g, 97.5))
        pi = (np.nanpercentile(p, 2.5), np.nanpercentile(p, 97.5))
        wide = gi if (gi[1] - gi[0]) >= (pi[1] - pi[0]) else pi
        which = "GAME" if wide is gi else "PLAYER"
        exc = not (wide[0] <= 0 <= wide[1])
        CI[(name, c)] = {"coef": fits[name]["coef"][c],
                         "ci_game": [float(gi[0]), float(gi[1])],
                         "ci_player": [float(pi[0]), float(pi[1])],
                         "ci_headline": [float(wide[0]), float(wide[1])],
                         "headline_level": which,
                         "sd_game": float(np.nanstd(g)), "sd_player": float(np.nanstd(p)),
                         "excludes_zero": bool(exc)}
        if c == "const":
            continue
        L(f"  {name:<12} {c:<6} {fits[name]['coef'][c]:+.4f}   "
          f"[{gi[0]:+.4f}, {gi[1]:+.4f}]    [{pi[0]:+.4f}, {pi[1]:+.4f}]    "
          f"[{wide[0]:+.4f}, {wide[1]:+.4f}] ({which})  {exc}")

# ============================================================================================
L("")
L("--- 6.2 CYCLIC WITHIN-PLAYER PERMUTATION NULL (D093) -----------------------------------")
L("  A plain within-player shuffle is ANTICONSERVATIVE for a walk-forward-EWMA regressor:")
L("  it destroys the regressor's autocorrelation while the response keeps its own drift.")
L("  The cyclic shift preserves each player's marginal AND serial structure and destroys")
L("  only the alignment to the response.")


def cyclic_perm_null(cols, shift_col, seed, ndraw):
    idx = A[["pts"] + cols].dropna().index
    D = A.loc[idx].sort_values(["player_id", "game_date"]).copy()
    yy = D.pts.values.astype(float)
    base = {c: D[c].values.astype(float) for c in cols}
    codes, uniq = pd.factorize(D.player_id)
    members = [np.where(codes == i)[0] for i in range(len(uniq))]
    lens = np.array([len(mm) for mm in members])
    rng = np.random.default_rng(seed)
    jshift = cols.index(shift_col)
    out = np.empty(ndraw)
    src = base[shift_col]
    Xcols = [np.ones(len(D))] + [base[c].copy() for c in cols]
    for d in range(ndraw):
        v = src.copy()
        for mi, mm in enumerate(members):
            n = lens[mi]
            if n < 2:
                continue
            k = int(rng.integers(1, n))
            v[mm] = np.roll(src[mm], k)
        Xcols[1 + jshift] = v
        X = np.column_stack(Xcols)
        out[d] = ols(X, yy)[1 + jshift]
    return out


PERM = {}
acf = A.sort_values(["player_id", "game_date"]).groupby("player_id").F1.apply(
    lambda s: s.autocorr(1) if len(s) > 3 else np.nan).mean()
L(f"  mean within-player lag-1 autocorrelation of F1 = {acf:.4f} "
  f"(materiality floor {mb.sk.ACF1_MATERIALITY_FLOOR}) -> cyclic scheme REQUIRED")

for name, term in [("ENC_M2_F1", "F1"), ("ENC_M2_F1", "M2"),
                   ("ENC_M2_F2", "F2"), ("ENC_M1_F1", "F1")]:
    nulls = cyclic_perm_null(MODELS[name], term, SEED_PERM, N_PERM)
    obs = fits[name]["coef"][term]
    p = (1 + (np.abs(nulls) >= abs(obs)).sum()) / (1 + N_PERM)
    PERM[(name, term)] = {"obs": float(obs), "p_two_sided": float(p),
                          "null_mean": float(nulls.mean()), "null_sd": float(nulls.std()),
                          "null_q025": float(np.percentile(nulls, 2.5)),
                          "null_q975": float(np.percentile(nulls, 97.5))}
    L(f"  {name:<12} shift {term:<3} obs={obs:+.4f}  null mean {nulls.mean():+.4f} "
      f"sd {nulls.std():.4f}  null 95% [{np.percentile(nulls, 2.5):+.4f}, "
      f"{np.percentile(nulls, 97.5):+.4f}]  p={p:.4f}")

# ============================================================================================
L("")
L("--- 6.3 MDE, REPORTED BEFORE THE NULL IS INTERPRETED (D136) ----------------------------")
sd_bF = max(CI[("ENC_M2_F1", "F1")]["sd_game"], CI[("ENC_M2_F1", "F1")]["sd_player"])
sd_bM = max(CI[("ENC_M2_F1", "M2")]["sd_game"], CI[("ENC_M2_F1", "M2")]["sd_player"])
MDE_bF = POWER_K * sd_bF
MDE_bM = POWER_K * sd_bM
L(f"  bootstrap SD of bF (wider cluster level) = {sd_bF:.4f}")
L(f"  MDE(bF) at 80% power, alpha=0.05 two-sided = 2.802 * {sd_bF:.4f} = {MDE_bF:.4f}")
L(f"  MDE(bM) = {MDE_bM:.4f}")
sdF = A.F1.std()
L(f"  In interpretable units: a coefficient of {MDE_bF:.4f} on F1 (sd(F1)={sdF:.3f}) moves the")
L(f"  combined forecast by {MDE_bF * sdF:.3f} points per 1sd of F1.")
# MAE gain a coefficient of exactly MDE would buy, holding the market coefficient at its fit
Xe = design(["M2", "F1"])
b_null = ols(np.column_stack([np.ones(len(A)), A.M2.values]), y)
pred_mkt = np.column_stack([np.ones(len(A)), A.M2.values]) @ b_null
resid_mkt = y - pred_mkt
F1c = A.F1.values - A.F1.values.mean()
M2c = A.M2.values - A.M2.values.mean()
F1_orth = F1c - M2c * (M2c @ F1c) / (M2c @ M2c)
mae_at_mde = np.abs(resid_mkt - MDE_bF * F1_orth).mean()
mae_mkt_fit = np.abs(resid_mkt).mean()
L(f"  MAE of the market-only FITTED regression = {mae_mkt_fit:.4f}; adding an F1 coefficient")
L(f"  of exactly MDE(bF) would give MAE {mae_at_mde:.4f}, a gain of "
  f"{mae_mkt_fit - mae_at_mde:+.4f} points.")
UNDERPOWERED = bool(MDE_bF > 0.25)
L(f"  MDE(bF)={MDE_bF:.4f}. PREREG says an underpowered null is NOT a finding.")
L(f"  Smallest edge this screen could have detected on F1: {MDE_bF:.4f} in coefficient units,")
L(f"  worth {mae_mkt_fit - mae_at_mde:.4f} MAE points. UNDERPOWERED FLAG = {UNDERPOWERED}")

# ============================================================================================
L("")
L("--- COMBINATION: what the fitted blend actually buys ------------------------------------")
comb_in = fits["ENC_M2_F1"]["mae"]
L(f"  in-sample MAE: market-only fit {mae_mkt_fit:.4f} -> blend {comb_in:.4f} "
  f"({comb_in - mae_mkt_fit:+.4f})")
L("  POST-HOC (not preregistered, labelled as such): leave-one-GAME-out cross-validated MAE,")
L("  because the blend weights are fitted on the same rows they are scored on.")
gids = A.gid.values
pred_cv = np.empty(len(A))
Xf = design(["M2", "F1"])
Xm = design(["M2"])
pred_cv_m = np.empty(len(A))
for gg in np.unique(gids):
    te = gids == gg
    tr = ~te
    pred_cv[te] = Xf[te] @ ols(Xf[tr], y[tr])
    pred_cv_m[te] = Xm[te] @ ols(Xm[tr], y[tr])
L(f"  LOGO-CV MAE: market-only fit {np.abs(y - pred_cv_m).mean():.4f} -> blend "
  f"{np.abs(y - pred_cv).mean():.4f} "
  f"({np.abs(y - pred_cv).mean() - np.abs(y - pred_cv_m).mean():+.4f})")
L(f"  raw (unfitted) M2 MAE {acc['M2']['mae']:.4f} vs LOGO-CV blend "
  f"{np.abs(y - pred_cv).mean():.4f}")

# ============================================================================================
L("")
L("--- P5: bootstrap CI on the raw line's bias --------------------------------------------")
rng = np.random.default_rng(SEED_BOOT)
codes, uniq = pd.factorize(A.gid)
members = [np.where(codes == i)[0] for i in range(len(uniq))]
bs = np.empty(N_BOOT)
d_bs = np.empty(N_BOOT)
diff_m1m2 = np.abs(A.M1.values - y) - np.abs(A.M2.values - y)
for d in range(N_BOOT):
    sel = np.concatenate([members[i] for i in rng.integers(0, len(uniq), len(uniq))])
    bs[d] = (A.M1.values[sel] - y[sel]).mean()
    d_bs[d] = diff_m1m2[sel].mean()
bias_ci = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
d_ci = (float(np.percentile(d_bs, 2.5)), float(np.percentile(d_bs, 97.5)))
L(f"  mean(M1) - mean(pts) = {(A.M1.values - y).mean():+.4f}  "
  f"BOOT_GAME 95% CI [{bias_ci[0]:+.4f}, {bias_ci[1]:+.4f}]")
L(f"  MAE(M1) - MAE(M2)    = {acc['M1']['mae'] - acc['M2']['mae']:+.4f}  "
  f"BOOT_GAME 95% CI [{d_ci[0]:+.4f}, {d_ci[1]:+.4f}]")

out = {"prereg_sha256": PRE, "n": int(len(A)), "accuracy": acc, "r2_ladder": r2tab,
       "fits": fits,
       "ci": {f"{k[0]}|{k[1]}": v for k, v in CI.items()},
       "perm": {f"{k[0]}|{k[1]}": v for k, v in PERM.items()},
       "mde": {"sd_bF": float(sd_bF), "MDE_bF": float(MDE_bF), "MDE_bM": float(MDE_bM),
               "mae_market_fit": float(mae_mkt_fit), "mae_at_mde": float(mae_at_mde),
               "mae_gain_at_mde": float(mae_mkt_fit - mae_at_mde),
               "underpowered_flag": UNDERPOWERED},
       "combination": {"mae_market_fit_insample": float(mae_mkt_fit),
                       "mae_blend_insample": float(comb_in),
                       "mae_market_fit_logocv__POSTHOC": float(np.abs(y - pred_cv_m).mean()),
                       "mae_blend_logocv__POSTHOC": float(np.abs(y - pred_cv).mean())},
       "p5": {"bias_M1": float((A.M1.values - y).mean()), "ci": list(bias_ci)},
       "p4": {"mae_M1_minus_M2": float(acc["M1"]["mae"] - acc["M2"]["mae"]), "ci": list(d_ci)},
       "corr_M2_F1": float(A[["M2", "F1"]].corr().iloc[0, 1]),
       "acf1_F1_within_player": float(acf)}
json.dump(out, open(os.path.join(mb.OUT, "s02_results.json"), "w"), indent=1)

rows = []
for name in MODELS:
    for c in ["const"] + MODELS[name]:
        k = (name, c)
        rows.append({"model": name, "term": c, "coef": fits[name]["coef"][c],
                     "n": fits[name]["n"],
                     "ci_game_lo": CI.get(k, {}).get("ci_game", [np.nan] * 2)[0],
                     "ci_game_hi": CI.get(k, {}).get("ci_game", [np.nan] * 2)[1],
                     "ci_player_lo": CI.get(k, {}).get("ci_player", [np.nan] * 2)[0],
                     "ci_player_hi": CI.get(k, {}).get("ci_player", [np.nan] * 2)[1],
                     "ci_headline_lo": CI.get(k, {}).get("ci_headline", [np.nan] * 2)[0],
                     "ci_headline_hi": CI.get(k, {}).get("ci_headline", [np.nan] * 2)[1],
                     "headline_cluster": CI.get(k, {}).get("headline_level"),
                     "ci_excludes_zero": CI.get(k, {}).get("excludes_zero"),
                     "perm_p_two_sided": PERM.get(k, {}).get("p_two_sided"),
                     "perm_null_sd": PERM.get(k, {}).get("null_sd"),
                     "r2_R0_grand_mean": fits[name]["r2_R0"]})
pd.DataFrame(rows).to_csv(os.path.join(mb.EXP_DIR, "ENCOMPASSING.csv"), index=False)
L("")
L("  wrote ENCOMPASSING.csv and out/s02_results.json")
L.close()
