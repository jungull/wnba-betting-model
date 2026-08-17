# PREREG — E1_I0049_benchmark_constants

**Screen.** Census, re-derivation and denominator audit of the programme's benchmark constants.
**Write scope.** `experiments/exploration/E1_I0049_benchmark_constants/` only. Nothing else on disk
is written, moved or renamed. The shared screen kit is **imported read-only** and never modified.
**Partition.** 2021–2024 only. 2025/26 is a sealed confirmation holdout and is never read, joined,
described or inferred from. Enforced by `screenkit.assert_partition` (a VALUE test) after every
load and every filter.
**Processes.** No blanket process kill of any kind. Any PID this screen launches is recorded in
`NOTES.md` and killed only by that PID.

---

## 1. THE QUESTION

Every screen dispatched on 2026-08-08/09 was briefed with the same sentence:

> *benchmarks: largest live effect 0.002057; single-cell detection floor 0.00102; 132-cell floor
> 0.00235.*

D125 records that `0.002057` has **no recorded bound in either direction**, that D084's `0.000129`
**understates its true bound by 10×**, that only **2 of 33** ceiling tables record a control, and
that the count **213** is 173 candidates plus 40 controls. This screen asks, for each constant in
circulation:

* **Q1 — PROVENANCE.** Where was it first computed, and on what exact denominator: response, row
  set, SST basis, weighting, base, fit kind, statistic family?
* **Q2 — RE-DERIVATION.** Does it reproduce from the artifact, not from a ledger sentence or a
  summary document? Where it does not, it is marked **UNVERIFIABLE** and may back no number.
* **Q3 — IS `0.002057` DEFENSIBLE?** Compute its bound properly (`c*` and the ORACLE). Report
  `c*` for every ceiling touched, per D125.
* **Q4 — ARE THE FLOORS CONVENTION-SENSITIVE?** D103's headline moved from 56.3% to a 45%–67%
  range under convention changes (D122). Do `0.00102` and `0.00235` move too? Report as intervals
  if so.
* **Q5 — WHAT WOULD FLIP?** Which judgements made under the briefed constants change under the
  corrected ones.

## 2. THE RULE THIS SCREEN IS ABOUT — D101

**Two numbers are comparable only under identical response, row set, SST basis, weighting and
base.** Every number this screen reports — including every number it computes itself — carries its
full denominator. A comparison whose two sides do not share a denominator is reported as
`NOT_COMPARABLE` and is not converted into a ratio, however tempting the ratio is.

**Two ceiling constructions share one name (D125).** Same-scale OLS (`d = β̂·x⊥` on the scored
rows) has `c* := (d·e)/(d·d) = 1` identically and is an exact bound. A **transported** ceiling — a
per-minute coefficient multiplied by an estimated-minutes vector and scored against points, or a
ceiling carried across a fold — leaves `c*` unconstrained and is **not** a bound. `c*` is reported
for every ceiling re-derived here.

## 3. CONSTANTS UNDER CENSUS — EXPLICIT ALLOWLIST

No name-based / substring selection of candidates. The allowlist is fixed here and the resolved
list is printed with counts by every script.

| key | value as briefed | claimed origin |
|---|---|---|
| `BEST_LIVE` | 0.002057 | D089 / `E1_I0018_teammate_volume_channel` |
| `FLOOR_1CELL` | 0.00102 | D103 / `E1_I0026_detection_floor` |
| `FLOOR_132` | 0.00235 | D103 / `E1_I0026_detection_floor` |
| `D084_CEILING` | 0.000129 | D084 / `E1_I0004_efficiency_transfer_v2` |
| `D079_CEILING` | 0.001127 | D079 / `E1_I0004_fga_forecast` |
| `N_APPEARED` | 13,879 | D076 / `E0_I0014_residual_heterogeneity` |
| `N_CEILING_KILLS` | 213 | D097 via `E1_I0036` census |
| `N_DECISION` | decision-stratum n | D081/D089/D097/D103 (values differ — that is the finding) |
| `BEST_EVER_LEAD` | 0.0023 | D089 walk-forward |
| `D103_BLIND` | 56.3% | D103, restated 45%–67% at D122 |

Any further recurring constant surfaced by the s01 sweep is added to `CENSUS.csv` with its
provenance and is named in `NOTES.md` as an addition, with the count of additions and drops.

## 4. ANCHORS — REPRODUCED BEFORE ANY NEW STATISTIC

Nothing new is computed until these pass. Each is a *recorded* number reproduced from the
artifact's own recorded inputs or from the frozen frame.

