# BOUND OR NOT — E1_I0047_ceiling_validity

Screen `E1_I0047_ceiling_validity` · `PREREG.md` sha256
`abbf0077ceb179b076646aeef5eda6ae2efeeced931fe87c69801ce6fc9b4994`
Partition 2021–2024. **2025/26 never opened.** Evidence: `EXPOSURE_213.csv`, `REMEASURE_30.csv`,
`NONLINEAR_NULLS.csv`, `COMPONENT_INJECTION.csv`, `CEILING_FORMS_CENSUS.csv`,
`COUNTEREXAMPLE/`, `scripts/run_log_s0{1..7}.txt`, `nulls/*.npz`.

---

## THE VERDICT, IN THREE SENTENCES

**`(d·d)/SST` is an upper bound on ΔR² if and only if `c* := (d·e)/(d·d) ≤ 1`, and it is a bound
with *exact equality* — not merely a bound — whenever the shift `d` is the OLS fitted contribution
of the candidate on the same rows, response, SST and base the increment is scored on.**
**Every one of the 213 ceiling kills is that case: all 213 come from a single screen (D097,
`E0_I0024`), all use a single construction, `c* = 1` holds to 2.2e-16, and the recorded form is the
realised increment multiplied by the variance-inflation factor, so it exceeds what it bounds on
every one of D097's 250 recorded cells with a minimum gap of exactly `+0.000e+00`.**
**E1_I0043's finding is correct but applies to a different construction: where the shift is
*transported* — a rate coefficient multiplied by an estimated-minutes vector and scored against
points, or carried across a fold boundary — `c*` is unconstrained, and the statistic is exceeded by
the realised increment in 35 of 64 rows of D098's own recorded table, including on D098's own
headline cell, by 46%.**

**All 213 are safe. 64 are safe on margin alone before any work. None reopens.**

---

## ANCHORS REPRODUCED BEFORE ANY NEW STATISTIC

| id | anchor | recorded | reproduced | \|diff\| |
|---|---|---|---|---|
| A1 | D097 `CEILING_dr2_residualised` ≡ `dr2`, 250 cells | — | — | **2.711e-20** |
| A2 | D097 `CEILING_dr2_D089form` ≡ `dr2 × VIF`, 250 cells | — | — | **1.440e-16** |
| A2b | D097 ceiling ≥ realised, 250 cells | — | 0 violations | **min gap +0.000e+00** |
| A3 | `DECISION\|y_oreb\|B_COMPLETE\|R08` dr2, n 5,111 | 0.001145976477 | 0.001145976477 | **3.318e-17** |
| A4 | `POOLED\|y_oreb\|B_COMPLETE\|R08` dr2, n 13,784 | 0.006488115970 | 0.006488115970 | **4.250e-17** |
| A5 | E1_I0023 max negative-control `ceiling_1sd_form` | 4.375669e-03 | 4.375669e-03 | 1.871e-10 |
| A6 | E1_I0023 disclosed control cell | 3.979894e-04 | 3.979894e-04 | 3.972e-11 |
| A7 | E1_I0023 D098 headline ceiling | 0.01280821 | 0.01280821 | 3.920e-09 |
| A8 | E1_I0043 `CEILING_MATCHED.csv` (48×20) loaded | — | — | — |

**9 of 9 pass.** Plus, in s04, **all 30 re-measured cells reproduce D097 exactly**: 0 row-count
mismatches, max |Δdr2| 9.920e-17, max |Δceiling| 9.953e-17. Plus E1_I0036's published eligibility
count reproduces exactly (118 of 1,580 = 7.5%). **41 reproductions, 32 of them at ≤1e-16.**

---

## 1. THE ALGEBRA

With `e = y − ŷ_base`, `d` the forecast shift, `SST = Σ(y−ȳ)²` on the scored rows:

```
SSE_base = e·e
SSE_new  = (e−d)·(e−d) = e·e − 2 d·e + d·d
ΔR²      = (2 d·e − d·d)/SST                                                   [1]

(d·d)/SST ≥ ΔR²   ⟺   d·d ≥ 2 d·e − d·d   ⟺   d·e ≤ d·d   ⟺   c* ≤ 1          [2]
ORACLE   := max_c (2c d·e − c² d·d)/SST = (d·e)²/((d·d)·SST) = c*² · (d·d)/SST  [3]
```

