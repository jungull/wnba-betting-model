#!/usr/bin/env python
"""test_graph_engine.py — validation for the orchestration layer.

These test the SCHEDULER only. A passing suite establishes nothing scientific. It establishes
that the scheduler cannot lose a failure, cannot dispatch two nodes onto the same file, cannot
let a node declare a write path inside a frozen area, and cannot let a fit precede its own
preregistration.

Standalone, matching the convention of the surrounding program tests. No third-party imports.

Run::

    python experiments/player_program/orchestration/tests/test_graph_engine.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import graph_lib as G  # noqa: E402

FAILED: list[str] = []


def check(cond, msg):
    if not cond:
        FAILED.append(msg)
        print(f"  FAIL  {msg}")
    return bool(cond)


GRAPH = G.load_graph()
IDX = G.node_index(GRAPH)


# ---------------------------------------------------------------- structure

def test_graph_is_acyclic_and_every_reference_resolves():
    order = G.topo_order(GRAPH)
    check(len(order) == len(GRAPH["nodes"]), "topological order covers every node")
    for n in GRAPH["nodes"]:
        for field in ("dependencies", "on_pass", "on_fail"):
            for ref in n[field]:
                check(ref in IDX, f"{n['id']}.{field} -> unknown node {ref}")
    print(f"  ok    {len(order)} nodes, acyclic, all references resolve")


def test_every_node_satisfies_the_contract():
    errs = []
    for n in GRAPH["nodes"]:
        errs.extend(G.validate_node_contract(n))
    check(not errs, f"contract violations: {errs[:5]}")
    print(f"  ok    {len(GRAPH['nodes'])} nodes satisfy NODE_CONTRACT.schema.json")


def test_node_ids_are_unique():
    ids = [n["id"] for n in GRAPH["nodes"]]
    check(len(ids) == len(set(ids)), "node ids are unique")
    print(f"  ok    {len(ids)} unique ids")


def test_no_concurrently_schedulable_pair_shares_a_write_scope():
    order = G.topo_order(GRAPH)
    reach = {i: set() for i in IDX}
    for nid in reversed(order):
        for d in IDX[nid]["dependencies"]:
            reach[d].add(nid)
            reach[d] |= reach[nid]
    ids = sorted(IDX)
    pairs = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if b in reach[a] or a in reach[b]:
                continue
            pairs += 1
            check(not G.ownership_conflicts(GRAPH, [a, b]), f"{a} and {b} contend for a write path")
    print(f"  ok    {pairs} concurrently-schedulable pairs, none contend")


# ---------------------------------------------------------------- derivation

def test_state_is_deterministic():
    events = G.load_events()
    check(G.derive_state(GRAPH, events) == G.derive_state(GRAPH, events),
          "state derivation is deterministic")
    print("  ok    derivation is a pure function")


def test_state_on_disk_matches_the_derivation():
    if not G.STATE_PATH.exists():
        check(False, "GRAPH_STATE.json missing")
        return
    on_disk = json.load(open(G.STATE_PATH, encoding="utf-8"))
    check(on_disk == G.derive_state(GRAPH, G.load_events()),
          "GRAPH_STATE.json reproduces from graph + events")
    print("  ok    committed state reproduces exactly")


def test_dependency_closure_gates_readiness():
    st = G.derive_state(GRAPH, [{"event": "node_passed", "node": "G00_LIVE_RECONCILIATION"}])
    check(st["status"]["G00_LIVE_RECONCILIATION"] == "PASSED", "passed node reads PASSED")
    check(st["status"]["G01_GRAPH_ENGINE"] == "READY", "sole dependency satisfied -> READY")
    check(st["status"]["G03_FROZEN_PATH_GUARD"] == "BLOCKED",
          "two dependencies, one satisfied -> still BLOCKED")
    print("  ok    readiness requires the full dependency closure")


def test_superseded_alone_does_not_satisfy_a_dependency():
    ev = [{"event": "node_superseded", "node": "G00_LIVE_RECONCILIATION",
           "superseded_by": "G02_DOCUMENT_INDEX"}]
    st = G.derive_state(GRAPH, ev)
    check(st["status"]["G00_LIVE_RECONCILIATION"] == "SUPERSEDED", "supersession recorded")
    check(st["status"]["G01_GRAPH_ENGINE"] == "BLOCKED",
          "SUPERSEDED without a PASSED successor must not unblock a dependent")
    print("  ok    superseding a node does not conjure its evidence")


def test_a_failure_is_never_silently_lost():
    ev = [{"event": "node_passed", "node": "G00_LIVE_RECONCILIATION"},
          {"event": "agent_launched", "node": "G01_GRAPH_ENGINE"},
          {"event": "validation_failed", "node": "G01_GRAPH_ENGINE"}]
    st = G.derive_state(GRAPH, ev)
    check(st["status"]["G01_GRAPH_ENGINE"] == "FAILED", "a failed validation reads FAILED")
    check(st["status"]["G03_FROZEN_PATH_GUARD"] == "BLOCKED", "descendants of a failure stay blocked")
    print("  ok    a failure blocks its descendants and stays visible")


def test_retry_resets_status_but_keeps_the_failure_in_the_ledger():
    ev = [{"event": "node_passed", "node": "G00_LIVE_RECONCILIATION"},
          {"event": "validation_failed", "node": "G01_GRAPH_ENGINE"},
          {"event": "node_reset", "node": "G01_GRAPH_ENGINE"}]
    st = G.derive_state(GRAPH, ev)
    check(st["status"]["G01_GRAPH_ENGINE"] == "READY", "a reset returns the node to READY")
    check(st["retry_counts"].get("G01_GRAPH_ENGINE") == 1, "the retry is counted")
    check(any(e.get("event") == "validation_failed" for e in ev),
          "the failure event is still present -- history is not rewritten")
    print("  ok    a retry re-opens the node without erasing the failure")


def test_human_gate_nodes_are_user_required():
    st = G.derive_state(GRAPH, [])
    gates = [n for n in GRAPH["nodes"] if n["human_gate"]]
    check(len(gates) >= 2, "at least the champion and shared-schema gates exist")
    for n in gates:
        check(st["status"][n["id"]] == "USER_REQUIRED", f"{n['id']} is USER_REQUIRED")
        check(n["merge_policy"] == "never", f"{n['id']} is never auto-merged")
    print(f"  ok    {len(gates)} human gates, all USER_REQUIRED and never auto-merged")


def test_a_blocker_in_one_lane_does_not_block_another():
    ev = [{"event": "node_passed", "node": "G00_LIVE_RECONCILIATION"},
          {"event": "node_passed", "node": "G01_GRAPH_ENGINE"},
          {"event": "node_halted", "node": "P22_POSTGAME_SURROGATE_GUARD"}]
    st = G.derive_state(GRAPH, ev)
    check(st["status"]["P22_POSTGAME_SURROGATE_GUARD"] == "HALTED", "halt recorded")
    check(st["status"]["U10_PREDICTION_API_SCHEMA"] == "READY", "product lane unaffected")
    check(st["status"]["D10_FIELD_AVAILABILITY_LEDGER"] == "READY", "data lane unaffected")
    check(st["status"]["P30_EVIDENCE_PACKET_V3"] == "BLOCKED",
          "the possession critical path below the halt IS blocked")
    print("  ok    a lane blocker stops its own descendants only")


# ---------------------------------------------------------------- frozen paths

FROZEN_MUST_REJECT = [
    "experiments/player_program/feature_gate.py",
    "experiments/player_program/comparison_gate.py",
    "experiments/player_program/gate_invocation.py",
    "experiments/player_program/receipt_integrity.py",
    "experiments/player_program/stage2a/EVIDENCE_PACKET.json",
    "experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json",
    "experiments/player_program/stage2a/V2_STOP_CONDITION.json",
    "experiments/player_program/possessions_v2/anything.parquet",
    "experiments/player_program/discovery_wave_1/FINAL_AUDIT_MATRIX.json",
    "experiments/player_program/fits_v1/D_ewma_shrunk.json",
    "experiments/player_program/arm_incumbent.py",
    "experiments/player_program/PROGRAM_STATE.json",
    "experiments/player_program/arm_registry.jsonl",
]

LANE_MUST_ALLOW = [
    "experiments/player_program/stage2b/P22_POSTGAME_SURROGATE_GUARD/REPORT.md",
    "experiments/player_program/orchestration/PROGRAM_GRAPH.json",
    "experiments/player_program/data_lane/D10_FIELD_AVAILABILITY_LEDGER/FINDINGS.json",
    "experiments/player_program/product_lane/U11_UI_SHELL/app.py",
    "experiments/player_program/ops_lane/I10_GENERIC_CLUSTERED_INFERENCE/boot.py",
]


def test_frozen_paths_are_rejected():
    for p in FROZEN_MUST_REJECT:
        check(bool(G.frozen_violations([p])), f"frozen path must be rejected: {p}")
    print(f"  ok    {len(FROZEN_MUST_REJECT)} frozen paths rejected")


def test_lane_workspaces_are_allowed():
    for p in LANE_MUST_ALLOW:
        check(not G.frozen_violations([p]), f"lane workspace must be allowed: {p}")
    print(f"  ok    {len(LANE_MUST_ALLOW)} lane workspaces allowed")


def test_no_node_declares_a_write_path_inside_a_frozen_area():
    for n in GRAPH["nodes"]:
        for p in n["allowed_write_paths"]:
            probe = G._norm(p).rstrip("/") + "/probe"
            check(not G.frozen_violations([probe]),
                  f"{n['id']} declares a write path inside a frozen area: {p}")
    print("  ok    no node may write a frozen path")


# ---------------------------------------------------------------- ownership

def test_paths_overlap_semantics():
    check(G.paths_overlap("a/b", "a/b"), "identical paths overlap")
    check(G.paths_overlap("a/b", "a/b/c"), "parent and child overlap")
    check(G.paths_overlap("a/b/c", "a/b"), "child and parent overlap")
    check(not G.paths_overlap("a/b", "a/bc"), "prefix-of-name is not containment")
    check(not G.paths_overlap("a/b/x.md", "a/b/y.md"), "siblings do not overlap")
    print("  ok    path overlap semantics")


def test_ownership_map_has_no_contested_file():
    own = G.build_ownership(GRAPH)
    check(own["contested_files"] == {}, f"contested files: {own['contested_files']}")
    print("  ok    no file is owned by two nodes")


# ---------------------------------------------------------------- policy invariants

def _ancestors(nid):
    anc, stack = set(), list(IDX[nid]["dependencies"])
    while stack:
        cur = stack.pop()
        if cur in anc:
            continue
        anc.add(cur)
        stack.extend(IDX[cur]["dependencies"])
    return anc


def test_every_experiment_sits_downstream_of_a_preregistration():
    prereg = {i for i in IDX if "PREREG" in i or "FREEZE_TASK_CARDS" in i}
    exps = [n for n in GRAPH["nodes"] if n["type"] == "experiment"]
    check(bool(exps), "there is at least one experiment node")
    for n in exps:
        check(bool(_ancestors(n["id"]) & prereg),
              f"{n['id']} may not fit without a preregistration ancestor")
    print(f"  ok    {len(exps)} experiment nodes, all downstream of a preregistration")


def test_blinding_the_fit_precedes_result_integrity_precedes_adjudication():
    order = G.topo_order(GRAPH)
    pos = {n: i for i, n in enumerate(order)}
    check(pos["P38_BLINDED_FIT"] < pos["P39_RESULT_INTEGRITY"], "fit precedes integrity check")
    check(pos["P39_RESULT_INTEGRITY"] < pos["P40_PRIMARY_ADJUDICATION"],
          "integrity check precedes adjudication")
    check(pos["P40_PRIMARY_ADJUDICATION"] < pos["P41_DOWNSTREAM_TURNOVER_CONFIRMATION"],
          "downstream turnover confirmation must never precede primary adjudication")
    check("P39_RESULT_INTEGRITY" in IDX["P40_PRIMARY_ADJUDICATION"]["dependencies"],
          "adjudication depends directly on result integrity")
    print("  ok    blinding order: fit -> integrity -> primary -> downstream")


def test_v3_depends_on_every_remediation_node():
    deps = set(IDX["P30_EVIDENCE_PACKET_V3"]["dependencies"])
    required = ["P21_FREEZE_V2_HALT_PACKET", "P22_POSTGAME_SURROGATE_GUARD",
                "P23_DIMENSION_CARDINALITY_GUARD", "P24_INJURY_REGIME_LEDGER",
                "P25_OFFSET_DEPENDENCY_GUARD", "P26_ARM_SPECIFIC_K0_CONTRACT",
                "P27_FOLD_LOCAL_ESTIMABILITY_GUARD", "P28_PRIMARY_SECONDARY_ORDERING_CONTRACT",
                "P29_TIP_TIME_AND_COVERAGE_AUDIT", "P2A_POSSESSION_COLUMN_ADJUDICATION"]
    for nid in required:
        check(nid in deps, f"V3 must depend on {nid}")
    print(f"  ok    V3 depends on all {len(required)} remediation nodes")


def test_final_ideation_depends_on_v3_only():
    check(IDX["P31_FINAL_V3_IDEATION"]["dependencies"] == ["P30_EVIDENCE_PACKET_V3"],
          "the final ideation wave sees V3 and nothing earlier")
    print("  ok    final ideation is gated on V3 alone")


def test_every_node_states_its_epistemic_status():
    for n in GRAPH["nodes"]:
        check(bool(n["epistemic_status"].strip()), f"{n['id']} has no epistemic status")
    print("  ok    every node states what its output is and is not")


def test_audit_nodes_do_not_share_files_with_what_they_audit():
    for n in GRAPH["nodes"]:
        if n["type"] != "audit":
            continue
        for d in n["dependencies"]:
            if IDX[d]["type"] != "implementation":
                continue
            shared = set(map(G._norm, n["owned_files"])) & set(map(G._norm, IDX[d]["owned_files"]))
            check(not shared, f"{n['id']} audits {d} but shares {shared}")
    print("  ok    no audit node owns the files it audits")


def main():
    tests = [
        test_graph_is_acyclic_and_every_reference_resolves,
        test_every_node_satisfies_the_contract,
        test_node_ids_are_unique,
        test_no_concurrently_schedulable_pair_shares_a_write_scope,
        test_state_is_deterministic,
        test_state_on_disk_matches_the_derivation,
        test_dependency_closure_gates_readiness,
        test_superseded_alone_does_not_satisfy_a_dependency,
        test_a_failure_is_never_silently_lost,
        test_retry_resets_status_but_keeps_the_failure_in_the_ledger,
        test_human_gate_nodes_are_user_required,
        test_a_blocker_in_one_lane_does_not_block_another,
        test_frozen_paths_are_rejected,
        test_lane_workspaces_are_allowed,
        test_no_node_declares_a_write_path_inside_a_frozen_area,
        test_paths_overlap_semantics,
        test_ownership_map_has_no_contested_file,
        test_every_experiment_sits_downstream_of_a_preregistration,
        test_blinding_the_fit_precedes_result_integrity_precedes_adjudication,
        test_v3_depends_on_every_remediation_node,
        test_final_ideation_depends_on_v3_only,
        test_every_node_states_its_epistemic_status,
        test_audit_nodes_do_not_share_files_with_what_they_audit,
    ]
    print("=" * 78)
    print("test_graph_engine — orchestration layer")
    print("=" * 78)
    for fn in tests:
        print(f"\n--- {fn.__name__} ---")
        fn()
    print("\n" + "=" * 78)
    print(f"{'PASS — all checks green' if not FAILED else 'FAIL: ' + str(FAILED)}")
    print("=" * 78)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
