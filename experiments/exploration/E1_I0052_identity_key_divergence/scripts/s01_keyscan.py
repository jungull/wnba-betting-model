"""
E1_I0052 s01 — AST census of every join / grouping / de-duplication / index / lookup
in the research lane.

NOT a grep. Parses every .py under experiments/exploration and
experiments/player_program with `ast`, walks Call nodes, and records the KEY COLUMNS
of every keyed operation, whatever they are named. Name-keying is then a *classification*
of the recovered keys, not the search term.

Operations recovered:
  merge / join            -> on=, left_on=, right_on=
  groupby                 -> by / positional
  drop_duplicates         -> subset=
  set_index / sort_values -> keys
  pivot / pivot_table     -> index=, columns=
  value_counts/unique/nunique/isin/map on an attribute or getitem  -> that column
  factorize               -> column
  Series.map(dict)        -> column
  .loc/.reindex on index  -> flagged separately

Writes: out/_s01_ops.csv   (one row per keyed operation)
"""
import ast, os, csv, json, sys, hashlib

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments")
OUT = os.path.join(EXP, "exploration", "E1_I0052_identity_key_divergence", "out")
os.makedirs(OUT, exist_ok=True)

SCOPES = [os.path.join(EXP, "exploration"), os.path.join(EXP, "player_program")]
SELF = os.path.join(EXP, "exploration", "E1_I0052_identity_key_divergence")

KEYED_METHODS = {
    "merge": ("JOIN", ("on", "left_on", "right_on")),
    "join": ("JOIN", ("on",)),
    "groupby": ("GROUPBY", ("by",)),
    "drop_duplicates": ("DEDUP", ("subset",)),
    "duplicated": ("DEDUP", ("subset",)),
    "set_index": ("SETINDEX", ("keys",)),
    "sort_values": ("SORT", ("by",)),
    "pivot": ("PIVOT", ("index", "columns")),
    "pivot_table": ("PIVOT", ("index", "columns")),
    "unstack": ("PIVOT", ()),
    "nunique": ("CARDINALITY", ()),
    "unique": ("UNIQUE", ()),
    "factorize": ("FACTORIZE", ()),
    "isin": ("MEMBERSHIP", ()),
    "map": ("LOOKUP", ()),
    "value_counts": ("CARDINALITY", ()),
    "reindex": ("REINDEX", ()),
    "transform": ("GROUPTRANSFORM", ()),
    "agg": ("GROUPAGG", ()),
}


