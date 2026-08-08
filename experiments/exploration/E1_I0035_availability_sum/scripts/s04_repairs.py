#!/usr/bin/env python3
"""E1_I0035 s04 -- MEASURE the four candidate repairs.  NOTHING IS ENACTED.

Every repair is fitted WALK-FORWARD on strictly earlier seasons.  Where an in-sample version is
also computed it is labelled ORACLE and carries no verdict.  This is the C-1 cheat the
preregistration names: realised appearance rates may JUDGE calibration but may not BUILD a
repair that is then scored on the same rows.

EVERY CELL IS REPORTED AT BOTH LEVELS.  The player level decides.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import av_base as ab  # noqa: E402

pd.set_option("display.width", 250)
F = {}
N_DRAWS = 20000

PF = pd.read_parquet(os.path.join(ab.OUT, "_player_frame.parquet"))
TF = pd.read_parquet(os.path.join(ab.OUT, "_team_frame.parquet"))
ALL = pd.read_parquet(os.path.join(ab.OUT, "_player_frame_all_seasons.parquet"))
ab.assert_partition(ALL, "all-seasons player frame")
n_tg = len(TF)
SST = ab.sst_of(TF["pts"].to_numpy())
print("  RS1 team-games %d   RS1P rows %d   fit pool (all seasons) %d" % (n_tg, len(PF), len(ALL)))

ALL["is_declared_const"] = (ALL["pa_component"] == "p_active/declared_constant")
PF = PF.sort_values(["season", "team_id", "game_id", "player_id"], kind="stable").reset_index(drop=True)

# strata for Xa: explicit, enumerated, asserted
STRATA = (("A", True), ("A", False), ("B", True), ("B", False))


def stratum(df):
    return np.where(df["tier_A"], "A", "B") + np.where(df["is_declared_const"], "|const", "|fit")


PF["stratum"] = stratum(PF)
ALL["stratum"] = stratum(ALL)
STRAT_NAMES = tuple(sorted(set(PF["stratum"])))
print("  strata resolved: %s" % (STRAT_NAMES,))
assert len(STRAT_NAMES) == 4, "expected 4 strata"

EPS = 1e-6


def logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -40, 40)))


def fit_logistic_1d(x, y, n_iter=200, ridge=1e-6):
    """Newton IRLS on [1, x].  Returns (a, b).  Falls back to intercept-only if x is constant."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 30:
        return None
    if np.std(x) < 1e-9:
        m = np.clip(y.mean(), EPS, 1 - EPS)
        return (float(np.log(m / (1 - m))), 0.0)
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(2)
    for _ in range(n_iter):
        p = sigmoid(X @ beta)
        W = np.clip(p * (1 - p), 1e-9, None)
        z = X.T @ (y - p) - ridge * beta
        H = X.T @ (X * W[:, None]) + ridge * np.eye(2)
        step = np.linalg.solve(H, z)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return (float(beta[0]), float(beta[1]))


# =========================================================================================
ab.hdr("1. Xa -- PER-STRATUM RECALIBRATION, WALK-FORWARD")
fits = []
w_xa = np.full(len(PF), np.nan)
for s in ab.SCORED_SEASONS:
    pool = ALL[ALL["season"] < s]
    for st in STRAT_NAMES:
        tr = pool[pool["stratum"] == st]
        te = (PF["season"] == s) & (PF["stratum"] == st)
        n_te = int(te.sum())
        if n_te == 0:
            continue
        coef = fit_logistic_1d(logit(tr["p_active_hat"]), tr["appeared"].astype(float)) \
            if len(tr) else None
        if coef is None:
            w_xa[te.to_numpy()] = PF.loc[te, "p_active_hat"].to_numpy()
            fits.append({"season": s, "stratum": st, "n_train": int(len(tr)), "n_test": n_te,
                         "a": None, "b": None, "action": "UNRECALIBRATED (train pool too thin)"})
        else:
            a, b = coef
            w_xa[te.to_numpy()] = sigmoid(a + b * logit(PF.loc[te, "p_active_hat"].to_numpy()))
            fits.append({"season": s, "stratum": st, "n_train": int(len(tr)), "n_test": n_te,
                         "a": a, "b": b,
                         "action": "intercept_only" if abs(b) < 1e-9 else "affine_in_logit",
                         "train_base_rate": float(tr["appeared"].mean())})
