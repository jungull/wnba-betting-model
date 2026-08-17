"""S05 -- two things the raw tables do not settle.

(1) PLACEBO-CALIBRATED p for every PART S channel.  The T2 placebo showed that two channels
    are NOT centred at zero under H0 (S3_ADD_VHAT mean -2.9e-4, S3_ADD_VHAT_X_LEVEL mean
    -2.2e-3).  For those the nominal sign-flip p is not the right yardstick and the observed
    dR2 must be read against the placebo's own distribution.  Computed on the GKF arm, which
    is the arm the placebo was run on.

(2) ABSTENTION, decomposed.  Dropping the rows with the largest predicted error lowers MSE.
    It also lowers the VARIANCE of the response on the rows that remain, because predicted
    error is mostly scoring level.  Reporting the MSE drop alone would be a skill claim by
    accident.  This step reports, on the SAME retained rows: SST, R2, and the same statistic
    for an abstention rule that uses the FORECAST LEVEL alone.

POST-HOC: item (2)'s R2-on-retained decomposition and the level-only abstention rule are not
in the PREREG (which scored S5 on MSE only).  They are reported because they are the check
that could have turned S5 into an inflated claim.
"""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa
from _wf import *      # noqa

ARM = "A4_CLEAN_DEC"
S = pd.read_csv(os.path.join(HERE, "POINTS_TEST.csv"))
PL = pd.read_csv(os.path.join(HERE, "_T2_PLACEBO_RAW.csv"))

# ------------------------------------------------------------------ (1) calibrated p
rows = []
obs = S[(S.scheme == "GKF") & (S.variance_model == "VSIG")]
for _, r in obs.iterrows():
    g = PL[(PL.channel == r["channel"]) & (PL.intercept_arm == str(r["intercept_arm"]))]
    if not len(g):
        continue
    d = g["delta_r2_points"].to_numpy()
    rows.append(dict(arm=ARM, scheme="GKF", variance_model="VSIG", channel=r["channel"],
                     intercept_arm=r["intercept_arm"],
                     observed_delta_r2=r["delta_r2_points"],
                     nominal_signflip_p=r["signflip_p_player_season"],
                     placebo_n=len(d), placebo_mean=float(d.mean()),
                     placebo_sd=float(d.std(ddof=1)),
                     placebo_q95=float(np.percentile(d, 95)),
                     placebo_calibrated_p_one_sided=float((np.sum(d >= r["delta_r2_points"]) + 1)
                                                          / (len(d) + 1)),
                     z_vs_placebo=float((r["delta_r2_points"] - d.mean())
                                        / d.std(ddof=1)) if d.std(ddof=1) > 0 else np.nan,
                     placebo_centred=bool(abs(d.mean()) < 2e-4)))
CP = pd.DataFrame(rows)
CP.to_csv(os.path.join(HERE, "_PLACEBO_CALIBRATED.csv"), index=False)
pd.set_option("display.width", 250)
print("=== placebo-calibrated p (GKF, VSIG) ===")
print(CP[["channel", "intercept_arm", "observed_delta_r2", "nominal_signflip_p",
          "placebo_mean", "placebo_sd", "placebo_calibrated_p_one_sided", "z_vs_placebo",
          "placebo_centred"]].round(6).to_string(index=False))

# ------------------------------------------------------------- (2) abstention decomposed
out = []
for scheme in ("WF", "GKF"):
    z = np.load(os.path.join(RAW, "points_test_%s_VSIG.npz" % scheme), allow_pickle=True)
    scored = z["scored"]
    y = z["y_pts"][scored]
    ref = z["pred__REF"][scored]
    v = z["pred__VHAT"][scored]
    lev = X[np.where(ARM_MASKS[ARM])[0], NAME_IX["pts__pred_point"]]  # arm order != scored order
    # rebuild the level column in the same row order as the npz
    mask = ARM_MASKS[ARM]
    idx = np.where(mask)[0]
    sub0 = f.iloc[idx]
    order = np.lexsort((sub0["row_uid"].to_numpy(), sub0["gdate"].to_numpy()))
    lev = X[idx[order], NAME_IX["pts__pred_point"]][scored]
    e = y - ref
    for rule, crit in (("VSIG_predicted_error", v), ("FORECAST_LEVEL_ALONE", lev)):
        for q in (10, 20, 30):
            thr = np.percentile(crit, 100 - q)
            keep = crit <= thr
            yy, ee = y[keep], e[keep]
            out.append(dict(
                arm=ARM, scheme=scheme, rule=rule, q_dropped_pct=q,
                n_scored=int(len(y)), n_retained=int(keep.sum()),
                mse_all=float((e ** 2).mean()), mse_retained=float((ee ** 2).mean()),
                mse_reduction=1.0 - float((ee ** 2).mean()) / float((e ** 2).mean()),
                sd_y_all=float(y.std(ddof=1)), sd_y_retained=float(yy.std(ddof=1)),
                variance_reduction_of_response=1.0 - float(yy.var(ddof=1)) / float(y.var(ddof=1)),
                r2_all=1.0 - float((e ** 2).sum()) / float(((y - y.mean()) ** 2).sum()),
                r2_retained=1.0 - float((ee ** 2).sum())
                / float(((yy - yy.mean()) ** 2).sum()),
                mean_y_all=float(y.mean()), mean_y_retained=float(yy.mean())))
AB = pd.DataFrame(out)
AB["r2_change_on_retained"] = AB["r2_retained"] - AB["r2_all"]
AB.to_csv(os.path.join(HERE, "_ABSTENTION_DECOMPOSED.csv"), index=False)
print("\n=== abstention decomposed (POST-HOC) ===")
print(AB[["scheme", "rule", "q_dropped_pct", "n_retained", "mse_reduction",
          "variance_reduction_of_response", "r2_all", "r2_retained",
          "r2_change_on_retained", "mean_y_retained"]].round(4).to_string(index=False))
print("\nDONE s05")
