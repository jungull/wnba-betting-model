# PREREG — E1_I0050, per-cell Type-I for the 54-cell queue left by E1_I0044

Screen `E1_I0050_queue_typeI`. One debt: `E1_I0044_broken_nulls_and_composites` re-measured 54
cells under a repaired ("composed-2") permutation null, found **37 of 54 with p < 0.05 and 17
family-wise significant on the clean decision stratum against a published `p_familywise` of
exactly 1.000**, and **refused to claim it** because it had measured its own null's Type-I on
only five cells, where it came out 0.0225, 0.0250, 0.0525, 0.1475 and 0.5950.

This screen measures Type-I **per cell, for all 54**, and applies the result.

**Partition: 2021–2024 exploration only. 2025/26 is a sealed confirmation holdout and is never
opened.** Every frame read asserts `2021 <= season <= 2024` and `max(gdate) < 2025-01-01`.
`E0_I0014`'s frame contains 2022–2024 only; 2021 is absent from it.

---

## 0. What was already fixed before this document was written

`s00_inventory_anchors.py` and `s01_why1000.py` are read-only. They reproduce prior screens'
published numbers from those screens' own artefacts and take the anatomy of the published
family-wise bar apart. Quoting them here makes it impossible to back-fit §5.

### Anchors reproduced BEFORE any new statistic — 25 of 26 (`run_log_s00.txt`)

| anchor | published | reproduced |
|---|---|---|
| D103 `out/retrospective_power.csv`, keyed `(screen, decision, family_size_K, cell)`, worst arm by `mde80_fw` | 1,349 / 760 / 0.5633802816901409 | **1,349 / 760 / `repr` identical to 16 digits** |
| `E1_I0041` `TSTAT_CELL_FLOORS.csv` `t_statistic` cells | 666 | **666** |
| ... `degeneracy_ratio > 5` | 67 | **67** |
| ... `sd_used_by_D103 == 0` exactly | 6 | **6** (overlap **0**) |
| ... broken total | 73 | **73** |
| ... recorded ADEQUATELY POWERED by D103 (`mde_published <= 0.0023`) | 35 | **35** |
| `E0_I0014` `t_classical`, 348 cells, rebuilt from `analysis_frame.parquet` | — | max rel **3.9388962285971545e-15**, **276 of 348 bitwise** |
| `E0_I0014` `null_correct_sd`, 348 cells, from the saved draws | — | max abs **2.220446049250313e-16** |
| `E0_I0014` `p_correct_level`, 348 cells | — | **0 mismatches** |
| `E0_I0014` `familywise_summary.json` bar mean / p95 / row-naive p95 / observed max\|t\| | 27.577598195648264 / 29.12663204615966 / 3.7295261371093513 / 41.60553110904952 | **all four to 1e-12; the first two also recomputed from the raw draws to 1e-9** |
| `E1_I0044` `BROKEN_NULLS.csv` rows / re-measured | 73 / 54 | **73 / 54** |
| `E1_I0044` A4 composed-2 `p_two_sided < 0.05` over the 54 | 37 | **37** |
| `E1_I0044` A4 composed-2 `p_familywise < 0.05` over the 54 | 17 | **17** |
| `E1_I0044` `TYPE_I_CALIBRATION.csv` median | 0.0525 | **0.0525** |
| the 18 structurally-void cells, identified **by measurement** (`sxx` after the base `< 1e-6`) | 18 | **18, and identical to E1_I0044's labelled set** |

**The one anchor that did NOT reproduce.** `E1_I0044` VERDICT §2 states `E0_I0014` published
`p_familywise_whole_screen = exactly 1.000` for **41 of the 54**. Recomputed from
`screen_results.csv` the count is **49 of the 54** (and **301 of all 348**). No script in
`E1_I0044/scripts/` computes 41. Nearby counts are 45 (`==1.000` and composed-2 A1 `p<0.05`),
36 (`==1.000` and composed-2 A4 `p<0.05`) and 35 (`p_familywise_within_dependent == 1.000`).
**This screen uses 49** and records the discrepancy in `DEFECTS.md` F-1. It does not change the
direction of anything.

