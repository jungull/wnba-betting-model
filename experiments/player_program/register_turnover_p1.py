#!/usr/bin/env python3
"""register_turnover_p1.py — freeze `turnover_rate_pooled_baseline_v1` BEFORE fitting."""
from __future__ import annotations
import argparse, hashlib, json, subprocess                                     # noqa: E401
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REG = HERE / "arm_registry.jsonl"
EXP = "turnover_rate_pooled_baseline_v1"

# ---- frozen hyperparameters, chosen BEFORE any result is visible ------------------ #
EB_PRIOR_K = 200.0      # offensive possessions of prior strength
EWMA_ALPHA = 0.10       # effective window ~ 2/alpha - 1 = 19 games
MIN_EXPOSURE = 1        # a prediction needs >=1 prior offensive possession for B/C/D
TEAM_MIN_PRIOR_TEAM_GAMES = 20


def _sha(rel: str):
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


RECORD = {
    "schema": "player_program_arm_registry/1", "kind": "arm", "experiment_id": EXP,
    "arm_id": "turnover_rate_pooled_baseline/1",
    "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "registered_before_execution": True,
    "registered_at_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                           capture_output=True, text=True).stdout.strip(),
    "extra": {
        "status": "historical development evidence only; cannot promote a production model",
        "primary_target": "total player-attributed turnover COUNT per (game_id, team_id, player_id)",
        "mechanisms": "preserved for diagnostics; NO separate mechanism models in this wave",
        "withdrawn_arm": {
            "arm": "starter/bench adjustment on top of the best of A-D",
            "why": ("it would select the parent arm AFTER results are visible, and role could rely "
                    "on target-game information. Role belongs in a separately registered later "
                    "wave, and only after a cutoff-valid PROJECTED-role artifact is validated."),
        },
        "p0_corrections_applied": {
            "duplicate_policy": {
                "id": "source_aware_exact_duplicate/1",
                "verdict": "the duplicated legacy EVENTNUM records are BYTE-LEVEL duplicates",
                "rule": "drop exact all-column duplicate source rows per game file, keep the first",
                "general": "applies to the whole artifact and both stores; not aimed at any external total",
                "rows_dropped": 7, "games_affected": 7,
                "effect": "external team reconciliation moved from 2989/2990 to 2990/2990 exact",
                "receipt": "turnover_targets_v1/DUPLICATE_ADJUDICATION.json",
            },
            "zero_exposure_policy": {
                "id": "zero_exposure_degraded/1",
                "rows": 57, "turnovers_represented": 0,
                "treatment": ("count targets RETAINED in the canonical and team artifacts; "
                              "EXCLUDED from rate fitting and intrinsic rate evaluation because "
                              "the denominator is undefined. No epsilon denominator; the rate is "
                              "NOT treated as zero."),
                "receipt": "turnover_targets_v1/ZERO_EXPOSURE_AUDIT.json",
            },
            "unresolved_no_team_event": "1 event; outside player and team targets; reported separately",
        },
        "frozen_arms": {
            "A_league_constant": "prior-games league player-attributed turnovers / prior-games league player offensive possessions",
            "B_career_shrunk": "career-to-date player rate, empirical-Bayes shrunk to the league rate",
            "C_season_shrunk": "season-to-date player rate, empirical-Bayes shrunk to the league rate",
            "D_ewma_shrunk": "possession-weighted trailing EWMA player rate, shrunk to the league rate",
        },
        "prohibited_features": ["role", "starter/bench", "opponent", "teammate", "matchup",
                                "source_system", "player archetype", "player-specific slopes"],
        "frozen_estimators": {
            "numerator": "player-attributed turnover COUNT from player_turnover_targets/1",
            "denominator": "realised player OFFENSIVE POSSESSIONS from player_possessions/2",
            "empirical_bayes_formula": "r_hat = (x_prior + K * r_league_prior) / (n_prior + K)",
            "prior_strength_K": {
                "value": EB_PRIOR_K, "units": "offensive possessions",
                "estimated_from_data": False,
                "rationale": ("PREREGISTERED CONSTANT, not learned. 200 offensive possessions is "
                              "roughly three to four games of a starter's offensive exposure at "
                              "~55-60 offensive possessions per game. Fixing it removes any "
                              "question of estimating a prior from post-cutoff information."),
                "recomputed_per_fold": False,
            },
            "r_league_prior": ("recomputed at every cutoff from games strictly earlier only; never "
                               "from the complete historical artifact"),
            "ewma": {"alpha": EWMA_ALPHA,
                     "form": "separate possession-weighted EWMA of numerator and denominator",
                     "effective_window_games": round(2 / EWMA_ALPHA - 1),
                     "rationale": ("alpha 0.10 gives an effective window of ~19 games, about half "
                                   "a WNBA regular season -- form over half a season. Chosen "
                                   "before fitting from that basketball rationale."),
                     "no_decay_search": True},
            "minimum_exposure": MIN_EXPOSURE,
            "zero_history_fallback": "arms B, C and D fall back to arm A's league rate",
            "rookies_and_returning_players": "zero prior history -> the league-rate fallback",
            "career_history_across_team_changes": "FOLLOWS THE PLAYER; career history is not reset by a club change",
            "season_to_date_after_a_team_change": "FOLLOWS THE PLAYER within the season; not reset by a club change",
            "offseason_reset": "arm C resets at each season boundary; arms B and D do not",
            "postseason": "pooled with the regular season; playoff games both predict and enter history",
            "unresolved_or_degraded_labels": "zero-exposure rows excluded from rate fitting and intrinsic evaluation; counts retained",
            "clipping": "predicted rate clipped to [0, 1] turnovers per offensive possession; no other clipping",
        },
        "team_unattributed_companion": {
            "shared_identically_by_every_player_arm": True,
            "formula": ("league-pooled prior-games-only team/unattributed turnovers divided by "
                        "league-pooled prior-games-only team offensive possessions"),
            "shrinkage": "none; a pooled league ratio",
            "season_opening_fallback": "none needed beyond the minimum-support rule",
            "minimum_support": f"{TEAM_MIN_PRIOR_TEAM_GAMES} prior team-games, else the team-game is excluded from the total-turnover metric",
            "playoffs": "pooled with the regular season",
            "expansion_or_new_teams": "unaffected, because the rate is league-pooled rather than per-team",
            "projected_team_possession_source": "team_possession_prior/1 projected_team_off_possessions",
            "cutoff_and_ordering": "games with game_date strictly earlier than the target game's date",
        },
        "prediction_protocol": {
            "one_prediction_per_eligible_player_game": True,
            "history": "only games completed before that game's canonical cutoff",
            "forbidden": ["target-game event, possession, minutes, lineup or box score",
                          "any post-cutoff information"],
            "intrinsic_track": "rate x REALISED offensive possessions — ORACLE-EXPOSURE DIAGNOSTIC ONLY",
            "operational_track": ("the SAME frozen rate x cutoff-valid PROJECTED offensive "
                                  "possessions from projected_player_possessions_v1; no refit and "
                                  "no different rate model"),
            "identical_rows_within_each_track": "all four arms on the same player-games and team-games",
            "cross_track_comparison": "only on the common observation set",
        },
        "evaluation_hierarchy": {
            "intrinsic_primary": "player-game POISSON DEVIANCE conditional on realised exposure",
            "operational_primary": "TEAM-GAME MAE for aggregated player-attributed turnovers",
            "operational_secondary": "total team-turnover MAE after adding the fixed companion component",
            "also_report": ["player-game count MAE", "RMSE", "bias",
                            "calibration by predicted-count bucket", "team-game bias",
                            "game-clustered paired confidence intervals", "by season",
                            "by source system (DIAGNOSTIC ONLY)", "by historical exposure support",
                            "by projected-exposure support", "rookie and low-history performance",
                            "percentage of games improved and worsened"],
            "source_stratification_is_not_evidence": (
                "source and season type are confounded, so source-stratified results are "
                "data-quality diagnostics, never evidence that source should enter the model"),
        },
        "interpretation_rules": [
            "an arm may show intrinsic signal and still fail operationally if projected exposure is poor",
            "do not promote on oracle-exposure performance alone",
            "do not promote on player-game improvement without team aggregation improvement",
            "do not promote on one season, one source schema, one support bucket or a post hoc mechanism finding",
            "do not declare an arm superior on one secondary metric or one subgroup",
            "these results may NOT alter the turnover taxonomy, duplicate policy, possession artifact or projected-exposure artifact",
        ],
        "stop_boundary": ["no starter/bench arm", "no alternate EWMA decay search",
                          "no shrinkage tuning after results", "no mechanism-specific models",
                          "no opponent or matchup features", "no steal linkage",
                          "no turnover forecasts into the team model", "no other event channel"],
    },
}


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    have = {json.loads(l).get("experiment_id")
            for l in REG.read_text(encoding="utf-8").splitlines() if l.strip()}
    if a.list:
        print(f"{'PRESENT' if EXP in have else 'ABSENT '}  {EXP}"); return
    if EXP in have:
        print(f"skip (already registered): {EXP}"); return
    with REG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(RECORD, sort_keys=False) + "\n")
    print(f"appended: {EXP}\nat commit {RECORD['registered_at_commit']}")


if __name__ == "__main__":
    main()
