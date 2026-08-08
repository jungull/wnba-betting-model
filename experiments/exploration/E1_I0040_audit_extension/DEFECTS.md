# DEFECTS — E1_I0040_audit_extension

Defects in this screen's own work, in the programme's recorded evidence, and in the methodology
this screen was directed to apply. Severity A = would change a verdict.

---

## D-01 (A) — **THIS SCREEN'S OWN FIRST PASS MIS-ATTACHED A VARIANCE SHARE BY SUBSTRING MATCH**

The brief warned that five findings in this programme have died to substring matching. It caught
this screen too, on the first pass, and the fix is recorded rather than quietly applied.

`scripts/s04_audit_table.py` matched `E1_I0034_redistribution`'s primary cells to its
`candidate_level_audit.csv` with

```python
if cand and (cand.split("_")[-1] in k or k.split()[0] in cand):
```

For candidate `FREED_minutes` this matched the audit row `u_minutes  (P03/P04 main term)` on the
token `minutes`, and attached **`u_minutes`'s** between-player share of 0.0742 to a completely
different quantity. Three cells (`P01_LEAKAGE_minutes/fga/pts`) were classified `NOT_EXPOSED` on a
number that was not theirs.

Caught by inspecting the UNDETERMINABLE list and noticing that P01 was absent from it when it
should not have been. Repaired in `scripts/s07_finalise.py` with an **explicit** cell → audit-row
map, and the three cells are now `UNDETERMINABLE` — which is what they always were, because
`candidate_level_audit.csv` measures over player and team-game while P01's null permutes within
**season**, and the share the rule needs is not on disk at any entity.

**Consequence if uncorrected:** 3 cells reported clean on borrowed evidence, and this screen's
UNDETERMINABLE count reported as 0 rather than 3 — which would have looked like a stronger record
and been a weaker one. That is precisely the misreading `E1_I0038` D-06 warned against.

**Remedy, generalised:** a candidate → level join must be an exact key match or an explicit map.
Substring matching between candidate names is not a join, and no screen in this programme should be
allowed to do it again.

---

## D-02 (A) — **`E1_I0031`'s DRAW ARCHIVE OMITS THE STRATUM KEY, AND 24 NULL MEANS ARE GONE — 16 OF THEM ON EXPOSED CELLS**

`E1_I0031_rapm_as_prior/permutation_draws_plusminus.csv` holds 48,000 draws keyed on
`(test, target, over, added)`. The results table `plusminus_separate.csv` has **two strata** per
key — `wf_eval_2023_24` and `decision_stratum_wf`. The archive has one.

Proved rather than assumed (`scripts/s06b_stratum_check.py`, `run_log_s06b.txt`): the archive's own
p95 reproduces the recorded `null_p95` to **< 1e-16 for all 24 `wf_eval_2023_24` rows** and misses
every one of the 24 `decision_stratum_wf` rows by 5e-04 to 2e-03. The decision-stratum arm's draws
were computed, used to produce a p and a p95, and then never written.

**Direction of harm is the worst possible.** The lost stratum is the *decision* stratum. 16 of its
24 rows are structurally exposed cells, and all **7** cells that this audit's frozen triage rule
would otherwise have made eligible for re-measurement are in it. The one place in thirty screens
where a null mean was needed is the one place it does not exist.

`E1_I0038` D-04 recorded 117 cells permanently unauditable because `E0_I0017` **standardised** its
draws. This is a second, distinct way to lose the same diagnostic: **write raw draws but forget a
key.** It is arguably worse, because standardisation is visible on inspection and a missing key is
not — the file loads, parses, and joins, and simply answers about the wrong arm.

**Remedy:** a draw archive must be keyed on **every** column that distinguishes a row of the results
table it belongs to, and a screen should assert `archive.groupby(keys).size() == results.groupby(
keys).size()` before it finishes. `E1_I0038`'s remedy ("write raw draws, always") is necessary and
not sufficient.

---

## D-03 (A) — **THE EXPOSURE RULE HAS AN UNSTATED SCOPE CONDITION: THE STATISTIC MUST BE ABLE TO SEE THE BETWEEN-ENTITY COMPONENT**

