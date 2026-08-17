#!/usr/bin/env python3
"""E1_I0045 s05 -- THE ARM THAT DECIDES WHAT THE USER IS ACTUALLY BEING ASKED TO CHANGE.

Z_R3 beats Xa.  But Z_R3 does two things at once: it uses the currency SIGNAL, and it changes the
ROW SET.  Only the second is a contract change, and only the second costs coverage.

Xa+ separates them.  It is Xa with the same currency signal admitted as an extra RECALIBRATION
STRATUM -- eight strata instead of four, (tier A/B) x (declared-constant/fitted) x (current/stale)
-- and it removes NO row, so its coverage cost is exactly zero and every appeared player-game
keeps a forecast.  If Xa+ matches Z_R3, then what the measurement establishes is that the currency
signal is informative, NOT that the universe must be pruned, and the cheaper change is the right
one to put in front of the user.

Also computed here: the injection-verified power floor for the CLEAN WINDOW, which s03's
sign-flip MDE80 left ambiguous, and the decision-stratum comparison.
"""
from __future__ import annotations
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rc_base as rb  # noqa: E402

pd.set_option("display.width", 250)
F = {}
N_DRAWS = 20000

PF = pd.read_parquet(os.path.join(rb.OUT, "_PF_arms.parquet"))
TF2 = pd.read_parquet(os.path.join(rb.OUT, "_TF_arms.parquet"))
ALL = pd.read_parquet(os.path.join(rb.OUT, "_pf_all_seasons.parquet"))
rb.assert_partition(ALL, "ALL")
ALL["is_declared_const"] = (ALL["pa_component"] == "p_active/declared_constant")

# rebuild the fit pool's S2 flag and the R3 drop mask exactly as s03 did
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


def r3_mask(d):
    return ((~d["tier_A"].to_numpy(bool)) & d["rec_S2"].to_numpy(bool)
            & (d["departed"].to_numpy(bool) | (d["seasons_since_club"].to_numpy() >= 2)))


ALL["stale"] = r3_mask(ALL)
PF["stale"] = r3_mask(PF)
assert bool((PF["stale"].to_numpy() == PF["drop_R3_union_S2"].to_numpy()).all())

# =========================================================================================
rb.hdr("1. Xa+  -- THE SAME SIGNAL AS A STRATUM, NOT AS A DELETION")
for d in (PF, ALL):
    d["stratum8"] = (np.where(d["tier_A"], "A", "B")
                     + np.where(d["is_declared_const"], "|const", "|fit")
                     + np.where(d["stale"], "|STALE", "|current"))
NAMES = tuple(sorted(set(PF["stratum8"]) | set(ALL["stratum8"])))
print("  strata (%d): %s" % (len(NAMES), NAMES))

w = np.full(len(PF), np.nan)
fits = []
for s in rb.SCORED_SEASONS:
    pool = ALL[ALL["season"] < s]
    for st in NAMES:
        te = ((PF["season"] == s) & (PF["stratum8"] == st)).to_numpy()
        if not te.any():
            continue
        tr = pool[pool["stratum8"] == st]
        coef = rb.fit_logistic_1d(rb.logit(tr["p_active_hat"]),
                                  tr["appeared"].astype(float)) if len(tr) else None
        if coef is None:
            w[te] = PF.loc[te, "p_active_hat"].to_numpy()
            fits.append({"season": s, "stratum": st, "n_train": int(len(tr)),
                         "n_test": int(te.sum()), "a": None, "b": None,
                         "action": "UNRECALIBRATED (train pool too thin)"})
        else:
            a, b = coef
            w[te] = rb.sigmoid(a + b * rb.logit(PF.loc[te, "p_active_hat"].to_numpy()))
            fits.append({"season": s, "stratum": st, "n_train": int(len(tr)),
                         "n_test": int(te.sum()), "a": a, "b": b,
                         "action": "intercept_only" if abs(b) < 1e-9 else "affine_in_logit",
                         "train_base_rate": float(tr["appeared"].mean())})
assert np.isfinite(w).all()
FT = pd.DataFrame(fits)
print(FT.to_string(index=False))
FT.to_csv(os.path.join(rb.OUT, "Xaplus_walkforward_fits.csv"), index=False)
PF["w_Xa_plus"] = w
PF["c_Xa_plus"] = w * PF["pts_hat"].to_numpy(float)
agg = PF.groupby(["game_id", "team_id"])[["c_Xa_plus", "w_Xa_plus"]].sum().reset_index()
TF2 = TF2.merge(agg, on=["game_id", "team_id"], how="left")