FIT = pd.DataFrame(fits)
print(FIT.to_string(index=False))
FIT.to_csv(os.path.join(ab.OUT, "Xa_walkforward_fits.csv"), index=False)
F["Xa_fits"] = fits
assert np.isfinite(w_xa).all(), "Xa left rows unweighted"

# ORACLE variant: same construction fitted on the scored season itself
w_xaO = np.full(len(PF), np.nan)
for s in ab.SCORED_SEASONS:
    for st in STRAT_NAMES:
        m = ((PF["season"] == s) & (PF["stratum"] == st)).to_numpy()
        if not m.any():
            continue
        coef = fit_logistic_1d(logit(PF.loc[m, "p_active_hat"]), PF.loc[m, "appeared"].astype(float))
        w_xaO[m] = PF.loc[m, "p_active_hat"].to_numpy() if coef is None else \
            sigmoid(coef[0] + coef[1] * logit(PF.loc[m, "p_active_hat"].to_numpy()))

# =========================================================================================
ab.hdr("2. Xb -- ROSTER-SIZE NORMALISATION (strictly prior games)")
# realised roster size per team-game, then a STRICTLY PRIOR same-season expanding mean
tf = TF.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable").copy()
roster = PF.groupby(["game_id", "team_id"])["appeared"].sum().rename("roster_realised")
tf = tf.merge(roster.reset_index(), on=["game_id", "team_id"], how="left")
prior_mean = np.full(len(tf), np.nan)
codes = tf.groupby(["season", "team_id"], sort=False).ngroup().to_numpy()
vals = tf["roster_realised"].to_numpy(float)
run_s, run_n = 0.0, 0
prev = -1
for i in range(len(tf)):
    if codes[i] != prev:
        run_s, run_n, prev = 0.0, 0, codes[i]
    prior_mean[i] = (run_s / run_n) if run_n else np.nan
    run_s += vals[i]; run_n += 1
tf["roster_prior"] = prior_mean
# season's first game has no prior -> the STRICTLY EARLIER seasons' league mean
# RS1 starts at 2022, so a 2022 season-opener has no earlier RS1 team-game to average.  The
# league prior is therefore taken from the FULL partition's earlier seasons (2021 included),
# which is strictly prior information and available at the 2022 cutoff.
roster_all = (ALL.groupby(["season", "game_id", "team_id"])["appeared"].sum()
              .rename("roster_realised").reset_index())
league_prior = {}
for s in ab.SCORED_SEASONS:
    ear = roster_all[roster_all["season"] < s]
    league_prior[s] = float(ear["roster_realised"].mean()) if len(ear) else np.nan
    print("    season %d opener prior from %d earlier team-games (seasons %s)"
          % (s, len(ear), sorted(ear["season"].unique().tolist())))
print("  league prior-season mean roster size used for season openers: %s"
      % {k: round(v, 4) for k, v in league_prior.items()})
tf["roster_target"] = tf["roster_prior"].fillna(tf["season"].map(league_prior))
n_open = int(tf["roster_prior"].isna().sum())
print("  season-opener rows using the league prior: %d" % n_open)
assert tf["roster_target"].notna().all(), "roster target undefined somewhere"
print("  mean roster_target %.4f   vs realised %.4f"
      % (tf["roster_target"].mean(), tf["roster_realised"].mean()))
F["Xb_roster_target"] = {"mean_target": float(tf["roster_target"].mean()),
                         "mean_realised": float(tf["roster_realised"].mean()),
                         "n_season_openers_on_league_prior": n_open,
                         "league_prior_by_season": league_prior}

