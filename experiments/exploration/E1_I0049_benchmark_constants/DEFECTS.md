# DEFECTS — E1_I0049_benchmark_constants

Defects this screen found, including the ones it found in its own commissioning brief and the one
it found in the screen that commissioned it. Ordered by consequence.

**Nothing here reopens any killed cell or reverses any gate.** Stated first so the length of this
file is not mistaken for the size of the exposure.

---

## D-01 — `0.002057` IS A CEILING BEING QUOTED AS AN EFFECT, AND IT IS NOT A BOUND EITHER

**Severity: it is the most-cited number in the programme and it is wrong in two independent ways.**

`E1_I0018/FINDINGS.json`, `STEP_4…/in_sample_coefficient[13]`,
`DECISION | B_COMPLETE | P01_c04_prevgame`, n = 5,673, response `y_pts`:

| quantity | value |
|---|---|
| `CEILING_dr2_points_per_sd` — **the published 0.002057** | 0.0020571994 |
| `paired_dr2_points` — **the realised increment on the same row of the same table** | **0.0033139323** |
| `c*` = (d·e)/(d·d) | **1.3594722754** |
| ORACLE — the true bound | **0.0035630546** |
| realised / published | **1.611×** |
| ORACLE / published | **1.732×** |

**The realised increment sits in the same JSON object as the ceiling that is supposed to bound it,
one key away, and is 61% larger.** It has been there since D089 was written and no screen has
compared them. D125 correctly identified that D089's `arithmetic_ceiling.csv` records no oracle —
but D089's **`ceiling_reconciliation.csv` records `c*` = 1.3594722754 and ORACLE = 0.0035630546 for
this exact cell**, so the bound was not missing from the record, only from the ledger sentence.

Both failures are re-derived from the frozen frame here at ≤ 4.8e-11 and reproduce D089's own
recorded columns.

**Consequence.** `0.002057` is (a) a ceiling, not an effect — the effect is `0.0023492235735382717`
on a different row set — and (b) a transported ceiling with `c* > 1`, so it is not a bound. It is
the one benchmark in the card that names nothing that exists.

**Not repaired.** Every affected file is outside this screen's write scope.

---

## D-02 — THE TWO DETECTION FLOORS ARE MEASURED ON A DIFFERENT RESPONSE FROM EVERY CONSTANT THEY ARE QUOTED AGAINST

**Severity: a D101 violation running through the whole ledger, ~30% in size.**

`E1_I0026_detection_floor/scripts/df_base.py:51`:

```
OUTCOME = "y_ppm"
```

`0.00102` and `0.00235` are ΔR² on **points per minute**. `0.002057`, `0.000129` and every ceiling
compared against them are ΔR² on **points**; `0.001127` is on **field-goal points**. Three
responses, one floor.

Measured directly (`raw/s03_null_draws_signed_raw.npz`, 600 shared entity-swap draws, seed
20260808, same rows / base / carrier):

| K | `y_ppm` floor (ARM P) | points floor (ARM T) | ratio |
|---|---|---|---|
| 1 | 0.001133 | **0.000798** | **0.704×** |
| 132 | 0.002671 | **0.002058** | **0.770×** |

**The published floors are ~30% too high for points-scale statistics.** Direction: every
"ceiling below the floor" kill was slightly weaker than stated; every "effect above the floor"
claim was slightly understated. `WHAT_WOULD_FLIP.md` shows nothing crosses.

**This screen's own limitation on the same finding:** one carrier, one null, 600 draws, and the
analytic MDE80 rather than E1_I0026's drift-corrected fixed point. **The ratio is the defensible
output; the absolute points-scale floors are indicative.**

---

## D-03 — E1_I0047's "D084 UNDERSTATES ITS TRUE BOUND BY 10×" IS A CROSS-SPEC COMPARISON, AND ON THE MATCHED CELL THE CEILING **OVERSTATES**

**Severity: corrects a defect claim, in the screen whose whole subject was denominator matching.**

`E1_I0047/DEFECTS.md` D-01 and `BOUND_OR_NOT.md` §7 report:

| stratum | n reported | max ORACLE reported |
|---|---|---|
| ON stratum | 5,086 | 1.283e-04 |
| ALL rows | 11,267 | 9.719e-05 |
| OFF stratum | 6,181 | 1.285e-03 |

