# Degenerate regions in the champion's output — 2022–2024

**Answer to the question that was asked: beyond the cold-start region already known from D092 and
D094, there are ZERO new degenerate regions.**

The brief was right that this is a good answer. The champion is sound outside a region that has
already been identified. Below is what that conclusion rests on, one genuinely new *structural*
fact inside the known region that is worth money, and two defects that a skill-ranked sweep would
have ranked away to nothing.

---

## 1. The headline, and how hard it was tested

The sweep ran a checklist fixed and hashed **before any data was read** (`_prereg.json`, sha256
`895bac8bc2255c9d660ac956873884eefbc95ddab6128fd80cbf90b8cbc6dac0`): six defect families across twenty pre-game partitions, four targets, two arms, three
seasons — **1,612 cells**.

**103 of the 104 cells flagged as constant or near-constant are ≥99% inside the
champion's own `is_fallback` flag.** The single exception is 98.2% inside it.

`is_fallback`, `component_id == */prefix_mean`, `fallback_level in {2,3}`, `is_cold_start`,
`n_prior_games == 0`, `n_prior_appearances == 0`, the low bins of the player's season game index,
`tip_time_quality is null` and `fit_eligible == False` are **not nine discoveries. They are one
population seen through nine windows.** (`tip_time_quality is null` is 100.0% inside `is_fallback`
on all three continuous targets — 1,071 of 1,071 rows.)

The decisive test is the **residual sweep**: the entire checklist re-run with the known fallback
rows removed. Across **286 non-fallback cells it flagged near-constancy exactly
0 times.**

**Positive control — the sweep must find the one known instance or it is broken.** It does,
unaided:

| quantity | D092 published | this screen |
|---|---|---|
| points, `n_prior_appearances < 3` | mean 8.704, sd 0.013 | **mean 8.7061, sd 0.0138** (n=5,378, exactly 3 distinct values) |
| minutes, same rows | mean 21.62, sd 0.09 | **mean 21.6056, sd 0.0878** |
| attempts, same rows | *not reported by D092* | mean 7.3146, sd 0.0360 |
| pooled points skill (D081) | −0.22% | **−0.2222%** |

The skill figure reproduces D081's published number to four decimals against D081's own stored
reference column, which validates the join, the truth mapping and the scoring path before any new
claim is made.

---

## 2. What IS recoverable — and the new structural fact about where it lives

D092 described the region as *"fewer than 3 prior appearances"*. That phrase covers **two
populations whose recoverable value differs by more than an order of magnitude**, and the smaller
one holds almost all of it.

Measured against D081's own reference column, v15 arm. **The row counts here are SCOREABLE rows**
— the ones an error can actually be computed on — which is why they are smaller than the
predicted-row counts in the ranked table further down:

| target | sub-region | scoreable rows | skill before | skill after | gain |
|---|---|---|---|---|---|
| points | whole region (<3 prior appearances) | 1061 | -0.22% | +2.67% | **+2.8957%** |
| points | 0 prior appearances | 114 | -0.22% | -0.15% | **+0.0767%** |
| points | 1-2 prior appearances | 947 | -0.22% | +2.59% | **+2.8169%** |
| minutes | whole region (<3 prior appearances) | 1061 | +3.55% | +8.65% | **+5.0951%** |
| minutes | 0 prior appearances | 114 | +3.55% | +3.66% | **+0.1035%** |
| minutes | 1-2 prior appearances | 947 | +3.55% | +8.54% | **+4.9885%** |
| attempts | whole region (<3 prior appearances) | 1061 | +0.12% | +4.25% | **+4.1303%** |
| attempts | 0 prior appearances | 114 | +0.12% | +0.21% | **+0.0907%** |
| attempts | 1-2 prior appearances | 947 | +0.12% | +4.15% | **+4.0358%** |

**Read the points row.** Routing the whole region gains **+2.90%**. Routing only the zero-history
rows gains **+0.08%**. Routing only the one-or-two-prior-appearance rows gains **+2.82%, which is
97% of the total.**

**Two facts drive that, and they compound:**

1. **Most zero-history rows are not scoreable.** A player with no prior appearances frequently does
   not appear in this game either, so the row carries no outcome. `fallback_level == 2` is **33.7%
   of the region's predicted rows (1,815 of 5,378) but 89.3% of its scoreable rows (947 of
   1,061)**. Both numbers are in the tables; quoting only the first would overstate how much the
   sub-region narrows the operational footprint.
2. **The champion is much worse where it is scoreable.** It loses to the tuned simple baseline by
   **9–10%** on the zero-history rows and by **39–66%** on the one-or-two-appearance rows. That gap
   is not a scoreability artefact — it is measured on the same rows for both forecasts.

