# PREREG — E1_I0051_constraint_sweep

**Which other screens in this programme modelled a constrained quantity without honouring the
constraint, and does honouring it change any published verdict?**

Frozen before any statistic in this screen was computed, other than the two probes `s00` and
`s00b`, whose complete output is committed in `out/s00.txt` and `out/s00b.txt` and whose contents
are reproduced verbatim in §3 below. Those probes were run *before* this file existed and their
numbers are what §3's gate is calibrated against; they are therefore disclosed as
**pre-hash measurements**, not preregistered predictions, and every one of them is a property of
the raw data rather than of any fit.

---

## 0. SCOPE, AND WHAT THIS SCREEN IS NOT

`E1_I0046_allocation` established, on a compositional response, that **three of four candidates
flip sign** when the forecast is forced to be a genuine allocation, and that **87–98 % of the
arithmetic ceiling** for the best candidate on each response exists only if the forecast may break
the budget. D127 ruling 3 generalised it: *any screen with a summing response that models
components independently is producing sign-unreliable results.*

**Nobody has asked which other screens are in that position.** This screen asks.

**This screen does not fit a champion, does not propose a production change, and does not enact
any repair.** It re-measures published cells under a constraint and reports the sign before and
after.

---

## 1. PARTITION AND HOLDOUT

* Regular season, **2021–2024 ONLY**. **2025 and 2026 are a SEALED confirmation holdout and are
  never read, joined, merged, described or referred to by any value.**
* The gate is enforced on **VALUES** (`season ∈ {2021,2022,2023,2024}`) and on any column whose
  dtype is **genuinely datetime**; nothing is coerced. `pd.to_datetime` on a float silently
  returns 1970 and a column named `candi-DATE` contains the substring `date` — neither trap is
  available to this screen because the check is dtype-gated and value-based.
* **The one clean window is 2023–2024.** 2021 is degenerate (all forecasts at fallback level 4, a
  constant) and 2022 depends only on 2021. Every headline is eval-2023 + eval-2024, walk-forward,
  training strictly earlier. **2022 is reported only as a disclosed contrast and is never a
  headline.**
* Manifests: `row` and `season` granularity are usable; `artifact` is not; **MISSING = UNVERIFIABLE
  and a missing manifest is never a pass.**

## 1.1 WRITE SCOPE AND PROCESS DISCIPLINE

* This screen writes **only** inside `experiments/exploration/E1_I0051_constraint_sweep/`.
* **The shared screen kit is not imported and not modified.** Sibling agents hold it open. All
  machinery is reimplemented in `scripts/cs_base.py`, which credits
  `E1_I0046_allocation/scripts/al_base.py` (read-only) as the source of its frame construction,
  projection, swap classes and `Cell`. That deliberate closeness is what makes the anchors in §7
  meaningful.
* **No blanket process kill of any kind.** No `Get-Process | Stop-Process`, no `taskkill`. Only
  PIDs this screen launches and records may be stopped, by id. Recorded in `NOTES.md`.
* No `git` write command is issued.

---

## 2. THE DEFINITION THE WHOLE SCREEN TURNS ON

A response is **CONSTRAINED** if the quantities being modelled must sum to, or be bounded by,
something **fixed at a higher level** — that is, determined *independently of the components
themselves*.

This is narrower than "the components sum to something", and the difference is the entire finding:

| | components sum to | is the total fixed at a higher level? | constrained? |
|---|---|---|---|
| player **minutes** | 200 + 25·(OT periods) | **YES — by the rules of basketball** | **YES** |
| player **points** | the team's points | **NO — the team total IS the outcome** | **NO** |
| player **attempts** | the team's attempts | **NO — same** | **NO** |
| player **rebounds** | the team's rebounds | **NO — same** | **NO** |
| `p_active` over a roster | the realised roster size | **NO — a random variable, not a budget** | **NO (soft)** |
| a **share** response `y_i / Σ_j y_j` | 1, by construction | **YES — but SELF-IMPOSED by the analyst** | **YES** |

**Modelling player points independently does not violate a budget. It implies a team total.** A
screen is only exposed to D111/D127 if the total it implies was already fixed by something else.
`E1_I0046` created its constraint by *choosing* a share response and then conditioning on the
realised total — which is why that screen's numbers are declared oracle ceilings throughout
(its `DEFECTS.md` D-07). A screen that models levels has no such exposure.

