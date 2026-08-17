"""s02 -- THE REFERENCE, TUNED HONESTLY, AND WHAT THE TUNING ALONE IS WORTH.

Nothing about any candidate is touched here.  This step exists because D094's headline was
withdrawn for testing against a weak benchmark and E1_I0046 found the tuning worth more than any
candidate it tested.  The tuning is held to the SAME bar as a candidate: a paired cluster
sign-flip over team-game blocks.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s02 REFERENCE   PREREG sha256 %s" % A.prereg_sha())
d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "cached frame", verbose=True)
season = d["season"].to_numpy()
dm = A.decision_mask(d)
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg).astype(float)
T_min_tg = np.bincount(tg_code, weights=d["T_min"].to_numpy(float), minlength=n_tg) / counts
ones = np.ones(n_tg)
EVALS = A.CLEAN_EVAL_SEASONS + A.DISCLOSED_EVAL_SEASONS

Y = {r: d[r].to_numpy(float) for r in A.RESPONSES}
PROJ_TOT = {"R1_min": T_min_tg, "R2_smin": ones}

rows = []
BASE = {}          # (resp, projmode) -> walk-forward tuned base column over eval rows
BENCH = {}         # (resp, projmode, name) -> walk-forward forecast column

for resp in A.RESPONSES:
    y = Y[resp]
    tot = PROJ_TOT[resp]
    for pm in ["RAW", "PROJ"]:
        b_t = np.full(len(d), np.nan)
        b_n = np.full(len(d), np.nan)
        b_5 = np.full(len(d), np.nan)
        b_u = np.full(len(d), np.nan)
        for es in EVALS:
            tr = dm & (season < es)
            if tr.sum() < 300:
                continue
            best = None
            for h in A.H_GRID:
                for kk in A.K_GRID:
                    raw = A.allocator_raw(d, resp, h, kk)
                    f = raw if pm == "RAW" else A.project_to_total(raw, tg_code, n_tg, counts, tot)
                    sse = float(((y[tr] - f[tr]) ** 2).sum())
                    if best is None or sse < best[0]:
                        best = (sse, h, kk, f)
            sse, h, kk, f = best

            def wrap(v):
                return v if pm == "RAW" else A.project_to_total(v, tg_code, n_tg, counts, tot)

            naive = wrap(A.allocator_raw(d, resp, 5, 0.0))
            trail5 = wrap(A.trailing5_mean_ref(d, resp))
            unif = (A.shrink_target(d, resp) if pm == "RAW" else tot[tg_code] / counts[tg_code])
            te = (season == es)
            b_t[te], b_n[te], b_5[te], b_u[te] = f[te], naive[te], trail5[te], unif[te]
            sc = dm & te
            rows.append(dict(response=resp, projection=pm, eval_season=int(es),
                             n_train_rows=int(tr.sum()), n_eval_rows=int(sc.sum()),
                             selected_h=("EXPANDING" if h == 0 else h), selected_k=kk,
                             train_sse=sse,
                             r2_tuned=A.r2_of_forecast(y[sc], f[sc]),
                             r2_naive=A.r2_of_forecast(y[sc], naive[sc]),
                             r2_trail5=A.r2_of_forecast(y[sc], trail5[sc]),
                             r2_uniform=A.r2_of_forecast(y[sc], unif[sc])))
            print("  %-8s %-4s eval %d  train=%5d  h=%-9s k=%-4s | R2 tuned %+.6f  naive %+.6f  "
                  "trail5 %+.6f  uniform %+.6f"
                  % (resp, pm, es, tr.sum(), rows[-1]["selected_h"], kk, rows[-1]["r2_tuned"],
                     rows[-1]["r2_naive"], rows[-1]["r2_trail5"], rows[-1]["r2_uniform"]))
        # Training rows need a base column too.  Fill them with the EARLIEST-eval-season allocator
        # (tuned on <= 2022 rows only), exactly as E1_I0046/s02 does.  No eval row informs it.
        first = np.full(len(d), np.nan)
        tr0 = dm & (season < A.CLEAN_EVAL_SEASONS[0])
        best0 = None
        for h in A.H_GRID:
            for kk in A.K_GRID:
                raw = A.allocator_raw(d, resp, h, kk)
                f0 = raw if pm == "RAW" else A.project_to_total(raw, tg_code, n_tg, counts, tot)
                s0 = float(((y[tr0] - f0[tr0]) ** 2).sum())
                if best0 is None or s0 < best0[0]:
                    best0 = (s0, f0)
        first = best0[1]
        b_t = np.where(np.isfinite(b_t), b_t, first)
        BASE[(resp, pm)] = b_t
        BENCH[(resp, pm, "NAIVE")] = b_n
        BENCH[(resp, pm, "TRAIL5")] = b_5
        BENCH[(resp, pm, "UNIFORM")] = b_u

pd.DataFrame(rows).to_csv(os.path.join(A.OUT, "REFERENCE_TUNING.csv"), index=False)

# ------------------------------------------------------------------ WHAT THE TUNING IS WORTH
A.hdr("WHAT THE TUNING ALONE IS WORTH -- paired cluster sign-flip, blocks = team-games")
clean = np.isin(season, A.CLEAN_EVAL_SEASONS)
disc = np.isin(season, A.DISCLOSED_EVAL_SEASONS)
worth = []
for resp in A.RESPONSES:
    y = Y[resp]
    for pm in ["RAW", "PROJ"]:
        for popname, pop in [("DECISION_CLEAN_2023_24", dm & clean),
                             ("DECISION_DISCLOSED_2022", dm & disc),
                             ("ALL_APPEARED_CLEAN_2023_24", clean)]:
            b = BASE[(resp, pm)]
            m = pop & np.isfinite(b)
            for bn in ["NAIVE", "TRAIL5", "UNIFORM"]:
                o = BENCH[(resp, pm, bn)]
                mm = m & np.isfinite(o)
                res = A.paired_signflip(y[mm], b[mm], o[mm], d.loc[mm, "tg"].to_numpy(),
                                        n_draws=A.N_DRAWS, seed=A.SEED)
                worth.append(dict(response=resp, projection=pm, population=popname,
                                  benchmark=bn, n=int(mm.sum()),
                                  n_blocks=res["n_blocks"],
                                  r2_tuned=A.r2_of_forecast(y[mm], b[mm]),
                                  r2_benchmark=A.r2_of_forecast(y[mm], o[mm]),
                                  dR2_tuned_minus_benchmark=res["real"],
                                  null_sd=res["null_sd"], z=res["z"], p=res["p"],
                                  p_min_attainable=res["p_min_attainable"],
                                  MDE80_analytic=2.80 * res["null_sd"]))
                if popname == "DECISION_CLEAN_2023_24":
                    A.save_null("REF__%s__%s__DECISION_CLEAN__TUNED_vs_%s" % (resp, pm, bn),
                                dict(label="REF %s %s TUNED-%s" % (resp, pm, bn), real=res["real"],
                                     draws=res["draws"], null_mean=res["null_mean"],
                                     null_sd=res["null_sd"], n_groups=res["n_blocks"],
                                     n_blocks=res["n_blocks"], n_draws=A.N_DRAWS),
                                dict(population=np.array(["DECISION_CLEAN_2023_24"]),
                                     n_rows=np.array([int(mm.sum())])))
                print("  %-8s %-4s %-26s vs %-8s n=%5d blk=%4d  dR2 %+10.6f  z %+8.2f  p %.4f"
                      % (resp, pm, popname, bn, mm.sum(), res["n_blocks"], res["real"], res["z"],
                         res["p"]))
W = pd.DataFrame(worth)
W.to_csv(os.path.join(A.OUT, "REFERENCE_WORTH.csv"), index=False)

np.savez(os.path.join(A.SCR, "_base.npz"),
         **{"%s|%s" % (k[0], k[1]): v for k, v in BASE.items()},
         **{"BENCH|%s|%s|%s" % k: v for k, v in BENCH.items()})
A.dump("s02", dict(prereg_sha=A.prereg_sha(), n_tuning_rows=len(rows), n_worth_rows=len(worth)))
A.hdr("s02 done")
