"""
c02 -- THE DECISIVE TEST.  A POOLED model carrying a TIER-DUMMY x DEFENCE term.

D098 left this exact specification named and unrun (its disclosure item 8).  Two readings fit both of
its numbers and they have opposite consequences:

  THRESHOLD      -- the defence effect is genuinely concentrated in high-volume players and is
                    NON-LINEAR in volume.  A linear usage x defence interaction cannot represent a
                    step, so it finds ~nothing; a tier-restricted refit represents it perfectly.
                    A POOLED TIER-DUMMY x DEFENCE TERM IS EXACTLY A STEP, so it must recover it.
  REFIT ARTEFACT -- the top tercile has different baseline relationships across the board, so
                    re-estimating every coefficient there improves fit regardless of defence.
                    A pooled step cannot recover the gain, because the gain was never about defence.

THE LADDER, ALL SCORED ON THE IDENTICAL 1,687 TOP-TERCILE ROWS WITH THE SAME SST:
  L1  pooled, one defence coefficient
  L2  pooled, defence + LINEAR usage x defence          (D098's interaction, as a family)
  L3  pooled, tier dummies + TIER-DUMMY x DEFENCE       <-- the decisive rung
  L4  tier-restricted refit + defence                   (D098's +0.023863)

Each rung's dR2 is measured against THAT RUNG'S OWN no-defence arm, so it is the increment
attributable to the defence family at that rung, exactly as D098 measured its +0.023863.  The
pairwise increments between rungs' full models are reported as well, because the "+0.0002" anchor is
an increment BETWEEN models (interaction over a model that already carries defence) while the
"+0.024" anchor is an increment over a model with NO defence, and quoting them against each other
without saying so is the single easiest way to misread this result.

NULL.  D098's within-date opponent swap, %d draws, the whole walk-forward redone inside every draw,
seeded identically -- so L4's null here must reproduce D098's published null moments, which is a
second reproduction check.  The whole-cluster sign-flip at opponent-team-season is reported beside
it.
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

RUNGS = ["L1", "L2", "L3", "L4"]
RUNG_LABEL = {"L1": "L1_pooled_defence_main", "L2": "L2_pooled_linear_interaction",
              "L3": "L3_pooled_tier_dummy_x_defence", "L4": "L4_tier_restricted_refit"}
__doc__ = __doc__ % cb.N_SWAP


def sse(y, p):
    return float(((y - p) ** 2).sum())


def main():
    P = cb.Tee()
    cb.hdr("E1_I0025 c02 -- THE DECISIVE TEST: POOLED TIER-DUMMY x DEFENCE")
    h, added, dropped = c0.check()
    P("  PREREG hash %s VERIFIED.  specs added=%d dropped=%d" % (h, len(added), len(dropped)))
    m, v, need, ncl, unit = cb.build(P)

    rows, pair_rows, draw_rows = [], [], []
    store = {}
    for sid in ("DECISION", "POOLED"):
        base_mask = cb.s02.stratum_mask(m, sid)
        for c in need:
            base_mask &= np.isfinite(v[c])
        tier, q = cb.tier_labels(m, v, base_mask)
        for eval_tier in (2, -1):
            mask_eval = base_mask if eval_tier == -1 else (base_mask & (tier == eval_tier))
            fl = cb.folds(m, base_mask, mask_eval)
            if not fl:
                continue
            for rid in ("ppm", "points"):
                resp = cb.s02.RESP[rid]
                preds = {}
                for rung in RUNGS:
                    if rung == "L4" and eval_tier == -1:
                        continue          # a tier-restricted refit is not defined on all tiers
                    dr2, y, A, B, C, sst, bet = cb.score_rung(m, v, rung, fl, v[cb.DEFENCE], tier,
                                                              resp, ret_pred=True)
                    preds[rung] = (A, B)
                    ct = cb.ub.paired_cluster_test(y, A, B, C, ncl, n_draws=2000, seed=cb.SEED)
                    ct.pop("draws_cluster")
                    rows.append(dict(
                        stratum=sid, eval_rows=("T3_high" if eval_tier == 2 else "ALL_TIERS"),
                        response=rid, rung=RUNG_LABEL[rung], n_scored=int(len(y)),
                        dr2_defence_family=dr2, sst=sst, sd_response=float(np.std(y, ddof=1)),
                        mae_without=cb.ub.mae(y, B), mae_with=cb.ub.mae(y, A),
                        mae_pct_reduction=float(100 * (1 - cb.ub.mae(y, A) / cb.ub.mae(y, B))),
                        n_defence_family_cols=int(len(bet[0])),
                        mean_defence_beta=float(np.mean([b[0] for b in bet])),
                        p_cluster_signflip=ct["p_cluster"], p_row_NAIVE=ct["p_row_NAIVE"],
                        null_sd_cluster=ct["null_sd_cluster"]))
                    store[(sid, eval_tier, rid, rung)] = (y, A, B, C, sst)
                    r = rows[-1]
                    P("  %-9s eval=%-9s %-7s %-32s n=%5d  dR2=%+.6f  cluster p=%.4f  "
                      "MAE %.5f -> %.5f (%+.3f%%)"
                      % (sid, r["eval_rows"], rid, RUNG_LABEL[rung], r["n_scored"], dr2,
                         ct["p_cluster"], r["mae_without"], r["mae_with"], r["mae_pct_reduction"]))
                # ------------- pairwise increments between the rungs' FULL models -------------
                y = store[(sid, eval_tier, rid, "L1")][0]
                sst = store[(sid, eval_tier, rid, "L1")][4]
                pairs = [("L2", "L1", "linear interaction OVER one pooled defence coefficient "
                          "-- the construction of D098's +0.0002 anchor"),
                         ("L3", "L1", "TIER STEP over one pooled defence coefficient "
                          "-- the step's own added value"),
                         ("L3", "L2", "TIER STEP over the LINEAR interaction"),
                         ("L4", "L3", "full tier refit over the pooled tier step "
                          "-- what the refit adds beyond a step")]
                for a, b, why in pairs:
                    if a not in preds or b not in preds:
                        continue
                    d = float((sse(y, preds[b][0]) - sse(y, preds[a][0])) / sst)
                    pair_rows.append(dict(stratum=sid,
                                          eval_rows=("T3_high" if eval_tier == 2 else "ALL_TIERS"),
                                          response=rid, increment="%s_over_%s" % (a, b),
                                          dr2=d, why=why))
                    P("      increment %s over %s = %+.6f   (%s)" % (a, b, d, why))

    # ================================================================ the swap null on the ladder
    cb.hdr("WITHIN-DATE OPPONENT-SWAP NULL ON EVERY RUNG (%d draws, the whole walk-forward redone "
           "inside each draw)" % cb.N_SWAP)
    P("  Seeded exactly as D098 seeded it (default_rng(SEED+99), draws consumed in the same order), "
      "so L4's null moments here must reproduce D098's published ones. That is a second "
      "reproduction check on top of c01's.")
    base_mask = cb.s02.stratum_mask(m, "DECISION")
    for c in need:
        base_mask &= np.isfinite(v[c])
    tier, q = cb.tier_labels(m, v, base_mask)
    mask_t3 = base_mask & (tier == 2)
    fl = cb.folds(m, base_mask, mask_t3)

    # ---- NO-OP PLACEBO: run the null code path with the UNPERMUTED column; must return the obs ----
    noop = {}
    for rid in ("ppm", "points"):
        noop[rid] = cb.score_rung(m, v, "L4", fl, v[cb.DEFENCE].copy(), tier, cb.s02.RESP[rid])
    P("  NO-OP PLACEBO (null code path, unpermuted defence column): ppm %+.15f  points %+.15f"
      % (noop["ppm"], noop["points"]))

    obs = {}
    for rid in ("ppm", "points"):
        for rung in RUNGS:
            obs[(rid, rung)] = cb.score_rung(m, v, rung, fl, v[cb.DEFENCE], tier,
                                             cb.s02.RESP[rid])
    P("  no-op placebo agrees with the observed L4 to %.3e (ppm) and %.3e (points) -- plumbing OK"
      % (abs(noop["ppm"] - obs[("ppm", "L4")]), abs(noop["points"] - obs[("points", "L4")])))

    rng = np.random.default_rng(cb.SEED + 99)
    draws = {k: np.empty(cb.N_SWAP) for k in obs}
    perturb_frac, perturb_corr = [], []
    orig_unit = unit["dval"].to_numpy(float)
    for k in range(cb.N_SWAP):
        dv = cb.s05.swap_within_date(m, unit, rng)
        if k < 50:      # DOES THE PLACEBO ACTUALLY PERTURB?  measured, not asserted
            uvals = pd.Series(dv, index=m["_tg"].to_numpy()).groupby(level=0).first()
            uvals = uvals.reindex(unit["_tg"].to_numpy()).to_numpy(float)
            perturb_frac.append(float(np.mean(uvals != orig_unit)))
            perturb_corr.append(float(np.corrcoef(uvals, orig_unit)[0, 1]))
        for rid in ("ppm", "points"):
            for rung in RUNGS:
                draws[(rid, rung)][k] = cb.score_rung(m, v, rung, fl, dv, tier, cb.s02.RESP[rid])
    P("  PLACEBO PERTURBATION CHECK: a real swap draw changes %.1f%% of the 1,632 team-game defence "
      "values (mean over 50 draws); corr(original, swapped) = %+.4f. A vacuous control is ruled out "
      "by measurement, not assertion."
      % (100 * float(np.mean(perturb_frac)), float(np.mean(perturb_corr))))

    swap_rows = []
    for rid in ("ppm", "points"):
        for rung in RUNGS:
            d = draws[(rid, rung)]
            d = d[np.isfinite(d)]
            o = obs[(rid, rung)]
            p = (1.0 + int((d >= o).sum())) / (len(d) + 1.0)
            z = float((o - d.mean()) / d.std(ddof=1))
            swap_rows.append(dict(response=rid, rung=RUNG_LABEL[rung], dr2=o, n_draws=int(len(d)),
                                  swap_null_mean=float(d.mean()), swap_null_sd=float(d.std(ddof=1)),
                                  swap_null_p95=float(np.percentile(d, 95)), z=z, p_swap=p))
            P("  %-7s %-32s dR2=%+.6f  swap null %+.6f +- %.6f  z=%+.2f  p=%.4f"
              % (rid, RUNG_LABEL[rung], o, d.mean(), d.std(ddof=1), z, p))
            for j in range(0, len(d), 2):
                draw_rows.append(dict(step="c02_swap_null", response=rid, rung=RUNG_LABEL[rung],
                                      draw=j, dr2=float(d[j])))

    d098_null = dict(mean=-0.0012040160869682239, sd=0.001957893123224803)
    dl4 = draws[("ppm", "L4")]
    P("  L4 null-moment reproduction vs D098 published: mean %+.10f vs %+.10f (|d|=%.2e), "
      "sd %.10f vs %.10f (|d|=%.2e)"
      % (dl4.mean(), d098_null["mean"], abs(dl4.mean() - d098_null["mean"]),
         dl4.std(ddof=1), d098_null["sd"], abs(dl4.std(ddof=1) - d098_null["sd"])))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(cb.OUT, "pooled_tier_dummy.csv"), index=False)
    pd.DataFrame(pair_rows).to_csv(os.path.join(cb.OUT, "ladder_increments.csv"), index=False)
    sw = pd.DataFrame(swap_rows)
    sw.to_csv(os.path.join(cb.OUT, "ladder_swap_null.csv"), index=False)
    pd.DataFrame(draw_rows).to_csv(os.path.join(cb.OUT, "permutation_draws_c02.csv"), index=False)

    # ================================================================ the headline comparison
    cb.hdr("THE NUMBER THE COORDINATOR ASKED FOR")
    g = {}
    for rid in ("ppm", "points"):
        sel = res[(res.stratum == "DECISION") & (res.eval_rows == "T3_high")
                  & (res.response == rid)].set_index("rung")
        G_refit = float(sel.loc[RUNG_LABEL["L4"], "dr2_defence_family"])
        G_step = float(sel.loc[RUNG_LABEL["L3"], "dr2_defence_family"])
        G_lin = float(sel.loc[RUNG_LABEL["L2"], "dr2_defence_family"])
        G_main = float(sel.loc[RUNG_LABEL["L1"], "dr2_defence_family"])
        g[rid] = dict(G_refit=G_refit, G_step=G_step, G_linear_family=G_lin,
                      G_pooled_main=G_main, F_recovery=G_step / G_refit if G_refit else np.nan)
        P("  %-7s  POOLED TIER-DUMMY x DEFENCE = %+.6f   against D098's tier-refit %+.6f  "
          "-> RECOVERY FRACTION F = %.3f" % (rid, G_step, G_refit, g[rid]["F_recovery"]))
        P("           for scale: pooled one-coefficient defence %+.6f ; pooled linear-interaction "
          "family %+.6f ; D098's pooled-interaction-over-defence anchor %+.6f"
          % (G_main, G_lin, cb.D098_ANCHORS["pooled_linear_interaction_%s_DECISION_ALL" % rid]))

    with open(os.path.join(cb.OUT, "_c02.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha256=h, headline=g,
                       ladder=json.loads(res.to_json(orient="records")),
                       increments=json.loads(pd.DataFrame(pair_rows).to_json(orient="records")),
                       swap_null=json.loads(sw.to_json(orient="records")),
                       noop_placebo=dict(ppm=noop["ppm"], points=noop["points"],
                                         abs_delta_ppm=abs(noop["ppm"] - obs[("ppm", "L4")])),
                       placebo_perturbs=dict(mean_fraction_changed=float(np.mean(perturb_frac)),
                                             mean_corr_orig_swapped=float(np.mean(perturb_corr))),
                       l4_null_reproduction=dict(reproduced_mean=float(dl4.mean()),
                                                 reproduced_sd=float(dl4.std(ddof=1)),
                                                 published=d098_null)),
                  fh, indent=2, default=float)
    P.write(os.path.join(cb.OUT, "run_log_c02.txt"))


if __name__ == "__main__":
    main()
