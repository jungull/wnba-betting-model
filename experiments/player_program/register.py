#!/usr/bin/env python3
"""register.py — append registrations to the PLAYER PROGRAM's own registry.

The shared `experiments/registry.jsonl` belongs to the team thread and is **never written by this
program**. Player-program registrations live in `experiments/player_program/registry.jsonl`, which
is append-only by the same convention.

Each registration is frozen at the moment it is appended: it records what will be done and how it
will be judged, BEFORE any result is seen. Corrections go to an erratum, never to the record.

**Nothing here is scored.** A registration states a hypothesis, a metric name and a bar; it
contains no measurement of any model against any outcome.

Run::

    python experiments/player_program/register.py          # append anything not already present
    python experiments/player_program/register.py --list    # show what is registered
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REGISTRY = HERE / "registry.jsonl"
SCHEMA = "player_program_registry/1"

#: Everything in this program is frozen against these. Repeated on every record so a row is
#: self-contained.
STANDING = {
    "scoring_authorization": "REQUIRED before any outcome-comparing metric is computed",
    "coverage_means": "OBLIGATION COMPLETENESS, never statistical coverage",
    "firewall": "project_docs/PROGRAM_FIREWALL.md is binding; no 2025/2026 outcome obtained "
                "through the game-model or betting programs may influence a player-rate decision",
    "isolation": "player program only; the shared experiments/registry.jsonl is not written",
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _spec_hash(rel: str) -> str | None:
    p = HERE.parents[1] / rel
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def records() -> list[dict]:
    v5_spec = "experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md"
    return [
        # ------------------------------------------------------------------ #
        {
            "kind": "specification",
            "id": "prediction_contract_v5",
            "title": "a candidacy universe that admits players who arrive after the season starts",
            "status": "SPECIFIED, NOT IMPLEMENTED",
            "spec_document": v5_spec,
            "spec_sha256": _spec_hash(v5_spec),
            "supersedes": None,
            "does_not_edit": ["prediction_contract_v4", "experiments/prediction_contract_v4/*"],
            "motivation_measured": {
                "receipt": "experiments/player_program/CANDIDACY_GAP_RECEIPT.json",
                "played_player_team_games": 28322,
                "not_an_obligation": 977,
                "pct": 3.45,
                "by_cause": {"season_opener": 749, "mid_season_arrival": 176,
                             "early_season_partial_window": 52},
            },
            "candidacy_sources": {
                "S1": "in-season box membership (v4's rule, unchanged)",
                "S2": "prior-season franchise membership, admitted only below S2_HORIZON=5",
                "S3": "captured pregame availability report, 2026-07-30 onward only",
                "S4": "transaction feed — RESERVED AND DECLARED UNAVAILABLE",
            },
            "eras": {"box_only": "2021 -> 2026-07-29 (S1,S2)",
                     "report_assisted": "2026-07-30 -> (S1,S2,S3)"},
            "binding_constraints": [
                "historical roster membership is never manufactured",
                "a source whose as-of bound is not STRICTLY earlier than the cutoff is not "
                "admitted; equality is a violation",
                "every v4 obligation must be a v5 obligation (superset property, checked)",
                "the candidacy exclusion audit is mandatory; a build without it FAILS",
                "a build reporting a zero exclusion count has a bug",
                "n_prior_games is not emitted under any circumstances",
            ],
            "history_fields": ["n_prior_candidate_obligations", "n_prior_appearances",
                               "n_prior_team_games"],
            "expected_effect_declared_before_build": {
                "season_openers_recovered_via_S2": 324,
                "season_openers_remaining_excluded": 425,
                "mid_season_arrivals_excluded_in_box_only_era": 176,
                "note": "obligation growth exceeds 324 because S2 admits CANDIDATES, only some "
                        "of whom play; the build reports the realised figure",
            },
        },
        # ------------------------------------------------------------------ #
        {
            "kind": "defect",
            "id": "P-D3__n_prior_games_overloaded",
            "status": "OPEN, resolved by prediction_contract_v5 section 4",
            "defect": ("cbs_player_runner_v14 emits n_prior_games meaning "
                       "n_prior_candidate_games for p_active on FITTED folds but "
                       "n_prior_appearances for all four targets on the DEGENERATE 2021 fold"),
            "consequence": ("any per-history-bucket report pooling 2021 with later seasons "
                            "buckets 2021 p_active rows on the wrong quantity"),
            "resolution": "three named fields, each defined once, never conditioned on fold or "
                          "target; the field each target read is recorded in the prediction row",
        },
        # ------------------------------------------------------------------ #
        {
            "kind": "track",
            "id": "P1__bottom_up_team_forecast",
            "title": "aggregate the player layer into home score, away score, margin and total",
            "status": "REGISTERED, blocked on scoring authorization and contract v5",
            "aggregates": ["availability", "minutes", "opportunities", "efficiency", "impact"],
            "targets": ["home_score", "away_score", "margin", "total",
                        "structural scoring channels ch_ft/ch_3pt/ch_paint/ch_np2"],
            "binding_prior_evidence": {
                "id": "bottomup_3pt_channel_v1",
                "source": "experiments/registry.jsonl (team thread), quoted not recomputed",
                "verdict": "improved its own channel, DEGRADED the joint forecast",
                "channel_mae_challenger": 7.0613613907012915,
                "channel_mae_incumbent": 7.114159926587364,
                "margin_mae_challenger_sub": 10.3569,
                "margin_mae_incumbent": 10.1753,
                "delta_degradation": 0.1816,
                "tolerance": 0.05,
                "n_games": 627,
                "decomposition": {
                    "challenger_sub": {"var_eh": 124.58480090951613,
                                       "var_ea": 121.0921279124604,
                                       "cov_eh_ea": 37.34476421448295,
                                       "corr_eh_ea": 0.3035610367421815,
                                       "var_margin_err": 171.10652244792126},
                    "incumbent": {"var_eh": 126.84376143574963,
                                  "var_ea": 121.21968716625749,
                                  "cov_eh_ea": 40.46128148404017,
                                  "corr_eh_ea": 0.3257806537168926,
                                  "var_margin_err": 167.26994873275947},
                },
                "mechanism": ("var(margin err) = var(e_h) + var(e_a) - 2cov. The bottom-up layer "
                              "reduced each side's error variance but DECORRELATED the two "
                              "sides, and the lost covariance cost more than the variance "
                              "saved. The team model's two-sided errors share a common "
                              "league/pace/era component that cancels in the margin; per-player "
                              "idiosyncratic noise does not."),
                "scope_of_the_verdict": ("it closes THAT IMPLEMENTATION, not the bottom-up "
                                         "approach. The challenger was unconstructible on "
                                         "2021-2023 (Stage-A artifacts test-years only), so the "
                                         "incumbent's train-years-only calibration was applied "
                                         "unchanged and no refit was possible without touching "
                                         "test data. The uncalibrated sensitivity agrees in "
                                         "direction (10.4371 vs 10.3402), so the verdict stands, "
                                         "but a rebuilt layer with full-history Stage-A "
                                         "artifacts is entitled to a fresh test."),
                "obligation": "PRESERVE AND REPRODUCE this decomposition for every P1 candidate",
            },
            "mandatory_reported_quantities": [
                "var(e_home)", "var(e_away)", "cov(e_home,e_away)", "corr(e_home,e_away)",
                "var(margin error)", "margin MAE", "total MAE",
            ],
            "promotion_rule": ("must improve its player target AND not degrade the joint team "
                               "forecast. Per-side improvement is NOT evidence."),
            "constraints": ["the 200-minute team constraint (plus OT)",
                            "statistical accounting identities",
                            "uncertainty propagation",
                            "cold-start and missing-player accounting"],
        },
        # ------------------------------------------------------------------ #
        {
            "kind": "track",
            "id": "P2__scenario_and_roster_change_adjustment",
            "title": "how the FROZEN team forecast should change after a roster event",
            "status": "REGISTERED, blocked on scoring authorization and contract v5",
            "may_succeed_even_if_P1_fails": True,
            "events": ["injuries and absences", "returns and restrictions",
                       "starter or rotation changes", "trades and signings",
                       "minute reallocations"],
            "evaluated_against": "the FROZEN team forecast, on registered affected-game subsets",
            "constraints": ["must account for replacement players",
                            "must preserve the 200-minute team constraint",
                            "affected-game subsets registered BEFORE results are seen"],
            "why_separate": ("an adjustment layer needs only the DELTA to be right, not the "
                             "level. P1 requires the level. The prior bottom-up failure was a "
                             "level failure via lost error correlation, which an adjustment "
                             "applied to a frozen forecast does not inherit."),
        },
        # ------------------------------------------------------------------ #
        {
            "kind": "track",
            "id": "P3__player_impact_and_valuation",
            "title": "regularized adjusted plus-minus with teammate, opponent, lineup and "
                     "game-state adjustment",
            "status": "REGISTERED, blocked on the real player baseline suite and possession "
                      "reconciliation",
            "estimates": ["offensive impact", "defensive impact", "net impact", "uncertainty",
                          "expected effect at a proposed number of minutes"],
            "baseline": "raw on/off, as a BASELINE ONLY",
            "validation": ["future stint prediction", "future lineup prediction",
                           "year-over-year stability", "ridge penalty sensitivity",
                           "garbage-time sensitivity", "replacement-level behaviour",
                           "rookie and low-minute behaviour",
                           "downstream team-forecast contribution"],
            "explicitly_not_a_promotion_test": (
                "'known stars rank highly' is a DATA-QUALITY SMOKE TEST ONLY and is inadmissible "
                "as evidence of predictive value"),
            "garbage_time_rule": ("define using ONLY score differential and time remaining, "
                                  "never with reference to the final outcome; preserve BOTH a "
                                  "full-game and a competitive-possession version; do not delete "
                                  "low-leverage possessions"),
        },
        # ------------------------------------------------------------------ #
        {
            "kind": "preregistration",
            "id": "integration_forms_v1",
            "title": "three integration forms, compared later, none presumed preferred",
            "status": "PREREGISTERED",
            "forms": {
                "F1_full_bottom_up_replacement": "replace the team forecast entirely",
                "F2_player_derived_features": "add player-derived roster and lineup features to "
                                              "the existing team model",
                "F3_residual_scenario_adjustment": "apply an adjustment to the frozen team "
                                                   "forecast",
            },
            "no_presumption": ("full bottom-up replacement is NOT presumed preferred. "
                               "bottomup_3pt_channel_v1 is evidence against F1 specifically and "
                               "is neutral on F2 and F3."),
            "candidate_supplemental_features": [
                "minutes-weighted offensive RAPM",
                "minutes-weighted defensive RAPM",
                "expected active-roster strength",
                "impact lost or gained from the prior rotation",
                "replacement-level minutes",
                "roster continuity",
                "expected starter strength",
                "expected closing-lineup strength",
                "rotation uncertainty",
                "projected score-differential impact of the roster change",
            ],
            "evaluation_discipline": [
                "date/game/team/player-aware uncertainty; player-games are NOT independent",
                "pooled micro, macro across players, minutes-weighted, per-player where sample "
                "is adequate, by role and volume bucket, by history/cold-start bucket, by team "
                "and season, calibration, prediction-INTERVAL coverage, obligation completeness, "
                "complexity and operational cost",
                "small favourable results are retained in the Micro-Gain Portfolio, never "
                "discarded solely for failing to replace the champion",
            ],
        },
        # ------------------------------------------------------------------ #
        {
            "kind": "incumbent",
            "id": "minutes_ewma_alpha030_v1",
            "title": "standing incumbent for e_minutes_given_active",
            "status": "RETAINED pending re-evaluation on the corrected contract",
            "quoted_from": "experiments/registry.jsonl (team thread), NOT recomputed",
            "minutes_mae": 4.642781593266165,
            "vs_carry_forward": 5.391305582302545,
            "n_rows": 13501,
            "n_date_clusters": 253,
            "seasons": [2024, 2025, 2026],
            "frozen_alpha": 0.30,
            "gates": "1 P, 2 P, 3 P, 4 not provided, 5 P -> PASS",
            "gate4_note": "gate4_joint_forecast was NOT PROVIDED. No minutes or availability "
                          "result in this project has ever been tested against the joint team "
                          "forecast.",
        },
        {
            "kind": "micro_gain",
            "id": "MG-1__minutes_twostage_availability_v1",
            "title": "two-stage availability x minutes",
            "status": "RETAINED in the Micro-Gain Portfolio; not discarded",
            "quoted_from": "experiments/registry.jsonl (team thread), NOT recomputed",
            "minutes_mae": 4.605734380542951,
            "improvement": 0.037047212723215296,
            "ci_90": [0.011580176368386902, 0.061290897665984806],
            "bar": 0.10,
            "verdict": "FAILS gate1 (improvement below bar); CI EXCLUDES HARM",
            "stage_a_brier": 0.07963273556522257,
            "stage_a_brier_incumbent": 0.10844881554367054,
            "stage_a_bar_met": True,
            "exploratory_rmse_note": ("not preregistered: RMSE 6.928 vs 7.282. MAE on a "
                                      "zero-inflated mixture grades medians and structurally "
                                      "rewards hard zeros; the aggregation layer consumes MEANS, "
                                      "which RMSE grades. Relevant to P1."),
            "audits": "incumbent reproduction max dev 7.1e-15; shift-recompute 875 checks 0 "
                      "mismatches; permutation probe collapses to the shuffled mean",
        },
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    existing = []
    if REGISTRY.exists():
        existing = [json.loads(ln) for ln in
                    REGISTRY.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if args.list:
        for r in existing:
            print(f"  {r.get('kind','?'):16s} {r.get('id','?'):46s} {r.get('status','')}")
        print(f"  ({len(existing)} records)")
        return 0

    have = {r.get("id") for r in existing}
    added = 0
    with REGISTRY.open("a", encoding="utf-8", newline="") as fh:
        for rec in records():
            if rec["id"] in have:
                continue
            rec = {"schema": SCHEMA, "registered_at": _utc(), "standing": dict(STANDING), **rec}
            fh.write(json.dumps(rec, sort_keys=False) + "\n")
            added += 1
            print(f"  registered {rec['kind']:16s} {rec['id']}")
    print(f"{added} appended, {len(existing) + added} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
