"""Build the FIXTURE prediction history for U12_PREDICTION_HISTORY.

EPISTEMIC STATUS: PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must
not imply a model has been promoted.

Everything here is SYNTHETIC. The model versions are placeholder strings, the artifact hashes are
digests of fixture text, the players and games are invented. No estimator was run, no repository
artifact was read to produce a number, and nothing in this file names a possession challenger.

Deterministic: fixed timestamps, fixed inputs, no randomness, no clock read. Re-running it
rebuilds a byte-identical ledger, which is what makes the ledger's own digests citable.

    python experiments/player_program/product_lane/U12_PREDICTION_HISTORY/build_fixture_history.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from prediction_history import (  # noqa: E402
    HEAD_NAME, LEDGER_NAME, HistoryError, SEVERITY_ADVISORY, SEVERITY_BLOCKING,
    append_prediction, canonical_bytes, key_uid, make_record, read_records, render_record,
    render_lineage, render_model_version_view, sha256_hex, verify_ledger, view_current,
)

FIXTURES = HERE / "fixtures"
LEDGER = FIXTURES / LEDGER_NAME

T0 = datetime(2026, 8, 1, 18, 0, 0, tzinfo=timezone.utc)


def h(tag: str) -> str:
    """A stand-in artifact digest. It is the digest of a fixture STRING, not of a model artifact.
    Named so no reader can mistake it for a real artifact hash."""
    return sha256_hex(f"FIXTURE-ARTIFACT::{tag}".encode())


# Two placeholder model versions. Neither names an arm. Both declare, as DATA, that nothing is
# promoted -- the store itself never infers promotion.
MODEL_A = {
    "model_version": "fixture_model/2026.08.01a",
    "model_family": "FIXTURE",
    "promotion_status": "not_promoted",
    "artifact_sha256": {
        "estimator_weights": h("weights-a"),
        "feature_spec": h("features-a"),
    },
    "code_provenance": {"producer": "FIXTURE (no estimator was executed)"},
}
MODEL_B = {
    "model_version": "fixture_model/2026.08.01b",
    "model_family": "FIXTURE",
    "promotion_status": "not_promoted",
    "artifact_sha256": {
        "estimator_weights": h("weights-b"),
        "feature_spec": h("features-a"),
    },
    "code_provenance": {"producer": "FIXTURE (no estimator was executed)"},
}


def fresh_inputs(at: datetime, *, lineup: bool = True, feed_age_s: int = 900) -> list[dict]:
    return [
        {"input_id": "player_history", "artifact_sha256": h("player-history"),
         "observed_at": (at - timedelta(seconds=3600)).isoformat().replace("+00:00", "Z"),
         "max_age_seconds": 86400, "required": True},
        {"input_id": "availability_report", "artifact_sha256": h("availability"),
         "observed_at": (at - timedelta(seconds=feed_age_s)).isoformat().replace("+00:00", "Z"),
         "max_age_seconds": 3600, "required": True},
        {"input_id": "projected_lineup",
         "artifact_sha256": h("lineup") if lineup else None,
         "observed_at": ((at - timedelta(seconds=600)).isoformat().replace("+00:00", "Z")
                         if lineup else None),
         "max_age_seconds": 7200, "required": True},
    ]


def key(game: str, team: str, player: str, target: str, cutoff: datetime) -> dict:
    return {"game_id": game, "team_id": team, "player_id": player, "target": target,
            "forecast_cutoff": cutoff.isoformat().replace("+00:00", "Z")}


def build() -> dict:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    if LEDGER.exists():
        LEDGER.unlink()          # rebuilding the FIXTURE from scratch; see note in REPORT.md
    head_sidecar = FIXTURES / HEAD_NAME
    if head_sidecar.exists():
        head_sidecar.unlink()

    cutoff = datetime(2026, 8, 2, 23, 0, 0, tzinfo=timezone.utc)
    written = []

    # 1. an ordinary projected record ------------------------------------------------
    k1 = key("FIXG0001", "FIXTEAM_A", "FIXPLAYER_01", "fixture_target_units", cutoff)
    r1 = append_prediction(LEDGER, make_record(
        k1, MODEL_A, fresh_inputs(T0), 31.5, interval=[26.0, 37.0], units="units",
        appended_at=T0))
    written.append(r1)

    # 2. the SAME forecast, corrected. A new record, never an edit. -------------------
    t2 = T0 + timedelta(hours=2)
    r2 = append_prediction(LEDGER, make_record(
        k1, MODEL_A, fresh_inputs(t2), 28.0, interval=[23.0, 33.0], units="units",
        appended_at=t2, revision_index=1, revises_record_id=r1["record_id"],
        revision_reason="availability report re-captured; the earlier record stands unchanged"))
    written.append(r2)

    # 3. same forecast again, under a DIFFERENT model version -------------------------
    t3 = T0 + timedelta(hours=4)
    r3 = append_prediction(LEDGER, make_record(
        k1, MODEL_B, fresh_inputs(t3), 29.25, interval=[24.0, 34.5], units="units",
        appended_at=t3, revision_index=2, revises_record_id=r2["record_id"],
        revision_reason="re-run under a second fixture model version"))
    written.append(r3)

    # 4. a MISSING lineup -- must render as a warning, never as a number ---------------
    k2 = key("FIXG0001", "FIXTEAM_A", "FIXPLAYER_02", "fixture_target_units", cutoff)
    r4 = append_prediction(LEDGER, make_record(
        k2, MODEL_A, fresh_inputs(T0, lineup=False), 22.0, units="units", appended_at=T0))
    written.append(r4)
    assert r4["status"] == "WITHHELD" and r4["projection"]["point"] is None

    # 5. a STALE feed -- the caller passed a number; the store refused to publish it ----
    k3 = key("FIXG0002", "FIXTEAM_B", "FIXPLAYER_03", "fixture_target_units", cutoff)
    r5 = append_prediction(LEDGER, make_record(
        k3, MODEL_A, fresh_inputs(T0, feed_age_s=7200), 17.75, units="units", appended_at=T0))
    written.append(r5)
    assert r5["status"] == "WITHHELD" and r5["projection"]["point"] is None

    # 6. that same forecast recovering once the feed refreshes -------------------------
    t6 = T0 + timedelta(hours=1)
    r6 = append_prediction(LEDGER, make_record(
        k3, MODEL_A, fresh_inputs(t6), 17.75, interval=[13.0, 22.5], units="units",
        appended_at=t6, revision_index=1, revises_record_id=r5["record_id"],
        revision_reason="feed refreshed; the WITHHELD record above is retained"))
    written.append(r6)

    # 7. a failed upstream job, declared explicitly by the caller ----------------------
    k4 = key("FIXG0002", "FIXTEAM_B", "FIXPLAYER_04", "fixture_target_units", cutoff)
    r7 = append_prediction(LEDGER, make_record(
        k4, MODEL_B, fresh_inputs(T0), None, units="units", appended_at=T0,
        extra_warnings=[{"code": "UPSTREAM_JOB_FAILED", "severity": SEVERITY_BLOCKING,
                         "detail": "fixture feature build exited non-zero; no projection exists"}]))
    written.append(r7)

    # 8. an advisory warning, which does NOT suppress the number ------------------------
    k5 = key("FIXG0002", "FIXTEAM_B", "FIXPLAYER_05", "fixture_target_units", cutoff)
    r8 = append_prediction(LEDGER, make_record(
        k5, MODEL_B, fresh_inputs(T0), 9.0, interval=[2.0, 16.0], units="units", appended_at=T0,
        extra_warnings=[{"code": "WIDE_INTERVAL", "severity": SEVERITY_ADVISORY,
                         "detail": "fixture interval is wide relative to the point"}]))
    written.append(r8)

    report = verify_ledger(LEDGER)
    records = read_records(LEDGER)
    summary = {
        "schema": "u12_fixture_history_summary/1",
        "note": ("SYNTHETIC fixture. No estimator was executed and no repository model artifact "
                 "was read. Model versions and artifact hashes are placeholders."),
        "n_records": len(records),
        "n_keys": len({r["key_uid"] for r in records}),
        "n_current": len(view_current(records)),
        "n_ok": sum(1 for r in records if r["status"] == "OK"),
        "n_withheld": sum(1 for r in records if r["status"] == "WITHHELD"),
        "n_revisions_beyond_first": sum(1 for r in records if r["revision_index"] > 0),
        "model_versions": sorted({r["model"]["model_version"] for r in records}),
        "promotion_status_values": sorted({r["model"]["promotion_status"] for r in records}),
        "withheld_codes": sorted({w["code"] for r in records for w in r["warnings"]
                                  if w["severity"] == "blocking"}),
        "verify": report,
        "ledger_sha256": sha256_hex(LEDGER.read_bytes()),
    }
    (FIXTURES / "FIXTURE_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    k1_uid = key_uid(k1)
    (HERE / "VIEW_SAMPLE.txt").write_text(
        "U12_PREDICTION_HISTORY -- rendered views over the FIXTURE ledger\n"
        "PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not\n"
        "imply a model has been promoted.\n\n"
        "== lineage of one forecast (a revision is a new record) ==\n\n"
        + render_lineage(records, k1_uid) + "\n"
        "== every current record, one line each ==\n\n"
        + "\n".join(
            f"  {r['prediction_key']['player_id']:<14} rev {r['revision_index']}  "
            f"{render_record(r)['display']}"
            for r in view_current(records).values()) + "\n\n"
        "== model-version view ==\n\n" + render_model_version_view(records),
        encoding="utf-8")
    return summary


if __name__ == "__main__":
    s = build()
    print(json.dumps({k: v for k, v in s.items() if k != "verify"}, indent=2, sort_keys=True))
    print("verify ok:", s["verify"]["ok"], "findings:", s["verify"]["findings"])
    raise SystemExit(0 if s["verify"]["ok"] else 1)
