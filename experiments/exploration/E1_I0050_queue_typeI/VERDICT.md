# VERDICT — E1_I0050, per-cell Type-I for the 54-cell queue

Partition: **2021–2024 exploration only. 2025/26 was never opened.** `E0_I0014`'s frame contains
2022–2024; every read asserts `season <= 2024` and `max(gdate) < 2025-01-01`.
Preregistration `PREREG.md`, sha256
`9a0eb0e7386f895ec98fff50b18724fb98f19a128c38785e652e6742f719908c`.

---

## HEADLINE

**On the clean decision stratum — 2023–24, ≥8 prior appearances and ≥24 trailing-5 minutes,
n = 3,549 in 174 player-season blocks — 48 of the 54 cells have a null whose measured Type-I is
within tolerance, 4 have no statistic at all because their candidate is constant inside the
stratum, and 2 fail; of the 37 cells `E1_I0044` found at `p < 0.05`, 35 retain that p under a null
with an acceptable Type-I and 16 of its 17 family-wise-significant cells survive.** **The
published family-wise `p` of exactly 1.000 is the artefact, and it is one cell: in 1,000 of 1,000
draws the whole 348-cell bar is supplied by `pl_pts_sd5|pts_absres`, whose own null sits at
mean `|t|` = 27.578 against a row-naive bar of 3.730.** **Type-I inflation is *not* predictable
from the candidate's distributional shape, because across 104 estimable (cell, arm) pairs there is
essentially no Type-I inflation to predict — 0 exceed tolerance under the reference generator —
and the two candidate types `E1_I0044` named as known-bad, a kurtosis-297 ratio and a pure
counter, are the most *conservative* cells in the queue.**

---

## THE COUNTERWEIGHT, IN THE SAME BREATH

**`E1_I0044`'s Type-I numbers reproduce. They were measuring its generator, not its null.**
Its `block_resample_matrix` copies whole donor blocks with `don[arange(len(b)) % len(don)]`,
preserving **absolute within-block position**. These responses carry a positional profile shared
across blocks, so it is transplanted intact into every "effect-free" dataset. Measured directly:
over 1,000 of its synthetic datasets the mean **signed** observed `t` exceeds 0.5 in magnitude on
**41 of 54** cells and reaches **7.31**; under two generators for which H0 does hold it exceeds
0.5 on **0 of 54**. So `E1_I0044` refused to claim a real result on the strength of a broken
control — the right instinct, the wrong evidence.

**And my own headline self-test failed.** PREREG T2 required composed-2 to hit nominal on an
iid candidate; it returned **0.0230 and 0.0060**. A second script settled whose fault that was:
on an iid candidate with an iid response the harness returns **0.0490 / 0.0470 / 0.0510**, and an
exact null on the same clustered data returns **0.0400 / 0.0510**. **The harness is exact; the
composed-2 null is conservative** — it fills a receiving block from one donor, giving an iid
carrier a between-block variance share of **0.1142** against its real **0.0344**. Every floor and
every `BLIND` verdict `E1_I0044` published for these cells is therefore **pessimistic, not
optimistic**. `DEFECTS.md` D-2.

**Two of my five predictions failed outright and one failed as stated** (`DEFECTS.md` D-3), and
**two cells sit just over a tolerance that is mine**: a reader setting it at 0.10 rather than
0.075 would make the A4 count 17 of 17 (D-5).

**None of this is a betting edge, and the reason is a D101 reason.** The response is
forecast-error magnitude; D103's 0.0023 bar is a ΔR² on D089 walk-forward **points**. Different
response, different SST, different base. The comparison is descriptive only.

---

## ANCHORS REPRODUCED BEFORE ANY NEW STATISTIC — 25 of 26

`scripts/run_log_s00.txt`.

| anchor | published | reproduced |
|---|---|---|
| D103 `retrospective_power.csv`, worst arm by `mde80_fw` | 1,349 / 760 / 0.5633802816901409 | **exact, `repr`-identical** |
| `E1_I0041` `t_statistic` cells / degenerate / `sd = 0` / total / adequate | 666 / 67 / 6 / 73 / 35 | **666 / 67 / 6 / 73 / 35**, overlap 0 |
| `E0_I0014` `t_classical`, 348 cells, rebuilt from the frame | — | max rel **3.9389e-15**, **276 of 348 bitwise** |
| `E0_I0014` `null_correct_sd` from the saved draws | — | **2.2204e-16** |
| `E0_I0014` `p_correct_level`, 348 cells | — | **0 mismatches** |
| `E0_I0014` family-wise bar mean / p95 / row-naive p95 / observed max\|t\| | 27.577598195648264 / 29.12663204615966 / 3.7295261371093513 / 41.60553110904952 | **all four to 1e-12**, first two also rebuilt from raw draws to 1e-9 |
| `E1_I0044` broken / re-measured / A4 `p<0.05` / A4 family-wise | 73 / 54 / 37 / 17 | **73 / 54 / 37 / 17** |
| `E1_I0044` Type-I median | 0.0525 | **0.0525** |
| the 18 void cells, identified **by measurement** (`sxx` after base < 1e-6) | 18 | **18, identical to its labelled set** |
| my own re-derivation of composed-2 `p`, ΔR² and `t` from its saved `.npz` vs its CSV | — | max abs **< 1e-12** on all three, all 108 rows |

