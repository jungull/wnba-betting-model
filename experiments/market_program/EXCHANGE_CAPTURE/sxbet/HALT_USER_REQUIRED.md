# TRACK SXBET — HALTED at the ToS-ambiguity gate before standing capture

**Status:** PARTIAL. WNBA existence and the technical API surface ARE verified (see
`API_AND_WNBA_VERIFICATION_2026-08-06.md`) via three lightweight, publicly-documented, rate-limit-
compliant GET requests. No order-book capture, no trade capture, no polling loop, and no persistent
archive of SX Bet market data (odds, prices, sizes) was built or run.

## Why this halts instead of executing the full D033 mandate

The dispatch brief for this track says: "if WNBA exists + free + lawful: build capture (order books,
trades if public) same discipline as Kalshi track, run one verification cycle, report counts."
WNBA existence: confirmed. Free: confirmed (no key, no paid tier gates market data). **Lawful is the
open condition**, and per `TERMS_OF_USE_VERIFIED_2026-08-06.md`, SX Bet's own published terms are
internally in tension on exactly this question — the general Terms and Conditions both (a) exempt
means "provided by us" (which the official API is) from the anti-scraper clause, and (b) separately
ban "scrap[ing] our odds" and "merg[ing]" Service content "with other data" without that same
qualifier. SX Bet's own docs do not resolve which reading controls.

Per the M00 contract (§9.7): "Legal/risk acceptance — scraping or licensing risk, ToS interpretation...
are user actions exclusively... it HALTS and raises a USER_REQUIRED gate." Per §11's stop conditions:
"accepting scraping/licensing risk... → HALT to USER_REQUIRED." This track follows the same discipline
the sibling Kalshi track applied under the D031 honesty-preservation condition — verify current terms,
and if a real prohibition-reading survives that verification, surface it rather than resolve it
unilaterally. Unlike Kalshi's Data Terms of Use, SX Bet's terms are **not** an unambiguous prohibition:
there is a live, plausible reading (official API = "means... provided by us") under which capture would
be permitted. That is precisely why this is a USER_REQUIRED interpretive question rather than either
an automatic HALT (like Kalshi, whose terms have no API carve-out at all) or an automatic GO.

## What WAS done

- Verified SX Bet documents a free, keyless, public REST API for market/odds/trade data, with stated
  rate limits this track's 1 rps discipline sits well inside.
- Verified WNBA markets exist and are live: league `1384` ("WNBA"), 60 active markets at capture time
  spanning multiple games, three market types (moneyline, spread, totals), each keyed by `marketHash`
  and linked to a fixture ID (`sportXeventId`) usable for D033 event-catalog linkage if capture is
  later authorized.
- Retrieved and quoted SX Bet's current Terms and Conditions and API help-article text verbatim.
- Made exactly three read-only GET requests total against `api.sx.bet` (`/sports`, `/leagues`,
  `/markets/active`) — no order-book (`/orders`) or trade (`/trades`) endpoint was queried, and no
  response was written to any capture file or database.

## What was NOT done, and why

- **Order-book capture** (`/orders?marketHashes=...`) — not queried. Blocked pending the ToS
  disposition below; this is exactly the "our odds" content the ownership/anti-scrape clauses name.
- **Trade capture** (`/trades?marketHashes=...`) — not queried, same reason.
- **Any polling loop, JSONL append, or persistent archive** — none written. Zero rows captured.
- **A capture-code skeleton was deliberately not written either**, unlike the Kalshi track's permitted
  WebSocket *design* document — because unlike Kalshi (whose docs were fair game as pure architecture
  reference disconnected from any live-data question), the open question here is specifically whether
  invoking the documented endpoints at all is the disputed act. Writing runnable capture code invites
  it to be run later without re-litigating this gate; a short architecture note is included below
  instead, containing no SX Bet data.

## Report counts (as requested by the dispatch brief)

**0 order-book rows, 0 trade rows, 0 poll cycles.** WNBA-market metadata rows observed during
verification: 60 (not stored — read from the API response and reported by count only, in this file).

## Minimal architecture note (no SX Bet data; docs-derived only, for if/when this unblocks)

- Poll target: `GET https://api.sx.bet/orders?marketHashes={comma-separated}` and
  `GET https://api.sx.bet/trades?marketHashes={comma-separated}`, batched across the WNBA `marketHash`
  set refreshed periodically from `GET /markets/active?leagueId=1384`.
- Cadence: 1 rps ceiling regardless of the documented 500 req/min allowance, per this program's
  polite-client rule; well under SX Bet's own 200 req/min (trades) / 500 req/min (other) limits.
  Order-book snapshots on the D033 event-adaptive grid (§Track A redesign) once/if a shared event
  catalog exists; trades can be polled continuously at low frequency since they are immutable once
  settled on-chain.
- Row schema would carry every amendment-4 field required by M00 §6.3 for any market-snapshot table:
  `vendor_ts` (SX Bet has no documented "book last change" timestamp distinct from ingest — default
  `vendor_ts_semantics = unknown_unverified` until confirmed), `retrieval_ts`, `ingestion_ts`,
  `max_staleness_bound`, `poll_interval_at_capture`, `vendor_latency_note`, `payload_hash`,
  `prev_snapshot_ref`. Append-only; a correction is a new row, never an UPDATE.
- Provenance/source-hierarchy class: SX Bet market data would enter as market-implied pricing evidence
  (S-MKT, §2 of the M00 contract), not as an injury/status source — it plays no role in the D033
  source hierarchy (which governs player-status provenance, not odds provenance).

## What resolves the halt

A user decision on one of:
- **(a)** Rule that the official-API reading controls (means "provided by us" are exempt from the
  general anti-scraper clause) and authorize capture to proceed under that reading — a §9.7 ToS-
  interpretation action only the user can make, mirroring the D031 pattern for Kalshi.
- **(b)** Seek SX Bet's written confirmation that programmatic archival via the documented API is
  permitted (a §9.7 legal/risk-acceptance and licensing action).
- **(c)** Accept the risk knowingly and explicitly instruct capture to proceed regardless (§9.7).
- **(d)** Confirm this track stays OFF and SX Bet is dropped from the exchange-capture roster.

Nothing beyond the three verification GETs listed above was executed against SX Bet's live systems.

---
## SUPERSEDED 2026-08-07 — capture authorized and running

**This document's "0 rows captured" statement was true when written and is now stale.** The user
ruled on the ToS interpretation in `DECISION_LEDGER.jsonl` decision `D035_EXCHANGE_DISPOSITIONS`:
the official-documented-API reading controls, and capture proceeds at gentle read-only rates.
Capture has since run continuously (scheduled task `WNBA_SxBetCapture`, one cycle per 5 minutes)
and M21_EXECUTION_REALISM measured 131 cycles / 10.93 hours / zero endpoint failures against it.

The ToS tension recorded above is preserved deliberately (D035: "the ToS tension recorded rather
than erased, and the disposition reversible if SX Bet ever objects"). Nothing in the analysis above
is retracted — only its capture-status claim is superseded.
