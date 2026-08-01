#!/usr/bin/env python
"""test_gate_layers.py — the gate must never again report one aggregate number.

WHAT THIS PROTECTS
------------------
`verify_all.py` runs two different kinds of check:

  * the REPOSITORY GATE (8 checks), which reproduces from a clean checkout;
  * the OPERATIONAL CERTIFICATION (1 check), which reads git-ignored capture
    data and therefore cannot be reproduced from any commit.

Adding them together produced "all 9 checks green", a claim that was true of a
machine rather than of a commit. These tests make that regression fail loudly:

  1. the two layers are declared separately and `daily_certify` is only in B;
  2. no aggregate "all N checks green" string survives in the reporting code;
  3. `--repository-gate` (and its `--quick` alias) runs layer A only;
  4. the installed pre-push hook runs layer A only — a clean checkout must not
     be refused a push for lacking capture files it never contained;
  5. the JSON summary exposes the layers separately and carries no aggregate
     green-count field;
  6. an operational WARN is reported as WARN, not silently as PASS.

Nothing here runs the real gate — that would take minutes and need live data.
The layer wiring is tested directly, and the reporting is tested against stub
check results.

Usage:  python tests/test_gate_layers.py
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("verify_all", REPO / "verify_all.py")
va = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(va)

PASSED = 0
FAILED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED
    if cond:
        PASSED += 1
    else:
        FAILED.append(f"{name}: {detail}")


def _stub(name: str, ok: bool, summary: str = "", output: str = "") -> dict:
    return {"name": name, "exit": 0 if ok else 1, "ok": ok, "elapsed": 0.0,
            "summary": summary, "runner_error": False, "output": output}


def _run_main(argv: list[str], stub_results: dict[str, dict]) -> tuple[str, int]:
    """Run verify_all.main() with run_check stubbed, capturing stdout."""
    real = va.run_check
    va.run_check = lambda name, cmd: stub_results[name]
    real_argv = sys.argv
    sys.argv = ["verify_all.py"] + argv
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = va.main()
    finally:
        va.run_check = real
        sys.argv = real_argv
    return buf.getvalue(), rc


# --------------------------------------------------------------------------
# 1. layer membership
# --------------------------------------------------------------------------
repo_names = [n for n, _ in va.REPOSITORY_CHECKS]
op_names = [n for n, _ in va.OPERATIONAL_CHECKS]

# Layer A was 8 checks when the split was specified; it is 10 now because this
# suite and tests/test_cbs_builders.py were wired in. The cardinality is not the
# invariant -- the MEMBERSHIP is. What must never change is that every check in
# layer A reads only committed files, and that daily_certify is not among them.
check("layer A has 10 checks", len(va.REPOSITORY_CHECKS) == 10,
      f"got {len(va.REPOSITORY_CHECKS)}: {repo_names}")
check("layer A is all committed-file checks (no capture-data reader)",
      all("daily_certify" not in n for n in repo_names), str(repo_names))
check("this suite is wired into layer A", "test_gate_layers" in repo_names,
      "an unwired test is a test that rots")
check("layer B has 1 check", len(va.OPERATIONAL_CHECKS) == 1, f"got {op_names}")
check("daily_certify is in layer B", "daily_certify" in op_names, str(op_names))
check("daily_certify is NOT in layer A", "daily_certify" not in repo_names, str(repo_names))
check("layers are disjoint", not (set(repo_names) & set(op_names)),
      str(set(repo_names) & set(op_names)))
check("back-compat aliases still resolve",
      va.CHECKS is va.REPOSITORY_CHECKS and va.SLOW_CHECKS is va.OPERATIONAL_CHECKS)

# --------------------------------------------------------------------------
# 2. the retired aggregate label is gone from the source
# --------------------------------------------------------------------------
src = (REPO / "verify_all.py").read_text(encoding="utf-8")
# Look only at code, not at the module docstring that explains the history.
code = src.split('"""', 2)[-1]
check("no 'all N checks green' aggregate in code",
      not re.search(r"all\s*\{?\s*len\(results\)|all \d+ checks green", code),
      "an aggregate green-count string is back")
