#!/usr/bin/env python
"""Compute the safe concurrent dispatch set.

Every READY node whose write ownership does not overlap any other node already selected or
already RUNNING. Deterministic: nodes are considered in topological order, and on a tie the
critical-path lane wins, so repeated runs produce the same set.

    dispatch_ready.py [--limit N] [--lane L] [--json] [--emit-launch]

--emit-launch appends an agent_launched event per selected node, which is what moves them to
RUNNING. Without it this is a read-only planner.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys

import graph_lib as G

# Lower sorts first. The possession critical path is always prioritised, but side lanes are
# still dispatched -- prioritisation is about ordering within a capacity limit, never about
# leaving a safe node unlaunched.
LANE_PRIORITY = {
    "possession": 0,
    "governance": 1,
    "data": 2,
    "operations": 3,
    "product": 4,
    "future_research": 5,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--lane")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--emit-launch", action="store_true")
    args = ap.parse_args()

    graph = G.load_graph()
    idx = G.node_index(graph)
    state = G.derive_state(graph, G.load_events())

    order = state["topological_order"]
    pos = {n: i for i, n in enumerate(order)}

    running = [n for n in order if state["status"][n] in ("RUNNING", "VERIFYING")]
    ready = [n for n in order if state["status"][n] == "READY"]
    if args.lane:
        ready = [n for n in ready if idx[n]["lane"] == args.lane]

    ready.sort(key=lambda n: (LANE_PRIORITY.get(idx[n]["lane"], 9), pos[n]))

    selected, deferred = [], []
    for cand in ready:
        conflict = None
        for other in running + selected:
            hits = G.ownership_conflicts(graph, [cand, other])
            if hits:
                conflict = {"with": other, "collisions": hits[0]["collisions"]}
                break
        if conflict:
            deferred.append({"node": cand, "reason": "write-ownership conflict", **conflict})
            continue
        if len(selected) >= args.limit:
            deferred.append({"node": cand, "reason": f"concurrency limit {args.limit}"})
            continue
        selected.append(cand)

    plan = {
        "already_running": running,
        "selected": [
            {
                "node": n,
                "lane": idx[n]["lane"],
                "type": idx[n]["type"],
                "title": idx[n]["title"],
                "agent_role": idx[n]["agent_role"],
                "prompt": idx[n]["agent_prompt_path"],
                "write_paths": idx[n]["allowed_write_paths"],
                "isolation": "worktree" if idx[n]["allowed_write_paths"] else "read-only",
                "merge_policy": idx[n]["merge_policy"],
            }
            for n in selected
        ],
        "deferred": deferred,
        "n_ready": len(ready),
        "n_selected": len(selected),
    }

    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(f"running: {len(running)}   ready: {len(ready)}   selected: {len(selected)}")
        for s in plan["selected"]:
            print(f"  DISPATCH {s['node']:<34} {s['lane']:<15} {s['isolation']:<10} {s['title']}")
        for d in deferred:
            print(f"  defer    {d['node']:<34} {d['reason']}"
                  + (f" (with {d['with']})" if d.get("with") else ""))

    if args.emit_launch:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        head = G.git("rev-parse", "HEAD")
        for n in selected:
            G.append_jsonl(G.EVENTS_PATH, {
                "ts": ts, "event": "agent_launched", "node": n,
                "base_commit": head, "branch": f"graph/{n}",
                "agent_role": idx[n]["agent_role"],
                "launch_window_note": (
                    "exact per-agent launch timestamps are not emitted by the harness; this "
                    "is the dispatch-batch bound, not a fabricated per-agent time"
                ),
            })
        print(f"emitted {len(selected)} agent_launched event(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
