"""S06 -- THE ROBUSTNESS ARM THAT COULD RETRACT THE SURVIVORS.

The BLOCKBOOT diagnostic says a within-block POSITIONAL profile shared across blocks exists in
these responses (measured: resp_shared_position_profile_sd 0.167-0.264 on A1).  If a surviving
cell's association is really "forecast error shrinks as the season goes on, and so does /
so does not this candidate", then it is a time-in-season effect wearing a candidate's name.

Direct test: put within-block position INTO THE BASE and re-run everything.

D101 -- THIS IS A SEPARATE ARM WITH ITS OWN DENOMINATOR AND NOTHING IS COMPARED ACROSS ARMS:
  response  : the cell's own dependent
  row set   : identical to the corresponding main arm (A4 3,549 / A1 13,879)
  base      : season fixed effects PLUS relative within-player-season position and its square
              -- 3 seasons + 2 = 5 columns, against the main arm's 3
  SST basis : the response residualised on THAT base, on those same rows.  It is NOT the main
              arm's SST, so dR2 here is NOT comparable to dR2 there, and is never differenced.
  weighting : unweighted
  statistic : signed one-column classical t on the candidate residualised on that same base
  family    : the same 348 cells, one shared gather index per draw, max|t| bar
Signed unstandardised draws saved.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *          # noqa

R = 2000
SEED = 20260808
Z80 = 0.8416212335729143
s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
CELLS = s00["cells54"]
rows = []

for ARM in ("A4_CLEAN_DEC", "A1_FULL"):
    mask = ARM_MASKS[ARM]
    ctx = arm_context(mask)
    m = ctx["m"]
    GP = blocks_on(mask, "player_id")
    BL = [b for s, bl in GP.items() for b in bl]
    # relative within-player-season position, 0..1, and its square
    pos = np.zeros(m)
    for b in BL:
        pos[b] = np.arange(len(b)) / max(len(b) - 1, 1)
    ss = ctx["ss"]
    sc = np.asarray(pd.Categorical(ss).codes, dtype=np.int64)
    nsn = int(sc.max() + 1)
    Bse = np.zeros((m, nsn)); Bse[np.arange(m), sc] = 1.0
    BASE = np.column_stack([Bse, pos, pos ** 2])
    Q, _ = np.linalg.qr(BASE)
    K = Q.shape[1]
    DF = m - K - 1

    def resid(M):
        M = np.asarray(M, float)
        return M - Q @ (Q.T @ M)

    def tv(ytil, Mt):
        with np.errstate(invalid="ignore", divide="ignore"):
            sxx = (Mt * Mt).sum(0); sxy = Mt.T @ ytil
            beta = np.where(sxx > 0, sxy / sxx, np.nan)
            sse = float(ytil @ ytil) - beta * sxy
            se = np.sqrt(np.maximum(sse, 0.0) / DF / np.where(sxx > 0, sxx, np.nan))
            return np.where(se > 0, beta / se, np.nan), sse

    Xza = ctx["Xza"]
    Xr = resid(Xza)
    Yr, SST = {}, {}
    for k, _ in DEPS:
        Yr[k] = resid(ctx["Y"][k].reshape(-1, 1))[:, 0]
        SST[k] = float(Yr[k] @ Yr[k])
    obs_t, obs_dr2 = {}, {}
    for k, _ in DEPS:
        tt, sse = tv(Yr[k], Xr)
        obs_t[k] = tt
        obs_dr2[k] = (SST[k] - sse) / SST[k]

    def composed2(rng):
        idx = np.arange(m)
        for s, bl in GP.items():
            o = rng.permutation(len(bl))
            for i, b in enumerate(bl):
                don = bl[o[i]]; idx[b] = don[rng.integers(0, len(don), len(b))]
        return idx

    rng = np.random.default_rng(SEED)
    NT = {k: np.zeros((R, C)) for k, _ in DEPS}
    t0 = time.time()
    print("\n=== %s position-adjusted arm: n=%d  base cols=%d (3 season + pos + pos^2) ==="
          % (ARM, m, K), flush=True)
    for d in range(R):
        Xp = resid(Xza[composed2(rng)])
        for k, _ in DEPS:
            NT[k][d] = tv(Yr[k], Xp)[0]
        if (d + 1) % 500 == 0:
            print("   draw %d/%d (%.0fs)" % (d + 1, R, time.time() - t0), flush=True)
    maxt = np.nanmax(np.abs(np.concatenate([NT[k] for k, _ in DEPS], axis=1)), axis=1)
    bar95 = float(np.nanpercentile(maxt, 95))
    np.savez_compressed(os.path.join(HERE, "nulls", "posadj_composed2_%s.npz" % ARM),
                        arm=np.array([ARM]), n=np.array([m]), R=np.array([R]),
                        seed=np.array([SEED]), base_cols=np.array([K]),
                        names=np.array(names),
                        dependents=np.array([k for k, _ in DEPS]),
                        maxt_familywise=maxt,
                        **{("t_signed__" + k): NT[k] for k, _ in DEPS},
                        **{("observed_t__" + k): obs_t[k] for k, _ in DEPS},
                        **{("observed_dr2__" + k): obs_dr2[k] for k, _ in DEPS})
    print("   family-wise bar95 (position-adjusted base) = %.4f" % bar95)
    for cell in CELLS:
        cand, dep = cell.split("|")
        j = names.index(cand)
        dv = NT[dep][:, j]
        fin = np.isfinite(dv)
        obs = float(obs_t[dep][j])
        sxxj = float((Xr[:, j] ** 2).sum())
        rec = dict(arm=ARM + "__POSADJ", cell=cell, candidate=cand, dependent=dep,
                   n=m, base_cols=K, R_draws=R, sxx_after_posadj_base=sxxj,
                   observed_signed_t=obs if np.isfinite(obs) else np.nan,
                   observed_dr2_posadj_SST=float(obs_dr2[dep][j]),
                   bar_familywise_q95=bar95)
        if fin.sum() == 0 or not np.isfinite(obs):
            rec["not_estimable"] = "CANDIDATE_ANNIHILATED_BY_POSITION_ADJUSTED_BASE"
            rows.append(rec); continue
        a = np.abs(dv[fin])
        rec["not_estimable"] = ""
        rec["null_mean_signed_t"] = float(dv[fin].mean())
        rec["null_sd_signed_t"] = float(dv[fin].std(ddof=1))
        rec["p_percell_plus1"] = float((np.sum(a >= abs(obs)) + 1) / (len(a) + 1))
        rec["p_familywise_plus1"] = float((np.sum(maxt >= abs(obs)) + 1) / (len(maxt) + 1))
        rec["bar_percell_abs_t"] = float(np.percentile(a, 97.5))
        rec["mde80_percell_ANALYTIC"] = (rec["bar_percell_abs_t"] +
                                         Z80 * rec["null_sd_signed_t"]) ** 2 / m
        rec["floor_basis"] = "ANALYTIC"
        rows.append(rec)

P = pd.DataFrame(rows)
P.to_csv(os.path.join(HERE, "_POSITION_ADJUSTED.csv"), index=False)
print("\nwrote _POSITION_ADJUSTED.csv", P.shape)

J = pd.read_csv(os.path.join(HERE, "CORRECTED_VERDICTS.csv"))
for ARM in ("A4_CLEAN_DEC", "A1_FULL"):
    surv = J[(J["arm"] == ARM) & (J["corrected_verdict"] == "FAMILYWISE_SIGNIFICANT")]["cell"]
    p = P[P["arm"] == ARM + "__POSADJ"].set_index("cell")
    print("\n=== %s : the %d clean family-wise survivors under a POSITION-ADJUSTED base ==="
          % (ARM, len(surv)))
    sub = p.loc[[c for c in surv if c in p.index]]
    ne = sub[sub["not_estimable"] != ""]
    ok = sub[sub["not_estimable"] == ""]
    print("   annihilated by the position-adjusted base : %d  %s"
          % (len(ne), list(ne.index)))
    print("   still family-wise significant             : %d of %d"
          % (int((ok["p_familywise_plus1"] < 0.05).sum()), len(ok)))
    print("   still per-cell significant                : %d of %d"
          % (int((ok["p_percell_plus1"] < 0.05).sum()), len(ok)))
    print(ok[["observed_signed_t", "observed_dr2_posadj_SST", "p_percell_plus1",
              "p_familywise_plus1"]].sort_values("observed_dr2_posadj_SST",
                                                 ascending=False).to_string())
print("DONE s06")
