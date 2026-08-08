"""E1_I0034 step 1: inspect every input BEFORE preregistering anything.

READ ONLY.  Prints schemas, manifests, row counts, partition coverage.
No statistic of the research question is computed here.
"""
import json, os, sys
import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, "experiments", "exploration", "_screen_kit")
sys.dont_write_bytecode = True
if KIT not in sys.path:
    sys.path.insert(0, KIT)
import screenkit as sk  # noqa

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 200)


def hdr(s):
    print("\n" + "=" * 100); print(s); print("=" * 100)


MASTER_PLAYER = os.path.join(ROOT, "data", "masters", "master_player.parquet")
MASTER_TEAM = os.path.join(ROOT, "data", "masters", "master_team.parquet")
CV4 = os.path.join(ROOT, "experiments", "prediction_contract_v4")
PLAYER_ARM = os.path.join(ROOT, "experiments", "cbs_v15_player_oof_v5", "attempt_001")
BIOS = os.path.join(ROOT, "data", "reference", "player_bios.csv")

hdr("MANIFEST CHECKS")
for p in [MASTER_PLAYER, MASTER_TEAM,
          os.path.join(CV4, "player_game.parquet"),
          os.path.join(CV4, "team_game.parquet")]:
    try:
        r = sk.check_manifest(p, verbose=False)
        print(os.path.basename(p), "->", json.dumps(r, default=str)[:600])
    except Exception as e:
        print(os.path.basename(p), "-> EXC", type(e).__name__, e)

hdr("MASTER_PLAYER schema")
mp = pd.read_parquet(MASTER_PLAYER)
print("shape", mp.shape)
print(list(mp.columns))
print(mp.dtypes.to_string())
print("\nseason counts:"); print(mp["season"].value_counts().sort_index().to_string())

hdr("MASTER_PLAYER head (2022)")
print(mp[mp["season"] == 2022].head(6).to_string())

hdr("MASTER_TEAM schema")
mt = pd.read_parquet(MASTER_TEAM)
print("shape", mt.shape)
print(list(mt.columns))
print("season counts:"); print(mt["season"].value_counts().sort_index().to_string())

hdr("CONTRACT v4 player_game")
cv4p = pd.read_parquet(os.path.join(CV4, "player_game.parquet"))
print("shape", cv4p.shape)
print(list(cv4p.columns))
print(cv4p.dtypes.to_string())
print(cv4p.head(5).to_string())
for c in cv4p.columns:
    if cv4p[c].dtype == bool or str(cv4p[c].dtype).startswith("bool"):
        print("BOOL col", c, cv4p[c].mean())
if "season" in cv4p.columns:
    print("season counts:"); print(cv4p["season"].value_counts().sort_index().to_string())

hdr("CONTRACT v4 team_game")
cv4t = pd.read_parquet(os.path.join(CV4, "team_game.parquet"))
print("shape", cv4t.shape); print(list(cv4t.columns))
print(cv4t.head(3).to_string())

hdr("PLAYER ARM files")
for f in sorted(os.listdir(PLAYER_ARM)):
    fp = os.path.join(PLAYER_ARM, f)
    print(f, os.path.getsize(fp) if os.path.isfile(fp) else "<dir>")

hdr("PLAYER ARM predictions schema (one file)")
import glob
cand = sorted(glob.glob(os.path.join(PLAYER_ARM, "predictions__*__2022.parquet")))
for c in cand:
    d = pd.read_parquet(c)
    print(os.path.basename(c), d.shape, list(d.columns))
    print(d.head(3).to_string())

hdr("BIOS")
b = pd.read_csv(BIOS)
print("shape", b.shape); print(list(b.columns))
print(b.head(5).to_string())

hdr("COLDSTART TIERING dir")
cs = os.path.join(ROOT, "experiments", "exploration", "E1_I0020_coldstart_tiering")
if os.path.isdir(cs):
    for f in sorted(os.listdir(cs)):
        print(f)
