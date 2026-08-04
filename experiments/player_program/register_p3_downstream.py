#!/usr/bin/env python3
"""register_p3_downstream.py — freeze the P3 downstream comparison BEFORE it is executed.

Registers `p3_projected_exposure_downstream_v1`: does the frozen P3 player-impact signal add
chronological out-of-sample team-forecast value when aggregated with CUTOFF-VALID PROJECTED
exposure, rather than the oracle rotations every prior positive P3 result depended on?

This is HISTORICAL DEVELOPMENT EVIDENCE ONLY. It cannot promote or replace the production team
incumbent, and it does not promote projected_player_possessions_v1.

Nothing is refit. The P3 coefficients, the exposure model, the pace model and the team incumbent
are all consumed frozen. The exposure allocator is not touched after results are opened.

Run::

    python experiments/player_program/register_p3_downstream.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARM_REGISTRY = HERE / "arm_registry.jsonl"
SCHEMA = "player_program_arm_registry/1"
EXP = "p3_projected_exposure_downstream_v1"

INCUMBENT = "experiments/channel_reval/predictions_v2.csv"
P3 = "experiments/player_program/fits_v1/p3_coefficients_v1.parquet"
EXPOSURE = "experiments/player_program/projected_exposure_v1/projected_player_possessions_v1.parquet"
ROTATIONS = "experiments/player_program/projected_exposure_v1/projected_team_rotations_v1.parquet"
PACE = "experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(rel: str) -> str | None:
    p = ROOT / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


RECORD = {
    "schema": SCHEMA,
    "kind": "arm",
    "experiment_id": EXP,
    "arm_id": "p3_projected_exposure_downstream/1",
    "registered_at": _utc(),
    "registered_before_execution": True,
    "registered_at_commit": _head(),
    "extra": {
        "purpose": (
            "test whether the frozen P3 player-impact signal adds chronological out-of-sample "
            "team-forecast value when aggregated using CUTOFF-VALID PROJECTED EXPOSURE rather than "
            "actual lineups, actual minutes, actual stint durations or actual possessions."),
        "status": {
            "evidence_class": "historical development evidence only",
            "cannot": ["promote or replace the production team incumbent",
                       "promote projected_player_possessions_v1",
                       "retune P3", "alter the team incumbent",
                       "alter the exposure allocator after results are opened"],
        },
        "why_this_matters": (
            "every positive P3 result on the record is ORACLE-CONDITIONED: it used realised "
            "ten-player lineups, realised stint boundaries, realised possession counts and "
            "realised exposure. Live-achievable P3 value is unestablished, not disproven. This is "
            "the first information-honest test."),
        "frozen_inputs": {
            "team_incumbent": {
                "artifact": INCUMBENT,
                "sha256": _sha(INCUMBENT),
                "what": ("the frozen STRUCTURAL chain architecture from "
                         "chanreval_2026_structural_repaired; columns str_home_cal and "
                         "str_away_cal are the calibrated home and away score forecasts"),
                "rows": "673 games, seasons 2024-2026, regular season and playoffs",
                "not_used": ("experiments/arm_incumbent/ is REJECTED (target-box membership "
                             "controlled its coverage) and is not consumed here"),
            },
            "p3_coefficients": {
                "artifact": P3, "sha256": _sha(P3),
                "rows": "1,177 player-cutoff rows",
                "cutoff_semantics": ("training_cutoff_season C was fit for test season C+1 "
                                     "(fit_rate_and_p3.py line 182: int(test_s) - 1). For a target "
                                     "game in season Y the admissible row is "
                                     "training_cutoff_season == Y - 1. Available cutoffs are "
                                     "2021-2025, so target seasons 2022-2026 are covered and the "
                                     "incumbent's 2024-2026 sample is fully covered."),
            },
            "exposure": {
                "player": {"artifact": EXPOSURE, "sha256": _sha(EXPOSURE)},
                "rotations": {"artifact": ROTATIONS, "sha256": _sha(ROTATIONS)},
                "pace": {"artifact": PACE, "sha256": _sha(PACE)},
                "provenance_note": (
                    "the operator authorised 'commit 9806cb5 versions'. The corrections commit that "
                    "follows 9806cb5 adds LABELLING columns only -- the four evidence fields and "
                    "the per-regime reconciliation in the receipt. Every projected minute and every "
                    "projected possession is byte-identical to 9806cb5. That identity is asserted "
                    "by the executor before any arm is evaluated and recorded in the result "
                    "receipt; if it fails, the experiment fails closed."),
            },
        },
        "refit_prohibition": ["P3 coefficients", "exposure model", "pace model", "team incumbent"],
        "primary_universe": {
            "regime": "tier_a_only",
            "requirements": [
                "game present in the frozen incumbent artifact",
                "pace resolved for both clubs",
                "rotation status == normal for BOTH clubs (a one-sided game is excluded)",
                "incumbent str_home_cal and str_away_cal present",
                "an admissible P3 cutoff exists for the target season",
                "a resolved trailing personnel baseline for BOTH clubs",
            ],
            "identical_rows_across_all_arms": (
                "MANDATORY. Every arm is evaluated on exactly the same games, team rows and "
                "decision times. No adjusted arm may select an easier subset. The executor "
                "computes ONE eligibility mask and applies it to every arm."),
            "exclusions": "every exclusion and its reason is counted and reported",
        },
        "sensitivity_universes": {
            "regimes": ["tier_a_plus_tx_b", "tier_a_plus_tx_b_plus_s2"],
            "rule": ("separately labelled; MAY NOT enlarge or redefine the primary evaluation "
                     "universe. Both are non-production-eligible: transaction Tier B is not "
                     "available at the cutoff, S2 is cutoff-available but operationally "
                     "implausible."),
        },
        "personnel_effect_construction": {
            "units": ("orapm_100 and drapm_100 are points per 100 possessions. Multiplying by "
                      "possessions/100 yields POINTS, the same unit as the incumbent's score "
                      "forecast."),
            "sign_conventions": {
                "orapm_100": "points ADDED per 100 offensive possessions; raises the player's OWN team's score",
                "drapm_100": ("points PREVENTED per 100 defensive possessions; the artifact already "
                              "flipped the internal points-allowed sign, so a POSITIVE value LOWERS "
                              "the OPPONENT's score"),
                "net_rapm_100": "orapm_100 + drapm_100",
            },
            "equations": {
                "E_off(T,g)": "sum_p orapm_100[p, Y-1] * projected_off_possessions[p,T,g] / 100",
                "E_def(T,g)": "sum_p drapm_100[p, Y-1] * projected_def_possessions[p,T,g] / 100",
                "E_net(T,g)": "sum_p net_rapm_100[p, Y-1] * projected_off_possessions[p,T,g] / 100",
            },
            "players_without_a_coefficient": {
                "rule": "coefficient 0.0 -- the neutral, league-average value in RAPM units",
                "not": "exclusion of the player or of the team-game",
                "reported": ("share of projected possessions covered by a coefficient, per team-game "
                             "and pooled; results are also bucketed by this coverage"),
            },
            "possession_scaling": "the projected possessions of projected_player_possessions/1, unchanged",
        },
        "centering_rule": {
            "why": ("the incumbent already contains historical team tendencies. Adding raw "
                    "exposure-weighted player coefficients would double-count team strength. The "
                    "adjustment must represent CURRENT projected personnel MINUS the team's "
                    "prior-games-only expected personnel."),
            "baseline_definition": (
                "B_x(T,g) = the mean of E_x(T,g') over team T's games g' strictly earlier than g, "
                "computed from THIS SAME exposure artifact, for x in {off, def, net}"),
            "frozen_ladder": [
                {"level": 1, "rule": "at least 3 prior SAME-SEASON games: mean over the most recent 10"},
                {"level": 2, "rule": "else at least 3 games in the immediately preceding season: "
                                     "mean over the most recent 10"},
                {"level": 3, "rule": "else the mean of E_x over ALL games strictly before the cutoff, "
                                     "all teams"},
                {"level": 4, "rule": "else UNRESOLVED -- the game is excluded from every arm"},
            ],
            "trailing_window_K": 10,
            "minimum_history_m": 3,
            "season_opening_fallback": "levels 2 then 3 then exclusion",
            "expansion_teams_and_unresolved_baselines": (
                "an expansion club has no prior season, so it falls to level 3 and then to "
                "exclusion. Excluded games are counted and reported, never silently dropped."),
            "cutoff_rule": "game_date strictly earlier than the target game's date",
            "why_this_ladder": (
                "it is the SAME window, minimum and fallback structure already registered and "
                "validated for team_possession_prior/1. Reusing a validated ladder avoids "
                "introducing a fresh arbitrary choice, and it was fixed before any downstream "
                "number was seen."),
            "no_post_hoc_selection": (
                "the window, the decay rule (none -- unweighted mean), the minimum history, the "
                "scaling and the fallbacks are frozen HERE. None may be chosen or changed after "
                "viewing downstream accuracy. Only ONE baseline rule is registered, so there is no "
                "multiplicity to correct for."),
            "adjustments": {
                "delta_off(T,g)": "E_off(T,g) - B_off(T,g)",
                "delta_def(T,g)": "E_def(T,g) - B_def(T,g)",
                "delta_net(T,g)": "E_net(T,g) - B_net(T,g)",
            },
        },
        "frozen_arms": {
            "A_incumbent": {"home": "str_home_cal", "away": "str_away_cal"},
            "B_offensive": {"home": "str_home_cal + delta_off(H)",
                            "away": "str_away_cal + delta_off(A)"},
            "C_net": {"home": "str_home_cal + delta_net(H)",
                      "away": "str_away_cal + delta_net(A)"},
            "D_separate": {"home": "str_home_cal + delta_off(H) - delta_def(A)",
                           "away": "str_away_cal + delta_off(A) - delta_def(H)",
                           "note": "the offensive effect acts on the player's OWN team's score; the "
                                   "defensive effect acts on the OPPONENT's score"},
            "E_defensive_diagnostic": {"home": "str_home_cal - delta_def(A)",
                                       "away": "str_away_cal - delta_def(H)"},
        },
        "predeclared_mathematical_consequences": {
            "1_equal_exposure": (
                "v1 assigns EQUAL projected offensive and defensive exposure to every player, so "
                "E_net == E_off + E_def EXACTLY, and likewise for the deltas. Any difference "
                "between Arms C and D therefore arises from coefficient construction, estimation "
                "and shrinkage -- NEVER from different offensive and defensive exposure estimates."),
            "2_identical_margins": (
                "it follows algebraically that Arms C and D produce IDENTICAL margin forecasts: "
                "C's margin adjustment is delta_net(H) - delta_net(A); D's is "
                "[delta_off(H) - delta_def(A)] - [delta_off(A) - delta_def(H)], which equals "
                "delta_off(H) + delta_def(H) - delta_off(A) - delta_def(A) = the same quantity. "
                "C and D can differ ONLY in how the adjustment is split between the home and away "
                "SCORES. This is predicted here, before execution, and is asserted numerically by "
                "the executor."),
            "3_consequence_for_interpretation": (
                "a margin-MAE difference between C and D would indicate an executor defect, not a "
                "finding. The informative comparison between C and D is on home-score and "
                "away-score MAE."),
        },
        "evaluation": {
            "harness": "evalharness.metrics and evalharness.compare, the existing frozen contract",
            "metrics": [
                "team-score MAE, RMSE and bias (home rows and away rows)",
                "margin MAE, RMSE and bias",
                "total-score MAE",
                "margin calibration slope (OLS of realised margin on predicted margin)",
                "paired arm-minus-incumbent differences",
                "game-clustered bootstrap confidence intervals",
                "results by season",
                "coverage and exclusion counts",
                "performance by coefficient-support bucket and by projected-exposure bucket",
            ],
            "clustering": (
                "paired inference is clustered at the GAME level so the two team-score rows from "
                "one game are never treated as independent"),
            "concentration_reporting": (
                "report whether any apparent gain is concentrated in one season, one team, "
                "high-exposure players or a small number of games"),
            "interpretation_bar": (
                "a numerically positive difference is NOT described as meaningful unless its "
                "uncertainty and stability support that conclusion"),
        },
        "leakage_requirements": [
            "every P3 coefficient row used must predate the target game's cutoff "
            "(training_cutoff_season == season - 1)",
            "the trailing personnel baseline uses only strictly earlier games",
            "no actual target-game minutes, lineups, stint durations, possessions or pace",
            "no target-game outcomes in any feature",
            "no post-cutoff transactions or availability",
            "canonical game and decision-time identities preserved",
        ],
        "outputs": {
            "results": "experiments/player_program/p3_downstream_v1/P3_DOWNSTREAM_RESULTS.json",
            "rows": "experiments/player_program/p3_downstream_v1/p3_downstream_rows.parquet",
        },
        "stop_boundary": (
            "after the registered comparison and the two sensitivity analyses, STOP. Do not "
            "promote a model, retune P3, alter the team incumbent, start event-channel models or "
            "begin another exposure revision without authorisation."),
    },
}


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
        print(f"{'PRESENT' if EXP in have else 'ABSENT '}  {EXP}")
        return
    if EXP in have:
        print(f"skip (already registered): {EXP}")
        return
    with ARM_REGISTRY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(RECORD, sort_keys=False) + "\n")
    print(f"appended: {EXP}\nat commit {RECORD['registered_at_commit']}")


if __name__ == "__main__":
    main()
