#!/usr/bin/env python3
"""E1_I0045 s03 -- BUILD AND MEASURE THE ROSTER-CURRENCY RULES.  NOTHING IS ENACTED.

The benchmark is Xa (E1_I0035's per-tier walk-forward recalibration), not doing nothing.  Xa is
reproduced here from its published construction before any currency arm is scored, and its
published headline values must land before the new arms are believed.

D101.  Every arm is scored on the IDENTICAL row sets RS1 (1,392 team-games, response
`master_team.pts`, SST 168710.4073, no weighting, no base) and RS1P (20,084 player rows, responses
`appeared` and `pts`).  A row a currency rule removes KEEPS ITS ROW and takes w = 0 -- exactly the
convention E1_I0035 used for Xc -- so no arm is scored on a row set another arm was not.  The
coverage consequence of removal is charged separately and by name.

EVERY INPUT TO EVERY RULE IS STRICTLY PRE-CUTOFF, derived in s01 from `master_player` through the
contract's own +36h availability bound.  The transaction wire is never read.
"""
from __future__ import annotations
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rc_base as rb  # noqa: E402

pd.set_option("display.width", 250)
F = {}
N_DRAWS = 20000

PF = pd.read_parquet(os.path.join(rb.OUT, "_PF.parquet"))
TF = pd.read_parquet(os.path.join(rb.OUT, "_TF.parquet"))
ALL = pd.read_parquet(os.path.join(rb.OUT, "_pf_all_seasons.parquet"))
rb.assert_partition(ALL, "ALL")
n_tg = len(TF)
SST = rb.sst_of(TF["pts"].to_numpy())
PF = PF.sort_values(["season", "team_id", "game_id", "player_id"],
                    kind="stable").reset_index(drop=True)
for d in (PF, ALL):
    d["is_declared_const"] = (d["pa_component"] == "p_active/declared_constant")
print("  RS1 %d team-games | RS1P %d rows | fit pool %d rows" % (n_tg, len(PF), len(ALL)))

# ALL needs the same S2 reconstruction for the Z arms' training pools.  s02 wrote rec_S2 onto PF
# only, so recompute the rule's DROP MASK on ALL from the same pre-cutoff features.
# (S2 admissibility on the fit pool: team_game_index < 5.  ALL carries no index, so it is derived
#  from the same schedule the contract uses.)
pm = rb.load_player_master()
tgs = (pm[["game_id", "team_id", "season", "game_date"]].drop_duplicates()
       .sort_values(["team_id", "season", "game_date", "game_id"], kind="mergesort"))
tgs["team_game_index"] = tgs.groupby(["team_id", "season"]).cumcount()
ALL = ALL.merge(tgs[["game_id", "team_id", "team_game_index"]], on=["game_id", "team_id"],
                how="left")
s2seen = {}
for t, p, s in zip(pm["team_id"], pm["player_id"], pm["season"]):
    s2seen.setdefault((int(t), int(p)), set()).add(int(s))
ALL["rec_S2"] = [(ti < 5) and any(x < s for x in s2seen.get((int(t), int(p)), ()))
                 for ti, t, p, s in zip(ALL["team_game_index"].fillna(-1).astype(int),
                                        ALL["team_id"], ALL["player_id"], ALL["season"])]
print("  fit-pool rows with rec_S2 = %d" % int(ALL["rec_S2"].sum()))

# =========================================================================================
rb.hdr("0. THE DECISION-STRATUM INTERSECTION, REPORTED FIRST")
print("  Stratum (E1_I0004's registered definition): >=8 prior same-season appearances AND")
print("  trailing-5 mean minutes >=24, both computed strictly pre-cutoff.")
for d in (PF, ALL):
    d["in_decision_stratum"] = ((d["n_prior_app_season"] >= 8)
                                & (d["trail5_min"].fillna(-1) >= 24))
DEC = PF["in_decision_stratum"]
print("\n  RS1P rows in the decision stratum: %d of %d (%.2f%%)"
      % (int(DEC.sum()), len(PF), 100.0 * DEC.mean()))
xt = pd.crosstab(PF["tier_A"], DEC)
print("  tier_A x in_decision_stratum:")
print(xt.to_string())
nb_dec = int((~PF["tier_A"] & DEC).sum())
print("\n  TIER-B rows in the decision stratum: %d  <-- the rows a currency rule could touch"
      % nb_dec)
