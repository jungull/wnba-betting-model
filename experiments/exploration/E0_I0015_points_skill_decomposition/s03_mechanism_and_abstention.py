"""STEP 3d -- WHY the composition loses skill (the mechanism).
   STEP 4b -- an HONEST (pre-game-reachable) ceiling, not just an oracle one.
   STEP 5  -- does abstention help the RATE component?  Full screen with correct-level nulls.
"""
import json
import os

import numpy as np
import pandas as pd

import psd_base as B
import screenkit as sk

pd.set_option("display.width", 230)
pd.set_option("display.max_columns", 60)

OUT = {}
f = pd.read_parquet(os.path.join(B.OUT, "decomp_frame.parquet"))
sk.assert_partition(f, verbose=False)
y = f["y_pts"].to_numpy(float)
blocks = B.block_codes_player_season(f)

# =====================================================================================
B.hdr("STEP 3d -- MECHANISM: WHY DO INDIVIDUALLY-BETTER FACTORS MULTIPLY INTO A WORSE PRODUCT?")
# =====================================================================================
print("""
  POINTS = MINUTES x RATE is a PRODUCT, and the conditional mean of a product is
      E[M*R] = E[M]*E[R] + Cov(M, R).
  Multiplying two separately-good marginal forecasts therefore omits the covariance term, and
  amplifies each factor's variance into the other.  Two measurable consequences are checked below.
""")
mmin = f["minutes__pred_point"].to_numpy(float)
rmin = f["ref_minutes"].to_numpy(float)
mppm = f["mdl_ppm"].to_numpy(float)
rppm = f["refA_ppm"].to_numpy(float)
rppmB = f["refB_ppm"].to_numpy(float)

# (i) the realised minutes-efficiency correlation, WITHIN player-season (an outcome property)
def within_corr(a, b, codes):
    a = np.asarray(a, float); b = np.asarray(b, float)
    da = a - pd.Series(a).groupby(codes).transform("mean").to_numpy()
    db = b - pd.Series(b).groupby(codes).transform("mean").to_numpy()
    m = np.isfinite(da) & np.isfinite(db)
    return float(np.corrcoef(da[m], db[m])[0, 1])

c_within = within_corr(f["y_minutes"], f["r_ppm"], blocks)
c_pooled = float(np.corrcoef(f["y_minutes"], f["r_ppm"])[0, 1])
print("  (i) realised corr(minutes, points-per-minute):  pooled %+.4f   WITHIN player-season %+.4f"
      % (c_pooled, c_within))
print("      OBSERVED SIGN IS POSITIVE, so the blowout/garbage-time story (more minutes at LOWER")
print("      efficiency) is NOT what is happening here -- within a player-season, the games where")
print("      a player plays more are also the games she scores at a HIGHER rate.  Cov(M,R) > 0,")
print("      so a product of marginal forecasts UNDERSTATES the mean and the two factors' errors")
print("      reinforce rather than cancel.  Candidate explanation (d) as originally worded is")
print("      REJECTED IN SIGN; the compounding is real but runs the other way.")

# (ii) dispersion of each candidate forecast vs the outcome
print("\n  (ii) forecast dispersion (sd) against the outcome's own sd:")
disp = [("y_pts (outcome)", y), ("REF_pts", f["ref_pts"].to_numpy(float)),
        ("H1 model_min x model_rate", mmin * mppm), ("H2 model_min x naive_rate", mmin * rppm),
        ("H3 naive_min x model_rate", rmin * mppm), ("H4 naive_min x naive_rate", rmin * rppm)]
disp_rows = []
for lbl, v in disp:
    sd = float(np.nanstd(v, ddof=1))
    b = float(np.nanmean(v) - np.nanmean(y))
    print("      %-30s sd=%7.4f  mean bias vs outcome=%+7.4f" % (lbl, sd, b))
    disp_rows.append(dict(forecast=lbl, sd=sd, mean_bias=b))
print("      A forecast whose sd EXCEEDS what its information supports is over-dispersed and pays")
print("      for it in MAE on a noisy target.  Compare H1 with H3.")

