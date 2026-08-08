# E1_I0022 — OPTIMAL SIMPLE ESTIMATOR

**Question this screen exists to answer.** Every screen in this programme has held the skill
reference FIXED and hunted for features to add on top of it. Nobody has optimised the reference
itself. D090 measured the same availability forecast at **+46.4%** against a simple prior rate and
**+7.1%** against a rich lookup — a factor of six from the comparison alone. D093 found that raising
a realised-minutes floor flipped which estimator won. Reference dependence is the top-ranked
explanation for this programme's persistent nulls (D091, D093).

So: **build the best strictly-prior-games-only estimator we can, tune it honestly, and find out
whether the champion actually beats it.**

---

## 1. Reproduction of the anchor (STEP 1)

D081's per-component skill table reproduced **EXACTLY**, all nine numbers, with this screen's own
metric code rather than by importing D081's `psd_base` or the shared kit.

| component | reference | n | model MAE | ref MAE | skill | published | **abs delta** |
|---|---|---|---|---|---|---|---|
| minutes | `ref_minutes` | 13879 | 5.079671 | 5.266907 | +3.5549460% | +3.554946% | **0.000e+00** |
| fga | `ref_fga` | 13879 | 2.637570 | 2.640611 | +0.1151613% | +0.115161% | **0.000e+00** |
| pts | `ref_pts` | 13879 | 4.190920 | 4.181629 | −0.2221832% | −0.222183% | **0.000e+00** |
| pts_per_min | `refA_ppm` | 13879 | 0.181743 | 0.182765 | +0.5590774% | +0.559% | **0.000e+00** |
| pts_per_min | `refB_ppm` | 13879 | 0.181743 | 0.183502 | +0.9588508% | +0.959% | **0.000e+00** |
| pts_per_fga | `refA_ppf` | 12976 | 0.506578 | 0.517586 | +2.1267713% | +2.127% | **0.000e+00** |
| pts_per_fga | `refB_ppf` | 12976 | 0.506578 | 0.511817 | +1.0236525% | +1.024% | **0.000e+00** |
| fga_per_min | `refA_fpm` | 13879 | 0.110338 | 0.111843 | +1.3453785% | — | **0.000e+00** |
| fga_per_min | `refB_fpm` | 13879 | 0.110338 | 0.111111 | +0.6953266% | — | **0.000e+00** |

Row counts match to the row (13,879 / 12,976). An independent rebuild of D076's level references
from the raw outcomes matched the frozen columns at max |diff| ≤ 6.75e-14. The leak probe
reproduced D081's published correlations to four decimals: the deliberately-retrospective
full-season mean correlates **+0.9480** with the player's strictly-future mean points, the
prior-only reference **+0.8453**.

---

## 2. TIME-WINDOW TABLE

The retrospective-baseline trap has **six** recorded instances in this programme, one of which
entered through the inference machinery rather than the features. Every object below is listed with
what it may see.

### 2a. Estimator ingredients

| object | grouping | window it may see | prior-only? |
|---|---|---|---|
| player history sums `S_num`, `S_den`, `S_w` | (season, player_id) | games at a **strictly earlier position** in the date-sorted block. The block's admissible games are compacted and prefix arrays are indexed at `h` = count of admissible games strictly before the row, **never `h+1`** | **YES** |
| realised-minutes floor on the history | (season, player_id) | applied to the **prior** game's realised minutes only; never to the row being scored, so all cells are scored on identical rows | **YES** |
| EWMA / SMA / expanding weights | (season, player_id) | functions of position within the prior history only | **YES** |
| shrink target `league` | (season) | same-season games on **strictly earlier DATES** (date-blocked, not row-blocked — a `shift(1)` inside a date-sorted season would let a row see other games played the *same day*, which are not available pre-game) → previous season's league value → GRAND | **YES** except GRAND, see §6 |
| shrink target `prior_season` | (season, player_id) | the player's **whole previous season**. Seasons are calendar-disjoint in this frame (2022 ends 2022-09-18, 2023 starts 2023-05-21; 2023 ends 2023-10-18, 2024 starts 2024-05-16), asserted in `assert_season_disjoint` | **YES** |
| shrink target `role` | (season, prior-season MPG tercile) | same-season strictly-earlier dates within the bucket. **Tercile cutpoints come from the previous season's distribution only** | **YES** |
| role bucket assignment | (player) | previous season's minutes per game; `-1` if no previous season in the frame | **YES** |
| composite points estimate | — | product of the same cell's minutes and points-per-minute estimates, both prior-only | **YES** |