# =========================================================================================
rb.hdr("2. THE HEAD-TO-HEAD: Xa  vs  Xa+ (stratify)  vs  Z_R3 (remove)")
ARMS = ("X0", "Xa", "Xa_plus", "Z_R3_union_S2")
y = PF["appeared"].to_numpy(float)
mA = PF["tier_A"].to_numpy(bool)
pth = PF["pts_hat"].to_numpy(float)
ypts = PF["pts"].to_numpy(float)
appm = (PF["appeared"] == 1).to_numpy()
rows = []
for wl, twm, pwm in (("FULL 2022-2024", TF2["season"].isin(rb.SCORED_SEASONS).to_numpy(),
                      PF["season"].isin(rb.SCORED_SEASONS).to_numpy()),
                     ("CLEAN 2023-2024", TF2["season"].isin(rb.CLEAN_WINDOW).to_numpy(),
                      PF["season"].isin(rb.CLEAN_WINDOW).to_numpy())):
    for a in ARMS:
        ww = PF["w_" + a].to_numpy(float)
        drop = (PF["drop_R3_union_S2"].to_numpy(bool) if a == "Z_R3_union_S2"
                else np.zeros(len(PF), bool))
        rows.append({
            "window": wl, "arm": a,
            "team_MAE": rb.mae(TF2.loc[twm, "pts"], TF2.loc[twm, "c_" + a]),
            "team_bias": rb.bias(TF2.loc[twm, "pts"], TF2.loc[twm, "c_" + a]),
            "team_corr": float(np.corrcoef(TF2.loc[twm, "pts"], TF2.loc[twm, "c_" + a])[0, 1]),
            "sum_w_per_team_game": float(TF2.loc[twm, "w_" + a].mean()),
            "brier_all": rb.brier(y[pwm], np.clip(ww[pwm], 0, 1)),
            "brier_tierA": rb.brier(y[pwm & mA], np.clip(ww[pwm & mA], 0, 1)),
            "brier_tierB": rb.brier(y[pwm & ~mA], np.clip(ww[pwm & ~mA], 0, 1)),
            "AUC_all": rb.auc(y[pwm], ww[pwm]),
            "logloss_all": rb.logloss(y[pwm], np.clip(ww[pwm], rb.EPS, 1 - rb.EPS)),
            "uncond_pts_MAE": rb.mae(ypts[pwm], (ww * pth)[pwm]),
            "appeared_rows_with_NO_forecast": int((appm & drop & pwm).sum())})
H = pd.DataFrame(rows)
print(H.to_string(index=False))
H.to_csv(os.path.join(rb.OUT, "HEAD_TO_HEAD.csv"), index=False)
F["head_to_head"] = H.to_dict("records")

# exposure shape for Xa+
mh = PF["min_hat"].to_numpy(float)
tb = (~PF["tier_A"]).to_numpy(float)
g = PF.groupby(["game_id", "team_id"]).ngroup().to_numpy()
ng = g.max() + 1
real_B = np.bincount(g, weights=tb * PF["minutes"].to_numpy(float), minlength=ng)
ex = []
for a in ARMS:
    num = PF["w_" + a].to_numpy(float) * mh
    den = np.bincount(g, weights=num, minlength=ng)
    alloc = 200.0 * np.bincount(g, weights=num * tb, minlength=ng) / np.maximum(den, 1e-12)
    ex.append({"arm": a, "misallocation_minutes_per_team_game": float((alloc - real_B).mean())})
print("\n  EXPOSURE SHAPE (minutes/team-game handed to tier-B rows in excess of what they play):")
print(pd.DataFrame(ex).to_string(index=False))
F["exposure_head_to_head"] = ex

