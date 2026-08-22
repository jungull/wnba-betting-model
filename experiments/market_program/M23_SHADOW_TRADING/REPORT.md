# M23 — shadow trading: 34 decisions committed before their outcome windows opened

**DECISION-SYSTEM VALIDATION WITHOUT MONEY.** Every paper decision is committed with a
pre-decision timestamp against a price that was capturable at that moment, with M21/M22
execution assumptions applied. Shadow results earn at most the M00 ladder status the contract
assigns them; **they are never a licence to trade.**

---

## What this node is, and what it is deliberately not

It validates the **decision system**, not a strategy. M22 has already measured what these
opportunity classes are worth, and the answers were: arbitrage is *"NOT A BUSINESS"*, line
shopping is *"A DISCOUNT, NOT INCOME"*, middles were *negative expectation*, and model-vs-market
showed *no edge on any slice tested*.

So a logged decision here is **not a claim that the opportunity is good**. Every record carries
its class's M22 verdict inline precisely so it can never be read as one.

## Why it cannot be backtested

The first acceptance criterion is that every decision is logged **before** its outcome window
opens. That property cannot be manufactured afterwards — a decision written once the game has
started is a retrospective annotation, not a shadow decision. The ledger therefore only ever
appends decisions on games that have not commenced, and **refuses** anything else.

## The live run

Board built **in memory** rather than from M28's `board.json`, for two reasons: the file on disk
is often hours stale, and writing another node's artifacts from here would recreate the
worktree-churn that previously threatened the push gate.

| | |
|---|---|
| snapshot | `20260822T171502Z`, captured 2026-08-22T17:15:02Z |
| quote age at decision | **406 s** |
| games / books / quotes | 7 / 11 / 378 |
| opportunities on the board | 38 |
| **decisions logged** | **34** |
| refused | 4 |

**Lead time to the outcome window: min 20,292 s (5.6 h), median 95,892 s (26.6 h).** Every record
predates its game by hours, verified against the ledger on disk rather than asserted.

### The refusals are the guard working

All four refusals are `PROMO-EXAMPLE-*` — the promotional offers that are **coordinator-invented
examples, not real offers**. They carry no `commence_time`, so their outcome window cannot be
shown to be closed, and they were refused. The refusal count and reasons are printed, never
silently dropped.

### What was logged

| class | n | M22 verdict carried on every record |
|---|---|---|
| MIDDLES_AND_DISLOCATIONS | 17 | D152 measured most as **negative expectation** |
| PURE_MICROSTRUCTURE | 15 | **A discount, not income** |
| STALE_LINE_DELAYED_REACTION | 2 | M08: 52% of apparent stale windows sit at the resolution floor — **unproven** |

Seventeen of the thirty-four decisions are in a class this programme has already measured as
losing. That is not a defect of the ledger; it is what the board surfaces, recorded honestly.

## The guarantees, each tamper-tested

**32 checks, all passing.** Every criterion is tested with a conforming case *and* a deliberate
violation, because a check that cannot fail is worse than the noisy one it replaced (D171):

| tamper | result |
|---|---|
| drop the outcome-window guard | 2 checks fail |
| drop the S42 guard | 1 check fails |
| let the adjusted stake overwrite the unadjusted | 2 checks fail |

**Criterion 1 — logged before the outcome window.** A started game is refused; a game commencing
*exactly now* is refused (the boundary is closed, not open); an opportunity with no
`commence_time` is refused. The quote acted on carries its own capture timestamp and its age at
decision.

**Criterion 2 — append-only.** Nothing is ever edited. A revision is a **new record** carrying
`supersedes`, and the superseded record stays exactly as written. Every on-disk record's
`record_sha256` is verified against its own content.

**Criterion 3 — M21/M22 applied, unadjusted retained.** Slippage comes from M21's measured p90
price move against real resting orders (1.351% at $50, 5.229% at $100); fills are capped at the
measured median depth of **$49.01** and flagged when the requested stake exceeds it. The
**unadjusted figure is retained beside the adjusted one, never replaced**. Book-side limits are
carried as **ABSENT** — M21 marked them unmeasured rather than estimating them, and this node
does not quietly supply a number M21 refused to invent.

**Criterion 4 — no money.** `order_placed` and `real_money_touched` are literal `False` on every
record; execution mode is SHADOW. There is no venue client, no credential read, and no network
call to any book. **S42 is enforced in code**: a decision in a fitted-scoring-model class raises
`S42Violation` and cannot enter the ledger at all.

## What this does not establish

- **No outcome has been scored.** The 34 decisions are on games commencing 2026-08-22/23. Their
  value is realised only when those games settle; scoring them is future work and requires
  outcomes this repository does not yet have.
- **No profitability claim of any kind.** Nothing here contradicts M32's −7.2% or M22's verdicts,
  and this ledger must never be cited as evidence that any class wins.
- **A single snapshot.** One board, one instant. Nothing about the *rate* at which decisions
  arrive is established.
- **Execution remains theoretical.** M21 measured depth and slippage on the exchange tape; that a
  stake was "fillable at median depth" is an assumption applied to a decision, not an observed
  fill.
- **The promotional class is untested here**, because the only offers on file are invented
  examples — which is exactly why they were refused.
