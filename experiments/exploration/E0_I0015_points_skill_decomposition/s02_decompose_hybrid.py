"""STEP 2 -- DECOMPOSE THE SKILL LOSS.   STEP 3 -- THE HYBRID 2x2.   STEP 4 -- INTRINSIC CEILING.

Every skill number is 1 - MAE_model/MAE_ref with the reference facing THE SAME ROWS.  Nothing is
refitted; the model's rate forecasts are ratios of its own already-emitted point forecasts.
"""
import json
import os

import numpy as np
import pandas as pd

import psd_base as B
import screenkit as sk

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)

OUT = {}
f = pd.read_parquet(os.path.join(B.OUT, "decomp_frame.parquet"))
sk.assert_partition(f, verbose=False)
print("  frame %s  seasons=%s" % (f.shape, sorted(f["season"].unique())))
blocks = B.block_codes_player_season(f)

B.hdr("R2 CONVENTION -- BOTH SEMANTICS REPORTED (see NOTES.md section 7, kit feedback)")
r2tab = []
for t in ["pts", "minutes", "fga"]:
    y = f["y_" + t].to_numpy(float)
    p = f["%s__pred_point" % t].to_numpy(float)
    a = B.r2_forecast(y, p)
    b = sk.r2_plain(y, p[:, None])
    print("  %-8s R2 of the forecast AS-IS (1-SSE/SST) = %.4f   |   screenkit.r2_plain (OLS REFIT "
          "of y on the forecast) = %.4f   | D076 published %.4f" %
          (t, a, b, {"pts": 0.4694, "minutes": 0.6194, "fga": 0.5893}[t]))
    r2tab.append(dict(target=t, r2_forecast_as_is=a, r2_screenkit_r2_plain_refit=b,
                      d076_published=  {"pts": 0.4694, "minutes": 0.6194, "fga": 0.5893}[t]))
OUT["r2_convention"] = {
    "declared": "D069 plain unweighted OLS R2, SST about the UNWEIGHTED mean.",
    "two_semantics_warning": "screenkit.r2_plain(y, X) FITS an OLS of y on X. Passing a forecast "
                             "as X reports the R2 of its best linear rescaling, not the forecast's "
                             "own R2. D076's rh_base.r2_plain(y, yhat) is 1-SSE/SST with SSE about "
                             "the supplied yhat. SAME NAME, DIFFERENT SEMANTICS.",
    "table": r2tab}

# =====================================================================================
B.hdr("STEP 2 -- PER-COMPONENT SKILL, EACH AGAINST ITS OWN MATCHED PRIOR-MEAN REFERENCE")
# =====================================================================================
COMPONENTS = [
    ("minutes",       "LEVEL", "y_minutes", "minutes__pred_point", ["ref_minutes"]),
    ("fga",           "LEVEL", "y_fga",     "fga__pred_point",     ["ref_fga"]),
    ("pts",           "LEVEL", "y_pts",     "pts__pred_point",     ["ref_pts"]),
    ("fga_per_min",   "RATE",  "r_fpm",     "mdl_fpm",             ["refA_fpm", "refB_fpm"]),
    ("pts_per_fga",   "RATE",  "r_ppf",     "mdl_ppf",             ["refA_ppf", "refB_ppf"]),
    ("pts_per_min",   "RATE",  "r_ppm",     "mdl_ppm",             ["refA_ppm", "refB_ppm"]),
]
comp_rows = []
print("\n  %-14s %-6s %7s %11s %11s %11s %9s %11s" %
      ("component", "kind", "n", "model MAE", "ref MAE", "skill", "p(block)", "reference"))
