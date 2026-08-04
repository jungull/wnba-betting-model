#!/usr/bin/env python
"""Materialise PROGRAM_GRAPH.json.

The graph is authored here rather than hand-edited as JSON so that write ownership stays
mechanically disjoint: every node's scope is derived from its lane and id, which makes an
accidental collision between two concurrently-schedulable nodes impossible to introduce by
typo. validate_graph.py still checks it independently.

Re-running this regenerates the node DEFINITIONS. It deliberately preserves any
`input_hashes` already frozen against a node, because those are evidence, not configuration.
"""

from __future__ import annotations

import sys

import graph_lib as G

PP = "experiments/player_program"
ORCH_REL = f"{PP}/orchestration"

# Lane -> workspace root. Every node writes under its own directory beneath these, so two
# nodes in different lanes can never contend, and two nodes in the same lane contend only if
# they are given the same id, which the id-uniqueness check already forbids.
LANE_ROOT = {
    "possession": f"{PP}/stage2b",
    "data": f"{PP}/data_lane",
    "operations": f"{PP}/ops_lane",
    "product": f"{PP}/product_lane",
    "future_research": f"{PP}/future_research",
    "governance": f"{ORCH_REL}/nodes",
}

# Read-only evidence every scientific node is entitled to.
FROZEN_EVIDENCE = [
    f"{PP}/stage2a/EVIDENCE_PACKET_V2.json",
    f"{PP}/stage2a/V2_STOP_CONDITION.json",
    f"{PP}/PROGRAM_STATE.json",
    f"{PP}/RESEARCH_CONTRACT_V1.md",
    f"{PP}/GATE_INVOCATION_CONTRACT.md",
]

# Files whose exposure would destroy a node's claim to independence.
IDEATION_FORBIDDEN = [
    f"{PP}/stage2a/HYPOTHESES_coordinator.md",
    f"{PP}/stage2a/HYPOTHESES_agent_pace_coaching.md",
    f"{PP}/stage2a/HYPOTHESES_agent_timeseries.md",
    f"{PP}/stage2a/HYPOTHESES_agent_opponent_env.md",
    f"{PP}/stage2a/HYPOTHESES_agent_roster_coldstart.md",
    f"{PP}/stage2a/HYPOTHESES_agent_adversarial.md",
    f"{PP}/stage2a/V2_HYPOTHESES_estimator.md",
    f"{PP}/stage2a/V2_HYPOTHESES_basketball.md",
    f"{PP}/stage2a/V2_HYPOTHESES_adversarial.md",
    f"{PP}/stage2a/SYNTHESIS.md",
    f"{PP}/stage2a/PACKET_ADDENDUM_coordinator.md",
]

RESULT_PATHS = [f"{PP}/stage2b/SEALED_RESULTS"]


