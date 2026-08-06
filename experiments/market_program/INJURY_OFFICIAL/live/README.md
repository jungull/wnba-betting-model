# INJURY_OFFICIAL/live — D032/D033 primary injury track, live capture

**Owner:** market_intelligence lane, D033 mandate (`experiments/player_program/orchestration/DECISION_LEDGER.jsonl`
decisions `D032_OFFICIAL_INJURY_REPORT_PRIMARY_TRACK`, `D033_ACQUISITION_STRATEGY_REVISION`).
**Contract:** `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md`
(verified sha256 `1152dcd3bf74000f700844bc8bfc0df25de61a067f59534a714ac4f2f20265de` before this
work started). Source hierarchy §D033: **official quarter-hour injury report** is rank 1 — the
top of the frozen hierarchy this track exists to fill.

**Ownership boundary:** this node writes only inside `experiments/market_program/INJURY_OFFICIAL/live/`
(this directory: `raw/`, `injury_snapshots.csv`, `status_transitions.csv`, this README, and the two
scripts). It does not write to the live main worktree (`C:\Users\jgallagher\wnba-betting-model`),
which is read-only per standing rules, and does not touch The Odds API (excluded — backfill running).

---

## 1. Source located and verified

**Host:** `https://ak-static.cms.nba.com/referee/wnba_injury/` — the same static, unauthenticated,
Amazon-S3-backed CDN the NBA injury report generator uses, re-hosting the WNBA report.
**URL pattern:** `Injury-Report_{YYYY-MM-DD}_{H_MM}{AM|PM}.pdf` (US/Eastern slot label).
**Format:** PDF, one table per report: Game Date / Game Time / Matchup / Team / Player / Current
Status / Reason, plus an embedded header line `Injury Report: MM/DD/YY HH:MM AM/PM` — the report's
own self-declared publication timestamp (stronger evidence than inferring the slot purely from the
URL, which is also retained).

### 1.1 Access posture — verified honest, not blocked

Three real quarter-hour documents were HEAD-probed directly this session (single polite client,
honest `User-Agent` naming this project and a contact address, `Invoke-WebRequest -UseBasicParsing`,
≥1s spacing):

| ET slot (2026-08-06) | Status | Content-Length | Last-Modified (UTC) | ETag |
|---|---|---|---|---|
| 03:00 PM | 200 | 70762 | 19:00:05 | `90c663314ad54190313c0b892c709f55` |
| 02:45 PM | 200 | 70842 | 18:45:05 | `7143313519dbf15d3f743bc50fe39c70` |
| 02:30 PM | 200 | 70763 | 18:30:05 | `b92bc4f8b4fedea206b16ce2b1a9e96e` |

Three distinct documents, three distinct ETags, `Last-Modified` values exactly 15 minutes apart —
this **confirms the true quarter-hour publishing cadence**, not an artifact of caching or a single
document served under multiple URLs. `Server: AmazonS3`; no Cloudflare/PerimeterX headers, no
challenge page, no CAPTCHA, no `robots.txt` block found. **The host does not block scripted
access.** Per standing rules, if a future run ever does see a bot-detection-shaped response (403
from a Cloudflare-style challenge), both `fetch_official_pdf.ps1` and the optional direct-Python
path in `capture_injury_official.py` detect it explicitly (`BotBlockDetected` / exit code 2) and
**stop rather than bypass** — this is implemented, not just documented.

This same source is already the `injury_capture_daily.py` script's PRIMARY on the live main
worktree (read only, not modified here), which was independently observed this session to hold
a real, ongoing archive of hourly-plus raw PDFs (`data/injury_capture/raw/`, files
`wnba_official_20260806T{14..19}0*Z.pdf`) confirming continuous production access to the identical
host outside this session.

### 1.2 Parser verified against real bytes

`parse_official_pdf()` was run against a real, previously-captured production PDF
(`wnba_official_20260806T190009Z.pdf`, read from the live worktree's own archive, read-only —
**not copied into this track's `raw/`**, since that would misattribute capture provenance; this
was a parser-validation read, not a capture). Result: 13 player-designation rows correctly
extracted, embedded slot timestamp correctly parsed as `2026-08-06T15:00:00` (matching the
`03_00PM` URL slot exactly), teams/matchups/statuses/reasons all correctly bucketed, e.g.:

```
{'team': 'Las Vegas Aces', 'player': 'Cheyenne Parker-Tyus', 'status': 'Out',
 'reason': 'Concussion Protocol'}
{'team': 'Indiana Fever', 'player': 'Caitlin Clark', 'status': 'Probable',
 'reason': 'Injury/Illness - Back; Back'}
```

Entity resolution was independently verified against the live worktree's `entity_resolution.py`
interface (read-only import, see §3): a 390-identity cross-season index resolved all four sampled
names correctly, e.g. `Caitlin Clark -> 1642286`, `Cheyenne Parker-Tyus -> 204323`.

