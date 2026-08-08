import json, os, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
recs = [json.loads(l) for l in open(os.path.join(ROOT, "experiments", "idea_log.jsonl"), encoding="utf-8") if l.strip()]

print("=== HAZARD / POLICY / CORRECTION records ===")
for r in recs:
    if r.get("kind") in ("hazard", "policy", "correction", "method"):
        print(json.dumps(r, indent=1)[:5000])
        print("-" * 60)

print("\n=== per-idea last verdict/status + artifacts ===")
byid = collections.defaultdict(list)
for r in recs:
    if r.get("idea_id"):
        byid[r["idea_id"]].append(r)
for i in sorted(byid):
    print("\n### %s" % i)
    for r in byid[i]:
        print("   kind=%s stage=%s status=%s decision=%s" % (r.get("kind"), r.get("stage"), str(r.get("status"))[:100], str(r.get("decision"))[:60]))
        if r.get("verdict"):
            print("      verdict: %s" % str(r["verdict"])[:300])
        if r.get("artifacts"):
            print("      artifacts: %s" % json.dumps(r["artifacts"])[:400])
