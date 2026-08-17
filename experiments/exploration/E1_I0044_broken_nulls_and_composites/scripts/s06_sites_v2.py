"""S06 -- construction-site resolution, v2: adds GENERATED column names.

Many candidate columns are created with a format literal, e.g. `app["pl_%s_sd5" % tag] = ...`
or `f["{}__pred_cv".format(t)]`.  An exact-string search cannot see them.  Resolving them by
guessing from the candidate's own spelling would be exactly the name-based inference that has
killed six findings here.  Instead the GENERATOR is taken from the source: every string literal
used as an assignment target that contains a format placeholder is turned into the regex it can
produce, and candidate names are matched against the code's own generator.  The matched
generator line is then read for its right-hand side.

Also adds:
  * `columns=[...]` / `DataFrame(..., columns=[...])` / `.rename(columns={...})` targets
  * bare `"name",` inside an explicit list literal assigned to a *_CANDS / *_COLS style variable

Output: _CONSTRUCTION_SITES_V2.csv with, per (screen, candidate):
  n_sites, site_scope, resolution_kind, rhs_expression (where extractable), sites json
"""
import json, os, re
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXPL))

cen = pd.read_csv(os.path.join(EXPL, "E1_I0036_level_artefact_sweep", "CENSUS.csv"),
                  low_memory=False)
ext = pd.read_csv(os.path.join(EXPL, "E1_I0040_audit_extension", "AUDIT_TABLE_EXT.csv"),
                  low_memory=False)
pairs = pd.concat([cen[["screen", "candidate"]], ext[["screen", "candidate"]]],
                  ignore_index=True).drop_duplicates().reset_index(drop=True)
pairs["candidate"] = pairs["candidate"].astype(str)
assert len(pairs) == 540

SRC = {}
for dp, dn, fn in os.walk(ROOT):
    if ".git" in dp or "__pycache__" in dp:
        continue
    for x in fn:
        if x.endswith(".py"):
            p = os.path.join(dp, x)
            try:
                SRC[p] = open(p, "r", encoding="utf-8-sig", errors="replace").read()
            except Exception:
                pass
print(".py files read: %d" % len(SRC))

LINES = {p: t.splitlines() for p, t in SRC.items()}

# ---------------------------------------------------------------- literal assignment targets
LIT_PATS = [
    (r'\[\s*[\'"]{nm}[\'"]\s*\]\s*(?:=|\+=)\s*(?P<rhs>.*)$', "SUBSCRIPT_ASSIGN"),
    (r'^\s*{nm}\s*=\s*(?P<rhs>.*)$',                          "NAME_ASSIGN"),
    (r'\bassign\s*\([^)]*?\b{nm}\s*=\s*(?P<rhs>[^,)]*)',      "ASSIGN_KW"),
    (r'[\'"]{nm}[\'"]\s*:\s*(?P<rhs>[^,}}]*)',                "DICT_VALUE"),
    (r'\(\s*[\'"]{nm}[\'"]\s*,\s*(?P<rhs>[^)]*)\)',           "TUPLE_PAIR"),
    (r'\brename\s*\([^)]*[\'"](?P<rhs>[^\'"]+)[\'"]\s*:\s*[\'"]{nm}[\'"]', "RENAME_TO"),
    (r'columns\s*=\s*\[[^\]]*[\'"]{nm}[\'"]',                 "COLUMNS_LIST"),
    (r'[\'"]{nm}[\'"]',                                       "MENTION"),
]

# ---------------------------------------------------------------- generated (format) targets
GEN_RX = re.compile(
    r'\[\s*(?:f?)([\'"])(?P<lit>[^\'"]*?(?:%s|%d|\{\}|\{[A-Za-z_][A-Za-z0-9_]*\})[^\'"]*?)\1'
    r'\s*(?:%|\.format\s*\()?[^\]]*\]\s*=\s*(?P<rhs>.*)$')

def lit_to_regex(lit):
    parts = re.split(r'(%s|%d|%[0-9.]*f|\{\}|\{[A-Za-z_][A-Za-z0-9_]*\})', lit)
    out = []
    for p in parts:
        if re.fullmatch(r'(%s|%d|%[0-9.]*f|\{\}|\{[A-Za-z_][A-Za-z0-9_]*\})', p or ""):
            out.append(r'[A-Za-z0-9_]+')
        else:
            out.append(re.escape(p or ""))
    return re.compile("^" + "".join(out) + "$")

RAW_GEN = []
for p, lns in LINES.items():
    for i, ln in enumerate(lns):
        m = GEN_RX.search(ln)
        if m:
            lit = m.group("lit")
            try:
                RAW_GEN.append((lit_to_regex(lit), p, i + 1, lit, m.group("rhs").strip()))
            except re.error:
                pass
print("format-literal column generators found in source: %d" % len(RAW_GEN))