# (iii) the two factors' errors, and whether they compound
e_min_model = f["y_minutes"].to_numpy(float) - mmin
e_min_naive = f["y_minutes"].to_numpy(float) - rmin
e_rate_model = f["r_ppm"].to_numpy(float) - mppm
e_rate_naive = f["r_ppm"].to_numpy(float) - rppm
print("\n  (iii) sd of each factor's own forecast error, and the error correlation that compounds:")
print("      minutes: model sd=%.4f  naive sd=%.4f   (model is the BETTER minutes forecast)"
      % (e_min_model.std(ddof=1), e_min_naive.std(ddof=1)))
print("      rate   : model sd=%.5f naive sd=%.5f  (model is the BETTER rate forecast)"
      % (e_rate_model.std(ddof=1), e_rate_naive.std(ddof=1)))
for lbl, em, er in [("model minutes x model rate", e_min_model, e_rate_model),
                    ("naive minutes x model rate", e_min_naive, e_rate_model),
                    ("model minutes x naive rate", e_min_model, e_rate_naive),
                    ("naive minutes x naive rate", e_min_naive, e_rate_naive)]:
    print("      corr(minutes error, rate error) for %-28s = %+.4f" % (lbl,
          float(np.corrcoef(em, er)[0, 1])))
OUT["mechanism"] = dict(
    corr_minutes_ppm_pooled=c_pooled, corr_minutes_ppm_within_player_season=c_within,
    dispersion=disp_rows,
    sd_minutes_error_model=float(e_min_model.std(ddof=1)),
    sd_minutes_error_naive=float(e_min_naive.std(ddof=1)),
    sd_rate_error_model=float(e_rate_model.std(ddof=1)),
    sd_rate_error_naive=float(e_rate_naive.std(ddof=1)),
    corr_factor_errors={
        "model_min_x_model_rate": float(np.corrcoef(e_min_model, e_rate_model)[0, 1]),
        "naive_min_x_model_rate": float(np.corrcoef(e_min_naive, e_rate_model)[0, 1]),
        "model_min_x_naive_rate": float(np.corrcoef(e_min_model, e_rate_naive)[0, 1]),
        "naive_min_x_naive_rate": float(np.corrcoef(e_min_naive, e_rate_naive)[0, 1])},
    note="POINTS = MINUTES x RATE. E[M*R] = E[M]E[R] + Cov(M,R). A product of separately-good "
         "marginal forecasts omits Cov and compounds both factors' errors.")

# (iv) shrinkage sweep -- does simply shrinking the champion's points forecast recover the skill?
print("\n  (iv) SHRINKAGE SWEEP.  If the loss is over-dispersion, shrinking the champion's points")
print("       forecast toward the player's prior mean should recover skill with NO new information.")
shr = []
ref_pts = f["ref_pts"].to_numpy(float)
champ = f["pts__pred_point"].to_numpy(float)
for lam in [0.0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75, 1.0]:
    yh = (1 - lam) * champ + lam * ref_pts
    s, mm, _ = B.skill(y, yh, ref_pts)
    shr.append(dict(lambda_toward_reference=lam, points_mae=mm, skill_vs_ref=s))
    print("       lambda=%.2f  MAE=%.4f  skill=%+.5f" % (lam, mm, s))
OUT["shrinkage_sweep"] = shr
pd.DataFrame(shr).to_csv(os.path.join(B.OUT, "shrinkage_sweep.csv"), index=False)

# (v) is the shrinkage gain OVER-DISPERSION, or is it an ENSEMBLE gain?  These are different
#     diagnoses with different fixes, and the sd table above already argues against over-dispersion
#     (H1 sd 5.77 is BELOW the reference's 5.79 and far below the outcome's 7.58).
e_champ = y - champ
e_ref = y - ref_pts
print("\n  (v) OVER-DISPERSION or ENSEMBLE GAIN?  These have different fixes.")
print("      corr(champion error, reference error) = %+.4f" % float(np.corrcoef(e_champ, e_ref)[0, 1]))
print("      sd(champion forecast)=%.4f  sd(reference)=%.4f  sd(outcome)=%.4f"
      % (champ.std(ddof=1), ref_pts.std(ddof=1), y.std(ddof=1)))
print("      corr(champion forecast, reference forecast) = %+.4f"
      % float(np.corrcoef(champ, ref_pts)[0, 1]))
