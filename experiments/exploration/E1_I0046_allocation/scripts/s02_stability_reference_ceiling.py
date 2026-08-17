"""E1_I0046 s02 -- STABILITY (share vs level), the TUNED reference, and the CEILING GATE.

Order matters and is preregistered: stability first (no gate), then the reference, then the
arithmetic ceiling, which is a GATE.  Nothing in s03 runs for a response the gate closes.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import al_base as A

pd.set_option("display.width", 240)
pd.set_option("display.max_columns", 200)

A.hdr("E1_I0046  --  s02  STABILITY / REFERENCE / CEILING")
print("PREREG.md sha256 = %s" % A.prereg_sha())

d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "FRAME(reload)", True)
print("  materialising the six preregistered candidates (fixed halflife %d, never tuned):"
      % A.CANDIDATE_PRIOR_HALFLIFE)
d = A.add_candidate_columns(d, verbose=True)
dm = A.decision_mask(d)
clean = d["season"].isin(A.CLEAN_EVAL_SEASONS).to_numpy()
n = len(d)

# ============================================================== 1. STABILITY: share vs level
A.hdr("1. STABILITY -- autocorrelation of SHARE against autocorrelation of LEVEL")
print("  IDENTICAL rows, identical (game_date, game_id) order, within (season, player_id).")
print("  This is the ONE cross-response comparison this screen makes, and it is made only on")
print("  UNITLESS quantities (autocorrelation, ICC).  No dR2/MAE is ever set beside another.")

order = np.lexsort((d["game_id"].to_numpy(), d["game_date"].to_numpy(), d["ps_code"].to_numpy()))
ps = d["ps_code"].to_numpy()[order]
pos = np.arange(n)
newg = np.r_[True, ps[1:] != ps[:-1]]
gstart = np.maximum.accumulate(np.where(newg, pos, 0))
within_pos = pos - gstart


def acf_pairs(x_ord, L, mask_ord):
    """Pairs (t, t-L) inside the same player-season, both members inside mask."""
    ok = (within_pos >= L) & (ps == np.roll(ps, L)) & mask_ord & np.roll(mask_ord, L)
    ok[:L] = False
    a = x_ord[ok]
    b = np.roll(x_ord, L)[ok]
    fin = np.isfinite(a) & np.isfinite(b)
    return a[fin], b[fin]


def pearson(a, b):
    if len(a) < 3:
        return np.nan
    a = a - a.mean()
    b = b - b.mean()
    den = np.sqrt(float(a @ a) * float(b @ b))
    return float(a @ b) / den if den > 0 else np.nan


def eta2_between(x, groups, mask):
    v = x[mask]
    g = groups[mask]
    fin = np.isfinite(v)
    v, g = v[fin], g[fin]
    gg = pd.factorize(g)[0]
    mu = v.mean()
    sst = float(((v - mu) ** 2).sum())
    gm = np.bincount(gg, weights=v) / np.maximum(np.bincount(gg), 1)
    ssw = float(((v - gm[gg]) ** 2).sum())
    return (sst - ssw) / sst if sst > 0 else np.nan


PAIRS = [("R1_s_pts", "pts", "points"), ("R2_s_min", "minutes", "minutes"),
         ("R3_s_fga", "fga", "attempts")]
POPS = [("DECISION", dm), ("DECISION_CLEAN_2023_24", dm & clean),
        ("ALL_APPEARED", np.ones(n, bool)), ("ALL_CLEAN_2023_24", clean)]

srows = []
for popname, popmask in POPS:
    mo = popmask[order]
    for sname, lname, chan in PAIRS:
        xs = d[sname].to_numpy(float)[order]
        xl = d[lname].to_numpy(float)[order]
        # within-player-season centred copies, computed on the SAME rows
        def centre(x):
            c = np.array(x, float)
            df = pd.DataFrame({"g": ps, "x": np.where(mo, c, np.nan)})
            mu = df.groupby("g")["x"].transform("mean").to_numpy()
            return c - mu
        xsc, xlc = centre(xs), centre(xl)
        rec = dict(population=popname, channel=chan, share_col=sname, level_col=lname,
                   n_rows=int(popmask.sum()),
                   icc_share=eta2_between(d[sname].to_numpy(float), d["ps_code"].to_numpy(), popmask),
                   icc_level=eta2_between(d[lname].to_numpy(float), d["ps_code"].to_numpy(), popmask),
                   cv_share=float(np.nanstd(d[sname].to_numpy(float)[popmask], ddof=1) /
                                  np.nanmean(d[sname].to_numpy(float)[popmask])),
                   cv_level=float(np.nanstd(d[lname].to_numpy(float)[popmask], ddof=1) /
                                  np.nanmean(d[lname].to_numpy(float)[popmask])))
        for L in range(1, 6):
            a, b = acf_pairs(xs, L, mo)
            rec["acf%d_share" % L] = pearson(a, b)
            rec["n_pairs_L%d" % L] = int(len(a))
            a, b = acf_pairs(xl, L, mo)
            rec["acf%d_level" % L] = pearson(a, b)
            a, b = acf_pairs(xsc, L, mo)
            rec["acf%d_share_withincentred" % L] = pearson(a, b)
            a, b = acf_pairs(xlc, L, mo)
            rec["acf%d_level_withincentred" % L] = pearson(a, b)
        rec["acf1_gap_share_minus_level"] = rec["acf1_share"] - rec["acf1_level"]
        srows.append(rec)
        print("  %-24s %-9s n=%6d  ICC share %.4f level %.4f | acf1 share %+.4f level %+.4f "
              "GAP %+.4f | within-centred acf1 share %+.4f level %+.4f"
              % (popname, chan, rec["n_rows"], rec["icc_share"], rec["icc_level"],
                 rec["acf1_share"], rec["acf1_level"], rec["acf1_gap_share_minus_level"],
                 rec["acf1_share_withincentred"], rec["acf1_level_withincentred"]))

# ---- the counterweight, in the same file
A.hdr("1b. THE COUNTERWEIGHT -- how much of any share/level gap is arithmetic")
cw = []
for popname, popmask in POPS:
    for sname, lname, chan in PAIRS:
        T = {"points": "T_pts", "minutes": "T_min", "attempts": "T_fga"}[chan]
        y = d[lname].to_numpy(float)[popmask]
        Y = d[T].to_numpy(float)[popmask]
        ok = np.isfinite(y) & np.isfinite(Y) & (y > 0) & (Y > 0)
        rec = dict(population=popname, channel=chan,
                   sd_log_level=float(np.std(np.log(y[ok]), ddof=1)),
                   sd_log_total=float(np.std(np.log(Y[ok]), ddof=1)),
                   corr_level_total=pearson(y[ok], Y[ok]),
                   var_share_of_total_in_level=float(np.var(np.log(Y[ok]), ddof=1) /
                                                     np.var(np.log(y[ok]), ddof=1)))
        # autocorrelation of the TEAM TOTAL itself, within team-season
        tgs = d.drop_duplicates("tg")
        tt = tgs.sort_values(["season", "team_id", "game_date", "game_id"])
        code = pd.factorize(tt["season"].astype(str) + "|" + tt["team_id"].astype(str))[0]
        vv = tt[T].to_numpy(float)
        okp = (np.r_[False, code[1:] == code[:-1]])
        rec["acf1_team_total"] = pearson(vv[okp], np.roll(vv, 1)[okp])
        cw.append(rec)
        print("  %-24s %-9s sd(log level) %.4f  sd(log total) %.4f  corr(level,total) %+.4f  "
              "total-variance share of level %.4f  acf1(team total) %+.4f"
              % (popname, chan, rec["sd_log_level"], rec["sd_log_total"], rec["corr_level_total"],
                 rec["var_share_of_total_in_level"], rec["acf1_team_total"]))

st = pd.DataFrame(srows)
st.to_csv(os.path.join(A.OUT, "STABILITY.csv"), index=False)
pd.DataFrame(cw).to_csv(os.path.join(A.OUT, "STABILITY_COUNTERWEIGHT.csv"), index=False)

# ============================================================== 2. THE TUNED REFERENCE
A.hdr("2. THE REFERENCE -- tuned on strictly earlier seasons only, 42 (h,k) combinations")
tg_code = d["tg_code"].to_numpy()
n_tg = int(tg_code.max()) + 1
counts = np.bincount(tg_code, minlength=n_tg)
season = d["season"].to_numpy()

ALLOC = {}     # (resp, evalseason) -> dict of projected forecasts on the whole frame
tune_rows = []
for resp in A.RESPONSES:
    y = d[resp].to_numpy(float)
    for es in A.CLEAN_EVAL_SEASONS + A.DISCLOSED_EVAL_SEASONS:
        tr = (season < es) & dm            # tuned on the stratum the cell is scored on
        if tr.sum() < 200:
            continue
        best = None
        for h in A.H_GRID:
            for kk in A.K_GRID:
                raw = A.allocator_raw(d, resp, h, kk)
                f = A.project(raw, tg_code, n_tg, counts)
                sse = float(((y[tr] - f[tr]) ** 2).sum())
                if best is None or sse < best[0]:
                    best = (sse, h, kk, f)
        sse, h, kk, f = best
        ALLOC[(resp, es)] = f
        naive = A.project(A.allocator_raw(d, resp, 5, 0.0), tg_code, n_tg, counts)
        unif = 1.0 / counts[tg_code].astype(float)
        te = dm & (season == es)
        tune_rows.append(dict(response=resp, eval_season=int(es), n_train_rows=int(tr.sum()),
                              selected_h=("EXPANDING" if h == 0 else h), selected_k=kk,
                              train_sse=sse,
                              r2_tuned_eval=A.r2_of_forecast(y[te], f[te]),
                              r2_naive_eval=A.r2_of_forecast(y[te], naive[te]),
                              r2_uniform_eval=A.r2_of_forecast(y[te], unif[te]),
                              n_eval_rows=int(te.sum())))
        print("  %-9s eval %d  train_rows=%5d  selected h=%-9s k=%-4s | eval R2 tuned %+.5f  "
              "naive %+.5f  uniform %+.5f"
              % (resp, es, tr.sum(), tune_rows[-1]["selected_h"], kk,
                 tune_rows[-1]["r2_tuned_eval"], tune_rows[-1]["r2_naive_eval"],
                 tune_rows[-1]["r2_uniform_eval"]))
pd.DataFrame(tune_rows).to_csv(os.path.join(A.OUT, "REFERENCE_TUNING.csv"), index=False)

# assemble a single walk-forward base column per response over the clean window
BASE = {}
for resp in A.RESPONSES:
    b = np.full(n, np.nan)
    for es in A.CLEAN_EVAL_SEASONS + A.DISCLOSED_EVAL_SEASONS:
        if (resp, es) in ALLOC:
            m = (season == es)
            b[m] = ALLOC[(resp, es)][m]
    # training rows need a base too: use the 2023-tuned allocator (built only from <=2022 rows)
    fallback = ALLOC[(resp, A.CLEAN_EVAL_SEASONS[0])]
    b = np.where(np.isfinite(b), b, fallback)
    BASE[resp] = b
np.savez(os.path.join(A.SCR, "_base.npz"), **{k: v for k, v in BASE.items()})
d.to_parquet(os.path.join(A.SCR, "_frame2.parquet"), index=False)

# ============================================================== 3. THE CEILING GATE
A.hdr("3. ARITHMETIC CEILING -- COMPUTED BEFORE ANY FIT.  THIS IS A GATE.")
print("  ORACLE dR2 = (d.e)^2 / ((d.d) * SST), the strict upper bound on any LINEAR addition of")
print("  that column with a hindsight-optimal coefficient.  E1_I0043 D-02 established the D084/D089")
print("  variance-share form (d.d)/SST is NOT a bound; both are reported, the gate uses the ORACLE.")


def base_residual(resp, mask, eval_seasons):
    """Walk-forward base fit.

    DEFECT D-01, caught before any headline: an earlier version projected over the SCORED rows
    only, which forces the decision stratum's shares to sum to 1 and injects the realised total of
    that subset.  The projection MUST run over the full appeared roster of the eval season.  This
    function therefore returns FULL eval-season arrays plus a keep mask, and every projection
    downstream uses the full arrays.
    """
    y = d[resp].to_numpy(float)
    b = BASE[resp]
    fullY, fullRaw, fullTg, keeps, idx, used = [], [], [], [], [], []
    for es in eval_seasons:
        tr = np.ones(n, bool) & (season < es)          # fit population = ALL appeared roster rows
        te = (season == es)
        sc = mask & te
        if tr.sum() < 300 or sc.sum() < 50:
            continue
        Xb_tr = np.column_stack([np.ones(int(tr.sum())), b[tr]])
        Xb_te = np.column_stack([np.ones(int(te.sum())), b[te]])
        bb = A.ols(Xb_tr, y[tr])
        fullY.append(y[te])
        fullRaw.append(Xb_te @ bb)
        fullTg.append(tg_code[te])
        keeps.append(sc[te])
        idx.append(np.flatnonzero(sc))
        used.append(int(es))
    Y = np.concatenate(fullY)
    RAW = np.concatenate(fullRaw)
    TG = np.concatenate(fullTg)
    KEEP = np.concatenate(keeps)
    PRJ = A.project(RAW, TG, n_tg, counts)
    return dict(Y=Y, RAW=RAW, TG=TG, KEEP=KEEP, idx=np.concatenate(idx), used_seasons=used,
                full_idx=np.concatenate([np.flatnonzero(season == es) for es in used]),
                y=Y[KEEP], yb_proj=PRJ[KEEP], yb_raw=RAW[KEEP])


def oracle_proj(br, dvals_full, sst):
    """Best achievable dR2 for y ~ base + g*d AFTER a FULL-ROSTER projection, g by hindsight."""
    Y, RAW, TG, KEEP = br["Y"], br["RAW"], br["TG"], br["KEEP"]
    e = Y[KEEP] - RAW[KEEP]
    dk = dvals_full[KEEP]
    dc = dk - dk.mean()
    dd = float(dc @ dc)
    g0 = float(dc @ e) / dd if dd > 0 else 0.0
    grid = np.unique(np.r_[0.0, g0 * np.linspace(-6, 10, 321)])
    sse_b = float(((Y[KEEP] - A.project(RAW, TG, n_tg, counts)[KEEP]) ** 2).sum())
    best = sse_b
    for g in grid:
        pr = A.project(RAW + g * dvals_full, TG, n_tg, counts)
        sse = float(((Y[KEEP] - pr[KEEP]) ** 2).sum())
        if np.isfinite(sse) and sse < best:
            best = sse
    return (sse_b - best) / sst


crows = []
gate = {}
for resp in A.RESPONSES:
    for popname, popmask, evs, win in [("DECISION", dm, A.CLEAN_EVAL_SEASONS, "CLEAN_2023_24"),
                                       ("ALL_APPEARED", np.ones(n, bool), A.CLEAN_EVAL_SEASONS,
                                        "CLEAN_2023_24")]:
        br = base_residual(resp, popmask, evs)
        y, ybp, ybr, idx = br["y"], br["yb_proj"], br["yb_raw"], br["idx"]
        sst = float(((y - y.mean()) ** 2).sum())
        e_raw = y - ybr
        e_prj = y - ybp
        D = []
        for cand in A.CANDIDATES:
            # full eval-season candidate vector, aligned to br["Y"] (needed for the projection)
            dv_full = d[cand].to_numpy(float)[br["full_idx"]]
            dv_full = np.where(np.isfinite(dv_full), dv_full, np.nanmean(dv_full))
            dv = dv_full[br["KEEP"]]
            # standardise to unit sd so the (non-bounding) D084 form is at least comparable
            sdv = float(np.std(dv_full, ddof=1))
            dv_full_z = (dv_full - float(dv_full.mean())) / (sdv if sdv > 0 else 1.0)
            dvz = dv_full_z[br["KEEP"]]
            # residualise on the base design [1, b]
            Xb = np.column_stack([np.ones(len(y)), ybr])
            dres = dvz - Xb @ A.ols(Xb, dvz)
            dd = float(dres @ dres)
            de_raw = float(dres @ e_raw)
            de_prj = float(dres @ e_prj)
            orc_raw = (de_raw ** 2) / (dd * sst) if dd > 0 else 0.0
            orc_prj_lin = (de_prj ** 2) / (dd * sst) if dd > 0 else 0.0
            orc_projfit = oracle_proj(br, dv_full_z, sst)
            d084 = dd / sst
            if cand in A.REAL_CANDIDATES:
                D.append(dres)
            crows.append(dict(response=resp, population=popname, window=win, candidate=cand,
                              n=len(y), sst=sst, r2_base_proj=1.0 - float((e_prj @ e_prj)) / sst,
                              r2_base_raw=1.0 - float((e_raw @ e_raw)) / sst,
                              oracle_dr2_raw=orc_raw, oracle_dr2_proj_linear=orc_prj_lin,
                              oracle_dr2_proj_fitted=orc_projfit, d084_variance_share=d084,
                              vs_single_cell_floor=max(orc_raw, orc_projfit) / A.FLOOR_SINGLE_CELL,
                              vs_largest_live_effect=max(orc_raw, orc_projfit) / A.LARGEST_LIVE_EFFECT))
        Dm = np.column_stack(D)
        proj = Dm @ np.linalg.lstsq(Dm, e_raw, rcond=None)[0]
        fam = float(proj @ proj) / sst
        crows.append(dict(response=resp, population=popname, window=win,
                          candidate="FAMILY_ORACLE_5_REAL", n=len(y), sst=sst,
                          r2_base_proj=1.0 - float((e_prj @ e_prj)) / sst,
                          r2_base_raw=1.0 - float((e_raw @ e_raw)) / sst,
                          oracle_dr2_raw=fam, oracle_dr2_proj_linear=np.nan,
                          oracle_dr2_proj_fitted=np.nan, d084_variance_share=np.nan,
                          vs_single_cell_floor=fam / A.FLOOR_SINGLE_CELL,
                          vs_largest_live_effect=fam / A.LARGEST_LIVE_EFFECT))
        if popname == "DECISION":
            best_single = max(r["oracle_dr2_proj_fitted"] for r in crows
                              if r["response"] == resp and r["population"] == "DECISION"
                              and r["candidate"] in A.REAL_CANDIDATES)
            gate[resp] = dict(family_oracle=fam, best_single_proj_oracle=best_single,
                              gate_value=max(fam, best_single),
                              floor=A.FLOOR_SINGLE_CELL,
                              PROCEED=bool(max(fam, best_single) >= A.FLOOR_SINGLE_CELL))
        print("  %-9s %-13s base R2 proj %+.5f raw %+.5f | family ORACLE %.6f = %.2fx floor"
              % (resp, popname, 1.0 - float(e_prj @ e_prj) / sst, 1.0 - float(e_raw @ e_raw) / sst,
                 fam, fam / A.FLOOR_SINGLE_CELL))

ce = pd.DataFrame(crows)
ce.to_csv(os.path.join(A.OUT, "CEILING.csv"), index=False)
print("\n  PER-CANDIDATE ORACLE CEILINGS, DECISION stratum, CLEAN window:")
q = ce[(ce["population"] == "DECISION")]
print(q[["response", "candidate", "n", "oracle_dr2_raw", "oracle_dr2_proj_fitted",
         "d084_variance_share", "vs_single_cell_floor"]].to_string(index=False))

A.hdr("4. THE PREREGISTERED GATE")
for resp in A.RESPONSES:
    g = gate[resp]
    print("  %-9s family ORACLE %.6f   best single (projected, hindsight) %.6f   "
          "floor %.5f  -->  %s"
          % (resp, g["family_oracle"], g["best_single_proj_oracle"], g["floor"],
             "PROCEED" if g["PROCEED"] else "CLOSED ON ARITHMETIC -- DO NOT FIT"))

A.dump("s02", dict(prereg_sha=A.prereg_sha(), stability=srows, counterweight=cw,
                   tuning=tune_rows, ceiling=ce.to_dict("records"), gate=gate))
print("\n  s02 OK.")
