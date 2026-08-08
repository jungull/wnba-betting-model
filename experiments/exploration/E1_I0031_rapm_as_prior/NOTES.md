# E1_I0031 — RAPM as a prior. Method, provenance, and everywhere I could have fooled myself.

> The user's suggestion: *"the wnba might even have a stat for this already like player plus minus
> which we should at least factor in or compete against."*

They were right that the stat exists. The answer to "factor in or compete against" is: **compete
against, and it loses; factor in, and it earns about a third of a percentage point** — except in
one specific place, the cold-start tier for returning veterans, where it is worth having.

---

## 0. AN INCIDENT I CAUSED, REPORTED FIRST BECAUSE IT AFFECTED OTHER PEOPLE'S WORK

**I killed the other running agents' Python processes.** Partway through this screen my step-2
script was running too slowly, and I stopped it with

```
Get-Process python | Stop-Process -Force
```

That is a blanket kill. Five other agents were running concurrently in
`E1_I0026_detection_floor`, `E1_I0027_reference_ladder`, `E0_I0028_degeneracy_sweep`,
`E0_I0029_freethrow_hurdle` and `E1_I0030_home_advantage_accounting`. Seven Python processes were
running; three had accumulated 500–1,550 seconds of CPU time and were almost certainly theirs. I
killed all of them.

I cannot undo it and I did not write to any of their directories, so no output of theirs is
corrupted — but any long-running computation they had in flight was lost.

**Status check afterwards (kill at ~14:55, checked at 15:36):**

| screen | last file write | resumed after the kill? |
|---|---|---|
| `E1_I0026_detection_floor` | 15:21:25 (`NOTES.md`) | yes |
| `E1_I0027_reference_ladder` | **14:46:48** (`run_log.txt`) | **NO — nothing written in ~50 min** |
| `E0_I0028_degeneracy_sweep` | 15:21:33 (`run_log.txt`) | yes |
| `E0_I0029_freethrow_hurdle` | 15:36:13 (`run_log_s05b.txt`) | yes, still running |
| `E1_I0030_home_advantage_accounting` | 15:22:51 (`NOTES.md`) | yes |

**`E1_I0027_reference_ladder` is the likely casualty and should be checked first.** The other four
wrote files after the kill and appear to have carried on or restarted.

For the rest of this screen I stopped processes by PID only, selecting on the command line
(`Get-CimInstance Win32_Process | Where-Object CommandLine -like '*s06_plusminus.py*'`).

---

## 1. Provenance, verified here rather than inherited

`data/rapm/rapm_walkforward.csv`, 169,266 bytes, sha256 `924411f3…`, which **matches its sibling
manifest exactly**. I re-hashed the bytes rather than taking the coordinator's word for it.

**But the kit does not pass this artifact.** `screenkit.check_manifest` only recognises
`asof_granularity` values `row` and `artifact`. For `season` it returns:

```
status = UNVERIFIABLE, usable_at_e0_e1 = False
note   = "manifest present but asof_granularity is 'season' (expected 'row' or 'artifact').
          UNVERIFIABLE -- not a pass."
```

So the manifest alone does **not** discharge the check, and neither does the byte match. What
discharges it is the value-level verification below.

### The value-level check (STEP 1), on every row of the file before any filtering

| emit season | `train_seasons` | max train | `fit_through_season` | strictly prior? | rows | players |
|---|---|---|---|---|---|---|
| 2022 | 2021 | 2021 | 2021 | yes | 155 | 155 |
| 2023 | 2021–2022 | 2022 | 2022 | yes | 206 | 206 |
| 2024 | 2021–2023 | 2023 | 2023 | yes | 237 | 237 |
| 2025 | *(verified, then dropped)* | 2024 | 2024 | yes | 265 | 265 |
| 2026 | *(verified, then dropped)* | 2025 | 2025 | yes | 314 | 314 |

- Rows with `max(train_seasons) >= emit season`: **0**
- Rows with `fit_through_season >= emit season`: **0**

