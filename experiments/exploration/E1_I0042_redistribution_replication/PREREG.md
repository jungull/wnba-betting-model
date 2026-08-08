# E1_I0042 — REPLICATION SCREEN FOR THE MINUTES-REDISTRIBUTION TERM (component C / D116)

**Status: preregistration. Written and hashed before any cell in §3–§8 is evaluated.**

The result under test is the programme's only commercially relevant candidate:
**decision-stratum minutes +1.73% (ΔMAE +0.0776, p 0.006, n 1,051)**, published by E1_I0039 §5,
itself a re-measurement of D116/E1_I0034's redistribution term. It rests on **one** walk-forward
window. This screen exists to give it a second honest test **or to kill it**.

Killing it is an acceptable and expected outcome. No champion is fitted. No production change is
proposed or enacted. Nothing outside
`experiments/exploration/E1_I0042_redistribution_replication/` is written, staged or committed.

---

## s0. WHAT WAS DONE BEFORE THIS HASH

One structural probe, `scripts/s00_probe.py`, output at `out/s00.txt`. It printed **column names,
season coverage, row and team-game counts, and the finite/zero counts of `freed_minutes`,
`u_minutes`, `uz_minutes`, `z_minutes`, `n_rem`, `n_absent`**. It evaluated **no cell**, compared
**no arm against another**, and touched **no response variable in a difference**. It exists so that
the allowlists in §2 can be written out **explicitly by name** rather than discovered by matching.

The champion fold receipts for 2021, 2022, 2023 and 2024 were also read in full (§1). They are
metadata about the fitting procedure, not outcomes.

---

## s1. THE PARTITION, AND THE WINDOW CENSUS RULE

**Exploration is 2021–2024 only. 2025 and 2026 are a sealed confirmation holdout and are never
read.** A value-level guard (`assert_partition`) runs on every frame at every load and raises if a
sealed season value appears. The champion's `fold_receipt__2025.json` and `fold_receipt__2026.json`
exist on disk and are **deliberately not opened**; only the 2021–2024 receipts are read.

Manifests: `row` and `season` are usable, `artifact` is not; MISSING = UNVERIFIABLE and
UNVERIFIABLE is not a pass. C's absence indicator is **realised, not forecast**, because both
pre-game injury sources return `manifest_present: false`. **Every cell in this screen is therefore
an ORACLE-ON-ABSENCE CEILING** and is labelled `ORACLEABS`. Nothing here is an achievable live
increment.

### The admissibility rule for a scored season — fixed here, applied in §3

A season `S` may be **scored** if and only if **both** hold:

* **(R1) The champion's own fold for `S` is not degenerate.** Verified from
  `fold_receipt__S.json`: `degenerate == false` **and** `model_was_fitted == true` **and**
  `n_train_rows > 0`.
* **(R2) The redistribution overlay has at least one admissible strictly-prior season to fit on.**
  The overlay is a walk-forward regression of `y − champion` on the redistribution regressors; a
  season whose champion is a declared constant carries no usable residual, so a season failing
  (R1) may not enter an overlay training pool either.

A **clean window** is a maximal contiguous run of seasons all of which satisfy (R1) and (R2).

**This rule is not relaxed for any reason.** If it admits only one window, `WINDOWS.md` will say
so plainly and will state that as the finding. A season-level split of a single window will be
reported as a **split of one window, never as a second window**, and labelled as such in every
table it appears in.

---

## s2. FRAMES AND EXPLICIT ALLOWLISTS — no name-based column selection anywhere

Five findings in this programme died to substring matching. Every column set below is an explicit
tuple, length-asserted, and membership-checked at load.

**PRIMARY frame `U39`** — `E1_I0039_stacking/_fit.parquet`, read-only. This is the frame in which
the +1.73% was measured; using it makes the replication like-for-like.

**SECONDARY frame `REM`** — `E1_I0034_redistribution/_rem_frame.parquet`, read-only. D116's own
remaining-player row set, built by different code. Carried as a **construction** check, not as a
window.

`U39_KEEP` (24): `row_uid, season, game_id, team_id, player_id, game_date, appeared, minutes,
pts, min_hat, pts_hat, is_fallback, fallback_level, n_prior_games, base5_minutes, base5_pts,
nprior_minutes, tg, z_minutes, z_pts, established, freed_minutes, n_rem, DECISION`

