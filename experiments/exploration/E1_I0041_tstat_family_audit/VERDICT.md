# VERDICT — E1_I0041, audit of D103's `t_statistic` scale conversion

**D103's `t_statistic` conversion turns a null width measured on the classical-t scale into a
detection floor on the ΔR² scale by `MDE80 = ((t_crit + z₈₀)·sd_t)² / n`, and its arithmetic is
sound**: fed a signed null sd and a correctly calibrated bar it reproduces an injection-verified
floor to a median of **0.989** across 96 clustered, unbalanced, autocorrelated conditions (p10
0.933, p90 1.052), and the scale identity it rests on — ΔR² = t²/(t²+df) — holds on the real cells
to a median ratio of **1.0000**. **What is wrong is what gets fed into it. For E0_I0014's 348 cells
`sd_null_t` is the standard deviation of |t| — a folded variable, 0.60× the signed sd the
derivation assumes — and for all 666 cells `t_crit` is the standardised maximum of a ΔR²
statistic (6.686 / 6.974 sd) applied as though it were a number of t-scale sds, where the
correctly calibrated bar is 3.795 / 3.773 sd.** Direction and size: correcting only the folding —
the one defect that is a category error rather than a defensible design choice — moves D103's
blind count from **760 to 886 of 1,349, 56.34 % → 65.68 %, +9.34 points**, twenty-one times the
+0.44 points E1_I0037 found. **D103 understates how blind its `t_statistic` family was. Its
qualitative conclusion survives and strengthens.**

---

## 1. The two input defects run in opposite directions and nearly cancel

This is the finding, and it is why nobody caught it.

| | E0_I0014 (348 cells) | E0_I0019 (318 cells) |
|---|---:|---:|
| `sd_null_t` is | **sd(\|t\|)** — folded | sd(t) — signed |
| folding factor on the bar | **× 0.559** (measured median fold 1.79; half-normal theory 1/1.659 = 0.603) | — |
| `t_crit` vs the correct bar | 6.686 vs 3.795 sd → **× 1.762** | 6.974 vs 3.773 → **× 1.849** |
| net bar, in the cell's own sd(t) | **3.735 sd** (correct: 3.795) | **6.974 sd** (correct: 3.773) |
| net error on the floor (per-cell median, corrected ÷ published) | **1.12×** excluding degenerate cells, 1.22× including — two wrongs, one near-right | **2.85×** — conservative |

