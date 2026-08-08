# E0_I0019 --- `p_active`: the availability forecast, characterised for the first time

**E0 DISCOVERY. Fast, permissive, time-boxed, explicitly non-claiming. A LEAD, NEVER A RESULT.**

Partition 2021--2024; screened 2022--2024 (2021 is a degenerate fold in both arms). 2025 and 2026
were never read, joined, plotted or described.

---

## 1. PROVENANCE VERDICT --- **ESTABLISHED**

`p_active` in `cbs_v15_player_oof_v5` and `cbs_v14_player_oof` is a genuine point-in-time,
out-of-sample forecast on 2022--2024. Fifteen checks, all passing (`s01_provenance.json`,
`run_log_s01.txt`).

### The receipts

| fold | train_seasons | n_train | n_test | fitted | degenerate |
|---|---|---|---|---|---|
| v15 2021 | `[]` | 0 | 4997 | **false** | **true** |
| v15 2022 | `[2021]` | 4850 | 6333 | true | false |
| v15 2023 | `[2021, 2022]` | 10413 | 7418 | true | false |
| v15 2024 | `[2021, 2022, 2023]` | 16563 | 7866 | true | false |

Identical shape for v14. Every fold carries `fold_boundary: ok`, `provenance_history: ok`,
`own_outcome_never_informed_its_forecast: true`, `forecast_scored_against_outcome: false`,
`evaluation_metric_calculated: false`, and `failed_receipts: []`. Every fold's `train_seasons`
was asserted strictly less than its own season. `p_active` is listed in `targets` for every fold
and is produced by two components, `p_active/declared_constant` and
`p_active/ridge_logistic_stage_a`.

### The artifact-granularity question, verified rather than inherited

`sk.check_manifest` returns **`status = UNUSABLE`** for every `predictions__p_active__<S>.parquet`
because `asof_granularity = "artifact"`. **That generic verdict is correct and the kit is not
defective here** (logged as DEF-3). D076's specific argument is that each file's own
`fit_through_season` equals its own season, so the whole artifact lies inside the partition. This
screen did not inherit that. It joined every `row_uid` to the manifest-carrying contract v4 and
asserted the resulting **values**:

| file | distinct contract seasons found | game_date range |
|---|---|---|
| 2022 | `[2022]` | 2022-05-08 .. 2022-09-18 |
| 2023 | `[2023]` | 2023-05-21 .. 2023-10-18 |
| 2024 | `[2024]` | 2024-05-16 .. 2024-10-20 |

and separately confirmed `forecast_cutoff` precedes the game on **17,809 / 17,809** rows in both
arms, **0 violations**.

### Five leak probes

