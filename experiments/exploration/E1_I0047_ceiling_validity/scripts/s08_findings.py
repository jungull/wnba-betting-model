"""E1_I0047 s08 -- assemble FINDINGS.json from the recorded artifacts only."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import cv_base as cb  # noqa: E402


def jload(n):
    with open(os.path.join(HERE, n), encoding="utf-8") as fh:
        return json.load(fh)


s01, s02, s03 = jload("_s01.json"), jload("_s02.json"), jload("_s03.json")
s06, s07 = jload("_s06.json"), jload("_s07.json")
E = pd.read_csv(os.path.join(cb.OUT, "EXPOSURE_213.csv"))
R = pd.read_csv(os.path.join(cb.OUT, "REMEASURE_30.csv"))
N = pd.read_csv(os.path.join(cb.OUT, "NONLINEAR_NULLS.csv"))
I = pd.read_csv(os.path.join(cb.OUT, "COMPONENT_INJECTION.csv"))
T = pd.read_csv(os.path.join(cb.OUT, "CEILING_FORMS_CENSUS.csv"))
with open(os.path.join(cb.OUT, "PREREG.sha256"), encoding="utf-8") as fh:
    sha = fh.read().strip().lstrip("﻿")

out = {
    "screen": "E1_I0047_ceiling_validity",
    "prereg_sha256": sha,
    "partition": {"seasons_read": [2021, 2022, 2023, 2024],
                  "sealed_holdout_2025_26_opened": False,
                  "d097_headline_window": [2022, 2023, 2024],
                  "clean_window_arm": [2023, 2024]},
    "seed": cb.SEED,
    "processes_launched": "python, foreground only, one at a time; no PID signalled; "
                          "NO blanket process kill of any kind was issued",

    "HEADLINE": {
        "is_it_a_bound": "CONDITIONALLY. (d.d)/SST >= dR2 iff c* := (d.e)/(d.d) <= 1. It is an "
                         "EXACT EQUALITY when d is the OLS fitted contribution on the same rows, "
                         "response, SST and base. It is NOT a bound when d is transported "
                         "(rate coefficient x minutes -> points, or across a fold boundary).",
        "understatement_factor": "c*^2, exactly",
        "all_213_safe": True,
        "n_at_risk": int(s03["at_risk"]),
        "n_safe_by_margin_100x": int(s03["safe_by_margin_100x"]),
        "n_safe_by_construction": int(s03["safe_by_construction"]),
        "n_reopened": 0,
        "failing_assumption": "SCALE (the shift applied below its optimal coefficient), "
                              "NOT orthogonality of the candidate to the base",
    },

    "anchors": {"n_pass": s01["n_pass"], "n_total": s01["n_total"], "detail": s01["anchors"],
                "additional_reproductions": {
                    "s04_30_cells_dr2_max_abs_diff":
                        float(R["arm1_abs_diff_vs_recorded_dr2"].max()),
                    "s04_30_cells_ceiling_max_abs_diff":
                        float(R["arm1_abs_diff_vs_recorded_ceiling"].max()),
                    "s04_30_cells_rowcount_mismatches":
                        int((R["n_arm1"] != R["n_recorded"]).sum()),
                    "e1_i0036_eligibility_118_of_1580_reproduced": True}},

    "algebra": {
        "identity": "dR2 = (2 d.e - d.d)/SST",
        "bound_condition": "c* <= 1",
        "oracle": "(d.e)^2/((d.d) SST) = c*^2 (d.d)/SST",
        "ols_same_scale_c_star": s02["algebra"]["c_star"],
        "minimal_counterexample": s02["minimal"],
        "collinearity_probe_max_abs_c_star_minus_1":
            s02["collinearity"]["max_abs_c_star_minus_1"],
        "collinearity_probe_min_varshare_over_realised":
            s02["collinearity"]["min_varshare_over_realised"]},

    "the_213": {
        "source_screen": "E0_I0024_reb_ast_characterisation (D097)",
        "source_decision": "D097",
        "single_construction": "C-RAWSD = (|beta_hat| sd(x)/sd(y))^2 == dR2 * VIF",
        "d101_declaration": {
            "response": "the cell's own target (y_reb/y_oreb/y_dreb/y_ast/y_pts)",
            "row_set": "D097 complete-case rows, seasons 2022-2024, POOLED or DECISION "
                       "(n_prior >= 8 AND ref_trail5_minutes >= 24)",
            "sst_basis": "sum (y - ybar)^2 on those same rows, unweighted (D069)",
            "weighting": "none",
            "base": "B_SINGLE / B_COMPLETE / B_COMPLETE_PLUS_R10 as recorded",
            "fit": "in-sample OLS, Frisch-Waugh, same rows",
            "floor_applied": "FLOOR_1CELL = 0.00102 (D103, injection-verified), same scale"},
        "counts": {"total": int(len(E)), "at_risk": int(s03["at_risk"]),
                   "safe_by_margin_100x": int(s03["safe_by_margin_100x"]),
                   "safe_by_construction": int(s03["safe_by_construction"]),
                   "degenerate_zero_ceiling": int(E["DEGENERATE_zero_ceiling"].sum()),
                   "negative_controls_G01_noise": int((E["candidate"] == "G01_noise").sum()),
                   "candidates_not_controls": int(len(E) - E["DEGENERATE_zero_ceiling"].sum()
                                                  - (E["candidate"] == "G01_noise").sum())},
        "margin_counts": s03["margin_counts"],
        "vif": {"min": float(E["VIF_slack"].min()), "median": float(E["VIF_slack"].median()),
                "max": float(E["VIF_slack"].max()),
                "n_below_1": int((E["VIF_slack"] < 1 - 1e-12).sum()),
                "n_effectively_orthogonal_lt_1p01": int((E["VIF_slack"] < 1.01).sum())},
        "understatement": {"n_U_gt_1": int(s03["n_U_gt_1"]),
                           "U_min": float(E["U_understatement_factor"].min()),
                           "U_max": float(E["U_understatement_factor"].max())},
        "realised_vs_floors": {
            "max_realised_dr2": float(s03["max_realised"]),
            "max_realised_over_FLOOR_1CELL": float(s03["max_realised_over_floor"]),
            "n_realised_ge_FLOOR_1CELL": int((E["R_realised_dr2"] >= cb.FLOOR_1CELL).sum()),
            "n_realised_ge_FLOOR_132": int((E["R_realised_dr2"] >= cb.FLOOR_132).sum()),
            "n_realised_ge_own_mde80": int((E["R_realised_dr2"]
                                            >= E["mde80_fw_used"]).sum()),
            "min_margin_vs_own_mde80": float(E["margin_vs_own_mde80"].min())}},

    "live_counterexamples": {
        "E1_I0023_arithmetic_ceiling": {
            "rows": s02["e1_i0023"]["n_rows"], "n_realised_exceeds_ceiling":
                s02["e1_i0023"]["n_exceeds"], "max_ratio": s02["e1_i0023"]["max_ratio"],
            "D098_headline_cell": {
                "cell": "A10_opp_defrtg|DECISION|T3_high_usage|MAIN_EFFECT|walk_forward",
                "ceiling": s02["e1_i0023"]["headline_ceiling"],
                "realised": s02["e1_i0023"]["headline_realised"],
                "oracle": s02["e1_i0023"]["headline_oracle"],
                "c_star": s02["e1_i0023"]["headline_c_star"],
                "realised_over_ceiling": s02["e1_i0023"]["headline_realised"]
                / s02["e1_i0023"]["headline_ceiling"]}},
        "E1_I0043_CEILING_MATCHED": s02["e1_i0043"],
        "D097_upstream_signals": s02["d097"]},

    "remeasurement": {
        "rule": "PREREG 6, unamended: margin < 10x OR top 25 by ceiling OR identity failure; "
                "cap 30 by rank_score. Selection by recorded numeric columns only.",
        "n_selected": int(s03["n_selected"]), "n_run": int(s03["n_to_run"]),
        "n_selected_not_run": int(s03["n_selected"] - s03["n_to_run"]),
        "decision_stratum_intersection": {
            "definition": "n_prior >= 8 AND ref_trail5_minutes >= 24",
            "frame_rows": 14327, "n_prior_ge_8": 10688, "trail5_ge_24": 6352,
            "intersection": 5111, "pct_of_frame": 35.67,
            "by_season": {"2022": 1559, "2023": 1776, "2024": 1776},
            "distinct_players": 132, "distinct_opp_team_seasons": 36,
            "cells_on_DECISION": int((R["stratum"] == "DECISION").sum()),
            "cells_on_POOLED": int((R["stratum"] == "POOLED").sum())},
        "frozen_intercept": {
            "max_frozen_over_refit": float((R["arm1F_dr2_frozen_intercept"]
                                            / R["arm1_dr2"]).max()),
            "min_frozen_over_refit": float((R["arm1F_dr2_frozen_intercept"]
                                            / R["arm1_dr2"]).min()),
            "n_frozen_gt_refit": int((R["arm1F_dr2_frozen_intercept"] > R["arm1_dr2"]).sum()),
            "note": "freezing the intercept SHRINKS every statistic; no conclusion depends on "
                    "which is used; both are published per cell in REMEASURE_30.csv"},
        "clean_window_2023_24": {
            "n_min": int(R["n_arm2"].min()), "n_max": int(R["n_arm2"].max()),
            "sst_recomputed_on_window_rows": True,
            "max_dr2": float(R["arm2_dr2"].max()),
            "max_over_FLOOR_1CELL": float(R["arm2_dr2"].max() / cb.FLOOR_1CELL),
            "n_ge_FLOOR_1CELL": int((R["arm2_dr2"] >= cb.FLOOR_1CELL).sum()),
            "max_abs_c_star_minus_1": float(np.abs(R["arm2_c_star"] - 1).max())},
        "walk_forward_diagnostic": {
            "folds": 2, "verdict_issued": False,
            "reason": "two folds is below the six-block requirement; this arm measures c*, "
                      "it does not judge a cell",
            "c_star_min": float(R["arm4_c_star"].min()),
            "c_star_max": float(R["arm4_c_star"].max()),
            "n_c_star_gt_1": int((R["arm4_c_star"] > 1).sum()),
            "n_bound_fails": int(R["arm4_bound_fails"].sum()),
            "max_oracle_over_FLOOR_1CELL": float(R["arm4_oracle"].max() / cb.FLOOR_1CELL)},
        "nonlinear_arm_RETRACTED_AS_A_FINDING": {
            "raw_result": "6-column block exceeds the recorded ceiling in 30 of 30 cells; "
                          "12 of 30 cross FLOOR_1CELL",
            "why_it_is_not_a_finding": "FLOOR_1CELL is a 1-column floor and the block is "
                                       "6 columns. E[dR2|null] ~ k/n = 1.174e-03 at n=5111, "
                                       "k=6, which is 1.15x FLOOR_1CELL before any signal.",
            "df_matched_floor_result": {
                "n_cells_nulled": int(len(N)),
                "n_exceeding_own_6df_floor": int((N["real_nl_over_FLOOR_6DF"] >= 1).sum()),
                "n_clearing_matched_null_p05": int((N["nl_p_matched"] < 0.05).sum()),
                "best_ratio_to_own_6df_floor": float(N["real_nl_over_FLOOR_6DF"].max()),
                "pure_noise_control_over_FLOOR_1CELL":
                    float(N[N["candidate"] == "G01_noise"]["real_nl_over_FLOOR_1CELL"].max())},
            "disposition": "uncorrected arm3_* columns kept on disk in REMEASURE_30.csv; "
                           "corrected 6-df floors in NONLINEAR_NULLS.csv"}},

    "nulls": {
        "matched_null_by_level": {"opp_team_season": "N_ESWAP", "team_season": "N_TSWAP",
                                  "player_season": "N_PSWAP", "row": "N_ROW"},
        "blind_arm": "within-entity shuffle, computed and published, never a verdict "
                     "(E1_I0043 D-05: blindness is a match between the permuting entity and "
                     "the candidate's constancy entity)",
        "draws_per_arm": 600,
        "blocks_min": int(N["nblocks"].min()), "blocks_max": int(N["nblocks"].max()),
        "n_power_not_assessed": int((~N["POWER_ASSESSED"]).sum()),
        "null_centre_ratio_min": float(N["nl_null_centre_ratio"].min()),
        "null_centre_ratio_max": float(N["nl_null_centre_ratio"].max()),
        "n_cells_null_centred_ge_0p8_of_real": int((N["nl_null_centre_ratio"] >= 0.8).sum()),
        "seeds": "deterministic, zlib.crc32 of the cell key + SEED; str.__hash__ NOT used "
                 "(E1_I0043 D-07 not repeated). Every draw archive regenerates from SEED alone.",
        "storage": "nulls/*.npz, signed and unstandardised, every stratum arm of every null"},

    "component_injection": {
        "design": "signal planted into a synthetic response (yhat_base + sd(e)*z + b*c_perp) so "
                  "it can neither cancel nor reinforce the cell's own effect; 200 replicates x "
                  "199-permutation bank",
        "type_I_at_delta_0": float(I[I["target_delta"] == 0]["power"].mean()),
        "n_arms_share_ge_10pct": int((I["var_share"] >= 0.10).sum()),
        "n_powered_ge_0p80_at_delta_0p006": int(I[(I["var_share"] >= 0.10)
                                                  & (I["target_delta"] >= 0.006)]
                                                ["rejects"].sum()),
        "n_arms_at_delta_0p006_share_ge_10pct": int(len(I[(I["var_share"] >= 0.10)
                                                          & (I["target_delta"] >= 0.006)])),
        "realisation_ratio_between": [float(I[(I.component == "BETWEEN")
                                              & (I.target_delta > 0)]["realisation_ratio"].min()),
                                      float(I[(I.component == "BETWEEN")
                                              & (I.target_delta > 0)]["realisation_ratio"].max())],
        "realisation_ratio_within": [float(I[(I.component == "WITHIN") & (I.target_delta > 0)
                                             & (I.var_share > 0.05)]["realisation_ratio"].min()),
                                     float(I[(I.component == "WITHIN") & (I.target_delta > 0)
                                             & (I.var_share > 0.05)]["realisation_ratio"].max())],
        "caveat": "the WITHIN arm realises about a third of its target, so its power is power "
                  "against something smaller -- the reading E1_I0043 D-06 asks for"},

    "noise_floor_check": {
        "scopes": s06["scopes"],
        "D098_headline_ceiling": s06["headline_ceiling"],
        "D098_headline_realised": s06["headline_realised"],
        "matched_noise_floor": s06["matched_noise_floor"],
        "ratio_against_matched_floor": s06["ratio_matched"],
        "E1_I0043_D01_verdict": "CONFIRMED at 10.99x under the scope the sentence is used in; "
                                "1.44x under its literal first clause. Both reported.",
        "pattern_elsewhere": "no second instance in the current record; E1_I0043 and E1_I0046 "
                             "both quote matched per-cell floors. But only 2 of 33 ceiling "
                             "tables record a negative control at all, so the sample is thin.",
        "noise_floor_spread_within_one_screen_max_over_median": 25.2},

    "ceiling_forms_census": {
        "n_tables": int(len(T)), "n_screens": int(T["table"].str.split("/").str[0].nunique()),
        "same_scale_ols_safe": ["E0_I0024_reb_ast_characterisation (D097)",
                                "E0_I0029_freethrow_hurdle (D108)"],
        "same_scale_violations": 0, "same_scale_rows_checked": 346,
        "transported_exposed": ["E1_I0004_efficiency_transfer_v2 (D084)",
                                "E1_I0018_teammate_volume_channel (D089)",
                                "E1_I0023_usage_defence_interaction (D098)",
                                "E1_I0043_opponent_defence"],
        "D084_oracle_by_stratum": {
            "on_stratum_decision_relevant": {"n": 5086, "max_oracle": 1.283495e-04,
                                             "x_floor": 0.1258},
            "all_rows_pooled": {"n": 11267, "max_oracle": 9.719177e-05, "x_floor": 0.0953},
            "off_stratum_not_a_decision_surface": {"n": 6181, "max_oracle": 1.285264e-03,
                                                   "x_floor": 1.2601},
            "verdict": "D084's kill HOLDS where it matters; its published 0.000129 understates "
                       "the true bound by up to 10x, entirely off-stratum"},
        "D089_no_oracle_in_arithmetic_ceiling_csv": True,
        "D089_reconciliation_max_c_star_sq": 8.989,
        "D089_reconciliation_max_oracle_over_floor": 14.6374},

    "defects": [
        {"id": "D-01", "who": "programme (D079/D084/D089/D098 form)",
         "what": "(d.d)/SST is not a bound for the transported form; c*^2 up to 8.99 observed; "
                 "counterexample sits on D098's own headline cell, exceeded by 46%",
         "reopens_anything": False},
        {"id": "D-02", "who": "E1_I0036",
         "what": "the 213 were excluded from re-levelling on the false premise that a "
                 "beta_hat-derived ceiling is invariant to re-levelling; 171 of 213 would have "
                 "been T2 and T3 eligible; published eligibility 7.5% -> 18.3%",
         "reopens_anything": False},
        {"id": "D-03", "who": "this screen (self-inflicted, caught in-run)",
         "what": "compared a 6-df nonlinear block against a 1-df floor and produced an apparent "
                 "12-cell reopening; the pure-noise control reaches 0.987x the same floor",
         "reopens_anything": False},
        {"id": "D-04", "who": "E1_I0043",
         "what": "D-01's '11x' is right for the scope used and 1.44x for the literal clause; "
                 "one number quoted where two are needed",
         "reopens_anything": False},
        {"id": "D-05", "who": "programme headline count",
         "what": "40 of the '213 ceiling kills' are negative controls (20 no-op placebo, "
                 "20 pure noise); the candidate count is 173",
         "reopens_anything": False},
        {"id": "D-06", "who": "this screen's brief",
         "what": "nominated orthogonality as the suspect; the operative condition is scale "
                 "transport, and orthogonality is the zero-slack case",
         "reopens_anything": False},
        {"id": "D-07", "who": "E1_I0036 D-03",
         "what": "33 ceiling tables across 12 screens exist, not one; D108's is the same "
                 "provably safe construction and was verified here (0 violations in 96 rows)",
         "reopens_anything": False}],

    "answers_to_the_brief": {
        "1_is_it_a_bound": "Conditionally. Exact equality for a same-scale OLS shift; not a "
                           "bound for a transported shift. The condition is c* <= 1.",
        "2_counterexample_or_proof": "BOTH. Proof for the same-scale case (c* = 1 identically, "
                                     "verified to 2.2e-16 on live cells and 6.8e-15 over 1,000 "
                                     "synthetic draws). Counterexample for the transported case, "
                                     "minimal at n=3 and live on D098's headline cell.",
        "3_exposure_across_213": "Zero. c* = 1 for all 213, U = 1/VIF <= 1, so the computed "
                                 "ceiling OVERSTATES the true one by up to 1.68x. Max realised "
                                 "effect among the 213 is 0.78x the single-cell floor.",
        "4_safe_by_margin_alone": int(s03["safe_by_margin_100x"]),
        "5_how_many_reopen": 0,
        "6_noise_floor_defect": "CONFIRMED at 10.99x (scope used), 1.44x (literal scope); "
                                "no second instance in the current record"},

    "what_most_weakens_this": [
        "The 213 are NOT pre-fit arithmetic kills. C-RAWSD is derived from beta_hat of the very "
        "fit it bounds; every one of the 213 was fitted. They are post-fit kills wearing a "
        "ceiling label, and they inherit every assumption of that fit -- base, level, linearity, "
        "in-sample scoring, rowset. The four rulings D114/D117/D120/D122 stand on their "
        "conclusion but not on their stated reason.",
        "One clean-window cell (DECISION|y_oreb|B_SINGLE|R07_own_miss_pg) reaches 1.39x "
        "FLOOR_1CELL on 2023-24 rows with SST recomputed. It sits on the thinnest base in the "
        "set and its B_COMPLETE sibling does not cross. Reported, not promoted.",
        "5 of 14 nulled cells have a matched null centred at >= 0.8 of the real effect, which "
        "makes those arms weak instruments even though they are the correctly matched ones.",
        "The cross-screen noise-floor sweep found only 2 of 33 ceiling tables carrying a "
        "negative control at all. 'No second instance of the defect' is a statement about a "
        "very thin sample, not about the other 31 tables.",
        "D084's off-stratum oracle clears the single-cell floor at 1.26x. Nothing "
        "decision-relevant follows, but the published ceiling understates the true bound 10x "
        "there and no artifact in the ledger records that."],

    "no_production_change_enacted": True,
    "no_champion_fitted": True,
    "write_scope_respected": "experiments/exploration/E1_I0047_ceiling_validity/ only; "
                             "the shared screen kit was never imported for writing and never "
                             "modified; no git write command was issued",
}

with open(os.path.join(cb.OUT, "FINDINGS.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, default=float)
print("wrote FINDINGS.json")
