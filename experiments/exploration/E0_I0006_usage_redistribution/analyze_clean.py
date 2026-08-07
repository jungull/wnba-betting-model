"""
Clean re-analysis using ONLY uncontaminated raw sources (clean_played_panel.parquet,
clean_roster_panel.parquet from rebuild_clean.py). Redoes: (1) pooled concentration + placebo,
then (2) the user-mandated conditional cuts -- starter vs bench absence, absent player's
position, team (coach proxy), and remaining-lineup composition (simultaneous absences) -- each
compared against its own matched placebo so a conditional slice isn't just noisier-N noise.

Exploration partition only: 2021-2024, inherited from rebuild_clean.py's file-level filtering.
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0006_usage_redistribution"
rng = np.random.default_rng(7)

played = pd.read_parquet(f"{OUT}/clean_played_panel.parquet")
roster = pd.read_parquet(f"{OUT}/clean_roster_panel.parquet")

# ---- high-usage rotation regulars (same thresholds as before: >=0.20 mean usage, >=15 GP) ----
baseline = played.groupby(["player_id", "player_name", "team_id", "season"]).agg(
    baseline_usage=("usage_percentage", "mean"), games_played=("game_id", "count"),
    start_rate=("start_position", lambda s: (s.fillna("") != "").mean()),
).reset_index()
hi = baseline[(baseline.baseline_usage >= 0.20) & (baseline.games_played >= 15)].copy()
hi["is_starter_type"] = hi.start_rate >= 0.5
print("high-usage player-team-seasons (clean rebuild):", len(hi))
hi.to_csv(f"{OUT}/clean_high_usage_players.csv", index=False)

# position lookup (player_bios.csv; per-season raw API pull, no manifest -> treated as
# uncontaminated raw capture, consistent with the other raw sources used here; simplified
# to G/F/C/Hybrid)
bios = pd.read_csv("data/reference/player_bios.csv")
bios = bios[bios.season.between(2021, 2024)][["player_id", "season", "position_raw"]]
def simplify(pos):
    if pd.isna(pos):
        return None
    pos = str(pos)
    has = lambda s: s in pos
    if has("Guard") and not has("Forward") and not has("Center"):
        return "G"
    if has("Forward") and not has("Guard") and not has("Center"):
        return "F"
    if has("Center") and not has("Forward") and not has("Guard"):
        return "C"
    return "Hybrid"
bios["pos_simple"] = bios.position_raw.apply(simplify)
hi = hi.merge(bios[["player_id", "season", "pos_simple"]], on=["player_id", "season"], how="left")

# ---- absence games from roster panel (DNP rows for high-usage players) ----
roster_idx = roster.set_index(["player_id", "team_id", "season"])
absence_rows = []
for _, row in hi.iterrows():
    key = (row.player_id, row.team_id, row.season)
    if key not in roster_idx.index:
        continue
    sub = roster_idx.loc[[key]] if key in roster_idx.index else pd.DataFrame()
    absences = sub[sub.is_dnp]
    for _, arow in absences.iterrows():
        absence_rows.append({
            "player_id": row.player_id, "player_name": row.player_name, "team_id": row.team_id,
            "season": row.season, "game_id": arow.game_id, "comment": arow.comment,
            "baseline_usage": row.baseline_usage, "is_starter_type": row.is_starter_type,
            "pos_simple": row.pos_simple,
        })
absence_df = pd.DataFrame(absence_rows).drop_duplicates(subset=["player_id", "team_id", "season", "game_id"])
print("absence-game rows (clean rebuild):", len(absence_df))
absence_df.to_csv(f"{OUT}/clean_absence_games.csv", index=False)

# how many high-usage teammates absent simultaneously in the same team-game (composition cut)
absence_df["co_absent_count"] = absence_df.groupby(["team_id", "game_id"]).player_id.transform("count")

# ---- redistribution rows: teammate deltas vs baseline (control games = player's presence games) ----
def build_redistribution(event_rows, leave_one_out=False):
    """event_rows: list of dicts with player_id, team_id, season, game_id (event game).
    leave_one_out: if True, event_gid is itself one of the player's presence games and must be
    excluded from the baseline (placebo case)."""
    out = []
    for r in event_rows:
        pid, tid, season, gid = r["player_id"], r["team_id"], r["season"], r["game_id"]
        pres_games = played[(played.team_id == tid) & (played.season == season) &
                             (played.player_id == pid)].game_id.unique()
        control_games = [g for g in pres_games if not (leave_one_out and g == gid)]
        if len(control_games) < 6:
            continue
        control = played[(played.team_id == tid) & (played.season == season) &
                          (played.game_id.isin(control_games)) & (played.player_id != pid)]
        tm_baseline = control.groupby(["player_id", "player_name"]).agg(
            tm_baseline_usage=("usage_percentage", "mean"), n_control_games=("game_id", "count")
        ).reset_index()
        tm_baseline = tm_baseline[tm_baseline.n_control_games >= 5]
        game_rows = played[(played.game_id == gid) & (played.team_id == tid) & (played.player_id != pid)]
        merged = game_rows.merge(tm_baseline, on=["player_id", "player_name"], how="inner")
        if merged.empty:
            continue
        merged["delta_usage"] = merged.usage_percentage - merged.tm_baseline_usage
        merged["event_key"] = f"{pid}_{tid}_{season}_{gid}"
        out.append(merged)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()

real_events = absence_df.to_dict("records")
real_redis = build_redistribution(real_events, leave_one_out=False)
real_redis.to_csv(f"{OUT}/clean_redistribution_rows.csv", index=False)
print("clean teammate-level redistribution rows:", len(real_redis))

# placebo: one random OWN presence game per high-usage player-team-season, matched n
placebo_events = []
for _, row in hi.sample(frac=1.0, random_state=7).iterrows():
    pres_games = played[(played.team_id == row.team_id) & (played.season == row.season) &
                         (played.player_id == row.player_id)].game_id.unique()
    if len(pres_games) < 7:
        continue
    gid = rng.choice(pres_games)
    placebo_events.append({"player_id": row.player_id, "team_id": row.team_id,
                            "season": row.season, "game_id": gid})
placebo_redis = build_redistribution(placebo_events, leave_one_out=True)
print("placebo teammate-level rows:", len(placebo_redis))


def top1_share_per_event(redis_df, key_col="event_key"):
    def f(g):
        pos = g[g.delta_usage > 0].sort_values("delta_usage", ascending=False)
        if len(pos) == 0 or pos.delta_usage.sum() <= 0:
            return pd.Series({"top1_share": np.nan, "n_gainers": len(pos)})
        return pd.Series({"top1_share": pos.delta_usage.iloc[0] / pos.delta_usage.sum(),
                           "n_gainers": len(pos)})
    return redis_df.groupby(key_col).apply(f).reset_index()

real_summary = top1_share_per_event(real_redis)
placebo_summary = top1_share_per_event(placebo_redis)
print("\n=== POOLED (clean rebuild) ===")
print("real absence-games top1_share: mean=%.3f median=%.3f n=%d" % (
    real_summary.top1_share.mean(), real_summary.top1_share.median(), real_summary.top1_share.notna().sum()))
print("placebo top1_share: mean=%.3f median=%.3f n=%d" % (
    placebo_summary.top1_share.mean(), placebo_summary.top1_share.median(), placebo_summary.top1_share.notna().sum()))

# map event_key back to absence_df attributes for conditional cuts
real_summary["event_key_parts"] = real_summary.event_key.str.split("_")
real_summary["player_id"] = real_summary.event_key_parts.apply(lambda x: int(x[0]))
real_summary["team_id"] = real_summary.event_key_parts.apply(lambda x: int(x[1]))
real_summary["season"] = real_summary.event_key_parts.apply(lambda x: int(x[2]))
real_summary["game_id"] = real_summary.event_key_parts.apply(lambda x: x[3])
real_summary = real_summary.merge(
    absence_df[["player_id", "team_id", "season", "game_id", "is_starter_type", "pos_simple", "co_absent_count"]],
    on=["player_id", "team_id", "season", "game_id"], how="left")
real_summary.to_csv(f"{OUT}/clean_per_absence_game_summary.csv", index=False)

print("\n=== CONDITIONAL CUTS (real absence games only; placebo pooled mean = %.3f is the noise floor) ===" % placebo_summary.top1_share.mean())

print("\n-- by starter-type of absent player --")
print(real_summary.groupby("is_starter_type").top1_share.agg(["mean", "median", "count"]))

print("\n-- by position of absent player --")
print(real_summary.groupby("pos_simple").top1_share.agg(["mean", "median", "count"]))

print("\n-- by team_id (coach proxy) --")
team_tbl = real_summary.groupby("team_id").top1_share.agg(["mean", "median", "count"])
print(team_tbl.sort_values("mean", ascending=False))
print("std of team means:", team_tbl["mean"].std(), " vs pooled std of individual games:", real_summary.top1_share.std())

print("\n-- by simultaneous co-absence count (remaining-lineup composition) --")
real_summary["co_absent_bucket"] = np.where(real_summary.co_absent_count >= 2, "2+_simultaneous", "1_alone")
print(real_summary.groupby("co_absent_bucket").top1_share.agg(["mean", "median", "count"]))

print("\nDONE analyze_clean.py")
