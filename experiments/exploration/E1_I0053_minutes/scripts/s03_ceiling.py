"""s03 -- THE ARITHMETIC CEILING, COMPUTED BEFORE ANY CANDIDATE IS FITTED.

Every number carries its full denominator.  Every ceiling carries c* and a matched control.
`(d.d)/SST` is computed for continuity and is used for NOTHING -- it is not a bound.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s03 CEILING   PREREG sha256 %s" % A.prereg_sha())
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
PROJ_TOT = {"R1_min": T_min_tg, "R2_smin": np.ones(n_tg)}
Y = {r: d[r].to_numpy(float) for r in A.RESPONSES}

# component decomposition, declared in PREREG 4.2
COMP = {}
for c in A.WITHIN_TG_CANDIDATES + ["G01_noise"]:
    x = d[c].to_numpy(float)
    gm = (np.bincount(tg_code, weights=x, minlength=n_tg) / counts)[tg_code]
    COMP[c + "__W"] = x - gm
    COMP[c + "__B"] = gm
ALLCOLS = {c: d[c].to_numpy(float) for c in A.CANDIDATES}
ALLCOLS.update(COMP)


def base_forecast(resp, pm, eval_seasons):
    """The Cell's own base forecast on the scored rows.  Candidate-independent by construction."""
    y = Y[resp]
    b = Z["%s|%s" % (resp, pm)]
    cell = A.Cell(d, y, b, "PROBE", np.zeros(len(d)), dm, dm, eval_seasons, "FROZEN", pm,
                  proj_totals=PROJ_TOT[resp])
    return cell.full()


def proj_oracle(resp, pm, dcol, eval_seasons):
    """Best attainable dR2 when only g is free and the forecast is then projected.  Bounds the
    FROZEN/PROJ arm only (E1_I0046 D-04: one ceiling does NOT cover both arms)."""
    y = Y[resp]
    b = Z["%s|%s" % (resp, pm)]
    tot = PROJ_TOT[resp]
    ys, ybs, raws, ds, tgs = [], [], [], [], []
    for s in eval_seasons:
        tr = dm & (season < s)
        te = (season == s)
        sc = dm & te
        if tr.sum() < 300 or sc.sum() < 50:
            continue
        Xb_tr = np.column_stack([np.ones(int(tr.sum())), b[tr]])
        Xb_te = np.column_stack([np.ones(int(te.sum())), b[te]])
        bb = A.ols(Xb_tr, y[tr])
        raws.append(Xb_te @ bb)
        ds.append(dcol[te] - float(dcol[tr].mean()))
        tgs.append(tg_code[te])
        ys.append(y[te])
        ybs.append(sc[te])
    if not ys:
        return np.nan, np.nan, np.nan, np.nan

    def sse_at(g):
        num = []
        for yy, rw, dd, tc, keep in zip(ys, raws, ds, tgs, ybs):
            f = rw + g * dd
            if pm == "PROJ":
                f = A.project_to_total(f, tc, n_tg, counts, tot)
            num.append(((yy[keep] - f[keep]) ** 2).sum())
        return float(np.sum(num))

    yy_all = np.concatenate([yy[k] for yy, k in zip(ys, ybs)])
    sst = float(((yy_all - yy_all.mean()) ** 2).sum())
    sse0 = sse_at(0.0)
    # g-grid anchored on the LINEAR frozen coefficient, exactly E1_I0046/s02::oracle_proj.
    # An unanchored wide grid is NOT a usable ceiling: at large |g| the non-negativity clip inside
    # the projection turns the search into an arbitrary monotone reallocation of d, and the
    # "ceiling" it returns is a property of the clip, not of the candidate.  (DEFECTS D-02.)
    e_all = np.concatenate([(yy - rw)[k] for yy, rw, k in zip(ys, raws, ybs)])
    d_all = np.concatenate([dd[k] for dd, k in zip(ds, ybs)])
    dc = d_all - d_all.mean()
    ddv = float(dc @ dc)
    g0 = float(dc @ e_all) / ddv if ddv > 0 else 0.0
    gs = np.unique(np.r_[0.0, g0 * np.linspace(-6.0, 10.0, 321)])
    vals = np.array([sse_at(g) for g in gs])
    i = int(np.argmin(vals))
    best = float(min(vals.min(), sse0))
    gstar = float(gs[i])
    # how much of this "ceiling" is the non-negativity CLIP rather than the candidate
    clip = 0.0
    ntot = 0
    for rw, dd in zip(raws, ds):
        f = rw + gstar * dd
        clip += float((f < 0).sum())
        ntot += len(f)
    # a tighter companion: g restricted to [-2 g0, 2 g0], where the clip is not yet active
    gs_r = np.unique(np.r_[0.0, g0 * np.linspace(-2.0, 2.0, 81)])
    best_r = float(min(np.min([sse_at(g) for g in gs_r]), sse0))
    return ((sse0 - best) / sst, gstar, clip / max(ntot, 1), (sse0 - best_r) / sst)