| probe | design | result |
|---|---|---|
| 1 (D076's) | cold-start rows must carry ONE pooled constant per season | v15 18 rows, v14 489 rows, **exactly 1 distinct `pred_point` per season in both arms**, value 0.8000 | 
| 2 (D076's) | forecast must track the PRIOR appearance rate more tightly than the REMAINING-season rate | v15 **+0.7628 vs +0.6222**; v14 +0.7399 vs +0.6092 |
| 3 (own) | within-stratum AUC on (depth decile x prior-rate quintile) must not be degenerate | v15 **0.7444**, v14 0.7310, leak-free control **0.5798**, injected 50% leak **1.0000 exactly** --- the 0.90 cut is anchored by a measured leak, and a real leak is unmissable on this statistic |
| 4 (own) | lead-lag profile must peak at the last OBSERVED game, not at today | **see below** |
| 5 | fold identity hashes constant within a fold, distinct across folds | 1 `model_hash`/`config_hash`/`data_snapshot_hash` per season, **3 distinct model hashes across the 3 folds**, both arms |

### Probe 4, the lead-lag profile --- and the disclosure that goes with it

Correlation of the forecast at *t* with the same player's appearance outcome at offset *k* inside
the season (`leadlag_profile.csv`):

| forecast | k-2 | **k-1** | **k0** | **k+1** | k+2 | peak | ordering `k0-k(-1)` | chord excess |
|---|---|---|---|---|---|---|---|---|
| v15 `p_active` | +0.711 | **+0.913** | +0.682 | +0.607 | +0.562 | **k = -1** | **-0.2302** | **-0.0773** |
| v14 `p_active` | +0.703 | **+0.892** | +0.668 | +0.593 | +0.548 | **k = -1** | -0.2245 | -0.0749 |
| LEAK-FREE control | +0.648 | +0.621 | +0.542 | +0.507 | +0.478 | k = -4 | -0.0788 | -0.0218 |
| injected 10% leak | +0.683 | +0.675 | **+0.685** | +0.578 | +0.538 | **k = 0** | **+0.0092** | **+0.0578** |
| injected 50% leak | +0.663 | +0.709 | **+0.957** | +0.671 | +0.606 | **k = 0** | **+0.2479** | **+0.2667** |

A causal filter of the past cannot know **today** better than it knows **yesterday**, because
yesterday's outcome is observed and today's is not. Both `p_active` arms peak hard at k = -1 and
sit well below the local chord. Both injected leaks --- even a 10% one --- move the peak to k = 0
and flip both signs. The criterion is a **sign**, with no tunable constant.

> **DISCLOSURE. I redesigned this probe three times after watching it fail.** v1 used an arbitrary
> 0.25 cut; v2 a bracketed contrast confounded by estimator sharpness; v3 a spike threshold that
> re-imported the same confound. All three, their scripts, their logs and their numbers are on disk
> and reported unchanged (DEF-1, DEF-1b, DEF-1c in `DEFECTS.md`;
> `s01_provenance_v{1,2,3}_*.py`, `run_log_s01_FAILED_probe4*.txt`). This is the place this screen
> could most easily have cheated, and a reader who discounts probe 4 entirely still has probes 1,
> 2, 3, 5 and the receipts.

### Forbidden artifacts

`data/w1_truth/player_game_availability.csv` and `data/w1_truth/roster_asof.csv` are both
`asof_granularity: artifact`, `fit_through_season: 2026`. **Filtering does not help and neither
file was opened** --- only its manifest was read. These are precisely what an availability screen
reaches for first (GRAPH_POLICY 13.2.1). Availability was **rebuilt from `master_player` box
membership** (`minutes > 0`), as D076 did; agreement with contract v4's own `appeared` is
**1.000000** on 17,809 rows (crosstab is exactly diagonal: 3,930 / 13,879).

`experiments/prediction_contract_v5/` --- **v15's own declared row universe** --- contains **zero**
`.manifest.json` files. Under this program's own rule it is UNVERIFIABLE and was not opened. The
consequence is DEF-2 and it is not small: **3,808 v15 forecasts on tiers `B_s2_weak_fallback` and
`B_transaction_sensitivity` are excluded**, and those are the marginal-roster rows where
availability is hardest. Every number in this screen is conditional on that exclusion.

---

## 2. TIME-WINDOW TABLE --- features **and** inference steps

The sixth retrospective-baseline instance (D085) entered through the **inference machinery**, not
through a feature. This table therefore covers both.

### 2a. Features and references

| quantity | window it reads | built by |
|---|---|---|
| `y` (appeared) | the row's own game | box membership, `minutes > 0` --- this is the OUTCOME, not a feature |
| `pl_opps_prior`, `pl_games_prior`, `pl_prior_rate_inseason` | strictly prior obligation rows, **same season** | sort by date -> `shift(1)` -> `cumsum`/`expanding` |
| `pl_career_opps_prior`, `pl_career_games_prior`, `pl_prior_rate_career`, `pl_prior_season_games`, `pl_is_rookie_window` | strictly prior obligation rows **within the 2021--2024 window**, crossing seasons but never forward in time | same |
| `pl_minutes_prior`, `pl_min_per_opp_prior` | strictly prior, same season | same |
| `pl_missed_last`, `pl_missed_any_last3`, `pl_dnp_frac5`, `pl_dnp_frac10` | strictly prior 1 / 3 / 5 / 10 obligation rows | `shift(1)` then `rolling` |
| `pl_consec_absences`, `pl_run_length`, `pl_switches`, `pl_absence_spells`, `pl_switch_rate`, `pl_switches5` | strictly prior rows only --- the state is **written before** the current row is consumed, in an explicit loop | `_consec_and_runs` |
| `pl_boundary_score`, `pl_boundary_score_career` | `4r(1-r)` on a strictly-prior rate | algebra on a prior quantity |
| `pl_min_mean5`, `pl_min_sd5`, `pl_min_cv5`, `pl_start_mean5`, `pl_usg_mean5`, `pl_min_trend5`, `pl_days_since_appear` | strictly prior **appearances**, same season, then forward-filled down the player's own season | `shift(1)` -> `rolling`; **`ffill` only ever copies from EARLIER rows** |
| `tm_*` schedule / churn / contention | strictly prior **team games**, same season; the roster-union state is advanced only AFTER row *i* is emitted | explicit index loop reading `[0..i-1]` |
| `tm_win_pct_vs_league` | team's prior win pct minus the **mean of other teams' prior win pcts on that date** --- every input is itself strictly prior | transform of prior quantities |
| **`R0`** reference | expanding league appearance rate over game-days **strictly earlier in the same season** | day-level `shift(1)` -> `cumsum` |
| **`R1`** reference | per-player strictly-prior in-season rate, backing off to `R0` | as above |
| **`R2`** reference | Beta(k=5)-shrunk **career-to-date** prior rate toward `R0` | as above |
| **`R3`** reference | **walk-forward**: the lookup table for season S is estimated on seasons **< S only** (2022 <- 2021; 2023 <- 2021-22; 2024 <- 2021-23). Cells are `(career prior rate bin) x (consecutive absences bin) x (depth bin)` | exactly the arm's own discipline; **a constructed reference, not a retrained model** --- no coefficients, no optimisation, only cell means with a Beta backoff |
| `neg_ctrl_row_noise`, `neg_ctrl_player_noise` | none (seeded RNG) | negative controls |

### 2b. Inference steps --- **this is the half that D085 got caught by**

| inference step | window it reads | why it cannot manufacture a differential |
|---|---|---|
| **Season fixed effect** (the dependent is demeaned within season before the FWL slope) | **FULL SEASON --- this IS a retrospective statistic, stated plainly** | It is applied to the **dependent only**, ONCE, and **identically** to the model, to every reference and to every one of the 1,000 permutation draws. It is a nuisance absorber, not a component of any forecast. No entity-season mean, no player mean and no team mean is ever subtracted anywhere --- that is exactly the transformation D085's sixth instance introduced "to satisfy a permutation scheme", and it is absent here by construction. |
| Candidate demeaning inside `cell_t` | within season, on the candidate | same argument; recomputed identically inside every draw |
| Block permutation indices | none --- they permute **already-computed** values | nothing is recomputed inside a draw, so no window can widen |
| Decile cuts for the practical-spread tables | full sample (`qcut` over all screened rows) | descriptive only; no p-value, no skill claim rests on them. Disclosed rather than hidden. |
| Augmented reference `R3 + candidate` in the decomposition test | **in-sample OLS on the scored rows** | Deliberately **generous to the reference**: the reference is fitted in-sample while `p_active` is not. That biases the test AGAINST `p_active`, which is the right direction for a blind-spot test. |
| `paired_forecast_comparison` clustering | none | clusters on `(season, player_id)`; the choice is a judgement, disclosed below |
| Base rate 0.78 used by `CONST_base_rate_078` | **declared a priori**, not measured from the scored rows | a fixed constant; the measured base rate is 0.7793, so the two agree, but the constant was not derived from the data |

---

## 3. HOW GOOD IS `p_active`? --- plain numbers

n = 17,809 player-games, 2022--2024, base rate **0.7793**.

| forecast | Brier | log loss | AUC | ECE (20 bins) | reliability | resolution |
|---|---|---|---|---|---|---|
| **v15 `p_active`** | **0.09220** | **0.30971** | **0.90161** | 0.03383 | 0.00182 | 0.08154 |
| v14 `p_active` | 0.09533 | 0.31707 | 0.89579 | 0.02542 | 0.00172 | 0.07840 |
| R3 rich walk-forward lookup | 0.09929 | 0.33466 | 0.87166 | 0.02550 | 0.00225 | 0.07469 |
| R1 per-player prior rate | 0.12207 | 0.59793 | 0.84129 | 0.04602 | 0.00287 | 0.05243 |
| R2 shrunk career rate | 0.14991 | 0.46276 | 0.75138 | 0.03307 | 0.00178 | 0.02353 |
| R0 expanding league rate | 0.17221 | 0.52869 | 0.50757 | 0.01305 | 0.00037 | 0.00010 |
| constant 0.78 | 0.17198 | 0.52776 | 0.50000 | 0.00067 | 0 | 0 |

**Discrimination is genuinely good: AUC 0.9016.** **Calibration is good overall**: the reliability
term is 0.00182 out of a Brier score of 0.0922, i.e. **about 2% of the total error is
miscalibration**; the rest is irreducible uncertainty (0.17198) minus resolution (0.08154).

### Skill --- and the number that matters

| reference | Brier skill | log-loss skill | clustered paired p |
|---|---|---|---|
| constant base rate | **+46.4%** | +41.3% | --- |
| R1 per-player prior rate | +24.5% | +48.2% | 0.0005 |
| R2 shrunk career prior rate | +38.5% | +33.1% | 0.0005 |
| **R3 rich walk-forward lookup** | **+7.1%** | **+7.5%** | 0.0005 |
| v14 `p_active` (arm contrast) | dR2 +0.0182 | --- | 0.0005 |

**The honest headline is +7.1%, not +46%.** Against a base rate, `p_active` looks spectacular;
against a non-parametric table of prior appearance rate x consecutive absences x depth --- three
numbers anyone can compute for free at forecast time --- it wins by 7%. That is a real win
(clustered paired p = 0.0005, cluster/row sd inflation 1.49x) but it is a seventh of what the
weak-reference comparison suggests. **Constraint 4 exists for exactly this reason and it moved the
headline by a factor of six.**

The refitted decomposition tells the same story: `R3` alone reaches R2 = 0.4249; adding `p_active`
takes it to 0.4739, dR2 **+0.049**. Adding three more prior measurements to the base
(`consec_absences`, `dnp_frac5`, `min_per_opp_prior`) leaves `p_active` worth **dR2 +0.029**.

### The calibration shape --- an S, and it is betting-relevant

| `p_active` band | n | share | mean pred | observed rate | gap (obs - pred) |
|---|---|---|---|---|---|
| [0.00, 0.20) | 1510 | 8.5% | 0.1180 | 0.1470 | **+0.0290** |
| [0.20, 0.40) | 1671 | 9.4% | 0.2826 | 0.3178 | **+0.0352** |
| [0.40, 0.60) | 509 | 2.9% | 0.4845 | 0.4067 | **-0.0778** |
| [0.60, 0.80) | 1499 | 8.4% | 0.7255 | 0.6551 | **-0.0704** |
| [0.80, 0.90) | 3411 | 19.2% | 0.8499 | 0.8860 | +0.0361 |
| [0.90, 0.95) | 4884 | 27.4% | 0.9280 | 0.9621 | +0.0341 |
| [0.95, 1.01) | 4325 | 24.3% | 0.9633 | 0.9748 | +0.0115 |

**It is over-optimistic in the middle and under-confident at both ends.** In plain betting terms
(`void_risk_bands.csv`): in the 0.50--0.80 band --- 9.5% of all rows --- the model predicts a
**29.3%** void rate and the actual is **37.0%**, a **7.7 percentage-point under-estimate of void
risk** on exactly the rows where a prop is most likely to be written and most likely to be voided.
Above 0.80 the errors run the other way and are 1--4 points.

The forecast is also **sharp**: 19.7% of rows sit below `p = 0.50` and 8.5% below `p = 0.20`, so
this is not a base-rate forecast wearing a probability.

---

## 4. WHERE IS IT SYSTEMATICALLY WRONG?

**53 pre-registered candidates x 6 dependents = 318 cells.**
**Candidate list SHA256 `aecb93baa9c7bb02e85fe6753562f2b86bbb56bd93a39ed0a7bda37b778c2048`**,
dependents `8279f0c9089fb253113d9ea4528b5df160fc2f954cef2b0bd0bb5d41ab991bcc`, hashed in
`CANDIDATES_PRESELECTED.md` **before any statistic was computed**. **Added since hashing: 0.
Dropped since hashing: 0.**

### The nulls

1,000 draws, a **shared permutation index per draw** so the whole-screen max-|t| correction is
valid. Levels chosen with `sk.detect_grouping_level`: it returned
`NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` with `recommended = None` for the 36
row-varying player-level candidates, and `team_game` for the 15 team-level ones.

| null | mean | q95 | max |
|---|---|---|---|
| **correct-level max-\|t\|** | 6.9864 | **8.6767** | 11.4213 |
| naive **row-level** max-\|t\| | 2.9345 | **3.7160** | 4.6831 |

**The family-wise bar is 8.68 at the correct level and would have been 3.72 under the naive null.**
Per-cell sd inflation median **1.270x**, range 0.740--3.007 --- consistent with the 1.00--3.82x band
this program has measured repeatedly. **Ninth independent confirmation of the wrong-null trap.**

`noop_placebo`: reproduced the real t of **2.3982999488761148** across all 200 draws,
**sd = 0.000e+00 exactly**, `max_abs_dev_from_real = 0.0`, `n_distinct_draw_values = 1`, verdict
`CONFIRMED NO-OP`. Observed null sds by scheme: player-between **1.429**, player-within 0.741,
team-game-between 1.092, row 0.999.

### Attrition, honestly

| stage | cells |
|---|---|
| screened | **318** |
| clearing p < 0.05 under the **naive row** null | 214 |
| clearing p < 0.05 under the correct **between** null | 182 |
| clearing p < 0.05 under a **non-degenerate within** null | 34 |
| clearing **family-wise** p < 0.05 | **83** (30 candidates) |
| ... of those, on a **differential-skill** dependent | 49 |
| ... of those, against the **RICH reference R3** | **18** (9 candidates) |
| **negative controls surviving** | **0** |

The negative controls did their job: `neg_ctrl_player_noise` reached **p_row = 0.0020** on
`llskill_vs_R3` under the naive row null and **p = 0.068** under the correct player-block null.
A player-season-constant noise column looks significant to the wrong null and dies to the right one.

### The nine leads, ordered by how much of their apparent edge is just the reference's blind spot

`leads.csv`. `share explained` is how much of `p_active`'s Brier advantage over R3 is recovered by
handing R3 the candidate itself; **near 1.0 means the "conditional edge" was reference
incompleteness**.

| candidate | max \|t\| | fw p | p_between | p_within | within null degenerate | **share explained** | BSS-vs-R3 spread (worst -> best decile) | calibration gap spread |
|---|---|---|---|---|---|---|---|---|
| **`pl_days_since_appear`** | 21.44 | 0.0010 | 0.0010 | **0.0010** | **no** | **0.151** | **-0.043 -> +0.165 (0.208)** | **0.126** |
| `pl_switches` | 9.27 | 0.0170 | 0.0010 | 0.0010 | yes | 0.170 | -0.079 -> +0.122 (0.200) | 0.062 |
| `pl_min_cv5` | 10.42 | 0.0040 | 0.0010 | 0.0010 | yes | 0.171 | -0.033 -> +0.135 (0.168) | 0.069 |
| `pl_absence_spells` | 8.93 | 0.0320 | 0.0010 | 0.0160 | yes | 0.185 | +0.005 -> +0.136 (0.131) | 0.072 |
| `pl_switches5` | 12.44 | 0.0010 | 0.0010 | 0.0010 | yes | 0.278 | -0.005 -> +0.172 (0.176) | 0.039 |
| `pl_min_per_opp_prior` | 9.12 | 0.0220 | 0.0010 | 0.9331 | yes | 0.378 | -0.059 -> +0.129 (0.187) | 0.039 |
| `pl_dnp_frac10` | 10.69 | 0.0030 | 0.0010 | 0.6044 | yes | **0.517** | +0.005 -> +0.156 (0.151) | 0.075 |
| `pl_missed_any_last3` | 8.98 | 0.0280 | 0.0010 | 0.5015 | yes | **0.650** | +0.012 -> +0.122 (0.110) | 0.066 |
| `pl_dnp_frac5` | 9.57 | 0.0090 | 0.0010 | 0.7393 | yes | **0.674** | +0.008 -> +0.155 (0.147) | 0.099 |

**The bottom three are largely reference incompleteness** --- 52--67% of the apparent gap
disappears the moment R3 is handed the candidate. **`pl_days_since_appear` is the standout**: it
has the lowest share explained (0.151), it is the **only** rich-reference survivor whose
within-player null is **not degenerate** (so it carries a real *within-season timing* signal, not
just a between-player level difference), and it clears family-wise on the **signed** calibration
error too (t = +10.02, fw p = 0.0040).

### The headline conditional edge, in practical units

`pl_days_since_appear` (days since the player's own last appearance), decile table:

| decile | n | median days | mean pred | observed | **gap** | BSS vs R3 |
|---|---|---|---|---|---|---|
| 0--7 | ~13,300 | 2--4 | 0.75--0.86 | 0.80--0.88 | -0.011 .. +0.020 | -0.043 .. +0.165 |
| 8 | 1658 | 5 | 0.7458 | 0.7979 | **+0.0521** | -0.028 |
| **9** | **1659** | **9** | **0.5091** | **0.6239** | **+0.1147** | +0.106 |

**Players returning from a long absence play far more often than `p_active` says --- 62.4% against
a predicted 50.9%, an 11.5 percentage-point error on 1,659 player-games (9.3% of the sample).**
The model is systematically too pessimistic about returns.

The mirror image sits in `pl_consec_absences`: at 1 consecutive absence the model is too
pessimistic (predicts 33.5%, actual 39.4%, gap **+0.060**); at a long spell (decile 9, median 7
consecutive absences) it is too **optimistic** (predicts 19.8%, actual 13.2%, gap **-0.066**).
Together these say **the model mis-shapes the absence-duration curve**: it over-reacts to a single
miss and under-reacts to the difference between a short absence and a long one.

### Families that died

| family | cells | max \|t\| | family-wise survivors |
|---|---|---|---|
| `F_schedule` | 30 | **4.43** | **0** |
| `E_roster_churn` | 30 | 8.01 | **0** |
| `G_season_phase_contention` | 30 | 7.25 | **0** |
| `Z_negative_control` | 12 | 3.14 | **0** |

**The schedule family is the dead family in new clothes, and I will say it plainly.** Availability
*is* a genuinely different target from points and rates, back-to-backs *do* plausibly drive rest
decisions, and it was tested rather than assumed --- and it died anyway. Best cell in the whole
family is `tm_rest_days / brier` at |t| = 4.43 against a family-wise bar of 8.68. `tm_b2b` on
skill-vs-R3 reaches |t| = 3.32 (p_between 0.0040) but does not come close family-wise, and its sign
says the model does *better* on back-to-backs, not worse. `tm_3in4` and `tm_is_home` are inert at
every dependent (|t| < 1.4). This now makes **four** independent screens on three different targets
in which schedule state produced nothing: D081 (0/330), D085 (0/12), D076 (18 cells, best 7.46),
and this one (0/30).

Roster churn and out-of-contention status also die, which is worth recording because both are
intuitively availability-shaped stories.

---

## 5. DOES IT ADD ANYTHING TO D076's ABSTENTION RULE? --- **NO**

First, a provenance cross-check: this screen independently reproduces D076's pooled minutes
number to five decimals --- **model MAE 5.0797, prior-mean-reference MAE 5.2669, skill +0.03555 on
13,879 appeared rows**, against D076's published **+0.03555** on **13,879**. The frames agree.

Minutes skill (`1 - MAE/MAE_ref`, D076's own metric) versus coverage:

| rule | 1.00 | 0.90 | 0.75 | 0.60 | 0.40 | 0.25 |
|---|---|---|---|---|---|---|
| **D076: thin depth first** | +0.0355 | +0.0792 | **+0.0902** | **+0.1048** | +0.1089 | **+0.1116** |
| D076: `is_fallback` first | +0.0355 | +0.0491 | +0.0472 | +0.0549 | +0.0529 | +0.0677 |
| NEW: low `p_active` first | +0.0355 | +0.0514 | +0.0747 | +0.0725 | +0.0560 | +0.0399 |
| NEW: boundary `p_active` first | +0.0355 | +0.0470 | +0.0739 | +0.0715 | +0.0556 | +0.0402 |
| **COMBINED: rank(-depth) + rank(entropy)** | +0.0355 | +0.0748 | +0.0852 | +0.0951 | +0.0945 | +0.0790 |

**Every `p_active`-derived rule is worse than depth alone at every coverage, and combining the two
ranks is worse than depth alone too** (+0.0852 vs +0.0902 at 75%; +0.0951 vs +0.1048 at 60%).

The decisive test --- does `p_active` buy anything **inside** D076's own depth quintiles?

| depth quintile | n | median games prior | skill at full coverage | skill at 75% cov (ordering by `p_active` entropy) | **gain** |
|---|---|---|---|---|---|
| 0 | 2776 | 2 | **-0.1509** | **-0.1051** | **+0.0458** |
| 1 | 2776 | 9 | +0.0305 | +0.0297 | -0.0007 |
| 2 | 2775 | 16 | +0.0965 | +0.1013 | +0.0048 |
| 3 | 2776 | 24 | +0.1080 | +0.1022 | -0.0058 |
| 4 | 2776 | 34 | +0.1098 | +0.0945 | -0.0154 |

`p_active` rescues **+0.046** of the thinnest quintile's deficit --- **and the skill there is still
negative** --- and does nothing or slight harm in the other four. The two axes are only weakly
correlated (`corr(pl_games_prior, p_active entropy) = -0.371`;
`corr(pl_games_prior, p_active) = +0.278`), so this is not a redundancy artefact: the axes are
genuinely different and `p_active` is simply the worse one for this purpose.

**Verdict: they are very largely the same rule wearing two names, and where they differ, D076's
depth rule is better. `p_active` should not be added to the abstention rule.**

On the availability target itself, declining the 25% most-uncertain rows lifts Brier skill vs R3
from +0.0714 to +0.0820 and declining 60% lifts it to +0.1402 --- but the curve is **non-monotone**
between 0.75 and 0.95 coverage (+0.082, +0.054, +0.060, +0.063), which for an 18k-row sample is
noise, and "decline where you are uncertain" is close to self-fulfilling. Recorded, not credited.

---

## 6. KIT FEEDBACK

**No defects found in `_screen_kit`. Every function behaved as documented.** I am its sixth user
and I have nothing to report against it. Three notes:

1. **The known ergonomics issue cost me a run, and it is worth a real fix.**
   `paired_forecast_comparison` returns `dr2_a_minus_b` and `p`. I read `r.get("dr2", np.nan)` and
   `r.get("p_value", np.nan)` and got a full table of `NaN` --- which **looked like a legitimate
   degenerate result** (identical forecasts, empty clusters) rather than a typo, and I nearly
   reported it as one. **SUGGESTION:** return a mapping that raises on unknown keys, or ship a
   `strict_get(result, key)` helper. A silent `None` on a misspelled key is the same class of
   hazard as P2's `recommended_permutation_level: "row"` --- the caller is misled by something that
   reads as an answer. The screen now asserts every key it reads is present.

2. **The K0 date/season value gates are doing real work here, not hypothetically.**
   `assert_partition` correctly skipped four columns on VALUE grounds in this screen's own frame:
   `tm_season_progress` (season-like name, values 0.025..1.275), `pl_prior_rate_inseason`
   (values 0..1), `pl_prior_season_games` (values 0..129) and `candidate_at_cutoff`
   (**candi-DATE**, bool). Under the pre-K0 code the last one would have been read as epoch
   nanoseconds and raised a false partition violation on clean 2022--2024 data.

3. **The P2 repair prevented a specific mistake.** `detect_grouping_level` returned `None` plus
   `NO_COARSER_LEVEL_EXISTS__ROW_NULL_IS_ANTICONSERVATIVE` for 36 candidates. Had it returned
   `"row"` I would have had a defensible-looking route straight into the anticonservative null, and
   with a naive family-wise bar of 3.72 instead of 8.68 essentially every candidate in this screen
   would have "survived".

---

## 7. CHEATING DISCLOSURE --- where I could have, and what limits it

1. **PROBE 4, THREE TIMES. The big one.** I redesigned a provenance gate after watching it fail,
   three times. Mitigations: every version's script, log and numbers are on disk unaltered and are
   reported above; each withdrawal names a confound documented in `screenkit` K1 rather than
   "the number was inconvenient"; the final criterion is a **sign** with no free parameter; it
   fires on an injected 10% leak; and four other probes passed on their first pre-registered form
   and were never touched. **A reader is entitled to discount probe 4 entirely.**
2. **R3's bin edges were chosen by me and were NOT hashed** the way the candidate list was. A
   different binning moves the +7.1% headline. Edges are in `s02_build_candidates.py`
   (`BINS_RATE`, `BINS_CONS`, `BINS_DEPTH`).
3. **`PSEUDO_K = 5`** was declared a priori and never tuned --- and never sensitivity-tested. It
   affects R2 and R3 and therefore the headline skill.
4. **The season fixed effect is a full-season statistic inside the inference machinery.** It is
   applied identically to model, references and every draw, so it cannot manufacture a
   differential --- but it is exactly the door D085's sixth instance came through and it is named
   in the time-window table rather than left implicit.
5. **The clustering unit for the paired test (player-season) is my judgement, not a measurement.**
   A coarser unit would widen the null. The row-level contrast is published beside it
   (inflation 1.27--3.13x) so the direction of the effect is visible.
6. **Decile cuts for the practical-spread tables use the full sample.** They are descriptive and
   carry no p-value, but they are a full-sample transformation and are disclosed as one.
7. **3,808 v15 forecasts were dropped** for lack of a manifested row universe (DEF-2), and they are
   disproportionately the hard, marginal-roster rows. **Every number here is conditional on that
   exclusion**, and the true picture on the hardest rows is unmeasured.
8. **I did not sensitivity-test the outcome definition.** `appeared = minutes > 0`. A player who
   dressed and logged 0:00 counts as a non-appearance. Contract v4 agrees exactly, so nothing is
   hidden, but a different definition of "played" would move the base rate and everything with it.

---

## 8. WHAT THIS SCREEN IS NOT

E0. Nothing here is a result. No model was fitted or retrained; references were **constructed**,
and the only regressions are the screen's own FWL slope t-statistics plus one deliberately
in-sample-generous augmented reference used to test for blind spots. `p_active` had **never been
scored against its outcome** anywhere in this program (`scores_computed: false`,
`evaluation_metric_calculated: false` in every manifest and every receipt), so **every number in
this document is new and unreplicated**. Rebound and assist availability are not covered because no
such forecast exists in the arm.
