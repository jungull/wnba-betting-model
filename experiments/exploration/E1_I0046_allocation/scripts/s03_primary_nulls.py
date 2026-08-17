"""E1_I0046 s03 -- Q1 (is allocation forecastable at all) and Q2 (is anything left) with matched nulls."""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import al_base as A

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 200)

A.hdr("E1_I0046  --  s03  PRIMARY CELLS AND MATCHED NULLS")
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
POPS = [("DECISION", dm), ("ALL_APPEARED", allrows)]

# ==================================================== 1. Q1 -- is allocation forecastable at all
A.hdr("1. Q1 -- IS ALLOCATION FORECASTABLE AT ALL?  (no gate; forecast contrasts, not increments)")
q1 = []
for resp in A.RESPONSES:
    y = d[resp].to_numpy(float)
    naive = A.project(A.allocator_raw(d, resp, 5, 0.0), tg_code, n_tg, counts)
    unif = 1.0 / counts[tg_code].astype(float)
    tuned = BASE[resp]
    for popname, popmask in POPS:
        m = popmask & np.isin(season, A.CLEAN_EVAL_SEASONS)
        yy = y[m]
        blocks = tg_code[m]
        pairs = [("B_TUNED_vs_N_UNIFORM", tuned[m], unif[m]),
                 ("B_TUNED_vs_B_NAIVE", tuned[m], naive[m]),
                 ("B_NAIVE_vs_N_UNIFORM", naive[m], unif[m])]
        for lab, fa, fb in pairs:
            r = A.paired_signflip(yy, fa, fb, blocks, n_draws=A.N_DRAWS, seed=A.SEED)
            q1.append(dict(response=resp, population=popname, window="CLEAN_2023_24", contrast=lab,
                           n=int(m.sum()), n_blocks=r["n_blocks"],
                           r2_a=A.r2_of_forecast(yy, fa), r2_b=A.r2_of_forecast(yy, fb),
                           dr2=r["real"], null_mean=r["null_mean"], null_sd=r["null_sd"],
                           z=r["z"], p=r["p"], p_min_attainable=r["p_min_attainable"],
                           mde80_analytic=2.80 * r["null_sd"]))
            print("  %-9s %-13s %-24s n=%5d blocks=%4d  R2 %+.5f vs %+.5f  dR2 %+.6f  z=%+8.2f  p=%.4f"
                  % (resp, popname, lab, m.sum(), r["n_blocks"], q1[-1]["r2_a"], q1[-1]["r2_b"],
                     r["real"], r["z"], r["p"]))
        A.save_null("Q1__%s__%s__TUNED_vs_UNIFORM" % (resp, popname),
                    dict(label="Q1", real=q1[-3]["dr2"], draws=np.array([]), n_draws=0,
                         null_mean=q1[-3]["null_mean"], null_sd=q1[-3]["null_sd"],
                         n_groups=q1[-3]["n_blocks"], n_blocks=q1[-3]["n_blocks"]))
pd.DataFrame(q1).to_csv(os.path.join(A.OUT, "Q1_ALLOCATION_FORECASTABLE.csv"), index=False)

# ==================================================== 2. Q2 -- point estimates, every arm
A.hdr("2. Q2 -- POINT ESTIMATES.  DECISION stratum FIRST.  FROZEN and UNFROZEN, PROJ and RAW.")
cells = []
CELLOBJ = {}
for resp in A.RESPONSES:
    y = d[resp].to_numpy(float)
    b = BASE[resp]
    for popname, popmask in POPS:
        for cand in A.CANDIDATES:
            cv = d[cand].to_numpy(float)
            cv = (cv - cv.mean()) / (cv.std(ddof=1) if cv.std(ddof=1) > 0 else 1.0)
            for arm in ["FROZEN", "UNFROZEN"]:
                for proj in [True, False]:
                    c = A.Cell(d, y, b, cand, cv, allrows, popmask, A.CLEAN_EVAL_SEASONS, arm, proj)
                    r = c.full()
                    key = (resp, popname, cand, arm, "PROJ" if proj else "RAW")
                    CELLOBJ[key] = c
                    cells.append(dict(response=resp, population=popname, window="CLEAN_2023_24",
                                      candidate=cand, arm=arm,
                                      projection="PROJ" if proj else "RAW",
                                      n=r["n"], n_folds=r["n_folds"], sst=r["sst"],
                                      r2_base=r["r2_base"], r2_aug=r["r2_aug"], dr2=r["dr2"],
                                      beta=r["beta"]))
