#!/usr/bin/env python3
"""register_arm_v15_rev2.py — the EXECUTION-BOUND registration `cbs_v15_player_oof_v5/2`.

`/1` is a design registration and is labelled so by its own erratum. `/2` is what execution binds
to, and it carries an exact SHA-256 for every file and artifact whose bytes can change what the
arm produces. `cbs_v15.verify_implementation_bytes` re-hashes all of them from disk at identity
time, so the arm cannot run against code its registration does not describe.

`/1` is **not mutated**. This record has its own `experiment_id`, so last-wins recomputation
cannot rebind `/1`.

Run::

    python experiments/player_program/register_arm_v15_rev2.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ARM_REGISTRY = HERE / "arm_registry.jsonl"
RECORD_ID = "cbs_v15_player_oof_v5__rev2"

#: Every file whose bytes can change what the arm produces.
IMPLEMENTATION = (
    "prediction_contract_v5.py",
    "prediction_contract_v5_enrich.py",
    "cbs_real_frames_v5.py",
    "cbs_v15.py",
    "cbs_player_runner_v15.py",
    "run_player_oof_v15.py",
)

#: Validators and the inherited estimator chain. Hashed so a change is visible even though these
#: are not v15's to modify.
INHERITED = (
    "cbs_v14.py", "cbs_player_runner_v14.py", "cbs_player_history_v14.py",
    "cbs_real_frames_v3.py", "cbs_v8.py", "cbs_v7.py", "cbs_v5.py",
    "cbs_generator.py", "cbs_builders.py",
    "contract_validator_v4_strict.py", "cbs_provenance_v4.py", "cbs_identity_v3.py",
    "cbs_obligation_key.py", "run_player_oof_v14.py",
)

ARTIFACTS = (
    "experiments/prediction_contract_v5/player_game.parquet",
    "experiments/prediction_contract_v5/player_game_enriched.parquet",
    "experiments/prediction_contract_v5/candidacy_exclusions.parquet",
    "experiments/prediction_contract_v5/contract.json",
)

SOURCE_SNAPSHOT = (
    "data/masters/master_player.parquet",
    "data/masters/master_team.parquet",
    "experiments/prediction_contract_v4/player_game.parquet",
    "data/injury_history/injury_history.csv",
    "data/injury_capture/injury_log.csv",
)

TESTS = (
    "tests/test_prediction_contract_v5.py",
    "tests/test_prediction_contract_v5_enrich.py",
    "tests/test_cbs_v15.py",
)


def sha(rel: str) -> str | None:
    p = REPO / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def config_hash_of(frozen: dict) -> str:
    payload = json.loads(json.dumps(frozen))
    payload.get("hashes", {}).pop("config_hash_value", None)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_frozen() -> dict:
    return {
        "arm_id": "cbs_v15_player_oof_v5",
        "arm_revision": 2,
        "revision_note": ("/1 is a DESIGN registration written before these files existed and is "
                          "labelled so by its own erratum. /2 is execution-bound."),
        "supersedes_revision": 1,
        "row_universe": "prediction_contract_v5",
        "row_universe_changed_vs_v14": True,

        "estimator_inheritance": {
            "claim": "fitting and prediction logic inherited UNCHANGED from "
                     "contract_baseline_suite_v14",
            "frame_fork": {
                "id": "cbs_real_frames/5", "forked_from": "cbs_real_frames/3.build_player_frame",
                "generated_at_import_from_inspect_getsource": True,
                "n_seams": 5, "n_changed_lines": 16,
                "seams": ["input: read the enriched v5 contract",
                          "carried_columns: keep the tier and evidence columns",
                          "train_filter: the training frame is Tier A only",
                          "universe_columns: the universe carries the tier columns",
                          "scoreability: p_active scoreable on Tier A or on an appearance"],
            },
            "runner_fork": {
                "id": "cbs_player_runner/15",
                "forked_from": "cbs_player_runner_v14.run_player_fold",
                "generated_at_import_from_inspect_getsource": True,
                "n_seams": 1, "n_changed_lines": 2,
                "seam": "the identity-binding call, rebound to /2",
            },
            "estimator_objects_are_identical_not_copied": True,
            "n_estimator_objects_asserted_identical": 14,
            "no_formula_token_in_either_diff": True,
        },

        "tier_policy": {
            "id": "tier_a_target_fit_with_observed_history/1",
            "supersedes": "tier_a_fit_only/1",
            "clauses": [
                "only Tier A rows contribute TARGET LOSS to the primary fit",
                "all cutoff-valid previously observed player performances may contribute to "
                "later HISTORY features",
                "transaction Tier B and S2-only Tier B rows do not contribute their own target "
                "loss",
                "no target-game or future outcome enters its own or an earlier feature",
                "indirect influence through later Tier A feature construction is EXPLICITLY "
                "PERMITTED and MEASURED",
            ],
            "measured_influence_2022_fold": {
                "min_ewma": 2027, "played_share_l10_team_games": 704,
                "start_share_l5": 122, "days_since_last_appearance": 102,
                "note": "Tier A TRAINING rows whose features change when Tier B observations "
                        "are withheld from the history walk",
            },
            "sensitivity": {
                "flag": "--sensitivity",
                "purpose": "ATTRIBUTION, never selection",
                "not_a_promotion_arm_unless_it_materially_differs": True,
            },
        },

        "evaluation_tiers": {
            "A_primary": "primary target fitting and evaluation",
            "B_transaction_sensitivity": "sensitivity predictions, not target-loss rows",
            "B_s2_weak_fallback": "fallback predictions only",
            "C": "audit-only exclusions, never in the contract",
            "pooling_prohibited": True,
        },

        "authorised_scope": {
            "no_estimator_redesign": True, "no_feature_search": True,
            "no_threshold_tuning": True, "no_accuracy_driven_correction": True,
        },

        "controls": {
            "v14_v4_control": {
                "artifact": "experiments/cbs_v14_player_oof/attempt_001",
                "n_obligations": 35627, "n_forecast_rows": 142508, "n_folds": 6,
                "receipts": "31/31 PASS", "frozen": True,
                "claims_no_reproduction_of_a_previously_existing_artifact": True,
            },
        },

        "implementation_sha256": {rel: sha(rel) for rel in IMPLEMENTATION},
        "inherited_sha256": {rel: sha(rel) for rel in INHERITED},
        "artifact_sha256": {rel: sha(rel) for rel in ARTIFACTS},
        "source_snapshot_sha256": {rel: sha(rel) for rel in SOURCE_SNAPSHOT},
        "test_sha256": {rel: sha(rel) for rel in TESTS},
        "test_results": {
            "tests/test_prediction_contract_v5.py": "44/44",
            "tests/test_prediction_contract_v5_enrich.py": "106/106",
            "tests/test_cbs_v15.py": "31/31",
        },

        "evidence_label": ("generation and validation only. Nothing is scored. No accuracy, "
                           "calibration, Brier, log-loss, MAE, RMSE, pinball, "
                           "interval-coverage, threshold, edge, return or profitability figure "
                           "is computed, and no forecast is compared to any outcome."),
        "not_an_accuracy_claim": ("v15 must NOT be described as an accuracy improvement over v14 "
                                  "until the common-row and universe effects are separated"),
        "immutable": {
            "contract_baseline_suite_v14": "frozen and untouched",
            "prediction_contract_v4": "not edited, not amended, not regenerated",
            "shared_experiments_registry": "not written by the player program",
            "cbs_v15_player_oof_v5_rev1": "not mutated; its DESIGN ONLY erratum stands",
        },
        "hashes": {"config_hash_value": None},
    }


def main() -> int:
    frozen = build_frozen()
    missing = [k for k, v in {**frozen["implementation_sha256"],
                              **frozen["artifact_sha256"]}.items() if v is None]
    if missing:
        raise SystemExit(f"cannot register: these files are absent: {missing}")

    h = config_hash_of(frozen)
    frozen["hashes"]["config_hash_value"] = h

    existing = []
    if ARM_REGISTRY.exists():
        existing = [json.loads(ln) for ln in
                    ARM_REGISTRY.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if any(r.get("experiment_id") == RECORD_ID for r in existing):
        print(f"{RECORD_ID} already registered; append-only, nothing written")
        print(f"config_hash = {h}")
        return 0

    record = {
        "schema": "player_program_arm_registry/1",
        "kind": "arm",
        "experiment_id": RECORD_ID,
        "arm_id": "cbs_v15_player_oof_v5",
        "arm_revision": 2,
        "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "registered_before_execution": True,
        "extra": {"frozen_config": frozen},
    }
    with ARM_REGISTRY.open("a", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(record, sort_keys=False) + "\n")
    print(f"registered {RECORD_ID}")
    print(f"config_hash = {h}")
    print(f"  implementation files: {len(frozen['implementation_sha256'])}")
    print(f"  inherited files     : {len(frozen['inherited_sha256'])}")
    print(f"  artifacts           : {len(frozen['artifact_sha256'])}")
    print(f"  source snapshot     : {len(frozen['source_snapshot_sha256'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
