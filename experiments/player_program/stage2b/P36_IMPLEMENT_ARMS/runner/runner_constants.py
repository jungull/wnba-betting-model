#!/usr/bin/env python3
"""runner_constants.py -- every frozen pin the P36 shared runner enforces, in one file.

Every value here is carried from a FROZEN source (P35_FREEZE_TASK_CARDS/SPEC.json, which carries
the P33 shared blocks by hash reference, amended by shared_frozen_amendments). Nothing in this
file is a tuning knob. Changing any value is a preregistration deviation and VOIDS the affected
arm (P35 shared_frozen_amendments.quasi_poisson_v2_retirement_disposal
.response_family_deviation_clause).

Sources, by pin:
  * estimation objective (quasi-Poisson IRLS, log link, tol 1e-10 on deviance change, 100
    iterations): P33 SPEC.json inference_spec_gap_resolution.estimation_objective_frozen_here,
    carried by P35 (task_cards carry_convention).
  * seed manifest: P33 SPEC.json seed_manifest_plan (master_seed 20260806; derivation string
    reproduced verbatim below), carried by P35.
  * bootstrap sizes: P33 inference.resampling (B=10,000 test) and inference.coefficient_inference
    (B=2,000 train refit, percentile 95%).
  * K7 symmetric NA rule: P35 shared_frozen_amendments.estimator_symmetry_rules.
  * intercept invariant: P35 shared_frozen_amendments.intercept_structure
    .no_implementation_default_intercept_invariant.
  * guard byte pins: P33 inference.guards_at_call_site (P22, P25) plus this node's live
    measurement of P23/P26/P27 bytes at implementation time (recorded so P37/P38 can detect
    drift between implementation and execution).
  * team_cities.csv pin: P35 shared_frozen_amendments.franchise_continuity_receipt_pin.
  * blinding: P36 mandate -- the runner REFUSES to run against real folds unless an explicit
    P38_UNSEALED environment flag exists.
"""
from __future__ import annotations

# ---------------------------------------------------------------- frozen estimation objective
IRLS_TOL = 1e-10                 # absolute change in Poisson deviance between iterations
IRLS_MAX_ITER = 100              # hitting the cap in a POINT fit => arm/fold UNEVALUABLE (K7)
LINK = "log"                     # containment forces log given the receipted log-scale offset

# ---------------------------------------------------------------- frozen inference scaffold
B_TEST_BOOTSTRAP = 10_000        # game-cluster test bootstrap draws per fold (paired)
B_TRAIN_REFIT = 2_000            # training-cluster refit draws per fold (coefficient intervals)
COEF_INTERVAL_LEVEL = 0.95       # percentile interval
ROW_WEIGHTS = "equal per team-game row"

# ---------------------------------------------------------------- frozen seed manifest
MASTER_SEED = 20260806
SEED_DERIVATION = ("seed(purpose, fold_id, b) = first 4 bytes of "
                   "sha256(utf8('{master_seed}|{fold_id}|{purpose}|{b}')) as big-endian "
                   "unsigned int")
SEED_PURPOSE_TEST = "test_bootstrap"
SEED_PURPOSE_TRAIN = "train_refit"

# ---------------------------------------------------------------- frozen column conventions
OFFSET_COL = "log_exposure"                         # receipted; the ONLY offset object
INCUMBENT_PROJECTION_COL = "projected_team_off_possessions"
TARGET_COL_REAL = "realised_team_off_possessions_reg_equiv"
CLUSTER_COL = "game_id"
INTERCEPT_COL = "intercept"      # a GLOBAL intercept enters a design ONLY as this explicit
                                 # column of ones, identically in arm and null (P35 intercept
                                 # table); no implementation default may add one

DECLARED_FAMILY_ALL_FITTED_ARMS = "SUBSTANTIVE"     # P35 p25_guard_invocation_pins
RECALIBRATION_DECLARATION = "NOT_APPLICABLE"        # no RECALIBRATION arm survives this cycle

# ------------------------------------------------- frozen intercept table (P35 intercept_structure)
# The global intercept column is present if and only if this table says so, IDENTICALLY in arm
# and null. No implementation-default intercept may enter ANY design.
ARMS_WITH_FREE_GLOBAL_INTERCEPT = frozenset({"A07", "A12", "A13", "A14", "A15"})
ARMS_WITHOUT_GLOBAL_INTERCEPT = frozenset({
    "A02", "A03", "A05", "A06", "A08", "A09", "A10", "A11", "A16", "A17", "A18",
    "A20", "A21", "A22", "A23", "A24", "A25", "A26"})

# ---------------------------------------------------------------- blinding
UNSEAL_ENV_FLAG = "P38_UNSEALED"
# structural signatures of the real universe / contract schedule; any match is treated as a
# real-fold run attempt (fail closed without the flag)
REAL_UNIVERSE_ROW_COUNTS = frozenset({2982, 2990})
REAL_UNIVERSE_CLUSTER_COUNTS = frozenset({1491, 1495})
# frozen real input artifacts, by bytes
REAL_ARTIFACT_SHA256 = frozenset({
    "c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18",  # team_possession_prior_v1.parquet
    "7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a",  # possessions_raw_v2.parquet
})
REAL_FOLD_IDS = ("train_lt_2022", "train_lt_2023", "train_lt_2024",
                 "train_lt_2025", "train_lt_2026")

# ---------------------------------------------------------------- frozen guard byte pins
# P22/P25 pins are the FROZEN values from P33 inference.guards_at_call_site; the other three are
# measured at P36 implementation time and pinned here so execution-time drift is detectable.
GUARD_SHA256_PINS = {
    "P22_postgame_surrogate_guard": "951e85132f470fdd939c8039958f0544413aaaa485da5dba7da9c1b9b73ceeda",
    "P23_merge_guard":              "b0e754194278d84b78a3e79af8a7b3996ab32521047093c735a5fe963ca3b7a8",
    "P25_offset_dependency_guard":  "c78e70b6a0603b15bd74dd4dd798ba698d962565e813b2eee8df9360cc100e95",
    "P26_validate_k0_matched":      "1fc798dae520a88d65c70d4e7ad7fcd2064851e45732d90b715ac2d7557d7e16",
    "P27_fold_estimability_guard":  "1fbec0d67c3a037184692b0a4320107344fc5dc715f1fbceb7314c59ddb25d2f",
}
TEAM_CITIES_SHA256_PIN = "10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d"
P35_SPEC_SHA256 = "68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32"

# ---------------------------------------------------------------- receipt schema
RECEIPT_SCHEMA = "p36_runner_receipt/1"
RUNNER_VERSION = "p36_shared_runner/1"
