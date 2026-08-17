# DEFECTS — E1_I0047_ceiling_validity

Defects this screen found, including the one it committed itself. Ordered by consequence, not by
whose fault they are.

**None of them reopens any of the 213.** That is stated first so no reader takes the length of this
file for the size of the exposure.

---

## D-01 — `(d·d)/SST` IS NOT A BOUND FOR THE TRANSPORTED FORM, AND THE PROGRAMME USES IT AS ONE

**Severity: confirms E1_I0043's finding, sharpens it, and locates it.**

`ΔR² = (2 d·e − d·d)/SST`, so `(d·d)/SST ≥ ΔR²` **iff `c* := (d·e)/(d·d) ≤ 1`**, and the achievable
increment exceeds the computed one by exactly `c*²`.

E1_I0043 named the mechanism correctly. Two things it did not have:

1. **The condition is scale, not orthogonality.** A perfectly orthogonal candidate applied at half
   its optimal coefficient breaks the bound 3× (`COUNTEREXAMPLE/minimal_counterexample.npz`, n = 3).
   A 1,000-draw collinearity sweep from ρ = 0 to 0.99 with an OLS-fitted shift never breaks it
   (max |c* − 1| = 6.772e-15).
2. **The counterexample was already in the record, on D098's own headline cell.**
   `E1_I0023/arithmetic_ceiling.csv`, `A10_opp_defrtg / DECISION / T3_high_usage / MAIN_EFFECT /
   walk_forward`: published ceiling 0.01280821, realised 0.01870281, `c*` 1.230.
   **The bound is exceeded by 46%.** 35 of that table's 64 rows exceed their own ceiling; 34 of 48
   in `E1_I0043/CEILING_MATCHED.csv` do.

**Where it bites.** `CEILING_FORMS_CENSUS.csv` classifies all 33 recorded ceiling tables:

| construction | screens | status |
|---|---|---|
| same-scale OLS (`d = β̂ x⊥` on the scored rows) | D097 `E0_I0024`, D108 `E0_I0029` | **exact bound, 0 violations in 346 rows** |
| transported (rate coef × minutes → points; or across a fold) | D079/D084 `E1_I0004*`, D089 `E1_I0018`, D098 `E1_I0023`, `E1_I0043` | **not a bound; c*² up to 8.99 observed** |

**Consequence for D084's kill, measured from its own recorded oracle column, decision stratum first:**

| stratum | n | max ORACLE (the real bound) | × FLOOR_1CELL |
|---|---|---|---|
| **ON stratum (decision-relevant)** | 5,086 | 1.283e-04 | **0.126×** |
| ALL rows (pooled) | 11,267 | 9.719e-05 | 0.095× |
| OFF stratum (not a decision surface) | 6,181 | 1.285e-03 | **1.260× — above the floor** |

**The D084 kill holds where it matters.** Its published figure of 0.000129 nevertheless understates
the true bound by up to **10×**, and off-stratum the true bound clears the single-cell floor. That is
worth recording even though nothing decision-relevant changes.

**D089's `arithmetic_ceiling.csv` records no oracle at all**, so its headline 0.002057 has no
recorded upper bound in either direction. Its later `ceiling_reconciliation.csv` does: max c*² 8.99,
max oracle 1.493e-02 = **14.6× the single-cell floor**, 11 of 16 rows above the floor. D089 is a
survivor, so nothing closed is reopened — but the ledger phrase *"the largest arithmetic ceiling the
programme has measured"* attributes a boundedness the statistic does not have.

**Not repaired here** — every one of those screens is outside this screen's write scope, and their
artifacts are correct; it is the prose and the ledger phrasing that are wrong. Recommended: record
`c*` as a column beside every ceiling, and quote the ORACLE wherever a bound is claimed.

---

## D-02 — E1_I0036 EXCLUDED THE 213 FROM RE-LEVELLING ON A FALSE PREMISE

**Severity: does not change E1_I0036's verdict; invalidates its stated eligibility ceiling.**

`E1_I0036/LEVEL_ARTEFACT_VERDICT.md`:

> **213 cells were killed on arithmetic ceiling. A ceiling kill is arithmetic and survives
> re-levelling. Not one of them was re-run.**

The premise is false for this construction. `C-RAWSD = (|β̂| sd(x)/sd(y))²` is derived **from the
fitted coefficient of an in-sample player-game OLS fit**. Aggregating player-games to team-games
changes `β̂`, `sd(x)`, `sd(y)` and `SST` — all four. A β̂-derived ceiling is not invariant to
re-levelling; only a genuinely prior arithmetic bound would be.

Measured on the census's own recorded columns (no name parsing):

| | |
|---|---|
| of the 213, level is roster-constant (`T2`) | **171** |
| target is summable (`T3`) | 213 |
| would have been `T2 ∧ T3` eligible but for `T1_not_ceiling` | **171** |
| E1_I0036 published eligibility | 118 of 1,580 killed cells (**7.5%**) — reproduced exactly |
| eligibility with these added | **289 of 1,580 (18.3%)** |

**No candidate is resurrected.** E1_I0036's own arithmetic — the detection floor rises 8.3–9.3× at
team level against a ~9.4× dilution gain — says re-levelling roughly cancels, and all 213 sit below
the *player*-level floor before any of that. The claim that must be withdrawn is the narrow one:
*"the level-artefact hypothesis can, at most, be about 7.5% of the negative record — and that ceiling
is set before any statistic."* The correct figure is 18.3%, and it is not set before any statistic.

---

