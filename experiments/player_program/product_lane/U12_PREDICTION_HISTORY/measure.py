"""Produce EVIDENCE_measured.json for U12_PREDICTION_HISTORY.

EPISTEMIC STATUS: PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must
not imply a model has been promoted.

Every number in REPORT.md comes from this script or from the two scripts it invokes. It runs
TESTS.py and build_fixture_history.py as subprocesses and records what they actually printed and
returned -- nothing here is asserted by hand.

Read-only outside this node's own directory. It runs no git command and reads no sealed result.

    python experiments/player_program/product_lane/U12_PREDICTION_HISTORY/measure.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAM = HERE.parents[1]                      # experiments/player_program
REPO = PROGRAM.parents[1]                      # worktree root

sys.path.insert(0, str(HERE))
import prediction_history as ph                # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(script: Path) -> dict:
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, cwd=str(REPO))
    out = r.stdout + r.stderr
    return {
        "command": f"python {script.relative_to(REPO).as_posix()}",
        "returncode": r.returncode,
        "n_pass": out.count("  PASS  "),
        "n_fail": out.count("  FAIL  "),
        "n_skip": out.count("  SKIP  "),
        "last_line": [l for l in out.splitlines() if l.strip()][-1] if out.strip() else "",
    }


def state_hash_check() -> dict:
    """Do the shared-contract digests PROGRAM_STATE.json records still match the bytes on disk?
    A contradiction here would be reportable; a match is a preserved negative result."""
    st = json.loads((PROGRAM / "PROGRAM_STATE.json").read_text(encoding="utf-8"))
    rows = {}
    for name, spec in st["shared_contracts"].items():
        p = REPO / spec["path"]
        rows[name] = {
            "path": spec["path"],
            "recorded_sha256": spec["sha256"],
            "measured_sha256": sha(p) if p.exists() else None,
            "match": bool(p.exists() and sha(p) == spec["sha256"]),
        }
    reg = REPO / st["registry"]["path"]
    n = sum(1 for line in reg.read_text(encoding="utf-8").splitlines() if line.strip())
    return {
        "shared_contracts": rows,
        "all_match": all(r["match"] for r in rows.values()),
        "registry_n_records_recorded": st["registry"]["n_records"],
        "registry_n_records_measured": n,
        "registry_count_matches": n == st["registry"]["n_records"],
    }


def main() -> int:
    build = run(HERE / "build_fixture_history.py")
    tests = run(HERE / "TESTS.py")

    led = HERE / "fixtures" / ph.LEDGER_NAME
    report = ph.verify_ledger(led)
    recs = ph.read_records(led)

    ev = {
        "schema": "u12_prediction_history_evidence/1",
        "node": "U12_PREDICTION_HISTORY",
        "lane": "product",
        "epistemic_status": ("PRODUCT SCAFFOLD built against fixtures. Carries no scientific "
                             "claim and must not imply a model has been promoted."),
        "promotion_claim": "none. No model is promoted, proposed for promotion, or evaluated here.",
        "runs": {"build_fixture_history": build, "TESTS": tests},
        "fixture_ledger": {
            "path": led.relative_to(REPO).as_posix(),
            "sha256": sha(led),
            "n_records": report["n_records"],
            "n_keys": report["n_keys"],
            "verify_ok": report["ok"],
            "findings": report["findings"],
            "n_ok_records": sum(1 for r in recs if r["status"] == ph.STATUS_OK),
            "n_withheld_records": sum(1 for r in recs if r["status"] == ph.STATUS_WITHHELD),
            "n_superseded": len(ph.view_superseded(recs)),
            "model_versions": sorted({r["model"]["model_version"] for r in recs}),
            "promotion_status_values": sorted({r["model"]["promotion_status"] for r in recs}),
            "blocking_codes_present": sorted({w["code"] for r in recs for w in r["warnings"]
                                              if w["severity"] == ph.SEVERITY_BLOCKING}),
        },
        "own_file_sha256": {p.name: sha(p) for p in sorted(HERE.glob("*.py"))},
        "program_state_cross_check": state_hash_check(),
    }
    (HERE / "EVIDENCE_measured.json").write_text(
        json.dumps(ev, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"tests": tests, "build_returncode": build["returncode"],
                      "verify_ok": report["ok"]}, indent=2))
    return 0 if (tests["returncode"] == 0 and build["returncode"] == 0 and report["ok"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
