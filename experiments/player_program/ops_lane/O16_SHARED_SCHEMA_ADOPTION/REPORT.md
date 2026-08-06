# O16_SHARED_SCHEMA_ADOPTION — REPORT

USER DECISION. Merging a shared schema or contract change is USER_REQUIRED: it crosses the boundary between the isolated operations lane and contracts other threads depend on. Confirmed at wave 3: the operations lane's targets (prospective_pair/should_run_base.py, coverage_audit.py) live on branch data-refresh-2026 and are ABSENT from this branch, so adoption is a cross-branch change as well as a shared-contract one.

## Authorization

The user approved **all three bundles** in chat on 2026-08-06; recorded as decision
`D022_O16_USER_APPROVAL_ALL_THREE` before any implementation was dispatched. Scope honored:
the three bundles exactly as proposed and tested by their originating nodes; no frozen path,
no gate module, no registry record, no push of data-refresh-2026.

## What was adopted (all on branch `data-refresh-2026`, merged fast-forward to `a470f34`, fix at `723a56d`)

**Bundle A — O11 scheduler patch.** `PROPOSED_PATCH.diff` applied byte-clean to
`prospective_pair/should_run_base.py` (pre `0D41A3B4…`, post `1A34E871…`). Slate rows with no
official game_id are now served under the provisional id daily_forecast mints instead of
being silently dropped, and every decline reason names the game count examined and any
unresolved provisional games. Suite: 69/69, including new checks that drive the real
module's `assess()`. The `and not dup` masking conjunction (defect D-c / node O12) is out of
this bundle's scope, verified unchanged and not worsened.

**Bundle B — O14 entity-resolution contract (all four proposals).** New
`entity_resolution.py` (cross-season identity index + curated alias overlay, normalized-exact
only, no fuzzy fallback); `injury_capture_daily.py` and `props_capture_daily.py` resolve
`player_id` at capture time, writer-forward (legacy-header logs keep receiving legacy-shape
rows; existing bytes never rewritten); single-tenant rosters with `assignment_source`
provenance; unbindable Out/Doubtful designations promoted WARN→BLOCK so availability fails
closed; alias table installed at `data/entity_resolution/alias_table.json` (schema
`ops_lane/O14/alias_table/1`). Migration script `migrate_o14_capture_player_id.py` is
**shipped, not run** (dry-run default, idempotent, atomic). Dry run: 547/551 injury rows and
2471/2471 props rows resolve; the 4 unresolved are the genuine cold starts O14 predicted.

**Bundle C — decision D-4.** `daily_forecast.py` restructured to per-game execution scope
(one failing game cannot abort or contaminate the slate); forecast log upgraded to SCHEMA/2
via `evalharness/forecast_log.py` with a both-versions reader; existing
`forecasts/forecast_log.jsonl` rows never rewritten; `migrate_forecast_log_schema2.py`
shipped, not run. B's two cross-owned edits (BLOCK severity admission; player-layer wiring)
were applied with documentation and independently re-verified (110/110).

**Explicitly NOT adopted** (outside the approved bundle, recorded, no silent scope growth):
O12's P3 proposal (decision_time_label reassignment — amends two registered team-thread
contracts); deeper internal structure for `alt_model_predictions` beyond what any document
specifies.

## Incidents surfaced by the adoption — both material, both resolved

1. **The live scheduler module was never under version control.** `prospective_pair/`
   (7 files including the patch target) existed only as untracked working files in the main
   worktree. Committed as-is as a pre-patch baseline (`17e05c4`) so the patch has an
   auditable base. Until today nothing protected those files against loss.
2. **A type defect the isolated worktree could not catch.** Live capture data carries
   `game_date` as strings; the adoption snapshot parsed datetimes. Three
   `.game_date.max().date()` sites in `entity_resolution.py` crashed against live bytes —
   caught by post-merge validation in the live worktree, before the next scheduled capture
   run could hit it. Fixed with explicit `pd.to_datetime` coercion (`723a56d`).

## Validation

| suite | isolated worktree | live worktree post-merge |
|---|---|---|
| O11 (scheduler) | 42/42 (design) → 69/69 (real module) | pass, 0 failed |
| O14 (entity resolution) | 55/55 (T5 replay skipped — postdated base) | **59/59** incl. live replay |
| D4 (per-game + SCHEMA/2) | 77/77 | 55/55 core + live-log read-only checks |

Live snapshot artifacts verified byte-identical after test runs. No agent ran git; all
commits are coordinator task-scoped commits.

## What remains deliberately undone

* Both migration scripts await a deliberately chosen quiet window (user or coordinator runs
  them; each is idempotent and dry-run-first).
* `data-refresh-2026` is **not pushed** (D017 authorizes pushing `player-model-program`
  only). If the user wants the ops branch backed up remotely, that is a one-line
  authorization away.
* The o16-adoption worktree is retained for audit; safe to remove after the next quiet
  window.

## Could not establish

Whether the WARN→BLOCK promotion changes forecast-gap counts on a real future slate — no
qualifying unbindable designation exists in the current capture window; the fail-closed path
is exercised by fixture tests only until one occurs naturally.
