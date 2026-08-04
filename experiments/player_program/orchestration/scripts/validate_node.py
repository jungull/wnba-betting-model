#!/usr/bin/env python
"""Validate one completed node. Run by a VERIFIER context, never by the implementing agent.

Checks, in order, stopping at the first class that fails:

  1. every expected output exists
  2. every frozen input hash rederives            (the evidence base did not shift)
  3. no frozen path was touched
  4. every validation_command exits 0
  5. acceptance criteria are present and machine-verifiable when merge_policy is auto

A pass here is necessary, not sufficient: GRAPH_POLICY.md section 5 also requires an
independent verifier to agree before the node is integrated.

    validate_node.py NODE_ID [--worktree DIR] [--range A..B] [--emit-event]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

import graph_lib as G


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("node_id")
    ap.add_argument("--worktree")
    ap.add_argument("--range")
    ap.add_argument("--emit-event", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    graph = G.load_graph()
    idx = G.node_index(graph)
    node = idx.get(args.node_id)
    if node is None:
        print(f"no such node: {args.node_id}")
        return 1

    root = Path(args.worktree) if args.worktree else G.REPO
    report = {"node": node["id"], "checks": {}, "failures": []}

    # 1. outputs exist
    missing = [o for o in node["expected_outputs"] if not (root / o).exists()]
    report["checks"]["expected_outputs"] = {
        "declared": node["expected_outputs"], "missing": missing,
    }
    if missing:
        report["failures"].append(f"missing declared output(s): {missing}")

    # 2. input hashes rederive
    drift = []
    for p, expected in sorted(node["input_hashes"].items()):
        actual = G.file_digest_or_none(p)
        if actual != expected:
            drift.append({"path": p, "expected": expected, "actual": actual})
    report["checks"]["input_hashes"] = {"n": len(node["input_hashes"]), "drift": drift}
    if drift:
        report["failures"].append(
            f"{len(drift)} frozen input(s) changed under the node — its conclusions rest on "
            f"bytes that no longer exist")

    # 3. frozen paths untouched
    if args.range:
        changed = [p for p in G.git("diff", "--name-only", args.range, cwd=root).splitlines() if p]
    else:
        changed = [p for p in G.git("status", "--porcelain", cwd=root).splitlines()]
        changed = [c[3:] for c in changed if c]
    viol = G.frozen_violations(changed)
    report["checks"]["frozen_paths"] = {"n_changed": len(changed), "violations": viol}
    if viol:
        report["failures"].append(f"frozen path(s) touched: {[v['path'] for v in viol]}")

    # 3b. changed files stay inside the declared write scope
    scope = [G._norm(p) for p in node["allowed_write_paths"]]
    out_of_scope = []
    for c in changed:
        q = G._norm(c)
        if not any(q == s or q.startswith(s.rstrip("/") + "/") for s in scope):
            out_of_scope.append(q)
    report["checks"]["write_scope"] = {"declared": scope, "out_of_scope": out_of_scope}
    if out_of_scope:
        report["failures"].append(
            f"node wrote outside its declared scope: {out_of_scope[:10]} — an agent may not "
            f"broaden its own write scope")

    # 4. validators
    results = []
    for cmd in node["validation_commands"]:
        res = subprocess.run(cmd, shell=True, cwd=str(root), capture_output=True, text=True)
        results.append({
            "cmd": cmd, "returncode": res.returncode,
            "stdout_tail": res.stdout[-2000:], "stderr_tail": res.stderr[-2000:],
        })
        if res.returncode != 0:
            report["failures"].append(f"validator failed ({res.returncode}): {cmd}")
    report["checks"]["validators"] = results

    # 5. auto-merge preconditions
    if node["merge_policy"] == "auto" and not node["acceptance_criteria"]:
        report["failures"].append("merge_policy=auto with no acceptance criteria")

    report["ok"] = not report["failures"]
    report["verdict"] = "PASSED" if report["ok"] else "FAILED"
    report["severity_if_failed"] = node["severity_on_failure"]
    report["note"] = (
        "A validator pass is necessary but NOT sufficient. GRAPH_POLICY.md s5 also requires an "
        "independent verifier context to agree before integration."
    )

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"node       {node['id']}")
        print(f"outputs    {len(node['expected_outputs']) - len(missing)}/{len(node['expected_outputs'])} present")
        print(f"inputs     {len(node['input_hashes']) - len(drift)}/{len(node['input_hashes'])} rederive")
        print(f"frozen     {len(viol)} violation(s)")
        print(f"scope      {len(out_of_scope)} file(s) outside declared write scope")
        for r in results:
            print(f"validator  [{r['returncode']}] {r['cmd']}")
            if r["returncode"] != 0:
                tail = (r["stderr_tail"] or r["stdout_tail"]).strip().splitlines()[-6:]
                for t in tail:
                    print(f"           | {t}")
        for f in report["failures"]:
            print(f"FAIL       {f}")
        print(f"VERDICT    {report['verdict']}")

    if args.emit_event:
        G.append_jsonl(G.EVENTS_PATH, {
            "ts": _now(),
            "event": "validation_passed" if report["ok"] else "validation_failed",
            "node": node["id"],
            "failures": report["failures"],
            "n_validators": len(results),
            "head": G.git("rev-parse", "HEAD"),
        })

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
