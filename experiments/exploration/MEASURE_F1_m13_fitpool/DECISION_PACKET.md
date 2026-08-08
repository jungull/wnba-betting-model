# F1 — how wrong is M13's residual fit, really?

**A decision packet for the user. Nothing here was written into M13 or M14; they are untouched.**

---

## The one-line answer

**The verdict survives. Fixing the defect does not change M13's conclusion, and it barely moves the
numbers — but the direction of the movement is the opposite of what everyone expected.**

M13 published `TRANSLATION_WORSE_CALIBRATED_THAN_MARKET`. Re-fit honestly — every scored game using
only residuals from games that had already been played — the verdict is still
`TRANSLATION_WORSE_CALIBRATED_THAN_MARKET`, and it is still worse by a margin roughly **26 times
larger** than the entire correction.

---

## Before anything else: the reproduction is exact

Every counterfactual below is only worth reading if the harness can first reproduce M13 as it
stands. It can, perfectly.

| check | result |
|---|---|
| 83 published numeric quantities, field by field | **max absolute difference 0.000e+00** |
| `translation_rows.parquet` sha256 | **byte-identical** |
| `FINDINGS.json` `result_hash` | **byte-identical** |
| M14 re-run against published M13 (control) | **`result_hash` byte-identical**, slope delta 0.000e+00 |

So nothing below is harness noise.

---

## What the defect actually is, and what it isn't

The audit is factually right about the code. `FIT_SEASONS = [2022…2026]`, the only exclusion is
row-level (`~row_uid.isin(matched)`), and there is no date filter anywhere. A game played in May
2024 is priced using an error distribution estimated partly on games from 2026.

But the *consequence* is much smaller than the mechanism suggests, for a reason worth understanding
before you rule:

- The fit pool is **already row-disjoint** from the rows being scored. The leak cannot let the model
  memorise the very games it is graded on.
- What is being fitted is a **three-number unconditional error distribution** (location, scale,
  degrees of freedom) estimated on **8,000–16,000 residuals**. There is essentially no capacity for
  "the future" to be stored in three parameters at that sample size.

So this is a real specification error, but it is a specification error in an object with almost no
room to absorb the information it is illegitimately seeing.

---

## The three variants, side by side (A_primary headline)

| quantity | **A — published (pooled 2022-26)** | **B — pooled, 2022-24 only** | **C — time-ordered (honest)** |
|---|---|---|---|
| fit pool size | 16,162 | 10,981 | expanding, 8,333 → 16,075 |
| primary family (AIC) | student_t | student_t | student_t (all 260 refits) |
| normal loc | −0.015165 | −0.062288 | −0.0946 → −0.0139 |
| normal scale | 5.15931 | 5.32620 | 5.5254 → 5.1606 (mean 5.3130) |
| student-t df | 8 | 7 | 8 on 217 dates, 7 on 43 |
| student-t scale | 4.46809 | 4.50146 | 4.7748 → 4.4692 |
| **Brier (primary)** | **0.274824** | 0.274607 | **0.274051** |
| Brier (market) | 0.248841 | 0.248841 | 0.248841 |
| **Brier gap vs market** | **0.025983** | 0.025766 | **0.025210** |
| **log-loss (primary)** | **0.763220** | 0.761361 | **0.759898** |
| log-loss gap vs market | 0.072406 | 0.070547 | 0.069084 |
| Brier-diff CI95 | [0.021129, 0.031188] | [0.020983, 0.030842] | [0.020431, 0.030281] |
| **Brier-diff CI95 width** | **0.010059** | 0.009859 | **0.009849** |
| log-loss-diff CI95 width | 0.033361 | 0.032078 | 0.031966 |
| **`calib_verdict`** | WORSE THAN MARKET | WORSE THAN MARKET | **WORSE THAN MARKET** |

Evaluation universe is identical across all three (5,737 A_primary player-games, 254 game-date
clusters, seasons 2024-2026). Nothing is confounded by a changing universe.

### The expected direction did NOT hold — say it plainly

The brief predicted the pooled fit would look **better calibrated and tighter** than an honest one.
**It does not. It looks slightly *worse* and slightly *wider*.**

- Honest Brier is **lower** (better) by 0.00077. The gap to the market **narrows** by 3.0%.
- Honest CI is **tighter**, not wider: −2.1% on Brier, −4.2% on log-loss.

The mechanism is straightforward once you see the scale parameter. Pooling in the future gives a
**tighter** dispersion (5.1593 vs an expanding-window mean of 5.3130), which makes the translated
probabilities **more confident**. M13's own finding is that this model has *poor discrimination* —
its probabilities spread across the range while realized frequency stays flat near 0.47. Extra
confidence on top of poor discrimination is **punished** by Brier and log-loss. The leak flattered
the *likelihood* of the fit while *hurting* its calibration score.

