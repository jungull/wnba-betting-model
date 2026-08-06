# INJURY_OFFICIAL/live -- D032/D033 primary injury track, live capture

**Owner:** market_intelligence lane, D033 mandate
(`experiments/player_program/orchestration/DECISION_LEDGER.jsonl`,
decisions `D032_OFFICIAL_INJURY_REPORT_PRIMARY_TRACK`,
`D033_ACQUISITION_STRATEGY_REVISION`, `D034_GRADUATION_STANDARD`).
**Contract:** `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md`,
verified sha256 `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de`
before this work started (full path, per the D030 lesson about naming
contract files unambiguously). Source hierarchy §D033: **official
quarter-hour injury report is rank 1**, the top of the frozen hierarchy
this track exists to fill.

**This is a replacement of an earlier session's version of this track.**
That earlier README made access-verification claims (three successful
HEAD probes against `ak-static.cms.nba.com`) this session could not
independently reproduce against the same host -- see "Note on the prior
run" in `ACCESS_VERIFICATION.md`. Every finding in this README and its
companion docs was re-verified from scratch this session; nothing here is
carried over from the prior README uncritically.

**Ownership boundary:** this node writes only inside
`experiments/market_program/INJURY_OFFICIAL/live/` (this directory,
`raw/`, the CSVs, this README, `SCHEMA.md`, `ACCESS_VERIFICATION.md`, the
Python modules, and `tests/`). It reads the live main worktree
(`C:\Users\jgallagher\wnba-betting-model`) **read-only**, for two things
only: (1) `entity_resolution.py`'s public interface, via
`entity_resolution_bridge.py`, matching the program's "one
identity-resolution implementation" discipline; (2) four real production
PDF bytes copied once into `tests/fixtures/` for offline parser testing
-- see `tests/fixtures/PROVENANCE.md`. It never writes to the live main
worktree and never touches The Odds API.

---

## 1. What was verified this session (full detail in `ACCESS_VERIFICATION.md`)

- **`www.wnba.com/api/injury-reports`** (the backing JSON the D033 history
  track found via Wayback CDX with zero historical depth) -- **confirmed
  live and reachable, HTTP 200**, from two independent HTTP clients
  (PowerShell `Invoke-WebRequest`, Python stdlib `urllib`), with an honest
  non-browser-spoofing User-Agent. Returns the exact quarter-hour slot
  list (`12:00 a.m.`, `12:15 a.m.`, `12:30 a.m.`, ... ET) for the current
  day, each entry linking an `ak-static.cms.nba.com` PDF. This is now the
  **discovery mechanism** this track's fetcher uses -- it enumerates the
  day's real documents, rather than guessing/walking back slot labels.
- **`www.wnba.com/wnba-injury-report`** (the human-readable page) -- also
  `200` this session, not blocked.
- **`ak-static.cms.nba.com/*.pdf`** (the actual report documents) -- TCP
  connects cleanly (DNS resolves, port 443 handshake succeeds), but the
  HTTP layer never completed across five attempts spanning four different
  client implementations (PowerShell, curl, .NET HttpClient, Python
  urllib) -- no 403/429/challenge-page signature anywhere, just timeouts
  and one connection reset. Classified `NETWORK_UNAVAILABLE` (distinct
  from a confirmed bot-block) and **not worked around**, per standing
  rules. One real, honestly-logged attempt from this track's own
  `capture_injury_live.py` is recorded in `capture_log.csv` with this
  exact outcome.
- **Parser verified against four real production PDFs**, sourced
  read-only from the live main worktree's own ongoing production archive
  (`data/injury_capture/raw/`, a script this track does not own or
  modify) -- 12/12 fixture tests pass, including one that pins a real,
  documented parser limitation (a reason-cell layout edge case) rather
  than hiding it. See `tests/`.
- **Entity resolution verified**: `entity_resolution_bridge.py` imports
  the live main worktree's `entity_resolution.py` read-only and resolves
  real names from the fixture PDFs.

## 2. What this track builds

### `fetch_official_report.py`
Owns the network layer only: `fetch_discovery_json()` (the JSON
enumeration, confirmed working) and `fetch_pdf()` (retries only on
`NetworkUnavailable`, never on `BotBlockDetected`). `BotBlockDetected` is
raised on an actual HTTP 401/403/429 or a challenge-page body marker, and
is never caught internally -- it propagates to the caller, which stops
rather than bypasses. `NetworkUnavailable` is raised on a connection-level
failure with no HTTP status at all, and is retried a bounded number of
times with backoff before propagating. Honest User-Agent throughout, 1 rps
minimum spacing enforced by `_pace()`.

