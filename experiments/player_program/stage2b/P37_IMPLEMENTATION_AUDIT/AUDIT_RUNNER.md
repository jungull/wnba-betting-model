# P37 IMPLEMENTATION AUDIT — RUNNER SLICE (`AUDIT_RUNNER.md`)

IMPLEMENTATION AUDIT. Establishes that the code is the preregistered code. Establishes nothing about results, which remain sealed.

**Auditor slice:** the P36 shared RUNNER (`stage2b/P36_IMPLEMENT_ARMS/runner/`), the guard
harness, the four RAISED ambiguities (K0_FLAT reading, P27 fold-policy, bootstrap p-value
operationalisation, P26 R8 call-site adjudication), the receipts/seed machinery, and blinding.

**Independence:** this auditor implemented no part of P36 (runner or arms) and wrote nothing
outside `stage2b/P37_IMPLEMENTATION_AUDIT/`. No file under `SEALED_RESULTS` was read; no
comparative historical performance of any challenger was inspected; the arm test suite re-run
was executed with all artifact writes redirected to a session scratchpad so no P36 byte was
touched. The `P38_UNSEALED` flag was absent from the environment throughout.

---

## 1. Frozen inputs verified before reliance

All hashes measured by `Get-FileHash -Algorithm SHA256` in the worktree root.

| artifact | measured sha256 | expected (source) | match |
|---|---|---|---|
| `stage2b/P35_FREEZE_TASK_CARDS/SPEC.json` | `68EF22F4...385D4B32` | dispatch pin | YES |
| `stage2b/P33_PREREGISTRATION_DRAFT/SPEC.json` | `066B2A04...D347D093` | P35 carry_convention pin | YES |
| `P22 postgame_surrogate_guard.py` | `951E8513...B73CEEDA` | P33 guards_at_call_site AND `runner_constants.GUARD_SHA256_PINS` | YES |
| `P23 merge_guard.py` | `B0E75419...63CA3B7A8` | `runner_constants` (measured-at-P36 pin) | YES |
| `P25 offset_dependency_guard.py` | `C78E70B6...CC100E95` | P33 inputs AND `runner_constants` | YES |
| `P26 validate_k0_matched.py` | `1FC798DA...557D7E16` | `runner_constants` (measured-at-P36 pin) | YES |
| `P27 fold_estimability_guard.py` | `1FBEC0D6...DDB25D2F` | `runner_constants` (measured-at-P36 pin) | YES |
| `data/reference/team_cities.csv` | `10A544FD...128AC42D` | P35 franchise_continuity_receipt_pin | YES |
| `projected_exposure_v1/team_possession_prior_v1.parquet` | `C37C0751...87C3DB18` | `runner_constants.REAL_ARTIFACT_SHA256` | YES |
| `possessions_v2/possessions_raw_v2.parquet` | `7200881F...B15A4B1A` | `runner_constants.REAL_ARTIFACT_SHA256` AND P35 A19 basis | YES |

The two blinding artifact pins therefore point at the real frozen input bytes, and every guard
byte-pin in `runner_constants.py` matches the frozen guard actually on disk. `GUARD_SHA256_PINS`
for P22/P25 equal the P33-frozen values verbatim; P23/P26/P27 pins are declared as
measured-at-implementation values (drift detectors), which is what they are.

## 2. Line-by-line code/formula identity vs the frozen preregistration

Each runner module was read in full and compared clause-by-clause against P33
(`inference_spec_gap_resolution`, `inference`, `seed_manifest_plan`, `universe`) as carried by
P35 (`carry_convention`, `shared_frozen_amendments`).