for name, kind, ycol, mcol, refcols in COMPONENTS:
    for refcol in refcols:
        y = f[ycol].to_numpy(float)
        m = f[mcol].to_numpy(float)
        r = f[refcol].to_numpy(float)
        ok = np.isfinite(y) & np.isfinite(m) & np.isfinite(r)
        s, mm, mr = B.skill(y[ok], m[ok], r[ok])
        d = np.abs(y[ok] - m[ok]) - np.abs(y[ok] - r[ok])       # model - reference, paired
        bt = B.block_signflip_test(d, blocks[ok], n_draws=2000)
        tag = "A mean-of-prior-ratios" if refcol.startswith("refA") else (
              "B ratio-of-prior-sums" if refcol.startswith("refB") else "D076 prior mean")
        print("  %-14s %-6s %7d %11.5f %11.5f %+11.5f %9.4f  %s"
              % (name, kind, int(ok.sum()), mm, mr, s, bt["p_two_sided_blockflip"], tag))
        comp_rows.append(dict(component=name, kind=kind, reference=refcol, reference_kind=tag,
                              n=int(ok.sum()), model_mae=mm, ref_mae=mr, skill=s,
                              r2_forecast_as_is=B.r2_forecast(y[ok], m[ok]),
                              paired_mean_abs_err_diff_model_minus_ref=bt["mean_diff"],
                              p_two_sided_block_signflip=bt["p_two_sided_blockflip"],
                              null_sd=bt["null_sd"], n_player_season_blocks=bt["n_blocks"]))
pd.DataFrame(comp_rows).to_csv(os.path.join(B.OUT, "component_skill.csv"), index=False)
OUT["component_skill"] = comp_rows

# per-season stability of the rate components
srows = []
for name, kind, ycol, mcol, refcols in COMPONENTS:
    for refcol in refcols[:1]:
        for s_ in B.SCREEN_SEASONS:
            g = f[f["season"] == s_]
            y, m, r = (g[ycol].to_numpy(float), g[mcol].to_numpy(float), g[refcol].to_numpy(float))
            ok = np.isfinite(y) & np.isfinite(m) & np.isfinite(r)
            sk_, mm, mr = B.skill(y[ok], m[ok], r[ok])
            srows.append(dict(component=name, season=int(s_), reference=refcol, n=int(ok.sum()),
                              skill=sk_))
pd.DataFrame(srows).to_csv(os.path.join(B.OUT, "component_skill_per_season.csv"), index=False)
OUT["component_skill_per_season"] = srows
print("\n  per-season skill (primary reference only):")
print(pd.DataFrame(srows).pivot(index="component", columns="season", values="skill").to_string(
    float_format=lambda v: "%+.4f" % v))

# =====================================================================================
B.hdr("STEP 3 -- THE HYBRID 2x2, SCORED IN POINTS.  Skill denominator = D076's ref_pts.")
# =====================================================================================
y = f["y_pts"].to_numpy(float)
ref_pts = f["ref_pts"].to_numpy(float)
mmin = f["minutes__pred_point"].to_numpy(float)
rmin = f["ref_minutes"].to_numpy(float)

HYB = {}
for rv, lbl in [("A", "mean-of-prior-ratios"), ("B", "ratio-of-prior-sums")]:
    mrate = f["mdl_ppm"].to_numpy(float)
    rrate = f["ref%s_ppm" % rv].to_numpy(float)
    HYB[rv] = {
        "H1_model_min_x_model_rate": mmin * mrate,
        "H2_model_min_x_naive_rate": mmin * rrate,
        "H3_naive_min_x_model_rate": rmin * mrate,
        "H4_naive_min_x_naive_rate": rmin * rrate,
    }

print("\n  identity check: H1 == pts__pred_point exactly?  max|H1 - pred| = %.3e"
      % float(np.max(np.abs(HYB["A"]["H1_model_min_x_model_rate"] - f["pts__pred_point"]))))

