"""
s04 -- STEP 4: THE SINGLE-PLAYER CEILING.  What is achievable with maximum data on one player?

THE USER ASKED FOR THIS DIRECTLY: "we can have a different model per player if we have to".  D091
authorises per-player fitting in the exploration lane.  The CHAMPION IS NOT TOUCHED anywhere here --
no champion forecast is refitted, and none is even read.

TRAP 4 IS THE WHOLE DESIGN CONSTRAINT.  A per-player coefficient fitted on all of a player's games
and applied to those same games is in-sample and meaningless, and the program has been caught by a
retrospective baseline six times, once inside the inference machinery itself.  So:
  * every coefficient scoring game i is fitted ONLY on that player's games strictly EARLIER than
    game i by DATE (expanding walk-forward).  Leave-one-game-out is deliberately NOT used: it reads
    later games, which is precisely the trap.
  * the reference is that same player's strictly-prior expanding mean rate, scored on the SAME rows.
  * an in-sample full-fit R2 is also reported and is LABELLED AN UNATTAINABLE UPPER BOUND, present
    only to show how much of the apparent fit is optimism.

CONDITIONING: figures under the realised-minutes floor answer "given this player got meaningful
minutes, is their rate predictable"; they are not live forecasting increments.
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

MIN_PRIOR_FIT = 25          # games strictly before the scored game required to fit at all
N_TOP_PLAYERS = 5
FEATURES_FULL = [r["x"] for r in pr.RELATIONSHIPS]
FEATURES_ONE = ["A10_opp_defrtg"]     # the one axis s03d showed carries structure


def ols_fit(X, y):
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return beta


def ols_pred(beta, x):
    return float(beta[0] + float(np.dot(beta[1:], x)))


def r2_forecast(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    ok = np.isfinite(y) & np.isfinite(yhat)
    y, yhat = y[ok], yhat[ok]
    sst = float(((y - y.mean()) ** 2).sum())
    sse = float(((y - yhat) ** 2).sum())
    return 1.0 - sse / sst if sst > 0 else np.nan


def walk_forward_player(g, features):
    """Expanding-window per-player OLS.  Row i is scored by a fit on rows 0..i-1 ONLY.

    `g` must already be sorted by date for this one player.  Returns arrays aligned to the rows
    that could be scored (those with at least MIN_PRIOR_FIT usable earlier rows).
    """
    X = g[features].to_numpy(float)
    y = g["y_ppm_floor"].to_numpy(float)
    n = len(g)
    preds = np.full(n, np.nan)
    for i in range(n):
        if i < MIN_PRIOR_FIT:
            continue
        Xtr, ytr = X[:i], y[:i]
        ok = np.isfinite(ytr) & np.isfinite(Xtr).all(axis=1)
        if ok.sum() < MIN_PRIOR_FIT or not np.isfinite(X[i]).all():
            continue
        Xo, yo = Xtr[ok], ytr[ok]
        if np.linalg.matrix_rank(np.column_stack([np.ones(len(Xo)), Xo])) < Xo.shape[1] + 1:
            continue
        preds[i] = ols_pred(ols_fit(Xo, yo), X[i])
    return preds


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    hb.hdr("E1_I0021 s04 -- THE SINGLE-PLAYER CEILING")
    h, _, _ = s02.check_prereg()
    P("  PREREG hash %s VERIFIED" % h)
    m = s02.build_merged(verbose=True)

    rows = []
    for floor in [0, pr.HEADLINE_FLOOR]:
        s = s02.floor_subset(m, floor)
        s, _ = s02.complete_case(s)
        s = s.sort_values(["player_id", "game_date"]).reset_index(drop=True)
        counts = s.groupby("player_id").size().sort_values(ascending=False)
        top = list(counts.index[:N_TOP_PLAYERS])
        P("")
        P("  ==== FLOOR %d min ====  top %d players by retained games: %s"
          % (floor, N_TOP_PLAYERS, ", ".join("id%s(n=%d)" % (p, counts[p]) for p in top)))
        P("  Every figure below conditions on realised minutes and is a MEASUREMENT, not a live "
          "forecasting increment.")
        for pid in top:
            g = s[s.player_id == pid].sort_values("game_date").reset_index(drop=True)
            y = g["y_ppm_floor"].to_numpy(float)

            # strictly-prior expanding mean of this player's own rate -- the no-skill reference
            ref0 = pd.Series(y).shift(1).expanding().mean().to_numpy()
            ref1 = pd.to_numeric(g["refB_ppm"], errors="coerce").to_numpy(float)

            pf = walk_forward_player(g, FEATURES_FULL)
            p1 = walk_forward_player(g, FEATURES_ONE)

            scored = np.isfinite(pf) & np.isfinite(p1) & np.isfinite(ref0) & np.isfinite(ref1) \
                & np.isfinite(y)
            ns = int(scored.sum())
            if ns < 20:
                P("    player id%s : only %d scorable rows -- skipped" % (pid, ns))
                continue
            yy = y[scored]
            out = {}
            for tag, pv in (("wf_6feature", pf[scored]), ("wf_1feature_oppdefrtg", p1[scored]),
                            ("ref_prior_mean", ref0[scored]), ("ref_refB_prior_ratio", ref1[scored])):
                out[tag] = dict(mae=float(np.mean(np.abs(yy - pv))), r2=r2_forecast(yy, pv))

            # in-sample full fit -- UNATTAINABLE UPPER BOUND, reported to expose the optimism
            Xf = g.loc[scored, FEATURES_FULL].to_numpy(float)
            b_in = ols_fit(Xf, yy)
            yhat_in = np.column_stack([np.ones(len(Xf)), Xf]) @ b_in
            r2_in = r2_forecast(yy, yhat_in)

            base_mae = out["ref_prior_mean"]["mae"]
            best_ref_tag = min(("ref_prior_mean", "ref_refB_prior_ratio"),
                               key=lambda t: out[t]["mae"])
            best_ref_mae = out[best_ref_tag]["mae"]
            sk6 = 1 - out["wf_6feature"]["mae"] / best_ref_mae
            sk1 = 1 - out["wf_1feature_oppdefrtg"]["mae"] / best_ref_mae
            rows.append(dict(
                floor=floor, player_id=int(pid), n_retained=int(counts[pid]), n_scored=ns,
                y_sd=float(np.std(yy, ddof=1)), y_mean=float(np.mean(yy)),
                mae_wf_6feature=out["wf_6feature"]["mae"], r2_wf_6feature=out["wf_6feature"]["r2"],
                mae_wf_1feature=out["wf_1feature_oppdefrtg"]["mae"],
                r2_wf_1feature=out["wf_1feature_oppdefrtg"]["r2"],
                mae_ref_prior_mean=base_mae, r2_ref_prior_mean=out["ref_prior_mean"]["r2"],
                mae_ref_refB=out["ref_refB_prior_ratio"]["mae"],
                r2_ref_refB=out["ref_refB_prior_ratio"]["r2"],
                best_reference=best_ref_tag, best_ref_mae=best_ref_mae,
                skill_6feature_vs_best_ref=sk6, skill_1feature_vs_best_ref=sk1,
                r2_INSAMPLE_UPPER_BOUND_not_attainable=r2_in))
            P("    player id%-7s n_retained=%3d  n_scored=%3d  ppm sd=%.4f | "
              "walk-forward 6-feature: MAE=%.4f R2=%+.4f skill vs best prior ref=%+6.2f%% | "
              "1-feature: MAE=%.4f skill=%+6.2f%% | best prior ref (%s) MAE=%.4f | "
              "IN-SAMPLE R2 (UPPER BOUND, NOT ATTAINABLE)=%+.4f"
              % (pid, counts[pid], ns, float(np.std(yy, ddof=1)),
                 out["wf_6feature"]["mae"], out["wf_6feature"]["r2"], 100 * sk6,
                 out["wf_1feature_oppdefrtg"]["mae"], 100 * sk1,
                 best_ref_tag, best_ref_mae, r2_in))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(hb.OUT, "single_player_ceiling.csv"), index=False)

    hb.hdr("THE CEILING, STATED PLAINLY")
    for floor in sorted(res.floor.unique()):
        sl = res[res.floor == floor]
        P("  floor %2d : across the %d best-sampled players, walk-forward per-player skill against "
          "that player's own strictly-prior reference is %+.2f%% (6-feature) and %+.2f%% "
          "(1-feature), median R2 %+.4f; the IN-SAMPLE upper bound is R2 %+.4f."
          % (floor, len(sl), 100 * sl["skill_6feature_vs_best_ref"].mean(),
             100 * sl["skill_1feature_vs_best_ref"].mean(),
             sl["r2_wf_6feature"].median(),
             sl["r2_INSAMPLE_UPPER_BOUND_not_attainable"].median()))
    P("")
    P("  n_scored is small by construction: a per-player walk-forward needs %d prior games before "
      "it can score anything, and the best-sampled player in the partition has fewer than 130 "
      "retained games in total." % MIN_PRIOR_FIT)

    out = dict(prereg_sha256=h, min_prior_fit=MIN_PRIOR_FIT, n_top_players=N_TOP_PLAYERS,
               features_full=FEATURES_FULL, features_one=FEATURES_ONE,
               summary={int(f): dict(
                   mean_skill_6feature=float(res[res.floor == f]["skill_6feature_vs_best_ref"].mean()),
                   mean_skill_1feature=float(res[res.floor == f]["skill_1feature_vs_best_ref"].mean()),
                   median_r2_wf=float(res[res.floor == f]["r2_wf_6feature"].median()),
                   median_r2_insample_upper_bound=float(
                       res[res.floor == f]["r2_INSAMPLE_UPPER_BOUND_not_attainable"].median()))
                   for f in sorted(res.floor.unique())})
    with open(os.path.join(hb.OUT, "_s04.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(hb.OUT, "run_log_s04.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote single_player_ceiling.csv, _s04.json")


if __name__ == "__main__":
    main()
