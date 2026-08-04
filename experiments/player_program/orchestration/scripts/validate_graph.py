#!/usr/bin/env python
"""Validate PROGRAM_GRAPH.json structurally and against the node contract.

Exit 0 only when every check passes. This is the gate that runs before any dispatch and
before any integration, so it is deliberately strict: a graph that cannot be validated
cannot be scheduled.
"""

from __future__ import annotations

import sys

import graph_lib as G


def main():
    graph = G.load_graph()
    errs, warns = [], []

    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        print("FAIL: PROGRAM_GRAPH.json has no nodes")
        return 1

    # 1. per-node contract
    for n in nodes:
        errs.extend(G.validate_node_contract(n))

    idx = G.node_index(graph)

    # 2. acyclic + every referenced id resolves
    try:
        order = G.topo_order(graph)
    except SystemExit as exc:
        print(f"FAIL: {exc}")
        return 1
    for n in nodes:
        for field in ("on_pass", "on_fail"):
            for ref in n[field]:
                if ref not in idx:
                    errs.append(f"{n['id']}: {field} references undeclared node {ref}")

    # 3. no live write-scope collision.
    #    Two nodes conflict only if they could be dispatched together, i.e. neither is an
    #    ancestor of the other. A node and its own descendant may share files: they are
    #    serialised by the dependency edge and can never run concurrently.
    reach = {i: set() for i in idx}
    for nid in reversed(order):
        for d in idx[nid]["dependencies"]:
            reach[d].add(nid)
            reach[d] |= reach[nid]

    def serialised(a, b):
        return b in reach[a] or a in reach[b]

    ids = sorted(idx)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if serialised(a, b):
                continue
            na, nb = idx[a], idx[b]
            for pa in na["allowed_write_paths"] + na["owned_files"]:
                for pb in nb["allowed_write_paths"] + nb["owned_files"]:
                    if G.paths_overlap(pa, pb):
                        errs.append(
                            f"write-scope collision between concurrently-schedulable "
                            f"{a} and {b}: {G._norm(pa)} vs {G._norm(pb)}"
                        )
                        break
                else:
                    continue
                break

    # 4. an audit node may not be the implementation node it audits
    for n in nodes:
        if n["type"] != "audit":
            continue
        for d in n["dependencies"]:
            dep = idx[d]
            if dep["type"] != "implementation":
                continue
            if n["agent_prompt_path"] and n["agent_prompt_path"] == dep["agent_prompt_path"]:
                errs.append(f"{n['id']} audits {d} but shares its agent_prompt_path")
            shared = set(map(G._norm, n["owned_files"])) & set(map(G._norm, dep["owned_files"]))
            if shared:
                errs.append(f"{n['id']} audits {d} but shares owned files: {sorted(shared)}")

    # 5. an experiment must sit downstream of a frozen preregistration
    prereg = {i for i in idx if "PREREG" in i or "FREEZE_TASK_CARDS" in i}
    for n in nodes:
        if n["type"] != "experiment":
            continue
        anc = set()
        stack = list(n["dependencies"])
        while stack:
            cur = stack.pop()
            if cur in anc:
                continue
            anc.add(cur)
            stack.extend(idx[cur]["dependencies"])
        if not (anc & prereg):
            errs.append(f"{n['id']} is an experiment with no preregistration node among its ancestors")

    # 6. seed status vs derived status — divergence is reported, not silently accepted
    state = G.derive_state(graph, G.load_events())
    for n in nodes:
        derived = state["status"][n["id"]]
        if n["status"] != derived and n["status"] not in G.DERIVED_ONLY:
            warns.append(f"{n['id']}: seed status {n['status']} vs derived {derived} "
                         f"(derived governs)")

    # 7. forbidden_inputs must not also be readable
    for n in nodes:
        both = set(map(G._norm, n["forbidden_inputs"])) & set(map(G._norm, n["allowed_read_paths"]))
        if both:
            errs.append(f"{n['id']}: path is both forbidden and allowed to read: {sorted(both)}")

    # 8. every declared input artifact that exists on disk must be hashable
    for n in nodes:
        for a in n["input_artifacts"]:
            p = G.REPO / a
            if p.exists() and not p.is_file() and not p.is_dir():
                errs.append(f"{n['id']}: input artifact {a} is neither file nor directory")

    for w in warns:
        print(f"WARN: {w}")
    for e in errs:
        print(f"FAIL: {e}")
    if errs:
        print(f"\n{len(errs)} error(s), {len(warns)} warning(s)")
        return 1
    print(f"OK: {len(nodes)} nodes, {len(graph.get('edges', []))} declared edges, "
          f"acyclic, contract-valid, no live write-scope collision "
          f"({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
