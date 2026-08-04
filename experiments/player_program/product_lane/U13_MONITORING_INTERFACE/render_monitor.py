"""
U13_MONITORING_INTERFACE -- the view.

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
has been promoted.

render_text(evaluation) turns an evaluation into the operator-facing panel. Four separate panels
-- INPUTS, LINEUPS, JOBS, ROLLBACK -- so the four contract-named failure classes are individually
visible. The PROJECTIONS panel prints a number only where the evaluation produced a NUMBER cell;
every other cell prints the alert token and its codes.

The renderer holds NO policy. It cannot decide to show a number the evaluation suppressed, because
it never sees the underlying value of a suppressed cell: monitor_state drops it.
"""

from __future__ import annotations

from monitor_schema import ALERT_CELL_TEXT, DISPLAY_NUMBER

BANNER = {
    "SERVING": "SERVING -- all monitored dependencies healthy",
    "DEGRADED": "DEGRADED -- some projections are suppressed; see PROJECTIONS",
    "SUPPRESSED": "SUPPRESSED -- NOTHING IS BEING SERVED. Every projection is withheld.",
}


def _table(headers, rows):
    widths = [len(h) for h in headers]
    cells = [[("" if c is None else str(c)) for c in row] for row in rows]
    for row in cells:
        for i, c in enumerate(row):
            widths[i] = max(widths[i], len(c))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()
    out = [line, "  ".join("-" * widths[i] for i in range(len(headers))).rstrip()]
    for row in cells:
        out.append("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())
    if not cells:
        out.append("(no rows -- see ALERTS)")
    return "\n".join(out)


def render_text(ev):
    if not isinstance(ev, dict):
        return "MONITOR UNAVAILABLE -- the evaluation itself is missing. Assume nothing is healthy."
    out = []
    serving = ev.get("serving", "SUPPRESSED")
    out.append("=" * 96)
    out.append(f"WNBA PLAYER MODEL -- OPERATIONAL MONITOR    [{serving}]")
    out.append(BANNER.get(serving, "SUPPRESSED -- state unknown; assume nothing is healthy."))
    out.append("=" * 96)

    binding = ev.get("model_binding") or {}
    out.append("")
    out.append("MODEL BINDING (opaque to this interface; carried as snapshot data)")
    out.append(f"  model_version   : {binding.get('model_version') or ALERT_CELL_TEXT}")
    out.append(f"  binding_source  : {binding.get('binding_source') or ALERT_CELL_TEXT}")
    hashes = binding.get("artifact_sha256") or {}
    if hashes:
        for name, value in sorted(hashes.items()):
            shown = value if isinstance(value, str) and value.strip() else ALERT_CELL_TEXT
            out.append(f"  artifact        : {name} = {shown}")
    else:
        out.append(f"  artifact        : {ALERT_CELL_TEXT} (no artifact hashes on the snapshot)")
    out.append(f"  snapshot        : id={ev.get('snapshot_id') or ALERT_CELL_TEXT} "
               f"generated={ev.get('snapshot_generated_at_utc') or ALERT_CELL_TEXT} "
               f"age={ev.get('snapshot_age_seconds')}s fresh={ev.get('snapshot_fresh')}")
    out.append(f"  evaluated_at    : {ev.get('evaluated_at_utc') or ALERT_CELL_TEXT}")

    out.append("")
    out.append("INPUT FRESHNESS")
    out.append(_table(
        ["input_id", "domain", "status", "observed_at_utc", "age_s", "limit_s", "required"],
        [[r.get("input_id"), r.get("domain"), r.get("status"),
          r.get("observed_at_utc") or ALERT_CELL_TEXT, r.get("age_seconds"),
          r.get("max_age_seconds"), r.get("required_for_serving")]
         for r in ev.get("input_rows") or []]))

    out.append("")
    out.append("LINEUPS")
    out.append(_table(
        ["game_key", "team", "status", "n_players", "observed_at_utc", "age_s"],
        [[r.get("game_key"), r.get("team"), r.get("status"),
          r.get("n_players") if r.get("n_players") is not None else ALERT_CELL_TEXT,
          r.get("observed_at_utc") or ALERT_CELL_TEXT, r.get("age_seconds")]
         for r in ev.get("lineup_rows") or []]))

    out.append("")
    out.append("JOBS")
    out.append(_table(
        ["job_id", "status", "due_at_utc", "cutoff_utc", "completed_at_utc",
         "cutoff_delta_min", "blocking"],
        [[r.get("job_id"), r.get("status"), r.get("due_at_utc") or "",
          r.get("cutoff_utc") or "", r.get("completed_at_utc") or ALERT_CELL_TEXT,
          r.get("latency_minutes_past_cutoff"), r.get("blocking")]
         for r in ev.get("job_rows") or []]))

    rb = ev.get("rollback_row") or {}
    out.append("")
    out.append("ROLLBACK")
    out.append(f"  state           : {rb.get('state') or ALERT_CELL_TEXT}")
    out.append(f"  active version  : {rb.get('active_model_version') or ALERT_CELL_TEXT}")
    out.append(f"  previous version: {rb.get('previous_model_version') or ALERT_CELL_TEXT}")
    out.append(f"  changed_at_utc  : {rb.get('changed_at_utc') or ALERT_CELL_TEXT}")
    out.append(f"  reason          : {rb.get('reason') or ALERT_CELL_TEXT}")
    out.append(f"  initiated_by    : {rb.get('initiated_by') or ALERT_CELL_TEXT}")

    out.append("")
    out.append("PROJECTIONS")
    proj_rows = []
    for r in ev.get("projection_rows") or []:
        display = r.get("display") or {}
        if display.get("kind") == DISPLAY_NUMBER:
            shown = display.get("text")
            why = ""
        else:
            shown = display.get("text") or ALERT_CELL_TEXT
            why = ",".join(display.get("codes") or []) or "UNKNOWN"
        proj_rows.append([r.get("game_key"), r.get("team"), r.get("metric"), shown,
                          r.get("unit") or "", why])
    out.append(_table(["game_key", "team", "metric", "value", "unit", "suppressed_by"], proj_rows))

    out.append("")
    out.append("ALERTS")
    alert_rows = [[a.get("severity"), a.get("code"), a.get("subject"), a.get("detail")]
                  for a in ev.get("alerts") or []]
    out.append(_table(["severity", "code", "subject", "detail"], alert_rows))

    c = ev.get("counters") or {}
    out.append("")
    out.append("COUNTERS  " + "  ".join(f"{k}={v}" for k, v in sorted(c.items())))
    out.append("")
    return "\n".join(out)