## D-03 — THIS SCREEN COMPARED A 6-DF STATISTIC AGAINST A 1-DF FLOOR (self-inflicted, caught in-run)

**Severity: would have manufactured a 12-cell reopening. Caught before it reached the verdict.**

`s04` ARM 3 entered each candidate as an orthogonal cubic polynomial plus quartile indicators — a
6-column block — to measure whether a *nonlinear* use of the candidate could exceed the linear
ceiling. It does, in **30 of 30 cells**, by a median of 2.07×, and **12 of 30 crossed FLOOR_1CELL**.

That looked like the reopening the brief was sent to find. It is the D101 error, committed by this
screen against itself: **FLOOR_1CELL = 0.00102 is a one-column floor and ARM 3 is a six-column
block.** `E[ΔR² | null] ≈ k/n`; at n = 5,111 and k = 6 that is **1.174e-03 = 1.15× FLOOR_1CELL
before any signal exists**.

`s05` derived the floor on the scale it is applied to — 600 matched-null draws of the same 6-column
statistic per cell:

| | |
|---|---|
| cells exceeding the **1-df** floor | 12 of 14 |
| cells exceeding their **own 6-df** floor (matched-null p95) | **0 of 14** |
| cells clearing the matched null at p < 0.05 | **0 of 14** |
| best ratio to own 6-df floor | 0.834 |
| **pure-noise `G01_noise` through the identical path** | 1.007e-03 = **0.987× FLOOR_1CELL** |

A column of pure noise reaches 99% of the single-cell floor by this route. **The uncorrected ARM 3
table is kept on disk** as columns `arm3_*` in `REMEASURE_30.csv`, with the corrected 6-df floors in
`NONLINEAR_NULLS.csv`, rather than being deleted — the same disposition E1_I0043 chose for its own
D101 error.

The general lesson, which is not this screen's own: **a "nonlinear headroom" check is worthless
without a df-matched floor, and the programme has no convention for one.** Any future screen that
widens the function class must widen the floor with it.

---

## D-04 — E1_I0043's D-01 IS RIGHT AT 11× AND OVERSTATED AT 1.44× (scope, not substance)

**Severity: cosmetic. The finding stands.**

E1_I0043 D-01 headlines *"understated by 11×"*. The disclosed sentence in `E1_I0023/NOTES.md` has
two clauses with two scopes:

| scope | max control ceiling (1sd form) | × disclosed 3.98e-04 |
|---|---|---|
| literal first clause — **interaction**, walk-forward | 5.732328e-04 | **1.44×** |
| second clause — *"ceilings below roughly 4e-04 **here**"*, whole table | 4.375669e-03 | **10.99×** |

**11× is right for the scope the sentence is used in**, and E1_I0043's supporting table names the
correct argmax row. But one number was quoted where two are needed, and a reader checking the first
clause alone would find the headline overstated by 7.6×. Full detail in `NOISE_FLOOR_CHECK.md`.

The finding underneath is confirmed and reproduced exactly: D098's headline ceiling is **3.077×** its
own matched noise floor of 4.162570e-03, not 32× as the disclosed floor implies.

---

## D-05 — 40 OF THE "213 CEILING KILLS" ARE NEGATIVE CONTROLS, NOT CANDIDATES

**Severity: a headline count is 23% inflated. No conclusion depends on it.**

From the census's own recorded columns: 20 of the 213 are `G02_placebo_noop` — an exact affine copy
of a base column, collinear with the base by construction, with ceiling and realised increment both
**exactly 0** — and 20 are `G01_noise`, the pure-noise control. Both were run *as controls* by D097.

"213 cells killed on arithmetic ceiling" is **173 candidates and 40 controls**. Wherever the number
213 is used to size the negative record, 173 is the figure that means what the sentence intends.

---

## D-06 — THE BRIEF'S OWN FRAMING NOMINATED THE WRONG SUSPECT

**Severity: brief-level, recorded for the next agent.**

This screen was directed: *"Orthogonality of the candidate to the existing base is the obvious
suspect — check it rather than assume it."* Checked, and it is the reverse.

For an OLS-fitted shift, **orthogonality is the zero-slack case** — the ceiling equals the realised
increment exactly — and correlation with the base only adds slack, at `VIF = 1/(1 − R²_{x∼base})`.
Across the 213: min VIF **1.0000000461**, max 1.678582, **zero cells below 1**. There is no
candidate–base correlation that makes this form fall below what it bounds.

The suspect that was right is **scale transport**, which the brief did not name. Recorded so the next
brief on this subject points at the right variable.

---

## D-07 — E1_I0036's D-03 UNDERSTATES ITS OWN BLIND SPOT

**Severity: scoping only.**

E1_I0036 D-03 records that *"only D097 ever wrote an arithmetic ceiling to disk, so the CEILING label
can only fire in that screen."* The first half is wrong as stated: **33 tables across 12 screens
carry a ceiling column** (`CEILING_FORMS_CENSUS.csv`), including `E0_I0029` (D108), whose
`arithmetic_ceiling.csv` carries the *identical* raw-sd / residualised pair over 96 rows and was
passed to the census as `ceiling=None`.

The conclusion E1_I0036 drew is nonetheless safe, and this screen verified it: D108's 96 rows show
max |C-RESID − ΔR²| = 3.331e-16 and min (C-RAWSD − ΔR²) = **+0.000e+00**, 0 violations. **The
ceiling kills invisible to the census are of the same provably safe construction as the visible
ones.** The correct statement is "only D097's ceilings were *harvested into the census*", and the
invisible ones are safe for the same reason the visible ones are.
