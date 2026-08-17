# DEFECTS — E1_I0046_allocation

Self-reported. Every defect found in this screen's own machinery or reasoning, including the ones
that change a headline. `PREREG.md` sha256
`b6dd2e6b141295b8accd92c9fb8920ef5d05a9901f35bf74410fb9c1ba331322`.

---

## D-01 — the projected oracle renormalised over the SCORED rows, not the roster · **FIXED, ceiling recomputed**

**Class: retrospective baseline.** The first implementation of `oracle_proj` in
`s02_stability_reference_ceiling.py` called `project(...)` with `tg_code[idx]`, the team-game codes
of the **decision-stratum rows only**. Renormalising over that subset forces the decision players'
shares to sum to 1, which injects the realised total *of that subset* into the forecast — the exact
class of error this programme has found six times, one of them inside inference machinery.

**How it was caught: the arithmetic became impossible.** It reported a ΔR² of **2.429873** on
`R2_s_min / A5_opp_defrtg`, where the maximum attainable is `1 − R²_base = 0.745`. It was not
caught by reading the code.

**Fix.** `base_residual` now returns the **full eval-season** arrays plus a keep mask, and every
projection runs over the complete appeared roster; only the SSE is taken on the scored rows. Every
number in `CEILING.md` and `CEILING.csv` is post-fix. **Effect on the headline: the pre-fix ceilings
were inflated by up to 1,000×; the gate would still have opened, so no verdict changed — but the
published ceiling would have been fiction.**

---

## D-02 — SAME-CHANNEL cells: two of eighteen candidate/response pairs are the base in disguise · **FLAGGED, excluded from every headline**

`A1_min_share_prior` is a prior EWMA of the **minutes** share; `R2_s_min` **is** the minutes share.
`A2_fga_share_prior` is a prior EWMA of the **attempts** share; `R3_s_fga` **is** the attempts
share. In those two cells the candidate is the base's own channel at a different halflife (5 against
the tuned 3 and 8). A positive result there measures **smoothing**, not information.

Both duly return the largest unfrozen values in their columns —
`R3_s_fga / A2 / UNFROZEN = +0.013228` is the biggest number in `PRIMARY_CELLS.csv` — and **neither
is quoted anywhere as a finding.** The primary response `R1_s_pts` is unaffected: no candidate on it
is the points channel.

Not caught by the preregistration, which named the candidates by construction without checking the
cross-product against the responses. **Effect on the headline: none, because the primary response is
clean — but the largest number in the screen is uninterpretable and would have been quotable.**

---

## D-03 — the FROZEN arm is structurally punitive for a candidate collinear with the base · **NOT A BUG; it is why both arms are reported**

Freezing holds the base slope at the base-only fit. A candidate that is a **better measurement of
the same latent quantity** requires the base weight to fall; frozen, it cannot. So the freeze does
not test "does this add information" for a substitute — it tests "does this add information *on top
of an unchanged base weight*", and a substitute fails that by construction.

Measured on the primary cell: `R1_s_pts / A2_fga_share_prior` is **−0.004696 (z −17.4)** frozen and
**+0.005487 (z +21.3)** unfrozen. **That split is not noise and it is not a defect — it is the
finding**, and `VERDICT.md` leads with both numbers rather than the favourable one.

The freeze still does the job it was mandated for: it is what shows that A1, A2 and A3 are **not**
increments over the trailing points share.

---

## D-04 — `CEILING.md`'s first draft implied one ceiling bounded both arms · **CORRECTED IN PLACE**

The unconstrained oracle `(d·e)²/((d·d)·SST)` residualises `d` on the base design and therefore
bounds the **UNFROZEN** arm. The projected oracle searches only `g`, with the base intercept and
slope held, and therefore bounds the **FROZEN/PROJ** arm only. The realised unfrozen
`R1_s_pts / A2 = +0.005487` exceeds the projected oracle (0.000762) and sits at **95.2 %** of the
unconstrained oracle (0.005763), which is consistent, not anomalous. The scope table is now in
`CEILING.md` above the per-candidate numbers.

---

## D-05 — the first injection DGP planted a vector that was not the model's regressor · **FIXED, curves recomputed**

