# REFERENCE CARD — the programme's benchmark constants, corrected

**Quote this file, not the coordinator's memory.**
Screen `E1_I0049_benchmark_constants` · PREREG sha256
`4770c3ac21a3e4e4d1c3e277d59dd7b49f1403d7e459e355b851945b58f23dfc`
Partition 2021–2024. **2025/26 never opened.** 22 anchors reproduced before any new statistic,
13 at 1e-16 or better. Evidence: `CENSUS.csv`, `RE_DERIVATION.csv`, `WHAT_WOULD_FLIP.md`,
`raw/s03_null_draws_signed_raw.{npz,csv}`, `scripts/run_log_s0{1..5}.txt`.

---

## THE ONE-PARAGRAPH VERSION

**The arithmetic is almost entirely correct.** Every constant re-derives from its artifact except
D079's `0.001127`, which exists only as a rounded scalar. **What is wrong is the vocabulary.**
`0.002057` is not "the programme's largest live effect": it is an in-sample *transported ceiling*
whose own cell's realised increment exceeds it by 61%, whose `c*` is 1.359 so it is not a bound at
all, and whose true bound is 1.73× larger. The programme's largest live *effect* is a different
number on a different row set. The two detection floors re-derive exactly but are measured on
`y_ppm`, while every constant they are quoted against is on a **points** response. **No killed cell
reopens and no gate flips.**

---

## THE CARD

Copy the whole row. A value without its denominator is not quotable.

### 1 — `BEST_LIVE` — **do not use `0.002057` as an effect**

