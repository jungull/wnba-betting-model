"""S08 -- classify every (screen, candidate) as COMPOSITE or ATOMIC from its construction
EXPRESSION, and extract the component operands.

The classification is made by parsing the right-hand side with `ast` and looking at which
BINARY OPERATORS join two COLUMN-LIKE operands.  A column-like operand is a subscript with a
string key (df["c"]), an attribute access (df.c), or a bare Name that is not a known scalar
literal.  Division/multiplication by a numeric literal is NOT a composite -- that is a rescale.

Nothing here reads the candidate's spelling.  The candidate name is used only to FIND the line.
"""
import ast, json, os, re
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPL = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(EXPL))

S = pd.read_csv(os.path.join(HERE, "_CONSTRUCTION_SITES_V2.csv"))
S["candidate"] = S["candidate"].astype(str)
STRONG = {"SUBSCRIPT_ASSIGN", "GENERATED", "NAME_ASSIGN", "ASSIGN_KW", "RENAME_TO"}
S["kind0"] = S["resolution_kind"].str.split("[").str[0]
print("strong sites: %d / %d" % (int(S["kind0"].isin(STRONG).sum()), len(S)))


def cols_in(node):
    """column-like operands inside an expression node"""
    out = []
    for nd in ast.walk(node):
        if isinstance(nd, ast.Subscript):
            k = nd.slice
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                out.append(k.value)
        elif isinstance(nd, ast.Attribute):
            pass
    return out


def is_columnlike(node):
    if isinstance(node, ast.Subscript):
        return True
    if isinstance(node, ast.Name):
        return True
    if isinstance(node, ast.Call):
        return True
    if isinstance(node, ast.Attribute):
        return True
    if isinstance(node, (ast.BinOp, ast.UnaryOp)):
        return True
    return False


def is_scalar(node):
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float))


OPMAP = {ast.Div: "RATIO", ast.Sub: "DIFFERENCE", ast.Mult: "PRODUCT",
         ast.Add: "SUM", ast.Pow: "POWER"}


def classify_rhs(rhs):
    """returns (class, operand_names, note)"""
    txt = (rhs or "").strip().rstrip("\\").rstrip(",")
    if not txt:
        return "UNDETERMINABLE_EXPR", [], "empty rhs"
    # strip a trailing unbalanced tail so ast can parse a fragment
    for cut in range(0, 6):
        t = txt if cut == 0 else txt[:-cut]
        try:
            tree = ast.parse(t, mode="eval")
            break
        except SyntaxError:
            tree = None
    if tree is None:
        # try balancing brackets
        t = txt
        for ch, op in [(")", "("), ("]", "["), ("}", "{")]:
            miss = t.count(op) - t.count(ch)
            if miss > 0:
                t = t + ch * miss
        try:
            tree = ast.parse(t, mode="eval")
        except SyntaxError:
            return "UNDETERMINABLE_EXPR", [], "unparseable: %s" % txt[:120]
    body = tree.body
    if isinstance(body, (ast.List, ast.Tuple)) and len(body.elts) > 1 and \
       all(isinstance(e, (ast.Constant, ast.Name, ast.Subscript)) for e in body.elts):
        nm = [e.value if isinstance(e, ast.Constant) else
              (e.id if isinstance(e, ast.Name) else "?") for e in body.elts]
        return "BUNDLE", [str(x) for x in nm], "list of %d terms" % len(body.elts)
    found = []
    for nd in ast.walk(body):
        if isinstance(nd, ast.BinOp) and type(nd.op) in OPMAP:
            L, R = nd.left, nd.right
            if is_scalar(L) or is_scalar(R):
                continue
            found.append(OPMAP[type(nd.op)])
    ops = sorted(set(found))
    names = cols_in(body)
    if not ops:
        return "ATOMIC", names, "no binary op on two column-like operands"
    if len(ops) == 1:
        return "COMPOSITE_" + ops[0], names, "op=%s" % ops[0]
    return "COMPOSITE_MIXED", names, "ops=%s" % ",".join(ops)


rows = []
for _, r in S.iterrows():
    if r["kind0"] in STRONG:
        cls, nms, note = classify_rhs(r["rhs"])
        src_kind = "EXPRESSION"
    else:
        cls, nms, note = "UNDETERMINABLE_SITE", [], "site kind=%s" % r["resolution_kind"]
        src_kind = "NO_STRONG_SITE"
    rows.append(dict(screen=r["screen"], candidate=r["candidate"],
                     resolution_kind=r["resolution_kind"], site_scope=r["site_scope"],
                     best_file=r["best_file"], best_line=r["best_line"],
                     construction_expr=str(r["rhs"])[:250], classification_source=src_kind,
                     candidate_class=cls, components=json.dumps(nms[:12]), class_note=note))
K = pd.DataFrame(rows)
K.to_csv(os.path.join(HERE, "_CLASSIFY_RAW.csv"), index=False)
print("\n=== class counts ===")
print(K["candidate_class"].value_counts().to_string())
print("\n=== composites by screen ===")
comp = K[K["candidate_class"].str.startswith(("COMPOSITE", "BUNDLE"))]
print(comp.groupby("screen").size().to_string())
print("\n=== composites, resolved list ===")
print(comp[["screen", "candidate", "candidate_class", "construction_expr"]].to_string(index=False))
print("\n=== unresolved, by screen ===")
un = K[K["candidate_class"].str.startswith("UNDETERMINABLE")]
print(un.groupby(["screen", "candidate_class"]).size().to_string())
print("\nunresolved candidates:")
for scr, g in un.groupby("screen"):
    print("  %-40s %s" % (scr, sorted(g["candidate"].tolist())))
print("\nDONE s08")
