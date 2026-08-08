# WITHIN-ENTITY NULL AUDIT — EXTENSION TO THE THIRTY UNAUDITED SCREENS — VERDICT

Screen `E1_I0040_audit_extension`. Extends `E1_I0038_within_entity_null_audit`, whose methodology
is applied here unchanged, not rederived.
Partition: 2021–2024 exploration only. **2025/26 was never opened.** Every frame read is asserted
free of any season > 2024 and any date >= 2025-01-01 before use (`scripts/s05_measure_shares.py`,
`scripts/s06_resolve.py`, `scripts/s08_discharge.py`).

---

## HEADLINE (first three sentences, as required)

**Of the 1,304 killed cells in the thirty screens outside `E1_I0036`'s census, 32 are structurally
EXPOSED to the within-entity null failure — 2.5% of those kills — and 3 are UNDETERMINABLE.**
The magnitude-aware flag `z = (observed − null_mean)/null_sd < −1.0` can be computed on only 69
killed cells and trips on 17 of them, 6 of which are genuinely exposed. **Combined with
`E1_I0038`'s 83, the programme-wide exposed total is 115 killed cells out of 2,671 auditable kills
(4.3%) across all 38 screens — that is the number this programme has been missing, and the audit
is now complete: there is no unaudited screen left.**

---

## THE COUNTERWEIGHT, IN THE SAME BREATH

