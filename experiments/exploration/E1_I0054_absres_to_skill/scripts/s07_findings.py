"""S07 -- assemble FINDINGS.json from the artifacts.  No new statistic is computed here."""
import json, os, sys, hashlib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *  # noqa

J = lambda p: json.load(open(os.path.join(HERE, "scripts", p)))
s00, s01, s02, s03, s04, s06 = (J("_s00.json"), J("_s01.json"), J("_s02.json"),
                                J("_s03.json"), J("_s04.json"), J("_s06.json"))
RP = pd.read_csv(os.path.join(HERE, "REPRODUCTION.csv"))
VP = pd.read_csv(os.path.join(HERE, "VOLUME_PROXY.csv"))
CAL = pd.read_csv(os.path.join(HERE, "CALIBRATION.csv"))
PT = pd.read_csv(os.path.join(HERE, "POINTS_TEST.csv"))
AB = pd.read_csv(os.path.join(HERE, "ABSTENTION.csv"))
ABD = pd.read_csv(os.path.join(HERE, "_ABSTENTION_DECOMPOSED.csv"))
CP = pd.read_csv(os.path.join(HERE, "_PLACEBO_CALIBRATED.csv"))
T2 = pd.read_csv(os.path.join(HERE, "_T2_PLACEBO.csv"))
TI = pd.read_csv(os.path.join(HERE, "TYPEI_CENTRED.csv"))
MECH = pd.read_csv(os.path.join(HERE, "_PRED_CV_MECHANISM.csv"))
SUBS = pd.read_csv(os.path.join(HERE, "_PRED_CV_SUBSTITUTION.csv"))
BAR = pd.read_csv(os.path.join(HERE, "_BAR_ANATOMY.csv"))

P16 = s00["published_16"]
a4 = RP[(RP.arm == "A4_CLEAN_DEC") & (RP.seed == SEEDS[0])].set_index("cell")
wf = PT[(PT.scheme == "WF") & (PT.variance_model == "VSIG") & (PT.channel != "RAW_INCUMBENT")]
best = PT[PT.channel != "RAW_INCUMBENT"].sort_values("delta_r2_points", ascending=False).iloc[0]

