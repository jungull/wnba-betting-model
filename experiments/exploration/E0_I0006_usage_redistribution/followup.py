"""
Follow-up checks on the E0 I0006 concentration/stability/composition results:
1. What RANK (by teammate season-baseline usage, among those present) is the actual top
   absorber, typically? (refines the null Q4 result -- maybe it's rank 2/3, not rank 1)
2. Is delta_usage driven mostly by extra MINUTES rather than per-minute usage rate change?
Exploration partition only (2021-2024), inherited from upstream files already filtered.
"""
import pandas as pd
import numpy as np

OUT = "experiments/exploration/E0_I0006_usage_redistribution"
redis = pd.read_csv(f"{OUT}/redistribution_rows.csv")

# ---- rank of top absorber by season-baseline usage among those present ----
def rank_of_top_absorber(g):
    g = g.copy()
    g["baseline_rank"] = g.tm_baseline_usage.rank(ascending=False, method="first")
    top = g.sort_values("delta_usage", ascending=False).iloc[0]
    return pd.Series({"top_absorber_baseline_rank": top.baseline_rank, "n_playing": len(g)})

ranks = redis.groupby("absence_game_id").apply(rank_of_top_absorber).reset_index()
print("=== rank (by season-baseline usage) of the actual top usage-gainer, among teammates present ===")
print(ranks.top_absorber_baseline_rank.value_counts().sort_index().head(10))
print("mean rank:", ranks.top_absorber_baseline_rank.mean(), " (rank 1 = highest-baseline-usage teammate present)")
print("share where top absorber is baseline rank 1, 2, or 3:",
      (ranks.top_absorber_baseline_rank <= 3).mean())
print("naive random baseline for rank<=3 given avg n_playing=%.1f: %.3f" % (
    ranks.n_playing.mean(), 3 / ranks.n_playing.mean()))

# ---- is delta_usage explained by extra minutes rather than per-minute usage change? ----
# proxy: correlate delta_usage with minutes (we don't have teammate baseline minutes in this
# file; approximate using games available). Instead check within-game: does the player with
# the biggest minutes increase tend to be the top usage gainer? We only have this game's
# minutes here, not baseline minutes, so just report the correlation between delta_usage and
# minutes played this game (crude, directional only).
corr = redis[["delta_usage", "minutes"]].corr().iloc[0, 1]
print("\ncorrelation(delta_usage, minutes played in absence game), crude/uncontrolled:", round(corr, 3))

print("\nDONE followup.py")
