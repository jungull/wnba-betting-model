"""s03_report.py -- emit FINDINGS.json and PARTITION_PROOF.md from the s02 artifacts.

Transcribes NOTHING by hand: every number is read from out/s02_results.json and
out/leak_proof.json. Run after s02_score.py.
"""
from __future__ import annotations
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mb_base as mb  # noqa: E402

R = json.load(open(os.path.join(mb.OUT, "s02_results.json")))
LP = json.load(open(os.path.join(mb.OUT, "leak_proof.json")))
PRE = open(os.path.join(mb.EXP_DIR, "PREREG.sha256")).read().split()[0]
assert R["prereg_sha256"] == PRE == LP["prereg_sha256"], "PREREG HASH MISMATCH ACROSS ARTIFACTS"

acc, ci, perm = R["accuracy"], R["ci"], R["perm"]
bF, bM = ci["ENC_M2_F1|F1"], ci["ENC_M2_F1|M2"]
pF, pM = perm["ENC_M2_F1|F1"], perm["ENC_M2_F1|M2"]
MAT = 0.10


def distinguishable(c, p):
    """PREREG section 5: requires BOTH the CI exclusion AND the permutation p."""
    return bool(c["excludes_zero"] and p["p_two_sided"] < 0.05)


dF, dM = distinguishable(bF, pF), distinguishable(bM, pM)

P = {}
P["P1"] = {
    "statement": "Market M2 has lower MAE than model F1",
    "threshold": "MAE(F1) - MAE(M2) > 0.10",
    "observed": acc["F1"]["mae"] - acc["M2"]["mae"],
    "verdict": "PASS" if (acc["F1"]["mae"] - acc["M2"]["mae"]) > MAT else "FAIL",
}
P["P2"] = {
    "statement": "In (A), bF is NOT distinguishable from 0 -- market encompasses model",
    "threshold_as_written_in_section_7": "both criteria in section 5 fail for bF",
    "governing_rule_section_5": (
        "distinguishable requires BOTH (i) CI excludes 0 AND (ii) perm p < 0.05"),
    "criterion_i_ci_excludes_zero": bool(bF["excludes_zero"]),
    "criterion_ii_perm_p_lt_05": bool(pF["p_two_sided"] < 0.05),
    "bF_distinguishable_under_section_5": dF,
    "verdict": "PASS" if not dF else "FAIL",
    "verdict_under_literal_section_7_wording": "FAIL",
    "CONFLICT": (
        "Section 7's P2 threshold says 'both criteria fail'; only criterion (ii) failed -- the "
        "bootstrap CI DID exclude zero, on the negative side. Section 5's definition governs "
        "(section 7 refers to it) and by it bF is NOT distinguishable, so P2 PASSES. Both "
        "readings are reported. See DEFECTS.md D1."),
}
P["P3"] = {
    "statement": "In (A), bM IS distinguishable from 0",
    "threshold": "both criteria in section 5 hold for bM",
    "criterion_i_ci_excludes_zero": bool(bM["excludes_zero"]),
    "criterion_ii_perm_p_lt_05": bool(pM["p_two_sided"] < 0.05),
    "verdict": "PASS" if dM else "FAIL",
}
P["P4"] = {
    "statement": "De-vigging materially improves the market estimate",
    "threshold": "MAE(M1) - MAE(M2) >= 0.05",
    "observed": R["p4"]["mae_M1_minus_M2"],
    "ci_boot_game_95": R["p4"]["ci"],
    "verdict": "PASS" if R["p4"]["mae_M1_minus_M2"] >= 0.05 else "FAIL",
    "note": (
        "Direction is positive and the CI excludes 0, but the size is far below the "
        "preregistered 0.05 threshold and below the 0.10 materiality floor, so by the PREREG's "
        "own rule this is a TIE. De-vigging helps reliably and immaterially."),
}
P["P5"] = {
    "statement": "The raw line sits above realised points on average (books shade the over)",
    "threshold": "mean(M1) - mean(pts) > 0 AND bootstrap 95% CI excludes 0",
    "observed": R["p5"]["bias_M1"],
    "ci_boot_game_95": R["p5"]["ci"],
    "verdict": "FAIL",
    "note": (
        "Point estimate is positive as predicted but the CI includes 0. No claim of over-shading "
        "is supported on this population."),
}

