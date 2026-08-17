"""s06 -- THE BUDGET DECOMPOSITION (answering E1_I0051's open question) + FINDINGS.

E1_I0051 measured that projecting a minutes forecast onto the 200-minute budget is worth
dR2 +0.020020 pooled, and asked whether the PRE-GAME-AVAILABLE portion of that can be separated
from the oracle portion on the decision stratum.  The projection operator has exactly two
ingredients:

    f_i  ->  f_i * TOTAL_g / SUM_{i in C(g)} f_i

    TOTAL_g   the team's minutes budget.  200 is the RULEBOOK and is KNOWN BEFORE TIP-OFF.
              The realised T_min departs from it only through overtime.
    C(g)      the set summed over: the REALISED APPEARED ROSTER.  NOT known before tip-off.

Four arms, identical base, identical rows, identical SST:
    A0_RAW      no projection                                   FULLY PRE-GAME
    A1_GLOBAL   forecast x a single scalar fitted on strictly earlier seasons   FULLY PRE-GAME
    A2_PROJ200  renormalise to the CONSTANT 200.0 over C(g)      budget free, ROSTER ORACLE
    A3_PROJT    renormalise to the realised T_min over C(g)      budget ORACLE, ROSTER ORACLE
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s06 BUDGET DECOMPOSITION   PREREG sha256 %s" % A.prereg_sha())
d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "cached frame", verbose=True)
Z = np.load(os.path.join(A.SCR, "_base.npz"), allow_pickle=True)
season = d["season"].to_numpy()
dm = A.decision_mask(d)
clean = np.isin(season, A.CLEAN_EVAL_SEASONS)
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg).astype(float)
T_min_tg = np.bincount(tg_code, weights=d["T_min"].to_numpy(float), minlength=n_tg) / counts
y = d["R1_min"].to_numpy(float)
b = Z["R1_min|RAW"]

# ---------------------------------------------------------------- 0. BUDGET TIGHTNESS, own frame
A.hdr("0. IS THE BUDGET REAL?  Cross-checking E1_I0051 on this screen's own frame.")
t = T_min_tg.copy()
near25 = np.abs(t - 25.0 * np.round(t / 25.0)) <= 0.066667
bt = dict(n_team_games=int(len(t)),
          frac_within_0p066667_of_a_multiple_of_25=float(near25.mean()),
          n_not_within=int((~near25).sum()),
          frac_exactly_200=float(np.mean(np.abs(t - 200.0) < 1e-9)),
          frac_within_0p07_of_200=float(np.mean(np.abs(t - 200.0) <= 0.07)),
          mean=float(t.mean()), sd=float(t.std(ddof=1)), min=float(t.min()), max=float(t.max()))
for k, v in bt.items():
    print("  %-42s %s" % (k, v))
print("  NOTE: E1_I0051 reports 95.27%% 'at exactly 200'.  On this frame the summed-from-box total")
print("        is exactly 200.000000 in %.2f%% of team-games and within 0.07 of 200 in %.2f%%."
      % (100 * bt["frac_exactly_200"], 100 * bt["frac_within_0p07_of_200"]))

# ---------------------------------------------------------------- 1. THE FOUR ARMS
A.hdr("1. THE FOUR PROJECTION ARMS -- base only, DECISION stratum, clean window")


def arms_for(cand_vals, arm):
    """Return (y, {armname: forecast}) on the scored rows, walk-forward, all arms sharing one fit."""
    ys, out, idxs = [], {k: [] for k in ["A0_RAW", "A1_GLOBAL", "A2_PROJ200", "A3_PROJT"]}, []
    for s in A.CLEAN_EVAL_SEASONS:
        tr = dm & (season < s)
        te = (season == s)
        sc = dm & te
        Xb_tr = np.column_stack([np.ones(int(tr.sum())), b[tr]])
        Xb_te = np.column_stack([np.ones(int(te.sum())), b[te]])
        bb = A.ols(Xb_tr, y[tr])
        yb_raw = Xb_te @ bb
        dbar = float(cand_vals[tr].mean())
        d_tr, d_te = cand_vals[tr] - dbar, cand_vals[te] - dbar
        if arm == "FROZEN":
            r_tr = y[tr] - Xb_tr @ bb
            dd = float(d_tr @ d_tr)
            g = float(d_tr @ r_tr) / dd if dd > 0 else 0.0
            f_raw = yb_raw + g * d_te
        elif arm == "UNFROZEN":
            ba = A.ols(np.column_stack([Xb_tr, d_tr]), y[tr])
            f_raw = np.column_stack([Xb_te, d_te]) @ ba
        else:                                    # BASE only
            f_raw = yb_raw
        tgc = tg_code[te]
        # A1: ONE scalar from the TRAINING seasons only -- no eval information of any kind.
        # DEFECT D-03, fixed: the first version summed the forecast over DECISION training rows
        # only (about 4 of a 9.4-player roster), so the scalar was ~1.67 and the arm scored
        # R2 = -10.34.  The team-game sum must run over the FULL appeared roster.
        tr_all = (season < s)
        f_tr_all = np.column_stack([np.ones(int(tr_all.sum())), b[tr_all]]) @ bb
        tg_tr = tg_code[tr_all]
        sums_tr = np.bincount(tg_tr, weights=f_tr_all, minlength=n_tg)
        used = np.unique(tg_tr)
        c_scalar = A.REGULATION_TEAM_MINUTES * len(used) / float(sums_tr[used].sum())
        keep = sc[te]
        ys.append(y[te][keep])
        out["A0_RAW"].append(f_raw[keep])
        out["A1_GLOBAL"].append((c_scalar * f_raw)[keep])
        out["A2_PROJ200"].append(A.project_to_total(
            f_raw, tgc, n_tg, counts, np.full(n_tg, A.REGULATION_TEAM_MINUTES))[keep])
        out["A3_PROJT"].append(A.project_to_total(f_raw, tgc, n_tg, counts, T_min_tg)[keep])
        idxs.append(np.flatnonzero(sc))
    return (np.concatenate(ys), {k: np.concatenate(v) for k, v in out.items()},
            np.concatenate(idxs))


zero = np.zeros(len(d))
yy, F, idx = arms_for(zero, "BASE")
blocks = d.loc[idx, "tg"].to_numpy()
rows = []
for k, f in F.items():
    rows.append(dict(what="BASE_ONLY", arm=k, n=len(yy), r2=A.r2_of_forecast(yy, f),
                     rms_team_sum_error=float(np.sqrt(np.mean(
                         (np.bincount(tg_code[idx], weights=f, minlength=n_tg)[np.unique(tg_code[idx])]
                          - 0) ** 2)) * 0 + np.nan)))
    print("  BASE  %-11s R2 %+.6f" % (k, rows[-1]["r2"]))

CONTRASTS = [("A1_GLOBAL", "A0_RAW", "FULLY PRE-GAME: one scalar, no game-specific information"),
             ("A2_PROJ200", "A0_RAW", "budget free (200 = rulebook) but ROSTER IS ORACLE"),
             ("A2_PROJ200", "A1_GLOBAL", "the team-game-specific part, over and above a scalar"),
             ("A3_PROJT", "A2_PROJ200", "ORACLE TOTAL over the rulebook 200 -- the overtime part"),
             ("A3_PROJT", "A0_RAW", "the whole projection gain, both oracles included")]
dec = []
for a, bb_, why in CONTRASTS:
    r = A.paired_signflip(yy, F[a], F[bb_], blocks, n_draws=A.N_DRAWS, seed=A.SEED)
    dec.append(dict(what="BASE_ONLY", arm_a=a, arm_b=bb_, meaning=why, n=len(yy),
                    n_blocks=r["n_blocks"], r2_a=A.r2_of_forecast(yy, F[a]),
                    r2_b=A.r2_of_forecast(yy, F[bb_]), dR2=r["real"], null_sd=r["null_sd"],
                    z=r["z"], p=r["p"], MDE80_analytic=2.80 * r["null_sd"]))
    A.save_null("BUDGET__R1_min__DECISION_CLEAN__%s_vs_%s" % (a, bb_),
                dict(label="BUDGET %s-%s" % (a, bb_), real=r["real"], draws=r["draws"],
                     null_mean=r["null_mean"], null_sd=r["null_sd"], n_groups=r["n_blocks"],
                     n_blocks=r["n_blocks"], n_draws=A.N_DRAWS))
    print("  %-11s - %-11s  dR2 %+10.6f  z %+7.2f  p %.4f  MDE80 %.6f   [%s]"
          % (a, bb_, r["real"], r["z"], r["p"], 2.80 * r["null_sd"], why))

# ------------------------------- 1b. IS THE PROJECTION GAIN THE BUDGET, OR IS IT THE OVERTIME?
A.hdr("1b. THE SAME CONTRASTS ON REGULATION-ONLY TEAM-GAMES (T_min within 0.07 of 200)")
reg_tg = np.abs(T_min_tg - 200.0) <= 0.07
keep_reg = reg_tg[tg_code[idx]]
print("  scored rows in regulation team-games: %d of %d (%.2f%%);  team-game blocks %d of %d"
      % (keep_reg.sum(), len(keep_reg), 100 * keep_reg.mean(),
         pd.Series(blocks[keep_reg]).nunique(), pd.Series(blocks).nunique()))
for a, bb_, why in CONTRASTS:
    r = A.paired_signflip(yy[keep_reg], F[a][keep_reg], F[bb_][keep_reg], blocks[keep_reg],
                          n_draws=A.N_DRAWS, seed=A.SEED)
    dec.append(dict(what="BASE_ONLY_REGULATION_GAMES_ONLY", arm_a=a, arm_b=bb_, meaning=why,
                    n=int(keep_reg.sum()), n_blocks=r["n_blocks"],
                    r2_a=A.r2_of_forecast(yy[keep_reg], F[a][keep_reg]),
                    r2_b=A.r2_of_forecast(yy[keep_reg], F[bb_][keep_reg]),
                    dR2=r["real"], null_sd=r["null_sd"], z=r["z"], p=r["p"],
                    MDE80_analytic=2.80 * r["null_sd"]))
    print("  %-11s - %-11s  dR2 %+10.6f  z %+7.2f  p %.4f   [%s]"
          % (a, bb_, r["real"], r["z"], r["p"], why))

# ---------------------------------------------------------------- 2. THE CANDIDATE IN EVERY ARM
A.hdr("2. C1_player_rest IN EVERY PROJECTION ARM, FROZEN AND UNFROZEN")
x1 = d["C1_player_rest"].to_numpy(float)
for arm in ["FROZEN", "UNFROZEN"]:
    yy2, Fa, idx2 = arms_for(x1, arm)
    _, Fb, _ = arms_for(zero, "BASE")
    for k in Fa:
        r = A.paired_signflip(yy2, Fa[k], Fb[k], blocks, n_draws=A.N_DRAWS, seed=A.SEED)
        dec.append(dict(what="C1_player_rest", arm_a=k + "|" + arm, arm_b=k + "|BASE",
                        meaning="candidate over base within the same projection arm",
                        n=len(yy2), n_blocks=r["n_blocks"], r2_a=A.r2_of_forecast(yy2, Fa[k]),
                        r2_b=A.r2_of_forecast(yy2, Fb[k]), dR2=r["real"], null_sd=r["null_sd"],
                        z=r["z"], p=r["p"], MDE80_analytic=2.80 * r["null_sd"]))
        print("  %-8s %-11s  base R2 %+.6f -> %+.6f   dR2 %+10.6f  z %+7.2f  p %.4f"
              % (arm, k, dec[-1]["r2_b"], dec[-1]["r2_a"], r["real"], r["z"], r["p"]))

D = pd.DataFrame(dec)
D.to_csv(os.path.join(A.OUT, "BUDGET_DECOMPOSITION.csv"), index=False)
pd.DataFrame([bt]).to_csv(os.path.join(A.OUT, "BUDGET_TIGHTNESS.csv"), index=False)

# ---------------------------------------------------------------- 3. TRANSLATION INTO MINUTES
A.hdr("3. WHAT THE SURVIVING EFFECT IS, IN MINUTES")
P = pd.read_csv(os.path.join(A.OUT, "PRIMARY_CELLS.csv"))
row = P[(P.grid == "PRIMARY") & (P.arm == "FROZEN") & (P.candidate == "C1_player_rest")].iloc[0]
yy3, Fa3, idx3 = arms_for(x1, "FROZEN")
_, Fb3, _ = arms_for(zero, "BASE")
mv = Fa3["A0_RAW"] - Fb3["A0_RAW"]
tr_ = dict(rms_forecast_movement_minutes=float(np.sqrt(np.mean(mv ** 2))),
           max_abs_forecast_movement_minutes=float(np.max(np.abs(mv))),
           response_sd_minutes=float(np.std(yy3, ddof=1)),
           base_mae_minutes=float(np.mean(np.abs(yy3 - Fb3["A0_RAW"]))),
           arm_mae_minutes=float(np.mean(np.abs(yy3 - Fa3["A0_RAW"]))),
           beta_minutes_per_rest_day=float(row["beta"]))
tr_["dMAE_minutes"] = tr_["base_mae_minutes"] - tr_["arm_mae_minutes"]
tr_["pct_of_MAE"] = 100.0 * tr_["dMAE_minutes"] / tr_["base_mae_minutes"]
for k, v in tr_.items():
    print("  %-38s %+.6f" % (k, v))
pd.DataFrame([tr_]).to_csv(os.path.join(A.OUT, "TRANSLATION.csv"), index=False)

A.dump("s06", dict(prereg_sha=A.prereg_sha(), budget_tightness=bt, translation=tr_,
                   decomposition=dec))
A.hdr("s06 done")
