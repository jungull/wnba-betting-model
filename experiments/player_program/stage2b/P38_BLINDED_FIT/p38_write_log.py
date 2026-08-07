#!/usr/bin/env python3
"""p38_write_log.py -- materialise EXECUTION_LOG.md and SPEC.json for P38_BLINDED_FIT from
the sealed MANIFEST.json and the fleet progress log. Operational facts only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import p38_driver as D

MANIFEST = json.loads((D.SEALED / "MANIFEST.json").read_text(encoding="utf-8"))
ARMS = MANIFEST["fleet"]["arms"]

EPI = MANIFEST["epistemic_status"]

FITTED = {k: v for k, v in ARMS.items() if v.get("status") == "FITTED"}
GUARD_BLOCKED = {k: v for k, v in ARMS.items() if v.get("status") == "BLOCKED_GUARD"}
MANDATE_BLOCKED = {k: v for k, v in ARMS.items()
                   if v.get("status") == "BLOCKED_AT_INVOCATION_BY_RATIFIED_MANDATE"}
EXCLUDED = {k: v for k, v in ARMS.items() if v.get("status") == "EXCLUDED_PRE_P38_PER_D039"}
SUPERSEDED = {k: v for k, v in ARMS.items()
              if v.get("status") == "SUPERSEDED_BY_D040_ELEMENTS_FITTED"}
D040_RERUN = {k: v for k, v in ARMS.items() if v.get("status_pre_d040") == "BLOCKED_GUARD"}
D040_NEW = {k: v for k, v in ARMS.items()
            if k.startswith("A08_K") and v.get("status") == "FITTED"}


def arm_rows():
    rows = []
    for k in sorted(ARMS):
        v = ARMS[k]
        st = v.get("status")
        receipt = v.get("receipt_sha256_measured") or "-"
        ev = (v.get("receipt") or {}).get("evaluable_folds")
        ev = ",".join(ev) if ev else "-"
        deact = (v.get("receipt") or {}).get("deactivated_folds")
        deact = ",".join(deact) if deact else "-"
        ws = v.get("wall_seconds", "-")
        rows.append(f"| `{k}` | {st} | {ws} | {ev} | {deact} | `{receipt}` |")
    return "\n".join(rows)


def guard_block_rows():
    """First-pass P25 block pattern (from the preserved BLOCK_DIAGNOSTICS.json extraction)
    plus the D040 re-run outcome, per re-run instance."""
    rows = []
    for k in sorted(D040_RERUN):
        v = D040_RERUN[k]
        pf = v.get("p25_per_fold_verdicts") or {}
        blocked_folds = [fid for fid, x in pf.items()
                         if isinstance(x, dict) and x.get("verdict") == "BLOCK"]
        fired = sorted({f"{kind}:{feat}" for fid, x in pf.items()
                        if isinstance(x, dict)
                        for kind, feat in x.get("fired", [])})
        tol = v.get("d040_p25_tolerance_applied_folds") or []
        rows.append(f"| `{k}` | {', '.join(sorted(blocked_folds))} | "
                    f"{'; '.join(fired)} | {v.get('status')} | {', '.join(tol) or '-'} |")
    return "\n".join(rows)


log = f"""# P38_BLINDED_FIT -- EXECUTION_LOG (operational record; the node report)

> **Epistemic status (verbatim, binding):** {EPI}

Executor: P38_BLINDED_FIT (D039 dispatch, workflow wf_6972ebba-bdb), in TWO passes on the
commit recorded in the dispatch event (`{MANIFEST['code']['commit']}`; see MANIFEST.json
code.commit_provenance -- git was not invoked by this node, per standing rule 4):
first pass 2026-08-06T23:39:49Z (D039 mandates EXEC-M1..M7); D040 continuation
{datetime.now(timezone.utc).isoformat()} (ruling D040_P38_FOLD_LOCAL_P25_AND_A08:
per-fold P25 call-site wrapper; seven P25-blocked instances re-run; A08 both K elements
fitted). First-pass sealed verdicts are preserved under `.pre_D040` names, never erased.

