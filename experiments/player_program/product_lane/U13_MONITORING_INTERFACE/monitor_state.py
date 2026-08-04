"""
U13_MONITORING_INTERFACE -- fail-closed evaluation of a monitoring snapshot.

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
has been promoted.

evaluate(snapshot, evaluated_at_utc) is a pure function. It reads a snapshot (a dict, typically
loaded from a fixture JSON) and returns an evaluation containing:

  * one row per input, per lineup, per job, plus a rollback row -- so stale inputs, missing
    lineups, failed jobs and rollback state are each INDIVIDUALLY visible, never merged into a
    single health light;
  * one display cell per projection, which is kind=NUMBER only when its whole dependency chain is
    healthy and the snapshot's model binding is complete, and kind=ALERT otherwise;
  * a flat alert list.

The function does not raise. Anything it cannot understand becomes a CRITICAL alert and suppresses
display. A monitoring interface that crashes on bad input is a monitoring interface that shows
nothing while something is wrong.

Model-agnosticism: this module never names a model, arm, estimator or challenger. model_version
and artifact_sha256 arrive as opaque snapshot data and are echoed, never interpreted.
"""

from __future__ import annotations

from datetime import datetime, timezone

from monitor_schema import (
    ALERT_CELL_TEXT,
    DISPLAY_ALERT,
    DISPLAY_NUMBER,
    EVALUATION_SCHEMA,
    INPUT_ERROR,
    INPUT_MISSING,
    INPUT_OK,
    INPUT_STALE,
    INPUT_STATUSES,
    INPUT_UNBOUND,
    INPUT_UNKNOWN,
    JOB_DID_NOT_RUN,
    JOB_FAILED,
    JOB_LATE,
    JOB_RUNNING,
    JOB_STATUSES,
    JOB_SUCCEEDED,
    JOB_UNKNOWN,
    LINEUP_MISSING,
    LINEUP_OBSERVED,
    LINEUP_STALE,
    LINEUP_STATUSES,
    LINEUP_UNBOUND,
    LINEUP_UNKNOWN,
    ROLLBACK_ACTIVE,
    ROLLBACK_FAILED,
    ROLLBACK_NONE,
    ROLLBACK_PENDING,
    ROLLBACK_STATES,
    ROLLBACK_UNKNOWN,
    SEVERITY_ORDER,
    SNAPSHOT_SCHEMA,
    SUPPRESSING_INPUT,
    SUPPRESSING_JOB,
    SUPPRESSING_LINEUP,
    SUPPRESSING_ROLLBACK,
    coerce_status,
    describe,
    severity_of,
)

# A snapshot older than this is itself treated as a failure: a dashboard whose feed died must not
# keep showing the last good frame.
DEFAULT_SNAPSHOT_MAX_AGE_SECONDS = 900


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------

