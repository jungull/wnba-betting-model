# F11_PLAYER_ALLOCATION_ARCHITECTURE — report

**Lane:** future_research · **Type:** documentation · **Role:** read-only research scout
**Governing contract:** `RESEARCH_CONTRACT_V1`
**Deliverable:** `TARGET_CONTRACT_DRAFT.md` (this report is the audit trail behind it)

> DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is NOT authorisation to
> fit. Fitting requires a target contract, a matched K0, cutoff-valid evidence, a preregistration
> and an independent gate review.

---

## 1. The finding

The player allocation / distribution architecture **has no estimand**. There is no documented
target statistic, no unit, no denominator. `TARGET_CONTRACT_DRAFT.md` records
`NOT_DERIVABLE_FROM_DOCUMENTATION` and does not invent one.

This is not a gap of neglect. The exposure arm that *is* the allocation architecture declines the
question on purpose: `arm_registry.jsonl:16` carries
`"nothing_scored": "this arm computes no accuracy, calibration, error or edge figure of any kind"`
and a `stop_boundary.must_not_be_inspected_in_this_phase` list whose first two entries are
"actual-minute MAE" and "possession MAE". The architecture is deliberately ungraded, and the
documentation that would ground a grade — the Stage-C "usage/possession share" row — is recorded
**ABSENT** at `PLAYER_RESEARCH_COVERAGE_MATRIX.md:57`.

G04 catalogued 13 tracks in this condition. The nearest, `M24_STAGE_CDE_TARGET_INVENTORY`, carries
`needs_target_contract: true`. This node is a fourteenth instance of the same condition, and the
correct output is to say so.

## 2. What was measured, and how

All numbers come from `MEASURE.py` in this directory, run as:

    python experiments/player_program/future_research/F11_PLAYER_ALLOCATION_ARCHITECTURE/MEASURE.py

It writes `MEASUREMENTS.json`. It reads five artifacts, fits nothing, scores nothing, and opens no
path under `stage2b/SEALED_RESULTS/`.

**Consequential measurements:**

* **The allocation layer has one free quantity.** In the primary regime,
  `projected_off_possessions - projected_minutes/40 × projected_team_off_possessions` has max
  absolute value **0.0**; the defensive analogue is also **0.0**; projected minute share equals
  projected possession share to **5.55e-17**. Under the frozen mapping
  (`arm_registry.jsonl:16`, `minutes_to_possession_mapping.frozen_rule`) a "possession allocation"
  arm and a "minutes allocation" arm are the same arm. Any estimand must say which it grades.
* **The conservation identities hold exactly, per regime.** Max deviation of the player-possession
  sum from 5× the team total: **8.88e-16** in each of the three regimes; team minutes sum to 200
  everywhere (199.99999999999997 to 200.00000000000003). The wave summary's claim at
  `DISCOVERY_WAVE_1_SUMMARY.md:218-219` is confirmed against the bytes.
* **`production_eligible` is `false` on all 120,262 rows.** No regime is production evidence.
* **Only the primary regime is both cutoff-valid and as-of-captured**: 35,629 rows, **2,914**
  team-games, **1,458** games. The second regime has `information_available_at_cutoff: false`;
  the third is cutoff-valid but not as-of-captured. Regime flags reproduce
  `PROJECTED_EXPOSURE_RECEIPT.json` `config.REGIME_EVIDENCE` exactly.
* **The allocation universe is not the possession universe.** The settled primary possession target
  runs on 2,982 team-games over 1,491 game clusters; measured, that is exactly the `pace_resolved`
  subset of `team_possession_prior_v1.parquet` (2,982 rows, 1,491 games, 8 unresolved). The primary
  allocation regime is 2,914 over 1,458. Conflating them in a fold design would be a defect.
* **Cutoff policy is not uniform.** `exact_tip_T-90m` exists only from 2025 (4,866 rows in 2025,
  5,395 in 2026); 2021–2024 are entirely `date_only_prior_day_cutoff`. Any chronological evaluation
  crosses the policy change inside its own window.
* **2021 is entirely fallback.** `pred_is_fallback` is true for 4,850 of 4,850 primary 2021 rows.
* **34.2% of allocated primary team-games are label-degraded**: of 2,914, `plausible` 1,916,
  `degraded_roster_cardinality` 989, `degraded_both` 5, `degraded_extreme_scaling` 4; a further
  **76** team-games are `unresolved_insufficient_candidates` and emit nothing.
* **A realised denominator is constructible but not admissible.** `possessions_raw_v2.parquet` has
  238,563 possessions over 1,495 games with a valid ten-player lineup on 238,060 (503 invalid), and
  **0** of the 2,914 primary team-games lack realised or valid-ten offensive rows. The registry
  declares this artifact a realised reconstruction that "cannot be used as forecast exposure", and
  the arm's stop boundary forbids inspecting minute or possession error in this phase.

