"""S00b -- reconnaissance: join keys, PBP assist structure, coverage.  NO STATISTICS COMPUTED."""
from __future__ import annotations
import glob, os, sys
import numpy as np, pandas as pd

ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
KIT = os.path.join(ROOT, r"experiments\exploration\_screen_kit")
sys.path.insert(0, KIT)
import screenkit as sk  # noqa: E402

pd.set_option("display.width", 200)

print("=" * 100); print("master_player manifest + partition"); print("=" * 100)
mp_path = os.path.join(ROOT, r"data\masters\master_player.parquet")
mv = sk.check_manifest(mp_path, verbose=True)
print({k: v for k, v in mv.items() if k in ("status", "usable_at_e0_e1", "asof_granularity", "filtering_helps")})

mp = pd.read_parquet(mp_path)
print("raw shape", mp.shape)
print("seasons:", sorted(mp["season"].dropna().unique().tolist()))
print("season_type:", mp["season_type"].value_counts(dropna=False).to_dict())

mp = mp[mp["season"].isin([2021, 2022, 2023, 2024])].copy()
mp["game_date"] = pd.to_datetime(mp["game_date"], errors="coerce")
sk.assert_partition(mp, verbose=True)
print("filtered shape", mp.shape)
print("by season_type after filter:", mp["season_type"].value_counts(dropna=False).to_dict())
print("games:", mp["game_id"].nunique(), "players:", mp["player_id"].nunique())
print("game_id dtype:", mp["game_id"].dtype, "example:", mp["game_id"].iloc[0])
print("player_id dtype:", mp["player_id"].dtype, "example:", mp["player_id"].iloc[0])

# rows with actual playing time and attempts
act = mp[(pd.to_numeric(mp["minutes"], errors="coerce") > 0) & (pd.to_numeric(mp["fga"], errors="coerce") >= 1)]
print("rows with minutes>0 and fga>=1:", len(act))
print("  regular only:", int((act["season_type"] == "regular").sum()) if "regular" in set(act["season_type"]) else "n/a")

print()
print("=" * 100); print("shotchart <-> master_player key compatibility"); print("=" * 100)
sh = pd.read_parquet(os.path.join(ROOT, r"data\shotcharts\shots_2023_regular.parquet"))
print("shot GAME_ID example:", repr(sh["GAME_ID"].iloc[0]), "dtype", sh["GAME_ID"].dtype)
mp23 = mp[(mp["season"] == 2023)]
print("mp 2023 game_id example:", repr(str(mp23["game_id"].iloc[0])))
sg = set(sh["GAME_ID"].astype(str)); mg = set(mp23["game_id"].astype(str))
print("shot games:", len(sg), " mp2023 games:", len(mg), " intersect:", len(sg & mg))
sp = set(sh["PLAYER_ID"].astype(int)); mpp = set(mp23["player_id"].astype(int))
print("shot players:", len(sp), " mp2023 players:", len(mpp), " intersect:", len(sp & mpp))

# does shot count per player-game match fga?
sc = sh.groupby(["GAME_ID", "PLAYER_ID"]).size().rename("n_shots").reset_index()
sc["game_id"] = sc["GAME_ID"].astype(str); sc["player_id"] = sc["PLAYER_ID"].astype(int)
m = mp23.assign(game_id=mp23["game_id"].astype(str), player_id=mp23["player_id"].astype(int)) \
        .merge(sc[["game_id", "player_id", "n_shots"]], on=["game_id", "player_id"], how="left")
m["n_shots"] = m["n_shots"].fillna(0)
m["fga_n"] = pd.to_numeric(m["fga"], errors="coerce").fillna(0)
agree = float((m["n_shots"] == m["fga_n"]).mean())
print(f"n_shots == fga on {agree:.4f} of 2023 master_player rows")
print("mismatch sample:")
print(m.loc[m["n_shots"] != m["fga_n"], ["player_name", "fga_n", "n_shots", "minutes"]].head(8).to_string())

print()
print("=" * 100); print("play-by-play: assist structure and coverage"); print("=" * 100)
pbps = sorted(glob.glob(os.path.join(ROOT, r"data\playbyplay\*.parquet")))
import collections
pref = collections.Counter(os.path.basename(f)[4:9] for f in pbps)
print("file-prefix counts:", sorted(pref.items()))
print("NOTE 10225* = 2025 season -> NEVER OPENED by this screen")
p = pd.read_parquet(pbps[0])
made = p[p["EVENTMSGTYPE"] == 1]
print("EVENTMSGTYPE==1 (made shot) rows:", len(made))
print("  of which PLAYER2_ID != 0 (assister present):", int((made["PLAYER2_ID"] != 0).sum()))
print(made[["PLAYER1_NAME", "PLAYER2_NAME", "HOMEDESCRIPTION", "VISITORDESCRIPTION"]].head(6).to_string())
print("EVENTMSGTYPE value counts:", p["EVENTMSGTYPE"].value_counts().to_dict())
