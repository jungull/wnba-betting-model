"""
REBUILD from raw, uncontaminated sources after coordinator flagged that
data/masters/master_player.parquet (fit_through_season=2026 per its manifest) may be
cross-season-fit and must not be used for an exploration-partition-only (2021-2024) screen.

Raw sources used instead (neither has a manifest.json, consistent with being untouched
single-season/single-game captures rather than cross-season-fit derived products):
  - data/wnba_gamelog_{2021,2022,2023,2024}.parquet  -- per-season, players who played only
    (FGA/FTA/TO/MIN present; used to self-compute usage_percentage with the standard formula,
    not read from any pre-fit master).
  - data/refresh_2026/misc/misc_<game_id>.parquet -- per-GAME files (24 rows = both full
    rosters incl. DNPs), used only to identify absences (comment field) and full roster
    membership. Filtered to game_id season prefix in {21,22,23,24} so 2025/2026 files are
    never opened.

HARD RULE: exploration partition only, seasons 2021-2024. Filter applied at the file-selection
level (glob pattern / season column), not after loading, so 2025/2026 rows never enter memory.
"""
import glob
import re
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0006_usage_redistribution"


def season_of_gid(gid):
    return 2000 + int(gid[3:5])


# ---- 1. player-game panel (players who played), 2021-2024 only ----
gamelog_frames = []
for season in [2021, 2022, 2023, 2024]:
    f = f"data/wnba_gamelog_{season}.parquet"
    df = pd.read_parquet(f)
    assert (df.SEASON.astype(int) == season).all()
    gamelog_frames.append(df)
gl = pd.concat(gamelog_frames, ignore_index=True)
print("raw gamelog rows (2021-2024 only, from per-season files):", len(gl))
assert gl.SEASON.astype(int).between(2021, 2024).all()

# parse "MM.000000:SS" -> float minutes
def parse_min(s):
    if s is None or s == "":
        return np.nan
    whole, sec = s.split(":")
    return float(whole) + float(sec) / 60.0

gl["minutes"] = gl.MIN.apply(parse_min)
gl["season"] = gl.SEASON.astype(int)
gl = gl.rename(columns={"GAME_ID": "game_id", "TEAM_ID": "team_id", "PLAYER_ID": "player_id",
                         "PLAYER_NAME": "player_name", "FGA": "fga", "FTA": "fta", "TO": "tov",
                         "START_POSITION": "start_position"})

# team-game totals for usage% denominator
team_tot = gl.groupby(["game_id", "team_id"]).agg(
    tm_min=("minutes", "sum"), tm_fga=("fga", "sum"), tm_fta=("fta", "sum"), tm_tov=("tov", "sum")
).reset_index()
gl = gl.merge(team_tot, on=["game_id", "team_id"], how="left")

gl["usage_percentage"] = (
    (gl.fga + 0.44 * gl.fta + gl.tov) * (gl.tm_min / 5.0)
) / (gl.minutes * (gl.tm_fga + 0.44 * gl.tm_fta + gl.tm_tov))
# players with 0 minutes shouldn't be in this file (played-only source), but guard anyway
gl.loc[gl.minutes <= 0, "usage_percentage"] = np.nan

print("usage_percentage describe (self-computed, clean):")
print(gl.usage_percentage.describe())
gl.to_parquet(f"{OUT}/clean_played_panel.parquet")

# ---- 2. roster + DNP panel from misc per-game files, 2021-2024 only by filename filter ----
misc_files = sorted(glob.glob("data/refresh_2026/misc/misc_*.parquet"))
misc_files_2124 = []
for f in misc_files:
    gid = re.search(r"misc_(\d+)\.parquet", f).group(1)
    if season_of_gid(gid) in (2021, 2022, 2023, 2024):
        misc_files_2124.append((f, gid))
print("misc per-game files selected for 2021-2024 (season inferred from filename, never opening 2025/2026 files):", len(misc_files_2124))

misc_frames = []
for f, gid in misc_files_2124:
    m = pd.read_parquet(f, columns=["gameId", "teamId", "personId", "firstName", "familyName",
                                     "position", "comment", "minutes"])
    misc_frames.append(m)
misc = pd.concat(misc_frames, ignore_index=True)
misc["season"] = misc.gameId.apply(season_of_gid)
assert misc.season.between(2021, 2024).all()
misc["is_dnp"] = misc.comment.fillna("").str.strip() != ""
misc = misc.rename(columns={"gameId": "game_id", "teamId": "team_id", "personId": "player_id"})
misc["player_name"] = misc.firstName.fillna("") + " " + misc.familyName.fillna("")
print("misc roster rows 2021-2024:", len(misc), " DNP rows:", misc.is_dnp.sum())
misc.to_parquet(f"{OUT}/clean_roster_panel.parquet")

print("DONE rebuild_clean.py")
