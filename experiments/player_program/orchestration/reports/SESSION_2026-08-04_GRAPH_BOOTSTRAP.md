# Session report — graph bootstrap and remediation waves, 2026-08-04

Companion to the auto-generated [`CURRENT_STATUS.md`](CURRENT_STATUS.md) (counts) and the
append-only ledgers (`GRAPH_EVENTS.jsonl`, `DECISION_LEDGER.jsonl`). This is the narrative:
what happened, what it means, what is next. Every claim here is backed by a ledger entry or a
commit; where a figure was relayed from an agent rather than reproduced by the coordinator, it
says so.

## Where the program stands

The autonomous graph is live: **65 nodes across six lanes**, 41 passed, 1 in verification,
2 retrying, 13 blocked only by the normal critical-path ordering, 2 waiting on the user by
design (champion replacement; shared-schema adoption). Five waves — 47 agent runs plus
verifiers — have executed with **zero frozen-artifact violations**: all 11 pinned hashes
(both evidence packets, the three V2 source outputs, generation order, stop condition, and
the four shared gates) still rederive exactly.

The possession critical path now stands at: every S1–S9 remediation node landed and
integrated → **next node is `P30_EVIDENCE_PACKET_V3`**, which becomes READY the moment the
P2B verifier passes. After V3: final ideation wave → candidate synthesis → preregistration →
red team → frozen task cards → blinded implementation → sealed fit → integrity check →
adjudication. Fitting stays locked behind the preregistration gates; nothing has peeked at
comparative performance.

## The findings that matter most

1. **The shared feature gate cannot enforce the duration prohibition** (D005). Reproduced by
   the coordinator from scratch: `feature_gate.audit` passes raw `game_minutes`, passes the
   `master_team.minutes` 5× shape, and passes a 100%-missing column with an empty findings
   list (cause located at `feature_gate.py:152`). Three independent sources converged on this
   (P22, P29, U10). The gate is frozen and stays frozen — the task-specific wrappers built in
   this session are the remedy, and V3 carries the corrected enforcement claim.

2. **The fold count is five, not six** (D006). The packet prose is ambiguous; the
   implementation is not, and the implementation governs. S7's "four of six folds" is a
   statement about seasons and gets restated in V3.

3. **`K0_MATCHED` is per-arm, and the packet's single control is unestimable as written**
   (D007). Two independent derivations (S6 ruling; S9 from the estimator source), plus P27's
   measurement that no training fold supports the full tier ladder under a 10-cluster floor.
   V2 stays frozen; V3 carries the itemised supersession.

4. **The market-odds family stays excluded, but for the right reason now** (D016, verification
   pending). The packet's stated ground — "capture begins 2026-07-31" — is factually false: a
   game-joined archive with snapshots from 2022-05-21 exists and is the parent of
   `tip_times.csv`. But the archive is a **single retrospective harvest** — exactly one
   snapshot per game across all 813 games, downloaded in a 571-second burst on 2026-07-30 —
   so it is permanently `CUTOFF_UNPROVEN`. Coordinator reproduced all three measurements.
   The separate question of whether a market feature belongs in a possession model at all is
   explicitly left open.

5. **Injury history contributes zero cutoff-valid rows in every fold** (P24); **38 of 48
   possession columns are realised target-game outcomes** (P2A); **the universe excludes the
   2021 opening day**, so every cold-start coverage figure is flattered by construction
   (D010, coordinator-confirmed: games `1022100001–1022100004`, all 2021-05-14).

6. **Two defects in the orchestration layer itself**, found by a node it scheduled and fixed
   (D013): the blinded-fit prompt rendered "Forbidden inputs: _none_", and the
   audit-independence check silently skipped the runner→integrity edge. Neither was caught by
   the engine's own 23-check suite.

## Process corrections worth remembering

- **Four missing reports were a harness refusal, not agent failure** (D012). The harness
  rejects subagent writes of report files; the workaround is verified and now rides in every
  brief. P25's original report prose was never persisted and is unrecoverable — its
  remediation is an independent write-up, not a restoration.
- **A manufactured negative survived one node and was caught by another** (D008). D10 declared
  coaching data absent; D12, independently, found it. The coordinator's own first check *also*
  false-negatived (pandas `StringDtype` silently defeating a string match) — the strongest
  argument this session produced for paying twice for independent coverage of the same bytes.
- **13 documented future tracks have no estimand** (D014). G04 refused to invent them.
  Documentation of machinery is not a target contract.

## Standing configuration

- **Model tiering** (D015, `GRAPH_POLICY.md` §9): highest tier for contract interpretation,
  K0 design, preregistration/red-team, critical-path verification, adjudication; `sonnet` for
  documentation extraction and off-path checking; `haiku` for mechanical assembly. A Severity A
  verifier never runs below the tier of the work it verifies.
- **Remote policy** (D017, `GRAPH_POLICY.md` §10): `player-model-program` pushes to `origin`
  after each integration cycle, per user authorization of 2026-08-04. No force-push, no `main`,
  no history rewrite.

## Open items needing nothing from the user yet

P2B independent verification (running at session model); F15/F16 target-contract drafts
(retry 1 after usage-limit deaths); then V3 assembly. The two `USER_REQUIRED` gates remain
far downstream: replacing Arm D, and adopting any shared-schema change out of the isolated
operations lane. A live capture gap on the 2026-08-05/06 slates was surfaced to the user in
session (D004) and deliberately not fixed here — it lives in a shared contract on another
branch.
