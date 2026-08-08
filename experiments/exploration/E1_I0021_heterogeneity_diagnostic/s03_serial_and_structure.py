"""
s03 -- WHY THE TWO NULLS DISAGREE, AND STEP 3 (STRUCTURE) UNDER THE NULL THAT SURVIVES.

PART A -- THE MECHANISM.  s02 found that the plain WITHIN-PLAYER SHUFFLE null and the WITHIN-PLAYER
CYCLIC-SHIFT null disagree sharply on exactly two of the eight relationships, and agree to within
noise on the other six.  The two that disagree (the player's own expanding prior efficiency, and
the player's own expanding prior usage) are RUNNING MEANS OF THAT PLAYER'S OWN HISTORY; the six
that agree are either exogenous opponent aggregates or pure iid noise.

The predicted mechanism is the classical spurious-regression one: when BOTH x and y carry
within-player serial correlation, the sampling distribution of their cross-product is WIDER than a
shuffle null says, because the shuffle destroys x's autocorrelation while y keeps its own, so the
effective number of independent (x, y) pairings is smaller than the row count.  This part MEASURES
the lag-1 within-player autocorrelation of every x and of the response, so the mechanism is checked
rather than asserted.  The prediction is precise and falsifiable: the shuffle-vs-cyclic gap should
track the autocorrelation of x, and should vanish where x is serially independent.

PART B -- STEP 3, RUN AS A BOUNDED NEGATIVE.  The directive makes step 3 conditional on step 2
being positive.  It is not: under the null that preserves serial structure the observed spread is
inside the null everywhere.  Correlating those per-player coefficients with player characteristics
would therefore manufacture structure out of noise -- which is precisely the failure mode this
screen exists to detect.  The question is nonetheless CLOSED rather than assumed, by testing the
observed coefficient-covariate correlations against the correlations obtained from coefficients
refitted under the CYCLIC-SHIFT null.  If the observed correlations sit inside that null, there is
no predictable structure to find, and that is stated as a negative rather than skipped.
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

N_STRUCT_DRAWS = 1000


def within_player_acf1(s, col, pcol="player_id"):
    """Lag-1 autocorrelation of `col` INSIDE each player, in date order, pooled over players.

    The series is demeaned inside the player first, so the statistic measures serial dependence and
    not the between-player level differences that would inflate any pooled autocorrelation.
    """
    v = pd.to_numeric(s[col], errors="coerce")
    d = pd.DataFrame({"v": v, "p": s[pcol].to_numpy()})
    num = den = 0.0
    for _, g in d.groupby("p", sort=False):
        x = g["v"].to_numpy(float)
        x = x[np.isfinite(x)]
        if len(x) < 5:
            continue
        x = x - x.mean()
        num += float((x[:-1] * x[1:]).sum())
        den += float((x * x).sum())
    return num / den if den > 0 else np.nan


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    hb.hdr("E1_I0021 s03 -- SERIAL STRUCTURE AND STEP 3")
    h, added, dropped = s02.check_prereg()
    P("  PREREG hash %s VERIFIED (added=%d dropped=%d)" % (h, len(added), len(dropped)))

    m = s02.build_merged(verbose=True)

    # =============================================================== PART A -- the mechanism
    hb.hdr("PART A -- WITHIN-PLAYER LAG-1 AUTOCORRELATION vs THE SHUFFLE/CYCLIC NULL GAP")
    pool = pd.read_csv(os.path.join(hb.OUT, "pooling_diagnostic.csv"))
    acf_rows = []
    for floor in pr.MINUTES_FLOOR_GRID:
        s = s02.floor_subset(m, floor)
        s, _ = s02.complete_case(s)
        s = s.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
        acf_y = within_player_acf1(s, "y_ppm_floor")
        for rel in s02.ALL_RELS:
            xc = s02.xcol_for(rel)
            a = within_player_acf1(s, xc)
            row = pool[(pool.floor == floor) & (pool.relationship == rel["id"])].iloc[0]
            acf_rows.append(dict(floor=floor, relationship=rel["id"], x=xc,
                                 acf1_x_within_player=a, acf1_y_within_player=acf_y,
                                 shuffle_ratio=row["n1_ratio_w"], cyclic_ratio=row["n4_cyclic_ratio_w"],
                                 gap_shuffle_minus_cyclic=row["n1_ratio_w"] - row["n4_cyclic_ratio_w"],
                                 shuffle_p=row["n1_p_w"], cyclic_p=row["n4_cyclic_p_w"]))
        P("  floor %2d : response y_ppm within-player lag-1 acf = %+.4f" % (floor, acf_y))
        for r in acf_rows[-len(s02.ALL_RELS):]:
            P("      %-32s acf1(x)=%+.4f   shuffle ratio=%.3f   cyclic ratio=%.3f   gap=%+.3f"
              % (r["relationship"], r["acf1_x_within_player"], r["shuffle_ratio"],
                 r["cyclic_ratio"], r["gap_shuffle_minus_cyclic"]))
    acf = pd.DataFrame(acf_rows)
    acf.to_csv(os.path.join(hb.OUT, "serial_structure_diagnostic.csv"), index=False)

    ok = acf.dropna(subset=["acf1_x_within_player", "gap_shuffle_minus_cyclic"])
    r_pearson = float(np.corrcoef(ok["acf1_x_within_player"], ok["gap_shuffle_minus_cyclic"])[0, 1])
    P("")
    P("  ACROSS ALL %d (floor x relationship) cells: corr( lag-1 acf of x , shuffle-minus-cyclic "
      "null gap ) = %+.3f" % (len(ok), r_pearson))
    P("  PREDICTION WAS: the gap is created by x's autocorrelation and vanishes when x is serially "
      "independent. The two negative controls are iid by construction:")
    for cid in [r["id"] for r in pr.NEGATIVE_CONTROLS]:
        sl = acf[acf.relationship == cid]
        P("      %-24s mean acf1(x)=%+.4f  mean gap=%+.4f"
          % (cid, sl["acf1_x_within_player"].mean(), sl["gap_shuffle_minus_cyclic"].mean()))
    for cid in ["R01_prior_efficiency_persistence", "R06_own_usage"]:
        sl = acf[acf.relationship == cid]
        P("      %-24s mean acf1(x)=%+.4f  mean gap=%+.4f"
          % (cid, sl["acf1_x_within_player"].mean(), sl["gap_shuffle_minus_cyclic"].mean()))

    # =============================================================== PART B -- step 3
    hb.hdr("PART B -- STEP 3 STRUCTURE, TESTED AGAINST THE CYCLIC-SHIFT NULL")
    P("  Step 2 is NEGATIVE under the null that preserves serial structure, so step 3 is run as a")
    P("  bounded negative: any correlation between per-player coefficients and player")
    P("  characteristics is compared against the SAME correlation computed from coefficients")
    P("  refitted on cyclic-shifted x. Observed correlations inside that null mean NO PREDICTABLE")
    P("  STRUCTURE -- and the question is closed by measurement rather than by assumption.")

    floor = pr.HEADLINE_FLOOR
    s = s02.floor_subset(m, floor)
    s, _ = s02.complete_case(s)
    s = s.sort_values(["player_id", "season", "game_date"]).reset_index(drop=True)
    pcodes, puq = pd.factorize(s["player_id"], sort=True)
    ng = len(puq)
    gns = np.bincount(pcodes, minlength=ng)
    gstarts = np.concatenate([[0], np.cumsum(gns)[:-1]])
    y = s["y_ppm_floor"].to_numpy(float)

    # ---- strictly-prior player characteristics, one value per player ----
    # Every source column is a PRIOR-ONLY column in its frozen frame (D089's PRIOR_ONLY_COLS /
    # D085's prior aggregates); summarising them per player is a description of the player, not a
    # forecast, and it never reads the response.
    cov_src = {
        "usage_tier_prior": "O01_own_usg_pg",
        "minutes_tier_prior": "refB_mpg" if "refB_mpg" in s.columns else "prior5_minutes",
        "role_stability_prior": "starter_flag",
        "team_pace_prior": "D01_tm_poss_per40",
        "experience_prior": "n_prior",
        "n_games_retained": None,
    }
    covs = pd.DataFrame({"player_id": puq})
    for name, src in cov_src.items():
        if src is None:
            covs[name] = gns
        elif src in s.columns:
            covs[name] = s.groupby("player_id", sort=True)[src].mean().reindex(puq).to_numpy()
        else:
            covs[name] = np.nan
    missing_covs = [k for k in cov_src if covs[k].isna().all()]
    P("")
    P("  covariates built: %s" % ", ".join(k for k in cov_src if k not in missing_covs))
    if missing_covs:
        P("  covariates NOT AVAILABLE in these frozen frames (declared, not silently dropped): %s"
          % ", ".join(missing_covs))
    P("  PREREGISTERED BUT UNAVAILABLE: player POSITION and YEARS OF EXPERIENCE are not carried by")
    P("  either frozen frame. `n_prior` (appearances so far) is used as an experience PROXY and is")
    P("  labelled as such. Position is simply not testable here and is reported as a coverage gap.")

    struct_rows = []
    for rel in pr.RELATIONSHIPS:
        xc = s02.xcol_for(rel)
        x = pd.to_numeric(s[xc], errors="coerce").to_numpy(float)
        beta, se, npg, valid = hb.group_slopes_fast(x, y, pcodes, ng,
                                                    min_games=pr.MIN_GAMES_PER_PLAYER)
        w = np.where(valid, 1.0 / np.maximum(se ** 2, 1e-300), 0.0)

        def wcorr(a, b, ww):
            ok2 = np.isfinite(a) & np.isfinite(b) & (ww > 0)
            if ok2.sum() < 10:
                return np.nan
            aa, bb, wv = a[ok2], b[ok2], ww[ok2]
            ma = np.average(aa, weights=wv)
            mb = np.average(bb, weights=wv)
            ca = aa - ma
            cb = bb - mb
            den = np.sqrt(np.average(ca ** 2, weights=wv) * np.average(cb ** 2, weights=wv))
            return float(np.average(ca * cb, weights=wv) / den) if den > 0 else np.nan

        # null: refit betas on cyclic-shifted x, correlate against the SAME fixed covariates
        rng = np.random.default_rng(pr.SEED + 7)
        null_abs = {c: np.empty(N_STRUCT_DRAWS) for c in cov_src}
        for k in range(N_STRUCT_DRAWS):
            xp = hb.cyclic_shift_within_groups(x, gstarts, gns, rng)
            bb, ss, _, vv = hb.group_slopes_fast(xp, y, pcodes, ng,
                                                 min_games=pr.MIN_GAMES_PER_PLAYER)
            ww = np.where(vv, 1.0 / np.maximum(ss ** 2, 1e-300), 0.0)
            for c in cov_src:
                null_abs[c][k] = abs(wcorr(bb, covs[c].to_numpy(float), ww) or np.nan)
        for c in cov_src:
            obs = wcorr(beta, covs[c].to_numpy(float), w)
            nd = null_abs[c][np.isfinite(null_abs[c])]
            p = (1.0 + int((nd >= abs(obs)).sum())) / (len(nd) + 1.0) if len(nd) else np.nan
            struct_rows.append(dict(floor=floor, relationship=rel["id"], covariate=c,
                                    n_players=int(valid.sum()), weighted_corr=obs,
                                    null_mean_abs_corr=float(np.mean(nd)) if len(nd) else np.nan,
                                    null_p95_abs_corr=float(np.percentile(nd, 95)) if len(nd) else np.nan,
                                    p_vs_cyclic_null=p))
            P("    %-32s %-22s corr=%+.3f  null mean|corr|=%.3f  null p95=%.3f  p=%.4f"
              % (rel["id"], c, obs, np.mean(nd) if len(nd) else np.nan,
                 np.percentile(nd, 95) if len(nd) else np.nan, p))
    st = pd.DataFrame(struct_rows)
    st.to_csv(os.path.join(hb.OUT, "heterogeneity_structure.csv"), index=False)
    n_cells = int(st["p_vs_cyclic_null"].notna().sum())
    n_hit = int((st["p_vs_cyclic_null"] < 0.05).sum())
    P("")
    P("  STEP 3 RESULT: %d of %d coefficient-covariate cells clear p<0.05 against the cyclic-shift "
      "null (%.1f expected by chance at 5%%)." % (n_hit, n_cells, 0.05 * n_cells))

    out = dict(prereg_sha256=h,
               corr_acf_vs_null_gap=r_pearson,
               n_structure_cells=n_cells, n_structure_hits=n_hit,
               structure_expected_by_chance=0.05 * n_cells,
               covariates_unavailable=missing_covs + ["position", "years_of_experience"],
               n_struct_draws=N_STRUCT_DRAWS)
    with open(os.path.join(hb.OUT, "_s03.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(hb.OUT, "run_log_s03.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote serial_structure_diagnostic.csv, heterogeneity_structure.csv, _s03.json")


if __name__ == "__main__":
    main()
