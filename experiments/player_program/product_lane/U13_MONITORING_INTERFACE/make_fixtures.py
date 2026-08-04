"""
U13_MONITORING_INTERFACE -- deterministic fixture generator.

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
has been promoted.

Every fixture is synthetic. No fixture contains a real model identifier, a real arm, a real
artifact hash from the program, or any historical performance figure. The model_version strings
are self-describing placeholders and the artifact hashes are sha256 of their own label, so no
reader can mistake them for program bytes.

The eight input domains and the lineup vocabulary are quoted from the repository:
  experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/capture_schema.py:78-173
The unbound fixture reproduces the measured repository fact that ZERO of those eight domains is
bound to a live source:
  experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/SOURCE_BINDING.json:442-444

Run:  python make_fixtures.py
"""

from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")

CLOCK = "2026-08-04T22:40:00Z"
SNAPSHOT_SCHEMA = "player_program/monitor_snapshot/1"

# The eight D11 domains, in the order capture_schema.py declares them.
DOMAINS = [
    "injury_designation", "lineup", "starter", "minute_restriction",
    "transaction", "coaching_change", "odds", "news",
]

GAME = "2026-08-05__AAA_at_BBB"
TEAM_H, TEAM_A = "BBB", "AAA"


def fake_hash(label: str) -> str:
    return hashlib.sha256(("U13_FIXTURE::" + label).encode("utf-8")).hexdigest()


def binding(label="v0"):
    return {
        "model_version": f"fixture-model-{label}",
        "binding_source": "fixture; no model has been promoted",
        "artifact_sha256": {
            "feature_bundle": fake_hash(f"feature_bundle::{label}"),
            "estimator_bundle": fake_hash(f"estimator_bundle::{label}"),
        },
    }


def inp(input_id, domain, observed, max_age=1800, required=True, **kw):
    row = {
        "input_id": input_id,
        "domain": domain,
        "bound": True,
        "observed_at_utc": observed,
        "max_age_seconds": max_age,
        "required_for_serving": required,
    }
    row.update(kw)
    return row


def lineup(team, status="ANNOUNCED", observed="2026-08-04T22:30:00Z", five=None, **kw):
    row = {
        "game_key": GAME,
        "team": team,
        "bound": True,
        "lineup_status": status,
        "announced_five": five if five is not None else [f"{team}_P{i}" for i in range(1, 6)],
        "observed_at_utc": observed,
        "max_age_seconds": 7200,
    }
    row.update(kw)
    return row


def job(job_id, outcome="SUCCEEDED", due="2026-08-04T22:20:00Z", cutoff="2026-08-04T22:30:00Z",
        completed="2026-08-04T22:25:00Z", blocking=True, detail=None):
    return {
        "job_id": job_id,
        "last_outcome": outcome,
        "due_at_utc": due,
        "cutoff_utc": cutoff,
        "completed_at_utc": completed,
        "blocking": blocking,
        "detail": detail,
    }


def projection(team, value, metric="projected_exposure", unit="possessions",
               inputs=("odds_feed", "injury_feed"), jobs=("nightly_feature_build",),
               lineups=True, uncertainty=None):
    return {
        "game_key": GAME,
        "team": team,
        "metric": metric,
        "unit": unit,
        "value": value,
        "uncertainty": uncertainty,
        "depends_on_inputs": list(inputs),
        "depends_on_jobs": list(jobs),
        "depends_on_lineups": [[GAME, team]] if lineups else [],
    }


def base_inputs():
    return [
        inp("injury_feed", "injury_designation", "2026-08-04T22:35:00Z"),
        inp("lineup_feed", "lineup", "2026-08-04T22:30:00Z"),
        inp("odds_feed", "odds", "2026-08-04T22:38:00Z", max_age=600),
        inp("news_feed", "news", "2026-08-04T22:10:00Z", max_age=3600, required=False),
    ]


def snapshot(snapshot_id, generated="2026-08-04T22:39:00Z", **kw):
    snap = {
        "schema": SNAPSHOT_SCHEMA,
        "snapshot_id": snapshot_id,
        "generated_at_utc": generated,
        "snapshot_max_age_seconds": 900,
        "model_binding": binding(),
        "inputs": base_inputs(),
        "lineups": [lineup(TEAM_H), lineup(TEAM_A)],
        "jobs": [job("nightly_feature_build"), job("odds_poll", cutoff="2026-08-04T22:40:00Z",
                                                   completed="2026-08-04T22:38:00Z")],
        "rollback": {
            "state": "NONE",
            "active_model_version": "fixture-model-v0",
            "previous_model_version": None,
            "changed_at_utc": None,
            "reason": None,
            "initiated_by": None,
        },
        "expected_projections": [
            {"game_key": GAME, "team": TEAM_H, "metric": "projected_exposure"},
            {"game_key": GAME, "team": TEAM_A, "metric": "projected_exposure"},
        ],
        "projections": [projection(TEAM_H, 81.25), projection(TEAM_A, 79.5)],
    }
    snap.update(kw)
    return snap


