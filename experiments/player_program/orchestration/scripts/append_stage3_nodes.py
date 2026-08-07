#!/usr/bin/env python3
"""Append the cycle-2 (stage3, score lane) node chain to PROGRAM_GRAPH.json.

D043/D047/D049 formalization: mirrors the battle-tested cycle-1 chain
P30..P43 onto the score-family estimands (E1 game total, E2 final margin,
E3 home win probability; CYCLE2_TARGET_CONTRACT). Append-only: existing
nodes are never modified; running this twice is a no-op for nodes already
present. Follows the exact node schema of the existing graph.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = os.path.abspath(os.path.join(HERE, "..", "PROGRAM_GRAPH.json"))

LANE = "score"
STAGE = "experiments/player_program/stage3_score"
SEALED = f"{STAGE}/SEALED_RESULTS"
CONTRACT_MD = f"{STAGE}/S30_TARGET_CONTRACT/CYCLE2_TARGET_CONTRACT.md"
CONTRACT_JSON = f"{STAGE}/S30_TARGET_CONTRACT/TARGET_CONTRACT.json"

COMMON = {
    "allowed_read_paths": ["experiments/player_program/", "experiments/market_program/"],
    "allowed_tools": ["Read", "Grep", "Glob", "Write", "Edit", "Bash"],
    "disallowed_tools": ["Agent"],
    "forbidden_inputs": ["experiments/player_program/stage2b/SEALED_RESULTS", SEALED],
    "human_gate": False,
    "input_artifacts": [
        "experiments/player_program/PROGRAM_STATE.json",
        "experiments/player_program/RESEARCH_CONTRACT_V1.md",
        "experiments/player_program/GATE_INVOCATION_CONTRACT.md",
    ],
    "input_hashes": {},
    "lane": LANE,
    "max_retries": 2,
    "merge_policy": "coordinator",
    "on_fail": [],
    "on_pass": [],
    "owned_files": [],
    "status": "BLOCKED",
    "validation_commands": [],
    "stop_conditions": [
        "a finding would change the cycle-2 estimands (E1/E2/E3), the K0 structure, the "
        "inference structure, the declared universe, the cutoff-valid feature set or the "
        "leakage status -- HALT and raise, do not resolve it inside the node"
    ],
}


def node(nid, title, ntype, role, deps, sev, epi, outputs, criteria, write_dir,
          extra_inputs=(), human_gate=False):
    n = dict(COMMON)
    n.update({
        "id": nid,
        "title": title,
        "type": ntype,
        "agent_role": role,
        "agent_prompt_path": f"experiments/player_program/orchestration/prompts/{nid}.md",
        "dependencies": list(deps),
        "severity_on_failure": sev,
        "epistemic_status": epi,
        "expected_outputs": list(outputs),
        "acceptance_criteria": list(criteria),
        "allowed_write_paths": [f"{STAGE}/{write_dir}/"],
        "human_gate": human_gate,
    })
    n["input_artifacts"] = list(COMMON["input_artifacts"]) + list(extra_inputs)
    # deterministic key order matching existing nodes (alphabetical, as emitted
    # by json.dump with sort_keys in the seed)
    return {k: n[k] for k in sorted(n)}


NODES = [
    node("S30_TARGET_CONTRACT",
         "Cycle-2 score-family target contract: freeze estimands, universe, folds, gates",
         "decision", "coordinator + two independent red-team reviewers",
         ["P42_SCIENTIFIC_COMPLETION"], "A",
         "TARGET CONTRACT. Once frozen it defines E1/E2/E3 and binds every downstream node; it does not itself authorise fitting.",
         [CONTRACT_MD, CONTRACT_JSON],
         ["estimands E1/E2/E3 stated with unit and denominator, full-game settled per D049",
          "universe, folds, clustering and inference declared with counts",
          "primary gate clauses (a)-(d) and K0_MATCHED thirteen-dimension discipline stated",
          "public floors declared as context never K0; market comparison declared context never gate",
          "two independent red-team reviews with every Severity A/B finding dispositioned before freeze",
          "the freeze event pins the contract sha256 in the events ledger"],
         "S30_TARGET_CONTRACT",
         extra_inputs=[
             "experiments/player_program/future_research/F12_OFF_DEF_STRENGTH_COMPONENTS/TARGET_CONTRACT_DRAFT.md",
             "experiments/player_program/future_research/F13_SCORE_MARGIN_TOTAL_DISTRIBUTIONS/TARGET_CONTRACT_DRAFT.md",
         ]),
    node("S31_SCORE_IDEATION",
         "Independent ideation wave on the frozen cycle-2 contract: isolated sources, no cross-exposure",
         "ideation", "independent scientific ideation sources (structurally isolated)",
         ["S30_TARGET_CONTRACT"], "A",
         "IDEATION OUTPUT. Raw candidate mechanisms from isolated packets; frozen and hashed before any other source reads them.",
         [f"{STAGE}/S31_SCORE_IDEATION/RAW_SOURCES_MANIFEST.json"],
         ["each source ran against an isolated packet containing only the frozen contract and its prompt",
          "no source saw another source's output, the D045/D046/D047 planning priors, or any market-bar value beyond what the frozen contract itself carries",
          "raw outputs frozen and hashed before synthesis reads them",
          "the D047 required coverage areas are each addressed by at least one source"],
         "S31_SCORE_IDEATION",
         extra_inputs=[CONTRACT_MD]),
    node("S32_CANDIDATE_SYNTHESIS",
         "Deduplicate ideation into mechanistically distinct score-family arm definitions",
         "synthesis", "synthesis author",
         ["S31_SCORE_IDEATION"], "A",
         "SYNTHESIS. Mechanistically distinct families with complete arm definitions; retry/replacement labels preserved; source counts never inflated.",
         [f"{STAGE}/S32_CANDIDATE_SYNTHESIS/REPORT.md", f"{STAGE}/S32_CANDIDATE_SYNTHESIS/CANDIDATES.json"],
         ["every retained candidate maps to frozen source bytes",
          "families are mechanistically distinct and each candidate is assigned exactly one primary family",
          "the A07 transient re-entry (if retained) carries its concentration-kill diagnostic as a mandatory receipted output"],
         "S32_CANDIDATE_SYNTHESIS"),
    node("S33_PREREGISTRATION_DRAFT",
         "Freeze every retained score arm's complete specification",
         "preregistration", "preregistration author",
         ["S32_CANDIDATE_SYNTHESIS"], "A",
         "PREREGISTRATION DRAFT. Not yet frozen; not yet authorisation to fit.",
         [f"{STAGE}/S33_PREREGISTRATION_DRAFT/REPORT.md", f"{STAGE}/S33_PREREGISTRATION_DRAFT/SPEC.json"],
         ["every arm freezes: arm ID, mechanism, formula, target estimand(s), exact features, lineage, cutoff evidence, coverage predicate (information-based, cutoff-valid, with an all-covered-games sensitivity), fallback, cold-start behaviour, hyperparameter handling, K0_MATCHED[arm] on all thirteen dimensions, folds, rows, weights, seeds, inference, multiplicity family (E1/E2/E3 treatment pinned explicitly), primary gate, kill conditions each with a receipted diagnostic, secondary diagnostics and expected failure mode",
          "every arm's expected failure mode is stated before any fit",
          "the declared universe counts appear verbatim and games are never split across folds or cluster-bootstrap draws"],
         "S33_PREREGISTRATION_DRAFT"),
    node("S34_PREREGISTRATION_RED_TEAM",
         "Independent adversarial review of the score preregistration",
         "audit", "adversarial reviewer (independent context)",
         ["S33_PREREGISTRATION_DRAFT"], "A",
         "ADVERSARIAL REVIEW. Findings bind; disagreements preserved, never averaged.",
         [f"{STAGE}/S34_PREREGISTRATION_RED_TEAM/FINDINGS.json"],
         ["every arm attacked for leakage, K0 gaming, coverage gaming, multiplicity ambiguity and unreceipted kills",
          "every Severity A finding dispositioned (arm withdrawn or pinned-repair) before freeze"],
         "S34_PREREGISTRATION_RED_TEAM"),
    node("S35_FREEZE_TASK_CARDS",
         "Freeze score task cards and append registry records",
         "decision", "coordinator single-writer",
         ["S34_PREREGISTRATION_RED_TEAM"], "A",
         "FROZEN CARDS. Registry append-only; baseline byte-identity verified on every append.",
         [f"{STAGE}/S35_FREEZE_TASK_CARDS/SPEC.json"],
         ["cards frozen with sha256 pins", "registry records appended after gate pass, byte-identity of prior records verified"],
         "S35_FREEZE_TASK_CARDS"),
    node("S36_IMPLEMENT_ARMS",
         "Implement each score arm, its K0_MATCHED, the shared runner and receipts",
         "engineering", "implementation fleet (one worktree per arm)",
         ["S35_FREEZE_TASK_CARDS"], "A",
         "IMPLEMENTATION. Unit/synthetic/identity/schema tests only; no comparative historical performance is revealed.",
         [f"{STAGE}/S36_IMPLEMENT_ARMS/RUNNER_MANIFEST.json"],
         ["every declared output exists with tests green",
          "no forbidden path changed; no performance number emitted anywhere"],
         "S36_IMPLEMENT_ARMS"),
    node("S37_IMPLEMENTATION_AUDIT",
         "Independent implementation audit of every score arm before any fit",
         "audit", "independent auditors (not the implementers)",
         ["S36_IMPLEMENT_ARMS"], "A",
         "IMPLEMENTATION AUDIT. Card-vs-code fidelity; cutoff validity receipts; kill-diagnostic presence verified.",
         [f"{STAGE}/S37_IMPLEMENTATION_AUDIT/SPEC.json"],
         ["auditors share no prompt or files with implementers (validate_graph rule)",
          "every CUTOFF_UNPROVEN field used by an arm carries a receipted cutoff-validity measurement",
          "every kill condition's diagnostic is verified to be a receipted output of the planned run"],
         "S37_IMPLEMENTATION_AUDIT"),
    node("S38_BLINDED_FIT",
         "Execute all score fits sealed; nobody reads results before integrity + adjudication",
         "execution", "sealed-fit executor",
         ["S37_IMPLEMENTATION_AUDIT"], "A",
         "SEALED EXECUTION. Results land under stage3_score/SEALED_RESULTS; unreadable by anyone including coordinators until S40.",
         [f"{STAGE}/SEALED_RESULTS/MANIFEST.json"],
         ["every fitted element writes receipts (seeds, hashes, folds, universes) into the sealed store",
          "zero performance numbers exist outside the seals"],
         "S38_BLINDED_FIT"),
    node("S39_RESULT_INTEGRITY",
         "Verify seals: commit, hashes, row universes, folds, K0 pairing, seeds — without opening results",
         "audit", "independent integrity verifier",
         ["S38_BLINDED_FIT"], "A",
         "INTEGRITY VERIFICATION. Structural only; results stay sealed.",
         [f"{STAGE}/S39_RESULT_INTEGRITY/INTEGRITY.json"],
         ["all structural checks pass with zero Severity A findings before any unsealing is authorized"],
         "S39_RESULT_INTEGRITY"),
    node("S40_PRIMARY_ADJUDICATION",
         "The only context authorized to open score seals; apply the frozen gate to every element",
         "decision", "adjudicator (sole unseal authority)",
         ["S39_RESULT_INTEGRITY"], "A",
         "ADJUDICATION. Opens seals under a recorded unseal ruling; verdicts fully provenanced; nulls and harms preserved permanently.",
         [f"{STAGE}/S40_PRIMARY_ADJUDICATION/ADJUDICATION.json"],
         ["every element receives a gate verdict with clause-by-clause accounting",
          "adjudicated numbers flow to the board solely through the D036 pipeline",
          "market comparison reported as context only, never as a gate"],
         "S40_PRIMARY_ADJUDICATION"),
    node("S41_SCIENTIFIC_COMPLETION",
         "Cycle-2 accepted/null/failed decisions, bounded effects, uncertainty, limitations",
         "decision", "coordinator + two reviewers",
         ["S40_PRIMARY_ADJUDICATION"], "A",
         "SCIENTIFIC COMPLETION REPORT. States what the wave established and what it did not. Does not itself promote anything.",
         [f"{STAGE}/S41_SCIENTIFIC_COMPLETION/COMPLETION.md"],
         ["accepted / null / failed decision for every arm",
          "bounded effect estimates with uncertainty",
          "failure explanations and downstream implications",
          "unresolved limitations stated",
          "a prospective-confirmation recommendation is given"],
         "S41_SCIENTIFIC_COMPLETION"),
    node("S42_ADOPTION_DECISION",
         "Whether any fitted score model is adopted for operational or wager-shaped use: the user's alone",
         "decision", "USER",
         ["S41_SCIENTIFIC_COMPLETION"], "A",
         "USER GATE. Adoption of a score model for anything wager-shaped is never self-granted by the graph.",
         [f"{STAGE}/S42_ADOPTION_DECISION/DECISION.md"],
         ["a decision packet states the adjudicated evidence, market context and risks; the user rules"],
         "S42_ADOPTION_DECISION", human_gate=True),
]


def main():
    with open(GRAPH, encoding="utf-8") as f:
        g = json.load(f)
    existing = {n["id"] for n in g["nodes"]}
    added = []
    for n in NODES:
        if n["id"] in existing:
            continue
        g["nodes"].append(n)
        added.append(n["id"])
    with open(GRAPH, "w", encoding="utf-8") as f:
        json.dump(g, f, indent=2, sort_keys=False)
        f.write("\n")
    print("added", len(added), "nodes:", ", ".join(added) or "(none)")


if __name__ == "__main__":
    main()
