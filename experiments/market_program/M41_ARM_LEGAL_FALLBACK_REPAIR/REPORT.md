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

---

# s02 — per-player history helps level 2 as well, and the legal repair overtakes the leaky one

`python s02_level2_own_rate.py`

s01 left one limb untested: level 2 still shrank the fitted rate toward a **global** prior-season
rate. Asking the same question of it:

| variant | selection (seasons < 2026) | held-out 2026 | gap closed |
|---|---|---|---|
| current model | −0.3084 | −0.3108 | — |
| level 2 toward **global** prior rate | −0.2351 | −0.2495 | 19.7% |
| level 2 toward **her own** prior rate | **−0.2221** | **−0.2230** | **28.3%** |

95% of level-2 rows have a prior-season rate of their own. Selection on seasons < 2026 picks
own-history independently, so the choice does not depend on the holdout.

**The combined arm-legal repair — per-player prior-season minutes at level 3, per-player
prior-season rate at level 2 — closes 28.3%, more than M38's non-legal 21.3%,** while reading
nothing but the masters.

The rate is computed as prior points ÷ prior minutes — a ratio of sums, not a mean of per-game
ratios, so a two-minute appearance does not weigh as much as a thirty-five-minute one.

## The result contradicted the prediction, and the file argued with itself

A level-2 row *already carries* current-season evidence, so the shrinkage target could have
mattered **less** here than at level 3. It matters **more**. One or two games of current-season
EWMA is a worse estimate of a player's scoring rate than her whole previous season — which is what
`cbs_v7` meant by "a fallback wearing a model's clothes", now measured.

**A method defect, found and fixed in this file:** that explanation was pre-written for a null
result and printed *unconditionally*, so it argued the target "matters less" directly beneath
numbers showing it mattering more. A rationalisation that fires whatever the result is worthless.
It is now confined to the branch it describes.

## The holdout is being spent — stop selecting on 2026

This is the binding constraint on any further work here, and it is easy to miss because each
individual step looked disciplined.

2026 has now been consulted by **M38 s03** (four variants), **s01** (four), and **s02** (three) —
roughly a dozen evaluations. Every one was a legitimate *confirmation* of a choice made on earlier
seasons, and that is the right procedure. But a holdout confirmed against a dozen times is no
longer a clean holdout: the surviving variant is partly selected by which confirmations were run.

Concretely, **`w = 0.60` should not now be re-tuned against the new targets on 2026**, even though
selecting it on seasons < 2026 and confirming once would be procedurally correct. The frozen weight
is the conservative choice and it stays frozen.

The next honest test of this repair is **not another variant**. It is the 2026 games that have not
been played yet — which arrive daily — or the implementation itself, scored prospectively.

## Still not an edge

−0.2230 is negative. The market remains better on the priced population. Nothing is implemented.
