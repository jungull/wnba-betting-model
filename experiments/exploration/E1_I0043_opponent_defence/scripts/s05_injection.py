"""
s05 -- COMPONENT-WISE INJECTION.  Is the verdict null actually able to see this candidate?

WHY IT IS COMPONENT-WISE AND NOT A SHUFFLED-RESIDUAL TEST.  D-04 (D115) proposed validating a null
by shuffling residuals.  E1_I0038 showed that shuffling residuals destroys the alignment between
entity-mean carrier and entity-mean residual by a factor of 74, moving the null's own centre by
167x, so the injection ends up GRADING A DIFFERENT NULL DISTRIBUTION FROM THE ONE THAT DECIDED THE
CELL.  This protocol therefore:

  1. generates its H0 responses with a permutation AT THE SAME LEVEL AS THE VERDICT NULL, so the
     null distribution being graded is the one that took the verdict;
  2. plants the effect on ONE NAMED COMPONENT at a time -- the between-opponent-team-season mean
     (77.1% of this candidate's variance) and the within-opponent-team-season deviation (22.9%) --
     so the answer is "which component is this null blind to", not just "is it blind";
  3. reports the NULL-CENTRE RATIO (injection null mean / verdict null mean) beside every power
     number, which is E1_I0038's one-line drop-in check that the certification means anything.

H0 GENERATOR.  y0 = base_pred + Pi(e), where e is the base residual and Pi relabels whole
opponent-team-season residual SERIES.  The base prediction is untouched, e keeps its marginal and
its within-entity temporal shape, and the only thing destroyed is the opponent labelling -- which
is exactly the hypothesis the verdict null tests.

REPLICATE COUNT.  nrep = 250 (se on a power estimate 0.025), because E1_I0038's DEFECTS D-03
records that 60 replicates cannot carry a hard 0.80 threshold (se 0.052).  Every floor this screen
quotes is therefore INJECTION-VERIFIED.  No analytic MDE80 appears anywhere in this screen.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import od_base as ob  # noqa: E402
import od_fast as of  # noqa: E402

LOG = []
NREP = 250
NDRAW = 250
ALPHA = 0.05
DELTAS = [0.0, 0.0005, 0.001, 0.002, 0.004, 0.008]


def P(x=""):
    print(x)
    LOG.append(str(x))


def main():
    t0 = time.time()
    ob.hdr("E1_I0043 s05 -- COMPONENT-WISE INJECTION (nrep=%d, ndraw=%d)" % (NREP, NDRAW))
    P("  PREREG.md sha256 %s" % ob.prereg_sha())
    m = ob.build_merged(verbose=False)
    m["_m_hat"] = m["prior5_minutes"].fillna(m["refB_mpg"])
    ssn = m["season"].to_numpy()
    dec = ob.decision_mask(m)
    need = list(dict.fromkeys(ob.BASE_B2_FAMILY + ob.CANDIDATE + ob.NEG_CONTROL
                              + ["y_ppm", "y_pts", "_m_hat"]))
    fin = ob.finite_mask(m, need)
    mask = dec & fin
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}

    packs, trm, tem = of.build_packs(v, ob.BASE_B1_HONEST, "y_ppm", mask,
                                     ob.CLEAN_EVAL_SEASONS, ssn)
    x = v["A10_opp_defrtg"]
    cell = of.FastCell(packs, of.UNFROZEN, x, trm, tem)
    obs = cell.full()["dr2"]
    P("  PRIMARY cell observed signed dR2 = %+.8f on n=%d" % (obs, cell.n))

    # components of the candidate
    bet = pd.Series(x).groupby(m["opp_team_season"].to_numpy()).transform("mean").to_numpy(float)
    wit = x - bet
    vshare_b = float(np.var(bet[mask], ddof=0) / np.var(x[mask], ddof=0))
    P("  COMPONENTS on the stratum: BETWEEN opp-team-season carries %.4f of variance, WITHIN "
      "%.4f." % (vshare_b, 1 - vshare_b))

    swap = ob.EntitySwap(m, ["opp_team_id", "season"])
    blind = ob.WithinEntityShuffle(m, ("opp_team_id", "season"))

    # verdict null on the REAL data, for the null-centre ratio
    cellv = type("C", (), {})()
    cellv.v = {"A10_opp_defrtg": x}
    cellv.dname = "A10_opp_defrtg"
    cellv.dr2 = lambda dv=None, c=cell: c.dr2(dv)
    verdict = {}
    for sname, sw in [("N_ESWAP", swap), ("N_BLIND", blind)]:
        r = ob.run_null(cellv, sw, n_draws=1000, seed=ob.SEED, label="verdict|" + sname)
        verdict[sname] = r
        P("  VERDICT-NULL CENTRE on real data  %-8s null_mean %+.8e  null_sd %.8e"
          % (sname, r["null_mean"], r["null_sd"]))

    # H0 machinery: base prediction and residual, per fold
    base_pred = [p.Xb_tr @ p.b_base for p in packs], [p.yb_te for p in packs]
    e_tr = [p.e_tr for p in packs]
    e_te = [p.y_te - p.yb_te for p in packs]
    # relabelling permutation for the residual, at the SAME level as the verdict null
    swap_tr = [ob.EntitySwap(m.loc[t].reset_index(drop=True), ["opp_team_id", "season"])
               for t in trm]
    swap_te = [ob.EntitySwap(m.loc[t].reset_index(drop=True), ["opp_team_id", "season"])
               for t in tem]

    # calibrate beta_delta on the residualised component, per fold-concatenated eval rows
    def calib(comp):
        c_te = np.concatenate([comp[t] for t in tem])
        yb = cell.yb
        Xall = np.column_stack([np.ones(len(c_te))]
                               + [np.concatenate([v[cc][t] for t in tem])
                                  for cc in ob.BASE_B1_HONEST])
        G = np.linalg.pinv(Xall.T @ Xall)
        ct = c_te - Xall @ (G @ (Xall.T @ c_te))
        return float(ct @ ct), cell.sst, yb

    rows = []
    for cname, comp in [("BETWEEN_opp_team_season", bet), ("WITHIN_opp_team_season", wit)]:
        ctct, sst, _ = calib(comp)
        for delta in DELTAS:
            beta = float(np.sqrt(delta * sst / ctct)) if ctct > 0 else 0.0
            for sname, sw in [("N_ESWAP", swap), ("N_BLIND", blind)]:
                rej, ps, nmeans, planted = 0, [], [], []
                for r in range(NREP):
                    rng = np.random.default_rng(ob.SEED + 1000 * r + hash(sname) % 97)
                    ynew = []
                    for k, p in enumerate(packs):
                        ytr = p.Xb_tr @ p.b_base + swap_tr[k].draw(e_tr[k], rng) \
                            + beta * comp[trm[k]]
                        yte = p.yb_te + swap_te[k].draw(e_te[k], rng) + beta * comp[tem[k]]
                        ynew.append((ytr, yte))
                    c2 = cell.with_response(ynew)
                    real = c2.dr2()
                    planted.append(real)
                    draws = np.empty(NDRAW)
                    for i in range(NDRAW):
                        draws[i] = c2.dr2(sw.draw(x, rng))
                    pv = (1.0 + int((draws >= real).sum())) / (NDRAW + 1.0)
                    ps.append(pv)
                    nmeans.append(float(draws.mean()))
                    rej += int(pv < ALPHA)
                power = rej / NREP
                inj_mean = float(np.mean(nmeans))
                ratio = inj_mean / verdict[sname]["null_mean"]
                rows.append(dict(component=cname, target_delta=delta, beta=beta,
                                 scheme=sname, nrep=NREP, ndraw=NDRAW,
                                 realised_planted_dr2=float(np.mean(planted)),
                                 power=power, se_power=float(np.sqrt(max(power * (1 - power), 1e-9)
                                                                     / NREP)),
                                 median_p=float(np.median(ps)),
                                 injection_null_mean=inj_mean,
                                 verdict_null_mean=verdict[sname]["null_mean"],
                                 null_centre_ratio=ratio,
                                 is_type_I=(delta == 0.0)))
                P("    %-24s delta %.4f (realised %+.6f)  %-8s  power %.3f (se %.3f)  "
                  "null-centre ratio %+.3f%s"
                  % (cname, delta, rows[-1]["realised_planted_dr2"], sname, power,
                     rows[-1]["se_power"], ratio,
                     "   <-- TYPE-I" if delta == 0.0 else ""))
    inj = pd.DataFrame(rows)
    inj.to_csv(os.path.join(ob.OUT, "INJECTION_POWER.csv"), index=False)

    ob.hdr("INJECTION-VERIFIED FLOORS AND THE VERDICT ON THE NULL")
    mdes = []
    for cname in inj.component.unique():
        for sname in inj.scheme.unique():
            q = inj[(inj.component == cname) & (inj.scheme == sname)].sort_values("target_delta")
            hit = q[q.power >= 0.80]
            if len(hit) == 0:
                mde = np.nan
                note = "power never reaches 0.80 on the grid (max %.3f at delta %.4f)" % (
                    q.power.max(), q.loc[q.power.idxmax(), "target_delta"])
            else:
                first = hit.iloc[0]
                below = q[q.target_delta < first.target_delta]
                if len(below) and below.iloc[-1].power < 0.80:
                    lo, hi = below.iloc[-1], first
                    f = (0.80 - lo.power) / max(hi.power - lo.power, 1e-9)
                    mde = float(lo.target_delta + f * (hi.target_delta - lo.target_delta))
                else:
                    mde = float(first.target_delta)
                note = "linear interpolation between bracketing grid points"
            t1 = float(q[q.target_delta == 0.0].power.iloc[0])
            mdes.append(dict(component=cname, scheme=sname, MDE80_injection_verified=mde,
                             type_I_at_alpha_0_05=t1, note=note))
            P("  %-24s %-8s  MDE80 (INJECTION-VERIFIED) %s   type-I %.3f   %s"
              % (cname, sname, ("%.6f" % mde) if np.isfinite(mde) else "NOT REACHED", t1, note))
    pd.DataFrame(mdes).to_csv(os.path.join(ob.OUT, "INJECTION_MDE.csv"), index=False)

    np.savez(os.path.join(ob.NULLS, "injection_verdict_centres.npz"),
             eswap_draws_raw_unstandardised=verdict["N_ESWAP"]["draws"],
             blind_draws_raw_unstandardised=verdict["N_BLIND"]["draws"],
             observed_signed=np.array([obs]))
    P("\n  elapsed %.1f s" % (time.time() - t0))
    with open(os.path.join(HERE, "_s05.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha=ob.prereg_sha(), observed=obs,
                       injection=json.loads(inj.to_json(orient="records")), mde=mdes), fh,
                  indent=2, default=float)
    with open(os.path.join(HERE, "run_log_s05.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(LOG))


if __name__ == "__main__":
    main()
