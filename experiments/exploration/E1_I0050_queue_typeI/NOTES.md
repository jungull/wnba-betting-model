# NOTES — E1_I0050

## What this screen was asked to settle, and what it settled

`E1_I0044` re-measured 54 cells under a repaired permutation null, found 37 at `p < 0.05` and 17
family-wise significant on the clean decision stratum against a published `p_familywise` of
exactly 1.000, and declined to claim it because it had measured its own null's Type-I on five
cells and two of those five came out at 0.1475 and 0.5950.

This screen measured Type-I on all 54, on two arms, against three synthetic-data generators and
three null schemes — 972 rejection rates. The result is that **the composed-2 null is fine and
`E1_I0044`'s Type-I control was not**, and that **the published 1.000 is one cell's broken null**.

Order of work, and what was fixed before what:

1. `s00` — anchors from prior screens' own artefacts, then the explicit 54-cell allowlist and the
   void-leak check. **Run before anything new was computed.** 25 of 26 anchors reproduced.
2. `s01` — forensics on the published family-wise bar. Read-only, no new estimand.
3. **`PREREG.md` written and hashed**, quoting `s00` and `s01` so §5's predictions cannot be
   back-fitted.
4. `s02` — the Type-I measurement, A4 then A1.
5. `s03` / `s07` — distributional shape and whether it predicts anything.
6. `s04` — validity rule applied; corrected p and family-wise recomputed from `E1_I0044`'s saved
   signed draws rather than from its CSV.
7. `s05` / `s05b` — the four preregistered instrument self-tests, and the follow-up that
   established whose fault the failing one was.
8. `s06` — the post-hoc position-adjusted robustness arm (declared post hoc; `DEFECTS.md` D-6).
9. `s08` — `FINDINGS.json`, assembled by reading the files, not by typing numbers.

## Files

| file | what it is |
|---|---|
| `PREREG.md` + `.sha256` | preregistration, `9a0eb0e7…908c` |
| **`TYPEI_PER_CELL.csv`** | 108 rows = 54 cells × 2 arms. Rejection rate for 3 generators × 3 null schemes, Clopper–Pearson intervals, n synthetic, verdict on the null's validity |
| **`CORRECTED_VERDICTS.csv`** | 108 rows. Corrected per-cell and family-wise p (both conventions), ΔR², floors, null validity, confounding flag, corrected verdict, published comparators |
| `WHY_1.000.md` | which side of the discrepancy is the artefact |
| `SHAPE_RULE.md` | is Type-I inflation predictable from shape (no), and the rule that is general (about the generator) |
| `VERDICT.md` | the summary |
| `DEFECTS.md` | 8 of my own, 6 found in other screens |
| `FINDINGS.json` | every headline number, read from the files |
| `_QUEUE54.csv` | the allowlist with published comparators |
| `_PUBLISHED_BAR_ANATOMY.csv` | per-cell null location for all 348, and which cell supplies the bar |
| `_TYPEI_RAW_*.csv` | the raw per-(cell, generator) rows behind `TYPEI_PER_CELL.csv` |
| `_SELFTESTS.csv`, `_HARNESS_EXACTNESS.csv` | PREREG §6 and the follow-up |
| `_SHAPE_CAND_*.csv`, `_SHAPE_RESP_*.csv`, `_SHAPE_TABLE.csv`, `_SHAPE_SPEARMAN.csv` | shape features and correlations |
| `_POSITION_ADJUSTED.csv` | the post-hoc robustness arm |
| `nulls/typeI_raw_*.npz` | **signed, unstandardised** observed `t` over all 1,000 synthetic datasets per cell per generator; per-replicate p; the null `t` pool for the first five replicates |
| `nulls/posadj_composed2_*.npz` | signed unstandardised draws for the position-adjusted arm, all 348 cells, both arms |
| `scripts/run_log_*.txt` | every run, including the crashed one |

## Storage discipline

Every stored statistic is **signed and unstandardised**. `np.abs` appears at no storage site in
`s02`, `s06` or `s08` — absolute values are formed only inside a comparison and discarded. Every
stratum arm of every null is saved. The stratum key (`arm`) is a column on every row of every
deliverable, so no cell is unauditable for the reason 24 cells in this programme already are.

