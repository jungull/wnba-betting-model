#!/usr/bin/env python3
"""register_program_roadmap.py — freeze the program's expanded objective and its research process.

Three records, appended to `arm_registry.jsonl`:

1. ``player_program_objective_v2`` — the endpoint is a granular player-event forecasting and
   game-simulation system, not a generic RAPM/ORtg/DRtg summary.
2. ``player_archetype_discovery_layer`` — archetype discovery as a registered layer BETWEEN pooled
   models and player-specific specialisation.
3. ``player_program_capability_matrix_and_lanes`` — reconcile the expansion with the repository's
   original player-centric design, and establish the permanent two-lane discovery process.

**None of these authorises execution.** Each records a research programme and its ordering
constraints so that nothing is lost and nothing is silently restarted from scratch. The binding
immediate ordering is recorded on record 3.

Run::

    python experiments/player_program/register_program_roadmap.py
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARM_REGISTRY = HERE / "arm_registry.jsonl"
SCHEMA = "player_program_arm_registry/1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


OBJECTIVE = {
    "schema": SCHEMA,
    "kind": "program_objective",
    "experiment_id": "player_program_objective_v2",
    "supersedes_scope_of": "player_program_objective (implicit: a generic player-impact summary)",
    "registered_at": _utc(),
    "authorises_execution": False,
    "statement": (
        "the intended endpoint is a granular player-event forecasting and game-simulation system. "
        "It is not merely a generic RAPM, offensive rating or defensive rating."),
    "per_player_forecast_distributions": [
        "active status", "minutes", "offensive and defensive possessions",
        "field-goal attempts by available location/type", "made field goals conditional on attempts",
        "three-point attempts and makes", "free-throw attempts and makes",
        "offensive rebounds", "defensive rebounds", "assists",
        "turnovers separated by mechanism where possible", "steals", "blocks",
        "personal fouls", "points", "any other reliably supported event channel",
    ],
    "aggregation": ("these forecasts aggregate through the PROJECTED ROTATIONS to construct team "
                    "strengths and opponent-specific matchup interactions"),
    "natural_opportunity_denominators": {
        "rule": ("do not treat generic per-minute rates as the final target definition. Minutes "
                 "determine exposure; each event uses its natural opportunity denominator where "
                 "the data permit."),
        "examples": {
            "steals": "per defensive possession or steal opportunity",
            "blocks": "per blockable opponent attempt, rim attempt or two-point attempt",
            "defensive_rebounds": "per available opponent miss",
            "offensive_rebounds": "per available teammate miss",
            "assists": "per potential assist, touch or teammate conversion opportunity",
            "turnovers": "per touch, possession used, pass or drive",
            "fouls": "per defensive possession or opponent attack",
            "shot_makes": "conditional on attempts by shot type or location",
            "free_throw_makes": "conditional on projected attempts",
        },
        "weaker_proxies": ("where the ideal denominator is unavailable, REGISTER the weaker proxy "
                          "explicitly rather than presenting it as equivalent"),
    },
    "multi_stage_forecast_structure": [
        "probability the player is active",
        "projected minutes conditional on active",
        "projected offensive and defensive possessions",
        "projected event opportunities",
        "event probability or rate conditional on opportunity",
        "efficiency or conversion conditional on the event",
        "predictive distribution and uncertainty",
    ],
    "wave_process_per_target": {
        "P0": "contract and target design: event definition, opportunity denominator, prediction "
              "requirement, scoreability, cutoff, outcome isolation, baseline metric, "
              "conservation constraints",
        "P1": "pooled baselines: career rate, season-to-date rate, trailing EWMA, recent games, "
              "age and experience, starting/bench role, player archetype",
        "P2": "exposure and role: availability, projected minutes, projected possessions, usage, "
              "starter status, rotation position, teammate availability, lineup role",
        "P3": "team and opponent context: team pace, opponent pace, team style, opponent event "
              "rates, projected teammates, projected opposing personnel, mechanism-specific "
              "matchup features",
        "P4": "schedule and environment: rest, back-to-backs, travel distance, timezone changes, "
              "schedule density, home/away, altitude, venue, playoff context, officials where "
              "valid data exist",
        "P5": "individual heterogeneity: hierarchical or partially pooled player-specific effects "
              "and slopes. NOT unrestricted independent feature selection per player.",
        "P6": "nonlinear challengers, registered, only after strong linear/generalised baselines",
    },
    "player_specific_effect_requirements": [
        "adequate historical sample", "shrinkage toward the population effect",
        "repeated chronological out-of-sample improvement",
        "stability across more than one fold or season",
        "correction for the large number of player-feature hypotheses considered",
    ],
    "specialisation_hierarchy_default_is_partial_pooling": [
        "pooled league model", "player identity effect", "archetype or role effects",
        "hierarchical player-specific slopes",
        "specialised player model only when justified by out-of-sample evidence",
    ],
    "simulation_causal_order": [
        "active rosters", "minutes and rotations", "offensive and defensive possessions",
        "player opportunities", "attempts, turnovers and fouls", "shot outcomes",
        "rebounds, assists, steals and blocks", "player and team scoring",
        "uncertainty distributions",
    ],
    "accounting_constraints": [
        "team minutes sum to 200",
        "player possessions reconcile to team possessions",
        "rebounds originate from missed shots",
        "assists relate to made field goals",
        "made shots cannot exceed attempts",
        "player totals reconcile with team totals",
        "both teams' possession accounting is coherent",
    ],
    "correlation_requirement": ("preserve correlations between event channels rather than "
                               "independently sampling every statistic"),
    "relationship_to_p3": {
        "p3_is": "ONE potential summary of latent player impact, not the complete player model",
        "preserve": "frozen offensive, defensive and net P3 coefficients for later ablations",
        "defensive_coefficient_test": ("whether exposure-weighted projected defenders improve the "
                                       "OPPONENT-POINTS forecast. It is not required to be a clean "
                                       "standalone player-ranking metric to have aggregate value."),
        "do_not_conflate": [
            "generic latent impact", "mechanism-specific event skill",
            "individually interpretable player talent", "downstream aggregate forecast value",
        ],
        "each_requires": "its own validation",
    },
    "first_channels_after_exposure_and_p3": [
        "turnovers and steals", "offensive and defensive rebounds", "shot attempts and scoring",
        "blocks and rim events", "fouls and free throws", "assists",
    ],
}


ARCHETYPES = {
    "schema": SCHEMA,
    "kind": "research_layer",
    "experiment_id": "player_archetype_discovery_layer",
    "registered_at": _utc(),
    "authorises_execution": False,
    "position_in_hierarchy": "BETWEEN pooled models and player-specific specialisation",
    "purpose": ("test whether partially pooling players with similar roles and statistical "
                "profiles improves player-event forecasts"),
    "may_support": [
        "archetype-specific baselines", "archetype-specific feature effects",
        "matchup interactions between offensive and defensive archetypes",
        "stronger shrinkage for low-sample players",
        "detection of players who consistently deviate from their archetype",
    ],
    "not": "final talent rankings or permanent identities",
    "unit_of_clustering": {
        "prefer": "player-season or player-role-state observations",
        "not": "one immutable career archetype",
        "why": ["lineup changes", "teammate availability", "aging", "team changes",
                "starter versus bench usage", "changes in offensive responsibility",
                "changes in defensive assignment"],
        "persist": "the cluster assignment TIME and the features available at that time",
    },
    "feature_families": {
        "test_separately_first": "offensive and defensive archetypes, before any combined representation",
        "offensive": ["usage", "touches or possession involvement", "assist and turnover rates",
                      "shot-location distribution", "three-point attempt rate", "rim-attempt rate",
                      "free-throw rate", "offensive rebound rate",
                      "pace and transition involvement", "starter and bench role",
                      "minutes and possession share"],
        "defensive": ["steal and forced-turnover rates", "block and rim-event rates",
                      "defensive rebound rate", "foul rate",
                      "opponent shot-location effects where supportable",
                      "defensive possession share",
                      "matchup or positional role where available",
                      "frozen P3 net or defensive summaries as OPTIONAL inputs, not defining truth"],
        "denominators": "natural opportunity denominators where possible",
    },
    "leakage_and_chronology": [
        "construct feature summaries using information available BEFORE the cutoff",
        "fit preprocessing and clustering ONLY on the training window",
        "assign held-out players using the frozen training-fold transformation and centroids",
        "never refit clusters using the held-out season",
        "never use target-game outcomes to define that game's archetype",
        "do NOT calculate one all-years clustering solution and apply it retrospectively",
    ],
    "bounded_challenger_set": {
        "methods": ["k-means as the simple baseline",
                    "Gaussian mixture model for soft membership",
                    "hierarchical clustering as a structural diagnostic"],
        "not": "an unrestricted clustering search",
        "k_selection": {
            "range": "a bounded range of small k",
            "criteria": ["fold-to-fold stability", "cluster size and minimum support",
                         "interpretability", "downstream out-of-sample predictive gain"],
            "insufficient_alone": "silhouette score or inertia",
        },
    },
    "soft_membership": {
        "retain": "membership probabilities or distances to centroids",
        "why": ("players near a boundary must not be forced into a completely different "
                "forecasting regime because of a small feature change"),
        "model_may_use": ["cluster identity", "distance to cluster center",
                          "soft membership weights", "archetype uncertainty"],
    },
    "forecasting_comparison": [
        "pooled player model",
        "pooled model plus raw continuous role features",
        "pooled model plus hard archetype",
        "pooled model plus soft archetype membership",
        "hierarchical model with archetype-level effects",
        "archetype model plus shrunk player-specific deviations",
    ],
    "bar": ("clustering is valuable ONLY if it improves chronological out-of-sample prediction "
            "BEYOND the continuous features used to create the clusters"),
    "matchup_use_after_exposure_exists": [
        "primary creators versus high-pressure defenders",
        "turnover-prone handlers versus steal-oriented rotations",
        "rim attackers versus projected rim-protecting lineups",
        "offensive rebounders versus defensive rebound archetypes",
        "high-foul-drawing players versus foul-prone defenders",
        "spot-up shooting rotations versus perimeter-suppression archetypes",
    ],
    "matchup_weighting": "by projected minutes or possessions",
    "stability_reporting_required": [
        "cluster sizes", "season-to-season player transitions", "centroid stability",
        "assignment stability across folds", "players with ambiguous membership",
        "low-support clusters", "downstream performance by archetype",
        "whether archetype gains persist after raw continuous features are included",
    ],
    "warning": "do not interpret a visually coherent cluster as predictive evidence",
    "start_boundary": "do not begin clustering before projected_player_possessions_v1 is frozen",
}


LANES = {
    "schema": SCHEMA,
    "kind": "process",
    "experiment_id": "player_program_capability_matrix_and_lanes",
    "registered_at": _utc(),
    "authorises_execution": False,
    "reconciliation_requirement": {
        "why": ("the repository's ORIGINAL player-centric design already anticipated "
                "possession-based player features, team aggregation, lineup chemistry, "
                "situational context, advanced player statistics, injury effects, ensembles, "
                "forward validation, uncertainty, player development and coaching effects. Those "
                "concepts must NOT be restarted from scratch."),
        "deliverable": "experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md",
        "per_capability_fields": [
            "original plan or source", "existing code", "existing artifact",
            "existing registration", "validation status",
            "canonical | prototype | superseded | blocked | not started",
            "what may be reused", "what must NOT be reused", "exact next dependency",
        ],
        "capabilities_at_minimum": [
            "raw play-by-play acquisition", "event parsing", "possession reconstruction",
            "on-court tracking", "lineup and stint construction", "player possession statistics",
            "opponent normalization", "availability", "conditional minutes",
            "constrained rotation allocation", "projected possessions", "attempts and scoring",
            "steals and turnovers", "offensive and defensive rebounds", "blocks and rim events",
            "assists", "fouls and free throws", "RAPM/P3", "player archetypes",
            "lineup chemistry and pairings", "travel, rest and venue",
            "player development and aging", "coaching and substitution strategy",
            "uncertainty and simulation", "team aggregation", "prospective logging",
        ],
        "search_before_labelling_anything_new": [
            "the current worktree", "registrations", "manifests", "historical scripts",
            "documentation",
        ],
    },
    "original_possession_script_disposition": {
        "script": "build_possession_based_features.py",
        "treat_as": "PROTOTYPE",
        "it_attempted": ["possession boundaries", "on-court tracking",
                         "offensive possession attribution", "player on-court points",
                         "opponent normalization"],
        "do_not": "create a parallel replacement from that prototype",
        "canonical_remains": ("player_possessions/2 is the canonical realised-possession artifact "
                              "unless validation proves otherwise"),
        "audit_only_for": "potentially useful event-parsing logic or known edge cases",
        "explicitly_forbidden_reuse": (
            "its same-game opponent-efficiency normalization as a pregame feature. Target-game "
            "outcomes cannot be used to normalize the forecast for that game."),
        "document_which_components_are": ["superseded by player_possessions/2", "still useful",
                                          "leakage-prone", "incomplete", "unused"],
    },
    "preserved_future_tracks": {
        "lineup_chemistry_and_transitions": {
            "test": ["two-player and three-player compatibility", "lineup continuity",
                     "substitution transitions", "role complementarity",
                     "starter/bench combinations",
                     "whether lineup interactions add value beyond additive player effects"],
            "constraint": ("do not begin with unrestricted lineup IDs; use shrinkage and "
                           "minimum-support rules"),
        },
        "player_development": {
            "model": ["age curves", "experience", "rookie progression", "veteran decline",
                      "return from injury or absence", "role expansion and contraction",
                      "team-change adaptation"],
            "constraint": ("development effects inform PRIORS and expected change; they must not "
                           "use future-season information"),
        },
        "coaching_and_rotation_strategy": {
            "after": "projected exposure exists",
            "test_whether_coaches_predictably_influence": [
                "player minutes", "substitution timing", "lineup combinations", "pace",
                "matchup usage", "role changes", "response to absences"],
        },
        "predictive_uncertainty": {
            "requirement": "each mature event channel emits an uncertainty DISTRIBUTION, not only a mean",
            "simulation_must_preserve_dependencies_among": [
                "active status", "minutes", "possessions", "usage", "attempts", "scoring",
                "assists", "rebounds", "steals and turnovers", "blocks and fouls"],
        },
        "interpretability": {
            "tools": "feature importance, SHAP-style attribution or partial dependence",
            "only_after": "a model has passed chronological validation",
            "warning": "interpretability does not validate a feature or establish causality",
        },
        "ensembles_and_multitask": {
            "incumbents_stay": "linear and generalized models, interpretable",
            "bounded_challengers_later": ["gradient boosting", "soft archetype mixtures",
                                          "multi-task models for related player statistics",
                                          "ensembles of independently valid models"],
            "not_before": ("deep-learning or graph-model work must not begin before the simpler "
                           "systems and the projected-exposure bridge are established"),
        },
    },
    "two_lanes": {
        "promotion_lane": {
            "is": "the formal evidence lane",
            "every_promoted_experiment_requires": [
                "registered target and opportunity denominator", "registered feature set",
                "cutoff-valid inputs", "chronological walk-forward evaluation", "fixed metrics",
                "coverage receipts", "comparison against a frozen incumbent",
                "downstream accounting where relevant",
                "no feature changes after results are opened",
            ],
        },
        "discovery_lane": {
            "is": "the trial-and-error lane",
            "purpose": ("brainstorm and rapidly test plausible ideas WITHOUT falsely describing "
                        "them as confirmation"),
            "may_investigate": [
                "alternate trailing windows", "decay rates", "transformations", "feature subsets",
                "interaction hypotheses", "player archetypes", "role states",
                "schedule and travel effects", "matchup features", "simple model families",
                "unusual player-specific responses", "opportunity-denominator definitions",
            ],
            "constraints": ["development folds only",
                            "cannot directly promote a model"],
            "cadence": ("reserve every THIRD player research wave as a discovery wave unless an "
                        "urgent infrastructure blocker takes precedence"),
        },
    },
    "discovery_wave_procedure": {
        "slate": "a bounded hypothesis slate at the start of each wave, e.g. 5-10 related hypotheses",
        "per_idea_fields": ["target statistic", "basketball mechanism", "opportunity denominator",
                            "proposed feature", "expected direction", "cutoff availability",
                            "leakage risk", "minimum sample", "affected players or archetypes",
                            "computational cost"],
        "funnel": ["data and leakage feasibility", "simple univariate or small ablation screen",
                   "chronological development-fold test",
                   "stability by season and player support",
                   "mechanism-specific target evaluation",
                   "only then nomination for a registered promotion experiment"],
        "forbidden": ("do not select ideas using the final confirmation period or prospective "
                      "results"),
    },
    "discovery_ledger": {
        "must_be": "searchable",
        "fields": ["idea", "implementation", "development result", "stability", "failure reason",
                   "closed | deferred | worth revisiting",
                   "dependencies that could change the verdict"],
        "preserve": ["null results", "negative results", "small stable gains",
                     "channel gains that fail downstream aggregation",
                     "ideas blocked by unavailable data"],
        "rule": "a failed implementation does not automatically close the entire mechanism",
    },
    "player_specific_experimentation": {
        "permitted_only_after": "pooled and archetype models exist",
        "must_be_tested_with": ["hierarchical shrinkage", "adequate player sample",
                                "chronological held-out performance",
                                "repeated support across folds or seasons",
                                "multiple-hypothesis correction or an equivalent "
                                "false-discovery safeguard"],
        "exploratory_player_stories": ("may be generated in the discovery lane, but cannot become "
                                       "production rules without repeated OOS evidence"),
    },
    "binding_immediate_ordering": [
        "1. finish and validate projected_player_possessions_v1",
        "2. test the frozen P3 aggregation honestly",
        "3. complete the capability matrix",
        "4. register the granular player-stat program",
        "5. begin target-specific pooled baselines",
        "6. insert recurring discovery waves for brainstorming and trial and error",
        "7. add archetype and player-specific specialization only after the relevant pooled "
        "baselines exist",
    ],
    "stop_boundary_unchanged": ("stop before projected-possession downstream accuracy, as "
                                "previously instructed. Steps 2 onward require authorisation."),
    "roadmap_must_not_interrupt": "the immediate dependency (step 1)",
}


RECORDS = [OBJECTIVE, ARCHETYPES, LANES]


def existing_ids() -> set[str]:
    if not ARM_REGISTRY.exists():
        return set()
    return {json.loads(l).get("experiment_id")
            for l in ARM_REGISTRY.read_text(encoding="utf-8").splitlines() if l.strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    have = existing_ids()
    if args.list:
        for r in RECORDS:
            print(f"{'PRESENT' if r['experiment_id'] in have else 'ABSENT '}  "
                  f"{r['kind']:18s}  {r['experiment_id']}")
        return

    n = 0
    with ARM_REGISTRY.open("a", encoding="utf-8") as fh:
        for r in RECORDS:
            if r["experiment_id"] in have:
                print(f"skip (already registered): {r['experiment_id']}")
                continue
            fh.write(json.dumps(r, sort_keys=False) + "\n")
            print(f"appended: {r['kind']:18s} {r['experiment_id']}")
            n += 1
    print(f"\n{n} record(s) appended to {ARM_REGISTRY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
