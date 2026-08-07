# S36 shared runner — frozen element-module interface (`s36_shared_runner/1`)

**Epistemic status:** IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative
historical performance is revealed.

Frozen contract for every S36 element module. Implemented by `runner/runner.py`, enforced by
`runner/runner_interface.py`. Every pinned number, name and hash the runner enforces lives in
`runner/runner_constants.py`; nothing in this document introduces a value not carried from
`stage3_score/S35_FREEZE_TASK_CARDS/SPEC.json`, which carries the 17 element cards and 11 arm
blocks by hash out of `S33R_PREREGISTRATION_REPAIR/SPEC_V2.json`
(sha256 `6402fc11b9118ef6978ca4feb4aec10e3b811209773b7ae5f03ba29962a8e945`).

---

## 1. One module = one arm. One `ElementSpec` = one frozen element card.

Eleven modules under `arms/`, seventeen `ElementSpec`s among them. `runner.load_modules()`
refuses a module for a non-retained arm by name — **SC07 was withdrawn by measurement and must
never acquire an implementation.**

`ElementSpec` carries: `element_id`, `arm_id`, `estimand`, `primary_metric`, `arm_kind`,
`family_primary`, `card_sha256`, `build`, `kill_conditions`, `mandatory_receipts`,
`structurally_deactivated_folds`, `sign_pin`, `notes`. `tests/TESTS.py` checks every one of these
against the frozen freeze bytes and re-derives all seventeen `card_sha256` values from
`SPEC_V2.json`.

## 2. `build(universe, fold, cache) -> DesignPair`

A module does **not** hand back two independently built designs. It hands back **one column
dictionary plus two column-name lists**:

| field | meaning |
|---|---|
| `columns` | `name -> float ndarray`, length = `len(universe.games)`, aligned to game order |
| `arm_cols` | the arm's design columns, in order |
| `k0_cols` | the K0_MATCHED design columns, in order |
| `treatment_cols` | the card's treatment terms (⊆ `arm_cols`, absent from `k0_cols`) |
| `structural_cols` | null-granted structural terms, present **identically on both sides** |
| `indicator_cols` | 0/1 columns; the K7 bootstrap NA rule conditions on these |
| `comparison` | `term_removal` (16 cards) or `parameter_fixed_at_null` (SC08 alone) |
| `fold_constants` | train-only constants materialised for this fold, receipted verbatim |
| `deactivated` | a card-declared structural deactivation of the **term**, never of rows |

**Why one dictionary and not two designs.** Two separately constructed designs can drift in a
preprocessing step, a fallback, or a fold constant, and the drift is invisible until it shows up
as an unexplained delta. Two *views of one dictionary* cannot drift. `validate_design`
reconstructs the K0 from the arm and refuses the pair unless `arm_cols` minus `treatment_cols` is
**exactly** `k0_cols`, in order.

## 3. What `validate_design` refuses — each of these is a Severity A by name

* K0 ≠ arm-minus-treatment → *unmatched comparison flexibility*
* a treatment term surviving in the K0
* a null-granted structural term missing from either side
* a non-finite value in any column (imputation must be declared, never implicit)
* a column not aligned to the full game order
* a constant column acting as a **silent second intercept**; a design has an intercept iff a
  ones column *named* `intercept` is declared, identically on both sides
* an `indicator_cols` member that is not 0/1
* a `comparison` outside the two frozen null constructions
* an element with no treatment column and no declared structural deactivation

Column **name** sets must be identical across folds. Values may vary through train-only constants.
The one admissible exception is a card-declared deactivation, and then the fold's set must be a
strict **subset** of the active set.

## 4. Order of operations

1. **O2 first.** `universe.build_universe()` refuses to return a frame unless
   `PREBUILD_GAME_ID_DIGEST.json` exists *and* the built game_id set re-derives to the digest
   pinned there. No design matrix in this node can precede the pre-build receipt.
