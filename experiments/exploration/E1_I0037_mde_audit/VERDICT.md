# VERDICT — E1_I0037, audit of the programme's analytic MDE80

**The claim is false as stated, and true in a weaker form with a different cause.** The headline
6.6× does not survive: E1_I0035 compared an injection floor measured on the **Xb** response
contrast (0.0025) against an analytic floor computed from the **Xa** contrast's null sd (0.00038)
— two different vectors, a D101 denominator violation; recomputed like-for-like from that
screen's own frame the ratios are **1.02× on Xa and 0.76× on Xb**, not 6.6×. The stated
*mechanism* is also misattributed, and misattributed in the reassuring direction: an
effect-carrying `null_sd` **inflates** the quoted floor, which makes the analytic form
**conservative**, not anti-conservative. But a real anti-conservative defect does exist in the
same construction — the test's **critical value** also grows with the effect — and its size is
governed by the **number of blocks**, not by the effect, the sample size or the variance.

---

## The three sentences, expanded

| | E1_I0035's D-3 said | This audit finds |
|---|---|---|
| Magnitude | anti-conservative **6.6×** | **1.02×** like-for-like on that cell; the 6.6× is a contrast mismatch |
| Mechanism | `null_sd` carries the effect → floor moves with it | that mechanism is real but runs **conservative**; the anti-conservatism comes from the **critical value**, a different term |
| Generality | "other screens quote the analytic form alone" | true — **232 quoted figures across 4 screens** — but the bias is **≤ 9 %** on every one of their actual designs except one |

E1_I0035 flagged this as a self-reported footnote and said it changed none of its verdicts. That
judgement was correct. The footnote was worth raising; the number in it was not reproducible.

---

## 1. THE CONSTRUCTION — confirmed, at source, in the shared kit

`_screen_kit\screenkit.py::paired_forecast_comparison` is the general case, not a local copy:

```
2143   d    = (y - a) ** 2 - (y - b) ** 2      <- OBSERVED losses of the two forecasts
2150   csum = np.bincount(gcodes, weights=d)   <- block sums OF THE OBSERVED vector
2156   draws = _draws_for(csum, rng)           <- +/- the SAME block sums
2170   sd   = float(draws.std(ddof=1))         <- the "null" sd
```

Nothing is permuted or resampled; only signs are flipped on the observed block sums. So
`E[draws] = 0` by construction but `Var[draws]` scales with the effect. `E1_I0035\scripts\
av_base.py::paired_signflip_block` (lines 273–294) and `E1_I0034\scripts\redist_base.py`
(lines 235–256) are the identical construction. **C1 is confirmed.**

Call graph resolved by AST, not by name: **417 `.py` files enumerated, 410 parsed, 7 UNRESOLVED**
(all `SyntaxError: U+FEFF` BOM, listed in `run_log_s01.txt` — none is an MDE producer, but I
cannot prove that of a file I could not parse, and they are named). Classifying functions by the
arithmetic they perform — a constant within 0.01 of `z_alpha + Phi^-1(0.80)`, or the closed form
— yields **13 MDE-producing functions** (excluding my own). Matching call sites by name *after*
identifying the functions by their bodies gives 103 hits, of which the specific (non-`main`)
resolutions are `rb.mde80` ×11, `ab.mde80` ×2, `mde80` ×4 (E1_I0036, a power-curve interpolator,
**not** this construction), `hb.paired_game_signflip` ×11.

## 2. THE MECHANISM — two effects, separated, running opposite ways

Write the sign-flip sd of an effect-carrying vector with `nb` blocks and true standard error `SE`:

```
sd(e) = sqrt( e² / nb + SE² )
```

**H_A — the quoted floor is inflated.** `2.802 · sd(e) > 2.802 · SE`. **Conservative.** Measured:

| cell | blocks | observed effect | contamination `sd_obs/sd_ctr` | quoted floor | correct |
|---|---:|---:|---:|---:|---:|
| E1_I0035 team Xb | 36 | −8.81 MAE | **2.435** | 4.595 | 1.887 |
| E1_I0035 team Xa | 36 | −7.31 | 2.074 | 3.994 | 1.926 |
| E1_I0035 player Xb | 488 | +0.01424 | 1.321 | 0.00305 | 0.00231 |
| E1_I0035 player Xa | 488 | +0.000148 | **1.003** | 0.000372 | 0.000371 |

Across the 1,304-condition grid: median contamination **1.019**, p90 **1.407**, max **14.4** —
and it is ~1.00 whenever the observed effect is near zero. **H_A cannot produce
anti-conservatism.** This corroborates E1_I0034's finding that its own `null_sd` is clean
(0.963–1.013): its cells' effects were small enough that there was nothing to contaminate.

**H_B — the critical value is inflated too.** Rejection needs `|mean(d)| ≥ t_crit · sd(e)`, whose
right-hand side grows like `t_crit·e/√nb`. Solving for 80 % power in `u = e/SE`:

