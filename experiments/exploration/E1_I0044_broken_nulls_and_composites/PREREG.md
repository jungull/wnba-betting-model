# PREREG — E1_I0044, the 73 broken nulls and the programme-wide composite sweep

Screen `E1_I0044_broken_nulls_and_composites`. Two debts, both left by completed audits:
`E1_I0041_tstat_family_audit` (73 cells whose permutation null does not function) and
`E1_I0040_audit_extension` (the composite-candidate failure mode, never swept for).

**Partition: 2021–2024 exploration only. 2025/26 is a sealed holdout and is never opened.**
Every frame read in this screen asserts `season <= 2024` and `max(gdate) < 2025-01-01` before use.

---

## 0. What is already fixed before this document was written

Sections 1–3 below quote numbers that were produced by three read-only steps run *before*
preregistration: `s00_anchors.py` (anchor reproduction), `s01_probe_broken.py` (file structure),
`s02_diagnose.py` (exact reconstruction of `E0_I0014`'s screen) and `s03_mechanism.py` (mechanism
attribution). They are descriptive confirmations of what is on disk and what prior screens
published. Quoting them here makes it impossible to back-fit the predictions in §4.

### Anchors reproduced BEFORE any new statistic (`run_log_s00.txt`, `run_log_s02.txt`)

| anchor | prior screen's value | reproduced here |
|---|---|---|
| D103 `out/retrospective_power.csv` keyed `(screen, decision, family_size_K, cell)`, worst null arm | 1,349 cells / 760 blind / 0.5633802816901409 | **1,349 / 760 / 0.5633802816901409**, exact to 16 digits |
| `E1_I0041` `t_statistic` family size | 666 | **666** |
| ... degenerate (`mean|t|/sd|t| > 5`) | 67 | **67** |
| ... `sd` exactly 0 | 6 | **6** |
| ... total broken | 73 | **73** (overlap 0) |
| ... recorded ADEQUATELY POWERED by D103 | 35 | **35** (all 35 in `E0_I0014`; 0 in `E0_I0019`) |
| `E0_I0014` `vsb`, 58 candidates, recomputed from `analysis_frame.parquet` vs `permutation_nulls.npz` | — | **max abs diff 0.000e+00** |
| `E0_I0014` `t_classical`, 348 cells, vs `screen_results.csv` | — | **max abs 3.553e-15, max relative 3.939e-15, 276 of 348 bitwise identical** (CSV text round-trip) |
| `E0_I0014` `null_correct_sd`, 348 cells, recomputed from the saved draws | — | **max abs diff 2.220e-16** (published uses `ddof=1`) |
| `E0_I0014` `p_correct_level`, 348 cells | — | **0 mismatches of 348** |

### The mechanism, measured (`run_log_s03.txt`)

Three mechanisms, and they are disjoint. **All 72 of the E0_I0014 broken cells have a
1,000-draw null with 1,000 distinct values or 1 — the permutation set is never "trivially
small" in the sense of too few arrangements.** What is broken is either the *statistic* or the
*location* of the null.

**M-VOID (18 cells, 3 candidates).** `pts__pred_sd`, `minutes__pred_sd`, `fga__pred_sd` take
**exactly one distinct value per season** in all three seasons. After the screen's own base
(season fixed effects) the design column has `sxx` of 0.000e+00 / 9.09e-27 / 4.59e-26 against
1.3876e+04 for every other candidate — a gap of thirty orders of magnitude. The observed `t` is
`NaN` (fga) or ~1e-13 (pts, minutes). Their nulls are correspondingly 1 unique value, and
`fga__pred_sd`'s six draws are all exactly 0.0 — the value `s04_screen.py:215` writes when a
permuted `t` is non-finite. These are the six cells for which D103's `sd = 0` returns a detection
floor of exactly 0.0.

**M-WITHIN (52 cells).** `within_block_index` shuffles values *inside* each (season, player)
block, so the block mean survives: measured max change in a block mean over all 475 blocks and
all 58 candidates is **1.776e-15**. For every one of these cells the block-mean component alone
carries a larger `|t|` than the whole candidate does — e.g. `pl_pts_sd5|pts_absres`
`t_full = 25.60`, `t_blockmean_only = 44.04`, `t_withindev_only = −2.47`. The component the null
cannot touch is the component that carries the association, so the null cloud sits on top of the
alternative.