sump = PF.groupby(["game_id", "team_id"])["p_active_hat"].sum().rename("sum_p")
tf = tf.merge(sump.reset_index(), on=["game_id", "team_id"], how="left")
scal = tf[["game_id", "team_id", "roster_target", "sum_p"]].copy()
scal["scale"] = scal["roster_target"] / scal["sum_p"]
PF = PF.merge(scal[["game_id", "team_id", "scale"]], on=["game_id", "team_id"], how="left")
w_xb = (PF["p_active_hat"] * PF["scale"]).to_numpy()
print("  Xb scale factor: mean %.4f  min %.4f  max %.4f"
      % (np.mean(PF['scale']), np.min(PF['scale']), np.max(PF['scale'])))

# =========================================================================================
ab.hdr("3. Xc -- PRUNE THE UNIVERSE (threshold fitted on strictly earlier seasons)")
GRID = np.round(np.arange(0.00, 0.905, 0.01), 4)
curve = []
for tau in GRID:
    keep = ALL["p_active_hat"] >= tau
    for s in ab.SCORED_SEASONS:
        pool = ALL[(ALL["season"] < s)]
        k = pool["p_active_hat"] >= tau
        curve.append({"season": s, "tau": float(tau),
                      "pool_rows": int(len(pool)), "pool_kept": int(k.sum()),
                      "pool_sum_p": float(pool.loc[k, "p_active_hat"].sum()),
                      "pool_appeared_kept": int(pool.loc[k, "appeared"].sum()),
                      "pool_appeared_total": int(pool["appeared"].sum())})
CV = pd.DataFrame(curve)
# rule, fixed in the prereg: choose tau so the KEPT sum of p_active on the training pool equals
# the training pool's realised number of appearances -- a prior-only target.
taus = {}
for s in ab.SCORED_SEASONS:
    sub = CV[CV["season"] == s].copy()
    if not len(sub) or sub["pool_rows"].iloc[0] == 0:
        taus[s] = 0.0
        continue
    sub["gap"] = np.abs(sub["pool_sum_p"] - sub["pool_appeared_total"])
    taus[s] = float(sub.loc[sub["gap"].idxmin(), "tau"])
print("  tau by season (fitted on strictly earlier seasons only): %s" % taus)
CV.to_csv(os.path.join(ab.OUT, "Xc_tau_curve.csv"), index=False)
F["Xc_tau"] = taus
PF["tau"] = PF["season"].map(taus)
PF["xc_keep"] = PF["p_active_hat"] >= PF["tau"]
w_xc = np.where(PF["xc_keep"], PF["p_active_hat"], 0.0)
n_pruned = int((~PF["xc_keep"]).sum())
n_pruned_appeared = int(((~PF["xc_keep"]) & (PF["appeared"] == 1)).sum())
n_appeared = int((PF["appeared"] == 1).sum())
print("  rows pruned: %d of %d (%.1f%%)" % (n_pruned, len(PF), 100.0 * n_pruned / len(PF)))
print("  APPEARED player-games left with NO forecast: %d of %d (%.2f%%)  <-- the coverage cost"
      % (n_pruned_appeared, n_appeared, 100.0 * n_pruned_appeared / n_appeared))
F["Xc_coverage"] = {"n_rows_pruned": n_pruned, "n_rows": int(len(PF)),
                    "n_appeared_pruned": n_pruned_appeared, "n_appeared": n_appeared,
                    "share_of_appeared_lost": n_pruned_appeared / n_appeared}

# =========================================================================================
ab.hdr("4. ASSEMBLE THE TEAM-LEVEL ARMS")
PF["w_X0"] = PF["p_active_hat"]
PF["w_Xa"] = w_xa
PF["w_XaO"] = w_xaO
PF["w_Xb"] = w_xb
PF["w_Xc"] = w_xc
ARMS = ("X0", "Xa", "XaO", "Xb", "Xc")
for a in ARMS:
    PF["c_" + a] = PF["w_" + a] * PF["pts_hat"]
agg = PF.groupby(["game_id", "team_id"])[["c_" + a for a in ARMS]].sum().reset_index()
TF2 = TF.merge(agg, on=["game_id", "team_id"], how="left")
TF2 = TF2.merge(tf[["game_id", "team_id", "roster_target", "roster_realised", "sum_p"]],
                on=["game_id", "team_id"], how="left")

