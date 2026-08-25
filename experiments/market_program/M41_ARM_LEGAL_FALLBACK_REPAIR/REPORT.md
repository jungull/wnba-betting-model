# M41 — M38's repair is not implementable as measured; a legal one recovers most of it

**E0-style diagnostic, NON-CLAIMING.** Nothing here fits, adopts or ships a model. S42 untouched.
Re-run with `python s01_arm_legal.py`.

## Why this was run

M38 s03 (D184) is recorded as the programme's **best model-side lead**: two walk-forward repairs
closing **21.3%** of the model's deficit to the market on held-out 2026. The handoff names it as
the thing to implement next.

Before building an arm revision on it, it was checked — the D201 lesson, where a headline that had
never been re-derived turned out to be wrong.

**The 21.3% reproduces exactly.** The arithmetic is not the problem. What the repair *reads* is.

## The defect: the constant is computed on the priced population

Both constants in `s03_two_repairs.py` are means over M33's **priced frame** —
`prior["rate_actual"].mean()` and `prior["min_actual"].mean()`, where `prior` is the subset of rows
that carried a market price. The arm cannot use that, for two independent reasons:

1. **It is outside the arm's file boundary.** The arm reads the contract and the masters, read-only.
   Market data is not in that boundary, so an arm cannot compute a priced-population constant at all.
2. **The priced population is selected on the quantity being predicted.** Bookmakers price starters
   and rotation regulars.

| season | priced-population mean minutes | all-rows mean minutes |
|---|---|---|
| 2025 | 30.56 | 21.45 |
| 2026 | 29.63 | 21.41 |

**An 8–9 minute gap.** Using the priced constant would also mean predicting ~30 minutes for
deep-bench players on every unpriced row — the arm emits predictions for all candidates, and only a
minority are ever priced. The repair is scored only where it flatters itself.

## What it is worth when made legal

Substituting a constant the arm *can* compute — prior-season mean minutes over all rows that played:

| variant | held-out 2026 | gap closed |
|---|---|---|
| current model | −0.3108 | — |
| priced constant (M38, **not arm-legal**) | −0.2447 | 21.3% |
| arm-legal **global** constant | −0.2917 | **6.2%** |
| arm-legal **her own prior-season mean** | −0.2495 | **19.7%** |

## The lead survives, in a better form

**Level 3 does not mean "no history" — it means "no appearance *this season*."** 156 of 168 level-3
rows (**93%**) belong to a player with prior-season minutes of her own.

Using **her own prior-season mean**, falling back to the global constant only when she has none,
closes **19.7%** — nearly all of the leaked figure, using nothing but the masters. It is strictly
*better* than what M38 proposed and it is legal.

## A look that had to be declared

The own-history variant was written **after** seeing the global variant score 6.2% on the held-out
season. That is a second look at 2026, and a figure chosen that way is not out-of-sample.

So the variants were re-selected on **seasons < 2026 alone**, exactly as s03 chose its shrinkage
weight:

| variant | selection (seasons < 2026, n=3884) |
|---|---|
| current | −0.3084 |
| arm-legal global constant | −0.2719 |
| **arm-legal own prior-season mean** | **−0.2351** ← wins |

Own-history wins the selection outright, so **the choice does not depend on the holdout**. The
ordering is recorded rather than asserted later.

## Limits

- The shrinkage weight **w = 0.60 is frozen** from M38 s03 and was not re-tuned here. Re-tuning it
  alongside a changed level-3 rule would be selecting two things on one holdout.
- Held-out n = 2005 priced rows; level 3 is only 168 rows in the full frame.
- The level-2 repair is unchanged and still uses a global prior-season **rate**; whether a per-player
  prior-season rate helps there was **not** tested, and should be, on the same select-then-confirm
  discipline.
- Nothing is implemented. The arm is a registered artifact and changing it is a new revision.

## What this does not show

**The model still loses.** −0.2495 is closer to the market than −0.3108 and is still negative: the
market remains better on the priced population. Closing part of a deficit is not an edge, and
nothing here revisits M32's −7.2%.
