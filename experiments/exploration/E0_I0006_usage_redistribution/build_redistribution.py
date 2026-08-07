"""
E0 I0006 -- usage redistribution screen.
HARD RULE: exploration partition only. season in [2021,2024]. Never touch 2025/2026.
Uses data/masters/master_player.parquet (per-player-per-game box score, includes
usage_percentage, minutes, dnp_reason). No on-court clock-time lineup join needed,
so this screen does NOT inherit the ~72% side-of-play attribution noise found in I0003.
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0006_usage_redistribution"

df = pd.read_parquet("data/masters/master_player.parquet")

# ---- HARD PARTITION FILTER, applied immediately ----
assert set(df.season.unique()) >= {2021, 2022, 2023, 2024, 2025, 2026}
d = df[df.season.between(2021, 2024)].copy()
d = d[d.season_type == "Regular Season"].copy()
print("post-filter seasons present:", sorted(d.season.unique()))
print("rows after partition+regular-season filter:", len(d))
assert d.season.max() <= 2024 and d.season.min() >= 2021

d["played"] = d.minutes.fillna(0) > 0
d["is_dnp"] = d.dnp_reason.notna()

# ---- 1. baseline usage per player-team-season (games actually played) ----
played = d[d.played]
baseline = (
    played.groupby(["player_id", "player_name", "team_id", "season"])
    .agg(baseline_usage=("usage_percentage", "mean"), games_played=("game_id", "count"))
    .reset_index()
)

# high-usage rotation regulars: baseline usage >= 0.20, games_played >= 15
hi = baseline[(baseline.baseline_usage >= 0.20) & (baseline.games_played >= 15)].copy()
print("high-usage player-team-season rows:", len(hi))
hi.to_csv(f"{OUT}/high_usage_players.csv", index=False)

# ---- 2. absence games for each high-usage player-team-season ----
absence_rows = []
d_idx = d.set_index(["player_id", "team_id", "season"])

for _, row in hi.iterrows():
    pid, tid, season = row.player_id, row.team_id, row.season
    try:
        sub = d_idx.loc[(pid, tid, season)]
    except KeyError:
        continue
    if isinstance(sub, pd.Series):
        sub = sub.to_frame().T
    absences = sub[(sub.is_dnp) & (~sub.played)]
    for _, arow in absences.iterrows():
        absence_rows.append({
            "player_id": pid, "player_name": row.player_name, "team_id": tid,
            "season": season, "game_id": arow.game_id, "game_date": arow.game_date,
            "dnp_reason": arow.dnp_reason, "baseline_usage": row.baseline_usage,
            "games_played_season": row.games_played,
        })

absence_df = pd.DataFrame(absence_rows)
print("total absence-game rows (high-usage players, DNP with reason):", len(absence_df))
absence_df.to_csv(f"{OUT}/absence_games.csv", index=False)

# ---- 3. for each absence game, teammates who played + their delta usage vs baseline ----
# teammate baseline = mean usage_percentage in OTHER games that season/team where the
# absent player DID play (control games), restricted to teammates who played >=5 such
# games with the absent player (avoid callups / small samples).
records = []
for _, arow in absence_df.iterrows():
    pid, tid, season, gid = arow.player_id, arow.team_id, arow.season, arow.game_id
    # control games: same team/season, player played, excluding this absence game itself (trivially true)
    control_games = played[(played.team_id == tid) & (played.season == season) & (played.player_id == pid)].game_id.unique()
    control = played[(played.team_id == tid) & (played.season == season) & (played.game_id.isin(control_games)) & (played.player_id != pid)]
    tm_baseline = control.groupby(["player_id", "player_name"]).agg(
        tm_baseline_usage=("usage_percentage", "mean"), n_control_games=("game_id", "count")
    ).reset_index()
    tm_baseline = tm_baseline[tm_baseline.n_control_games >= 5]

    game_rows = d[(d.game_id == gid) & (d.team_id == tid) & (d.played) & (d.player_id != pid)]
    merged = game_rows.merge(tm_baseline, on=["player_id", "player_name"], how="inner")
    if merged.empty:
        continue
    merged["delta_usage"] = merged.usage_percentage - merged.tm_baseline_usage
    merged["absent_player_id"] = pid
    merged["absent_player_name"] = arow.player_name
    merged["absent_baseline_usage"] = arow.baseline_usage
    merged["absence_game_id"] = gid
    merged["season"] = season
    merged["dnp_reason"] = arow.dnp_reason
    records.append(merged[["absent_player_id", "absent_player_name", "absent_baseline_usage",
                            "absence_game_id", "season", "dnp_reason", "team_id",
                            "player_id", "player_name", "usage_percentage",
                            "tm_baseline_usage", "n_control_games", "delta_usage", "minutes"]])

redis = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
print("teammate-level redistribution rows:", len(redis))
redis.to_csv(f"{OUT}/redistribution_rows.csv", index=False)

print("DONE build_redistribution.py")