print("      The champion is NOT more dispersed than the reference, so 'over-confident spread' is")
print("      NOT the diagnosis.  The two forecasts make PARTLY INDEPENDENT errors, so a blend beats")
print("      either -- an ENSEMBLE gain.  The champion's information is real; it is simply not")
print("      incremental to the prior mean as a point forecast.")
blend_rows = []
for lbl, other in [("champion + reference", ref_pts),
                   ("champion + H3(naive_min x model_rate)", rmin * mppm),
                   ("reference + H3(naive_min x model_rate)", rmin * mppm)]:
    basev = ref_pts if lbl.startswith("reference") else champ
    best = None
    for lam in np.arange(0, 1.001, 0.05):
        yh = (1 - lam) * basev + lam * other
        s, mm, _ = B.skill(y, yh, ref_pts)
        if best is None or mm < best[1]:
            best = (lam, mm, s)
    print("      best blend %-42s lambda=%.2f  MAE=%.4f  skill=%+.5f"
          % (lbl, best[0], best[1], best[2]))
    blend_rows.append(dict(blend=lbl, best_lambda=float(best[0]), points_mae=float(best[1]),
                           skill_vs_ref=float(best[2])))
OUT["ensemble_diagnosis"] = dict(
    corr_champion_error_reference_error=float(np.corrcoef(e_champ, e_ref)[0, 1]),
    corr_champion_forecast_reference_forecast=float(np.corrcoef(champ, ref_pts)[0, 1]),
    sd_champion_forecast=float(champ.std(ddof=1)), sd_reference=float(ref_pts.std(ddof=1)),
    sd_outcome=float(y.std(ddof=1)), best_blends=blend_rows,
    diagnosis="NOT over-dispersion (champion sd < reference sd). The gain from blending is an "
              "ENSEMBLE gain from partly independent errors. Blend weights were swept AFTER seeing "
              "the skill numbers and are IN-SAMPLE -- see NOTES.md section 8.")
pd.DataFrame(blend_rows).to_csv(os.path.join(B.OUT, "blend_sweep.csv"), index=False)

# =====================================================================================
B.hdr("STEP 4b -- AN HONEST, PRE-GAME-REACHABLE CEILING (not just an oracle one)")
# =====================================================================================
STABLE = (f["pl_games_prior"].to_numpy(float) >= 15) & (f["pl_min_mean5"].to_numpy(float) >= 24)
sub = f[STABLE].copy()
ys = sub["y_pts"].to_numpy(float)
fe = pd.get_dummies(sub["season"].astype(str) + "_" + sub["player_id"].astype(str),
                    drop_first=True).to_numpy(float)
lad = {
    "oracle: player-season FE alone (perfect knowledge of WHO)":
        sk.r2_plain(ys, fe),
    "oracle-on-player + HONEST model minutes forecast":
        sk.r2_plain(ys, np.column_stack([fe, sub["minutes__pred_point"].to_numpy(float)])),
    "oracle-on-player + ACTUAL minutes played (UNREACHABLE)":
        sk.r2_plain(ys, np.column_stack([fe, sub["y_minutes"].to_numpy(float)])),
}
print("  STABLE subset n=%d (pre-game rule).  Plain unweighted R2 (D069):" % len(sub))
for k, v in lad.items():
    print("    %-58s %.4f" % (k, v))
r2_champ = B.r2_forecast(ys, sub["pts__pred_point"].to_numpy(float))
r2_ref = B.r2_forecast(ys, sub["ref_pts"].to_numpy(float))
print("    %-58s %.4f" % ("HONEST: champion forecast as-is", r2_champ))
print("    %-58s %.4f" % ("HONEST: prior-mean reference as-is", r2_ref))
reachable = lad["oracle-on-player + HONEST model minutes forecast"]
print("\n  The largest R2 any PRE-GAME forecast could reach if it knew each player's true")
print("  season-long scoring level perfectly and forecast minutes exactly as well as the champion")
print("  already does is %.4f.  The champion is at %.4f and the naive reference at %.4f."
      % (reachable, r2_champ, r2_ref))