| | |
|---|---|
| **as briefed** | "largest live effect **0.002057**" |
| **what it actually is** | an **in-sample TRANSPORTED arithmetic CEILING** (D125's unsafe class) |
| **origin** | D089 · `E1_I0018_teammate_volume_channel/FINDINGS.json` → `STEP_4…/in_sample_coefficient[13]/CEILING_dr2_points_per_sd` |
| **response** | `y_pts` — **total box points** |
| **row set** | `DECISION`, **n = 5,673** (`n_prior≥8 & prior5_minutes≥24`), seasons **2021–2024** |
| **SST basis** | `Σ(y_pts − ȳ)²`, about the **unweighted** mean (D069) |
| **weighting** | none |
| **base** | `[1, refB_ppm, refB_spm, refB_pps, refB_mpg]` (`B_COMPLETE`) |
| **fit kind** | in-sample OLS **on `y_ppm`**, transported to points by the **mean** of `m_hat` |
| **statistic** | variance share `(|β̂|·sd(x)·mean(m_hat) / sd(y_pts))²` |
| **re-derived** | **0.0020571994** — exact from the frozen frame |
| **`c*` = (d·e)/(d·d)** | **1.3594722754 → NOT A BOUND** |
| **true bound (ORACLE)** | **0.0035630546** = **1.732×** the published figure |
| **realised, same cell** | **0.0033139323** = **1.611×** the published figure |
| **control (measured here, first time)** | 600 matched entity-swap draws: null mean 1.357e-04, **q95 5.276e-04**. The ceiling is **3.65×** its own q95, **p = 0.0017 — IT CLEARS.** |

**D089 records three different ceilings for this one cell**, spread 8.9%:
`0.0020571994` (per-sd, mean minutes) · `0.0020995386` (per-row shift sd) · `0.0019278879`
(`(d·d)/SST`). The ledger quotes the first; the reconciliation table quotes the third.

### 2 — the number you probably wanted: `BEST_EVER_LEAD`

| | |
|---|---|
| **value** | **0.0023492235735382717** (ledger's "0.0023") |
| **what it is** | a **REALISED walk-forward effect** — the thing `0.002057` gets mistaken for |
| **origin** | D089 · `E1_I0018/walkforward_points.csv`, verified on bytes by the coordinator |
| **response** | `y_pts` (points) |
| **row set** | `DECISION`, walk-forward **scored** rows, **n = 4,517**, seasons **2022–2024** |
| **SST basis** | `Σ(y_pts − ȳ)²` on the scored rows, unweighted |
| **base** | `B_COMPLETE` own-prior · **fit**: walk-forward |
| **statistic** | paired-forecast ΔR², cluster sign-flip at team-season, cluster p 0.0345 |
| **control** | `G01_noise` 0.000266 at p 0.463 — behaved |
| **bound** | none recorded |

**It is 1.142× the ceiling that was supposed to bound it** — because they are on different row sets
(4,517 vs 5,673) and different seasons. Under D101 the pair is **NOT_COMPARABLE**; the same-row-set
comparison is 0.0033139 against 0.0020572, a 1.611× breach.

**There is no single "largest live effect."** The honest statement is a table
(`raw/_s04_largest_effect_candidates.csv`): D089 walk-forward 0.0023492 (n=4,517, points);
D089 in-sample same-cell 0.0033139 (n=5,673, points); D089 in-sample `B_SINGLE` 0.0038420
(n=5,673); D108 0.002951 (n=5,111, points, OLS increment). Three responses, four row sets, three
statistic families. **If a brief needs one number, use 0.0023492 and name its denominator.**

### 3 — `FLOOR_1CELL` — `0.00102`, and it is on the wrong response

| | |
|---|---|
| **as briefed** | "single-cell detection floor **0.00102**" |
| **origin** | D103 · `E1_I0026_detection_floor/mde_table.csv`, `DECISION \| B_COMPLETE \| N_B_entity_swap_team_season \| K=1` |
| **response** | **`y_ppm` — points PER MINUTE** (`scripts/df_base.py:51`, `OUTCOME = "y_ppm"`) |
| **row set** | `DECISION`, **n = 5,673**, seasons 2021–2024, D089 frame ⋈ D085 frame |
| **SST basis** | `Σ(y_ppm − ȳ)²`, unweighted · **weighting** none |
| **base** | `[1, refB_ppm, refB_spm, refB_pps, refB_mpg]` |
| **null** | entity swap **team-season**, 48 clusters, 600 draws, seed 20260808 |
| **statistic** | OLS increment ΔR², drift-corrected MDE80 at 80% power, `t_crit(K=1) = 1.645` |
| **re-derived** | null mean **1.661220e-04** and sd **2.152857e-04** reproduced from the frozen frame at **7.3e-17** and **1.9e-17**; real ΔR² at **3.6e-17** |
| **control** | type-I 0.040–0.069 (nominal 0.05) across all 24 design cells |
| **CONVENTION-SENSITIVE** | **YES — report as an interval** |

**Intervals** (all `DECISION`, drift-corrected, from D103's own published surface):

| axis | range |
|---|---|
| across the five nulls × two bases, K=1 | **0.00091 … 0.00336** (published 0.00102) |
| drift correction on/off, published cell | 0.00102 (corrected) vs **0.00164** (uncorrected) |
| `t_crit(K=1)` 1.645 (published) vs the screen's **own** empirical q95 max-t ≈ 2.00 | 0.001133 → **0.001245** (+9.9%) |
| **response**, measured here | **0.704× → points-scale ≈ 0.00072** |

### 4 — `FLOOR_132` — `0.00235`, same caveats

| | |
|---|---|
| **origin** | same cell, `family_size_K = 132`, `t_crit = 6.974475` from the real 154-cell max-t matrix |
| **response / rows / base / null** | **identical to `FLOOR_1CELL`** — `y_ppm`, n = 5,673, `B_COMPLETE`, entity swap team-season |
| **re-derived** | reproduces from `mde_table.csv`; the null moments behind it reproduce at 1e-17 |
| **interval, DECISION stratum, across nulls × bases** | **0.00235 … 0.00974** |
| **note** | the published 0.00235 is the **minimum** of its own DECISION-stratum range |
| **response-matched (points), measured here** | 0.770× → **≈ 0.00181** |

### 5 — `D084_CEILING` — `0.000129` — **correct, and a valid bound**

| | |
|---|---|
| **origin** | D084 · `E1_I0004_efficiency_transfer_v2/arithmetic_ceiling.csv`, `SPEC_RA / on_stratum` |
| **response** | points (total box), `sd_y = 7.550491622813534` |
| **row set** | **n = 5,086** on-stratum of an 11,267-row efficiency frame · **weighting** none |
| **fit / statistic** | in-sample transported; variance share `(move_per_1sd / sd_y)²` |
| **re-derived** | **0.00012940370236262536** — exact, `|Δ| = 2.5e-17` |
| **`c*` on its own cell** | **0.547 → the ceiling IS a valid bound here** |
| **own-cell ORACLE** | 3.872589814675139e-05 — the ceiling **overstates** the true bound by **3.342×** |

**Correction to D125 / E1_I0047.** The claim that this figure "understates its true bound by 10×"
compares `SPEC_ALL5_GLOBAL / off_stratum` (n = 5,024, `sd_y` = 5.318) against
`SPEC_RA / on_stratum` (n = 5,086, `sd_y` = 7.550) — **different spec, different rows, different
SST**. Under D101 that pair is `NOT_COMPARABLE`. The largest oracle *anywhere* in D084's table is
1.285e-03 and it belongs to a different cell whose own ceiling is 1.591e-04 (`c*` = 2.842, a
genuine breach — but of that cell's ceiling, not of the published one). **D084's kill stands and
its published number is sound.**

### 6 — `D079_CEILING` — `0.001127` — **PARTIALLY VERIFIABLE**

| | |
|---|---|
| **origin** | D079 · `E1_I0004_fga_forecast/FINDINGS.json` — **a bare rounded scalar** |
| **response** | **`fg_pts` — FIELD-GOAL points only**, `sd_y = 5.823572695034913`. **Not** total box points. |
| **row set** | n = 10,245 frame / **9,238 scored** · **weighting** none |
| **base** | `pts ~ 1 + FGAhat · Σ_z(S1_z q_z v_z)` · **fit** pooled in-sample |
| **what re-derives** | the response, `sd_y`, and `coef_mix_pooled` (0.535442856732823) all reproduce |
| **what does not** | no recorded `sd` of the mix term and no recorded move. The "0.196 points per sd" exists only in ledger prose. Inverting the published value gives 0.195502 — consistent, not a reproduction. |
| **status** | **PARTIALLY VERIFIABLE — the denominator is documented, the numerator is not independently checkable from any artifact.** |

**D079 is on field-goal points (sd 5.82) and D084 is on total box points (sd 7.55).** D084 disclosed
this at the time. The standing "D084's ceiling is 8.7× smaller than D079's" is a **cross-response**
ratio and should be dropped.

### 7 — counts

| constant | correct value |
|---|---|
| ceiling kills | **173 candidates + 40 controls = 213**. Controls are exactly `G01_noise` ×20 and `G02_placebo_noop` ×20. **Never quote 213 as a candidate count.** |
| **`213` is ambiguous** | Two different sets of exactly 213 cells carry this number: (A) cells killed on arithmetic ceiling; (B) killed cells recorded at `player_season` level, the "213" of D115/D117's "550 = 213 + 337". **\|A ∩ B\| = 2.** Jaccard 0.0047. Always say which. |
| `550 = 213 + 337` | the level counts. **124 of the 337 are themselves ceiling kills**, so the "550 exposed" and "213 ceiling kills" arithmetics double-count 126 cells. |
| `13,879` | D076 appeared player-games, **tier-A, seasons 2022–2024 only** (not 2021). Reproduces exactly, repeatedly. **The most reliable constant in the programme.** |
| `56.3%` | D103 blindness = 760/1349 = 0.5633802816901409, exact. **Superseded by D122: report the interval 45.44% – 67.31%.** |

### 8 — "the decision stratum" names **four different row sets**

| n | where | predicate / frame |
|---|---|---|
| **5,673** | D089 points step, **D103's floors** | `n_prior≥8 & prior5_minutes≥24`, finite on `y_ppm,y_pts,m_hat,B_COMPLETE`; D089 frame (14,852) — **verified exactly** |
| **5,654** | D089 `arithmetic_ceiling.csv` (volume route) | same predicate **plus** finite `y_spm,y_pps` — **verified exactly** |
| **5,111** | D097 / the 213 | `n_prior≥8 & ref_trail5_minutes≥24` on D097's 14,327-row frame |
| **5,086** | D084 on-stratum | same idea on the 11,267-row efficiency frame |

The programme's standing comparison — D084's `0.000129` (n = 5,086) and D079's `0.001127`
(n = 9,238 scored, different response) against D103's floor (n = 5,673, different response) —
**crosses all of them.**

---

## THE RESPONSE MISMATCH, MEASURED

`E1_I0026/scripts/df_base.py:51` fixes `OUTCOME = "y_ppm"`. The floors are ΔR² on **points per
minute**. `0.002057`, `0.000129` and every ceiling compared against them are ΔR² on **points**.

Same rows (n = 5,673), same base, same carrier, same null, **one shared sequence of 600 entity-swap
draws** (seed 20260808), three matched arms:

| arm | response | statistic | null mean | null q95 | MDE80 K=1 | MDE80 K=132 |
|---|---|---|---|---|---|---|
| **P** | `y_ppm` | OLS increment ΔR² | 1.661e-04 | 6.538e-04 | 0.001133 | 0.002671 |
| **T** | `y_pts` | D089's own `(2d·e−d·d)/SST` | 9.695e-05 | 4.517e-04 | **0.000798** | **0.002058** |
| **C** | `y_pts` | the ceiling `(d·d)/SST` | 1.357e-04 | 5.276e-04 | 0.000925 | 0.002180 |

**ARM T / ARM P = 0.704× at K = 1 and 0.770× at K = 132.** Applying those to the published
drift-corrected floors gives **points-scale floors of ≈ 0.00072 and ≈ 0.00181**.

**Direction:** the published floors are ~30% **too high** for points-scale statistics. Every
"the ceiling is X× below the floor" kill argument in the record was therefore **slightly weaker
than stated**, and every "the effect is X× above the floor" claim was **slightly understated**.
Nothing in the record moves far enough to change a verdict — see `WHAT_WOULD_FLIP.md`.

---

## RULES FOR THE NEXT BRIEF

1. **Never write "largest live effect 0.002057."** Write either
   *"D089's largest live effect, walk-forward paired-forecast ΔR² = 0.0023492 on points, n = 4,517,
   2022–2024"* or *"D089's transported ceiling 0.0020572 (c\* = 1.359, not a bound; true bound
   0.0035631), points, n = 5,673."*
2. **Quote a floor with its response.** `0.00102` and `0.00235` are `y_ppm` floors. On a points
   statistic use ≈ 0.00072 / ≈ 0.00181, or say the comparison is approximate.
3. **Quote floors as intervals**, or name the null: `0.00091–0.00336` (K=1) and `0.00235–0.00974`
   (K=132) on the DECISION stratum.
4. **Every ceiling carries `c*`.** No `c*`, no bound claim.
5. **Every ceiling carries a matched control.** It costs 600 draws through the same path; it took
   0.7 seconds here for the programme's most-cited ceiling.
6. **Say which 213 you mean**, and say 173 when you mean candidates.
7. **State the full denominator** — response · row set · SST basis · weighting · base · fit kind ·
   statistic family — or mark the comparison `NOT_COMPARABLE`.

---

## WHAT MOST WEAKENS THIS CARD

* **Two of the four ceiling constants are arithmetically perfect.** `0.002057` re-derives to the
  digit and `0.000129` re-derives at 2.5e-17. The problem is naming and comparison, not arithmetic.
* **D089's ceiling clears its own newly-measured control at p = 0.0017.** The "only 2 of 33 ceiling
  tables record a control" alarm turns out to be **benign** for the constant it was raised about.
* **The points-scale floors here are indicative, not a replacement surface.** They come from one
  carrier, one null, 600 draws, and the *analytic* MDE80 closed form rather than E1_I0026's
  drift-corrected fixed-point solve. **The defensible output is the ratio 0.704 / 0.770**, not the
  absolute numbers.
* **Nothing reopens.** No killed cell, no gate, no verdict changes. The largest single correction in
  this document is a factor of 1.73 on one number.