**This file contains ZERO comparative performance numbers.** Every result of every fit is
sealed under `stage2b/SEALED_RESULTS/P38/` and was written there by the frozen runner
directly; this executor never read, printed or returned any of them. The machine-readable
mirror of this log is `SPEC.json` beside it; the sealed manifest is
`stage2b/SEALED_RESULTS/MANIFEST.json` (sha256 recorded in SPEC.json).

## 1. What executed

* **Fold policy NAMED on the record before any real fit (EXEC-M2):**
  `EXPANDING_PRIOR_SEASONS`. {MANIFEST['folds']['policy_basis']}
  The naming lands in every receipt's P27 record (`p27_fold_policy` field, verified in all
  fitted receipts).
* **Universe:** 2,982 team-game rows / 1,491 game clusters
  (`{MANIFEST['row_universe']['row_universe_digest']}`), built by
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
  `cluster_bootstrap.py` sha256 `{MANIFEST['code']['runner_sources_sha256']['runner/cluster_bootstrap.py']}`.

## 2. Fleet outcome after the D040 continuation ({len(ARMS)} sealed element directories, zero performance numbers)

| element | status | wall s | evaluable folds | deactivated folds | receipt sha256 |
|---|---|---|---|---|---|
{arm_rows()}

Counts: **{len(FITTED)} FITTED** ({len(D040_RERUN)} of them re-run under D040 after
first-pass BLOCKED_GUARD, and {len(D040_NEW)} the new A08 K elements),
**{len(GUARD_BLOCKED)} BLOCKED_GUARD remaining**,
**{len(MANDATE_BLOCKED)} BLOCKED_AT_INVOCATION_BY_RATIFIED_MANDATE**
(EXEC-M6: A20, A23 x2; PIN-A21: A21), **{len(EXCLUDED)} EXCLUDED_PRE_P38_PER_D039**
(A24: registry amendment still pending), **{len(SUPERSEDED)} SUPERSEDED_BY_D040**
(the A08_league_lag_level placeholder: its D039 exclusion condition was met and the two
K elements fitted; the original EXCLUSION_RECORD.json is untouched beside
D040_SUPERSESSION.json). Cumulative fleet wall time {MANIFEST['wall_seconds_fleet']}s
(both passes; progress.jsonl carries each pass).

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

## 4. The seven frozen-P25 guard blocks: RAISED as P38-R1 (first pass), RESOLVED by D040 (this pass)

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

First-pass block pattern and D040 re-run outcome, per instance:

| element | folds that BLOCKED (first pass) | findings fired (kind:feature) | D040 status | FOLD_UNEVALUABLE folds |
|---|---|---|---|---|
{guard_block_rows()}

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

## 5. Blocks and exclusions by ratified mandate (results)

* **A20** -- BLOCKED, EXEC-M6 contract-clock adjudication (barred universe-row clock; no
  contract-schedule input; remediation-node work). Verdict sealed.
* **A21** -- BLOCKED, PIN-A21 (D039, verbatim): the implemented game-weighted `nc` is the
  recorded-but-REJECTED construction; rebuild under a remediation node with targeted
  re-audit. Fitting it would seal a non-preregistered result. Verdict sealed.