hyb_rows = []
for rv, lbl in [("A", "mean-of-prior-ratios"), ("B", "ratio-of-prior-sums")]:
    print("\n  ---- naive rate variant %s (%s) ----" % (rv, lbl))
    print("  %-32s %11s %11s %11s %9s" % ("cell", "points MAE", "skill vs ref", "RMSE", "R2 as-is"))
    base = {"H1_model_min_x_model_rate": ("model", "model"),
            "H2_model_min_x_naive_rate": ("model", "naive"),
            "H3_naive_min_x_model_rate": ("naive", "model"),
            "H4_naive_min_x_naive_rate": ("naive", "naive")}
    for k, (mfac, rfac) in base.items():
        yh = HYB[rv][k]
        ok = np.isfinite(yh) & np.isfinite(y) & np.isfinite(ref_pts)
        s, mm, mr = B.skill(y[ok], yh[ok], ref_pts[ok])
        rmse = float(np.sqrt(np.mean((y[ok] - yh[ok]) ** 2)))
        print("  %-32s %11.4f %+11.5f %11.4f %9.4f" % (k, mm, s, rmse, B.r2_forecast(y[ok], yh[ok])))
        hyb_rows.append(dict(naive_rate_variant=rv, naive_rate_kind=lbl, cell=k,
                             minutes_factor=mfac, rate_factor=rfac, n=int(ok.sum()),
                             points_mae=mm, ref_pts_mae=mr, skill_vs_ref_pts=s, rmse=rmse,
                             r2_forecast_as_is=B.r2_forecast(y[ok], yh[ok])))
    # the D076 reference itself, for the row of the table it belongs on
    s0, m0, _ = B.skill(y, ref_pts, ref_pts)
    print("  %-32s %11.4f %+11.5f %11.4f %9.4f  [D076 reference: prior mean of POINTS directly]"
          % ("REF_pts (D076 denominator)", m0, 0.0,
             float(np.sqrt(np.mean((y - ref_pts) ** 2))), B.r2_forecast(y, ref_pts)))
hyb_rows.append(dict(naive_rate_variant="-", naive_rate_kind="D076 prior mean of POINTS",
                     cell="REF_pts", minutes_factor="-", rate_factor="-", n=int(len(y)),
                     points_mae=B.mae(y, ref_pts), ref_pts_mae=B.mae(y, ref_pts),
                     skill_vs_ref_pts=0.0,
                     rmse=float(np.sqrt(np.mean((y - ref_pts) ** 2))),
                     r2_forecast_as_is=B.r2_forecast(y, ref_pts)))
pd.DataFrame(hyb_rows).to_csv(os.path.join(B.OUT, "hybrid_2x2.csv"), index=False)
OUT["hybrid_2x2"] = hyb_rows

B.hdr("STEP 3b -- PAIRED CONTRASTS, (season,player) BLOCK SIGN-FLIP NULL, 2000 draws")
CONTRASTS = [("H2_model_min_x_naive_rate", "H1_model_min_x_model_rate",
              "does a NAIVE rate beat the MODEL rate when both use MODEL minutes?"),
             ("H3_naive_min_x_model_rate", "H1_model_min_x_model_rate",
              "does the MODEL's minutes forecast add value on top of its own rate?"),
             ("H4_naive_min_x_naive_rate", "H2_model_min_x_naive_rate",
              "does the MODEL's minutes forecast add value on top of a NAIVE rate?"),
             ("H4_naive_min_x_naive_rate", "H3_naive_min_x_model_rate",
              "does the MODEL's rate add value on top of NAIVE minutes?")]
con_rows = []
draws_store = {}
print("\n  %-38s %-38s %11s %11s %9s" % ("A", "B", "MAE A", "MAE B", "p"))
for rv in ["A", "B"]:
    for a, b, why in CONTRASTS:
        ya, yb = HYB[rv][a], HYB[rv][b]
        ok = np.isfinite(ya) & np.isfinite(yb)
        d = np.abs(y[ok] - ya[ok]) - np.abs(y[ok] - yb[ok])
        bt = B.block_signflip_test(d, blocks[ok], n_draws=2000, return_draws=True)
        print("  %-38s %-38s %11.4f %11.4f %9.4f  [%s]"
              % (a[:38], b[:38], B.mae(y[ok], ya[ok]), B.mae(y[ok], yb[ok]),
                 bt["p_two_sided_blockflip"], rv))
        con_rows.append(dict(naive_rate_variant=rv, A=a, B=b, question=why,
                             mae_A=B.mae(y[ok], ya[ok]), mae_B=B.mae(y[ok], yb[ok]),
                             mean_paired_abs_err_diff_A_minus_B=bt["mean_diff"],
                             p_two_sided_block_signflip=bt["p_two_sided_blockflip"],
                             null_sd=bt["null_sd"], n_blocks=bt["n_blocks"],
                             n_rows=bt["n_rows"], n_draws=bt["n_draws"], seed=bt["seed"]))
        draws_store["%s__%s_vs_%s" % (rv, a, b)] = bt["draws"]
    # champion vs D076 reference, the -0.22% itself
    d = np.abs(y - f["pts__pred_point"].to_numpy(float)) - np.abs(y - ref_pts)
    bt = B.block_signflip_test(d, blocks, n_draws=2000, return_draws=True)
    con_rows.append(dict(naive_rate_variant=rv, A="CHAMPION_pts_pred", B="REF_pts",
                         question="is the champion's -0.22% points skill distinguishable from 0?",
                         mae_A=B.mae(y, f["pts__pred_point"]), mae_B=B.mae(y, ref_pts),
                         mean_paired_abs_err_diff_A_minus_B=bt["mean_diff"],
                         p_two_sided_block_signflip=bt["p_two_sided_blockflip"],
                         null_sd=bt["null_sd"], n_blocks=bt["n_blocks"], n_rows=bt["n_rows"],
                         n_draws=bt["n_draws"], seed=bt["seed"]))
    draws_store["%s__CHAMPION_vs_REF" % rv] = bt["draws"]
    break_flag = True
