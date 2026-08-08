# E1_I0032 — the aggregate stack: method, time windows, and everywhere this could have cheated

Preregistration `7f784133085fffc3ef9ce93086b6c64045e5190e875f302c682547aafde0206d`
Amendment 1 `b33ff1e4e779dbec7ea1ebf11872b3fc873e3378d4d85908da7007dd2ab6d26f`
Reference ladder `8079f632ea1bc159bdb993e1e1efdf49d6f73c11e5ade1b5398bdffb8dac24db` (imported from D101)

Components added after hashing: **0**. Dropped: **0**.

---

## 1. What was built

    stack(target) = ROUTE( champion_stored_forecast , tuned_estimator )
                    + slope(opponent_defence | top prior-usage tercile)
                    + slope(teammate_volume_prior_only)
                    + slope(home)

- The **champion is never refitted**. Its stored `pred_point` is read and scored (D091).
- `ROUTE` replaces the champion on rows where its own `fallback_level == 2` — D102's retarget, not
  D092's "fewer than 3 prior appearances". `fallback_level == 3` (pure cold start, 43 rows here) is
  **not** routed.
- The routed-to estimator's hyperparameters are **imported** from `refladder.CANON`, i.e. from
  D094's 15,048-cell grid. They are not re-searched on the scored rows. A structural check confirms
  the estimator built here is bit-identical to the ladder's `R2_EWMA_TUNED` (|max diff| 0.000e+00 on
  all four targets).
- Each feature component is a **walk-forward OLS slope**, fitted on seasons strictly earlier than
  the scored season, on the residual of the stack so far.

### The intercept defect, found and fixed, both numbers published

The first draft fitted `[1, x]` against a bare reference. On the home component that returned
**dR2 −1.379e-03 at p 0.0015** — thirty times D104's analytic ceiling of 4.63e-05, and the **wrong
sign**. None of it was home advantage; all of it was the walk-forward intercept recalibrating the
reference. Adding a "feature" was silently smuggling in a base recalibration that is not in the
preregistered component list.

Fixed by holding an intercept in **both** arms: `correction = fit[1, x] − fit[1]`. That is exactly
the comparison D089, D099 and D104 all made. The corrected figure is **+7.148e-05 at p 0.4576**
against D104's published +6.5e-05 at p 0.556 — a clean reproduction. **Both numbers are in
`component_reproduction.csv` and the failed run log is on disk as
`run_log_s07_FIRSTRUN_intercept_defect.txt`.** This is the single most consequential defect found in
this screen and it would have manufactured a significant negative "home effect".

## 2. The row set and the denominator

**One row set** for every target, every arm, every ablation, every placebo: 13,808 rows,
2022–2024, 472 player-season clusters. Decision stratum 5,107 rows, 257 clusters.

**One denominator per (target, stratum)**: SST of the realised response on the full scored row set
about its own unweighted mean, computed once and passed explicitly. There is no code path that can
compute a subset's own SST by accident — D099's defect made structurally impossible rather than
discouraged.

Denominators are named in every table (`sst_common`). Strata are never differenced against each
other; a decision-stratum dR2 and a pooled dR2 are different denominators and are never compared.

`POOLED_EXCL_ROUTED__POSTHOC` is labelled post hoc **everywhere it appears**. It was added after
seeing that C1 carries almost all of the pooled gain. It is not a headline cell. D094's precedent:
the fallback/modelled split was labelled post hoc throughout and the label was preserved.

## 3. TIME-WINDOW TABLE — components AND inference

