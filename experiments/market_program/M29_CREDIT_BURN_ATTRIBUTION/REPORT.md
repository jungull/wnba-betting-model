# M29_CREDIT_BURN_ATTRIBUTION — where the credits went, and what cadence we can afford

**Coordinator #08, 2026-08-19.** Resolves the open risk `M27_PER_BOOK_POLLING` raised on
2026-08-07 and could not answer, which has been the stated blocker on the one upgrade the
opportunity board most needs.

---

## 1. The question, and why it mattered

M27 observed **11,728 credits consumed inside a 57-minute window** that it could attribute
neither to its own code nor to the market ladder. It ruled both out by direct measurement, then
made this its **top recommendation**:

> *"Recommend the user first identify the ambient consumer, then run
> `MARKET_PER_BOOK_POLLING_ENABLED=1` as a FURTHER-BOUNDED pilot… before treating it as a standing
> schedule change."*

That worry sat open for twelve days. Meanwhile `M28_OPPORTUNITY_BOARD` established that **capture
cadence — not modelling — is the binding constraint on the product**: on an hourly grid every
locked-arbitrage row is structurally retrospective. So the unresolved credit question was gating
the highest-value product upgrade available.

M27 had 57 minutes of evidence. This node has **12.85 days and 207 observations**.

## 2. Method, and its one assumption

`poll_log.csv` records, per call, the vendor's own `credits_used` / `credits_remaining` counters
*plus* `credits_last` — what that specific call cost. Between two consecutive observations the
counter should advance by exactly the later call's cost. **Any excess was consumed by something
this logger does not see.**

*Assumption, stated because it is one:* the vendor's counters are accurate and monotonic. If they
are not, every figure here moves.

An excess proves only that the key was used by something outside this log. **It is an attribution
measurement, never an accusation of a defect.**

## 3. The headline that is true and misleading

| | credits |
|---|---|
| counter advance over the window | 41,306 |
| attributable to our logged calls | 724 (**1.8%**) |
| not attributable | 40,582 (**98.2%**) |

Taken alone, "98% of our credit burn is unaccounted for" reads as an emergency. **It is not, and
reporting it without the next table would have been the kind of overstatement this programme
records against itself.**

## 4. Three episodes explain almost all of it

| when | gap | excess |
|---|---|---|
| 2026-08-07T15:00:56 | 0.19 h | **19,004** |
| 2026-08-07T14:03:04 | 0.96 h | **11,728** ← *the one M27 flagged* |
| 2026-08-06T18:52:04 | 2.00 h | **9,060** |

Those three total **39,792 credits — 98.8% of all unattributed burn** — and they fall on
**2026-08-06/07**, which is exactly when the **authorised historical backfill** was running under
`D025` (verification queries authorised) and `D029` (*"the backfill resumes immediately from its
saved state"*). That backfill does not write to `poll_log.csv`.

**Conclusion: authorised work by an unlogged process, not a leak.** M27 could not see this because
it was looking at one 57-minute slice of a two-day backfill.

## 5. The steady state is small

Since the 2026-08-08 cutover:

| | per day |
|---|---|
| ambient (unlogged) | **41.5** |
| our own logged calls | 34.0 |
| **combined** | **75.5** |

**Quota remaining: 31,622 → 419 days (13.8 months) at the current rate.**

The alarming alternative figure — 9.8 days — comes from averaging the one-time backfill into the
ongoing rate. It is wrong by a factor of forty and is exactly the arithmetic to avoid.

## 6. What cadence we can afford — the actionable part

| scenario | added/day | runway |
|---|---|---|
| status quo (hourly) | 0 | 419 days |
| per-book polling, M27 realistic mid | 144 | 144 days |
| bundled 5-min polling, 4 h/day | 144 | 144 days |
| bundled 5-min polling, 8 h/day | 288 | **87 days** |
| bundled 5-min polling, 12 h/day | 432 | **62 days** |
| per-book polling, M27 theoretical max | 411 | 65 days |

**Every scenario covers the rest of this season.** The 2024 season ran 2026-05-14 → 2026-10-20 in
our own analysis frame; from 2026-08-19 that is roughly 60 days. Even the most aggressive option
here clears it.

**So the answer to "can we afford to poll fast enough for the board to be useful" is yes,
comfortably** — and the blocker M27 asked to be cleared first is now cleared.

## 7. What this does NOT establish

* **Attribution is by counter arithmetic, not process identity.** This proves the burn was not
  ours and that it coincides with the backfill window. It does **not** prove the backfill caused
  it, because the backfill does not log per-call credits. A reader who wants certainty should
  instrument that script.
* **The ~41 credits/day steady-state ambient is real and still unidentified.** It appears in
  roughly daily episodes of 30–155 credits, consistent with a nightly scheduled job. Small enough
  not to threaten the quota, large enough to deserve a name.
* **Season end date remains unestablished** — flagged independently by `M07` and `M27`, and still
  true. Runway is therefore quoted in days, never as "to end of season".
* **Activation is not authorised here.** This node measures affordability. Turning polling up is
  an execution-mode and spend-adjacent change; `MARKET_PER_BOOK_POLLING_ENABLED` stays at its
  default-off and the decision is the user's.

## 8. Reproduce

```
python attribute.py            # print the analysis
python attribute.py --json     # also write FINDINGS.json
```

Reads `data/market_snapshots/poll_log.csv`. Writes nothing outside this directory. Makes no API
calls and consumes no credits.
