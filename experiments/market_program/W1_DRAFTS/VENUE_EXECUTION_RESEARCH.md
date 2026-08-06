# Venue & execution research — user-supplied, synthesized and integrated

Provenance: research supplied by the user in chat, 2026-08-06. Claims about venue APIs,
state licensing, and regulator positions are **web-derived and unverified by this
repository**; legal positions are time-sensitive and disputed in places. NOTHING here is
legal advice, and nothing here authorizes an account, a deposit, or a wager. Every
real-money step remains behind USER_REQUIRED gates (D023, D024). Verify every load-bearing
claim against primary sources before any funding decision.

## 1. The structural finding

**Execution feasibility is jurisdiction-gated, not engineering-gated.** For a user
physically in New York:

| track | venues | automation | status for us |
|---|---|---|---|
| Exchange APIs | ProphetX (Trading API: WebSocket, CLOB, limit orders, cancel, sandbox), BettorEdge (REST: order book, orders, portfolio) | Officially supported | Technically ideal; **legally unresolved in NY** — operator claims conflict with the NY State Gaming Commission's position that prediction/peer-to-peer markets are not licensed sports-wagering operators. Sandbox/shadow work only until written answers + user legal clearance. |
| Kalshi | Full Trade API | Officially supported | **Active NY legal dispute — excluded from production planning now.** |
| Novig | — | No public execution API found | Explicitly excludes NY. Out. |
| Licensed NY books | DraftKings, FanDuel, BetMGM, Caesars, Bally Bet, ESPN Bet, Fanatics, Resorts World, BetRivers | **None** — no consumer wagering API; ToS prohibit automated access and automated bet placement | Compliant pattern only: automated detection → recommendation + bet-slip preparation → **manual human confirmation**. No scraping, no Selenium/Playwright automation, no private-endpoint reverse engineering — prohibited by their terms and by this program's own rules. |

Consequence: the near-term executable path in NY is **alert-plus-manual-confirm** on
licensed books (fast enough for slower derivative markets, not for the first seconds after
star injury news), while exchange automation is a **sandbox-and-shadow research track**
until the legal conflict is resolved in writing.

## 2. Standing policy adopted (D024): the execution-mode ladder

Four explicit, mutually exclusive modes; transitions are one-way gates, never automatic:

* **OFF** — no orders, no alerts.
* **SHADOW** *(default and starting mode for every strategy)* — generate the exact order
  that would have been placed, with full audit record; send nothing.
* **CONFIRM** — generate the order and present a single confirmation to the human; the
  human clicks or nothing happens. The only mode ever contemplated for licensed NY books,
  and the entry mode for exchange testing with real funds.
* **AUTO** — API order placement without per-order approval. Requires ALL of: written
  platform authorization for algorithmic entry on our account class; jurisdiction
  clearance in writing; passed sandbox tests; prospective SHADOW performance meeting
  preregistered gates; verified risk controls (below); and an explicit financial
  USER_REQUIRED authorization. None of these can be self-granted by the graph.

**Hard risk controls required before any non-SHADOW order** (adopted verbatim as the M24
checklist skeleton): approved event source; minimum confidence; minimum edge; maximum
quote age; maximum stake; per-game and per-player exposure caps; minimum liquidity; no
duplicate or correlated-order conflict; no trading through a suspension; daily loss and
volume caps; global kill switch.

## 3. Architecture absorbed into existing workstreams

* **Precomputed scenario repricing** ("do the reasoning before the news"): per-game
  scenario table (normal / limited / inactive per key player, with replacement allocation
  and resulting fair ML/spread/total/team-total/prop deltas), updated in milliseconds from
  precomputed states when an event fires — this is the operational form of
  M13_PLAYER_VALUE_TRANSLATION and consumes the injury/news first-seen events we already
  capture. The parser output contract (player, event type, status transition, P(play),
  minutes delta, confidence, evidence span) matches our existing information-event schema.
* **Execution-adjusted edge**: usable_edge = model_edge − fees − expected slippage −
  latency penalty − uncertainty buffer. Never trade a raw one-cent disagreement. Folds
  into M21_EXECUTION_REALISM as its objective function.
* **Bounded orders**: on any exchange, aggressive *limit* orders with price bound, stake
  bound, and short cancel timers (e.g. "≤54% implied, ≤$75, cancel unmatched after 2s");
  engine must handle complete/partial/no fill, rejection, suspension, stale remainder,
  and mid-flight quote movement. This becomes the order-router design contract (M27).
* **Latency test ladder**: simulate at 100ms / 500ms / 1s / 5s / 30s — merges directly
  into M21's delay grid (which already required 15s–5m; the sub-second rungs are added
  for the exchange track).
* **Complete audit record** per opportunity (information received, evidence, model state,
  fair price, observed book, decision, request/ack timestamps, fills, fees, subsequent
  movement, close, result) — so failures decompose into: bad signal vs slow ingestion vs
  bad execution vs no liquidity vs right-but-untradeable. This is our receipts culture
  applied to execution; adopted as the M23 shadow-record schema.

## 4. New graph work this creates

* **M26_VENUE_AUTOMATION_REGISTRY** (wave-1.5, after M00): one row per venue —
  jurisdiction, state license status, platform legal claim, regulator position, WNBA/props
  availability, official execution API (y/n), WebSocket, latency, order types, partial
  fills, fees, liquidity, rate limits, sandbox, approval process, automation-permitted-by-
  terms, production status. Every legal-status cell carries a citation and a
  last-verified date. Nothing in the registry is self-certified by a platform's own claim.
* **M27_ORDER_ROUTER_AND_SHADOW_EXECUTION** (design-first): universal order-router
  interface (venue-agnostic order intents → venue adapters), SHADOW implementation first,
  CONFIRM UI hook second, AUTO adapter last and gated. ProphetX sandbox and BettorEdge
  read-only evaluations are the first pilots — **sandbox/demo-funds only**, and account
  creation/KYC on any venue is a USER task, never an agent action.
* **M06/M13 tie-in**: injury-triggered scenario repricing becomes the first SHADOW
  consumer once capture upgrade (M03) and linkage (M05) land.

## 5. User decisions this queues (none blocking current work)

1. Whether to seek written answers from ProphetX/BettorEdge on NY legality, API permission
   for individual NY users, algorithmic entry on our account class, WNBA prop coverage,
   and API-user requirements — the letters are drafted by the lane when you say go; you
   send them.
2. Whether/when to create sandbox accounts (user-performed; demo funds only).
3. Any eventual CONFIRM- or AUTO-mode activation — each its own explicit gate, far
   downstream of shadow evidence.

## 6. What this does NOT change

The lane still places no wagers, holds no credentials, spends no money. The possession
program is untouched. The final-state archive rulings, timestamp-uncertainty discipline,
and preregistration culture all apply to execution research exactly as to market research.
