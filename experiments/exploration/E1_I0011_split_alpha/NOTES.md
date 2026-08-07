# E1 I0011 — does the split-alpha advantage persist out-of-sample?

**This is an E1 signal-candidate screen. Its output is a LEAD, never a RESULT.**
No registry entry, no preregistration, no leaderboard row, no bootstrap significance claim,
no promotion threshold. Per GRAPH_POLICY §13 the headline is a one-line kill/keep verdict per
target and nothing stronger.

---

## Headline

| target | verdict |
|---|---|
| **points** | `keep-as-lead` **(ATTENUATED)** |
| **rebounds** | `keep-as-lead` |
| **assists** | `keep-as-lead` |

**Did the advantage persist out-of-sample, or was it a single-split artifact?**
**It persisted — decisively — but it is not the effect E0 said it was.**

The E0 selected on 2021–22 and scored on 2023–24: one split. E1 ran **11 folds across three
protocols** and the split-alpha configuration beat the program incumbent in **33 of 33**
target × fold combinations. That is not a single-split artifact.

But E0's headline number confounded two different things, and separating them is the main
content of this screen:

> **62–88% of the "+2.5 to +3.9% vs incumbent" is just retuning α at all. Only the
> remaining 12–38% is attributable to giving the two channels *different* αs**
> — 12–14% on points, 31–38% on rebounds, 18–24% on assists.

| target | total gap vs incumbent (mean by protocol) | of which: retuning a **single** common α | of which: **splitting** the channels |
|---|---|---|---|
| pts | +2.69 / +2.91 / +3.22 % | +2.37 / +2.51 / +2.76 % | **+0.33 / +0.41 / +0.48 %** |
| reb | +2.71 / +2.80 / +3.03 % | +1.88 / +1.89 / +1.89 % | **+0.85 / +0.93 / +1.16 %** |
| ast | +3.17 / +3.40 / +3.58 % | +2.42 / +2.57 / +2.92 % | **+0.68 / +0.85 / +0.68 %** |

Protocols in order: P1 leave-one-season-out / P2 walk-forward / P3 within-season halves.

Both facts matter, and they point in different directions:

- For the **program**, the actionable finding is unchanged and if anything strengthened:
  `ALPHA = 0.30` is wrong on the efficiency channel, and fixing it is worth ~2.7–3.2% MAE
  on all three counting stats, in every fold, in every protocol.
- For the **hypothesis** `F_TENDENCY_ESTIMATOR` — specifically the claim that the *channels*
  need separate horizons — the surviving effect is **much smaller than E0 implied**:
  +0.3% (pts), +0.9% (reb), +0.7–0.9% (ast).

**Why points is downgraded to ATTENUATED.** Its split-specific increment (+0.33 to +0.48%) is
smaller than its own across-fold sd (0.19–0.44). It is positive in 11 of 11 folds, which is
why it is not killed, but a mean under one fold-sd is not something to build on. For points,
"α = 0.30 is wrong" is the finding; "the two channels need different αs" is barely detectable.

---

## Method

### The decisive contrast, and why E0 could not see it

E0 compared a tuned split-α estimator against the **untuned** incumbent (α = 0.30 on both
channels). That comparison cannot distinguish "splitting the channels helped" from "tuning
anything at all helped." E1 adds the missing arm:

- `SINGLE_tuned` — the best `PER36` cell **constrained to `alpha_eff == alpha_exp`**, tuned on
  the same training pool, in the same family, over the same grid diagonal.
- `SPLIT_tuned` — the best `PER36` cell over the full 14×14 grid.

`SPLIT_tuned vs SINGLE_tuned` isolates the split. Everything else is held fixed. That contrast
is the actual E1 question and it is the one reported above.

### Arms

| arm | definition | tuned per fold? |
|---|---|---|
| `INCUMBENT` | `PER36` α_eff = α_exp = 0.30 — `props_edge.py` | no |
| `NAIVE` | season-to-date mean of the raw total | no |
| `FROZEN_SPLIT` | `PER36` α_eff = 0.03, α_exp = 0.30 — fixed a priori | no |
| `TOT_tuned` | best single-channel EWMA of the total | yes |
| `SINGLE_tuned` | best `PER36` cell with α_eff == α_exp | yes |
| `SPLIT_tuned` | best `PER36` cell, full grid | yes |
| `SPLITFORM` | best cell over all four two-channel forms | yes |

