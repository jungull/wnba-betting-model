# NOTES — E1_I0043_opponent_defence

`PREREG.md` sha256 `629fe4aa2d757d393ec7db5861feba28e431f25cb89562ac1e61e05cf9b73add`,
hashed before any statistic produced by this screen existed. 0 cells added, 0 dropped.

---

## FRAME AND PARTITION

Inner merge of two frozen artifacts on `(season, player_id, game_id)`:

* `E0_I0016_efficiency_predictors/screen_frame.parquet` — D085's frame, 14,852 × 67, the source of
  `A10_opp_defrtg`.
* `E1_I0018_teammate_volume_channel/screen_frame.parquet` — D089's frame, 14,852 × 59, the source of
  `prior5_minutes`, `y_pts`, and the `refB_*` player-prior family.

Merged: **14,852 rows** (asserted against the literal), 247 players, 48 opponent-team-seasons,
827 games, 313 dates, seasons {2021, 2022, 2023, 2024}.

`assert_partition` is value-level and reimplemented locally. **It checks only columns whose dtype is
actually datetime; nothing is coerced.** This is the K0 trap: `'date' in 'candidate'` is `True`, and
`pd.to_datetime` on a float column returns 1970-01-01 rather than raising, so a name-based date
detector raises `PartitionViolation` on a wholly in-partition frame. Both frames' only datetime
column is `game_date`, max 2024-09-19. **2025/26 was never read, joined, merged, plotted or
described.**

**The shared screen kit was neither imported nor modified.** `EntitySwap` is a faithful
reimplementation of `E0_I0016/ep_base.py::EntitySwap` (read-only) with that authorship credited in
the source; the 16-anchor reproduction is the check that the reimplementation is faithful.

## THE ONE CLEAN WINDOW

Walk-forward evaluation on **2023 and 2024 only**. E1_I0042 verified from fold receipts that 2021 is
degenerate (all forecasts at fallback level 4, a constant with no usable residual) and that 2022
depends only on 2021. 2021 and 2022 appear as **training rows only** in the headline. A 2022-eval
arm is computed, reported, and labelled at every appearance as resting one step from the degenerate
fold. **No second window was manufactured.**

## COLUMN SELECTION

Every list is a literal allowlist, printed at resolution and length-asserted against a literal. No
substring, prefix, regex or `startswith` selection occurs anywhere in this screen.

```
CANDIDATE      n=1  ['A10_opp_defrtg']
B0_COMPLETE    n=5  refB_ppm refB_spm refB_pps refB_mpg refB_own_usg_pg
B1_HONEST      n=7  B0 + D01_tm_poss_per40 D02_opp_poss_per40
B2_FAMILY      n=9  B1 + A01_opp_efg_allowed A02_opp_ts_allowed
A_FAMILY       n=12 (the D085 opponent-allowance family, enumerated)
complete-case  n=13 (printed in run_log_s02.txt and run_log_s03.txt)
```

The candidate is a **single column**, asserted, so D120's "a composite candidate needs a null valid
for every component it contains" is satisfied by construction — and the assertion is the proof
rather than the claim. Component-wise validity is nevertheless measured (s05), because a single
column can still have components a null is blind to, which is the whole point.

## NULLS

| id | scheme | permuting unit | blocks | role |
|---|---|---|---|---|
| `N_ESWAP` | relabel whole opponent-team-season series within season, proportional-position map | opponent-team-season | 48 (24 in the eval window) | **VERDICT** |
| `N_DATE` | permute opponent-team-game values among the games on the same date | opponent-team-game within date | 1,627 | **VERDICT** (second) |
| `N_BLIND` | free shuffle **inside** each opponent-team-season | opponent-team-season | 48 | **CONTRAST ONLY** |
| `N_WITHIN_PLAYER` | cyclic shift inside each player-season | player-season | 600 | **CONTRAST ONLY** |

`N_DRAWS = 2000` on the verdict cells, `SEED = 20260808`. `p` is the add-one estimator, so
`p_min = 1/2001 = 4.998e-04` and no `p` is ever 0.

