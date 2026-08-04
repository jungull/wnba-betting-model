#!/usr/bin/env python
"""Reconcile the live repository before any write.

Never trust a relayed state. This resolves the actual branch, HEAD and cleanliness, checks
declared ancestry, lists the commit range, and rederives every frozen artifact hash. It
writes nothing except (optionally) a reconciliation event.

    reconcile_repo.py [--expect-head SHA] [--expect-ancestor SHA ...]
                      [--scope PREFIX] [--since SHA] [--emit-event] [--json]

Exit 1 on any hash divergence or ancestry failure. A scope violation is reported and exits 1
as well: an unexpected file outside the declared scope is preserved and surfaced, never
discarded.
"""

from __future__ import annotations

import argparse
import json
import sys

import graph_lib as G

# Frozen artifacts whose hashes are pinned by prior accepted work. A divergence here is a
# Severity A "altered frozen artifact" finding under RESEARCH_CONTRACT_V1.
PINNED = {
    "experiments/player_program/stage2a/EVIDENCE_PACKET.json":
        "f373e3eed710026c9d82ff88aad1e9a2cae640ee461a5d7df5208d76abaf1e4e",
    "experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json":
        "3a35ae735333c47713d6e7cc4c35c081e4eb07364c71cba744db03709730a32c",
    "experiments/player_program/stage2a/V2_HYPOTHESES_basketball.md":
        "6ee4af03f99a79e1daffd9dd8208730151552561e5794742decb3043aaa32690",
    "experiments/player_program/stage2a/V2_HYPOTHESES_adversarial.md":
        "e38857002413f322887d47aac27bec770832e4f424824daeba9bafd1c07c5a92",
    "experiments/player_program/stage2a/V2_HYPOTHESES_estimator.md":
        "c4d6680612ade6c523c7a0bb592eeb999b5b14cffe0d21fa08552a0e5e8440df",
    "experiments/player_program/stage2a/V2_STOP_CONDITION.json":
        "a4dd090b2b38dfb4d37028e15daa10c689deb27269cde3d8b9cddd12fd92244d",
    "experiments/player_program/stage2a/V2_GENERATION_ORDER.json":
        "1998d5fda12ece9554d1ace895d010e46ba647c526df0e5170ae12e1a5f340ce",
}

# Shared contracts, pinned from PROGRAM_STATE.json at the time the graph was bootstrapped.
PINNED_CONTRACTS = {
    "experiments/player_program/feature_gate.py":
        "b064c2c4675d354ec5cb5c6647782634c8139ca4233a5d732f408b6c2532f9a7",
    "experiments/player_program/comparison_gate.py":
        "c2d242581cc7551c6ce7d3aaf554f0cc18fd9b1f72677edd61ba95f91a7b5b92",
    "experiments/player_program/gate_invocation.py":
        "5c144b12c67910a4996aafe08e86e8939a2a1878168431850a99d22754ff9ded",
    "experiments/player_program/receipt_integrity.py":
        "8c88617407d6dfb50c394ad5888ff77cd2464b590242a35c5f97a1320e05751d",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect-head")
    ap.add_argument("--expect-ancestor", action="append", default=[])
    ap.add_argument("--scope", action="append", default=[])
    ap.add_argument("--since")
    ap.add_argument("--emit-event", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    facts = G.repo_facts()
    report = {"repo": facts, "checks": {}, "failures": []}

    if args.expect_head:
        ok = facts["head"].startswith(args.expect_head) or args.expect_head.startswith(facts["head"][:7])
        report["checks"]["expected_head"] = {"expected": args.expect_head, "actual": facts["head"], "match": ok}
        if not ok:
            report["failures"].append(
                f"HEAD is {facts['head'][:7]}, expected {args.expect_head}; "
                f"the relayed state is stale — reconcile before writing")

    anc = {}
    for a in args.expect_ancestor:
        res = G.git("merge-base", "--is-ancestor", a, "HEAD", check=False)
        code = 0 if res == "" else 1
        import subprocess
        code = subprocess.run(["git", "merge-base", "--is-ancestor", a, "HEAD"],
                              cwd=str(G.REPO), capture_output=True).returncode
        anc[a] = (code == 0)
        if code != 0:
            report["failures"].append(f"{a} is NOT an ancestor of HEAD")
    report["checks"]["ancestry"] = anc

    if args.since:
        commits = []
        raw = G.git("log", "--format=%H%x1f%an%x1f%s", f"{args.since}..HEAD")
        for line in raw.splitlines():
            if not line.strip():
                continue
            h, an, subj = line.split("\x1f")
            commits.append({"sha": h, "author": an, "subject": subj})
        changed = [p for p in G.git("diff", "--name-only", f"{args.since}..HEAD").splitlines() if p]
        report["checks"]["range"] = {
            "since": args.since, "n_commits": len(commits), "commits": commits,
            "n_files": len(changed), "changed_files": changed,
        }
        if args.scope:
            out = [p for p in changed if not any(p.startswith(s) for s in args.scope)]
            report["checks"]["out_of_scope"] = out
            if out:
                report["failures"].append(
                    f"{len(out)} changed file(s) outside declared scope {args.scope}: {out[:10]} "
                    f"-- PRESERVED, not discarded; open an integration node")

    hashes = {}
    for path, expected in {**PINNED, **PINNED_CONTRACTS}.items():
        actual = G.file_digest_or_none(path)
        match = (actual == expected)
        hashes[path] = {"expected": expected, "actual": actual, "match": match}
        if not match:
            report["failures"].append(
                f"FROZEN ARTIFACT DIVERGED (Severity A): {path} "
                f"expected {expected[:12]}… actual {(actual or 'MISSING')[:12]}…")
    report["checks"]["frozen_hashes"] = hashes
    report["ok"] = not report["failures"]

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"branch      {facts['branch']}")
        print(f"HEAD        {facts['head']}")
        print(f"tree        {'clean' if facts['working_tree_clean'] else 'DIRTY (' + str(len(facts['dirty_paths'])) + ' paths)'}")
        for a, ok in anc.items():
            print(f"ancestor    {a} {'YES' if ok else 'NO'}")
        if args.since:
            r = report["checks"]["range"]
            print(f"range       {args.since}..HEAD  {r['n_commits']} commits, {r['n_files']} files")
        nmatch = sum(1 for v in hashes.values() if v["match"])
        print(f"frozen      {nmatch}/{len(hashes)} artifacts reconcile")
        for f in report["failures"]:
            print(f"FAIL        {f}")
        if report["ok"]:
            print("OK          live state reconciled")

    if args.emit_event:
        G.append_jsonl(G.EVENTS_PATH, {
            "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": "reconciliation",
            "ok": report["ok"],
            "head": facts["head"],
            "branch": facts["branch"],
            "working_tree_clean": facts["working_tree_clean"],
            "frozen_reconciled": sum(1 for v in hashes.values() if v["match"]),
            "frozen_total": len(hashes),
            "failures": report["failures"],
        })

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
