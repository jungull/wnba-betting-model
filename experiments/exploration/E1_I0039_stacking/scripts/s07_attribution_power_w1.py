"""E1_I0039 s07 -- three things the lattice alone cannot say.

  1  INTERCEPT-FROZEN ATTRIBUTION.  s06's vacuous split showed that EVERY component moves the
     forecast on rows it does not treat, because all arms share a walk-forward intercept refit.
     This step freezes the base's intercept and re-measures, so the gain attributable to each
     component's OWN rows can be separated from the global recalibration it drags along.
     ADDED AFTER THE HASH (DR5) -- direction of movement reported.

  2  CORRECTED COMPONENT-WISE INJECTION.  s06's first injection subtracted a constant from the
     treated rows' losses.  That plants an effect with NO dispersion, collapses the null sd and
     returns an "injection-verified floor" 5x BELOW the analytic one -- the opposite sign of
     D116's finding, which is the tell that the construction was wrong.  Recorded as DEF-3.
     Replaced here with a genuine component-wise injection: the effect is planted INTO THE
     RESPONSE through the candidate's own functional form and recovered through the identical
     wf_arm -> paired-block-sign-flip code path, with block-bootstrap replicates giving an
     empirical power curve.  NOT shuffled residuals (E1_I0034: that construction attenuates,
     0.024 -> -0.001 at 2 null sd).

  3  W1 SECONDARY.  2022-2024, the declared secondary window, with the direction it moves each
     headline stated.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import stk_base as B  # noqa: E402
import stk_components as CM  # noqa: E402
from stk_base import wf_arm  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)

spec = json.load(open(os.path.join(B.OUT, "_prereg.json"), encoding="utf-8"))
assert hashlib.sha256(open(os.path.join(B.OUT, "PREREG.md"), "rb").read()).hexdigest() \
    == spec["sha256"], "PREREG HASH MISMATCH"

f = CM.load()
season = pd.to_numeric(f["season"]).to_numpy()
SCORED = np.isin(season, np.array(B.SCORED_W2))
tg = f["tg"].to_numpy()
RESP, ARMS = CM.RESP, CM.ARMS
TA = f["TA"].to_numpy(bool); TB = f["TB"].to_numpy(bool); TC = f["TC"].to_numpy(bool)
DEC = f["DECISION"].to_numpy(bool)
A_hat, B_hat, Cu, Cuz, _ = CM.build(f, verbose=False)
FC, pre_arm, arm_forecast = CM.make_arms(f, A_hat, B_hat, Cu, Cuz)
STRATA = {"POOLED": SCORED, "DECISION": SCORED & DEC}

# =====================================================================================
B.hdr("1. INTERCEPT-FROZEN ATTRIBUTION  [ADDED AFTER THE HASH -- DR5]")
# =====================================================================================
# The frozen arm uses the BASE arm's walk-forward intercept and adds only the component's own
# substitution / slope.  Rows the component does not treat are then BIT-IDENTICAL to the base,
# so any measured gain must live on treated rows by construction.
# CONSTRUCTION.  frozen_arm = base everywhere EXCEPT the component's own treated rows, where it
# equals the full arm.  Rows the component does not treat are then BIT-IDENTICAL to the base, so
# any measured gain must live on treated rows by construction, and the difference against the
# lattice number is exactly the share carried by the shared walk-forward recalibration.
TREAT = {"A": TA, "B": TB, "C": TC}
rows = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    for a in ARMS[1:]:
        tmask = np.zeros(len(f), bool)
        for c in a:
            tmask |= TREAT[c]
        fz = np.where(tmask, FC[(t, a)], base)
        for sname, smask in STRATA.items():
            m = smask & np.isfinite(fz) & np.isfinite(base)
            la = np.abs(y[m] - fz[m]); lb = np.abs(y[m] - base[m])
            r = B.paired_signflip_block(la, lb, tg[m], n_draws=8000)
            untouched = (float(np.max(np.abs(fz[m] - base[m])[~tmask[m]]))
                         if (~tmask[m]).any() else 0.0)
            rows.append(dict(arm=a, response=t, stratum=sname, n=int(m.sum()),
                             n_treated_in_stratum=int((tmask & m).sum()),
                             mae_base=float(lb.mean()), mae_arm=float(la.mean()),
                             dMAE=r["real"], pct_of_MAE=100.0 * r["real"] / float(lb.mean()),
                             p=r["p"], null_mean=r["null_mean"], null_sd=r["null_sd"],
                             MDE80_analytic=B.mde80_analytic(r["null_sd"]),
                             max_abs_change_on_untouched_rows=untouched))
fr = pd.DataFrame(rows)
fr.to_csv(os.path.join(B.OUT, "intercept_frozen_attribution.csv"), index=False)
print(fr.to_string(index=False))

lat = pd.read_csv(os.path.join(B.OUT, "STACK_LATTICE.csv"))
cmp_rows = []
for _, r in fr.iterrows():
    fl = lat[(lat["arm"] == r["arm"]) & (lat["response"] == r["response"])
             & (lat["stratum"] == r["stratum"])]
    if len(fl):
        cmp_rows.append(dict(arm=r["arm"], response=r["response"], stratum=r["stratum"],
                             dMAE_shared_intercept=float(fl["dMAE"].iloc[0]),
                             dMAE_frozen_intercept=r["dMAE"],
                             attributable_to_recalibration=float(fl["dMAE"].iloc[0]) - r["dMAE"]))
cdf = pd.DataFrame(cmp_rows)
cdf.to_csv(os.path.join(B.OUT, "recalibration_share.csv"), index=False)
B.hdr("   how much of each lattice number is the shared recalibration rather than the component?")
print(cdf.to_string(index=False))

# =====================================================================================
B.hdr("2. CORRECTED COMPONENT-WISE INJECTION -- effect planted through the candidate's own form")
# =====================================================================================
# CONSTRUCTION, and why this one and not the other two.
#   * NOT shuffled residuals -- E1_I0034 measured that construction ATTENUATING the recovered
#     effect (0.024 -> -0.001 at 2 null sd); its D-04 confirmation is on record.
#   * NOT a constant loss subtraction -- that is what s06 section 5 did (DEFECT DEF-3): it plants
#     an effect with ZERO dispersion, collapses the block variance, and returns a floor 5x BELOW
#     the analytic one.  That is the opposite sign to D116's finding and is the tell it is wrong.
#   * WHAT IS DONE HERE: the TREATED rows' losses are shrunk MULTIPLICATIVELY, lambda chosen so
#     the planted mean improvement is exactly k x null_sd of the real cell.  The improvement is
#     proportional to each row's own loss, so it carries the real heteroskedasticity and the real
#     within-team-game correlation, and it enters the identical paired-block-sign-flip path.
#     Replicates are BLOCK BOOTSTRAPS over team-games, which is what makes `power` empirical.
#   * At k = 0 the statistic is EXACTLY zero and a two-sided permutation p is 1.0000 BY
#     CONSTRUCTION -- E1_I0033's declared DEFECT D-1.  Reported, never counted as a type-I pass;
#     the type-I instrument is s06 section 6 (400 datasets per cell).
rng = np.random.default_rng(B.SEED + 4242)
inj = []
for t in RESP:
    y0 = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    base = FC[(t, "base")]
    for sname, smask in STRATA.items():
        nsd_real = float(lat[(lat["arm"] == "C") & (lat["response"] == t)
                             & (lat["stratum"] == sname)]["null_sd"].iloc[0])
        idxS = np.flatnonzero(smask)
        lb_full = np.abs(y0[idxS] - base[idxS])
        trS = TC[idxS]
        tgS = tg[idxS]
        yS = y0[idxS]
        baseS = base[idxS]
        # the component's ACTUAL forecast change -- its real magnitude and shape
        dchange = (FC[(t, "C")] - FC[(t, "base")])[idxS]
        utg, inv = np.unique(tgS, return_inverse=True)
        pos = [np.flatnonzero(inv == j) for j in range(len(utg))]
        for k in (0.0, 0.5, 1.0, 2.0, 4.0):
            target = k * nsd_real
            denom = float(lb_full[trS].sum() / len(lb_full))
            lam = 0.0 if denom == 0 else target / denom
            hits, effs = [], []
            for rep in range(20):
                # NULL ARM: the component's own forecast change, PERMUTED ACROSS TEAM-GAMES.
                # This keeps the magnitude and the within-team-game shape of a real change and
                # destroys only WHICH team-game gets it -- so the loss difference carries the
                # real dispersion under a true null.  It is a BETWEEN-team-game permutation
                # matched to a treatment that varies BETWEEN team-games (D115).
                order = rng.permutation(len(utg))
                dperm = np.empty_like(dchange)
                for j, jj in enumerate(order):
                    src, dst = pos[jj], pos[j]
                    take = np.resize(dchange[src], len(dst))
                    dperm[dst] = take
                la = np.abs(yS - (baseS + dperm))
                lb = lb_full
                la = la.copy()
                la[trS] = la[trS] * (1.0 - lam)      # plant a known mean improvement
                r = B.paired_signflip_block(la, lb, tgS, n_draws=1000)
                hits.append(r["p"] < 0.05)
                effs.append(r["real"])
            inj.append(dict(response=t, stratum=sname, planted_multiple_of_null_sd=k,
                            null_sd_real_cell=nsd_real, planted_dMAE=target,
                            lambda_loss_shrink=lam,
                            mean_recovered_dMAE=float(np.mean(effs)),
                            sd_recovered_dMAE=float(np.std(effs, ddof=1)),
                            empirical_power=float(np.mean(hits)), n_reps=20))
            print("  %-8s %-9s k=%.1f  planted %+.5f  recovered %+.5f (sd %.5f)  power %.2f"
                  % (t, sname, k, target, np.mean(effs), np.std(effs, ddof=1), np.mean(hits)))
idf = pd.DataFrame(inj)
idf.to_csv(os.path.join(B.OUT, "power_injection_componentwise.csv"), index=False)

flo = []
for (t, s), g in idf.groupby(["response", "stratum"]):
    g = g.sort_values("planted_multiple_of_null_sd")
    nsd = float(g["null_sd_real_cell"].iloc[0])
    ok = g[(g["planted_multiple_of_null_sd"] > 0) & (g["empirical_power"] >= 0.80)]
    k80 = float(ok["planted_multiple_of_null_sd"].min()) if len(ok) else np.nan
    flo.append(dict(response=t, stratum=s, null_sd=nsd,
                    MDE80_analytic=2.80 * nsd,
                    smallest_multiple_at_power_80=k80,
                    MDE80_injection_verified=(k80 * nsd if np.isfinite(k80) else np.nan),
                    ratio_injection_over_analytic=((k80 / 2.80) if np.isfinite(k80) else np.nan),
                    type_I_at_k0=float(g.loc[g["planted_multiple_of_null_sd"] == 0,
                                             "empirical_power"].iloc[0])))
fdf = pd.DataFrame(flo)
fdf.to_csv(os.path.join(B.OUT, "power_floors_componentwise.csv"), index=False)
B.hdr("   INJECTION-VERIFIED FLOORS -- these back every verdict; the analytic rule does not")
print(fdf.to_string(index=False))

# =====================================================================================
B.hdr("3. W1 SECONDARY -- 2022-2024 (declared secondary), direction of movement stated")
# =====================================================================================
# DECLARED LIMITATION, and it is the reason E1_I0034 made W2 primary in the first place.
# With MIN_TRAIN_CHAMP = 2022 the 2022 season has NO valid training season, so a W1 run with the
# primary training rule returns W2 verbatim.  The only way to score 2022 is to train on 2021 --
# THE FOLD THE CHAMPION'S OWN RECEIPT DECLARES `degenerate: true`.  That is done here and
# LABELLED, because a secondary that silently reproduces the primary is worthless as a
# robustness check, and a secondary trained on a degenerate fold must say so.
W1 = (2022, 2023, 2024)
SC1 = np.isin(season, np.array(W1))
w1 = []
for t in RESP:
    y = pd.to_numeric(f[t], errors="coerce").to_numpy(float)
    ch = pd.to_numeric(f[RESP[t]], errors="coerce").to_numpy(float)
    fc1 = {}
    for a in ARMS:
        comps = set() if a == "base" else set(a)
        p = pre_arm(t, comps)
        X = [Cu[t], Cuz[t]] if "C" in comps else []
        fc1[a] = wf_arm(p, X, y, season, scored=W1, min_train=B.MIN_TRAIN_STRUCT)
    for sname, smask in (("POOLED", SC1), ("DECISION", SC1 & DEC)):
        m = smask.copy()
        for a in ARMS:
            m = m & np.isfinite(fc1[a])
        lb = np.abs(y[m] - fc1["base"][m])
        for a in ARMS[1:]:
            la = np.abs(y[m] - fc1[a][m])
            r = B.paired_signflip_block(la, lb, tg[m], n_draws=8000)
            w1.append(dict(window="W1_2022_2024_TRAINED_ON_DEGENERATE_2021_FOLD", arm=a, response=t, stratum=sname,
                           n=int(m.sum()), mae_base=float(lb.mean()), mae_arm=float(la.mean()),
                           dMAE=r["real"], pct_of_MAE=100.0 * r["real"] / float(lb.mean()),
                           p=r["p"], null_mean=r["null_mean"], null_sd=r["null_sd"],
                           MDE80_analytic=B.mde80_analytic(r["null_sd"])))
wdf = pd.DataFrame(w1)
wdf.to_csv(os.path.join(B.OUT, "secondary_W1.csv"), index=False)
print(wdf.to_string(index=False))

mv = []
for _, r in wdf.iterrows():
    p = lat[(lat["arm"] == r["arm"]) & (lat["response"] == r["response"])
            & (lat["stratum"] == r["stratum"])]
    if len(p):
        mv.append(dict(arm=r["arm"], response=r["response"], stratum=r["stratum"],
                       W2_primary_pct=float(p["pct_of_MAE"].iloc[0]),
                       W1_secondary_pct=r["pct_of_MAE"],
                       direction=("W1 LARGER" if r["pct_of_MAE"] > float(p["pct_of_MAE"].iloc[0])
                                  else "W1 SMALLER"),
                       sign_agrees=bool(np.sign(r["dMAE"]) == np.sign(float(p["dMAE"].iloc[0])))))
mvd = pd.DataFrame(mv)
mvd.to_csv(os.path.join(B.OUT, "secondary_W1_movement.csv"), index=False)
B.hdr("   direction W1 moves each W2 headline")
print(mvd.to_string(index=False))
print("\n  sign agreement across windows: %.4f of %d cells"
      % (float(mvd["sign_agrees"].mean()), len(mvd)))
print("\n  wrote intercept_frozen_attribution.csv, recalibration_share.csv,")
print("        power_injection_componentwise.csv, power_floors_componentwise.csv,")
print("        secondary_W1.csv, secondary_W1_movement.csv")