`E1_I0038` PREREG 3 freezes the rule as: decision null is within-entity AND the candidate's
between-entity variance share >= 0.50 → EXPOSED. Applied mechanically to
`E1_I0021_heterogeneity_diagnostic`, that rule returns **12 exposed cells**, on measured shares of
0.8413 (`O01_own_usg_pg`) and 0.7575 (`refA_ppm`).

The rule is wrong there, and the demonstration is arithmetic rather than argumentative
(`E1_I0021_ESTIMAND_CHECK.csv`). `E1_I0021`'s statistic is the SD of per-player slopes fitted on
**within-player demeaned** x and y (`hd_base.py:225-252`, `demean=True`; the null runs the identical
arithmetic at `hd_base.py:269`). Multiplying the between-player component of the candidate by 10, or
deleting it outright, changes the statistic by at most **4.441e-16**.

> A null cannot be blind to a component the statistic cannot see either.

**This is the fourth instance of the pattern D108's preserved disagreement named** — a rule
generalised from a well-measured case carrying an unstated scope condition. `E1_I0038`'s census is
entirely pooled-ΔR² cells, where the candidate enters at its raw level and the rule is exactly
right. The first screen outside that census with a within-entity *estimand* breaks it.

**Consequence if uncorrected:** the programme-wide exposed total is 127 rather than 115, and 12
cells in a clean screen are re-opened for no reason. Conversely, if the clause is adopted
carelessly, a screen could claim immunity by asserting its estimand is within-entity without
measuring it. The clause must be **measured** the way it was here, not declared.

**Remedy:** amend the rule to three clauses — (i) the decision null is within-entity, (ii) the
candidate's measured between-entity share >= 0.50, **and (iii) perturbing the candidate's
between-entity component measurably changes the statistic.** Clause (iii) costs two extra
evaluations of the statistic and is decisive.

---

## D-04 (A) — **A NULL CHOSEN CORRECTLY PER COLUMN CAN STILL BE WRONG FOR A BUNDLE OF COLUMNS. THIS IS A NEW DEFECT SHAPE.**

`E1_I0031_rapm_as_prior` applies the level-matching rule that `E0_I0014` and `E0_I0015` use, and
applies it correctly to every column it tests atomically:

* `pm_prev_season_imp` — measured constant within player-season in 475 of 475 player-seasons →
  given the **between-entity** relabel null. Correct.
* the four game-level running series → given the **within-entity** cyclic null. Defensible.

It then composes `pm_all = pm_game_level + pm_prev_season` and tests the composite under the
**within-entity cyclic null**. A cyclic shift of a within-group constant is the identity, so for
those 16 cells the null cannot move one of the five columns at all. The screen had already proved
that column constant, in its own assertion at `s06_plusminus.py:49`.

**The failure is not `max()`, and the programme's current ban does not catch it.** `max()` over two
nulls is a defect of *combination*; this is a defect of *composition*. Both arise the same way: a
level-matching rule stated over candidates, applied to something that is not a single candidate.

The harm here is bounded — the blind component contributes at most 4.83e-05 of ΔR² and is killed
under its own matched null on all 16 cells (`FLIPS.md` route 1) — but the harm being small is a
property of this data, not of the construction.

**Remedy:** the null must be selected from the **maximum** between-entity variance share over the
bundle's component columns, not from the bundle's name or its dominant member. Stated as a rule: a
composite candidate inherits the most restrictive null any of its components would require.

---

## D-05 (B) — **ONLY 21.3% OF CELLS IN THE THIRTY CARRY A NULL MEAN, WORSE THAN THE CENSUS'S 42.3%, AND D103 RULING 2 IS STILL NOT BEING APPLIED**

`E1_I0038` D-05 found 846 of 1,999 census cells (42.3%) with a null mean written beside the p. The
thirty are worse: **445 of 2,085 (21.3%)**, concentrated in 7 of the 15 screens that decide cells.
`E1_I0032`, `E1_I0033`, `E1_I0034`, `E1_I0035` and `E1_I0036` record it consistently; `E0_I0015`,
`E1_I0004` (both), `E1_I0020`, `E1_I0022`, `E1_I0025` and `E1_I0027` record a null **sd** or a
**p95** but not a mean.

