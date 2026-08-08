"""
s07 -- STRESS-TESTING THE ONE THING THAT SURVIVED, AND ASKING WHETHER IT IS WHAT IT LOOKS LIKE.

WHAT SURVIVED.  Not the preregistered interaction -- that failed its own primary cell.  What
survived is the opponent-defence MAIN EFFECT INSIDE THE TOP USAGE TERCILE: walk-forward dR2
+0.0239 (points-per-minute) and +0.0187 (points) on the decision stratum, against the COMPLETE prior
reference, surviving a within-date opponent-swap null at the 500-draw floor, with the defence column
independently verified strictly prior (s06).

THIS SECTION IS EXPLICITLY POST-HOC AND IS LABELLED AS SUCH EVERYWHERE.  The tier decomposition was
directed (step 4) and the main-effect-by-tier test was directed (step 5) with its prediction
registered before the numbers, but the SURVIVING CELL is not one of the 18 hashed interaction cells
and does not inherit their family-wise correction.  It gets its own, here.

SIX TESTS, ALL DECLARED BEFORE THEY ARE RUN:
    T1 FAMILY-WISE over the 12 main-effect tier cells (2 responses x 2 strata x 3 tiers), under the
       within-date opponent-swap null, coupled across cells by a shared draw sequence.
    T2 NEGATIVE CONTROL: run the identical tier machinery with a PURE NOISE column in place of the
       defence term. If the tier split alone manufactures a top-tier effect, this fires.
    T3 SEASON STABILITY: 2023 and 2024 scored separately. A real opponent effect should appear in
       both; an artefact of one season's peculiarity should not.
    T4 LEAVE-ONE-OPPONENT-SEASON-OUT jackknife over the 48 clusters. If a handful of opponents carry
       it, it is not a general effect.
    T5 IS THE AXIS REALLY USAGE?  The same split on PRIOR MINUTES and on PRIOR POINTS-PER-MINUTE.
       If any high-level split works equally, "usage" is not the mechanism, it is a proxy for
       "player scores a lot".
    T6 IS IT MERELY SCALE?  A defence effect that MULTIPLIES a player's rate is automatically larger
       in absolute units for a high-rate player, and needs NO heterogeneity at all -- one pooled
       multiplicative parameter reproduces it. Tested by (a) making the response RELATIVE to the
       player's own prior rate and re-running the tier split, and (b) a single POOLED interaction of
       the player's own prior rate with defence, scored against the same reference.
       IF T6 EXPLAINS IT, THE FINDING IS A SCALE EFFECT AND NOT A HETEROGENEITY FINDING, AND THE
       CORRECT MODEL IS ONE POOLED PARAMETER RATHER THAN A TIERED OR INTERACTED ONE.
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
import s02_interaction_forecast as s02  # noqa: E402
import s05_placebos as s05  # noqa: E402

DEFENCE = "A10_opp_defrtg"
UCOL = pr.USAGE_MAIN
BASE = pr.BASE_COMPLETE
N_SWAP = 500
TN = {0: "T1_low", 1: "T2_mid", 2: "T3_high"}


def tiers_for(m, v, mask, axis):
    first_tr = mask & (m["season"].to_numpy() < pr.PREREG["partition"]["scored_seasons"][0])
    src = v[axis]
    t, q = ub.usage_terciles(src[first_tr] if first_tr.sum() > 200 else src[mask], src)
    return t, q


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    ub.hdr("E1_I0023 s07 -- STRESS TESTS ON THE SURVIVING MAIN EFFECT (POST-HOC, LABELLED)")
    h, _, _ = pr.check_prereg()
    P("  PREREG hash %s VERIFIED" % h)
    P("  EVERYTHING IN THIS SCRIPT IS POST-HOC RELATIVE TO THE 18 HASHED INTERACTION CELLS. It gets "
      "its own family-wise correction and is never quoted under the preregistered one.")
    m, ncl = s02.build_frame(P)
    m, unit = s05.build_placebos(m, P)

    m["_rel_ppm"] = m["y_ppm"] / m["refB_ppm"].replace(0.0, np.nan)
    need = list(dict.fromkeys(BASE + [UCOL, DEFENCE, "G01_noise", "y_ppm", "y_pts", "_m_hat",
                                      "_rel_ppm", "refB_mpg", "refB_ppm"]))
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}
    RESP_PPM = s02.RESP["ppm"]
    RESP_PTS = s02.RESP["points"]
    RESP_REL = {"id": "rel_ppm", "rate_col": "_rel_ppm", "target_col": "_rel_ppm",
                "scale_by_minutes": False}

    # ================================================================= T1 + T2
    ub.hdr("T1 FAMILY-WISE over the 12 main-effect tier cells + T2 NEGATIVE CONTROL")
    rows, draws_by_cell = [], {}
    for dcol, kind in ((DEFENCE, "REAL"), ("G01_noise", "NEGATIVE_CONTROL")):
        for resp in (RESP_PPM, RESP_PTS):
            for sid in ("POOLED", "DECISION"):
                base_mask = s02.stratum_mask(m, sid)
                for c in need:
                    base_mask &= np.isfinite(v[c])
                tier_all, q = tiers_for(m, v, base_mask, UCOL)
                for t in (0, 1, 2):
                    mask = base_mask & (tier_all == t)
                    real = s05.score(m, v, BASE, mask, v[dcol], UCOL, False, resp)
                    if real is None:
                        continue
                    dr2 = real[0]
                    rng = np.random.default_rng(ub.SEED + 99)
                    dr = np.empty(N_SWAP)
                    for k in range(N_SWAP):
                        dv = s05.swap_within_date(m, unit, rng)
                        rr = s05.score(m, v, BASE, mask, dv, UCOL, False, resp)
                        dr[k] = rr[0] if rr is not None else np.nan
                    dr = dr[np.isfinite(dr)]
                    cid = "%s|%s|%s|%s" % (kind, resp["id"], sid, TN[t])
                    draws_by_cell[cid] = dr
                    p = (1.0 + int((dr >= dr2).sum())) / (len(dr) + 1.0)
                    rows.append(dict(cell=cid, kind=kind, response=resp["id"], stratum=sid,
                                     tier=TN[t], n=int(len(real[1])), dr2=dr2,
                                     swap_null_mean=float(dr.mean()),
                                     swap_null_sd=float(dr.std(ddof=1)), p_swap=p,
                                     z=float((dr2 - dr.mean()) / dr.std(ddof=1))))
                    r = rows[-1]
                    P("  %-14s %-7s %-9s %-8s n=%5d  dR2=%+.6f  swap null %+.6f+-%.6f  z=%+.2f  "
                      "p=%.4f" % (kind, resp["id"], sid, TN[t], r["n"], dr2, dr.mean(),
                                  dr.std(ddof=1), r["z"], p))
    tdf = pd.DataFrame(rows)
    real_cells = [c for c in draws_by_cell if c.startswith("REAL")]
    n = min(len(draws_by_cell[c]) for c in real_cells)
    zst = []
    for c in real_cells:
        d = draws_by_cell[c][:n]
        zst.append((d - d.mean()) / d.std(ddof=1))
    maxnull = np.vstack(zst).max(axis=0)
    obs = float(tdf[tdf.kind == "REAL"]["z"].max())
    arg = tdf[tdf.kind == "REAL"].iloc[tdf[tdf.kind == "REAL"]["z"].to_numpy().argmax()]["cell"]
    p_fw = (1.0 + int((maxnull >= obs).sum())) / (len(maxnull) + 1.0)
    P("  FAMILY-WISE over the 12 real tier cells: max z=%+.2f (%s)  null p95=%.2f  p_fw=%.4f -> %s"
      % (obs, arg, float(np.percentile(maxnull, 95)), p_fw,
         "CLEARS" if p_fw < 0.05 else "does not clear"))
    ctrl = tdf[tdf.kind == "NEGATIVE_CONTROL"]
    P("  NEGATIVE CONTROL max z = %+.2f, min p = %.4f  -> %s"
      % (float(ctrl["z"].max()), float(ctrl["p_swap"].min()),
         "CLEAN" if ctrl["p_swap"].min() > 0.05 else "*** A CONTROL FIRED ***"))

    # ================================================================= T3 season stability
    ub.hdr("T3 SEASON STABILITY of the top-tier main effect")
    st = []
    for resp in (RESP_PPM, RESP_PTS):
        for sid in ("POOLED", "DECISION"):
            base_mask = s02.stratum_mask(m, sid)
            for c in need:
                base_mask &= np.isfinite(v[c])
            tier_all, _ = tiers_for(m, v, base_mask, UCOL)
            mask = base_mask & (tier_all == 2)
            ssn = m["season"].to_numpy()
            for s in (2022, 2023, 2024):
                tr, te = mask & (ssn < s), mask & (ssn == s)
                if tr.sum() < 300 or te.sum() < 80:
                    continue
                X0tr = np.column_stack([np.ones(int(tr.sum()))] + [v[c][tr] for c in BASE]
                                       + [v[UCOL][tr]])
                X0te = np.column_stack([np.ones(int(te.sum()))] + [v[c][te] for c in BASE]
                                       + [v[UCOL][te]])
                X1tr = np.column_stack([X0tr, v[DEFENCE][tr]])
                X1te = np.column_stack([X0te, v[DEFENCE][te]])
                b0 = ub.ols(X0tr, v[resp["rate_col"]][tr])
                b1 = ub.ols(X1tr, v[resp["rate_col"]][tr])
                sc = v["_m_hat"][te] if resp["scale_by_minutes"] else 1.0
                y = v[resp["target_col"]][te]
                B, A = (X0te @ b0) * sc, (X1te @ b1) * sc
                sst = float(((y - y.mean()) ** 2).sum())
                st.append(dict(response=resp["id"], stratum=sid, season=int(s), n=int(te.sum()),
                               beta_defence=float(b1[-1]),
                               dr2=float((((y - B) ** 2).sum() - ((y - A) ** 2).sum()) / sst)))
                r = st[-1]
                P("  %-7s %-9s season %d  n=%4d  beta=%+.3e  dR2=%+.6f"
                  % (resp["id"], sid, s, r["n"], r["beta_defence"], r["dr2"]))
    sdf = pd.DataFrame(st)

    # ================================================================= T4 jackknife
    ub.hdr("T4 LEAVE-ONE-OPPONENT-SEASON-OUT JACKKNIFE (top tier, ppm, DECISION)")
    base_mask = s02.stratum_mask(m, "DECISION")
    for c in need:
        base_mask &= np.isfinite(v[c])
    tier_all, _ = tiers_for(m, v, base_mask, UCOL)
    mask0 = base_mask & (tier_all == 2)
    full = s05.score(m, v, BASE, mask0, v[DEFENCE], UCOL, False, RESP_PPM)[0]
    clus = m["_cluster"].to_numpy()
    jk = []
    for g in np.unique(clus[mask0]):
        mk = mask0 & (clus != g)
        r = s05.score(m, v, BASE, mk, v[DEFENCE], UCOL, False, RESP_PPM)
        if r:
            jk.append(r[0])
    jk = np.array(jk)
    P("  full dR2=%+.6f   jackknife over %d opponent-seasons: min=%+.6f  median=%+.6f  max=%+.6f  "
      "all positive=%s" % (full, len(jk), jk.min(), float(np.median(jk)), jk.max(),
                           bool((jk > 0).all())))

    # ================================================================= T5 alternative axes
    ub.hdr("T5 IS THE AXIS REALLY USAGE?  Same split on prior MINUTES and on prior PPM")
    ax = []
    for axis, lbl in ((UCOL, "prior_usage_per_game"), ("refB_mpg", "prior_minutes_per_game"),
                      ("refB_ppm", "prior_points_per_minute")):
        for resp in (RESP_PPM, RESP_PTS):
            base_mask = s02.stratum_mask(m, "DECISION")
            for c in need:
                base_mask &= np.isfinite(v[c])
            tier_all, _ = tiers_for(m, v, base_mask, axis)
            for t in (0, 2):
                r = s05.score(m, v, BASE, base_mask & (tier_all == t), v[DEFENCE], UCOL, False, resp)
                if r is None:
                    continue
                ax.append(dict(axis=lbl, response=resp["id"], tier=TN[t], n=int(len(r[1])),
                               dr2=r[0]))
                P("  axis=%-24s %-7s %-8s n=%5d  dR2=%+.6f"
                  % (lbl, resp["id"], TN[t], ax[-1]["n"], ax[-1]["dr2"]))
    axdf = pd.DataFrame(ax)

    # ================================================================= T6 the scale test
    ub.hdr("T6 IS IT MERELY SCALE?  Relative response, and ONE POOLED multiplicative parameter")
    sc_rows = []
    base_mask = s02.stratum_mask(m, "DECISION")
    for c in need:
        base_mask &= np.isfinite(v[c])
    tier_all, _ = tiers_for(m, v, base_mask, UCOL)
    P("  (a) RESPONSE MADE RELATIVE to the player's own strictly-prior rate (y_ppm / refB_ppm).")
    P("      If the tier gradient FLATTENS here, the gradient was scale, not heterogeneity.")
    for t in (0, 1, 2):
        r = s05.score(m, v, BASE, base_mask & (tier_all == t), v[DEFENCE], UCOL, False, RESP_REL)
        if r is None:
            continue
        sc_rows.append(dict(test="relative_response", tier=TN[t], n=int(len(r[1])), dr2=r[0]))
        P("      %-8s n=%5d  dR2 on the RELATIVE response = %+.6f" % (TN[t], len(r[1]), r[0]))
    P("  (b) ONE POOLED interaction of the player's own PRIOR RATE with defence "
      "(a multiplicative opponent adjustment; one parameter, no tiers, no usage).")
    for resp in (RESP_PPM, RESP_PTS):
        for sid in ("POOLED", "DECISION"):
            bm = s02.stratum_mask(m, sid)
            for c in need:
                bm &= np.isfinite(v[c])
            r_int = s05.score(m, v, BASE, bm, v[DEFENCE], "refB_ppm", True, resp)
            r_usg = s05.score(m, v, BASE, bm, v[DEFENCE], UCOL, True, resp)
            if r_int is None:
                continue
            ct = ub.paired_cluster_test(r_int[1], r_int[2], r_int[3], r_int[4], ncl,
                                        n_draws=pr.N_DRAWS, seed=ub.SEED)
            ct.pop("draws_cluster")
            rng = np.random.default_rng(ub.SEED + 99)
            dr = np.empty(N_SWAP)
            for k in range(N_SWAP):
                dv = s05.swap_within_date(m, unit, rng)
                rr = s05.score(m, v, BASE, bm, dv, "refB_ppm", True, resp)
                dr[k] = rr[0] if rr is not None else np.nan
            dr = dr[np.isfinite(dr)]
            p = (1.0 + int((dr >= r_int[0]).sum())) / (len(dr) + 1.0)
            sc_rows.append(dict(test="pooled_rate_x_defence", response=resp["id"], stratum=sid,
                                n=int(len(r_int[1])), dr2=r_int[0], p_swap=p,
                                dr2_usage_x_defence_for_contrast=r_usg[0] if r_usg else np.nan,
                                p_cluster=ct["p_cluster"]))
            P("      %-7s %-9s n=%5d  POOLED prior-rate x defence dR2=%+.6f (swap p=%.4f, "
              "sign-flip p=%.4f)   [preregistered usage x defence, same rows: %+.6f]"
              % (resp["id"], sid, len(r_int[1]), r_int[0], p, ct["p_cluster"],
                 r_usg[0] if r_usg else np.nan))
    scdf = pd.DataFrame(sc_rows)

    tdf.to_csv(os.path.join(ub.OUT, "stress_family_wise.csv"), index=False)
    sdf.to_csv(os.path.join(ub.OUT, "stress_season_stability.csv"), index=False)
    axdf.to_csv(os.path.join(ub.OUT, "stress_alternative_axes.csv"), index=False)
    scdf.to_csv(os.path.join(ub.OUT, "stress_scale_test.csv"), index=False)
    dd = [dict(step="s07_swap_null", cell=c, draw=k, dr2=float(x))
          for c, d in draws_by_cell.items() for k, x in enumerate(d) if k % 2 == 0]
    pd.DataFrame(dd).to_csv(os.path.join(ub.OUT, "permutation_draws_s07.csv"), index=False)

    with open(os.path.join(ub.OUT, "_s07.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha256=h, family_wise_p=p_fw, family_wise_max_z=obs,
                       family_wise_argmax=arg,
                       control_min_p=float(ctrl["p_swap"].min()),
                       control_max_z=float(ctrl["z"].max()),
                       jackknife_min=float(jk.min()), jackknife_median=float(np.median(jk)),
                       jackknife_all_positive=bool((jk > 0).all()), jackknife_full=float(full),
                       tier_table=json.loads(tdf.to_json(orient="records")),
                       season=json.loads(sdf.to_json(orient="records")),
                       axes=json.loads(axdf.to_json(orient="records")),
                       scale=json.loads(scdf.to_json(orient="records"))),
                  fh, indent=2, default=float)
    with open(os.path.join(ub.OUT, "run_log_s07.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote stress_family_wise.csv, stress_season_stability.csv, stress_alternative_axes.csv, "
      "stress_scale_test.csv, permutation_draws_s07.csv, _s07.json")


if __name__ == "__main__":
    main()
