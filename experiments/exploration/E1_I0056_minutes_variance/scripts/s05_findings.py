"""S05 -- assemble FINDINGS.json from the stage artifacts.  Computes nothing new."""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(HERE, "scripts")


def L(name):
    p = os.path.join(S, name)
    return json.load(open(p)) if os.path.exists(p) else {}


s1, s2, s3, s4 = L("_s01.json"), L("_s02.json"), L("_s03.json"), L("_s04.json")
pre = open(os.path.join(HERE, "PREREG.md"), "rb").read()
pre_hash = hashlib.sha256(pre).hexdigest()
declared = open(os.path.join(HERE, "PREREG.sha256")).read().split()[0]
assert pre_hash == declared, "PREREG.md no longer matches PREREG.sha256"

PRED = [
    ("P1", "minutes pred_sd has exactly 1 distinct value per season on the shipped parquet",
     s1.get("P1")),
    ("P2", "minutes q75/q50 offsets have exactly 1 distinct value per season", s1.get("P2")),
    ("P3", "all q05 row-variation is deterministic clipping at the support floor", s1.get("P3")),
    ("P4", "VLEV anchor reproduces to 1e-6", s1.get("P4")),
    ("P5", "VSIG anchor reproduces (R2 1e-4, decile ratio 2e-3)", s1.get("P5")),
    ("P6", "strongest level-only reference L5 reaches OOF R2 >= 0.030", s2.get("P6")),
    ("P7", "dR2(C5 over L5) > 0", s2.get("P7")),
    ("P8a", "dR2(C1 over L1) >= 0.015", s2.get("P8a")),
    ("P8b", "dR2(C5 over L5) >= 0.010", s2.get("P8b")),
    ("P9", "cyclic within-player-season null p < 0.05", s2.get("P9")),
    ("P10", "p(plain shuffle) <= p(cyclic)  [D093 direction]", s2.get("P10")),
    ("P11", "noise control |mean dR2| < 0.002 and Type-I <= 0.10", s2.get("P11")),
    ("P12", "abstention: drop top 30% by C5 -> MAE reduction >= 8%", s3.get("P12")),
    ("P13", "no conversion to a better minutes LEVEL forecast", s3.get("P13")),
    ("P14", "increment > 0 on the second response refabs_minutes", s3.get("P14")),
    ("P15", "detection rate >= 0.80 at an injected dR2 of ~0.010", s3.get("P15")),
    ("P16", "median within-player-season lag-1 acf of block N >= 0.20", s2.get("P16")),
]
res = [dict(id=i, statement=t, outcome=("HELD" if v is True else
                                        "FAILED" if v is False else "NOT_RUN"))
       for i, t, v in PRED]
nheld = sum(r["outcome"] == "HELD" for r in res)
nfail = sum(r["outcome"] == "FAILED" for r in res)

lad = pd.read_csv(os.path.join(HERE, "REFERENCE_LADDER.csv")).set_index("arm")
best = s2.get("best_level")
Z = np.load(os.path.join(HERE, "raw", "s02_nulls.npz"), allow_pickle=True)
noise_sd = float(np.std(Z["noise_dr2"], ddof=1))
cyc_sd = float(np.std(Z["cyclic"], ddof=1))
sd_above_noise = (s2["dr2_over_L5"] - s2["noise_mean_dr2"]) / noise_sd
sd_above_cyclic = (s2["dr2_over_L5"] - s2["null_cyclic_mean"]) / cyc_sd

