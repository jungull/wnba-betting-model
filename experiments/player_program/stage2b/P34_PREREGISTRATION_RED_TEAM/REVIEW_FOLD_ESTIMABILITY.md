# P34 RED TEAM — REVIEW: FOLD ESTIMABILITY

**Reviewer dimension:** fold estimability (single-active-fold licensing, per-fold support, active-set
deferrals, per-fold data dependencies vs the five D006 folds, universe re-derivation).
**Reviewer independence:** this reviewer did not author the preregistration and read no other
P34 reviewer file (REVIEW_LEAKAGE.md and REVIEW_TARGET_UNITS.md were present in this directory
when I wrote this file; I did not open either).

ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean review does not make an arm true; it makes it fittable.

**Verdict: ACCEPT_WITH_REQUIRED_CHANGES.**
**Stop condition: NOT TRIPPED** — nothing below requires changing the primary target, the K0
structure, the five-fold/cluster inference structure, the candidate universe, the cutoff-valid
feature set, or the leakage status. One caveat stated plainly: if the required fix to A08
(finding F1) were resolved by *dropping* training rows for that arm, the arm's per-fold row set
would deviate from the frozen fold table; that is an arm-level section-4 fallback, not a change
to D006, but the P35 freeze must say so explicitly rather than let it be discovered at invocation.

## 0. Inputs verified

All four pinned hashes verified (`Get-FileHash -Algorithm SHA256`) before any reading:
P33 SPEC.json `066b2a04…`, P33 REPORT.md `6d945b86…`, P32 SPEC.json `1dc25981…`,
P30 EVIDENCE_PACKET_V3.json `95d2412c…` — **ALL MATCH**.

## 1. What I measured and how

Two scripts, run live against the frozen artifacts via
`possession_features.load_universe()` / `chronological_folds()`:

* `scratchpad/p34_fold_estimability_measurements.py` — universe/fold re-derivation, depth
  histogram, A03 tier support (train **and test** side), A05 playoff support, A14 expansion
  support incl. distinct-franchise counts, zero-prior-game rows (universe proxy), A08 trailing
  league-window definedness per fold per K, training seasons per fold, fold-5 test season types.
* `scratchpad/p34_fold_estimability_measurements2.py` — full-schedule reference counts (2,990 /
  1,495 / 8 unresolved), possession-archive coverage of the 8 excluded team-games, zero-prior
  rows recomputed against the **possessions archive** (the lag operator's actual source), and
  A14 effective decay support.

Both scripts are feature/schedule-only: no target value entered any statistic, nothing was
fitted, no performance number was computed, nothing under SEALED_RESULTS was read.

### 1.1 Universe and fold re-derivation — VERIFIED EXACTLY

* Universe: **2,982 rows / 1,491 clusters**, seasons 2021–2026. Full-schedule reference
  2,990 rows / 1,495 clusters with exactly 8 `pace_resolved == False` rows. Matches SPEC and D006.
* Five folds, byte-identical to the SPEC table (fold ids, cutoffs 2022-05-06 / 2023-05-19 /
  2024-05-14 / 2025-05-16 / 2026-05-08, train rows 410/888/1408/1932/2552, test rows
  478/520/524/620/430, train clusters 205/444/704/966/1276, test clusters 239/260/262/310/215).
* Games never split: `rows == 2 × clusters` holds in the train **and** test side of all five
  folds (the SPEC states it measured only the train side; I confirmed both).
* Depth histogram reproduced exactly: {0: 37, 3–9: 76 each, 10: 2413}; no rows at depth 1 or 2,
  confirming the A03 t=3 rationale's factual premise.

### 1.2 Arm-level support measurements (verbatim numbers)

* **A03**: shallow (depth ≤ 3) training clusters by fold **24/36/46/57/69** — reproduces the
  SPEC exactly; deep tier 189/428/686/947/1253. Test-side shallow support (NOT in the SPEC):
  rows **12/12/12/16/21**, clusters **12/10/11/12/15**.
* **A05**: training playoff clusters **17/40/60/82/106**; test playoff rows **46/40/44/48/0**;
  fold-5 test contains only `Regular Season` (430 rows). The declared numeric trigger
  (test playoff rows == 0 in train_lt_2026) is confirmed against the bytes.
* **A14**: expansion teams 1611661331 (first season 2025), 1611661327/1611661332 (2026).
  Expansion training clusters by fold **0/0/0/0/46** — reproduces the SPEC. New measurements
  the SPEC does not contain: distinct expansion **franchises** in train_lt_2026 training = **1**
  (1611661331 only); test-side fold-5 expansion rows = 57 across **2 different franchises**;
  fold-4 (train_lt_2025) has 46 expansion TEST rows with 0 training support (arm correctly
  inactive there). Effective decay support in train_lt_2026: clusters with treatment
  `exp_i·exp(−n_i/5)` ≥ 0.05 → **15**; ≥ 0.1 → **12**; ≥ 0.2 → **9** (vs 46 nominal flag clusters).
* **A08**: training rows with fewer than K completed league games strictly before their date
  (i.e., rows where the TS4 window definition leaves L_t undefined): K=20 → **44 rows in every
  training fold** (10.7% of fold-1 training); K=80 → **162 rows in every training fold**
  (**39.5%** of fold-1 training). All are 2021 rows, hence training-only; no test row is affected.
* **A11/A12/A13**: train_lt_2022's training set contains season **2021 only** (schedule fact
  confirmed); every later training fold contains at least one full season with an archived prior
  season, so the A12/A13 ≥10-cluster |dev_prev| > 0 floors in folds 2–5 have a schedule-fact
  lower bound in the hundreds of clusters.