## Preserved rather than overwritten

* `scripts/run_log_s02_A4_run1_CRASHED.txt` and its `_err` — the first A4 run, which died on a
  `ZeroDivisionError` because two candidates are constant inside the decision stratum. Not killed;
  it exited on its own. No output CSV was produced, so nothing was overwritten.
* The Clopper–Pearson defect (`DEFECTS.md` D-1) affected only intervals, never rates. The first
  A4 run's log preserves the `[1.0000, 1.0000]` output it produced.

## Process discipline

**No blanket kill of any kind was issued at any point.** No `Get-Process python | Stop-Process`,
no `taskkill`, no wildcard, no `-Force` against a process. Three sibling agents were running
concurrently throughout and no process I did not launch was touched. Six PIDs were launched —
7540, 31028, 11504, 29792, 28156, 33200 — all recorded in `scripts/_s0*_pid.txt`; five ran to
completion and one (7540) exited on its own with an error. **None was killed.**

## Scope discipline

Every write is inside `experiments/exploration/E1_I0050_queue_typeI/`. The shared screen kit
`_screen_kit/` was never opened for writing. No `git` command of any kind was run. Prior screens'
directories were read only — `E0_I0014`, `E1_I0044`, `E1_I0041`, `E1_I0026`. `E1_I0044`'s
`scripts/_rebuild_e14.py` is `exec`'d as read-only input and is not modified; that is the
mechanism by which this screen reproduces `E0_I0014`'s matrices exactly.

## Partition

2021–2024 only. **2025/26 was never opened, never listed, never read.** `E0_I0014`'s frame
contains 2022, 2023 and 2024 — 2021 is absent from it, which is why the clean window here is
2023–24 rather than the programme's usual statement. Both `_common.py` and `E1_I0044`'s rebuild
script assert `season <= 2024` and `max(gdate) < 2025-01-01` before any frame is used.

## Selection discipline

No name-based selection anywhere. The 54 come from an explicit `resolution` column in
`E1_I0044/BROKEN_NULLS.csv`, are printed in full in `run_log_s00.txt`, and their count is
asserted in code (`assert len(CELLS54) == 54 and len(set(CELLS54)) == 54`). The 18 structurally
void cells are identified **by measuring** `sxx` after the screen's own base, not by matching a
label string, and the measured set is asserted identical to `E1_I0044`'s labelled set. The
intersection is asserted empty. Every candidate in the queue is asserted player-level before its
blocks are built.

## Two things a successor should not have to rediscover

1. **Level and blindness are different failures.** `E0_I0014`'s within-block null has a Type-I of
   0.057 — perfectly calibrated — and is centred at `|t|` = 27.6 on the real response. A Type-I
   audit alone clears it. A blindness audit alone would clear a null that over-rejects. Any future
   null audit in this programme needs both, and neither `E1_I0044` nor this screen ran both on
   every cell.
2. **A Type-I study's generator is itself an instrument that can be wrong, and wrong in the
   direction of condemning good work.** Whole-block resampling that preserves within-block
   position is not an effect-free generator for any candidate that is a function of position. The
   check that catches it is cheap and should be standard: **record the mean signed observed `t`
   over the synthetic datasets and require it to be ≈ 0.** Here it was 0.020–0.055 under the two
   valid generators and up to **7.31** under the invalid one.

## Not done, and named

* No exact null was built. Composed-2 is conservative (`DEFECTS.md` D-2) and a studentised or
  wild-bootstrap alternative would probably recover power, but constructing one after seeing the
  survivor list would be fitting and was not done.
* The extra variance from the shared permutation pool was not measured (D-4).
* `E0_I0019 pl_opps_prior|brier`, the 73rd cell, is still `PERMANENTLY UNVERIFIABLE — no
  functioning null on disk`. Settling it needs a composed null on `E0_I0019`'s own frame, which is
  a refit on another screen and was not run here either.
* The 18 structurally void cells were verified void and not re-measured. Correctly: no statistic
  exists.