**All 32 exposed cells are in one screen — `E1_I0031_rapm_as_prior` — and none of them is a flip.**
16 of the 32 are dischargeable from disk without a refit; 18 sit below D103's single-cell floor of
0.00102 where no null can produce a lead; 7 survive both filters and **not one of them has a
recoverable null mean**, so this screen produces **zero E0 leads**. `E1_I0038` corrected a real
ledger verdict (D085's "nothing clears"); this extension corrects none. The thirty screens are, in
bulk and in detail, cleaner than the eight.

**And `E1_I0021_heterogeneity_diagnostic` — the screen `E1_I0038` named as the highest risk of the
thirty — is not exposed at all.** See below; it is the most important negative result here.

---

## ANCHORS REPRODUCED BEFORE ANY NEW STATISTIC WAS COMPUTED

Required by the standard. `scripts/s00_anchors.py`, log `scripts/run_log_s00.txt`.

| anchor | prior screen's value | reproduced here | match |
|---|---|---|---|
| killed cells at `opp_team_season` | 337 | **337** | exact |
| killed cells at `player_season` | 213 | **213** | exact |
| ... their sum, D115's level-based estimate | 550 | **550** | exact |
| all cells at those levels, survivors included | 299 / 427 | **299 / 427** | exact |
| arithmetic-ceiling kills in the census | 213 | **213** | exact |
| `E1_I0038` census size / exposed / undeterminable | 1,999 / 83 / 0 | **1,999 / 83 / 0** | exact |
| **ΔR² on exactly 13,784 rows** (D097 `R08_player_ra_share → y_oreb`, `B_COMPLETE`) | 0.0064881160 | **0.0064881159695263** | exact to the quoted digit |
| that cell's `N_CYCLIC` null mean | 0.0078802401 | **0.0078802401210119** | exact to the quoted digit |

One disclosure on the 213/337 anchor: it reproduces from `level_recorded`, the CENSUS *declaration*
column, not from `candidate_level_recorded` (which gives 431/337). `E1_I0038`'s wording does not say
which; both columns are in `AUDIT_TABLE.csv` and only one reproduces. Recorded so the next reader
does not spend the twenty minutes this screen spent.

---

## COVERAGE — WHAT "THIRTY SCREENS" TURNED OUT TO MEAN

`COVERAGE_EXT.csv`, `INVENTORY_SCREENS.csv`, `INVENTORY_TABLES.csv`.

38 screens exist. `E1_I0036`'s census covers 8. The 30 remaining were all opened.

| | screens |
|---|---|
| **decide cells with a permutation null** — audited cell by cell | **15** |
| do not decide any cell with a permutation null | 15 |

The 15 that decide nothing are feature dumps (`E0_I0012`, `E0_I0013`, `E1_I0013`), reproduction and
partition screens (`E1_I0009_r2_rerun`, `E1_I0012`, `MEASURE_F1_m13_fitpool`), forecast-construction
screens (`E1_I0004_fga_forecast`, `_rim_finishing`, `_shot_selection`, `E1_I0008`, `E1_I0009`,
`E1_I0011`), the degeneracy sweep (`E0_I0028`), the power/injection study `E1_I0026_detection_floor`
— whose 1,349 cell rows are a **re-analysis of the census, not new cells** — and `_screen_kit`
itself, which was opened read-only and not modified.

**2,085 cells audited, 1,304 of them kills.** By screen, in `COVERAGE_EXT.csv`.

---

## THE `max()` SIGNATURE — THE HUNT, AND ITS RESULT

`E1_I0038` named `p_correct = max(p_within, p_between)` as the signature of the defect and the
programme has since banned it. **It does not occur anywhere in the thirty.**

Two passes, the second deliberately looser so a null result could not be an artefact of a tight
regex (`MAX_SIGNATURE_HITS.csv`, `MAX_SIGNATURE_LOOSE.csv`, `MAX_SIGNATURE_LOOSE_FILTERED.csv`):

| pass | hits |
|---|---|
| targeted `max(p_a, p_b)` / `p_correct = ... max ...` / `np.max([p_...` | **0** |
| every line containing `max`/`.max(`/`maximum` AND a p-like token | 240 |
| ... after removing print/format lines and **max-T family-wise statistics** (a maximum over CELLS within ONE null — legitimate and standard) | 106 |
| ... that combine two p-values or two null-scheme names on one line | **3** |
| ... that survive reading: `E1_I0009_r2_rerun:84,105` are `P_LOO.max() − P_LOO.min()`, a spread; `E1_I0025/c06_findings.py:58` is `max()` over rows of ONE randomization table for ONE statistic — conservative selection within a single null, not over two schemes | **0** |

**Zero of the thirty screens combine two nulls with a maximum.** Where a within-entity null appears
at all, the screens that use it follow D090's formulation without being told to:

* `E1_I0021`: *"Four schemes were run. All are reported; only one is the verdict."*
* `E1_I0030`: runs the plain within-shuffle beside the cyclic one and labels it in its own source
  **"UNSAFE within-SHUFFLE arm (D093's trap, reported for the gap only)"**
  (`s05_heterogeneity.py:97-100`).
* `E1_I0031`: selects the null **per candidate from that candidate's level**, and reports the two
  arms side by side.
* `E1_I0027`, `E1_I0036`: one null per row, each reported separately.

---

## WHERE THE EXPOSURE IS, AND THE MECHANISM IS NOT THE CONJUNCTION

### `E1_I0031_rapm_as_prior` — 32 exposed kills, and a NEW defect shape

`E1_I0031` did the right thing by design: it chose each null from the candidate's level, exactly as
`E0_I0014` does. Its own source says so (`s06_plusminus.py:8-16`) and it verified the premise. The
candidate bundles are:

```
pm_game_level  = [pm_ewma5_imp, pm_ewma2_imp, pm_run_mean_imp, pm_per36_prior_imp]  -> CYCLIC (within player-season)
pm_prev_season = [pm_prev_season_imp]                                               -> RELABEL (between player-season)
pm_all         = pm_game_level + pm_prev_season                                     -> CYCLIC (within player-season)
```

**Measured**, not inferred from names (`MEASURED_VARIANCE_SHARES.csv`, computed on
`E1_I0031/analysis_frame.parquet`, 13,879 rows):

| column | between-player-season variance share |
|---|---|
| `pm_run_mean_imp` | **0.7275** |
| `pm_ewma5_imp` | **0.5937** |
| `pm_per36_prior_imp` | **0.5718** |
| `pm_ewma2_imp` | 0.4458 |
| `pm_prev_season_imp` | **1.0000** |

A cyclic shift preserves each player-season's mean **exactly**, so that share of the candidate
survives the null untouched. For `pm_game_level` the null is blind to 73% of the dominant column.
For `pm_all` it is worse and it is provable rather than estimated:

> **`pm_prev_season_imp` is constant within player-season in 0 of 475 player-seasons' exception —
> maximum within-group spread 0.000e+00 (`scripts/s08_discharge.py`). A cyclic shift of a constant
> is the identity. The null literally cannot move that column.**

**The defect here is not `max()`. It is a composite candidate assigned the null appropriate to only
one of its components.** The screen tested `pm_prev_season` alone and correctly gave it a
between-entity relabel null; it then folded that same column into `pm_all` and tested the bundle
under the within-entity null. That is a sibling of the conjunction, in a screen that got the
level-matching rule right everywhere it applied it atomically.

### The discharge — 16 of 32, from disk, with no refit

Because `pm_prev_season` was **also** run on its own, on the same rows and the same statistic, under
its correctly matched relabel null, the blind component's own p is already recorded
(`EXPOSED_DISCHARGE.csv`):

| | cells |
|---|---|
| `pm_all` exposed kills | 16 |
| ... blind component (`pm_prev_season_imp`) tested alone under its MATCHED between-entity null | **16 of 16** |
| ... and **killed** under that matched null (p 0.381 – 0.999) | **16 of 16** |
| max ΔR² the blind component contributes to `pm_all` | **4.83e-05** |

**The exposure on `pm_all` is real and it changes nothing**: the component the null could not see
carries no effect when it is tested by a null that can see it. This is `E1_I0038`'s "the matched
null was already on disk" ruling, applied, and it discharges half the exposure at zero cost.

### What remains

| | cells |
|---|---|
| exposed kills | **32** |
| ... dischargeable from disk as above | 16 |
| ... below D103's single-cell floor of 0.00102, where no null can produce a lead | 18 |
| ... **ELIGIBLE for re-measurement under `E1_I0038`'s frozen triage rule (PREREG 5.1)** | **7** |
| ... of those 7, null mean recoverable from disk | **0** |

The 7 are all `pm_game_level` on the `decision_stratum_wf` arm, ΔR² 0.00093–0.00202, p 0.080–0.449.
**They were not re-measured.** A matched between-player-season null for that arm does not exist on
disk and constructing one is a 2,000-draw refit whose product would be an in-sample number on a
walk-forward stratum — a refit, not a reading, and the brief makes refitting the last resort. They
are recorded as **UNRESOLVED, not as clean**, in `EXPOSED_CELLS_EXT.csv`.

One on-disk number bears on how much room there is, reported as evidence of null *width* only —
D101 forbids treating it as a repriced p, because it is a different candidate bundle:
**the cyclic null's p95 is a median 3.14× wider than the relabel null's on the same rows, same
statistic, same screen** (`NULL_WIDTH_CONTRAST.csv`, range 1.78×–5.50×).

---

## `E1_I0021_heterogeneity_diagnostic` — THE NAMED HIGHEST-RISK SCREEN. VERDICT: NOT EXPOSED.

`E1_I0038` D-07 wrote: *"`E1_I0021` is specifically a heterogeneity screen and is therefore more
likely than average to have pointed a cyclic null at a between-entity quantity."* It is the right
worry and the measurement contradicts it.

**58 killed cells, 54 of them decided by a within-player cyclic null. 0 exposed.**

The frozen exposure rule applied **mechanically** would say otherwise, and this screen reports that
number rather than hiding it. Measured between-player variance shares on D085's and D089's frozen
frames (14,852 rows):

| relationship | regressor | measured between-player share | mechanical rule |
|---|---|---|---|
| R06 own usage | `O01_own_usg_pg` | **0.8413** | EXPOSED |
| R01 prior efficiency | `refA_ppm` | **0.7575** | EXPOSED |
| R05 teammate volume | `P01_c04_prevgame` | 0.2731 | not exposed |
| R03 opp ts allowed | `A02_opp_ts_allowed` | 0.0170 | not exposed |
| R02 opp efg allowed | `A01_opp_efg_allowed` | 0.0165 | not exposed |
| R04 opp defrtg | `A10_opp_defrtg` | 0.0160 | not exposed |
| NC1/NC2 controls | `G01_noise*` | 0.0169–0.0180 | not exposed |

**Under the unmodified rule, 12 of `E1_I0021`'s 58 killed cells are EXPOSED.** The column
`EXPOSURE_MECHANICAL_RULE` in `AUDIT_TABLE_EXT.csv` carries that classification so a reader can
adopt it and recompute every total in this document.

They are not exposed, and the reason is measurable rather than arguable. `E1_I0021`'s statistic is
the SD of **per-player slopes fitted on within-player demeaned x and y**
(`hd_base.py:225-252, per_player_slopes(demean=True)`; the null uses the identical arithmetic at
`hd_base.py:269`). The between-player component of the candidate is subtracted off *before the
statistic exists*. So this screen manipulated it and measured what the statistic did
(`E1_I0021_ESTIMAND_CHECK.csv`):

| candidate | measured between-player share | SD of slopes, as measured | with the between component ×10 | with it removed entirely |
|---|---|---|---|---|
| `O01_own_usg_pg` | 0.8413 | 0.109769676399 | 0.109769676399 | 0.109769676399 |
| `refA_ppm` | 0.7575 | 1.149636158461 | 1.149636158461 | 1.149636158461 |
| `P01_c04_prevgame` | 0.2731 | 0.007103515479 | 0.007103515479 | 0.007103515479 |

> **Maximum change in the statistic over every manipulation of the between-player component:
> 4.441e-16.** Floating-point noise. The component the null is blind to cannot reach the statistic,
> so the null cannot be blind to anything the statistic can see.

**This is a scope condition on `E1_I0038`'s rule, and it is the fourth instance of the pattern
D108's preserved disagreement named.** The rule reads "within-entity null AND between-entity share
>= 0.50 → exposed". It is correct wherever the candidate enters the statistic at its raw level — a
pooled ΔR², which is every cell in `E1_I0038`'s census. It is wrong where the estimand is itself a
within-entity quantity, because there the between component is annihilated by construction. The
rule needs a third clause: **and the statistic must be able to see the between-entity component.**
`E1_I0021` is immune by design in the same way `E0_I0014` is, but by a different mechanism —
`E0_I0014` chooses the right null, `E1_I0021` uses an estimand that makes the choice moot.

`E1_I0021`'s remaining 4 killed cells are decided by a covariate permutation **across** players — a
between-entity null correctly matched to a player-level covariate. Also not exposed.

---

## `E0_I0015_points_skill_decomposition` — 548 KILLS, 358 WITHIN-BLOCK, ZERO EXPOSED, BY DESIGN

The largest population in the thirty, and the cleanest result. `E0_I0015` chooses its scheme from
the measured variance share, in its own code:

```python
# s03_mechanism_and_abstention.py:284
scheme_used = "BETWEEN-block" if (vsb is not None and vsb == vsb and vsb > 0.5) else "WITHIN-block"
```

and it writes the shares it used to `grouping_levels.csv`, all 55 candidates. Verified here:

| | value |
|---|---|
| maximum between-player-season share among its **WITHIN-block** candidates | **0.4791** |
| minimum between-player-season share among its **BETWEEN-block** candidates | **0.5149** |

A WITHIN-block decision cell has `vsb <= 0.5` **by construction**. **Structurally immune, on a
measurement the screen made and recorded.** This is `E0_I0014`'s immunity, in a second screen, and
it is the kit's own documented rule applied without being asked. It should be the programme default;
`E1_I0038` already said so and this is the corroboration.

---

## `E1_I0030` — RESOLVED FROM UNDETERMINABLE BY MEASUREMENT

12 cells entered the table as UNDETERMINABLE because no variance share was recorded on disk. Rather
than guess from the column name, they were measured on the screen's own frozen frames:

| candidate | null entity | measured between-entity share | rows | verdict |
|---|---|---|---|---|
| `is_home` | `player_id` | **0.005025** | 21,462 | NOT_EXPOSED |
| `same_zone_travel` | `season+team_id` | 0.030014 | 1,940 | NOT_EXPOSED |
| `eastbound` | `season+team_id` | 0.014720 | 1,940 | NOT_EXPOSED |
| `westbound` | `season+team_id` | 0.012650 | 1,940 | NOT_EXPOSED |

The within-entity null is the correctly matched instrument in every one of these cells. `E1_I0030`
also carries the only computable `z` in that screen: on `heterogeneity.csv`, `fta_pm` has
`null_mean` 0.027493 > observed 0.026263, so the **bare** flag trips — but z = **−0.530**, well
short of −1.0. Published, not acted on, exactly as `E1_I0038` recommends.

---

## THE FLAG, MEASURED AGAIN ON AN INDEPENDENT POPULATION

`E1_I0038` measured the bare `null_mean > observed` flag at PPV 0.146 and recommended acting on
`z < −1.0` (specificity 0.980). Re-measured here on the killed cells of the thirty whose z is
computable (n = 69, of which 16 exposed / 50 not exposed / 3 undeterminable):

| rule | | EXPOSED | NOT_EXPOSED | sensitivity | specificity | PPV |
|---|---|---|---|---|---|---|
| `null_mean > observed` | trips | 12 | 25 | 0.750 | 0.500 | **0.324** |
| **`z < −1.0`** | trips | 6 | 8 | 0.375 | **0.840** | **0.429** |

**The direction of `E1_I0038`'s finding replicates: the bare flag is a screen, not a verdict, and
the magnitude-aware form is materially more specific.** The magnitudes do not replicate as
favourably, and that is stated here rather than buried: **specificity of `z < −1.0` is 0.840 here
against 0.980 there, and sensitivity is 0.375 against 0.446.** n = 69 is small and 50 of the 69
come from three screens, so neither number should be treated as a revision of `E1_I0038`'s
estimate — but the recommendation "act on z < −1.0" is now supported by a specificity of 0.84, not
0.98, on the only independent sample it has been tried on.

---

## ARITHMETIC-CEILING CELLS — EXCLUDED BY RULE, NOT RE-MEASURED

`E1_I0036`'s 213 ceiling kills are all inside the census and none of them is in the thirty. **This
audit re-measured none of them and re-measured no ceiling cell of its own.**

**20 arithmetic-ceiling-attaining cells were found in the thirty**, all in `E1_I0036`'s own
re-run tables (`LEVEL_RERUN_CELLS.csv` 10, `LEVEL_FAIRTEST_CELLS.csv` 8, `D097_RELEVEL_CELLS.csv` 2),
identified by `observed == ceiling` to within 1e-12 and flagged `is_ceiling` in
`AUDIT_TABLE_EXT.csv`. They are ceiling-*attaining* by construction (fair-test cells), not cells
killed for being at a ceiling; the `kill_reason == CEILING` category itself has **0** members in the
thirty because it is a census-era column. A ceiling kill is arithmetic and survives every
methodological revision, including this one.

---

## UNDETERMINABLE — 3, AND THE CATEGORY IS NOT COLLAPSED

`E1_I0036` ruled 436 cells ineligible rather than guessing their level. `E1_I0038` reported 0
undeterminable and correctly explained that this was a stronger record rather than an improving one.
This screen reports **3**, all in `E1_I0034_redistribution`:

`P01_LEAKAGE_minutes`, `P01_LEAKAGE_fga`, `P01_LEAKAGE_pts` — candidate `FREED_*`, decided by
`N4_freed_permute_within_season`. `E1_I0034` publishes a `candidate_level_audit.csv` with measured
shares, but it measures over **player** and **team-game**, and the null's own entity is **season**.
The share the rule needs is not on disk at any entity, and this audit did not invent one.

**This number went UP before it went down and the story matters more than the number.** 50 cells
entered as UNDETERMINABLE. 44 were resolved by *measuring* the share on the screens' own frozen
frames — which is a measurement, exactly as `E1_I0038` allowed under `var_share_source = COMPUTED`,
not a name lookup. 3 could not be, and 3 remain. See DEFECTS D-01 for the one place where this
screen's first pass did guess, by substring, and was wrong.

---

## RECORD-KEEPING — EXTENDING THE 846-OF-1,999 FINDING

`E1_I0038` found only 846 of 1,999 census cells (42.3%) had a null mean written beside their p, and
**117 permanently unauditable because `E0_I0017` stored its draws standardised**. That number bounds
what any future audit can recover. The equivalent bound for the thirty:

| | cells | screens |
|---|---|---|
| cells audited in the thirty | 2,085 | 15 |
| null mean **written beside the p by the screen itself** | **445 (21.3%)** | 7 |
| null mean **recovered by this audit from the screen's own draw archive** | 24 | 1 |
| null mean **PERMANENTLY UNRECOVERABLE** | **24** | **1** |
| no null mean extracted here, but raw draws are on disk and it is recoverable | 1,592 | 13 |

**Answering the question directly: 0 of 30 screens stored their draws standardised.** Every draw
archive in the thirty — 119 CSV dumps and 35 `.npz` archives — was tested empirically for
mean-0/sd-1 structure and **every one is raw** (`INVENTORY_CSV_DRAWS.csv`, `INVENTORY_NPZ.csv`).
`E0_I0017`'s failure mode does not recur outside the census.

**1 of 30 screens has an unrecoverable archive, for a different reason.**
`E1_I0031/permutation_draws_plusminus.csv` holds 48,000 draws keyed on
`(test, target, over, added)` but **not on stratum**, while the results table has two strata. Proved
by exact match rather than assumed: the archive's p95 reproduces the recorded `null_p95` to
< 1e-16 for all 24 `wf_eval_2023_24` rows and misses every one of the 24 `decision_stratum_wf` rows
(`scripts/s06b_stratum_check.py`, `run_log_s06b.txt`). **The decision-stratum arm's draws were never
written. Those 24 null means can never be recovered — and 16 of the 24 are exposed kills, including
all 7 cells this audit would otherwise have been able to triage.** The one place in the thirty where
the record fails is precisely the place where it mattered.

**The 1,592 cells with no null mean extracted here are not a loss.** Their decision null is a
between-entity scheme, so they are structurally incapable of this failure, and recovering their
null means would change no verdict. Raw draws exist for all of them. Recorded as available work,
not as damage.

---

## DOES THE NEGATIVE RECORD SURVIVE ITS FOURTH CHALLENGE?

**Yes, and more cleanly than the third.** 1,267 of 1,304 auditable kills in the thirty (97.2%) are
not exposed. Fourteen of the fifteen screens that decide cells have **zero** exposed cells, and two
of them — `E0_I0015` and `E1_I0021` — are immune *by design*, by two different mechanisms, neither
of which anyone instructed them to use. The banned `max()` conjunction, the defect that drove
`E1_I0038`'s entire finding, **does not occur once in thirty screens.**

**The one screen with exposure is a screen that was trying.** `E1_I0031` selected its null per
candidate from that candidate's level — the correct rule, the one `E0_I0014` uses — and was bitten
by applying it to a bundle instead of to a column. Half its exposure discharges from a number it
had already written down.

**The programme-wide picture, complete for the first time:**

| | census (8 screens) | the thirty | **all 38** |
|---|---|---|---|
| auditable kills | 1,367 (+213 ceiling) | 1,304 (+20 ceiling-attaining) | **2,671** |
| **EXPOSED** | **83** | **32** | **115** |
| NOT_EXPOSED | 1,284 | 1,267 | 2,551 |
| UNDETERMINABLE | 0 | 3 | **3** |
| exposure rate | 6.1% | 2.5% | **4.3%** |
| verdicts that FLIP | 52 per-cell, 11 family-wise | **0** | 52 / 11 |

D115 feared 550. The programme-wide answer is **115**, and every one of the 32 new ones is in a
single screen, none of them flips, and 16 of them were already answered by a column that screen had
written.

---

## WHAT WOULD CHANGE THIS VERDICT

* **The 7 unresolved `pm_game_level` cells.** They are above D103's single-cell floor, their
  decision-stratum null means are gone, and no matched arm exists on disk. A 2,000-draw
  between-player-season null on that stratum is the only thing that would settle them. It was not
  run here. **If a flip exists anywhere in the thirty, it is in those 7 cells and nowhere else.**
* **The estimand clause.** If the programme decides `E1_I0038`'s rule should be applied
  mechanically, without the "the statistic must be able to see the between component" clause this
  screen adds, then `E1_I0021` contributes **12** exposed cells, the thirty's total becomes **44**
  (exposure rate 3.4%) and the programme-wide total becomes **127** (4.8%).
  `EXPOSURE_MECHANICAL_RULE` in `AUDIT_TABLE_EXT.csv` lets a reader recompute every figure under
  that reading. This screen
  believes the clause is right because it measured the consequence at 4.441e-16, but the rule as
  frozen does not contain it, and the disagreement is preserved rather than resolved by assertion.
* **The 0.50 threshold.** Unchanged from `E1_I0038` and not retuned. `E1_I0031`'s exposure is not
  marginal to it (0.7275 and 1.0000) and `E0_I0015`'s immunity has a margin of only 0.0209
  (0.4791 vs 0.50) — that screen's cleanliness *is* threshold-sensitive and would not survive a
  threshold of 0.45.
* **`E1_I0026_detection_floor`'s 1,349 cell rows** were treated as a re-analysis of census cells
  rather than as new cells. If the programme disagrees and counts them as this screen's own, they
  need auditing and the coverage claim in the headline is wrong.
* **The flag's specificity.** 0.840 here against 0.980 there, on n = 69. The recommendation to act
  on `z < −1.0` is weaker than `E1_I0038` measured it, not stronger.
