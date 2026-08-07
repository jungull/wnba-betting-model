"""
E0 I0008 -- On-court height/size differential vs rebound outcomes, 2021-2024 ONLY.

HARD PARTITION FILTER APPLIED HERE (line marked FILTER-POINT): possessions_v2 season
column is filtered to {'2021','2022','2023','2024'} immediately after load, before any
other join. Events are then restricted to game_ids that survive that filter. 2025/2026
are never read into any dataframe in this script.

Reuses the possessions_v2 (off_p1..5 / def_p1..5) on-court lineup fields and the
canonical_player_events_v1 rebound events, matched by clock-time-to-possession-interval
join -- the SAME construction I0003 used and flagged as ~72% accurate on side-of-play
(84% DRB, 43% ORB). That defect is inherited here and is NOT re-measured; see NOTES.md.
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0008_height_differential"

# ---- load ----------------------------------------------------------------
poss = pd.read_parquet("experiments/player_program/possessions_v2/possessions_raw_v2.parquet")
ev = pd.read_parquet("experiments/player_program/event_contract_v1/canonical_player_events_v1.parquet")
bios = pd.read_csv("data/reference/player_bios.csv")

# FILTER-POINT: exploration partition only, applied before any further join.
EXPLORATION_SEASONS = {"2021", "2022", "2023", "2024"}
poss = poss[poss["season"].isin(EXPLORATION_SEASONS)].copy()
print("possessions after partition filter:", poss.shape, sorted(poss["season"].unique()))

partition_game_ids = set(poss["game_id"].unique())
print("n games in partition:", len(partition_game_ids))

ev = ev[ev["game_id"].isin(partition_game_ids)].copy()
print("events after restricting to partition game_ids:", ev.shape)

# ---- bios lookup (player_id, season) -> height_inches -------------------
bios["season_str"] = bios["season"].astype(str)
bios_lookup = bios.set_index(["player_id", "season_str"])["height_inches"].to_dict()

def height_of(pid, season):
    if pd.isna(pid):
        return np.nan
    return bios_lookup.get((int(pid), season), np.nan)

# ---- rebound events -------------------------------------------------------
reb = ev[ev["event_family"] == "rebound"].copy()
print("rebound events in partition:", reb.shape)

# ---- clock-time join to possession lineups (inherits I0003's known ceiling) ----
# For each game+period, sort possessions by descending start clock and use merge_asof
# (direction='backward' on a DEscending-sorted key emulated by negating clock) to find
# the possession whose [end_sec, start_sec] clock window contains the event's clock.
poss_sorted = poss.sort_values(["game_id", "period", "period_clock_start_sec"], ascending=[True, True, False]).copy()
reb_sorted = reb.sort_values(["game_id", "period", "clock_seconds_remaining"], ascending=[True, True, False]).copy()

# normalize join-key dtypes so merge_asof's by= columns match exactly
for df_ in (poss_sorted, reb_sorted):
    df_["game_id"] = df_["game_id"].astype(str)
    df_["period"] = df_["period"].astype("int64")

# merge_asof requires numeric ascending keys; negate clock so it's ascending.
poss_sorted["_neg_clock"] = -poss_sorted["period_clock_start_sec"]
reb_sorted["_neg_clock"] = -reb_sorted["clock_seconds_remaining"]

matched = pd.merge_asof(
    reb_sorted,
    poss_sorted,
    by=["game_id", "period"],
    on="_neg_clock",
    direction="backward",
    suffixes=("_ev", "_poss"),
)

# keep only matches where the event's clock actually falls within the matched possession's window
matched = matched[
    (matched["clock_seconds_remaining"] <= matched["period_clock_start_sec"])
    & (matched["clock_seconds_remaining"] >= matched["period_clock_end_sec"])
].copy()
print("rebound events with a valid enclosing possession match:", matched.shape[0], "of", reb.shape[0])

# require a fully-populated 10-man lineup on the matched possession
matched = matched[matched["lineup_valid_ten"] == True].copy()
print("...and lineup_valid_ten==True:", matched.shape[0])

# ---- side-of-play: offense (ORB) vs defense (DRB) for the credited rebounder ----
# event_team_id on the rebound event = the team credited with the board.
matched["is_orb"] = (matched["event_team_id"] == matched["offense_team_id"]).astype(int)

# ---- height differential at the moment of the rebound ---------------------
off_cols = ["off_p1", "off_p2", "off_p3", "off_p4", "off_p5"]
def_cols = ["def_p1", "def_p2", "def_p3", "def_p4", "def_p5"]

season_col = matched["season"]  # from possessions side, string

def mean_height(row, cols):
    hs = [height_of(row[c], row["season"]) for c in cols]
    hs = [h for h in hs if not pd.isna(h)]
    return np.mean(hs) if hs else np.nan

matched["off_mean_height"] = matched.apply(lambda r: mean_height(r, off_cols), axis=1)
matched["def_mean_height"] = matched.apply(lambda r: mean_height(r, def_cols), axis=1)
matched["off_minus_def_height"] = matched["off_mean_height"] - matched["def_mean_height"]

before = matched.shape[0]
matched = matched.dropna(subset=["off_mean_height", "def_mean_height"]).copy()
print("rebound events with both lineups fully height-resolved:", matched.shape[0], "of", before)

keep_cols = [
    "game_id", "season", "period", "clock_seconds_remaining",
    "player1_id", "event_team_id", "offense_team_id", "defense_team_id",
    "is_orb", "off_mean_height", "def_mean_height", "off_minus_def_height",
] + off_cols + def_cols
matched[keep_cols].to_csv(f"{OUT}/rebound_events_height.csv", index=False)
print(f"wrote {OUT}/rebound_events_height.csv:", matched.shape[0], "rows")

# ---- player-season own rebounding rate (secure rate proxy), partition-internal ----
# opportunity events = missed field goals (rebound-eligible), partition only
opp = ev[ev["event_family"] == "missed_field_goal"].copy()
print("missed FG events in partition:", opp.shape)

# per player-season: count of rebounds secured (from full reb set, not just matched-with-lineup)
reb_all = reb.copy()
# need season per event via game->season map from filtered possessions (1:1)
game_season = poss[["game_id", "season"]].drop_duplicates().set_index("game_id")["season"]
reb_all["season"] = reb_all["game_id"].map(game_season)
reb_all = reb_all.dropna(subset=["season"])

player_reb_counts = reb_all.groupby(["player1_id", "season"]).size().rename("reb_count").reset_index()
# minutes proxy: count of all events a player appears in as player1 (rough proxy; no clean minutes table used)
opp["season"] = opp["game_id"].map(game_season)
player_reb_counts.to_csv(f"{OUT}/player_season_reb_counts.csv", index=False)
print(f"wrote {OUT}/player_season_reb_counts.csv:", player_reb_counts.shape[0], "rows")

print("DONE")