Against a properly calibrated family-wise bar, E0_I0014's published bar is right to within
**1.6 %** and its floors to within ~12 % on the median cell, entirely by accident: a sd that is
44 % too small is multiplied by a critical value that is 76 % too large. (The bar figure comes
from medians; the floor figure is the median of the per-cell ratios, which is the larger of the
two because the ratio's distribution is right-skewed.) E0_I0019, which has the *correct* sd, gets
no such cancellation and its floors are ~2.85× too large. **Neither screen's floor is right for
the right reason.**

Both halves were measured, not asserted:

* the folding factor, on the real cells, by exact moment recovery from E0_I0014's own saved
  draws — `sd(t)² = sd(|t|)² + mean(|t|)²` under `E[t]=0`, validated in simulation to a median
  relative error of **0.00032** (p90 0.0052) against the true signed sd;
* the correct bar, on a **60,000-draw null cloud with a held-out calibration half**, giving
  3.67–3.79 sd across sixteen panel configurations — the Šidák-normal value to two decimals.

## 2. The reference bar matters more than either defect, and it cuts both ways

`t_crit` is not the only candidate bar, and the answer depends on which one the retrospective is
supposed to reproduce. All three are computed on all 1,349 cells, using D103's own key and its own
0.0023 comparison, and the control reproduces 760 exactly.

| correction | blind / 1349 | share | move |
|---|---:|---:|---:|
| **as published** | 760 | 0.5634 | — |
| **R-A — fold fixed only, D103's `t_crit` untouched** | **886** | **0.6568** | **+126 cells, +9.34 pp** |
| R-B — each screen's **own** published family-wise bar | 908 | 0.6731 | +148 cells, +10.97 pp |
| R-C — Šidák-normal bar for K independent cells | **613** | **0.4544** | **−147 cells, −10.90 pp** |

**R-A is the figure I stand behind**, because it repairs a category error and changes nothing else
about D103's design. R-B is what the retrospective question literally asks for — the rule each
screen actually applied to declare the verdicts being retrospected — and it moves further in the
same direction. **R-C moves the other way by almost exactly as much, and it is stated here rather
than in a footnote.** The honest summary is that D103's headline is **convention-sensitive by
±11 points**: it is 45 %–67 % depending on which family-wise bar you accept, not 56.3 % ± nothing.
The qualitative claim — that a very large share of the programme's recorded nulls could not have
seen its own best finding — holds under every one of the three.

## 3. What actually dominates: 73 cells whose null is not a null

Bigger than any conversion error, and not previously counted:

* **67 of 666 cells have a degenerate permutation null** — mean(|t|)/sd(|t|) > 5, against ~1.32
  for *any* symmetric distribution. The shuffle barely moves the statistic, so the "null" is a
  tight cloud sitting far from zero. 66 are in E0_I0014, 1 in E0_I0019 (whose screen invented this
  very criterion, at `s05_spreads_and_decomposition.py:56-58`, and applied it only to itself).
* **6 more have a null of standard deviation exactly zero.** D103's formula returns a floor of
  **exactly 0.0** for them, so all six are recorded as *perfectly powered*.
* **35 of these 73 are recorded by D103 as adequately powered.** A narrower null buys a smaller
  floor; a null that has collapsed buys the smallest floor of all. The cells D103 rates best are
  the cells whose null failed.

## 4. The gate: a coverage gap, confirmed, with nothing hiding elsewhere

E1_I0037's claim is exact. `validate()` (`s06_retrospective.py:85-96`) reads
`out/s04_mde_table.csv` — 216 rows, **no `stat_family` column**, six simulated nulls whose
statistic is `dR2 = (a*a/b)/sst` (`s04_power.py:118`), never a t — and calls only
`mde80_increment`. An AST sweep of **1,104 `.py` files** resolved `mde80_tscale` to exactly **four
call sites, all in that one file** (lines 167, 168, 201, 202), and found **no other validation of
it anywhere**. Twenty files failed to parse (all `U+FEFF` BOM) and are named in `run_log_s01.txt`;
the only D103 file among them, `scripts/s06b_ns.py`, was opened and read literally — it is a
parquet-shape probe and validates nothing. **There is no second gate. This is a coverage gap.**

## 5. The two structural gates do not apply here, and that is a real answer

| gate | count over 666 cells | applicable? |
|---|---:|---|
| fewer than six blocks | **0** | **No** — `p_min = 2^(1−nb)` is a sign-flip identity; here the null is a 1,000-draw permutation, `p_min = 1/1001` |
| `t_crit ≥ √nb` | **102** (all E0_I0014, 36 team-season blocks) | **No** — the gate needs a null whose sd grows with the effect; **measured** at `sd(δ=0.3)/sd(0) = 1.0001`, p10 0.9987, p90 1.0030 |

Block counts in the family: 475 (246 cells), 489 (228), 36 (102), 1486 (90). The 102-cell count is
real arithmetic and it is **not a finding** — reporting it as one would be exactly the name-based
inference this programme has lost five findings to. Where E1_I0037 found the gates dominated the
`paired` family, here they are inert; the analogous structural hazard is the 73 degenerate nulls
of §3.

## 6. The results that most weaken this verdict

Stated here, not in `DEFECTS.md`:

1. **R-C reverses the sign.** Against a textbook Šidák bar the `t_statistic` family becomes
   *less* blind, 760 → 613, −10.90 points — very nearly the mirror image of R-A. My reason for
   preferring R-A is that it is the minimal repair of a category error, and my reason for
   preferring R-B over R-C is that it is the rule the screens actually applied; both are
   judgements, not measurements, and a coordinator could reasonably choose otherwise.
2. **The conversion, as an equation, is exonerated.** Every component of D103's derivation that
   could have been checked came back sound: the scale identity (median ratio 1.0000 on real
   cells), the closed form (1.07e-14 against a literal recompute), and the formula itself
   (0.989 against an injection-verified floor). The programme's `t_statistic` floors are wrong
   because of two inputs, one of which is arguably a design choice.
3. **My own first run was degenerate**, in the way three sibling screens have now been. I planted
   the effect along the real carrier while testing the permuted one — near-orthogonal, so power
   never left the floor and `E_inj` was `ABOVE_GRID_MAX` in **192 of 192** conditions. The
   pre-committed S2 check caught it; the defective output is kept at
   `SIMULATION_DEFECTIVE_s03run1.csv`. My first family-wise Type-I check was also mis-specified
   and its replacement was **not estimable** at K = 348 from 1,000 draws; those rows are flagged
   in `SIMULATION.csv` and the question was moved to a dedicated 60,000-draw arm. See
   `DEFECTS.md` D-1 to D-4.
4. **My proposed fix is worse than the incumbent in two named regimes** (`DEFECTS.md` D-5): it
   returns `nan` for 73 real cells the incumbent scores, and at `mean|t|/sd|t|` between ~1.5 and 5
   its degeneracy guard does not fire while the moment recovery is already overstating sd(t) — by
   124 % at a shift of 2 sd. It is **not recommended** without a caller-side rule that `nan` means
   UNVERIFIABLE and never "not blind".
5. **A D101 caveat that applies to all of D103 and that E1_I0037 did not raise.** D103 compares
   every cell's floor, a ΔR² *of that cell's own response*, against 0.0023, a ΔR² on D089's
   walk-forward points. E0_I0014's responses are |residual| and squared residual of
   minutes/points/FGA; E0_I0019's are Brier-skill differences. Different SST bases. It is D103's
   own design and it hits all three families equally, so it does not change the *relative*
   correction — but the absolute blind counts, mine included, inherit it.

## 7. Anchor

Reproduced before any new statistic was generated, from D103's own `out/retrospective_power.csv`
keyed exactly as E1_I0037 keyed it: **1,349 unique cells, 760 blind, share
0.5633802816901409** — identical to the published value at all sixteen digits. My reconstruction
of D103's own `mde80_fw` for all 666 `t_statistic` cells agrees to **1.07e-13 relative**, so every
correction above is applied to the published quantity itself and not to a look-alike.

**Preregistration:** `PREREG.md`, sha256 `869a92f0bb041c825c9cf73de5f19ca9cf239b292b8756ad702fd095deafe660`.
Predictions P1 (A_cor/E_inj ∈ [0.85, 1.20] → 0.989), P2 (folded ≈ 0.36 → 0.359), P3 (signed sound
→ 0.995) and P4 (invariance to n, ρ, imbalance → 0.344–0.370 across all arms) all held. P5, the
pre-stated outcome that would have cleared the conversion, did not.
