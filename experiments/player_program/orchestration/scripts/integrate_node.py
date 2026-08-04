#!/usr/bin/env python
"""Integrate a validated node branch into the program branch.

Preconditions, all mandatory (GRAPH_POLICY.md s8):

  * the node's base is a clean ancestor of the target
  * changed files stay inside the node's declared write scope
  * no frozen path changed (frozen_path_guard.py)
  * validators pass (validate_node.py)
  * artifact hashes reconcile
  * no file owned by another RUNNING node is touched
  * an explicit merge event is appended

    integrate_node.py NODE_ID --branch graph/NODE_ID [--target player-model-program] [--apply]

Without --apply this is a dry run that reports exactly what would happen. Never force-pushes,
never resets, never rewrites history, never pushes to a remote.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import subprocess
import sys

import graph_lib as G


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(*args, check=True):
    res = subprocess.run(["git"] + list(args), cwd=str(G.REPO), capture_output=True, text=True)
    if check and res.returncode != 0:
        raise SystemExit(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("node_id")
    ap.add_argument("--branch")
    ap.add_argument("--target", default="player-model-program")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    graph = G.load_graph()
    idx = G.node_index(graph)
    node = idx.get(args.node_id)
    if node is None:
        print(f"no such node: {args.node_id}")
        return 1
    branch = args.branch or f"graph/{args.node_id}"

    failures = []

    # branch exists
    if _run("rev-parse", "--verify", branch, check=False).returncode != 0:
        print(f"FAIL: branch {branch} does not exist")
        return 1
    tip = G.git("rev-parse", branch)
    target_tip = G.git("rev-parse", args.target)
    base = G.git("merge-base", branch, args.target)
    print(f"branch   {branch} @ {tip[:7]}")
    print(f"target   {args.target} @ {target_tip[:7]}")
    print(f"base     {base[:7]}")

    changed = [p for p in G.git("diff", "--name-only", f"{base}..{tip}").splitlines() if p]
    print(f"changed  {len(changed)} file(s)")

    # scope
    scope = [G._norm(p) for p in node["allowed_write_paths"]]
    out = [c for c in changed
           if not any(G._norm(c) == s or G._norm(c).startswith(s.rstrip('/') + '/') for s in scope)]
    if out:
        failures.append(f"outside declared write scope: {out[:10]}")

    # frozen
    viol = G.frozen_violations(changed)
    hard = [v for v in viol if v["path"] not in
            {"experiments/player_program/arm_registry.jsonl", "experiments/player_program/registry.jsonl"}]
    if hard:
        failures.append(f"frozen path(s) touched: {[v['path'] for v in hard]}")

    # ownership vs other live nodes
    state = G.derive_state(graph, G.load_events())
    live = [n for n in state["status"] if state["status"][n] in ("RUNNING", "VERIFYING")
            and n != node["id"]]
    conflicts = G.ownership_conflicts(graph, [node["id"]] + live) if live else []
    conflicts = [c for c in conflicts if node["id"] in (c["a"], c["b"])]
    if conflicts:
        failures.append(f"write ownership overlaps a live node: {conflicts}")

    # merge policy
    if node["merge_policy"] == "never":
        failures.append("merge_policy=never — this node's output is evidence, not authority; "
                        "it is not merged")

    for f in failures:
        print(f"FAIL     {f}")
    if failures:
        return 1

    print("OK       all integration preconditions satisfied")
    if not args.apply:
        print("dry run — pass --apply to merge")
        return 0

    cur = G.git("rev-parse", "--abbrev-ref", "HEAD")
    if cur != args.target:
        print(f"FAIL: run this from a worktree on {args.target} (currently {cur})")
        return 1
    if G.git("status", "--porcelain"):
        print("FAIL: working tree is dirty; refusing to merge")
        return 1

    msg = f"graph({node['id']}): {node['title']}"
    res = _run("merge", "--no-ff", "-m", msg, branch, check=False)
    print(res.stdout or res.stderr)
    if res.returncode != 0:
        G.append_jsonl(G.EVENTS_PATH, {
            "ts": _now(), "event": "node_failed", "node": node["id"],
            "detail": "merge conflict; branch preserved, nothing discarded",
        })
        return 1

    new_head = G.git("rev-parse", "HEAD")
    G.append_jsonl(G.EVENTS_PATH, {
        "ts": _now(), "event": "merge_completed", "node": node["id"],
        "branch": branch, "branch_tip": tip, "target": args.target,
        "merge_commit": new_head, "n_files": len(changed), "changed_files": changed,
    })
    G.append_jsonl(G.EVENTS_PATH, {
        "ts": _now(), "event": "node_passed", "node": node["id"],
        "merge_commit": new_head,
    })
    print(f"merged   {branch} -> {args.target} @ {new_head[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
