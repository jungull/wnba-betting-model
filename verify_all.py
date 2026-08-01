#!/usr/bin/env python
"""verify_all.py — the one command that decides whether this repo may be pushed.

WHY THIS EXISTS
---------------
The constitution gates every commit on five test suites, the as-of manifest scan,
the forecast chain, and daily certification.  Until now that gate lived in a
human's (or an agent's) memory: someone had to remember the list, run it, and
read the output honestly.  A gate enforced by recollection is not a gate.

This script makes the gate a deterministic artifact with an exit code.  It runs
every required check, reports each one's own exit status, and returns non-zero if
any of them failed.  It decides nothing on its own — it only aggregates what the
underlying checks already report.  No check's verdict is reinterpreted here, and
a check that cannot be run counts as a failure, never as a pass.

TWO LAYERS, NEVER ONE NUMBER
----------------------------
These checks are not one kind of evidence, and adding them up produced a claim
that was true of a *machine* rather than of a *commit*:

  * **REPOSITORY GATE** — 8 checks.  Reads only committed files, so it
    reproduces from a clean checkout of a commit and nothing else.
  * **OPERATIONAL CERTIFICATION** — 1 check (`daily_certify`, the 9th).  Reads
    live capture data that is git-ignored, untracked or dirty.  It therefore
    **cannot** be reproduced from a commit, and a clean worktree legitimately
    cannot satisfy it.

So this script reports the two separately and **never** prints an aggregate
"all N checks green".  The installed pre-push hook runs the repository gate
only: a clean checkout must not be refused a push for lacking capture files it
was never supposed to contain.  Run the operational certification on the capture
machine, paired with `operational_input_manifest.py`, which hashes every
non-committed input it consumed.

USAGE
-----
    python verify_all.py                    # both layers, reported separately
    python verify_all.py --repository-gate  # layer A only (what the hook runs)
    python verify_all.py --quick            # alias of --repository-gate
    python verify_all.py --json             # machine-readable, per layer

    # optional: refuse to push unless the REPOSITORY GATE is green
    python verify_all.py --install-hook     # writes .git/hooks/pre-push

EXIT CODES
----------
    0  every check that ran passed
    1  at least one check failed (either layer)
    2  the runner itself could not execute a check (treated as failure)

NOTE ON daily_certify: it exits 0 on WARN and non-zero on FAIL.  WARN is
surfaced in the output but does not fail the gate, matching its own semantics.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent

#: LAYER A — the repository gate.  The five suites named in the constitution,
#: plus the invariant and chain checks.  Every one of these reads only committed
#: files, so this layer reproduces from a clean checkout.
#: Order is cheapest-first so a broken tree fails fast.
REPOSITORY_CHECKS = [
    ("test_evalharness",           [sys.executable, "tests/test_evalharness.py"]),
    ("test_forecast_log",          [sys.executable, "tests/test_forecast_log.py"]),
    ("test_permutation_integrity", [sys.executable, "tests/test_permutation_integrity.py"]),
    ("test_asof_invariant",        [sys.executable, "tests/test_asof_invariant.py"]),
    ("test_edge_target_identity",  [sys.executable, "tests/test_edge_target_identity.py"]),
    ("test_prediction_contract_v2",[sys.executable, "tests/test_prediction_contract_v2.py"]),
    ("test_gate_layers",           [sys.executable, "tests/test_gate_layers.py"]),
    ("test_cbs_builders",          [sys.executable, "tests/test_cbs_builders.py"]),
    ("asof_manifest_scan",         [sys.executable, "asof_invariant.py", "--scan"]),
    ("forecast_chain",             [sys.executable, "-c",
                                    "import sys;from evalharness import verify_chain;"
                                    "r=verify_chain('forecasts/forecast_log.jsonl');"
                                    "print(f'chain ok={r.ok} n_records={getattr(r,\"n_records\",\"?\")}');"
                                    "sys.exit(0 if r.ok else 1)"]),
]

#: LAYER B — the operational certification.  Environment-dependent by
#: construction: it reads git-ignored / untracked / dirty capture data.  Never
#: folded into the repository-gate count.
OPERATIONAL_CHECKS = [
    ("daily_certify",              [sys.executable, "daily_certify.py"]),
]

#: Back-compat aliases.  Older callers imported these names.
CHECKS = REPOSITORY_CHECKS
SLOW_CHECKS = OPERATIONAL_CHECKS


def _last_meaningful_line(text: str) -> str:
    """The last non-blank line — every check here ends with its own verdict."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else "(no output)"


def run_check(name: str, cmd: list[str]) -> dict:
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except Exception as exc:                    # could not even launch it
        return {"name": name, "exit": None, "ok": False, "elapsed": time.time() - started,
                "summary": f"RUNNER ERROR: {exc}", "runner_error": True}
    out = (proc.stdout or "") + (proc.stderr or "")
    return {"name": name, "exit": proc.returncode, "ok": proc.returncode == 0,
            "elapsed": time.time() - started, "summary": _last_meaningful_line(out),
            "runner_error": False, "output": out}