**This distinction is preregistered as the classification rule, and it is the thing most likely to
make this screen's answer "almost nothing is exposed".** It is stated here, before the census, so
that it cannot be adjusted afterwards to produce casualties.

### 2.1 The four classifications, and NOT-DETERMINABLE is real

* **HONOURED** — the screen projected, conditioned on, renormalised to, or otherwise respected the
  budget; or its response is the budget's own share and the projection was applied.
* **VIOLATED** — the response is constrained under §2 and the screen modelled its components
  independently with no projection, conditioning or renormalisation.
* **NOT-APPLICABLE** — the response is not constrained under §2. **This is expected to be the
  overwhelming majority and establishing it is the cheap part of the work.**
* **NOT-DETERMINABLE** — the screen's own documents do not fix the answer and it could not be
  settled by measurement within this screen. **Kept as an honest category. A NOT-DETERMINABLE is
  never reported as a violation and never as a clean bill of health.**

---

## 3. THE BUDGET GATE — MEASURED, NOT ASSERTED (pre-hash, from `out/s00.txt`, `out/s00b.txt`)

Appeared roster (`minutes > 0`), regular season 2021–2024, **16,717 player-games in 1,776
team-games**.

| summing quantity | team-game total: mean | sd | **cv** | lands on a rules lattice? | MAE of the best *pre-tip* assertion | **as % of the total** |
|---|---:|---:|---:|---|---:|---:|
| **player minutes** | 201.270 | 5.857 | **0.0291** | **YES — 1,776 of 1,776 within 0.0667 min of a multiple of 25; 95.2703 % at exactly 200** | **1.26984** (assert 200) | **0.635 %** |
| player points | 81.885 | 11.005 | 0.1344 | no | 8.75004 (assert the mean) | 10.686 % |
| player attempts | 68.250 | 6.307 | 0.0924 | no | 4.95242 (assert the mean) | 7.256 % |
| player `possessions` | 408.238 | 22.297 | 0.0546 | no | — | — |
| player `usage_percentage` | 1.7016 | 0.2341 | 0.1376 | no | — | — |

The minutes residual off the nearest multiple of 25 has **mean +0.002646, sd 0.007924, max
0.066667** minutes — four seconds, the minute:second rounding artefact `E1_I0046` records. **The
minutes budget is not approximately fixed. It is exactly fixed, and the only thing not known
before tip-off is the number of overtime periods.**

### GATE S1 — a response passes the budget gate iff **both**

* **(S1a)** its team-game total lands on a lattice fixed by the rules on **≥ 99 %** of team-games
  to within **0.5** units; **and**
* **(S1b)** the best assertion of that total available **before tip-off** has MAE **≤ 2 %** of the
  total.

**Minutes passes (100.00 %, 0.635 %). Points fails S1a and S1b. Attempts fails S1a and S1b.
Possessions fails S1a. Usage fails S1a.** The gate is decided by the table above and by nothing
else.

`usage_percentage` is additionally disposed of arithmetically: it is a per-100-possessions rate
whose denominator is the player's own on-court possessions, so it has no shared budget at all.

### 3.1 THE THING THAT MAKES MINUTES DIFFERENT FROM `E1_I0046`'S RESPONSES

`E1_I0046` had to grant itself **two oracles** — the realised team total `Y_g` and the realised
roster `C(g)` — and states eleven times that no number in it is an achievable live increment.

**The minutes budget is not an oracle.** 200 is knowable before tip-off and is correct on 95.27 %
of team-games at an MAE of 0.635 %. Only the *roster* remains an oracle. **This screen therefore
carries a projection that is live-available in its budget and oracular only in its denominator
set, and it says so on every number.**

---

## 4. THE SELECTION RULE FOR RE-MEASUREMENT — PREREGISTERED

A published cell is re-measured iff **all four** hold:

* **S1** its response passes the budget gate of §3;
* **S2** the screen's own published construction did **not** project, condition on, or renormalise
  to that budget (established by reading the screen's documents, quoted in
  `CONSTRAINT_CENSUS.csv`);
* **S3** the screen published at least one **signed** candidate statistic on that response;
* **S4** the cell is inside the clean window and the decision stratum is computable for it.

