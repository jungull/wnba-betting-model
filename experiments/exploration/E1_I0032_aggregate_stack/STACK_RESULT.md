# Do fractional improvements aggregate?

**Yes — but only two of the six do any work, and the big one only helps players you would never bet on.**

You said you didn't care how small an improvement is, you wanted them to aggregate. That was the
right instinct and the power analysis backed it: measuring the whole stack once is a stronger test
than measuring the pieces separately. So we built the stack, measured it once, and then tried to
break it. Here is what came back.

---

## 1. The stack's gain, measured once

One row set (13,808 player-games, 2022–2024), one denominator, walk-forward, against the champion's
own stored forecasts. Nothing about the champion was refitted.

| target | everybody (13,808 rows) | the players you'd bet on (5,107 rows) |
|---|---|---|
| **points** | **+0.0342** (p 0.0003) | **+0.0035** (p 0.029) |
| **minutes** | **+0.0494** (p 0.0003) | **−0.0052** (p 0.0003) — **worse** |
| **attempts** | **+0.0430** (p 0.0003) | +0.0011 (p 0.30) — nothing |
| **points per minute** | **+0.0143** (p 0.0003) | **+0.0068** (p 0.0008) |

Those are shares of explainable variance. In plain accuracy terms, pooled: points error falls from
4.183 to 4.029 (−3.7%), minutes from 5.049 to 4.727 (−6.4%), attempts from 2.628 to 2.492 (−5.2%).

**The pooled numbers look excellent and they are mostly one thing: repairing the 947 games where
the model was printing a constant.** Strip those 947 rows out and the whole stack is worth +0.0015
on points, +0.0019 on points-per-minute, and nothing at all on minutes and attempts.

**And here is the number that matters most for betting: not one of those 947 rows is in the
decision stratum.** Zero. By construction — the routing targets players with almost no history, and
the decision stratum requires at least eight prior games. So the largest, best-evidenced,
double-corroborated component in the whole programme contributes **exactly nothing** to the
population you would actually put money on.

## 2. Is it real, or did we select twenty numbers for their sign?

We built a matched fake stack: same six slots, same functional forms, same fitting, same nulls, same
rows, same denominator — random routing target, random half-lives, random shrinkage, opponent
ratings shuffled between opponents, a pre-existing noise column standing in for teammate volume, and
a coin-flip home flag. It went through the identical pipeline.

**The fake stack shows no gain anywhere.** On nine of twelve cells it is negative. On the three
where it is positive the largest is +0.0004 at p 0.24 — indistinguishable from zero, and 87 times
smaller than the real stack on the same cell.

So the real stack's gain is not an artefact of picking components because they measured positive.
That was the failure mode we were most worried about and it did not happen.

One honest caveat: on the strictest cut (points, excluding the repaired rows) the real number is
+0.0015 and the placebo is +0.0004 — only about 4× apart. That cell is the weakest thing in the
report.

## 3. Which pieces are load-bearing

Remove each component from the finished stack and re-measure. Positive = removing it hurts.

| component | points | minutes | attempts | ppm | verdict |
|---|---|---|---|---|---|
| **routing the fallback rows** | +0.0326 | +0.0497 | +0.0424 | +0.0125 | **load-bearing — and all of it outside the betting population** |
| **shrinking to the player's own prior season** | +0.0059 | 0 (by design) | +0.0047 | +0.0249 | **load-bearing** |
| **opponent defence, applied selectively** | +0.0017 (p 0.007) | −0.0001 | +0.0004 (p 0.11) | +0.0018 (p 0.002) | **load-bearing — and it is the ONLY thing that works on the betting population** |
| per-target EWMA half-lives | −0.0001 | −0.00002 | 0 | −0.0001 | **not load-bearing** |
| teammate volume | −0.0004 | −0.0002 | +0.000001 | −0.0002 | **not load-bearing; actively harmful on minutes** |
| home / away | +0.0001 | +0.000004 | +0.00002 | +0.0001 | **not load-bearing** |

