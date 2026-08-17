# CLOSURE — does the five-zone simplex close, and where exactly does it break?

Evidence: `out/s02.txt`, `scripts/_s02.json`, `raw/S02_closure_matrices.npz`.
Closure is **asserted numerically**, never assumed: every line is a
`max |Σ − target|` over a stated and printed number of units.

---

## THE ANSWER IN THREE LINES

**The data close exactly. All six closure identities hold to at worst 5.97e-16 over
10,245 complete player-games — including `E1_I0051`'s asserted `Σ_z OS_z = 0`, which
holds at 1.110e-16.** Both the response residual and the regressor already live in the
zero-sum tangent space of the simplex.

**What violates closure is the FIT, and only the fit.** Five independently fitted slopes
spanning 0.3247 … 0.7743 (2.384×) make the five forecast shares sum to
**1 ± 0.0079 (sd), MAE 0.6448 % of a budget that is exactly 1 with zero pre-tip
uncertainty.** For scale, the sibling minutes screen measured MAE 13.0942 on a budget of
200 = **6.5471 %** — this violation is real, and it is **10.2× smaller in relative
terms** than the one that reversed three of five minutes candidates.

**One genuine defect was found, and it is not the one `E1_I0051` predicted: 62 of the
10,307 published analysis player-games silently carry only FOUR zones.** The parent
screen deletes a simplex component whenever the *league* took zero shots in that zone on
that calendar date.

---

## 1. THE SIX IDENTITIES, MEASURED

### On the full pre-gate panel — every player-game with ≥ 1 FGA, rebuilt from raw shots

| id | assertion | units | max \|Σ − target\| |
|---|---|---:|---|
| C1 | `Σ_z share_z = 1` | **17,056** | **1.110e-16** |

### On the published 51,473-row analysis frame (complete player-games only)

| id | assertion | units | incomplete units | max \|Σ − target\| |
|---|---|---:|---:|---|
| **C1** | `Σ_z share_z = 1` | 10,245 | 62 | **1.110e-16** |
| **C2** | `Σ_z S1_z = 1` (the frozen base) | 10,245 | 62 | **5.551e-16** |
| **C3** | `Σ_z (share − S1)_z = 0` (the response) | 10,245 | 62 | **5.967e-16** |
| **C4** | `Σ_z opp_share_prior_z = 1` | 10,245 | 62 | **1.110e-16** |
| **C5** | `Σ_z lg_share_prior_z = 1` | 10,245 | 62 | **0.000e+00** |
| **C6** | `Σ_z OS_z = 0` | 10,245 | 62 | **1.110e-16** |

**C2 was a claim, not an assumption, and it is now measured.** `S1` is
`EWMA_0.03(share_z)` over the player's strictly prior games; every zone of a player-game
shares the same game sequence and therefore the same EWMA weights, so
`Σ_z S1_z = EWMA_0.03(Σ_z share_z) = EWMA_0.03(1) = 1`. Confirmed at 5.551e-16.

