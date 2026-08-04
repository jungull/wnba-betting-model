#!/usr/bin/env python3
"""register_turnover_p2.py — freeze the P1 result and register `turnover_rate_role_context_v1`."""
from __future__ import annotations
import argparse, json, subprocess                                              # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REG = HERE / "arm_registry.jsonl"
EXP = "turnover_rate_role_context_v1"

RIDGE_LAMBDA = 10.0
INVOLVE_ALPHA = 0.10
INVOLVE_SHRINK_K = 50.0
MIN_TRAIN_ROWS = 2000


def _head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


P1_FINAL = {
    "schema": "player_program_arm_registry/1", "kind": "completion",
    "experiment_id": "turnover_rate_pooled_baseline_v1__final",
    "applies_to": "turnover_rate_pooled_baseline_v1",
    "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "principal_result": (
        "Player turnover history contains genuine predictive signal. The frozen EWMA-shrunk rate "
        "arm provides a small but statistically supported improvement over the league-constant "
        "baseline on both the intrinsic and operational team-level evaluations. The gain is not "
        "stable across every season and is not promotion-grade."),
    "development_champion": {"arm": "D_ewma_shrunk", "scope": "turnover channel, P1 development only",
                             "not": ["production-ready", "universally superior"]},
    "limitations": [
        "operational team-MAE improvement is approximately 0.046 turnovers per team-game, about 1.5%",
        "2021 is adverse",
        "career-to-date shrinkage (arm B) is a team-level null",
        "season-to-date shrinkage (arm C) passes only operationally",
        "the Tier A candidate universe misses actual appearances AND assigns exposure to players "
        "who do not appear",
        "candidate precision, appearance forecasting, exposure allocation and turnover-rate error "
        "all contribute to operational performance",
    ],
    "superseded": {
        "what": "the operational results computed over realised participants only",
        "status": "INVALID",
        "superseded_by_commit": "7cbfa9d",
        "defect": ("team aggregation summed only over players present in the realised target "
                   "artifact -- retrospective rotation membership -- via a left merge starting "
                   "FROM realised rows"),
    },
    "withdrawn_claim": ("that projected exposure is the DOMINANT error source. It was inflated by "
                        "the universe defect. Arm D's intrinsic-to-operational team MAE gap is "
                        "2.8960 to 2.9675."),
}

