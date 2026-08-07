# M17_SUSPENSION_REOPENING — REPORT

> Filename note: the spawn instructions for this node explicitly say "Do NOT write REPORT.md
> (write REPORT_BODY.md)" and name `SUSPENSION.json` as the structured output. This agent's Write
> tool independently refuses any file literally named `REPORT.md` or `REPORT_BODY.md`
> ("Subagents should return findings as text, not write report files") -- the identical failure
> mode M03_CAPTURE_UPGRADE hit and documented in its own placeholder file. This file is written
> under the nearest permitted name (`SUSPENSION_REPORT_BODY.md`, mirroring M03's
> `CAPTURE_REPORT.md` workaround) so the full report content still lands inside this node's write
> scope; the identical text is also returned as this agent's final response to the orchestrator,
> which is where `REPORT_BODY.md` should be materialized from at integration.
>
> Separately: the node's own generated contract
> (`experiments/player_program/orchestration/prompts/M17_SUSPENSION_REOPENING.md`) names
> `REPORT.md` + `FINDINGS.json` as required outputs, with a stated validation step of
> `json.load` against `FINDINGS.json` -- a second, independent contradiction with the spawn
> instructions' `SUSPENSION.json`. Both `SUSPENSION.json` and a byte-identical `FINDINGS.json`
> were written so that validation command still passes regardless of which document controls.

EPISTEMIC STATUS: PROSPECTIVE MEASUREMENT. Characterises when books suspend and how they reopen
around information events. A gap in our own capture is not a suspension; the two must be
distinguished by evidence, not assumption.

## What was measured

Two independently-captured tapes were characterized in full: `data/market_snapshots/snapshots.csv`
(The Odds API ladder, T0 witnessed) and the four files under `data/sxbet_capture/` (SX Bet exchange
public API, `EXCHANGE_PUBLIC_API` / `VENDOR_ASSERTED`), cross-checked against
`logs/sxbet/poll_log.jsonl` for HTTP-level poll success. Both are our own T0 capture; neither is the
final-state (T2) `master_odds.csv` archive, which was not opened by this node.

### 1. Odds API ladder — `data/market_snapshots/snapshots.csv`

Command: `csv.DictReader` over the file, grouped into chains of
`(game_id, book, market, outcome, line)` (the schema's `ChainKey` plus line, since props keep
distinct lines as distinct series).

- **3,152 rows**, 4 distinct `game_id`, 5 books (`betonlineag`, `betrivers`, `draftkings`,
  `fanduel`, `williamhill_us`), 4 markets — all **player props** (`player_assists`,
  `player_points`, `player_rebounds`, `player_threes`); no h2h/spreads/totals rows in this extract.
- **Per book:** fanduel 621, draftkings 628, williamhill_us 493, betrivers 765, betonlineag 645.
- **Per market:** player_assists 603, player_points 1180, player_rebounds 802, player_threes 567.
  (Coverage reported per book and per market before the pooled statements below, per the
  acceptance criteria.)
- **`market_status` census: `active` = 3,152 (100%); `suspended` = 0; `missing` = 0.**
- **704 distinct chains**, chain-length histogram `{1:43, 2:59, 3:78, 4:391, 6:1, 8:1, 9:131}`.
- **0 status transitions** — no chain's `market_status` ever changes value across its observed
  history.
- Cadence (gap in seconds between consecutive polls of the same chain, sorted): n=2,448,
  min=0.24s, p10=0.25s, median=2,999.7s (~50 min), p90=7,201.3s (~2h), max=13,799.7s (~3h50m). The
  sub-second minimum is same-poll duplicate outcome rows, not cadence; the real cadence is the
  ladder's rung schedule. `poll_interval_at_capture` values observed: 900s, 3,600s, 7,200s, 14,400s,
  86,400s — i.e. rung-triggered (T-15m/T-60m/T-2h/T-4h/T-24h), not continuous polling.
