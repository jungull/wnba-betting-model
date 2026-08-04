"""
U13_MONITORING_INTERFACE -- measurements against the repository, for REPORT.md.

PRODUCT SCAFFOLD built against fixtures. Carries no scientific claim and must not imply a model
has been promoted.

Everything this script prints is read from bytes in the worktree at run time. It writes
REPO_FACTS.json. Every number quoted in REPORT.md comes from here or from TESTS.py; nothing is
asserted from memory.

Run:  python measure_repo_facts.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.abspath(os.path.join(HERE, "..", ".."))          # experiments/player_program
REPO = os.path.abspath(os.path.join(PROGRAM, "..", ".."))          # worktree root

SOURCE_BINDING = os.path.join(PROGRAM, "data_lane", "D11_LIVE_INFORMATION_CAPTURE",
                              "SOURCE_BINDING.json")
CAPTURE_SCHEMA = os.path.join(PROGRAM, "data_lane", "D11_LIVE_INFORMATION_CAPTURE",
                              "capture_schema.py")
PROJECT_UPDATE = os.path.join(PROGRAM, "PROJECT_UPDATE_2026-08-04.md")
PROGRAM_STATE = os.path.join(PROGRAM, "PROGRAM_STATE.json")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def line_of(path, needle, start=1):
    """1-indexed line number of the first line containing `needle`, or None."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            if i >= start and needle in line:
                return i
    return None


def measure_source_binding():
    with open(SOURCE_BINDING, encoding="utf-8") as fh:
        doc = json.load(fh)
    domains = doc.get("domains", {})
    bound = {k: bool(v.get("bound")) for k, v in domains.items()}
    return {
        "path": "experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/"
                "SOURCE_BINDING.json",
        "sha256": sha256_of(SOURCE_BINDING),
        "n_domains_field": doc.get("n_domains"),
        "n_bound_field": doc.get("n_bound"),
        "n_domains_counted": len(domains),
        "n_bound_counted": sum(1 for v in bound.values() if v),
        "domains": bound,
        "headline_line": line_of(SOURCE_BINDING, '"headline"'),
        "n_bound_line": line_of(SOURCE_BINDING, '"n_bound"'),
        "n_domains_line": line_of(SOURCE_BINDING, '"n_domains"'),
        "headline": doc.get("headline"),
    }


def measure_capture_schema():
    with open(CAPTURE_SCHEMA, encoding="utf-8") as fh:
        text = fh.read()
    lines = text.splitlines()
    domain_line = next((i for i, l in enumerate(lines, 1)
                        if l.startswith("DOMAINS: dict[str, dict] = {")), None)
    lineup_enum_line = next((i for i, l in enumerate(lines, 1)
                             if '"lineup_status": ["PROJECTED", "ANNOUNCED", "CONFIRMED"]' in l),
                            None)
    criteria_line = next((i for i, l in enumerate(lines, 1)
                          if l.startswith("CONTRACT_CRITERIA = [")), None)
    return {
        "path": "experiments/player_program/data_lane/D11_LIVE_INFORMATION_CAPTURE/"
                "capture_schema.py",
        "sha256": sha256_of(CAPTURE_SCHEMA),
        "domains_decl_line": domain_line,
        "lineup_status_enum_line": lineup_enum_line,
        "contract_criteria_line": criteria_line,
    }


