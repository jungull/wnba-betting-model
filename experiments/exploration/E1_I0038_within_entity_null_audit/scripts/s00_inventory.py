"""S00 -- inventory: what columns exist, everywhere, that could tell us
   (a) the null scheme, (b) the level the null permutes at,
   (c) the level the candidate varies at, (d) null_mean, (e) observed statistic.

READ ONLY. Writes nothing outside this screen's directory.
"""
import os, json, glob
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
EXP = os.path.join(ROOT, "experiments", "exploration")
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def hdr(s):
    print("\n" + "=" * 100 + "\n" + s + "\n" + "=" * 100)

# ---- 1. every FINDINGS.json under exploration
hdr("FINDINGS.json FILES")
fj = sorted(glob.glob(os.path.join(EXP, "**", "FINDINGS.json"), recursive=True))
for p in fj:
    print(f"  {os.path.relpath(p, EXP)}  [{os.path.getsize(p)}]")
print(f"total {len(fj)}")

# ---- 2. every CSV under exploration, with columns matching null/level keywords
hdr("CSV FILES WITH NULL / LEVEL / MEAN COLUMNS")
KEYS = ["null", "scheme", "level", "entity", "var_share", "between", "within",
        "perm", "shuffle", "cyclic", "swap", "cluster", "p_"]
csvs = sorted(glob.glob(os.path.join(EXP, "**", "*.csv"), recursive=True))
print(f"scanning {len(csvs)} csvs")
rows = []
for p in csvs:
    rel = os.path.relpath(p, EXP)
    if rel.startswith("E1_I0038"):
        continue
    try:
        cols = list(pd.read_csv(p, nrows=0).columns)
    except Exception as e:
        rows.append(dict(file=rel, ncol=-1, nrow=-1, hits="ERR:" + str(e)[:60]))
        continue
    hits = [c for c in cols if any(k in c.lower() for k in KEYS)]
    if not hits:
        continue
    try:
        n = sum(1 for _ in open(p, encoding="utf-8", errors="replace")) - 1
    except Exception:
        n = -1
    rows.append(dict(file=rel, ncol=len(cols), nrow=n, hits="|".join(hits)))
inv = pd.DataFrame(rows)
inv.to_csv(os.path.join(OUT, "_inventory_csv_columns.csv"), index=False)
print(f"{len(inv)} csvs carry at least one matching column -> _inventory_csv_columns.csv")

# ---- 3. specifically: which files carry a null_mean-like column
hdr("FILES WITH A NULL-MEAN-LIKE COLUMN")
NM = ["null_mean", "nullmean", "mean_null", "null_mu", "null_avg"]
for r in rows:
    h = r["hits"].lower()
    if any(k in h for k in NM):
        print(f"  {r['file']}  ({r['nrow']} rows)")
        print(f"      {r['hits']}")

# ---- 4. and: which carry a var_share/between-like column
hdr("FILES WITH A VARIANCE-SHARE COLUMN")
for r in rows:
    h = r["hits"].lower()
    if "var_share" in h:
        print(f"  {r['file']}  ({r['nrow']} rows)")
        print(f"      {r['hits']}")

# ---- 5. the 8 census source files, full column dump
hdr("CENSUS SOURCE FILES -- FULL COLUMNS")
SRC = [
    "E0_I0014_residual_heterogeneity/screen_results.csv",
    "E0_I0016_efficiency_predictors/screen_results.csv",
    "E0_I0017_shot_quality_efficiency/screen_results.csv",
    "E0_I0019_availability_forecast/screen_results_repaired.csv",
    "E0_I0024_reb_ast_characterisation/upstream_signals.csv",
    "E0_I0029_freethrow_hurdle/screen_results.csv",
    "E1_I0018_teammate_volume_channel/screen_results.csv",
    "E1_I0023_usage_defence_interaction/interaction_forecast.csv",
]
for s in SRC:
    p = os.path.join(EXP, *s.split("/"))
    d = pd.read_csv(p)
    print(f"\n--- {s}   shape={d.shape}")
    for c in d.columns:
        print(f"      {c}")
