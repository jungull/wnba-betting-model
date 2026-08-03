#!/usr/bin/env python3
"""register_tier_policy_erratum.py — `tier_a_fit_only/1` described its own influence too weakly.

`/1` said Tier B rows entering later histories were "not coefficient influence". That is wrong,
and the correction matters because it is the difference between a policy that describes what it
does and one that understates it.

Excluding Tier B rows as fitting TARGETS does not exclude them from the fit. An observed Tier B
game changes the EWMA and other historical features of **later Tier A training rows**, and those
changed feature values can change selected hyperparameters, fitted coefficients, calibration and
every later prediction. That is indirect fitting influence, arriving through legitimate historical
observation.

It is not leakage and not a defect. Once a game has occurred the player's performance is
historically knowable and ordinarily *should* enter subsequent form estimates. What was wrong was
the description, not the behaviour.

`tier_a_fit_only/1` is superseded by `tier_a_target_fit_with_observed_history/1`. `/1` is NOT
mutated; this is an appended erratum under its own experiment_id, for the same reason the design
erratum has one — a record sharing an id would silently rebind the arm under last-wins
recomputation.

Run::

    python experiments/player_program/register_tier_policy_erratum.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM_REGISTRY = HERE / "arm_registry.jsonl"
ERRATUM_ID = "tier_policy__erratum_indirect_history_influence"

POLICY_ID = "tier_a_target_fit_with_observed_history/1"

RECORD = {
    "schema": "player_program_arm_registry/1",
    "kind": "erratum",
    "experiment_id": ERRATUM_ID,
    "applies_to": "cbs_v15_player_oof_v5",
    "supersedes_policy": "tier_a_fit_only/1",
    "new_policy_id": POLICY_ID,
    "defect_in_the_prior_description": (
        "tier_a_fit_only/1 stated that Tier B rows entering later histories were 'not coefficient "
        "influence'. Too strong. Excluding Tier B rows as fitting TARGETS does not exclude them "
        "from the fit: an observed Tier B game changes the EWMA and other historical features of "
        "LATER TIER A TRAINING ROWS, and those changed feature values can change selected "
        "hyperparameters, fitted coefficients, calibration and every later prediction."),
    "why_it_is_nevertheless_permitted": (
        "once the game has occurred the player's actual performance is historically knowable, and "
        "ordinarily it SHOULD enter subsequent form estimates. Excluding it would make a player's "
        "own history less correct -- those are exactly the games v4 was missing. The behaviour is "
        "right; the description was not."),
    "policy": {
        "id": POLICY_ID,
        "clauses": [
            "only Tier A rows contribute TARGET LOSS to the primary fit",
            "all cutoff-valid previously observed player performances may contribute to later "
            "HISTORY FEATURES",
            "transaction Tier B and S2-only Tier B rows do not contribute their own target loss",
            "no target-game or future outcome enters its own or an earlier feature",
            "indirect influence through later Tier A feature construction is EXPLICITLY "
            "PERMITTED and MEASURED",
        ],
        "measurement_required": [
            "Tier B appeared rows admitted into later histories",
            "later Tier A rows whose features change because of them",
            "which feature families change",
            "fitted folds whose selected parameters change",
            "prediction differences on common v14/v15 Tier A rows",
            "earliest date any Tier B history affects a later Tier A prediction",
        ],
        "sensitivity_required": {
            "what": "a diagnostic build in which Tier B historical observations are EXCLUDED "
                    "from feature history",
            "purpose": "ATTRIBUTION, not selection",
            "explicitly_not": "a search for the better result; it does not become a promotion "
                              "arm unless it materially differs",
        },
    },
    "not_mutated": True,
    "why_a_separate_experiment_id": (
        "a record sharing cbs_v15_player_oof_v5's id would silently rebind the arm's config hash "
        "under last-wins recomputation"),
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
    print(f"tier_a_fit_only/1 -> {POLICY_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
