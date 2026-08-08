"""
c05 -- WHICH AXIS CARRIES IT, AND ARE THE AXES SEPARABLE AT ALL?

D098 records that prior minutes (+0.019177) and prior points-per-minute (+0.026204) work as well as
or better than prior usage (+0.023863), so "usage" is a proxy for "this player scores a lot" and the
mechanism is unidentified.  This script asks whether the three axes can be told apart:

  A. how collinear are they, on the rows that matter (Pearson and Spearman, and the overlap of the
     three top terciles as a Jaccard index);
  B. the D098 statistic on each axis, reproduced;
  C. the DISAGREEMENT rows -- top tercile on one axis but NOT on another.  If the gain lives on one
     axis's disagreement set and not the other's, the axes are separable.  If both disagreement sets
     carry it, or if they are too small to measure, they are not;
  D. a JOINT pooled model carrying BOTH axes' tier dummies interacted with defence, so each axis is
     asked what it adds GIVEN the other.

PREREGISTERED RULE: separable only if the gain is present on one axis's top tercile and below 0.30x
on another's, measured on the DISAGREEMENT rows.  If the disagreement sets are too small or all axes
carry it, the honest answer is COLLINEAR AND NOT SEPARABLE, and that is the result, not a failure.

ALSO IN THIS SCRIPT, AND LABELLED POST-HOC: the within-date opponent-swap null for the CONCENTRATION
increment (the pooled tier-step model's gain over one pooled defence coefficient).  It was computed
after c04's random-tier null came back marginal.  The quantity itself is preregistered (it is a
ladder increment) and the null is the preregistered headline null; only the decision to null THIS
increment is post-hoc, and it is reported as a diagnostic, never as a verdict input.
"""
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np       # noqa: E402
import pandas as pd      # noqa: E402
import cbase as cb       # noqa: E402
import c00_prereg as c0  # noqa: E402

AXES = [(cb.UCOL, "prior_usage_per_game"), ("refB_mpg", "prior_minutes_per_game"),
        ("refB_ppm", "prior_points_per_minute")]


def sse(y, p):
    return float(((y - p) ** 2).sum())


