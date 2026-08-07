"""
E0 I0006 analysis: is vacated usage redistribution concentrated, stable, and explained
by teammate composition? Exploration partition only (2021-2024), already enforced
upstream in build_redistribution.py.
"""
import pandas as pd
import numpy as np
import math

OUT = "experiments/exploration/E0_I0006_usage_redistribution"


def paired_ttest(a, b):
    d = np.asarray(a) - np.asarray(b)
    n = len(d)
    mean_d = d.mean()
    se = d.std(ddof=1) / math.sqrt(n)
    t = mean_d / se if se > 0 else np.nan
    # approx two-sided p via normal approx for large n (n here is in the hundreds)
    from math import erf
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / math.sqrt(2))))
    return t, p


def binom_test_approx(k, n, p0):
    # normal approximation to binomial test, two-sided (n is in the hundreds here)
    mean = n * p0
    sd = math.sqrt(n * p0 * (1 - p0))
    z = (k - mean) / sd if sd > 0 else np.nan
    from math import erf
    p = 2 * (1 - 0.5 * (1 + erf(abs(z) / math.sqrt(2))))
    return z, p

redis = pd.read_csv(f"{OUT}/redistribution_rows.csv")
absence = pd.read_csv(f"{OUT}/absence_games.csv")

print("=== BASIC COUNTS ===")
print("absence games (high-usage player DNP):", len(absence))
print("distinct absent players:", absence.player_id.nunique())
print("teammate-rows:", len(redis))
print("distinct absence-games with >=1 usable teammate row:", redis.absence_game_id.nunique())

# ---- Q1: concentration -- where does vacated usage go? one teammate, spread, or inconsistent? ----
def game_stats(g):
    pos = g[g.delta_usage > 0].sort_values("delta_usage", ascending=False)
    n_playing = len(g)
    total_pos_delta = pos.delta_usage.sum()
    top1_share = (pos.delta_usage.iloc[0] / total_pos_delta) if len(pos) and total_pos_delta > 0 else np.nan
    top2_share = (pos.delta_usage.iloc[:2].sum() / total_pos_delta) if len(pos) >= 2 and total_pos_delta > 0 else top1_share
    # Herfindahl index over positive deltas (0=perfectly spread, 1=one player takes all)
    if total_pos_delta > 0 and len(pos) > 0:
        shares = pos.delta_usage / total_pos_delta
        hhi = (shares ** 2).sum()
    else:
        hhi = np.nan
    return pd.Series({
        "n_playing": n_playing,
        "n_gainers": len(pos),
        "total_pos_delta": total_pos_delta,
        "top1_share": top1_share,
        "top2_share": top2_share,
        "hhi": hhi,
        "even_split_top1_baseline": 1.0 / len(pos) if len(pos) > 0 else np.nan,
    })

per_game = redis.groupby("absence_game_id").apply(game_stats).reset_index()
per_game.to_csv(f"{OUT}/per_absence_game_concentration.csv", index=False)

print("\n=== Q1: CONCENTRATION ===")
print("n absence-games with >=1 usage gainer:", per_game.n_gainers.gt(0).sum(), "/", len(per_game))
print("top1_share: mean=%.3f median=%.3f std=%.3f" % (
    per_game.top1_share.mean(), per_game.top1_share.median(), per_game.top1_share.std()))
print("even-split baseline (1/n_gainers): mean=%.3f median=%.3f" % (
    per_game.even_split_top1_baseline.mean(), per_game.even_split_top1_baseline.median()))
print("HHI: mean=%.3f median=%.3f  (1/n_gainers avg=%.3f would be even split)" % (
    per_game.hhi.mean(), per_game.hhi.median(), (1/per_game.n_gainers.replace(0,np.nan)).mean()))
t_top1, p_top1 = paired_ttest(per_game.top1_share.dropna(),
                               per_game.loc[per_game.top1_share.notna(), "even_split_top1_baseline"])
print(f"paired t-test top1_share vs even-split baseline: t={t_top1:.2f} p={p_top1:.4f}")