check("no bare 'GATE: PASS' aggregate in code",
      "GATE: PASS  (all" not in code, "the retired aggregate label is back")
check("both layer headings exist",
      "REPOSITORY GATE" in code and "OPERATIONAL CERTIFICATION" in code)

# --------------------------------------------------------------------------
# 3. --repository-gate / --quick run layer A only
# --------------------------------------------------------------------------
stubs = {n: _stub(n, True, "ok") for n in repo_names}
stubs["daily_certify"] = _stub("daily_certify", True, "SUMMARY: WARN",
                               "SUMMARY: WARN  (0 fail, 1 warn, 9 pass/skip)")

for flag in ("--repository-gate", "--quick"):
    out, rc = _run_main([flag], stubs)
    check(f"{flag} exits 0 when layer A is green", rc == 0, f"rc={rc}")
    check(f"{flag} reports REPOSITORY GATE: PASS", "REPOSITORY GATE: PASS" in out, out)
    check(f"{flag} skips layer B", "OPERATIONAL CERTIFICATION: SKIPPED" in out, out)
    # A per-layer "n/n checks green" is fine and wanted; what must never come
    # back is a CROSS-LAYER aggregate that adds the two together.
    check(f"{flag} emits no cross-layer aggregate",
          "GATE: PASS  (all" not in out
          and not re.search(r"all \d+ checks green", out), out)

# --------------------------------------------------------------------------
# 4. the installed hook runs layer A only
# --------------------------------------------------------------------------
hook_src = None
for line in src.splitlines():
    if "verify_all.py" in line and "exec python" in line:
        hook_src = line
check("install_hook writes a pre-push command", hook_src is not None)
check("the pre-push hook runs --repository-gate",
      hook_src is not None and "--repository-gate" in hook_src, str(hook_src))

# --------------------------------------------------------------------------
# 5. JSON exposes layers separately, with no aggregate count
# --------------------------------------------------------------------------
out, rc = _run_main(["--json"], stubs)
payload = json.loads(out)
check("json has repository_gate", "repository_gate" in payload, str(payload.keys()))
check("json has operational_certification", "operational_certification" in payload)
check("json repository_gate counts every layer-A check",
      payload["repository_gate"]["n_checks"] == len(va.REPOSITORY_CHECKS),
      str(payload["repository_gate"]["n_checks"]))
check("json operational counts 1", payload["operational_certification"]["n_checks"] == 1)
check("json has no top-level aggregate check list", "checks" not in payload,
      "a flat aggregate check list is back")

# --------------------------------------------------------------------------
# 6. WARN is reported as WARN, and failures still exit non-zero
# --------------------------------------------------------------------------
out, rc = _run_main([], stubs)
check("operational WARN is surfaced as WARN",
      "OPERATIONAL CERTIFICATION: WARN" in out, out)
check("operational WARN does not fail the run", rc == 0, f"rc={rc}")

clean = dict(stubs)
clean["daily_certify"] = _stub("daily_certify", True, "SUMMARY: PASS", "SUMMARY: PASS")
out, rc = _run_main([], clean)
check("operational clean is reported PASS", "OPERATIONAL CERTIFICATION: PASS" in out, out)

failing = dict(stubs)
failing["daily_certify"] = _stub("daily_certify", False, "SUMMARY: FAIL", "SUMMARY: FAIL")
out, rc = _run_main([], failing)
check("operational FAIL is reported FAIL", "OPERATIONAL CERTIFICATION: FAIL" in out, out)
check("operational FAIL exits non-zero", rc == 1, f"rc={rc}")
check("layer A still PASSes when only layer B fails",
      "REPOSITORY GATE: PASS" in out, out)

repo_broken = dict(stubs)
repo_broken[repo_names[0]] = _stub(repo_names[0], False, "boom")
out, rc = _run_main(["--repository-gate"], repo_broken)
check("layer A failure exits non-zero", rc == 1, f"rc={rc}")
check("layer A failure is reported FAIL", "REPOSITORY GATE: FAIL" in out, out)

# --------------------------------------------------------------------------

print(f"{PASSED}/{PASSED + len(FAILED)} tests passed")
for f in FAILED:
    print(f"  FAIL  {f}")
sys.exit(1 if FAILED else 0)
