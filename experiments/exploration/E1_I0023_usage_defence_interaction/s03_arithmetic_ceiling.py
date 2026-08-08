"""
s03 -- STEP 3.  THE ARITHMETIC CEILING, BEFORE ANYTHING IS CELEBRATED.

Three leads in this programme died on arithmetic rather than on statistics.  The question is not
"is the interaction significant" but "how much can 1 sd of the interaction term move a points
forecast, against the response sd".  Computed in D084's and D089's exact form:

    d          = the forecast SHIFT the interaction produces, in POINTS
               = beta_interaction x (usage-u)(defence-d) x minutes_estimate
    ceiling    = Var(d) / Var(y)            -- the D084/D089 form, a variance share
    1-sd form  = ( |beta| x sd(interaction) x mean(minutes) / sd(y) )^2   -- the same thing quoted
                 as "points moved by 1 sd", which is how D084 and D089 stated it
    ORACLE     = (d.e)^2 / ((d.d) x SST)    -- best rescaling chosen with FULL HINDSIGHT.
                 DIAGNOSTIC ONLY, excluded from every headline, exactly as D084 and D089 treated it.

BENCHMARKS, quoted from the decision ledger and frozen in this screen's preregistration BEFORE any
of these numbers existed:
    D079 shot-mix            dR2 <= 0.001127
    D084 conversion          dR2 <= 0.000129
    D089 teammate volume     dR2 <= 0.002057   (prior-only; the largest the programme has measured)

IF THE CEILING IS TINY, THAT CLOSES THE LEAD AND IS A COMPLETE ANSWER.
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

BENCH = pr.CEILING_BENCHMARKS


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    ub.hdr("E1_I0023 s03 -- STEP 3: THE ARITHMETIC CEILING")
    h, added, dropped = pr.check_prereg()
    P("  PREREG hash %s VERIFIED. cells added=%d dropped=%d" % (h, len(added), len(dropped)))
    P("  BENCHMARKS (frozen before computing): D079 shot-mix %.6f | D084 conversion %.6f | "
      "D089 teammate-volume %.6f" % (BENCH["D079_shot_mix"], BENCH["D084_conversion"],
                                     BENCH["D089_teammate_volume_prior_only"]))
    m, ncl = s02.build_frame(P)

    basecols = pr.BASE_COMPLETE
    rows = []
    for dterm in [d["id"] for d in pr.DEFENCE_TERMS] + ["G01_noise_tvframe"]:
        ucol = pr.USAGE_MAIN
        for sid, tier in [("POOLED", -1), ("DECISION", -1), ("POOLED", 2), ("DECISION", 2)]:
            for contrast in ["INTERACTION", "MAIN_EFFECT"]:
              for fit in ["walk_forward", "in_sample"]:
                need = list(dict.fromkeys(basecols + [ucol, dterm, "y_ppm", "y_pts", "_m_hat"]))
                v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}
                mask = s02.stratum_mask(m, sid)
                for c in need:
                    mask &= np.isfinite(v[c])
                if tier == 2:
                    first_tr = mask & (m["season"].to_numpy()
                                       < pr.PREREG["partition"]["scored_seasons"][0])
                    tall, _ = ub.usage_terciles(v[ucol][first_tr] if first_tr.sum() > 200
                                                else v[ucol][mask], v[ucol])
                    mask = mask & (tall == 2)
                ssn = m["season"].to_numpy()

                dd_all, y_all, e_all, xi_all, mh_all, betas = [], [], [], [], [], []
                folds = ([(mask & (ssn < s), mask & (ssn == s))
                          for s in pr.PREREG["partition"]["scored_seasons"]]
                         if fit == "walk_forward" else [(mask, mask)])
                for tr, te in folds:
                    if tr.sum() < 300 or te.sum() < 80:
                        continue
                    uc, dc = float(v[ucol][tr].mean()), float(v[dterm][tr].mean())
                    if contrast == "INTERACTION":
                        Xb_tr = s02.design(v, basecols, tr, ucol, dterm, uc, dc, False)
                        Xa_tr = s02.design(v, basecols, tr, ucol, dterm, uc, dc, True)
                        Xb_te = s02.design(v, basecols, te, ucol, dterm, uc, dc, False)
                        Xa_te = s02.design(v, basecols, te, ucol, dterm, uc, dc, True)
                        sig_tr = (v[ucol][te] - uc) * (v[dterm][te] - dc)
                    else:   # MAIN_EFFECT: the increment is the centred defence column itself
                        Xa_tr = s02.design(v, basecols, tr, ucol, dterm, uc, dc, False)
                        Xa_te = s02.design(v, basecols, te, ucol, dterm, uc, dc, False)
                        Xb_tr, Xb_te = Xa_tr[:, :-1], Xa_te[:, :-1]
                        sig_tr = v[dterm][te] - dc
                    bb = ub.ols(Xb_tr, v["y_ppm"][tr])
                    ba = ub.ols(Xa_tr, v["y_ppm"][tr])
                    mh = v["_m_hat"][te]
                    dd_all.append((Xa_te @ ba - Xb_te @ bb) * mh)     # forecast shift, POINTS
                    e_all.append(v["y_pts"][te] - (Xb_te @ bb) * mh)  # reference points residual
                    y_all.append(v["y_pts"][te])
                    xi_all.append(sig_tr)
                    mh_all.append(mh)
                    betas.append(float(ba[-1]))
                if not y_all:
                    continue
                d = np.concatenate(dd_all)
                e = np.concatenate(e_all)
                y = np.concatenate(y_all)
                xi = np.concatenate(xi_all)
                mh = np.concatenate(mh_all)
                sst = float(((y - y.mean()) ** 2).sum())
                sdd, sde = float(d @ d), float(d @ e)
                ceiling = sdd / sst
                oracle = (sde * sde) / (sdd * sst) if sdd > 0 else np.nan
                realised = (2 * sde - sdd) / sst
                beta = float(np.mean(betas))
                sd_xi = float(np.std(xi, ddof=1))
                mean_mh = float(np.mean(mh))
                sd_y = float(np.std(y, ddof=1))
                pts_1sd = abs(beta) * sd_xi * mean_mh
                ceiling_1sd = (pts_1sd / sd_y) ** 2
                rows.append(dict(
                    defence=dterm, usage=ucol, stratum=sid,
                    tier=("ALL_TIERS" if tier == -1 else "T3_high_usage"),
                    contrast=contrast, fit=fit,
                    is_negative_control=(dterm == "G01_noise_tvframe"),
                    n=int(len(y)), sd_y_points=sd_y,
                    mean_interaction_beta_on_ppm=beta, sd_interaction_term=sd_xi,
                    mean_minutes_estimate=mean_mh,
                    points_moved_by_1sd=pts_1sd,
                    ceiling_1sd_form=ceiling_1sd,
                    ceiling_D084_form_var_share=ceiling,
                    DIAGNOSTIC_oracle_best_rescaling=oracle,
                    implied_optimal_rescaling=(sde / sdd if sdd > 0 else np.nan),
                    realised_paired_dr2_points=realised,
                    vs_D079_shot_mix=ceiling / BENCH["D079_shot_mix"],
                    vs_D084_conversion=ceiling / BENCH["D084_conversion"],
                    vs_D089_teammate_volume=ceiling / BENCH["D089_teammate_volume_prior_only"]))
                r = rows[-1]
                P("  %-20s %-9s %-14s %-11s %-13s n=%5d  1 sd moves points by %.5f against a "
                  "response sd of %.4f  ->  1-sd ceiling %.8f  (D084-form %.8f, ORACLE %.8f)%s"
                  % (dterm, sid, r["tier"], contrast, fit, r["n"], pts_1sd, sd_y, ceiling_1sd,
                     ceiling, oracle,
                     "   <-- NEGATIVE CONTROL" if r["is_negative_control"] else ""))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(ub.OUT, "arithmetic_ceiling.csv"), index=False)

    def pick(stratum, tier, contrast):
        q = res[(res.defence == "A10_opp_defrtg") & (res.stratum == stratum) & (res.tier == tier)
                & (res.contrast == contrast) & (res.fit == "walk_forward")]
        return q.iloc[0] if len(q) else None

    ub.hdr("THE CEILINGS AGAINST THE THREE BENCHMARKS")
    picks = [("PREREGISTERED INTERACTION, DECISION", pick("DECISION", "ALL_TIERS", "INTERACTION")),
             ("PREREGISTERED INTERACTION, POOLED", pick("POOLED", "ALL_TIERS", "INTERACTION")),
             ("MAIN EFFECT, DECISION, TOP USAGE TIER", pick("DECISION", "T3_high_usage",
                                                            "MAIN_EFFECT")),
             ("MAIN EFFECT, POOLED, TOP USAGE TIER", pick("POOLED", "T3_high_usage",
                                                          "MAIN_EFFECT")),
             ("MAIN EFFECT, DECISION, ALL TIERS", pick("DECISION", "ALL_TIERS", "MAIN_EFFECT"))]
    for lbl, r in picks:
        if r is None:
            continue
        P("  %-40s ceiling dR2 <= %.8f   = %.2fx D079 (%.6f), %.2fx D084 (%.6f), %.2fx D089 (%.6f)"
          % (lbl, r["ceiling_D084_form_var_share"], r["vs_D079_shot_mix"], BENCH["D079_shot_mix"],
             r["vs_D084_conversion"], BENCH["D084_conversion"],
             r["vs_D089_teammate_volume"], BENCH["D089_teammate_volume_prior_only"]))
    P("")
    hl = pick("DECISION", "T3_high_usage", "MAIN_EFFECT")
    P("  THE LEVER IN ONE LINE (main effect, DECISION, top usage tier, walk-forward): 1 sd of the "
      "centred opponent defensive rating = %.5f, x beta %.3e points-per-minute = %.6f ppm, "
      "x %.2f minutes = %.5f points per game = %.3f%% of a response sd of %.4f."
      % (hl["sd_interaction_term"], hl["mean_interaction_beta_on_ppm"],
         hl["sd_interaction_term"] * hl["mean_interaction_beta_on_ppm"],
         hl["mean_minutes_estimate"], hl["points_moved_by_1sd"],
         100.0 * hl["points_moved_by_1sd"] / hl["sd_y_points"], hl["sd_y_points"]))
    hi = pick("DECISION", "ALL_TIERS", "INTERACTION")
    P("  THE SAME LINE FOR THE PREREGISTERED INTERACTION (DECISION): 1 sd = %.5f, x beta %.3e "
      "= %.6f ppm, x %.2f minutes = %.5f points per game = %.3f%% of a response sd of %.4f."
      % (hi["sd_interaction_term"], hi["mean_interaction_beta_on_ppm"],
         hi["sd_interaction_term"] * hi["mean_interaction_beta_on_ppm"],
         hi["mean_minutes_estimate"], hi["points_moved_by_1sd"],
         100.0 * hi["points_moved_by_1sd"] / hi["sd_y_points"], hi["sd_y_points"]))

    out = dict(prereg_sha256=h, benchmarks=BENCH,
               headline_interaction_decision=json.loads(hi.to_json()),
               headline_maineffect_top_tier_decision=json.loads(hl.to_json()),
               table=json.loads(res.to_json(orient="records")))
    with open(os.path.join(ub.OUT, "_s03.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(ub.OUT, "run_log_s03.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote arithmetic_ceiling.csv, _s03.json")


if __name__ == "__main__":
    main()
