"""E1_I0042 s07 -- assemble FINDINGS.json from the CSVs the earlier steps wrote.

Nothing new is measured here.  One derived quantity is computed: the per-fold injection-verified
floor, obtained by carrying THIS SCREEN'S OWN measured anti-conservatism ratio (1.876x, s06) onto
each fold's analytic floor.  It is labelled CARRIED_RESCALE, not a per-fold measurement, wherever
it appears.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import rr_base as R  # noqa: E402

pd.set_option("display.width", 250)
R.check_prereg()

L = lambda n: pd.read_csv(os.path.join(R.OUT, n))  # noqa: E731
J = lambda n: json.load(open(os.path.join(R.OUT, n), encoding="utf-8"))  # noqa: E731

s01, s02 = J("_s01.json"), J("_s02.json")
s03, s04 = J("_s03.json"), J("_s04.json")
s05, s06 = J("_s05.json"), J("_s06.json")
P = L("PRIMARY_CELLS.csv")
RATIO = float(s06["floors"][0]["ratio_interpolated_over_analytic"])

R.hdr("1. THE HEADLINE CELLS, WITH THIS SCREEN'S OWN INJECTION-VERIFIED FLOOR CARRIED ONTO THEM")
head = P[(P.response == "minutes") & (P.stratum == "C_TREATED_and_DECISION")
         & (P.arm.isin(["C_SHARED_INTERCEPT", "C_FROZEN_INTERCEPT",
                        "ABC_SHARED_INTERCEPT"]))].copy()
head["MDE80_injection_carried_rescale"] = head.MDE80_analytic * RATIO
head["effect_over_injection_floor"] = head.dMAE / head.MDE80_injection_carried_rescale
head["VERDICT"] = [R.verdict(d, fl, nb) for d, fl, nb in
                   zip(head.dMAE, head.MDE80_injection_carried_rescale, head.n_blocks)]
COLS = ["window", "arm", "n", "n_blocks", "dMAE", "pct_of_MAE", "p", "MDE80_analytic",
        "MDE80_injection_carried_rescale", "effect_over_injection_floor", "VERDICT"]
print(head[COLS].to_string(index=False))
head.to_csv(os.path.join(R.OUT, "HEADLINE_WITH_FLOORS.csv"), index=False)

pts = P[(P.response == "pts") & (P.stratum == "C_TREATED_and_DECISION")
        & (P.arm == "C_FROZEN_INTERCEPT")]
R.hdr("2. THE SAME CELL ON POINTS -- compared only to its own base, never to minutes (D101)")
print(pts[["window", "arm", "n", "n_blocks", "dMAE", "pct_of_MAE", "p",
           "MDE80_analytic"]].to_string(index=False))

R.hdr("3. FINDINGS.json")
F = {
    "screen": "E1_I0042_redistribution_replication",
    "question": ("Does E1_I0039's decision-stratum minutes +1.73% (component C / D116 minutes "
                 "redistribution) replicate on a second clean window, and does it survive a "
                 "frozen walk-forward intercept?"),
    "prereg_sha256": s06 and json.load(open(os.path.join(R.OUT, "_prereg.json"),
                                            encoding="utf-8-sig"))["sha256"],
    "partition": {"exploration_seasons": list(R.EXPLORATION_SEASONS),
                  "sealed_never_read": list(R.SEALED),
                  "sealed_receipts_present_but_not_opened": s01["sealed_receipts_not_opened"]},
    "conditioning": ("ORACLE-ON-ABSENCE CEILING on every cell. The absence indicator is REALISED, "
                     "not forecast; both pre-game injury sources are UNVERIFIABLE. No cell here is "
                     "an achievable live increment."),

    "F1_WINDOW_CENSUS": {
        "n_clean_windows": s01["n_clean_windows"],
        "windows": s01["windows"],
        "scorable_seasons": s01["scorable_seasons"],
        "rule": "R1 champion fold not degenerate AND R2 >=1 admissible strictly-prior season",
        "2021_rejected_because": ("degenerate:true, model_was_fitted:false, n_train_rows:0, and "
                                  "all 4997 minutes forecasts are level-4 constant fallbacks -- "
                                  "verified first-hand from fold_receipt__2021.json"),
        "2022_rejected_because": ("fails R2: its only strictly-prior season is the degenerate "
                                  "2021 fold"),
        "residual_contamination": ("2023's overlay training pool is the single season 2022, whose "
                                   "OWN champion was trained on nothing but the degenerate 2021 "
                                   "fold. The degeneracy is one step removed, not quarantined."),
        "split_available": ("the one window contains two DISJOINT scored folds, 2023 and 2024. "
                            "This is a SPLIT of one window, NOT a second window: 2024's overlay "
                            "training pool contains 2023."),
        "VERDICT": "EXACTLY ONE CLEAN WINDOW EXISTS. A second was not manufactured."
    },

    "F2_DECISION_STRATUM_INTERSECTION_REPORTED_FIRST": s02["intersection"],

    "F3_DOES_THE_HEADLINE_REPLICATE": {
        "published_E1_I0039_ABC_shared": 0.07758861005075739,
        "reproduced_here_exactly": s02["A14"]["dMAE"],
        "C_shared_intercept_pooled": float(P[(P.response == "minutes")
                                             & (P.stratum == "C_TREATED_and_DECISION")
                                             & (P.window == "PRIMARY_WINDOW_2023_2024")
                                             & (P.arm == "C_SHARED_INTERCEPT")].dMAE.iloc[0]),
        "C_FROZEN_intercept_pooled": float(P[(P.response == "minutes")
                                             & (P.stratum == "C_TREATED_and_DECISION")
                                             & (P.window == "PRIMARY_WINDOW_2023_2024")
                                             & (P.arm == "C_FROZEN_INTERCEPT")].dMAE.iloc[0]),
        "fold_2023_frozen": float(P[(P.response == "minutes")
                                    & (P.stratum == "C_TREATED_and_DECISION")
                                    & (P.window == "PRIMARY_WINDOW_SPLIT_2023")
                                    & (P.arm == "C_FROZEN_INTERCEPT")].dMAE.iloc[0]),
        "fold_2024_frozen": float(P[(P.response == "minutes")
                                    & (P.stratum == "C_TREATED_and_DECISION")
                                    & (P.window == "PRIMARY_WINDOW_SPLIT_2024")
                                    & (P.arm == "C_FROZEN_INTERCEPT")].dMAE.iloc[0]),
        "sign_agreement_across_folds": True,
        "both_folds_clear_the_injection_floor": False,
        "VERDICT": ("PARTIALLY REPLICATED IN SIGN, NOT ESTABLISHED IN SIZE. The effect survives "
                    "the frozen intercept and is positive on both disjoint folds, but it sits at "
                    "0.55x its own injection-verified floor and empirical power at the observed "
                    "effect size is 0.482.")
    },

    "F4_FROZEN_INTERCEPT": {
        "construction": ("base's walk-forward intercept held; candidate contributes only slopes, "
                         "fitted with NO intercept on the residual about the frozen base. Verified "
                         "BIT-IDENTICAL to base wherever u == 0 (guards G1, G2, G4 all exact)."),
        "why_E1_I0039s_freeze_was_not_one": ("it set the arm to base OFF the treated rows and to "
                                             "the full shared-intercept arm ON them, so on the "
                                             "treated rows the number was still unfrozen"),
        "C_decision_shared": 0.075991,
        "C_decision_frozen": 0.079598,
        "component_survives_the_freeze": True,
        "recalibration_share_of_published_number": -4.75,
        "VERDICT": ("C DOES NOT COLLAPSE. Unlike A and B, whose decision-stratum effect is 100% "
                    "recalibration, C's effect GROWS by 4.7% when the intercept is frozen -- the "
                    "shared recalibration was working AGAINST it.")
    },

    "F5_VACUOUS_CONTROL_AND_A_KILL": {
        "E1_I0039_claim": ("'below the threshold the treatment is actively harmful on minutes, "
                           "-0.0230 at p 0.0003' (VERDICT.md s4 and s3 of the brief)"),
        "reproduced_here_exactly": s02["A15"]["dMAE"],
        "same_cell_with_the_intercept_frozen": 0.0,
        "why": ("the published C arm gates its regressors at freed >= 25, so on freed < 25 rows "
                "u is IDENTICALLY ZERO and the arm can differ from the base only through the "
                "shared walk-forward intercept"),
        "VERDICT": ("KILLED. The below-threshold harm is 100% recalibration, not treatment. "
                    "E1_I0034's own vacuous-control trap, firing again on a claim E1_I0039 "
                    "promoted to a headline.")
    },

    "F6_A_AND_B_VACUOUS_GAIN": {
        "cell": "C's own decision-stratum rows, n=1051, where A and B substitute ZERO rows",
        "AB_only_dMAE_minutes": 0.028705,
        "p": 0.00005,
        "vs_analytic_floor": 0.017496,
        "share_of_Cs_own_frozen_effect": 0.36,
        "VERDICT": ("A vacuous gain that CLEARS ITS FLOOR. On 1,051 rows the A/B arm does not "
                    "touch, substituting A and B is 'worth' +0.0287 minutes MAE at p 0.00005 -- "
                    "36% of C's whole frozen effect -- purely by moving the shared intercept. Any "
                    "shared-intercept lattice in this programme is exposed to this.")
    },

    "F7_CLAIM_1_THRESHOLD": {
        "mechanism_reproduces_exactly": ("all 20 published figures of E1_I0034's accounting table "
                                         "reproduce: trailing-5 sums 198.96 / 201.08 / 201.50 / "
                                         "191.44 / 184.02 and gains -3.24 / -2.59 / -3.01 / "
                                         "+6.36 / +15.47"),
        "forecasting_threshold_point_estimate_minutes": s04["tau_hat"],
        "bootstrap_ci90": s04["ci90"],
        "bootstrap_replicates_with_no_crossing": s04["n_boot_no_crossing"],
        "distinct_bootstrap_values": "0.0 in every replicate that crossed at all",
        "D101_clean_gate_sweep_best_gate": 0.0,
        "gate_0_dMAE": 0.041433,
        "gate_25_dMAE": 0.036044,
        "gate_30_dMAE": 0.036270,
        "VERDICT": ("THE MECHANISM THRESHOLD IS REAL AND REPRODUCES EXACTLY. THE FORECASTING "
                    "THRESHOLD DOES NOT EXIST. Under a frozen intercept the effect never changes "
                    "sign in the freed-minutes direction; only its magnitude varies. On one fixed "
                    "row set the UNGATED arm is the best of eleven gates, so 'under ~30 minutes, "
                    "do nothing' is not merely unsupported -- it costs 13% of the gain.")
    },

    "F8_CLAIM_2_EVEN_ALLOCATION": {
        "EVEN_u_only": 0.121985,
        "TILTED_published_u_and_uz": 0.079598,
        "PROPORTIONAL_to_base5": 0.088170,
        "PROPORTIONAL_plus_tilt": 0.044609,
        "allocations_beating_EVEN_by_more_than_its_floor": 0,
        "VERDICT": ("UPHELD, AND MORE STRONGLY THAN PUBLISHED. Even allocation is not beaten by "
                    "either alternative. The published specification's tilt term (u*z) is a DRAG: "
                    "dropping it raises the effect from +0.0796 to +0.1220. Note the honest "
                    "counterweight -- EVEN's larger effect comes with a larger null_sd (0.0504 vs "
                    "0.0273) and does NOT clear its own analytic floor, whereas TILTED does.")
    },

    "F9_CLAIM_3_STAGE_BOUNDARY": {
        "points_on_the_commercial_cell_shared": -0.013142,
        "points_on_the_commercial_cell_frozen": -0.018716,
        "points_on_all_C_treated_rows_frozen": -0.058789,
        "points_vacuous_gain_freed_eq_0_shared": 0.018717,
        "points_vacuous_gain_freed_eq_0_frozen": 0.0,
        "VERDICT": ("HOLDS, AND HARDENS. Every points cell that carries a treatment is negative, "
                    "and freezing the intercept makes them MORE negative. E1_I0039's apparently "
                    "positive pooled points number for C (+0.0012) is entirely vacuous: frozen, "
                    "it is -0.0161. Redistribution must not be applied to the points stage.")
    },

    "F10_ORDER_AND_SPECIFICATION": {
        "order_spread_pct_of_effect": 36.3,
        "E1_I0039_stack_order_spread_pct": "19-22",
        "C_alone_is_order_sensitive": True,
        "frame_U39_frozen": 0.079598,
        "frame_REM_frozen": 0.048246,
        "spec_lattice_spread": s05["spec_spread"],
        "spec_lattice_spread_pct_of_headline": 97.0,
        "all_variants_same_sign": True,
        "VERDICT": ("C ALONE IS ORDER-SENSITIVE, contrary to the expectation stated in the brief. "
                    "The full specification lattice spans 97% of the headline. Every variant is "
                    "POSITIVE, which is the strongest thing that can be said for the result: the "
                    "SIGN is robust, the SIZE is not.")
    },

    "F11_POWER_AND_NULLS": {
        "null": "paired sign-flip blocked at TEAM-GAME, 20,000 draws",
        "null_mean_diagnostic": ("STRUCTURALLY VACUOUS on a sign-flip null -- draws are +/- fixed "
                                 "block sums so E[draws] = 0 exactly. Recorded, never quoted as "
                                 "clearing anything."),
        "min_n_blocks_across_180_primary_cells": 113,
        "six_block_floor": "PASS on every cell",
        "type_I_at_alpha_05": s06["type_I"],
        "n_synthetic_datasets": s06["n_synthetic"],
        "MDE80_analytic": 0.076473,
        "MDE80_carried_D116_1_22x": 0.093297,
        "MDE80_injection_verified_this_screen": s06["MDE80_injection_interpolated"],
        "injection_over_analytic_ratio": RATIO,
        "empirical_power_at_the_observed_effect": s06["empirical_power_at_observed_effect"],
        "random_target_ratio": s06["random_target_ratio"],
        "no_op_placebo_dMAE": 0.0,
        "bonferroni_alpha_over_180_cells": s06["bonferroni_alpha"],
        "bonferroni_attainable_everywhere": True,
        "VERDICT": ("THE CELL IS UNDERPOWERED. This screen's own injection-verified floor is "
                    "0.1435, 1.88x the analytic rule -- independently confirming D113's suspicion "
                    "and exceeding D116's carried 1.22x. The observed effect is 0.55x that floor "
                    "and empirical power at the observed effect size is 0.482, not 0.80.")
    },

    "OVERALL_VERDICT": ("PARTIALLY REPLICATED, NOT ESTABLISHED, AND THE OPERATIONAL PRESCRIPTION "
                        "IS WRONG. Exactly one clean window exists. On it the +1.73% reproduces "
                        "exactly, survives a genuine frozen intercept at +1.77%, keeps its sign on "
                        "both disjoint folds and across every one of fifteen specification "
                        "variants -- but it is 0.55x its own injection-verified floor at 48% "
                        "power, only the 2024 fold rejects on its own, the '~30-minute threshold' "
                        "does not exist as a forecasting rule, and the below-threshold harm that "
                        "E1_I0039 promoted to a headline is 100% recalibration."),
    "PRODUCTION": "NO PRODUCTION CHANGE IS PROPOSED OR ENACTED. C remains unauthorised.",
    "anchors_reproduced_before_any_new_statistic": 43,
    "anchors_exact_at_zero": 40,
    "anchors_at_machine_precision": 3,
    "anchor_mismatches": 0,
    "anchor_breakdown": {"champion_fold_receipts": 6, "E1_I0034": 6, "E1_I0039": 11,
                         "E1_I0034_mechanism_table": 20},
    "construction_guards_additional": {"G1_frozen_base_eq_shared_base": 2,
                                       "G2_frozen_eq_base_off_treated_rows": 2,
                                       "G4_ungated_frozen_eq_base_where_u_zero": 1,
                                       "P1_noop_placebo_exactly_zero": 1},
}
R.dump(F, "FINDINGS.json")
print(json.dumps({k: (v if not isinstance(v, (dict, list)) else "...") for k, v in F.items()},
                 indent=1)[:2000])
print("\n  wrote FINDINGS.json, HEADLINE_WITH_FLOORS.csv")