### 2b. Tuning

| object | window it may see | prior-only? |
|---|---|---|
| split A hyperparameters | season **2022** only | **YES** relative to the 2023 rows they score |
| split B hyperparameters | seasons **2022 + 2023** | **YES** relative to the 2024 rows they score |
| depth-adaptive cells | the tuning rows **of that tier only**, same split structure | **YES** |
| in-sample counterfactual cell | the **evaluation rows themselves** | **NO — deliberately retrospective.** Exists only to publish the optimism gap. Never a headline. |

### 2c. Evaluation

| object | window | prior-only? |
|---|---|---|
| walk-forward evaluation rows | 2023 ∪ 2024, n = 9,517 | — |
| champion forecasts | frozen `*__pred_point` columns from D076's OOF walk-forward; **nothing refitted** | inherited |
| decision stratum selector (`pl_games_prior ≥ 8`, `pl_min_mean5 ≥ 24`) | strictly prior appearances | **YES** |
| prior-appearance tiers | `pl_games_prior`, strictly prior | **YES** |
| fallback split (`*__is_fallback`) | emitted by the champion's own pre-game inference | **YES** (but the split was chosen post hoc — §6) |
| slice variables `pl_min_sd5`, `pl_dnp_frac5`, `pl_rest_days` | trailing-5 / prior only | **YES** |

### 2d. Partition

Seasons present: 2022, 2023, 2024 only. Enforced by `assert_partition`, which parses **column
values** (season integers, date years) and never scans file text or column names. The 2021 fold is
degenerate (`n_train_rows = 0`) and is absent from the frozen frame. **No 2025 or 2026 row was
read, joined, plotted or described.**

---

## 3. Preregistration

`ESTIMATOR_GRID.md` was written and hashed **before any skill number for any grid cell was
computed**. The only numbers computed earlier are the STEP 1 reproduction of someone else's
published table, and row/column counts.

```
GRID_SHA256 = 5ddbd754cc3f0c9eb9b7e29f8a6e77b37e0b078b647785629ad42167ac6cf4db
SPEC_SHA256 = df9ef234eba9b1069d0c38d7c02cafa358c18a3c6311d4616f2fb563bbb40300
N_CELLS     = 15048
ADDED after preregistration   = 0
DROPPED after preregistration = 0
```

`s03_sweep.py` recomputes the enumeration hash and **refuses to run** unless it matches.
9 target-mode pairs × 19 memory settings × 22 shrinkage settings × 4 history floors = 15,048.

---

## 4. Tuning protocol (stated explicitly, as required)

| split | hyperparameters selected on | scored on |
|---|---|---|
| A | season 2022 (4,362 rows) | season 2023 (4,748 rows) |
| B | seasons 2022 + 2023 (9,110 rows) | season 2024 (4,769 rows) |

**Walk-forward evaluation rows = 2023 ∪ 2024, n = 9,517.** Selection criterion is the lowest MAE on
the *tuning* rows, computed by the identical code path used on the evaluation rows. **No evaluation
number is consulted by any selection.** The whole 15,048-cell surface is computed in `s03` with no
selection in it at all, so selection in `s04` cannot be contaminated by having looked.

### In-sample versus walk-forward gap

| target | walk-forward MAE | in-sample-selected MAE | optimism gap |
|---|---|---|---|
| points | 4.147585 | 4.115465 | **+0.780%** |
| minutes | 4.884528 | 4.882011 | **+0.052%** |
| FGA | 2.558836 | 2.538488 | **+0.802%** |
| points-per-minute | 0.180293 | 0.179398 | **+0.499%** |

D093 found per-player models with in-sample R² of +0.04 to +0.18 whose walk-forward R² was
**negative**. That failure mode is not present here: the gap is 0.05–0.80%. This matters for the
verdict — **the champion's deficit (−1.93% to −4.41%) is 2.4× to 85× the entire tuning optimism**,
so the answer survives even if the estimator had been tuned with full hindsight.

The selected cell was **identical** across splits A and B for minutes; it differed for points
(half-life 5→8, league→prior-season shrink), FGA (half-life 3→5) and ppm (expanding→half-life 40).
The estimator is therefore genuinely re-tuned per split, not a fixed choice dressed as one.

