# PREREGISTRATION -- E1_I0038_within_entity_null_audit

Screen: `experiments/exploration/E1_I0038_within_entity_null_audit`
Commissioned by: **D115** (`D115_THE_WITHIN_ENTITY_NULL_FAILURE_IS_GENERAL_550_CELLS_ARE_EXPOSED_AND_D108_S_OWN_INJECTION_PROTOCOL_IS_DEFECTIVE`), rulings 1-4.
Partition: **2021-2024 exploration only. 2025/26 is a sealed holdout and is never opened.**

This document is hashed (`PREREG.sha256`) BEFORE any classification rule is applied to any cell
and before any new statistic is computed. Section 0 discloses exactly what was already seen.

---

## 0. WHAT WAS ALREADY SEEN BEFORE THIS DOCUMENT WAS FROZEN (full disclosure)

Reconnaissance was read-only and is disclosed here rather than concealed, because parts of it
could in principle have shaped the rules below.

**Seen (structure):**

* `E1_I0036_level_artefact_sweep/` -- `LEVEL_ARTEFACT_VERDICT.md`, `DEFECTS.md` (D-01..D-08),
  `D097_REBOUND_REEXAMINATION.md`, `CENSUS.csv` header and its builder `scripts/s07_census.py`,
  and `scripts/lab.py` (its `BaseFit`, `null_draws`, `injection_power`, `var_share_between`).
* Decision ledger entries D103, D108, D113, D115 in full.
* The column *names* of the 8 census source tables, and the *keys and shapes* of the 7 raw
  permutation-draw `.npz` archives.
* The null-construction source code of six screens: `E0_I0014/s04_screen.py` lines 192-294,
  `E0_I0016/s02_screen.py` lines 160-190 and `ep_base.py` 207-300, `E0_I0019/s04_screen.py`
  lines 141-240 and `s05_spreads_and_decomposition.py` lines 30-70, `E0_I0024/s04_screen.py`
  lines 100-170, `E1_I0018/s03_screen.py` lines 158-198 and `tv_base.py` 182-232,
  `E1_I0023/uid_base.py` 237-276.
* The shared screen kit's docstrings for `SCHEME_BETWEEN` / `SCHEME_WITHIN` /
  `SCHEME_WITHIN_CYCLIC` / `SCHEME_ENTITY_SWAP` (`screenkit.py` lines 418-450, 1371-1420).
  **The kit was opened read-only and is not modified by this screen. No file outside
  `E1_I0038_within_entity_null_audit/` is written, staged or committed.**

**Seen (marginal distributions, no cell-level verdicts):** the value counts of
`correct_null_level`, `entity_level`, `level`, `correct_null_used`, `scheme_between`,
`perm_scheme`; the `describe()` of `var_share_between_blocks`, `var_share_between_entity`,
`var_share_between`, `var_share_between_team_season`; and crosstabs of recorded level against
which recorded p-column the decision p numerically equals.

**The one fact that most obviously could have shaped a rule, stated plainly:** `E0_I0014`'s own
code sets `use_between = var_share_between_blocks > 0.5`. The 0.50 threshold adopted in
section 3 below is therefore **not invented by this screen** -- it is the programme's own
existing operational threshold, and it is adopted for that reason and no other. Had I chosen a
different threshold I would have been choosing one that flatters this screen's hypothesis.

**Not seen:** no exposure classification, no flag count, no re-measured statistic, no injection
power number of my own has been computed. `TRIAGE_RANKING.csv` from `E1_I0036` has NOT been
opened (it ranks by a *re-levelling* EV, not by this screen's rule, and reading it first could
anchor my triage).

---

## 1. THE QUESTION

> **Which of the programme's recorded killed cells were decided by a null that permutes WITHIN
> an entity while the candidate varies BETWEEN those entities -- and is D108's injection
> protocol capable of certifying such a null?**

Three sub-questions, in order:

1. **AUDIT.** For every recorded cell: the null scheme used, the level the candidate varies at,
   the level the null permutes at, the null mean, the observed statistic, p, and the verdict.
2. **FLAG.** Apply `null_mean > observed` everywhere it can be computed; count the cells where
   it was never recorded; measure its agreement with the structural classification.
