# P38_BLINDED_FIT -- EXECUTION_LOG (operational record; the node report)

> **Epistemic status (verbatim, binding):** SEALED RESULTS. Standing conditional authorisation: the fit executes automatically once P37 passes, because the preregistration and the implementation audit are exactly the conditions the contract requires. Outputs are sealed and unread until P39 verifies them.

Executor: P38_BLINDED_FIT (D039 dispatch, workflow wf_6972ebba-bdb), in THREE passes
(git was not invoked by this node, per standing rule 4; commits carried from the ledger):
first pass 2026-08-06T23:39:49Z on the dispatch-event commit
(`b8422d2ae16a29d0d65174f8cd4b0a1b0651744b`; D039 mandates EXEC-M1..M7); D040 continuation
2026-08-06T23:59:21Z (ruling D040_P38_FOLD_LOCAL_P25_AND_A08: per-fold P25 call-site
wrapper; seven P25-blocked instances re-run; A08 both K elements fitted); FINAL-FITS pass
2026-08-07T00:32:37.333452+00:00 on the remediation-wave commit
(`4814a95474969ff1bdfd860b03447b295d505fdd`; see MANIFEST.json
code.final_fits_commit_provenance): A20/A21/A23 fitted from their D039/D040
remediation-lane rebuilds (suites green) and A24 fitted after its registry amendment was
appended by the coordinator single-writer and verified against its pins. Prior sealed
verdicts are preserved under `.pre_D040` names and beside `FINAL_FITS_SUPERSESSION.json`
sidecars, never erased.

**This file contains ZERO comparative performance numbers.** Every result of every fit is
sealed under `stage2b/SEALED_RESULTS/P38/` and was written there by the frozen runner
directly; this executor never read, printed or returned any of them. The machine-readable
mirror of this log is `SPEC.json` beside it; the sealed manifest is
`stage2b/SEALED_RESULTS/MANIFEST.json` (sha256 recorded in SPEC.json).

## 1. What executed

* **Fold policy NAMED on the record before any real fit (EXEC-M2):**
  `EXPANDING_PRIOR_SEASONS`. D039 ratification of the P37 frozen-precedence analysis: the D006 operative fold masks (train_lt_2022..train_lt_2026) ARE the EXPANDING_PRIOR_SEASONS masks; SEASON_BLOCK is preserved on the record as the historical shape of the S7 statement, not an operative mask.
  The naming lands in every receipt's P27 record (`p27_fold_policy` field, verified in all
  fitted receipts).
* **Universe:** 2,982 team-game rows / 1,491 game clusters
  (`raw_index_membership:n=2982:sha256=61f69db015f3270c7f0fd182a92e0371`), built by
  `possession_features.load_universe()`; offset `log_exposure` verified bit-identical to
  `log(projected_team_off_possessions)` (max abs diff 0.0). Caller-supplied columns added
  for frozen card names: `log_exposure`, `own_est`/`opp_est` (A02's P25-registered contrast
  inputs), `opp_id` (A22), `is_home_offense` (A25; derived two-sidedly from the frozen
  possessions artifact, verified exactly one home row per game).
* **Folds:** the five frozen D006 expanding folds, season-mask == date-cutoff-mask verified
  fold-by-fold; games never split (verified). Contract-schedule archive: 2,990 rows /
  1,495 games (includes the 8 opener rows the universe excludes); realised per-team-game
  facts joined 1:1 from the possessions artifact with zero misses.
* **Input pins:** both frozen artifacts re-hashed and equal to their pins
  (`team_possession_prior_v1.parquet`, `possessions_raw_v2.parquet`); P35 SPEC.json
  re-hashed and equal to `runner_constants.P35_SPEC_SHA256`; all five guard byte pins and
  `team_cities.csv` verified inside every receipt (`guard_pins.all_match == true`).
* **Blinding:** `P38_UNSEALED` set by this executor only; every receipt records
  `blinding.unsealed == true` with the real-structure signatures listed.
* **Seeds:** master 20260806, frozen derivation string; per-fold stream digests in every
  receipt and in the sealed manifest. B_test=10,000; B_train_refit=2,000; K7 symmetric NA
  rule as frozen; p-value formula consumed byte-unchanged (EXEC-M3);
  `cluster_bootstrap.py` sha256 `08081fac50951b535c8650b5fe6ec07890072915fdd5418607cf36ccfd4fdea0`.

## 2. Fleet outcome after the FINAL-FITS pass (30 sealed element directories, zero performance numbers)