ce = pd.DataFrame(cells)
ce.to_csv(os.path.join(A.OUT, "PRIMARY_CELLS.csv"), index=False)
hl = ce[(ce.population == "DECISION") & (ce.projection == "PROJ")]
print(hl[["response", "candidate", "arm", "n", "r2_base", "dr2", "beta"]].to_string(index=False))

# ==================================================== 3. NULLS matched to the level
A.hdr("3. NULLS.  N_TGSWAP for every BETWEEN-PLAYER candidate; N_TGBLOCK for the TG-CONSTANT one.")
swap = A.WithinTeamGameSwap(d)
blk = A.WithinDateTeamGameSwap(d)
cyc = A.WithinPlayerCyclic(d)
print("  N_TGSWAP  blocks(team-games)=%d   N_TGBLOCK blocks(dates)=%d units=%d   "
      "N_WITHIN_PLAYER groups=%d" % (swap.n_blocks, blk.n_blocks, blk.n_groups, cyc.n_groups))

nulls = []
fam = []
t0 = time.time()
for resp in A.RESPONSES:
    for arm in ["FROZEN", "UNFROZEN"]:
        # ---- JOINT draw stream: ONE permutation per draw applied to ALL between-player
        # candidates simultaneously, so per-candidate p and the family-wise max-z come from the
        # same draws and the cross-candidate correlation is preserved (D120).
        objs = {c: CELLOBJ[(resp, "DECISION", c, arm, "PROJ")]
                for c in A.BETWEEN_PLAYER_CANDIDATES}
        xs = {c: objs[c].cand for c in A.BETWEEN_PLAYER_CANDIDATES}
        real = {c: float(objs[c].dr2()) for c in A.BETWEEN_PLAYER_CANDIDATES}
        draws = {c: np.empty(A.N_DRAWS) for c in A.BETWEEN_PLAYER_CANDIDATES}
        rng = np.random.default_rng(A.SEED)
        for i in range(A.N_DRAWS):
            keys = rng.random(swap.n)
            perm = np.lexsort((keys, swap.codes))
            for c in A.BETWEEN_PLAYER_CANDIDATES:
                xp = np.empty(swap.n)
                xp[swap.order] = xs[c][perm]
                draws[c][i] = objs[c].dr2(xp)
        zs = []
        for c in A.BETWEEN_PLAYER_CANDIDATES:
            dd = draws[c][np.isfinite(draws[c])]
            mu, sd = float(dd.mean()), float(dd.std(ddof=1))
            z = (real[c] - mu) / sd if sd > 0 else np.nan
            p = float((1.0 + int((dd >= real[c]).sum())) / (len(dd) + 1.0))
            if c in A.REAL_CANDIDATES:
                zs.append((real[c] - mu) / sd if sd > 0 else np.nan)
            nulls.append(dict(response=resp, population="DECISION", window="CLEAN_2023_24",
                              candidate=c, arm=arm, projection="PROJ", null="N_TGSWAP",
                              n_blocks=swap.n_blocks, n_groups=swap.n_groups,
                              observed=real[c], null_mean=mu, null_sd=sd, z=z, p=p,
                              mde80_analytic=2.80 * sd,
                              null_absorbs=bool(np.sign(mu) == np.sign(real[c]) and
                                                abs(mu) > 0.25 * abs(real[c]))))
            A.save_null("%s__DECISION__%s__PROJ__%s__N_TGSWAP" % (resp, arm, c),
                        dict(label="%s|%s|%s" % (resp, arm, c), real=real[c], draws=draws[c],
                             n_draws=A.N_DRAWS, null_mean=mu, null_sd=sd,
                             n_groups=swap.n_groups, n_blocks=swap.n_blocks))
            print("  %-9s %-9s %-22s N_TGSWAP  obs %+.6f  null mu %+.6f sd %.6f  z %+7.3f  p %.4f"
                  % (resp, arm, c, real[c], mu, sd, z, p))
        # family-wise max-z over the 4 real between-player candidates, same draws
        M = np.column_stack([draws[c] for c in A.BETWEEN_PLAYER_CANDIDATES if c in A.REAL_CANDIDATES])
        mus = M.mean(0)
        sds = M.std(0, ddof=1)
        Z = (M - mus) / np.where(sds > 0, sds, 1.0)
        maxz_draws = Z.max(1)
        obs_maxz = float(np.nanmax(zs))
        pfam = float((1.0 + int((maxz_draws >= obs_maxz).sum())) / (len(maxz_draws) + 1.0))
        fam.append(dict(response=resp, arm=arm, family="4 between-player real candidates",
                        observed_max_z=obs_maxz, p_familywise=pfam,
                        crit_z_95=float(np.quantile(maxz_draws, 0.95))))
        print("    FAMILY-WISE (max-z over 4 real between-player candidates): obs max z %+.3f  "
              "p_fw %.4f  crit z(95%%) %+.3f" % (obs_maxz, pfam, fam[-1]["crit_z_95"]))
        A.save_null("FAMILYWISE__%s__%s" % (resp, arm),
                    dict(label="famwise", real=obs_maxz, draws=maxz_draws, n_draws=A.N_DRAWS,
                         null_mean=float(maxz_draws.mean()), null_sd=float(maxz_draws.std(ddof=1)),
                         n_groups=swap.n_groups, n_blocks=swap.n_blocks))