print("  champion vs D076 ref_pts: mean paired |err| diff = %+.5f  p=%.4f"
      % (con_rows[-1]["mean_paired_abs_err_diff_A_minus_B"],
         con_rows[-1]["p_two_sided_block_signflip"]))
pd.DataFrame(con_rows).to_csv(os.path.join(B.OUT, "hybrid_contrasts.csv"), index=False)
pd.DataFrame(draws_store).to_csv(os.path.join(B.OUT, "blockflip_draws.csv"), index=False)
OUT["hybrid_contrasts"] = con_rows

B.hdr("STEP 3c -- THE SAME 2x2 ON THE FGA CHAIN: POINTS = FGA x POINTS-PER-FGA")
g_ok = np.isfinite(f["mdl_ppf"].to_numpy(float)) & np.isfinite(f["refA_ppf"].to_numpy(float))
mfga = f["fga__pred_point"].to_numpy(float)
rfga = f["ref_fga"].to_numpy(float)
g_rows = []
print("\n  %-32s %11s %11s   (n=%d rows where the model's FGA forecast is > 0)"
      % ("cell", "points MAE", "skill", int(g_ok.sum())))
for rv in ["A", "B"]:
    mppf = f["mdl_ppf"].to_numpy(float)
    rppf = f["ref%s_ppf" % rv].to_numpy(float)
    for k, yh in [("G1_model_fga_x_model_ppf", mfga * mppf),
                  ("G2_model_fga_x_naive_ppf", mfga * rppf),
                  ("G3_naive_fga_x_model_ppf", rfga * mppf),
                  ("G4_naive_fga_x_naive_ppf", rfga * rppf)]:
        ok = g_ok & np.isfinite(yh)
        s, mm, _ = B.skill(y[ok], yh[ok], ref_pts[ok])
        print("  %-32s %11.4f %+11.5f   [%s]" % (k, mm, s, rv))
        g_rows.append(dict(naive_rate_variant=rv, cell=k, n=int(ok.sum()), points_mae=mm,
                           skill_vs_ref_pts=s))
pd.DataFrame(g_rows).to_csv(os.path.join(B.OUT, "hybrid_fga_chain.csv"), index=False)
OUT["hybrid_fga_chain"] = g_rows

# =====================================================================================
B.hdr("STEP 4 -- IS THE CEILING INTRINSIC?  AN ORACLE LADDER.")
# =====================================================================================
print("""
  METHOD AND ITS ASSUMPTIONS, STATED PLAINLY.
  The oracles below DELIBERATELY READ THE FUTURE.  They are NOT forecasts, are NEVER used as a
  skill reference, and exist only to bound how much of game-to-game points variation is even
  forecastable.  O1-O3 use the player's WHOLE-SEASON information and O2-O4 use the ACTUAL minutes
  played, both unavailable pre-game.  An oracle's MAE is therefore a LOWER BOUND on any honest
  forecast's MAE.  If the champion sits close to it, the remaining error is irreducible at the
  player-game level given that information -- an ESTIMATE, not a theorem.

  ASSUMPTIONS: (i) a player's true scoring rate is roughly constant within a season, so a
  season-mean rate is a fair stand-in for "perfect knowledge of the player"; (ii) the relationship
  between minutes and points is roughly linear within a player-season; (iii) the STABLE subset is
  chosen from PRE-GAME observables only, so the ceiling quoted on it is one a forecaster could
  actually target.  Violations of (i)/(ii) make the oracle WEAKER, so the estimated ceiling is
  conservative -- the true ceiling is at least this good.
""")
STABLE = (f["pl_games_prior"].to_numpy(float) >= 15) & (f["pl_min_mean5"].to_numpy(float) >= 24)
print("  STABLE subset (PRE-GAME rule: >=15 prior same-season appearances AND trailing-5 mean "
      "minutes >=24): n=%d of %d (%.1f%%)" % (STABLE.sum(), len(f), 100 * STABLE.mean()))

