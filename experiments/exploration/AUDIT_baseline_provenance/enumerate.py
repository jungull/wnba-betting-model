"""STEP 1 - enumerate everything in scope for the baseline-provenance audit."""
import json, os, sys, io

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")

EXCLUDED = {
    r"experiments\exploration\E1_I0013_tempo_redundancy",
    r"experiments\exploration\E1_I0004_shot_selection",
    r"experiments\exploration\E0_I0014_residual_heterogeneity",
    r"experiments\exploration\AUDIT_baseline_provenance",
}

SCAN_DIRS = [
    r"experiments\exploration",
    r"experiments\player_program",
    r"experiments\market_program",
]

CODE_EXT = {".py", ".ipynb"}
DOC_EXT = {".md", ".json", ".jsonl", ".txt", ".csv"}


def rel(p):
    return os.path.relpath(p, ROOT)


def excluded(relpath):
    for e in EXCLUDED:
        if relpath == e or relpath.startswith(e + os.sep):
            return True
    return False


inv = {"screens": {}, "root_scripts": [], "skipped": [], "artifacts": []}

for sd in SCAN_DIRS:
    base = os.path.join(ROOT, sd)
    if not os.path.isdir(base):
        inv["skipped"].append({"path": sd, "reason": "directory does not exist"})
        continue
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        r = rel(full)
        if not os.path.isdir(full):
            # loose files at the top of the scan dir
            inv["screens"].setdefault(sd, {}).setdefault("_loose_files", []).append(r)
            continue
        if excluded(r):
            inv["skipped"].append({"path": r, "reason": "concurrently-running agent dir (off limits) or this audit dir"})
            continue
        files = []
        for dp, dns, fns in os.walk(full):
            dns[:] = [d for d in dns if d != "__pycache__"]
            for fn in fns:
                fp = os.path.join(dp, fn)
                ext = os.path.splitext(fn)[1].lower()
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    sz = -1
                files.append({"path": rel(fp), "ext": ext, "size": sz})
        inv["screens"][r] = {"files": files,
                             "n_py": sum(1 for f in files if f["ext"] == ".py"),
                             "n_files": len(files)}

# root scripts named in the brief plus anything at root that looks analytical
NAMED_ROOT = ["conditional_edge.py", "daily_forecast.py", "pocket_mining.py"]
for fn in NAMED_ROOT:
    fp = os.path.join(ROOT, fn)
    inv["root_scripts"].append({"path": fn, "exists": os.path.exists(fp)})

for fn in sorted(os.listdir(ROOT)):
    fp = os.path.join(ROOT, fn)
    if os.path.isfile(fp) and fn.endswith(".py"):
        if fn not in NAMED_ROOT:
            inv["root_scripts"].append({"path": fn, "exists": True, "note": "root-level python"})

with io.open(os.path.join(OUT, "inventory.json"), "w", encoding="utf-8") as f:
    json.dump(inv, f, indent=1)

print("screens enumerated:", len(inv["screens"]))
for k in sorted(inv["screens"]):
    v = inv["screens"][k]
    if isinstance(v, dict) and "n_files" in v:
        print("  %-70s files=%3d py=%2d" % (k, v["n_files"], v["n_py"]))
print("skipped:", len(inv["skipped"]))
for s in inv["skipped"]:
    print("  SKIP", s["path"], "|", s["reason"])
print("root scripts:", len(inv["root_scripts"]))