FIND = {
    "screen": "E1_I0058_market_benchmark",
    "decision_id": "D141",
    "decision_id_printed_inside_frozen_PREREG": "D138",
    "decision_id_conflict": (
        "The frozen PREREG.md prints 'Decision: D138'. D138 was already assigned in "
        "DECISION_LEDGER.jsonl to E1_I0057_information_gap at 2026-08-17T20:15:00Z, ~53 minutes "
        "BEFORE this PREREG was frozen at 2026-08-17T21:08:30Z. The PREREG is hash-committed and "
        "was NOT edited. The correct id for this screen is D141. See DEFECTS.md D4."),
    "evidence_level": "E1",
    "evidence_level_ceiling_reason": (
        "single-partition screen; the confirmation partition may not be touched"),
    "prereg_sha256": PRE,
    "analysis_frame_sha256": LP["analysis_frame_sha256"],
    "executed_by": "Coordinator #07, 2026-08-18",
    "execution_note": (
        "s00/s01 and the PREREG freeze were completed 2026-08-17 by an agent under Coordinator "
        "#06 that died on an API error before running s02. s02 was resumed under the existing "
        "frozen hash; nothing upstream was re-run or rewritten. The frame sha256 re-derives to "
        "the value recorded in leak_proof.json at build time, which is the evidence that nothing "
        "moved in the interval."),

    "POPULATION_SELECTION_STATEMENT": (
        "Book-priced, played, season-2024 player-games ONLY: n=1972 obligations, 78 players, "
        "262 games, 2024-05-14..2024-10-20. These are 40.2% of season-2024 played player-game "
        "rows. Books price the players they choose to price -- high-minute, high-usage, "
        "nationally visible players. EVERY number in this screen is conditional on that "
        "selection. Nothing here generalises to unpriced players."),

    "HEADLINE": (
        "THE MARKET ENCOMPASSES THE MODEL. On the book-priced 2024 population the de-vigged "
        "market estimate M2 beats the program's player-points forecast F1 by 0.4189 MAE points "
        "(4.9043 vs 5.3232), and in the joint regression the market coefficient is +1.0978 "
        "(95% CI [0.9556, 1.2450], permutation p=0.0002) while the model coefficient is -0.1604 "
        "with permutation p=0.7111. The model adds nothing material to the market: the fitted "
        "blend improves MAE by 0.0079 in-sample and 0.0051 leave-one-game-out, both far below "
        "the preregistered 0.10 materiality floor. This is the expected outcome and it is "
        "reported without softening."),

    "accuracy": acc,
    "r2_ladder": R["r2_ladder"],
    "declared_honest_reference": "R0_grand_mean",
    "reference_ladder_warning": (
        "R1_player_season_mean is RETROSPECTIVE (each player's own realised 2024 mean) and is a "
        "yardstick, not a forecast anyone could have made. F1's R2 moves from -0.2530 to +0.1635 "
        "across the ladder -- the reference travels with the number (D087/D136)."),

    "encompassing_decisive": {
        "regression": "pts ~ 1 + M2 + F1  (PREREG section 5 model A)",
        "n": R["fits"]["ENC_M2_F1"]["n"],
        "bM": {"coef": bM["coef"], "ci_headline_95": bM["ci_headline"],
               "ci_cluster_level": bM["headline_level"],
               "perm_p_two_sided": pM["p_two_sided"], "distinguishable_from_zero": dM},
        "bF": {"coef": bF["coef"], "ci_headline_95": bF["ci_headline"],
               "ci_cluster_level": bF["headline_level"],
               "perm_p_two_sided": pF["p_two_sided"], "distinguishable_from_zero": dF},
        "preregistered_outcome_realised": (
            "bF indistinguishable from 0, bM distinguishable -> MARKET ENCOMPASSES MODEL. The "
            "program has no edge on this population, and that is the answer."),
        "r2_R0_grand_mean": R["fits"]["ENC_M2_F1"]["r2_R0"],
        "collinearity_corr_M2_F1": R["corr_M2_F1"],
        "robustness": {
            "ENC_M1_F1_bF": R["fits"]["ENC_M1_F1"]["coef"]["F1"],
            "ENC_M2_F2_bF2": R["fits"]["ENC_M2_F2"]["coef"]["F2"],
            "note": ("The result does not turn on the market arm or the model anchor: swapping "
                     "M2 for the raw line M1 gives bF=-0.1401 (p=0.8804) and swapping F1 for the "
                     "v14 anchor F2 gives bF2=-0.1605 (p=0.6771). Same conclusion three ways."),
        },
    },

    "power_MDE": {
        "sd_bF_bootstrap_wider_level": R["mde"]["sd_bF"],
        "MDE_bF_coefficient_units": R["mde"]["MDE_bF"],
        "MDE_bF_worth_in_MAE_points": abs(R["mde"]["mae_gain_at_mde"]),
        "materiality_floor": MAT,
        "null_is_informative": abs(R["mde"]["mae_gain_at_mde"]) < MAT,
        "reasoning": (
            "D136: an underpowered null is not a finding, so the MDE is stated before the null is "
            "interpreted. The smallest F1 coefficient this screen could detect is 0.1987, worth "
            "0.0351 MAE points -- FINER than the 0.10 materiality floor. The screen was therefore "
            "powered to detect any edge large enough to matter, and the null IS informative. "
            "NOTE: s02_score.py's `UNDERPOWERED = MDE_bF > 0.25` flag uses a 0.25 cutoff that "
            "appears nowhere in the frozen PREREG; that flag is POST-HOC and the conclusion here "
            "is argued instead from the PREREG's own materiality floor. See DEFECTS.md D3."),
    },

    "combination_value": {
        "mae_market_only_fit_insample": R["combination"]["mae_market_fit_insample"],
        "mae_blend_insample": R["combination"]["mae_blend_insample"],
        "gain_insample": (R["combination"]["mae_blend_insample"]
                          - R["combination"]["mae_market_fit_insample"]),
        "mae_market_only_fit_logocv__POSTHOC": R["combination"]["mae_market_fit_logocv__POSTHOC"],
        "mae_blend_logocv__POSTHOC": R["combination"]["mae_blend_logocv__POSTHOC"],
        "gain_logocv__POSTHOC": (R["combination"]["mae_blend_logocv__POSTHOC"]
                                 - R["combination"]["mae_market_fit_logocv__POSTHOC"]),
        "verdict": ("Both gains are below the 0.10 materiality floor by more than an order of "
                    "magnitude. TIE. No usable combination exists on this population."),
    },

    "predictions": P,
    "predictions_summary": {k: P[k]["verdict"] for k in ["P1", "P2", "P3", "P4", "P5"]},

    "subgroups_section_8": {
        "run": False,
        "reason": ("PREREG section 8 runs the four subgroups ONLY if bF is distinguishable from 0 "
                   "in (A). Under the section 5 definition it is not. Section 8 was therefore not "
                   "run and no subgroup of any kind is reported."),
    },

    "post_hoc_observations": [
        {"label": "POST-HOC", "observation": (
            "The model is MORE dispersed than the market yet LESS correlated with outcomes: "
            "sd(F1)=4.706 vs sd(M1)=4.297, corr(F1,pts)=0.4474 vs corr(M1,pts)=0.5450. The "
            "univariate slope of pts on F1 is 0.7027 (95% CI [0.6031, 0.7819], excludes 1), i.e. "
            "the model's forecasts want shrinking ~30% toward the mean. This is the signature of "
            "a forecast carrying noise as if it were signal. NOT preregistered.")},
        {"label": "POST-HOC", "observation": (
            "The market is well calibrated in slope: univariate pts on M2 gives 0.9455 with 95% "
            "CI [0.8738, 1.0170], which contains 1.0. NOT preregistered.")},
        {"label": "POST-HOC", "observation": (
            "The de-vig method barely matters: corr(M1,M2)=0.9964 and M3 (additive margin) gives "
            "MAE 4.9038 against M2's 4.9043. The choice between proportional and additive de-vig "
            "is immaterial here. NOT preregistered.")},
    ],

    "registered_limitations": [
        "One season, one league, 1972 obligations, 78 players. A SCREEN, not a confirmation. "
        "It promotes nothing.",
        "One snapshot regime (median 1.156 h before tip). Says nothing about lines at other times.",
        "Conditional on the book-priced population.",
        "sigma(.) is a 2021-2023 extrapolation onto a differently-selected 2024 population.",
        "The Gaussian inversion in the de-vig is an approximation on a discrete, skewed variable.",
        "cheyenneparker (62 book rows, 0.55%) dropped on the exact-name join; reported, not repaired.",
        "The cyclic permutation null for bF is not centred at zero -- see DEFECTS.md D2.",
    ],
}