**C6 is `E1_I0051`'s assertion and it is correct.** `OS_z = opp_share_prior_z −
lg_share_prior_z`; both terms sum to 1 across zones, so the regressor sums to zero
identically.

**The consequence `E1_I0051` did not draw:** because *both* sides already close, the
constraint does **not** invalidate the model class. A single common slope
`ŷ_z = a_z + b·OS_z` produces a fitted increment summing to `Σ_z a_z + b·0`, which
closes. **Only slope heterogeneity breaks closure**, and only through the term
`Σ_z (b_z − b̄)·OS_z`.

---

## 2. C7 — THE FITTED COEFFICIENTS, AND `E1_I0051`'s CLAIM

| zone | n | intercept | slope |
|---|---:|---:|---:|
| Restricted Area | 10,307 | +0.00398463 | **+0.77427267** |
| In The Paint (Non-RA) | 10,307 | +0.00151446 | +0.65298970 |
| Mid-Range | 10,307 | −0.00172491 | +0.55582503 |
| Corner 3 | **10,245** | −0.00123378 | **+0.32472290** |
| Above the Break 3 | 10,307 | −0.00240234 | +0.56298405 |

**Range 0.3247 … 0.7743, spread 2.384×.** `E1_I0051` asserted "0.325 to 0.774" and
"spread by more than 2×". **Both confirmed.**

`Σ_z intercept_z = +1.380639e-04`, not zero — because the Corner 3 cell is fitted on 62
fewer rows than the other four (see §4). On matched row sets it would be zero.

---

## 3. THE VIOLATION, IN UNITS OF ITS OWN BUDGET

`ŝ_z = S1_z + â_z + b̂_z·OS_z`, over the 10,245 complete player-games:

| quantity | value |
|---|---|
| mean of `Σ_z ŝ_z − 1` | +0.000156 |
| sd | **0.007924** |
| **MAE** | **0.006448** |
| max \|·\| | 0.025609 |
| q05 / q95 | −0.012627 / +0.013543 |
| player-games closing to within 0.5 pp of 1 | **43.12 %** |
| **MAE as % of the budget** | **0.6448 %** |
| **budget** | **exactly 1, pre-tip uncertainty exactly 0** |
| sibling minutes screen, same statistic | **6.5471 %** (MAE 13.0942 on 200) |

**Decomposition, verified to `0.000e+00`.** The varying part of the violation is
`Σ_z (b_z − b̄)·OS_z`; its sd is **0.007924**, identical to the sd of the full violation
at `|Δ| = 0.000e+00`. The constant part is `Σ_z â_z = +1.38e-04`. **The violation is
the slope spread and nothing else.**

**Read this the way it cuts.** The minutes budget is knowable pre-tip only to 0.631 % of
itself, so the sibling's 6.55 % violation was 10.3× its own budget's uncertainty. The
share budget is exactly 1 with **zero** uncertainty, so **0.6448 % is infinitely many
times the budget's own uncertainty and the violation is unambiguously real** — it is
simply small in absolute terms, which is why (see `VERDICT.md`) correcting it moves the
estimate by two per cent rather than reversing it.

---

## 4. C8 — THE DEFECT THAT WAS ACTUALLY THERE

**62 of the 10,307 published analysis player-games carry only four zones. All 62 are
missing `Corner 3`.**

| zones present | player-games |
|---|---:|
| 5 | 10,245 |
| **4** | **62** |

**Cause, traced to source.** `OS_z` is `opp_share_prior_z − lg_share_prior_z`, and
`lg_share_prior` is merged from a table grouped by `(season, game_date, zone)`. On a
date when the **league** took zero shots in a zone, that table has no row, the merge
yields NaN, `OS` is NaN, and the parent screen's `notna` gate silently deletes that
zone's row. There are exactly **6 such (season, date, zone) cells in the partition, all
`Corner 3`**: 2021-06-18, 2021-08-18, 2021-08-25, 2021-09-13, 2023-06-14, 2024-09-04.

**How much it matters, measured — and it matters less than it looks.** On those 62
player-games the four surviving shares sum to `min 1.000000 / mean 1.000000 /
max 1.000000`. Because the league took no corner threes that day, *every* player in
those games had `share(Corner 3) = 0`, so the deleted component was always the zero one
and the simplex still closes on what remains.

**But it is still a real defect, and it is a defect of exactly the kind this programme
keeps finding:** the rows deleted are **selected on the value of the response**
(`share = 0`, always). The Corner 3 cell is therefore fitted on a row set from which 62
zero-share observations have been non-randomly removed. It is 0.60 % of the rows and it
is the weakest cell in the family — the one that already fails the family-wise bar — so
it changes no verdict. **It is reported because it was found, not because it matters.**

Every arm in `VERDICT.md`, RAW included, runs on the **10,245 complete player-games** so
that the projected and unprojected arms are like-for-like. That costs the RAW arm 62
player-games relative to the published number and moves the published RA slope from
+0.77427267 to +0.7778 — disclosed, and reported beside every cell.

---

## 5. THE PROJECTION NO-OP PLACEBO — HONESTLY

`PREREG.md` §5 required a no-op placebo returning **exactly `0.000e+00`**. Asserted
precondition: a fit whose five slopes are equal by construction already closes —
verified, `max |Σ_z fit_eq| = 6.852e-17` over 10,245 units, so the check is not vacuous.

**Result: `max |project(fit_eq) − fit_eq| = 1.388e-17`. That is NOT exactly
`0.000e+00`, and I am not going to write that it is.** It is one unit in the last place
of the operand scale: subtracting the row mean of a vector that sums to 6.85e-17 rather
than to 0 cannot return the identity in IEEE-754. The projection is the identity to
within floating point and to no better; the preregistered "exactly zero" bar was written
for an integer-budget projection and is unattainable for this one. Recorded as
`DEFECTS.md` D-03.

---

## 6. X2 — CAN THE CANDIDATE MOVE AN ALLOCATION AT ALL?

A quantity constant within the team-game cannot move an allocation *through a common
slope*. `OS_z` is constant within an opponent-game **for a given zone** but varies across
zones, and because `Σ_z OS_z = 0` exactly its row-constant component is **zero by
construction**:

| component of `var(OS)` | value | share |
|---|---|---|
| total | 7.390711e-04 | 100 % |
| within-row, across-zone | 7.390711e-04 | **100.0000 %** |
| row-constant (mean over zones) | 4.765867e-35 | **0.0000 %** |

**`OS` is 100 % across-zone contrast. X2 does not deflate this lead.**

---

## 7. WHAT THIS SECTION MOST WEAKENS

* **The violation is small.** 0.6448 % of the budget, against the sibling's 6.5471 %.
  Anyone expecting `E1_I0051`'s flag to detonate this lead should read that number
  first. The flag was correct that the constraint was never honoured; it was silent on
  the magnitude, and the magnitude is the whole story.
* **`E1_I0051`'s stated mechanism is right but its implication is overstated.** "The
  fitted increment vanishes only if all five coefficients are equal" is true. It does
  **not** follow that a heterogeneous fit is sign-unreliable: the projection is exactly
  invariant to the common component (proved arithmetically here, verified by injection
  in `out/s04.txt`), so it can only rescale the spread, never reverse a common effect.
* **The C8 defect I found is real but inert**, and I have said so rather than promoting
  it. It deletes 62 zero-valued response rows from the weakest of five cells.
