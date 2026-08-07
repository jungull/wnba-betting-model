# E0 I0011 — F_TENDENCY_ESTIMATOR: does *how* you estimate a player's tendency matter?

**This is an E0 exploration screen. It produces a LEAD, never a RESULT.** No significance
claim, no promotion, no leaderboard entry. Time-boxed.

## Hypothesis as registered

> How a player's underlying tendency is **estimated** materially changes forecast accuracy:
> a shifted, context-normalized EWMA at a **tuned** horizon beats the untuned rolling/EWMA
> baselines the program has been using, and the best horizon differs by stat and by role.

The hypothesis has three separable claims. They did **not** all survive, and separating them
is the main content of this screen:

1. tuned horizon > untuned baselines — **survives, but the size depends entirely on which
   baseline you mean** (large vs the program's incumbent, small vs a season-to-date mean);
2. context normalization helps — **does not survive**;
3. best horizon differs by stat and by role — **by stat: no. By role: yes. By channel
   (efficiency vs exposure): yes, and that is the actual finding.**

## Inputs and the manifest check (GRAPH_POLICY §13.2.2)

**`data/masters/master_player.parquet`** — sibling manifest
`master_player.parquet.manifest.json`, quoted verbatim in the relevant part:

```json
{
  "artifact": "data/masters/master_player.parquet",
  "asof_granularity": "row",
  "bound_source": "game_date via asof_invariant.bound_from_dates",
  "fit_seasons": [2021, 2022, 2023, 2024, 2025, 2026],
  "fit_through_season": 2026,
  "producer": "build_masters.py",
  "schema": "asof_invariant/1"
}
```

`asof_granularity` is **`"row"`**, so per §13.2.2 filtering to 2021-2024 is sufficient and the
`fit_through_season: 2026` field does not make the artifact unusable. (Note for the record:
E0_I0008's NOTES.md treated this same artifact as contaminated on the basis of
`fit_through_season` alone; §13.2.2 supersedes that reading, because the as-of bound here is
derived per row from `game_date`.)

**`data/masters/master_team.parquet`** — sibling manifest is identical in structure and also
declares `"asof_granularity": "row"`, same `fit_seasons` and `fit_through_season`. Same
conclusion. Used only to derive team-game possessions and opponent-allowed rates.

No other pre-built artifact was used. Nothing was read from `features/`, `forecasts/`,
`leaderboards/`, or any fitted model object.

### FILTER-POINTs

`build_frame.py` filters immediately after every load, before any join or computation:
- `tm = tm[tm["season"].isin(PARTITION)]` on the line after `read_parquet(master_team)`;
- `mp = mp[mp["season"].isin(PARTITION)]` on the line after `read_parquet(master_player)`.

`assert_partition()` is called after **every** step (raw load, context build, merge,
prior-season merge, final frame) and prints the surviving season set. All eight prints in
`run_log.txt` show `[2021, 2022, 2023, 2024]`.

## Partition verification ON THE OUTPUT BYTES

`verify_partition.py` (output: `run_log_verify.txt`) runs two independent checks over all 21
files this experiment wrote.

**(1) Structural.** Every output carrying a `season` column was reloaded and its value set
checked against `{2021,2022,2023,2024}`:
- `frame.parquet` → `[2021, 2022, 2023, 2024]` **PASS**
- `gap_bootstrap.csv` → `[2023, 2024]` **PASS**
- all other outputs carry no `season` column (they are keyed by estimator/slice/split labels).

**(2) Byte-level.** Raw bytes of every file scanned for the literals `2025` and `2026`,
with 45 bytes of context printed for each of the 76 hits so each can be judged by eye.
Every hit is one of exactly four benign kinds, and there are no others:
- digits inside a float, e.g. `4.374854130822199,5.528265620255885` and `1.202589809227255`;
- the RNG seed `SEED = 20260807` in `build_frame.py` / `score.py` / `PRE_DECLARED_SLICES.md`;
- a **row count** that happens to equal 2026 — the `S1_starter=0` slice has 2026 scored rows
  in 2023 and 2026 in 2024 (`heterogeneity.csv`, `run_log.txt`);
- `verify_partition.py`'s own search literals, in its source and its docstring.

A fifth benign kind exists in **this file only**: NOTES.md itself contains the tokens because
it quotes the manifest's `fit_seasons` array verbatim (as §13.2.2 requires) and because this
paragraph describes the scan. Those 17 hits are prose and a quoted JSON field, not data.

**No output file contains a 2025 or 2026 season value.** 2025/2026 rows were never loaded
into any dataframe: both masters were filtered on the line following their `read_parquet`.

## Selection / scoring split (the circularity guard)

Pre-declared in `PRE_DECLARED_SLICES.md`, written before `score.py` existed, and never revised:

- **SELECT on seasons 2021 + 2022.** Every hyperparameter — EWMA alpha, rolling window,
  shrinkage weight, and the *choice of estimator family* — is chosen by minimising MAE on
  these two seasons and nothing else.
- **SCORE on seasons 2023 and 2024**, reported separately and pooled. No quantity computed
  on 2023 or 2024 was ever consulted during selection.
- Two nuisance constants that could have leaked were also fit on the selection seasons only
  and then frozen: the home/away multipliers (`[home-mult frozen on 2021-2022]` in the log)
  and the mean-possessions normaliser (82.054).
- **Eval universe:** `minutes > 0` and `n_prior >= 3` prior played games in the same season,
  so every estimator family is defined on exactly the same rows. 16,345 rows total;
  4,435 in 2023 and 4,447 in 2024. This gate matches the incumbent's own gate in
  `props_edge.py` ("Gate: >= 3 PRIOR played appearances in that season").

## Estimator family built (all strictly shifted)

Every estimate for game *t* is computed from a series that has already been `.shift(1)`-ed
within `(player_id, season)`, so game *t* can never enter its own feature. 365 configs per
counting-stat target, 65 for minutes.

| family | form |
|---|---|
| `STD_expanding` | season-to-date mean of the per-game total — **the naive default** |
| `ROLL_w{1,3,5,10,20}` | fixed-window rolling mean of the total |
| `TOT_a{α}` | EWMA of the per-game total, α ∈ {.05,.08,.10,.15,.20,.25,.30,.40,.50,.70} |
| `PER36_a{αr}_m{αm}` | **EWMA of the per-36 rate** × EWMA of minutes / 36 — the incumbent's form |
| `RATE36_a{αr}_m{αm}` | ratio of EWMAs: EWMA(stat)/EWMA(min) × EWMA(min) |
| `PER100_/RATE100_a{αr}_p{αp}` | same two forms on per-100-**possessions** rates |
| `CTX_*`, `PER36CTX_*`, `RATE36CTX_*`, `CTXROLL_*` | context-normalized twins of the above |
| `SHRINK_a{α}_k{2,5,10}` | prior-season shrunk: (n·EWMA + k·prior-season mean)/(n+k) |
| `NEG_reversed`, `NEG_league_const`, `NEG_other_player` | negative controls |

`αr` is the **efficiency/rate** horizon, `αm`/`αp` the **exposure** horizon. Sweeping them
independently (a 10×10 grid) is what turned out to matter. Note the algebraic degeneracy:
`RATE36_a_m` with `αr == αm` collapses exactly to `TOT_a`, so only the off-diagonal cells of
that family are distinct objects. `PER36` (EWMA of the ratio) does **not** degenerate, because
an EWMA of a ratio is not the ratio of EWMAs — this distinction is what makes `PER36` a
faithful reproduction of the incumbent rather than a plain EWMA in disguise.

### The two declared reference points

- **NAIVE** = `STD_expanding`, the season-to-date mean.
- **INCUMBENT** = `PER36_a0.30_m0.30`, reproducing `props_edge.py` exactly:
  `proj = EWMA_0.30(pts/minutes*36) × EWMA_0.30(minutes) / 36`, gate ≥3 prior played games.
  `props_edge.py:203` — `ALPHA = 0.30  # registered frozen family`. The same 0.30 appears as
  `MINUTES_ALPHA = 0.30` in `daily_forecast.py:112` and `EWMA_ALPHA = 0.30` in
  `minutes_twostage.py:83` / `cbs_real_frames.py:83`.

**A first-pass version of this screen coded the incumbent as a ratio-of-EWMAs and it silently
collapsed to `TOT_a0.30`.** That would have mis-stated the gap. It was caught by reading
`props_edge.py` lines 13-23 and 312-350 rather than trusting the summary, and the faithful
`PER36` arm was added and everything rerun. The numbers below are from the corrected run.

### Prior-season handling (a real design choice, documented)

Prior-season mean = that player's mean of the stat over the whole preceding season, which is
complete before the current season starts, so no leakage. Players with no preceding season
**inside the partition** — which includes *every* 2021 row and all rookies — fall back to the
selection-season league mean of the stat. That fallback is crude, and it is the most likely
reason the shrinkage family underperforms; see the honest caveat in the verdicts.

## Results — estimator comparison, per target, per scored season

Full table: `all_estimator_metrics.csv` (8,240 rows). Best-per-family, selected on 2021-22:
`family_scored.csv`. Skill = % MAE reduction vs `STD_expanding`.

### points
| family | selected on 2021-22 | sel MAE | 2023 MAE | 2024 MAE | pool RMSE | skill 23 | skill 24 |
|---|---|---|---|---|---|---|---|
| RATE36CTX | `a0.05_m0.25` | 4.0531 | 4.0818 | 4.0181 | 5.3326 | +0.51% | +2.15% |
| PER36CTX | `a0.05_m0.25` | 4.0563 | 4.0673 | 4.0036 | 5.3467 | +0.86% | +2.51% |
| RATE36 | `a0.05_m0.20` | 4.0583 | 4.0776 | 4.0462 | 5.3560 | +0.61% | +1.47% |
| RATE100 | `a0.05_p0.25` | 4.0587 | 4.0749 | 4.0437 | 5.3595 | +0.68% | +1.53% |
| PER36 | `a0.05_m0.20` | 4.0621 | 4.0642 | 4.0316 | 5.3709 | +0.94% | +1.83% |
| PER100 | `a0.05_p0.20` | 4.0630 | 4.0615 | 4.0274 | 5.3710 | +1.00% | +1.93% |
| CTX | `a0.10` | 4.0704 | 4.0888 | 4.0426 | 5.3510 | +0.34% | +1.56% |
| TOT | `a0.10` | 4.0747 | 4.0851 | 4.0673 | 5.3754 | +0.43% | +0.96% |
| ROLL | `w10` | 4.0968 | 4.1278 | 4.1038 | 5.4235 | −0.61% | +0.07% |
| SHRINK | `a0.15_k2` | 4.1028 | 4.1121 | 4.0977 | 5.3601 | −0.23% | +0.21% |
| **STD_expanding (naive)** | — | 4.1176 | 4.1027 | 4.1065 | 5.4071 | 0.00% | 0.00% |
| NEG_reversed | — | 4.4701 | 4.4115 | 4.5172 | 5.8932 | −7.53% | −10.00% |

### rebounds
| family | selected | sel MAE | 2023 | 2024 | pool RMSE | skill 23 | skill 24 |
|---|---|---|---|---|---|---|---|
| RATE36CTX | `a0.05_m0.30` | 1.8031 | 1.7711 | 1.7640 | 2.3515 | +1.42% | +2.17% |
| RATE100 | `a0.05_p0.30` | 1.8055 | 1.7671 | 1.7580 | 2.3481 | +1.64% | +2.51% |
| RATE36 | `a0.05_m0.30` | 1.8077 | 1.7683 | 1.7600 | 2.3483 | +1.57% | +2.40% |
| PER100 | `a0.05_p0.30` | 1.8092 | 1.7691 | 1.7558 | 2.3550 | +1.53% | +2.63% |
| PER36 | `a0.05_m0.30` | 1.8124 | 1.7710 | 1.7582 | 2.3552 | +1.42% | +2.50% |
| TOT | `a0.10` | 1.8224 | 1.7765 | 1.7807 | 2.3614 | +1.11% | +1.25% |
| SHRINK | `a0.15_k2` | 1.8228 | 1.7753 | 1.7858 | 2.3506 | +1.18% | +0.97% |
| ROLL | `w20` | 1.8334 | 1.7931 | 1.7961 | 2.3835 | +0.19% | +0.39% |
| **STD_expanding (naive)** | — | 1.8418 | 1.7965 | 1.8032 | 2.3897 | 0.00% | 0.00% |
| NEG_reversed | — | 1.9894 | 1.9879 | 1.9827 | 2.6420 | −10.65% | −9.95% |

### assists
| family | selected | sel MAE | 2023 | 2024 | pool RMSE | skill 23 | skill 24 |
|---|---|---|---|---|---|---|---|
| RATE100 | `a0.05_p0.30` | 1.2188 | 1.2055 | 1.1985 | 1.6403 | +1.82% | +2.20% |
| RATE36 | `a0.05_m0.30` | 1.2192 | 1.2062 | 1.1993 | 1.6400 | +1.76% | +2.13% |
| RATE36CTX | `a0.05_m0.30` | 1.2221 | 1.2112 | 1.1970 | 1.6392 | +1.35% | +2.32% |
| PER100 | `a0.05_p0.40` | 1.2223 | 1.2053 | 1.2024 | 1.6478 | +1.83% | +1.88% |
| PER36 | `a0.05_m0.40` | 1.2229 | 1.2059 | 1.2033 | 1.6478 | +1.79% | +1.81% |
| TOT | `a0.08` | 1.2311 | 1.2180 | 1.2054 | 1.6491 | +0.80% | +1.63% |
| **STD_expanding (naive)** | — | 1.2353 | 1.2278 | 1.2255 | 1.6654 | 0.00% | 0.00% |
| ROLL | `w20` | 1.2368 | 1.2256 | 1.2159 | 1.6615 | +0.19% | +0.78% |
| SHRINK | `a0.08_k2` | 1.2370 | 1.2265 | 1.2099 | 1.6384 | +0.11% | +1.27% |
| NEG_reversed | — | 1.3244 | 1.3095 | 1.3669 | 1.8346 | −6.65% | −11.54% |

### minutes
| family | selected | sel MAE | 2023 | 2024 | pool RMSE | skill 23 | skill 24 |
|---|---|---|---|---|---|---|---|
| CTX | `a0.30` | 4.8640 | 4.6728 | 4.7008 | 6.1164 | +7.79% | +9.86% |
| TOT | `a0.30` | 4.8640 | 4.6726 | 4.7009 | 6.1161 | +7.79% | +9.85% |
| SHRINK | `a0.30_k2` | 4.9643 | 4.7561 | 4.8114 | 6.1365 | +6.15% | +7.74% |
| ROLL | `w5` | 4.9996 | 4.8347 | 4.8265 | 6.3271 | +4.60% | +7.45% |
| **STD_expanding (naive)** | — | 5.1954 | 5.0675 | 5.2147 | 6.6752 | 0.00% | 0.00% |
| NEG_reversed | — | 6.0106 | 5.9471 | 6.3214 | 7.9983 | −17.36% | −21.22% |

## THE GAP — tuned vs the naive default vs the program incumbent

`gap_table.csv`. **The gap depends enormously on which baseline you mean, and this is the
single most important thing in this screen.**

| target | tuned pick | vs NAIVE 2023 | vs NAIVE 2024 | vs INCUMBENT 2023 | vs INCUMBENT 2024 |
|---|---|---|---|---|---|
| pts | `RATE36CTX_a0.05_m0.25` | **+0.51%** | +2.15% | **+2.53%** | **+3.11%** |
| reb | `RATE36CTX_a0.05_m0.30` | +1.42% | +2.17% | **+2.79%** | **+2.76%** |
| ast | `RATE100_a0.05_p0.30` | +1.82% | +2.20% | **+3.91%** | **+2.65%** |
| minutes | `CTX_a0.30` | +7.79% | +9.86% | **−0.00%** | **+0.00%** |

Two facts drive everything:

1. **The program's incumbent is worse than a season-to-date mean on all three counting
   stats.** `PER36_a0.30_m0.30` scores 4.1878 / 4.1470 MAE on points (2023/2024) against the
   naive mean's 4.1027 / 4.1065; rebounds 1.8218 / 1.8141 vs 1.7965 / 1.8032; assists
   1.2546 / 1.2311 vs 1.2278 / 1.2255. **It loses to the naive baseline in every scored
   season on every counting stat.** The untuned α = 0.30 is not merely suboptimal, it is on
   the wrong side of the naive default.
2. **For minutes the incumbent is already exactly optimal.** The tuned selection on 2021-22
   independently landed on α = 0.30 — the value already frozen in `daily_forecast.py` and
   `minutes_twostage.py`. Gap vs incumbent is 0.00% (bootstrap win share 0.386 / 0.594, i.e.
   a coin flip). The +8.8% is entirely a gap over the *naive* mean, which the program was
   never using for minutes.

### Gap stability (descriptive, NOT a significance test)

`gap_bootstrap.csv` — 1,000 resamples of **players** (clustered) with replacement, per scored
season. Reported to answer discipline 4 ("is this too noisy to distinguish?"), not to make a
significance claim.

| target | 2023 vs naive | 2024 vs naive | 2023 vs incumbent | 2024 vs incumbent |
|---|---|---|---|---|
| pts | +0.021 [−0.007,+0.047] win .883 | +0.088 win 1.000 | +0.106 [+0.074,+0.138] win 1.000 | +0.129 win 1.000 |
| reb | +0.026 [+0.008,+0.043] win .994 | +0.039 win 1.000 | +0.051 win 1.000 | +0.050 win 1.000 |
| ast | +0.022 [+0.012,+0.034] win 1.000 | +0.027 win 1.000 | +0.049 win 1.000 | +0.033 win 1.000 |
| minutes | +0.395 win 1.000 | +0.514 win 1.000 | −0.000 [−0.001,+0.001] win .386 | +0.000 win .594 |

The one wobble: **points, 2023, vs the naive mean** — the interval crosses zero (win share
0.883). Against the incumbent it does not, in either season. So the honest statement is
"tuning clearly beats what the program currently runs; whether it beats a season-to-date mean
on points is not resolved by 2023 alone".

### Is the tuned horizon real, or just the edge of my grid?

The selected efficiency alpha came out at **0.05, the floor of the main grid** — a tuned
value sitting on its own boundary is not a tuned value. `boundary_check.py` extends the
efficiency grid down to 0.01 and adds the expanding mean of the rate (α→0), holding the
exposure alpha at the selected value:

| efficiency α | pts sel | pts 2023 | pts 2024 | reb sel | ast sel |
|---|---|---|---|---|---|
| 0.01 | 4.0662 | 4.0650 | 4.0312 | 1.8127 | 1.2220 |
| 0.03 | 4.0639 | 4.0641 | 4.0307 | 1.8123 | 1.2222 |
| **0.05** | **4.0625** | 4.0648 | 4.0320 | 1.8124 | 1.2229 |
| 0.10 | 4.0668 | 4.0736 | 4.0422 | 1.8163 | 1.2270 |
| 0.20 | 4.1049 | 4.1155 | 4.0827 | 1.8334 | 1.2426 |
| **0.30 (incumbent)** | **4.1663** | 4.1821 | 4.1430 | 1.8592 | 1.2651 |
| α→0 (expanding) | 4.0677 | 4.0660 | 4.0320 | 1.8131 | 1.2221 |

0.05 is an **interior minimum of a very flat basin**: anything in 0.01-0.08 is within 0.004
MAE. So the precise tuned value is not the finding and should not be treated as one. The
finding is the **shape**: the curve is flat below ~0.08 and climbs steeply above ~0.10, and
the incumbent's 0.30 sits well up the wrong side of it.

## The normalization contrast — the actual thesis test

`normalisation_contrast.csv`. Matched pairs: the identical estimator with and without
context normalization (pace from derived team possessions, home/away, and a leave-one-out
opponent-allowed factor built only from games strictly before *t*). Negative Δ = helps.

| target | Δ MAE 2023 | Δ MAE 2024 | verdict |
|---|---|---|---|
| pts | **+0.002 to +0.017 (HURTS)** | −0.018 to −0.031 (helps) | sign flips by season |
| reb | +0.002 to +0.007 (hurts) | +0.003 to +0.018 (hurts) | hurts in both |
| ast | +0.004 to +0.010 (hurts) | −0.002 to +0.008 (mixed) | hurts in 2023, ~flat 2024 |
| minutes | +0.0002 (≈0) | +0.0001 (≈0) | identically nothing |

**Context normalization does not survive the persistence bar.** It never exceeds ±0.34% of
MAE, it flips sign between the two scored seasons on points, and it is negative in both
seasons on rebounds. The pts winner `RATE36CTX_a0.05_m0.25` was selected partly on a ctx
component that this matched-pair contrast shows is not persistent — the non-ctx twins
(`PER36_a0.05_m0.20` = 4.0642/4.0316, `PER100_a0.05_p0.20` = 4.0615/4.0274) are as good or
better on the scored seasons. **The recommended configuration is therefore the non-ctx one.**

**Honest limitation on this null (discipline 4).** This is a null through a *coarse*
construction, and I will not sell it as a clean negative for the thesis. Specifically:
the home/away multipliers came out at 1.0046 / 0.9954 for points — a 0.5% effect, i.e. home
court is essentially nothing at the player-game level, so that channel could not contribute.
The opponent factor is **team-level points/rebounds/assists allowed**, which is far too coarse
to capture a matchup; and it is clipped to [0.85, 1.15] and forced to 1.0 for the first 5
team games. The pace factor is the only one with real variance. So the correct reading is:
**cheap, coarse, league-average context normalization buys nothing** — not "context does not
matter". A per-position or per-archetype opponent-allowed factor is a different and untested
object.

## Heterogeneity — the pre-declared slices, all of them

Declared in `PRE_DECLARED_SLICES.md` before `score.py` was written. Best α re-selected
**within each slice on 2021-22 only**, then scored in-slice on 2023 and 2024 separately.
Family held fixed at `TOT` (raw EWMA of the total) so the α is comparable across slices.
`heterogeneity.csv`. All 13 slices ran on all 4 targets; all 52 cells are reported.

Selected α by slice (the headline of this section):

| slice | pts | reb | ast | minutes |
|---|---|---|---|---|
| S1 starter = 1 | 0.08 | 0.05 | 0.05 | 0.25 |
| S1 starter = 0 | **0.15** | **0.20** | **0.10** | **0.30** |
| S2 minutes < 15 | 0.15 | 0.15 | 0.15 | 0.30 |
| S2 minutes 15-25 | 0.15 | 0.20 | 0.10 | 0.30 |
| S2 minutes ≥ 25 | **0.08** | **0.05** | **0.05** | **0.20** |
| S3 usage low | 0.15 | 0.15 | 0.10 | 0.40 |
| S3 usage mid | 0.15 | 0.15 | 0.10 | 0.30 |
| S3 usage high | **0.08** | **0.08** | **0.05** | **0.20** |
| S4 n_prior 3-7 | 0.08 | 0.20 | 0.05 | 0.30 |
| S4 n_prior 8-19 | 0.08 | 0.10 | 0.08 | 0.25 |
| S4 n_prior ≥ 20 | 0.15 | 0.10 | 0.08 | 0.30 |
| S5 regular season | 0.10 | 0.10 | 0.05 | 0.30 |
| S5 playoffs | 0.15 | 0.15 | 0.15 | 0.25 |

**This is the one part of the hypothesis that clearly holds.** In S1, S2 and S3 — three
independently-defined role cuts — the ordering is the same on all four targets:
**high-role players (starters, ≥25 min, high usage) want a slower estimator; low-role players
(bench, <15 min, low usage) want a faster one**, typically 2-3× the alpha. That the same
direction appears in 12 of 12 target×slice-family combinations is what makes it look like
signal rather than slicing noise. The mechanism is unsurprising in hindsight: a bench
player's role changes discretely and often, so old games are genuinely stale; a starter's
does not, so more history is more information.

Skill vs naive is also much larger in the low-role slices — e.g. rebounds, bench:
+2.86% / +2.44% (2023/2024) vs starters +0.60% / +0.75%; assists, 15-25 min:
+2.03% / +5.10% vs ≥25 min +0.12% / +0.27%.

**The boring slices, reported as required.** S4 (history depth) shows no clean monotone
pattern — α wanders 0.05→0.20→0.10 on rebounds with no interpretable ordering, and the
n_prior 3-7 cell is the one place skill goes slightly *negative* on both pts (+0.08%/+0.07%,
i.e. nothing) and ast (−0.03%/−0.25%). S5 (playoffs) shows large skill numbers
(reb +5.07% in 2023 but −0.27% in 2024; ast +0.09% then +5.06%) on n = 354 / 397 — these
**swing wildly between the two scored seasons and should be read as noise, not as a playoff
effect**. Minutes in playoffs (+13.31% / +11.43%) is the only playoff cell consistent across
both seasons.

### Does the best horizon differ by stat?

**No, not meaningfully — and this part of the hypothesis should be dropped.** The efficiency
horizon is 0.03-0.05 for points, rebounds *and* assists, all inside the same flat basin
(boundary check above). The exposure horizon is 0.20-0.25 for points and 0.30 for rebounds
and assists — a difference smaller than the flatness of the curve. What genuinely differs is
**channel** (efficiency ≈ season-to-date vs exposure ≈ α 0.25-0.30, a 6-10× separation) and
**role** (table above). "By stat" was the wrong axis.

## Early-season / prior-season shrinkage

`early_season.csv`, evaluated on `n_prior ∈ {1,2}` (n = 306 in 2023, 307 in 2024), outside the
main eval universe. Shrinkage toward the prior-season mean **helps nowhere except marginally
on rebounds** (`SHRINK_a0.30_k2`: 1.8540 / 1.8919 vs naive 1.8693 / 1.8974) and is actively
harmful at k = 5 and k = 10 on every target. On minutes it is a disaster (5.95 / 6.07 vs
naive 5.13 / 4.70).

I do **not** read this as "prior-season information is useless". The fallback described
above — league mean for every player without a preceding partition season, which is all of
2021 and every rookie — is crude enough to explain the result on its own, and n ≈ 300 per
scored season is thin. This is a **badly-measured comparison, not a negative**.

## Negative control

`negative_control_ranking.csv`. Three controls, pre-declared. Pooled 2023+2024 MAE, ranked
against every family winner:

| target | NEG_reversed | NEG_league_const | NEG_other_player | rank of the 3 controls |
|---|---|---|---|---|
| pts | 4.4644 | 6.2808 | 7.8156 | 11, 12, **13 of 13** |
| reb | 1.9853 | 2.6149 | 3.1046 | 11, 12, **13 of 13** |
| ast | 1.3382 | 1.7517 | 2.2015 | 11, 12, **13 of 13** |
| minutes | 6.1345 | 9.4875 | 12.7998 | 8, 9, **10 of 10** |

**`NEG_other_player` ranks dead last on all four targets**, `NEG_league_const` second-last,
and `NEG_reversed` — the subtlest control, same history with recency weights inverted — ranks
below *every* real estimator on all four targets while still beating the two cruder controls.
The harness orders all three controls correctly and by the expected severity. It detects
deliberately broken estimators.

## Verdicts

- **points — `keep-as-lead`.** Beating the incumbent by +2.53% / +3.11% MAE is persistent
  across both scored seasons with bootstrap win share 1.000, and the incumbent loses to a
  season-to-date mean in both seasons, which is a defect worth fixing on its own. Held back
  from anything stronger because the gap over the *naive* mean is +0.51% in 2023 with a
  bootstrap interval crossing zero.
- **rebounds — `keep-as-lead`.** +2.79% / +2.76% vs incumbent and +1.42% / +2.17% vs naive,
  same sign both scored seasons, bootstrap win share ≥0.994 on all four comparisons. The
  cleanest of the four.
- **assists — `keep-as-lead`.** +3.91% / +2.65% vs incumbent, +1.82% / +2.20% vs naive, win
  share 1.000 on all four comparisons.
- **minutes — `kill`.** The hypothesis is that a *tuned* horizon beats the untuned baseline.
  For minutes the tuned horizon **is** the baseline: selection on 2021-22 independently
  recovered α = 0.30, the value already frozen in the program, and the gap is 0.00% with a
  coin-flip win share. Context normalization is identically zero here. There is nothing to
  win by tuning the minutes horizon; that lane is already correct. (This is a kill for
  *I0011 on minutes*, emphatically **not** a statement that minutes projection is solved —
  see the flag below.)
- **the context-normalization arm — `kill` as constructed.** Never beyond ±0.34% MAE, sign
  flips between scored seasons, negative in both seasons on rebounds. Killed as a cheap
  coarse construction; the thesis that context matters is untouched by this, because the
  construction tested was too blunt to carry it (see the limitation note above).

**Blunt summary for the program: tuning the horizon buys ~2-3% MAE, and essentially all of it
comes from one specific error — using a single common alpha for both the efficiency channel
and the exposure channel.** Efficiency wants near-season-to-date memory (α ≈ 0.03-0.05);
exposure wants α ≈ 0.25-0.30. The incumbent runs 0.30 on both, which over-weights recency on
the efficiency channel badly enough that it loses to a season-to-date mean. The fix is a
one-line change to a frozen constant, not a modelling programme. Context normalization, which
is the more interesting half of the hypothesis, bought nothing at this construction quality.

## Noticed but NOT tested — candidate ideas, not findings

Flagging these as leads for the coordinator; none of them was investigated here.

1. **`master_player.pace` looks corrupt.** On the 2021-2024 partition it ranges 0 to 7200
   with a mean of 84.7 against a median of 96.1. I avoided the column entirely and derived
   possessions from `master_team` instead. If any lane consumes `pace` from
   `master_player`, that is a data-integrity ticket, not an idea.
2. **`master_player.position` is unusable.** Empty on 55% of partition rows (11,762 of
   21,462), and the non-empty values are exactly 3,880 F / 3,880 G / 1,940 C — suspiciously
   round and exactly proportional to team-games, which suggests a placeholder fill rather
   than real position data. This blocks any position-based work, including a per-position
   opponent-allowed factor.
3. **A per-position or per-archetype opponent-allowed factor** is the obvious next version of
   the context arm. My null is on team-level allowed rates only, and I clipped them to
   [0.85,1.15]; that is where I would look before concluding anything about context.
4. **Rest days, back-to-backs, and travel are not built anywhere I looked**, and they are
   free pregame-observables. For the *exposure* channel specifically they are more plausible
   than pace, which is the channel where the tuning gains actually live.
5. **The exposure channel dominates the error budget.** Minutes MAE is ~4.69 against a mean of
   21.4 minutes — a ~22% error on the quantity every counting stat is multiplied through.
   That is an order of magnitude larger than the 2-3% the estimator tuning recovers. If the
   program wants a big number, it is here, and I0011 says the current EWMA is already the best
   *EWMA* — which implies the next gain has to come from a different kind of model
   (role/rotation/injury-aware), not a better-tuned average.
6. **`minutes_twostage.py` already separates the two stages** and carries both
   `EWMA_ALPHA = 0.30` and `TEAM_ALPHA = 0.10`. Worth checking whether that lane's two stages
   already use different alphas by accident, in which case part of this finding may already be
   half-implemented somewhere in the repo.
7. **Playoff minutes** was the only playoff cell consistent across both scored seasons
   (+13.31% / +11.43% skill). Small n (354/397) and I would not touch it, but it is the one
   playoff signal that did not swing.

## Artifacts

`experiments/exploration/E0_I0011_tendency_estimator/`:
`eda.py`, `build_frame.py`, `score.py`, `boundary_check.py`, `verify_partition.py`,
`PRE_DECLARED_SLICES.md`, `frame.parquet`, `all_estimator_metrics.csv`,
`family_selections.csv`, `family_scored.csv`, `gap_table.csv`, `gap_bootstrap.csv`,
`normalisation_contrast.csv`, `heterogeneity.csv`, `negative_control_ranking.csv`,
`early_season.csv`, `boundary_check.csv`, `run_log.txt`, `run_log_boundary.txt`,
`run_log_verify.txt`, `NOTES.md` (this file).

Deterministic: `SEED = 20260807` set in `build_frame.py` and `score.py`; the bootstrap uses
`default_rng(SEED + season)`. Rerun order: `build_frame.py` → `score.py` →
`boundary_check.py` → `verify_partition.py`.