Recomputed from `E1_I0004_efficiency_transfer_v2/arithmetic_ceiling.csv` (9 rows, all printed in
`scripts/run_log_s02.txt`):

* the ON-stratum maximum **1.283e-04 belongs to `SPEC_ALL5_GLOBAL`, n = 4,938, `sd_y` = 7.5316** —
  not to the n = 5,086 row it is labelled with;
* the OFF-stratum maximum **1.285e-03 belongs to `SPEC_ALL5_GLOBAL`, n = 5,024, `sd_y` = 5.3180** —
  not to the n = 6,181 row it is labelled with;
* **on the published kill cell** (`SPEC_RA / on_stratum`, n = 5,086) the recorded oracle is
  **3.872589814675139e-05**, giving `c*` = **0.547** — the ceiling is a **valid bound** and it
  **overstates** the achievable increment by **3.342×**.

The "10×" is `1.285e-03 / 1.294e-04` = 9.932, formed across **different specs, different row sets
and different SSTs**. Under D101 that pair is `NOT_COMPARABLE`.

**What survives.** There **is** a genuine breach in D084's table: `SPEC_ALL5_GLOBAL / off_stratum`
has `c*` = 2.842 and its own ceiling of 1.591e-04 is exceeded 8.08×. That is a real instance of
D125's transported-ceiling failure — **of that cell's ceiling, not of the published one.** And the
claim "off-stratum the oracle clears the floor at 1.26×" is arithmetically right (1.285e-03 /
0.00102 = 1.260) but compares an off-stratum `SPEC_ALL5_GLOBAL` oracle on n = 5,024 against a
`y_ppm` floor on n = 5,673 — two of this document's other defects stacked.

**D084's kill and D084's published number are both sound.** E1_I0047's conclusion ("the kill holds
where it matters") is right; its supporting ratio is not.

---

## D-04 — `213` NAMES TWO DIFFERENT SETS OF 213 CELLS THAT SHARE TWO MEMBERS

**Severity: a coincidence that has been read as an identity in at least six ledger entries.**

From `E1_I0036_level_artefact_sweep/CENSUS.csv`, restricted to the 1,580 kills (allowlist
`[POWERED_NULL, UNINFORMATIVE_NULL, CEILING]`, count asserted):

| set | size | quoted at |
|---|---|---|
| **A** — `kill_reason == CEILING` | **213** | D114, D117, D120, D122, D125, E1_I0047 |
| **B** — `level_recorded == player_season` | **213** | D115/D117 "550 = 213 + 337", E1_I0038, E1_I0040 |
| **A ∩ B** | **2** | — |

Jaccard **0.0047**. And **124 of the 337** `opp_team_season` kills *are* ceiling kills, so the
"550 exposed" arithmetic and the "213 ceiling kills" arithmetic **double-count 126 cells**.

`E1_I0040/DEFECTS.md` D-07(B) already noted that the 213/337 anchor "reproduces from one column and
not the other, and it does not say which". This pins it: the two columns describe **almost disjoint
sets that happen to have the same cardinality**.

**No conclusion measured here depends on it** — both counts are individually correct — but the two
must never be added, differenced or treated as the same cells.

---

## D-05 — D079's `0.001127` IS RECORDED ONLY AS A ROUNDED SCALAR AND IS **PARTIALLY VERIFIABLE**

**Severity: one of the two "dead benchmark" constants cannot be checked to its own precision.**

`E1_I0004_fga_forecast/FINDINGS.json` records
`arithmetic_ceiling_dR2_if_the_mix_term_were_a_perfect_orthogonal_predictor = 0.001127` and nothing
else. **No recorded table in that screen carries the sd of the mix term or the points move.** The
"0.196 points per sd" exists only in the D079 ledger prose, at three significant figures, while the
constant is quoted at four.

What *does* reproduce: the response (`fg_pts`), `sd_y` = 5.823572695034913, n = 10,245 / 9,238
scored, and `coef_mix_pooled` = 0.535442856732823. Inverting the published value gives a move of
0.195502 — **consistent with the prose, but consistency with a rounded sentence is not a
reproduction.** An indicative rebuild of the mix term from `forecast_frame.parquet` returned
ceilings 3.5×–24× smaller, which shows only that the zone-value and row-set conventions are not
pinned down by the artifacts.

