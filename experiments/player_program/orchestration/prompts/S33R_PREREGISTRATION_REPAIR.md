# S33R_PREREGISTRATION_REPAIR — Disposition every S34 Severity A/B finding; emit the repaired card set for freeze

**Lane:** score  |  **Type:** documentation  |  **Severity on failure:** A  |  **Role:** preregistration repair author + independent re-verifier

> This file is GENERATED from the node's contract in `PROGRAM_GRAPH.json`. It is the auditable
> record of exactly what this node's agent was told. Do not edit it by hand.

---

## Standing rules — these override any instinct to be helpful

1. **Frozen bytes govern over prose.** Where a document and an artifact hash disagree, the hash
   wins. Never silently reconcile a contradiction — report it.
2. **You may write ONLY inside your declared write scope** (below). An agent may not broaden its
   own write scope. Writing outside it fails the node at integration.
3. **Do not modify any frozen artifact.** In particular: `feature_gate.py`, `comparison_gate.py`,
   `gate_invocation.py`, `receipt_integrity.py`, the arm registry, `PROGRAM_STATE.json`, the
   Stage 2A evidence packets and hypothesis files, anything under the canonical `*_v1`/`*_v2`
   artifact directories, and anything constituting Arm D (`D_ewma_shrunk`). Enforcement belongs at
   the **call site** — if a check is missing, write a task-specific wrapper, never edit a shared gate.
4. **Do not run git.** Write files. The coordinator makes the task-scoped commit after validating
   your output. This is how concurrent nodes avoid contending for the git index.
5. **You do not mark your own work accepted.** A separate verifier context validates it. Report
   what you found, including what you could not establish.
6. **Measure, do not assert.** Every number in your output must come from code you actually ran
   against the actual artifact. If you could not measure something, say so explicitly and say why.
   A plausible-sounding figure you did not compute is a defect, not a contribution.
7. **Preserve nulls and negative results.** "This mechanism does not exist in the data" is a
   finding. Do not manufacture a positive.
8. **No performance peeking.** You may run unit, synthetic, identity and schema tests. You may NOT
   inspect comparative historical performance of any challenger, and you may not read anything
   under `experiments/player_program/stage2b/SEALED_RESULTS/`.

## Epistemic status of your output

REPAIR. Dispositions S34's findings against the REVIEWED draft, which stays byte-frozen and auditable. Emits SPEC_V2.json; authorizes nothing to fit.

Write this verbatim into your report. It bounds what your output may later be cited for.

---

## Scientific state you are working inside

* **Incumbent, frozen:** `D_ewma_shrunk`, K=200, α=0.1, operational team MAE ≈ 2.9675, intrinsic
  ≈ 2.896. No challenger has been promoted. Do not retune or alter it.
* **Primary target, settled:** `REGULATION_EQUIVALENT_TEAM_OFFENSIVE_POSSESSIONS`. Realized
  duration may normalize a *completed-game historical outcome* only. Current-game realized
  overtime, `game_minutes`, duration, overtime periods, and any exact or approximate same-game
  surrogate for those are **prohibited from the prediction path**.
* **Universe:** 2,982 team-game rows over 1,491 game clusters. Report both. Games must never be
  split across folds or cluster-bootstrap draws.
* **Controls:** `K0_FLAT` is diagnostic only. `K0_MATCHED` is authoritative and is **per-arm**.
* **Downstream:** the operational scorer pairs regulation-equivalent projected exposure with raw
  full-game turnovers. This mismatch is documented and the scorer is **frozen**. Possession
  candidates are selected on the primary possession target first; downstream turnover results are
  secondary and may never rescue a candidate that fails or worsens the primary target.
* **The V2 halt carries NINE findings, S1–S9.** S8 and S9 were raised by the estimator source that
  returned after the halt was declared. Read `stage2a/V2_STOP_CONDITION.json` for all nine.

---

## Your mandate

**Disposition every S34 Severity A/B finding; emit the repaired card set for freeze**

Deliver exactly this, to the standard the acceptance criteria below describe. The criteria are not a summary of the mandate — they *are* the mandate.

## Acceptance criteria — your output is validated against exactly these

* A1 game_date cutoff: replace the named S37 promotion measurement with one that is INDEPENDENT of the P2B-barred market archive, COVERS 2021, and tests reschedule directly (per-game first-observed-commence vs settled date, n_commence_variants>1 on the 36 flagged games), plus an explicit receipt enumerating the 272 unwitnessed clusters (67 pooled-test). If no admissible witness exists, say so and withdraw or re-card every arm whose lineage depends on it - do not promote the field under an excluded channel
* A2 deletion-invariance: register the S34 identity-set extension S30 section 1 requires - the five byte-pinned frozen-composite prediction columns and projected_team_off_possessions, each justified as a frozen, hash-pinned, strictly-lagged pregame construction - AND extend every features_lineage entry from artifact grain to consumed-source-COLUMN grain so the receipt has a per-source classification to run against; the extension is recorded in SPEC_V2 and is itself reviewable
* A3 SC01 stratum: pin ONE predicate with its matching count (max<=12 -> 472, or min<=12 -> 516) and correct the incoherent reconciliation; the kill terminates all three SC01 elements so the ambiguity is arm-fatal if left
* A4 SC08::E3: either make the K0's Brier against the frozen p_home column a MANDATORY sealed receipt with a preregistered below-floor rule forcing the BELOW-FLOOR NULL label and S40->S42 routing, or refit SC08's mean map to the win outcome; and move the J3 justification out of the report into the binding SPEC records
* every Severity B dispositioned: B1 R5 key-vs-name mismatch on SC06 (and the false PASS in self_validation), B2 the two undeclared strictly-prior row bases, B3 SC12's kill that cannot fire, B4 SC10's unlineaged orthogonalization covariate, B5 SC02's threshold-less retirement kill, B6 the uncarried SC10<->SC12 family dispute, B7 SC05's unregistered disputed assignment, B8 SC09's calibration_freedom declaration contradicting its own treatment
* the four Severity C notes are answered or explicitly accepted with reasons
* the reviewed S33 draft is NOT edited - SPEC_V2 supersedes it and both remain in the repo
* an independent re-verifier confirms each A/B finding is closed against the actual bytes before S35

## Stop conditions — HALT and report rather than resolving these yourself

* a finding would change the cycle-2 estimands (E1/E2/E3), the K0 structure, the inference structure, the declared universe, the cutoff-valid feature set or the leakage status -- HALT and raise, do not resolve it inside the node

---

## Scope

**Read:** `experiments/player_program/`, `experiments/market_program/`

**Write (nothing outside this):** `experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/`

**Forbidden inputs:** `experiments/player_program/stage2b/SEALED_RESULTS`, `experiments/player_program/stage3_score/SEALED_RESULTS`

**Required outputs:**

* `experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/SPEC_V2.json`
* `experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/REPORT.md`
* `experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/S34_DISPOSITION.md`

## Validation that will be run against your output

* `python -c "import json;json.load(open('experiments/player_program/stage3_score/S33R_PREREGISTRATION_REPAIR/SPEC_V2.json'))"`

---

## Report format

Write `REPORT.md` as prose a scientist can audit, and the machine-readable file as structured
data. The report must contain:

* the epistemic-status line above, verbatim;
* what you measured, with the exact command or script that produced each number;
* what you could **not** establish, and why;
* every contradiction you found between documents, or between a document and the bytes;
* anything you believe trips a stop condition, stated plainly rather than worked around.

Do not narrate routine commands or transient debugging. Report the consequential facts.
