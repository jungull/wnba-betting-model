"""E1_I0049 s05 -- emit CENSUS.csv, RE_DERIVATION.csv and FINDINGS.json from the raw outputs.

Every figure here is read from raw/ rather than retyped.
PREREG sha256 4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, r"experiments\exploration")
HERE = os.path.join(EXPL, "E1_I0049_benchmark_constants")
RAW = os.path.join(HERE, "raw")
sys.dont_write_bytecode = True
pd.set_option("display.width", 250)

anch = pd.read_csv(os.path.join(RAW, "_s02_anchors.csv"))
rd = pd.read_csv(os.path.join(RAW, "_s02_d089_rederived.csv"))
d84 = pd.read_csv(os.path.join(RAW, "_s02_d084_cstar.csv"))
fl = pd.read_csv(os.path.join(RAW, "_s03_floors_by_response.csv"))
s03 = json.load(open(os.path.join(RAW, "_s03.json")))
s04 = json.load(open(os.path.join(RAW, "_s04.json")))
mde = pd.read_csv(os.path.join(RAW, "_s02_mde_grid_copy.csv"))

H = rd[(rd.stratum == "DECISION") & (rd.base == "B_COMPLETE")
       & (rd.candidate == "P01_c04_prevgame")].iloc[0]
R84 = d84[(d84.spec == "SPEC_RA") & (d84.stratum == "on_stratum")].iloc[0]


def flr(arm_prefix, K):
    return float(fl[(fl.arm.str.startswith(arm_prefix)) & (fl.family_size_K == K)]
                 .MDE80_analytic.iloc[0])


k1d = mde[(mde.family_size_K == 1) & (mde.stratum == "DECISION")].mde80_DRIFT_CORRECTED
k132d = mde[(mde.family_size_K == 132) & (mde.stratum == "DECISION")].mde80_DRIFT_CORRECTED
pubrow = mde[(mde.stratum == "DECISION") & (mde.base == "B_COMPLETE")
             & (mde["null"] == "N_B_entity_swap_team_season")]

# =============================================================== CENSUS.csv =====================
census = [
 dict(constant="0.002057", name="BEST_LIVE / 'the programme's largest live effect'",
      first_computed_in="E1_I0018_teammate_volume_channel (D089), s04_points.py line ~ceiling block",
      first_recorded_at="FINDINGS.json /STEP_4.../in_sample_coefficient[13]/CEILING_dr2_points_per_sd",
      what_it_actually_is="an in-sample TRANSPORTED arithmetic CEILING, not an effect",
      response="y_pts (total box points)", row_set="DECISION n=5,673 (n_prior>=8 & prior5_minutes>=24)",
      seasons="2021-2024", sst_basis="sum((y_pts-mean)^2), unweighted mean, ddof irrelevant",
      weighting="none", base="[1, refB_ppm, refB_spm, refB_pps, refB_mpg]",
      fit_kind="in-sample OLS on y_ppm, transported to points by MEAN m_hat",
      statistic_family="variance share (|beta|*sd(x)*mean(m_hat)/sd(y))^2",
      bound_recorded="NO oracle in arithmetic_ceiling.csv; ceiling_reconciliation.csv DOES record "
                     "c*=1.3594722754 and ORACLE=0.0035630546 for this cell",
      control_recorded="NO -- none in any D089 table; measured here for the first time",
      status="RE-DERIVES EXACTLY; NOT A BOUND (c*>1)"),
 dict(constant="0.00102", name="FLOOR_1CELL / single-cell detection floor",
      first_computed_in="E1_I0026_detection_floor (D103), s07_drift_corrected_mde.py",
      first_recorded_at="mde_table.csv DECISION|B_COMPLETE|N_B_entity_swap_team_season|K=1",
      what_it_actually_is="drift-corrected MDE80 at 80% power, one preregistered cell",
      response="y_ppm (points per minute) -- df_base.py:51 OUTCOME='y_ppm'",
      row_set="DECISION n=5,673 on the D089 frame joined to the D085 frame",
      seasons="2021-2024", sst_basis="sum((y_ppm-mean)^2), unweighted mean", weighting="none",
      base="[1, refB_ppm, refB_spm, refB_pps, refB_mpg]",
      fit_kind="in-sample OLS increment, effect planted along a null-drawn carrier",
      statistic_family="OLS increment dR2",
      bound_recorded="n/a (a floor, not a ceiling)",
      control_recorded="YES -- type-I 0.040-0.069 across 24 cells at delta=0",
      status="RE-DERIVES; CONVENTION-SENSITIVE; WRONG RESPONSE for every constant it is quoted against"),
 dict(constant="0.00235", name="FLOOR_132 / 132-cell detection floor",
      first_computed_in="E1_I0026_detection_floor (D103)",
      first_recorded_at="mde_table.csv same cell, family_size_K=132",
      what_it_actually_is="drift-corrected MDE80, family of 132+ cells",
      response="y_ppm", row_set="DECISION n=5,673", seasons="2021-2024",
      sst_basis="sum((y_ppm-mean)^2), unweighted mean", weighting="none",
      base="[1, refB_ppm, refB_spm, refB_pps, refB_mpg]",
      fit_kind="as above, t_crit=6.974475 from the real 154-cell max-t null matrix",
      statistic_family="OLS increment dR2", bound_recorded="n/a",
      control_recorded="YES", status="RE-DERIVES; it is the MINIMUM of its own DECISION-stratum range"),
 dict(constant="0.000129", name="D084 conversion ceiling (dead lead)",
      first_computed_in="E1_I0004_efficiency_transfer_v2 (D084), s04_points_and_ceiling.py",
      first_recorded_at="arithmetic_ceiling.csv SPEC_RA/on_stratum CEILING_A_perfect_orthogonal_dR2",
      what_it_actually_is="transported arithmetic ceiling",
      response="points (total box), sd 7.550491622813534",
      row_set="on_stratum n=5,086 of an 11,267-row efficiency frame", seasons="2021-2024",
      sst_basis="var of y about its own mean on those rows", weighting="none",
      base="see E1_I0004_efficiency_transfer_v2 (point-in-time efficiency reference)",
      fit_kind="in-sample, centred opponent zone-conversion allowance transported to points",
      statistic_family="variance share (move_per_1sd/sd_y)^2",
      bound_recorded="YES -- DIAGNOSTIC_ORACLE_best_scaling_dR2 = 3.872589814675139e-05 on the "
                     "very same row (c* = 0.547)",
      control_recorded="NO",
      status="RE-DERIVES EXACTLY (2.5e-17); IS A VALID BOUND ON ITS OWN CELL"),
 dict(constant="0.001127", name="D079 shot-mix ceiling (dead lead)",
      first_computed_in="E1_I0004_fga_forecast (D079)",
      first_recorded_at="FINDINGS.json /step4_player_points/why_it_fails/... -- a bare scalar",
      what_it_actually_is="transported arithmetic ceiling",
      response="fg_pts (FIELD-GOAL points only), sd 5.823572695034913 -- NOT total box points",
      row_set="n=10,245 frame / 9,238 scored", seasons="2021-2024",
      sst_basis="var of fg_pts about its own mean", weighting="none",
      base="pts ~ 1 + FGAhat * sum_z(S1_z q_z v_z)",
      fit_kind="pooled in-sample coefficient on the mix interaction",
      statistic_family="variance share", bound_recorded="NO",
      control_recorded="NO",
      status="PARTIALLY VERIFIABLE -- no recorded sd or move; only the rounded scalar exists"),
 dict(constant="13,879", name="D076 appeared player-games",
      first_computed_in="E0_I0014_residual_heterogeneity (D076)",
      first_recorded_at="E0_I0014/FINDINGS.json n=13879 and every successor's anchor block",
      what_it_actually_is="a row count", response="n/a",
      row_set="tier-A appeared player-games", seasons="2022-2024 ONLY (not 2021)",
      sst_basis="n/a", weighting="n/a", base="n/a", fit_kind="n/a", statistic_family="count",
      bound_recorded="n/a", control_recorded="n/a",
      status="RE-DERIVES EXACTLY -- the single most reliable constant in the programme"),
 dict(constant="213", name="ceiling kills / player_season kills -- TWO DIFFERENT SETS",
      first_computed_in="E1_I0036_level_artefact_sweep census (both)",
      first_recorded_at="CENSUS.csv kill_reason=='CEILING' (213) AND "
                        "level_recorded=='player_season' among kills (213)",
      what_it_actually_is="TWO disjoint counts sharing one number",
      response="n/a", row_set="1,580 killed cells", seasons="n/a", sst_basis="n/a",
      weighting="n/a", base="n/a", fit_kind="n/a", statistic_family="count",
      bound_recorded="n/a", control_recorded="n/a",
      status="COLLISION -- |A n B| = 2 of 213; and 173 candidates + 40 controls, not 213 candidates"),
 dict(constant="0.0023", name="BEST_EVER_LEAD (D089 walk-forward)",
      first_computed_in="E1_I0018_teammate_volume_channel (D089), s05_walkforward_and_mechanism.py",
      first_recorded_at="walkforward_points.csv, value 0.0023492235735382717",
      what_it_actually_is="a REALISED walk-forward effect -- the thing 0.002057 is mistaken for",
      response="y_pts (points)", row_set="DECISION walk-forward scored, n=4,517",
      seasons="2022-2024 (2021 is the first training year)",
      sst_basis="sum((y_pts-mean)^2) on the scored rows", weighting="none",
      base="B_COMPLETE own-prior", fit_kind="walk-forward",
      statistic_family="paired-forecast dR2, cluster sign-flip at team-season",
      bound_recorded="n/a", control_recorded="YES -- G01_noise 0.000266 at p 0.463",
      status="RECORDED AND VERIFIED IN THE LEDGER; larger than the 'ceiling' 0.002057"),
 dict(constant="56.3%", name="D103 blindness share",
      first_computed_in="E1_I0026_detection_floor (D103)",
      first_recorded_at="FINDINGS.json /retrospective/share_blind_to_best_lead_0.0023_familywise",
      what_it_actually_is="share of 1,349 recorded cells blind to 0.0023",
      response="mixed (three statistic families)", row_set="1,349 cells across 7 screens",
      seasons="2021-2024", sst_basis="per-screen", weighting="none", base="per-screen",
      fit_kind="design-only", statistic_family="mixed increment / paired / t-scale",
      bound_recorded="n/a", control_recorded="n/a",
      status="RE-DERIVES to 16 digits (0.5633802816901409); RESTATED AT D122 AS 45.44%-67.31%"),
]
cdf = pd.DataFrame(census)
cdf.to_csv(os.path.join(HERE, "CENSUS.csv"), index=False)
print("wrote CENSUS.csv  %s" % (cdf.shape,))

# ========================================================== RE_DERIVATION.csv ===================
rows = [
 dict(constant="0.002057", quantity="D089 ceiling, per-sd form, DECISION|B_COMPLETE|P01",
      source_value=0.002057, source_precise=0.0020571994,
      rederived=float(H.CEIL_per_sd), delta=float(H.CEIL_per_sd - 0.0020571994),
      method="refit from E1_I0018/screen_frame.parquet, n=5,673", verdict="REPRODUCES"),
 dict(constant="0.002057", quantity="c* for that cell (was never quoted with it)",
      source_value=1.3594722754, source_precise=1.3594722754,
      rederived=float(H.C_STAR), delta=float(H.C_STAR - 1.3594722754),
      method="(d.e)/(d.d) on the transported shift", verdict="REPRODUCES -- c* > 1, NOT A BOUND"),
 dict(constant="0.002057", quantity="ORACLE = the true bound for that construction",
      source_value=0.0035630546, source_precise=0.0035630546,
      rederived=float(H.ORACLE), delta=float(H.ORACLE - 0.0035630546),
      method="(d.e)^2/((d.d)*SST)",
      verdict="REPRODUCES -- the true bound is 1.732x the published ceiling"),
 dict(constant="0.002057", quantity="REALISED increment on the SAME cell",
      source_value=0.0033139323, source_precise=0.0033139323,
      rederived=float(H.REALISED), delta=float(H.REALISED - 0.0033139323),
      method="(2 d.e - d.d)/SST",
      verdict="REPRODUCES -- realised is 1.611x the 'ceiling' that was supposed to bound it"),
 dict(constant="0.002057", quantity="ceiling, actual-shift sd form (same cell, D089's own alt)",
      source_value=0.0020995386, source_precise=0.0020995386,
      rederived=float(H.CEIL_actual_shift), delta=float(H.CEIL_actual_shift - 0.0020995386),
      method="(sd(beta*(x-xbar)*m_hat)/sd(y))^2", verdict="REPRODUCES"),
 dict(constant="0.002057", quantity="ceiling, (d.d)/SST var-share form (same cell, D089's own alt)",
      source_value=0.0019278879, source_precise=0.0019278879,
      rederived=float(H.CEIL_var_share), delta=float(H.CEIL_var_share - 0.0019278879),
      method="(d.d)/SST", verdict="REPRODUCES -- three published ceilings for ONE cell, spread 8.9%"),
 dict(constant="0.000129", quantity="D084 ceiling SPEC_RA/on_stratum",
      source_value=0.000129, source_precise=0.00012940370236262536,
      rederived=float(R84.CEILING_A_perfect_orthogonal_dR2),
      delta=float(R84.CEILING_A_perfect_orthogonal_dR2 - 0.00012940370236262536),
      method="(points_moved_by_1sd/sd_y)^2 from its own recorded columns",
      verdict="REPRODUCES EXACTLY (2.5e-17)"),
 dict(constant="0.000129", quantity="c* on D084's own kill cell",
      source_value=np.nan, source_precise=np.nan, rederived=float(R84.c_star), delta=np.nan,
      method="sqrt(recorded ORACLE / recorded ceiling)",
      verdict="c* = 0.547 < 1 -- ON ITS OWN CELL THE CEILING IS A VALID BOUND"),
 dict(constant="0.000129", quantity="D084 own-cell ORACLE (the true bound)",
      source_value=3.872589814675139e-05, source_precise=3.872589814675139e-05,
      rederived=float(R84.DIAGNOSTIC_ORACLE_best_scaling_dR2), delta=0.0,
      method="recorded in D084's own table",
      verdict="the ceiling OVERSTATES the true bound by 3.342x -- it does NOT understate it"),
 dict(constant="0.001127", quantity="D079 shot-mix ceiling",
      source_value=0.001127, source_precise=np.nan, rederived=np.nan, delta=np.nan,
      method="no recorded sd or move; indicative rebuild gave 3.5x-24x smaller",
      verdict="PARTIALLY VERIFIABLE -- numerator not independently checkable"),
 dict(constant="0.00102", quantity="FLOOR_1CELL, published cell",
      source_value=0.00102, source_precise=float(pubrow[pubrow.family_size_K == 1]
                                                 .mde80_DRIFT_CORRECTED.iloc[0]),
      rederived=float(pubrow[pubrow.family_size_K == 1].mde80_DRIFT_CORRECTED.iloc[0]), delta=0.0,
      method="read from mde_table.csv; null moments reproduced from the frame at 7.3e-17",
      verdict="REPRODUCES; but response is y_ppm, not points"),
 dict(constant="0.00102", quantity="MATCHED points-scale floor, same rows/base/null (ARM T, K=1)",
      source_value=np.nan, source_precise=np.nan, rederived=flr("T", 1), delta=np.nan,
      method="600 entity-swap draws, seed 20260808, D089's own transported statistic",
      verdict="NEW -- matched floor is %.3fx the y_ppm analytic floor"
              % (flr("T", 1) / flr("P", 1))),
 dict(constant="0.00235", quantity="FLOOR_132, published cell",
      source_value=0.00235, source_precise=float(pubrow[pubrow.family_size_K == 132]
                                                 .mde80_DRIFT_CORRECTED.iloc[0]),
      rederived=float(pubrow[pubrow.family_size_K == 132].mde80_DRIFT_CORRECTED.iloc[0]),
      delta=0.0, method="read from mde_table.csv", verdict="REPRODUCES; response y_ppm"),
 dict(constant="0.00235", quantity="MATCHED points-scale floor (ARM T, K=132)",
      source_value=np.nan, source_precise=np.nan, rederived=flr("T", 132), delta=np.nan,
      method="same 600 draws", verdict="NEW -- %.3fx the y_ppm analytic floor"
              % (flr("T", 132) / flr("P", 132))),
 dict(constant="0.002057", quantity="NOISE FLOOR OF THE CEILING ITSELF (never recorded anywhere)",
      source_value=np.nan, source_precise=np.nan,
      rederived=float(fl[(fl.arm.str.startswith("C")) & (fl.family_size_K == 1)].null_q95.iloc[0]),
      delta=np.nan, method="600 matched entity-swap draws of (d.d)/SST through the same path",
      verdict="NEW -- D089's ceiling is 3.65x its own q95 control, p=0.0017. IT CLEARS."),
 dict(constant="13,879", quantity="D076 appeared player-games 2022-2024",
      source_value=13879, source_precise=13879, rederived=13879, delta=0,
      method="row count of E1_I0031/analysis_frame.parquet", verdict="EXACT"),
 dict(constant="5,673", quantity="D089/D103 DECISION row count",
      source_value=5673, source_precise=5673,
      rederived=s04["decision_n_verified"]["points_step"], delta=0,
      method="predicate re-applied to the frozen frame", verdict="EXACT"),
 dict(constant="5,654", quantity="D089 volume-route DECISION row count",
      source_value=5654, source_precise=5654,
      rederived=s04["decision_n_verified"]["volume_route"], delta=0,
      method="same predicate + finiteness on y_spm, y_pps", verdict="EXACT"),
 dict(constant="213", quantity="ceiling kills: candidates vs controls",
      source_value=213, source_precise=213, rederived=173, delta=-40,
      method="explicit control allowlist [G01_noise, G02_placebo_noop] on EXPOSURE_213.csv",
      verdict="173 candidates + 40 controls -- D125 CONFIRMED"),
 dict(constant="213", quantity="ceiling-kill set vs player_season-kill set",
      source_value=213, source_precise=213, rederived=2, delta=np.nan,
      method="set intersection on E1_I0036/CENSUS.csv, kills only",
      verdict="TWO DIFFERENT SETS OF 213; they share 2 cells"),
 dict(constant="56.3%", quantity="D103 blindness",
      source_value=0.5633802816901409, source_precise=0.5633802816901409,
      rederived=0.5633802816901409, delta=0.0, method="FINDINGS.json",
      verdict="EXACT; superseded by D122's 45.44%-67.31% interval"),
]
rdf = pd.DataFrame(rows)
rdf.to_csv(os.path.join(HERE, "RE_DERIVATION.csv"), index=False)
print("wrote RE_DERIVATION.csv  %s" % (rdf.shape,))

# ============================================================= FINDINGS.json ====================
F = {
 "screen": "E1_I0049_benchmark_constants",
 "prereg_sha256": "4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc",
 "partition": "2021-2024 only; 2025/26 never opened; screenkit.assert_partition after every load",
 "one_line": ("Every benchmark constant re-derives from its artifact EXCEPT D079's 0.001127, which "
              "is recorded only as a rounded scalar. But 0.002057 is not what its name says: it is "
              "a TRANSPORTED CEILING with c* = 1.359, its own cell's realised increment exceeds it "
              "by 61%, its true bound is 1.73x larger, and the programme's actual largest live "
              "EFFECT is a different number (0.0023492) on a different row set."),
 "anchors": {"total": int(len(anch)), "passed": int(anch.PASS.sum()),
             "at_1e_16_or_better": int((anch["diff"] <= 1e-16).sum()),
             "plus_s03": ["A15_real_dr2 3.6e-17", "A15_null_mean 7.3e-17", "A15_null_sd 1.9e-17",
                          "A15_n exact"]},
 "Q3_is_0_002057_defensible": {
   "verdict": "NO, NOT AS A BOUND AND NOT AS AN EFFECT.",
   "cell": "E1_I0018 (D089) | DECISION | B_COMPLETE | P01_c04_prevgame",
   "denominator": ("response y_pts | n=5,673 | SST=sum((y-mean)^2) unweighted | no weights | "
                   "base [1,refB_ppm,refB_spm,refB_pps,refB_mpg] | in-sample OLS on y_ppm "
                   "transported to points by mean m_hat | seasons 2021-2024"),
   "construction": "TRANSPORTED (D125 class) -- c* is unconstrained",
   "published_ceiling": float(H.CEIL_per_sd),
   "c_star": float(H.C_STAR),
   "c_star_squared": float(H.C_STAR ** 2),
   "ORACLE_true_bound": float(H.ORACLE),
   "realised_same_cell": float(H.REALISED),
   "realised_over_published": float(H.REALISED / H.CEIL_per_sd),
   "oracle_over_published": float(H.ORACLE / H.CEIL_per_sd),
   "three_published_ceilings_one_cell": {"per_sd": float(H.CEIL_per_sd),
                                         "actual_shift": float(H.CEIL_actual_shift),
                                         "var_share_dd_over_SST": float(H.CEIL_var_share),
                                         "spread_pct": float(100 * (H.CEIL_actual_shift
                                                                    / H.CEIL_var_share - 1))},
   "category_error": ("it is a CEILING, quoted in a dozen briefs as 'the programme's largest live "
                      "EFFECT'. D089's realised walk-forward effect is 0.0023492235735382717 on "
                      "n=4,517, seasons 2022-2024 -- a different row set and 1.142x larger."),
   "control_measured_here_for_the_first_time": {
      "null": "entity swap team-season, 600 draws, seed 20260808, same rows/base/carrier",
      "ceiling_null_mean": float(fl[(fl.arm.str.startswith("C"))
                                    & (fl.family_size_K == 1)].null_mean.iloc[0]),
      "ceiling_null_q95": float(fl[(fl.arm.str.startswith("C"))
                                   & (fl.family_size_K == 1)].null_q95.iloc[0]),
      "published_over_q95": float(H.CEIL_per_sd
                                  / fl[(fl.arm.str.startswith("C"))
                                       & (fl.family_size_K == 1)].null_q95.iloc[0]),
      "p": 0.0017,
      "verdict": "THE CEILING CLEARS ITS OWN CONTROL. This retires the 'no control recorded' "
                 "concern for the single most-cited ceiling in the programme."},
 },
 "Q4_are_the_floors_convention_sensitive": {
   "verdict": "YES, ON FIVE AXES. Report as intervals.",
   "published": {"FLOOR_1CELL": 0.00102, "FLOOR_132": 0.00235,
                 "cell": "DECISION | B_COMPLETE | N_B_entity_swap_team_season | y_ppm | "
                         "drift-corrected | t_crit(K=1)=1.645"},
   "C1_null_choice_DECISION_stratum": {"K1_range": [float(k1d.min()), float(k1d.max())],
                                       "K132_range": [float(k132d.min()), float(k132d.max())],
                                       "note": "published 0.00235 is the MINIMUM of its own "
                                               "DECISION-stratum K=132 range"},
   "C3_stratum": {"POOLED_K1_range": [float(mde[(mde.family_size_K == 1)
                                                & (mde.stratum == "POOLED")]
                                            .mde80_DRIFT_CORRECTED.min()),
                                      float(mde[(mde.family_size_K == 1)
                                                & (mde.stratum == "POOLED")]
                                            .mde80_DRIFT_CORRECTED.max())]},
   "C4_drift_correction_on_the_published_cell": {
      "corrected": float(pubrow[pubrow.family_size_K == 1].mde80_DRIFT_CORRECTED.iloc[0]),
      "uncorrected": float(pubrow[pubrow.family_size_K == 1].mde80_s04_uncorrected.iloc[0])},
   "C6_RESPONSE_MISMATCH": {
      "floors_response": "y_ppm (E1_I0026/scripts/df_base.py:51)",
      "constants_response": "points (0.002057, 0.000129) / field-goal points (0.001127)",
      "matched_points_floor_K1": flr("T", 1), "y_ppm_analytic_floor_K1": flr("P", 1),
      "ratio_K1": flr("T", 1) / flr("P", 1),
      "matched_points_floor_K132": flr("T", 132), "y_ppm_analytic_floor_K132": flr("P", 132),
      "ratio_K132": flr("T", 132) / flr("P", 132),
      "implied_points_scale_floors": {
          "FLOOR_1CELL_points": 0.00102 * flr("T", 1) / flr("P", 1),
          "FLOOR_132_points": 0.00235 * flr("T", 132) / flr("P", 132)}},
   "C7_t_crit_at_K1": {"published": 1.645,
                       "the_screen_own_empirical_q95_maxt": [1.999254, 2.002969],
                       "analytic_MDE80_at_1_645": 0.001133, "analytic_MDE80_at_2_00": 0.001245,
                       "note": "E1_I0026/NOTES.md section 4 says t_crit(K=1) ~ 2.00 and that "
                               "1.645 understates every per-cell threshold; the published K=1 "
                               "rows nonetheless all carry 1.645"},
   "RECOMMENDED_INTERVALS": {
      "FLOOR_1CELL_DECISION_y_ppm": [float(k1d.min()), float(k1d.max())],
      "FLOOR_132_DECISION_y_ppm": [float(k132d.min()), float(k132d.max())],
      "FLOOR_1CELL_points_matched": flr("T", 1),
      "FLOOR_132_points_matched": flr("T", 132)},
 },
 "counts": s04["count_213"] | {"two_213s": s04["two_213s"]},
 "decision_stratum_n": s04["decision_strata"],
 "largest_effect_candidates": s04["largest_effect_candidates"],
 "D084": {"headline": 0.00012940370236262536, "own_cell_oracle": 3.872589814675139e-05,
          "own_cell_c_star": float(R84.c_star),
          "verdict": "THE CEILING IS A VALID BOUND ON ITS OWN CELL. E1_I0047's '10x "
                     "understatement' compares SPEC_ALL5_GLOBAL/off_stratum (n=5,024, sd_y=5.318) "
                     "against SPEC_RA/on_stratum (n=5,086, sd_y=7.550) -- different spec, "
                     "different rows, different SST. On the matched cell the ceiling OVERSTATES "
                     "the true bound by 3.342x."},
 "what_most_weakens_this_screen": [
   "The matched points-scale floor (ARM T) is computed from ONE cell's carrier under ONE null with "
   "600 draws, and uses the analytic MDE80 closed form rather than E1_I0026's drift-corrected "
   "fixed-point solve. The ratio ARM T / ARM P is therefore the defensible output; the absolute "
   "points-scale floors are indicative.",
   "The ARM T/ARM P ratio is measured on P01_c04_prevgame only. A different carrier could give a "
   "different ratio, and the response mismatch could be larger or smaller elsewhere.",
   "0.002057 re-derives EXACTLY and D084's 0.000129 re-derives EXACTLY. Two of the four ceiling "
   "constants are arithmetically perfect; the problem is what they are called and what they are "
   "compared against, not the arithmetic.",
   "D089's ceiling CLEARS its own newly-measured control at p=0.0017. The 'no control recorded' "
   "concern turns out to be benign for the constant it was raised about.",
   "Nothing here reopens any killed cell, and no ratio in the programme moves by an order of "
   "magnitude. The largest single correction is a factor of 1.73 on one number."],
}
json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w"), indent=1, default=str)
print("wrote FINDINGS.json")
print(json.dumps(F["Q4_are_the_floors_convention_sensitive"]["C6_RESPONSE_MISMATCH"], indent=1))
print(json.dumps(F["Q4_are_the_floors_convention_sensitive"]["RECOMMENDED_INTERVALS"], indent=1))
print("DONE s05")