def _parse_utc(value):
    """Return an aware datetime, or None. Never raises."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _age_seconds(observed, now):
    if observed is None or now is None:
        return None
    return (now - observed).total_seconds()


def _alert(code, subject, detail):
    return {
        "code": code,
        "severity": severity_of(code),
        "subject": subject,
        "detail": detail or describe(code),
    }


def _dict(value):
    return value if isinstance(value, dict) else {}


def _list(value):
    return value if isinstance(value, list) else []


def _alert_cell(codes):
    return {"kind": DISPLAY_ALERT, "text": ALERT_CELL_TEXT, "codes": sorted(set(codes))}


def _number_cell(value, unit=None):
    return {"kind": DISPLAY_NUMBER, "text": f"{value:.4g}", "value": float(value),
            "unit": unit, "codes": []}


# ---------------------------------------------------------------------------------------------
# per-family evaluation
# ---------------------------------------------------------------------------------------------

def _eval_input(row, now):
    row = _dict(row)
    input_id = row.get("input_id") or "<unnamed input>"
    domain = row.get("domain")
    required = bool(row.get("required_for_serving", True))
    bound = row.get("bound")
    observed_raw = row.get("observed_at_utc")
    observed = _parse_utc(observed_raw)
    max_age = row.get("max_age_seconds")
    age = _age_seconds(observed, now)

    declared = row.get("status")
    if declared is not None:
        status = coerce_status(declared, INPUT_STATUSES, INPUT_UNKNOWN)
    elif row.get("error"):
        status = INPUT_ERROR
    elif bound is False:
        status = INPUT_UNBOUND
    elif bound is not True:
        status = INPUT_UNKNOWN          # bound unstated -> not assumed bound
    elif observed is None:
        status = INPUT_MISSING
    elif now is None:
        status = INPUT_UNKNOWN          # cannot age it without a clock
    elif not isinstance(max_age, (int, float)) or isinstance(max_age, bool) or max_age <= 0:
        status = INPUT_UNKNOWN          # freshness undefined -> not assumed fresh
    elif age is None or age > float(max_age):
        status = INPUT_STALE
    else:
        status = INPUT_OK

    # An input the snapshot declares OK but whose own numbers contradict that is still stale.
    if status == INPUT_OK and age is not None and isinstance(max_age, (int, float)) \
            and not isinstance(max_age, bool) and max_age > 0 and age > float(max_age):
        status = INPUT_STALE

    return {
        "input_id": input_id,
        "domain": domain,
        "status": status,
        "bound": bound,
        "observed_at_utc": observed_raw,
        "age_seconds": None if age is None else round(age, 3),
        "max_age_seconds": max_age if isinstance(max_age, (int, float))
        and not isinstance(max_age, bool) else None,
        "required_for_serving": required,
        "error": row.get("error"),
        "source_path": row.get("source_path"),
    }


def _eval_lineup(row, now):
    row = _dict(row)
    game_key = row.get("game_key") or "<unkeyed game>"
    team = row.get("team") or "<unnamed team>"
    observed_raw = row.get("observed_at_utc")
    observed = _parse_utc(observed_raw)
    max_age = row.get("max_age_seconds")
    age = _age_seconds(observed, now)
    bound = row.get("bound")

    declared = row.get("lineup_status")
    if bound is False:
        status = LINEUP_UNBOUND
    elif declared is None:
        status = LINEUP_MISSING
    else:
        status = coerce_status(declared, LINEUP_STATUSES, LINEUP_UNKNOWN)

    if status in LINEUP_OBSERVED:
        five = row.get("announced_five")
        if not isinstance(five, list) or len(five) != 5 or any(
                not isinstance(p, str) or not p.strip() for p in five):
            # An "announced" five that is not five named players is not a lineup.
            status = LINEUP_MISSING
        elif observed is None or now is None:
            status = LINEUP_UNKNOWN
        elif isinstance(max_age, (int, float)) and not isinstance(max_age, bool) and max_age > 0 \
                and age is not None and age > float(max_age):
            status = LINEUP_STALE

    return {
        "game_key": game_key,
        "team": team,
        "status": status,
        "lineup_status": declared,
        "n_players": len(row["announced_five"]) if isinstance(row.get("announced_five"), list)
        else None,
        "observed_at_utc": observed_raw,
        "age_seconds": None if age is None else round(age, 3),
        "max_age_seconds": max_age if isinstance(max_age, (int, float))
        and not isinstance(max_age, bool) else None,
    }


def _eval_job(row, now):
    row = _dict(row)
    job_id = row.get("job_id") or "<unnamed job>"
    blocking = bool(row.get("blocking", True))
    due = _parse_utc(row.get("due_at_utc"))
    cutoff = _parse_utc(row.get("cutoff_utc"))
    completed_raw = row.get("completed_at_utc")
    completed = _parse_utc(completed_raw)

    declared = row.get("last_outcome")
    status = coerce_status(declared, JOB_STATUSES, JOB_UNKNOWN) if declared is not None else None

    if status is None:
        if completed is not None:
            status = JOB_SUCCEEDED
        elif due is not None and now is not None and now > due:
            status = JOB_DID_NOT_RUN
        else:
            status = JOB_UNKNOWN

    # A job that claims success but finished after its own cutoff is LATE, not SUCCEEDED.
    # This is the D-d / D-a shape: a late record must not read as a healthy record.
    latency_minutes = None
    if completed is not None and cutoff is not None:
        latency_minutes = round((completed - cutoff).total_seconds() / 60.0, 3)
    if status == JOB_SUCCEEDED:
        if completed is None:
            status = JOB_UNKNOWN
        elif latency_minutes is not None and latency_minutes > 0:
            status = JOB_LATE
    if status == JOB_RUNNING and cutoff is not None and now is not None and now <= cutoff:
        # still in flight but not yet past its cutoff: not an alert, but not servable either
        pass

    return {
        "job_id": job_id,
        "status": status,
        "declared_outcome": declared,
        "blocking": blocking,
        "due_at_utc": row.get("due_at_utc"),
        "cutoff_utc": row.get("cutoff_utc"),
        "completed_at_utc": completed_raw,
        "latency_minutes_past_cutoff": latency_minutes,
        "detail": row.get("detail"),
    }


def _eval_rollback(block):
    block = _dict(block)
    declared = block.get("state")
    state = coerce_status(declared, ROLLBACK_STATES, ROLLBACK_UNKNOWN) if declared is not None \
        else ROLLBACK_UNKNOWN
    active = block.get("active_model_version")
    previous = block.get("previous_model_version")
    if state == ROLLBACK_ACTIVE and (not isinstance(active, str) or not active.strip()):
        state = ROLLBACK_UNKNOWN
    return {
        "state": state,
        "declared_state": declared,
        "active_model_version": active,
        "previous_model_version": previous,
        "changed_at_utc": block.get("changed_at_utc"),
        "reason": block.get("reason"),
        "initiated_by": block.get("initiated_by"),
    }


def _eval_binding(block):
    block = _dict(block)
    version = block.get("model_version")
    hashes = block.get("artifact_sha256")
    alerts = []
    if not isinstance(version, str) or not version.strip():
        alerts.append(_alert("MODEL_VERSION_ABSENT", "model_binding", None))
    if not isinstance(hashes, dict) or not hashes:
        alerts.append(_alert("ARTIFACT_HASHES_ABSENT", "model_binding", None))
        hashes = {}
    else:
        for name, value in sorted(hashes.items()):
            if not isinstance(value, str) or not value.strip():
                alerts.append(_alert("ARTIFACT_HASH_NULL", f"model_binding.{name}",
                                     f"artifact hash for {name!r} is null or empty"))
    return {
        "model_version": version if isinstance(version, str) else None,
        "artifact_sha256": hashes,
        "binding_source": block.get("binding_source"),
        "n_artifacts": len(hashes),
    }, alerts


# ---------------------------------------------------------------------------------------------
# evaluate
# ---------------------------------------------------------------------------------------------

def evaluate(snapshot, evaluated_at_utc=None, snapshot_max_age_seconds=None):
    alerts = []
    now = _parse_utc(evaluated_at_utc)
    if now is None:
        alerts.append(_alert("CLOCK_UNKNOWN", "evaluation",
                             f"evaluated_at_utc={evaluated_at_utc!r} is absent or unparseable"))

    if snapshot is None:
        alerts.append(_alert("SNAPSHOT_ABSENT", "snapshot",
                             "no snapshot was supplied; nothing is known about the system"))
        snapshot = {}
    elif not isinstance(snapshot, dict):
        alerts.append(_alert("SNAPSHOT_MALFORMED", "snapshot",
                             f"snapshot is {type(snapshot).__name__}, not an object"))
        snapshot = {}
    elif snapshot.get("schema") != SNAPSHOT_SCHEMA:
        alerts.append(_alert("SNAPSHOT_MALFORMED", "snapshot",
                             f"schema is {snapshot.get('schema')!r}, expected {SNAPSHOT_SCHEMA!r}"))

    max_age = snapshot_max_age_seconds
    if max_age is None:
        max_age = snapshot.get("snapshot_max_age_seconds", DEFAULT_SNAPSHOT_MAX_AGE_SECONDS)
    generated = _parse_utc(snapshot.get("generated_at_utc"))
    snapshot_age = _age_seconds(generated, now)
    if generated is None:
        alerts.append(_alert("SNAPSHOT_STALE", "snapshot",
                             "snapshot carries no parseable generated_at_utc; its age is unknown"))
        snapshot_fresh = False
    elif snapshot_age is None:
        snapshot_fresh = False
    elif isinstance(max_age, (int, float)) and not isinstance(max_age, bool) and max_age > 0 \
            and snapshot_age > float(max_age):
        alerts.append(_alert("SNAPSHOT_STALE", "snapshot",
                             f"snapshot is {snapshot_age:.0f}s old against a {max_age:.0f}s limit"))
        snapshot_fresh = False
    else:
        snapshot_fresh = True

    binding, binding_alerts = _eval_binding(snapshot.get("model_binding"))
    alerts.extend(binding_alerts)
    binding_ok = not binding_alerts

    input_rows = [_eval_input(r, now) for r in _list(snapshot.get("inputs"))]
    lineup_rows = [_eval_lineup(r, now) for r in _list(snapshot.get("lineups"))]
    job_rows = [_eval_job(r, now) for r in _list(snapshot.get("jobs"))]
    rollback_row = _eval_rollback(snapshot.get("rollback"))

    for r in input_rows:
        if r["status"] in SUPPRESSING_INPUT:
            detail = f"input {r['input_id']!r}"
            if r["status"] == INPUT_STALE and r["age_seconds"] is not None:
                detail += (f" last observed {r['observed_at_utc']} "
                           f"({r['age_seconds']:.0f}s old, limit {r['max_age_seconds']}s)")
            elif r["status"] == INPUT_ERROR:
                detail += f" adapter error: {r['error']}"
            elif r["status"] == INPUT_UNBOUND:
                detail += " has no bound live source"
            elif r["status"] == INPUT_MISSING:
                detail += " has never been observed"
            else:
                detail += " state could not be determined"
            alerts.append(_alert(f"INPUT_{r['status']}", r["input_id"], detail))

    for r in lineup_rows:
        if r["status"] in SUPPRESSING_LINEUP:
            alerts.append(_alert(
                f"LINEUP_{r['status']}", f"{r['game_key']}/{r['team']}",
                f"lineup for {r['team']} in {r['game_key']}: {r['status'].lower()}"
                + (f" (declared {r['lineup_status']!r})" if r["lineup_status"] else "")))

    for r in job_rows:
        if r["status"] in SUPPRESSING_JOB:
            detail = f"job {r['job_id']!r} is {r['status']}"
            if r["latency_minutes_past_cutoff"] is not None and r["status"] == JOB_LATE:
                detail += (f": completed {r['completed_at_utc']}, "
                           f"{r['latency_minutes_past_cutoff']:.2f} min after its cutoff "
                           f"{r['cutoff_utc']}")
            elif r["detail"]:
                detail += f": {r['detail']}"
            alerts.append(_alert(f"JOB_{r['status']}", r["job_id"], detail))

    if rollback_row["state"] != ROLLBACK_NONE:
        alerts.append(_alert(
            f"ROLLBACK_{rollback_row['state']}", "rollback",
            f"rollback state {rollback_row['state']}; serving "
            f"{rollback_row['active_model_version']!r}, previous "
            f"{rollback_row['previous_model_version']!r}"
            + (f"; reason: {rollback_row['reason']}" if rollback_row.get("reason") else "")))

    # ---- global gates ------------------------------------------------------------------------
    global_codes = []
    if now is None:
        global_codes.append("CLOCK_UNKNOWN")
    if not snapshot_fresh:
        global_codes.append("SNAPSHOT_STALE")
    if not binding_ok:
        global_codes.extend(a["code"] for a in binding_alerts)
    if rollback_row["state"] in SUPPRESSING_ROLLBACK:
        global_codes.append(f"ROLLBACK_{rollback_row['state']}")

    input_by_id = {r["input_id"]: r for r in input_rows}
    job_by_id = {r["job_id"]: r for r in job_rows}
    lineup_by_key = {(r["game_key"], r["team"]): r for r in lineup_rows}

    # inputs and jobs flagged required_for_serving/blocking gate EVERY projection
    for r in input_rows:
        if r["required_for_serving"] and r["status"] in SUPPRESSING_INPUT:
            global_codes.append(f"INPUT_{r['status']}")
    for r in job_rows:
        if r["blocking"] and r["status"] in SUPPRESSING_JOB:
            global_codes.append(f"JOB_{r['status']}")

    # ---- expected coverage -------------------------------------------------------------------
    # A projection that vanishes from the snapshot is invisible unless the monitor knows what it
    # was supposed to see. The snapshot therefore declares its obligations explicitly; an
    # undeclared slate is itself a suppressing failure.
    raw_projections = _list(snapshot.get("projections"))
    expected_raw = snapshot.get("expected_projections")
    expected_keys = None
    if isinstance(expected_raw, list):
        expected_keys = []
        for e in expected_raw:
            e = _dict(e)
            expected_keys.append((e.get("game_key"), e.get("team"), e.get("metric")))
    if expected_keys is None:
        alerts.append(_alert("EXPECTED_COVERAGE_UNDECLARED", "projections",
                             "the snapshot declares no expected_projections, so a projection that "
                             "vanished could not be distinguished from one that never existed"))
        global_codes.append("EXPECTED_COVERAGE_UNDECLARED")
    else:
        present_keys = {(_dict(p).get("game_key"), _dict(p).get("team"), _dict(p).get("metric"))
                        for p in raw_projections}
        for key in expected_keys:
            if key not in present_keys:
                alerts.append(_alert("PROJECTION_ROW_ABSENT", "/".join(str(k) for k in key),
                                     "this projection was expected and is absent from the "
                                     "snapshot; it is NOT silently omitted from the panel"))
        for key in sorted(present_keys, key=lambda k: tuple(str(x) for x in k)):
            if key not in expected_keys:
                alerts.append(_alert("PROJECTION_ROW_UNEXPECTED",
                                     "/".join(str(k) for k in key),
                                     "this projection is not in the declared expected slate"))

    # ---- projections -------------------------------------------------------------------------
    projection_rows = []
    if not raw_projections:
        alerts.append(_alert("NO_PROJECTIONS", "projections",
                             "the snapshot carries no projection rows; nothing can be shown"))

    for raw in raw_projections:
        raw = _dict(raw)
        game_key = raw.get("game_key") or "<unkeyed game>"
        team = raw.get("team")
        codes = list(global_codes)

        for dep in _list(raw.get("depends_on_inputs")):
            dep_row = input_by_id.get(dep)
            if dep_row is None:
                codes.append("DEPENDENCY_UNDECLARED")
            elif dep_row["status"] in SUPPRESSING_INPUT:
                codes.append(f"INPUT_{dep_row['status']}")
        for dep in _list(raw.get("depends_on_jobs")):
            dep_row = job_by_id.get(dep)
            if dep_row is None:
                codes.append("DEPENDENCY_UNDECLARED")
            elif dep_row["status"] in SUPPRESSING_JOB:
                codes.append(f"JOB_{dep_row['status']}")
        for dep in _list(raw.get("depends_on_lineups")):
            dep = dep if isinstance(dep, (list, tuple)) and len(dep) == 2 else None
            dep_row = lineup_by_key.get(tuple(dep)) if dep else None
            if dep_row is None:
                codes.append("DEPENDENCY_UNDECLARED")
            elif dep_row["status"] in SUPPRESSING_LINEUP:
                codes.append(f"LINEUP_{dep_row['status']}")

        # A projection for a game/team whose lineup row exists is gated by it even when the
        # projection forgot to declare the dependency. Forgetting to declare must not buy a number.
        if team is not None and (game_key, team) in lineup_by_key:
            row = lineup_by_key[(game_key, team)]
            if row["status"] in SUPPRESSING_LINEUP:
                codes.append(f"LINEUP_{row['status']}")

        value = raw.get("value")
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        if not numeric:
            codes.append("PROJECTION_VALUE_ABSENT")

        display = _alert_cell(codes) if codes else _number_cell(value, raw.get("unit"))
        for code in sorted(set(codes)):
            alerts.append(_alert(code, f"{game_key}/{team}/{raw.get('metric')}",
                                 f"projection suppressed: {describe(code)}"))
        projection_rows.append({
            "game_key": game_key,
            "team": team,
            "metric": raw.get("metric"),
            "unit": raw.get("unit"),
            "uncertainty": raw.get("uncertainty"),
            "depends_on_inputs": _list(raw.get("depends_on_inputs")),
            "depends_on_jobs": _list(raw.get("depends_on_jobs")),
            "depends_on_lineups": _list(raw.get("depends_on_lineups")),
            "display": display,
        })

    # An expected-but-absent projection is rendered as its own suppressed row, so the operator
    # sees the hole rather than a shorter table.
    if expected_keys is not None:
        present_keys = {(r["game_key"], r["team"], r["metric"]) for r in projection_rows}
        for key in expected_keys:
            if key not in present_keys:
                projection_rows.append({
                    "game_key": key[0], "team": key[1], "metric": key[2], "unit": None,
                    "uncertainty": None, "depends_on_inputs": [], "depends_on_jobs": [],
                    "depends_on_lineups": [],
                    "display": _alert_cell(["PROJECTION_ROW_ABSENT"]),
                })

    alerts = _dedupe(alerts)
    counters = {
        "n_inputs": len(input_rows),
        "n_inputs_ok": sum(1 for r in input_rows if r["status"] == INPUT_OK),
        "n_inputs_stale": sum(1 for r in input_rows if r["status"] == INPUT_STALE),
        "n_inputs_missing": sum(1 for r in input_rows if r["status"] == INPUT_MISSING),
        "n_inputs_unbound": sum(1 for r in input_rows if r["status"] == INPUT_UNBOUND),
        "n_lineups": len(lineup_rows),
        "n_lineups_present": sum(1 for r in lineup_rows if r["status"] in LINEUP_OBSERVED),
        "n_lineups_missing": sum(1 for r in lineup_rows if r["status"] == LINEUP_MISSING),
        "n_jobs": len(job_rows),
        "n_jobs_failed": sum(1 for r in job_rows if r["status"] == JOB_FAILED),
        "n_jobs_did_not_run": sum(1 for r in job_rows if r["status"] == JOB_DID_NOT_RUN),
        "n_jobs_late": sum(1 for r in job_rows if r["status"] == JOB_LATE),
        "n_expected_projections": None if expected_keys is None else len(expected_keys),
        "n_projections": len(projection_rows),
        "n_projections_shown": sum(1 for r in projection_rows
                                   if r["display"]["kind"] == DISPLAY_NUMBER),
        "n_projections_suppressed": sum(1 for r in projection_rows
                                        if r["display"]["kind"] == DISPLAY_ALERT),
        "n_alerts": len(alerts),
        "n_alerts_critical": sum(1 for a in alerts if a["severity"] == "CRITICAL"),
        "n_alerts_warning": sum(1 for a in alerts if a["severity"] == "WARNING"),
    }

    serving = "SERVING"
    if global_codes:
        serving = "SUPPRESSED"
    elif counters["n_projections"] and not counters["n_projections_shown"]:
        serving = "SUPPRESSED"
    elif not counters["n_projections"]:
        serving = "SUPPRESSED"
    elif counters["n_projections_suppressed"]:
        serving = "DEGRADED"

    return {
        "schema": EVALUATION_SCHEMA,
        "snapshot_id": snapshot.get("snapshot_id"),
        "snapshot_generated_at_utc": snapshot.get("generated_at_utc"),
        "snapshot_age_seconds": None if snapshot_age is None else round(snapshot_age, 3),
        "snapshot_max_age_seconds": max_age,
        "snapshot_fresh": snapshot_fresh,
        "evaluated_at_utc": evaluated_at_utc,
        "model_binding": binding,
        "serving": serving,
        "global_suppression_codes": sorted(set(global_codes)),
        "input_rows": input_rows,
        "lineup_rows": lineup_rows,
        "job_rows": job_rows,
        "rollback_row": rollback_row,
        "projection_rows": projection_rows,
        "alerts": alerts,
        "counters": counters,
    }


def _dedupe(alerts):
    seen = set()
    out = []
    for a in alerts:
        key = (a["code"], a["subject"], a["detail"])
        if key in seen:
            continue
        seen.add(key)
        out.append(a)
    out.sort(key=lambda a: (SEVERITY_ORDER.get(a["severity"], 0), a["code"], str(a["subject"])))
    return out
