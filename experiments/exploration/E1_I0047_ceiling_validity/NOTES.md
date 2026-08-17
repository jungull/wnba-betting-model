# NOTES — E1_I0047_ceiling_validity

PREREG sha256 `abbf0077ceb179b076646aeef5eda6ae2efeeced931fe87c69801ce6fc9b4994`.
Read `BOUND_OR_NOT.md` first; it carries the verdict. This file carries the reasoning that did not
fit there, the process record, and the things a successor needs.

---

## 1. THE ONE-PARAGRAPH ANSWER

`(d·d)/SST` is a bound on ΔR² **iff `c* = (d·e)/(d·d) ≤ 1`**, and it understates the achievable
increment by exactly `c*²` when it is not. The programme uses two different constructions under one
name. **Same-scale OLS** — the shift is the fitted contribution on the very rows, response, SST and
base the increment is scored on — forces `c* = 1` identically, making the statistic *equal* to the
realised increment, and the raw-sd variant *equal times VIF ≥ 1*. **Transported** — a rate
coefficient multiplied by an estimated-minutes vector and scored against points, or a coefficient
carried across a fold boundary — leaves `c*` unconstrained, and the statistic fails as a bound in
over half the rows of the two tables that record both quantities. **All 213 ceiling kills are the
first kind. Every ceiling in the ledger's headline sentences is the second kind.**

---

## 2. THE THING THAT SURPRISED ME

The brief nominated orthogonality. I expected to find that a candidate correlated with the base
would produce a ceiling that undershot, because the raw-sd form uses `sd(x)` rather than the
residualised `sd(x⊥)`.

It is the exact opposite, and the sign is not a detail — it is the whole answer.
`C-RAWSD = ΔR² × VIF` with `VIF = 1/(1 − R²_{x∼base})`. Correlation with the base makes the
statistic **larger**, i.e. more conservative as a kill criterion. An *exactly orthogonal* candidate
is the worst case, and even then the statistic equals the realised increment rather than falling
below it. Across the 213 the minimum VIF is 1.0000000461 and there are zero cells below 1.

The failing assumption was never about the candidate's relationship to the base. It is about whether
the shift was applied at the coefficient the data supports. A perfectly orthogonal candidate applied
at half its optimal coefficient breaks the bound 3× — that is the n = 3 counterexample in
`COUNTEREXAMPLE/`, and it is orthogonal by construction.

I record this because a successor reading only E1_I0043's DEFECTS.md would inherit the same wrong
suspect.

---

## 3. THE MISTAKE I MADE, AND HOW IT WAS CAUGHT

`s04` ARM 3 asked the one question the linear ceiling genuinely cannot answer: could the candidate
buy more if it entered nonlinearly? I entered each candidate as an orthogonal cubic polynomial plus
quartile indicators and compared the resulting ΔR² against `FLOOR_1CELL = 0.00102`.

It exceeded the recorded ceiling in **30 of 30 cells**, median 2.07×, and crossed the floor in 12.
For about ten minutes that was a twelve-cell reopening.

It is a six-column statistic compared against a one-column floor — the D101 error, verbatim, in a
new costume. `E[ΔR² | null] ≈ k/n`; at n = 5,111 and k = 6 that is 1.174e-03, **1.15× the floor
before any signal exists at all**. The check that settled it was the one D097 had already built into
its own frame: run `G01_noise` — a column of pure Gaussian noise — through the identical path. It
returns 1.007e-03, **0.987× the single-cell floor**. Then 600 matched-null draws per cell gave the
6-df floor directly: **not one of the 14 cells exceeds its own floor** (best ratio 0.834) and **not
one clears the matched null** (best p 0.103).

The uncorrected `arm3_*` columns are kept in `REMEASURE_30.csv` rather than deleted, which is the
disposition E1_I0043 chose for its own D101 error and seems right.

**The general lesson is not this screen's own.** The programme has no convention for a
degrees-of-freedom-matched floor. Any future screen that widens the function class — splines,
interactions, tercile dummies, a candidate family entered as a block — must widen the floor with it,
and there is nothing in the ledger that says so.

