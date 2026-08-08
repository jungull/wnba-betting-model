"""
s02 -- STEP 2.  DOES THE USAGE x DEFENCE INTERACTION IMPROVE A FORECAST?

THE CONTRAST IS STRICTLY NESTED.
    Arm B (without) : [1, COMPLETE prior reference, usage, defence]
    Arm A (with)    : [1, COMPLETE prior reference, usage, defence, (usage-u)x(defence-d)]
Identical rows, identical base, identical main effects.  The ONLY difference is the interaction
column.  Without both main effects in BOTH arms the "interaction" would simply be a main effect in
disguise -- and the defence main effect is comprehensively dead (D085, 0 of 36 cells), so any
increment attributed to it would be spurious.

THE REFERENCE IS THE THING MOST LIKELY TO KILL THIS, AND IT IS DELIBERATELY COMPLETE.
    D091 ranks reference incompleteness as the top explanation for this programme's nulls, and D090
    showed the SAME forecast scoring +46.4% or +7.1% by reference choice alone.  The base therefore
    carries EVERY strictly-prior measurement of the target the frozen frames hold:
        refB_ppm  prior points per minute
        refB_spm  prior true-shooting attempts per minute
        refB_pps  prior points per attempt
        refB_mpg  prior minutes per game
        refB_own_usg_pg  prior usage per game
    A deliberately INCOMPLETE base (refB_ppm alone) is run alongside as a preregistered CONTRAST so
    the reference-sensitivity of any result is a measured number rather than an assertion.

FIT WINDOW.  HEADLINE is WALK-FORWARD: coefficients fitted on seasons strictly before the scored
season and applied forward, exactly as D089's `walkforward_points.csv` did it.  2021 is a TRAINING
fold only; every scored row is 2022-2024.  The in-sample fit is also reported and labelled a
DIAGNOSTIC, because an in-sample coefficient reads the whole partition (constraint 4 covers
inference steps, not only features).

MINUTES.  Points and attempts are reached as rate x `_m_hat`, where `_m_hat` is the player's
strictly-prior trailing-5 mean minutes with a strictly-prior mean-minutes fallback -- D089's
construction.  NO REALISED MINUTES ANYWHERE: unlike D093's measurement question, this is a
forecasting question and may not condition on the game's own outcome.

NULL.  Whole-cluster sign-flip at OPPONENT-TEAM-SEASON, which is the level the defence term varies
at.  Cluster codes are GLOBAL and the sign draws are SHARED across cells, so the max-statistic
family-wise null across the 18 real cells is coupled rather than a stack of independent maxima.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import uid_base as ub  # noqa: E402
import s00_prereg as pr  # noqa: E402

TV_COLS = ["O01_own_usg_pg", "G01_noise", "y_spm", "y_pts", "TSA", "refB_ppm", "refB_spm",
           "refB_pps", "refB_mpg", "refB_own_usg_pg", "prior5_minutes"]
BASES = {"B_COMPLETE": pr.BASE_COMPLETE, "B_SINGLE": pr.BASE_SINGLE}
RESP = {r["id"]: r for r in pr.RESPONSES}


def build_frame(P):
    m = ub.build_merged(verbose=True, include_2021=True, tv_cols=TV_COLS)
    # D085's frame and D089's frame both carry refB_ppm from the same construction; the merge
    # suffixes D089's copy.  VERIFY they agree rather than assuming it, then drop the duplicate.
    d = np.nanmax(np.abs(m["refB_ppm"].to_numpy(float) - m["refB_ppm_tv"].to_numpy(float)))
    P("  refB_ppm cross-frame identity check: max|D085 - D089| = %.3e" % d)
    assert d < 1e-12, "the two frames disagree on refB_ppm"
    m = m.drop(columns=["refB_ppm_tv"])
    m["_m_hat"] = m["prior5_minutes"].fillna(m["refB_mpg"])
    # GLOBAL cluster codes: the same integer means the same opponent-team-season in every cell.
    key = list(zip(m["opp_team_id"].astype(str), m["season"].astype(int)))
    codes, uq = pd.factorize(pd.Series(key), sort=True)
    m["_cluster"] = codes
    P("  frame: %d rows, seasons %s, %d opponent-team-season clusters"
      % (len(m), sorted(m["season"].unique()), len(uq)))
    P("  _m_hat = prior5_minutes (strictly-prior trailing-5 mean) with refB_mpg fallback; "
      "NO realised minutes anywhere in this step")
    return m, len(uq)


def stratum_mask(m, sid):
    if sid == "POOLED":
        return np.ones(len(m), bool)
    return ((m["n_prior"] >= 8).to_numpy()
            & (pd.to_numeric(m["prior5_minutes"], errors="coerce") >= 24).to_numpy(dtype=bool))


def design(v, basecols, sel, ucol, dcol, uc, dc, with_int):
    u, d = v[ucol][sel], v[dcol][sel]
    cols = [np.ones(len(u))] + [v[c][sel] for c in basecols] + [u, d]
    if with_int:
        cols.append((u - uc) * (d - dc))
    return np.column_stack(cols)


def run_cell(m, ncl, cell, basename, basecols, n_draws, fit="walk_forward"):
    r = RESP[cell["response"]]
    ucol, dcol = cell["usage"], cell["defence"]
    need = list(dict.fromkeys(basecols + [ucol, dcol, r["rate_col"], r["target_col"], "_m_hat"]))
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}
    mask = stratum_mask(m, cell["stratum"])
    for c in need:
        mask &= np.isfinite(v[c])
    ssn = m["season"].to_numpy()
    clus = m["_cluster"].to_numpy()

    yy, pa, pb, cc, betas, ns = [], [], [], [], [], []
    if fit == "walk_forward":
        folds = [(mask & (ssn < s), mask & (ssn == s)) for s in pr.PREREG["partition"]["scored_seasons"]]
    else:
        folds = [(mask, mask)]
    for tr, te in folds:
        if tr.sum() < 500 or te.sum() < 100:
            continue
        uc, dc = float(v[ucol][tr].mean()), float(v[dcol][tr].mean())
        Xb_tr = design(v, basecols, tr, ucol, dcol, uc, dc, False)
        Xa_tr = design(v, basecols, tr, ucol, dcol, uc, dc, True)
        Xb_te = design(v, basecols, te, ucol, dcol, uc, dc, False)
        Xa_te = design(v, basecols, te, ucol, dcol, uc, dc, True)
        yr = v[r["rate_col"]]
        bb = ub.ols(Xb_tr, yr[tr])
        ba = ub.ols(Xa_tr, yr[tr])
        scale = v["_m_hat"][te] if r["scale_by_minutes"] else 1.0
        pb.append((Xb_te @ bb) * scale)
        pa.append((Xa_te @ ba) * scale)
        yy.append(v[r["target_col"]][te])
        cc.append(clus[te])
        betas.append(float(ba[-1]))
        ns.append(int(te.sum()))
    if not yy:
        return None
    y = np.concatenate(yy)
    A = np.concatenate(pa)
    B = np.concatenate(pb)
    C = np.concatenate(cc)
    t = ub.paired_cluster_test(y, A, B, C, ncl, n_draws=n_draws, seed=ub.SEED)
    draws = t.pop("draws_cluster")
    out = dict(cell_id=cell["cell_id"], kind=cell["kind"], base=basename, fit=fit,
               usage=ucol, defence=dcol, response=cell["response"], stratum=cell["stratum"],
               n_scored=int(len(y)), n_rows_eligible=int(mask.sum()),
               r2_without=ub.r2_of_forecast(y, B), r2_with=ub.r2_of_forecast(y, A),
               mae_without=ub.mae(y, B), mae_with=ub.mae(y, A),
               mae_pct_reduction=float(100.0 * (1.0 - ub.mae(y, A) / ub.mae(y, B))),
               mean_interaction_beta=float(np.mean(betas)),
               beta_sign_consistent=bool(len(set(np.sign(betas))) == 1),
               sd_response=float(np.std(y, ddof=1)), **t)
    return out, draws


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    ub.hdr("E1_I0023 s02 -- STEP 2: DOES THE INTERACTION IMPROVE A FORECAST?")
    h, added, dropped = pr.check_prereg()
    P("  PREREG hash %s VERIFIED. cells added=%d dropped=%d (list is unchanged)"
      % (h, len(added), len(dropped)))
    m, ncl = build_frame(P)

    cells = pr.cells()
    P("  %d preregistered cells (%d real, %d control) x %d bases x 2 fit windows"
      % (len(cells), pr.PREREG["n_real_cells"], pr.PREREG["n_control_cells"], len(BASES)))

    rows, draws_store = [], {}
    for fit in ("walk_forward", "in_sample"):
        ub.hdr("FIT WINDOW: %s%s" % (fit, "   <-- HEADLINE" if fit == "walk_forward"
                                     else "   <-- DIAGNOSTIC ONLY (reads the whole partition)"))
        for basename, basecols in BASES.items():
            for c in cells:
                res = run_cell(m, ncl, c, basename, basecols, pr.N_DRAWS, fit=fit)
                if res is None:
                    P("  %-46s %-11s SKIPPED (insufficient rows)" % (c["cell_id"], basename))
                    continue
                out, dr = res
                rows.append(out)
                if fit == "walk_forward":
                    draws_store[(basename, c["cell_id"])] = dr
                P("  %-46s %-11s n=%5d  dR2=%+.6f  cluster p=%.4f (row p=%.4f)  "
                  "MAE %.4f -> %.4f (%+.3f%%)  beta_int=%+.3e%s"
                  % (c["cell_id"], basename, out["n_scored"], out["dr2_a_minus_b"],
                     out["p_cluster"], out["p_row_NAIVE"], out["mae_without"], out["mae_with"],
                     out["mae_pct_reduction"], out["mean_interaction_beta"],
                     "  <-- CONTROL" if c["kind"] == "CONTROL" else ""))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(ub.OUT, "interaction_forecast.csv"), index=False)

    # ------------------------------------------------------------------ family-wise, coupled
    ub.hdr("FAMILY-WISE MAX-STATISTIC ACROSS THE 18 REAL CELLS (walk-forward, B_COMPLETE)")
    real_ids = [c["cell_id"] for c in cells if c["kind"] == "REAL"]
    zs, zdraws = {}, []
    for cid in real_ids:
        d = draws_store[("B_COMPLETE", cid)]
        row = res[(res.cell_id == cid) & (res.base == "B_COMPLETE")
                  & (res.fit == "walk_forward")].iloc[0]
        sd = float(np.std(d, ddof=1))
        zs[cid] = float(row["dr2_a_minus_b"] / sd) if sd > 0 else np.nan
        zdraws.append(np.abs(d / sd) if sd > 0 else np.full_like(d, np.nan))
    maxnull = np.nanmax(np.vstack(zdraws), axis=0)
    obs_max = float(np.nanmax(np.abs(list(zs.values()))))
    argmax = max(zs, key=lambda k: abs(zs[k]))
    p_fw = (1.0 + int((maxnull >= obs_max).sum())) / (len(maxnull) + 1.0)
    P("  max |z| observed = %.3f (%s)" % (obs_max, argmax))
    P("  family-wise null p95 of max|z| = %.3f   (naive per-cell 2-sided bar = 1.96)"
      % float(np.percentile(maxnull, 95)))
    P("  FAMILY-WISE p = %.4f -> %s" % (p_fw, "CLEARS 0.05" if p_fw < 0.05 else "DOES NOT CLEAR"))
    P("  per-cell z: %s" % "  ".join("%s=%+.2f" % (k, v) for k, v in zs.items()))

    ctrl_ids = [c["cell_id"] for c in cells if c["kind"] == "CONTROL"]
    ctrl = res[(res.cell_id.isin(ctrl_ids)) & (res.base == "B_COMPLETE")
               & (res.fit == "walk_forward")]
    P("  negative controls (walk-forward, B_COMPLETE): %s"
      % ", ".join("%s dR2=%+.2e p=%.3f" % (r.cell_id, r.dr2_a_minus_b, r.p_cluster)
                  for r in ctrl.itertuples()))
    ctrl_clean = bool((ctrl["p_cluster"] > 0.05).all())

    # ------------------------------------------------------------------ attrition
    ub.hdr("HONEST ATTRITION")
    wf = res[(res.fit == "walk_forward") & (res.base == "B_COMPLETE") & (res.kind == "REAL")]
    a0 = len(wf)
    a1 = int((wf["dr2_a_minus_b"] > 0).sum())
    a2 = int(((wf["dr2_a_minus_b"] > 0) & (wf["p_row_NAIVE"] < 0.05)).sum())
    a3 = int(((wf["dr2_a_minus_b"] > 0) & (wf["p_cluster"] < 0.05)).sum())
    P("  %d real cells -> %d with dR2 > 0 -> %d at the NAIVE row-level p<0.05 -> "
      "%d at the CORRECT cluster-level p<0.05 -> family-wise %s"
      % (a0, a1, a2, a3, "CLEARS" if p_fw < 0.05 else "does not clear"))
    med_infl = float(wf["null_width_inflation_cluster_over_row"].median())
    P("  median null-width inflation (cluster / row) = %.3f  -- the wrong-null trap, again"
      % med_infl)

    # ------------------------------------------------------------------ primary cell
    ub.hdr("THE PRIMARY CELL, DECLARED BEFORE ANY STATISTIC WAS COMPUTED")
    pid = "%s|%s|%s" % (pr.PRIMARY["defence"], pr.PRIMARY["response"], pr.PRIMARY["stratum"])
    cid2 = "%s|%s|%s" % (pr.CO_PRIMARY["defence"], pr.CO_PRIMARY["response"], pr.CO_PRIMARY["stratum"])
    prim = res[(res.cell_id == pid) & (res.base == "B_COMPLETE")
               & (res.fit == "walk_forward")].iloc[0]
    cop = res[(res.cell_id == cid2) & (res.base == "B_COMPLETE")
              & (res.fit == "walk_forward")].iloc[0]
    for lbl, r in (("PRIMARY   ", prim), ("CO-PRIMARY", cop)):
        P("  %s %-46s n=%5d  dR2=%+.6f  cluster p=%.4f  MAE %.5f -> %.5f (%+.4f%%)"
          % (lbl, r["cell_id"], r["n_scored"], r["dr2_a_minus_b"], r["p_cluster"],
             r["mae_without"], r["mae_with"], r["mae_pct_reduction"]))

    # ------------------------------------------------------------------ reference sensitivity
    ub.hdr("REFERENCE SENSITIVITY -- the failure mode D090/D091 rank first")
    sens = []
    for cid in real_ids:
        a = res[(res.cell_id == cid) & (res.base == "B_COMPLETE") & (res.fit == "walk_forward")]
        b = res[(res.cell_id == cid) & (res.base == "B_SINGLE") & (res.fit == "walk_forward")]
        if len(a) == 0 or len(b) == 0:
            continue
        sens.append(dict(cell_id=cid, dr2_B_COMPLETE=float(a.iloc[0]["dr2_a_minus_b"]),
                         dr2_B_SINGLE=float(b.iloc[0]["dr2_a_minus_b"]),
                         ratio=float(b.iloc[0]["dr2_a_minus_b"] / a.iloc[0]["dr2_a_minus_b"])
                         if a.iloc[0]["dr2_a_minus_b"] != 0 else np.nan))
    sdf = pd.DataFrame(sens)
    sdf.to_csv(os.path.join(ub.OUT, "reference_sensitivity.csv"), index=False)
    for r in sdf.itertuples():
        P("  %-46s COMPLETE %+.6f   INCOMPLETE %+.6f   x%.2f"
          % (r.cell_id, r.dr2_B_COMPLETE, r.dr2_B_SINGLE, r.ratio))

    dd = []
    for (bn, cid), d in draws_store.items():
        for k in range(0, len(d), 4):     # thinned 4:1 to keep the artefact readable
            dd.append(dict(step="s02_walkforward", base=bn, cell_id=cid, null="cluster_sign_flip",
                           draw=k, dr2=float(d[k])))
    pd.DataFrame(dd).to_csv(os.path.join(ub.OUT, "permutation_draws_s02.csv"), index=False)

    out = dict(prereg_sha256=h, cells_added=len(added), cells_dropped=len(dropped),
               n_clusters=int(ncl), family_wise_p=p_fw, family_wise_max_z=obs_max,
               family_wise_argmax=argmax,
               family_wise_null_p95=float(np.percentile(maxnull, 95)),
               controls_clean=ctrl_clean,
               attrition=dict(real_cells=a0, positive=a1, naive_p05=a2, cluster_p05=a3),
               median_null_width_inflation=med_infl,
               primary=json.loads(prim.to_json()), co_primary=json.loads(cop.to_json()))
    with open(os.path.join(ub.OUT, "_s02.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(ub.OUT, "run_log_s02.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("")
    P("  wrote interaction_forecast.csv, reference_sensitivity.csv, permutation_draws_s02.csv, "
      "_s02.json")


if __name__ == "__main__":
    main()