Two results deserve calling out.

**Teammate volume is worse than useless in a stack.** On the decision stratum it costs minutes
−0.0049 at p 0.0005 — that single component is what turns the stack's minutes result negative there.
D101 had already downgraded its evidence; this says it should come out.

**Opponent defence is the only component that survives on the players you'd bet on**: points
+0.0033 (p 0.020), points-per-minute +0.0059 (p 0.0013). The ledger has it filed as raised, not
accepted. On this evidence it is the one worth promoting.

## 4. Where does the curve flatten?

Adding components one at a time, biggest published claim first (points, everybody):

| step | added | cumulative | this step added |
|---|---|---|---|
| 1 | routing | +0.0268 | +0.0268 |
| 2 | per-target half-lives | +0.0268 | +0.00002 |
| 3 | own-prior-season shrinkage | +0.0328 | **+0.0059** |
| 4 | opponent defence | +0.0345 | **+0.0017** |
| 5 | teammate volume | +0.0341 | −0.0004 |
| 6 | home / away | +0.0342 | +0.0001 |

**It flattens after step 4, and steps 5 and 6 go backwards.** Every other target tells the same
story: minutes flattens after step 1, attempts and points-per-minute after step 4.

**So the practical answer to "how far do fractional improvements aggregate" is: about four
components, and only two of those four carry real weight.** The two smallest genuinely-established
effects in the programme — teammate volume and home advantage — did not aggregate. They contributed
nothing and one of them subtracted.

That is a real answer to your question rather than a hedge. Effects at the 1e-4 scale, which is what
home advantage is, cannot aggregate here: the whole stack's own noise band is ±0.004, forty times
larger. There is nothing clever to do about that — D103 measured it and it is a sample-size fact.

## 5. Are the components redundant — the same signal under different names?

Mostly **no**, which was the surprise. The sum of the six ablation deltas comes to 0.85–1.16 times
the whole stack's gain on eleven of twelve cells. Real redundancy would have shown a large shortfall
and it is not there.

But that is a less impressive result than it sounds, because only two components carry anything, and
they are not competing for the same signal — one repairs a broken region and the other adds an
opponent term everywhere else. **You don't get redundancy when you only have two things.**

The one exception is points-per-minute pooled, where the parts sum to 2.7× the whole. There the
routing on its own makes things **worse** (−0.0125) and the shrinkage rescues it (+0.0249) — a
genuine interaction, and the reason the ledger's instruction to verify per target matters.

## 6. Availability

Kept separate, because it is a yes/no outcome and cannot be added to a points number without
breaking the comparability rule. The long-absence recalibration D090 asked for does work on the v15
arm: Brier 0.0871 → 0.0859, +1.40% skill at p 0.027, against a placebo version at +0.02% and p 0.94.
On the v14 arm it is +0.96% at p 0.13 — the right direction, not significant.

It also cannot help the stack even in principle here: every scored row is a game the player actually
played, so an availability correction has nowhere to act.

## 7. What we'd do with this

1. **Ship the fallback routing** — but describe it accurately. It is a repair worth 3.7–6.4% of
   error pooled, on 6.9% of games, and it is worth **zero** on the players you bet. Route per target
   and verify per target: on points-per-minute, routing without the shrinkage makes things worse.
2. **Promote opponent defence from raised to accepted.** It is the only component that works where
   it matters, it survives a correct-level null on two targets, and its placebo is clean.
3. **Drop teammate volume.** Two independent lines now point the same way and this one shows real
   harm in combination.
4. **Do not add a home term.** D104 said so on arithmetic; the stack confirms it empirically.
5. **Stop adding components.** The curve is flat after four. The next gain has to come from a
   genuinely new mechanism or from more data, not from stacking more small effects.

## What this does *not* say

Nothing here has been tested against a market, and nothing here has touched 2025 or 2026. A 3.7%
reduction in pooled points error, concentrated in games involving players with almost no track
record, is not evidence that anyone can beat a line.
