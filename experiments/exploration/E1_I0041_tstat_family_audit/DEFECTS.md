# DEFECTS — E1_I0041

## Part A — defects in **my own** machinery

Reported first, in full, because three sibling screens have now shipped degenerate power or
Type-I checks and the standing instruction is to assume mine is broken until proven otherwise.
**Two of my four pre-committed machinery checks failed on the first run.** No defective output was
deleted.

### D-1 — my power sweep had zero power in 192 of 192 conditions. CAUGHT BY S2. SEVERE.

`s03_simulation.py`, run 1. I planted the effect along the **real** residualised carrier
(`y(δ) = yt + c·xt_real`) and measured the statistic on the **permuted** carrier. Those two
vectors are near-orthogonal by construction — that is the entire point of the permutation — so
almost none of the planted effect reached the statistic being tested. Power never left the floor:
`max_power < 0.99` in all 192 rows, `E_inj = ABOVE_GRID_MAX` in all 192, no finite floor anywhere.

* **Caught by:** pre-committed check S2 (PREREG 3.4), which required power to reach ≥ 0.99 at the
  top of the grid in at least 80 % of conditions. It reached it in 0 %.
* **Correct construction:** `s04_power.py:11` and `:213` plant the effect along the **same
  permuted carrier that is then tested** — the permuted carrier is a column with the real
  structure and no real association, and it plays the role of the candidate. Run 2 does this.
* **Preserved:** `SIMULATION_DEFECTIVE_s03run1.csv`, `run_log_s03_DEFECTIVE_run1.txt`,
  `scripts/s03_simulation_DEFECTIVE_run1.py`.
* **Deviation from PREREG:** PREREG 3.2 described planting along `x̃_real`. That description was
  wrong and is corrected in run 2. The declared **contrast** is unchanged in substance — ΔR² of
  the season-demeaned response on the season-demeaned carrier, unweighted, SST from the
  effect-free response, single added regressor, base = season fixed effects — but the carrier is
  the permuted one, which is what makes the δ = 0 row a Type-I check by construction. Recorded
  here rather than by re-hashing the preregistration.

### D-2 — my first family-wise Type-I check was mis-specified. Not a machinery fault.

Run 1 measured the rejection rate of a **single** cell against a **family-wise** bar and reported
it as a Type-I rate. It came out 0.0000 in all 96 conditions, which is correct behaviour — a bar
calibrated so that *any* of K = 348 cells exceeds it with probability 0.05 is exceeded by one
nominated cell with probability ≈ 0.05/348. The check, not the machinery, was wrong. Run 2
measures the family-wise error at the family level.

### D-3 — the family-wise bar is not estimable at K = 348 from 1,000 draws. ARM RETIRED.

Even measured at the family level, run 2's family-wise bar gave a family error of **0.284**, not
0.05. Cause: the bar was built by drawing K = 348 values **with replacement** from a 1,000-value
null cloud and taking the q95 of the maximum. The maximum of 348 draws from 1,000 values is almost
always one of the top handful of atoms, so the distribution of the maximum is nearly discrete and
its q95 is exceeded far more often than 5 % of the time. The bar at K = 348 is the 0.99985
quantile of the per-cell null, which 1,000 draws cannot resolve.

* **Consequence:** the 96 `regime = family_wise` rows in `SIMULATION.csv` are flagged
  `status = OK_FORMULA_ONLY__BAR_NOT_ESTIMABLE_AT_K348_FROM_1000_DRAWS`. Their
  `ratio_A_pub_folded` and `ratio_A_pub_signed` columns are **not interpretable** as
  published-versus-correct, because the denominator's bar is mis-calibrated.
* **What those rows still establish, and it is worth having:** `ratio_A_cor` = **0.984**
  (p10 0.949, p90 1.012). The floor formula is accurate at a family-wise-magnitude bar as well as
  at α = 0.05, because the 80 %-power calculation only needs the *bulk* of the null, not its tail.
  The tail is needed for the bar, and only for the bar.
* **Replacement:** `s03b_familywise_bar.py` — a 30,000-draw cloud to set the bar and an
  independent 30,000-draw cloud to measure the error, with the family error computed analytically
  from the held-out per-cell exceedance rate rather than by resampling. Sixteen configurations.

### D-4 — my AST function classifier found zero MDE-producing functions. Cosmetic, corrected.

`s01`'s first classifier looked for the literal string `0.8416` inside function bodies. D103
defines `Z80` as a module constant and its functions reference the name, so the classifier
returned 0 hits. This did not affect any result — the call-graph resolution that matters was done
on `ast.Call` nodes by callee name against the four function names actually defined in
`s06_retrospective.py`, and it resolved `mde80_tscale` to exactly four call sites. Recorded
because E1_I0037 logged the same class of error (its D-2) and the pattern is worth naming: a
body-text classifier must resolve module constants or it silently returns nothing, which reads
identically to "there is nothing there".

### D-5 — my proposed fix is worse than the incumbent in two named regimes. NOT RECOMMENDED as-is.

`PROPOSED_FIX/` passes 13 of 13 tests, which is not the same as being an improvement.

1. **It returns `nan` for 73 real cells the incumbent scores** (67 degenerate nulls + 6 zero-width
   nulls). That is the correct answer — those cells have no recoverable floor — but D103's
   downstream comparison is `mde80_fw > 0.0023`, under which `nan` evaluates to `False` and the
   cell is silently counted **not blind**. A caller that adopts this fix without also adopting the
   rule `nan == UNVERIFIABLE` is **strictly worse off than with the incumbent**, which at least
   produces a number.