### Void-leak check, asserted not assumed

The 18 structurally-void cells are identified **by measuring `sxx` of the design column after the
screen's own base**, not by reading a label: three candidates (`pts__pred_sd`,
`minutes__pred_sd`, `fga__pred_sd`) have `sxx` of 0.0, 9.09e-27 and 4.59e-26 against
**1.3876e+04** for every one of the 54 queue candidates. `|CELLS54 ∩ VOID18| = 0`.
**No structurally void cell is in the queue.** The 54 are listed in full in `run_log_s00.txt`
and in `_QUEUE54.csv`; the count is asserted in code.

### The published family-wise bar, taken apart (`run_log_s01.txt`)

**In 1,000 of 1,000 draws the family-wise `max|t|` is supplied by ONE cell,
`pl_pts_sd5|pts_absres`, whose own null sits at mean `|t|` = 27.58 with sd 0.92.** It is one of
the 73 broken cells. Removing the 18 void cells changes the bar by nothing; removing all 72
broken cells drops its p95 from **29.13 to 9.08**. `E0_I0014`'s own row-naive null gives a
348-cell bar of **3.73**; `E1_I0044`'s composed-2 gives **5.83** (A1) and **5.32** (A4).

---

## 1. Estimand, and the D101 statement for every number in this screen

**Question.** For each of the 54 cells, what is the probability that the test as actually run
rejects at nominal 0.05 when there is no association?

**D101 DENOMINATOR STATEMENT — applies to every statistic, floor and bar reported here.**

| | |
|---|---|
| **response** | one of `{pts,minutes,fga} × {absres,sqres}` — `E0_I0014`'s forecast-error-magnitude responses. Never mixed, never pooled across dependents. |
| **row set** | stated per arm below. Each arm is self-contained. |
| **base** | season fixed effects on that arm's own seasons |
| **SST basis** | the season-demeaned response **on that arm's own rows**. `ΔR² = (SST − SSE)/SST` with both terms from the same arm, same response, same base. |
| **weighting** | unweighted OLS throughout |
| **statistic** | signed classical `t` on the arm-local season-z-scored, season-demeaned candidate; one column |
| **family / bar** | 58 candidates × 6 dependents = **348 cells**, one shared gather index per draw. The family-wise bar is the 95th percentile of `max|t|` over the family within a draw. A one-column statistic is only ever compared against a one-column floor. |
| **null draws** | signed, unstandardised, stored raw |

**Nothing is compared across arms.** Where two arms are shown side by side it is labelled as a
description of two separate measurements, never as a difference.

### Arms

| arm | window | rows | player-season blocks | note |
|---|---|---:|---:|---|
| **A4_CLEAN_DEC** *(reported first — standing requirement)* | 2023–2024 | 3,549 | 174 | decision stratum: `pl_games_prior >= 8 AND pl_min_mean5 >= 24` |
| A1_FULL | 2022–2024 | 13,879 | 475 | the arm the published verdict was formed on, and the arm `E1_I0044` measured its five Type-I numbers on |

2021 is not in `E0_I0014`'s frame at all. The clean window is **2023–2024** (2022's forecasts
depend only on 2021, which is degenerate — all forecasts at fallback level 4).
All 54 queue candidates are player-level, so all use player-season blocks; this is asserted in code.

---

## 2. The synthetic null data — three generators, and why three

A Type-I measurement is only as good as its "no planted effect" generator. `E1_I0044` used one
generator. **Its generator is itself under test here**, because for a candidate that is a
function of within-block position the generator can leave a real association in the data, in
which case a high rejection rate is not the null's fault.

Let `e0` be the cell's own residual after the candidate — the effect-free response — on the arm's
rows, season-demeaned. Let blocks be the arm's (season, player) blocks, `bm` the block means of
`e0` and `dev = e0 − bm[block]`.

