#!/usr/bin/env python3
"""u10_adapter.py — OPTIONAL, UNBLESSED adapter from a U10 prediction response to the
U11 view payload.

Status, stated plainly: at the time this node ran, `U10_PREDICTION_API_SCHEMA` was
`RUNNING` (`experiments/player_program/orchestration/GRAPH_STATE.json:245`), i.e. in
flight and not verified. Its files appeared in the working tree mid-node. This adapter is
therefore written against an UNSTABLE, UNACCEPTED shape and is NOT a dependency of
`ui_shell.py`, of the fixtures, or of the node's acceptance criteria. It is a pure dict
transform: no I/O, no policy.

The adapter deliberately makes NO suppression decisions. It moves identity, freshness
facts and dependency edges across; the shell re-derives every suppression from those
facts. A U10 response that claims a projection is servable will still be suppressed by
the shell if the freshness arithmetic says otherwise.
"""
from __future__ import annotations

from typing import Any

U10_SCHEMA_PREFIX = "prediction_response"


def looks_like_u10(resp: Any) -> bool:
    return (
        isinstance(resp, dict)
        and isinstance(resp.get("model"), dict)
        and isinstance(resp.get("inputs"), list)
        and isinstance(resp.get("projections"), list)
        and isinstance(resp.get("game"), dict)
    )


def _input_record(i: dict) -> dict:
    job = str(i.get("job_status") or "").lower()
    fresh = str(i.get("freshness") or "").lower()
    if job in {"failed", "error"}:
        status = "failed"
    elif fresh in {"missing", "absent"} or i.get("observed_at_utc") in (None, ""):
        status = "missing"
    else:
        status = "ok"
    return {
        "input_id": i.get("input_id"),
        "label": i.get("input_id"),
        "status": status,
        "captured_at": i.get("observed_at_utc") or i.get("as_of_utc"),
        "max_age_seconds": i.get("max_age_seconds"),
        "detail": f"source={i.get('source')} job_status={i.get('job_status')} "
                  f"freshness={i.get('freshness')}",
    }


def _row(p: dict) -> dict:
    unc = p.get("uncertainty") or {}
    mkt = p.get("market") or {}
    return {
        "entity_id": p.get("subject_id"),
        "entity_label": f"{p.get('subject_id')} ({p.get('target')})",
        "required_inputs": list(p.get("depends_on") or []),
        "row_blockers": [str(r) for r in (p.get("withheld_reasons") or [])],
        "projection": {"value": p.get("point"), "units": p.get("unit")},
        "uncertainty": {"lo": unc.get("p10"), "hi": unc.get("p90"), "level": "p10-p90"},
        "market": ({"line": mkt.get("line"), "source": mkt.get("book")}
                   if mkt.get("available") else {"line": None, "source": None}),
        "components": [{"name": c.get("name"), "contribution": c.get("contribution")}
                       for c in (p.get("components") or [])],
    }


def adapt(resp: dict) -> dict:
    """U10 response dict -> u11_view_payload/1 dict. Pure; raises on a non-U10 shape."""
    if not looks_like_u10(resp):
        raise ValueError("not a U10-shaped prediction response")
    model = resp.get("model") or {}
    game = resp.get("game") or {}
    return {
        "schema": "u11_view_payload/1",
        "title": f"Projection view — adapted from {resp.get('schema')}",
        "as_of": resp.get("generated_at_utc"),
        "model": {
            "version": model.get("model_version"),
            "artifact_sha256": model.get("artifact_sha256") or {},
            "promotion_status": model.get("promotion_status"),
        },
        "inputs": [_input_record(i) for i in resp.get("inputs") or []],
        "games": [{
            "game_id": game.get("game_id"),
            "label": f"{game.get('home_team_id')} vs {game.get('away_team_id')}",
            "tipoff": game.get("scheduled_tip_utc"),
            "required_inputs": [],
            "rows": [_row(p) for p in resp.get("projections") or []],
            "notes": [str(w.get("message")) for w in (resp.get("warnings") or [])
                      if isinstance(w, dict)],
        }],
        "audit": {
            "payload_id": resp.get("response_id"),
            "generated_by": "u10_adapter.adapt (unblessed; U10 was RUNNING when written)",
            "source": "ADAPTED_FIXTURE",
            "notes": "Adapter carries facts only. Every suppression is re-derived by ui_shell.",
        },
    }
