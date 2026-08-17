"""s04 -- THE PRIMARY CELLS.  Every cell in BOTH arms, with a null matched to its level.

Grids, all preregistered in PREREG.md section 8:
  PRIMARY     R1_min  RAW   FROZEN+UNFROZEN  10 candidates
  CONSTRAINT  R1_min  PROJ  FROZEN+UNFROZEN  10 candidates
  SHARE       R2_smin PROJ  FROZEN+UNFROZEN  10 candidates
  COMPONENT   R1_min  RAW   FROZEN+UNFROZEN  __W and __B of 5 within-tg candidates + G01_noise
"""
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s04 PRIMARY   PREREG sha256 %s" % A.prereg_sha())
d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "cached frame", verbose=True)
Z = np.load(os.path.join(A.SCR, "_base.npz"), allow_pickle=True)
season = d["season"].to_numpy()
dm = A.decision_mask(d)
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg).astype(float)
T_min_tg = np.bincount(tg_code, weights=d["T_min"].to_numpy(float), minlength=n_tg) / counts
PROJ_TOT = {"R1_min": T_min_tg, "R2_smin": np.ones(n_tg)}
Y = {r: d[r].to_numpy(float) for r in A.RESPONSES}

COMP = {}
for c in A.WITHIN_TG_CANDIDATES + ["G01_noise"]:
    x = d[c].to_numpy(float)
    gm = (np.bincount(tg_code, weights=x, minlength=n_tg) / counts)[tg_code]
    COMP[c + "__W"] = x - gm
    COMP[c + "__B"] = gm
COL = {c: d[c].to_numpy(float) for c in A.CANDIDATES}
COL.update(COMP)

WITHIN_SET = set(A.WITHIN_TG_CANDIDATES + ["G01_noise"] +
                 [c + "__W" for c in A.WITHIN_TG_CANDIDATES + ["G01_noise"]])
TGC_SET = set(A.TG_CONSTANT_CANDIDATES + ["G02_tg_noise"] +
              [c + "__B" for c in A.WITHIN_TG_CANDIDATES + ["G01_noise"]])

SW_TG = A.WithinTeamGameSwap(d)
SW_BLK = A.WithinDateTeamGameSwap(d)
SW_PS = A.PlayerSeriesSwap(d)
print("  swappers: N_TGSWAP blocks=%d  N_TGBLOCK blocks=%d  N_PSWAP groups=%d blocks=%d"
      % (SW_TG.n_blocks, SW_BLK.n_blocks, SW_PS.n_groups, SW_PS.n_blocks))

N_PSWAP_DRAWS = 600
BOOT = 2000

GRIDS = [("PRIMARY", "R1_min", "RAW", A.CANDIDATES),
         ("CONSTRAINT", "R1_min", "PROJ", A.CANDIDATES),
         ("SHARE", "R2_smin", "PROJ", A.CANDIDATES),
         ("COMPONENT", "R1_min", "RAW", sorted(COMP.keys()))]


def make_cell(resp, pm, cname, arm, evals):
    return A.Cell(d, Y[resp], Z["%s|%s" % (resp, pm)], cname, COL[cname], dm, dm, evals, arm, pm,
                  proj_totals=PROJ_TOT[resp])


def bootstrap_dr2(full, blocks, n=BOOT, seed=A.SEED):
    """Block bootstrap over the scored team-game blocks.  A SECOND variance estimate, not the
    permutation null: it asks whether the NUMBER would replicate, not whether assignment matters."""
    y, yb, ya = full["y"], full["yb"], full["ya"]
    codes = pd.factorize(blocks, sort=True)[0]
    nb = int(codes.max()) + 1
    idx_by = [np.flatnonzero(codes == b) for b in range(nb)]
    rng = np.random.default_rng(seed)
    out = np.empty(n, float)
    for i in range(n):
        pick = rng.integers(0, nb, nb)
        sel = np.concatenate([idx_by[b] for b in pick])
        yy = y[sel]
        sst = float(((yy - yy.mean()) ** 2).sum())
        out[i] = (float(((yy - yb[sel]) ** 2).sum()) - float(((yy - ya[sel]) ** 2).sum())) / sst
    return out


