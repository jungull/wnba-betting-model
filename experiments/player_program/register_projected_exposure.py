#!/usr/bin/env python3
"""register_projected_exposure.py — freeze the exposure bridge BEFORE it is built.

Appends four records to the player program's `arm_registry.jsonl`:

1. ``p3_defensive_impact__amendment_downstream_ablation`` — amends finding 5. Individual defensive
   impact is UNPROVEN, not prohibited. The frozen defensive coefficients are preserved as an
   experimental input; they are not published as individually interpretable ratings.
2. ``exposure_bridge__amendment_matchup_interaction_track`` — adds a SECOND purpose for the bridge.
   It must support mechanism-specific matchup interactions, not only aggregation of generic
   coefficients.
3. ``team_possession_prior_v1`` — the prior-games-only team-possession estimator. No frozen
   cutoff-valid pace artifact exists to reuse (see ``reuse_search`` below), so one is registered.
4. ``projected_player_possessions_v1`` — the projected-exposure artifact itself.

Records 3 and 4 are registered BEFORE execution. Neither is a revision of `p3_adjusted_impact_v1`
or `cbs_v15_player_oof_v5`; both are new artifacts under new ids.

**Nothing here is scored.** No record contains a measurement of any model against any outcome.

Run::

    python experiments/player_program/register_projected_exposure.py
    python experiments/player_program/register_projected_exposure.py --list
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARM_REGISTRY = HERE / "arm_registry.jsonl"
SCHEMA = "player_program_arm_registry/1"

PACE_ARM = "team_possession_prior_v1"
EXPOSURE_ARM = "projected_player_possessions_v1"
DEF_AMENDMENT = "p3_defensive_impact__amendment_downstream_ablation"
MATCHUP_AMENDMENT = "exposure_bridge__amendment_matchup_interaction_track"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(rel: str) -> str | None:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


CONTRACT = "experiments/prediction_contract_v5/player_game_enriched.parquet"
POSS = "experiments/player_program/possessions_v2/possessions_raw_v2.parquet"


# --------------------------------------------------------------------------- #
# 1. amendment: individual defensive impact is unproven, not prohibited
# --------------------------------------------------------------------------- #
DEF_RECORD = {
    "schema": SCHEMA,
    "kind": "amendment",
    "experiment_id": DEF_AMENDMENT,
    "applies_to": "p3_adjusted_impact_v1",
    "amends": "prior program finding 5, 'individual defensive impact is not defensible'",
    "amended_by": "operator instruction, in session",
    "what_stands": [
        "offence-only, net-only and separate offence/defence produce nearly identical held-out "
        "stint accuracy; defence-only is slightly worse",
        "offensive and defensive design columns are nearly collinear",
        "defensive penalties are selected substantially stronger",
        "apparent DRAPM stability is partly induced by shrinkage",
    ],
    "what_is_corrected": (
        "the prior finding read as a prohibition. It is not one. The evidence shows the separate "
        "defensive coefficients are not sufficiently IDENTIFIED to support publication or "
        "interpretation as standalone individual defensive ratings. It does NOT establish that "
        "defensive player effects are useless for forecasting opponent points."),
    "intended_operational_role": (
        "narrower than a player rating: aggregate the projected defensive EXPOSURE of the expected "
        "lineup and use it to adjust the OPPONENT's expected scoring. The question is not whether "
        "DRAPM is a clean individual talent measure; it is whether its aggregated, "
        "exposure-weighted contribution improves out-of-sample opponent scoring forecasts."),
    "why_untested": (
        "the information-honest downstream test has not been run because projected player "
        "possessions do not exist. That is what this registration builds."),
    "disposition_of_frozen_coefficients": {
        "preserve_as": "experimental input",
        "do_not": [
            "publish as individually interpretable ratings",
            "promote without a downstream ablation",
        ],
    },
    "downstream_ablation_required_before_any_promotion": {
        "on": "identical games and cutoffs",
        "arms": [
            "frozen team incumbent",
            "incumbent plus offensive player effects",
            "incumbent plus net player effects",
            "incumbent plus separate offensive and defensive effects",
            "defensive-only adjustment as a diagnostic",
        ],
        "application_rule": (
            "apply defensive effects to the OPPOSING team's predicted points using projected "
            "defensive possessions"),
        "report": [
            "home-score MAE", "away-score MAE", "opponent-points error",
            "margin MAE", "total MAE",
            "home residual variance", "away residual variance",
            "residual covariance", "residual correlation",
            "paired uncertainty against the incumbent",
        ],
    },
    "not_authorised_yet": "this ablation runs only after the exposure artifact is frozen and validated",
    "registered_at": _utc(),
}


# --------------------------------------------------------------------------- #
# 2. amendment: the bridge has a second purpose
# --------------------------------------------------------------------------- #
MATCHUP_RECORD = {
    "schema": SCHEMA,
    "kind": "amendment",
    "experiment_id": MATCHUP_AMENDMENT,
    "applies_to": EXPOSURE_ARM,
    "amended_by": "operator instruction, in session",
    "second_purpose": (
        "the projected-exposure bridge must support MECHANISM-SPECIFIC player matchup "
        "interactions, not only aggregation of generic RAPM coefficients."),
    "why": (
        "the current P3 validation tests additive player POINT impact. It does not answer whether "
        "projected opposing personnel improve specific EVENT forecasts -- turnovers, steals, "
        "rebounds, rim scoring or free throws."),
    "research_track_preserved_not_started": {
        "name": "player matchup interaction track",
        "estimates": (
            "whether an offence's demonstrated tendencies interact predictively with the projected "
            "opposing rotation's corresponding defensive skills"),
        "candidate_channels": {
            "turnovers_and_steals": {
                "match": [
                    "offensive turnover susceptibility",
                    "bad-pass and live-ball turnover rates where available",
                    "ball-handler usage",
                    "projected opposing steal, deflection and forced-turnover rates",
                ],
                "constraint": (
                    "do not equate every turnover with a steal. Separate live-ball or "
                    "steal-related turnovers from travels, offensive fouls and other turnover "
                    "causes where the event data permit."),
            },
            "rebounding": {
                "match": [
                    "projected offensive rebound strength",
                    "projected opponent defensive rebound strength",
                    "expected missed-shot opportunities",
                    "lineup size and positional composition where preregistered",
                ],
                "constraint": "use rebound OPPORTUNITIES as the denominator, not total possessions",
            },
            "rim_scoring_and_rim_protection": {
                "match": [
                    "rim-attempt frequency",
                    "player finishing at the rim",
                    "projected opponent block, deterrence and rim-suppression evidence",
                    "opponent foul propensity",
                ],
                "constraint": (
                    "do not claim individual rim-defence effects unless the event data support the "
                    "required location and defender attribution"),
            },
            "foul_drawing_and_foul_propensity": {
                "match": [
                    "projected offensive foul-drawing players",
                    "projected defenders' foul rates",
                    "team foul environment",
                ],
            },
            "perimeter_shooting_and_defence": {
                "match": [
                    "projected three-point creation and shooter exposure",
                    "opponent attempt suppression or closeout effects",
                ],
                "confidence": (
                    "LOWER. Treat as low confidence unless the available data identify defender "
                    "and shot-quality effects adequately."),
            },
        },
        "modelling_rule": {
            "these_are": "interaction features, not generic player-rating sums",
            "each_channel_uses": [
                "the offence's pre-cutoff tendency",
                "the opposing projected players' pre-cutoff defensive tendency",
                "projected player possessions or minutes",
                "appropriate opportunity denominators",
                "shrinkage for small samples",
            ],
            "hard_constraint": "no target-game events may enter the features",
        },
        "evaluation_sequence": {
            "rule": (
                "each channel must first improve its OWN held-out event target before being "
                "allowed into the team-score forecast"),
            "examples": {
                "turnover module": "held-out turnovers or live-ball turnovers",
                "rebound module": "offensive and defensive rebounds per opportunity",
                "foul module": "free-throw attempts or shooting fouls",
                "rim module": "rim attempts and rim efficiency",
            },
            "then": (
                "only after channel validation may the module be converted into expected points "
                "and tested as a supplemental adjustment to the frozen team incumbent"),
        },
        "avoid_double_counting": (
            "the team incumbent already contains team-level tendencies. The player matchup layer "
            "models the INCREMENTAL difference between the team's normal personnel environment and "
            "the projected personnel for the specific game. Prefer residual or deviation features "
            "-- projected lineup strength minus the team's trailing personnel baseline -- rather "
            "than adding full season-level rates again."),
        "required_downstream_ablations": {
            "on": "identical games and cutoffs",
            "arms": [
                "frozen team incumbent",
                "incumbent plus generic net player impact",
                "incumbent plus separate offensive and defensive point-impact aggregation",
                "incumbent plus mechanism-specific matchup channels",
                "incumbent plus both generic impact and matchup channels",
            ],
            "report": [
                "channel-specific accuracy",
                "home-score MAE", "away-score MAE",
                "total MAE", "margin MAE",
                "home residual variance", "away residual variance",
                "residual covariance", "residual correlation",
                "coverage by roster-evidence regime",
                "paired uncertainty",
            ],
            "do_not_presume": (
                "the generic defensive coefficient and the mechanism-specific defensive features "
                "are NOT interchangeable. A noisy standalone DRAPM estimate may fail as a player "
                "ranking while steal, rebound or rim-protection interactions still add useful "
                "aggregate forecasting signal."),
        },
        "start_boundary": (
            "do not begin this interaction modelling before the projected-exposure artifact is "
            "frozen and validated"),
    },
    "consequences_for_this_artifact": {
        "must_supply": [
            "per-player projected exposure for BOTH sides of every game, so an offence's projected "
            "rotation can be matched against the projected OPPOSING rotation",
            "projected minutes AND projected offensive/defensive possessions, since the matchup "
            "rule permits either as the exposure weight",
            "a cutoff-valid projection for every historical game in the universe, so a team's "
            "TRAILING PERSONNEL BASELINE is computable from this artifact itself and deviation "
            "features can be formed without a second exposure model",
        ],
        "must_not_supply": [
            "opportunity denominators -- rebound opportunities, rim attempts, shot locations, "
            "defender attribution. Those require the EVENT stream, which this artifact does not "
            "read. The rebound-opportunity limitation already on the program's record is "
            "unchanged by this amendment.",
        ],
    },
    "registered_at": _utc(),
}


# --------------------------------------------------------------------------- #
# 3. the pace estimator
# --------------------------------------------------------------------------- #
PACE_RECORD = {
    "schema": SCHEMA,
    "kind": "arm",
    "experiment_id": PACE_ARM,
    "arm_id": "team_possession_prior/1",
    "registered_at": _utc(),
    "registered_before_execution": True,
    "extra": {
        "reuse_search": {
            "instruction": "prefer reuse of a frozen cutoff-valid pace estimate in the team artifacts",
            "searched": [
                "experiments/registry.jsonl (96 records) for any pace or possession estimator arm",
                "features/ for committed as-of pace columns",
                "src-level producers for a persisted pace artifact",
            ],
            "found": {
                "features/common.py::pace_sew": (
                    "a shifted within-team-season EWMA of realised offensive possessions, "
                    "alpha 0.10, used as a TEAM-MODEL FEATURE"),
            },
            "why_not_reused": [
                "it is a feature column computed inside the team feature lab, not a frozen, "
                "registered, independently addressable artifact with a hash",
                "no registered arm in experiments/registry.jsonl defines it as a pace estimator",
                "it declares no season-opening fallback: shift(1) within team-season leaves the "
                "first game of every team-season undefined",
                "it declares no overtime treatment, so an overtime game inflates the estimate with "
                "no regulation normalisation",
                "its source is filtered to Regular Season and passes a season-quarantine screen, "
                "so it does not cover the playoff games in this universe",
                "it is ordered by game index, not by a forecast cutoff",
            ],
            "conclusion": "no frozen cutoff-valid pace estimate exists to reuse; register one",
        },
        "frozen_config": {
            "arm_id": "team_possession_prior/1",
            "purpose": (
                "a prior-games-only projected team offensive possession count, for the exposure "
                "bridge. Registered as a separate arm because the exposure artifact must bind a "
                "hashed pace input, not compute one inline."),
            "source_artifact": "player_possessions/2",
            "source_path": POSS,
            "source_sha256": _sha(POSS),
            "source_role": (
                "REALISED possessions of STRICTLY EARLIER games only. No target-game possession "
                "count enters any estimate."),
            "realised_quantity": {
                "game_minutes": "40 + 5 * max(0, max_period_in_game - 4)",
                "regulation_equivalent_team_off_poss":
                    "n_off_poss(team, game) * 40 / game_minutes(game)",
                "game_pace":
                    "the MEAN of the two teams' regulation-equivalent offensive possessions",
                "why_symmetric": (
                    "possessions are a property of the game, not of a side. In the realised "
                    "artifact the home-minus-away offensive possession difference has mean 0.002 "
                    "with no systematic sign; the residual spread is possession-reconstruction "
                    "imprecision, not a team effect. Projecting a side differential would be "
                    "projecting noise."),
            },
            "estimator": {
                "form": "unweighted mean of game_pace over a trailing window",
                "window_K": 10,
                "min_history_m": 3,
                "levels": [
                    {"level": 1, "id": "team_window_same_season",
                     "rule": "at least 3 prior SAME-SEASON games for this team: mean game_pace "
                             "over its most recent 10 of them"},
                    {"level": 2, "id": "team_window_prior_season",
                     "rule": "else at least 3 games for this team in the immediately preceding "
                             "season: mean game_pace over its most recent 10 of them"},
                    {"level": 3, "id": "league_prior_all",
                     "rule": "else the mean game_pace over ALL games strictly before the cutoff, "
                             "all teams, all seasons present"},
                    {"level": 4, "id": "unresolved_no_prior_games",
                     "rule": "no game strictly before the cutoff exists: pace is UNRESOLVED and no "
                             "possession projection is emitted for that game"},
                ],
                "game_estimate": (
                    "the mean of the two teams' level-resolved estimates. If EITHER side is "
                    "level 4 the game's pace is unresolved."),
            },
            "frozen_declarations": {
                "historical_window": "trailing 10 games, unweighted, no decay",
                "season_opening_fallback": "level 2, then level 3, then unresolved (level 4)",
                "overtime_treatment": (
                    "normalised OUT. Every realised game is converted to a 40-minute regulation "
                    "equivalent before entering any mean, and the artifact projects "
                    "regulation-equivalent exposure only. No overtime minutes or overtime "
                    "possessions are projected."),
                "home_away_treatment": "NONE. No venue term, no home/away split, no venue adjustment.",
                "opponent_adjustment": "NONE.",
                "season_type_treatment": (
                    "regular season and playoff games are pooled. No separate playoff estimator."),
                "minimum_history_behaviour": "fewer than 3 qualifying games falls to the next level",
                "cutoff_rule": (
                    "a game is admissible history iff its game_date is STRICTLY EARLIER than the "
                    "target game's date. The contract's cutoff policy is "
                    "date_only_prior_day_cutoff, so every strictly-earlier-date game is complete "
                    "and its possession count observable before the cutoff. Same-date games are "
                    "excluded."),
            },
            "selection_discipline": {
                "K_and_m_chosen": "declared here, before execution, and before any downstream number is viewed",
                "not_selected_on": (
                    "no downstream P3, team-margin, possession, minutes or betting result. This "
                    "estimator will NOT be re-tuned after a downstream result is seen."),
            },
            "nothing_fitted": True,
            "output_schema": [
                "game_id", "team_id", "game_date", "season", "season_type",
                "pace_level", "pace_source", "n_history_games",
                "projected_team_off_possessions",
            ],
        },
    },
}


# --------------------------------------------------------------------------- #
# 4. the exposure artifact
# --------------------------------------------------------------------------- #
EXPOSURE_RECORD = {
    "schema": SCHEMA,
    "kind": "arm",
    "experiment_id": EXPOSURE_ARM,
    "arm_id": "projected_player_possessions/1",
    "registered_at": _utc(),
    "registered_before_execution": True,
    "extra": {
        "is_not_a_revision_of": ["p3_adjusted_impact_v1", "cbs_v15_player_oof_v5", "player_possessions/2"],
        "why_a_new_arm": (
            "player_possessions/2 is a REALISED historical reconstruction and cannot be used as "
            "forecast exposure. v15 predicts p_active and e_minutes_given_active but supplies no "
            "constrained team-minute allocation, no projected possessions and no frozen "
            "minutes-to-possession mapping. This artifact is the missing bridge."),
        "purposes": [
            "information-honest P3 rotation aggregation (generic coefficient track)",
            "mechanism-specific player matchup interactions (see "
            "exposure_bridge__amendment_matchup_interaction_track)",
        ],
        "frozen_config": {
            "arm_id": "projected_player_possessions/1",
            "permitted_inputs": {
                "v15_p_active": "experiments/cbs_v15_player_oof_v5/attempt_001/predictions__p_active__*.parquet",
                "v15_e_minutes_given_active":
                    "experiments/cbs_v15_player_oof_v5/attempt_001/predictions__e_minutes_given_active__*.parquet",
                "contract_v5_candidate_and_tier_fields": CONTRACT,
                "contract_v5_sha256": _sha(CONTRACT),
                "team_possession_estimate": "team_possession_prior/1 (separately registered above)",
                "identities": "canonical game_id, team_id, player_id, row_uid, forecast_cutoff",
            },
            "forbidden_inputs": [
                "actual lineups", "actual minutes", "actual pace", "actual possessions",
                "target-game box-score outcomes", "post-cutoff availability information",
                "any column derived from whether the player appeared in the target game",
            ],
            "expected_minutes_allocation": {
                "raw": "raw_expected_minutes = p_active * e_minutes_given_active",
                "algorithm": "iterative capped-proportional allocation (water-filling)",
                "steps": [
                    "viable candidates are those with raw_expected_minutes > 0",
                    "if fewer than 5 viable candidates exist the team-game is UNRESOLVED and no "
                    "allocation is emitted; no player is invented",
                    "otherwise scale all viable raw values by a common factor so they sum to 200",
                    "any player exceeding 40 is pinned at 40; the remaining 200 - 40*n_capped "
                    "minutes are re-scaled across the uncapped players; repeat until stable",
                ],
                "constraints": {
                    "nonnegative": True,
                    "per_player_max_minutes": 40,
                    "team_total_minutes": 200,
                    "exactness": (
                        "the allocation is settled in INTEGER micro-minutes (1e-6 min) by the "
                        "largest-remainder method, so the team total is exactly 200000000 "
                        "micro-minutes with no floating-point residue. The float column is the "
                        "integer column divided by 1e6 and is validated to within 1e-9 of 200."),
                    "tie_break": "ascending row_uid; deterministic",
                },
                "redistribution_is_explicit": (
                    "the scale factor, the raw sum, the redistributed quantity (200 - raw sum) and "
                    "the capped count are persisted per team-game, so every minute moved is "
                    "attributable."),
                "no_rotation_truncation": (
                    "every viable candidate receives minutes. No short-rotation cut is applied. A "
                    "cut would be a tuning choice with no preregistered basis, and tuning "
                    "redistribution against downstream results is forbidden."),
                "not_tuned_against": "team-margin, possession, minutes or betting results",
            },
            "minutes_to_possession_mapping": {
                "frozen_rule": {
                    "player_off_possessions":
                        "projected_team_off_possessions * (projected_minutes / 40)",
                    "player_def_possessions":
                        "projected_opp_off_possessions * (projected_minutes / 40)",
                },
                "why": (
                    "five players are on the floor at every instant, so a player's share of the "
                    "team's possessions is exactly their share of the 200 team-minutes: "
                    "5 * minutes/200 = minutes/40. With team minutes summing to exactly 200 the "
                    "possession-mass constraints hold by construction, not by adjustment."),
                "known_consequence_disclosed_in_advance": (
                    "the pace estimate is symmetric, so projected_team_off_possessions equals "
                    "projected_opp_off_possessions and therefore a player's projected OFFENSIVE "
                    "and DEFENSIVE possessions are EQUAL. This is not a defect and it is not "
                    "hidden: at projection time nothing distinguishes the two counts. The "
                    "consequence for the downstream defensive ablation is that separate offensive "
                    "and defensive effects are applied to IDENTICAL exposure, so any difference "
                    "between the net-effect arm and the separate-effect arm comes from the "
                    "coefficient vector alone, never from the exposure. Manufacturing an "
                    "asymmetry to avoid this would be projecting noise -- see the pace arm's "
                    "why_symmetric."),
            },
            "evidence_regimes": {
                "rule": "reported separately; never silently pooled",
                "regimes": [
                    {"id": "tier_a_only", "role": "PRIMARY",
                     "candidates": "evaluation_tier == A_primary"},
                    {"id": "tier_a_plus_tx_b", "role": "sensitivity",
                     "candidates": "A_primary plus B_transaction_sensitivity"},
                    {"id": "tier_a_plus_tx_b_plus_s2", "role": "sensitivity",
                     "candidates": "A_primary plus B_transaction_sensitivity plus B_s2_weak_fallback"},
                ],
                "unresolved": "a fourth reported class, not a regime: any team-game and regime "
                              "with fewer than 5 viable candidates",
                "s2_never_pooled": (
                    "S2-only weak-roster candidates carry weak_prior_season evidence. Prior-season "
                    "affiliation is weak evidence of PAST affiliation, not proof of current-season "
                    "roster membership. They appear only in the third regime and are labelled."),
            },
            "status_vocabulary": {
                "normal": "allocation formed and pace resolved at level 1",
                "fallback": "allocation formed but the pace resolved at level 2 or 3, or at least "
                            "one bound v15 prediction is itself a fallback prediction",
                "minutes_only_no_pace": "allocation formed, pace unresolved (level 4); projected "
                                        "possessions are null and the minutes stand",
                "unresolved_insufficient_candidates": "fewer than 5 viable candidates; nothing emitted",
            },
            "ambiguous_candidates": {
                "situation": "a player-game claimed as a candidate by both clubs",
                "policy": (
                    "BOTH claims are retained, in each club's candidate set, and flagged with "
                    "candidate_claimed_by_multiple_teams."),
                "why_not_resolved": (
                    "the contract's ambiguity STATE distinguishes the claims by which club holds "
                    "the player's box row. That is target-game outcome information. Using it to "
                    "assign the player would leak. The ambiguity is therefore disclosed and "
                    "counted, never silently resolved."),
                "outcome_derived_column_excluded": (
                    "team_assignment_ambiguity_state is NOT written into the artifact; it is "
                    "reported in the receipt only."),
            },
            "no_outcome_columns": (
                "minutes, pts, fga, appeared, in_target_box and every outcome_scoreable__* column "
                "of the contract are dropped before the artifact is written, and the producer "
                "fails closed if any survives"),
            "determinism": "same inputs always produce the same result; generation is idempotent",
            "nothing_fitted": True,
            "nothing_scored": (
                "this arm computes no accuracy, calibration, error or edge figure of any kind"),
            "outputs": {
                "player_level": "experiments/player_program/projected_exposure_v1/"
                                "projected_player_possessions_v1.parquet",
                "team_game_level": "experiments/player_program/projected_exposure_v1/"
                                   "projected_team_rotations_v1.parquet",
                "pace_level": "experiments/player_program/projected_exposure_v1/"
                              "team_possession_prior_v1.parquet",
                "receipt": "experiments/player_program/projected_exposure_v1/"
                           "PROJECTED_EXPOSURE_RECEIPT.json",
                "validation": "experiments/player_program/projected_exposure_v1/"
                              "PROJECTED_EXPOSURE_VALIDATION.json",
            },
        },
        "stop_boundary": {
            "this_registration_authorises": ["registration", "construction", "validation"],
            "then": "STOP and request authorisation for the downstream experiment",
            "must_not_be_inspected_in_this_phase": [
                "actual-minute MAE", "possession MAE", "team-margin MAE",
                "calibration", "residual covariance", "betting outcomes",
            ],
            "binding_prior_warning": (
                "bottomup_3pt_channel_v1 improved its own channel and degraded joint team-margin "
                "accuracy by reducing useful home/away residual covariance. Every future "
                "player-to-team aggregation experiment must report home residual variance, away "
                "residual variance, covariance, corr(e_home, e_away), and the resulting margin "
                "variance and MAE. A channel-level gain is not sufficient for promotion."),
        },
    },
}


RECORDS = [DEF_RECORD, MATCHUP_RECORD, PACE_RECORD, EXPOSURE_RECORD]


def existing_ids() -> set[str]:
    if not ARM_REGISTRY.exists():
        return set()
    out = set()
    for line in ARM_REGISTRY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.add(json.loads(line).get("experiment_id"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    have = existing_ids()
    if args.list:
        for r in RECORDS:
            print(f"{'PRESENT' if r['experiment_id'] in have else 'ABSENT '}  "
                  f"{r['kind']:10s}  {r['experiment_id']}")
        return

    appended = []
    with ARM_REGISTRY.open("a", encoding="utf-8") as fh:
        for r in RECORDS:
            if r["experiment_id"] in have:
                print(f"skip (already registered): {r['experiment_id']}")
                continue
            fh.write(json.dumps(r, sort_keys=False) + "\n")
            appended.append(r["experiment_id"])
            print(f"appended: {r['kind']:10s} {r['experiment_id']}")

    if appended:
        print(f"\n{len(appended)} record(s) appended to {ARM_REGISTRY.relative_to(ROOT)}")
    else:
        print("\nnothing appended")


if __name__ == "__main__":
    main()