2. **Byte pins.** All four input artifacts re-hashed; `master_team.parquet` is additionally
   refused **by name** if it hashes to the known drifted data-worktree copy.
3. **Build** — authorised on the real universe (`blinding.assert_may_build`).
4. **Parity** — `validate_design` on every element × every fold.
5. **Fit** — `blinding.assert_may_fit`. **Refused on the real universe at S36.**
6. **Paired bootstrap** — B_test = 10,000 game-cluster draws; draw *b* depends only on
   `(master_seed, fold_id, purpose, b)`, so arm and null are paired *by derivation*.
7. **Train-refit bootstrap** — B = 2,000, percentile 95% intervals, **K7 symmetric NA rule**.
8. **Receipt** — code state, source hashes, input hashes, seed manifest, environment, per-fold
   records, C1 alpha disclosure, canonical manifest digest.

## 5. Frozen numeric pins

* Folds: five D006 expanding walk-forward folds, `train_lt_2022 … train_lt_2026`,
  train/test cluster counts 205/239, 444/260, 704/262, 966/310, 1276/215.
* Universe: 1,491 clusters / 2,982 rows; both counts always reported alongside the
  1,495 / 2,990 full-schedule reference.
* Inference: B_test 10,000; B_train_refit 2,000; percentile 95%; unit = game-clustered bootstrap.
* Seeds: master **20260807**; `seed(purpose, fold_id, b) = first 4 bytes of
  sha256(utf8('{master_seed}|{fold_id}|{purpose}|{b}'))` big-endian unsigned.
* Estimators: OLS; bernoulli-logit IRLS (tol 1e-10, max 100 iter); closed-form MoM; pinned-init
  Newton for SC08 dispersion (tol 1e-10). **All deterministic; no fit-time seed exists.**
* E3 probability clip `[0.001, 0.999]`, post-link, pre-metric, identical on both sides.
* Weights: unit, equal per game cluster. Games are never split across folds or draws.
* Two-sided p (cycle-1 operationalisation, carried):
  `p = min(1, 2*min((1+#{d<=0})/(B+1), (1+#{d>=0})/(B+1)))`.

## 6. Blinding

`blinding.assert_may_fit` refuses on row count ∈ {2982, 2990}, cluster count ∈ {1491, 1495}, any
D006 fold id, or any artifact hashing to a frozen real sha256 — unless `S38_UNSEALED` is present.
Tests exercise the unseal branch **only** via an injected mapping and assert the flag is absent
from `os.environ`.

`assert_may_build` is separate and permissive, because the freeze authorises building feature
matrices on the pinned universe while forbidding fitting. Keeping them as two functions is what
stops the distinction from blurring.

## 7. The obligations are mechanisms, not prose

| obligation | mechanism |
|---|---|
| ROOT_PATH_RULE / O1 | `prebuild` + `universe._verify_input_pins`, drifted copy refused by name |
| O2 pre-build digest | `prebuild/PREBUILD_GAME_ID_DIGEST.py`; `build_universe` halts without it |
| C1 alpha disclosure | `obligations.stamp_program_alpha` on every receipt |
| C2 SC06 power statement | `sc06.era_split_receipt` is the only emitter and self-checks |
| C3 SC11 label | `sc11.cross_estimand_receipt` is the only emitter and self-checks |
| O5 `R_SC08_FLOOR` | `sc08.r_sc08_floor_receipt`, takes no challenger argument |
| O6 `R-A1-EXCEPTIONS` | mandatory on every `ElementSpec`, checked in tests |
| O7 identity-set extension | column-grain classifications validated against `SPEC_V2` |

`obligations.verify_obligation_text()` re-reads the frozen S35 bytes on every run and fails closed
if any verbatim string drifted, so a transcription typo cannot silently weaken an obligation.

## 8. Ownership

Everything under `stage3_score/S36_IMPLEMENT_ARMS/` is this node's. Nothing outside it is written.
`git` is not run — the coordinator makes the task-scoped commit.