* **A23 (both bundles)** -- BLOCKED, EXEC-M6 (as A20; rest misresolution on the 8 opener
  teams' second 2021 games measured by auditor 3). Verdicts sealed.
* **A08** -- first pass: EXCLUDED pre-P38 (D039, conditional on a non-implementer
  re-audit). Condition MET: `P37_IMPLEMENTATION_AUDIT/REAUDIT_A08.md`, verdict PASS
  (independent tie-heavy fixture; bitwise d_t parity with A09/A10; suite re-run passing).
  D040 ruled both K elements fit-eligible; this continuation FITTED `A08_K20` and
  `A08_K80` under the same discipline (contract-schedule archive constructor-bound as the
  clock, caller-supplied `pace` computed by the frozen lagged_regulation_equivalent_pin
  formula at the call site -- the EXEC-M4 obligation recorded at first pass -- named fold
  policy, sealed receipts). The original EXCLUSION_RECORD.json is untouched;
  D040_SUPERSESSION.json sits beside it.
* **A24** -- EXCLUDED pre-P38 (D039 option (a): registry-appended amendment required
  BEFORE A24 fits; not yet appended at either execution time). Record sealed. UNCHANGED
  by D040 (the ruling's A24 lane is coordinator single-writer work, not this executor's).

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

## 7. What could not be established

* The executing git commit was not re-measured in-process (standing rule 4); it is carried
  from the dispatch ledger event and must be confirmed by the coordinator/P39 against the
  task-scoped commit. The D040 continuation ran in the same working tree; its executor
  sources are re-hashed in the refreshed manifest.
* Byte-identity of the runner sources to the P36 baseline commit could not be verified
  in-node without git; the measured sha256 of every runner source, arm module, guard and
  P38 wrapper file is in the sealed manifest for P39 to check.
* A24's outcome: pending its D039 condition (registry-appended amendment, coordinator
  single-writer); nothing here prejudges it. A20/A21/A23 remediation builds are D039/D040
  remediation-node work, not this executor's.

## 8. Custody

