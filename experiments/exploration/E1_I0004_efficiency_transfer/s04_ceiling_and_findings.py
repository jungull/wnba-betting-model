"""STEP 4b -- THE CEILING STATED THE WAY D079 STATED IT, AN IN-SAMPLE ORACLE UPPER BOUND, AND
FINDINGS.json.

Two things this adds to S03.

(1) COMPARABILITY WITH D079.  D079's shot-mix ceiling was dR2 <= 0.00113 = (0.196 / 5.82)^2, i.e.
    a 1-sd mix move of 0.196 points against a 5.82-point FIELD-GOAL-points response sd.  This
    screen's frame is a different row set with a different response sd, so the conversion channel
    is restated on the SAME denominators: FG points, and the literal 5.82 D079 used.

(2) AN IN-SAMPLE ORACLE UPPER BOUND.  The headline uses the FROZEN D074 slope, so a reader may
    reasonably ask whether the transfer merely has the wrong SCALE.  screenkit.delta_r2_plain
    REFITS, so `delta_r2_plain(y, [base], [base, adj])` is the dR2 the term would buy if its
    coefficient AND the base's coefficient were chosen with full knowledge of the answer on these
    very rows.  *** THAT IS AN ORACLE NUMBER, NOT A FORECAST, AND IT IS NOT A RESULT. ***  It is
    reported only as an upper bound: if even the oracle scaling buys nothing, no scaling does.
    No model is retrained and the champion is never modified.
"""
import json
import os

import numpy as np
import pandas as pd

import et_base as E
import screenkit as sk

pd.set_option("display.width", 260)

OUT = {}
D079_MIX_1SD_POINTS = 0.196
D079_FG_POINTS_SD = 5.82
D079_MIX_CEILING = 0.001127

f = pd.read_parquet(os.path.join(E.HERE, "efficiency_frame.parquet"))
sk.assert_partition(f, verbose=False)
gp = f["pl_games_prior"].to_numpy(float)
m5 = f["pl_min_mean5"].to_numpy(float)
M_DEC = (gp >= 8) & (m5 >= 24)
STRATA = [("DECISION-RELEVANT (>=8 prior, trail5 min >=24)", M_DEC),
          ("OFF-STRATUM (everything else)", ~M_DEC),
          ("POOLED", np.ones(len(f), bool))]

E.hdr("S04.1 -- THE CEILING ON D079's OWN DENOMINATORS (FG points, and the literal 5.82 sd)")
print("""  D079: a 1-sd move of the MIX term shifted the points forecast by 0.196 points against a
  5.82-point FG-points response sd, hence ceiling dR2 <= (0.196/5.82)^2 = 0.00113.  The same
  arithmetic for the CONVERSION channel, on this frame:""")
rows = []
print("\n  %-46s %8s %10s %10s %12s %12s %12s"
      % ("stratum", "n", "sd FGpts", "sd totpts", "1sd move", "dR2 vs FGpts", "dR2 vs 5.82"))
for lbl, m in STRATA:
    d = f.loc[m, ["y_pts", "DIAG_fg_points", "adjA_ppf", "adjB_ppf", "adjC_ppf",
                  "fga__pred_point"]].dropna()
    sd_fg = float(d["DIAG_fg_points"].std())
    sd_tot = float(d["y_pts"].std())
    r = dict(stratum=lbl, n=int(len(d)), sd_fg_points_DIAG=sd_fg, sd_total_points=sd_tot)
    for tag in ["A", "B", "C"]:
        mv = float(np.std((d["adj%s_ppf" % tag] * d["fga__pred_point"]).to_numpy(float), ddof=1))
        r["one_sd_move_points_" + tag] = mv
        r["ceiling_dR2_vs_fg_points_" + tag] = (mv / sd_fg) ** 2
        r["ceiling_dR2_vs_total_points_" + tag] = (mv / sd_tot) ** 2
        r["ceiling_dR2_vs_D079_denominator_" + tag] = (mv / D079_FG_POINTS_SD) ** 2
    rows.append(r)
    print("  %-46s %8d %10.4f %10.4f %12.4f %12.3e %12.3e"
          % (lbl, len(d), sd_fg, sd_tot, r["one_sd_move_points_A"],
             r["ceiling_dR2_vs_fg_points_A"], r["ceiling_dR2_vs_D079_denominator_A"]))
CE = pd.DataFrame(rows)
CE.to_csv(os.path.join(E.HERE, "ceiling_vs_d079.csv"), index=False)
OUT["ceiling_vs_d079"] = rows
dec = rows[0]
print("""
  HEAD TO HEAD, decision-relevant stratum, spec A vs D079's mix channel:
      channel            1 sd moves points by      ceiling dR2 (D079's 5.82 denominator)
      SHOT MIX (D079)              %.3f                      %.5f
      CONVERSION (here)            %.3f                      %.5f
  The conversion channel moves a points forecast by LESS THAN HALF as much as the mix channel D079
  already killed, and its arithmetic ceiling is about %.1fx SMALLER.  D079's ceiling argument does
  not transfer to conversion -- but a ceiling computed from scratch for conversion is TIGHTER, not
  looser.  This is a complete answer on its own and it does not depend on any p-value."""
      % (D079_MIX_1SD_POINTS, D079_MIX_CEILING, dec["one_sd_move_points_A"],
         dec["ceiling_dR2_vs_D079_denominator_A"],
         D079_MIX_CEILING / dec["ceiling_dR2_vs_D079_denominator_A"]))

E.hdr("S04.2 -- IN-SAMPLE ORACLE UPPER BOUND (delta_r2_plain REFITS -- NOT A FORECAST)")
print("""  *** EVERY NUMBER IN THIS BLOCK IS AN ORACLE. ***  It is what the term would buy if its
  coefficient were chosen knowing the answer on these very rows.  It cannot be earned in a
  forecast and is reported only as an upper bound.""")
orc = []
print("\n  %-46s %-6s %8s %13s %13s"
      % ("stratum", "target", "n", "oracle dR2", "oracle coef"))
for lbl, m in STRATA:
    for target, ycol, bcol in [("ppf", "y_ppf", "base_ppf"), ("ppm", "y_ppm", "base_ppm"),
                               ("pts", "y_pts", "pts__pred_point")]:
        acol = "adjA_ppf" if target != "pts" else "_adjpts"
        d = f.loc[m].copy()
        d["_adjpts"] = d["adjA_ppf"] * d["fga__pred_point"]
        d = d[[ycol, bcol, acol]].dropna()
        y = d[ycol].to_numpy(float)
        Xb = d[[bcol]].to_numpy(float)
        Xf = d[[bcol, acol]].to_numpy(float)
        dr2 = float(sk.delta_r2_plain(y, Xb, Xf))
        X = np.column_stack([np.ones(len(y)), Xf])
        coef = float(np.linalg.lstsq(X, y, rcond=None)[0][2])
        orc.append(dict(stratum=lbl, target=target, n=int(len(d)),
                        ORACLE_in_sample_delta_r2=dr2, ORACLE_fitted_coefficient=coef))
        print("  %-46s %-6s %8d %+13.3e %+13.4f" % (lbl, target, len(d), dr2, coef))
OUT["ORACLE_in_sample_upper_bound"] = orc
print("""
  The frozen transfer uses coefficient 1.0 on this term by construction.  Where the oracle
  coefficient is NEGATIVE the data are saying the term should be subtracted, i.e. the transferred
  D074 direction does not reproduce on the champion's own residual on those rows.""")

json.dump(OUT, open(os.path.join(E.HERE, "_s04.json"), "w"), indent=2, default=str)
print("\nDONE s04")