F["decision_stratum"] = {
    "definition": ">=8 prior same-season appearances AND trailing-5 mean minutes >=24",
    "n_in_stratum": int(DEC.sum()), "n_rows": int(len(PF)), "share": float(DEC.mean()),
    "n_tier_B_in_stratum": nb_dec,
    "n_tier_A_in_stratum": int((PF["tier_A"] & DEC).sum())}

# =========================================================================================
rb.hdr("1. THE CURRENCY RULES  (every input strictly pre-cutoff; no wire, no bios, no roster_asof)")


def drop_masks(d):
    """Return the DROP mask for each rule.  Enumerated, not pattern-matched."""
    tierB = ~d["tier_A"].to_numpy(bool)
    s2 = d["rec_S2"].to_numpy(bool)
    dep = d["departed"].to_numpy(bool)
    stale = (d["seasons_since_club"].to_numpy() >= 2)
    return {
        # R1: she has played for SOMEBODY ELSE since she last played for you, and the only thing
        #     holding her here is prior-season affiliation.
        "R1_departed_S2": tierB & s2 & dep,
        # R2: bound S2 to the immediately preceding season -- she has not played for you since
        #     before last season (99 = never played for you at all).
        "R2_stale_S2": tierB & s2 & stale,
        # R3: either.
        "R3_union_S2": tierB & s2 & (dep | stale),
        # R4: the departure signal applied everywhere, including tier A.  The over-reach variant.
        "R4_departed_all": dep,
    }


RULES = tuple(drop_masks(PF).keys())
DM = drop_masks(PF)
DM_ALL = drop_masks(ALL)
rows = []
for r in RULES:
    m = DM[r]
    rows.append({"rule": r, "n_dropped": int(m.sum()),
                 "share_of_RS1P": float(m.mean()),
                 "n_dropped_tier_A": int((m & PF["tier_A"].to_numpy(bool)).sum()),
                 "n_dropped_tier_B": int((m & ~PF["tier_A"].to_numpy(bool)).sum()),
                 "n_dropped_that_APPEARED": int((m & (PF["appeared"] == 1).to_numpy()).sum()),
                 "appearance_rate_of_dropped": float(PF.loc[m, "appeared"].mean()),
                 "mean_p_active_of_dropped": float(PF.loc[m, "p_active_hat"].mean()),
                 "sum_p_active_removed_per_team_game":
                     float(PF.loc[m, "p_active_hat"].sum() / n_tg),
                 "n_dropped_in_decision_stratum": int((m & DEC.to_numpy()).sum())})
RT = pd.DataFrame(rows)
print(RT.to_string(index=False))
RT.to_csv(os.path.join(rb.OUT, "currency_rules_footprint.csv"), index=False)
F["rule_footprint"] = RT.to_dict("records")

# the recency curve, published so the absence of tau-shopping is auditable
GRID = [7, 14, 30, 60, 90, 120, 180, 200, 250, 300, 365, 400, 500, 700, 900]
cur = []
tb = ~PF["tier_A"].to_numpy(bool)
for tau in GRID:
    m = tb & PF["rec_S2"].to_numpy(bool) & (PF["days_since_club"].fillna(1e9).to_numpy() > tau)
    cur.append({"tau_days": tau, "n_dropped": int(m.sum()),
                "n_dropped_that_appeared": int((m & (PF["appeared"] == 1).to_numpy()).sum()),
                "appearance_rate_of_dropped": float(PF.loc[m, "appeared"].mean()) if m.sum()
                else np.nan,
                "sum_p_removed_per_team_game": float(PF.loc[m, "p_active_hat"].sum() / n_tg)})
CUR = pd.DataFrame(cur)
print("\n  RECENCY CURVE (drop S2 rows whose last appearance for this club is > tau days old):")
print(CUR.to_string(index=False))
CUR.to_csv(os.path.join(rb.OUT, "recency_tau_curve.csv"), index=False)
F["recency_curve"] = CUR.to_dict("records")

# =========================================================================================
rb.hdr("2. Xa REPRODUCED -- the benchmark, per-stratum walk-forward recalibration")
STRAT = lambda d: (np.where(d["tier_A"], "A", "B")
                   + np.where(d["is_declared_const"], "|const", "|fit"))
