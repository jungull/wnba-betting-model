"""
E1 I0008 -- build the analysis frame for the height/size-mismatch lead.

Independently rebuilds the RUNG-1 / RUNG-2 frame described in
experiments/exploration/E0_I0008_height_differential/NOTES.md, from the same two raw
sources, inside THIS screen's directory. Nothing outside this directory is written.

PARTITION GUARD (GRAPH_POLICY 13.2): seasons 2021-2024 ONLY. Every load is followed
immediately by a `# FILTER-POINT` on the season COLUMN VALUES (never a byte scan), and
sorted(season.unique()) is printed after each one.

Manifest / 13.2.2 check is performed here on bytes and printed, not cited.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.dirname(os.path.abspath(__file__))
EXPLORATION_SEASONS = [2021, 2022, 2023, 2024]
FORBIDDEN_SEASONS = {2025, 2026}

MP_PATH = os.path.join(REPO, "data", "masters", "master_player.parquet")
MP_MANIFEST = MP_PATH + ".manifest.json"
BIOS_PATH = os.path.join(REPO, "data", "reference", "player_bios.csv")


def assert_partition(df, name):
    """Re-assert the partition on COLUMN VALUES. Hard-exit on violation."""
    seasons = sorted(int(s) for s in pd.unique(df["season"]))
    print(f"  [partition] {name}: seasons = {seasons}  rows = {len(df)}")
    bad = FORBIDDEN_SEASONS.intersection(seasons)
    if bad:
        sys.exit(f"PARTITION VIOLATION in {name}: {sorted(bad)}")
    if "game_date" in df.columns and len(df):
        gd = pd.to_datetime(df["game_date"], errors="coerce")
        print(f"  [partition] {name}: game_date range = {gd.min()} .. {gd.max()}")
        if gd.max() is not pd.NaT and gd.max() >= pd.Timestamp("2025-01-01"):
            sys.exit(f"PARTITION VIOLATION (date) in {name}: max game_date {gd.max()}")
    return seasons


print("=" * 78)
print("MANIFEST / GRAPH_POLICY 13.2.2 CHECK -- read from bytes, this session")
print("=" * 78)
manifest_records = {}

with open(MP_MANIFEST, "r", encoding="utf-8") as fh:
    man = json.load(fh)
rec = {
    "artifact": "data/masters/master_player.parquet",
    "manifest_present": True,
    "asof_granularity": man.get("asof_granularity"),
    "fit_seasons": man.get("fit_seasons"),
    "fit_through_season": man.get("fit_through_season"),
    "content_sha256": man.get("content_sha256"),
    "13_2_2_test": "asof_granularity == 'row'",
    "13_2_2_pass": man.get("asof_granularity") == "row",
}
manifest_records["master_player.parquet"] = rec
print(json.dumps(rec, indent=2))
if not rec["13_2_2_pass"]:
    sys.exit("13.2.2 FAIL: master_player.parquet is not row-granular; cannot use.")

bios_manifest = BIOS_PATH + ".manifest.json"
rec_b = {
    "artifact": "data/reference/player_bios.csv",
    "manifest_present": os.path.exists(bios_manifest),
    "asof_granularity": None,
    "note": (
        "Static biographical data (height_inches / weight_lbs / position_raw), keyed "
        "(player_id, season). No manifest sibling exists; not a statistically fit artifact. "
        "Filtered to 2021-2024 on season column values anyway."
    ),
    "13_2_2_pass": None,
}
manifest_records["player_bios.csv"] = rec_b
print(json.dumps(rec_b, indent=2))

print()
print("=" * 78)
print("LOAD + FILTER")
print("=" * 78)

mp = pd.read_parquet(MP_PATH)
print("master_player raw:", mp.shape, "raw seasons present:", sorted(mp["season"].unique()))
mp = mp[mp["season"].isin(EXPLORATION_SEASONS)].copy()  # FILTER-POINT
assert_partition(mp, "master_player after FILTER-POINT")

bios = pd.read_csv(BIOS_PATH)
print("player_bios raw:", bios.shape, "raw seasons present:", sorted(bios["season"].unique()))
bios = bios[bios["season"].isin(EXPLORATION_SEASONS)].copy()  # FILTER-POINT
assert_partition(bios, "player_bios after FILTER-POINT")

# played rows only (DNP rows carry no rebound signal) -- matches E0 I0008
mp = mp[mp["minutes"].fillna(0) > 0].copy()
assert_partition(mp, "master_player after minutes>0")

bios_h = (
    bios[["player_id", "season", "height_inches", "weight_lbs", "position_raw"]]
    .drop_duplicates(["player_id", "season"])
)
mp = mp.merge(bios_h, on=["player_id", "season"], how="left")
print("own height matched on:", round(float(mp["height_inches"].notna().mean()), 4), "of rows")
assert_partition(mp, "after bios merge")

# ---------------------------------------------------------------------------
# Opponent roster-height aggregates, keyed on TRUE teams.
#   rung 1: season minutes-weighted mean height over every player who logged minutes
#   rung 2: same, restricted to the team-season's top 8 players by total season minutes
# NOTE (forward-fill audit): these aggregates are means of a STATIC biographical field.
# There is no per-player rate being carried forward, so the "forward-fill last observed
# rate indefinitely" defect seen in sibling roster-pool constructions does not apply.
# What DOES apply: the minutes WEIGHTS are full-season, so the aggregate is not strictly
# pregame-observable at game t. Recorded in NOTES.md.
# ---------------------------------------------------------------------------
h = mp.dropna(subset=["height_inches"]).copy()
h["_hm"] = h["height_inches"] * h["minutes"]

roster = (
    h.groupby(["team_id", "season"], as_index=False)
    .agg(_num=("_hm", "sum"), _den=("minutes", "sum"))
)
roster["team_roster_mean_height"] = roster["_num"] / roster["_den"]
roster = roster[["team_id", "season", "team_roster_mean_height"]]
assert_partition(roster, "roster height profile")
print("team-season roster profiles:", roster.shape)

season_minutes = h.groupby(["team_id", "season", "player_id"], as_index=False)["minutes"].sum()
season_minutes["rot_rank"] = (
    season_minutes.groupby(["team_id", "season"])["minutes"].rank(ascending=False, method="first")
)
rot = season_minutes[season_minutes["rot_rank"] <= 8].merge(
    bios_h[["player_id", "season", "height_inches"]], on=["player_id", "season"], how="left"
).dropna(subset=["height_inches"])
rot["_hm"] = rot["height_inches"] * rot["minutes"]
rotation = (
    rot.groupby(["team_id", "season"], as_index=False)
    .agg(_num=("_hm", "sum"), _den=("minutes", "sum"))
)
rotation["team_rotation_mean_height"] = rotation["_num"] / rotation["_den"]
rotation = rotation[["team_id", "season", "team_rotation_mean_height"]]
assert_partition(rotation, "rotation height profile")
print("team-season rotation profiles:", rotation.shape)

# ---------------------------------------------------------------------------
# Attach the opponent's profile to each player-game row
# ---------------------------------------------------------------------------
df = mp.dropna(subset=["height_inches", "opp_team_id"]).copy()
df = df.merge(
    roster.rename(columns={"team_id": "opp_team_id",
                           "team_roster_mean_height": "opp_roster_mean_height"}),
    on=["opp_team_id", "season"], how="left",
)
df = df.merge(
    rotation.rename(columns={"team_id": "opp_team_id",
                             "team_rotation_mean_height": "opp_rotation_mean_height"}),
    on=["opp_team_id", "season"], how="left",
)
df["rung1_height_diff"] = df["height_inches"] - df["opp_roster_mean_height"]
df["rung2_height_diff"] = df["height_inches"] - df["opp_rotation_mean_height"]
print("rows with rung1 diff:", int(df["rung1_height_diff"].notna().sum()))
print("rows with rung2 diff:", int(df["rung2_height_diff"].notna().sum()))

# ---------------------------------------------------------------------------
# Own recent rate -- EXACTLY the estimator E0 I0008 used for its headline:
# trailing EWMA halflife=5, min_periods=3, .shift(1), within (player_id, season).
# (Stage 2, if reached, replaces this with own_rate_v2_split_alpha.)
# ---------------------------------------------------------------------------
df = df.sort_values(["player_id", "season", "game_date"]).copy()


def trailing_ewma(s, halflife=5):
    return s.shift(1).ewm(halflife=halflife, min_periods=3).mean()


df["own_recent_oreb_pct"] = df.groupby(["player_id", "season"])["offensive_rebound_percentage"].transform(trailing_ewma)
df["own_recent_dreb_pct"] = df.groupby(["player_id", "season"])["defensive_rebound_percentage"].transform(trailing_ewma)

keep = [
    "game_id", "season", "game_date", "player_id", "player_name", "team_id", "opp_team_id",
    "position", "position_raw", "minutes", "height_inches", "weight_lbs",
    "oreb", "dreb", "reb",
    "opp_roster_mean_height", "opp_rotation_mean_height",
    "rung1_height_diff", "rung2_height_diff",
    "offensive_rebound_percentage", "defensive_rebound_percentage",
    "own_recent_oreb_pct", "own_recent_dreb_pct",
]
out = df[keep].copy()
assert_partition(out, "FINAL frame (re-assert before write)")
out.to_parquet(os.path.join(OUT, "frame.parquet"), index=False)
print("wrote frame.parquet:", out.shape)

with open(os.path.join(OUT, "manifest_checks.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest_records, fh, indent=2)
print("wrote manifest_checks.json")
print("DONE build_frame")
