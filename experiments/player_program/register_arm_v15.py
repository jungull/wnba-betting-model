#!/usr/bin/env python3
"""register_arm_v15.py — register `cbs_v15_player_oof_v5/1` BEFORE it is executed.

A new arm, not an amendment. `contract_baseline_suite_v14` and its registration in the shared
`experiments/registry.jsonl` are **frozen and untouched**: contract identity, config hash,
universe, snapshot hash, model designation and historical interpretation all stand exactly as
registered. This program does not write to that file.

WHY A NEW ARM WHEN THE ESTIMATOR CODE IS UNCHANGED
---------------------------------------------------
Because **the population being predicted is part of the model definition.** v15 fits and predicts
with logic inherited unchanged from v14 — the same estimator, standardizer, lambda and alpha
selection, masks, calibration, dispersion and emission objects — but over a different candidate
universe, with different history-accounting fields and different cold-start and fallback
semantics. The config hash, contract hash and universe identity therefore must change, and calling
that an amendment to v14 would make two different populations share one identity.

**v15 is NOT an accuracy improvement over v14** and must not be described as one until the
common-row and universe effects are separated. Nothing is scored here.

The registry written is `experiments/player_program/arm_registry.jsonl`, owned by the player
program. It follows the shared registry's `extra.frozen_config` convention exactly, so
`cbs_v7.recompute_registered_config_hash` can bind an arm to it unchanged.

Run::

    python experiments/player_program/register_arm_v15.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ARM_REGISTRY = HERE / "arm_registry.jsonl"

ARM_ID = "cbs_v15_player_oof_v5"


def config_hash_of(frozen: dict) -> str:
    """The shared registry's convention: canonical JSON minus the self-reference."""
    payload = json.loads(json.dumps(frozen))
    payload.get("hashes", {}).pop("config_hash_value", None)
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


