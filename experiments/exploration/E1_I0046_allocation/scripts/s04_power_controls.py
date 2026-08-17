"""E1_I0046 s04 -- power by COMPONENT-WISE injection, type-I, placebos, leakage probe, substitute test.

The synthetic-data generator is COMPOSITION-PRESERVING by construction:
    y' = f + PI(resid) + theta * delta
with f a projected allocation (sums to 1 inside every team-game), PI a within-team-game permutation
of the base residual (which sums to 0 inside every team-game), and delta the candidate centred
within team-game (also sums to 0).  Therefore y' sums to exactly 1 inside every team-game, at every
theta, in every replicate -- asserted, not assumed.  E1_I0036 found the shuffled-RESIDUAL injection
style defective; here the planted effect is added to the REAL response and the WHOLE path is rerun.
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import al_base as A

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 200)

A.hdr("E1_I0046  --  s04  POWER, CONTROLS, LEAKAGE, SUBSTITUTE TEST")
print("PREREG.md sha256 = %s" % A.prereg_sha())

d = pd.read_parquet(os.path.join(A.SCR, "_frame2.parquet"))
A.assert_partition(d, "FRAME2", True)
BASE = dict(np.load(os.path.join(A.SCR, "_base.npz")))
n = len(d)
season = d["season"].to_numpy()
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg)
dm = A.decision_mask(d)
allrows = np.ones(n, bool)
swap = A.WithinTeamGameSwap(d)


def tg_centre(x):
    m = np.bincount(tg_code, weights=x, minlength=n_tg) / np.maximum(counts, 1)
    return x - m[tg_code]


def zcand(c):
    v = d[c].to_numpy(float)
    return (v - v.mean()) / (v.std(ddof=1) if v.std(ddof=1) > 0 else 1.0)


# ======================================================= 1. NO-OP PLACEBO
A.hdr("1. NO-OP PLACEBO -- the identity permutation through the WHOLE path")
pl = []
for resp in ["R1_s_pts", "R2_s_min", "R3_s_fga"]:
    for cand in ["A2_fga_share_prior", "A4_vac_x_own"]:
        for arm in ["FROZEN", "UNFROZEN"]:
            c = A.Cell(d, d[resp].to_numpy(float), BASE[resp], cand, zcand(cand), allrows, dm,
                       A.CLEAN_EVAL_SEASONS, arm, True)
            real = float(c.dr2())
            ident = float(c.dr2(c.cand.copy()))
            pl.append(dict(response=resp, candidate=cand, arm=arm, real=real, identity=ident,
                           deviation=abs(real - ident),
                           transform_is_identity=bool(np.array_equal(c.cand, c.cand.copy()))))
            print("  %-9s %-20s %-9s real %+.10f  identity %+.10f  deviation %.3e  "
                  "transform asserted identity: %s"
                  % (resp, cand, arm, real, ident, abs(real - ident),
                     pl[-1]["transform_is_identity"]))
pd.DataFrame(pl).to_csv(os.path.join(A.OUT, "PLACEBOS.csv"), index=False)

# ======================================================= 2. COMPONENT-WISE INJECTION
A.hdr("2. COMPONENT-WISE INJECTION -- planted into the REAL response, whole path rerun")
INJ_CELLS = [("R1_s_pts", "A2_fga_share_prior", "UNFROZEN"),
             ("R1_s_pts", "A4_vac_x_own", "FROZEN"),
             ("R1_s_pts", "A1_min_share_prior", "UNFROZEN"),
             ("R2_s_min", "A4_vac_x_own", "FROZEN"),
             ("R3_s_fga", "A4_vac_x_own", "FROZEN")]
TARGETS = [0.0, 0.5, 1.0, 2.0, 4.0]          # x the single-cell floor, in RECOVERED dR2 units
R_REP = 30
N_INJ_DRAWS = 150
inj = []
t0 = time.time()
print("  DGP: y' = project(f + theta*z) + PI(resid).  The planted effect is expressed in the")
print("  MODEL'S OWN regressor z and its OWN functional form, so a recovered value is directly")
print("  comparable to the observed statistic.  An earlier version planted a team-game-centred")
print("  vector instead, which is NOT the model's regressor; it recovered NEGATIVE effects and is")
print("  recorded as DEFECT D-05.  The simplex is asserted on every synthetic response.")
for resp, cand, arm in INJ_CELLS:
    y = d[resp].to_numpy(float)
    f = BASE[resp]
    resid = y - f
    ssum = np.bincount(tg_code, weights=resid, minlength=n_tg)
    assert float(np.max(np.abs(ssum))) < 1e-9, "residual does not sum to 0 within team-game"
    z = zcand(cand)

    def make_true(theta):
        return A.project(f + theta * z, tg_code, n_tg, counts)

    # ---- calibrate theta to a target RECOVERED dR2, noiselessly (real residual, unpermuted)
    grid = np.r_[0.0, np.geomspace(1e-4, 1.0, 28)]
    ach = []
    for th in grid:
        cl = A.Cell(d, make_true(th) + resid, f, cand, z, allrows, dm, A.CLEAN_EVAL_SEASONS,
                    arm, True)
        ach.append(float(cl.dr2()))
    ach = np.array(ach)
    base_ach = ach[0]

    def theta_for(target):
        want = base_ach + target
        for i in range(1, len(grid)):
            if ach[i - 1] < want <= ach[i]:
                return float(grid[i - 1] + (want - ach[i - 1]) * (grid[i] - grid[i - 1]) /
                             (ach[i] - ach[i - 1]))
        return float(grid[int(np.argmax(ach))])

    for tmul in TARGETS:
        target = tmul * A.FLOOR_SINGLE_CELL
        theta = 0.0 if tmul == 0 else theta_for(target)
        rej = 0
        recs = []
        for r in range(R_REP):
            rng = np.random.default_rng(A.SEED + 1000 * r + int(tmul * 97))
            keys = rng.random(n)
            perm = np.lexsort((keys, tg_code))
            rp = np.empty(n)
            rp[swap.order] = resid[perm]
            yprime = make_true(theta) + rp
            s2 = np.bincount(tg_code, weights=yprime, minlength=n_tg)
            assert float(np.max(np.abs(s2 - 1.0))) < 1e-9, "synthetic response left the simplex"
            cl = A.Cell(d, yprime, f, cand, z, allrows, dm, A.CLEAN_EVAL_SEASONS, arm, True)
            rr = A.run_null(cl, swap, n_draws=N_INJ_DRAWS, seed=A.SEED + r, label="inj")
            recs.append(rr["real"] - rr["null_mean"])
            rej += int(rr["p"] <= 0.05)
        inj.append(dict(response=resp, candidate=cand, arm=arm, target_x_floor=tmul,
                        target_dr2=target, theta=theta, noiseless_dr2=float(
                            A.Cell(d, make_true(theta) + resid, f, cand, z, allrows, dm,
                                   A.CLEAN_EVAL_SEASONS, arm, True).dr2()) - base_ach,
                        n_replicates=R_REP, n_draws=N_INJ_DRAWS,
                        rejection_rate=rej / R_REP, mean_recovered_centred=float(np.mean(recs)),
                        sd_recovered=float(np.std(recs, ddof=1))))
        print("  %-9s %-20s %-9s target %.1fx floor (dR2 %.5f)  theta %.5f  noiseless %.5f  "
              "rejection %.3f  mean recovered %+.6f"
              % (resp, cand, arm, tmul, target, theta, inj[-1]["noiseless_dr2"],
                 rej / R_REP, float(np.mean(recs))))
ij = pd.DataFrame(inj)
ij.to_csv(os.path.join(A.OUT, "INJECTION_POWER.csv"), index=False)
print("  [injection done in %.1f s]" % (time.time() - t0))

# injection-verified 80% floor per cell, by linear interpolation on the rejection curve
fl = []
for (resp, cand, arm), g in ij.groupby(["response", "candidate", "arm"], sort=False):
    g = g.sort_values("target_dr2")
    # the floor is expressed in RECOVERED dR2 units, so it is directly comparable to the observed
    x, yv = g["mean_recovered_centred"].to_numpy(), g["rejection_rate"].to_numpy()
    xt = g["target_dr2"].to_numpy()
    floor = np.nan
    for i in range(1, len(x)):
        if yv[i - 1] < 0.8 <= yv[i]:
            floor = x[i - 1] + (0.8 - yv[i - 1]) * (x[i] - x[i - 1]) / (yv[i] - yv[i - 1])
            break
    if np.isnan(floor) and yv[0] >= 0.8:
        floor = x[0]
    fl.append(dict(response=resp, candidate=cand, arm=arm,
                   floor_injection_verified_recovered_units=floor,
                   max_target_tested=float(xt.max()),
                   max_recovered_tested=float(x.max()),
                   max_rejection_reached=float(yv.max()),
                   type_I_at_theta0=float(yv[0]),
                   floor_kind="injection" if np.isfinite(floor) else "NOT_REACHED_within_grid"))
    print("  FLOOR %-9s %-20s %-9s injection-verified 80%% floor (recovered units) = %s   "
          "max rejection reached %.3f at recovered %.6f   type-I at theta=0 = %.3f"
          % (resp, cand, arm, ("%.6f" % floor) if np.isfinite(floor) else "NOT REACHED",
             yv.max(), x.max(), yv[0]))
pd.DataFrame(fl).to_csv(os.path.join(A.OUT, "POWER_FLOORS.csv"), index=False)

# ============ 2b. TYPE-I ON A SYNTHETIC CANDIDATE -- the NON-CIRCULAR calibration check
A.hdr("2b. TYPE-I, NON-CIRCULAR.  Real response, real serial structure, ZERO true relation.")
print("  The injection DGP in section 2 permutes residuals inside the team-game, which destroys the")
print("  same structure N_TGSWAP destroys -- so its type-I rate is CIRCULAR and cannot detect a")
print("  too-narrow null.  This check instead keeps the REAL response and builds candidates that")
print("  carry a real player's whole series but belong to a player on ANOTHER team-season, so the")
print("  candidate has realistic level and autocorrelation and ZERO true relation to the response.")
pswap = A.PlayerSeriesSwap(d)
codes_ps = d["ps_code"].to_numpy()
o_ps = np.lexsort((d["game_id"].to_numpy(), d["game_date"].to_numpy(), codes_ps))
oc = codes_ps[o_ps]
st_ = np.flatnonzero(np.r_[True, oc[1:] != oc[:-1]])
en_ = np.r_[st_[1:], len(oc)]
PS_GROUPS = [o_ps[s:e] for s, e in zip(st_, en_)]
t1 = []
for resp, cand, arm in [("R1_s_pts", "A2_fga_share_prior", "UNFROZEN"),
                        ("R1_s_pts", "A4_vac_x_own", "FROZEN")]:
    x0 = zcand(cand)
    rej = 0
    N_T1 = 100
    zs = []
    for r in range(N_T1):
        rng = np.random.default_rng(A.SEED + 31 * r)
        perm = rng.permutation(len(PS_GROUPS))
        xs = np.empty(n)
        for a, b in enumerate(perm):
            ia, ib = PS_GROUPS[a], PS_GROUPS[b]
            na, nb = len(ia), len(ib)
            pos = (np.round(np.arange(na) / max(na - 1, 1) * max(nb - 1, 0)).astype(int)
                   if na > 1 else np.zeros(na, int))
            xs[ia] = x0[ib][pos]
        cl = A.Cell(d, d[resp].to_numpy(float), BASE[resp], cand, xs, allrows, dm,
                    A.CLEAN_EVAL_SEASONS, arm, True)
        rr = A.run_null(cl, swap, n_draws=120, seed=A.SEED + r, label="typeI")
        zs.append(rr["z"])
        rej += int(rr["p"] <= 0.05)
    t1.append(dict(response=resp, candidate=cand, arm=arm, n_replicates=N_T1, n_draws=120,
                   null="N_TGSWAP", rejection_rate_alpha05=rej / N_T1,
                   mean_z=float(np.nanmean(zs)), sd_z=float(np.nanstd(zs, ddof=1))))
    print("  %-9s %-20s %-9s  type-I rejection at alpha=0.05: %.3f  (nominal 0.05)   mean z %+.3f  "
          "sd z %.3f  <-- sd z >> 1 means the null is TOO NARROW"
          % (resp, cand, arm, rej / N_T1, t1[-1]["mean_z"], t1[-1]["sd_z"]))
pd.DataFrame(t1).to_csv(os.path.join(A.OUT, "TYPE_I_NONCIRCULAR.csv"), index=False)

# ============ 2c. THE SERIAL-STRUCTURE-PRESERVING NULL, run beside N_TGSWAP
A.hdr("2c. N_PSWAP -- a null that PRESERVES the candidate's within-player serial structure")
print("  N_TGSWAP blocks=%d groups=%d   N_PSWAP blocks(team-seasons)=%d groups(player-seasons)=%d"
      % (swap.n_blocks, swap.n_groups, pswap.n_blocks, pswap.n_groups))
ps_rows = []
for resp in A.RESPONSES:
    for cand in ["A1_min_share_prior", "A2_fga_share_prior", "A3_starter_rate_prior",
                 "A4_vac_x_own", "G01_noise"]:
        for arm in ["FROZEN", "UNFROZEN"]:
            cl = A.Cell(d, d[resp].to_numpy(float), BASE[resp], cand, zcand(cand), allrows, dm,
                        A.CLEAN_EVAL_SEASONS, arm, True)
            rr = A.run_null(cl, pswap, n_draws=800, seed=A.SEED, label="%s|%s|%s|N_PSWAP"
                            % (resp, arm, cand))
            ps_rows.append(dict(response=resp, candidate=cand, arm=arm, null="N_PSWAP",
                                n_blocks=rr["n_blocks"], n_groups=rr["n_groups"],
                                observed=rr["real"], null_mean=rr["null_mean"],
                                null_sd=rr["null_sd"], z=rr["z"], p=rr["p"],
                                mde80_analytic=2.80 * rr["null_sd"]))
            A.save_null("%s__DECISION__%s__PROJ__%s__N_PSWAP" % (resp, arm, cand), rr)
            print("  %-9s %-9s %-22s N_PSWAP  obs %+.6f  null mu %+.6f sd %.6f  z %+8.3f  p %.4f"
                  % (resp, arm, cand, rr["real"], rr["null_mean"], rr["null_sd"], rr["z"], rr["p"]))
pd.DataFrame(ps_rows).to_csv(os.path.join(A.OUT, "NULLS_PSWAP.csv"), index=False)

# ======================================================= 3. RESPONSE-PERMUTATION PLACEBO
A.hdr("3. RESPONSE PLACEBO -- permute the RESPONSE inside the team-game, rerun the whole path")
rp_rows = []
for resp, cand, arm in [("R1_s_pts", "A2_fga_share_prior", "UNFROZEN"),
                        ("R1_s_pts", "A4_vac_x_own", "FROZEN")]:
    y = d[resp].to_numpy(float)
    vals = []
    for r in range(60):
        rng = np.random.default_rng(A.SEED + 7 * r)
        keys = rng.random(n)
        perm = np.lexsort((keys, tg_code))
        yp = np.empty(n)
        yp[swap.order] = y[perm]
        cl = A.Cell(d, yp, BASE[resp], cand, zcand(cand), allrows, dm, A.CLEAN_EVAL_SEASONS, arm, True)
        vals.append(float(cl.dr2()))
    rp_rows.append(dict(response=resp, candidate=cand, arm=arm, n_replicates=60,
                        mean_dr2=float(np.mean(vals)), sd_dr2=float(np.std(vals, ddof=1)),
                        max_dr2=float(np.max(vals))))
    print("  %-9s %-20s %-9s response-permuted dR2: mean %+.6f  sd %.6f  max %+.6f"
          % (resp, cand, arm, np.mean(vals), np.std(vals, ddof=1), np.max(vals)))
pd.DataFrame(rp_rows).to_csv(os.path.join(A.OUT, "RESPONSE_PLACEBO.csv"), index=False)

# ======================================================= 4. FUTURE-LEAKAGE PROBE
A.hdr("4. FUTURE-LEAKAGE PROBE -- a SCREENING FLAG, not a verdict (kit K1)")
o = np.lexsort((d["game_id"].to_numpy(), d["game_date"].to_numpy(), d["ps_code"].to_numpy()))
ps = d["ps_code"].to_numpy()[o]
lk = []
for resp in A.RESPONSES:
    ys = d[resp].to_numpy(float)[o]
    fut = np.full(len(ys), np.nan)
    st = 0
    for i in range(1, len(ys) + 1):
        if i == len(ys) or ps[i] != ps[st]:
            seg = ys[st:i]
            cs = np.cumsum(seg)
            tot = cs[-1]
            cnt = np.arange(len(seg))
            rem = len(seg) - 1 - cnt
            fut[st:i] = np.where(rem > 0, (tot - cs) / np.maximum(rem, 1), np.nan)
            st = i
    for col in [("B_TUNED", BASE[resp][o])] + [(c, d[c].to_numpy(float)[o]) for c in A.CANDIDATES]:
        name, v = col
        ok = np.isfinite(v) & np.isfinite(fut)
        a, b = v[ok] - v[ok].mean(), fut[ok] - fut[ok].mean()
        cc = float(a @ b) / np.sqrt(float(a @ a) * float(b @ b))
        lk.append(dict(response=resp, column=name, n=int(ok.sum()), corr_with_own_future=cc))
    q = [r for r in lk if r["response"] == resp]
    print("  %-9s corr with the player's OWN strictly-after-date future share:  %s"
          % (resp, "  ".join("%s %+.4f" % (r["column"].replace("_share_prior", ""),
                                           r["corr_with_own_future"]) for r in q)))
pd.DataFrame(lk).to_csv(os.path.join(A.OUT, "LEAKAGE_PROBE.csv"), index=False)

# ======================================================= 5. THE SUBSTITUTE TEST
A.hdr("5. SUBSTITUTE TEST -- is the attempts channel an ADDITION or a REPLACEMENT?")
print("  ADDED AFTER THE PREREG HASH.  Direction of effect on the headline is stated in NOTES.md.")
sub = []
for es in A.CLEAN_EVAL_SEASONS:
    pass
y1 = d["R1_s_pts"].to_numpy(float)
best_alt = {}
for es in A.CLEAN_EVAL_SEASONS:
    tr = (season < es) & dm
    best = None
    for h in A.H_GRID:
        for kk in A.K_GRID:
            raw = A.allocator_raw(d, "R3_s_fga", h, kk)      # ATTEMPTS-share allocator ...
            f = A.project(raw, tg_code, n_tg, counts)
            sse = float(((y1[tr] - f[tr]) ** 2).sum())        # ... tuned to forecast POINTS share
            if best is None or sse < best[0]:
                best = (sse, h, kk, f)
    best_alt[es] = best
ALT = np.full(n, np.nan)
for es in A.CLEAN_EVAL_SEASONS:
    ALT[season == es] = best_alt[es][3][season == es]
ALT = np.where(np.isfinite(ALT), ALT, best_alt[A.CLEAN_EVAL_SEASONS[0]][3])
for popname, popmask in [("DECISION", dm), ("ALL_APPEARED", allrows)]:
    m = popmask & np.isin(season, A.CLEAN_EVAL_SEASONS)
    r = A.paired_signflip(y1[m], ALT[m], BASE["R1_s_pts"][m], tg_code[m], n_draws=A.N_DRAWS,
                          seed=A.SEED)
    sub.append(dict(population=popname, contrast="ATTEMPTS-share allocator vs POINTS-share allocator",
                    response="R1_s_pts", n=int(m.sum()), n_blocks=r["n_blocks"],
                    r2_attempts_allocator=A.r2_of_forecast(y1[m], ALT[m]),
                    r2_points_allocator=A.r2_of_forecast(y1[m], BASE["R1_s_pts"][m]),
                    dr2=r["real"], null_mean=r["null_mean"], null_sd=r["null_sd"], z=r["z"],
                    p=r["p"], mde80_analytic=2.80 * r["null_sd"],
                    selected=str({int(es): (best_alt[es][1], best_alt[es][2])
                                  for es in A.CLEAN_EVAL_SEASONS})))
    print("  %-13s R2 attempts-allocator %+.5f vs points-allocator %+.5f  dR2 %+.6f  z %+7.2f  "
          "p %.4f  (selected %s)" % (popname, sub[-1]["r2_attempts_allocator"],
                                     sub[-1]["r2_points_allocator"], r["real"], r["z"], r["p"],
                                     sub[-1]["selected"]))
# and the two channels TOGETHER, unfrozen, against each alone
for popname, popmask in [("DECISION", allrows * dm)]:
    m = popmask & np.isin(season, A.CLEAN_EVAL_SEASONS)
    r = A.paired_signflip(y1[m], 0.5 * (ALT[m] + BASE["R1_s_pts"][m]), BASE["R1_s_pts"][m],
                          tg_code[m], n_draws=A.N_DRAWS, seed=A.SEED)
    sub.append(dict(population=popname, contrast="50/50 BLEND vs POINTS-share allocator",
                    response="R1_s_pts", n=int(m.sum()), n_blocks=r["n_blocks"],
                    r2_attempts_allocator=A.r2_of_forecast(y1[m], 0.5 * (ALT[m] + BASE["R1_s_pts"][m])),
                    r2_points_allocator=A.r2_of_forecast(y1[m], BASE["R1_s_pts"][m]),
                    dr2=r["real"], null_mean=r["null_mean"], null_sd=r["null_sd"], z=r["z"],
                    p=r["p"], mde80_analytic=2.80 * r["null_sd"], selected="n/a"))
    print("  %-13s 50/50 BLEND R2 %+.5f vs %+.5f  dR2 %+.6f  z %+7.2f  p %.4f"
          % (popname, sub[-1]["r2_attempts_allocator"], sub[-1]["r2_points_allocator"],
             r["real"], r["z"], r["p"]))
pd.DataFrame(sub).to_csv(os.path.join(A.OUT, "SUBSTITUTE_TEST.csv"), index=False)

# ======================================================= 6. SEASON SPLIT + DISCLOSED WINDOW
A.hdr("6. SEASON SPLIT AND THE DISCLOSED 2022 WINDOW -- for the cells that survived s03")
ss = []
for resp, cand, arm in [("R1_s_pts", "A2_fga_share_prior", "UNFROZEN"),
                        ("R1_s_pts", "A2_fga_share_prior", "FROZEN"),
                        ("R1_s_pts", "A4_vac_x_own", "FROZEN"),
                        ("R1_s_pts", "A1_min_share_prior", "UNFROZEN")]:
    for wlab, evs in [("CLEAN_2023_24", A.CLEAN_EVAL_SEASONS), ("EVAL_2023_ONLY", [2023]),
                      ("EVAL_2024_ONLY", [2024]), ("DISCLOSED_2022", [2022])]:
        c = A.Cell(d, d[resp].to_numpy(float), BASE[resp], cand, zcand(cand), allrows, dm, evs,
                   arm, True)
        r = c.full()
        if r is None:
            continue
        ss.append(dict(response=resp, candidate=cand, arm=arm, window=wlab, n=r["n"],
                       r2_base=r["r2_base"], dr2=r["dr2"], beta=r["beta"]))
        print("  %-9s %-20s %-9s %-15s n=%5d  base R2 %+.5f  dR2 %+.6f  beta %+.6f"
              % (resp, cand, arm, wlab, r["n"], r["r2_base"], r["dr2"], r["beta"]))
pd.DataFrame(ss).to_csv(os.path.join(A.OUT, "SEASON_STABILITY.csv"), index=False)

# ======================================================= 7. BOOTSTRAP vs ANALYTIC VARIANCE
A.hdr("7. BLOCK-BOOTSTRAP vs PERMUTATION null sd (D113 check)")
bs = []
for resp, cand, arm in [("R1_s_pts", "A2_fga_share_prior", "UNFROZEN"),
                        ("R1_s_pts", "A4_vac_x_own", "FROZEN")]:
    c = A.Cell(d, d[resp].to_numpy(float), BASE[resp], cand, zcand(cand), allrows, dm,
               A.CLEAN_EVAL_SEASONS, arm, True)
    r = c.full()
    sst = r["sst"]
    dl = (r["y"] - r["yb"]) ** 2 - (r["y"] - r["ya"]) ** 2
    blk = tg_code[r["idx"]]
    codes = pd.factorize(blk, sort=True)[0]
    nb = int(codes.max()) + 1
    sums = np.bincount(codes, weights=dl, minlength=nb)
    rng = np.random.default_rng(A.SEED)
    draws = np.array([float(sums[rng.integers(0, nb, nb)].sum()) / sst for _ in range(4000)])
    bs.append(dict(response=resp, candidate=cand, arm=arm, dr2=r["dr2"],
                   bootstrap_sd=float(draws.std(ddof=1)), n_blocks=nb))
    print("  %-9s %-20s %-9s dR2 %+.6f  block-bootstrap sd %.6f over %d team-game blocks"
          % (resp, cand, arm, r["dr2"], draws.std(ddof=1), nb))
pd.DataFrame(bs).to_csv(os.path.join(A.OUT, "BOOTSTRAP_VARIANCE.csv"), index=False)

A.dump("s04", dict(prereg_sha=A.prereg_sha(), placebo=pl, injection=inj, floors=fl,
                   type_I_noncircular=t1, pswap=ps_rows,
                   response_placebo=rp_rows, leakage=lk, substitute=sub, season=ss, bootstrap=bs))
print("\n  s04 OK.")