So the statistic is a bound iff `c* ≤ 1`, and **`c*²` is exactly the factor by which it understates
the achievable increment**. Verified numerically in `scripts/s02_bound_or_not.py`: at `c* = 2` the
three quantities are 4.710e-04 / 1.884e-03 / 1.413e-03 and the bound fails; at `c* = 0.667` it holds
loosely.

### The sufficient condition, which is the one that matters

If `d = β̂ x⊥` with `β̂ = (x⊥·e)/(x⊥·x⊥)` — the Frisch–Waugh OLS contribution on the same rows —
then `d·e = β̂(x⊥·e) = β̂²(x⊥·x⊥) = d·d` **identically**. Hence `c* = 1`, and

```
(d·d)/SST  =  ORACLE  =  ΔR²        — one number, not three.
```

**Under what assumptions IS it an upper bound, and do they hold here?** The assumption is *scale*:
the shift must be applied at no less than its optimal coefficient. Same-rows OLS satisfies it with
equality by construction. **Orthogonality of the candidate to the base is not required and is not
the failing assumption** — see §3.

---

## 2. THE FORM THE 213 ACTUALLY USE

Established from source before any measurement: `E1_I0036/scripts/s07_census.py` populates
`ceiling_recorded` for **exactly one** screen — `E0_I0024` (D097), from `CEILING_dr2_D089form`.
Every other SPEC passes `ceiling=None`. So all 213 CEILING kills share one construction:

```
C-RAWSD  =  (|β̂| · sd(x) / sd(y))²        E0_I0024/s04_screen.py line 171
C-RESID  =  (|β̂| · sd(x⊥) / sd(y))²       E0_I0024/s04_screen.py line 172
```

Because the base carries an intercept, `mean(x⊥) = 0`, so `sd(x⊥)² = (x⊥·x⊥)/(n−1)` and
`sd(y)² = SST/(n−1)`. Therefore

```
C-RESID = β̂²(x⊥·x⊥)/SST = ΔR²           EXACTLY        (A1: 2.711e-20)
C-RAWSD = ΔR² × (sd(x)/sd(x⊥))² = ΔR² × VIF            (A2: 1.440e-16)
```

with `VIF = 1/(1 − R²_{x∼base}) ≥ 1` always. **The raw-sd form is the realised increment inflated
by the variance-inflation factor. It cannot fall below what it bounds.**

The identical structure holds in the only other screen that wrote the same pair of columns,
`E0_I0029` (D108): max |C-RESID − ΔR²| = 3.331e-16, min (C-RAWSD − ΔR²) = **+0.000e+00**, 0 of 96
violations.

---

## 3. THE ORTHOGONALITY SUSPICION IS EXACTLY INVERTED

The brief nominated non-orthogonality as the obvious suspect. It was checked, not assumed.

| | value |
|---|---|
| VIF across the 213: min | **1.0000000461** |
| median | 1.004196 |
| max | 1.678582 |
| cells with VIF < 1 (the only way C-RAWSD could fail) | **0** |
| cells effectively orthogonal (VIF < 1.01) | 140 of 213 (65.7%) |

An **exactly orthogonal** candidate is the *worst* case for this form: VIF = 1, zero slack, and the
ceiling equals the realised increment. Correlation with the base only *adds* slack. A 1,000-draw
sweep of the candidate–base correlation from 0 to 0.99 (`COUNTEREXAMPLE/collinearity_probe.csv`)
gives max |c* − 1| = **6.772e-15** and min (varshare/realised) = **0.999999999999996**; the bound
never fails and the raw-sd form's VIF rises to 57× at the collinear end.

**The failing assumption is scale, not orthogonality.** The minimal counterexample
(`COUNTEREXAMPLE/minimal_counterexample.npz`) is n = 3, `y = (−1,0,1)`, base = intercept only,
candidate `x = (−1,0,1)` — *exactly orthogonal to the base* — with the shift applied at half its
optimal coefficient: `(d·d)/SST = 0.25` against a realised `ΔR² = 0.75`. The bound is exceeded 3×
by a perfectly orthogonal candidate.

---

## 4. WHERE IT REALLY FAILS — AND IT IS NOT A SYNTHETIC CASE

`COUNTEREXAMPLE/live_counterexamples.csv`. Discovery rule was column presence, not names: any
recorded table carrying both a ceiling column and a realised-increment column computed by its own
screen inside one loop iteration on one `(d, e, SST)` triple.