**Practical reading: M13's published number is, if anything, marginally harsh on itself. The defect
did not manufacture a favourable result.** This contradicts the audit's stated `direction` field for
F1 ("The leak biases the model favourably"), which should be corrected — it was an unprobed inference,
and the probe now exists.

---

## Is the change bigger than the noise? Two answers, both true

| question | answer |
|---|---|
| Is the move large relative to M13's own uncertainty? | **No.** The whole A→C move in the Brier gap (0.00077) is **7.7% of the published CI95 width** (0.01006). It is an order of magnitude inside the artifact's own error bars. |
| Is the move a real, systematic shift rather than resampling luck? | **Yes.** The per-row paired difference-of-differences, cluster-bootstrapped by game date with the node's own seed and method, gives Brier CI95 **[−0.000941, −0.000616]** — excluding zero. |

Both matter. The shift is **real and negligible**. Anything that quotes M13's gap to two decimal
places is unaffected; anything that would claim "we closed the gap by X" where X is of order 0.001
is not safe on the published fit.

**At the individual quoted probability level:** switching to the honest fit moves any single
`p_over` by RMSE **0.0040**, max **0.019**, and flips the over/under call on **0.31%** of rows. For
scale, M13 *already publishes* a disagreement between its own `normal` and `student_t` variants of
RMSE 0.0111, and between `normal` and `empirical` of RMSE 0.0435 with a **16.2%** call-flip rate —
and treats those as tolerable, reported sensitivity. **The leak is 0.36× the size of a disagreement
the node already lives with, and 0.09× the size of another.**

---

## Does M14 move? (fully traced, not estimated)

M14 was re-run end to end, five times, against each counterfactual `translation_rows.parquet`. The
control run against the real published M13 reproduced M14's `result_hash` byte-identically, so the
trace is trustworthy.

| M14 headline | published (A) | B | C (honest) | D (both fixes) |
|---|---|---|---|---|
| pooled falsification slope | −0.098248 | −0.098961 | −0.099608 | −0.098420 |
| slope CI95 width | 0.171610 | 0.173502 | 0.173247 | 0.174125 |
| slope distinguishable from 0 | yes | yes | yes | yes |
| **`falsification.verdict`** | FALSIFIED | FALSIFIED | **FALSIFIED** | FALSIFIED |
| by-season slope 2024 / 2025 / 2026 | −0.145 / −0.135 / −0.033 | −0.146 / −0.137 / −0.033 | −0.147 / −0.139 / −0.033 | −0.147 / −0.137 / −0.033 |

The largest slope movement is **0.0014, which is 0.8% of M14's own CI width**. Every M14 verdict,
every season sign, and every leave-out-top-N influence check is unchanged. **M14 is materially
unaffected.**

*What I could not establish:* M14 quantities that do not depend on M13's `p_over_*` columns (parts of
the book-level reconstruction) are unchanged by construction and were not separately re-derived.

---

## Decomposition: time-ordering vs holdout-inclusion (a full 2×2)

These are separately remediable and you may want to rule differently on each.

| Brier gap vs market | seasons 2022-2026 | seasons 2022-2024 |
|---|---|---|
| **pooled (no time cutoff)** | **A = 0.025983** (published) | B = 0.025766 |
| **time-ordered (expanding)** | C = 0.025210 | D = 0.025399 |

| effect | size | share |
|---|---|---|
| holdout inclusion alone (A→B) | −0.000217 | **~22%** |
| time ordering alone (A→C) | −0.000774 | **~78%** |
| both together (A→D) | −0.000584 | 5.8% of the published CI width |

Two things to note. **Time-ordering is the larger of the two defects, by roughly 3.5:1.** And the two
are **not additive** — applying both moves the gap *less* than time-ordering alone, because removing
2025/2026 from an already-time-ordered pool starves the 2025/2026 rows of history and partly cancels
the effect. Both effects point the same way (the honest gap is *smaller*), and both are tiny.

---

## Method notes you should check before ruling

- **Time-ordering was verified on column values, not text.** At each of the 260 refits, the maximum
  `game_date` in the fit pool was asserted strictly less than the evaluation date. **0 violations.**
- **Minimum-sample rule, fixed before any variant was run:** a row is unscorable if its prior pool
  holds < 500 residuals; unscorable rows are counted and dropped, with **no fallback to the pooled
  fit** (a fallback would silently reintroduce the defect). **Zero rows were unscorable** — the
  props archive confines evaluation to 2024-2026 while the fit pool starts in 2022, so the thinnest
  pool any row ever saw was 8,333 residuals, 16.7× the threshold.
- **Holdout discipline.** The evaluation universe is 2024-2026, so this necessarily reads 2025/2026.
  That is licensed only because M13's published numbers already rest on those seasons and this is an
  audit of an existing artifact. Nothing new was discovered or tuned on them; variants B and D give
  the 2022-2024-fit version of every headline.