---

## 5. Controls and traps honoured

**Autocorrelation trap (D093).** Prior-history estimators are autocorrelated by construction.
`s05` runs a **within-player CYCLIC SHIFT** of the champion's forecast series (construction credited
to `E1_I0021_heterogeneity_diagnostic/hd_base.py::cyclic_shift_within_groups`, read-only, not
imported) and, for comparison, the plain within-player shuffle D093 warned about. Measured null SDs:

| target | cyclic-shift null SD | plain-shuffle null SD | shuffle is narrower by |
|---|---|---|---|
| points | 6.049e-03 | 4.499e-03 | 1.34× |
| minutes | 1.448e-02 | 6.770e-03 | **2.14×** |
| FGA | 8.265e-03 | 4.811e-03 | 1.72× |
| ppm | 3.886e-03 | 3.174e-03 | 1.22× |

D093's warning reproduces cleanly: the plain shuffle null is too narrow here too, by up to 2.14×.

**Vacuous-control trap (D093).** D093 found a "control" that relabelled a player key and refit
per-player coefficients was a literal no-op at measured sd 5.2e-17. Every control here is checked
for a nonzero measured SD **before** being read as evidence, and `s05` asserts it: the cyclic shift
moves the statistic by SD 3.9e-03 to 1.4e-02, not 5.2e-17.

**Paired inference.** (season, player_id) **block sign-flip** on the paired absolute-error
difference `|e_champion| − |e_estimator|` on the same row, 4,000 draws. Never row-level: flipping
per row would treat 9,517 correlated rows as independent.

**Nothing was fitted on the champion.** Its stored forecasts are scored only. Fitting simple
estimators is authorised by D091.

