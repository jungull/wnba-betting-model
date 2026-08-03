#!/usr/bin/env python3
"""register_v15_design_erratum.py — `cbs_v15_player_oof_v5/1` is a DESIGN registration.

`/1` was written before any Stage-1.5 implementation file existed. Its `config_hash`
`81b3593a…` therefore hashes a *design*, and cannot honestly be said to cover code that had not
yet been written. This appends an erratum saying so.

`/1` is **not mutated**. The registry is append-only and this record carries a DIFFERENT
`experiment_id`, deliberately: appending another record under `cbs_v15_player_oof_v5` would make
`recompute_registered_config_hash` — which takes last-wins for an id — silently rebind the arm's
identity to a different frozen config. That would be exactly the class of quiet redefinition the
whole identity mechanism exists to prevent.

Execution must bind to `cbs_v15_player_oof_v5/2`, registered separately once Stage 1.5 passes,
carrying exact hashes for every implementation file.

Run::

    python experiments/player_program/register_v15_design_erratum.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM_REGISTRY = HERE / "arm_registry.jsonl"
ERRATUM_ID = "cbs_v15_player_oof_v5__erratum_design_only"

RECORD = {
    "schema": "player_program_arm_registry/1",
    "kind": "erratum",
    "experiment_id": ERRATUM_ID,
    "applies_to": "cbs_v15_player_oof_v5",
    "applies_to_revision": 1,
    "status": "cbs_v15_player_oof_v5/1 is a DESIGN REGISTRATION and is NOT execution-bound",
    "why": (
        "/1 was registered before the Stage-1.5 implementation existed. Its config hash "
        "81b3593a349569738d6fb9b1459958d0137158f99720986821037fbd9d198748 hashes a design: the "
        "arm's intent, universe, tier policy and evidence regimes. It does not and cannot cover "
        "prediction_contract_v5_enrich.py, a v5 real-frame builder, a v15 arm wrapper, a v15 "
        "player runner, a v15 OOF runner or their validators, because none of those files "
        "existed when it was written."),
    "what_remains_true_of_slash_1": [
        "the tier fitting policy tier_a_fit_only/1, registered before execution",
        "the evidence-regime separation and the prohibition on pooling them",
        "the statement that v15 is a new arm because the population is part of the model "
        "definition",
        "the requirement of a v4 reproduction control before interpreting v5",
        "the prohibition on calling v15 an accuracy improvement over v14",
    ],
    "not_mutated": True,
    "why_a_separate_experiment_id": (
        "appending another record under `cbs_v15_player_oof_v5` would make "
        "recompute_registered_config_hash — which takes LAST WINS for an id — silently rebind the "
        "arm to a different frozen config. A distinct id keeps /1 frozen and readable."),
    "execution_requires": {
        "revision": "cbs_v15_player_oof_v5/2",
        "must_carry_exact_hashes_for": [
            "prediction contract v5 (player_game.parquet)",
            "the v5 enrichment adapter",
            "the v5 real-frame builder",
            "the v15 arm wrapper",
            "the v15 player runner",
            "the v15 OOF runner",
            "the validators",
            "the tier policy",
            "the source-universe snapshot",
        ],
        "registered_before": "generating any real v15 artifact",
    },
    "control_that_stands": {
        "arm": "contract_baseline_suite_v14",
        "universe": "prediction_contract_v4",
        "artifact": "experiments/cbs_v14_player_oof/attempt_001",
        "n_obligations": 35627, "n_forecast_rows": 142508, "n_folds": 6,
        "fan_in_valid": True, "n_exclusions": 0,
        "outcome_columns_in_forecast_outputs": 0,
        "claims_no_reproduction_of_a_previously_existing_artifact": True,
    },
}


def main() -> int:
    existing = []
    if ARM_REGISTRY.exists():
        existing = [json.loads(ln) for ln in
                    ARM_REGISTRY.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if any(r.get("experiment_id") == ERRATUM_ID for r in existing):
        print("erratum already registered; nothing written")
        return 0
    rec = dict(RECORD)
    rec["registered_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with ARM_REGISTRY.open("a", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(rec, sort_keys=False) + "\n")
    print(f"registered {ERRATUM_ID}")
    print("cbs_v15_player_oof_v5/1 is now labelled DESIGN ONLY; execution requires /2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
