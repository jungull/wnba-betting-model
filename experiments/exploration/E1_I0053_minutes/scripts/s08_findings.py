"""s08 -- FLOORS, CONCENTRATION, AND FINDINGS.json.

s07 showed the only surviving cell collapses to -0.000408 when 120 rows are removed.  This step
measures exactly what those rows are, whether there are enough blocks for the null to reject at
all, and assembles the floor table and FINDINGS.json.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mn_base as A                                                    # noqa: E402

A.hdr("s08 FLOORS + CONCENTRATION + FINDINGS   PREREG sha256 %s" % A.prereg_sha())
d = pd.read_parquet(os.path.join(A.SCR, "_frame.parquet"))
A.assert_partition(d, "cached frame", verbose=True)
season = d["season"].to_numpy()
dm = A.decision_mask(d)
clean = np.isin(season, A.CLEAN_EVAL_SEASONS)
m = dm & clean
x = d["C1_player_rest"].to_numpy(float)
y = d["R1_min"].to_numpy(float)

A.hdr("1. WHERE THE ONLY SURVIVING EFFECT ACTUALLY LIVES")
conc = []
for thr in [4, 6, 8, 12]:
    sel = m & (x >= thr)
    conc.append(dict(threshold_days=thr, n_rows=int(sel.sum()),
                     pct_of_decision_stratum=100.0 * sel.sum() / m.sum(),
                     n_team_game_blocks=int(d.loc[sel, "tg"].nunique()),
                     n_players=int(d.loc[sel, "player_id"].nunique()),
                     n_dates=int(d.loc[sel, "game_date"].nunique()),
                     n_rows_2023=int((sel & (season == 2023)).sum()),
                     n_rows_2024=int((sel & (season == 2024)).sum()),
                     mean_minutes=float(y[sel].mean()),
                     mean_minutes_rest_of_stratum=float(y[m & ~(x >= thr)].mean())))
    c = conc[-1]
    print("  rest >= %2d days: n=%4d (%.2f%% of 3,167) in %3d blocks, %3d players, %3d dates "
          "| 2023 %3d / 2024 %3d | mean minutes %.3f vs %.3f elsewhere"
          % (thr, c["n_rows"], c["pct_of_decision_stratum"], c["n_team_game_blocks"],
             c["n_players"], c["n_dates"], c["n_rows_2023"], c["n_rows_2024"],
             c["mean_minutes"], c["mean_minutes_rest_of_stratum"]))
pd.DataFrame(conc).to_csv(os.path.join(A.OUT, "CONCENTRATION.csv"), index=False)

A.hdr("2. POWER FLOORS -- all on THIS screen's response, rows, SST and null")
P = pd.read_csv(os.path.join(A.OUT, "PRIMARY_CELLS.csv"))
INJ = pd.read_csv(os.path.join(A.OUT, "INJECTION_POWER.csv"))
floors = []
for cand in ["C1_player_rest", "C7_sched_density", "G01_noise"]:
    sub = INJ[INJ["candidate"] == cand].sort_values("theta_minutes_per_sd")
    pw = sub["power_at_alpha_05"].to_numpy()
    th = sub["theta_minutes_per_sd"].to_numpy()
    rc = sub["mean_recovered_dR2"].to_numpy()
    theta80 = np.nan
    for i in range(1, len(pw)):
        if pw[i - 1] < 0.80 <= pw[i]:
            theta80 = th[i - 1] + (0.80 - pw[i - 1]) / (pw[i] - pw[i - 1]) * (th[i] - th[i - 1])
            break
    lin = np.nan
    for i in range(1, len(pw)):
        if pw[i - 1] < 0.80 <= pw[i]:
            lin = rc[i - 1] + (0.80 - pw[i - 1]) / (pw[i] - pw[i - 1]) * (rc[i] - rc[i - 1])
            break
    quad = rc[-1] * (theta80 / th[-1]) ** 2 if np.isfinite(theta80) else np.nan
    row = P[(P.grid == "PRIMARY") & (P.arm == "FROZEN") & (P.candidate == cand)]
    obs = float(row["dR2"].iloc[0]) if len(row) else np.nan
    floors.append(dict(candidate=cand, observed_frozen_dR2=obs,
                       theta80_minutes_per_sd=theta80,
                       floor_injection_linear_interp=lin,
                       floor_injection_quadratic_from_theta1=quad,
                       floor_analytic_2p80_null_sd=float(row["MDE80_analytic"].iloc[0])
                       if len(row) else np.nan,
                       floor_block_bootstrap=float(row["boot_MDE80"].iloc[0]) if len(row) else np.nan,
                       ratio_vs_injection_conservative=obs / max(lin, quad)
                       if np.isfinite(quad) else np.nan,
                       ratio_vs_bootstrap=obs / float(row["boot_MDE80"].iloc[0]) if len(row) else np.nan))
    f = floors[-1]
    print("  %-18s observed %+.6f | theta80 %.4f | floors: injection lin %.6f / quad %.6f, "
          "analytic %.6f, bootstrap %.6f | x conservative injection %.2f | x bootstrap %.2f"
          % (cand, f["observed_frozen_dR2"], f["theta80_minutes_per_sd"],
             f["floor_injection_linear_interp"], f["floor_injection_quadratic_from_theta1"],
             f["floor_analytic_2p80_null_sd"], f["floor_block_bootstrap"],
             f["ratio_vs_injection_conservative"], f["ratio_vs_bootstrap"]))
pd.DataFrame(floors).to_csv(os.path.join(A.OUT, "POWER_FLOORS.csv"), index=False)

A.hdr("3. FINDINGS.json")
anch = pd.read_csv(os.path.join(A.OUT, "ANCHORS.csv"))
ref = pd.read_csv(os.path.join(A.OUT, "REFERENCE_WORTH.csv"))
cei = pd.read_csv(os.path.join(A.OUT, "CEILING.csv"))
rob = pd.read_csv(os.path.join(A.OUT, "ROBUSTNESS.csv"))
bud = pd.read_csv(os.path.join(A.OUT, "BUDGET_DECOMPOSITION.csv"))
nc = pd.read_csv(os.path.join(A.OUT, "NULL_CENTRE.csv"))
ti = pd.read_csv(os.path.join(A.OUT, "TYPE_I_NONCIRCULAR.csv"))
tr = pd.read_csv(os.path.join(A.OUT, "TRANSLATION.csv"))
bt = pd.read_csv(os.path.join(A.OUT, "BUDGET_TIGHTNESS.csv"))


def refrow(bench, pop="DECISION_CLEAN_2023_24"):
    q = ref[(ref.response == "R1_min") & (ref.projection == "RAW") & (ref.population == pop) &
            (ref.benchmark == bench)]
    return q.iloc[0].to_dict()


def prim(cand, arm="FROZEN"):
    return P[(P.grid == "PRIMARY") & (P.arm == arm) & (P.candidate == cand)].iloc[0].to_dict()


F = {
    "screen": "E1_I0053_minutes",
    "prereg_sha256": A.prereg_sha(),
    "partition": "2021-2024 regular season only; 2025/26 never opened",
    "denominator": {
        "response": "R1_min = minutes (LEVEL); secondary R2_smin = minutes/T_min (SHARE)",
        "row_set": "DECISION (n_prior>=8 AND prior5_minutes>=24) x eval seasons 2023-2024",
        "n": 3167, "n_team_game_blocks": 764, "n_players": 113,
        "sst_basis": "sum((y-ybar)^2) about the unweighted mean, on the 3,167 scored rows",
        "sst_value_minutes_squared": 132506.769701,
        "weighting": "none",
        "base": "[1, B_TUNED]; B_TUNED = shrunken EWMA of own prior minutes, h=3 k=1 selected "
                "by SSE on decision-stratum rows from strictly earlier seasons only",
        "fit_kind": "walk-forward (eval 2023 trains on <=2022, eval 2024 on <=2023)",
        "statistic": "paired-forecast dR2 with shared SST = (SSE_base - SSE_aug)/SST",
        "primary_arm": "RAW -- the 200-minute constraint is UNENFORCED and this is declared",
    },
    "anchors": {"n_reproduced": int(len(anch)), "n_exact_zero": int((anch.abs_diff == 0).sum()),
                "n_failed": int((~anch.PASS).sum()),
                "includes": "E1_I0046 minutes-share tuned/naive/uniform R2 reproduced bit-exactly "
                            "for eval 2022, 2023 and 2024 by an independent reimplementation"},
    "Q_what_is_the_tuning_alone_worth": {
        "vs_untuned_EWMA_h5": refrow("NAIVE"),
        "vs_literal_trailing5_mean": refrow("TRAIL5"),
        "vs_uniform_split": refrow("UNIFORM"),
        "disclosed_2022_vs_NAIVE": refrow("NAIVE", "DECISION_DISCLOSED_2022"),
        "pooled_all_appeared_vs_NAIVE": refrow("NAIVE", "ALL_APPEARED_CLEAN_2023_24"),
        "verdict": "tuning is worth +0.016456 over an untuned EWMA and +0.050624 over the literal "
                   "trailing-5 mean; the best candidate anywhere in this screen is +0.006644, so "
                   "the tuning alone is worth 2.5x to 7.6x the best candidate",
    },
    "ceiling": {
        "family_oracle_8_real_candidates": 0.025831946458381935,
        "df_cost_K_over_n": 0.0025260498894853173,
        "family_oracle_df_corrected": 0.023305896568896617,
        "largest_single": {"candidate": "C1_player_rest", "oracle_dR2": 0.009455,
                           "c_star": -0.629152, "is_a_bound": True},
        "matched_controls": {"G01_noise_within_tg": 0.000032, "G02_tg_noise_tg_constant": 0.000167},
        "programme_floors": "NOT_COMPARABLE under D101: 0.00102/0.00235 are y_ppm, 0.002057 is a "
                            "ceiling with c*=1.359 (not a bound), 0.0023492 is on points n=4,517. "
                            "This screen's response is minutes. Own floors used throughout.",
    },
    "decision_stratum_result": {
        "surviving_cell": "C1_player_rest / R1_min / RAW / DECISION / 2023-24",
        "FROZEN": prim("C1_player_rest", "FROZEN"),
        "UNFROZEN": prim("C1_player_rest", "UNFROZEN"),
        "freeze_verdict": "THE FREEZE CHANGES NOTHING: +0.006644 frozen vs +0.006661 unfrozen, a "
                          "0.26% difference. The channel is an ADDITION to the tuned reference, "
                          "not a substitute for it. Contrast E1_I0046's A2: +0.005487 -> -0.004696.",
        "all_other_candidates": {c: {"FROZEN_dR2": prim(c, "FROZEN")["dR2"],
                                     "FROZEN_p": prim(c, "FROZEN")["p"],
                                     "UNFROZEN_dR2": prim(c, "UNFROZEN")["dR2"],
                                     "UNFROZEN_p": prim(c, "UNFROZEN")["p"]}
                                 for c in A.CANDIDATES if c != "C1_player_rest"},
    },
    "WHAT_KILLS_IT": {
        "concentration": conc,
        "robustness": rob.to_dict("records"),
        "statement": "Removing the 120 decision-stratum rows with rest > 7 days (3.79% of the "
                     "stratum) takes the cell from +0.006644 to -0.000408 (p 0.9920). Clipping "
                     "rest at 4 days gives +0.000053 (p 0.1129). A bare binary flag for 'rest >= "
                     "8 days' reproduces the whole effect (+0.007107). THE CANDIDATE IS NOT A "
                     "REST EFFECT. It is a RETURN-FROM-ABSENCE effect on 3.79% of the rows, and "
                     "ordinary schedule rest (1-7 days, 96.21% of the stratum) is null.",
        "shape": "mean base residual is +0.29/-0.03/+0.44/+0.37/+0.29 minutes for rest buckets "
                 "[0,2),[2,3),[3,4),[4,6),[6,8) and then -2.155 (n=44) and -4.150 (n=76) for "
                 "[8,12) and [12,22). Flat then a cliff, not a gradient.",
    },
    "budget_decomposition_answering_E1_I0051": {
        "budget_tightness_own_frame": bt.iloc[0].to_dict(),
        "contrasts": bud[bud.what.isin(["BASE_ONLY", "BASE_ONLY_REGULATION_GAMES_ONLY"])]
        .to_dict("records"),
        "headline": "THE PROJECTION GAIN IS AN OVERTIME ORACLE, NOT A BUDGET EFFECT. Renormalising "
                    "onto the RULEBOOK 200 over the realised roster is worth -0.006357 (p 0.7041). "
                    "Replacing 200 with the REALISED T_min is worth +0.034620 (p 0.0005). "
                    "Restricted to the 737 regulation-time team-game blocks (96.43% of scored "
                    "rows) the whole projection is worth -0.000061 (p 0.9970). The pre-game-"
                    "available portion of the projection gain is ZERO.",
    },
    "null_validity": {
        "null_centre_ratios": nc.to_dict("records"),
        "type_I_non_circular": ti.iloc[0].to_dict(),
        "noop_placebo_sd": 8.899e-19,
        "response_placebo": {"mean": -0.000156, "sd": 0.000360, "max": 0.000744,
                             "observed": 0.006644},
        "blind_null": "N_WITHIN_PLAYER applied to C1_player_rest inflates z from +4.70 to +12.02 "
                      "and its centre ratio is -0.1103 against +1.0232 for the matched null. "
                      "Here it inflates rather than reverses; E1_I0046 saw it reverse a sign.",
    },
    "translation_into_minutes": tr.iloc[0].to_dict(),
    "VERDICT": "NO CANDIDATE IS ESTABLISHED AS A GENERAL MINUTES SIGNAL ON THE DECISION STRATUM. "
               "Seven of eight are null in both arms. The eighth clears every preregistered bar "
               "but is confined to 120 of 3,167 rows and is a return-from-absence effect, not the "
               "schedule-rest effect it was preregistered as. The tuned reference is worth 2.5x to "
               "7.6x more than it. No production change is proposed and no champion was fitted.",
    "no_production_change": True,
    "champion_fitted": False,
}
with open(os.path.join(A.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(F, fh, indent=1, default=float)
print("  FINDINGS.json written (%d bytes)"
      % os.path.getsize(os.path.join(A.OUT, "FINDINGS.json")))
A.hdr("s08 done")