def install_hook() -> int:
    # Ask git where the hooks live rather than assuming REPO/".git" is a
    # directory: inside a linked worktree, .git is a FILE, and hooks are shared
    # from the common git dir. Assuming the layout silently failed there.
    try:
        common = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--git-common-dir"],
                                capture_output=True, text=True, encoding="utf-8").stdout.strip()
    except Exception:
        common = ""
    if not common:
        print(f"[!] could not resolve the git dir for {REPO} — is this a git repo?",
              file=sys.stderr)
        return 2
    git_dir = Path(common)
    if not git_dir.is_absolute():
        git_dir = (REPO / git_dir).resolve()
    hook = git_dir / "hooks" / "pre-push"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        "#!/bin/sh\n"
        "# Installed by verify_all.py --install-hook.\n"
        "# Refuses the push unless the REPOSITORY GATE (layer A) is green.\n"
        "#\n"
        "# Layer A only, deliberately.  The operational certification reads\n"
        "# git-ignored capture data, so a clean checkout cannot satisfy it and\n"
        "# must not be refused a push for lacking files it never contained.\n"
        "# Run layer B on the capture machine:\n"
        "#     python verify_all.py            # both layers, reported apart\n"
        "#     python operational_input_manifest.py --out <manifest>\n"
        "#\n"
        "# Bypass with --no-verify only when you can say out loud why the gate\n"
        "# does not apply.\n"
        'exec python "$(git rev-parse --show-toplevel)/verify_all.py" --repository-gate\n',
        encoding="utf-8",
    )
    try:                                        # no-op on Windows, matters elsewhere
        hook.chmod(0o755)
    except OSError:
        pass
    print(f"[ok] pre-push hook installed at {hook}")
    print("     every 'git push' now runs the REPOSITORY GATE (layer A) first.")
    print("     the operational certification is NOT run by the hook — it needs")
    print("     capture data no commit contains.  Run it separately.")
    return 0


def _certify_state(r: dict) -> str:
    """PASS / WARN / FAIL for an operational check.

    daily_certify exits 0 on WARN, so the exit code alone cannot distinguish
    'clean' from 'warned'; its own SUMMARY line is the authority.
    """
    if not r["ok"]:
        return "FAIL"
    return "WARN" if "SUMMARY: WARN" in (r.get("output") or "") else "PASS"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repository-gate", "--quick", dest="repository_gate",
                    action="store_true",
                    help="run LAYER A only (the repository gate); skip the "
                         "environment-dependent operational certification")
    ap.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    ap.add_argument("--install-hook", action="store_true",
                    help="write .git/hooks/pre-push and exit")
    args = ap.parse_args()

    if args.install_hook:
        return install_hook()

    def run_layer(title: str, checks: list, note: str = "") -> list[dict]:
        if not args.json:
            print()
            print(f"{title} — {len(checks)} check{'s' if len(checks) != 1 else ''}"
                  f"{'  (' + note + ')' if note else ''}")
            print("-" * 78)
        out = []
        for name, cmd in checks:
            r = run_check(name, cmd)
            out.append(r)
            if not args.json:
                mark = "PASS" if r["ok"] else "FAIL"
                print(f"  {mark}  {name:28s} exit={str(r['exit']):>4s}  "
                      f"{r['elapsed']:5.1f}s  {r['summary'][:70]}")
        return out

    if not args.json:
        print(f"verify_all — repo {REPO}")

    repo_results = run_layer("REPOSITORY GATE", list(REPOSITORY_CHECKS),
                             "reproduces from a clean checkout")
    repo_failed = [r for r in repo_results if not r["ok"]]
    if not args.json:
        print("-" * 78)
        state = "FAIL" if repo_failed else "PASS"
        print(f"REPOSITORY GATE: {state}  "
              f"({len(repo_results) - len(repo_failed)}/{len(repo_results)} checks green)")
        for r in repo_failed:
            print(f"  ! {r['name']}: {r['summary']}")

    op_results: list[dict] = []
    op_state = "SKIPPED"
    if not args.repository_gate:
        op_results = run_layer("OPERATIONAL CERTIFICATION", list(OPERATIONAL_CHECKS),
                               "environment-dependent; NOT reproducible from a commit")
        op_state = _certify_state(op_results[0]) if op_results else "SKIPPED"
        if not args.json:
            print("-" * 78)
            print(f"OPERATIONAL CERTIFICATION: {op_state}")
            for r in op_results:
                if not r["ok"]:
                    print(f"  ! {r['name']}: {r['summary']}")
            print("  (bind its non-committed inputs with operational_input_manifest.py;")
            print("   a layer-B result is only meaningful with that manifest hash)")
    elif not args.json:
        print()
        print("OPERATIONAL CERTIFICATION: SKIPPED  (--repository-gate)")
        print("  run it on the capture machine; a clean checkout cannot supply its inputs")

    results = repo_results + op_results
    failed = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({
            "ok": not failed,
            "repository_gate": {
                "state": "FAIL" if repo_failed else "PASS",
                "n_checks": len(repo_results),
                "n_green": len(repo_results) - len(repo_failed),
                "checks": [{k: v for k, v in r.items() if k != "output"}
                           for r in repo_results],
            },
            "operational_certification": {
                "state": op_state,
                "n_checks": len(op_results),
                "checks": [{k: v for k, v in r.items() if k != "output"}
                           for r in op_results],
            },
            # deliberately no aggregate "N of N green" field: the two layers are
            # different kinds of evidence and must not be added together
        }, indent=1))
    elif failed:
        print("\nFull output of the first failure:\n")
        # A failing check's captured output can contain characters the console
        # encoding cannot represent (cp1252 on Windows, plus U+FFFD from our own
        # errors="replace" decode). Printing it raw made the RUNNER crash while
        # reporting someone else's failure, which hid the real one.
        blob = (failed[0].get("output") or "")[-3000:]
        enc = (sys.stdout.encoding or "utf-8")
        print(blob.encode(enc, errors="replace").decode(enc, errors="replace"))

    if any(r.get("runner_error") for r in results):
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