| stage | ingredient | window consumed | verdict |
|---|---|---|---|
| base universe | E0_I0024 screen frame, 2021–2024 | 2021 rows are **history only** and are never scored | in-partition |
| partition guard | `refladder.assert_partition`, value-based, runs inside `ladder()` | seasons 2021–2024, dates 2022-05-08 … 2024-10-20 | **2025/2026 never read, joined, plotted or described** |
| champion forecast | `pred_point`, `fallback_level` | the champion's own stored output; **not refitted** | as produced by the champion |
| routed-to estimator | prior-game sums | the player's own same-season games at a strictly earlier date position; prefix arrays indexed at h, never h+1 | prior-only |
| routed-to estimator | half-life / mode / shrinkage | D094's grid, selected on 2022–2023 and evaluated on 2023–2024; **imported, not re-searched here** | prior-only by D094's construction |
| routed-to estimator | shrinkage target `prior_season` | the player's own previous season, whole; calendar-disjoint, asserted by `assert_season_disjoint` | prior-only |
| R4_RICH_LOOKUP (reference) | feature columns | each is a rung or a prior-only aggregate | prior-only |
| R4_RICH_LOOKUP | **blend coefficients (inference)** | OLS on seasons strictly earlier than the scored season | prior-only |
| C6 defence | `A10_opp_defrtg` | opponent's prior team-games, as built by E0_I0016 | prior-only |
| C6 defence | **usage terciles (inference)** | quantile cut computed on **strictly earlier seasons only** | prior-only |
| C6/C5/C7 | **slope coefficients (inference)** | walk-forward OLS on seasons strictly earlier than the scored season | prior-only |
| C5 teammate volume | `P01_c04_prevgame` | the team's **previous** game's box score. The tip-time variant `T01` is a post-game observation (D089 ruling 2) and is **never** used, quoted or fitted | prior-only |
| C7 home | venue flag | known at scheduling | prior-only |
| C2 availability | duration bin offsets (inference) | fitted on seasons strictly earlier; 2022 is therefore **unscored** for C2 | prior-only |
| nulls | clustered paired sign-flip | uses only realised y and the two forecasts on the scored rows; identical across arms | not a forecast input |
| SST | realised y of the full scored set | as every R² denominator must; identical across every arm of every comparison | uses realised y of the scored set only |

**D100 compliance.** Hindsight informed *where* we looked — the components came from the ledger, and
the ledger read outcomes. It never informed a number that drives a decision: every hyperparameter is
imported from a prior screen's train-only selection, every coefficient is fitted on strictly earlier
seasons, and the preregistration was hashed before any data was opened.

## 4. Nulls

- **Scheme**: clustered **paired sign-flip** on season × player blocks, `screenkit.paired_forecast_comparison`, 4,000 draws, seed 20260808. Whole clusters are sign-flipped; rows are not.
- **`null_mean` and `null_sd` are published beside every p** in every CSV (D103 ruling 2), and the raw draws for all 24 headline/placebo cells are in `permutation_draws.npz` with an index in `permutation_draws_index.csv`.
- The naive row-level p and its inflation factor are published beside every cluster p, for contrast only.
- **Cluster-robust SEs are not used and are not a substitute** (constraint 5).
- The kit's anticonservative plain within-player shuffle is not used anywhere. Where a within-entity null was wanted the cyclic variant is the available option; in the event every inference in this screen is a **paired forecast comparison**, for which the clustered sign-flip is the exact test under exchangeability, so no within-entity shuffle was needed.

**Controls.** `NOOP` (stack built from the empty component set) and `SELF` (champion vs champion)
return dR2 exactly 0.0 at p exactly 1.0 on all four targets — `controls.csv`.

**Power context.** The headline cells' own null sds are 0.0033–0.0042 pooled and 0.0010–0.0019 on
the decision stratum. D103's single-preregistered-cell floor on the decision stratum is 0.00102.
C7's ablation deltas run from +4e-06 to +3.7e-04 — **3× to 100× below that floor**. It is below the
programme's detection floor by construction, which is why "did home survive the ablation" is a test
of the aggregation thesis rather than a test of home advantage.

## 5. Reproduction — STEP 1