print("  Reachable headroom = %.4f R2.  Unreachable (needs the actual minutes played) = %.4f R2."
      % (reachable - r2_champ,
         lad["oracle-on-player + ACTUAL minutes played (UNREACHABLE)"] - reachable))
print("  Irreducible even to the ACTUAL-minutes oracle = %.1f%% of points variance."
      % (100 * (1 - lad["oracle-on-player + ACTUAL minutes played (UNREACHABLE)"])))
OUT["honest_ceiling"] = dict(
    subset="STABLE pre-game rule (>=15 prior same-season appearances AND trailing-5 mean min >=24)",
    n=int(len(sub)),
    r2_oracle_player_FE=float(lad["oracle: player-season FE alone (perfect knowledge of WHO)"]),
    r2_reachable_oracle_player_plus_honest_minutes=float(reachable),
    r2_unreachable_oracle_player_plus_ACTUAL_minutes=float(
        lad["oracle-on-player + ACTUAL minutes played (UNREACHABLE)"]),
    r2_champion=float(r2_champ), r2_reference=float(r2_ref),
    reachable_headroom_r2=float(reachable - r2_champ),
    unreachable_headroom_r2=float(
        lad["oracle-on-player + ACTUAL minutes played (UNREACHABLE)"] - reachable),
    irreducible_variance_share=float(
        1 - lad["oracle-on-player + ACTUAL minutes played (UNREACHABLE)"]))

# =====================================================================================
B.hdr("STEP 5 -- DOES ABSTENTION HELP THE RATE COMPONENT?")
# =====================================================================================
f["pts__pred_width"] = f["pts__pred_q95"] - f["pts__pred_q05"]
f["minutes__pred_width"] = f["minutes__pred_q95"] - f["minutes__pred_q05"]
f["fga__pred_width"] = f["fga__pred_q95"] - f["fga__pred_q05"]
f["pts__pred_iqr"] = f["pts__pred_q75"] - f["pts__pred_q25"]
f["rate_pred_width"] = f["pts__pred_width"] / f["minutes__pred_point"]
f["rate_pred_cv"] = f["pts__pred_sd"] / f["pts__pred_point"].replace(0, np.nan)

CANDIDATES = [c for c in [
    "pl_games_prior", "pl_minutes_prior", "pl_career_games_prior", "pl_prior_season_games",
    "pl_is_rookie_window", "pl_min_sd5", "pl_min_mean5", "pl_fga_sd5", "pl_fga_mean5",
    "pl_pts_sd5", "pl_pts_mean5", "pl_usg_sd5", "pl_usg_mean5", "pl_min_cv5", "pl_min_rng5",
    "pl_min_trend5", "pl_abs_min_trend5", "pl_start_frac5", "pl_start_switch5", "pl_rest_days",
    "pl_teamgames_since_appear", "pl_dnp_frac5",
    "tm_game_idx", "tm_rest_days", "tm_b2b", "tm_3in4", "tm_games_prior7d", "tm_poss_mean_prior",
    "tm_roster_churn_prior", "tm_newfaces_prior", "tm_five_tenure_prior", "tm_five_changed_prior",
    "tm_season_progress", "tm_prior_meetings", "tm_first_meeting", "tm_is_home", "tm_rest_diff",
    "opp_poss_mean_prior", "opp_rest_days", "opp_game_idx",
    "pts__pred_sd", "pts__pred_width", "pts__pred_iqr", "pts__is_fallback", "pts__fallback_level",
    "pts__is_cold_start", "pts__n_prior_games", "minutes__pred_sd", "minutes__pred_width",
    "minutes__is_fallback", "fga__pred_sd", "fga__pred_width", "fga__is_fallback",
    "rate_pred_width", "rate_pred_cv",
] if c in f.columns]
print("  candidate list fixed BEFORE any abstention curve was computed: %d candidates"
      % len(CANDIDATES))

DEPENDENTS = [
    ("rate_ppm_refA", "r_ppm", "mdl_ppm", "refA_ppm"),
    ("rate_ppm_refB", "r_ppm", "mdl_ppm", "refB_ppm"),
    ("rate_ppf_refA", "r_ppf", "mdl_ppf", "refA_ppf"),
    ("level_points",  "y_pts", "pts__pred_point", "ref_pts"),
    ("level_minutes", "y_minutes", "minutes__pred_point", "ref_minutes"),
]
COV = 0.75

