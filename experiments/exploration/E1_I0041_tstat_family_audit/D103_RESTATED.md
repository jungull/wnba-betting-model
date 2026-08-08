# D103_RESTATED — the corrected blind count, with evidence

**Corrected figures and evidence only. I do not revise D103. The coordinator rules.**

Reconstruction check first: my recomputation of D103's own `mde80_fw` for all 666 `t_statistic`
cells, from the two screens' published null columns and D103's own `t_crit` at full stored
precision, agrees with the published values to **1.07e-13 relative** (max absolute difference
9.98e-17). The corrections below are applied to the published quantity itself.

---

## Headline

| | cells | blind to 0.0023 (family-wise) | share | move |
|---|---:|---:|---:|---:|
| **as published** | 1,349 | **760** | **0.5633802816901409** | — |
| **R-A** — folded sd corrected, everything else untouched | 1,349 | **886** | **0.6568** | **+126, +9.34 pp** |
| R-B — each screen's own family-wise bar | 1,349 | 908 | 0.6731 | +148, +10.97 pp |
| R-C — Šidák-normal bar, K independent cells | 1,349 | **613** | **0.4544** | **−147, −10.90 pp** |

**The figure I put forward is R-A: 886 of 1,349, 65.68 %, +126 cells.** It repairs a category
error — a folded standard deviation fed to a formula derived for a signed statistic — and changes
nothing else about D103's design, its thresholds, its key or its benchmark. R-B and R-C bracket a
separate question, the choice of family-wise bar, which is D103's design decision and not mine to
overturn.

**Direction: D103 understates the blindness of its `t_statistic` family. Its qualitative
conclusion — that many recorded nulls are uninformative rather than evidence of absence —
survives and strengthens.** The counter-result R-C, which reverses the sign by almost the same
magnitude, is given equal weight in §4.

---

## 1. Where the 126 cells come from

Only `E0_I0014_residual_heterogeneity` is affected by R-A, because only it stores a folded null.

| screen | cells | blind as published | blind under R-A | move |
|---|---:|---:|---:|---:|
| E0_I0014_residual_heterogeneity | 348 | 203 | **329** | **+126** |
| E0_I0019_availability_forecast | 318 | 315 | 315 | 0 |
| all other families (`increment`, `paired`) | 683 | 242 | 242 | 0 |

E0_I0019 does not move under R-A because `nullsd_between` is already the sd of the **signed** t
(`s04_screen.py:181` stores `tt`, not `abs(tt)`; 14 %–50 % of its stored draws are negative).
E0_I0019 was already 315/318 blind, so it has almost no room to move in that direction anyway.

Per-cell ratio of corrected to published floor, E0_I0014, R-A:

| | min | p10 | median | p90 | max |
|---|---:|---:|---:|---:|---:|
| all 342 cells with a finite ratio | 2.458 | 2.716 | **3.205** | 115.0 | 6.8e+31 |
| excluding the 72 degenerate/zero-width cells | 2.458 | 2.707 | **2.950** | 10.53 | 25.9 |

The half-normal expectation is 2.752. The bulk sits just above it because the real permutation
clouds are slightly heavier-tailed than normal; the extreme tail is the degenerate cells of §3,
where the moment recovery is an upper bound rather than an equality and the number should be read
as "unverifiable", not as "115× too small".

## 2. The evidence for R-A

Three independent legs, all pre-registered:

1. **At source.** `E0_I0014/s04_screen.py:211` — `v = np.abs(tvec(yt, Xx, NS)[1])`. The stored
   draws are |t|. Confirmed empirically: all 18 saved null arrays have `frac_negative = 0.0000`
   and `min = 0.000000`. `null_correct_sd` (`s04_screen.py:291`) is `nb.std(ddof=1)` of that
   folded array, and my recomputation of it from the `.npz` matches the published column to a
   maximum absolute difference of **2.22e-16** over all 348 cells.
2. **The recovery is exact.** `sd(t)² = sd(|t|)² + mean(|t|)²` whenever `E[t] = 0` — no shape
   assumption. Validated against the truth in simulation, where both the signed and folded draws
   exist: median relative error **0.00032**, p90 0.0052, max 0.046 over 192 conditions. Validated
   again in `PROPOSED_FIX/test_mde_tscale.py` T2–T3 on normal, Student-t₃, Laplace and uniform
   nulls at 200,000 draws — relative error < 1e-5 in every case.
3. **The consequence is what simulation says it is.** With a signed sd and a per-cell bar, the
   published formula reproduces an injection-verified floor at a ratio of **0.995**
   (p10 0.927, p90 1.071). With the folded sd it reproduces it at **0.359** (p10 0.338,
   p90 0.386) — i.e. the floor is 2.79× too small. The pre-registered prediction was 0.36. This
   ratio is invariant to block count (0.344–0.370 across 36/64/128/475/489/1486), to
   autocorrelation (ρ = 0: 0.361, ρ = 0.5: 0.356), to block-length imbalance (0.355/0.362) and to
   the between-block variance share (0.354–0.363), exactly as pre-registered.