# =========================================================================================
rb.hdr("3. NULLS -- Xa+ and Z_R3 against Xa, and Z_R3 against Xa+")
blk_t = (TF2["season"].astype(str) + "_" + TF2["team_id"].astype(str)).to_numpy()
blk_p = (PF["season"].astype(str) + "_" + PF["player_id"].astype(str)).to_numpy()
draws = {}
res = []
PAIRS = (("Xa_plus", "Xa"), ("Z_R3_union_S2", "Xa"), ("Z_R3_union_S2", "Xa_plus"))
for wl, twm, pwm in (("FULL 2022-2024", TF2["season"].isin(rb.SCORED_SEASONS).to_numpy(),
                      PF["season"].isin(rb.SCORED_SEASONS).to_numpy()),
                     ("CLEAN 2023-2024", TF2["season"].isin(rb.CLEAN_WINDOW).to_numpy(),
                      PF["season"].isin(rb.CLEAN_WINDOW).to_numpy())):
    for a, ref in PAIRS:
        la = np.abs(TF2["pts"] - TF2["c_" + a]).to_numpy(float)
        lr = np.abs(TF2["pts"] - TF2["c_" + ref]).to_numpy(float)
        r = rb.paired_signflip_block(la[twm], lr[twm], blk_t[twm], N_DRAWS, rb.SEED)
        draws["team_%s_%s_vs_%s" % (wl.split()[0], a, ref)] = r["draws"]
        # per-comparison injection floor, from THIS comparison's own noise
        noise = (la - lr)[twm]
        fl = {e: rb.injection_power(noise, blk_t[twm], e, 2000, rb.SEED, n_reps=200)
              for e in (0.1, 0.2, 0.3, 0.4, 0.6, 0.9)}
        floor = min([e for e, v in fl.items() if v >= 0.80], default=None)
        res.append({"window": wl, "level": "TEAM", "arm": a, "reference": ref,
                    "delta_MAE": r["real"], "p": r["p"], "null_sd": r["null_sd"],
                    "MDE80_signflip": rb.mde80(r["null_sd"]),
                    "injection_floor_80pct": floor, "n_blocks": r["n_blocks"],
                    "power_floor_kind": "INJECTION-VERIFIED",
                    "verdict": ("ESTABLISHED" if (r["p"] < 0.05 and floor is not None
                                                  and abs(r["real"]) > floor)
                                else "NOT ESTABLISHED (below injection floor)"
                                if r["p"] < 0.05 else "NOT ESTABLISHED")})
        for lbl, m0 in (("RS1P (all)", np.ones(len(PF), bool)), ("RS1P-A (tier A)", mA),
                        ("RS1P-B (tier B)", ~mA),
                        ("DECISION STRATUM", PF["in_decision_stratum"].to_numpy(bool))):
            m = m0 & pwm
            ba = (np.clip(PF["w_" + a].to_numpy(float), 0, 1) - y) ** 2
            br = (np.clip(PF["w_" + ref].to_numpy(float), 0, 1) - y) ** 2
            rr = rb.paired_signflip_block(ba[m], br[m], blk_p[m], N_DRAWS, rb.SEED + 7)
            draws["player_%s_%s_vs_%s_%s" % (wl.split()[0], a, ref, lbl.split()[0])] = rr["draws"]
            nz = (ba - br)[m]
            fl = {e: rb.injection_power(nz, blk_p[m], e, 2000, rb.SEED + 7, n_reps=200)
                  for e in (0.00025, 0.0005, 0.001, 0.002)}
            floor = min([e for e, v in fl.items() if v >= 0.80], default=None)
            res.append({"window": wl, "level": "PLAYER " + lbl, "arm": a, "reference": ref,
                        "delta_Brier": rr["real"], "p": rr["p"], "null_sd": rr["null_sd"],
                        "MDE80_signflip": rb.mde80(rr["null_sd"]),
                        "injection_floor_80pct": floor, "n_blocks": rr["n_blocks"],
                        "power_floor_kind": "INJECTION-VERIFIED",
                        "verdict": ("ESTABLISHED" if (rr["p"] < 0.05 and floor is not None
                                                      and abs(rr["real"]) > floor)
                                    else "NOT ESTABLISHED (below injection floor)"
                                    if rr["p"] < 0.05 else "NOT ESTABLISHED")})
R = pd.DataFrame(res)
print(R.to_string(index=False))
R.to_csv(os.path.join(rb.OUT, "HEAD_TO_HEAD_tests.csv"), index=False)
F["head_to_head_tests"] = res

# =========================================================================================
rb.hdr("4. FREEZE THE INTERCEPT, Xa+ AND Z_R3")
fr = []
for wl, twm in (("FULL 2022-2024", TF2["season"].isin(rb.SCORED_SEASONS).to_numpy()),
                ("CLEAN 2023-2024", TF2["season"].isin(rb.CLEAN_WINDOW).to_numpy())):
    for a in ARMS:
        sw = TF2["w_" + a].to_numpy(float)
        sc = np.where(sw > 1e-9, TF2["w_Xa"].to_numpy(float) / np.maximum(sw, 1e-9), 1.0)
        fr.append({"window": wl, "arm": a,
                   "team_MAE_unfrozen": rb.mae(TF2.loc[twm, "pts"], TF2.loc[twm, "c_" + a]),
                   "team_MAE_frozen_to_Xa_level": rb.mae(
                       TF2.loc[twm, "pts"].to_numpy(float),
                       (TF2["c_" + a].to_numpy(float) * sc)[twm])})
FR = pd.DataFrame(fr)
print(FR.to_string(index=False))
FR.to_csv(os.path.join(rb.OUT, "frozen_intercept_head_to_head.csv"), index=False)
F["frozen_head_to_head"] = FR.to_dict("records")

np.savez_compressed(os.path.join(rb.OUT, "nulls", "head_to_head_draws.npz"), **draws)
PF.to_parquet(os.path.join(rb.OUT, "_PF_arms.parquet"), index=False)
TF2.to_parquet(os.path.join(rb.OUT, "_TF_arms.parquet"), index=False)
rb.dump(F, "_s05.json")
print("\nDONE s05")
