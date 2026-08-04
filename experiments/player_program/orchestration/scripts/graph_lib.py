"""Shared core for the program graph.

Everything in this module is deterministic. GRAPH_STATE.json is a pure function of
PROGRAM_GRAPH.json and GRAPH_EVENTS.jsonl -- no wall-clock, no environment, no ordering
dependence beyond the append order of the event ledger itself. That is what makes
`graphctl.py state --check` a real check rather than a formality.

No third-party imports. The schema in NODE_CONTRACT.schema.json is enforced by
validate_graph.py directly so that the graph never depends on `jsonschema` being installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

# ---------------------------------------------------------------- locations

ORCH = Path(__file__).resolve().parent.parent
REPO = ORCH.parent.parent.parent

GRAPH_PATH = ORCH / "PROGRAM_GRAPH.json"
STATE_PATH = ORCH / "GRAPH_STATE.json"
EVENTS_PATH = ORCH / "GRAPH_EVENTS.jsonl"
DECISIONS_PATH = ORCH / "DECISION_LEDGER.jsonl"
ARTIFACTS_PATH = ORCH / "ARTIFACT_LEDGER.jsonl"
OWNERSHIP_PATH = ORCH / "FILE_OWNERSHIP.json"
SCHEMA_PATH = ORCH / "NODE_CONTRACT.schema.json"
STATUS_REPORT_PATH = ORCH / "reports" / "CURRENT_STATUS.md"

# ---------------------------------------------------------------- statuses

TERMINAL = {"PASSED", "FAILED", "HALTED", "SUPERSEDED"}
DERIVED_ONLY = {"BLOCKED", "READY"}
ALL_STATUSES = {
    "BLOCKED", "READY", "RUNNING", "VERIFYING", "PASSED",
    "FAILED", "HALTED", "SUPERSEDED", "USER_REQUIRED",
}

# event type -> status it forces on its node. Events not listed here are
# informational (they are still recorded, they just do not move the status).
EVENT_STATUS = {
    "agent_launched": "RUNNING",
    "agent_returned": "VERIFYING",
    "validation_started": "VERIFYING",
    "validation_passed": "PASSED",
    "validation_failed": "FAILED",
    "node_passed": "PASSED",
    "node_failed": "FAILED",
    "node_halted": "HALTED",
    "node_superseded": "SUPERSEDED",
    "human_gate_opened": "USER_REQUIRED",
    "node_reset": None,  # clears the event-forced status; used by a retry
}

KNOWN_EVENT_TYPES = set(EVENT_STATUS) | {
    "graph_bootstrapped", "node_created", "dependency_added", "input_frozen",
    "raw_output_frozen", "remediation_node_created", "commit_created",
    "merge_completed", "artifact_hashed", "decision_recorded", "note",
    "reconciliation", "retry_labelled", "replacement_labelled",
}

# ---------------------------------------------------------------- io

def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{i}: malformed JSONL: {exc}")
    return out


def load_graph():
    return _read_json(GRAPH_PATH)


def load_events():
    return _read_jsonl(EVENTS_PATH)


def load_artifacts():
    return _read_jsonl(ARTIFACTS_PATH)


def write_json(path, obj):
    """Deterministic JSON: sorted keys, fixed indent, trailing newline, LF."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def append_jsonl(path, obj):
    """Append-only. Never rewrites an existing line."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_digest_or_none(rel):
    p = REPO / rel
    if p.is_file():
        return sha256_file(p)
    return None


# ---------------------------------------------------------------- git

def git(*args, cwd=None, check=True):
    res = subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
    )
    if check and res.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout.strip()


def repo_facts():
    """Live repository facts. Never cached, never quoted from a generated file."""
    return {
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": git("rev-parse", "HEAD"),
        "head_short": git("rev-parse", "--short", "HEAD"),
        "working_tree_clean": git("status", "--porcelain") == "",
        "dirty_paths": [l[3:] for l in git("status", "--porcelain").splitlines() if l],
        "worktree": str(REPO),
    }


# ---------------------------------------------------------------- indexing

def node_index(graph):
    idx = {}
    for n in graph["nodes"]:
        if n["id"] in idx:
            raise SystemExit(f"duplicate node id: {n['id']}")
        idx[n["id"]] = n
    return idx


def topo_order(graph):
    """Kahn, with ids sorted at each frontier so the order is deterministic.

    Raises on a cycle, naming the nodes still unresolved.
    """
    idx = node_index(graph)
    indeg = {i: 0 for i in idx}
    adj = {i: [] for i in idx}
    for n in graph["nodes"]:
        for d in n["dependencies"]:
            if d not in idx:
                raise SystemExit(f"{n['id']}: dependency on undeclared node {d}")
            adj[d].append(n["id"])
            indeg[n["id"]] += 1
    frontier = sorted(i for i, k in indeg.items() if k == 0)
    order = []
    while frontier:
        cur = frontier.pop(0)
        order.append(cur)
        for nxt in sorted(adj[cur]):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                frontier.append(nxt)
                frontier.sort()
    if len(order) != len(idx):
        stuck = sorted(set(idx) - set(order))
        raise SystemExit(f"dependency cycle among: {', '.join(stuck)}")
    return order


# ---------------------------------------------------------------- derivation

def derive_state(graph, events):
    """Rebuild current status for every node.

    Precedence, strongest first:
      1. an event-forced status (the ledger is the history of what actually happened)
      2. human_gate -> USER_REQUIRED
      3. dependency closure -> READY when every dependency is satisfied, else BLOCKED

    A dependency is satisfied when it is PASSED, or SUPERSEDED by a node that itself
    reached PASSED. SUPERSEDED alone does not satisfy: superseding a node does not
    conjure its evidence.
    """
    idx = node_index(graph)
    order = topo_order(graph)

    forced = {}
    retries = {i: 0 for i in idx}
    supersedes = {}          # superseded_id -> successor_id
    for ev in events:
        nid = ev.get("node")
        if nid is None or nid not in idx:
            continue
        et = ev.get("event")
        if et == "node_reset":
            forced.pop(nid, None)
            retries[nid] += 1
            continue
        if et == "node_superseded" and ev.get("superseded_by"):
            supersedes[nid] = ev["superseded_by"]
        if et in EVENT_STATUS and EVENT_STATUS[et]:
            forced[nid] = EVENT_STATUS[et]

    status = {}

    def satisfied(dep):
        s = status.get(dep)
        if s == "PASSED":
            return True
        if s == "SUPERSEDED":
            succ = supersedes.get(dep)
            return bool(succ) and status.get(succ) == "PASSED"
        return False

    for nid in order:
        node = idx[nid]
        if nid in forced:
            status[nid] = forced[nid]
            continue
        if node.get("human_gate"):
            status[nid] = "USER_REQUIRED"
            continue
        seed = node.get("status")
        if seed in ("SUPERSEDED", "HALTED", "USER_REQUIRED"):
            status[nid] = seed
            continue
        deps = node["dependencies"]
        blocking = [d for d in deps if not satisfied(d)]
        status[nid] = "BLOCKED" if blocking else "READY"

    counts = {s: 0 for s in sorted(ALL_STATUSES)}
    for s in status.values():
        counts[s] += 1

    lanes = {}
    for nid, s in status.items():
        lanes.setdefault(idx[nid]["lane"], {}).setdefault(s, []).append(nid)
    for lane in lanes.values():
        for k in lane:
            lane[k].sort()

    blockers = {}
    for nid in order:
        if status[nid] == "BLOCKED":
            blockers[nid] = sorted(d for d in idx[nid]["dependencies"] if not satisfied(d))

    return {
        "schema": "player_program/orchestration/graph_state/1",
        "derived_not_maintained": (
            "Every field is a pure function of PROGRAM_GRAPH.json and GRAPH_EVENTS.jsonl. "
            "Do not hand-edit: run scripts/graphctl.py state."
        ),
        "graph_sha256": sha256_file(GRAPH_PATH),
        "events_sha256": sha256_file(EVENTS_PATH) if EVENTS_PATH.exists() else None,
        "n_events": len(events),
        "n_nodes": len(idx),
        "counts": counts,
        "status": dict(sorted(status.items())),
        "by_lane": dict(sorted(lanes.items())),
        "blocked_on": dict(sorted(blockers.items())),
        "retry_counts": {k: v for k, v in sorted(retries.items()) if v},
        "topological_order": order,
    }


# ---------------------------------------------------------------- ownership

def _norm(p):
    return p.replace("\\", "/").rstrip("/")


def paths_overlap(a, b):
    """True when two declared write scopes could touch the same bytes.

    Prefix containment in either direction counts: 'x/y' and 'x/y/z' overlap.
    """
    a, b = _norm(a), _norm(b)
    if a == b:
        return True
    return a.startswith(b + "/") or b.startswith(a + "/")


def ownership_conflicts(graph, node_ids):
    """Every pairwise write-scope collision among the given nodes."""
    idx = node_index(graph)
    out = []
    ids = sorted(node_ids)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            na, nb = idx[a], idx[b]
            hits = set()
            for pa in na["allowed_write_paths"] + na["owned_files"]:
                for pb in nb["allowed_write_paths"] + nb["owned_files"]:
                    if paths_overlap(pa, pb):
                        hits.add((_norm(pa), _norm(pb)))
            if hits:
                out.append({"a": a, "b": b, "collisions": sorted(hits)})
    return out


def build_ownership(graph):
    idx = node_index(graph)
    owners = {}
    for nid in sorted(idx):
        for p in idx[nid]["owned_files"]:
            owners.setdefault(_norm(p), []).append(nid)
    scopes = {nid: sorted(_norm(p) for p in idx[nid]["allowed_write_paths"]) for nid in sorted(idx)}
    return {
        "schema": "player_program/orchestration/file_ownership/1",
        "derived_not_maintained": "Generated by scripts/graphctl.py ownership.",
        "graph_sha256": sha256_file(GRAPH_PATH),
        "file_to_nodes": {k: sorted(v) for k, v in sorted(owners.items())},
        "contested_files": {k: sorted(v) for k, v in sorted(owners.items()) if len(v) > 1},
        "write_scopes": scopes,
    }


# ---------------------------------------------------------------- frozen paths

FROZEN_PREFIXES = [
    "experiments/player_program/possessions_v1/",
    "experiments/player_program/possessions_v2/",
    "experiments/player_program/projected_exposure_v1/",
    "experiments/player_program/event_contract_v1/",
    "experiments/player_program/turnover_targets_v1/",
    "experiments/player_program/turnover_p1_v1/",
    "experiments/player_program/turnover_p2_v1/",
    "experiments/player_program/p3_downstream_v1/",
    "experiments/player_program/fits_v1/",
    "experiments/player_program/possession_features_v1/",
    "experiments/player_program/validation_v1/",
    "experiments/player_program/discovery_wave_1/",
]

FROZEN_FILES = [
    "experiments/player_program/feature_gate.py",
    "experiments/player_program/comparison_gate.py",
    "experiments/player_program/gate_invocation.py",
    "experiments/player_program/receipt_integrity.py",
    "experiments/player_program/arm_registry.jsonl",
    "experiments/player_program/registry.jsonl",
    "experiments/player_program/PROGRAM_STATE.json",
    "experiments/player_program/RESEARCH_CONTRACT_V1.md",
    "experiments/player_program/GATE_INVOCATION_CONTRACT.md",
    "experiments/player_program/stage2a/EVIDENCE_PACKET.json",
    "experiments/player_program/stage2a/EVIDENCE_PACKET.sha256",
    "experiments/player_program/stage2a/EVIDENCE_PACKET_V2.json",
    "experiments/player_program/stage2a/CORRECTION_ADDENDUM.json",
    "experiments/player_program/stage2a/GENERATION_ORDER.json",
    "experiments/player_program/stage2a/V2_GENERATION_ORDER.json",
    "experiments/player_program/stage2a/V2_STOP_CONDITION.json",
    "experiments/player_program/stage2a/V2_HYPOTHESES_estimator.md",
    "experiments/player_program/stage2a/V2_HYPOTHESES_basketball.md",
    "experiments/player_program/stage2a/V2_HYPOTHESES_adversarial.md",
    "experiments/player_program/stage2a/SYNTHESIS.md",
    "experiments/player_program/stage2a/PHASE0A_RESOLUTION.md",
    "experiments/player_program/stage2a/PACKET_ADDENDUM_coordinator.md",
    "experiments/player_program/stage2a/HYPOTHESES_coordinator.md",
    "experiments/player_program/stage2a/HYPOTHESES_agent_adversarial.md",
    "experiments/player_program/stage2a/HYPOTHESES_agent_opponent_env.md",
    "experiments/player_program/stage2a/HYPOTHESES_agent_pace_coaching.md",
    "experiments/player_program/stage2a/HYPOTHESES_agent_roster_coldstart.md",
    "experiments/player_program/stage2a/HYPOTHESES_agent_timeseries.md",
]

# Arm D. Matched as substrings against a changed path, because the incumbent's
# bytes live under several families and the guard must fail closed on all of them.
ARM_D_MARKERS = ["D_ewma_shrunk", "arm_incumbent.py"]


def frozen_violations(changed_paths):
    """Return every changed path that touches a frozen artifact."""
    bad = []
    for p in changed_paths:
        q = _norm(p)
        for pre in FROZEN_PREFIXES:
            if q.startswith(pre):
                bad.append({"path": q, "rule": f"frozen directory {pre}"})
                break
        else:
            if q in FROZEN_FILES:
                bad.append({"path": q, "rule": "frozen file"})
                continue
            for m in ARM_D_MARKERS:
                if m in q:
                    bad.append({"path": q, "rule": f"Arm D marker '{m}'"})
                    break
    return bad


# ---------------------------------------------------------------- schema check

_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def validate_node_contract(node):
    """Enforce NODE_CONTRACT.schema.json without a jsonschema dependency."""
    schema = _read_json(SCHEMA_PATH)
    props = schema["properties"]
    required = schema["required"]
    errs = []
    nid = node.get("id", "<no id>")

    for key in required:
        if key not in node:
            errs.append(f"{nid}: missing required field '{key}'")
    for key in node:
        if key not in props:
            errs.append(f"{nid}: unknown field '{key}'")

    def enum_check(field):
        if field in node and node[field] not in props[field]["enum"]:
            errs.append(f"{nid}: {field}={node[field]!r} not in {props[field]['enum']}")

    for f in ("lane", "type", "status", "severity_on_failure", "merge_policy"):
        enum_check(f)

    if "id" in node and not _ID_RE.match(str(node["id"])):
        errs.append(f"{nid}: id does not match {_ID_RE.pattern}")
    for f in ("title", "agent_role", "agent_prompt_path", "epistemic_status"):
        if f in node and not isinstance(node[f], str):
            errs.append(f"{nid}: {f} must be a string")
    if node.get("epistemic_status", "").strip() == "":
        errs.append(f"{nid}: epistemic_status must not be empty")
    for f in ("dependencies", "input_artifacts", "forbidden_inputs", "allowed_read_paths",
              "allowed_write_paths", "owned_files", "allowed_tools", "disallowed_tools",
              "expected_outputs", "validation_commands", "acceptance_criteria",
              "stop_conditions", "on_pass", "on_fail"):
        if f in node and not isinstance(node[f], list):
            errs.append(f"{nid}: {f} must be a list")
    if "input_hashes" in node and not isinstance(node["input_hashes"], dict):
        errs.append(f"{nid}: input_hashes must be an object")
    if "human_gate" in node and not isinstance(node["human_gate"], bool):
        errs.append(f"{nid}: human_gate must be a boolean")
    mr = node.get("max_retries")
    if not isinstance(mr, int) or isinstance(mr, bool) or not (0 <= mr <= 2):
        errs.append(f"{nid}: max_retries must be an integer in [0, 2]")

    # invariants beyond the field schema
    if node.get("human_gate"):
        if node.get("status") != "USER_REQUIRED":
            errs.append(f"{nid}: human_gate=true requires status USER_REQUIRED")
        if node.get("merge_policy") != "never":
            errs.append(f"{nid}: human_gate=true requires merge_policy never")
    if node.get("merge_policy") == "auto":
        if not node.get("validation_commands"):
            errs.append(f"{nid}: merge_policy=auto requires at least one validation_command")
        if not node.get("acceptance_criteria"):
            errs.append(f"{nid}: merge_policy=auto requires at least one acceptance_criterion")
    for p in node.get("allowed_write_paths", []):
        for bad in frozen_violations([_norm(p).rstrip("/") + "/x"]):
            errs.append(f"{nid}: allowed_write_path {p!r} intersects a frozen path ({bad['rule']})")
    return errs