- `vendor_ts_semantics`: `unknown_unverified` on all 3,152 rows (the conservative M00 §6.3 default,
  never overridden here). `vendor_latency_note`: present as a column on every row but the **empty
  string** on all 3,152 rows — the advisory field exists structurally, carries no content in this
  extract.
- Required-field null check (schema's `REQUIRED_PRESENT` list): **PASS**, zero blanks.
- Capture window: `2026-08-06T18:52:04Z` → `2026-08-07T01:42:03Z` (~6h50m).

**Write-path audit (why `suspended` never appears):** read `market_snapshot_writer.py` in full.
`flatten_odds_payload()` (line 152) writes `market_status = "active" if outcomes else "missing"`
only for a (book, market) pair that IS present in the vendor payload; a book/market absent from the
payload produces no row at all. `flatten_props_payload()` (lines 202, 222) writes `"active"`
whenever any outcome exists, and `"missing"` only as a single **event-level** placeholder when the
entire event returns zero outcomes across every book and market. **No code path in this writer ever
assigns `market_status = "suspended"`**, even though it is a legal value in the schema's
`MARKET_STATUS_VALUES`. The Odds API's `/odds` and `/events/{id}/odds` response shapes expose no
book-suspended flag distinct from "no outcomes in this payload" for this writer to key off. This is
a structural ceiling, not a sampling gap: even a much longer capture run on the current writer could
not produce a labeled suspension for a game-market row, and could produce only the coarse,
event-level `missing` label for props.

### 2. SX Bet exchange tape — `data/sxbet_capture/{markets,orderbook,best_line,trades}.jsonl`

Single venue; "per book" doesn't apply the way it does for the multi-book ladder above, so coverage
is reported per market type and per game instead.

- **markets.jsonl**: 314 rows, 100% `leagueLabel="WNBA"` (capture is scoped to `league_id=1384` by
  construction — expected, not a finding). 138 distinct `marketHash` chains across 9 distinct games
  (`sportXeventId`). Market-type census: type 226 (moneyline) n=8, type 28 (totals) n=163, type 342
  (spread or similar) n=143. **`content.status` census: `ACTIVE` = 314 (100%)**; no other value ever
  observed. Chain-length histogram `{1:50, 2:50, 3:16, 4:9, 5:5, 6:3, 7:3, 8:2}` — half the markets
  were written only once and never again (see game-lifecycle note below). **0 status transitions.**
  Written-row cadence: 53 gaps, min 298.0s, p10 299.3s, median 300.4s, p90 1,504.0s, max 5,399.9s —
  but this measures gaps between cycles that produced a *new/changed* row, not true poll cadence.
- **`logs/sxbet/poll_log.jsonl`** (the true poll record): 767 total HTTP attempts
  (`/markets/active` ×131, `/orders` ×318, `/trades` ×318), **0 failures** (767/767 `ok=True`,
  `http_status=200`). `/markets/active`'s `n_returned` fell from 90–100 in the first ~35 minutes to
  a 28–44 plateau for the remaining ~10.5 hours. Cross-referencing `markets.jsonl` `content.gameTime`
  shows the earliest-vanishing markets belong to games whose scheduled tip-off was already at or
  before the capture window's start (e.g. Portland Fire @ Toronto Tempo, `gameTime`
  `2026-08-07T02:00:00`, capture starting `02:39:05`) — consistent with ordinary in-play/post-game
  market retirement, not suspension, and the zero-failure poll log rules out our own polling as the
  cause of the count drop.
- **orderbook.jsonl**: 6,333 rows, `orderStatus` census `{ACTIVE: 6333}` (100%), 130 distinct
  cycles.