def node(
    nid, title, lane, ntype, deps, role, epistemic,
    outputs=None, validators=None, criteria=None, stops=None,
    reads=None, writes=None, owned=None, inputs=None, forbidden=None,
    severity="B", merge="auto", human=False, status="BLOCKED",
    on_pass=None, on_fail=None, tools=None, no_tools=None, retries=2,
):
    root = LANE_ROOT[lane]
    ws = writes if writes is not None else [f"{root}/{nid}/"]
    return {
        "id": nid,
        "title": title,
        "lane": lane,
        "type": ntype,
        "status": status,
        "dependencies": deps,
        "input_artifacts": inputs if inputs is not None else list(FROZEN_EVIDENCE),
        "input_hashes": {},
        "forbidden_inputs": forbidden if forbidden is not None else list(RESULT_PATHS),
        "allowed_read_paths": reads if reads is not None else [PP + "/"],
        "allowed_write_paths": ws,
        "owned_files": owned if owned is not None else [],
        "allowed_tools": tools if tools is not None else ["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
        "disallowed_tools": no_tools if no_tools is not None else ["Agent"],
        "agent_role": role,
        "agent_prompt_path": f"{ORCH_REL}/prompts/{nid}.md",
        "epistemic_status": epistemic,
        "expected_outputs": outputs or [f"{root}/{nid}/REPORT.md"],
        "validation_commands": validators or [],
        "acceptance_criteria": criteria or [],
        "stop_conditions": stops or [
            "a finding would change the primary target, the K0 structure, the inference "
            "structure, the candidate universe, the cutoff-valid feature set or the leakage "
            "status -- HALT and raise, do not resolve it inside the node"
        ],
        "severity_on_failure": severity,
        "max_retries": retries,
        "merge_policy": merge,
        "human_gate": human,
        "on_pass": on_pass or [],
        "on_fail": on_fail or [],
    }


def build():
    N = []
    py = "python experiments/player_program/orchestration/scripts"

    # ---------------------------------------------------------------- governance
    N.append(node(
        "G00_LIVE_RECONCILIATION",
        "Reconcile live repository state, ancestry and frozen artifact hashes",
        "governance", "audit", [],
        "coordinator",
        "VERIFIED_PROJECT_STATE. Establishes what is actually true of the repository right "
        "now. Supersedes every relayed or remembered state claim, including this directive's.",
        outputs=[f"{ORCH_REL}/nodes/G00_LIVE_RECONCILIATION/RECONCILIATION.json"],
        validators=[f"{py}/reconcile_repo.py --expect-ancestor e79ae2c --expect-ancestor 32c8a6f "
                    f"--expect-ancestor db66a720"],
        criteria=[
            "branch, HEAD and working-tree state are read live, never quoted from a generated file",
            "e79ae2c, 32c8a6f and db66a720 are all ancestors of HEAD",
            "every pinned frozen artifact hash rederives exactly",
            "the complete changed-file list for db66a720..HEAD is recorded",
            "any file changed outside experiments/player_program/stage2a/ is named explicitly",
        ],
        severity="A", status="READY",
        on_pass=["G01_GRAPH_ENGINE", "G02_DOCUMENT_INDEX", "P20_INGEST_PENDING_ESTIMATOR"],
    ))

    N.append(node(
        "G01_GRAPH_ENGINE",
        "Persistent orchestration framework: graph, ledgers, validators, dispatcher",
        "governance", "implementation", ["G00_LIVE_RECONCILIATION"],
        "coordinator",
        "INFRASTRUCTURE. Carries no scientific claim. Its correctness is demonstrated by its "
        "own test suite; it establishes nothing about the model.",
        outputs=[
            f"{ORCH_REL}/GRAPH_POLICY.md", f"{ORCH_REL}/PROGRAM_GRAPH.json",
            f"{ORCH_REL}/GRAPH_STATE.json", f"{ORCH_REL}/NODE_CONTRACT.schema.json",
            f"{ORCH_REL}/FILE_OWNERSHIP.json", f"{ORCH_REL}/README.md",
            f"{ORCH_REL}/scripts/graphctl.py", f"{ORCH_REL}/scripts/validate_graph.py",
            f"{ORCH_REL}/scripts/reconcile_repo.py", f"{ORCH_REL}/scripts/hash_artifacts.py",
            f"{ORCH_REL}/scripts/dispatch_ready.py", f"{ORCH_REL}/scripts/validate_node.py",
            f"{ORCH_REL}/scripts/integrate_node.py", f"{ORCH_REL}/scripts/frozen_path_guard.py",
        ],
        validators=[
            f"{py}/validate_graph.py",
            f"{py}/graphctl.py state --check",
            "python experiments/player_program/orchestration/tests/test_graph_engine.py",
        ],
        criteria=[
            "validate_graph.py exits 0: acyclic, contract-valid, no live write-scope collision",
            "GRAPH_STATE.json reproduces byte-identically from graph + events",
            "the orchestration test suite passes",
            "no file outside experiments/player_program/orchestration/ is written",
        ],
        writes=[f"{ORCH_REL}/GRAPH_POLICY.md", f"{ORCH_REL}/PROGRAM_GRAPH.json",
                f"{ORCH_REL}/GRAPH_STATE.json", f"{ORCH_REL}/GRAPH_EVENTS.jsonl",
                f"{ORCH_REL}/DECISION_LEDGER.jsonl", f"{ORCH_REL}/ARTIFACT_LEDGER.jsonl",
                f"{ORCH_REL}/FILE_OWNERSHIP.json", f"{ORCH_REL}/NODE_CONTRACT.schema.json",
                f"{ORCH_REL}/README.md", f"{ORCH_REL}/scripts/", f"{ORCH_REL}/tests/",
                f"{ORCH_REL}/prompts/", f"{ORCH_REL}/reports/CURRENT_STATUS.md"],
        severity="A", status="BLOCKED",
    ))

    N.append(node(
        "G02_DOCUMENT_INDEX",
        "Index every authoritative document, contract, task card, ledger, receipt and frozen artifact",
        "governance", "audit", ["G00_LIVE_RECONCILIATION"],
        "fast documentation indexer",
        "VERIFIED_READ_ONLY_DERIVATION. A map of what exists with hashes. Carries no scientific "
        "judgement about whether any indexed claim is correct.",
        outputs=[f"{ORCH_REL}/reports/DOCUMENT_INDEX.json", f"{ORCH_REL}/reports/DOCUMENT_INDEX.md"],
        validators=["python -c \"import json,sys; d=json.load(open('experiments/player_program/"
                    "orchestration/reports/DOCUMENT_INDEX.json')); "
                    "sys.exit(0 if len(d['documents'])>40 and all('sha256' in x for x in d['documents']) else 1)\""],
        criteria=[
            "every indexed document carries a path, a sha256 and a one-line role",
            "frozen artifacts are flagged as frozen with their governing rule",
            "the index distinguishes DERIVED files from HAND-MAINTAINED files",
            "no document is summarised beyond what it says",
        ],
        writes=[f"{ORCH_REL}/reports/DOCUMENT_INDEX.json", f"{ORCH_REL}/reports/DOCUMENT_INDEX.md"],
        reads=[".", ], severity="C",
    ))

    N.append(node(
        "G03_FROZEN_PATH_GUARD",
        "Task-specific tests proving the frozen-path guard fails closed",
        "governance", "implementation", ["G01_GRAPH_ENGINE", "G02_DOCUMENT_INDEX"],
        "fast test engineer",
        "INFRASTRUCTURE. Demonstrates the guard rejects what it must reject. Does not modify "
        "any shared gate: enforcement is added at the call site, never inside feature_gate.py.",
        outputs=[f"{ORCH_REL}/tests/test_frozen_path_guard.py"],
        validators=["python experiments/player_program/orchestration/tests/test_frozen_path_guard.py"],
        criteria=[
            "a test proves a change to a frozen directory is rejected",
            "a test proves an edit to an existing registry record is rejected",
            "a test proves an append to the registry is permitted",
            "a test proves an Arm D path is rejected",
            "feature_gate.py, comparison_gate.py, gate_invocation.py are byte-unchanged",
        ],
        writes=[f"{ORCH_REL}/tests/test_frozen_path_guard.py"], severity="A",
    ))

    N.append(node(
        "G04_PROGRAM_ROADMAP_EXTRACTION",
        "Convert documented remaining program into graph nodes; unknown work becomes NEEDS_TARGET_CONTRACT",
        "governance", "documentation", ["G02_DOCUMENT_INDEX"],
        "roadmap extractor",
        "VERIFIED_READ_ONLY_DERIVATION of what the documents already commit to. Where "
        "documentation is absent the node must record NEEDS_TARGET_CONTRACT and must NOT "
        "invent a scientific target.",
        outputs=[f"{ORCH_REL}/reports/ROADMAP_EXTRACTION.json",
                 f"{ORCH_REL}/reports/ROADMAP_EXTRACTION.md"],
        validators=["python -c \"import json,sys; d=json.load(open('experiments/player_program/"
                    "orchestration/reports/ROADMAP_EXTRACTION.json')); "
                    "sys.exit(0 if d.get('items') else 1)\""],
        criteria=[
            "every proposed node cites the document and line that authorises it",
            "work with no documented target is marked NEEDS_TARGET_CONTRACT, not invented",
            "no proposed node claims authorisation to fit",
        ],
        writes=[f"{ORCH_REL}/reports/ROADMAP_EXTRACTION.json",
                f"{ORCH_REL}/reports/ROADMAP_EXTRACTION.md"],
        severity="C",
    ))

    # ---------------------------------------------------------------- possession halt lane
    N.append(node(
        "P20_INGEST_PENDING_ESTIMATOR",
        "Ingest and freeze the third V2 source (estimator) that returned after the halt",
        "possession", "integration", ["G00_LIVE_RECONCILIATION"],
        "coordinator",
        "POST_RULING_CONSTRAINED_DISCOVERY. The estimator source is the ORIGINAL run, not a "
        "replacement: it is recorded in V2_GENERATION_ORDER.json's original launch batch and "
        "its output hash is now pinned. It is NOT an independent free first pass.",
        outputs=[f"{PP}/stage2b/P20_INGEST_PENDING_ESTIMATOR/INGEST_RECEIPT.json"],
        validators=[f"{py}/reconcile_repo.py"],
        criteria=[
            "V2_HYPOTHESES_estimator.md exists and hashes to "
            "c4d6680612ade6c523c7a0bb592eeb999b5b14cffe0d21fa08552a0e5e8440df",
            "V2_GENERATION_ORDER.json records that hash in output_hashes",
            "the run is labelled ORIGINAL, not REPLACEMENT",
            "the pre-output generation-order artifact is retained through git history",
        ],
        severity="A",
    ))

    N.append(node(
        "P21_FREEZE_V2_HALT_PACKET",
        "Freeze the complete V2 halt packet: three source outputs, nine findings, scope reconciliation",
        "possession", "integration", ["P20_INGEST_PENDING_ESTIMATOR"],
        "coordinator",
        "POST_RULING_CONSTRAINED_DISCOVERY, frozen. Agreement with the original five-source "
        "round is post-ruling corroboration and is WEAKER evidence than that round's own "
        "convergence. This is not a final candidate-generation wave.",
        outputs=[f"{PP}/stage2b/P21_FREEZE_V2_HALT_PACKET/V2_HALT_PACKET.json"],
        validators=[f"{py}/reconcile_repo.py"],
        criteria=[
            "all three V2 source output hashes are recorded and rederive",
            "all nine findings S1-S9 are carried with their severities and affected dimensions",
            "the four tripped stop conditions are named",
            "the not-stop-conditions-but-recorded block is carried forward unedited",
            "V1 and V2 evidence packets are byte-unchanged",
        ],
        severity="A",
    ))

    remediation = [
        ("P22_POSTGAME_SURROGATE_GUARD",
         "S1: enforced invariant against current-game outcome-derived columns",
         "implementation", "leakage-enforcement engineer",
         "INFRASTRUCTURE + task-specific INVARIANT. Establishes that a prohibited column cannot "
         "silently enter a prediction frame. Establishes nothing about any candidate's accuracy.",
         ["a test proves unlagged master_team.minutes FAILS",
          "a test proves minutes/5 FAILS",
          "a test proves a renamed or linearly transformed current-game duration FAILS",
          "a test proves a correctly lagged prior-game duration PASSES when every cutoff check passes",
          "same-game joins fail closed",
          "construction receipts record the lag transformation and the source keys",
          "feature_gate.py is byte-unchanged: this is a Stage 2 wrapper, not a gate edit"]),
        ("P23_DIMENSION_CARDINALITY_GUARD",
         "S2: merge cardinality invariants preserving the 2,982-row / 1,491-game universe",
         "implementation", "data-integrity engineer",
         "INFRASTRUCTURE + task-specific INVARIANT. Proves a dimension merge cannot silently "
         "change the row universe. Does not establish that any dimension is scientifically usable.",
         ["every dimension merge declares explicit keys and expected cardinality",
          "row count, game key set and team-game key set are asserted unchanged",
          "duplicate primary keys are rejected and fan-out fails the merge",
          "null expansion is reported",
          "the duplicated team_id 1611661317 (PHO/PHX) is resolved ONLY from documented "
          "effective-date or season semantics; if it cannot be, the affected feature family is "
          "EXCLUDED rather than guessed",
          "deduplication by arbitrary first/last row order is not used anywhere"]),
        ("P24_INJURY_REGIME_LEDGER",
         "S3: split injury data into explicit epistemic regimes and report cutoff-valid coverage",
         "audit", "cutoff-validity auditor",
         "VERIFIED_READ_ONLY_DERIVATION. Classifies fields by epistemic regime. A field passing "
         "classification is ELIGIBLE for consideration, which is not the same as useful or admitted.",
         ["missed_game_* and every realised-participation or retrospective field is classified "
          "NOT A PREGAME FEATURE",
          "a field is usable only with a source timestamp at or before the declared pregame "
          "cutoff, documented designation semantics, and no derivation from the game outcome",
          "rows with missing or ambiguous timestamps are marked CUTOFF_UNPROVEN and excluded "
          "from the fitted feature universe while remaining in availability reports",
          "historical coverage is reported by season and by fold",
          "the 5,373 / 2,967 split of the 8,340 rows is reproduced or corrected with evidence"]),
        ("P25_OFFSET_DEPENDENCY_GUARD",
         "S4/S5: full-design offset and affine-dependency audit including own/opponent contrasts",
         "implementation", "identifiability engineer",
         "INFRASTRUCTURE + task-specific INVARIANT. Proves a design cannot smuggle the offset "
         "into substantive_features. Establishes nothing about which mechanism is real.",
         ["the audit runs on the COMPLETE design [offset | nuisance | candidate], never on "
          "candidate features in isolation",
          "a candidate that is an exact or near-exact affine function of the offset is REJECTED",
          "a candidate that is an exact function of the incumbent projection is REJECTED",
          "a pair of candidates that JOINTLY reconstruct the offset is REJECTED",
          "the identity own_est + opp_est == 2 * projected is reproduced and its rejection proven",
          "a single nonredundant contrast such as own_est - opp_est is permitted only with a "
          "preregistered exact formula, fold-local full rank, and no offset reconstruction",
          "recalibration is a SEPARATE hypothesis family with its own nested null and its own "
          "family-level multiplicity accounting; a calibration parameter may not hide inside a "
          "substantive-feature arm",
          "feature_gate.py is byte-unchanged"]),
        ("P26_ARM_SPECIFIC_K0_CONTRACT",
         "S6/S9: the K0_MATCHED[arm_id] contract and machine-readable schema",
         "documentation", "control-design methodologist",
         "CONTRACT. Defines what a matched null must be for each kind of arm. It is a "
         "specification, not evidence, and it decides no arm's fate.",
         ["K0_MATCHED is defined per arm_id, not as one universal object",
          "for every arm the matched null holds identical rows, target, folds, weights, offset, "
          "fallback machinery, nuisance terms and lower-order structural terms",
          "the matched null excludes ONLY the treatment mechanism under test",
          "for a calibration-only arm the matched null fixes the tested parameter at its "
          "incumbent/null value (slope fixed at 1; the preregistered lower-order intercept structure)",
          "for a substantive-feature arm K0 contains every non-substantive structural degree of "
          "freedom granted to the candidate and excludes the substantive terms",
          "a candidate with tier interactions has lower-order tier main effects in its K0",
          "no arm receives credit for free re-centring, changed fallback, or a more flexible estimator",
          "K0_FLAT is marked diagnostic only",
          "a machine-readable schema validates a K0 specification against its arm"]),
        ("P27_FOLD_LOCAL_ESTIMABILITY_GUARD",
         "S7: fold-local rank, support, variance and degeneracy checks",
         "implementation", "numerical-diagnostics engineer",
         "INFRASTRUCTURE + task-specific INVARIANT. Proves an arm/fold is estimable before it is "
         "fitted. Does not establish that an estimable arm is a real effect.",
         ["checks run separately for each outer training fold AND for the final design",
          "the design-rank audit includes the offset and nuisance terms, not features alone",
          "zero-variance, unique-level counts, treatment support by game cluster and a "
          "condition-number check are all reported per fold",
          "candidate and null parameter counts are reconciled",
          "a pooled pass with a term absent in a fold is never silently reported as a pass",
          "a fold-local active-set rule is permitted only if preregistered before results, based "
          "solely on training-fold support, applied symmetrically, incapable of selecting on test "
          "performance, and fully recorded in the receipt",
          "otherwise the arm/fold is marked prospectively UNEVALUABLE",
          "the S7 measurement is reproduced: a tier indicator identically zero in four of six folds"]),
        ("P28_PRIMARY_SECONDARY_ORDERING_CONTRACT",
         "Possession-first adjudication; prohibit downstream OT-mismatch arbitrage",
         "documentation", "adjudication methodologist",
         "CONTRACT. Fixes the order in which evidence may be consulted. Prevents a secondary "
         "number from rescuing a primary failure; decides no arm's fate itself.",
         ["a candidate must pass its registered PRIMARY possession-target gate before it may "
          "enter the frozen turnover scorer",
          "the primary verdict is frozen before any downstream number is computed",
          "a candidate improving downstream turnover MAE while WORSENING the primary "
          "regulation-equivalent possession target FAILS",
          "trailing overtime rate, or any feature whose only benefit channel is arbitraging the "
          "raw/regulation-equivalent exposure mismatch, may not be credited",
          "the documented scorer mismatch is restated, not repaired: the scorer is frozen"]),
        ("P29_TIP_TIME_AND_COVERAGE_AUDIT",
         "Resolve the fold-aligned tip-time null pattern and rule on tip-derived eligibility",
         "audit", "coverage auditor",
         "VERIFIED_READ_ONLY_DERIVATION. Determines whether a null mask is separable from fold "
         "identity. A coverage finding is not a licence to admit a feature.",
         ["the reported pattern is reproduced or corrected: 1,219 of 1,495 games null, none in 2021",
          "the null mask's correlation with fold identity is measured explicitly",
          "a feature is NOT admitted merely because some seasons have coverage",
          "if the null mask is not separable from fold identity, tip-derived features are ruled "
          "INELIGIBLE for this wave and the reason is recorded",
          "the tip_times.csv provenance question is addressed: it is odds-derived and covers "
          "2022-2026, which sits oddly beside 'market odds unavailable historically'"]),
        ("P2A_POSSESSION_COLUMN_ADJUDICATION",
         "S8: adjudicate the 32 possession columns the availability table never named",
         "audit", "schema reconciliation auditor",
         "VERIFIED_READ_ONLY_DERIVATION. Closes a coordinator error: the packet dumped 48 column "
         "names under context_availability and the gating availability table named none of them. "
         "Adjudication makes a column ELIGIBLE or PROHIBITED; it admits nothing.",
         ["all 48 columns of possessions_raw_v2 are enumerated and individually adjudicated",
          "is_overtime, score_diff_offense_start, score_diff_offense_end, abs_score_diff_start, "
          "regulation_seconds_remaining and non_competitive_conservative are classified as "
          "REALISED TARGET-GAME OUTCOMES and are lagged-use-only",
          "the 99.789% valid-ten-lineup coverage over 238,563 possessions is reproduced or corrected",
          "each column receives exactly one of ELIGIBLE / LAGGED_USE_ONLY / PROHIBITED / "
          "CUTOFF_UNPROVEN with its evidence",
          "no column is admitted on availability grounds alone"]),
    ]

    for nid, title, ntype, role, epis, crit in remediation:
        N.append(node(
            nid, title, "possession", ntype, ["G01_GRAPH_ENGINE"], role, epis,
            outputs=[f"{PP}/stage2b/{nid}/REPORT.md", f"{PP}/stage2b/{nid}/FINDINGS.json"],
            validators=[f"python {PP}/stage2b/{nid}/TESTS.py"] if ntype == "implementation"
                       else [f"python -c \"import json;json.load(open('{PP}/stage2b/{nid}/FINDINGS.json'))\""],
            criteria=crit, severity="A",
        ))

    N.append(node(
        "P30_EVIDENCE_PACKET_V3",
        "Build and freeze EVIDENCE_PACKET_V3 with an immutable correction addendum",
        "possession", "integration",
        ["P21_FREEZE_V2_HALT_PACKET"] + [r[0] for r in remediation],
        "coordinator",
        "FROZEN EVIDENCE. V3 supersedes V2 as the basis for candidate selection. V1 and V2 are "
        "historical records and are NOT edited. V3 states explicitly what was withdrawn, "
        "corrected, left unchanged and left unresolved.",
        outputs=[f"{PP}/stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.json",
                 f"{PP}/stage2b/P30_EVIDENCE_PACKET_V3/EVIDENCE_PACKET_V3.sha256"],
        validators=[f"{py}/reconcile_repo.py"],
        criteria=[
            "V1 and V2 hash unchanged to f373e3ee… and 3a35ae73…",
            "V3 carries the existing valid V2 material plus an immutable correction addendum",
            "V3 carries postgame-surrogate enforcement, dimension-merge cardinality rules, injury "
            "regime classification, offset-dependence rules, arm-specific K0 rules, fold-local "
            "estimability rules and primary-before-secondary ordering",
            "V3 carries an updated cutoff-validity table covering all 48 possession columns",
            "V3 records full artifact hashes",
            "V3 states explicitly what was withdrawn, corrected, unchanged and unresolved",
            "no unresolved issue remains that changes the target unit, K0 structure, inference, "
            "candidate universe, cutoff-valid feature set or leakage status",
        ],
        severity="A", merge="coordinator",
    ))

    N.append(node(
        "P31_FINAL_V3_IDEATION",
        "Final clean ideation wave: six independent roles, V3 only, no source sees another output",
        "possession", "audit", ["P30_EVIDENCE_PACKET_V3"],
        "six independent scientific sources",
        "INDEPENDENT FIRST-PASS IDEATION under V3. Structural independence: each source runs "
        "against an isolated directory holding only V3 and its prompt. Raw outputs are frozen and "
        "hashed before any other source or synthesis can read them. This is the final first-pass "
        "wave unless V3 is later invalidated by a newly proven Severity A defect.",
        outputs=[f"{PP}/stage2b/P31_FINAL_V3_IDEATION/GENERATION_ORDER_V3.json"],
        validators=[f"python -c \"import json;d=json.load(open('{PP}/stage2b/P31_FINAL_V3_IDEATION/"
                    f"GENERATION_ORDER_V3.json'));assert len(d['output_hashes'])>=6\""],
        criteria=[
            "at least six roles: calibration and control structure; time-series and shrinkage; "
            "opponent and basketball mechanism; cold-start and fallback; cutoff-validity and "
            "leakage; adversarial statistics and identifiability",
            "each source's raw output is hashed before any other source could read it",
            "no source read another source's output, the synthesis, or coordinator hypotheses",
            "the generation-order artifact records the forbidden-file list given to each source",
            "a retry is labelled RETRY and does not increase the independent source count",
        ],
        severity="A", merge="coordinator",
    ))

    chain = [
        ("P32_CANDIDATE_SYNTHESIS", "Deduplicate into mechanistically distinct families; return complete arm definitions",
         "decision", "coordinator + two independent reviewers",
         "SYNTHESIS. Reduces sources to families. Rejection here is a design decision, not an "
         "empirical result: nothing has been fitted.",
         ["families are mechanistically distinct, not textually distinct",
          "hyperparameters are separated from hypotheses",
          "offset reconstructions, postgame surrogates, cutoff-unproven injury fields, unsafe "
          "fan-out features, fold-degenerate candidates and duplicate formulations are rejected "
          "with a named reason each",
          "a candidate whose only value is downstream mismatch exploitation is rejected",
          "complete arm definitions are returned, not counts",
          "disagreement between reviewers is preserved, not averaged"]),
        ("P33_PREREGISTRATION_DRAFT", "Freeze every retained arm's complete specification",
         "documentation", "preregistration author",
         "PREREGISTRATION DRAFT. Not yet frozen; not yet authorisation to fit.",
         ["every arm freezes: arm ID, mechanism, formula, target, exact features, lineage, cutoff "
          "evidence, fallback, cold-start behaviour, hyperparameter handling, K0_MATCHED[arm], "
          "folds, rows, weights, seeds, inference, multiplicity family, primary gate, secondary "
          "diagnostics and expected failure mode",
          "every arm's expected failure mode is stated before any fit",
          "the 2,982-row / 1,491-cluster universe is declared and games are never split across "
          "folds or cluster-bootstrap draws"]),
        ("P34_PREREGISTRATION_RED_TEAM", "Independent adversarial review of the preregistration",
         "audit", "independent reviewers per dimension",
         "ADVERSARIAL REVIEW. Reviewers are independent of the preregistration author. A clean "
         "review does not make an arm true; it makes it fittable.",
         ["separate independent reviewers for leakage, offset dependence, K0 parity, fold "
          "estimability, multiplicity, target-unit consistency and operational relevance",
          "no reviewer authored the preregistration",
          "every Severity A finding is closed or the arm is withdrawn",
          "disagreement is preserved"]),
        ("P35_FREEZE_TASK_CARDS", "Freeze task cards and append registry records",
         "integration", "coordinator",
         "FROZEN PREREGISTRATION. Standing conditional authorisation: freezing happens "
         "automatically once every P34 Severity A finding is closed. Registry records are "
         "APPENDED; the existing 41 are never edited.",
         ["every P34 Severity A finding is closed",
          "task cards are frozen and hashed",
          "new registry records are APPENDED only; the existing 41 records are byte-identical",
          "the append is made by a single writer"]),
        ("P36_IMPLEMENT_ARMS", "Implement each arm, K0_FLAT, each K0_MATCHED, the shared runner and receipts",
         "implementation", "one implementation agent per arm, isolated worktrees",
         "IMPLEMENTATION. Blinded: no agent may inspect challenger performance. Unit, synthetic, "
         "identity and schema tests only.",
         ["one node and worktree per arm, plus separate nodes for K0_FLAT, each arm's K0_MATCHED, "
          "the shared task-specific runner and receipt integration",
          "no implementation agent inspects comparative historical performance",
          "no canonical artifact is written",
          "Arm D is byte-unchanged"]),
        ("P37_IMPLEMENTATION_AUDIT", "Verify code matches formula, gates, receipts, parity",
         "audit", "auditors independent of the implementers",
         "IMPLEMENTATION AUDIT. Establishes that the code is the preregistered code. Establishes "
         "nothing about results, which remain sealed.",
         ["code/formula identity is verified line by line against the frozen preregistration",
          "full-design gates, receipts and fold-local estimability all pass",
          "row parity is byte-identical across arms, K0_FLAT, K0_MATCHED and the incumbent",
          "no canonical writes, no Arm D change, no result access",
          "no auditor implemented the arm it audits"]),
    ]
    prev = "P31_FINAL_V3_IDEATION"
    for nid, title, ntype, role, epis, crit in chain:
        N.append(node(nid, title, "possession", ntype, [prev], role, epis,
                      outputs=[f"{PP}/stage2b/{nid}/REPORT.md", f"{PP}/stage2b/{nid}/SPEC.json"],
                      validators=[f"python -c \"import json;json.load(open('{PP}/stage2b/{nid}/SPEC.json'))\""],
                      criteria=crit, severity="A", merge="coordinator"))
        prev = nid

    N.append(node(
        "P38_BLINDED_FIT", "Execute the frozen preregistered experiment into a sealed result directory",
        "possession", "experiment", ["P37_IMPLEMENTATION_AUDIT"], "runner",
        "SEALED RESULTS. Standing conditional authorisation: the fit executes automatically once "
        "P37 passes, because the preregistration and the implementation audit are exactly the "
        "conditions the contract requires. Outputs are sealed and unread until P39 verifies them.",
        outputs=[f"{PP}/stage2b/SEALED_RESULTS/MANIFEST.json"],
        validators=[f"python -c \"import json;json.load(open('{PP}/stage2b/SEALED_RESULTS/MANIFEST.json'))\""],
        criteria=["results are written into the sealed directory and are not opened by the runner",
                  "the exact code commit, data hashes, row universe, folds, K0 pairing and seeds "
                  "are recorded in the manifest"],
        writes=[f"{PP}/stage2b/SEALED_RESULTS/"], severity="A", merge="coordinator",
        forbidden=[], retries=1,
    ))
    N.append(node(
        "P39_RESULT_INTEGRITY", "Verify sealed outputs without interpreting which arm won",
        "possession", "audit", ["P38_BLINDED_FIT"], "result-integrity agent",
        "INTEGRITY VERIFICATION. Confirms the run is the preregistered run. The verifier does not "
        "interpret, rank or report which arm performed better.",
        outputs=[f"{PP}/stage2b/P39_RESULT_INTEGRITY/INTEGRITY_REPORT.json"],
        validators=[f"python -c \"import json;json.load(open('{PP}/stage2b/P39_RESULT_INTEGRITY/INTEGRITY_REPORT.json'))\""],
        criteria=["exact code commit, data hashes, row universe, folds, K0 pairing and seeds all verify",
                  "every declared output is present",
                  "the report contains no comparative performance statement",
                  "the integrity agent is not the adjudication agent"],
        severity="A", merge="coordinator",
    ))
    N.append(node(
        "P40_PRIMARY_ADJUDICATION", "Open results; apply the preregistered primary possession gates",
        "possession", "decision", ["P39_RESULT_INTEGRITY"], "adjudication agent + independent reviewer",
        "PRIMARY ADJUDICATION. The first context permitted to see results. Criteria are the "
        "preregistered ones and are not altered after seeing outcomes.",
        outputs=[f"{PP}/stage2b/P40_PRIMARY_ADJUDICATION/ADJUDICATION.json"],
        validators=[f"python -c \"import json;json.load(open('{PP}/stage2b/P40_PRIMARY_ADJUDICATION/ADJUDICATION.json'))\""],
        criteria=["results are opened only after P39 passed",
                  "the preregistered primary possession gate and prospective multiplicity plan are "
                  "applied exactly as frozen",
                  "no criterion is altered after results were observed",
                  "nulls and negative results are preserved as results"],
        severity="A", merge="coordinator",
    ))
    N.append(node(
        "P41_DOWNSTREAM_TURNOVER_CONFIRMATION", "Downstream turnover scoring for arms that passed the primary gate only",
        "possession", "experiment", ["P40_PRIMARY_ADJUDICATION"], "runner",
        "SECONDARY EVIDENCE. Operational relevance only. A downstream result can never rescue an "
        "arm that failed or worsened the primary possession target.",
        outputs=[f"{PP}/stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION/DOWNSTREAM.json"],
        validators=[f"python -c \"import json;json.load(open('{PP}/stage2b/P41_DOWNSTREAM_TURNOVER_CONFIRMATION/DOWNSTREAM.json'))\""],
        criteria=["only arms that passed the primary possession gate are run",
                  "the frozen turnover scorer is used unmodified",
                  "no arm is credited for exploiting the raw/regulation-equivalent mismatch"],
        severity="A", merge="coordinator",
    ))
    N.append(node(
        "P42_SCIENTIFIC_COMPLETION", "Accepted/null/failed decisions, bounded effects, uncertainty, limitations",
        "possession", "decision", ["P41_DOWNSTREAM_TURNOVER_CONFIRMATION"], "coordinator + two reviewers",
        "SCIENTIFIC COMPLETION REPORT. States what the wave established and what it did not. "
        "Does not itself promote anything.",
        outputs=[f"{PP}/stage2b/P42_SCIENTIFIC_COMPLETION/COMPLETION.md"],
        validators=[],
        criteria=["accepted / null / failed decision for every arm",
                  "bounded effect estimates with uncertainty",
                  "failure explanations and downstream implications",
                  "unresolved limitations stated",
                  "a prospective-confirmation recommendation is given"],
        severity="A", merge="coordinator",
    ))
    N.append(node(
        "P43_CHAMPION_DECISION", "Whether to replace Arm D as the frozen champion",
        "possession", "decision", ["P42_SCIENTIFIC_COMPLETION"], "USER",
        "USER DECISION. Replacing the champion, modifying a canonical artifact, or promoting to "
        "production is reserved to the user under GRAPH_POLICY.md section 6.",
        outputs=[], validators=[], criteria=[],
        stops=["reached: this node exists to stop"],
        severity="A", merge="never", human=True, status="USER_REQUIRED", retries=0,
    ))

    # ---------------------------------------------------------------- data lane
    data = [
        ("D10_FIELD_AVAILABILITY_LEDGER",
         "Field-level cutoff-validity coverage across every candidate source",
         "VERIFIED_READ_ONLY_DERIVATION. An availability ledger. Availability is not eligibility "
         "and eligibility is not admission.",
         ["coverage is reported per field for injuries, transactions, schedules, rest, venues, "
          "travel, elevation, time zones, tip times, roster continuity, coaching and opponent history",
          "each field carries a cutoff-validity verdict with its evidence",
          "a field with no source timestamp is CUTOFF_UNPROVEN, never assumed valid",
          "coverage is broken out by season and by fold, not pooled"]),
        ("D11_LIVE_INFORMATION_CAPTURE",
         "Timestamped prospective capture with first-seen and change history",
         "PROSPECTIVE CAPTURE INFRASTRUCTURE. Builds the record that would make future features "
         "cutoff-provable. Creates no historical evidence and repairs no historical gap.",
         ["capture covers injury designation changes, lineups, starters, minute restrictions, "
          "transactions, coaching changes, odds and attributable news",
          "first-seen timestamp and full change history are preserved, never overwritten",
          "a record is never backdated",
          "the capture writes only under its own lane directory"]),
        ("D12_COACHING_HISTORY",
         "Retrospectively auditable coaching table",
         "REFERENCE DATA. Auditable history only. Explicitly NOT admitted to any experiment "
         "before a cutoff review.",
         ["every coaching record carries a source and an effective date",
          "the table is not admitted to an experiment before cutoff review",
          "ambiguous tenure boundaries are marked, not smoothed"]),
        ("D13_ARENA_TRAVEL_DIMENSION",
         "Unique effective-dated team/arena/travel dimension with cardinality tests",
         "REFERENCE DATA + INVARIANT. Fixes the S2 fan-out hazard at its source.",
         ["the dimension is unique on its declared key, with effective dates",
          "cardinality tests prove a merge cannot fan out",
          "the PHO/PHX duplicate is resolved from documented effective-date semantics or the "
          "affected family is excluded",
          "elevation, timezone and travel fields carry their derivation"]),
        ("D14_ENTITY_RESOLUTION_AND_COLD_START",
         "Tests and design artifacts for aliases, new signings, zero-history players, team transitions",
         "DESIGN ARTIFACT + TESTS. Defines behaviour at the boundaries. Establishes no effect.",
         ["transferred-player aliases resolve to one identity with evidence",
          "new signings and players with no historical rows have declared, tested behaviour",
          "team-history transitions are handled explicitly",
          "cold-start behaviour is a declared fallback, never a silent default"]),
    ]
    for nid, title, epis, crit in data:
        N.append(node(nid, title, "data", "audit" if "LEDGER" in nid or "HISTORY" in nid else "implementation",
                      ["G01_GRAPH_ENGINE"], "data and cutoff-validity engineer", epis,
                      outputs=[f"{PP}/data_lane/{nid}/REPORT.md", f"{PP}/data_lane/{nid}/FINDINGS.json"],
                      validators=[f"python -c \"import json;json.load(open('{PP}/data_lane/{nid}/FINDINGS.json'))\""],
                      criteria=crit, severity="B"))

    # ---------------------------------------------------------------- infrastructure lane
    infra = [
        ("I10_GENERIC_CLUSTERED_INFERENCE",
         "Reusable game-clustered bootstrap and interval utilities in a task-isolated namespace",
         "INFRASTRUCTURE. Utilities in an isolated namespace. Shared adoption requires a separate "
         "review node; nothing here amends a shared contract.",
         ["games are never split across cluster-bootstrap draws",
          "the 2,982-row / 1,491-cluster distinction is honoured and both are reported",
          "seeds are explicit and results reproduce exactly",
          "the namespace is task-isolated; no shared contract is modified"]),
        ("I11_BLINDED_RESULT_PACKAGING",
         "Generic sealed-result and integrity-manifest tooling",
         "INFRASTRUCTURE. Enforces the seal mechanically rather than by convention.",
         ["a sealed directory cannot be read by the writing process",
          "the manifest binds code commit, data hashes, row universe, folds, K0 pairing and seeds",
          "opening a seal is a separate, logged operation"]),
        ("I12_DESIGN_DEPENDENCY_AUDIT",
         "Reusable full-design offset/dependency audits without modifying frozen shared gates",
         "INFRASTRUCTURE. Call-site enforcement. feature_gate.py is not touched.",
         ["the audit accepts the complete design [X | offset | nuisance]",
          "augmented rank, condition number and affine-reconstruction checks are included",
          "feature_gate.py, comparison_gate.py and gate_invocation.py are byte-unchanged"]),
        ("I13_REPRODUCIBILITY_RUNNER",
         "Deterministic commands, seed manifests and artifact reconciliation",
         "INFRASTRUCTURE. Makes a run rerunnable and checkable. Proves nothing scientific.",
         ["a recorded run reproduces byte-identically from its manifest",
          "seeds, code commit and input hashes are all bound",
          "a divergence is reported as a failure, never silently accepted"]),
    ]
    for nid, title, epis, crit in infra:
        N.append(node(nid, title, "operations", "implementation", ["G01_GRAPH_ENGINE"],
                      "experiment-infrastructure engineer", epis,
                      outputs=[f"{PP}/ops_lane/{nid}/REPORT.md"],
                      validators=[f"python {PP}/ops_lane/{nid}/TESTS.py"],
                      criteria=crit, severity="B"))

    ops = [
        ("O10_LATE_RECORD_AUDIT_CLASSIFICATION", "Classify late-arriving records in the prospective capture audit"),
        ("O11_OBLIGATION_DISCOVERY_LEAD_WINDOW", "Obligation-discovery lead window defect"),
        ("O12_PER_GAME_EXECUTION_SCOPE", "Per-game execution scope defect"),
        ("O13_LEAD_WINDOW_LATENCY", "Lead-window latency defect"),
        ("O14_OPS_ENTITY_RESOLUTION", "Entity resolution in the prospective capture path"),
        ("O15_LOGOUT_SURVIVAL", "Logout survival for the capture scheduler"),
    ]
    for nid, title in ops:
        N.append(node(nid, title, "operations", "audit", ["G01_GRAPH_ENGINE"],
                      "operations defect analyst",
                      "DESIGN OR IMPLEMENTATION ANALYSIS of a documented prospective-capture defect. "
                      "Isolated branch only. This lane does not block possession research unless it "
                      "changes the historical feature evidence.",
                      outputs=[f"{PP}/ops_lane/{nid}/REPORT.md", f"{PP}/ops_lane/{nid}/FINDINGS.json"],
                      validators=[f"python -c \"import json;json.load(open('{PP}/ops_lane/{nid}/FINDINGS.json'))\""],
                      criteria=["the defect is reproduced or shown not to reproduce, with evidence",
                                "the fix is designed and tested in an isolated branch",
                                "no shared schema or contract change is merged from this node",
                                "if the defect changes historical feature evidence, it is escalated "
                                "to the possession lane rather than fixed quietly"],
                      severity="C"))

    # Remediation family, created by the coordinator from confirmed defects rather than seeded.
    #
    # Three nodes failed the SAME way: they produced substantive machine-readable artifacts,
    # working code and evidence, and then did not write their declared prose REPORT.md. In two of
    # the three the independent verifier still scored PASS_WITH_DEFECTS -- once while itself
    # listing the missing output under failed_criteria. The mechanical expected-output check
    # caught all three. That is the argument for running both an independent reviewer and a
    # mechanical validator: they fail differently.
    #
    # A remediation writes up evidence that ALREADY EXISTS. It may not add a finding the original
    # run did not make -- that would be an unregistered second attempt wearing a repair's clothes.
    REPORT_REMEDIATION = [
        ("R10_O15_REPORT_REMEDIATION", "O15_LOGOUT_SURVIVAL", "ops_lane", "operations"),
        ("R11_P25_REPORT_REMEDIATION", "P25_OFFSET_DEPENDENCY_GUARD", "stage2b", "possession"),
        ("R12_P27_REPORT_REMEDIATION", "P27_FOLD_LOCAL_ESTIMABILITY_GUARD", "stage2b", "possession"),
        ("R13_I12_REPORT_REMEDIATION", "I12_DESIGN_DEPENDENCY_AUDIT", "ops_lane", "operations"),
    ]
    for nid, parent, sub, lane in REPORT_REMEDIATION:
        root = LANE_ROOT[lane]
        N.append(node(
            nid,
            f"Write the missing {parent} report from its own preserved evidence",
            lane, "documentation", ["G01_GRAPH_ENGINE"], "documentation engineer",
            f"REMEDIATION of a confirmed missing declared output. It writes up evidence that "
            f"ALREADY EXISTS in {sub}/{parent}/ and may not add a finding the original run did "
            f"not make. Its parent finding is {parent}'s validation_failed event, which is "
            f"preserved and not rewritten.",
            outputs=[f"{root}/{nid}/REPORT.md"],
            validators=[f"python -c \"import pathlib,sys;p=pathlib.Path('{root}/{nid}/REPORT.md');"
                        f"sys.exit(0 if p.exists() and p.stat().st_size>1000 else 1)\""],
            criteria=[
                f"the report is derived ONLY from files already present in {PP}/{sub}/{parent}/",
                "no new measurement is performed and no new finding is introduced",
                "the epistemic status of the original node is carried verbatim",
                f"the report states that {parent}'s declared output was missing and that this is "
                f"a remediation, not the original run",
                f"nothing under {PP}/{sub}/{parent}/ is modified",
                "every defect the independent verifier raised against the original node is "
                "carried into the report rather than quietly dropped",
            ],
            severity="C",
        ))

    # Substantive remediations -- these correct a WRONG CLAIM, not a missing file, so each one
    # must re-measure rather than re-narrate.
    N.append(node(
        "R14_D10_COACHING_CORRECTION",
        "Correct D10's manufactured negative on the coaching family and re-measure its coverage",
        "data", "audit", ["G01_GRAPH_ENGINE"], "cutoff-validity auditor",
        "REMEDIATION of a confirmed FALSE NEGATIVE. D10 reported the coaching family ABSENT with "
        "0 coverage on an assertion contradicted by the bytes of a file it had itself loaded. "
        "This node RE-MEASURES; it may not simply restate D12's numbers, because relaying an "
        "unverified figure is the failure mode that produced the defect.",
        outputs=[f"{PP}/data_lane/R14_D10_COACHING_CORRECTION/CORRECTION.json",
                 f"{PP}/data_lane/R14_D10_COACHING_CORRECTION/REPORT.md"],
        validators=[f"python -c \"import json;json.load(open('{PP}/data_lane/"
                    f"R14_D10_COACHING_CORRECTION/CORRECTION.json'))\""],
        criteria=[
            "the 49 front_office rows in data/injury_history/injury_history.csv are enumerated "
            "and classified, and the ~2,930 COACH'S DECISION rows are explicitly excluded as noise "
            "rather than counted as coaching identity",
            "coverage by season and by fold is RE-MEASURED, not copied from D12",
            "the corrected verdict is PRESENT_RETROSPECTIVE / CUTOFF_UNPROVEN, and the "
            "cutoff_valid count stays 0 -- presence is not cutoff validity",
            "the correction states how the false negative was produced, so the same search error "
            "is not repeated",
            "D10's original ledger is NOT edited; the correction is a separate artifact",
        ],
        severity="B",
    ))

    N.append(node(
        "R15_G02_INDEX_CLASSIFICATION",
        "Repair the DERIVED vs HAND-MAINTAINED classification in the document index",
        "governance", "implementation", ["G01_GRAPH_ENGINE"], "documentation engineer",
        "REMEDIATION of a confirmed misclassification. The index exists and is useful; the "
        "criterion it failed is the one that makes it safe to ACT on, since treating a "
        "hand-maintained contract as regenerable invites someone to regenerate it.",
        outputs=[f"{ORCH_REL}/reports/DOCUMENT_INDEX_CORRECTION.json"],
        validators=[f"python -c \"import json;json.load(open('{ORCH_REL}/reports/"
                    f"DOCUMENT_INDEX_CORRECTION.json'))\""],
        criteria=[
            "classification is evidenced per file -- a generator that writes it, or a header "
            "declaring it -- never inferred from the file extension alone",
            "RESEARCH_CONTRACT_V1.md, GRAPH_POLICY.md, README.md and the handoffs are corrected "
            "to HAND_MAINTAINED",
            "a file claiming DERIVED names the generator that produces it",
            "the self-reference case is handled: the index itself is DERIVED",
            "the original DOCUMENT_INDEX.json is NOT edited; the correction is separate",
        ],
        severity="C",
        writes=[f"{ORCH_REL}/reports/DOCUMENT_INDEX_CORRECTION.json"],
    ))

    N.append(node(
        "R16_I11_SEAL_HONESTY",
        "Make I11's seal claim honest: obfuscation is not blinding",
        "operations", "implementation", ["G01_GRAPH_ENGINE"], "blinding infrastructure engineer",
        "REMEDIATION of an OVERSTATED ACCEPTANCE CRITERION. An independent verifier reconstructed "
        "the plaintext of both sealed payloads in about ten lines from public inputs. Blinding for "
        "the possession experiment rests on PROCESS separation enforced by the graph, not on "
        "cryptography; this node removes the temptation to treat the crypto as a second line of "
        "defence when it is not one.",
        outputs=[f"{PP}/ops_lane/R16_I11_SEAL_HONESTY/REPORT.md",
                 f"{PP}/ops_lane/R16_I11_SEAL_HONESTY/TESTS.py"],
        validators=[f"python {PP}/ops_lane/R16_I11_SEAL_HONESTY/TESTS.py"],
        criteria=[
            "the reconstruction attack is reproduced as an executable test that PASSES when the "
            "plaintext is recoverable -- the defect is demonstrated, not described",
            "the criterion 'a sealed directory cannot be read by the writing process' is either "
            "MET by a mechanism that survives the attack, or explicitly WITHDRAWN and replaced by "
            "the process-separation guarantee the graph actually enforces",
            "no claim of cryptographic blinding survives that the test does not support",
            "the manifest binding, which was sound, is retained",
            "I11's own artifacts are NOT edited",
        ],
        severity="B",
    ))

    N.append(node(
        "O16_SHARED_SCHEMA_ADOPTION", "Merge a shared schema or contract change proposed by the operations lane",
        "operations", "decision", [o[0] for o in ops] + ["R10_O15_REPORT_REMEDIATION"], "USER",
        "USER DECISION. Merging a shared schema or contract change is USER_REQUIRED: it crosses "
        "the boundary between the isolated operations lane and contracts other threads depend on. "
        "Confirmed at wave 3: the operations lane's targets (prospective_pair/should_run_base.py, "
        "coverage_audit.py) live on branch data-refresh-2026 and are ABSENT from this branch, so "
        "adoption is a cross-branch change as well as a shared-contract one.",
        outputs=[], validators=[], criteria=[],
        stops=["reached: this node exists to stop"],
        severity="A", merge="never", human=True, status="USER_REQUIRED", retries=0,
    ))

    # ---------------------------------------------------------------- product lane
    product = [
        ("U10_PREDICTION_API_SCHEMA", "Model-agnostic versioned response schema built against fixtures",
         ["the schema is model-agnostic: no possession challenger is hard-coded",
          "the response carries game IDs, model version, artifact hashes, input freshness, "
          "projections, uncertainty, warnings, component explanations, market comparison and "
          "audit metadata",
          "it is versioned and built against fixtures, not live model output"]),
        ("U11_UI_SHELL", "UI shell built against fixtures or frozen outputs",
         ["the UI runs entirely against fixtures or frozen outputs",
          "no possession challenger is hard-coded",
          "an absent or stale input renders as a warning, never as a number"]),
        ("U12_PREDICTION_HISTORY", "Immutable prediction-history and model-version views",
         ["prediction history is immutable and append-only",
          "each prediction is bound to its model version and artifact hashes",
          "a revised prediction appears as a new record, never as an edit"]),
        ("U13_MONITORING_INTERFACE", "Stale-input, missing-lineup, failed-job and rollback visibility",
         ["stale inputs, missing lineups and failed jobs are each individually visible",
          "rollback state is visible",
          "a silent failure is impossible: absence of data renders as an explicit alert"]),
    ]
    for nid, title, crit in product:
        N.append(node(nid, title, "product", "implementation", ["G01_GRAPH_ENGINE"],
                      "product engineer",
                      "PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and "
                      "must not imply a model has been promoted.",
                      outputs=[f"{PP}/product_lane/{nid}/REPORT.md"],
                      validators=[f"python {PP}/product_lane/{nid}/TESTS.py"],
                      criteria=crit, severity="C"))

    # ---------------------------------------------------------------- future research
    future = [
        ("F10_WITHIN_BETWEEN_TEAM_INVOLVEMENT", "Within-team versus between-team involvement forecaster"),
        ("F11_PLAYER_ALLOCATION_ARCHITECTURE", "Player allocation / distribution architecture"),
        ("F12_OFF_DEF_STRENGTH_COMPONENTS", "Offensive and defensive strength components"),
        ("F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS", "Score, margin and total distributions"),
        ("F14_DECISION_TIME_MARKET_COMPARISON", "Decision-time market comparison"),
        ("F15_PROSPECTIVE_VALIDATION", "Prospective validation design"),
        ("F16_PLAYER_PROPS", "Player props — last, by design"),
    ]
    for nid, title in future:
        N.append(node(nid, title, "future_research", "documentation", ["G04_PROGRAM_ROADMAP_EXTRACTION"],
                      "read-only research scout",
                      "DIAGNOSTIC AND TARGET-CONTRACT DRAFT ONLY. Discovery work being unblocked is "
                      "NOT authorisation to fit. Fitting requires a target contract, a matched K0, "
                      "cutoff-valid evidence, a preregistration and an independent gate review.",
                      outputs=[f"{PP}/future_research/{nid}/TARGET_CONTRACT_DRAFT.md"],
                      validators=[],
                      criteria=["a target contract draft states the estimand, the unit and the denominator",
                                "the matched-K0 requirement is stated for this target",
                                "cutoff-valid evidence is inventoried, not assumed",
                                "the draft states explicitly that it does not authorise fitting"],
                      severity="C", merge="coordinator"))

    return {
        "schema": "player_program/orchestration/program_graph/1",
        "version": "GRAPH_V1",
        "generated_by": f"{ORCH_REL}/scripts/seed_graph.py",
        "policy": f"{ORCH_REL}/GRAPH_POLICY.md",
        "contract": f"{ORCH_REL}/NODE_CONTRACT.schema.json",
        "governing_scientific_contract": "RESEARCH_CONTRACT_V1",
        "notes": [
            "Node ids are stable and never reused. A superseded node keeps its id.",
            "Write ownership is derived from lane and id, so two concurrently-schedulable nodes "
            "cannot contend by construction. validate_graph.py verifies this independently.",
            "Seed statuses are a starting point only. The authoritative status is derived from "
            "GRAPH_EVENTS.jsonl by graphctl.py state.",
        ],
        "nodes": N,
    }


def main():
    graph = build()
    if G.GRAPH_PATH.exists():
        old = {n["id"]: n for n in G.load_graph()["nodes"]}
        for n in graph["nodes"]:
            if n["id"] in old and old[n["id"]].get("input_hashes"):
                n["input_hashes"] = old[n["id"]]["input_hashes"]
    G.write_json(G.GRAPH_PATH, graph)
    lanes = {}
    for n in graph["nodes"]:
        lanes[n["lane"]] = lanes.get(n["lane"], 0) + 1
    print(f"wrote {G.GRAPH_PATH.relative_to(G.REPO)}: {len(graph['nodes'])} nodes")
    for k in sorted(lanes):
        print(f"  {k:<16} {lanes[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
