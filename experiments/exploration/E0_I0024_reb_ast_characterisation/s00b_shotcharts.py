"""E0_I0024 s00b -- SHOTCHART GRANULARITY + JOIN FEASIBILITY.  Inspection only, no statistics.

The shotchart parquets carry NO MANIFEST.  A MISSING MANIFEST IS UNVERIFIABLE, NEVER A PASS.
D087 nevertheless established ROW-GRANULARITY on VALUE EVIDENCE: SHOT_DISTANCE is reproducible
from that same row's LOC_X / LOC_Y.  This script REPRODUCES that check on the rows this screen
will actually consume (2021-2024 only) rather than citing D087 from notes, and reports the
fraction.  The value evidence is a MITIGATION, not a manifest, and is reported as such.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
OUT = os.path.join(ROOT, r"experiments\exploration\E0_I0024_reb_ast_characterisation")
SHOTDIR = os.path.join(ROOT, r"data\shotcharts")
MT = os.path.join(ROOT, r"data\masters\master_team.parquet")

sys.dont_write_bytecode = True
pd.set_option("display.width", 250)


def hdr(s):
    print("\n" + "=" * 100)
    print(s)
    print("=" * 100)


rep = {}

hdr("1. LOAD SHOTCHARTS 2021-2024 (regular + playoffs).  2025/2026 FILES ARE NEVER OPENED.")
parts = []
opened = []
for s in [2021, 2022, 2023, 2024]:
    for k in ["regular", "playoffs"]:
        p = os.path.join(SHOTDIR, "shots_%d_%s.parquet" % (s, k))
        if not os.path.exists(p):
            print("  MISSING %s" % os.path.basename(p))
            continue
        d = pd.read_parquet(p)
        d["_season"] = s
        d["_type"] = k
        parts.append(d)
        opened.append(os.path.basename(p))
        print("  opened %-32s rows=%d" % (os.path.basename(p), len(d)))
sh = pd.concat(parts, ignore_index=True)
rep["files_opened"] = opened
print("  TOTAL shot rows 2021-2024: %d" % len(sh))

hdr("2. PARTITION CHECK ON VALUES (GAME_DATE parsed, never a byte scan)")
sh["gdate"] = pd.to_datetime(sh["GAME_DATE"].astype(str), format="%Y%m%d", errors="coerce")
print("  parsed dates: %d of %d   range %s .. %s"
      % (sh["gdate"].notna().sum(), len(sh), sh["gdate"].min().date(), sh["gdate"].max().date()))
assert sh["gdate"].max() < pd.Timestamp("2025-01-01"), "PARTITION VIOLATION in shotcharts"
rep["shot_partition"] = dict(ok=True, min=str(sh["gdate"].min().date()),
                             max=str(sh["gdate"].max().date()), n=int(len(sh)))
print("  PARTITION OK")

hdr("3. ROW-GRANULARITY VALUE EVIDENCE (D087 method, REPRODUCED HERE)")
# NBA shot coords are in tenths of a foot; SHOT_DISTANCE is feet, rounded.
d_calc = np.sqrt(sh["LOC_X"].astype(float) ** 2 + sh["LOC_Y"].astype(float) ** 2) / 10.0
for rule, lab in [(np.round(d_calc), "round"), (np.floor(d_calc), "floor")]:
    ok = (rule == sh["SHOT_DISTANCE"].astype(float))
    print("  %-6s rule: reproduced on %d of %d rows = %.6f" % (lab, ok.sum(), len(sh), ok.mean()))
    rep["granularity_%s" % lab] = float(ok.mean())
best = max(rep["granularity_round"], rep["granularity_floor"])
rep["granularity_best_fraction"] = best
print("  BEST = %.6f" % best)
print("  VERDICT: value evidence for ROW granularity; the file still has NO MANIFEST and is")
print("           therefore reported as UNVERIFIABLE_NO_MANIFEST + VALUE_EVIDENCE_ROW.")

hdr("4. JOIN FEASIBILITY: shotchart GAME_ID vs master_team game_id")
mt = pd.read_parquet(MT)
mt["game_date"] = pd.to_datetime(mt["game_date"], errors="coerce")
mt = mt[mt["season"].isin([2021, 2022, 2023, 2024])].copy()
mg = set(mt["game_id"].astype(str))
sg = set(sh["GAME_ID"].astype(str))
print("  master_team games 2021-24: %d   shotchart games: %d" % (len(mg), len(sg)))
print("  shotchart games found in master_team: %d (%.4f)"
      % (len(sg & mg), len(sg & mg) / max(len(sg), 1)))
print("  master_team games with shotchart:     %d (%.4f)"
      % (len(sg & mg), len(sg & mg) / max(len(mg), 1)))
rep["join"] = dict(master_games=len(mg), shot_games=len(sg), overlap=len(sg & mg),
                   shot_cov=len(sg & mg) / max(len(sg), 1),
                   master_cov=len(sg & mg) / max(len(mg), 1))
print("\n  examples only in shotcharts: %s" % sorted(list(sg - mg))[:5])
print("  examples only in master:     %s" % sorted(list(mg - sg))[:5])

hdr("5. TEAM_ID CONSISTENCY")
st = set(sh["TEAM_ID"].astype("int64"))
mtid = set(pd.to_numeric(mt["team_id"], errors="coerce").dropna().astype("int64"))
print("  shot TEAM_IDs: %d   master team_ids: %d   overlap: %d" % (len(st), len(mtid), len(st & mtid)))
rep["team_overlap"] = len(st & mtid)

hdr("6. SHOTS PER GAME SANITY (both teams present in each game?)")
g = sh.groupby("GAME_ID")["TEAM_ID"].nunique()
print("  games with exactly 2 shooting teams: %d of %d (%.4f)"
      % ((g == 2).sum(), len(g), (g == 2).mean()))
rep["games_two_teams_frac"] = float((g == 2).mean())

hdr("7. ZONE VOCABULARY ACROSS ALL 2021-2024")
print(sh["SHOT_ZONE_BASIC"].value_counts().to_string())
rep["zones"] = sh["SHOT_ZONE_BASIC"].value_counts().to_dict()
print("\n  SHOT_TYPE:")
print(sh["SHOT_TYPE"].value_counts().to_string())

hdr("8. SHOTCHART vs BOX FGA RECONCILIATION (team-game level)")
sh["att"] = pd.to_numeric(sh["SHOT_ATTEMPTED_FLAG"], errors="coerce").fillna(0)
sh["made"] = pd.to_numeric(sh["SHOT_MADE_FLAG"], errors="coerce").fillna(0)
agg = sh.groupby(["GAME_ID", "TEAM_ID"], as_index=False).agg(sc_fga=("att", "sum"),
                                                             sc_fgm=("made", "sum"))
agg["GAME_ID"] = agg["GAME_ID"].astype(str)
agg["TEAM_ID"] = agg["TEAM_ID"].astype("int64")
m = mt.copy()
m["game_id"] = m["game_id"].astype(str)
m["team_id"] = pd.to_numeric(m["team_id"], errors="coerce").astype("int64")
j = m.merge(agg, left_on=["game_id", "team_id"], right_on=["GAME_ID", "TEAM_ID"], how="inner")
j["d_fga"] = pd.to_numeric(j["fga"], errors="coerce") - j["sc_fga"]
j["d_fgm"] = pd.to_numeric(j["fgm"], errors="coerce") - j["sc_fgm"]
print("  matched team-games: %d" % len(j))
print("  FGA exact match: %.4f   mean|diff|=%.4f" % ((j["d_fga"] == 0).mean(), j["d_fga"].abs().mean()))
print("  FGM exact match: %.4f   mean|diff|=%.4f" % ((j["d_fgm"] == 0).mean(), j["d_fgm"].abs().mean()))
rep["fga_exact_match"] = float((j["d_fga"] == 0).mean())
rep["fgm_exact_match"] = float((j["d_fgm"] == 0).mean())

json.dump(rep, open(os.path.join(OUT, "_s00b.json"), "w"), indent=2, default=str)
print("\nWROTE _s00b.json")