---

## ⚠ The foundation underneath this defect is unverifiable

Per-artifact manifest check on all 15 inputs M13 actually consumes:

| status | count | which |
|---|---|---|
| **`asof_granularity: "row"`** (bounded, filterable) | **1** | `data/masters/master_player.parquet` |
| **`asof_granularity: "artifact"`** (whole-file bounded; **filtering does not help**) | **6** | all six `predictions__player_scoring_distribution__{season}.parquet` |
| **NO MANIFEST AT ALL — UNVERIFIABLE, not a pass** | **8** | all six outcome gamelogs, `prediction_contract_v5/player_game_enriched.parquet`, and `data/props_capture/historical/master_props_historical.csv` |

**This matters more than F1 does.** My time-ordered counterfactual orders rows by their recorded
`game_date`, which is the best bound available — but the model predictions themselves are
artifact-granular, so **no row-level filter, including mine, can bound them.** If those prediction
files were produced with cross-season information, this measurement does not remove it and does not
claim to. The measured F1 correction is small; the unbounded foundation is a much larger open
question, and it is prior to this one.

---

## Remediation options and their costs

| option | what it costs | what it buys |
|---|---|---|
| **1. Do nothing; annotate.** Add a documented limitation to M13's `could_not_establish` recording the pooled fit, the measured magnitude, and the direction. | ~zero. No re-run, no downstream invalidation, no passed-node reopening under GRAPH_POLICY 6. | Honest disclosure. The published numbers stand as measured-correct-to-0.001. **Recommended if the measured magnitude is what you care about.** |
| **2. Re-run M13+M14 with the time-ordered fit (variant C).** | Both nodes' published figures change in the 4th decimal; `result_hash` and `translation_rows.parquet` sha256 change; every citation of those hashes must be refreshed. Requires your GRAPH_POLICY 6 ruling to reopen two passed nodes. Compute is small (~15 min). | A specification that is defensible on its face. Buys no change in any conclusion. |
| **3. Re-run with variant D (time-ordered AND 2022-24 only).** | Same as option 2, plus it starves 2025/2026 rows of legitimate prior history and gives a *worse* honest estimate than C. | Cleanest holdout story. **Statistically the weakest of the three fits.** |
| **4. Fix the code without re-publishing.** Correct `build_translation.py` so any future run is time-ordered, leaving the current published artifacts and their hashes alone, with a note that they were produced under the old specification. | Small. Avoids reopening published figures. | Stops the defect propagating to any future node built on this code. **Pairs well with option 1.** |

**My read, for what it is worth:** the defect is real, the measurement is clean, and the impact is
immaterial — 7.7% of the artifact's own confidence interval, in the direction that made M13 look
*worse* rather than better, with no verdict flip anywhere in M13 or M14. Options 1 + 4 together get
you honesty and prevention at near-zero cost. Option 2 is defensible but buys a fourth-decimal
change at the price of reopening two passed nodes. **The unverifiable-manifest problem in the table
above is the more consequential thing on this page.**

---

## Where I could have cheated

- **Specifications were fixed before results.** The minimum-sample rule, the no-fallback rule, the
  common-subset rule, the AIC family-selection rule and the noise test were written into
  `step2_variants.py`'s `SPEC` block and saved to disk **before any variant was executed**. The only
  thing added afterwards was variant D, added to complete the 2×2 the task asked for — and D is
  reported as it fell, which is the *less* tidy answer (it moves the gap less than C).
- **I used the mildest honest re-specification.** An expanding window using all prior residuals. A
  shorter rolling window would show a **larger** delta. I did not run one. **The reported magnitude
  is a lower bound on how much an aggressive re-specification could move things.**
- **I report both noise answers.** I could have quoted only "delta ≪ CI width, immaterial" or only
  "paired CI excludes zero, real". Both are true, they answer different questions, and both are above.
- **No silent fallbacks.** The thin-pool count (0) is measured and reported, not assumed.

---

## Files

All inside `experiments/exploration/MEASURE_F1_m13_fitpool/`:

`MEASUREMENT.json` (full machine-readable record) · `DECISION_PACKET.md` (this file) ·
`step0_manifests.py/.json` · `step1_reproduce.py` / `step1_reproduction.json` ·
`step2_variants.py/.json` · `step3_variantD_and_parquets.py` / `step3_variants2x2.json` ·
`step4_m14_trace.py/.json` · `step5_rowlevel_drift.py/.json` · `step6_assemble.py` ·
`m13_lib.py`, `m14_lib.py` (copies, path constants only) · `cf_*/translation_rows.parquet`
(counterfactual outputs) · `m14_out/*/FINDINGS.json` (counterfactual M14 runs) ·
`time_ordered_per_date_fits.csv` (all 260 refits) · `run_log*.txt`
