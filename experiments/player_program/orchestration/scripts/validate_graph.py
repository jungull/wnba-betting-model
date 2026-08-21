#!/usr/bin/env python
"""Validate PROGRAM_GRAPH.json structurally and against the node contract.

Exit 0 only when every check passes. This is the gate that runs before any dispatch and
before any integration, so it is deliberately strict: a graph that cannot be validated
cannot be scheduled.
"""

from __future__ import annotations

import hashlib
import json
import re
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

    # 4. an audit node may not be the node whose work it audits.
    #    Covers every type that PRODUCES work an audit examines, not implementation alone.
    #    Found by R16_I11_SEAL_HONESTY: restricting this to "implementation" silently skipped
    #    P38_BLINDED_FIT -> P39_RESULT_INTEGRITY, which is the single most important
    #    independence edge in the whole graph -- the runner must not audit its own results.
    AUDITABLE = {"implementation", "experiment", "integration"}
    for n in nodes:
        if n["type"] != "audit":
            continue
        for d in n["dependencies"]:
            dep = idx[d]
            if dep["type"] not in AUDITABLE:
                continue
            if n["agent_prompt_path"] and n["agent_prompt_path"] == dep["agent_prompt_path"]:
                errs.append(f"{n['id']} audits {d} but shares its agent_prompt_path")
            shared = set(map(G._norm, n["owned_files"])) & set(map(G._norm, dep["owned_files"]))
            if shared:
                errs.append(f"{n['id']} audits {d} but shares owned files: {sorted(shared)}")

    # 5. an experiment must sit downstream of a frozen preregistration.
    #
    # Two arrangements satisfy this, because the requirement is a FROZEN PREREGISTRATION and
    # not a naming convention:
    #
    #   (a) an ancestor node whose id names it as one. This is how the player program is
    #       built -- a preregistration node freezes the task cards, and the experiments that
    #       consume them sit downstream.
    #
    #   (b) the node pins its OWN PREREG.md in input_hashes. A single-node measurement that
    #       carries its preregistration internally satisfies the intent directly, and (b) is
    #       checked more strictly than (a) has ever been: the file must exist on disk AND
    #       still hash to the pinned value. Form (a) never verified that any preregistration
    #       was actually frozen, only that a node with the right name was upstream.
    #
    # Amended under D159 when M30_PRICE_LEADERSHIP -- which carries a hash-frozen prereg and
    # re-verifies it on every run -- failed a rule whose purpose it fully met.
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
        if anc & prereg:
            continue
        own = {p: h for p, h in (n.get("input_hashes") or {}).items()
               if p.rsplit("/", 1)[-1].upper().startswith("PREREG")}
        if not own:
            errs.append(f"{n['id']} is an experiment with no preregistration node among its "
                        f"ancestors and no PREREG file pinned in its own input_hashes")
            continue
        for path, want in own.items():
            full = G.REPO / path
            if not full.exists():
                errs.append(f"{n['id']} pins {path} as its preregistration but the file "
                            f"does not exist")
            elif hashlib.sha256(full.read_bytes()).hexdigest() != want:
                errs.append(f"{n['id']} pins {path} at {want[:16]}... but the file on disk "
                            f"hashes to {hashlib.sha256(full.read_bytes()).hexdigest()[:16]}"
                            f"... -- restore the frozen bytes, do not re-pin (D158)")

    # 6. seed status vs derived status — divergence is reported, not silently accepted.
    #
    # ONE DIVERGENCE IS STRUCTURAL AND WAS WARNING FOREVER FOR NO INFORMATION. The node
    # contract REQUIRES a human_gate node to carry seed status USER_REQUIRED
    # (validate_node_contract), while derive_state gives an event-forced status precedence
    # OVER the human_gate rule. So the moment such a node legitimately passes, its seed and
    # derived statuses diverge by construction and stay diverged for the life of the graph.
    # The warning fired identically whether the gate had been satisfied by a recorded user
    # decision or closed by nobody, so it could not distinguish the benign case from the one
    # worth stopping for.
    #
    # It now judges the thing that matters: whether the event that closed the gate RECORDS AN
    # AUTHORITY. A human gate that passed citing a decision is silent. One that passed citing
    # nothing is an ERROR — that is the case this check exists for, and it was previously
    # indistinguishable from the benign one. Amended under D171.
    events = G.load_events()
    state = G.derive_state(graph, events)
    by_node = {}
    for e in events:
        nid = e.get("node") or e.get("node_id")
        if nid:
            by_node.setdefault(nid, []).append(e)

    # A citation counts ONLY if the decision exists in the ledger AND names this node. The
    # first version of this check accepted any D-number appearing anywhere in the event, and a
    # tamper test caught it: stripping O16's real authority (D022) still passed, because the
    # same sentence happens to mention D017 -- an unrelated push authorisation whose `nodes`
    # field is null. A regex over free text is not an authority check.
    _ledger = {}
    try:
        with open(G.REPO / "experiments" / "player_program" / "orchestration"
                  / "DECISION_LEDGER.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    did = str(r.get("decision_id", ""))
                    key = did.split("_")[0]
                    if key:
                        _ledger.setdefault(key, set()).update(r.get("nodes") or [])
    except OSError:
        _ledger = {}

    def closing_authority(nid, derived):
        """Decisions cited by the event that produced THIS status, that exist and name the node.

        Not merely any status-forcing event: `agent_launched` also forces a status (RUNNING)
        and O16's happens to cite the same decision, so scanning all of them let a stripped
        `node_passed` citation pass the tamper test. The authority must be carried by the event
        that actually closed the gate.
        """
        cited = set()
        for e in by_node.get(nid, []):
            if G.EVENT_STATUS.get(e.get("event")) != derived:
                continue
            for d in re.findall(r"\bD\d{2,4}\b", json.dumps(e, ensure_ascii=False)):
                if nid in _ledger.get(d, set()):
                    cited.add(d)
        return sorted(cited)

    for n in nodes:
        derived = state["status"][n["id"]]
        if n["status"] == derived or n["status"] in G.DERIVED_ONLY:
            continue
        if n.get("human_gate") and n["status"] == "USER_REQUIRED":
            cited = closing_authority(n["id"], derived)
            if cited:
                continue                     # gate satisfied, and the authority is on record
            errs.append(
                f"{n['id']}: a HUMAN GATE reads {derived}, but the event that set that "
                f"status cites no ledger decision naming this node; a gate closed by "
                f"nobody is not a closed gate")
            continue
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
