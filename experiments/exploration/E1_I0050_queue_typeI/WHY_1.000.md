# WHY_1.000 — which side of the discrepancy is the artefact

`E0_I0014` published `p_familywise_whole_screen = exactly 1.000` for **49 of the 54 queue
cells** (and for **301 of all 348**). `E1_I0044` re-measured the same cells under a repaired
null and got `p < 0.05` on 37 of 54 and family-wise significance on 17. One of those two
numbers is an artefact. This document says which, by measurement.

**Answer: the 1.000 is the artefact. It is one cell's broken null, and nothing else.**
The new `p < 0.05` is not an artefact — the repaired null's measured Type-I is at or below
nominal on every cell of both arms under both genuinely-H0 generators.

---

## D101 statement for every number below

| | |
|---|---|
| response | each of `{pts,minutes,fga} × {absres,sqres}` separately; never pooled |
| row set | `E0_I0014`'s own 13,879 rows, 2022–2024, all rows — the arm the verdict was formed on |
| base | season fixed effects (3 seasons) |
| SST basis | season-demeaned response on those same rows |
| weighting | unweighted OLS |
| statistic | signed one-column classical `t`; one-column statistic, one-column floor |
| family | 58 candidates × 6 dependents = **348 cells**, one shared gather index per draw |
| bar | `max|t|` over the 348 cells within a draw; `p_fw = P(bar >= |t_obs|)`, R = 1,000 |

---

## 1. The published bar is one cell

`_PUBLISHED_BAR_ANATOMY.csv`, `run_log_s01.txt`. Rebuilt from `permutation_nulls.npz` —
`E0_I0014`'s own saved draws — and reproducing `familywise_summary.json` to 1e-9.

**In 1,000 of 1,000 draws the family-wise `max|t|` is supplied by the same single cell,
`pl_pts_sd5|pts_absres`.** Its own null sits at mean `|t|` = **27.578** with sd **0.917**.
The bar is that cell's null and nothing else.

| the 348-cell bar | mean | p95 |
|---|---:|---:|
| **as published** (correct-level null) | **27.578** | **29.127** |
| after removing the 18 structurally void cells | 27.578 | 29.127 |
| **after removing all 72 broken cells** | **7.398** | **9.078** |
| `E0_I0014`'s own row-naive null, same 348 cells | 2.915 | **3.730** |
| `E1_I0044`'s composed-2 null, same 348 cells, A1 | 4.102 | **5.835** |
| composed-2, A4 decision stratum | 3.820 | **5.323** |
| composed-2, restricted to cells whose null this screen validated — A4 / A1 | — | **4.072 / 4.609** |

A bar at 29.13 means every cell with `|t_obs| < 29.13` returns `p_fw` at or near 1.000. The
observed `max|t|` over the whole screen is 41.606, which is why the *screen-level*
`familywise_p_whole_screen` is 0.0000 while 301 of its 348 individual cells read exactly 1.000.
**Both numbers come out of the same broken bar.**

### Null mean `|t|` by group, 348 cells

| group | cells | median null mean `\|t\|` | max |
|---|---:|---:|---:|
| not broken | 276 | 1.393 | 6.209 |
| broken, not void | 54 | **7.692** | **27.578** |
| structurally void | 18 | 5.18e-14 | 2.28e-13 |

The void cells contribute nothing to the bar — removing them changes it by zero. **The bar is
driven by null *location*, not by null width**: `pl_pts_sd5|pts_absres` has a null sd of 0.917,
which is normal; it is centred at 27.6, which is not.

---

## 2. The mechanism, isolated

`_SELFTESTS.csv` T4. `E0_I0014`'s own within-block null applied to `pl_pts_sd5|pts_absres`:

| null on the real response | mean signed `t` | sd |
|---|---:|---:|
| `E0_I0014`'s own (within-block) | **+27.616** | 0.872 |
| composed-2 | **−0.135** | 1.672 |

+27.616 reproduces the published bar mean of 27.578 to within my own draw noise. The within-block
shuffle preserves each block mean exactly, the candidate's association with the response lives in
the block means, so the permuted `t` is essentially the observed `t`. **The null contains the
alternative.** `E1_I0044` established this mechanism (its M-WITHIN); this screen confirms it in a
single number and shows it is the whole of the published bar.

### And this defect is invisible to a Type-I study — measured, not assumed

The same cell, same null, Type-I at δ = 0 under the EXCH generator: **0.057**, against a nominal
0.05. **`E0_I0014`'s null is not anticonservative. Its defect is blindness**, which is a power
and bar failure. A Type-I measurement alone would have cleared it. This matters for how the
programme reads any future null audit: level and blindness are different failures and need
different instruments.

---

## 3. Is the new `p < 0.05` the artefact instead?