def lit(node):
    """Recover string literal(s) from an AST node; return list of strings or None."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out = []
        for e in node.elts:
            r = lit(e)
            if r:
                out.extend(r)
            else:
                out.append("<expr>")
        return out
    if isinstance(node, ast.Name):
        return ["<var:%s>" % node.id]
    if isinstance(node, ast.Attribute):
        return ["<attr:%s>" % node.attr]
    if isinstance(node, ast.Subscript):
        inner = lit(node.slice)
        return ["<sub:%s>" % (",".join(inner) if inner else "?")]
    return None


def receiver_col(node):
    """If the call receiver is df['col'] or df.col, recover 'col'."""
    if isinstance(node, ast.Subscript):
        r = lit(node.slice)
        if r and len(r) == 1 and not r[0].startswith("<"):
            return r[0]
        return None
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def receiver_src(node):
    try:
        return ast.unparse(node)[:120]
    except Exception:
        return "?"


IDLIKE = ("player_id", "person_id", "athlete_id", "nba_id", "pid",
          "team_id", "game_id", "obligation_key", "entity_id")
NAMELIKE = ("player_name", "name", "player", "athlete", "full_name",
            "display_name", "playername")


def classify(keys):
    """Return (klass, evidence). PLAYER_NAME dominates if any key is a player name."""
    ks = [k for k in keys if k and not k.startswith("<")]
    low = [k.lower() for k in ks]
    name_hits = [k for k in low if k in ("player_name", "player", "name", "full_name",
                                         "display_name", "player_norm", "name_norm",
                                         "norm_name", "playername", "player_key")]
    id_hits = [k for k in low if "player_id" in k or k in ("person_id", "athlete_id")]
    if name_hits and not id_hits:
        return "PLAYER_NAME_KEYED", ";".join(name_hits)
    if name_hits and id_hits:
        return "MIXED", ";".join(name_hits + id_hits)
    if id_hits:
        return "PLAYER_ID_KEYED", ";".join(id_hits)
    return "NOT_PLAYER_KEYED", ""


rows = []
files_scanned = 0
parse_fail = []

for scope in SCOPES:
    for dirpath, dirnames, filenames in os.walk(scope):
        if "__pycache__" in dirpath:
            continue
        if dirpath.startswith(SELF):
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                src = open(fp, "r", encoding="utf-8-sig", errors="replace").read()
                tree = ast.parse(src)
            except Exception as e:
                parse_fail.append((fp, repr(e)))
                continue
            files_scanned += 1
            rel = os.path.relpath(fp, EXP)

            # ---- per-file constant table: NAME = "col" / NAME = ["a","b"] ----
            consts = {}
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign) and len(n.targets) == 1 and \
                        isinstance(n.targets[0], ast.Name):
                    v = lit(n.value)
                    if v and all(not x.startswith("<") for x in v):
                        consts.setdefault(n.targets[0].id, v)

            def resolve(keys):
                out = []
                for k in keys:
                    if k.startswith("<var:") and k[5:-1] in consts:
                        out.extend(consts[k[5:-1]])
                    else:
                        out.append(k)
                return out

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute):
                    continue
                meth = node.func.attr
                if meth not in KEYED_METHODS:
                    continue
                # --- exclude str.join / os.path.join, which are not DataFrame joins ---
                if meth == "join":
                    recv = node.func.value
                    if isinstance(recv, ast.Constant):
                        continue                      # "sep".join(...)
                    if isinstance(recv, ast.Attribute) and recv.attr in ("path", "sep"):
                        continue                      # os.path.join(...)
                    if isinstance(recv, ast.Name) and recv.id in ("os", "posixpath", "ntpath"):
                        continue
                    src_j = receiver_src(node)
                    if "path.join" in src_j or src_j.startswith(("'", '"')):
                        continue
                    # a real DataFrame .join always names a frame-ish receiver AND
                    # is rare here; keep it, it will be reviewed by hand.
                # --- .map(callable) is not a lookup; only .map(dict/Series) is ---
                if meth == "map" and node.args and isinstance(
                        node.args[0], (ast.Lambda, ast.Name)) and not node.keywords:
                    pass  # keep, classified by receiver column
                op, kwnames = KEYED_METHODS[meth]
                keys = []
                for kw in node.keywords:
                    if kw.arg in kwnames:
                        r = lit(kw.value)
                        if r:
                            keys.extend(r)
                # positional for groupby/merge-on/sort_values/set_index/isin
                if meth in ("groupby", "set_index", "sort_values", "isin",
                            "drop_duplicates", "duplicated") and node.args:
                    r = lit(node.args[0])
                    if r:
                        keys.extend(r)
                if meth == "merge" and len(node.args) >= 2:
                    r = lit(node.args[1])
                    if r:
                        keys.extend(r)
                # column-level ops: key is the receiver column
                if meth in ("unique", "nunique", "value_counts", "factorize",
                            "isin", "map", "duplicated"):
                    rc = receiver_col(node.func.value)
                    if rc:
                        keys.append(rc)
                if not keys:
                    keys = ["<none>"]
                keys = resolve(keys)
                klass, ev = classify(keys)
                if klass == "NOT_PLAYER_KEYED" and \
                        any(k.startswith("<") for k in keys) and \
                        not any(k for k in keys if not k.startswith("<")):
                    klass = "UNRESOLVED_KEY"
                rows.append({
                    "file": rel.replace("\\", "/"),
                    "line": node.lineno,
                    "op": op,
                    "method": meth,
                    "keys": "|".join(keys),
                    "class": klass,
                    "name_evidence": ev,
                    "src": receiver_src(node)[:160],
                })

with open(os.path.join(OUT, "_s01_ops.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)

from collections import Counter
c = Counter(r["class"] for r in rows)
print("files scanned:", files_scanned, " parse failures:", len(parse_fail))
print("keyed operations recovered:", len(rows))
for k, v in c.most_common():
    print("   %-20s %6d" % (k, v))
print()
print("--- PLAYER_NAME_KEYED / MIXED, by file ---")
cf = Counter(r["file"] for r in rows if r["class"] in ("PLAYER_NAME_KEYED", "MIXED"))
for k, v in cf.most_common():
    print("   %4d  %s" % (v, k))
print()
print("--- PLAYER_ID_KEYED, by file (top 25) ---")
ci = Counter(r["file"] for r in rows if r["class"] == "PLAYER_ID_KEYED")
for k, v in ci.most_common(25):
    print("   %4d  %s" % (v, k))
if parse_fail:
    print()
    print("--- parse failures ---")
    for fp, e in parse_fail[:20]:
        print("   ", os.path.relpath(fp, EXP), e)