# Xd -- leave p_active alone, fix the level downstream with a walk-forward affine on B1
TF2 = TF2.sort_values(["season", "team_id", "game_date", "game_id"], kind="stable").reset_index(drop=True)
xd = np.full(len(TF2), np.nan)
aff = []
for s in ab.SCORED_SEASONS:
    tr = TF2[TF2["season"] < s]
    te = (TF2["season"] == s).to_numpy()
    if len(tr) >= 30:
        Xm = np.column_stack([np.ones(len(tr)), tr["c_X0"].to_numpy(float)])
        b = np.linalg.lstsq(Xm, tr["pts"].to_numpy(float), rcond=None)[0]
    else:
        b = np.array([float(TF2.loc[TF2["season"] < s, "pts"].mean()
                            if (TF2["season"] < s).any() else TF2["pts"].mean()), 0.0])
    xd[te] = b[0] + b[1] * TF2.loc[te, "c_X0"].to_numpy(float)
    aff.append({"season": s, "n_train": int(len(tr)), "a": float(b[0]), "b": float(b[1])})
TF2["c_Xd"] = xd
print("  Xd walk-forward affine (a + b*B1):")
print(pd.DataFrame(aff).to_string(index=False))
F["Xd_affine"] = aff
ARMS_T = ("X0", "Xa", "XaO", "Xb", "Xc", "Xd")

rows = []
for a in ARMS_T:
    yh = TF2["c_" + a].to_numpy(float)
    y = TF2["pts"].to_numpy(float)
    rows.append({"arm": a, "n": len(TF2), "MAE": ab.mae(y, yh), "RMSE": ab.rmse(y, yh),
                 "bias": ab.bias(y, yh), "R2_common_SST": ab.r2_common(y, yh, SST),
                 "corr_with_response": float(np.corrcoef(y, yh)[0, 1]),
                 "mean_sum_w": float(PF.groupby(['game_id', 'team_id'])['w_' + a].sum().mean())
                 if a in ARMS else np.nan})
TEAM = pd.DataFrame(rows)
TEAM["MAE_vs_X0"] = TEAM["MAE"].iloc[0] - TEAM["MAE"]
print("\n  TEAM LEVEL  (RS1, n=%d, response master_team.pts, SST %.4f, no weighting, no base)"
      % (len(TF2), SST))
print(TEAM.to_string(index=False))

# =========================================================================================
ab.hdr("5. TEAM-LEVEL NULLS  (paired block sign-flip at TEAM-SEASON, 36 blocks)")
blk_t = (TF2["season"].astype(str) + "_" + TF2["team_id"].astype(str)).to_numpy()
la0 = np.abs(TF2["pts"] - TF2["c_X0"]).to_numpy(float)
tstats = []
draws_store = {}
for a in ARMS_T[1:]:
    lb = np.abs(TF2["pts"] - TF2["c_" + a]).to_numpy(float)
    r = ab.paired_signflip_block(lb, la0, blk_t, N_DRAWS, ab.SEED)
    draws_store["team_" + a] = r["draws"]
    m = ab.mde80(r["null_sd"])
    tstats.append({"cell": "T_" + a, "arm": a, "delta_MAE_vs_X0": r["real"],
                   "p": r["p"], "null_mean": r["null_mean"], "null_sd": r["null_sd"],
                   "MDE80": m, "n_blocks": r["n_blocks"],
                   "verdict": ("ESTABLISHED" if (r["p"] < 0.05 and abs(r["real"]) > m)
                               else "NOT ESTABLISHED (underpowered)" if r["p"] < 0.05
                               else "NOT ESTABLISHED")})
TS = pd.DataFrame(tstats)
print(TS.to_string(index=False))
print("\n  (delta_MAE_vs_X0 > 0 means the repair IMPROVES on the champion as emitted)")