### `parser.py`
Independent implementation (not copied from the live main worktree's
`injury_capture_daily.py`, though structurally similar because the real
PDF layout dictates the approach -- see its module docstring). Coordinate
(x, y) word clustering, per-page header re-derivation, wrapped-name and
wrapped-reason merging, explicit `NOT YET SUBMITTED` handling, and a
documented known limitation around one specific reason-cell layout
pattern (rejects rather than silently mis-parses). Returns
`(rows, meta, rejects)` -- rejects are never dropped.

### `entity_resolution_bridge.py`
Read-only bridge to the live main worktree's single entity-resolution
implementation. Degrades to blank `player_id` (never guessed) if
unavailable, matching `entity_resolution.py`'s own
`try_load_capture_index()` discipline.

### `capture_injury_live.py`
The orchestrator (see `SCHEMA.md` for full column-by-column detail):
hash-dedup against `capture_log.csv`'s full history (survives restarts),
status-supersession detection producing `status_transitions.csv` rows
with M00-§6.1-style `[t_lower, t_upper]` interval censoring, the
`REMOVED_FROM_REPORT` sentinel (a player dropping out of the report is
recorded explicitly, never silently), `NOT_YET_SUBMITTED` coverage rows,
and `rejects.csv`. Three timestamp classes kept distinct on every snapshot
row per D034: provider publication (embedded PDF header, T1), document
(URL slot label / `Last-Modified`), our capture (`retrieval_ts_utc` /
`ingestion_ts_utc`, T0).

`run_latest_cycle()` is the normal 15-minute-cadence entry point: pulls
the discovery JSON, fetches every link not already in `capture_log.csv`.
A `BotBlockDetected` on any link stops the whole run immediately (exit
code 2). A `NetworkUnavailable` is logged per-link and does not abort
already-attempted work, but the process still exits nonzero (exit code 1)
so a scheduler sees the cycle as incomplete.

## 3. Tests (D033 mandate item 4 -- run regardless of live accessibility)

```
cd experiments/market_program/INJURY_OFFICIAL/live
python -m unittest discover -s tests -v
```

12 tests, all passing this session: 5 parser tests against real bytes
(including the documented known limitation), 7 pipeline tests (hash-dedup,
status-supersession, the `REMOVED_FROM_REPORT` absent-row rule, the
`NOT_YET_SUBMITTED` coverage rule, rejects reporting, and that both
`BotBlockDetected` and `NetworkUnavailable` are logged and re-raised, never
swallowed). Pipeline tests run against a temp directory (monkeypatched
paths) and never touch this track's real CSVs or `raw/`.

## 4. Run status this session

- **Discovery-endpoint access verification: DONE, and it changes the
  picture** -- `wnba.com/api/injury-reports` is live and reachable, not
  blocked, contradicting the mandate's premise that it was still blocked
  from an earlier survey. Full detail and the exact discrepancy with that
  earlier survey: `ACCESS_VERIFICATION.md` §1-2.
- **PDF-host access verification: DONE** -- not blocked (no bot-mitigation
  signature observed), but not reachable this session from this sandbox
  (`NETWORK_UNAVAILABLE`, reproduced five ways). `ACCESS_VERIFICATION.md`
  §3.
- **Parser verified: DONE** against four real production PDFs.
- **Entity resolution verified: DONE**.
- **Capture module: BUILT, tested, and actually run this session** against
  the real discovery endpoint. It correctly discovered 63 real report
  links, attempted a real fetch of the first, and honestly logged
  `NETWORK_UNAVAILABLE` in `capture_log.csv` when the PDF host didn't
  respond -- it did not fabricate a capture, did not fall back to stale
  data, and did not retry indefinitely (bounded retries, then stop and
  report). `injury_snapshots.csv`, `status_transitions.csv`,
  `report_coverage.csv`, and `rejects.csv` are therefore headers-only as
  of this session; the one real row that exists is in `capture_log.csv`,
  proving one real attempted cycle.
- **Fixture tests: DONE, all 12 passing**, independent of live access.

## 5. Scheduling

Not scheduled by this node (D033 mandate: "NOT scheduled -- coordinator
schedules"). Invoke manually via `python capture_injury_live.py` (normal
cadence: every 15 minutes, matching the report's own publish grid; a
`--backfill-today` style re-run of `run_latest_cycle()` will pick up every
link not yet in `capture_log.csv`, so a gap in scheduling self-heals up to
whatever the discovery JSON still lists for the current ET day). Recommend
the coordinator's first scheduled run retry the PDF fetch from whatever
environment actually runs the schedule -- this sandbox's specific egress
condition to `ak-static.cms.nba.com` may not reproduce there.