P2 = {
    "schema": "player_program_arm_registry/1", "kind": "arm", "experiment_id": EXP,
    "arm_id": "turnover_rate_role_context/1",
    "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "registered_before_execution": True, "registered_at_commit": _head(),
    "extra": {
        "status": "historical development evidence only",
        "question": ("do cutoff-valid role and offensive-involvement features add STABLE turnover-"
                     "rate information beyond the frozen EWMA-shrunk P1 baseline?"),
        "frozen_and_not_retuned": ["K=200", "alpha=0.10", "the P1 shrinkage formula",
                                   "the projected-exposure artifact", "the candidate-universe policy",
                                   "the team/unattributed companion component",
                                   "frozen P1 Arm D predictions"],
        "comparison_rule": "every P2 challenger is compared against the exact frozen Arm D predictions on identical rows",
        "feature_boundary": {
            "allowed": ["projected role and exposure", "prior-games-only role history",
                        "prior-games-only offensive-involvement proxies",
                        "projected teammate-context changes"],
            "forbidden": ["actual target-game starter status", "actual target-game minutes",
                          "actual target-game possessions",
                          "actual target-game shots, assists or turnovers",
                          "actual target-game lineup membership", "post-cutoff availability",
                          "source system as a predictive feature",
                          "retrospective transaction evidence in the primary arm"],
        },
        "feature_artifact": {
            "id": "turnover_role_context_features_v1",
            "grain": ["game_id", "team_id", "player_id", "decision_time_label"],
            "decision_time_label": "pregame_cutoff (the contract's forecast_cutoff for that game)",
        },
        "feature_groups": {
            "1_projected_role": {
                "fields": ["proj_minutes", "proj_minutes_share", "proj_off_poss",
                           "proj_off_poss_share", "p_active", "proj_rotation_rank",
                           "proj_top5_concentration"],
                "source": "projected_player_possessions/1 (tier_a_only) and v15 p_active",
                "origin": "projected",
                "why_share_not_volume": (
                    "projected possessions ALREADY enter the model as the count OFFSET, so raw "
                    "volume is not additional information. The SHARE and RANK features are tested "
                    "as ROLE proxies -- who is expected to carry the offence -- which is a "
                    "different quantity from how many possessions the player is on the floor for. "
                    "A share feature can only help if turnover rate PER POSSESSION varies with "
                    "role, not with volume."),
                "no_postgame_starter_indicator": True,
            },
            "2_prior_role": {
                "fields": ["trailing_minutes_share", "trailing_rotation_rank", "role_change"],
                "source": "master_player minutes for games strictly before the cutoff",
                "origin": "historically derived",
                "starter_status_OMITTED": (
                    "data/derived/starters.csv is not validated across BOTH source eras, and the "
                    "registration forbids reconstructing it inconsistently. Trailing start "
                    "probability and rotation-start features are therefore omitted rather than "
                    "built on an unvalidated base."),
            },
            "3_offensive_involvement": {
                "field": "offensive_involvement_proxy",
                "formula": ("EWMA(player FGA, alpha=0.10, prior games only) divided by "
                            "EWMA(team FGA over the same prior games), shrunk toward the "
                            "equal-share value 1/9 with strength K=50 EWMA-weighted attempts"),
                "source": "master_player fga, strictly prior games",
                "origin": "historically derived",
                "deliberately_not_called_usage_rate": (
                    "the formula is a field-goal-attempt share. It excludes turnovers and free-"
                    "throw trips, so it does NOT satisfy the standard usage-rate definition and "
                    "must not carry that name."),
                "assists_excluded": "assist attribution is not validated across both source eras",
                "shrinkage_for_low_support": True,
            },
            "4_teammate_context_change": {
                "field": "displaced_involvement",
                "definition": ("the summed trailing offensive_involvement_proxy of players who "
                               "appeared for this club in its last 10 games but are NOT Tier A "
                               "candidates for this game -- i.e. how much of the club's normal "
                               "offensive responsibility is absent from the projected rotation"),
                "incremental_not_absolute": (
                    "it measures the CHANGE from the club's own historical personnel baseline, "
                    "not the total strength of the current roster"),
                "sources": ["Tier A projected candidates", "cutoff-valid projected exposure",
                            "frozen prior-games-only teammate involvement estimates"],
                "tier_b_and_s2_excluded_from_the_primary": True,
            },
        },
        "frozen_arms": {
            "A": "league-constant benchmark (frozen from P1)",
            "D": "frozen P1 EWMA-shrunk incumbent, unchanged",
            "E": "D plus projected-role features",
            "F": "D plus prior-role features",
            "G": "D plus the offensive-involvement proxy",
            "H": "D plus projected teammate-context change",
            "I": "D plus ALL of groups 1-4, frozen here before any result is visible",
        },
        "arm_I_is_frozen_now": ("arm I is the union of the four registered groups. It is NOT to be "
                                "assembled afterwards from whichever features win."),
        "failed_group_policy": ("if a group fails its provenance or validation gate, its arm is "
                                "REMOVED before execution through a registered pre-result erratum "
                                "and is NOT replaced with a new idea"),
        "model_form": {
            "family": "Poisson", "link": "log",
            "offset": "log(projected or realised offensive possessions) PLUS log(frozen P1 Arm D rate)",
            "why_that_offset": ("with both terms in the offset, beta = 0 reproduces Arm D EXACTLY, "
                                "so every coefficient measures departure from the frozen incumbent"),
            "coefficients": "pooled across all players; NO per-player slopes",
            "transformations": "all features standardised using TRAINING-FOLD means and standard deviations only",
            "interactions": "NONE",
            "regularisation": {"type": "ridge (L2) on the coefficients, intercept unpenalised",
                               "lambda": RIDGE_LAMBDA, "frozen_in_advance": True,
                               "no_penalty_search": True},
            "clipping": "predicted rate clipped to [0, 1] per offensive possession, as in P1",
            "missing_values": "mean-imputed within the training fold and flagged; never dropped",
            "training_windows": ("expanding walk-forward by SEASON: predict season Y using all "
                                 "rows from seasons strictly before Y"),
            "minimum_training_rows": MIN_TRAIN_ROWS,
            "cold_seasons": ("a season with insufficient prior training rows falls back to beta = 0, "
                             "i.e. exactly Arm D. 2021 has no prior season and always falls back."),
            "hyperparameter_estimation": "NONE learned; lambda and alphas are preregistered constants",
        },
        "tracks": {
            "intrinsic": "realised offensive-possession exposure; ORACLE DIAGNOSTIC ONLY",
            "operational": ("every Tier A candidate obligation with projected offensive-possession "
                            "exposure, INCLUDING candidates who do not appear. Team aggregation "
                            "begins from the full pregame obligation set, never from realised rows."),
            "companion": "the same frozen team/unattributed component added to every arm",
        },
        "primary_decision": ("does a P2 challenger improve OPERATIONAL player-attributed "
                            "team-turnover MAE over frozen Arm D?"),
        "sign_convention": ("all paired differences are INCUMBENT absolute error MINUS CHALLENGER "
                            "absolute error. POSITIVE means the challenger BEATS the incumbent."),
        "passing_bar": ("a nonzero pooled coefficient or a player-level deviance gain is NOT "
                        "sufficient. The challenger must add STABLE team-level OPERATIONAL value "
                        "beyond D."),
        "required_ablations": ["projected role", "prior role", "offensive involvement",
                               "teammate-context change"],
        "collinearity_rule": ("if projected role and offensive involvement are strongly collinear, "
                              "report it and make no individual causal claim"),
        "interpretation_rules": [
            "a role feature does NOT solve the turnover-opportunity denominator problem",
            "the v1 denominator remains offensive-possession exposure; role features only explain "
            "variation in turnover opportunity WITHIN that broad exposure",
            "a positive result supports richer conditional rate modelling; it does NOT establish "
            "that offensive possessions are the natural final denominator",
            "do not promote on player-level deviance alone, one season, one club, "
            "non-appearing-candidate performance alone, a combined arm assembled after results, "
            "or a gain obtained only from retrospective evidence",
        ],
        "stop_boundary": ["no mechanism-specific turnover models", "no P1 retune",
                          "no candidate-universe change",
                          "no projected-exposure revision in response to results",
                          "no opponent defensive pressure", "no steal linkage",
                          "no turnover forecasts into the team model",
                          "no rebounds, assists, blocks, fouls or shot models"],
    },
}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--list", action="store_true")
    ap.parse_args()
    have = {json.loads(l).get("experiment_id")
            for l in REG.read_text(encoding="utf-8").splitlines() if l.strip()}
    with REG.open("a", encoding="utf-8") as fh:
        for r in (P1_FINAL, P2):
            if r["experiment_id"] in have:
                print(f"skip: {r['experiment_id']}"); continue
            fh.write(json.dumps(r, sort_keys=False) + "\n")
            print(f"appended: {r['experiment_id']}")


if __name__ == "__main__":
    main()