* **Zero-prior-game rows** (against the possessions archive, the lag operator's actual source;
  all 8 excluded opening-day team-games DO have possession rows, so they count as priors):
  exactly **7 universe rows** whose offense team has zero strictly earlier possession-archive
  games — four 2021-05-15 rows (teams 1611661319/1611661322/1611661328/1611661329), plus the
  three expansion debuts (2025-05-16, 2026-05-08, 2026-05-09). These sit in **5 clusters
  (10 rows)** once the paired defensive side is counted. Fold placement: the four 2021 rows are
  in every training fold; the 2025 debut is a fold-4 TEST row and fold-5 training row; the two
  2026 debuts are fold-5 TEST rows.

## 2. Findings

### F1 (Severity B) — A08's window-definedness constraint is measurably unsatisfiable for BOTH enumerated K, in every training fold; internal contradiction frozen into the spec

The SPEC freezes two mutually inconsistent statements for A08 and then defers the collision to
invocation:

* the TS4 window definition ("rows are defined once >= K league games are completed", quoted in
  `hyperparameters.handling`), under which L_t is undefined on the archive's first K league games; and
* the element constraint: "K elements must keep L_t defined on **all rows of every training
  fold** … verified at P25/P27 invocation".

Measured: L_t is undefined on 44 training rows (K=20) and 162 training rows (K=80) in **every**
fold, because every expanding-window training fold contains the 2021 season head. Under the
literal constraint, **both** elements of A08's grid fail at invocation → the arm evaporates
post-freeze as a "design failure" nobody predicted (its own expected_failure_mode names P25
near-affinity, not this), and the timeseries_shrinkage Holm denominator (10) silently changes
after the P35 freeze. The alternative reading — that the "symmetric training-support-based
window rule" *handles* undefined rows "identically in arm and null" (A08.cold_start_behaviour) —
has no frozen content: no drop rule, no imputation, nothing that says what the 44/162 rows do.
GATE_INVOCATION_CONTRACT §4 is explicit that any such fallback "must be part of the frozen
specification, registered before any result is visible" and that a fold-level failure discovered
after results invalidates the arm's published result. This is decidable **today** (I decided it
with schedule facts alone) and must not be left to invocation.

**Required change:** before P35 freeze, either (a) freeze the pre-window-row rule explicitly
(e.g., drop those rows for arm AND null in that fold, or a declared deterministic imputation),
restating A08's per-fold row counts accordingly, or (b) withdraw the failing element(s)/arm now
and restate the family budget. Note the fix is training-side only: no test row is affected.

