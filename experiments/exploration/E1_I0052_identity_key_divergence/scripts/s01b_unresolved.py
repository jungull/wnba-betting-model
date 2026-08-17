import pandas as pd, collections, os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
df = pd.read_csv(os.path.join(OUT, "_s01_ops.csv"))
u = df[df["class"] == "UNRESOLVED_KEY"]
print("total ops:", len(df))
print("UNRESOLVED by op/method:")
print(u.groupby(["op", "method"]).size().sort_values(ascending=False).to_string())
print()
HARD = ["JOIN", "GROUPBY", "DEDUP", "SETINDEX", "PIVOT", "LOOKUP", "MEMBERSHIP", "UNIQUE"]
hard = u[u.op.isin(HARD)]
print("HARD unresolved:", len(hard))
print(hard.groupby("op").size().to_string())
print()
c = collections.Counter()
for k in hard["keys"]:
    for t in str(k).split("|"):
        c[t] += 1
print("distinct unresolved key tokens (top 45):")
for t, n in c.most_common(45):
    print("  %5d %s" % (n, t))
print()
print("--- HARD unresolved JOIN/GROUPBY/DEDUP/SETINDEX by file (top 25) ---")
h2 = u[u.op.isin(["JOIN", "GROUPBY", "DEDUP", "SETINDEX", "PIVOT"])]
print(h2.groupby("file").size().sort_values(ascending=False).head(25).to_string())
print()
print("TOTAL hard-structural ops (all classes):")
allh = df[df.op.isin(["JOIN", "GROUPBY", "DEDUP", "SETINDEX", "PIVOT"])]
print(allh.groupby("class").size().to_string())
