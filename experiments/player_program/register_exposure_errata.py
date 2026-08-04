#!/usr/bin/env python3
"""register_exposure_errata.py — three corrections to the exposure bridge's own record.

Appended, never mutated in place, for the same reason every other correction in this program is:
a record sharing an id would silently rebind the arm under last-wins recomputation.

1. ``exposure_coverage__erratum_cutoff_valid_prior`` — the coverage claim was too strong. The
   artifact does NOT cover every historical game; it covers every game for which a cutoff-valid
   prior exists and FAILS CLOSED otherwise.
2. ``exposure_offdef__erratum_projection_assumption`` — the offensive/defensive equality was
   justified too strongly. The realised evidence supports ONE GAME-LEVEL possession total; it does
   not establish that individual players experience identical offensive and defensive possession
   counts, because substitutions occur BETWEEN possessions.
3. ``exposure_s2__policy_weak_evidence_diagnostic`` — S2-only is formally degraded, with declared
   plausibility diagnostics reported for EVERY regime so the comparison is complete.

**Nothing here is scored.**

Run::

    python experiments/player_program/register_exposure_errata.py
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


COVERAGE = {
    "schema": SCHEMA,
    "kind": "erratum",
    "experiment_id": "exposure_coverage__erratum_cutoff_valid_prior",
    "applies_to": "projected_player_possessions_v1",
    "corrects_record": "exposure_bridge__amendment_matchup_interaction_track",
    "corrects_clause": "consequences_for_this_artifact.must_supply[2]",
    "registered_at": _utc(),
    "defect_in_the_prior_description": (
        "the clause said the artifact supplies 'a cutoff-valid projection for EVERY historical "
        "game in the universe'. That is false as written. Eight team-games -- both sides of the "
        "four games on the first date of the 2021 season, the first date in the universe -- have "
        "no game strictly before their cutoff, so no prior-games-only pace estimate exists for "
        "them and none is emitted."),
    "corrected_language": (
        "the artifact covers every game for which a CUTOFF-VALID PRIOR EXISTS, and fails closed "
        "otherwise. Where no prior exists the team-game carries an explicit unresolved state and "
        "no possession projection; where a rotation can still be formed the projected minutes "
        "stand and only the possessions are withheld (status minutes_only_no_pace)."),
    "option_deliberately_rejected": {
        "option": "introduce a pre-universe opening prior to achieve full coverage",
        "why_rejected": (
            "the only data available to construct one lies AFTER those cutoffs. Computing an "
            "opening prior from later 2021 games would be retrospective fabrication of coverage. "
            "An explicit unresolved state is preferable to fabricated coverage."),
        "what_would_be_acceptable_later": (
            "a separately registered, genuinely EX ANTE pre-universe prior built from information "
            "that predates the 2021 season opener and uses no later 2021 or future information. "
            "None exists in this repository's data, so none is claimed."),
    },
    "consequence_for_the_matchup_track": (
        "a team's TRAILING PERSONNEL BASELINE is computable from this artifact for every game "
        "except those with no cutoff-valid prior. Deviation features must therefore handle the "
        "unresolved state explicitly rather than assuming full coverage."),
    "affected_rows": {
        "unresolved_pace_team_games": 8,
        "unresolved_pace_games": ["1022100001", "1022100002", "1022100003", "1022100004"],
        "all_on": "the first game date of the 2021 season, the first date in the universe",
    },
}


OFFDEF = {
    "schema": SCHEMA,
    "kind": "erratum",
    "experiment_id": "exposure_offdef__erratum_projection_assumption",
    "applies_to": "projected_player_possessions_v1",
    "corrects_record": "projected_player_possessions_v1",
    "corrects_clause": "frozen_config.minutes_to_possession_mapping.known_consequence_disclosed_in_advance",
    "registered_at": _utc(),
    "what_the_evidence_actually_supports": (
        "the realised home-minus-away team offensive possession difference has mean 0.002 with no "
        "systematic sign. That supports estimating ONE GAME-LEVEL possession total and applying it "
        "to both clubs. That is all it supports."),
    "defect_in_the_prior_description": (
        "the registration used that near-zero team-level difference to justify equal PLAYER-LEVEL "
        "offensive and defensive possessions. It does not establish that. Substitutions occur "
        "BETWEEN possessions, so an individual player's realised offensive and defensive "
        "possession counts can differ even when the two teams' game totals are identical -- a "
        "player subbed in during a defensive stint and out before the next offensive one is the "
        "trivial counterexample."),
    "corrected_status": {
        "equal_player_off_and_def_possessions_is": (
            "a SIMPLIFYING PROJECTION ASSUMPTION of v1, not an empirically established "
            "player-level fact"),
        "where_it_comes_from": (
            "both counts are derived from the SAME projected minute share and the SAME single "
            "game-level pace estimate. v1 projects no within-game substitution timing, so it "
            "carries no information that could separate the two counts."),
        "acceptable_because": (
            "it is registered in advance, disclosed, and consistent with the information v1 "
            "actually has. It is not acceptable to describe it as measured."),
        "what_would_relax_it": (
            "a projected substitution-timing or stint-level model, which v1 does not contain and "
            "which is not authorised here."),
    },
    "required_language_for_the_p3_ablation": (
        "the arms using NET coefficients and the arms using SEPARATE offensive and defensive "
        "coefficients share the SAME v1 exposure allocation. Any difference between them therefore "
        "reflects coefficient construction, estimation and shrinkage -- NOT a different exposure "
        "model. No result from that comparison may be attributed to exposure."),
    "does_not_change": "any number in the artifact; this corrects the interpretation only",
}


S2_POLICY = {
    "schema": SCHEMA,
    "kind": "policy",
    "experiment_id": "exposure_s2__policy_weak_evidence_diagnostic",
    "policy_id": "s2_weak_evidence_diagnostic/1",
    "applies_to": "projected_player_possessions_v1",
    "registered_at": _utc(),
    "finding_that_motivates_it": (
        "the S2-only sensitivity regime allocates up to 70 players across a single team-game, with "
        "team scale factors as low as 0.17. A 70-player rotation is not a rotation. The regime "
        "does not represent a plausible rotation forecast."),
    "policy": {
        "s2_regime_is": "a LABELLED WEAK-EVIDENCE DIAGNOSTIC",
        "s2_regime_is_not": "an operationally achievable forecast",
        "never": [
            "pool S2 with Tier A",
            "pool S2 with transaction-derived Tier B",
            "present S2 downstream results as operationally achievable forecasts",
        ],
        "field": "operationally_achievable = False for the tier_a_plus_tx_b_plus_s2 regime",
    },
    "declared_plausibility_diagnostics": {
        "reported_for": "EVERY regime -- Tier A and transaction-derived Tier B as well as S2, so "
                        "the comparison is complete and Tier A is not exempted from its own test",
        "fields": {
            "n_allocated": "count of players receiving projected minutes",
            "exceeds_standard_active_roster": (
                "n_allocated > 12. The WNBA standard maximum active roster is 12. Hardship "
                "exceptions can raise it temporarily, so this is a PLAUSIBILITY FLAG, not proof of "
                "error."),
            "n_players_ge_10_min": "conventional rotation-player count",
            "n_players_ge_20_min": "conventional heavy-rotation count",
            "effective_rotation_size": (
                "inverse Simpson index on projected minute shares, 1 / sum(share^2). A concentration "
                "measure: 200 minutes split evenly over k players gives exactly k."),
            "top5_minute_share": "share of the 200 team minutes held by the five largest allocations",
            "max_player_minutes": "largest single allocation",
            "min_player_minutes": "smallest nonzero allocation",
            "scale_factor": "200 / sum(raw_expected_minutes); already persisted",
            "extreme_scaling": (
                "scale_factor outside [0.8, 1.25]. Declared band, reciprocal-symmetric "
                "(1/1.25 = 0.8). A LABEL only."),
            "rotation_plausibility": (
                "plausible | degraded_roster_cardinality | degraded_extreme_scaling | "
                "degraded_both"),
        },
        "selection_discipline": (
            "the 12-player threshold is an external league roster rule, not a tuned parameter. The "
            "[0.8, 1.25] band is declared here, before any downstream number is viewed. NEITHER "
            "changes any allocated minute or possession -- both are labels attached to rows that "
            "are computed identically with or without them."),
    },
    "reporting_rule": (
        "degraded and unresolved rows are reported SEPARATELY and must never be allowed to pass "
        "aggregate checks by being averaged in with normal rows"),
    "expected_consequence_disclosed": (
        "Tier A is expected to trip exceeds_standard_active_roster on some team-games too -- its "
        "maximum allocated count is 17. That is a real property of the candidate universe and is "
        "reported, not suppressed."),
}


RECORDS = [COVERAGE, OFFDEF, S2_POLICY]


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
                  f"{r['kind']:8s}  {r['experiment_id']}")
        return
    n = 0
    with ARM_REGISTRY.open("a", encoding="utf-8") as fh:
        for r in RECORDS:
            if r["experiment_id"] in have:
                print(f"skip (already registered): {r['experiment_id']}")
                continue
            fh.write(json.dumps(r, sort_keys=False) + "\n")
            print(f"appended: {r['kind']:8s} {r['experiment_id']}")
            n += 1
    print(f"\n{n} record(s) appended to {ARM_REGISTRY.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