Cells are **ranked by (published |effect| ÷ the injection-verified single-cell floor 0.00102) ×
(constraint tightness `1 − MAE_pretip/budget`)**, and the top **K = 6** are re-measured. K is fixed
here at 6 and is not conditioned on what the ranking turns out to be.

**If no response passes S1, the screen reports that and re-measures nothing.** That is an
acceptable and preregistered outcome.

---

## 5. THE RE-MEASUREMENT

### 5.1 Responses

| id | definition | kind |
|---|---|---|
| **`M_level_min`** | `minutes` — the player's realised minutes, **as a LEVEL** | the construction every minutes screen in this programme actually used |
| `S_share_min` | `minutes / Σ_{j∈C(g)} minutes` | the `E1_I0046` construction, carried **only** to anchor against its published `R2_s_min` numbers |

`C(g)` = every player of that team with `minutes > 0`. **These are different responses and no ΔR²,
MAE, skill ratio or variance share is ever carried between them** (D101). The only quantity
compared across them is the **sign** of a candidate, which is unitless.

### 5.2 The three projection arms — the whole experiment

| arm | forecast | what it is |
|---|---|---|
| **RAW** | `ŷ_i` as fitted | **model the components independently.** What every minutes screen did. |
| **PROJ_BUDGET** | `ŷ_i ← 200 · max(ŷ_i,0) / Σ_{j∈C(g)} max(ŷ_j,0)` | force the roster to sum to the **live-available rules budget** |
| **PROJ_ORACLE** | `ŷ_i ← T_min(g) · max(ŷ_i,0) / Σ_j max(ŷ_j,0)` | force it to sum to the **realised** team minutes (an oracle; carried as the ceiling of the projection) |

Applied **identically** to the base arm, the augmented arm and **every one of the 2,000 null
draws**, so the projection can advantage neither side. Fallback to an equal split of the budget if
a team-game's projected sum is 0. Blocking is always at the **team-game**, never the row.

**A log-ratio (clr/alr) transform is rejected in advance**, for the reason `E1_I0046` gives and for
one more: minutes has **zero exact zeros** among appeared player-games (measured, `out/s00.txt`),
so alr is available on minutes where it was not on points — but the projection has **no free
parameter** and a zero-replacement constant is a free parameter sitting in the middle of the
response, so projection is used regardless and this is recorded as a choice rather than a
necessity.

### 5.3 Base reference

`B_TUNED`: a shrunken prior EWMA of the player's **own earlier** response,
`(1−w)·EWMA(h) + w·target`, `w = k/(k+n_prior)`, target `200/n̂` for the level and `1/n̂` for the
share, with `n̂` the team's strictly-prior expanding mean roster size. **`(h,k)` selected over the
42-point grid `h ∈ {2,3,5,8,13,21,expanding} × k ∈ {0,0.5,1,2,4,8}` on strictly earlier seasons
only.** No hyperparameter ever sees an evaluation row.

The tuned reference is mandatory, not decorative: `E1_I0046` measured tuned-over-naive at **+0.0384
R² on minutes**, larger than its entire family ceiling. **Anything measured against a naive
allocator would be measuring the halflife.**

### 5.4 Candidates — explicit literal allowlist, no name matching

`A1_pts_share_prior`, `A2_fga_share_prior`, `A3_starter_rate_prior`, `A4_vac_x_own`,
`A5_opp_defrtg`, `G01_noise`. Six, asserted. Between-player: the five excluding `A5`.
Team-game-constant: `A5` alone. Candidate prior halflife fixed at **5**, never tuned.

Constructed identically to `E1_I0046`'s so that its published `R2_s_min` cells are reachable as
anchors. **`A4_vac_x_own` is the cell of interest**: `E1_I0046` reported it at **+0.002640 FROZEN**
on the projected minutes share — the largest frozen effect in that screen — and it is the channel
D116 and E1_I0034/E1_I0042 built the only operationally actionable recommendation on.

**`A5_opp_defrtg` is preregistered as the arithmetic control.** A team-game-constant candidate is
incapable of moving a projected allocation, because adding `g·x_g` to every member and
renormalising divides through by the same shift. Its predicted ΔR² under **PROJ** is ≈ 0 and its
predicted ΔR² under **RAW** is not. **That contrast is the screen's own demonstration that the
projection is doing what it claims**, and it is a control that cannot fail — labelled as such,
not reported as a clean bill of health.

