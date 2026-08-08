"""
c04 -- PLACEBO TIERS, RANDOM TIERS, AND THE NEGATIVE CONTROL.

c03 established that restricting to the top tercile and refitting the NON-defence coefficients is
worth MORE than the defence term is credited with.  That is the artefact hypothesis's own premise
confirmed -- the top tercile really does have different baseline relationships.  It does not yet say
whether the DEFENCE gain rides on it.  Two things separate them:

  PLACEBO TIERS -- run the identical machinery on the MIDDLE and BOTTOM terciles.  If the REFIT gain
    appears there too but the DEFENCE gain does not, the refit is a generic property of taking a
    subset and the defence gain is specific to high volume.  If both appear everywhere, the gain is
    about refitting a subset.

  RANDOM TIERS -- refit on random subsets of the same size, %d draws, the whole walk-forward redone
    inside every draw.  This is the null distribution for "refitting any 1,687 rows".  Two variants,
    because a row-level shuffle destroys the player-block structure of the real tiers and could make
    the null too easy: a within-season ROW shuffle and a size-matched PLAYER-SEASON BLOCK assignment.

  NEGATIVE CONTROL -- the whole ladder and the whole decomposition with a PURE NOISE column in place
    of defence.  If the machinery manufactures an increment from nothing, it fires here.

Both the DEFENCE statistic and the REFIT-WITHOUT-DEFENCE statistic are pushed through the random-tier
null, because they are different claims and each needs its own null.
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

__doc__ = __doc__ % cb.N_RANDOM_TIER


def main():
    P = cb.Tee()
    cb.hdr("E1_I0025 c04 -- PLACEBO TIERS, RANDOM TIERS, NEGATIVE CONTROL")
    h, added, dropped = c0.check()
    P("  PREREG hash %s VERIFIED.  specs added=%d dropped=%d" % (h, len(added), len(dropped)))
    m, v, need, ncl, unit = cb.build(P)

    base_mask = cb.s02.stratum_mask(m, "DECISION")
    for c in need:
        base_mask &= np.isfinite(v[c])
    tier, q = cb.tier_labels(m, v, base_mask)

    # ================================================================ placebo tiers
    cb.hdr("PLACEBO TIERS -- the identical machinery on the MIDDLE and BOTTOM terciles")
    rows = []
    for t in (2, 1, 0):
        mask_t = base_mask & (tier == t)
        fl = cb.folds(m, base_mask, mask_t)
        for rid in ("ppm", "points"):
            resp = cb.s02.RESP[rid]
            gd = cb.score_rung(m, v, "L4", fl, v[cb.DEFENCE], tier, resp)
            gn = cb.score_rung(m, v, "L4", fl, v["G01_noise"], tier, resp)
            ro, _ = cb.refit_only(m, v, fl, tier, resp)
            rows.append(dict(kind="REAL_TIER", tier=cb.TN[t], response=rid,
                             n=int(sum(int(te.sum()) for (_, _, _, te) in fl)),
                             defence_gain_L4=gd, refit_without_defence=ro["dr2"],
                             negative_control_noise_gain=gn))
            r = rows[-1]
            P("  %-8s %-7s n=%5d  DEFENCE gain=%+.6f   REFIT-WITHOUT-DEFENCE=%+.6f   "
              "NEGATIVE CONTROL (noise)=%+.6f"
              % (cb.TN[t], rid, r["n"], gd, ro["dr2"], gn))
    P("  READ: if the refit gain is comparable across tiers but the defence gain is not, the refit is "
      "a generic property of subsetting and the defence gain is specific to high volume.")

    # ================================================================ random tiers
    cb.hdr("RANDOM TIERS -- the null distribution for 'refitting any %d rows' (%d draws each)"
           % (int((base_mask & (tier == 2)).sum()), cb.N_RANDOM_TIER))
    fl_real = cb.folds(m, base_mask, base_mask & (tier == 2))
    real = {}
    for rid in ("ppm", "points"):
        resp = cb.s02.RESP[rid]
        real[(rid, "defence")] = cb.score_rung(m, v, "L4", fl_real, v[cb.DEFENCE], tier, resp)
        real[(rid, "refit")] = cb.refit_only(m, v, fl_real, tier, resp)[0]["dr2"]

    draw_rows, null_rows = [], []
    for variant, fn in (("ROWSHUFFLE", cb.random_tier_rowshuffle),
                        ("PLAYERBLOCK", cb.random_tier_playerblock)):
        rng = np.random.default_rng(cb.SEED + 4242)
        acc = {k: [] for k in real}
        sizes, changed = [], []
        for k in range(cb.N_RANDOM_TIER):
            pt = fn(tier, base_mask, m, rng)
            pm = base_mask & (pt == 2)
            sizes.append(int(pm.sum()))
            changed.append(float(np.mean(pt[base_mask] != tier[base_mask])))
            fl = cb.folds(m, base_mask, pm)
            if not fl:
                continue
            for rid in ("ppm", "points"):
                resp = cb.s02.RESP[rid]
                acc[(rid, "defence")].append(cb.score_rung(m, v, "L4", fl, v[cb.DEFENCE], pt, resp))
                acc[(rid, "refit")].append(cb.refit_only(m, v, fl, pt, resp)[0]["dr2"])
        P("  %-12s pseudo-top-tier size: median %d (real %d);  %.1f%% of rows get a different tier "
          "label -- THE PLACEBO ACTUALLY PERTURBS"
          % (variant, int(np.median(sizes)), int((base_mask & (tier == 2)).sum()),
             100 * float(np.mean(changed))))
        for (rid, stat), d in acc.items():
            d = np.array([x for x in d if np.isfinite(x)])
            o = real[(rid, stat)]
            p = (1.0 + int((d >= o).sum())) / (len(d) + 1.0)
            null_rows.append(dict(variant=variant, response=rid, statistic=stat, observed=o,
                                  n_draws=int(len(d)), null_mean=float(d.mean()),
                                  null_sd=float(d.std(ddof=1)),
                                  null_p95=float(np.percentile(d, 95)),
                                  null_max=float(d.max()),
                                  z=float((o - d.mean()) / d.std(ddof=1)), p_onesided=p))
            r = null_rows[-1]
            P("  %-12s %-7s %-8s observed=%+.6f   null %+.6f +- %.6f  p95=%+.6f  max=%+.6f  "
              "z=%+.2f  p=%.4f"
              % (variant, rid, stat, o, r["null_mean"], r["null_sd"], r["null_p95"], r["null_max"],
                 r["z"], p))
            for j in range(0, len(d), 2):
                draw_rows.append(dict(step="c04_random_tier", variant=variant, response=rid,
                                      statistic=stat, draw=j, value=float(d[j])))

    # ================================================================ negative control, full ladder
    cb.hdr("NEGATIVE CONTROL -- the WHOLE ladder with a pure noise column in place of defence")
    nc = []
    for rid in ("ppm", "points"):
        resp = cb.s02.RESP[rid]
        for rung in ("L1", "L2", "L3", "L4"):
            gn = cb.score_rung(m, v, rung, fl_real, v["G01_noise"], tier, resp)
            gr = cb.score_rung(m, v, rung, fl_real, v[cb.DEFENCE], tier, resp)
            nc.append(dict(response=rid, rung=rung, noise_dr2=gn, real_dr2=gr,
                           noise_share_of_real=gn / gr if gr else np.nan))
            P("  %-7s %-3s  noise column dR2=%+.6f   (real defence %+.6f)  share=%.3f"
              % (rid, rung, gn, gr, nc[-1]["noise_share_of_real"]))
        tn, _ = cb.frozen_transplant(m, v, fl_real, v["G01_noise"], tier, resp, freeze="pooled")
        nc.append(dict(response=rid, rung="TRANSPLANT_pooled_frozen", noise_dr2=tn["dr2"],
                       real_dr2=np.nan, noise_share_of_real=np.nan))
        P("  %-7s transplant(pooled-frozen) with noise dR2=%+.6f" % (rid, tn["dr2"]))
    ncdf = pd.DataFrame(nc)
    ctrl_clean = bool((ncdf["noise_dr2"] < 0.005).all())
    P("  NEGATIVE CONTROL: max noise dR2 = %+.6f  ->  %s"
      % (float(ncdf["noise_dr2"].max()),
         "CLEAN (nothing manufactured)" if ctrl_clean else "*** A CONTROL FIRED ***"))

    pd.DataFrame(rows).to_csv(os.path.join(cb.OUT, "placebo_tiers.csv"), index=False)
    ndf = pd.DataFrame(null_rows)
    ndf.to_csv(os.path.join(cb.OUT, "random_tier_null.csv"), index=False)
    ncdf.to_csv(os.path.join(cb.OUT, "negative_control.csv"), index=False)
    pd.DataFrame(draw_rows).to_csv(os.path.join(cb.OUT, "permutation_draws_c04.csv"), index=False)

    with open(os.path.join(cb.OUT, "_c04.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha256=h, placebo_tiers=json.loads(pd.DataFrame(rows).to_json(orient="records")),
                       random_tier_null=json.loads(ndf.to_json(orient="records")),
                       negative_control=json.loads(ncdf.to_json(orient="records")),
                       control_clean=ctrl_clean), fh, indent=2, default=float)
    P.write(os.path.join(cb.OUT, "run_log_c04.txt"))


if __name__ == "__main__":
    main()