3. **D-04.** Verify that D108's injection protocol can certify a blind null, implement the
   amended protocol, and demonstrate that it correctly FAILS `N_CYCLIC` on the exact cell the
   original certified at power 0.95.

---

## 2. UNIVERSE, AND WHAT COUNTS AS A RECORD

**Universe U1 (primary):** the **1,999 cells** of `E1_I0036/CENSUS.csv`, spanning 8 screens
(D078/D082, D085, D087, D089, D090, D097, D098/D099, D108). This is the programme's own
assembled census and is adopted unchanged so the two screens' counts are comparable.

**Universe U2 (coverage check):** every `FINDINGS.json` under `experiments/exploration/`. U2 is
used ONLY to report how much of the programme's recorded evidence the census does *not* cover.
No cell is classified from a `FINDINGS.json` narrative field.

**Universe U3 (context):** `experiments/player_program/orchestration/DECISION_LEDGER.jsonl`
(114 entries; the brief says 115 -- the discrepancy is recorded, not silently reconciled). Used
to attach the ruling each screen's cells were consumed by, and to identify which verdicts turn
on a flagged cell. No cell is classified from ledger prose.

### 2.1 What is admissible as a record of a level (the D-01 line)

`E1_I0036` ruled 436 cells ineligible rather than infer a level from a candidate's name. **That
line is held.** Admissible sources, ranked, and each cell records which one was used:

| `level_source` | admissible? | definition |
|---|---|---|
| `TABLE` | YES | the screen's own results table carries the level/entity as a column value |
| `PREREG` | YES | the screen's frozen prereg JSON assigns the candidate a level, and the screen's code reads it |
| `CODE` | YES | the screen's own source code fixes the entity for every cell; cited by file and line in `AUDIT_TABLE.csv` |
| `NAME` | **NO** | inferred from a candidate's or a column's name -- **never used, for anything** |

`CODE` is admitted because reading a screen's construction is how this programme has verified
every other structural claim (`E1_I0036` verified `R08`'s construction by reading
`E0_I0024/s02_build_frame.py` lines 295-307). It is nonetheless a weaker record than `TABLE`
and every count below is reported **split by `level_source`** so a reader can discard it.

### 2.2 What is admissible as a between-entity variance share

