# GATE INVOCATION CONTRACT — when `feature_gate.py` must be called

**Status:** shared experimental contract for the player-model program. Binding on every arm,
challenger, control, discovery workstream and re-fit that consumes
`experiments/player_program/feature_gate.py`.

**Scope.** This document governs the *invocation* of the gate: when it runs, on which matrix, and
with which arguments. It does **not** restate, weaken, extend or replace the gate's own checks, and
it does **not** modify `feature_gate.py`. The gate defines *what* is checked; this contract defines
*when*.

**Prepared at** `0397fbd8f870f17b6e3ced82a30a31680b20eb1f` (branch `player-model-program`), against
`feature_gate.py` as of `55f4500` (rank / conditioning) and `42af2cd` (informative missingness).

---

## 1. The clause

> **Feature audits must run separately on EVERY chronological training fold, and again on the final
> assembled design. A pooled audit cannot establish that every training fold is identified.**

A single audit over the pooled dataset does not discharge this requirement. The pooled matrix is
never fitted. The matrices that are actually fitted are the per-fold training designs, and each of
them must be audited on its own, before its own fit.

**Pooled variance is an average. Identifiability is a per-fold property.** A column can carry ample
variation across all seasons and none at all inside the season the model is currently training on.
Averaging over folds hides exactly the folds that are degenerate, because the healthy folds
dominate the pooled statistic.

The same argument applies to rank, conditioning, missingness rate and scaling. None of them is
preserved under pooling. A pooled audit is therefore evidence about a matrix nobody fits, and is
not admissible as evidence about the matrices everybody fits.

---

## 2. The case that motivates the clause

**ws3 (`discovery_wave_1/ws3`, branch tip `1e3509f`), stage-2 within-team-centred design, 2022
training fold.**

The 2021 projected-exposure regime assigns every Tier A candidate on a team an identical projected
possession share and an identical `p_active`. Within a team-game, in the material the 2022 fold
trains on, those columns carry no variation at all.

Measured, in ws3's own per-fold gate record `stage2_winsorised_train_fold_2022/attempt0`:

| column | fold-level standard deviation | gate finding |
|---|---|---|
| `proj_off_poss_share` | **`7.80108356964482e-09`** | `impossible_scaling` |
| `p_active` | **`5.13611574504531e-17`** | `impossible_scaling` |

And, in the same run's **pooled** audit
(`stage2_after_removing_the_duplicate_and_the_within_team_constant`, 8 features, 35,629 rows):
both of those columns are present, `findings: []`, `blocking: []`, `passed: true`.

**The pooled audit passed the two columns that the 2022 fold audit blocks.** That is the entire
argument for this contract, stated in one line, on real measured artifacts.

What followed from the degeneracy:

- standardising test rows by that fold-level standard deviation drove `|X·gamma|` to **`6.9e4`**;
- the within-team softmax **saturated to exact `0.0` and `1.0` shares**;
- **the optimiser converged** — stage 2 converged in five Newton iterations in every fold,
  including this one;
- winsorisation had previously *masked* the problem by clipping the feature to a sign indicator,
  which is not a fix.

A second, independent instance from the same wave: in P2's own design
`proj_off_poss_share == proj_minutes_share` and
`role_change == proj_minutes_share − trailing_minutes_share`, both exact. Ten declared features
spanned eight dimensions (numerical rank 8 of 10, condition `1.1738e16`); five declared features
spanned four (rank 4 of 5, smallest singular value `0.0`, condition `1.4012e15`). The duplicate pair
is visible pairwise (correlation `1.0`); the three-term dependency `c = a − b` is **not** — no
pairwise correlation among those three columns reaches the threshold. This is why numerical rank is
mandatory and not discretionary.

---

## 3. Required checks, per fold and on the final design

The following must run **on every chronological training fold** and **again on the final assembled
design**. The right-hand column names the `feature_gate.py` finding kind(s) that discharge the
requirement, so the obligation is concretely testable.

| # | Required check | `feature_gate.py` finding kind(s) | blocking? |
|---|---|---|---|
| 1 | **Numerical rank** of the standardised complete-case design | `rank_deficient` | yes |
| 1a | pairwise special cases of the same failure | `exact_duplicate`, `near_collinear`, `deterministic_transform_of_offset` | yes |
| 2 | **Conditioning** | `ill_conditioned` | yes |
| 3 | **Zero variance** | `zero_variance` | yes |
| 3a | **Near-zero variance** (`std < 1e-8`) | `impossible_scaling` | yes |
| 4 | **Missingness** | `missingness_present` | **no** — reported, not blocking |
| 5 | **Outcome-associated missingness** | `missingness_encodes_outcome`, `missingness_informative` | yes |
| 5a | outcome-associated **values** (as distinct from mask) | `target_derived` | yes |
| 6 | **Non-finite values** | `non_finite` | yes |
| 7 | **Scaling** (degenerate `std`, or `max\|x\| > 1e12`) | `impossible_scaling` | yes |
| 8 | **Schema consistency** train vs test | `schema_mismatch` | yes |