Forms swept: `PER36` (EWMA **of the ratio** — `props_edge.py`'s actual form), `RATE36` (ratio
of EWMAs), `PER100` / `RATE100` (possession exposure), `TOT`, `STD`. α grid: 14 values
`{0.00 (= expanding), 0.01, 0.02, 0.03, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.70}`.

**The incumbent is an EWMA OF THE RATIO, not a ratio of EWMAs.** E0 got this wrong on its first
pass; it is reproduced faithfully here (`PER36`), and the two forms are carried as separate
families so the distinction cannot collapse silently. `RATE36` with α_eff == α_exp degenerates
algebraically to `TOT_a`; `PER36` does not.

### Protocols — 11 folds

| protocol | folds | train | test |
|---|---|---|---|
| **P1 LOSO** | 4 | the other three seasons | one held-out season |
| **P2 WALKFWD** | 3 | all seasons `< s` | season `s` (2022/23/24) |
| **P3 HALF** | 4 | first half of `s` + all earlier seasons | second half of `s` |

P2 is the honest deployment analogue (nothing in train post-dates test). P1 maximises fold
count at the cost of temporal ordering. **P3 is secondary and labelled as such** — train and
test share players heavily, so it tests "does the α choice transfer forward in time" and not
much more. All three are reported separately; nothing is pooled into a single number.

### Effect sizes are reported with across-fold variability, never pooled

Every gap in `fold_summary.csv` carries `mean / sd / min / max / n_folds_positive` over its
protocol's folds. A pooled single number would hide exactly the thing E1 exists to measure.

### Evaluation is matched-pair by construction

Estimators were evaluated once into a tidy metric table keyed by atomic cell
(season × half × slice), and every fold is an n-weighted pool of those cells. Consequence:
**no estimator is ever recomputed, and every estimator is defined on exactly the same rows in
every cell** — asserted, 0 of 132 cells show `n` varying across estimators. Eval gate is
`minutes > 0` and `n_prior >= 3`, identical to `props_edge.py`'s registered gate:
16,345 rows (3,433 / 4,030 / 4,435 / 4,447 by season).

### Independent reproduction of E0

The frame was rebuilt from `master_player.parquet` without reusing E0's `frame.parquet`, and
reproduces E0's numbers to four decimals on both scored seasons — incumbent
4.1878/4.1470 (pts), 1.8218/1.8141 (reb), 1.2546/1.2311 (ast); naive 4.1027/4.1065,
1.7965/1.8032, 1.2278/1.2255. Row counts match exactly (4,435 / 4,447). E0's measurement
is not in doubt; only its interpretation is revised.

---

## The exploration partition

Seasons **2021–2024 only**. The 2025/2026 confirmation holdout was **never** read, joined,
plotted, filtered against, counted or described. **No partition incident occurred.**

**Manifest gate (§13.2.2)** is enforced *in code*, not asserted in prose: `build_frame.py`
reads `master_player.parquet.manifest.json` and hard-exits unless
`asof_granularity == "row"`. It is `"row"`, `bound_source` is
`"game_date via asof_invariant.bound_from_dates"` — so each row is bounded by its own date and
**filtering to 2021–2024 is sufficient**. `fit_through_season: 2026` records only which seasons
the file *contains* and does not make it unusable. The filter is applied on the line
immediately following `read_parquet`, before any join or computation.

`master_team.parquet` was **not used at all** — the context-normalization arm was killed at E0
and is not revisited here, so no team-derived quantity was needed.

### Verification (`verify_partition.py` → `run_log_verify.txt`)

Two checks over all 31 output files:

1. **Structural** — every output with a `season` column reloaded and its value set required to
   be ⊆ {2021,2022,2023,2024}; every date column's min/max printed.
   `frame.parquet` → `[2021,2022,2023,2024]`, `game_date` 2021-05-14 … **2024-10-20**.
   `grid_metrics.parquet` → same. **0 violations.**