| `var_share_source` | admissible? | definition |
|---|---|---|
| `RECORDED` | YES | the screen recorded a between-entity variance share **over the same entity its null permutes within** (established from that screen's code) |
| `COMPUTED` | YES, flagged | the screen did not record one, and it is computed **directly from that screen's own frame, on its own regressor column, on its own row set** -- no fitting, no refitting, no new data |
| `INFERRED` | **NO** | guessed from anything |

`COMPUTED` is a measurement of a recorded regressor, not an inference. It is reported
separately throughout, and the headline exposure count is given **both** ways.

---

## 3. THE EXPOSURE RULE (FROZEN)

For each cell define:

* `null_class` in {`WITHIN_ENTITY`, `BETWEEN_ENTITY`, `ROW`, `UNDETERMINABLE`}.
  * `WITHIN_ENTITY` = the null permutes values *inside* an entity, leaving each entity's own
    level intact. Covers `SCHEME_WITHIN`, `SCHEME_WITHIN_CYCLIC`, `p_N1_within_entity`,
    `p_within`, `p_within_block_null`, `p_cyclic_shift`, `p_N_CYCLIC`.
  * `BETWEEN_ENTITY` = the null destroys the entity's level: `SCHEME_BETWEEN`,
    `entity_swap_null`, `p_N2_entity_swap`, `p_entity_swap`, `p_N_PSWAP`, `p_N_ENTITY`,
    `p_between`, `p_between_block_null`, whole-cluster sign-flip.
  * `ROW` = free row-level shuffle.
  * `UNDETERMINABLE` = the scheme behind the decision p cannot be established from an
    admissible record.
* The **decision null** is the null the cell's recorded verdict rests on. Where a screen takes
  `p_correct = max(p_A, p_B)`, the decision null is the arm attaining the maximum, established
  by **exact numeric match** (`|p_col - p_correct| < 1e-12`) of the decision p against each
  arm's p column. Ties (both arms attain it) are resolved to the arm whose exclusion could not
  change the verdict -- i.e. a tie is classified `WITHIN_ENTITY` only if the within arm alone
  attains the maximum. **A tie therefore counts AGAINST this screen's hypothesis.**

**A cell is `EXPOSED` iff ALL THREE hold:**

* **E1** `null_class == WITHIN_ENTITY` for the decision null; and
* **E2** the candidate's between-entity variance share, over **the same entity the null
  permutes within**, is **>= 0.50**; and
* **E3** the cell is a KILL (`kill_reason` not in {`SURVIVOR`, `SURVIVOR_PERCELL_ONLY`}) and is
  **not** a `CEILING` kill.

**A cell is `NOT_EXPOSED` iff** E3 holds and (E1 fails) or (E1 holds and E2 fails on an
admissible share).

**A cell is `UNDETERMINABLE` iff** E3 holds and the classification cannot be completed from
admissible records: no admissible null class, or no admissible variance share over the null's
entity, or the null's entity itself is not on an admissible record.

Surviving and ceiling cells are carried in `AUDIT_TABLE.csv` with
`EXPOSURE = NOT_A_KILL` / `CEILING_EXCLUDED` and are excluded from every exposure count.

**Sensitivity, preregistered:** the same counts are also reported at thresholds 0.30 and 0.80.
The headline uses 0.50.

**`exposure_confidence`** (used only for ranking, never for the verdict):
`1.00` if `level_source == TABLE` and `var_share_source == RECORDED`;
`0.70` if either is `CODE` or `PREREG`;
`0.50` if `var_share_source == COMPUTED`.

---

## 4. THE `null_mean > observed` FLAG (FROZEN)

The diagnostic is only meaningful for a statistic that is **non-negative by construction**, for
which a null distribution centred above the observed value means the null contains the effect
rather than excluding it. Each cell therefore records `stat_scale`:

| `stat_scale` | statistic | flag form | applicable? |
|---|---|---|---|
| `DR2` | incremental R2 | `null_mean > observed` | YES |
| `ABS_T` | permutation p taken on `|t|` | `mean(|t_null|) > |t_obs|` | YES (computed from raw draws) |
| `SIGNED_SYMMETRIC` | a null symmetric about 0 by construction (sign-flip) | -- | **NO -- vacuous, reported as such** |
| `STANDARDISED` | draws standardised to mean 0 | -- | **NO -- standardisation erases the diagnostic** |

`null_mean_source` in {`RECORDED`, `FROM_DRAWS`, `NONE`}. Both are reported: how many cells the
*screens themselves* recorded a null mean for (the record-keeping finding D103 ruling 2 is
about), and how many it can be recovered for from the raw `.npz` draw archives.

Agreement is reported as a 2x3 table of `flag_null_mean_gt_observed` against `EXPOSURE`, plus
sensitivity / specificity of the flag as a detector of structural exposure, on the subset where
both are computable.

---

## 5. TRIAGE AND RE-MEASUREMENT (FROZEN BEFORE APPLICATION)

### 5.1 Eligibility for re-measurement

A cell is eligible iff:

* `EXPOSURE == EXPOSED`; **and**
* it is **not** a ceiling kill -- and additionally **not** one of the 213 arithmetic-ceiling
  kills named in `E1_I0036/LEVEL_ARTEFACT_VERDICT.md`. **A ceiling kill is arithmetic and
  survives every methodological revision. Not one is re-measured, and the exclusion is stated
  explicitly in `VERDICT.md`.** The 16 distinct candidates so killed are listed in
  `CEILING_EXCLUSIONS.csv`; **and**
* `dr2_reported >= 0.00102` (D103's single-cell floor). Below the floor a re-measurement cannot
  produce a lead under any null, so spending compute there is theatre; **and**
* the screen's frame, response column, base columns and row set are all reproducible on disk,
  so D101's denominator rule can be honoured exactly.

### 5.2 Ranking

`EV = log10(max(dr2_reported, 1e-6)) + log10(exposure_confidence)`.

Take the **top 5** distinct `(screen, candidate, target, base, stratum)` tuples, with **at most
2 per screen** so the result is not one screen's story. If fewer than 5 are eligible, take all.

### 5.3 The re-measurement protocol

For each selected cell:

1. **Anchor first.** Reproduce the screen's recorded `dr2` on its own rows to `< 5e-7`
   absolute, with the row count matching exactly. **A cell whose anchor does not reproduce is
   NOT re-measured** -- it is reported as `ANCHOR_FAILED` and left alone.
2. **D101 denominator.** Identical response, row set, SST basis, weighting and base as the
   source screen. No cross-level dR2 is ever formed.
3. **D087 coverage.** Assert every base column covers every analysis row; assert the count.
4. **NO RETROSPECTIVE BASELINE.** No reference is rebuilt. The source screen's own reference
   columns are used as-is, and their strictly-prior construction is asserted by reading the
   builder, not assumed.
5. **Matched null:** entity-swap at the entity the candidate varies at (`N_ESWAP`: swap whole
   entity-season ordered series within season). R = 601 draws, so the minimum attainable p is
   1/601 = 0.001664. Null draws written to `nulls/*.npz`.
6. **Injection verification under the AMENDED protocol of section 6**, component-wise. A null
   that fails is declared VOID for that cell and no p is quoted from it.
7. **MDE.** Only an **injection-verified** MDE80 is quoted. The analytic MDE80 is **not used
   anywhere in this screen** (D113: it is under audit for being anti-conservative by ~6.6x).
   Every number states which kind it is.
8. **Verdict language.** A cell that clears is labelled **E0 LEAD, NOT A FINDING**, in-sample,
   with its family-wise position stated and its decision-stratum shrinkage stated.

---

## 6. THE D-04 TEST AND THE AMENDED INJECTION PROTOCOL (FROZEN)

### 6.1 The claim under test

> D108's injection protocol can CERTIFY a null that is blind to the real candidate, because
> shuffling the base residuals to build the synthetic response destroys the between-entity
> structure of the RESPONSE -- the very structure the null fails to destroy in the CARRIER.

### 6.2 The cell and the gate

`R08_player_ra_share -> y_oreb`, `B_COMPLETE`, POOLED, `E0_I0024` frame, seasons 2022-2024.

**Two anchors, both must reproduce or the screen halts:**

* **A1** `dR2 = 0.006488` on exactly **13,784** rows (`E1_I0036` reproduced this; I reproduce it
  independently as this screen's required prior-anchor).
* **A2 (new, from bytes never quoted before):** the mean of D097's own on-disk cyclic null draws
  for `POOLED|y_oreb|B_COMPLETE|R08_player_ra_share` in
  `E0_I0024/permutation_draws.npz` equals **0.0078802** to 5 significant figures, and **exceeds
  A1**. A2 is the flag firing on D097's own recorded bytes, three screens before anyone looked.

### 6.3 The four runs, all preregistered

| run | protocol | expected if D-04 is TRUE | expected if D-04 is FALSE |
|---|---|---|---|
| **R1** | ORIGINAL (PREREG 5.3 of `E1_I0036`: shuffle base residuals, plant `delta` along the full carrier) on `N_CYCLIC` | power >= 0.80 at 0.002057 -> **CERTIFIES** | power < 0.80 -> nothing to fix |
| **R2** | MECHANISM: between-player variance share of the REAL response `y` vs of the SYNTHETIC response `y0 = fitted + shuffle(resid)` | synthetic share collapses toward the fitted-only share -> the shuffle destroys the response structure | shares comparable -> the stated mechanism is wrong |
| **R3** | AMENDED (section 6.4) on `N_CYCLIC` | **VOID** -- power ~0 on the between component, which carries the majority of the effect | passes -> the amendment adds nothing |
| **R4** | AMENDED on `N_PSWAP` (positive control) | **PASS** -- the amendment must not reject a valid null | fails -> the amendment is a blanket rejector and is not adopted |

**R5, the specificity control, added because a fix that rejects everything is not a fix:** the
amended protocol is run on `N_CYCLIC` against a candidate whose variance is genuinely mostly
WITHIN player, where the cyclic null is the correct instrument. **The amended protocol must
PASS it.** If it does not, the amendment is reported as over-broad and is not recommended. The
candidate is selected as the D097 candidate with the LOWEST measured between-player variance
share on the same frame, chosen on the regressor alone before any response is touched.

### 6.4 THE AMENDED PROTOCOL (specified now, in full, before it is run)

Given a fit `bf` (response `y`, base `X`), a carrier `x`, an entity key `g`, and a null:

1. Decompose the carrier at the null's entity: `x_between = mean(x | g)`, `x_within = x - x_between`.
2. Measure which component carries the effect:
   `w_between = dR2(x_between) / (dR2(x_between) + dR2(x_within))`.
3. Define the **dominant component** as `BETWEEN` if `w_between >= 0.50` else `WITHIN`.
4. Run the injection **once per component** (`FULL`, `BETWEEN`, `WITHIN`), planting `delta`
   along that component of the carrier.
5. **VERDICT ON THE NULL:**
   * `VOID_FOR_THIS_CANDIDATE` if power at `delta = 0.002057` on the **dominant component**
     is `< 0.80`. A null that cannot see the component carrying the majority of the candidate's
     measured effect is void for that candidate **regardless of its power on the full carrier**.
   * `ANTICONSERVATIVE` if type-I at `delta = 0` exceeds 0.10.
   * `USABLE` otherwise.
6. **Unconditionally**, and independently of steps 1-5, report `null_mean` beside every p and
   raise `FLAG_NULL_MEAN_GT_OBSERVED` when `null_mean > observed`. This flag is advisory on its
   own and **decisive when it co-occurs with `VOID_FOR_THIS_CANDIDATE`**.

Deltas: `[0.0, 0.000129, 0.000500, 0.001127, 0.002057]`. Replicates: 60 per delta (the count
`E1_I0036` used for its component runs, adopted so the two are comparable). Seed 20260809.
R = 601 null draws.

**Success criterion for the deliverable, stated before running:** the demonstration succeeds iff
R1 certifies `N_CYCLIC` (power >= 0.80) **and** R3 voids it, **and** R4 passes `N_PSWAP`,
**and** R5 passes `N_CYCLIC` on a within-varying candidate. **Anything less is reported as a
partial or failed demonstration**, including the case where R1 fails to certify -- which would
mean `E1_I0036`'s power-0.95 result does not reproduce and D-04's evidence is weaker than
claimed.

---

## 7. HALT CONDITIONS

* Either anchor (A1, A2) fails to reproduce -> halt, report, compute nothing further.
* Any season outside {2021, 2022, 2023, 2024} appears in any frame -> halt.
* A manifest with `asof_granularity == "artifact"` is required -> that input is UNVERIFIABLE and
  is not used. MISSING manifest = UNVERIFIABLE.
* Any attempted write outside `E1_I0038_within_entity_null_audit/` -> halt.

## 8. WHAT WOULD FALSIFY THIS SCREEN'S HYPOTHESIS

Stated now so it cannot be re-written later:

* **If most killed cells are NOT exposed, that is the result and it is reported as the
  headline.** A finding that the negative record survives its third challenge is worth exactly
  as much as a finding that it does not. No casualty is manufactured.
* If the `null_mean > observed` flag fires on cells that are structurally fine, or fails to fire
  on cells that are structurally exposed, the flag is reported as a **poor** detector and D115's
  proposed universal diagnostic is reported as weaker than proposed.
* If R1 fails to certify `N_CYCLIC`, D-04's central evidence does not reproduce and that is
  reported in the first three sentences of `VERDICT.md`.
* If R5 fails, the amended protocol is over-broad and is **not** recommended for adoption.

## 9. DELIVERABLES

`PREREG.md` + `PREREG.sha256` · `AUDIT_TABLE.csv` · `VERDICT.md` ·
`INJECTION_PROTOCOL_D04.md` + `scripts/d04_protocol.py` + the `N_CYCLIC` demonstration ·
`FINDINGS.json` · `NOTES.md` · `DEFECTS.md` · `CEILING_EXCLUSIONS.csv` ·
`FLAG_AGREEMENT.csv` · `TRIAGE_RANKING.csv` · `REMEASUREMENT_CELLS.csv` ·
`CENSUS_COVERAGE.csv` · nulls as `nulls/*.npz` · run logs.

## 10. STANDING CONSTRAINTS ACKNOWLEDGED

D101 denominator rule · D103/D113 power (injection-verified floors only, kind stated) ·
D087 reference incompleteness (coverage counts asserted) · no retrospective baseline ·
a reinstated cell is an **E0 LEAD**, never a finding · no champion is fitted · no production
change is enacted · the shared screen kit at `experiments/exploration/_screen_kit/` is **not
modified** · no blanket process kill is ever issued; only a PID this screen launched and
recorded may be terminated.
