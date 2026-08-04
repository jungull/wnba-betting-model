#!/usr/bin/env python
"""Fail any change that touches a frozen path.

Task-specific guard. It deliberately does NOT modify feature_gate.py or any other shared
contract -- enforcement belongs at the call site, per GRAPH_POLICY.md section 3.

    frozen_path_guard.py --range A..B
    frozen_path_guard.py --paths p1 p2 ...
    frozen_path_guard.py --staged

Exit 1 on any violation. The registry files are a special case: appending records is allowed
after a passed preregistration gate, so a registry change is reported as APPEND-ONLY-CHECK
and passes only if every existing line is byte-identical to its previous version.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

import graph_lib as G

APPEND_ONLY = {
    "experiments/player_program/arm_registry.jsonl",
    "experiments/player_program/registry.jsonl",
}


def _changed(args):
    if args.paths:
        return list(args.paths)
    if args.staged:
        return [p for p in G.git("diff", "--cached", "--name-only").splitlines() if p]
    if args.range:
        return [p for p in G.git("diff", "--name-only", args.range).splitlines() if p]
    return [p for p in G.git("diff", "--name-only", "HEAD").splitlines() if p]


def _append_only_ok(path, base):
    """Every previously existing line must survive byte-identically, in order."""
    old = subprocess.run(["git", "show", f"{base}:{path}"], cwd=str(G.REPO),
                         capture_output=True, text=True)
    if old.returncode != 0:
        return True, "new file"
    old_lines = old.stdout.splitlines()
    try:
        with open(G.REPO / path, "r", encoding="utf-8") as fh:
            new_lines = fh.read().splitlines()
    except FileNotFoundError:
        return False, "existing registry file was DELETED"
    if len(new_lines) < len(old_lines):
        return False, f"record count fell from {len(old_lines)} to {len(new_lines)}"
    for i, (a, b) in enumerate(zip(old_lines, new_lines), 1):
        if a != b:
            return False, f"existing record {i} was EDITED (registry is append-only)"
    return True, f"append-only OK: {len(old_lines)} -> {len(new_lines)} records"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--range")
    ap.add_argument("--paths", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--base", default="HEAD")
    args = ap.parse_args()

    changed = _changed(args)
    if not changed:
        print("OK: no changed paths")
        return 0

    violations = G.frozen_violations(changed)
    hard, soft = [], []
    for v in violations:
        if v["path"] in APPEND_ONLY:
            ok, why = _append_only_ok(v["path"], args.base)
            (soft if ok else hard).append({**v, "detail": why})
        else:
            hard.append(v)

    for s in soft:
        print(f"NOTE  {s['path']}: {s['detail']}")
    for h in hard:
        print(f"FAIL  {h['path']}: {h['rule']}" + (f" — {h['detail']}" if h.get("detail") else ""))

    if hard:
        print(f"\n{len(hard)} frozen-path violation(s). Severity A: altered frozen artifact.")
        return 1
    print(f"OK: {len(changed)} changed path(s), no frozen-path violation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