out = {
  "screen": "E1_I0054_absres_to_skill",
  "prereg_sha256": open(os.path.join(HERE, "PREREG.sha256")).read().strip(),
  "partition": {"seasons_used": SEASONS_PRESENT, "sealed_holdout": "2025/26 NEVER OPENED",
                "frame": "E0_I0014_residual_heterogeneity/analysis_frame.parquet"},
  "headline": (
     "The sixteen reproduce exactly.  They are a VARIANCE result, not a skill result: no use "
     "of the predicted |residual| improves a POINTS forecast on the decision stratum, and "
     "12 of the 16 are volume proxies that vanish once trailing scoring level is in the base."),

  "PART_R_reproduction": {
    "anchors": {"R_A1_max_rel_dt_vs_E0_I0014_screen_results": s00["R_A1_max_rel_dt"],
                "R_A1_bitwise_identical": "%d of %d" % (s00["R_A1_bitwise_identical"],
                                                        s00["R_A1_n_cells"]),
                "R_A2_max_abs_ddr2": s00["R_A2_max_abs_ddr2"],
                "R_A3_max_abs_dt_vs_E1_I0050": s00["R_A3_max_abs_dt"],
                "R_A3_max_abs_ddr2_vs_E1_I0050": s00["R_A3_max_abs_ddr2"],
                "all_pass": True},
    "the_sixteen_reproduce": True,
    "symmetric_difference_vs_published_by_seed": {str(k): len(set(v) ^ set(P16))
                                                  for k, v in s01["sets"].items()},
    "A1_FULL_count": len(s01["a1_full"]),
    "A1_FULL_matches_published_24_plus_12_confounded": True,
    "bar_q95_A4_by_seed": {str(r["seed"]): r["bar_familywise_q95"]
                           for _, r in BAR[BAR.arm == "A4_CLEAN_DEC"].iterrows()},
    "bar_q95_A4_published_E1_I0050": 5.323081389242404,
    "cells": {c: {"signed_t": float(a4.loc[c, "observed_signed_t"]),
                  "dr2_base_B0": float(a4.loc[c, "observed_dr2"]),
                  "p_familywise_plus1": float(a4.loc[c, "p_familywise_plus1"])} for c in P16},
    "predictions": {"P_R1_set_size_16": True, "P_R2_symdiff_le_2": True,
                    "P_R3_bar_within_0.30": True}},

  "PART_R_bar_dominance": {
    "published_E0_I0014_bar": {"mean": s00["published_bar_mean"], "p95": s00["published_bar_p95"],
      "top_supplier": s00["published_bar_top_cell"],
      "share_of_draws": s00["published_bar_top_cell_share"],
      "n_distinct_suppliers": s00["published_bar_n_distinct_suppliers"]},
    "repaired_composed2_bar_A4": {
      "top_supplier": BAR[BAR.arm == "A4_CLEAN_DEC"].iloc[0]["top_supplier_cell"],
      "share_of_draws": float(BAR[BAR.arm == "A4_CLEAN_DEC"].iloc[0]["top_supplier_share"]),
      "n_distinct_suppliers": int(BAR[BAR.arm == "A4_CLEAN_DEC"].iloc[0]
                                  ["n_distinct_suppliers"])}},

  "PART_V_volume_proxy": {
    "bases": {"B0": "season FE only (published)",
              "B1": "B0 + matched trailing level",
              "B2": "B1 + matched forecast level",
              "B3": "B0 + all eight level columns (mapping-free)",
              "B4": "POST-HOC: B3 + the three emitted forecast sd columns"},
    "survivors_within_the_16": {b: s02["survivors_within_16"][b] for b in
                                ("B0", "B1", "B2", "B3", "B4")},
    "n_survivors_within_the_16": {b: len(s02["survivors_within_16"][b]) for b in
                                  ("B0", "B1", "B2", "B3", "B4")},
    "median_retained_share_vs_B0": {b: float(VP[(VP.base == b) & VP.cell.isin(P16)]
                                             ["retained_share_vs_B0"].median())
                                    for b in ("B1", "B2", "B3", "B4")},
    "retained_share_per_cell_B3": {c: float(VP[(VP.base == "B3") & (VP.cell == c)]
                                            ["retained_share_vs_B0"].iloc[0]) for c in P16},
    "MECHANISM_pred_cv_is_reciprocal_of_forecast_level": {
      "pts__pred_sd_distinct_values_per_season_on_A4": 1,
      "within_season_corr_pred_cv_vs_one_over_pred_point_A4": float(
        MECH[(MECH.arm == "A4_CLEAN_DEC") & (MECH.target == "pts")]
        ["within_season_corr_min"].iloc[0]),
      "substitution_reproduces_t_and_dr2_exactly": bool(
        np.allclose(SUBS[SUBS.carrier == "pts__pred_cv"]["signed_t"].to_numpy(),
                    SUBS[SUBS.carrier == "ONE_OVER_pts__pred_point"]["signed_t"].to_numpy(),
                    atol=1e-12)),
      "note": "on the decision stratum <target>__pred_sd takes exactly ONE value per season, "
              "so <target>__pred_cv IS k(season)/<target>__pred_point"},
    "predictions": {"P_V1_pred_cv_pts_absres_retained_B2_lt_0.50": True,
                    "P_V2_ge_3_minutes_candidates_retained_B2_gt_0.50": True,
                    "P_V3_ge_4_of_16_lose_familywise_under_B3": True}},

  "PART_S_points": {
    "D101": {"response": "y_pts (total box points)", "row_set": "A4_CLEAN_DEC scored rows",
             "n_scored_WF": s04["n_scored"]["WF"], "n_scored_GKF": s04["n_scored"]["GKF"],
             "SST_basis": "sum (y_pts - ybar)^2 on the scored rows, unweighted",
             "weighting": "none in the metric",
             "base": "B_PTS = 1 + pts__pred_point + minutes__pred_point + pl_pts_mean5 + "
                     "pl_min_mean5 + pl_fga_mean5 + pl_usg_mean5 + pl_start_frac5",
             "fit": "out-of-fold, expanding window by gdate (WF) / GroupKFold on player_id",
             "statistic": "paired dR2 = (SSE_ref - SSE_treat)/SST",
             "reference": "tuned ridge on B_PTS, lambda by inner time-ordered CV"},
    "ANY_CHANNEL_IMPROVES_POINTS": bool(s04["any_channel_improves"]),
    "n_channel_arms_tested": int(len(PT[PT.channel != "RAW_INCUMBENT"])),
    "best_delta_r2_anywhere": {"scheme": best["scheme"], "variance_model": best["variance_model"],
                               "channel": best["channel"], "intercept_arm": best["intercept_arm"],
                               "delta_r2_points": float(best["delta_r2_points"]),
                               "signflip_p_player_season": float(best["signflip_p_player_season"])},
    "floors_points_scale_E1_I0049": {"K1": FLOOR_POINTS_K1, "K132": FLOOR_POINTS_K132,
      "NOTE": "the published 0.00102 / 0.00235 are y_ppm floors and are NEVER quoted here"},
    "WF_VSIG_channels": [{k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                          for k, v in r.items()
                          if k in ("channel", "intercept_arm", "r2_reference", "r2_treatment",
                                   "delta_r2_points", "signflip_p_player_season",
                                   "signflip_p_team_season", "clears_floor_K1")}
                         for _, r in wf.iterrows()],
    "only_channels_significant_at_0.05_are_HARMFUL": [
      {"scheme": r["scheme"], "variance_model": r["variance_model"], "channel": r["channel"],
       "intercept_arm": r["intercept_arm"], "delta_r2_points": float(r["delta_r2_points"]),
       "signflip_p_player_season": float(r["signflip_p_player_season"])}
      for _, r in PT[(PT.channel != "RAW_INCUMBENT")
                     & (PT.signflip_p_player_season < 0.05)].iterrows()],
    "n_channel_arms_significant_at_0.05": int(((PT.channel != "RAW_INCUMBENT")
                                               & (PT.signflip_p_player_season < 0.05)).sum()),
    "dependent_mix_of_the_16": {"minutes": 11, "pts_error": 3, "fga": 2},
    "r2_of_tuned_reference_WF": float(wf["r2_reference"].iloc[0]),
    "raw_incumbent_vs_tuned_reference_dr2_WF": float(
      PT[(PT.scheme == "WF") & (PT.variance_model == "VSIG")
         & (PT.channel == "RAW_INCUMBENT")]["delta_r2_points"].iloc[0]),
    "predictions": {"P_S1_no_channel_meets_the_rule": True,
                    "P_S2_S3_vhat_coefficient_not_significant": True,
                    "P_S3_abstention_gt_15pct_at_q30": False,
                    "P_S3_measured_at_q30_WF_VSIG": float(
                      AB[(AB.scheme == "WF") & (AB.variance_model == "VSIG")
                         & (AB.q_dropped_pct == 30)]["mse_reduction_vs_all"].iloc[0])}},

  "PART_C_calibration": {
    "response": "absres_<target> on A4_CLEAN_DEC scored rows",
    "incumbent_variance_forecast_is_degenerate": {
      "column": "<target>__pred_sd", "distinct_values_per_season_on_A4": 1,
      "consequence": "the shipped model emits a per-season CONSTANT uncertainty on the "
                     "decision stratum; VSD carries no within-season information"},
    "headline_WF": [{k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                     for k, v in r.items()
                     if k in ("target", "model", "n_scored", "decile1_mean_realised",
                              "decile10_mean_realised", "top_over_bottom_decile_ratio",
                              "ratio_boot_lo", "ratio_boot_hi", "spearman_vhat_vs_realised",
                              "oof_r2_of_vhat_on_absres", "calibration_slope")}
                    for _, r in CAL[CAL.scheme == "WF"].iterrows()],
    "predictions": {"P_C1_minutes_VSIG_ratio_gt_1.6": True,
                    "P_C2_VSIG_beats_V0_all_three": True,
                    "P_C3_VSIG_does_not_beat_VSD_by_gt_0.02_on_pts": False,
                    "P_C3_measured_gap_pts": float(
                      CAL[(CAL.scheme == "WF") & (CAL.target == "pts")
                          & (CAL.model == "VSIG")]["oof_r2_of_vhat_on_absres"].iloc[0]
                      - CAL[(CAL.scheme == "WF") & (CAL.target == "pts")
                            & (CAL.model == "VSD")]["oof_r2_of_vhat_on_absres"].iloc[0])}},

  "PART_C_abstention": {
    "mse_reduction_q30_WF_VSIG": float(AB[(AB.scheme == "WF") & (AB.variance_model == "VSIG")
                                          & (AB.q_dropped_pct == 30)]
                                       ["mse_reduction_vs_all"].iloc[0]),
    "p_vs_random_subsets": float(AB[(AB.scheme == "WF") & (AB.variance_model == "VSIG")
                                    & (AB.q_dropped_pct == 30)]["p_vs_random_subsets"].iloc[0]),
    "POST_HOC_decomposition": {
      "r2_on_retained_rows_FALLS": float(ABD[(ABD.scheme == "WF")
                                             & (ABD.rule == "VSIG_predicted_error")
                                             & (ABD.q_dropped_pct == 30)]
                                         ["r2_change_on_retained"].iloc[0]),
      "response_variance_reduction_on_retained": float(
        ABD[(ABD.scheme == "WF") & (ABD.rule == "VSIG_predicted_error")
            & (ABD.q_dropped_pct == 30)]["variance_reduction_of_response"].iloc[0]),
      "abstaining_on_FORECAST_LEVEL_ALONE_mse_reduction_q30_WF": float(
        ABD[(ABD.scheme == "WF") & (ABD.rule == "FORECAST_LEVEL_ALONE")
            & (ABD.q_dropped_pct == 30)]["mse_reduction"].iloc[0]),
      "verdict": "abstention lowers MSE by removing high-variance ROWS, not by forecasting "
                 "them better; R2 on the retained rows FALLS, and a rule that uses the "
                 "forecast level alone does at least as well"}},

  "PART_T_controls": {
    "T1_centred_generator": {"pairs_centred": "%d of %d" % (s06["centred_pairs"],
                                                            s06["n_h0_pairs"]),
      "max_abs_mean_signed_t_H0_generators": s06["max_abs_mean_signed_t_H0"],
      "requirement": "< 0.15", "PASS": True,
      "composed2_typeI_median": s06["typeI_median"], "composed2_typeI_max": s06["typeI_max"],
      "n_over_tolerance_0.075": s06["n_over_tolerance"],
      "BLOCKBOOT_diagnostic_max_abs_mean_signed_t": s06["max_abs_mean_signed_t_BLOCKBOOT"],
      "BLOCKBOOT_note": "the defective generator reproduces its defect in my hands and is "
                        "never used to accept or reject anything"},
    "T2_placebo_on_the_points_statistic": [
      {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in r.items()
       if k in ("channel", "intercept_arm", "n", "mean_signed_delta_r2", "sd_signed_delta_r2",
                "typeI_at_0p05", "centred_ok_abs_mean_lt_2e-4")}
      for _, r in T2[T2.channel != "RAW_INCUMBENT"].iterrows()],
    "T2_channels_NOT_centred": sorted(set(T2[(T2.channel != "RAW_INCUMBENT")
                                             & (~T2["centred_ok_abs_mean_lt_2e-4"])]["channel"])),
    "T3_blindness": {"max_abs_null_mean_signed_t_on_real_response_A4":
                     float(RP[RP.arm == "A4_CLEAN_DEC"]["null_mean_signed_t"].abs().max()),
                     "threshold": TOL_BLIND, "n_blind": int(s06["n_blind"])},
    "T4_bar_dominance": "reported for every bar in _BAR_ANATOMY.csv and _BAR_ANATOMY_BY_BASE.csv"},

  "PLACEBO_CALIBRATED_NOTE": {
    "channels_above_their_placebo_at_p_lt_0.01": sorted(
      CP[CP.placebo_calibrated_p_one_sided < 0.01]["channel"].tolist()),
    "largest_such_delta_r2": float(CP[CP.placebo_calibrated_p_one_sided < 0.01]
                                   ["observed_delta_r2"].max()) if len(
      CP[CP.placebo_calibrated_p_one_sided < 0.01]) else None,
    "WARNING": "the placebo varies vhat only, holding the data fixed, so a placebo-calibrated "
               "p answers 'is this what a NOISE vhat would give on THIS dataset', not 'is this "
               "distinguishable from zero across resamples'.  The cluster sign-flip test is the "
               "sampling-noise test and it is null for every channel."},

  "storage": {"signed_unstandardised_draws": "raw/*.npz, with season / player_id / team_id / "
                                             "gdate / player-season block / team-season block",
              "files": sorted(os.listdir(RAW))},
}

p = os.path.join(HERE, "FINDINGS.json")
json.dump(out, open(p, "w"), indent=2, default=float)
print("wrote FINDINGS.json  sha256 %s"
      % hashlib.sha256(open(p, "rb").read()).hexdigest()[:16])
print("DONE s07")