print("  [joint N_TGSWAP nulls done in %.1f s]" % (time.time() - t0))

# ---- A5: the team-game-CONSTANT candidate.  Its verdict null is N_TGBLOCK.  N_TGSWAP is run
# beside it to DEMONSTRATE that a within-composition swap is the literal identity for it.
A.hdr("4. A5_opp_defrtg -- a TEAM-GAME-CONSTANT candidate.  Two nulls, one of which cannot fail.")
for resp in A.RESPONSES:
    for arm in ["FROZEN", "UNFROZEN"]:
        c = CELLOBJ[(resp, "DECISION", "A5_opp_defrtg", arm, "PROJ")]
        for nlab, sw in [("N_TGBLOCK", blk), ("N_TGSWAP_VACUOUS_CONTROL", swap)]:
            r = A.run_null(c, sw, n_draws=(A.N_DRAWS if nlab == "N_TGBLOCK" else 200),
                           seed=A.SEED, label="%s|%s|A5|%s" % (resp, arm, nlab))
            nulls.append(dict(response=resp, population="DECISION", window="CLEAN_2023_24",
                              candidate="A5_opp_defrtg", arm=arm, projection="PROJ", null=nlab,
                              n_blocks=r["n_blocks"], n_groups=r["n_groups"], observed=r["real"],
                              null_mean=r["null_mean"], null_sd=r["null_sd"], z=r["z"], p=r["p"],
                              mde80_analytic=2.80 * r["null_sd"],
                              null_absorbs=bool(np.sign(r["null_mean"]) == np.sign(r["real"]) and
                                                abs(r["null_mean"]) > 0.25 * abs(r["real"]))))
            A.save_null("%s__DECISION__%s__PROJ__A5_opp_defrtg__%s" % (resp, arm, nlab), r)
            print("  %-9s %-9s A5 %-26s obs %+.6f  null mu %+.6f sd %.3e  z %+8.3f  p %.4f"
                  % (resp, arm, nlab, r["real"], r["null_mean"], r["null_sd"], r["z"], r["p"]))

# ---- the blindness demonstration, on this screen's own candidate
A.hdr("5. BLIND-NULL DEMONSTRATION -- a within-PLAYER null against a between-PLAYER candidate")
blind = []
for cand in ["A1_min_share_prior", "A2_fga_share_prior"]:
    c = CELLOBJ[("R1_s_pts", "DECISION", cand, "FROZEN", "PROJ")]
    for nlab, sw, nd in [("N_TGSWAP_CORRECT", swap, 500), ("N_WITHIN_PLAYER_BLIND", cyc, 500)]:
        r = A.run_null(c, sw, n_draws=nd, seed=A.SEED, label="blind|%s|%s" % (cand, nlab))
        blind.append(dict(candidate=cand, null=nlab, n_draws=nd, observed=r["real"],
                          null_mean=r["null_mean"], null_sd=r["null_sd"], z=r["z"], p=r["p"],
                          n_groups=r["n_groups"]))
        A.save_null("BLINDDEMO__R1_s_pts__%s__%s" % (cand, nlab), r)
        print("  %-22s %-24s obs %+.6f null mu %+.6f sd %.6f  z %+7.3f  p %.4f"
              % (cand, nlab, r["real"], r["null_mean"], r["null_sd"], r["z"], r["p"]))
pd.DataFrame(blind).to_csv(os.path.join(A.OUT, "BLIND_NULL_DEMO.csv"), index=False)

nu = pd.DataFrame(nulls)
nu.to_csv(os.path.join(A.OUT, "NULLS.csv"), index=False)
pd.DataFrame(fam).to_csv(os.path.join(A.OUT, "FAMILYWISE.csv"), index=False)
A.dump("s03", dict(prereg_sha=A.prereg_sha(), q1=q1, cells=cells, nulls=nulls, family=fam,
                   blind=blind))
print("\n  s03 OK.")