**M-BETWEEN (2 cells).** `block_index` maps a donor block's rows onto the receiving block **in
chronological position order** (`don[arange(len(b)) % len(don)]`), so the within-block ordinal
profile survives the reassignment. Measured correlation between the real and permuted
within-block deviation: 0.140 for `pts__pred_width`, and 0.48–0.64 for the monotone counters
`pl_games_prior`, `pl_minutes_prior`, `pts__n_prior_games`, `pts__is_fallback`,
`pts__fallback_level` — for which *both* of `E0_I0014`'s schemes retain signal.

### The statistic-blindness test, run BEFORE any condemnation (`_STATISTIC_BLINDNESS.csv`)

`E1_I0040` established that a null cannot be blind to something the statistic itself cannot see,
and proved it by multiplying the suspect component by ten and then deleting it (max change
4.441e-16). Applied here to all 72 E0_I0014 broken cells: **minimum change in `t` over every
manipulation is 2.303861e-02 and the number of cells whose statistic cannot see the blind
component is 0 of 72.** `E0_I0014`'s statistic is a pooled `t` on the raw candidate, so the
escape hatch that saved `E1_I0021` does not apply here. This is a measured negative, not an
assumption, and it is why the condemnation below is allowed to proceed.

---

## 1. The re-measurement: a null that functions

**Proposed instrument — the COMPOSED null.** One gather index per draw, shared across all 58
candidates so a max-|t| family-wise statistic remains valid, built as

```
idx  = block_index(groups, n, rng)          # whole blocks reassigned within season, as E0_I0014
idx[b] = rng.permutation(idx[b])            # THEN positions randomised inside the receiving block
```

