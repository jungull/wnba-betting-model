"""STEP 2 scan - find every candidate baseline/control/reference construction and the
time-window operators near it, with file path + line number + the raw line.

Deliberately dumb and exhaustive: we surface candidates, then a human (me) reads the
construction. No classification happens here.
"""
import json, os, re, io, sys

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, "experiments", "exploration", "AUDIT_baseline_provenance")

EXCLUDED = [
    r"experiments\exploration\E1_I0013_tempo_redundancy",
    r"experiments\exploration\E1_I0004_shot_selection",
    r"experiments\exploration\E0_I0014_residual_heterogeneity",
    r"experiments\exploration\AUDIT_baseline_provenance",
]

SCAN_DIRS = [r"experiments\exploration", r"experiments\player_program",
             r"experiments\market_program"]
ROOT_FILES = ["conditional_edge.py", "daily_forecast.py", "pocket_mining.py",
              "rebaseline_screen.py", "crossseason_screen.py", "minutes_baselines.py",
              "volume_heterogeneity.py", "feature_lab.py", "interactions_lab.py",
              "bottomup_3pt.py", "joint_differential.py", "matchup_overlay.py",
              "prob_edge_ablation.py", "props_edge.py", "calibrated_prob_edge.py",
              "arm_incumbent.py", "clv_transfer.py", "oracle_bracket.py",
              "dist_margin_cover.py", "asof_invariant.py", "bios_screen.py",
              "minutes_twostage.py", "totals_head.py", "totals_online.py"]

# names that in this program have been observed to lie
BASELINE_NAME = re.compile(
    r"(?i)\b(baseline|base_line|control|reference|ref_model|tendency|prior|expected|"
    r"pregame|pre_game|loo|leave_one|leave-one|allowance|null_model|naive|benchmark|"
    r"_exp\b|expectation|season_rate|season_mean|career)\w*")

WINDOW_OP = re.compile(
    r"(searchsorted|shift\s*\(|expanding\s*\(|rolling\s*\(|cumsum|cumcount|cumprod|"
    r"transform\s*\(\s*['\"](mean|sum|count|size|median)|groupby|"
    r"\.sum\s*\(\s*\)\s*-|\.mean\s*\(\s*\)|side\s*=\s*['\"](left|right)|"
    r"< *date|<= *date|game_date *<|date *<|before|as_?of|asof)")

INCREMENT = re.compile(
    r"(?i)(d_?r2|delta_?r2|dr2|delta_?mae|d_?mae|improvement|uplift|gain_over|"
    r"vs_baseline|over_baseline|headline|verdict|gate)")

CODE_EXT = {".py"}
DOC_EXT = {".md", ".json", ".txt"}


def rel(p):
    return os.path.relpath(p, ROOT)


def is_excluded(r):
    for e in EXCLUDED:
        if r == e or r.startswith(e + os.sep):
            return True
    return False


files = []
for sd in SCAN_DIRS:
    base = os.path.join(ROOT, sd)
    if not os.path.isdir(base):
        continue
    for dp, dns, fns in os.walk(base):
        dns[:] = [d for d in dns if d != "__pycache__"]
        if is_excluded(rel(dp)):
            dns[:] = []
            continue
        for fn in fns:
            fp = os.path.join(dp, fn)
            if is_excluded(rel(fp)):
                continue
            if os.path.splitext(fn)[1].lower() in CODE_EXT:
                files.append(fp)
for fn in ROOT_FILES:
    fp = os.path.join(ROOT, fn)
    if os.path.exists(fp):
        files.append(fp)

hits = []
stats = {"files_scanned": 0, "files_with_hits": 0}
for fp in files:
    stats["files_scanned"] += 1
    try:
        lines = io.open(fp, "r", encoding="utf-8", errors="replace").read().split("\n")
    except Exception as e:
        hits.append({"file": rel(fp), "line": 0, "kind": "READ_ERROR", "text": str(e)})
        continue
    fh = 0
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        nb = bool(BASELINE_NAME.search(s))
        nw = bool(WINDOW_OP.search(s))
        ni = bool(INCREMENT.search(s))
        if not (nb or ni):
            continue
        # keep assignment/construction lines and increment lines
        kind = []
        if nb and nw:
            kind.append("BASELINE_CONSTRUCTION")
        elif nb and ("=" in s or "def " in s or "return" in s):
            kind.append("BASELINE_NAME")
        if ni:
            kind.append("INCREMENT")
        if not kind:
            continue
        hits.append({"file": rel(fp), "line": i, "kind": "+".join(kind),
                     "text": s[:400]})
        fh += 1
    if fh:
        stats["files_with_hits"] += 1

with io.open(os.path.join(OUT, "scan_hits.json"), "w", encoding="utf-8") as f:
    json.dump({"stats": stats, "hits": hits}, f, indent=1)

# summary by file for triage
from collections import Counter, defaultdict
byfile = defaultdict(lambda: Counter())
for h in hits:
    byfile[h["file"]][h["kind"].split("+")[0]] += 1
print("files scanned:", stats["files_scanned"], "with hits:", stats["files_with_hits"],
      "total hits:", len(hits))
print()
rows = sorted(byfile.items(), key=lambda kv: -sum(kv[1].values()))
for f, c in rows:
    print("%4d  %s  %s" % (sum(c.values()), f, dict(c)))
