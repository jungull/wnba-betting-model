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

USAGE
-----
    python verify_all.py                 # full gate (slow: daily_certify included)
    python verify_all.py --quick         # skip daily_certify (~minutes faster)
    python verify_all.py --json          # machine-readable summary on stdout

    # optional: refuse to push unless the gate is green
    python verify_all.py --install-hook  # writes .git/hooks/pre-push

EXIT CODES
----------
    0  every check passed
    1  at least one check failed
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

#: The five suites named in the constitution, plus the invariant and chain checks.
#: Order is cheapest-first so a broken tree fails fast.
CHECKS = [
    ("test_evalharness",           [sys.executable, "tests/test_evalharness.py"]),
    ("test_forecast_log",          [sys.executable, "tests/test_forecast_log.py"]),
    ("test_permutation_integrity", [sys.executable, "tests/test_permutation_integrity.py"]),
    ("test_asof_invariant",        [sys.executable, "tests/test_asof_invariant.py"]),
    ("test_edge_target_identity",  [sys.executable, "tests/test_edge_target_identity.py"]),
    ("test_prediction_contract_v2",[sys.executable, "tests/test_prediction_contract_v2.py"]),
    ("asof_manifest_scan",         [sys.executable, "asof_invariant.py", "--scan"]),
    ("forecast_chain",             [sys.executable, "-c",
                                    "import sys;from evalharness import verify_chain;"
                                    "r=verify_chain('forecasts/forecast_log.jsonl');"
                                    "print(f'chain ok={r.ok} n_records={getattr(r,\"n_records\",\"?\")}');"
                                    "sys.exit(0 if r.ok else 1)"]),
]

SLOW_CHECKS = [
    ("daily_certify",              [sys.executable, "daily_certify.py"]),
]


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
    hook = REPO / ".git" / "hooks" / "pre-push"
    if not hook.parent.is_dir():
        print(f"[!] {hook.parent} does not exist — is this a git repo?", file=sys.stderr)
        return 2
    hook.write_text(
        "#!/bin/sh\n"
        "# Installed by verify_all.py --install-hook.\n"
        "# Refuses the push unless the full gate is green.  Bypass with --no-verify\n"
        "# only when you can say out loud why the gate does not apply.\n"
        'exec python "$(git rev-parse --show-toplevel)/verify_all.py"\n',
        encoding="utf-8",
    )
    try:                                        # no-op on Windows, matters elsewhere
        hook.chmod(0o755)
    except OSError:
        pass
    print(f"[ok] pre-push hook installed at {hook}")
    print("     every 'git push' now runs the full gate first.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quick", action="store_true",
                    help="skip daily_certify (the slow data-certification pass)")
    ap.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    ap.add_argument("--install-hook", action="store_true",
                    help="write .git/hooks/pre-push and exit")
    args = ap.parse_args()

    if args.install_hook:
        return install_hook()

    checks = list(CHECKS) + ([] if args.quick else list(SLOW_CHECKS))
    results = []
    if not args.json:
        print(f"verify_all — {len(checks)} checks, repo {REPO}")
        print("-" * 78)

    for name, cmd in checks:
        r = run_check(name, cmd)
        results.append(r)
        if not args.json:
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"  {mark}  {name:28s} exit={str(r['exit']):>4s}  "
                  f"{r['elapsed']:5.1f}s  {r['summary'][:70]}")

    failed = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({"ok": not failed,
                          "checks": [{k: v for k, v in r.items() if k != "output"}
                                     for r in results]}, indent=1))
    else:
        print("-" * 78)
        if failed:
            print(f"GATE: FAIL  ({len(failed)} of {len(results)} checks failed)")
            for r in failed:
                print(f"  ! {r['name']}: {r['summary']}")
            print("\nFull output of the first failure:\n")
            print((failed[0].get("output") or "")[-3000:])
        else:
            print(f"GATE: PASS  (all {len(results)} checks green"
                  f"{' — quick mode, daily_certify skipped' if args.quick else ''})")

    if any(r.get("runner_error") for r in results):
        return 2
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