Full table in `component_reproduction.csv` (25 rows). Two different kinds of number are reported and
they are never mixed: **reproduction on the published basis** (same frame, rows, base, metric — the
only kind that can carry a delta) and **re-measurement on the common basis** (this screen's row set).

| component | published | reproduced | delta | status |
|---|---|---|---|---|
| C1 — the constant, points | 8.704 (sd 0.013) | 8.7045 (sd 0.0131) | +0.0005 | **exact** |
| C1 — the constant, minutes | 21.62 (sd 0.09) | 21.6228 (sd 0.0908) | +0.0028 | **exact** |
| C1 — routing gain, points | +2.8169% | +3.5849% | — | **not commensurable**: D102's figure is MAE skill against D081's own reference column in the v15 arm; ours is against `R1_PLAYER_EXPAND` in the v14 arm. D101 forbids rescaling across bases, so no delta is quoted. |
| C3 — half-life, points | 8.0 | 8.0 | 0 | **exact** |
| C3 — half-life, minutes | 2.0 | 2.0 | 0 | **exact** |
| C3 — half-life, ppm | 40.0 | 40.0 | 0 | **exact** |
| C3 — half-life, attempts | 5.0 | 3.0 | −2.0 | **differs** — adjacent grid point, different row universe and selection protocol |
| C4 — own prior season beats league | qualitative | wins on 4 of 4 targets | — | **reproduced** |
| C5 — teammate volume, direct points regression | +0.0023492 | +0.0066578 | +0.0043 | denominator mismatch — see below |
| C5 — teammate volume, **propagated from ppm** | +0.0023492 | **+0.0023266** | **−0.0000227** | **reproduced** |
| C6 — defence, points | +0.003335 | +0.0034322 | +0.0000972 | **reproduced** |
| C6 — defence, ppm | +0.005028 | **+0.0050281** | **+5.6e-08** | **exact** |
| C7 — home, pooled | +6.5e-05 (p 0.556) | +7.148e-05 (p 0.4576) | +6.5e-06 | **reproduced** |
| C2 — long-absence gap | +0.1148 | +0.1095 | −0.0053 | **reproduced** (v14 arm) |

**Nothing was excluded for non-reproducibility.** All six continuous components reproduce; C1's
*routing gain* is the one figure whose published basis is not available in this repository and it is
labelled RECONSTRUCTED, not REPRODUCED, with no delta quoted.

### A denominator finding about D089, offered carefully

D089's points figure reproduces at **−2.3e-05** once it is computed the way D101's own
reconstruction computes it: forecast **points-per-minute** walk-forward and propagate to points
through a minutes estimate. A **direct** points regression on the identical rows, base and stratum
gives +0.0066578 — 2.83× larger. The cluster p is 0.0350 either way against D089's published 0.0345,
which is the tell: **p is invariant to the denominator and dR2 is not.** So the two routes differ in
construction, not in signal. `component_reproduction.csv` carries the SSE reduction (1727.35) and
the dR2 it implies on the stratum SST, on the whole-frame SST, and the SST the published figure
implies, so a reader can check this rather than take it on trust. It is recorded as an observation
about **construction**, not as a correction to D089 — we did not run D089 and cannot see its code
path from here.

## 6. Where the pending work attaches

Neither `E0_I0029_freethrow_hurdle` nor `E1_I0031_rapm_as_prior` was read or opened. Both were
declared as hooks in the preregistration and the stack is built so neither needs a restructure.

- **C8, the free-throw hurdle channel.** It is a per-row feature, so it attaches as one more entry
  in `FEATURE_ORDER` in `scripts/s08_stack.py` and one more `dict(col=..., mask=...)` in `FEAT`,
  plus its placebo twin in `PFEAT`. The ablation matrix, the cumulative curve and the placebo stack
  all iterate over `ALL_COMPONENTS`, so they extend automatically. Position: D104 established that
  97.6% of the home effect is free throws and that free throws are **attempts, not accuracy**, so
  the hurdle channel should be added **before** C7 in the order and C7's remaining role is then to
  test whether anything is left once free throws are modelled explicitly.
- **C9, RAPM-as-prior.** If it is a shrinkage target it attaches at the `CANON` dict as
  `shrink="rapm"` inside `stack_base.cfg_from_canon` and needs no change to the routing or scoring
  machinery — it becomes a variant of C4 and its ablation is the same k=0 revert. If it is instead a
  per-row feature it attaches exactly as C8 does. Either way: **verify per target.** C4's behaviour
  here is the warning — the same shrinkage that is worth +0.0249 on points-per-minute is worth
  exactly 0 on minutes because D094 set k=0 there.

## 7. DISCLOSURE — where this screen could have cheated

1. **The amendment widened C1's population from 62 rows to 947.** That can only help the component
   with the largest published claim. The agent had computed **no** dR2 when it made the change — the
   trigger was a printed row count of zero — so it could not have known the sign. But a reader should
   treat C1's measured gain as the number this amendment most affects. The checks on it are the
   ablation and the placebo route, both hashed before the amendment.
2. **The intercept defect (§1).** The first draft produced a significant, wrong-signed "home effect"
   thirty times its own analytic ceiling. It was caught by comparing against D104's ceiling rather
   than by any automated guard. Had the ceiling not been in the brief, it would have shipped.
3. **`POOLED_EXCL_ROUTED__POSTHOC` was chosen after seeing the ablation.** It is labelled post hoc in
   every table and in the report, and it is not a headline cell. It is also the cell where the real
   stack is closest to its placebo (3.6×), which is the honest place to look for trouble.
4. **The stack order was hashed in advance**, so the cumulative curve could not be reordered to make
   it flatten later. Had we been free to choose, putting C6 first would have made the decision-stratum
   story look much better.
5. **C7 could not be dropped.** It is hashed into the component list. Its ledger ruling says do not
   ship it; including it anyway is what makes the ablation informative, and dropping it once its
   ceiling was recalled would have been the obvious cheat.
6. **The half-lives were not re-searched on the scored rows.** They are imported. A grid search here
   would have been in-sample tuning wearing a component's name.
7. **We report both bases for every headline cell.** The stack looks far better against R4 than
   against the champion on attempts (+0.442 vs +0.043) because the champion is already very strong on
   attempts. Quoting only the flattering base was available and is not taken.
8. **The feature corrections are fitted on all common rows including the routed ones.** So ablating
   C1 changes the coefficients that C5/C6/C7 apply on the decision stratum, which is why C1 shows a
   small non-zero decision-stratum ablation delta (minutes +0.000684, p 0.0022) despite acting on
   **zero** decision-stratum rows. That is a knock-on through the fitting pool, not a direct effect,
   and it is recorded rather than smoothed over.
9. **C3's attempts ablation is exactly 0.000000 and C4's minutes ablation is exactly 0.000000.**
   These are structural identities, not measurements: D094's selected cell for attempts (`equal`,
   half-life 5.0) *is* the naive comparator, and D094's k for minutes *is* 0. `identical_forecast` is
   flagged True on those rows in `ablation_matrix.csv` so nobody reads a null into them.
