# P36 SHARED RUNNER — FROZEN ARM-MODULE INTERFACE (`p36_shared_runner/1`)

**Status:** frozen contract for every P36 arm module. Implemented by `runner.py` and enforced by
`runner_interface.validate_arm_module`. Every pinned number, name and hash the runner enforces
lives in `runner_constants.py`; nothing in this document introduces a value not carried from a
frozen source (P35_FREEZE_TASK_CARDS/SPEC.json sha256
`68ef22f4fca15a2e8d91eeeb9b84b86f86e8e9e7caab5e23e6a9b950385b4d32`, which carries the P33 shared
blocks by hash reference, sha256 `066b2a046021db119a75e2c847c325f6f4e40bb6e418bc7b31c8d072d347d093`).

Epistemic status of everything under `runner/`: **IMPLEMENTATION. Blinded: no agent may inspect
challenger performance. Unit, synthetic, identity and schema tests only.**

---

## 1. One module = one arm × one enumeration element

Every enumerated grid element is fitted end-to-end as its own variant (P35
`multiplicity_recomputed.grid_element_regime_pinned`). Therefore **one arm-module instance binds
exactly one enumeration element**. Multi-element arms (A08 K∈{20,80}, A09 κ∈{2,10,50}, A10
λ∈{0.2,0.5}, A11 ρ∈{0.25,0.5,0.75}, A23 two bundles) provide one module instance per element;
the runner never selects among elements — there is no training-time selection of
kappa/lambda/rho/K/bundle anywhere.

## 2. Required hooks

An arm module is any object exposing ALL of the following. `validate_arm_module` fails closed on
any missing or malformed hook.

| hook | type | contract |
|---|---|---|
| `arm_id` | `str` attr | the P35 task-card `arm_id`, e.g. `"A08_league_lag_level"` |
| `card_id()` | `-> str` | the frozen task-card identifier (normally `== arm_id`) |
| `declared_family()` | `-> str` | MUST return `"SUBSTANTIVE"` (P35 `p25_guard_invocation_pins`); the runner refuses any other value |
| `recalibration_declaration()` | `-> str` | MUST return `"NOT_APPLICABLE"` (no RECALIBRATION arm survives this cycle) |
| `enumeration_element()` | `-> dict` | the frozen grid element this instance binds (e.g. `{"K": 20}`); `{}` for single-element arms |
| `element_id()` | `-> str` | deterministic label, e.g. `"A08_K20"`; used in receipts and output keys |
| `uses_global_intercept()` | `-> bool` | must agree with the frozen P35 intercept table (`runner_constants.ARMS_WITH_FREE_GLOBAL_INTERCEPT` / `ARMS_WITHOUT_GLOBAL_INTERCEPT`); checked, not trusted |
| `build_design(fold, universe)` | `-> dict` | see §3 |
| `p26_k0_record()` | `-> dict` | the FULL `k0_matched/1` record for this arm, consistent with the card's `p26_k0_record`; validated by the P26 wrapper (§5) at fit initialisation, BEFORE P25 |
| `lag_specs()` | `-> dict[str, dict]` | per design column, kwargs for `postgame_surrogate_guard.LagSpec` (P22). Absence of a column's spec is a P22 failure, never a pass |
| `lag_sources()` | `-> dict[str, DataFrame]` | source frames for `PRIOR_GAME` re-derivation; `{}` if none |
| `preregistered_contrasts()` | `-> list[dict] \| None` | P25 preregistration records for any contrast column (A02 must return the registered `contrast_own_minus_opp_pace_estimate` record) |
| `prereg_digest_expected()` | `-> str \| None` | expected digest of the contrast preregistration |
| `requires_franchise_continuity()` | `-> bool` | per the card (P33 `p23_franchise_continuity_precondition` arms) |
| `p23_receipts()` | `-> list[dict]` | merge-guard receipts for cross-season history features; must be non-empty when `requires_franchise_continuity()`; each receipt must pin `team_cities.csv` at the frozen sha256 or the runner fails the arm closed |
| `p27_rule()` | `-> tuple(dict, dict) \| None` | `(ActiveSetRule kwargs, Preregistration kwargs)` when the card registers an S7 active-set rule; `None` otherwise |

### 2a. Optional hook

| hook | type | contract |
|---|---|---|
| `structurally_deactivated_folds()` | `-> list[str]` | folds the card structurally deactivates for arm AND null identically (A11: `train_lt_2022`, per `a11_repair.fold1_evaluability_pinned`). A deactivated fold enters neither the pooled delta_MAE nor any kill's evaluable-fold set. Missing hook = no deactivation. |

## 3. `build_design(fold, universe) -> dict`

`fold` is `{"fold_id": str, "train_idx": int ndarray, "test_idx": int ndarray}` (positional row
indices into `universe`); the pseudo-fold `{"fold_id": "FINAL_ASSEMBLED_DESIGN", "train_idx": all
rows, "test_idx": empty}` is also passed once. `universe` is the immutable input frame; the module
must NEVER mutate it.

