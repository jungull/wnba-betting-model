"""
E0 I0005 -- does player turnover tendency interact with opponent defensive pressure,
beyond a pooled turnover rate?

Reads player_game_analysis.csv (already partition-filtered to 2021-2024, built by
build_data.py). This script does not touch any raw source file itself.
"""
import math
import numpy as np
import pandas as pd

OUT = r"C:\Users\jgallagher\wnba-betting-model\.claude\worktrees\player-model-program\experiments\exploration\E0_I0005_turnover_interaction"

df = pd.read_csv(f"{OUT}/player_game_analysis.csv")
assert set(df["season"].unique()).issubset({2021, 2022, 2023, 2024}), "PARTITION VIOLATION"
print("rows:", len(df), "seasons:", sorted(df["season"].unique()))

Y = df["turnovers_per_100_off_poss"].to_numpy(float)
X1 = df["player_tendency_loo"].to_numpy(float)   # player's own LOO turnover-rate tendency
X2 = df["opponent_pressure_loo"].to_numpy(float)  # opponent defense's LOO forced-TO rate
W = df["realised_off_possessions"].to_numpy(float)  # exposure weight (games with more possessions are measured less noisily)

def wls(y, X, w):
    """Weighted least squares via normal equations. X must include intercept column."""
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    yw = y * sw
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    sse = float(resid @ resid)
    sst = float(((yw - yw.mean()) ** 2).sum())
    r2 = 1 - sse / sst if sst > 0 else np.nan
    return beta, r2, sse

def design(*cols):
    return np.column_stack([np.ones(len(cols[0]))] + list(cols))

# Model A: pooled -- player tendency only (this is the "pooled turnover rate" baseline;
#          it already reflects individual tendency, so it is a strong baseline, not a naive league mean)
XA = design(X1)
betaA, r2A, sseA = wls(Y, XA, W)

# Model B: additive -- player tendency + opponent pressure, no interaction
XB = design(X1, X2)
betaB, r2B, sseB = wls(Y, XB, W)

# Model C: interaction -- player tendency x opponent pressure added
inter = X1 * X2
XC = design(X1, X2, inter)
betaC, r2C, sseC = wls(Y, XC, W)

print("\n=== Weighted least squares (weight = realised_off_possessions) ===")
print(f"Model A (tendency only):            R2={r2A:.5f}  beta={betaA}")
print(f"Model B (tendency + pressure):       R2={r2B:.5f}  beta={betaB}")
print(f"Model C (tendency + pressure + x):   R2={r2C:.5f}  beta={betaC}")
print(f"R2 improvement B->C (interaction beyond additive): {r2C - r2B:.6f}")
print(f"R2 improvement A->B (pressure beyond pooled tendency alone): {r2B - r2A:.6f}")

# ---------------------------------------------------------------------------
# Partial-correlation test for the interaction term, with a permutation null.
# Residualize Y and the interaction term against the additive model (X1, X2, intercept),
# then correlate the residuals. This isolates what the interaction uniquely explains.
# Permutation: shuffle player_tendency_loo WITHIN season (breaks the true player<->game
# pairing while preserving each season's marginal distributions and the opponent side).
# ---------------------------------------------------------------------------
def residualize(y, X):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return y - X @ beta

Xadd = design(X1, X2)
resid_Y = residualize(Y, Xadd)
resid_inter = residualize(inter, Xadd)
obs_stat = float(np.corrcoef(resid_Y, resid_inter)[0, 1])
print(f"\nObserved partial correlation (interaction vs residual Y | tendency, pressure): {obs_stat:.5f}")

rng = np.random.default_rng(20260807)
n_perm = 2000
season_arr = df["season"].to_numpy()
null_stats = np.empty(n_perm)
for i in range(n_perm):
    X1_perm = X1.copy()
    for s in np.unique(season_arr):
        idx = np.where(season_arr == s)[0]
        X1_perm[idx] = rng.permutation(X1_perm[idx])
    inter_perm = X1_perm * X2
    Xadd_perm = design(X1_perm, X2)
    ry = residualize(Y, Xadd_perm)
    ri = residualize(inter_perm, Xadd_perm)
    null_stats[i] = np.corrcoef(ry, ri)[0, 1]

p_two_sided = float(np.mean(np.abs(null_stats) >= abs(obs_stat)))
print(f"Permutation null (n={n_perm}, within-season shuffle of player tendency): "
      f"mean={null_stats.mean():.5f} sd={null_stats.std():.5f}")
