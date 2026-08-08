import json, os, re, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
ORCH = os.path.join(ROOT, "experiments", "player_program", "orchestration")
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

def norm(p):
    return re.sub(r"[\\/]+", "/", str(p)).lower().lstrip("./")

gs = json.load(open(os.path.join(ORCH, "GRAPH_STATE.json"), encoding="utf-8"))
node_status = {}
for lane, d in gs["by_lane"].items():
    for status, nodes in d.items():
        for n in nodes:
            node_status[n] = (lane, status)

pg = json.load(open(os.path.join(ORCH, "PROGRAM_GRAPH.json"), encoding="utf-8"))

# artifact-path -> set of node ids that name it as an input
art2node = collections.defaultdict(set)
# directory prefix -> node id (owned/write scope)
prefix2node = []
for n in pg["nodes"]:
    nid = n["id"]
    for f in (n.get("input_artifacts") or []) + (n.get("expected_outputs") or []) + (n.get("owned_files") or []):
        art2node[norm(f)].add(nid)
    for p in (n.get("allowed_write_paths") or []) + (n.get("owned_files") or []):
        prefix2node.append((norm(p), nid))

rows = json.load(open(os.path.join(OUT, "inventory_shared68.json"), encoding="utf-8"))

def nodes_for_path(path):
    """node ids implicated by a file path: exact artifact match, path-component id, or write-scope prefix"""
    np_ = norm(path)
    hits = set(art2node.get(np_, set()))
    for part in re.split(r"[\\/]", path):
        if part in node_status:
            hits.add(part)
    for pref, nid in prefix2node:
        if pref and np_.startswith(pref.rstrip("/") + "/"):
            hits.add(nid)
    return hits

STATUS_RANK = {"PASSED": 5, "HALTED": 4, "BLOCKED": 3, "READY": 3, "USER_REQUIRED": 3, "SUPERSEDED": 1}

for r in rows:
    art = r["artifact"]
    direct = nodes_for_path(art)          # node names this artifact directly
    via_consumers = set()
    for c in r["consumers"]:
        via_consumers |= nodes_for_path(c)
    alln = {n: node_status.get(n, ("?", "UNKNOWN")) for n in (direct | via_consumers)}
    r["nodes_naming_artifact"] = sorted(direct)
    r["nodes_via_consumers"] = sorted(via_consumers - direct)
    r["node_statuses"] = {k: list(v) for k, v in alln.items()}
    live = [k for k, v in alln.items() if v[1] in ("PASSED", "HALTED", "BLOCKED", "READY", "USER_REQUIRED")]
    r["live_nodes"] = sorted(live)
    r["passed_nodes"] = sorted(k for k, v in alln.items() if v[1] == "PASSED")
    if r["passed_nodes"]:
        r["liveness"] = "LIVE_PASSED_NODE"
    elif live:
        r["liveness"] = "LIVE_OPEN_NODE"
    else:
        r["liveness"] = "NO_GRAPH_NODE"

json.dump(rows, open(os.path.join(OUT, "inventory_shared68.json"), "w", encoding="utf-8"), indent=1)

print(collections.Counter(r["liveness"] for r in rows))
print()
for r in sorted(rows, key=lambda x: (-{"LIVE_PASSED_NODE": 2, "LIVE_OPEN_NODE": 1}.get(x["liveness"], 0), -x["n_consumers"])):
    print("%-18s cons=%-2d %s" % (r["liveness"], r["n_consumers"], r["artifact"]))
    if r["passed_nodes"]:
        print("      PASSED: " + ", ".join(r["passed_nodes"]))
    other = [k for k in r["live_nodes"] if k not in r["passed_nodes"]]
    if other:
        print("      OTHER : " + ", ".join("%s(%s)" % (k, r["node_statuses"][k][1]) for k in other))
