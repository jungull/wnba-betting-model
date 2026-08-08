"""Constraint 3: MANIFEST CHECK.

For every pre-built artifact consumed by a screen, find the sibling <artifact>.manifest.json
and record asof_granularity. Per GRAPH_POLICY 13.2.2:
  asof_granularity == "artifact" -> whole file bounded by its LATEST input; a 2021 row may
                                    embed 2026 information; FILTERING DOES NOT HELP.
  asof_granularity == "row"      -> each row bounded by its own date; filtering IS sufficient.
No manifest at all -> the check CANNOT BE PERFORMED. Flag explicitly.

We test COLUMN VALUES / manifest fields, never a byte-scan for season strings.
"""
import json, io, os, re
from collections import defaultdict

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")

EXCLUDED = [r"experiments\exploration\E1_I0013_tempo_redundancy",
            r"experiments\exploration\E1_I0004_shot_selection",
            r"experiments\exploration\E0_I0014_residual_heterogeneity",
            r"experiments\exploration\AUDIT_baseline_provenance"]
SCAN = [r"experiments\exploration", r"experiments\player_program", r"experiments\market_program"]

# capture read_parquet / read_csv / np.load targets
READ = re.compile(r"""(?:read_parquet|read_csv|read_json|np\.load|load_parquet)\s*\(\s*([^)]{0,300})""")
PATHLIKE = re.compile(r"""["']([^"'\n]*\.(?:parquet|csv|npz|npy|json))["']""")
VARPATH = re.compile(r"""(\w+)\s*\+\s*r?["'](\\?[^"'\n]*\.(?:parquet|csv|npz|npy|json))["']""")


def rel(p):
    return os.path.relpath(p, ROOT)


def excl(r):
    return any(r == e or r.startswith(e + os.sep) for e in EXCLUDED)


consumers = defaultdict(set)   # artifact-ish string -> set of consuming files
files = []
for sd in SCAN:
    base = os.path.join(ROOT, sd)
    if not os.path.isdir(base):
        continue
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d != "__pycache__"]
        if excl(rel(dp)):
            dns[:] = []
            continue
        for fn in fns:
            if fn.endswith(".py"):
                files.append(os.path.join(dp, fn))
for fn in os.listdir(ROOT):
    if fn.endswith(".py"):
        files.append(os.path.join(ROOT, fn))

for fp in files:
    try:
        src = io.open(fp, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    for m in READ.finditer(src):
        arg = m.group(1)
        for pm in PATHLIKE.finditer(arg):
            consumers[pm.group(1)].add(rel(fp))
        for vm in VARPATH.finditer(arg):
            consumers[vm.group(2)].add(rel(fp))

# resolve each referenced artifact name to a real file on disk (by basename) anywhere in repo
disk = defaultdict(list)
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if d not in ("__pycache__", ".git")]
    for fn in fns:
        if fn.lower().endswith((".parquet", ".csv", ".npz", ".npy")):
            disk[fn.lower()].append(os.path.join(dp, fn))

rows = []
for ref, cons in sorted(consumers.items()):
    bn = os.path.basename(ref.replace("/", "\\")).lower()
    matches = disk.get(bn, [])
    if not matches:
        rows.append({"referenced_as": ref, "resolved": None, "manifest": "UNRESOLVED_ON_DISK",
                     "asof_granularity": None, "consumers": sorted(cons)})
        continue
    for mfp in matches:
        # skip artifacts produced inside a screen dir by that same screen (intermediates)
        man = mfp + ".manifest.json"
        alt = os.path.splitext(mfp)[0] + ".manifest.json"
        manp = man if os.path.exists(man) else (alt if os.path.exists(alt) else None)
        gran, note = None, None
        if manp:
            try:
                mj = json.load(io.open(manp, encoding="utf-8"))
                gran = mj.get("asof_granularity") or mj.get("asofGranularity")
                if gran is None:
                    for k in ("granularity", "asof"):
                        if k in mj:
                            gran = mj[k]
                            break
                note = {k: mj.get(k) for k in ("asof", "asof_date", "inputs", "built_at",
                                               "max_input_date", "seasons") if k in mj}
            except Exception as e:
                gran, note = "MANIFEST_UNPARSEABLE", str(e)
        rows.append({"referenced_as": ref, "resolved": rel(mfp),
                     "manifest": rel(manp) if manp else "NO_SIBLING_MANIFEST",
                     "asof_granularity": gran, "manifest_note": note,
                     "consumers": sorted(cons)})

missing = [r for r in rows if r["manifest"] == "NO_SIBLING_MANIFEST"]
artifact_gran = [r for r in rows if r["asof_granularity"] == "artifact"]
row_gran = [r for r in rows if r["asof_granularity"] == "row"]
unresolved = [r for r in rows if r["manifest"] == "UNRESOLVED_ON_DISK"]

with io.open(os.path.join(OUT, "MISSING_MANIFESTS.json"), "w", encoding="utf-8") as f:
    json.dump({
        "policy": ("GRAPH_POLICY 13.2.2: asof_granularity='artifact' means the file is bounded "
                   "by its LATEST input, so a 2021 row may embed 2026 information and filtering "
                   "by season DOES NOT HELP. 'row' means each row is bounded by its own date and "
                   "filtering IS sufficient. No manifest = the check cannot be performed."),
        "method": "manifest fields read as JSON; NO byte/regex scan for season strings was used.",
        "counts": {"referenced_artifacts": len(rows), "no_sibling_manifest": len(missing),
                   "asof_granularity_artifact": len(artifact_gran),
                   "asof_granularity_row": len(row_gran),
                   "unresolved_on_disk": len(unresolved)},
        "UNVERIFIABLE_no_manifest": missing,
        "UNUSABLE_at_E0_E1_artifact_granular": artifact_gran,
        "OK_row_granular": row_gran,
        "unresolved_references": unresolved,
    }, f, indent=1)

print("referenced artifacts resolved:", len(rows))
print("  NO sibling manifest      :", len(missing))
print("  asof_granularity=artifact:", len(artifact_gran))
print("  asof_granularity=row     :", len(row_gran))
print("  unresolved on disk       :", len(unresolved))
print("\n--- artifact-granular (UNUSABLE at E0/E1, filtering does not help) ---")
for r in artifact_gran:
    print(" ", r["resolved"], "| consumers:", len(r["consumers"]))
print("\n--- no sibling manifest (check CANNOT be performed) ---")
seen = set()
for r in missing:
    if r["resolved"] in seen:
        continue
    seen.add(r["resolved"])
    print(" ", r["resolved"], "| consumers:", len(r["consumers"]))
