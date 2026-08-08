import json, os, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
p = os.path.join(ROOT, "experiments", "idea_log.jsonl")
recs = []
for line in open(p, encoding="utf-8"):
    line = line.strip()
    if line:
        recs.append(json.loads(line))
print("n recs:", len(recs))
print("kinds:", collections.Counter(r.get("kind") for r in recs))
keys = collections.Counter()
for r in recs:
    keys.update(r.keys())
print("keys:", keys.most_common())

# per idea id, latest status
byid = collections.defaultdict(list)
for r in recs:
    i = r.get("idea_id") or r.get("id")
    byid[i].append(r)
print("\nIDs:", len(byid))
for i in sorted(byid, key=lambda x: str(x)):
    last = byid[i][-1]
    st = last.get("status") or last.get("verdict") or last.get("kind")
    print("  %-10s n=%-2d  %s | %s" % (i, len(byid[i]), str(st)[:70], str(last.get("title") or last.get("hypothesis") or "")[:80]))