2. **Its degeneracy guard has a blind band.** At `mean(|t|)/sd(|t|) ≈ 2` the guard (cut at 5) does
   not fire, but `E[t] = 0` already fails and the moment recovery **overstates sd(t) by 124 %**
   (T4, measured at a 2-sd shift). Lowering the cut to ~2 would catch it and would also refuse a
   large number of legitimate cells, since the symmetric reference is 1.32 and real clouds scatter
   above it. I could not find a cut that is right in both directions and I did not tune one to
   look good.

**Recommendation: do not adopt** unless the caller-side `nan == UNVERIFIABLE` rule is adopted
first. Not applied. Not installed in the shared kit. `experiments/exploration/_screen_kit/` was
never opened for writing.

---

## Part B — defects found in the audited code

### D103-1 — `mde80_tscale` receives a folded standard deviation for 348 of 666 cells. ANTI-CONSERVATIVE.

`s06_retrospective.py:167-168` passes `E0_I0014.screen_results.null_correct_sd` as `sd_null_t`.
That column is `nb.std(ddof=1)` of an array built at `E0_I0014/s04_screen.py:211` as
`np.abs(tvec(...)[1])` — the sd of **|t|**. The conversion's derivation is for the signed
statistic ("planting an effect δ shifts t by √(δn)", "the mean cancels"). Folding narrows the
distribution by a measured median factor of **1.79** on the real cells (half-normal theory:
1.6589), so the floor is understated by ≈ 2.95–3.21×. **126 additional cells become blind.**
Nothing in the retrospective's code or comments distinguishes E0_I0014's folded column from
E0_I0019's signed one; they arrive under the same parameter name.

### D103-2 — `t_crit` is a ΔR²-scale quantile applied to a t-scale statistic. CONSERVATIVE.

`s04_power.py:70-72` standardises D089's **ΔR²** null matrix and takes the q95 of its max over K
cells: 6.686 (K = 348) and 6.974 (K = 318). A standardised ΔR² is a right-skewed, squared quantity;
a t is symmetric. The correctly calibrated bar for K independent near-normal cells is **3.795** and
**3.773** sd — measured on 60,000-draw clouds, not assumed. Applying the borrowed value overstates
the floor by ≈ 2.85×. **For the `increment` family this is not a defect** — there `t_crit`
multiplies a ΔR²-scale sd, which is the scale it was calibrated on, and D103's validation covers
it.

### D103-3 — 73 of 666 cells have a null that did not function, and the formula rewards them.

67 cells have `mean(|t|)/sd(|t|) > 5` (≈1.32 for any symmetric distribution); 6 more have a null
sd of **exactly 0**, for which `mde80_tscale` returns a floor of **exactly 0.0**. **35 of the 73
are recorded by D103 as adequately powered.** A collapsed null is the cheapest possible way to buy
a low detection floor and nothing in the pipeline notices. `E0_I0019` built precisely this check
for itself (`s05_spreads_and_decomposition.py:56-58`, cut at 5) and its result is not carried into
the retrospective; `E0_I0014` never built one.

### D103-4 — `validate()` does not cover the path carrying 68 % of the blind verdicts. CONFIRMED.

`s06_retrospective.py:85-96` reads `out/s04_mde_table.csv` (216 rows, no `stat_family` column, six
simulated nulls whose statistic is `dR2 = (a*a/b)/sst`) and calls only `mde80_increment`. The
assertion at line 251 gates the whole retrospective on a median ratio that never sees a t. An AST
sweep of 1,104 `.py` files found no other call site of `mde80_tscale` and no other validation of
it. The one unparsable D103 file, `scripts/s06b_ns.py`, was read literally: it is a parquet-shape
probe. **This is a coverage gap, not validation living elsewhere** — the question E1_I0037 said to
check, checked, and answered in the worse direction.

### D103-5 — `mde80_percell` uses a one-sided constant against a two-sided statistic. MINOR.

`s06_retrospective.py:167` and `:201` pass `t_crit = 1.645` (one-sided 95 %) for a per-cell floor
on a statistic whose own p-values are two-sided (`(np.abs(a) >= abs(t)).mean()`). 1.960 is the
matching constant. This understates the per-cell floor by ≈ 12 %. **It does not touch any blind
count in this document**, all of which use `mde80_fw`. Recorded for completeness.

### E0_I0014-1 — an unstandardised family-wise max|t| across cells whose nulls span two orders of magnitude. FOR ROUTING.

`E0_I0014/s04_screen.py:238` takes the maximum of raw `|t|` over all 348 cells. Its cells' null
widths range from 0 to > 10, so the bar is set by a handful of pathological cells: q95 = **29.13**,
which is **15.9 of a median cell's own noise widths** where a properly calibrated bar is 3.8. Under
that bar essentially the whole screen is undetectable (348/348 blind, R-B). This is the single
largest contributor to the R-B restatement and it is a property of **E0_I0014's own procedure**,
not of D103's conversion. E0_I0019 does not have this problem (own bar 6.74 sd vs D103's 6.97 sd,
a 3 % difference). **Not adjudicated here — flagged for the coordinator.**

### E0_I0019-1 — one all-NaN null array. NO IMPACT, verified.

`permutation_nulls.npz::null_teamseason_between` is entirely NaN. It is never a primary scheme
(`scheme_primary` is `player_between` ×228 or `teamgame_between` ×90), so `nullsd_between` is
never NaN and no `mde80_fw` is NaN in either screen (0 of 348, 0 of 318). Checked because a silent
NaN would have been counted "not blind"; it does not occur.
