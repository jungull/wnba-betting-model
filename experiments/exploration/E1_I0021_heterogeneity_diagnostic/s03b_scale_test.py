"""
s03b -- TWO FOLLOW-THROUGHS THAT THE PREVIOUS RESULTS FORCE.

(1) WHY THE SHUFFLE NULL IS TOO NARROW, MEASURED RATHER THAN ASSERTED.
    s03 showed the shuffle-vs-cyclic null gap tracks the lag-1 autocorrelation of x (r = +0.83),
    but it also showed the RESPONSE's lag-1 autocorrelation is essentially zero.  A lag-1
    correlation near zero does NOT mean the response has no slow structure: a gentle season-long
    drift buried under large game-to-game noise shows almost nothing at lag 1 while still putting
    power at low frequency, which is exactly where an expanding-mean regressor puts ALL of its
    power.  This part measures the response's LOW-FREQUENCY share directly -- the variance of a
    within-player rolling mean of the response, against the variance a white-noise series of the
    same length would show -- so the claim is a measurement.

(2) IS THE STRUCTURE FOUND IN STEP 3 SCALE HETEROGENEITY?
    Step 3 found the per-player OPPONENT coefficients correlate with the player's own prior usage
    (r = +0.27 to +0.45, p = 0.001-0.004 against the cyclic null), on relationships whose POOLED
    effect is real (t = +3.5 to +6.0).  The obvious mechanism is not that different players respond
    in different DIRECTIONS but that they respond on different SCALES: an opponent effect on
    points-per-minute should be roughly proportional to how many points per minute the player
    scores.  That is heterogeneity of a trivially predictable kind and it argues for a
    MULTIPLICATIVE model, not for per-player fitting.
    THE TEST: divide the response by the player's own STRICTLY-PRIOR expanding rate (refB_ppm, a
    prior-only column already in the frozen frame) so the response becomes a RELATIVE rate, refit
    the per-player coefficients, and re-run the same correlation against the same cyclic-shift null.
    If the correlation collapses toward the null, the heterogeneity is scale and nothing more.
    If it survives, there is genuine directional heterogeneity in how players meet defences.
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

N_DRAWS = 1000
SCALE_RELS = ["R02_opp_efg_allowed", "R03_opp_ts_allowed", "R04_opp_defrtg",
              "R01_prior_efficiency_persistence", "R05_teammate_volume_pregame", "R06_own_usage"]


def lowfreq_share(s, col, window=5, pcol="player_id"):
    """Variance of a within-player rolling mean, relative to what white noise would give.

    For an iid series the variance of a k-game rolling mean is var/k, so the ratio
    var(rolling_k) / (var/k) is 1.0 under white noise and > 1 when the series carries slow
    structure.  Computed inside the player on the within-player demeaned series.
    """
    v = pd.to_numeric(s[col], errors="coerce")
    d = pd.DataFrame({"v": v, "p": s[pcol].to_numpy()})
    num = den = 0.0
    for _, g in d.groupby("p", sort=False):
        x = g["v"].to_numpy(float)
        x = x[np.isfinite(x)]
        if len(x) < 3 * window:
            continue
        x = x - x.mean()
        rm = pd.Series(x).rolling(window).mean().dropna().to_numpy()
        if len(rm) < 3:
            continue
        num += float(np.var(rm) * len(rm))
        den += float(np.var(x) / window * len(rm))
    return num / den if den > 0 else np.nan


def wcorr(a, b, ww):
    ok = np.isfinite(a) & np.isfinite(b) & (ww > 0)
    if ok.sum() < 10:
        return np.nan
    aa, bb, wv = a[ok], b[ok], ww[ok]
    ca = aa - np.average(aa, weights=wv)
    cb = bb - np.average(bb, weights=wv)
    den = np.sqrt(np.average(ca ** 2, weights=wv) * np.average(cb ** 2, weights=wv))
    return float(np.average(ca * cb, weights=wv) / den) if den > 0 else np.nan


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    hb.hdr("E1_I0021 s03b -- LOW-FREQUENCY STRUCTURE AND THE SCALE TEST")
    h, _, _ = s02.check_prereg()
    P("  PREREG hash %s VERIFIED" % h)
    m = s02.build_merged(verbose=True)

    # ------------------------------------------------------------------ (1) low-frequency share
    hb.hdr("(1) LOW-FREQUENCY SHARE -- variance of a within-player 5-game rolling mean vs white noise")
    lf_rows = []
    for floor in pr.MINUTES_FLOOR_GRID:
        s = s02.floor_subset(m, floor)
        s, _ = s02.complete_case(s)
        s = s.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
        r_y = lowfreq_share(s, "y_ppm_floor")
        row = dict(floor=floor, series="y_ppm (RESPONSE)", lowfreq_ratio=r_y)
        lf_rows.append(row)
        P("  floor %2d  RESPONSE y_ppm             low-frequency ratio = %.3f  (1.00 = white noise)"
          % (floor, r_y))
        for rel in s02.ALL_RELS:
            xc = s02.xcol_for(rel)
            r_x = lowfreq_share(s, xc)
            lf_rows.append(dict(floor=floor, series=rel["id"], lowfreq_ratio=r_x))
            P("           %-32s low-frequency ratio = %.3f" % (rel["id"], r_x))
    pd.DataFrame(lf_rows).to_csv(os.path.join(hb.OUT, "lowfreq_share.csv"), index=False)
    P("")
    P("  READING: a ratio above 1.00 on the RESPONSE means the response is not white inside a")
    P("  player -- it carries slow season structure. A shuffle null destroys the regressor's slow")
    P("  structure while the response keeps its own, so the shuffle null is TOO NARROW by exactly")
    P("  the overlap between the two. The cyclic-shift null preserves both and is the honest one.")

    # ------------------------------------------------------------------ (2) the scale test
    hb.hdr("(2) SCALE TEST -- does the coefficient/usage correlation survive a relative response?")
    floor = pr.HEADLINE_FLOOR
    s = s02.floor_subset(m, floor)
    s, _ = s02.complete_case(s)
    s = s.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    assert "refB_ppm" in s.columns
    scaler = pd.to_numeric(s["refB_ppm"], errors="coerce").to_numpy(float)
    good = np.isfinite(scaler) & (scaler > 0.02)
    P("  scaler = refB_ppm (STRICTLY-PRIOR ratio-of-prior-sums rate, already in the frozen frame). "
      "%d of %d rows usable (%.2f%% dropped for a missing or degenerate prior rate)."
      % (int(good.sum()), len(s), 100 * (1 - good.mean())))
    s = s.loc[good].reset_index(drop=True)
    scaler = scaler[good]
    pcodes, puq = pd.factorize(s["player_id"], sort=True)
    ng = len(puq)
    gns = np.bincount(pcodes, minlength=ng)
    gstarts = np.concatenate([[0], np.cumsum(gns)[:-1]])

    y_abs = s["y_ppm_floor"].to_numpy(float)
    y_rel = y_abs / scaler
    usage = s.groupby("player_id", sort=True)["O01_own_usg_pg"].mean().reindex(puq).to_numpy()

    rows = []
    for rid in SCALE_RELS:
        rel = [r for r in s02.ALL_RELS if r["id"] == rid][0]
        xc = s02.xcol_for(rel)
        x = pd.to_numeric(s[xc], errors="coerce").to_numpy(float)
        out = {}
        for tag, yv in (("absolute_ppm", y_abs), ("relative_ppm", y_rel)):
            beta, se, npg, valid = hb.group_slopes_fast(x, yv, pcodes, ng,
                                                        min_games=pr.MIN_GAMES_PER_PLAYER)
            w = np.where(valid, 1.0 / np.maximum(se ** 2, 1e-300), 0.0)
            obs = wcorr(beta, usage, w)
            rng = np.random.default_rng(pr.SEED + 11)
            nd = np.empty(N_DRAWS)
            for k in range(N_DRAWS):
                xp = hb.cyclic_shift_within_groups(x, gstarts, gns, rng)
                bb, ss, _, vv = hb.group_slopes_fast(xp, yv, pcodes, ng,
                                                     min_games=pr.MIN_GAMES_PER_PLAYER)
                ww = np.where(vv, 1.0 / np.maximum(ss ** 2, 1e-300), 0.0)
                nd[k] = abs(wcorr(bb, usage, ww))
            nd = nd[np.isfinite(nd)]
            p = (1.0 + int((nd >= abs(obs)).sum())) / (len(nd) + 1.0)
            # pooled effect on this response, for context
            pw = w[valid]
            pb = float((beta[valid] * pw).sum() / pw.sum())
            pse = float(np.sqrt(1.0 / pw.sum()))
            out[tag] = dict(corr=obs, p=p, null_mean=float(nd.mean()),
                            null_p95=float(np.percentile(nd, 95)),
                            pooled_beta=pb, pooled_t=pb / pse, n_players=int(valid.sum()))
        rows.append(dict(relationship=rid, x=xc,
                         corr_absolute=out["absolute_ppm"]["corr"],
                         p_absolute=out["absolute_ppm"]["p"],
                         corr_relative=out["relative_ppm"]["corr"],
                         p_relative=out["relative_ppm"]["p"],
                         null_p95=out["relative_ppm"]["null_p95"],
                         pooled_t_absolute=out["absolute_ppm"]["pooled_t"],
                         pooled_t_relative=out["relative_ppm"]["pooled_t"],
                         n_players=out["absolute_ppm"]["n_players"]))
        P("  %-32s corr(beta, prior usage): ABSOLUTE ppm = %+.3f (p=%.4f)   RELATIVE ppm = %+.3f "
          "(p=%.4f)   null p95=%.3f   pooled t: abs=%+.2f rel=%+.2f"
          % (rid, out["absolute_ppm"]["corr"], out["absolute_ppm"]["p"],
             out["relative_ppm"]["corr"], out["relative_ppm"]["p"],
             out["relative_ppm"]["null_p95"], out["absolute_ppm"]["pooled_t"],
             out["relative_ppm"]["pooled_t"]))
    sc = pd.DataFrame(rows)
    sc.to_csv(os.path.join(hb.OUT, "scale_test.csv"), index=False)

    surv = sc[(sc.p_relative < 0.05)]
    P("")
    P("  %d of %d relationships still show a coefficient/usage correlation once the response is "
      "made RELATIVE to the player's own strictly-prior rate." % (len(surv), len(sc)))
    if len(surv) == 0:
        P("  VERDICT: the structure step 3 found is SCALE heterogeneity and nothing more. Players do")
        P("  not respond to opponents in different directions; they respond in proportion to how")
        P("  much they score. That argues for a MULTIPLICATIVE (relative-rate) model, and it argues")
        P("  AGAINST per-player fitting, which spends a coefficient per player to recover a")
        P("  proportionality the pooled model can carry in one term.")
    else:
        P("  VERDICT: some coefficient/usage correlation survives scale normalisation: %s"
          % ", ".join(surv["relationship"]))

    out = dict(prereg_sha256=h, n_scale_rels=len(sc),
               n_surviving_relative=int(len(surv)),
               surviving=list(surv["relationship"]),
               n_draws=N_DRAWS)
    with open(os.path.join(hb.OUT, "_s03b.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(hb.OUT, "run_log_s03b.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote lowfreq_share.csv, scale_test.csv, _s03b.json")


if __name__ == "__main__":
    main()
