# M03_CAPTURE_UPGRADE — REPORT

> Materialized by the coordinator from the build agent's returned report content, verbatim in
> substance: the harness refused the agent's own write of a file named REPORT.md ("Subagents
> should return findings as text"). The placeholder CAPTURE_REPORT.md records the same event
> from the agent's side. Content below is the agent's; only this header is the coordinator's.

EPISTEMIC STATUS: PROSPECTIVE CAPTURE INFRASTRUCTURE on the D023 amendment-3 immediate
critical path. Builds the tape that makes future market claims provable. Creates no
historical evidence and repairs no historical gap: every week without the upgraded tape is a
week of event studies that can never be run.

## What was implemented (all with tests; 69/69 pass — 68 hermetic + 1 gated live smoke)

* **(a) Ladder scheduler** `market_ladder_scheduler.py`: 8 rungs T-24h..final_pregame
  mirroring `should_run_base.py`'s lead-window / at-most-once gate pattern
  (dependency-injected slate; no coupling to the forecast chain's evalharness import).
  DISCLOSED INTERPRETATION: the design leaves `final_pregame` without a numeric offset; this
  implementation sets it to **T-5m** (one rung tighter than T-15m) — a one-line change if a
  different offset is wanted, not a measurement.
* **(a) Burst triggers** `market_burst_trigger.py`: polls injury_log.csv / news_items.csv
  via a persisted row-count cursor, resolves first-seen rows to a still-future slate game,
  schedules 3 legs (+0/+5/+15min), dedupes against pending ladder rungs. DISCLOSED
  DEVIATION: team/slate resolution is dependency-injected rather than importing
  `prospective_pair/coverage_audit.py` directly (that module pulls in alt_model_log →
  evalharness.forecast_log — far heavier than a capture-layer watcher needs); production
  wiring (`market_capture_run.py`) DOES import `coverage_audit.build_slate()`/TEAMS and
  inject them — the deviation is in *how*, not *whether*, the join logic is reused.
* **(b) Append-only writer + schema** `market_snapshot_writer.py` / `market_snapshot_schema.py`:
  every contract-6.3 mandatory field present (vendor_ts, vendor_ts_semantics — default
  `unknown_unverified`, hard-coded with no path that sets it otherwise — retrieval_ts,
  ingestion_ts, max_staleness_bound, poll_interval_at_capture, vendor_latency_note,
  payload_hash, prev_snapshot_ref), enforced as a MANDATE via `validate_row()`/SchemaViolation
  that refuses to write a non-compliant row (tested: never written, not silently dropped
  after writing). `price` vs `price_over`/`price_under` kept as separate columns per the
  design's explicit instruction.
* **(c) Poll log**: one row per poll ATTEMPT (success or failure) to `poll_log.csv`,
  append-only, credit headers captured verbatim from the vendor response.
* **(d)/(e) Coverage audit** `capture_coverage_audit.py`: missed-poll classification
  (served / not_yet_due / postponed_or_tip_changed / missing_poll_did_not_run — with an
  explicit test that a row retrieved before a rung's cutoff can never backdate service),
  silent-overwrite detection (walks the prev_snapshot_ref chain), identifier-change diff
  (NOTE-only, allow-listed), stale-job surfacing (no row ever, or last row older than 26h).
* **(f) Coexistence**: `market_capture_config.is_enabled()` defaults **False**
  (`MARKET_LADDER_ENABLED` must be explicitly truthy); `market_capture_run.main()` exits 0
  as a no-op when disabled; writes only to new `data/market_snapshots/`; imports only
  `odds_capture_daily.api_key` from the existing jobs, never their capture/write functions;
  no Task Scheduler XML, no .cmd wrapper, and no edit to any existing capture job or
  anything under `prospective_pair/`.

## Live validation

The node's allowed ≤2 live calls, both spent on free endpoints: GET /v4/sports → 200;
GET /v4/sports/basketball_wnba/events → 200 (6 events). Both cost 0 credits
(x-requests-last: 0). Headers: used=609, remaining=19,391 — live confirmation of the
20,000/month quota (the D025 plan). **Total vendor credits spent by this node: 0.**

## Could not establish

1. Live-measured per-run cost of the ladder's PAID /odds calls under the new cadence —
   would have exceeded the 2-call budget; the design's cost formulas rest on
   props_capture_daily.py's own prior "verified 2026-07-31" measurement.
2. vendor_ts_semantics resolution against The Odds API's docs/support — left
   `unknown_unverified` everywhere per design open item #2.
3. Real-world burst-trigger volume (design open item #3) — not measurable without running
   the watcher over live time.

## Contradictions found

1. Write-scope contradiction between the node prompt (program-worktree path) and the
   spawning instructions (isolated m03-capture worktree) — resolved by using the same
   relative path inside the m03-capture worktree; flagged, not silently resolved.
2. None between CAPTURE_UPGRADE_DESIGN.md's claims about the existing capture jobs and
   their actual code — checked directly, matched on cadence and cost formulas.

## Observed side effect, disclosed

Importing `odds_capture_daily.py` (required to reuse `api_key()` per the credential rule)
runs that module's top-level `OUTDIR.mkdir()`, creating an EMPTY `data/odds_capture/`
directory in this worktree — pre-existing behavior of the reused module. Confirmed empty
after every test run; `capture_log.csv` never created or touched.

## Stop conditions

None tripped. No money spent (0 credits), no credentials outside the existing .env/env-var
mechanism, no new scraping target (api.the-odds-api.com only), final-state archive
untouched, and every row this writer can produce is schema-blocked from omitting the
amendment-4 fields — the infrastructure itself cannot manufacture an unsupportable timing
claim.

## Routed to M02B (USER_REQUIRED)

Enabling `MARKET_LADDER_ENABLED` on an ongoing basis: modeled at ~1,875–7,140 credits/month
additive to the existing jobs' ~750–1,500/month, against the live-confirmed 20,000/month
quota. The flag ships OFF regardless of the tier purchase; flipping it on — and the 1–2 week
burn-in the design specifies before any 100K-tier discussion — is a user decision.
