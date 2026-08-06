# M09_TRUE_ARB_SCANNER — activation checklist for the real scan

**Status: FROZEN. This checklist is not itself a finding and grants nothing on its own.**
The scanner engine (`arb_scanner.py`) is built and tested now, against synthetic
fixtures (`fixtures.py`/`TESTS.py`) and a labeled demonstration replay over the
existing coarse capture sample (`coarse_tape_demo.py` /
`COARSE_TAPE_DEMO_RESULTS.json`). It does not run as a live scan today because
the high-frequency ladder does not exist yet (ladder OFF, per program honesty
rule). This checklist is the frozen gate between "machinery exists and is
tested" and "the scanner is scanning."

Every item below must be independently true, on real bytes, before this
scanner's output may be cited as anything other than a demo. None of these
items is satisfied by this node. None of these items is self-certifying —
each is checked against an artifact this node did not produce.

## 1. Capture cadence

- [ ] The odds-capture poll interval is sub-minute (or otherwise fine enough
      that `poll_interval_at_capture` on the resulting rows is smaller than
      the shortest realistic true-arb persistence window). Verified against
      the ACTUAL recorded `snapshot_utc` gaps in the capture log at
      activation time, never against a nominal polling config value — the
      final-state archive (P2B/D016) is the standing example of why a
      configured cadence and an actual cadence can differ.
- [ ] `poll_interval_event` is likewise established from real event-stream
      poll gaps if this scanner is ever asked to gate on event-linked
      conditions (out of scope for pure cross-book arb, but recorded here
      because the same PollLog machinery is shared).

## 2. Clock-skew measurement

- [ ] A per-run NTP (or equivalent) clock-skew measurement exists and is
      attached to the capture run, populating `clock_skew_bound` with a real
      `epsilon_max_s` and a stated measurement method — never
      `UNMEASURED`. Every row of `coarse_tape_demo.py`'s replay was
      `UNMEASURED` by construction; that must flip before any flag counts.
- [ ] The measurement method is auditable (source, procedure, and frequency
      of re-measurement stated) — a one-time skew check does not license
      treating skew as constant forever.

## 3. Vendor latency bounds

- [ ] Every venue this scanner is asked to pair carries a **sourced**
      `vendor_latency_bound` (a citation, not an assumption) in the table
      passed to `simultaneity_window`. A venue without one is `UNBOUNDED`
      and the scanner correctly refuses to certify simultaneity on any pair
      touching it (already enforced in code — this item is about supplying
      the bounds, not about the enforcement, which already exists).
- [ ] The eleven real bookmakers exercised in `coarse_tape_demo.py`
      (`betmgm`, `betonlineag`, `betrivers`, `betus`, `bovada`,
      `draftkings`, `fanatics`, `fanduel`, `lowvig`, `mybookieag`,
      `williamhill_us`) each get a real sourced bound before their pairs are
      ever scored for a live flag, not the empty `{}` this demo intentionally
      passed.

## 4. Settlement-rule and fee inventory (real venues)

- [ ] Every venue above (and any other venue the live scanner touches) has a
      verified `SETTLEMENT_RULES` row (push handling, void/DNP handling) —
      not the single `REAL_BOOK_BASELINE_RULE` this demo used as an
      explicitly-labeled placeholder for h2h-only scoring. That inventory is
      M00-U3 territory (identifier/settlement conventions) and belongs to
      whichever node owns verifying it against each venue's actual rules
      page, with a citation and last-verified date per venue.
- [ ] Every venue has a verified `FEE_MODEL` row (this demo assumed
      zero-fee retail sportsbooks, which is directionally correct for
      standard-book moneylines but must be confirmed, and must be replaced
      with the exchange commission schedule for any exchange venue such as
      the fixture's `exchange_epsilon` analog in real life).
- [ ] Spreads and totals markets get their own verified push-handling rows
      before this scanner is extended to score them on real venues (this
      node's demo deliberately scored h2h only, for exactly this reason —
      see `coarse_tape_demo.py`'s `SCORABLE_MARKET` comment).

## 5. Posted limits / capacity

- [ ] `POSTED_LIMITS` carries real per-venue per-market stake caps sourced
      from the M26 venue registry, or the scanner continues to report
      `CAPACITY_UNKNOWN` honestly (already the default; this item is about
      supplying real numbers where available, not about removing the
      honest default).

## 6. Linkage / event-market join (if extended beyond pure cross-book pairs)

- [ ] If this scanner is ever asked to gate a flag on a linked event (not
      required for pure TRUE_CROSS_BOOK_ARBITRAGE, which needs no event —
      contract section 1.1 mechanism is asynchronous repricing, not an
      information event), it must consume TRUSTED linkage records from
      M05, never re-derive its own event-quote linkage.

## 7. Execution-mode posture

- [ ] Confirmed still `OFF` for this scanner's own output: it produces
      flags, never orders, regardless of any item above. This item never
      changes as a *consequence* of items 1–6 clearing — mode transitions
      are their own USER_REQUIRED gate (contract section 7) and are never
      granted by satisfying a data-quality checklist.

## What "the ladder turns on" means for this specific node

Once items 1–5 are independently verified (item 6 only if in scope, item 7
is a standing constraint, not a gate to clear), `arb_scanner.py` itself
needs **no code change** to go from demo to live: the same `build_flag`
function, the same `simultaneity_window` combined-inequality logic, and the
same append-only flag log already implement the full contract-section-1.1
definition. What changes is only the *inputs*: real `clock_skew`, real
`vendor_latency_bounds`, real per-venue `SETTLEMENT_RULES`/`FEE_MODEL`/
`POSTED_LIMITS` rows, and a poll grid fine enough for the resulting
`t_lower <= t_upper` windows to ever overlap. This checklist exists so that
day is a verified go, not a rerun of this node's own say-so.
