# P33_PREREGISTRATION_DRAFT — report

PREREGISTRATION DRAFT. Not yet frozen; not yet authorisation to fit.

This node froze all 26 retained arms of the amended P32 SPEC into fit-ready preregistration
records (`SPEC.json` beside this report), discharged or carried every inherited D021 obligation,
and executed the measurable parts of the collapse rules. Nothing was fitted; no performance
number was computed; nothing under `SEALED_RESULTS` was read (the directory does not exist);
no frozen artifact was modified; nothing was written outside this directory.

## 1. Input verification

Both mandated inputs verified by sha256 over raw bytes before any other read
(`Get-FileHash -Algorithm SHA256`):

| input | expected | measured | match |
|---|---|---|---|
| `stage2b/P32_CANDIDATE_SYNTHESIS/SPEC.json` (amended) | `1dc25981ed14be0ef59c994a47a99970d790b644d8cdce354c617f9198c2138c` | same (case-insensitive) | YES |
| `stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json` | `95d2412c28ce34bb6330f5055bc9087693c1d70ed21a12b4edb5b5f950875e75` | same | YES |

Also read as committed: P32 `ADJUDICATION.md` and `AMENDMENT_LOG.md`,
`stage2a/EVIDENCE_PACKET_V2.json` (hash re-derived, matches the pinned
`3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c`),
`stage2a/PHASE0A_RESOLUTION.md` (matches `137b7267d0a364320c0ef2121151da1652ae6454a18e96dd02039097b51a4b91`),
`stage2a/V2_STOP_CONDITION.json` (all nine findings), `PROGRAM_STATE.json`,
`RESEARCH_CONTRACT_V1.md`, `GATE_INVOCATION_CONTRACT.md`, and the D1-D9 preserved
disagreements inside the amended SPEC. `possession_features.py` re-hashed:
`d44cca3828476e1c38b1e310d5ef9974e46afa68df8596cb22fdd24e2670d105`, identical to the value
pinned at D021. `offset_dependency_guard.py` re-hashed:
`c78e70b6a0603b15bd74dd4dd798ba698d962565e813b2eee8df9360cc100e95`.
`ACTIVE_SET_RULE_PREREGISTRATION.json` re-hashed: matches the SPEC-cited
`327fa8ec9fb54e3635ae70b540573b4121c6136fc5034cbdb689cabbe2986db7`.

## 2. How each inherited obligation was discharged

**(1) INFERENCE_SPEC_GAP — DISCHARGED FROM RECEIPTS; nothing invented.**
The receipted estimator convention was located in the frozen implementation, which governs over
prose (RESEARCH_CONTRACT_V1 precedence):

* `possession_features.py` line 319: `F[OFFSET_COLUMN] = np.log(F["projected_team_off_possessions"]...)`;
  line 135: `OFFSET_COLUMN = "log_projected_team_off_possessions"`; line 515: the offset is handed
  to the gates renamed `log_exposure`; docstring lines 62-64: "projected_team_off_possessions --
  it is the OFFSET (as a log), not a feature".
* `incumbent_input` (lines 399-406): the incumbent's prediction **is**
  `projected_team_off_possessions`.
* `GATE_INVOCATION_CONTRACT.md` section 3.1: "every turnover arm carries `log(exposure)` ... in
  the offset".

Together with the k0_matched core rule that every nested null must recover the incumbent
EXACTLY at zero treatment, these fix the **link as LOG**: a linear predictor carrying the
receipted log-scale offset reproduces the incumbent's frozen prediction at zero treatment iff
the mean is `exp(linear predictor)`. Measured, not asserted: max abs deviation of the offset
column from `log(projected_team_off_possessions)` over all 2,982 rows = **0.0**.

Centered-offset treatment scale: for A01/A04, `off` **is** the receipted `log_exposure`, so
`(off - m_bar)` is on the **log scale** with `m_bar` the training-fold mean of `log_exposure`
-- fixed by the identity of the only receipted `off` object. For A02 the treatment column is
not a function of the offset at all: measured on all 2,982 rows,
`(own_est - opp_est) == pace_gap` exactly (see obligation 3). The response FAMILY is fixed by
no receipt and none was claimed: the draft freezes Poisson quasi-likelihood IRLS as the
estimation objective with the reasoning stated in
`SPEC.json.inference_spec_gap_resolution.estimation_objective_frozen_here` (the measured
under-dispersion 0.193 biases only likelihood-based SEs, which are never used -- all inference
is game-cluster bootstrap). No arm is preregistration-incomplete on this ground.

