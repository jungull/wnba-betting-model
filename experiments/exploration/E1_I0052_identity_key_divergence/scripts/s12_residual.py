"""E1_I0052 s12 -- the RESIDUAL: could an unresolved key be a name key?

872 structural operations hold their key in a variable my static resolver could not fold.
The headline "nothing diverges" is only earned if none of them is a hidden name key ON A
FRAME WHERE AN IDENTITY IS AMBIGUOUS. Anywhere else a name key cannot diverge, because the
name is a bijection with the id there.

So the residual is bounded to: unresolved structural ops inside the screens that own or
consume one of the 16 frames in which an identity is ambiguous within 2021-2024. Those are
printed in full with source context and adjudicated by hand.
"""
import os, sys, json
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

ops = pd.read_csv(os.path.join(B.OUT, "_s01_ops.csv"))
guard = pd.read_csv(os.path.join(B.OUT, "_s07_frame_divergence_guarded.csv"))
hot = guard[pd.to_numeric(guard.get("ids_with_multiple_names"), errors="coerce").fillna(0) > 0]


def screen_of(path):
    parts = str(path).split("/")
    return parts[0] + "/" + parts[1] if len(parts) >= 2 else parts[0]


hot_screens = sorted({screen_of(p) for p in hot.path})
B.banner("s12  RESIDUAL -- unresolved keys in the screens where ambiguity actually exists")
print("  frames with an in-partition ambiguous identity: %d" % len(hot))
print("  owning screens (%d):" % len(hot_screens))
for s in hot_screens:
    print("    %s" % s)

ops["screen"] = ops["file"].map(screen_of)
STRUCT = ["JOIN", "GROUPBY", "DEDUP", "SETINDEX", "PIVOT"]
res = ops[(ops.screen.isin(hot_screens)) & (ops.op.isin(STRUCT)) &
          (ops["class"] == "UNRESOLVED_KEY")]
print("\n  unresolved structural ops inside those screens: %d" % len(res))
print("  (out of %d unresolved structural ops repository-wide)"
      % int(((ops.op.isin(STRUCT)) & (ops["class"] == "UNRESOLVED_KEY")).sum()))

EXPD = B.EXP
for f, g in res.groupby("file"):
    fp = os.path.join(EXPD, f.replace("/", os.sep))
    lines = open(fp, "r", encoding="utf-8-sig", errors="replace").read().splitlines()
    print("\n  " + "-" * 88)
    print("  " + f)
    for _, r in g.iterrows():
        i = int(r.line) - 1
        ctx = "\n".join("        %4d| %s" % (j + 1, lines[j][:130])
                        for j in range(max(0, i - 2), min(len(lines), i + 2)))
        print("    L%-5d %s(%s) keys=%s" % (r.line, r.method, r.op, r["keys"]))
        print(ctx)

# also: consumers of the hot frames anywhere in the lane
B.banner("who reads the ambiguous frames?")
names = sorted({os.path.basename(p) for p in hot.path})
print("  frame basenames: %s" % names)
hits = {}
for root, dirs, files in os.walk(EXPD):
    if "__pycache__" in root:
        continue
    for fn in files:
        if not fn.endswith(".py"):
            continue
        fp = os.path.join(root, fn)
        try:
            txt = open(fp, "r", encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        for n in names:
            if n in txt:
                hits.setdefault(n, []).append(os.path.relpath(fp, EXPD).replace("\\", "/"))
for n in names:
    cs = sorted(set(hits.get(n, [])))
    print("\n  %-46s read by %d file(s)" % (n, len(cs)))
    for c in cs:
        sc = screen_of(c)
        nk = int(ops[(ops.file == c) & (ops["class"].isin(
            ["PLAYER_NAME_KEYED", "MIXED"]))].shape[0])
        print("      %-72s name_keyed_ops=%d" % (c, nk))

json.dump({"hot_screens": hot_screens,
           "unresolved_structural_ops_in_hot_screens": int(len(res)),
           "unresolved_structural_ops_repo_wide": int(
               ((ops.op.isin(STRUCT)) & (ops["class"] == "UNRESOLVED_KEY")).sum())},
          open(os.path.join(B.OUT, "_s12.json"), "w"), indent=2)
