"""E1_I0018 s05 -- three things s04 left open, plus STEP 5 (mechanism).

(1) THE CEILING PARADOX, RECONCILED.  s04's headline points contrast (DECISION, B_SINGLE, tip-time)
    is paired dR2 = +0.011521, which is LARGER than the D084-form arithmetic ceiling of 0.004278
    computed on the same rows.  That is not a contradiction and it must not be left unexplained.

        D084's ceiling is  Var(forecast shift) / Var(response)  -- the variance the signal's move
        accounts for IF the move IS the true conditional-mean component (which is exactly the
        in-sample OLS increment when the fit and the response are on the SAME scale).

        Here they are NOT on the same scale.  The coefficient is fitted on POINTS-PER-MINUTE, then
        multiplied by minutes to reach POINTS.  Points errors scale with minutes, so the shift is
        UNDER-scaled for points; the realised increment is
            dR2 = (2*sum(d*e) - sum(d*d)) / SST
        and sum(d*e) > sum(d*d) makes it exceed Var(d)/Var(y).  The implied optimal rescaling and
        the resulting ORACLE ceiling are computed here.  THE ORACLE USES THE REALISED RESPONSE and
        is a DIAGNOSTIC ONLY, excluded from every headline -- the same treatment D084 gave its own.

(2) WALK-FORWARD COEFFICIENTS.  s04's propagation fits the screening coefficient IN SAMPLE on the
    same rows it scores.  Constraint 3 of this screen's brief requires the time-window audit to
    cover INFERENCE STEPS, not only features, and an in-sample coefficient reads the whole
    partition.  So the propagation is repeated with the coefficient fitted STRICTLY FORWARD: for
    season s, the screening regression is fitted on seasons < s only and applied to season s.
    2021 has no prior season and is therefore not scored.  This is still the screening regression;
    NO MODEL IS FITTED and the champion is never loaded.

(3) STEP 5 -- MECHANISM AND ITS SIGN, with the sign predicted in advance in
    CANDIDATES_PRESELECTED.md §6:
        usage redistribution -> NEGATIVE coefficient on T01 for ppm and spm
        shot creation        -> POSITIVE
    and the symmetry test: a purely mechanical redistribution is SYMMETRIC between absence and
    return, so the KINK term adds nothing over the linear deviation.  The kink is screened with the
    same three nulls as everything else.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_base import ENTITY_TEAM, N_DRAWS, OUT, SEED, BaseFit, hdr, mae, run_nulls, sk

f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f, verbose=True)
f["_m_hat"] = f["prior5_minutes"].fillna(f["refB_mpg"])
STRATA = {"POOLED": np.ones(len(f), bool),
          "DECISION": ((f["n_prior"] >= 8).to_numpy()
                       & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool))}
BASES = {"B_SINGLE": ["refB_ppm"],
         "B_COMPLETE": ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg"]}
CANDS = ["T01_c04_tiptime", "P01_c04_prevgame", "P02_c04_availweighted", "G01_noise"]

# =====================================================================================
hdr("1. THE CEILING PARADOX, RECONCILED -- and the ORACLE rescaling (DIAGNOSTIC ONLY)")
# =====================================================================================
rec = []
for sname, smask in STRATA.items():
    for bname, basecols in BASES.items():
        for cand in CANDS:
            cols = [cand, "y_ppm", "y_pts", "_m_hat"] + basecols
            v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
            m = smask.copy()
            for c in cols:
                m &= np.isfinite(v[c])
            y_ppm, y_pts, mh = v["y_ppm"][m], v["y_pts"][m], v["_m_hat"][m]
            B = np.column_stack([v[c][m] for c in basecols])
            x = v[cand][m]
            bf = BaseFit(y_ppm, B)
            pts_ref = bf.fitted_base() * mh
            d = (bf.fitted_with(x) - bf.fitted_base()) * mh      # the forecast SHIFT, in points
            e = y_pts - pts_ref                                   # the reference's points residual
            sst = float(((y_pts - y_pts.mean()) ** 2).sum())
            sdd, sde = float(d @ d), float(d @ e)
            realised = (2 * sde - sdd) / sst
            var_share = sdd / sst                                 # the D084-form ceiling
            oracle = (sde * sde) / (sdd * sst) if sdd > 0 else np.nan   # DIAGNOSTIC: uses response
            c_opt = sde / sdd if sdd > 0 else np.nan
            rec.append(dict(stratum=sname, base=bname, candidate=cand, n=int(m.sum()),
                            realised_paired_dr2_points=float(realised),
                            D084_form_ceiling_var_share=float(var_share),
                            implied_optimal_rescaling=float(c_opt),
                            DIAGNOSTIC_ORACLE_ceiling_best_rescaling=float(oracle),
                            corr_shift_with_reference_residual=float(
                                np.corrcoef(d, e)[0, 1]),
                            r2_of_reference_points=float(sk.r2_of_forecast(y_pts, pts_ref))))
            r = rec[-1]
            print("  %-9s %-11s %-22s realised dR2 %+.6f | D084-form ceiling %.6f | "
                  "optimal rescale x%.3f | ORACLE(diagnostic) %.6f"
                  % (sname, bname, cand, r["realised_paired_dr2_points"],
                     r["D084_form_ceiling_var_share"], r["implied_optimal_rescaling"],
                     r["DIAGNOSTIC_ORACLE_ceiling_best_rescaling"]))
ceil_df = pd.DataFrame(rec)
ceil_df.to_csv(os.path.join(OUT, "ceiling_reconciliation.csv"), index=False)
print("\n  IDENTITY CHECK: realised = 2*c_opt*var_share - var_share, and ORACLE = c_opt^2*var_share")
_chk = np.max(np.abs(ceil_df["realised_paired_dr2_points"]
                     - (2 * ceil_df["implied_optimal_rescaling"]
                        * ceil_df["D084_form_ceiling_var_share"]
                        - ceil_df["D084_form_ceiling_var_share"])))
print("  max |realised - (2*c_opt-1)*var_share| = %.3e" % _chk)

# =====================================================================================
hdr("2. WALK-FORWARD COEFFICIENTS -- fitted on seasons < s, applied to season s")
# =====================================================================================
wf = []
for sname, smask in STRATA.items():
    for bname, basecols in BASES.items():
        for cand in CANDS:
            cols = [cand, "y_ppm", "y_pts", "_m_hat"] + basecols
            v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
            m = smask.copy()
            for c in cols:
                m &= np.isfinite(v[c])
            ssn = f["season"].to_numpy()
            pr, pc, yy, gg = [], [], [], []
            for s in (2022, 2023, 2024):
                tr = m & (ssn < s)
                te = m & (ssn == s)
                if tr.sum() < 500 or te.sum() < 100:
                    continue
                Btr = np.column_stack([np.ones(tr.sum())] + [v[c][tr] for c in basecols])
                Bte = np.column_stack([np.ones(te.sum())] + [v[c][te] for c in basecols])
                bb, *_ = np.linalg.lstsq(Btr, v["y_ppm"][tr], rcond=None)
                Ftr = np.column_stack([Btr, v[cand][tr]])
                Fte = np.column_stack([Bte, v[cand][te]])
                bf_, *_ = np.linalg.lstsq(Ftr, v["y_ppm"][tr], rcond=None)
                pr.append((Bte @ bb) * v["_m_hat"][te])
                pc.append((Fte @ bf_) * v["_m_hat"][te])
                yy.append(v["y_pts"][te])
                gg.append(sk._group_codes(f.loc[te, ["team_id", "season"]], ["team_id", "season"]))
            if not yy:
                continue
            y = np.concatenate(yy); a = np.concatenate(pc); b = np.concatenate(pr)
            g = np.concatenate([gi + 1000 * k for k, gi in enumerate(gg)])
            pfc = sk.paired_forecast_comparison(y, a, b, groups=g, n_draws=2000, seed=SEED)
            wf.append(dict(stratum=sname, base=bname, candidate=cand, n_scored=int(len(y)),
                           seasons_scored="2022,2023,2024",
                           r2_reference=float(sk.r2_of_forecast(y, b)),
                           r2_with_candidate=float(sk.r2_of_forecast(y, a)),
                           walkforward_paired_dr2_points=float(pfc["dr2_a_minus_b"]),
                           paired_p_cluster=float(pfc["p"]),
                           paired_p_row_NAIVE=float(pfc["p_row_level_NAIVE"]),
                           mae_reference=mae(y, b), mae_with_candidate=mae(y, a),
                           mae_pct_reduction=float(100 * (1 - mae(y, a) / mae(y, b)))))
            r = wf[-1]
            print("  %-9s %-11s %-22s n=%5d  R2 %+.6f -> %+.6f   WALK-FORWARD paired dR2 %+.6f  "
                  "cluster p=%.4f  (MAE %.4f -> %.4f, %.3f%%)"
                  % (sname, bname, cand, r["n_scored"], r["r2_reference"], r["r2_with_candidate"],
                     r["walkforward_paired_dr2_points"], r["paired_p_cluster"],
                     r["mae_reference"], r["mae_with_candidate"], r["mae_pct_reduction"]))
wf_df = pd.DataFrame(wf)
wf_df.to_csv(os.path.join(OUT, "walkforward_points.csv"), index=False)

# =====================================================================================
hdr("3. STEP 5 -- MECHANISM.  THE SIGN WAS PREDICTED IN ADVANCE.")
# =====================================================================================
print("  PREDICTION (CANDIDATES_PRESELECTED.md §6, frozen before any statistic):")
print("    usage redistribution -> NEGATIVE on ppm AND spm ;  shot creation -> POSITIVE")
mech = []
for sname, smask in STRATA.items():
    for oc, refc in [("ppm", "refB_ppm"), ("spm", "refB_spm")]:
        for cand in ["T01_c04_tiptime", "T02_teamgame_present_usg", "T03_absent_usg",
                     "P01_c04_prevgame"]:
            cols = [cand, "y_" + oc, refc]
            v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
            m = smask.copy()
            for c in cols:
                m &= np.isfinite(v[c])
            bf = BaseFit(v["y_" + oc][m], v[refc][m])
            x = v[cand][m]
            q = np.quantile(x, [0.10, 0.90])
            lo, hi = x <= q[0], x >= q[1]
            resid = bf.e
            spread = float(np.mean(resid[hi]) - np.mean(resid[lo]))
            mm = float(np.mean(f.loc[m, "_m_hat"]))
            mech.append(dict(stratum=sname, outcome=oc, candidate=cand, n=int(m.sum()),
                             beta=float(bf.beta(x)), sign=float(bf.beta_sign(x)),
                             p10=float(q[0]), p90=float(q[1]),
                             decile_spread_on_reference_residual=spread,
                             mean_m_hat=mm,
                             per_game_equivalent=float(spread * mm)))
            r = mech[-1]
            unit = "shots" if oc == "spm" else "points"
            print("  %-9s %-5s %-26s beta=%+.6f sign %+.0f   p10->p90 spread on the reference "
                  "residual = %+.5f %s/min = %+.4f %s/game at %.1f min"
                  % (sname, oc, cand, r["beta"], r["sign"], spread, unit,
                     r["per_game_equivalent"], unit, mm))
mech_df = pd.DataFrame(mech)
mech_df.to_csv(os.path.join(OUT, "mechanism_signs.csv"), index=False)

# =====================================================================================
hdr("4. STEP 5b -- SYMMETRY: is absence the mirror of return?  THE KINK TEST.")
# =====================================================================================
# dev = T01 - (strictly-prior running norm).  Base = [1, ref, dev].  Candidate = min(dev,0).
# A purely mechanical redistribution is SYMMETRIC -> the kink adds nothing.
sym = []
for sname, smask in STRATA.items():
    for oc, refc in [("ppm", "refB_ppm"), ("spm", "refB_spm")]:
        for norm, poscol, negcol in [("team_norm", "M01_dev_pos", "M02_dev_neg"),
                                     ("player_norm", "M03_dev_pos_playernorm",
                                      "M04_dev_neg_playernorm")]:
            cols = [poscol, negcol, "y_" + oc, refc]
            v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
            m = smask.copy()
            for c in cols:
                m &= np.isfinite(v[c])
            if m.sum() < 400:
                continue
            y = v["y_" + oc][m]
            dev = v[poscol][m] + v[negcol][m]
            kink = v[negcol][m]
            # (a) both arms free
            Xb = np.column_stack([v[refc][m]])
            bf_both = BaseFit(y, np.column_stack([Xb, v[poscol][m], v[negcol][m]]))
            X = np.column_stack([np.ones(m.sum()), Xb, v[poscol][m], v[negcol][m]])
            bb, *_ = np.linalg.lstsq(X, y, rcond=None)
            b_pos, b_neg = float(bb[-2]), float(bb[-1])
            # (b) the kink test: does min(dev,0) add over the LINEAR dev?
            bf_lin = BaseFit(y, np.column_stack([Xb, dev]))
            d = f.loc[m, ["season", "player_id", "team_id", "opp_team_id", "game_id",
                          "game_date"]].reset_index(drop=True)
            nl = run_nulls(bf_lin, d, kink, ENTITY_TEAM[1], n_draws=N_DRAWS, seed=SEED)
            nl.pop("draws_N1"); nl.pop("draws_N2")
            sym.append(dict(stratum=sname, outcome=oc, norm=norm, n=int(m.sum()),
                            beta_dev_pos_returns=b_pos, beta_dev_neg_absences=b_neg,
                            asymmetry_ratio=float(b_pos / b_neg) if b_neg != 0 else np.nan,
                            beta_linear_dev=float(bf_lin.beta(dev)),
                            dr2_kink_over_linear=float(nl["real"]), **nl))
            r = sym[-1]
            print("  %-9s %-5s %-12s n=%5d  beta(returns)=%+.6f  beta(absences)=%+.6f  "
                  "ratio=%.3f   KINK dR2 over the linear dev = %.6f  p_N1=%.4f p_N2=%.4f"
                  % (sname, oc, norm, r["n"], b_pos, b_neg, r["asymmetry_ratio"],
                     r["dr2_kink_over_linear"], r["p_N1_within_entity"], r["p_N2_entity_swap"]))
sym_df = pd.DataFrame(sym)
sym_df.to_csv(os.path.join(OUT, "symmetry_kink_test.csv"), index=False)

with open(os.path.join(OUT, "_s05.json"), "w", encoding="utf-8") as fh:
    json.dump({"ceiling_reconciliation": json.loads(ceil_df.to_json(orient="records")),
               "walkforward_points": json.loads(wf_df.to_json(orient="records")),
               "mechanism_signs": json.loads(mech_df.to_json(orient="records")),
               "symmetry_kink_test": json.loads(sym_df.to_json(orient="records"))},
              fh, indent=2, default=str)
print("\n  wrote ceiling_reconciliation.csv, walkforward_points.csv, mechanism_signs.csv, "
      "symmetry_kink_test.csv, _s05.json")
