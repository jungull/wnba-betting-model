"""E1_I0052 s02 -- print every PLAYER_NAME_KEYED / MIXED site with source context.
Named-case discipline: the count is not the finding; the sites are."""
import pandas as pd, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "out")
EXP = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments"

df = pd.read_csv(os.path.join(OUT, "_s01_ops.csv"))
sites = df[df["class"].isin(["PLAYER_NAME_KEYED", "MIXED"])].sort_values(["file", "line"])
print("name-keyed / mixed sites:", len(sites), "in", sites.file.nunique(), "files\n")

for f, g in sites.groupby("file"):
    fp = os.path.join(EXP, f.replace("/", os.sep))
    lines = open(fp, "r", encoding="utf-8-sig", errors="replace").read().splitlines()
    print("=" * 100)
    print(f)
    print("=" * 100)
    for _, r in g.iterrows():
        lo = max(0, r.line - 4)
        hi = min(len(lines), r.line + 3)
        print("  --- L%d  %s(%s)  keys=%s  [%s]" % (r.line, r.method, r.op, r["keys"], r["class"]))
        for i in range(lo, hi):
            mark = ">>" if i == r.line - 1 else "  "
            print("   %s %4d| %s" % (mark, i + 1, lines[i][:150]))
        print()