2. **Targeted textual** — scans only for tokens that could actually *denote* a holdout season:
   an ISO date beginning `2025-`/`2026-`, or the digits adjacent to a season-ish word.
   3 hits, all prose in docstrings describing the partition rule itself.

**Deliberately NOT a bare byte-scan.** A previous coordinator in this program produced a false
partition violation by scanning raw bytes for `2025`/`2026` and matching digit runs inside
floats and row counts that happened to equal 2026. §13.2.2 asks for **column values in
season/date columns**, and that is what is checked.

---

## What persisted

**1. The shape of the finding persisted more robustly than its size.**
In all 33 target × fold selections, `alpha_eff` landed in `[0.00, 0.10]` and `alpha_exp` in
`[0.08, 0.40]`. The exposure/efficiency ratio was ≥ 1.5 in 32 of 33 folds and ≥ 4 in 30 of 33.
The incumbent's 0.30 sits **above the selected efficiency alpha in every one of the 33**. The
qualitative claim — *efficiency wants slow memory, exposure wants fast* — is the most durable
thing in this screen.

**2. Frozen constants beat a tuner.** `FROZEN_SPLIT` (0.03 / 0.30), fixed a priori with no
per-fold selection, **matched or beat** per-fold re-selection on all three targets in all three
protocols. The basin is flat enough — at α_eff = 0.03, moving α_exp anywhere in 0.20–0.30
costs points at most 0.0020 MAE (0.05%) — that tuning machinery contributes only selection
variance. The corrected baseline therefore ships as
two constants, not as a fitter.

**3. The incumbent losing to a season-to-date mean persisted in all four seasons.**
Not two seasons — four.

## What did not persist

**1. Role-conditional alphas — `kill`.**
The role tiers *do* prefer different alphas, consistently: bench / `<15` min / low-usage want a
much faster **exposure** channel (0.30–0.50) than starters / `≥25` min (0.10–0.20), while the
efficiency channel sits at 0.02–0.05 in every tier. E0 saw this and it reproduces.

But E0 measured it by re-selecting α *inside* each slice and scoring *inside* that slice, which
shows the slices differ and **not** that a role-conditional estimator is better. The operational
test — choose α per tier on the training seasons, assemble one estimator, score it on the
held-out season against a global pair **on identical rows** — comes out flat:

- mean gap spans **−0.219% to +0.172%** across all 18 target × family × protocol cells;
- across-fold sd is **at least as large as |mean| in 17 of 18**;
- **not one** of the 18 cells has every fold positive.

Three independently-defined role families (starter flag, prior-minutes tier, usage tercile) all
agree that role-conditioning buys nothing. **E0's role heterogeneity is real as a description
and worthless as an estimator upgrade.** Recorded in the spec as a tested-and-rejected option
so the next screen does not spend budget on it.

**2. The per-100-possessions exposure variant — partial keep, not adopted.**
Using `EWMA(possessions)` as the exposure channel beat the minutes form on rebounds
(+1.00/+1.07/+1.47% vs a tuned common α) and assists (+1.07/+0.98/+0.81%), but **sign-flipped
on points in 2 of 11 folds**. Not carried into the baseline: it adds a data dependency for a
gain inside the across-fold sd. Flagged as a live minor variant for rebounds specifically.

**3. Points' split-specific effect is marginal**, as above.

---

## Negative controls and the no-op placebo

Pooled 2021–2024 eval universe, **40 seeds** per permutation control.

### The no-op diagnostic — run on purpose

The defect this program has seen before: a placebo that permutes a **grouping key** and then
**recomputes the aggregate** from the permuted key is a **no-op**. Permuting a label is a
bijection on labels, so the permuted cell is the same row set under a new name and every row
still gets its own true value.

`NOOP_regroup` implements exactly that defect and was run deliberately as a calibration:

| target | `NOOP_regroup` MAE | sd over 40 seeds | the real naive MAE | delta |
|---|---|---|---|---|
| pts | 4.110515 | **0.000000** | 4.110515 | +0.000000000 |
| reb | 1.819030 | **0.000000** | 1.819030 | +0.000000000 |
| ast | 1.230611 | **0.000000** | 1.230611 | +0.000000000 |