PF["stratum"] = STRAT(PF)
ALL["stratum"] = STRAT(ALL)
NAMES = tuple(sorted(set(PF["stratum"])))
assert len(NAMES) == 4, NAMES
print("  strata: %s" % (NAMES,))


def recalibrate(keep_mask_all, keep_mask_pf, tag):
    """Per-stratum logistic recalibration fitted on STRICTLY EARLIER seasons.

    `keep_mask_all` restricts the TRAINING pool to rows the rule would also have kept; rows the
    rule drops carry w = 0 and are not recalibrated.  Where a training stratum is empty the row is
    left unrecalibrated and that is printed, exactly as E1_I0035 did.
    """
    w = np.full(len(PF), np.nan)
    fits = []
    for s in rb.SCORED_SEASONS:
        pool = ALL[(ALL["season"] < s) & keep_mask_all]
        for st in NAMES:
            te = ((PF["season"] == s) & (PF["stratum"] == st)).to_numpy() & keep_mask_pf
            if not te.any():
                continue
            tr = pool[pool["stratum"] == st]
            coef = rb.fit_logistic_1d(rb.logit(tr["p_active_hat"]),
                                      tr["appeared"].astype(float)) if len(tr) else None
            if coef is None:
                w[te] = PF.loc[te, "p_active_hat"].to_numpy()
                fits.append({"arm": tag, "season": s, "stratum": st, "n_train": int(len(tr)),
                             "n_test": int(te.sum()), "a": None, "b": None,
                             "action": "UNRECALIBRATED (train pool too thin)"})
            else:
                a, b = coef
                w[te] = rb.sigmoid(a + b * rb.logit(PF.loc[te, "p_active_hat"].to_numpy()))
                fits.append({"arm": tag, "season": s, "stratum": st, "n_train": int(len(tr)),
                             "n_test": int(te.sum()), "a": a, "b": b,
                             "action": "intercept_only" if abs(b) < 1e-9 else "affine_in_logit",
                             "train_base_rate": float(tr["appeared"].mean())})
    w[~keep_mask_pf] = 0.0
    assert np.isfinite(w).all()
    return w, fits


all_true_A = np.ones(len(ALL), bool)
all_true_P = np.ones(len(PF), bool)
w_Xa, fits_Xa = recalibrate(all_true_A, all_true_P, "Xa")
FITS = list(fits_Xa)
print(pd.DataFrame(fits_Xa).to_string(index=False))

# ---- reproduce Xa's published headlines BEFORE the new arms are believed ------------------
PFq = PF.copy()
PFq["w"] = w_Xa
b1 = (PFq["w"] * PFq["pts_hat"]).groupby([PFq["game_id"], PFq["team_id"]]).sum()
TFq = TF.merge(b1.rename("c").reset_index(), on=["game_id", "team_id"], how="left")
xa_mae = rb.mae(TFq["pts"], TFq["c"])
y = PF["appeared"].to_numpy(float)
xa_br = rb.brier(y, np.clip(w_Xa, 0, 1))
mA = PF["tier_A"].to_numpy(bool)
xa_brA = rb.brier(y[mA], np.clip(w_Xa[mA], 0, 1))
xa_auc = rb.auc(y, w_Xa)
chk = [("Xa team MAE", xa_mae, 10.957, 5e-3), ("Xa player Brier (all)", xa_br, 0.0947, 5e-4),
       ("Xa player Brier (tier A)", xa_brA, 0.0933, 5e-4), ("Xa player AUC", xa_auc, 0.9285, 5e-4),
       ("Xa sum p_active/team-game",
        float(PFq.groupby(["game_id", "team_id"])["w"].sum().mean()), 9.561, 5e-3)]
print("\n  %-30s %12s %12s %11s  %s" % ("Xa quantity", "MINE", "PUBLISHED", "abs diff", "verdict"))
ok_all = True
for nm, mine, pub, tol in chk:
    ok = abs(mine - pub) <= tol
    ok_all &= ok
    print("  %-30s %12.6f %12.6f %11.6f  %s"
          % (nm, mine, pub, abs(mine - pub), "CONFIRMED" if ok else "*** DISCREPANCY ***"))
F["Xa_reproduction"] = [{"quantity": n_, "mine": m_, "published": p_, "confirmed": bool(
    abs(m_ - p_) <= t_)} for n_, m_, p_, t_ in chk]