The full blocking set implemented in `feature_gate.BLOCKING` is:
`exact_duplicate`, `near_collinear`, `deterministic_transform_of_offset`, `zero_variance`,
`non_finite`, `impossible_scaling`, `schema_mismatch`, `target_derived`, `rank_deficient`,
`ill_conditioned`, `missingness_encodes_outcome`, `missingness_informative`.

Governing thresholds are the gate's own constants and defaults, not this contract's:
`RANK_TOL = 1e-8`, `COND_MAX = 1e6`, `corr_threshold = 0.999`,
`target_corr_threshold = 0.98`, `missingness_corr_threshold = 0.5`.

### 3.1 Optional arguments are not optional under this contract

Several checks in the table above **do not run at all** unless the caller supplies the corresponding
argument. Omitting an argument produces a silent pass, which is indistinguishable in the output from
a genuine pass unless the caller looks. Under this contract:

| argument to `feature_gate.audit` | must be supplied because | checks it enables |
|---|---|---|
| `offset=` | every turnover arm carries `log(exposure)` (and `log(D)`) in the offset | `deterministic_transform_of_offset` |
| `target=` | leakage from target-derived fields, and informative missingness | `target_derived`, `missingness_informative`, one branch of `missingness_encodes_outcome` |
| `outcome_mask=` | the exact-indicator branch of the null-mask check | `missingness_encodes_outcome` (exact off-diagonal test) |
| `test_df=` | fold train/test schema drift | `schema_mismatch` |

An audit record that omits an applicable argument is **not** a passing audit. It is an incomplete
audit and must be recorded as such.

---

## 4. Pooled-healthy / fold-degenerate

**A feature that is healthy pooled but degenerate in a fold must FAIL for that fold, or be governed
by a fallback frozen and registered before any result is visible.** There is no third option.

It may not be admitted because the pooled audit passed. It may not be admitted because the fold is
"early", "small", or "a warm-up". It may not be rescued by a remedy chosen after the failure is
observed. Any fallback — drop the column for that fold, fall back to the incumbent arm, widen the
training window, refuse to score the fold — must be part of the frozen specification, registered
before execution, with its trigger stated numerically.

A fold-level failure discovered after results are visible invalidates the affected arm's published
result. It does not license repair-and-rerun inside the same wave; the repaired specification is a
new frozen challenger in a later wave.

---

## 5. Convergence is not evidence

**A converging optimiser is not an acceptable substitute for any check in section 3.** This restates
`feature_gate.py`'s own note — "a converging optimiser does not validate an unidentified design" —
as an invocation-time obligation.

Convergence establishes that the solver reached a stationary point of a penalised objective. It
establishes nothing about whether the design was identified, whether the fold's scaling was sane, or
whether the null mask encoded the outcome. Penalised estimators converge on rank-deficient designs;
the coefficients are then a property of the penalty. The following are all inadmissible as
substitutes for a gate record:

- the fit converged, or converged in few iterations, or converged in every fold;
- the predictions are finite;
- the coefficients look plausible;
- the held-out metric improved.

P2's arms E and I converged (a damped IRLS with step-halving was added, and it converged) and
returned predictions peaking at `4.85e8` per row. ws3's stage 2 converged in five Newton iterations
in every fold while producing exactly saturated shares.

---

## 6. Recording requirement

Every fitted arm must emit a machine-readable per-fold gate record: one audit object per
chronological training fold, keyed by fold identifier, plus one for the final assembled design, plus
the argument set supplied to each call (§3.1).

**Absence of the per-fold record is itself a gate failure.** An arm whose fold-level audits were
never recorded may not be reported as having passed the gate. "The gate exists in the repository" is
not a gate record.

---

## 7. What this gate does NOT catch

This section exists so that a passing gate record is never read as more than it is. **Passing
`feature_gate.audit` on every fold does not establish that a design is identified or leakage-free.**
It establishes that the specific enumerated failure modes in section 3 were tested for and not
found.

Known and currently open:

1. **Nonlinear deterministic dependency.** The rank and conditioning checks operate on the
   standardised design via SVD, and the duplicate/collinearity checks on Pearson correlation. Both
   are linear. A feature that is a deterministic function of the others through a **nonlinear** map
   — a product, a ratio, a rank transform, a threshold indicator, a softmax share — can be exactly
   redundant while the design retains full numerical rank and unremarkable pairwise correlations.
   The gate passes it. This is an open gap, not a solved one.

2. **Anything that is a property of the COMPARISON rather than of the design matrix.** The gate
   audits one matrix. It has no view of the incumbent, of what fitting flexibility the challenger
   received that the baseline did not, of intercept treatment, calibration freedom, clipping,
   evaluation-row alignment, companion components or fallback rules. No feature-matrix check can
   catch these, because they are not properties of the features.

   That class is the subject of a **separate** contract, `comparison_gate.py`, being built in
   parallel as Workstream A. This document neither specifies nor assumes anything about its
   interface beyond the module name; consult that module and its own contract. The two gates are
   complementary and neither subsumes the other. The concrete case: an unpenalised intercept given
   to a fitted challenger but not to an unfitted incumbent is worth about **`+0.0033`** operational
   team MAE — the size of the effects being hunted — and `feature_gate.py` cannot see it, because
   the challenger's feature matrix is entirely innocent.

3. **Construction-time provenance.** The gate sees the assembled matrix, not how it was built. A
   column derived from post-cutoff information whose values happen not to correlate above threshold
   with the target, and whose null mask happens not to be an exact outcome indicator, passes. Cutoff
   validity remains a registration obligation and a producer obligation, and is not delegated here.

Accordingly: a gate record is a **necessary** condition for reporting an arm, never a sufficient
one, and must never be cited as evidence that no unidentified or leakage-prone construction is
present.

---

## 8. Precedence

Where this contract and an arm's own registration disagree on invocation timing, this contract
governs. Where an arm's registration is stricter, the stricter requirement governs. Where this
contract and `feature_gate.py` appear to disagree about what a check does, `feature_gate.py`
governs — it is the implementation, and this document does not modify it.

## 8a. Dual-frame requirement — audit BEFORE and AFTER missing-value transformation

**Status: REQUIRED BY THIS CONTRACT. NOT YET IMPLEMENTED in `gate_invocation.py` (`d58a6b2`).
It is a standing methodological gap, not a closed class.**

The ws2 defect is a different failure from a missing or defaulted argument, and the wrapper's
`argument_is_placeholder_default` does **not** catch it. ws2's `build_constructions()` imputed
`offensive_involvement_proxy` and `trailing_minutes_share` to `0.0` **before** the gate was
called. What reached the gate was:

* a fully populated, imputed design with no nulls at all;
* a valid, non-placeholder `target`, `offset`, `outcome_mask` and `test_df`;
* correctly aligned row identities.

Every fold passed. The null mask had already been converted into ordinary numeric values, and it
survived as one: `transfer_direct`, `transfer_allocated` and `transfer_role_sensitive` are
non-zero on 25,522 / 25,522 / 9,577 appearers and on **zero** of the 8,278 non-appearers, so a
non-zero value certifies appearance. `missingness_encodes_outcome` cannot fire on a frame with no
missingness. **A gate that only ever sees the transformed frame is blind to this by construction.**

Accordingly, every fitted design must be audited **before** missing-value transformation and
**again** after it. The invocation receipt must bind:

* raw feature-frame digest;
* raw missingness-mask digest, **per column**;
* the transformation or imputation specification, declared explicitly;
* transformed feature-frame digest;
* the transformed design audit;
* confirmation that no feature was constructed from target-game appearance or any other
  post-cutoff outcome.

Invocation must fail **before fitting** when:

* only the transformed frame is supplied;
* raw missingness provenance is unavailable;
* an imputation operation is not declared;
* raw and transformed feature names or row identities do not reconcile;
* the transformed values encode an outcome-associated raw null mask;
* a caller audits one matrix but fits another.

Until that is implemented, no claim may be made that the invocation layer closes the ws2 class.
The wrapper closes argument omission, defaulting, misalignment, universe substitution, silent
reordering and receipt reuse. It does **not** close pre-gate transformation.

## 9. Retrospective note

Had this contract been in force at P2 (`turnover_rate_role_context_v1`), and had the gate existed in
its current form, arms E and I would have been blocked pre-fit on `near_collinear` and
`rank_deficient`, and arms F and G would have been blocked pre-fit on
`missingness_encodes_outcome`. This is stated as a retrospective observation about invocation
timing. It is **not** a licence to repair and re-run those arms inside the P2 wave; see
`turnover_p2_v1/P2_SUPERSESSION.md`.
