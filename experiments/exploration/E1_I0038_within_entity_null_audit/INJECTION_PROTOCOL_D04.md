# THE AMENDED INJECTION PROTOCOL -- D-04 REMEDY, VERIFIED

Screen `E1_I0038_within_entity_null_audit`, PREREG section 6.
Commissioned by **D115 ruling 2**. Working code: `scripts/d04_protocol.py` (self-contained,
drop-in, **does not import the shared screen kit**).
Evidence: `D04_SCORECARD.csv`, `D04_INJECTION_POWER.csv`, `D04_MECHANISM.csv`,
`D04_CONFIRM_NREP250.csv`, `nulls/d04_r08_null_draws.npz`, `nulls/d04_r5_control_null_draws.npz`.

---

## 1. THE CLAIM UNDER TEST, AND THE VERDICT

> **D-04 (E1_I0036, Severity A):** D108's injection protocol can certify a null that is blind to
> the real candidate, because shuffling the base residuals destroys the between-entity structure
> of the RESPONSE — the very structure the null fails to destroy in the CARRIER.

**VERDICT: the defect is CONFIRMED. The stated cause is REFUTED and replaced.**

The protocol does certify a blind null — demonstrated below on the exact cell, twice, at two
replicate counts. But it does not do so for the reason D-04 gives, and the difference is not
cosmetic: it changes the remedy from an expensive one to a cheap one.

## 2. THE GATE: TWO ANCHORS, BOTH FROM PRIOR SCREENS' OWN BYTES

| anchor | value | source | reproduced |
|---|---|---|---|
| **A1** `dR2` of `R08_player_ra_share → y_oreb`, `B_COMPLETE`, POOLED | **0.0064881160** on **13,784** rows | D097 recorded 0.006488 / n=13,784 | diff 1.16e-07; fast-vs-literal identity 8.9e-17 |
| **A2** mean of D097's own recorded cyclic null draws | **0.0078802401** | `E0_I0024/permutation_draws.npz`, key `POOLED\|y_oreb\|B_COMPLETE\|R08_player_ra_share`, 600 draws | diff 4.0e-08 |

**A2 is the point.** `null_mean / observed = 1.2146`. The flag D115 proposes as the programme's
new universal diagnostic was already computable from D097's own permutation archive on the day
D097 was written. It took three screens and two ledger entries to look.

D087 coverage guard asserted: all 10 base columns cover all 13,784 rows.

## 3. THE FIVE PREREGISTERED RUNS

Seed 20260809 · R = 601 null draws · deltas `[0, 1.29e-4, 5.0e-4, 1.127e-3, 2.057e-3]` ·
60 replicates per delta (matched to `E1_I0036` so the two are comparable) · confirmatory
re-run at 250 replicates.

### R1 — the ORIGINAL protocol certifies the blind null

| delta | benchmark | achieved dR2 | power |
|---|---|---|---|
| 0.000000 | type-I | 2.6e-05 | 0.067 |
| 0.000129 | D084, DEAD | 1.29e-04 | 0.117 |
| 0.000500 | — | 5.00e-04 | 0.350 |
| 0.001127 | D079, DEAD | 1.127e-03 | 0.650 |
| **0.002057** | **D089, largest live** | **2.057e-03** | **0.933** |

**ORIGINAL VERDICT: CERTIFIED** (power 0.93 >= 0.80, type-I 0.067 <= 0.10).
Injection-verified MDE80 = 1.62e-03. `E1_I0036` reported 0.95 at 100 replicates. It reproduces.

### R2 — D-04's stated mechanism: **FAILED**, and kept as failed

The preregistered check was: does shuffling the base residuals destroy the response's
between-entity variance share?

| quantity | value |
|---|---|
| var share between player-season, REAL response `y` | 0.3304 |
| var share between player-season, base fitted values | 0.8416 |
| var share between player-season, SYNTHETIC `y0` (60 draws) | 0.2437 ± 0.0051 |
| var share between player-season, **REAL residual `e`** | **0.0396** |
| var share between player-season, **SHUFFLED residual** | **0.0337 ± 0.0023** |

**Collapse factor 1.17x.** The threshold preregistered for "confirmed" was 1.5x. **This check is
recorded as FAILED and the PREREG text is not rewritten.**

### R2b/R2c — the mechanism, measured in the right currency (disclosed post-hoc)

The residual's between-entity variance *share* is a marginal. What a cyclic shift cannot destroy
is a *joint*: the alignment between the entity means of the carrier and the entity means of the
residual. A rotation preserves each entity's carrier mean exactly, so that alignment survives
every single draw.