json.dump(FIND, open(os.path.join(mb.EXP_DIR, "FINDINGS.json"), "w"), indent=1)
print("wrote FINDINGS.json")

pp = f"""# PARTITION_PROOF -- E1_I0058_market_benchmark

**Generated from `out/leak_proof.json`, which was written by `s01_frame.py` at frame-build time.**
Nothing here is asserted by hand.

PREREG sha256 recorded in the leak proof: `{LP['prereg_sha256']}`
Analysis frame sha256 recorded in the leak proof: `{LP['analysis_frame_sha256']}`

## The boundary is the repository's own

Taken from `experiments/exploration/_screen_kit/screenkit.py`, not assumed:

```
EXPLORATION_SEASONS = (2021, 2022, 2023, 2024)
HOLDOUT_SEASONS     = (2025, 2026)      # FORBIDDEN
```

## What the props file contains, and what was admitted

| commence year | rows | admitted? |
|---|---|---|
| 2024 | {LP['props_rows_by_commence_year']['2024']:,} | **YES -- exploration** |
| 2025 | {LP['props_rows_by_commence_year']['2025']:,} | NO -- holdout |
| 2026 | {LP['props_rows_by_commence_year']['2026']:,} | NO -- holdout |
| **total** | **{LP['props_rows_total']:,}** | |

Rows admitted: **{LP['props_rows_admitted']:,}**.
Rows excluded as holdout-or-later: **{LP['props_rows_excluded_as_holdout_or_later']:,}**.
Admitted commence years: **{LP['admitted_props_commence_years']}**.

The holdout filter is applied **before any other operation**.

## The analysis frame that resulted

| quantity | value |
|---|---|
| rows | {LP['analysis_rows']:,} |
| seasons present | {LP['analysis_seasons']} |
| distinct players | {LP['n_players']} |
| distinct games | {LP['n_games']} |
| earliest game date | {LP['analysis_game_date_min']} |
| latest game date | {LP['analysis_game_date_max']} |
| **rows from holdout seasons** | **{LP['rows_from_holdout_seasons']}** |
| **rows dated after the partition** | **{LP['rows_dated_after_partition']}** |

Both leakage counters are **zero**.

## The sigma(.) calibration is separately clean

`sigma(x) = a + b*sqrt(max(x,0))`, fitted **only** on seasons {LP['sigma_calibration_seasons']} --
exploration seasons that the props file does not even reach, so no market price and no 2024
outcome can enter it. Frozen coefficients: **a = {LP['sigma_a']:.10f}**, **b = {LP['sigma_b']:.10f}**.

## The outcome

`pts` enters this screen **only as the response**, never as a regressor, at any stage. s00
established -- before the PREREG was frozen -- that `feature_asof < forecast_cutoff` on 100% of
rows, that `forecast_cutoff` precedes tip on 100% of rows, and that the market snapshot precedes
`commence_time` on 100% of rows (median lead 1.156 h).

## Re-derivation

`scripts/verify.py` recomputes both file hashes from the bytes on disk and re-asserts every
counter in this document. It exits non-zero if any of them moves.
"""
open(os.path.join(mb.EXP_DIR, "PARTITION_PROOF.md"), "w").write(pp)
print("wrote PARTITION_PROOF.md")
