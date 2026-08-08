import json, os, re, collections, io

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "MANIFEST_REMEDIATION")
SKIP = ("MANIFEST_REMEDIATION", "E1_I0004_fga_forecast", "MEASURE_F1_m13_fitpool", "_screen_kit",
        "__pycache__", ".git", "node_modules")

rows = json.load(open(os.path.join(OUT, "inventory_shared68.json"), encoding="utf-8"))
targets = {}
for r in rows:
    base = os.path.basename(r["artifact"])
    targets.setdefault(base, []).append(r["artifact"])

pyfiles = []
for dp, dns, fns in os.walk(ROOT):
    dns[:] = [d for d in dns if d not in SKIP]
    for f in fns:
        if f.endswith(".py"):
            pyfiles.append(os.path.join(dp, f))
print("scanning %d py files" % len(pyfiles))

WRITE = re.compile(r"to_parquet|to_csv|write_parquet|write_csv|savetxt|\.dump\(|pq\.write_table|open\(", re.I)

hits = collections.defaultdict(list)   # basename -> [(file, lineno, line, is_write)]
for pf in pyfiles:
    try:
        txt = io.open(pf, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    lines = txt.split("\n")
    for i, ln in enumerate(lines, 1):
        for base in targets:
            if base in ln:
                # is this a write? check this line and next 4 lines
                ctx = "\n".join(lines[max(0, i - 4):i + 4])
                is_w = bool(WRITE.search(ctx))
                hits[base].append((os.path.relpath(pf, ROOT), i, ln.strip()[:200], is_w))

res = {}
for base, hl in hits.items():
    res[base] = [{"file": f, "line": n, "text": t, "write_context": w} for f, n, t, w in hl]
json.dump(res, open(os.path.join(OUT, "producer_candidates.json"), "w", encoding="utf-8"), indent=1)

for base in sorted(targets):
    hl = hits.get(base, [])
    w = [h for h in hl if h[3]]
    print("\n=== %s  (%d refs, %d write-ctx)" % (base, len(hl), len(w)))
    seen = set()
    for f, n, t, iw in w[:14]:
        if f in seen:
            continue
        seen.add(f)
        print("   W %s:%d  %s" % (f, n, t[:140]))
    if not w:
        for f, n, t, iw in hl[:6]:
            print("   . %s:%d  %s" % (f, n, t[:140]))
