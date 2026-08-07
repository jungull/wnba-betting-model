"""S37 auditor re-derivation. WRITES NOTHING outside the scratchpad."""
import sys, io, json, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np, pandas as pd

W = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
N = W + r"\experiments\player_program\stage3_score\S36_IMPLEMENT_ARMS"
sys.path.insert(0, N + r"\runner"); sys.path.insert(0, N + r"\arms")

import runner_constants as K
import universe as U
import runner
from canon import column_digest, join_key_digest, sha256_file

print("=== M2: universe re-derived independently at S37 ===")
u = U.build_universe()
print("n_clusters:", len(u.games), " n_team_rows:", len(u.team_rows))
print("game_id_digest:", u.game_id_digest)
print("per_season:", u.games.groupby("season")["game_id"].nunique().to_dict())
print("composite fallback clusters:", int((u.games["composite_source"]==K.FALLBACK_METHOD).sum()))
print("C_p_home NaN on the 1491 universe rows:", int(u.games["C_p_home"].isna().sum()))
print("  of which season==2021:", int(u.games.loc[u.games["C_p_home"].isna(),"season"].eq(2021).sum()))
print("  season breakdown:", u.games.loc[u.games["C_p_home"].isna()].groupby("season").size().to_dict())
print("settled ties:", int((u.games["E2_FINAL_MARGIN_HOME"]==0).sum()))

print()
print("=== raw score_baseline_rows composite p_home NaN (the '188' claim) ===")
sb = pd.read_parquet(K.artifact_path("experiments/market_program/SCORE_BASELINES/score_baseline_rows.parquet"))
sb["game_id"]=sb["game_id"].astype(str)
comp = sb[sb["method"]==K.COMPOSITE_METHOD]
print("composite rows:", len(comp), " p_home NaN:", int(comp['p_home'].isna().sum()),
      " pred_margin NaN:", int(comp['pred_margin'].isna().sum()),
      " pred_total NaN:", int(comp['pred_total'].isna().sum()))
cg = set(comp["game_id"]); ug = set(u.games["game_id"])
print("composite game_ids in universe:", len(cg & ug), " composite not in universe:", len(cg-ug))
nanids = set(comp.loc[comp['p_home'].isna(),'game_id'])
print("p_home-NaN composite ids that ARE in the universe:", len(nanids & ug))
sub = u.games[u.games["game_id"].isin(nanids)]
print("  their seasons:", sub.groupby("season").size().to_dict())

print()
print("=== M3: R10 byte-pin recomputation ===")
def canon_vals(s):
    out=[]
    for v in s:
        if isinstance(v,float) or (hasattr(v,'dtype') and np.issubdtype(type(v), np.floating)):
            out.append(repr(float(v)))
        elif isinstance(v,(int,np.integer)):
            out.append(str(int(v)))
        else:
            out.append(str(v))
    return out
for pin in K.FROZEN_COLUMN_PINS:
    df = pd.read_parquet(K.artifact_path(pin["artifact"]))
    df["game_id"]=df["game_id"].astype(str)
    if pin["method_filter"]:
        df = df[df["method"]==pin["method_filter"]]
    keys = pin["join_key_columns"]
    if len(keys)==1:
        df = df.sort_values("game_id", key=lambda s: s.astype(str), kind="mergesort")
    else:
        df["team_id"]=df["team_id"].astype("int64")
        df = df.sort_values(keys, key=lambda s: s.astype(str), kind="mergesort")
    col = df[pin["column"]]
    d = column_digest(col)
    ok = d==pin["column_sha256"]
    print("%-32s n=%d n_nan=%d digest_match=%s (carded n=%d n_nan=%d)" % (
        pin["column"], len(col), int(col.isna().sum()), ok, pin["n_values"], pin["n_nan"]))
    rows = list(zip(*[df[k].tolist() for k in keys]))
    jk = join_key_digest(rows)
    print("     join_key_match=%s" % (jk==pin["join_key_sha256"]))
