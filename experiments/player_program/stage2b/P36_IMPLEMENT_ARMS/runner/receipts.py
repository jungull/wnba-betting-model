#!/usr/bin/env python3
"""receipts.py -- I13-convention receipts for every runner execution.

Follows the I13_REPRODUCIBILITY_RUNNER manifest conventions (schema repro_run_manifest/2):
code state (git commit + per-source sha256), input-artifact hashes, environment versions, the
full seed manifest, and a canonical manifest digest computed over the record with the digest
field removed.

Git note: P36 implementation sessions do not run git (standing rule 4); tests therefore call
`collect_code_state(run_git=False)`. At P38 execution time the caller passes run_git=True so the
commit is recorded per I13. The receipt states which mode produced it.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from runner_constants import RECEIPT_SCHEMA, RUNNER_VERSION

_RUNNER = Path(__file__).resolve().parent
ROOT = _RUNNER.parents[4]

#: the runner sources every receipt pins (this unit's closure)
RUNNER_SOURCES = ("runner_constants.py", "quasipoisson_irls.py", "seed_manifest.py",
                  "cluster_bootstrap.py", "blinding.py", "guard_harness.py", "k0_flat.py",
                  "receipts.py", "runner_interface.py", "runner.py")


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     default=str).encode()).hexdigest()


def collect_code_state(*, run_git: bool = False) -> dict:
    sources = {}
    for name in RUNNER_SOURCES:
        p = _RUNNER / name
        if p.exists():
            sources[f"stage2b/P36_IMPLEMENT_ARMS/runner/{name}"] = {
                "bytes": p.stat().st_size, "sha256": sha256_file(p)}
    commit, git_available = None, False
    if run_git:
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=30,
                                    capture_output=True, text=True,
                                    check=True).stdout.strip()
            git_available = True
        except Exception:                                     # noqa: BLE001 - recorded, not raised
            git_available = False
    return {"git_invoked": bool(run_git), "git_available": git_available, "commit": commit,
            "commit_note": (None if run_git else
                            "git not invoked: P36 implementation sessions do not run git "
                            "(standing rule 4); P38 records the commit"),
            "runner_version": RUNNER_VERSION, "sources": sources}


def collect_environment() -> dict:
    import numpy
    import pandas
    return {"python": sys.version.split()[0], "implementation": platform.python_implementation(),
            "system": platform.system(), "machine": platform.machine(),
            "packages": {"numpy": numpy.__version__, "pandas": pandas.__version__}}


def hash_inputs(paths: dict) -> dict:
    out = {}
    for name, p in (paths or {}).items():
        p = Path(p)
        out[name] = ({"path": str(p), "bytes": p.stat().st_size, "sha256": sha256_file(p)}
                     if p.exists() else {"path": str(p), "missing": True})
    return out


def build_receipt(*, arm_id: str, element_id: str, enumeration_element: dict,
                  declared_family: str, blinding: dict, guard_pins: dict,
                  guard_records: dict, seed_manifest: dict, folds: list,
                  results: dict, input_paths: dict | None = None,
                  run_git: bool = False) -> dict:
    rec = {"schema": RECEIPT_SCHEMA,
           "recorded_utc": datetime.now(timezone.utc).isoformat(),
           "arm_id": arm_id, "element_id": element_id,
           "enumeration_element": enumeration_element,
           "declared_family": declared_family,
           "code": collect_code_state(run_git=run_git),
           "environment": collect_environment(),
           "inputs": hash_inputs(input_paths or {}),
           "blinding": blinding,
           "guard_pins": guard_pins,
           "guard_records": guard_records,
           "seeds": seed_manifest,
           "folds": folds,
           "results": results}
    body = {k: v for k, v in rec.items() if k != "recorded_utc"}
    rec["manifest_digest"] = canonical_digest(body)
    return rec


def write_receipt(rec: dict, path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return sha256_file(path)