## 3. Proving the negative

The estimand's absence is a measured absence. Greps for `possession share`, `usage rate`,
`usage_rate`, `minutes share`, `minute_share` across the four root planning documents and all of
`experiments/player_program/` returned **positive** hits — `PLAYER_RESEARCH_COVERAGE_MATRIX.md:57`,
`register_program_roadmap.py:181` and `:185`, `build_projected_exposure.py:409`,
`HYPOTHESIS_LEDGER.json:21` and `:26`, `GATE_INVOCATION_CONTRACT.md:43`, and the exposure receipt
and validation files. The search machinery finds these strings. Every hit is a feature-family
entry, a diagnostic label, or an ABSENT inventory row. None is a target definition.

## 4. What I could not establish

1. **Whether the program intends the allocation estimand to be a share, a count, or a
   distribution.** The objective lists per-player forecast distributions and a staged causal order
   (`register_program_roadmap.py:49-85`) without naming a graded statistic for the allocation step.
   Choosing among them is a registration act, not a reading act.
2. **Whether any Stage C/D/E denominator is settled or illustrative.** Same limitation G04 recorded:
   `register_program_roadmap.py:63` labels them `"examples"` and `:74` supplies a weaker-proxy rule.
   No per-channel denominator is a frozen contract.
3. **The discovery-wave source file `run_ws5.py`.** `HYPOTHESIS_LEDGER.json:715` cites
   `run_ws5.py:226-235` as the comparison-parity receipt for the WKfree control. No file named
   `run_ws5.py` exists anywhere in this worktree. The ledger's *description* of the control was
   quoted from the ledger line itself and verified there; the referenced source lines could not be
   read. Recorded, not resolved.
4. **Any statement about how well the allocation layer performs.** No comparative performance was
   measured, computed or sought; `SEALED_RESULTS` was not opened. Discovery-wave figures exist in
   the ledger and the wave summary, but they are development-only discovery evidence, explicitly
   "discovery directions, not promotion candidates"
   (`DISCOVERY_WAVE_1_SUMMARY.md:224`), and this draft rests on none of them.
5. **Whether the exposure flags are true.** `PROGRAM_STATE.json` records `cutoff_validity_asserted`
   (Severity B, `implemented: false`): cutoff validity "is a property of upstream construction and
   cannot be verified from bytes". The inventory reports the flag values as they exist, measured;
   their truth is an assertion.

## 5. Contradictions found

1. **`RESEARCH_CONTRACT_V1.md:36` vs `PROGRAM_STATE.json`.** The contract states dual-frame auditing
   is "contractually required but not yet fully implemented". The state file records
   `dual_frame_audit` as `implemented: true`, `closed_by: PLAYER_DUAL_FRAME_AUDIT_v2`. The state
   file is authoritative for scientific state and is derived, so this reads as a documentation lag
   in the contract prose — but reconciling them is outside this node's authority. Reported, not
   silently reconciled.
2. **Coverage matrix vs artifact (apparent, resolved).** `PLAYER_RESEARCH_COVERAGE_MATRIX.md:57`
   marks "usage/possession share" ABSENT while the exposure artifact emits a projected possession
   share. Consistent: the matrix inventories Stage-C opportunity *targets*; the artifact is an
   ungraded forecast-exposure bridge. Recorded so the artifact is not later read as closing that
   matrix row.
3. **A measurement trap, not a contradiction.** The exposure artifact stacks three evidence regimes
   in one file. Pooled across regimes, player possessions sum to 10–15× the team total and minutes
   to 400–600 per team-game. The documented 5×/200 identities are **per regime** and hold exactly
   there. Anyone re-measuring must group by `regime` first.

## 6. Stop conditions

The node's stop condition was **not tripped**. This draft defines no target, registers no arm,
proposes no feature, touches no fold structure, and changes no universe, K0 structure, inference
structure, cutoff-valid feature set or leakage status.

One Severity A item is **carried forward, not raised here**:
`general_feature_producer_provenance` (`PROGRAM_STATE.json`, `implemented: false`) blocks any fitted
arm whose feature producer emits no construction receipt, and only `possession_features.py` emits
one. G04 already raised it as Q10. An allocation feature producer would hit it immediately.

## 7. Compliance

* No git command was run. No frozen artifact was read for modification or modified.
* Writes are confined to
  `experiments/player_program/future_research/F11_PLAYER_ALLOCATION_ARCHITECTURE/`:
  `TARGET_CONTRACT_DRAFT.md`, `REPORT.md`, `MEASUREMENTS.json`, `MEASURE.py`.
* `experiments/player_program/stage2b/SEALED_RESULTS/` was never opened.
* Nothing was fitted and nothing was scored.