rows = []
FAM = {}
for resp in A.RESPONSES:
    for pm in (["RAW", "PROJ"] if resp == "R1_min" else ["PROJ"]):
        r0 = base_forecast(resp, pm, A.CLEAN_EVAL_SEASONS)
        yy, yb, idx = r0["y"], r0["yb"], r0["idx"]
        e = yy - yb
        sst = r0["sst"]
        n = r0["n"]
        b_on_rows = Z["%s|%s" % (resp, pm)][idx]
        X = np.column_stack([np.ones(n), b_on_rows])
        P = X @ np.linalg.pinv(X)
        Dmat = []
        names = []
        for c, col in ALLCOLS.items():
            x = col[idx]
            x = (x - x.mean()) / (x.std(ddof=1) if x.std(ddof=1) > 0 else 1.0)
            dv = x - P @ x
            dd = float(dv @ dv)
            de = float(dv @ e)
            unc = (de ** 2) / (dd * sst) if dd > 0 and sst > 0 else np.nan
            cstar = de / dd if dd > 0 else np.nan
            po, gstar, clipf, po_r = proj_oracle(resp, pm, col, A.CLEAN_EVAL_SEASONS)
            rows.append(dict(response=resp, projection=pm, stratum="DECISION_CLEAN_2023_24",
                             candidate=c, n=n, sst=sst, r2_base=r0["r2_base"],
                             corr_with_base=float(np.corrcoef(col[idx], b_on_rows)[0, 1]),
                             ORACLE_unconstrained=unc, ORACLE_projected=po, c_star=cstar,
                             g_star_projected=gstar, clip_frac_at_gstar=clipf,
                             ORACLE_projected_g_within_2g0=po_r,
                             NOT_A_BOUND_dd_over_sst=dd / sst))
            if c in A.REAL_CANDIDATES:
                Dmat.append(dv)
                names.append(c)
            print("  %-8s %-4s %-20s ORACLE unc %.6f  proj %.6f  c* %+9.4f  corr(base) %+.4f"
                  % (resp, pm, c, unc, po, cstar, rows[-1]["corr_with_base"]))
        D = np.column_stack(Dmat)
        fam = float(e @ (D @ np.linalg.pinv(D)) @ e) / sst
        FAM[(resp, pm)] = dict(family_oracle=fam, K=len(names), n=n,
                               df_cost=len(names) / n, family_oracle_df_corrected=fam - len(names) / n)
        print("  %-8s %-4s FAMILY joint oracle over K=%d real candidates: %.6f   df cost K/n=%.6f"
              " -> df-corrected %.6f" % (resp, pm, len(names), fam, len(names) / n,
                                         fam - len(names) / n))

C = pd.DataFrame(rows)
C.to_csv(os.path.join(A.OUT, "CEILING.csv"), index=False)
A.dump("s03", dict(prereg_sha=A.prereg_sha(),
                   family={"%s|%s" % k: v for k, v in FAM.items()},
                   n_rows=len(C)))
A.hdr("s03 done -- CEILING.csv written")
