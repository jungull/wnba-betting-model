"""E1 I0011 split-alpha -- build the evaluation frame.

EXPLORATION PARTITION (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY.
The 2025/2026 confirmation holdout is never loaded, joined, counted or described.

Artifact contamination check (13.2.2) -- performed in code below, not by assertion
in prose: both masters' sibling manifests are read and `asof_granularity` is
required to be "row". Row-granularity => filtering to 2021-2024 is SUFFICIENT.

Hazards honoured:
  - master_player.pace is NOT read (E0 found range 0-7200, mean 84.7 vs median 96.1).
  - master_player.position is NOT read (lineup-slot label, empty on 55% of rows).
  - observed_time is dropped and never written.

Output: frame.parquet -- one row per played player-game, 2021-2024.
"""
import json
import numpy as np
import pandas as pd

SEED = 20260807
np.random.seed(SEED)

PARTITION = [2021, 2022, 2023, 2024]
ROOT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program"
HERE = ROOT + r"\experiments\exploration\E1_I0011_split_alpha"

BANNED_COLS = ["pace", "pace_per40", "estimated_pace", "position", "observed_time"]


def manifest_gate(path):
    """13.2.2: an artifact is usable at E0/E1 only if asof_granularity == 'row'."""
    with open(path + ".manifest.json", "r", encoding="utf-8") as fh:
        m = json.load(fh)
    g = m.get("asof_granularity")
    print(f"[manifest] {m.get('artifact')}: asof_granularity={g!r} "
          f"bound_source={m.get('bound_source')!r}")
    if g != "row":
        raise SystemExit(f"UNUSABLE AT E1: asof_granularity={g!r} (need 'row')")
    print("[manifest]   -> row-bounded: filtering to 2021-2024 is sufficient. USABLE.")
    return m


def assert_partition(d, label):
    got = sorted(int(x) for x in pd.unique(d["season"]))
    if not set(got) <= set(PARTITION):
        raise SystemExit(f"{label}: PARTITION VIOLATION {got}")
    print(f"[partition-check] {label}: seasons={got} rows={len(d)}")


MP_PATH = ROOT + r"\data\masters\master_player.parquet"
manifest_gate(MP_PATH)

mp = pd.read_parquet(MP_PATH)
mp = mp[mp["season"].isin(PARTITION)].copy()            # FILTER-POINT (immediately after load)
assert_partition(mp, "master_player raw")

# drop hazardous / non-as-of columns before anything else touches them
drop = [c for c in BANNED_COLS if c in mp.columns]
mp = mp.drop(columns=drop)
print("[hazard] dropped columns:", drop)

for c in ["minutes", "pts", "reb", "ast", "possessions", "usage_percentage",
          "starter_flag", "is_home"]:
    mp[c] = pd.to_numeric(mp[c], errors="coerce").astype(float)

mp = mp[mp["minutes"].fillna(0) > 0].copy()             # played rows only
mp = mp.sort_values(["player_id", "season", "game_date", "game_id"]).reset_index(drop=True)
assert_partition(mp, "master_player played rows")

KEY = ["player_id", "season"]
g = mp.groupby(KEY, sort=False)
mp["n_prior"] = g.cumcount()                            # prior PLAYED games this season

gk = [mp["player_id"], mp["season"]]
mp["std_minutes"] = (g["minutes"].shift(1)
                     .groupby(gk, sort=False).transform(lambda s: s.expanding(1).mean()))
mp["std_usage"] = (g["usage_percentage"].shift(1)
                   .groupby(gk, sort=False).transform(lambda s: s.expanding(1).mean()))

# within-season temporal half, cut on the season's own game-date median (protocol P3)
mp["game_date"] = pd.to_datetime(mp["game_date"])
med = mp.groupby("season")["game_date"].transform("median")
mp["half"] = np.where(mp["game_date"] <= med, 1, 2)

keep = ["game_id", "season", "season_type", "game_date", "team_id", "opp_team_id", "is_home",
        "player_id", "player_name", "starter_flag", "minutes", "pts", "reb", "ast",
        "possessions", "usage_percentage", "n_prior", "std_minutes", "std_usage", "half"]
out = mp[keep].copy()
assert_partition(out, "FINAL frame")
assert "observed_time" not in out.columns and "pace" not in out.columns

out.to_parquet(HERE + r"\frame.parquet", index=False)
print("wrote frame.parquet", out.shape)
print("rows per season:", out.groupby("season").size().to_dict())
print("rows per season x half:", out.groupby(["season", "half"]).size().to_dict())
ev = out[(out["n_prior"] >= 3)]
print("eval-universe rows per season:", ev.groupby("season").size().to_dict())
print("eval-universe rows per season x half:", ev.groupby(["season", "half"]).size().to_dict())