* **`quasipoisson_irls.py`** — Poisson quasi-likelihood IRLS, log link, additive offset,
  tol 1e-10 on absolute Poisson-deviance change, max 100 iterations, deterministic, no seed
  parameter, identical machinery for arm and null. Matches
  `estimation_objective_frozen_here` exactly. The fitter has **no intercept option** (design
  fitted as supplied), satisfying `no_implementation_default_intercept_invariant` at the
  estimator level. Zero-parameter designs are not fitted at all (`eta = offset` exactly), which
  makes the `[log_exposure]` nulls of A02/A03/A05/A16/A25 literally the incumbent per the P35
  intercept table. Non-convergence (`iteration_cap`), singularity and non-finite divergence
  (eta > 700) all return `converged=False` — fail-closed, never clipped. Working weights
  `w = mu`, working response `z = (eta-offset) + (y-mu)/mu`: the canonical quasi-Poisson IRLS;
  the dispersion constant appears nowhere, matching the P35 retirement disposal ("constant
  dispersion cancels from the quasi-score"). Independent check: fitted slope satisfies the
  quasi-score equation `sum(x*(y-mu)) = -1.37e-11` at beta-hat (script `indep_checks.py`,
  section 5 below).
* **`runner_constants.py`** — every numeric pin equals its frozen source: IRLS 1e-10/100;
  B_test 10,000; B_train 2,000; interval 0.95; master seed 20260806; derivation string
  reproduced verbatim from P33 `seed_manifest_plan.derivation`; offset/incumbent/target column
  names; SUBSTANTIVE / NOT_APPLICABLE pins (P35 `p25_guard_invocation_pins`); intercept table
  {A07,A12,A13,A14,A15} with / 18 arms without, byte-equal to P35 `intercept_structure`;
  P35 SPEC sha pin correct (re-verified on disk by test T14 and by this auditor).
* **`seed_manifest.py`** — `derive_seed` implements exactly
  `first 4 bytes of sha256(utf8('{master_seed}|{fold_id}|{purpose}|{b}')) big-endian`.
  Recomputed independently (no P36 import): seeds 3279392468 / 1499380193 / 1709903536 for the
  three probe tuples equal both the module's values and the values in P36's `TEST_RECEIPT.json`.
  One RNG per (purpose, fold, b) makes pairing a property of the derivation, not caller
  discipline — matches "one stream per fold, SHARED by every arm and every null".
* **`cluster_bootstrap.py`** — TEST stream: resample n_clusters cluster slots with replacement,
  concatenate ALL rows of each sampled cluster (games never split; verified structurally in
  T04: every sampled game contributes an even row count). Deterministic sorted-unique cluster
  ordering. Paired deltas `MAE(null)-MAE(arm)` on the SAME draw index set. TRAIN stream:
  refit BOTH members per draw; K7 symmetric NA rule implemented exactly as
  `estimator_symmetry_rules.bootstrap_draw_rule`: (a) any declared indicator column constant on
  the resampled rows of EITHER member, or (b) either member's refit non-convergent (including
  singular/non-finite) ⇒ NA for BOTH, excluded from BOTH intervals, counts reported by reason.
  Percentile 95% intervals. Verified in T05 including the analytic NA-rate check
  ((1-1/12)^12 ≈ 0.352 vs measured 107/300).
* **`blinding.py`** — structural refusal on any of: row count ∈ {2982, 2990}; cluster count ∈
  {1491, 1495}; any D006 fold id; any input artifact hashing to a frozen real-artifact sha256.
  Refusal raises before any guard or fit. Unseal branch keyed on `P38_UNSEALED`; the test suite
  asserts the flag is absent from `os.environ` and exercises the branch only via an injected
  mapping. Verified in T06 and end-to-end in T13 (runner refuses a real fold id).
* **`guard_harness.py`** — call-site wrappers only; no shared gate edited (all five guard files
  hash to their pins, section 1). P26 runs at fit initialisation BEFORE P25 (P35
  `p26_k0_contract_enforcement.call_site`; runner.py step 4 vs step 5). P25 invoked with
  `offset = log_exposure`, `incumbent_projection = projected_team_off_possessions`,
  `declared_family = "SUBSTANTIVE"`, `recalibration_declaration = None` — checked against the
  frozen `audit_augmented_design` signature (a dict-or-None parameter; None is the correct
  encoding of NOT_APPLICABLE for a SUBSTANTIVE arm), on each fold's TRAINING rows. P22 runs on
  the complete design with a required prohibited basis; a missing LagSpec is a failure, never a
  pass (negative-path tested, T09). P23 wrapper enforces the franchise-continuity receipt and
  the team_cities pin, fail-closed both ways (T09). Every wrapper raises
  `GuardHarnessFailure` carrying the guard's own record.
