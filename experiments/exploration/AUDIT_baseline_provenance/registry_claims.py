"""Extract every registered experiment carrying a headline increment from registry.jsonl."""
import json, io, os, re

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")
REG = os.path.join(ROOT, "experiments", "registry.jsonl")

recs = []
for i, ln in enumerate(io.open(REG, encoding="utf-8"), 1):
    ln = ln.strip()
    if not ln:
        continue
    try:
        recs.append((i, json.loads(ln)))
    except Exception as e:
        recs.append((i, {"_PARSE_ERROR": str(e), "_raw": ln[:200]}))

print("records:", len(recs))
keys = set()
for _, r in recs:
    keys |= set(r.keys())
print("top-level keys:", sorted(keys))
print()

INC = re.compile(r"(?i)(d_?r2|delta|improve|uplift|increment|baseline|gain|headline)")


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, path + "." + str(k))
    elif isinstance(o, list):
        for j, v in enumerate(o):
            yield from walk(v, path + "[%d]" % j)
    else:
        yield path, o


summ = []
for ln, r in recs:
    eid = r.get("experiment_id") or r.get("id") or r.get("screen") or r.get("node_id")
    inc = []
    for p, v in walk(r):
        if INC.search(p) and isinstance(v, (int, float)) and not isinstance(v, bool):
            inc.append((p, v))
        elif INC.search(p) and isinstance(v, str) and len(v) < 200:
            inc.append((p, v))
    summ.append({"line": ln, "id": eid, "status": r.get("status"),
                 "path": r.get("path") or r.get("dir") or r.get("location"),
                 "increment_fields": inc})

with io.open(os.path.join(OUT, "registry_claims.json"), "w", encoding="utf-8") as f:
    json.dump(summ, f, indent=1)

for s in summ:
    if s["increment_fields"]:
        print("L%-3d %-38s status=%-12s path=%s" % (s["line"], str(s["id"])[:38],
                                                    str(s["status"])[:12], s["path"]))
        for p, v in s["increment_fields"][:14]:
            print("        %-58s = %s" % (p[:58], str(v)[:110]))