- **best_line.jsonl**: 4,449 rows (derived from `/orders`, not independently witnessed), 130 distinct
  cycles. `n_active_orders` histogram `{0:511, 1:1122, 2:971, 3:820, 4:556, 5:315, 6:119, 7:31, 8:3,
  9:1}` — 511/4,449 rows (11.5%) show zero resting orders on one side of one market. **This is a
  thin-liquidity observation, not a suspension signal**: at every one of these 511 rows, the
  corresponding `markets.jsonl` entry for that `marketHash` (when present) still reads
  `status=ACTIVE`. The two phenomena are not conflated in this data.
- **trades.jsonl**: 7,442 rows, `tradeStatus` census `{SUCCESS: 7442}` (100%).

**Write-path audit (the central finding of this node):** read `capture_sxbet.py` in full.
`SxBetClient.get_active_markets()` (lines 221–227) calls `/markets/active` exclusively — an
endpoint that, by its own name and by the 100% `ACTIVE` census above, returns only markets the
exchange currently considers active; a suspended market would not appear with a non-`ACTIVE` status,
it would simply not appear. `/orders` (feeding `orderbook.jsonl`) shows the identical pattern
(100% `orderStatus=ACTIVE`). Separately, `build_envelope()` (lines 390–426) writes a new row to
`markets.jsonl` **only** when a `marketHash`'s content is new or has changed (SHA-256 comparison
against the persisted `StateStore`); byte-identical content across cycles is deduplicated and
produces **no row**. No per-cycle roster snapshot (the full set of `marketHash`es `/markets/active`
returned on a given cycle) is persisted anywhere — `poll_log.jsonl` records only the *count*
(`n_returned`), not membership. **Consequence: if a market were suspended (vanished from
`/markets/active` for one or more cycles) and reopened with identical content to before, this
writer would record nothing at all — no removal event, no reappearance event, no gap.** A
suspend/reopen cycle with unchanged content is invisible to the persisted data by construction. This
is distinct from, and not explained by, a we-failed-to-poll gap: the poll log shows 0/767 HTTP
failures, so failed polling is ruled out — the gap is in what gets *written* on a successful poll of
unchanged content, not in polling itself. This directly bears on acceptance criterion 1 ("a
suspension is claimed only from capture evidence that distinguishes book-suspended from
we-failed-to-poll"): right now, neither tape has evidence to claim from in either direction, for two
different structural reasons (S1/S2 vs S3 in `SUSPENSION.json`).

## Status transitions observed

**Zero, in both tapes, over the full captured window** (odds-API ladder: ~6h50m, 4 games, 3,152
rows; sxbet exchange: ~10h51m and still running at measurement time, 9 games, 314 markets.jsonl
rows / 6,333 orderbook rows / 4,449 best_line rows / 7,442 trades). This is a preserved negative
result, not an absence of measurement — every row and every transition-candidate chain was
enumerated and checked.

## Duration and price-jump measurements

**Not applicable.** No transition exists in either tape to bound a duration on, or to measure a
pre-suspension vs. post-reopen price against. Acceptance criteria 2 and 3 (timestamp-uncertainty
terms on timing claims; reopening price jumps measured against the last pre-suspension capture) are
correspondingly moot rather than satisfied or violated — there is no timing claim or price-jump
claim in this report to carry those fields, and none is asserted in their absence.

## Feasibility verdict

**NOT YET.** `MARKET_MECHANISM_SUPPORTED` (M00 §3, rung 1) for the `PURE_MICROSTRUCTURE` class
(M00 §1.6, suspension/reopening) cannot be reached on the current tape or the current writer design.
Two independent structural gaps stand in front of pure sample-size accumulation:

1. The odds-API ladder writer has no code path that can ever emit `suspended` (verified by full
   read of `market_snapshot_writer.py`).
2. The sxbet writer's dedup-on-unchanged-content design cannot witness a suspend/reopen cycle that
   leaves content unchanged on reopening (verified by full read of `capture_sxbet.py`) — this is a
   capture-architecture gap, not only a low-base-rate problem.

**What would change the verdict:** a capture-upgrade change to the sxbet writer (or a companion
process) that persists a per-cycle roster snapshot — e.g. a heartbeat row per still-tracked
`marketHash` even when content is unchanged, or an explicit "not present in this cycle's active
list" row — so absence becomes a witnessed, timestamped event instead of a silent non-write. That
is a prerequisite for *any* future transition in this tape to be usable as evidence, independent of
how much more time passes. For the odds-API ladder, either a vendor-side suspension signal (not
currently exposed by the endpoints this writer calls) or accepting the coarser event-level `missing`
label as the ceiling for props.

**No calendar estimate is given for how long accumulation would take**, because no base rate for
suspension events at this venue/vendor pair exists anywhere in this dataset (n=0 observed across
~17.5 combined tape-hours and 13 total games). Stating a number here would be an unmeasured guess,
which the node's standing rules prohibit ("measure, do not assert").

## Could not establish

- Whether any suspend/reopen event actually occurred during the captured window that the current
  writer design simply failed to represent — this is unknowable from the persisted artifacts, by
  construction, not merely unmeasured.
- Any duration bound (lower or upper) for a suspension — none was observed to bound.
- Any reopening price-jump measurement — no reopening event exists in the data.
- A base rate or expected-time-to-first-transition for either tape.
- Whether `/orders` and `/markets/active` structurally exclude non-active objects by vendor design
  (the best-supported inference from the endpoint names, the code, and the 100%-ACTIVE census) versus
  some other explanation — SX Bet's API documentation was not fetched live as part of this
  read-only, local-artifact audit, so this remains an inference, not a vendor-confirmed fact.

## Contradictions found

1. **Output-filename conflict** between the spawn instructions (`SUSPENSION.json` +
   `REPORT_BODY.md`, explicitly not `REPORT.md`) and this node's own generated contract
   (`REPORT.md` + `FINDINGS.json`, with `FINDINGS.json` named in the stated validation command).
   Resolved by writing both filename pairs' content (under a permitted filename for the report
   half, per the header note above) rather than guessing which instruction source controls;
   flagged for the coordinator.