**The one that failed:** `E1_I0044` states 41 of the 54 have a published `p_familywise` of exactly
1.000. The count is **49** (and 301 of all 348). `DEFECTS.md` F-1.

**Void-leak check:** `|CELLS54 ∩ VOID18| = 0`. The three void candidates have `sxx` after the base
of 0.0, 9.09e-27 and 4.59e-26; the minimum over the 54 queue candidates is **1.3876e+04**. None
leaked.

---

## D101 STATEMENT — every number in this screen

| | |
|---|---|
| response | one of `{pts,minutes,fga} × {absres,sqres}`; never mixed, never pooled |
| row set | **A4_CLEAN_DEC** 3,549 rows, 2023–24, `pl_games_prior >= 8 AND pl_min_mean5 >= 24`, 174 player-season blocks. **A1_FULL** 13,879 rows, 2022–24, 475 blocks. |
| base | season fixed effects on the arm's own seasons |
| SST basis | season-demeaned response on the arm's own rows |
| weighting | unweighted OLS |
| statistic | signed one-column classical `t`; **one-column statistic, one-column floor** |
| family / bar | 348 cells, one shared gather index per draw; bar = 95th pct of `max|t|` |
| p convention | `(k+1)/(R+1)`, R = 2,000. `E1_I0044` used `k/R`, which can return an impossible exactly-zero p. Both are in `CORRECTED_VERDICTS.csv`; the counts are identical. |

Each arm is self-contained. **Nothing is compared across arms.** The position-adjusted arm in §4
has its own base and its own SST and is never differenced against the main arms.

---

## 1. TYPE-I, ALL 54, PER CELL — `TYPEI_PER_CELL.csv`

**B = 1,000 synthetic datasets per (cell, arm, generator); POOL = 1,000 permuted carriers;
R_NULL = 500 drawn without replacement per replicate.** Preregistered and not revised.
54 cells × 2 arms × 3 generators × 3 null schemes = **972 rejection rates**.

Three generators, differing only in what within-block alignment survives. All three preserve n,
block count, block sizes, the block-mean distribution, the within-block deviation distribution
and therefore the response's variance decomposition.

| | H0 true? | construction |
|---|---|---|
| **EXCH** | yes | block means reassigned within season; deviations permuted |
| **CIRCSHIFT** | yes | block means reassigned; deviations circularly rolled — retains serial correlation |
| **BLOCKBOOT** | **no** | `E1_I0044`'s; whole donor blocks, absolute position preserved |

### Composed-2, nominal 0.05, preregistered tolerance 0.075