**(2) A06 — preregistered CONDITIONALLY, not admitted.** INADMISSIBLE_UNTIL_RECEIPTED carried
verbatim with both repair paths; the condition is decidable (receipt hash-pinned before the P35
task-card freeze, else A06 is excluded from the P36 fit set this cycle, recorded
`PREREGISTERED_CONDITIONAL_NOT_FIT`, and its 2 conditional elements leave the family
denominator). Its enumerations are fixed now regardless (thirds-bins 2 df; monotone class
bounded to exactly `{identity}` -- the AI-H5 source's sole example). No preseason schedule
artifact exists inside `experiments/player_program/`; established by directory enumeration.

**(3) A02 — condition DISCHARGED from receipts; arm now unconditional.**
`own_est`/`opp_est` are `team_pace_estimate`/`opp_pace_estimate` of
`team_possession_prior_v1.parquet` (canonical, sha256
`c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18` per PROGRAM_STATE), on the
Stage 1B receipted path governed by D009 standard (a); the mapping is pinned by P25 `TESTS.py`
lines 60-71. Measured by this node on all 2,982 rows: this row's `opp_pace_estimate` equals
the paired row's `team_pace_estimate` (max abs dev 0.0); `own_est + opp_est == 2*projected`
(0.0); and `(own_est - opp_est) == pace_gap` **exactly** (0.0 -- `pace_gap` is constructed as
precisely this difference at `possession_features.py` line 315). The A02/A15 accounting is
pinned: A02 tests the gap MAIN effect (null without it); A15 is credited only for the gap*asym
interaction (gap main granted to its null); neither may claim the other's term. A02's
fold-local full rank was re-measured on the actual five D006 folds (R11 had measured six
season blocks): corr(pace_gap, log_exposure) ~ 1e-18, R2 ~ 0, condition number 1.000 in every
training fold.

**(4) Enumeration obligations — all seven fixed, each element charged.**
A03: single element t = 3 (the incumbent's own switching boundary, pace_level > 1 iff
game_no_in_season <= 3, measured 2982/2982 in EVIDENCE_PACKET_V2.control_specification;
measured depth histogram {0, 3..10} shows t in {0,1,2} is the same 37-row stratum with failing
support). A04: basis = binary tier only (kernel struck at D021), threshold tied to A03's t = 3
-- 1 element. A06: 2 conditional elements (above). A08: K in {20, 80} ("K small" is the
source's own bound; factor-4 log bracket of the two named drift horizons). A09: kappa in
{2, 10, 50} (half-weight points; 10 anchors the producer's frozen WINDOW_K = 10). A10: lambda
in {0.2, 0.5} (excludes the incumbent's own alpha = 0.1 by design -- that element is the arm's
declared P25 death). A11: rho in {0.25, 0.5, 0.75} (interior of [0,1]; both boundaries are
null presumptions). A16: k = 5, the program's only recurring frozen trailing-evidence scale
(tau = 5, h = 5, s-scale 5), inside the producer's evidence cap. Every justification is
written into the arm record; the word "small" appears nowhere as a specification.

**(5) A14 — single-active-fold licensing and decidable kills, with the support question now
MEASURED.** P32 could not measure expansion support; this node could and did: expansion teams
in the frozen prior artifact are 1611661331 (first season 2025) and 1611661327/1611661332
(first season 2026); expansion training-cluster counts by fold are 0/0/0/0/**46**. Exactly one
active training fold (train_lt_2026) -- the D021-anticipated case is the measured reality. The
draft states in advance: a single-active-fold result licenses only a fold-local diagnostic
statement; A14 is **promotion-ineligible this cycle by structure**, retains its Holm slot so
the family denominator is not quietly shrunk, and its kill conditions are restated decidably
for the one-fold case (retired-unevaluated / KILLED / PRELIMINARY_SUPPORTED_SINGLE_FOLD; sign
stability replaced by the ineligibility declaration). Also measured: team_id 1611661317
(PHO/PHX) has first season 2021, so no rebrand resolution can flip the expansion set -- the
P23 precondition still travels with the arm.

**(6) Collapse rules — defined concretely, and executed where measurable.**
Near-affinity test frozen numerically: R2(u ~ 1 + v) >= NEAR_R2 = 0.998001
(`offset_dependency_guard.py` line 75) or |spearman| >= 0.999 (line 77) in EVERY training
fold. S7 tiebreak frozen deterministically: lower max per-training-fold condition number of
the complete standardised design; then fewer treatment df; then lexicographic arm_id.
**A03/A07: EXECUTED — no collapse.** Measured per training fold: R2 = 0.7134 / 0.3321 /
0.2359 / 0.1923 / 0.1770, spearman = 0.5141 / 0.3794 / 0.3291 / 0.3034 / 0.2904 -- nowhere
near either threshold. Both arms proceed with full budgets. **A04/A09: frozen, directional
(A09 withdraws into F04 on failure), executed at the P25 call site before any fit** --
constructing A09's d_t is P36 implementation scope; the test needs no discretion. Bonus
measurement: A07's declared risk against depth is quantified -- R2(exp(-n/5) ~ 1 + depth) =
0.958 in train_lt_2022 (elevated, below the blocking threshold), 0.31-0.49 elsewhere.

**(7) A23 — the two source-consistent bundles paired; no cross-product.**
bundle_AI = {cap 7, previous SCHEDULED same-season game, S7 symmetric opener fallback};
bundle_OM = {cap 4, most recent COMPLETED same-season game, opener = fully-rested cap
assignment}. 2 elements charged; the 8-cell cross-product is explicitly NOT preregistered.
One honesty note: the D021 record's phrase "cap 4-or-merged" is ambiguous; resolved to the
source-frozen cap 4 because only source-frozen constants are admissible bundle members
(AI-H2's 7 was an example, corrected at D021 -- it survives only inside bundle_AI as that
source's own bundle).

**(8) D1-D9 — none silently harmonized.** Dispositions per disagreement are in
`SPEC.json.preserved_disagreements_disposition`. Two need calling out:

* **D1 resolved from receipts (no performance peeking).** `PROJECTED_EXPOSURE_RECEIPT.json`
  `pace.source_counts`: team_window_same_season 2762, team_window_prior_season 183,
  league_prior_all 37, unresolved 8. The incumbent **switches** tiers; it never blends
  prior-season with current-season evidence at any weight. Therefore neither A11's rho = 1
  null nor A12's no-carryover null is "the incumbent's construction"; A11's null gloss
  ("incumbent-equivalent undifferentiated pooling") is corrected in the frozen record to
  "undifferentiated-pooling reference model". Both arms stand as distinct preregistered
  readings -- which is the both-readings-as-distinct-arms branch of the obligation.
* **D2/D5 (multiplicity partition).** Each arm is charged to its canonical source's declared
  family (provenance rule); every disputed arm (A06, A07, A11, A12, A13) must additionally
  survive Holm under BOTH candidate partitions -- stricter governs, per RESEARCH_CONTRACT_V1.
  Neither reading is erased.

## 3. What was measured, and how

Hash verifications: `Get-FileHash -Algorithm SHA256 <path>` (PowerShell), reported in section 1.
All other numbers come from one script run once:

    python <scratchpad>/p33_measurements.py

The script is feature/schedule-only; the target column is never read into any statistic;
nothing is fitted; no comparative historical performance of any challenger was inspected. Its
complete JSON output is embedded in `SPEC.json.measurements_by_this_node`, and the script's
logic is fully specified there field-by-field (universe re-derivation via
`possession_features.load_universe()` and `chronological_folds()`; exact identity deviations
via numpy max-abs; per-training-fold R2/spearman/condition numbers via least squares on
centered-standardised columns; expansion/playoff/tier cluster counts via pandas groupby on
`game_id`). Headlines:

* **Universe re-derived live:** 2,982 rows / 1,491 clusters, seasons 2021-2026; exactly the
  five D006 folds with the pinned train/test row counts; train clusters = train rows / 2
  exactly in every fold (410/205, 888/444, 1408/704, 1932/966, 2552/1276) -- games never split.
* **Offset convention:** offset column == log(projection), max abs dev 0.0 (2,982 rows).
* **A02 identities:** all three measured at exactly 0.0 (section 2.3).
* **A03/A07 collapse test and A07-vs-depth:** section 2.6.
* **A03 tier support (t = 3):** shallow training clusters 24/36/46/57/69, deep
  189/428/686/947/1253 -- both tiers >= 10 clusters in every training fold.
* **A05:** training playoff clusters 17/40/60/82/106; fold-2026 test playoff rows = 0 (the S7
  degeneracy, now measured at the fold level, with the section-4 fallback declared).
* **A14:** expansion clusters by training fold 0/0/0/0/46 (section 2.5).
* **A16 archive retrievability (P32 could-not-establish #3 resolved):**
  `team_possession_prior_v1.parquet` carries `projected_team_off_possessions` per
  (game_id, team_id) row for all 2,990 team-games, read live -- archived per-prior-game
  projections are retrievable without recomputation.

## 4. What could NOT be established

Carried in `SPEC.json.could_not_establish`: the A06 repair receipt (does not exist in scope;
stays conditional); the A19/A20 end_reason dictionary adequacy (deferred to the P35 dictionary
freeze; withdrawal-on-failure preregistered); the A04/A09 near-affinity numbers (test frozen;
d_t construction is P36 scope); A12/A13 active-set counts for folds >= 2023 (lagged aggregates
are P36 scope; the 2021 structural deactivation is a schedule fact); the D4 cause (unchanged
from P32).

## 5. Contradictions found

1. **A11's null gloss vs the receipted incumbent** (document vs bytes): the TS3-derived text
   calls rho = 1 "incumbent-equivalent undifferentiated pooling"; the receipt shows a tiered
   switch (2762/183/37 source counts). Not repaired in any frozen document; corrected in THIS
   draft's record with the receipt cited. This is the D1 resolution, not a new halt: it
   changes a null's description, not any control's construction.
2. **R11's preregistered-contrast audit vs the receipted design offset** (document vs
   document): `PREREGISTERED_CONTRASTS.json` audits the contrast against the natural-scale
   offset `projected_team_off_possessions` and against six season blocks, while the fitted
   design's offset is `log_exposure` and the folds are the five D006 folds. Handled
   prospectively, not repaired: the draft requires P25 invocation with `offset = log_exposure`
   AND `incumbent_projection = projected_team_off_possessions` (R11's own t09 shows the latter
   argument is load-bearing under a log offset), and this node re-measured the contrast's
   rank/condition/orthogonality on the actual five folds (clean everywhere).
3. **"cap 4-or-merged" ambiguity** in the D021 A23 note (document ambiguity): resolved to the
   source-frozen cap 4, stated openly in the arm record (section 2.7).
4. **TS4's "K small" vs edict 5's "small is not a specification"** (document vs document):
   resolved by enumerating {20, 80} with the defense written into the arm record.

## 6. Stop conditions

None tripped. Assessed explicitly against all six: primary target unchanged; K0 structure
unchanged (per-arm map carried and completed); inference structure unchanged -- the link
resolution FILLS the named gap by the exact procedure D021 prescribed (receipted convention,
implementation governs), and folds/clustering/resampling/weights/estimand are untouched;
candidate universe re-derived byte-consistent (2,982/1,491); cutoff-valid feature set
unchanged (A02's treatment maps onto the already-adjudicated pace_gap; no new field enters);
leakage status unchanged (every realized-column construction remains strictly-lagged under the
P22 discipline; the prohibited same-game surrogates appear in no prediction path).

## 7. What P34 should attack first (declared, not hidden)

The judgment calls this node made, all inside its mandate but each a legitimate red-team
target: the estimation-objective freeze (quasi-Poisson IRLS -- link is receipted, family is
this draft's choice); the enumeration choices for A08/A09/A10/A11 where sources froze nothing
(each defended in its record, none source-frozen); the provenance rule plus dual-Holm
construction for D2/D5; the A23 "4-or-merged" resolution; and the A14 promotion-ineligibility
structure (it spends a family element on an arm that cannot promote -- deliberate, so the
denominator is not quietly shrunk).