### 5.5 Both arms, always

* **FROZEN**: intercept **and** base slope held at the base-only fit; only the candidate
  coefficient estimated, on the base's **training** residual, against a **train-mean-centred**
  candidate, so no mean shift can be smuggled in.
* **UNFROZEN**: all coefficients refit.

The freeze is mandatory because a component once scored **+0.0287 at p 0.00005 on rows where it
substituted nothing**, and because `E1_I0046`'s surviving allocation candidate ran **+0.005487
unfrozen and −0.004696 frozen**. **Both numbers are reported for every cell, in the same table.**

### 5.6 Nulls, matched to the level the candidate varies at

| null | tests | blocks | valid for | INVALID for |
|---|---|---:|---|---|
| **`N_TGSWAP`** | which player *in this composition* holds which value | 1,776 team-games | the five between-player candidates | anything team-game-constant — it is the **identity** there |
| **`N_PSWAP`** | which player owns a whole **series**, inside the team-season | 48 team-seasons | the same five, preserving serial structure | the same exclusion |
| `N_TGBLOCK` | which opponent this roster faced, calendar held | 335 dates | `A5` only | between-player candidates |
| `N_WITHIN_PLAYER` | — | 634 player-seasons | **nothing. CONTRAST ONLY.** | everything here |

**Every verdict requires BOTH `N_TGSWAP` and `N_PSWAP`.** A composite requires a null valid for
**every** component, verified **component-wise by injection into the real response**, never by
shuffled residuals.

**The null-centre check is mandatory on every cell**: the null mean is reported beside the observed
value, unstandardised, and any cell whose null mean sits further from zero than the observed
statistic is flagged. A blind within-entity null does not merely lose power — on `E1_I0046`'s own
cells it returned **p = 0.0020 WITH THE SIGN REVERSED** where the correct null returned 1.0000.
That demonstration is **re-run on this screen's own primary cell**, not cited.

Family-wise correction is a **max-z over the five between-player candidates from one shared draw
stream**, so cross-candidate correlation is preserved (D120).

### 5.7 D101 — stated for every number, including this screen's own

Every reported figure carries: **response**, **row set**, **SST basis**, **weighting**, **base**,
**arm**, **projection arm**. Pure noise reached **0.987× the floor in use** in this programme
because a six-column statistic was compared against a one-column floor. No number in this screen is
compared to a floor computed on a different row set.

**Floors.** The programme constants `0.00102` (single cell) and `0.00235` (132 cell) are quoted
only as context. **Every verdict uses an injection-verified floor computed on THIS screen's own row
set**, and says so. The constant **`0.002057` is not used as a benchmark anywhere**: it has no
recorded bound in either direction, it is under audit, and `E1_I0049` established it is an
in-sample transported ceiling rather than a live effect.

---

## 6. THE AVAILABILITY DEFECT AS A CONSTRAINT PROBLEM

D112 recorded `Σ p_active = 10.338` against a realised roster of **9.402**, and framed all four
repairs as calibration. `AVAILABILITY_AS_CONSTRAINT.md` asks whether the constraint framing
suggests anything the calibration framing missed. **Measure, do not enact.** Three repair options
are already recorded and awaiting the user; **this screen recommends none of them and enacts none.**

Two predictions are recorded **here, before the analysis**, both derivable from `E1_I0046`'s
arithmetic rather than from any fit:

* **P1.** A roster sum is **not** a budget under §2 — the realised roster size is a random variable
  (measured sd 1.0077, range 6–12), not a fixed total. So the availability defect is a **level**
  defect, not a compositional one, and projection is not the right operation for it.
* **P2.** `Xb` (normalise `Σ p_active` to `R̂`) is a **per-team-game uniform rescaling**. By the
  same arithmetic that makes a team-game-constant candidate incapable of moving an allocation, a
  uniform rescaling **must cancel exactly** in any downstream step that renormalises within the
  team-game. **Its downstream effect is predicted to be exactly zero, before looking.**

If P2 is confirmed by `E1_I0035`'s published measurement, the constraint framing has *derived*
what the calibration framing *observed*, which is a strictly weaker contribution than finding a new
repair, and it will be reported as such.

---