The good news is real and should be recorded as loudly: **0 of 30 screens stored their draws
standardised.** Every one of the 119 CSV draw dumps and 35 `.npz` archives in the thirty was tested
empirically for mean-0/sd-1 structure and every one is raw (`INVENTORY_CSV_DRAWS.csv`,
`INVENTORY_NPZ.csv`). `E0_I0017`'s permanent loss of 117 cells does not recur outside the census.
The 1,592 cells with no null mean extracted here are **recoverable** — the draws are on disk for all
of them — and were not recovered only because their decision null is between-entity and recovery
would change no verdict.

**Remedy:** unchanged from `E1_I0038` D-05 and still not done — a one-off pass writing `null_mean`
and `null_sd` back into each screen's results tables from its own archives. **NOT DONE HERE; that
would be a write outside this screen's scope.** Recorded as available work, now costed: it is
possible for 1,592 of the 1,616 cells in the thirty that lack one, and impossible for 24 (D-02).

---

## D-06 (B) — **THE FLAG'S SPECIFICITY DOES NOT REPLICATE AT `E1_I0038`'s VALUE**

`E1_I0038` measured `z < −1.0` at sensitivity 0.446 / specificity 0.980 on 1,170 census cells and
recommended acting on it. On the only independent sample it has since been tried on — 66 killed
cells in the thirty with a computable z and a determinate exposure class — it measures
**sensitivity 0.375 / specificity 0.840 / PPV 0.429**.

The **direction** replicates and is the important part: the bare `null_mean > observed` flag
measures 0.750 / 0.500 / 0.324 on the same cells, so the magnitude-aware form is still materially
more specific and the recommendation stands. But 0.840 is not 0.980, and a programme acting on this
flag should expect roughly one false re-opening for every true one, not one in fifty.

n = 66 is small and 50 of the 66 come from three screens, so this is not a revision of
`E1_I0038`'s estimate. It is a caution that its estimate came from a single census and has not yet
been reproduced.

**Remedy:** state the flag's operating characteristics with the population they were measured on
attached, and stop quoting 0.980 unqualified.

---

## D-07 (B) — **`E1_I0038`'s 213/337 ANCHOR REPRODUCES FROM ONE COLUMN AND NOT THE OTHER, AND IT DOES NOT SAY WHICH**

`E1_I0038/VERDICT.md` states "213 at `player_season` + 337 at `opp_team_season` ... both anchors
reproduce to the unit". `AUDIT_TABLE.csv` carries two candidate-level columns. Grouping killed cells
by `level_recorded` gives **213 / 337** exactly; grouping by `candidate_level_recorded` gives
**431 / 337**. Only the first reproduces, and the prose names neither.

Not a defect in the number — the number is right and reproduces exactly. A defect in the record: an
anchor that a later screen is required to reproduce before it may compute anything must name the
column it came from. This screen spent real time on it.

**Remedy:** quote anchors as `file :: column :: filter`, not as bare integers.

---

## D-08 (C) — **`E1_I0026_detection_floor`'s 1,349 CELL ROWS WERE TREATED AS A RE-ANALYSIS, NOT AS NEW CELLS, AND THAT IS A JUDGEMENT CALL**

`E1_I0026/s08_cell_verdicts.csv` (1,349 rows) and `retrospective_power.csv` (1,975 rows) carry
per-cell verdicts keyed on `decision ∈ {D078/D082, D085, D087, D089, D090, D097, D098/D099}` — the
census screens. They are a power re-analysis of cells that `E1_I0036` and `E1_I0038` already
audited, not new decided cells, so they are excluded here to avoid double-counting.

Same treatment applied to `E1_I0036`'s two `D097_COMPONENT_NULLS.csv` `N_CYCLIC` rows: they are a
re-measurement of D097's `R08_player_ra_share` cell, which is already one of `E1_I0038`'s 83. They
are classified `EXPOSED_ALREADY_COUNTED_IN_E1_I0038` in `AUDIT_TABLE_EXT.csv` and excluded from this
screen's total. `E1_I0036` itself measured that null's power on the between component at **0.00** and
flagged it blind, so their exposure is not in doubt — only their ownership.