| tag | construction | H0 true by construction? |
|---|---|---|
| **EXCH** | block means randomly **reassigned** across blocks within season; within-block deviations randomly **permuted** in position | **YES.** No alignment survives at either level. |
| **CIRCSHIFT** | block means randomly reassigned; within-block deviations **circularly shifted** by a random offset | **YES**, and it *retains* within-block serial correlation, which EXCH destroys. |
| **BLOCKBOOT** | `E1_I0044`'s generator: whole donor blocks resampled with replacement, `don[arange(len(b)) % len(don)]`, so **absolute within-block position is preserved** | **NO, not necessarily.** If `e0` has a within-block positional profile shared across blocks, the profile survives into every synthetic response, and a candidate that is a function of position is genuinely associated with it. |

All three preserve: n, block count, block sizes, the empirical distribution of block means, the
empirical within-block deviation distribution, and hence the response's variance decomposition
and its marginal shape. They differ **only** in what within-block alignment survives.

**Primary validity verdict is taken on EXCH and CIRCSHIFT.** BLOCKBOOT is reported for every
cell as a **confounding diagnostic** and to reproduce `E1_I0044`'s five numbers.

### Null schemes tested against each generator

Per cell, on the same synthetic responses (D101: one contrast — same rows, same response, same
base, same SST): **COMPOSED2** (`E1_I0044`'s repaired null, the instrument under test),
**E0_I0014_LEVEL_MATCHED** (the screen's own published null, between- or within-block by its own
`use_between`), **ROW_NAIVE**.

---

## 3. Sample sizes — PREREGISTERED, and not to be revised after seeing a result

| quantity | value | consequence |
|---|---:|---|
| synthetic datasets per (cell, arm, generator) | **B = 1,000** | Monte-Carlo se at nominal 0.05 = **0.00689** |
| permuted carriers in the pool per (candidate, arm, scheme) | **POOL = 1,000** | |
| null draws per replicate, drawn **without replacement** from the pool | **R_NULL = 500** | `p = (#{|t_null| >= |t_obs|} + 1)/501`; granularity 0.002 |
| cells | **54** | 54 × 2 arms × 3 generators × 3 schemes = **972 rejection rates** |
| seed | 20260808 + cell index | |

**If a quantity turns out not to be estimable at these sizes, that is reported as not estimable.
It is not re-run at a larger size chosen after seeing the answer.**

---

## 4. Validity rule — frozen here, with its tolerance stated

Nominal level **0.05**.

* **NULL_ACCEPTABLE** — measured Type-I `<= 0.075` (1.5 × nominal) under **both** H0 generators
  (EXCH and CIRCSHIFT), for the COMPOSED2 scheme.
* **NULL_INVALID_ANTICONSERVATIVE** — measured Type-I `> 0.075` under either H0 generator.
* **NULL_CONSERVATIVE** (a sub-flag of ACCEPTABLE, not a failure) — Type-I `<= 0.025` under both.
  Recorded because *a degenerate null can make a floor too large, not only too small*, and three
  separately suspected anti-conservative defects in this programme have turned out conservative.
* **CONFOUNDED_WITH_BLOCK_POSITION** (an additional flag, orthogonal to the above) — acceptable
  under both H0 generators but `> 0.075` under BLOCKBOOT. The null is valid; the cell's real-data
  association is entangled with a within-block positional/time profile shared across blocks, and
  the *interpretation* of its p is unverifiable without a position-adjusted base.

**Why 0.075.** At B = 1,000 a truly-nominal test exceeds 0.075 with probability ≈ 2e-4
(z = 3.63), so the rule almost never condemns a valid null; a test whose true level is 0.10 is
caught with probability ≈ 0.999. Exact Clopper–Pearson 95% intervals are reported for every rate
so a reader may impose their own threshold.

**A cell whose null is not acceptable is marked UNVERIFIABLE — not null, and not significant.**

---

## 5. Predictions, frozen before the Type-I measurement is run

**P1 — the composed-2 null is mostly fine.** Under EXCH, **at least 40 of the 54** cells have
Type-I `<= 0.075`.

**P2 — the published 1.000 is the degenerate-null artefact.** Already 1,000/1,000 draws of the
published bar come from one broken cell (§0). The prediction that remains falsifiable: rebuilt on
a null that functions, **at least 30 of the 49 cells** whose published `p_familywise` is exactly
1.000 have a family-wise p `< 0.05` on **A1_FULL** — i.e. the 1.000 was hiding real family-wise
significance rather than the new p being invented.

**P3 — `E1_I0044`'s 0.5950 is a generator artefact, not a null defect.** For the three
position-monotone candidates (`pl_games_prior`, `pl_minutes_prior`, `pts__n_prior_games`),
COMPOSED2 Type-I is `> 0.075` under BLOCKBOOT and `<= 0.075` under EXCH, on A1_FULL.
*This is the prediction whose failure would mean the null really is broken for counters.*

**P4 — shape predicts inflation.** Across the 54 cells, the Spearman correlation between the
candidate's within-block excess kurtosis and its COMPOSED2 Type-I under EXCH exceeds **0.5**,
and a two-feature rule (heavy tail; position-monotonicity) separates acceptable from
non-acceptable with at most **5 misclassifications of 54**.

**P5 — the queue mostly does not survive as a decision-stratum finding.** After applying §4, at
most **12 of the 17** A4 family-wise-significant cells remain, and the surviving set contains
**no cell whose ΔR² clears D103's 0.0023 comparison bar on a like-for-like response**.

**The pre-stated outcome that would clear the queue entirely:** every one of the 54 has an
acceptable null AND its corrected family-wise p on A4 is `< 0.05` AND its ΔR² exceeds the
single-cell floor. That outcome is available and is not expected.

**The pre-stated outcome that would kill it entirely:** Type-I `> 0.075` under EXCH for every
cell, in which case all 54 are UNVERIFIABLE and nothing survives. That outcome is available and
is a fully acceptable result.

---

## 6. Instrument self-tests, run and reported whether they pass or fail

**My own instrument is the thing under test.** `E1_I0044`'s first repaired null was defective in
the same shape as the defect it repaired. Four checks, all pre-committed:

1. **Reproduce `E1_I0044`'s five Type-I numbers** by running my harness under BLOCKBOOT on
   A1_FULL — their generator, their arm, their three schemes. Agreement is expected within Monte
   Carlo error only (different RNG stream, B 1,000 vs 400, R_NULL 500 vs 300); the criterion is
   `|mine − theirs| <= 3 × sqrt(p(1−p)(1/1000 + 1/400))` for all five, and **the ordering of the
   five must be preserved**.
2. **Positive control on level.** A synthetic candidate that is iid noise within season, carrying
   no block structure, run through the full pipeline: COMPOSED2 Type-I must be within
   `0.05 ± 3 MC se` under EXCH.
3. **Positive control on power.** An effect of ΔR² = 0.005 injected into EXCH responses on three
   cells: rejection rate must exceed 0.50, proving the harness can reject at all and is not
   returning non-rejection for a mechanical reason.
4. **Degenerate-null control.** `E0_I0014`'s own level-matched null applied to
   `pl_pts_sd5|pts_absres` — the cell that supplies 100% of the published family-wise bar. Its
   measured Type-I is reported whatever it is.

**Every defective output is preserved, never overwritten.** Any re-run writes to a new filename
with the reason recorded in `DEFECTS.md`.

---

## 7. Constraints

* 2021–2024 only; **2025/26 never opened**. Manifests: `row`/`season` usable, `artifact` not;
  MISSING = UNVERIFIABLE.
* Write scope is `experiments/exploration/E1_I0050_queue_typeI/` and nothing else. **The shared
  screen kit is not modified** — three sibling agents hold it open. No `git` write command.
* **No blanket process kill of any kind.** No `Get-Process python | Stop-Process`, no `taskkill`.
  Only PIDs launched by this screen are ever touched and every one is recorded in `NOTES.md`.
* Signed, unstandardised draws stored; every stratum arm saved; `np.abs` at no storage site.
* No name-based selection: the 54 are an explicit allowlist, printed in full, count asserted, and
  checked disjoint from the 18 void cells.
* No production change. No champion fitted. No prior screen's directory written to.
