"""s05 -- CONTROLS.  Injection power and floors, non-circular type-I, the null-centre check, the
blind-null demonstration, the no-op placebo, the response placebo, and the leakage probe.

INJECTION IS COMPONENT-WISE AND THE WHOLE PATH IS RERUN.  For replicate r a SYNTHETIC candidate is
drawn from the real candidate's own matched null -- so it carries the real column's marginal
distribution and its level structure and has ZERO true relation to the response -- theta * x_r is
planted into the REAL MINUTES, the player's strictly-prior EWMA is REBUILT from the injected
minutes, the allocator and the base coefficients are refitted, and the cell is retested against a
fresh null.  theta = 0 is the type-I arm.  Residuals are never shuffled.
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s05 CONTROLS   PREREG sha256 %s" % A.prereg_sha())
d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "cached frame", verbose=True)
Z = np.load(os.path.join(A.SCR, "_base.npz"), allow_pickle=True)
season = d["season"].to_numpy()
dm = A.decision_mask(d)
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg).astype(float)
T_min_tg = np.bincount(tg_code, weights=d["T_min"].to_numpy(float), minlength=n_tg) / counts
y_real = d["R1_min"].to_numpy(float)
n_hat = d["n_hat"].to_numpy(float)
n_prior = d["n_prior"].to_numpy(float)
SW_TG = A.WithinTeamGameSwap(d)
SW_BLK = A.WithinDateTeamGameSwap(d)
SW_WP = A.WithinPlayerCyclic(d)

H_SEL, K_SEL = 3, 1.0          # selected in s02 on strictly earlier seasons, for both eval folds
PS = d["ps_code"].to_numpy()
ORD = np.lexsort((d["game_id"].to_numpy(), d["game_date"].to_numpy(), PS))
INV = np.empty_like(ORD)
INV[ORD] = np.arange(len(ORD))
PS_ORD = PS[ORD]
NEWGRP = np.r_[True, PS_ORD[1:] != PS_ORD[:-1]]


def rebuild_base(minutes):
    """Rebuild the strictly-prior EWMA and the tuned allocator from a (possibly injected) minutes
    column.  Same construction as mn_base.build_frame + allocator_raw, at the selected (h, k)."""
    s = pd.Series(minutes[ORD])
    g = pd.Series(PS_ORD).values
    pr = s.groupby(g).transform(
        lambda v: v.shift(1).ewm(halflife=H_SEL, adjust=True, min_periods=1).mean()).to_numpy()
    pr = pr[INV]
    tgt = A.REGULATION_TEAM_MINUTES / n_hat
    w = K_SEL / (K_SEL + n_prior)
    pr = np.where(np.isfinite(pr), pr, tgt)
    return (1.0 - w) * pr + w * tgt


b_check = rebuild_base(y_real)
b_s02 = Z["R1_min|RAW"]
mask23 = np.isin(season, A.CLEAN_EVAL_SEASONS)
print("  rebuild_base vs s02 base on eval rows: max|d| = %.3e"
      % float(np.max(np.abs(b_check[mask23] - b_s02[mask23]))))


def cell_with(bvec, cand_vals, arm="FROZEN", y=None):
    return A.Cell(d, y_real if y is None else y, bvec, "INJ", cand_vals, dm, dm,
                  A.CLEAN_EVAL_SEASONS, arm, "RAW", proj_totals=T_min_tg)


# =============================================================== 1. COMPONENT-WISE INJECTION
A.hdr("1. COMPONENT-WISE INJECTION -- whole path rerun.  theta = 0 is the type-I arm.")
THETAS = [0.0, 0.2, 0.35, 0.5, 0.7, 1.0]       # minutes per sd of the planted component
NREP = 40
NDRAW_INJ = 200
inj_rows = []
NC = {}
for cname, sw, fam in [("C1_player_rest", SW_TG, "WITHIN_TG"),
                       ("C7_sched_density", SW_BLK, "TG_CONSTANT"),
                       ("G01_noise", SW_TG, "WITHIN_TG_CONTROL")]:
    x0 = d[cname].to_numpy(float)
    t0 = time.time()
    for th in THETAS:
        det, zs, dr2s = 0, [], []
        for r in range(NREP):
            rng = np.random.default_rng(90000 + 137 * r)
            xr = sw.draw(x0, rng)
            xs = (xr - xr.mean()) / (xr.std(ddof=1) if xr.std(ddof=1) > 0 else 1.0)
            y_inj = y_real + th * xs
            b_inj = rebuild_base(y_inj)
            cell = cell_with(b_inj, xr, "FROZEN", y_inj)
            real = float(cell.dr2())
            draws = np.empty(NDRAW_INJ, float)
            for i in range(NDRAW_INJ):
                draws[i] = cell.dr2(xr[sw.draw_index(np.random.default_rng(A.SEED + i))])
            mu, sd = float(draws.mean()), float(draws.std(ddof=1))
            p = float((1.0 + int((draws >= real).sum())) / (len(draws) + 1.0))
            det += int(p < 0.05)
            zs.append((real - mu) / sd if sd > 0 else np.nan)
            dr2s.append(real)
            if th == 0.0:
                NC.setdefault(cname, []).append((real, mu))
        inj_rows.append(dict(candidate=cname, family=fam, theta_minutes_per_sd=th,
                             n_rep=NREP, n_draws=NDRAW_INJ,
                             power_at_alpha_05=det / NREP,
                             mean_recovered_dR2=float(np.mean(dr2s)),
                             sd_recovered_dR2=float(np.std(dr2s, ddof=1)),
                             mean_z=float(np.nanmean(zs)), sd_z=float(np.nanstd(zs, ddof=1))))
        print("  %-18s theta %.2f  power %.3f  mean recovered dR2 %+10.6f  mean z %+7.2f  "
              "sd(z) %.3f" % (cname, th, det / NREP, inj_rows[-1]["mean_recovered_dR2"],
                              inj_rows[-1]["mean_z"], inj_rows[-1]["sd_z"]))
    print("    (%.1f s)" % (time.time() - t0))
INJ = pd.DataFrame(inj_rows)
INJ.to_csv(os.path.join(A.OUT, "INJECTION_POWER.csv"), index=False)


def mde80(sub):
    """Injection-verified 80 %-power floor, in RECOVERED dR2 units, by linear interpolation."""
    s = sub.sort_values("theta_minutes_per_sd")
    pw = s["power_at_alpha_05"].to_numpy()
    rc = s["mean_recovered_dR2"].to_numpy()
    for i in range(1, len(pw)):
        if pw[i - 1] < 0.80 <= pw[i]:
            f = (0.80 - pw[i - 1]) / (pw[i] - pw[i - 1])
            return float(rc[i - 1] + f * (rc[i] - rc[i - 1]))
    return float("nan") if pw[-1] < 0.80 else float(rc[0])


FLOORS = {c: mde80(INJ[INJ["candidate"] == c]) for c in INJ["candidate"].unique()}
print("\n  INJECTION-VERIFIED 80%%-POWER FLOORS (recovered dR2 units): %s" % FLOORS)

# =============================================================== 2. THE NULL-CENTRE CHECK
A.hdr("2. NULL-CENTRE CHECK -- a valid null sits at ~ +1; E1_I0043 separated valid/blind at "
      "+1.030 vs -0.040")
nc_rows = []
for cname, sw in [("C1_player_rest", SW_TG), ("C7_sched_density", SW_BLK), ("G01_noise", SW_TG)]:
    pairs = NC[cname]
    inj_centre = float(np.mean([a for a, _ in pairs]))     # statistic under a KNOWN-null candidate
    null_centre = float(np.mean([m for _, m in pairs]))    # where the null says it should sit
    nc_rows.append(dict(candidate=cname, null="matched",
                        injection_centre_theta0=inj_centre, null_centre=null_centre,
                        null_centre_ratio=null_centre / inj_centre if inj_centre != 0 else np.nan))
    print("  %-18s matched null: injection centre %+.3e  null centre %+.3e  RATIO %+8.4f"
          % (cname, inj_centre, null_centre, nc_rows[-1]["null_centre_ratio"]))
# the blind arm, same construction
x0 = d["C1_player_rest"].to_numpy(float)
bl_real, bl_mu = [], []
for r in range(NREP):
    rng = np.random.default_rng(90000 + 137 * r)
    xr = SW_TG.draw(x0, rng)
    cell = cell_with(b_check, xr, "FROZEN")
    real = float(cell.dr2())
    draws = np.array([cell.dr2(xr[SW_WP.draw_index(np.random.default_rng(A.SEED + i))])
                      for i in range(NDRAW_INJ)])
    bl_real.append(real)
    bl_mu.append(float(draws.mean()))
nc_rows.append(dict(candidate="C1_player_rest", null="N_WITHIN_PLAYER_BLIND",
                    injection_centre_theta0=float(np.mean(bl_real)),
                    null_centre=float(np.mean(bl_mu)),
                    null_centre_ratio=float(np.mean(bl_mu)) / float(np.mean(bl_real))))
print("  %-18s BLIND null:   injection centre %+.3e  null centre %+.3e  RATIO %+8.4f"
      % ("C1_player_rest", nc_rows[-1]["injection_centre_theta0"], nc_rows[-1]["null_centre"],
         nc_rows[-1]["null_centre_ratio"]))
pd.DataFrame(nc_rows).to_csv(os.path.join(A.OUT, "NULL_CENTRE.csv"), index=False)

# =============================================================== 3. BLIND-NULL DEMONSTRATION
A.hdr("3. BLIND NULL ON THIS SCREEN'S OWN LIVE CELL -- demonstrated, not cited")
bl_rows = []
for cname in ["C1_player_rest", "C1_player_rest__B", "C6_team_rest"]:
    if cname.endswith("__B"):
        base_c = cname[:-3]
        x = d[base_c].to_numpy(float)
        xv = (np.bincount(tg_code, weights=x, minlength=n_tg) / counts)[tg_code]
    else:
        xv = d[cname].to_numpy(float)
    correct_sw = SW_BLK if (cname in A.TG_CONSTANT_CANDIDATES or cname.endswith("__B")) else SW_TG
    correct_nm = "N_TGBLOCK" if correct_sw is SW_BLK else "N_TGSWAP"
    for arm in ["FROZEN"]:
        cell = cell_with(b_check, xv, arm)
        for nm, sw in [(correct_nm + "_CORRECT", correct_sw), ("N_WITHIN_PLAYER_BLIND", SW_WP)]:
            res = A.run_null_family({cname: cell}, sw, 1000, A.SEED, "BLIND|" + nm)[cname]
            bl_rows.append(dict(candidate=cname, arm=arm, null=nm, observed=res["real"],
                                null_mean=res["null_mean"], null_sd=res["null_sd"], z=res["z"],
                                p=res["p"], n_blocks=res["n_blocks"], n_draws=1000))
            A.save_null("BLINDDEMO__R1_min__RAW__%s__%s__%s" % (arm, cname, nm), res,
                        dict(candidate=np.array([cname]), null=np.array([nm])))
            print("  %-20s %-8s %-24s obs %+10.6f  null mean %+10.6f  z %+7.2f  p %.4f"
                  % (cname, arm, nm, res["real"], res["null_mean"], res["z"], res["p"]))
pd.DataFrame(bl_rows).to_csv(os.path.join(A.OUT, "BLIND_NULL_DEMO.csv"), index=False)

# =============================================================== 4. NON-CIRCULAR TYPE-I
A.hdr("4. NON-CIRCULAR TYPE-I -- 100 synthetic candidates carrying a REAL player's whole rest "
      "series but belonging to a player on another team-season")
ps_codes = d["ps_code"].to_numpy()
groups = {}
for i, p in enumerate(ps_codes):
    groups.setdefault(int(p), []).append(i)
gids = [g for g in groups.values() if len(g) >= 5]
x_rest = d["C1_player_rest"].to_numpy(float)
rng = np.random.default_rng(4242)
zs, ps_ = [], []
for k in range(100):
    synth = np.empty(len(d))
    donors = rng.permutation(len(gids))
    for a, idx in enumerate(gids):
        src = gids[donors[a]]
        v = x_rest[src]
        pos = (np.round(np.arange(len(idx)) / max(len(idx) - 1, 1) * max(len(v) - 1, 0))
               .astype(int) if len(idx) > 1 else np.zeros(len(idx), int))
        synth[idx] = v[pos]
    bad = np.setdiff1d(np.arange(len(d)), np.concatenate([np.asarray(g) for g in gids]))
    synth[bad] = float(x_rest.mean())
    cell = cell_with(b_check, synth, "FROZEN")
    res = A.run_null_family({"S": cell}, SW_TG, 200, A.SEED, "TYPEI")["S"]
    zs.append(res["z"])
    ps_.append(res["p"])
zs = np.asarray(zs)
ps_ = np.asarray(ps_)
ti = dict(n_synthetic=100, rejection_at_05=float(np.mean(ps_ < 0.05)), mean_z=float(np.mean(zs)),
          sd_z=float(np.std(zs, ddof=1)), max_z=float(np.max(zs)), min_z=float(np.min(zs)))
print("  rejection %.3f (nominal 0.050)   mean z %+.3f   sd(z) %.3f   max z %+.2f   min z %+.2f"
      % (ti["rejection_at_05"], ti["mean_z"], ti["sd_z"], ti["max_z"], ti["min_z"]))
pd.DataFrame([ti]).to_csv(os.path.join(A.OUT, "TYPE_I_NONCIRCULAR.csv"), index=False)
np.savez(os.path.join(A.NULLS, "TYPEI__R1_min__RAW__FROZEN__synthetic_z.npz"),
         draws_raw_unstandardised=zs, observed_signed=np.array([np.nan]),
         label=np.array(["non-circular type-I z over 100 synthetic candidates"]))

# =============================================================== 5. PLACEBOS
A.hdr("5. PLACEBOS")
pl = []
cellC1 = cell_with(b_check, d["C1_player_rest"].to_numpy(float), "FROZEN")
ident = np.array([cellC1.dr2(d["C1_player_rest"].to_numpy(float).copy()) for _ in range(20)])
assert float(np.std(ident, ddof=1)) < 1e-15, "no-op placebo is not the identity"
pl.append(dict(placebo="NOOP_identity_transform", n=20, observed_sd=float(np.std(ident, ddof=1)),
               n_distinct=int(len(np.unique(ident))), note="transform asserted to be the identity"))
print("  NOOP identity: observed sd %.3e  distinct draw values %d"
      % (pl[-1]["observed_sd"], pl[-1]["n_distinct"]))
# response placebo: permute the RESPONSE inside the team-game, rerun
rp = []
for i in range(200):
    pi = SW_TG.draw_index(np.random.default_rng(70000 + i))
    y_p = y_real[pi]
    b_p = rebuild_base(y_p)
    c = cell_with(b_p, d["C1_player_rest"].to_numpy(float), "FROZEN", y_p)
    rp.append(float(c.dr2()))
rp = np.asarray(rp)
pl.append(dict(placebo="RESPONSE_permuted_within_team_game", n=200, observed_sd=float(rp.std(ddof=1)),
               n_distinct=int(len(np.unique(rp))),
               note="mean %+.6f  max %+.6f  min %+.6f" % (rp.mean(), rp.max(), rp.min())))
print("  RESPONSE placebo: mean %+.6f  sd %.6f  max %+.6f" % (rp.mean(), rp.std(ddof=1), rp.max()))
np.savez(os.path.join(A.NULLS, "RESPONSE_PLACEBO__R1_min__RAW__FROZEN__C1_player_rest.npz"),
         draws_raw_unstandardised=rp, observed_signed=np.array([float(cellC1.dr2())]),
         label=np.array(["response permuted within team-game, whole path rerun"]))
pd.DataFrame(pl).to_csv(os.path.join(A.OUT, "PLACEBOS.csv"), index=False)

# =============================================================== 6. LEAKAGE PROBE
A.hdr("6. FUTURE-LEAKAGE PROBE -- correlation with the player's OWN strictly-after-date future")
fut = np.full(len(d), np.nan)
srt = np.lexsort((d["game_id"].to_numpy(), d["game_date"].to_numpy(), PS))
mv = y_real[srt]
gv = PS[srt]
acc = {}
for i in range(len(srt) - 1, -1, -1):
    g = gv[i]
    s, c = acc.get(g, (0.0, 0))
    fut[srt[i]] = s / c if c > 0 else np.nan
    acc[g] = (s + mv[i], c + 1)
lk = []
m = dm & mask23 & np.isfinite(fut)
for c in A.CANDIDATES + ["B_TUNED"]:
    v = b_s02 if c == "B_TUNED" else d[c].to_numpy(float)
    lk.append(dict(column=c, n=int(m.sum()), corr_with_own_future_mean_minutes=
                   float(np.corrcoef(v[m], fut[m])[0, 1])))
    print("  %-20s corr with own strictly-after-date future mean minutes %+8.4f"
          % (c, lk[-1]["corr_with_own_future_mean_minutes"]))
pd.DataFrame(lk).to_csv(os.path.join(A.OUT, "LEAKAGE_PROBE.csv"), index=False)

A.dump("s05", dict(prereg_sha=A.prereg_sha(), injection_floors=FLOORS, type_I=ti,
                   null_centre=nc_rows, placebos=pl))
A.hdr("s05 done")