def skill_gain_at(v, y_, m_, r_, ascending, cov=COV):
    """skill on the kept `cov` fraction MINUS skill on all rows.  Reference faces the SAME rows."""
    fin = np.isfinite(v) & np.isfinite(y_) & np.isfinite(m_) & np.isfinite(r_)
    n = int(fin.sum())
    if n < 200:
        return np.nan
    key = np.where(fin, v if ascending else -v, np.inf)
    order = np.argsort(key, kind="stable")[:max(int(round(cov * n)), 50)]
    s_all = 1.0 - np.abs(y_[fin] - m_[fin]).mean() / np.abs(y_[fin] - r_[fin]).mean()
    s_keep = 1.0 - np.abs(y_[order] - m_[order]).mean() / np.abs(y_[order] - r_[order]).mean()
    return float(s_keep - s_all)

# --- grouping level: report what the kit says, then choose the scheme by variance share ---
def var_share_between(v, codes):
    v = np.asarray(v, float)
    m = np.isfinite(v)
    if m.sum() < 10:
        return np.nan
    tot = np.nanvar(v[m])
    if tot <= 0:
        return np.nan
    s = pd.Series(v[m]).groupby(codes[m])
    gm = v[m].mean()
    num = float((s.count() * (s.mean() - gm) ** 2).sum())
    return float(num / m.sum() / tot)

# *** KIT DEFECT WORKAROUND ***  screenkit.detect_grouping_level (and permutation_null through the
# same helper `_constant_within`) raises TypeError on any BOOLEAN column, because bool passes
# pd.api.types.is_numeric_dtype and the numeric branch then does max - min on numpy bools.  See
# KIT_BUG_REPRO.py in this directory for a minimal reproduction.  The kit is outside this screen's
# write scope and was NOT modified; boolean candidates are cast to float here instead.
BOOLCAST = [c for c in CANDIDATES if pd.api.types.is_bool_dtype(f[c])]
for c in BOOLCAST:
    f[c] = f[c].astype(float)
print("  KIT DEFECT WORKAROUND: cast %d boolean candidates to float (%s) -- "
      "detect_grouping_level crashes on bool. See KIT_BUG_REPRO.py." % (len(BOOLCAST), BOOLCAST))

lvl_rows = []
for c in CANDIDATES:
    d = sk.detect_grouping_level(f, c)
    vsb = var_share_between(f[c].to_numpy(float), blocks)
    lvl_rows.append(dict(candidate=c, kit_recommended_level=d["recommended_permutation_level"],
                         n_distinct=d["n_distinct_values_global"],
                         var_share_between_player_season=vsb,
                         scheme_used="BETWEEN-block" if (vsb is not None and vsb == vsb and vsb > 0.5)
                                     else "WITHIN-block"))
lv = pd.DataFrame(lvl_rows)
lv.to_csv(os.path.join(B.OUT, "grouping_levels.csv"), index=False)
print("\n  screenkit.detect_grouping_level recommendation, counted:")
print(lv["kit_recommended_level"].value_counts().to_string())
print("  permutation scheme actually used (chosen by variance share between player-seasons):")
print(lv["scheme_used"].value_counts().to_string())
print("""
  *** KIT GAP, DECLARED. *** detect_grouping_level recommends 'row' for a feature that varies row
  by row -- correct as to WHERE THE FEATURE VARIES, but 'row' is exactly the anticonservative null
  this program has found wrong six times, because the OUTCOME is clustered by player-season even
  when the feature is not.  The kit's own docstring admits it does not detect this.  The kit offers
  no WITHIN-block scheme at all, so both block schemes below are implemented here, mirroring D076's
  rh_base.  The kit's ROW_LEVEL null is run alongside purely to publish the inflation factor.
""")

# --- permutation indices, shared across every candidate/dependent so max-stat is valid ---
def block_lists(codes, seasons):
    g = {}
    for i, (c, s) in enumerate(zip(codes, seasons)):
        g.setdefault(s, {}).setdefault(c, []).append(i)
    return {s: [np.array(v) for v in d.values()] for s, d in g.items()}

seasons = f["season"].to_numpy()
BL = block_lists(blocks, seasons)