# ---- REJECT OVER-BROAD GENERATORS.  A generator that matches half the programme's candidate
# names identifies nothing; accepting it would be name-based inference wearing a code-shaped hat.
# Three objective rules, applied before any candidate is resolved, and the rejects are printed.
ALLNAMES = sorted(set(str(x) for x in pairs["candidate"]))
GENERATORS = []
REJECTED = []
for rx, p, ln, lit, rhs in RAW_GEN:
    lit_chars = len(re.sub(r'(%s|%d|%[0-9.]*f|\{\}|\{[A-Za-z_][A-Za-z0-9_]*\})', '', lit))
    nmatch = sum(1 for x in ALLNAMES if rx.match(x))
    in_expl = (os.sep + "exploration" + os.sep) in p
    why = []
    if lit_chars < 4: why.append("literal_chars<4(%d)" % lit_chars)
    if nmatch > 10:   why.append("matches>10(%d)" % nmatch)
    if not in_expl:   why.append("file_outside_exploration")
    if why and nmatch > 0:
        REJECTED.append(dict(literal=lit, file=os.path.relpath(p, ROOT), line=ln,
                             n_candidate_matches=nmatch, literal_chars=lit_chars,
                             reason=";".join(why)))
    if not why:
        GENERATORS.append((rx, p, ln, lit, rhs))
print("generators ACCEPTED: %d   REJECTED (that matched >=1 candidate): %d"
      % (len(GENERATORS), len(REJECTED)))
if REJECTED:
    RJ = pd.DataFrame(REJECTED).drop_duplicates(["literal", "file", "line"])
    RJ.to_csv(os.path.join(HERE, "_GENERATORS_REJECTED.csv"), index=False)
    print(RJ.sort_values("n_candidate_matches", ascending=False).head(20).to_string(index=False))

def screen_dir(scr):
    return os.path.join(EXPL, scr)

def files_for(scr):
    d = screen_dir(scr)
    return [p for p in SRC if p.startswith(d + os.sep)]

def find(nm, files):
    esc = re.escape(nm)
    hits = []
    for p in files:
        if nm not in SRC[p]:
            continue
        for i, ln in enumerate(LINES[p]):
            for pat, kind in LIT_PATS:
                m = re.search(pat.format(nm=esc), ln)
                if m:
                    rhs = ""
                    try:
                        rhs = (m.group("rhs") or "").strip()
                    except Exception:
                        rhs = ""
                    hits.append((kind, os.path.relpath(p, ROOT), i + 1, ln.strip()[:300], rhs[:300]))
                    break
    return hits

def find_generated(nm, files):
    hits = []
    for rx, p, ln, lit, rhs in GENERATORS:
        if files is not None and p not in files:
            continue
        if rx.match(nm):
            hits.append(("GENERATED[%s]" % lit, os.path.relpath(p, ROOT), ln,
                         LINES[p][ln - 1].strip()[:300], rhs[:300]))
    return hits

ORDER = ["SUBSCRIPT_ASSIGN", "GENERATED", "NAME_ASSIGN", "ASSIGN_KW", "RENAME_TO",
         "TUPLE_PAIR", "DICT_VALUE", "COLUMNS_LIST", "MENTION"]
def rank(kind):
    k = kind.split("[")[0]
    return ORDER.index(k) if k in ORDER else 99

rows = []
for _, r in pairs.iterrows():
    scr, nm = str(r["screen"]), str(r["candidate"])
    fs = files_for(scr)
    hits = find(nm, fs) + find_generated(nm, fs)
    hits = sorted(hits, key=lambda h: rank(h[0]))
    scope = "IN_SCREEN"
    STRONG = ("SUBSCRIPT_ASSIGN", "GENERATED", "NAME_ASSIGN", "ASSIGN_KW", "RENAME_TO")
    # a bare MENTION / column-list / dict-key is NOT a construction site.  If the screen only
    # mentions the column (it was imported from another screen's builder), search the worktree.
    if (not hits) or (hits[0][0].split("[")[0] not in STRONG):
        wide = find(nm, list(SRC)) + find_generated(nm, None)
        wide = sorted(wide, key=lambda h: rank(h[0]))
        if wide and wide[0][0].split("[")[0] in STRONG:
            hits = wide
            scope = "WORKTREE"
        elif not hits:
            hits = wide
            scope = "WORKTREE" if wide else "NONE"
    best = hits[0] if hits else None
    rows.append(dict(
        screen=scr, candidate=nm, n_sites=len(hits), site_scope=scope,
        resolution_kind=(best[0] if best else "NONE"),
        best_file=(best[1] if best else ""), best_line=(best[2] if best else -1),
        best_src=(best[3] if best else ""),
        rhs=(best[4] if best else ""),
        sites=json.dumps(hits[:10])))
S = pd.DataFrame(rows)
S.to_csv(os.path.join(HERE, "_CONSTRUCTION_SITES_V2.csv"), index=False)
print("\nscope:"); print(S["site_scope"].value_counts().to_string())
print("\nresolution kind:")
print(S["resolution_kind"].str.split("[").str[0].value_counts().to_string())
print("\nstill NONE by screen:")
nn = S[S["site_scope"] == "NONE"]
print(nn.groupby("screen").size().to_string() if len(nn) else "  (none)")
print("\nNONE candidates:"); print(sorted(nn["candidate"].tolist()))
print("\nDONE s06")
