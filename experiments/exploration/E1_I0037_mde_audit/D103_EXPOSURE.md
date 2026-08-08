# D103_EXPOSURE — does the power audit need restating?

**Correction factor and evidence only. I do not revise D103's numbers; the coordinator rules.**

## Headline

**D103's qualitative conclusion survives intact, and its headline moves by +0.44 percentage
points in the direction it already pointed.**

| | cells | blind to 0.0023 (family-wise) | share |
|---|---:|---:|---:|
| **as published** | 1,349 | 760 | **0.5634** |
| **after the H_B correction** | 1,349 | 766 | **0.5678** |
| movement | — | **+6 cells** | **+0.44 pp** |

D103 said its negative record is weak. After correction it is very slightly weaker. Nothing about
"56.3 % of recorded cells could not have detected the programme's own best finding" needs
withdrawing or softening.

## Why the exposure is small: only 2.2 % of D103's cells use the affected construction

D103 computes MDE three different ways, and only one of them takes an sd from an effect-carrying
sign-flip:

| `stat_family` | cells | share | sd comes from | affected? | validated by D103? |
|---|---:|---:|---|---|---|
| `increment` | 653 | 48.4 % | screens' **permutation** nulls (carrier permuted) | **No** | **Yes** — median analytic/simulated 0.989, p10–p90 0.78–1.11, n = 192 |
| `t_statistic` | 666 | 49.4 % | screens' **permutation** nulls, classical-t scale | **No** | **NO — never validated** |
| `paired` | **30** | **2.2 %** | E1_I0023's **observed paired loss-difference** sign-flip | **YES** | **NO — never validated** |

The affected family is entirely `E1_I0023_usage_defence_interaction`, whose `null_sd_cluster` is
`screenkit.paired_forecast_comparison`'s `sd`, fed to
`s06_retrospective.py::mde80_paired(sd, t_crit) = (t_crit + 0.8416)·sd`.

## The correction, by hypothesis, kept separate

### H_A — contamination of `null_sd`. Direction: D103's paired floors are **overstated**.

Contamination inflates the sd, so removing it makes floors **smaller** and cells **less** blind.
I cannot point-estimate it for E1_I0023 (I do not hold its loss vectors and it is outside my write
scope), so I bound it from the two real cells I did measure: contamination ∈ **[1.00, 2.44]**.
**Upper bound: up to 24 of the 30 paired cells could be *less* blind than published.** This
correction runs *against* D103's conclusion and is reported for that reason.

### H_B — miscalibration of the rule. Direction: D103's paired floors are **understated — infinitely so**.

E1_I0023's cells have **48 clusters**. D103 applies a family-wise `t_crit` of **6.974**
(`s04_familywise_thresholds.csv`, N2_entity_swap, K = 132). Since

```
t_crit = 6.974  >=  sqrt(48) = 6.928
```

the rejection threshold `t_crit · sd(e)` grows with the effect faster than the statistic does.
**Verified by simulation, not algebra** (`s05`, `infinite_mde_verification.csv`): sweeping the
effect from 0.5 SE to 10,000,000 SE, **maximum power attained = 0.0000**. Controls in the same
run: the same cells at the per-cell threshold 1.645 reach 80 % power at 2.76 SE; nb = 60 at the
same `t_crit` reaches it at 20.3 SE.

**So all 30 paired cells have an infinite family-wise MDE.** D103 publishes finite values for them
(median `mde80_fw` 0.0044) and counts 24 of the 30 blind. The correct count is 30 of 30 — not
because their floor is high, but because at that threshold **they have no floor**. The published
number is not conservative; it is not a floor at all.

**Net: 760 → 766 blind. H_B adds 6 cells; H_A could remove up to 24 in the other direction but
only from a family that H_B has already made infinite, so H_A is dominated and does not apply.**

## What this does NOT do

* It does not validate E1_I0035's 6.6×. The mechanism here is the **critical value** and it bites
  only at `t_crit ≥ √nb`. E1_I0035's cell has 488 blocks against `t_crit` 1.96 — `√488 = 22.1`,
  nowhere near the boundary, H_B factor **1.005**.
* It does not touch the 1,319 cells on permutation nulls. Their sd does not scale with the effect,
  and D103's `increment` family was independently validated against a 5,616-row simulated power
  surface.
* It does not make D103 *anti*-conservative overall. The brief's worry — "D103 is understating the
  problem" — is correct in sign but the magnitude is 0.44 pp, not a re-statement.

## The exposure that is larger than this one

**`t_statistic`: 666 cells (49.4 %), carrying 518 of the 760 blind verdicts (68.2 %).**

`s06_retrospective.py::mde80_tscale` converts a classical-t-scale null width to the ΔR² scale via
`MDE80 = ((t_crit + z₈₀)·sd_t)² / n`. D103's `validate()` gate — `assert abs(median ratio − 1) <
0.15`, which passed at 0.989 — reads `s04_mde_table.csv`, and every row in that file is an
`increment` cell on a permutation null. **The conversion carrying two-thirds of D103's blind
verdicts was never put through the gate that D103 built to protect exactly this.**

I have not quantified it. It is a different defect (a scale conversion, not an effect-carrying
null), it needs a different simulation, and E1_I0038 is already loaded. **Recommendation: this is
the next power screen, not another pass at the sign-flip null.**

## Also affected outside D103 — for the coordinator's routing, not adjudicated here

* **E1_I0033_aggregation_level** — 24 quoted figures, all exactly `2.800 × null_sd` on a paired
  block sign-flip at team-season, **36 blocks**. H_B factor **1.085**. Two cells turn on the
  floor and both have near-zero observed effects, so H_A does not rescue them: **P02** ("significant
  *and* underpowered", floor 0.25118) and **s10** (floor 0.00583684, observed −0.00004). Both get
  **~9 % more underpowered**, not less. Its `NOTES.md` §5 heads that table "Power verified by
  injection" while the values are the analytic form to 16 significant figures — that label should
  be corrected whatever else is decided.
* **E1_I0034_redistribution** — 71 quoted figures on the same construction. Its three reported
  anti-conservatism ratios imply, under the block-count law, **effective block counts of 16.1
  (minutes), 8.1 (attempts) and 4.9 (points)**. The last is **below six**, where the sign-flip
  cannot reject at all. That is a falsifiable prediction against that screen's own cluster counts
  and I recommend E1_I0038 check it.
* **E1_I0035_availability_sum** — 17 quoted figures. Its own judgement (publish both, treat
  injection as authoritative, no verdict changes) was right.
