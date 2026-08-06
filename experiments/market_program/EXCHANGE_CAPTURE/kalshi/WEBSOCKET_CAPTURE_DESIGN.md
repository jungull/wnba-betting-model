# Kalshi WebSocket capture — DESIGN ONLY, NOT RUN

**Status:** Design document only. No connection to any Kalshi WebSocket endpoint has been made or
attempted. This document does not depend on, and is not blocked by, the `HALT_USER_REQUIRED.md`
finding in this directory, because producing it required no request to kalshi.com and captured no
Kalshi Data (price/volume/settlement content) — only a description of an architecture referencing
publicly documented endpoint *shapes*, which is not itself Kalshi Data under the Data Terms of Use
definition in `DATA_TERMS_OF_USE_VERIFIED_2026-08-06.md`.

**This design must not be implemented or run until the HALT in this directory is resolved by the
user**, because a running WebSocket capture is exactly the kind of automated, persistent access to
Kalshi Data that the Data Terms of Use §II prohibits absent written consent — arguably more clearly
than REST polling, since a WebSocket subscription is a standing "agent" maintaining continuous
"access" and "retrieval."

## 1. Scope

Capture real-time order-book deltas and trade prints for open WNBA-relevant Kalshi markets,
supplementing the (also-blocked) 60s REST poll with sub-second update resolution, once/if
authorized.

## 2. Assumed transport shape (from Kalshi's public API documentation, unverified against a live
connection by this track)

- A single authenticated or unauthenticated WebSocket endpoint accepting a JSON subscribe message
  naming one or more channels (order book deltas, trades, ticker) and one or more `market_ticker`
  values.
- Server pushes incremental order-book delta messages plus periodic full-book snapshots, and
  discrete trade-print messages (price, size (contracts), taker side, timestamp).
- Sequence numbers per channel, used to detect gaps and trigger a resync (request a fresh snapshot)
  rather than silently continuing on a torn book.

Every field above is a description of a *message shape*, not a captured value, and must be
independently confirmed against the live schema at build time (not assumed from memory) once the
halt is resolved.

## 3. Proposed architecture (not implemented)

```
kalshi_ws_capture/
  connector.py        # opens ws, subscribes, dispatches by channel, 1 rps connect/reconnect backoff
  book_state.py        # maintains local order-book replica per market_ticker; sequence-gap detection
  writers/
    trades_writer.py    # append-only JSONL, one row per trade print
    book_snapshot_writer.py  # periodic full-book snapshot rows, not deltas, for replay simplicity
  resync.py             # on sequence gap: log gap event, re-request snapshot, do not interpolate
  poll_log.jsonl         # connect/disconnect/resync/error events, resumable cursor state
```

## 4. Row schema (mirrors the REST backfill schema in `BACKFILL_DESIGN.md`, extended with WS fields)

**Trade row:**
```
ts                    ISO-8601, server-asserted trade time (VENDOR_ASSERTED)
retrieval_ts           ISO-8601, local receipt time
market_ticker
price                  cents, integer
qty                    contracts
taker_side              yes | no
seq                    per-channel sequence number
provenance             EXCHANGE_PUBLIC_API
provenance_ts_class     VENDOR_ASSERTED (ts) / WITNESSED (retrieval_ts)
payload_hash            sha256 of raw message bytes
```

**Book snapshot row:**
```
ts                     server-asserted snapshot time if provided, else null
retrieval_ts            ISO-8601, local receipt time
market_ticker
yes_bids / yes_asks      list of [price_cents, qty]
seq
provenance              EXCHANGE_PUBLIC_API
provenance_ts_class      VENDOR_ASSERTED / WITNESSED
payload_hash
gap_detected             bool, true if this snapshot follows a sequence-number gap
```

Both row types append-only; a correction is a new row, never an in-place update, matching the
amendment-4 discipline this whole program uses elsewhere (M00 §6.3).

## 5. Resumability

- `poll_log.jsonl` records every connect, subscribe-ack, disconnect, resync, and error with
  timestamps, so a restarted process can report the exact gap window rather than silently
  continuing.
- On reconnect, request a fresh full snapshot before resuming delta application; never trust a
  delta stream across a reconnect boundary without a fresh base.

## 6. Politeness / access posture (carried from the standing rules this whole track operates under)

- Honest User-Agent identifying this as a research capture process.
- Single connection per process; no connection-storming reconnect loop — exponential backoff capped
  at a sane ceiling (e.g. 60s).
- If Kalshi's WebSocket requires an API key/auth handshake even for "public" market data, that is a
  credential and is out of scope for this track without a separate USER_REQUIRED credential
  decision (M00 §9.3) — this design assumes the unauthenticated path documented for market data
  reads, to be reconfirmed at build time.

## 7. Explicit non-goals

- No order placement, no authenticated trading session, no execution-path code. This is a read-only
  research capture design, S-MKT only, per the M00 §2 four-system separation — never S-EXEC.
- No claim of latency/reaction-time superiority over the REST poll is made without the full §6
  timestamp-uncertainty field set once real captures exist.