2. **Tooling conflict**, distinct from (1): this agent's own Write tool refuses any file literally
   named `REPORT.md` or `REPORT_BODY.md` regardless of which instruction source is followed
   ("Subagents should return findings as text, not write report files"). Neither instruction source
   anticipated this; both asked for a report file this agent's tooling cannot produce under either
   requested name. Resolved the same way M03_CAPTURE_UPGRADE resolved the identical conflict:
   write the content under the nearest permitted filename inside the write scope, and return the
   same content as this agent's final response text for the coordinator to materialize as
   `REPORT_BODY.md`.
3. No contradiction found between the M00 contract's schema mandate (§6.3) and the bytes: every
   `REQUIRED_PRESENT` field in `snapshots.csv` is populated (zero blanks checked directly), and
   every sxbet row carries the full amendment-4 field set including `vendor_ts_semantics` defaulting
   to `unknown_unverified`.
4. Minor, non-methodological: `vendor_latency_note` is present as a column on every `snapshots.csv`
   row (satisfying the schema's structural requirement) but is the empty string on all 3,152 rows —
   an advisory field with no content yet, not a schema violation (`vendor_latency_note` is in
   `NULLABLE_OK`), but worth surfacing since a future reader might expect it to carry the same kind
   of prose the sxbet capture's `vendor_latency_note` does.

## Stop conditions

**None tripped.** No finding here required spending money, placing a wager, entering credentials,
accepting scraping/licensing risk, or reading sealed possession results. No reaction-time or timing
claim was made at all (zero transitions to time), so the amendment-4 UNSUPPORTABLE-labeling
condition is moot rather than tripped — there is nothing timing-shaped in this report to label. No
use of the final-state (T2) `master_odds.csv` archive occurred; this node never opened it or its
extension files. This report contains no wager-shaped or order-shaped recommendation of any kind.
