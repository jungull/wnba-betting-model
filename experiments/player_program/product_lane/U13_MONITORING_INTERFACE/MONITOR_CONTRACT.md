# U13 monitoring interface — contract

> PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
> has been promoted.

This document states what the monitor promises, in terms a later implementer can be held to. It
is a product contract, not a scientific one. Nothing in it asserts that any model is fit to serve,
and nothing in it implies that a challenger exists or has been promoted.

## 1. What the monitor is

A pure function over a snapshot:

```
evaluate(snapshot: dict, evaluated_at_utc: str) -> evaluation
render_text(evaluation) -> str
```

The snapshot is `player_program/monitor_snapshot/1`. The evaluation is
`player_program/monitor_evaluation/1`. Both are plain JSON. The monitor never fetches, never
writes, never retries and never caches. A caller supplies a frame; the monitor judges that frame.

## 2. Model-agnosticism (hard requirement)

`model_binding.model_version` and `model_binding.artifact_sha256` are **opaque data**. The monitor
never parses them, never branches on them and never compares them to a known list. Any string is
accepted and echoed. The interface therefore cannot tell which model produced a number, which is
precisely the property that keeps it usable if the incumbent is never replaced.

`TESTS.py` section D enforces this mechanically: it reads every `arm_id`, `experiment_id` and
`artifact_id` out of `experiments/player_program/arm_registry.jsonl`, adds the frozen incumbent's
arm name from `PROGRAM_STATE.json`, and fails if any of those 50 strings — or either of the
incumbent's two MAE figures — appears anywhere on the product surface
(`monitor_schema.py`, `monitor_state.py`, `render_monitor.py`, `build_views.py`,
`make_fixtures.py`, `fixtures/*.json`).

## 3. The four failure classes are separate panels

| Panel | Statuses | Rendered as |
|---|---|---|
| INPUT FRESHNESS | `OK` `STALE` `MISSING` `UNBOUND` `ERROR` `UNKNOWN` | one row per input, with observed time, measured age and the breached limit |
| LINEUPS | `PROJECTED` `ANNOUNCED` `CONFIRMED` `MISSING` `UNBOUND` `STALE` `UNKNOWN` | one row per (game, team) |
| JOBS | `SUCCEEDED` `RUNNING` `LATE` `FAILED` `DID_NOT_RUN` `UNKNOWN` | one row per job, with due time, cutoff, completion and signed latency past cutoff |
| ROLLBACK | `NONE` `ACTIVE` `PENDING` `FAILED` `UNKNOWN` | serving version, superseded version, when, why, by whom |

They are never merged into a single health light. A stale odds feed and a failed feature build
produce different rows, different codes and different severities.

The lineup status vocabulary is not invented here. It is quoted from the repository's own capture
schema: `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/capture_schema.py:98`
(`"lineup_status": ["PROJECTED", "ANNOUNCED", "CONFIRMED"]`). The eight input domains are the
eight D11 contract domains declared at `capture_schema.py:78`.

## 4. Fail-closed, everywhere

1. Every status vocabulary has an `UNKNOWN` member and every unparseable, absent or
   out-of-vocabulary value maps to it. `UNKNOWN` suppresses. There is no path by which missing
   information becomes a default `OK`.
2. `bound` unstated is **not** treated as bound.
3. An input with no `max_age_seconds` has undefined freshness and is `UNKNOWN`, not fresh.
4. A job that declares `SUCCEEDED` but whose `completed_at_utc` is after its own `cutoff_utc` is
   downgraded to `LATE` on the timestamps alone. A late record does not read as a healthy record.
   This is the shape the repository documents as defects **D-a** and **D-d**
   (`experiments/player_program/PROJECT_UPDATE_2026-08-04.md:199` and `:202`).
5. A lineup declaring `ANNOUNCED` whose `announced_five` is not five named players is `MISSING`.
6. An absent `rollback` block is `UNKNOWN`, never `NONE`.
7. `evaluate` does not raise. `None`, a list, a string and a wrong-schema object all evaluate to
   `SUPPRESSED` with alerts. A monitor that crashes is a monitor that shows nothing while
   something is wrong.
8. The snapshot's own age is checked. A frame older than `snapshot_max_age_seconds`
   (default 900 s) suppresses everything: a frozen dashboard must not keep showing the last good
   frame.

## 5. Absence never renders as a number

Every displayable quantity passes through a display cell:

```
{"kind": "NUMBER", "text": "81.25", "value": 81.25, "unit": ..., "codes": []}
{"kind": "ALERT",  "text": "UNAVAILABLE", "codes": ["INPUT_STALE", ...]}
```

An `ALERT` cell **does not carry the underlying value at all** — `monitor_state` drops it — so the
renderer physically cannot print it. The alert token is the word `UNAVAILABLE`: not a blank, not a
dash, not a zero, nothing that reads as a quantity.

A projection renders as `NUMBER` only when **all** of the following hold:

* the evaluation clock parses;
* the snapshot is fresh and schema-valid;
* `model_version` is a non-empty string and at least one artifact hash is present and non-empty;
* the rollback state is not `PENDING`, `FAILED` or `UNKNOWN`;
* every input marked `required_for_serving` is `OK`, and every declared input dependency is `OK`;
* every `blocking` job is `SUCCEEDED`, and every declared job dependency is `SUCCEEDED`;
* every declared lineup dependency is present and fresh — **and** any lineup row that exists for
  the projection's own (game, team) is present and fresh, even if the projection forgot to declare
  it. Forgetting to declare a dependency does not buy a number;
* the value itself is a real number.

Otherwise the cell is `ALERT` and carries the codes that suppressed it.

## 6. Expected coverage: a vanished row is a failure

A projection that disappears from the snapshot is invisible — a shorter table reads as a complete
table. The snapshot therefore declares `expected_projections`, its obligations for the frame. Any
expected key with no matching projection is rendered as **its own suppressed row** plus a
`CRITICAL` `PROJECTION_ROW_ABSENT` alert. A snapshot that declares no expected slate raises
`EXPECTED_COVERAGE_UNDECLARED` and suppresses everything: a monitor that does not know what it
should be showing cannot certify that it is showing it.

This mirrors the obligation-based framing the operations lane already uses for capture coverage
(`experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/FINDINGS.json`), where
the defect was precisely that an obligation which never became visible produced no alarm.

## 7. Serving states

* `SERVING` — no global suppression, every projection rendered.
* `DEGRADED` — some projections suppressed, others rendered. The panel says so.
* `SUPPRESSED` — nothing is being served. This is the state for an empty, stale, malformed or
  unbound frame.

`ROLLBACK_ACTIVE` deliberately does **not** suppress. A rolled-back version is still a real
serving version and its numbers are real; hiding them would push the operator to a worse source.
It raises a mandatory banner naming both the serving and the superseded version instead.

## 8. What this contract does not do

* It does not fetch, schedule, alert-route, page or persist. It renders one frame.
* It does not define who writes the snapshot. Binding it to a real producer is out of this node's
  write scope and is not attempted.
* It makes no claim that any model is accurate, promoted, or ready. It only reports whether the
  inputs a projection depended on were present and fresh at a stated instant.
