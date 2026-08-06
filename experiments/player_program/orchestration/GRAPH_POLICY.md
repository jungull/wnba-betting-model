# Graph policy — autonomous program graph for the WNBA player model

Version: `GRAPH_POLICY_V1`. Governs the orchestration layer only. It does **not** amend
`RESEARCH_CONTRACT_V1`, `GATE_INVOCATION_CONTRACT.md`, or any frozen scientific artifact — where
this policy and a scientific contract appear to disagree, the **scientific contract governs** and
the disagreement is recorded in `DECISION_LEDGER.jsonl` rather than silently reconciled.

---

## 1. Source-of-truth hierarchy

Applied in this order. A lower tier never overrides a higher one.

1. frozen artifact bytes and rederived hashes
2. committed receipts and manifests
3. `RESEARCH_CONTRACT_V1.md`
4. `PROGRAM_STATE.json`
5. accepted task cards and decision records
6. accepted scientific rulings recorded in Stage 1B and Stage 2A artifacts
7. project updates and prose handoffs
8. task-specific rulings recorded in `DECISION_LEDGER.jsonl`

**Where prose conflicts with frozen bytes, the bytes govern.** Never silently reconcile a
contradiction; append it to `DECISION_LEDGER.jsonl` with both readings preserved.

---

## 2. What the committed graph is

| file | role | mutability |
|---|---|---|
| `PROGRAM_GRAPH.json` | node definitions and dependency structure | append/amend, never delete a node id |
| `GRAPH_EVENTS.jsonl` | historical ledger of everything that happened | **append-only, never rewritten** |
| `GRAPH_STATE.json` | generated current snapshot | **derived, never hand-edited** |
| `DECISION_LEDGER.jsonl` | coordinator rulings and preserved contradictions | append-only |
| `ARTIFACT_LEDGER.jsonl` | path → sha256 → observed-at-event | append-only |
| `FILE_OWNERSHIP.json` | generated write-ownership map | derived |

`GRAPH_STATE.json` must be **deterministically reconstructable** from the graph definition, the
append-only events, repository state and artifact hashes. `graphctl.py state --check` rebuilds it
and fails on any divergence. Runtime scratch lives under `.claude/graph_runtime/` and is ignored;
nothing there is authority.

**Never rewrite history to make a failed attempt disappear.** A failed node keeps its FAILED
event; remediation is a *new* node that declares the failure as its parent finding.

---

## 3. Frozen paths — no graph node may write here

Enforced by `scripts/frozen_path_guard.py`, which is invoked by `integrate_node.py` before any
merge and fails closed.

* `experiments/player_program/possessions_v1/`, `possessions_v2/`, `projected_exposure_v1/`,
  `event_contract_v1/`, `turnover_targets_v1/`, `turnover_p1_v1/`, `turnover_p2_v1/`,
  `p3_downstream_v1/`, `fits_v1/`, `possession_features_v1/`, `validation_v1/`
* `experiments/player_program/arm_registry.jsonl`, `registry.jsonl` — **append-only**; existing
  records may never be edited. Appending requires a passed preregistration gate.
* `experiments/player_program/feature_gate.py`, `comparison_gate.py`, `gate_invocation.py`,
  `receipt_integrity.py` — shared contracts
* `experiments/player_program/discovery_wave_1/`
* `experiments/player_program/stage2a/EVIDENCE_PACKET.json`,
  `EVIDENCE_PACKET_V2.json`, `V2_HYPOTHESES_*.md`, `V2_GENERATION_ORDER.json`,
  `V2_STOP_CONDITION.json`, `GENERATION_ORDER.json`, `HYPOTHESES_*.md`, `SYNTHESIS.md`
* everything constituting **Arm D** (`D_ewma_shrunk`): source, configuration and outputs
* `PROGRAM_STATE.json` — derived; regenerate via `build_program_state.py`, never hand-edit

A task-specific wrapper is the correct way to add enforcement. **Do not modify a frozen shared
gate to add a check** — write the check at the call site.

---

## 4. Isolation

**Writable engineering nodes.** One worktree per node, branch `graph/<node_id>`, pinned base
commit, exclusive file ownership. Two live nodes may never own the same file. `dispatch_ready.py`
refuses to emit a dispatch set containing an ownership collision.

**Scientific ideation nodes.** Independence is *structural*, not promised. The node runs against
an isolated directory containing only the allowed frozen packet and its prompt. The repository is
not exposed. Other hypothesis files, syntheses and coordinator ideas are not exposed. Raw output is
frozen and hashed **before** any other source can read it.

**Audit nodes.** An audit node may not be the implementation node whose work it audits. Enforced
by `validate_graph.py`: an audit node listing implementation node `X` in `dependencies` must not
share `X`'s `agent_prompt_path` or `owned_files`.

**Retries and replacements.** A retry is labelled `RETRY` and is *not* a new independent source. A
replacement for a lost agent is labelled `REPLACEMENT`. Neither inflates evidence-source counts.

---

## 5. Automatic advancement

A node passes automatically only when **all** hold:

1. every declared output exists;
2. every input hash rederives to its frozen value;
3. every `validation_command` exits 0;
4. every `acceptance_criterion` is machine-verifiable and satisfied;
5. no Severity A issue remains open against it;
6. no forbidden path changed;
7. an **independent verifier context** agrees.