---

## 4. WHAT THE 213 ACTUALLY ARE

This is the finding I would put second after the verdict.

`C-RAWSD` is `(|β̂| sd(x)/sd(y))²`. `β̂` is the Frisch–Waugh coefficient of the in-sample OLS fit
`y ~ 1 + base + x` on the scored rows. **The ceiling is computed from the fit whose increment it
bounds.** D097 did not close 213 channels without fitting them. It fitted all 250 cells, computed
each cell's realised ΔR², multiplied by that cell's VIF, and called the product a ceiling.

That makes the kills sound — a statistic that is provably ≥ the thing it bounds cannot produce a
false kill — and it makes the *reason* the ledger gives for them wrong. The premise behind D114,
D117, D120 and D122 is that an arithmetic ceiling is prior to statistics and therefore survives any
methodological revision. **A β̂-derived ceiling is not prior to anything.** It inherits the base, the
level, the linearity, the in-sample scoring and the rowset of the fit that produced it. Change any
of those and the ceiling changes.

The concrete cost of that premise is already on the record: E1_I0036 excluded all 213 from its
re-levelling triage on the stated ground that a ceiling kill "is arithmetic and survives
re-levelling". It does not — `β̂`, `sd(x)`, `sd(y)` and `SST` all move when player-games become
team-games. **171 of the 213 are roster-constant with a summable target** and would have been
eligible. Published eligibility goes from 118 of 1,580 (7.5%) to 289 of 1,580 (18.3%).

**Nothing is resurrected by that.** E1_I0036's own arithmetic says re-levelling roughly cancels
(floor rises 8.3–9.3×, dilution gain ~9.4×), and all 213 sit below the *player*-level floor before
the question arises. The claim that has to be withdrawn is the narrow one about 7.5% being a
before-any-statistic ceiling on the level hypothesis.

---

## 5. WHY THE 213 ARE SAFE TWICE OVER

Two independent arguments, and the second is stronger than the first.

**Argument 1 — the margin.** 64 of 213 sit at ≥100× below the single-cell floor, 135 at ≥10×, all
213 at ≥1×. The brief asked for this count before any expensive work and it is 64.

**Argument 2 — the realised effect.** Because `c* = 1` and `U = 1/VIF ≤ 1`, the true achievable
ceiling *is* the realised ΔR². And:

- **0 of 213** have a realised ΔR² at or above `FLOOR_1CELL` (0.00102);
- **0 of 213** at or above `FLOOR_132` (0.00235) or `BEST_LIVE` (0.002057);
- **0 of 213** at or above their **own** injection-verified `mde80_fw` (min margin 2.05×);
- the **largest realised effect among all 213 is 0.00079634 = 0.78× the single-cell floor**.

Argument 2 does not depend on the margin, on the ceiling statistic, or on the classification rule.
It says the effects themselves were below every floor the programme has. That is why the answer is
"all 213 are safe" and not "64 are safe and 149 need work".

---

## 6. D101 IN PRACTICE — WHAT I DID DIFFERENTLY

The brief said this is the trap that created the screen I was auditing, and it caught me anyway
(§3). Three things helped:

1. **Every arm declares five fields.** Response, row set, SST basis, weighting, base. Written into
   `PREREG.md` §4 before running and repeated at the head of every section of every run log. ARM 2
   recomputes SST on the clean-window rows and is never compared against an ARM 1 ceiling.
2. **The negative control travels with the statistic.** D097 put `G01_noise` and `G02_placebo_noop`
   in its own frame, so any new path I built could be run on noise for free. That is what caught the
   df error. **A screen that ships a pure-noise column in its frame gives every successor a free
   calibration.** Worth making standard.
3. **The floor is derived, not looked up.** Where the statistic changed shape (6 columns instead of
   1) I computed a new floor by permutation rather than reusing the constant. The reused constant is
   what would have produced the false finding.

---

