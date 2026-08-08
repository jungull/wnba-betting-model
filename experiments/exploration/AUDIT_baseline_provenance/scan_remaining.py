"""Gap-close: the brief's minimum sweep named exploration / player_program / market_program /
registry / root scripts / coherence_study. That leaves ~50 other experiments\* directories
unscanned. Scan them too, so coverage can be stated honestly rather than left silent.

Reports, per directory: whether it contains code, and whether that code contains a
FULL-SEASON aggregation (the trap's signature) or an artifact-granular consumption.
"""
import io, json, os, re
from collections import defaultdict

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")
EXPB = os.path.join(ROOT, "experiments")
ALREADY = {"exploration", "player_program", "market_program"}

# the trap's actual signature: a season-level aggregate, or a LOO subtraction
TRAP = re.compile(
    r"(?i)(leave.?one|_loo\b|loo_|\bloo\b|"
    r"groupby\(\s*\[?[^)\]]*['\"]season['\"][^)\]]*\]?\s*\)[^\n]{0,80}(transform|\.agg|\.sum|\.mean)|"
    r"season_(sum|tot|total|mean|rate|att|mk|poss|tov|minutes)|"
    r"transform\(\s*['\"](mean|sum)['\"]\s*\))")
GUARD = re.compile(r"(searchsorted|shift\(1\)|expanding\(|cumsum|<\s*date|<\s*cutoff|"
                   r"game_date\s*<|season\s*<|allow_exact_matches\s*=\s*False)")
ARTI = re.compile(r"(predictions_v2\.csv|rapm_v0\.csv)")
INCR = re.compile(r"(?i)(pooled_improvement|improvement|delta|dR2|d_r2|mae_diff|vs_incumbent)")

rows = []
for name in sorted(os.listdir(EXPB)):
    p = os.path.join(EXPB, name)
    if not os.path.isdir(p) or name in ALREADY:
        continue
    pys = []
    for dp, dns, fns in os.walk(p):
        dns[:] = [d for d in dns if d != "__pycache__"]
        pys += [os.path.join(dp, f) for f in fns if f.endswith(".py")]
    if not pys:
        rows.append({"dir": name, "n_py": 0, "verdict": "NO CODE (artifact/report dir only)"})
        continue
    trap, guard, arti, incr, hits = 0, 0, 0, 0, []
    for fp in pys:
        try:
            src = io.open(fp, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for i, ln in enumerate(src.split("\n"), 1):
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if TRAP.search(s):
                trap += 1
                if len(hits) < 6:
                    hits.append("%s:%d | %s" % (os.path.relpath(fp, ROOT), i, s[:150]))
            if GUARD.search(s):
                guard += 1
            if ARTI.search(s):
                arti += 1
                hits.append("ARTIFACT-GRANULAR INPUT >> %s:%d | %s"
                            % (os.path.relpath(fp, ROOT), i, s[:150]))
            if INCR.search(s):
                incr += 1
    rows.append({"dir": name, "n_py": len(pys), "trap_signature_lines": trap,
                 "guard_lines": guard, "artifact_granular_reads": arti,
                 "increment_lines": incr, "sample_hits": hits})

with io.open(os.path.join(OUT, "scan_remaining.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=1)

print("%-34s %5s %6s %6s %6s %6s" % ("dir", "py", "trap", "guard", "artif", "incr"))
for r in rows:
    if r["n_py"] == 0:
        print("%-34s   --  (no code)" % r["dir"])
        continue
    print("%-34s %5d %6d %6d %6d %6d" % (r["dir"], r["n_py"], r["trap_signature_lines"],
                                         r["guard_lines"], r["artifact_granular_reads"],
                                         r["increment_lines"]))
print("\n--- directories that read an artifact-granular input AND publish an increment ---")
for r in rows:
    if r.get("artifact_granular_reads") and r.get("increment_lines"):
        print("\n##", r["dir"])
        for h in r["sample_hits"]:
            if h.startswith("ARTIFACT"):
                print("   ", h)