No. `TYPEI_PER_CELL.csv`, 54 cells × 2 arms × 3 generators × 3 schemes, B = 1,000 synthetic
datasets per cell per generator (preregistered).

| composed-2 Type-I, nominal 0.05, tolerance 0.075 | A4_CLEAN_DEC | A1_FULL |
|---|---|---|
| EXCH generator — median / max / **n above tolerance** | 0.0205 / 0.0590 / **0 of 50** | 0.0260 / 0.0700 / **0 of 54** |
| CIRCSHIFT generator — median / max / **n above tolerance** | 0.0225 / 0.0920 / **2 of 50** | 0.0320 / 0.0860 / **1 of 54** |

The repaired null does not over-reject. It **under**-rejects: the median is roughly *half*
nominal. A conservative null cannot manufacture `p < 0.05`; if anything it suppresses it.

### The counterweight, in the same breath

Because the null is conservative, **every floor `E1_I0044` published for these cells is too
large and every `BLIND` verdict resting on one is pessimistic.** That is the third separately
suspected anticonservative defect in this programme to turn out conservative on measurement, and
it is the direction that costs power rather than the direction that invents findings.

The mechanism is measured, not inferred (`_HARNESS_EXACTNESS.csv`). Composed-2 fills a receiving
block from **one** donor block, so the permuted carrier inherits that donor's block mean and
acquires between-block structure the real column need not have:

| between-block variance share of an **iid** carrier | |
|---|---:|
| real | 0.0344 |
| after composed-2 (with replacement) | **0.1142** |
| after composed-2 (without replacement) | 0.1058 |
| after a row-naive permutation | 0.0342 |

A 3.3× manufactured design effect. It is **not** the with-replacement resampling — removing that
changes 0.114 to 0.106. It is the whole-block donor assignment itself.

---

## 4. Applying it: what the 1.000 was hiding

`CORRECTED_VERDICTS.csv`. Family-wise bar = 95th percentile of `max|t|` over the same 348 cells
under composed-2, `p = (k+1)/(R+1)`, R = 2,000.

**A4_CLEAN_DEC (2023–24 decision stratum, n = 3,549, 174 player-season blocks) — reported first:**

| | cells |
|---|---:|
| of the 49 with a published `p_fw` of exactly 1.000 | 47 have an acceptable null |
| ... of those, family-wise `p < 0.05` under a null that functions | **15** |
| all 54: family-wise significant with an acceptable, unconfounded null | **16** |

**A1_FULL (2022–24, n = 13,879, 475 blocks), retained only for like-for-like with the published
cell:**

| | cells |
|---|---:|
| of the 49, acceptable null | 48 |
| ... family-wise `p < 0.05` | **31** |
| all 54: family-wise significant, acceptable null, not confounded | **24** |

**So the 1.000 was hiding 31 family-wise-significant cells on the very arm the published verdict
was formed on.** That is a verdict-level correction to a live screen.

---

## 5. What most weakens this document

1. **A conservative bar is still a contaminated bar.** The composed-2 family-wise bar is built
   over all 348 cells, and composed-2 is conservative on most of them, so the bar (A4 5.323) is
   larger than a bar over only the cells whose nulls this screen validated (A4 4.072). Every
   family-wise verdict here is therefore *conservative*, not liberal — but it is not the bar an
   exact null would give, and I did not build one.
2. **Bonferroni is not estimable at R = 2,000.** The smallest achievable per-cell `p` is
   1/2,001 = 0.0005; × 348 = 0.174. No cell can clear a Bonferroni bar at this draw count, and
   raising the draw count was not preregistered and was not done. The max-`|t|` bar is the only
   multiplicity control available here, and it is the one `E0_I0014` itself chose.
3. **`E1_I0044`'s stated "41 of the 54" does not reproduce.** The count from
   `screen_results.csv` is 49. No script in `E1_I0044/scripts/` computes 41. Nearby counts are
   45, 36 and 35 (`DEFECTS.md` F-1). It does not change any direction, but a headline number in
   a live verdict is wrong.
4. **The whole of §1–§2 rests on `E0_I0014`'s saved draws being what it says they are.** They
   reproduce its published `t_classical` (276 of 348 bitwise), `null_correct_sd` (2.2e-16),
   `p_correct_level` (0 mismatches of 348) and its `familywise_summary.json` (1e-12), so this is
   about as well anchored as it can be without a refit — but it is still the screen auditing
   itself with its own artefacts.
5. **None of this makes a betting edge**, and the reason is a D101 reason. The response is
   forecast-error magnitude. D103's 0.0023 comparison bar is a ΔR² on D089 walk-forward
   **points**. Different response, different SST, different base. Every ΔR² in
   `CORRECTED_VERDICTS.csv` is on the former and must not be read against the latter, which is
   `E1_I0041`'s standing objection to D103's design and is inherited here unchanged.
