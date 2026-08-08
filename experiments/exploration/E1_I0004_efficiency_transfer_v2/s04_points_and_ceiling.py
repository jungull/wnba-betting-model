"""STEP 4 -- PROPAGATE TO POINTS, AND STATE THE ARITHMETIC CEILING THE WAY D079 DID.

POINTS PROPAGATION.  pts_cand = ppm_cand x the champion's OWN minutes forecast, which is
identically pts_pred + fga_pred * S (verified to 3.6e-15 in s02).  Scored against y_pts with
paired_forecast_comparison at the same cluster levels, and as SKILL against D081's own frozen
point-in-time reference ref_pts.

THE ARITHMETIC CEILING.  D079 killed the SHOT-MIX channel not on significance but on arithmetic:
1 sd of the mix signal moved the points forecast by 0.196 points against a 5.82-point response sd,
so even a PERFECT, ORTHOGONAL mix term could buy at most dR2 = 0.00113.  The same calculation is
made here for the CONVERSION channel.  Two forms, both reported:

  CEILING-A  "perfect orthogonal predictor" (D079's exact form, pure arithmetic, no fitting):
             delta = sd( the points the signal moves the forecast by ) = sd(fga_pred * S)
             ceiling dR2 <= (delta / sd(y))^2

  CEILING-B  ORACLE BEST SCALING.  *** THIS USES THE REALISED RESPONSE AND IS LOUDLY LABELLED. ***
             The largest dR2 obtainable by adding c*S to the champion forecast when c is chosen
             WITH HINDSIGHT on these very rows: dR2_oracle = corr(y - pred, S)^2 * var(y - pred)
             / var(y).  It is an UPPER BOUND and a DIAGNOSTIC, never a screened result and never
             a forecast.  It exists to separate "the transfer coefficient is mis-scaled" from
             "there is nothing here at any scale".  Constraint 9 is not violated: no model is
             fitted or modified; a bound is computed and reported as a bound.

Both ceilings are reported against the response sd of THIS frame (total points) and, for direct
comparability with D079, against D079's 5.82-point FG-points response sd.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import etv2_base as E  # noqa: E402
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 60)
OUT = {}
N_DRAWS = 5000
D079_FG_POINTS_SD = 5.823572695034913     # E1_I0004_shot_selection, for comparability only

f = pd.read_parquet(os.path.join(E.HERE, "eff_frame_v2.parquet"))
sk.assert_partition(f, verbose=False)

SPECS = ["SPEC_RA", "SPEC_ALL5_GLOBAL", "SPEC_ALL5_PERZONE", "SPEC_RA_UNCENTRED"]
STRATA = [("all", None), ("on_stratum", True), ("off_stratum", False)]
CLUSTERS = [("opponent_team_season", "opp_team_season"),
            ("opponent_team_season_game", "opp_team_season_game"),
            ("game", "gid"), ("player_season", "player_season")]

E.hdr("S04.1 -- POINTS: candidate = champion points + fga_forecast * S  (== ppm_cand x minutes)")
rows = []
for sp in SPECS:
    ccol = "pts_cand_" + sp
    for stag, sval in STRATA:
        m = np.isfinite(f["y_pts"]) & np.isfinite(f["pts__pred_point"]) & np.isfinite(f[ccol]) \
            & np.isfinite(f["ref_pts"])
        if sval is not None:
            m = m & (f["stratum"] == sval)
        sub = f[m]
        y = sub["y_pts"].to_numpy(float)
        b = sub["pts__pred_point"].to_numpy(float)
        c = sub[ccol].to_numpy(float)
        rf = sub["ref_pts"].to_numpy(float)
        h = sk.paired_forecast_comparison(y, c, b, sub["opp_team_season"].to_numpy(),
                                          n_draws=N_DRAWS, seed=E.SEED)
        rec = dict(spec=sp, centred=("UNCENTRED" not in sp), stratum=stag, n=int(h["n"]),
                   r2_champion=float(h["r2_b"]), r2_candidate=float(h["r2_a"]),
                   dR2_cand_minus_champ=float(h["dr2_a_minus_b"]),
                   p_cluster_opp_team_season=float(h["p"]),
                   p_row_level_NAIVE=float(h["p_row_level_NAIVE"]),
                   inflation=float(h["inflation"]),
                   points_skill_champion=E.skill(y, b, rf)[0],
                   points_skill_candidate=E.skill(y, c, rf)[0],
                   mae_champion=E.mae(y, b), mae_candidate=E.mae(y, c), mae_reference=E.mae(y, rf))
        rec["d_points_skill"] = rec["points_skill_candidate"] - rec["points_skill_champion"]
        for cname, cc in CLUSTERS:
            hh = sk.paired_forecast_comparison(y, c, b, sub[cc].to_numpy(),
                                               n_draws=N_DRAWS, seed=E.SEED)
            rec["p_" + cname] = float(hh["p"])
        rows.append(rec)
P = pd.DataFrame(rows)
P.to_csv(os.path.join(E.HERE, "points_contrast.csv"), index=False)
print(P[["spec", "centred", "stratum", "n", "r2_champion", "r2_candidate",
         "dR2_cand_minus_champ", "p_cluster_opp_team_season", "p_row_level_NAIVE",
         "points_skill_champion", "points_skill_candidate", "d_points_skill"]].to_string(index=False))
OUT["points_contrast"] = P.to_dict(orient="records")

E.hdr("S04.2 -- THE ARITHMETIC CEILING (D079's form) FOR THE CONVERSION CHANNEL")
cr = []
for sp in ["SPEC_RA", "SPEC_ALL5_GLOBAL", "SPEC_ALL5_PERZONE"]:
    for stag, sval in STRATA:
        m = np.isfinite(f["y_pts"]) & np.isfinite(f["pts__pred_point"]) & np.isfinite(f["S_" + sp])
        if sval is not None:
            m = m & (f["stratum"] == sval)
        sub = f[m]
        y = sub["y_pts"].to_numpy(float)
        pred = sub["pts__pred_point"].to_numpy(float)
        move = (sub["fga__pred_point"] * sub["S_" + sp]).to_numpy(float)   # points moved
        sdy = float(np.std(y, ddof=1))
        delta = float(np.std(move, ddof=1))
        resid = y - pred
        cc = float(np.corrcoef(resid, move)[0, 1])
        ceil_a = (delta / sdy) ** 2
        ceil_a_d079 = (delta / D079_FG_POINTS_SD) ** 2
        oracle = cc ** 2 * float(np.var(resid, ddof=1)) / float(np.var(y, ddof=1))
        cr.append(dict(spec=sp, stratum=stag, n=int(len(sub)),
                       sd_y_points_this_frame=sdy,
                       points_moved_by_1sd_of_signal=delta,
                       CEILING_A_perfect_orthogonal_dR2=ceil_a,
                       CEILING_A_vs_D079_5p82_sd=ceil_a_d079,
                       DIAGNOSTIC_corr_resid_vs_move=cc,
                       DIAGNOSTIC_ORACLE_best_scaling_dR2=oracle,
                       D079_mix_ceiling_for_comparison=0.001127))
C = pd.DataFrame(cr)
C.to_csv(os.path.join(E.HERE, "arithmetic_ceiling.csv"), index=False)
print(C.to_string(index=False))
print("""
  HOW TO READ THIS.  `points_moved_by_1sd_of_signal` is how many POINTS one standard deviation of
  the CENTRED conversion signal moves the champion's points forecast.  CEILING-A is the dR2 that
  movement could buy IF the signal were a perfect, orthogonal predictor -- pure arithmetic, no
  fitting, exactly D079's calculation.  CEILING-B (the ORACLE column) is the dR2 obtainable if the
  transfer coefficient were rescaled WITH HINDSIGHT on these very rows; it USES THE REALISED
  RESPONSE, is an UPPER BOUND, and is never a screened result.  D079's shot-mix ceiling of
  0.001127 is printed beside it.""")
OUT["arithmetic_ceiling"] = cr

E.hdr("S04.3 -- THE SAME CEILING ON THE EFFICIENCY RESPONSE ITSELF (points per minute)")
er = []
for sp in ["SPEC_RA", "SPEC_ALL5_GLOBAL", "SPEC_ALL5_PERZONE"]:
    for stag, sval in STRATA:
        m = np.isfinite(f["r_ppm"]) & np.isfinite(f["mdl_ppm"]) & np.isfinite(f["S_" + sp])
        if sval is not None:
            m = m & (f["stratum"] == sval)
        sub = f[m]
        y = sub["r_ppm"].to_numpy(float)
        pred = sub["mdl_ppm"].to_numpy(float)
        move = (sub["S_" + sp] * sub["mdl_fpm"]).to_numpy(float)
        sdy = float(np.std(y, ddof=1))
        delta = float(np.std(move, ddof=1))
        resid = y - pred
        cc = float(np.corrcoef(resid, move)[0, 1])
        er.append(dict(spec=sp, stratum=stag, n=int(len(sub)), sd_y_ppm=sdy,
                       ppm_moved_by_1sd_of_signal=delta,
                       CEILING_A_perfect_orthogonal_dR2=(delta / sdy) ** 2,
                       DIAGNOSTIC_corr_resid_vs_move=cc,
                       DIAGNOSTIC_ORACLE_best_scaling_dR2=cc ** 2 * float(np.var(resid, ddof=1))
                       / float(np.var(y, ddof=1))))
Ce = pd.DataFrame(er)
Ce.to_csv(os.path.join(E.HERE, "efficiency_ceiling.csv"), index=False)
print(Ce.to_string(index=False))
OUT["efficiency_ceiling"] = er

E.hdr("S04.4 -- WHAT WOULD THE SIGNAL HAVE TO BE WORTH TO MATTER?")
on = C[(C["spec"] == "SPEC_RA") & (C["stratum"] == "on_stratum")].iloc[0]
gap = 0.0035882639143178796      # D081: the champion's points skill deficit on this stratum
print("""  On the decision-relevant stratum the champion's points skill is -0.36%% against the
  point-in-time reference (D081, reproduced exactly in s01).  One sd of the centred RA conversion
  signal moves the points forecast by %.4f points against a %.4f-point response sd.  Even as a
  PERFECT ORTHOGONAL predictor that is dR2 <= %.6f -- %.1fx D079's already-fatal shot-mix ceiling
  of 0.001127 in the SAME units.  Rescaled with hindsight it is dR2 <= %.6f.  Measured as built,
  it is dR2 = %+.6f: NEGATIVE.""" % (
    on["points_moved_by_1sd_of_signal"], on["sd_y_points_this_frame"],
    on["CEILING_A_perfect_orthogonal_dR2"],
    on["CEILING_A_perfect_orthogonal_dR2"] / 0.001127,
    on["DIAGNOSTIC_ORACLE_best_scaling_dR2"],
    float(P[(P["spec"] == "SPEC_RA") & (P["stratum"] == "on_stratum")]
          ["dR2_cand_minus_champ"].iloc[0])))
OUT["d081_stratum_points_skill_deficit"] = gap

json.dump(OUT, open(os.path.join(E.HERE, "_s04.json"), "w"), indent=2, default=str)
print("DONE s04")
