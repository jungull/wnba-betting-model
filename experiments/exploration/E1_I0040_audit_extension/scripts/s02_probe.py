"""S02 -- Second pass, deliberately LOOSER than S01, so a null result is not an artefact of a
tight regex.

 (a) ANY use of max()/np.maximum/.max() on a line that also mentions a p-value, in the 30 screens.
 (b) ANY 'ceiling' column or ceiling verdict in the 30 screens' tables  -> arithmetic-ceiling kills.
 (c) ANY kill / verdict / clears column, so we know which tables contain DECIDED cells.
 (d) CSV-stored permutation draws (E1_I0021, E1_I0030) tested empirically for standardisation.
"""
import os, re, json
import numpy as np
import pandas as pd

EXPL = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

cov = pd.read_csv(os.path.join(EXPL, "E1_I0038_within_entity_null_audit", "CENSUS_COVERAGE.csv"))
CENSUS = {"E0_I0014_residual_heterogeneity", "E0_I0016_efficiency_predictors",
          "E0_I0017_shot_quality_efficiency", "E0_I0019_availability_forecast",
          "E0_I0024_reb_ast_characterisation", "E0_I0029_freethrow_hurdle",
          "E1_I0018_teammate_volume_channel", "E1_I0023_usage_defence_interaction"}
TARGETS = [s for s in sorted(cov["screen"].unique()) if s not in CENSUS]

# ---------------- (a) LOOSE max() scan ----------------
loose = []
MAXWORD = re.compile(r"\bmax\b|\.max\(|maximum", re.I)
PWORD = re.compile(r"\bp[_a-z0-9]*\b|pval|p_value|alpha|signif", re.I)
for sc in TARGETS:
    d = os.path.join(EXPL, sc)
    for root, _dd, files in os.walk(d):
        for fn in files:
            if not fn.lower().endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            try:
                src = open(fp, "r", encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for ln, line in enumerate(src.splitlines(), 1):
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if MAXWORD.search(s) and PWORD.search(s):
                    loose.append(dict(screen=sc, file=os.path.relpath(fp, EXPL).replace("\\", "/"),
                                      line=ln, code=s[:220]))
L = pd.DataFrame(loose)
L.to_csv(os.path.join(HERE, "MAX_SIGNATURE_LOOSE.csv"), index=False)
print("LOOSE max()+p lines:", len(L))
if len(L):
    print(L.to_string(max_colwidth=200))

# ---------------- (b)(c) ceiling / kill / verdict columns ----------------
CEIL = re.compile(r"ceiling|ceil_|arithmetic_max|max_attainable|upper_bound", re.I)
KILL = re.compile(r"kill|verdict|clears|survive|decision|status|outcome|reject|pass_fail|is_dead", re.I)
rows = []
for sc in TARGETS:
    d = os.path.join(EXPL, sc)
    for root, _dd, files in os.walk(d):
        for fn in files:
            if not fn.lower().endswith(".csv"):
                continue
            fp = os.path.join(root, fn)
            try:
                head = pd.read_csv(fp, nrows=3)
            except Exception:
                continue
            cols = list(head.columns)
            c_ceil = [c for c in cols if CEIL.search(c)]
            c_kill = [c for c in cols if KILL.search(c)]
            if c_ceil or c_kill:
                try:
                    full = pd.read_csv(fp)
                except Exception:
                    continue
                vals = {}
                for c in (c_ceil + c_kill)[:8]:
                    vc = full[c].astype(str).value_counts().head(8).to_dict()
                    vals[c] = vc
                rows.append(dict(screen=sc, file=os.path.relpath(fp, EXPL).replace("\\", "/"),
                                 rows=len(full), ceiling_cols="|".join(c_ceil),
                                 kill_cols="|".join(c_kill), value_counts=json.dumps(vals)[:1500]))
K = pd.DataFrame(rows)
K.to_csv(os.path.join(HERE, "INVENTORY_KILL_COLS.csv"), index=False)
print("\ntables with ceiling/kill/verdict columns:", len(K))
if len(K):
    print(K[["screen", "file", "rows", "ceiling_cols", "kill_cols"]].to_string(max_colwidth=90))

# ---------------- (d) CSV draw dumps: standardised? ----------------
draws = []
for sc in TARGETS:
    d = os.path.join(EXPL, sc)
    for root, _dd, files in os.walk(d):
        for fn in files:
            if not fn.lower().endswith(".csv") or "draw" not in fn.lower():
                continue
            fp = os.path.join(root, fn)
            try:
                df = pd.read_csv(fp)
            except Exception:
                continue
            num = df.select_dtypes("number")
            stats = {}
            for c in num.columns:
                a = num[c].to_numpy(float)
                a = a[np.isfinite(a)]
                if a.size >= 50:
                    stats[c] = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), n=int(a.size))
            std_like = [c for c, v in stats.items()
                        if abs(v["mean"]) < 1e-6 and abs(v["sd"] - 1) < 1e-4]
            draws.append(dict(screen=sc, file=os.path.relpath(fp, EXPL).replace("\\", "/"),
                              rows=len(df), numeric_cols=len(stats),
                              standardised_cols="|".join(std_like),
                              RAW_RECOVERABLE=(len(std_like) == 0),
                              stats=json.dumps(stats)[:1200]))
D = pd.DataFrame(draws)
D.to_csv(os.path.join(HERE, "INVENTORY_CSV_DRAWS.csv"), index=False)
print("\nCSV draw dumps:", len(D))
if len(D):
    print(D[["screen", "file", "rows", "numeric_cols", "standardised_cols", "RAW_RECOVERABLE"]].to_string())