| element | status | wall s | evaluable folds | deactivated folds | receipt sha256 |
|---|---|---|---|---|---|
| `A02_cal_blend_contrast__single` | FITTED | 18.1 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `234dbf256c18a22703dfa9a32269d3af2b7834f1db220a902ae77f06bb272468` |
| `A03_cal_shallow_tier_intercept__t3` | FITTED | 20.4 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `48b3015a04ea54b842f5b6b809a6a677e7a81fdd7e94ceabdc1759449e329e19` |
| `A05_cal_playoff_intercept__single` | FITTED | 20.2 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `f5b4c59f92aa98d56b1242d533e9c33aee29d86b1b16e685b4607f876c43b0f1` |
| `A07_early_season_transient__single` | FITTED | 29.8 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `d77f9678656e02b0090f2b5175b18a6e10b7560cdaf1beda524d16eaec82a294` |
| `A08_K20` | FITTED | 25.3 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `4a5e34564fb3a038ff3f08623c767bac96f419bdf6b6b69a85ccb1b4513f9043` |
| `A08_K80` | FITTED | 25.2 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `469b4edec8f5c10888d4737db8689e2389919b93658ae280019127bfe6c967c3` |
| `A08_league_lag_level` | SUPERSEDED_BY_D040_ELEMENTS_FITTED | - | - | - | `-` |
| `A09_kappa10` | FITTED | 25.5 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `7329e1492cd8c5bb6487dbad8d4ea1db8b3c848027ecfd623d0319680b0ca85f` |
| `A09_kappa2` | FITTED | 24.9 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `7c3d0d92a43056c2585a320520de9fc2c395d2d1309c5b9b740ab5b09d91b201` |
| `A09_kappa50` | FITTED | 23.8 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `06c3977aec3086b86b20e8d8baf38033803b2fb5c4d5c8a06e619ee361a804e7` |
| `A10_lambda0.2` | FITTED | 26.6 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `312bdaee217b3fc2e2d01dd03399ed6a2beb89009391999dedd2c3b053625b76` |
| `A10_lambda0.5` | FITTED | 25.4 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `62fcedfe7a2552711edd7cf1294134b93b4524544bbb2ffc43a5763688fb16a1` |
| `A11_rho0.25` | FITTED | 19.0 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `e103e7714747b4d34743be350102866b121c3bf1b607a5a370c10237193693ab` |
| `A11_rho0.5` | FITTED | 21.2 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `a019a17720c02f013c5b9d4fee2d21d9b83d2dfae5bcf04e78defe25eb44be8c` |
| `A11_rho0.75` | FITTED | 19.6 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `2e4ff8bca51ccaf0fabb5a1b7314a5e4d3a6c1460baa2779933d69f6d76e700e` |
| `A12_carryover_additive_decay__single` | FITTED | 29.9 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `00079f93a4427726b2f986132d0352d683f41fe06b87968572bf5b1495548678` |
| `A13_carryover_roster_continuity_moderator__single` | FITTED | 61.4 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `e1893b3ac32149d1e3a666e75c425345e72c658ef85a9c1e393946a525f3fb57` |
| `A14_expansion_intercept_decay__single` | FITTED | 11.7 | train_lt_2026 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025 | `5bc7891ccee835017c88f2dec14c3978ea525c926f84b2c8580b12f35a9c151c` |
| `A15_gap_by_depth_asymmetry__single` | FITTED | 26.9 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `12bf8980751a4af589ac48474f5ab0fc45ebd01fbaa1021c57c54ab72117ef97` |
| `A16_lag_residual_own_minus_opp` | FITTED | 18.1 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `ae749940301d5a930ad413af5822e7210ae280113ea9c3cb8ac0e5d8ddd7f67d` |
| `A17_transition_mix_share__single` | FITTED | 22.8 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `3f682237435d547e4eb49437b04ac68431c7f03021a243d68685252b6685dbda` |
| `A18_median_duration_contrast` | FITTED | 42.8 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `8466f0876cd8baa830e3f00390b5a5c679905cb3a1c94a8aef76970d0233bd51` |
| `A20_forced_turnover_contrast` | FITTED | 26.2 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `ef12a5d5ae176bd49a7d4abfaca494f1cf3b67e87c75ef33f9603d9cb30840be` |
| `A21_garbage_time_contamination` | FITTED | 25.5 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `106829b49a0134ee0dc8284f0b79a415917d8651404db192e6cf8d1d79317a6e` |
| `A22_lineup_churn_tv_distance__single` | FITTED | 25.0 | train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | train_lt_2022 | `b2e060b3f0936ef1916c41a7103081c8466788a02b866fb5d677260d3b2f18d6` |
| `A23_rest_differential_contrast__bundle_AI` | FITTED | 29.3 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `c49424d38e5b2b2cce1d8fa005a4d419d30da82c724f6dafc57d7a48a57b0b3a` |
| `A23_rest_differential_contrast__bundle_OM` | FITTED | 29.4 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `afebd1fa861b5620eb93dbacd741adacc4927094d3dbb9e935934ebe1cfef4ce` |
| `A24_rest_advantage_symmetric` | FITTED | 21.6 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `be2b66495a8a1eeed3f6dd1ab6c12d55176b66ced130089df6a4d0a0bbe01450` |
| `A25_home_offense_contrast__single` | FITTED | 20.4 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `9053c3baba5f2f773f40b15a26a352ecb3a6ff4d303aa3cb72b4b7d9722271e5` |
| `A26_sos_correction_own_minus_opp` | FITTED | 40.3 | train_lt_2022,train_lt_2023,train_lt_2024,train_lt_2025,train_lt_2026 | - | `d2a5c29d30e74e8ffa874ec5293487bb5df377906d5a95addbab63e92c0198fb` |