print("\n  POWER VERIFIED BY INJECTION (team-season blocks).")
print("  Noise vector = the REAL Xb-vs-X0 per-row loss difference, centred, so the planted")
print("  world has this data's actual dispersion and block structure.")
noise_t = np.abs(TF2["pts"] - TF2["c_Xb"]).to_numpy(float) - la0
for eff in (0.5, 1.0, 2.0, 4.6, 6.0):
    pw = ab.injection_power(noise_t, blk_t, eff, 2000, ab.SEED, n_reps=200)
    print("    planted %.2f MAE  ->  detection rate %.3f" % (eff, pw))
    F.setdefault("team_injection_power", {})[str(eff)] = pw

# =========================================================================================
ab.hdr("6. PLAYER LEVEL -- THE PART THAT DECIDES")
y_app = PF["appeared"].to_numpy(float)
y_pts = PF["pts"].to_numpy(float)
prow = []
for a in ARMS:
    w = PF["w_" + a].to_numpy(float)
    for lbl, m in (("RS1P (all)", np.ones(len(PF), bool)),
                   ("RS1P-A (tier A)", PF["tier_A"].to_numpy(bool)),
                   ("RS1P-B (tier B)", ~PF["tier_A"].to_numpy(bool))):
        wm, ym = w[m], y_app[m]
        cal = fit_logistic_1d(logit(np.clip(wm, EPS, 1 - EPS)), ym)
        prow.append({"arm": a, "row_set": lbl, "n": int(m.sum()),
                     "mean_w": float(wm.mean()), "base_rate": float(ym.mean()),
                     "brier": ab.brier(ym, np.clip(wm, 0, 1)),
                     "logloss": ab.logloss(ym, np.clip(wm, EPS, 1 - EPS)),
                     "AUC": ab.auc(ym, wm),
                     "cal_intercept": None if cal is None else cal[0],
                     "cal_slope": None if cal is None else cal[1],
                     "uncond_pts_MAE": ab.mae(y_pts[m], (w * PF["pts_hat"].to_numpy())[m]),
                     "uncond_pts_bias": ab.bias(y_pts[m], (w * PF["pts_hat"].to_numpy())[m])})
PL = pd.DataFrame(prow)
print("\n  p_active AS A PROBABILITY FORECAST OF APPEARANCE, and unconditional E[pts]")
print("  (response `appeared` / `pts`; n stated per row; Xd is ABSENT because it changes")
print("   nothing at the player level -- that is its defining property)")
print(PL.to_string(index=False))

ab.hdr("7. INVARIANCE CHECK -- conditional pts_hat on appeared rows must not move")
appm = PF["appeared"] == 1
base_cond = ab.mae(PF.loc[appm, "pts"], PF.loc[appm, "pts_hat"])
print("  conditional pts_hat MAE on appeared rows (n=%d): %.6f" % (int(appm.sum()), base_cond))
print("  every repair Xa/Xb/Xd leaves pts_hat untouched by construction -> identical.")
kept = appm & PF["xc_keep"]
print("  Xc: %d appeared rows survive; conditional MAE on SURVIVORS %.6f"
      % (int(kept.sum()), ab.mae(PF.loc[kept, "pts"], PF.loc[kept, "pts_hat"])))
print("      but %d appeared player-games have NO FORECAST AT ALL under Xc." % n_pruned_appeared)
F["conditional_pts_hat_MAE"] = {"n_appeared": int(appm.sum()), "MAE": base_cond,
                                "invariant_under": ["Xa", "Xb", "Xd"],
                                "Xc_survivors": int(kept.sum()),
                                "Xc_MAE_on_survivors":
                                    ab.mae(PF.loc[kept, "pts"], PF.loc[kept, "pts_hat"])}

