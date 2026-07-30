#!/usr/bin/env python3
"""
Rebuild the channel base from the REBUILT uniform masters (Phase 1, step 1).

Inputs:  data/masters/master_team.parquet + data/masters/master_player.parquet
         (NOT the drive_masters CSVs -- those are the July-15 diff targets).
Output:  experiments/channel_reval/channel_base_v2.csv, schema-identical to the
         July experiment's channel_base.csv (experiments/channels/build_channel_base.py)
         so the re-validation isolates DATA + harness, not schema drift.

Channels per team-game (box-score identity: ch_ft + ch_3pt + pts_2s == pts):
    ch_ft    = ftm
    ch_3pt   = 3 * fg3m
    ch_paint = team-summed player points_paint (== master_team.points_paint,
               verified identical on every row before use)
    ch_np2   = 2*(fgm - fg3m) - ch_paint            (must be >= 0)

Verifications run every time (the masters certify these; we re-prove, never trust):
    1. box identity violations == 0
    2. ch_np2 < 0 count == 0
    3. player-summed paint == master_team.points_paint on every row
    4. opp_* mirror consistency: row A's opp stats == row B's own stats per game
    5. every game has exactly two rows, exactly one home

Note on the 1,296 player-sum-derived team rows (2021-23 regular seasons):
the channel inputs used here (ftm / fg3m / fgm / pts) are IDENTICAL between
derived and real team rows -- player-sum reconciliation was 0-mismatch
(data/masters/REBUILD_VALIDATION.md sec.3, sec.4a: ftm/fg3m/fgm/pts all 2132/2132
exact vs the Drive masters). Channel results are therefore invariant to the
pending team-gamelog upgrade of those rows (which changes team-credited TOV only).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "channel_base_v2.csv"

team = pd.read_parquet(REPO / "data/masters/master_team.parquet")
player = pd.read_parquet(REPO / "data/masters/master_player.parquet")

# ---- team-summed paint from the player master (July methodology) ----
agg = (
    player.groupby(["game_id", "team_id"], as_index=False)
    .agg(team_pts_paint=("points_paint", "sum"), n_paint_rows=("points_paint", "count"))
)
df = team.merge(agg, on=["game_id", "team_id"], how="left", validate="one_to_one")

failures = []

# check 3: player-summed paint must equal the team-row misc paint on every row
paint_diff = (df["team_pts_paint"] - df["points_paint"]).abs()
n_paint_mismatch = int((paint_diff > 0).sum() + df["team_pts_paint"].isna().sum())
if n_paint_mismatch:
    failures.append(f"player-summed paint != master_team.points_paint on {n_paint_mismatch} rows")

# ---- July schema mapping ----
df = df.rename(
    columns={
        "game_id": "GAME_ID",
        "team_id": "TEAM_ID",
        "team_abbreviation": "TEAM_ABBREVIATION",
        "game_date": "GAME_DATE",
        "season": "year",
        "pf": "team_pf",
        "fouls_drawn": "team_pfd",
        "fta": "team_fta",
        "ftm": "team_ftm",
        "ft_pct": "team_ft_pct",
        "fg3a": "team_fg3a",
        "fg3m": "team_fg3m",
        "fga": "team_fga",
        "fgm": "team_fgm",
        "pts": "team_pts",
    }
)
df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
df["is_home"] = df["is_home"].astype(int)

df["ch_ft"] = df.team_ftm
df["ch_3pt"] = df.team_fg3m * 3
df["pts_2s"] = (df.team_fgm - df.team_fg3m) * 2
df["ch_paint"] = df.team_pts_paint
df["ch_np2"] = df.pts_2s - df.team_pts_paint

# check 1 + 2
viol = int((df.ch_ft + df.ch_3pt + df.pts_2s - df.team_pts).abs().gt(0).sum())
neg = int((df.ch_np2 < 0).sum())
if viol:
    failures.append(f"box identity violations: {viol} (expected 0)")
if neg:
    failures.append(f"negative non-paint-2s rows: {neg} (expected 0)")

# check 5: exactly two rows per game, exactly one home
per_game = df.groupby("GAME_ID").agg(n=("TEAM_ID", "size"), h=("is_home", "sum"))
bad_pairs = int((per_game.n != 2).sum())
bad_home = int((per_game.h != 1).sum())
if bad_pairs or bad_home:
    failures.append(f"games without exactly 2 rows: {bad_pairs}; without exactly 1 home: {bad_home}")

keep = [
    "GAME_ID", "TEAM_ID", "TEAM_ABBREVIATION", "GAME_DATE", "year", "season_type", "is_home",
    "team_pf", "team_pfd", "team_fta", "team_ftm", "team_ft_pct", "team_fg3a", "team_fg3m",
    "team_fga", "team_fgm", "team_pts_paint", "team_pts",
    "ch_ft", "ch_3pt", "ch_paint", "ch_np2", "pts_2s",
]
d = df[keep].copy()

# ---- opponent self-merge (July methodology) ----
opp = d[["GAME_ID", "TEAM_ID", "team_pf", "team_fta", "team_fg3a", "team_fg3m", "team_ftm",
         "ch_3pt", "ch_paint", "ch_np2", "ch_ft", "team_pts"]].copy()
opp.columns = ["GAME_ID", "OPP_TEAM_ID", "opp_pf", "opp_fta", "opp_fg3a", "opp_fg3m", "opp_ftm",
               "opp_ch_3pt", "opp_ch_paint", "opp_ch_np2", "opp_ch_ft", "opp_pts"]
pairs = d.merge(opp, on="GAME_ID")
pairs = pairs[pairs.TEAM_ID != pairs.OPP_TEAM_ID].sort_values(["TEAM_ID", "GAME_DATE", "GAME_ID"]).reset_index(drop=True)

# check 4: our self-merge must agree with the master's own opp_* mirror columns
mirror = team.rename(columns={"game_id": "GAME_ID", "team_id": "TEAM_ID"})[
    ["GAME_ID", "TEAM_ID", "opp_pf", "opp_fta", "opp_fg3a", "opp_fg3m", "opp_ftm", "opp_pts", "opp_points_paint"]
]
chk = pairs.merge(mirror, on=["GAME_ID", "TEAM_ID"], suffixes=("", "_master"), validate="one_to_one")
mirror_bad = 0
for c in ["opp_pf", "opp_fta", "opp_fg3a", "opp_fg3m", "opp_ftm", "opp_pts"]:
    mirror_bad += int((chk[c] - chk[f"{c}_master"]).abs().gt(0).sum())
mirror_bad += int((chk["opp_ch_paint"] - chk["opp_points_paint"]).abs().gt(0).sum())
if mirror_bad:
    failures.append(f"opp mirror disagreements vs master_team opp_* columns: {mirror_bad}")

n_derived = int((team.box_source == "player_sum").sum())

print(f"rows: {len(pairs)} | games: {pairs.GAME_ID.nunique()}")
print(f"box identity violations: {viol} | negative np2: {neg} (both must be 0)")
print(f"player-summed paint vs master_team.points_paint mismatches: {n_paint_mismatch}")
print(f"opp mirror disagreements: {mirror_bad}")
print(f"player_sum-derived team rows carried (2021-23 reg. seasons): {n_derived} "
      f"-- channel inputs identical to real team rows (see module docstring)")
print(pairs.groupby("year")[["ch_ft", "ch_3pt", "ch_paint", "ch_np2"]].mean().round(1))
print("^ sanity: paint ~34-36 and np2 ~7-10 every season; a season with paint ~0 means broken misc data")

if failures:
    for f in failures:
        print("FAIL:", f, file=sys.stderr)
    sys.exit(1)

pairs.to_csv(OUT, index=False)
print(f"wrote {OUT}")