The coordinator may decide without asking the user when the governing contract resolves it, when
it is a deterministic consequence of an accepted ruling, when it narrows scope to avoid leakage or
unverified data, when it removes a redundant or unidentified candidate, when it rejects an arm for
failing predeclared integrity checks, or when it advances an experiment whose frozen
preregistration and implementation audits pass. Consequential coordinator gates use **at least two
independent reviewers**, and **disagreement is preserved**, never averaged away.

Severity B failures automatically spawn a remediation node, at most two cycles unless a new
mechanism is involved. Severity C is documented and scheduled without halting unrelated work.

---

## 6. `USER_REQUIRED` — the only stopping points

Stop, and ask exactly one concrete question with the evidence needed to answer it, when a decision
would:

* change the primary estimand or target;
* weaken a scientific gate after any relevant outcome was observed;
* modify a frozen canonical artifact;
* modify Arm D or replace the champion;
* accept known leakage or an unresolved Severity A risk;
* alter an existing registry record;
* make an external deployment, push or financial commitment;
* choose between scientifically equivalent alternatives on a business preference not documented in
  the repository.

Everything else proceeds. In particular the coordinator does **not** ask permission to create
worktrees, make task-scoped commits, run tests, perform read-only audits, remediate a confirmed
implementation defect, advance a fully satisfied gate, retry a failed agent, launch an unblocked
node, update graph metadata, freeze a preregistration whose reviews all passed, or execute an
already-frozen preregistered experiment.

---

## 7. Blinding

Candidate-performance results stay **sealed** until V3 is frozen, hypotheses are frozen, families
are deduplicated, multiplicity treatment is frozen, task cards are frozen, formulas are frozen,
feature lineages are frozen, `K0_MATCHED[arm]` is frozen for every arm, implementation code is
frozen, and all integrity audits pass.

Implementation nodes may run unit, synthetic, identity and schema tests, and dry runs that do not
reveal comparative historical performance. They may **not** inspect challenger performance. The
runner writes into a sealed result directory; a separate result-integrity node verifies commit,
data hashes, row universe, folds, `K0` pairing, seeds and output completeness; only then may a
separate adjudication node open results.

---

## 8. Git policy

**Allowed without asking:** local worktrees, local branches, task-scoped commits, merging a
validated task branch into `player-model-program`, appending graph and evidence records, appending
new registry records after the preregistration gate passes.

**Prohibited:** force push, force reset, history rewrite, deleting another actor's work, editing an
existing registry record, modifying frozen canonical bytes, modifying Arm D, pushing to a remote,
deploying, changing production credentials, spending money, modifying shared contracts or frozen
gates.

Integration requires: clean dependency base, changed-file scope check, test pass, artifact-hash
reconciliation, no unexpected file ownership, no forbidden-path change, and an explicit merge
event.

---

## 9. Model tiering — match the agent to the task

Dispatch cost is real. Every agent launch declares a model tier and a reasoning effort, chosen
by what the node *is*, not by what capacity happens to be free:

| tier | use for |
|---|---|
| **highest available** (inherit session model, high effort) | target and contract interpretation; K0 design; preregistration authoring and red-team review; adversarial verification on the possession critical path; final adjudication; graph mutation after a scientific blocker |
| **mid** (`sonnet`, medium effort) | documentation extraction with refusal discipline; target-contract drafts; citation-checking verification off the critical path; data cleaning with fixed rules; UI scaffolding |
| **fast** (`haiku`, low effort) | file inventory; mechanical reformatting; report assembly from existing structured data with no judgement calls |

Two rules that override the table:

1. **Verification of a Severity A node never runs below the tier of the work it verifies.**
   A cheap verifier signing off on expensive analysis is how a plausible-but-wrong finding
   survives.
2. **Do not launch redundant agents merely because capacity exists.** An additional agent must
   supply a distinct expertise lens, an independent audit, genuinely parallel implementation, or
   fault isolation.

## 10. Remote policy

The program branch `player-model-program` is pushed to `origin` after each integration cycle
(user authorization 2026-08-04, superseding this policy's original no-push rule — see decision
`D017`). Constraints that remain in force: never force-push, never push `main` or any branch not
owned by this graph, never rewrite published history. A push is a backup of committed work, not a
deployment.

**Pushes require a quiescent tree** (`D018`). The repository's pre-push hook runs `verify_all`
(~10 min, 35 checks), and `test_run_player_oof_v14` check 10 asserts the dirty-path count is
stable across its own runtime — a deliberate refusal to certify a tree that changed while being
measured. A push attempted while agents are writing fails that check *by design*. Therefore: a
push happens only after the running wave has completed, its outputs are committed, and no agent
holds a write scope in the worktree. Never bypass the hook (`--no-verify` is prohibited); if the
gate fails, the tree was not quiescent or something real broke — investigate, never override.

## 11. Severity and blocking

A blocker in one lane blocks **descendants in that lane**, not independent work elsewhere. Severity
A stops affected descendants. Severity B creates a remediation node. Severity C is scheduled.

Do not report "waiting" while unrelated nodes remain READY.
