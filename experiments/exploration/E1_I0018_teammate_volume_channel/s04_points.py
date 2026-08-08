"""E1_I0018 s04 -- STEP 4: DOES IT REACH POINTS, AND WHAT IS THE ARITHMETIC CEILING?

TWO THINGS ARE DONE HERE AND THEY ANSWER DIFFERENT QUESTIONS.

(1) PROPAGATION.  A points forecast is built and scored against a MATCHED POINT-IN-TIME REFERENCE
    FACING THE SAME ROWS, with screenkit.paired_forecast_comparison and a whole-cluster sign-flip
    null at team_season.  D076's rule is obeyed throughout: raw MAE reduction is NOT differential
    skill, and both are reported side by side so they can never be confused.

    points_forecast = ppm_forecast x minutes_forecast

    minutes_forecast `m_hat` is STRICTLY PRIOR: the player's trailing-5 prior mean minutes, with
    the expanding prior mean minutes as the cold fallback.  It is IDENTICAL in the reference and
    the candidate forecast, so the contrast isolates the per-minute step exactly as D081 framed it.
    Using realised minutes would read the response; it is computed ONLY as a loudly-labelled
    ORACLE-MINUTES DIAGNOSTIC and is excluded from every headline.

    THE PPM FORECAST IS AN IN-SAMPLE SCREENING REGRESSION FIT, y_ppm ~ 1 + base + candidate.  That
    is an UPPER BOUND on out-of-sample skill, not an estimate of it.  It is stated that way
    everywhere.  NO MODEL IS FITTED: the champion is never loaded and never retrained.

(2) THE ARITHMETIC CEILING, as D079, D084 and D087 all did.  How much can ONE SD of the signal move
    a points forecast, against the response sd?  Even a PERFECT, ORTHOGONAL predictor with that
    much leverage cannot beat dR2 = (move / response_sd)^2.  Precedents to compare against:
        D079 shot-mix channel      dR2 <= 0.001127
        D084 conversion channel    dR2 <= 0.000129
    The ceiling is computed on BOTH routes -- straight through ppm, and through the volume
    decomposition (shots-per-minute x points-per-shot x minutes) -- because the second is the
    channel this screen actually identified.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tv_base import ENTITY_TEAM, OUT, SEED, BaseFit, hdr, mae, sk

f = pd.read_parquet(os.path.join(OUT, "screen_frame.parquet"))
sk.assert_partition(f, verbose=True)

STRATA = {"POOLED": np.ones(len(f), bool),
          "DECISION": ((f["n_prior"] >= 8).to_numpy()
                       & (f["prior5_minutes"] >= 24).to_numpy(dtype=bool))}
BASES = {"B_SINGLE": ["refB_ppm"],
         "B_COMPLETE": ["refB_ppm", "refB_spm", "refB_pps", "refB_mpg"]}
CANDS = ["T01_c04_tiptime", "P01_c04_prevgame", "P02_c04_availweighted", "G01_noise"]
TIP_TIME = {"T01_c04_tiptime"}

# ---- STRICTLY-PRIOR minutes forecast.  .shift(1) precedes both the rolling and the expanding. ----
m_hat = f["prior5_minutes"].fillna(f["refB_mpg"])
f["_m_hat"] = m_hat
print("\n  minutes forecast m_hat: trailing-5 prior mean minutes, cold fallback = expanding prior")
print("    mean=%.4f sd=%.4f  n_from_trailing5=%d  n_from_cold_fallback=%d  n_nan=%d"
      % (float(m_hat.mean()), float(m_hat.std()), int(f["prior5_minutes"].notna().sum()),
         int(f["prior5_minutes"].isna().sum() - m_hat.isna().sum()), int(m_hat.isna().sum())))
print("    corr(m_hat, realised minutes) = %.4f   r2_of_forecast(minutes, m_hat) = %.4f"
      % (float(np.corrcoef(m_hat[m_hat.notna()], f.loc[m_hat.notna(), "minutes"])[0, 1]),
         float(sk.r2_of_forecast(f.loc[m_hat.notna(), "minutes"].to_numpy(float),
                                 m_hat[m_hat.notna()].to_numpy(float)))))

rows = []
hdr("A. POINTS PROPAGATION -- skill against the MATCHED POINT-IN-TIME REFERENCE, same rows")
for sname, smask in STRATA.items():
    for bname, basecols in BASES.items():
        for cand in CANDS:
            cols = [cand, "y_ppm", "y_pts", "_m_hat", "minutes"] + basecols
            v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
            m = smask.copy()
            for c in cols:
                m &= np.isfinite(v[c])
            if m.sum() < 400:
                continue
            y_ppm, y_pts = v["y_ppm"][m], v["y_pts"][m]
            mh, mreal = v["_m_hat"][m], v["minutes"][m]
            B = np.column_stack([v[c][m] for c in basecols])
            x = v[cand][m]
            bf = BaseFit(y_ppm, B)

            ppm_ref = bf.fitted_base()             # base-only ppm forecast, strictly prior inputs
            ppm_cand = bf.fitted_with(x)           # IN-SAMPLE screening fit -- an UPPER BOUND
            pts_ref = ppm_ref * mh
            pts_cand = ppm_cand * mh
            g = sk._group_codes(f.loc[m, ["team_id", "season"]], ["team_id", "season"])
            pfc = sk.paired_forecast_comparison(y_pts, pts_cand, pts_ref, groups=g,
                                                n_draws=2000, seed=SEED,
                                                name_a=cand, name_b="reference")
            # ORACLE-MINUTES DIAGNOSTIC -- uses the realised minutes.  NEVER a headline.
            pfc_o = sk.paired_forecast_comparison(y_pts, ppm_cand * mreal, ppm_ref * mreal,
                                                  groups=g, n_draws=2000, seed=SEED)

            beta = bf.beta(x)
            sdx = float(np.std(x))
            move_ppm_per_sd = abs(beta) * sdx                     # ppm move per 1 sd of signal
            move_pts_per_sd_meanmin = move_ppm_per_sd * float(np.mean(mh))
            delta_pts = beta * (x - x.mean()) * mh                # the actual per-row move
            move_pts_sd = float(np.std(delta_pts))
            sd_y_pts = float(np.std(y_pts))
            rows.append(dict(
                stratum=sname, base=bname, candidate=cand, tip_time=cand in TIP_TIME,
                n=int(m.sum()),
                r2_reference=float(sk.r2_of_forecast(y_pts, pts_ref)),
                r2_with_candidate=float(sk.r2_of_forecast(y_pts, pts_cand)),
                paired_dr2_points=float(pfc["dr2_a_minus_b"]),
                paired_p_cluster=float(pfc["p"]),
                paired_p_row_NAIVE=float(pfc["p_row_level_NAIVE"]),
                n_clusters=int(len(np.unique(g))),
                mae_reference_points=mae(y_pts, pts_ref),
                mae_with_candidate_points=mae(y_pts, pts_cand),
                mae_pct_reduction=float(100 * (1 - mae(y_pts, pts_cand) / mae(y_pts, pts_ref))),
                ORACLE_MINUTES_paired_dr2=float(pfc_o["dr2_a_minus_b"]),
                ORACLE_MINUTES_p_cluster=float(pfc_o["p"]),
                beta_ppm=float(beta), cand_sd=sdx, ppm_move_per_sd=float(move_ppm_per_sd),
                mean_m_hat=float(np.mean(mh)),
                points_move_per_sd=float(move_pts_per_sd_meanmin),
                points_move_sd_of_actual_shift=move_pts_sd,
                sd_y_points=sd_y_pts,
                CEILING_dr2_points_per_sd=float((move_pts_per_sd_meanmin / sd_y_pts) ** 2),
                CEILING_dr2_points_actual_shift=float((move_pts_sd / sd_y_pts) ** 2)))
            r = rows[-1]
            print("\n  %-9s %-11s %-22s n=%d" % (sname, bname, cand, r["n"]))
            print("      R2 of the points forecast   reference %+.6f -> with candidate %+.6f"
                  % (r["r2_reference"], r["r2_with_candidate"]))
            print("      PAIRED dR2 (points)         %+.6f   cluster p=%.4f  (row-NAIVE p=%.4f, "
                  "%d clusters)" % (r["paired_dr2_points"], r["paired_p_cluster"],
                                    r["paired_p_row_NAIVE"], r["n_clusters"]))
            print("      D076 CONTRAST: points MAE   %.4f -> %.4f  (%.3f%% reduction) "
                  "-- NOT differential skill"
                  % (r["mae_reference_points"], r["mae_with_candidate_points"],
                     r["mae_pct_reduction"]))
            print("      ORACLE-MINUTES DIAGNOSTIC   paired dR2 %+.6f p=%.4f  <-- reads the "
                  "response, excluded from every headline"
                  % (r["ORACLE_MINUTES_paired_dr2"], r["ORACLE_MINUTES_p_cluster"]))
            print("      ARITHMETIC CEILING: 1 sd of the signal (%.4f) moves ppm by %.6f, i.e. "
                  "%.4f POINTS at mean m_hat %.2f, against a %.4f-point response sd"
                  % (r["cand_sd"], r["ppm_move_per_sd"], r["points_move_per_sd"],
                     r["mean_m_hat"], r["sd_y_points"]))
            print("      -> EVEN AS A PERFECT ORTHOGONAL PREDICTOR:  dR2 <= %.6f   "
                  "(actual per-row shift sd route: dR2 <= %.6f)"
                  % (r["CEILING_dr2_points_per_sd"], r["CEILING_dr2_points_actual_shift"]))

pts = pd.DataFrame(rows)
pts.to_csv(os.path.join(OUT, "points_propagation.csv"), index=False)

# =====================================================================================
hdr("B. THE CEILING ON THE VOLUME ROUTE -- the channel this screen actually identified")
# =====================================================================================
# 1 sd of the signal -> delta shots-per-minute -> x minutes -> delta shots -> x points-per-shot
vol = []
for sname, smask in STRATA.items():
    for bname, basecols in BASES.items():
        for cand in ["T01_c04_tiptime", "P01_c04_prevgame"]:
            cols = [cand, "y_spm", "y_pts", "_m_hat", "y_pps"] + basecols
            bc = [c if c != "refB_ppm" or bname != "B_SINGLE" else "refB_spm" for c in basecols]
            bc = ["refB_spm"] if bname == "B_SINGLE" else basecols
            cols = [cand, "y_spm", "y_pts", "_m_hat", "y_pps"] + bc
            v = {c: pd.to_numeric(f[c], errors="coerce").to_numpy(float) for c in set(cols)}
            m = smask.copy()
            for c in cols:
                m &= np.isfinite(v[c])
            if m.sum() < 400:
                continue
            y_spm = v["y_spm"][m]
            B = np.column_stack([v[c][m] for c in bc])
            x = v[cand][m]
            bf = BaseFit(y_spm, B)
            beta = bf.beta(x)
            sdx = float(np.std(x))
            d_spm = abs(beta) * sdx
            mean_min = float(np.mean(v["_m_hat"][m]))
            mean_pps = float(np.mean(v["y_pps"][m]))
            d_shots = d_spm * mean_min
            d_pts = d_shots * mean_pps
            sd_pts = float(np.std(v["y_pts"][m]))
            vol.append(dict(stratum=sname, base=bname, candidate=cand, n=int(m.sum()),
                            beta_spm=float(beta), cand_sd=sdx,
                            d_spm_per_sd=float(d_spm), mean_m_hat=mean_min,
                            d_shots_per_sd=float(d_shots), mean_points_per_shot=mean_pps,
                            d_points_per_sd=float(d_pts), sd_y_points=sd_pts,
                            CEILING_dr2_points=float((d_pts / sd_pts) ** 2)))
            r = vol[-1]
            print("\n  %-9s %-11s %-22s n=%d" % (sname, bname, cand, r["n"]))
            print("      1 sd of signal (%.4f) x beta_spm (%+.6f) = %.6f shots/min"
                  % (r["cand_sd"], r["beta_spm"], r["d_spm_per_sd"]))
            print("      x mean m_hat %.2f min = %.4f shots   x mean pts/shot %.4f = %.4f POINTS"
                  % (r["mean_m_hat"], r["d_shots_per_sd"], r["mean_points_per_shot"],
                     r["d_points_per_sd"]))
            print("      against a %.4f-point response sd  ->  dR2 <= %.6f"
                  % (r["sd_y_points"], r["CEILING_dr2_points"]))
volm = pd.DataFrame(vol)
volm.to_csv(os.path.join(OUT, "arithmetic_ceiling.csv"), index=False)

# =====================================================================================
hdr("C. THE CEILING COMPARISON THE BRIEF ASKED FOR")
# =====================================================================================
PRECEDENT = {"D079_shot_mix_channel": 0.001127, "D084_conversion_channel": 0.000129}
best = {}
for sname in STRATA:
    for bname in BASES:
        q = pts[(pts["stratum"] == sname) & (pts["base"] == bname)
                & (pts["candidate"] == "T01_c04_tiptime")]
        if len(q):
            best["%s|%s|TIP_TIME" % (sname, bname)] = float(q["CEILING_dr2_points_per_sd"].iloc[0])
        q = pts[(pts["stratum"] == sname) & (pts["base"] == bname)
                & (pts["candidate"] == "P01_c04_prevgame")]
        if len(q):
            best["%s|%s|PRIOR_ONLY" % (sname, bname)] = float(
                q["CEILING_dr2_points_per_sd"].iloc[0])
print(json.dumps({"precedents": PRECEDENT, "this_screen_ceilings_dr2": best}, indent=2))
mx = max(best.values())
print("\n  LARGEST ceiling in this screen = %.6f" % mx)
print("  vs D079 mix ceiling 0.001127  -> %.2fx" % (mx / PRECEDENT["D079_shot_mix_channel"]))
print("  vs D084 conversion ceiling 0.000129 -> %.2fx" % (mx / PRECEDENT["D084_conversion_channel"]))

with open(os.path.join(OUT, "_s04.json"), "w", encoding="utf-8") as fh:
    json.dump({"minutes_forecast": {
                   "construction": "trailing-5 prior mean minutes (.shift(1) before .rolling(5)), "
                                   "cold fallback = expanding prior mean minutes (.shift(1) before "
                                   ".expanding()). STRICTLY PRIOR. Identical in reference and "
                                   "candidate forecasts.",
                   "mean": float(m_hat.mean()), "sd": float(m_hat.std())},
               "propagation": json.loads(pts.to_json(orient="records")),
               "volume_route_ceiling": json.loads(volm.to_json(orient="records")),
               "precedent_ceilings": PRECEDENT,
               "largest_ceiling_this_screen": mx}, fh, indent=2, default=str)
print("\n  wrote points_propagation.csv, arithmetic_ceiling.csv, _s04.json")