`U39_C` (4): `u_minutes, uz_minutes, u_pts, uz_pts`

`U39_AB` (4): `depth_bucket, draft_bucket, e_full_minutes, e_full_pts`

`REM_KEEP` (18): `row_uid, season, game_id, team_id, player_id, minutes, pts, min_hat, pts_hat,
n_prior_games, base5_minutes, established, freed_minutes, n_rem, u_minutes, uz_minutes, z_minutes,
tg`

**Responses.** `minutes` and `pts`, and they are **NEVER compared to each other** (D101). Every
comparison holds identical response, identical row set, identical SST basis, identical weighting
and identical base on both sides.

---

## s3. THE DECISION STRATUM, REPORTED BEFORE ANY EFFECT SIZE

`DECISION := (n_prior_games >= 8) AND (base5_minutes >= 24)`, exactly as E1_I0039.

**The intersection table is printed and written to disk before any ΔMAE in this screen is
computed**, and it leads `VERDICT.md`. Required contents: |U|, |DECISION|, |C-treated|,
|C-treated ∩ DECISION|, and the same four counts **per scored season**. A pooled gain on rows
outside the stratum is not a commercial result and is not reported as one.

---

## s4. ANCHORS — reproduced on bytes before any new statistic

The run **halts** if any anchor fails. Tolerance `0.0` (exact) except where stated.

| id | anchor | source | want |
|---|---|---|---|
| A1 | 2021 champion fold `degenerate` | receipt | `true` |
| A2 | 2021 champion `model_was_fitted` | receipt | `false` |
| A3 | 2021 champion `n_train_rows` | receipt | `0` |
| A4 | 2022 champion `train_seasons` | receipt | `[2021]` |
| A5 | E1_I0034 P04 minutes, ≥25 stratum, n | REDISTRIBUTION.md §3 | `2475` |
| A6 | E1_I0034 P04 minutes, ≥25 stratum, MAE(M0) | stratification_by_freed.csv | `5.101386713527127` (tol 1e-9) |
| A7 | E1_I0034 P04 minutes, ≥25 stratum, ΔMAE | stratification_by_freed.csv | `0.09269264623364977` (tol 1e-9) |
| A8 | E1_I0034 P04 points, ≥25 stratum, ΔMAE | stratification_by_freed.csv | `-0.048450995372577264` (tol 1e-9) |
| A9 | E1_I0034 P03 minutes, ALL, ΔMAE | stratification_by_freed.csv | `0.02949664894847303` (tol 1e-9) |
| A10 | E1_I0039 universe \|U\| | ROW_OVERLAP.csv | `9022` |
| A11 | E1_I0039 \|DECISION\| | ROW_OVERLAP.csv | `3158` |
| A12 | E1_I0039 \|C ∩ DECISION\| | ROW_OVERLAP.csv | `1051` |
| A13 | E1_I0039 C decision-stratum-own-rows minutes ΔMAE | C_on_own_rows.csv | `0.07599108674339723` (tol 1e-9) |
| A14 | E1_I0039 ABC decision-stratum-own-rows minutes ΔMAE — **the +1.73%** | C_on_own_rows.csv | `0.07758861005075739` (tol 1e-9) |
| A15 | E1_I0039 C minutes `freed_0_to_25` ΔMAE | negative_and_threshold_strata.csv | `-0.023018530431078568` (tol 1e-9) |
| A16 | E1_I0039 C minutes `freed_ge_30` ΔMAE | negative_and_threshold_strata.csv | `0.144255239602443` (tol 1e-9) |

A5–A9 are recomputed from `REM` through this screen's own code. A10–A16 are recomputed from `U39`
through this screen's own code. Reproducing a published number by reading it out of a CSV is not
an anchor and is not counted as one.

---

## s5. THE ARMS, AND THE TWO INTERCEPT REGIMES

Let `ch` be the champion forecast, `y` the response, `S` a scored season, and the training pool for
`S` be the admissible seasons strictly before `S`.