| table | rows | realised > ceiling | c* range | max ratio |
|---|---|---|---|---|
| `E1_I0023/arithmetic_ceiling.csv` | 64 | **35 (54.7%)** | −23.17 … 2.45 | **3.903** |
| `E1_I0043/CEILING_MATCHED.csv` | 48 | **34** | −0.069 … 8.43 | **15.861** |
| `E0_I0024/upstream_signals.csv` (**the 213**) | 250 | **0** | ≡ 1 | — |

### The counterexample is D098's own headline cell

`A10_opp_defrtg / DECISION / T3_high_usage / MAIN_EFFECT / walk_forward`, n = 1,687:

| quantity | value |
|---|---|
| ceiling `(d·d)/SST` — the number D098 published | **0.01280821** |
| realised `(2 d·e − d·d)/SST` — what the same shift bought | **0.01870281** |
| ORACLE `(d·e)²/((d·d)·SST)` | 0.01938101 |
| `c*` | 1.230110 |
| **realised / ceiling** | **1.4602 — the bound is exceeded by 46%** |

This is in the artifact E1_I0023 wrote in August 2026. E1_I0043 diagnosed the mechanism correctly
and did not find this instance because it was looking at the noise floor of the same cell.

### The mechanism, isolated

Splitting E1_I0023's table by fit kind: `in_sample` c* mean 0.330 (sd 4.30), 17 of 32 exceed;
`walk_forward` c* mean 1.016 (sd 0.680), 18 of 32 exceed. **Both fail.** Out-of-sample-ness is *not*
the operative condition — both arms transport a points-per-minute coefficient onto a points response
via an estimated-minutes vector. **Transport is the operative condition.**

Reproduced independently inside D097's own data (`REMEASURE_30.csv`, ARM 4): fitting the same 30
candidates on strictly earlier seasons and scoring on the eval season gives c* from −0.98 to 2.49,
with c* > 1 and the variance-share form failing as a bound in **9 of 30 cells**.

---

## 5. THE EXPOSURE ACROSS THE 213 — `EXPOSURE_213.csv`

`U` = the factor by which the true achievable ceiling could exceed the computed one = `c*² / VIF`.

| | |
|---|---|
| `c*` for all 213 | **1, exactly** (A3/A4 \|c*−1\| ≤ 2.2e-16) |
| cells with `U > 1` (genuine understatement) | **0 of 213** |
| `U` range | 0.5957 … 0.99999995 — the computed ceiling **overstates** the true one by up to 1.68× |
| **AT_RISK** (`true_ceiling_upper ≥ FLOOR_1CELL`) | **0 of 213** |
| **SAFE_BY_MARGIN (≥100×) — before any expensive work** | **64 of 213 (30.0%)** |
| SAFE_BY_CONSTRUCTION (C ≥ R verified and U ≤ 1) | **213 of 213 (100%)** |
| of which trivially degenerate (ceiling ≡ realised ≡ 0) | 20 |

Margin `= FLOOR_1CELL / ceiling`: min **1.28×**, median 21.67×; ≥1000× in 37, ≥100× in 64, ≥30× in
86, ≥10× in 135, ≥3× in 193, ≥1× in all 213.

**The decisive number is not the margin.** Because `U ≤ 1`, `true_ceiling_upper = realised ΔR²`, and:

| | |
|---|---|
| the 213's realised ΔR² ≥ FLOOR_1CELL (0.00102) | **0** |
| ≥ FLOOR_132 (0.00235) | **0** |
| ≥ BEST_LIVE (0.002057) | **0** |
| ≥ each cell's **own** injection-verified `mde80_fw` | **0** (min margin 2.05×, median 48.5×) |
| **max realised ΔR² among all 213** | **0.00079634 = 0.7807× the single-cell floor** |

Ranking by `U × (gap to floor)` is therefore ranking by realised effect over floor, and the top of
that list — `DECISION | y_dreb | B_SINGLE | R02_opp_allowed_ra_share` — sits at 0.78× the floor.

---

## 6. RE-MEASUREMENT — `REMEASURE_30.csv`

Preregistered rule (§6 of PREREG, applied without amendment): margin < 10× **or** top 25 by ceiling
**or** identity failure; 78 selected, capped at 30 by rank score, 48 recorded as
selected-but-not-run. Selection used recorded numeric columns only.

### Decision-stratum intersection, reported first