**Why this matters practically.** On a row with no history at all a constant is defensible — there
is little to condition on and a simple baseline is nearly as blind. On a row where the player has
already played once or twice, the baseline uses that and the champion does not.

> The defect is not *"the champion emits a constant when it knows nothing"*.
> It is **"the champion keeps emitting the constant after it has started to know something."**

Both sub-regions are readable from the champion's own `fallback_level` column at forecast time.
**A rule that routes only `fallback_level == 2` captures ~97% of the value while touching 34% of
the region's predicted rows**, and leaves the genuinely-no-history rows on the champion.

### The full ranked table

| arm | target | region | rows | share | champ loss | base loss | champ worse by | pooled gain | worst over k-grid |
|---|---|---|---|---|---|---|---|---|---|
| v14 | minutes | R1_is_fallback | 2459 | 13.8% | 9.747 | 6.954 | +40.2% | **+5.43%** | +0.74% |
| v15 | minutes | R1_is_fallback | 5378 | 24.9% | 9.539 | 6.722 | +41.9% | **+5.40%** | +0.73% |
| v14 | minutes | R3_fallback_level_2 | 1409 | 7.9% | 9.829 | 6.013 | +63.5% | **+4.91%** | +0.71% |
| v15 | minutes | R3_fallback_level_2 | 1815 | 8.4% | 9.688 | 5.846 | +65.7% | **+4.91%** | +0.68% |
| v15 | attempts | R1_is_fallback | 5378 | 24.9% | 4.523 | 3.343 | +35.3% | **+4.51%** | +0.68% |
| v14 | attempts | R1_is_fallback | 2459 | 13.8% | 4.418 | 3.260 | +35.5% | **+4.50%** | +0.69% |
| v15 | attempts | R3_fallback_level_2 | 1815 | 8.4% | 4.486 | 2.928 | +53.2% | **+3.96%** | +0.65% |
| v14 | attempts | R3_fallback_level_2 | 1409 | 7.9% | 4.410 | 2.873 | +53.5% | **+3.95%** | +0.63% |
| v14 | points | R1_is_fallback | 2459 | 13.8% | 6.036 | 4.697 | +28.5% | **+3.28%** | +0.51% |
| v15 | points | R1_is_fallback | 5378 | 24.9% | 6.057 | 4.739 | +27.8% | **+3.19%** | +0.52% |
| v14 | points | R3_fallback_level_2 | 1409 | 7.9% | 6.083 | 4.313 | +41.1% | **+2.87%** | +0.48% |
| v15 | points | R3_fallback_level_2 | 1815 | 8.4% | 6.133 | 4.413 | +39.0% | **+2.77%** | +0.48% |
| v14 | p_active | R1_is_fallback | 1466 | 8.2% | 0.162 | 0.131 | +23.7% | **+2.08%** | -0.37% |
| v14 | p_active | R3_fallback_level_2 | 977 | 5.5% | 0.168 | 0.121 | +38.3% | **+2.08%** | -0.06% |
| v15 | attempts | R2_is_cold_start | 3563 | 16.5% | 4.596 | 4.163 | +10.4% | **+0.55%** | +0.03% |
| v14 | attempts | R2_is_cold_start | 1050 | 5.9% | 4.435 | 4.023 | +10.2% | **+0.54%** | +0.06% |
| v14 | minutes | R2_is_cold_start | 1050 | 5.9% | 9.587 | 8.806 | +8.9% | **+0.51%** | +0.03% |
| v15 | minutes | R2_is_cold_start | 3563 | 16.5% | 9.242 | 8.453 | +9.3% | **+0.51%** | +0.04% |
| v15 | points | R2_is_cold_start | 3563 | 16.5% | 5.904 | 5.380 | +9.7% | **+0.42%** | +0.03% |
| v14 | points | R2_is_cold_start | 1050 | 5.9% | 5.944 | 5.456 | +8.9% | **+0.40%** | +0.03% |
| v14 | p_active | R2_is_cold_start | 489 | 2.7% | 0.149 | 0.149 | +0.3% | **+0.01%** | -0.30% |

Every gain above is significant at the block sign-flip floor (p = 0.00025; clusters =
season × player; 4,000 draws) and stays positive at the **worst** of 8 shrinkage constants × 2
estimator forms.

---

## 3. The counterexample: degenerate does NOT mean recoverable

The **v15 `p_active`** head emits **exactly one** distinct value — 0.8, sd 2.2e-16 — on 2,268 rows
under `component_id == p_active/declared_constant`. By the preregistered test this is the *most*
degenerate cell in the entire sweep.

**Routing it to the simple baseline loses 4.96% of pooled Brier skill.** The flat 0.8 is genuinely
better there than a prior-appearance-rate estimator. The same region on the **v14** arm *gains*
2.08%.