print(f"Two-sided permutation p-value for interaction: {p_two_sided:.4f}")

# ---------------------------------------------------------------------------
# Tercile heatmap: player tendency tercile (within season) x opponent pressure tercile
# (within season) -> mean observed turnover rate, weighted by exposure.
# ---------------------------------------------------------------------------
def within_season_tercile(s, x):
    out = np.empty(len(x), dtype=int)
    for season in np.unique(s):
        idx = np.where(s == season)[0]
        q = pd.qcut(x[idx], 3, labels=False, duplicates="drop")
        out[idx] = q
    return out

df["tend_tercile"] = within_season_tercile(season_arr, X1)
df["press_tercile"] = within_season_tercile(season_arr, X2)

def wmean(g):
    return np.average(g["turnovers_per_100_off_poss"], weights=g["realised_off_possessions"])

heat = df.groupby(["tend_tercile", "press_tercile"]).apply(wmean, include_groups=False).unstack()
print("\n=== Weighted mean turnover_per_100_off_poss by tercile (rows=player tendency, cols=opponent pressure) ===")
print(heat.round(3))
heat.to_csv(f"{OUT}/tercile_heatmap.csv")

# slope of turnover rate vs opponent pressure tercile, separately for low vs high tendency group
low_slope = heat.loc[0, 2] - heat.loc[0, 0]
high_slope = heat.loc[2, 2] - heat.loc[2, 0]
print(f"\nLow-tendency group: rate diff (high press - low press) = {low_slope:.3f}")
print(f"High-tendency group: rate diff (high press - low press) = {high_slope:.3f}")
print(f"Difference-in-differences (high tendency slope - low tendency slope): {high_slope - low_slope:.3f}")

# ---------------------------------------------------------------------------
# Per-season replication of the partial-correlation sign/magnitude
# ---------------------------------------------------------------------------
print("\n=== Per-season partial correlation (interaction vs residual Y | tendency, pressure) ===")
season_results = {}
for s in sorted(df["season"].unique()):
    idx = season_arr == s
    Xadd_s = design(X1[idx], X2[idx])
    ry = residualize(Y[idx], Xadd_s)
    ri = residualize(inter[idx], Xadd_s)
    stat = float(np.corrcoef(ry, ri)[0, 1])
    season_results[int(s)] = stat
    print(f"season {s}: n={idx.sum()}  partial_corr={stat:.5f}")

# ---------------------------------------------------------------------------
# Role concentration: does whatever signal exists concentrate in high-minutes players?
# ---------------------------------------------------------------------------
df["minutes_tercile"] = within_season_tercile(season_arr, df["minutes"].to_numpy(float))
print("\n=== Per role (minutes tercile) partial correlation ===")
for m in sorted(df["minutes_tercile"].unique()):
    idx = (df["minutes_tercile"] == m).to_numpy()
    Xadd_m = design(X1[idx], X2[idx])
    ry = residualize(Y[idx], Xadd_m)
    ri = residualize(inter[idx], Xadd_m)
    stat = float(np.corrcoef(ry, ri)[0, 1])
    print(f"minutes tercile {m}: n={idx.sum()}  partial_corr={stat:.5f}")

# ---------------------------------------------------------------------------
# Feature-availability / missingness sanity check (explicit per the Arm-G leakage prior).
# Confirm the 13 rows dropped for undefined LOO tendency/pressure are NOT concentrated
# in unusual outcome values (would indicate a missingness-outcome correlation).
# ---------------------------------------------------------------------------
print("\n=== Missingness sanity check ===")
print(f"Rows with rate_defined but undefined LOO predictors were dropped upstream in build_data.py.")
print(f"Final frame outcome summary (for reference, not a leakage claim by itself):")
print(df["turnovers_per_100_off_poss"].describe())

summary = {
    "n_rows": int(len(df)),
    "r2_A_tendency_only": r2A,
    "r2_B_additive": r2B,
    "r2_C_interaction": r2C,
    "r2_gain_interaction_over_additive": r2C - r2B,
    "r2_gain_pressure_over_pooled": r2B - r2A,
    "partial_corr_interaction": obs_stat,
    "permutation_p_value": p_two_sided,
    "beta_C_intercept_tendency_pressure_interaction": betaC.tolist(),
    "tercile_diff_in_diff": float(high_slope - low_slope),
    "per_season_partial_corr": season_results,
}
import json
with open(f"{OUT}/summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print("\nwrote summary.json")
