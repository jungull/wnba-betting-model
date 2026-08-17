"""
E1_I0049_benchmark_constants -- s01
CENSUS SWEEP: locate every occurrence of the programme's benchmark constants
across DECISION_LEDGER.jsonl, every FINDINGS.json under experiments/exploration/,
and every .md/.csv there.

NO NAME-BASED SELECTION of candidates anywhere: constants are matched by literal
numeric token, and the file allowlist is printed and counted.

Writes: raw/_s01_census_hits.json, raw/_s01_summary.json
"""
import json, os, re, sys, hashlib, io

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXPL = os.path.join(ROOT, "experiments", "exploration")
LEDGER = os.path.join(ROOT, "experiments", "player_program", "orchestration", "DECISION_LEDGER.jsonl")
OUT = os.path.join(EXPL, "E1_I0049_benchmark_constants", "raw")
os.makedirs(OUT, exist_ok=True)

# EXPLICIT ALLOWLIST of constants under census. Each entry: (key, list of literal
# string forms to search for). Forms are literal substrings -- no regex classes,
# no name matching.
CONSTANTS = {
    "BEST_LIVE_0.002057":      ["0.002057", "0.00205", "2.057e-03", "2.0570e-03", "2.057e-3"],
    "FLOOR_1CELL_0.00102":     ["0.00102", "1.02e-03", "1.020e-03", "1.02e-3"],
    "FLOOR_132_0.00235":       ["0.00235", "2.35e-03", "2.350e-03", "2.35e-3"],
    "D084_CEILING_0.000129":   ["0.000129", "1.29e-04", "1.290e-04", "1.29e-4"],
    "CONST_0.001127":          ["0.001127", "1.127e-03", "1.1270e-03", "1.127e-3"],
    "N_13879":                 ["13879", "13,879"],
    "N_213":                   ["213 ", " 213", "\"213\"", ":213", "=213"],
    "N_173":                   ["173 ", " 173"],
    "N_5111":                  ["5111", "5,111"],
    "N_13784":                 ["13784", "13,784"],
    "PCT_56.3":                ["56.3"],
}

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()

# ---------- build the file allowlist, print it, assert counts ----------
findings_files = []
md_files = []
csv_files = []
for dirpath, dirnames, filenames in os.walk(EXPL):
    # do not descend into our own screen output (avoid self-reference), or caches
    dirnames[:] = [d for d in dirnames if d not in ("__pycache__",)]
    for fn in filenames:
        p = os.path.join(dirpath, fn)
        rel = os.path.relpath(p, EXPL)
        if rel.startswith("E1_I0049_benchmark_constants"):
            continue
        if fn == "FINDINGS.json":
            findings_files.append(p)
        elif fn.lower().endswith(".md"):
            md_files.append(p)
        elif fn.lower().endswith(".csv"):
            csv_files.append(p)

print("=" * 78)
print("FILE ALLOWLIST (resolved, printed in full per NO-NAME-BASED-SELECTION rule)")
print("=" * 78)
print(f"FINDINGS.json files: {len(findings_files)}")
for p in sorted(findings_files):
    print("   F  " + os.path.relpath(p, EXPL))
print(f"\n.md files: {len(md_files)}")
print(f".csv files: {len(csv_files)}")
print(f"ledger exists: {os.path.exists(LEDGER)}  sha256={sha256(LEDGER)[:16]}")

hits = {k: [] for k in CONSTANTS}

def scan_text(text, source_label, kinds=None):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        for key, forms in CONSTANTS.items():
            if kinds and key not in kinds:
                continue
            for form in forms:
                if form in line:
                    hits[key].append({
                        "source": source_label,
                        "lineno": i + 1,
                        "form": form,
                        "excerpt": line.strip()[:400],
                    })
                    break

# ---------- ledger ----------
ledger_entries = []
with io.open(LEDGER, "r", encoding="utf-8", errors="replace") as f:
    for i, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception as e:
            print(f"  LEDGER PARSE FAIL line {i+1}: {e}")
            continue
        ledger_entries.append((i + 1, obj))
print(f"\nledger entries parsed: {len(ledger_entries)}")

for lineno, obj in ledger_entries:
    did = obj.get("decision_id", "?")
    blob = json.dumps(obj, ensure_ascii=False)
    for key, forms in CONSTANTS.items():
        for form in forms:
            if form in blob:
                # capture the sentence containing it
                for fld, val in obj.items():
                    if isinstance(val, str) and form in val:
                        idx = val.find(form)
                        hits[key].append({
                            "source": f"LEDGER:{did}",
                            "lineno": lineno,
                            "form": form,
                            "field": fld,
                            "excerpt": val[max(0, idx - 300): idx + 300],
                        })
                break

# ---------- FINDINGS.json ----------
for p in sorted(findings_files):
    rel = os.path.relpath(p, EXPL)
    try:
        text = io.open(p, "r", encoding="utf-8", errors="replace").read()
    except Exception as e:
        print(f"  READ FAIL {rel}: {e}")
        continue
    scan_text(text, "FINDINGS:" + rel)

# ---------- .md ----------
for p in sorted(md_files):
    rel = os.path.relpath(p, EXPL)
    text = io.open(p, "r", encoding="utf-8", errors="replace").read()
    scan_text(text, "MD:" + rel)

# ---------- .csv (header + any cell) : only numeric constants ----------
numeric_keys = [k for k in CONSTANTS if not k.startswith("N_") and not k.startswith("PCT")]
for p in sorted(csv_files):
    rel = os.path.relpath(p, EXPL)
    try:
        sz = os.path.getsize(p)
        if sz > 8_000_000:
            continue
        text = io.open(p, "r", encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    scan_text(text, "CSV:" + rel, kinds=set(numeric_keys))

print("\n" + "=" * 78)
print("HIT COUNTS BY CONSTANT")
print("=" * 78)
summary = {}
for key in CONSTANTS:
    srcs = {}
    for h in hits[key]:
        s = h["source"].split(":")[0]
        srcs[s] = srcs.get(s, 0) + 1
    summary[key] = {"total": len(hits[key]), "by_kind": srcs,
                    "distinct_sources": len({h["source"] for h in hits[key]})}
    print(f"{key:28s} total={len(hits[key]):5d}  distinct_sources={summary[key]['distinct_sources']:4d}  {srcs}")

json.dump(hits, open(os.path.join(OUT, "_s01_census_hits.json"), "w"), indent=1)
json.dump({"summary": summary,
           "n_findings_files": len(findings_files),
           "n_md": len(md_files), "n_csv": len(csv_files),
           "n_ledger": len(ledger_entries),
           "ledger_sha256": sha256(LEDGER),
           "findings_files": [os.path.relpath(p, EXPL) for p in sorted(findings_files)]},
          open(os.path.join(OUT, "_s01_summary.json"), "w"), indent=1)
print("\nWROTE raw/_s01_census_hits.json, raw/_s01_summary.json")
