"""S08 -- VERIFY.  Every headline claim in the four markdown deliverables, re-checked against
the CSVs by assertion.  If this exits non-zero, a document says something the data does not."""
import json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa

ok = []


def check(name, cond, detail=""):
    ok.append((name, bool(cond), detail))
    print("%-62s %s  %s" % (name, "PASS" if cond else "**FAIL**", detail))


s00 = json.load(open(os.path.join(HERE, "scripts", "_s00.json")))
s01 = json.load(open(os.path.join(HERE, "scripts", "_s01.json")))
s02 = json.load(open(os.path.join(HERE, "scripts", "_s02.json")))
s06 = json.load(open(os.path.join(HERE, "scripts", "_s06.json")))
RP = pd.read_csv(os.path.join(HERE, "REPRODUCTION.csv"))
VP = pd.read_csv(os.path.join(HERE, "VOLUME_PROXY.csv"))
CAL = pd.read_csv(os.path.join(HERE, "CALIBRATION.csv"))
PT = pd.read_csv(os.path.join(HERE, "POINTS_TEST.csv"))
AB = pd.read_csv(os.path.join(HERE, "ABSTENTION.csv"))
ABD = pd.read_csv(os.path.join(HERE, "_ABSTENTION_DECOMPOSED.csv"))
T2 = pd.read_csv(os.path.join(HERE, "_T2_PLACEBO.csv"))
TI = pd.read_csv(os.path.join(HERE, "TYPEI_CENTRED.csv"))
SUB = pd.read_csv(os.path.join(HERE, "_PRED_CV_SUBSTITUTION.csv"))
MEC = pd.read_csv(os.path.join(HERE, "_PRED_CV_MECHANISM.csv"))
DEG = pd.read_csv(os.path.join(HERE, "_PRED_COLUMN_DEGENERACY.csv"))
P16 = s00["published_16"]

# ---- REPRODUCTION.md
check("R-A1 max relative |dt| < 1e-9", s00["R_A1_max_rel_dt"] < 1e-9,
      "%.2e" % s00["R_A1_max_rel_dt"])
check("R-A2 max |ddR2| < 1e-12", s00["R_A2_max_abs_ddr2"] < 1e-12,
      "%.2e" % s00["R_A2_max_abs_ddr2"])
check("R-A3 max |dt| vs E1_I0050 < 1e-9", s00["R_A3_max_abs_dt"] < 1e-9,
      "%.2e" % s00["R_A3_max_abs_dt"])
check("the sixteen reproduce, symdiff 0 at every seed",
      all(len(set(v) ^ set(P16)) == 0 for v in s01["sets"].values()),
      str({k: len(set(v) ^ set(P16)) for k, v in s01["sets"].items()}))
check("A1_FULL count is 36", len(s01["a1_full"]) == 36, str(len(s01["a1_full"])))
check("bar q95 A4 within 0.30 of published 5.3231",
      all(abs(b["bar_familywise_q95"] - 5.323081389242404) < 0.30
          for b in s01["bar_anatomy"] if b["arm"] == "A4_CLEAN_DEC"),
      str([round(b["bar_familywise_q95"], 4) for b in s01["bar_anatomy"]]))
check("published E0_I0014 bar is supplied by ONE cell in 1000/1000",
      s00["published_bar_top_cell_share"] == 1.0 and s00["published_bar_n_distinct_suppliers"] == 1,
      s00["published_bar_top_cell"])
check("repaired bar has >=250 distinct suppliers",
      min(b["n_distinct_suppliers"] for b in s01["bar_anatomy"]) >= 250,
      str(min(b["n_distinct_suppliers"] for b in s01["bar_anatomy"])))
check("T3 no cell blind on either arm (|null mean signed t| <= 0.20)",
      RP["null_mean_signed_t"].abs().max() <= TOL_BLIND,
      "max %.4f" % RP["null_mean_signed_t"].abs().max())
check("11 of the 16 have a minutes response, 3 points-error, 2 fga",
      sum(c.split("|")[1].startswith("minutes") for c in P16) == 11
      and sum(c.split("|")[1].startswith("pts") for c in P16) == 3
      and sum(c.split("|")[1].startswith("fga") for c in P16) == 2)

# ---- T1
h0 = TI[TI.is_H0_generator]
check("T1 every H0 pair centred, |mean signed t| < 0.15",
      bool(h0["centred_ok"].all()), "max %.4f" % h0["mean_signed_t_obs"].abs().max())
check("T1 composed-2 Type-I: none over 0.075",
      int((h0["typeI_COMPOSED2"] > TOL_TYPEI).sum()) == 0,
      "median %.4f max %.4f" % (h0["typeI_COMPOSED2"].median(), h0["typeI_COMPOSED2"].max()))