F = {
    "screen": "E1_I0056_minutes_variance",
    "evidence_level": "E1",
    "claiming": False,
    "prereg_sha256": pre_hash,
    "response_primary": "absres_minutes (realised |error| of the SHIPPED minutes point forecast)",
    "response_replication": "refabs_minutes (|error| of the strictly-prior trailing-mean forecast)",
    "stratum": "A4_CLEAN_DEC = season>=2023 & pl_games_prior>=8 & pl_min_mean5>=24",
    "n_rows": s2.get("n_scored"), "n_total_rows": 3549,
    "n_player_season_blocks": s2.get("n_blocks"), "n_team_games": 848,
    "SST": s2.get("SST"), "scheme": "walk-forward, 138 folds, MIN_TRAIN=600",
    "convention": "plain unweighted R2; SST about the unweighted mean; shared SST for every dR2",

    "Q1_the_defect": {
        "verdict": "CONFIRMED ON BYTES. The shipped per-row uncertainty is a PER-SEASON CONSTANT.",
        "pred_sd_distinct_values_per_season": 1,
        "minutes_pred_sd_by_season": {"2022": 6.710391139367, "2023": 5.934714400560,
                                      "2024": 6.037461772357},
        "all_three_targets_constant": True,
        "quantiles": ("pred_q50 and pred_q75 are pred_point plus a single per-season offset; the "
                      "only per-row variation in pred_q05/pred_q95 is deterministic clipping at "
                      "the [0, 48] support, reproduced to <= 3.6e-15"),
        "dispersion_method_decided_on_values": "empirical (off_q75 != z75*sd, off_q50 != 0)",
        "emitting_code": {
            "scalar_computed": "cbs_v5.py:169-180  dispersion() -> a single float sd per fold",
            "scalar_broadcast": ("cbs_player_runner_v14.py:313  "
                                 "pd.Series(sd_v, index=test.index)  <-- THE LINE"),
            "same_construction_in": ["cbs_v8.py:965", "cbs_v8.py:1134", "cbs_v7.py:1428",
                                     "cbs_v7.py:1603"],
            "arm_path": ("run_player_oof_v15.py -> cbs_player_runner_v15 (forks cbs_v14._run at "
                         "one identity line) -> cbs_player_runner_v14.run_player_fold (unforked)"),
        },
        "consequence": ("the incumbent variance model cannot have positive out-of-fold R2 by "
                        "construction: it is an intercept with extra steps. Measured "
                        + "%+.6f." % float(lad.loc["VSD", "oof_r2"])),
        "s00_label_was_accurate": True,
    },

    "Q2_the_increment": {
        "reference_ladder_oof_r2": {k: float(lad.loc[k, "oof_r2"])
                                    for k in ["L0", "L1", "L2", "L3", "L4", "L5"]},
        "reference_ladder_decile_ratio": {k: float(lad.loc[k, "decile_ratio"])
                                          for k in ["L0", "L1", "L2", "L3", "L4", "L5"]},
        "strongest_level_rung": best,
        "reference_spread_T4": s2.get("level_spread"),
        "candidate_arms": {k: {"oof_r2": float(lad.loc[k, "oof_r2"]),
                               "decile_ratio": float(lad.loc[k, "decile_ratio"]),
                               "calib_slope": float(lad.loc[k, "calib_slope"]),
                               "n_features": int(lad.loc[k, "n_features"])}
                           for k in ["C1", "C5", "NONLY", "C5X", "VSIG", "VSD"]},
        "dr2_over_L1_the_D134_reference": s2.get("dr2_over_L1"),
        "dr2_over_L5_PREREGISTERED_PRIMARY": s2.get("dr2_over_L5"),
        "dr2_over_strongest_level_rung": s2.get("dr2_over_best"),
        "block_bootstrap_ci_95_over_L5": s2.get("boot_ci"),
        "block_bootstrap_frac_le_zero": s2.get("boot_frac_le0"),
        "signflip_p_player_season": s2.get("signflip_p_playerseason"),
        "signflip_p_team_game": s2.get("signflip_p_teamgame"),
        "signflip_z_player_season": s2.get("signflip_z_playerseason"),
        "cyclic_null_p": s2.get("p_cyclic"),
        "cyclic_null_mean": s2.get("null_cyclic_mean"),
        "cyclic_null_sd": s2.get("null_cyclic_sd"),
        "shuffle_null_p": s2.get("p_shuffle"),
        "null_width_ratio_shuffle_over_cyclic": s2.get("null_width_ratio"),
        "noise_control_mean_dr2": s2.get("noise_mean_dr2"),
        "noise_control_typeI": s2.get("noise_typeI"),
        "vacuity_control_sd": s2.get("vacuity_sd"),
        "control_is_not_vacuous": s2.get("control_not_vacuous"),
        "median_acf1_of_block_N": s2.get("acf_median"),
        "grouping_level_status": s2.get("grouping_level", {}).get("status"),
        "signflip_is_uncalibrated_here": True,
        "signflip_typeI_on_noise": s2.get("noise_typeI"),
        "noise_control_sd_dr2": noise_sd,
        "observed_sd_above_noise_placebo": float(sd_above_noise),
        "observed_sd_above_cyclic_null": float(sd_above_cyclic),
        "decomposition_of_the_increment": {
            "destroys_everything_36_iid_columns": s2.get("noise_mean_dr2"),
            "destroys_only_within_player_season_timing": s2.get("null_cyclic_mean"),
            "destroys_nothing_the_real_block": s2.get("dr2_over_L5"),
            "reading": ("essentially all of the increment is CROSS-SECTIONAL (which player-season "
                        "the row belongs to); essentially none of it is temporal"),
        },
        "POSTHOC_reference_incompleteness_is_established": {
            "note": "NOT PREREGISTERED. Added after the ladder was seen. s04_posthoc_power.py.",
            "dr2_L4_over_L1": s4.get("dr2_L4_over_L1"),
            "bootstrap_ci": s4.get("boot_ci_L4_over_L1"),
            "bootstrap_frac_le_zero": s4.get("boot_frac_le0_L4_over_L1"),
            "signflip_p_UNCALIBRATED": s4.get("signflip_p_L4_over_L1"),
            "dr2_L5_over_L1": s4.get("dr2_L5_over_L1"),
        },
    },

    "Q3_is_it_worth_anything": {
        "abstention_drop30_mae_reduction_C5": s3.get("abst_c5_drop30"),
        "abstention_drop30_mae_reduction_level_only": s3.get("abst_level_drop30"),
        "full_sample_mae_minutes": s3.get("base_mae"),
        "intervals": s3.get("intervals"),
        "conversion_arms": s3.get("conversion"),
        "level_reference_r2_on_y_minutes": s3.get("level_ref_r2"),
        "replication": s3.get("replication"),
    },

    "power": {
        "preregistered_iid_injection": s3.get("power_rows"),
        "mde_dr2_at_80pct_power_iid": s3.get("mde_dr2_at_80pct"),
        "posthoc_clustered_injection_NOT_PREREGISTERED": s4.get("rows"),
        "mde_dr2_at_80pct_power_clustered_POSTHOC": s4.get("mde_dr2_at_80pct_clustered"),
    },

    "D131_budget_disclosure": {
        "note": ("dispersion only, never a mean. The primary response does not sum; this is "
                 "reported because the brief requires it of any minutes work."),
        "realised": s1.get("budget_ysum"),
        "shipped_forecast": s1.get("budget_psum"),
    },

    "T1_imputation_exposure": {
        "inherited_rule": "_common._impute_by_season -- season median over the WHOLE season",
        "rows_affected": s1.get("imputation_fills_prior"),
        "primary_arms_use": "strictly-prior expanding median",
        "max_abs_difference_between_the_two_rules": s1.get(
            "imputation_max_abs_diff_vs_season_median"),
        "why_it_is_zero": ("the 385 unjoined rows are exactly the postseason and fall strictly "
                           "after every joined row, so the expanding prior median has already "
                           "converged to the season median. Verified, not assumed."),
    },

    "predictions": res,
    "n_predictions": len(res), "n_held": nheld, "n_failed": nfail,
    "prediction_numbering_note": ("PREREG.md numbers 16 predictions; P8 has two parts (P8a, P8b), "
                                  "so 17 statements are tested."),
    "nothing_revised_after_seeing_a_result": True,
}
json.dump(F, open(os.path.join(HERE, "FINDINGS.json"), "w"), indent=2, default=str)
print("wrote FINDINGS.json  --  %d predictions, %d HELD, %d FAILED" % (len(res), nheld, nfail))
for r in res:
    print("  %-4s %-8s %s" % (r["id"], r["outcome"], r["statement"]))
