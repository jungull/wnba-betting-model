# DOCUMENT_INDEX — every authoritative document, contract, task card, ledger, receipt and frozen artifact

**Node:** `G02_DOCUMENT_INDEX`  |  **Lane:** governance  |  **Type:** audit

**Epistemic status of this output, verbatim from the node brief:**

> VERIFIED_READ_ONLY_DERIVATION. A map of what exists with hashes. Carries no scientific judgement about whether any indexed claim is correct.

This index says what exists, what its bytes hash to, what the document says its own role is, whether the program's own frozen-path rules classify it as frozen, and whether it is generated or hand-maintained. It does **not** say whether anything any of these documents claims is true.

## Snapshot identity

| | |
|---|---|
| generated at (UTC) | `2026-08-04T19:59:37Z` |
| worktree | `C:/Users/jgallagher/wnba-betting-model/.claude/worktrees/player-model-program` |
| branch | `player-model-program` |
| HEAD at start of build | `b6228a17d974691e21bdc0afa8226ce613461eac` |
| HEAD at end of build | `b6228a17d974691e21bdc0afa8226ce613461eac` |
| HEAD moved during build | `False` |
| hash algorithm | sha256 over raw file bytes |
| frozen-rule authority | `experiments/player_program/orchestration/scripts/graph_lib.py (FROZEN_PREFIXES, FROZEN_FILES, ARM_D_MARKERS, frozen_violations)` |

**This index is a snapshot of a live worktree.** This index is a SNAPSHOT. The worktree was live while it was built: other graph nodes were writing concurrently. Any record whose git_tracked is false, or whose path appears in dirty_paths below, may have changed since the digest was taken.

Graph node status at snapshot, read from `GRAPH_STATE.json`: BLOCKED=22, PASSED=4, RUNNING=29, USER_REQUIRED=2.

No indexed path changed bytes between the first and second hashing pass.

## Counts

| | n |
|---|---|
| documents indexed | 245 |
| flagged FROZEN by `graph_lib.frozen_violations()` | 93 |
| DERIVED | 187 |
| HAND_MAINTAINED | 54 |
| UNDETERMINED (generation could not be established) | 4 |
| append-only ledgers/registries | 5 |
| not tracked by git at snapshot | 38 |
| total bytes indexed | 70,783,229 |
| records in ARTIFACT_LEDGER.jsonl | 1 |

By extension: `.json` 91, `.jsonl` 11, `.md` 101, `.parquet` 19, `.py` 21, `.sha256` 2.

## Scope of the index

Included:

