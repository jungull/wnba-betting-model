#!/usr/bin/env python3
"""merge_ledger_updates.py -- the SINGLE WRITER that merges the eight discovery-wave
result sets into HYPOTHESIS_LEDGER.json.

Design constraints:

  * ONE writer. The eight workstreams ran in eight separate git worktrees off the same
    base commit (eb1103c) and every one of them deliberately declined to edit the shared
    ledger. This script is the only thing that writes it.
  * DETERMINISTIC. No wall-clock timestamps, no randomness, no dict iteration on unordered
    input. Commit dates come from git, not from `now()`.
  * IDEMPOTENT. Each workstream entry is rebuilt from the frozen preregistration keys
    (exactly the keys make_ledger.py wrote) plus a freshly derived merge block. Running
    this over an already-merged ledger reproduces the same bytes.
  * IT ACTUALLY READS THE SOURCES. Artifact hashes are computed from the real files, and
    every workstream carries PROBES: live reads of its own result JSON that are asserted
    against the values recorded below. If a source artifact changes, the merge ABORTS
    rather than silently recording a stale narrative.

The prose in RESULTS below is derived from the workstreams' own artifacts. Where a
workstream supplied its own ledger patch (ws3, ws5, ws7, ws8) its wording is carried
through rather than paraphrased. Nulls and negative results are preserved verbatim; no
finding is softened.

Usage:  python merge_ledger_updates.py [--worktrees-root PATH] [--check]
        --check validates and diffs without writing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "HYPOTHESIS_LEDGER.json"
RECEIPT = HERE / "LEDGER_MERGE_RECEIPT.json"

# The keys make_ledger.py froze. Everything else in an entry is rebuilt by this script,
# which is what makes the merge idempotent.
PREREG_KEYS = (
    "basketball_mechanism",
    "exact_formulation",
    "expected_direction",
    "data_and_provenance",
    "supports_hypothesis",
    "falsifies_or_weakens",
    "known_confounders",
    "metrics",
    "development_only",
)

# feature_gate.py blob sha256 at each relevant commit. Recomputed from git at run time and
# asserted, so these cannot drift silently.
GATE_BLOBS = {
    "eb1103c": "3f8d707213e70206ecb930cd2d829c78ad33720729e38af6060319751a8d286c",
    "55f4500": "76dbc437d538ebf9ef57ecc794406b81ca4d8d890cbde4a1d58ca56a74c271b0",
    "42af2cd": "b064c2c4675d354ec5cb5c6647782634c8139ca4233a5d732f408b6c2532f9a7",
}

WAVE_BASE_COMMIT = "eb1103c"

SKIP_DIR_NAMES = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


# --------------------------------------------------------------------------------------
# source registry
# --------------------------------------------------------------------------------------

SOURCES = {
    "ws1_repaired_projected_role": {
        "worktree": "agent-a062ec7d27d10b55b",
        "subdir": "ws1",
        "result_commit": "5313ebd",
        "preregistration_commit": None,
        "superseded_commits": ["3726991"],
        "primary_artifact": "WS1_RESULTS.json",
    },
    "ws2_responsibility_transfer": {
        "worktree": "agent-a366d924a9b4dfcd5",
        "subdir": "ws2",
        "result_commit": "863a900",
        "preregistration_commit": "8116b7d",
        "superseded_commits": [],
        "primary_artifact": "WS2_VERDICT.json",
    },
    "ws3_team_total_plus_allocation": {
        "worktree": "agent-a96f23f70cffc45d0",
        "subdir": "ws3",
        "result_commit": "1e3509f",
        "preregistration_commit": None,
        "superseded_commits": [],
        "primary_artifact": "LEDGER_UPDATE_ws3.json",
    },
    "ws4_ewma_timescale_family": {
        "worktree": "agent-a578166bb62b091a5",
        "subdir": "ws4",
        "result_commit": "1b634fb",
        "preregistration_commit": "a6d5cd4",
        "superseded_commits": [],
        "primary_artifact": "WS4_VERDICT.json",
    },
    "ws5_opportunity_proxies": {
        "worktree": "agent-ab8223114ea98f146",
        "subdir": "ws5",
        "result_commit": "6d9e3f2",
        "preregistration_commit": "059db0d",
        "superseded_commits": [],
        "primary_artifact": "WS5_VERDICT.json",
    },
    "ws6_mechanism_decomposition": {
        "worktree": "agent-abba0a0dbf84578f1",
        "subdir": "ws6",
        "result_commit": "5ef1f25",
        "preregistration_commit": None,
        "superseded_commits": [],
        "primary_artifact": "WS6_MECHANISM_DECOMPOSITION.json",
    },
    "ws7_nonlinear_heterogeneous": {
        "worktree": "agent-ab4ac90b1f887b5b7",
        "subdir": "ws7",
        "result_commit": "e858e96",
        "preregistration_commit": "58b3a91",
        "superseded_commits": [],
        "primary_artifact": "WS7_LEDGER_UPDATE.json",
    },
    "ws8_operational_error_decomposition": {
        "worktree": "agent-a5694dab4e5ccdb3d",
        "subdir": "ws8",
        "result_commit": "c1d2637",
        "preregistration_commit": None,
        "superseded_commits": [],
        "primary_artifact": "WS8_LEDGER_RESULT.json",
    },
}

# Live reads asserted against recorded values. (artifact, key-path, expected)
PROBES = {
    "ws1_repaired_projected_role": [
        ("WS1_RESULTS.json", ["verdict_block", "verdict"], "falsifies"),
        ("WS1_RESULTS.json", ["verdict_block", "arms_beating_K0_with_ci_excluding_zero"], []),
        ("WS1_RESULTS.json",
         ["coefficient_stability", "operational", "L1_linear", "expanded_role_bounded", "sign_consistent"], True),
    ],
    "ws2_responsibility_transfer": [
        ("WS2_VERDICT.json", ["disposition"],
         "NULL PRESERVED. Does not qualify as a challenger to Arm D. Recorded as development evidence only."),
        ("WS2_VERDICT.json", ["paired_team_mae_operational", "vs_K0_honest_control", "T2", "excludes_zero"], False),
        ("WS2_VERDICT.json", ["player_level_operational_vs_K0", "T2", "excludes_zero"], True),
    ],
    "ws3_team_total_plus_allocation": [
        ("LEDGER_UPDATE_ws3.json", ["workstream"], "ws3_team_total_plus_allocation"),
    ],
    "ws4_ewma_timescale_family": [
        ("WS4_VERDICT.json", ["hypothesis_verdict"], "NOT_SUPPORTED"),
        ("WS4_VERDICT.json", ["hypothesis_verdict_by_track", "operational",
                              "gated_or_dual_superior_in_any_unstable_stratum"], []),
        ("WS4_VERDICT.json", ["hypothesis_verdict_by_track", "intrinsic",
                              "gated_or_dual_superior_in_any_unstable_stratum"], []),
    ],
    "ws5_opportunity_proxies": [
        ("WS5_VERDICT.json", ["verdict", "result"], "PARTIAL SUPPORT -- allocation only; expected direction FALSIFIED"),
        ("WS5_VERDICT.json", ["verdict", "expected_direction"],
         "FALSIFIED. Play-ending involvement does not beat FGA share in any role. r(x1, x3) = 0.994."),
    ],
    "ws6_mechanism_decomposition": [
        ("WS6_MECHANISM_DECOMPOSITION.json", ["verdict"],
         "REJECTED_AS_CAUSE__HETEROGENEITY_REAL_BUT_NOT_OFFSETTING"),
        ("WS6_MECHANISM_DECOMPOSITION.json",
         ["card_criteria_evaluated", "card_expected_direction", "met"], False),
        ("WS6_MECHANISM_DECOMPOSITION.json",
         ["card_criteria_evaluated", "identified_cause_instead", "n_mechanisms_with_beta_between_below_beta_within"], 9),
    ],
    "ws7_nonlinear_heterogeneous": [
        ("WS7_LEDGER_UPDATE.json", ["patch", "result"], "NULL on the hypothesis; REFUTED on the operational decision metric"),
        ("WS7_LEDGER_UPDATE.json", ["patch", "disposition"], "DO NOT CARRY FORWARD"),
    ],
    "ws8_operational_error_decomposition": [
        ("WS8_LEDGER_RESULT.json", ["patch", "incremental_deltas_primary_ordering",
                                    "team_possession_total_projection", "verdict"],
         "SIGNIFICANTLY POSITIVE — the only addressable source"),
        ("WS8_LEDGER_RESULT.json", ["patch", "conditional_rate_contribution", "ratio_to_floor"], 0.9969),
    ],
}


# --------------------------------------------------------------------------------------
# the merged result content, derived from the artifacts above
# --------------------------------------------------------------------------------------

RESULTS = {
    "ws1_repaired_projected_role": {
        "result": (
            "FALSIFIED on the registered decision rule. The rule was: the primary arm must beat the "
            "K0 intercept-only recalibration control on operational team MAE with a 90% game-clustered "
            "CI excluding zero. L1_linear vs K0 = -0.00145 (CI [-0.00792, +0.00477]); N1_split vs K0 = "
            "-0.00378 (CI [-0.01170, +0.00343]). ZERO arms beat K0 with a CI excluding zero. Against the "
            "unfitted Arm D the arms look better (L1 +0.00181, D0_change_only +0.00583) but K0 -- no "
            "features at all -- already collects +0.00326 of that, so the apparent gain is free "
            "recalibration, not role. Card criteria: 'role CHANGE positive on turnover rate' is NOT what "
            "was fitted -- the role_change coefficient is NEGATIVE and sign-consistent in all five folds "
            "(mean -0.02144, sd 0.00801). "
            "SURVIVING SIGNAL, preserved and not promoted: the bounded material-expansion ramp "
            "expanded_role_bounded carries coefficient +0.02647 (sd 0.00175), positive in every one of the "
            "five walk-forward folds 2022-2026, and +0.02533 (sd 0.00290) in the change-only arm. That is a "
            "COEFFICIENT, not an MAE gain. "
            "Where it pays, and where it does not: on the INTRINSIC track the 699 team-games with material "
            "expansion favour L1 by +0.00763 vs D and +0.01314 vs K0 (CI [-0.00032, +0.02771] -- includes "
            "zero), while the 2,283 team-games without are -0.00633 vs D and -0.00995 vs K0 (CI "
            "[-0.01750, -0.00371] -- EXCLUDES zero, i.e. significantly WORSE). On the OPERATIONAL track -- "
            "the decision track -- the split is 946/1,968 and the sign REVERSES: L1 vs D is -0.00758 on the "
            "expansion games and +0.00632 on the rest; vs K0 it is -0.00261 and -0.00089, neither excluding "
            "zero. The segment lead is therefore real only under realised exposure and does not survive the "
            "move to projected exposure."
        ),
        "disposition": "FALSIFIED",
        "valid_decision_result": (
            "Falsified. Neither preregistered primary arm beats the K0 recalibration control on operational "
            "team MAE; no arm in the family does. The gated expansion term is a narrow, non-significant, "
            "intrinsic-track-only lead that reverses sign operationally."
        ),
        "contaminated_runs": [
            {
                "commit": "3726991",
                "what": "the original WS1 run",
                "defect": (
                    "consumed turnover_p2_v1/turnover_role_context_features_v1.parquet columns "
                    "trailing_minutes_share, trailing_rotation_rank and role_change, whose null mask is an "
                    "EXACT post-cutoff did_appear indicator: 8,278 null rows = the non-appearers, 27,351 "
                    "non-null = the appearers, zero off-diagonal. Standardise-then-fillna encodes the "
                    "outcome into the design matrix."
                ),
                "superseded_by": "5313ebd",
                "effect_of_the_repair": (
                    "verdict UNCHANGED (falsifies, in both runs). The expansion coefficient is essentially "
                    "identical (+0.02651 sd 0.00171 contaminated -> +0.02647 sd 0.00175 repaired). What DID "
                    "move is the operational segmentation: the material-expansion team-game split went "
                    "702/2,212 -> 946/1,968 and L1's operational paired delta vs D flipped from +0.00481 "
                    "(with expansion) / +0.00227 (without) to -0.00758 / +0.00632. Any read of the "
                    "operational segment result taken from 3726991 is invalid."
                ),
            }
        ],
        "corrected_reruns": [
            {
                "commit": "5313ebd",
                "what": (
                    "discards the three defective P2 columns outright (never imputed) and rebuilds the "
                    "trailing-role state into ws1_trailing_role_state_v1.parquet with the same EWMA machine "
                    "(alpha=0.10, state snapshotted strictly before the day's games) but READING state for "
                    "every Tier A candidate rather than only appearers. All seven declared features are "
                    "non-null on all 35,629 operational rows, so no missingness indicator exists."
                ),
                "is_the_valid_run": True,
            }
        ],
        "formulation_dependence": (
            "This falsifies ONE formulation of the role hypothesis: projected-minutes-share level, "
            "role_change, rotation_rank_change and a [0.05, 0.10] bounded expansion ramp, entered linearly "
            "and in one preregistered positive/negative hinge split, under a Poisson ridge with lambda=10 "
            "and a log(exposure)+log(D) offset. It is NOT a null on 'role change affects turnover rate' in "
            "general. The bounded-ramp coefficient is stable and positive in every fold, which is a "
            "mechanism signal the MAE metric cannot resolve at the team grain."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "the expansion ramp knots (0.05 / 0.10) were preregistered, never tuned; a different material-expansion threshold is untested",
            "the role-change effect was only ever tested additively on the log rate; a multiplicative or exposure-side correction is untested",
            "exposure_error_attribution shows role_change correlates -0.336 with exposure error and rotation_rank_change -0.324, so these features may be an EXPOSURE-PROJECTION correction rather than a turnover-RATE effect -- that reading is untested as a model",
            "the segment result exists only under realised exposure; whether it survives an improved exposure projection is untested",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "WEAKLY, AND ONLY AS A NARROW GATED TERM",
            "what": (
                "expanded_role_bounded alone, as a single gated term, is the only candidate. Its coefficient "
                "is the most stable object in the whole workstream."
            ),
            "conditions": [
                "the evaluation TRACK must be frozen in advance: the lead exists on the intrinsic track and reverses on the operational track, so a challenger chosen after seeing both is not a test",
                "the with/without material-expansion strata must be preregistered, not read off this run",
                "it must be benchmarked against K0, not against unfitted Arm D",
                "on present evidence it does NOT clear the bar on the operational metric and must not be presented as if it does",
            ],
        },
    },

    "ws2_responsibility_transfer": {
        "result": (
            "NULL on the registered primary metric (operational team MAE). Against the K0 intercept-only "
            "control: T1_direct -0.0010 [-0.0051, +0.0034]; T2_allocated -0.0007 [-0.0057, +0.0047]; "
            "T3_role_sensitive -0.0002 [-0.0016, +0.0013]; T123 +0.0006 [-0.0051, +0.0065]. None excludes "
            "zero. All three constructions nominally beat the team-level H arm, but H is itself worse than "
            "doing nothing (-0.0040 [-0.0073, -0.0008] vs K0), so beating H says only that the T-arms avoid "
            "H's harm. The one CI exclusion in the family (T3 vs H, lower bound +0.0001) is one marginal "
            "exclusion among 28 registered comparisons. "
            "PRESERVED POSITIVE, at the player grain only: vs K0, T2_allocated +0.002250 "
            "[+0.002085, +0.002419] and T1_direct +0.001783 [+0.001647, +0.001920], both excluding zero, "
            "while the team-level H arm is significantly WORSE than doing nothing (-0.000247 "
            "[-0.000349, -0.000153]). That is exactly the contrast the hypothesis predicted. T3 is null "
            "even here (+0.000049). Coefficients on the transfer term are POSITIVE in all five folds and "
            "grow monotonically with training support; H's displaced_involvement is NEGATIVE in all five. "
            "Effect size: ~1.9% on the predicted rate for a 1 SD move, ~0.02 turnovers for a typical player. "
            "Redistribution was tested and REJECTED as the explanation for the team-level null -- the "
            "per-player perturbations ADD at the team grain (cancellation ratio 0.94-0.96, 1.0 = pure "
            "addition). The team metric can see the effect; the effect is two orders of magnitude too small."
        ),
        "disposition": "NULL PRESERVED",
        "valid_decision_result": (
            "Null vs K0 on operational team MAE. Does not qualify as a challenger to Arm D. The player-grain "
            "positive for T2 is preserved as development evidence, not as a promotion claim."
        ),
        "contaminated_runs": [],
        "corrected_reruns": [],
        "formulation_dependence": (
            "This is a null for THREE frozen constructions of responsibility transfer, measured on "
            "operational team-game MAE. It is not a null on the transfer mechanism. The mechanism is present, "
            "direction-correct and statistically clear at the player grain; the team-game metric has a noise "
            "floor roughly two orders of magnitude above the effect. A different metric, not a different "
            "feature, is what this result argues for."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "T3's role weighting zeroes 73% of rows (expansion is 0 for 71% of candidates) -- a softer or continuous role weighting is untested",
            "no adjustment was made for the two confounders named on the card (absences correlate with opponent quality and with the absent player's own rate); they plausibly INFLATE the small player-level positive",
            "the transfer term was never tested on a team metric with a lower noise floor, which is the only place a 2% rate effect could resolve",
            "the joint HT2 arm separates cleanly into offsetting terms (-0.018..-0.036 vs +0.019..+0.035) but is unstable out of sample and has the WORST team MAE of any arm (2.9719); a shrunk or constrained joint form is untested",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "ONLY AS T2, AND NOT AT THE TEAM-GAME GRAIN",
            "what": "T2 (allocated displaced load) alone. T1 is a noisier version of the same signal; T3 is null.",
            "conditions": [
                "evaluate at the player grain or on a team metric with a materially lower noise floor -- team-game MAE provably cannot resolve it",
                "benchmark against K0, never against unfitted Arm D",
                "adjust for opponent quality and the absent player's own rate before the player-level positive is believed",
            ],
        },
    },

    "ws3_team_total_plus_allocation": {
        "result": (
            "NULL. The two-stage formulation does not improve player identity and does not match the D "
            "aggregate on the team total. Stage 1 team MAE 3.00926 vs the frozen D aggregate 2.96745 "
            "(paired -0.04181, 90% CI [-0.07115, -0.01324]); against a K0 intercept-only control through "
            "the identical pipeline the nine stage-1 features add nothing (-0.00340, CI "
            "[-0.03975, +0.03398]). Stage 2 allocation, evaluated with the team total held EXACTLY at the D "
            "aggregate so the team metric is identical to the incumbent by construction, makes player "
            "identity WORSE: deviance 1.22854 -> 1.24366, MAE -0.00302 (CI [-0.00498, -0.00104]). Share "
            "calibration improves (slope 1.0293 -> 0.9703) while multinomial log loss degrades "
            "(2.26964 -> 2.27674). Allocated expectations sum to the stage-1 total exactly (max deviation "
            "1.07e-14). "
            "THE MOTIVATING OBSERVATION IS WITHDRAWN: arm G's 'aggregation cancellation' reading (player "
            "deviance 1.22854 -> 1.22717 while team MAE worsened 2.96745 -> 2.97251) rested on "
            "turnover_p2_v1/turnover_role_context_features_v1.parquet columns offensive_involvement_proxy, "
            "trailing_minutes_share and role_change, which are non-null on exactly the 27,351 appearing "
            "candidates and null on exactly the 8,278 non-appearing ones, zero off-diagonal -- an exact "
            "post-cutoff did_appear indicator. Refit through an identical pipeline the leaking column is "
            "worth 0.02180 player deviance over a cutoff-valid rebuild, 15.9x the entire published arm-G "
            "gain of 0.00137. The premise of the hypothesis is contaminated."
        ),
        "disposition": "NULL / FALSIFIED FOR THIS FORMULATION, WITH A REDIRECTION",
        "valid_decision_result": (
            "Null on both halves of the joint criterion, and the falsifier written on the card ('the "
            "allocation gain requires sacrificing team-total accuracy') is NOT what happened -- there was no "
            "allocation gain to trade. The decomposition instead localises the error: holding the D shares "
            "fixed and supplying the true candidate total is worth +0.04135 player MAE "
            "(CI [+0.03865, +0.04417]), roughly an order of magnitude more than any movement in the "
            "allocation layer. The D-proportional allocation is already near the achievable frontier for "
            "these features; the TEAM TOTAL is the binding constraint. This converges independently on ws8."
        ),
        "contaminated_runs": [
            {
                "commit": None,
                "what": "the hypothesis PREMISE, not a ws3 run",
                "defect": (
                    "the arm-G aggregation-cancellation observation that motivated the two-stage split was "
                    "measured on the leaking P2 role-context columns; on cutoff-valid inputs it is not "
                    "established. ws3's own fits are clean."
                ),
                "superseded_by": None,
                "effect_of_the_repair": (
                    "the motivating observation is withdrawn. The ws3 null stands independently of it."
                ),
            }
        ],
        "corrected_reruns": [],
        "gate_findings_for_the_wave": [
            "feature_gate.audit must be run on the TRAINING FOLD ACTUALLY BEING FITTED, not once on the pooled matrix. The 2021 projected-exposure regime gives every Tier A candidate on a team an identical projected possession share and an identical p_active, so the 2022 training fold's within-team design had std 7.8e-9 and 5.1e-17 while the POOLED design looked healthy. The gate blocks it as impossible_scaling the moment it is applied per fold.",
            "the gate is PAIRWISE and cannot see a multi-way exact linear dependency. proj_off_poss_share == proj_minutes_share exactly and role_change == proj_minutes_share - trailing_minutes_share, so three declared features span two dimensions. A supplementary SVD rank check is implemented in ws3/run_ws3_two_stage.py::rank_check.",
            "a feature construction that is safe under an additive link is not automatically safe under a compositional one. P2's EWMA decays player state only on days the player appeared while team state decays every team game, so the ratio is not a share (max 1.617). A log-offset Poisson absorbs that; a within-team softmax saturated to exact 0.0 and 1.0 shares, deviance 8.2465.",
            "in every one of these failures the optimiser converged -- stage 2 in five Newton iterations in every fold.",
        ],
        "formulation_dependence": (
            "This is a null for ONE two-stage construction: a Poisson team-total stage on nine features with "
            "a log(projected_team_off_possessions) offset, plus a conditional softmax allocation stage with "
            "ridge shrinkage and a log(pred_D) offset. It is NOT a null on 'separating total from "
            "allocation is a good idea'. The structural claim -- that the constraint can be enforced exactly "
            "-- was demonstrated (1.07e-14). What failed is the feature content of both stages, and stage 1 "
            "failed against an intercept, meaning the team-total features carry no information rather than "
            "the architecture being wrong."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "stage 1 loses catastrophically in 2022 (3.4319 vs 3.0745) where it trains on 406 team-games and wins 2023-2025; a formulation with a longer burn-in or cross-season pooling is untested",
            "the nine stage-1 features add nothing over a fitted intercept on projected possessions -- a stage-1 feature set built from possession/pace inputs rather than turnover inputs is untested, and ws8 says that is where the error actually lives",
            "Dirichlet-multinomial and shrunk-multinomial allocations named on the card were not the tested form; only the ridge softmax was",
            "whether an allocation layer helps once the team total is genuinely improved is untested -- ws3 could only test allocation against a total it could not improve",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "NOT FOR THE ALLOCATION LAYER; YES FOR THE TOTAL",
            "what": (
                "a challenger on the TEAM POSSESSION / TEAM TOTAL side. The allocation layer is at the "
                "frontier for these features and should not be re-attempted with them."
            ),
            "conditions": [
                "any stage-1 challenger must beat K0 through an identical pipeline, not just the D aggregate",
                "the per-fold gate must be run on the fold actually being fitted before any such fit",
                "converges with ws8's recommendation -- these should be ONE registered evaluation, not two",
            ],
        },
    },

    "ws4_ewma_timescale_family": {
        "result": (
            "FALSIFIED, AND IN THE OPPOSITE DIRECTION FROM THE HYPOTHESIS. The card predicted faster "
            "adaptation would help after role shifts while slow decay stayed better for stable roles. The "
            "evidence runs the other way: within this frozen family the error is MONOTONE IN MEMORY LENGTH "
            "-- longer memory is better and shorter memory is worse, in stable AND unstable strata alike. "
            "Pooled operational player MAE: V1_slow_season_memory 0.845712 < V6_gate_instant 0.846233 < "
            "V5_dual_precision 0.847078 < V7_gate_persist10 0.847544 < V4_dual_equal 0.847740 < "
            "V0_incumbent_alpha=0.10 0.847871 < V3_fast_role_responsive 0.852376. "
            "Faster decay (alpha=0.20, half-life 3.1 appearances) helps in NO stratum on either track; it is "
            "significantly WORSE than alpha=0.10 in every unstable stratum with enough rows to resolve. The "
            "single stratum where it is even directionally ahead is rookie_low_history, where "
            "empirical-Bayes shrinkage to the league rate dominates and all timescales nearly coincide. "
            "The GATE adds nothing: V6 equals the fast variant exactly on fired rows and the slow variant "
            "exactly elsewhere (confirmed to machine precision), so because fast LOSES on the fired rows, "
            "gating strictly DILUTES the slow variant's gain; V7's persistence window is worse still. "
            "Registered verdict: zero gated or dual variants are superior in ANY unstable stratum on either "
            "track, so the supporting clause fails outright -- the non-inferiority half in stable strata is "
            "moot. "
            "EFFECT-SIZE HONESTY, from the workstream itself: the largest pooled gain in the whole family is "
            "0.00216, about a quarter of one percent of the incumbent's MAE. It is resolvable at 35,629 rows "
            "and holds in all five nested folds, but it is not a material forecasting improvement."
        ),
        "disposition": "FALSIFIED (opposite direction)",
        "valid_decision_result": (
            "Hypothesis NOT_SUPPORTED on both the operational and intrinsic tracks by the preregistered "
            "C1-C4 selection rule applied mechanically. The family's own ranking points at SLOWER decay, "
            "which the family was not built to test."
        ),
        "contaminated_runs": [],
        "corrected_reruns": [],
        "formulation_dependence": (
            "This falsifies the specific frozen family: alpha=0.05 (one slower variant), the alpha=0.10 "
            "incumbent, alpha=0.20 fast, two dual short+long forms, and two role-change-gated forms. A null "
            "-- here, an inversion -- under this family is NOT a null on timescale in general. The workstream "
            "states explicitly that alpha=0.05 is NOT declared the right decay rate: the family contains "
            "exactly ONE slower variant, and reading its alpha off the aggregate and presenting it as "
            "confirmed is precisely what the preregistration forbids."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "the slow end of the timescale axis is tested at exactly one point (alpha=0.05); the optimum is unidentified and could be slower still",
            "the gate was triggered on role change; a gate on a different instability signal (trade, injury return, rotation-rank jump) is untested",
            "dual-timescale weighting was fixed (equal, and precision-weighted); a fitted or shrunk mixing weight is untested",
            "the team-game level does not resolve -- only ~2,900 team-games exist and almost every team-level interval spans zero, so the player-level ranking must NOT be restated as a team-level result. The one exception, V5_dual_precision at team level on 'all' (+0.00331, CI [+0.00038, +0.00625], excludes zero), is a single interval inside a large family and the workstream declines to claim it",
            "stratified TEAM-level numbers outside the 'all' stratum are partial-team sums, not full team totals; they are diagnostics only",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "YES -- BUT ON THE OPPOSITE AXIS FROM THE ONE THE CARD PROPOSED",
            "what": (
                "a preregistered grid of SLOWER decay rates (and only that), since the error is monotone in "
                "memory length across the tested range and the slow end is pinned by a single point."
            ),
            "conditions": [
                "the grid must be frozen before it is fitted; alpha=0.05 must not be adopted by reading it off this run",
                "alpha=0.10 remains the FROZEN registered incumbent -- nothing here promotes anything",
                "the challenger must state its metric grain in advance; the player-level gain is ~0.25% of MAE and the team grain does not resolve at ~2,900 team-games",
            ],
        },
    },

    "ws5_opportunity_proxies": {
        "result": (
            "PARTIAL. Six frozen proxies x three roles. As RATE PREDICTORS and as INTERACTIONS all six "
            "FAIL: none beats the recalibration-only control K0 on operational team MAE and five of six are "
            "significantly WORSE than it (R1 -0.00877, R2 -0.00263, R3 -0.00809, R5 -0.00332, R6 -0.00389, "
            "all with CIs excluding zero; R4 null at +0.00044). No interaction arm beats K0 either; X1 and "
            "X3 are significantly worse. Every one of them is significantly BETTER than K0 at the PLAYER "
            "level -- exactly the trap the P2 registration warned about and exactly the pattern P2 arm G "
            "showed. "
            "As PLAYER-ALLOCATION WEIGHTS five of six deliver a small, statistically clear, season-stable "
            "player-level gain over K0 at exactly zero team-level cost, because allocation arms are "
            "team-total-pinned by construction: WK1 +0.00175 [+0.00150, +0.00198], WK5 +0.00171, WK3 "
            "+0.00164, WK6 +0.00164, WK2 +0.00128, all excluding zero; WK4 is significantly negative "
            "(-0.00010). The no-proxy control WKfree, which renormalises identically, is significantly "
            "NEGATIVE (-0.00039), so the gain belongs to the PROXY and not to the renormalisation. "
            "EXPECTED DIRECTION FALSIFIED: play-ending involvement does NOT beat FGA share in any role. "
            "r(x1, x3) = 0.994 -- adding a 0.44-weighted free-throw-trip term and turnovers to an FGA share "
            "produces a near-no-op. x2 (per-36 intensity) is the only materially distinct construction "
            "(r ~ 0.65) and is the WEAKEST of the five allocation weights that work. "
            "The proxies are NOT redundant with the P1 EWMA correlationally (R^2 on log D from 0.0008 to "
            "0.2282) but ARE redundant with free recalibration in the rate role. "
            "MANDATORY DISCLOSURE, carried from the workstream: none of the six observes touches, passes, "
            "drives, time of possession or potential assists. No tracking data enters any of them. "
            "'Play-ending involvement' counts only possessions the player is recorded as having TERMINATED; "
            "a possession the player initiated, advanced or created for a teammate is invisible to all six."
        ),
        "disposition": "PARTIAL (allocation only); expected direction FALSIFIED; CLOSED for rate and interaction",
        "valid_decision_result": (
            "The card clause 'a proxy improves the conditional rate OR allocation beyond the P1 EWMA' is MET "
            "for ALLOCATION only, by x1, x2, x3, x5 and x6, against both Arm D and K0, positive in every "
            "fitted season. The rate and interaction roles are null to negative. Not promotable: the winning "
            "role cannot improve team-level turnover forecasts at all, by construction, and the player-level "
            "effect is ~0.2% of MAE."
        ),
        "contaminated_runs": [],
        "corrected_reruns": [],
        "shared_input_defect_found": (
            "ws5 independently found the same did_appear leak in "
            "turnover_p2_v1/turnover_role_context_features_v1.parquet (offensive_involvement_proxy, "
            "trailing_minutes_share, role_change: 27,351 non-null appearers / 8,278 null non-appearers, zero "
            "off-diagonal). ws5 CONSUMES NONE OF THEM -- all six proxies are rebuilt so state is read for "
            "every Tier A candidate and are non-null on all 35,629 operational rows. ws5's x1 reproduces the "
            "canonical FGA-share formula EXACTLY where the canonical is defined (max abs diff 0.0) and "
            "supplies genuine strictly-prior values on the 8,278 non-appearers, so ws5 R1 is the CLEAN "
            "re-measurement of P2 arm G: 2.97296 vs the published 2.9725, i.e. arm G had looked marginally "
            "better than it is (~+0.0005). The P2 arm-G conclusion is robust to the defect, but the clean "
            "number is ws5 R1's. See WS5_INPUT_DEFECT_RECEIPT.json. Canonical artifact not modified."
        ),
        "formulation_dependence": (
            "This closes SIX specific box-score constructions in THREE specific roles. It is not a null on "
            "'opportunity matters'. The disclosure above is the boundary of the claim: with no touches, "
            "passes, drives or time-of-possession data, ball-handling responsibility is only observed through "
            "possessions the player TERMINATED. A proxy built on tracking data is a different hypothesis and "
            "is entirely untested here."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "the whole opportunity axis is measured only through play-ENDING events; initiation, advancement and creation for teammates are unobserved and untested",
            "the free-throw trip weight was FROZEN at 0.44 and never varied",
            "x1 and x3 are correlated 0.994, so the six-proxy set really spans about three distinct constructions; a genuinely different construction is untested",
            "the allocation gain is measured only under a team-total-pinned allocation; whether it survives an unpinned allocation is untested and, per the workstream, structurally cannot help team totals",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "NO -- NOT ON ITS OWN",
            "what": (
                "the allocation finding is real, tiny, and structurally incapable of helping team totals. It "
                "does not justify a follow-on wave by itself."
            ),
            "conditions": [
                "it could only ride along inside a challenger whose primary claim is elsewhere",
                "do NOT pursue opportunity proxies as rate predictors or interactions; that direction is closed",
            ],
        },
    },

    "ws6_mechanism_decomposition": {
        "result": (
            "HYPOTHESIS REJECTED AS CAUSE; the real cause was identified instead. Verdict string from the "
            "artifact: REJECTED_AS_CAUSE__HETEROGENEITY_REAL_BUT_NOT_OFFSETTING. "
            "The card's SUPPORTS marker ('involvement helps one mechanism and hurts another with opposite "
            "signs') is technically MET -- bad_pass, bad_pass_out_of_bounds and lost_ball are significantly "
            "POSITIVE at 90% while traveling is significantly NEGATIVE, and mechanism heterogeneity is large "
            "(Q = 90.5028, df = 8, p = 3.68e-16, I2 = 0.912). The card's FALSIFIER ('all mechanisms respond "
            "in the same direction') is NOT met. But the card's EXPECTED DIRECTION -- that arm G's "
            "player-level gain and team-level loss ARISE FROM those offsetting effects -- is NOT met, for "
            "two independent reasons: (1) the count-weighted sum of mechanism coefficients (0.024214) "
            "reproduces the monolithic total coefficient (0.024297) almost exactly, because the positive "
            "mechanisms carry ~75% of all turnovers and the negative one ~9%; (2) giving every mechanism its "
            "own coefficient makes team MAE WORSE, not better -- sum-of-mechanisms 2.90961 vs monolithic G "
            "2.90673, a paired -0.002881 [-0.004243, -0.001719] over 2,982 team-games. If offsetting "
            "mechanism effects were the cause, modelling mechanisms separately would have recovered the loss. "
            "It does not. "
            "THE REAL CAUSE: the sign reversal that matters is WITHIN-team vs BETWEEN-team, not across "
            "mechanisms. offensive_involvement_proxy is a SHARE of team shot attempts, and 92.6% of its "
            "variance is within a team-game (within 0.896292 / between 0.071963 of total 0.968255). Arm G "
            "pools a POSITIVE within-team effect (beta_within +0.036064, se 0.005292) with a NEGATIVE "
            "between-team effect (beta_between -0.106881, se 0.020375) into ONE coefficient that the within "
            "variance dominates. The resulting coefficient allocates turnovers correctly BETWEEN TEAMMATES "
            "(player deviance improves) while pushing TEAM TOTALS the wrong way (team MAE degrades). The "
            "reversal holds in 9 of 9 fitted mechanisms -- beta_between < beta_within everywhere -- so it is "
            "a property of the FEATURE, not of the mechanism mix."
        ),
        "disposition": "REJECTED AS CAUSE (real cause identified)",
        "valid_decision_result": (
            "The offsetting-mechanism explanation for arm G is rejected. Separate mechanism modelling is not "
            "supportable and was not promoted. The operative finding is that a within-team share entered as "
            "a single pooled coefficient will systematically improve player allocation while degrading team "
            "totals -- which generalises to every share-valued feature in this programme, not just arm G."
        ),
        "contaminated_runs": [],
        "corrected_reruns": [],
        "formulation_dependence": (
            "The card's own supports-marker was met and its falsifier was not, yet the hypothesis still "
            "fails: sign heterogeneity across mechanisms is REAL but is not what produces arm G's behaviour. "
            "This is a rejection of a CAUSAL claim, not a null on mechanism heterogeneity -- mechanism "
            "coefficients genuinely differ (I2 = 0.912). Separately, ws6 did NOT test the within/between "
            "decomposition as a FORECASTER; it measured it as a diagnostic. The two-coefficient form is "
            "identified as the cause but is untested as a model."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "the within/between split of involvement is diagnosed, never fitted as a forecasting arm -- entering beta_within and beta_between as two separate coefficients is the indicated formulation and is UNTESTED",
            "three mechanism columns are absent from the target entirely (shot_clock, eight_second, excess_timeout), so the shot-clock mechanism named on the card could not be tested at all",
            "mechanism mix differs by source schema, which is confounded with season type; the source_schema_caveat applies specifically to the negative (traveling) arm",
            "six of the fifteen mechanisms lack the support to resolve a coefficient at 90%; their nulls are power limits, not evidence of absence",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "YES -- BUT FOR THE WITHIN/BETWEEN FORM, NOT FOR MECHANISM SPLITTING",
            "what": (
                "an arm that enters any share-valued feature as SEPARATE within-team and between-team "
                "coefficients rather than one pooled coefficient. This is the single most transferable "
                "finding in the wave."
            ),
            "conditions": [
                "mechanism-level splitting must NOT be carried forward -- it is measured and it is worse",
                "the within/between form must be registered and frozen before fitting; ws6 only diagnosed it",
                "it must be benchmarked against K0 on operational team MAE, since the whole point is the team grain",
            ],
        },
    },

    "ws7_nonlinear_heterogeneous": {
        "result": (
            "NULL on the hypothesis; REFUTED on the operational decision metric. No bounded nonlinear or "
            "heterogeneous formulation of role or involvement beats the frozen incumbent Arm D on "
            "operational team MAE, and none beats a zero-feature intercept-only recalibration baseline (K0). "
            "Zero of 7 variants beat Arm D with a CI excluding zero. One (W3_expansion_contraction) had a "
            "positive point estimate vs Arm D (+0.00221, CI [-0.00569, +0.01019]) which INVERTS to -0.00105 "
            "against K0. Five of seven are significantly WORSE than fitting no features at all. "
            "The card's falsifier is PARTIALLY met and it does not rescue the hypothesis: W1_pw_involvement "
            "beats L_involvement by +0.00284 [+0.00045, +0.00550] and W4_inv_x_minutes by +0.00363 "
            "[+0.00092, +0.00619], so linear and nonlinear are NOT indistinguishable -- but both remain "
            "below Arm D and significantly below K0. The nonlinear forms damage team accuracy LESS than the "
            "linear form does; they never open a gain. "
            "EXPECTED DIRECTION REFUTED for primary creators: after the leakage repair every arm is "
            "significantly NEGATIVE there (W1 -0.00204 vs K0, CI excluding zero) -- the leakage had been "
            "MASKING a real loss. Supported at player level only for secondary creators receiving expanded "
            "roles (W1 +0.00517 vs K0, 93% appearance rate, the one clean positive), but the linear arm "
            "already captures +0.00295 of it and it does not survive team aggregation. "
            "The card's own 'role tiers correlate with support' confounder was MEASURED, not assumed: "
            "log1p_player_support correlates 0.82 with offensive_involvement_proxy, so W5 is a joint "
            "usage/support test rather than a clean support test, and W5 was the single worst arm against K0 "
            "(-0.00873). Not a multiplicity artifact: 7 variants, 90% CIs, no correction, and zero positives "
            "against K0, so no positive requires a multiplicity defence."
        ),
        "disposition": "NULL on hypothesis; REFUTED on decision metric; DO NOT CARRY FORWARD",
        "valid_decision_result": (
            "Refuted on the operational decision metric against K0, and the verdict is UNCHANGED after the "
            "leakage repair. The failure mechanism was identified: Arm D is essentially unbiased on "
            "abrupt-role-change team-games (signed team error +0.0009) and over-predicts stable ones by "
            "+0.4254, so the needed correction is stratum-specific -- but every arm, INCLUDING K0 which has "
            "no features, applies a broadly uniform DOWNWARD shift, helping the over-predicted stable games "
            "and pushing the unbiased abrupt games into under-prediction. Against K0, has_abrupt_change is "
            "negative for six of seven variants with CIs excluding zero. Every arm improves player-row MAE "
            "(0.8479 -> ~0.8453) while worsening team MAE: under MAE on a low-count right-skewed target, "
            "shifting mass downward reduces per-row absolute error, but within-team-game shifts are "
            "correlated and do not cancel in the sum."
        ),
        "contaminated_runs": [
            {
                "commit": "e858e96",
                "what": "WS7_RESULTS_v1_leaky.json and ws7_predictions_{intrinsic,operational}_v1_leaky.parquet and gate_v1_leaky/ -- the contaminated FIRST PASS, preserved in the same commit as the repaired run rather than discarded",
                "defect": (
                    "did_appear leakage in the shared P2 prior-role columns. "
                    "turnover_p2_v1/turnover_role_context_features_v1.parquet columns trailing_minutes_share, "
                    "role_change, trailing_rotation_rank and offensive_involvement_proxy are built by "
                    "iterating the realised box score and left-merging onto the candidate universe; the null "
                    "pattern is an EXACT did_appear indicator (null 8,278 = non-appearers, non-null 27,351 = "
                    "appearers, zero off-diagonal). Standardise-then-fillna encodes that post-cutoff outcome "
                    "into the design. Found by coordinator amendment 2; ws7 had seen the crosstab and "
                    "misdiagnosed it as downstream candidate-precision."
                ),
                "superseded_by": "WS7_RESULTS.json (v2) in the same commit e858e96",
                "effect_of_the_repair": (
                    "verdict UNCHANGED. The repair moved the arms leaning hardest on the affected columns: "
                    "L_priorrole -0.00057 -> -0.00279 and W3b -0.00111 -> -0.00299. The leakage had been "
                    "FLATTERING the prior-role arms. It also emptied the no_prior_history stratum, which "
                    "under v1 held 8,278 rows of which 0 appeared and showed the largest gains -- proving "
                    "those gains were an artifact of the leaky nulls. Those rows redistributed into "
                    "low_usage, which now carries 38% non-appearers."
                ),
            }
        ],
        "corrected_reruns": [
            {
                "commit": "e858e96",
                "what": (
                    "build_trailing_v2.py rebuilds the same EWMA machine (alpha 0.10, strictly prior games) "
                    "but READS state for every Tier A candidate, not only appearers. Non-null on all 35,629 "
                    "operational rows. 'No prior history' falls from 8,278 rows (0 appeared) to 473 (71 "
                    "appeared). Canonical artifact untouched. Outputs WS7_RESULTS.json (v2), "
                    "ws7_trailing_role_features_v2.parquet and gate/."
                ),
                "is_the_valid_run": True,
            }
        ],
        "new_confound_found": {
            "name": "free-intercept recalibration",
            "detail": (
                "Every Poisson-ridge arm carries an unpenalised intercept that the unfitted Arm D does not. "
                "K0_intercept_only -- zero features, identical pipeline, offset and folds -- reaches "
                "operational team MAE 2.9642 versus Arm D 2.9675, a free +0.00326. ws7 independently "
                "reproduced the externally measured 2.96419."
            ),
            "scope": "affects EVERY arm in this programme benchmarked against unfitted Arm D, not just ws7",
            "recommendation": (
                "K0 should become a standing second baseline for the turnover channel. The confound is the "
                "same order of magnitude as every effect discovery wave 1 is hunting."
            ),
            "independently_confirmed_by": ["ws1", "ws2", "ws3", "ws5"],
        },
        "formulation_dependence": (
            "Seven bounded forms were tested: piecewise-linear, restricted cubic splines, "
            "expansion/contraction asymmetry, involvement x projected minutes, involvement x support, and "
            "partial pooling by within-fold role tier. This refutes THOSE forms on THIS metric. It is not a "
            "null on nonlinearity in general -- and the workstream's own failure analysis says a further "
            "functional form is the wrong next move regardless, because the residual structure is "
            "stratum-specific bias rather than curvature. A caveat the workstream flags itself: stratum cuts "
            "were frozen against the v1 distribution and were NOT retuned after the repair, so stratum SIZES "
            "are not comparable across v1 and v2 (has_abrupt_change team-games 1,339 -> 2,368)."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "the stratum-specific bias correction implied by the failure analysis is NOT a functional form and was never tested",
            "stratum thresholds were frozen against the contaminated v1 distribution and not retuned; the repaired role_change is differently distributed, so the strata themselves are a formulation choice made under contamination",
            "the one clean positive -- secondary creators receiving expanded roles, W1 +0.00517 vs K0 at player level -- was never tested as a standalone gated form",
            "partial pooling was by continuous role tier derived within each training fold; no unrestricted player-specific slopes were permitted by the card, so player-level heterogeneity is untested by construction",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "NO -- NOT FOR ANOTHER FUNCTIONAL FORM",
            "what": (
                "the workstream names two leads it considers worth more than any further functional form: "
                "(1) Arm D over-predicts stable team-games by +0.4254 while being near-unbiased on "
                "abrupt-role-change games, so a stratum-specific correction is better targeted than any "
                "smooth function of involvement; (2) the 8,278 non-appearing Tier A candidates carrying a "
                "mean 15.1 possessions of projected exposure -- a candidate-precision problem, not a "
                "rate-model problem."
            ),
            "conditions": [
                "any stratum-specific challenger must freeze its strata on repaired (v2) data, not on the v1 distribution",
                "K0 must be the benchmark",
                "note that ws8 finds the candidate-precision lead does NOT move the TEAM total (the 5x identity), so lead (2) is a player-grain lead only -- the two workstreams must be read together",
            ],
        },
    },

    "ws8_operational_error_decomposition": {
        "result": (
            "COMPLETE and DECISIVE ON DIRECTION -- a clear ordering was obtained; one source dominates, two "
            "are NULL and one is REVERSED. 2,914 team-games common to every counterfactual; target "
            "player_attributed; the frozen operational 2.9675 is reproduced EXACTLY by CF1. Counterfactual "
            "team MAE: CF1_full_operational 2.967451, CF2_oracle_appearance 2.9708, "
            "CF3_plus_missing_participants 2.971143, CF4_oracle_allocation 2.989249, CF5_realised_exposure "
            "2.885903. "
            "Sign convention: delta = MAE(before the fix) minus MAE(after the fix); POSITIVE means the fix "
            "REDUCES team MAE. Incremental ordering: team possession-total projection +0.103346 "
            "[+0.083268, +0.124435] SIGNIFICANTLY POSITIVE, the only addressable source; within-team "
            "minutes/possession allocation -0.018106 [-0.027573, -0.008861] SIGNIFICANTLY NEGATIVE, i.e. the "
            "ORACLE ALLOCATION IS WORSE than the model's; availability / candidate appearance -0.00335 "
            "[-0.01269, +0.00623] NULL; missing actual participants -0.000342 [-0.002028, +0.001287] NULL. "
            "Path-dependence check: a genuinely different ordering (possession total applied first) "
            "reproduces the ranking and every sign (+0.10731 / -0.00760 / +0.00069 / -0.01886). "
            "THE RATE IS AT THE NOISE FLOOR: with perfect exposure, team MAE is 2.885903 -- 97.25% of "
            "operational MAE -- against a Poisson MAD floor at those predictions of 2.894872, a ratio of "
            "0.9969. The frozen Arm D rate given oracle exposure is AT the irreducible count noise of the "
            "target. That 97.25% share is not modelling error and is not addressable. "
            "STRUCTURAL FINDING: the sum of projected_off_possessions over a team-game's Tier A candidates "
            "equals EXACTLY 5x projected_team_off_possessions (max abs dev 1.1e-13). Team prediction = "
            "T_team x exposure-weighted mean rate, and T_team does not depend on the candidate list, so "
            "candidate-set and allocation errors cannot change forecast VOLUME, only the weighted mean rate. "
            "Only the possession total and the rate can move the team forecast."
        ),
        "disposition": "DECISIVE ON DIRECTION",
        "valid_decision_result": (
            "The card's falsifier ('contributions are diffuse and none dominates') is NOT met. The card's "
            "expected direction ('exposure-side errors dominate rate error') is NOT supported in LEVEL terms "
            "-- the rate accounts for 97.25% of operational MAE and is irreducible -- but IS supported in "
            "ADDRESSABLE terms: every point of addressable error sits on the exposure side, and specifically "
            "in the team possession total. "
            "SCOPE LIMIT, carried verbatim in force: TEAM-level only. The 5x identity gives NO cancellation "
            "at the player level -- the 8,278 non-appearing candidate rows carry 4,283.18 predicted "
            "turnovers against 0 realised and are 14.18% of player-level absolute error. Deprioritising "
            "availability work is valid ONLY for the team total. "
            "ORACLE DISCLOSURE: CF2..CF5 consume post-cutoff information and are LABELLED DIAGNOSTICS ONLY -- "
            "not forecasts, not models, not promotion evidence, not registrable arms."
        ),
        "contaminated_runs": [],
        "corrected_reruns": [],
        "formulation_dependence": (
            "The two NULLs here (availability, missing participants) are nulls FOR THE TEAM TOTAL under the "
            "5x exposure identity, and the workstream says so explicitly and unprompted. They are NOT nulls "
            "at the player grain, where availability is 14.18% of absolute error. The negative result on "
            "within-team allocation is likewise metric-specific: oracle allocation being WORSE on team MAE "
            "does not mean the model's allocation is right, only that reallocating exposure toward actual "
            "participants moves the exposure-weighted mean rate unfavourably."
        ),
        "remaining_formulation_dependent_hypotheses": [
            "the decomposition holds Arm D FIXED; a different rate model could redistribute where the addressable error sits",
            "the rate's 0.9969 ratio to the Poisson MAD floor is conditional on the target being player_attributed turnovers with Poisson noise; a different target definition or noise model would move the floor",
            "the 5x identity is a property of the current projected_player_possessions/1 construction; if that construction changed, candidate-set errors could begin to move team volume",
            "only five labelled counterfactuals were run; interactions between error sources beyond the two tested orderings are untested",
        ],
        "may_justify_future_frozen_challenger": {
            "answer": "YES -- AND IT IS THE ONLY DIRECTION THE WAVE ENDORSES FOR TEAM MAE",
            "what": (
                "a challenger on the TEAM POSSESSION (pace) projection -- team_possession_prior_v1 / "
                "projected_team_off_possessions -- and nowhere else in this decomposition. ws3 converges on "
                "the same target from the opposite direction."
            ),
            "conditions": [
                "value is bounded and small, stated by the workstream: a 25-50% reduction in possession projection error buys +0.036 to +0.065 team MAE, i.e. 1.2-2.2% of operational MAE",
                "no oracle counterfactual may be registered as an arm or cited as promotion evidence",
                "do NOT deprioritise availability work on the strength of this result unless the objective is strictly the team total",
            ],
        },
    },
}


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(repo: Path, *args: str) -> str:
    """Read-only git. This script never runs a git write command."""
    forbidden = {"add", "commit", "checkout", "switch", "stash", "reset", "merge",
                 "rebase", "branch", "restore", "clean", "push", "apply", "cherry-pick"}
    if args and args[0] in forbidden:
        raise RuntimeError(f"refusing to run a git write command: {args[0]}")
    out = subprocess.run(["git", "-C", str(repo), *args],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {out.stderr.strip()}")
    return out.stdout.strip()


def hash_tree(root: Path) -> dict:
    """sha256 of every artifact under root, keyed by posix-relative path, sorted."""
    entries = {}
    for p in sorted(root.rglob("*"), key=lambda q: q.relative_to(root).as_posix()):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        if p.suffix in SKIP_SUFFIXES:
            continue
        entries[rel.as_posix()] = sha256_file(p)
    return dict(sorted(entries.items()))


def dig(obj, path):
    for key in path:
        obj = obj[key]
    return obj


def blob_sha256(repo: Path, commit: str, relpath: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{relpath}"],
                         capture_output=True, check=True)
    return hashlib.sha256(out.stdout).hexdigest()


# --------------------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------------------

def build(worktrees_root: Path) -> tuple[dict, dict]:
    coordinator = HERE.parents[2]          # .../worktrees/player-model-program
    gate_rel = "experiments/player_program/feature_gate.py"

    # 1. verify the gate blobs we reason about are the ones actually in the repo
    gate_actual = {c: blob_sha256(coordinator, c, gate_rel) for c in GATE_BLOBS}
    for c, expected in GATE_BLOBS.items():
        if gate_actual[c] != expected:
            raise SystemExit(f"ABORT: feature_gate.py at {c} is {gate_actual[c]}, expected {expected}")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    if ledger.get("schema") != "discovery_hypothesis_ledger/1":
        raise SystemExit(f"ABORT: unexpected ledger schema {ledger.get('schema')!r}")

    merged_ws = {}
    receipt_ws = {}

    for key in ledger["workstreams"]:
        if key not in SOURCES:
            raise SystemExit(f"ABORT: ledger workstream {key} has no registered source")
        src = SOURCES[key]
        res = RESULTS[key]

        wt = worktrees_root / src["worktree"]
        wsdir = wt / "experiments/player_program/discovery_wave_1" / src["subdir"]
        if not wsdir.is_dir():
            raise SystemExit(f"ABORT: {key} source directory missing: {wsdir}")

        # 2. verify the result commit exists and the worktree is parked on it, clean
        head = git(wt, "rev-parse", "HEAD")
        full = git(wt, "rev-parse", src["result_commit"] + "^{commit}")
        if head != full:
            raise SystemExit(f"ABORT: {key} worktree HEAD {head[:9]} != result commit {full[:9]}")
        subject = git(wt, "log", "-1", "--format=%s", full)
        cdate = git(wt, "log", "-1", "--format=%ad", "--date=short", full)
        dirty = [ln for ln in git(wt, "status", "--porcelain", "--",
                                  f"experiments/player_program/discovery_wave_1/{src['subdir']}").splitlines()
                 if "__pycache__" not in ln]
        if dirty:
            raise SystemExit(f"ABORT: {key} has uncommitted changes under {src['subdir']}: {dirty[:3]}")

        for c in src["superseded_commits"]:
            git(wt, "rev-parse", c + "^{commit}")
        if src["preregistration_commit"]:
            git(wt, "rev-parse", src["preregistration_commit"] + "^{commit}")

        # 3. the gate this workstream actually ran under
        gate_used = sha256_file(wt / gate_rel)
        gate_commit = next((c for c, h in gate_actual.items() if h == gate_used), "UNKNOWN")
        has_rank = gate_used == gate_actual["55f4500"] or gate_used == gate_actual["42af2cd"]
        has_missing = gate_used == gate_actual["42af2cd"]

        # 4. probe the real artifacts -- abort on any drift
        probe_log = []
        for artifact, path, expected in PROBES[key]:
            doc = json.loads((wsdir / artifact).read_text(encoding="utf-8"))
            got = dig(doc, path)
            if got != expected:
                raise SystemExit(
                    f"ABORT: probe drift in {key} :: {artifact}:{'.'.join(map(str, path))}\n"
                    f"  expected {expected!r}\n  got      {got!r}")
            probe_log.append({"artifact": artifact, "path": ".".join(map(str, path)), "value": got})

        # 5. artifact hashes
        hashes = hash_tree(wsdir)

        # 6. rebuild the entry: frozen prereg keys verbatim, then results, then merge block
        old = ledger["workstreams"][key]
        entry = {k: old[k] for k in PREREG_KEYS}
        entry["result"] = res["result"]
        entry["disposition"] = res["disposition"]

        merge = {
            "preregistration_commit": src["preregistration_commit"],
            "result_commit": full[:7],
            "result_commit_full": full,
            "result_commit_subject": subject,
            "result_commit_date": cdate,
            "superseded_commits": src["superseded_commits"],
            "source_worktree": src["worktree"],
            "source_path": f"experiments/player_program/discovery_wave_1/{src['subdir']}/",
            "wave_base_commit": WAVE_BASE_COMMIT,
            "feature_gate_in_force": {
                "sha256": gate_used,
                "commit": gate_commit,
                "includes_rank_and_conditioning_fix_55f4500": has_rank,
                "includes_informative_missingness_fix_42af2cd": has_missing,
                "note": (
                    "THIS RESULT PREDATES BOTH GATE FIXES. It ran under the eb1103c gate "
                    "(sha256 3f8d7072..., 4,628 bytes), which has neither the rank/conditioning check "
                    "(55f4500) nor the informative-missingness check (42af2cd). Both fixes are children of "
                    "eb1103c on the coordinator line and are NOT ancestors of any of the eight result "
                    "commits. Every gate audit recorded by any of the eight workstreams was run by the "
                    "pre-fix gate."
                ) if not (has_rank and has_missing) else
                "ran under a gate carrying both fixes",
            },
            "valid_decision_result": res["valid_decision_result"],
            "hypothesis_disposition": res["disposition"],
            "contaminated_original_runs": res["contaminated_runs"],
            "corrected_reruns": res["corrected_reruns"],
            "formulation_dependence": res["formulation_dependence"],
            "remaining_formulation_dependent_hypotheses": res["remaining_formulation_dependent_hypotheses"],
            "may_justify_future_frozen_challenger": res["may_justify_future_frozen_challenger"],
            "artifact_sha256": hashes,
            "artifact_count": len(hashes),
            "probes_verified": probe_log,
        }
        for extra in ("gate_findings_for_the_wave", "shared_input_defect_found", "new_confound_found"):
            if extra in res:
                merge[extra] = res[extra]

        entry["merge"] = merge
        merged_ws[key] = entry

        receipt_ws[key] = {
            "result_commit": full[:7],
            "preregistration_commit": src["preregistration_commit"],
            "superseded_commits": src["superseded_commits"],
            "source_worktree": src["worktree"],
            "disposition": res["disposition"],
            "feature_gate_sha256": gate_used,
            "feature_gate_commit": gate_commit,
            "gate_predates_55f4500": not has_rank,
            "gate_predates_42af2cd": not has_missing,
            "artifact_count": len(hashes),
            "artifact_sha256": hashes,
            "probes_verified": len(probe_log),
        }

    out = dict(ledger)
    out["workstreams"] = merged_ws
    out["merge_provenance"] = {
        "merged_by": "experiments/player_program/discovery_wave_1/merge_ledger_updates.py",
        "writer_model": "SINGLE WRITER. The eight discovery workstreams ran in eight separate worktrees "
                        "off base commit eb1103c and every one of them deliberately declined to edit this "
                        "shared file. Concurrent direct writes are forbidden; this script is the only "
                        "writer and is deterministic and idempotent.",
        "wave_base_commit": WAVE_BASE_COMMIT,
        "feature_gate_versions": {
            "eb1103c_prefix_gate": gate_actual["eb1103c"],
            "55f4500_rank_and_conditioning": gate_actual["55f4500"],
            "42af2cd_informative_missingness": gate_actual["42af2cd"],
        },
        "feature_gate_finding": (
            "ALL EIGHT result commits carry the eb1103c gate blob. Neither 55f4500 (rank/conditioning) nor "
            "42af2cd (informative missingness) is an ancestor of any of them, so no discovery result in this "
            "wave was audited by a gate carrying either fix. Three workstreams compensated by hand and said "
            "so: ws1 implemented its own SVD rank and condition-number check and an explicit leakage guard; "
            "ws3 implemented rank_check in run_ws3_two_stage.py and documented that the gate is pairwise and "
            "cannot see a multi-way exact linear dependency; ws5 and ws7 found the informative-missingness "
            "defect (the exact did_appear null pattern) by hand, which is precisely what 42af2cd was written "
            "to catch. Any gate audit recorded inside a ws directory should be read as a PRE-FIX audit."
        ),
        "cross_cutting_findings": [
            "FREE-INTERCEPT RECALIBRATION (found independently by ws7, ws1, ws2, ws3 and ws5): every fitted "
            "Poisson-ridge arm carries an unpenalised intercept that the unfitted Arm D does not. A "
            "zero-feature K0 control through the identical pipeline reaches operational team MAE 2.96419 "
            "against Arm D's 2.96745 -- a free +0.00326, the same order of magnitude as every effect this "
            "wave was hunting. Results benchmarked only against unfitted Arm D are not interpretable. K0 "
            "should become a standing second baseline.",
            "did_appear LEAKAGE in turnover_p2_v1/turnover_role_context_features_v1.parquet (found "
            "independently by ws1, ws3, ws5 and ws7): trailing_minutes_share, trailing_rotation_rank, "
            "role_change and offensive_involvement_proxy are non-null on exactly the 27,351 appearing "
            "candidates and null on exactly the 8,278 non-appearers, zero off-diagonal. The null mask is an "
            "exact post-cutoff outcome indicator. ws1 and ws7 rebuilt the signal leak-free; ws5 never "
            "consumed the columns; ws3 used the finding to withdraw the arm-G premise. The canonical "
            "artifact was NOT modified by any workstream.",
            "WITHIN-vs-BETWEEN TEAM SIGN REVERSAL (ws6): a share-valued feature entered as one pooled "
            "coefficient mixes a positive within-team effect with a negative between-team effect and will "
            "systematically improve player allocation while degrading team totals. This is the general form "
            "of the player-improves/team-degrades pattern that ws5, ws7 and P2 arm G all hit separately.",
            "THE TEAM TOTAL IS THE BINDING CONSTRAINT (ws8 directly, ws3 independently): 97.25% of "
            "operational team MAE is the conditional rate at its irreducible Poisson noise floor (ratio "
            "0.9969); the only addressable source is the team possession-total projection (+0.1033).",
        ],
        "binding_rule_restated": (
            "No discovery result in this wave replaces Arm D. Nothing here was appended to "
            "arm_registry.jsonl. Every workstream is DISCOVERY, development folds only."
        ),
    }
    # ------------------------------------------------------------------------------------
    # Wave status is DELIBERATELY multi-axis.
    #
    # Every hypothesis card carrying a non-PENDING `result` means only that the eight
    # discovery RUNS finished. It does NOT mean the wave is scientifically settled: the runs
    # executed under the pre-fix eb1103c gate, no comparison-parity contract existed while
    # they ran, and their retrospective integrity and decision classifications are still
    # being established. Collapsing those into one COMPLETE flag is exactly the conflation
    # this program keeps having to correct.
    # ------------------------------------------------------------------------------------
    out["wave_status"] = {
        "execution_status": "COMPLETE",
        "integrity_audit_status": "IN_PROGRESS",
        "comparison_audit_status": "IN_PROGRESS",
        "decision_status": "PROVISIONAL",
        "integration_status": "IN_PROGRESS",
        "overall": "NOT COMPLETE",
        "statement": ("Discovery executions are complete; retrospective integrity and decision "
                      "classifications are still in progress."),
        "why_not_complete": (
            "A non-PENDING result field records that a RUN finished, not that its result is "
            "established. Until the retrospective per-fold gate audit, the Layer A / Layer B "
            "comparison-parity results and the consolidated audit matrix are committed, every "
            "workstream carries at most a provisional decision status and the substantive "
            "ranking is not frozen."),
        "unblocks_when": [
            "every workstream carries a feature-design integrity classification with evidence",
            "every workstream carries a decision-validity classification with evidence",
            "the consolidated audit matrix is committed",
        ],
    }
    return out, {
        "schema": "discovery_ledger_merge_receipt/1",
        "wave": "discovery_wave_1",
        "ledger": "experiments/player_program/discovery_wave_1/HYPOTHESIS_LEDGER.json",
        "merged_by": "experiments/player_program/discovery_wave_1/merge_ledger_updates.py",
        "single_writer": True,
        "deterministic": "no wall-clock timestamps; commit dates from git; artifact order sorted",
        "idempotent": "entries rebuilt from frozen preregistration keys plus derived merge block",
        "wave_base_commit": WAVE_BASE_COMMIT,
        "feature_gate_versions": gate_actual,
        "all_eight_predate_both_gate_fixes": True,
        "workstreams": receipt_ws,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktrees-root", default=None)
    ap.add_argument("--check", action="store_true", help="validate only; do not write")
    args = ap.parse_args()

    root = Path(args.worktrees_root).resolve() if args.worktrees_root else HERE.parents[3]
    if not (root / "player-model-program").is_dir():
        raise SystemExit(f"ABORT: {root} does not look like the worktrees root")

    ledger, receipt = build(root)
    led_txt = json.dumps(ledger, indent=2) + "\n"
    rec_txt = json.dumps(receipt, indent=2) + "\n"

    # validate before writing
    json.loads(led_txt)
    json.loads(rec_txt)
    bad = [k for k, v in ledger["workstreams"].items()
           if v["result"] in ("PENDING", "", None) or v["disposition"] in ("PENDING", "", None)]
    if bad:
        raise SystemExit(f"ABORT: still PENDING: {bad}")
    if len(ledger["workstreams"]) != 8:
        raise SystemExit(f"ABORT: expected 8 workstreams, got {len(ledger['workstreams'])}")

    if args.check:
        same = LEDGER.exists() and LEDGER.read_text(encoding="utf-8") == led_txt
        print(f"check: ledger would be {'UNCHANGED (idempotent)' if same else 'MODIFIED'}")
        return 0

    LEDGER.write_text(led_txt, encoding="utf-8")
    RECEIPT.write_text(rec_txt, encoding="utf-8")

    print(f"merged {len(ledger['workstreams'])} workstreams -> {LEDGER.name}")
    for k, v in ledger["workstreams"].items():
        m = v["merge"]
        print(f"  {k:38s} {v['disposition']:52s} {m['result_commit']}  "
              f"{m['artifact_count']:3d} artifacts")
    print(f"receipt -> {RECEIPT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