**Reasonable people can differ.** If the programme counts them as new, `E1_I0026` needs a cell-level
audit it did not get here, and the claim in `VERDICT.md` that the audit is complete is wrong.
Disclosed rather than assumed.

---

## D-09 (C) — **`E0_I0015`'s IMMUNITY HAS A MARGIN OF 0.0209 AND IS THRESHOLD-SENSITIVE**

`E0_I0015_points_skill_decomposition` is structurally immune because its own code picks the scheme
at `vsb > 0.5` and its WITHIN-block candidates therefore top out at a measured share of **0.4791**.
That is 0.0209 below the audit's 0.50 threshold. At a threshold of 0.45 — a defensible choice
nobody has argued for — `rate_pred_cv` (0.4791), `pl_pts_sd5` (0.4603) and `pl_usg_sd5` (0.4576)
would all cross, and 548 clean kills would need re-examining.

The 0.50 threshold is **not retuned here**; it is `E1_I0038`'s, which is `E0_I0014`'s, which is the
kit's. But the largest clean population in the thirty owes its cleanliness to a rule that is
self-fulfilling — the screen chose its null *at* the threshold, so it cannot fail a test conducted
*at* the threshold. That is a real limitation of testing a screen against its own operating rule
and it is not resolved by this audit.

`E1_I0031`'s exposure, by contrast, is nowhere near the threshold (0.7275 and 1.0000) and would
survive any threshold between 0.05 and 0.72.

---

## NOT A DEFECT, RECORDED SO IT IS NOT RE-LITIGATED

* **The banned `max(p_within, p_between)` does not occur in any of the thirty screens.** Two passes,
  the second deliberately loose (240 raw hits reduced to 0 after reading). `max`-T family-wise
  statistics — a maximum over CELLS within ONE null — are legitimate, standard, and appear in seven
  screens; they are not the defect and must not be confused with it.
* **`E1_I0030` runs the unsafe plain within-shuffle beside the cyclic null and labels it as unsafe
  in its own source** (`s05_heterogeneity.py:97-100`: *"UNSAFE within-SHUFFLE arm (D093's trap,
  reported for the gap only)"*). It reports the gap and takes the verdict from the cyclic arm. That
  is D090's formulation, arrived at independently, in a fourth screen.
* **`E1_I0021` found and reported the kit gap that this whole line of enquiry rests on.** Its
  NOTES §5b names `SCHEME_WITHIN`'s anticonservatism for autocorrelated regressors, measures it
  (p = 0.0015 where the honest null gives 0.39), and recommends `SCHEME_WITHIN_CYCLIC`. The kit now
  carries that scheme and **raises** on the unsafe one. The screen the audit was told to fear
  hardest is the screen that supplied the fix.
* **No process was killed.** This screen launched Python only through synchronous, short-lived
  foreground invocations; no PID was recorded because none outlived its command, and **no blanket
  `Stop-Process`, `taskkill`, or `Get-Process python | Stop-Process` was ever issued.** Sibling
  agents' processes were never touched.
* **The shared screen kit was never modified.** `_screen_kit` was opened read-only, for the scheme
  vocabulary only (`SCHEME_CODE_HITS.csv` records the lines read). Nothing outside
  `experiments/exploration/E1_I0040_audit_extension/` was written, staged, or committed, and no
  `git` write command was run.
* **2025/26 was never opened.** Every parquet frame read here is asserted free of any season > 2024
  and any date >= 2025-01-01 before a single value is used
  (`s05_measure_shares.py::assert_partition`, and explicit asserts in `s06_resolve.py` and
  `s08_discharge.py`). All CSV sources are 2021–2024 exploration artefacts.
* **No champion was fitted, no production change was enacted, and no cell was re-measured.** The
  only computation performed on raw data was a variance share and a slope dispersion — both
  measurements of existing frozen columns, in the sense `E1_I0038` established with
  `var_share_source = COMPUTED`.