`DECISION = n_prior ≥ 8 AND ref_trail5_minutes ≥ 24` (D097's own definition, verbatim).
Frame 14,327 rows → `n_prior ≥ 8` 10,688 → `ref_trail5_minutes ≥ 24` 6,352 →
**intersection 5,111 (35.67% of the frame)**, agreeing with the frame's own `DECISION` column
exactly. By season 2022 / 2023 / 2024 = 1,559 / 1,776 / 1,776. 132 distinct players,
36 opponent-team-seasons. **20 of the 30 re-measured cells are on DECISION; 10 on POOLED.**

### Frozen vs refit intercept — both published

| | |
|---|---|
| max frozen/refit ratio | 0.9999 |
| min frozen/refit ratio | **0.0067** |
| cells where frozen > refit | **0** |

The intercept matters enormously for `B_SINGLE` cells (ratios 0.007–0.10) and barely at all for
`B_COMPLETE` (0.95–1.00). Freezing the intercept **shrinks** every statistic; no conclusion here
depends on which is used, and both are in the table.

### Clean window 2023–2024, SST recomputed on those rows

n 3,552–9,571. Max ΔR² 1.422e-03 = 1.39× FLOOR_1CELL, in **1** cell
(`DECISION | y_oreb | B_SINGLE | R07_own_miss_pg`). max |c* − 1| = 1.998e-15 — the identity survives
the window change, as the algebra requires. This one cell is the only clean-window crossing and it
sits on the thinnest base in the set (`B_SINGLE`, one column); its `B_COMPLETE` sibling does not
cross. It is reported, not promoted.

### Nonlinear headroom — the one route by which a true ceiling *can* exceed

The linear ceiling says nothing about a nonlinear use of the candidate. Entering each candidate as
an orthogonal cubic polynomial plus quartile indicators (6 columns) on the same rows/response/SST/
base gives arm3/ceiling ratios of 1.12–3.06 (median 2.07) and **exceeds the recorded ceiling in 30
of 30 cells**, with 12 of 30 crossing FLOOR_1CELL.

**That is not a reopening, and this screen committed the D101 error against itself to find out.**
A 6-column statistic was being compared against a 1-column floor. `E[ΔR² | null] ≈ k/n`; at n = 5,111
and k = 6 that is **1.174e-03 = 1.15× FLOOR_1CELL before any signal exists**. Deriving the floor on
the scale it is applied to (`NONLINEAR_NULLS.csv`, 600 matched-null draws per cell):

| | |
|---|---|
| cells whose 6-df statistic exceeds the **1-df** floor | 12 of 14 |
| cells whose 6-df statistic exceeds its **own 6-df** floor (matched-null p95) | **0 of 14** |
| cells clearing the matched null at p < 0.05 | **0 of 14** |
| best ratio to own 6-df floor | 0.834 |
| **pure-noise control `G01_noise` through the identical path** | **1.007e-03 = 0.987× FLOOR_1CELL** |

A column of pure noise reaches 99% of the single-cell floor through this path. The nonlinear
"headroom" is degrees of freedom.

### Null validation for the cells that were nulled

Matched null by level (`N_ESWAP` / `N_TSWAP` / `N_PSWAP` / `N_ROW`), blind within-entity arm run
alongside and published, never a verdict. Blocks 12–5,111, **all ≥ 6**, no cell labelled
`POWER_NOT_ASSESSED`. Null-centre ratios 0.564–0.999; 5 of 14 sit at ≥0.8 of the real effect and are
flagged as weak instruments in `NONLINEAR_NULLS.csv`.

Component-wise injection into a synthetic response (`COMPONENT_INJECTION.csv`, 200 replicates ×
199-permutation bank, deterministic CRC32-derived seeds — E1_I0043 D-07 not repeated):

| | |
|---|---|
| type-I at δ = 0 | **0.0462** (nominal 0.05) |
| power ≥ 0.80 at δ = 0.0060, components with variance share ≥ 10% | **7 of 7 arms** |
| realisation ratio at δ = 0.0020 / 0.0060, BETWEEN (share 0.70) | 0.72–0.77 / 0.69–0.72 |
| realisation ratio, WITHIN (share 0.30) | 0.33–0.39 / 0.31–0.32 |

**The matched null is powered against both components.** The WITHIN arm realises only ~1/3 of its
target, so its power is power against something smaller — stated here rather than hidden, which is
the reading E1_I0043 D-06 asks for.

**No arm of any re-measured cell reaches FLOOR_132. Nothing reopens.**

---

## 7. WHAT MOST WEAKENS THIS CONCLUSION

Four things, in descending order of consequence.

**(a) These are not the pre-fit arithmetic kills the ruling describes.** `C-RAWSD` is computed *from*
`β̂` — the fitted coefficient of the very in-sample OLS fit whose increment it bounds. D097 did not
close these channels without fitting: **every one of the 213 was fitted**, and the "ceiling" is that
fit's realised increment times its VIF. The kills are sound. But the ruling's premise — that an
arithmetic ceiling is cheap, prior to statistics, and therefore immune to methodological revision —
does not describe this construction. A β̂-derived ceiling inherits every assumption of the fit that
produced it: the base, the level, the linearity, the in-sample scoring, the rowset.

**(b) The exclusion from E1_I0036's re-levelling audit rests on a false premise.** That screen
excluded all 213 on the stated ground *"a ceiling kill is arithmetic and survives re-levelling"*
(`T1_not_ceiling`). It does not: `β̂`, `sd(x)`, `sd(y)` and `SST` all change when player-games are
aggregated to team-games. Of the 213, **171 are at a roster-constant level with a summable target**
and would have been `T2 ∧ T3` eligible but for `T1`. Published eligibility rises from
**118 of 1,580 (7.5%) to 289 of 1,580 (18.3%)**. This does not resurrect any of them — E1_I0036's
own arithmetic (floor rises 8.3–9.3× at team level against ~9.4× dilution gain) says re-levelling
roughly cancels, and all 213 sit below the *player*-level floor before any of that. But the stated
ground is wrong and is recorded as `D-02`.

**(c) 40 of the 213 are negative controls, not candidates.** 20 are `G02_placebo_noop` (an exact
affine copy of a base column, ceiling ≡ realised ≡ 0) and 20 are `G01_noise`. The headline count
"213 cells killed on arithmetic ceiling" is 173 candidates and 40 controls.

**(d) The ledger's other ceilings are exposed, and one is exposed by an order of magnitude.**
`CEILING_FORMS_CENSUS.csv`: 33 recorded tables carry a ceiling column. The two same-scale OLS
families (D097, D108) are provably safe. The transported family is not, and includes D079's kill,
D084's kill and D089's headline. Measured directly from D084's own recorded oracle column:

| stratum | n | max ORACLE (the real bound) | × FLOOR_1CELL |
|---|---|---|---|
| **ON stratum (decision-relevant)** | 5,086 | 1.283e-04 | **0.126×** |
| ALL rows (pooled) | 11,267 | 9.719e-05 | 0.095× |
| OFF stratum (not a decision surface) | 6,181 | **1.285e-03** | **1.260× — above the floor** |

**D084's kill holds where it matters** (0.126× the floor on the decision stratum, 0.095× pooled).
But its published figure of 0.000129 understates the true bound by up to **10×**, and off-stratum the
true bound clears the floor. D089's `arithmetic_ceiling.csv` records no oracle at all, so its
headline 0.002057 has no recorded bound in either direction; its later `ceiling_reconciliation.csv`
does record one, at max c*² = 8.99 and max oracle 1.493e-02 = 14.6× the floor. D089 is a survivor,
so nothing closed is reopened — but the ledger phrase *"the largest arithmetic ceiling the programme
has measured"* attributes a boundedness the statistic does not have.

---

## 8. WHAT SHOULD CHANGE (recommendations only — no production change is enacted here)

1. **Rename.** `(d·d)/SST` is a *variance share*, not a ceiling. Quote the ORACLE
   `(d·e)²/((d·d)·SST)` beside it or instead of it wherever a bound is claimed.
2. **Record `c*`.** One extra column, `(d·e)/(d·d)`, makes the exposure of any future ceiling
   readable at a glance. E1_I0023 and E1_I0043 already do this; D089 does not.
3. **Two ceilings, not one.** A same-scale OLS ceiling is exact and safe. A transported ceiling is
   neither. They deserve different names in the ledger and different treatment in audits.
4. **The four rulings (D114, D117, D120, D122) stand on their conclusion but not on their reason.**
   The 213 survive every methodological revision tested here — but because the fits behind them
   returned effects below every floor, not because the ceiling is prior to statistics. If a future
   revision changes the *base*, the *level*, or the *function class*, the 213 are exposed to it
   exactly as any other post-fit kill is. Excluding them from a base-revision audit on the ground
   used at D114–D122 would be a mistake.
