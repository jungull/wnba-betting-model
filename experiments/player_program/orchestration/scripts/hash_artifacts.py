#!/usr/bin/env python
"""Freeze artifact bytes into ARTIFACT_LEDGER.jsonl.

Two uses, and the distinction matters:

  --freeze-inputs NODE    hash every input_artifact of a node BEFORE its agent launches,
                          and write the digests into the node's input_hashes. This is what
                          makes "the agent saw exactly these bytes" checkable afterwards.

  --freeze-output PATH    hash a raw agent output BEFORE any other source or synthesis can
                          read it. Independence of sources is only real if the bytes are
                          pinned at the moment they land.

  --verify NODE           rederive a node's frozen input hashes and fail on divergence.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

import graph_lib as G


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iter_files(rel):
    p = G.REPO / rel
    if p.is_file():
        yield rel, p
    elif p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                yield str(f.relative_to(G.REPO)).replace("\\", "/"), f


def _record(path, digest, kind, node=None, note=None):
    rec = {"ts": _now(), "path": path, "sha256": digest, "kind": kind}
    if node:
        rec["node"] = node
    if note:
        rec["note"] = note
    rec["head"] = G.git("rev-parse", "HEAD")
    G.append_jsonl(G.ARTIFACTS_PATH, rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze-inputs")
    ap.add_argument("--freeze-output", action="append", default=[])
    ap.add_argument("--verify")
    ap.add_argument("--note")
    args = ap.parse_args()

    if args.freeze_inputs:
        graph = G.load_graph()
        idx = G.node_index(graph)
        node = idx.get(args.freeze_inputs)
        if node is None:
            print(f"no such node: {args.freeze_inputs}")
            return 1
        frozen, missing = {}, []
        for rel in node["input_artifacts"]:
            found = list(_iter_files(rel))
            if not found:
                missing.append(rel)
                continue
            for p, fp in found:
                d = G.sha256_file(fp)
                frozen[p] = d
                _record(p, d, "node_input", node["id"])
        node["input_hashes"] = dict(sorted(frozen.items()))
        G.write_json(G.GRAPH_PATH, graph)
        G.append_jsonl(G.EVENTS_PATH, {
            "ts": _now(), "event": "input_frozen", "node": node["id"],
            "n_inputs": len(frozen), "missing": missing,
            "head": G.git("rev-parse", "HEAD"),
        })
        print(f"{node['id']}: froze {len(frozen)} input file(s)"
              + (f"; MISSING {missing}" if missing else ""))
        return 1 if missing else 0

    if args.freeze_output:
        rc = 0
        for rel in args.freeze_output:
            found = list(_iter_files(rel))
            if not found:
                print(f"MISSING: {rel}")
                rc = 1
                continue
            for p, fp in found:
                d = G.sha256_file(fp)
                _record(p, d, "raw_output", note=args.note)
                G.append_jsonl(G.EVENTS_PATH, {
                    "ts": _now(), "event": "raw_output_frozen",
                    "path": p, "sha256": d, "note": args.note,
                    "head": G.git("rev-parse", "HEAD"),
                })
                print(f"{d}  {p}")
        return rc

    if args.verify:
        idx = G.node_index(G.load_graph())
        node = idx.get(args.verify)
        if node is None:
            print(f"no such node: {args.verify}")
            return 1
        if not node["input_hashes"]:
            print(f"{node['id']}: no frozen input hashes to verify")
            return 1
        bad = []
        for p, expected in sorted(node["input_hashes"].items()):
            actual = G.file_digest_or_none(p)
            if actual != expected:
                bad.append((p, expected, actual))
        for p, e, a in bad:
            print(f"FAIL {p}: expected {e[:12]}… actual {(a or 'MISSING')[:12]}…")
        if bad:
            print(f"{len(bad)} input(s) diverged — the node's evidence base changed under it")
            return 1
        print(f"OK: {len(node['input_hashes'])} input hash(es) rederive for {node['id']}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
