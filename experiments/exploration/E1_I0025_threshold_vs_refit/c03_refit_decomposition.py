"""
c03 -- SEPARATING THE REFIT FROM THE SIGNAL DIRECTLY.

The pooled test in c02 is not conclusive on its own, so this script measures the refit's contribution
without going through the defence term at all.

1. REFIT WITHOUT DEFENCE.  Restrict to the top tercile and refit every coefficient EXCEPT defence --
   i.e. the no-defence base fitted POOLED versus the SAME no-defence base fitted TIER-RESTRICTED,
   scored on the identical top-tercile rows.  NO DEFENCE COLUMN IS PRESENT IN EITHER ARM.  Whatever
   this recovers is the refit's own contribution.  THIS IS THE SINGLE CLEANEST MEASUREMENT OF THE
   ARTEFACT HYPOTHESIS.

2. TRANSPLANT.  Freeze the tier-restricted model's NON-DEFENCE coefficients and add a defence term
   fitted on the frozen model's training residual (centred defence, no free intercept, so the frozen
   level really is frozen).  Does the defence term still earn its keep when it may not re-shuffle the
   other coefficients?  The same with the POOLED non-defence coefficients frozen, which is the
   version with no tier refit anywhere.

3. ABSOLUTE ACCOUNTING.  Every dR2 in this family is a ratio to the SST of whichever rows it is
   scored on, and the two anchors D098 quotes are scored on DIFFERENT row sets.  The absolute SSE
   reduction is therefore reported alongside every ratio, and the pooled model's SSE reduction is
   split between the top tercile and the rest, because a term that helps high-volume rows and HURTS
   low-volume ones is a different object from one that helps everywhere and is merely measured
   against a smaller denominator in one place.
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


def main():
    P = cb.Tee()
    cb.hdr("E1_I0025 c03 -- REFIT vs SIGNAL, MEASURED DIRECTLY")
    h, added, dropped = c0.check()
    P("  PREREG hash %s VERIFIED.  specs added=%d dropped=%d" % (h, len(added), len(dropped)))
    m, v, need, ncl, unit = cb.build(P)

    rows = []
    for sid in ("DECISION", "POOLED"):
        base_mask = cb.s02.stratum_mask(m, sid)
        for c in need:
            base_mask &= np.isfinite(v[c])
        tier, q = cb.tier_labels(m, v, base_mask)
        for t in (2, 1, 0):
            mask_t = base_mask & (tier == t)
            fl = cb.folds(m, base_mask, mask_t)
            if not fl:
                continue
            for rid in ("ppm", "points"):
                resp = cb.s02.RESP[rid]
                # ---------- the anchor: D098's tier-restricted defence increment ----------
                g_refit, y, A, B, C, sst, bet = cb.score_rung(m, v, "L4", fl, v[cb.DEFENCE], tier,
                                                              resp, ret_pred=True)
                # ---------- 1. REFIT WITHOUT DEFENCE ----------
                ro, (yr, Ar, Br, Cr, sstr) = cb.refit_only(m, v, fl, tier, resp)
                ct_r = cb.ub.paired_cluster_test(yr, Ar, Br, Cr, ncl, n_draws=2000, seed=cb.SEED)
                ct_r.pop("draws_cluster")
                # ---------- 2. TRANSPLANTS ----------
                tt, _ = cb.frozen_transplant(m, v, fl, v[cb.DEFENCE], tier, resp, freeze="tier")
                tp, _ = cb.frozen_transplant(m, v, fl, v[cb.DEFENCE], tier, resp, freeze="pooled")
                # ---------- 3. the pooled one-coefficient rung, same rows ----------
                g_pool = cb.score_rung(m, v, "L1", fl, v[cb.DEFENCE], tier, resp)
                g_step = cb.score_rung(m, v, "L3", fl, v[cb.DEFENCE], tier, resp)
                rows.append(dict(
                    stratum=sid, tier=cb.TN[t], response=rid, n_scored=int(len(y)), sst=sst,
                    sd_response=float(np.std(y, ddof=1)),
                    G_refit_L4=g_refit, G_step_L3=g_step, G_pooled_main_L1=g_pool,
                    R_nodef_refit_only=ro["dr2"],
                    R_nodef_p_cluster=ct_r["p_cluster"],
                    R_nodef_share_of_G_refit=(ro["dr2"] / g_refit if g_refit else np.nan),
                    transplant_tier_frozen_dr2=tt["dr2"],
                    transplant_tier_frozen_share=(tt["dr2"] / g_refit if g_refit else np.nan),
                    transplant_tier_gamma=tt["gamma_mean"],
                    transplant_pooled_frozen_dr2=tp["dr2"],
                    transplant_pooled_frozen_share=(tp["dr2"] / g_refit if g_refit else np.nan),
                    abs_sse_reduction_L4=g_refit * sst, abs_sse_reduction_L1=g_pool * sst,
                    abs_sse_reduction_refit_only=ro["dr2"] * sst))
                r = rows[-1]
                P("  %-9s %-8s %-7s n=%5d | G_refit(L4)=%+.6f  G_step(L3)=%+.6f  "
                  "G_pooled(L1)=%+.6f" % (sid, cb.TN[t], rid, r["n_scored"], g_refit, g_step,
                                          g_pool))
                P("                              | REFIT WITHOUT DEFENCE = %+.6f  (%.1f%% of "
                  "G_refit, cluster p=%.4f)"
                  % (ro["dr2"], 100 * r["R_nodef_share_of_G_refit"], ct_r["p_cluster"]))
                P("                              | transplant tier-frozen = %+.6f (%.0f%%)  "
                  "pooled-frozen = %+.6f (%.0f%%)"
                  % (tt["dr2"], 100 * r["transplant_tier_frozen_share"], tp["dr2"],
                     100 * r["transplant_pooled_frozen_share"]))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(cb.OUT, "refit_decomposition.csv"), index=False)

    # ================================================================ absolute accounting
    cb.hdr("ABSOLUTE ACCOUNTING -- WHERE THE POOLED DEFENCE COEFFICIENT'S SSE REDUCTION LANDS")
    P("  The SAME pooled model, the SAME fitted coefficients. Only the rows the dR2 is computed on "
      "change. If the reduction on the top tercile EXCEEDS the reduction over the whole stratum, the "
      "term genuinely helps high-volume rows and HURTS the others -- concentration, not a smaller "
      "denominator.")
    acc = []
    for sid in ("DECISION",):
        base_mask = cb.s02.stratum_mask(m, sid)
        for c in need:
            base_mask &= np.isfinite(v[c])
        tier, q = cb.tier_labels(m, v, base_mask)
        for rid in ("ppm", "points"):
            resp = cb.s02.RESP[rid]
            fl_all = cb.folds(m, base_mask, base_mask)
            d_all, y, A, B, C, sst_all, _ = cb.score_rung(m, v, "L1", fl_all, v[cb.DEFENCE], tier,
                                                          resp, ret_pred=True)
            tl = np.concatenate([tier[te] for (_, _, _, te) in fl_all])
            red = (y - B) ** 2 - (y - A) ** 2
            tot = float(red.sum())
            per = {t: float(red[tl == t].sum()) for t in (0, 1, 2)}
            sst_t = {t: float(((y[tl == t] - y[tl == t].mean()) ** 2).sum()) for t in (0, 1, 2)}
            acc.append(dict(stratum=sid, response=rid, n=int(len(y)), sst_all=sst_all,
                            dr2_on_all_rows=d_all, total_sse_reduction=tot,
                            sse_reduction_T1=per[0], sse_reduction_T2=per[1],
                            sse_reduction_T3=per[2],
                            dr2_T3_own_sst=per[2] / sst_t[2],
                            dr2_T3_common_sst=per[2] / sst_all,
                            sd_ratio_T3_over_all=float(np.std(y[tl == 2], ddof=1)
                                                       / np.std(y, ddof=1))))
            a = acc[-1]
            P("  %-7s pooled one-coefficient defence: total SSE reduction %+.4f over %d rows"
              % (rid, tot, len(y)))
            P("          T1 %+.4f   T2 %+.4f   T3 %+.4f   -> the top tercile alone accounts for "
              "%.0f%% of a reduction that is %s in the other two tiers"
              % (per[0], per[1], per[2], 100 * per[2] / tot,
                 "NEGATIVE" if (per[0] + per[1]) < 0 else "positive"))
            P("          dR2 on T3 with T3's own SST = %+.6f ; with the WHOLE stratum's SST = "
              "%+.6f ; sd(T3)/sd(all) = %.4f"
              % (a["dr2_T3_own_sst"], a["dr2_T3_common_sst"], a["sd_ratio_T3_over_all"]))
    adf = pd.DataFrame(acc)
    adf.to_csv(os.path.join(cb.OUT, "absolute_accounting.csv"), index=False)

    with open(os.path.join(cb.OUT, "_c03.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha256=h, decomposition=json.loads(res.to_json(orient="records")),
                       accounting=json.loads(adf.to_json(orient="records"))), fh, indent=2,
                  default=float)
    P.write(os.path.join(cb.OUT, "run_log_c03.txt"))


if __name__ == "__main__":
    main()
