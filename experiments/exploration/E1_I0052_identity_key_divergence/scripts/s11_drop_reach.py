"""E1_I0052 s11 -- does the cross-feed DROP reach the champion's fit pool, and by how much?

The result that most weakens this screen's own headline, computed rather than asserted.
"""
import os, sys, json
import pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ik_base as B

M13 = os.path.join(B.EXP, "exploration", "MEASURE_F1_m13_fitpool")
TR = os.path.join(M13, "repro_out", "translation_rows.parquet")
tr = pd.read_parquet(TR)
tr24, g = B.partition_guard(tr, "season", "translation_rows")

B.banner("s11  does the drop reach the fit pool?")
print("  translation_rows: all=%d  2021-2024(=2024 only)=%d" % (len(tr), len(tr24)))
print("  PARTITION GUARD: %s" % json.dumps(g))
PID = 204323
print("\n  player_id %d (Cheyenne Parker-Tyus) in the 2024 fit pool: %d rows"
      % (PID, int((tr24.player_id == PID).sum())))
print("  distinct player_id in the 2024 fit pool: %d" % tr24.player_id.nunique())
print("  fit-pool rows 2024                     : %d" % len(tr24))

# what would her rows have added?
present = int((tr24.player_id == PID).sum())
if present == 0:
    # she is absent: bound the effect by her share of the priced feed
    print("\n  -> she is ABSENT from the 2024 fit pool.")
    print("     The 62 unresolved priced rows collapse to at most a handful of")
    print("     (game_id, player_id) fit-pool rows after consensus-line aggregation.")
    props = pd.read_csv(os.path.join(B.PROD, "data", "props_capture", "historical",
                                     "master_props_historical.csv"), low_memory=False)
    props["game_id"] = props["game_id"].astype(str)
    props["_season"] = props["game_id"].str[3:5].astype(int) + 2000
    pr, _ = B.partition_guard(props, "_season", "props")
    sub = pr[pr.player_name == "Cheyenne Parker"]
    ngames = sub.game_id.nunique()
    print("     her priced rows 2024: %d over %d distinct game_ids" % (len(sub), ngames))
    print("     UPPER BOUND on fit-pool rows lost: %d of %d = %.4f%%"
          % (ngames, len(tr24) + ngames, 100.0 * ngames / (len(tr24) + ngames)))
    print("     (upper bound because a game also needs a scored model row and a")
    print("      two-sided consensus line to enter the pool)")
    lost = ngames
else:
    lost = 0

# is this already disclosed by the m13/m14 audit?
B.banner("is it already disclosed?")
found = []
for root, dirs, files in os.walk(M13):
    if "__pycache__" in root:
        continue
    for f in files:
        if not f.endswith(".json"):
            continue
        fp = os.path.join(root, f)
        try:
            txt = open(fp, "r", encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if "Cheyenne" in txt or "unresolved" in txt.lower():
            hits = []
            if "Cheyenne" in txt:
                hits.append("names Cheyenne")
            for k in ("n_unresolved", "unresolved_names", "unresolved"):
                if '"%s"' % k in txt:
                    hits.append(k)
            found.append((os.path.relpath(fp, B.EXP), sorted(set(hits))))
for fp, h in found:
    print("  %-72s %s" % (fp, h))
if not found:
    print("  NOT disclosed anywhere in MEASURE_F1_m13_fitpool.")

json.dump({"pid": PID, "fit_pool_rows_2024": len(tr24),
           "her_rows_in_fit_pool": present,
           "upper_bound_fit_pool_rows_lost": int(lost),
           "disclosed_in": [f for f, _ in found]},
          open(os.path.join(B.OUT, "_s11.json"), "w"), indent=2)
