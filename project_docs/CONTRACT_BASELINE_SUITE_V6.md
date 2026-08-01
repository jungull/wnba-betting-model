# `contract_baseline_suite_v6` — the complete runner

*Registered 2026-08-01. **No real contract row has been read; no historical OOF, fitted suite
artifact, accuracy figure or coverage score exists or was inspected.** The implementation runs on
synthetic data only and has no file I/O.*

**Supersedes `contract_baseline_suite_v5`.** v1–v5 records and documents are unchanged.

`config_hash` **`4857907f8f338bd9bafbcf22847da56f3f22785159a7d65b4f1381e2a02ec0f7`**.

---

## 0. Why v6 exists

v5 corrected the primitives. It did **not** ship a runner: `cbs_v5.py` ended at
`resolve_feature_asof`, with no fold runner, no emission path, no fitted-state constructor, no
validation composition and no call site outside its own tests.

The consequence is the thing that matters: **none of v5's corrections ever reached a generated
contract row.** The only executable runners were still v4's — with v4's defects and v4's arm
identity. v5's "corrected implementation" label was too strong, and that is recorded in
`project_docs/SPEC_ERRATA.md` rather than by editing the frozen v5 document.

v6 supplies the missing pipeline and binds every v5 correction into emitted output.

---

## 1. The runners

`cbs_v6.run_player_fold` and `cbs_v6.run_team_fold`, built **only** from the corrected v5
primitives. **No path argument exists anywhere in the module**, so the pipeline cannot reach the
real contract even by accident.

Each returns one object: `predictions` (per target), `history_sidecar`, `diagnostics`,
`validation_receipts`, `coverage`, `validated` and `scoring_permitted`.

All five targets emit a row for **every required obligation** — predicted or explicitly excluded.

## 2. The history-audit sidecar — `cbs_history_audit/1`

v5 computed `n_prior_candidate_games` and `n_prior_appearances` separately and then **dropped
them on the floor**. They are the evidence that 0-of-k was treated as *evidence* rather than
*absence*, so they now survive into an artifact, one row per obligation:

`row_uid` · `n_prior_candidate_games` · `n_prior_appearances` · `has_prior_obligation` ·
`has_prior_appearance` · `team_prior_games`.

The contract's `n_prior_games` remains **prior appearances**, and a test asserts the two agree.

## 3. Cold and fallback, bound into the rows

| target | cold when | also fallback? |
|---|---|---|
| `p_active` | no prior **obligation** | no |
| the three conditional targets | no prior **appearance** | **yes** — no conditional history exists |
| `team_game_distribution` | `prior_games == 0` (season opener) | no |

## 4. Fitted state and `model_hash`

`FittedState` is constructed **per fold and per target** from the actual fitted objects: feature
order, scaler mean and std, dropped features, λ, coefficients, selected αs, calibration maps, base
rate, fallback mean, dispersion sd/method/offsets, and support bounds. `model_hash` is its digest.

v5 hashed a generic dictionary that only a hand-built test populated. Here a test mutates **each
of sixteen components** and requires the emitted hash to move, and asserts the four player targets
carry four distinct hashes in the real run.

## 5. Real-boundary identity

`require_identity` binds the registered config hash and an **exact** snapshot hash. Placeholders
(`"synthetic"`, all-zero, non-hex) are rejected unless the caller passes `synthetic=True`. A
runner invoked with `synthetic=False` and a placeholder raises `AdapterBoundaryError`.

## 6. The composite validation gate

`validate_arm_output` runs the **historical** `prediction_contract_v2.validate_predictions()`
**and then** the hardened strict validator, returning **one fail-closed receipt**. `ok` requires
both, so tightening the strict validator can never be bypassed by satisfying only the historical
one. A malformed frame returns a verdict; it never raises.

Receipts — coverage, exclusions, provenance, validation — are produced by the runner, and
`scoring_permitted` is gated on `validated`. **No scoring function is reachable before them, and
this runner computes no accuracy or coverage score in any case.**

### Strict validator hardening — `contract_v2_strict/2`

| gap in `/1` | `/2` |
|---|---|
| expected arm/fold/config/snapshot defaulted to `None`, so identity binding was **optional** | all four are **mandatory**; omitting one is itself a rejection |
| universe fold/cutoff checks vanished if those columns were absent | the universe **must** carry them |
| `+inf` accepted on unbounded targets | point and quantiles must be **finite** |
| non-numeric `p_active.pred_sd` silently coerced to null | must be **actually** null |
| numeric `0`/`1` (including floats) accepted as booleans | genuine booleans only |
| excluded rows unconstrained | must have **null** point/sd/quantiles **and retain full identity lineage** |
| a malformed frame could raise | **fails closed** with a reason |

## 7. Team structural preconditions

All fail closed: four channels present, **non-null and finite**; `side` present, non-null, values
exactly `home`/`away`; no duplicate `(team_id, game_id)`; and **every game exactly one home and
one away row**. v5 checked only that the channel columns existed.

## 8. Runner-level tests — `tests/test_cbs_v6.py`, 104 assertions, synthetic only

R1 five targets, full coverage, composite gate · R2 full train/test shuffle invariance of
predictions **and** model hashes · R3 causal as-of (a row changes neither itself nor any earlier
prediction) · R4 calibration/T3 and outer-test isolation · R5 side maps and every structural
precondition · R6 conditional fallback emission and target-specific cold starts · R7
zero-candidate visibility and exact coverage · R8 sidecar completeness · R9 every fitted-state
component moves the hash · R10 strict rejection of wrong/missing identity, absent universe
columns, infinities, fake-null SD, numeric flags and malformed excluded rows.

## 9. Status

**Not** a promotion candidate; **not** evidence; `arm_incumbent` remains rejected and unconsumed;
the hierarchical arm is **not** begun. Real-contract execution awaits supervisory review, and
validation, provenance, obligation coverage and exclusion cross-tabs must pass **before any
accuracy metric is inspected**.