10. **A contradiction with D094 we did not suppress.** D094 says shrinkage "strictly hurts" minutes.
    On this universe, shrinking minutes toward the player's own prior season at k=0.5 *helps* by
    −0.0057 MAE. We kept D094's k=0 as preregistered and report the contradiction rather than
    re-tuning. It is a different row universe and a different selection protocol; it is not a
    refutation and it is not nothing.

## 8. Known limitations

- **The feature components cannot act in 2022.** Their coefficients are fitted on strictly earlier
  seasons and the champion does not exist in 2021, so 2022's residual has no training pool. C5, C6
  and C7 are structurally zero on 4,338 of 13,808 scored rows. Their measured contribution is
  diluted by roughly a third and that is a floor on them, not a ceiling.
- **C5 and C6 have incomplete coverage** even where they can act: teammate volume reaches 11,706 of
  13,808 rows and 62 of 947 routed rows; defence reaches 11,983. Coverage is published per component
  in `ablation_matrix.csv` (`rows_component_can_act_on`, `coverage_frac`).
- **The 2021 history is E0_I0024's universe**, which is the fullest available, but the champion has
  no 2021 output, so 2022's routed-to estimator leans on a history the champion itself never scored.
- **Only the v14 arm is stacked.** D102's counterexample is about v15's availability forecast; the
  continuous stack here is v14 only and no blanket rule is proposed for either arm.
- **No market test and no 2025/2026 anything.**