The first `s04` planted `θ · tg_centre(z)` additively into the response. That is not the regressor
the model uses (`z`, uncentred, then projected), and it is strongly collinear with the base, so the
base refit absorbed it. Symptom: **planting a larger positive effect made the recovered statistic
more negative** (`R1_s_pts / A4 / FROZEN`: recovered −0.000012, −0.000039, −0.000181, −0.000253 at
increasing θ) and the rejection rate **fell to 0.000**.

**Fix.** The DGP is now the model's own functional form:
`y' = project(f + θ·z) + Π(resid)`, with `Π` a within-team-game permutation of the base residual.
`f` sums to 1 and `Π(resid)` sums to 0 inside every team-game, so **the synthetic response is
asserted to lie on the simplex at every θ in every replicate**. θ is calibrated against a noiseless
run so the planted level is expressed in ΔR² units the observed statistic can be compared to.

---

## D-06 — the injection curve is not resolved for the `A4_vac_x_own / FROZEN` cells · **DISCLOSED; the analytic floor is used and labelled**

For `A4_vac_x_own` in the frozen arm the rejection rate is already **1.000 at the lowest non-zero
planted level**, and the *recovered* value at that level (0.003905 on `R1_s_pts`) is **4.8× the
noiseless value** (0.00081). Recovery exceeding the noiseless effect means the permuted-residual
noise is itself raising the statistic, so the curve is not a clean power curve for this cell and the
interpolated floor (0.003100) is an artefact of the grid, not a measurement.

**Consequence, and it is the conservative direction:** the A4 verdicts use the **analytic**
`MDE80 = 2.80 × null_sd` floor and are labelled `analytic`. On `R1_s_pts` that floor is
**0.000703** against an observed **0.000573**, so A4 on the primary response is **NOT ESTABLISHED** —
which is the reading the unresolved injection curve cannot overturn in either direction.

---

## D-07 — two oracles are granted and neither is available live · **DECLARED IN THE PREREG, restated here**

The response needs the realised team total `Y_g`; the projection needs the realised roster `C(g)`.
Both pre-game injury sources in this repository return `manifest_present: false`, and E1_I0033
measured the champion's availability forecast summing to **10.34 players where 9.40 play**. **No
number in this screen is an achievable live increment.** A null under these oracles is a null *a
fortiori*; a survivor under them is an **upper bound on** a live survivor and nothing more. The one
surviving cell is reported as an oracle ceiling throughout.

---

## D-08 — this screen's `prior5_minutes` is defined on 2,919 rows where `E1_I0018` leaves it NaN · **DISCLOSED, no effect**

`E1_I0018/screen_frame.parquet` applies a larger `min_periods`; this screen uses `min_periods=1`.
On the **11,933** rows where both are defined the agreement is exact (max |diff| `1.4e-14`, anchor
A5c). Every affected row has `n_prior ≤ 1` and is therefore outside the decision stratum
(`n_prior ≥ 8`) by construction, so no reported cell is touched.

---

## D-09 — the family oracle in `CEILING.md` is not corrected for its five free coefficients · **DISCLOSED IN `CEILING.md` ITSELF**

Five hindsight coefficients on 3,167 residual rows carry an expected in-sample R² near
`5/3167 = 0.00158` under the pure null — about **26 %** of the `R1_s_pts` family ceiling of
0.005999. A corrected family ceiling would sit near 0.0044 (R1) and 0.0037 (R3), and the margins
over the 132-cell floor would fall from 2.55×/2.26× to roughly 1.9×/1.6×. The gate opens either
way. Stated on the ceiling page rather than only here.

---

## D-10 — `A5_opp_defrtg` is a proxy, not a defensive rating · **DISCLOSED**

It is the opponent's own strictly-prior mean **points allowed per game**, not a possession-adjusted
defensive rating. That weakens it as a defence measure. It does **not** weaken the use it is put to:
the claim about `A5` is that a **team-game-constant** candidate cannot move an allocation, and that
property holds for any such column whatever it measures. The demonstration that the within-team-game
swap is the **literal identity** for it (null sd `8.5e-22`, and exactly `0.0` in two cells) is a
property of the null and the column's support, not of its content.