* **`receipts.py`** — I13 conventions (I13 `repro_run_manifest/2` exists and carries the same
  elements): per-source sha256 of the full runner closure (10 files), input-artifact hashes,
  environment versions, full seed manifest (master seed, derivation string, first seeds and a
  sha256 digest over each fold's complete seed stream), canonical manifest digest over the
  record minus the timestamp. Git honestly recorded as not-invoked for P36 (standing rule 4)
  with `run_git=True` reserved for P38. Verified in T12 (digest recomputes; input hash exact).
* **`runner.py` / `runner_interface.py`** — order of operations matches RUNNER_INTERFACE.md §4:
  blinding → byte pins → module conformance → P26 → per-fold (bundle validation → P22 → P25) →
  P27 → point fits → paired test bootstrap → train refit bootstrap → K0_FLAT → receipt.
  Intercept invariant enforced twice (module-level against the frozen table; bundle-level:
  explicit all-ones column present iff pinned, in arm AND null identically, constant
  non-intercept columns refused as silent intercepts, intercept barred from `indicator_cols`).
  Column-name drift across folds refused. Point-fit non-convergence of either member ⇒
  arm/fold UNEVALUABLE symmetrically (K7 point rule). Structural deactivation hook honoured
  (deactivated folds enter neither fits nor the seed manifest). Pooled delta_MAE combines each
  evaluable fold's OWN seeded draw b at equal per-row weight — the correct stratified pooling
  under `inference.resampling`; pooled point estimate is the row-weighted MAE difference over
  concatenated evaluable-fold test rows. Row parity within the runner is structural: arm, null
  and K0_FLAT consume the same materialised frame, the same y/offset/cluster arrays and the
  same fold index sets; cross-arm parity is a property of the seed derivation (same (fold, b)
  ⇒ same clusters) plus P38 handing every arm the same universe — the runner side of that
  contract is correct.

## 3. Test suites run by this auditor

* **Re-run of the full P36 runner suite** (14 tests) via a scratchpad driver that imports
  `TESTS.py` and repoints its artifact directory outside the P36 tree
  (`audit_run_tests.py`; command:
  `python <scratchpad>\audit_run_tests.py`): **14/14 PASS**.
* **Bit-reproducibility across sessions:** the T13 end-to-end canonical results digest from my
  run, `ad9485a035891c6a12f61d0427ff881eb8f4b74824ab35c5e71da54a847504f0`, is byte-identical to
  the digest recorded in P36's `TEST_RECEIPT.json`. Every `measured` block of all 14 tests is
  identical between P36's receipt and my re-run except wall-clock seconds.
* **Independent checks not taken from P36 code** (`indep_checks.py`):
  seed derivation recomputed from the P33 prose alone (3 probes, all equal);
  two-sided p-value hand cases (7+/3− of B=10 → 8/11 = 0.7273; all-positive B=10 → 2/11;
  all-zero → capped at 1.0 — all reproduced);
  IRLS quasi-score identity at beta-hat (−1.37e-11; statsmodels unavailable in this
  environment, so the score equation was used as the independent reference).

## 4. Rulings on the four RAISED ambiguities

### 4.1 K0_FLAT reading — **SOUND** (naming adjudicated: offset-carrying reading is the receipted one)

The frozen prose pins only "(intercept-only) DIAGNOSTIC ONLY" (P33 `inference.k0_flat`).
Measured lineage: `comparison_gate.py` lines 7–10 define K0 as "an intercept-only, feature-free
control (K0) built from the challenger's own pipeline" with K0 MAE 2.96419
(also `comparison_gate.py:307`, `test_comparison_gate.py:7/50/880`), and the challenger
pipelines carry the receipted log-exposure offset program-wide. The offset-carrying reading
(`k0_flat_offset_intercept`) is therefore the receipted K0 lineage; a no-offset flat mu appears
nowhere in that lineage. `k0_flat.py` computes BOTH readings, labels them distinctly, stamps
every record `role = "diagnostic_only"`, and neither enters any promotion decision (verified in
code and in T11/T13). Since the control is diagnostic-only, carrying both readings changes no
inference. **Adjudication for the record:** `k0_flat_offset_intercept` IS "K0_FLAT" wherever
frozen prose says K0_FLAT; `k0_flat_pure_intercept` is an auxiliary diagnostic and may never be
cited as "K0_FLAT" without its qualifier. No code change required. (Note: the claim "2.96419 is
only reachable with the offset carried" was verified as documentary lineage, not re-measured —
re-measuring it would require touching real-fold data, which this audit is barred from.)

### 4.2 P27 fold-policy (SEASON_BLOCK vs EXPANDING_PRIOR_SEASONS) — **NEEDS-P38-EXECUTOR-DECISION**

The ambiguity is real and belongs to the frozen guard itself, not to P36:
`fold_estimability_guard.py:121–146` documents both readings and requires the caller to name
one; the receipt records the choice. P36 correctly refused to resolve it silently: the harness
exposes `fold_policy` as a named parameter (default `SEASON_BLOCK`), the choice lands in the
guard's own receipt, and both policies are exercised in T09. Facts the executor's naming
decision should weigh, both measured this audit:
(i) the S7 finding was stated under SEASON_BLOCK — "a tier indicator is IDENTICALLY ZERO in
four of six chronological folds" (`stage2a/V2_STOP_CONDITION.json` line 134; six per-season
blocks exist, not six D006 folds);
(ii) the D006 operative folds of the preregistration are literally the
EXPANDING_PRIOR_SEASONS masks — `make_outer_training_folds(..., "EXPANDING_PRIOR_SEASONS")`
emits fold ids `train_lt_<s>`, exactly the five frozen D006 fold ids, and the task cards'
numeric active-set triggers (">= 10 training clusters ...") are stated over D006 training
folds. The executor must name the policy on the record before any real fit; whichever is named,
the receipt already captures it. Not resolvable by this auditor: the two readings' verdicts can
differ only on real-fold support patterns, which are blinded from this audit by design.
See also finding **F1** below, which interacts with this item.

