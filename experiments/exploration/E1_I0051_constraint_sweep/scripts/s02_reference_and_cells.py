"""E1_I0051 -- s02.  Tuned reference (strictly earlier seasons), arithmetic ceiling, primary cells.

Every cell states, in the CSV: response, row set, SST basis, weighting, base, arm, projection arm.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_base as B  # noqa: E402

pd.set_option("display.width", 240)

d = pd.read_parquet(os.path.join(B.SCR, "_frame.parquet"))
B.assert_partition(d, "FRAME_reload", True)
dm = B.decision_mask(d)
season = d["season"].to_numpy()
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg)
B_live = d["B_live"].to_numpy(float)
B_rules = d["B_rules"].to_numpy(float)
T_real = d["T_min"].to_numpy(float)

B.hdr("s02  PREREG sha256 %s" % B.prereg_sha())
print("  frame %d rows / %d team-games   decision stratum %d   clean-window decision %d"
      % (len(d), n_tg, int(dm.sum()),
         int((dm & np.isin(season, B.CLEAN_EVAL_SEASONS)).sum())))

# =============================================================================================
B.hdr("1. TUNED REFERENCE -- (h, k) chosen on STRICTLY EARLIER seasons only, per eval season")


def score_reference(resp, h, k, eval_season, proj, row_mask):
    """R2 of the shrunken prior-EWMA allocator on `eval_season`, scored on `row_mask` rows."""
    f = B.allocator_raw(d, resp, h, k)
    te = (season == eval_season)
    if proj == "RAW":
        fh = f[te]
    else:
        tgt = B_live[te] if proj == "PROJ_BUDGET" else T_real[te]
        if resp == "S_share_min":
            tgt = np.ones(int(te.sum())) if proj == "PROJ_BUDGET" else np.ones(int(te.sum()))
        fh = B.project_to(f[te], tg_code[te], n_tg, counts, tgt)
    keep = row_mask[te]
    y = d[resp].to_numpy(float)[te][keep]
    return B.r2_of_forecast(y, fh[keep])


tune_rows = []
CHOSEN = {}
for resp in B.RESPONSES:
    for ev in B.CLEAN_EVAL_SEASONS + B.DISCLOSED_EVAL_SEASONS:
        prior = [s for s in sorted(B.ALLOWED_SEASONS) if s < ev]
        if not prior:
            continue
        best = None
        for h in B.H_GRID:
            for k in B.K_GRID:
                # SELECTION SCORE: on the LAST strictly-earlier season only, decision stratum,
                # RAW arm.  Selecting on RAW so the projection cannot be tuned into the reference.
                sel = score_reference(resp, h, k, prior[-1], "RAW", dm)
                tune_rows.append(dict(response=resp, eval_season=ev, select_on=prior[-1],
                                      h=h, k=k, select_r2=sel))
                if best is None or sel > best[0]:
                    best = (sel, h, k)
        CHOSEN[(resp, ev)] = (best[1], best[2])
        print("  %-14s eval %d  selected on %d  ->  h=%-2d k=%-4s  (selection R2 %+.6f)"
              % (resp, ev, prior[-1], best[1], str(best[2]), best[0]))
pd.DataFrame(tune_rows).to_csv(os.path.join(B.OUT, "REFERENCE_TUNING.csv"), index=False)


def base_column(resp, ev):
    h, k = CHOSEN[(resp, ev)]
    return B.allocator_raw(d, resp, h, k)


# =============================================================================================
B.hdr("2. Q1 -- IS THE FORECAST ANY GOOD, AND WHAT DOES THE PROJECTION DO TO IT ALONE?")
print("""  response / row set / SST basis are stated on every row.  No number here is compared to a
  number on a different response.""")
q1 = []
for resp in B.RESPONSES:
    for pop, mask, plab in (("DECISION", dm, "n_prior>=8 & prior5_minutes>=24"),
                            ("ALL_APPEARED", np.ones(len(d), bool), "all appeared")):
        for proj in B.ARMS_PROJ:
            ys, fs, nb = [], [], []
            for ev in B.CLEAN_EVAL_SEASONS:
                h, k = CHOSEN[(resp, ev)]
                f = B.allocator_raw(d, resp, h, k)
                te = (season == ev)
                if proj == "RAW":
                    fh = f[te]
                else:
                    if resp == "S_share_min":
                        tgt = np.ones(int(te.sum()))
                    else:
                        tgt = B_live[te] if proj == "PROJ_BUDGET" else T_real[te]
                    fh = B.project_to(f[te], tg_code[te], n_tg, counts, tgt)
                keep = mask[te]
                ys.append(d[resp].to_numpy(float)[te][keep])
                fs.append(fh[keep])
                nb.append(tg_code[te][keep])
            y = np.concatenate(ys)
            fh = np.concatenate(fs)
            blocks = np.concatenate(nb)
            q1.append(dict(response=resp, population=pop, row_set=plab, projection=proj,
                           n=len(y), n_blocks=int(pd.unique(blocks).size),
                           sst=float(((y - y.mean()) ** 2).sum()),
                           r2=B.r2_of_forecast(y, fh),
                           mae=float(np.abs(y - fh).mean()),
                           mean_tg_sum=float(pd.Series(fh).groupby(blocks).sum().mean())))
q1 = pd.DataFrame(q1)
print(q1.to_string(index=False, float_format=lambda x: "%.6f" % x))
q1.to_csv(os.path.join(B.OUT, "Q1_PROJECTION_EFFECT.csv"), index=False)

# ---- the paired sign-flip on the projection itself -------------------------------------------
B.hdr("2b. IS THE PROJECTION ITSELF AN IMPROVEMENT?  paired sign-flip, blocks = team-games")
sf_rows = []
for resp in B.RESPONSES:
    for pop, mask in (("DECISION", dm), ("ALL_APPEARED", np.ones(len(d), bool))):
        store = {}
        for proj in B.ARMS_PROJ:
            ys, fs, bs = [], [], []
            for ev in B.CLEAN_EVAL_SEASONS:
                h, k = CHOSEN[(resp, ev)]
                f = B.allocator_raw(d, resp, h, k)
                te = (season == ev)
                if proj == "RAW":
                    fh = f[te]
                else:
                    if resp == "S_share_min":
                        tgt = np.ones(int(te.sum()))
                    else:
                        tgt = B_live[te] if proj == "PROJ_BUDGET" else T_real[te]
                    fh = B.project_to(f[te], tg_code[te], n_tg, counts, tgt)
                keep = mask[te]
                ys.append(d[resp].to_numpy(float)[te][keep])
                fs.append(fh[keep])
                bs.append(tg_code[te][keep])
            store[proj] = (np.concatenate(ys), np.concatenate(fs), np.concatenate(bs))
        y, _, blk = store["RAW"]
        for a in ("PROJ_BUDGET", "PROJ_ORACLE"):
            r = B.paired_signflip(y, store[a][1], store["RAW"][1], blk)
            sf_rows.append(dict(response=resp, population=pop, contrast="%s vs RAW" % a,
                                n=len(y), dr2=r["real"], z=r["z"], p=r["p"],
                                n_blocks=r["n_blocks"], null_sd=r["null_sd"],
                                null_mean=r["null_mean"], p_min_attainable=r["p_min_attainable"]))
            print("  %-12s %-13s %-22s dR2 %+.6f  z %+8.2f  p %.4f  blocks %d"
                  % (resp, pop, "%s vs RAW" % a, r["real"], r["z"], r["p"], r["n_blocks"]))
pd.DataFrame(sf_rows).to_csv(os.path.join(B.OUT, "PROJECTION_SIGNFLIP.csv"), index=False)

# =============================================================================================
B.hdr("3. ARITHMETIC CEILING -- computed BEFORE any candidate null")
ceil_rows = []
for resp in B.RESPONSES:
    for proj in B.ARMS_PROJ:
        # base walk-forward eval residual on the decision stratum, clean window
        es, ds_ = [], {c: [] for c in B.CANDIDATES}
        for ev in B.CLEAN_EVAL_SEASONS:
            h, k = CHOSEN[(resp, ev)]
            f = B.allocator_raw(d, resp, h, k)
            tr = dm & (season < ev)
            te = (season == ev)
            Xb_tr = np.column_stack([np.ones(int(tr.sum())), f[tr]])
            Xb_te = np.column_stack([np.ones(int(te.sum())), f[te]])
            bb = B.ols(Xb_tr, d[resp].to_numpy(float)[tr])
            fb = Xb_te @ bb
            if proj != "RAW":
                if resp == "S_share_min":
                    tgt = np.ones(int(te.sum()))
                else:
                    tgt = B_live[te] if proj == "PROJ_BUDGET" else T_real[te]
                fb = B.project_to(fb, tg_code[te], n_tg, counts, tgt)
            keep = dm[te]
            y = d[resp].to_numpy(float)[te][keep]
            es.append(y - fb[keep])
            for c in B.CANDIDATES:
                x = d[c].to_numpy(float)[te][keep]
                ds_[c].append(x)
        e = np.concatenate(es)
        sst = float(((np.concatenate([d[resp].to_numpy(float)[(season == ev)][dm[(season == ev)]]
                                      for ev in B.CLEAN_EVAL_SEASONS]) -
                      np.concatenate([d[resp].to_numpy(float)[(season == ev)][dm[(season == ev)]]
                                      for ev in B.CLEAN_EVAL_SEASONS]).mean()) ** 2).sum())
        base_r2 = 1.0 - float((e ** 2).sum()) / sst
        for c in B.CANDIDATES:
            x = np.concatenate(ds_[c])
            x = (x - x.mean()) / (x.std(ddof=1) if x.std(ddof=1) > 0 else 1.0)
            # residualise on [1] only -- the base is already in e
            dd_ = x - x.mean()
            num = float(dd_ @ e) ** 2
            den = float(dd_ @ dd_) * sst
            ceil_rows.append(dict(response=resp, projection=proj, candidate=c,
                                  row_set="DECISION x CLEAN_2023_24", n=len(e), sst=sst,
                                  base_r2=base_r2, oracle_dr2=num / den if den > 0 else np.nan,
                                  x_floor_single_cell=(num / den) / B.FLOOR_SINGLE_CELL
                                  if den > 0 else np.nan))
ce = pd.DataFrame(ceil_rows)
print(ce.pivot_table(index=["response", "candidate"], columns="projection", values="oracle_dr2"
                     ).to_string(float_format=lambda x: "%.6f" % x))
ce.to_csv(os.path.join(B.OUT, "CEILING.csv"), index=False)

# =============================================================================================
B.hdr("4. PRIMARY CELLS -- response x candidate x arm x projection.  THE SIGN IS THE POINT.")
cells = []
for resp in B.RESPONSES:
    for ev_set, wlab in ((B.CLEAN_EVAL_SEASONS, "CLEAN_2023_24"),
                         (B.DISCLOSED_EVAL_SEASONS, "DISCLOSED_2022")):
        for pop, mask in (("DECISION", dm), ("ALL_APPEARED", np.ones(len(d), bool))):
            for ev in ev_set:
                pass
            base = np.zeros(len(d))
            # per-eval-season base is handled inside Cell via a single column; build the union
            # column by writing each eval season's own tuned base into its own rows and the
            # LAST-EARLIER season's tuning into the training rows (which is what walk-forward
            # selection means).  Training rows use the same (h,k) as the eval fold they serve.
            for ev in ev_set:
                h, k = CHOSEN[(resp, ev)]
                f = B.allocator_raw(d, resp, h, k)
                base = np.where((season == ev) | (season < ev), f, base)
            for c in B.CANDIDATES:
                for arm in ("FROZEN", "UNFROZEN"):
                    for proj in B.ARMS_PROJ:
                        cell = B.Cell(d, d[resp].to_numpy(float), base, c,
                                      d[c].to_numpy(float), mask, mask, ev_set, arm, proj,
                                      B_rules, B_live if resp == "M_level_min"
                                      else np.ones(len(d)),
                                      T_real if resp == "M_level_min" else np.ones(len(d)))
                        r = cell.full()
                        if r is None:
                            continue
                        cells.append(dict(response=resp, window=wlab, population=pop,
                                          row_set=("n_prior>=8 & prior5_minutes>=24"
                                                   if pop == "DECISION" else "all appeared"),
                                          candidate=c, arm=arm, projection=proj,
                                          weighting="none", base="B_TUNED (h,k) walk-forward",
                                          n=r["n"], n_folds=r["n_folds"], sst=r["sst"],
                                          r2_base=r["r2_base"], r2_aug=r["r2_aug"],
                                          dr2=r["dr2"], beta=r["beta"],
                                          sign=("+" if r["dr2"] > 0 else
                                                ("-" if r["dr2"] < 0 else "0"))))
pc = pd.DataFrame(cells)
pc.to_csv(os.path.join(B.OUT, "PRIMARY_CELLS.csv"), index=False)

prim = pc[(pc["response"] == "M_level_min") & (pc["window"] == "CLEAN_2023_24") &
          (pc["population"] == "DECISION")]
print("\nPRIMARY: response M_level_min | DECISION | CLEAN_2023_24 | SST on scored rows | no weights")
print(prim.pivot_table(index=["candidate", "arm"], columns="projection", values="dr2"
                       )[B.ARMS_PROJ].to_string(float_format=lambda x: "%+.6f" % x))

B.dump("s02", dict(prereg_sha=B.prereg_sha(), chosen={str(kk): vv for kk, vv in CHOSEN.items()},
                   n_cells=len(pc)))
print("\nwrote REFERENCE_TUNING.csv Q1_PROJECTION_EFFECT.csv PROJECTION_SIGNFLIP.csv "
      "CEILING.csv PRIMARY_CELLS.csv")
B.hdr("DONE s02")
