# M24 — the staking policy stakes nothing, by arithmetic

**DECISION-SYSTEM SPECIFICATION.** A staking policy is a frozen rule set evaluated in shadow
before any real-money question is even well-posed. This node specifies and backtests-in-shadow;
**activating any policy with money is USER_REQUIRED and is not this node's decision.**

---

## The result

Evaluated against the M23 shadow ledger — the only evidence criterion 4 permits it to read:

| | |
|---|---|
| shadow decisions sized | **34** |
| decisions receiving a non-zero stake | **0** |
| **total notional stake** | **$0.00** of a $1,000 bankroll |

**It stakes nothing by arithmetic, not by caution.** That distinction is the whole point of the
node: a policy that stakes nothing because someone decided to be careful can be argued out of by
the next person who feels differently. A policy that stakes nothing because the arithmetic on the
measured evidence returns zero cannot.

**Three independent rules each zero every one of the 34 decisions on their own:**

| rule | decisions zeroed | why |
|---|---|---|
| eligibility gate | 34 | fails closed — no machine-readable ladder status exists |
| max quote age | 34 | the quote was **406 s** old against a **300 s** cap |
| Kelly at the 95% lower bound | 34 | not one measured class has a positive lower bound |

## Kelly at the lower bound (criterion 1)

Kelly evaluated at a **point estimate** treats an uncertain edge as certain, and systematically
oversizes. This policy evaluates Kelly at the **95% lower confidence bound** instead. When the
interval includes zero — which is the case for every class this programme has measured — the
lower bound is at or below zero, the fraction is at or below zero, and the stake is zero
arithmetically.

The measured inputs, frozen in `SPEC.json` before this ran:

| class | expectation | source | positive lower bound? |
|---|---|---|---|
| MIDDLES_AND_DISLOCATIONS | negative | D152 | no |
| PURE_MICROSTRUCTURE | zero as income — a cost reduction | M22 | no |
| STALE_LINE_DELAYED_REACTION | unproven, 52% at the resolution floor | M08 | no |
| TRUE_CROSS_BOOK_ARBITRAGE | positive but immaterial ($0.20–0.83) | M22 | no |
| CONSENSUS_DISLOCATION | **−7.2%** against realised outcomes | D172 | no |
| MODEL_VS_MARKET_VALUE | no edge — and forbidden regardless | D141/D150, S42 | no |
| PROMOTIONAL_VALUE | largest per-unit value measured, no real offer ever entered | M22 | no |

## An unplanned finding: the freshness rule rejects the board's own decisions

The 300-second maximum quote age was set from the measured 5-minute capture cadence (M03) —
a quote older than one full cadence cannot be shown to have been standing. M23's decisions were
made on a quote **406 seconds old**, so **the policy rejects the board's own output on freshness
alone.**

That was not designed; it fell out of applying the rule. It means the gap between capture and
decision currently exceeds one cadence, so either the cap is too tight or the decision path is
too slow. It is recorded here rather than resolved, because tuning a freshness cap to admit the
decisions you already have is exactly how a rule stops being a rule.

## Exposure, drawdown and the risk-control map (criteria 2 and 3)

Exposure caps as a percentage of bankroll: **1.0 per decision, 2.0 per game, 1.0 per market,
5.0 per book, 6.0 per day.** Caps bind in order and **the binding constraint is recorded on every
sized decision**, so a stake can always be traced to the rule that limited it.

Drawdown rules, frozen before evaluation: **3.0% daily loss cap, 10.0% trailing drawdown stop,
5 consecutive losing days**, plus a manual global kill switch. Re-enabling after any stop is
USER_REQUIRED.

Against M00's eleven hard risk controls, **three are NOT covered and are named rather than
glossed**: per-player exposure caps (the board's classes are game-level), correlated-order
conflict (correlation between legs across markets on one game is not modelled), and trading
through a suspension (M17 is not built).

## Tests

**32 checks, all passing.** The suite proves the claim in **both** directions, because
"stakes nothing" is untestable on its own — a policy hard-wired to return zero would pass every
other check in the file. So it also verifies that a fully-qualified decision **does** receive a
non-zero stake, that an exposure cap can bind, that a stale quote zeroes an otherwise-qualified
stake, and that a stake never exceeds measured liquidity.

One test failed on first run and the fix went into `policy.py`, **not** into `SPEC.json`: the
per-result authorisation note carried the spec's statement but not the operative term
`USER_REQUIRED`. `SPEC.json` declares `frozen_before_evaluation: true`, and editing it after the
evaluation had run would have made that declaration false. The note is now composed from both
spec fields at read time.

## What this does not establish

- **No profit-and-loss evaluation exists**, and none was attempted. The 34 decisions are on games
  commencing 2026-08-22/23 and **no outcome has been observed**. A staking policy that stakes zero
  needs no outcomes to be assessed — but it also earns no evidence from their absence.
- **Nothing here is authorised.** Every figure is notional. Real-money activation is a mode
  transition, is never self-grantable by this lane, and is outside this node entirely.
- **The eligibility gate has nothing to read.** The M00 contract defines a seven-rung evidence
  ladder, but **no per-class ladder status is recorded anywhere machine-readable**. The gate
  therefore fails closed on every class. That absence is a real gap in the contract's machinery,
  not a property of the opportunities.
- **The quarter-Kelly cap is a judgement**, recorded as one. It is not derived from anything this
  programme measured.
- **Correlated exposure is not modelled.** Caps are per-market and per-game but assume
  independence between them, which is false for legs on the same game.