### 4.3 Bootstrap p-value operationalisation — **SOUND**

P33 pins "two-sided cluster-bootstrap p-value" with no formula; the runner's
`p = min(1, 2*min((1+#{d<=0})/(B+1), (1+#{d>=0})/(B+1)))` (`cluster_bootstrap.py:70–76`,
recorded in RUNNER_INTERFACE.md §4 step 7) is the standard add-one two-sided resampling
p-value: deterministic given the frozen seeds, never exactly zero, ties counted in both tails
(conservative), capped at 1. Hand-computed cases reproduce exactly (section 3). It was recorded
in the frozen interface document while every agent was blinded, i.e. it is a completion of an
unpinned specification made before any result existed — the epistemically acceptable direction.
**Condition attached to this ruling:** the formula is now part of the audited implementation;
any change at or after P38 unsealing is a preregistration deviation and voids the affected
comparisons. P38 must consume it byte-unchanged.

### 4.4 P26 R8 call-site adjudication — **SOUND** (one wording discrepancy, C, no behavioural effect)

Verified against the frozen validator bytes (`validate_k0_matched.py`, R8 branch lines
264–285): for `calibration_only` records the frozen branch necessarily fires on the frozen
cards (they pin empty `lower_order_structural_terms` and declare no slope-role parameter), so a
call-site adjudication is required to run A02/A03/A05 at all — exactly what P35
`r8_scope_adjudication` mandates. `guard_harness.p26_check` filters ONLY the three R8-shaped
finding kinds, each keyed to its R8 signature: `tested_parameter_missing` with
`missing_role == "slope"` (emitted only at validator line 273); `null_value_not_null` with
`expected == 1.0` (sole emission site line 276, calibration slope rule); and
`lower_order_term_missing_from_k0` carrying `arm_kind == "calibration_only"` only when the
record itself pins an empty lower-order set (the R6 interaction-closure emission at line 251
carries no `arm_kind` key and is therefore never filtered). Every other finding kind, and every
R8-shaped finding on a record that does NOT pin the empty set, passes through blocking. The
extended rule is then enforced (tested parameters present with null_value 0), raw findings AND
adjudicated disposition are both recorded with the P35 basis string, and the shared validator
bytes are untouched (hash match, section 1). Negative paths verified in T08: a null retaining
the treatment still blocks; a calibration record with no tested parameter still blocks.
**Discrepancy (finding F2, severity C):** the P36 SPEC.json describes the extended rule as
">= 1 tested parameter with null_value 0" while the code requires **all** declared tested
parameters to have null_value 0 (`all(...)` over a non-empty list, guard_harness.py:145–146).
The code is strictly stronger. Every frozen calibration card declares exactly one tested
parameter with null_value 0, so the two readings are indistinguishable on the frozen cards;
recorded so nobody later cites the SPEC wording as the implemented rule.

## 5. Findings