**The documented signature reproduces exactly.** That is the calibration against which the
controls actually used are shown to be non-degenerate.

### The controls actually used — correct form (permuted *assignment*), sds reported

| control | pts MAE (sd) | reb MAE (sd) | ast MAE (sd) |
|---|---|---|---|
| `NEG_other_player` — a different player's season-to-date series assigned to these rows | 7.3999 (**0.124380**) | 3.1000 (**0.046442**) | 2.0681 (**0.033702**) |
| `NEG_channel_scramble` — own efficiency state × a **different player's** exposure state | 5.6924 (**0.070305**) | 2.5409 (**0.031003**) | 1.5851 (**0.020052**) |

Both have **non-degenerate spread**. `NEG_channel_scramble` is new here and is aimed squarely
at this lead: if the split-α advantage were an artefact of the arithmetic rather than of
genuinely player-specific exposure, scrambling whose minutes-EWMA gets multiplied in would not
hurt. It hurts enormously (+40% MAE on points).

`NEG_reversed` (4.4483 / 1.9751 / 1.3263) and `NEG_league_const` (6.1110 / 2.5748 / 1.7387) are
**deterministic** — they involve no permutation, so their sd is 0 **by construction**, which is
not the no-op signature and is labelled as such in `placebo.csv`.

### Ranking — carried forward from E0 and reproduced

Pooled 2021–2024, worst last. Identical severity ordering to E0:

```
pts: corrected 4.0569 < naive 4.1105 < incumbent 4.1690
     < NEG_reversed 4.4483 < NEG_channel_scramble 5.6924
     < NEG_league_const 6.1110 < NEG_other_player 7.3999
```

`NEG_other_player` ranks **dead last on all three targets**, `NEG_league_const` second-last,
`NEG_reversed` — the subtlest control — below every real estimator while still beating the
cruder controls. Every control ranks below every real estimator. The harness detects
deliberately broken estimators.

---

## Addendum for COORDINATOR #04 — is I0009 sitting on the same baseline?

**One line: MATERIALLY DIFFERENT, and the direction depends on which of I0009's two baselines
is the headline.** Full numbers in `i0009_baseline_delta.csv` / `.json`.

| baseline | pts R² | reb R² | ast R² | ΔR² (corrected − this) |
|---|---|---|---|---|
| leave-one-out full-season rate (`player_tendency_loo`) | 0.5129 | 0.4936 | 0.4947 | **−0.0201 / −0.0137 / −0.0199** |
| expanding season-to-date total | 0.4873 | 0.4645 | 0.4663 | **+0.0055 / +0.0153 / +0.0085** |
| expanding **both** channels | 0.4831 | 0.4618 | 0.4637 | **+0.0097 / +0.0180 / +0.0110** |
| **corrected baseline** | **0.4928** | **0.4799** | **0.4748** | — |
| `props_edge.py` incumbent | 0.4604 | 0.4465 | 0.4364 | +0.0324 / +0.0334 / +0.0384 |

**The prior reasoning is half right, and the conclusion does not follow.** The premise is
confirmed: the *efficiency* channel does want α ≈ 0.03, which is very nearly a season-to-date
mean. But the entire I0011 finding is that the *exposure* channel does **not** — it wants 0.30,
a ~10× separation. A single-horizon season rate gets the efficiency channel about right and the
exposure channel wrong. The clean test is `EXPANDING_BOTH`, which differs from the corrected
baseline **only in α_exp**: it loses by ΔR² 0.0097 / 0.0180 / 0.0110 and 1.25 / 1.92 / 1.57%
MAE. So "I0009 may already be sitting on approximately the endorsed baseline" is **not**
supported.

Direction of revision:

- **If I0009's headline is vs an expanding / shrunk tendency → revise DOWN**, by at most
  ΔR² 0.0055 (pts) / 0.0153 (reb) / 0.0085 (ast). That is an **upper bound on absorption** and
  is only realised to the extent the opponent-pressure signal is correlated with minutes
  recency. If the two are near-orthogonal, little or none of it moves.