### F2 (Severity B) — Four arms carry a definedness claim the bytes refute: 7 rows have zero prior possession-archive games; A16/A17/A19/A21's "defined on every row" is false, including on TEST rows of folds 4 and 5

* A16.fallback: "resolved universe already excludes the no-prior-games stratum; defined on all
  2,982 rows in every fold" — **FALSE**: 7 offense-side rows have |P| = 0; the own-minus-opp
  contrast is undefined on all 10 rows of the 5 affected clusters.
* A17 ("share defined from |P| >= 1 by universe construction"), A19 ("share defined on every
  row"), A21 ("defined on every row, bounded [0,1]") inherit the same false premise for their
  own side and doubly for the symmetric (own+opp)/2 constructions.
* Materially: 2 affected clusters sit inside every training fold; **1 affected row is a fold-4
  TEST row and 2 are fold-5 TEST rows** (the expansion debuts). An arm whose treatment column is
  undefined on a test row cannot produce that row's prediction, while its K0 null (which
  excludes the column) can — an undeclared arm/null row-set asymmetry that would surface only at
  fit time, exactly the discovered-too-late failure §4 prohibits. A22 is the model to copy: it
  declares churn := 0 for the no-base-window case. A18/A20/A26 are immune (E=3 imputation covers
  the zero-prior stratum deterministically).

**Required change:** correct the four definedness claims and freeze a deterministic, symmetric
|P| = 0 rule per arm (A16, A17, A19, A21) before P35 — imputation value or row treatment,
identical in arm and null, covering the enumerated 7 offense-side rows / 5 clusters.

### F3 (Severity B) — A14's Holm-slot mechanics are underdetermined, and under one admissible reading the promotion-ineligible diagnostic arm can BLOCK a real arm's promotion

The draft keeps A14 as 1 of 5 COLDSTART_FALLBACK elements "so the family denominator is not
quietly shrunk" and says "its test is still performed" — but never states whether A14's
primary-gate p-value **enters the Holm step-down ordering**. The two readings differ materially:

* If A14's p enters the ordering: Holm's stopping rule means an intermediate non-rejection by
  A14 terminates the sequence, so promotable arms (A07/A12/A13/A15) with p-values behind A14's
  can be denied testing at thresholds they would have passed under m = 4. A promotion decision
  would then depend on the p-value of an arm that (i) cannot be promoted and (ii) is confounded
  with a single franchise (F4). Conservative, but not what "retaining the denominator" implies.
* If A14 is a fixed non-rejected slot (p := 1, always last): the family is Holm over the other
  four at denominators 5,4,3,2 — pure m-inflation, no blocking. This appears to be the intent
  but is written nowhere.

**Required change:** P35 must pin one reading. Recommendation: the fixed-slot reading (A14
charged to m, excluded from the ordering), which matches the draft's stated purpose and removes
the blocking pathology.

### F4 (Severity B) — A14's single-active-fold licensing omits a measured confound: the training stratum is ONE franchise, and effective decay support is 9–15 clusters, not 46

Measured: in train_lt_2026, all 46 expansion training clusters belong to a single franchise
(1611661331, first season 2025); the 2026 test-side expansion rows belong to two *different*
franchises. Within the only active fold, `exp_i` on training data is exactly a
one-franchise-one-season indicator, so kappa-hat is unidentifiable against that franchise's
idiosyncratic level — "expansion effect" and "this one team was fast/slow" are the same
parameter in this design. Additionally, the treatment column's decay means the 10-cluster floor
(46 nominal) overstates identifying variation: clusters with treatment ≥ 0.05 number 15; ≥ 0.2
number 9. The restated kills ARE decidable as written — (i) floor re-check, (ii) interval covers
0, (iii) interval excludes 0, (iv) replaced — I verify that; but outcome (iii)'s label
`PRELIMINARY_SUPPORTED_SINGLE_FOLD`, carried to the next cycle without the confound stated, is
an over-read waiting to happen.

**Required change:** add to `single_active_fold_licensing`: the licensed statement is about the
2025 cohort of exactly one franchise, kappa-hat is confounded with that franchise's identity,
and the effective decayed support (~9–15 clusters) accompanies any carried-forward record.
**On the mandate's other question — is keeping A14 in the fit set justified at all:** yes,
conditionally. The fit is cheap, preregistered, feeds the next cycle, and its floor is met; but
its retention is only sound jointly with F3's fixed-slot resolution and this licensing caveat.
If neither lands at P35, the correct disposition is to drop A14 from the fit set and shrink the
family to 4 declared elements — openly, not quietly.

