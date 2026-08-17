"""E1_I0046 s06 -- assemble FINDINGS.json from the frozen CSVs.  Computes no new statistic."""
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import al_base as A


def rd(name):
    return pd.read_csv(os.path.join(A.OUT, name))


def rows(df):
    return json.loads(df.to_json(orient="records"))


anch = rd("ANCHORS.csv")
cells = rd("PRIMARY_CELLS.csv")
nulls = rd("NULLS.csv")
pswap = rd("NULLS_PSWAP.csv")
fam = rd("FAMILYWISE.csv")
q1 = rd("Q1_ALLOCATION_FORECASTABLE.csv")
ceil = rd("CEILING.csv")
stab = rd("STABILITY.csv")
cw = rd("STABILITY_COUNTERWEIGHT.csv")
inj = rd("INJECTION_POWER.csv")
fl = rd("POWER_FLOORS.csv")
t1 = rd("TYPE_I_NONCIRCULAR.csv")
sub = rd("SUBSTITUTE_TEST.csv")
ss = rd("SEASON_STABILITY.csv")
bs = rd("BOOTSTRAP_VARIANCE.csv")
pl = rd("PLACEBOS.csv")
bl = rd("BLIND_NULL_DEMO.csv")
lk = rd("LEAKAGE_PROBE.csv")
cen = rd("DECISION_STRATUM.csv")
tun = rd("REFERENCE_TUNING.csv")
rpl = rd("RESPONSE_PLACEBO.csv")


