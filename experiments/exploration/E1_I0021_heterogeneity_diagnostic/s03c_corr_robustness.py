"""
s03c -- STRESS TEST ON THE ONE POSITIVE FINDING, BEFORE IT IS CLAIMED.

s03/s03b found that per-player OPPONENT coefficients correlate with the player's own strictly-prior
usage (weighted r = +0.27 to +0.45, p = 0.001 against the cyclic-shift null), and that the
correlation SURVIVES making the response relative to the player's own prior rate.  Taken at face
value that is a directional, predictable heterogeneity -- the single most useful thing this screen
could return.

BUT IT SITS IN TENSION WITH STEP 2.  If ~20% of the weighted variance of the coefficients were
systematic, the omnibus spread statistic should have come in around 1.12; it came in at 1.02.  A
finding that contradicts the screen's own omnibus test is exactly the kind of thing this program has
been burned by, so it is stress-tested here BEFORE it is written down anywhere as a result:

  A. THE RIGHT NULL FOR THIS QUESTION.  "Is the coefficient related to this player characteristic?"
     is answered by permuting the CHARACTERISTIC ACROSS PLAYERS, which holds both the fitted
     coefficients and the covariate values exactly fixed and destroys only their pairing.  It makes
     no assumption about how the coefficients were fitted, so it cannot be fooled by anything in the
     fitting.  Reported alongside the cyclic-shift null.
  B. ESTIMATOR ROBUSTNESS.  Precision-weighted Pearson, UNWEIGHTED Pearson, and SPEARMAN rank.  A
     weighted Pearson correlation is not robust; if the result lives only in the weighted version it
     lives in a handful of high-weight players.
  C. INFLUENCE.  Drop the 10 highest-weight players and recompute.
  D. THE ARITHMETIC RECONCILIATION.  The weighted variance share of the coefficients explained by
     the covariate, set beside the excess variance the step-2 spread statistic actually found. These
     two numbers must be consistent; if they are not, the correlation is not measuring heterogeneity
     of the coefficients and must not be reported as if it were.
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
import hd_base as hb  # noqa: E402
import s00_prereg as pr  # noqa: E402
import s02_pooling as s02  # noqa: E402

N_DRAWS = 5000
RELS = ["R02_opp_efg_allowed", "R03_opp_ts_allowed", "R04_opp_defrtg",
        "R01_prior_efficiency_persistence", "R05_teammate_volume_pregame", "R06_own_usage",
        "NC1_noise_eff_frame", "NC2_noise_tv_frame"]


def wcorr(a, b, w):
    ok = np.isfinite(a) & np.isfinite(b) & (w > 0)
    aa, bb, wv = a[ok], b[ok], w[ok]
    if len(aa) < 10:
        return np.nan
    ca = aa - np.average(aa, weights=wv)
    cb = bb - np.average(bb, weights=wv)
    den = np.sqrt(np.average(ca ** 2, weights=wv) * np.average(cb ** 2, weights=wv))
    return float(np.average(ca * cb, weights=wv) / den) if den > 0 else np.nan


def rankcorr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return np.nan
    ra = pd.Series(a[ok]).rank().to_numpy()
    rb = pd.Series(b[ok]).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    hb.hdr("E1_I0021 s03c -- STRESS TEST ON THE COEFFICIENT/USAGE CORRELATION")
    h, _, _ = s02.check_prereg()
    P("  PREREG hash %s VERIFIED" % h)
    m = s02.build_merged(verbose=True)
    floor = pr.HEADLINE_FLOOR
    s = s02.floor_subset(m, floor)
    s, _ = s02.complete_case(s)
    s = s.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    pcodes, puq = pd.factorize(s["player_id"], sort=True)
    ng = len(puq)
    gns = np.bincount(pcodes, minlength=ng)
    gstarts = np.concatenate([[0], np.cumsum(gns)[:-1]])
    y = s["y_ppm_floor"].to_numpy(float)
    usage = s.groupby("player_id", sort=True)["O01_own_usg_pg"].mean().reindex(puq).to_numpy()

    pool = pd.read_csv(os.path.join(hb.OUT, "pooling_diagnostic.csv"))
    rows = []
    for rid in RELS:
        rel = [r for r in s02.ALL_RELS if r["id"] == rid][0]
        xc = s02.xcol_for(rel)
        x = pd.to_numeric(s[xc], errors="coerce").to_numpy(float)
        beta, se, npg, valid = hb.group_slopes_fast(x, y, pcodes, ng,
                                                    min_games=pr.MIN_GAMES_PER_PLAYER)
        w = np.where(valid, 1.0 / np.maximum(se ** 2, 1e-300), 0.0)
        b_ok, u_ok, w_ok = beta[valid], usage[valid], w[valid]

        r_w = wcorr(beta, usage, w)
        r_u = float(np.corrcoef(b_ok[np.isfinite(u_ok)], u_ok[np.isfinite(u_ok)])[0, 1])
        r_s = rankcorr(b_ok, u_ok)

        # ---- A. covariate-permutation null: shuffle the CHARACTERISTIC across players ----
        rng = np.random.default_rng(pr.SEED + 13)
        nd = np.empty(N_DRAWS)
        for k in range(N_DRAWS):
            nd[k] = abs(wcorr(b_ok, u_ok[rng.permutation(len(u_ok))], w_ok))
        nd = nd[np.isfinite(nd)]
        p_cov = (1.0 + int((nd >= abs(r_w)).sum())) / (len(nd) + 1.0)

        # A2. the SAME null on the UNWEIGHTED and RANK correlations.  The precision weights are the
        # one thing in the weighted statistic that is tied to the player and NOT permuted, so if the
        # result lives only in the weighted version it is a weighting artefact rather than a
        # relationship.  Both negative controls are run through the identical path.
        okc = np.isfinite(b_ok) & np.isfinite(u_ok)
        bb2, uu2 = b_ok[okc], u_ok[okc]
        rng2 = np.random.default_rng(pr.SEED + 17)
        nd_u = np.empty(N_DRAWS)
        nd_s = np.empty(N_DRAWS)
        rb2 = pd.Series(bb2).rank().to_numpy()
        for k in range(N_DRAWS):
            perm = rng2.permutation(len(uu2))
            nd_u[k] = abs(np.corrcoef(bb2, uu2[perm])[0, 1])
            nd_s[k] = abs(np.corrcoef(rb2, pd.Series(uu2[perm]).rank().to_numpy())[0, 1])
        p_cov_u = (1.0 + int((nd_u >= abs(r_u)).sum())) / (N_DRAWS + 1.0)
        p_cov_s = (1.0 + int((nd_s >= abs(r_s)).sum())) / (N_DRAWS + 1.0)

        # ---- C. influence: drop the 10 highest-weight players ----
        order = np.argsort(-w_ok)
        keep = np.ones(len(w_ok), bool)
        keep[order[:10]] = False
        r_w_drop10 = wcorr(b_ok[keep], u_ok[keep], w_ok[keep])

        # ---- D. arithmetic reconciliation ----
        # weighted variance share of beta explained by a weighted linear fit on usage
        okk = np.isfinite(u_ok) & np.isfinite(b_ok) & (w_ok > 0)
        bb, uu, ww = b_ok[okk], u_ok[okk], w_ok[okk]
        mb = np.average(bb, weights=ww)
        mu = np.average(uu, weights=ww)
        sl = np.average((bb - mb) * (uu - mu), weights=ww) / np.average((uu - mu) ** 2, weights=ww)
        var_tot_w = float(np.average((bb - mb) ** 2, weights=ww))
        resid = bb - (mb + sl * (uu - mu))
        var_res_w = float(np.average(resid ** 2, weights=ww))
        share_explained = 1.0 - var_res_w / var_tot_w if var_tot_w > 0 else np.nan
        prow = pool[(pool.floor == floor) & (pool.relationship == rid)].iloc[0]
        cyc_ratio = float(prow["n4_cyclic_ratio_w"])
        implied_share_from_spread = 1.0 - 1.0 / (cyc_ratio ** 2) if cyc_ratio > 0 else np.nan

        rows.append(dict(relationship=rid, x=xc, n_players=int(valid.sum()),
                         corr_weighted=r_w, corr_unweighted=r_u, corr_spearman=r_s,
                         corr_weighted_drop_top10=r_w_drop10,
                         p_covariate_permutation=p_cov,
                         p_covariate_permutation_unweighted=p_cov_u,
                         p_covariate_permutation_spearman=p_cov_s,
                         cov_null_p95=float(np.percentile(nd, 95)),
                         weighted_var_share_explained=share_explained,
                         cyclic_spread_ratio=cyc_ratio,
                         implied_var_share_from_spread=implied_share_from_spread,
                         reconciles=bool(np.isfinite(share_explained)
                                         and np.isfinite(implied_share_from_spread)
                                         and share_explained <= max(implied_share_from_spread, 0)
                                         + 0.05)))
        P("  %-32s r_w=%+.3f (p=%.4f)  r_unw=%+.3f (p=%.4f)  r_spear=%+.3f (p=%.4f)  "
          "r_w(drop top10)=%+.3f | weighted var share explained=%.3f vs share implied by the "
          "spread statistic=%.3f -> %s"
          % (rid, r_w, p_cov, r_u, p_cov_u, r_s, p_cov_s, r_w_drop10,
             share_explained, implied_share_from_spread,
             "CONSISTENT" if rows[-1]["reconciles"] else "DOES NOT RECONCILE"))

    rb = pd.DataFrame(rows)
    rb.to_csv(os.path.join(hb.OUT, "correlation_robustness.csv"), index=False)

    hb.hdr("READING")
    real = rb[~rb.relationship.str.startswith("NC")]
    ctrl = rb[rb.relationship.str.startswith("NC")]
    for r in ctrl.itertuples():
        P("  NEGATIVE CONTROL %-22s p_weighted=%.4f  p_unweighted=%.4f  p_spearman=%.4f "
          "-- none of these may clear" % (r.relationship, r.p_covariate_permutation,
                                          r.p_covariate_permutation_unweighted,
                                          r.p_covariate_permutation_spearman))
    bad = real[~real["reconciles"]]
    P("  %d of %d real relationships DO NOT reconcile: the variance share the correlation implies "
      "is larger than the omnibus spread statistic found." % (len(bad), len(real)))
    if len(bad):
        P("  Those cells are NOT reportable as heterogeneity: %s"
          % ", ".join(bad["relationship"]))
    surv = real[(real.p_covariate_permutation < 0.05)
                & (real.corr_spearman.abs() > 0.15)
                & (real.corr_weighted_drop_top10.abs() > 0.15)]
    P("  %d of %d survive the covariate-permutation null AND rank correlation AND the "
      "drop-top-10 influence check: %s"
      % (len(surv), len(real), ", ".join(surv["relationship"]) if len(surv) else "(none)"))

    out = dict(prereg_sha256=h, n_draws=N_DRAWS,
               n_real=len(real), n_not_reconciling=int(len(bad)),
               not_reconciling=list(bad["relationship"]),
               n_surviving_all_checks=int(len(surv)),
               surviving_all_checks=list(surv["relationship"]))
    with open(os.path.join(hb.OUT, "_s03c.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(hb.OUT, "run_log_s03c.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote correlation_robustness.csv, _s03c.json")


if __name__ == "__main__":
    main()