def measure_defect_table():
    """The documented capture-defect ids and the lines that carry them."""
    out = []
    with open(PROJECT_UPDATE, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            m = re.match(r"^\|\s*\*\*(D-[a-f])\*\*\s*\|\s*\*\*(.+?)\.?\*\*", line)
            if m:
                out.append({"defect_id": m.group(1), "title": m.group(2).strip(), "line": i})
    return {
        "path": "experiments/player_program/PROJECT_UPDATE_2026-08-04.md",
        "sha256": sha256_of(PROJECT_UPDATE),
        "defects": out,
        "n_defects": len(out),
    }


def measure_rollback_mentions():
    """Is 'rollback' documented anywhere in the program other than this node's own contract?"""
    pattern = re.compile(r"rollback", re.IGNORECASE)
    hits = []
    for root, dirs, files in os.walk(PROGRAM):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        if os.path.abspath(root).startswith(os.path.abspath(HERE)):
            continue                                    # exclude this node's own output
        if "SEALED_RESULTS" in root:
            continue                                    # forbidden input; never opened
        for name in files:
            if not name.lower().endswith((".py", ".md", ".json", ".jsonl", ".txt", ".csv")):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if pattern.search(line):
                            hits.append({
                                "path": os.path.relpath(path, REPO).replace("\\", "/"),
                                "line": i,
                                "text": line.strip()[:160],
                            })
            except OSError:
                continue
    self_referential = [h for h in hits
                        if "/orchestration/" in h["path"] or h["path"].endswith("PROGRAM_GRAPH.json")]
    other = [h for h in hits if h not in self_referential]
    return {
        "pattern": "rollback (case-insensitive)",
        "scanned_root": "experiments/player_program (excluding this node and SEALED_RESULTS)",
        "n_hits": len(hits),
        "n_hits_self_referential": len(self_referential),
        "n_hits_elsewhere": len(other),
        "hits_elsewhere": other,
        "interpretation": (
            "Self-referential hits are this node's own contract in PROGRAM_GRAPH.json, the "
            "generated prompt, the seed script and the generated status/index reports -- i.e. the "
            "graph restating the acceptance criterion. They are not evidence that a rollback "
            "mechanism exists."),
    }


def measure_program_state():
    with open(PROGRAM_STATE, encoding="utf-8") as fh:
        doc = json.load(fh)
    frozen = doc.get("frozen_incumbent", {})
    return {
        "path": "experiments/player_program/PROGRAM_STATE.json",
        "sha256": sha256_of(PROGRAM_STATE),
        "frozen_incumbent_arm": frozen.get("arm"),
        "frozen_incumbent_status": frozen.get("status"),
        "frozen_incumbent_line": line_of(PROGRAM_STATE, '"frozen_incumbent"'),
        "n_canonical_artifact_families": len(doc.get("canonical_artifacts", {})),
        "registry_n_records": (doc.get("registry") or {}).get("n_records"),
    }


def measure_product_lane():
    lane = os.path.join(PROGRAM, "product_lane")
    entries = sorted(os.listdir(lane)) if os.path.isdir(lane) else []
    return {"path": "experiments/player_program/product_lane", "exists": os.path.isdir(lane),
            "entries": entries}


def main():
    facts = {
        "schema": "player_program/u13_repo_facts/1",
        "epistemic_status": ("PRODUCT SCAFFOLD built against fixtures. Carries no scientific "
                             "claim and must not imply a model has been promoted."),
        "generated_by": "experiments/player_program/product_lane/U13_MONITORING_INTERFACE/"
                        "measure_repo_facts.py",
        "worktree": REPO.replace("\\", "/"),
        "source_binding": measure_source_binding(),
        "capture_schema": measure_capture_schema(),
        "defect_table": measure_defect_table(),
        "rollback_mentions": measure_rollback_mentions(),
        "program_state": measure_program_state(),
        "product_lane": measure_product_lane(),
    }
    path = os.path.join(HERE, "REPO_FACTS.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(facts, fh, indent=2)
        fh.write("\n")
    sb = facts["source_binding"]
    print(f"D11 domains: {sb['n_domains_counted']} counted / n_domains={sb['n_domains_field']}; "
          f"bound: {sb['n_bound_counted']} counted / n_bound={sb['n_bound_field']}")
    print(f"documented capture defects: {facts['defect_table']['n_defects']} "
          f"({', '.join(d['defect_id'] for d in facts['defect_table']['defects'])})")
    rb = facts["rollback_mentions"]
    print(f"'rollback' hits in program: {rb['n_hits']} total, "
          f"{rb['n_hits_self_referential']} self-referential, {rb['n_hits_elsewhere']} elsewhere")
    for h in rb["hits_elsewhere"]:
        print(f"  {h['path']}:{h['line']}  {h['text'][:100]}")
    print(f"product_lane entries: {facts['product_lane']['entries']}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