| quantity | REAL response | SYNTHETIC response | collapse |
|---|---|---|---|
| residual between-entity variance share (D-04's quantity) | 0.0396 | 0.0337 | **1.17x** |
| **corr(entity-mean carrier, entity-mean residual)** | **+0.4407** | −0.0059 ± 0.0313 | **74.1x** |
| **`N_CYCLIC` null mean** | **7.882e-03** | 4.731e-05 ± 4.8e-05 | **166.6x** |

> **The injection test grades a null distribution 167x smaller than the one that decided the
> cell. It is not testing the null that produced the verdict.**

### R3 — the AMENDED protocol VOIDS `N_CYCLIC`

Carrier decomposed at `player_season`: `dR2(BETWEEN) = 9.83e-03`, `dR2(WITHIN) = 4.81e-04`,
**`w_between = 0.953`** → dominant component **BETWEEN**.

| delta | planted BETWEEN | planted FULL | planted WITHIN |
|---|---|---|---|
| 0.000000 | 0.000 | 0.117 | 0.150 |
| 0.000129 | **0.000** | 0.133 | 0.600 |
| 0.000500 | **0.000** | 0.383 | 0.983 |
| 0.001127 | **0.000** | 0.700 | 1.000 |
| 0.002057 | **0.000** | 0.800 | 1.000 |

**Power 0.00 on the dominant component at every delta tested. MDE80 on the dominant component
= infinity.** `AMENDED_VERDICT = VOID_FOR_THIS_CANDIDATE`.
Flag: `null_mean 7.934e-03 > observed 6.488e-03` — **True**.

### R4 — positive control: the AMENDED protocol PASSES `N_PSWAP`

| delta | BETWEEN | FULL | WITHIN |
|---|---|---|---|
| 0.000000 | 0.083 | 0.067 | 0.083 |
| 0.000500 | 1.000 | 1.000 | 1.000 |
| 0.002057 | **1.000** | 1.000 | 1.000 |

`AMENDED_VERDICT = USABLE`, type-I 0.067, MDE80 (injection-verified) **4.23e-04**.
Flag silent (null mean 7.06e-05 vs observed 6.49e-03). **The amendment does not reject valid
nulls.**

### R5 — specificity control: the AMENDED protocol PASSES `N_CYCLIC` where it belongs

A fix that rejects everything is not a fix. The control candidate was chosen **on the regressor
alone, before any response was touched**: the D097 candidate with the lowest between-player-season
variance share on the same 13,784 rows.

`G01_noise`, between-share **0.0340** (96.6% of its variance is WITHIN player-season) →
dominant component **WITHIN** → **power 1.00** → `AMENDED_VERDICT = USABLE`.

**`N_CYCLIC` is a perfectly good null and the amendment says so.** It is void for one candidate,
not as a class.

**And `G01_noise` TRIPS the raw flag** (null mean 4.822e-05 > observed 1.672e-05) while being
structurally fine — a live demonstration, on the screen's own designated noise placebo, that
`null_mean > observed` alone is not a verdict.

### Scorecard

| # | check | result |
|---|---|---|
| R1 | ORIGINAL certifies `N_CYCLIC` | **PASS** — 0.93 @ 0.002057 |
| R2 | shuffle destroys response entity structure (as D-04 stated) | **FAIL** — 1.17x |
| R3 | AMENDED voids `N_CYCLIC` | **PASS** — 0.00 on dominant |
| R4 | AMENDED passes `N_PSWAP` | **PASS** — 1.00, type-I 0.07 |
| R5 | AMENDED passes `N_CYCLIC` on a within-varying candidate | **PASS** — 1.00 |

**4 of 5. Reported as a partial success, as preregistered.** The demonstration D115 asked for —
"the amended version correctly FAILS a null the original certified at power 0.95" — **landed.**
The check that failed is the one that would have let this screen agree with `E1_I0036` about
*why*.

### CONFIRMATORY RUN — the SHIPPED module, nrep = 250 (`D04_CONFIRM_NREP250.csv`)

The 60-replicate runs above cannot carry a hard 0.80 threshold (DEFECTS D-03). The deliverable
module `d04_protocol.verify_null` was therefore re-run end to end at **nrep = 250** (se 0.025),
on the same cell, exercising the code exactly as it ships.

| check | result |
|---|---|
| ORIGINAL D108 protocol still CERTIFIES `N_CYCLIC` on the full carrier | **PASS** — power 0.908, type-I 0.040 |
| AMENDED protocol REJECTS `N_CYCLIC` | **PASS** — `INJECTION_TESTED_A_DIFFERENT_NULL`; power on dominant component **0.012**, null-centre ratio **155.4x** |
| AMENDED protocol ACCEPTS `N_PSWAP` | **PASS** — power on dominant 1.000, type-I 0.044, null-centre ratio **1.47x** |

**3 of 3.** Two details worth recording:

* At 250 replicates the power on the BETWEEN component is **0.012**, not 0.000 — 3 detections in
  250, consistent with a fraction of the type-I rate. The 60-replicate "0.00" was a true zero
  only within its own resolution. The verdict is unchanged; the number is more honest.
* **C1 fires before C2.** The module returns `INJECTION_TESTED_A_DIFFERENT_NULL` rather than
  `VOID_FOR_THIS_CANDIDATE`, because the null-centre check is evaluated first and is decisive on
  its own. That is the intended ordering: the cheapest check that can settle it, settles it.
* `C3_z_observed_vs_null = −2.407` for `N_CYCLIC` and **+58.6** for `N_PSWAP` — the magnitude-aware
  form separates them by 60 standard deviations where the raw flag is a single bit.

---

## 4. THE AMENDED PROTOCOL AS ADOPTED (three checks, increasing cost)

Implemented in `scripts/d04_protocol.py::verify_null`, which returns a single verdict plus the
full per-component power table.

### C1 — NULL-CENTRE CONSISTENCY *(free; new; catches the defect with no decomposition)*

Compare the null mean the **injection** generates against the null mean the **real verdict** was
taken from. If they differ by more than 10x, the injection tested a different null and its
certification means nothing.

| null | verdict null mean | injection null mean | ratio | |
|---|---|---|---|---|
| `N_CYCLIC` | 7.882e-03 | 4.731e-05 | **167x** | **FAIL** |
| `N_PSWAP` | 7.551e-05 | 5.492e-05 | 1.37x | PASS |

Costs one line. Needs no entity key, no decomposition, and nothing the injection loop was not
already computing. **This is the check the programme should have had.**

### C2 — COMPONENT-WISE INJECTION *(the verdict rule; D115 ruling 2 as proposed)*

1. Decompose the carrier at the entity the null operates on: `x_between = mean(x | entity)`,
   `x_within = x - x_between`.
2. `w_between = dR2(x_between) / (dR2(x_between) + dR2(x_within))`; dominant component is
   `BETWEEN` if `w_between >= 0.50` else `WITHIN`.
3. Inject along `FULL`, `BETWEEN` and `WITHIN` separately.
4. **A null with power < 0.80 on the DOMINANT component is VOID for that candidate regardless of
   its power on the full carrier.**
5. Type-I at delta 0 > 0.10 → `ANTICONSERVATIVE`.

C2 says *which* component is blind; C1 says *that* the certification is meaningless. Keep both.

### C3 — THE `null_mean > observed` FLAG *(unconditional, ADVISORY ONLY)*

Publish it beside every p, always — D103 ruling 2 already requires the null mean, and the
comparison is free. **Do not use it alone as a verdict.** Measured over 1,170 of this
programme's own killed cells (`FLAG_AGREEMENT.csv`):

**sensitivity 0.831 · specificity 0.629 · positive predictive value 0.146.**

403 of 472 flagged cells are structurally fine. Use the magnitude-aware form instead when a
single number is wanted:

| rule | sensitivity | specificity |
|---|---|---|
| `null_mean > observed` | 0.831 | 0.510 |
| `z = (observed − null_mean)/null_sd < −1.0` | 0.446 | **0.980** |
| `z < −1.5` | 0.277 | **1.000** |

D097's `R08` sits at **z = −2.4**.

### Replicate count — this is not optional

The CERTIFY/VOID decision is a hard threshold at power 0.80.

| nrep | se at true power 0.80 | 95% CI half-width |
|---|---|---|
| 60 | 0.052 | 0.101 |
| 100 | 0.040 | 0.078 |
| **250** | **0.025** | 0.050 |
| 500 | 0.018 | 0.035 |

**Observed in this screen: the same null on the same cell scored 0.93 under one seed and 0.80
under another, both at 60 replicates. One certifies, one does not.** `verify_null` defaults to
250 and warns below 150.

## 5. WHAT THIS PROTOCOL STILL DOES NOT DO

* It does not choose the entity for you. `groups` is an input, and a wrong entity gives a
  confident wrong answer. There is no way to detect that from inside.
* It assumes the statistic is non-negative (dR2). For a signed statistic C3 is vacuous and C1
  needs restating in terms of `mean|stat|`.
* C2's 0.50 dominance threshold is a convention. A carrier split 0.51/0.49 will be judged on its
  BETWEEN component alone, which is arbitrary at the boundary; report `w_between` always.
* The whole protocol tests a null's **power**, not the **reference's** completeness (D087) or the
  **denominator's** comparability (D101). A null can be perfectly valid and the cell still wrong.
* It was verified on **one cell, one programme, one sport, in-sample**. R4 and R5 are controls,
  not independent replications.
