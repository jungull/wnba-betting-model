"""
Placebo/robustness check: is the observed top1_share concentration (mean 0.397 vs even-split
0.199) actually a response to the absence, or just ordinary game-to-game noise in usage_percentage
(i.e. SOME teammate always has a relatively big game purely by chance, which would produce
apparent "concentration" even with no true redistribution effect)?

Method: for a matched sample of PRESENCE games (the studied player DID play -- these are exactly
the "control games" used to build teammate baselines), leave one control game out, recompute each
teammate's baseline from the REMAINING control games, and compute delta_usage + top1_share exactly
as in analyze.py. If placebo top1_share ~= observed 0.397, the concentration finding is noise, not
signal. If placebo top1_share is much lower (near even-split ~0.20), the concentration on true
absence games is real.

Exploration partition only (2021-2024), inherited from upstream filtering.
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0006_usage_redistribution"

df = pd.read_parquet("data/masters/master_player.parquet")
d = df[df.season.between(2021, 2024)]
d = d[d.season_type == "Regular Season"].copy()
d["played"] = d.minutes.fillna(0) > 0
played = d[d.played]

hi = pd.read_csv(f"{OUT}/high_usage_players.csv")
absence = pd.read_csv(f"{OUT}/absence_games.csv")

rng = np.random.default_rng(42)
records = []
n_target = 335  # match the n of real absence-games with usable teammate rows

# sample (player, team, season) rows from hi, then sample one of THEIR OWN control (presence) games
hi_shuf = hi.sample(frac=1.0, random_state=42).reset_index(drop=True)

count = 0
for _, row in hi_shuf.iterrows():
    if count >= n_target:
        break
    pid, tid, season = row.player_id, row.team_id, row.season
    control_games = played[(played.team_id == tid) & (played.season == season) & (played.player_id == pid)].game_id.unique()
    if len(control_games) < 6:
        continue
    # pick one "pseudo-event" game at random from the player's OWN presence games
    event_gid = rng.choice(control_games)
    remaining_games = [g for g in control_games if g != event_gid]

    control = played[(played.team_id == tid) & (played.season == season) & (played.game_id.isin(remaining_games)) & (played.player_id != pid)]
    tm_baseline = control.groupby(["player_id", "player_name"]).agg(
        tm_baseline_usage=("usage_percentage", "mean"), n_control_games=("game_id", "count")
    ).reset_index()
    tm_baseline = tm_baseline[tm_baseline.n_control_games >= 5]

    game_rows = d[(d.game_id == event_gid) & (d.team_id == tid) & (d.played) & (d.player_id != pid)]
    merged = game_rows.merge(tm_baseline, on=["player_id", "player_name"], how="inner")
    if merged.empty:
        continue
    merged["delta_usage"] = merged.usage_percentage - merged.tm_baseline_usage
    pos = merged[merged.delta_usage > 0].sort_values("delta_usage", ascending=False)
    if len(pos) == 0 or pos.delta_usage.sum() <= 0:
        continue
    top1_share = pos.delta_usage.iloc[0] / pos.delta_usage.sum()
    records.append({"player_id": pid, "team_id": tid, "season": season, "event_gid": event_gid,
                     "n_gainers": len(pos), "top1_share": top1_share,
                     "even_split_baseline": 1.0 / len(pos)})
    count += 1

placebo = pd.DataFrame(records)
placebo.to_csv(f"{OUT}/placebo_presence_games.csv", index=False)
print("placebo n:", len(placebo))
print("placebo top1_share: mean=%.3f median=%.3f" % (placebo.top1_share.mean(), placebo.top1_share.median()))
print("placebo even-split baseline: mean=%.3f" % placebo.even_split_baseline.mean())
print("\nREAL absence-game top1_share (from analyze.py): mean=0.397 median=0.385 (n=335)")
print("PLACEBO presence-game top1_share (this script):   mean=%.3f median=%.3f (n=%d)" % (
    placebo.top1_share.mean(), placebo.top1_share.median(), len(placebo)))

print("\nDONE placebo_check.py")
