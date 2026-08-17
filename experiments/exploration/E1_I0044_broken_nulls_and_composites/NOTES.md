# NOTES — E1_I0044, the 73 broken nulls and the programme-wide composite sweep

## 0. What was asked and what came back

Two debts left by completed audits. `E1_I0041` found 73 cells whose permutation null does not
function and ruled them UNVERIFIABLE without doing the work. `E1_I0040` discovered the
composite-candidate failure mode in one screen and adopted an invariant nobody had swept for.

**Short answer.** The 73 split three ways by a mechanism that is measurable, not arguable:
**18 have no statistic at all** (the candidate is constant within season, so it is annihilated by
the screen's own base), **54 have a null whose *location* is broken and is repairable**, and
**1 has no functioning null anywhere on disk**. Re-measured under a repaired null, the 35 cells
D103 called adequately powered come back **18 permanently unverifiable and 17 still adequately
powered on the like-for-like arm — but 0 of 35 on the clean decision-stratum window.** The
composite sweep covers 540 (screen, candidate) pairs across the 23 screens that decide cells;
**174 are composites and 15 of them are exposed**, of which 14 were unknown.

## 1. Order of work

| step | script | output | note |
|---|---|---|---|
| anchors | `s00_anchors.py` | `_s00.json` | 1,349 / 760 / 0.5633802816901409 exact; 666 / 67 / 6 / 73 / 35 exact |
| structural probe | `s01_probe_broken.py` | — | read-only |
| exact reconstruction of E0_I0014 | `s02_diagnose.py` | `_E0_I0014_CELL_DIAG.csv` | vsb 0.000e+00, t 3.9e-15 rel (276/348 bitwise), null sd 2.2e-16, p 0/348 mismatches |
| mechanism + blindness test | `s03_mechanism.py` | `_COMPONENT_T.csv`, `_STATISTIC_BLINDNESS.csv` | |
| **PREREG written and hashed** | — | `PREREG.md`, `PREREG.sha256` `d25fc5ec…` | |
| re-measure, composed-1 | `s04_remeasure.py` | `_REMEASURE_ALL_ARMS.csv`, `nulls/composed_null_*.npz` | **defective, kept** (DEFECTS D-1) |
| re-measure, composed-2 | `s07_remeasure_v2.py` | `_REMEASURE2_ALL_ARMS.csv`, `nulls/composed2_null_*.npz` | the one every verdict uses |
| the E0_I0019 cell | `s09_e0i0019.py` | `_E0_I0019_ARMS.csv` | resolved from disk, no refit |
| broken-null table | `s11_broken_nulls_table.py` | **`BROKEN_NULLS.csv`** | all 73 |
| family-wise p | `s12_typeI_and_fw.py` (part B) | `_FAMILYWISE_P_COMPOSED2.csv` | |
| Type-I + injection | `s13_typeI_injection_fast.py` | `TYPE_I_CALIBRATION.csv`, `INJECTION_VERIFICATION.csv` | |
| composite population + sites | `s05`, `s06_sites_v2.py` | `_CONSTRUCTION_SITES_V2.csv`, `_GENERATORS_REJECTED.csv` | |
| expression classification | `s08_classify.py` | `_CLASSIFY_RAW.csv` | `ast` parse of the right-hand side |
| source-read overrides | `s14_composite_sweep.py` | `_COMPOSITE_SWEEP_STAGE1.csv` | 134 overrides, 133 matched |
| pending resolution | `s15_resolve_pending.py` | `_PENDING_RESOLVED.csv` | |
| measurement of the interactions | `s16_measure_interactions.py` | `MEASURED_COMPONENT_SHARES.csv` | resolved 23 of 51 undeterminable |
| final sweep | `s17_finalise_sweep.py` | **`COMPOSITE_SWEEP.csv`** | |
| ranking + ceiling check | `s18_ranking.py` | `SURVIVOR_RANKING_A4.csv`, `_A1.csv` | |

`s00`–`s03` ran before the preregistration was written. They are descriptive confirmations of
what is on disk, and every number they produced is quoted inside `PREREG.md`, so nothing in §4's
predictions could be back-fitted.

## 2. The mechanism, and why "degenerate null" was three different things

`E1_I0041` reported one number — `mean|t|/sd|t| > 5` — for 67 cells and `sd = 0` for 6. The
three mechanisms behind it are disjoint and only one of them is a null problem at all.

**M-VOID, 18 cells, 3 candidates.** `pts__pred_sd`, `minutes__pred_sd`, `fga__pred_sd` take
**exactly one distinct value per season** in all three seasons of `E0_I0014`'s frame. After the
screen's own base (season fixed effects) the design column has `sxx` of 0.000e+00 / 9.09e-27 /
4.59e-26, against **1.3876e+04** for all 55 other candidates. The observed `t` is `NaN` for `fga`
and ~1e-13 for the other two. `s04_screen.py:215` writes 0.0 for a non-finite permuted `t`, which
is where D103's `sd = 0` and its detection floor of *exactly 0.0* come from. These cells were
never measurable and no null can make them so. `E0_I0014`'s `add()` guard tests
`np.nanstd(out) == 0` over the whole frame, which a per-season constant passes.

**M-WITHIN, 52 cells.** `within_block_index` shuffles inside each (season, player) block, and the
block mean survives **exactly** — measured max change over all 475 blocks × 58 candidates
**1.776e-15**. For every one of these cells the block-mean component alone carries a larger `|t|`
than the assembled candidate does: `pl_pts_sd5|pts_absres` has `t_full` 25.60,
`t_blockmean_only` **44.04**, `t_withindev_only` −2.47. So the null cloud sits on top of the
alternative and `mean|t|` runs to 27.6 while `sd|t|` stays near 0.9.

**M-BETWEEN, 3 cells.** `block_index` maps the donor block onto the receiver **in chronological
position order** and truncates a long donor to its first `len(b)` rows, so the within-block
ordinal profile survives. Measured correlation between the real and permuted within-block
deviation: 0.140 for `pts__pred_width`, and 0.48–0.64 for the monotone counters
`pl_games_prior`, `pl_minutes_prior`, `pts__n_prior_games`, `pts__is_fallback`,
`pts__fallback_level` — for which **both** of `E0_I0014`'s schemes retain signal.

Two hypotheses in the brief were tested and are **false** here: the permutation set is never
trivially small (1,000 distinct draws in every non-void cell), and no cell is below six blocks
(475 player-season blocks, 36 team-season, and 174/24 on the smallest arm). The sign-flip
identity `p_min = 2^(1−nb)` does not apply to a permutation null at all; `p_min = 1/(R+1)`.

## 3. The blindness test, run before condemning anything

`E1_I0040` established that a null cannot be blind to something the statistic cannot see, and
proved it by multiplying the suspect component by ten and then deleting it (max change
4.441e-16, which is how `E1_I0021` escaped a mechanical condemnation). The same test, on all 72
`E0_I0014` broken cells: **minimum change in `t` over every manipulation 2.303861e-02, and the
number of cells whose statistic cannot see the blind component is 0 of 72**
(`_STATISTIC_BLINDNESS.csv`). `E0_I0014`'s statistic is a pooled `t` on the raw candidate, so the
escape hatch does not exist here. This is a measured negative and it is what licenses the rest.

## 4. The repaired null, and why it took two attempts

Composed-2: one gather index per draw, shared across all 58 candidates so max-|t| stays valid;
a donor block drawn at random within season, then `len(b)` values resampled uniformly from the
**whole** donor block. It destroys the block-mean alignment (M-WITHIN's blind spot), the
within-block ordinal alignment (M-BETWEEN's) and the length truncation (my own composed-1's,
DEFECTS D-1), while preserving the candidate's block-structured marginal, the rows, the response
and the base.

Result on the whole 348-cell family, arm A1_FULL: **330 of 348 function** (`|mean signed t|`
< 0.20 and `mean|t|/sd|t|` ∈ [1.10, 1.60]); the 18 that do not are exactly the 18 void cells.
Median degeneracy ratio **1.3259** against 1.32 for any symmetric null; median `|mean signed t|`
**0.0230**. Signed, unstandardised draws for every arm are in `nulls/composed2_null_*.npz`.

**But it is not uniformly calibrated, and that is the largest single caveat in this screen.**
Measured Type-I at δ = 0 on five cells, nominal 0.05, MC se 0.0109:
**0.0225 / 0.0250 / 0.0525 / 0.1475 / 0.5950** (median 0.0525). Three pass. Two do not:
`pts__pred_cv`, a ratio with a heavy tail, and `pl_games_prior`, a pure within-block counter for
which **no permutation scheme tested — mine, `E0_I0014`'s, or the row-naive one — is valid**
(0.595 / 0.925 / 0.908). For contrast on the same synthetic responses, `E0_I0014`'s **own
level-matched null** measured 0.0175 / 0.0675 / **0.2500** / **0.5925** / **0.9250**, median
0.2500, and the row-naive null 0.2625 / 0.1800 / 0.2800 / 0.5475 / 0.9075.

Consequence: **the survivor list in `VERDICT.md` §2 is a follow-up queue, not a finding**, and
49 of the 54 re-measured cells have no measured Type-I at all. DEFECTS D-2.

## 5. Arms, and which window backs which number

Four self-contained arms, nothing ever compared across them (D101).

| arm | window | rows | player-season blocks | team-season blocks |
|---|---|---:|---:|---:|
| **A4_CLEAN_DEC** *(reported first)* | 2023–2024 | 3,549 | 174 | 24 |
| A3_CLEAN | 2023–2024 | 9,517 | 311 | 24 |
| A2_DEC | 2022–2024 | 5,107 | 257 | 36 |
| A1_FULL | 2022–2024 | 13,879 | 475 | 36 |

`E0_I0014`'s own frame is **2022–2024** — 2021 is not in it, so the "2021 is degenerate" hazard
does not reach this screen directly, but 2022's forecast-side candidates depend on 2021 and the
clean window is therefore 2023–2024. **Every headline number in `VERDICT.md` §1 is on A4, the
clean window intersected with the decision stratum** (`pl_games_prior >= 8 AND
pl_min_mean5 >= 24`, the screen's own columns). A1 exists so the re-measurement can be set beside
the published cell it corrects, and for no other purpose.

Four cells cannot be evaluated on A4 at all: `pts__is_fallback` and `pts__fallback_level` are
constant inside the decision stratum, because a row with ≥8 prior appearances is never a
fallback row. They are `UNVERIFIABLE` on A4 and measured on A1.

## 6. The composite sweep — what "programme-wide" turned out to mean

38 screens exist. **23 of them contribute a candidate to any decided cell**; the other 15 decide
nothing with a permutation null (`E1_I0040`'s `COVERAGE_EXT.csv`, asserted here, not assumed).
Population: `E1_I0036/CENSUS.csv` (1,999 cells, 8 screens) ∪ `E1_I0040/AUDIT_TABLE_EXT.csv`
(2,085 cells, 15 screens) = **4,084 cells, 540 distinct (screen, candidate) pairs**, all three
counts asserted.

Classification is from the **construction expression**, never the spelling. 523 of 540 resolved
to a construction site; the 17 that did not are twelve bare numbers and five tier labels that are
not candidate names at all (DEFECTS F-3).

| | pairs |
|---|---:|
| COMPOSITE (ratio / difference / product / sum / bundle / model spec) | **174** |
| ATOMIC or single-quantity aggregate | 258 |
| NOT A FEATURE (stratum, arm label, harvest artefact) | 37 |
| construction UNDETERMINABLE | 71 |

Among the 174 composites: **15 EXPOSED, 129 NOT EXPOSED, 28 UNDETERMINABLE, 2 not applicable.**

**Undeterminable was kept honest.** 51 composites entered undeterminable; 23 were resolved by
*measuring* component variance shares on the screens' own frozen frames
(`MEASURED_COMPONENT_SHARES.csv`), which is a measurement and not a name lookup. 28 remain and
are named in full in `COMPOSITE_SWEEP.csv`.

## 7. What I did not do

* **No 2025/26 data was opened.** Every frame read asserts `season <= 2024` and
  `max(gdate) < 2025-01-01` before use (`scripts/_rebuild_e14.py`, `s16_measure_interactions.py`).
* **No production change was enacted and no champion was fitted.** Nothing outside
  `E1_I0044_broken_nulls_and_composites/` was created or modified. `_screen_kit/` was never
  opened for writing. No `git` command was run.
* **No blanket process kill.** Two PIDs were stopped, both launched by this screen and both
  recorded (DEFECTS D-4). `Get-Process python | Stop-Process` and `taskkill` were never issued.
* **I did not revise D103, `E0_I0014`, `E0_I0019` or any other screen.** Every prior directory is
  byte-identical to how I found it.
* **I did not re-measure any arithmetic-ceiling cell.** `E1_I0036` names 213, all in
  `E0_I0024_reb_ast_characterisation`; **0 of the 73 and 0 of the 15 exposed composites are among
  them**, so 0 were found and excluded (`s18_ranking.py`).
* **I did not run a composed null on `E0_I0019`.** That is the one thing that would settle its
  single broken cell and it is a refit on another screen's frame.

## 8. What I would send the next screen after

1. **`E0_I0014`'s family-wise bar, again.** `E1_I0041` flagged it and this screen measured the
   consequence: 41 of the 54 re-measurable broken cells carry a published
   `p_familywise_whole_screen` of **exactly 1.000**, and 33 of them are family-wise significant
   under a properly built bar. That is a verdict-level correction to a live screen, not a
   retrospective power correction, and it is bigger than anything D103's conversion did.
2. **`E0_I0024`'s `p_correct = max(p_swap, p_cyc)`** (`s04_screen.py:153`) is the banned
   conjunction, live, as the verdict column, on 250 cells and 213 ceiling kills. It is in the
   census, so `E1_I0040`'s "zero in the thirty" is intact — and nobody has checked the eight.
3. **A studentised or rank-based statistic for the ratio candidates.** `pts__pred_cv`,
   `pl_min_cv5` and their siblings break Type-I on every null tried here, including mine.
4. **The 28 undeterminable composites**, four of which (`E1_I0030`'s `__RECON_*`) are
   undeterminable because they have no null at all.