It destroys the block-mean alignment (M-WITHIN's blind spot) **and** the within-block ordinal
alignment (M-BETWEEN's blind spot), while preserving the candidate's block-structured marginal,
the row set, the response, the base and the season boundaries. It is the composition of the two
schemes `E0_I0014` already runs, not a new estimand.

**Storage.** Every draw is stored **signed and unstandardised** in `nulls/*.npz`, keyed by
`(arm, dependent)` with candidates on the column axis. `np.abs` is applied nowhere at a storage
site. Every stratum arm of every null is saved.

**Arms.** Four, each self-contained — its own rows, own SST, own base, own null, own bar. No
quantity is ever compared across arms (D101).

| arm | window | rows | player-season blocks | team-season blocks |
|---|---|---|---|---|
| **A4 CLEAN_DEC** *(reported first)* | 2023–2024 | 3,549 | 174 | 24 |
| A3 CLEAN | 2023–2024 | 9,517 | 311 | 24 |
| A2 DEC | 2022–2024 | 5,107 | 257 | 36 |
| A1 FULL *(comparability with the published cell)* | 2022–2024 | 13,879 | 475 | 36 |

`E0_I0014`'s own frame is 2022–2024; 2021 is not in it. The **clean window is 2023–2024** because
2022's forecasts depend only on 2021, which is degenerate (all forecasts at fallback level 4).
A1 is the only arm on which the published verdict was formed and is retained solely so the
re-measurement can be set beside it.
**Decision stratum** = `pl_games_prior >= 8 AND pl_min_mean5 >= 24` (≥8 prior appearances AND
≥24 trailing-5 minutes), the standing programme definition, using `E0_I0014`'s own columns.

**Power.** Block count is reported per cell for every arm. All four arms have ≥24 blocks, so the
sign-flip identity `p_min = 2^(1−nb)` is not binding (and it does not apply to a permutation null
at all — here `p_min = 1/(R+1)`). `R = 2000` draws, seed 20260808.

**Floors.** `MDE80 = (bar_abs + z80 · sd_signed_t)² / n`, `z80 = 0.8416`, the form
`E1_I0041` validated against an injection-verified floor to a median ratio of 0.989 across 96
conditions. `bar_abs` is taken two ways and **both are reported for every cell**: per-cell
(the null's own 97.5th percentile of `|t|`) and family-wise (the 95th percentile of the
`max|t|` over the 348 cells within a draw, computed on the shared index). Every floor is labelled
`ANALYTIC` or `INJECTION_VERIFIED`. The `null_mean > observed` flag is recorded but **not acted
on**: it is advisory only, its latest measured specificity is 0.840, and it is structurally
vacuous on sign-flip nulls.

---

## 2. Classification rule, frozen here

For each of the 73:

* **PERMANENTLY UNVERIFIABLE — STRUCTURALLY VOID**: the candidate has no within-season variation,
  so `ΔR²` is identically zero after the base. No null exists because no statistic exists.
* **PERMANENTLY UNVERIFIABLE — NO FUNCTIONING NULL**: the composed null still fails its own
  functioning test (§4 P1) on every arm.
* **RE-MEASURED — BLIND**: composed null functions, `MDE80 > 0.0023`.
* **RE-MEASURED — ADEQUATELY POWERED**: composed null functions, `MDE80 <= 0.0023`.
* Cells below D103's single-cell floor of **0.00102** are additionally flagged
  `BELOW_SINGLE_CELL_FLOOR`, where no null can produce a lead.

**Arithmetic-ceiling kills are excluded by rule and are not re-measured.** `E1_I0036` names 213;
the count found and excluded here is reported in the verdict.

---

## 3. The composite sweep

**Population.** The union of `E1_I0036/CENSUS.csv` (1,999 cells, 8 screens) and
`E1_I0040/AUDIT_TABLE_EXT.csv` (2,085 cells, 15 screens) — **4,084 cells, 23 screens,
540 distinct (screen, candidate) pairs.** The remaining 15 of the programme's 38 screens decide
no cell with a permutation null (`E1_I0040`'s COVERAGE_EXT finding) and therefore contribute no
candidate to sweep; that is asserted, not assumed.

**No name-based selection.** Six findings in this programme have died to substring matching.
A candidate is classified as a composite **only from its construction expression in source**,
located by exact-string match of the candidate name as an *assignment target*, then read.
The resolved list is printed in full and its count asserted. Classification classes:
`RATIO`, `DIFFERENCE`, `PRODUCT/INTERACTION`, `SUM`, `RESIDUAL_FROM_MODEL`, `BUNDLE`
(candidate is a list of columns, `E1_I0031`'s shape), `ATOMIC`, `UNDETERMINABLE`
(no construction site found — kept as its own category, never folded into ATOMIC).

**Invariant tested.** *A composite candidate requires a null valid for every component it
contains.* For each composite, the level of **every** component is determined — by measuring its
between-entity variance share on the screen's own frozen frame where a frame exists, marked
`var_share_source = COMPUTED`; by the screen's own recorded share where it wrote one, marked
`RECORDED`; and `UNDETERMINABLE` otherwise. A composite is **EXPOSED** when the null used is
valid for at least one component and invalid for at least one other, **and** the statistic can
see the component the null cannot (the `E1_I0040` clause, tested by the same ×10 / delete
perturbation).

---

## 4. Predictions, frozen before the re-measurement is run

**P1 — the composed null functions.** Over the re-measurable broken cells, on arm A1,
`|mean(signed t)| < 0.20` and `mean|t|/sd|t| ∈ [1.10, 1.60]` (the symmetric-null value is 1.32)
for **at least 90 %** of cells. A cell failing this on all four arms is PERMANENTLY UNVERIFIABLE.

**P2 — the void 18.** `pts__pred_sd`, `minutes__pred_sd`, `fga__pred_sd` × 6 dependents classify
PERMANENTLY UNVERIFIABLE — STRUCTURALLY VOID on every arm.

**P3 — the 35 reclassify downward.** At most **5** of the 35 cells D103 records as adequately
powered remain ADEQUATELY POWERED after re-measurement on arm A1.

**P4 — no survivors.** Every re-measured cell has a composed-null two-sided `p >= 0.05` on arm
A4. *This is the prediction whose failure would be the finding.*

**P5 — most composites are clean.** Of the 540 (screen, candidate) pairs, fewer than 25 % are
composites, and of those composites at most **20** are EXPOSED. `UNDETERMINABLE` is reported as
its own number and is not collapsed into either verdict.

**The pre-stated outcome that would clear the 73 entirely:** if the composed null's `p` and the
published `p_correct_level` agree in verdict for every cell (both `>= 0.05` or both `< 0.05`) and
no cell's classification moves, then the degeneracy was cosmetic and `E1_I0041`'s alarm was
overstated. That outcome is available and is not expected.

---

## 5. Constraints this screen operates under

* 2021–2024 only; **2025/26 never opened**. Manifests: `row`/`season` usable, `artifact` not;
  MISSING = UNVERIFIABLE.
* Write scope is `experiments/exploration/E1_I0044_broken_nulls_and_composites/` and nothing else.
  The shared screen kit is not modified. No `git` write command is run.
* No blanket process kill of any kind. Only PIDs launched by this screen are ever touched, and
  they are recorded in the run logs.
* Signed statistics are stored, never absolute values. Every stratum arm of every null is saved.
* No production change is enacted. No champion is fitted. Prior screens' directories are read-only.