def main():
    P = cb.Tee()
    cb.hdr("E1_I0025 c05 -- AXIS RESOLUTION")
    h, added, dropped = c0.check()
    P("  PREREG hash %s VERIFIED.  specs added=%d dropped=%d" % (h, len(added), len(dropped)))
    m, v, need, ncl, unit = cb.build(P)
    base_mask = cb.s02.stratum_mask(m, "DECISION")
    for c in need:
        base_mask &= np.isfinite(v[c])

    # ------------------------------------------------------------------ A. collinearity
    cb.hdr("A. HOW COLLINEAR ARE THE THREE AXES ON THE DECISION STRATUM?")
    rows = []
    tiers = {}
    for col, lbl in AXES:
        tiers[lbl], _ = cb.tier_labels(m, v, base_mask, axis=col)
    for i in range(len(AXES)):
        for j in range(i + 1, len(AXES)):
            a, la = AXES[i]
            b, lb = AXES[j]
            x, y = v[a][base_mask], v[b][base_mask]
            pear = float(np.corrcoef(x, y)[0, 1])
            spear = cb.ub.spearman(x, y)
            ta = base_mask & (tiers[la] == 2)
            tb = base_mask & (tiers[lb] == 2)
            jac = float((ta & tb).sum()) / float((ta | tb).sum())
            rows.append(dict(section="collinearity", axis_a=la, axis_b=lb, pearson=pear,
                             spearman=spear, jaccard_top_tercile=jac,
                             n_a=int(ta.sum()), n_b=int(tb.sum()),
                             n_both=int((ta & tb).sum()),
                             n_a_only=int((ta & ~tb).sum()), n_b_only=int((tb & ~ta).sum())))
            r = rows[-1]
            P("  %-24s vs %-24s  pearson %+.4f  spearman %+.4f  top-tercile Jaccard %.4f  "
              "(both %d, %s only %d, %s only %d)"
              % (la, lb, pear, spear, jac, r["n_both"], la, r["n_a_only"], lb, r["n_b_only"]))

    # ------------------------------------------------------------------ B. per-axis gain
    cb.hdr("B. THE D098 STATISTIC ON EACH AXIS (reproduction of its alternative-axes table)")
    D098_AX = {("prior_usage_per_game", "ppm"): 0.023862917871899685,
               ("prior_minutes_per_game", "ppm"): 0.019176724230180454,
               ("prior_points_per_minute", "ppm"): 0.02620440823647721,
               ("prior_usage_per_game", "points"): 0.018702810112816298,
               ("prior_minutes_per_game", "points"): 0.01647374624233155,
               ("prior_points_per_minute", "points"): 0.017019217299656237}
    for col, lbl in AXES:
        t = tiers[lbl]
        fl = cb.folds(m, base_mask, base_mask & (t == 2))
        for rid in ("ppm", "points"):
            resp = cb.s02.RESP[rid]
            g = cb.score_rung(m, v, "L4", fl, v[cb.DEFENCE], t, resp)
            gp = cb.score_rung(m, v, "L1", fl, v[cb.DEFENCE], t, resp)
            ro, _ = cb.refit_only(m, v, fl, t, resp)
            pub = D098_AX[(lbl, rid)]
            rows.append(dict(section="per_axis", axis=lbl, response=rid,
                             n=int(sum(int(te.sum()) for (_, _, _, te) in fl)),
                             defence_gain_L4=g, pooled_defence_L1=gp,
                             refit_without_defence=ro["dr2"],
                             D098_published=pub, abs_delta_vs_D098=abs(g - pub)))
            r = rows[-1]
            P("  axis=%-24s %-7s n=%5d  L4=%+.6f (D098 %+.6f, |d|=%.2e)  L1(pooled)=%+.6f  "
              "refit-without-defence=%+.6f"
              % (lbl, rid, r["n"], g, pub, r["abs_delta_vs_D098"], gp, ro["dr2"]))

    # ------------------------------------------------------------------ C. disagreement rows
    cb.hdr("C. THE DISAGREEMENT ROWS -- top tercile on one axis but NOT on another")
    for i in range(len(AXES)):
        for j in range(len(AXES)):
            if i == j:
                continue
            la, lb = AXES[i][1], AXES[j][1]
            ta = base_mask & (tiers[la] == 2)
            tb = base_mask & (tiers[lb] == 2)
            mk = ta & ~tb
            fl = cb.folds(m, base_mask, mk)
            n_sc = sum(int(te.sum()) for (_, _, _, te) in fl) if fl else 0
            if not fl:
                rows.append(dict(section="disagreement", top_on=la, not_top_on=lb,
                                 n_frame=int(mk.sum()), n_scored=0, defence_gain_L4=np.nan,
                                 note="TOO SMALL to run the walk-forward (fold gating failed)"))
                P("  top on %-24s but NOT on %-24s : %4d frame rows -- TOO SMALL, fold gating failed"
                  % (la, lb, int(mk.sum())))
                continue
            g = cb.score_rung(m, v, "L4", fl, v[cb.DEFENCE], tiers[la], cb.s02.RESP["ppm"])
            gp = cb.score_rung(m, v, "L1", fl, v[cb.DEFENCE], tiers[la], cb.s02.RESP["ppm"])
            rows.append(dict(section="disagreement", top_on=la, not_top_on=lb,
                             n_frame=int(mk.sum()), n_scored=int(n_sc), defence_gain_L4=g,
                             pooled_defence_L1=gp, note=""))
            P("  top on %-24s but NOT on %-24s : n=%4d  L4=%+.6f  L1(pooled)=%+.6f"
              % (la, lb, n_sc, g, gp))

    # ------------------------------------------------------------------ D. joint pooled model
    cb.hdr("D. JOINT POOLED MODEL -- each axis asked what it adds GIVEN the other")
    P("  Arm B: [1, COMPLETE reference, usage, tier dummies of BOTH axes].")
    P("  Arm A: arm B + defence + BOTH axes' tier dummies x centred defence.")
    P("  The incremental dR2 of dropping one axis's interaction pair from arm A is what that axis "
      "adds given the other.")
    for i in range(len(AXES)):
        for j in range(i + 1, len(AXES)):
            la, lb = AXES[i][1], AXES[j][1]
            ta, tb = tiers[la], tiers[lb]
            mk = base_mask & (ta == 2)
            fl = cb.folds(m, base_mask, mk)
            for rid in ("ppm",):
                resp = cb.s02.RESP[rid]
                yy, pfull, pB, pdropA, pdropB = [], [], [], [], []
                for (s, tr_p, tr_t, te) in fl:
                    dc = float(v[cb.DEFENCE][tr_p].mean())

                    def X(sel, which):
                        cols = cb.Z(v, sel) + cb.dummies(ta, sel) + cb.dummies(tb, sel)
                        if which == "B":
                            return np.column_stack(cols)
                        d = v[cb.DEFENCE][sel]
                        cols = cols + [d]
                        if which in ("full", "dropB"):
                            cols += [x * (d - dc) for x in cb.dummies(ta, sel)]
                        if which in ("full", "dropA"):
                            cols += [x * (d - dc) for x in cb.dummies(tb, sel)]
                        return np.column_stack(cols)

                    yr = v[resp["rate_col"]]
                    sc = v["_m_hat"][te] if resp["scale_by_minutes"] else 1.0
                    for nm, store in (("B", pB), ("full", pfull), ("dropA", pdropA),
                                      ("dropB", pdropB)):
                        b = cb.ub.ols(X(tr_p, nm), yr[tr_p])
                        store.append((X(te, nm) @ b) * sc)
                    yy.append(v[resp["target_col"]][te])
                y = np.concatenate(yy)
                sst = float(((y - y.mean()) ** 2).sum())
                F, B_, DA, DB = (np.concatenate(pfull), np.concatenate(pB),
                                 np.concatenate(pdropA), np.concatenate(pdropB))
                rows.append(dict(section="joint", axis_a=la, axis_b=lb, response=rid,
                                 n=int(len(y)),
                                 dr2_full_over_B=float((sse(y, B_) - sse(y, F)) / sst),
                                 dr2_added_by_a_given_b=float((sse(y, DA) - sse(y, F)) / sst),
                                 dr2_added_by_b_given_a=float((sse(y, DB) - sse(y, F)) / sst)))
                r = rows[-1]
                P("  scored on %s's top tercile (n=%d): full defence family %+.6f | %s adds %+.6f "
                  "given %s | %s adds %+.6f given %s"
                  % (la, r["n"], r["dr2_full_over_B"], la, r["dr2_added_by_a_given_b"], lb,
                     lb, r["dr2_added_by_b_given_a"], la))

    # ------------------------------------------------------------------ concentration increment null
    cb.hdr("POST-HOC DIAGNOSTIC -- swap null for the CONCENTRATION increment (L3 over L1)")
    P("  Computed AFTER c04's random-tier null came back marginal. The quantity is a preregistered "
      "ladder increment and the null is the preregistered headline null; only the decision to null "
      "THIS increment is post-hoc. Reported as a diagnostic, NEVER as a verdict input.")
    tier = tiers["prior_usage_per_game"]
    fl = cb.folds(m, base_mask, base_mask & (tier == 2))
    conc = []
    for rid in ("ppm", "points"):
        resp = cb.s02.RESP[rid]

        def inc(dv):
            _, y, A3, _, _, sst, _ = cb.score_rung(m, v, "L3", fl, dv, tier, resp, ret_pred=True)
            _, _, A1, _, _, _, _ = cb.score_rung(m, v, "L1", fl, dv, tier, resp, ret_pred=True)
            return float((sse(y, A1) - sse(y, A3)) / sst)

        o = inc(v[cb.DEFENCE])
        rng = np.random.default_rng(cb.SEED + 99)
        d = np.array([inc(cb.s05.swap_within_date(m, unit, rng)) for _ in range(cb.N_SWAP)])
        d = d[np.isfinite(d)]
        p = (1.0 + int((d >= o).sum())) / (len(d) + 1.0)
        conc.append(dict(response=rid, increment="L3_over_L1_concentration", observed=o,
                         null_mean=float(d.mean()), null_sd=float(d.std(ddof=1)),
                         null_p95=float(np.percentile(d, 95)),
                         z=float((o - d.mean()) / d.std(ddof=1)), p_swap=p, n_draws=int(len(d))))
        r = conc[-1]
        P("  %-7s L3-over-L1 = %+.6f   swap null %+.6f +- %.6f  p95=%+.6f  z=%+.2f  p=%.4f"
          % (rid, o, r["null_mean"], r["null_sd"], r["null_p95"], r["z"], p))

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(cb.OUT, "axis_resolution.csv"), index=False)
    cdf = pd.DataFrame(conc)
    cdf.to_csv(os.path.join(cb.OUT, "concentration_increment_null.csv"), index=False)
    with open(os.path.join(cb.OUT, "_c05.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha256=h, axis=json.loads(df.to_json(orient="records")),
                       concentration_null=json.loads(cdf.to_json(orient="records"))),
                  fh, indent=2, default=float)
    P.write(os.path.join(cb.OUT, "run_log_c05.txt"))


if __name__ == "__main__":
    main()