def fixture(fixture_id, purpose, snap, expect, clock=CLOCK):
    return {
        "schema": "player_program/monitor_fixture/1",
        "fixture_id": fixture_id,
        "purpose": purpose,
        "epistemic_status": ("PRODUCT SCAFFOLD built against fixtures. Carries no scientific "
                             "claim and must not imply a model has been promoted."),
        "synthetic": True,
        "evaluated_at_utc": clock,
        "expect": expect,
        "snapshot": snap,
    }


def build():
    out = {}

    # 1. healthy ------------------------------------------------------------------------------
    out["healthy"] = fixture(
        "healthy",
        "every dependency healthy; both projections render as numbers. The control case: without "
        "it, a monitor that alerts on everything would trivially satisfy 'no silent failure'.",
        snapshot("snap-healthy"),
        {"serving": "SERVING", "n_projections_shown": 2, "must_alert_codes": []})

    # 2. stale input --------------------------------------------------------------------------
    stale = snapshot("snap-stale-input")
    stale["inputs"] = [
        inp("injury_feed", "injury_designation", "2026-08-04T22:35:00Z"),
        inp("lineup_feed", "lineup", "2026-08-04T22:30:00Z"),
        # 42 minutes old against a 600-second limit
        inp("odds_feed", "odds", "2026-08-04T21:58:00Z", max_age=600),
        inp("news_feed", "news", "2026-08-04T22:10:00Z", max_age=3600, required=False),
    ]
    out["stale_input"] = fixture(
        "stale_input",
        "one required input is past its declared maximum age. The projections that depend on it "
        "must not render, and the staleness must be visible as its own row and its own alert.",
        stale,
        {"serving": "SUPPRESSED", "n_projections_shown": 0,
         "must_alert_codes": ["INPUT_STALE"]})

    # 3. missing lineup -----------------------------------------------------------------------
    missing = snapshot("snap-missing-lineup")
    missing["lineups"] = [
        lineup(TEAM_H),
        {"game_key": GAME, "team": TEAM_A, "bound": True, "lineup_status": None,
         "announced_five": None, "observed_at_utc": None, "max_age_seconds": 7200},
    ]
    out["missing_lineup"] = fixture(
        "missing_lineup",
        "one team has no lineup observation. Its projection must be withheld; the other team's "
        "must still render, so a per-entity gap does not blind the whole slate and does not "
        "silently pass either.",
        missing,
        {"serving": "DEGRADED", "n_projections_shown": 1,
         "must_alert_codes": ["LINEUP_MISSING"]})

    # 4. failed jobs --------------------------------------------------------------------------
    failed = snapshot("snap-failed-job")
    failed["jobs"] = [
        job("nightly_feature_build", outcome="FAILED", completed=None,
            detail="adapter raised; no output written"),
        job("lineup_poll", outcome=None, due="2026-08-04T22:00:00Z",
            cutoff="2026-08-04T22:20:00Z", completed=None, blocking=False,
            detail="due and no run exists"),
        # the D-d shape: the job claims success but finished after its own cutoff
        job("odds_poll", outcome="SUCCEEDED", due="2026-08-04T22:20:00Z",
            cutoff="2026-08-04T22:34:00Z", completed="2026-08-04T22:45:08Z", blocking=False),
    ]
    out["failed_job"] = fixture(
        "failed_job",
        "three distinct job pathologies in one frame: an outright failure, a job that was due and "
        "never ran, and a job that reports SUCCEEDED but completed after its own cutoff. The "
        "third is the failure mode the repository documents as D-d and D-a: a late record read as "
        "a healthy record. The evaluator downgrades it to LATE on the timestamps alone.",
        failed,
        {"serving": "SUPPRESSED", "n_projections_shown": 0,
         "must_alert_codes": ["JOB_FAILED", "JOB_DID_NOT_RUN", "JOB_LATE"]})

    # 5. rollback active ----------------------------------------------------------------------
    rolled = snapshot("snap-rollback-active")
    rolled["model_binding"] = binding("v0")
    rolled["rollback"] = {
        "state": "ACTIVE",
        "active_model_version": "fixture-model-v0",
        "previous_model_version": "fixture-model-v1",
        "changed_at_utc": "2026-08-04T21:05:00Z",
        "reason": "fixture: operator rolled serving back one version",
        "initiated_by": "fixture-operator",
    }
    out["rollback_active"] = fixture(
        "rollback_active",
        "serving has been rolled back to an earlier version. The numbers are real and still "
        "render, but the rollback banner is mandatory: an operator must never read a projection "
        "without knowing which version produced it.",
        rolled,
        {"serving": "SERVING", "n_projections_shown": 2,
         "must_alert_codes": ["ROLLBACK_ACTIVE"]})

    # 6. rollback in flight -------------------------------------------------------------------
    pending = snapshot("snap-rollback-pending")
    pending["rollback"] = {
        "state": "PENDING",
        "active_model_version": "fixture-model-v1",
        "previous_model_version": "fixture-model-v0",
        "changed_at_utc": "2026-08-04T22:39:30Z",
        "reason": "fixture: rollback in flight",
        "initiated_by": "fixture-operator",
    }
    out["rollback_pending"] = fixture(
        "rollback_pending",
        "a rollback is in flight, so which version is serving is not established. Everything is "
        "withheld: an indeterminate binding is not a servable binding.",
        pending,
        {"serving": "SUPPRESSED", "n_projections_shown": 0,
         "must_alert_codes": ["ROLLBACK_PENDING"]})

    # 7. the silent-failure attempt -----------------------------------------------------------
    silent = {
        "schema": SNAPSHOT_SCHEMA,
        "snapshot_id": "snap-silent-failure-attempt",
        "generated_at_utc": None,
        "model_binding": {},
        "inputs": [],
        "lineups": [],
        "jobs": [],
        "rollback": {},
        "projections": [projection(TEAM_H, 81.25, inputs=(), jobs=(), lineups=False),
                        projection(TEAM_A, 79.5, inputs=(), jobs=(), lineups=False)],
    }
    out["silent_failure_attempt"] = fixture(
        "silent_failure_attempt",
        "the adversarial case this node exists for: a snapshot carrying two entirely plausible "
        "projections and NO evidence of any kind -- no clock on the snapshot, no model binding, "
        "no inputs, no lineups, no jobs, no rollback state, and no declared dependencies. A "
        "monitor that shows these two numbers is the exact failure the lane exists to prevent.",
        silent,
        {"serving": "SUPPRESSED", "n_projections_shown": 0,
         "must_alert_codes": ["MODEL_VERSION_ABSENT", "ARTIFACT_HASHES_ABSENT", "SNAPSHOT_STALE",
                              "ROLLBACK_UNKNOWN", "EXPECTED_COVERAGE_UNDECLARED"]})

    # 7b. a projection that vanished ----------------------------------------------------------
    vanished = snapshot("snap-vanished-projection")
    vanished["projections"] = [projection(TEAM_H, 81.25)]
    out["vanished_projection"] = fixture(
        "vanished_projection",
        "the slate declares two projections and the snapshot carries one. Without a declared "
        "expected slate the second would simply not appear -- a shorter table reads as a complete "
        "table. The monitor renders the hole as its own suppressed row and a CRITICAL alert.",
        vanished,
        {"serving": "DEGRADED", "n_projections_shown": 1,
         "must_alert_codes": ["PROJECTION_ROW_ABSENT"]})

    # 8. the repository's actual live-input state ---------------------------------------------
    unbound_inputs = [
        {"input_id": f"{d}_feed", "domain": d, "bound": False, "observed_at_utc": None,
         "max_age_seconds": None, "required_for_serving": d in ("lineup", "injury_designation"),
         "source_path": ("experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/"
                         "SOURCE_BINDING.json")}
        for d in DOMAINS
    ]
    unbound = snapshot("snap-unbound-reality")
    unbound["inputs"] = unbound_inputs
    unbound["lineups"] = [
        {"game_key": GAME, "team": t, "bound": False, "lineup_status": None,
         "announced_five": None, "observed_at_utc": None, "max_age_seconds": None}
        for t in (TEAM_H, TEAM_A)
    ]
    unbound["projections"] = [projection(TEAM_H, 81.25), projection(TEAM_A, 79.5)]
    out["unbound_reality"] = fixture(
        "unbound_reality",
        "the state the repository is measurably in today: none of the eight D11 capture domains "
        "is bound to a live source (SOURCE_BINDING.json:443, n_bound=0 of 8). Rendered honestly, "
        "the dashboard is a wall of UNBOUND and shows no projection at all. This fixture is the "
        "answer to 'what would this interface show if it were pointed at the program right now'.",
        unbound,
        {"serving": "SUPPRESSED", "n_projections_shown": 0,
         "must_alert_codes": ["INPUT_UNBOUND", "LINEUP_UNBOUND"]})

    return out


def main():
    os.makedirs(FIXTURES, exist_ok=True)
    built = build()
    for name, payload in sorted(built.items()):
        path = os.path.join(FIXTURES, f"{name}.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")
        print(f"wrote {path}")
    print(f"{len(built)} fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
