"""Pull the BASELINE_CONSTRUCTION + strong-signal lines for the exploration screens only,
so they can be read one screen at a time."""
import json, io, os, re, sys

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")

d = json.load(io.open(os.path.join(OUT, "scan_hits.json"), encoding="utf-8"))

# the operations that actually determine a time window
STRONG = re.compile(
    r"(?i)(leave.?one|loo|_loo\b|season_(sum|tot|mean|rate|poss|tov)|"
    r"transform\s*\(\s*['\"](mean|sum)|groupby\(\[?[^)]*season[^)]*\)|"
    r"\.sum\(\)\s*-|searchsorted|shift\(1\)|expanding\(|rolling\(|"
    r"cumsum|as_?of|pregame|prior_|before)")

sel = [h for h in d["hits"]
       if h["file"].startswith("experiments\\exploration")
       and ("BASELINE_CONSTRUCTION" in h["kind"] or STRONG.search(h["text"]))]

from collections import defaultdict
by = defaultdict(list)
for h in sel:
    screen = "\\".join(h["file"].split("\\")[:3])
    by[screen].append(h)

with io.open(os.path.join(OUT, "triage_exploration.txt"), "w", encoding="utf-8") as f:
    for s in sorted(by):
        f.write("\n#### %s  (%d lines)\n" % (s, len(by[s])))
        cur = None
        for h in sorted(by[s], key=lambda x: (x["file"], x["line"])):
            if h["file"] != cur:
                cur = h["file"]
                f.write("  -- %s\n" % cur)
            f.write("     %5d | %s\n" % (h["line"], h["text"]))
print("screens:", len(by), "lines:", len(sel))
for s in sorted(by):
    print("  %-60s %d" % (s, len(by[s])))