assert ok_all, "Xa did not reproduce -- the benchmark is not the published one; halting"
print("  Xa REPRODUCED.  It is a valid benchmark.")

# =========================================================================================
rb.hdr("3. ASSEMBLE THE ARMS")
W = {"X0": PF["p_active_hat"].to_numpy(float), "Xa": w_Xa}
DROP = {"X0": np.zeros(len(PF), bool), "Xa": np.zeros(len(PF), bool)}
for r in RULES:
    keepP = ~DM[r]
    keepA = ~DM_ALL[r]
    W["Y_" + r] = np.where(keepP, PF["p_active_hat"].to_numpy(float), 0.0)
    DROP["Y_" + r] = DM[r]
    wz, fz = recalibrate(keepA, keepP, "Z_" + r)
    W["Z_" + r] = wz
    DROP["Z_" + r] = DM[r]
    FITS += fz
pd.DataFrame(FITS).to_csv(os.path.join(rb.OUT, "walkforward_recalibration_fits.csv"), index=False)
ARMS = tuple(W.keys())
print("  arms: %s" % (ARMS,))

for a in ARMS:
    PF["w_" + a] = W[a]
    PF["c_" + a] = W[a] * PF["pts_hat"].to_numpy(float)
agg = PF.groupby(["game_id", "team_id"])[["c_" + a for a in ARMS]].sum().reset_index()
sumw = PF.groupby(["game_id", "team_id"])[["w_" + a for a in ARMS]].sum().reset_index()
TF2 = TF.merge(agg, on=["game_id", "team_id"], how="left").merge(
    sumw, on=["game_id", "team_id"], how="left")

# =========================================================================================
rb.hdr("4. TEAM LEVEL  (RS1, n=1392, response master_team.pts, SST %.4f, no weighting, no base)"
       % SST)
WINDOWS = (("FULL 2022-2024", TF2["season"].isin(rb.SCORED_SEASONS).to_numpy()),
           ("CLEAN WINDOW 2023-2024", TF2["season"].isin(rb.CLEAN_WINDOW).to_numpy()))
trows = []
for wl, wm in WINDOWS:
    for a in ARMS:
        yh = TF2.loc[wm, "c_" + a].to_numpy(float); yy = TF2.loc[wm, "pts"].to_numpy(float)
        trows.append({"window": wl, "arm": a, "n": int(wm.sum()), "MAE": rb.mae(yy, yh),
                      "RMSE": rb.rmse(yy, yh), "bias": rb.bias(yy, yh),
                      "R2_common_SST": rb.r2_common(yy, yh, rb.sst_of(yy)),
                      "corr_with_response": float(np.corrcoef(yy, yh)[0, 1]),
                      "mean_sum_w": float(TF2.loc[wm, "w_" + a].mean())})
TEAM = pd.DataFrame(trows)
for wl, _ in WINDOWS:
    m = TEAM["window"] == wl
    TEAM.loc[m, "MAE_vs_X0"] = TEAM.loc[m & (TEAM["arm"] == "X0"), "MAE"].iloc[0] - TEAM.loc[m, "MAE"]
    TEAM.loc[m, "MAE_vs_Xa"] = TEAM.loc[m & (TEAM["arm"] == "Xa"), "MAE"].iloc[0] - TEAM.loc[m, "MAE"]
print(TEAM.to_string(index=False))
TEAM.to_csv(os.path.join(rb.OUT, "team_level.csv"), index=False)
F["team_table"] = TEAM.to_dict("records")