* worktree-root program documents (START_HERE, ROADMAP, MISSION_LEDGER, HANDOFF_*, PLAYER_RESEARCH_*)
* every .md/.json/.jsonl/.sha256/.parquet file under experiments/player_program/
* experiments/player_program/orchestration/scripts/*.py and experiments/player_program/orchestration/tests/*.py (the governance machinery)
* every .py the program's own frozen rules classify as frozen

Excluded, deliberately:

* experiments/player_program/stage2b/SEALED_RESULTS (forbidden input; verified NOT PRESENT on disk)
* __pycache__
* the ~90 non-frozen producer/analysis .py files at experiments/player_program/ top level and the ~130 .py files at the worktree root -- code, not documents; named in maintenance_evidence where they reference an indexed artifact
* the other 52 experiments/* directories outside player_program

## How each column was obtained

| column | method |
|---|---|
| `sha256` | sha256 over the raw file bytes |
| `role` | extracted **from the document's own bytes** — markdown title, JSON `schema`/`description` value, JSONL record count and first-record keys, parquet row×column shape, or module docstring. `role_source` on every record states which. No document is paraphrased or summarised beyond what it literally says. |
| `frozen` / `frozen_rule` | `graph_lib.frozen_violations([path])` — the program's own frozen-path authority, imported and called, not transcribed |
| `maintenance` | DERIVED if the file self-declares generation or carries a machine-emission key; HAND_MAINTAINED if no generation marker is present; UNDETERMINED otherwise. `maintenance_evidence` records the exact basis. |
| `git_tracked` | membership in `git ls-files` |

## Consistency checks — document claims against the bytes

62 checks run, 1 disagreement(s).

### Disagreements — recorded, not reconciled

| check | document says | bytes say | note |
|---|---|---|---|
| CURRENT_STATUS.md table 'HEAD' == git rev-parse HEAD | `6abe0cccf073fa61705e8aca7f3110c84ab103fd` | `b6228a17d974691e21bdc0afa8226ce613461eac` | CURRENT_STATUS.md is DERIVED and records the HEAD it was generated at. Its HEAD is an ancestor of the live HEAD: True; commits behind: 1. A derived file lagging its source by regeneration is not a contradiction in the record -- it is regeneration lag, and it is recorded, not repaired here (the file is owned by G01_GRAPH_ENGINE). |

<details><summary>All checks</summary>

| result | check | expected | actual |
|---|---|---|---|
| OK | FILE_OWNERSHIP.json:graph_sha256 == sha256(PROGRAM_GRAPH.json) | `87624320e065f48db14f…` | `87624320e065f48db14f…` |
| OK | sha256 sidecar EVIDENCE_PACKET.sha256 == sha256(EVIDENCE_PACKET.json) | `f373e3eed710026c9d82…` | `f373e3eed710026c9d82…` |
| OK | sha256 sidecar V2_HALT_PACKET.sha256 == sha256(V2_HALT_PACKET.json) | `68a9ceff84b8b965817b…` | `68a9ceff84b8b965817b…` |
| OK | GRAPH_STATE.json:graph_sha256 == sha256(PROGRAM_GRAPH.json) | `87624320e065f48db14f…` | `87624320e065f48db14f…` |
| OK | GRAPH_STATE.json:events_sha256 == sha256(GRAPH_EVENTS.jsonl) | `f455b0196c47339ba56a…` | `f455b0196c47339ba56a…` |
| OK | GRAPH_STATE.json:n_events == records in GRAPH_EVENTS.jsonl | `39` | `39` |
| OK | GRAPH_STATE.json:n_nodes == nodes in PROGRAM_GRAPH.json | `57` | `57` |
| OK | CURRENT_STATUS.md table 'events' == records in GRAPH_EVENTS.jsonl | `39` | `39` |
| **DISAGREE** | CURRENT_STATUS.md table 'HEAD' == git rev-parse HEAD | `6abe0cccf073fa61705e…` | `b6228a17d974691e21bd…` |
| OK | V2_STOP_CONDITION.json findings count == 9 | `9` | `9` |
| OK | declared-frozen file exists on disk: experiments/player_program/feature_gate.py | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/comparison_gate.py | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/gate_invocation.py | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/receipt_integrity.py | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/arm_registry.jsonl | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/registry.jsonl | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/PROGRAM_STATE.json | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/RESEARCH_CONTRACT_V1.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/GATE_INVOCATION_CONTRACT.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/EVIDENCE_PACKET.json | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/EVIDENCE_PACKET.sha256 | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/CORRECTION_ADDENDUM.json | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/GENERATION_ORDER.json | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/V2_GENERATION_ORDER.json | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/V2_STOP_CONDITION.json | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/V2_HYPOTHESES_estimator.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/V2_HYPOTHESES_basketball.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/V2_HYPOTHESES_adversarial.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/SYNTHESIS.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/PHASE0A_RESOLUTION.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/PACKET_ADDENDUM_coordinator.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/HYPOTHESES_coordinator.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/HYPOTHESES_agent_adversarial.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/HYPOTHESES_agent_opponent_env.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/HYPOTHESES_agent_pace_coaching.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/HYPOTHESES_agent_roster_coldstart.md | `True` | `True` |
| OK | declared-frozen file exists on disk: experiments/player_program/stage2a/HYPOTHESES_agent_timeseries.md | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/possessions_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/possessions_v2/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/projected_exposure_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/event_contract_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/turnover_targets_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/turnover_p1_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/turnover_p2_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/p3_downstream_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/fits_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/possession_features_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/validation_v1/ | `True` | `True` |
| OK | declared-frozen directory exists on disk: experiments/player_program/discovery_wave_1/ | `True` | `True` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/comparison_gate.py | `c2d242581cc7551c6ce7…` | `c2d242581cc7551c6ce7…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/feature_gate.py | `b064c2c4675d354ec5cb…` | `b064c2c4675d354ec5cb…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/gate_invocation.py | `5c144b12c67910a4996a…` | `5c144b12c67910a4996a…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/receipt_integrity.py | `8c88617407d6dfb50c39…` | `8c88617407d6dfb50c39…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/stage2a/EVIDENCE_PACKET.json | `f373e3eed710026c9d82…` | `f373e3eed710026c9d82…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json | `3a35ae735333c47713d6…` | `3a35ae735333c47713d6…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/stage2a/V2_GENERATION_ORDER.json | `1998d5fda12ece9554d1…` | `1998d5fda12ece9554d1…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/stage2a/V2_HYPOTHESES_adversarial.md | `e38857002413f322887d…` | `e38857002413f322887d…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/stage2a/V2_HYPOTHESES_basketball.md | `6ee4af03f99a79e1daff…` | `6ee4af03f99a79e1daff…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/stage2a/V2_HYPOTHESES_estimator.md | `c4d6680612ade6c523c7…` | `c4d6680612ade6c523c7…` |
| OK | G00 RECONCILIATION frozen hash: experiments/player_program/stage2a/V2_STOP_CONDITION.json | `a4dd090b2b38dfb4d370…` | `a4dd090b2b38dfb4d370…` |
| OK | ARTIFACT_LEDGER: experiments/player_program/stage2b/P21_FREEZE_V2_HALT_PACKET/V2_HALT_PACKET.json | `68a9ceff84b8b965817b…` | `68a9ceff84b8b965817b…` |

</details>

## The index

`F` = flagged frozen by the program's own rule. `D`/`H`/`?` = DERIVED / HAND_MAINTAINED / UNDETERMINED. `+` = append-only. `u` = untracked by git at snapshot.

### Paths matching an Arm D marker in `graph_lib.ARM_D_MARKERS` — the entire path-level enforcement of the Arm D freeze — 1 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `FH..` | `arm_incumbent.py` | `a740bf1d271ef3ea09de82129595feb96e23b4c4baa1f324ee54806668d90a46` | Per (player, season) shifted histories.  Season-bounded, matching the contract's |

### `experiments/arm_incumbent/` — a REJECTED player-level arm artifact, `arm_id` = `incumbent_ewma_ridge`; NOT matched by any Arm D marker — 4 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.H..` | `experiments/arm_incumbent/REJECTED.md` | `2c3cc2e02a7ed75107582e467560fb19f5b744b59300e8b9bc5ab1f7a96f9c32` | REJECTED ARTIFACT — do not consume |
| `.D..` | `experiments/arm_incumbent/predictions.parquet` | `bc017f4ddebd9ccef888a71543e6b53bdfd4f9cb104f22aa4ad71bb64c6a4cfc` | Parquet table, 142460 row(s) x 20 column(s): row_uid, target_key, arm_id, fold_id, forecast_cutoff, pred_point, pred_sd, is_fallback, is_cold_start, n_prior_games ... |
| `.D..` | `experiments/arm_incumbent/predictions.parquet.manifest.json` | `21410827d30d08a533489c153f954856c69a05a4fc2a4fcc75c25f36ac434a50` | schema="asof_invariant/1" |
| `.D..` | `experiments/arm_incumbent/report.json` | `386596026ef4fd8d80f7b82b3dd423bb5bb0e7a1eb159719c6338666ed57886a` | JSON object, 7 top-level key(s): arm_id, config, config_hash, data_snapshot_hash, rows_emitted, validation, note |

### Program-level narrative and handoffs (worktree root) — 8 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.H..` | `HANDOFF_ADDENDUM_INTEGRITY_WORK.md` | `cf50f0c220dc182723d9c4ec08a17969cf63f6ecef044ae9e151c34377971964` | Handoff addendum — program-integrity work A–D is NOT done |
| `.D..` | `HANDOFF_PLAYER_MODEL_PROGRAM.md` | `9139b497d6272ab7bba3b3cc84f5097acc2d4fc91f4bdb0076075cc0a0841078` | HANDOFF — the player model program |
| `.H..` | `HANDOFF_TURNOVER_DISCOVERY.md` | `9a9e009f5bbaa131b8d02b7a874ec9f37de5ae22885ff65f0b92eeb87995783e` | Handoff — WNBA player program, turnover channel and discovery wave 1 |
| `.H..` | `MISSION_LEDGER.md` | `acb21f3d22f722e16a1f987add9ed088006619787a81d3757d318835ecdc0675` | MISSION LEDGER |
| `.H..` | `PLAYER_RESEARCH_COVERAGE_MATRIX.md` | `566f6bec2dbf052face85fa2b05faef7f2497041ffa81bc1c53d2024c026dc18` | PLAYER RESEARCH COVERAGE MATRIX |
| `.H..` | `PLAYER_RESEARCH_LEDGER.md` | `df22f00226a2a3708a7522f11930912ad04a7f9b70cc21cede07818068ffd16c` | PLAYER RESEARCH LEDGER |
| `.H..` | `ROADMAP.md` | `994bee91e9c3e7dcc9e9b3c4842cac63158d988b3d29521d2cc23a3fa673f301` | ROADMAP — WNBA Prediction Engine |
| `.H..` | `START_HERE.md` | `f5d072960983e995fea0bf254f184a7101482d334db583242df009439081db0d` | START HERE — WNBA prediction engine |

### Governing contracts and program state — 25 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.D..` | `experiments/player_program/CANDIDACY_GAP_RECEIPT.json` | `20e0e4fd4e1477dc68d1f880477e75471c95e4dab27d3333d953a2b7cf984555` | schema="player_candidacy_gap/1" |
| `.H..` | `experiments/player_program/ERRATUM_CLEAN_PRODUCER_1.md` | `661cfee1c6279059ac4298f2e226596fe59122bce288fb98f96f849c8e8e7597` | Erratum · `clean_producer/1` could report a clean tree it never measured |
| `.D..` | `experiments/player_program/FAILCLOSED_GATE_TEST_RECEIPT.json` | `f8dd0a76beb975e47e446be4a129ef7d0e1cb9233b1e5bdd96ddd552533b2c53` | schema="failclosed_gate_tests/1" |
| `FH..` | `experiments/player_program/GATE_INVOCATION_CONTRACT.md` | `ea6f31a0a6d7095ca1e022e88c4e9f0e4345c6e79b0e7b7522984f4ae4611c0a` | GATE INVOCATION CONTRACT — when `feature_gate.py` must be called |
| `.H..` | `experiments/player_program/NOTICE_TO_TEAM_THREAD_provenance.md` | `fbafbe5b22ea1337571aa8a15c28d8f350823f8210ba55c546b57a17c47b727c` | NOTICE to the team-model thread · a producer gate could report a clean tree it never measured |
| `.D..` | `experiments/player_program/PHASE0_AUDIT_RECEIPT.json` | `21019f09932726f595715251c55bbf324d7700f8ef812ef63edd808c1cb6923c` | schema="player_program_phase0_audit/1" |
| `.H..` | `experiments/player_program/PLAYER_MODEL_CAPABILITY_MATRIX.md` | `9d91fa3427bc29a7e77580684e3799bb3c36b13fad90c0e7ddad2e1981e57f8d` | Player model — capability matrix |
| `.H..` | `experiments/player_program/PREDICTION_CONTRACT_V5_SPEC.md` | `0877a89280d29dfc46ed7673a0236f2cc10b7a685ba8ee242476f1eb28f32f65` | `prediction_contract_v5` — a tiered candidacy universe |
| `FD..` | `experiments/player_program/PROGRAM_STATE.json` | `6e7f40979fe2f5ad60c558660f5b6791f8c453e55d549bb0a59816ce70a9192f` | schema="player_program_state/1" |
| `.H..` | `experiments/player_program/PROJECT_UPDATE_2026-08-04.md` | `1f29db49dabb80ee3c6cf74e7cabc99a5d6e822fbaa8bf228ac6982324d5b211` | Project update — 2026-08-04 |
| `.H..` | `experiments/player_program/README.md` | `4ac8065d3fa3d22223b7df8ce126bf3e9fc46a74f4e9b2bd7d3a6c7b828c71bb` | `experiments/player_program/` |
| `FD..` | `experiments/player_program/RESEARCH_CONTRACT_V1.md` | `ebf578ccf4a55ff67e5ecdc44dabd334869686012b1303f854890d154a554ea2` | Research contract v1 — WNBA player program |
| `.D..` | `experiments/player_program/ROSTER_SOURCE_AUDIT_RECEIPT.json` | `e70579b5ca69fdf5d432ed1e496bdc62459495e2af6a059cc105752d358559e5` | schema="player_roster_source_audit/1" |
| `.D..` | `experiments/player_program/STAGE15_RECEIPT.json` | `55414d3955aed389a4d4d90a0c25926fc00b8324a9e429b7b78ffb3e78bd049f` | schema="stage15_receipt/1" |
| `.D..` | `experiments/player_program/STAGE15_TEST_RECEIPT.json` | `8494fb825e968088fa8540c42efbe5f578970017ca83c8d36ee5fe255cd91616` | schema="stage15_tests/1" |
| `.D..` | `experiments/player_program/V14_CONTROL_RECEIPT.json` | `220ca3dc8935159a26d81805d6f81f0e410f41e9a414b58d8b4a90eed4fe048c` | schema="v14_control/1" |
| `.D..` | `experiments/player_program/V14_V15_SCORING.json` | `2540dc64e0ee9cf438989c37de38d0249607313d90cee4c82775bf8707dbc3b5` | schema="v14_v15_scoring/1" |
| `.D..` | `experiments/player_program/V15_MODULE_TEST_RECEIPT.json` | `f9b29895376c3e1d85373d41d731df42aa8c98e76629770abbe4592887f3d442` | schema="v15_module_tests/1" |
| `.D..` | `experiments/player_program/V15_PRESCORE_RECEIPT.json` | `78b33838c7f228a498564563fcb3c6b38d8604acad9ee1566c67992df82c11ac` | schema="v15_prescore_receipt/1" |
| `FD+.` | `experiments/player_program/arm_registry.jsonl` | `4137d122c7aadb27d58d81c43280dd1ac3c0e887e5e9e960211df7e7e2ae5a31` | JSONL ledger, 41 record(s); first record key(s): schema, kind, experiment_id, registered_at, registered_before_execution, board, extra |
| `FH..` | `experiments/player_program/comparison_gate.py` | `c2d242581cc7551c6ce7d3aaf554f0cc18fd9b1f72677edd61ba95f91a7b5b92` | #!/usr/bin/env python3 |
| `FH..` | `experiments/player_program/feature_gate.py` | `b064c2c4675d354ec5cb5c6647782634c8139ca4233a5d732f408b6c2532f9a7` | #!/usr/bin/env python3 |
| `FH..` | `experiments/player_program/gate_invocation.py` | `5c144b12c67910a4996aafe08e86e8939a2a1878168431850a99d22754ff9ded` | #!/usr/bin/env python3 |
| `FH..` | `experiments/player_program/receipt_integrity.py` | `8c88617407d6dfb50c394ad5888ff77cd2464b590242a35c5f97a1320e05751d` | Audit every registered family. Never stops at the first failure. |
| `FD+.` | `experiments/player_program/registry.jsonl` | `7917fb96c57397bed1253e75a0c733f38c718b2637479012370abcdb9d479746` | JSONL ledger, 8 record(s); first record key(s): schema, registered_at, standing, kind, id, title, status, spec_document, spec_sha256, supersedes, does_not_edit, motivation_measured |

### Orchestration: graph, ledgers, policy, machinery — 25 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.D+.` | `experiments/player_program/orchestration/ARTIFACT_LEDGER.jsonl` | `7eeda434c4e545960d4138428c5a010d0858ab6e53109397b173a386d17192e1` | JSONL ledger, 1 record(s); first record key(s): head, kind, note, path, sha256, ts |
| `.D+.` | `experiments/player_program/orchestration/DECISION_LEDGER.jsonl` | `7016a6a34a4a9d88f6d9b8e7a83e0af2b73a89aaa0d377e1af094cb145873be9` | JSONL ledger, 2 record(s); first record key(s): authority, decision_id, made_by, nodes, question, ruling, ts |
| `.D..` | `experiments/player_program/orchestration/FILE_OWNERSHIP.json` | `f5eaac5bf48be5220d17753203773c91cf637e56ca3b07dd7b5d7826503c3cfc` | schema="player_program/orchestration/file_ownership/1" |
| `.D+.` | `experiments/player_program/orchestration/GRAPH_EVENTS.jsonl` | `f455b0196c47339ba56a7537d833519d270d4b234f3b87c216ffd079f8d75ef2` | JSONL ledger, 39 record(s); first record key(s): detail, event, n_nodes, repo, ts, version |
| `.D..` | `experiments/player_program/orchestration/GRAPH_POLICY.md` | `bd664c856744c264d2e2d70552e349f4eb0a2ec16c0234f8d6057286220f39e6` | Graph policy — autonomous program graph for the WNBA player model |
| `.D..` | `experiments/player_program/orchestration/GRAPH_STATE.json` | `228ddbf313e8b264e058d122ac3b8950f4249124ee7bad1f495e2ac3d2834b88` | schema="player_program/orchestration/graph_state/1" |
| `.D..` | `experiments/player_program/orchestration/NODE_CONTRACT.schema.json` | `798cc37409e2115284ccc47276274e0651e2c53ec462b9deb63a46a7b5c8e428` | description="Every node in PROGRAM_GRAPH.json must satisfy this contract. The schema is enforced by scripts/validate_graph.py, which implements it directly and does not require the jsonschema package to be installed." |
| `.D..` | `experiments/player_program/orchestration/PROGRAM_GRAPH.json` | `87624320e065f48db14f5b16db2741fa7a3e72991c9e305beda62cc18870c676` | schema="player_program/orchestration/program_graph/1" |
| `.D..` | `experiments/player_program/orchestration/README.md` | `7079707d8c4a5fe3afaaac95435ec66972a68e2f7cbe3677a9883673548ac1a9` | Orchestration — the persistent program graph |
| `.D..` | `experiments/player_program/orchestration/nodes/G00_LIVE_RECONCILIATION/RECONCILIATION.json` | `2600c0fb71b52d3a3315d18fccc884ac4f7bfd3c904b7dac0cae954208ccd636` | JSON object, 5 top-level key(s): annotation, checks, failures, ok, repo |
| `.D..` | `experiments/player_program/orchestration/reports/CURRENT_STATUS.md` | `714180ebe647b940c0f9542419027107c7ea1aa96759494e3b28b4a17483b654` | Current status — autonomous program graph |
| `.D.u` | `experiments/player_program/orchestration/reports/DOCUMENT_INDEX.json` | `a4c8c5c0eff7fdd5234e1a1f8605da7d56c8a2397b19a2da8026035a97ce74cd` | schema="player_program/orchestration/document_index/1" |
| `.H.u` | `experiments/player_program/orchestration/reports/DOCUMENT_INDEX.md` | `4a0574203d4ffb838df771ab139d52e7b7124886eacc5f7c3399b549d8564f4b` | DOCUMENT_INDEX — every authoritative document, contract, task card, ledger, receipt and frozen artifact |
| `.H..` | `experiments/player_program/orchestration/scripts/dispatch_ready.py` | `24b85531499374ba0b014b394b9f41bf4afc51b22da629faf7477b7167af7dfb` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/scripts/frozen_path_guard.py` | `c48dffddf93302e11d35e63192e9475e0092a75efd3a3a2dffd41556271b15d0` | Every previously existing line must survive byte-identically, in order. |
| `.D..` | `experiments/player_program/orchestration/scripts/generate_prompts.py` | `b151d707a50120da8a265455570a4669d80cec084a53339ebdedee9c266267f3` | #!/usr/bin/env python |
| `.D..` | `experiments/player_program/orchestration/scripts/graph_lib.py` | `f7740e52e705b61db67ece13a88c5499def9c08619089414bbc7d7fcc92b9021` | Shared core for the program graph. |
| `.D..` | `experiments/player_program/orchestration/scripts/graphctl.py` | `d7da3252e92ce72cfb4b4b1b250172a1b38a76f6c7fd0fdc4ebecb4464dfbae3` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/scripts/hash_artifacts.py` | `4e1d57a17ba89ad22edab7c47100298508c06e854ef21b30552d06cc5a754e9d` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/scripts/integrate_node.py` | `6bf7cc45b175e0aabca8646dc925956b750d3aae414156223fecf9f1d4271786` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/scripts/reconcile_repo.py` | `b10fe66b42ea78b673bb97dca5ccbf47b140b7680c8b19294bc02e1e7c1fc80d` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/scripts/seed_graph.py` | `1ca740732a9dcc5e212d7e2a4c6e0ede0a80c9c71e5fbcc5984547dbd50abc57` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/scripts/validate_graph.py` | `107fb91a055641a3ef9056166b4d5b60f751a8def10b53bc9f8f4c08a3e62800` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/scripts/validate_node.py` | `7de0a38b8ab1c14f7629debfd0956f107ddb65f2a1fc8e2fb61980be8404e1b9` | #!/usr/bin/env python |
| `.H..` | `experiments/player_program/orchestration/tests/test_graph_engine.py` | `18d0ae738f7853cd45c51708da42ea10b2a343e1dc5f174ba06b789357aa94f1` | #!/usr/bin/env python |

### Orchestration: generated node task cards (prompts) — 57 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.D..` | `experiments/player_program/orchestration/prompts/D10_FIELD_AVAILABILITY_LEDGER.md` | `96f1e43b8b83885d83e716fce46956bc342de173b22f87b4c8fd3ccc8dfea03d` | D10_FIELD_AVAILABILITY_LEDGER — Field-level cutoff-validity coverage across every candidate source |
| `.D..` | `experiments/player_program/orchestration/prompts/D11_LIVE_INFORMATION_CAPTURE.md` | `9cee21bf6d6492d3dc9826e9039e7b52f0419db42439953be7cfdc279dd64df4` | D11_LIVE_INFORMATION_CAPTURE — Timestamped prospective capture with first-seen and change history |
| `.D..` | `experiments/player_program/orchestration/prompts/D12_COACHING_HISTORY.md` | `eefcd917c2cf380ad5c3bcd8e2de462474817b0d1497a4f8f624d4db308b20bf` | D12_COACHING_HISTORY — Retrospectively auditable coaching table |
| `.D..` | `experiments/player_program/orchestration/prompts/D13_ARENA_TRAVEL_DIMENSION.md` | `221d8e8928300f4912752a2d1bcbb8de0d025f6657fbfe51f24091bf67488d48` | D13_ARENA_TRAVEL_DIMENSION — Unique effective-dated team/arena/travel dimension with cardinality tests |
| `.D..` | `experiments/player_program/orchestration/prompts/D14_ENTITY_RESOLUTION_AND_COLD_START.md` | `23149488b420d62d1eaefa2ad2025c8ca081a382b7fbc5296c4e01085389c4f7` | D14_ENTITY_RESOLUTION_AND_COLD_START — Tests and design artifacts for aliases, new signings, zero-history players, team transitions |
| `.D..` | `experiments/player_program/orchestration/prompts/F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT.md` | `68e2930e60fe0182d6af902cf142a38db08398c6d7c9c3c81afef171046aa520` | F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT — Within-team versus between-team involvement forecaster |
| `.D..` | `experiments/player_program/orchestration/prompts/F11_PLAYER_ALLOCATION_ARCHITECTURE.md` | `f4c1e9f73caec20428413222128b9823f3f6e0560dd7d8549f2ff82f4c785199` | F11_PLAYER_ALLOCATION_ARCHITECTURE — Player allocation / distribution architecture |
| `.D..` | `experiments/player_program/orchestration/prompts/F12_OFF_DEF_STRENGTH_COMPONENTS.md` | `f7e1e32e7f226edb656f1f0f9d6069c53ee246c545003d8c3e6f266245128f83` | F12_OFF_DEF_STRENGTH_COMPONENTS — Offensive and defensive strength components |
| `.D..` | `experiments/player_program/orchestration/prompts/F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS.md` | `d8143768200db60623e39808fc1e231284e65adb88b5f015c9b1eb531bc9730a` | F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS — Score, margin and total distributions |
| `.D..` | `experiments/player_program/orchestration/prompts/F14_DECISION_TIME_MARKET_COMPARISON.md` | `152515b2fc98e02c494d2a3a808b4eec3e2ab1aa4f46d9f47def6eff565f785b` | F14_DECISION_TIME_MARKET_COMPARISON — Decision-time market comparison |
| `.D..` | `experiments/player_program/orchestration/prompts/F15_PROSPECTIVE_VALIDATION.md` | `9c1c60caae19af9b72e0625cde9252a692e745b0955058d2d37ea2615f3bf807` | F15_PROSPECTIVE_VALIDATION — Prospective validation design |
| `.D..` | `experiments/player_program/orchestration/prompts/F16_PLAYER_PROPS.md` | `c0d78f547c9ccfa4a7475cce5b5a04b09b9f8ac132af3503386249d497395c05` | F16_PLAYER_PROPS — Player props — last, by design |
| `.D..` | `experiments/player_program/orchestration/prompts/G00_LIVE_RECONCILIATION.md` | `6cae2e0e7bc9a69cc7053faf0cba93529a59036ff7a0b5a9b1be659db8b8cea9` | G00_LIVE_RECONCILIATION — Reconcile live repository state, ancestry and frozen artifact hashes |
| `.D..` | `experiments/player_program/orchestration/prompts/G01_GRAPH_ENGINE.md` | `b30fd37363c8c6c5a219b0c87608a2f83a25cfe06b5f224a51188782dc6556d9` | G01_GRAPH_ENGINE — Persistent orchestration framework: graph, ledgers, validators, dispatcher |
| `.D..` | `experiments/player_program/orchestration/prompts/G02_DOCUMENT_INDEX.md` | `16a25456ca7764491bc7d1071a73b2e5da1f4dabfe18eb7efc3cd45fdd670670` | G02_DOCUMENT_INDEX — Index every authoritative document, contract, task card, ledger, receipt and frozen artifact |
| `.D..` | `experiments/player_program/orchestration/prompts/G03_FROZEN_PATH_GUARD.md` | `b6911137f27f1a23a960e9c013c565436cb3ebb3b64db119153ab7faea104bcb` | G03_FROZEN_PATH_GUARD — Task-specific tests proving the frozen-path guard fails closed |
| `.D..` | `experiments/player_program/orchestration/prompts/G04_PROGRAM_ROADMAP_EXTRACTION.md` | `ace18915d90b9fd7e40c1c96d619887daba22d29f7f985b9376ee058f712007b` | G04_PROGRAM_ROADMAP_EXTRACTION — Convert documented remaining program into graph nodes; unknown work becomes NEEDS_TARGET_CONTRACT |
| `.D..` | `experiments/player_program/orchestration/prompts/I10_GENERIC_CLUSTERED_INFERENCE.md` | `1053d00125bbdfda3ad6f437b4a218351a7641a07dec3d3b2c5fee95d34a1957` | I10_GENERIC_CLUSTERED_INFERENCE — Reusable game-clustered bootstrap and interval utilities in a task-isolated namespace |
| `.D..` | `experiments/player_program/orchestration/prompts/I11_BLINDED_RESULT_PACKAGING.md` | `212b5073454e8e7d3441d6b2bbf0056227fd3a9d20f0f3032ba2b514709f1b91` | I11_BLINDED_RESULT_PACKAGING — Generic sealed-result and integrity-manifest tooling |
| `.D..` | `experiments/player_program/orchestration/prompts/I12_DESIGN_DEPENDENCY_AUDIT.md` | `e49dcf9d61fbfe9d7a5b663a96bd916da99493eca0db60572cbb530d3b1a9953` | I12_DESIGN_DEPENDENCY_AUDIT — Reusable full-design offset/dependency audits without modifying frozen shared gates |
| `.D..` | `experiments/player_program/orchestration/prompts/I13_REPRODUCIBILITY_RUNNER.md` | `c3626cebd639dc100e064e540d063698717860eef4aa4f88799d57553856197f` | I13_REPRODUCIBILITY_RUNNER — Deterministic commands, seed manifests and artifact reconciliation |
| `.D..` | `experiments/player_program/orchestration/prompts/O10_LATE_RECORD_AUDIT_CLASSIFICATION.md` | `a7a8c6b496503b8742053e7a4f322abfb9dd9b8cf21fee3d3facf09eb66b7988` | O10_LATE_RECORD_AUDIT_CLASSIFICATION — Classify late-arriving records in the prospective capture audit |
| `.D..` | `experiments/player_program/orchestration/prompts/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW.md` | `b1fd255b2f7c6a6fab15d58f2f9e38a30871b1b17175cf318e362bfaf6dab611` | O11_OBLIGATION_DISCOVERY_LEAD_WINDOW — Obligation-discovery lead window defect |
| `.D..` | `experiments/player_program/orchestration/prompts/O12_PER_GAME_EXECUTION_SCOPE.md` | `7e3f7b7d1cad810ab5e57225c630cfbd9b8e7bfb31e64f6b30bc6f03881d80e1` | O12_PER_GAME_EXECUTION_SCOPE — Per-game execution scope defect |
| `.D..` | `experiments/player_program/orchestration/prompts/O13_LEAD_WINDOW_LATENCY.md` | `53020f42cc13674a32aee8231d3cca12e1f6f088a69af5878703a84ab03e24e4` | O13_LEAD_WINDOW_LATENCY — Lead-window latency defect |
| `.D..` | `experiments/player_program/orchestration/prompts/O14_OPS_ENTITY_RESOLUTION.md` | `a04ad0c818800de3a70db8a2237d7cfc555b8d75f55183ff4a626e26b50ac276` | O14_OPS_ENTITY_RESOLUTION — Entity resolution in the prospective capture path |
| `.D..` | `experiments/player_program/orchestration/prompts/O15_LOGOUT_SURVIVAL.md` | `5e89e78c040f12fa5ff5e4d8d2b6a88d664d85a51834ca132373ec821381bdfe` | O15_LOGOUT_SURVIVAL — Logout survival for the capture scheduler |
| `.D..` | `experiments/player_program/orchestration/prompts/O16_SHARED_SCHEMA_ADOPTION.md` | `839392969e55ecc3c2fe4cdbd84c17e89612169754daba09203b4567ded20a11` | O16_SHARED_SCHEMA_ADOPTION — Merge a shared schema or contract change proposed by the operations lane |
| `.D..` | `experiments/player_program/orchestration/prompts/P20_INGEST_PENDING_ESTIMATOR.md` | `db3f475d32493eba1d4314e35797c5b0964fd3bf1d1811661695d92bab410526` | P20_INGEST_PENDING_ESTIMATOR — Ingest and freeze the third V2 source (estimator) that returned after the halt |
| `.D..` | `experiments/player_program/orchestration/prompts/P21_FREEZE_V2_HALT_PACKET.md` | `21a89f1cd24ac1f345858804c4c25983275670f519196641f81382d54a6ebaef` | P21_FREEZE_V2_HALT_PACKET — Freeze the complete V2 halt packet: three source outputs, nine findings, scope reconciliation |
| `.D..` | `experiments/player_program/orchestration/prompts/P22_POSTGAME_SURROGATE_GUARD.md` | `7552cd23656e4464c766b371db4a5cd9afea8318422771bf895aa672d1f51d67` | P22_POSTGAME_SURROGATE_GUARD — S1: enforced invariant against current-game outcome-derived columns |
| `.D..` | `experiments/player_program/orchestration/prompts/P23_DIMENSION_CARDINALITY_GUARD.md` | `99d895f32486b94ebb6468192b912ac977dc6eaf1c21587d3ddfce4e82edba59` | P23_DIMENSION_CARDINALITY_GUARD — S2: merge cardinality invariants preserving the 2,982-row / 1,491-game universe |
| `.D..` | `experiments/player_program/orchestration/prompts/P24_INJURY_REGIME_LEDGER.md` | `3c242edf5aa42b5dd05ccdbb7bd3019232c5a4fb74d746da77b580308062e0d3` | P24_INJURY_REGIME_LEDGER — S3: split injury data into explicit epistemic regimes and report cutoff-valid coverage |
| `.D..` | `experiments/player_program/orchestration/prompts/P25_OFFSET_DEPENDENCY_GUARD.md` | `5a666d4884ad79400fdd2129a4addd059ff1577e9e85a40adf6d97e4151b57c1` | P25_OFFSET_DEPENDENCY_GUARD — S4/S5: full-design offset and affine-dependency audit including own/opponent contrasts |
| `.D..` | `experiments/player_program/orchestration/prompts/P26_ARM_SPECIFIC_K0_CONTRACT.md` | `6c68fdf0f02331d6ea1773b2056d696683b237760fdc9f9c4b46b72effd3d079` | P26_ARM_SPECIFIC_K0_CONTRACT — S6/S9: the K0_MATCHED[arm_id] contract and machine-readable schema |
| `.D..` | `experiments/player_program/orchestration/prompts/P27_FOLD_LOCAL_ESTIMABILITY_GUARD.md` | `b9034f6013024b59098c0b0946065019e178bc01f0b8b8cdf67cfc0b29099c43` | P27_FOLD_LOCAL_ESTIMABILITY_GUARD — S7: fold-local rank, support, variance and degeneracy checks |
| `.D..` | `experiments/player_program/orchestration/prompts/P28_PRIMARY_SECONDARY_ORDERING_CONTRACT.md` | `9326271095e8264c35061002ac6a4985af8b389325a1d3f4385b68ad1701cac0` | P28_PRIMARY_SECONDARY_ORDERING_CONTRACT — Possession-first adjudication; prohibit downstream OT-mismatch arbitrage |
| `.D..` | `experiments/player_program/orchestration/prompts/P29_TIP_TIME_AND_COVERAGE_AUDIT.md` | `55750157aa98e1583ac0c070c6d465b8bdf0ec894a8fa934987826592b7f3a08` | P29_TIP_TIME_AND_COVERAGE_AUDIT — Resolve the fold-aligned tip-time null pattern and rule on tip-derived eligibility |
| `.D..` | `experiments/player_program/orchestration/prompts/P2A_POSSESSION_COLUMN_ADJUDICATION.md` | `de778a0a2e5693ce4c405be12405ec9cd4c427b3db8ff535e11f9943401e4660` | P2A_POSSESSION_COLUMN_ADJUDICATION — S8: adjudicate the 32 possession columns the availability table never named |
| `.D..` | `experiments/player_program/orchestration/prompts/P30_EVIDENCE_PACKET_V3.md` | `e20a2a48b75915367f7f02babb5f17203cfbe87450cf1f2a173dcb0646de3a4b` | P30_EVIDENCE_PACKET_V3 — Build and freeze EVIDENCE_PACKET_V3 with an immutable correction addendum |
| `.D..` | `experiments/player_program/orchestration/prompts/P31_FINAL_V3_IDEATION.md` | `11b78853bb9c7fe64e324a4ab024465fac09dce65bc510345649d33d1788dc53` | P31_FINAL_V3_IDEATION — Final clean ideation wave: six independent roles, V3 only, no source sees another output |
| `.D..` | `experiments/player_program/orchestration/prompts/P32_CANDIDATE_SYNTHESIS.md` | `2ecfba59d5e8f7d96c9c94f0ca880acd7eff2507becda4061ba6210c973d3f66` | P32_CANDIDATE_SYNTHESIS — Deduplicate into mechanistically distinct families; return complete arm definitions |
| `.D..` | `experiments/player_program/orchestration/prompts/P33_PREREGISTRATION_DRAFT.md` | `1805d7e8e26cbe0ac243cc80794fa50c4a516a56196761ada5007d60044167c4` | P33_PREREGISTRATION_DRAFT — Freeze every retained arm's complete specification |
| `.D..` | `experiments/player_program/orchestration/prompts/P34_PREREGISTRATION_RED_TEAM.md` | `bda5b1e4b9df4beb29c6220ba051dab5cda7c18640b87b6539c8610357447d02` | P34_PREREGISTRATION_RED_TEAM — Independent adversarial review of the preregistration |
| `.D..` | `experiments/player_program/orchestration/prompts/P35_FREEZE_TASK_CARDS.md` | `f537f39cea3cf71d801fd400dc07ad28ae0e04b05078e9fdbd7902e36aefd61c` | P35_FREEZE_TASK_CARDS — Freeze task cards and append registry records |
| `.D..` | `experiments/player_program/orchestration/prompts/P36_IMPLEMENT_ARMS.md` | `883f789dd126a8c83aa2b01575b0e2dc24c8bb16071b070f007007bb013ca1b7` | P36_IMPLEMENT_ARMS — Implement each arm, K0_FLAT, each K0_MATCHED, the shared runner and receipts |
| `.D..` | `experiments/player_program/orchestration/prompts/P37_IMPLEMENTATION_AUDIT.md` | `bad31042d9d5c2047e9dba330b107ac0585aa1249660193dd9f40784918e8318` | P37_IMPLEMENTATION_AUDIT — Verify code matches formula, gates, receipts, parity |
| `.D..` | `experiments/player_program/orchestration/prompts/P38_BLINDED_FIT.md` | `00ffb0b5a761305ed9247e31f5469e05a696753e5e124add34d2e3fa6c921159` | P38_BLINDED_FIT — Execute the frozen preregistered experiment into a sealed result directory |
| `.D..` | `experiments/player_program/orchestration/prompts/P39_RESULT_INTEGRITY.md` | `14a0dd2bc03ecde9ed9b69fad5d54d13e41037b19768ee06a2d5a3e1781c8901` | P39_RESULT_INTEGRITY — Verify sealed outputs without interpreting which arm won |
| `.D..` | `experiments/player_program/orchestration/prompts/P40_PRIMARY_ADJUDICATION.md` | `58c451161cd9ac6f71f637995d5f9574f19f16d88abff39002b723130ab12bdb` | P40_PRIMARY_ADJUDICATION — Open results; apply the preregistered primary possession gates |
| `.D..` | `experiments/player_program/orchestration/prompts/P41_DOWNSTREAM_TURNOVER_CONFIRMATION.md` | `38104e9ee5b43d5ee837e8cc3efcc9d8226daff7360587feb856e8e9a84dbbd5` | P41_DOWNSTREAM_TURNOVER_CONFIRMATION — Downstream turnover scoring for arms that passed the primary gate only |
| `.D..` | `experiments/player_program/orchestration/prompts/P42_SCIENTIFIC_COMPLETION.md` | `0b61ad26e7d0bef038d14c03d6e07e8e67a8e7307f4d5f42193be7742701d267` | P42_SCIENTIFIC_COMPLETION — Accepted/null/failed decisions, bounded effects, uncertainty, limitations |
| `.D..` | `experiments/player_program/orchestration/prompts/P43_CHAMPION_DECISION.md` | `abe5c97b1d04237b1b4d43fe78648804382498a83e1e96322872f6c23eb06610` | P43_CHAMPION_DECISION — Whether to replace Arm D as the frozen champion |
| `.D..` | `experiments/player_program/orchestration/prompts/U10_PREDICTION_API_SCHEMA.md` | `776edc66a956ae2f11debd3b3ce0c29ef4209cc8a5e3628941e32e34d44c79cf` | U10_PREDICTION_API_SCHEMA — Model-agnostic versioned response schema built against fixtures |
| `.D..` | `experiments/player_program/orchestration/prompts/U11_UI_SHELL.md` | `8944827c7b49c988d3ea90a48433d4de09bf05b5ce5ae8f75fd08d9b2edd238a` | U11_UI_SHELL — UI shell built against fixtures or frozen outputs |
| `.D..` | `experiments/player_program/orchestration/prompts/U12_PREDICTION_HISTORY.md` | `ac69c0a2a58775d06d2056e7dd33bbecbbcc2642777f79d7ec6ab44311c78242` | U12_PREDICTION_HISTORY — Immutable prediction-history and model-version views |
| `.D..` | `experiments/player_program/orchestration/prompts/U13_MONITORING_INTERFACE.md` | `255e14b16ebf02b9a2e4b159e1a3bc8214357ef5a6f0438cb7de1258334654a9` | U13_MONITORING_INTERFACE — Stale-input, missing-lineup, failed-job and rollback visibility |

### Stage 2A: frozen evidence packets, hypotheses, halt — 19 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `FD..` | `experiments/player_program/stage2a/CORRECTION_ADDENDUM.json` | `6c475e6a98d7add4c436d5260cc8ba2a22fff7786cf5ce7fa19073dab1edd4dc` | schema="stage2a_correction_addendum/1" |
| `FD..` | `experiments/player_program/stage2a/EVIDENCE_PACKET.json` | `f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e` | schema="stage2a_evidence_packet/1" |
| `FD..` | `experiments/player_program/stage2a/EVIDENCE_PACKET.sha256` | `c835619012b74c3b23e61474924ec7e5ea711354cbbdbc7e6d7a3589532c6d5d` | sha256 sidecar, content: f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e  EVIDENCE_PACKET.json |
| `FD..` | `experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json` | `3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c` | schema="stage2a_evidence_packet/2" |
| `FD..` | `experiments/player_program/stage2a/GENERATION_ORDER.json` | `f98befe25a34fce4c03e700a0329b88ee022dc79f8822f8f95254079814e5edd` | schema="stage2a_generation_order/1" |
| `FH..` | `experiments/player_program/stage2a/HYPOTHESES_agent_adversarial.md` | `3ce6b8ab295fc0656a97e1dff6ced390a9200018c97c9e32a0def1a739bbae6c` | Stage 2A — adversarial leakage and identifiability review |
| `FH..` | `experiments/player_program/stage2a/HYPOTHESES_agent_opponent_env.md` | `e4c7d88c5d9565d194d643b7fd5b42e30f763ad2b1248e3c2a938dd833b859b4` | Stage 2A hypotheses — source: **opponent interaction and game environment** |
| `FH..` | `experiments/player_program/stage2a/HYPOTHESES_agent_pace_coaching.md` | `1bd4af0889ee347fe509f89172822bc60ebee1f9c2c60b6e4af0c0a83883772c` | Stage 2A Hypotheses — Source: BASKETBALL PACE AND COACHING |
| `FH..` | `experiments/player_program/stage2a/HYPOTHESES_agent_roster_coldstart.md` | `1efe7c4f6c911eb2e898eac7a1b3a76a7fbf9daa7a5dcafb06fab2dbdd7128e2` | Stage 2A hypotheses — source: `agent_roster_coldstart` |
| `FH..` | `experiments/player_program/stage2a/HYPOTHESES_agent_timeseries.md` | `45c2a2f406293b80473d75cd4f821bda47a26279c1899f12dc44ff4d83d1f0d5` | HYPOTHESES — Stage 2A independent source: statistical time-series and shrinkage |
| `FH..` | `experiments/player_program/stage2a/HYPOTHESES_coordinator.md` | `6776bddb31d753a4cca0a55239b6fffa214f9a8e19a8a7b3e55e89c5bf9167dc` | Stage 2A hypotheses — source: CLAUDE COORDINATOR |
| `FH..` | `experiments/player_program/stage2a/PACKET_ADDENDUM_coordinator.md` | `0f3e94c2cac55763b13df2baba9ba9a839273173a7b3bdd1160a4bb6176e9b42` | Evidence-packet addendum — coordinator verification |
| `FH..` | `experiments/player_program/stage2a/PHASE0A_RESOLUTION.md` | `137b7267d0a364320c0ef2121151da1652ae6454a18e96dd02039097b51a4b91` | STAGE2A_PHASE0A_RESOLUTION_v1 |
| `FH..` | `experiments/player_program/stage2a/SYNTHESIS.md` | `b5ed656f1a406ad84a7fc434f6849dca7f5f343b864ffd04cf323b05dba8fa9e` | Stage 2A synthesis — deduplicated families, proposed variants, multiplicity plan |
| `FD..` | `experiments/player_program/stage2a/V2_GENERATION_ORDER.json` | `1998d5fda12ece9554d1ace895d010e46ba647c526df0e5170ae12e1a5f340ce` | schema="stage2a_v2_generation_order/1" |
| `FH..` | `experiments/player_program/stage2a/V2_HYPOTHESES_adversarial.md` | `e38857002413f322887d47aac27bec770832e4f424824daeba9bafd1c07c5a92` | V2 — ADVERSARIAL LEAKAGE, IDENTIFIABILITY AND EVALUATION REVIEW |
| `FD..` | `experiments/player_program/stage2a/V2_HYPOTHESES_basketball.md` | `6ee4af03f99a79e1daffd9dd8208730151552561e5794742decb3043aaa32690` | V2 Hypotheses — Basketball Mechanism and Game Context |
| `FH..` | `experiments/player_program/stage2a/V2_HYPOTHESES_estimator.md` | `c4d6680612ade6c523c7a0bb592eeb999b5b14cffe0d21fa08552a0e5e8440df` | V2 HYPOTHESES — Estimator Structure and Statistical Form |
| `FD..` | `experiments/player_program/stage2a/V2_STOP_CONDITION.json` | `a4dd090b2b38dfb4d37028e15daa10c689deb27269cde3d8b9cddd12fd92244d` | schema="stage2a_v2_stop_condition/1" |

### Stage 2B: post-halt node outputs — 15 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.D..` | `experiments/player_program/stage2b/P20_INGEST_PENDING_ESTIMATOR/INGEST_RECEIPT.json` | `fb5263abca03718816fd76765b05deb3e6963585265790b88160bc40329929f6` | schema="player_program/stage2b/ingest_receipt/1" |
| `.D..` | `experiments/player_program/stage2b/P21_FREEZE_V2_HALT_PACKET/V2_HALT_PACKET.json` | `68a9ceff84b8b965817b3cf75577c5186864d17bbded53b182b2b8e34ae9cd1c` | schema="player_program/stage2b/v2_halt_packet/1" |
| `.D..` | `experiments/player_program/stage2b/P21_FREEZE_V2_HALT_PACKET/V2_HALT_PACKET.sha256` | `700f85c56f03a0a3945d656b42a0d58478c33b7d14f77e48eaf173acd5b06290` | sha256 sidecar, content: 68a9ceff84b8b965817b3cf75577c5186864d17bbded53b182b2b8e34ae9cd1c  V2_HALT_PACKET.json |
| `.D.u` | `experiments/player_program/stage2b/P22_POSTGAME_SURROGATE_GUARD/MEASUREMENTS.json` | `711855ec2f517395ddb78699b12025ac3247f7055b9048bad5b4b8ba85955d58` | JSON object, 15 top-level key(s): feature_gate_sha256, S1, universe, feature_gate_blindness, A1_blocking_kinds, A2_blocking_kinds, A3_blocking_kinds, A4_lag_verification, A4_dependency_vs_game_minutes, A4_complete_case_rows, A4_per_fold, A5_routes, A6_receipt_path, A6_receipt_digest |
| `.D.u` | `experiments/player_program/stage2b/P22_POSTGAME_SURROGATE_GUARD/receipts/EXEMPLAR_LAGGED_DURATION_RECEIPT.json` | `7ef6e4e29e1bc765867efda3d2580316e1306807ddd47b594154a2a85b789da2` | schema="construction_receipt/1" |
| `.H.u` | `experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/REPORT.md` | `6267f4450f42133e8be4e855b216121c1b4328f49caabacf6b39dd0e0caa5ffe` | Epistemic status |
| `.D.u` | `experiments/player_program/stage2b/P23_DIMENSION_CARDINALITY_GUARD/TEST_RESULTS.json` | `a89de6ecbf3dcf340c7c2e599a43090124c475c02327a8ac6dda4c05c4afad32` | JSON object, 4 top-level key(s): n_tests, n_failed, results, measurements |
| `.D.u` | `experiments/player_program/stage2b/P24_INJURY_REGIME_LEDGER/FINDINGS.json` | `05bee2d9a2cfec8560eb39ea6c89ef57370e9fe1495bb9d51cb6cf87e33eaf99` | schema="p24_injury_regime_ledger/1" |
| `.D.u` | `experiments/player_program/stage2b/P25_OFFSET_DEPENDENCY_GUARD/MEASUREMENTS.json` | `f45d430bb2f94088b385dfcfa447f7b92015e674ca3199b2efaa8bfee34d6ed3` | JSON object, 56 top-level key(s): audited_columns, augmented_rank, benign_candidate_corr, complete_recalibration_family_passes, contrast_augmented_rank, contrast_formula_max_abs_deviation, contrast_offset_corr_if_400_games_become_one_sided, contrast_per_fold, contrast_permitted, contrast_r2_offset_on_design, corr_contrast_projected, corr_own_opp, corr_own_projected, feature_gate_bytes |
| `.D.u` | `experiments/player_program/stage2b/P25_OFFSET_DEPENDENCY_GUARD/PREREGISTERED_CONTRASTS.json` | `df934b95ab1c8dcac0ba026d93fc9cd5b524571ba6ee60e7b55871266bfbee4b` | schema="offset_dependency_guard_prereg/1" |
| `.?.u` | `experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_EXAMPLES.json` | `c959b0bc077b8e5b1829b435a278b15a77d473878fade24a829b08737c09fe39` | JSON object, 2 top-level key(s): EXAMPLE_opponent_pace_adjustment_v1, EXAMPLE_offset_recalibration_v1 |
| `.D.u` | `experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_SCHEMA.json` | `312c1792812039f7bfbe8c6ae7031d416a52a2e76a037455f5b1bd47d29bfec9` | description="ONE record per arm_id. K0_MATCHED is a MAP keyed by arm_id, never a single universal object. This file constrains the SHAPE of a record; the cross-field rules that JSON Schema cannot express (exclusion minimality, lower-" |
| `.D.u` | `experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/MEASUREMENTS.json` | `2650730ad3e7cdad47484dcb2f2f184e8f028c2b08f2531b6a44a65ce71695e0` | schema="p26_measurements/1" |
| `.D.u` | `experiments/player_program/stage2b/P27_FOLD_LOCAL_ESTIMABILITY_GUARD/ACTIVE_SET_RULE_PREREGISTRATION.json` | `327fa8ec9fb54e3635ae70b540573b4121c6136fc5034cbdb689cabbe2986db7` | schema="s7_active_set_preregistration/1" |
| `.D.u` | `experiments/player_program/stage2b/P27_FOLD_LOCAL_ESTIMABILITY_GUARD/MEASUREMENTS.json` | `0a94be22096270bb3e12a23459586e34a7ba80ca64029d6f84f5d38361a0c353` | schema="s7_measurements/1" |

### Discovery wave 1 (frozen) — 11 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `FH..` | `experiments/player_program/discovery_wave_1/DISCOVERY_WAVE_1_SUMMARY.md` | `c584133d9de81e4d02fa2ebb442ed8792bc469b77a9478c2f8f29e07bbde7ed4` | Discovery wave 1 — consolidated summary |
| `FD..` | `experiments/player_program/discovery_wave_1/FINAL_AUDIT_MATRIX.json` | `1923a21d65c8df35908131cd5d93b2dcff1d7df35965aef1c270aeeb416d164a` | schema="discovery_wave_1_final_audit_matrix/1" |
| `FH..` | `experiments/player_program/discovery_wave_1/FINAL_AUDIT_MATRIX.md` | `93e7ded3fef57a28d2f7791e352e6341c7a9335b1a4dcc0698fa404caf66ed47` | Discovery wave 1 — final audit matrix |
| `FD..` | `experiments/player_program/discovery_wave_1/HYPOTHESIS_LEDGER.json` | `e2c821e705d761a33a5f51df0404076cc86aa1c48f49c34535b1c3562cb818c7` | schema="discovery_hypothesis_ledger/1" |
| `FD..` | `experiments/player_program/discovery_wave_1/LEDGER_MERGE_RECEIPT.json` | `3a976180c9c79c09163f07f9e61227d71a2bffb486f43ab3b2dfe60b7a377ddb` | schema="discovery_ledger_merge_receipt/1" |
| `FD..` | `experiments/player_program/discovery_wave_1/RETROSPECTIVE_GATE_AUDIT.json` | `bfb1c0beba6f1c4402e6296784871f4fa7b11a045afe68a8857825a50a174d0b` | schema="retrospective_gate_audit/2" |
| `FD..` | `experiments/player_program/discovery_wave_1/RETROSPECTIVE_GATE_AUDIT.md` | `686589b4a5e8898c745da612886b41047899f5be2295c0f14d6188bf1d6ca22b` | Retrospective gate audit — discovery wave 1 |
| `FH..` | `experiments/player_program/discovery_wave_1/build_final_matrix.py` | `56af12a4eb69a4967d857e9fe4652f08cfa7bd7623415690568fcea06a4d2306` | #!/usr/bin/env python3 |
| `FH..` | `experiments/player_program/discovery_wave_1/make_ledger.py` | `8fb6559dee137e3d3952d163a89d56212fc27af6c1df1bafad6ef0c6f281c48f` | make_ledger.py — freeze the eight discovery hypothesis cards before execution. |
| `FH..` | `experiments/player_program/discovery_wave_1/merge_ledger_updates.py` | `dff174dd17a077e66dda04a4b04881b86f0331c058d6675996a0d155f7343dfa` | sha256 of every artifact under root, keyed by posix-relative path, sorted. |
| `FH..` | `experiments/player_program/discovery_wave_1/retrospective_gate_audit.py` | `a49b738cd0c5025c5b6b132f6e8d21b42b83c891f62b3833df36475606a13171` | Merge the audit facts with the classification and enforce the acceptance gate. |

### Frozen canonical artifact directories (v1/v2 data, receipts, fits) — 53 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `FD..` | `experiments/player_program/event_contract_v1/EVENT_AUDIT_SAMPLE.json` | `075ab7ad1be921cef4c518cb87f2e04101dfe73884c0dbd3342ae2be24d53603` | JSON object, 10 top-level key(s): early_2021_legacy, late_legacy_before_changeover, first_cdn_after_changeover, 2026_games, playoff_games, overtime_games, high_substitution_games, games_missing_shot_coordinates, administrative_or_ejection_games, technical_foul_games |
| `FH..` | `experiments/player_program/event_contract_v1/EVENT_CROSSWALK.md` | `657311767b20366ba3d7545fef1a8f0b83f28f913cf53d4116c615176ddadabc` | `canonical_player_events/1` — crosswalk and limitations |
| `FH..` | `experiments/player_program/event_contract_v1/EVENT_LIMITATIONS.md` | `657311767b20366ba3d7545fef1a8f0b83f28f913cf53d4116c615176ddadabc` | `canonical_player_events/1` — crosswalk and limitations |
| `FD..` | `experiments/player_program/event_contract_v1/EVENT_NORMALISATION_RECEIPT.json` | `d2c59121a168cedf55b68a2a2fa685b2f78b4f6019cf8e129e32dcb1a7c011c8` | schema="canonical_event_receipt/1" |
| `FD..` | `experiments/player_program/event_contract_v1/EVENT_SOURCE_INVENTORY.json` | `5ce5849947ea918692551b2595b71e1d236665d2447c187ed040833bcb62597f` | schema="event_source_inventory/1" |
| `FD..` | `experiments/player_program/event_contract_v1/EVENT_VALIDATION.json` | `95425fb1335b801bf431f0938a8de148cd528e9ec2bf2fa812f99323d56df33e` | schema="canonical_event_validation/1" |
| `FD..` | `experiments/player_program/event_contract_v1/canonical_player_events_v1.parquet` | `b0220e3e2f37b50775642d52e3273c997e6e9297398c071977869098aac93352` | Parquet table, 589123 row(s) x 50 column(s): event_uid, game_id, canonical_event_seq, source_system, source_file, source_file_sha256, source_event_id, source_row_index, period, clock_seconds_remaining ... |
| `FD..` | `experiments/player_program/event_contract_v1/event_crosswalk.json` | `f12f679357552c95db16810a12baf11e334ec247bcdd396a6a04e4468f6be60f` | JSON object, 4 top-level key(s): legacy_EVENTMSGTYPE, cdn_actionType, cdn_period_subtype, cdn_empty_actiontype |
| `FD..` | `experiments/player_program/fits_v1/RATE_AND_P3_REPORT.json` | `bf9e3204ed900c78df840aac29f008db1e689f6bc341859269463039dd64f1ed` | schema="rate_and_p3_fit/1" |
| `FD..` | `experiments/player_program/fits_v1/p3_coefficients_v1.parquet` | `a9948cc418596bb8cefd864f438dceaa658bbeb4a52279881080e08a12748c32` | Parquet table, 1177 row(s) x 8 column(s): training_cutoff_season, player_id, orapm_100, drapm_100, net_rapm_100, off_possessions, def_possessions, total_possessions |
| `FD..` | `experiments/player_program/p3_downstream_v1/P3_DOWNSTREAM_RESULTS.json` | `ca6181daad1555b742654a42878cf9d47c31358b32dd4bebe54000bb20e42b57` | schema="p3_downstream_results/1" |
| `FH..` | `experiments/player_program/p3_downstream_v1/P3_EXPERIMENT_SUMMARY.md` | `997007b2ec4e91c37880b0f9ff7c83fc46a5df40365ec4c883989ed01d83e6bb` | `p3_projected_exposure_downstream_v1` — final summary |
| `FD..` | `experiments/player_program/p3_downstream_v1/p3_downstream_rows.parquet` | `e8c5e59bb08853cacef89dfb7dc13b557845b5d3947d8da9250d134471859c6c` | Parquet table, 673 row(s) x 55 column(s): GAME_ID, GAME_DATE_h, season_h, season_type_h, TEAM_ABBREVIATION_h, TEAM_ABBREVIATION_a, any_fallback, fallback_row_h, fallback_row_a, margin_true ... |
| `FD..` | `experiments/player_program/possession_features_v1/dryrun_receipts/CONSTRUCTION_RECEIPT__possession_prior__incumbent_equivalent__final_design.json` | `b66bec91ec4012de35e282bd2a29565294c07de4e718e6bcd0cbd3f9b4aa627a` | schema="construction_receipt/1" |
| `FD..` | `experiments/player_program/possession_features_v1/dryrun_receipts/CONSTRUCTION_RECEIPT__possession_prior__incumbent_equivalent__train_lt_2022.json` | `3fd3a792b5db66225b2fad1d20f15aa03f94fe02b7d0ea085fdeaf3a5537d313` | schema="construction_receipt/1" |
| `FD..` | `experiments/player_program/possession_features_v1/dryrun_receipts/CONSTRUCTION_RECEIPT__possession_prior__incumbent_equivalent__train_lt_2023.json` | `85b71d2d0a552cd824ae51fa462afa8c710a9b2d8457a62493295cb63f021611` | schema="construction_receipt/1" |
| `FD..` | `experiments/player_program/possession_features_v1/dryrun_receipts/CONSTRUCTION_RECEIPT__possession_prior__incumbent_equivalent__train_lt_2024.json` | `8031d8a3839c5a748cef5fcd4136b4d4f3135b339636cfd8c0b015425d1ad17f` | schema="construction_receipt/1" |
| `FD..` | `experiments/player_program/possession_features_v1/dryrun_receipts/CONSTRUCTION_RECEIPT__possession_prior__incumbent_equivalent__train_lt_2025.json` | `8f905f9026af75e008fe90c21d630848985573ff3d95d491075d226b17c4c861` | schema="construction_receipt/1" |
| `FD..` | `experiments/player_program/possession_features_v1/dryrun_receipts/CONSTRUCTION_RECEIPT__possession_prior__incumbent_equivalent__train_lt_2026.json` | `87ed14a7c425a1722618e6e1daa2e3891afd17561c9d4232cd4c2543a97aac6a` | schema="construction_receipt/1" |
| `FD..` | `experiments/player_program/possession_features_v1/dryrun_receipts/DRYRUN_REPORT.json` | `47bb4a9d3598cf0db724075307a8fbb6dbc267e779e94075f9e2b5ed96012d9a` | schema="possession_features.dry_run/1" |
| `FD..` | `experiments/player_program/possessions_v1/POSSESSION_INTEGRITY_RECEIPT.json` | `f40389e30ede3d37835881c3c1555fe1b5937712c7bb5301dbf0fff491619b7c` | schema="possession_artifact_receipt/1" |
| `FD..` | `experiments/player_program/possessions_v1/player_season_possessions_v1.parquet` | `dd656a6ef76183175a7062313fabe52a08d6510e83d237dc54f8d36664efed4c` | Parquet table, 1038 row(s) x 10 column(s): player_id, season, offensive_possessions, defensive_possessions, excluded_invalid_lineup, games, teams, first_date, last_date, total_valid_possessions |
| `FD..` | `experiments/player_program/possessions_v1/possessions_raw_v1.parquet` | `49e9bf5ec5a50f88fd4f765c3b93dbd36364627daf0bbcb25b11d848f2df09d0` | Parquet table, 238563 row(s) x 45 column(s): game_id, season, season_type, era, possession_idx, period, start_sec, end_sec, duration_sec, offense_team_id ... |
| `FD..` | `experiments/player_program/possessions_v2/POSSESSION_INTEGRITY_RECEIPT_V2.json` | `51346e7a08f9fab4db8ff250c452688a552e938a2e7a2ca4e1f7e2f7c1f6b6d4` | schema="possession_artifact_receipt/2" |
| `FD..` | `experiments/player_program/possessions_v2/V1_TO_V2_RECONCILIATION.json` | `91334655a5356ad59f37d61edb3fd032403da91e47e39ffcc84b18ad4f3962da` | JSON object, 19 top-level key(s): v1_rows, v2_rows, rows_added, rows_removed, rows_common, games_v1, games_v2, games_added, games_removed, on_common_rows, v1_valid_pct, v2_valid_pct, v1_points_on_invalid, v2_points_on_invalid |
| `FD..` | `experiments/player_program/possessions_v2/player_season_possessions_v2.parquet` | `62ad07849ebd832f4852e314ad2368cfc08c2103871c14b06452c811022d3a58` | Parquet table, 1039 row(s) x 10 column(s): player_id, season, offensive_possessions, defensive_possessions, excluded_invalid_lineup, games, teams, first_date, last_date, total_valid_possessions |
| `FD..` | `experiments/player_program/possessions_v2/possessions_raw_v2.parquet` | `7200881fd811db9d0d6b10ea0a19b01ec7b6d027ee4567b9ef963241b15a4b1a` | Parquet table, 238563 row(s) x 48 column(s): game_id, season, season_type, era, possession_idx, period, start_sec, end_sec, duration_sec, offense_team_id ... |
| `FD..` | `experiments/player_program/projected_exposure_v1/PROJECTED_EXPOSURE_RECEIPT.json` | `475ea28e3c84217fa0664ae845268c894c96e66b5441ef9df2307e87d503d6aa` | schema="projected_exposure_receipt/1" |
| `FD..` | `experiments/player_program/projected_exposure_v1/PROJECTED_EXPOSURE_VALIDATION.json` | `50cf0f3061363f8aef838d57b7067f9c2436f04162998fba0dc164eae521748c` | schema="projected_exposure_validation/2" |
| `FD..` | `experiments/player_program/projected_exposure_v1/projected_player_possessions_v1.parquet` | `1f47f1f169955cae5c65457f1db30665ac6da20e821e458257d21276646df50f` | Parquet table, 120262 row(s) x 51 column(s): row_uid, obligation_uid, game_id, team_id, player_id, game_date, season, forecast_cutoff, fold_id, universe_tier ... |
| `FD..` | `experiments/player_program/projected_exposure_v1/projected_team_rotations_v1.parquet` | `d2c4011382eddc82e66eaa16b12ca67fe82f540f86c04b4411c45952bb096128` | Parquet table, 8970 row(s) x 39 column(s): game_id, team_id, opp_team_id, game_date, season, season_type, regime, n_candidates, n_viable, pace_level ... |
| `FD..` | `experiments/player_program/projected_exposure_v1/team_possession_prior_v1.parquet` | `c37c075148553920b79c9320ea03afb37986bfc752fc84dd695f154887c3db18` | Parquet table, 2990 row(s) x 11 column(s): game_id, team_id, game_date, season, season_type, pace_level, pace_source, n_history_games, team_pace_estimate, projected_team_off_possessions ... |
| `FD..` | `experiments/player_program/turnover_p1_v1/TURNOVER_P1_RESULTS.json` | `9d0ae315b211d05bc835beaa4a18723c7e104d1a1c1e9a0c7c82edc446db89d0` | schema="turnover_p1_results/1" |
| `FD..` | `experiments/player_program/turnover_p1_v1/TURNOVER_P1_UNIVERSE_AUDIT.json` | `b6231b4d37d153aa8afdd06401954cbba481ddbdd3f3608e32e294a5fcb89ca1` | schema="turnover_p1_universe_fix/1" |
| `FD..` | `experiments/player_program/turnover_p1_v1/turnover_p1_predictions_intrinsic.parquet` | `ed73bfae7757a52a76c94d78f3221c0bbd64d7dfa1907b3e62e25aab52495567` | Parquet table, 28193 row(s) x 18 column(s): game_id, team_id, player_id, game_date, season, turnovers, realised_off_possessions, prior_off_possessions, eligible, A_league_constant ... |
| `FD..` | `experiments/player_program/turnover_p1_v1/turnover_p1_predictions_operational.parquet` | `bffd9264a612f1f5fb2a7d5aa0ba61c00dcb1ecc6f9a6dec95adc8f2105f09fa` | Parquet table, 27299 row(s) x 18 column(s): game_id, team_id, player_id, game_date, season, turnovers, realised_off_possessions, prior_off_possessions, eligible, A_league_constant ... |
| `FD..` | `experiments/player_program/turnover_p1_v1/turnover_p1_predictions_operational_corrected.parquet` | `998a293b88c7ec1e7091df08b399e5c1d2ddd6f550dcf592cc8546d4edb81c64` | Parquet table, 35629 row(s) x 18 column(s): game_id, team_id, player_id, game_date, season, turnovers, did_appear, exposure, team_game_status, league_prior_fallback ... |
| `FD..` | `experiments/player_program/turnover_p2_v1/FEATURE_VALIDATION.json` | `4829c55bbcb5c6632e50526d80b52cca0e182fc79c567303aeb09ebdff185862` | artifact="turnover_role_context_features_v1" |
| `FD..` | `experiments/player_program/turnover_p2_v1/P2_SUPERSESSION.json` | `41bc29ed3968bea6f98a757ba486b8cbe294b505dfaa1a3e1de6a16a3fc24866` | schema="player_program_supersession/1" |
| `FH..` | `experiments/player_program/turnover_p2_v1/P2_SUPERSESSION.md` | `6dbdd7cc7e222abcd466064a3a867f139c3846eb0feb72a32725586fedc017e4` | P2 SUPERSESSION — `turnover_rate_role_context_v1` |
| `FD..` | `experiments/player_program/turnover_p2_v1/PROPOSED_REGISTRY_RECORDS.jsonl` | `843315e6b61c197b237b0ccf10109f832346efa3a9431e1c999fdab0902adeb0` | JSONL ledger, 6 record(s); first record key(s): schema, kind, experiment_id, applies_to, registered_at, extends_not_replaces, defect, measured_truth, consequence, status, what_is_NOT_done, root_cause_is_the_registration_not_the_solver |
| `FD..` | `experiments/player_program/turnover_p2_v1/TURNOVER_P2_RESULTS.json` | `bc2967b4ad73feddb0509f9b5be5f013b507efa628a256c7218144d14f4c94f9` | schema="turnover_p2_results/1" |
| `F?..` | `experiments/player_program/turnover_p2_v1/turnover_p2_predictions_intrinsic.parquet` | `50a841adcdf9fb0c067d86eca69c7812ffbe50aa984367ffb22ba36ee1f2e76e` | Parquet table, 28193 row(s) x 35 column(s): game_id, team_id, player_id, game_date, season, turnovers, exposure, prior_off_possessions, eligible, A_league_constant ... |
| `F?..` | `experiments/player_program/turnover_p2_v1/turnover_p2_predictions_operational.parquet` | `5330fe8d04cc7c57e2b095db402a40999f403189a0bc8ac8a8caeda947a7e1dc` | Parquet table, 35629 row(s) x 35 column(s): game_id, team_id, player_id, game_date, season, turnovers, did_appear, exposure, team_game_status, league_prior_fallback ... |
| `FD..` | `experiments/player_program/turnover_p2_v1/turnover_role_context_features_v1.parquet` | `5ab9160078771f6857cd332da9d3a1182e83ce4ab35b5dd8c2746b0be98b2072` | Parquet table, 35629 row(s) x 20 column(s): game_id, team_id, player_id, projected_minutes, projected_off_possessions, p_active, proj_minutes_share, proj_off_poss_share, proj_rotation_rank, proj_top5_concentration ... |
| `FD..` | `experiments/player_program/turnover_targets_v1/DUPLICATE_ADJUDICATION.json` | `be40d789989b3e900dc49cc0c75b1714e1960f1fb460bfaa46f5d50eef0fb732` | JSON object, 12 top-level key(s): policy, question, verdict, evidence, ruled_out, rule, general_not_targeted, rows_dropped, games_affected, affected_event_families, external_reconciliation_after, no_degraded_exclusion_needed |
| `FD..` | `experiments/player_program/turnover_targets_v1/TURNOVER_DISCREPANCY_AUDIT.json` | `a15c74c87b91adda153719d5c3ab54c5a910bce317318c6c744bff0ae217f1e7` | JSON object, 4 top-level key(s): turnover_heavy_team_games, degraded_turnover_rows, external_disagreements, unresolved_no_team_events |
| `FD..` | `experiments/player_program/turnover_targets_v1/TURNOVER_TARGET_RECEIPT.json` | `1db89003151c5a629488379dfba974d614776809695b3e2a79270dc8100faf32` | schema="turnover_target_receipt/1" |
| `FD..` | `experiments/player_program/turnover_targets_v1/TURNOVER_VALIDATION.json` | `4dc49068ea09602ad6da960a6ad6a17479243a807845ffb115c4b70c2357615e` | schema="turnover_target_validation/1" |
| `FD..` | `experiments/player_program/turnover_targets_v1/ZERO_EXPOSURE_AUDIT.json` | `021c154ed93cb63795f542b5ceb683e666323d11a2073cc715718ba7d619ca2f` | JSON object, 14 top-level key(s): policy, rows, with_zero_turnovers, with_one_or_more_turnovers, total_turnovers_represented, by_source, by_season, all_have_recorded_minutes, minutes_summary, appear_in_incomplete_lineup_possessions, lineup_validity_column_used, likely_cause, treatment, examples |
| `FD..` | `experiments/player_program/turnover_targets_v1/player_turnover_targets_v1.parquet` | `65641a7875cd266df8a0b44f3c4a5f9409f34efffc08c2683f2cc17ad0983ae4` | Parquet table, 28328 row(s) x 32 column(s): game_id, team_id, player_id, season, season_type, minutes, external_tov, realised_off_possessions, zero_possession_exposure, turnovers ... |
| `FD..` | `experiments/player_program/turnover_targets_v1/team_turnover_reconciliation_v1.parquet` | `446af16c237d59cc52a5294862ce60a2977522e14500370ec843cc29baae6e93` | Parquet table, 2990 row(s) x 10 column(s): game_id, team_id, team_turnovers_total, player_attributed, team_unattributed, team_off_possessions, source_system, external_team_tov, diff_vs_external, player_sum_from_artifact |
| `FD..` | `experiments/player_program/validation_v1/P3_VALIDATION.json` | `eec757274ed2e97cb3973219491b00b7f453819df686c5d7f57f03259c0ad954` | schema="p3_validation/1" |

### Node lanes populated after the graph started (data / ops / future_research / product) — 24 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.D.u` | `experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json` | `d05dfa8fca7c26cbfc78abd7c5acd222e3401cd32d7af2a22f39fa7ca551b7ec` | schema="field_availability_ledger/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/SELFTEST_RECEIPT.json` | `1378c53e99cfba0933bc240303315ebfdf96882db3afd8915d696fca46eaa799` | schema="player_program/live_capture_selftest_receipt/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/SOURCE_BINDING.json` | `526da04d0ae665774864f3f921a36faac6759a795cea74d871a962de1d7ecb8c` | schema="player_program/live_capture_source_binding/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/ledger/MANIFEST.json` | `6089a24e44a1d099fb96f9523bde423f7f9f020f51815b46cc82bdf3c267332c` | schema="player_program/live_capture_manifest/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/ledger/README.md` | `aeea753859caa016ee96f2f1cdd7b04f64b359a69944320bbbe3d32e93c94da4` | Production capture ledger — EMPTY |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/ledger/STATE_INDEX.json` | `31d561bc306968597777c068f52477262a8421964cf730dc5ed81d4b165d0032` | schema="player_program/live_capture_state_index/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/ledger/WATERMARKS.json` | `f06404c78bb86df97907d56f7f05ec5d7b1d4a9ae9845d67bdd843ed348ee519` | schema="player_program/live_capture_watermarks/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/ledger/observations.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | JSONL ledger, 0 records (empty) |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/selftest/MANIFEST.json` | `a7b3ae74b52315c722a247a5c12171dbdeaba4dd15051f4469a511775712b2d6` | schema="player_program/live_capture_manifest/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/selftest/STATE_INDEX.json` | `645f02738eab41159c4f932b65fd1fd4ceff65db0d4bf12a942843e9a56d1ce7` | schema="player_program/live_capture_state_index/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/selftest/WATERMARKS.json` | `42313a3bc52901540307a088e7690771b7e93545878a217bc3b1ba740d4ac69b` | schema="player_program/live_capture_watermarks/1" |
| `.D.u` | `experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/selftest/observations.jsonl` | `4c0a48677a11da9def7b2f5ec22aa5e4da0bcb5ccb4939c02b58828920f8bbf9` | JSONL ledger, 13 record(s); first record key(s): change_index, change_kind, cutoff_basis, domain, effective_at_utc, entity_key, fetch_id, first_seen_at_utc, ingest_at_utc, ingest_seq, observed_at_utc, payload |
| `.D.u` | `experiments/player_program/data_lane/D12_COACHING_HISTORY/MEASUREMENTS.json` | `da8dbf9acb14371a7484a703c425a4ed974db771a5eea1f595bdcc2cdcc51f5e` | epistemic_status="REFERENCE DATA. Auditable history only. Explicitly NOT admitted to any experiment before a cutoff review." |
| `.D.u` | `experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/MEASUREMENTS.json` | `64f44f1d381a558e858c8a4a4758e9af860986068b038a371f783269ff14a70a` | JSON object, 18 top-level key(s): generated_utc, source_files, raw_source, effective_dating, master_corroboration, universe, seasons_in_master, dimension, cardinality_tests, venue_pair_travel, home_venue_assignment, identity_proxy_check, game_venue_derivation, first_season_censoring |
| `.D.u` | `experiments/player_program/data_lane/D13_ARENA_TRAVEL_DIMENSION/arena_dimension_v1.meta.json` | `185e8f3a5cfa90946a8767a21801ee7c710935f111e3918ba66dccaa6b364414` | artifact="arena_dimension_v1.csv" |
| `.D.u` | `experiments/player_program/data_lane/D14_ENTITY_RESOLUTION_AND_COLD_START/TEST_RESULTS.json` | `85ae0fd02389fae033317e949a9c904c5db8c35b8afdbe08480e7780c9b29890` | schema="d14_entity_resolution_and_cold_start_tests/1" |
| `.D.u` | `experiments/player_program/ops_lane/O10_LATE_RECORD_AUDIT_CLASSIFICATION/evidence/coverage_receipt_snapshot.json` | `00b2274684125f46f73157d0eabe18d68e3978d88ea090ef43f105d722a61198` | JSON object, 10 top-level key(s): obligations_total, duplicate_records_excluded, obligations_due, served, coverage_served, not_yet_due, operational_misses, unexplained, promotion_grade, threshold |
| `.?.u` | `experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/DISCOVERY_LAG.json` | `e9e9368f6adce8cae39bc8d5dafb69dfe85c4d8378f30767f53ee378e8bd7a96` | JSON object, 8 top-level key(s): obligations_examined, distinct_games, obligations_with_no_game_id_ever, obligations_discoverable_before_cutoff, obligations_NOT_discoverable_before_cutoff, by_label, odds_lead_min_median_by_label, id_lead_min_median_by_label |
| `.D.u` | `experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/FINDINGS.json` | `f0d1283bb229ab5feabc22486b3d0f26c56c7967962c64569a2a4b12ba62f9b4` | epistemic_status="DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. Isolated branch only. This lane does not block possession research unless it changes the historical feature evidence." |
| `.D.u` | `experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/_scratch_chains/distinct.jsonl` | `43eacd6af3d9ba5709116e5e3fbc4c12186da3cadf627aeca928744b39fb6757` | JSONL ledger, 6 record(s); first record key(s): core_only_prediction, core_plus_w1_prediction, data_snapshot_hash, decision_time_label, forecast_cutoff, game_id, intended_bet_decision, logged_at_utc, market_book, market_line, market_price, market_source |
| `.D.u` | `experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/_scratch_chains/fixed.jsonl` | `31f9897870b8bb7d114cded306e91332e72539c2c3f6d3fabd8db0cd96c2ef87` | JSONL ledger, 1 record(s); first record key(s): core_only_prediction, core_plus_w1_prediction, data_snapshot_hash, decision_time_label, forecast_cutoff, game_id, intended_bet_decision, logged_at_utc, market_book, market_line, market_price, market_source |
| `.D.u` | `experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/_scratch_chains/repro.jsonl` | `f78438d989fdfe24fc95b16c5f7433b61e74d3c5a4057767daed253e5b6756ec` | JSONL ledger, 4 record(s); first record key(s): core_only_prediction, core_plus_w1_prediction, data_snapshot_hash, decision_time_label, forecast_cutoff, game_id, intended_bet_decision, logged_at_utc, market_book, market_line, market_price, market_source |
| `.D.u` | `experiments/player_program/ops_lane/O12_PER_GAME_EXECUTION_SCOPE/chain_scope_measurements.json` | `98bc139394d2fb29d32cf9b17b0b9b6fc6160c72c356af9aae31dcdfb58f15fb` | JSON object, 2 top-level key(s): official, scratch |
| `.D.u` | `experiments/player_program/ops_lane/O14_OPS_ENTITY_RESOLUTION/MEASUREMENTS.json` | `db84617ad166a5cf42667bd3e7e0db3e3c3fc8be6e7031699a4f25af46d4a245` | JSON object, 2 top-level key(s): generated_by, snapshots |

### Everything else in scope — 3 file(s)

| flags | path | sha256 | role (from the file itself) |
|---|---|---|---|
| `.D..` | `experiments/player_program/preserved_uncommitted_d69aa02/PRESERVATION_MANIFEST.json` | `fa7fb187b9c25f38bf30e0a2437833aed9a9e5cdeae44bbed76ed9d5680b5ff7` | schema="player_program_preservation/1" |
| `.H..` | `experiments/player_program/templates/EXPERIMENT_COMPLETION_REPORT.md` | `4abef5bae54df27ad353c7aaf90c41829ed08cd78899ca62f9263b423061aa13` | Experiment completion report |
| `.H..` | `experiments/player_program/templates/EXPERIMENT_TASK_CARD.md` | `f5b91d10f228de4fe0ba3cfe2496c3b9cec2fc129730b719133a144600e309ae` | Experiment task card |

## Frozen artifacts and their governing rule

Every rule string below is the return value of `graph_lib.frozen_violations()` for that path — the same function `orchestration/scripts/frozen_path_guard.py` calls before any node merge, and it fails closed.

| governing rule | n files |
|---|---|
| Arm D marker 'arm_incumbent.py' | 1 |
| frozen directory experiments/player_program/discovery_wave_1/ | 11 |
| frozen directory experiments/player_program/event_contract_v1/ | 8 |
| frozen directory experiments/player_program/fits_v1/ | 2 |
| frozen directory experiments/player_program/p3_downstream_v1/ | 3 |
| frozen directory experiments/player_program/possession_features_v1/ | 7 |
| frozen directory experiments/player_program/possessions_v1/ | 3 |
| frozen directory experiments/player_program/possessions_v2/ | 4 |
| frozen directory experiments/player_program/projected_exposure_v1/ | 5 |
| frozen directory experiments/player_program/turnover_p1_v1/ | 5 |
| frozen directory experiments/player_program/turnover_p2_v1/ | 8 |
| frozen directory experiments/player_program/turnover_targets_v1/ | 7 |
| frozen directory experiments/player_program/validation_v1/ | 1 |
| frozen file | 28 |

The two registries (`arm_registry.jsonl`, `registry.jsonl`) are frozen **and** append-only: `frozen_path_guard.py` reports a registry change as an APPEND-ONLY-CHECK and passes only if every previously existing line is byte-identical. `GRAPH_EVENTS.jsonl`, `DECISION_LEDGER.jsonl` and `ARTIFACT_LEDGER.jsonl` are declared append-only by `GRAPH_POLICY.md` section 2 but are **not** in `graph_lib`'s frozen set — they are flagged `+` here and not `F`.

### Measured coverage of the Arm D clause

`GRAPH_POLICY.md` section 3 freezes "everything constituting **Arm D** (`D_ewma_shrunk`): source, configuration and outputs". That clause is implemented as substring matching of `graph_lib.ARM_D_MARKERS` = `['D_ewma_shrunk', 'arm_incumbent.py']` against changed paths. Measured against this index:

| | |
|---|---|
| indexed paths whose path contains `D_ewma_shrunk` | **0** |
| indexed paths whose path contains `arm_incumbent.py` | 1 |
| tracked files under `experiments/player_program/` whose *contents* mention `D_ewma_shrunk` | 81 (24 excluding the generated prompts, which all restate the standing rule) |

So the Arm D clause contributes **no path coverage at all** through the `D_ewma_shrunk` marker, and one path through `arm_incumbent.py`. Arm D's bytes are in fact protected — but by the frozen-directory and frozen-file rules, not by the Arm D clause. Whether that incidental coverage is *complete* is stated below under what could not be established. This is a finding for `G03_FROZEN_PATH_GUARD`, not something this node may fix: the guard is outside its write scope.

### The identifier `D_ewma_shrunk` denotes two different objects in the record

Both readings are preserved here rather than reconciled, per `GRAPH_POLICY.md` section 1.

| source | what it says `D_ewma_shrunk` is |
|---|---|
| `experiments/player_program/PROGRAM_STATE.json -> frozen_incumbent` | {"arm": "D_ewma_shrunk", "K": 200, "alpha": 0.1, "operational_team_mae": 2.9675, "intrinsic_team_mae": 2.896, "status": "FROZEN — do not alter or retune"} |
| `experiments/player_program/arm_registry.jsonl line 31 (experiment_id=turnover_rate_pooled_baseline_v1) -> extra.frozen_arms.D_ewma_shrunk` | possession-weighted trailing EWMA player rate, shrunk to the league rate |
| `experiments/player_program/arm_registry.jsonl line 32 (experiment_id=turnover_rate_pooled_baseline_v1__final) -> development_champion` | {"arm": "D_ewma_shrunk", "scope": "turnover channel, P1 development only", "not": ["production-ready", "universally superior"]} |

This node did **not** establish whether these are the same estimator family applied to two channels or two distinct objects sharing a letter. It matters because the freeze clause and the standing rule in every generated node prompt both name Arm D by this string alone.

## DERIVED vs HAND-MAINTAINED

A DERIVED file can be regenerated and must never be hand-edited; a divergence between it and its source is a regeneration lag, not a contradiction in the record. A HAND_MAINTAINED file is authored, and a divergence is a genuine disagreement between two human statements. The classification therefore changes what a disagreement means.

| classification | n | basis |
|---|---|---|
| DERIVED | 187 | self-declared generation marker, or a machine-emission key in the JSON |
| HAND_MAINTAINED | 54 | no generation marker present |
| UNDETERMINED | 4 | machine-shaped, no self-declaration, and no script in the program references its filename |

The UNDETERMINED files, named rather than guessed at:

* `experiments/player_program/ops_lane/O11_OBLIGATION_DISCOVERY_LEAD_WINDOW/DISCOVERY_LAG.json` — machine-shaped artifact with no self-declaration and no script in the program references its filename
* `experiments/player_program/stage2b/P26_ARM_SPECIFIC_K0_CONTRACT/K0_MATCHED_EXAMPLES.json` — machine-shaped artifact with no self-declaration and no script in the program references its filename
* `experiments/player_program/turnover_p2_v1/turnover_p2_predictions_intrinsic.parquet` — machine-shaped artifact with no self-declaration and no script in the program references its filename
* `experiments/player_program/turnover_p2_v1/turnover_p2_predictions_operational.parquet` — machine-shaped artifact with no self-declaration and no script in the program references its filename

## What was measured, and how

Every number in this file came from code run against the actual bytes in this worktree. Nothing is transcribed from prose. The headline figures and how to reproduce each:

| number | value | how |
|---|---|---|
| worktree branch | `player-model-program` | `git -C <worktree> rev-parse --abbrev-ref HEAD` |
| documents indexed | 245 | walk of the scope above; `len(d['documents'])` in `DOCUMENT_INDEX.json` |
| flagged frozen | 93 | `graph_lib.frozen_violations([path])` imported from `orchestration/scripts/` and called on every indexed path |
| paths matching the `D_ewma_shrunk` Arm D marker | 0 | substring test over every indexed path |
| files whose contents mention `D_ewma_shrunk` | 81 | `git grep -l D_ewma_shrunk -- experiments/player_program` |
| findings in the V2 halt | 9 | `python -c "import json;print(len(json.load(open('experiments/player_program/stage2a/V2_STOP_CONDITION.json'))['findings']))"` |
| consistency checks run / disagreeing | 62 / 1 | see the checks table above; each compares a value a document states against a digest or count recomputed from the bytes |
| records in `ARTIFACT_LEDGER.jsonl` | 1 | count of non-blank lines |
| indexed paths that changed bytes during the build | 0 | every file hashed twice, first pass vs second |

The builder is a scratch script, not committed: this node's declared write scope is exactly `DOCUMENT_INDEX.json` and `DOCUMENT_INDEX.md`, and adding a third file would put the node outside its scope. Every figure above is reproducible from the command given, or from `DOCUMENT_INDEX.json` itself.

## What this node could NOT establish

1. **Whether the frozen coverage of Arm D is complete.** No path contains `D_ewma_shrunk`, and no document in the indexed scope enumerates the file paths that constitute Arm D. Arm D's bytes appear to be covered by the frozen-directory and frozen-file rules, but that is coverage *by coincidence of location*, and this node could not verify it is exhaustive.
2. **Whether the two `D_ewma_shrunk` readings denote the same object.** Both are recorded above, unreconciled.
3. **Whether any DERIVED file actually regenerates to its current bytes.** No generator was run — running one would write outside this node's scope. What was checked is narrower: whether a digest or count a derived file *states* matches the bytes it claims to summarise.
4. **Whether anything any indexed document claims is true.** That is outside this node's epistemic status by construction. In particular, nothing in this index establishes that any field is cutoff-valid, and no record here may be cited as evidence of availability, eligibility, admission or cutoff validity. A field having a row in a parquet file indexed here says only that the row exists.
5. **Completeness of the freeze record.** `ARTIFACT_LEDGER.jsonl` holds 1 record against 245 indexed files. The ledger is therefore **not** a complete history of frozen bytes, and this index is not a substitute for one — it is a single snapshot with no before/after.
6. **Stability.** The worktree was live: 29 nodes were RUNNING at snapshot and 38 indexed paths were untracked by git. The document count rose on every rebuild during this node's own execution. A digest taken later will differ for those paths.
7. **The 4 UNDETERMINED file(s)** listed above: generation could not be attributed by any signal this node measured.
8. **Anything outside the indexed scope.** The other 52 `experiments/*` directories, and the ~220 non-frozen `.py` files, were not indexed. If an authoritative claim lives there, this index does not know about it.
9. `experiments/player_program/stage2b/SEALED_RESULTS` was **not read**. It is a forbidden input for this node and was verified absent from disk rather than opened.

## Stop conditions

This node's stop condition is a finding that would change the primary target, the K0 structure, the inference structure, the candidate universe, the cutoff-valid feature set, or the leakage status. **No finding here does any of those.** Stated plainly so it is not read as understatement: the two findings above — that the Arm D freeze clause has zero path coverage through its own identifier, and that `D_ewma_shrunk` labels two objects in the record — are *governance* defects in how the freeze is enforced and how the incumbent is named. They do not alter the target, the universe, the folds, the K0 structure or any leakage judgement, and this node did not touch them. Both belong to `G03_FROZEN_PATH_GUARD`, which owns the guard; this node cannot and did not modify it.

---

Generated by the `G02_DOCUMENT_INDEX` node. The machine-readable form, with every field per record, is `DOCUMENT_INDEX.json` alongside this file. This node wrote nothing else: `REPORT.md` was deliberately not created, because the node's declared write scope is these two files and no more.