```
u²(1 − t_crit²/nb) − 2·z₈₀·u + (z₈₀² − t_crit²) ≥ 0
```

**This is the real defect and it is anti-conservative.** `E_inj / (2.802 · sd_centred)`:

| blocks | 8 | 16 | 32 | 64 | 128 | 256 | 512 |
|---|---:|---:|---:|---:|---:|---:|---:|
| median | **1.269** | **1.131** | 1.043 | 1.019 | 1.012 | 1.014 | 1.001 |
| p10–p90 | 1.03–1.77 | 0.99–1.42 | 0.97–1.21 | 0.95–1.10 | 0.93–1.09 | 0.95–1.08 | 0.94–1.05 |

It depends on **block count alone** — `σ = 1` and `σ = 25` arms agree, and `n` from 32 to 32,768
makes no difference (`run_log_s02.txt` §H).

## 3. THE RATIO DISTRIBUTION — 1,304 conditions, 1,141 with a finite crossing

| ratio | min | p10 | **median** | p90 | max |
|---|---:|---:|---:|---:|---:|
| `E_inj / A_obs` (the D-3 comparison) | 0.553 | 0.877 | **1.006** | 1.173 | 2.319 |
| `E_inj / A_ctr` (correct sd, incumbent rule) | 0.632 | 0.951 | **1.038** | 1.279 | 3.178 |
| `E_inj / A_oracle` (known SE) | 0.854 | 0.973 | **1.029** | 1.188 | 1.397 |

**6.6× lies far outside this distribution — beyond the maximum of every column.** It is not a
worst case of this mechanism; it is not this mechanism.

The apparent direction flips with the observed effect, exactly as preregistered (P3): at an
observed effect of 3 SE, **64 %** of conditions look *conservative* (`E_inj/A_obs < 1`); at zero
observed effect only **29 %** do. That is why E1_I0035 saw "conservative 2.3×" on its big-effect
team cell and something else on its near-zero player cell.

## 4. TWO STRUCTURAL RESULTS THAT MATTER MORE THAN THE RATIO

**(a) Below six blocks a two-sided sign-flip can never reject.** `p_min = 2^(1−nb)`, so
`p < 0.05` needs `nb ≥ 6`. Measured Type-I at R = 2,000: nb = 3, 4, 5 → **0.0000, 0.0000,
0.0000**; nb = 6 → 0.0275; nb = 7 → 0.0470; nb ≥ 8 → 0.043–0.051. Such a cell's MDE is `+∞`
regardless of its null sd.

**(b) When `t_crit ≥ √nb` the MDE is infinite.** Verified by direct simulation over an
eight-order effect sweep, not by algebra alone: at nb = 48, `t_crit` = 6.974, **max power
attained = 0.0000**; at nb = 60 with the same `t_crit`, 80 % power at 20.3 SE. **This is exactly
D103's family-wise threshold applied to E1_I0023's 48-cluster paired cells.**

## 5. THE RESULT THAT MOST WEAKENS THIS AUDIT'S OWN CONCLUSION

Three, stated here rather than buried:

1. **On the programme's real designs the defect I was sent to audit is negligible.** E1_I0035
   player 488 blocks → 1.005×; E1_I0035 team and all of E1_I0033, 36 blocks → 1.085×; E1_I0023
   per-cell, 48 blocks → 1.045×. Only the family-wise application to E1_I0023 breaks, and those
   cells were already counted blind. **The programme's ~1,000 negative conclusions are not
   materially less informative than D103 already said.**
2. **My own simulator's first run was degenerate in E1_I0035's D-2 way** — I centred each noise
   realisation, making the statistic identically zero and the Type-I rate 0.0000 in every
   FRESH condition. My preregistered S1 check caught it; the defective output is kept at
   `SIMULATION_DEFECTIVE_s02run1.csv`. See `DEFECTS.md` D-1.
3. **My proposed closed-form fix over-corrects worse than the incumbent under-corrects at 8
   blocks** (37 % vs 16 %), and my exact solver scatters ~40 % there. Test T6 records this as a
   failure I could not engineer away. Below ~32 blocks **no** data-driven MDE is stable; the
   honest output is "this design has no reliable floor", which the fix now emits.

## 6. THE LARGER EXPOSURE I FOUND AND DID NOT QUANTIFY

D103's `stat_family = 't_statistic'` — **666 of 1,349 cells (49.4 %), carrying 518 of the 760
blind verdicts (68.2 %)** — uses `MDE80 = ((t_crit + z₈₀)·sd_t)² / n`, a scale conversion that was
**never validated**. D103's validation (`s06_validation_analytic_vs_simulated.csv`, median ratio
0.989, n = 192) reads `s04_mde_table.csv`, which contains only `increment` cells. **This is a
bigger unvalidated surface than the one I was sent to audit and it needs its own screen.**

## 7. ANCHOR

Reproduced before generating any new statistic, from D103's own `retrospective_power.csv`:
**1,349 unique cells, 760 blind, share 0.5633802816901409** — identical to the published
`FINDINGS.json` value to all 16 digits.