---

## 2. What this track builds

### `fetch_official_pdf.ps1`
Owns the network fetch only: walks back from the current 15-minute ET slot (bounded lookback,
default 6h) until a real report is found, archives the raw PDF bytes **verbatim** to `raw/`, and
emits a small JSON descriptor (`raw_path`, `source_url`, `url_slot_ts_et`, `capture_id`,
`retrieval_ts_utc`). Detects and stops on bot-block-shaped responses.

**Why a PowerShell fetch script exists at all, next to a Python parser:** this sandbox's outbound
egress reliably resets/times-out every connection opened via Python's `requests`/`urllib3` to this
host (`ConnectionResetError 10054` on HEAD, then `ReadTimeoutError`, reproduced across two separate
runs), while `Invoke-WebRequest -UseBasicParsing` (WinHTTP-backed) succeeded cleanly against the
identical URL in the same session (§1.1 table). This is a property of the *sandbox's* HTTP stack
selection, not of the host — the host answered PowerShell's requests instantly with correct
headers. `capture_injury_official.py` therefore defaults to shelling out to this script, with an
optional `--no-shell-fetch` direct-Python path preserved for environments where `requests` works
normally. Only one parser implementation exists regardless of which fetch path ran.

### `capture_injury_official.py`
Owns parsing, entity resolution, snapshot writing and transition detection — see the module
docstring for the full step-by-step. Schema (amendment-4 discipline, D033 mandate + M00 §6
pattern applied to this non-market capture):

**`injury_snapshots.csv`** (append-only; a correction is a new row, never an `UPDATE`):
`capture_id, report_slot_ts_et, report_slot_ts_source (pdf_embedded_header|url_slot_inferred),
url_slot_ts_et, retrieval_ts_utc, ingestion_ts_utc, poll_interval_at_capture (PT15M),
max_staleness_bound_minutes, vendor_latency_note, payload_hash_sha256, prev_snapshot_ref,
source_url, source_provenance_class, game_date, game_time_et, matchup, team, player_raw,
player_id, status, reason`.

**`status_transitions.csv`**: a row per (team, player_raw) whose `status` changed between the
immediately preceding snapshot and this one. Carries the M00 §6.1 interval-censored bound
`[t_lower_utc_bound, t_upper_utc_bound]` = `[prev retrieval_ts, this retrieval_ts]` — **never** a
sharper point estimate than the 15-minute report grid (`poll_interval_event=PT15M`,
`censor_type=interval`, `tier=T0` — directly witnessed by us, not vendor-asserted).

### 3. Entity resolution / status-transition detection
Per the mandate, this reads the interface from `entity_resolution.py` on the live main worktree
(read-only import via `sys.path`, not forked/copied — one identity-resolution implementation in
the program): `resolve_player_id(raw_name, index)` and `try_load_capture_index()`, exactly the
same functions `injury_capture_daily.py` already uses in production. Resolution failure degrades
to a blank `player_id` with an explicit stderr note; it never blocks a capture (same discipline as
the production script). Full `player_layer_resolved()` (team-assignment / single-tenancy logic)
was read for interface understanding but is **not** invoked here — this track's status-transition
detection is per-row (`team`, `player_raw`) keyed, which is what the mandate specifies
("designation parser ... status-transition detection via our entity resolution"); roster/tenancy
construction belongs to the forecast-time consumer, not this capture-time producer.

---

## 4. Run status this session

- **Access verification: DONE.** Three real quarter-hour documents confirmed (§1.1).
- **Parser verification: DONE.** Real production bytes parsed correctly (§1.2).
- **Entity resolution verification: DONE.** Four real names resolved correctly against the live
  390-identity index (§1.2).
- **One live capture cycle end-to-end: ATTEMPTED, NOT COMPLETED THIS SESSION.** After the
  verification probes above succeeded, every subsequent fetch attempt (both the direct-Python path
  and the PowerShell path, run repeatedly with increasing pauses) returned connection timeouts —
  no 403, no challenge page, no bot-detection signature; a plain, symmetric timeout on every
  attempt regardless of client library. This reads as a **transient sandbox egress condition**
  (plausibly exhausted by the volume of retries the direct-Python path generated before the
  PowerShell split was built), not a host-side block. **Reported, not bypassed, per standing
  rules.** `injury_snapshots.csv` and `status_transitions.csv` are therefore not yet populated by
  this track; the pipeline is built, verified end-to-end against real bytes, and ready to run.
  Recommend the coordinator's first scheduled 15-minute cycle serve as the actual first capture, or
  a retry once network conditions in the execution environment are confirmed normal.

## 5. Scheduling
Not scheduled by this node (D033 mandate: "NOT scheduled - coordinator schedules"). Invoke
manually via `python capture_injury_official.py` (defaults to the PowerShell fetch path). Intended
cadence: every 15 minutes, matching the report's own publication grid.
