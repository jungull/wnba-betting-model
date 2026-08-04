# U11 view payload contract — `u11_view_payload/1`

This is the *only* thing `ui_shell.py` understands. It is a rendering contract, not a
scientific one: it says what the page needs in order to draw a cell honestly, and it says
nothing about how any number was produced.

**Epistemic status:** PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim
and must not imply a model has been promoted.

## Relationship to U10_PREDICTION_API_SCHEMA

`U10_PREDICTION_API_SCHEMA` was `RUNNING` concurrently with this node at the time this was
written (`experiments/player_program/orchestration/GRAPH_STATE.json`, key
`status.U10_PREDICTION_API_SCHEMA`), so no U10 response schema existed to build against.
This contract was therefore defined locally, but deliberately field-for-field over the
same families U10's acceptance criteria name (game IDs, model version, artifact hashes,
input freshness, projections, uncertainty, warnings, component explanations, market
comparison, audit metadata — `PROGRAM_GRAPH.json`, node `U10_PREDICTION_API_SCHEMA`,
`acceptance_criteria[1]`). When U10 lands, the expected integration is a single adapter
function mapping the U10 response onto this dict; `render_payload()` should not change.

## Shape

```
{
  "schema": "u11_view_payload/1",         # anything else renders a PAYLOAD_UNREADABLE warning
  "title": str,
  "as_of": ISO-8601 instant,              # the clock staleness is measured against
  "model": {
    "version":           str | null,      # opaque. The shell never interprets it.
    "artifact_sha256":   {name: digest},  # opaque. Rendered verbatim.
    "promotion_status":  str | null       # rendered verbatim, labelled "as stated by payload"
  },
  "inputs": [ {
    "input_id": str, "label": str,
    "status": "ok" | "missing" | "failed",
    "captured_at": ISO-8601 | null,
    "max_age_seconds": number | null,
    "detail": str
  } ],
  "games": [ {
    "game_id": str, "label": str, "tipoff": ISO-8601,
    "required_inputs": [input_id, ...],   # drives per-game suppression
    "rows": [ {
      "entity_id": str, "entity_label": str,
      "row_blockers": [str, ...],         # optional; any entry suppresses this row
      "projection":  {"value": number|null, "units": str},
      "uncertainty": {"lo": number|null, "hi": number|null, "level": str},
      "market":      {"line": number|null, "source": str},
      "components":  [ {"name": str, "contribution": number|null} ]
    } ],
    "notes": [str, ...]
  } ],
  "audit": {"payload_id": str, "generated_by": str, "source": str, "notes": str}
}
```

## Rendering rules the shell enforces (not the producer)

The producer is not trusted to have suppressed anything. Every rule below is applied at
render time against whatever the payload actually contains, including a payload that
carries a complete, plausible set of numbers behind a broken input — which is exactly what
`fixtures/F2_stale_input.json` and `fixtures/F4_failed_job.json` do.

| Condition | Rendered as |
| --- | --- |
| input `status: failed` | `INPUT_FAILED` warning; every number in each game requiring it is suppressed |
| input `status: missing`, or no `captured_at` | `INPUT_MISSING` |
| `as_of - captured_at > max_age_seconds`, or negative age | `INPUT_STALE` |
| `captured_at`, `as_of` or `max_age_seconds` unparseable/absent | `INPUT_MISSING` — freshness that cannot be evaluated is never treated as fresh |
| `required_inputs` names an id absent from `inputs` | `INPUT_UNDECLARED` |
| no `model.version`, or empty `artifact_sha256` | `OUTPUT_UNBOUND` — an unattributable number is never shown |
| `row_blockers` non-empty | `ROW_BLOCKED`, scoped to that row |
| value `null` or key absent | `VALUE_ABSENT` |
| value non-numeric (incl. `bool`) | `VALUE_NOT_NUMERIC` |
| value NaN or ±inf | `VALUE_NOT_FINITE`; the rejected value is not echoed |
| `market` absent | market and delta cells warn; the projection still renders |
| `components` absent or empty | the explanation cell warns |

There is no imputation, no default, no zero, no carry-forward and no last-known-good
anywhere in the shell. A suppressed cell shows a reason code and nothing else.

## Deliberate non-features

* The shell has no notion of which model is correct, current or preferred.
* The shell will not rank, select or blend models. It renders one payload.
* The shell computes exactly one derived number, `projection − market line`, and only when
  both operands survived resolution.