### F5 (Severity B) — A11's fold-1 fallback names a mechanism, not a rule; fold-1 evaluability is undefined while 100% of its training rows lack dprev

Measured schedule fact: train_lt_2022's training set is the 2021 season only; `dprev_t` is
undefined (no archived prior season) on **every** training row. A11 declares "GATE_INVOCATION_
CONTRACT section 4 fold-level fallback DECLARED for train_lt_2022's training season" — but §4
offers a menu (drop the column for that fold / fall back to the incumbent arm / widen the
window / refuse to score the fold) and requires the *choice* to be frozen. A11 freezes no
choice. Consequences left undecidable: (a) does fold 1 enter A11's pooled delta_MAE (if the
column is dropped, arm == null on fold 1 and its 478 test rows purely dilute the pooled
statistic — note fold-1 TEST rows are 2022 rows where dprev IS defined, so a fallback model
simply refuses information the arm's own formula wants); (b) does fold 1 count as "evaluable"
for the rho-interval kill ("includes 1 in every evaluable fold")? Contrast A12/A13, which handle
the identical situation crisply (explicit structural deactivation, folds 2–5 active), and A05
("five fitted, four evaluable" with a numeric trigger). A11 must be brought to that standard.

**Required change:** name the §4 option and state fold-1 evaluability for both the pooled
primary gate and the coefficient kill, before P35.

### F6 (Severity B) — The active-set rule every thin-support arm leans on is, by its own frozen text, "NOT registered for any arm"

`P27_FOLD_LOCAL_ESTIMABILITY_GUARD/ACTIVE_SET_RULE_PREREGISTRATION.json` (hash-pinned by P33)
states: "It is NOT registered for any arm. An arm that wishes to use it must register it in the
arm registry before its own execution; this file is the guard's conformance example, not a
program-level registration." P33 cites the file as the operative fallback authority for A03
("active-set rule per ACTIVE_SET_RULE_PREREGISTRATION.json") and A04/A12/A13/A14 declare rules
identical in form — but the P33 draft creates no registration obligation. If the rule is
unregistered at fit time, a fold-level deactivation would rest on an unregistered fallback,
which §4 treats as invalidating when noticed post-results.

**Required change:** the P35 task cards must register S7_TIER_SUPPORT_v1 (or the arm-specific
instances) in the arm registry for every arm that invokes it, per the guard file's own condition.

### F7 (Severity C) — A12/A13 deferral to P27-at-invocation is SOUND; the residual risk is negligible and bounded by schedule facts

The mandate asked whether the deferral risks a fold-degenerate fit discovered too late. It does
not, materially: the deferred quantity (≥10 training clusters with |dev_prev| > 0 in folds 2–5)
has a schedule-fact lower bound of hundreds of clusters per fold (every training fold from
train_lt_2023 on contains at least one complete season whose teams all have an archived prior
season; dev_prev = 0 exactly requires a team's prior-season mean to equal the league mean to the
last bit). The genuinely-P36 part is only the numeric |dev_prev| > 0 check. Deferral upheld;
recommend P35 record the schedule-fact lower bound so the invocation check is a confirmation,
not a decision. The fold-1 structural deactivation is verified as a schedule fact.

### F8 (Severity C) — The P27 rule conditions on training-side support ONLY; the test-side blind spot was hand-patched for A05 but no general rule exists

The active-set rule's own text: "conditions_on: SupportSummary (training-fold counts only)".
A05's fold-5 test-side degeneracy (0 playoff test rows — verified) was caught and given a
bespoke numeric trigger, which I verify as decidable and correctly derived. But that catch was
per-arm diligence, not structure: no preregistered rule exists that would flag a
training-supported/test-degenerate fold for any other arm. Measured today, no other arm has a
fully test-degenerate fold (A03 test-side shallow rows 12/12/12/16/21; A14 fold-5 test expansion
rows 57), so this is a record-level finding, not a blocking one this cycle.