A blanket "route every fallback region" rule would **destroy** v15 `p_active` skill. The decision
has to be made per (arm, target), and this is the case that proves it.

---

## 4. Two defects a skill-ranked sweep would have ranked away

### 4a. `pred_sd` is a per-season constant — on 100% of rows

`pred_sd` takes **exactly one value per season** on each continuous target — **three distinct
values across 2022–2024** — on all 21,617 (v15) and 17,809 (v14) rows. Every player in a season is
emitted with the same predicted dispersion: the leading scorer and the twelfth man alike. Its
correlation with the champion's own realised absolute error runs **−0.0122 to +0.0002**, which is
indistinguishable from zero.

**The sharp part: the quantiles are fine.** On the same rows `q95 − q05` takes **6,519** distinct
values for points, 1,912 for minutes and 4,550 for attempts; nothing ever crosses; coverage is
86.5–87.7% against a nominal 90%. The champion **does** carry per-row dispersion — it simply does
not put it in `pred_sd`.

> **Anything downstream that sizes stakes or computes edge from `pred_sd` is reading a per-season
> constant, while a per-row answer sits unused two columns away.**

`p_active` is worse: `pred_sd` **and all five quantile columns are 100% NULL** on every row of both
arms — 21,617 and 17,809 rows respectively. That head emits no uncertainty at all.

**Recoverable pooled skill: zero.** The point forecast is untouched, so the skill metric is blind to
this. That is exactly why it is reported separately instead of being ranked away — and why a screen
that ranks only by recoverable value would have missed it entirely.

### 4b. A zero floor on the lower quantile

No prediction and no `q05` is ever negative, and the minimum is exactly 0.0, so both are clipped at
zero. 135 v15 points predictions sit exactly at 0.0. The **lower quantile** saturates far more
often: **`pred_q05` is exactly 0.0 on 42.7% of v15 points rows**, 30.7% of attempts rows and 15.4%
of minutes rows.

For a non-negative quantity a zero floor is *correct*, not a bug. The narrower consequence worth
stating: on those rows `q05` carries no information and the interval is effectively one-sided.

---

## 5. What was checked and found clean

| check | result |
|---|---|
| quantile crossings (q05 ≤ q25 ≤ q50 ≤ q75 ≤ q95) | **0** — every row, both arms, all targets |
| point forecast outside its own [q05, q95] | **0** — every row |
| interval coverage, nominal 90% | 86.5–87.7% — mild under-coverage, inside the preregistered tolerance |
| duplicated prediction vectors outside the known region | largest cluster 70 rows / 11 players (points); nothing structural |
| ceiling / upper saturation | none on any target |
| near-constancy outside the known region | **none**, across 286 cells |

---

## 6. What is NOT a finding, and why

D6 flagged `fit_eligible == False` (352 rows) and `evaluation_tier == B_transaction_sensitivity`
(113 rows) with a nominal-90% interval covering 71.4% of realised minutes.

**Those cells contain only 14 scoreable rows.** A coverage estimated on 14 outcomes has
a standard error near 8 percentage points; 0.714 is 10 of 14. This is noise, and the brief's own
rule — a 20-row curiosity ranks below a 700-row region — applies to it. Recorded as **underpowered,
not established**, so a future screen with more scoreable rows in that tier can pick it up.

An earlier draft of this document described these cells as a defect found. That was wrong and the
correction is recorded in `FINDINGS.json` rather than quietly made.

---

## 7. Honest limits

- **The preregistration was amended after the data was inspected.** The trigger was a row-count
  mismatch alone — the two arms sit on different contracts, and binding both to contract v4 would
  have silently dropped 3,808 v15 rows (17.6% of its output). No defect statistic existed when the
  amendment was written; `run_log_s01_FAILED.txt` is retained as evidence of how far step 01 got.
  It corrected one input path and added six partitions; it dropped and relaxed nothing.
  **A reader who rejects the amendment can read the v14 arm alone, which it does not touch — every
  headline holds there.**
- **The baseline is tuned**, which flatters the routing gain. Tuning is walk-forward on strictly
  earlier exploration seasons; 2022 has no earlier season and uses an untuned default (k = 5) fixed
  in the prereg before any data was read. Worst-case-over-grid figures are published beside every
  selected one, and every headline gain survives the worst case.
- **This sweep tests the champion's OUTPUT.** A region degenerate in some way none of the six
  preregistered families describes would not be found by it.
- **2021 is excluded** as a known non-finding (degenerate by design, `n_train_rows = 0`,
  `model_was_fitted = false`, confirmed from both arms' fold receipts). **2025 and 2026 were never
  read.**