**Block counts are reported for every cell.** The headline cell has 24 opponent-team-seasons in the
eval window and 48 in the permuted frame. A two-sided sign-flip at 24 blocks would have
`p_min = 2^(1−24) = 1.192e-07`; this screen does not use a sign-flip for any verdict, so the
`nb < 6` arithmetic-incapability rule never binds. `sqrt(24) = 4.899` is the ceiling on any block
`t` statistic and no `t` above it is quoted anywhere.

**Every floor quoted in this screen is INJECTION-VERIFIED.** No analytic MDE80 appears anywhere
(D113: the analytic rule is anti-conservative by up to 1.27× at 8 blocks).

**Every null's raw, unstandardised draws are on disk** in `nulls/*.npz`, each carrying the observed
signed statistic, the null mean, the null sd, the block count, and the stratum/response/base/arm/
scheme keys. Nothing is standardised before storage — `E0_I0017` lost 117 cells permanently by
storing z-scores. Signed statistics only; no absolute value is stored anywhere.

## THE FROZEN / UNFROZEN CONTRAST

* **UNFROZEN** — refit the augmented model on the training fold; intercept and every base
  coefficient free. The conventional ΔR².
* **FROZEN** — intercept and every base coefficient held at the base fit. Only the defence
  coefficient is estimated, on the base's training residual, against a **train-mean-centred**
  defence column so no mean shift can enter through the back door.
* **INTERCEPT_ONLY** — a free intercept shift and no defence column at all, so the intercept's own
  contribution is measured rather than inferred. It returns **exactly +0.00000000** on every cell.

## MACHINERY VALIDATION

The fast Frisch–Waugh–Lovell path is checked against a literal `np.linalg.lstsq` refit on real data
before any statistic is produced: **0.00939777595318 vs 0.00939777595311, |diff| 6.573e-14.**

The no-op placebo (the identical column passed as a "probe") returns the observed statistic to
**|diff| 0.000e+00**, asserted at `< 1e-15`.

## ANCHORS — 16, REPRODUCED BEFORE ANY NEW STATISTIC

`ANCHORS.csv`. Four at exactly **0.000e+00**, the rest below the precision at which the source
recorded them.

| anchor | what | \|diff\| |
|---|---|---|
| A7a/b/c | both frames and the merge at 14,852 rows | **0.000e+00** |
| A1 | D085 `A10_opp_defrtg → ppm` dR² over `refB_ppm` = 0.001443097415 | **9.324e-18** |
| A1b | the same cell over `refA_ppm` = 0.001508765789 | 1.930e-17 |
| A3 | between-opponent-team-season variance share 0.771355969528 | 1.110e-16 |
| A2a/b/c | D085's `p_N2` 0.001664, `p_familywise_N2` 0.009983, `p_N1` 0.870216 | ≤ 3.6e-07 |
| A4a–d | D098's ceiling 0.01280821, lever 0.739198 pts, realised 0.018703, n 1,687 | ≤ 3.5e-07 |
| A5a/b | D099's corrected realised 0.003335 on n 4,514 | ≤ 4.2e-07 |
| A6 | D093's Spearman 0.3200431235648813 | **0.000e+00** |

The decision stratum itself reproduces the programme's recorded **n = 5,673** exactly, which was not
in the preregistered anchor list and is recorded here as a bonus reproduction.

## D087 REFERENCE-COVERAGE ASSERTIONS

Every base column's finite count is asserted equal to the stratum row count and printed
(`REFERENCE_COVERAGE.csv`). All 21 base-column × base combinations return coverage exactly 1.000000
on 5,673 rows; complete-casing drops **0 rows**. A reference silently covering part of the rows is
the D087 failure mode and shrank one screen's effects by 2.2×–8.3×; the assertion is the guard, and
here it does not fire.

## WHAT THE CHANNEL ACTUALLY IS

`PLACEBOS.csv`, on the primary cell:

| probe | signed ΔR² | share of observed |
|---|---|---|
| OBSERVED | +0.00939778 | 1.000 |
| no-op (identical column) | +0.00939778 | **1.000, \|diff\| 0.000e+00** |
| league mean on date | −0.00024048 | **−0.026** |
| within-date demeaned | +0.01013469 | **+1.078** |
| **opponent-season MEAN only (77.1% of variance)** | **+0.01103633** | **+1.174** |
| within-opponent-season deviation only (22.9%) | −0.00025220 | **−0.027** |

