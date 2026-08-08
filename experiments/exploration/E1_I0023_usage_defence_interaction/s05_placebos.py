"""
s05 -- THE DIAGNOSTICS THAT DECIDE WHETHER STEP 5's RESULT IS REAL.

WHY THIS SCRIPT EXISTS, WRITTEN BEFORE ITS NUMBERS.
    s04 returned an opponent-defence MAIN effect inside the top usage tier of walk-forward
    dR2 = +0.0144 (points-per-minute, pooled) and +0.0239 (decision stratum), at cluster-level
    p 0.0005-0.0010, with an in-sample cluster-robust t of +6.7.  D085 screened TWELVE
    constructions of opponent defensive matchup across 36 cells and its BEST dR2 WAS 0.00144.
    This screen's number is TEN TIMES D085's best.  The prior that a screen has found a real effect
    an established twelve-construction screen missed by an order of magnitude is very low, and this
    programme's own history says the explanation is usually the machinery.

    THE SPECIFIC SUSPICION, STATED BEFORE THE TEST.  `A10_opp_defrtg` is an EXPANDING PRIOR MEAN
    over the opponent's earlier games.  Such a series carries a strong SEASON-LEVEL and
    WITHIN-SEASON TIME component that is shared by every row on a date and has nothing to do with
    WHICH opponent a player faced.  Because the walk-forward arms are refit on earlier seasons and
    applied forward, a term correlated with the league's own drift can improve the test-season fit
    by correcting a LEVEL error -- and it would do so MORE for high-scoring, high-usage players,
    because their level error is larger in absolute points.  That reproduces every feature of the
    s04 result without any opponent-specific signal existing at all.

FOUR DIAGNOSTICS, ALL PREDECLARED HERE:
    P1 LEAGUE-MEAN PLACEBO.  Replace the opponent's defensive rating with the LEAGUE MEAN defensive
       rating over the team-games played on that same date.  It carries the entire time and level
       component and ZERO opponent-specific information.  If it reproduces the effect, the effect is
       the time component.
    P2 WITHIN-DATE OPPONENT SWAP NULL.  Permute the defence values among the team-games played on
       the same date.  Preserves the date's marginal distribution EXACTLY -- and therefore the whole
       time and level component -- and destroys ONLY which opponent a player actually faced.  This
       is the correct-level null for a between-opponent question (D085's entity-swap, at a level
       that also controls the time component).  The whole walk-forward fit is REDONE inside every
       draw, so the null is of the same estimator, not of a fixed coefficient.
    P3 WITHIN-DATE DEMEANED DEFENCE.  Defence minus the date's league mean: the purely
       CROSS-SECTIONAL opponent contrast, with the time component removed. If the effect is a real
       matchup effect it must live here.
    P4 The identical battery applied to the INTERACTION contrast, which is this screen's actual
       headline family.

A PLACEBO THAT REPRODUCES THE RESULT IS A KILL, AND IT IS A COMPLETE ANSWER.
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

DEFENCE = "A10_opp_defrtg"
UCOL = pr.USAGE_MAIN
N_SWAP = 500
TIER_NAMES = {0: "T1_low_usage", 1: "T2_mid_usage", 2: "T3_high_usage", -1: "ALL_TIERS"}


def team_game_units(m):
    """Unit at which the defence value is constant: one (season, team_id, game_id) team-game."""
    key = list(zip(m["season"].astype(int), m["team_id"].astype(str), m["game_id"].astype(str)))
    codes, uq = pd.factorize(pd.Series(key), sort=True)
    return codes, len(uq)


def build_placebos(m, P):
    """P1 league-mean-on-date and P3 within-date-demeaned versions of the defence term."""
    tg, ntg = team_game_units(m)
    m = m.copy()
    m["_tg"] = tg
    unit = m.groupby("_tg", sort=True).agg(season=("season", "first"),
                                           gdate=("game_date", "first"),
                                           dval=(DEFENCE, "first")).reset_index()
    daymean = unit.groupby(["season", "gdate"], sort=False)["dval"].transform("mean")
    unit["_daymean"] = daymean
    unit["_ngames_on_date"] = unit.groupby(["season", "gdate"], sort=False)["dval"].transform("size")
    lut_mean = unit.set_index("_tg")["_daymean"]
    m["P1_leaguemean_on_date"] = lut_mean.reindex(m["_tg"]).to_numpy()
    m["P3_defence_within_date_demeaned"] = (m[DEFENCE].to_numpy()
                                            - m["P1_leaguemean_on_date"].to_numpy())
    P("  placebo construction: %d team-game units, median %d team-games per date; "
      "P1 = league mean defrtg on the date (zero opponent information), "
      "P3 = defrtg minus that mean (pure cross-section)"
      % (ntg, int(unit["_ngames_on_date"].median())))
    P("  corr(defrtg, P1_leaguemean_on_date) = %.4f ; sd(defrtg) = %.4f, sd(P1) = %.4f, sd(P3) = %.4f"
      % (float(np.corrcoef(m[DEFENCE], m["P1_leaguemean_on_date"])[0, 1]),
         float(m[DEFENCE].std()), float(m["P1_leaguemean_on_date"].std()),
         float(m["P3_defence_within_date_demeaned"].std())))
    return m, unit


def swap_within_date(m, unit, rng):
    """P2: permute the defence value among the team-games played on the SAME date."""
    vals = unit["dval"].to_numpy(float).copy()
    out = vals.copy()
    for _, idx in unit.groupby(["season", "gdate"], sort=False).indices.items():
        if len(idx) > 1:
            out[idx] = vals[idx][rng.permutation(len(idx))]
    lut = pd.Series(out, index=unit["_tg"].to_numpy())
    return lut.reindex(m["_tg"]).to_numpy()


def score(m, v, basecols, mask, dvals, ucol, with_int, resp):
    """Walk-forward paired dR2 of [.., defence(+interaction)] over [.., (no defence)]."""
    ssn = m["season"].to_numpy()
    clus = m["_cluster"].to_numpy()
    yy, pa, pb, cc = [], [], [], []
    for s in pr.PREREG["partition"]["scored_seasons"]:
        tr, te = mask & (ssn < s), mask & (ssn == s)
        if tr.sum() < 300 or te.sum() < 80:
            continue
        uc, dc = float(v[ucol][tr].mean()), float(dvals[tr].mean())

        def X(sel, use_d, use_i):
            cols = [np.ones(int(sel.sum()))] + [v[c][sel] for c in basecols] + [v[ucol][sel]]
            if use_d:
                cols.append(dvals[sel])
            if use_i:
                cols.append((v[ucol][sel] - uc) * (dvals[sel] - dc))
            return np.column_stack(cols)

        if with_int:      # interaction contrast: both arms carry the defence main effect
            X0tr, X0te = X(tr, True, False), X(te, True, False)
            X1tr, X1te = X(tr, True, True), X(te, True, True)
        else:             # main-effect contrast: the defence column itself is the increment
            X0tr, X0te = X(tr, False, False), X(te, False, False)
            X1tr, X1te = X(tr, True, False), X(te, True, False)
        b0 = ub.ols(X0tr, v[resp["rate_col"]][tr])
        b1 = ub.ols(X1tr, v[resp["rate_col"]][tr])
        scale = v["_m_hat"][te] if resp["scale_by_minutes"] else 1.0
        pb.append((X0te @ b0) * scale)
        pa.append((X1te @ b1) * scale)
        yy.append(v[resp["target_col"]][te])
        cc.append(clus[te])
    if not yy:
        return None
    y, A, B, C = (np.concatenate(yy), np.concatenate(pa), np.concatenate(pb), np.concatenate(cc))
    sst = float(((y - y.mean()) ** 2).sum())
    dr2 = float((((y - B) ** 2).sum() - ((y - A) ** 2).sum()) / sst)
    return dr2, y, A, B, C


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    ub.hdr("E1_I0023 s05 -- PLACEBOS AND THE WITHIN-DATE OPPONENT-SWAP NULL")
    h, added, dropped = pr.check_prereg()
    P("  PREREG hash %s VERIFIED. cells added=%d dropped=%d" % (h, len(added), len(dropped)))
    P("  PREDECLARED SUSPICION: an expanding-prior opponent rating carries a shared TIME/LEVEL "
      "component. If the placebo carrying only that component reproduces the effect, the effect is "
      "not a matchup effect.")
    m, ncl = s02.build_frame(P)
    m, unit = build_placebos(m, P)

    basecols = pr.BASE_COMPLETE
    need = list(dict.fromkeys(basecols + [UCOL, DEFENCE, "P1_leaguemean_on_date",
                                          "P3_defence_within_date_demeaned", "y_ppm", "y_pts",
                                          "y_spm", "TSA", "_m_hat"]))
    v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}

    rows = []
    for resp_id in ["ppm", "points"]:
        resp = s02.RESP[resp_id]
        for sid in ["POOLED", "DECISION"]:
            base_mask = s02.stratum_mask(m, sid)
            for c in need:
                base_mask &= np.isfinite(v[c])
            first_tr = base_mask & (m["season"].to_numpy()
                                    < pr.PREREG["partition"]["scored_seasons"][0])
            tier_all, _ = ub.usage_terciles(v[UCOL][first_tr] if first_tr.sum() > 200
                                            else v[UCOL][base_mask], v[UCOL])
            for tier in [-1, 2]:                       # ALL tiers and the TOP usage tier
                mask = base_mask if tier == -1 else (base_mask & (tier_all == tier))
                for contrast, with_int in (("MAIN_EFFECT", False), ("INTERACTION", True)):
                    real = score(m, v, basecols, mask, v[DEFENCE], UCOL, with_int, resp)
                    if real is None:
                        continue
                    dr2_real, y, A, B, C = real
                    ct = ub.paired_cluster_test(y, A, B, C, ncl, n_draws=pr.N_DRAWS, seed=ub.SEED)
                    ct.pop("draws_cluster")
                    p1 = score(m, v, basecols, mask, v["P1_leaguemean_on_date"], UCOL, with_int, resp)
                    p3 = score(m, v, basecols, mask, v["P3_defence_within_date_demeaned"], UCOL,
                               with_int, resp)
                    # ---- P2: within-date opponent swap, whole walk-forward redone each draw ----
                    rng = np.random.default_rng(ub.SEED + 99)
                    draws = np.empty(N_SWAP)
                    for k in range(N_SWAP):
                        dv = swap_within_date(m, unit, rng)
                        r = score(m, v, basecols, mask, dv, UCOL, with_int, resp)
                        draws[k] = r[0] if r is not None else np.nan
                    draws = draws[np.isfinite(draws)]
                    p_swap = (1.0 + int((draws >= dr2_real).sum())) / (len(draws) + 1.0)
                    rows.append(dict(
                        response=resp_id, stratum=sid, tier=TIER_NAMES[tier], contrast=contrast,
                        n_scored=int(len(y)), dr2_real=dr2_real,
                        p_cluster_signflip=ct["p_cluster"],
                        dr2_P1_leaguemean_placebo=p1[0] if p1 else np.nan,
                        P1_share_of_real=(p1[0] / dr2_real if p1 and dr2_real != 0 else np.nan),
                        dr2_P3_within_date_demeaned=p3[0] if p3 else np.nan,
                        P3_share_of_real=(p3[0] / dr2_real if p3 and dr2_real != 0 else np.nan),
                        p_P2_within_date_swap=p_swap, n_swap_draws=int(len(draws)),
                        P2_swap_null_mean=float(draws.mean()),
                        P2_swap_null_sd=float(draws.std(ddof=1)),
                        P2_swap_null_p95=float(np.percentile(draws, 95))))
                    r = rows[-1]
                    P("  %-6s %-9s %-14s %-11s n=%5d  REAL dR2=%+.6f (sign-flip p=%.4f)  |  "
                      "P1 league-mean placebo=%+.6f (%.0f%% of real)  |  P3 cross-section=%+.6f "
                      "(%.0f%% of real)  |  P2 SWAP NULL mean=%+.6f sd=%.6f p95=%+.6f  ->  "
                      "p_swap=%.4f"
                      % (resp_id, sid, TIER_NAMES[tier], contrast, r["n_scored"], r["dr2_real"],
                         r["p_cluster_signflip"], r["dr2_P1_leaguemean_placebo"],
                         100 * r["P1_share_of_real"], r["dr2_P3_within_date_demeaned"],
                         100 * r["P3_share_of_real"], r["P2_swap_null_mean"], r["P2_swap_null_sd"],
                         r["P2_swap_null_p95"], r["p_P2_within_date_swap"]))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(ub.OUT, "placebo_diagnostics.csv"), index=False)

    ub.hdr("VERDICT FROM THE PLACEBOS")
    for r in res.itertuples():
        v1 = ("KILLED BY THE PLACEBO -- the league-mean-on-date column, which carries NO opponent "
              "information, reproduces %.0f%% of it" % (100 * r.P1_share_of_real)
              if r.P1_share_of_real > 0.5 else
              "the league-mean placebo does NOT reproduce it (%.0f%%)" % (100 * r.P1_share_of_real))
        v2 = ("and it does NOT survive the within-date opponent swap (p=%.4f)" % r.p_P2_within_date_swap
              if r.p_P2_within_date_swap >= 0.05 else
              "and it DOES survive the within-date opponent swap (p=%.4f)" % r.p_P2_within_date_swap)
        P("  %-6s %-9s %-14s %-11s : %s, %s" % (r.response, r.stratum, r.tier, r.contrast, v1, v2))

    with open(os.path.join(ub.OUT, "_s05.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(prereg_sha256=h, n_swap_draws=N_SWAP,
                       table=json.loads(res.to_json(orient="records"))), fh, indent=2, default=float)
    with open(os.path.join(ub.OUT, "run_log_s05.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote placebo_diagnostics.csv, _s05.json")


if __name__ == "__main__":
    main()