## 7. ANCHORS — REPRODUCED BEFORE ANY NEW STATISTIC. THE RUN HALTS ON ANY FAILURE.

| # | anchor | source | required |
|---|---|---|---|
| A1 | appeared player-games 2021–24 RS | `E1_I0046` | **16,717** exact |
| A2 | team-games | `E1_I0046` | **1,776** exact |
| A3 | `Σ player pts == team pts` | `E1_I0046` | max abs diff **exactly 0**, 0 nonzero |
| A4 | `Σ player fga == team fga` | `E1_I0046` | max abs diff **exactly 0**, 0 nonzero |
| A5 | `Σ player minutes` vs box | `E1_I0046` | max abs diff **≤ 0.07** |
| A6 | decision stratum, all seasons | `E1_I0043` | **5,673** rows / **149** players / **708** games |
| A7 | decision stratum, clean window | `E1_I0046` | **3,167** rows |
| A8 | mean appeared roster | `E1_I0046` / `E1_I0033` | **9.41** (2 dp) |
| A9 | `E0_I0016`/`E1_I0018` screen frame | those screens | **14,852** rows |
| A10 | home advantage, team points | D104 / `E1_I0030` | **+0.965090** on **888** games |
| A11 | `Σ` player possessions ÷ (5 × team possessions), median | `E0_I0012` | **0.992** (3 dp) |
| A12 | minutes budget lattice | this screen, `s00` | **1,776 of 1,776**, max residual **0.066667** |
| A13 | `E1_I0034` trailing-5 minute sums by absence bucket | `E1_I0034` / `E1_I0042` | **198.96 / 201.08 / 201.50 / 191.44 / 184.02** |
| A14 | zero points shares among appeared rows | `E1_I0046` | **2,506** |

**A13 is the load-bearing one.** It is the published measurement that a team's remaining players'
trailing-form minutes sum to **250 against a 200-minute budget** in heavy-absence games. If it
reproduces, the constraint violation this screen is hunting is not hypothetical — it is already in
the record, already named by `E1_I0034` as *"the same class of defect as D111 ruling 3"*, and never
repaired.

---

## 8. CONTROLS

1. **No-op placebo** — the identity transform must give deviation **exactly `0.000e+00`** on every
   cell, with the transform asserted to be the identity so the check is not vacuous.
2. **`G01_noise`** — seeded row-level noise through the identical path, every arm.
3. **`A5_opp_defrtg` under `N_TGSWAP`** — the **literal identity**; expected null sd ~1e-21 and
   possibly exactly 0. Run deliberately, labelled as a control that cannot fail.
4. **Response placebo** — permute the response inside the team-game.
5. **Non-circular type-I** — synthetic candidates carrying a real player's whole series but
   belonging to a player on **another team-season**: realistic level and autocorrelation, zero true
   relation. `sd(z) ≫ 1` would show a too-narrow null.
6. **Component-wise injection into the REAL response, in the model's own functional form**, with
   the whole path rerun. Type-I at θ = 0 must be at nominal.
7. **Block bootstrap over team-games**, reported beside the permutation null. `E1_I0046` found
   these disagreeing by **8.07×** on its primary cell; if they disagree here, both are stated and
   the cell is not established under the more conservative one.
8. **Season split** — eval 2023, eval 2024, and the disclosed 2022 contrast, reported separately.

---

## 9. WHAT WOULD MAKE THIS SCREEN WRONG, AND WHAT IT WILL REPORT ANYWAY

* **The most likely outcome is that almost no screen had a constrained response and nothing
  changes.** That is stated here as the expected result. Six agents in this programme have found
  apparent defects, measured them properly, and retracted. **This screen will report the number of
  NOT-APPLICABLE screens first, before any exposure count.**
* **The `E1_I0046` result may not generalise at all**, because its constraint was self-imposed by
  its choice of response. If so, the honest headline is that D127 ruling 3 binds exactly one screen
  — the one that discovered it — and that is what will be written.
* **A sign flip on minutes would not automatically overturn anything**, because the minutes cells
  in this programme are mostly nulls, and a null that flips sign is still a null.
* **The result that most weakens this screen's conclusion is reported in the same document as the
  conclusion**, in `VERDICT.md`, not in a separate file.

**No production change is proposed. No champion is fitted. No repair is enacted.**
