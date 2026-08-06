# Schema -- D032/D033 official injury report, live capture

All tables are **append-only**: a correction is a new row, never an
`UPDATE`, matching the M00 contract's amendment-4 discipline (§6.3) applied
here to a non-market capture, at the D033 mandate's request, "by the same
self-imposed discipline."

## `capture_log.csv` -- proof of every attempted poll, success or not

One row per fetch attempt (not per parsed report -- this is the honest
record that a cycle was attempted at all, independent of whether it
produced anything new).

| column | meaning |
|---|---|
| `capture_id` | this attempt's id |
| `attempted_ts_utc` | when the fetch attempt began |
| `source_url` | the PDF URL attempted |
| `http_status` | HTTP status if one was returned, else blank (blank means `NetworkUnavailable` -- no status at all, see `fetch_official_report.py`) |
| `outcome` | `NOVEL` \| `DUPLICATE_OF_PRIOR` \| `BOT_BLOCK` \| `NETWORK_UNAVAILABLE` |
| `payload_hash_sha256` | sha256 of the raw response bytes, blank if the fetch never completed |
| `dedup_of_capture_id` | if `DUPLICATE_OF_PRIOR`, the `capture_id` of the first capture with this hash |
| `raw_path` | path under `raw/` the verbatim bytes were archived to (blank if the fetch failed before bytes arrived) |
| `retrieval_ts_utc` | when the response was fully received |

## `injury_snapshots.csv` -- one row per player-designation, per NOVEL capture

Only rows the report explicitly prints. **Never** a synthetic
"Available"/healthy row for a player not printed (see "Absent row is not
healthy", below).

| column | timestamp class | meaning |
|---|---|---|
| `capture_id` | -- | joins to `capture_log.csv` |
| `cycle_id` | -- | groups captures by ET calendar day (`cycle_YYYYMMDD`) |
| `url_slot_label` | document | the discovery JSON's own label, e.g. `"3:15 p.m. ET report"` |
| `url_slot_ts_et` / `url_slot_ts_utc` | document | parsed slot instant, when the label parses cleanly (never guessed if it doesn't) |
| `doc_last_modified_utc` | document | the PDF response's own `Last-Modified` header, when present |
| `provider_publication_ts_raw` / `_et` | **provider publication** | the PDF's own embedded header line (`"Injury Report: MM/DD/YY HH:MM AM/PM"`), publisher-asserted, **T1** |
| `retrieval_ts_utc` | **our capture** | when our GET completed -- T0, witnessed by us |
| `ingestion_ts_utc` | **our capture** | when this row was written -- T0 |
| `poll_interval_at_capture` | -- | `PT15M`, the report's own publish grid |
| `max_staleness_bound_minutes` | -- | `15`; never claim anything sharper than the grid |
| `vendor_latency_note` | -- | explicit UNBOUNDED-below-the-grid caveat (see `capture_injury_live.py::VENDOR_LATENCY_NOTE`) |
| `source_url` | -- | the exact PDF URL |
| `source_provenance_class` | -- | one-line plain-English restatement, D033 §SCHEMA.md-style discipline |
| `payload_hash_sha256` | -- | sha256 of the raw PDF bytes this row was parsed from |
| `prev_snapshot_capture_id` | -- | reserved; not yet populated (no two NOVEL captures existed in the same session to link) |
| `game_date`, `game_time_et`, `matchup` | -- | as printed |
| `team_raw` | -- | exactly as printed |
| `team` | -- | currently identical to `team_raw` -- **no canonical team-name mapping is applied here**; this track deliberately did not fork/guess a normalization table, to avoid a second, divergent copy of `normalize_team()` (the production implementation in `injury_capture_daily.py`, not imported here because it isn't factored out as an independently importable pure function -- flagged for the runbook as the one piece of production logic this track chose NOT to reuse, and why) |
| `player_raw` | -- | exactly as printed, `Last, First` reordered to `First Last`, hyphen line-wraps rejoined |
| `player_id` | -- | resolved via the program's one entity-resolution implementation (`entity_resolution_bridge.py`, read-only import of the live main worktree's `entity_resolution.py`); **blank, never guessed**, if resolution is unavailable or the name doesn't match |
| `status` | -- | one of `parser.OFFICIAL_STATUSES`; unrecognized values are rejected, not coerced |
| `reason` | -- | free text; **word order is best-effort, not guaranteed** -- see `parser.py`'s documented known limitation |

## `status_transitions.csv` -- one row per (team_raw, player_raw) whose
status changed between the immediately preceding NOVEL capture and this one

| column | meaning |
|---|---|
| `transition_id` | this transition's id |
| `team_raw`, `team`, `player_raw`, `player_id` | as in the snapshot table |
| `status_before` | prior status, blank if this player had no prior snapshot row |
| `status_after` | new status, or the sentinel `REMOVED_FROM_REPORT` (see below) |
| `reason_after` | the new reason text (or an explicit plain-English note for `REMOVED_FROM_REPORT`) |
| `t_lower_utc_bound` / `t_upper_utc_bound` | M00 §6.1-style interval censoring: `[prior retrieval_ts, this retrieval_ts]` -- **never** a sharper point estimate than the 15-minute grid |
| `poll_interval_event` | `PT15M` |
| `censor_type` | always `interval` (never `exact`) |
| `tier` | `T0` -- directly witnessed by us, not vendor-asserted |
| `prev_capture_id`, `curr_capture_id` | the two `capture_id`s bracketing the transition |

**`REMOVED_FROM_REPORT`** is a real, explicit status value this table can
carry -- it means "this player had a row in the previous NOVEL snapshot and
does not have one in this one." It is **not** a synonym for `Available`
and must never be read as one; the `reason_after` field says so on every
such row. This is the mechanical implementation of the "absent row is not
healthy" rule for the transition case, not just for the snapshot case.

## `report_coverage.csv` -- explicit NOT_YET_SUBMITTED rows

A team-game the report marks "NOT YET SUBMITTED" (a real, structurally
meaningful report state) gets one row here per NOVEL capture. A consumer
must check this table before treating "no snapshot row for this team-game"
as informative at all: it may mean the team filed a clean report with no
designations, or it may mean the team hasn't filed yet, and only this
table distinguishes the two.

## `rejects.csv` -- unmatched / ambiguous parser output, never silently dropped

One row per PDF fragment the parser could not confidently place into a
snapshot row, D034's "unmatched-player/rejects reporting" requirement.
Carries the raw text and a reason code (`unplaceable_row_fragment`,
`row_before_header`, `unrecognized_status:<value>`, or a header-shape
error). A capture with rejects still succeeds and still writes every row
it COULD place -- rejects are additive information, not a reason to
discard an otherwise-good capture.

## Absent-row-is-not-healthy, enforced structurally (not just by policy)

Three independent mechanisms, not one:
1. `injury_snapshots.csv` is built entirely from what the parser found
   printed -- there is no roster cross-join anywhere in
   `capture_injury_live.py` that could synthesize a healthy row.
2. A player who drops out of the report between two NOVEL captures gets an
   explicit `REMOVED_FROM_REPORT` transition row, not silence.
3. A team-game the report itself marks not-yet-filed gets an explicit
   `NOT_YET_SUBMITTED` coverage row, so "no data" and "filed, all healthy"
   are never conflated.
`tests/test_pipeline.py` asserts all three mechanically (not just by
reading the code), against real fixture bytes.