## 3. What R-A does *not* fix: 73 cells whose null collapsed

* **67 cells** have `mean(|t|)/sd(|t|) > 5`, against ≈1.32 for any symmetric distribution
  (66 in E0_I0014, 1 in E0_I0019). Their permutation null is a tight cloud far from zero: the
  shuffle is not shuffling anything.
* **6 further cells** have a null sd of **exactly zero**. `mde80_tscale` returns **exactly 0.0**
  for them. All six are recorded as perfectly powered.
* **35 of the 73 are counted by D103 as adequately powered** — i.e. their recorded negative
  results are treated as informative evidence of absence.

For these cells `E[t] = 0` is not credible, so the moment recovery is only an upper bound and no
corrected floor can be quoted. The correct status is **UNVERIFIABLE**, not "blind" and not
"powered". R-A counts 55 of the 73 blind (their recovered floors are large) and 18 not blind; an
equally defensible treatment removes all 73 from **both** numerator and denominator, giving
**886 − 55 = 831 blind of 1,276 scoreable cells = 0.6513** — statistically indistinguishable from
R-A's 0.6568, because the unusable cells split in roughly the family's own proportion. Both are
reported; neither is smuggled in.

## 4. R-C, the result that runs against this restatement

The Šidák-normal bar for K independent two-sided tests is **3.795 sd** at K = 348 and **3.773 sd**
at K = 318 — confirmed by direct simulation on 60,000-draw null clouds (measured 3.67–3.79 across
sixteen panel configurations). Measured in each cell's own correct sd(t):

| | D103's published bar | the screen's own bar | Šidák |
|---|---:|---:|---:|
| E0_I0014 | **3.735 sd** | 15.86 sd | 3.795 sd |
| E0_I0019 | **6.974 sd** | 6.744 sd | 3.773 sd |

Read that table honestly. **Against the Šidák benchmark, D103's published E0_I0014 bar is right to
1.6 %** — the folding error and the borrowed-`t_crit` error cancel — and its E0_I0019 bar is 85 %
too far out, making those floors ~2.85× too *large*. Under R-C the family becomes *less* blind:
613 of 1,349, 45.44 %, **−147 cells**.

Why I still prefer R-A over R-C: R-C changes two things at once (the sd *and* the bar) and its bar
assumes the K cells are independent, which they are not — real between-cell correlation lowers the
true bar further, which would push R-C's count lower still. R-A changes exactly one thing and that
thing is unambiguously wrong. But R-C is a coherent position, it moves the headline by almost
exactly as much in the other direction, and a coordinator who takes D103's threshold convention as
the object of the retrospective should prefer it.

Why R-B rather than R-C as the "what actually happened" reading: E0_I0014's recorded verdicts came
from `p_familywise_whole_screen`, an **unstandardised** max|t| bar of **29.13** (q95 of its own
1,000-draw max|t| null), and E0_I0019's from `p_familywise`, an unstandardised bar of **8.68**.
Those are the rules that produced the negative results being retrospected. E0_I0014's bar works
out to 15.9 of a median cell's own noise widths because its family-wise procedure takes an
unstandardised maximum across cells whose null widths span two orders of magnitude — **that is a
defect in E0_I0014's own procedure, not in D103's conversion**, and it is the single largest
contributor to R-B. Flagged here for routing, not adjudicated.

## 5. Standing D101 caveat on every figure above, mine included

D103 compares each cell's floor — a ΔR² **of that cell's own response, row set, SST basis,
weighting and base** — against 0.0023, a ΔR² on D089's walk-forward points. E0_I0014's responses
are |residual| and squared residual of minutes / points / FGA; E0_I0019's are Brier-skill
differences against reference forecasts. These are different SST bases. The comparison is D103's
own design and it applies identically to all three `stat_family` groups, so it does not affect the
*relative* corrections in this document — but the absolute blind counts, published and corrected
alike, inherit it. E1_I0037 did not raise this and it should be on the record.

## 6. Summary for the ledger

* D103's `t_statistic` family: **666 cells, 518 blind as published.**
* Corrected for the folded standard deviation only: **644 blind in that family**, total
  **886 / 1,349 = 0.6568**, a **+9.34 point** move.
* Range across defensible family-wise-bar conventions: **0.4544 – 0.6731**.
* **73 cells (11 %) have a null that did not function and should be UNVERIFIABLE in any version.**
* **D103's qualitative conclusion holds under every treatment.** Its headline *number* is
  ±11 points less determinate than published.
