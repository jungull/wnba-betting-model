"""
s04 -- STEP 4 (is the heterogeneity EXPLOITABLE?) and STEP 5 (does cancellation explain the dead
main effect?).

STEP 4.  If the interaction helps, WHERE?  The gain is decomposed by USAGE TIER, where the tier is
    assigned from tercile cut points computed on the TRAINING seasons only and applied forward -- so
    a tier label could genuinely have been attached before tip-off.  D093 found the coefficient
    variation is EXPLAINABLE by an observable; this checks whether that survives being used for
    forecasting rather than measured as a correlation.

STEP 5.  THE RECONCILIATION THAT DECIDES WHAT THIS IS.
    The opponent-defence MAIN effect is comprehensively dead: 12 constructions, 0 of 36 cells
    (D085).  The hypothesis under test is that the main effect is null BECAUSE IT IS HETEROGENEOUS
    -- strong for high-usage players, weak or absent for low-usage ones, cancelling in the pooled
    average.  That is directly testable: fit the main effect WITHIN each usage tier and look at the
    signs.

    IF THE MAIN EFFECT IS UNIFORMLY NULL INSIDE EVERY TIER, the interaction is NOT rescuing a
    cancelled effect, and this screen must say so -- that would make the interaction something else,
    and quite possibly an artefact.  The prediction is registered here before the numbers:
        CANCELLATION  -> main effect POSITIVE in the top usage tier, ~zero or NEGATIVE in the bottom
        NOT CANCELLATION -> main effect ~zero in every tier
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

TIER_NAMES = {0: "T1_low_usage", 1: "T2_mid_usage", 2: "T3_high_usage"}
DEFENCE = "A10_opp_defrtg"
UCOL = pr.USAGE_MAIN


def walk_folds(m, mask):
    ssn = m["season"].to_numpy()
    return [(mask & (ssn < s), mask & (ssn == s)) for s in pr.PREREG["partition"]["scored_seasons"]]


def main():
    log = []

    def P(x=""):
        print(x)
        log.append(str(x))

    ub.hdr("E1_I0023 s04 -- STEP 4 (usage tiers) and STEP 5 (main effect by tier)")
    h, added, dropped = pr.check_prereg()
    P("  PREREG hash %s VERIFIED. cells added=%d dropped=%d" % (h, len(added), len(dropped)))
    P("  REGISTERED PREDICTION for step 5, written before the numbers: if the dead main effect is a "
      "CANCELLATION, it is POSITIVE in the top usage tier and ~zero or NEGATIVE in the bottom. If "
      "it is ~zero in every tier, the interaction is not rescuing a cancelled effect.")
    m, ncl = s02.build_frame(P)
    basecols = pr.BASE_COMPLETE

    # =============================================================== STEP 4: tiers
    ub.hdr("STEP 4 -- WHERE DOES THE INTERACTION'S GAIN LIVE?  BY PRE-GAME USAGE TERCILE")
    tier_rows = []
    for resp_id in ["ppm", "points"]:
        r = s02.RESP[resp_id]
        for sid in ["POOLED", "DECISION"]:
            need = list(dict.fromkeys(basecols + [UCOL, DEFENCE, r["rate_col"], r["target_col"],
                                                  "_m_hat"]))
            v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}
            mask = s02.stratum_mask(m, sid)
            for c in need:
                mask &= np.isfinite(v[c])
            clus = m["_cluster"].to_numpy()
            yy, pa, pb, cc, tt, cutpoints = [], [], [], [], [], []
            for tr, te in walk_folds(m, mask):
                if tr.sum() < 500 or te.sum() < 100:
                    continue
                uc, dc = float(v[UCOL][tr].mean()), float(v[DEFENCE][tr].mean())
                Xb_tr = s02.design(v, basecols, tr, UCOL, DEFENCE, uc, dc, False)
                Xa_tr = s02.design(v, basecols, tr, UCOL, DEFENCE, uc, dc, True)
                Xb_te = s02.design(v, basecols, te, UCOL, DEFENCE, uc, dc, False)
                Xa_te = s02.design(v, basecols, te, UCOL, DEFENCE, uc, dc, True)
                bb = ub.ols(Xb_tr, v[r["rate_col"]][tr])
                ba = ub.ols(Xa_tr, v[r["rate_col"]][tr])
                scale = v["_m_hat"][te] if r["scale_by_minutes"] else 1.0
                pb.append((Xb_te @ bb) * scale)
                pa.append((Xa_te @ ba) * scale)
                yy.append(v[r["target_col"]][te])
                cc.append(clus[te])
                tier, q = ub.usage_terciles(v[UCOL][tr], v[UCOL][te])
                tt.append(tier)
                cutpoints.append(q)
            if not yy:
                continue
            y, A, B = np.concatenate(yy), np.concatenate(pa), np.concatenate(pb)
            C, T = np.concatenate(cc), np.concatenate(tt)
            qs = np.mean(np.vstack(cutpoints), axis=0)
            for t in [0, 1, 2]:
                s = T == t
                if s.sum() < 100:
                    continue
                res = ub.paired_cluster_test(y[s], A[s], B[s], C[s], ncl, n_draws=pr.N_DRAWS,
                                             seed=ub.SEED)
                res.pop("draws_cluster")
                tier_rows.append(dict(response=resp_id, stratum=sid, tier=TIER_NAMES[t],
                                      n=int(s.sum()),
                                      tier_cut_low=float(qs[0]), tier_cut_high=float(qs[1]),
                                      mae_without=ub.mae(y[s], B[s]), mae_with=ub.mae(y[s], A[s]),
                                      mae_pct_reduction=float(
                                          100 * (1 - ub.mae(y[s], A[s]) / ub.mae(y[s], B[s]))),
                                      **res))
                q = tier_rows[-1]
                P("  %-7s %-9s %-14s n=%5d  dR2=%+.6f  cluster p=%.4f  MAE %.5f -> %.5f (%+.3f%%)"
                  % (resp_id, sid, TIER_NAMES[t], q["n"], q["dr2_a_minus_b"], q["p_cluster"],
                     q["mae_without"], q["mae_with"], q["mae_pct_reduction"]))
    tdf = pd.DataFrame(tier_rows)
    tdf.to_csv(os.path.join(ub.OUT, "usage_tier_gain.csv"), index=False)

    # =============================================================== STEP 5: main effect by tier
    ub.hdr("STEP 5 -- THE OPPONENT-DEFENCE MAIN EFFECT WITHIN EACH USAGE TIER")
    P("  Arms: [1, COMPLETE reference, usage] vs [1, COMPLETE reference, usage, DEFENCE]. The "
      "interaction is NOT in either arm -- this is the pure main effect, fitted inside a tier.")
    me_rows = []
    for resp_id in ["ppm", "points"]:
        r = s02.RESP[resp_id]
        for sid in ["POOLED", "DECISION"]:
            need = list(dict.fromkeys(basecols + [UCOL, DEFENCE, r["rate_col"], r["target_col"],
                                                  "_m_hat"]))
            v = {c: pd.to_numeric(m[c], errors="coerce").to_numpy(float) for c in need}
            mask = s02.stratum_mask(m, sid)
            for c in need:
                mask &= np.isfinite(v[c])
            clus = m["_cluster"].to_numpy()

            # ---- tier labels for the WHOLE masked frame, from the earliest training fold ----
            first_tr = mask & (m["season"].to_numpy() < pr.PREREG["partition"]["scored_seasons"][0])
            base_u = v[UCOL][first_tr] if first_tr.sum() > 200 else v[UCOL][mask]
            tier_all, qq = ub.usage_terciles(base_u, v[UCOL])
            for t in [0, 1, 2]:
                tm = mask & (tier_all == t)
                # ---------- in-sample slope of the defence term inside the tier ----------
                X0 = s02.design(v, basecols, tm, UCOL, DEFENCE, 0.0, 0.0, False)
                X0 = X0[:, :-1]                    # drop the defence column -> arm WITHOUT
                yr = v[r["rate_col"]][tm]
                X1 = np.column_stack([X0, v[DEFENCE][tm]])
                b1 = ub.ols(X1, yr)
                resid = yr - X1 @ b1
                dofn = max(len(yr) - X1.shape[1], 1)
                XtX_inv = np.linalg.pinv(X1.T @ X1)
                s2 = float(resid @ resid) / dofn
                se = float(np.sqrt(max(s2 * XtX_inv[-1, -1], 0.0)))
                beta_d = float(b1[-1])
                # cluster-robust se (opponent-team-season), because rows sharing an opponent-season
                # are not independent -- the naive se is anticonservative here by construction
                cl = clus[tm]
                u = X1 * resid[:, None]
                meat = np.zeros((X1.shape[1], X1.shape[1]))
                for g in np.unique(cl):
                    ug = u[cl == g].sum(axis=0)
                    meat += np.outer(ug, ug)
                V = XtX_inv @ meat @ XtX_inv
                se_cl = float(np.sqrt(max(V[-1, -1], 0.0)))

                # ---------- walk-forward paired dR2 of the main effect inside the tier ----------
                yy, pa, pb, cc = [], [], [], []
                for tr, te in walk_folds(m, tm):
                    if tr.sum() < 300 or te.sum() < 80:
                        continue
                    X0tr = s02.design(v, basecols, tr, UCOL, DEFENCE, 0.0, 0.0, False)[:, :-1]
                    X0te = s02.design(v, basecols, te, UCOL, DEFENCE, 0.0, 0.0, False)[:, :-1]
                    X1tr = np.column_stack([X0tr, v[DEFENCE][tr]])
                    X1te = np.column_stack([X0te, v[DEFENCE][te]])
                    b0 = ub.ols(X0tr, v[r["rate_col"]][tr])
                    bw = ub.ols(X1tr, v[r["rate_col"]][tr])
                    scale = v["_m_hat"][te] if r["scale_by_minutes"] else 1.0
                    pb.append((X0te @ b0) * scale)
                    pa.append((X1te @ bw) * scale)
                    yy.append(v[r["target_col"]][te])
                    cc.append(clus[te])
                if yy:
                    y, A, B = np.concatenate(yy), np.concatenate(pa), np.concatenate(pb)
                    res = ub.paired_cluster_test(y, A, B, np.concatenate(cc), ncl,
                                                 n_draws=pr.N_DRAWS, seed=ub.SEED)
                    res.pop("draws_cluster")
                    n_sc = int(len(y))
                else:
                    res = dict(dr2_a_minus_b=np.nan, p_cluster=np.nan, p_row_NAIVE=np.nan,
                               n_clusters_present=0, null_sd_cluster=np.nan, null_sd_row=np.nan,
                               null_width_inflation_cluster_over_row=np.nan)
                    n_sc = 0
                me_rows.append(dict(response=resp_id, stratum=sid, tier=TIER_NAMES[t],
                                    n_rows_in_tier=int(tm.sum()), n_scored_walkforward=n_sc,
                                    mean_prior_usage=float(np.mean(v[UCOL][tm])),
                                    tier_cut_low=float(qq[0]), tier_cut_high=float(qq[1]),
                                    beta_defence_in_sample=beta_d, se_naive=se,
                                    t_naive=beta_d / se if se > 0 else np.nan,
                                    se_cluster_robust=se_cl,
                                    t_cluster_robust=beta_d / se_cl if se_cl > 0 else np.nan,
                                    **res))
                q = me_rows[-1]
                P("  %-7s %-9s %-14s n=%5d  mean prior usage=%.4f  MAIN-EFFECT beta=%+.6e  "
                  "t_naive=%+.2f  t_cluster=%+.2f   walk-forward dR2=%+.6f  cluster p=%.4f"
                  % (resp_id, sid, TIER_NAMES[t], q["n_rows_in_tier"], q["mean_prior_usage"],
                     q["beta_defence_in_sample"], q["t_naive"], q["t_cluster_robust"],
                     q["dr2_a_minus_b"], q["p_cluster"]))
    mdf = pd.DataFrame(me_rows)
    mdf.to_csv(os.path.join(ub.OUT, "usage_tier_maineffect.csv"), index=False)

    ub.hdr("IS THE DEAD MAIN EFFECT EXPLAINED BY CANCELLATION?")
    verdicts = {}
    for resp_id in ["ppm", "points"]:
        for sid in ["POOLED", "DECISION"]:
            q = mdf[(mdf.response == resp_id) & (mdf.stratum == sid)].set_index("tier")
            lo = q.loc["T1_low_usage"]
            hi = q.loc["T3_high_usage"]
            monotone = bool(q["beta_defence_in_sample"].is_monotonic_increasing)
            signs_differ = bool(np.sign(lo["beta_defence_in_sample"])
                                != np.sign(hi["beta_defence_in_sample"]))
            any_sig = bool((q["t_cluster_robust"].abs() > 1.96).any())
            v = ("CANCELLATION SUPPORTED" if (signs_differ and any_sig)
                 else ("MONOTONE IN USAGE but no tier is individually significant"
                       if monotone and not any_sig
                       else "NOT CANCELLATION: the main effect is not significant in any tier"
                       if not any_sig else "MIXED"))
            verdicts["%s|%s" % (resp_id, sid)] = v
            P("  %-7s %-9s  low-tier beta=%+.3e (t_cl %+.2f)  high-tier beta=%+.3e (t_cl %+.2f)  "
              "monotone=%s  ->  %s"
              % (resp_id, sid, lo["beta_defence_in_sample"], lo["t_cluster_robust"],
                 hi["beta_defence_in_sample"], hi["t_cluster_robust"], monotone, v))

    out = dict(prereg_sha256=h, tier_gain=json.loads(tdf.to_json(orient="records")),
               main_effect_by_tier=json.loads(mdf.to_json(orient="records")),
               cancellation_verdicts=verdicts)
    with open(os.path.join(ub.OUT, "_s04.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, default=float)
    with open(os.path.join(ub.OUT, "run_log_s04.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log))
    P("  wrote usage_tier_gain.csv, usage_tier_maineffect.csv, _s04.json")


if __name__ == "__main__":
    main()