**Marked `PARTIALLY_VERIFIABLE`. Its denominator is fully documented; its numerator is not
independently checkable.** Per the standing rule, a figure that cannot be re-derived may back no
number — so the standing comparison *"D084's ceiling is 8.7× smaller than D079's"* should be
withdrawn, for this reason **and** because the two are on different responses (7.55 vs 5.82).

---

## D-06 — E1_I0026 FLAGGED ITS OWN `t_crit(K=1)` CONVENTION AND THEN DID NOT APPLY IT

**Severity: +9.9% on the single-cell floor. Small, and in the anticonservative direction.**

`E1_I0026/NOTES.md` §4, verbatim:

> Note `t_crit(K=1) ≈ 2.00`, not 1.645: a dR2 null is right-skewed, and using a normal quantile
> would understate every per-cell threshold.

Its own `out/s04_familywise_thresholds.csv` measures q95 max-t at K = 1 as **1.999254**
(`N1_within`) and **2.002969** (`N2_entity_swap`). **Every K = 1 row of `mde_table.csv`
nevertheless carries `t_crit = 1.645`**, and so does the retrospective's `mde80_percell`
(confirmed by inverting all 1,189 increment rows: implied `t_crit` = 1.645 exactly, min = median =
max).

On the published cell the analytic MDE80 moves **0.001133 → 0.001245**. `FLOOR_1CELL` is therefore
**understated by ~10% by the screen's own stated preference.** Direction: a too-small floor makes
"below the floor" kills weaker, not stronger.

---

## D-07 — D089 PUBLISHES THREE DIFFERENT CEILINGS FOR ONE CELL AND THE LEDGER QUOTES A FOURTH SHAPE

**Severity: 8.9% spread; explains why `0.002057` and `0.0019279` both appear for the same thing.**

Same cell, same rows, same base, same response:

| form | value | where |
|---|---|---|
| per-sd, **mean** `m_hat` | **0.0020571994** | `FINDINGS.json` `CEILING_dr2_points_per_sd` — **the ledger's 0.002057** |
| per-row shift, sd form | 0.0020995386 | `FINDINGS.json` `CEILING_dr2_points_actual_shift` |
| per-row shift, `(d·d)/SST` | 0.0019278879 | `ceiling_reconciliation.csv` `D084_form_ceiling_var_share` |

All three re-derive exactly here. The first uses a **constant** mean-minutes multiplier and a
`x − x̄` centring; the third uses the **actual** residualised shift and is the only one that enters
the `c*` / ORACLE algebra. **D089's own `arithmetic_ceiling.csv` adds a fourth number for the same
conceptual cell — 0.0012290190 — on a fifth row set (n = 5,654) via the shots-per-minute route.**

The ledger phrase *"computed in D084's exact form"* is true of the third, and the number quoted is
the first.

---

## D-08 — THIS SCREEN'S OWN LIMITATIONS

1. **The points-scale floor is one cell.** One carrier (`P01_c04_prevgame`), one null (entity swap
   team-season), 600 draws, analytic MDE80. A different carrier could give a different ARM T / ARM P
   ratio. **Reported as a ratio for that reason.**
2. **The D079 rebuild is not a reproduction and is labelled as such in the run log.** It is left in
   the record rather than deleted because it is the evidence for `PARTIALLY_VERIFIABLE`.
3. **The anchor block was widened once.** A1/A2 initially failed at a 1e-15 *relative* tolerance
   because `E1_I0018/FINDINGS.json` rounds every float to **10 decimal places**, so a value of
   2.7e-05 carries ~6 significant digits. The check was moved to the absolute scale, where 10 dp is
   the binding precision, and passes at 4.7e-11. **The change is recorded here rather than made
   silently**; the identity itself was never in doubt and the frozen-frame refit (A14) confirms it
   at 4.8e-11 independently.
4. **A10 was redirected once.** `mde_table.csv`'s `mde80_s04_uncorrected` is a **simulated**
   power-surface number, not the analytic closed form, so the analytic identity could never have
   reproduced it. It was re-anchored on `retrospective_power.csv`, where the closed form is what is
   actually used, and passes at ≤1e-9 over 1,189 rows. The analytic-vs-simulated ratio is reported
   beside it (median 0.982, p10–p90 0.769–1.118), consistent with E1_I0026's published 0.984–0.989.
5. **No process was killed.** No `Get-Process | Stop-Process`, no `taskkill`, no blanket kill of any
   kind. This screen launched five short foreground `python` processes, each of which exited on its
   own; no PID required intervention.