| id | anchor | source | tolerance |
|---|---|---|---|
| A1 | `CEILING_dr2_points_per_sd` = (points_move_per_sd / sd_y_points)², all 16 D089 cells | `E1_I0018/FINDINGS.json` | 1e-15 rel |
| A2 | `CEILING_dr2_points_actual_shift` = (points_move_sd / sd_y_points)², all 16 | same | 1e-15 rel |
| A3 | D089 headline `0.002057` = row `DECISION\|B_COMPLETE\|P01_c04_prevgame` | same | exact to 6 dp |
| A4 | D089 reconciliation identity `realised = (2c*−1)·var_share`, all 16 rows | `E1_I0018/ceiling_reconciliation.csv` | 1e-12 rel |
| A5 | D089 reconciliation identity `oracle = c*²·var_share`, all 16 rows | same | 1e-12 rel |
| A6 | D084 `CEILING_A_perfect_orthogonal_dR2` = (points_moved_by_1sd / sd_y)², all 9 rows | `E1_I0004_efficiency_transfer_v2/arithmetic_ceiling.csv` | 1e-15 rel |
| A7 | D084 headline `0.00012940370236262536` on `SPEC_RA / on_stratum`, n 5,086 | same | exact |
| A8 | D089 volume-route `CEILING_dr2_points` from its own 5 components, all 8 rows | `E1_I0018/arithmetic_ceiling.csv` | 1e-15 rel |
| A9 | D103 blindness `760/1349 = 0.5633802816901409` | `E1_I0026/retrospective_power.csv` or FINDINGS | 1e-16 |
| A10 | E1_I0026 analytic MDE80 `(√(μ+t·σ) + 0.8416√μ)²` reproduces `mde80_s04_uncorrected` | `E1_I0026/mde_table.csv` | 1e-9 rel |
| A11 | D076 `13,879` appeared player-games, 2022–2024 | frozen frame used by D089/E1_I0031 | exact |
| A12 | D089 DECISION row count 5,673 from `n_prior≥8 & prior5_minutes≥24` on the frozen frame | `E1_I0018/screen_frame.parquet` | exact |
| A13 | `213 = 173 candidates + 40 controls` and `20 G01_noise + 20 G02_placebo_noop` | `E1_I0047/EXPOSURE_213.csv` | exact |
| A14 | E1_I0018 `paired_dr2_points` for the `0.002057` cell reproduced by refit from the frozen frame | `E1_I0018/screen_frame.parquet` | 1e-10 |

**If fewer than 10 anchors pass, the screen stops and reports that instead.**

## 5. RE-DERIVATION PROTOCOL

For each constant: go to the **artifact**, never the ledger sentence. Record

`response · row set (n and definition) · SST basis · weighting · base · fit kind (in-sample /
walk-forward / transported) · statistic family (OLS ΔR² / paired-forecast ΔR² / variance share) ·
seasons`

and the source value, the re-derived value, and the signed delta. A constant that cannot be
re-derived from an artifact is **UNVERIFIABLE** and is recorded as such — that is a first-class
result, not a failure of the screen.

## 6. Q3 — THE BOUND FOR `0.002057`, PREREGISTERED BEFORE COMPUTING IT

On the frozen frame `E1_I0018/screen_frame.parquet`, DECISION stratum, base `B_COMPLETE`, candidate
`P01_c04_prevgame`, exactly as `E1_I0018/s04_points.py` does it:

```
d   = (fitted_with(x) − fitted_base) · m_hat        the transported forecast shift, in points
e   = y_pts − fitted_base · m_hat                   the reference's points residual
SST = Σ(y_pts − ȳ_pts)²
c*      = (d·e)/(d·d)
ORACLE  = (d·e)²/((d·d)·SST)          the bound over all rescalings of d
realised= (2 d·e − d·d)/SST
```

**Preregistered dispositions.** `c* ≤ 1` → `0.002057` is a bound and is defensible as one.
`c* > 1` → it is not a bound, the true bound is the ORACLE, and the understatement factor is `c*²`.
Both outcomes are published. The three ceiling variants D089 records for this cell
(`per_sd`, `actual_shift`, `var_share`) are all reported; **no variant is selected after seeing
which is largest or smallest.**

## 7. Q4 — CONVENTION SENSITIVITY OF THE FLOORS, PREREGISTERED GRID

`FLOOR_1CELL` and `FLOOR_132` are read off one cell of a 180-row surface. The grid below is fixed
here; **every cell is reported, none is selected.**

* **C1 — null**: entity-swap team-season (as published) vs the other four nulls E1_I0026 measured.
* **C2 — base**: `B_COMPLETE` (as published) vs `B_SINGLE`.
* **C3 — stratum**: `DECISION` n=5,673 (as published) vs `POOLED` n=14,852.
* **C4 — drift correction**: drift-corrected (as published) vs uncorrected — both on disk at
  `mde_table.csv`.
* **C5 — family size**: K = 1, 18, 44, 132 (as published).
* **C6 — RESPONSE.** `E1_I0026/scripts/df_base.py:51` fixes `OUTCOME = "y_ppm"`. Every constant
  the floor is quoted against (`0.002057`, `0.001127`, `0.000129`) is on a **points** response.
  This screen measures the same null on the same rows with the same base **on the points-scale
  transported statistic D089 actually used**, and reports both floors side by side.
  600 draws, seed `20260809`, `screenkit.entity_swap_null`, `date_col="game_date"`,
  `season_col="season"`, `tiebreak_col="game_id"` — E1_I0026's own call, unchanged.

**Reported as an interval** if any convention moves a floor by more than 10%; as a point value
otherwise. The published cell is always named as the published cell.

## 8. STORAGE

Every null draw is stored **raw, signed and unstandardised**, with the full stratum key on every
row (`stratum|base|null|carrier|response|statistic`). No absolute values, no standardisation. 117
cells in this programme are permanently unauditable because one screen stored standardised draws
and 24 more because a stratum key was omitted; that is not repeated here.

## 9. WHAT THIS SCREEN WILL NOT DO

* It will not fit a champion, tune anything, or enact any production change.
* It will not repair any file outside its own directory, including the ones it finds defects in.
* It will not manufacture a discrepancy. **"The constants are all correct as recorded" is the most
  valuable available outcome** and will be reported as-is if that is what the arithmetic says.
* It will not convert a `NOT_COMPARABLE` pair into a ratio.
* Every document produced carries, in the same document, the result that most weakens its own
  conclusion.

## 10. DELIVERABLES

`PREREG.md` + `.sha256` · `REFERENCE_CARD.md` · `CENSUS.csv` · `RE_DERIVATION.csv` ·
`WHAT_WOULD_FLIP.md` · `FINDINGS.json` · `NOTES.md` · `DEFECTS.md` · `scripts/` with run logs ·
`raw/` with signed unstandardised draws.