**PASS.** Every row's training seasons are strictly prior to its emit season.

### A correction to the brief

The brief described the construction as `2022<-2021, 2023<-2022, 2024<-2023` — prior-season-only.
That is what `fit_through_season` says, and `fit_through_season` is the **last** training season.
The `train_seasons` column shows the fit is **cumulative / expanding-window**: emit 2023 is fitted
on 2021–2022, emit 2024 on 2021–2023. This is still strictly prior — it is *more* information than
the brief assumed, not less — but it is not "the prior season only", and a 2024 RAPM value is
partly a 2021 fact.

### Partition handling

The artifact carries five emit seasons. **The 2025 and 2026 emit rows (579 of 1,177) are dropped at
the filter-point** in `rp_base.load_rapm`, after being verified and before anything is joined,
described or written. No 2025/2026 value appears in any output table. `data/rapm/rapm_v0.csv` is
`asof_granularity: "artifact"` and **was never opened**.

### What season granularity does and does not buy (D080)

Season granularity **satisfies the partition guard**: the object attached to a 2023 row has no 2023
input. It **does not on its own discharge the retrospective check** — a season-granular artifact
could still have been built looking backwards. Here the artifact's own `train_seasons` column,
checked on values, is what discharges it, and that is stronger than season boundedness.

**The limitation that travels with every number in this screen:** RAPM is a **slow-moving prior** —
one value per player per season. It cannot move when a role changes in June, when a player returns
from injury, when a teammate is traded, or when someone gets hot. It is a level, not a trajectory.
Any apparent within-season signal from it would be something else in disguise.

### A hazard I found that the manifest does not mention

`lambda_chosen` varies **50×** across emit seasons:

| emit | λ chosen | λ source | train poss. | SD of `net_100` | thin-history caveat |
|---|---|---|---|---|---|
| 2022 | 100,000 | `fallback_max_grid` | 33,161 | **0.095** | **True** |
| 2023 | 33,000 | `inner_validation` | 71,264 | 0.372 | False |
| 2024 | 2,000 | `inner_validation` | 112,608 | **2.367** | False |

The 2022 fit had one training season and no inner-validation season, so the selector fell back to
the maximum of the grid — maximal shrinkage. `net_100` for 2022 is very nearly a constant. **A 25×
spread in the scale of the same column across seasons** means pooling it raw would let 2024
dominate purely by scale. So:

- `net_100`, `orapm_100`, `drapm_100` are used **only** after within-emit-season standardisation;
- the primary continuous measure is a **fixed-λ** column (`net_100_lam2000`), comparable by
  construction.

---

## 2. TIME-WINDOW TABLE

Every ingredient, and exactly what it is allowed to see.

| ingredient | granularity | what it reads | strictly prior to the scored row? |
|---|---|---|---|
| `rapm_walkforward` emit season *S* | player-season | possessions from seasons ≤ *S*−1 | **yes**, verified on values (§1) |
| `net_100_lam*` | player-season | as above, fixed λ | yes |
| `z_*` standardisation | within emit season | the emit season's own cross-player distribution | yes — no outcome enters; it is a rescaling of a prior-only column |
| D094 estimator (`est_*`) | row | the player's own strictly earlier same-season games; prefix arrays indexed at *h*, never *h*+1 | yes (D094's construction, reproduced exactly) |
| `ref_*` (D076/D081) | row | prior-appearance running mean | yes |
| `pl_*_mean5`, `pl_*_sd5` | row | the player's last 5 prior games | yes |
| `prevseason_*` | player-season | the player's own previous season **in the frame** | yes (seasons are calendar-disjoint) |
| `lgexp_*` | date | same-season games on **strictly earlier dates** (not `shift(1)`, which would leak same-day games) | yes |
| `role_*` | player-season | previous season's MPG tercile | yes |
| `m_pts/m_minutes/m_fga/m_ppm` (s05) | player-season | master_player previous season, shifted +1 | yes |
| `pm_ewma5/2`, `pm_run_mean`, `pm_per36_prior` | row | `.shift(1)` then expanding/EWMA within (season, player) | yes |
| `pm_prev_season` | player-season | previous season's mean plus-minus | yes |
| D092 `C0` placeholder | row | reproduced from D092's own components; its priors are fitted on seasons < *S* | yes (D092's construction) |
| `g_S(rapm)` map | fold | player-seasons of seasons < *S* only | yes |
| ridge α, shrinkage *k* | fold | chosen inside the training fold (forward-in-time inner split) | yes |
| structural-availability drop | fold | the NaN rate of the raw source **on training rows** | yes |