Return value keys (all required):

* `treatment_cols: list[str]` — exactly the card's treatment terms, as materialised columns.
* `nuisance_cols: list[str]` — the card's nuisance terms. If the arm carries a free global
  intercept (P35 intercept table) it appears HERE, as the explicit all-ones column named
  `"intercept"`, and nowhere else. **No implementation-default intercept exists anywhere in the
  runner: the IRLS fitter has no intercept option at all** — a design has an intercept if and
  only if a column of ones named `intercept` is declared, identically in arm and null
  (P35 `no_implementation_default_intercept_invariant`).
* `k0_matched_design: dict` — `{"treatment_cols": list[str], "nuisance_cols": list[str],
  "comparison": "term_removal" | "parameter_fixed_at_null"}`. For `term_removal` nulls
  `treatment_cols` is `[]` and `nuisance_cols` equals the arm's nuisance set. For
  `parameter_fixed_at_null` (A11) the null's own free column(s) (e.g. `dblend_t(1)`) appear in
  `treatment_cols` of the null design with the comparison label carrying the frozen semantics.
* `indicator_cols: list[str]` — the subset of treatment+nuisance columns that are 0/1 indicator
  columns, in BOTH members' designs. This is the column set the K7 bootstrap-draw rule (a)
  conditions on (`estimator_symmetry_rules.bootstrap_draw_rule`). The explicit `intercept`
  column is structural, not an indicator, and must not be listed.
* `columns: dict[str, ndarray]` — the constructed feature columns, aligned to `universe`'s full
  row order (length = len(universe)). Training-fold-computed constants (e.g. A13's `cbar_F`, A17's
  imputation means) are computed from `fold["train_idx"]` rows ONLY, once per fold, and are held
  fixed across bootstrap refits — the runner re-uses these materialised columns for every draw
  and never calls `build_design` inside the bootstrap.

The column NAME sets must be identical across folds (values may differ fold-to-fold through
training-only constants). The runner checks this and fails closed on drift.

## 4. What the runner does with it (frozen execution semantics)

Order of operations per arm module (single entry point `runner.run_arm`):

1. **Blinding** (`blinding.assert_not_real`): the runner REFUSES to run unless the data is
   structurally non-real OR the environment carries the explicit `P38_UNSEALED` flag. Real-fold
   signatures (any one trips refusal): row count ∈ {2982, 2990}; cluster count ∈ {1491, 1495};
   any fold_id in the frozen D006 list; any supplied input artifact hashing to a frozen real
   artifact sha256. Fail-closed: refusal raises before any guard or fit runs.
2. **Guard byte pins** (`guard_harness.verify_guard_pins`): P22/P23/P25/P26/P27 module bytes and
   `data/reference/team_cities.csv` are re-hashed and compared to `runner_constants.
   GUARD_SHA256_PINS` / `TEAM_CITIES_SHA256_PIN`. Mismatch fails the run closed.
3. **P26 wrapper** (`guard_harness.p26_check`): `validate_k0_matched.validate` on the module's
   full record, at fit initialisation, BEFORE the P25 invocation (P35
   `p26_k0_contract_enforcement.call_site`). The R8 slope rule is applied under the P35
   `r8_scope_adjudication`: for `calibration_only` arms the validator's slope-specific findings
   (`tested_parameter_missing[missing_role=slope]`, slope `null_value_not_null`, and the R8-shaped
   `lower_order_term_missing_from_k0` when the frozen card pins an EMPTY lower-order set and no
   global intercept) are re-adjudicated to the extended rule: the record must declare ≥1 tested
   parameter with `null_value == 0` (term absent = incumbent). Raw validator findings AND the
   adjudicated disposition are both recorded in the receipt; the shared gate is never edited.
4. **Per fold** (each real fold, then `FINAL_ASSEMBLED_DESIGN`):
   a. materialise the design (§3); verify the intercept invariant (intercept column present iff
      pinned, all-ones, identical in arm and null; no other constant column silently acting as one);
   b. **P22** `postgame_surrogate_guard.audit` on the fold's frame with the module's lag specs and
      the caller-supplied prohibited basis (built by `realised_duration_basis` at P38 time;
      synthetic basis in tests). Blocking finding ⇒ arm/fold fails closed;
   c. **P25** `offset_dependency_guard.audit_augmented_design` on the fold's TRAINING rows with
      `offset = log_exposure` column values, `incumbent_projection = projected_team_off_possessions`
      column values, `declared_family = "SUBSTANTIVE"`, and the module's preregistered contrasts.
      Blocking ⇒ fail closed (P25 rejection is withdrawal/design failure, before any performance
      number).
5. **P27** `fold_estimability_guard.guard` once on the final assembled frame (it audits every
   season-block training fold internally, plus the final design), with the module's registered
   active-set rule when the card carries one. `FAIL` ⇒ affected folds unevaluable per the guard's
   own verdicts; runner honours them symmetrically for arm and null.