rows = []
t0 = time.time()
for gname, resp, pm, cands in GRIDS:
    A.hdr("GRID %s   response %s   projection %s   %d candidates" % (gname, resp, pm, len(cands)))
    for arm in ["FROZEN", "UNFROZEN"]:
        cells = {c: make_cell(resp, pm, c, arm, A.CLEAN_EVAL_SEASONS) for c in cands}
        w_names = [c for c in cands if c in WITHIN_SET]
        t_names = [c for c in cands if c in TGC_SET]
        res = {}
        if w_names:
            res.update(A.run_null_family({k: cells[k] for k in w_names}, SW_TG, A.N_DRAWS, A.SEED,
                                         "%s|%s|%s|N_TGSWAP" % (resp, pm, arm)))
        if t_names:
            res.update(A.run_null_family({k: cells[k] for k in t_names}, SW_BLK, A.N_DRAWS, A.SEED,
                                         "%s|%s|%s|N_TGBLOCK" % (resp, pm, arm)))
        # second required null for the within-team-game family
        res2 = A.run_null_family({k: cells[k] for k in w_names}, SW_PS, N_PSWAP_DRAWS, A.SEED,
                                 "%s|%s|%s|N_PSWAP" % (resp, pm, arm)) if w_names else {}
        # the vacuous control: N_TGSWAP is the LITERAL IDENTITY for a tg-constant column
        res3 = A.run_null_family({k: cells[k] for k in t_names}, SW_TG, 200, A.SEED,
                                 "%s|%s|%s|N_TGSWAP_VACUOUS" % (resp, pm, arm)) if t_names else {}
        fw_w = A.familywise_from_stream(res, [c for c in w_names if c in A.REAL_CANDIDATES or
                                              c.split("__")[0] in A.WITHIN_TG_CANDIDATES])
        fw_t = A.familywise_from_stream(res, [c for c in t_names if c in A.REAL_CANDIDATES or
                                              c.split("__")[0] in A.WITHIN_TG_CANDIDATES])
        for c in cands:
            full = cells[c].full()
            prim = res[c]
            nulln = "N_TGSWAP" if c in WITHIN_SET else "N_TGBLOCK"
            sec = res2.get(c) or res3.get(c)
            secn = "N_PSWAP" if c in WITHIN_SET else "N_TGSWAP_VACUOUS_IDENTITY"
            blocks = d.loc[full["idx"], "tg"].to_numpy()
            bs = bootstrap_dr2(full, blocks)
            per = {}
            for es in [2023, 2024, 2022]:
                cc = make_cell(resp, pm, c, arm, [es])
                f = cc.full()
                per["dr2_eval_%d" % es] = np.nan if f is None else f["dr2"]
            rows.append(dict(
                grid=gname, response=resp, projection=pm, arm=arm, candidate=c,
                stratum="DECISION", window="CLEAN_2023_24", n=full["n"],
                n_blocks_scored=int(pd.Series(blocks).nunique()), sst=full["sst"],
                r2_base=full["r2_base"], r2_aug=full["r2_aug"], dR2=full["dr2"],
                beta=full["beta"],
                primary_null=nulln, null_mean=prim["null_mean"], null_sd=prim["null_sd"],
                z=prim["z"], p=prim["p"], n_null_blocks=prim["n_blocks"],
                n_draws=prim["n_draws"],
                p_floor=1.0 / (prim["n_finite"] + 1.0),
                second_null=secn,
                null_mean_2=(sec or {}).get("null_mean", np.nan),
                null_sd_2=(sec or {}).get("null_sd", np.nan),
                z_2=(sec or {}).get("z", np.nan), p_2=(sec or {}).get("p", np.nan),
                n_draws_2=(sec or {}).get("n_draws", 0),
                p_familywise=fw_w.get(c, fw_t.get(c, np.nan)),
                MDE80_analytic=2.80 * prim["null_sd"],
                boot_sd=float(bs.std(ddof=1)), boot_t=full["dr2"] / float(bs.std(ddof=1)),
                boot_MDE80=2.80 * float(bs.std(ddof=1)),
                boot_over_perm_sd=float(bs.std(ddof=1)) / prim["null_sd"]
                if prim["null_sd"] > 0 else np.nan,
                **per))
            key = "%s__%s__%s__%s__DECISION_CLEAN" % (resp, pm, arm, c)
            A.save_null(key + "__" + nulln, prim,
                        dict(response=np.array([resp]), projection=np.array([pm]),
                             arm=np.array([arm]), candidate=np.array([c]),
                             stratum=np.array(["DECISION"]), window=np.array(["CLEAN_2023_24"]),
                             n_rows=np.array([full["n"]]),
                             n_scored_blocks=np.array([int(pd.Series(blocks).nunique())])))
            if sec is not None:
                A.save_null(key + "__" + secn, sec,
                            dict(response=np.array([resp]), projection=np.array([pm]),
                                 arm=np.array([arm]), candidate=np.array([c]),
                                 stratum=np.array(["DECISION"]),
                                 window=np.array(["CLEAN_2023_24"])))
            np.savez(os.path.join(A.NULLS, key + "__BOOTSTRAP.npz"),
                     draws_raw_unstandardised=bs, observed_signed=np.array([full["dr2"]]),
                     n_blocks=np.array([int(pd.Series(blocks).nunique())]),
                     label=np.array([key + "|block_bootstrap"]))
            print("  %-10s %-8s %-4s %-9s %-20s dR2 %+10.6f  %s z %+7.2f p %.4f | %s z %+7.2f "
                  "p %.4f | fw %.4f | boot sd %.6f (%.2fx)"
                  % (gname, resp, pm, arm, c, full["dr2"], nulln, prim["z"], prim["p"], secn,
                     (sec or {}).get("z", np.nan), (sec or {}).get("p", np.nan),
                     rows[-1]["p_familywise"], rows[-1]["boot_sd"],
                     rows[-1]["boot_over_perm_sd"]))
    print("  ... elapsed %.1f s" % (time.time() - t0))

P = pd.DataFrame(rows)
P.to_csv(os.path.join(A.OUT, "PRIMARY_CELLS.csv"), index=False)
A.dump("s04", dict(prereg_sha=A.prereg_sha(), n_cells=len(P),
                   elapsed_s=time.time() - t0))
A.hdr("s04 done -- %d cells -> PRIMARY_CELLS.csv   (%.1f s)" % (len(P), time.time() - t0))