## 7. PROCESS RECORD (required by the brief)

- **No blanket process kill of any kind was issued.** No `Stop-Process`, no `taskkill`, no
  `Get-Process | Stop-Process`, at any point. Every `python` invocation ran in the foreground, one at
  a time, and exited on its own. **No PID was signalled, so there is no PID list to report.**
- **The shared screen kit was never imported and never modified.** `experiments/exploration/
  _screen_kit/screenkit.py` was listed once to confirm what was there and never opened for writing.
  `scripts/cv_base.py` re-implements the incremental-R² path independently, which is also why the
  D097 reproductions in `s01` are an independent check rather than a call back into the same object.
- **All writes are inside `experiments/exploration/E1_I0047_ceiling_validity/`.** No `git` command of
  any kind was run.
- **Partition.** Only `E0_I0024/screen_frame.parquet` (seasons 2021–2024, guarded by
  `cv_base.assert_partition`) and recorded `.csv`/`.md`/`.json` artifacts were read. **No 2025 or
  2026 season key was read at any point.** D097's own headline window is 2022–2024; 2021 is dropped
  by D097 itself, consistent with E1_I0043's finding that 2021 is degenerate.
- **Seeds.** `SEED = 20260808`. Per-cell seeds are `SEED + zlib.crc32(cell_key) % 1000003` —
  deterministic across processes. **E1_I0043's D-07 (`str.__hash__` randomisation) is not repeated**;
  every `.npz` in `nulls/` regenerates bit-identically from `SEED` alone.
- **Storage.** Every null archive stores signed, unstandardised draws — `linear_matched`,
  `nonlinear_matched`, `linear_blind`, `nonlinear_blind`, plus the real statistics, `n` and
  `nblocks`. No absolute values anywhere.

---

## 8. WHAT I DID NOT DO

- **I did not re-measure the 48 selected-but-not-run cells.** The preregistered cap was 30 and I kept
  it. They are flagged `SELECTED = True, TO_RUN = False` in `EXPOSURE_213.csv`. Given that the 30 run
  were the top 30 by rank score and none came close, the 48 are a formality — but they are recorded
  as not run rather than as run.
- **I did not re-derive D079's ceiling.** `E1_I0004_efficiency_transfer/arithmetic_ceiling.csv`
  records three ceiling columns and no oracle, so its `c*` cannot be recovered from the artifact.
  D079's 0.001127 is **1.10× the single-cell floor** as published, which means that channel was never
  killed on being below the detection floor in the first place — it was killed on usefulness. Worth a
  successor's ten minutes; not this screen's mandate.
- **I did not repair `E1_I0023/NOTES.md`**, `E1_I0036/LEVEL_ARTEFACT_VERDICT.md`, or any ledger
  entry. All are outside write scope. The recommendations are in `DEFECTS.md`.
- **I did not fit a champion, load a model, or enact any production change.**

---

## 9. FOR THE NEXT AGENT

Three things, in order of value.

1. **The cheap fix is one column.** Any screen computing a ceiling should record
   `c* = (d·e)/(d·d)` beside it. It costs one dot product and it makes the exposure of that
   ceiling readable forever. E1_I0023 and E1_I0043 already do; D089 does not, which is why its
   headline 0.002057 has no recorded bound in either direction.
2. **Two names, not one.** A same-scale OLS "ceiling" is an equality and is exact. A transported
   "ceiling" is a variance share and bounds nothing. Calling both "the arithmetic ceiling" is what
   let a wrong premise survive four rulings.
3. **The unaudited surface is base revision, not level.** The 213 are safe against the level
   hypothesis, against the null hypothesis, against the clean-window restriction, against a frozen
   intercept and against a nonlinear function class — all tested here. They are **not** protected
   against a change of base, because `β̂` is conditional on the base and the base is the programme's
   own top-ranked source of wrong answers (D087, D101). If a future revision widens the reference,
   the 213 must be re-run like anything else. Excluding them on the D114–D122 ground would be a
   mistake, and that is the single most important sentence in this screen.