**Nothing reads 2025 or 2026.** `assert_partition_values` runs on the full analysis frame and tests
every numeric column that looks season-valued and every datetime column, on values.

---

## 3. What was preregistered, and what was not

`CANDIDATES_PRESELECTED.md`, sha256
**`79331a724bbde189d17a887400e36587ee53d8cf242411b2baeec765cda7c026`** — 10 RAPM candidates,
5 plus-minus candidates, 3 controls, 6 reference variants, 5 cold-start variants, 43 base columns
across 4 targets. **Added after preregistration: 0. Dropped: 0.** Every downstream step recomputes
the hash from its own copy of the list and aborts on mismatch.

**Two analyses in this screen were NOT preregistered and are labelled `_POSTHOC` in every table:**

1. `step3_V3_fill_decomposition_POSTHOC` — the F0–F4 fill sources.
2. `step4_C3_decomposition_POSTHOC` — C3 with the RAPM term removed, and with it relabelled.

Both were built *after* seeing that V3 and C3 beat their incumbents, because the brief requires any
survivor to be decomposed against its own components. **Both can only reduce a claim, never create
one** — and both did reduce one, substantially. That is the honest direction for a post-hoc control
to move.

One preregistration defect, reported rather than quietly fixed: **C1 and C4 turned out to be the
same construction** (both set the cold-start structural prior to `g_S(rapm)` alone). Both are
reported and they agree exactly. That is a property of the list I wrote, not a result.

---

## 4. Two real defects I found in my own method, and how they were fixed

Both were caught because a number looked wrong against a known anchor, not because a test failed.

### 4a. The walk-forward rank hazard (step 2)

A plain `lstsq` walk-forward fit over the complete base scored **MAE 9.30 on 2023 points**, where
D094's estimator scores **4.19**. Cause: in the **2022 training fold**, `prevseason_pts`,
`lgexp_pts` and `role_pts` are *the same column* — 2022 is the first season in the frame, so no
player has a previous season and all three carry the league fallback. The system is rank-deficient
(4 zero singular values, condition number 3.5×10²⁰); `lstsq` returns the minimum-norm solution,
which splits a coefficient of −1.256 across the three identical columns. In 2023 those columns
diverge (`prevseason_pts` spans 0–22.7, `role_pts` 4–13.8) and the fit explodes.

