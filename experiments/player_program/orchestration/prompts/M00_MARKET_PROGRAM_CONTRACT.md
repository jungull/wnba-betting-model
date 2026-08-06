# M00_MARKET_PROGRAM_CONTRACT — Freeze the market lane's taxonomy, evidence ladder, system separation and archive-use bounds

**Lane:** market_intelligence  |  **Type:** documentation  |  **Severity on failure:** A  |  **Role:** market program methodologist

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

CONTRACT. Freezes what the market lane may claim and how claims are labelled. It is a specification, not evidence: it decides no signal's fate and admits no data source. Every other market node cites it; a market claim that cannot be stated in this contract's vocabulary is not a claim this program makes.

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

**Freeze the market lane's taxonomy, evidence ladder, system separation and archive-use bounds**

Deliver exactly this, to the standard the acceptance criteria below describe. The criteria are not a summary of the mandate — they *are* the mandate.

## Acceptance criteria — your output is validated against exactly these

* the opportunity taxonomy separates true arbitrage, middles, stale-line, model-value, vendor-value and microstructure -- each with a definition, the mechanism that would make it real, and what evidence would falsify it
* the evidence ladder is frozen from MARKET_MECHANISM_SUPPORTED through PRODUCTION_ELIGIBLE, every intermediate label defined with explicit promotion criteria, and no label is skippable
* the four-system separation -- fundamental model / market-reaction / execution / decision -- is frozen with the explicit interface each system exposes to the next
* point-in-time requirements are frozen: a claim about market state at time T requires a capture record whose first-seen timestamp is at or before T; reconstructed or final-state data is never presented as point-in-time
* the BOUNDED FINAL-STATE ARCHIVE USES ruling (D023 amendment 2) is frozen: the 813-game one-snapshot-per-game archive, ruled permanently CUTOFF_UNPROVEN for timing by D016/P2B, gets its legitimate uses ENUMERATED (candidates: market/book/game universe census, join-key and schema scaffolding, long-run closing-level description, fixture data) and its permanently unsupported uses ENUMERATED (event timing, latency, lead-lag, stale windows, any 'we could have seen this at time T' claim) -- the archive is neither written off entirely nor rehabilitated
* the timestamp-uncertainty discipline (D023 amendment 4) is frozen: every future reaction-time claim carries explicit timestamp-uncertainty and vendor-latency terms, and a reaction-time figure missing either term is a defect, not a result
* the contract cites decision D023 and its four user amendments verbatim and does not relitigate D016/P2B

## Stop conditions — HALT and report rather than resolving these yourself

* a finding would require spending money, placing a wager, entering credentials, accepting scraping or licensing risk, or reading sealed possession results -- HALT and raise to a USER_REQUIRED gate, do not resolve it inside the node
* a reaction-time or timing claim cannot carry its explicit timestamp-uncertainty and vendor-latency terms (D023 amendment 4) -- report the claim as UNSUPPORTABLE rather than stating it without them
* a use of the final-state odds archive falls outside the bounded-uses enumeration of the M00 contract -- HALT and raise, do not stretch the enumeration

---

## Scope

**Read:** `experiments/`

**Write (nothing outside this):** `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/`

**Forbidden inputs:** `experiments/player_program/stage2b/SEALED_RESULTS`

**Required outputs:**

* `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/MARKET_PROGRAM_CONTRACT.md`
* `experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/TAXONOMY.json`

## Validation that will be run against your output

* `python -c "import json;json.load(open('experiments/market_program/M00_MARKET_PROGRAM_CONTRACT/TAXONOMY.json'))"`

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