# ---- Q2/Q3: stability -- for a given absent player, is the SAME teammate the top absorber repeatedly? ----
print("\n=== Q2/Q3: STABILITY (same player, repeat absences) ===")
top_absorber = (
    redis.sort_values("delta_usage", ascending=False)
    .groupby("absence_game_id")
    .first()[["absent_player_id", "absent_player_name", "player_id", "player_name", "delta_usage", "season"]]
    .reset_index()
    .rename(columns={"player_id": "top_absorber_id", "player_name": "top_absorber_name"})
)
top_absorber.to_csv(f"{OUT}/top_absorber_per_game.csv", index=False)

counts = top_absorber.groupby("absent_player_id").absence_game_id.count()
repeat_players = counts[counts >= 3].index
print(f"absent players with >=3 usable absence games: {len(repeat_players)} (out of {counts.shape[0]} with any)")

consistency_rows = []
for pid in repeat_players:
    sub = top_absorber[top_absorber.absent_player_id == pid]
    mode_absorber = sub.top_absorber_id.mode()
    if len(mode_absorber) == 0:
        continue
    mode_id = mode_absorber.iloc[0]
    frac_mode = (sub.top_absorber_id == mode_id).mean()
    n_unique_absorbers = sub.top_absorber_id.nunique()
    consistency_rows.append({
        "absent_player_id": pid,
        "absent_player_name": sub.absent_player_name.iloc[0],
        "n_absences": len(sub),
        "n_unique_top_absorbers": n_unique_absorbers,
        "modal_absorber_share": frac_mode,
    })
consistency = pd.DataFrame(consistency_rows)
consistency.to_csv(f"{OUT}/stability_by_player.csv", index=False)
print("modal top-absorber share across repeat-absence players: mean=%.3f median=%.3f" % (
    consistency.modal_absorber_share.mean(), consistency.modal_absorber_share.median()))
print("distribution of n_unique_top_absorbers (lower = more consistent):")
print(consistency.n_unique_top_absorbers.value_counts().sort_index())

# ---- Q4: does teammate composition explain it? "next-highest-baseline-usage teammate absorbs it" ----
print("\n=== Q4: TEAMMATE COMPOSITION -- does highest-baseline-usage available teammate absorb it? ===")
# For each absence game: among teammates who played (in redis), does the top absorber == the
# teammate with the HIGHEST tm_baseline_usage among those present (i.e. the "next man up" by
# pecking order, not by who happened to have a hot game)?
def pecking_order_check(g):
    n = len(g)
    if n == 0:
        return pd.Series({"top_absorber_is_highest_baseline_usage": np.nan, "n_playing": n})
    top_absorber_row = g.sort_values("delta_usage", ascending=False).iloc[0]
    highest_baseline_row = g.sort_values("tm_baseline_usage", ascending=False).iloc[0]
    match = top_absorber_row.player_id == highest_baseline_row.player_id
    return pd.Series({"top_absorber_is_highest_baseline_usage": match, "n_playing": n})

pecking = redis.groupby("absence_game_id").apply(pecking_order_check).reset_index()
pecking = pecking[pecking.n_playing > 0]
match_rate = pecking.top_absorber_is_highest_baseline_usage.mean()
baseline_rate = (1.0 / pecking.n_playing).mean()  # chance rate if random teammate absorbed
print(f"n absence-games evaluated: {len(pecking)}")
print(f"observed match rate (top absorber == highest-baseline-usage teammate present): {match_rate:.3f}")
print(f"naive random-chance baseline (avg of 1/n_playing): {baseline_rate:.3f}")

# binomial test vs naive baseline (using mean n_playing as an approx), normal approximation
avg_n = pecking.n_playing.mean()
k = int(pecking.top_absorber_is_highest_baseline_usage.sum())
n = len(pecking)
z, p_bt = binom_test_approx(k, n, 1 / avg_n)
print(f"binomial test (normal approx) vs p=1/{avg_n:.1f}: observed successes={k}/{n}, z={z:.2f}, p-value={p_bt:.2e}")

print("\nDONE analyze.py")
