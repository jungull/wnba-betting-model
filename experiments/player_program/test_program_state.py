#!/usr/bin/env python3
"""test_program_state.py — validation for the coordination layer.

Checks that the derived program state is deterministic and truthful, that the research contract
and templates carry their required sections, and — the load-bearing one — that adding this
coordination layer changed NO scientific artifact.

Run::

    python experiments/player_program/test_program_state.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_program_state as bps  # noqa: E402

FAILED: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("  PASS  " if cond else "  FAIL  ") + label)
    if not cond:
        FAILED.append(label)


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=HERE, capture_output=True,
                          text=True).stdout.strip()


# ---------------------------------------------------------------- determinism
def test_generator_is_deterministic() -> None:
    a = json.dumps(bps.build(deterministic=True), indent=2, ensure_ascii=False)
    b = json.dumps(bps.build(deterministic=True), indent=2, ensure_ascii=False)
    check(a == b, "build_program_state is deterministic across two runs")
    check(json.loads(a)["generated_at"] is None,
          "deterministic mode nulls the volatile timestamp")
    live = bps.build(deterministic=False)
    check(live["generated_at"] is not None, "normal mode stamps a timestamp")
    d1, d2 = json.loads(a), dict(live)
    d2["generated_at"] = None
    check(json.dumps(d2, indent=2, ensure_ascii=False) == json.dumps(d1, indent=2,
          ensure_ascii=False),
          "timestamp is the ONLY difference between deterministic and normal output")


# ---------------------------------------------------------------- truthfulness
def test_freshly_built_provenance_agrees_with_git() -> None:
    """A FRESH build's provenance must equal live git. The COMMITTED file's provenance is the
    parent commit by construction, and that is not drift -- see generated_from._meaning."""
    s = bps.build(deterministic=True)
    r = s["generated_from"]
    check(r["branch"] == git("rev-parse", "--abbrev-ref", "HEAD"),
          f"fresh build provenance branch == live git ({r['branch']})")
    check(r["head"] == git("rev-parse", "HEAD"), "fresh build provenance head == live git HEAD")
    dirty = [ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]
    check(r["working_tree_state"] == ("clean" if not dirty else "dirty"),
          f"fresh build working_tree_state == live git ({'clean' if not dirty else 'dirty'})")
    check("repository" not in s,
          "no field named 'repository' — provenance is not mislabelled as current state")
    check("_meaning" in r and "PROVENANCE" in r["_meaning"],
          "generated_from carries its provenance meaning inline")
    check("authority" in s and "NOT" in s["authority"],
          "state declares it is NOT authoritative for live repository state")


def test_state_is_internally_consistent() -> None:
    s = bps.build(deterministic=True)
    check(s["schema"] == bps.SCHEMA, "schema recorded")
    check(s["research_contract_version"] == "RESEARCH_CONTRACT_V1", "contract version recorded")
    sp = s["state_of_play"]
    for k, v in [("discovery_executions", "COMPLETE"), ("integrity_integration", "COMPLETE"),
                 ("experiment_currently_authorized", False), ("workstream_running", False),
                 ("arm_D", "UNCHANGED")]:
        check(sp[k] == v, f"state_of_play.{k} == {v!r}")
    check(sp["next_substantive_direction"] == "REQUIRES USER AUTHORIZATION",
          "next direction requires authorization")
    check(s["execution"]["running_workstreams"] == [], "no workstream running")
    check(s["execution"]["active_task_ids"] == [], "no active task ids")
    check(s["stop_boundary"]["in_force"] is True, "stop boundary in force")
    check(bool(s["next_decision_requiring_authorization"]), "next decision field is populated")
    check(len(s["open_methodological_gaps"]) >= 5, "open gaps enumerated")
    check(any(g["id"] == "dual_frame_audit" and g["implemented"] is False
              for g in s["open_methodological_gaps"]),
          "dual-frame gap recorded as NOT implemented")
    fam = s["canonical_artifacts"]
    check(len(fam) == 3, "three canonical artifact families pinned")
    for aid, blk in fam.items():
        check(all(len(h) == 64 for h in blk["artifact_sha256"].values()),
              f"{aid} artifact hashes are real sha256")


def test_generator_fails_closed(tmp_missing: str = "HYPOTHESIS_LEDGER.json") -> None:
    """Renaming a required source must raise, not emit a confident-looking file."""
    p = bps.DW1 / tmp_missing
    bak = p.with_suffix(p.suffix + ".bak_test")
    p.rename(bak)
    try:
        try:
            bps.build(deterministic=True)
            check(False, "generator FAILS CLOSED when a required source is missing")
        except bps.ProgramStateFailure:
            check(True, "generator FAILS CLOSED when a required source is missing")
    finally:
        bak.rename(p)
    check(p.exists(), "required source restored after the fail-closed test")


# ---------------------------------------------------------------- contract + templates
CONTRACT_SECTIONS = [
    "Phase 0", "Phase 1", "Phase 2", "Severity A", "Severity B", "Severity C",
    "Communication protocol", "Task specification versioning",
]
STATUS_WORDS = ["REQUESTED", "RUNNING", "LANDED", "VERIFIED", "COMMITTED",
                "SCIENTIFICALLY_ACCEPTED", "SUPERSEDED", "INVALID"]


def test_contract_sections_exist() -> None:
    t = (HERE / "RESEARCH_CONTRACT_V1.md").read_text(encoding="utf-8")
    for s in CONTRACT_SECTIONS:
        check(s in t, f"contract contains section {s!r}")
    for w in STATUS_WORDS:
        check(w in t, f"contract defines status {w}")
    check("dual-frame" in t.lower(), "contract preserves the dual-frame limitation")
    check("not yet fully implemented" in t.lower() or "not yet implemented" in t.lower(),
          "contract states the dual-frame limitation is unimplemented")


TASK_CARD_FIELDS = [
    "Task ID", "Specification version", "Research lane", "Branch", "Worktree", "Base commit",
    "Basketball mechanism", "Frozen inputs", "Prediction universe", "Target", "Denominator",
    "Frozen arms", "Matched K0", "Incumbent", "Required preflight", "Primary metric",
    "Sign convention", "Uncertainty method", "Falsifier", "Allowed files", "Prohibited files",
    "Deliverables", "Stop boundary",
]
REPORT_FIELDS = [
    "Task ID", "Specification version", "Status", "Base commit", "Result commit",
    "Working-tree state", "Exact completed scope", "Preflight receipt table",
    "Evaluation universe", "Challenger versus K0", "Challenger versus incumbent",
    "Direct findings versus inference", "Defects and deviations", "Feature-design integrity",
    "Decision validity", "Scientific disposition", "Recommended next action", "Stop confirmation",
]


def test_templates_have_required_headings() -> None:
    card = (HERE / "templates" / "EXPERIMENT_TASK_CARD.md").read_text(encoding="utf-8")
    rep = (HERE / "templates" / "EXPERIMENT_COMPLETION_REPORT.md").read_text(encoding="utf-8")
    miss_c = [f for f in TASK_CARD_FIELDS if f not in card]
    miss_r = [f for f in REPORT_FIELDS if f not in rep]
    check(not miss_c, f"task card carries all {len(TASK_CARD_FIELDS)} required fields"
                      + (f" (missing {miss_c})" if miss_c else ""))
    check(not miss_r, f"completion report carries all {len(REPORT_FIELDS)} required fields"
                      + (f" (missing {miss_r})" if miss_r else ""))
    for w in ("valid_as_published", "diagnostic_only", "invalid", "not_reconstructable"):
        check(w in rep, f"report offers decision-validity value {w}")


# ---------------------------------------------------------------- nothing scientific changed
# Standing scientific invariants, each pinned to the commit that FROZE it — not to a moving
# HEAD. Shared contract CODE (comparison_gate, gate_invocation, receipt_integrity) is
# deliberately absent: it is under authorized development and pinning it here would forbid
# sanctioned work rather than protect a result. What must not move is the gate, the registry's
# append-only history, the canonical bytes, and the finalised wave record.
FROZEN_AT = {
    "42af2cd": ["feature_gate.py"],
    "866f3fb": ["discovery_wave_1/HYPOTHESIS_LEDGER.json",
                "discovery_wave_1/FINAL_AUDIT_MATRIX.json"],
}
SESSION_BASE = "0397fbd"


def test_no_scientific_artifact_changed() -> None:
    for base, paths in FROZEN_AT.items():
        for p in paths:
            d = git("diff", "--name-only", base, "HEAD", "--", f"experiments/player_program/{p}")
            check(d == "", f"{p} identical to {base}")
    dirty = {ln[3:] for ln in git("status", "--porcelain").splitlines() if ln.strip()}
    changed = set(git("diff", "--name-only", SESSION_BASE, "HEAD").splitlines()) | dirty
    parq = [c for c in changed if c.endswith(".parquet")]
    check(not parq, f"no parquet changed since {SESSION_BASE} (found {parq})")
    reg = HERE / "arm_registry.jsonl"
    n = sum(1 for ln in reg.read_text(encoding="utf-8").splitlines() if ln.strip())
    check(n >= 41, f"registry holds >= 41 records, append-only (found {n})")
    old = git("show", f"{SESSION_BASE}:experiments/player_program/arm_registry.jsonl").splitlines()
    new = reg.read_text(encoding="utf-8").splitlines()
    old = [ln for ln in old if ln.strip()]
    new = [ln for ln in new if ln.strip()]
    check(new[:len(old)] == old, "registry prior records byte-identical (append-only preserved)")


def main() -> int:
    print("=" * 78)
    print("coordination layer — validation")
    print("=" * 78)
    for fn in [test_generator_is_deterministic, test_freshly_built_provenance_agrees_with_git,
               test_state_is_internally_consistent, test_generator_fails_closed,
               test_contract_sections_exist, test_templates_have_required_headings,
               test_no_scientific_artifact_changed]:
        print(f"\n--- {fn.__name__} ---")
        fn()
    print("\n" + "=" * 78)
    print(f"{'PASS — all checks green' if not FAILED else 'FAIL: ' + str(FAILED)}")
    print("=" * 78)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