def between_index(rng, n):
    idx = np.arange(n)
    for s, bl in BL.items():
        order = rng.permutation(len(bl))
        for i, b in enumerate(bl):
            don = bl[order[i]]
            idx[b] = don[np.arange(len(b)) % len(don)]
    return idx

def within_index(rng, n):
    idx = np.arange(n)
    for s, bl in BL.items():
        for b in bl:
            idx[b] = b[rng.permutation(len(b))]
    return idx

def row_index(rng, n):
    idx = np.arange(n)
    for s in np.unique(seasons):
        m = np.where(seasons == s)[0]
        idx[m] = m[rng.permutation(len(m))]
    return idx

N_DRAWS = 400
n = len(f)
rngs = {k: np.random.default_rng(B.SEED + i) for i, k in enumerate(["between", "within", "row"])}
IDX = {"between": [between_index(rngs["between"], n) for _ in range(N_DRAWS)],
       "within":  [within_index(rngs["within"], n) for _ in range(N_DRAWS)],
       "row":     [row_index(rngs["row"], n) for _ in range(N_DRAWS)]}
print("  built %d permutation indices for each of 3 schemes (seed %d), shared across all cells"
      % (N_DRAWS, B.SEED))

dep_arr = {}
for dname, ycol, mcol, rcol in DEPENDENTS:
    dep_arr[dname] = (f[ycol].to_numpy(float), f[mcol].to_numpy(float), f[rcol].to_numpy(float))

rows = []
maxstat = {k: np.zeros(N_DRAWS) for k in ["correct", "row"]}
scheme_of = dict(zip(lv["candidate"], lv["scheme_used"]))
for c in CANDIDATES:
    v = pd.to_numeric(f[c], errors="coerce").to_numpy(float)
    sch = "between" if scheme_of[c] == "BETWEEN-block" else "within"
    perm_c = [v[ix] for ix in IDX[sch]]
    perm_r = [v[ix] for ix in IDX["row"]]
    for dname, (yv, mv, rv) in dep_arr.items():
        for asc, dirlbl in [(True, "abstain on HIGH"), (False, "abstain on LOW")]:
            real = skill_gain_at(v, yv, mv, rv, asc)
            if not np.isfinite(real):
                continue
            dc = np.array([skill_gain_at(pv, yv, mv, rv, asc) for pv in perm_c])
            dr = np.array([skill_gain_at(pv, yv, mv, rv, asc) for pv in perm_r])
            dcf, drf = dc[np.isfinite(dc)], dr[np.isfinite(dr)]
            p_c = (1 + int((dcf >= real).sum())) / (len(dcf) + 1)
            p_r = (1 + int((drf >= real).sum())) / (len(drf) + 1)
            maxstat["correct"] = np.maximum(maxstat["correct"], np.nan_to_num(dc, nan=-9e9))
            maxstat["row"] = np.maximum(maxstat["row"], np.nan_to_num(dr, nan=-9e9))
            rows.append(dict(candidate=c, dependent=dname, direction=dirlbl, coverage=COV,
                             skill_gain=real, scheme=scheme_of[c],
                             p_correct_level=p_c, p_row_level_NAIVE=p_r,
                             null_sd_correct=float(dcf.std(ddof=1)),
                             null_sd_row_NAIVE=float(drf.std(ddof=1)),
                             inflation_sd_correct_over_row=float(dcf.std(ddof=1) /
                                                                 drf.std(ddof=1))
                             if drf.std(ddof=1) > 0 else np.nan))
R = pd.DataFrame(rows)
R.to_csv(os.path.join(B.OUT, "abstention_rate_screen.csv"), index=False)
pd.DataFrame(maxstat).to_csv(os.path.join(B.OUT, "maxt_null_draws.csv"), index=False)

print("\n  %d cells = %d candidates x %d dependents x 2 directions" %
      (len(R), R["candidate"].nunique(), R["dependent"].nunique()))
print("  INFLATION FACTOR sd(correct-level null) / sd(NAIVE row-level null):")
inf = R["inflation_sd_correct_over_row"].dropna()
print("    median %.2f   5th-95th pct %.2f-%.2f   range %.2f-%.2f   fraction > 1: %.0f%%"
      % (inf.median(), inf.quantile(.05), inf.quantile(.95), inf.min(), inf.max(),
         100 * (inf > 1).mean()))

