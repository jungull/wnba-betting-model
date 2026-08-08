import json, io, os
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")
d = json.load(io.open(os.path.join(OUT, "MISSING_MANIFESTS.json"), encoding="utf-8"))

print("=== asof_granularity = row (manifest present, filtering IS sufficient) ===")
for r in d["OK_row_granular"]:
    print(" ", r["resolved"])
    print("     manifest:", r["manifest"], "| consumers:", len(r["consumers"]))

print("\n=== asof_granularity = artifact (UNUSABLE at E0/E1) ===")
for r in d["UNUSABLE_at_E0_E1_artifact_granular"]:
    print(" ", r["resolved"], "->", r["manifest"])
    print("     note:", r.get("manifest_note"))
    for c in r["consumers"]:
        print("     consumer:", c)

print("\n=== SHARED/UPSTREAM inputs with NO manifest (excludes screen-local intermediates) ===")
def is_local(res, cons):
    """intermediate = produced inside the same screen dir that consumes it"""
    if res is None:
        return False
    dirn = os.path.dirname(res)
    return all(c.startswith(dirn) for c in cons)

seen = set()
for r in d["UNVERIFIABLE_no_manifest"]:
    res = r["resolved"]
    if res in seen:
        continue
    seen.add(res)
    if is_local(res, r["consumers"]):
        continue
    print(" ", res)
    for c in r["consumers"]:
        print("       <-", c)

print("\n=== unresolved references (path built dynamically / not found on disk) ===")
for r in d["unresolved_references"]:
    print(" ", r["referenced_as"], "<-", ", ".join(r["consumers"][:3]))

# also check the two master parquets directly
print("\n=== direct check: data\\masters ===")
md = os.path.join(ROOT, "data", "masters")
if os.path.isdir(md):
    for fn in sorted(os.listdir(md)):
        print("  ", fn)