| | **A4_CLEAN_DEC** (reported first) | A1_FULL |
|---|---|---|
| EXCH — median / max / **above tolerance** | 0.0205 / 0.0590 / **0 of 50** | 0.0260 / 0.0700 / **0 of 54** |
| CIRCSHIFT — median / max / **above tolerance** | 0.0225 / 0.0920 / **2 of 50** | 0.0320 / 0.0860 / **1 of 54** |
| BLOCKBOOT (`E1_I0044`'s) — median / max / above | 0.0115 / 0.1070 / 1 of 50 | 0.0455 / **0.9860** / **22 of 54** |

### Null validity over the 54

| | A4_CLEAN_DEC | A1_FULL |
|---|---:|---:|
| **ACCEPTABLE** | 22 | 39 |
| **ACCEPTABLE — CONSERVATIVE** (≤ 0.025) | 26 | 14 |
| **total acceptable** | **48** | **53** |
| INVALID — anticonservative | 2 | 1 |
| UNVERIFIABLE — candidate constant in stratum, no statistic | 4 | 0 |

The 4 are `pts__is_fallback` and `pts__fallback_level` on the two minutes responses: a row with
≥8 prior appearances is never a fallback row. That is a property of the stratum, not a defect,
and it is detected by measurement (`sxx` after base ≤ 1e-8), not by a label.

The 3 invalid are `pl_pts_sd5|pts_sqres` (A4 0.092, A1 0.086) and `pl_fga_sd5|fga_sqres`
(A4 0.081) — all marginal, Clopper–Pearson upper bounds 0.100–0.112. `DEFECTS.md` D-5.

### The other two schemes, on the same synthetic data

| null scheme, cells failing tolerance | A4 | A1 |
|---|---:|---:|
| `E0_I0014`'s own level-matched null | 8 of 50 | **29 of 54** |
| row-naive | **48 of 50** | **50 of 54** |

---

## 2. THE CORRECTED VERDICTS — `CORRECTED_VERDICTS.csv`

### A4_CLEAN_DEC — the decision stratum, reported first

n = 3,549, 174 player-season blocks, family-wise bar 5.323 (4.072 over validated cells only).

| corrected verdict | cells |
|---|---:|
| **FAMILY-WISE SIGNIFICANT**, acceptable null, not confounded | **16** |
| per-cell significant only | 18 |
| per-cell significant only, confounded with block position | 1 |
| not significant | 13 |
| **UNVERIFIABLE — null fails Type-I** | 2 |
| **UNVERIFIABLE — no statistic in stratum** | 4 |

**Of `E1_I0044`'s 37 at `p < 0.05`: 35 retain a per-cell `p < 0.05` under a null with an
acceptable Type-I; 2 become UNVERIFIABLE. Of its 17 family-wise-significant: 16 survive.**

| cell | n | blocks | ΔR² | `p` per-cell | `p` family-wise | Type-I worst-H0 | published `p_fw` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `pts__pred_cv\|pts_absres` | 3,549 | 174 | 0.02743 | 0.0005 | 0.0010 | 0.027 | **1.000** |
| `pl_min_rng5\|minutes_absres` | 3,549 | 174 | 0.02511 | 0.0005 | 0.0015 | 0.032 | **1.000** |
| `pl_min_sd5\|minutes_absres` | 3,549 | 174 | 0.02422 | 0.0005 | 0.0015 | 0.030 | **1.000** |
| `pts__pred_cv\|pts_sqres` | 3,549 | 174 | 0.02407 | 0.0005 | 0.0015 | 0.030 | **1.000** |
| `pts__pred_cv\|fga_absres` | 3,549 | 174 | 0.01937 | 0.0005 | 0.0020 | 0.029 | **1.000** |
| `pts__pred_cv\|fga_sqres` | 3,549 | 174 | 0.01854 | 0.0005 | 0.0025 | 0.026 | **1.000** |
| `pts__pred_cv\|minutes_sqres` | 3,549 | 174 | 0.01557 | 0.0005 | 0.0065 | 0.035 | **1.000** |
| `pl_abs_min_trend5\|minutes_absres` | 3,549 | 174 | 0.01381 | 0.0005 | 0.0070 | 0.023 | **1.000** |
| `pl_start_switch5\|minutes_absres` | 3,549 | 174 | 0.01283 | 0.0005 | 0.0090 | 0.016 | **1.000** |
| `pl_min_rng5\|minutes_sqres` | 3,549 | 174 | 0.01264 | 0.0005 | 0.0090 | 0.043 | **1.000** |
| `pl_min_sd5\|minutes_sqres` | 3,549 | 174 | 0.01232 | 0.0005 | 0.0100 | 0.040 | **1.000** |
| `pl_dnp_frac5\|minutes_sqres` | 3,549 | 174 | 0.01132 | 0.0005 | 0.0125 | 0.018 | **1.000** |
| `pts__pred_width\|minutes_absres` | 3,549 | 174 | 0.01096 | 0.0005 | 0.0135 | 0.021 | **1.000** |
| `pl_abs_min_trend5\|minutes_sqres` | 3,549 | 174 | 0.00919 | 0.0005 | 0.0280 | 0.035 | **1.000** |
| `pl_pts_sd5\|pts_absres` | 3,549 | 174 | 0.00852 | 0.0005 | 0.0385 | 0.070 | **1.000** |
| `pl_dnp_frac5\|minutes_absres` | 3,549 | 174 | 0.00815 | 0.0005 | 0.0460 | 0.010 | **1.000** |

All 16 clear D103's single-cell floor of 0.00102. **15 of the 16** carry a published
`p_familywise_whole_screen` of exactly **1.000**; the sixteenth, `pl_pts_sd5|pts_absres`, carries
0.977 — it is the one cell in the queue whose observed `|t|` is large enough to register against
even the broken 29.13 bar, because it is the very cell whose own broken null *is* that bar.

**And six of the sixteen were not significant on `E0_I0014`'s own per-cell column either**
(`published_p_correct_level` of 0.855, 0.937, 0.977, 0.998, 1.000 and 0.178). For those the
correction is not merely family-wise: the published per-cell `p` was itself produced by a null
that contains the alternative. The other ten already had `p_correct_level` between 0.000 and
0.046, so for them **only the family-wise verdict changes**.

### A1_FULL — retained only for like-for-like with the published cell

24 family-wise significant with an acceptable, unconfounded null; 12 more family-wise significant
but flagged confounded with block position; 1 unverifiable. **Of the 49 cells with a published
`p_fw` of exactly 1.000, 48 have an acceptable null and 31 reach family-wise `p < 0.05`.**

---

## 3. WHY THE 1.000 — `WHY_1.000.md`

**The published bar is one cell.** In 1,000 of 1,000 draws the 348-cell `max|t|` comes from
`pl_pts_sd5|pts_absres`, whose within-block null is centred at **+27.616** with sd 0.872 on the
real response — because that shuffle preserves each block mean exactly and the association lives
in the block means. Bar p95: **29.127** as published; **9.078** with the 72 broken cells removed;
**3.730** under the screen's own row-naive null; **5.835 / 5.323** under composed-2 on A1 / A4.
Removing the 18 void cells changes it by zero.

**And that defect is invisible to a Type-I study.** The same cell, same null, measured Type-I:
**0.057**. `E0_I0014`'s null is not anticonservative — it is **blind**, which is a power and bar
failure. Level and blindness are different failures needing different instruments, and neither
`E1_I0044`'s blindness test nor this screen's level test would have been sufficient alone.

---

## 4. THE ROBUSTNESS ARM THAT COULD HAVE RETRACTED EVERYTHING

`_POSITION_ADJUSTED.csv`. **A separate arm with its own denominator:** same rows, base = season
fixed effects **plus relative within-player-season position and its square**, SST = the response
residualised on *that* base. Composed-2 null, 2,000 draws, bar rebuilt under the new base.

| | A4 | A1 |
|---|---:|---:|
| clean survivors tested | 16 | 24 |
| annihilated by the position base | **0** | **0** |
| **still family-wise significant** | **16 of 16** | **24 of 24** |

It retracts nothing. Even `pl_games_prior|minutes_absres` and `pts__n_prior_games|minutes_*` —
candidates that *are* the within-block position index — survive a base containing position and
position², at `p_familywise` 0.0005–0.0010. **I built this arm expecting it to kill the counters
and it did not.**

---

## 5. WHAT MOST WEAKENS THIS VERDICT

1. **The composed-2 null is conservative, so the bar is contaminated in the safe direction but is
   still contaminated.** The 348-cell family-wise bar (A4 5.323) is built over cells whose nulls
   are mostly conservative; over only the cells this screen validated it is **4.072**. Every
   family-wise verdict here is conservative relative to an exact null, and I did not build one.
2. **Bonferroni is not estimable at R = 2,000.** Minimum per-cell `p` is 1/2,001 = 0.0005;
   × 348 = 0.174. No cell can clear a Bonferroni bar at this draw count. Max-`|t|` is the only
   multiplicity control available, and it is the one `E0_I0014` chose.
3. **Replicates share a permutation pool** (`DEFECTS.md` D-4). The extra variance is unmeasured;
   the true se is nearer 0.010 than the binomial 0.00689 I report, so every Clopper–Pearson
   interval is narrower than the truth. It does not move a verdict — median 0.021–0.035 against a
   0.075 bar — but it would matter for the three boundary cells.
4. **The 0.075 tolerance is mine.** At 0.10 the A4 count is 17 of 17, not 16 of 17.
5. **The survivors are heteroscedasticity relationships, not point-forecast edges**, and they are
   mostly not new: 25 of the 54 already had a published `p_correct_level < 0.05`. **What changes
   is the family-wise verdict**, and only that.
6. **Fifteen candidates carry fifty-four cells**, so every shape correlation has at most 15
   independent points and `SHAPE_RULE.md` declines to propose a screening rule on that basis.
7. **`pts__pred_cv` holds five of the sixteen A4 survivor slots**, and it is a ratio
   `pred_sd / pred_point` whose within-block excess kurtosis on A1 is **297**. Its null tests
   clean (Type-I 0.009–0.047), but a single heavy-tailed constructed ratio carrying nearly a third
   of the surviving list is a concentration worth naming rather than a reassurance.
8. **Two of five preregistered predictions failed and one failed as stated**, all reported in the
   direction the data gave.

---

## 6. WHAT THIS DOES AND DOES NOT LICENCE

**It licences**: retiring `p_familywise_whole_screen` from `E0_I0014/screen_results.csv` as
unusable; recording D103's floors for these 54 as pessimistic rather than merely wrong; and
treating the 16 A4 cells as **family-wise significant with a validated null** rather than as
"UNVERIFIABLE" or as "null".

**It does not licence** a production change, a champion, a comparison against D103's 0.0023 bar,
or a claim that any of this is a betting edge. No production change was enacted. No champion was
fitted. No prior screen's directory was written to. The sealed 2025/26 holdout was never opened.