6. **Point fits** (`quasipoisson_irls.fit`): quasi-Poisson IRLS, log link, offset =
   `log_exposure`, tol 1e-10 on Poisson-deviance change, max 100 iterations, deterministic, no
   stochastic component, identical machinery for arm and null. IRLS hitting the cap in a POINT
   fit of either member ⇒ that arm/fold is UNEVALUABLE, symmetrically, recorded (K7).
7. **Paired test bootstrap**: B = 10,000 game-cluster draws per fold over the fold's TEST
   clusters, both team-rows of a sampled game always carried together. Draw `b` uses seed
   `seed("test_bootstrap", fold_id, b)` (§6) and is therefore the SAME resampled cluster index
   set for the arm, its null, and every other arm evaluated in that fold. Pooled delta_MAE
   combines the per-fold draws at equal per-row weight over the arm's evaluable folds.
   Two-sided p-value operationalisation (recorded, deterministic):
   `p = min(1, 2*min( (1+#{delta_b <= 0})/(B+1), (1+#{delta_b >= 0})/(B+1) ))`.
8. **Training-cluster refit bootstrap**: B = 2,000 draws per fold over TRAINING clusters, seed
   `seed("train_refit", fold_id, b)`, refit of BOTH members per draw, percentile 95% intervals
   per coefficient. **K7 symmetric NA rule**, exactly as the cards pin it: a draw in which (a)
   any declared treatment/nuisance INDICATOR column of either member's design is constant on the
   resampled rows, or (b) either member's IRLS refit fails to converge within 100 iterations
   (or is numerically singular/non-finite), is recorded NA for BOTH members; NA draws are
   excluded from both interval constructions and their count is reported per arm/fold.
9. **K0_FLAT diagnostic** (`k0_flat.py`): fitted per fold with the identical pipeline, zero
   features. DIAGNOSTIC ONLY — it enters no promotion decision and the receipt labels it
   `diagnostic_only`. See §7 for the definitional note.
10. **Receipt** (`receipts.py`, schema `p36_runner_receipt/1`, I13 conventions): code state
    (commit when git is available at execution time — never invoked by P36 tests), source-file
    hashes, input-artifact hashes, guard receipts (bytes pins + every guard record), the full
    seed manifest (master seed, derivation string, per-fold seed digests), environment versions,
    per-fold results, and a canonical manifest digest.

## 5. Frozen numeric pins the runner enforces (see `runner_constants.py` for provenance)

* IRLS: tol `1e-10` (absolute deviance change), max 100 iterations, log link, offset
  `log_exposure`.
* Bootstrap: B_test = 10,000; B_train_refit = 2,000; coefficient interval = percentile 95%.
* Seeds: master 20260806; `seed(purpose, fold_id, b) = first 4 bytes of
  sha256(utf8('{master_seed}|{fold_id}|{purpose}|{b}')) as big-endian unsigned int`; purposes
  `test_bootstrap`, `train_refit`. IRLS is deterministic; no fit-time seed exists; any
  stochastic fitting step violates the preregistration.
* Row weights: equal per team-game row. Games are never split across folds or draws.
* Any per-arm response-family or estimation-objective deviation VOIDS the arm
  (`response_family_deviation_clause`); the runner exposes no such option.

## 6. Blinding contract

The refusal predicate lives in `blinding.py` and is tested with the `P38_UNSEALED` flag ABSENT
from the process environment (the unseal branch is exercised only via an explicit injected
mapping, never by setting the real environment variable). P38 is the only context in which the
flag may exist.

## 7. K0_FLAT — definitional note (flagged for P37)

P33/P35 define K0_FLAT only as "(intercept-only) DIAGNOSTIC ONLY". Two readings exist:

* **(i) offset-carrying intercept-only** — design `[intercept]` WITH the receipted
  `log_exposure` offset in the identical quasi-Poisson pipeline, zero features. This matches the
  program's receipted K0 lineage: `comparison_gate.py` line 7 ("intercept-only, feature-free
  control (K0) built from the challenger's own pipeline") and the discovery-wave K0
  ("intercept-only control arm, identical pipeline"), whose measured MAE (2.96419,
  `test_comparison_gate.py`) is only reachable with the offset carried.
* **(ii) pure intercept** — design `[intercept]` with NO offset; a literally flat μ.

`k0_flat.py` computes BOTH, labels (i) `k0_flat_offset_intercept` (default diagnostic, receipted
basis above) and (ii) `k0_flat_pure_intercept`, and marks the ambiguity in every receipt.
Because K0_FLAT is diagnostic-only and appears in no promotion decision, carrying both readings
changes no inference; the naming decision is raised to P37 rather than resolved silently.

## 8. Ownership and write scope

Everything under `experiments/player_program/stage2b/P36_IMPLEMENT_ARMS/runner/` is this unit's.
Arm modules live in their own worktrees/nodes and import this contract; they never edit it.