* **BASE** `M0 = ch + b(S)` where `b(S)` is a walk-forward **intercept-only** fit of `y − ch`.
  An intercept is held in **both** arms of every comparison (E1_I0032's HIGH defect designed out).
* **SHARED-INTERCEPT C arm** `M1 = ch + a0(S) + a1(S)·u + a2(S)·uz`, a walk-forward fit of
  `y − ch` on `[1, u, uz]`. This is E1_I0034's and E1_I0039's construction, byte-compatible.
* **FROZEN-INTERCEPT C arm** `M1f = ch + b(S) + c1(S)·u + c2(S)·uz`, where `(c1, c2)` are a
  walk-forward fit of `y − ch − b(S)` on `[u, uz]` **with no intercept term**.

**Why the frozen arm is the honest one, and why E1_I0039's freeze was not a freeze.** E1_I0039's
`intercept_frozen_attribution.csv` set the arm equal to the base off the treated rows and to the
full shared-intercept arm on them. On the treated rows themselves that is the *unfrozen* number;
it removes off-row movement but leaves the recalibration inside the treated-row forecast. `M1f`
above is bit-identical to `M0` wherever `u = 0` **by construction**, so any measured effect must
live on treated rows. Both regimes are computed and **both are reported side by side**; the frozen
number is the one carried into `VERDICT.md`'s first three sentences.

**PREDICTION, fixed now.** If C's decision-stratum gain is genuine it should **survive** the
freeze. If it collapses toward zero, that is the finding and it leads the verdict.

**SECOND PREDICTION, fixed now.** Under `M1f` with the gate at 25 minutes, every row with
`freed < 25` has `u = 0` and is therefore **bit-identical to base**. E1_I0039 §4 reports
`freed_0_to_25` minutes at **−0.0230, p 0.0003, "actively harmful"**. If that number is the
treatment it must survive the freeze; if it is recalibration it must go to **exactly 0.0000**.
This screen states in advance that it expects **exactly 0.0000** and will report it either way.

---

## s6. THE THREE CLAIMS, AND HOW EACH IS TESTED

### Claim 1 — a ~30-minute threshold

**Tested on an UNGATED arm.** The gated-at-25 arm cannot locate a threshold: below 25 its
regressor is identically zero, so any "below-threshold" number it produces is recalibration, not
treatment. The threshold arm therefore applies `u` on **every** established row with `freed > 0`,
frozen intercept, and the effect is stratified by `freed_minutes` on a fine grid
`τ ∈ {0, 2.5, 5, …, 60}`.

**The threshold is reported as a measured interval, not a constant.** Estimator: the smallest τ at
which the frozen-arm decision-stratum ΔMAE on rows with `freed ≥ τ` becomes and stays positive.
Interval: **block bootstrap over team-games, 2,000 replicates, percentile 5th–95th**, written to
`THRESHOLD.csv` together with the per-τ block count. If the interval spans more than 20 minutes
the threshold is reported as **not localised**, and "~30 minutes" is reported as an artefact of a
five-bin stratification.

### Claim 2 — allocate evenly

Three allocations of the same freed volume, identical rows, identical response, identical base,
frozen intercept:

* **EVEN** — regressor `[u]`, `u = freed / n_rem`
* **TILTED** — regressors `[u, u·z]`, the published specification
* **PROPORTIONAL** — regressor `[u_prop]`, `u_prop_i = freed · base5_i / Σ_rem base5`

Even is upheld only if neither TILTED nor PROPORTIONAL beats it by more than the cell's
injection-verified floor. A difference inside the floor is reported as **not established**, never
as "even wins".

### Claim 3 — minutes yes, points no

The identical arm, rows and base, run on `pts`. D101 forbids comparing the minutes number to the
points number; each is compared only to its own base. Both are reported with the frozen-intercept
number beside the shared one, and the vacuous split (`freed = 0`) is reported for both, because
E1_I0039 found C's *points* gain living entirely on rows where its own term is zero.

---

## s7. NULLS, POWER, AND CONTROLS

* **Null** — paired **sign-flip blocked at TEAM-GAME**, 20,000 draws, on the per-row loss
  difference. The redistribution term is a **team-game-level** property, so the block matches the
  level the candidate varies at (D115). Draws for every primary cell are written to
  `nulls/*.npz`.
* **The `null_mean > observed` diagnostic is NOT quoted as clearing anything.** On a sign-flip
  null the draws are ± fixed block sums, so `E[draws] = 0` exactly and the diagnostic is
  **structurally vacuous**. It is recorded and explicitly labelled vacuous.
* **Six-block hard floor, binding.** `n_blocks` is reported for **every** cell. A cell with
  `n_blocks < 6` is arithmetically incapable of rejecting (`p_min = 2^(1−nb)`; measured Type-I
  exactly 0.0000 at nb = 3,4,5) and is reported as **UNDECIDABLE**, never as a null.
* **`t_crit` vs `√nb`.** For every cell, `p_min = 2^(1−nb)` and the sign-flip statistic's maximum
  attainable `|t| = √nb` are computed and compared to the α actually used, **before** any
  family-wise correction is applied. A correction that pushes the required `t` past `√nb` makes
  the cell undetectable at any effect size and is **not applied**; the cell is reported
  uncorrected with that fact stated.
* **Injection is COMPONENT-WISE, not shuffled residuals.** A known redistribution effect is
  planted **into the response through the candidate's own functional form**
  (`y' = y + κ·u` on treated rows) and recovered through the identical walk-forward →
  sign-flip path. Shuffled-residual injection is not used: E1_I0034 measured it attenuating
  (0.024 → −0.001 at 2 null sd). Constant loss subtraction is not used: E1_I0039 recorded it as
  DEF-3 (zero dispersion, floor 5× below analytic).
* **Type-I** is measured on synthetic no-effect datasets (block-resampled residuals about the base,
  team-game blocks), ≥400 per primary cell, target 0.05.
* **Vacuous control (E1_I0034's trap).** Every headline is accompanied by its effect on the
  `freed = 0` rows, where C's term is identically zero. A headline whose gain lives there is
  reported as vacuous.
* **No-op placebo.** The identity transform must return ΔMAE exactly `0.000e+00`, and the
  transform is asserted to be the identity so the check is not vacuous.
* **Random-target control.** C's treatment reassigned to a same-size random set of team-games.

---

## s8. SPECIFICATION AND ORDER SENSITIVITY

E1_I0039 found application order moving the stacked result by 19–22% of its decision-stratum
number. C alone should be insensitive; this is **verified, not assumed**. The lattice, all on
identical rows and base:

1. C applied to the raw champion vs C applied to the A/B-substituted forecast (order)
2. gate at 25 vs gate at 30 vs ungated
3. `[u]` vs `[u, uz]` (specification)
4. shared vs frozen intercept
5. `U39` frame vs `REM` frame (construction)
6. pooled window vs each scored season alone (the split of §s1)

The **full spread** across this lattice is reported against the headline. If the spread exceeds
the headline, the headline is reported as **specification-dependent**.

---

## s9. VERDICT GRAMMAR — fixed before the numbers exist

* **REPLICATED** — the decision-stratum minutes effect is positive, exceeds its
  injection-verified floor, and does so on **both** scored seasons independently, with the frozen
  intercept.
* **PARTIALLY REPLICATED** — positive and above floor pooled and on one season, not the other.
* **NOT REPLICATED** — fails the floor pooled, or reverses sign on either season.
* **KILLED** — collapses to or below zero under the frozen intercept, or is shown to live on rows
  the treatment does not touch.
* **UNDECIDABLE** — fewer than six blocks, or the floor exceeds the effect by construction.

**The result that most weakens the conclusion is reported in the same document as the conclusion**,
in a section headed as such, not in a footnote.

---

## s10. DELIVERABLES

`PREREG.md` + `PREREG.sha256` · `WINDOWS.md` · `VERDICT.md` · `THRESHOLD.csv` · `FINDINGS.json` ·
`NOTES.md` · `DEFECTS.md` · `nulls/*.npz` · all CSVs named above · `out/*.txt` run logs.

**Cells fixed by this preregistration: 14** (decision-stratum intersection; C frozen and shared on
own decision rows, minutes and points; per-season split, minutes and points; threshold interval;
even vs tilted vs proportional; vacuous split; order; gate; frame; power floor). Anything added
after the hash is labelled **ADDED AFTER THE HASH** with the direction it moved the headline.