- **If I0009's headline is vs `player_tendency_loo` → do not revise down; if anything, up.**
  The leave-one-out rate is a *stronger* predictor than the corrected baseline.

**Separate integrity flag, offered to whoever owns I0009 and not acted on here.** A leave-one-out
full-season rate is **not pregame-observable**: `(season_sum − y_t)/(n−1)` reads the player's
*later* games in the same season. An increment measured over it is not a forecasting increment,
independently of how strong the baseline is. This screen did not re-run I0009 and makes no claim
about its result.

---

## Hazards hit, and observations

- **`master_player.pace`** — not read. `pace`, `pace_per40`, `estimated_pace` are dropped in
  `build_frame.py` before any use. E0's corruption report stands unchallenged.
- **`master_player.position`** — not read. Dropped in the same place.
- **`observed_time`** — dropped immediately after load and never written, so no 2026 file-mtime
  bytes reach any output. Confirmed by `verify_partition.py`.
- **`master_player.possessions` is CLEAN**, unlike `pace` — range 0–95, median 39, no nulls on
  the partition. Worth recording because the two are easy to conflate. Used only for the
  per-100 variant, which was not adopted.
- **`minutes_twostage.py` — checked as instructed, and it does NOT already implement this
  finding.** Its `EWMA_ALPHA = 0.30` / `TEAM_ALPHA = 0.10` split is by **entity** (player-level
  vs team-trait EWMAs), not by efficiency-vs-exposure. Within the player level it applies 0.30
  uniformly to `minutes`, `min_share` **and `pf_per_min`** — and `pf_per_min` is a *rate*, i.e.
  an efficiency-channel quantity carrying the exposure-channel α. **That is the same defect
  pattern I0011 identifies in `props_edge.py`.** Not changed, as instructed; reported as an
  observation for the coordinator.
- **Self-inflicted slowdown, recorded for honesty.** `validate_baseline.py`'s `.fit()` over the
  full 14×14 grid re-projects the whole frame 196 times per fold and was far too slow to be
  worth it; it was cut to a coarse grid purely to exercise the public API. The authoritative
  per-fold re-selection is `folds.py`, which does it efficiently from the precomputed metric
  table. No result depends on the cut.

---

## Deliverables

```
experiments/exploration/E1_I0011_split_alpha/
  FINDINGS.json                per target, per fold: OOS comparison, verdict, placebo sds
  NOTES.md                     this file
  build_frame.py               manifest gate + FILTER-POINT + hazard drops -> frame.parquet
  grid.py                      14x14 x 4 forms x 3 targets -> grid_metrics.parquet (tidy)
  folds.py                     11 folds x 3 protocols; role slices; alpha surface
  role_conditional.py          is a role-conditional alpha worth carrying? (no)
  placebo.py                   negative controls + the no-op diagnostic
  i0009_baseline_delta.py      COORDINATOR #04 addendum
  make_findings.py             assembles FINDINGS.json from the artifacts
  verify_partition.py          structural + targeted-textual partition check
  frame.parquet  grid_metrics.parquet
  fold_arms.csv  fold_contrasts.csv  fold_summary.csv
  slice_folds.csv  slice_summary.csv  alpha_surface.csv
  role_conditional.csv  role_conditional_summary.csv
  placebo.csv  i0009_baseline_delta.csv  i0009_baseline_delta.json
  run_log_*.txt
  baseline/
    SPEC.md                    the corrected baseline, fully specified
    corrected_baseline.py      runnable, importable, clean interface
    validate_baseline.py       equivalence check + measured performance
    BASELINE_PERFORMANCE.json
    run_log_validate.txt
```

Rerun order: `build_frame.py` → `grid.py` → `folds.py` → `role_conditional.py` →
`placebo.py` → `baseline/validate_baseline.py` → `i0009_baseline_delta.py` →
`make_findings.py` → `verify_partition.py`.

Deterministic: `SEED = 20260807` throughout; permutation controls use
`default_rng(SEED + i)` for `i` in `0..39`.

Nothing outside this directory was modified. `props_edge.py` was read only. No git command was
run. The alpha defect remains a **LEAD**; fixing it was not authorised here and was not done.
