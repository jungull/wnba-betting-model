import json, os, collections

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
SRC = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance", "MISSING_MANIFESTS.json")
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")

d = json.load(open(SRC, encoding="utf-8"))

cons = collections.defaultdict(set)
refnames = collections.defaultdict(set)
for e in d.get("UNVERIFIABLE_no_manifest", []):
    r = e.get("resolved")
    if r:
        for c in e.get("consumers", []) or []:
            cons[r].add(c)
        refnames[r].add(e.get("referenced_as"))

rows = []
for s in d["shared_or_upstream_no_manifest"]:
    p = s["artifact"]
    c = sorted(set(s.get("consumers") or []) | cons.get(p, set()))
    rows.append({
        "artifact": p,
        "exists": os.path.exists(os.path.join(ROOT, p)),
        "size_mb": round(os.path.getsize(os.path.join(ROOT, p)) / 1e6, 2) if os.path.exists(os.path.join(ROOT, p)) else None,
        "n_consumers": len(c),
        "consumers": c,
        "referenced_as": sorted(x for x in refnames.get(p, set()) if x),
    })

rows.sort(key=lambda r: (-r["n_consumers"], r["artifact"]))
json.dump(rows, open(os.path.join(OUT, "inventory_shared68.json"), "w", encoding="utf-8"), indent=1)

print("N =", len(rows))
for i, r in enumerate(rows, 1):
    print("%2d) cons=%-2d exists=%-5s size=%-8s %s" % (i, r["n_consumers"], r["exists"], r["size_mb"], r["artifact"]))

print("\n--- screen_local_intermediates (24) ---")
for s in d["screen_local_intermediates_no_manifest"]:
    print("   cons=%d  %s" % (len(s.get("consumers") or []), s["artifact"]))

print("\n--- unresolved_references (21) ---")
for s in d["unresolved_references"]:
    print("   %s <- %s" % (s.get("referenced_as"), (s.get("consumers") or [None])[0]))
