# M24_STAKING — Staking policy specification: sizing, exposure and drawdown rules

**Lane:** market_intelligence  |  **Type:** documentation  |  **Severity on failure:** B  |  **Role:** staking policy author

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

DECISION-SYSTEM SPECIFICATION. A staking policy is a frozen rule set evaluated in shadow before any real-money question is even well-posed. This node specifies and backtests-in-shadow; activating any policy with money is USER_REQUIRED and is not this node's decision.

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

**Staking policy specification: sizing, exposure and drawdown rules**

Deliver exactly this, to the standard the acceptance criteria below describe. The criteria are not a summary of the mandate — they *are* the mandate.

## Acceptance criteria — your output is validated against exactly these

* sizing rules (including any Kelly fraction) are stated with their inputs' uncertainty explicitly propagated
* exposure caps per game, market, book and day are explicit
* drawdown and stop rules are frozen before evaluation on the shadow ledger
* the policy is evaluated only against the M23 shadow ledger under M21/M22 assumptions
* real-money activation is stated to be USER_REQUIRED and outside this node

## Stop conditions — HALT and report rather than resolving these yourself

* a finding would require spending money, placing a wager, entering credentials, accepting scraping or licensing risk, or reading sealed possession results -- HALT and raise to a USER_REQUIRED gate, do not resolve it inside the node
* a reaction-time or timing claim cannot carry its explicit timestamp-uncertainty and vendor-latency terms (D023 amendment 4) -- report the claim as UNSUPPORTABLE rather than stating it without them
* a use of the final-state odds archive falls outside the bounded-uses enumeration of the M00 contract -- HALT and raise, do not stretch the enumeration

---

## Scope

**Read:** `experiments/`

**Write (nothing outside this):** `experiments/market_program/M24_STAKING/`

**Forbidden inputs:** `experiments/player_program/stage2b/SEALED_RESULTS`

**Required outputs:**

* `experiments/market_program/M24_STAKING/REPORT.md`
* `experiments/market_program/M24_STAKING/SPEC.json`

## Validation that will be run against your output

* `python -c "import json;json.load(open('experiments/market_program/M24_STAKING/SPEC.json'))"`

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
