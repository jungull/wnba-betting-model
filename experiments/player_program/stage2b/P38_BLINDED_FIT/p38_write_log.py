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
    rows = []
    for k in sorted(GUARD_BLOCKED):
        v = GUARD_BLOCKED[k]
        pf = v.get("p25_per_fold_verdicts") or {}
        blocked_folds = [fid for fid, x in pf.items()
                         if isinstance(x, dict) and x.get("verdict") == "BLOCK"]
        fired = sorted({f"{kind}:{feat}" for fid, x in pf.items()
                        if isinstance(x, dict)
                        for kind, feat in x.get("fired", [])})
        rows.append(f"| `{k}` | {', '.join(sorted(blocked_folds))} | "
                    f"{'; '.join(fired)} |")
    return "\n".join(rows)


log = f"""# P38_BLINDED_FIT -- EXECUTION_LOG (operational record; the node report)

> **Epistemic status (verbatim, binding):** {EPI}

Executor: P38_BLINDED_FIT (D039 dispatch, workflow wf_6972ebba-bdb). Executed
{datetime.now(timezone.utc).isoformat()} on the commit recorded in the dispatch event
(`{MANIFEST['code']['commit']}`; see MANIFEST.json code.commit_provenance -- git was not
invoked by this node, per standing rule 4).

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

## 2. Fleet outcome (27 sealed entries, zero performance numbers)

| element | status | wall s | evaluable folds | deactivated folds | receipt sha256 |
|---|---|---|---|---|---|
{arm_rows()}

Counts: **{len(FITTED)} FITTED**, **{len(GUARD_BLOCKED)} BLOCKED_GUARD** (frozen P25 guard,
see section 4), **{len(MANDATE_BLOCKED)} BLOCKED_AT_INVOCATION_BY_RATIFIED_MANDATE**
(EXEC-M6: A20, A23 x2; PIN-A21: A21), **{len(EXCLUDED)} EXCLUDED_PRE_P38_PER_D039**
(A08 re-audit pending; A24 registry amendment pending). Fleet wall time
{MANIFEST['wall_seconds_fleet']}s.

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

## 4. The seven frozen-P25 guard blocks (results, and a RAISED finding)

The frozen runner audits EVERY fold's design with P22/P25 in its bundle loop, and a P25
blocking finding in ANY single fold fails the whole arm closed. Seven instances blocked
that way; the executor then re-invoked the frozen P25 wrapper per fold with the runner's
own argument pins (diagnostics sealed per arm in `BLOCK_DIAGNOSTICS.json`; full guard
records inside, never printed):

| element | folds that BLOCK | findings fired (kind:feature) |
|---|---|---|
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

**RAISED, not resolved in-node (P38-R1):** this is R-F1's whole-arm-vs-per-fold shape in
the runner's P25 branch, which P37 did not adjudicate and EXEC-M1 (worded for P27 only)
does not cover. No ratified mandate authorises tolerating P25 findings at the call site,
so the executor held the fail-closed line and the blocks stand as sealed results. A
coordinator ruling (an EXEC-M1 analogue for the runner's per-fold P22/P25 audits, or
remediation nodes) is required before these seven can fit. Fail-closed direction: this can
only wrongly kill, never wrongly promote.

## 5. Blocks and exclusions by ratified mandate (results)

* **A20** -- BLOCKED, EXEC-M6 contract-clock adjudication (barred universe-row clock; no
  contract-schedule input; remediation-node work). Verdict sealed.
* **A21** -- BLOCKED, PIN-A21 (D039, verbatim): the implemented game-weighted `nc` is the
  recorded-but-REJECTED construction; rebuild under a remediation node with targeted
  re-audit. Fitting it would seal a non-preregistered result. Verdict sealed.
* **A23 (both bundles)** -- BLOCKED, EXEC-M6 (as A20; rest misresolution on the 8 opener
  teams' second 2021 games measured by auditor 3). Verdicts sealed.
* **A08** -- EXCLUDED pre-P38 (D039: remediation confirmed, fit-eligibility pending
  non-implementer re-audit). Record sealed, with the EXEC-M4 pace-column obligation noted
  for its entry.
* **A24** -- EXCLUDED pre-P38 (D039 option (a): registry-appended amendment required
  BEFORE A24 fits; not yet appended at execution time). Record sealed.

## 6. Contradictions found (reported, never silently reconciled)

1. **"21 fit-eligible arms" (D039 ruling text, dispatch, graph events) vs the measured
   count of 20.** 22 arm ids are implemented under P36 (A06 was never implemented --
   D021 amended it to INADMISSIBLE-UNTIL-RECEIPTED); 22 - A08 - A24 = 20 fit-eligible arm
   ids = 26 fit-eligible module instances. The likely arithmetic source of "21" is
   D026's "23 fit-eligible" (26 - A01/A04/A19) minus 2, which overlooks A06. This node
   executed against the measured set: 22 instances run, 4 instances mandate-blocked
   (A20, A21, A23 x2), matching 26.
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

## 7. What could not be established

* The executing git commit was not re-measured in-process (standing rule 4); it is carried
  from the dispatch ledger event and must be confirmed by the coordinator/P39 against the
  task-scoped commit.
* Byte-identity of the runner sources to the P36 baseline commit could not be verified
  in-node without git; the measured sha256 of every runner source, arm module, guard and
  P38 wrapper file is in the sealed manifest for P39 to check.
* Whether the seven P25-blocked arms would pass under a per-fold reading (P38-R1) was NOT
  computed: producing their fitted results without a ratified mandate would create sealed
  numbers whose admissibility is undecided. Only guard verdicts were re-measured.
* A08/A24 outcomes: pending their D039 conditions; nothing here prejudges them.

## 8. Custody

Sealed manifest: `stage2b/SEALED_RESULTS/MANIFEST.json`. Per-arm receipts, sidecars, block
verdicts, block diagnostics and exclusion records under `stage2b/SEALED_RESULTS/P38/<element>/`
with sha256 in SPEC.json. Driver/wrapper sources and their hashes: `p38_driver.py`,
`p38_wrappers.py`, `p38_run_fleet.py`, `p38_block_diagnostics.py`, `p38_finalize.py`,
`p38_write_log.py` (hashes in the manifest and SPEC.json). Fleet progress: `progress.jsonl`.
No frozen artifact was modified; no git command was run; nothing outside
`stage2b/SEALED_RESULTS/` and `stage2b/P38_BLINDED_FIT/` was written.
"""