def hsh(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


hd = cells[(cells.response == "R1_s_pts") & (cells.population == "DECISION") &
           (cells.projection == "PROJ") & (cells.candidate == "A2_fga_share_prior")]
n_tg = nulls[(nulls.response == "R1_s_pts") & (nulls.candidate == "A2_fga_share_prior") &
             (nulls.arm == "UNFROZEN") & (nulls.null == "N_TGSWAP")].iloc[0]
n_ps = pswap[(pswap.response == "R1_s_pts") & (pswap.candidate == "A2_fga_share_prior") &
             (pswap.arm == "UNFROZEN")].iloc[0]
b_hd = bs[(bs.response == "R1_s_pts") & (bs.candidate == "A2_fga_share_prior")].iloc[0]
f_hd = fl[(fl.response == "R1_s_pts") & (fl.candidate == "A2_fga_share_prior")].iloc[0]

out = {
    "screen": "E1_I0046_allocation",
    "question": ("Independent of absences, is the ALLOCATION of a team's scoring across its roster "
                 "forecastable at all?"),
    "prereg": {"file": "PREREG.md", "sha256": A.prereg_sha(),
               "bytes": os.path.getsize(os.path.join(A.OUT, "PREREG.md")),
               "cells_dropped_after_hash": 0,
               "cells_added_after_hash": [
                   {"id": "N_PSWAP", "what": "a second, serial-structure-preserving null",
                    "direction": "WEAKENS -- every verdict now requires TWO nulls"},
                   {"id": "SUBSTITUTE_TEST",
                    "what": "an attempts-share allocator and a 50/50 blend, as forecasts",
                    "direction": ("WEAKENS -- the implementable form of the surviving cell does NOT "
                                  "establish on the decision stratum (p 0.0870)")},
                   {"id": "TYPE_I_NONCIRCULAR",
                    "what": "type-I on 100 synthetic candidates with real serial structure",
                    "direction": "CONTROL -- it passed; had it failed the headline would have died"}]},
    "partition": {"seasons_used": [2021, 2022, 2023, 2024], "season_type": "Regular Season",
                  "clean_window_eval_seasons": A.CLEAN_EVAL_SEASONS,
                  "disclosed_contrast_eval_seasons": A.DISCLOSED_EVAL_SEASONS,
                  "2021_evaluated": False,
                  "holdout_2025_2026_opened": False,
                  "enforcement": "VALUE-level; datetime dtype only, never a name match"},
    "construction": {
        "response": "s_i = y_i / sum_{j in appeared roster} y_j  -- a COMPOSITION",
        "responses": {"R1_s_pts": "points share (PRIMARY)", "R2_s_min": "minutes share",
                      "R3_s_fga": "attempts share"},
        "simplex_asserted_to": 1e-12,
        "closure_vs_master_team": {"team_games": 1776, "max_abs_diff_points": 0.0,
                                   "max_abs_diff_attempts": 0.0,
                                   "max_abs_diff_minutes": 0.06666666666666643,
                                   "mean_roster": 9.412725225225226},
        "compositional_handling": ("within-team-game simplex projection applied identically to every "
                                   "arm and every null draw; team-game blocking; the unprojected RAW "
                                   "arm reported beside every cell as the measured cost of ignoring "
                                   "the constraint (D111)"),
        "oracles_granted": ["ORACLE TOTAL (response side only)", "ORACLE ROSTER (projection "
                            "denominator)"],
        "leakage_firewall": ("the realised total and roster enter the RESPONSE and the PROJECTION "
                             "DENOMINATOR only; no base or candidate column reads game-g data. Every "
                             "feature is an explicit .shift(1) inside (season, player_id) or "
                             "(season, team_id) ordered by (game_date, game_id).")},
    "decision_stratum": {"definition": "n_prior >= 8 AND prior5_minutes >= 24 (D081)",
                         "census": rows(cen),
                         "reported_before_pooled_everywhere": True},
    "reference": {"tuned_grid": "halflife in {2,3,5,8,13,21,EXPANDING} x k in {0,0.5,1,2,4,8} = 42",
                  "selection": "min SSE on strictly earlier seasons only, per eval season",
                  "tuning": rows(tun)},
    "Q1_is_allocation_forecastable_at_all": {"answer": "YES, emphatically", "cells": rows(q1)},
    "arithmetic_ceiling": {
        "computed_before_any_fit": True,
        "gate": "family ORACLE ceiling < 0.00102 (D103 single-cell floor) -> DO NOT FIT",
        "benchmarks": {"largest_live_effect_D089": A.LARGEST_LIVE_EFFECT,
                       "single_cell_floor_D103": A.FLOOR_SINGLE_CELL,
                       "floor_132_cell_D103": A.FLOOR_132_CELL},
        "verdict": {"R1_s_pts": "PROCEED (0.005999 = 5.88x floor)",
                    "R2_s_min": "PROCEED (0.022916 = 22.47x floor)",
                    "R3_s_fga": "PROCEED (0.005319 = 5.21x floor)"},
        "constraint_destroys_pct_of_ceiling": {"R1_s_pts/A2": 86.8, "R2_s_min/A2": 87.8,
                                               "R3_s_fga/A2": 98.4, "R3_s_fga/A4": 92.4},
        "table": rows(ceil)},
    "Q2_headline": {
        "cell": "R1_s_pts / A2_fga_share_prior / DECISION / CLEAN_2023_24 / PROJ",
        "n": 3167, "n_team_game_blocks": 764,
        "base_r2": float(hd.iloc[0]["r2_base"]),
        "dr2_UNFROZEN": float(hd[hd.arm == "UNFROZEN"].iloc[0]["dr2"]),
        "dr2_FROZEN": float(hd[hd.arm == "FROZEN"].iloc[0]["dr2"]),
        "N_TGSWAP": {"null_mean": float(n_tg["null_mean"]), "null_sd": float(n_tg["null_sd"]),
                     "z": float(n_tg["z"]), "p": float(n_tg["p"]),
                     "p_is_at_its_floor_with_2000_draws": True},
        "N_PSWAP": {"null_mean": float(n_ps["null_mean"]), "null_sd": float(n_ps["null_sd"]),
                    "z": float(n_ps["z"]), "p": float(n_ps["p"]),
                    "p_is_at_its_floor_with_600_draws": True},
        "familywise_p": 0.0004997501249375312,
        "floor_analytic_2p80_null_sd": 2.80 * float(n_tg["null_sd"]),
        "floor_injection_verified": float(f_hd["floor_injection_verified_recovered_units"]),
        "floor_bootstrap_2p80_boot_sd": 2.80 * float(b_hd["bootstrap_sd"]),
        "bootstrap_sd_over_permutation_sd": float(b_hd["bootstrap_sd"]) / float(n_tg["null_sd"]),
        "translation": {"share_sd_decision_clean": 0.08908,
                        "rms_forecast_movement_share_points": 0.006600,
                        "rms_forecast_movement_team_points": 0.5455,
                        "points_level_response_sd": 7.7415},
        "verdict": ("ESTABLISHED under both preregistered permutation nulls and the "
                    "injection-verified floor; NOT ESTABLISHED under the block-bootstrap sampling "
                    "floor (t = 2.61 against a 2.80 threshold). The implementable allocator form "
                    "(50/50 blend) does NOT establish on the decision stratum (p 0.0870). Both "
                    "figures are ORACLE ceilings."),
        "mechanism": ("points = attempts x efficiency and efficiency is mostly noise, so the "
                      "attempts share is a cleaner measurement of the same role than the points "
                      "share. The frozen/unfrozen split says it REPLACES rather than ADDS.")},
    "Q2_all_cells": rows(cells),
    "nulls": {"N_TGSWAP": rows(nulls), "N_PSWAP": rows(pswap), "familywise": rows(fam),
              "blind_null_demonstration": rows(bl),
              "note": ("A5_opp_defrtg is TEAM-GAME-CONSTANT: the within-composition swap is the "
                       "LITERAL IDENTITY for it and returns null sd 8.5e-22, exactly 0.0 in two "
                       "cells. Its verdict null is the date-blocked N_TGBLOCK.")},
    "stability_share_vs_level": {
        "answer": ("NO. Share is not materially more stable than level: the acf1 gap is between "
                   "-0.0023 and +0.0116, and on the PRIMARY response in the clean window it is "
                   "NEGATIVE (-0.0023)."),
        "mechanism": ("dividing by the team total can only remove the variance the total "
                      "contributes, and that is 4.4% (points), 2.6% (attempts) and 0.8% (minutes) "
                      "of the level's log-variance. There was never more than ~4% to remove."),
        "comparison_is_legitimate_because": ("autocorrelation and ICC are unitless, computed on "
                                             "IDENTICAL rows in identical order. No dR2/MAE is ever "
                                             "compared across responses (D101)."),
        "table": rows(stab), "counterweight": rows(cw)},
    "power": {"injection": rows(inj), "floors": rows(fl), "type_I_noncircular": rows(t1),
              "bootstrap_vs_permutation": rows(bs),
              "block_counts": {"N_TGSWAP": 1776, "N_PSWAP": 48, "sign_flip_decision": 764,
                               "p_min_attainable_764_blocks": 0.0},
              "note": ("floors are labelled analytic or injection. The A4_vac_x_own frozen "
                       "injection curves are NOT resolved (DEFECTS D-06) and those cells use the "
                       "analytic floor.")},
    "controls": {"noop_placebo": rows(pl), "response_placebo": rows(rpl),
                 "leakage_probe": rows(lk),
                 "leakage_reading": ("kit K1: a flag is equally consistent with leakage and with a "
                                     "better estimator of a persistent quantity. Both columns are "
                                     "shift(1) constructions and cannot read the future; A2 "
                                     "tracking the player's own future share better than the base "
                                     "IS the claimed mechanism.")},
    "substitute_test": rows(sub),
    "season_stability": rows(ss),
    "anchors": {"n_total": int(len(anch)), "n_pass": int(anch["PASS"].sum()),
                "n_exact_zero": int((anch["abs_diff"] == 0).sum()), "table": rows(anch)},
    "defects_self_reported": 10,
    "no_production_change_proposed": True,
    "no_champion_fitted": True,
    "seed": A.SEED, "n_draws": A.N_DRAWS,
    "file_hashes": {f: hsh(os.path.join(A.OUT, f)) for f in
                    sorted(os.listdir(A.OUT)) if f.endswith((".md", ".csv"))},
}

with open(os.path.join(A.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1, default=str)
print("FINDINGS.json written: %d bytes" % os.path.getsize(os.path.join(A.OUT, "FINDINGS.json")))
print("anchors %d/%d pass, %d exact zero" % (out["anchors"]["n_pass"], out["anchors"]["n_total"],
                                             out["anchors"]["n_exact_zero"]))
print("headline dr2 UNFROZEN %+.6f  FROZEN %+.6f" % (out["Q2_headline"]["dr2_UNFROZEN"],
                                                     out["Q2_headline"]["dr2_FROZEN"]))
print("bootstrap/permutation sd ratio %.2f" % out["Q2_headline"]["bootstrap_sd_over_permutation_sd"])