The channel is **entirely the opponent's current-season defensive LEVEL**. It is not a calendar or
league-drift artefact (the date-mean placebo returns −2.6%), it is cross-sectional (within-date
demeaning keeps 108%), and the "how is this defence playing lately" component contributes nothing
(−2.7%). Anything built on this channel would be a season-level opponent-strength adjustment, not a
form or matchup read.

**The opponent's PREVIOUS-season mean returns +0.00094229** — below the single-cell floor of
0.00102. The signal is in-season accumulation, not durable team quality.

## VACUOUS-CONTROL CHECK

`VACUITY_BANDS.csv`. Eval rows split into terciles by |deviation of the opponent's rating from its
mean|:

| band | n | contribution to ΔR² | share of the gain |
|---|---|---|---|
| nearest an average defence | 1,055 | +0.00015441 | **+1.6%** |
| middle | 1,056 | +0.00218126 | +23.2% |
| most extreme defences | 1,056 | +0.00706211 | **+75.1%** |

The gain lives on the rows the candidate actually moves. This is not a vacuous control.

## LEAD-LAG / ORACLE PROBE (diagnostic only, never a headline)

Because the whole channel turns out to be a season-level quantity, and a season-level quantity is
exactly the shape a leak would take if the "strictly prior" expanding mean were contaminated:

| column | `y_ppm` | `y_pts` |
|---|---|---|
| `A10_opp_defrtg` strictly-prior expanding (**the candidate**) | +0.00939778 | +0.00452075 |
| opponent FULL-SEASON mean (**reads the future**) | +0.01103633 | +0.00571311 |
| oracle / prior ratio | **1.174** | **1.264** |

The future-reading column is materially better, so the prior column is a genuinely prior and noisy
estimate. Had they been equal, that would have been the leak signature.

## DISCLOSURES

1. **The independence audit's conclusion was reached before any effect size existed**, as
   preregistered, and it did not change afterwards.
2. S1 and S3 row sets are **reconstructions** and miss their recorded counts by 182 and 3 rows
   (`DEFECTS.md` D-03). S2 and S4 reproduce exactly.
3. `s02`'s ceiling was computed on the wrong scale and is superseded by `s04`'s. **The uncorrected
   table is kept on disk** as `CEILING.csv` rather than deleted (`DEFECTS.md` D-02).
4. The oracle-column probe and the ORACLE ceiling form both read the future by construction. Both
   are labelled DIAGNOSTIC and neither is a headline.
5. The negative control `G01_noise` was run through every path. It clears nothing:
   ΔR² +0.00019978 at `p = 0.111444` (`N_ESWAP`) and `p = 0.082959` (`N_DATE`) on the primary cell's
   configuration. **It is not significant, and it is also not zero** — a walk-forward noise column
   returns roughly 0.2× the single-cell floor on this stratum, which is the scale of the "no effect
   at all" background here.
6. **The injection study's per-replicate seeds are not bit-reproducible across processes.** They are
   derived as `SEED + 1000*r + hash(scheme_name) % 97`, and Python randomises `str.__hash__` per
   process unless `PYTHONHASHSEED` is set. The power estimates are valid; the exact draw sequence is
   not reproducible from the recorded seed alone. The one-line fix is to replace `hash(sname)` with
   a literal per-scheme integer. Recorded rather than repaired, because repairing it means a 25-minute
   re-run that would change the third decimal of numbers whose se is 0.025 anyway.
7. Scripts `s04`, `s05` and `s06` were written after `s03`'s effect sizes were seen. **They are
   declared as kill attempts, with their hypotheses stated in their own docstrings before they were
   run**: s04 asks whether the effect is a date/level artefact or shared-intercept movement, s05
   whether the null can see the candidate at all, s06 whether the column is leaking and whether the
   effect survives its own family bar. Three of the four hypotheses failed to kill it; the fourth
   (season stability, in s04) partly succeeded and is in `VERDICT.md`'s counterweight.
8. No process was killed that this screen did not launch. Launched PIDs, all recorded at launch and
   all exited on their own: **30304** (s03), **18936** (s04), **34428** (s05). s01, s02 and s06 ran
   in the foreground.
9. Nothing outside `experiments/exploration/E1_I0043_opponent_defence/` was written, staged or
   committed. No `git` write command was issued. No champion was fitted, no production change
   enacted, no promotion proposed.
