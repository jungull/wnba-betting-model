# M37 — the evidence ladder is asserted in reports and adjudicated nowhere

**E0-style diagnostic, NON-CLAIMING.** Not a graph node. Nothing here grades any opportunity
class, and nothing here may be cited as evidence that one does or does not hold a label.

M24's staking gate needed each class's M00 evidence-ladder rank and found nothing to read. This
asks the prior question: **is the ladder actually in use, and where?**

---

## The answer, in one line

**The ladder is used in node reports, never adjudicated in the ledger, and not one opportunity
class is graded by it.**

## 1. The ledger — where adjudication would live

| | |
|---|---|
| decisions in `DECISION_LEDGER.jsonl` | **178** |
| decisions naming any ladder label | **1** (`D142`) |

The ledger is where rulings live. In 178 rulings, the contract's central apparatus for what may
be claimed is named **once**.

## 2. The artifacts — where the labels actually appear

**23 assertions across 16 artifacts.**

| rung | label | assertions | negated |
|---|---|---|---|
| 1 | MARKET_MECHANISM_SUPPORTED | 4 | **4** |
| 2 | LINE_MOVEMENT_PREDICTIVE_ONLY | **0** | — |
| 3 | CLOSING_LINE_VALUE_SUPPORTED | **0** | — |
| 4 | HISTORICALLY_PROFITABLE | 2 | **2** |
| 5 | EXECUTION_FEASIBLE | 12 | 9 |
| 6 | PROSPECTIVELY_SUPPORTED | **0** | — |
| 7 | PRODUCTION_ELIGIBLE | 9 | 6 |

**Three rungs — 2, 3 and 6 — have never been mentioned anywhere in the market lane.** Rung 4,
HISTORICALLY_PROFITABLE, is mentioned twice and negated both times.

## 3. By class — the part that matters for M24

| class | assertions pairing it with a label |
|---|---|
| PURE_MICROSTRUCTURE | 4, **all negated** (MARKET_MECHANISM_SUPPORTED) |
| every other class | **0** |

Six of seven opportunity classes have **never** been paired with a ladder label in a single
sentence anywhere in the lane. The seventh is paired only with a negation.

**So M24's eligibility gate was right to fail closed, and now the reason is documented rather
than assumed.** It is not that a registry was never built; it is that there is nothing for a
registry to record.

## What this cannot do, and deliberately does not

**A scan of prose cannot adjudicate an evidence ladder.** Labels appear inside report bodies and
JSON string fields, most often *negated*. Counting those as evidence of a label held would
manufacture exactly the authority the programme lacks — worse than having no registry at all.

The output is therefore titled **ASSERTIONS FOUND**, never *labels held*, and
`any_class_holds_a_label` is a literal `false` in `LADDER_REGISTRY.json`. Adjudication is a
**ruling**; rulings belong in the ledger and are made by a person or a coordinator, not inferred
by a scanner.

## Two defects found in this file's own method, both fixed and recorded

**1. The negation regex under-detected, in the dangerous direction.** `\bno \b` failed to match
`` No `EXECUTION_FEASIBLE` `` because a backtick is not a word boundary. Two genuinely negated
HISTORICALLY_PROFITABLE assertions were classified UNCLEAR — making the evidence look *more*
supported than it was, which is the direction that matters. Fixed to `\bno\b` plus
*neither/none/without*.

**2. A false positive that would have been the headline.** Before the contract directory was
excluded, `TRUE_CROSS_BOOK_ARBITRAGE` appeared paired with **un-negated** EXECUTION_FEASIBLE and
PRODUCTION_ELIGIBLE — the single most consequential claim this scan could have produced. It was
an artifact: two unrelated fragments of one minified JSON line joined into a "sentence", inside
`TAXONOMY_AMENDMENTS.json`, which is part of the contract that *defines* the labels rather than
asserting them of a class. **Co-occurrence inside a long JSON line is not a semantic pairing.**

Both were caught by reading the underlying sentence before believing the count. Neither would
have been caught by the summary table alone.

## What follows from this

- **Do not build a ladder registry that infers labels.** There is nothing to infer from.
- **If the ladder is to gate anything, classes must be adjudicated explicitly in the ledger**,
  one ruling per class per label, with the evidence cited. That is a substantial act of
  governance and is not a coordinator's to do silently.
- **Until then M24's gate stays fail-closed**, which is the correct behaviour and now has a
  measured basis.
- **The contract's own machinery is unexercised.** Three of seven rungs have never been invoked;
  the ladder describes a promotion path that nothing has ever travelled.
