#!/usr/bin/env python
"""graphctl -- the program graph command line.

    graphctl.py state [--check]     rebuild GRAPH_STATE.json (--check: fail on divergence)
    graphctl.py ownership           rebuild FILE_OWNERSHIP.json
    graphctl.py ready               list READY node ids
    graphctl.py show <id>           print one node
    graphctl.py event <type> [...]  append an event to GRAPH_EVENTS.jsonl
    graphctl.py decision [...]      append a ruling to DECISION_LEDGER.jsonl
    graphctl.py status              render reports/CURRENT_STATUS.md
    graphctl.py summary             one-line counts, for a quick check

The event ledger is append-only. There is deliberately no command that edits or deletes an
event: a wrong event is corrected by appending a corrective event, never by rewriting history.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys

import graph_lib as G


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- commands

def cmd_state(args):
    graph = G.load_graph()
    events = G.load_events()
    state = G.derive_state(graph, events)
    if args.check:
        if not G.STATE_PATH.exists():
            print("FAIL: GRAPH_STATE.json does not exist; run `graphctl.py state`")
            return 1
        on_disk = json.load(open(G.STATE_PATH, encoding="utf-8"))
        if on_disk != state:
            print("FAIL: GRAPH_STATE.json diverges from the derivation.")
            for k in sorted(set(on_disk) | set(state)):
                if on_disk.get(k) != state.get(k):
                    print(f"  field {k!r} differs")
            return 1
        print(f"OK: GRAPH_STATE.json reproduces exactly ({state['n_nodes']} nodes, "
              f"{state['n_events']} events)")
        return 0
    G.write_json(G.STATE_PATH, state)
    print(f"wrote {G.STATE_PATH.relative_to(G.REPO)}: " +
          ", ".join(f"{k}={v}" for k, v in state["counts"].items() if v))
    return 0


def cmd_ownership(args):
    graph = G.load_graph()
    own = G.build_ownership(graph)
    G.write_json(G.OWNERSHIP_PATH, own)
    n = len(own["contested_files"])
    print(f"wrote {G.OWNERSHIP_PATH.relative_to(G.REPO)}: "
          f"{len(own['file_to_nodes'])} owned files, {n} contested")
    return 1 if n else 0


def cmd_ready(args):
    graph = G.load_graph()
    state = G.derive_state(graph, G.load_events())
    idx = G.node_index(graph)
    ready = [n for n in state["topological_order"] if state["status"][n] == "READY"]
    if args.lane:
        ready = [n for n in ready if idx[n]["lane"] == args.lane]
    for n in ready:
        print(f"{n}\t{idx[n]['lane']}\t{idx[n]['title']}")
    return 0


def cmd_show(args):
    idx = G.node_index(G.load_graph())
    if args.id not in idx:
        print(f"no such node: {args.id}")
        return 1
    print(json.dumps(idx[args.id], indent=2, sort_keys=True))
    return 0


def cmd_event(args):
    graph = G.load_graph()
    idx = G.node_index(graph)
    if args.event not in G.KNOWN_EVENT_TYPES:
        print(f"unknown event type {args.event!r}; known: {sorted(G.KNOWN_EVENT_TYPES)}")
        return 1
    if args.node and args.node not in idx:
        print(f"event references undeclared node {args.node!r}")
        return 1
    rec = {"ts": _now(), "event": args.event}
    if args.node:
        rec["node"] = args.node
    if args.detail:
        rec["detail"] = args.detail
    for kv in args.field or []:
        if "=" not in kv:
            print(f"--field expects key=value, got {kv!r}")
            return 1
        k, v = kv.split("=", 1)
        try:
            rec[k] = json.loads(v)
        except json.JSONDecodeError:
            rec[k] = v
    rec["repo"] = {"head": G.git("rev-parse", "HEAD"), "branch": G.git("rev-parse", "--abbrev-ref", "HEAD")}
    G.append_jsonl(G.EVENTS_PATH, rec)
    print(f"appended: {rec['event']} {rec.get('node', '')}".rstrip())
    return 0


def cmd_decision(args):
    rec = {
        "ts": _now(),
        "decision_id": args.decision_id,
        "question": args.question,
        "ruling": args.ruling,
        "authority": args.authority,
        "made_by": args.made_by,
    }
    if args.nodes:
        rec["nodes"] = args.nodes
    if args.preserved_disagreement:
        rec["preserved_disagreement"] = args.preserved_disagreement
    G.append_jsonl(G.DECISIONS_PATH, rec)
    G.append_jsonl(G.EVENTS_PATH, {
        "ts": rec["ts"], "event": "decision_recorded",
        "decision_id": args.decision_id,
        "repo": {"head": G.git("rev-parse", "HEAD")},
    })
    print(f"recorded decision {args.decision_id}")
    return 0


def cmd_summary(args):
    graph = G.load_graph()
    state = G.derive_state(graph, G.load_events())
    print(" ".join(f"{k}={v}" for k, v in state["counts"].items() if v))
    return 0


def cmd_status(args):
    graph = G.load_graph()
    events = G.load_events()
    state = G.derive_state(graph, events)
    idx = G.node_index(graph)
    facts = G.repo_facts()
    c = state["counts"]

    ready = [n for n in state["topological_order"] if state["status"][n] == "READY"]
    running = [n for n in state["topological_order"] if state["status"][n] in ("RUNNING", "VERIFYING")]
    passed = [n for n in state["topological_order"] if state["status"][n] == "PASSED"]
    failed = [n for n in state["topological_order"] if state["status"][n] in ("FAILED", "HALTED")]
    gates = [n for n in state["topological_order"] if state["status"][n] == "USER_REQUIRED"]

    sev_a = [n for n in failed if idx[n]["severity_on_failure"] == "A"]

    L = []
    L.append("# Current status — autonomous program graph")
    L.append("")
    L.append("Generated by `scripts/graphctl.py status`. Derived from `PROGRAM_GRAPH.json` and the")
    L.append("append-only `GRAPH_EVENTS.jsonl`. Not hand-maintained.")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append(f"| branch | `{facts['branch']}` |")
    L.append(f"| HEAD | `{facts['head']}` |")
    L.append(f"| working tree | {'clean' if facts['working_tree_clean'] else 'DIRTY'} |")
    L.append(f"| nodes | {state['n_nodes']} |")
    L.append(f"| events | {state['n_events']} |")
    L.append("")
    L.append("## Counts by status")
    L.append("")
    L.append("| status | n |")
    L.append("|---|---|")
    for k, v in c.items():
        if v:
            L.append(f"| {k} | {v} |")
    L.append("")

    L.append("## Severity A blockers")
    L.append("")
    if sev_a:
        for n in sev_a:
            L.append(f"* **{n}** — {idx[n]['title']}")
    else:
        L.append("None open against a node.")
    L.append("")

    L.append("## Running")
    L.append("")
    L.extend([f"* `{n}` — {idx[n]['title']}" for n in running] or ["None."])
    L.append("")

    L.append("## Ready — next automatically scheduled")
    L.append("")
    L.extend([f"* `{n}` ({idx[n]['lane']}) — {idx[n]['title']}" for n in ready] or ["None."])
    L.append("")

    L.append("## Passed")
    L.append("")
    L.extend([f"* `{n}` — {idx[n]['title']}" for n in passed] or ["None yet."])
    L.append("")

    L.append("## Human gates")
    L.append("")
    L.extend([f"* `{n}` — {idx[n]['title']}" for n in gates] or ["None open."])
    L.append("")

    L.append("## By lane")
    L.append("")
    L.append("| lane | " + " | ".join(k for k in c if c[k]) + " |")
    L.append("|---|" + "---|" * len([k for k in c if c[k]]))
    for lane in sorted(state["by_lane"]):
        row = state["by_lane"][lane]
        L.append(f"| {lane} | " + " | ".join(str(len(row.get(k, []))) for k in c if c[k]) + " |")
    L.append("")

    G.STATUS_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(G.STATUS_REPORT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
    print(f"wrote {G.STATUS_REPORT_PATH.relative_to(G.REPO)}")
    return 0


# ---------------------------------------------------------------- cli

def main(argv=None):
    ap = argparse.ArgumentParser(prog="graphctl")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("state"); p.add_argument("--check", action="store_true"); p.set_defaults(fn=cmd_state)
    p = sub.add_parser("ownership"); p.set_defaults(fn=cmd_ownership)
    p = sub.add_parser("ready"); p.add_argument("--lane"); p.set_defaults(fn=cmd_ready)
    p = sub.add_parser("show"); p.add_argument("id"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("summary"); p.set_defaults(fn=cmd_summary)
    p = sub.add_parser("status"); p.set_defaults(fn=cmd_status)

    p = sub.add_parser("event")
    p.add_argument("event"); p.add_argument("--node"); p.add_argument("--detail")
    p.add_argument("--field", action="append")
    p.set_defaults(fn=cmd_event)

    p = sub.add_parser("decision")
    p.add_argument("--decision-id", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--ruling", required=True)
    p.add_argument("--authority", required=True)
    p.add_argument("--made-by", required=True)
    p.add_argument("--nodes", nargs="*")
    p.add_argument("--preserved-disagreement")
    p.set_defaults(fn=cmd_decision)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