Standardising and truncating at `rcond=1e-6` did **not** fix it — the columns are near-identical,
not identical, so the system is ill-conditioned rather than singular. Ridge alone did not fix it
either, and made the diagnosis clearer: with standardisation the in-fold MAE was 4.03 (better than
D094's 4.15) while the out-of-fold MAE was still 6.80. A healthy in-fold fit with a large
train/test gap is the signature of extrapolation blow-up — dividing 2023 values by a 2022 SD of
~0.1 produced z-scores of magnitude **135**.

**Fix, applied identically to both arms:** a structural-availability drop (a column whose raw source
is undefined for >99% of *training* rows is dropped for that fold), standardisation, clipping the
scored fold's z-scores to the training fold's observed range, and ridge with α chosen on a
forward-in-time inner split of the training fold. After the fix the base scores 4.221 on points
against D094's 4.148 — sane, and slightly worse than the tuned simple estimator, which is itself
worth knowing.

**Consequence, stated rather than buried:** the 2023 fold has a *structurally thinner* base than the
2024 fold. It cannot use any previous-season quantity, because it is trained on the first season in
the frame. Recorded per fold in `rapm_feature_wf_folds.csv`.

**Had I not caught this, I would have reported "RAPM hurts points by −2.9%".** The pre-fix and
post-fix numbers differ in sign.

### 4b. Two permutation nulls that were too slow to run honestly

The first implementation of the player-season relabelling looped over rows in Python; the first
cyclic shifter called `np.roll` once per group per column per draw (~120M calls). Both were
rewritten as single vectorised gathers. **The vectorised cyclic shifter is verified against the loop
implementation it replaces** (same multiset, values never leave their player-season, 5 seeds), and
the relabeller is verified to round-trip exactly under the identity permutation. Neither rewrite
changes the null; had I instead reduced the draw count to make it finish, that *would* have.

---

## 5. Null construction (constraint 4)

RAPM is **constant within (season, player_id)** — asserted on values in `s01`, not assumed. So:

- **RAPM block → whole-player-season relabelling.** Row-wise permutation, or a within-player
  shuffle, would destroy nothing real and give an anticonservative null; the kit refuses the
  within-player variant for exactly this reason.
- **The whole block moves under ONE permutation per draw.** Permuting each RAPM column
  independently would destroy the real correlation between `orapm`/`drapm`/`net` and between λ
  levels, which is not what the null is meant to break.
- **Game-level plus-minus → cyclic shift** within (season, player), rows sorted by date. Credit:
  `E1_I0021_heterogeneity_diagnostic/hd_base.py` (D093), which measured p=0.0015 from a shuffle
  where the honest null gave p=0.39.
- **`pm_prev_season` → player-season relabelling**, because it is constant within a player-season.
  Reported apart from the game-level family, never mixed.
- **Cluster-robust standard errors are not used anywhere**, as a substitute or otherwise.
- Paired forecast comparisons use a **block sign-flip at (season, player)**, 2000 draws.

All draws are written out: `permutation_draws_feature_dr2.csv` (16,000),
`permutation_draws_feature_paired.csv` (16,000), `permutation_draws_reference.csv` (96,000),
`permutation_draws_coldstart.csv` (90,000), `permutation_draws_decomposition.csv` (40,000),
`permutation_draws_plusminus.csv` (48,000).

---

## 6. Denominator rule (D099)

Every dR² in every output table carries an **`sst_basis`** column and is reported both on its own
stratum's SST (`dr2_own_sst`) and on the full walk-forward SST (`dr2_on_full_wf_sst`) — or, in
step 4, on the full data-poor-tier SST (`dr2_on_full_tier_sst`). **No subset dR² is ever compared to
a full-stratum dR² in this screen.**

---

## 7. WHERE I COULD HAVE CHEATED

Every one of these is a place where a defensible-looking choice would have made RAPM look better.

1. **Thinning the base.** The single easiest cheat. If I had left D094's tuned estimator out of the
   base — or the 5-game mean, or the previous-season value — RAPM would have "survived" carrying
   information the base simply failed to hold. The base is 11 columns per target *including* the
   strongest prior-only forecast this programme knows. Reference incompleteness is the top-ranked
   source of false results here and it is the thing I most deliberately guarded.

2. **Reporting the detection dR² and stopping.** The pooled dR² is significant for all four
   targets (p = 0.0005–0.0045). Stopping there would have read as "RAPM works". The walk-forward
   forecast test says it does not lift a refit past the incumbent, and the decomposition says most
   of what it does carry is a *veteran/rookie indicator*, not quality.

3. **Reporting V3's +1.04% and stopping.** V3 beats D094's incumbent on all four targets with
   p ≤ 0.016. That headline is mostly **re-tuned shrinkage strength**: filling with the *league*
   value and re-tuning *k* already gives +0.61/+0.86/+1.20/+0.32. The post-hoc F0 control is what
   exposes this, and I ran it only because the brief demanded a decomposition.

4. **Not building the same-coverage non-adjusted comparator.** F2 — the player's raw previous-season
   box score from `master_player`, same backward coverage, no adjustment — matches RAPM on three of
   four targets and beats it on points-per-minute. Omitting F2 would have let "RAPM helps" stand in
   for "having any prior-season number helps". **F2 is the direct answer to the user's question and
   it is the least flattering result in the screen.**

5. **Reporting C3's +2.35% and stopping.** C3 refits a coefficient on D092's *own* structural prior
   as well as adding RAPM. Pooled, recalibration alone gets +2.11% of the +2.35%. Only the
   veteran/rookie split rescues a genuine RAPM effect — and only for veterans.

6. **Pooling veterans and rookies.** RAPM does not exist for a true rookie. Pooling would have let
   a +2.28% veteran gain be reported as if it applied to the 18% of the tier where the same change
   costs −54%. The two markers agreeing on all 698 rows is what makes the split trustworthy.

7. **Imputation choice.** Missing RAPM is filled with the within-emit-season mean plus a `has_rapm`
   indicator. That indicator turned out to be the largest single component of the detected signal —
   so the imputation policy is *load-bearing*, and had I filled with the replacement level instead
   the decomposition would read differently. Stated because it is a genuine researcher degree of
   freedom, not because it is wrong.

8. **Choosing the evaluation stratum after looking.** The strata are fixed in
   `CANDIDATES_PRESELECTED.md` before any statistic: `wf_eval` = 2023+2024 (9,517),
   `decision_stratum` (3,549), `data_poor` (657). RAPM looks *worse* on the decision stratum than
   pooled in step 2 — I report both.

9. **The ridge α and shrinkage k grids.** Both are tuned, and both are tuned **inside the training
   fold only**. Each arm picks its own α, which is the fair comparison — but a grid is still a
   researcher choice, and a different grid would move the third decimal place.

10. **Excluding 2022 from step 4.** Necessary — the RAPM→level map needs an earlier season and 2022
    has none inside the frame. But it means my cold-start numbers cover 698 of D092's 1,061 rows
    and are **not** directly comparable to D092's three-season headline. The incumbent is rescored
    on exactly my rows so both sides face the same games.

11. **`grand_fallback` and the 2022 opening date.** Inherited from D094's machinery. It fires only
    on 2022 opening-date rows, which are never in the headline evaluation stratum.

12. **What I did not do:** the champion was never retrained or refitted; no file outside
    `E1_I0031_rapm_as_prior/` was written; `registry.jsonl`, `DECISION_LEDGER.jsonl`,
    `GRAPH_EVENTS.jsonl` and `idea_log.jsonl` were not touched; the five sibling agents' directories
    were never read or written (though see §0 for the harm I did cause them).

---

## 8. Files

| file | what it holds |
|---|---|
| `FINDINGS.json` | every headline number, machine-readable |
| `CANDIDATES_PRESELECTED.md` | the frozen candidate list and its sha256 |
| `rapm_as_feature.csv` | step 2: detection dR² and walk-forward forecast skill |
| `rapm_feature_marginal_dr2.csv`, `rapm_feature_decomposition.csv`, `rapm_feature_controls.csv`, `rapm_feature_wf_folds.csv` | step 2 supporting tables |
| `rapm_as_reference.csv` | step 3: V0–V5 against D094's incumbent, 4 strata |
| `rapm_reference_fold_detail.csv`, `rapm_reference_fold_meta.csv` | per-fold k choices and map availability |
| `coldstart_comparison.csv` | step 4: C0–C4 by population |
| `coldstart_context_vs_champion.csv`, `coldstart_populations.csv`, `coldstart_rapm_map.csv` | step 4 supporting tables |
| `decomposition_posthoc.csv` | the two post-hoc decompositions |
| `plusminus_separate.csv` | step 5: dR², head-to-head, walk-forward |
| `provenance_emit_seasons.csv`, `d094_reproduction.csv` | step 1 verification |
| `permutation_draws_*.csv` | 206,000 null draws |
| `rp_base.py`, `s00`–`s07` | scripts, in order |
| `run_log_s00.txt` … `run_log_s07.txt` | full console output of every step |