**Row-filter robustness (D093's own floor).** D093's minutes floor filtered the rows being *scored*;
this grid's floor filters the *history*. Both were run. The champion loses at **every**
evaluation-row minutes floor from 0 to 24 minutes, on all four targets (`eval_row_floor_robustness.csv`).

---

## 6. WHERE I COULD HAVE CHEATED — full disclosure

1. **The GRAND fallback touches the whole frame.** The shrinkage-target chain ends in a whole-frame
   value. It fires on **56 rows, all in 2022**, being the rows on the opening date of 2022 that have
   neither a strictly-earlier same-season game nor a predecessor season in the frame. 2023 and 2024
   opening-date rows (79 rows) fall back to the previous season instead, which is calendar-disjoint
   and strictly prior. **No walk-forward evaluation row ever reaches GRAND.** Worst case it
   contaminated 56 of 4,362 split-A tuning rows (1.28%).
   *This was found because the assertion in `s03_sweep.py` FIRED on a first draft that asserted the
   wrong claim (that no row lacked same-season league history). The claim was wrong; 135 rows lack
   it. The corrected assertion is live in the shipped script.*
2. **The fallback/modelled split in `s06` is POST HOC.** It was chosen after seeing the tier table.
   Nothing was re-selected on it and no hyperparameter depends on it, and the switch variable is the
   champion's own pre-game flag so the hybrid is implementable — but `hybrid_postocc.csv` must be
   read as descriptive, not as a validated result.
3. **No hyperparameter was chosen after seeing an evaluation number.** The grid was hashed before
   any cell's skill existed; `s03` computes the surface with no selection; `s04` selects only on
   tuning-row MAE. The in-sample selection is published **solely** as the optimism gap.
4. **The conditional slices in `s05` are not multiplicity-corrected.** The slice list was written
   before the numbers, but individual slice p-values should be read as descriptive.
5. **Points-per-minute is scored on the ratio scale**, so its skill numbers are not commensurable
   with the level targets'.
6. **Small block count.** 236 players, 475 player-seasons. Tier-0 (n = 47) numbers are reported but
   should not be leaned on.
7. **The shared screen kit was not used and not read** — another agent is editing it. Every
   primitive (MAE, R², partition assertion, block sign-flip, cyclic shift) is reimplemented locally
   in `ose_base.py`. This is a deviation from five previous screens' practice and means these
   numbers do not share a code path with them; the exact reproduction in STEP 1 is the evidence that
   the local implementations agree with the kit's.

---

## 7. The estimator surface — what actually won

Ranked on tuning rows (2022+2023) only. Full surface in `estimator_surface.csv` (15,048 rows).

### FORM
EWMA beats SMA beats expanding, for **all four targets**. Best-in-class tuning MAE for points:
EWMA 4.10855 < SMA 4.12853 < expanding 4.13359. Minutes-weighting the history **hurts every level
target** (points 4.10855 → 4.30762; minutes 4.87032 → 5.11527; FGA 2.56438 → 2.70366). For points
the **composite** estimate (minutes estimate × points-per-minute estimate) narrowly beats the direct
points estimate, 4.10855 vs 4.11323 — D081's decomposition is worth something, but only just.

### MEMORY — the optimum differs by a factor of 20 across targets
| target | best memory | reading |
|---|---|---|
| minutes | **EWMA half-life 2 games** | role changes fast; only the last handful of games matter |
| FGA | EWMA half-life 5 games | |
| points | EWMA half-life 8 games | |
| points-per-minute | **EWMA half-life 40 games** (≈ expanding) | true shooting talent barely moves |

The SMA profile is U-shaped everywhere: for points, window 1 is 4.63074 and window 15 is 4.12853,
recovering to 4.13370 at window 30. A single half-life across the three quantities is the wrong
object.

### SHRINKAGE — weak, and never toward the league
Best shrink target, every quantity: **the player's own prior season**. The league mean was the
*worst* of the three targets for every quantity. Strength: k = 0.5 prior-games-equivalent for points
and FGA, k = 2 for ppm, and **k = 0 (none) for minutes** — shrinkage strictly hurts minutes. At
k = 32 the points estimator degrades to 4.76492.

### HISTORY MINUTES FLOOR — floor 0 wins, monotonically
Points tuning MAE at floors 0 / 5 / 10 / 15 = 4.10855 / 4.20921 / 4.37905 / 4.61659. Every positive
floor degrades every target. **Discarding low-minute prior games throws away more information than
it removes noise.** (This is not in tension with D093, which floored the rows being *scored*.)

### RATIO-OF-PRIOR-SUMS vs MEAN-OF-PRIOR-RATIOS — does not flip here
| history floor | mean-of-prior-ratios | ratio-of-prior-sums | winner |
|---|---|---|---|
| 0 | **0.180073** | 0.181304 | mean-of-prior-ratios |
| 5 | **0.181246** | 0.182425 | mean-of-prior-ratios |
| 10 | **0.182368** | 0.183982 | mean-of-prior-ratios |
| 15 | **0.183314** | 0.185672 | mean-of-prior-ratios |

D093 found the ordering flipped under its floor. It does **not** flip under a history floor — and
the margin *widens* with the floor. Because it was carried as a dimension rather than a choice, this
is a measurement rather than an assumption.

### DEPTH ADAPTATION — the optimum does vary, the payoff does not
The selected cell differs sharply by tier. Minutes picks EWMA half-life 12 **with** role shrinkage
at 1–2 priors and half-life 2 **unshrunk** at 25+. Points-per-minute picks a **1-game** window
heavily shrunk at 1–2 priors and a **30-game** window at 25+. But the walk-forward payoff from
exploiting that is −0.061% (points), −0.185% (minutes), −0.208% (FGA) — real but tiny — and
**+0.074% (a LOSS) for ppm**. One global setting is very nearly good enough; the depth-dependence
is real and not worth exploiting at this sample size.

---

## 8. The decisive comparison

`skill = 1 − MAE_champion / MAE_best_tuned_simple`, identical walk-forward rows, n = 9,517.
Positive = the champion is better. Full table in `champion_vs_best.csv`.

| target | pooled | decision stratum (n=3549) | **modelled rows (n=8819)** | fallback rows (n=698) |
|---|---|---|---|---|
| points | **−1.928%** (p=0.0002) | −0.576% (p=0.032) | **+1.065% (p=0.0002)** | −35.21% (p=0.0002) |
| minutes | **−4.411%** (p=0.0002) | −0.051% (p=0.663) | +0.029% (p=0.774) | −40.58% (p=0.0002) |
| FGA | **−3.132%** (p=0.0002) | −0.138% (p=0.686) | **+0.882% (p=0.0012)** | −42.89% (p=0.0002) |
| ppm | **−1.331%** (p=0.0002) | −0.583% (p=0.0027) | −0.392% (p=0.072) | −11.75% (p=0.0002) |

### How much of this is the reference?
Same champion forecasts, same rows, only the reference changes:

| target | champion vs D081's frozen reference | champion vs best tuned simple | **swing** |
|---|---|---|---|
| minutes | **+3.714%** | **−4.411%** | **8.12 points** |
| FGA | +0.002% | −3.132% | 3.13 points |
| ppm | +0.991% | −1.331% | 2.32 points |
| points | −0.567% | −1.928% | 1.36 points |

The best tuned simple estimator beats D081's frozen reference by +1.34% (points), **+7.78%
(minutes)**, +3.04% (FGA), +2.29% (ppm). **D090's factor-of-six phenomenon reproduces on four new
targets.** The programme's headline minutes number was measured against a reference that a
two-game-half-life EWMA beats by 7.78%.

R² on walk-forward rows (no refit, D069 denominator): points 0.4833 champion / **0.5118 estimator** /
0.4919 D081 ref; minutes 0.6312 / **0.6629** / 0.6093; FGA 0.6077 / **0.6366** / 0.6109;
ppm 0.1491 / **0.1804** / 0.1346. The estimator wins on R² too, so this is not an MAE artefact.

---

## 9. Where the advantage lives

**The pooled number is a near-cancellation — exactly the failure D081 warned about.** For points the
pooled −1.93% is 610 rows at −38.06% cancelling 8,860 rows at +0.92%. The 1–2-prior tier alone
contributes **+139.5%** of the pooled excess error for points and **+92.4%** for minutes.

**The single dominant split is the champion's own `*__is_fallback` flag.** 698 of 9,517 walk-forward
rows (7.33%), fallback levels 2 (632 rows) and 3 (66 rows). On those rows the champion emits
**exactly two distinct point values across all 698 rows** — points SD 0.0156, minutes SD 0.0474, FGA
SD 0.0177, against SD 6.27 / 9.70 / 4.72 on modelled rows. It is a literal constant. This extends
D092, which found a constant below 3 appearances: **the constant region *is* the fallback region** —
all 657 rows with <3 priors, plus 41 rows in the 3–7 tier.

**Champion wins:** points on modelled rows (+1.07%) and in every tier with ≥3 priors (+0.54% to
+1.32%, pooled +0.92%, p=0.0012); FGA on modelled rows (+0.88%) and at 15–24 priors (+1.82%,
p=0.0007) and 25+ (+0.77%, p=0.047). It wins *more* on low-minute players — points +4.36% in the
bottom trailing-5-minutes quartile versus −1.08% in the top quartile — which is the opposite of
where the money is.

**Champion loses:** every fallback row catastrophically; **minutes essentially everywhere** (its
best tier result is +0.03%, p=0.86 — it has no minutes skill the EWMA does not have); ppm in every
tier except a dead heat at 15–24 priors; short rest (points −8.64% at 1–2 rest days) and long
layoffs (−2.81% at 3+ days).

**Post hoc, declared as such:** routing the fallback rows to the tuned estimator and keeping the
champion elsewhere gives points MAE 4.107 (+2.85% on the champion, +0.98% on the estimator alone),
minutes 4.883, FGA 2.538 (+3.81% / +0.80%). Descriptive only — the split was chosen after seeing the
tier table.

---

## 10. Files

| file | what |
|---|---|
| `ANSWER.md` | the plain-language answer to the user's question |
| `FINDINGS.json` | machine-readable everything |
| `ESTIMATOR_GRID.md` | the preregistration + hash |
| `estimator_surface.csv` | all 15,048 cells × tune/eval/tier MAEs and skills |
| `champion_vs_best.csv` | the decisive comparison, every slice |
| `selection_and_optimism.csv` | selected cells + in-sample-vs-walk-forward gap |
| `depth_adaptive_selection.csv` | per-tier cells and the payoff from adapting |
| `paired_inference.csv` | block sign-flip p-values |
| `cyclic_shift_control.csv` | the D093 control, with measured SDs |
| `eval_row_floor_robustness.csv` | D093-style row filter |
| `ros_vs_mor_by_floor.csv` | the flip that did not happen |
| `where_the_advantage_lives.csv`, `pooled_decomposition.csv`, `fallback_by_tier.csv`, `fallback_split.csv`, `hybrid_postocc.csv`, `r2_walkforward.csv`, `reproduction.csv` | characterisation |
| `ose_base.py`, `s00`–`s07` | scripts |
| `run_log.txt`, `run_log_s0*.txt` | console output |