ps = f.groupby(["season", "player_id"], sort=False)
f["_o_pts_mean"] = ps["y_pts"].transform("mean")
f["_o_ppm_mean"] = ps["y_pts"].transform("sum") / ps["y_minutes"].transform("sum")
f["_o_n"] = ps["y_pts"].transform("size")

def within_block_ols(fr, ycol, xcol, key=("season", "player_id"), min_n=5):
    """ORACLE: OLS of y on x fitted INSIDE each player-season using that season's own games.
    Reads the future by construction; ceiling estimate only."""
    out = np.full(len(fr), np.nan)
    yv = fr[ycol].to_numpy(float)
    xv = fr[xcol].to_numpy(float)
    for _, idx in fr.groupby(list(key), sort=False).indices.items():
        if len(idx) < min_n:
            out[idx] = yv[idx].mean()
            continue
        X = np.column_stack([np.ones(len(idx)), xv[idx]])
        beta, *_ = np.linalg.lstsq(X, yv[idx], rcond=None)
        out[idx] = X @ beta
    return out

f["_o_ols_min"] = within_block_ols(f, "y_pts", "y_minutes")

LADDER = [
    ("REF   prior-mean of points (D076 reference)", f["ref_pts"].to_numpy(float), "honest"),
    ("MODEL champion pts__pred_point",              f["pts__pred_point"].to_numpy(float), "honest"),
    ("H2    model minutes x naive prior rate",      HYB["A"]["H2_model_min_x_naive_rate"], "honest"),
    ("O4    ACTUAL minutes x model rate",           f["y_minutes"].to_numpy(float) * f["mdl_ppm"].to_numpy(float), "ORACLE"),
    ("O5    model minutes x SEASON-MEAN rate",      f["minutes__pred_point"].to_numpy(float) * f["_o_ppm_mean"].to_numpy(float), "ORACLE"),
    ("O1    SEASON-MEAN points (knows the season)", f["_o_pts_mean"].to_numpy(float), "ORACLE"),
    ("O2    ACTUAL minutes x SEASON-MEAN rate",     f["y_minutes"].to_numpy(float) * f["_o_ppm_mean"].to_numpy(float), "ORACLE"),
    ("O3    within-player-season OLS on ACTUAL min", f["_o_ols_min"].to_numpy(float), "ORACLE"),
]
lad_rows = []
for subset, sname in [(np.ones(len(f), bool), "ALL"), (STABLE, "STABLE (pre-game rule)")]:
    print("\n  ---- %s  (n=%d) ----" % (sname, int(subset.sum())))
    print("  %-46s %-7s %10s %10s %10s %12s" %
          ("forecast", "kind", "MAE", "RMSE", "R2 as-is", "MAE vs O2"))
    o2 = (f["y_minutes"].to_numpy(float) * f["_o_ppm_mean"].to_numpy(float))[subset]
    mae_o2 = B.mae(y[subset], o2)
    for label, yh, kind in LADDER:
        v = yh[subset]
        ok = np.isfinite(v)
        mm = B.mae(y[subset][ok], v[ok])
        print("  %-46s %-7s %10.4f %10.4f %10.4f %12s"
              % (label, kind, mm, float(np.sqrt(np.mean((y[subset][ok] - v[ok]) ** 2))),
                 B.r2_forecast(y[subset][ok], v[ok]),
                 "%+.4f" % (mm - mae_o2)))
        lad_rows.append(dict(subset=sname, n=int(ok.sum()), forecast=label, kind=kind, mae=mm,
                             rmse=float(np.sqrt(np.mean((y[subset][ok] - v[ok]) ** 2))),
                             r2_forecast_as_is=B.r2_forecast(y[subset][ok], v[ok]),
                             mae_minus_oracle_O2=mm - mae_o2))
