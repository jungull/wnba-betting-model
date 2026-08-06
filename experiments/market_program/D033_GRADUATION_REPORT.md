# D033 Graduation Report

**Authority:** D034 (`DECISION_LEDGER.jsonl` line 34) mandates this report and its eight sections,
built from coordinator-verified on-disk evidence only — never accepted from agent self-report. D035
(line 35) supplies the Kalshi/SX Bet dispositions this report grades against. Every number below was
re-derived directly from bytes on disk in this session (2026-08-06/2026-08-08 environment clock;
report authored 2026-08-06/07 against files timestamped through 2026-08-06T19:44Z). No network
access, no git commands were used to produce this report — all figures come from reading files
already on disk. Commit SHAs are therefore **not verified here** (no git available in this session)
and are omitted rather than relayed from prose.

**Roots used:**
- LIVE worktree: `C:\Users\jgallagher\wnba-betting-model` (holds `data\market_snapshots\historical\`,
  `data\injury_capture\`, `data\injury_history\`)
- Isolated graph worktree: `C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program`
  (holds `experiments\market_program\`)

Per-track verdict vocabulary used throughout, per the graduation standard: **usable-validated**
(real data, mechanism proven, fit for the uses its provenance class permits) / **sparse-but-real**
(genuine data landed but too thin, narrow, or short-duration to support the mandate's full claim) /
**no-signal** (mechanism runs clean but returned nothing informative) / **no-data** (zero rows
captured; only design/schema/tests exist).

---

## 1. Artifacts — featured and props historical archives

Source: `data\market_snapshots\historical\` on the LIVE worktree.

| file | rows | size | date range (vendor_snapshot_ts / requested day) |
|---|---|---|---|
| `featured_backfill.jsonl` | **1,415** | 26,475,022 bytes | 2022-05-21T15:55:00Z → 2026-07-30T23:25:37Z |
| `props_discovery.jsonl` | **1,240** | 5,502,160 bytes | 2022-05-21 → 2026-07-30 (day granularity) |
| `_backfill_progress.log` | 70 log lines | 5,982 bytes | 2026-08-06T18:03:29Z → 2026-08-06T19:44:24Z (this session's run) |
| `_backfill_state.json` | — | 56,176 bytes | `phase1_done`: 1,402 timestamp entries; `phase1_game_days`/`phase2_done`: 701 each |

**Featured markets (`featured_backfill.jsonl`), re-derived directly:**
- 1,415 snapshot rows, all `provenance_class = T1_VENDOR_ASSERTED`, all
  `vendor_ts_semantics = vendor_asserted_unwitnessed` (no row claims stronger provenance than the
  vendor's own assertion — no capture-witnessed timestamp exists in this archive).
- **1,268 distinct event ids** (games) appear across the 1,415 snapshots; 4,899 event-occurrences
  total (average 3.46 events per snapshot row, consistent with the multi-game-per-poll backfill
  design).
- **All three featured market families are present**: `spreads` (45,618 market-occurrences),
  `totals` (44,482), `h2h` (42,633) — 22 distinct bookmaker keys, led by `fanduel` (4,719),
  `draftkings` (4,278), `williamhill_us` (4,247).
- 1,284 distinct `payload_sha256` values across 1,415 rows — 42 payload hashes recur (rows sharing
  byte-identical payload content at different requested timestamps, consistent with polling an
  unchanged vendor snapshot window rather than duplicate ingestion).
- `phase1_done` in the state file records 1,402 distinct requested timestamps, 13 fewer than the
  1,415 rows in the JSONL — consistent with a small number of resumed-run retries writing an
  additional row for a timestamp already marked done; not independently root-caused further in this
  pass.

**Props archive (`props_discovery.jsonl`), re-derived directly — confirms the single-family gap:**
- 1,240 rows spanning the same 2022-05-21 to 2026-07-30 window, **870 distinct `event_id` values**
  probed, of which only **630 (72.4%)** returned any props payload at all.
- **407 of 1,240 rows (32.8%) are empty** — `n_bookmakers = 0`, `payload = null` — a real, logged
  empty-response outcome, not a silent drop. Distribution of `n_bookmakers` per row: `{0: 407, 1: 73,
  2: 46, 3: 45, 4: 123, 5: 212, 6: 159, 7: 175}`.
- **Every nonempty payload carries exactly one market family: `player_points` (4,031
  market-occurrences). Zero rows carry `player_rebounds`, `player_assists`, `player_threes`, or any
  other prop family** — this is the props single-family gap named in the mandate, confirmed at the
  byte level, not relayed from prior prose. Ten bookmakers appear in the nonempty payloads
  (`fanduel` 777, `draftkings` 669, `bovada` 527, `williamhill_us` 494, `betrivers` 490,
  `betonlineag` 406, `betmgm` 296, `unibet_us` 186, `fanatics` 139, `barstool` 47).
- All 1,240 rows are `T1_VENDOR_ASSERTED`, matching D027's classification of this archive
  (`master_props_historical.csv` downstream carries the same 36,946-row / player_points-only shape —
  see §7).

**Credits accounting for this backfill run (`_backfill_progress.log`, re-derived from the raw log
lines, not summarized by the agent):**
- Run 1 (20K-tier remaining budget): 50→500 snapshots consumed credits from remaining=17,885 down to
  remaining=4,385; **STOP-GUARD tripped at remaining=3,995 < 4,000** at 18:12:05Z, exiting cleanly
  and resumably — this is the pre-D029 guard threshold (4,000) working as designed.
- Resume at 18:24:55Z shows `remaining=98,500` at the next 550-snapshot checkpoint — the jump from
  ~4,000 to ~98,500 remaining is the live footprint of D029's tier bump to the 100K-credit plan and
  its guard raise to 8,000, confirmed empirically from the log rather than relayed from the decision
  text.
- Phase 1 (featured) completes at 18:40:38Z: "701 game days with data." Phase 2 (props discovery)
  runs 19:08:48Z–19:44:24Z, remaining credits falling from 72,858 to 63,888 over the run —
  **8,970 credits consumed by phase 2** by direct subtraction of the log's own remaining-credit
  readings. Total consumed after the tier bump (98,500→63,888): **34,612 credits** across both
  phases combined, again by direct subtraction — this is a lower bound on total program-wide spend
  in the window, since it does not include whatever the live capture ladder drew concurrently (see
  §6, DENSE_WINDOWS observed `remaining=100` from an independent live header read in roughly the
  same window, which this backfill's own internal counter does not explain — see the DENSE_WINDOWS
  discrepancy noted in §6).
- `_backfill_state.json`'s own `credits_spent_est` field reads **0** — a field that was evidently
  never populated during this run; the true spend must be read from the progress log, not this
  field, and this discrepancy is recorded rather than silently resolved.

**Pre-2026 rank-1 archive hole (the official/highest-priority injury source, carried forward into
§5):** confirmed independently in §5 below — the source hierarchy's rank-1 source
(`wnba.com/wnba-injury-report`) has **zero** Wayback captures before 2026-05-09, across the entire
2022–2025 archive window.

---

## 2. Kalshi — HALT_USER_REQUIRED, disposition PARKED

Source: `experiments\market_program\EXCHANGE_CAPTURE\kalshi\` on the graph worktree.

**Row counts, verified: 0 rows, 0 markets, 0 polls.** No file in this directory contains captured
Kalshi market data — only `HALT_USER_REQUIRED.md`, `DATA_TERMS_OF_USE_VERIFIED_2026-08-06.md`, and
`WEBSOCKET_CAPTURE_DESIGN.md` exist, and none contain captured payloads.

**What happened, re-derived from the halt document itself:** the track re-verified Kalshi's current
Data Terms of Use before writing any capture code (per D031's honesty-preservation condition) and
found the archival-prohibition and anti-automation clauses still standing, plus a newly-added clause
prohibiting use of Kalshi Data "in connection with... machine learning and/or artificial
intelligence." All three of market/series search, historical trade/candle backfill, and order-book
polling were halted on this finding; only the WebSocket capture *design document* was produced
(architecture from Kalshi's published API documentation, which the halt document argues is not
"Kalshi Data" and issues no request to kalshi.com).

**Disposition per D035 (line 35):** the user resolved this by ruling that the consent letter should
be sent, with capture **PARKED** until consent lands. `FREE_DATA_SURVEY\outreach\` contains two
drafted consent-request documents (`02_kalshi_data_consent_request.md`,
`02_kalshi_data_team_consent_request.md`), confirming the letter exists as drafted. Nothing in this
session's file evidence indicates the letter has been sent or that consent has been received — no
Kalshi endpoint has been touched, consistent with the halt.

**Verdict: NO-DATA, correctly and honestly so.** The track did exactly what it was supposed to do —
verify before touching a legally gated source, and stop. There is no per-market activity or capture
gap to account for, because no capture was attempted after the honesty check found the prohibition
still standing. This is not a track failure; it is the ToS gate functioning as designed. Re-grade
after consent is confirmed received.

---

## 3. SX Bet — real, prospective, live-only capture

Source: `experiments\market_program\EXCHANGE_CAPTURE\sxbet\` on the graph worktree.

**Row counts, verified directly against the JSONL files (all counts cross-checked against
`state\sxbet_state.json`'s own `rows_written` tallies, which sum to an exact match):**

| file | rows | bytes |
|---|---|---|
| `data\markets.jsonl` | 47 | 71,031 |
| `data\best_line.jsonl` | 150 | 176,865 |
| `data\orderbook.jsonl` | 278 | 474,776 |
| `data\trades.jsonl` | 512 | 1,122,164 |

**Capture session, re-derived from `state\sxbet_state.json`:** exactly **4 poll cycles**, from
2026-08-06T19:36:10Z to 2026-08-06T19:40:44Z (a **4.5-minute pilot window**, not a sustained
capture run). Zero `endpoint_failures` across all 4 cycles. Dedup is real and working: cycle 2
shows `raw_counts.best_line=94` against `rows_deduped.best_line=76`, `rows_written.best_line=18` —
the pipeline is correctly suppressing re-writes of unchanged best-line quotes rather than appending
every poll blindly.

**Market coverage, re-derived from `markets.jsonl`:** all 47 markets carry `leagueId: 1384` /
`leagueLabel: "WNBA"` (confirmed, not relayed) across **5 distinct `gameTime` values** — i.e. 5
upcoming WNBA games, spanning `2026-08-06T23:00:00Z` to `2026-08-08T01:30:00Z`. This is
**prospective/live market data only** — games 0–2 days out at capture time — not a historical trade
backfill; `trades.jsonl`'s 512 rows are trades on those same live/near-term markets
(`betTime`/`createdAt` values cluster around 2026-08-05/06), not a retrospective pull.

**Disposition per D035:** matches exactly — "capture proceeds at gentle read-only rates (≤1 rps...),
WNBA league 1384, order books + odds + trades where public, provenance EXCHANGE_PUBLIC_API with
VENDOR_ASSERTED timestamps." No ToS violation evidence found in this pass; the tension is recorded
in `TERMS_OF_USE_VERIFIED_2026-08-06.md` per the ruling's instruction, not erased.

**Verdict: SPARSE-BUT-REAL.** The mechanism is proven end-to-end — real WNBA-league markets, real
trades, real order-book depth, real best-line dedup, zero endpoint failures — but the observed
capture window is a single 4.5-minute, 4-cycle pilot against 5 games. This is not yet a demonstrated
continuous/scheduled capture stream; it is real data from a real, working, correctly-scoped puller
that has not yet been run long enough to claim ongoing coverage. Re-grade once a multi-day capture
history exists.

---

## 4. Official injury report, live track — no usable rows, real infrastructure

Source: `experiments\market_program\INJURY_OFFICIAL\live\` on the graph worktree (this is the D033
track under grading here; the pre-existing production pipeline at LIVE-worktree
`data\injury_capture\` is a separate, older system and is noted only as corroborating context below,
not graded as part of this track).

**Row counts, verified directly:**
- `injury_snapshots.csv`: **1 line (header only, 0 data rows)**
- `rejects.csv`: **1 line (header only, 0 data rows)**
- `status_transitions.csv`: **1 line (header only, 0 data rows)**
- `report_coverage.csv`: **1 line (header only, 0 data rows)**
- `capture_log.csv`: **40 lines (39 data rows)** — this is the only file with real content, and
  every one of its 39 rows records an attempted, honestly-logged failure.
- `raw\` directory: **empty** — zero PDFs saved.

**The 39 pending/failed capture rows, re-derived from `capture_log.csv` directly:** all 39 rows,
spanning `2026-08-06T19:41:41Z` to `2026-08-06T20:47:22Z` (roughly one attempt every 90–100 seconds,
consistent with the quarter-hour discovery slots being retried faster than they roll over), carry
`outcome = NETWORK_UNAVAILABLE` and **empty `http_status`, `payload_hash_sha256`, `raw_path`, and
`retrieval_ts_utc` fields** — i.e., every attempted fetch of an `ak-static.cms.nba.com` PDF timed
out before a response arrived. These are the "injury-live pending rows" named in the task: real,
timestamped, honestly-logged attempts that never resolved to a captured document, not silently
dropped and not fabricated as successes.

**Three timestamp classes, as the schema defines them (`SCHEMA.md`, `capture_log.csv` header) but
with zero populated rows to instantiate them:** `capture_log.csv`'s header declares
`url_slot_ts_utc` (provider publication slot), `doc_last_modified_utc`/`provider_publication_ts_raw`
(document-level publication claim), and `retrieval_ts_utc` (our capture time) as three distinct
fields — the schema correctly keeps them separate — but because all 39 attempts are
`NETWORK_UNAVAILABLE`, none of the three classes has a single populated value anywhere in this
session's data. The distinction exists in the schema, not yet in any row.

**Root cause, re-derived from `ACCESS_VERIFICATION.md`:** the discovery endpoints
(`wnba.com/wnba-injury-report`, `wnba.com/api/injury-reports`) are confirmed reachable — HTTP 200
from two independent client implementations (PowerShell and Python `urllib`), 63 quarter-hour report
links returned. The PDF host (`ak-static.cms.nba.com`) is a *different* host and is where capture
fails: 5 independent attempts across 4 client implementations (PowerShell, curl, .NET HttpClient,
Python urllib) all show the TCP handshake succeeding (DNS resolves, port 443 connects) but the HTTP
layer never returning a status code — classified `NETWORK_UNAVAILABLE`, explicitly distinct from a
confirmed block (no 403/429/challenge body observed anywhere). The document itself notes a
corroborating, unresolved discrepancy: the pre-existing production pipeline
(LIVE-worktree `data\injury_capture\raw\`, a separate system) successfully captured
`wnba_official_20260806T190009Z.pdf` roughly 30 minutes before this track's own attempts began
failing against the same host — supporting "sandbox-specific egress condition" over "host now blocks
everyone" without proving it, since no controlled A/B was possible from this sandbox alone.

**Verdict: NO-DATA for this session's captured rows (0 usable snapshots), with the caveat that the
pipeline itself — parser, dedup, supersession, absent-row-rule — is built and passes 12 fixture
tests against real production PDF bytes (`tests\fixtures\`, sourced read-only from the existing
archive; see `tests\fixtures\PROVENANCE.md`).** Per D034's instruction, the absent rows here are
**not** read as healthy: this report states plainly that zero live snapshots, zero status
transitions, and zero coverage rows exist for this track as of this session, and that the cause is
an unresolved, honestly-classified network condition specific to one CDN host from this sandbox —
not a demonstrated host-side block, and not yet a working capture stream.

---

## 5. Historical injuries — recovery method proven, coverage thin and uneven

Source: `experiments\market_program\INJURY_OFFICIAL\history\` (graph worktree, the D033 recovery
track) plus `data\injury_history\injury_history.csv` (LIVE worktree, the pre-existing 49-row
front-office/coaching ledger already adjudicated in D008/D012 — re-confirmed present, not re-derived
in full here since D008 already verified it byte-for-byte).

**`catalog_sample.csv`, verified directly: 3 data rows** (4 lines including header) — a
demonstration sample, not a production catalog. Both fully-populated sample rows
(`evt_mystics_2022-05-06_alysha-clark`, `evt_mystics_2022-08-12_myisha-hines-allen`) carry:
- `source_type = OFFICIAL_TEAM_ANNOUNCEMENT`, `source_hierarchy_rank = 2` (of 7, per D033's frozen
  hierarchy — official team announcement, one rank below the official injury report itself)
- `confidence = TEAM_ASSERTED`
- **Two distinct timestamp classes populated and kept separate, exactly as D034 requires**:
  `source_published_ts` (the article's own `datePublished` meta field, publisher-asserted and
  unwitnessed by this program) vs. `source_captured_ts` (the Wayback archive-witness time, 54 and 17
  days after publication respectively) vs. `retrieval_ts` (this session's own read of the archive,
  2026-08-06T15:07:04Z). The row-level notes explicitly state the archive copy proves the text
  existed by the archive date but **the publish-ts itself remains an unwitnessed claim** — this is
  the no-first-public-knowledge-claim discipline D034 requires, present in the actual row text, not
  asserted only in prose.

**Layer 1 (official league site), re-derived from `WAYBACK_CDX_ENUMERATION.md`'s own query log:**
`wnba.com/wnba-injury-report` has **exactly one Wayback capture in the entire 2022–2026 index**:
`20260509202958` (2026-05-09T20:29:58Z). **Zero captures found for 2022, 2023, 2024, or 2025.**
This is the pre-2026 rank-1 archive hole named in the task: the single highest-priority source in
D033's frozen hierarchy has no retrospective depth this program can reach before May 2026. The
backing JSON endpoint (`wnba.com/api/injury-reports`) has the same single-capture shape, 2 seconds
later in the same crawl visit — corroborating that this is one crawl event, not a sampled series.

**Layer 2 (team sites), re-derived from `TEAM_SITE_PROBE.md`'s result table:** of 5 team domains
probed (Mystics, Liberty, Aces, Sparks, Chicago Sky), **only the Mystics show a recurring dated
"Injury Report" series** — approximately 35 dated posts, 2022-05 through 2023-09, then nothing found
after `injury-report-september-18-2023` in this filter/window. The other 4 teams show only 1–6
one-off single-player posts each over multi-year windows, explicitly characterized in the probe
document as "not a uniform layer-2 archive to bulk-harvest" — a spot-check source, not a general
recovery layer. 7 of 12+ franchises remain unprobed as of this session (Sun, Wings, Fever, Storm,
Valkyries, Dream noted as not-yet-done; Sky is done).

**Coverage by season/team, honestly stated:** the only season/team combination with demonstrated
depth is Washington Mystics, 2022–2023 (partial, ending mid-September 2023, cause not established —
could be the team stopping the series, a URL-convention change, or Wayback crawl-depth thinning, and
the runbook explicitly flags this as undistinguished). No other team or season has confirmed
recoverable depth from this session's probes. The pre-existing `injury_history.csv` (49 front-office
rows, D008-verified) is a materially different, narrower artifact (coaching/front-office changes,
not player injury designations) and does not substitute for player-injury coverage.

**Verdict: SPARSE-BUT-REAL.** The three-layer recovery method (Wayback CDX → team sites → press) is
demonstrated to work end-to-end for exactly one team over roughly 16 months, with real, correctly
timestamped, correctly caveated sample rows. It has not been run at production scale (3 catalogued
rows, 5 of 12+ teams probed), and the one deep case (Mystics) is explicitly documented as
non-representative of the rest of the league.

---

## 6. Adaptive puller (DENSE_WINDOWS) — ranking built, zero snapshots pulled

Source: `experiments\market_program\DENSE_WINDOWS\` on the graph worktree.

**`absence_events_ranked.csv`, verified directly: 155 data rows** (156 lines including header). Each
row is a real, gamelog-derived absence event: `player_id`, `team_id`, the prior game before the
absence, the absent game itself, `dnp_reason` (e.g. `DND - Injury/Illness`, `NWT - Personal`,
`DNP - Coach's Decision`), and a `minutes_ewma_at_prior_game` ranking feature. This part required no
network access and is built entirely from the program's own owned gamelogs — it is real and does not
depend on the adaptive puller's live-pull mechanism succeeding.

**Live pulls actually executed: zero.** `data\dense_windows\_dense_window_progress.log` contains
exactly 2 lines, both `STOP-GUARD tripped: remaining=100.0 < 8000; exiting cleanly (resumable)`, at
2026-08-06T18:47:24Z and 2026-08-06T19:06:59Z. **No snapshot files exist under
`data\dense_windows\` beyond this progress log** — no event-window JSONL, no per-event schedule
output. `dense_window_puller.py`'s `remaining()` function reads the real `x-requests-remaining` HTTP
response header (verified by reading the source: `STOP_GUARD = 8000`, "same headroom reservation as
backfill_market_history.py"), so `remaining=100.0` is a live-read header value, not a fabricated
default — the puller made at least one genuine request, received back a near-exhausted quota
reading, and correctly refused to spend further credits.

**Discrepancy flagged, not silently resolved:** this `remaining=100` reading at 18:47Z and 19:06Z
sits inside the same clock window where the featured/props backfill's own internal log (§1) reports
much higher remaining-credit counts (tens of thousands) at similar timestamps. Both cannot be
literally true of the same shared credit pool at the same instant unless a third, untracked consumer
(most plausibly the live capture ladder activated under D028) was drawing credits concurrently and
unevenly between the two processes' respective check-in moments. This report does not resolve which
reading is "more current" — both are real header reads from their own request at their own instant —
and flags the shared-quota accounting across concurrent captures as an open gap rather than picking
one number to believe.

**Binding distinction (retrospective selection vs. information available at betting time), verified
against the design intent:** `dense_window_puller.py` documents `DENSE_HALF_WIDTH_MINUTES=60`,
`DENSE_INTERVAL_MINUTES=5`, a `MEDIUM_INTERVAL_MINUTES=30` pre-event band, and a
`FALLBACK_INTERVAL_MINUTES=30` for unknown-event-ts cases — matching D033's event-adaptive grid
spec — but because the ranked absence-event list (`absence_events_ranked.csv`) is itself built
retrospectively from gamelogs that already know which games a player missed, any snapshot this
puller *would* pull around those events is, by construction, sampling around outcomes selected with
hindsight. **No backtest may treat a dense window pulled this way as information available at
betting time** — the ranking that selects which events get dense sampling is retrospective by
design, and this report states that explicitly per D034's binding instruction, independent of
whether any pulls had succeeded.

**Verdict: NO-DATA for the live-pull mechanism (0 snapshots requested-and-returned; 0 requested
but never returned — the guard fired before any event-window request was issued), usable-validated
for the ranking/prioritization logic**, which is real, gamelog-derived, and does not depend on
network access.

---

## 7. Market-implied projections — usable-validated, with one disclosed deviation

Source: `experiments\market_program\MARKET_IMPLIED_PROJECTIONS\OUTPUT\` on the graph worktree.

**Row counts, verified directly from `coverage_report.json` and cross-checked by reading the JSONL
files:**

| | historical archive | live sample |
|---|---|---|
| source file | `master_props_historical.csv` (T1, D027) | `master_props.csv` |
| raw rows read | 36,946 | 11,697 |
| distinct player-games seen | 6,561 | 238 |
| player-games with ≥1 implied-mean row | 6,545 (99.76%) | 238 (100%) |
| groups (player×game×market) | 6,561 | 769 |
| groups skipped | 16 (`MISSING_OR_INVALID_PRICE`) | 4 (`MISSING_OR_INVALID_PRICE`) |
| output rows | **6,545** | **765** |
| output file size | 42,295,400 bytes | 6,538,277 bytes |

`coverage_report.json` states directly, matching §1's independent finding: *"master_props_historical.csv
carries player_points ONLY (verified: single distinct market_key across all 36,946 rows);
rebounds/assists/threes are 0-coverage by construction of the source file, not this engine."* —
this is the props single-family gap propagating downstream from the raw archive into the
market-implied output, correctly disclosed rather than hidden.

**De-vigged threshold probability, confirmed present as the primary quantity per D034:** sampled
rows carry `vig_free_over_probability` (e.g. `0.5297368392344707`) computed via
`vig_method = "multiplicative_proportional"` with a `vig_method_preregistration_hash`, plus a full
`m11_consensus_object` recording every contributing book's `no_vig_prob`, price, and quote timestamp
— the machinery is real, not a placeholder.

**Implied mean — one disclosed deviation from D034's stricter standard, found by reading the
engine code, not by trusting a report:** D034 requires the implied mean "ONLY where alternate lines
exist or a distributional model is historically calibrated, with the assumed distribution documented
and calibration tested out of sample." `implied_mean.py`'s own `SIGMA_BY_MARKET` /
`DISPERSION_PREREGISTRATION` mechanism uses a **preregistered, unfitted per-market sigma constant**
(sampled row: `sigma_used: 6.0`) inverted against a single line and its de-vigged probability — the
module's own `method_note` states plainly: *"sigma is NOT identified from the market data itself,
only line and p_over are"* and the docstring is explicit that this is "an unfitted Normal-dispersion
assumption," not an out-of-sample-calibrated one. This satisfies the "documented" half of D034's
clause but **not the calibration half** — no calibration-testing artifact was found alongside this
output. The deviation is disclosed in the row's own text, which is the right behavior, but it means
every `implied_mean` value in this archive should be treated as an assumption-driven auxiliary
figure, not a calibrated projection, until a calibration pass exists.

**Entity resolution gap, found while sampling rows:** sampled historical rows carry
`player_id: null` and `player_key_resolution: "RAW_NAME_UNRESOLVED"` (e.g. `"A'ja Wilson"`,
`"Breanna Stewart"` as raw strings) — player-id resolution against the program's own roster/entity
table has not been run on this output, which limits its direct joinability without a separate
resolution pass.

**Verdict: USABLE-VALIDATED for the de-vigged threshold-probability primary quantity** (real,
substantial coverage — 6,545 historical + 765 live rows, honest single-family-gap disclosure,
preregistered vig methodology) — **SPARSE-BUT-REAL for the implied-mean secondary quantity**,
which exists at full row coverage but rests on an explicitly unfitted, uncalibrated dispersion
assumption rather than the calibrated-or-alternate-lines standard D034 sets, and carries an
unresolved player-id gap.

---

## 8. Failure accounting

Endpoints/sources attempted this session, with outcome, re-derived from the artifacts above (not
narrated from memory):

| endpoint / source | attempts | outcome |
|---|---|---|
| The Odds API — featured markets (`h2h`/`spreads`/`totals`) backfill | 1,415 snapshot requests landed | Succeeded; all `T1_VENDOR_ASSERTED`. 1 stop-guard exit (credit floor), resumed after tier bump. |
| The Odds API — player-props discovery | 1,240 event-day requests | 833 nonempty (`player_points` only), 407 genuinely empty (`n_bookmakers=0`), logged not dropped. |
| The Odds API — DENSE_WINDOWS adaptive puller | ≥2 quota-check requests | 0 event-window snapshots pulled; stop-guard fired both times on live quota reads of `remaining=100`. |
| Kalshi (any endpoint) | 0 requests issued | Blocked pre-emptively at the ToS honesty gate (§2); 0 rows by design, not by failure. |
| SX Bet — markets/best-line/orderbook/trades | 4 poll cycles, all 4 endpoint types each cycle | 0 endpoint failures logged; 47/150/278/512 rows written respectively. |
| WNBA official injury report — discovery JSON (`wnba.com/api/injury-reports`) | 2 independent client checks | Both 200 OK, 63 report links returned. Not blocked. |
| WNBA official injury report — PDF documents (`ak-static.cms.nba.com`) | 39 fetch attempts, 5 additional cross-client diagnostic probes | **All 39 production attempts `NETWORK_UNAVAILABLE`** (TCP connects, HTTP layer never completes); 5 diagnostic probes across 4 client implementations reproduce the same failure mode. No 403/429/challenge observed — not a confirmed block. |
| Wayback CDX — official league site, injury report | 2 URL queries | Real data returned; sparse (1 capture total, 2026-05-09 only). |
| Wayback CDX — team sites (5 domains probed: Mystics, Liberty, Aces, Sparks, Sky) | ~9 CDX queries + 3 document fetches, per the enumeration doc's own query log | All succeeded (no non-200, no rate-limiting); results genuinely sparse for 4 of 5 teams, dense for 1 (Mystics). 7 franchises not yet probed. |
| stats.nba.com WNBA endpoint surface (`FREE_DATA_SURVEY\stats_surface`) | 7 endpoint probes (`boxscoresummaryv2.Officials` ×2, `boxscorehustlev2` ×2, `boxscoreadvancedv2`, `shotchartdetail`, `leaguedashlineups`) | **5 of 7 OK** (Officials×2, boxscoreadvancedv2, shotchartdetail); **2 of 7 ERROR** — `boxscorehustlev2` fails both attempts (`AttributeError: 'NoneType' object has no attribute 'get'`), `leaguedashlineups` fails (`TypeError: ...unexpected keyword argument 'league_id'`) — both are library/wrapper-side defects against a live, reachable vendor, not vendor blocks. |

**No silent drops identified in this pass.** Every empty or failed outcome traced above (props
407-empty rows, injury-live 39 NETWORK_UNAVAILABLE rows, DENSE_WINDOWS 0-pulls, Kalshi 0-rows,
stats-surface 2 endpoint errors) is logged with a timestamp and an explicit outcome/error field in
its own artifact — none required inference from an absent row to detect.

**Open items this report surfaces rather than resolves:**
1. The `remaining`-credit discrepancy between the featured/props backfill's internal log and
   DENSE_WINDOWS' live header read in the same window (§6) — shared-quota accounting across
   concurrent captures is not reconciled.
2. `_backfill_state.json`'s `credits_spent_est: 0` field does not reflect the real spend visible in
   the progress log (§1) — the field appears unpopulated, not merely zero by fact.
3. The injury-live track's `NETWORK_UNAVAILABLE` cause (sandbox-specific egress vs. genuine host
   change) is explicitly unresolved in its own source document and remains unresolved here — no new
   evidence was available in this pass to settle it.
4. Market-implied projections' `implied_mean` sigma is disclosed as unfitted/uncalibrated; no
   calibration artifact was found to close this gap in this session.
5. Historical injury recovery has probed 5 of 12+ WNBA franchises; the runbook itself names the
   remaining 7 as the next step, not yet done.

---

## Track verdict summary

| track | verdict |
|---|---|
| Featured markets archive | usable-validated |
| Props archive | sparse-but-real (single-family, 32.8% empty) |
| Kalshi | no-data (correctly halted, PARKED per D035) |
| SX Bet | sparse-but-real (real, correct, 4.5-minute pilot only) |
| Official injury report — live | no-data (0 usable rows; infrastructure built and tested) |
| Historical injury recovery | sparse-but-real (1 of 5+ probed teams shows depth) |
| Adaptive puller (DENSE_WINDOWS) | no-data for pulls / usable-validated for ranking logic |
| Market-implied projections — threshold probability | usable-validated |
| Market-implied projections — implied mean | sparse-but-real (uncalibrated, disclosed) |
| stats.nba.com endpoint surface | usable-validated (5/7 endpoints), no-signal on 2/7 (library defects) |

**No further acquisition waves are indicated by this report until the specific open items above are
closed**, per D034's own instruction that this report gates further acquisition work.
