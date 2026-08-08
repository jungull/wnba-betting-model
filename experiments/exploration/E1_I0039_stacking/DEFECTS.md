# DEFECTS — E1_I0039_stacking (self-reported)

Every one of these was found by this screen, in this screen. Severity is my own assessment.
Three of them change a number that appears in `VERDICT.md`.

---

## DEF-1 — HIGH — the walk-forward trained on a fold the programme declares degenerate, and the anchor caught it

**What.** My first draft of the walk-forward machinery trained every arm from 2021 onward.
E1_I0034 `s06` excludes 2021 from every champion-based arm because the champion's 2021 fold
receipt declares `degenerate: true`.

**What it did.** Anchor A8 (E1_I0034's published P04 minutes cell) missed by **6.65e-2** on
`MAE(M0′)`, and the candidate arm came back **catastrophically worse than the base**: ΔMAE
**−0.7019** against a published **+0.0927**. The degenerate fold poisoned the fitted slopes.

**How it was caught.** The reproduction anchor, run **before** any new statistic, with a hard
assert. Nothing else in the screen would have flagged it — the number was large, stable and
wrong-signed, and would have read as "redistribution destroys the minutes forecast."

**Fix.** `MIN_TRAIN_CHAMP = 2022` for anything fitted on champion residuals;
`MIN_TRAIN_STRUCT = 2021` for component A's structural means, which never touch champion output.
A8 then reproduces to **5.1e-16**.

**Lesson worth keeping.** A reproduction anchor is not ceremony. This one caught a defect that no
null, no placebo and no permutation control in the screen could have seen, because the defective
arm was *internally consistent* — exactly the shape D109 reported when a published arithmetic
ceiling functioned as a smoke alarm for the intercept confound.

---

## DEF-2 — MEDIUM — "slope-only" residual arithmetic is not equivalent to a single regression when a scored season is also a training season

**What.** I first built the candidate arm as `base + (fit[1,X] − fit[1])` on the residual
`y − base`. That is algebraically identical to `offset + fit[1,X]` **only if the intercept is
constant across the training pool**. It is not: scored season 2023 is also a **training** season
for 2024, and by then it had already had its intercept subtracted, while 2022 had not.

**What it did.** Anchor A8c missed by **2.34e-4** (0.09293 against 0.09269) with `MAE(M0′)` exact.

**Fix.** Replaced with E1_I0034's own single-regression construction (`wf_arm`), which is the
byte-level equivalent. Both arms still hold an intercept, so E1_I0032's documented
intercept-confound defect remains designed out.

---

## DEF-3 — HIGH — my first injection planted an effect with no dispersion and returned a floor five times too small

**What.** `s06` §5 planted a "known MAE shift" by subtracting a **constant** from the treated
rows' losses.

**What it did.** The resulting loss-difference vector is constant on treated rows and zero
elsewhere, so the block variance collapses. Detection reached power 1.00 at 0.5× the null sd and
the implied `MDE80_injection` came out at **0.18× the analytic floor** — i.e. the analytic rule
would look *conservative*. That is the **opposite sign** to D113/D116's finding, which is the tell
that the construction, not the rule, was wrong.

**Status.** Disclosed and **not used**. `power_injection.csv` and `power_floors.csv` are retained
on disk as the record of the failed construction; nothing in `VERDICT.md` is backed by them.

---

## DEF-4 — MEDIUM — component A's structural fit pool silently swallows the whole degenerate 2021 season

**What.** A's league / depth-rank / draft-slot deviations are fitted on prior-season rows in the
**data-poor tier** (`is_fallback`). In 2021 the champion flags **every** row as fallback, so the
"data-poor tier" for the 2022 and 2023 fits is the entire 2021 season plus the genuinely data-poor
rows of 2022 (`component_A_walkforward_fits.csv`: n_train 3,479 / 3,963 / 4,434 against 3,479 total
2021 rows).

**Direction.** A's structural means are fitted on the **realised response**, not on champion
output, so the degenerate champion fold cannot corrupt them directly. The effect is that the
"league level for a data-poor player" is pulled toward the whole-league mean — i.e. toward the
constant the champion already emits — which makes A's placeholder **less** distinctive and
therefore **understates** A. Conservative for A's own number; irrelevant to the stacking verdict,
which turns on A being a subset of B.

**Second, smaller instance.** For scored season 2022 the tier frame supplies no depth or draft
buckets (it covers 2022–2024 only), so A's 2022 placeholder is **league-only**. 2022 is never
scored in the primary window; it enters only as training data for C's slopes in the AC/ABC arms.

**Not fixed.** Disclosed rather than repaired, because repairing it would change A's magnitude and
not the conclusion, and this screen is not permitted to tune a component.

---

## DEF-5 — HIGH — the second injection was a negative control wearing an MDE's clothes

**What.** `s07` §2 replaced DEF-3 with a construction that permutes the component's **actual
forecast change** across team-games to build the null, then plants a multiplicative loss shrink on
top.

**What it did.** At `k = 0` the recovered statistic is **−0.0543** (minutes pooled) at power 1.00,
not zero — because applying C's forecast change to the **wrong** team-games is genuinely harmful.
So the construction has a large true effect under its own null and cannot calibrate anything.
`smallest_multiple_at_power_80` is therefore meaningless and is reported as such.

**What it *is* good for, and this is worth keeping.** It is an excellent **negative control**:
misapplied redistribution costs **−5.0% on pooled minutes and −12.6% on decision-stratum minutes**.
That the same treatment applied to the right team-games *gains* is direct evidence the targeting,
not the functional form, carries the effect. Reported in `power_injection_componentwise.csv` under
that reading only.

---

## DEF-6 — HIGH — consequence of DEF-3 and DEF-5: this screen has NO self-derived power floor

**What.** After two failed constructions, no injection-verified MDE80 was obtained on this screen's
own machinery.

**Consequence, and it is material.** Every verdict in `STACK_LATTICE.csv` under
`verdict_DR1_injection_floor_CARRIED` leans on **D116's factors carried across** (minutes 1.22×,
points 3.40×) — measured on a different cell, a different row set and a different arm. **Twelve of
forty verdicts change depending on which floor is used**: under the analytic floor alone, eight
pooled points cells read DECIDED-POSITIVE rather than NOT ESTABLISHED and four decision-stratum
points cells read DECIDED-NEGATIVE. Both columns are published side by side in
`STACK_LATTICE.csv` so a reader can see the dependence rather than inherit my choice.