Sealed manifest: `stage2b/SEALED_RESULTS/MANIFEST.json`. Per-arm receipts, sidecars, block
verdicts, block diagnostics, exclusion records, D040 fold-local P25 records
(`P25_FOLD_LOCAL_RECORDS.json`), first-pass preservations (`*.pre_D040.json`) and the A08
supersession note under `stage2b/SEALED_RESULTS/P38/<element>/` with sha256 in SPEC.json.
Driver/wrapper sources and their hashes: `p38_driver.py`, `p38_wrappers.py`,
`p38_run_fleet.py`, `p38_block_diagnostics.py`, `p38_finalize.py`, `p38_write_log.py`
(hashes in the manifest and SPEC.json; these sources were EXTENDED for the D040
continuation -- the frozen runner, harness, guards and arm modules were not touched).
Fleet progress: `progress.jsonl` (both passes, append-only). No frozen artifact was
modified; no git command was run; nothing outside `stage2b/SEALED_RESULTS/` and
`stage2b/P38_BLINDED_FIT/` was written.
"""

spec = {
    "schema": "player_program/p38_blinded_fit/1",
    "node": "P38_BLINDED_FIT",
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "epistemic_status": EPI,
    "authority": "D039_P37_ADJUDICATION + D040_P38_FOLD_LOCAL_P25_AND_A08",
    "fold_policy_named": "EXPANDING_PRIOR_SEASONS",
    "sealed_manifest": {
        "path": "stage2b/SEALED_RESULTS/MANIFEST.json",
        "sha256": D.sha256_file(D.SEALED / "MANIFEST.json"),
    },
    "counts": {
        "fit_eligible_arm_ids_measured": 21,
        "fit_eligible_module_instances_measured": 28,
        "instances_executed_through_runner": 24,
        "fitted": len(FITTED),
        "blocked_by_frozen_guard": len(GUARD_BLOCKED),
        "blocked_by_ratified_mandate": len(MANDATE_BLOCKED),
        "excluded_pre_p38": len(EXCLUDED),
        "superseded_by_d040": len(SUPERSEDED),
        "d040_rerun_after_first_pass_guard_block": len(D040_RERUN),
        "d040_new_a08_elements_fitted": len(D040_NEW),
        "count_contradiction": "D039/dispatch say 21 fit-eligible arms; first-pass "
                               "measured 20 (A06 never implemented). Post-D040 measured "
                               "21 arm ids / 28 instances -- numerically equal to the "
                               "D039 text but composition-different (excludes A21 per "
                               "PIN-A21, includes A08 per D040). Recorded, not "
                               "reconciled.",
    },
    "d040_continuation": {
        "authority": "D040_P38_FOLD_LOCAL_P25_AND_A08 (DECISION_LEDGER.jsonl, "
                     "2026-08-06T23:41:49Z; ruled a deterministic consequence of "
                     "D039/EXEC-M1)",
        "wrapper": "p38_wrappers.P25FoldLocalGuardView + p38_driver.p25_fold_prepass "
                   "(task-specific call-site wrapper; no frozen file edited)",
        "semantics": "fold-local P25 block -> FOLD_UNEVALUABLE with the frozen guard's "
                     "full record (receipt guard_records.p25_per_fold + "
                     "P25_FOLD_LOCAL_RECORDS.json); arm fits on remaining folds, arm AND "
                     "null identically; FINAL-design / non-excluded-fold blocks fail "
                     "closed",
        "rerun_elements": sorted(D040_RERUN),
        "a08_elements_fitted": sorted(D040_NEW),
        "a08_fit_eligibility_basis": "D039 exclusion condition met: "
                                     "P37_IMPLEMENTATION_AUDIT/REAUDIT_A08.md verdict "
                                     "PASS (non-implementer targeted re-audit)",
        "first_pass_custody": "P38_EXECUTION_SIDECAR.pre_D040.json preserved per re-run "
                              "element; BLOCK_DIAGNOSTICS.json untouched; "
                              "A08_league_lag_level EXCLUSION_RECORD.json untouched "
                              "beside D040_SUPERSESSION.json",
    },
    "arms": {k: {kk: vv for kk, vv in v.items() if kk != "receipt"} |
                ({"receipt_sha256": v.get("receipt_sha256_measured"),
                  "manifest_digest": v["receipt"]["manifest_digest"],
                  "evaluable_folds": v["receipt"]["evaluable_folds"],
                  "fold_statuses": v["receipt"]["fold_statuses"],
                  "k0_pairing": v["receipt"]["k0_pairing"],
                  "p27_overall": v["receipt"]["p27_overall"],
                  "p27_fold_policy": v["receipt"]["p27_fold_policy"]}
                 if "receipt" in v else {})
             for k, v in ARMS.items()},
    "executor_mandates": MANIFEST["executor_mandates"],
    "arm_level_pins_carried": MANIFEST["arm_level_pins_carried"],
    "raised_findings": MANIFEST["raised_findings"],
    "contradictions": [
        "21-vs-20 fit-eligible count (D039 text vs measured; A06 never implemented)",
        "PIN-A21 (remediation-node rebuild, ratified) vs dispatch fit-eligible list "
        "(executor followed the pin; A21 blocked)",
        "receipts.py run_git=True expectation at P38 vs standing rule 4 (executor chose "
        "rule 4; commit carried from the dispatch ledger event)",
        "EXEC-M7 bind path raw re-validation vs frozen R8 scope adjudication for "
        "calibration_only arms (tolerated_r8_shape, recorded per arm)",
        "runner labels P38-governor fold exclusions (including D040 FOLD_UNEVALUABLE "
        "folds) as card-pinned structural deactivations (true bases in sidecars)",
        "P38-R1: runner escalates fold-local P25 findings (including on card-deactivated/"
        "rule-collapsed folds) to whole-arm refusals -- raised for coordinator ruling; "
        "RESOLVED BY D040 at the call site (frozen runner behaviour unchanged)",
    ],
    "zero_performance_numbers": True,
    "wall_seconds_fleet": MANIFEST["wall_seconds_fleet"],
}

(D.HERE / "EXECUTION_LOG.md").write_text(log, encoding="utf-8")
(D.HERE / "SPEC.json").write_text(json.dumps(spec, indent=2, sort_keys=True),
                                  encoding="utf-8")
print("written EXECUTION_LOG.md sha256:", D.sha256_file(D.HERE / "EXECUTION_LOG.md"))
print("written SPEC.json sha256:", D.sha256_file(D.HERE / "SPEC.json"))
