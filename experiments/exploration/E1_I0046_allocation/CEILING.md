# CEILING — COMPUTED BEFORE ANY FIT

Screen `E1_I0046_allocation` · `PREREG.md` sha256
`b6dd2e6b141295b8accd92c9fb8920ef5d05a9901f35bf74410fb9c1ba331322`
Evidence: `CEILING.csv`, `REFERENCE_TUNING.csv`, `scripts/run_log_s02.txt`.
Window **CLEAN_2023_24** (eval 2023 and 2024, train strictly earlier). Stratum **DECISION**
(`n_prior ≥ 8` AND `prior5_minutes ≥ 24`), **n = 3,167**. Pooled figures are in `CEILING.csv` and
are reported second, always.

---

## THE ANSWER: THE CEILING CLEARS THE FLOOR. THE GATE SAYS PROCEED, ON ALL THREE RESPONSES.

| response | family ORACLE ΔR² (5 candidates, hindsight) | × single-cell floor 0.00102 | × 132-cell floor 0.00235 | × largest live effect 0.002057 | **GATE** |
|---|---:|---:|---:|---:|---|
| **R1_s_pts** (primary) | **0.005999** | **5.88×** | 2.55× | 2.92× | **PROCEED** |
| R2_s_min | **0.022916** | **22.47×** | 9.75× | 11.14× | **PROCEED** |
| R3_s_fga | **0.005319** | **5.21×** | 2.26× | 2.59× | **PROCEED** |

**This is the expensive outcome, and it is recorded as such.** The channel cannot be closed on
arithmetic and the preregistered gate released the fit. The prior on Q2 remains null; the ceiling
says only that a null, if one comes, will be a *measured* null rather than an arithmetic one.

The gate was applied to the **more generous** of two forms — the unconstrained linear oracle and the
projected hindsight oracle — precisely so that a decision to stop would have to survive both.

---

## WHAT THE BASE ALREADY IS — Q1 ANSWERED ARITHMETICALLY BEFORE ANY NULL

The tuned trailing-share allocator, `B_TUNED`, hyperparameters selected on **strictly earlier
seasons only** (`REFERENCE_TUNING.csv`):

| response | eval 2023 (h, k) | eval 2024 (h, k) | R² tuned | R² naive trailing-5 | R² uniform 1/n |
|---|---|---|---:|---:|---:|
| **R1_s_pts** | h = 13, k = 1 | h = 13, k = 1 | **+0.3462 / +0.3263** | +0.3327 / +0.3086 | **−0.4093 / −0.4127** |
| R2_s_min | h = 3, k = 1 | h = 3, k = 1 | **+0.2768 / +0.2455** | +0.2396 / +0.2060 | −1.6246 / −1.5766 |
| R3_s_fga | h = 8, k = 0.5 | h = 8, k = 1 | **+0.4744 / +0.5040** | +0.4683 / +0.4984 | −0.5497 / −0.5727 |

**Allocation is emphatically forecastable — by the simplest thing there is.** A shrunken EWMA of a
player's own earlier shares explains a third of the variation in her points share and half of her
attempts share, where an equal split is *worse than the response mean*. That is Q1, and it is not in
dispute.

**And the tuned reference genuinely beats the naive one**, by +0.0135 / +0.0177 R² on points and
+0.0373 / +0.0395 on minutes. Those gaps are 13× to 39× the single-cell detection floor. **Anything
tested here that beat only the naive allocator would be measuring the tuning, not the candidate.**
This is the discipline the brief demanded, and it is not decorative: on minutes the naive-versus-tuned
gap is **larger than the entire family oracle ceiling**.

---

## PER-CANDIDATE CEILINGS, AND THE ONE NUMBER THAT MATTERS MOST

Candidates standardised to unit sd; ΔR² is invariant to that. `d` is the candidate residualised on
the base design `[1, b]`; `e` is the base's walk-forward eval residual.

**WHICH ARM EACH BOUND ACTUALLY BOUNDS — read this before comparing a realised number to a ceiling.**

| bound | what it holds fixed | bounds |
|---|---|---|
| **unconstrained ORACLE** `(d·e)²/((d·d)·SST)` | nothing; the base coefficients are free because `d` is residualised on the base design | **the UNFROZEN arm**, and the RAW (unprojected) arm |
| **projected ORACLE** | the base intercept and slope, held at the base fit; only `g` is searched | **the FROZEN/PROJ arm only** |

A realised **UNFROZEN/PROJ** value may legitimately exceed the projected oracle, because the
unfrozen arm is also permitted to re-weight the base. It may not exceed the unconstrained oracle by
more than fold-to-fold noise, and in this screen it does not. Recorded as **D-04** in `DEFECTS.md`
because the first draft of this page implied a single ceiling covered both arms.

**R1_s_pts — the primary response. Base R² = 0.33491.**

| candidate | ORACLE ΔR², **unconstrained** `(d·e)²/((d·d)·SST)` | ORACLE ΔR², **projected onto the simplex** | × single-cell floor (max of the two) |
|---|---:|---:|---:|
| A1_min_share_prior | 0.000294 | 0.000693 | 0.68× |
| **A2_fga_share_prior** | **0.005763** | **0.000762** | 5.65× |
| A3_starter_rate_prior | 0.000091 | 0.000500 | 0.49× |
| A4_vac_x_own | 0.001172 | 0.001859 | 1.82× |
| A5_opp_defrtg *(team-game constant)* | 0.000071 | 0.000413 | 0.41× |
| `G01_noise` *(negative control)* | **0.000039** | 0.000000 | 0.04× |
| **FAMILY (5 real, joint)** | **0.005999** | — | **5.88×** |