bb = TI[~TI.is_H0_generator]
check("T1 BLOCKBOOT (defective) fails centring on some cells",
      not bool(bb["centred_ok"].all()),
      "%d of %d not centred, max %.4f" % (int((~bb["centred_ok"]).sum()), len(bb),
                                          bb["mean_signed_t_obs"].abs().max()))

# ---- VOLUME_PROXY.md
n16 = {b: len(s02["survivors_within_16"][b]) for b in ("B0", "B1", "B2", "B3", "B4")}
check("volume base survivors: B0=16 B1=6 B2=5 B3=4",
      n16["B0"] == 16 and n16["B1"] == 6 and n16["B2"] == 5 and n16["B3"] == 4, str(n16))
med3 = float(VP[(VP.base == "B3") & VP.cell.isin(P16)]["retained_share_vs_B0"].median())
check("median retained share under B3 approx 0.238", abs(med3 - 0.238) < 0.005, "%.4f" % med3)
check("12 of the 16 are volume proxies (lose family-wise under B3)", 16 - n16["B3"] == 12)
check("all four B3 survivors have a minutes response",
      all(c.split("|")[1].startswith("minutes") for c in s02["survivors_within_16"]["B3"]),
      str(s02["survivors_within_16"]["B3"]))
check("no points-error cell survives B3",
      not any(c.split("|")[1].startswith("pts") for c in s02["survivors_within_16"]["B3"]))
r_cv = float(VP[(VP.base == "B3") & (VP.cell == "pts__pred_cv|pts_absres")]
             ["retained_share_vs_B0"].iloc[0])
check("pts__pred_cv|pts_absres retains <1% under B3", r_cv < 0.01, "%.4f" % r_cv)
r_sd = float(VP[(VP.base == "B3") & (VP.cell == "pl_pts_sd5|pts_absres")]
             ["retained_share_vs_B0"].iloc[0])
check("pl_pts_sd5|pts_absres retains ~5.6% under B3", abs(r_sd - 0.056) < 0.005, "%.4f" % r_sd)

# ---- mechanism
d = DEG[(DEG.arm == "A4_CLEAN_DEC") & (DEG.column.str.endswith("pred_sd"))]
check("all three <target>__pred_sd have 1 distinct value per season on A4",
      all(json.loads(x) == {"2023": 1, "2024": 1} for x in d["n_distinct_by_season"]))
check("within-season corr(pred_cv, 1/pred_point) == 1.000 on both arms",
      float(MEC["within_season_corr_min"].min()) > 0.99999,
      "%.6f" % MEC["within_season_corr_min"].min())
a = SUB[SUB.carrier == "pts__pred_cv"].reset_index(drop=True)
b = SUB[SUB.carrier == "ONE_OVER_pts__pred_point"].reset_index(drop=True)
check("substituting 1/pred_point reproduces t and dR2 exactly",
      float((a.signed_t - b.signed_t).abs().max()) < 1e-10
      and float((a.dr2 - b.dr2).abs().max()) < 1e-14,
      "max |dt| %.2e" % (a.signed_t - b.signed_t).abs().max())

# ---- SKILL_OR_VARIANCE.md
ch = PT[PT.channel != "RAW_INCUMBENT"]
check("96 channel arms tested", len(ch) == 96, str(len(ch)))
check("NO channel meets the preregistered decision rule",
      int(ch["improves_points_PREREG_RULE"].sum()) == 0)
bestv = float(ch["delta_r2_points"].max())
bestr = ch.loc[ch["delta_r2_points"].idxmax()]
check("best dR2 on points is +0.00047 and below the 0.00072 points floor",
      abs(bestv - 0.000470) < 5e-6 and bestv < FLOOR_POINTS_K1,
      "%.6f  %s/%s/%s  p=%.3f" % (bestv, bestr["scheme"], bestr["variance_model"],
                                  bestr["channel"], bestr["signflip_p_player_season"]))
sig = ch[ch["signflip_p_player_season"] < 0.05]
check("the ONLY channels significant at 0.05 are HARMFUL (negative dR2)",
      len(sig) == 2 and bool((sig["delta_r2_points"] < 0).all()),
      "%d of 96, both %s / S2_SHRINK, dR2 %.6f, p %.4f"
      % (len(sig), sig["variance_model"].iloc[0], sig["delta_r2_points"].iloc[0],
         sig["signflip_p_player_season"].iloc[0]))
r2ref = float(PT[(PT.scheme == "WF") & (PT.variance_model == "VSIG")]["r2_reference"].iloc[0])
check("tuned reference OOF R2 on points approx 0.3183", abs(r2ref - 0.3183) < 5e-4, "%.4f" % r2ref)
raw = float(PT[(PT.scheme == "WF") & (PT.variance_model == "VSIG")
               & (PT.channel == "RAW_INCUMBENT")]["delta_r2_points"].iloc[0])