# =========================================================================================
rb.hdr("5. PLAYER LEVEL -- THE PART THAT DECIDES")
y_app = PF["appeared"].to_numpy(float)
y_pts = PF["pts"].to_numpy(float)
pth = PF["pts_hat"].to_numpy(float)
prows = []
for wl, wm in (("FULL 2022-2024", PF["season"].isin(rb.SCORED_SEASONS).to_numpy()),
               ("CLEAN WINDOW 2023-2024", PF["season"].isin(rb.CLEAN_WINDOW).to_numpy())):
    for a in ARMS:
        w = W[a]
        for lbl, m0 in (("RS1P (all)", np.ones(len(PF), bool)),
                        ("RS1P-A (tier A)", mA), ("RS1P-B (tier B)", ~mA),
                        ("DECISION STRATUM", PF["in_decision_stratum"].to_numpy(bool))):
            m = m0 & wm
            if m.sum() < 5:
                continue
            wm_, ym_ = np.clip(w[m], 0, 1), y_app[m]
            cal = rb.fit_logistic_1d(rb.logit(wm_), ym_)
            prows.append({"window": wl, "arm": a, "row_set": lbl, "n": int(m.sum()),
                          "mean_w": float(wm_.mean()), "base_rate": float(ym_.mean()),
                          "brier": rb.brier(ym_, wm_), "logloss": rb.logloss(ym_, wm_),
                          "AUC": rb.auc(ym_, w[m]),
                          "cal_intercept": None if cal is None else cal[0],
                          "cal_slope": None if cal is None else cal[1],
                          "uncond_pts_MAE": rb.mae(y_pts[m], (w * pth)[m]),
                          "uncond_pts_bias": rb.bias(y_pts[m], (w * pth)[m])})
PL = pd.DataFrame(prows)
print(PL.to_string(index=False))
PL.to_csv(os.path.join(rb.OUT, "player_level.csv"), index=False)
F["player_table"] = PL.to_dict("records")

rb.hdr("6. INVARIANCE CHECK -- conditional pts_hat on appeared rows must not move")
appm = (PF["appeared"] == 1).to_numpy()
base_cond = rb.mae(PF.loc[appm, "pts"], PF.loc[appm, "pts_hat"])
print("  conditional pts_hat MAE on appeared rows (n=%d): %.6f" % (int(appm.sum()), base_cond))
print("  no arm here touches pts_hat, so this is identical for every arm BY CONSTRUCTION.")
inv = []
for a in ARMS:
    surv = appm & ~DROP[a]
    inv.append({"arm": a, "n_appeared": int(appm.sum()),
                "n_appeared_with_a_forecast": int(surv.sum()),
                "n_appeared_with_NO_forecast": int((appm & DROP[a]).sum()),
                "share_of_appeared_lost": float((appm & DROP[a]).sum() / appm.sum()),
                "cond_MAE_on_survivors": rb.mae(PF.loc[surv, "pts"], PF.loc[surv, "pts_hat"])})
INV = pd.DataFrame(inv)
print(INV.to_string(index=False))
INV.to_csv(os.path.join(rb.OUT, "coverage_and_invariance.csv"), index=False)
F["coverage"] = INV.to_dict("records")

# =========================================================================================
rb.hdr("7. NULLS -- paired block sign-flip, vs X0 AND vs Xa")
blk_t = (TF2["season"].astype(str) + "_" + TF2["team_id"].astype(str)).to_numpy()
blk_p = (PF["season"].astype(str) + "_" + PF["player_id"].astype(str)).to_numpy()
draws = {}
tt = []
for wl, wm in WINDOWS:
    for ref in ("X0", "Xa"):
        lr = np.abs(TF2["pts"] - TF2["c_" + ref]).to_numpy(float)
        for a in ARMS:
            if a == ref:
                continue
            la = np.abs(TF2["pts"] - TF2["c_" + a]).to_numpy(float)
            r = rb.paired_signflip_block(la[wm], lr[wm], blk_t[wm], N_DRAWS, rb.SEED)
            draws["team_%s_%s_vs_%s" % (wl.split()[0], a, ref)] = r["draws"]
            m = rb.mde80(r["null_sd"])
            tt.append({"window": wl, "level": "TEAM", "arm": a, "reference": ref,
                       "delta_MAE": r["real"], "p": r["p"], "null_mean": r["null_mean"],
                       "null_sd": r["null_sd"], "MDE80": m, "n_blocks": r["n_blocks"],
                       "verdict": rb.verdict(r["p"], r["real"], m)})
TT = pd.DataFrame(tt)
print("  TEAM-LEVEL TESTS (delta_MAE > 0 = the arm beats the reference)")
print(TT.to_string(index=False))