pd.DataFrame(lad_rows).to_csv(os.path.join(B.OUT, "ceiling_oracle_ladder.csv"), index=False)
OUT["ceiling_oracle_ladder"] = lad_rows

# variance accounting on the stable subset
print("\n  VARIANCE ACCOUNTING (plain unweighted R2, D069, on the STABLE subset):")
sub = f[STABLE].copy()
ys = sub["y_pts"].to_numpy(float)
fe = pd.get_dummies(sub["season"].astype(str) + "_" + sub["player_id"].astype(str),
                    drop_first=True).to_numpy(float)
r2_fe = sk.r2_plain(ys, fe)
r2_fe_min = sk.r2_plain(ys, np.column_stack([fe, sub["y_minutes"].to_numpy(float)]))
r2_model = B.r2_forecast(ys, sub["pts__pred_point"].to_numpy(float))
r2_ref = B.r2_forecast(ys, sub["ref_pts"].to_numpy(float))
print("    R2 of player-season fixed effects alone (ORACLE)               = %.4f" % r2_fe)
print("    R2 of player-season FE + ACTUAL minutes played (ORACLE)        = %.4f" % r2_fe_min)
print("    R2 of the champion forecast as-is (honest)                     = %.4f" % r2_model)
print("    R2 of the prior-mean reference as-is (honest)                  = %.4f" % r2_ref)
print("    -> IRREDUCIBLE share of points variance left even to the oracle = %.1f%%"
      % (100 * (1 - r2_fe_min)))
print("    -> headroom between the champion and the FE+actual-minutes oracle = %.4f R2"
      % (r2_fe_min - r2_model))
OUT["ceiling_variance_accounting"] = dict(
    subset="STABLE (pre-game rule: >=15 prior appearances AND trailing-5 mean minutes >=24)",
    n=int(STABLE.sum()),
    r2_oracle_player_season_FE=float(r2_fe),
    r2_oracle_player_season_FE_plus_ACTUAL_minutes=float(r2_fe_min),
    r2_champion_forecast_as_is=float(r2_model),
    r2_prior_mean_reference_as_is=float(r2_ref),
    irreducible_share_of_variance=float(1 - r2_fe_min),
    headroom_r2_champion_to_oracle=float(r2_fe_min - r2_model),
    convention="D069 plain unweighted; oracle rows use screenkit.r2_plain (an OLS fit, correct "
               "here because FE/minutes really are regressors); honest rows use r2_forecast "
               "(1-SSE/SST about the supplied forecast).")

# how much of the model's points error is attributable to minutes error vs rate error
print("\n  ERROR ATTRIBUTION (points MAE, all rows):")
mae_champ = B.mae(y, f["pts__pred_point"].to_numpy(float))
mae_oracle_min = B.mae(y, f["y_minutes"].to_numpy(float) * f["mdl_ppm"].to_numpy(float))
mae_oracle_rate = B.mae(y, f["minutes__pred_point"].to_numpy(float) * f["r_ppm"].to_numpy(float))
print("    champion                                          %.4f" % mae_champ)
print("    give it PERFECT MINUTES, keep its own rate        %.4f   (cut %.1f%%)"
      % (mae_oracle_min, 100 * (1 - mae_oracle_min / mae_champ)))
print("    give it PERFECT RATE, keep its own minutes        %.4f   (cut %.1f%%)"
      % (mae_oracle_rate, 100 * (1 - mae_oracle_rate / mae_champ)))
OUT["error_attribution"] = dict(champion_points_mae=mae_champ,
                                perfect_minutes_own_rate_mae=mae_oracle_min,
                                perfect_rate_own_minutes_mae=mae_oracle_rate,
                                pct_cut_from_perfect_minutes=100 * (1 - mae_oracle_min / mae_champ),
                                pct_cut_from_perfect_rate=100 * (1 - mae_oracle_rate / mae_champ),
                                note="ORACLE decomposition; both read the outcome. Reported to "
                                     "show WHICH factor's error dominates, not as a forecast.")

f.to_parquet(os.path.join(B.OUT, "decomp_frame.parquet"), index=False)
json.dump(OUT, open(os.path.join(B.OUT, "_s02.json"), "w"), indent=2, default=str)
print("\nDONE s02")
