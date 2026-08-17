# CEILING — COMPUTED BEFORE ANY FIT

Screen `E1_I0043_opponent_defence` · `PREREG.md` sha256
`629fe4aa2d757d393ec7db5861feba28e431f25cb89562ac1e61e05cf9b73add`
Evidence: `CEILING.csv` (as preregistered), `CEILING_MATCHED.csv` (scale-corrected),
`scripts/run_log_s02.txt`, `scripts/run_log_s04.txt`.

---

## THE ANSWER: THE CEILING CLEARS THE FLOOR. THE GATE SAYS PROCEED.

**1 sd of opponent defensive rating moves a decision-stratum player by 0.44602 points per game —
5.761% of a 7.7415-point response sd — and the arithmetic ceiling that implies is 0.00344 in the
points-scale D084/D089 form and 0.01094 as a strict oracle bound on the primary cell's own scale.**
Both sit above D103's injection-verified single-cell floor of 0.00102. The channel therefore
**cannot be closed on arithmetic**, and the preregistered gate released the fit.

That is the opposite of the cheap outcome. It is recorded as such.

---

## THE LEVER, IN ONE LINE

Decision stratum (`n_prior ≥ 8` AND `prior5_minutes ≥ 24`), walk-forward eval on the clean
2023–2024 window, base `B1_HONEST`:

| step | value |
|---|---|
| 1 sd of the train-centred opponent defensive rating | **4.62367** rating points |
| × β on points-per-minute | **3.151741e-03** ppm per rating point |
| = rate shift | **0.01457262** ppm |
| × estimated minutes (`prior5_minutes`, refB_mpg fallback) | **30.61** |
| **= points moved per 1 sd** | **0.44602 points per game** |
| against a response sd of | **7.7415 points** |
| **= share of one response sd** | **5.761%** |

---

## THE THREE FORMS, AND WHICH ONE IS ACTUALLY A BOUND

| form | value (primary cell) | is it an upper bound on ΔR²? |
|---|---|---|
| D084/D089 variance-share `(d·d)/SST`, points scale | **0.00344222** | **NO** |
| injected variance share on the cell's own `y_ppm` scale | 0.00426445 | **NO** |
| **ORACLE `(d·e)²/((d·d)·SST)` on the cell's own scale** | **0.01094259** | **YES** |

`ΔR² = (2 d·e − d·d)/SST`, which exceeds `(d·d)/SST` whenever `d·e > d·d` — i.e. whenever the
fitted coefficient is smaller than the optimal one, which is the normal case for a walk-forward
forecast. **The statistic D084 and D089 both call "the ceiling" is not a ceiling.** The strict
arithmetic bound achievable by rescaling the shift with full hindsight is the ORACLE. Both are
reported here and the gate is applied to both; this screen's own s02 applied the points-scale form
to a cell fitted on points directly, which is the D101 error, and it is corrected in s04 rather
than quietly reissued (`DEFECTS.md` D-02).

---

## AGAINST THE THREE PROGRAMME BENCHMARKS

Frozen in `PREREG.md` before any of these numbers existed.

| benchmark | value | ceiling (D084 form, points) | ORACLE bound (own scale) |
|---|---|---|---|
| single-cell detection floor (D103, **injection-verified**) | 0.00102 | **3.37×** | **10.73×** |
| 132-cell floor (D103, **injection-verified**) | 0.00235 | **1.46×** | **4.66×** |
| largest live effect ever measured (D089) | 0.002057 | **1.67×** | 5.32× |

**PREREGISTERED GATE: ceiling > single-cell floor → PROCEED.**

By base, on the primary response (`y_ppm`, clean window, ORACLE bound):

| base | ORACLE | × single-cell floor | realised / oracle |
|---|---|---|---|
| `B0_COMPLETE` (5 player-prior cols) | 0.01156094 | 11.33× | 0.894 |
| **`B1_HONEST` (+ own and opponent pace)** | **0.01094259** | **10.73×** | **0.859** |
| `B2_FAMILY` (+ `A01_opp_efg_allowed`, `A02_opp_ts_allowed`) | 0.00582414 | 5.71× | 0.760 |

Adding the other two opponent-allowance columns **halves the ceiling before a single statistic is
fitted**. That is item 5 of the brief answered arithmetically: roughly half of what this channel
can possibly buy is already reachable from columns the programme already has.

---

## THE NOISE FLOOR OF THE CEILING STATISTIC, WHICH IS NOT NEGLIGIBLE

A pure-noise column (`G01_noise`) was run through the identical path:

| | ORACLE bound | D084 form |
|---|---|---|
| `A10_opp_defrtg`, primary cell | 0.01094259 | 0.00344222 |
| `G01_noise`, identical path | **0.00019983** | **0.00016461** |
| ratio | **54.8×** | **20.9×** |

The real ceiling is comfortably clear of its own noise floor **on this stratum and this window**.
It is not always. See the defect below.

---

## A DEFECT IN THE PRIOR SCREEN'S DISCLOSED NOISE FLOOR

`E1_I0023` (D098) disclosed: *"The ceiling statistic is disclosed to have a noise floor — the
pure-noise control returns up to 3.98e-04."*

Read off its own `arithmetic_ceiling.csv`, the maximum pure-noise ceiling in that table is
**4.376e-03** (1-sd form) / **4.163e-03** (D084 form), on
`DECISION / T3_high_usage / MAIN_EFFECT / walk_forward`. The disclosed 3.98e-04 is the
`DECISION / ALL_TIERS / INTERACTION / walk_forward` value.

**The understatement is a factor of 11, and it sits on exactly the stratum-and-contrast combination
D098 headlined.** D098's withdrawn "6.2× the largest ceiling this programme has measured" claim of
0.012808 is only **3.08×** its own matched noise floor of 0.004163 — which is a much weaker
statement than the one that was published and then withdrawn for a different reason (D099 withdrew
it for the denominator, not for the noise floor). Recorded in `DEFECTS.md` as D-01.

This does not touch the present screen's numbers: its matched noise control sits at 0.00020 against
a real ceiling of 0.01094, and both are computed on the same rows in the same run.

---

## THE RESULT ON THIS PAGE THAT MOST WEAKENS IT

The ceiling is not stable across the seasons inside the clean window. On `y_ppm`, `B1_HONEST`,
one eval season at a time:

| eval season | between-team sd of opponent defensive rating | corr(defence, ppm) | realised ΔR² |
|---|---|---|---|
| 2023 | **3.49** | +0.0426 | **+0.00405** |
| 2024 | **5.37** | +0.1467 | **+0.01548** |

**2024 has 54% more between-team dispersion in defensive rating than 2023 and a 3.4× larger raw
correlation, and it carries most of the headline ceiling.** The ceiling is a statement about how
spread out the league's defences happened to be, and the two seasons in the one clean window
disagree about that by a wide margin. A ceiling computed on a two-season window where one season
supplies most of the dispersion is a weaker bound than a single number makes it look.