check("tuned reference beats the raw shipped forecast", raw < 0, "raw - ref = %.5f" % raw)
t2 = T2[T2.channel != "RAW_INCUMBENT"]
check("T2: S3 channels are NOT centred and the others are",
      set(t2[~t2["centred_ok_abs_mean_lt_2e-4"]]["channel"]) == {"S3_ADD_VHAT",
                                                                 "S3_ADD_VHAT_X_LEVEL"},
      str(sorted(set(t2[~t2["centred_ok_abs_mean_lt_2e-4"]]["channel"]))))
check("T2: S3_ADD_VHAT Type-I is about 3x nominal",
      float(t2[t2.channel == "S3_ADD_VHAT"]["typeI_at_0p05"].max()) > 0.12,
      "%.3f" % t2[t2.channel == "S3_ADD_VHAT"]["typeI_at_0p05"].max())

# ---- calibration
w = CAL[CAL.scheme == "WF"].set_index(["target", "model"])
check("VSIG pts decile ratio 1.63, CI clear of 1",
      abs(w.loc[("pts", "VSIG"), "top_over_bottom_decile_ratio"] - 1.629) < 0.01
      and w.loc[("pts", "VSIG"), "ratio_boot_lo"] > 1.0,
      "%.3f [%.3f, %.3f]" % (w.loc[("pts", "VSIG"), "top_over_bottom_decile_ratio"],
                             w.loc[("pts", "VSIG"), "ratio_boot_lo"],
                             w.loc[("pts", "VSIG"), "ratio_boot_hi"]))
check("VSIG minutes decile ratio > 1.6 (P-C1)",
      w.loc[("minutes", "VSIG"), "top_over_bottom_decile_ratio"] > 1.6,
      "%.3f" % w.loc[("minutes", "VSIG"), "top_over_bottom_decile_ratio"])
check("VSIG beats V0 on OOF R2 for all three targets (P-C2)",
      all(w.loc[(t, "VSIG"), "oof_r2_of_vhat_on_absres"]
          > w.loc[(t, "V0"), "oof_r2_of_vhat_on_absres"] for t in ("pts", "minutes", "fga")))
check("VSD (incumbent) has NEGATIVE OOF R2 on all three targets",
      all(w.loc[(t, "VSD"), "oof_r2_of_vhat_on_absres"] < 0
          for t in ("pts", "minutes", "fga")))
check("VLEV (level alone) matches VSIG on pts and beats it on fga",
      abs(w.loc[("pts", "VLEV"), "top_over_bottom_decile_ratio"]
          - w.loc[("pts", "VSIG"), "top_over_bottom_decile_ratio"]) < 0.05
      and w.loc[("fga", "VLEV"), "top_over_bottom_decile_ratio"]
      > w.loc[("fga", "VSIG"), "top_over_bottom_decile_ratio"])
check("VSIG beats VLEV clearly ONLY on minutes",
      w.loc[("minutes", "VSIG"), "top_over_bottom_decile_ratio"]
      - w.loc[("minutes", "VLEV"), "top_over_bottom_decile_ratio"] > 0.4)

# ---- abstention
a30 = AB[(AB.scheme == "WF") & (AB.variance_model == "VSIG") & (AB.q_dropped_pct == 30)].iloc[0]
check("P-S3 FAILED: abstention MSE reduction at q=30 is below 15%",
      a30["mse_reduction_vs_all"] < 0.15, "%.4f" % a30["mse_reduction_vs_all"])
d30 = ABD[(ABD.scheme == "WF") & (ABD.q_dropped_pct == 30)].set_index("rule")
check("abstention LOWERS R2 on the retained rows",
      d30.loc["VSIG_predicted_error", "r2_change_on_retained"] < 0,
      "%.4f" % d30.loc["VSIG_predicted_error", "r2_change_on_retained"])
check("abstaining on FORECAST LEVEL ALONE does at least as well",
      d30.loc["FORECAST_LEVEL_ALONE", "mse_reduction"]
      >= d30.loc["VSIG_predicted_error", "mse_reduction"],
      "%.4f vs %.4f" % (d30.loc["FORECAST_LEVEL_ALONE", "mse_reduction"],
                        d30.loc["VSIG_predicted_error", "mse_reduction"]))

nf = [n for n, c, _ in ok if not c]
print("\n%d checks, %d failed" % (len(ok), len(nf)))
if nf:
    print("FAILED:", nf)
    sys.exit(1)
print("ALL VERIFICATION CHECKS PASS")