Counts: **29 module instances / 29 FITTED / 0 outstanding**
(7 re-run under D040 after first-pass BLOCKED_GUARD, 2 the
A08 K elements added by D040, and 5 the FINAL-FITS elements -- A20, A21,
A23 x2, A24 -- fitted from the remediation-lane rebuilds / the verified registry
amendment, each with its first-pass BLOCK_VERDICT.json or EXCLUSION_RECORD.json preserved
byte-for-byte beside FINAL_FITS_SUPERSESSION.json),
**0 BLOCKED_GUARD remaining**,
**0 BLOCKED_AT_INVOCATION_BY_RATIFIED_MANDATE remaining**,
**0 EXCLUDED_PRE_P38_PER_D039 remaining**, **1
SUPERSEDED_BY_D040** (the A08_league_lag_level placeholder: its D039 exclusion condition
was met and the two K elements fitted; the original EXCLUSION_RECORD.json is untouched
beside D040_SUPERSESSION.json). Cumulative fleet wall time
771.2s (all passes; progress.jsonl carries each pass).

## 3. Executor mandates (EXEC-M1..M7) -- what was implemented, exactly

* **EXEC-M1** -- `p38_wrappers.P27GuardHarnessView` + `FoldGovernor`: task-specific
  call-site wrappers; the frozen guard's per-fold UNEVALUABLE verdicts and preregistered
  active-set-rule collapses are honoured symmetrically for arm and null via the runner's
  own deactivation mechanism; remaining folds proceed; A07's ">=2 folds" retirement
  arithmetic implemented (not triggered: zero A07 folds unevaluable). No frozen file
  edited; the interposition is an in-process rebinding of the loaded runner module's `gh`
  attribute for the duration of each run, recorded per arm. NOTE (recorded, not hidden):
  the frozen runner labels governor-excluded folds "STRUCTURALLY_DEACTIVATED /
  card-pinned"; the true basis for every excluded fold is in each sidecar's
  `fold_exclusions` map. P38 fold exclusions actually applied: A12 train_lt_2022
  (card-deactivated AND rule-collapsed), A13 train_lt_2022 (rule-collapsed), A14
  train_lt_2022..train_lt_2025 (rule-collapsed; expansion regressor structurally zero
  before 2026), A11 train_lt_2022 (card, module's own hook).
* **EXEC-M2** -- named above; passed explicitly to every P27 invocation (prepass and
  runner); never the shipped SEASON_BLOCK default.
* **EXEC-M3** -- `two_sided_bootstrap_p` consumed byte-unchanged (file hash above; the
  executed bytes are the receipts' `code.sources` hashes).
* **EXEC-M4** -- A09/A10 `build_design` re-bound at the call site to the 2,990-row
  contract-schedule archive using the arms' OWN frozen pure functions
  (`align_n_t_d_t_by_key` / `align_n_t_d_t_c_t_by_key` / `kappa_contrast`); the 2,982-row
  universe supplies target keys only and never enters the clock. Clock divergence
  MEASURED (universe-clock vs contract-clock, structural feature-construction fact,
  recorded in the A09/A10 sidecars): n_t differs on 1,890 rows and d_t on 2,975 of the
  2,982 universe rows (the four missing opener games shift the all-prior league mean for
  nearly every later row) -- the barred clock is anything but empirically inert,
  confirming the mandate's point.
  A08's caller-supplied-pace obligation is recorded in the manifest for its
  post-re-audit entry. A12's `pace` column computed by the frozen
  lagged_regulation_equivalent_pin formula at the call site.
* **EXEC-M5** -- A03 `tier_symmetry_check` invoked per fold (training rows), arm and null
  identically; all five folds returned ESTIMABLE (both tiers above the 10-cluster floor);
  records in the A03 sidecar.
* **EXEC-M6** -- ONE fleet-wide adjudication, on the record: the `n_clock_pin` scope is
  UNIVERSAL (the pin's own frozen text "the universe-row clock is barred", frozen-bytes
  precedence, and the D039-ratified compiler observation). Consequence, per the auditors'
  fork: A20 and A23 (both bundles) require re-derivation on the contract clock -- a code
  change, hence remediation nodes, never a silent P38 patch -- and are BLOCKED at
  invocation (block verdicts sealed); A26 is FITTED under its two P37-verified exact
  mitigations (league-mean cancellation is an algebraic identity in z5; residual
  divergence confined to 2021 opener-team rows), with the structural exposure re-measured
  and sealed in every sidecar: 8 opener rows / 4 games absent from the universe, 8 opener
  team ids, 266 universe rows of 2021 belonging to opener teams.
* **EXEC-M7** -- `p26_check(bind=True)` invoked at scoring time for every executed arm.
  Outcomes: `bound` (binding ran; `require_matched_k0` matched) for every substantive
  arm; `tolerated_r8_shape` for the three calibration_only arms (A02/A03/A05), where the
  bind path's RAW re-validation refuses the record on exactly the R8-shaped findings the
  frozen P35 r8_scope_adjudication scopes out -- the adjudicated (non-bind) wrapper
  validation passed for all three, and the refusal is recorded verbatim per arm
  (contradiction 4 below).
* **D040** (this continuation) -- `p38_wrappers.P25FoldLocalGuardView` +
  `p38_driver.p25_fold_prepass`: the EXEC-M1 analogue for the runner's per-fold P25
  audit, ruled a deterministic consequence of D039 (D040_P38_FOLD_LOCAL_P25_AND_A08).
  Section 4 below has the full mechanics and custody. Applied to every instance executed
  in this continuation (for instances whose every P25 fold verdict PASSES, the prepass
  records the verdicts and the tolerance never fires). FOLD_UNEVALUABLE exclusions
  actually applied by the wrapper this pass: A05/A15/A17/A22 train_lt_2022 (each fits on
  the remaining 4 folds); A12/A13 train_lt_2022 and A14 train_lt_2022..train_lt_2025
  were ALREADY excluded by the first-pass P27/card machinery (EXEC-M1), so for them the
  D040 wrapper's contribution is that the runner's bundle-loop audit of those excluded
  folds' degenerate designs no longer escalates to a whole-arm refusal.
* **FINAL-FITS pass** (this closure) -- the D039/D040 remediation lane closed out per
  D040 ruling item (3). A20/A21/A23 constructed from their REMEDIATED modules (rebuilt by
  the remediation lane to EXEC-M6's contract clock and PIN-A21's possession-weighted
  reading; suites green -- A20's suite additionally re-run green by this executor
  immediately before its fit); A24 constructed with the REGISTRY-ADJUDICATED fallback
  applied at the call site after `p38_driver.verify_registry_amendment()` matched the
  appended registry to its pins (51 records; fail-closed check). A21's frozen card column
  name `opponent_team_id` supplied at the call site as an alias of the universe's own
  `opp_team_id` (same discipline as `opp_id`/A22). Directory keys reuse the fleet's
  original sealed element keys so every receipt sits beside its superseded first-pass
  verdict; each receipt's own `element_id` is the module's and is recorded as-is
  (A21_garbage_time_contamination__single, A23_bundle_AI/OM,
  A24_rest_level_symmetric__single). All five FITTED; A21 train_lt_2022 FOLD_UNEVALUABLE
  under the standing D040 wrapper; A24's amendment-scope contradiction recorded
  (section 5 / contradiction 8).

## 4. The seven frozen-P25 guard blocks: RAISED as P38-R1 (first pass), RESOLVED by D040 (second pass)

The frozen runner audits EVERY fold's design with P22/P25 in its bundle loop, and a P25
blocking finding in ANY single fold fails the whole arm closed. Seven instances blocked
that way on the first pass; the executor raised P38-R1 rather than tolerate P25 findings
without a mandate, and the coordinator ruled (**D040_P38_FOLD_LOCAL_P25_AND_A08**, a
deterministic consequence of D039/EXEC-M1): a task-specific per-fold P25 CALL-SITE
wrapper -- never a guard edit -- honours the frozen guard's own fold-local verdicts. A
fold whose P25 verdict is fold-local-blocked records **FOLD_UNEVALUABLE** with the full
guard record (carried unmodified in the sealed receipt's `guard_records.p25_per_fold`
and in `P25_FOLD_LOCAL_RECORDS.json`), and the arm fits on its remaining folds, arm AND
null identically via the P38 fold governor. FINAL-design or non-excluded-fold P25 blocks
still fail closed. Implemented as `p38_wrappers.P25FoldLocalGuardView` +
`p38_driver.p25_fold_prepass`, mirroring EXEC-M1's `P27GuardHarnessView` exactly (the
view cross-checks the runner's deterministic fold audit order by training-row count and
refuses on any desynchronisation).

(The FINAL-FITS A21 fit later joined the same per-fold P25 mechanism: its train_lt_2022
`is_playoff_game` column is game-level under the game-shared projection, so that fold is
FOLD_UNEVALUABLE and A21 fits on the remaining four -- recorded in its own sidecar and
`P25_FOLD_LOCAL_RECORDS.json`, not in the seven-instance table below.)

First-pass block pattern and D040 re-run outcome, per instance:

| element | folds that BLOCKED (first pass) | findings fired (kind:feature) | D040 status | FOLD_UNEVALUABLE folds |
|---|---|---|---|---|
| `A05_cal_playoff_intercept__single` | train_lt_2022 | calibration_parameter_in_substantive_arm:is_playoff_indicator; candidate_exactly_determined_by_offset:is_playoff_indicator; candidate_is_function_of_incumbent_projection:is_playoff_indicator | FITTED | train_lt_2022 |
| `A12_carryover_additive_decay__single` | train_lt_2022 | augmented_rank_deficient:__augmented_design__; calibration_parameter_in_substantive_arm:dev_prev; calibration_parameter_in_substantive_arm:w_n:dev_prev; candidate_exactly_determined_by_offset:dev_prev; candidate_exactly_determined_by_offset:w_n:dev_prev; candidate_is_function_of_incumbent_projection:dev_prev; candidate_is_function_of_incumbent_projection:w_n:dev_prev | FITTED | train_lt_2022 |
| `A13_carryover_roster_continuity_moderator__single` | train_lt_2022 | augmented_rank_deficient:__augmented_design__; calibration_parameter_in_substantive_arm:cont_i; calibration_parameter_in_substantive_arm:cont_i:dev_prev; calibration_parameter_in_substantive_arm:dev_prev; calibration_parameter_in_substantive_arm:w_n:dev_prev; candidate_exactly_determined_by_offset:cont_i; candidate_exactly_determined_by_offset:cont_i:dev_prev; candidate_exactly_determined_by_offset:dev_prev; candidate_exactly_determined_by_offset:w_n:dev_prev; candidate_is_function_of_incumbent_projection:cont_i; candidate_is_function_of_incumbent_projection:cont_i:dev_prev; candidate_is_function_of_incumbent_projection:dev_prev; candidate_is_function_of_incumbent_projection:w_n:dev_prev | FITTED | train_lt_2022 |
| `A14_expansion_intercept_decay__single` | train_lt_2022, train_lt_2023, train_lt_2024, train_lt_2025 | augmented_rank_deficient:__augmented_design__; calibration_parameter_in_substantive_arm:expansion_decay_interaction; candidate_exactly_determined_by_offset:expansion_decay_interaction; candidate_is_function_of_incumbent_projection:expansion_decay_interaction | FITTED | train_lt_2022, train_lt_2023, train_lt_2024, train_lt_2025 |
| `A15_gap_by_depth_asymmetry__single` | train_lt_2022 | calibration_parameter_in_substantive_arm:pace_gap:asym; candidate_exactly_determined_by_offset:pace_gap:asym; candidate_is_function_of_incumbent_projection:pace_gap:asym | FITTED | train_lt_2022 |
| `A17_transition_mix_share__single` | train_lt_2022 | calibration_parameter_in_substantive_arm:is_playoff_indicator; candidate_exactly_determined_by_offset:is_playoff_indicator; candidate_is_function_of_incumbent_projection:is_playoff_indicator | FITTED | train_lt_2022 |
| `A22_lineup_churn_tv_distance__single` | train_lt_2022 | calibration_parameter_in_substantive_arm:is_playoff_indicator; candidate_exactly_determined_by_offset:is_playoff_indicator; candidate_is_function_of_incumbent_projection:is_playoff_indicator | FITTED | train_lt_2022 |

Every other fold PASSES and the FINAL_ASSEMBLED_DESIGN passes for all seven. Measured
mechanisms (structural facts, sealed):

1. **Structurally-zero columns in recognised-degenerate folds** (A12, A13, A14): the fired
   columns are fold-constant exactly in the folds the preregistration itself already
   recognises as degenerate (A12's card-deactivated train_lt_2022; A13/A14's preregistered
   active-set-rule collapses, which the P38 governor had already excluded from FITTING).
   The runner still AUDITS those folds' designs.
2. **Game-level columns under a game-shared projection** (A05, A15, A17, A22): the
   projection is game-shared for ALL 1,491 games (measured; 1,014 distinct values), so
   every game pair is an offset tie group, and the exact-determination clause reads any
   game-level column (`is_playoff_indicator`; A15's symmetric `pace_gap:asym`) as
   offset-determined whenever the fold's cross-game ties happen not to break constancy --
   which occurs only in the smallest fold, train_lt_2022.

**P38-R1 disposition:** RAISED on the first pass (the executor held the fail-closed line;
no mandate then authorised tolerating P25 findings at the call site); RESOLVED by ruling
D040 (coordinator, 2026-08-06T23:41:49Z) and executed in this continuation. Custody of
every first-pass block verdict: `P38_EXECUTION_SIDECAR.pre_D040.json` (the first-pass
BLOCKED_GUARD sidecar with the frozen harness's whole-arm refusal text, preserved
byte-for-byte under the renamed path; the first pass wrote no separate
GUARD_BLOCK_RECORD.json for these seven), `BLOCK_DIAGNOSTICS.json` (the frozen guard's
FULL per-fold machine-readable records from the first-pass re-invocation, untouched),
plus this pass's `P25_FOLD_LOCAL_RECORDS.json` and the failing fold's full guard record
inside each sealed `receipt.json` (`guard_records.p25_per_fold[fold].passed == false`,
verified in all seven). Nothing was erased; the re-run wrote beside the first-pass
record, not over it.

## 5. First-pass blocks and exclusions by ratified mandate, and their FINAL-FITS closure

Every first-pass verdict below is PRESERVED byte-for-byte in its sealed directory; the
FINAL-FITS pass sealed `FINAL_FITS_SUPERSESSION.json` beside each (citing the remediation
records and the ledger-carried remediation-wave commit
`4814a95474969ff1bdfd860b03447b295d505fdd`) and then fitted the element through the frozen
runner under the identical discipline.

* **A20** -- first pass: BLOCKED, EXEC-M6 contract-clock adjudication (barred universe-row
  clock; no contract-schedule input). FINAL-FITS: FITTED from the remediation rebuild --
  constructor-injected contract_schedule frame as the trailing-window and E=3 clock
  (n_clock_pin satisfied; the four universe-excluded 2021 opener games enter the 8 opener
  teams' windows); suite re-run green by this executor immediately before the fit
  (T01..T17 incl. the T17 contract-clock regression, exit 0).
* **A21** -- first pass: BLOCKED, PIN-A21 (D039, verbatim): the implemented game-weighted
  `nc` was the recorded-but-REJECTED construction. FINAL-FITS: FITTED from the remediation
  rebuild carrying A17's POSSESSION-WEIGHTED `nc` (the preregistered reading; 15/15 PASS,
  `A21_TEST_RECEIPT.json`). The rejected construction was never fitted. train_lt_2022 is
  FOLD_UNEVALUABLE under the D040 per-fold P25 wrapper (same game-level
  `is_playoff_game`-under-game-shared-projection mechanism as A05/A17/A22); the arm fits
  on the remaining 4 folds, arm and null identically.
* **A23 (both bundles)** -- first pass: BLOCKED, EXEC-M6 (rest misresolution on the 8
  opener teams' second 2021 games). FINAL-FITS: both bundles FITTED from the remediation
  rebuild -- rest on the CONTRACT-SCHEDULE clock via the constructor-injected
  contract_schedule frame (A24's constructor pattern, the ruling's named in-fleet remedy;
  10/10 PASS, `TEST_RECEIPT.json`).
* **A08** -- first pass: EXCLUDED pre-P38 (D039, conditional on a non-implementer
  re-audit). Condition MET: `P37_IMPLEMENTATION_AUDIT/REAUDIT_A08.md`, verdict PASS
  (independent tie-heavy fixture; bitwise d_t parity with A09/A10; suite re-run passing).
  D040 ruled both K elements fit-eligible; the D040 continuation FITTED `A08_K20` and
  `A08_K80` under the same discipline (contract-schedule archive constructor-bound as the
  clock, caller-supplied `pace` computed by the frozen lagged_regulation_equivalent_pin
  formula at the call site -- the EXEC-M4 obligation recorded at first pass -- named fold
  policy, sealed receipts). The original EXCLUSION_RECORD.json is untouched;
  D040_SUPERSESSION.json sits beside it.
* **A24** -- first pass: EXCLUDED pre-P38 (D039 option (a): registry-appended amendment
  required BEFORE A24 fits; not yet appended then). FINAL-FITS: the amendment (adjudicated
  franchise-debut fallback, appended by the coordinator single-writer as registry record
  51) VERIFIED against its pins (51 records; sha256
  `a0aff704ba2c70f2edf756c5dc765f0ab63fb528ecc1585f6fc8cfbbcf33a7a6` == pin) and A24 FITTED with the
  fallback applied by a call-site build_design override over the arm's own frozen pure
  functions (`p38_wrappers.a24_registry_fallback_build_design`; the frozen module's
  fail-closed build_design is byte-untouched). MEASURED SCOPE CONTRADICTION RECORDED
  (contradiction 8 below): the amendment's registered enumeration (exactly 3 debut games /
  6 rows / no other row) is measured FALSE on the real universe -- the rule's own
  predicate (no strictly-earlier contract-schedule game) is also structurally true for
  the four 2021 teams whose first contract game was 2021-05-15 (the archive begins
  2021-05-14): measured 7 own-side predicate rows / 10 affected rows / 5 games, every
  predicate row structurally verified per call against the contract schedule (any row
  outside the two verified classes fails closed). The rule sentence governs by
  frozen-text precedence (the EXEC-M6 basis) and is the only reading achieving the
  amendment's own registered purpose ("a total function over the real universe"). Full
  record: `A24_REGISTRY_FALLBACK_SCOPE_RECORD.json`; the first FINAL-FITS attempt, which
  failed closed on exactly this discrepancy, is preserved as
  `P38_EXECUTION_SIDECAR.final_fits_attempt1_FAILED_PREPASS.json`.

## 6. Contradictions found (reported, never silently reconciled)

1. **"21 fit-eligible arms" (D039 ruling text, dispatch, graph events) vs the measured
   count of 20 at first pass.** 22 arm ids are implemented under P36 (A06 was never
   implemented -- D021 amended it to INADMISSIBLE-UNTIL-RECEIPTED); 22 - A08 - A24 = 20
   fit-eligible arm ids = 26 fit-eligible module instances. The likely arithmetic source
   of "21" is D026's "23 fit-eligible" (26 - A01/A04/A19) minus 2, which overlooks A06.
   Post-D040 the measured count is 21 arm ids / 28 instances / 24 run through the runner
   -- numerically equal to the D039 "21" but composition-DIFFERENT (D039's 21 counted A21
   and excluded A08; the measured 21 excludes A21 per PIN-A21 and includes A08 per D040).
   Recorded, not reconciled.
2. **PIN-A21 vs the dispatch's fit-eligible list.** D039 simultaneously ratified PIN-A21
   verbatim (rebuild under a remediation node; implemented construction rejected) and
   dispatched P38 "on the 21 fit-eligible arms" with only A08/A24 excluded. The executor
   followed the ratified pin (A21 blocked); both texts preserved.
3. **receipts.py expects `run_git=True` at P38 vs standing rule 4 "do not run git".**
   Executor chose rule 4: receipts carry `commit=null` + the receipts.py commit_note; the
   dispatch-event HEAD is recorded in the sealed manifest with provenance.
4. **EXEC-M7 vs the frozen R8 adjudication.** The mandated bind path re-validates the RAW
   record inside frozen `validate_k0_matched.bind_and_require_matched_k0`, which refuses
   the three calibration_only cards on exactly the R8-shaped findings the frozen P35
   r8_scope_adjudication (ratified SOUND at P37) scopes out. Recorded per arm as
   `tolerated_r8_shape` with the refusal text; the adjudicated wrapper validation passed
   for all three. The two frozen rules are in genuine tension; neither was edited.
5. **Runner deactivation labelling.** Folds excluded by the P38 governor are labelled by
   the frozen runner as "STRUCTURALLY_DEACTIVATED / card-pinned structural deactivation"
   in receipts; the true per-fold bases live in each sidecar's `fold_exclusions`.
6. **P38-R1** (section 4): the runner audits card-deactivated/rule-collapsed folds'
   degenerate designs and escalates fold-local P25 findings to whole-arm refusals.
   RESOLVED BY D040 in this continuation; the frozen runner's escalation behaviour itself
   is unchanged (call-site wrapper only) and the contradiction remains on the record as a
   fact about the frozen bytes.
7. **The frozen runner's receipt labelling of D040 exclusions** (same shape as
   contradiction 5): a FOLD_UNEVALUABLE fold under the D040 wrapper is labelled
   "STRUCTURALLY_DEACTIVATED / card-pinned structural deactivation" by the frozen runner;
   the true basis is in the sidecar's `fold_exclusions` ("P25_FOLD_LOCAL_BLOCK ->
   FOLD_UNEVALUABLE ... D040") and in `P25_FOLD_LOCAL_RECORDS.json`.
8. **The A24 registry amendment's registered enumeration vs the measured universe**
   (FINAL-FITS pass). The amendment's operative RULE ("any team t ... no prior
   CONTRACT-SCHEDULE game before g -> rest := cap", registered purpose: "extends the
   domain of rest(.,.) to a total function over the real universe") and its subordinate
   enumeration ("Affected rows: exactly 3 debut games ... 6 rows total. No other row is
   affected") disagree on the real universe: the predicate is also structurally true for
   the four 2021 archive-start teams' 2021-05-15 first games (4 rows / 2 games; teams
   1611661319/1611661322/1611661328/1611661329) -- an archive-start boundary fact the
   enumeration overlooked, exactly analogous to the opener facts EXEC-M6 adjudicated.
   Measured: 7 own-side predicate rows / 10 affected rows / 5 games vs registered 3/6/3.
   The executor applied the RULE sentence (frozen-text precedence; the only reading
   achieving the amendment's own registered purpose), structurally verified every
   predicate row per call, failed the first attempt closed on the discrepancy (verdict
   preserved), and RECORDED the contradiction here, in
   `A24_REGISTRY_FALLBACK_SCOPE_RECORD.json` and in the supersession sidecar -- never
   silently reconciled. The registered enumeration text is untouched in the registry.

## 7. What could not be established

* The executing git commits were not re-measured in-process (standing rule 4); they are
  carried from ledger events (dispatch commit for passes 1-2; the remediation-wave commit
  for the FINAL-FITS pass) and must be confirmed by the coordinator/P39 against the
  task-scoped commits. Executor sources are re-hashed in the refreshed manifest.
* Byte-identity of the runner sources to the P36 baseline commit could not be verified
  in-node without git; the measured sha256 of every runner source, arm module, guard and
  P38 wrapper file is in the sealed manifest for P39 to check.
* Whether the A24 amendment's authors INTENDED the rule's predicate to cover the four
  2021 archive-start rows (contradiction 8) is a question about a frozen text this
  executor cannot answer; the rule was applied as written, the discrepancy is fully
  recorded, and P39/P40 can strike A24 if the coordinator rules the enumeration was
  binding. Nothing else remains outstanding: every one of the 29 fit-eligible module
  instances is FITTED and sealed.

## 8. Custody

Sealed manifest: `stage2b/SEALED_RESULTS/MANIFEST.json`. Per-arm receipts, sidecars, block
verdicts, block diagnostics, exclusion records, D040 fold-local P25 records
(`P25_FOLD_LOCAL_RECORDS.json`), first-pass preservations (`*.pre_D040.json`), the A08
supersession note, the FINAL-FITS supersession sidecars (`FINAL_FITS_SUPERSESSION.json`
beside each preserved BLOCK_VERDICT/EXCLUSION_RECORD), the A24 fallback scope record
(`A24_REGISTRY_FALLBACK_SCOPE_RECORD.json`) and the preserved first FINAL-FITS attempt
(`P38_EXECUTION_SIDECAR.final_fits_attempt1_FAILED_PREPASS.json`) under
`stage2b/SEALED_RESULTS/P38/<element>/` with sha256 in SPEC.json. The appended arm
registry was verified, never written, by this node (51 records, sha256 in MANIFEST.json
`registry_amendment`). Driver/wrapper sources and their hashes: `p38_driver.py`,
`p38_wrappers.py`, `p38_run_fleet.py`, `p38_block_diagnostics.py`, `p38_finalize.py`,
`p38_write_log.py` (hashes in the manifest and SPEC.json; these sources were EXTENDED for
the D040 continuation and again for the FINAL-FITS pass -- the frozen runner, harness,
guards and arm modules were not touched by this node; A20/A21/A23's rebuilt modules were
written by their remediation lane, not here). Fleet progress: `progress.jsonl` (all
passes, append-only). No frozen artifact was modified; no git command was run; nothing
outside `stage2b/SEALED_RESULTS/` and `stage2b/P38_BLINDED_FIT/` was written.