FROZEN: dict = {
    "arm_id": ARM_ID,
    "spec_doc": "experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md",

    # ---- what is INHERITED, unchanged ------------------------------------
    "estimator_inheritance": {
        "claim": "fitting and prediction logic are inherited UNCHANGED from "
                 "contract_baseline_suite_v14",
        "inherited_by_reference_not_by_copy": [
            "cbs_generator.logistic_fit", "cbs_generator.logistic_predict",
            "cbs_generator.Standardizer", "cbs_generator.player_split",
            "cbs_generator.prefix_mean", "cbs_generator.select_alpha_bound",
            "cbs_v5.select_lambda_chronological", "cbs_v5.dispersion", "cbs_v5.residuals",
            "cbs_v7.walk_forward_ewma", "cbs_v7.conditional_center",
            "cbs_v7.build_walk_forward_plan", "cbs_v7.player_fallback_level",
            "cbs_v8.stage_a_features_v8", "cbs_v8._emit", "cbs_v8._finish",
            "cbs_v8._provenance_rows",
        ],
        "runner_fork": {
            "id": "cbs_player_runner/15",
            "forked_from": "cbs_player_runner_v14.run_player_fold",
            "permitted_diff": "EXACTLY ONE line: the identity-binding call, rebound from v14's "
                              "registration to v15's. No estimator, mask, tuning, calibration, "
                              "availability gate, conditional history or grouping rule differs.",
            "diff_is_checked_at_test_time": True,
        },
        "model_form_changed": False,
    },

    # ---- what CHANGED, and why that forces a new identity -----------------
    "row_universe": "prediction_contract_v5",
    "row_universe_changed": True,
    "row_universe_supersedes": "prediction_contract_v4",
    "what_changed": {
        "candidate_universe": {
            "v4": 35627, "v5": 44851,
            "tier_a": 35629, "tier_b": 9222,
            "v4_rows_lost": 0,
            "superset_property": "every v4 obligation is a v5 obligation; v5 only ADDS",
            "appearing_players_missed_v4": 977, "appearing_players_missed_v5": 210,
        },
        "history_accounting": {
            "retired": "n_prior_games",
            "added": ["n_prior_candidate_obligations", "n_prior_appearances",
                      "n_prior_team_games"],
            "why": "n_prior_games meant prior candidate games for p_active on fitted folds and "
                   "prior appearances for all four targets on the degenerate fold. One column, "
                   "meaning conditioned on fold and target (P-D3).",
        },
        "cold_start_and_fallback_semantics": {
            "is_cold_start": "derives from n_prior_appearances",
            "new_row_level_fields": ["universe_tier", "candidate_source",
                                     "team_assignment_source", "team_assignment_confidence",
                                     "candidate_evidence_time", "candidate_published_time",
                                     "candidate_observed_time", "is_fallback", "cutoff_source"],
        },
        "identity_consequence": ("config hash, contract hash and universe identity all change. "
                                 "The population being predicted is part of the model "
                                 "definition, so this is a NEW ARM even though the estimator "
                                 "code is byte-identical."),
    },

    # ---- the Tier policy, declared BEFORE execution -----------------------
    "tier_fitting_policy": {
        "id": "tier_a_fit_only/1",
        "registered_before_execution": True,
        "primary": {
            "tier_a": "TRAINS and scores the primary model",
            "tier_b_transaction": "receives a prediction, SEPARATELY LABELLED and separately "
                                  "evaluated; does NOT enter the training frame",
            "tier_b_s2_only": "receives a fallback/sensitivity prediction; does NOT influence "
                              "the primary fit",
            "tier_c": "receives NO prediction",
        },
        "why": ("9,222 Tier B candidates -- 5,053 of them S2-sole-source with a 0.87% appearance "
                "rate -- would otherwise flood the availability model as ordinary negative "
                "examples and move the learned base rate and every coefficient. That would be a "
                "different model wearing the same name."),
        "training_frame_restriction": "train = Tier A rows of strictly earlier seasons ONLY",
        "prediction_frame": "ALL tiers of the fold season, so every obligation receives a slot",
        "known_residual_influence": {
            "what": ("Tier B rows still enter the shared walk-forward HISTORY frame, because a "
                     "Tier B row that appeared is a real game the player played. It therefore "
                     "contributes to later rows' EWMA centres within the same (player, season)."),
            "is_it_coefficient_influence": False,
            "why_it_is_retained": ("excluding real appearances from a player's own history would "
                                   "make the history LESS correct, not more -- those games are "
                                   "exactly the ones v4 was missing. It is measured and reported "
                                   "rather than silently accepted."),
            "must_be_reported": True,
        },
        "alternative_is_a_separate_challenger": (
            "training ON Tier B rows changes the learned availability base rate and coefficients "
            "and must be preregistered as its own arm, never folded into this one"),
    },

    # ---- evidence regimes, which may not be pooled ------------------------
    "evidence_regimes": {
        "tier_a": {"regime": "A", "use": "primary historical player-model evaluation"},
        "tier_b_transaction": {
            "regime": "B",
            "use": "audited reconstruction / sensitivity regime, NOT fully point-in-time "
                   "historical evidence",
            "why": "the transaction wire has real per-row effective dates but was observed in a "
                   "single 2026-07-30 scrape with no preserved historical publication timestamp",
        },
        "tier_b_s2_only": {
            "regime": "B, weak",
            "use": "reported SEPARATELY from transaction-derived Tier B; a weak candidate prior, "
                   "not verified membership",
            "measured": {"sole_source_rows": 5053, "of_which_appeared": 44,
                         "appearance_rate_pct": 0.87, "nonappearance_rate_pct": 99.13},
        },
        "tier_c": {"regime": "excluded and audited",
                   "residual_appearing_players_missed": 210},
        "pooling_prohibited": ("Tier A, transaction-derived Tier B and S2-only Tier B may not be "
                               "pooled into one headline historical result"),
        "completeness_claim_prohibited": ("v5 does NOT have complete historical roster coverage; "
                                          "210 appearing players remain missed and are reported"),
    },

    "controls": {
        "v4_reproduction_control": {
            "required_before_interpreting_v5": True,
            "requires": ["original row count", "original selected parameters",
                         "original prediction digest", "original validation receipts",
                         "original coverage"],
            "on_failure": "STOP before scoring v5; a difference would be code or fitting drift "
                          "rather than a universe effect",
        },
    },

    "immutable": {
        "contract_baseline_suite_v14": "frozen; registration, config hash, universe, snapshot "
                                       "hash, model designation and historical interpretation "
                                       "all unchanged",
        "prediction_contract_v4": "not edited, not amended, not regenerated",
        "shared_experiments_registry": "not written by the player program",
        "no_globals_were_monkey_patched": True,
    },

    "evidence_label": ("generation and validation only. Nothing is scored. No accuracy, "
                       "calibration, Brier, log-loss, MAE, RMSE, pinball, interval-coverage, "
                       "threshold, edge, return or profitability figure is computed, and no "
                       "forecast is compared to any outcome. 'Coverage' means OBLIGATION "
                       "COMPLETENESS."),
    "not_an_accuracy_claim": ("v15 must NOT be described as an accuracy improvement over v14 "
                              "until the common-row and universe effects are separated"),
    "hashes": {"config_hash_value": None},
}


def main() -> int:
    frozen = json.loads(json.dumps(FROZEN))
    h = config_hash_of(frozen)
    frozen["hashes"]["config_hash_value"] = h

    existing = []
    if ARM_REGISTRY.exists():
        existing = [json.loads(ln) for ln in
                    ARM_REGISTRY.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if any(r.get("experiment_id") == ARM_ID for r in existing):
        print(f"{ARM_ID} already registered; registry is append-only and nothing was written")
        print(f"config_hash = {h}")
        return 0

    record = {
        "schema": "player_program_arm_registry/1",
        "kind": "arm",
        "experiment_id": ARM_ID,
        "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "registered_before_execution": True,
        "board": None,
        "extra": {"frozen_config": frozen},
    }
    with ARM_REGISTRY.open("a", encoding="utf-8", newline="") as fh:
        fh.write(json.dumps(record, sort_keys=False) + "\n")
    print(f"registered {ARM_ID}")
    print(f"config_hash = {h}")
    print("\nBind cbs_v15.REGISTERED_CONFIG_HASH to this value.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