**This does not change the headline.** The decision-stratum minutes number (0.0218) is below the
floor on **either** basis (analytic 0.0278, carried 0.0340), and the decision-stratum points number
is nil at p 0.90 regardless. The floor question bites on the *pooled* points cells, which are the
ones `VERDICT.md` already says should never be quoted alone.

---

## DEF-7 — MEDIUM — a D087 reference-incompleteness failure that was my universe's fault, not the reference's

**What.** The completeness assertion on the team-game reference fired: E1_I0034's `_tg_frame`
covered 888 of the 1,044 W2 team-games in my first universe.

**Diagnosis.** The 156 missing team-games were **all playoff team-games** (`game_id` prefix
`1042x`), some with 12 established players and up to **90.5 freed minutes** — **not vacuous**.
E1_I0034's RS1 is regular season; my universe was not.

**Fix.** Universe restricted to regular season, and the team-game reference **rebuilt complete**
from the full champion candidate frame using E1_I0034's own definition, then asserted to agree with
the inherited frame on all four fields to **1.42e-14** (floating-point summation order) with the 72
remaining rebuild-only team-games asserted to carry `n_elig == 0` and `freed == 0` by construction.

**Why it matters.** Silently accepting the incomplete merge would have set `freed = NaN` on 14.7%
of rows, which would have quietly *excluded* those rows from every C cell — a reference covering
part of the row set, passing every other guard, which is precisely D087's trap.

---

## DEF-8 — MEDIUM — my first anchor was pointed at a number the artefact does not back

**What.** I anchored `_tg_frame` to E1_I0033's **1,392** RS1 team-games and got **1,284**.

**Diagnosis.** My error, not a data discrepancy: 1,392 counts RS1 team-games in `master_team`,
whereas `_tg_frame` carries only team-games containing at least one established player. **1,284** is
E1_I0034's own published RSP-W1 block count.

**Fix.** Retargeted to the 11,721 / 1,284 pair the artefact actually backs. Recorded rather than
silently deleted, because a reader should be able to see that an anchor failure was investigated
rather than dropped.

---

## DEF-9 — LOW — the declared W1 secondary is unrunnable as declared

**What.** `PREREG.md` §2 declares W1 (2022–2024) as a secondary window. With `MIN_TRAIN = 2022`
the 2022 season has no valid training season, so a W1 run returns **W2 verbatim** — the first
version of `s07` §3 printed 28 rows identical to the primary and I nearly published them.

**Fix.** The W1 run is forced through by training on 2021 and is labelled in the artefact itself:
`window = "W1_2022_2024_TRAINED_ON_DEGENERATE_2021_FOLD"`. Its results are reported as a
counterweight (sign agreement 0.64, C reversing to −12.56%) and never as corroboration.

**Standing consequence.** **The C result in this screen has been checked against exactly one clean
window.** There is no second clean window available in the exploration partition, and the sealed
2025/26 holdout is the only place one exists.

---

## Not defects, but limits a reader should carry

* **The null is coarser than two of the three components need.** The paired sign-flip is blocked at
  **team-game** because C's treatment is a team-game property and a row-level flip would be
  anticonservative for it. For A and B, which vary at player-game level, that block is
  **conservative rather than wrong** — their p-values are pessimistic, not optimistic. On a common
  row set mixing two levels this is the only construction valid for every cell (D115).
* **Every C cell is an oracle-on-absence ceiling.** Both pre-game injury sources return
  UNVERIFIABLE from `check_manifest` and back no number in this screen.
* **The decision stratum here is n = 3,158**, the W2 regular-season restriction of the programme's
  5,111–5,673. It is not the same n and must not be compared to a stratum figure quoted on
  2022–2024.
