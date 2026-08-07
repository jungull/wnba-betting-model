#!/usr/bin/env python3
"""runner_constants.py -- every pinned number, path and hash the S36 runner enforces.

Epistemic status: IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

NOTHING here is a choice made at S36. Every value is carried from a frozen source:

  * S35_FREEZE_TASK_CARDS/SPEC.json  sha256 (recomputed at import time by verify_freeze_pins)
  * S33R_PREREGISTRATION_REPAIR/SPEC_V2.json sha256
    6402fc11b9118ef6978ca4feb4aec10e3b811209773b7ae5f03ba29962a8e945
    -- which carries the 17 element cards and 11 arm blocks BY HASH.

If a value below disagrees with the frozen bytes, the BYTES GOVERN and the disagreement is a
defect to report, never to reconcile silently (GRAPH_POLICY section 1).
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------------------------
# Roots. ROOT_PATH_RULE: the PROGRAM WORKTREE, never the live data worktree.
# --------------------------------------------------------------------------------------------
#: the program worktree root, derived from this file's own location (never from cwd, never from
#: an environment variable a caller could point at the drifted data worktree).
PROGRAM_WORKTREE = Path(__file__).resolve().parents[5]
NODE_DIR = Path(__file__).resolve().parents[1]

ROOT_PATH_RULE = (
    "every cycle-2 score node reads data/masters/master_team.parquet from the PROGRAM WORKTREE "
    "and verifies sha256 ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528 before "
    "building anything. The live data-worktree copy legitimately grows with the season and is "
    "INADMISSIBLE; measuring it is a defect of the same class that previously produced a "
    "1,508-cluster universe and a false 'artifacts missing' conclusion."
)
#: the sha256 of the copy that legitimately drifts. Reading a file with THIS hash is the defect
#: the rule names, so the runner refuses it by name rather than merely failing the pin.
KNOWN_DRIFTED_MASTER_TEAM_SHA256 = (
    "e8e35b539df2d13f2325e207b9fb2ba8b2e96da476eaa0ec877fcf5588a71c19")

# --------------------------------------------------------------------------------------------
# Input artifact pins (SPEC_V2 arms[].features_lineage[].sources[] + null_strength_floor byte pins)
# --------------------------------------------------------------------------------------------
INPUT_PINS: dict[str, str] = {
    "data/masters/master_team.parquet":
        "ad79ce5cdda7e058ba24be45243037252e3795a3e9f0c18cc41b3f12f3c38528",
    "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet":
        "5d1fc4c9af2334a6edd6ddffab91fe7cff5596578d9995937859a86cfc1e1452",
    "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet":
        "c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18",
    "data/reference/team_cities.csv":
        "10a544fdc52a9c80c1573437c9838b11815c9eafe6ac2cf052be17a2128ac42d",
}
SPEC_V2_PATH = ("experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/SPEC_V2.json")
SPEC_V2_SHA256 = "6402fc11b9118ef6978ca4feb4aec10e3b811209773b7ae5f03ba29962a8e945"
FREEZE_SPEC_PATH = ("experiments/player_program/stage3_score/S35_FREEZE_TASK_CARDS/SPEC.json")
COMPARISON_GATE_PATH = "experiments/player_program/comparison_gate.py"
COMPARISON_GATE_SHA256 = "c2d242581cc7551c6ce7d3aaf554f0cc18fd9b1f72677edd61ba95f91a7b5b92"

#: the four frozen column/join-key pins recomputed at S36 under R10 (see canon.py).
FROZEN_COLUMN_PINS = [
    {"artifact": "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet",
     "method_filter": "composite_pace_x_eff_v1", "sort_rule": "lexicographic on str(game_id) asc",
     "join_key_columns": ["game_id"],
     "join_key_sha256": "d3a4b7fac5399f8d5c7e27b969e8e9901e6e44846f95c42af7967aa7eb51d249",
     "column": "pred_margin", "n_values": 1465, "n_nan": 0,
     "column_sha256": "1d79ff3adeda3d66e26f3bda1702d36301da447d87828c474d488d793de44ff4"},
    {"artifact": "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet",
     "method_filter": "composite_pace_x_eff_v1", "sort_rule": "lexicographic on str(game_id) asc",
     "join_key_columns": ["game_id"],
     "join_key_sha256": "d3a4b7fac5399f8d5c7e27b969e8e9901e6e44846f95c42af7967aa7eb51d249",
     "column": "pred_total", "n_values": 1465, "n_nan": 0,
     "column_sha256": "16c312aba2f964682f4d20a694b09890f4488f0e5bcdf31f827946158e145f3d"},
    {"artifact": "experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet",
     "method_filter": "composite_pace_x_eff_v1", "sort_rule": "lexicographic on str(game_id) asc",
     "join_key_columns": ["game_id"],
     "join_key_sha256": "d3a4b7fac5399f8d5c7e27b969e8e9901e6e44846f95c42af7967aa7eb51d249",
     "column": "p_home", "n_values": 1465, "n_nan": 188,
     "column_sha256": "8a92c017e4f8606c3a7405116a455dc746493581454dc4dcbe1aab6d00b41989"},
    {"artifact": "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet",
     "method_filter": None,
     "sort_rule": "lexicographic on (str(game_id), str(team_id)) asc",
     "join_key_columns": ["game_id", "team_id"],
     "join_key_sha256": "6b8b2709af3890c40a2fbc14eec36f02a5eae048aece1480ce7f3929126dd59b",
     "column": "projected_team_off_possessions", "n_values": 2990, "n_nan": 8,
     "column_sha256": "9078790427e0c3357dd8fe6a337fcc96852bfbfedaac48d963f5686894ac71bd"},
]

# --------------------------------------------------------------------------------------------
# Universe (SPEC_V2.shared_universe, re-derived at S35 and again here)
# --------------------------------------------------------------------------------------------
UNIVERSE_CLUSTERS = 1491
UNIVERSE_ROWS = 2982
FULL_SCHEDULE_CLUSTERS = 1495
FULL_SCHEDULE_ROWS = 2990
#: D010 / cycle-1 P33 precedent: the four games of the first 2021 date are excluded.
D010_EXCLUDED_DATE = "2021-05-14"
D010_EXCLUDED_CLUSTERS = 4
PER_SEASON_CLUSTERS = {2021: 205, 2022: 239, 2023: 260, 2024: 262, 2025: 310, 2026: 215}
POOLED_TEST_CLUSTERS = 1286  # 239+260+262+310+215
D010_CAVEAT = ("the universe excludes the 2021 opening day; every cold-start figure is flattered "
               "by construction and no cold-start claim may cite the missing stratum")
STRICTLY_PRIOR_ROW_BASE = (
    "PINNED (S34 finding B2): every strictly-prior construction in this slate, arm and K0 alike, "
    "draws its prior rows from the 1,491-cluster / 2,982-row RESOLVED UNIVERSE - never from the "
    "1,495-cluster full schedule.")

FOLDS = {
    "train_lt_2022": {"train_seasons": [2021], "test_season": 2022,
                      "train_clusters": 205, "test_clusters": 239},
    "train_lt_2023": {"train_seasons": [2021, 2022], "test_season": 2023,
                      "train_clusters": 444, "test_clusters": 260},
    "train_lt_2024": {"train_seasons": [2021, 2022, 2023], "test_season": 2024,
                      "train_clusters": 704, "test_clusters": 262},
    "train_lt_2025": {"train_seasons": [2021, 2022, 2023, 2024], "test_season": 2025,
                      "train_clusters": 966, "test_clusters": 310},
    "train_lt_2026": {"train_seasons": [2021, 2022, 2023, 2024, 2025], "test_season": 2026,
                      "train_clusters": 1276, "test_clusters": 215},
}
FOLD_IDS = tuple(FOLDS)
GAMES_NEVER_SPLIT = ("the game cluster is the only admissible independent unit; games are never "
                     "split across folds or bootstrap draws (S30 section 2, F13 verbatim)")
INDEPENDENT_UNIT = "game_cluster"

# --------------------------------------------------------------------------------------------
# Inference (SPEC_V2.inference + seed_manifest_plan)
# --------------------------------------------------------------------------------------------
B_TEST = 10000
B_TRAIN_REFIT = 2000
MASTER_SEED = 20260807
SEED_DERIVATION = ("seed(purpose, fold_id, b) = first 4 bytes of "
                   "sha256(utf8('{master_seed}|{fold_id}|{purpose}|{b}')) as big-endian unsigned "
                   "int (cycle-1 P33 derivation, new master seed)")
SEED_PURPOSE_TEST = "test_bootstrap"
SEED_PURPOSE_TRAIN = "train_refit"
FITTING_DETERMINISM = (
    "all fits are deterministic (OLS, IRLS, closed-form MoM, pinned-init Newton for SC08 "
    "dispersion); no fit-time seed exists; any implementation introducing a stochastic fitting "
    "step violates this preregistration")
#: cycle-1 P36 operationalisation of the two-sided cluster-bootstrap p-value, carried unchanged.
TWO_SIDED_P_RULE = ("p = min(1, 2*min((1+#{delta_b <= 0})/(B+1), (1+#{delta_b >= 0})/(B+1)))")

# Deterministic estimator pins.
OLS_RCOND = None            # exact lstsq; no ridge unless the card pins one
IRLS_TOL = 1e-10
IRLS_MAX_ITER = 100
NEWTON_TOL = 1e-10          # SC08 dispersion
NEWTON_MAX_ITER = 200
E3_P_CLIP = (0.001, 0.999)  # SC08 card pin; E1/E2 carry p_clipping.applicable = False

# --------------------------------------------------------------------------------------------
# Blinding (GRAPH_POLICY section 7; S35 what_this_freeze_authorises.NOT_AUTHORISED_FITTING)
# --------------------------------------------------------------------------------------------
UNSEAL_ENV_FLAG = "S38_UNSEALED"
REAL_UNIVERSE_ROW_COUNTS = frozenset({UNIVERSE_ROWS, FULL_SCHEDULE_ROWS})
REAL_UNIVERSE_CLUSTER_COUNTS = frozenset({UNIVERSE_CLUSTERS, FULL_SCHEDULE_CLUSTERS})
REAL_FOLD_IDS = frozenset(FOLD_IDS)
REAL_ARTIFACT_SHA256 = frozenset(INPUT_PINS.values()) | {SPEC_V2_SHA256}
NOT_AUTHORISED_FITTING = (
    "This freeze does NOT authorise fitting. Fitting requires a PASSED S37 implementation audit. "
    "Until S37 passes, no arm and no K0 may be fitted and no performance number may be computed.")

# --------------------------------------------------------------------------------------------
# The slate
# --------------------------------------------------------------------------------------------
ARM_IDS = ("SC01_OPP_ADJ_INTERACTING", "SC02_A07_SCORE_TRANSIENT", "SC03_SEASON_CARRYOVER_PRIOR",
           "SC04_HCA_LEAGUE_DRIFT", "SC05_HCA_TEAM_OFFSETS", "SC06_SCHED_FATIGUE_DIFF",
           "SC08_SIGMA_MARGIN_MAP", "SC09_FAV_GAP_COMPRESSION", "SC10_FORM_TREND",
           "SC11_LEAGUE_TOTAL_DRIFT", "SC12_ROBUST_INPUT_WINSOR")
WITHDRAWN_ARM_IDS = ("SC07_REF_CREW_TOTALS",)
N_ELEMENT_CARDS = 17
N_ARM_BLOCKS = 11
ESTIMANDS = ("E1_GAME_TOTAL", "E2_FINAL_MARGIN_HOME", "E3_HOME_WIN_PROB")
PRIMARY_METRIC = {"E1_GAME_TOTAL": "mae", "E2_FINAL_MARGIN_HOME": "mae",
                  "E3_HOME_WIN_PROB": "brier_raw_model_probability"}

COMPOSITE_METHOD = "composite_pace_x_eff_v1"
FALLBACK_METHOD = "league_average_v1"
#: SPEC_V2 invariants.fallback_machinery, measured: 26 composite-uncovered clusters.
N_COMPOSITE_UNCOVERED = 26
COMPOSITE_UNCOVERED_BY_SEASON = {2021: 17, 2025: 3, 2026: 6}


def artifact_path(rel: str) -> Path:
    return PROGRAM_WORKTREE / Path(rel)


def assert_program_worktree() -> None:
    """Fail closed if this file is not sitting where ROOT_PATH_RULE says it must."""
    expect = PROGRAM_WORKTREE / "experiments" / "player_program" / "stage3_score" / \
        "S36_IMPLEMENT_ARMS" / "runner" / "runner_constants.py"
    if Path(__file__).resolve() != expect.resolve():
        raise RuntimeError(f"ROOT_PATH_RULE: runner is not in the program worktree layout: "
                           f"{Path(__file__).resolve()} != {expect}")
    if not (PROGRAM_WORKTREE / "data" / "masters" / "master_team.parquet").exists():
        raise RuntimeError("ROOT_PATH_RULE: master_team.parquet missing from the program worktree")