fw_correct = np.sort(maxstat["correct"])
fw_row = np.sort(maxstat["row"])
R["familywise_p_correct"] = [(1 + int((fw_correct >= g).sum())) / (len(fw_correct) + 1)
                             for g in R["skill_gain"]]
print("\n  FAMILY-WISE: observed max skill gain = %+.5f  against a correct-level max-stat null "
      "whose own max over %d draws = %+.5f" % (R["skill_gain"].max(), N_DRAWS, fw_correct.max()))
print("  (the NAIVE row-level max-stat null maxes at %+.5f -- it would have passed far more)"
      % fw_row.max())
R.to_csv(os.path.join(B.OUT, "abstention_rate_screen.csv"), index=False)

print("\n  TOP 15 CELLS BY SKILL GAIN AT 75%% COVERAGE:")
print(R.sort_values("skill_gain", ascending=False).head(15)[
    ["candidate", "dependent", "direction", "skill_gain", "scheme", "p_correct_level",
     "familywise_p_correct", "p_row_level_NAIVE"]].to_string(index=False,
    float_format=lambda v: "%+.5f" % v))

print("\n  BEST CELL PER DEPENDENT:")
best = R.loc[R.groupby("dependent")["skill_gain"].idxmax()]
print(best[["dependent", "candidate", "direction", "skill_gain", "p_correct_level",
            "familywise_p_correct"]].to_string(index=False, float_format=lambda v: "%+.5f" % v))

print("\n  HOW MANY CELLS CLEAR THE FAMILY on each dependent (familywise p < 0.05):")
print(R.assign(clears=R["familywise_p_correct"] < 0.05).groupby("dependent")["clears"].agg(
    ["sum", "size"]).to_string())

OUT["abstention_on_rates"] = dict(
    coverage=COV, n_candidates=len(CANDIDATES), n_cells=int(len(R)), n_draws=N_DRAWS,
    seed=B.SEED,
    inflation_median=float(inf.median()), inflation_p05=float(inf.quantile(.05)),
    inflation_p95=float(inf.quantile(.95)), inflation_min=float(inf.min()),
    inflation_max=float(inf.max()), inflation_frac_gt_1=float((inf > 1).mean()),
    familywise_max_stat_null_max_correct=float(fw_correct.max()),
    familywise_max_stat_null_max_row_NAIVE=float(fw_row.max()),
    observed_max_skill_gain=float(R["skill_gain"].max()),
    best_per_dependent=best[["dependent", "candidate", "direction", "skill_gain",
                             "p_correct_level", "familywise_p_correct"]].to_dict("records"),
    n_cells_clearing_family_by_dependent=R.assign(
        clears=R["familywise_p_correct"] < 0.05).groupby("dependent")["clears"].sum().to_dict(),
    top15=R.sort_values("skill_gain", ascending=False).head(15).to_dict("records"))

# full abstention curves for the best rate rule and for the D076 points rule, for comparability
curves = []
for dname, ycol, mcol, rcol in DEPENDENTS:
    brow = R[R["dependent"] == dname].sort_values("skill_gain", ascending=False).iloc[0]
    cur = B.abstention_curve(f, f[brow["candidate"]], f[ycol], f[mcol], f[rcol],
                             ascending=(brow["direction"] == "abstain on HIGH"))
    cur["dependent"] = dname
    cur["candidate"] = brow["candidate"]
    cur["direction"] = brow["direction"]
    curves.append(cur)
CU = pd.concat(curves, ignore_index=True)
CU.to_csv(os.path.join(B.OUT, "abstention_curves_best.csv"), index=False)
print("\n  ABSTENTION CURVES for the best candidate on each dependent:")
print(CU[["dependent", "candidate", "direction", "coverage", "n_kept", "model_mae", "ref_mae",
          "skill"]].to_string(index=False, float_format=lambda v: "%.5f" % v))
OUT["abstention_curves_best"] = CU.to_dict("records")

json.dump(OUT, open(os.path.join(B.OUT, "_s03.json"), "w"), indent=2, default=str)
print("\nDONE s03")