spec = {
    "schema": "player_program/p38_blinded_fit/1",
    "node": "P38_BLINDED_FIT",
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "epistemic_status": EPI,
    "authority": "D039_P37_ADJUDICATION",
    "fold_policy_named": "EXPANDING_PRIOR_SEASONS",
    "sealed_manifest": {
        "path": "stage2b/SEALED_RESULTS/MANIFEST.json",
        "sha256": D.sha256_file(D.SEALED / "MANIFEST.json"),
    },
    "counts": {
        "fit_eligible_arm_ids_measured": 20,
        "fit_eligible_module_instances_measured": 26,
        "instances_executed_through_runner": 22,
        "fitted": len(FITTED),
        "blocked_by_frozen_guard": len(GUARD_BLOCKED),
        "blocked_by_ratified_mandate": len(MANDATE_BLOCKED),
        "excluded_pre_p38": len(EXCLUDED),
        "count_contradiction": "D039/dispatch say 21 fit-eligible arms; measured 20 "
                               "(A06 never implemented). Recorded, not reconciled.",
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
        "runner labels P38-governor fold exclusions as card-pinned structural "
        "deactivations (true bases in sidecars)",
        "P38-R1: runner escalates fold-local P25 findings (including on card-deactivated/"
        "rule-collapsed folds) to whole-arm refusals -- raised for coordinator ruling",
    ],
    "zero_performance_numbers": True,
    "wall_seconds_fleet": MANIFEST["wall_seconds_fleet"],
}

(D.HERE / "EXECUTION_LOG.md").write_text(log, encoding="utf-8")
(D.HERE / "SPEC.json").write_text(json.dumps(spec, indent=2, sort_keys=True),
                                  encoding="utf-8")
print("written EXECUTION_LOG.md sha256:", D.sha256_file(D.HERE / "EXECUTION_LOG.md"))
print("written SPEC.json sha256:", D.sha256_file(D.HERE / "SPEC.json"))
