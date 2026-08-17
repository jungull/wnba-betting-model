"""S05 -- programme-wide composite-candidate sweep, PART 1: population + construction sites.

Population = union of E1_I0036/CENSUS.csv (1,999 cells, 8 screens) and
E1_I0040/AUDIT_TABLE_EXT.csv (2,085 cells, 15 screens).  Asserted, not assumed.

NO NAME-BASED SELECTION.  A candidate's class is decided from its CONSTRUCTION EXPRESSION in
source.  The construction site is located by exact-string match of the candidate name as an
ASSIGNMENT TARGET (df["name"] = ..., df['name'] = ..., name = ..., "name": ..., ("name", ...)),
never by a substring pattern over the name itself.  The resolved list is printed in full and its
count asserted.  Candidates with no located site are UNDETERMINABLE and stay their own category.
"""
import json, os, re, io, tokenize
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXPL))     # worktree root

cen = pd.read_csv(os.path.join(EXPL, "E1_I0036_level_artefact_sweep", "CENSUS.csv"),
                  low_memory=False)
ext = pd.read_csv(os.path.join(EXPL, "E1_I0040_audit_extension", "AUDIT_TABLE_EXT.csv"),
                  low_memory=False)
assert len(cen) == 1999 and cen["screen"].nunique() == 8, (len(cen), cen["screen"].nunique())
assert len(ext) == 2085 and ext["screen"].nunique() == 15, (len(ext), ext["screen"].nunique())

pop = pd.concat([
    cen[["screen", "candidate", "target", "level_recorded"]].rename(
        columns={"level_recorded": "level_recorded"}).assign(source="CENSUS"),
    ext[["screen", "candidate", "target", "candidate_level"]].rename(
        columns={"candidate_level": "level_recorded"}).assign(source="EXT"),
], ignore_index=True)
pairs = pop.drop_duplicates(["screen", "candidate"])[["screen", "candidate"]].reset_index(drop=True)
print("cells in population: %d" % len(pop))
print("screens in population: %d" % pairs["screen"].nunique())
print("(screen, candidate) pairs: %d" % len(pairs))
assert len(pop) == 4084, len(pop)
assert pairs["screen"].nunique() == 23
assert len(pairs) == 540, len(pairs)

# the 15 screens that decide nothing -- asserted from E1_I0040's own coverage file
cov = pd.read_csv(os.path.join(EXPL, "E1_I0040_audit_extension", "COVERAGE_EXT.csv"))
print("\nCOVERAGE_EXT columns:", list(cov.columns))
print(cov.to_string(index=False))

# ------------------------------------------------------------------ source corpus
py = []
for dp, dn, fn in os.walk(ROOT):
    if ".git" in dp or "__pycache__" in dp:
        continue
    for x in fn:
        if x.endswith(".py"):
            py.append(os.path.join(dp, x))
print("\n.py files in worktree: %d" % len(py))

SRC = {}
for p in py:
    try:
        SRC[p] = open(p, "r", encoding="utf-8-sig", errors="replace").read()
    except Exception as e:
        print("  UNREADABLE", p, e)
print("read %d files" % len(SRC))

# screen dir for each screen so we can prefer in-screen definitions
def screen_files(screen):
    d = os.path.join(EXPL, screen)
    return [p for p in SRC if p.startswith(d + os.sep) or os.path.dirname(p) == d]

ASSIGN_PATTERNS = [
    r'\[\s*[\'"]{name}[\'"]\s*\]\s*(?:=|\+=)\s*',          # df["name"] = ...
    r'^\s*{name}\s*=\s*',                                   # name = ...
    r'\.\s*assign\s*\(\s*(?:[^()]*?[,(]\s*)?{name}\s*=',    # .assign(name=...)
    r'[\'"]{name}[\'"]\s*:\s*',                             # {"name": ...}
    r'\(\s*[\'"]{name}[\'"]\s*,\s*',                        # ("name", expr)
]

def find_sites(name, files):
    hits = []
    esc = re.escape(name)
    for p in files:
        txt = SRC[p]
        if name not in txt:
            continue
        lines = txt.splitlines()
        for pat in ASSIGN_PATTERNS:
            rx = re.compile(pat.format(name=esc))
            for i, ln in enumerate(lines):
                if rx.search(ln):
                    hits.append((p, i + 1, ln.rstrip()[:400]))
    # dedupe on (file, line)
    seen = set(); out = []
    for h in hits:
        if (h[0], h[1]) in seen: continue
        seen.add((h[0], h[1])); out.append(h)
    return out

rows = []
for _, r in pairs.iterrows():
    scr, cand = r["screen"], str(r["candidate"])
    inscreen = screen_files(scr)
    sites = find_sites(cand, inscreen)
    where = "IN_SCREEN"
    if not sites:
        sites = find_sites(cand, list(SRC))
        where = "WORKTREE" if sites else "NONE"
    rows.append(dict(screen=scr, candidate=cand, n_sites=len(sites), site_scope=where,
                     sites=json.dumps([(os.path.relpath(p, ROOT), ln, txt)
                                       for p, ln, txt in sites[:8]])))
SITES = pd.DataFrame(rows)
print("\nsite resolution:")
print(SITES["site_scope"].value_counts().to_string())
SITES.to_csv(os.path.join(HERE, "_CONSTRUCTION_SITES.csv"), index=False)
print("wrote _CONSTRUCTION_SITES.csv")

print("\n--- candidates with NO construction site (UNDETERMINABLE so far) ---")
nn = SITES[SITES["site_scope"] == "NONE"]
print(nn.groupby("screen").size().to_string())
print(sorted(nn["candidate"].unique())[:120])