**R2_s_min — base R² = 0.25511.** A1 0.013875 / 0.007601 · A2 0.013901 / 0.001694 · A3 0.003502 /
0.000285 · A4 0.008431 / 0.006850 · A5 0.000982 / 0.001690 · noise 0.000073 / 0.000046 ·
**family 0.022916**.

**R3_s_fga — base R² = 0.48914.** A1 0.000087 / 0.000145 · A2 0.004443 / 0.000073 · A3 0.000002 /
0.000108 · A4 0.003084 / 0.000234 · A5 0.000020 / 0.000836 · noise 0.000023 / 0.000051 ·
**family 0.005319**.

### The noise floor of the ceiling statistic

`G01_noise` through the identical path returns **0.000039 / 0.000073 / 0.000023**. The family
ceilings are **154× / 314× / 231×** their own matched noise floors. The ceiling is real, not an
artefact of the statistic.

---

## THE COMPOSITIONAL CONSTRAINT, MEASURED RATHER THAN ASSERTED

D111's rule — *allocations of a shared fixed budget do not survive being modelled separately* — is
usually quoted. Here it is a number, available **before any fit**:

| response | candidate | unconstrained ceiling | ceiling once the forecast must remain an allocation | **destroyed by the constraint** |
|---|---|---:|---:|---:|
| R1_s_pts | A2_fga_share_prior | 0.005763 | 0.000762 | **86.8 %** |
| R2_s_min | A2_fga_share_prior | 0.013901 | 0.001694 | **87.8 %** |
| R3_s_fga | A2_fga_share_prior | 0.004443 | 0.000073 | **98.4 %** |
| R3_s_fga | A4_vac_x_own | 0.003084 | 0.000234 | **92.4 %** |

For the single most promising candidate on every response, **between 87 % and 98 % of the apparent
room exists only if the forecast is permitted to break the budget**. A screen that modelled these
shares independently would have inherited a ceiling roughly **7.6× too large** on the primary
response and reported the difference as headroom.

The constraint does not always subtract: A1, A3 and A5 gain from projection on points, because the
renormalisation can undo a common-mode error. **Both directions are reported, and the gate used the
larger, so the constraint could not be the reason a response was closed.**

---

## THE ARITHMETIC RESULT THAT NEEDED NO FIT AT ALL

`A5_opp_defrtg` is **constant within the team-game**. Adding `g · x_g` to every member of a
composition and renormalising divides through by the same shift, so a team-game-constant candidate
cannot move an allocation except through the second-order curvature of the renormalisation. Its
unconstrained ceiling on points is **0.000071 — 1.8× the pure-noise control and 0.41× the detection
floor** — and it is preregistered here precisely to be the demonstration.

**Opponent, venue, pace, rest, travel and referee assignment are all team-game-constant.** Every one
of them is arithmetically incapable of forecasting an allocation, whatever it does to a level. That
is a structural statement about the response, not a result about basketball, and it disposes of an
entire family of candidates without a fit.

---

## THE FORM THIS SCREEN DOES *NOT* USE, AND WHY

`CEILING.csv` also carries the D084/D089 variance-share form `(d·d)/SST`. **It is not a bound**
(E1_I0043 `DEFECTS.md` D-02: `ΔR² = (2 d·e − d·d)/SST` exceeds `(d·d)/SST` whenever `d·e > d·d`),
and on a share response it is additionally **uninterpretable**: with the candidate standardised and
`SST` on a scale of `10⁻³`, the ratio runs to `10²`–`10³`. It is retained in the CSV for continuity
and is used for nothing.

---

## A DEFECT IN THIS FILE'S FIRST DRAFT, FIXED BEFORE PUBLICATION

The first implementation of the projected oracle renormalised over the **scored rows** rather than
the **full appeared roster**. That forces the decision stratum's shares to sum to 1 and injects the
realised total of that subset — a retrospective baseline of exactly the class this programme has
found six times. It produced impossible values (a ΔR² of **2.43** against a maximum attainable of
0.745). It was caught by the arithmetic being impossible, not by inspection. Recorded as **D-01** in
`DEFECTS.md`; every number on this page is post-fix.

---

## WHAT ON THIS PAGE MOST WEAKENS IT

**The family oracle is a hindsight fit of five columns to 3,167 residuals, and it is not corrected
for that.** Five free coefficients on 3,167 rows carry an expected in-sample R² of about
`5/3167 = 0.00158` under the pure null — **26 % of the R1 family ceiling of 0.005999**, and the
measured pure-noise single-candidate value of 0.000039 is *lower* than the `1/3167 = 0.000316`
that a single free coefficient would predict, so the noise-floor control is if anything flattering.
On R1 and R3 the family ceiling clears the single-cell floor by **5.9×** and **5.2×**, but a
degrees-of-freedom-corrected family ceiling would sit nearer **0.0044** and **0.0037**, and the
2.55× / 2.26× margins over the 132-cell floor would fall to roughly **1.9× / 1.6×**. The gate would
still open on all three responses; the R1 and R3 margins are thinner than the headline table makes
them look.
