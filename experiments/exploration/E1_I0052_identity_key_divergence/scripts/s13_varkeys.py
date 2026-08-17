"""E1_I0052 s13 -- close the residual formally.

Every assignment whose target is a key-shaped variable name, in the whole research lane,
recovered by AST and inspected for a player-name column. This converts "I could not resolve
872 keys" into "here is what those variables are actually bound to".
"""
import ast, os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

SCOPES = [os.path.join(B.EXP, "exploration"), os.path.join(B.EXP, "player_program")]
SELF = os.path.join(B.EXP, "exploration", "E1_I0052_identity_key_divergence")
KEYVARS = {"key", "keys", "KEY", "KEYS", "gk", "GK", "pk", "PK", "kk", "_kk", "tk", "ka",
           "kt", "kp", "grp", "by", "keycols", "key_cols", "key_col", "keycol", "lvl",
           "lvl_cols", "entity_cols", "group", "group_col", "groupcols", "_key", "ck"}
NAME_TOKENS = ("player_name", "playername", "full_name", "display_name", "norm_name",
               "player_norm", "name_norm")

rows = []
for scope in SCOPES:
    for dp, dn, fns in os.walk(scope):
        if "__pycache__" in dp or dp.startswith(SELF):
            continue
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(dp, fn)
            try:
                src = open(fp, "r", encoding="utf-8-sig", errors="replace").read()
                tree = ast.parse(src)
            except Exception:
                continue
            for n in ast.walk(tree):
                if not isinstance(n, ast.Assign):
                    continue
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id in KEYVARS:
                        try:
                            rhs = ast.unparse(n.value)
                        except Exception:
                            rhs = "?"
                        rows.append({"file": os.path.relpath(fp, B.EXP).replace("\\", "/"),
                                     "line": n.lineno, "var": t.id, "rhs": rhs[:200]})

df = pd.DataFrame(rows)
B.banner("s13  every key-shaped variable binding in the research lane")
print("  assignments recovered: %d in %d files" % (len(df), df.file.nunique()))
low = df.rhs.str.lower()
df["mentions_player_name"] = low.apply(lambda s: any(t in s for t in NAME_TOKENS))
df["mentions_player_id"] = low.str.contains("player_id")
print("  bindings mentioning a PLAYER NAME column : %d" % int(df.mentions_player_name.sum()))
print("  bindings mentioning player_id            : %d" % int(df.mentions_player_id.sum()))
print("  bindings mentioning neither              : %d"
      % int((~df.mentions_player_name & ~df.mentions_player_id).sum()))
if df.mentions_player_name.any():
    print("\n  THE NAME-BEARING BINDINGS, in full:")
    for _, r in df[df.mentions_player_name].iterrows():
        print("    %-70s L%-5d %s = %s" % (r.file, r.line, r["var"], r.rhs))
else:
    print("\n  ZERO key-shaped variables in the research lane are bound to a player-name column.")
print("\n  the ten most common bindings:")
print(df.rhs.value_counts().head(10).to_string())
df.to_csv(os.path.join(B.OUT, "_s13_key_variable_bindings.csv"), index=False)
json.dump({"n_bindings": int(len(df)),
           "n_mentioning_player_name": int(df.mentions_player_name.sum()),
           "n_mentioning_player_id": int(df.mentions_player_id.sum())},
          open(os.path.join(B.OUT, "_s13.json"), "w"), indent=2)
