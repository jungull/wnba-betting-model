import json, os, re, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
ORCH = os.path.join(ROOT, "experiments", "player_program", "orchestration")
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

gs = json.load(open(os.path.join(ORCH, "GRAPH_STATE.json"), encoding="utf-8"))
node_status = {}
for lane, d in gs["by_lane"].items():
    for status, nodes in d.items():
        for n in nodes:
            node_status[n] = (lane, status)

print("n nodes with status:", len(node_status))
print("status counts:", collections.Counter(s for _, s in node_status.values()))

rows = json.load(open(os.path.join(OUT, "inventory_shared68.json"), encoding="utf-8"))

# map a consumer path -> node id if any path component matches a node id
def nodes_for(path):
    parts = re.split(r"[\\/]", path)
    hits = []
    for p in parts:
        if p in node_status:
            hits.append(p)
    return hits

for r in rows:
    ns = collections.OrderedDict()
    for c in r["consumers"]:
        for n in nodes_for(c):
            ns[n] = node_status[n]
    r["consumer_nodes"] = {k: list(v) for k, v in ns.items()}
    r["has_passed_node_consumer"] = any(v[1] == "PASSED" for v in ns.values())

json.dump(rows, open(os.path.join(OUT, "inventory_shared68.json"), "w", encoding="utf-8"), indent=1)

print("\nartifacts whose consumers map to a graph node:")
for r in rows:
    if r["consumer_nodes"]:
        print("  %-2d %s" % (r["n_consumers"], r["artifact"]))
        for k, v in r["consumer_nodes"].items():
            print("        -> %s [%s / %s]" % (k, v[0], v[1]))

print("\nartifacts with NO node mapping (%d):" % sum(1 for r in rows if not r["consumer_nodes"]))
for r in rows:
    if not r["consumer_nodes"]:
        print("  %-2d %s" % (r["n_consumers"], r["artifact"]))