pt = []
for wl, wm in (("FULL 2022-2024", PF["season"].isin(rb.SCORED_SEASONS).to_numpy()),
               ("CLEAN WINDOW 2023-2024", PF["season"].isin(rb.CLEAN_WINDOW).to_numpy())):
    for ref in ("X0", "Xa"):
        br = (np.clip(W[ref], 0, 1) - y_app) ** 2
        for a in ARMS:
            if a == ref:
                continue
            ba = (np.clip(W[a], 0, 1) - y_app) ** 2
            for lbl, m0 in (("RS1P (all)", np.ones(len(PF), bool)),
                            ("RS1P-A (tier A)", mA), ("RS1P-B (tier B)", ~mA)):
                m = m0 & wm
                r = rb.paired_signflip_block(ba[m], br[m], blk_p[m], N_DRAWS, rb.SEED + 7)
                draws["player_%s_%s_vs_%s_%s" % (wl.split()[0], a, ref, lbl.split()[0])] = r["draws"]
                mm = rb.mde80(r["null_sd"])
                pt.append({"window": wl, "level": "PLAYER", "metric": "Brier", "arm": a,
                           "reference": ref, "row_set": lbl, "delta_Brier": r["real"],
                           "p": r["p"], "null_mean": r["null_mean"], "null_sd": r["null_sd"],
                           "MDE80": mm, "n_blocks": r["n_blocks"],
                           "verdict": rb.verdict(r["p"], r["real"], mm)})
PT = pd.DataFrame(pt)
print("\n  PLAYER-LEVEL TESTS (delta_Brier > 0 = the arm LOWERS Brier, i.e. is better)")
print(PT.to_string(index=False))
TT.to_csv(os.path.join(rb.OUT, "team_level_tests.csv"), index=False)
PT.to_csv(os.path.join(rb.OUT, "player_level_tests.csv"), index=False)
F["team_tests"] = tt
F["player_tests"] = pt

# =========================================================================================
rb.hdr("8. POWER, VERIFIED BY INJECTION")
noise_t = (np.abs(TF2["pts"] - TF2["c_Y_R1_departed_S2"]).to_numpy(float)
           - np.abs(TF2["pts"] - TF2["c_Xa"]).to_numpy(float))
print("  TEAM (team-season blocks, n_blocks=%d).  Noise = the REAL Y_R1-vs-Xa per-row loss"
      % len(set(blk_t)))
print("  difference, centred -- a no-effect world with this data's dispersion and blocks.")
for eff in (0.25, 0.5, 1.0, 2.0, 4.0):
    pw = rb.injection_power(noise_t, blk_t, eff, 2000, rb.SEED, n_reps=200)
    print("    planted %.2f MAE -> detection rate %.3f" % (eff, pw))
    F.setdefault("team_injection_power_vs_Xa", {})[str(eff)] = pw
bA = (np.clip(W["Xa"], 0, 1) - y_app) ** 2
bY = (np.clip(W["Z_R3_union_S2"], 0, 1) - y_app) ** 2
noise_p = (bY - bA)[mA]
print("\n  PLAYER, tier A (player-season blocks, n_blocks=%d).  Noise = the REAL Z_R3-vs-Xa"
      % len(set(blk_p[mA])))
print("  per-row Brier difference on tier A, centred.")
for eff in (0.0005, 0.001, 0.0025, 0.005, 0.01):
    pw = rb.injection_power(noise_p, blk_p[mA], eff, 2000, rb.SEED + 7, n_reps=200)
    print("    planted %.4f Brier -> detection rate %.3f" % (eff, pw))
    F.setdefault("player_injection_power_tierA_vs_Xa", {})[str(eff)] = pw

print("\n  TYPE-I CHECK (400 synthetic no-effect datasets, team-season blocks)")
ps = rb.type_I_rate(noise_t, blk_t, 1000, rb.SEED + 99, n_reps=400)
print("    rejection rate at nominal 0.05 = %.4f   p quartiles %.3f / %.3f / %.3f"
      % (float((ps < 0.05).mean()), *np.percentile(ps, [25, 50, 75])))
F["type_I"] = {"rejection_rate": float((ps < 0.05).mean()),
               "quartiles": np.percentile(ps, [25, 50, 75]).tolist()}

