# Research contract v1 — WNBA player program

Binding operating rules for research work in this program. Version identifier:
**`RESEARCH_CONTRACT_V1`**.

Every rule here exists because its absence cost something real. This document does not re-explain
that history — see `discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md`. It states what is now required.

Precedence: where this contract and an arm's own registration disagree, the **stricter** governs.
Where this contract and a shared gate implementation appear to disagree about what a check does,
the **implementation** governs.

---

## Phase 0 — design and adversarial preflight

**No model fitting may occur before all of the following are complete.** A fit that begins before
preflight is not a result, regardless of what it produces.

1. hypothesis card **frozen**;
2. basketball mechanism **stated** — a mechanism, not a feature list;
3. candidate universe **frozen**;
4. target and denominator **frozen**;
5. **raw** feature frame audited;
6. transformation or imputation **declared explicitly**;
7. **transformed** fit frame audited;
8. chronological **fold-level** rank, conditioning, variance and missingness checks pass — pooled
   audits do not satisfy this;
9. challenger and matched **K0** established at strict pipeline parity (Layer A);
10. incumbent comparison differences **disclosed** with named reason codes (Layer B);
11. metrics, sign conventions and stop boundary **frozen**;
12. artifact, source and receipt **lineage recorded**.

### Unresolved limitation — dual-frame binding

Requirements 5 and 7 are **contractually required but not yet fully implemented**.
`gate_invocation.py` does not bind the raw pre-transformation frame, its per-column missingness
mask, or the declared imputation specification into the receipt. A caller can therefore present a
fully populated, correctly aligned, imputed design and pass every check while the null mask
survives as an ordinary value.

Until that is implemented, Phase 0 compliance on requirements 5–7 is **asserted by the author,
not demonstrated by the tooling**, and must be stated as such in the completion report. See
`GATE_INVOCATION_CONTRACT.md` §8a.

---

## Phase 1 — isolated execution

1. **One isolated worktree per parallel agent.** Not a shared worktree with disjoint file
   assignments.
2. Shared contracts, registries, ledgers and canonical artifacts are **coordinator-only**. Agents
   propose records; they never append.
3. **No unregistered post-result reformulation.** A formulation changed after seeing results is a
   new registration, not a refinement of the old one.
4. **Nulls and negative results are preserved.** A null that produces no challenger is still a
   result.
5. **No result is promoted from the discovery lane.** Discovery findings become challengers only
   through a separate registered evaluation.
6. **Amendments only for defects that can invalidate the current result.** Everything else waits
   for the next contract version.

---

## Phase 2 — integration and decision

1. The coordinator **independently verifies** commits and receipts. An agent's report identifies
   where to look; it is not evidence.
2. **Feature-design integrity and decision validity are classified separately.** A gate pass does
   not establish a valid decision.
3. **Challenger versus K0 is the primary feature-value comparison.**
4. **Challenger versus incumbent establishes operational relevance only** and cannot attribute a
   gain to features.
5. **Diagnostics are not challengers.** An oracle counterfactual is not a model.
6. **Coefficients are not forecast gains.** Never report a fitted coefficient as if it were a
   metric improvement.
7. **Rankings use only admissible evidence** — evidence whose decision validity permits the claim
   being made.
8. Shared ledgers and registries are updated **sequentially, by one writer**.
9. **No new experiment begins during synthesis.**

---

## Severity rules

Only **Severity A** interrupts unaffected parallel work. B and C never justify halting a
workstream that is not affected.

### Severity A — stop affected work immediately

* target or post-cutoff leakage
* wrong prediction universe
* unmatched comparison flexibility
* unidentified design
* invalid chronology
* altered frozen artifact
* artifact/receipt disagreement
* auditing one matrix and fitting another

### Severity B — correct before synthesis

* mislabelled metric
* ambiguous sign convention
* a coefficient described as a performance gain
* incomplete subgroup reporting
* interpretation exceeding the evidence

### Severity C — record for the next contract version

* stronger digest binding
* nonlinear dependency detection
* report-format improvements
* code cleanup not affecting the current result

---

## Communication protocol

### Status vocabulary — use these words, and only with their evidence

| status | means |
|---|---|
| `REQUESTED` | instruction sent, not started |
| `RUNNING` | execution started |
| `LANDED` | output returned or files written, **not independently checked** |
| `VERIFIED` | coordinator reproduced the critical checks |
| `COMMITTED` | accepted files committed |
| `SCIENTIFICALLY_ACCEPTED` | evidence and interpretation approved |
| `SUPERSEDED` | replaced by a corrected result |
| `INVALID` | cannot support its original conclusion |

**Do not use "done", "closed", "accepted", or "no rework needed" without the corresponding
evidence state.** `LANDED` is not `VERIFIED`. Queueing an instruction is not compliance.

### Progress updates contain only

* status
* one consequential new fact
* impact
* action
* evidence path or commit

Do **not** narrate routine commands, transient debugging, or failed test assumptions — unless the
failure reveals a methodological defect, in which case it is the consequential fact.

### On receiving a correction or amendment

* state the exact delta
* do **not** repeat requirements already implemented
* identify which outputs are affected
* identify whether rework is **actually** required
* preserve the existing stop boundary unless explicitly changed

---

## Task specification versioning

Every authorized task carries a specification version, e.g. **`TURNOVER_DW2_WS3_v1`**.

Amendments are written as explicit deltas:

| field | content |
|---|---|
| previous version | `..._v1` |
| new version | `..._v2` |
| changed requirements | only what changed |
| affected workstreams | which are impacted |
| prior output still admissible? | yes / no / partially, with reasons |

**Do not continuously append long instructions to an unnamed task.** An instruction stream with no
version identifier cannot be audited, and work completed under an earlier state of it cannot be
distinguished from work completed under the current one.

---

## Artifacts

| artifact | path |
|---|---|
| program state (derived) | `PROGRAM_STATE.json` |
| state generator | `build_program_state.py` |
| task card template | `templates/EXPERIMENT_TASK_CARD.md` |
| completion report template | `templates/EXPERIMENT_COMPLETION_REPORT.md` |
| gate invocation contract | `GATE_INVOCATION_CONTRACT.md` |
| wave summary | `discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md` |
| audit matrix | `discovery_wave_1/FINAL_AUDIT_MATRIX.json` |

`PROGRAM_STATE.json` is **derived, never hand-edited**. Re-run the generator.

### Scope of authority

`PROGRAM_STATE.json` is **authoritative for program and scientific state** — frozen incumbent,
canonical artifact hashes, workstream classifications, wave status, open gaps, stop boundary,
next decision.

It is **not authoritative for live repository state.** Its `generated_from` block is
**provenance**: it describes the repository as it stood when the state was generated, which is
necessarily the **parent** of the commit carrying the file — neither that commit's hash nor its
tree status exists until after the file is written.

**Live branch, HEAD and working-tree status must be obtained by running
`build_program_state.py`, or its `--check` command, against the current repository.** Never quote
`generated_from.head` as the current HEAD.
