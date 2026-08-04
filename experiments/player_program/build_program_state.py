#!/usr/bin/env python3
"""build_program_state.py — derive PROGRAM_STATE.json from the repository, not from prose.

A session that starts by reading a hand-maintained status document inherits whatever was true
when someone last remembered to update it. This wave began exactly that way: two handoff
documents disagreed, and the one that was authoritative about integrity work was wrong about
which receipt had drifted and about the evidence behind a ranked conclusion.

So this file is DERIVED. Branch, HEAD and tree state come from git; artifact hashes from the
bytes on disk; the frozen incumbent, wave status and workstream dispositions from the ledger and
audit matrix; shared-contract versions from the source files themselves. The only freehand
content is the stop boundary and the next decision, which are governance statements no artifact
can supply.

FAILS CLOSED. A missing required source, or a state that contradicts itself, raises rather than
emitting a confident-looking file.

Determinism: ``--deterministic`` sets ``generated_at`` to null so two runs over an unchanged
repository produce byte-identical output. Tests use that mode.

Scope of authority. This file is authoritative for PROGRAM AND SCIENTIFIC state. It is **not**
authoritative for live repository state: ``generated_from`` is PROVENANCE, describing the
repository as it stood when the state was generated — necessarily the parent of the commit that
carries the file, since neither that commit's hash nor its tree status exists until after the
file is written. For live branch, HEAD and working-tree status, run this generator or its
``--check`` command against the current repository.

Run::

    python experiments/player_program/build_program_state.py
    python experiments/player_program/build_program_state.py --deterministic --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DW1 = HERE / "discovery_wave_1"
OUT = HERE / "PROGRAM_STATE.json"

SCHEMA = "player_program_state/1"
RESEARCH_CONTRACT_VERSION = "RESEARCH_CONTRACT_V1"

#: shared process contracts whose identity future work must be able to pin
SHARED_CONTRACTS = {
    "feature_gate": "feature_gate.py",
    "comparison_gate": "comparison_gate.py",
    "gate_invocation": "gate_invocation.py",
    "receipt_integrity": "receipt_integrity.py",
}

#: canonical artifacts: (family dir, receipt file, artifact files)
CANONICAL = {
    "projected_player_possessions/1": (
        "projected_exposure_v1", "PROJECTED_EXPOSURE_RECEIPT.json",
        ["projected_player_possessions_v1.parquet", "team_possession_prior_v1.parquet",
         "projected_team_rotations_v1.parquet"]),
    "canonical_player_events/1": (
        "event_contract_v1", "EVENT_NORMALISATION_RECEIPT.json",
        ["canonical_player_events_v1.parquet"]),
    "player_turnover_targets/1": (
        "turnover_targets_v1", "TURNOVER_TARGET_RECEIPT.json",
        ["player_turnover_targets_v1.parquet", "team_turnover_reconciliation_v1.parquet"]),
}

REQUIRED = [
    HERE / "arm_registry.jsonl",
    HERE / "feature_gate.py",
    HERE / "GATE_INVOCATION_CONTRACT.md",
    DW1 / "HYPOTHESIS_LEDGER.json",
    DW1 / "FINAL_AUDIT_MATRIX.json",
    DW1 / "RETROSPECTIVE_GATE_AUDIT.json",
    DW1 / "DISCOVERY_WAVE_1_SUMMARY.md",
    HERE / "turnover_p2_v1" / "P2_SUPERSESSION.json",
]


class ProgramStateFailure(RuntimeError):
    """Raised when the state cannot be derived, or contradicts itself."""


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True)
    if r.returncode != 0:
        raise ProgramStateFailure(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _rel(p: Path) -> str:
    return p.relative_to(HERE.parents[1]).as_posix()


def build(deterministic: bool = False) -> dict:
    missing = [_rel(p) for p in REQUIRED if not p.exists()]
    if missing:
        raise ProgramStateFailure(f"required source(s) missing, refusing to emit: {missing}")

    ledger = json.loads((DW1 / "HYPOTHESIS_LEDGER.json").read_text(encoding="utf-8"))
    matrix = json.loads((DW1 / "FINAL_AUDIT_MATRIX.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "turnover_p2_v1" / "P2_SUPERSESSION.json").read_text(encoding="utf-8"))

    # ---- internal consistency: the ledger and the matrix must agree ------------------------
    lrows = {k.split("_")[0]: v for k, v in ledger["workstreams"].items()}
    mrows = {r["workstream"]: r for r in matrix["rows"]}
    if set(lrows) != set(mrows):
        raise ProgramStateFailure(
            f"ledger and matrix disagree on workstreams: {sorted(set(lrows) ^ set(mrows))}")
    for ws, mr in mrows.items():
        rc = lrows[ws].get("retrospective_classification") or {}
        if rc.get("decision_validity") != mr["decision_validity"]:
            raise ProgramStateFailure(
                f"{ws}: ledger decision_validity {rc.get('decision_validity')!r} != "
                f"matrix {mr['decision_validity']!r}")
    if ledger["frozen_incumbent"] != matrix["frozen_incumbent"]:
        raise ProgramStateFailure("ledger and matrix disagree on the frozen incumbent")

    # ---- git ------------------------------------------------------------------------------
    dirty = [ln for ln in _git("status", "--porcelain").splitlines() if ln.strip()]

    # ---- canonical artifacts --------------------------------------------------------------
    canon = {}
    for aid, (fam, rec, files) in CANONICAL.items():
        d = HERE / fam
        rp = d / rec
        if not rp.exists():
            raise ProgramStateFailure(f"canonical receipt missing: {_rel(rp)}")
        r = json.loads(rp.read_text(encoding="utf-8"))
        arts = {}
        for f in files:
            fp = d / f
            if not fp.exists():
                raise ProgramStateFailure(f"canonical artifact missing: {_rel(fp)}")
            arts[f] = _sha(fp)
        canon[aid] = {
            "family": fam, "receipt": rec, "receipt_schema": r.get("schema"),
            "contract_version": r.get("contract_version"),
            "experiment_id": r.get("experiment_id"),
            "artifact_sha256": arts, "status": "FROZEN — do not alter",
        }

    contracts = {}
    for name, fn in SHARED_CONTRACTS.items():
        p = HERE / fn
        if not p.exists():
            raise ProgramStateFailure(f"shared contract missing: {_rel(p)}")
        contracts[name] = {"path": _rel(p), "sha256": _sha(p),
                           "last_commit": _git("log", "-1", "--format=%h", "--", fn)}

    invalid = [{"id": k, "status": (v.get("status") if isinstance(v, dict) else str(v))}
               for k, v in sorted((p2.get("arms") or p2.get("supersessions") or {}).items())] \
        if isinstance(p2.get("arms") or p2.get("supersessions"), dict) else []
    for ws, mr in sorted(mrows.items()):
        if mr["decision_validity"] in ("invalid", "superseded"):
            invalid.append({"id": ws, "status": mr["decision_validity"],
                            "detail": mr["evidence_status"]})

    state = {
        "schema": SCHEMA,
        "generated_at": None if deterministic else
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generator": _rel(Path(__file__)),
        "derived_not_maintained": (
            "every field below is derived from git, the registries, the ledger, the audit matrix "
            "and the artifact bytes. Do not hand-edit; re-run the generator."),
        "authority": (
            "PROGRAM_STATE.json is AUTHORITATIVE for program and scientific state. It is NOT "
            "authoritative for live repository state. Live branch, HEAD and working-tree status "
            "must be obtained by running build_program_state.py, or its --check command, against "
            "the current repository."),
        "research_contract_version": RESEARCH_CONTRACT_VERSION,
        "generated_from": {
            "_meaning": (
                "PROVENANCE, not current repository state. A committed generated file cannot "
                "record the hash or clean-tree status of the commit that contains it -- neither "
                "exists until after the file is written. These fields describe the repository as "
                "it stood when this state was generated, i.e. the PARENT of the commit carrying "
                "this file. For live state, run the generator."),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "head": _git("rev-parse", "HEAD"),
            "head_short": _git("rev-parse", "--short", "HEAD"),
            "working_tree_state": "clean" if not dirty else "dirty",
            "dirty_paths": dirty,
            "worktree": _rel(HERE.parents[1]),
            "authoritative_lineage": ("this worktree, NOT the repository root, which is on a "
                                      "different branch"),
        },
        "frozen_incumbent": dict(ledger["frozen_incumbent"],
                                 status="FROZEN — do not alter or retune"),
        "canonical_artifacts": canon,
        "shared_contracts": contracts,
        "registry": {
            "path": "experiments/player_program/arm_registry.jsonl",
            "n_records": sum(1 for ln in (HERE / "arm_registry.jsonl")
                             .read_text(encoding="utf-8").splitlines() if ln.strip()),
            "append_only": True,
            "single_writer": "coordinator only; agents propose records, never append",
        },
        "execution": {
            "active_task_ids": [],
            "running_workstreams": [],
            "landed_but_unverified": [],
            "accepted_work": [
                {"commit": "75ac7ba", "what": "comparison-parity contract"},
                {"commit": "7d7fc7b", "what": "corrected turnover receipt + integrity check"},
                {"commit": "507f62d", "what": "P2 supersession + gate-invocation contract"},
                {"commit": "c9fc6f7", "what": "integrated hypothesis ledger"},
                {"commit": "afda8c5", "what": "multi-axis wave status"},
                {"commit": "b626d50", "what": "Layer A/B comparison gate"},
                {"commit": "76a15ae", "what": "retrospective two-axis gate audit"},
                {"commit": "88c128a", "what": "receipt full-chain validation"},
                {"commit": "d58a6b2", "what": "validated gate-invocation wrapper"},
                {"commit": "866f3fb", "what": "final audit matrix + two-axis ledger"},
                {"commit": "12f7272", "what": "consolidated discovery-wave summary"},
            ],
        },
        "invalid_or_superseded": invalid,
        "discovery_wave_1": {
            "wave_status": ledger["wave_status"],
            "workstreams": {ws: {"feature_design_integrity": mr["feature_design_integrity"],
                                 "decision_validity": mr["decision_validity"],
                                 "evidence_role": mr["evidence_role"]}
                            for ws, mr in sorted(mrows.items())},
            "gate_governance": matrix["gate_governance_statement"],
            "summary": _rel(DW1 / "DISCOVERY_WAVE_1_SUMMARY.md"),
            "matrix": _rel(DW1 / "FINAL_AUDIT_MATRIX.json"),
            "finalised_as": "DEVELOPMENT EVIDENCE ONLY. No challenger registered.",
        },
        "state_of_play": {
            "discovery_executions": "COMPLETE",
            "integrity_integration": "COMPLETE",
            "experiment_currently_authorized": False,
            "workstream_running": False,
            "turnover_discovery_wave": "FINALISED as development evidence",
            "arm_D": "UNCHANGED",
            "next_substantive_direction": "REQUIRES USER AUTHORIZATION",
        },
        "stop_boundary": {
            "in_force": True,
            "do_not_without_fresh_authorization": [
                "begin a confirmation experiment",
                "promote any discovery arm",
                "alter Arm D or retune P1",
                "alter canonical exposure or the canonical target",
                "begin another event channel (rebounds, assists, blocks, fouls, shots)",
                "feed turnover forecasts into the team model",
                "append new scientific registry records",
                "modify feature_gate.py, comparison_gate.py or the invocation wrapper",
            ],
        },
        "next_decision_requiring_authorization": (
            "No experiment is authorized. The most defensible next substantive step, IF "
            "authorized, is a registered improvement to team_possession_prior/1 — the only "
            "materially addressable team-aggregate error source found (WS8: +0.1033 "
            "[0.0833, 0.1244]). Its honest prize is small: 1.2–2.2% of operational MAE. Any "
            "such task must be issued as a versioned specification under "
            f"{RESEARCH_CONTRACT_VERSION}."),
        "open_methodological_gaps": [
            {"id": "dual_frame_audit", "severity": "A",
             "gap": "designs are not audited before AND after missing-value transformation; the "
                    "invocation layer does NOT close the ws2 pre-gate-imputation class",
             "specified_in": "GATE_INVOCATION_CONTRACT.md §8a", "implemented": False},
            {"id": "validator_lineage", "severity": "B",
             "gap": "validate_turnover_targets.py records the producer hash but not its own; the "
                    "receipt chain is NOT cryptographically closed", "implemented": False},
            {"id": "fresh_execution_unprovable", "severity": "B",
             "gap": "no validator-emitted per-execution identity, so a copied-forward receipt "
                    "cannot be distinguished from an identical rerun", "implemented": False},
            {"id": "nonlinear_dependency", "severity": "C",
             "gap": "the gate detects linear rank deficiency only", "implemented": False},
            {"id": "pipeline_id_asserted", "severity": "C",
             "gap": "comparison_gate cannot prove K0 came from the challenger's code path; "
                    "producer-source digest binding would close it", "implemented": False},
            {"id": "ws6_no_featureless_control", "severity": "B",
             "gap": "ws6 has no K0 of any kind, so its free-intercept confound is uncontrolled",
             "implemented": False},
        ],
    }
    return state


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deterministic", action="store_true",
                    help="null the timestamp so output is byte-stable")
    ap.add_argument("--check", action="store_true",
                    help="do not write; fail if the on-disk file differs (ignoring timestamp)")
    a = ap.parse_args()
    try:
        state = build(deterministic=a.deterministic)
    except ProgramStateFailure as e:
        print(f"FAIL CLOSED: {e}", file=sys.stderr)
        return 2
    txt = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    if a.check:
        if not OUT.exists():
            print("FAIL: PROGRAM_STATE.json does not exist", file=sys.stderr)
            return 1
        cur = json.loads(OUT.read_text(encoding="utf-8"))
        # Compare SUBSTANCE. `generated_at` is volatile by design, and `generated_from` is
        # provenance that is necessarily one commit behind whenever the state file is itself
        # committed -- see generated_from._meaning.
        want, got = dict(state), dict(cur)
        for d in (want, got):
            d.pop("generated_at", None)
            d.pop("generated_from", None)
        if json.dumps(got, indent=2, ensure_ascii=False) != json.dumps(
                want, indent=2, ensure_ascii=False):
            print("FAIL: PROGRAM_STATE.json is substantively stale; re-run the generator",
                  file=sys.stderr)
            return 1
        if cur["generated_from"]["branch"] != state["generated_from"]["branch"]:
            print("FAIL: PROGRAM_STATE.json was generated from a different branch",
                  file=sys.stderr)
            return 1
        print("PROGRAM_STATE.json is substantively current.")
        print(f"  stored provenance : generated_from.head = {cur['generated_from']['head_short']}"
              f" ({cur['generated_from']['working_tree_state']})")
        print(f"  LIVE repository   : HEAD = {state['generated_from']['head_short']}"
              f" ({state['generated_from']['working_tree_state']})")
        return 0
    OUT.write_text(txt, encoding="utf-8")
    r = state["generated_from"]
    print(f"wrote {OUT.name}")
    print(f"  generated_from: branch {r['branch']} @ {r['head_short']} "
          f"({r['working_tree_state']})  [provenance, not live HEAD]")
    print(f"  contract {state['research_contract_version']} · "
          f"authorized={state['state_of_play']['experiment_currently_authorized']} · "
          f"running={state['state_of_play']['workstream_running']}")
    print(f"  open gaps: {len(state['open_methodological_gaps'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
