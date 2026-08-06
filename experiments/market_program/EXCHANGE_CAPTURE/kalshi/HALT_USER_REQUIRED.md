# TRACK KALSHI — HALTED at the D031 honesty-preservation gate

**Status:** BLOCKED, USER_REQUIRED. No Kalshi Data was searched, fetched, backfilled, or polled by
this track. No API request was made to any `kalshi.com` or `elections.kalshi.com` /
`trading-api.kalshi.com` endpoint.

## Why this halts instead of executing D033's Kalshi mandate

D033's mandate text for this track opens: "Using Kalshi PUBLIC market-data endpoints (their docs
describe unauthenticated access)" and directs immediate execution of market search, trade/candle
backfill, and an order-book poll. That characterization — unauthenticated access implying
permitted use — is the premise this track was asked to build on.

D031 (`DECISION_LEDGER.jsonl` line 31), the ruling this mandate cites, is more careful than that
premise: the user's ruling is that the *permission-letter dependency* is unnecessary because Kalshi
documents public data endpoints and "data access is separate from trading eligibility" — but D031
does **not** waive verification. It says explicitly:

> "HONESTY PRESERVED: the capture builder re-verifies the CURRENT data-terms text verbatim as it
> builds; if the explicit archival-prohibition clause the survey quoted still stands, the exact
> quote is surfaced to the user once before capture starts - otherwise capture begins."

This is a conditional, not a blanket go-ahead. I re-verified (see `DATA_TERMS_OF_USE_VERIFIED_2026-08-06.md`
in this directory) before writing a single line of capture code, per that condition. Result: **the
clause still stands**, and it is broader than the version FREE_DATA_SURVEY quoted:

1. Non-commercial-use carve-out excludes, without Kalshi's prior written consent: "(1) the
   development of any software program... [or] (2) providing archived or cached data sets
   containing Kalshi Data to another person or entity." — This is exactly what D033 steps (1)-(3)
   ask for: a market-search script, an append-only backfill JSONL, and a resumable polling capture
   with a poll log.
2. A broader anti-automation clause strictly prohibits, absent Kalshi's written permission, using
   "scripts, software, spiders, robots... agents, tools" to "navigate, access, copy in bulk,
   retrieve, harvest, index, search or analyze any portion of the Website." This reaches even the
   single step-1 market-search call — not just the backfill/poll.
3. A bolded clause added since the earlier survey pass expressly prohibits using Kalshi Data "in
   any manner for any machine learning and/or artificial intelligence... or in connection with the
   use of such technologies, tools, or models to generate any information, material, data, derived
   works, content, or output." This document is being produced by an LLM-driven agent acting on
   Kalshi Data it would otherwise fetch — squarely inside that clause.

Per the M00 contract this track is bound by (§9.7): "Legal/risk acceptance — scraping or licensing
risk, ToS interpretation... are user actions exclusively... it HALTS and raises a USER_REQUIRED
gate." Per §11's stop conditions: "accepting scraping/licensing risk... → HALT to USER_REQUIRED."
D031's own honesty clause requires the same thing on this specific fact pattern. Three independent
sources of authority point the same direction, so this track stops here rather than executing.

## What was NOT done, and why each is blocked by the same finding

- **(1) Market/series search** — blocked: any scripted GET against Kalshi's site/API is "use of...
  scripts... to navigate, access... search... any portion of the Website," prohibited absent
  written permission, independent of whether the result is stored.
- **(2) Historical trades/candlestick/metadata backfill into JSONL** — blocked on two independent
  grounds: it is exactly "providing archived... data sets containing Kalshi Data," and it requires
  step (1) first.
- **(3) Polling order-book depth capture (60s, resumable, poll log)** — blocked on the same two
  grounds as (2), continuously rather than once.
- **(4) WebSocket capture DESIGN doc** — **NOT blocked** by the Data Terms of Use, because a design
  document describing architecture from Kalshi's published API *documentation* (not "Kalshi Data" —
  documentation is not volume/price/settlement content) captures no Kalshi Data and issues no
  request against kalshi.com. Written separately as `WEBSOCKET_CAPTURE_DESIGN.md` in this directory,
  per D033's own instruction that this deliverable is designed but never run.

## What resolves the halt

A user decision on one of:
- **(a)** Seek Kalshi's prior written consent for the archival/software-development use (the
  original FREE_DATA_SURVEY M02B path, §9.7's legal/risk-acceptance and licensing action, still a
  USER_REQUIRED action — the user would need to request or authorize this outreach), or
- **(b)** Accept the ToS risk knowingly and explicitly instruct capture to proceed anyway (a §9.7
  legal/risk-acceptance the graph cannot self-grant), or
- **(c)** Confirm this track stays OFF and Kalshi is dropped from the exchange-capture roster, same
  disposition as the FREE_DATA_SURVEY originally recommended before D031 reopened the question.

Nothing below this point was executed. Row counts for backfill and the polling cycle D033 asked to
be reported: **0 rows, 0 markets, 0 polls** — none were attempted.