**F1 (Severity B) — runner escalates any P27 per-fold UNEVALUABLE verdict to whole-arm
refusal, contradicting its own interface document and the cards' fold-level semantics.**
`fold_estimability_guard.guard` sets `overall = "FAIL"` whenever ANY internal fold is
UNEVALUABLE (guard lines 695–702), and `guard_harness.p27_check` raises on `overall == "FAIL"`
(guard_harness.py:258–259), which aborts the entire arm in `runner.run_arm`. But
RUNNER_INTERFACE.md §4 step 5 promises "`FAIL` ⇒ affected folds unevaluable per the guard's own
verdicts; runner honours them symmetrically for arm and null", and multiple frozen cards pin
fold-LOCAL prospective unevaluability (A15: "S7 failure -> arm/fold prospectively unevaluable,
accepted in advance"; A07: "arm/fold UNEVALUABLE on failure; retirement if unevaluable in >= 2
folds"). The runner has no mechanism to mark an individual fold unevaluable on a P27 verdict
and continue with the remaining folds. Direction: fail-closed (can only wrongly kill an arm,
never wrongly promote one), and P35-measured support suggests no current arm trips it — but if
any fold does trip at P38, the executed semantics will contradict the frozen cards, and A07's
">= 2 folds" retirement rule is unimplementable as-is. This is a document-vs-code
contradiction inside the audited unit. Remedy belongs at the call site (a wrapper honouring
per-fold verdicts), decided by P38's executor on the record — NOT by editing the frozen guard.
Interacts with 4.2: the named fold policy determines which internal folds P27 audits.

**F2 (Severity C)** — R8 extended-rule wording discrepancy (all-vs-">=1"); see 4.4. No effect
on any frozen card.

**F3 (Severity C) — K7 clause (a) trusts the module's `indicator_cols` declaration.** The
bootstrap-draw constancy test conditions only on columns the arm module declares as
indicators; an under-declared indicator column would skip clause (a). Mitigation measured in
code: a constant-zero column makes the normal equations singular ⇒ NA via clause (b); the
residual exposure is a constant-one draw in a no-intercept design, which is estimable rather
than degenerate. `validate_design_bundle` refuses undeclared indicators only in the other
direction (declared-but-absent). Acceptable, recorded so arm audits check indicator
declarations against the cards.

**F4 (Severity C) — card-vs-module consistency of `p26_k0_record` is not machine-enforced at
the runner.** P35 pins P26 validation "against the p26_k0_record frozen in each task card";
the runner validates the record the arm MODULE supplies. Whether each module's record equals
its frozen card is an arm-level identity question (the per-arm audit slices own it). Likewise
`p26_check(bind=True)` — the delegation into the frozen `comparison_gate.require_matched_k0` —
is not exercised by `run_arm`; P38 must invoke the bind path at scoring time.

**F5 (Severity C) — blinding is structural, not adversarial.** A real-data subset with renamed
fold ids and no artifact paths supplied would not trip any signature. The P36 mandate asked for
structural refusal against the real folds/universe, which this satisfies; recorded so nobody
mistakes it for a cryptographic seal. The two artifact pins do hash to the true frozen input
bytes (section 1), so any honest path through `input_paths` is caught.

**Contradictions between documents found:** exactly one inside this slice — F1
(RUNNER_INTERFACE.md §4 step 5 vs `runner.py`/`guard_harness.p27_check` behaviour). No
document-vs-bytes hash contradiction was found anywhere in the slice.

## 6. What this audit could NOT establish, and why

* Anything about real-fold behaviour: fits, MAEs, evaluability of specific folds, or which P27
  fold-policy verdicts differ on the real universe — blinded by design (standing rule 8, no
  result access); everything above rests on synthetic/identity/schema evidence.
* The pure-intercept K0_FLAT variant's MAE claim (4.1) — documentary lineage only; verifying it
  numerically requires real-fold data.
* Holm/family machinery, dual-family compositions, both-pass re-tests — not in the runner unit
  (correctly so: they are cross-arm P38 orchestration); no code for them was audited here.
* Per-arm identity of formulas, columns and `p26_k0_record`s against the frozen cards — the
  other auditors' slices.

## 7. Stop conditions

None tripped in this slice. Nothing found would change the primary target, the K0 structure,
the inference structure, the candidate universe, the cutoff-valid feature set or the leakage
status. F1 does not change the inference structure — it is a fail-closed implementation
divergence whose remedy is a call-site wrapper decision at P38; it is raised here plainly
rather than fixed, per the audit mandate (never fix — report).

## 8. Verdict for this slice

* Code/formula identity of the shared runner vs the frozen preregistration: **VERIFIED**, with
  the single B-severity divergence F1 (fail-closed direction) and four C-severity notes.
* Runner test suite: **14/14 PASS re-run by this auditor**, bit-identical results digest to the
  P36 receipt.
* Guard harness: call-site-only, byte-pinned, fail-closed on every negative path tested.
* Seeds/receipts: derivation independently reproduced; manifests pin every seed stream by
  digest; receipts carry code, inputs, environment, guards, seeds and results under a canonical
  digest.
* Blinding: structural refusal verified positive and negative; unseal flag absent throughout.
* RAISED items: K0_FLAT **sound** (offset-carrying reading adjudicated as the receipted
  default); P27 fold-policy **needs-P38-executor-decision** (with the two measured facts the
  decision must weigh, and F1 to resolve alongside it); bootstrap p-value **sound**
  (byte-unchanged carriage into P38 is a condition); P26 R8 adjudication **sound** (one
  C-severity wording note).
