# How many clean windows does the partition allow? **Exactly one.**

**E1_I0042.** Preregistration hash
`33135817779e66637ac68e3da2baa590dcb2be224f34c8a3332a159bb17c68d1`, 15,833 bytes.
Evidence: `WINDOW_CENSUS.csv`, `_s01.json`, `out/s01.txt`.

**This is the finding, and it is worth more than a strained second test would have been.** No
window was manufactured. No criterion was relaxed to produce one.

---

## 1. The rule, fixed in the preregistration before the receipts were opened

A season `S` may be **scored** only if both hold:

* **(R1)** the champion's own fold for `S` is not degenerate —
  `degenerate == false` **and** `model_was_fitted == true` **and** `n_train_rows > 0`;
* **(R2)** the redistribution overlay has at least one **admissible** strictly-prior season to fit
  on — because the overlay regresses `y − champion` and a season whose champion is a declared
  constant carries no usable residual.

A **clean window** is a maximal contiguous run of seasons satisfying both.

## 2. The census

| scored season | R1 champion not degenerate | overlay training pool | R2 | scorable |
|---|---|---|---|---|
| 2021 | **FAIL** | — | fail | **no** |
| 2022 | pass | **empty** | **FAIL** | **no** |
| 2023 | pass | {2022} | pass | **yes** |
| 2024 | pass | {2022, 2023} | pass | **yes** |

**Maximal contiguous clean windows: 1 → (2023, 2024).**

## 3. The 2021 degeneracy, verified first-hand and not inherited

Both prior screens assert it. I read `fold_receipt__2021.json` myself. It says, in its own fields:

* `degenerate: true`
* `model_was_fitted: false`
* `n_train_rows: 0`, `train_seasons: []`
* `cold_start_declared_constant_only: true`
* and the decisive one — the minutes target's `fallback_levels` is `{"4": 4997}`. **Every one of
  the 4,997 minutes forecasts in 2021 is a level-4 constant fallback.** There is no model there
  to have a residual about.

Five anchors, all exact. The inherited claim is correct.

## 4. Why 2022 cannot be forced, and what happens when it is

2022 fails **(R2)**, not (R1). Its champion fold *is* fitted — but on
`train_seasons: [2021]` **only**. Scoring 2022 means fitting the redistribution overlay on
residuals about a constant. E1_I0039 did exactly that and reported component C at **−12.56%** on
decision-stratum minutes with cross-window sign agreement of **0.64 of 28 cells**. That is not a
disagreeing window; it is a broken one. **The preregistration forbids relaxing (R2) and it was not
relaxed.**

## 5. The observation that weakens even the surviving window

**2023's overlay training pool is the single season 2022, and 2022's own champion was trained on
nothing but the degenerate 2021 fold.** The degeneracy is not quarantined — it is one step removed
from the 2023 fold and two steps from the 2024 fold. This is a real limitation on the only window
the programme has, and it goes some way to explaining why the 2023 fold is the weaker of the two
(§6).

## 6. What *is* available: a split of the one window, and it is called that everywhere

The one clean window contains **two disjoint scored folds**, each with its own admissible training
pool:

| fold | rows in U | team-games | decision stratum | C-treated | **C-treated ∩ decision** | blocks |
|---|---:|---:|---:|---:|---:|---:|
| 2023 | 4,520 | 480 | 1,591 | 1,452 | **613** | 151 |
| 2024 | 4,502 | 480 | 1,567 | 1,023 | **438** | 113 |
| pooled | 9,022 | 960 | 3,158 | 2,475 | **1,051** | 264 |

Scoring them separately is the strongest honest second test the partition allows, and this screen
ran it. **It is a split, not a second window**, and every table in this screen labels it
`PRIMARY_WINDOW_SPLIT`: 2024's overlay training pool *contains* 2023, so the two folds share
fitted information in one direction. A split-half cannot do what a genuinely independent window
would do.

## 7. What this means for the programme

The programme's replication capacity on this candidate is **one window and one split**. Exploration
runs 2021–2024; one of those four seasons is a constant, a second is unusable because it can only
train on the first, and the remaining two are the whole evidence base for the only commercially
relevant result the programme has. **Any future claim to have "replicated" this result on
exploration data is, on the current partition, either this split or a relaxed criterion.**

The confirmation holdout is 2025–2026. It was **not opened**. Both sealed fold receipts are present
on disk and were listed by name and explicitly skipped (`out/s01.txt`).