# =========================================================================================
rb.hdr("9. FREEZE THE INTERCEPT")
print("  A component can score above every power floor on rows where it does nothing, purely by")
print("  moving a shared level (measured elsewhere in this programme at +0.0287, p 0.00005).")
print("  TEAM: each arm's per-team-game sum of w is rescaled to equal Xa's, so the arm can differ")
print("  from Xa only in SHAPE -- which players carry the weight -- and not in level.")
frz = []
for wl, wm in WINDOWS:
    for a in ARMS:
        sw = TF2["w_" + a].to_numpy(float)
        scale = np.where(sw > 1e-9, TF2["w_Xa"].to_numpy(float) / np.maximum(sw, 1e-9), 1.0)
        cf = TF2["c_" + a].to_numpy(float) * scale
        frz.append({"window": wl, "arm": a, "MAE_unfrozen": rb.mae(TF2.loc[wm, "pts"],
                                                                   TF2.loc[wm, "c_" + a]),
                    "MAE_frozen_to_Xa_level": rb.mae(TF2.loc[wm, "pts"].to_numpy(float), cf[wm]),
                    "mean_sum_w_unfrozen": float(sw[wm].mean()),
                    "mean_sum_w_frozen": float(TF2.loc[wm, "w_Xa"].mean())})
FR = pd.DataFrame(frz)
for wl, _ in WINDOWS:
    m = FR["window"] == wl
    FR.loc[m, "frozen_MAE_vs_Xa"] = (FR.loc[m & (FR["arm"] == "Xa"), "MAE_frozen_to_Xa_level"].iloc[0]
                                     - FR.loc[m, "MAE_frozen_to_Xa_level"])
print(FR.to_string(index=False))

print("\n  PLAYER: every arm receives a single GLOBAL intercept-only recalibration fitted")
print("  walk-forward on strictly earlier seasons, so all arms share a fitted global level and")
print("  any remaining Brier difference is shape, not shared-intercept movement.")
pf_frz = []
for a in ARMS:
    wfr = np.zeros(len(PF))
    for s in rb.SCORED_SEASONS:
        te = (PF["season"] == s).to_numpy()
        # training pool: the SAME arm's weights on strictly earlier seasons.  For X0/Xa the fit
        # pool is ALL; for a currency arm the dropped rows are excluded from the fit (they carry
        # w=0 and no intercept can move them).
        trm = (ALL["season"] < s).to_numpy()
        if a == "X0" or a == "Xa":
            xw = ALL.loc[trm, "p_active_hat"].to_numpy(float)
        else:
            r = a.split("_", 1)[1]
            xw = ALL.loc[trm & ~DM_ALL[r], "p_active_hat"].to_numpy(float)
            trm = trm & ~DM_ALL[r]
        aI = rb.fit_intercept_only(rb.logit(xw), ALL.loc[trm, "appeared"].to_numpy(float))
        z = rb.sigmoid((0.0 if aI is None else aI) + rb.logit(np.clip(W[a][te], rb.EPS, 1 - rb.EPS)))
        wfr[te] = np.where(DROP[a][te], 0.0, z)
    for lbl, m0 in (("RS1P (all)", np.ones(len(PF), bool)), ("RS1P-A (tier A)", mA),
                    ("RS1P-B (tier B)", ~mA)):
        pf_frz.append({"arm": a, "row_set": lbl, "n": int(m0.sum()),
                       "brier_unfrozen": rb.brier(y_app[m0], np.clip(W[a][m0], 0, 1)),
                       "brier_frozen": rb.brier(y_app[m0], wfr[m0]),
                       "mean_w_unfrozen": float(np.clip(W[a][m0], 0, 1).mean()),
                       "mean_w_frozen": float(wfr[m0].mean()),
                       "AUC_unfrozen": rb.auc(y_app[m0], W[a][m0])})
PFR = pd.DataFrame(pf_frz)
print(PFR.to_string(index=False))
FR.to_csv(os.path.join(rb.OUT, "frozen_intercept_team.csv"), index=False)
PFR.to_csv(os.path.join(rb.OUT, "frozen_intercept_player.csv"), index=False)
F["frozen_team"] = FR.to_dict("records")
F["frozen_player"] = PFR.to_dict("records")

# =========================================================================================
rb.hdr("10. PERSIST")
np.savez_compressed(os.path.join(rb.OUT, "nulls", "permutation_draws.npz"), **draws)
np.savez_compressed(os.path.join(rb.OUT, "nulls", "type_I_pvalues.npz"), p=ps)
for r in RULES:
    PF["drop_" + r] = DM[r]
PF.to_parquet(os.path.join(rb.OUT, "_PF_arms.parquet"), index=False)
TF2.to_parquet(os.path.join(rb.OUT, "_TF_arms.parquet"), index=False)
rb.dump(F, "_s03.json")
print("  written.")
print("\nDONE s03")