### F9 (Severity C) — A03 verified; note the per-fold discrimination rests on 12–21 test rows

Training support reproduced exactly (24/36/46/57/69 shallow clusters ≥ 10 everywhere); the t=3
rationale's premises (no depth-1/2 rows; {0,1,2} thresholds collapse to the 37-row league-prior
stratum) are confirmed in the bytes. The SPEC reports only training-side support; the test-side
signal carrier is 12–21 rows (2.5–4.9% of test rows) per fold. That is power, and the arm's
expected_failure_mode already names power as the likely death — consistent, no defect. Recorded
so the eventual null is read as underpowered-stratum evidence, not mechanism refutation.

### F10 (Severity C) — No frozen rule for degenerate bootstrap draws or IRLS non-convergence inside a draw

The training-cluster bootstrap (B = 2,000, refit per draw) has no rule for a draw in which a
thin stratum vanishes or IRLS hits max 100 iterations. Quantified for the current arms, the
degenerate-draw probability is negligible (zero playoff clusters in a fold-1 draw ≈ e^−17 ≈
4×10⁻⁸; shallow ≈ e^−24; expansion ≈ e^−46), so this is a completeness note for the P35 cards
(state: drop-and-redraw vs NA-propagation, and the non-convergence disposition), not a threat to
any current arm.

## 3. Contradictions found (documents vs documents / documents vs bytes)

1. **Within P33 SPEC (A08):** TS4 window definition ("defined once ≥ K league games are
   completed") vs the element constraint ("keep L_t defined on all rows of every training
   fold") — irreconcilable as written; measured 44 (K=20) and 162 (K=80) undefined training
   rows in every fold. (F1)
2. **P33 SPEC vs bytes:** A16 "resolved universe already excludes the no-prior-games stratum" /
   A17 "|P| ≥ 1 by universe construction" / A19, A21 "defined on every row" — vs 7 measured
   zero-prior offense rows (5 clusters, 10 rows), three of them test rows in folds 4–5. (F2)
3. **P33 SPEC vs P27 guard file:** P33 cites ACTIVE_SET_RULE_PREREGISTRATION.json as an arm's
   operative fallback; the file's own frozen text says it is a reference instance registered
   for no arm. (F6)
4. **No contradiction found** in: the universe/fold table (verified exactly), the A03/A05/A14
   support numbers (all reproduced to the digit), the depth histogram, or the games-never-split
   invariant (verified on both train and test sides).

## 4. What I could NOT establish, and why

* Whether the possessions-archive rows of the 8 excluded 2021-05-14 team-games are themselves
  fit for lag aggregation under P22 (they exist — all 8 have possession rows — but their
  adjudication is P22's at invocation, not mine).
* A12/A13's actual |dev_prev| > 0 cluster counts (requires building P36 lagged aggregates;
  I established only the schedule-fact lower bound in F7).
* Whether IRLS convergence behaves on bootstrap draws (F10) — would require fitting, which this
  node may not do.
* How the other P34 reviewers' findings interact with mine — by design; I read none of them.

## 5. On the self-frozen quasi-Poisson IRLS convention (as it touches this dimension only)

The response-family freeze is inference-structure territory owned by other reviewers; from the
fold-estimability side I note only: quasi-Poisson IRLS point estimation is well-defined on every
per-fold design measured here (large counts, no separation risk from the indicator terms at the
measured supports), and no fold-local estimability objection arises from the family choice
itself. The only estimability-adjacent gap it leaves is F10 (non-convergence disposition inside
bootstrap draws), which is a P35 completeness item.

## 6. Verdict

**ACCEPT_WITH_REQUIRED_CHANGES.** Six Severity B findings (F1–F6) must be closed at or before
the P35 task-card freeze; none requires changing fold structure, universe, target, K0, or
inference structure, and none admits leakage. The fold table, universe re-derivation, A03/A05/
A14 support measurements, and the A05 four-effective-folds declaration are verified against the
bytes to the digit. A14's restated kills are decidable as written; its retention in the fit set
is justified only jointly with the F3 Holm-slot pin and the F4 licensing caveat.