ab.hdr("8. PLAYER-LEVEL NULLS  (paired block sign-flip at PLAYER-SEASON)")
blk_p = (PF["season"].astype(str) + "_" + PF["player_id"].astype(str)).to_numpy()
pstats = []
for a in ARMS[1:]:
    for lbl, m in (("RS1P (all)", np.ones(len(PF), bool)),
                   ("RS1P-A (tier A)", PF["tier_A"].to_numpy(bool)),
                   ("RS1P-B (tier B)", ~PF["tier_A"].to_numpy(bool))):
        b0 = (np.clip(PF["w_X0"].to_numpy(float), 0, 1) - y_app) ** 2
        bA = (np.clip(PF["w_" + a].to_numpy(float), 0, 1) - y_app) ** 2
        r = ab.paired_signflip_block(bA[m], b0[m], blk_p[m], N_DRAWS, ab.SEED + 7)
        draws_store["player_brier_%s_%s" % (a, lbl.split()[0])] = r["draws"]
        mm = ab.mde80(r["null_sd"])
        pstats.append({"cell": "P_%s_%s" % (a, lbl.split()[0]), "arm": a, "row_set": lbl,
                       "metric": "Brier", "delta_vs_X0": r["real"], "p": r["p"],
                       "null_mean": r["null_mean"], "null_sd": r["null_sd"], "MDE80": mm,
                       "n_blocks": r["n_blocks"],
                       "verdict": ("ESTABLISHED" if (r["p"] < 0.05 and abs(r["real"]) > mm)
                                   else "NOT ESTABLISHED (underpowered)" if r["p"] < 0.05
                                   else "NOT ESTABLISHED")})
PS = pd.DataFrame(pstats)
print(PS.to_string(index=False))
print("\n  (delta_vs_X0 > 0 means the repair LOWERS Brier, i.e. IMPROVES the player forecast)")

print("\n  POWER VERIFIED BY INJECTION (player-season blocks, Brier scale).")
print("  Noise = the REAL Xb-vs-X0 per-row Brier difference on tier A, centred.")
b0 = (np.clip(PF["w_X0"].to_numpy(float), 0, 1) - y_app) ** 2
bXb = (np.clip(PF["w_Xb"].to_numpy(float), 0, 1) - y_app) ** 2
mA = PF["tier_A"].to_numpy(bool)
noise_p = (bXb - b0)[mA]
for eff in (0.0005, 0.001, 0.003, 0.01):
    pw = ab.injection_power(noise_p, blk_p[mA], eff, 2000, ab.SEED + 7, n_reps=200)
    print("    planted %.4f Brier (tier A) -> detection rate %.3f" % (eff, pw))
    F.setdefault("player_injection_power_tierA", {})[str(eff)] = pw

# =========================================================================================
ab.hdr("9. TYPE-I CHECK (400 synthetic no-effect datasets, team-season blocks)")
ps = ab.type_I_rate(noise_t, blk_t, 1000, ab.SEED + 99, n_reps=400)
print("  rejection rate at nominal 0.05 = %.4f" % float((ps < 0.05).mean()))
print("  p quartiles %.3f / %.3f / %.3f" % tuple(np.percentile(ps, [25, 50, 75])))
F["type_I"] = {"rejection_rate": float((ps < 0.05).mean()),
               "quartiles": np.percentile(ps, [25, 50, 75]).tolist()}

# =========================================================================================
ab.hdr("10. PERSIST")
TEAM.to_csv(os.path.join(ab.OUT, "repairs_team_level.csv"), index=False)
TS.to_csv(os.path.join(ab.OUT, "repairs_team_level_tests.csv"), index=False)
PL.to_csv(os.path.join(ab.OUT, "repairs_player_level.csv"), index=False)
PS.to_csv(os.path.join(ab.OUT, "repairs_player_level_tests.csv"), index=False)
np.savez_compressed(os.path.join(ab.OUT, "nulls", "permutation_draws.npz"), **draws_store)
np.savez_compressed(os.path.join(ab.OUT, "nulls", "type_I_pvalues.npz"), p=ps)
F["team_table"] = TEAM.to_dict("records")
F["team_tests"] = tstats
F["player_table"] = PL.to_dict("records")
F["player_tests"] = pstats
PF.to_parquet(os.path.join(ab.OUT, "_player_frame_repaired.parquet"), index=False)
TF2.to_parquet(os.path.join(ab.OUT, "_team_frame_repaired.parquet"), index=False)
open(os.path.join(ab.OUT, "_s04.json"), "w", encoding="utf-8").write(
    json.dumps(ab.jsonable(F), indent=2))
print("  written.")
print("\nDONE s04")
